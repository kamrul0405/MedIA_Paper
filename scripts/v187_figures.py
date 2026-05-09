"""v187 audit figures (Fig 20-22) — round 25."""
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


def figure_20_bimodal_ablation():
    print("Figure 20: bimodal-kernel ablation", flush=True)
    v187 = json.loads((RESULTS / "v187_core_claims_audit.json").read_text())
    a1 = v187["audits"]["audit_1_bimodal_ablation"]

    variants = ["A_full_bimodal", "B_persistence_only", "C_gaussian_only"]
    labels = ["Full bimodal\nmax(M, G_sigma*M)",
              "Persistence-only\n(M, M)",
              "Gaussian-only\n(M, G_sigma*M)"]
    metrics = ["ensemble_outgrowth_coverage_mean", "auc_mean", "dice_mean"]
    metric_labels = ["Outgrowth coverage (%)", "AUC", "Dice"]
    cohorts = ["upenn", "yale"]

    fig, axes = plt.subplots(2, 3, figsize=(13.0, 7.5))
    for col, (m, ml) in enumerate(zip(metrics, metric_labels)):
        for row, c in enumerate(cohorts):
            ax = axes[row, col]
            vals = [a1[v][c][m] for v in variants]
            if m == "ensemble_outgrowth_coverage_mean":
                vals = [v * 100 for v in vals]
            colors = ["#0072B2", "#E69F00", "#009E73"]
            bars = ax.bar(range(len(variants)), vals, color=colors,
                            edgecolor="black", linewidth=0.5)
            for i, v in enumerate(vals):
                ax.text(i, v * 1.02 if v > 0.1 else v + 0.01,
                        f"{v:.3f}" if m != "ensemble_outgrowth_coverage_mean"
                        else f"{v:.2f}",
                        ha="center", fontsize=8)
            ax.set_xticks(range(len(variants)))
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_ylabel(ml)
            ax.set_title(f"{c.upper()} — {ml}")
            if m == "auc_mean":
                ax.axhline(0.5, color="grey", linestyle="--", alpha=0.6,
                            label="Chance")
                ax.legend(loc="lower right", fontsize=7)
                ax.set_ylim(0, 1.0)

    fig.suptitle("v187 AUDIT 1 — Bimodal-kernel ablation: full bimodal "
                  "outperforms single-mode by 3-4 pp on coverage,\n"
                  "but AUC/Dice differences are small (~0.02)",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig20_bimodal_ablation")


def figure_21_sigma_sweep():
    print("Figure 21: sigma sensitivity sweep", flush=True)
    v187 = json.loads((RESULTS / "v187_core_claims_audit.json").read_text())
    a2 = v187["audits"]["audit_2_sigma_sensitivity"]

    sigmas = sorted([float(k.split("=")[1]) for k in a2.keys()])
    upenn_cov = [a2[f"sigma={s}"]["upenn"]["ensemble_outgrowth_coverage_mean"] * 100
                  for s in sigmas]
    yale_cov = [a2[f"sigma={s}"]["yale"]["ensemble_outgrowth_coverage_mean"] * 100
                  for s in sigmas]
    upenn_dice = [a2[f"sigma={s}"]["upenn"]["dice_mean"] for s in sigmas]
    yale_dice = [a2[f"sigma={s}"]["yale"]["dice_mean"] for s in sigmas]
    upenn_auc = [a2[f"sigma={s}"]["upenn"]["auc_mean"] for s in sigmas]
    yale_auc = [a2[f"sigma={s}"]["yale"]["auc_mean"] for s in sigmas]

    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.5))

    axes[0].plot(sigmas, upenn_cov, "o-", color="#56B4E9",
                  linewidth=2, markersize=9, label="UPENN-GBM")
    axes[0].plot(sigmas, yale_cov, "o-", color="#000000",
                  linewidth=2, markersize=9, label="Yale-Brain-Mets")
    for s, u, y in zip(sigmas, upenn_cov, yale_cov):
        axes[0].text(s, u + 1.5, f"{u:.1f}", ha="center", fontsize=8,
                      color="#56B4E9")
        axes[0].text(s, y + 1.5, f"{y:.1f}", ha="center", fontsize=8,
                      color="#000000")
    axes[0].set_xlabel("sigma (Gaussian smoothing scale, voxels)")
    axes[0].set_ylabel("Ensemble outgrowth coverage (%)")
    axes[0].set_title("Coverage")
    axes[0].set_ylim(20, 105)
    axes[0].legend(loc="lower right", fontsize=9)
    axes[0].axvline(7, color="grey", linestyle=":", alpha=0.5,
                     label="Round-1 default")

    axes[1].plot(sigmas, upenn_auc, "o-", color="#56B4E9",
                  linewidth=2, markersize=9, label="UPENN-GBM")
    axes[1].plot(sigmas, yale_auc, "o-", color="#000000",
                  linewidth=2, markersize=9, label="Yale-Brain-Mets")
    axes[1].axhline(0.5, color="grey", linestyle="--", alpha=0.6,
                     label="Chance")
    axes[1].set_xlabel("sigma")
    axes[1].set_ylabel("Patient-level AUC")
    axes[1].set_title("AUC")
    axes[1].legend(loc="lower right", fontsize=8)
    axes[1].set_ylim(0.4, 1.0)
    axes[1].axvline(7, color="grey", linestyle=":", alpha=0.5)

    axes[2].plot(sigmas, upenn_dice, "o-", color="#56B4E9",
                  linewidth=2, markersize=9, label="UPENN-GBM")
    axes[2].plot(sigmas, yale_dice, "o-", color="#000000",
                  linewidth=2, markersize=9, label="Yale-Brain-Mets")
    axes[2].set_xlabel("sigma")
    axes[2].set_ylabel("Dice")
    axes[2].set_title("Dice")
    axes[2].set_ylim(0, max(max(upenn_dice), max(yale_dice)) * 1.15)
    axes[2].legend(loc="upper right", fontsize=9)
    axes[2].axvline(7, color="grey", linestyle=":", alpha=0.5)

    fig.suptitle("v187 AUDIT 2 — Sigma sensitivity (HONEST FINDING): "
                  "round-1 default sigma=7 is NOT optimal\n"
                  "Larger sigma -> higher coverage; smaller sigma -> "
                  "higher Dice (precision)",
                  fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig21_sigma_sensitivity")


def figure_22_foundation_value():
    print("Figure 22: does foundation model add value over kernel alone?",
          flush=True)
    v187 = json.loads((RESULTS / "v187_core_claims_audit.json").read_text())
    a3 = v187["audits"]["audit_3_foundation_adds_value"]

    cohorts = ["UPENN-GBM", "Yale-Brain-Mets"]
    keys = ["upenn", "yale"]
    kernel_only = [a3[k]["kernel_only_pct"] for k in keys]
    ensemble = [a3[k]["ensemble_pct"] for k in keys]
    delta = [a3[k]["delta_pp"] for k in keys]

    x = np.arange(len(cohorts))
    width = 0.35

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.0))

    axes[0].bar(x - width/2, kernel_only, width, label="Bimodal kernel ALONE\n(no learning)",
                  color="#999999", edgecolor="black", linewidth=0.5)
    axes[0].bar(x + width/2, ensemble, width, label="Foundation model + kernel\n(ensemble)",
                  color="#0072B2", edgecolor="black", linewidth=0.5)
    for i, (ko, en) in enumerate(zip(kernel_only, ensemble)):
        axes[0].text(i - width/2, ko + 1, f"{ko:.1f}%", ha="center", fontsize=9)
        axes[0].text(i + width/2, en + 1, f"{en:.1f}%", ha="center", fontsize=9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(cohorts)
    axes[0].set_ylabel("Outgrowth coverage (%)")
    axes[0].set_title("Foundation adds value? Kernel alone vs ensemble")
    axes[0].set_ylim(0, max(ensemble) * 1.15)
    axes[0].legend(loc="lower right", fontsize=9)

    colors = ["#009E73" if d > 0 else "#D55E00" for d in delta]
    axes[1].bar(x, delta, color=colors, edgecolor="black", linewidth=0.5)
    for i, d in enumerate(delta):
        axes[1].text(i, d + 1 if d >= 0 else d - 2,
                      f"{d:+.2f} pp", ha="center", fontsize=10,
                      fontweight="bold",
                      color="#009E73" if d > 0 else "#D55E00")
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(cohorts)
    axes[1].set_ylabel("delta = ensemble - kernel-only (pp)")
    axes[1].set_title("Foundation-model value-add (pp)")
    axes[1].set_ylim(min(delta) - 5, max(delta) + 8)

    fig.suptitle("v187 AUDIT 3 (CRITICAL HONEST FINDING): foundation model "
                  "adds 34.95 pp on UPENN (in-distribution)\nbut "
                  "0.00 pp on Yale (out-of-distribution) — learned 3D U-Net "
                  "contributes nothing beyond bimodal kernel on Yale",
                  fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig22_foundation_value_added")


def main():
    figure_20_bimodal_ablation()
    figure_21_sigma_sweep()
    figure_22_foundation_value()
    print("done", flush=True)


if __name__ == "__main__":
    main()
