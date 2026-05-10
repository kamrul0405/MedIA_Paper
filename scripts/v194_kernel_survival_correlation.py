"""v194: Does the training-free kernel predict patient SURVIVAL? — round 32.

A senior Nature researcher's flagship-extension question:

  Round 27 v189 showed that the bimodal heat kernel max(M, G_3 * M)
  beats the foundation model on outgrowth-region AUC across 7
  cohorts WITHOUT TRAINING. The natural follow-up: does this kernel
  predict CLINICALLY MEANINGFUL OUTCOMES — not just outgrowth
  coverage but actual patient overall survival (OS) or
  progression-free survival (PFS)?

  If YES: a training-free physics kernel applied to a single
  baseline scan predicts patient survival → world-changing.

Method:
  Use the RHUH-GBM cohort (n=39 with PFS + OS + right-censored flag
  in clinical_data_TCIA_RHUH-GBM.csv). For each patient:
    - Load cached baseline mask (RHUH-GBM_RHUH-XXXX_b.npy)
    - Compute kernel-predicted outgrowth volume V_kernel:
        V_kernel = sum( (max(M, G_sigma * M) > 0.5) AND (NOT M) )
        for sigma in {1, 3, 7, 15} (sweep)
    - Match to clinical OS/PFS days
  Statistical analyses:
    - Spearman rank correlation: V_kernel vs OS/PFS
    - Median split: log-rank test (high vs low V_kernel)
    - Quartile split: Kaplan-Meier curves
    - Cox proportional hazards (V_kernel as continuous predictor)

Outputs:
  Nature_project/05_results/v194_kernel_survival.json
  Nature_project/05_results/v194_kernel_survival_per_patient.csv
"""
from __future__ import annotations

import csv
import json
import time
import warnings
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
CLINICAL_CSV = Path(r"C:\Users\kamru\Downloads\clinical_data_TCIA_RHUH-GBM.csv")
OUT_JSON = RESULTS / "v194_kernel_survival.json"
OUT_CSV = RESULTS / "v194_kernel_survival_per_patient.csv"

SIGMA_GRID = [1.0, 3.0, 7.0, 15.0]


# ============================================================================
# Helpers
# ============================================================================

def heat_constant(mask, sigma):
    if mask.sum() == 0:
        return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0:
        h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma)
    return np.maximum(persistence, h_broad)


def kernel_outgrowth_volume(mask, sigma, threshold=0.5):
    """V_kernel = number of voxels with kernel >= threshold OUTSIDE the mask."""
    K = heat_bimodal(mask, sigma)
    m = mask.astype(bool)
    return int(((K >= threshold) & ~m).sum())


def logrank_test(times1, events1, times2, events2):
    """Two-sample log-rank test (Mantel-Haenszel)."""
    times = np.concatenate([times1, times2])
    events = np.concatenate([events1, events2])
    groups = np.concatenate([np.zeros(len(times1)), np.ones(len(times2))])
    order = np.argsort(times)
    times = times[order]
    events = events[order]
    groups = groups[order]
    O1 = 0.0  # observed events in group 1
    E1 = 0.0  # expected
    V = 0.0   # variance
    n1 = len(times1)
    n2 = len(times2)
    n_remain1 = n1
    n_remain2 = n2
    unique_event_times = np.unique(times[events == 1])
    for t in unique_event_times:
        # at risk just before t
        r1 = float(((np.array(times1) >= t)).sum())
        r2 = float(((np.array(times2) >= t)).sum())
        r = r1 + r2
        if r == 0:
            continue
        # events at time t
        d1 = float(((np.array(times1) == t) & (np.array(events1) == 1)).sum())
        d2 = float(((np.array(times2) == t) & (np.array(events2) == 1)).sum())
        d = d1 + d2
        if d == 0:
            continue
        e1 = d * r1 / r
        v = d * (r1 / r) * (r2 / r) * ((r - d) / (r - 1)) if r > 1 else 0
        O1 += d1
        E1 += e1
        V += v
    if V <= 0:
        return float("nan"), float("nan")
    chi2 = (O1 - E1) ** 2 / V
    # one-sided p ~ from chi-square with 1 dof; two-sided
    from scipy.stats import chi2 as chi2dist
    p = float(1 - chi2dist.cdf(chi2, df=1))
    return float(chi2), p


