"""v195: Multimodal Cox PH prognosis — does kernel add value
beyond established clinical features? — round 33.

Senior-Nature-reviewer-driven extension after round 32's honest
negative (kernel alone doesn't predict OS): test whether the
training-free kernel-predicted outgrowth volume adds INDEPENDENT
prognostic information when combined with established clinical
features in a multivariate Cox proportional hazards model.

Method (RHUH-GBM, n=39):
  Clinical features extracted from clinical_data_TCIA_RHUH-GBM.csv:
    - Age (continuous)
    - Preoperative KPS (continuous)
    - IDH status (mutant=1, wild-type=0, NOS=NA)
    - WHO grade (continuous; mostly 4)
    - Preoperative contrast-enhancing tumor volume (cm^3)
    - Postoperative residual tumor (cm^3)
    - EOR % (continuous)
    - Adjuvant RT+TMZ (binary)
  Plus:
    - V_kernel sigma=3 (from v194)

Models:
  M0: clinical-only Cox (Age + KPS + IDH + EOR + RT_TMZ)
  M1: clinical + V_kernel Cox

Tests:
  - Univariate Cox for each feature
  - Multivariate Cox for M0 and M1
  - Likelihood ratio test (M0 nested in M1)
  - Concordance (C-index) for M0 vs M1
  - Bootstrap 95% CI on Delta C-index

Outputs:
  Nature_project/05_results/v195_multimodal_prognosis.json
"""
from __future__ import annotations

import csv
import json
import re
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.stats import chi2 as chi2dist, norm

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CLINICAL_CSV = Path(r"C:\Users\kamru\Downloads\clinical_data_TCIA_RHUH-GBM.csv")
V194_CSV = RESULTS / "v194_kernel_survival_per_patient.csv"
OUT_JSON = RESULTS / "v195_multimodal_prognosis.json"
N_BOOT = 1000


# ============================================================================
# Cox PH (multivariate via Newton-Raphson)
# ============================================================================

def cox_ph_multivariate(times, events, X):
    """Multivariate Cox PH via scipy.optimize on negative log partial likelihood.

    Uses Breslow approximation for ties (sorted by time descending,
    risk set at i = all j with j >= i in descending-time order).
    """
    from scipy.optimize import minimize
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=float)
    X = np.atleast_2d(np.asarray(X, dtype=float))
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    n, p = X.shape
    order = np.argsort(-times)
    Z = X[order]
    e = events[order]

    def neg_log_pl(beta):
        eta = Z @ beta
        # Numerical stability: subtract max eta from each cumulative sum
        # log-sum-exp trick
        # cumsum from front (in time-descending order = risk set growing)
        max_eta = np.maximum.accumulate(eta)
        # shifted sum: cumsum(exp(eta - max_eta)); careful with running max
        # Simpler: compute log(cumsum(exp(eta))) via log-sum-exp running
        log_S = np.zeros(n)
        running_max = -np.inf
        running_sum_exp = 0.0
        for i in range(n):
            new_max = max(running_max, eta[i])
            running_sum_exp = (np.exp(running_max - new_max) * running_sum_exp
                                + np.exp(eta[i] - new_max))
            running_max = new_max
            log_S[i] = running_max + np.log(running_sum_exp)
        # log partial likelihood at events
        log_pl = float((eta[e == 1] - log_S[e == 1]).sum())
        return -log_pl

    beta0 = np.zeros(p)
    result = minimize(neg_log_pl, beta0, method="L-BFGS-B",
                      options={"maxiter": 200})
    beta = result.x
    log_pl = -result.fun

    # Estimate SE via numerical Hessian at MLE
    eps = 1e-4
    H = np.zeros((p, p))
    f0 = neg_log_pl(beta)
    for i in range(p):
        for j in range(p):
            if i <= j:
                bp = beta.copy()
                bp[i] += eps
                bp[j] += eps
                f_pp = neg_log_pl(bp)
                bp = beta.copy()
                bp[i] += eps
                bp[j] -= eps
                f_pm = neg_log_pl(bp)
                bp = beta.copy()
                bp[i] -= eps
                bp[j] += eps
                f_mp = neg_log_pl(bp)
                bp = beta.copy()
                bp[i] -= eps
                bp[j] -= eps
                f_mm = neg_log_pl(bp)
                H[i, j] = (f_pp - f_pm - f_mp + f_mm) / (4 * eps * eps)
                H[j, i] = H[i, j]
    # H is the Hessian of NEGATIVE log-PL = -Hessian(log-PL).
    # Standard error from inverse:
    try:
        cov = np.linalg.inv(H)
        se = np.sqrt(np.maximum(np.diag(cov), 0))
    except np.linalg.LinAlgError:
        se = np.full(p, np.nan)

    return {
        "beta": beta.tolist(),
        "se": se.tolist(),
        "log_pl": float(log_pl),
        "n_iter": int(result.nit),
        "converged": bool(result.success),
    }


