"""v196: Longitudinal evolution of UODSL length scale λ — round 34.

Senior-Nature-reviewer-driven flagship-extension question:

  Round 23 v185 established UODSL: P(d) = A * exp(-d / lambda)
  where lambda is a disease-specific length scale (round 24
  confirmed with multi-test suite). All previous analyses computed
  COHORT-POOLED lambda. The natural question:

    Within an individual patient with multiple followup timepoints,
    is lambda STABLE across time (patient-intrinsic biology) or
    EVOLVING (treatment / tumour adaptation / clinical course)?

  PROTEAS-brain-mets has ~45 patients each with multiple followups
  and GROUND-TRUTH segmentations — ideal for this longitudinal test.

Method:
  For each PROTEAS patient with >= 2 followup timepoints:
    For each followup_i (baseline -> fu_i):
      Compute outgrowth = fu_mask AND NOT baseline_mask
      Fit UODSL: P(d) = A * exp(-d/lambda) per patient per followup
      Record (patient_id, followup_index, lambda_i, R^2_i)
  Aggregate:
    - Per-patient lambda trajectories: lambda(t)
    - Spearman correlation lambda vs followup_index per patient
    - Intra-patient vs inter-patient variance ratio
    - Mean lambda at each followup index

Outputs:
  Nature_project/05_results/v196_uodsl_longitudinal.json
  Nature_project/05_results/v196_uodsl_longitudinal_per_obs.csv
"""
from __future__ import annotations

import csv
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
from scipy.ndimage import distance_transform_edt, zoom
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
DATA_ZIP = Path(r"C:\Users\kamru\Downloads\Datasets\PKG - PROTEAS-brain-mets-zenodo-17253793.zip")
OUT_JSON = RESULTS / "v196_uodsl_longitudinal.json"
OUT_CSV = RESULTS / "v196_uodsl_longitudinal_per_obs.csv"

TARGET_SHAPE = (16, 48, 48)
DISTANCE_BINS = np.arange(1, 25)


def resize_to_target(arr, target_shape):
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


def fit_lambda(mask, outgrowth):
    """Fit UODSL exp decay P(d) = A * exp(-d/lambda) for one patient/timepoint."""
    m = mask.astype(bool)
    out = outgrowth.astype(bool)
    if m.sum() == 0 or out.sum() == 0:
        return float("nan"), float("nan"), float("nan"), 0
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
    return float(A), lam, r2, int(valid.sum())


def load_proteas_with_followups():
    """Load PROTEAS yielding (pid, followup_index, baseline_mask, fu_mask)."""
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v196_") as td:
        work = Path(td)
        with zipfile.ZipFile(DATA_ZIP) as outer:
            entries = sorted(
                [e for e in outer.infolist() if re.fullmatch(r"P\d+[ab]?\.zip", e.filename)],
                key=lambda e: e.filename,
            )
            print(f"  PROTEAS: {len(entries)} patient zips found",
                  flush=True)
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
                        baseline_name = next(
                            (f"{seg_dir}{pid}_tumor_mask_baseline.nii.gz" for seg_dir in seg_dirs
                             if f"{seg_dir}{pid}_tumor_mask_baseline.nii.gz" in names),
                            f"{prefix}tumor segmentation/{pid}_tumor_mask_baseline.nii.gz",
                        )
                        followup_names = sorted([
                            n for n in names
                            if any(n.startswith(f"{seg_dir}{pid}_tumor_mask_fu") for seg_dir in seg_dirs)
                            and n.endswith(".nii.gz")
                        ])
                        if baseline_name not in names or len(followup_names) < 2:
                            continue
                        out_path = patient_tmp / Path(baseline_name).name
                        out_path.write_bytes(inner.read(baseline_name))
                        base_arr = np.asanyarray(nib.load(str(out_path)).dataobj).astype(np.float32)
                        base_mask = base_arr > 0
                        if base_mask.sum() == 0:
                            continue
                        m_r = resize_to_target(base_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                        for fu_idx, fu_name in enumerate(followup_names):
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
                                "pid": pid,
                                "followup_index": fu_idx,
                                "followup_name": fu_name,
                                "mask": m_r.astype(np.float32),
                                "outgrowth": outgrowth_r.astype(np.float32),
                            })
                finally:
                    shutil.rmtree(patient_tmp, ignore_errors=True)
                    try:
                        nested_path.unlink()
                    except OSError:
                        pass
                if i % 10 == 0 or i == len(entries):
                    print(f"    {i}/{len(entries)} ({time.time()-t0:.0f}s)",
                          flush=True)
    return rows


