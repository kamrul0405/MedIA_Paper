"""v160: Cluster-bootstrap 95% CIs on v156 universal foundation
model per-patient predictions.

Reads v156_universal_foundation_per_patient.csv and computes 10,000-
replicate cluster-bootstrap CIs (patient-level resampling) per
held-out cohort for:
  - learned-only outgrowth coverage
  - bimodal outgrowth coverage
  - ensemble outgrowth coverage
  - ensemble overall coverage

Outputs:
    Nature_project/05_results/v160_v156_bootstrap_cis.json
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
INPUT_CSV = RESULTS / "v156_universal_foundation_per_patient.csv"
OUT_JSON = RESULTS / "v160_v156_bootstrap_cis.json"

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
N_BOOT = 10000
RNG = np.random.default_rng(16001)


def vectorised_cluster_bootstrap(values, alpha=0.05):
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    if valid.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    v = values[valid]
    n = len(v)
    sample_idx = RNG.integers(0, n, size=(N_BOOT, n))
    boot_means = v[sample_idx].mean(axis=1)
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return float(boot_means.mean()), lo, hi


def main():
    print("=" * 78, flush=True)
    print("v160 CLUSTER-BOOTSTRAP CIs ON v156 UNIVERSAL FOUNDATION MODEL", flush=True)
    print(f"  N_BOOT = {N_BOOT}; alpha = 0.05 (95% CI)", flush=True)
    print("=" * 78, flush=True)

    rows = list(csv.DictReader(open(INPUT_CSV)))
    print(f"\nLoaded {len(rows)} per-patient rows from {INPUT_CSV.name}", flush=True)

    out = {"version": "v160", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "source_csv": INPUT_CSV.name,
           "n_total_rows": len(rows),
           "n_bootstrap_replicates": N_BOOT, "alpha": 0.05,
           "by_cohort": {}}

    metrics = ["learned_outgrowth", "bimodal_outgrowth",
               "ensemble_outgrowth", "ensemble_overall"]
    print("\n=== Per-cohort 95% CIs ===", flush=True)
    print(f"  {'Held-out':<22s} {'N':>4s} ", end="", flush=True)
    for m in metrics:
        print(f"{m[:18]:>22s} ", end="", flush=True)
    print(flush=True)

    for cohort in ALL_COHORTS:
        sub = [r for r in rows if r["fold_held_out"] == cohort]
        if not sub: continue
        cohort_results = {"n": len(sub)}
        print(f"  {cohort:<22s} {len(sub):>4d} ", end="", flush=True)
        for m in metrics:
            vals = np.array([float(r[m]) for r in sub], dtype=float)
            mean, lo, hi = vectorised_cluster_bootstrap(vals)
            cohort_results[m] = {
                "mean_pct": round(mean * 100, 2),
                "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)],
            }
            print(f"{mean*100:6.2f}% [{lo*100:5.2f},{hi*100:5.2f}] ",
                  end="", flush=True)
        print(flush=True)
        out["by_cohort"][cohort] = cohort_results

    # Cohort-mean across the 5 cohort means (per-cohort means -> mean of means)
    cohort_mean = {}
    print(f"\n  {'5-cohort MEAN':<22s} {'':>4s} ", end="", flush=True)
    for m in metrics:
        cohort_means = [out["by_cohort"][c][m]["mean_pct"]
                        for c in ALL_COHORTS if c in out["by_cohort"]]
        cohort_mean[m] = float(np.mean(cohort_means))
        print(f"{cohort_mean[m]:6.2f}%                  ", end="", flush=True)
    print(flush=True)
    out["cohort_mean_pct"] = cohort_mean

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
