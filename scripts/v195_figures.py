"""v195 figures (Fig 41-42): multimodal Cox prognosis — honest negative."""
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


def figure_41_univariate_forest():
    print("Figure 41: univariate Cox forest plot", flush=True)
    v195 = json.loads((RESULTS / "v195_multimodal_prognosis.json").read_text())
    uni = v195["univariate_cox"]

    feats = ["postop_vol", "gtr", "kps", "preop_vol", "age", "idh",
              "v_kernel_s3"]
    feat_labels = {
        "postop_vol": "Postop residual\nvolume (cm³)",
        "gtr": "GTR\n(vs <100% resection)",
        "kps": "Preop KPS",
        "preop_vol": "Preop tumor\nvolume (cm³)",
        "age": "Age",
        "idh": "IDH mutant\n(vs wild-type)",
        "v_kernel_s3": "V_kernel σ=3\n(round-27 kernel)",
    }
    HRs = [uni[f]["HR_per_SD"] for f in feats]
    pvals = [uni[f]["p_value"] for f in feats]

    fig, ax = plt.subplots(figsize=(9.0, 6.0))
    y = np.arange(len(feats))
    colors = ["#D55E00" if p < 0.05 else "#999999" for p in pvals]
    sizes = [200 if p < 0.05 else 100 for p in pvals]
    ax.scatter(HRs, y, s=sizes, c=colors, edgecolor="black",
                linewidth=0.7, zorder=3)
    ax.axvline(1, color="black", linestyle="--", alpha=0.5,
                label="HR = 1 (no effect)")
    for i, (hr, p, f) in enumerate(zip(HRs, pvals, feats)):
        col = "#D55E00" if p < 0.05 else "black"
        marker = "★" if p < 0.05 else ""
        ax.text(hr * 1.05, i, f"  HR={hr:.3f}, p={p:.4f} {marker}",
                color=col, fontsize=9, va="center")
    ax.set_yticks(y)
    ax.set_yticklabels([feat_labels[f] for f in feats], fontsize=9)
    ax.set_xlabel("Univariate Cox hazard ratio per SD")
    ax.set_xlim(0.4, 2.5)
    ax.set_xscale("log")
    ax.set_title(f"v195 univariate Cox HRs (RHUH-GBM, n=39, "
                  f"{31}/39 events)\n"
                  f"Postop residual volume + GTR are significant; "
                  f"V_kernel is NOT (p = 0.92)")
    ax.legend(loc="lower right", fontsize=9)
    return save_fig(fig, "fig41_univariate_cox_forest")


def figure_42_cindex_comparison():
    print("Figure 42: M0 vs M1 C-index", flush=True)
    v195 = json.loads((RESULTS / "v195_multimodal_prognosis.json").read_text())
    c0 = v195["M0_clinical_only"]["c_index"]
    c1 = v195["M1_clinical_plus_kernel"]["c_index"]
    delta = v195["delta_c_index"]
    lrt = v195["likelihood_ratio_test"]

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.0))

    # Left: C-index bars
    models = ["M0\n(Clinical only)", "M1\n(Clinical + V_kernel)"]
    cs = [c0, c1]
    colors = ["#999999", "#56B4E9"]
    axes[0].bar(models, cs, color=colors, edgecolor="black", linewidth=0.5)
    for i, c in enumerate(cs):
        axes[0].text(i, c + 0.01, f"{c:.4f}",
                       ha="center", fontsize=11, fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.5,
                     label="C = 0.5 (chance)")
    axes[0].set_ylabel("Harrell's C-index")
    axes[0].set_title(f"Cox PH model comparison\n"
                       f"Delta C = {c1-c0:+.4f}, "
                       f"LRT chi^2={lrt['chi2']:.3f}, p={lrt['p_value']:.3f}")
    axes[0].set_ylim(0.4, 0.8)
    axes[0].legend(loc="lower right", fontsize=9)

    # Right: bootstrap delta C-index distribution
    # Re-create bootstrap from saved CI
    delta_pt = delta["point"]
    ci_lo = delta["ci_95_lo"]
    ci_hi = delta["ci_95_hi"]

    axes[1].axvline(0, color="black", linewidth=2, label="Delta C = 0")
    axes[1].axvline(delta_pt, color="#D55E00", linewidth=2,
                       label=f"Observed Delta C = {delta_pt:+.4f}")
    axes[1].axvspan(ci_lo, ci_hi, alpha=0.25, color="#D55E00",
                       label=f"95% bootstrap CI [{ci_lo:+.4f}, {ci_hi:+.4f}]")
    axes[1].set_xlabel("Delta C-index (M1 - M0)")
    axes[1].set_ylabel("")
    axes[1].set_yticks([])
    axes[1].set_title(f"Bootstrap 95% CI on Delta C-index\n"
                       f"CI spans 0 - kernel does NOT add prognostic info")
    axes[1].set_xlim(-0.10, 0.10)
    axes[1].legend(loc="upper right", fontsize=9)

    fig.suptitle("v195 HONEST NEGATIVE: kernel does NOT improve Cox "
                  "prognosis beyond clinical features\n"
                  "Clinical-only model (Age, KPS, IDH, GTR, RT+TMZ) "
                  "achieves C = 0.667; adding V_kernel does NOT help",
                  fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig42_multimodal_cox_cindex")


def main():
    figure_41_univariate_forest()
    figure_42_cindex_comparison()
    print("done", flush=True)


if __name__ == "__main__":
    main()
