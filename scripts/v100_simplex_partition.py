"""v100: Information-geometric simplex partition — visualises the K-class
composition-shift simplex partitioned into convex regions where each
candidate model is the optimal-Brier predictor.

This is the geometric interpretation of the multi-class adaptive-selector
theorem (MedIA paper Section 2.5.1). The simplex Delta^(K-1) of cohort
compositions pi = (pi_1, ..., pi_K) with sum pi_k = 1 is partitioned into
M convex polygonal regions R_j = { pi : L_m_j(pi) <= L_m_j'(pi) for all
j' != j }; the boundaries are linear hyperplanes (since L_m_j is linear in
pi); the optimal-model frontier is the convex hull of these hyperplanes.

Generates two panels:
  - K = 2: line segment [0, 1]; partition into 2 regions; pi* = 0.43 boundary.
  - K = 3: triangular simplex; partition into M regions for M model variants;
    hyperplane boundaries shown.

Outputs:
  C:/Users/kamru/Downloads/Nature_project/05_results/v100_simplex_partition.json
  C:/Users/kamru/Downloads/MedIA_Paper/figures/main/v100_simplex_partition.png
"""
import json
import time
from pathlib import Path

import numpy as np


ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
FIG_DIR = Path(r"C:\Users\kamru\Downloads\MedIA_Paper\figures\main")


