"""v86: Close the three concrete MedIA reviewer gaps.

(1) UNETR with two additional seeds (8502, 8503) at the same 16x48x48 scale as
    seed 8501 to give a 3-seed UNETR estimate.
(2) SwinUNETR with seed 8501 at zero-padded 32x64x64 so the 2**5-divisibility
    constraint is satisfied.
(3) Sanity-check: UNETR seed 8501 at the same padded 32x64x64 to confirm the
    crop-scale change is not what flips ranking direction.

Outputs:
  C:/Users/kamru/Downloads/Nature_project/05_results/v86_extra_seeds_padded.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from monai.networks.nets import UNETR, SwinUNETR
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "v78_raw_mri_loco_cache.npz"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EPOCHS = 22
BATCH = 4
COHORT_NAMES = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]


def patient_brier(pred, target):
    pred = np.clip(pred, 1e-6, 1 - 1e-6)
    return float(((pred - target) ** 2).mean())


def heat_brier_arr(heat, target):
    pred = np.clip(heat, 0, 1)
    return float(((pred - target) ** 2).mean())


def pad_to(arr, target_shape):
    """Symmetric zero-pad spatial dimensions of arr to target_shape.

    arr can have shape (N, C, D, H, W) or (N, D, H, W); target_shape is the
    target spatial shape (D, H, W).
    """
    if arr.ndim == 4:
        d_cur, h_cur, w_cur = arr.shape[1:]
    else:
        d_cur, h_cur, w_cur = arr.shape[2:]
    d_t, h_t, w_t = target_shape
    pad_d = (d_t - d_cur) // 2
    pad_h = (h_t - h_cur) // 2
    pad_w = (w_t - w_cur) // 2
    if arr.ndim == 4:
        out = np.zeros((arr.shape[0], d_t, h_t, w_t), dtype=arr.dtype)
        out[:, pad_d:pad_d + d_cur, pad_h:pad_h + h_cur, pad_w:pad_w + w_cur] = arr
    else:
        out = np.zeros((arr.shape[0], arr.shape[1], d_t, h_t, w_t), dtype=arr.dtype)
        out[:, :, pad_d:pad_d + d_cur, pad_h:pad_h + h_cur, pad_w:pad_w + w_cur] = arr
    return out


def build_inputs(cache, idx, image_size=(16, 48, 48)):
    raw = cache["raw"][idx]
    mask = cache["mask"][idx][:, None]
    heat = cache["heat"][idx][:, None]
    sdf = cache["sdf"][idx][:, None]
    target = cache["target"][idx][:, None]
    if image_size != (16, 48, 48):
        raw = pad_to(raw, image_size)
        mask = pad_to(mask[:, 0], image_size)[:, None]
        heat = pad_to(heat[:, 0], image_size)[:, None]
        sdf = pad_to(sdf[:, 0], image_size)[:, None]
        target = pad_to(target[:, 0], image_size)[:, None]
    return (
        np.concatenate([raw, mask, heat, sdf], axis=1),
        target,
        cache["heat"][idx],
    )


def train_one(cache, held_out, seed, model_name, image_size):
    torch.manual_seed(seed)
    np.random.seed(seed)

    cohorts = cache["cohorts"]
    train_idx = np.where(cohorts != held_out)[0]
    test_idx = np.where(cohorts == held_out)[0]

    Xtr, Ytr, _ = build_inputs(cache, train_idx, image_size)
    Xte_arr, Yte_arr, heat_test_orig = build_inputs(cache, test_idx, image_size)
    target_test_orig = cache["target"][test_idx]

    if model_name == "unetr":
        model = UNETR(
            in_channels=7, out_channels=1,
            img_size=image_size,
            feature_size=12,
            hidden_size=192,
            mlp_dim=384,
            num_heads=6,
            dropout_rate=0.1,
            spatial_dims=3,
        ).to(DEVICE)
    elif model_name == "swinunetr":
        model = SwinUNETR(
            in_channels=7, out_channels=1,
            feature_size=12,
            spatial_dims=3,
            use_checkpoint=False,
        ).to(DEVICE)
    else:
        raise ValueError(model_name)

    optim = torch.optim.AdamW(model.parameters(), lr=5e-4)
    bce = nn.BCEWithLogitsLoss()

    Xt = torch.from_numpy(Xtr).float()
    Yt = torch.from_numpy(Ytr).float()
    loader = DataLoader(TensorDataset(Xt, Yt), batch_size=BATCH, shuffle=True)

    for _ in range(EPOCHS):
        model.train()
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            logits = model(xb)
            loss = bce(logits, yb)
            optim.zero_grad(); loss.backward(); optim.step()

    model.eval()
    Xte = torch.from_numpy(Xte_arr).float()
    briers = []
    with torch.no_grad():
        for i in range(len(Xte)):
            xb = Xte[i:i + 1].to(DEVICE)
            logits = model(xb)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            briers.append(patient_brier(pred, Yte_arr[i, 0]))

    heat_briers_test = [
        heat_brier_arr(heat_test_orig[i], target_test_orig[i])
        for i in range(len(test_idx))
    ]
    n_params = sum(p.numel() for p in model.parameters())

    return {
        "held_out": held_out,
        "model": model_name,
        "seed": seed,
        "image_size": list(image_size),
        "n_test": len(Xte),
        "n_params_M": round(n_params / 1e6, 2),
        "model_brier_mean": float(np.mean(briers)),
        "model_brier_sd": float(np.std(briers)),
        "heat_brier_mean": float(np.mean(heat_briers_test)),
        "delta_model_minus_heat": float(np.mean(briers) - np.mean(heat_briers_test)),
        "model_beats_heat": bool(np.mean(briers) < np.mean(heat_briers_test)),
    }


def main():
    print("=" * 78)
    print("v86 EXTRA SEEDS (UNETR 8502/8503 @ 16x48x48) + PADDED SwinUNETR @ 32x64x64")
    print("=" * 78)
    cache = dict(np.load(CACHE, allow_pickle=True))

    runs = []
    # (1) UNETR 16x48x48 with seeds 8502 and 8503 (3-seed total with existing 8501)
    for seed in [8502, 8503]:
        for held_out in COHORT_NAMES:
            t0 = time.time()
            try:
                r = train_one(cache, held_out, seed, "unetr", (16, 48, 48))
                r["elapsed_sec"] = time.time() - t0
                print(f"  UNETR seed={seed} {held_out}: brier={r['model_brier_mean']:.4f} "
                      f"heat={r['heat_brier_mean']:.4f} delta={r['delta_model_minus_heat']:+.4f} "
                      f"beats_heat={r['model_beats_heat']} ({r['elapsed_sec']:.0f}s)", flush=True)
                runs.append(r)
            except Exception as e:
                print(f"  UNETR seed={seed} {held_out}: FAILED — {type(e).__name__}: {e}", flush=True)
                runs.append({"held_out": held_out, "model": "unetr", "seed": seed, "error": str(e)})

    # (2) SwinUNETR padded 32x64x64 with seed 8501
    for held_out in COHORT_NAMES:
        t0 = time.time()
        try:
            r = train_one(cache, held_out, 8501, "swinunetr", (32, 64, 64))
            r["elapsed_sec"] = time.time() - t0
            print(f"  SwinUNETR padded 32x64x64 {held_out}: brier={r['model_brier_mean']:.4f} "
                  f"heat={r['heat_brier_mean']:.4f} delta={r['delta_model_minus_heat']:+.4f} "
                  f"beats_heat={r['model_beats_heat']} ({r['elapsed_sec']:.0f}s)", flush=True)
            runs.append(r)
        except Exception as e:
            print(f"  SwinUNETR padded {held_out}: FAILED — {type(e).__name__}: {e}", flush=True)
            runs.append({"held_out": held_out, "model": "swinunetr",
                         "image_size": [32, 64, 64], "seed": 8501, "error": str(e)})

    # (3) UNETR padded 32x64x64 with seed 8501 — sanity check that crop-scale
    #     change does not by itself flip the ranking direction
    for held_out in COHORT_NAMES:
        t0 = time.time()
        try:
            r = train_one(cache, held_out, 8501, "unetr", (32, 64, 64))
            r["elapsed_sec"] = time.time() - t0
            print(f"  UNETR padded 32x64x64 {held_out}: brier={r['model_brier_mean']:.4f} "
                  f"heat={r['heat_brier_mean']:.4f} delta={r['delta_model_minus_heat']:+.4f} "
                  f"beats_heat={r['model_beats_heat']} ({r['elapsed_sec']:.0f}s)", flush=True)
            runs.append(r)
        except Exception as e:
            print(f"  UNETR padded {held_out}: FAILED — {type(e).__name__}: {e}", flush=True)
            runs.append({"held_out": held_out, "model": "unetr",
                         "image_size": [32, 64, 64], "seed": 8501, "error": str(e)})

    out = {
        "version": "v86",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device": str(DEVICE),
        "epochs": EPOCHS,
        "results": runs,
    }
    out_path = RESULTS / "v86_extra_seeds_padded.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