def cox_p_values(beta, se):
    z = np.asarray(beta) / np.maximum(np.asarray(se), 1e-12)
    p = 2 * (1 - norm.cdf(np.abs(z)))
    return p.tolist()


def concordance(times, events, risk_scores):
    """Harrell's C-index."""
    times = np.asarray(times)
    events = np.asarray(events)
    risk_scores = np.asarray(risk_scores)
    n = len(times)
    n_pairs = 0
    n_concordant = 0
    n_ties = 0
    for i in range(n):
        for j in range(i+1, n):
            if events[i] == 0 and events[j] == 0:
                continue  # neither event observed
            # Lower time should have higher risk
            if times[i] < times[j]:
                if events[i] != 1:
                    continue  # i censored before j event - uncomparable
                n_pairs += 1
                if risk_scores[i] > risk_scores[j]:
                    n_concordant += 1
                elif risk_scores[i] == risk_scores[j]:
                    n_ties += 1
            elif times[j] < times[i]:
                if events[j] != 1:
                    continue
                n_pairs += 1
                if risk_scores[j] > risk_scores[i]:
                    n_concordant += 1
                elif risk_scores[i] == risk_scores[j]:
                    n_ties += 1
            # ties in time skipped
    if n_pairs == 0:
        return float("nan")
    return (n_concordant + 0.5 * n_ties) / n_pairs


