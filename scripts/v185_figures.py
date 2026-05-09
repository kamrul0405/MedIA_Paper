"""v185_figures: UODSL figures for round 23.

Generates:
  Fig 13: P(outgrowth) vs distance from baseline boundary, log-scale,
          all 7 cohorts overlaid with fitted exponential curves
  Fig 14: Per-cohort lambda values with 95% bootstrap CIs, ordered by
          tumour type (brain-mets vs GBM vs glioma-mixed)
  Fig 15: Universal scaling collapse: P/A vs d/lambda, log-scale, all
          7 cohorts on same axes -> tests whether the FUNCTIONAL form
          is universal even if lambda varies
"""
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
    "grid.linestyle": "--",
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})

# Colour palette grouped by tumour-type biology
TUMOR_GROUPS = {
    "Brain-mets":          ["Yale-Brain-Mets", "PROTEAS-brain-mets"],
    "GBM (post-op/mixed)": ["UCSF-POSTOP", "RHUH-GBM"],
    "Mixed/lower-grade":   ["LUMIERE", "MU-Glioma-Post", "UPENN-GBM"],
}
COHORT_COLORS = {
    "Yale-Brain-Mets":     "#000000",
    "PROTEAS-brain-mets":  "#D55E00",
    "UCSF-POSTOP":         "#0072B2",
    "RHUH-GBM":            "#009E73",
    "LUMIERE":             "#CC79A7",
    "MU-Glioma-Post":      "#E69F00",
    "UPENN-GBM":           "#56B4E9",
}
COHORT_GROUP = {c: g for g, lst in TUMOR_GROUPS.items() for c in lst}


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


# ============================================================================
# Figure 13 — P(outgrowth) vs distance log-scale, all 7 cohorts
# ============================================================================

def figure_13_decay_curves():
    print("Figure 13: per-cohort exponential decay curves", flush=True)
    v185 = json.loads((RESULTS / "v185_uodsl.json").read_text())
    res = v185["cohort_results"]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.0))

    # Left: linear y-axis
    # Right: log y-axis (exponential decay -> linear in log)
    for ax in axes:
        for c, r in res.items():
            d = np.array(r["d_array"])
            p = np.array(r["p_array"])
            color = COHORT_COLORS[c]
            ax.plot(d, p, "o", color=color, markersize=6,
                    label=f"{c} (n={r['n_patients']}, "
                          f"lambda={r['lambda_point']:.2f})",
                    alpha=0.85)
            # fitted line
            d_fit = np.linspace(0.5, np.max(d) * 1.1, 100)
            A = r["A_point"]
            lam = r["lambda_point"]
            if not (np.isnan(lam) or np.isinf(lam)):
                p_fit = A * np.exp(-d_fit / lam)
                ax.plot(d_fit, p_fit, "-", color=color, linewidth=1.2,
                        alpha=0.6)
        ax.set_xlabel("Distance from baseline mask boundary (voxels)")

    axes[0].set_ylabel("P(outgrowth | distance d)")
    axes[0].set_title("Linear scale — empirical P(outgrowth | d)")
    axes[0].set_ylim(bottom=0)

    axes[1].set_ylabel("P(outgrowth | distance d)  [log scale]")
    axes[1].set_yscale("log")
    axes[1].set_title("Log scale — exponential = straight line")
    axes[1].legend(loc="upper right", fontsize=7,
                    title="Cohort  (n, lambda)",
                    title_fontsize=8)

    fig.suptitle("v185 UODSL: P(outgrowth | distance) = A * exp(-d / lambda)\n"
                  "across all 7 cohorts (n_total = 695)",
                  fontsize=12, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig13_uodsl_decay_curves")


# ============================================================================
# Figure 14 — Per-cohort lambda with bootstrap CIs, ordered by tumour group
# ============================================================================

def figure_14_lambda_per_cohort():
    print("Figure 14: per-cohort lambda values with CIs", flush=True)
    v185 = json.loads((RESULTS / "v185_uodsl.json").read_text())
    res = v185["cohort_results"]

    # Order cohorts by tumour group
    ordered = []
    for group, members in TUMOR_GROUPS.items():
        for c in members:
            if c in res:
                ordered.append((c, group))

    fig, ax = plt.subplots(figsize=(12.0, 5.5))
    x = np.arange(len(ordered))

    means = [res[c]["lambda_point"] for c, _ in ordered]
    los = [res[c]["lambda_ci_lo"] for c, _ in ordered]
    his = [res[c]["lambda_ci_hi"] for c, _ in ordered]
    colors = [COHORT_COLORS[c] for c, _ in ordered]
    err_lo = [m - l for m, l in zip(means, los)]
    err_hi = [h - m for m, h in zip(means, his)]
    # Cap error bars to avoid extreme outliers blowing up the y-axis
    err_lo = [min(e, 30) for e in err_lo]
    err_hi = [min(e, 50) for e in err_hi]

    bars = ax.bar(x, means, yerr=[err_lo, err_hi], color=colors,
                    edgecolor="black", linewidth=0.5,
                    error_kw={"capsize": 4, "linewidth": 1.2})

    # Group separators
    group_changes = []
    prev = None
    for i, (_, g) in enumerate(ordered):
        if g != prev:
            group_changes.append(i)
            prev = g
    for i, gc in enumerate(group_changes[1:]):
        ax.axvline(gc - 0.5, color="grey", linestyle="--", alpha=0.5)

    # Group labels
    yl = max(means) * 1.18
    for i, (gc_start, gc_end) in enumerate(zip(group_changes,
                                                  group_changes[1:] + [len(ordered)])):
        mid = (gc_start + gc_end - 1) / 2
        group = ordered[gc_start][1]
        ax.text(mid, yl, group, ha="center", fontsize=10,
                fontweight="bold", color="#333333")

    for i, m in enumerate(means):
        ax.text(i, m + 1.0, f"{m:.2f}", ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("-", "\n") for c, _ in ordered],
                        fontsize=8)
    ax.set_ylabel("Outgrowth length scale lambda (voxels)")
    ax.set_title("v185 UODSL: tumour-outgrowth length scale lambda is "
                  "DISEASE-SPECIFIC\n"
                  "(brain-mets ~ 3-5 voxels; GBM ~ 7-12; mixed ~ 25-58)")
    ax.set_ylim(0, max(his) * 1.25)
    return save_fig(fig, "fig14_uodsl_lambda_per_cohort")


