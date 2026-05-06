"""v77_ucsf_raw_mri_baseline.py

Empirical raw-MRI stress test for the NMI paper.

This script reads the UCSF postoperative glioma zip directly, builds small
3D crops around the baseline tumour, and trains lightweight 3D U-Nets under
cross-validation. It is intentionally framed as a stress test, not as a final
nnU-Net replacement: it asks whether a raw-image model with access to T1/T1CE/
T2/FLAIR can erase the heat-kernel advantage on the surveillance-dominant UCSF
cohort.

Output:
  05_results/v77_ucsf_raw_mri_cache.npz
  05_results/v77_ucsf_raw_mri_baseline.json
"""

from __future__ import annotations

import io
import argparse
import json
import math
import tempfile
import time
import zipfile
import os
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


ROOT = Path(__file__).resolve().parents[1]
DATA = Path(r"C:\Users\kamru\Downloads\Datasets")
RESULTS = ROOT / "05_results"
UCSF_ZIP = DATA / "UCSF_POSTOP_GLIOMA_DATASET_FINAL_v1.0.zip"
CACHE = RESULTS / "v77_ucsf_raw_mri_cache.npz"
OUT = RESULTS / "v77_ucsf_raw_mri_baseline.json"
MASTER_INDEX = RESULTS / "master_neurooncology_dataset_index.csv"

CROP = (16, 48, 48)  # D, H, W after transpose from native x,y,z
SIGMA = 2.5
EPOCHS = 28
BATCH = 10
LR = 1e-3
SEED = 7701
FOLDS = 3
BOOT = 5000

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_nifti_from_zip(zf: zipfile.ZipFile, name: str) -> np.ndarray:
    """Load a gzipped NIfTI member from a zip archive."""
    payload = zf.read(name)
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as tmp:
            tmp.write(payload)
            tmp_name = tmp.name
        return np.asanyarray(nib.load(tmp_name).dataobj).astype(np.float32)
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def _norm(vol: np.ndarray) -> np.ndarray:
    finite = np.isfinite(vol)
    positive = finite & (vol != 0)
    if not positive.any():
        return np.zeros_like(vol, dtype=np.float32)
    lo, hi = np.percentile(vol[positive], [1, 99])
    if hi <= lo:
        hi = float(np.max(vol[positive])) + 1e-6
        lo = float(np.min(vol[positive]))
    out = np.clip((vol - lo) / (hi - lo + 1e-6), 0, 1)
    out[~finite] = 0
    return out.astype(np.float32)


def _centroid(mask: np.ndarray) -> np.ndarray:
    pts = np.argwhere(mask > 0)
    if len(pts) == 0:
        return np.array(mask.shape, dtype=float) / 2
    return pts.mean(axis=0)


