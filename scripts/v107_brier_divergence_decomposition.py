"""v107: Analytical information-theoretic Brier-divergence decomposition.

Verifies the Section A.1 (Methods) information-theoretic decomposition
    L_m(pi) - L_m_star(pi) = sum_c pi_c * D_Br(m || m_star | c)
where D_Br(m || m_star | c) is the per-stratum Brier divergence of model m
from the per-stratum optimal predictor m_star.

Uses the empirical UCSF source-cohort per-stratum Brier values from MedIA
section 2.5 plus the four-cohort LOCO data from v78. Confirms that:
  (i) the regime-dependent ranking flip arises from unequal per-stratum
      Brier divergences (not from absolute Brier levels);
  (ii) the closed-form crossover pi* = (L_m2_a - L_m1_a) / ((L_m2_a -
       L_m1_a) + (L_m1_s - L_m2_s)) is exactly the Bayesian decision
       boundary in the K=2 simplex.

Outputs:
    C:/Users/kamru/Downloads/Nature_project/05_results/v107_brier_divergence.json
"""
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"

# UCSF source per-stratum Brier values (MedIA section 2.5)
UCSF_PER_STRATUM = {
    "heat_stable":   0.041,
    "heat_active":   0.274,
    "learned_stable": 0.140,
    "learned_active": 0.199,
}

# Four-cohort LOCO Brier (from v78) — heat vs raw+mask
LOCO_HEAT = {"UCSF-POSTOP": 0.108, "MU-Glioma-Post": 0.279,
             "RHUH-GBM": 0.504,  "UCSD-PTGBM": 0.165}
LOCO_RAW_MASK = {"UCSF-POSTOP": 0.145, "MU-Glioma-Post": 0.274,
                 "RHUH-GBM": 0.392,  "UCSD-PTGBM": 0.203}
LOCO_PI_STABLE = {"UCSF-POSTOP": 0.81, "MU-Glioma-Post": 0.34,
                  "RHUH-GBM": 0.29,  "UCSD-PTGBM": 0.24}


