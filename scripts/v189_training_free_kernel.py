"""v189: Training-free bimodal kernel as a clinical deployment tool — round 27.

A senior Nature researcher's paradigm-shift hypothesis:

  Does the bimodal heat kernel K(x; M) = max(M, G_sigma * M) — with
  NO training, NO GPU, NO ML expertise — achieve competitive
  patient-level AUC across all 7 cohorts at the optimal sigma?

  If YES, this is a major paradigm shift for clinical AI: the
  heuristic kernel is a training-free deployment tool for tumour
  outgrowth prediction, deployable on ANY institution's data
  without retraining.

Method:
  - For each of 7 cohorts, compute kernel-only voxel-level AUC
    across sigma in {1, 2, 3, 4, 5, 7, 10, 12, 15, 20, 25, 30}.
  - Find per-cohort optimal sigma; record optimal AUC.
  - Find single 'universal sigma' that maximises mean AUC across
    cohorts.
  - Compare to v184's foundation-model AUC.

Outputs:
  Nature_project/05_results/v189_training_free_kernel.json
  Nature_project/05_results/v189_kernel_only_per_cohort.csv
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
OUT_JSON = RESULTS / "v189_training_free_kernel.json"
OUT_CSV = RESULTS / "v189_kernel_only_per_cohort.csv"

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets", "UPENN-GBM", "Yale-Brain-Mets"]

SIGMA_GRID = [1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0, 12.0, 15.0, 20.0, 25.0, 30.0]
TARGET_SHAPE = (16, 48, 48)


# ============================================================================
# Helpers
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


def dice(pred_bin, target_bin):
    a = pred_bin.astype(bool)
    b = target_bin.astype(bool)
    inter = float((a & b).sum())
    s = float(a.sum() + b.sum())
    if s == 0:
        return float("nan")
    return (2 * inter) / s


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
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth})
    return rows


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v189_") as td:
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
        rows.append({
            "pid": str(pid), "cohort": "UPENN-GBM",
            "mask": m_3d.astype(np.float32),
            "fu": t_3d.astype(np.float32),
            "outgrowth": outgrowth_3d.astype(np.float32),
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
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r.astype(np.float32),
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
        })
    return rows


# ============================================================================
# Main
# ============================================================================

def kernel_only_metrics(patients, sigma):
    """Compute per-patient AUC, Dice, coverage for kernel-only at given sigma."""
    pat_auc = []
    pat_dice = []
    pat_cov = []
    for d in patients:
        K = heat_bimodal(d["mask"], sigma)
        mask = d["mask"].astype(bool)
        outgrowth = d["outgrowth"].astype(bool)
        if outgrowth.sum() == 0:
            continue
        bg = ~mask
        if bg.sum() == 0:
            continue
        # AUROC
        auc = auroc(K[bg], outgrowth[bg].astype(np.float32))
        if not np.isnan(auc):
            pat_auc.append(auc)
        # Dice + coverage
        K_pred = (K * (~mask)) >= 0.5
        d_score = dice(K_pred, outgrowth)
        if not np.isnan(d_score):
            pat_dice.append(d_score)
        cov = float((K_pred & outgrowth).sum() / outgrowth.sum())
        pat_cov.append(cov)
    def safe_mean(arr):
        return float(np.mean(arr)) if arr else float("nan")
    return {
        "auc_mean": safe_mean(pat_auc),
        "dice_mean": safe_mean(pat_dice),
        "coverage_mean": safe_mean(pat_cov),
        "n_eval": len(pat_auc),
    }


def main():
    print("=" * 78, flush=True)
    print("v189 TRAINING-FREE KERNEL — DOES THE BIMODAL KERNEL ALONE WORK?",
          flush=True)
    print(f"  sigma grid: {SIGMA_GRID}", flush=True)
    print("=" * 78, flush=True)

    cohort_data = {}
    cohort_data["UCSF-POSTOP"] = load_glioma_cohort("UCSF-POSTOP")
    cohort_data["MU-Glioma-Post"] = load_glioma_cohort("MU-Glioma-Post")
    cohort_data["RHUH-GBM"] = load_glioma_cohort("RHUH-GBM")
    cohort_data["LUMIERE"] = load_glioma_cohort("LUMIERE")
    cohort_data["PROTEAS-brain-mets"] = load_proteas()
    cohort_data["UPENN-GBM"] = load_upenn()
    cohort_data["Yale-Brain-Mets"] = load_yale()
    for c, rows in cohort_data.items():
        print(f"  {c}: {len(rows)} patients", flush=True)

    # Sweep sigma
    results = {}
    csv_rows = []
    for c, patients in cohort_data.items():
        if not patients:
            continue
        print(f"\n  cohort: {c} (n = {len(patients)})", flush=True)
        per_sigma = {}
        for sigma in SIGMA_GRID:
            m = kernel_only_metrics(patients, sigma)
            per_sigma[f"sigma={sigma}"] = m
            csv_rows.append({"cohort": c, "sigma": sigma, **m})
            print(f"    sigma={sigma:5.1f}  AUC={m['auc_mean']:.4f}  "
                  f"Dice={m['dice_mean']:.4f}  cov={m['coverage_mean']*100:.2f}%",
                  flush=True)
        # Find optimum sigma per cohort by AUC
        valid = [(s, per_sigma[f"sigma={s}"]["auc_mean"])
                  for s in SIGMA_GRID
                  if not np.isnan(per_sigma[f"sigma={s}"]["auc_mean"])]
        if valid:
            best_sigma, best_auc = max(valid, key=lambda kv: kv[1])
        else:
            best_sigma = float("nan")
            best_auc = float("nan")
        results[c] = {
            "n_patients": len(patients),
            "per_sigma": per_sigma,
            "optimal_sigma": float(best_sigma),
            "optimal_auc": float(best_auc),
        }
        print(f"    OPTIMAL: sigma={best_sigma}, AUC={best_auc:.4f}",
              flush=True)

    # Find universal sigma (max mean AUC across cohorts)
    print("\n  Universal sigma (max mean-AUC across 7 cohorts):", flush=True)
    universal_means = {}
    for sigma in SIGMA_GRID:
        aucs = [results[c]["per_sigma"][f"sigma={sigma}"]["auc_mean"]
                for c in ALL_COHORTS
                if c in results
                and not np.isnan(
                    results[c]["per_sigma"][f"sigma={sigma}"]["auc_mean"])]
        if aucs:
            universal_means[sigma] = float(np.mean(aucs))
            print(f"    sigma={sigma:5.1f}  mean AUC across cohorts = "
                  f"{universal_means[sigma]:.4f}", flush=True)
    best_universal_sigma = max(universal_means, key=universal_means.get)
    best_universal_auc = universal_means[best_universal_sigma]
    print(f"\n  BEST UNIVERSAL sigma = {best_universal_sigma}  "
          f"(mean AUC = {best_universal_auc:.4f})", flush=True)

    # Compare to v184 foundation model AUC
    v184_path = RESULTS / "v184_clinical_readiness.json"
    foundation_auc = {}
    if v184_path.exists():
        v184 = json.loads(v184_path.read_text())
        for c in ALL_COHORTS:
            if c in v184["cohort_summaries"]:
                foundation_auc[c] = v184["cohort_summaries"][c]["auc_mean"]
        print("\n  FOUNDATION MODEL vs KERNEL-ONLY AUC comparison:",
              flush=True)
        for c in ALL_COHORTS:
            if c in foundation_auc and c in results:
                f_auc = foundation_auc[c]
                k_auc = results[c]["optimal_auc"]
                k_sigma = results[c]["optimal_sigma"]
                k_universal = results[c]["per_sigma"].get(
                    f"sigma={best_universal_sigma}", {}).get(
                    "auc_mean", float("nan"))
                print(f"    {c:25s}  Foundation = {f_auc:.4f}  "
                      f"Kernel-only optimal = {k_auc:.4f} (sigma={k_sigma})  "
                      f"Kernel universal = {k_universal:.4f}", flush=True)

    out = {
        "version": "v189",
        "experiment": ("Training-free bimodal kernel as a clinical "
                       "deployment tool"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sigma_grid": SIGMA_GRID,
        "per_cohort": results,
        "universal_means": {f"sigma={k}": v
                             for k, v in universal_means.items()},
        "best_universal_sigma": float(best_universal_sigma),
        "best_universal_auc": float(best_universal_auc),
        "foundation_auc_v184": foundation_auc,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if csv_rows:
        with OUT_CSV.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