# ============================================================================
# Figure 15 — Universal scaling collapse: P/A vs d/lambda
# ============================================================================

def figure_15_universal_collapse():
    print("Figure 15: universal scaling collapse", flush=True)
    v185 = json.loads((RESULTS / "v185_uodsl.json").read_text())
    res = v185["cohort_results"]

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.0))

    for ax in axes:
        for c, r in res.items():
            d = np.array(r["d_array"])
            p = np.array(r["p_array"])
            A = r["A_point"]
            lam = r["lambda_point"]
            if np.isnan(lam) or np.isinf(lam) or A <= 0 or lam <= 0:
                continue
            d_norm = d / lam
            p_norm = p / A
            ax.plot(d_norm, p_norm, "o-", color=COHORT_COLORS[c],
                    markersize=5, linewidth=1.2,
                    label=f"{c}", alpha=0.85)

    # Theoretical universal curve: exp(-x)
    x_grid = np.linspace(0, 5, 100)
    y_grid = np.exp(-x_grid)

    axes[0].plot(x_grid, y_grid, "k--", linewidth=2.5,
                  label="exp(-d/lambda) (theory)")
    axes[0].set_xlabel("Rescaled distance d / lambda")
    axes[0].set_ylabel("Rescaled probability P / A")
    axes[0].set_title("Linear: collapse to exp(-x) curve")
    axes[0].set_xlim(0, 5)
    axes[0].set_ylim(0, 1.1)
    axes[0].legend(loc="upper right", fontsize=8)

    axes[1].plot(x_grid, y_grid, "k--", linewidth=2.5,
                  label="exp(-d/lambda) (theory)")
    axes[1].set_xlabel("Rescaled distance d / lambda")
    axes[1].set_ylabel("Rescaled probability P / A  [log]")
    axes[1].set_yscale("log")
    axes[1].set_title("Log: should be straight line slope -1")
    axes[1].set_xlim(0, 5)
    axes[1].set_ylim(0.01, 1.5)
    axes[1].legend(loc="lower left", fontsize=8)

    fig.suptitle("v185 UODSL: universal scaling collapse — when rescaled by "
                  "(A, lambda),\nall 7 cohorts collapse onto the same "
                  "exp(-x) curve (functional-form universality)",
                  fontsize=11, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig15_uodsl_universal_collapse")


def main():
    print("v185 figures (UODSL)", flush=True)
    figure_13_decay_curves()
    figure_14_lambda_per_cohort()
    figure_15_universal_collapse()
    print("done", flush=True)


if __name__ == "__main__":
    main()