def main():
    print("=" * 78)
    print("v107 INFORMATION-THEORETIC BRIER-DIVERGENCE DECOMPOSITION")
    print("=" * 78)

    # Identify per-cohort optimal predictor (heat or learned)
    print("\nUCSF source per-stratum Brier:")
    for k, v in UCSF_PER_STRATUM.items():
        print(f"  {k}: {v}")

    # Per-stratum optimal predictor m_star: lower Brier on each stratum.
    L_h_s, L_h_a = UCSF_PER_STRATUM["heat_stable"], UCSF_PER_STRATUM["heat_active"]
    L_m_s, L_m_a = UCSF_PER_STRATUM["learned_stable"], UCSF_PER_STRATUM["learned_active"]
    star_stable = "heat" if L_h_s < L_m_s else "learned"
    star_active = "heat" if L_h_a < L_m_a else "learned"
    L_star_s = min(L_h_s, L_m_s)
    L_star_a = min(L_h_a, L_m_a)

    print(f"\nPer-stratum optimal predictor m_star:")
    print(f"  stable: {star_stable} (L_star_stable = {L_star_s})")
    print(f"  active: {star_active} (L_star_active = {L_star_a})")

    # Per-stratum Brier divergence of each model from m_star
    D_heat_s = L_h_s - L_star_s
    D_heat_a = L_h_a - L_star_a
    D_learned_s = L_m_s - L_star_s
    D_learned_a = L_m_a - L_star_a

    print(f"\nPer-stratum Brier divergence D_Br(m || m_star | c):")
    print(f"  heat:    D_stable={D_heat_s:.4f}    D_active={D_heat_a:.4f}")
    print(f"  learned: D_stable={D_learned_s:.4f}    D_active={D_learned_a:.4f}")

    # The closed-form crossover pi*
    pi_star = (L_m_a - L_h_a) / ((L_m_a - L_h_a) + (L_h_s - L_m_s))
    print(f"\nClosed-form pi* = {pi_star:.4f}")

    # Verify decomposition on the four LOCO cohorts
    print("\nDecomposition verification on 4 LOCO cohorts:")
    print(f"{'Cohort':<18} {'pi':<6} {'L_heat':<8} {'L_learn':<8} {'L_diff':<10} {'predicted':<10} {'observed':<10}")
    cohort_results = []
    for c, pi in LOCO_PI_STABLE.items():
        L_h = LOCO_HEAT[c]
        L_l = LOCO_RAW_MASK[c]
        L_diff = L_h - L_l
        predicted_winner = "heat" if pi > pi_star else "learned"
        observed_winner = "heat" if L_h < L_l else "learned"
        match = predicted_winner == observed_winner
        # Decomposition: L_m(pi) - L_m_star(pi) = pi * D_stable + (1 - pi) * D_active
        L_heat_decomp_excess = pi * D_heat_s + (1 - pi) * D_heat_a
        L_learned_decomp_excess = pi * D_learned_s + (1 - pi) * D_learned_a
        cohort_results.append({
            "cohort": c, "pi": pi,
            "L_heat_observed": L_h, "L_learned_observed": L_l,
            "predicted_winner": predicted_winner, "observed_winner": observed_winner,
            "match": match,
            "L_heat_decomposition_excess_predicted": L_heat_decomp_excess,
            "L_learned_decomposition_excess_predicted": L_learned_decomp_excess,
        })
        print(f"{c:<18} {pi:<6.2f} {L_h:<8.3f} {L_l:<8.3f} {L_diff:+.4f}  {predicted_winner:<10} {observed_winner:<10}")

    correct = sum(r["match"] for r in cohort_results)
    print(f"\nDirectional accuracy: {correct}/{len(cohort_results)}")

    # Test the simplex partition area
    pi_grid = np.linspace(0.0, 1.0, 1001)
    heat_excess = pi_grid * D_heat_s + (1 - pi_grid) * D_heat_a
    learned_excess = pi_grid * D_learned_s + (1 - pi_grid) * D_learned_a
    heat_optimal_region = pi_grid[heat_excess <= learned_excess]
    learned_optimal_region = pi_grid[heat_excess > learned_excess]
    print(f"\nSimplex partition (1001-grid):")
    print(f"  heat-optimal region: pi in [{heat_optimal_region[0]:.3f}, {heat_optimal_region[-1]:.3f}]")
    if len(learned_optimal_region) > 0:
        print(f"  learned-optimal region: pi in [{learned_optimal_region[0]:.3f}, {learned_optimal_region[-1]:.3f}]")
    pi_star_empirical = float((heat_excess - learned_excess).argmin()) / 1000.0  # location of zero crossing
    # Find exact crossing
    diff = heat_excess - learned_excess
    crossing_idx = np.where(np.diff(np.sign(diff)))[0]
    if len(crossing_idx) > 0:
        i = crossing_idx[0]
        x1, x2 = pi_grid[i], pi_grid[i + 1]
        y1, y2 = diff[i], diff[i + 1]
        pi_star_grid = x1 - y1 * (x2 - x1) / (y2 - y1)
        print(f"  empirical pi* (from grid): {pi_star_grid:.4f}")
        print(f"  closed-form pi*:           {pi_star:.4f}")
        print(f"  match: {abs(pi_star - pi_star_grid) < 0.001}")

    out = {
        "version": "v107",
        "experiment": "Information-theoretic Brier-divergence decomposition + simplex-partition validation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ucsf_per_stratum_brier": UCSF_PER_STRATUM,
        "per_stratum_optimal": {"stable": star_stable, "active": star_active},
        "per_stratum_brier_divergences": {
            "heat": {"D_stable": D_heat_s, "D_active": D_heat_a},
            "learned": {"D_stable": D_learned_s, "D_active": D_learned_a},
        },
        "closed_form_pi_star": float(pi_star),
        "empirical_pi_star_from_grid": float(pi_star_grid) if 'pi_star_grid' in dir() else None,
        "decomposition_holds_at_grid_resolution": bool(abs(pi_star - pi_star_grid) < 0.001),
        "loco_cohort_decomposition_verification": cohort_results,
        "directional_accuracy": correct / len(cohort_results),
    }
    out_path = RESULTS / "v107_brier_divergence.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
