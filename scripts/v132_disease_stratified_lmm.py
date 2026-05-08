"""v132: Disease-stratified LMM combining all 5 cohorts.

Motivation. v124 found a clean per-patient sigma scaling law on 4
glioma cohorts (beta = +1.273 [+1.158, +1.389]). v127 found that
this does NOT generalise to PROTEAS-brain-mets (slope = -0.383).

v132 combines all 5 cohorts into a single LMM with disease as a
fixed effect:
  log(sigma_opt) ~ log(r_eq) * disease + (1|cohort)

If the log(r_eq) : disease interaction term has CI excluding zero,
that's formal evidence of disease-specificity.

Outputs:
    Nature_project/05_results/v132_disease_stratified_lmm.json
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import t as student_t

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
PROTEAS_CSV = Path(r"C:\Users\kamru\Downloads\RTO_paper\source_data\v127_loco_sigma_scaling_per_patient.csv")
OUT_JSON = RESULTS / "v132_disease_stratified_lmm.json"

SIGMA_GRID = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
HEAT_THRESHOLD = 0.5
COHORT_DISEASE = {
    "UCSF-POSTOP": "glioma",
    "MU-Glioma-Post": "glioma",
    "RHUH-GBM": "glioma",
    "LUMIERE": "glioma",
    "PROTEAS-brain-mets": "brain_mets",
}


def heat_kernel(mask, sigma):
    if mask.sum() == 0: return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0: h = h / h.max()
    return h.astype(np.float32)


def coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0: return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def equivalent_radius(mask):
    n = float(mask.sum())
    if n == 0: return 0.0
    return float((3 * n / (4 * np.pi)) ** (1 / 3))


def per_patient_optima_cache3d(cohort: str):
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    out = []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists(): continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0: continue
        r_eq = equivalent_radius(m)
        if r_eq < 1.0: continue
        best_sig = None; best_cov = -1.0
        for sig in SIGMA_GRID:
            h = heat_kernel(m, sig)
            cov = coverage(t, h >= HEAT_THRESHOLD)
            if np.isnan(cov): continue
            if cov > best_cov:
                best_cov = cov; best_sig = sig
        if best_sig is None or best_cov <= 0: continue
        out.append({"cohort": cohort, "disease": COHORT_DISEASE[cohort],
                     "pid": pid, "r_eq": r_eq, "log_r_eq": float(np.log(r_eq)),
                     "sigma_opt": best_sig, "log_sigma_opt": float(np.log(best_sig)),
                     "best_coverage": best_cov})
    return out


def fit_lmm_with_interaction(records):
    """Fit log(sigma_opt) ~ log(r_eq) * disease + (1|cohort)
    with iterative reweighting REML."""
    n = len(records)
    log_r = np.array([r["log_r_eq"] for r in records], dtype=float)
    log_s = np.array([r["log_sigma_opt"] for r in records], dtype=float)
    is_metast = np.array([1.0 if r["disease"] == "brain_mets" else 0.0
                            for r in records], dtype=float)
    cohort_to_int = {c: i for i, c in enumerate(sorted(set(r["cohort"] for r in records)))}
    g = np.array([cohort_to_int[r["cohort"]] for r in records], dtype=int)
    n_groups = int(g.max()) + 1

    # Design: intercept, log_r, is_metast, log_r:is_metast
    X = np.column_stack([np.ones(n), log_r, is_metast, log_r * is_metast])
    beta_names = ["intercept", "log_r_eq", "is_metast", "log_r_eq:is_metast"]

    # OLS init
    beta = np.linalg.lstsq(X, log_s, rcond=None)[0]
    sigma_e2 = float(np.var(log_s - X @ beta, ddof=4))
    tau2 = 0.0

    for it in range(50):
        resid = log_s - X @ beta
        u = np.zeros(n_groups)
        for j in range(n_groups):
            mask = g == j
            n_j = int(mask.sum())
            if n_j > 0:
                u[j] = (tau2 / (tau2 + sigma_e2 / n_j)) * resid[mask].mean()
        y_adj = log_s - u[g]
        beta_new = np.linalg.lstsq(X, y_adj, rcond=None)[0]
        resid_full = log_s - X @ beta_new - u[g]
        sigma_e2_new = float(np.var(resid_full, ddof=4))
        tau2_new = max(0.0, float(np.var(u, ddof=1)) if n_groups > 1 else 0.0)
        if abs(beta_new[3] - beta[3]) < 1e-6 and abs(tau2_new - tau2) < 1e-6:
            beta = beta_new; sigma_e2 = sigma_e2_new; tau2 = tau2_new
            break
        beta = beta_new; sigma_e2 = sigma_e2_new; tau2 = tau2_new

    # Standard errors via marginal model
    XtX = X.T @ X
    icc = tau2 / max(tau2 + sigma_e2, 1e-9)
    eff_n = max(1.0, n * (1 - icc) / (1 + (n - 1) * icc) * n_groups)
    cov_beta = np.linalg.inv(XtX) * sigma_e2 * (n / max(eff_n, 1.0))
    se_beta = np.sqrt(np.diag(cov_beta))

    df = max(n - 4, 1)
    t_crit = float(student_t.ppf(0.975, df=df))
    ci_lo = beta - t_crit * se_beta
    ci_hi = beta + t_crit * se_beta
    t_stat = beta / se_beta
    p_vals = 2 * (1 - student_t.cdf(np.abs(t_stat), df=df))

    return {
        "n": n,
        "n_groups": n_groups,
        "beta": [float(b) for b in beta],
        "beta_names": beta_names,
        "se": [float(s) for s in se_beta],
        "ci_lo": [float(b) for b in ci_lo],
        "ci_hi": [float(b) for b in ci_hi],
        "p_values": [float(p) for p in p_vals],
        "tau2": tau2,
        "sigma_e2": sigma_e2,
        "ICC_pct": float(icc * 100),
    }


def main():
    print("=" * 78)
    print("v132 DISEASE-STRATIFIED LMM combining 5 cohorts")
    print(f"  glioma cohorts: UCSF, MU-Glioma-Post, RHUH-GBM, LUMIERE")
    print(f"  brain-mets cohort: PROTEAS-brain-mets")
    print(f"  threshold: heat >= {HEAT_THRESHOLD}")
    print("=" * 78)

    all_records = []
    for cohort in ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]:
        recs = per_patient_optima_cache3d(cohort)
        print(f"  {cohort}: {len(recs)} patients")
        all_records.extend(recs)

    # PROTEAS from v127 CSV
    if PROTEAS_CSV.exists():
        with open(PROTEAS_CSV) as f:
            proteas_rows = list(csv.DictReader(f))
        # Each PROTEAS row corresponds to a follow-up; we use per-follow-up sigma_opt
        n_proteas = 0
        for row in proteas_rows:
            sig_str = row.get("sigma_opt_actual_thr_0.5", "")
            r_eq_str = row.get("r_eq", "")
            if not sig_str or not r_eq_str: continue
            try:
                sig_opt = float(sig_str); r_eq = float(r_eq_str)
            except ValueError:
                continue
            if sig_opt <= 0 or r_eq < 1.0: continue
            all_records.append({"cohort": "PROTEAS-brain-mets", "disease": "brain_mets",
                                  "pid": row["pid"], "r_eq": r_eq,
                                  "log_r_eq": float(np.log(r_eq)),
                                  "sigma_opt": sig_opt,
                                  "log_sigma_opt": float(np.log(sig_opt))})
            n_proteas += 1
        print(f"  PROTEAS-brain-mets: {n_proteas} follow-ups (from v127 CSV)")
    else:
        print("  v127 CSV not found; cannot include PROTEAS")

    n = len(all_records)
    print(f"\n  Total: N = {n} observations")
    n_glioma = sum(1 for r in all_records if r["disease"] == "glioma")
    n_brain = sum(1 for r in all_records if r["disease"] == "brain_mets")
    print(f"  Glioma: {n_glioma}; Brain-mets: {n_brain}")

    res = fit_lmm_with_interaction(all_records)

    print("\n=== LMM RESULT ===")
    for i, name in enumerate(res["beta_names"]):
        marker = "**SIG**" if (res["ci_lo"][i] > 0 or res["ci_hi"][i] < 0) else ""
        print(f"  {name:25s} = {res['beta'][i]:+.4f} +/- {res['se'][i]:.4f} "
              f"(95% CI [{res['ci_lo'][i]:+.4f}, {res['ci_hi'][i]:+.4f}]) "
              f"p={res['p_values'][i]:.4f} {marker}")
    print(f"\n  ICC = {res['ICC_pct']:.1f}%; tau^2 = {res['tau2']:.4f}; "
          f"sigma_e^2 = {res['sigma_e2']:.4f}")

    # Interpretation
    print("\n=== INTERPRETATION ===")
    interaction_idx = res["beta_names"].index("log_r_eq:is_metast")
    int_lo = res["ci_lo"][interaction_idx]
    int_hi = res["ci_hi"][interaction_idx]
    int_excludes_zero = (int_lo > 0 or int_hi < 0)
    print(f"  Interaction log(r_eq):is_metast: "
          f"{res['beta'][interaction_idx]:+.4f} [{int_lo:+.4f}, {int_hi:+.4f}]")
    print(f"  CI excludes zero? {int_excludes_zero}")

    if int_excludes_zero:
        glioma_slope = res["beta"][1]  # log_r_eq main effect
        metast_slope = glioma_slope + res["beta"][interaction_idx]
        print(f"\n  --> Disease-specific scaling LAW CONFIRMED:")
        print(f"      Glioma cohorts: log(sigma_opt) slope on log(r_eq) = {glioma_slope:+.4f}")
        print(f"      Brain-mets:     log(sigma_opt) slope on log(r_eq) = {metast_slope:+.4f}")
    else:
        print(f"\n  --> Interaction not significant; disease may not modify scaling.")

    out = {
        "version": "v132",
        "experiment": "Disease-stratified LMM combining 5 cohorts on per-patient sigma_opt",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": "log(sigma_opt) ~ log(r_eq) * disease + (1|cohort)",
        "n_observations": n,
        "n_glioma": n_glioma,
        "n_brain_mets": n_brain,
        "result": res,
        "interaction_excludes_zero": bool(int_excludes_zero),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}")


if __name__ == "__main__":
    main()
