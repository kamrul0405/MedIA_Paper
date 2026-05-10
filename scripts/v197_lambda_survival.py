"""v197: Does per-patient UODSL λ predict patient survival? — round 35.

Senior-Nature-reviewer-driven extension after round 34 established λ
as patient-intrinsic (ICC-proxy = 0.834). The natural follow-up:

  Round 32-33 showed kernel-predicted OUTGROWTH VOLUME does not
  predict survival. But round 34 just established that the UODSL
  length scale lambda IS a patient-intrinsic biological signature.
  These are fundamentally different quantities:
    - V_kernel = how MUCH outgrowth (sum of voxels above threshold)
    - lambda = how the outgrowth probability DECAYS with distance

  Lambda may capture a deeper invasion-biology signature than mere
  volume. Test: does per-patient lambda predict OS/PFS in
  RHUH-GBM where v195 already showed clinical features dominate?

Method (RHUH-GBM, n=39 with full clinical OS+PFS+IDH):
  - Compute per-patient lambda from baseline -> followup outgrowth
    (fit P(d) = A * exp(-d/lambda) per patient).
  - Match to clinical OS / PFS / event status.
  - Statistical analyses:
    * Spearman lambda vs OS / PFS
    * Cox univariate (HR per SD)
    * Multivariate Cox: M0 (clinical) vs M1 (clinical + lambda) vs
      M2 (clinical + lambda + V_kernel)
    * Log-rank median split

Outputs:
  Nature_project/05_results/v197_lambda_survival.json
  Nature_project/05_results/v197_lambda_survival_per_patient.csv
"""
from __future__ import annotations

import csv
import json
import re
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.optimize import minimize
from scipy.stats import chi2 as chi2dist, norm, spearmanr

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
CLINICAL_CSV = Path(r"C:\Users\kamru\Downloads\clinical_data_TCIA_RHUH-GBM.csv")
V195_JSON = RESULTS / "v195_multimodal_prognosis.json"
V194_CSV = RESULTS / "v194_kernel_survival_per_patient.csv"
OUT_JSON = RESULTS / "v197_lambda_survival.json"
OUT_CSV = RESULTS / "v197_lambda_survival_per_patient.csv"

DISTANCE_BINS = np.arange(1, 25)


# ============================================================================
# UODSL fit per patient (re-used from v186/v196)
# ============================================================================

def fit_lambda(mask, outgrowth):
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


# ============================================================================
# Cox PH (re-used from v195)
# ============================================================================

def cox_ph_multivariate(times, events, X):
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
        log_S = np.zeros(n)
        running_max = -np.inf
        running_sum_exp = 0.0
        for i in range(n):
            new_max = max(running_max, eta[i])
            running_sum_exp = (np.exp(running_max - new_max) * running_sum_exp
                                + np.exp(eta[i] - new_max))
            running_max = new_max
            log_S[i] = running_max + np.log(running_sum_exp)
        log_pl = float((eta[e == 1] - log_S[e == 1]).sum())
        return -log_pl

    beta0 = np.zeros(p)
    result = minimize(neg_log_pl, beta0, method="L-BFGS-B",
                      options={"maxiter": 200})
    beta = result.x
    log_pl = -result.fun

    eps = 1e-4
    H = np.zeros((p, p))
    for i in range(p):
        for j in range(p):
            if i <= j:
                bp = beta.copy(); bp[i] += eps; bp[j] += eps
                f_pp = neg_log_pl(bp)
                bp = beta.copy(); bp[i] += eps; bp[j] -= eps
                f_pm = neg_log_pl(bp)
                bp = beta.copy(); bp[i] -= eps; bp[j] += eps
                f_mp = neg_log_pl(bp)
                bp = beta.copy(); bp[i] -= eps; bp[j] -= eps
                f_mm = neg_log_pl(bp)
                H[i, j] = (f_pp - f_pm - f_mp + f_mm) / (4 * eps * eps)
                H[j, i] = H[i, j]
    try:
        cov = np.linalg.inv(H)
        se = np.sqrt(np.maximum(np.diag(cov), 0))
    except np.linalg.LinAlgError:
        se = np.full(p, np.nan)

    return {
        "beta": beta.tolist(),
        "se": se.tolist(),
        "log_pl": float(log_pl),
        "converged": bool(result.success),
    }


