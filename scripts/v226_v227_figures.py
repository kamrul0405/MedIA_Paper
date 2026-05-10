"""v226/v227 figures (Fig 80-81): L1 lasso path + stability
selection; IDH1 molecular classification."""
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


def figure_80_lasso_stability():
    print("Figure 80: lasso + stability selection",
          flush=True)
    v226 = json.loads(
        (RESULTS / "v226_stability_selection.json").read_text())
    path = v226["lasso_path"]
    stab = v226["stability_selection"]
    auc_cmp = v226["auc_comparison"]
    freqs = stab["selection_frequencies"]
    feat_names = list(freqs.keys())
    freq_vals = list(freqs.values())

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: Lasso path (n_nonzero vs λ)
    lams = sorted([float(k) for k in path.keys()])
    n_nonzero = [path[f"{l:.4f}"]["n_nonzero"] for l in lams]
    aucs = [path[f"{l:.4f}"]["auc"] for l in lams]
    ax_a = axes[0]
    color1 = "#0072B2"
    color2 = "#D55E00"
    ax_a.plot(lams, n_nonzero, "-o", color=color1,
                linewidth=2, markersize=8,
                label="# nonzero features")
    ax_a.set_xlabel("λ (L1 penalty)")
    ax_a.set_ylabel("# nonzero features",
                       color=color1)
    ax_a.tick_params(axis="y", labelcolor=color1)
    ax_a.set_xscale("log")
    ax_a2 = ax_a.twinx()
    ax_a2.plot(lams, aucs, "-s", color=color2,
                 linewidth=2, markersize=8,
                 label="AUC")
    ax_a2.set_ylabel("AUC", color=color2)
    ax_a2.tick_params(axis="y", labelcolor=color2)
    ax_a2.axhline(0.5, color="grey", linestyle=":",
                    alpha=0.5)
    ax_a.set_title("A. Lasso regularization path\n"
                     "Multi-σ logistic feature selection")
    lines1, labels1 = ax_a.get_legend_handles_labels()
    lines2, labels2 = ax_a2.get_legend_handles_labels()
    ax_a.legend(lines1 + lines2, labels1 + labels2,
                  loc="center", fontsize=9)

    # Panel B: stability frequencies
    ax_b = axes[1]
    sorted_idx = np.argsort(freq_vals)[::-1]
    feat_sorted = [feat_names[i] for i in sorted_idx]
    freq_sorted = [freq_vals[i] for i in sorted_idx]
    colors_b = ["#009E73" if f >= 0.80
                  else "#D55E00" if f >= 0.50
                  else "#999999"
                  for f in freq_sorted]
    ax_b.barh(range(len(feat_sorted)), freq_sorted,
                color=colors_b, edgecolor="black",
                linewidth=0.5)
    for i, f in enumerate(freq_sorted):
        marker = "✓" if f >= 0.80 else ""
        ax_b.text(f + 0.01, i, f"{f:.3f} {marker}",
                    va="center", fontsize=9,
                    fontweight="bold")
    ax_b.axvline(0.80, color="#009E73",
                   linestyle="--", alpha=0.7,
                   label="80% threshold")
    ax_b.axvline(0.50, color="#D55E00",
                   linestyle="--", alpha=0.7,
                   label="50% threshold")
    ax_b.set_yticks(range(len(feat_sorted)))
    ax_b.set_yticklabels(feat_sorted, fontsize=9)
    ax_b.set_xlabel("Selection frequency over 200 bootstraps")
    ax_b.set_title("B. Stability selection (λ=0.05)\n"
                     "σ=3 is the canonically-stable kernel scale")
    ax_b.set_xlim(0, 1.15)
    ax_b.invert_yaxis()
    ax_b.legend(loc="lower right", fontsize=8)

    # Panel C: parsimony comparison
    ax_c = axes[2]
    methods = [
        ("Multi-σ {2,3,4,5}\n(round 47)", 7,
         auc_cmp["multi_sigma_2_3_4_5"], "#0072B2"),
        ("70%-stable\n{idh1, V_k σ=3}",
         2, 0.7230, "#009E73"),
        ("60%-stable\n{idh1, V_k σ=2,3}",
         3, 0.7235, "#56B4E9"),
        ("50%-stable\n{idh1, V_k σ=1,2,3}",
         4, 0.7243, "#D55E00"),
    ]
    nfs = [m[1] for m in methods]
    aucs_c = [m[2] for m in methods]
    colors_c = [m[3] for m in methods]
    ax_c.scatter(nfs, aucs_c, s=200, c=colors_c,
                   edgecolor="black", linewidth=0.5)
    for i, (lab, n_, a, _) in enumerate(methods):
        ax_c.annotate(lab,
                        (n_, a),
                        xytext=(8, 5),
                        textcoords="offset points",
                        fontsize=8)
    ax_c.set_xlabel("Number of features")
    ax_c.set_ylabel("AUC at H=365 d")
    ax_c.set_title("C. Parsimony: stable subsets vs full multi-σ\n"
                     "2-feature model achieves AUC=0.723")
    ax_c.set_xlim(0, 9)
    ax_c.set_ylim(0.65, 0.86)

    fig.suptitle("v226 BEYOND-NMI L1 lasso + stability "
                  "selection: σ=3 emerges as the canonically-"
                  "stable kernel scale (74.5% selection over "
                  "200 bootstraps); a 2-feature model "
                  "{IDH1, V_k σ=3} achieves AUC=0.723 — "
                  "extreme parsimony.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig80_v226_lasso_stability")


