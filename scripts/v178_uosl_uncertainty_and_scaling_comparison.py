"""v178: UOSL parameter uncertainty (bootstrap) + comparison vs
neural scaling laws (Kaplan-McCandlish, Chinchilla-style).

Round 19, part 1.

For a flagship submission we need:
  (a) Confidence intervals on the four UOSL parameters
      (P_0, P_inf, a, n_c) — establishes that the fit is not a
      single-realisation artefact;
  (b) Monte-Carlo prediction interval for the Yale prediction —
      i.e. the 78.71% Yale observed should fall inside the UOSL's
      predicted distribution, not just close to its point estimate;
  (c) Comparison with two baseline scaling laws established in the
      LLM literature:
        - Kaplan-McCandlish (Kaplan et al., 2020):
            P = P_inf - (C / n_train)^alpha
        - Chinchilla-style (Hoffmann et al., 2022) lite:
            P = P_inf - C * n_train^-alpha - D * N_cohorts^-beta

We fit each law on the same 10 training points (v174 + v159 LOCO)
and report:
  - Within-fit RMSE
  - Out-of-sample RMSE on (v172 zero-shot UPENN, Yale)
  - Yale prediction error

The headline claim is that UOSL — by including the disease-similarity
factor S — beats naive dataset-size-only scaling laws on cross-cohort
extrapolation.

Outputs:
  Nature_project/05_results/v178_uosl_uncertainty_scaling_comparison.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
OUT_JSON = RESULTS / "v178_uosl_uncertainty_scaling_comparison.json"

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
RNG = np.random.default_rng(42)
N_BOOT = 5000

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


# ---------- scaling laws ----------

def uosl_v2(features, p_0, p_inf, a, n_c):
    n_train, S = features
    N_eff = np.log1p(n_train) * S
    return p_0 + (p_inf - p_0) / (1.0 + np.exp(-a * (N_eff - n_c)))


def kaplan(features, p_inf, C, alpha):
    """P = P_inf - (C / n_train)^alpha (Kaplan-McCandlish).

    Ignores S — pure dataset-size scaling.
    """
    n_train, _S = features
    n = np.maximum(np.asarray(n_train, dtype=float), 1.0)
    return p_inf - (C / n) ** alpha


def chinchilla_lite(features, p_inf, C, alpha, D, beta, N_cohorts):
    n_train, _S = features
    n = np.maximum(np.asarray(n_train, dtype=float), 1.0)
    N = np.maximum(np.asarray(N_cohorts, dtype=float), 1.0)
    return p_inf - C * n ** (-alpha) - D * N ** (-beta)


# ---------- main ----------

def main():
    print("=" * 78, flush=True)
    print("v178 UOSL UNCERTAINTY + SCALING-LAW COMPARISON", flush=True)
    print("=" * 78, flush=True)

    # Build the 10-point fitting set (v174 + v159 LOCO)
    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    v159 = json.loads((RESULTS / "v159_multiseed_v156.json").read_text())

    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]

    fit_n_train, fit_S, fit_P, fit_N_cohorts, fit_label = [], [], [], [], []

    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        N = int(n_str)
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        P = row["ensemble_outgrowth_pct"] / 100.0
        fit_n_train.append(row["n_train_patients"])
        fit_S.append(S)
        fit_P.append(P)
        fit_N_cohorts.append(N)
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
        fit_N_cohorts.append(4)
        fit_label.append(f"v159 LOCO held={held_out}")

    fit_n_train = np.array(fit_n_train, dtype=float)
    fit_S = np.array(fit_S, dtype=float)
    fit_P = np.array(fit_P, dtype=float)
    fit_N_cohorts = np.array(fit_N_cohorts, dtype=float)
    n10 = len(fit_P)
    print(f"  fitting set: n = {n10}", flush=True)

    # ---------- 1) UOSL fit + bootstrap parameter CIs ----------
    print("\nFitting UOSL v2 + 5000-bootstrap parameter CIs...", flush=True)
    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt_full, _ = curve_fit(uosl_v2, (fit_n_train, fit_S), fit_P,
                              p0=p0, bounds=bounds, maxfev=50000)
    p_0_pt, p_inf_pt, a_pt, n_c_pt = popt_full

    boot_params = []
    boot_yale_pred = []
    boot_v172_pred = []

    # Yale and v172 predictor features
    td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
    n_tr_full = sum(n_per_cohort[c] for c in ALL_COHORTS)
    S_yale = similarity_index(td_full, "Yale-Brain-Mets")
    S_upenn = similarity_index(td_full, "UPENN-GBM")
    yale_features = (np.array([n_tr_full]), np.array([S_yale]))
    upenn_features = (np.array([n_tr_full]), np.array([S_upenn]))

    for b in range(N_BOOT):
        idx = RNG.integers(0, n10, size=n10)
        try:
            popt_b, _ = curve_fit(
                uosl_v2,
                (fit_n_train[idx], fit_S[idx]),
                fit_P[idx],
                p0=popt_full, bounds=bounds, maxfev=20000)
        except Exception:
            continue
        boot_params.append(popt_b)
        boot_yale_pred.append(float(uosl_v2(yale_features, *popt_b)[0]))
        boot_v172_pred.append(float(uosl_v2(upenn_features, *popt_b)[0]))

    boot_params = np.array(boot_params)
    print(f"  successful bootstrap iterations: {len(boot_params)} / {N_BOOT}",
          flush=True)

    param_ci = {}
    for i, name in enumerate(["P_0", "P_inf", "a", "n_c"]):
        lo, hi = np.percentile(boot_params[:, i], [2.5, 97.5])
        med = float(np.median(boot_params[:, i]))
        param_ci[name] = {
            "point": float(popt_full[i]),
            "median_boot": med,
            "ci_lo": float(lo),
            "ci_hi": float(hi),
        }
        print(f"  {name:6s} = {popt_full[i]:.4f}  "
              f"95% CI [{lo:.4f}, {hi:.4f}]", flush=True)

    yale_pt = float(uosl_v2(yale_features, *popt_full)[0])
    yale_lo, yale_hi = np.percentile(boot_yale_pred, [2.5, 97.5])
    yale_obs = 0.7871   # from v177
    print(f"\nYale prediction:", flush=True)
    print(f"  point = {yale_pt:.4f}  95% CI [{yale_lo:.4f}, {yale_hi:.4f}]",
          flush=True)
    print(f"  observed = {yale_obs:.4f}", flush=True)
    print(f"  observed inside 95% CI? "
          f"{yale_lo <= yale_obs <= yale_hi}", flush=True)

    upenn_pt = float(uosl_v2(upenn_features, *popt_full)[0])
    upenn_lo, upenn_hi = np.percentile(boot_v172_pred, [2.5, 97.5])
    upenn_obs = 0.9285   # from v172 N=0
    print(f"\nv172 zero-shot UPENN prediction:", flush=True)
    print(f"  point = {upenn_pt:.4f}  95% CI [{upenn_lo:.4f}, {upenn_hi:.4f}]",
          flush=True)
    print(f"  observed = {upenn_obs:.4f}", flush=True)
    print(f"  observed inside 95% CI? "
          f"{upenn_lo <= upenn_obs <= upenn_hi}", flush=True)

    # ---------- 2) Kaplan-McCandlish baseline ----------
    print("\nFitting Kaplan-McCandlish baseline...", flush=True)
    p0_k = [1.0, 100.0, 0.5]
    bounds_k = ([0.5, 0.1, 0.001], [1.0, 1e6, 5.0])
    popt_k, _ = curve_fit(kaplan, (fit_n_train, fit_S), fit_P,
                           p0=p0_k, bounds=bounds_k, maxfev=50000)
    pred_k = kaplan((fit_n_train, fit_S), *popt_k)
    rmse_k_fit = float(np.sqrt(np.mean((pred_k - fit_P) ** 2)))
    yale_pred_k = float(kaplan(yale_features, *popt_k)[0])
    upenn_pred_k = float(kaplan(upenn_features, *popt_k)[0])
    print(f"  P_inf={popt_k[0]:.4f} C={popt_k[1]:.4f} alpha={popt_k[2]:.4f}",
          flush=True)
    print(f"  Within-fit RMSE = {rmse_k_fit:.4f}", flush=True)
    print(f"  Yale pred = {yale_pred_k:.4f}  (obs {yale_obs:.4f}, "
          f"err {abs(yale_pred_k - yale_obs)*100:.2f} pp)", flush=True)
    print(f"  v172 UPENN pred = {upenn_pred_k:.4f}  (obs {upenn_obs:.4f}, "
          f"err {abs(upenn_pred_k - upenn_obs)*100:.2f} pp)", flush=True)

    # ---------- 3) Chinchilla-lite baseline ----------
    print("\nFitting Chinchilla-lite baseline...", flush=True)

    def chinchilla_for_fit(features_aug, p_inf, C, alpha, D, beta):
        n_train, _S, N_co = features_aug
        return p_inf - C * np.maximum(n_train, 1.0) ** (-alpha) - \
            D * np.maximum(N_co, 1.0) ** (-beta)

    p0_c = [1.0, 1.0, 0.3, 1.0, 0.3]
    bounds_c = ([0.5, 0.0, 0.001, 0.0, 0.001],
                [1.5, 1e3, 5.0, 1e3, 5.0])
    popt_c, _ = curve_fit(chinchilla_for_fit,
                           (fit_n_train, fit_S, fit_N_cohorts),
                           fit_P, p0=p0_c, bounds=bounds_c, maxfev=100000)
    pred_c = chinchilla_for_fit((fit_n_train, fit_S, fit_N_cohorts), *popt_c)
    rmse_c_fit = float(np.sqrt(np.mean((pred_c - fit_P) ** 2)))
    yale_pred_c = float(chinchilla_for_fit(
        (np.array([n_tr_full]), np.array([S_yale]), np.array([5.0])),
        *popt_c)[0])
    upenn_pred_c = float(chinchilla_for_fit(
        (np.array([n_tr_full]), np.array([S_upenn]), np.array([5.0])),
        *popt_c)[0])
    print(f"  P_inf={popt_c[0]:.4f} C={popt_c[1]:.4f} alpha={popt_c[2]:.4f} "
          f"D={popt_c[3]:.4f} beta={popt_c[4]:.4f}", flush=True)
    print(f"  Within-fit RMSE = {rmse_c_fit:.4f}", flush=True)
    print(f"  Yale pred = {yale_pred_c:.4f}  (err "
          f"{abs(yale_pred_c - yale_obs)*100:.2f} pp)", flush=True)
    print(f"  v172 UPENN pred = {upenn_pred_c:.4f}  (err "
          f"{abs(upenn_pred_c - upenn_obs)*100:.2f} pp)", flush=True)

    # ---------- 4) UOSL within-fit and out-of-sample ----------
    pred_uosl = uosl_v2((fit_n_train, fit_S), *popt_full)
    rmse_uosl_fit = float(np.sqrt(np.mean((pred_uosl - fit_P) ** 2)))
    err_yale_uosl = abs(yale_pt - yale_obs) * 100
    err_v172_uosl = abs(upenn_pt - upenn_obs) * 100

    print("\n=== SCALING-LAW COMPARISON ===", flush=True)
    header = f"  {'Law':25s} {'Within-fit RMSE':18s} {'Yale err (pp)':16s} {'v172 err (pp)':16s}"
    print(header, flush=True)
    print(f"  {'UOSL v2':25s} {rmse_uosl_fit:14.4f}     "
          f"{err_yale_uosl:12.2f}     {err_v172_uosl:12.2f}", flush=True)
    print(f"  {'Kaplan-McCandlish':25s} {rmse_k_fit:14.4f}     "
          f"{abs(yale_pred_k - yale_obs)*100:12.2f}     "
          f"{abs(upenn_pred_k - upenn_obs)*100:12.2f}", flush=True)
    print(f"  {'Chinchilla-lite':25s} {rmse_c_fit:14.4f}     "
          f"{abs(yale_pred_c - yale_obs)*100:12.2f}     "
          f"{abs(upenn_pred_c - upenn_obs)*100:12.2f}", flush=True)

    # ---------- 5) Save ----------
    out = {
        "version": "v178",
        "experiment": ("UOSL parameter uncertainty (5000-bootstrap) + "
                       "comparison vs Kaplan/Chinchilla scaling laws"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_fit_points": int(n10),
        "n_bootstrap": int(N_BOOT),
        "uosl_v2": {
            "param_point": {
                "P_0": float(p_0_pt), "P_inf": float(p_inf_pt),
                "a": float(a_pt), "n_c": float(n_c_pt),
            },
            "param_ci_95": param_ci,
            "rmse_within_fit": rmse_uosl_fit,
            "yale_prediction": {
                "point": yale_pt,
                "ci_95_lo": float(yale_lo),
                "ci_95_hi": float(yale_hi),
                "observed": yale_obs,
                "in_ci_95": bool(yale_lo <= yale_obs <= yale_hi),
                "err_pp": err_yale_uosl,
            },
            "v172_zero_shot_upenn_prediction": {
                "point": upenn_pt,
                "ci_95_lo": float(upenn_lo),
                "ci_95_hi": float(upenn_hi),
                "observed": upenn_obs,
                "in_ci_95": bool(upenn_lo <= upenn_obs <= upenn_hi),
                "err_pp": err_v172_uosl,
            },
        },
        "kaplan_mccandlish": {
            "params": {"P_inf": float(popt_k[0]), "C": float(popt_k[1]),
                       "alpha": float(popt_k[2])},
            "rmse_within_fit": rmse_k_fit,
            "yale_pred": yale_pred_k,
            "yale_err_pp": float(abs(yale_pred_k - yale_obs) * 100),
            "v172_pred": upenn_pred_k,
            "v172_err_pp": float(abs(upenn_pred_k - upenn_obs) * 100),
        },
        "chinchilla_lite": {
            "params": {
                "P_inf": float(popt_c[0]), "C": float(popt_c[1]),
                "alpha": float(popt_c[2]),
                "D": float(popt_c[3]), "beta": float(popt_c[4]),
            },
            "rmse_within_fit": rmse_c_fit,
            "yale_pred": yale_pred_c,
            "yale_err_pp": float(abs(yale_pred_c - yale_obs) * 100),
            "v172_pred": upenn_pred_c,
            "v172_err_pp": float(abs(upenn_pred_c - upenn_obs) * 100),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
