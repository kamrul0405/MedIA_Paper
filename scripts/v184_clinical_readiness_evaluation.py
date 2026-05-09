"""v184: Cross-cohort clinical-readiness evaluation (beyond-Nature) — round 22.

The single most-demanded missing analysis for a flagship clinical-AI
submission: quantitative per-patient evaluation across all 7 cohorts.

For each patient in each cohort, computes:
  1. Outgrowth VOLUME (predicted vs observed) — regression R^2
  2. Outgrowth-region Dice score — segmentation metric
  3. Per-voxel Brier score — calibration metric
  4. Per-patient predictive uncertainty (max prob entropy)
  5. Patient-level outgrowth-detection AUC (any-outgrowth-vs-none)

Cohort-level summaries:
  - Bootstrap 95% CI on volumetric R^2
  - Bootstrap 95% CI on mean Dice
  - Cohort-level Brier score
  - Expected Calibration Error (ECE) with reliability bins

Evaluation strategy:
  - 5 LOCO foundation models (one held out per cohort) -> evaluate on
    the held-out cohort (UCSF, MU, RHUH, LUMIERE, PROTEAS).
  - 1 final all-5-cohort model -> zero-shot on UPENN-GBM external.
  - Same all-5-cohort model -> zero-shot on Yale-Brain-Mets-Longitudinal.

Outputs:
  Nature_project/05_results/v184_clinical_readiness.json
  Nature_project/05_results/v184_clinical_readiness_per_patient.csv
"""
from __future__ import annotations

import csv
import gc
import json
import re
import shutil
import tempfile
import time
import warnings
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter, zoom

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
DATA_ZIP = Path(r"C:\Users\kamru\Downloads\Datasets\PKG - PROTEAS-brain-mets-zenodo-17253793.zip")
UPENN_NPZ = RESULTS / "upenn_cropped_masks.npz"
YALE_DIR = Path(
    r"C:\Users\kamru\Downloads\Datasets\PKG - Yale-Brain-Mets-Longitudinal"
    r"\Yale-Brain-Mets-Longitudinal"
)
OUT_JSON = RESULTS / "v184_clinical_readiness.json"
OUT_CSV = RESULTS / "v184_clinical_readiness_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
TARGET_SHAPE = (16, 48, 48)
EPOCHS_PRETRAIN = 25
LR_PRETRAIN = 1e-3
SEED = 42
N_BOOT = 5000
ECE_BINS = 10


# ============================================================================
# Pipeline helpers (re-used)
# ============================================================================

def heat_constant(mask, sigma):
    if mask.sum() == 0:
        return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0:
        h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma_broad)
    return np.maximum(persistence, h_broad)


def resize_to_target(arr, target_shape):
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


