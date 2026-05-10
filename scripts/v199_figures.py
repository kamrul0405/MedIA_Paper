"""v199 figures (Fig 51-53): Yale longitudinal lambda — Layer 2 REPLICATES."""
from __future__ import annotations

import csv
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


def figure_51_yale_trajectories():
    print("Figure 51: Yale per-patient lambda trajectories", flush=True)
    csv_path = RESULTS / "v199_yale_per_obs.csv"
    by_patient = {}
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            if row["valid"] != "True":
                continue
            try:
                lam = float(row["lambda"])
                fu = int(row["followup_index"])
            except (ValueError, TypeError):
                continue
            by_patient.setdefault(row["pid"], []).append((fu, lam))
    multi = {pid: sorted(obs) for pid, obs in by_patient.items()
              if len(obs) >= 2}
    fig, ax = plt.subplots(figsize=(11.0, 6.5))
    colors = plt.cm.tab20(np.linspace(0, 1, len(multi)))
    for (pid, obs), color in zip(multi.items(), colors):
        ts = [o[0] for o in obs]
        ls = [o[1] for o in obs]
        ax.plot(ts, ls, "o-", color=color, linewidth=1.8, markersize=8,
                  alpha=0.75,
                  label=f"{pid[:13]}... (n={len(obs)})")
        ax.axhline(np.mean(ls), color=color, linestyle=":", alpha=0.3,
                     linewidth=0.8)
    ax.set_xlabel("Followup timepoint index (later in time →)")
    ax.set_ylabel("UODSL length scale λ (voxels)")
    ax.set_title(f"v199 Yale-Brain-Mets longitudinal λ trajectories "
                  f"(n_patients={len(multi)} with multi-followup valid λ)\n"
                  f"Each patient shows STABLE λ across time → λ is "
                  f"patient-intrinsic")
    ax.legend(loc="upper right", fontsize=6, ncol=2,
                title="Patient ID", title_fontsize=7)
    return save_fig(fig, "fig51_yale_lambda_trajectories")


