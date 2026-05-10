"""v198 figures (Fig 49-50): MU replication HONEST NEGATIVE refutes round 35."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
FIG_DIRS = [
    Path(r"C:\Users\kamru\Downloads\MedIA_Paper\figures"),
    Path(r"C:\Users\kamru\Downloads\RTO_paper\figures"),
]
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})


def save_fig(fig, name):
    paths = []
    for d in FIG_DIRS:
        p_png = d / f"{name}.png"
        p_pdf = d / f"{name}.pdf"
        fig.savefig(p_png, dpi=300)
        fig.savefig(p_pdf)
        paths.append(str(p_png))
    plt.close(fig)
    return paths


def figure_49_replication_comparison():
    print("Figure 49: RHUH vs MU C-index comparison", flush=True)
    v198 = json.loads((RESULTS / "v198_mu_replication.json").read_text())
    mc = v198["multivariate_cox"]

    # Round-35 RHUH reference
    rhuh = {"M0": 0.7833, "M1": 0.8000, "M2": 0.8833,
              "LRT_M2_p": 0.0018, "n": 13}
    mu = {"M0": mc["M0_c_index"], "M1": mc["M1_c_index"],
            "M2": mc["M2_c_index"],
            "LRT_M2_p": mc["LRT_M0_vs_M2"]["p_value"],
            "n": v198["n_complete_case"]}

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.5))

    # Left: RHUH bars
    models = ["M0\nClinical", "M1\n+λ", "M2\n+λ+V_kernel"]
    rhuh_vals = [rhuh["M0"], rhuh["M1"], rhuh["M2"]]
    colors_rhuh = ["#999999", "#56B4E9", "#009E73"]
    axes[0].bar(models, rhuh_vals, color=colors_rhuh,
                  edgecolor="black", linewidth=0.5)
    for i, c in enumerate(rhuh_vals):
        axes[0].text(i, c + 0.01, f"{c:.4f}", ha="center",
                       fontsize=11, fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.5)
    axes[0].set_ylim(0.4, 1.0)
    axes[0].set_ylabel("Harrell's C-index")
    axes[0].set_title(f"Round 35 RHUH-GBM (n={rhuh['n']})\n"
                        f"M0 vs M2 LRT p = {rhuh['LRT_M2_p']:.4f} (***)\n"
                        f"PRELIMINARY SYNERGY")

    # Right: MU bars
    mu_vals = [mu["M0"], mu["M1"], mu["M2"]]
    colors_mu = ["#999999", "#D55E00", "#D55E00"]
    axes[1].bar(models, mu_vals, color=colors_mu,
                  edgecolor="black", linewidth=0.5)
    for i, c in enumerate(mu_vals):
        axes[1].text(i, c + 0.01, f"{c:.4f}", ha="center",
                       fontsize=11, fontweight="bold")
    axes[1].axhline(0.5, color="grey", linestyle="--", alpha=0.5)
    axes[1].set_ylim(0.4, 1.0)
    axes[1].set_ylabel("Harrell's C-index")
    axes[1].set_title(f"Round 36 v198 MU-Glioma-Post REPLICATION (n={mu['n']})\n"
                        f"M0 vs M2 LRT p = {mu['LRT_M2_p']:.4f} (NS)\n"
                        f"SYNERGY DOES NOT REPLICATE")

    fig.suptitle("v198 HONEST NEGATIVE: round-35 RHUH n=13 synergy does NOT "
                  "replicate on MU n=49\n"
                  "Adding λ+V_kernel REDUCES C-index on MU (Δ = -0.05) — "
                  "round 35 was overfit",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig49_RHUH_vs_MU_replication")


def figure_50_paper_a5_three_layer_status():
    print("Figure 50: Paper A5 three-layer narrative status", flush=True)
    fig, ax = plt.subplots(figsize=(11.0, 6.0))

    layers = [
        ("Layer 1\nPopulation scaling law\n(round 23 v185)",
         "P(d) = A * exp(-d/λ)\nfit on 7 cohorts;\nR² = 0.32 to 0.87",
         "✓ CONFIRMED"),
        ("Layer 2\nPer-patient biomarker\n(round 34 v196)",
         "λ is patient-intrinsic;\nICC-proxy = 0.834\nin PROTEAS longitudinal",
         "✓ CONFIRMED"),
        ("Layer 3\nClinical prognostic\n(rounds 35-36 v197/v198)",
         "λ+V_kernel synergy\nRHUH n=13: p=0.0018\n→ MU n=49: p=0.25\n(REFUTED on replication)",
         "✗ REFUTED"),
    ]

    x_positions = [0, 1, 2]
    colors = ["#009E73", "#009E73", "#D55E00"]
    for x, (title, body, status), color in zip(x_positions, layers, colors):
        # Box
        ax.add_patch(plt.Rectangle((x - 0.4, 0.05), 0.8, 0.85,
                                       facecolor=color, alpha=0.15,
                                       edgecolor=color, linewidth=2))
        # Title
        ax.text(x, 0.85, title, ha="center", va="top",
                fontsize=11, fontweight="bold")
        # Body
        ax.text(x, 0.55, body, ha="center", va="center",
                fontsize=10)
        # Status
        ax.text(x, 0.18, status, ha="center", va="center",
                fontsize=14, fontweight="bold", color=color)

    # Arrows between layers
    for x in [0, 1]:
        ax.annotate("", xy=(x + 1 - 0.42, 0.5),
                     xytext=(x + 0.42, 0.5),
                     arrowprops=dict(arrowstyle="->", lw=2,
                                       color="grey"))

    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Paper A5 (UODSL) THREE-LAYER NARRATIVE — "
                  "post-round-36 honest scoping\n"
                  "Layers 1-2 stand; layer 3 (clinical prognostic) is "
                  "REFUTED on replication",
                  fontsize=12, y=1.02)
    return save_fig(fig, "fig50_paper_a5_three_layer_status")


def main():
    figure_49_replication_comparison()
    figure_50_paper_a5_three_layer_status()
    print("done", flush=True)


if __name__ == "__main__":
    main()