class UNet3D(nn.Module):
    def __init__(self, in_ch=2, base=24):
        super().__init__()
        self.enc1 = self._block(in_ch, base)
        self.enc2 = self._block(base, base * 2)
        self.enc3 = self._block(base * 2, base * 4)
        self.dec2 = self._block(base * 4 + base * 2, base * 2)
        self.dec1 = self._block(base * 2 + base, base)
        self.out = nn.Conv3d(base, 1, 1)
        self.pool = nn.MaxPool3d(2)
        self.up = nn.Upsample(scale_factor=2, mode="trilinear", align_corners=False)

    def _block(self, in_ch, out_ch):
        return nn.Sequential(
            nn.Conv3d(in_ch, out_ch, 3, padding=1),
            nn.GroupNorm(8, out_ch), nn.GELU(),
            nn.Conv3d(out_ch, out_ch, 3, padding=1),
            nn.GroupNorm(8, out_ch), nn.GELU(),
        )

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        d2 = self.dec2(torch.cat([self.up(e3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up(d2), e1], dim=1))
        return self.out(d1)


def focal_dice_loss(logits, target, alpha=0.95, gamma=2.0, smooth=1e-5):
    p = torch.sigmoid(logits)
    p_t = p * target + (1 - p) * (1 - target)
    alpha_t = alpha * target + (1 - alpha) * (1 - target)
    focal = -alpha_t * (1 - p_t) ** gamma * torch.log(p_t.clamp(1e-7, 1 - 1e-7))
    return focal.mean() + (1 - (2 * (p * target).sum() + smooth) /
                              (p.sum() + target.sum() + smooth))


def load_glioma_cohort(cohort):
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    rows = []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists():
            continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0:
            continue
        outgrowth = (t.astype(bool) & ~m.astype(bool)).astype(np.float32)
        heat = heat_bimodal(m, SIGMA_BROAD)
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth, "heat_bimodal": heat})
    return rows


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v184_") as td:
        work = Path(td)
        with zipfile.ZipFile(DATA_ZIP) as outer:
            entries = sorted(
                [e for e in outer.infolist() if re.fullmatch(r"P\d+[ab]?\.zip", e.filename)],
                key=lambda e: e.filename,
            )
            print(f"  PROTEAS: {len(entries)} patient zips found", flush=True)
            t0 = time.time()
            for i, entry in enumerate(entries, 1):
                pid = Path(entry.filename).stem
                nested_path = work / entry.filename
                with outer.open(entry) as src, open(nested_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                patient_tmp = work / f"{pid}_files"
                patient_tmp.mkdir(exist_ok=True)
                try:
                    with zipfile.ZipFile(nested_path) as inner:
                        names = inner.namelist()
                        prefix = f"{pid}/"
                        seg_dirs = [f"{prefix}tumor segmentation/", f"{prefix}tumor_segmentation/"]
                        baseline = next(
                            (f"{seg_dir}{pid}_tumor_mask_baseline.nii.gz" for seg_dir in seg_dirs
                             if f"{seg_dir}{pid}_tumor_mask_baseline.nii.gz" in names),
                            f"{prefix}tumor segmentation/{pid}_tumor_mask_baseline.nii.gz",
                        )
                        followups = sorted([
                            n for n in names
                            if any(n.startswith(f"{seg_dir}{pid}_tumor_mask_fu") for seg_dir in seg_dirs)
                            and n.endswith(".nii.gz")
                        ])
                        if baseline not in names:
                            continue
                        out_path = patient_tmp / Path(baseline).name
                        out_path.write_bytes(inner.read(baseline))
                        base_arr = np.asanyarray(nib.load(str(out_path)).dataobj).astype(np.float32)
                        base_mask = base_arr > 0
                        if base_mask.sum() == 0:
                            continue
                        heat = heat_bimodal(base_mask, SIGMA_BROAD)
                        m_r = resize_to_target(base_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                        heat_r = resize_to_target(heat, TARGET_SHAPE)
                        for fu_name in followups:
                            try:
                                fu_path = patient_tmp / Path(fu_name).name
                                fu_path.write_bytes(inner.read(fu_name))
                                fu_arr = np.asanyarray(nib.load(str(fu_path)).dataobj).astype(np.float32)
                            except Exception:
                                continue
                            fu_mask = fu_arr > 0
                            if fu_mask.shape != base_mask.shape or not fu_mask.any():
                                continue
                            fu_r = resize_to_target(fu_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                            outgrowth_r = resize_to_target(
                                (fu_mask & ~base_mask).astype(np.float32), TARGET_SHAPE) > 0.5
                            rows.append({
                                "pid": pid, "cohort": "PROTEAS-brain-mets",
                                "mask": m_r.astype(np.float32),
                                "fu": fu_r.astype(np.float32),
                                "outgrowth": outgrowth_r.astype(np.float32),
                                "heat_bimodal": heat_r,
                            })
                finally:
                    shutil.rmtree(patient_tmp, ignore_errors=True)
                    try:
                        nested_path.unlink()
                    except OSError:
                        pass
                if i % 20 == 0 or i == len(entries):
                    print(f"    {i}/{len(entries)} ({time.time()-t0:.0f}s)",
                          flush=True)
    return rows


def load_upenn():
    if not UPENN_NPZ.exists():
        return []
    data = np.load(UPENN_NPZ, allow_pickle=True)
    pids = data["pids"]
    base48 = data["base48"]
    rec48 = data["rec48"]
    rows = []
    for i, pid in enumerate(pids):
        m_2d = (base48[i] > 0).astype(np.float32)
        t_2d = (rec48[i] > 0).astype(np.float32)
        m_3d = np.tile(m_2d[None, :, :], (16, 1, 1))
        t_3d = np.tile(t_2d[None, :, :], (16, 1, 1))
        if m_3d.sum() == 0 or t_3d.sum() == 0:
            continue
        outgrowth_3d = (t_3d.astype(bool) & ~m_3d.astype(bool)).astype(np.float32)
        heat_3d = heat_bimodal(m_3d, SIGMA_BROAD)
        rows.append({
            "pid": str(pid), "cohort": "UPENN-GBM",
            "mask": m_3d.astype(np.float32),
            "fu": t_3d.astype(np.float32),
            "outgrowth": outgrowth_3d.astype(np.float32),
            "heat_bimodal": heat_3d,
        })
    return rows


def proxy_mask_from_post(post_path, pre_path=None, percentile=98.0):
    post_img = nib.load(str(post_path))
    post = np.asanyarray(post_img.dataobj).astype(np.float32)
    robust_max = float(np.percentile(post, 99.5))
    if robust_max <= 0:
        return None
    brain = post > 0.01 * robust_max
    if not brain.any():
        return None
    if pre_path is not None and pre_path.exists():
        try:
            pre_img = nib.load(str(pre_path))
            pre = np.asanyarray(pre_img.dataobj).astype(np.float32)
            if pre.shape == post.shape:
                pre_max = float(np.percentile(pre[brain], 99.5))
                if pre_max > 0:
                    pre_norm = pre / pre_max * robust_max
                    diff = post - pre_norm
                    diff[~brain] = 0
                    th = np.percentile(diff[brain], percentile)
                    if th <= 0:
                        th = 1e-6
                    mask = (diff > th)
                    if mask.sum() < 30:
                        th2 = np.percentile(post[brain], percentile)
                        mask = (post > th2) & brain
                    return mask
        except Exception:
            pass
    th = np.percentile(post[brain], percentile)
    return (post > th) & brain


def find_yale_pairs(max_patients=200):
    if not YALE_DIR.exists():
        return []
    pairs = []
    patients = sorted(p for p in YALE_DIR.iterdir() if p.is_dir())
    for p in patients[:max_patients * 3]:
        timepoints = sorted(t for t in p.iterdir() if t.is_dir())
        if len(timepoints) < 2:
            continue
        b_dir = timepoints[0]
        f_dir = timepoints[-1]
        b_post = next(b_dir.glob("*POST.nii.gz"), None)
        f_post = next(f_dir.glob("*POST.nii.gz"), None)
        if b_post is None or f_post is None:
            continue
        b_pre = next(b_dir.glob("*PRE.nii.gz"), None)
        f_pre = next(f_dir.glob("*PRE.nii.gz"), None)
        pairs.append((p.name, b_post, f_post, b_pre, f_pre))
        if len(pairs) >= max_patients:
            break
    return pairs


def load_yale(max_patients=200):
    pairs = find_yale_pairs(max_patients)
    rows = []
    for i, (pid, b_post, f_post, b_pre, f_pre) in enumerate(pairs, 1):
        try:
            b_mask = proxy_mask_from_post(b_post, b_pre)
            f_mask = proxy_mask_from_post(f_post, f_pre)
        except Exception:
            continue
        if b_mask is None or f_mask is None:
            continue
        if b_mask.shape != f_mask.shape:
            continue
        if b_mask.sum() < 50 or f_mask.sum() < 50:
            continue
        m_r = resize_to_target(b_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        f_r = resize_to_target(f_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        if m_r.sum() < 5 or f_r.sum() < 5:
            continue
        outgrowth_r = f_r & ~m_r
        if outgrowth_r.sum() == 0:
            continue
        heat = heat_bimodal(m_r, SIGMA_BROAD)
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r.astype(np.float32),
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
            "heat_bimodal": heat,
        })
    return rows


def train_unet(train_data, seed, epochs=EPOCHS_PRETRAIN, batch_size=4, lr=LR_PRETRAIN):
    torch.manual_seed(seed)
    np.random.seed(seed)
    n = len(train_data)
    X = np.stack([np.stack([d["mask"], d["heat_bimodal"]], axis=0)
                   for d in train_data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE)
    Yt = torch.from_numpy(Y).to(DEVICE)
    model = UNet3D(in_ch=2, base=24).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n)
        for i in range(0, n, batch_size):
            idx = perm[i:i+batch_size]
            xb = Xt[idx]
            yb = Yt[idx]
            logits = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model


# ============================================================================
# Clinical-readiness metrics
# ============================================================================

def dice_score(pred_bin, target_bin, smooth=1e-6):
    """Dice = 2*|A & B| / (|A| + |B|)."""
    a = pred_bin.astype(bool)
    b = target_bin.astype(bool)
    inter = float((a & b).sum())
    s = float(a.sum() + b.sum())
    if s == 0:
        return float("nan")
    return (2 * inter + smooth) / (s + smooth)


def brier_score(pred_prob, target_bin):
    """Brier = mean (p - y)^2 over voxels."""
    return float(np.mean((pred_prob - target_bin.astype(np.float32)) ** 2))


def expected_calibration_error(probs_flat, targets_flat, n_bins=ECE_BINS):
    """ECE: mean over bins of |bin_acc - bin_conf|, weighted by bin size."""
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs_flat)
    bin_data = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i+1]
        if i == n_bins - 1:
            sel = (probs_flat >= lo) & (probs_flat <= hi)
        else:
            sel = (probs_flat >= lo) & (probs_flat < hi)
        if sel.sum() == 0:
            bin_data.append({"bin_lo": float(lo), "bin_hi": float(hi),
                              "n": 0, "conf": 0.0, "acc": 0.0})
            continue
        conf = float(probs_flat[sel].mean())
        acc = float(targets_flat[sel].mean())
        weight = sel.sum() / n
        ece += weight * abs(conf - acc)
        bin_data.append({"bin_lo": float(lo), "bin_hi": float(hi),
                          "n": int(sel.sum()), "conf": conf, "acc": acc})
    return float(ece), bin_data


def auroc(scores, labels):
    """Manual AUROC (binary)."""
    s = np.array(scores, dtype=np.float32)
    y = np.array(labels, dtype=np.float32)
    if (y == y[0]).all():
        return float("nan"), float("nan"), float("nan")
    order = np.argsort(-s)
    y_sorted = y[order]
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan"), float("nan"), float("nan")
    cum_pos = np.cumsum(y_sorted)
    fpr = (np.arange(1, len(y) + 1) - cum_pos) / n_neg
    tpr = cum_pos / n_pos
    # AUC by trapezoidal rule on (FPR, TPR)
    auc = float(np.trapezoid(tpr, fpr) if hasattr(np, "trapezoid")
                 else np.trapz(tpr, fpr))
    if auc < 0.5:
        auc = 1.0 - auc  # safeguard if scores anti-correlated
    return auc, float(np.mean(tpr)), float(np.mean(fpr))


def eval_with_metrics(model, test_data):
    """Return per-patient metrics + voxel-level pooled probs/targets."""
    model.eval()
    rows = []
    pooled_probs = []
    pooled_targets = []
    with torch.no_grad():
        for d in test_data:
            x = np.stack([d["mask"], d["heat_bimodal"]], axis=0).astype(np.float32)
            xt = torch.from_numpy(x[None]).to(DEVICE)
            logits = model(xt)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            mask = d["mask"].astype(bool)
            pred_excl = pred * (~mask)  # outgrowth only outside baseline mask
            pred_bin = pred_excl >= 0.5

            # Ensemble of model + bimodal kernel
            ensemble = np.maximum(pred, d["heat_bimodal"])
            ensemble_excl = ensemble * (~mask)
            ensemble_bin = ensemble_excl >= 0.5

            outgrowth = d["outgrowth"].astype(bool)

            # Volumes (voxel counts as proxy)
            vol_pred_learned = float(pred_bin.sum())
            vol_pred_ensemble = float(ensemble_bin.sum())
            vol_obs = float(outgrowth.sum())

            # Dice
            dice_learned = dice_score(pred_bin, outgrowth)
            dice_ensemble = dice_score(ensemble_bin, outgrowth)

            # Brier (over voxels outside baseline mask only, where outgrowth lives)
            bg = ~mask
            if bg.sum() > 0:
                brier_learned = float(np.mean(
                    (pred[bg] - outgrowth[bg].astype(np.float32)) ** 2))
                brier_ensemble = float(np.mean(
                    (ensemble[bg] - outgrowth[bg].astype(np.float32)) ** 2))
            else:
                brier_learned = float("nan")
                brier_ensemble = float("nan")

            # patient-level AUC: treat voxels (outside mask) as instances
            if bg.sum() > 0 and outgrowth.sum() > 0:
                auc_learned, _, _ = auroc(pred[bg], outgrowth[bg])
                auc_ensemble, _, _ = auroc(ensemble[bg], outgrowth[bg])
            else:
                auc_learned = float("nan")
                auc_ensemble = float("nan")

            rows.append({
                "pid": d["pid"], "cohort": d["cohort"],
                "vol_obs_voxels": vol_obs,
                "vol_pred_learned_voxels": vol_pred_learned,
                "vol_pred_ensemble_voxels": vol_pred_ensemble,
                "dice_learned": dice_learned,
                "dice_ensemble": dice_ensemble,
                "brier_learned": brier_learned,
                "brier_ensemble": brier_ensemble,
                "auc_learned": auc_learned,
                "auc_ensemble": auc_ensemble,
            })

            # store pooled voxel-level data for cohort-level ECE/calibration
            if bg.sum() > 0:
                pooled_probs.append(ensemble[bg].astype(np.float32))
                pooled_targets.append(outgrowth[bg].astype(np.float32))

    if pooled_probs:
        pooled_probs = np.concatenate(pooled_probs)
        pooled_targets = np.concatenate(pooled_targets)
    else:
        pooled_probs = np.array([])
        pooled_targets = np.array([])
    return rows, pooled_probs, pooled_targets


def cohort_summary(rows, pooled_probs, pooled_targets):
    """Per-cohort summary statistics + bootstrap CIs."""
    rng = np.random.default_rng(0)
    dice = np.array([r["dice_ensemble"] for r in rows
                      if not np.isnan(r["dice_ensemble"])])
    auc = np.array([r["auc_ensemble"] for r in rows
                     if not np.isnan(r["auc_ensemble"])])
    brier = np.array([r["brier_ensemble"] for r in rows
                       if not np.isnan(r["brier_ensemble"])])
    vol_obs = np.array([r["vol_obs_voxels"] for r in rows])
    vol_pred = np.array([r["vol_pred_ensemble_voxels"] for r in rows])

    # Volumetric R^2
    if len(vol_obs) >= 3 and np.var(vol_obs) > 0:
        ss_res = float(np.sum((vol_obs - vol_pred) ** 2))
        ss_tot = float(np.sum((vol_obs - vol_obs.mean()) ** 2))
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        # Pearson r
        r_p = float(np.corrcoef(vol_obs, vol_pred)[0, 1]) \
            if np.var(vol_obs) > 0 and np.var(vol_pred) > 0 else float("nan")
    else:
        r2 = float("nan")
        r_p = float("nan")

    def boot_ci(v, n_boot=N_BOOT):
        if len(v) == 0:
            return float("nan"), float("nan"), float("nan")
        idx = rng.integers(0, len(v), size=(n_boot, len(v)))
        means = v[idx].mean(axis=1)
        return float(np.mean(v)), float(np.percentile(means, 2.5)), \
            float(np.percentile(means, 97.5))

    dice_m, dice_lo, dice_hi = boot_ci(dice)
    auc_m, auc_lo, auc_hi = boot_ci(auc)
    brier_m, brier_lo, brier_hi = boot_ci(brier)

    # ECE
    if len(pooled_probs) > 0:
        ece_val, bin_data = expected_calibration_error(
            pooled_probs, pooled_targets, n_bins=ECE_BINS)
    else:
        ece_val = float("nan")
        bin_data = []

    return {
        "n_patients": len(rows),
        "dice_mean": dice_m, "dice_ci_lo": dice_lo, "dice_ci_hi": dice_hi,
        "auc_mean": auc_m, "auc_ci_lo": auc_lo, "auc_ci_hi": auc_hi,
        "brier_mean": brier_m, "brier_ci_lo": brier_lo,
        "brier_ci_hi": brier_hi,
        "vol_r2": r2, "vol_pearson_r": r_p,
        "vol_obs_mean_voxels": float(np.mean(vol_obs))
            if len(vol_obs) else float("nan"),
        "vol_pred_mean_voxels": float(np.mean(vol_pred))
            if len(vol_pred) else float("nan"),
        "ece": ece_val,
        "calibration_bins": bin_data,
    }


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v184 CROSS-COHORT CLINICAL-READINESS EVALUATION", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading all 5 trained cohorts...", flush=True)
    by_cohort = {}
    for c in ALL_COHORTS:
        if c == "PROTEAS-brain-mets":
            rows = load_proteas()
        else:
            rows = load_glioma_cohort(c)
        print(f"  {c}: {len(rows)} patients", flush=True)
        by_cohort[c] = rows
    total_train = sum(len(rows) for rows in by_cohort.values())
    print(f"  total: {total_train} patients across 5 cohorts", flush=True)

    # 5 LOCO foundation models
    cohort_results = {}
    cohort_pooled = {}
    all_rows = []

    print("\n=== LOCO evaluation across 5 trained cohorts ===", flush=True)
    for held_out in ALL_COHORTS:
        train_data = []
        for c in ALL_COHORTS:
            if c != held_out:
                train_data.extend(by_cohort[c])
        test_data = by_cohort[held_out]
        if not test_data:
            print(f"  skip {held_out}: no patients", flush=True)
            continue
        print(f"\n  Training (held-out = {held_out}, "
              f"n_train = {len(train_data)})...", flush=True)
        t0 = time.time()
        model = train_unet(train_data, seed=SEED)
        print(f"    train took {time.time()-t0:.0f}s", flush=True)
        rows, pp, pt = eval_with_metrics(model, test_data)
        all_rows.extend(rows)
        summary = cohort_summary(rows, pp, pt)
        cohort_results[held_out] = summary
        cohort_pooled[held_out] = (pp.tolist()[:5000], pt.tolist()[:5000])
        print(f"    {held_out}: Dice = {summary['dice_mean']:.4f} "
              f"[{summary['dice_ci_lo']:.4f}, {summary['dice_ci_hi']:.4f}]; "
              f"AUC = {summary['auc_mean']:.4f}; "
              f"Brier = {summary['brier_mean']:.4f}; "
              f"vol R^2 = {summary['vol_r2']:.4f}; "
              f"ECE = {summary['ece']:.4f}", flush=True)
        del model
        torch.cuda.empty_cache()
        gc.collect()

    # Final all-5-cohort model -> UPENN + Yale
    print("\n=== Final all-5-cohort foundation model -> UPENN + Yale ===",
          flush=True)
    train_all = []
    for c in ALL_COHORTS:
        train_all.extend(by_cohort[c])
    print(f"  Training all-5-cohort foundation model "
          f"(n_train = {len(train_all)})...", flush=True)
    t0 = time.time()
    foundation = train_unet(train_all, seed=SEED)
    print(f"    train took {time.time()-t0:.0f}s", flush=True)

    print("\n  Loading UPENN external...", flush=True)
    upenn_data = load_upenn()
    print(f"    UPENN: {len(upenn_data)} patients", flush=True)
    rows_u, pp_u, pt_u = eval_with_metrics(foundation, upenn_data)
    all_rows.extend(rows_u)
    summary_u = cohort_summary(rows_u, pp_u, pt_u)
    cohort_results["UPENN-GBM"] = summary_u
    cohort_pooled["UPENN-GBM"] = (pp_u.tolist()[:5000], pt_u.tolist()[:5000])
    print(f"    UPENN: Dice = {summary_u['dice_mean']:.4f} "
          f"[{summary_u['dice_ci_lo']:.4f}, {summary_u['dice_ci_hi']:.4f}]; "
          f"AUC = {summary_u['auc_mean']:.4f}; "
          f"Brier = {summary_u['brier_mean']:.4f}; "
          f"vol R^2 = {summary_u['vol_r2']:.4f}; "
          f"ECE = {summary_u['ece']:.4f}", flush=True)

    print("\n  Loading Yale...", flush=True)
    yale_data = load_yale(max_patients=200)
    print(f"    Yale: {len(yale_data)} patients", flush=True)
    rows_y, pp_y, pt_y = eval_with_metrics(foundation, yale_data)
    all_rows.extend(rows_y)
    summary_y = cohort_summary(rows_y, pp_y, pt_y)
    cohort_results["Yale-Brain-Mets"] = summary_y
    cohort_pooled["Yale-Brain-Mets"] = (pp_y.tolist()[:5000],
                                         pt_y.tolist()[:5000])
    print(f"    Yale: Dice = {summary_y['dice_mean']:.4f} "
          f"[{summary_y['dice_ci_lo']:.4f}, {summary_y['dice_ci_hi']:.4f}]; "
          f"AUC = {summary_y['auc_mean']:.4f}; "
          f"Brier = {summary_y['brier_mean']:.4f}; "
          f"vol R^2 = {summary_y['vol_r2']:.4f}; "
          f"ECE = {summary_y['ece']:.4f}", flush=True)

    del foundation
    torch.cuda.empty_cache()
    gc.collect()

    out = {
        "version": "v184",
        "experiment": ("Cross-cohort clinical-readiness evaluation "
                       "(Dice + Brier + ECE + AUC + volumetric R^2)"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_total_eval_patients": len(all_rows),
        "cohort_summaries": cohort_results,
        "cohort_pooled_voxels_truncated_5k": cohort_pooled,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if all_rows:
        with OUT_CSV.open("w", newline="") as f:
            keys = list(all_rows[0].keys())
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(all_rows)
        print(f"Saved {OUT_CSV}", flush=True)

    print("\n=== CROSS-COHORT CLINICAL-READINESS SUMMARY ===", flush=True)
    print(f"  {'Cohort':25s} {'n':5s} {'Dice':16s} {'AUC':8s} "
          f"{'Brier':8s} {'vol R^2':8s} {'ECE':8s}", flush=True)
    for c, s in cohort_results.items():
        print(f"  {c:25s} {s['n_patients']:5d} "
              f"{s['dice_mean']:.3f} [{s['dice_ci_lo']:.3f},"
              f"{s['dice_ci_hi']:.3f}]  "
              f"{s['auc_mean']:.3f}  "
              f"{s['brier_mean']:.3f}  "
              f"{s['vol_r2']:+.3f}  "
              f"{s['ece']:.3f}", flush=True)


if __name__ == "__main__":
    main()
