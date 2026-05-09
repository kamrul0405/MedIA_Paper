"""v183: Expanded UOSL calibration set (20 datapoints) — round 21, part 2.

Round 20 found that UOSL has marginal LOOCV stability (RMSE 12.80 pp,
worse than mean-baseline 11.78 pp) and weak permutation p-values
(0.16, 0.17, 0.05) — clearly small-sample limitations from fitting
4 parameters on 10 datapoints.

v183 doubles the calibration set by using each of v159's 15 individual
(cohort, seed) datapoints separately, instead of just the per-cohort
means (which collapsed 15 -> 5 points). This gives:

    5 v174 datapoints  + 15 v159 datapoints  = 20 datapoints

Re-fits UOSL, bootstraps, runs LOOCV and permutation again. Compares
to round-20 results.

Outputs:
  Nature_project/05_results/v183_uosl_expanded_calibration.json
"""
from __future__ import annotations

import json
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
OUT_JSON = RESULTS / "v183_uosl_expanded_calibration.json"
RNG = np.random.default_rng(42)
N_BOOT = 5000
N_PERM = 1000

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
DISEASE_VEC = {
    "UCSF-POSTOP":         np.array([0.7, 0.3, 0.0]),
    "MU-Glioma-Post":      np.array([0.7, 0.3, 0.0]),
    "RHUH-GBM":            np.array([1.0, 0.0, 0.0]),
    "LUMIERE":             np.array([0.4, 0.6, 0.0]),
    "PROTEAS-brain-mets":  np.array([0.0, 0.0, 1.0]),
    "UPENN-GBM":           np.array([1.0, 0.0, 0.0]),
    "Yale-Brain-Mets":     np.array([0.0, 0.0, 1.0]),
}


def cohort_weighted_distribution(train_cohorts, n_per_cohort):
    total = sum(n_per_cohort.get(c, 0) for c in train_cohorts)
    if total == 0:
        return np.zeros(3)
    avg = np.zeros(3)
    for c in train_cohorts:
        n = n_per_cohort.get(c, 0)
        avg += (n / total) * DISEASE_VEC[c]
    return avg


def similarity_index(train_dist, test_cohort):
    test = DISEASE_VEC[test_cohort]
    nt = np.linalg.norm(train_dist)
    nT = np.linalg.norm(test)
    if nt == 0 or nT == 0:
        return 0.0
    return float(np.dot(train_dist, test) / (nt * nT))


def uosl_v2(features, p_0, p_inf, a, n_c):
    n_train, S = features
    N_eff = np.log1p(n_train) * S
    return p_0 + (p_inf - p_0) / (1.0 + np.exp(-a * (N_eff - n_c)))


