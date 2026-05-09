"""v188 figures (Fig 23-25): interpretability + adversarial robustness."""
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


def figure_23_residual_analysis():
    print("Figure 23: residual analysis", flush=True)
    csv_path = RESULTS / "v188_residual_per_patient.csv"
    by_cohort = {"UPENN-GBM": [], "Yale-Brain-Mets": []}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = row["cohort"]
            if c not in by_cohort:
                continue
            by_cohort[c].append({
                "mean_R": float(row["mean_R_outside_mask"]),
                "std_R": float(row["std_R"]),
                "sparsity": float(row["sparsity_pct"]),
                "corr_dist": (float(row["corr_abs_R_distance_from_boundary"])
                              if row["corr_abs_R_distance_from_boundary"]
                              not in ("", "nan") else float("nan")),
                "separation": (float(row["R_separation_outgrowth_vs_non"])
                                 if row["R_separation_outgrowth_vs_non"]
                                 not in ("", "nan") else float("nan")),
            })

    cohorts = list(by_cohort.keys())
    metrics = [
        ("mean_R", "Mean residual R = F - K\n(outside baseline mask)"),
        ("std_R", "Std of residual R"),
        ("sparsity", "Sparsity (% near-zero R) (%)"),
        ("corr_dist", "Corr(|R|, distance from boundary)"),
        ("separation", "R(outgrowth) - R(non-outgrowth)\n(positive = discriminative)"),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(20.0, 4.5))
    colors = {"UPENN-GBM": "#56B4E9", "Yale-Brain-Mets": "#000000"}

    for col, (key, label) in enumerate(metrics):
        ax = axes[col]
        for i, c in enumerate(cohorts):
            vals = [r[key] for r in by_cohort[c]
                     if not np.isnan(r[key])]
            if not vals:
                continue
            x_jit = np.random.default_rng(0).uniform(
                -0.05, 0.05, size=len(vals)) + i
            ax.scatter(x_jit, vals, alpha=0.55, s=36, color=colors[c],
                        edgecolor="black", linewidth=0.4)
            ax.plot([i - 0.25, i + 0.25],
                    [np.mean(vals), np.mean(vals)],
                    color="red", linewidth=2.5, zorder=10)
            ax.text(i, max(vals) + (max(vals) - min(vals)) * 0.05,
                    f"mean = {np.mean(vals):.3f}",
                    ha="center", fontsize=8)
        ax.axhline(0, color="grey", linestyle="--", alpha=0.6)
        ax.set_xticks(range(len(cohorts)))
        ax.set_xticklabels([c.replace("-", "\n") for c in cohorts],
                           fontsize=9)
        ax.set_title(label, fontsize=10)

    fig.suptitle("v188 Mechanistic interpretability: residual R = F(x) - K(x)\n"
                 "UPENN: dense, +0.33, NON-discriminative (sep~0).  "
                 "Yale: sparse, -0.26, ANTI-discriminative (sep=-0.35).",
                 fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig23_foundation_residual_analysis")


def figure_24_adversarial_robustness():
    print("Figure 24: adversarial robustness", flush=True)
    v188 = json.loads((RESULTS / "v188_interpretability_robustness.json")
                      .read_text())
    pert = v188["robustness"]["results_by_perturbation"]
    perturbations = ["baseline", "erode_1", "erode_2", "dilate_1",
                      "dilate_2", "flip_1pct"]
    upenn_aucs = [pert[k]["upenn"]["auc_mean"] for k in perturbations]
    yale_aucs = [pert[k]["yale"]["auc_mean"] for k in perturbations]
    upenn_dice = [pert[k]["upenn"]["dice_mean"] for k in perturbations]
    yale_dice = [pert[k]["yale"]["dice_mean"] for k in perturbations]
    upenn_cov = [pert[k]["upenn"]["ensemble_outgrowth_coverage_mean"] * 100
                  for k in perturbations]
    yale_cov = [pert[k]["yale"]["ensemble_outgrowth_coverage_mean"] * 100
                  for k in perturbations]

    x = np.arange(len(perturbations))
    width = 0.35

    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.5))

    axes[0].bar(x - width/2, upenn_aucs, width, label="UPENN-GBM",
                 color="#56B4E9", edgecolor="black", linewidth=0.5)
    axes[0].bar(x + width/2, yale_aucs, width, label="Yale-Brain-Mets",
                 color="#000000", edgecolor="black", linewidth=0.5)
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.6,
                    label="Chance")
    for i, (u, y) in enumerate(zip(upenn_aucs, yale_aucs)):
        axes[0].text(i - width/2, u + 0.01, f"{u:.3f}", ha="center", fontsize=7)
        axes[0].text(i + width/2, y + 0.01, f"{y:.3f}", ha="center", fontsize=7)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(perturbations, rotation=20, ha="right",
                              fontsize=9)
    axes[0].set_ylabel("Patient-level AUC")
    axes[0].set_title("AUC under perturbation")
    axes[0].legend(loc="lower right", fontsize=9)
    axes[0].set_ylim(0, 1.0)

    axes[1].bar(x - width/2, upenn_dice, width, label="UPENN-GBM",
                 color="#56B4E9", edgecolor="black", linewidth=0.5)
    axes[1].bar(x + width/2, yale_dice, width, label="Yale-Brain-Mets",
                 color="#000000", edgecolor="black", linewidth=0.5)
    for i, (u, y) in enumerate(zip(upenn_dice, yale_dice)):
        axes[1].text(i - width/2, u + 0.01, f"{u:.3f}", ha="center", fontsize=7)
        axes[1].text(i + width/2, y + 0.01, f"{y:.3f}", ha="center", fontsize=7)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(perturbations, rotation=20, ha="right",
                              fontsize=9)
    axes[1].set_ylabel("Dice")
    axes[1].set_title("Dice under perturbation")
    axes[1].legend(loc="upper right", fontsize=9)

    axes[2].bar(x - width/2, upenn_cov, width, label="UPENN-GBM",
                 color="#56B4E9", edgecolor="black", linewidth=0.5)
    axes[2].bar(x + width/2, yale_cov, width, label="Yale-Brain-Mets",
                 color="#000000", edgecolor="black", linewidth=0.5)
    for i, (u, y) in enumerate(zip(upenn_cov, yale_cov)):
        axes[2].text(i - width/2, u + 1, f"{u:.1f}", ha="center", fontsize=7)
        axes[2].text(i + width/2, y + 1, f"{y:.1f}", ha="center", fontsize=7)
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(perturbations, rotation=20, ha="right",
                              fontsize=9)
    axes[2].set_ylabel("Outgrowth coverage (%)")
    axes[2].set_title("Coverage under perturbation")
    axes[2].legend(loc="lower right", fontsize=9)

    fig.suptitle("v188 Adversarial robustness: 5 mask perturbations on "
                  "UPENN + Yale\nAUC max dAUC = 0.016 (HIGHLY ROBUST). "
                  "Coverage drops with erosion (smaller mask).",
                  fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig24_adversarial_robustness")


def figure_25_dauc_summary():
    print("Figure 25: dAUC summary", flush=True)
    v188 = json.loads((RESULTS / "v188_interpretability_robustness.json")
                      .read_text())
    delta = v188["robustness"]["delta_auc_vs_baseline"]
    keys = list(delta.keys())
    upenn_d = [delta[k]["upenn_delta_auc"] for k in keys]
    yale_d = [delta[k]["yale_delta_auc"] for k in keys]

    x = np.arange(len(keys))
    width = 0.35

    fig, ax = plt.subplots(figsize=(11.0, 5.0))
    upenn_colors = ["#009E73" if d >= 0 else "#D55E00" for d in upenn_d]
    yale_colors = ["#56B4E9" if d >= 0 else "#CC79A7" for d in yale_d]
    ax.bar(x - width/2, upenn_d, width, label="UPENN-GBM",
            color=upenn_colors, edgecolor="black", linewidth=0.5)
    ax.bar(x + width/2, yale_d, width, label="Yale-Brain-Mets",
            color=yale_colors, edgecolor="black", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=1)
    ax.axhspan(-0.05, 0.05, alpha=0.1, color="grey",
                label="+/- 0.05 AUC robustness threshold")

    for i, (u, y) in enumerate(zip(upenn_d, yale_d)):
        ax.text(i - width/2, u + (0.002 if u >= 0 else -0.005),
                f"{u:+.4f}", ha="center", fontsize=8)
        ax.text(i + width/2, y + (0.002 if y >= 0 else -0.005),
                f"{y:+.4f}", ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(keys, rotation=15, ha="right")
    ax.set_ylabel("dAUC vs baseline")
    ax.set_title("v188 dAUC under 5 perturbations: max |dAUC| = 0.016 — "
                  "FOUNDATION MODEL ROBUST to clinical mask noise")
    ax.legend(loc="upper right", fontsize=9)
    return save_fig(fig, "fig25_dauc_robustness_summary")


def main():
    figure_23_residual_analysis()
    figure_24_adversarial_robustness()
    figure_25_dauc_summary()
    print("done", flush=True)


if __name__ == "__main__":
    main()
