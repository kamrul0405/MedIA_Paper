"""v181: UOSL permutation/null-shuffle test — round 20, part 2.

A flagship reviewer will ask: is the (n_train, S) -> P relationship
captured by UOSL real, or could a permuted set of features fit
just as well?

Test:
  1. Fit UOSL on the true 10-point training set (v174 + v159 LOCO).
     Record true_rmse.
  2. For 10,000 random permutations of the (n_train, S) feature
     pairs across the 10 datapoints, refit UOSL and record
     perm_rmse[i].
  3. Empirical p-value =
       P( perm_rmse[i] <= true_rmse | shuffled features )
     i.e. fraction of permutations that do AS WELL OR BETTER than
     the true assignment. A small p-value means the structural
     relationship between (n_train, S) and P is real.
  4. Repeat the same test for Yale prediction error and v172 UPENN
     prediction error (using each permuted fit's prediction).

Outputs:
  Nature_project/05_results/v181_uosl_permutation_test.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
OUT_JSON = RESULTS / "v181_uosl_permutation_test.json"
RNG = np.random.default_rng(2026)
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
    print("v181 UOSL PERMUTATION/NULL-SHUFFLE TEST", flush=True)
    print(f"  N_perm = {N_PERM}", flush=True)
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

    # Truth
    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt_true, _ = curve_fit(uosl_v2, (fit_n_train, fit_S), fit_P,
                              p0=p0, bounds=bounds, maxfev=50000)
    pred_true = uosl_v2((fit_n_train, fit_S), *popt_true)
    true_rmse = float(np.sqrt(np.mean((pred_true - fit_P) ** 2)))

    td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
    n_tr_full = sum(n_per_cohort[c] for c in ALL_COHORTS)
    S_yale = similarity_index(td_full, "Yale-Brain-Mets")
    S_upenn = similarity_index(td_full, "UPENN-GBM")
    yale_obs = 0.7871
    upenn_obs = 0.9285

    yale_pred_true = float(uosl_v2(
        (np.array([n_tr_full]), np.array([S_yale])), *popt_true)[0])
    upenn_pred_true = float(uosl_v2(
        (np.array([n_tr_full]), np.array([S_upenn])), *popt_true)[0])
    true_yale_err = abs(yale_pred_true - yale_obs)
    true_upenn_err = abs(upenn_pred_true - upenn_obs)
    print(f"\nTrue fit: RMSE = {true_rmse:.4f}  "
          f"Yale err = {true_yale_err*100:.2f} pp  "
          f"UPENN err = {true_upenn_err*100:.2f} pp", flush=True)

    print(f"\nRunning {N_PERM} feature permutations...", flush=True)
    perm_rmses = []
    perm_yale_errs = []
    perm_upenn_errs = []
    fits_attempted = 0
    fits_failed = 0
    t0 = time.time()
    for i in range(N_PERM):
        # Permute the (n_train, S) PAIRS as a unit so we destroy their
        # association with P, but keep the marginal distributions.
        perm_idx = RNG.permutation(n10)
        perm_n_train = fit_n_train[perm_idx]
        perm_S = fit_S[perm_idx]
        try:
            popt_p, _ = curve_fit(uosl_v2,
                                   (perm_n_train, perm_S), fit_P,
                                   p0=popt_true, bounds=bounds, maxfev=5000)
            fits_attempted += 1
        except Exception:
            fits_failed += 1
            continue
        pred_p = uosl_v2((perm_n_train, perm_S), *popt_p)
        perm_rmses.append(float(np.sqrt(np.mean((pred_p - fit_P) ** 2))))

        yale_p = float(uosl_v2(
            (np.array([n_tr_full]), np.array([S_yale])), *popt_p)[0])
        upenn_p = float(uosl_v2(
            (np.array([n_tr_full]), np.array([S_upenn])), *popt_p)[0])
        perm_yale_errs.append(abs(yale_p - yale_obs))
        perm_upenn_errs.append(abs(upenn_p - upenn_obs))

        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{N_PERM} ({time.time()-t0:.0f}s) — "
                  f"current p_rmse={np.mean(np.array(perm_rmses) <= true_rmse):.4f}",
                  flush=True)

    perm_rmses = np.array(perm_rmses)
    perm_yale_errs = np.array(perm_yale_errs)
    perm_upenn_errs = np.array(perm_upenn_errs)
    n_eff = len(perm_rmses)
    print(f"\n  successful permutation fits: {n_eff} / {N_PERM} "
          f"(failed = {fits_failed})", flush=True)

    # one-sided p-values: how often does the permutation match or beat truth?
    p_rmse = float(np.mean(perm_rmses <= true_rmse))
    p_yale = float(np.mean(perm_yale_errs <= true_yale_err))
    p_upenn = float(np.mean(perm_upenn_errs <= true_upenn_err))

    print(f"\n=== Permutation-test results ===", flush=True)
    print(f"  Within-fit RMSE:", flush=True)
    print(f"    true = {true_rmse:.4f}", flush=True)
    print(f"    permutation 5%/50%/95% = "
          f"{np.percentile(perm_rmses, 5):.4f}/"
          f"{np.percentile(perm_rmses, 50):.4f}/"
          f"{np.percentile(perm_rmses, 95):.4f}", flush=True)
    print(f"    P(perm <= true) = {p_rmse:.4f}", flush=True)
    print(f"  Yale prediction error:", flush=True)
    print(f"    true = {true_yale_err*100:.2f} pp", flush=True)
    print(f"    permutation 5%/50%/95% = "
          f"{np.percentile(perm_yale_errs, 5)*100:.2f}/"
          f"{np.percentile(perm_yale_errs, 50)*100:.2f}/"
          f"{np.percentile(perm_yale_errs, 95)*100:.2f} pp", flush=True)
    print(f"    P(perm <= true) = {p_yale:.4f}", flush=True)
    print(f"  v172 UPENN prediction error:", flush=True)
    print(f"    true = {true_upenn_err*100:.2f} pp", flush=True)
    print(f"    permutation 5%/50%/95% = "
          f"{np.percentile(perm_upenn_errs, 5)*100:.2f}/"
          f"{np.percentile(perm_upenn_errs, 50)*100:.2f}/"
          f"{np.percentile(perm_upenn_errs, 95)*100:.2f} pp", flush=True)
    print(f"    P(perm <= true) = {p_upenn:.4f}", flush=True)

    out = {
        "version": "v181",
        "experiment": ("UOSL permutation/null-shuffle test "
                       "(10,000 feature permutations)"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_perm": N_PERM,
        "n_perm_successful": int(n_eff),
        "n_perm_failed": int(fits_failed),
        "true_within_fit_rmse": true_rmse,
        "true_yale_err": true_yale_err,
        "true_upenn_err": true_upenn_err,
        "p_value_rmse": p_rmse,
        "p_value_yale_err": p_yale,
        "p_value_upenn_err": p_upenn,
        "perm_rmse_quantiles": {
            "p05": float(np.percentile(perm_rmses, 5)),
            "p50": float(np.percentile(perm_rmses, 50)),
            "p95": float(np.percentile(perm_rmses, 95)),
        },
        "perm_yale_err_quantiles": {
            "p05": float(np.percentile(perm_yale_errs, 5)),
            "p50": float(np.percentile(perm_yale_errs, 50)),
            "p95": float(np.percentile(perm_yale_errs, 95)),
        },
        "perm_upenn_err_quantiles": {
            "p05": float(np.percentile(perm_upenn_errs, 5)),
            "p50": float(np.percentile(perm_upenn_errs, 50)),
            "p95": float(np.percentile(perm_upenn_errs, 95)),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