def _crop_native(vol: np.ndarray, centre_xyz: np.ndarray) -> np.ndarray:
    """Crop native (X,Y,Z) volume and return (D,H,W)."""
    d, h, w = CROP
    sx, sy, sz = vol.shape
    cx, cy, cz = [int(round(v)) for v in centre_xyz]
    x0 = max(0, min(cx - w // 2, sx - w))
    y0 = max(0, min(cy - h // 2, sy - h))
    z0 = max(0, min(cz - d // 2, sz - d))
    crop = vol[x0:x0 + w, y0:y0 + h, z0:z0 + d]
    if crop.shape != (w, h, d):
        padded = np.zeros((w, h, d), dtype=vol.dtype)
        padded[:crop.shape[0], :crop.shape[1], :crop.shape[2]] = crop
        crop = padded
    return np.transpose(crop, (2, 1, 0)).astype(np.float32)


def _heat(mask: np.ndarray) -> np.ndarray:
    h = gaussian_filter(mask.astype(np.float32), sigma=SIGMA)
    mx = float(h.max())
    return (h / mx).astype(np.float32) if mx > 0 else h.astype(np.float32)


def _sdf(mask: np.ndarray) -> np.ndarray:
    m = mask > 0
    if not m.any():
        return np.zeros_like(mask, dtype=np.float32)
    inside = distance_transform_edt(m).astype(np.float32)
    outside = distance_transform_edt(~m).astype(np.float32)
    s = inside - outside
    scale = max(abs(float(s.min())), abs(float(s.max())), 1e-6)
    return (s / scale).astype(np.float32)


def build_cache() -> dict[str, np.ndarray]:
    if CACHE.exists():
        loaded = np.load(CACHE, allow_pickle=True)
        return {k: loaded[k] for k in loaded.files}

    if not UCSF_ZIP.exists():
        raise FileNotFoundError(f"Missing UCSF zip: {UCSF_ZIP}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    records = []
    with zipfile.ZipFile(UCSF_ZIP) as zf:
        folders = sorted({
            n.split("/", 1)[0]
            for n in zf.namelist()
            if "/" in n and n.endswith("_time1_t1ce.nii.gz")
        })
        for idx, pid in enumerate(folders, 1):
            required = [
                f"{pid}/{pid}_time1_t1ce.nii.gz",
                f"{pid}/{pid}_time1_flair.nii.gz",
                f"{pid}/{pid}_time1_t2.nii.gz",
                f"{pid}/{pid}_time1_t1.nii.gz",
                f"{pid}/{pid}_time1_seg.nii.gz",
                f"{pid}/{pid}_time2_seg.nii.gz",
            ]
            if any(r not in zf.namelist() for r in required):
                continue
            try:
                t1ce = _norm(_load_nifti_from_zip(zf, required[0]))
                flair = _norm(_load_nifti_from_zip(zf, required[1]))
                t2 = _norm(_load_nifti_from_zip(zf, required[2]))
                t1 = _norm(_load_nifti_from_zip(zf, required[3]))
                seg1 = (_load_nifti_from_zip(zf, required[4]) > 0).astype(np.float32)
                seg2 = (_load_nifti_from_zip(zf, required[5]) > 0).astype(np.float32)
            except Exception as exc:
                print(f"Skipping {pid}: {exc}")
                continue
            centre = _centroid(seg1)
            mask = _crop_native(seg1, centre)
            target = _crop_native(seg2, centre)
            raw = np.stack([
                _crop_native(t1ce, centre),
                _crop_native(flair, centre),
                _crop_native(t2, centre),
                _crop_native(t1, centre),
            ], axis=0)
            heat = _heat(mask)
            sdf = _sdf(mask)
            change = abs(float(target.sum()) - float(mask.sum())) / (float(mask.sum()) + 1e-6)
            records.append({
                "pid": pid,
                "raw": raw.astype(np.float32),
                "mask": mask.astype(np.float32),
                "heat": heat.astype(np.float32),
                "sdf": sdf.astype(np.float32),
                "target": target.astype(np.float32),
                "stable": 1 if change < 0.25 else 0,
                "base_vox": float(mask.sum()),
                "target_vox": float(target.sum()),
            })
            if idx % 25 == 0:
                print(f"Cached {idx}/{len(folders)} UCSF cases")

    if not records:
        raise RuntimeError("No UCSF records could be built")

    arrays = {
        "pids": np.array([r["pid"] for r in records]),
        "raw": np.stack([r["raw"] for r in records]),
        "mask": np.stack([r["mask"] for r in records]),
        "heat": np.stack([r["heat"] for r in records]),
        "sdf": np.stack([r["sdf"] for r in records]),
        "target": np.stack([r["target"] for r in records]),
        "stable": np.array([r["stable"] for r in records], dtype=np.int64),
        "base_vox": np.array([r["base_vox"] for r in records], dtype=np.float32),
        "target_vox": np.array([r["target_vox"] for r in records], dtype=np.float32),
    }
    np.savez_compressed(CACHE, **arrays)
    return arrays


def apply_limit(data: dict[str, np.ndarray], limit: int | None) -> dict[str, np.ndarray]:
    if limit is None or limit <= 0:
        return data
    n = min(limit, len(data["raw"]))
    return {k: v[:n] if hasattr(v, "__len__") and len(v) == len(data["raw"]) else v for k, v in data.items()}


def align_to_master_index(data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Use the locked UCSF cohort and endpoint labels from the project index."""
    if not MASTER_INDEX.exists():
        return data
    df = pd.read_csv(MASTER_INDEX)
    df = df[df["cohort"].astype(str).eq("UCSF-POSTOP")].copy()
    if df.empty:
        return data
    df["pid_clean"] = df["pid"].astype(str).str.split(":").str[-1]
    keep_order = [pid for pid in df["pid_clean"].tolist() if pid in set(data["pids"].astype(str))]
    if not keep_order:
        return data
    pos = {pid: i for i, pid in enumerate(data["pids"].astype(str))}
    idx = np.array([pos[pid] for pid in keep_order], dtype=int)
    stable_map = dict(zip(df["pid_clean"], df["endpoint_class"].astype(str).eq("stable").astype(int)))
    out = {k: v[idx] if hasattr(v, "__len__") and len(v) == len(data["raw"]) else v for k, v in data.items()}
    out["stable"] = np.array([stable_map[pid] for pid in keep_order], dtype=np.int64)
    out["master_index_aligned"] = np.array([1], dtype=np.int64)
    return out


class CropDataset(Dataset):
    def __init__(self, x: np.ndarray, y: np.ndarray, augment: bool):
        self.x = x
        self.y = y
        self.augment = augment

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, idx: int):
        x = self.x[idx].copy()
        y = self.y[idx].copy()
        if self.augment:
            for ax in [1, 2, 3]:
                if np.random.rand() < 0.5:
                    x = np.flip(x, axis=ax).copy()
                    y = np.flip(y, axis=ax).copy()
            if np.random.rand() < 0.5:
                x[:4] = np.clip(x[:4] * np.random.uniform(0.9, 1.1) + np.random.uniform(-0.03, 0.03), 0, 1)
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


class DoubleConv(nn.Module):
    def __init__(self, ic: int, oc: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv3d(ic, oc, 3, padding=1, bias=False),
            nn.BatchNorm3d(oc),
            nn.ReLU(inplace=True),
            nn.Conv3d(oc, oc, 3, padding=1, bias=False),
            nn.BatchNorm3d(oc),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.net(x)


class SmallUNet3D(nn.Module):
    def __init__(self, in_c: int, base: int = 16):
        super().__init__()
        b = base
        self.e1 = DoubleConv(in_c, b)
        self.p1 = nn.MaxPool3d(2)
        self.e2 = DoubleConv(b, b * 2)
        self.p2 = nn.MaxPool3d(2)
        self.e3 = DoubleConv(b * 2, b * 4)
        self.p3 = nn.MaxPool3d(2)
        self.bn = DoubleConv(b * 4, b * 8)
        self.u3 = nn.ConvTranspose3d(b * 8, b * 4, 2, stride=2)
        self.d3 = DoubleConv(b * 8, b * 4)
        self.u2 = nn.ConvTranspose3d(b * 4, b * 2, 2, stride=2)
        self.d2 = DoubleConv(b * 4, b * 2)
        self.u1 = nn.ConvTranspose3d(b * 2, b, 2, stride=2)
        self.d1 = DoubleConv(b * 2, b)
        self.out = nn.Conv3d(b, 1, 1)

    def forward(self, x):
        e1 = self.e1(x)
        e2 = self.e2(self.p1(e1))
        e3 = self.e3(self.p2(e2))
        bn = self.bn(self.p3(e3))
        d3 = self.d3(torch.cat([self.u3(bn), e3], dim=1))
        d2 = self.d2(torch.cat([self.u2(d3), e2], dim=1))
        d1 = self.d1(torch.cat([self.u1(d2), e1], dim=1))
        return torch.sigmoid(self.out(d1))


def combo_loss(pred, target):
    bce = nn.functional.binary_cross_entropy(pred, target)
    inter = (pred * target).sum(dim=(1, 2, 3, 4))
    denom = pred.sum(dim=(1, 2, 3, 4)) + target.sum(dim=(1, 2, 3, 4))
    dice = 1 - ((2 * inter + 1e-5) / (denom + 1e-5))
    return 0.5 * bce + 0.5 * dice.mean()


def eval_arrays(preds: np.ndarray, y: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    briers, dices, aucs, eces = [], [], [], []
    for p, t, m in zip(preds, y, mask):
        roi = binary_dilation(m > 0, iterations=6)
        if not roi.any():
            roi = np.ones_like(m, dtype=bool)
        pv = p[roi].ravel()
        tv = t[roi].ravel()
        briers.append(float(np.mean((pv - tv) ** 2)))
        hard = p > 0.5
        inter = float(np.logical_and(hard, t > 0).sum())
        denom = float(hard.sum() + (t > 0).sum())
        dices.append(float((2 * inter + 1e-5) / (denom + 1e-5)))
        try:
            aucs.append(float(roc_auc_score(tv.astype(np.uint8), pv)))
        except Exception:
            aucs.append(float("nan"))
        bins = np.linspace(0, 1, 11)
        ece = 0.0
        for lo, hi in zip(bins[:-1], bins[1:]):
            sel = (pv >= lo) & (pv < hi)
            if sel.any():
                ece += float(sel.mean()) * abs(float(tv[sel].mean()) - float(pv[sel].mean()))
        eces.append(ece)
    return {
        "brier_mean": float(np.mean(briers)),
        "brier_sd": float(np.std(briers, ddof=1)),
        "dice_mean": float(np.mean(dices)),
        "auroc_mean": float(np.nanmean(aucs)),
        "ece_mean": float(np.mean(eces)),
    }


def per_case_brier(preds: np.ndarray, y: np.ndarray, mask: np.ndarray) -> np.ndarray:
    vals = []
    for p, t, m in zip(preds, y, mask):
        roi = binary_dilation(m > 0, iterations=6)
        if not roi.any():
            roi = np.ones_like(m, dtype=bool)
        vals.append(float(np.mean((p[roi].ravel() - t[roi].ravel()) ** 2)))
    return np.array(vals, dtype=np.float32)


def paired_bootstrap(delta: np.ndarray) -> dict[str, float]:
    rng = np.random.default_rng(SEED)
    delta = np.asarray(delta, dtype=float)
    draws = rng.choice(delta, size=(BOOT, len(delta)), replace=True).mean(axis=1)
    return {
        "mean": float(delta.mean()),
        "ci95_lo": float(np.percentile(draws, 2.5)),
        "ci95_hi": float(np.percentile(draws, 97.5)),
        "p_delta_lt_0": float(np.mean(draws < 0)),
        "n": int(len(delta)),
    }


def train_fold(x_train, y_train, x_test, y_test, in_c: int, fold: int, variant: str):
    torch.manual_seed(SEED + fold)
    np.random.seed(SEED + fold)
    model = SmallUNet3D(in_c=in_c).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    loader = DataLoader(CropDataset(x_train, y_train, augment=True), batch_size=BATCH, shuffle=True, num_workers=0)
    best_state, best_loss = None, math.inf
    for epoch in range(1, EPOCHS + 1):
        model.train()
        losses = []
        for xb, yb in loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            opt.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = combo_loss(pred, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            losses.append(float(loss.item()))
        sched.step()
        mean_loss = float(np.mean(losses))
        if mean_loss < best_loss:
            best_loss = mean_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if epoch in {1, 10, 20, EPOCHS}:
            print(f"{variant} fold {fold} epoch {epoch}/{EPOCHS}: loss={mean_loss:.4f}")
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    preds = []
    with torch.no_grad():
        for xb, _ in DataLoader(CropDataset(x_test, y_test, augment=False), batch_size=BATCH, shuffle=False):
            preds.append(model(xb.to(DEVICE)).cpu().numpy())
    return np.concatenate(preds, axis=0)[:, 0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UCSF raw-MRI internal CV stress test")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--folds", type=int, default=FOLDS)
    parser.add_argument("--batch", type=int, default=BATCH)
    parser.add_argument("--limit", type=int, default=0, help="Optional first-N case limit for smoke tests")
    parser.add_argument("--rebuild-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    global EPOCHS, FOLDS, BATCH
    args = parse_args()
    EPOCHS = args.epochs
    FOLDS = args.folds
    BATCH = args.batch
    if args.rebuild_cache and CACHE.exists():
        CACHE.unlink()
    start = time.time()
    print(f"Device: {DEVICE}")
    if DEVICE.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    data = apply_limit(align_to_master_index(build_cache()), args.limit or None)

    raw = data["raw"]
    mask = data["mask"]
    heat = data["heat"]
    sdf = data["sdf"]
    y = data["target"][:, None]
    stable = data["stable"]

    variants = {
        "raw4": raw,
        "raw4_mask": np.concatenate([raw, mask[:, None]], axis=1),
        "raw4_mask_heat_sdf": np.concatenate([raw, mask[:, None], heat[:, None], sdf[:, None]], axis=1),
    }

    kf = KFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    results = {}
    folds = list(kf.split(raw))
    heat_fold_metrics = []
    for fold, (_, test_idx) in enumerate(folds):
        heat_fold_metrics.append(eval_arrays(heat[test_idx], y[test_idx, 0], mask[test_idx]))
    results["heat_prior_no_training"] = {
        "folds": heat_fold_metrics,
        "brier_mean": float(np.mean([f["brier_mean"] for f in heat_fold_metrics])),
        "ece_mean": float(np.mean([f["ece_mean"] for f in heat_fold_metrics])),
        "auroc_mean": float(np.mean([f["auroc_mean"] for f in heat_fold_metrics])),
    }
    heat_oof = np.zeros_like(heat, dtype=np.float32)
    for _, test_idx in folds:
        heat_oof[test_idx] = heat[test_idx]
    heat_case_brier = per_case_brier(heat_oof, y[:, 0], mask)
    case_brier = {"heat_prior_no_training": heat_case_brier}

    for variant, x in variants.items():
        fold_metrics = []
        oof = np.zeros_like(mask, dtype=np.float32)
        for fold, (train_idx, test_idx) in enumerate(folds):
            pred = train_fold(
                x[train_idx], y[train_idx],
                x[test_idx], y[test_idx],
                in_c=x.shape[1], fold=fold, variant=variant,
            )
            oof[test_idx] = pred
            fold_metrics.append(eval_arrays(pred, y[test_idx, 0], mask[test_idx]))
        case_brier[variant] = per_case_brier(oof, y[:, 0], mask)
        results[variant] = {
            "folds": fold_metrics,
            "brier_mean": float(np.mean([f["brier_mean"] for f in fold_metrics])),
            "brier_sd_across_folds": float(np.std([f["brier_mean"] for f in fold_metrics], ddof=1)),
            "ece_mean": float(np.mean([f["ece_mean"] for f in fold_metrics])),
            "auroc_mean": float(np.mean([f["auroc_mean"] for f in fold_metrics])),
            "dice_mean": float(np.mean([f["dice_mean"] for f in fold_metrics])),
        }

    best_model = min([k for k in results if k != "heat_prior_no_training"], key=lambda k: results[k]["brier_mean"])
    paired = {
        k: paired_bootstrap(case_brier[k] - heat_case_brier)
        for k in results
        if k != "heat_prior_no_training"
    }
    out = {
        "version": "v77_ucsf_raw_mri_baseline",
        "status": "EMPIRICAL_RAW_MRI_STRESS_TEST",
        "date": time.strftime("%Y-%m-%d"),
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if DEVICE.type == "cuda" else None,
        "n_cases": int(len(raw)),
        "n_stable": int(stable.sum()),
        "pi_stable": float(stable.mean()),
        "master_index_aligned": bool(int(data.get("master_index_aligned", np.array([0]))[0])),
        "crop_shape_DHW": list(CROP),
        "folds": FOLDS,
        "epochs": EPOCHS,
        "batch_size": BATCH,
        "case_limit": int(args.limit) if args.limit else None,
        "variants": results,
        "best_raw_model": best_model,
        "heat_brier": results["heat_prior_no_training"]["brier_mean"],
        "best_raw_brier": results[best_model]["brier_mean"],
        "delta_raw_minus_heat_brier": float(results[best_model]["brier_mean"] - results["heat_prior_no_training"]["brier_mean"]),
        "paired_bootstrap_delta_raw_minus_heat": paired,
        "interpretation": (
            "Negative delta means the best raw-MRI model beat the heat prior on internal UCSF CV; "
            "positive delta means heat remained stronger despite raw MRI access. This is internal "
            "cross-validation, not leave-cohort-out external raw-image nnU-Net evidence."
        ),
        "runtime_s": round(time.time() - start, 2),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({
        "n_cases": out["n_cases"],
        "pi_stable": out["pi_stable"],
        "heat_brier": out["heat_brier"],
        "best_raw_model": out["best_raw_model"],
        "best_raw_brier": out["best_raw_brier"],
        "delta_raw_minus_heat_brier": out["delta_raw_minus_heat_brier"],
        "runtime_s": out["runtime_s"],
    }, indent=2))


if __name__ == "__main__":
    main()