def figure_81_idh_classification():
    print("Figure 81: IDH1 molecular classification",
          flush=True)
    v227 = json.loads(
        (RESULTS / "v227_idh_classification.json").read_text())
    res = v227["results"]
    deltas = v227["bootstrap_deltas"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: AUC by variant
    methods = [
        ("**A. Clinical only**\n(age + MGMT)\nn=2",
         res["A_clin_only"]["pooled_oof_auc"], "#0072B2"),
        ("B. Kernel only\n(multi-σ)\nn=4",
         res["B_kernel_only"]["pooled_oof_auc"], "#999999"),
        ("**C. Combined**\n(clin + multi-σ)\nn=6",
         res["C_clin_plus_kernel"]["pooled_oof_auc"],
         "#D55E00"),
        ("D. 3D CNN\n(488K params)",
         res["D_3D_CNN"]["pooled_oof_auc"], "#56B4E9"),
    ]
    labels = [m[0] for m in methods]
    aucs = [m[1] for m in methods]
    colors = [m[2] for m in methods]
    bars = axes[0].bar(range(len(methods)), aucs,
                        color=colors, edgecolor="black",
                        linewidth=0.5)
    for i, a in enumerate(aucs):
        axes[0].text(i, a + 0.01, f"{a:.3f}",
                       ha="center", fontsize=11,
                       fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7, label="chance")
    axes[0].set_xticks(range(len(methods)))
    axes[0].set_xticklabels(labels, fontsize=8)
    axes[0].set_ylabel("Pooled OOF AUC for IDH1 status")
    axes[0].set_title("A. IDH1 classification (n=151, "
                       "39 mut / 112 WT)\n"
                       "Clinical alone strong; kernel alone "
                       "near chance")
    axes[0].set_ylim(0.45, 1.0)
    axes[0].legend(loc="upper right", fontsize=9)

    # Panel B: per-fold AUC
    n_folds = 5
    width = 0.20
    x = np.arange(n_folds)
    fold_data = [
        ("Clin only", res["A_clin_only"]["fold_aucs"],
         "#0072B2"),
        ("Kernel only", res["B_kernel_only"]["fold_aucs"],
         "#999999"),
        ("Combined",
         res["C_clin_plus_kernel"]["fold_aucs"], "#D55E00"),
        ("CNN", res["D_3D_CNN"]["fold_aucs"], "#56B4E9"),
    ]
    for i, (lab, fa, col) in enumerate(fold_data):
        axes[1].bar(x + (i - 1.5) * width, fa, width,
                      color=col, edgecolor="black",
                      linewidth=0.5, label=lab)
    axes[1].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"Fold {i+1}"
                                for i in range(n_folds)])
    axes[1].set_ylabel("Per-fold AUC")
    axes[1].set_title("B. Per-fold AUC distribution\n"
                       "Clinical and Combined dominate; "
                       "Kernel-only chance-level")
    axes[1].set_ylim(0.4, 1.05)
    axes[1].legend(loc="lower right", fontsize=8)

    # Panel C: Δ AUC
    delta_combined = deltas["combined_minus_clin"]
    delta_kernel = deltas["kernel_minus_clin"]
    pair_data = [
        ("**Combined − clinical**",
         delta_combined["mean"],
         delta_combined["95_CI"],
         delta_combined["p_one_sided"],
         "#D55E00"),
        ("Kernel − clinical",
         delta_kernel["mean"],
         delta_kernel["95_CI"],
         delta_kernel["p_one_sided"],
         "#999999"),
    ]
    labels_c = [d[0] for d in pair_data]
    means = [d[1] for d in pair_data]
    cis = [d[2] for d in pair_data]
    ps = [d[3] for d in pair_data]
    err_lo = [max(0, m - c[0]) for m, c in zip(means, cis)]
    err_hi = [max(0, c[1] - m) for m, c in zip(means, cis)]
    colors_c = [d[4] for d in pair_data]
    axes[2].bar(range(len(pair_data)), means,
                  yerr=[err_lo, err_hi], color=colors_c,
                  edgecolor="black", linewidth=0.5,
                  capsize=6)
    for i, (m, p) in enumerate(zip(means, ps)):
        sig = "✓" if p < 0.05 else "~" if p < 0.10 else ""
        axes[2].text(i, m + 0.015 * np.sign(
            m if m != 0 else 1),
                       f"Δ={m:+.3f}{sig}\nP={p:.3f}",
                       ha="center", fontsize=10,
                       fontweight="bold",
                       va="bottom" if m >= 0 else "top")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_xticks(range(len(pair_data)))
    axes[2].set_xticklabels(labels_c, fontsize=9)
    axes[2].set_ylabel("Δ AUC vs clinical-only")
    axes[2].set_title("C. Bootstrap pairwise Δ\n"
                       "Combined adds +0.018 (P=0.064 marginal); "
                       "Kernel alone -0.310")
    axes[2].set_ylim(-0.45, 0.10)

    fig.suptitle("v227 BEYOND-NMI HONEST SCOPING: kernel does "
                  "NOT primarily encode molecular pathology. "
                  "Clinical features (age + MGMT) achieve AUC="
                  "0.882 for IDH1; kernel alone is chance-level "
                  "(0.554). Combined gives marginal +0.018 lift. "
                  "Kernel is PFS-specific (encodes outgrowth/"
                  "recurrence biology), not a general molecular "
                  "biomarker.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig81_v227_idh_classification")


def main():
    figure_80_lasso_stability()
    figure_81_idh_classification()
    print("done", flush=True)


if __name__ == "__main__":
    main()
