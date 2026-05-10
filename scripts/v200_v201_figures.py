"""v200/v201 figures (Fig 54-55): λ vs molecular + survival U-Net failure."""
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


def figure_54_lambda_vs_molecular():
    print("Figure 54: lambda vs molecular subgroups", flush=True)
    v200 = json.loads((RESULTS / "v200_lambda_vs_molecular.json").read_text())
    sub_means = v200["subgroup_means"]
    sub_n = v200["subgroup_n"]

    fig, axes = plt.subplots(1, 3, figsize=(15.0, 5.0))

    # Panel A: IDH1
    idh1 = v200["test_1_idh1"]
    groups_idh = ["Wild-type", "Mutant"]
    means_idh = [idh1["mean_lambda_wt"], idh1["mean_lambda_mut"]]
    medians_idh = [idh1["median_lambda_wt"], idh1["median_lambda_mut"]]
    ns_idh = [idh1["n_wt"], idh1["n_mut"]]
    x = np.arange(len(groups_idh))
    width = 0.35
    axes[0].bar(x - width/2, means_idh, width, label="Mean",
                  color="#0072B2", edgecolor="black", linewidth=0.5)
    axes[0].bar(x + width/2, medians_idh, width, label="Median",
                  color="#D55E00", edgecolor="black", linewidth=0.5)
    for i, (m, md, n) in enumerate(zip(means_idh, medians_idh, ns_idh)):
        axes[0].text(i - width/2, m + 0.5, f"{m:.2f}", ha="center", fontsize=9)
        axes[0].text(i + width/2, md + 0.5, f"{md:.2f}", ha="center", fontsize=9)
        axes[0].text(i, -1.5, f"n={n}", ha="center", fontsize=8, color="grey")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(groups_idh)
    axes[0].set_ylabel("Per-patient λ (voxels)")
    axes[0].set_title(f"λ vs IDH1\nMann-Whitney p = {idh1['p_value_raw']:.3f}\n"
                        f"(Bonferroni p = "
                        f"{idh1['p_value_bonferroni']:.3f})")
    axes[0].legend(loc="upper right", fontsize=9)

    # Panel B: MGMT
    mgmt = v200["test_2_mgmt"]
    groups_mgmt = ["Unmethylated", "Methylated"]
    means_mgmt = [mgmt["mean_lambda_unmethylated"],
                    mgmt["mean_lambda_methylated"]]
    medians_mgmt = [mgmt["median_lambda_unmethylated"],
                      mgmt["median_lambda_methylated"]]
    ns_mgmt = [mgmt["n_unmethylated"], mgmt["n_methylated"]]
    axes[1].bar(x - width/2, means_mgmt, width, label="Mean",
                  color="#0072B2", edgecolor="black", linewidth=0.5)
    axes[1].bar(x + width/2, medians_mgmt, width, label="Median",
                  color="#D55E00", edgecolor="black", linewidth=0.5)
    for i, (m, md, n) in enumerate(zip(means_mgmt, medians_mgmt, ns_mgmt)):
        axes[1].text(i - width/2, m + 0.5, f"{m:.2f}", ha="center", fontsize=9)
        axes[1].text(i + width/2, md + 0.5, f"{md:.2f}", ha="center", fontsize=9)
        axes[1].text(i, -1.5, f"n={n}", ha="center", fontsize=8, color="grey")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(groups_mgmt)
    axes[1].set_ylabel("Per-patient λ (voxels)")
    axes[1].set_title(f"λ vs MGMT methylation\n"
                        f"Mann-Whitney p = {mgmt['p_value_raw']:.3f}\n"
                        f"(Bonferroni p = "
                        f"{mgmt['p_value_bonferroni']:.3f})")
    axes[1].legend(loc="upper right", fontsize=9)

    # Panel C: cross-tab
    keys_order = ["IDH=0_MGMT=0", "IDH=0_MGMT=1",
                    "IDH=1_MGMT=0", "IDH=1_MGMT=1"]
    labels_order = ["IDH-WT\nMGMT-unmeth\n(worst prog)",
                      "IDH-WT\nMGMT-meth", "IDH-mut\nMGMT-unmeth",
                      "IDH-mut\nMGMT-meth\n(best prog)"]
    means_x = [sub_means[k] for k in keys_order]
    ns_x = [sub_n[k] for k in keys_order]
    colors = ["#D55E00", "#E69F00", "#56B4E9", "#009E73"]
    bars = axes[2].bar(range(len(keys_order)), means_x, color=colors,
                          edgecolor="black", linewidth=0.5)
    for i, (m, n) in enumerate(zip(means_x, ns_x)):
        axes[2].text(i, m + 0.5, f"{m:.2f}", ha="center", fontsize=10,
                       fontweight="bold")
        axes[2].text(i, -1.5, f"n={n}", ha="center", fontsize=8,
                       color="grey")
    axes[2].set_xticks(range(len(keys_order)))
    axes[2].set_xticklabels(labels_order, fontsize=8)
    axes[2].set_ylabel("Per-patient λ (voxels)")
    axes[2].set_title("λ by (IDH × MGMT) subgroup\n"
                        "Worse prognosis → larger λ\n(direction matches "
                        "biology; not significant after Bonf)")

    fig.suptitle("v200 HONEST TRENDING: λ trends with worse molecular "
                  "prognosis (mean WT 12.7 vs mut 3.9 = 3× difference)\n"
                  "but neither IDH nor MGMT reaches Bonferroni "
                  "significance — biological direction confirmed, "
                  "statistical power insufficient",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig54_lambda_vs_molecular_subgroups")


def figure_55_survival_unet_failure():
    print("Figure 55: survival U-Net cross-cohort failure", flush=True)
    v201 = json.loads((RESULTS / "v201_survival_foundation.json").read_text())
    res = v201["results"]
    refs = v201["references"]

    setups = [
        ("v201 Train MU\n→ Test RHUH\n(GPU survival U-Net)",
         res["train_MU_test_RHUH"]["c_index_test"], "#D55E00"),
        ("v201 Train RHUH\n→ Test MU\n(GPU survival U-Net)",
         res["train_RHUH_test_MU"]["c_index_test"], "#D55E00"),
        ("v201 Train RHUH\n→ Test RHUH\n(overfit reference)",
         res["train_RHUH_test_RHUH"]["c_index_test"], "#999999"),
        ("Round 33 RHUH\nclinical-only Cox\n(reference)",
         refs["round_33_RHUH_clinical_C"], "#0072B2"),
        ("Round 36 MU\nclinical-only Cox\n(reference)",
         refs["round_36_MU_clinical_C"], "#0072B2"),
    ]

    fig, ax = plt.subplots(figsize=(12.0, 6.0))
    x = np.arange(len(setups))
    labels = [s[0] for s in setups]
    cs = [s[1] for s in setups]
    colors = [s[2] for s in setups]
    bars = ax.bar(x, cs, color=colors, edgecolor="black", linewidth=0.5)
    for i, c in enumerate(cs):
        ax.text(i, c + 0.01, f"{c:.4f}", ha="center", fontsize=11,
                fontweight="bold")
    ax.axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                 label="C = 0.5 (chance)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Harrell's C-index")
    ax.set_title("v201 HONEST NEGATIVE: survival-supervised 3D U-Net FAILS "
                  "to cross-cohort generalize\n"
                  "Cross-cohort C ~ 0.45-0.49 (chance); within-training C "
                  "= 0.70 (overfit)\n"
                  "Simple clinical Cox (C ~ 0.60-0.67) BEATS deep learning "
                  "for survival prediction")
    ax.set_ylim(0.4, 0.75)
    ax.legend(loc="lower right", fontsize=10)
    return save_fig(fig, "fig55_survival_unet_cross_cohort_failure")


def main():
    figure_54_lambda_vs_molecular()
    figure_55_survival_unet_failure()
    print("done", flush=True)


if __name__ == "__main__":
    main()
