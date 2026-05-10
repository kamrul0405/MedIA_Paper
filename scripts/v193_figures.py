"""v193 figures (Fig 37-38): multi-seed hybrid recipe bootstrap."""
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


def figure_37_per_seed_metrics():
    print("Figure 37: per-seed UPENN + Yale metrics", flush=True)
    v193 = json.loads((RESULTS / "v193_hybrid_multiseed.json").read_text())
    by_seed = v193["by_seed"]
    summary = v193["summary_across_seeds"]
    seeds = list(by_seed.keys())

    upenn_auc = [by_seed[s]["UPENN-GBM"]["auc_mean"] for s in seeds]
    upenn_dice = [by_seed[s]["UPENN-GBM"]["dice_mean"] for s in seeds]
    yale_auc = [by_seed[s]["Yale-Brain-Mets"]["auc_mean"] for s in seeds]
    yale_dice = [by_seed[s]["Yale-Brain-Mets"]["dice_mean"] for s in seeds]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.5))

    x = np.arange(len(seeds))
    width = 0.4

    axes[0].bar(x - width/2, upenn_auc, width,
                  label="UPENN-GBM (foundation+kernel)",
                  color="#56B4E9", edgecolor="black", linewidth=0.5)
    axes[0].bar(x + width/2, yale_auc, width,
                  label="Yale-Brain-Mets (kernel-only σ=3)",
                  color="#000000", edgecolor="black", linewidth=0.5)
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.5,
                      label="Chance")
    axes[0].axhline(summary["UPENN-GBM"]["auc_mean"], color="#56B4E9",
                      linestyle=":", alpha=0.6,
                      label=f"UPENN mean = {summary['UPENN-GBM']['auc_mean']:.4f} "
                            f"+/- {summary['UPENN-GBM']['auc_se']:.4f}")
    axes[0].axhline(summary["Yale-Brain-Mets"]["auc_mean"],
                      color="#000000", linestyle=":", alpha=0.6,
                      label=f"Yale mean = {summary['Yale-Brain-Mets']['auc_mean']:.4f} "
                            f"+/- {summary['Yale-Brain-Mets']['auc_se']:.4f}")
    for i, (u, y) in enumerate(zip(upenn_auc, yale_auc)):
        axes[0].text(i - width/2, u + 0.01, f"{u:.4f}",
                       ha="center", fontsize=8)
        axes[0].text(i + width/2, y + 0.01, f"{y:.4f}",
                       ha="center", fontsize=8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f"Seed {s}" for s in seeds])
    axes[0].set_ylabel("Patient-level AUC")
    axes[0].set_title("Per-seed AUC (multi-seed hybrid recipe)")
    axes[0].set_ylim(0.4, 1.0)
    axes[0].legend(loc="lower right", fontsize=8)

    axes[1].bar(x - width/2, upenn_dice, width,
                  label="UPENN-GBM (foundation+kernel)",
                  color="#56B4E9", edgecolor="black", linewidth=0.5)
    axes[1].bar(x + width/2, yale_dice, width,
                  label="Yale-Brain-Mets (kernel-only σ=3)",
                  color="#000000", edgecolor="black", linewidth=0.5)
    for i, (u, y) in enumerate(zip(upenn_dice, yale_dice)):
        axes[1].text(i - width/2, u + 0.01, f"{u:.4f}",
                       ha="center", fontsize=8)
        axes[1].text(i + width/2, y + 0.01, f"{y:.4f}",
                       ha="center", fontsize=8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"Seed {s}" for s in seeds])
    axes[1].set_ylabel("Dice")
    axes[1].set_title("Per-seed Dice (multi-seed hybrid recipe)")
    axes[1].legend(loc="upper right", fontsize=8)

    fig.suptitle("v193: Multi-seed hybrid recipe BULLETPROOFED — UPENN AUC "
                  "0.6457 +/- 0.0056, Dice 0.7058 +/- 0.0045\n"
                  "Yale (kernel route) is DETERMINISTIC: AUC 0.8913 across "
                  "all seeds (no training dependency)",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig37_hybrid_multiseed_perseed")


def figure_38_recipe_with_CIs():
    print("Figure 38: hybrid recipe with multi-seed CIs", flush=True)
    v193 = json.loads((RESULTS / "v193_hybrid_multiseed.json").read_text())
    summary = v193["summary_across_seeds"]

    cohorts = ["UPENN-GBM", "Yale-Brain-Mets"]
    recipes = [summary[c]["recipe"] for c in cohorts]
    auc_m = [summary[c]["auc_mean"] for c in cohorts]
    auc_se = [summary[c]["auc_se"] for c in cohorts]
    dice_m = [summary[c]["dice_mean"] for c in cohorts]
    dice_se = [summary[c]["dice_se"] for c in cohorts]
    cov_m = [summary[c]["coverage_mean"] * 100 for c in cohorts]
    cov_se = [summary[c]["coverage_se"] * 100 for c in cohorts]
    n = [summary[c]["n_patients"] for c in cohorts]

    fig, axes = plt.subplots(1, 3, figsize=(15.0, 5.0))

    x = np.arange(len(cohorts))
    colors = ["#009E73" if "foundation" in r else "#D55E00"
                for r in recipes]

    axes[0].bar(x, auc_m, yerr=auc_se, color=colors,
                  edgecolor="black", linewidth=0.5,
                  error_kw={"capsize": 5, "linewidth": 1.5})
    for i, (m, s) in enumerate(zip(auc_m, auc_se)):
        axes[0].text(i, m + s + 0.02, f"{m:.4f}\n+/- {s:.4f}",
                       ha="center", fontsize=9)
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.5)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([f"{c}\n({recipes[i]})\nn={n[i]}"
                                for i, c in enumerate(cohorts)],
                              fontsize=8)
    axes[0].set_ylabel("Patient-level AUC")
    axes[0].set_title("AUC with multi-seed SE")
    axes[0].set_ylim(0, 1.0)

    axes[1].bar(x, dice_m, yerr=dice_se, color=colors,
                  edgecolor="black", linewidth=0.5,
                  error_kw={"capsize": 5, "linewidth": 1.5})
    for i, (m, s) in enumerate(zip(dice_m, dice_se)):
        axes[1].text(i, m + s + 0.02, f"{m:.4f}\n+/- {s:.4f}",
                       ha="center", fontsize=9)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"{c}\n({recipes[i]})\nn={n[i]}"
                                for i, c in enumerate(cohorts)],
                              fontsize=8)
    axes[1].set_ylabel("Dice")
    axes[1].set_title("Dice with multi-seed SE")

    axes[2].bar(x, cov_m, yerr=cov_se, color=colors,
                  edgecolor="black", linewidth=0.5,
                  error_kw={"capsize": 5, "linewidth": 1.5})
    for i, (m, s) in enumerate(zip(cov_m, cov_se)):
        axes[2].text(i, m + s + 2, f"{m:.2f}%\n+/- {s:.2f}%",
                       ha="center", fontsize=9)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([f"{c}\n({recipes[i]})\nn={n[i]}"
                                for i, c in enumerate(cohorts)],
                              fontsize=8)
    axes[2].set_ylabel("Coverage (%)")
    axes[2].set_title("Coverage with multi-seed SE")
    axes[2].set_ylim(0, 105)

    fig.suptitle("v193 final hybrid recipe deployment metrics with "
                  "multi-seed (3-seed) CIs\n"
                  "Foundation route (green) is bulletproofed; kernel route "
                  "(orange) is deterministic",
                  fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig38_hybrid_multiseed_summary")


def main():
    figure_37_per_seed_metrics()
    figure_38_recipe_with_CIs()
    print("done", flush=True)


if __name__ == "__main__":
    main()
