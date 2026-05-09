"""v192: UOSL-similarity-gated HYBRID deployment — round 30.

Senior-Nature-reviewer synthesis question:

  Round 22 (v184): foundation+kernel ensemble wins on Dice/coverage
                    for in-distribution cohorts (UPENN Dice 0.71).
  Round 27 (v189): kernel-only at sigma=3 wins on AUC across
                    all 7 cohorts (mean 0.79 vs foundation 0.72).
  Round 28-29 (v190, v191): patient-adaptive sigma + multi-scale
                              ensembling do NOT improve over sigma=3.

  THE REMAINING SYNTHESIS: a UOSL-similarity-gated hybrid
  recipe — use foundation+kernel ensemble for cohorts with high
  UOSL S (in-distribution); use kernel-only sigma=3 for cohorts
  with low UOSL S (out-of-distribution).

  Hypothesis: hybrid achieves the best AUC AND the best Dice/
  coverage simultaneously — the unified deployable recipe.

Method (pure analysis, no retraining):
  - Re-use v184 foundation+kernel ensemble metrics per cohort.
  - Re-use v189 kernel-only sigma=3 metrics per cohort.
  - Compute UOSL similarity S per cohort relative to 5-cohort
    training (using DISEASE_VEC from v177 UOSL).
  - Apply gating rule: if S > S_threshold use foundation; else
    use kernel-only sigma=3.
  - Sweep S_threshold in {0.3, 0.4, 0.5, 0.6, 0.7, 0.8}.
  - Report: per-cohort AUC, Dice, coverage; mean across 7 cohorts.
  - Compare to non-hybrid baselines.

Outputs:
  Nature_project/05_results/v192_uosl_gated_hybrid.json
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
OUT_JSON = RESULTS / "v192_uosl_gated_hybrid.json"

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets", "UPENN-GBM", "Yale-Brain-Mets"]
TRAINED_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM",
                    "LUMIERE", "PROTEAS-brain-mets"]

# Disease taxonomy from v177 (3-class: GBM, glioma-other, brain-mets)
DISEASE_VEC = {
    "UCSF-POSTOP":         np.array([0.7, 0.3, 0.0]),
    "MU-Glioma-Post":      np.array([0.7, 0.3, 0.0]),
    "RHUH-GBM":            np.array([1.0, 0.0, 0.0]),
    "LUMIERE":             np.array([0.4, 0.6, 0.0]),
    "PROTEAS-brain-mets":  np.array([0.0, 0.0, 1.0]),
    "UPENN-GBM":           np.array([1.0, 0.0, 0.0]),
    "Yale-Brain-Mets":     np.array([0.0, 0.0, 1.0]),
}

S_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


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


def main():
    print("=" * 78, flush=True)
    print("v192 UOSL-GATED HYBRID DEPLOYMENT — round 30", flush=True)
    print("=" * 78, flush=True)

    # Load v184 (foundation+kernel ensemble metrics)
    v184 = json.loads((RESULTS / "v184_clinical_readiness.json").read_text())
    foundation = {}
    for c, s in v184["cohort_summaries"].items():
        foundation[c] = {
            "auc": s["auc_mean"],
            "dice": s["dice_mean"],
            # v184 used "coverage" implicitly via outgrowth; use vol_pred/vol_obs
            # as a proxy for coverage where it exists; or just use auc/dice
            "n": s["n_patients"],
        }

    # Load v189 kernel-only at sigma=3 metrics
    v189 = json.loads((RESULTS / "v189_training_free_kernel.json").read_text())
    kernel_s3 = {}
    for c, r in v189["per_cohort"].items():
        kernel_s3[c] = {
            "auc": r["per_sigma"]["sigma=3.0"]["auc_mean"],
            "dice": r["per_sigma"]["sigma=3.0"]["dice_mean"],
            "coverage": r["per_sigma"]["sigma=3.0"]["coverage_mean"],
            "n": r["n_patients"],
        }

    # Load v174 to get n_per_cohort
    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]
    print(f"\n  n_per_cohort: {n_per_cohort}", flush=True)

    # Compute UOSL S per cohort relative to 5-cohort training
    # For trained cohorts (LOCO held-out), training = other 4 cohorts
    # For external (UPENN, Yale), training = all 5 cohorts
    print("\n  UOSL similarity S per cohort:", flush=True)
    S_per_cohort = {}
    for c in ALL_COHORTS:
        if c in TRAINED_COHORTS:
            train_set = [tc for tc in TRAINED_COHORTS if tc != c]
        else:
            train_set = TRAINED_COHORTS
        td = cohort_weighted_distribution(train_set, n_per_cohort)
        S = similarity_index(td, c)
        S_per_cohort[c] = float(S)
        print(f"    {c:25s}  S = {S:.4f}", flush=True)

    # Build comparison: foundation, kernel_s3, hybrid for each S_threshold
    print("\n  Comparison across recipes (mean across 7 cohorts):",
          flush=True)
    headers = ["Recipe", "Mean AUC", "Mean Dice", "Mean coverage"]
    print(f"  {headers[0]:35s} {headers[1]:>10s} {headers[2]:>10s} "
          f"{headers[3]:>15s}", flush=True)

    def cohort_mean(metric_dict, key):
        vals = [metric_dict[c][key] for c in ALL_COHORTS
                if c in metric_dict
                and not np.isnan(metric_dict[c].get(key, float("nan")))]
        return float(np.mean(vals)) if vals else float("nan")

    foundation_mean_auc = cohort_mean(foundation, "auc")
    foundation_mean_dice = cohort_mean(foundation, "dice")
    kernel_mean_auc = cohort_mean(kernel_s3, "auc")
    kernel_mean_dice = cohort_mean(kernel_s3, "dice")
    kernel_mean_cov = cohort_mean(kernel_s3, "coverage")

    print(f"  {'Foundation alone (v184)':35s} {foundation_mean_auc:10.4f} "
          f"{foundation_mean_dice:10.4f} {'(see v184)':>15s}", flush=True)
    print(f"  {'Kernel-only sigma=3 (v189)':35s} {kernel_mean_auc:10.4f} "
          f"{kernel_mean_dice:10.4f} {kernel_mean_cov:15.4f}",
          flush=True)

    hybrid_results = {}
    for S_thr in S_THRESHOLDS:
        hybrid_per_cohort = {}
        for c in ALL_COHORTS:
            S = S_per_cohort[c]
            if S > S_thr:
                src = "foundation"
                metric = foundation.get(c, {})
                auc = metric.get("auc", float("nan"))
                dice = metric.get("dice", float("nan"))
            else:
                src = "kernel_s3"
                metric = kernel_s3.get(c, {})
                auc = metric.get("auc", float("nan"))
                dice = metric.get("dice", float("nan"))
            hybrid_per_cohort[c] = {
                "S": S, "source": src, "auc": auc, "dice": dice,
            }
        mean_auc = float(np.mean([v["auc"] for v in hybrid_per_cohort.values()
                                    if not np.isnan(v["auc"])]))
        mean_dice = float(np.mean([v["dice"] for v in hybrid_per_cohort.values()
                                     if not np.isnan(v["dice"])]))
        hybrid_results[S_thr] = {
            "S_threshold": S_thr,
            "per_cohort": hybrid_per_cohort,
            "mean_auc": mean_auc,
            "mean_dice": mean_dice,
        }
        # Routing summary
        route = {c: hybrid_per_cohort[c]["source"] for c in ALL_COHORTS}
        print(f"  Hybrid S>{S_thr:.1f}: mean AUC = {mean_auc:.4f}, "
              f"mean Dice = {mean_dice:.4f}", flush=True)
        for c in ALL_COHORTS:
            v = hybrid_per_cohort[c]
            print(f"    {c:25s}  S={v['S']:.3f}  -> {v['source']:12s}  "
                  f"AUC={v['auc']:.4f}  Dice={v['dice']:.4f}", flush=True)

    # Find best S_threshold by harmonic mean of (AUC, Dice)
    print("\n  Recipe ranking by harmonic mean of (AUC, Dice):", flush=True)
    candidates = [
        ("Foundation alone", foundation_mean_auc, foundation_mean_dice),
        ("Kernel-only sigma=3", kernel_mean_auc, kernel_mean_dice),
    ]
    for S_thr, r in hybrid_results.items():
        candidates.append((f"Hybrid S>{S_thr:.1f}",
                            r["mean_auc"], r["mean_dice"]))

    def harmonic(a, b):
        if a + b == 0 or np.isnan(a) or np.isnan(b):
            return float("nan")
        return 2 * a * b / (a + b)

    candidates_with_h = [
        (name, auc, dice, harmonic(auc, dice))
        for name, auc, dice in candidates
    ]
    candidates_with_h.sort(key=lambda x: -x[3])
    print(f"  {'Recipe':30s} {'AUC':>8s} {'Dice':>8s} "
          f"{'H-mean':>8s}", flush=True)
    for name, auc, dice, h in candidates_with_h:
        print(f"  {name:30s} {auc:8.4f} {dice:8.4f} {h:8.4f}",
              flush=True)

    # Save results
    out = {
        "version": "v192",
        "experiment": "UOSL-similarity-gated hybrid deployment",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_per_cohort": n_per_cohort,
        "S_per_cohort": S_per_cohort,
        "S_thresholds_tested": S_THRESHOLDS,
        "foundation_per_cohort": foundation,
        "kernel_s3_per_cohort": kernel_s3,
        "hybrid_results": {str(k): v for k, v in hybrid_results.items()},
        "summary_means": {
            "foundation": {"auc": foundation_mean_auc,
                            "dice": foundation_mean_dice},
            "kernel_s3": {"auc": kernel_mean_auc,
                           "dice": kernel_mean_dice,
                           "coverage": kernel_mean_cov},
        },
        "ranking_by_harmonic_mean_auc_dice": [
            {"recipe": name, "auc": auc, "dice": dice, "harmonic": h}
            for name, auc, dice, h in candidates_with_h
        ],
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
