"""v188: Mechanistic interpretability + adversarial robustness — round 26.

A senior Nature reviewer's two final demands for any clinical AI paper:

  PART 1 — Mechanistic interpretability ("what does the model
  actually learn that the kernel doesn't?").

  Decompose the foundation model's voxel-level output:
      F(x) = sigmoid(unet(mask, K))         [learned model]
      K(x) = max(M, G_sigma * M)            [bimodal kernel]
  Define the *learned residual*
      R(x) = F(x) - K(x)
  and characterise it on UPENN external + Yale zero-shot:
    - Mean magnitude, sign, sparsity
    - Spatial concentration (within-mask vs near-boundary vs distant)
    - Per-patient distribution

  PART 2 — Adversarial robustness ("does the foundation model
  break under realistic clinical noise?").

  Apply five clinically-realistic perturbations to the UPENN
  baseline mask + heat kernel:
    - erode 1 voxel  (under-segmentation)
    - erode 2 voxels (under-segmentation, severe)
    - dilate 1 voxel (over-segmentation)
    - dilate 2 voxels (over-segmentation, severe)
    - random 1% voxel flip (annotation noise)
  Re-evaluate AUC + Dice + outgrowth coverage. Compare to baseline.

Outputs:
  Nature_project/05_results/v188_interpretability_robustness.json
  Nature_project/05_results/v188_residual_per_patient.csv
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
from scipy.ndimage import (binary_dilation, binary_erosion,
                              distance_transform_edt, gaussian_filter, zoom)

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
OUT_JSON = RESULTS / "v188_interpretability_robustness.json"
OUT_CSV = RESULTS / "v188_residual_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
TARGET_SHAPE = (16, 48, 48)
EPOCHS_PRETRAIN = 25
LR_PRETRAIN = 1e-3
SEED = 42
BATCH_SIZE = 4


# ============================================================================
# Pipeline helpers (reused)
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
    with tempfile.TemporaryDirectory(prefix="proteas_v188_") as td:
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
                        m_r = resize_to_target(base_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                        m_r_f = m_r.astype(np.float32)
                        heat = heat_bimodal(m_r_f, SIGMA_BROAD)
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
                            outgrowth_r = fu_r & ~m_r
                            rows.append({
                                "pid": pid, "cohort": "PROTEAS-brain-mets",
                                "mask": m_r_f,
                                "fu": fu_r.astype(np.float32),
                                "outgrowth": outgrowth_r.astype(np.float32),
                                "heat_bimodal": heat,
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
        m_r_f = m_r.astype(np.float32)
        heat = heat_bimodal(m_r_f, SIGMA_BROAD)
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r_f,
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
            "heat_bimodal": heat,
        })
    return rows


def train_unet(train_data, seed, epochs=EPOCHS_PRETRAIN, batch_size=BATCH_SIZE, lr=LR_PRETRAIN):
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


def auroc(scores, labels):
    s = np.array(scores, dtype=np.float32)
    y = np.array(labels, dtype=np.float32)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(-s)
    y_sorted = y[order]
    cum_pos = np.cumsum(y_sorted)
    fpr = (np.arange(1, len(y) + 1) - cum_pos) / n_neg
    tpr = cum_pos / n_pos
    fpr = np.concatenate([[0.0], fpr])
    tpr = np.concatenate([[0.0], tpr])
    if hasattr(np, "trapezoid"):
        auc = float(np.trapezoid(tpr, fpr))
    else:
        auc = float(np.trapz(tpr, fpr))
    if auc < 0.5:
        auc = 1.0 - auc
    return auc


# ============================================================================
# PART 1 — Mechanistic interpretability: residual analysis
# ============================================================================

def analyse_residual(model, test_data):
    model.eval()
    rows = []
    with torch.no_grad():
        for d in test_data:
            x = np.stack([d["mask"], d["heat_bimodal"]], axis=0).astype(np.float32)
            xt = torch.from_numpy(x[None]).to(DEVICE)
            logits = model(xt)
            F_pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            K = d["heat_bimodal"]
            mask = d["mask"].astype(bool)
            outgrowth = d["outgrowth"].astype(bool)
            # Residual analysis only outside the baseline mask
            bg = ~mask
            R = (F_pred - K)
            R_bg = R[bg]
            F_bg = F_pred[bg]
            K_bg = K[bg]

            # Stats
            mean_R = float(np.mean(R_bg))
            std_R = float(np.std(R_bg))
            sparsity = float((np.abs(R_bg) < 0.01).sum() / len(R_bg))
            # Spatial concentration: is R concentrated near boundary or far?
            d_dist = distance_transform_edt(~mask)
            d_dist_bg = d_dist[bg]
            # Correlation between |R| and distance from boundary
            if np.std(d_dist_bg) > 0:
                corr_abs_R_distance = float(
                    np.corrcoef(np.abs(R_bg), d_dist_bg)[0, 1])
            else:
                corr_abs_R_distance = float("nan")
            # Concentration in outgrowth region vs non-outgrowth region
            out_mask = outgrowth & bg
            non_out = bg & ~outgrowth
            if out_mask.sum() > 0 and non_out.sum() > 0:
                mean_R_in_outgrowth = float(np.mean(R[out_mask]))
                mean_R_non_outgrowth = float(np.mean(R[non_out]))
                separation_R = mean_R_in_outgrowth - mean_R_non_outgrowth
            else:
                mean_R_in_outgrowth = float("nan")
                mean_R_non_outgrowth = float("nan")
                separation_R = float("nan")

            rows.append({
                "pid": d["pid"], "cohort": d["cohort"],
                "mean_R_outside_mask": mean_R,
                "std_R": std_R,
                "sparsity_pct": sparsity * 100,
                "corr_abs_R_distance_from_boundary": corr_abs_R_distance,
                "mean_R_in_outgrowth_region": mean_R_in_outgrowth,
                "mean_R_in_non_outgrowth": mean_R_non_outgrowth,
                "R_separation_outgrowth_vs_non": separation_R,
                "n_voxels_outside_mask": int(bg.sum()),
                "n_voxels_in_outgrowth": int(out_mask.sum()),
            })
    return rows


# ============================================================================
# PART 2 — Adversarial robustness
# ============================================================================

def perturb_mask(mask, kind, rng=None):
    """Return a perturbed mask + recomputed heat kernel."""
    if kind == "baseline":
        return mask.copy()
    if kind == "erode_1":
        return binary_erosion(mask, iterations=1).astype(np.float32)
    if kind == "erode_2":
        return binary_erosion(mask, iterations=2).astype(np.float32)
    if kind == "dilate_1":
        return binary_dilation(mask, iterations=1).astype(np.float32)
    if kind == "dilate_2":
        return binary_dilation(mask, iterations=2).astype(np.float32)
    if kind == "flip_1pct":
        rng = rng if rng is not None else np.random.default_rng(0)
        m = mask.copy().astype(bool)
        flip = rng.random(m.shape) < 0.01
        m[flip] = ~m[flip]
        return m.astype(np.float32)
    raise ValueError(f"unknown kind {kind}")


def evaluate_perturbation(model, test_data, perturbation_kind, sigma=SIGMA_BROAD):
    model.eval()
    pat_cov = []
    pat_auc = []
    pat_dice = []
    rng = np.random.default_rng(SEED)
    with torch.no_grad():
        for d in test_data:
            m_perturbed = perturb_mask(d["mask"], perturbation_kind, rng=rng)
            heat_perturbed = heat_bimodal(m_perturbed, sigma)
            x = np.stack([m_perturbed, heat_perturbed], axis=0).astype(np.float32)
            xt = torch.from_numpy(x[None]).to(DEVICE)
            logits = model(xt)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]

            mask_bool = m_perturbed.astype(bool)
            outgrowth = (d["fu"].astype(bool)) & ~mask_bool

            ensemble = np.maximum(pred, heat_perturbed)
            ensemble_bin = (ensemble * (~mask_bool)) >= 0.5
            if outgrowth.sum() > 0:
                cov = float((ensemble_bin & outgrowth).sum() / outgrowth.sum())
                pat_cov.append(cov)

            bg = ~mask_bool
            if bg.sum() > 0 and outgrowth.sum() > 0:
                auc = auroc(ensemble[bg], outgrowth[bg].astype(np.float32))
                if not np.isnan(auc):
                    pat_auc.append(auc)
            inter = (ensemble_bin & outgrowth).sum()
            s = ensemble_bin.sum() + outgrowth.sum()
            if s > 0:
                pat_dice.append(float(2 * inter / s))

    def safe_mean(arr):
        return float(np.mean(arr)) if arr else float("nan")

    return {
        "kind": perturbation_kind,
        "n_eval": len(pat_cov),
        "ensemble_outgrowth_coverage_mean": safe_mean(pat_cov),
        "auc_mean": safe_mean(pat_auc),
        "dice_mean": safe_mean(pat_dice),
    }


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v188 INTERPRETABILITY + ADVERSARIAL ROBUSTNESS", flush=True)
    print("=" * 78, flush=True)

    # Load all 5 trained cohorts -> train one foundation model
    print("\nLoading 5 trained cohorts...", flush=True)
    train_data = []
    for c in ALL_COHORTS:
        if c == "PROTEAS-brain-mets":
            rows = load_proteas()
        else:
            rows = load_glioma_cohort(c)
        train_data.extend(rows)
        print(f"  {c}: {len(rows)} patients", flush=True)
    print(f"  Total train: {len(train_data)} patients", flush=True)

    print("\nLoading UPENN + Yale...", flush=True)
    upenn_data = load_upenn()
    yale_data = load_yale()
    print(f"  UPENN: {len(upenn_data)} patients", flush=True)
    print(f"  Yale: {len(yale_data)} patients", flush=True)

    print("\nTraining foundation model on 5 cohorts...", flush=True)
    t0 = time.time()
    model = train_unet(train_data, seed=SEED)
    print(f"  Train took {time.time()-t0:.0f}s", flush=True)

    # ========================================================================
    # PART 1 — Residual analysis
    # ========================================================================
    print("\n" + "=" * 60, flush=True)
    print("PART 1 — Mechanistic interpretability (learned residual)",
          flush=True)
    print("=" * 60, flush=True)

    upenn_rows = analyse_residual(model, upenn_data)
    yale_rows = analyse_residual(model, yale_data)

    def summarise(rows, cohort):
        sep = [r["R_separation_outgrowth_vs_non"] for r in rows
                if not np.isnan(r["R_separation_outgrowth_vs_non"])]
        mean_R = [r["mean_R_outside_mask"] for r in rows]
        std_R = [r["std_R"] for r in rows]
        spar = [r["sparsity_pct"] for r in rows]
        corr = [r["corr_abs_R_distance_from_boundary"] for r in rows
                 if not np.isnan(r["corr_abs_R_distance_from_boundary"])]
        return {
            "cohort": cohort,
            "n_patients": len(rows),
            "mean_R_outside_mask_mean": float(np.mean(mean_R)),
            "std_R_mean": float(np.mean(std_R)),
            "sparsity_pct_mean": float(np.mean(spar)),
            "corr_abs_R_distance_mean": float(np.mean(corr))
                if corr else float("nan"),
            "R_separation_outgrowth_vs_non_mean": float(np.mean(sep))
                if sep else float("nan"),
        }

    upenn_summary = summarise(upenn_rows, "UPENN-GBM")
    yale_summary = summarise(yale_rows, "Yale-Brain-Mets")
    print(f"  UPENN residual summary:", flush=True)
    for k, v in upenn_summary.items():
        if isinstance(v, float):
            print(f"    {k}: {v:.4f}", flush=True)
    print(f"  Yale residual summary:", flush=True)
    for k, v in yale_summary.items():
        if isinstance(v, float):
            print(f"    {k}: {v:.4f}", flush=True)

    all_residual_rows = upenn_rows + yale_rows
    if all_residual_rows:
        with OUT_CSV.open("w", newline="") as f:
            keys = list(all_residual_rows[0].keys())
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(all_residual_rows)
        print(f"  Saved {OUT_CSV}", flush=True)

    # ========================================================================
    # PART 2 — Adversarial robustness on UPENN
    # ========================================================================
    print("\n" + "=" * 60, flush=True)
    print("PART 2 — Adversarial robustness (perturbations on UPENN)",
          flush=True)
    print("=" * 60, flush=True)

    perturbations = [
        "baseline", "erode_1", "erode_2", "dilate_1", "dilate_2",
        "flip_1pct",
    ]
    pert_results = {}
    for kind in perturbations:
        print(f"  evaluating perturbation: {kind}", flush=True)
        upenn_perf = evaluate_perturbation(model, upenn_data, kind)
        yale_perf = evaluate_perturbation(model, yale_data, kind)
        pert_results[kind] = {"upenn": upenn_perf, "yale": yale_perf}
        print(f"    UPENN: cov={upenn_perf['ensemble_outgrowth_coverage_mean']*100:.2f}%  "
              f"AUC={upenn_perf['auc_mean']:.3f}  Dice={upenn_perf['dice_mean']:.3f}",
              flush=True)
        print(f"    Yale:  cov={yale_perf['ensemble_outgrowth_coverage_mean']*100:.2f}%  "
              f"AUC={yale_perf['auc_mean']:.3f}  Dice={yale_perf['dice_mean']:.3f}",
              flush=True)

    # Compute degradation deltas relative to baseline
    upenn_baseline_auc = pert_results["baseline"]["upenn"]["auc_mean"]
    yale_baseline_auc = pert_results["baseline"]["yale"]["auc_mean"]
    delta = {}
    for kind in perturbations:
        if kind == "baseline":
            continue
        delta[kind] = {
            "upenn_delta_auc": pert_results[kind]["upenn"]["auc_mean"]
                                  - upenn_baseline_auc,
            "yale_delta_auc": pert_results[kind]["yale"]["auc_mean"]
                                  - yale_baseline_auc,
        }
    print("\n  Per-perturbation AUC degradation relative to baseline:",
          flush=True)
    for k, d in delta.items():
        print(f"    {k:15s}  UPENN dAUC = {d['upenn_delta_auc']:+.4f}  "
              f"Yale dAUC = {d['yale_delta_auc']:+.4f}", flush=True)

    out = {
        "version": "v188",
        "experiment": ("Mechanistic interpretability (residual analysis) "
                       "+ adversarial robustness"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "interpretability": {
            "upenn_summary": upenn_summary,
            "yale_summary": yale_summary,
        },
        "robustness": {
            "perturbations": list(perturbations),
            "results_by_perturbation": pert_results,
            "delta_auc_vs_baseline": delta,
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
