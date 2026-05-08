"""v126: Cross-cohort persistence-baseline universality test.

Motivation. v117 showed on PROTEAS-brain-mets that the lesion-
persistence baseline (heat = baseline mask itself) achieves 51.95%
overall coverage at heat>=0.80, beating every structural prior.
v126 tests whether this finding generalises across the cache_3d
cohorts (UCSF, MU, RHUH, LUMIERE).

For each cohort, computes 10,000-replicate cluster-bootstrap CIs on:
  - Persistence baseline coverage at heat>=0.50 / 0.80
  - sigma=1.0 and sigma=2.5 coverage
  - Paired-delta CIs for each constant-sigma vs persistence

Headline expected: persistence dominates at heat>=0.80 universally.

Outputs:
    Nature_project/05_results/v126_cross_cohort_persistence.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v126_cross_cohort_persistence.json"

COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_GRID = [0.5, 1.0, 2.5]
HEAT_THRESHOLDS = [0.5, 0.8]
N_BOOT = 10000
RNG = np.random.default_rng(12601)


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


def cluster_bootstrap_ci(values, pids, alpha=0.05):
    pids_unique = np.unique(pids)
    boots = np.empty(N_BOOT)
    for b in range(N_BOOT):
        sample = RNG.choice(pids_unique, size=len(pids_unique), replace=True)
        vals = []
        for s in sample:
            mask = pids == s
            vals.extend(values[mask].tolist())
        boots[b] = np.nanmean(vals) if vals else np.nan
    lo = np.nanpercentile(boots, 100 * alpha / 2)
    hi = np.nanpercentile(boots, 100 * (1 - alpha / 2))
    return float(np.nanmean(boots)), float(lo), float(hi)


def load_cohort_per_patient(cohort: str):
    """Load all patient masks + targets for a cohort."""
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    rows = []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists():
            continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0:
            continue
        rows.append({"pid": pid, "mask": m, "target": t})
    return rows


def main():
    print("=" * 78)
    print("v126 CROSS-COHORT PERSISTENCE UNIVERSALITY TEST")
    print(f"  cohorts: {COHORTS}")
    print(f"  N_BOOT = {N_BOOT}")
    print("=" * 78)

    out = {"version": "v126", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "n_bootstrap_replicates": N_BOOT, "alpha": 0.05, "cohorts": {}}

    for cohort in COHORTS:
        print(f"\n--- {cohort} ---")
        rows = load_cohort_per_patient(cohort)
        n = len(rows)
        if n == 0:
            print("  no data; skipping")
            continue
        print(f"  N = {n} patients with valid mask + target")

        pids = np.array([r["pid"] for r in rows])
        cohort_results = {"thresholds": {}}

        for thr in HEAT_THRESHOLDS:
            print(f"\n  threshold heat >= {thr}:")
            # Compute per-patient coverage for each method
            cov_pers = []
            cov_sigma = {sig: [] for sig in SIGMA_GRID}
            for r in rows:
                m = r["mask"]
                t = r["target"]
                # Persistence baseline = mask itself
                cov_pers.append(coverage(t, m.astype(bool)))
                for sig in SIGMA_GRID:
                    h = heat_kernel(m, sig)
                    cov_sigma[sig].append(coverage(t, h >= thr))

            cov_pers = np.array(cov_pers, dtype=float)
            for sig in SIGMA_GRID:
                cov_sigma[sig] = np.array(cov_sigma[sig], dtype=float)

            # Cluster-bootstrap CIs
            mp, lp, hp = cluster_bootstrap_ci(cov_pers, pids)
            print(f"    persistence: {mp*100:5.2f}% [{lp*100:.2f}, {hp*100:.2f}]")
            thr_results = {
                "n_patients": n,
                "persistence": {"mean_pct": round(mp * 100, 2),
                                "ci95_pct": [round(lp * 100, 2), round(hp * 100, 2)]},
                "sigma_methods": {},
                "paired_deltas_vs_persistence": {},
            }
            for sig in SIGMA_GRID:
                m_s, l_s, h_s = cluster_bootstrap_ci(cov_sigma[sig], pids)
                thr_results["sigma_methods"][f"sigma_{sig}"] = {
                    "mean_pct": round(m_s * 100, 2),
                    "ci95_pct": [round(l_s * 100, 2), round(h_s * 100, 2)],
                }
                print(f"    sigma={sig}:    {m_s*100:5.2f}% "
                      f"[{l_s*100:.2f}, {h_s*100:.2f}]")
                # Paired delta vs persistence
                diff = cov_sigma[sig] - cov_pers
                m_d, l_d, h_d = cluster_bootstrap_ci(diff, pids)
                thr_results["paired_deltas_vs_persistence"][f"sigma_{sig}_minus_pers"] = {
                    "mean_pp": round(m_d * 100, 2),
                    "ci95_pp": [round(l_d * 100, 2), round(h_d * 100, 2)],
                    "excludes_zero": bool(l_d > 0 or h_d < 0),
                }
                sig_marker = ("**SIG**" if (l_d > 0 or h_d < 0) else "      ")
                print(f"    delta sigma={sig} - pers: {m_d*100:+6.2f} pp "
                      f"[{l_d*100:+.2f}, {h_d*100:+.2f}] {sig_marker}")

            cohort_results["thresholds"][f"heat_ge_{thr}"] = thr_results

        out["cohorts"][cohort] = cohort_results

    # Cross-cohort summary: persistence dominance count
    print("\n=== CROSS-COHORT SUMMARY ===")
    for thr in HEAT_THRESHOLDS:
        print(f"\n  threshold heat >= {thr}:")
        for cohort in COHORTS:
            tr = out["cohorts"].get(cohort, {}).get("thresholds", {}).get(f"heat_ge_{thr}")
            if tr is None: continue
            pers = tr["persistence"]["mean_pct"]
            print(f"    {cohort:18s}: persistence = {pers:.2f}%, "
                  f"sigma=2.5 = {tr['sigma_methods']['sigma_2.5']['mean_pct']:.2f}%")
            # Count: persistence dominance
            for sig in SIGMA_GRID:
                d = tr["paired_deltas_vs_persistence"][f"sigma_{sig}_minus_pers"]
                marker = ""
                if d["excludes_zero"]:
                    marker = "(persist beats)" if d["mean_pp"] < 0 else "(sigma beats)"
                # No print here, kept for json

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}")


if __name__ == "__main__":
    main()