def main():
    print("=" * 78, flush=True)
    print("v183 EXPANDED UOSL CALIBRATION (20 DATAPOINTS)", flush=True)
    print("=" * 78, flush=True)

    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    v159 = json.loads((RESULTS / "v159_multiseed_v156.json").read_text())

    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]

    n_train_arr, S_arr, P_arr, lbl_arr = [], [], [], []
    # 5 v174 (varying n_train, near-constant S)
    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        n_train_arr.append(row["n_train_patients"])
        S_arr.append(S)
        P_arr.append(row["ensemble_outgrowth_pct"] / 100.0)
        lbl_arr.append(f"v174 N={n_str}->UPENN")
    # 15 v159 (per-seed values from each held-out cohort)
    for held_out, stats in v159["by_cohort"].items():
        train_cohorts = [c for c in ALL_COHORTS if c != held_out]
        train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
        S = similarity_index(train_dist, held_out)
        n_tr = sum(n_per_cohort[c] for c in train_cohorts)
        per_seed = stats["per_seed"]
        for seed, srow in per_seed.items():
            n_train_arr.append(n_tr)
            S_arr.append(S)
            P_arr.append(srow["ensemble_outgrowth"] / 100.0)
            lbl_arr.append(f"v159 LOCO held={held_out} seed={seed}")

    n_train_arr = np.array(n_train_arr, dtype=float)
    S_arr = np.array(S_arr, dtype=float)
    P_arr = np.array(P_arr, dtype=float)
    n_total = len(P_arr)
    print(f"  expanded calibration set: n = {n_total}", flush=True)
    for lbl, nt, S, P in zip(lbl_arr, n_train_arr, S_arr, P_arr):
        print(f"    {lbl:45s} n_train={int(nt):4d}  S={S:.4f}  P={P:.4f}",
              flush=True)

    # Full fit
    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt_full, _ = curve_fit(uosl_v2, (n_train_arr, S_arr), P_arr,
                              p0=p0, bounds=bounds, maxfev=50000)
    pred_full = uosl_v2((n_train_arr, S_arr), *popt_full)
    rmse_full = float(np.sqrt(np.mean((pred_full - P_arr) ** 2)))
    r_full = float(np.corrcoef(pred_full, P_arr)[0, 1])
    print(f"\nUOSL v2 expanded fit:", flush=True)
    print(f"  P_0={popt_full[0]:.4f} P_inf={popt_full[1]:.4f} "
          f"a={popt_full[2]:.4f} n_c={popt_full[3]:.4f}", flush=True)
    print(f"  Within-fit RMSE = {rmse_full:.4f}  r = {r_full:.4f}",
          flush=True)

    # Out-of-sample Yale + v172
    n_tr_full = sum(n_per_cohort[c] for c in ALL_COHORTS)
    td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
    S_yale = similarity_index(td_full, "Yale-Brain-Mets")
    S_upenn = similarity_index(td_full, "UPENN-GBM")
    yale_obs = 0.7871
    upenn_obs = 0.9285
    yale_pred = float(uosl_v2((np.array([n_tr_full]),
                                 np.array([S_yale])), *popt_full)[0])
    upenn_pred = float(uosl_v2((np.array([n_tr_full]),
                                  np.array([S_upenn])), *popt_full)[0])
    yale_err = abs(yale_pred - yale_obs)
    upenn_err = abs(upenn_pred - upenn_obs)
    print(f"\nOut-of-sample predictions (expanded fit):", flush=True)
    print(f"  Yale: pred={yale_pred:.4f}  obs={yale_obs:.4f}  "
          f"err={yale_err*100:.2f} pp", flush=True)
    print(f"  v172 UPENN: pred={upenn_pred:.4f}  obs={upenn_obs:.4f}  "
          f"err={upenn_err*100:.2f} pp", flush=True)

    # Bootstrap parameter CIs
    print(f"\nBootstrap n_boot={N_BOOT}...", flush=True)
    boot = []
    boot_yale = []
    boot_upenn = []
    for b in range(N_BOOT):
        idx = RNG.integers(0, n_total, size=n_total)
        try:
            popt_b, _ = curve_fit(uosl_v2, (n_train_arr[idx], S_arr[idx]),
                                   P_arr[idx], p0=popt_full, bounds=bounds,
                                   maxfev=20000)
            boot.append(popt_b)
            boot_yale.append(float(uosl_v2((np.array([n_tr_full]),
                                              np.array([S_yale])),
                                             *popt_b)[0]))
            boot_upenn.append(float(uosl_v2((np.array([n_tr_full]),
                                               np.array([S_upenn])),
                                              *popt_b)[0]))
        except Exception:
            continue
    boot = np.array(boot)
    boot_yale = np.array(boot_yale)
    boot_upenn = np.array(boot_upenn)
    print(f"  successful: {len(boot)}/{N_BOOT}", flush=True)
    param_ci = {}
    for i, name in enumerate(["P_0", "P_inf", "a", "n_c"]):
        lo, hi = np.percentile(boot[:, i], [2.5, 97.5])
        param_ci[name] = {"point": float(popt_full[i]),
                          "ci_lo": float(lo), "ci_hi": float(hi)}
        print(f"  {name:6s} = {popt_full[i]:.4f}  95% CI [{lo:.4f}, {hi:.4f}]",
              flush=True)
    yale_lo, yale_hi = np.percentile(boot_yale, [2.5, 97.5])
    upenn_lo, upenn_hi = np.percentile(boot_upenn, [2.5, 97.5])
    print(f"  Yale prediction CI = [{yale_lo:.4f}, {yale_hi:.4f}]  "
          f"obs in CI? {yale_lo <= yale_obs <= yale_hi}", flush=True)
    print(f"  UPENN prediction CI = [{upenn_lo:.4f}, {upenn_hi:.4f}]  "
          f"obs in CI? {upenn_lo <= upenn_obs <= upenn_hi}", flush=True)

    # LOOCV
    print(f"\nLOOCV (n={n_total} folds)...", flush=True)
    pred_loocv = np.zeros(n_total)
    for k in range(n_total):
        keep = np.ones(n_total, dtype=bool)
        keep[k] = False
        try:
            popt_k, _ = curve_fit(uosl_v2,
                                   (n_train_arr[keep], S_arr[keep]),
                                   P_arr[keep], p0=popt_full, bounds=bounds,
                                   maxfev=20000)
            pred_loocv[k] = float(uosl_v2(
                (np.array([n_train_arr[k]]), np.array([S_arr[k]])),
                *popt_k)[0])
        except Exception:
            pred_loocv[k] = float("nan")
    valid = ~np.isnan(pred_loocv)
    err_loocv = np.abs(pred_loocv[valid] - P_arr[valid])
    rmse_loocv = float(np.sqrt(np.mean(err_loocv ** 2)))
    mae_loocv = float(np.mean(err_loocv))
    if valid.sum() >= 3:
        r_loocv = float(np.corrcoef(pred_loocv[valid], P_arr[valid])[0, 1])
    else:
        r_loocv = float("nan")
    mean_baseline_rmse = float(np.sqrt(np.mean(
        (np.mean(P_arr) - P_arr) ** 2)))
    print(f"  LOOCV RMSE = {rmse_loocv:.4f}  ({rmse_loocv*100:.2f} pp)",
          flush=True)
    print(f"  LOOCV MAE = {mae_loocv:.4f}  r = {r_loocv:.4f}", flush=True)
    print(f"  Mean-baseline RMSE = {mean_baseline_rmse:.4f}  (for comparison)",
          flush=True)
    print(f"  UOSL beats mean-baseline? {rmse_loocv < mean_baseline_rmse}",
          flush=True)

    # Permutation test
    print(f"\nPermutation test (N_perm={N_PERM})...", flush=True)
    rng2 = np.random.default_rng(2026)
    perm_rmses = []
    perm_yale_errs = []
    perm_upenn_errs = []
    for i in range(N_PERM):
        perm_idx = rng2.permutation(n_total)
        try:
            popt_p, _ = curve_fit(
                uosl_v2,
                (n_train_arr[perm_idx], S_arr[perm_idx]), P_arr,
                p0=popt_full, bounds=bounds, maxfev=5000)
            pred_p = uosl_v2((n_train_arr[perm_idx], S_arr[perm_idx]),
                              *popt_p)
            perm_rmses.append(float(np.sqrt(np.mean((pred_p - P_arr) ** 2))))
            yale_p = float(uosl_v2((np.array([n_tr_full]),
                                     np.array([S_yale])), *popt_p)[0])
            upenn_p = float(uosl_v2((np.array([n_tr_full]),
                                      np.array([S_upenn])), *popt_p)[0])
            perm_yale_errs.append(abs(yale_p - yale_obs))
            perm_upenn_errs.append(abs(upenn_p - upenn_obs))
        except Exception:
            continue
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{N_PERM}", flush=True)
    perm_rmses = np.array(perm_rmses)
    perm_yale_errs = np.array(perm_yale_errs)
    perm_upenn_errs = np.array(perm_upenn_errs)
    print(f"  successful permutations: {len(perm_rmses)}/{N_PERM}",
          flush=True)
    p_rmse = float(np.mean(perm_rmses <= rmse_full))
    p_yale = float(np.mean(perm_yale_errs <= yale_err))
    p_upenn = float(np.mean(perm_upenn_errs <= upenn_err))
    print(f"  P(perm RMSE <= true) = {p_rmse:.4f}", flush=True)
    print(f"  P(perm Yale err <= true) = {p_yale:.4f}", flush=True)
    print(f"  P(perm UPENN err <= true) = {p_upenn:.4f}", flush=True)

    # Compare to round-20 (10-point) results
    print(f"\n=== COMPARISON: 10-point (round 20) vs 20-point (round 21) ===",
          flush=True)
    print(f"  Within-fit RMSE:  10pt = 9.11 pp  -> 20pt = "
          f"{rmse_full*100:.2f} pp", flush=True)
    print(f"  LOOCV RMSE:       10pt = 12.80 pp -> 20pt = "
          f"{rmse_loocv*100:.2f} pp", flush=True)
    print(f"  LOOCV r:          10pt = 0.20     -> 20pt = "
          f"{r_loocv:.2f}", flush=True)
    print(f"  Yale prediction:  10pt = 1.27 pp  -> 20pt = "
          f"{yale_err*100:.2f} pp", flush=True)
    print(f"  UPENN prediction: 10pt = 2.04 pp  -> 20pt = "
          f"{upenn_err*100:.2f} pp", flush=True)
    print(f"  Permutation p_rmse:  10pt = 0.157  -> 20pt = "
          f"{p_rmse:.4f}", flush=True)
    print(f"  Permutation p_yale:  10pt = 0.174  -> 20pt = "
          f"{p_yale:.4f}", flush=True)
    print(f"  Permutation p_upenn: 10pt = 0.051  -> 20pt = "
          f"{p_upenn:.4f}", flush=True)

    out = {
        "version": "v183",
        "experiment": ("Expanded UOSL calibration: 5 v174 + 15 v159 per-seed "
                       "= 20 datapoints"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_calibration_points": int(n_total),
        "fit_params": {
            "P_0": float(popt_full[0]), "P_inf": float(popt_full[1]),
            "a": float(popt_full[2]), "n_c": float(popt_full[3]),
        },
        "param_ci_95": param_ci,
        "within_fit_rmse": rmse_full,
        "within_fit_r": r_full,
        "loocv_rmse": rmse_loocv,
        "loocv_mae": mae_loocv,
        "loocv_r": r_loocv,
        "mean_baseline_rmse": mean_baseline_rmse,
        "uosl_beats_mean_baseline_loocv": bool(rmse_loocv < mean_baseline_rmse),
        "yale": {
            "S": float(S_yale),
            "P_pred": yale_pred, "P_obs": yale_obs,
            "err_pp": yale_err * 100,
            "ci_95_lo": float(yale_lo), "ci_95_hi": float(yale_hi),
            "obs_in_ci_95": bool(yale_lo <= yale_obs <= yale_hi),
        },
        "v172_upenn": {
            "S": float(S_upenn),
            "P_pred": upenn_pred, "P_obs": upenn_obs,
            "err_pp": upenn_err * 100,
            "ci_95_lo": float(upenn_lo), "ci_95_hi": float(upenn_hi),
            "obs_in_ci_95": bool(upenn_lo <= upenn_obs <= upenn_hi),
        },
        "permutation_test": {
            "n_perm": N_PERM,
            "n_perm_successful": int(len(perm_rmses)),
            "p_value_rmse": p_rmse,
            "p_value_yale_err": p_yale,
            "p_value_upenn_err": p_upenn,
        },
        "round20_comparison": {
            "rmse_within_fit_10pt": 0.0911,
            "rmse_within_fit_20pt": rmse_full,
            "rmse_loocv_10pt": 0.1280,
            "rmse_loocv_20pt": rmse_loocv,
            "rmse_loocv_change_pp":
                (rmse_loocv - 0.1280) * 100,
            "p_rmse_10pt": 0.1566,
            "p_rmse_20pt": p_rmse,
            "p_yale_10pt": 0.1742,
            "p_yale_20pt": p_yale,
            "p_upenn_10pt": 0.0505,
            "p_upenn_20pt": p_upenn,
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
