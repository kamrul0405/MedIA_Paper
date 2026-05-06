"""v78_raw_mri_loco.py

Raw-MRI external transportability stress test for the NMI paper.

This script addresses the strongest post-v77 reviewer attack: UCSF raw MRI is
available and an internal raw+mask model can beat the heat prior, so the paper
must test whether raw-image access removes the endpoint-regime ranking reversal
under external leave-one-cohort-out (LOCO) transfer.

Inputs:
  - UCSF cache from v77 (`05_results/v77_ucsf_raw_mri_cache.npz`)
  - MU-Glioma-Post local NIfTI files
  - RHUH-GBM local NIfTI files
  - `05_results/master_neurooncology_dataset_index.csv`

Outputs:
  - `05_results/v78_raw_mri_loco_cache.npz`
  - `05_results/v78_raw_mri_loco.json`

The experiment is deliberately framed as a stress test. It is not a claim that
this lightweight cropped U-Net is a final nnU-Net replacement.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
import time
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
from scipy.ndimage import binary_dilation, distance_transform_edt, gaussian_filter
from sklearn.metrics import roc_auc_score

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset


ROOT = Path(__file__).resolve().parents[1]
DATA = Path(r"C:\Users\kamru\Downloads\Datasets")
RESULTS = ROOT / "05_results"
MASTER_INDEX = RESULTS / "master_neurooncology_dataset_index.csv"

UCSF_ZIP = DATA / "UCSF_POSTOP_GLIOMA_DATASET_FINAL_v1.0.zip"
UCSF_CACHE = RESULTS / "v77_ucsf_raw_mri_cache.npz"
MU_ROOT = DATA / "PKG - MU-Glioma-Post" / "MU-Glioma-Post"
RHUH_ROOT = DATA / "PKG - RHUH-GBM-nii-v1" / "RHUH-GBM_nii_v1"
UCSD_ROOT = DATA / "PKG - UCSD-PTGBM-v1" / "UCSD-PTGBM"

CACHE = RESULTS / "v78_raw_mri_loco_cache.npz"
OUT = RESULTS / "v78_raw_mri_loco.json"

CROP = (16, 48, 48)  # D, H, W
SIGMA = 2.5
SEED = 7801
BOOT = 5000
DEFAULT_EPOCHS = 24
DEFAULT_BATCH = 10
LR = 1e-3

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_nifti(path: Path) -> np.ndarray:
    return np.asanyarray(nib.load(str(path)).dataobj).astype(np.float32)


def _load_nifti_from_zip(zf: zipfile.ZipFile, name: str) -> np.ndarray:
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
        lo = float(np.min(vol[positive]))
        hi = float(np.max(vol[positive])) + 1e-6
    out = np.clip((vol - lo) / (hi - lo + 1e-6), 0, 1)
    out[~finite] = 0
    return out.astype(np.float32)


def _centroid(mask: np.ndarray) -> np.ndarray:
    pts = np.argwhere(mask > 0)
    if len(pts) == 0:
        return np.array(mask.shape, dtype=float) / 2
    return pts.mean(axis=0)


def _crop_native(vol: np.ndarray, centre_xyz: np.ndarray) -> np.ndarray:
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


def _timepoint_key(name: str) -> int:
    m = re.search(r"(\d+)$", name)
    return int(m.group(1)) if m else 0


def _master_labels() -> pd.DataFrame:
    df = pd.read_csv(MASTER_INDEX)
    df = df[df["cohort"].isin(["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"])].copy()
    df["pid_clean"] = df["pid"].astype(str).str.split(":").str[-1]
    df["stable01"] = df["endpoint_class"].astype(str).eq("stable").astype(int)
    return df


def _add_record(records: list[dict], cohort: str, pid: str, raw: np.ndarray, mask: np.ndarray, target: np.ndarray) -> None:
    records.append({
        "cohort": cohort,
        "pid": pid,
        "raw": raw.astype(np.float32),
        "mask": mask.astype(np.float32),
        "heat": _heat(mask).astype(np.float32),
        "sdf": _sdf(mask).astype(np.float32),
        "target": target.astype(np.float32),
        "base_vox": float(mask.sum()),
        "target_vox": float(target.sum()),
    })


def _build_ucsf(records: list[dict], label_df: pd.DataFrame) -> None:
    available = set(label_df[label_df["cohort"].eq("UCSF-POSTOP")]["pid_clean"].astype(str))
    if UCSF_CACHE.exists():
        z = np.load(UCSF_CACHE, allow_pickle=True)
        pids = z["pids"].astype(str)
        for i, pid in enumerate(pids):
            if pid not in available:
                continue
            _add_record(
                records,
                "UCSF-POSTOP",
                pid,
                z["raw"][i],
                z["mask"][i],
                z["target"][i],
            )
        return

    if not UCSF_ZIP.exists():
        raise FileNotFoundError(f"Missing UCSF zip/cache: {UCSF_ZIP}")
    with zipfile.ZipFile(UCSF_ZIP) as zf:
        folders = sorted({
            n.split("/", 1)[0]
            for n in zf.namelist()
            if "/" in n and n.endswith("_time1_t1ce.nii.gz")
        })
        for pid in folders:
            if pid not in available:
                continue
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
            t1ce = _norm(_load_nifti_from_zip(zf, required[0]))
            flair = _norm(_load_nifti_from_zip(zf, required[1]))
            t2 = _norm(_load_nifti_from_zip(zf, required[2]))
            t1 = _norm(_load_nifti_from_zip(zf, required[3]))
            seg1 = (_load_nifti_from_zip(zf, required[4]) > 0).astype(np.float32)
            seg2 = (_load_nifti_from_zip(zf, required[5]) > 0).astype(np.float32)
            centre = _centroid(seg1)
            raw = np.stack([
                _crop_native(t1ce, centre),
                _crop_native(flair, centre),
                _crop_native(t2, centre),
                _crop_native(t1, centre),
            ], axis=0)
            _add_record(records, "UCSF-POSTOP", pid, raw, _crop_native(seg1, centre), _crop_native(seg2, centre))


def _build_mu(records: list[dict], label_df: pd.DataFrame) -> None:
    available = set(label_df[label_df["cohort"].eq("MU-Glioma-Post")]["pid_clean"].astype(str))
    if not MU_ROOT.exists():
        return
    for pdir in sorted(MU_ROOT.iterdir()):
        if not pdir.is_dir() or pdir.name not in available:
            continue
        tps = sorted([d for d in pdir.iterdir() if d.is_dir()], key=lambda p: _timepoint_key(p.name))
        if len(tps) < 2:
            continue
        btp, rtp = tps[0], tps[-1]
        pid = pdir.name
        paths = {
            "t1ce": btp / f"{pid}_{btp.name}_brain_t1c.nii.gz",
            "flair": btp / f"{pid}_{btp.name}_brain_t2f.nii.gz",
            "t2": btp / f"{pid}_{btp.name}_brain_t2w.nii.gz",
            "t1": btp / f"{pid}_{btp.name}_brain_t1n.nii.gz",
            "seg1": btp / f"{pid}_{btp.name}_tumorMask.nii.gz",
            "seg2": rtp / f"{pid}_{rtp.name}_tumorMask.nii.gz",
        }
        if any(not p.exists() for p in paths.values()):
            continue
        try:
            seg1 = (_load_nifti(paths["seg1"]) > 0).astype(np.float32)
            seg2 = (_load_nifti(paths["seg2"]) > 0).astype(np.float32)
            centre = _centroid(seg1)
            raw = np.stack([
                _crop_native(_norm(_load_nifti(paths["t1ce"])), centre),
                _crop_native(_norm(_load_nifti(paths["flair"])), centre),
                _crop_native(_norm(_load_nifti(paths["t2"])), centre),
                _crop_native(_norm(_load_nifti(paths["t1"])), centre),
            ], axis=0)
            _add_record(records, "MU-Glioma-Post", pid, raw, _crop_native(seg1, centre), _crop_native(seg2, centre))
        except Exception as exc:
            print(f"Skipping MU {pid}: {exc}")


def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _build_rhuh(records: list[dict], label_df: pd.DataFrame) -> None:
    available = set(label_df[label_df["cohort"].eq("RHUH-GBM")]["pid_clean"].astype(str))
    if not RHUH_ROOT.exists():
        return
    for pdir in sorted(RHUH_ROOT.iterdir()):
        if not pdir.is_dir() or pdir.name not in available:
            continue
        tps = sorted([d for d in pdir.iterdir() if d.is_dir()], key=lambda p: _timepoint_key(p.name))
        if len(tps) < 2:
            continue
        btp, rtp = tps[0], tps[-1]
        pid = pdir.name
        paths = {
            "t1ce": btp / f"{pid}_{btp.name}_t1ce.nii.gz",
            "flair": btp / f"{pid}_{btp.name}_flair.nii.gz",
            "t2": btp / f"{pid}_{btp.name}_t2.nii.gz",
            "t1": btp / f"{pid}_{btp.name}_t1.nii.gz",
            "seg1": _first_existing([btp / f"{pid}_{btp.name}_segmentations.nii.gz", btp / f"{pid}_{btp.name}_seg.nii.gz"]),
            "seg2": _first_existing([rtp / f"{pid}_{rtp.name}_segmentations.nii.gz", rtp / f"{pid}_{rtp.name}_seg.nii.gz"]),
        }
        if any(p is None or not p.exists() for p in paths.values()):
            continue
        try:
            seg1 = (_load_nifti(paths["seg1"]) > 0).astype(np.float32)
            seg2 = (_load_nifti(paths["seg2"]) > 0).astype(np.float32)
            centre = _centroid(seg1)
            raw = np.stack([
                _crop_native(_norm(_load_nifti(paths["t1ce"])), centre),
                _crop_native(_norm(_load_nifti(paths["flair"])), centre),
                _crop_native(_norm(_load_nifti(paths["t2"])), centre),
                _crop_native(_norm(_load_nifti(paths["t1"])), centre),
            ], axis=0)
            _add_record(records, "RHUH-GBM", pid, raw, _crop_native(seg1, centre), _crop_native(seg2, centre))
        except Exception as exc:
            print(f"Skipping RHUH {pid}: {exc}")


def _build_ucsd(records: list[dict], label_df: pd.DataFrame) -> None:
    available = set(label_df[label_df["cohort"].eq("UCSD-PTGBM")]["pid_clean"].astype(str))
    if not UCSD_ROOT.exists():
        return
    session_dirs = sorted([p for p in UCSD_ROOT.iterdir() if p.is_dir()])
    by_pid: dict[str, list[Path]] = {}
    for sdir in session_dirs:
        pid = re.sub(r"_\d+$", "", sdir.name)
        by_pid.setdefault(pid, []).append(sdir)
    for pid in sorted(available):
        sessions = sorted(by_pid.get(pid, []), key=lambda p: _timepoint_key(p.name))
        if len(sessions) < 2:
            continue
        btp, rtp = sessions[0], sessions[-1]
        paths = {
            "t1ce": btp / f"{btp.name}_T1post.nii.gz",
            "flair": btp / f"{btp.name}_FLAIR.nii.gz",
            "t2": btp / f"{btp.name}_T2.nii.gz",
            "t1": btp / f"{btp.name}_T1pre.nii.gz",
            "seg1": _first_existing([
                btp / f"{btp.name}_total_cellular_tumor_seg.nii.gz",
                btp / f"{btp.name}_BraTS_tumor_seg.nii.gz",
            ]),
            "seg2": _first_existing([
                rtp / f"{rtp.name}_total_cellular_tumor_seg.nii.gz",
                rtp / f"{rtp.name}_BraTS_tumor_seg.nii.gz",
            ]),
        }
        if any(p is None or not p.exists() for p in paths.values()):
            continue
        try:
            seg1 = (_load_nifti(paths["seg1"]) > 0).astype(np.float32)
            seg2 = (_load_nifti(paths["seg2"]) > 0).astype(np.float32)
            centre = _centroid(seg1)
            raw = np.stack([
                _crop_native(_norm(_load_nifti(paths["t1ce"])), centre),
                _crop_native(_norm(_load_nifti(paths["flair"])), centre),
                _crop_native(_norm(_load_nifti(paths["t2"])), centre),
                _crop_native(_norm(_load_nifti(paths["t1"])), centre),
            ], axis=0)
            _add_record(records, "UCSD-PTGBM", pid, raw, _crop_native(seg1, centre), _crop_native(seg2, centre))
        except Exception as exc:
            print(f"Skipping UCSD {pid}: {exc}")


def build_cache(rebuild: bool = False) -> dict[str, np.ndarray]:
    if CACHE.exists() and not rebuild:
        z = np.load(CACHE, allow_pickle=True)
        return {k: z[k] for k in z.files}

    label_df = _master_labels()
    stable_map = dict(zip(zip(label_df["cohort"], label_df["pid_clean"]), label_df["stable01"]))
    endpoint_map = dict(zip(zip(label_df["cohort"], label_df["pid_clean"]), label_df["endpoint_class"].astype(str)))
    records: list[dict] = []

    print("Building UCSF raw records...")
    _build_ucsf(records, label_df)
    print("Building MU raw records...")
    _build_mu(records, label_df)
    print("Building RHUH raw records...")
    _build_rhuh(records, label_df)
    print("Building UCSD raw records...")
    _build_ucsd(records, label_df)

    if not records:
        raise RuntimeError("No raw-MRI records could be built")

    keep = []
    for r in records:
        key = (r["cohort"], r["pid"])
        if key in stable_map:
            r["stable"] = int(stable_map[key])
            r["endpoint_class"] = endpoint_map[key]
            keep.append(r)
    records = keep
    if not records:
        raise RuntimeError("No raw-MRI records aligned to master index")

    arrays = {
        "cohorts": np.array([r["cohort"] for r in records]),
        "pids": np.array([r["pid"] for r in records]),
        "endpoint_class": np.array([r["endpoint_class"] for r in records]),
        "stable": np.array([r["stable"] for r in records], dtype=np.int64),
        "raw": np.stack([r["raw"] for r in records]),
        "mask": np.stack([r["mask"] for r in records]),
        "heat": np.stack([r["heat"] for r in records]),
        "sdf": np.stack([r["sdf"] for r in records]),
        "target": np.stack([r["target"] for r in records]),
        "base_vox": np.array([r["base_vox"] for r in records], dtype=np.float32),
        "target_vox": np.array([r["target_vox"] for r in records], dtype=np.float32),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE, **arrays)
    return arrays


def limit_per_cohort(data: dict[str, np.ndarray], limit: int | None) -> dict[str, np.ndarray]:
    if not limit:
        return data
    keep = []
    cohorts = data["cohorts"].astype(str)
    for cohort in sorted(set(cohorts)):
        idx = np.where(cohorts == cohort)[0][:limit]
        keep.extend(idx.tolist())
    keep = np.array(sorted(keep), dtype=int)
    return {k: v[keep] if hasattr(v, "__len__") and len(v) == len(cohorts) else v for k, v in data.items()}


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
            if x.shape[0] >= 4 and np.random.rand() < 0.5:
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


def eval_arrays(preds: np.ndarray, y: np.ndarray, mask: np.ndarray, stable: np.ndarray) -> dict[str, float]:
    briers, dices, aucs, eces = [], [], [], []
    stable_briers, active_briers = [], []
    for p, t, m, s in zip(preds, y, mask, stable):
        roi = binary_dilation(m > 0, iterations=6)
        if not roi.any():
            roi = np.ones_like(m, dtype=bool)
        pv = p[roi].ravel()
        tv = t[roi].ravel()
        b = float(np.mean((pv - tv) ** 2))
        briers.append(b)
        if int(s) == 1:
            stable_briers.append(b)
        else:
            active_briers.append(b)
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
        "brier_sd": float(np.std(briers, ddof=1)) if len(briers) > 1 else 0.0,
        "dice_mean": float(np.mean(dices)),
        "auroc_mean": float(np.nanmean(aucs)),
        "ece_mean": float(np.mean(eces)),
        "brier_stable": float(np.mean(stable_briers)) if stable_briers else None,
        "brier_active": float(np.mean(active_briers)) if active_briers else None,
        "n_stable": int(len(stable_briers)),
        "n_active": int(len(active_briers)),
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


def train_model(x_train, y_train, x_test, y_test, in_c: int, tag: str, epochs: int, batch: int):
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    model = SmallUNet3D(in_c=in_c).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    loader = DataLoader(CropDataset(x_train, y_train, augment=True), batch_size=batch, shuffle=True, num_workers=0)
    best_state, best_loss = None, math.inf
    for epoch in range(1, epochs + 1):
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
        if epoch in {1, max(1, epochs // 2), epochs}:
            print(f"{tag} epoch {epoch}/{epochs}: loss={mean_loss:.4f}")
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    preds = []
    with torch.no_grad():
        for xb, _ in DataLoader(CropDataset(x_test, y_test, augment=False), batch_size=batch, shuffle=False):
            preds.append(model(xb.to(DEVICE)).cpu().numpy())
    del model
    if DEVICE.type == "cuda":
        torch.cuda.empty_cache()
    return np.concatenate(preds, axis=0)[:, 0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raw-MRI LOCO external transportability stress test")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--limit-per-cohort", type=int, default=0)
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument(
        "--variants",
        default="mask_heat_sdf,raw4,raw4_mask,raw4_mask_heat_sdf",
        help="Comma-separated variants: mask_heat_sdf,raw4,raw4_mask,raw4_mask_heat_sdf",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start = time.time()
    print(f"Device: {DEVICE}")
    if DEVICE.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    data = limit_per_cohort(build_cache(rebuild=args.rebuild_cache), args.limit_per_cohort or None)
    cohorts = data["cohorts"].astype(str)
    raw = data["raw"]
    mask = data["mask"]
    heat = data["heat"]
    sdf = data["sdf"]
    y = data["target"][:, None]
    stable = data["stable"]

    variant_arrays = {
        "mask_heat_sdf": np.concatenate([mask[:, None], heat[:, None], sdf[:, None]], axis=1),
        "raw4": raw,
        "raw4_mask": np.concatenate([raw, mask[:, None]], axis=1),
        "raw4_mask_heat_sdf": np.concatenate([raw, mask[:, None], heat[:, None], sdf[:, None]], axis=1),
    }
    requested = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in requested:
        if v not in variant_arrays:
            raise ValueError(f"Unknown variant: {v}")

    cohort_summary = {}
    for cohort in sorted(set(cohorts)):
        idx = np.where(cohorts == cohort)[0]
        cohort_summary[cohort] = {
            "n": int(len(idx)),
            "pi_stable": float(stable[idx].mean()),
            "n_stable": int(stable[idx].sum()),
            "n_active": int(len(idx) - stable[idx].sum()),
        }
        print(f"{cohort}: n={len(idx)}, pi_stable={stable[idx].mean():.3f}")

    loco_results = {}
    held_cohorts = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]
    for held in held_cohorts:
        test_idx = np.where(cohorts == held)[0]
        train_idx = np.where(cohorts != held)[0]
        print("\n" + "=" * 70)
        print(f"LOCO raw stress test: train non-{held} n={len(train_idx)} -> test {held} n={len(test_idx)}")

        heat_metrics = eval_arrays(heat[test_idx], y[test_idx, 0], mask[test_idx], stable[test_idx])
        heat_case = per_case_brier(heat[test_idx], y[test_idx, 0], mask[test_idx])
        results = {"heat_prior_no_training": heat_metrics}
        case_briers = {"heat_prior_no_training": heat_case}
        print(f"Heat: Brier={heat_metrics['brier_mean']:.4f}, ECE={heat_metrics['ece_mean']:.4f}")

        for variant in requested:
            x = variant_arrays[variant]
            tag = f"{variant} -> {held}"
            pred = train_model(
                x[train_idx], y[train_idx],
                x[test_idx], y[test_idx],
                in_c=x.shape[1], tag=tag, epochs=args.epochs, batch=args.batch,
            )
            metrics = eval_arrays(pred, y[test_idx, 0], mask[test_idx], stable[test_idx])
            results[variant] = metrics
            case_briers[variant] = per_case_brier(pred, y[test_idx, 0], mask[test_idx])
            print(f"{variant}: Brier={metrics['brier_mean']:.4f}, ECE={metrics['ece_mean']:.4f}, AUROC={metrics['auroc_mean']:.4f}")

        deltas = {
            variant: paired_bootstrap(case_briers[variant] - heat_case)
            for variant in requested
        }
        best_variant = min(requested, key=lambda v: results[v]["brier_mean"])
        all_methods = ["heat_prior_no_training"] + requested
        winner = min(all_methods, key=lambda v: results[v]["brier_mean"])
        loco_results[held] = {
            "train_cohorts": sorted([c for c in set(cohorts) if c != held]),
            "n_train": int(len(train_idx)),
            "n_test": int(len(test_idx)),
            "pi_stable_test": float(stable[test_idx].mean()),
            "metrics": results,
            "paired_delta_vs_heat": deltas,
            "best_raw_variant": best_variant,
            "winner_by_brier": winner,
        }

    output = {
        "version": "v78_raw_mri_loco",
        "status": "RAW_MRI_EXTERNAL_TRANSPORTABILITY_STRESS_TEST",
        "date": time.strftime("%Y-%m-%d"),
        "device": str(DEVICE),
        "gpu": torch.cuda.get_device_name(0) if DEVICE.type == "cuda" else None,
        "crop_shape_DHW": list(CROP),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch),
        "limit_per_cohort": int(args.limit_per_cohort) if args.limit_per_cohort else None,
        "variants": requested,
        "cohort_summary": cohort_summary,
        "loco_results": loco_results,
        "interpretation": (
            "This tests whether raw MRI plus masks erase the heat-prior ranking reversal under "
            "external leave-one-cohort-out transfer. Negative paired deltas mean the trained model "
            "beat heat on held-out Brier; positive deltas mean heat remained stronger."
        ),
        "runtime_s": round(time.time() - start, 2),
    }
    OUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("\nSaved ->", OUT)
    print(json.dumps({
        "cohorts": cohort_summary,
        "winners": {k: v["winner_by_brier"] for k, v in loco_results.items()},
        "runtime_s": output["runtime_s"],
    }, indent=2))


if __name__ == "__main__":
    main()
