"""v220/v221 figures (Fig 74-75): multi-σ comprehensive validation +
final SOTA leaderboard."""
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


def figure_74_multi_sigma_comprehensive():
    print("Figure 74: multi-σ comprehensive validation",
          flush=True)
    v220 = json.loads(
        (RESULTS / "v220_multi_sigma_comprehensive.json"
         ).read_text())
    cc = v220["cross_cohort"]
    meta = v220["meta_analysis_multi_sigma"]
    cox = v220["cox_pfs_multi_sigma"]

    fig = plt.figure(figsize=(16.5, 10.0))
    gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.32)

    # Panel A: forest plot single-σ vs multi-σ
    ax_a = fig.add_subplot(gs[0, :2])
    rows_a = [
        ("MU in-sample\n**single-σ** (round 43)\nbootstrap mean",
         0.099, 0.008, 0.209, "#0072B2"),
        ("MU in-sample\n**multi-σ** (round 48)\nbootstrap mean",
         cc["MU_in_sample"]["bootstrap_mean"],
         cc["MU_in_sample"]["bootstrap_95_CI"][0],
         cc["MU_in_sample"]["bootstrap_95_CI"][1], "#D55E00"),
        ("RHUH external\n**single-σ** (round 42)",
         0.011, -0.197, 0.239, "#999999"),
        ("RHUH external\n**multi-σ** (round 48)",
         cc["RHUH_external"]["bootstrap_mean"],
         cc["RHUH_external"]["bootstrap_95_CI"][0],
         cc["RHUH_external"]["bootstrap_95_CI"][1], "#56B4E9"),
        ("**Round 43 META**\n**single-σ**\nP=0.036",
         0.083, -0.008, 0.173, "#0072B2"),
        ("**Round 48 META**\n**multi-σ**\n**P=0.0053**",
         meta["pooled_delta"], meta["pooled_95_CI"][0],
         meta["pooled_95_CI"][1], "#009E73"),
    ]
    y_pos = np.arange(len(rows_a))
    for i, (lab, mn, lo, hi, col) in enumerate(rows_a):
        ax_a.errorbar(mn, i, xerr=[[mn - lo], [hi - mn]],
                       fmt="o", color=col, markersize=12,
                       capsize=6, linewidth=2,
                       markeredgecolor="black",
                       markeredgewidth=0.5)
        ax_a.text(hi + 0.02, i, f"Δ={mn:+.3f}\n[{lo:+.3f}, "
                                  f"{hi:+.3f}]",
                    fontsize=9, va="center")
    ax_a.axvline(0, color="black", linewidth=0.8)
    ax_a.axvline(0.108, color="grey", linestyle=":",
                  alpha=0.5,
                  label="MU permutation-significant +0.108")
    ax_a.set_yticks(y_pos)
    ax_a.set_yticklabels([r[0] for r in rows_a],
                            fontsize=9)
    ax_a.set_xlabel("Δ AUC at H=365 d")
    ax_a.set_title(f"A. Forest plot: single-σ vs multi-σ\n"
                    f"Multi-σ meta P = "
                    f"{meta['one_sided_p']:.4f} (vs single-σ "
                    f"P = 0.036)")
    ax_a.set_xlim(-0.30, 0.45)
    ax_a.legend(loc="lower right", fontsize=9)
    ax_a.invert_yaxis()

    # Panel B: meta-analysis comparison
    ax_b = fig.add_subplot(gs[0, 2])
    metas = [
        ("Round 43\nsingle-σ", 0.083, 0.036, "#0072B2"),
        ("**Round 48\nmulti-σ**", meta["pooled_delta"],
         meta["one_sided_p"], "#009E73"),
    ]
    labels_b = [m[0] for m in metas]
    deltas = [m[1] for m in metas]
    ps = [m[2] for m in metas]
    colors = [m[3] for m in metas]
    ax_b.bar(range(len(metas)), deltas, color=colors,
              edgecolor="black", linewidth=0.5)
    for i, (d, p) in enumerate(zip(deltas, ps)):
        ax_b.text(i, d + 0.005, f"Δ={d:+.3f}",
                    ha="center", fontsize=11,
                    fontweight="bold")
        ax_b.text(i, d / 2, f"P={p:.4f}",
                    ha="center", fontsize=11,
                    fontweight="bold", color="white")
    ax_b.axhline(0, color="black", linewidth=0.8)
    ax_b.set_xticks(range(len(metas)))
    ax_b.set_xticklabels(labels_b, fontsize=10)
    ax_b.set_ylabel("IV-weighted pooled Δ AUC")
    ax_b.set_title("B. Meta-analysis upgrade\n"
                    "Multi-σ ~7× more significant\n"
                    "(P 0.036 → 0.0053)")
    ax_b.set_ylim(0, 0.18)

    # Panel C: continuous PFS Cox
    ax_c = fig.add_subplot(gs[1, 0])
    cox_models = [
        ("Clinical only\n(round 45)", cox["clin_only"]["C"],
         "#999999"),
        ("Clin + V_k σ=3\n(round 45)\nLR P=0.007",
         cox["clin_plus_Vk_s3"]["C"], "#0072B2"),
        ("**Clin + V_k\nmulti-σ (round 48)**\n**LR P=0.0009**",
         cox["clin_plus_Vk_multi_sigma"]["C"], "#D55E00"),
    ]
    labels_c = [m[0] for m in cox_models]
    cs = [m[1] for m in cox_models]
    colors_c = [m[2] for m in cox_models]
    ax_c.bar(range(len(cox_models)), cs, color=colors_c,
              edgecolor="black", linewidth=0.5)
    for i, c in enumerate(cs):
        ax_c.text(i, c + 0.005, f"{c:.4f}", ha="center",
                    fontsize=11, fontweight="bold")
    ax_c.axhline(0.5, color="grey", linestyle="--",
                  alpha=0.7, label="chance")
    ax_c.set_xticks(range(len(cox_models)))
    ax_c.set_xticklabels(labels_c, fontsize=8)
    ax_c.set_ylabel("Harrell's C-index (continuous PFS)")
    ax_c.set_title("C. Continuous PFS Cox\n"
                    "Multi-σ C=0.645 (LR=18.65, df=4, "
                    "P=0.0009)")
    ax_c.set_ylim(0.45, 0.70)
    ax_c.legend(loc="upper left", fontsize=9)

    # Panel D: incremental LRT
    ax_d = fig.add_subplot(gs[1, 1])
    incremental = cox["multi_sigma_incremental_vs_single_sigma"]
    rows_d = [
        ("Single-σ V_k\nadd to clinical\n(round 45 LR=7.32)",
         7.32, 1, 0.0068, "#0072B2"),
        ("**Multi-σ V_k\nadd to clinical**\n(round 48 LR=18.65)",
         18.65, 4, 0.0009, "#009E73"),
        ("**Multi-σ vs σ=3\nincremental**\n(round 48)",
         incremental["LR"], incremental["df"],
         incremental["P_one_sided"], "#D55E00"),
    ]
    labels_d = [r[0] for r in rows_d]
    lrs = [r[1] for r in rows_d]
    colors_d = [r[4] for r in rows_d]
    ax_d.bar(range(len(rows_d)), lrs, color=colors_d,
              edgecolor="black", linewidth=0.5)
    for i, (lr, df_v, p) in enumerate([(r[1], r[2], r[3])
                                          for r in rows_d]):
        ax_d.text(i, lr + 0.5, f"LR={lr:.2f}\ndf={df_v}\nP="
                                  f"{p:.4f}",
                    ha="center", fontsize=9,
                    fontweight="bold")
    ax_d.axhline(chi2_threshold(0.05, 1), color="grey",
                  linestyle=":", alpha=0.7,
                  label="χ² 5% threshold (df=1)")
    ax_d.set_xticks(range(len(rows_d)))
    ax_d.set_xticklabels(labels_d, fontsize=8)
    ax_d.set_ylabel("Likelihood-ratio statistic")
    ax_d.set_title("D. Cox LRT: multi-σ adds significantly "
                    "over single-σ\nIncremental LR=11.33 "
                    "(df=3, P=0.0101)")
    ax_d.set_ylim(0, 25)
    ax_d.legend(loc="upper left", fontsize=8)

    # Panel E: summary
    ax_e = fig.add_subplot(gs[1, 2])
    rows_e = [
        ("MU AUC\n(in-sample\nbootstrap)",
         "single-σ", 0.099, "#0072B2"),
        ("MU AUC\n(in-sample\nbootstrap)", "**multi-σ**",
         cc["MU_in_sample"]["bootstrap_mean"], "#D55E00"),
        ("Cross-cohort\nmeta-analysis", "single-σ", 0.083,
         "#0072B2"),
        ("Cross-cohort\nmeta-analysis", "**multi-σ**",
         meta["pooled_delta"], "#009E73"),
        ("Cox PFS\nC-index lift", "single-σ", 0.031,
         "#0072B2"),
        ("Cox PFS\nC-index lift", "**multi-σ**",
         cox["clin_plus_Vk_multi_sigma"]["C"]
         - cox["clin_only"]["C"], "#56B4E9"),
    ]
    bar_data = {}
    for name, cat, val, col in rows_e:
        bar_data.setdefault(name, [None, None, None, None])
        if cat == "single-σ":
            bar_data[name][0] = val
            bar_data[name][2] = "#0072B2"
        else:
            bar_data[name][1] = val
            bar_data[name][3] = col
    cats = list(bar_data.keys())
    x = np.arange(len(cats))
    width = 0.35
    single_vals = [bar_data[c][0] for c in cats]
    multi_vals = [bar_data[c][1] for c in cats]
    ax_e.bar(x - width/2, single_vals, width,
              color="#0072B2", edgecolor="black",
              linewidth=0.5, label="single-σ (round 43-45)")
    ax_e.bar(x + width/2, multi_vals, width,
              color="#D55E00", edgecolor="black",
              linewidth=0.5, label="**multi-σ (round 48)**")
    for i, (s, m) in enumerate(zip(single_vals, multi_vals)):
        ax_e.text(i - width/2, s + 0.005, f"{s:+.3f}",
                    ha="center", fontsize=8)
        ax_e.text(i + width/2, m + 0.005, f"{m:+.3f}",
                    ha="center", fontsize=9,
                    fontweight="bold")
    ax_e.set_xticks(x)
    ax_e.set_xticklabels(cats, fontsize=8)
    ax_e.set_ylabel("Effect size")
    ax_e.set_title("E. Single-σ vs multi-σ across all "
                    "evidence levels\n(multi-σ wins on every "
                    "metric)")
    ax_e.legend(loc="upper right", fontsize=8)

    fig.suptitle("v220 BEYOND-NMI multi-σ comprehensive "
                  f"validation: meta-analysis pooled Δ=+"
                  f"{meta['pooled_delta']:.3f} (z={meta['z_score']:.2f}, "
                  f"P={meta['one_sided_p']:.4f}) ~7× more "
                  "significant than round 43 single-σ; multi-σ "
                  "Cox C=0.645 P=0.0009; multi-σ adds "
                  "significantly over single-σ in Cox (P=0.0101).",
                  fontsize=10.5, y=0.995)
    return save_fig(fig, "fig74_v220_multi_sigma_comprehensive")


