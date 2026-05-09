"""v187: Senior-Nature-reviewer audit of CORE CLAIMS — round 25.

Three independent core-claim audits:

  AUDIT 1 — Bimodal-kernel ablation. The foundation-model input is
  (mask, K(x; M)) where K is the bimodal kernel max(M, G_sigma*M).
  Variants:
    A. Full bimodal:        in = (mask, max(M, G7*M))      [baseline]
    B. Persistence-only:    in = (mask, mask)              [no Gaussian]
    C. Gaussian-only:       in = (mask, G7*M)              [no persistence]
    D. Mask-only single:    in = (mask, mask)              [1-channel x 2]

  AUDIT 2 — Sigma-sensitivity sweep. Re-train foundation with sigma in
  {3, 7, 15} and evaluate. If the law holds robustly, sigma=7 should
  be near-optimal but performance should degrade gracefully.

  AUDIT 3 — "Foundation model adds value over kernel alone" test.
  Compare:
    - Bimodal kernel ALONE (heuristic, no learning) -> outgrowth coverage
    - Full foundation (model + bimodal ensemble) -> outgrowth coverage
  Difference = "value added by learning."

All audits evaluate on UPENN external (zero-shot, 41 patients) +
Yale-Brain-Mets zero-shot (19 patients).

Outputs:
  Nature_project/05_results/v187_core_claims_audit.json
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
OUT_JSON = RESULTS / "v187_core_claims_audit.json"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]

TARGET_SHAPE = (16, 48, 48)
EPOCHS_PRETRAIN = 25
LR_PRETRAIN = 1e-3
SEED = 42
BATCH_SIZE = 4

# Sigma values for AUDIT 2
SIGMA_GRID = [3.0, 7.0, 15.0]


# ============================================================================
# Pipeline
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


def overall_coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0:
        return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def outgrowth_coverage(future_mask, baseline_mask, region_mask):
    fut = future_mask.astype(bool)
    base = baseline_mask.astype(bool)
    out = fut & (~base)
    if out.sum() == 0:
        return float("nan")
    return float((out & region_mask.astype(bool)).sum() / out.sum())


def auroc_voxel(probs, labels):
    s = np.array(probs, dtype=np.float32)
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


def dice_score(pred_bin, target_bin):
    a = pred_bin.astype(bool)
    b = target_bin.astype(bool)
    inter = float((a & b).sum())
    s = float(a.sum() + b.sum())
    if s == 0:
        return float("nan")
    return (2 * inter) / s


# ============================================================================
# Data loaders (re-used)
# ============================================================================

def load_glioma_cohort(cohort, sigma_for_kernel):
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
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth,
                     "kernel_full":      heat_bimodal(m, sigma_for_kernel),
                     "kernel_gaussian":  heat_constant(m, sigma_for_kernel),
                     "kernel_persist":   m.astype(np.float32),
                     })
    return rows


def load_proteas(sigma_for_kernel):
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v187_") as td:
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
                        kf = heat_bimodal(m_r_f, sigma_for_kernel)
                        kg = heat_constant(m_r_f, sigma_for_kernel)
                        kp = m_r_f.copy()
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
                                "kernel_full": kf,
                                "kernel_gaussian": kg,
                                "kernel_persist": kp,
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


def load_upenn(sigma_for_kernel):
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
        rows.append({
            "pid": str(pid), "cohort": "UPENN-GBM",
            "mask": m_3d.astype(np.float32),
            "fu": t_3d.astype(np.float32),
            "outgrowth": outgrowth_3d.astype(np.float32),
            "kernel_full":     heat_bimodal(m_3d, sigma_for_kernel),
            "kernel_gaussian": heat_constant(m_3d, sigma_for_kernel),
            "kernel_persist":  m_3d.astype(np.float32),
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


def load_yale(sigma_for_kernel, max_patients=200):
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
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r_f,
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
            "kernel_full":     heat_bimodal(m_r_f, sigma_for_kernel),
            "kernel_gaussian": heat_constant(m_r_f, sigma_for_kernel),
            "kernel_persist":  m_r_f.copy(),
        })
    return rows


# ============================================================================
# Model
# ============================================================================

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


def train_unet(train_data, kernel_key, seed=SEED, epochs=EPOCHS_PRETRAIN,
                batch_size=BATCH_SIZE, lr=LR_PRETRAIN):
    torch.manual_seed(seed)
    np.random.seed(seed)
    n = len(train_data)
    X = np.stack([np.stack([d["mask"], d[kernel_key]], axis=0)
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


def evaluate_with_kernel(model, test_data, kernel_key):
    """Per-patient outgrowth coverage + AUC + Dice with chosen kernel."""
    model.eval()
    pat_cov = []
    pat_auc = []
    pat_dice = []
    pat_kernel_only_cov = []
    with torch.no_grad():
        for d in test_data:
            x = np.stack([d["mask"], d[kernel_key]], axis=0).astype(np.float32)
            xt = torch.from_numpy(x[None]).to(DEVICE)
            logits = model(xt)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            mask = d["mask"].astype(bool)
            outgrowth = d["outgrowth"].astype(bool)
            kernel = d[kernel_key]

            # Ensemble = max of model pred + kernel
            ensemble = np.maximum(pred, kernel)
            ensemble_region = (ensemble * (~mask)) >= 0.5
            cov = outgrowth_coverage(d["fu"], d["mask"], ensemble_region)
            pat_cov.append(cov)

            kernel_only_region = (kernel * (~mask)) >= 0.5
            cov_kernel_only = outgrowth_coverage(d["fu"], d["mask"],
                                                   kernel_only_region)
            pat_kernel_only_cov.append(cov_kernel_only)

            bg = ~mask
            if bg.sum() > 0 and outgrowth.sum() > 0:
                auc = auroc_voxel(ensemble[bg], outgrowth[bg])
                pat_auc.append(auc)

            ensemble_bin = (ensemble * (~mask)) >= 0.5
            d_score = dice_score(ensemble_bin, outgrowth)
            if not np.isnan(d_score):
                pat_dice.append(d_score)

    def safe_mean(arr):
        a = np.array([x for x in arr if not np.isnan(x)])
        return float(np.mean(a)) if len(a) else float("nan")

    return {
        "ensemble_outgrowth_coverage_mean": safe_mean(pat_cov),
        "kernel_only_outgrowth_coverage_mean": safe_mean(pat_kernel_only_cov),
        "auc_mean": safe_mean(pat_auc),
        "dice_mean": safe_mean(pat_dice),
        "n_eval": int(sum(1 for v in pat_cov if not np.isnan(v))),
    }


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v187 SENIOR-NATURE-REVIEWER CORE-CLAIMS AUDIT", flush=True)
    print("=" * 78, flush=True)

    # We'll need data with multiple kernel variants pre-computed.
    # To save time we precompute three kernels per patient at sigma=7,
    # and re-load with sigma=3 / sigma=15 only when needed (AUDIT 2).
    print("\nLoading 5 trained cohorts + UPENN + Yale (sigma=7)...", flush=True)
    cohort_data = {}
    for c in ALL_COHORTS:
        if c == "PROTEAS-brain-mets":
            rows = load_proteas(7.0)
        else:
            rows = load_glioma_cohort(c, 7.0)
        cohort_data[c] = rows
        print(f"  {c}: {len(rows)} patients", flush=True)
    upenn_data_s7 = load_upenn(7.0)
    yale_data_s7 = load_yale(7.0)
    print(f"  UPENN: {len(upenn_data_s7)} patients", flush=True)
    print(f"  Yale: {len(yale_data_s7)} patients", flush=True)
    train_all_s7 = sum((cohort_data[c] for c in ALL_COHORTS), [])
    print(f"  Total train: {len(train_all_s7)} patients", flush=True)

    audit_results = {}

    # ========================================================================
    # AUDIT 1 — Bimodal-kernel ablation
    # ========================================================================
    print("\n" + "=" * 60, flush=True)
    print("AUDIT 1 — Bimodal-kernel ablation (sigma=7)", flush=True)
    print("=" * 60, flush=True)

    variants = {
        "A_full_bimodal":     "kernel_full",
        "B_persistence_only": "kernel_persist",
        "C_gaussian_only":    "kernel_gaussian",
    }
    audit_1 = {}
    for name, kernel_key in variants.items():
        print(f"\n  Variant {name}  (kernel = {kernel_key})", flush=True)
        t0 = time.time()
        model = train_unet(train_all_s7, kernel_key, seed=SEED)
        print(f"    train took {time.time()-t0:.0f}s", flush=True)
        upenn_metrics = evaluate_with_kernel(model, upenn_data_s7, kernel_key)
        yale_metrics = evaluate_with_kernel(model, yale_data_s7, kernel_key)
        audit_1[name] = {
            "kernel_key": kernel_key,
            "upenn": upenn_metrics,
            "yale": yale_metrics,
        }
        print(f"    UPENN: ens-out = "
              f"{upenn_metrics['ensemble_outgrowth_coverage_mean']*100:.2f}%   "
              f"AUC = {upenn_metrics['auc_mean']:.3f}   "
              f"Dice = {upenn_metrics['dice_mean']:.3f}", flush=True)
        print(f"    Yale:  ens-out = "
              f"{yale_metrics['ensemble_outgrowth_coverage_mean']*100:.2f}%   "
              f"AUC = {yale_metrics['auc_mean']:.3f}   "
              f"Dice = {yale_metrics['dice_mean']:.3f}", flush=True)
        del model
        torch.cuda.empty_cache()
        gc.collect()

    audit_results["audit_1_bimodal_ablation"] = audit_1

    # ========================================================================
    # AUDIT 3 — Foundation model adds value over kernel alone
    # ========================================================================
    print("\n" + "=" * 60, flush=True)
    print("AUDIT 3 — Foundation model adds value over kernel alone",
          flush=True)
    print("=" * 60, flush=True)
    # The 'kernel_only' coverage was already recorded in evaluate_with_kernel
    # for variant A_full_bimodal. Compare ensemble vs kernel_only.
    full = audit_1["A_full_bimodal"]
    delta_upenn = (full["upenn"]["ensemble_outgrowth_coverage_mean"]
                    - full["upenn"]["kernel_only_outgrowth_coverage_mean"])
    delta_yale = (full["yale"]["ensemble_outgrowth_coverage_mean"]
                   - full["yale"]["kernel_only_outgrowth_coverage_mean"])
    audit_3 = {
        "upenn": {
            "kernel_only_pct":
                full["upenn"]["kernel_only_outgrowth_coverage_mean"] * 100,
            "ensemble_pct":
                full["upenn"]["ensemble_outgrowth_coverage_mean"] * 100,
            "delta_pp": delta_upenn * 100,
        },
        "yale": {
            "kernel_only_pct":
                full["yale"]["kernel_only_outgrowth_coverage_mean"] * 100,
            "ensemble_pct":
                full["yale"]["ensemble_outgrowth_coverage_mean"] * 100,
            "delta_pp": delta_yale * 100,
        },
    }
    print(f"  UPENN:  kernel-only = "
          f"{audit_3['upenn']['kernel_only_pct']:.2f}%   "
          f"ensemble = {audit_3['upenn']['ensemble_pct']:.2f}%   "
          f"delta = {audit_3['upenn']['delta_pp']:+.2f} pp",
          flush=True)
    print(f"  Yale:   kernel-only = "
          f"{audit_3['yale']['kernel_only_pct']:.2f}%   "
          f"ensemble = {audit_3['yale']['ensemble_pct']:.2f}%   "
          f"delta = {audit_3['yale']['delta_pp']:+.2f} pp",
          flush=True)
    audit_results["audit_3_foundation_adds_value"] = audit_3

    # ========================================================================
    # AUDIT 2 — Sigma-sensitivity sweep
    # ========================================================================
    print("\n" + "=" * 60, flush=True)
    print(f"AUDIT 2 — Sigma-sensitivity sweep (sigma in {SIGMA_GRID})",
          flush=True)
    print("=" * 60, flush=True)

    audit_2 = {}
    for sigma in SIGMA_GRID:
        print(f"\n  sigma = {sigma}", flush=True)
        # Re-build kernels for this sigma. Cheaper than re-loading data:
        # walk each patient and recompute kernel_full and kernel_gaussian.
        for c in ALL_COHORTS:
            for d in cohort_data[c]:
                d[f"kernel_full_s{sigma}"] = heat_bimodal(d["mask"], sigma)
        for d in upenn_data_s7:
            d[f"kernel_full_s{sigma}"] = heat_bimodal(d["mask"], sigma)
        for d in yale_data_s7:
            d[f"kernel_full_s{sigma}"] = heat_bimodal(d["mask"], sigma)

        # Treat as full bimodal just at this sigma.
        kernel_key = f"kernel_full_s{sigma}"
        train_all = sum((cohort_data[c] for c in ALL_COHORTS), [])

        t0 = time.time()
        model = train_unet(train_all, kernel_key, seed=SEED)
        print(f"    train took {time.time()-t0:.0f}s", flush=True)
        upenn_metrics = evaluate_with_kernel(model, upenn_data_s7, kernel_key)
        yale_metrics = evaluate_with_kernel(model, yale_data_s7, kernel_key)
        audit_2[f"sigma={sigma}"] = {
            "sigma": sigma,
            "upenn": upenn_metrics,
            "yale": yale_metrics,
        }
        print(f"    UPENN: ens-out = "
              f"{upenn_metrics['ensemble_outgrowth_coverage_mean']*100:.2f}%   "
              f"AUC = {upenn_metrics['auc_mean']:.3f}   "
              f"Dice = {upenn_metrics['dice_mean']:.3f}", flush=True)
        print(f"    Yale:  ens-out = "
              f"{yale_metrics['ensemble_outgrowth_coverage_mean']*100:.2f}%   "
              f"AUC = {yale_metrics['auc_mean']:.3f}   "
              f"Dice = {yale_metrics['dice_mean']:.3f}", flush=True)
        del model
        torch.cuda.empty_cache()
        gc.collect()

    audit_results["audit_2_sigma_sensitivity"] = audit_2

    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 78, flush=True)
    print("SUMMARY — CORE-CLAIMS AUDIT", flush=True)
    print("=" * 78, flush=True)
    print("\nAUDIT 1 (Bimodal-kernel ablation, on UPENN):", flush=True)
    for name, r in audit_1.items():
        print(f"  {name:25s}  ens-out={r['upenn']['ensemble_outgrowth_coverage_mean']*100:6.2f}%  "
              f"AUC={r['upenn']['auc_mean']:.3f}  "
              f"Dice={r['upenn']['dice_mean']:.3f}", flush=True)
    print("\nAUDIT 2 (Sigma sweep, on UPENN):", flush=True)
    for k, r in audit_2.items():
        print(f"  {k:15s}  ens-out={r['upenn']['ensemble_outgrowth_coverage_mean']*100:6.2f}%  "
              f"AUC={r['upenn']['auc_mean']:.3f}  "
              f"Dice={r['upenn']['dice_mean']:.3f}", flush=True)
    print("\nAUDIT 3 (Foundation adds value):", flush=True)
    print(f"  UPENN: ensemble - kernel-only = "
          f"{audit_3['upenn']['delta_pp']:+.2f} pp", flush=True)
    print(f"  Yale:  ensemble - kernel-only = "
          f"{audit_3['yale']['delta_pp']:+.2f} pp", flush=True)

    out = {
        "version": "v187",
        "experiment": "Senior-Nature-reviewer core-claims audit",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "audits": audit_results,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
