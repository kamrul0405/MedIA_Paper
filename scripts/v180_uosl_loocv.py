"""v180: UOSL Leave-One-Out cross-validation (LOOCV) — round 20, part 1.

Round 19 reported within-fit RMSE (9.11 pp) and out-of-sample errors
on Yale (1.27 pp) + v172 UPENN (2.04 pp). Reviewers at flagship
venues require a third number: leave-one-out cross-validation RMSE
across all fit datapoints.

For each of the 10 fit datapoints (v174 + v159 LOCO):
  - hold out the datapoint
  - re-fit UOSL on the remaining 9
  - predict the held-out point
  - record absolute prediction error

Report:
  - per-fold prediction errors
  - LOOCV RMSE
  - LOOCV correlation
  - LOOCV predictions vs observed scatter

Outputs:
  Nature_project/05_results/v180_uosl_loocv.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
OUT_JSON = RESULTS / "v180_uosl_loocv.json"

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
    print("v180 UOSL LEAVE-ONE-OUT CROSS-VALIDATION (LOOCV)", flush=True)
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

    fit_n_train, fit_S, fit_P, fit_label = [], [], [], []
    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        N = int(n_str)
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        P = row["ensemble_outgrowth_pct"] / 100.0
        fit_n_train.append(row["n_train_patients"])
        fit_S.append(S)
        fit_P.append(P)
        fit_label.append(f"v174 N={N}->UPENN")

    for held_out, stats in v159["by_cohort"].items():
        train_cohorts = [c for c in ALL_COHORTS if c != held_out]
        train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
        S = similarity_index(train_dist, held_out)
        P = stats["ensemble_outgrowth_mean"] / 100.0
        n_tr = sum(n_per_cohort[c] for c in train_cohorts)
        fit_n_train.append(n_tr)
        fit_S.append(S)
        fit_P.append(P)
        fit_label.append(f"v159 LOCO held={held_out}")

    fit_n_train = np.array(fit_n_train, dtype=float)
    fit_S = np.array(fit_S, dtype=float)
    fit_P = np.array(fit_P, dtype=float)
    n10 = len(fit_P)
    print(f"  fitting set: n = {n10}", flush=True)

    # full-fit baseline
    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt_full, _ = curve_fit(uosl_v2, (fit_n_train, fit_S), fit_P,
                              p0=p0, bounds=bounds, maxfev=50000)
    pred_full = uosl_v2((fit_n_train, fit_S), *popt_full)
    rmse_full = float(np.sqrt(np.mean((pred_full - fit_P) ** 2)))
    print(f"\nFull-fit (10 datapoints): RMSE = {rmse_full:.4f}", flush=True)

    # LOOCV
    print(f"\nRunning LOOCV across {n10} folds...", flush=True)
    fold_results = []
    pred_loocv = np.zeros(n10)
    for k in range(n10):
        keep = np.ones(n10, dtype=bool)
        keep[k] = False
        try:
            popt_k, _ = curve_fit(uosl_v2,
                                   (fit_n_train[keep], fit_S[keep]),
                                   fit_P[keep],
                                   p0=popt_full, bounds=bounds, maxfev=50000)
        except Exception as e:
            print(f"  fold {k+1}/{n10} ({fit_label[k]}): FIT FAIL {e}",
                  flush=True)
            pred_loocv[k] = float("nan")
            fold_results.append({
                "fold": k + 1, "label": fit_label[k],
                "n_train": int(fit_n_train[k]),
                "S": float(fit_S[k]),
                "P_observed": float(fit_P[k]),
                "P_predicted": float("nan"),
                "abs_err_pp": float("nan"),
                "params": None,
            })
            continue
        p_pred = float(uosl_v2(
            (np.array([fit_n_train[k]]), np.array([fit_S[k]])),
            *popt_k)[0])
        pred_loocv[k] = p_pred
        err_pp = abs(p_pred - fit_P[k]) * 100
        fold_results.append({
            "fold": k + 1, "label": fit_label[k],
            "n_train": int(fit_n_train[k]),
            "S": float(fit_S[k]),
            "P_observed": float(fit_P[k]),
            "P_predicted": p_pred,
            "abs_err_pp": float(err_pp),
            "params": {
                "P_0": float(popt_k[0]), "P_inf": float(popt_k[1]),
                "a": float(popt_k[2]), "n_c": float(popt_k[3]),
            },
        })
        print(f"  fold {k+1:2d}/{n10}  {fit_label[k]:35s}  "
              f"obs={fit_P[k]:.4f}  pred={p_pred:.4f}  err={err_pp:.2f} pp",
              flush=True)

    valid = ~np.isnan(pred_loocv)
    err = np.abs(pred_loocv[valid] - fit_P[valid])
    rmse_loocv = float(np.sqrt(np.mean(err ** 2)))
    mae_loocv = float(np.mean(err))
    if valid.sum() >= 3:
        r_loocv = float(np.corrcoef(pred_loocv[valid], fit_P[valid])[0, 1])
    else:
        r_loocv = float("nan")

    print(f"\n=== LOOCV SUMMARY ===", flush=True)
    print(f"  n_folds_valid = {int(valid.sum())} / {n10}", flush=True)
    print(f"  LOOCV RMSE = {rmse_loocv:.4f}  ({rmse_loocv*100:.2f} pp)",
          flush=True)
    print(f"  LOOCV MAE  = {mae_loocv:.4f}  ({mae_loocv*100:.2f} pp)",
          flush=True)
    print(f"  LOOCV r    = {r_loocv:.4f}", flush=True)
    print(f"  Within-fit RMSE = {rmse_full:.4f} (for comparison)",
          flush=True)

    # Compare to a simple-mean baseline (predict mean of training set)
    mean_baseline_rmse = float(np.sqrt(np.mean(
        (np.mean(fit_P) - fit_P) ** 2)))
    print(f"  Mean-baseline RMSE = {mean_baseline_rmse:.4f} (for comparison)",
          flush=True)

    out = {
        "version": "v180",
        "experiment": "UOSL Leave-One-Out cross-validation (10 folds)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_folds": n10,
        "n_folds_valid": int(valid.sum()),
        "full_fit_params": {
            "P_0": float(popt_full[0]), "P_inf": float(popt_full[1]),
            "a": float(popt_full[2]), "n_c": float(popt_full[3]),
        },
        "full_fit_rmse": rmse_full,
        "loocv_rmse": rmse_loocv,
        "loocv_mae": mae_loocv,
        "loocv_r": r_loocv,
        "mean_baseline_rmse": mean_baseline_rmse,
        "fold_results": fold_results,
        "fit_labels": fit_label,
        "fit_n_train": fit_n_train.tolist(),
        "fit_S": fit_S.tolist(),
        "fit_P": fit_P.tolist(),
        "pred_loocv": pred_loocv.tolist(),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
