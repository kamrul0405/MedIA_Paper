"""v199: Yale longitudinal replication of round-34 λ patient-intrinsic
finding — round 37.

Senior-Nature-reviewer-driven cross-cohort replication. Round 34 v196
established that UODSL λ is patient-intrinsic in PROTEAS-brain-mets
(ICC-proxy = 0.834; intra-patient variance 0.43 vs inter-patient
2.57). The question: does this hold on a SECOND independent
multi-timepoint cohort?

Yale-Brain-Mets-Longitudinal has 1,430 timepoint folders covering
~200+ patients. Many patients have ≥3 timepoints — perfect for
cross-cohort λ-stability replication. Yale uses proxy POST-contrast
masks (different segmentation pipeline from PROTEAS ground-truth),
which adds noise but provides INDEPENDENT cohort + INDEPENDENT
segmentation method.

Method:
  - Walk Yale patient folders; collect baseline + each followup
    POST/PRE pair
  - For each timepoint, generate proxy mask via POST-PRE thresholding
  - For each patient with >=2 followups: fit UODSL λ at each
    (baseline, followup_i) pair
  - Track λ trajectories per patient
  - Compute ICC-proxy on Yale; compare to PROTEAS round 34

If Yale ICC >= 0.5 → robust cross-cohort replication.
If Yale ICC ~ 0 → patient-intrinsic claim weakens.

Outputs:
  Nature_project/05_results/v199_yale_longitudinal_lambda.json
  Nature_project/05_results/v199_yale_per_obs.csv
"""
from __future__ import annotations

import csv
import json
import time
import warnings
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import distance_transform_edt, zoom
from scipy.stats import binomtest, spearmanr

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
YALE_DIR = Path(
    r"C:\Users\kamru\Downloads\Datasets\PKG - Yale-Brain-Mets-Longitudinal"
    r"\Yale-Brain-Mets-Longitudinal"
)
OUT_JSON = RESULTS / "v199_yale_longitudinal_lambda.json"
OUT_CSV = RESULTS / "v199_yale_per_obs.csv"

TARGET_SHAPE = (16, 48, 48)
DISTANCE_BINS = np.arange(1, 25)
MAX_PATIENTS = 300


def resize_to_target(arr, target_shape):
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


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
                    mask = diff > th
                    if mask.sum() < 30:
                        th2 = np.percentile(post[brain], percentile)
                        mask = (post > th2) & brain
                    return mask
        except Exception:
            pass
    th = np.percentile(post[brain], percentile)
    return (post > th) & brain