def chi2_threshold(p, df):
    from scipy.stats import chi2
    return float(chi2.isf(p, df))


def figure_75_sota_leaderboard():
    print("Figure 75: final SOTA leaderboard", flush=True)
    v221 = json.loads(
        (RESULTS / "v221_3d_vit_sota.json").read_text())
    lb = v221["sota_leaderboard"]

    fig, axes = plt.subplots(1, 2, figsize=(16.5, 6.5))

    # Panel A: leaderboard ranked
    sorted_lb = sorted(lb, key=lambda x: -x["auc"])
    methods = [m["method"].replace("**", "") for m in sorted_lb]
    aucs = [m["auc"] for m in sorted_lb]
    kinds = [m["kind"] for m in sorted_lb]
    colors = ["#D55E00" if k == "logistic" else "#0072B2"
                for k in kinds]
    # Highlight the multi-σ logistic
    for i, m in enumerate(sorted_lb):
        if "multi-σ" in m["method"] and \
            "shape" not in m["method"] and \
                "kitchen" not in m["method"]:
            colors[i] = "#009E73"
    bars = axes[0].barh(range(len(methods)), aucs,
                          color=colors, edgecolor="black",
                          linewidth=0.5)
    for i, a in enumerate(aucs):
        axes[0].text(a + 0.005, i, f"{a:.3f}",
                       fontsize=9, va="center",
                       fontweight="bold")
    axes[0].axvline(0.5, color="grey", linestyle="--",
                     alpha=0.7, label="chance")
    axes[0].set_yticks(range(len(methods)))
    axes[0].set_yticklabels(methods, fontsize=8)
    axes[0].set_xlabel("MU pooled OOF AUC at H=365 d")
    axes[0].set_title("A. Final SOTA leaderboard "
                       "(ranked by AUC)\n"
                       "Logistic models DOMINATE deep learning")
    axes[0].set_xlim(0.45, 0.95)
    axes[0].legend(loc="lower right", fontsize=9)
    axes[0].invert_yaxis()

    # Panel B: AUC vs param count
    ax_b = axes[1]
    for m in lb:
        col = ("#D55E00" if m["kind"] == "logistic"
                 else "#0072B2")
        if "multi-σ" in m["method"] and \
            "shape" not in m["method"] and \
                "kitchen" not in m["method"]:
            col = "#009E73"
        ax_b.scatter(m["params_or_feats"], m["auc"],
                       s=200, color=col, edgecolor="black",
                       linewidth=0.5)
        if "multi-σ" in m["method"] or "ResNet" in m[
            "method"] or "ViT" in m["method"] or \
            "logistic clin only" in m["method"]:
            short_name = m["method"].split("(")[0].replace(
                "**", "").strip()
            ax_b.annotate(short_name,
                            (m["params_or_feats"], m["auc"]),
                            xytext=(8, 5),
                            textcoords="offset points",
                            fontsize=8)
    ax_b.set_xscale("log")
    ax_b.set_xlabel("Parameters or features (log scale)")
    ax_b.set_ylabel("MU pooled OOF AUC at H=365 d")
    ax_b.set_title("B. AUC vs model complexity\n"
                    "**More parameters HURT** at MU n=130; "
                    "logistic (orange/green) ≫ deep (blue)")
    ax_b.axhline(0.5, color="grey", linestyle="--", alpha=0.5)
    ax_b.set_ylim(0.45, 0.95)

    fig.suptitle("v221 BEYOND-NMI FINAL SOTA LEADERBOARD: "
                  "logistic clin+V_kernel multi-σ (7 features) "
                  "wins by +0.116 to +0.247 AUC over every deep "
                  "architecture tested (SimpleCNN, deep "
                  "ensemble, ResNet-18, ResNet-18+SimCLR, "
                  "Vision Transformer). At MU n=130, the "
                  "feature-engineered logistic is the "
                  "deployment-optimal model.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig75_v221_sota_leaderboard")


def main():
    figure_74_multi_sigma_comprehensive()
    figure_75_sota_leaderboard()
    print("done", flush=True)


if __name__ == "__main__":
    main()
