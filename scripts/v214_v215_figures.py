"""v214/v215 figures (Fig 68-69): binary-score-in-Cox unification +
self-supervised SimCLR pretraining."""
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


def figure_68_cox_unification():
    print("Figure 68: binary-score-in-Cox unification",
          flush=True)
    v214 = json.loads(
        (RESULTS / "v214_binary_score_cox.json").read_text())
    cox = v214["cox_models"]
    boot = v214["bootstrap"]
    lrt_vk = v214["LRT_clin_vs_VkernelPlusClin"]
    lrt_phat = v214["LRT_clin_vs_phatPlusClin"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: Cox C-index comparison
    setups = [
        ("Clinical only\n(age+IDH+MGMT)",
         cox["clin_only"]["C_index"], "#999999"),
        ("V_kernel only\n(round 32 setup)",
         cox["Vkernel_only"]["C_index"], "#56B4E9"),
        ("p_hat only\n(binary classifier\nrisk score)",
         cox["phat_only"]["C_index"], "#0072B2"),
        ("**V_kernel + clinical**\n(LRT P=0.007 ✓✓)",
         cox["Vkernel_plus_clin"]["C_index"], "#D55E00"),
        ("**p_hat + clinical**\n(LRT P=0.010 ✓✓)",
         cox["phat_plus_clin"]["C_index"], "#009E73"),
    ]
    labels = [s[0] for s in setups]
    cs = [s[1] for s in setups]
    colors = [s[2] for s in setups]
    axes[0].bar(range(len(setups)), cs,
                  color=colors, edgecolor="black", linewidth=0.5)
    for i, c in enumerate(cs):
        axes[0].text(i, c + 0.005, f"{c:.4f}",
                       ha="center", fontsize=10,
                       fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7, label="chance")
    axes[0].axhline(cox["clin_only"]["C_index"],
                     color="#999999", linestyle=":", alpha=0.7,
                     label=f"Clinical baseline = "
                           f"{cox['clin_only']['C_index']:.3f}")
    axes[0].set_xticks(range(len(setups)))
    axes[0].set_xticklabels(labels, fontsize=8)
    axes[0].set_ylabel("Harrell's C-index (continuous PFS)")
    axes[0].set_title("A. Cox PH on continuous PFS (n=130)\n"
                       "V_kernel AND p_hat both significantly "
                       "improve over clinical")
    axes[0].set_ylim(0.4, 0.70)
    axes[0].legend(loc="upper left", fontsize=8)

    # Panel B: bootstrap Δ C
    boot_setups = [
        ("Δ C\n(V_kernel + clin)\n− clin",
         boot["delta_C_Vk_minus_clin_mean"],
         boot["delta_C_Vk_minus_clin_95_CI"], "#D55E00"),
        ("Δ C\n(p_hat + clin)\n− clin",
         boot["delta_C_phat_minus_clin_mean"],
         boot["delta_C_phat_minus_clin_95_CI"], "#009E73"),
        ("Δ C\n(p_hat + clin)\n− (V_k + clin)",
         boot["delta_C_phat_minus_Vk_mean"],
         boot["delta_C_phat_minus_Vk_95_CI"], "#56B4E9"),
    ]
    labels_b = [s[0] for s in boot_setups]
    means_b = [s[1] for s in boot_setups]
    cis_b = [s[2] for s in boot_setups]
    err_lo = [m - ci[0] for m, ci in zip(means_b, cis_b)]
    err_hi = [ci[1] - m for m, ci in zip(means_b, cis_b)]
    colors_b = [s[3] for s in boot_setups]
    axes[1].bar(range(len(boot_setups)), means_b,
                  yerr=[err_lo, err_hi], color=colors_b,
                  edgecolor="black", linewidth=0.5, capsize=6)
    for i, m in enumerate(means_b):
        axes[1].text(i, m + 0.003 * np.sign(m if m != 0 else 1),
                       f"{m:+.4f}", ha="center", fontsize=10,
                       fontweight="bold",
                       va="bottom" if m >= 0 else "top")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_xticks(range(len(boot_setups)))
    axes[1].set_xticklabels(labels_b, fontsize=8)
    axes[1].set_ylabel("Δ C-index")
    axes[1].set_title("B. Bootstrap Δ C-index\n"
                       "p_hat ≈ V_kernel in Cox (third bar NS)")
    axes[1].set_ylim(-0.04, 0.12)

    # Panel C: endpoint-mismatch summary
    ax_c = axes[2]
    rows = [
        ("OS Cox\n(rounds 32-38)\nV_kernel + clin", "FAIL",
         "#999999"),
        ("OS supervised CNN\n(round 38 v201)\nC = 0.45",
         "FAIL", "#999999"),
        ("PFS binary 365-d AUC\n(round 39 v202)\nΔ AUC = +0.108",
         "WORKS", "#009E73"),
        ("**PFS Cox**\n**(round 45 v214)**\nΔ C = +0.031, P=0.007",
         "WORKS", "#D55E00"),
    ]
    labels_c = [r[0] for r in rows]
    colors_c = [r[2] for r in rows]
    statuses = [r[1] for r in rows]
    ax_c.bar(range(len(rows)),
              [1] * len(rows),
              color=colors_c, edgecolor="black", linewidth=0.5)
    for i, st in enumerate(statuses):
        ax_c.text(i, 0.5, st, ha="center", va="center",
                    fontsize=12, fontweight="bold",
                    color="white")
    ax_c.set_xticks(range(len(rows)))
    ax_c.set_xticklabels(labels_c, fontsize=8)
    ax_c.set_yticks([])
    ax_c.set_title("C. Endpoint-mismatch resolved\n"
                    "Kernel works for PFS (binary AND continuous)\n"
                    "but NOT OS continuous Cox (5 negatives)")

    fig.suptitle(f"v214 BEYOND-NMI ENDPOINT-MISMATCH UNIFICATION: "
                  f"on continuous MU PFS (n=130, 130 events), "
                  f"V_kernel + clinical Cox C={cox['Vkernel_plus_clin']['C_index']:.3f} "
                  f"(LR={lrt_vk['LR']:.2f}, "
                  f"df=1, P={lrt_vk['P']:.4f}). p_hat + clinical "
                  f"matches (P={lrt_phat['P']:.4f}). The earlier "
                  f"5 'negatives' (rounds 32-38) were OS-specific; "
                  f"PFS works.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig68_v214_cox_unification")


def figure_69_simclr():
    print("Figure 69: SimCLR self-supervised pretraining",
          flush=True)
    v215 = json.loads(
        (RESULTS / "v215_simclr_pretrain.json").read_text())

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: pretraining loss curve
    losses = v215["pretrain_loss_curve"]
    axes[0].plot(range(1, len(losses) + 1), losses,
                   "-o", color="#D55E00", linewidth=2,
                   markersize=5)
    axes[0].set_xlabel("Pretraining epoch")
    axes[0].set_ylabel("NT-Xent contrastive loss")
    axes[0].set_title(f"A. SimCLR pretraining loss\n"
                       f"509 multi-cohort masks "
                       f"(label-free, 4 cohorts)")
    axes[0].axhline(np.log(2 * 16),  # log(2N) baseline
                      color="grey", linestyle="--",
                      alpha=0.7,
                      label="Random pairing baseline\n"
                            "log(2*16)≈3.47")
    axes[0].legend(loc="upper right", fontsize=9)

    # Panel B: per-fold AUC
    fold_aucs = v215["fold_aucs"]
    folds = list(range(1, len(fold_aucs) + 1))
    axes[1].bar(folds, fold_aucs, color="#56B4E9",
                  edgecolor="black", linewidth=0.5)
    for f, a in zip(folds, fold_aucs):
        axes[1].text(f, a + 0.01, f"{a:.3f}",
                       ha="center", fontsize=10,
                       fontweight="bold")
    axes[1].axhline(v215["pooled_oof_auc"], color="#0072B2",
                     linestyle="--", alpha=0.8,
                     label=f"Pooled OOF = "
                           f"{v215['pooled_oof_auc']:.3f}")
    axes[1].axhline(v215["fold_mean_auc"], color="#009E73",
                     linestyle="--", alpha=0.8,
                     label=f"Per-fold mean = "
                           f"{v215['fold_mean_auc']:.3f}")
    axes[1].axhline(0.5, color="grey", linestyle=":",
                     alpha=0.7, label="chance")
    axes[1].set_xticks(folds)
    axes[1].set_xticklabels([f"Fold {f}" for f in folds])
    axes[1].set_ylabel("MU OOF AUC at H=365 d")
    axes[1].set_title("B. SimCLR + head FT on MU (5-fold CV)\n"
                       "Per-fold mean = 0.706 vs supervised "
                       "CNN ~0.586")
    axes[1].set_ylim(0.4, 0.95)
    axes[1].legend(loc="lower right", fontsize=9)

    # Panel C: comparison summary
    methods = [
        ("v207 5-seed\nsupervised CNN\n(MU only)", 0.586,
         "#999999"),
        ("v209 deep\nensemble 50 models\n(MU only)", 0.587,
         "#999999"),
        ("**v215 SimCLR**\n**(LABEL-FREE\n509 masks pretrain)**",
         v215["pooled_oof_auc"], "#D55E00"),
        ("v215 SimCLR\nper-fold mean",
         v215["fold_mean_auc"], "#56B4E9"),
        ("v202 logistic\nclin+V_kernel\n(MU)", 0.728, "#0072B2"),
        ("v213 supervised\npretrain MU + FT RHUH",
         0.804, "#009E73"),
    ]
    labels_c = [m[0] for m in methods]
    aucs_c = [m[1] for m in methods]
    colors_c = [m[2] for m in methods]
    axes[2].bar(range(len(methods)), aucs_c,
                  color=colors_c, edgecolor="black",
                  linewidth=0.5)
    for i, a in enumerate(aucs_c):
        axes[2].text(i, a + 0.01, f"{a:.3f}",
                       ha="center", fontsize=10,
                       fontweight="bold")
    axes[2].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7, label="chance")
    axes[2].set_xticks(range(len(methods)))
    axes[2].set_xticklabels(labels_c, fontsize=8)
    axes[2].set_ylabel("AUC at H=365 d")
    axes[2].set_title("C. Self-supervised vs supervised\n"
                       "Label-free SimCLR per-fold mean = 0.706 "
                       "(supervised CNN was 0.586)")
    axes[2].set_ylim(0.45, 0.85)
    axes[2].legend(loc="lower right", fontsize=8)

    fig.suptitle("v215 BEYOND-NMI SELF-SUPERVISED LABEL-FREE "
                  "PRETRAINING: contrastive learning on 509 multi-"
                  "cohort masks (4 cohorts, no PFS labels for "
                  "encoder) + frozen-encoder head fine-tune on MU "
                  "n=130 reaches per-fold AUC=0.706 (vs supervised "
                  "CNN 0.586, +0.12). Approaches simple logistic "
                  "(0.728) without using any labels for the "
                  "encoder.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig69_v215_simclr_pretrain")


def main():
    figure_68_cox_unification()
    figure_69_simclr()
    print("done", flush=True)


if __name__ == "__main__":
    main()