def concordance(times, events, risk_scores):
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
                continue
            if times[i] < times[j]:
                if events[i] != 1:
                    continue
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
    if n_pairs == 0:
        return float("nan")
    return (n_concordant + 0.5 * n_ties) / n_pairs


def main():
    print("=" * 78, flush=True)
    print("v197 PER-PATIENT LAMBDA -> SURVIVAL (RHUH-GBM, n=39)", flush=True)
    print("=" * 78, flush=True)

    # ---------- Load clinical ----------
    clinical = {}
    with CLINICAL_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        pid_col = "Patient ID"
        age_col = "Age"
        kps_col = "Preoperative KPS"
        idh_col = next((c for c in cols if "IDH" in c.upper()), None)
        eor_cat_col = next((c for c in cols if "EOR =" in c), None)
        rt_tmz_col = next((c for c in cols if "Adjuvant therapy" in c), None)
        pfs_col = next((c for c in cols if "PFS" in c.upper()
                          and "day" in c.lower()), None)
        os_col = next((c for c in cols if "Overall survival" in c
                         and "day" in c.lower()), None)
        cens_col = next((c for c in cols if "censor" in c.lower()), None)

        def safe_float(s):
            s = (s or "").strip()
            try:
                return float(re.sub(r"[^\d.\-+]", "", s)) if s else None
            except (ValueError, TypeError):
                return None

        for row in reader:
            pid = row[pid_col].strip()
            event = 0 if row[cens_col].strip().lower() == "yes" else 1
            idh_raw = (row[idh_col] or "").lower()
            if "mut" in idh_raw and "nos" not in idh_raw:
                idh = 1.0
            elif "wild" in idh_raw or "wt" in idh_raw:
                idh = 0.0
            else:
                idh = None
            rt_tmz_raw = (row[rt_tmz_col] or "").upper()
            rt_tmz = 1.0 if "RT" in rt_tmz_raw and "TMZ" in rt_tmz_raw else 0.0
            eor_cat = (row[eor_cat_col] or "").upper()
            gtr = 1.0 if "GTR" in eor_cat else 0.0
            clinical[pid] = {
                "age": safe_float(row[age_col]),
                "kps": safe_float(row[kps_col]),
                "idh": idh,
                "gtr": gtr,
                "rt_tmz": rt_tmz,
                "pfs": safe_float(row[pfs_col]),
                "os": safe_float(row[os_col]),
                "event": event,
            }
    print(f"  loaded clinical for {len(clinical)} RHUH patients",
          flush=True)

    # ---------- Load V_kernel from v194 ----------
    v_kernel = {}
    with V194_CSV.open() as f:
        for row in csv.DictReader(f):
            try:
                v_kernel[row["pid"].strip()] = float(row["V_kernel_sigma3"])
            except (ValueError, KeyError):
                continue

    # ---------- Compute per-patient lambda for RHUH ----------
    print("\nComputing per-patient lambda for RHUH-GBM...", flush=True)
    rows = []
    for f in sorted(CACHE.glob("RHUH-GBM_RHUH-*_b.npy")):
        pid = f.stem.replace("RHUH-GBM_", "").replace("_b", "")
        if pid not in clinical:
            continue
        m = (np.load(f) > 0).astype(np.float32)
        fr_path = f.parent / f.name.replace("_b.npy", "_r.npy")
        if not fr_path.exists():
            continue
        fu = (np.load(fr_path) > 0).astype(np.float32)
        outgrowth = (fu.astype(bool) & ~m.astype(bool)).astype(np.float32)
        if m.sum() == 0 or outgrowth.sum() == 0:
            continue
        A, lam, r2, n_pts = fit_lambda(m, outgrowth)
        valid = (not np.isnan(lam)) and (not np.isinf(lam)) and \
                lam > 0 and lam < 200 and r2 > 0.5 and n_pts >= 4
        c = clinical[pid]
        rows.append({
            "pid": pid,
            "lambda_obs": lam if valid else None,
            "lambda_r2": r2 if not np.isnan(r2) else None,
            "lambda_n_pts": n_pts,
            "lambda_valid": valid,
            "v_kernel_s3": v_kernel.get(pid),
            "age": c["age"],
            "kps": c["kps"],
            "idh": c["idh"],
            "gtr": c["gtr"],
            "rt_tmz": c["rt_tmz"],
            "pfs": c["pfs"],
            "os": c["os"],
            "event": c["event"],
        })

    n_total = len(rows)
    n_valid_lam = sum(1 for r in rows if r["lambda_valid"])
    print(f"  {n_total} RHUH patients with mask + clinical", flush=True)
    print(f"  {n_valid_lam} patients with valid per-patient lambda",
          flush=True)

    # ---------- Restrict to valid lambda ----------
    valid_rows = [r for r in rows if r["lambda_valid"]
                   and r["os"] is not None and r["event"] is not None]
    print(f"  {len(valid_rows)} patients with valid lambda + OS data",
          flush=True)

    # ---------- Spearman correlations ----------
    print("\n=== Spearman: lambda vs survival ===", flush=True)
    lams = np.array([r["lambda_obs"] for r in valid_rows], dtype=float)
    os_d = np.array([r["os"] for r in valid_rows], dtype=float)
    pfs_d = np.array([r["pfs"] for r in valid_rows
                        if r["pfs"] is not None], dtype=float)
    rho_os, p_os = spearmanr(lams, os_d)
    print(f"  lambda vs OS:  n={len(lams)}  rho={rho_os:+.4f}  p={p_os:.4f}",
          flush=True)
    if len(pfs_d) >= 5:
        # match
        lams_pfs = np.array([r["lambda_obs"] for r in valid_rows
                                if r["pfs"] is not None], dtype=float)
        rho_pfs, p_pfs = spearmanr(lams_pfs, pfs_d)
        print(f"  lambda vs PFS: n={len(lams_pfs)}  rho={rho_pfs:+.4f}  "
              f"p={p_pfs:.4f}", flush=True)
    else:
        rho_pfs, p_pfs = float("nan"), float("nan")

    # ---------- Univariate Cox: lambda ----------
    print("\n=== Univariate Cox PH ===", flush=True)
    times = np.array([r["os"] for r in valid_rows], dtype=float)
    events = np.array([r["event"] for r in valid_rows], dtype=float)
    print(f"  n={len(times)}  events={int(events.sum())}", flush=True)
    lam_z = (lams - lams.mean()) / max(lams.std(), 1e-12)
    cox_lam = cox_ph_multivariate(times, events, lam_z.reshape(-1, 1))
    if cox_lam:
        beta = cox_lam["beta"][0]
        se = cox_lam["se"][0]
        z = beta / max(se, 1e-12)
        p = float(2 * (1 - norm.cdf(abs(z))))
        HR = float(np.exp(beta))
        print(f"  lambda  HR/SD = {HR:.4f}  beta={beta:+.4f}  SE={se:.4f}  "
              f"p={p:.4f}", flush=True)
    else:
        HR, p = float("nan"), float("nan")

    # ---------- Multivariate Cox ----------
    print("\n=== Multivariate Cox (complete-case) ===", flush=True)
    m0_feats = ["age", "kps", "idh", "gtr", "rt_tmz"]
    m1_feats = m0_feats + ["lambda_obs"]
    m2_feats = m1_feats + ["v_kernel_s3"]
    cc = [r for r in valid_rows if all(r[f] is not None and not (
        isinstance(r[f], float) and np.isnan(r[f])) for f in m2_feats)]
    print(f"  complete-case n = {len(cc)}", flush=True)
    times_cc = np.array([r["os"] for r in cc], dtype=float)
    events_cc = np.array([r["event"] for r in cc], dtype=float)

    def build_X(rows, feats):
        X = np.array([[r[f] for f in feats] for r in rows], dtype=float)
        means = X.mean(axis=0)
        stds = X.std(axis=0)
        stds[stds == 0] = 1
        return (X - means) / stds

    X0 = build_X(cc, m0_feats)
    X1 = build_X(cc, m1_feats)
    X2 = build_X(cc, m2_feats)
    M0 = cox_ph_multivariate(times_cc, events_cc, X0)
    M1 = cox_ph_multivariate(times_cc, events_cc, X1)
    M2 = cox_ph_multivariate(times_cc, events_cc, X2)

    risk_M0 = X0 @ np.array(M0["beta"]) if M0 else np.zeros(len(times_cc))
    risk_M1 = X1 @ np.array(M1["beta"]) if M1 else np.zeros(len(times_cc))
    risk_M2 = X2 @ np.array(M2["beta"]) if M2 else np.zeros(len(times_cc))
    c_M0 = concordance(times_cc, events_cc, risk_M0)
    c_M1 = concordance(times_cc, events_cc, risk_M1)
    c_M2 = concordance(times_cc, events_cc, risk_M2)
    print(f"\n  M0 (clinical only):                C = {c_M0:.4f}",
          flush=True)
    print(f"  M1 (clinical + lambda):            C = {c_M1:.4f}  "
          f"Delta = {c_M1 - c_M0:+.4f}", flush=True)
    print(f"  M2 (clinical + lambda + V_kernel): C = {c_M2:.4f}  "
          f"Delta = {c_M2 - c_M0:+.4f}", flush=True)

    # LRT M0 vs M1, M0 vs M2
    if M0 and M1:
        lrt01 = 2 * (M1["log_pl"] - M0["log_pl"])
        p_01 = float(1 - chi2dist.cdf(lrt01, df=1))
    else:
        lrt01, p_01 = float("nan"), float("nan")
    if M0 and M2:
        lrt02 = 2 * (M2["log_pl"] - M0["log_pl"])
        p_02 = float(1 - chi2dist.cdf(lrt02, df=2))
    else:
        lrt02, p_02 = float("nan"), float("nan")
    print(f"\n  LRT M0 vs M1 (df=1): chi^2 = {lrt01:.4f}  p = {p_01:.4f}",
          flush=True)
    print(f"  LRT M0 vs M2 (df=2): chi^2 = {lrt02:.4f}  p = {p_02:.4f}",
          flush=True)

    # ---------- Compare to round 32-33 (V_kernel only) ----------
    print(f"\n  Reference: round-32 V_kernel univariate Cox HR/SD = 0.981, "
          f"p = 0.92", flush=True)
    print(f"  Reference: round-33 multivariate Cox added V_kernel:        "
          f"Delta C = -0.005, LRT p = 0.53", flush=True)

    out = {
        "version": "v197",
        "experiment": "Per-patient lambda -> survival in RHUH-GBM",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_rhuh_total": n_total,
        "n_valid_lambda": n_valid_lam,
        "n_valid_lambda_with_OS": len(valid_rows),
        "n_complete_case": len(cc),
        "spearman": {
            "lambda_vs_OS_n": int(len(lams)),
            "lambda_vs_OS_rho": float(rho_os),
            "lambda_vs_OS_p": float(p_os),
            "lambda_vs_PFS_n": int(len(pfs_d)),
            "lambda_vs_PFS_rho": float(rho_pfs) if not np.isnan(rho_pfs) else None,
            "lambda_vs_PFS_p": float(p_pfs) if not np.isnan(p_pfs) else None,
        },
        "univariate_cox_lambda": {
            "n": int(len(times)),
            "events": int(events.sum()),
            "HR_per_SD": HR,
            "p_value": p,
        },
        "multivariate_cox": {
            "n_complete_case": len(cc),
            "M0_clinical_only_c_index": c_M0,
            "M1_clinical_plus_lambda_c_index": c_M1,
            "M1_delta_c": c_M1 - c_M0,
            "M2_clinical_plus_lambda_plus_kernel_c_index": c_M2,
            "M2_delta_c": c_M2 - c_M0,
            "LRT_M0_vs_M1": {"chi2": lrt01, "p_value": p_01},
            "LRT_M0_vs_M2": {"chi2": lrt02, "p_value": p_02},
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if rows:
        with OUT_CSV.open("w", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