def main():
    print("=" * 78, flush=True)
    print("v195 MULTIMODAL COX PROGNOSIS — round 33", flush=True)
    print("=" * 78, flush=True)

    # ---------- Load clinical data ----------
    clinical = {}
    with CLINICAL_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        # Identify columns
        pid_col = "Patient ID"
        age_col = "Age"
        sex_col = "Sex"
        kps_col = "Preoperative KPS"
        idh_col = next((c for c in cols if "IDH" in c.upper()), None)
        who_col = next((c for c in cols if "WHO grade" in c), None)
        eor_pct_col = next((c for c in cols if "Extent of resection" in c
                              and "%" in c), None)
        eor_cat_col = next((c for c in cols if "EOR =" in c), None)
        rt_tmz_col = next((c for c in cols if "Adjuvant therapy" in c), None)
        pfs_col = next((c for c in cols if "PFS" in c.upper()
                          and "day" in c.lower()), None)
        os_col = next((c for c in cols if "Overall survival" in c
                         and "day" in c.lower()), None)
        cens_col = next((c for c in cols if "censor" in c.lower()), None)
        prev_treat_col = next((c for c in cols if "Previous treatment" in c),
                                None)
        preop_vol_col = next((c for c in cols if "Preoperative" in c
                                 and "tumor volume" in c), None)
        postop_vol_col = next((c for c in cols if "Postoperative" in c
                                  and "residual tumor" in c), None)

        def safe_float(s):
            s = (s or "").strip()
            try:
                return float(re.sub(r"[^\d.\-+]", "", s)) if s else None
            except (ValueError, TypeError):
                return None

        for row in reader:
            pid = row[pid_col].strip()
            try:
                event = 0 if (cens_col and row[cens_col].strip().lower() == "yes") else 1
            except Exception:
                event = None
            idh_raw = (row.get(idh_col, "") or "").lower()
            if "mut" in idh_raw and "nos" not in idh_raw:
                idh = 1.0
            elif "wild" in idh_raw or "wt" in idh_raw:
                idh = 0.0
            else:
                idh = None
            rt_tmz_raw = (row.get(rt_tmz_col, "") or "").upper()
            rt_tmz = 1.0 if ("RT" in rt_tmz_raw and "TMZ" in rt_tmz_raw) else 0.0
            eor_cat = (row.get(eor_cat_col, "") or "").upper()
            gtr = 1.0 if "GTR" in eor_cat else 0.0
            clinical[pid] = {
                "age": safe_float(row.get(age_col)),
                "kps": safe_float(row.get(kps_col)),
                "idh": idh,
                "who_grade": safe_float(row.get(who_col)),
                "eor_pct": safe_float(row.get(eor_pct_col)),
                "gtr": gtr,
                "rt_tmz": rt_tmz,
                "preop_vol": safe_float(row.get(preop_vol_col)),
                "postop_vol": safe_float(row.get(postop_vol_col)),
                "pfs": safe_float(row.get(pfs_col)),
                "os": safe_float(row.get(os_col)),
                "event": event,
            }

    # ---------- Load V_kernel from v194 ----------
    v_kernel = {}
    with V194_CSV.open() as f:
        for row in csv.DictReader(f):
            try:
                v_kernel[row["pid"].strip()] = float(row["V_kernel_sigma3"])
            except (ValueError, KeyError):
                continue

    # ---------- Build merged table ----------
    pids = sorted(set(clinical.keys()) & set(v_kernel.keys()))
    rows = []
    for pid in pids:
        c = clinical[pid]
        if c["os"] is None or c["event"] is None:
            continue
        rows.append({
            "pid": pid,
            "age": c["age"],
            "kps": c["kps"],
            "idh": c["idh"],
            "gtr": c["gtr"],
            "rt_tmz": c["rt_tmz"],
            "preop_vol": c["preop_vol"],
            "postop_vol": c["postop_vol"],
            "v_kernel_s3": v_kernel[pid],
            "os": c["os"],
            "event": c["event"],
        })
    print(f"  {len(rows)} patients with full clinical + kernel data",
          flush=True)

    # ---------- Univariate Cox per feature ----------
    times = np.array([r["os"] for r in rows], dtype=float)
    events = np.array([r["event"] for r in rows], dtype=float)
    print(f"  {int(events.sum())} events / {len(times)} total "
          f"({100*events.sum()/len(times):.0f}% event rate)", flush=True)

    candidate_features = ["age", "kps", "idh", "gtr", "rt_tmz",
                            "preop_vol", "postop_vol", "v_kernel_s3"]
    univariate = {}
    for feat in candidate_features:
        x = np.array([r[feat] for r in rows], dtype=float)
        # Drop patients with missing
        mask = ~np.isnan(x)
        if mask.sum() < 10:
            continue
        x_v = x[mask]
        t_v = times[mask]
        e_v = events[mask]
        # Standardize for HR-per-SD interpretation
        if np.std(x_v) == 0:
            continue
        x_z = (x_v - x_v.mean()) / x_v.std()
        result = cox_ph_multivariate(t_v, e_v, x_z.reshape(-1, 1))
        if result is None:
            continue
        beta = result["beta"][0]
        se = result["se"][0]
        z = beta / max(se, 1e-12)
        p = float(2 * (1 - norm.cdf(abs(z))))
        univariate[feat] = {
            "n": int(mask.sum()),
            "beta": float(beta),
            "se": float(se),
            "HR_per_SD": float(np.exp(beta)),
            "p_value": p,
        }
        print(f"    {feat:15s}  n={mask.sum()}  HR/SD={np.exp(beta):.3f}  "
              f"p={p:.4f}", flush=True)

    # ---------- Multivariate Cox: M0 (clinical only) vs M1 (clinical + kernel) ----------
    # Use complete-case analysis with the most-significant clinical features
    print("\n=== Multivariate Cox models (complete-case) ===", flush=True)
    # Pre-define M0 features (clinical only) and M1 (M0 + kernel)
    m0_feats = ["age", "kps", "idh", "gtr", "rt_tmz"]
    m1_feats = m0_feats + ["v_kernel_s3"]

    def build_X(rows, feats):
        X = np.array([[r[f] for f in feats] for r in rows], dtype=float)
        # Standardize each column
        means = X.mean(axis=0)
        stds = X.std(axis=0)
        stds[stds == 0] = 1
        Xz = (X - means) / stds
        return Xz, means, stds

    # Drop patients with missing clinical features
    complete_rows = [r for r in rows
                       if all(r[f] is not None and not (isinstance(r[f], float)
                                                          and np.isnan(r[f]))
                              for f in m1_feats)]
    print(f"  complete-case n = {len(complete_rows)}", flush=True)

    times_cc = np.array([r["os"] for r in complete_rows])
    events_cc = np.array([r["event"] for r in complete_rows])

    X0, _, _ = build_X(complete_rows, m0_feats)
    X1, _, _ = build_X(complete_rows, m1_feats)

    M0 = cox_ph_multivariate(times_cc, events_cc, X0)
    M1 = cox_ph_multivariate(times_cc, events_cc, X1)
    print(f"\n  M0 (clinical only, p={len(m0_feats)}):", flush=True)
    if M0 is not None:
        p_vals_0 = cox_p_values(M0["beta"], M0["se"])
        for f, b, s, p in zip(m0_feats, M0["beta"], M0["se"], p_vals_0):
            print(f"    {f:15s}  beta={b:+.4f}  SE={s:.4f}  "
                  f"HR/SD={np.exp(b):.3f}  p={p:.4f}", flush=True)
        print(f"    M0 log_pl = {M0['log_pl']:.4f}", flush=True)
    print(f"\n  M1 (clinical + V_kernel, p={len(m1_feats)}):", flush=True)
    p_vals_1 = []
    if M1 is not None:
        p_vals_1 = cox_p_values(M1["beta"], M1["se"])
        for f, b, s, p in zip(m1_feats, M1["beta"], M1["se"], p_vals_1):
            print(f"    {f:15s}  beta={b:+.4f}  SE={s:.4f}  "
                  f"HR/SD={np.exp(b):.3f}  p={p:.4f}", flush=True)
        print(f"    M1 log_pl = {M1['log_pl']:.4f}", flush=True)

    # Likelihood ratio test
    if M0 and M1:
        lrt = 2 * (M1["log_pl"] - M0["log_pl"])
        p_lrt = float(1 - chi2dist.cdf(lrt, df=1))
        print(f"\n  Likelihood ratio test (M0 vs M1, df=1):  "
              f"chi^2 = {lrt:.4f}  p = {p_lrt:.4f}", flush=True)
    else:
        lrt = float("nan")
        p_lrt = float("nan")

    # C-index for each
    risk_M0 = X0 @ np.array(M0["beta"]) if M0 else np.zeros(len(times_cc))
    risk_M1 = X1 @ np.array(M1["beta"]) if M1 else np.zeros(len(times_cc))
    c_M0 = concordance(times_cc, events_cc, risk_M0)
    c_M1 = concordance(times_cc, events_cc, risk_M1)
    print(f"\n  C-index M0 (clinical only)        = {c_M0:.4f}", flush=True)
    print(f"  C-index M1 (clinical + V_kernel)  = {c_M1:.4f}", flush=True)
    print(f"  Delta C-index                       = {c_M1 - c_M0:+.4f}",
          flush=True)

    # Bootstrap delta C-index
    print(f"\n  Bootstrap {N_BOOT}-resamples on Delta C-index...",
          flush=True)
    rng = np.random.default_rng(42)
    deltas = []
    n_cc = len(complete_rows)
    for b in range(N_BOOT):
        idx = rng.integers(0, n_cc, size=n_cc)
        if events_cc[idx].sum() < 3:
            continue
        m0_b = cox_ph_multivariate(times_cc[idx], events_cc[idx], X0[idx])
        m1_b = cox_ph_multivariate(times_cc[idx], events_cc[idx], X1[idx])
        if m0_b is None or m1_b is None:
            continue
        risk0_b = X0[idx] @ np.array(m0_b["beta"])
        risk1_b = X1[idx] @ np.array(m1_b["beta"])
        c0_b = concordance(times_cc[idx], events_cc[idx], risk0_b)
        c1_b = concordance(times_cc[idx], events_cc[idx], risk1_b)
        if not (np.isnan(c0_b) or np.isnan(c1_b)):
            deltas.append(c1_b - c0_b)
    if len(deltas) >= 100:
        ci_lo, ci_hi = np.percentile(deltas, [2.5, 97.5])
    else:
        ci_lo = ci_hi = float("nan")
    print(f"  Delta C-index 95% bootstrap CI: [{ci_lo:+.4f}, {ci_hi:+.4f}]  "
          f"(based on {len(deltas)} valid resamples)", flush=True)

    out = {
        "version": "v195",
        "experiment": ("Multimodal Cox: does V_kernel add prognostic info "
                       "beyond clinical features?"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_total": len(rows),
        "n_complete_case": len(complete_rows),
        "n_events": int(events.sum()),
        "univariate_cox": univariate,
        "M0_clinical_only": {
            "features": m0_feats,
            "fit": M0,
            "p_values": p_vals_0 if M0 else None,
            "c_index": c_M0,
        },
        "M1_clinical_plus_kernel": {
            "features": m1_feats,
            "fit": M1,
            "p_values": p_vals_1 if M1 else None,
            "c_index": c_M1,
        },
        "likelihood_ratio_test": {
            "chi2": float(lrt) if not np.isnan(lrt) else None,
            "p_value": float(p_lrt) if not np.isnan(p_lrt) else None,
        },
        "delta_c_index": {
            "point": c_M1 - c_M0,
            "ci_95_lo": float(ci_lo) if not np.isnan(ci_lo) else None,
            "ci_95_hi": float(ci_hi) if not np.isnan(ci_hi) else None,
            "n_bootstrap": len(deltas),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