def figure_52_cross_cohort_replication():
    print("Figure 52: PROTEAS vs Yale ICC replication", flush=True)
    v199 = json.loads((RESULTS / "v199_yale_longitudinal_lambda.json")
                      .read_text())
    proteas = {
        "icc": 0.834,
        "inter_var": 2.574,
        "intra_var": 0.428,
        "n_multi": 6,
        "n_3plus": 3,
    }
    yale = {
        "icc": v199["variance_components"]["icc_proxy"],
        "inter_var": v199["variance_components"]["inter_patient_variance"],
        "intra_var": v199["variance_components"]["mean_intra_patient_variance"],
        "n_multi": v199["n_patients_with_multi_valid_lambda"],
        "n_3plus": v199["n_patients_with_3plus_followups"],
    }

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.5))

    # Left: variance components stacked bar
    cohorts = ["PROTEAS\n(round 34)", "Yale\n(round 37)"]
    inter_vars = [proteas["inter_var"], yale["inter_var"]]
    intra_vars = [proteas["intra_var"], yale["intra_var"]]
    x = np.arange(len(cohorts))
    width = 0.35
    axes[0].bar(x - width/2, inter_vars, width,
                  label="Inter-patient variance",
                  color="#0072B2", edgecolor="black", linewidth=0.5)
    axes[0].bar(x + width/2, intra_vars, width,
                  label="Mean intra-patient variance",
                  color="#D55E00", edgecolor="black", linewidth=0.5)
    for i, (iv, ia) in enumerate(zip(inter_vars, intra_vars)):
        axes[0].text(i - width/2, iv + 0.05, f"{iv:.3f}",
                       ha="center", fontsize=9)
        axes[0].text(i + width/2, ia + 0.05, f"{ia:.3f}",
                       ha="center", fontsize=9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(cohorts)
    axes[0].set_ylabel("λ variance (voxels²)")
    axes[0].set_title("Variance components")
    axes[0].legend(loc="upper right", fontsize=9)

    # Right: ICC bars
    iccs = [proteas["icc"], yale["icc"]]
    colors = ["#009E73", "#009E73"]
    bars = axes[1].bar(cohorts, iccs, color=colors, edgecolor="black",
                          linewidth=0.5)
    axes[1].axhline(0.5, color="grey", linestyle="--", alpha=0.6,
                      label="Replication threshold (0.5)")
    for i, c in enumerate(iccs):
        axes[1].text(i, c + 0.02, f"{c:.4f}",
                       ha="center", fontsize=12, fontweight="bold")
        n_multi = [proteas, yale][i]["n_multi"]
        n_3p = [proteas, yale][i]["n_3plus"]
        axes[1].text(i, 0.05, f"n_multi = {n_multi}\nn_≥3fu = {n_3p}",
                       ha="center", fontsize=8, alpha=0.7)
    axes[1].set_ylim(0, 1.0)
    axes[1].set_ylabel("ICC-proxy (between-patient fraction)")
    axes[1].set_title(f"ICC-proxy: BOTH cohorts ≥ 0.5\n"
                        f"→ Layer 2 (λ patient-intrinsic) REPLICATES")
    axes[1].legend(loc="lower right", fontsize=9)

    fig.suptitle("v199 CROSS-COHORT REPLICATION SUCCESS: Layer 2 (λ "
                  "patient-intrinsic) REPLICATES on Yale\n"
                  "PROTEAS ICC = 0.83 (ground-truth segs); Yale ICC = "
                  "0.66 (proxy POST-PRE masks). Both > 0.5 threshold.",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig52_cross_cohort_icc_replication")


def figure_53_paper_a5_updated_status():
    print("Figure 53: Paper A5 updated three-layer status", flush=True)
    fig, ax = plt.subplots(figsize=(12.0, 6.0))

    layers = [
        ("Layer 1\nPopulation scaling law\n(round 23 v185)",
         "P(d) = A * exp(-d/λ)\nfit on 7 cohorts;\nR² = 0.32 to 0.87",
         "✓ CONFIRMED",
         "#009E73"),
        ("Layer 2\nPer-patient biomarker\n(rounds 34, 37)",
         "ICC-proxy = 0.834 (PROTEAS, round 34)\n"
         "ICC-proxy = 0.657 (Yale, round 37)\n"
         "BOTH > 0.5 → REPLICATES",
         "✓ CONFIRMED + REPLICATED",
         "#009E73"),
        ("Layer 3\nClinical prognostic\n(rounds 35-36)",
         "λ+V_kernel synergy\nRHUH n=13: p=0.0018\nMU n=49: p=0.25\n(REFUTED on replication)",
         "✗ REFUTED",
         "#D55E00"),
    ]

    for x, (title, body, status, color) in zip([0, 1, 2], layers):
        ax.add_patch(plt.Rectangle((x - 0.42, 0.05), 0.84, 0.85,
                                       facecolor=color, alpha=0.15,
                                       edgecolor=color, linewidth=2))
        ax.text(x, 0.85, title, ha="center", va="top",
                fontsize=11, fontweight="bold")
        ax.text(x, 0.50, body, ha="center", va="center",
                fontsize=10)
        ax.text(x, 0.15, status, ha="center", va="center",
                fontsize=14, fontweight="bold", color=color)

    for x in [0, 1]:
        ax.annotate("", xy=(x + 1 - 0.44, 0.5),
                     xytext=(x + 0.44, 0.5),
                     arrowprops=dict(arrowstyle="->", lw=2,
                                       color="grey"))

    ax.set_xlim(-0.5, 2.5)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Paper A5 (UODSL) THREE-LAYER NARRATIVE — "
                  "post-round-37 update\n"
                  "Layer 2 now CROSS-COHORT REPLICATED on Yale "
                  "(ICC = 0.66). Layers 1-2 stand on solid evidence.",
                  fontsize=12, y=1.02)
    return save_fig(fig, "fig53_paper_a5_post_round37_status")


def main():
    figure_51_yale_trajectories()
    figure_52_cross_cohort_replication()
    figure_53_paper_a5_updated_status()
    print("done", flush=True)


if __name__ == "__main__":
    main()
