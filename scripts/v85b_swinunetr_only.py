"""v85b: re-run SwinUNETR only after fixing the MONAI 1.5+ API change."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from monai.networks.nets import SwinUNETR
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "v78_raw_mri_loco_cache.npz"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EPOCHS = 22
BATCH = 4
SEED = 8501


def patient_brier(pred, target):
    pred = np.clip(pred, 1e-6, 1 - 1e-6)
    return float(((pred - target) ** 2).mean())


def heat_brier_arr(heat, target):
    pred = np.clip(heat, 0, 1)
    return float(((pred - target) ** 2).mean())


def make_swinunetr():
    """Build SwinUNETR with MONAI 1.5+ API (no img_size kwarg)."""
    return SwinUNETR(
        in_channels=7, out_channels=1,
        feature_size=12,
        spatial_dims=3,
        use_checkpoint=False,
    )


def train_swin(cache, held_out):
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    cohorts = cache["cohorts"]
    train_idx = np.where(cohorts != held_out)[0]
    test_idx = np.where(cohorts == held_out)[0]

    raw = cache["raw"]; mask = cache["mask"]; heat = cache["heat"]; sdf = cache["sdf"]
    target = cache["target"]

    inputs_train = np.concatenate([raw[train_idx], mask[train_idx][:, None],
                                    heat[train_idx][:, None], sdf[train_idx][:, None]], axis=1)
    targets_train = target[train_idx][:, None]

    inputs_test = np.concatenate([raw[test_idx], mask[test_idx][:, None],
                                   heat[test_idx][:, None], sdf[test_idx][:, None]], axis=1)
    targets_test = target[test_idx][:, None]
    heat_test = heat[test_idx]

    model = make_swinunetr().to(DEVICE)
    optim = torch.optim.AdamW(model.parameters(), lr=5e-4)
    bce = nn.BCEWithLogitsLoss()

    Xt = torch.from_numpy(inputs_train).float()
    Yt = torch.from_numpy(targets_train).float()
    loader = DataLoader(TensorDataset(Xt, Yt), batch_size=BATCH, shuffle=True)

    for epoch in range(EPOCHS):
        model.train()
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            logits = model(xb)
            loss = bce(logits, yb)
            optim.zero_grad(); loss.backward(); optim.step()

    model.eval()
    Xte = torch.from_numpy(inputs_test).float()
    briers = []
    with torch.no_grad():
        for i in range(len(Xte)):
            xb = Xte[i:i+1].to(DEVICE)
            logits = model(xb)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            briers.append(patient_brier(pred, targets_test[i, 0]))

    heat_briers_test = [heat_brier_arr(heat_test[i], targets_test[i, 0]) for i in range(len(Xte))]
    n_params = sum(p.numel() for p in model.parameters())

    return {
        "held_out": held_out,
        "model": "swinunetr",
        "n_test": len(Xte),
        "n_params_M": round(n_params / 1e6, 2),
        "transformer_brier_mean": float(np.mean(briers)),
        "transformer_brier_sd": float(np.std(briers)),
        "heat_brier_mean": float(np.mean(heat_briers_test)),
        "delta_transformer_minus_heat": float(np.mean(briers) - np.mean(heat_briers_test)),
        "transformer_beats_heat": bool(np.mean(briers) < np.mean(heat_briers_test)),
    }


def main():
    print("=" * 78)
    print("v85b SwinUNETR (fixed MONAI 1.5+ API)")
    print("=" * 78)
    cache = dict(np.load(CACHE, allow_pickle=True))
    cohort_names = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]

    results = []
    for held_out in cohort_names:
        t0 = time.time()
        try:
            r = train_swin(cache, held_out)
            r["elapsed_sec"] = time.time() - t0
            print(f"  {held_out}: swinunetr={r['transformer_brier_mean']:.4f} "
                  f"heat={r['heat_brier_mean']:.4f} delta={r['delta_transformer_minus_heat']:+.4f} "
                  f"beats_heat={r['transformer_beats_heat']} ({r['n_params_M']}M params, {r['elapsed_sec']:.0f}s)",
                  flush=True)
            results.append(r)
        except Exception as e:
            print(f"  {held_out}: FAILED — {type(e).__name__}: {e}", flush=True)
            import traceback; traceback.print_exc()
            results.append({"held_out": held_out, "error": str(e)})

    out = {
        "version": "v85b",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device": str(DEVICE),
        "epochs": EPOCHS,
        "seed": SEED,
        "swinunetr_results": results,
    }
    (RESULTS / "v85b_swinunetr_baselines.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {RESULTS / 'v85b_swinunetr_baselines.json'}")


if __name__ == "__main__":
    main()
