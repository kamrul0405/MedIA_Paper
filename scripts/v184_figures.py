"""v184_figures: Clinical-readiness figures for round 22.

Generates:
  Fig 9: Cross-cohort Dice + AUC bar chart with 95% CIs
  Fig 10: Cross-cohort ROC curves (7-cohort overlay)
  Fig 11: Cross-cohort calibration reliability diagrams (7-panel grid)
  Fig 12: Per-patient AUC violin plot across 7 cohorts

Saves to MedIA_Paper/figures/ and RTO_paper/figures/.
"""
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
    "grid.linestyle": "--",
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})

COHORT_COLORS = {
    "UCSF-POSTOP":         "#0072B2",
    "MU-Glioma-Post":      "#E69F00",
    "RHUH-GBM":            "#009E73",
    "LUMIERE":             "#CC79A7",
    "PROTEAS-brain-mets":  "#D55E00",
    "UPENN-GBM":           "#56B4E9",
    "Yale-Brain-Mets":     "#000000",
}
COHORT_ORDER = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
                "PROTEAS-brain-mets", "UPENN-GBM", "Yale-Brain-Mets"]


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
# Figure 9 — Cross-cohort Dice + AUC bar chart with 95% CIs
# ============================================================================

def figure_9_dice_auc_bars():
    print("Figure 9: cross-cohort Dice + AUC bar chart", flush=True)
    v184 = json.loads((RESULTS / "v184_clinical_readiness.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.5))

    cohorts_present = [c for c in COHORT_ORDER
                       if c in v184["cohort_summaries"]]
    x = np.arange(len(cohorts_present))
    colors = [COHORT_COLORS[c] for c in cohorts_present]

    # Dice panel
    means = [v184["cohort_summaries"][c]["dice_mean"]
             for c in cohorts_present]
    lo = [v184["cohort_summaries"][c]["dice_ci_lo"]
          for c in cohorts_present]
    hi = [v184["cohort_summaries"][c]["dice_ci_hi"]
          for c in cohorts_present]
    err_lo = [m - l for m, l in zip(means, lo)]
    err_hi = [h - m for m, h in zip(means, hi)]
    axes[0].bar(x, means, yerr=[err_lo, err_hi], color=colors,
                  edgecolor="black", linewidth=0.5,
                  error_kw={"capsize": 4, "linewidth": 1.2})
    for i, m in enumerate(means):
        axes[0].text(i, m + 0.02, f"{m:.3f}", ha="center", fontsize=8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([c.replace("-", "\n") for c in cohorts_present],
                              rotation=0, fontsize=8)
    axes[0].set_ylabel("Dice score (mean +/- 95% bootstrap CI)")
    axes[0].set_title("v184: Per-patient Dice score on outgrowth region "
                        "(LOCO + zero-shot)")
    axes[0].set_ylim(0, max(hi) * 1.15)

    # AUC panel
    auc_means = [v184["cohort_summaries"][c]["auc_mean"]
                 for c in cohorts_present]
    auc_lo = [v184["cohort_summaries"][c]["auc_ci_lo"]
              for c in cohorts_present]
    auc_hi = [v184["cohort_summaries"][c]["auc_ci_hi"]
              for c in cohorts_present]
    auc_err_lo = [m - l for m, l in zip(auc_means, auc_lo)]
    auc_err_hi = [h - m for m, h in zip(auc_means, auc_hi)]
    axes[1].bar(x, auc_means, yerr=[auc_err_lo, auc_err_hi], color=colors,
                  edgecolor="black", linewidth=0.5,
                  error_kw={"capsize": 4, "linewidth": 1.2})
    for i, m in enumerate(auc_means):
        axes[1].text(i, m + 0.02, f"{m:.3f}", ha="center", fontsize=8)
    axes[1].axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                     label="Chance (AUC = 0.5)")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([c.replace("-", "\n") for c in cohorts_present],
                              rotation=0, fontsize=8)
    axes[1].set_ylabel("Patient-level AUC (mean +/- 95% bootstrap CI)")
    axes[1].set_title("v184: Per-patient outgrowth-detection AUC across "
                        "7 cohorts")
    axes[1].set_ylim(0.4, 1.0)
    axes[1].legend(loc="lower right", fontsize=9)

    fig.suptitle("Cross-cohort clinical-readiness: AUC > 0.67 across all 7 "
                  "cohorts; Yale (zero-shot) AUC = 0.835",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig09_dice_auc_per_cohort")


# ============================================================================
# Figure 10 — Cross-cohort ROC curves
# ============================================================================

def figure_10_roc_curves():
    print("Figure 10: cross-cohort ROC curves", flush=True)
    v184 = json.loads((RESULTS / "v184_clinical_readiness.json").read_text())
    fig, ax = plt.subplots(figsize=(7.5, 7.0))

    for c in COHORT_ORDER:
        if c not in v184["cohort_pooled_voxels_truncated_5k"]:
            continue
        probs, targets = v184["cohort_pooled_voxels_truncated_5k"][c]
        if not probs:
            continue
        probs = np.array(probs, dtype=np.float32)
        targets = np.array(targets, dtype=np.float32)
        if (targets == targets[0]).all():
            continue
        order = np.argsort(-probs)
        y = targets[order]
        n_pos = int(y.sum())
        n_neg = len(y) - n_pos
        if n_pos == 0 or n_neg == 0:
            continue
        cum_pos = np.cumsum(y)
        fpr = (np.arange(1, len(y) + 1) - cum_pos) / n_neg
        tpr = cum_pos / n_pos
        # prepend 0
        fpr = np.concatenate([[0.0], fpr])
        tpr = np.concatenate([[0.0], tpr])
        if hasattr(np, "trapezoid"):
            auc = float(np.trapezoid(tpr, fpr))
        else:
            auc = float(np.trapz(tpr, fpr))
        if auc < 0.5:
            auc = 1.0 - auc
        auc_summary = v184["cohort_summaries"][c]["auc_mean"]
        ax.plot(fpr, tpr, color=COHORT_COLORS[c], linewidth=1.8,
                  label=f"{c} (n={v184['cohort_summaries'][c]['n_patients']}, "
                        f"AUC={auc_summary:.3f})")

    ax.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Chance")
    ax.set_xlabel("False positive rate (voxel-level)")
    ax.set_ylabel("True positive rate (voxel-level)")
    ax.set_title("v184: Voxel-level ROC curves across 7 cohorts\n"
                  "(pooled outside-baseline-mask voxels, truncated to 5k/cohort)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", fontsize=8)
    return save_fig(fig, "fig10_roc_curves_7cohort")


# ============================================================================
# Figure 11 — Calibration reliability diagrams (7-panel)
# ============================================================================

def figure_11_calibration_grid():
    print("Figure 11: calibration reliability diagrams 7-panel", flush=True)
    v184 = json.loads((RESULTS / "v184_clinical_readiness.json").read_text())
    cohorts_present = [c for c in COHORT_ORDER
                       if c in v184["cohort_summaries"]]
    n = len(cohorts_present)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(13.0, 3.0 * rows))
    axes = np.array(axes).flatten() if n > 1 else [axes]

    for i, c in enumerate(cohorts_present):
        ax = axes[i]
        bins = v184["cohort_summaries"][c]["calibration_bins"]
        ece = v184["cohort_summaries"][c]["ece"]
        mids = [(b["bin_lo"] + b["bin_hi"]) / 2 for b in bins]
        accs = [b["acc"] for b in bins]
        ns = [b["n"] for b in bins]
        # bar widths proportional to bin size
        max_n = max(ns) if max(ns) > 0 else 1
        widths = [0.08 + 0.02 * (b["n"] / max_n) for b in bins]

        # bar = empirical accuracy in each bin
        ax.bar(mids, accs, width=widths, alpha=0.6,
                color=COHORT_COLORS[c], edgecolor="black",
                linewidth=0.5)
        ax.plot([0, 1], [0, 1], "k--", alpha=0.5, linewidth=1,
                  label="Perfect calibration")

        ax.set_title(f"{c}\nECE = {ece:.3f}", fontsize=10)
        ax.set_xlabel("Predicted probability")
        ax.set_ylabel("Empirical fraction outgrowth")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")

    for j in range(n, len(axes)):
        axes[j].axis("off")

    fig.suptitle("v184: Calibration reliability diagrams across 7 cohorts "
                  "(voxel-level, ECE = Expected Calibration Error)",
                  fontsize=11, y=1.01)
    fig.tight_layout()
    return save_fig(fig, "fig11_calibration_reliability_grid")


# ============================================================================
# Figure 12 — Per-patient AUC violin plot
# ============================================================================

def figure_12_per_patient_auc_violin():
    print("Figure 12: per-patient AUC violin", flush=True)
    csv_path = RESULTS / "v184_clinical_readiness_per_patient.csv"
    if not csv_path.exists():
        return []
    by_cohort = {c: [] for c in COHORT_ORDER}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = row.get("cohort", "")
            if c not in by_cohort:
                continue
            try:
                v = float(row["auc_ensemble"])
            except (ValueError, TypeError):
                continue
            if np.isnan(v):
                continue
            by_cohort[c].append(v)

    cohorts_present = [c for c in COHORT_ORDER if by_cohort[c]]
    fig, ax = plt.subplots(figsize=(11.0, 5.0))
    data = [by_cohort[c] for c in cohorts_present]
    colors = [COHORT_COLORS[c] for c in cohorts_present]

    parts = ax.violinplot(data, positions=range(len(cohorts_present)),
                           widths=0.85, showmeans=True, showmedians=True)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.55)
        pc.set_edgecolor("black")
    parts["cmeans"].set_color("black")
    parts["cmeans"].set_linewidth(2.0)
    parts["cmedians"].set_color("#D55E00")

    rng = np.random.default_rng(0)
    for i, vals in enumerate(data):
        x_jit = rng.uniform(-0.07, 0.07, size=len(vals)) + i
        ax.scatter(x_jit, vals, alpha=0.5, s=10, color="black")

    for i, (c, vals) in enumerate(zip(cohorts_present, data)):
        m = np.mean(vals)
        ax.text(i, 1.04, f"{m:.3f}\n(n={len(vals)})",
                ha="center", fontsize=8)

    ax.axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                label="Chance (AUC = 0.5)")
    ax.set_xticks(range(len(cohorts_present)))
    ax.set_xticklabels([c.replace("-", "\n") for c in cohorts_present],
                        fontsize=9)
    ax.set_ylabel("Per-patient outgrowth-detection AUC (voxel-level)")
    ax.set_title("v184: Per-patient AUC distribution across 7 cohorts")
    ax.set_ylim(0.0, 1.10)
    ax.legend(loc="lower right", fontsize=9)
    return save_fig(fig, "fig12_per_patient_auc_violin")


def main():
    print("v184 figures (rebuilding)", flush=True)
    figure_9_dice_auc_bars()
    figure_10_roc_curves()
    figure_11_calibration_grid()
    figure_12_per_patient_auc_violin()
    print("done", flush=True)


if __name__ == "__main__":
    main()