def main():
    print("=" * 78, flush=True)
    print("v196 LONGITUDINAL UODSL — round 34", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading PROTEAS with followups...", flush=True)
    obs = load_proteas_with_followups()
    print(f"  Loaded {len(obs)} (patient, followup) observations",
          flush=True)

    # Fit lambda per (patient, followup)
    print("\nFitting UODSL lambda per (patient, followup)...", flush=True)
    per_obs = []
    for o in obs:
        A, lam, r2, n_pts = fit_lambda(o["mask"], o["outgrowth"])
        valid = (not np.isnan(lam)) and (not np.isinf(lam)) and \
                lam > 0 and lam < 200 and r2 > 0.5 and n_pts >= 4
        per_obs.append({
            "pid": o["pid"], "followup_index": o["followup_index"],
            "A": A if not (np.isnan(A) or np.isinf(A)) else None,
            "lambda": lam if (not np.isnan(lam) and not np.isinf(lam))
                else None,
            "r2": r2 if not np.isnan(r2) else None,
            "n_distance_points": n_pts,
            "valid": valid,
        })
    n_valid = sum(1 for r in per_obs if r["valid"])
    print(f"  {n_valid}/{len(per_obs)} valid lambda fits", flush=True)

    # Group by patient: compute lambda(t) trajectories
    by_patient = {}
    for r in per_obs:
        if not r["valid"]:
            continue
        by_patient.setdefault(r["pid"], []).append(
            (r["followup_index"], r["lambda"]))

    # Patients with >= 2 valid lambda observations
    multi_obs_patients = {pid: sorted(obs_list)
                            for pid, obs_list in by_patient.items()
                            if len(obs_list) >= 2}
    print(f"\n  {len(multi_obs_patients)} patients with >= 2 valid "
          f"longitudinal lambda observations", flush=True)
    for pid, obs_list in list(multi_obs_patients.items())[:5]:
        print(f"    {pid}: lambda(t) = {[(t, f'{l:.2f}') for t, l in obs_list]}",
              flush=True)

    # Per-patient Spearman: lambda vs followup_index
    print("\n=== Per-patient lambda vs followup_index ===", flush=True)
    per_patient_spearman = []
    for pid, obs_list in multi_obs_patients.items():
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
    print(f"  {len(per_patient_spearman)} patients with >= 3 followups for "
          f"Spearman rho", flush=True)
    if per_patient_spearman:
        rhos = [r["rho"] for r in per_patient_spearman if r["rho"] is not None]
        ps = [r["p_value"] for r in per_patient_spearman if r["p_value"] is not None]
        print(f"  Per-patient rho distribution: mean = {np.mean(rhos):+.3f}, "
              f"median = {np.median(rhos):+.3f}", flush=True)
        n_pos = sum(1 for r in rhos if r > 0)
        n_neg = sum(1 for r in rhos if r < 0)
        print(f"  rho > 0: {n_pos}/{len(rhos)} (lambda increases); "
              f"rho < 0: {n_neg}/{len(rhos)} (lambda decreases)",
              flush=True)
        # Sign test
        n_eff = n_pos + n_neg
        from scipy.stats import binomtest
        if n_eff > 0:
            p_sign = float(binomtest(min(n_pos, n_neg), n_eff,
                                       p=0.5).pvalue)
            print(f"  Two-sided sign test p-value (no temporal trend): "
                  f"p = {p_sign:.4f}", flush=True)
        else:
            p_sign = float("nan")

    # Mean lambda at each followup index across patients
    print("\n=== Mean lambda at each followup index ===", flush=True)
    by_fu_index = {}
    for r in per_obs:
        if not r["valid"]:
            continue
        by_fu_index.setdefault(r["followup_index"], []).append(r["lambda"])
    fu_summary = {}
    for fu_idx in sorted(by_fu_index.keys()):
        lams = by_fu_index[fu_idx]
        fu_summary[fu_idx] = {
            "n": len(lams),
            "mean": float(np.mean(lams)),
            "median": float(np.median(lams)),
            "std": float(np.std(lams)),
        }
        print(f"  followup_index={fu_idx}  n={len(lams)}  "
              f"mean lambda={np.mean(lams):.2f}  median={np.median(lams):.2f}",
              flush=True)

    # Intra-patient vs inter-patient variance
    print("\n=== Intra-patient vs inter-patient lambda variance ===",
          flush=True)
    intra_vars = []
    for pid, obs_list in multi_obs_patients.items():
        ls = np.array([o[1] for o in obs_list])
        if len(ls) >= 2:
            intra_vars.append(float(np.var(ls, ddof=1)))
    all_lams = [r["lambda"] for r in per_obs if r["valid"]]
    inter_var = float(np.var(all_lams, ddof=1))
    intra_var_mean = float(np.mean(intra_vars)) if intra_vars else float("nan")
    icc_proxy = (inter_var - intra_var_mean) / inter_var if inter_var > 0 else float("nan")
    print(f"  Inter-patient lambda variance = {inter_var:.4f}", flush=True)
    print(f"  Mean intra-patient lambda variance = {intra_var_mean:.4f}",
          flush=True)
    print(f"  ICC-proxy (between-patient fraction) = {icc_proxy:.4f}",
          flush=True)
    if icc_proxy > 0.5:
        interp = ("HIGH ICC: lambda is more PATIENT-INTRINSIC than "
                  "time-varying (patient biology dominates).")
    elif icc_proxy < 0.5:
        interp = ("LOW ICC: lambda is more TIME-VARYING within patients "
                  "(temporal evolution dominates).")
    else:
        interp = "Borderline ICC."
    print(f"  Interpretation: {interp}", flush=True)

    out = {
        "version": "v196",
        "experiment": ("Longitudinal evolution of UODSL lambda in "
                       "PROTEAS-brain-mets"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_observations_total": len(per_obs),
        "n_valid_lambda_fits": n_valid,
        "n_patients_with_multi_followup": len(multi_obs_patients),
        "n_patients_with_3plus_followup": len(per_patient_spearman),
        "per_patient_spearman_summary": {
            "n_patients": len(per_patient_spearman),
            "mean_rho": float(np.mean(rhos)) if per_patient_spearman else None,
            "median_rho": float(np.median(rhos)) if per_patient_spearman else None,
            "n_rho_positive": int(n_pos) if per_patient_spearman else 0,
            "n_rho_negative": int(n_neg) if per_patient_spearman else 0,
            "sign_test_p_value": float(p_sign) if per_patient_spearman else None,
        },
        "by_followup_index": fu_summary,
        "variance_components": {
            "inter_patient_variance": inter_var,
            "mean_intra_patient_variance": intra_var_mean,
            "icc_proxy": float(icc_proxy),
            "interpretation": interp,
        },
        "per_patient_spearman": per_patient_spearman,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if per_obs:
        with OUT_CSV.open("w", newline="") as fp:
            keys = list(per_obs[0].keys())
            w = csv.DictWriter(fp, fieldnames=keys)
            w.writeheader()
            w.writerows(per_obs)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
