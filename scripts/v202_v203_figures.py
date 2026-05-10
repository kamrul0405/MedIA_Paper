"""v202/v203 figures (Fig 56-57): PFS binary screening + multi-task survival."""
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
        d.mkdir(parents=True, exist_ok=True)
        p_png = d / f"{name}.png"
        p_pdf = d / f"{name}.pdf"
        fig.savefig(p_png, dpi=300)
        fig.savefig(p_pdf)
        paths.append(str(p_png))
    plt.close(fig)
    return paths


def figure_56_pfs_binary_screening():
    print("Figure 56: PFS binary screening", flush=True)
    v202 = json.loads((RESULTS / "v202_pfs_binary_screening.json").read_text())
    h = v202["horizon_results"]
    h180 = h["180"]
    h365 = h["365"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.0))

    # Panel A: univariate AUCs at 180 days
    feats = ["v_kernel_s3", "baseline_volume", "age", "idh1", "mgmt", "lambda"]
    nice = ["V_kernel\n(σ=3)", "baseline\nvolume", "age", "IDH1",
            "MGMT", "λ"]
    aucs180 = [h180["univariate_AUCs"][f]["AUC"] for f in feats]
    aucs365 = [h365["univariate_AUCs"][f]["AUC"] for f in feats]
    colors = ["#D55E00", "#0072B2", "#56B4E9", "#009E73", "#CC79A7", "#F0E442"]

    x = np.arange(len(feats))
    width = 0.4
    axes[0].bar(x - width/2, aucs180, width, label="180-day horizon",
                color="#0072B2", edgecolor="black", linewidth=0.5)
    axes[0].bar(x + width/2, aucs365, width, label="365-day horizon",
                color="#D55E00", edgecolor="black", linewidth=0.5)
    for i, (a180, a365) in enumerate(zip(aucs180, aucs365)):
        axes[0].text(i - width/2, a180 + 0.01, f"{a180:.3f}",
                     ha="center", fontsize=8)
        axes[0].text(i + width/2, a365 + 0.01, f"{a365:.3f}",
                     ha="center", fontsize=8)
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                    label="chance")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(nice, fontsize=9)
    axes[0].set_ylabel("Univariate AUC")
    axes[0].set_title("A. Univariate AUC by feature\n"
                      "V_kernel WINS at 365-day PFS (AUC=0.692)")
    axes[0].set_ylim(0.45, 0.78)
    axes[0].legend(loc="upper right", fontsize=8)

    # Panel B: multivariate clinical vs clinical+V_kernel
    horizons = ["180-day PFS", "365-day PFS"]
    auc_clin = [h180["multivariate"]["auc_clinical_only"],
                h365["multivariate"]["auc_clinical_only"]]
    auc_full = [h180["multivariate"]["auc_clinical_plus_Vkernel"],
                h365["multivariate"]["auc_clinical_plus_Vkernel"]]
    deltas = [h180["multivariate"]["delta_AUC"],
              h365["multivariate"]["delta_AUC"]]
    x = np.arange(len(horizons))
    width = 0.35
    bars1 = axes[1].bar(x - width/2, auc_clin, width,
                        label="Clinical only\n(age + IDH + MGMT)",
                        color="#0072B2", edgecolor="black", linewidth=0.5)
    bars2 = axes[1].bar(x + width/2, auc_full, width,
                        label="Clinical + V_kernel",
                        color="#D55E00", edgecolor="black", linewidth=0.5)
    for i, (a, b, d) in enumerate(zip(auc_clin, auc_full, deltas)):
        axes[1].text(i - width/2, a + 0.005, f"{a:.4f}", ha="center",
                     fontsize=10)
        axes[1].text(i + width/2, b + 0.005, f"{b:.4f}", ha="center",
                     fontsize=10, fontweight="bold")
        axes[1].text(i, max(a, b) + 0.05, f"Δ = +{d:.3f}",
                     ha="center", fontsize=11, fontweight="bold",
                     color="#D55E00",
                     bbox=dict(boxstyle="round,pad=0.3", fc="white",
                               ec="#D55E00"))
    axes[1].axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                    label="chance")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(horizons)
    axes[1].set_ylabel("Multivariate logistic AUC")
    axes[1].set_title("B. V_kernel adds incremental signal\n"
                      "+10.8 pp AUC at 365-day horizon")
    axes[1].set_ylim(0.45, 0.85)
    axes[1].legend(loc="upper left", fontsize=8)

    # Panel C: rescue narrative
    metrics = ["Round 32 Cox\nHR p-value\n(continuous PFS)",
               "Round 27 binary\nresidual AUC\n(within-cohort)",
               "Round 39 binary\n365-d PFS\n+V_kernel AUC"]
    values = [0.92, 0.736, h365["multivariate"]["auc_clinical_plus_Vkernel"]]
    colors_panel = ["#D55E00", "#0072B2", "#009E73"]
    interpret = ["FAIL\n(p>>0.05)", "STRONG\n(AUC>0.7)", "RESCUE\n(+10.8 pp)"]

    bars = axes[2].bar(range(len(metrics)), values, color=colors_panel,
                       edgecolor="black", linewidth=0.5)
    for i, (v, txt) in enumerate(zip(values, interpret)):
        axes[2].text(i, v + 0.02, f"{v:.3f}", ha="center", fontsize=11,
                     fontweight="bold")
        axes[2].text(i, v / 2, txt, ha="center", fontsize=10,
                     fontweight="bold", color="white")
    axes[2].set_xticks(range(len(metrics)))
    axes[2].set_xticklabels(metrics, fontsize=8)
    axes[2].set_ylabel("Value")
    axes[2].set_title("C. METRIC MISMATCH RESOLVED\n"
                      "Kernel = good binary screen, bad continuous regressor")
    axes[2].set_ylim(0, 1.0)

    fig.suptitle("v202 PARADIGM RESCUE: V_kernel reframed as 365-day PFS "
                 "binary screen RECOVERS clinical utility (+10.8 pp AUC over "
                 "age+IDH+MGMT)\n"
                 "Resolves metric-mismatch hypothesis: kernel encodes "
                 "RANK-correct early-progression risk but FAILS continuous "
                 "Cox HR estimation",
                 fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig56_v202_pfs_binary_screening")


def figure_57_multitask_foundation():
    print("Figure 57: multi-task foundation comparison", flush=True)
    v203 = json.loads((RESULTS / "v203_multitask_foundation.json").read_text())
    refs = v203["references"]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.5))

    # Panel A: cross-cohort C-index comparison
    setups = [
        ("Clinical Cox\n(Round 33/36)\nbaseline", refs["clinical_cox_RHUH"],
         "#0072B2"),
        ("v201 single-task\nU-Net\n(Round 38)", refs["v201_single_task_train_MU_test_RHUH"],
         "#999999"),
        ("v203 multi-task\nU-Net\n(Round 39)",
         v203["loco_1_train_MU_test_RHUH"]["c_index_test_RHUH"], "#D55E00"),
    ]
    labels = [s[0] for s in setups]
    vals = [s[1] for s in setups]
    colors = [s[2] for s in setups]
    bars = axes[0].bar(range(len(setups)), vals, color=colors,
                       edgecolor="black", linewidth=0.5)
    for i, v in enumerate(vals):
        axes[0].text(i, v + 0.01, f"{v:.4f}", ha="center", fontsize=11,
                     fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                    label="chance")
    axes[0].set_xticks(range(len(setups)))
    axes[0].set_xticklabels(labels, fontsize=9)
    axes[0].set_ylabel("Harrell's C-index")
    axes[0].set_title("A. Train MU → Test RHUH\n"
                      "Clinical Cox (C=0.666) BEATS deep learning")
    axes[0].set_ylim(0.4, 0.75)
    axes[0].legend(loc="upper right", fontsize=9)

    # Panel B: train RHUH → test MU
    setups2 = [
        ("Clinical Cox\n(Round 33/36)\nbaseline", refs["clinical_cox_MU"],
         "#0072B2"),
        ("v201 single-task\nU-Net\n(Round 38)",
         refs["v201_single_task_train_RHUH_test_MU"], "#999999"),
        ("v203 multi-task\nU-Net\n(Round 39)",
         v203["loco_2_train_RHUH_test_MU"]["c_index_test_MU"], "#D55E00"),
    ]
    labels2 = [s[0] for s in setups2]
    vals2 = [s[1] for s in setups2]
    colors2 = [s[2] for s in setups2]
    bars = axes[1].bar(range(len(setups2)), vals2, color=colors2,
                       edgecolor="black", linewidth=0.5)
    for i, v in enumerate(vals2):
        axes[1].text(i, v + 0.01, f"{v:.4f}", ha="center", fontsize=11,
                     fontweight="bold")
    axes[1].axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                    label="chance")
    axes[1].set_xticks(range(len(setups2)))
    axes[1].set_xticklabels(labels2, fontsize=9)
    axes[1].set_ylabel("Harrell's C-index")
    axes[1].set_title("B. Train RHUH → Test MU\n"
                      "Multi-task improves slightly (+0.057) but still loses")
    axes[1].set_ylim(0.4, 0.75)
    axes[1].legend(loc="upper right", fontsize=9)

    fig.suptitle("v203 HONEST NEGATIVE #5: multi-task foundation (auxiliary "
                 "outgrowth supervision) CANNOT rescue cross-cohort survival\n"
                 "Multi-task: 0.464 (MU→RHUH), 0.546 (RHUH→MU); Single-task: "
                 "0.452, 0.490; Clinical Cox: 0.666, 0.601 — clinical wins "
                 "every comparison",
                 fontsize=10.5, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig57_v203_multitask_foundation")


def main():
    figure_56_pfs_binary_screening()
    figure_57_multitask_foundation()
    print("done", flush=True)


if __name__ == "__main__":
    main()
