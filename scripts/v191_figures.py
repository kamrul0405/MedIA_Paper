"""v191 figures (Fig 32-33): multi-scale kernel — honest negative."""
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

COHORT_ORDER = ["Yale-Brain-Mets", "PROTEAS-brain-mets", "UCSF-POSTOP",
                 "RHUH-GBM", "LUMIERE", "UPENN-GBM", "MU-Glioma-Post"]
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


def figure_32_variant_ranking():
    print("Figure 32: variant ranking bar chart", flush=True)
    v191 = json.loads((RESULTS / "v191_multiscale_kernel.json").read_text())
    results = v191["results"]
    baselines = v191["baselines"]

    items = sorted(results.items(),
                    key=lambda kv: kv[1]["mean_auc_across_cohorts"])
    labels = [k for k, _ in items]
    values = [r["mean_auc_across_cohorts"] for _, r in items]

    # Add baselines
    labels_full = list(labels) + ["BASELINE: Foundation v184",
                                    "BASELINE: Kernel single σ=3 (v189)",
                                    "BASELINE: Per-cohort optimal (v189)"]
    values_full = list(values) + [
        baselines["foundation_v184_mean_auc"],
        baselines["kernel_single_sigma3_v189_mean_auc"],
        baselines["kernel_per_cohort_optimal_v189_mean_auc"],
    ]

    # Sort by value
    order = np.argsort(values_full)
    labels_full = [labels_full[i] for i in order]
    values_full = [values_full[i] for i in order]

    colors = []
    for lbl in labels_full:
        if "BASELINE: Per-cohort optimal" in lbl:
            colors.append("#009E73")  # green
        elif "BASELINE: Kernel single" in lbl:
            colors.append("#0072B2")  # blue (the winner)
        elif "BASELINE: Foundation" in lbl:
            colors.append("#999999")  # grey
        elif "single_3" in lbl:
            colors.append("#0072B2")  # blue (also single σ=3)
        elif "__max" in lbl:
            colors.append("#D55E00")  # vermillion
        else:
            colors.append("#CC79A7")  # purple (mean-pooled)

    fig, ax = plt.subplots(figsize=(11.0, 7.5))
    y = np.arange(len(labels_full))
    bars = ax.barh(y, values_full, color=colors, edgecolor="black",
                     linewidth=0.5)
    for i, v in enumerate(values_full):
        ax.text(v + 0.003, i, f"{v:.4f}",
                va="center", fontsize=8)
    ax.axvline(baselines["kernel_single_sigma3_v189_mean_auc"],
                 color="black", linestyle=":", alpha=0.7,
                 label=f"Single σ=3 baseline = "
                       f"{baselines['kernel_single_sigma3_v189_mean_auc']:.4f}")
    ax.set_yticks(y)
    ax.set_yticklabels(labels_full, fontsize=8)
    ax.set_xlabel("Mean AUC across 7 cohorts")
    ax.set_xlim(0.65, 0.82)
    ax.legend(loc="lower right", fontsize=9)
    ax.set_title("v191 multi-scale kernel ranking — single σ=3 BEATS all "
                  "10 multi-scale variants tested\n(blue = single σ=3 "
                  "winner; vermillion = max-pooled; purple = mean-pooled; "
                  "grey = foundation; green = oracle)")
    return save_fig(fig, "fig32_multiscale_variant_ranking")


def figure_33_per_cohort_compare():
    print("Figure 33: per-cohort comparison", flush=True)
    v191 = json.loads((RESULTS / "v191_multiscale_kernel.json").read_text())
    v189 = json.loads((RESULTS / "v189_training_free_kernel.json").read_text())

    results = v191["results"]
    # Pick best multi-scale variant by mean AUC
    best_multi_key = max([k for k in results if k != "single_3__max"
                           and k != "single_3__mean"],
                          key=lambda k: results[k]["mean_auc_across_cohorts"])
    fa = v189["foundation_auc_v184"]

    cohorts = COHORT_ORDER
    foundation = [fa[c] for c in cohorts]
    single_s3 = [v189["per_cohort"][c]["per_sigma"]["sigma=3.0"]["auc_mean"]
                  for c in cohorts]
    multi_best = [results[best_multi_key]["per_cohort"][c]["auc_mean"]
                   for c in cohorts]
    per_cohort_optimal = [v189["per_cohort"][c]["optimal_auc"]
                            for c in cohorts]

    x = np.arange(len(cohorts))
    width = 0.21
    fig, ax = plt.subplots(figsize=(13.0, 5.5))
    ax.bar(x - 1.5*width, foundation, width,
            label="Foundation model (v184)",
            color="#999999", edgecolor="black", linewidth=0.5)
    ax.bar(x - 0.5*width, single_s3, width,
            label=f"Single σ=3 universal (v189) = 0.7856",
            color="#0072B2", edgecolor="black", linewidth=0.5)
    ax.bar(x + 0.5*width, multi_best, width,
            label=f"Best multi-scale ({best_multi_key}) = "
                  f"{results[best_multi_key]['mean_auc_across_cohorts']:.4f}",
            color="#CC79A7", edgecolor="black", linewidth=0.5)
    ax.bar(x + 1.5*width, per_cohort_optimal, width,
            label="Per-cohort optimal (v189 oracle) = 0.8030",
            color="#009E73", edgecolor="black", linewidth=0.5)

    ax.axhline(0.5, color="grey", linestyle="--", alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("-", "\n") for c in cohorts], fontsize=8)
    ax.set_ylabel("Patient-level AUC")
    ax.set_title("v191 per-cohort: single σ=3 (blue) BEATS best multi-scale "
                  "(purple) on most cohorts\n"
                  "Multi-scale ensembling does NOT help beyond single σ=3")
    ax.set_ylim(0.4, 1.0)
    ax.legend(loc="lower right", fontsize=8)
    return save_fig(fig, "fig33_per_cohort_multiscale_compare")


def main():
    figure_32_variant_ranking()
    figure_33_per_cohort_compare()
    print("done", flush=True)


if __name__ == "__main__":
    main()
