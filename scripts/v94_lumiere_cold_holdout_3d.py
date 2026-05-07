"""v94: LUMIERE 3D cold-holdout LOCO using existing cache_3d.

cache_3d/ contains 1018 16×48×48 per-patient .npy files across four cohorts:
  UCSF-POSTOP   N=297 (594 files; b/r per patient)
  MU-Glioma-Post N=151 (302 files)
  RHUH-GBM      N=39  (78 files)
  LUMIERE       N=22  (44 files)

The 'b' suffix is baseline lesion mask; 'r' is recurrence/follow-up label.
This script trains UNETR on the three non-LUMIERE cohorts (UCSF + MU + RHUH;
N=487 patient-level evaluations) and externally evaluates on LUMIERE as a
cold-holdout. LUMIERE is glioma IDH-stratified; this is a stronger out-of-
distribution test than the 4-cohort LOCO because the IDH-mutant subtype is
biologically distinct from IDH-wildtype GBM.

Adds heat-kernel structural-prior baseline computed from M_baseline.

Outputs:
  C:/Users/kamru/Downloads/Nature_project/05_results/v94_lumiere_cold_holdout.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from monai.networks.nets import UNETR
from scipy.ndimage import gaussian_filter
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
EPOCHS = 22
BATCH = 4
SEED = 9401
SIGMA = 2.5
COHORTS_TRAIN = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM"]
COHORT_TEST = "LUMIERE"


def patient_brier(pred, target):
    pred = np.clip(pred, 1e-6, 1 - 1e-6)
    return float(((pred - target) ** 2).mean())


def heat_kernel(mask: np.ndarray, sigma: float = SIGMA) -> np.ndarray:
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    mx = float(h.max())
    return (h / mx).astype(np.float32) if mx > 0 else h.astype(np.float32)


def load_cohort(cohort: str):
    """Load all (mask, target) pairs for a cohort from cache_3d.

    cache_3d files are uint8 arrays with values already in {0, 1} (binary
    lesion / future-lesion masks); cast to float32 without any division.
    """
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    masks, targets = [], []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists():
            continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        masks.append(m)
        targets.append(t)
    if masks:
        return np.stack(masks), np.stack(targets)
    return np.empty((0, 16, 48, 48)), np.empty((0, 16, 48, 48))


def build_inputs(masks: np.ndarray):
    """Compute heat-kernel risk and SDF channels per patient."""
    heats = np.stack([heat_kernel(m) for m in masks])
    # signed-distance field: mask boundary at distance 0
    from scipy.ndimage import distance_transform_edt
    sdfs = []
    for m in masks:
        if m.max() > 0:
            sdf = distance_transform_edt(1 - (m > 0.5)).astype(np.float32)
            sdf = sdf / max(sdf.max(), 1.0)
            sdfs.append(sdf)
        else:
            sdfs.append(np.zeros_like(m, dtype=np.float32))
    sdfs = np.stack(sdfs)
    # 3-channel mask + heat + sdf (no raw MRI in cache_3d)
    return np.stack([masks, heats, sdfs], axis=1), heats


def main():
    print("=" * 78)
    print("v94 LUMIERE COLD-HOLDOUT 3D LOCO")
    print(f"  Train cohorts: {COHORTS_TRAIN}")
    print(f"  Test cohort:   {COHORT_TEST}")
    print("=" * 78)

    train_masks, train_targets = [], []
    cohort_sizes = {}
    for c in COHORTS_TRAIN:
        m, t = load_cohort(c)
        cohort_sizes[c] = len(m)
        if len(m) == 0:
            print(f"  WARNING: cohort {c} has zero examples")
        train_masks.append(m)
        train_targets.append(t)
    test_masks, test_targets = load_cohort(COHORT_TEST)
    cohort_sizes[COHORT_TEST] = len(test_masks)
    print(f"  Cohort sizes: {cohort_sizes}")
    train_masks = np.concatenate(train_masks, axis=0)
    train_targets = np.concatenate(train_targets, axis=0)
    print(f"  Train N={len(train_masks)}; Test N={len(test_masks)}")

    Xtr, _ = build_inputs(train_masks)
    Ytr = train_targets[:, None]
    Xte, heat_test = build_inputs(test_masks)
    Yte = test_targets[:, None]

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    model = UNETR(
        in_channels=3, out_channels=1, img_size=(16, 48, 48),
        feature_size=12, hidden_size=192, mlp_dim=384,
        num_heads=6, dropout_rate=0.1, spatial_dims=3,
    ).to(DEVICE)
    optim = torch.optim.AdamW(model.parameters(), lr=5e-4)
    bce = nn.BCEWithLogitsLoss()

    Xt = torch.from_numpy(Xtr).float()
    Yt = torch.from_numpy(Ytr).float()
    loader = DataLoader(TensorDataset(Xt, Yt), batch_size=BATCH, shuffle=True)

    print(f"\n  Training UNETR for {EPOCHS} epochs...")
    t0 = time.time()
    for epoch in range(EPOCHS):
        model.train()
        ep_loss = 0.0
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            logits = model(xb)
            loss = bce(logits, yb)
            optim.zero_grad(); loss.backward(); optim.step()
            ep_loss += loss.item()
        if (epoch + 1) % 5 == 0:
            print(f"    epoch {epoch+1}/{EPOCHS} loss={ep_loss/len(loader):.4f}  ({time.time()-t0:.0f}s)")

    print(f"  Training complete in {time.time()-t0:.0f}s")

    print(f"\n  Evaluating on LUMIERE cold-holdout (N={len(Xte)})...")
    model.eval()
    Xte_t = torch.from_numpy(Xte).float()
    unetr_briers = []
    heat_briers = []
    mask_briers = []
    with torch.no_grad():
        for i in range(len(Xte_t)):
            xb = Xte_t[i:i+1].to(DEVICE)
            logits = model(xb)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            unetr_briers.append(patient_brier(pred, Yte[i, 0]))
            heat_briers.append(patient_brier(heat_test[i], Yte[i, 0]))
            mask_briers.append(patient_brier(test_masks[i], Yte[i, 0]))

    out = {
        "version": "v94",
        "experiment": "LUMIERE 3D cold-holdout LOCO",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "device": str(DEVICE),
        "epochs": EPOCHS,
        "seed": SEED,
        "train_cohorts": COHORTS_TRAIN,
        "train_n": int(len(train_masks)),
        "test_cohort": COHORT_TEST,
        "test_n": int(len(test_masks)),
        "cohort_sizes": cohort_sizes,
        "unetr_brier_mean": float(np.mean(unetr_briers)),
        "unetr_brier_sd": float(np.std(unetr_briers)),
        "heat_brier_mean": float(np.mean(heat_briers)),
        "heat_brier_sd": float(np.std(heat_briers)),
        "mask_brier_mean": float(np.mean(mask_briers)),
        "delta_unetr_minus_heat": float(np.mean(unetr_briers) - np.mean(heat_briers)),
        "unetr_beats_heat": bool(np.mean(unetr_briers) < np.mean(heat_briers)),
    }

    out_path = RESULTS / "v94_lumiere_cold_holdout.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\n  Heat baseline Brier:  {out['heat_brier_mean']:.4f}")
    print(f"  UNETR cold-holdout:   {out['unetr_brier_mean']:.4f} ± {out['unetr_brier_sd']:.4f}")
    print(f"  Delta:                {out['delta_unetr_minus_heat']:+.4f}")
    print(f"  UNETR beats heat:     {out['unetr_beats_heat']}")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
