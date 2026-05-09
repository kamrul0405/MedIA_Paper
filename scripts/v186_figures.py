"""v186 confirmation figures (Fig 16-19) — round 24."""
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

ALL_COHORTS = ["Yale-Brain-Mets", "PROTEAS-brain-mets", "UCSF-POSTOP",
               "RHUH-GBM", "UPENN-GBM", "LUMIERE", "MU-Glioma-Post"]
DISEASE_GROUP = {
    "Yale-Brain-Mets":     "Brain-mets",
    "PROTEAS-brain-mets":  "Brain-mets",
    "UCSF-POSTOP":         "GBM",
    "RHUH-GBM":            "GBM",
    "LUMIERE":             "Mixed",
    "MU-Glioma-Post":      "Mixed",
    "UPENN-GBM":           "Mixed",
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
GROUP_COLORS = {"Brain-mets": "#D55E00", "GBM": "#0072B2", "Mixed": "#CC79A7"}


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
# Figure 16: Per-patient lambda violin per cohort
# ============================================================================

def figure_16_per_patient_lambda():
    print("Figure 16: per-patient lambda violin", flush=True)
    csv_path = RESULTS / "v186_uodsl_per_patient.csv"
    by_cohort = {c: [] for c in ALL_COHORTS}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            c = row.get("cohort")
            if c not in by_cohort:
                continue
            if row.get("valid_fit") != "True":
                continue
            try:
                lam = float(row["lambda"])
            except (ValueError, TypeError):
                continue
            if 0 < lam < 200:
                by_cohort[c].append(lam)

    fig, ax = plt.subplots(figsize=(11.0, 5.5))
    cohorts_present = [c for c in ALL_COHORTS if by_cohort[c]]
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
        ax.scatter(x_jit, vals, alpha=0.45, s=12, color="black")

    for i, (c, vals) in enumerate(zip(cohorts_present, data)):
        m = np.median(vals)
        ax.text(i, np.percentile(vals, 95) + 1, f"med {m:.2f}\n(n={len(vals)})",
                ha="center", fontsize=8)

    # Cohort-pooled overlay (red dashes)
    cohort_pooled = {
        "UCSF-POSTOP": 7.45, "MU-Glioma-Post": 58.43, "RHUH-GBM": 11.82,
        "LUMIERE": 25.0, "PROTEAS-brain-mets": 4.59, "UPENN-GBM": 23.86,
        "Yale-Brain-Mets": 3.51,
    }
    for i, c in enumerate(cohorts_present):
        if c in cohort_pooled:
            ax.plot([i - 0.35, i + 0.35],
                    [cohort_pooled[c], cohort_pooled[c]],
                    color="red", linewidth=2.5, zorder=10,
                    label="Cohort-pooled (round 23)" if i == 0 else None)

    ax.set_xticks(range(len(cohorts_present)))
    ax.set_xticklabels([c.replace("-", "\n") for c in cohorts_present],
                        fontsize=9)
    ax.set_ylabel("Per-patient lambda (voxels)")
    ax.set_title("v186: Per-patient lambda (R^2 > 0.5 quality fits) is "
                  "SYSTEMATICALLY SMALLER than cohort-pooled lambda\n"
                  "(red dashes = round-23 cohort-pooled; violin = per-patient "
                  "valid fits)")
    ax.set_ylim(0, 70)
    ax.legend(loc="upper right", fontsize=9)
    return save_fig(fig, "fig16_per_patient_lambda_violin")


# ============================================================================
# Figure 17: Bin-sensitivity comparison
# ============================================================================

def figure_17_bin_sensitivity():
    print("Figure 17: bin-sensitivity", flush=True)
    v186 = json.loads((RESULTS / "v186_uodsl_confirmation.json").read_text())
    bin_lams = v186["test_2_bin_sensitivity"]["lambda_per_cohort_per_strategy"]

    cohorts_present = list(bin_lams.keys())
    strategies = list(next(iter(bin_lams.values())).keys())

    x = np.arange(len(cohorts_present))
    width = 0.27
    fig, ax = plt.subplots(figsize=(13.0, 5.5))
    strat_colors = ["#0072B2", "#E69F00", "#009E73"]

    for i, strat in enumerate(strategies):
        vals = [bin_lams[c][strat] for c in cohorts_present]
        ax.bar(x + (i - 1) * width, vals, width=width,
                label=strat, color=strat_colors[i],
                edgecolor="black", linewidth=0.5)

    cv = v186["test_2_bin_sensitivity"]["lambda_cv_across_strategies"]
    for i, c in enumerate(cohorts_present):
        ax.text(i, max(bin_lams[c][s] for s in strategies) + 2,
                f"CV={cv[c]:.2f}", ha="center", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("-", "\n") for c in cohorts_present],
                        fontsize=9)
    ax.set_ylabel("Cohort-pooled lambda (voxels)")
    ax.set_title("v186 Test 2: lambda is robust across distance-binning "
                  "strategies (CV across strategies = 3-15%)")
    ax.legend(title="Bin strategy", loc="upper left", fontsize=9)
    return save_fig(fig, "fig17_bin_sensitivity")