def cox_univariate(times, events, x):
    """Univariate Cox PH via Newton-Raphson on log partial likelihood."""
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=float)
    x = np.asarray(x, dtype=float)
    # Standardize x
    x_mean = x.mean()
    x_std = x.std()
    if x_std == 0:
        return float("nan"), float("nan"), float("nan")
    x_n = (x - x_mean) / x_std
    n = len(times)
    order = np.argsort(times)
    t = times[order]
    e = events[order]
    z = x_n[order]
    beta = 0.0
    for _ in range(50):
        # risk set: index >= i
        eta = beta * z
        exp_eta = np.exp(eta)
        # for each event time, compute log-lik components
        # cumulative from end
        S = np.cumsum(exp_eta[::-1])[::-1]  # sum of exp_eta over risk set
        SZ = np.cumsum((z * exp_eta)[::-1])[::-1]
        SZZ = np.cumsum((z * z * exp_eta)[::-1])[::-1]
        # gradient and hessian
        d_idx = np.where(e == 1)[0]
        if len(d_idx) == 0:
            return float("nan"), float("nan"), float("nan")
        grad = float((z[d_idx] - SZ[d_idx] / S[d_idx]).sum())
        hess = float(((SZ[d_idx] / S[d_idx]) ** 2 - SZZ[d_idx] / S[d_idx]).sum())
        if hess == 0:
            break
        delta = -grad / hess
        beta_new = beta + delta
        if abs(delta) < 1e-6:
            beta = beta_new
            break
        beta = beta_new
    # standard error from inverse Hessian
    if hess == 0:
        return float("nan"), float("nan"), float("nan")
    var_beta = -1.0 / hess
    if var_beta <= 0:
        return float("nan"), float("nan"), float("nan")
    se = float(np.sqrt(var_beta))
    HR = float(np.exp(beta))
    z_score = beta / se
    from scipy.stats import norm
    p = float(2 * (1 - norm.cdf(abs(z_score))))
    return HR, p, float(beta)