def main():
    print("=" * 78)
    print("v100 INFORMATION-GEOMETRIC SIMPLEX PARTITION")
    print("=" * 78)

    # K = 2 case: closed-form crossover from MedIA paper (UCSF source values)
    L_h_s = 0.041   # heat-prior on stable
    L_h_a = 0.274   # heat-prior on active
    L_m_s = 0.140   # learned-mask on stable
    L_m_a = 0.199   # learned-mask on active
    pi_star_2 = (L_m_a - L_h_a) / ((L_m_a - L_h_a) + (L_h_s - L_m_s))
    print(f"K = 2 case (heat vs learned-mask, UCSF source):")
    print(f"  per-stratum Brier: L_h_s={L_h_s}, L_h_a={L_h_a}, L_m_s={L_m_s}, L_m_a={L_m_a}")
    print(f"  pi* = {pi_star_2:.4f}")

    # K = 3 case: extended stable/progressive/responsive (synthetic per-stratum)
    # 3 candidate models, 3 strata
    L = np.array([
        # stable, progressive, responsive
        [0.04, 0.30, 0.20],   # m1: heat-prior
        [0.14, 0.20, 0.18],   # m2: learned mask
        [0.20, 0.15, 0.10],   # m3: learned full-context
    ])
    print(f"\nK = 3 case (synthetic per-stratum Brier):")
    print(f"  m1 (heat-prior):       {L[0]}")
    print(f"  m2 (learned-mask):     {L[1]}")
    print(f"  m3 (learned-context):  {L[2]}")

    # Sample the K=3 simplex on a grid and find the optimal model at each point
    n_grid = 100
    pi_1 = np.linspace(0, 1, n_grid)
    pi_2 = np.linspace(0, 1, n_grid)
    optimal_model = np.full((n_grid, n_grid), -1, dtype=int)
    for i, p1 in enumerate(pi_1):
        for j, p2 in enumerate(pi_2):
            if p1 + p2 > 1.0 + 1e-9:
                continue
            p3 = 1 - p1 - p2
            briers = L[:, 0] * p1 + L[:, 1] * p2 + L[:, 2] * p3
            optimal_model[i, j] = int(np.argmin(briers))

    # Compute hyperplane equations for boundaries between models
    # Boundary between m_i and m_j: (L_i_s - L_j_s) pi_s + (L_i_p - L_j_p) pi_p + (L_i_r - L_j_r) pi_r = 0
    # With pi_r = 1 - pi_s - pi_p: a*pi_s + b*pi_p + c = 0
    boundaries = []
    M = L.shape[0]
    for i in range(M):
        for j in range(i + 1, M):
            a = (L[i, 0] - L[j, 0]) - (L[i, 2] - L[j, 2])
            b = (L[i, 1] - L[j, 1]) - (L[i, 2] - L[j, 2])
            c = L[i, 2] - L[j, 2]
            boundaries.append({"m_i": i, "m_j": j, "a_pi_s": float(a), "b_pi_p": float(b), "c_const": float(c)})

    # Region statistics
    region_areas = {}
    for k in range(M):
        mask = optimal_model == k
        # Approximate area as fraction of grid points in valid simplex
        valid = optimal_model >= 0
        region_areas[f"m{k}_area_fraction"] = float(mask.sum() / max(valid.sum(), 1))

    # Output JSON
    out = {
        "version": "v100",
        "experiment": "Information-geometric simplex partition (K=2 binary; K=3 multi-class)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "K_2_case": {
            "per_stratum_brier": {"L_heat_stable": L_h_s, "L_heat_active": L_h_a,
                                   "L_learned_stable": L_m_s, "L_learned_active": L_m_a},
            "pi_star": float(pi_star_2),
        },
        "K_3_case": {
            "model_per_stratum_brier": L.tolist(),
            "n_models": M,
            "n_strata": L.shape[1],
            "region_areas": region_areas,
            "hyperplane_boundaries": boundaries,
            "interpretation": "Region R_j contains the simplex points where model m_j achieves minimum Brier; boundaries are linear hyperplanes parameterised by per-stratum Brier differences.",
        },
    }
    out_path = RESULTS / "v100_simplex_partition.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")

    # Generate visualisation
    try:
        import matplotlib.pyplot as plt
        FIG_DIR.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # K=2 panel
        ax = axes[0]
        pi_grid = np.linspace(0, 1, 200)
        L_heat_pi = pi_grid * L_h_s + (1 - pi_grid) * L_h_a
        L_learn_pi = pi_grid * L_m_s + (1 - pi_grid) * L_m_a
        ax.plot(pi_grid, L_heat_pi, label='Heat prior (m1)', linewidth=2)
        ax.plot(pi_grid, L_learn_pi, label='Learned (m2)', linewidth=2)
        ax.axvline(pi_star_2, color='red', linestyle='--', label=f'$\\pi^*$ = {pi_star_2:.3f}')
        ax.fill_between(pi_grid, 0, np.minimum(L_heat_pi, L_learn_pi), alpha=0.15, color='gray', label='Optimal-model frontier')
        ax.set_xlabel('$\\pi_{stable}$')
        ax.set_ylabel('Mixture-weighted Brier $L_m(\\pi)$')
        ax.set_title('K = 2 binary simplex partition')
        ax.legend(loc='upper center', fontsize=8)
        ax.set_xlim(0, 1); ax.set_ylim(0, 0.30)
        ax.grid(True, alpha=0.3)

        # K=3 panel: triangular simplex with model regions
        ax = axes[1]
        # Convert (pi_1, pi_2) grid to barycentric for plotting
        # Use simple 2D plot with pi_1 on x, pi_2 on y, pi_3 = 1 - pi_1 - pi_2
        for k in range(M):
            mask = optimal_model == k
            ax.scatter(pi_1[np.where(mask)[0]] if mask.any() else [],
                       pi_2[np.where(mask)[1]] if mask.any() else [],
                       label=f'm{k+1} optimal', s=2, alpha=0.4)
        # Better: use imshow with masked array
        ax.cla()
        # Construct displayable image
        masked = np.ma.masked_array(optimal_model.T, mask=(optimal_model.T < 0))
        im = ax.imshow(masked, origin='lower', extent=[0, 1, 0, 1], cmap='Set2',
                       vmin=0, vmax=M-1, aspect='auto', alpha=0.6)
        ax.plot([0, 1, 0, 0], [0, 0, 1, 0], 'k-', linewidth=1)
        ax.set_xlabel('$\\pi_{stable}$')
        ax.set_ylabel('$\\pi_{progressive}$')
        ax.set_title(f'K = 3 multi-class simplex partition\\n($\\pi_{{responsive}} = 1 - \\pi_s - \\pi_p$)')
        # Manual legend
        from matplotlib.patches import Patch
        cmap = plt.cm.Set2
        legend_elems = [
            Patch(facecolor=cmap(0/(M-1)), label='m1 (heat-prior) optimal'),
            Patch(facecolor=cmap(1/(M-1)), label='m2 (learned-mask) optimal'),
            Patch(facecolor=cmap(2/(M-1)), label='m3 (learned-context) optimal'),
        ]
        ax.legend(handles=legend_elems, loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)

        fig.suptitle('Information-geometric simplex partition for composition-shift ranking', fontsize=12)
        fig.tight_layout()
        fig_path = FIG_DIR / "v100_simplex_partition.png"
        fig.savefig(fig_path, dpi=300, bbox_inches='tight')
        print(f"Saved figure: {fig_path}")
    except Exception as e:
        print(f"Figure generation failed: {e}")


if __name__ == "__main__":
    main()
