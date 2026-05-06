"""v84 retry: just run E3 (conformal), E4 (negative controls), E5 (Bernstein bound)
on already-cached data. Saves master summary by combining with E1/E2 from JSON.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v84_complete_experiments import (
    E3_conformal_coverage, E4_negative_controls, E5_empirical_bernstein_bound,
    RESULTS, np
)


def main():
    cache = dict(np.load(RESULTS / "v78_raw_mri_loco_cache.npz", allow_pickle=True))

    e1 = json.loads((RESULTS / "v84_E1_improved_rasn.json").read_text())
    e2 = json.loads((RESULTS / "v84_E2_hard_router.json").read_text())

    print("\n[E3] Conformal coverage")
    e3 = E3_conformal_coverage()
    (RESULTS / "v84_E3_conformal_coverage.json").write_text(json.dumps(e3, indent=2, default=str))

    print("\n[E4] Negative controls")
    e4 = E4_negative_controls(cache)
    (RESULTS / "v84_E4_negative_controls.json").write_text(json.dumps(e4, indent=2, default=str))

    print("\n[E5] Empirical-Bernstein bound")
    e5 = E5_empirical_bernstein_bound()
    (RESULTS / "v84_E5_empirical_bernstein.json").write_text(json.dumps(e5, indent=2, default=str))

    # Master summary
    summary = {
        "version": "v84_master",
        "timestamp": "2026-05-06",
        "E1_seeds_completed": len(e1),
        "E1_rasn_beats_best_count": sum(1 for r in e1 if r.get("rasn_beats_best_individual")),
        "E1_rasn_beats_best_per_cohort": {
            cohort: sum(1 for r in e1 if r.get("held_out") == cohort and r.get("rasn_beats_best_individual"))
            for cohort in ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]
        },
        "E1_mean_regret_vs_oracle": float(np.mean([r["regret_vs_oracle"] for r in e1])),
        "E1_per_cohort_mean_regret": {
            cohort: float(np.mean([r["regret_vs_oracle"] for r in e1 if r.get("held_out") == cohort]))
            for cohort in ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]
        },
        "E2_hard_router_summary": [
            {"cohort": r["held_out"],
             "rasn_brier": r["rasn_brier_mean"],
             "heat_brier": r["heat_brier_mean"],
             "learnt_brier": r["learned_unet_brier_mean"]}
            for r in e2
        ],
        "E3_coverage": {k: e3["results"][k]["empirical_coverage"] for k in e3["results"]},
        "E4_max_fold_increase": float(max(e4["fold_increase"].values())),
        "E4_min_fold_increase": float(min(e4["fold_increase"].values())),
        "E4_baseline_brier": e4["ucsf_baseline_heat_brier"],
        "E5_bernstein_factor_at_dpi_010": e5["bounds_per_delta_pi"][2]["bernstein_tighter_factor"],
    }
    (RESULTS / "v84_master_summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("\n" + "=" * 78)
    print("MASTER SUMMARY:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 78)


if __name__ == "__main__":
    main()
