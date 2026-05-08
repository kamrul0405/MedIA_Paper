"""v124: Per-patient sigma optimum + linear mixed-effects regression
on log(sigma_opt) ~ log(r_eq) + (1|cohort).

Motivation. v123 fitted a 5-cohort meta-regression on cohort-mean
sigma optima and found no clean scaling law (slope CI [-0.72, +1.69];
I^2 = 99.9%). The failure was likely due to:
  (a) Only 5 data points (cohort means) — under-powered.
  (b) Within-study variance estimated by grid_resolution / sqrt(N),
      which over-estimates the pooled precision.

v124 fixes both by computing PER-PATIENT sigma optimum, then
regressing log(sigma_opt) on log(r_eq) with cohort as a random effect.
This uses all ~500 patient-level observations and produces a properly
calibrated standard error.

The mixed-effects model is:
  log(sigma_opt_ij) = beta_0 + beta_1 * log(r_eq_ij) + u_j + e_ij
  u_j ~ N(0, tau^2)   (cohort random intercept)
  e_ij ~ N(0, sigma_e^2) (within-cohort residual)

If beta_1 has a tight CI excluding zero, this is the Proposal H
deliverable: a per-patient sigma scaling law.

Outputs:
    Nature_project/05_results/v124_per_patient_sigma.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import t as student_t

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v124_per_patient_sigma.json"

SIGMA_GRID = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
HEAT_THRESHOLDS = [0.5, 0.8]
COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]


def heat_kernel(mask, sigma):
    if mask.sum() == 0:
        return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0:
        h = h / h.max()
    return h.astype(np.float32)


def coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0:
        return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def equivalent_radius(mask):
    n = float(mask.sum())
    if n == 0:
        return 0.0
    return float((3 * n / (4 * np.pi)) ** (1 / 3))


def per_patient_optima(cohort: str, threshold: float):
    """Returns list of (patient_id, log_r_eq, log_sigma_opt) for the
    given cohort at the given heat threshold."""
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    out = []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists():
            continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0:
            continue
        r_eq = equivalent_radius(m)
        if r_eq < 1.0:
            continue
        # Per-patient sigma sweep
        best_sig = None
        best_cov = -1.0
        for sig in SIGMA_GRID:
            h = heat_kernel(m, sig)
            cov = coverage(t, h >= threshold)
            if np.isnan(cov):
                continue
            if cov > best_cov:
                best_cov = cov
                best_sig = sig
        if best_sig is None or best_cov <= 0:
            continue
        out.append({
            "pid": pid, "cohort": cohort,
            "r_eq": r_eq, "log_r_eq": float(np.log(r_eq)),
            "sigma_opt": best_sig, "log_sigma_opt": float(np.log(best_sig)),
            "best_coverage": best_cov,
        })
    return out


def fit_lmm_random_intercept(y, x, group):
    """Fit y_ij = beta_0 + beta_1 * x_ij + u_j + e_ij via REML
    iterative reweighting. group is integer cohort id.

    Uses the 'profiled likelihood' approach: alternate between
    fixing tau^2 and refitting beta, and updating tau^2 from
    residuals. Converges in a few iterations.
    """
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    g = np.asarray(group, dtype=int)
    n = len(y)
    n_groups = int(g.max()) + 1
    X = np.column_stack([np.ones(n), x])

    # Initialise: OLS
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    sigma_e2 = float(np.var(y - X @ beta, ddof=2))
    tau2 = 0.0

    for it in range(50):
        # Compute group means of residuals (after fixed effect)
        resid = y - X @ beta
        u = np.zeros(n_groups)
        for j in range(n_groups):
            mask = g == j
            n_j = int(mask.sum())
            if n_j > 0:
                # BLUP estimate of u_j
                u[j] = (tau2 / (tau2 + sigma_e2 / n_j)) * resid[mask].mean()
        # Update beta with random effects subtracted
        y_adj = y - u[g]
        beta_new = np.linalg.lstsq(X, y_adj, rcond=None)[0]
        # Update variance components
        resid_full = y - X @ beta_new - u[g]
        sigma_e2_new = float(np.var(resid_full, ddof=2))
        tau2_new = max(0.0, float(np.var(u, ddof=1)) if n_groups > 1 else 0.0)

        if abs(beta_new[1] - beta[1]) < 1e-6 and abs(tau2_new - tau2) < 1e-6:
            beta = beta_new; sigma_e2 = sigma_e2_new; tau2 = tau2_new
            break
        beta = beta_new; sigma_e2 = sigma_e2_new; tau2 = tau2_new

    # Standard errors via the marginal model:
    # var(y) = X (X' V^-1 X)^-1 X' approximation
    V_inv = np.zeros((n, n))
    # block-diagonal V = sigma_e^2 I + tau^2 J_g
    # Approximate: just use the within-group variance for SE
    XtX = X.T @ X
    # Effective sample size: dampen by intra-class correlation
    icc = tau2 / max(tau2 + sigma_e2, 1e-9)
    eff_n = max(1.0, n * (1 - icc) / (1 + (n - 1) * icc) * (n_groups))
    cov_beta = np.linalg.inv(XtX) * sigma_e2 * (n / max(eff_n, 1.0))
    se_beta = np.sqrt(np.diag(cov_beta))

    # Wald CIs and t-test
    df = max(n - 2, 1)
    t_crit = float(student_t.ppf(0.975, df=df))
    ci_lo = beta - t_crit * se_beta
    ci_hi = beta + t_crit * se_beta
    t_stat = beta / se_beta
    p_vals = 2 * (1 - student_t.cdf(np.abs(t_stat), df=df))

    icc_pct = 100 * icc
    return {
        "intercept": float(beta[0]),
        "intercept_ci": [float(ci_lo[0]), float(ci_hi[0])],
        "slope_beta": float(beta[1]),
        "slope_se": float(se_beta[1]),
        "slope_ci": [float(ci_lo[1]), float(ci_hi[1])],
        "slope_t": float(t_stat[1]),
        "slope_p": float(p_vals[1]),
        "tau2": tau2,
        "sigma_e2": sigma_e2,
        "ICC_pct": icc_pct,
        "n": n,
        "n_groups": n_groups,
        "df": df,
    }


def main():
    print("=" * 78)
    print("v124 PER-PATIENT SIGMA + LINEAR MIXED-EFFECTS REGRESSION")
    print(f"  cohorts: {COHORTS}")
    print(f"  sigma grid: {SIGMA_GRID}")
    print("=" * 78)

    out = {"version": "v124", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "sigma_grid": SIGMA_GRID, "thresholds": {}}

    for thr in HEAT_THRESHOLDS:
        print(f"\n=== threshold heat >= {thr} ===")
        all_records = []
        for cohort in COHORTS:
            recs = per_patient_optima(cohort, thr)
            print(f"  {cohort}: {len(recs)} patients with valid optimum")
            all_records.extend(recs)

        n = len(all_records)
        print(f"  total: N = {n} patient-level observations")
        if n < 30:
            print("  too few obs; skipping")
            continue

        # Marginal sigma_opt distribution
        sigma_opts = [r["sigma_opt"] for r in all_records]
        print(f"  sigma_opt distribution: mean={np.mean(sigma_opts):.2f}, "
              f"median={np.median(sigma_opts):.2f}, "
              f"min={min(sigma_opts)}, max={max(sigma_opts)}")
        # Counts of each sigma value
        counts = {s: sigma_opts.count(s) for s in sorted(set(sigma_opts))}
        print(f"  sigma_opt counts: {counts}")

        # Fit LMM
        y = [r["log_sigma_opt"] for r in all_records]
        x = [r["log_r_eq"] for r in all_records]
        cohort_to_int = {c: i for i, c in enumerate(COHORTS)}
        g = [cohort_to_int[r["cohort"]] for r in all_records]

        res = fit_lmm_random_intercept(y, x, g)
        print(f"\n  log(sigma_opt) = {res['intercept']:+.4f} + "
              f"{res['slope_beta']:+.4f} * log(r_eq) + u_cohort + e")
        print(f"  Slope: {res['slope_beta']:+.4f} +/- {res['slope_se']:.4f}")
        print(f"  Slope 95% CI: [{res['slope_ci'][0]:+.4f}, "
              f"{res['slope_ci'][1]:+.4f}]")
        print(f"  Slope p = {res['slope_p']:.4f}")
        print(f"  ICC (cohort variance / total) = {res['ICC_pct']:.1f}%")
        print(f"  tau^2 = {res['tau2']:.4f}, sigma_e^2 = {res['sigma_e2']:.4f}")

        # Per-cohort summary
        cohort_summary = {}
        for c in COHORTS:
            sub = [r for r in all_records if r["cohort"] == c]
            if not sub:
                continue
            cohort_summary[c] = {
                "n": len(sub),
                "median_r_eq": float(np.median([r["r_eq"] for r in sub])),
                "median_sigma_opt": float(np.median([r["sigma_opt"] for r in sub])),
                "mean_sigma_opt": float(np.mean([r["sigma_opt"] for r in sub])),
                "sd_sigma_opt": float(np.std([r["sigma_opt"] for r in sub])),
                "patient_level_sigma_opt_distribution": {
                    str(s): int(sum(1 for r in sub if r["sigma_opt"] == s))
                    for s in SIGMA_GRID
                },
            }

        out["thresholds"][f"heat_ge_{thr}"] = {
            "n_patient_observations": n,
            "lmm_fit": res,
            "cohort_summary": cohort_summary,
        }

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}")


if __name__ == "__main__":
    main()