def main():
    print("=" * 78, flush=True)
    print("v194 KERNEL -> SURVIVAL CORRELATION (RHUH-GBM, n=39)", flush=True)
    print("=" * 78, flush=True)

    # Load clinical CSV
    clinical = {}
    with CLINICAL_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        # Find column names
        pid_col = "Patient ID"
        pfs_col = next((c for c in cols if "PFS" in c.upper()
                          and "day" in c.lower()), None)
        os_col = next((c for c in cols if "Overall survival" in c
                         and "day" in c.lower()), None)
        cens_col = next((c for c in cols if "censor" in c.lower()), None)
        idh_col = next((c for c in cols if "IDH" in c.upper()), None)
        for row in reader:
            pid = row[pid_col].strip()
            try:
                pfs = float(row[pfs_col]) if row[pfs_col] else None
            except (ValueError, TypeError):
                pfs = None
            try:
                os_d = float(row[os_col]) if row[os_col] else None
            except (ValueError, TypeError):
                os_d = None
            cens = row[cens_col].strip().lower() if cens_col and row[cens_col] else ""
            idh = row[idh_col].strip().lower() if idh_col and row[idh_col] else ""
            event = 0 if cens == "yes" else 1  # right-censored=yes -> event=0
            clinical[pid] = {
                "pfs": pfs, "os": os_d, "event": event, "idh": idh,
            }
    print(f"  loaded clinical data for {len(clinical)} RHUH patients",
          flush=True)

    # Build per-patient table: kernel-predicted outgrowth volume + survival
    rows = []
    for f in sorted(CACHE.glob("RHUH-GBM_RHUH-*_b.npy")):
        pid = f.stem.replace("RHUH-GBM_", "").replace("_b", "")
        if pid not in clinical:
            continue
        m = (np.load(f) > 0).astype(np.float32)
        if m.sum() == 0:
            continue
        # Kernel volumes at multiple sigma
        v_sigma = {sigma: kernel_outgrowth_volume(m, sigma)
                    for sigma in SIGMA_GRID}
        # Also compute baseline mask volume itself
        baseline_volume = int(m.sum())
        rows.append({
            "pid": pid,
            "baseline_mask_volume": baseline_volume,
            **{f"V_kernel_sigma{int(s)}": v_sigma[s] for s in SIGMA_GRID},
            "OS_days": clinical[pid]["os"],
            "PFS_days": clinical[pid]["pfs"],
            "event": clinical[pid]["event"],
            "IDH": clinical[pid]["idh"],
        })
    print(f"  matched {len(rows)} patients with both mask and clinical data",
          flush=True)

    # Filter for valid OS and event
    valid_rows = [r for r in rows
                   if r["OS_days"] is not None and r["event"] is not None]
    print(f"  {len(valid_rows)} patients with valid OS data", flush=True)

    # Spearman correlations
    print("\n=== Spearman correlations: V_kernel vs survival ===",
          flush=True)
    spearman_results = {}
    for sigma in SIGMA_GRID:
        col = f"V_kernel_sigma{int(sigma)}"
        for outcome in ["OS_days", "PFS_days"]:
            xs = np.array([r[col] for r in valid_rows
                            if r[outcome] is not None], dtype=float)
            ys = np.array([r[outcome] for r in valid_rows
                            if r[outcome] is not None], dtype=float)
            if len(xs) < 5:
                continue
            rho, p = spearmanr(xs, ys)
            spearman_results[f"{col}_vs_{outcome}"] = {
                "n": int(len(xs)), "rho": float(rho), "p_value": float(p),
            }
            print(f"  {col} vs {outcome}  n={len(xs)}  rho={rho:+.4f}  p={p:.4f}",
                  flush=True)
    # Also baseline mask volume
    for outcome in ["OS_days", "PFS_days"]:
        xs = np.array([r["baseline_mask_volume"] for r in valid_rows
                        if r[outcome] is not None], dtype=float)
        ys = np.array([r[outcome] for r in valid_rows
                        if r[outcome] is not None], dtype=float)
        if len(xs) >= 5:
            rho, p = spearmanr(xs, ys)
            spearman_results[f"baseline_mask_volume_vs_{outcome}"] = {
                "n": int(len(xs)), "rho": float(rho), "p_value": float(p),
            }
            print(f"  baseline_mask_volume vs {outcome}  n={len(xs)}  "
                  f"rho={rho:+.4f}  p={p:.4f}", flush=True)

    # Log-rank tests: median split by V_kernel sigma=3
    print("\n=== Median-split log-rank tests (V_kernel sigma=3) ===",
          flush=True)
    sigma_for_test = 3
    col = f"V_kernel_sigma{sigma_for_test}"
    times = np.array([r["OS_days"] for r in valid_rows], dtype=float)
    events = np.array([r["event"] for r in valid_rows], dtype=float)
    x = np.array([r[col] for r in valid_rows], dtype=float)
    median = float(np.median(x))
    high = x > median
    chi2, p_lr = logrank_test(
        times[high], events[high],
        times[~high], events[~high]
    )
    print(f"  V_kernel_sigma3 median = {median:.0f} voxels", flush=True)
    print(f"  high group (n={high.sum()}) median OS = "
          f"{np.median(times[high]):.0f} days", flush=True)
    print(f"  low group (n={(~high).sum()}) median OS = "
          f"{np.median(times[~high]):.0f} days", flush=True)
    print(f"  log-rank chi2 = {chi2:.4f}  p = {p_lr:.4f}", flush=True)

    # Cox univariate
    print("\n=== Cox proportional hazards (continuous V_kernel) ===",
          flush=True)
    cox_results = {}
    for sigma in SIGMA_GRID:
        col = f"V_kernel_sigma{int(sigma)}"
        x = np.array([r[col] for r in valid_rows], dtype=float)
        HR, p, beta = cox_univariate(times, events, x)
        cox_results[col] = {
            "HR_per_SD": HR, "p_value": p, "beta": beta,
            "n": int(len(times)),
        }
        print(f"  {col}  HR per SD = {HR:.4f}  p = {p:.4f}", flush=True)
    # Also baseline mask volume
    x_bv = np.array([r["baseline_mask_volume"] for r in valid_rows],
                     dtype=float)
    HR_bv, p_bv, beta_bv = cox_univariate(times, events, x_bv)
    cox_results["baseline_mask_volume"] = {
        "HR_per_SD": HR_bv, "p_value": p_bv, "beta": beta_bv,
        "n": int(len(times)),
    }
    print(f"  baseline_mask_volume  HR per SD = {HR_bv:.4f}  p = {p_bv:.4f}",
          flush=True)

    out = {
        "version": "v194",
        "experiment": "Kernel -> survival correlation on RHUH-GBM",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_patients": len(valid_rows),
        "spearman": spearman_results,
        "logrank_median_split_sigma3": {
            "chi2": chi2, "p_value": p_lr,
            "median_threshold_voxels": median,
            "n_high": int(high.sum()), "n_low": int((~high).sum()),
            "median_OS_high": float(np.median(times[high])),
            "median_OS_low": float(np.median(times[~high])),
        },
        "cox_univariate": cox_results,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    # Save per-patient CSV
    if rows:
        with OUT_CSV.open("w", newline="") as fp:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