def fit_lambda(mask, outgrowth):
    m = mask.astype(bool)
    out = outgrowth.astype(bool)
    if m.sum() == 0 or out.sum() == 0:
        return float("nan"), float("nan"), 0
    d = distance_transform_edt(~m)
    d_int = np.round(d).astype(int)
    d_arr, p_arr, n_arr = [], [], []
    for b in DISTANCE_BINS:
        sel = (d_int == b)
        if sel.sum() < 5:
            continue
        n_total = int(sel.sum())
        n_out = int((sel & out).sum())
        d_arr.append(b)
        p_arr.append(n_out / n_total)
        n_arr.append(n_total)
    d_arr = np.array(d_arr, dtype=float)
    p_arr = np.array(p_arr, dtype=float)
    n_arr = np.array(n_arr, dtype=float)
    valid = p_arr > 0
    if valid.sum() < 3:
        return float("nan"), float("nan"), int(valid.sum())
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
        return float("nan"), float("nan"), int(valid.sum())
    slope = (sw * sw_d_logp - sw_d * sw_logp) / denom
    intercept = (sw_logp - slope * sw_d) / sw
    lam = float(-1.0 / slope) if slope < 0 else float("inf")
    pred = intercept + slope * d_v
    ss_res = float(np.sum(w * (log_p - pred) ** 2))
    ss_tot = float(np.sum(w * (log_p - np.mean(log_p)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return lam, r2, int(valid.sum())


def find_yale_multi_timepoint(max_patients=MAX_PATIENTS):
    """For each Yale patient with >= 2 timepoints, return (pid, [post_paths])."""
    if not YALE_DIR.exists():
        return []
    out = []
    for p in sorted(YALE_DIR.iterdir())[:max_patients]:
        if not p.is_dir():
            continue
        timepoints = sorted(t for t in p.iterdir() if t.is_dir())
        if len(timepoints) < 2:
            continue
        post_pairs = []
        for tp in timepoints:
            post = next(tp.glob("*POST.nii.gz"), None)
            pre = next(tp.glob("*PRE.nii.gz"), None)
            if post is None:
                continue
            post_pairs.append((post, pre))
        if len(post_pairs) >= 2:
            out.append((p.name, post_pairs))
    return out


def main():
    print("=" * 78, flush=True)
    print("v199 YALE LONGITUDINAL LAMBDA REPLICATION (round 37)",
          flush=True)
    print("=" * 78, flush=True)

    print("\nDiscovering Yale multi-timepoint patients...", flush=True)
    patients = find_yale_multi_timepoint(MAX_PATIENTS)
    print(f"  Found {len(patients)} Yale patients with >= 2 timepoints "
          f"(out of {MAX_PATIENTS} max)", flush=True)

    # Process each patient: build mask at each timepoint (baseline = first)
    # then fit lambda for (baseline, followup_i) for each i >= 1
    print("\nFitting lambda per (patient, followup) using proxy masks...",
          flush=True)
    per_obs = []
    n_processed = 0
    t0 = time.time()
    for pid, pairs in patients:
        # baseline = first timepoint
        b_post, b_pre = pairs[0]
        try:
            base_mask_full = proxy_mask_from_post(b_post, b_pre)
        except Exception:
            continue
        if base_mask_full is None or base_mask_full.sum() < 50:
            continue
        # Resize baseline mask
        base_r = resize_to_target(base_mask_full.astype(np.float32),
                                       TARGET_SHAPE) > 0.5
        if base_r.sum() < 5:
            continue
        # For each follow-up timepoint
        for fu_idx, (fu_post, fu_pre) in enumerate(pairs[1:], start=1):
            try:
                fu_mask_full = proxy_mask_from_post(fu_post, fu_pre)
            except Exception:
                continue
            if fu_mask_full is None:
                continue
            if fu_mask_full.shape != base_mask_full.shape:
                continue
            if fu_mask_full.sum() < 50:
                continue
            fu_r = resize_to_target(fu_mask_full.astype(np.float32),
                                         TARGET_SHAPE) > 0.5
            if fu_r.sum() < 5:
                continue
            outgrowth = fu_r & ~base_r
            if outgrowth.sum() == 0:
                continue
            lam, r2, n_pts = fit_lambda(base_r, outgrowth)
            valid = (not np.isnan(lam)) and (not np.isinf(lam)) and \
                    lam > 0 and lam < 200 and r2 > 0.5 and n_pts >= 4
            per_obs.append({
                "pid": pid,
                "followup_index": fu_idx,
                "lambda": float(lam) if (not np.isnan(lam)
                                            and not np.isinf(lam))
                    else None,
                "r2": float(r2) if not np.isnan(r2) else None,
                "n_pts": n_pts,
                "valid": valid,
            })
        n_processed += 1
        if n_processed % 25 == 0:
            print(f"  processed {n_processed}/{len(patients)} patients "
                  f"({time.time()-t0:.0f}s)", flush=True)

    n_valid = sum(1 for r in per_obs if r["valid"])
    print(f"\n  Total observations: {len(per_obs)}", flush=True)
    print(f"  Valid lambda fits: {n_valid}", flush=True)

    # Group by patient: get patients with >=2 valid lambdas
    by_patient = {}
    for r in per_obs:
        if not r["valid"]:
            continue
        by_patient.setdefault(r["pid"], []).append(
            (r["followup_index"], r["lambda"]))
    multi = {pid: sorted(obs) for pid, obs in by_patient.items()
              if len(obs) >= 2}
    print(f"  Patients with >= 2 valid longitudinal lambda: "
          f"{len(multi)}", flush=True)

    # Print example trajectories
    for pid, obs_list in list(multi.items())[:8]:
        print(f"    {pid}: lambda(t) = {[(t, f'{l:.2f}') for t, l in obs_list]}",
              flush=True)

    # Per-patient Spearman lambda vs followup_index
    per_patient_spearman = []
    for pid, obs_list in multi.items():
        if len(obs_list) < 3:
            continue
        ts = [o[0] for o in obs_list]
        ls = [o[1] for o in obs_list]
        rho, p = spearmanr(ts, ls)
        per_patient_spearman.append({
            "pid": pid, "n_followups": len(obs_list),
            "rho": float(rho) if not np.isnan(rho) else None,
            "p_value": float(p) if not np.isnan(p) else None,
            "lambda_min": float(min(ls)),
            "lambda_max": float(max(ls)),
            "lambda_mean": float(np.mean(ls)),
            "lambda_std": float(np.std(ls)),
        })

    # Variance components / ICC-proxy
    intra_vars = []
    for pid, obs_list in multi.items():
        ls = np.array([o[1] for o in obs_list])
        if len(ls) >= 2:
            intra_vars.append(float(np.var(ls, ddof=1)))
    all_lams = [r["lambda"] for r in per_obs if r["valid"]]
    inter_var = float(np.var(all_lams, ddof=1)) if len(all_lams) >= 2 else float("nan")
    intra_var_mean = float(np.mean(intra_vars)) if intra_vars else float("nan")
    if inter_var > 0 and not np.isnan(intra_var_mean):
        icc_proxy = float((inter_var - intra_var_mean) / inter_var)
    else:
        icc_proxy = float("nan")

    # Sign test for trend
    sign_p = float("nan")
    if per_patient_spearman:
        rhos = [r["rho"] for r in per_patient_spearman if r["rho"] is not None]
        n_pos = sum(1 for r in rhos if r > 0)
        n_neg = sum(1 for r in rhos if r < 0)
        n_eff = n_pos + n_neg
        if n_eff > 0:
            sign_p = float(binomtest(min(n_pos, n_neg), n_eff,
                                       p=0.5).pvalue)

    print("\n=== YALE LONGITUDINAL LAMBDA SUMMARY ===", flush=True)
    print(f"  Inter-patient variance:       {inter_var:.4f}", flush=True)
    print(f"  Mean intra-patient variance:  {intra_var_mean:.4f}",
          flush=True)
    print(f"  ICC-proxy (between-patient):  {icc_proxy:.4f}", flush=True)
    print(f"  Sign test (n_patients>=3 fu): n={len(per_patient_spearman)}, "
          f"p_two_sided={sign_p:.4f}", flush=True)

    # Compare with round 34 (PROTEAS)
    proteas_icc = 0.834
    print(f"\n=== CROSS-COHORT REPLICATION COMPARISON ===", flush=True)
    print(f"  PROTEAS-brain-mets (round 34): ICC-proxy = {proteas_icc:.4f}",
          flush=True)
    print(f"  Yale-Brain-Mets (round 37):    ICC-proxy = {icc_proxy:.4f}",
          flush=True)
    if not np.isnan(icc_proxy):
        if icc_proxy >= 0.5:
            verdict = "REPLICATES (Yale ICC >= 0.5)"
        elif icc_proxy >= 0.3:
            verdict = "PARTIAL REPLICATION (0.3 <= ICC < 0.5)"
        else:
            verdict = "DOES NOT REPLICATE (ICC < 0.3)"
        print(f"  >>> {verdict} <<<", flush=True)
    else:
        verdict = "INSUFFICIENT_DATA"

    out = {
        "version": "v199",
        "experiment": ("Yale longitudinal replication of round-34 "
                       "patient-intrinsic lambda finding"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_patients_with_multi_tp": len(patients),
        "n_observations_total": len(per_obs),
        "n_valid_lambda": n_valid,
        "n_patients_with_multi_valid_lambda": len(multi),
        "n_patients_with_3plus_followups": len(per_patient_spearman),
        "variance_components": {
            "inter_patient_variance": inter_var,
            "mean_intra_patient_variance": intra_var_mean,
            "icc_proxy": icc_proxy,
        },
        "sign_test_p": sign_p,
        "comparison_with_round34_PROTEAS": {
            "proteas_icc_proxy": proteas_icc,
            "yale_icc_proxy": icc_proxy,
            "verdict": verdict,
        },
        "per_patient_spearman": per_patient_spearman,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if per_obs:
        with OUT_CSV.open("w", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=list(per_obs[0].keys()))
            w.writeheader()
            w.writerows(per_obs)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
