"""v97b: Full-volume sub-canonical 3D U-Net at 64×96×96 on UCSF subset
(memory-efficient; processes one patient at a time during evaluation).

Memory-efficient version of v97. Trains a 3D BasicUNet at 64×96×96 (4×
linear scale of 16×48×48 cropcache; 3.4× volume scale; closer to canonical
full-resolution than the cropcache).

Subset: 80 randomly-chosen UCSF-POSTOP patients (60 train / 20 test).

Outputs:
  C:/Users/kamru/Downloads/Nature_project/05_results/v97b_full_volume_subset.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from monai.networks.nets import BasicUNet
from scipy.ndimage import gaussian_filter, zoom
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "v77_ucsf_raw_mri_cache.npz"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EPOCHS = 30
BATCH = 1
SEED = 9702
SIGMA = 2.5
TARGET_SHAPE = (64, 96, 96)  # 4× linear scale of 16×48×48; memory-safe
N_SUBSET = 80


def patient_brier(pred, target):
    pred = np.clip(pred, 1e-6, 1 - 1e-6)
    return float(((pred - target) ** 2).mean())


def heat_kernel(mask, sigma=SIGMA * 4):
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    mx = float(h.max())
    return (h / mx).astype(np.float32) if mx > 0 else h.astype(np.float32)


def upsample_one(arr, target_shape):
    if arr.ndim == 3:
        zf = tuple(t / s for t, s in zip(target_shape, arr.shape))
        return zoom(arr.astype(np.float32), zf, order=1)
    elif arr.ndim == 4:
        zf = (1,) + tuple(t / s for t, s in zip(target_shape, arr.shape[1:]))
        return zoom(arr.astype(np.float32), zf, order=1)
    raise ValueError


def main():
    import gc
    print("=" * 78)
    print(f"v97b FULL-VOLUME SUB-CANONICAL 3D U-NET AT {TARGET_SHAPE} ON UCSF (subset N={N_SUBSET})")
    print("=" * 78)

    cache = dict(np.load(CACHE, allow_pickle=True))
    raw = cache["raw"]
    mask = cache["mask"]
    target = cache["target"]
    n_total = len(raw)
    print(f"UCSF cache total: N={n_total}; using random subset N={N_SUBSET}")

    np.random.seed(SEED)
    perm = np.random.permutation(n_total)[:N_SUBSET]
    perm_train = perm[:60]
    perm_test = perm[60:]

    print(f"Up-sampling subset to {TARGET_SHAPE} (per-patient, memory-safe)...")
    t0 = time.time()

    # Train data — up-sample one at a time
    Xtr_list, Ytr_list = [], []
    for j, idx in enumerate(perm_train):
        r = upsample_one(raw[idx], TARGET_SHAPE)
        m = upsample_one(mask[idx], TARGET_SHAPE)
        t = upsample_one(target[idx], TARGET_SHAPE)
        Xtr_list.append(np.concatenate([r, m[None]], axis=0).astype(np.float32))
        Ytr_list.append(t[None].astype(np.float32))
        del r, m, t
        gc.collect()
        if (j + 1) % 10 == 0:
            print(f"  Train up-sample {j+1}/{len(perm_train)}  ({time.time()-t0:.0f}s)", flush=True)
    Xtr = np.stack(Xtr_list)
    Ytr = np.stack(Ytr_list)
    del Xtr_list, Ytr_list
    gc.collect()
    print(f"  Train shape: {Xtr.shape}; size {Xtr.nbytes/1e6:.0f} MB")

    # Test data
    Xte_list, Yte_list = [], []
    heat_test_list = []
    target_test_list = []
    for idx in perm_test:
        r = upsample_one(raw[idx], TARGET_SHAPE)
        m = upsample_one(mask[idx], TARGET_SHAPE)
        t = upsample_one(target[idx], TARGET_SHAPE)
        h = heat_kernel(m, sigma=SIGMA * 4)
        Xte_list.append(np.concatenate([r, m[None]], axis=0).astype(np.float32))
        Yte_list.append(t[None].astype(np.float32))
        heat_test_list.append(h)
        target_test_list.append(t)
        del r, m, t, h
        gc.collect()
    Xte = np.stack(Xte_list)
    Yte = np.stack(Yte_list)
    heat_test = np.stack(heat_test_list)
    target_test = np.stack(target_test_list)
    print(f"  Test shape: {Xte.shape}")

    model = BasicUNet(spatial_dims=3, in_channels=5, out_channels=1,
                     features=(16, 32, 64, 128, 256, 32)).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Model: BasicUNet 3D, {n_params/1e6:.2f} M params")

    optim = torch.optim.AdamW(model.parameters(), lr=5e-4)
    bce = nn.BCEWithLogitsLoss()

    Xt = torch.from_numpy(Xtr).float()
    Yt = torch.from_numpy(Ytr).float()
    loader = DataLoader(TensorDataset(Xt, Yt), batch_size=BATCH, shuffle=True)

    print(f"\nTraining for {EPOCHS} epochs...")
    t0 = time.time()
    for ep in range(EPOCHS):
        model.train()
        ep_loss = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            logits = model(xb)
            loss = bce(logits, yb)
            optim.zero_grad(); loss.backward(); optim.step()
            ep_loss += loss.item()
        if (ep + 1) % 5 == 0:
            print(f"  epoch {ep+1}/{EPOCHS} loss={ep_loss/len(loader):.4f}  ({time.time()-t0:.0f}s)", flush=True)
    print(f"Training complete in {time.time()-t0:.0f}s")

    print("\nEvaluating on UCSF held-out subset...")
    model.eval()
    Xte_t = torch.from_numpy(Xte).float()
    unet_briers, heat_briers = [], []
    with torch.no_grad():
        for i in range(len(Xte_t)):
            xb = Xte_t[i:i+1].to(DEVICE)
            logits = model(xb)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            unet_briers.append(patient_brier(pred, target_test[i]))
            heat_briers.append(patient_brier(heat_test[i], target_test[i]))

    out = {
        "version": "v97b",
        "experiment": f"Full-volume sub-canonical 3D U-Net at {TARGET_SHAPE} on UCSF (N=80 subset)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device": str(DEVICE),
        "target_shape": list(TARGET_SHAPE),
        "epochs": EPOCHS,
        "seed": SEED,
        "n_train": 60,
        "n_test": 20,
        "n_subset_total": N_SUBSET,
        "n_params_M": round(n_params / 1e6, 2),
        "full_volume_unet_brier_mean": float(np.mean(unet_briers)),
        "full_volume_unet_brier_sd": float(np.std(unet_briers)),
        "heat_brier_mean_full_volume": float(np.mean(heat_briers)),
        "heat_brier_sd_full_volume": float(np.std(heat_briers)),
        "delta_unet_minus_heat": float(np.mean(unet_briers) - np.mean(heat_briers)),
        "unet_beats_heat": bool(np.mean(unet_briers) < np.mean(heat_briers)),
    }
    out_path = RESULTS / "v97b_full_volume_subset.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n  Heat baseline (full-volume):  {out['heat_brier_mean_full_volume']:.4f}")
    print(f"  Full-volume U-Net:            {out['full_volume_unet_brier_mean']:.4f}")
    print(f"  Delta:                        {out['delta_unet_minus_heat']:+.4f}")
    print(f"  U-Net beats heat:             {out['unet_beats_heat']}")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
