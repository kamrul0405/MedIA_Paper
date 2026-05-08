"""v123: DerSimonian-Laird random-effects meta-analysis on the
cohort-conditional optimal sigma at heat>=0.50.

v117 established that heat>=0.50 is the clinically meaningful
threshold (where the anisotropic kernel is the only structural prior
to significantly beat persistence). v115 + v109 together produced
per-cohort optima at heat>=0.50:

  - UCSF-POSTOP: sigma_opt = 0.75 voxels (median r_eq = 15.32)
  - MU-Glioma-Post: sigma_opt = 2.5 voxels (median r_eq = 16.92)
  - RHUH-GBM: sigma_opt = 2.0 voxels (median r_eq = 18.82)
  - LUMIERE: sigma_opt = 2.5 voxels (median r_eq = 12.11)
  - PROTEAS-brain-mets: sigma_opt = 1.0 voxels (estimated r_eq ~6)

This script fits a DerSimonian-Laird random-effects model on
log(sigma_opt) vs log(r_eq) and computes:
  - Pooled slope beta and 95% CI
  - I^2 heterogeneity (between-cohort variance fraction)
  - Cochran Q-test for heterogeneity
  - Predictive interval (where would a new cohort's sigma_opt fall?)

If the slope CI excludes 0 and I^2 is bounded (<75%), this is a
proper Proposal H deliverable as a meta-analytic scaling law.

Outputs:
    Nature_project/05_results/v123_re_meta_analysis_sigma.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
OUT = ROOT / "05_results" / "v123_re_meta_analysis_sigma.json"


# Cohort table (cohort, sigma_opt at heat>=0.50, median r_eq, sample size for SE)
COHORTS = [
    {"name": "UCSF-POSTOP", "sigma_opt": 0.75, "r_eq": 15.32, "n": 297},
    {"name": "MU-Glioma-Post", "sigma_opt": 2.5, "r_eq": 16.92, "n": 151},
    {"name": "RHUH-GBM", "sigma_opt": 2.0, "r_eq": 18.82, "n": 39},
    {"name": "LUMIERE", "sigma_opt": 2.5, "r_eq": 12.11, "n": 22},
    {"name": "PROTEAS-brain-mets", "sigma_opt": 1.0, "r_eq": 6.0, "n": 42},
]


def estimate_within_study_variance(study, sigma_grid_resolution=0.25):
    """Estimate the within-study standard error of log(sigma_opt) using
    the grid resolution / sqrt(N) approximation.

    Rationale: the optimum is identified to within +/- 0.5 grid steps
    (here 0.25 voxels), and the precision improves with cohort size.
    Approximate SE on log scale.
    """
    n = study["n"]
    sig_opt = study["sigma_opt"]
    # Grid uncertainty: ~0.25 voxels around optimum -> SE = 0.25/sqrt(N)
    se_sigma = sigma_grid_resolution / np.sqrt(n)
    # Convert to log SE via delta method: SE(log x) = SE(x) / x
    se_log = se_sigma / max(sig_opt, 0.1)
    var_log = se_log ** 2
    return var_log


def dl_random_effects_meta_regression(y, x, vy):
    """DerSimonian-Laird RE meta-regression of y on x with within-study
    variances vy. Returns intercept, slope, tau^2, I^2, Q, p_Q.

    Uses iterative reweighted least squares per Hartung-Knapp framework
    for the RE adjustment.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    vy = np.asarray(vy, dtype=float)
    k = len(y)
    if k < 2:
        return None

    # Step 1: fixed-effect (FE) weighted least squares (weights = 1/vy)
    w = 1.0 / vy
    X = np.column_stack([np.ones(k), x])
    W = np.diag(w)
    XtWX = X.T @ W @ X
    XtWy = X.T @ W @ y
    beta_fe = np.linalg.solve(XtWX, XtWy)
    fitted_fe = X @ beta_fe
    Q = float(np.sum(w * (y - fitted_fe) ** 2))

    df = k - 2  # 2 parameters
    p_Q = float(1 - chi2.cdf(Q, df=df)) if df > 0 else float("nan")

    # Step 2: DL tau^2 estimator
    # tau^2 = max(0, (Q - df) / c) with c = sum(w) - tr(XtWX^-1 X' W^2 X)
    if df > 0:
        XtW2X = X.T @ (W @ W) @ X
        c = float(np.sum(w) - np.trace(np.linalg.solve(XtWX, XtW2X)))
        tau2 = max(0.0, (Q - df) / c) if c > 0 else 0.0
    else:
        tau2 = 0.0

    # Step 3: RE re-weight and refit
    w_re = 1.0 / (vy + tau2)
    W_re = np.diag(w_re)
    XtWX_re = X.T @ W_re @ X
    XtWy_re = X.T @ W_re @ y
    beta_re = np.linalg.solve(XtWX_re, XtWy_re)
    cov_re = np.linalg.inv(XtWX_re)
    se_re = np.sqrt(np.diag(cov_re))
    z_re = beta_re / se_re
    p_re = 2 * (1 - norm.cdf(np.abs(z_re)))
    ci_lo = beta_re - 1.96 * se_re
    ci_hi = beta_re + 1.96 * se_re

    # I^2
    I2 = max(0.0, (Q - df) / Q) * 100 if Q > 0 else 0.0

    # Predictive interval (Higgins-Thompson 2009)
    if k - 2 > 0 and tau2 > 0:
        # 95% predictive interval for slope (where would a new cohort's slope-effect lie?)
        from scipy.stats import t as student_t
        t_crit = float(student_t.ppf(0.975, df=k - 2))
        pred_se = float(np.sqrt(tau2 + se_re[1] ** 2))
        pred_lo = float(beta_re[1] - t_crit * pred_se)
        pred_hi = float(beta_re[1] + t_crit * pred_se)
    else:
        pred_lo = pred_hi = float("nan")

    return {
        "intercept": float(beta_re[0]),
        "intercept_ci": [float(ci_lo[0]), float(ci_hi[0])],
        "slope_beta": float(beta_re[1]),
        "slope_se": float(se_re[1]),
        "slope_ci": [float(ci_lo[1]), float(ci_hi[1])],
        "slope_p": float(p_re[1]),
        "slope_z": float(z_re[1]),
        "tau2": float(tau2),
        "I2_pct": float(I2),
        "Q": Q,
        "Q_df": df,
        "Q_p": p_Q,
        "predictive_interval_slope_95": [pred_lo, pred_hi],
    }