# ============================================================================
# Figure 18: Theory vs empirical lambda
# ============================================================================

def figure_18_theory_vs_empirical():
    print("Figure 18: theory vs empirical lambda", flush=True)
    v186 = json.loads((RESULTS / "v186_uodsl_confirmation.json").read_text())
    cohort_means = v186["test_1_per_patient_lambda"]["median_lambda_per_cohort"]
    theory = v186["test_4_theory_vs_empirical"]
    cohort_pooled = {
        "UCSF-POSTOP": 7.45, "MU-Glioma-Post": 58.43, "RHUH-GBM": 11.82,
        "LUMIERE": 25.0, "PROTEAS-brain-mets": 4.59, "UPENN-GBM": 23.86,
        "Yale-Brain-Mets": 3.51,
    }
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0))
    sigma = theory["sigma_kernel"]

    # Left: theory predictions (3 lines for tau values)
    tau_grid = np.linspace(0.05, 10, 200)
    lam_theory = sigma * np.sqrt(tau_grid)
    axes[0].plot(tau_grid, lam_theory, "k-", linewidth=2,
                  label="Theory: lambda = sigma * sqrt(tau)")
    axes[0].axhline(theory["lambda_theory_tau_0p3_brain_mets"],
                     color="#D55E00", linestyle=":", linewidth=1,
                     label=f"tau=0.3 -> {theory['lambda_theory_tau_0p3_brain_mets']:.2f}")
    axes[0].axhline(theory["lambda_theory_tau_1_GBM"],
                     color="#0072B2", linestyle=":", linewidth=1,
                     label=f"tau=1 -> {theory['lambda_theory_tau_1_GBM']:.2f}")
    axes[0].axhline(theory["lambda_theory_tau_8_heterogeneous"],
                     color="#CC79A7", linestyle=":", linewidth=1,
                     label=f"tau=8 -> {theory['lambda_theory_tau_8_heterogeneous']:.2f}")
    axes[0].set_xlabel("Effective diffusion time tau (sigma^2/D units)")
    axes[0].set_ylabel("Theoretical lambda (voxels)")
    axes[0].set_title("Theory: Fisher-KPP / Darcy diffusion, sigma=7")
    axes[0].legend(loc="upper left", fontsize=9)
    axes[0].set_xscale("log")

    # Right: empirical vs theory scatter (cohort-pooled vs per-patient)
    cohorts = list(cohort_means.keys())
    x_pp = []  # per-patient median
    x_pl = []  # cohort-pooled
    labels = []
    colors = []
    for c in cohorts:
        x_pp.append(cohort_means[c])
        x_pl.append(cohort_pooled.get(c, 0))
        labels.append(c)
        colors.append(COHORT_COLORS[c])
    x_pp = np.array(x_pp)
    x_pl = np.array(x_pl)

    axes[1].scatter(x_pp, x_pl, s=120, c=colors, edgecolor="black",
                     linewidth=0.7, label="Cohort points (per-patient med vs pooled)")
    for i, lbl in enumerate(labels):
        axes[1].annotate(lbl.split("-")[0], (x_pp[i], x_pl[i]),
                         xytext=(5, 5), textcoords="offset points",
                         fontsize=7)
    lo = min(min(x_pp), min(x_pl)) - 1
    hi = max(max(x_pp), max(x_pl)) * 1.05
    axes[1].plot([lo, hi], [lo, hi], "k--", alpha=0.5,
                  label="y = x (consistency)")
    # 2x, 5x, 10x lines
    axes[1].plot([lo, hi], [lo * 2, hi * 2], color="grey", linestyle=":",
                  alpha=0.4, label="2x")
    axes[1].plot([lo, hi], [lo * 5, hi * 5], color="grey", linestyle=":",
                  alpha=0.3, label="5x")
    axes[1].set_xlabel("Per-patient median lambda (voxels)")
    axes[1].set_ylabel("Cohort-pooled lambda (voxels)")
    axes[1].set_title("Empirical: cohort-pooled lambda OVERESTIMATES "
                       "per-patient median by 2-10x")
    axes[1].set_xlim(0, hi)
    axes[1].set_ylim(0, hi)
    axes[1].legend(loc="upper left", fontsize=8)

    fig.suptitle("v186 Tests 1+4: theory matches cohort-pooled; per-patient "
                  "median is systematically smaller",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig18_theory_vs_empirical")


# ============================================================================
# Figure 19: Hold-out prediction confusion-matrix-style
# ============================================================================

def figure_19_holdout_prediction():
    print("Figure 19: hold-out prediction", flush=True)
    v186 = json.loads((RESULTS / "v186_uodsl_confirmation.json").read_text())
    rows = v186["test_5_holdout_prediction"]["rows"]
    mae = v186["test_5_holdout_prediction"]["mean_abs_error_voxels"]

    cohorts = [r["cohort"] for r in rows]
    obs = [r["observed_median_lambda"] for r in rows]
    pred = [r["predicted_median_lambda"] for r in rows]
    err = [r["abs_err_voxels"] for r in rows]
    groups = [r["disease_group"] for r in rows]
    colors = [GROUP_COLORS.get(g, "grey") for g in groups]

    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.0))

    # Left: observed vs predicted scatter
    axes[0].scatter(obs, pred, s=130, c=colors, edgecolor="black",
                     linewidth=0.7)
    for o, p, lbl in zip(obs, pred, cohorts):
        axes[0].annotate(lbl.split("-")[0], (o, p),
                          xytext=(5, 5), textcoords="offset points",
                          fontsize=8)
    lo = min(min(obs), min(pred)) - 1
    hi = max(max(obs), max(pred)) + 1
    axes[0].plot([lo, hi], [lo, hi], "k--", alpha=0.5, label="y = x (perfect)")
    # +/- 2 voxel band
    axes[0].fill_between([lo, hi], [lo - 2, hi - 2], [lo + 2, hi + 2],
                          alpha=0.1, color="grey", label="+/- 2 voxels")
    axes[0].set_xlabel("Observed per-patient median lambda (voxels)")
    axes[0].set_ylabel("Predicted lambda (from same-disease-group cohorts)")
    axes[0].set_title(f"v186 Test 5: hold-out prediction MAE = "
                       f"{mae:.2f} voxels")
    axes[0].set_xlim(lo, hi)
    axes[0].set_ylim(lo, hi)
    axes[0].legend(loc="upper left", fontsize=9)

    # Right: bar chart of per-cohort error
    x = np.arange(len(cohorts))
    axes[1].bar(x, err, color=colors, edgecolor="black", linewidth=0.5)
    for i, e in enumerate(err):
        axes[1].text(i, e + 0.1, f"{e:.2f}", ha="center", fontsize=9)
    axes[1].axhline(mae, color="red", linestyle="--",
                     label=f"Mean = {mae:.2f}")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([c.split("-")[0] for c in cohorts],
                              rotation=0, fontsize=9)
    axes[1].set_ylabel("Absolute error (voxels)")
    axes[1].set_title("Per-cohort hold-out error")
    axes[1].legend(fontsize=9)

    # Group-level legend
    handles = [plt.Rectangle((0, 0), 1, 1, color=GROUP_COLORS[g])
                for g in ["Brain-mets", "GBM", "Mixed"]]
    axes[0].legend(handles, ["Brain-mets", "GBM", "Mixed"],
                    loc="upper left", fontsize=9, title="Disease group")

    fig.tight_layout()
    return save_fig(fig, "fig19_holdout_prediction")


def main():
    print("v186 figures (UODSL confirmation suite)", flush=True)
    figure_16_per_patient_lambda()
    figure_17_bin_sensitivity()
    figure_18_theory_vs_empirical()
    figure_19_holdout_prediction()
    print("done", flush=True)


if __name__ == "__main__":
    main()
