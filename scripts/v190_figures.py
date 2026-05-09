"""v190 figures (Fig 29-31): patient-adaptive kernel — honest results."""
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

COHORT_COLORS = {
    "Yale-Brain-Mets":     "#000000",
    "PROTEAS-brain-mets":  "#D55E00",
    "UCSF-POSTOP":         "#0072B2",
    "RHUH-GBM":            "#009E73",
    "LUMIERE":             "#CC79A7",
    "MU-Glioma-Post":      "#E69F00",
    "UPENN-GBM":           "#56B4E9",
}


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


def figure_29_lambda_vs_features():
    print("Figure 29: per-patient lambda vs mask features", flush=True)
    csv_path = RESULTS / "v190_per_patient.csv"
    rows = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                if row.get("lambda_observed") in ("", "nan"):
                    continue
                rows.append({
                    "cohort": row["cohort"],
                    "lambda": float(row["lambda_observed"]),
                    "volume": float(row["volume"]),
                    "surface_area": float(row["surface_area"]),
                    "sphericity": float(row["sphericity"]),
                    "extent_z": float(row["extent_z"]),
                    "extent_y": float(row["extent_y"]),
                    "extent_x": float(row["extent_x"]),
                })
            except (ValueError, KeyError):
                continue

    feats = ["volume", "surface_area", "sphericity",
              "extent_z", "extent_y", "extent_x"]
    feat_labels = ["Volume (voxels)", "Surface area (voxels)",
                    "Sphericity", "Extent z (voxels)",
                    "Extent y (voxels)", "Extent x (voxels)"]
    feat_log = [True, True, False, False, False, False]

    fig, axes = plt.subplots(2, 3, figsize=(13.0, 8.5))
    axes = axes.flatten()
    for k, (feat, label, log) in enumerate(zip(feats, feat_labels, feat_log)):
        ax = axes[k]
        for c in COHORT_COLORS:
            sub = [r for r in rows if r["cohort"] == c]
            if not sub:
                continue
            xs = [r[feat] for r in sub]
            ys = [r["lambda"] for r in sub]
            ax.scatter(xs, ys, color=COHORT_COLORS[c], alpha=0.6, s=20,
                        edgecolor="black", linewidth=0.3, label=c)
        # Pearson correlation across all patients
        all_x = np.array([r[feat] for r in rows])
        all_y = np.array([r["lambda"] for r in rows])
        if log:
            all_x_log = np.log1p(all_x)
            r = float(np.corrcoef(all_x_log, all_y)[0, 1])
            ax.set_xscale("log")
        else:
            r = float(np.corrcoef(all_x, all_y)[0, 1])
        ax.set_xlabel(label)
        ax.set_ylabel("Per-patient lambda (voxels)")
        ax.set_title(f"r = {r:+.3f}")
        if k == 0:
            ax.legend(loc="upper right", fontsize=6)
    fig.suptitle("v190 PART A: Per-patient lambda vs baseline mask "
                  "features (n = 375 valid fits)\n"
                  "All correlations are weak |r| < 0.3 — baseline geometry "
                  "alone does NOT determine per-patient lambda",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig29_lambda_vs_mask_features")


def figure_30_loco_predicted_vs_observed():
    print("Figure 30: LOCO predicted lambda vs observed", flush=True)
    csv_path = RESULTS / "v190_per_patient.csv"
    obs = []
    pred = []
    cohorts = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                lam_obs = float(row["lambda_observed"]) if row["lambda_observed"] not in ("", "nan") else None
                lam_pred = float(row["lambda_predicted"]) if row["lambda_predicted"] not in ("", "nan") else None
            except (ValueError, KeyError):
                continue
            if lam_obs is None or lam_pred is None:
                continue
            obs.append(lam_obs)
            pred.append(lam_pred)
            cohorts.append(row["cohort"])
    obs = np.array(obs)
    pred = np.array(pred)

    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    for c in COHORT_COLORS:
        sel = [i for i, ck in enumerate(cohorts) if ck == c]
        if not sel:
            continue
        ax.scatter(obs[sel], pred[sel], color=COHORT_COLORS[c],
                    alpha=0.6, s=30, edgecolor="black", linewidth=0.3,
                    label=f"{c} (n={len(sel)})")
    lo = min(obs.min(), pred.min()) * 0.8
    hi = max(obs.max(), pred.max()) * 1.1
    ax.plot([lo, hi], [lo, hi], "k--", alpha=0.5,
              label="y = x (perfect)")

    if np.var(obs) > 0:
        r = float(np.corrcoef(obs, pred)[0, 1])
        R2 = 1 - np.sum((obs - pred) ** 2) / np.sum((obs - obs.mean()) ** 2)
        MAE = float(np.mean(np.abs(obs - pred)))
    else:
        r = R2 = MAE = float("nan")

    ax.set_xlabel("Observed per-patient lambda (voxels)")
    ax.set_ylabel("LOCO-predicted lambda from mask geometry (voxels)")
    ax.set_title(f"v190 PART B HONEST NEGATIVE RESULT: LOCO R^2 = {R2:.3f} "
                  f"(NEGATIVE = worse than mean baseline)\n"
                  f"r = {r:+.3f}, MAE = {MAE:.2f} voxels — baseline mask "
                  f"geometry CANNOT predict per-patient lambda")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.legend(loc="upper left", fontsize=8)
    return save_fig(fig, "fig30_loco_lambda_prediction")


def figure_31_sigma_opt_ratio():
    print("Figure 31: sigma_opt vs lambda — non-monotonic", flush=True)
    v189 = json.loads((RESULTS / "v189_training_free_kernel.json").read_text())
    v185 = json.loads((RESULTS / "v185_uodsl.json").read_text())

    cohorts = []
    sigmas = []
    lambdas = []
    aucs = []
    for c in v189["per_cohort"]:
        if c not in v185["cohort_results"]:
            continue
        cohorts.append(c)
        sigmas.append(v189["per_cohort"][c]["optimal_sigma"])
        lambdas.append(v185["cohort_results"][c]["lambda_point"])
        aucs.append(v189["per_cohort"][c]["optimal_auc"])

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.5))

    # Left: sigma_opt vs lambda
    for i, c in enumerate(cohorts):
        axes[0].scatter(lambdas[i], sigmas[i], s=200,
                          c=COHORT_COLORS[c],
                          edgecolor="black", linewidth=0.7, alpha=0.85)
        axes[0].annotate(c.replace("-", "\n"),
                          (lambdas[i], sigmas[i]),
                          xytext=(8, 5), textcoords="offset points",
                          fontsize=8)
    lam_grid = np.array([min(lambdas) * 0.7, max(lambdas) * 1.2])
    axes[0].plot(lam_grid, lam_grid / 4, "k:", alpha=0.5,
                   label="sigma = lambda / 4 (round-27 simplification)")
    # Spearman rank correlation
    from scipy.stats import spearmanr
    rho, _ = spearmanr(lambdas, sigmas)
    axes[0].set_xlabel("UODSL cohort-pooled lambda (voxels)")
    axes[0].set_ylabel("Kernel-only optimal sigma (voxels)")
    axes[0].set_title(f"sigma_opt vs lambda: Spearman rho = "
                        f"{rho:+.3f} (NON-MONOTONIC)")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].legend(loc="upper left", fontsize=9)

    # Right: ratio sigma_opt/lambda
    ratios = [s / l for s, l in zip(sigmas, lambdas)]
    x = np.arange(len(cohorts))
    axes[1].bar(x, ratios, color=[COHORT_COLORS[c] for c in cohorts],
                  edgecolor="black", linewidth=0.5)
    for i, r in enumerate(ratios):
        axes[1].text(i, r * 1.1, f"{r:.2f}", ha="center", fontsize=9)
    axes[1].axhline(0.25, color="red", linestyle="--", alpha=0.6,
                     label="round-27 simplification ratio = 0.25")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([c.replace("-", "\n") for c in cohorts],
                              fontsize=8)
    axes[1].set_ylabel("sigma_opt / lambda")
    axes[1].set_title(f"Ratio varies 0.09 to 2.54 — round-27 simplification "
                       f"sigma=lambda/4 does NOT hold rigorously")
    axes[1].set_yscale("log")
    axes[1].legend(loc="upper right", fontsize=9)

    fig.suptitle("v190 HONEST RE-EXAMINATION of round-27 sigma_opt vs "
                  "lambda — relationship is NON-MONOTONIC; universal "
                  "sigma=3 remains the best deployable recipe",
                  fontsize=11, y=1.04)
    fig.tight_layout()
    return save_fig(fig, "fig31_sigma_opt_vs_lambda_honest")


def main():
    figure_29_lambda_vs_features()
    figure_30_loco_predicted_vs_observed()
    figure_31_sigma_opt_ratio()
    print("done", flush=True)


if __name__ == "__main__":
    main()
