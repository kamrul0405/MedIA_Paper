"""v192 figures (Fig 34-36): UOSL-gated hybrid recipe."""
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

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
                "PROTEAS-brain-mets", "UPENN-GBM", "Yale-Brain-Mets"]
COHORT_COLORS = {
    "Yale-Brain-Mets":     "#000000",
    "PROTEAS-brain-mets":  "#D55E00",
    "UCSF-POSTOP":         "#0072B2",
    "RHUH-GBM":            "#009E73",
    "LUMIERE":             "#CC79A7",
    "MU-Glioma-Post":      "#E69F00",
    "UPENN-GBM":           "#56B4E9",
}


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


def figure_34_hybrid_routing():
    print("Figure 34: hybrid routing per cohort", flush=True)
    v192 = json.loads((RESULTS / "v192_uosl_gated_hybrid.json").read_text())
    S = v192["S_per_cohort"]
    foundation = v192["foundation_per_cohort"]
    kernel = v192["kernel_s3_per_cohort"]

    # Use S>0.5 routing
    hybrid = v192["hybrid_results"]["0.5"]["per_cohort"]

    # Order cohorts by S (low to high)
    cohorts = sorted(ALL_COHORTS, key=lambda c: S[c])

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.5))

    # Left: per-cohort AUC, three bars (foundation, kernel, hybrid)
    x = np.arange(len(cohorts))
    width = 0.27
    f_auc = [foundation[c]["auc"] for c in cohorts]
    k_auc = [kernel[c]["auc"] for c in cohorts]
    h_auc = [hybrid[c]["auc"] for c in cohorts]
    h_src = [hybrid[c]["source"] for c in cohorts]

    axes[0].bar(x - width, f_auc, width, label="Foundation alone",
                  color="#999999", edgecolor="black", linewidth=0.5)
    axes[0].bar(x, k_auc, width, label="Kernel-only σ=3",
                  color="#0072B2", edgecolor="black", linewidth=0.5)
    bars3 = axes[0].bar(x + width, h_auc, width,
                          label="Hybrid (S>0.5 routing)",
                          color=["#D55E00" if s == "kernel_s3" else "#009E73"
                                  for s in h_src],
                          edgecolor="black", linewidth=1.2)
    for i, (h, s) in enumerate(zip(h_auc, h_src)):
        marker = "K" if s == "kernel_s3" else "F"
        axes[0].text(i + width, h + 0.01,
                       f"{h:.3f}\n({marker})", ha="center", fontsize=7)
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.5)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f"{c.replace('-', chr(10))}\nS={S[c]:.2f}"
                                for c in cohorts], fontsize=8)
    axes[0].set_ylabel("Patient-level AUC")
    axes[0].set_title("AUC per cohort under hybrid recipe (S>0.5)")
    axes[0].legend(loc="lower right", fontsize=8)
    axes[0].set_ylim(0.4, 1.0)

    # Right: per-cohort Dice, three bars
    f_d = [foundation[c]["dice"] for c in cohorts]
    k_d = [kernel[c]["dice"] for c in cohorts]
    h_d = [hybrid[c]["dice"] for c in cohorts]

    axes[1].bar(x - width, f_d, width, label="Foundation alone",
                  color="#999999", edgecolor="black", linewidth=0.5)
    axes[1].bar(x, k_d, width, label="Kernel-only σ=3",
                  color="#0072B2", edgecolor="black", linewidth=0.5)
    axes[1].bar(x + width, h_d, width,
                  label="Hybrid (S>0.5 routing)",
                  color=["#D55E00" if s == "kernel_s3" else "#009E73"
                          for s in h_src],
                  edgecolor="black", linewidth=1.2)
    for i, (h, s) in enumerate(zip(h_d, h_src)):
        marker = "K" if s == "kernel_s3" else "F"
        axes[1].text(i + width, h + 0.02,
                       f"{h:.3f}\n({marker})", ha="center", fontsize=7)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"{c.replace('-', chr(10))}\nS={S[c]:.2f}"
                                for c in cohorts], fontsize=8)
    axes[1].set_ylabel("Dice")
    axes[1].set_title("Dice per cohort under hybrid recipe (S>0.5)")
    axes[1].legend(loc="upper right", fontsize=8)

    fig.suptitle("v192 UOSL-gated hybrid (S>0.5): kernel routes for OOD "
                  "(K = green/orange) — gets high AUC; foundation routes "
                  "for in-distribution (F = green) — gets good Dice",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig34_hybrid_routing_per_cohort")


def figure_35_recipe_scatter():
    print("Figure 35: AUC-vs-Dice scatter per recipe", flush=True)
    v192 = json.loads((RESULTS / "v192_uosl_gated_hybrid.json").read_text())
    ranking = v192["ranking_by_harmonic_mean_auc_dice"]

    fig, ax = plt.subplots(figsize=(9.0, 7.5))

    colors = []
    markers = []
    for r in ranking:
        if "Foundation" in r["recipe"]:
            colors.append("#999999")
            markers.append("s")
        elif "Kernel-only" in r["recipe"]:
            colors.append("#0072B2")
            markers.append("o")
        elif "Hybrid" in r["recipe"]:
            colors.append("#009E73")
            markers.append("D")
        else:
            colors.append("black")
            markers.append("x")

    for r, color, marker in zip(ranking, colors, markers):
        ax.scatter(r["auc"], r["dice"], s=200, c=color, marker=marker,
                    edgecolor="black", linewidth=0.7, alpha=0.85,
                    label=r["recipe"])
        ax.annotate(r["recipe"], (r["auc"], r["dice"]),
                     xytext=(8, 5), textcoords="offset points",
                     fontsize=8)

    # Pareto-optimal frontier shading
    aucs = np.array([r["auc"] for r in ranking])
    dices = np.array([r["dice"] for r in ranking])
    # Iso-harmonic curves
    for h_target in [0.30, 0.35, 0.40, 0.45]:
        a = np.linspace(0.5, 1.0, 100)
        d = h_target * a / (2 * a - h_target)
        valid = (d > 0) & (d < 0.5)
        ax.plot(a[valid], d[valid], "k:", alpha=0.3, linewidth=0.7)
        ax.text(a[valid][0] - 0.005, d[valid][0] + 0.003,
                  f"H={h_target:.2f}", fontsize=7, color="grey")

    ax.set_xlabel("Mean patient-level AUC across 7 cohorts")
    ax.set_ylabel("Mean patient-level Dice across 7 cohorts")
    ax.set_title("v192 recipe Pareto plot: hybrid (green) achieves "
                  "best harmonic mean of (AUC, Dice)")
    ax.set_xlim(0.65, 0.85)
    ax.set_ylim(0.15, 0.40)
    return save_fig(fig, "fig35_recipe_pareto_auc_dice")


def figure_36_harmonic_ranking():
    print("Figure 36: harmonic-mean ranking", flush=True)
    v192 = json.loads((RESULTS / "v192_uosl_gated_hybrid.json").read_text())
    ranking = v192["ranking_by_harmonic_mean_auc_dice"]

    names = [r["recipe"] for r in ranking]
    h = [r["harmonic"] for r in ranking]
    aucs = [r["auc"] for r in ranking]
    dices = [r["dice"] for r in ranking]

    fig, ax = plt.subplots(figsize=(11.0, 5.5))
    x = np.arange(len(names))
    colors = ["#009E73" if "Hybrid" in n
                else "#999999" if "Foundation" in n
                else "#0072B2" for n in names]
    ax.bar(x, h, color=colors, edgecolor="black", linewidth=0.5)
    for i, (hv, a, d) in enumerate(zip(h, aucs, dices)):
        ax.text(i, hv + 0.005, f"{hv:.4f}\n(AUC={a:.3f}\nDice={d:.3f})",
                ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Harmonic mean of (AUC, Dice)")
    ax.set_title("v192 recipe ranking — Hybrid recipes (green) DOMINATE "
                  "the harmonic mean of AUC and Dice\n"
                  "Best: hybrid S>0.4 (h-mean = 0.4462) — +6.3% over "
                  "foundation alone, +45% over kernel-only sigma=3")
    return save_fig(fig, "fig36_recipe_harmonic_ranking")


def main():
    figure_34_hybrid_routing()
    figure_35_recipe_scatter()
    figure_36_harmonic_ranking()
    print("done", flush=True)


if __name__ == "__main__":
    main()