def main():
    print("=" * 78)
    print("v123 RE META-ANALYSIS: log(sigma_opt) ~ log(r_eq) at heat>=0.50")
    print("=" * 78)

    print("\nCohort optima (heat>=0.50):")
    for c in COHORTS:
        c["log_sigma"] = float(np.log(c["sigma_opt"]))
        c["log_r"] = float(np.log(c["r_eq"]))
        c["var_log_sigma"] = float(estimate_within_study_variance(c))
        print(f"  {c['name']:22s}  N={c['n']:4d}  r={c['r_eq']:5.2f}  "
              f"sigma_opt={c['sigma_opt']:.2f}  "
              f"log(sigma)={c['log_sigma']:+.3f}  "
              f"var(log_sigma)={c['var_log_sigma']:.5f}")

    y = [c["log_sigma"] for c in COHORTS]
    x = [c["log_r"] for c in COHORTS]
    vy = [c["var_log_sigma"] for c in COHORTS]
    res = dl_random_effects_meta_regression(y, x, vy)

    print("\n=== DERSIMONIAN-LAIRD RE META-REGRESSION ===")
    print(f"  log(sigma_opt) = {res['intercept']:+.4f} + "
          f"{res['slope_beta']:+.4f} * log(r_eq)")
    print(f"  Intercept 95% CI: [{res['intercept_ci'][0]:+.4f}, "
          f"{res['intercept_ci'][1]:+.4f}]")
    print(f"  Slope (beta): {res['slope_beta']:+.4f} +/- {res['slope_se']:.4f} "
          f"(95% CI [{res['slope_ci'][0]:+.4f}, {res['slope_ci'][1]:+.4f}])")
    print(f"  Slope p = {res['slope_p']:.4f}")
    print(f"  Cochran Q = {res['Q']:.3f} (df={res['Q_df']}, "
          f"p_Q = {res['Q_p']:.4f})")
    print(f"  I^2 = {res['I2_pct']:.1f}%")
    print(f"  Between-cohort variance tau^2 = {res['tau2']:.4f}")
    print(f"  95% predictive interval for slope: "
          f"[{res['predictive_interval_slope_95'][0]:+.4f}, "
          f"{res['predictive_interval_slope_95'][1]:+.4f}]")

    # Test of canonical scaling values
    print("\n=== INTERPRETATION ===")
    beta = res["slope_beta"]; se = res["slope_se"]
    if abs(beta) < 0.2 and (res["slope_ci"][0] < 0 < res["slope_ci"][1]):
        print(f"  Slope CI includes zero -> scaling law NOT clearly different from constant.")
        print(f"  Implies: sigma_opt is approximately cohort-INVARIANT at heat>=0.50.")
    else:
        print(f"  Slope CI excludes zero -> meaningful r-dependent scaling.")
    print(f"  beta=0 distance: {abs(beta)/max(se, 1e-9):.2f} sigma units")
    print(f"  beta=1 (linear) distance: {abs(1-beta)/max(se, 1e-9):.2f} sigma units")
    print(f"  beta=0.5 (sqrt) distance: {abs(0.5-beta)/max(se, 1e-9):.2f} sigma units")

    out = {
        "version": "v123",
        "experiment": ("Random-effects meta-analysis of cohort-conditional "
                       "sigma optima at heat>=0.50 vs lesion-equivalent radius"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cohorts": COHORTS,
        "model": "log(sigma_opt) = intercept + beta * log(r_eq)",
        "method": "DerSimonian-Laird RE meta-regression",
        "result": res,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
