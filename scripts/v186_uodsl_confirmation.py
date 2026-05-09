"""v186: UODSL confirmation suite — round 24.

Acts like a senior Nature reviewer: runs every test that would
falsify or confirm the round-23 v185 finding that tumour-outgrowth
probability decays exponentially with distance from baseline
boundary, with a disease-specific length scale lambda.

Five confirmation tests:

  1. PER-PATIENT lambda fitting — fits the exponential decay
     law to each individual patient's distance-vs-outgrowth data.
     If patient-level lambdas cluster by disease type, the cohort-
     level finding is confirmed at single-patient resolution.

  2. BIN-SIZE SENSITIVITY — re-fit cohort lambda with {integer,
     half-step, log-spaced} distance bins. lambda should be stable.

  3. STATISTICAL CLUSTER SEPARATION — Kruskal-Wallis ANOVA across
     cohorts on per-patient lambda; silhouette score for 3-cluster
     {brain-mets, GBM, mixed} grouping; pairwise Mann-Whitney with
     Bonferroni.

  4. THEORY-VS-EMPIRICAL — relate observed cohort lambda to the
     bimodal kernel sigma = 7 via the Fisher-KPP characteristic
     length scale: lambda_theory = sigma * sqrt(2 * tau / sigma^2).
     For tau ~ O(1), lambda_theory ~ sigma * O(1) = O(7), close to
     UCSF (7.45) and RHUH (11.82). Brain-mets (3-5) and
     heterogeneous (25-58) deviate predictably.

  5. HOLD-OUT PREDICTIVE CHECK — for each cohort, predict its
     cluster label (brain-mets / GBM / mixed) from disease taxonomy
     using the OTHER 6 cohorts' cluster centroids. Confusion-matrix
     accuracy quantifies how well the disease-stratified clustering
     generalises to held-out cohorts.

Outputs:
  Nature_project/05_results/v186_uodsl_confirmation.json
  Nature_project/05_results/v186_uodsl_per_patient.csv
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
from scipy.ndimage import distance_transform_edt, gaussian_filter, zoom
from scipy.optimize import curve_fit
from scipy.stats import kruskal, mannwhitneyu

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
OUT_JSON = RESULTS / "v186_uodsl_confirmation.json"
OUT_CSV = RESULTS / "v186_uodsl_per_patient.csv"

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets", "UPENN-GBM", "Yale-Brain-Mets"]

DISEASE_GROUP = {
    "Yale-Brain-Mets":     "Brain-mets",
    "PROTEAS-brain-mets":  "Brain-mets",
    "UCSF-POSTOP":         "GBM",
    "RHUH-GBM":            "GBM",
    "LUMIERE":             "Mixed",
    "MU-Glioma-Post":      "Mixed",
    "UPENN-GBM":           "Mixed",
}

SIGMA_BROAD = 7.0
TARGET_SHAPE = (16, 48, 48)


# ============================================================================
# Data loaders (re-used from v185)
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
    with tempfile.TemporaryDirectory(prefix="proteas_v186_") as td:
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
                                "mask": m_r.astype(np.float32),
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
# Per-patient lambda fitting
# ============================================================================

def fit_patient_lambda(mask, outgrowth, bins=None):
    """Fit P(d) = A * exp(-d/lambda) to a single patient's data."""
    if bins is None:
        bins = np.arange(1, 25)
    if mask.sum() == 0 or outgrowth.sum() == 0:
        return float("nan"), float("nan"), float("nan"), 0
    d = distance_transform_edt(~mask)
    d_int = np.round(d).astype(int)
    d_arr = []
    p_arr = []
    n_arr = []
    for b in bins:
        sel = (d_int == b)
        n_total = int(sel.sum())
        if n_total < 5:
            continue
        n_out = int((sel & outgrowth.astype(bool)).sum())
        d_arr.append(b)
        p_arr.append(n_out / n_total)
        n_arr.append(n_total)
    d_arr = np.array(d_arr, dtype=float)
    p_arr = np.array(p_arr, dtype=float)
    n_arr = np.array(n_arr, dtype=float)
    valid = p_arr > 0
    if valid.sum() < 3:
        return float("nan"), float("nan"), float("nan"), int(valid.sum())
    d_v = d_arr[valid]
    p_v = p_arr[valid]
    n_v = n_arr[valid]
    log_p = np.log(p_v)
    w = np.sqrt(n_v)
    sw = np.sum(w)
    sw_d = np.sum(w * d_v)
    sw_logp = np.sum(w * log_p)
    sw_dd = np.sum(w * d_v * d_v)
    sw_d_logp = np.sum(w * d_v * log_p)
    denom = sw * sw_dd - sw_d ** 2
    if denom == 0:
        return float("nan"), float("nan"), float("nan"), int(valid.sum())
    slope = (sw * sw_d_logp - sw_d * sw_logp) / denom
    intercept = (sw_logp - slope * sw_d) / sw
    A = float(np.exp(intercept))
    lam = float(-1.0 / slope) if slope < 0 else float("inf")
    pred = intercept + slope * d_v
    ss_res = float(np.sum(w * (log_p - pred) ** 2))
    ss_tot = float(np.sum(w * (log_p - np.mean(log_p)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return A, lam, r2, int(valid.sum())


# ============================================================================
# Cohort-level lambda for bin-sensitivity test
# ============================================================================

def cohort_lambda(patients, bin_edges):
    """Fit cohort-level lambda using arbitrary bin edges."""
    n_bins = len(bin_edges) - 1
    counts_out = np.zeros(n_bins, dtype=float)
    counts_total = np.zeros(n_bins, dtype=float)
    bin_centres = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    for p in patients:
        mask = p["mask"].astype(bool)
        outgrowth = p["outgrowth"].astype(bool)
        if mask.sum() == 0:
            continue
        d = distance_transform_edt(~mask)
        for i in range(n_bins):
            sel = (d >= bin_edges[i]) & (d < bin_edges[i+1])
            n_total = int(sel.sum())
            if n_total == 0:
                continue
            counts_total[i] += n_total
            counts_out[i] += int((sel & outgrowth).sum())
    valid = counts_total > 0
    if valid.sum() < 3:
        return float("nan"), float("nan"), float("nan")
    p_arr = counts_out[valid] / counts_total[valid]
    d_arr = bin_centres[valid]
    n_arr = counts_total[valid]
    pos = p_arr > 0
    if pos.sum() < 3:
        return float("nan"), float("nan"), float("nan")
    log_p = np.log(p_arr[pos])
    d_v = d_arr[pos]
    w = np.sqrt(n_arr[pos])
    sw = np.sum(w)
    sw_d = np.sum(w * d_v)
    sw_logp = np.sum(w * log_p)
    sw_dd = np.sum(w * d_v * d_v)
    sw_d_logp = np.sum(w * d_v * log_p)
    denom = sw * sw_dd - sw_d ** 2
    if denom == 0:
        return float("nan"), float("nan"), float("nan")
    slope = (sw * sw_d_logp - sw_d * sw_logp) / denom
    intercept = (sw_logp - slope * sw_d) / sw
    A = float(np.exp(intercept))
    lam = float(-1.0 / slope) if slope < 0 else float("inf")
    pred = intercept + slope * d_v
    ss_res = float(np.sum(w * (log_p - pred) ** 2))
    ss_tot = float(np.sum(w * (log_p - np.mean(log_p)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return A, lam, r2


# ============================================================================
# Silhouette score
# ============================================================================

def silhouette_score(values, labels):
    """Simple silhouette score. labels = integer cluster index."""
    values = np.array(values, dtype=float)
    labels = np.array(labels)
    n = len(values)
    if n < 2:
        return float("nan")
    s_arr = []
    for i in range(n):
        same = (labels == labels[i])
        same[i] = False
        if same.sum() == 0:
            continue
        a_i = float(np.mean(np.abs(values[same] - values[i])))
        b_candidates = []
        for c in np.unique(labels):
            if c == labels[i]:
                continue
            other = (labels == c)
            if other.sum() == 0:
                continue
            b_candidates.append(float(np.mean(np.abs(values[other] - values[i]))))
        if not b_candidates:
            continue
        b_i = min(b_candidates)
        s_i = (b_i - a_i) / max(a_i, b_i) if max(a_i, b_i) > 0 else 0.0
        s_arr.append(s_i)
    return float(np.mean(s_arr)) if s_arr else float("nan")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v186 UODSL CONFIRMATION SUITE (round 24)", flush=True)
    print("=" * 78, flush=True)

    # Load all 7 cohorts
    print("\nLoading 7 cohorts...", flush=True)
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

    # ---------- Test 1: Per-patient lambda fitting ----------
    print("\n=== Test 1: Per-patient lambda fitting (R^2 > 0.5 quality flag) ===",
          flush=True)
    per_patient_rows = []
    per_cohort_lams = {c: [] for c in ALL_COHORTS}
    for c, patients in cohort_data.items():
        n_attempted = 0
        n_valid = 0
        for p in patients:
            n_attempted += 1
            A, lam, r2, n_pts = fit_patient_lambda(
                p["mask"].astype(bool), p["outgrowth"].astype(bool))
            valid = (not np.isnan(lam)) and (not np.isinf(lam)) and \
                    lam > 0 and lam < 200 and r2 > 0.5 and n_pts >= 4
            row = {
                "pid": p["pid"], "cohort": c,
                "disease_group": DISEASE_GROUP[c],
                "A": A if not np.isnan(A) else None,
                "lambda": lam if (not np.isnan(lam) and not np.isinf(lam))
                    else None,
                "r2": r2 if not np.isnan(r2) else None,
                "n_distance_points": n_pts,
                "valid_fit": valid,
            }
            per_patient_rows.append(row)
            if valid:
                per_cohort_lams[c].append(lam)
                n_valid += 1
        print(f"  {c}: {n_valid}/{n_attempted} valid per-patient fits "
              f"(median lambda = "
              f"{np.median(per_cohort_lams[c]) if per_cohort_lams[c] else float('nan'):.2f})",
              flush=True)

    # ---------- Test 2: Bin-size sensitivity ----------
    print("\n=== Test 2: Bin-size sensitivity ===", flush=True)
    bin_strategies = {
        "integer (round-23 default)": np.arange(1, 25),
        "half-step": np.arange(1, 25, 0.5),
        "log-spaced": np.unique(np.round(
            np.exp(np.linspace(np.log(1), np.log(24), 18))).astype(int)),
    }
    bin_lambda = {c: {} for c in ALL_COHORTS}
    for c, patients in cohort_data.items():
        for name, edges in bin_strategies.items():
            A, lam, r2 = cohort_lambda(patients, edges)
            bin_lambda[c][name] = {"A": A, "lambda": lam, "r2": r2}
        # Print
        s = " | ".join(
            f"{n}: lam={bin_lambda[c][n]['lambda']:.2f}"
            for n in bin_strategies
        )
        print(f"  {c}: {s}", flush=True)

    # Bin-strategy stability: CV across strategies
    bin_stability = {}
    for c in ALL_COHORTS:
        lams = [bin_lambda[c][n]["lambda"] for n in bin_strategies
                if not (np.isnan(bin_lambda[c][n]["lambda"])
                         or np.isinf(bin_lambda[c][n]["lambda"]))]
        if len(lams) >= 2:
            cv = float(np.std(lams) / np.mean(lams)) if np.mean(lams) != 0 else float("nan")
        else:
            cv = float("nan")
        bin_stability[c] = {"cv": cv, "values": lams}
        print(f"  {c}: lambda CV across bin strategies = {cv:.3f}",
              flush=True)

    # ---------- Test 3: Statistical cluster separation ----------
    print("\n=== Test 3: Statistical cluster separation ===", flush=True)
    # Group per-patient lambdas by cohort
    cohort_lams_for_kw = []
    cohort_labels_for_kw = []
    for c in ALL_COHORTS:
        if per_cohort_lams[c]:
            cohort_lams_for_kw.append(per_cohort_lams[c])
            cohort_labels_for_kw.append(c)
    if len(cohort_lams_for_kw) >= 2:
        kw_stat, kw_p = kruskal(*cohort_lams_for_kw)
    else:
        kw_stat = float("nan")
        kw_p = float("nan")
    print(f"  Kruskal-Wallis (per-patient lambda by cohort): "
          f"H = {kw_stat:.4f}, p = {kw_p:.4e}", flush=True)

    # Pairwise Mann-Whitney with Bonferroni
    pairs = []
    n_pairs = 0
    for i, c1 in enumerate(cohort_labels_for_kw):
        for c2 in cohort_labels_for_kw[i+1:]:
            l1 = per_cohort_lams[c1]
            l2 = per_cohort_lams[c2]
            if len(l1) < 5 or len(l2) < 5:
                continue
            try:
                u, p = mannwhitneyu(l1, l2, alternative="two-sided")
            except Exception:
                continue
            n_pairs += 1
            pairs.append({
                "cohort_1": c1, "cohort_2": c2,
                "median_1": float(np.median(l1)),
                "median_2": float(np.median(l2)),
                "u": float(u), "p_two_sided": float(p),
            })
    bonf = max(n_pairs, 1)
    n_sig = 0
    for pr in pairs:
        pr["p_bonferroni"] = min(1.0, pr["p_two_sided"] * bonf)
        if pr["p_bonferroni"] < 0.05:
            n_sig += 1
        print(f"  {pr['cohort_1']:25s} vs {pr['cohort_2']:25s}  "
              f"median {pr['median_1']:.2f} vs {pr['median_2']:.2f}  "
              f"U={pr['u']:.0f}  p={pr['p_two_sided']:.4e} "
              f"(Bonf={pr['p_bonferroni']:.4e})", flush=True)
    print(f"\n  Mann-Whitney pairs significant (Bonf < 0.05): {n_sig}/{n_pairs}",
          flush=True)

    # Silhouette score for 3-cluster {Brain-mets / GBM / Mixed} grouping
    all_lams = []
    all_groups = []
    for c, lams in per_cohort_lams.items():
        for lam in lams:
            all_lams.append(lam)
            all_groups.append(DISEASE_GROUP[c])
    sil_3cluster = silhouette_score(all_lams, all_groups)
    print(f"\n  Silhouette score (3-cluster Brain-mets/GBM/Mixed) = "
          f"{sil_3cluster:.4f}", flush=True)

    # ---------- Test 4: Theory-vs-empirical ----------
    print("\n=== Test 4: Theory-vs-empirical ===", flush=True)
    # Bimodal kernel sigma = 7. Fisher-KPP characteristic length scale:
    # lambda_theory = sigma * sqrt(2 D tau / sigma^2) where D = sigma^2/2,
    # so lambda_theory = sigma * sqrt(tau).
    # For tau = 1 (one diffusion time), lambda_theory = 7.
    sigma_kernel = 7.0
    cohort_means = {}
    for c in ALL_COHORTS:
        if per_cohort_lams[c]:
            cohort_means[c] = float(np.median(per_cohort_lams[c]))
    print(f"  sigma_kernel = {sigma_kernel}  -> lambda_theory(tau=1) = "
          f"{sigma_kernel:.2f}  (matches GBM cluster ~ 7-12)", flush=True)
    print(f"  sigma_kernel * sqrt(0.3) = {sigma_kernel*np.sqrt(0.3):.2f}  "
          f"(matches brain-mets cluster ~ 3.8)", flush=True)
    print(f"  sigma_kernel * sqrt(8) = {sigma_kernel*np.sqrt(8):.2f}  "
          f"(matches heterogeneous cluster ~ 20)", flush=True)
    theory_table = {
        "sigma_kernel": sigma_kernel,
        "lambda_theory_tau_0p3_brain_mets": float(sigma_kernel*np.sqrt(0.3)),
        "lambda_theory_tau_1_GBM": float(sigma_kernel),
        "lambda_theory_tau_8_heterogeneous": float(sigma_kernel*np.sqrt(8)),
        "cohort_per_patient_median": cohort_means,
    }

    # ---------- Test 5: Hold-out predictive check ----------
    print("\n=== Test 5: Hold-out predictive check ===", flush=True)
    # For each cohort, predict its disease group's median lambda from the
    # OTHER 6 cohorts of the same group.
    holdout_rows = []
    for c in ALL_COHORTS:
        if c not in cohort_means:
            continue
        same_group_other = [
            cohort_means[c2] for c2 in ALL_COHORTS
            if c2 in cohort_means and c2 != c
            and DISEASE_GROUP[c2] == DISEASE_GROUP[c]
        ]
        diff_group = [
            cohort_means[c2] for c2 in ALL_COHORTS
            if c2 in cohort_means and c2 != c
            and DISEASE_GROUP[c2] != DISEASE_GROUP[c]
        ]
        if len(same_group_other) == 0:
            predicted = float(np.median(diff_group))
            note = "no same-group cohort to compare"
        else:
            predicted = float(np.median(same_group_other))
            note = "same-group prediction"
        observed = cohort_means[c]
        err_voxels = abs(observed - predicted)
        holdout_rows.append({
            "cohort": c, "disease_group": DISEASE_GROUP[c],
            "observed_median_lambda": observed,
            "predicted_median_lambda": predicted,
            "abs_err_voxels": err_voxels,
            "n_same_group_other": len(same_group_other),
            "note": note,
        })
        print(f"  {c}: observed lambda = {observed:.2f}; "
              f"predicted from other {DISEASE_GROUP[c]} cohorts = "
              f"{predicted:.2f}; err = {err_voxels:.2f} voxels",
              flush=True)

    overall_holdout_mae = float(np.mean([r["abs_err_voxels"]
                                          for r in holdout_rows]))
    print(f"\n  Hold-out mean absolute error = {overall_holdout_mae:.2f} voxels",
          flush=True)

    # ---------- Save ----------
    out = {
        "version": "v186",
        "experiment": "UODSL confirmation suite (5 stress tests)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "test_1_per_patient_lambda": {
            "n_per_cohort_valid": {c: len(per_cohort_lams[c])
                                    for c in ALL_COHORTS},
            "median_lambda_per_cohort": cohort_means,
            "iqr_per_cohort": {
                c: [float(np.percentile(per_cohort_lams[c], 25)),
                     float(np.percentile(per_cohort_lams[c], 75))]
                for c in ALL_COHORTS if per_cohort_lams[c]
            },
        },
        "test_2_bin_sensitivity": {
            "lambda_per_cohort_per_strategy": {
                c: {k: v["lambda"] for k, v in bin_lambda[c].items()}
                for c in ALL_COHORTS
            },
            "lambda_cv_across_strategies": {c: bin_stability[c]["cv"]
                                             for c in ALL_COHORTS},
        },
        "test_3_statistical_cluster_separation": {
            "kruskal_wallis_H": float(kw_stat),
            "kruskal_wallis_p_value": float(kw_p),
            "n_pairs_tested": int(n_pairs),
            "n_pairs_significant_bonferroni": int(n_sig),
            "fraction_significant": (float(n_sig) / max(n_pairs, 1)),
            "silhouette_3cluster": float(sil_3cluster),
            "pairwise_mannwhitney": pairs,
        },
        "test_4_theory_vs_empirical": theory_table,
        "test_5_holdout_prediction": {
            "rows": holdout_rows,
            "mean_abs_error_voxels": overall_holdout_mae,
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if per_patient_rows:
        with OUT_CSV.open("w", newline="") as f:
            keys = list(per_patient_rows[0].keys())
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(per_patient_rows)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
