"""v78_nature_upgrade_figures.py

Generate source-data-backed v78 figures for the corrected NMI/NBE story.

Outputs:
  04_figures/V78_NMI_raw_loco_stress.{png,tif}
  04_figures/V78_NBE_proteas_boundary.{png,tif}
  05_results/v78_nmi_raw_loco_source_data.csv
  05_results/v78_nbe_boundary_source_data.csv
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "05_results"
FIGS = ROOT / "04_figures"
FIGS.mkdir(parents=True, exist_ok=True)

NMI_JSON = RESULTS / "v78_raw_mri_loco.json"
NBE_JSON = RESULTS / "v78_proteas_boundary_stats.json"

NMI_SRC = RESULTS / "v78_nmi_raw_loco_source_data.csv"
NBE_SRC = RESULTS / "v78_nbe_boundary_source_data.csv"


COLORS = {
    "heat_prior_no_training": "#1b9e77",
    "mask_heat_sdf": "#7570b3",
    "raw4": "#d95f02",
    "raw4_mask": "#e7298a",
    "raw4_mask_heat_sdf": "#66a61e",
}
LABELS = {
    "heat_prior_no_training": "Heat prior",
    "mask_heat_sdf": "Mask+heat+SDF U-Net",
    "raw4": "Raw MRI U-Net",
    "raw4_mask": "Raw MRI+mask U-Net",
    "raw4_mask_heat_sdf": "Raw MRI+mask+heat+SDF U-Net",
}
COHORT_LABELS = {
    "UCSF-POSTOP": "UCSF",
    "MU-Glioma-Post": "MU",
    "RHUH-GBM": "RHUH",
    "UCSD-PTGBM": "UCSD",
}


def _save(fig, stem: str) -> None:
    fig.savefig(FIGS / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGS / f"{stem}.tif", dpi=300, bbox_inches="tight")
    plt.close(fig)


def nmi_figure() -> None:
    d = json.loads(NMI_JSON.read_text(encoding="utf-8"))
    rows = []
    delta_rows = []
    for cohort, res in d["loco_results"].items():
        pi = res["pi_stable_test"]
        winner = res["winner_by_brier"]
        for method, metrics in res["metrics"].items():
            rows.append({
                "cohort": cohort,
                "cohort_label": COHORT_LABELS.get(cohort, cohort),
                "pi_stable": pi,
                "method": method,
                "method_label": LABELS.get(method, method),
                "brier": metrics["brier_mean"],
                "ece": metrics["ece_mean"],
                "auroc": metrics["auroc_mean"],
                "winner_by_brier": winner,
            })
        for method, delta in res["paired_delta_vs_heat"].items():
            delta_rows.append({
                "cohort": cohort,
                "cohort_label": COHORT_LABELS.get(cohort, cohort),
                "method": method,
                "method_label": LABELS.get(method, method),
                "delta_mean": delta["mean"],
                "ci95_lo": delta["ci95_lo"],
                "ci95_hi": delta["ci95_hi"],
                "p_delta_lt_0": delta["p_delta_lt_0"],
            })
    df = pd.DataFrame(rows)
    delta_df = pd.DataFrame(delta_rows)
    df.to_csv(NMI_SRC, index=False)

    cohorts = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]
    methods = ["heat_prior_no_training", "mask_heat_sdf", "raw4", "raw4_mask", "raw4_mask_heat_sdf"]

    fig = plt.figure(figsize=(13.2, 7.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1.0], height_ratios=[1.0, 0.9], wspace=0.28, hspace=0.36)
    ax1 = fig.add_subplot(gs[:, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 1])

    x = np.arange(len(cohorts))
    width = 0.15
    offsets = np.linspace(-2, 2, len(methods)) * width
    for off, method in zip(offsets, methods):
        vals = [df[(df["cohort"].eq(c)) & (df["method"].eq(method))]["brier"].iloc[0] for c in cohorts]
        ax1.bar(x + off, vals, width=width, color=COLORS[method], label=LABELS[method], edgecolor="white", linewidth=0.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels([COHORT_LABELS[c] for c in cohorts])
    ax1.set_ylabel("Held-out Brier score")
    ax1.set_title("a  Raw-MRI access does not remove external ranking reversal", loc="left", fontweight="bold")
    ax1.legend(frameon=False, fontsize=8, ncol=1, loc="upper left")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", color="#dddddd", linewidth=0.6)

    delta_method = "raw4_mask"
    dsub = delta_df[delta_df["method"].eq(delta_method)].set_index("cohort").loc[cohorts].reset_index()
    y = np.arange(len(cohorts))
    ax2.axvline(0, color="#222222", linewidth=1)
    ax2.errorbar(
        dsub["delta_mean"], y,
        xerr=[dsub["delta_mean"] - dsub["ci95_lo"], dsub["ci95_hi"] - dsub["delta_mean"]],
        fmt="o", color=COLORS[delta_method], ecolor="#555555", capsize=3,
    )
    ax2.set_yticks(y)
    ax2.set_yticklabels([COHORT_LABELS[c] for c in cohorts])
    ax2.invert_yaxis()
    ax2.set_xlabel("Brier delta vs heat (model - heat)")
    ax2.set_title("b  Raw+mask external delta", loc="left", fontweight="bold")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="x", color="#dddddd", linewidth=0.6)

    best_rows = []
    for cohort in cohorts:
        sub = df[df["cohort"].eq(cohort)].copy()
        best = sub.sort_values("brier").iloc[0]
        best_rows.append(best)
    best = pd.DataFrame(best_rows)
    ax3.scatter(best["pi_stable"], best["brier"], s=110, c=[COLORS[m] for m in best["method"]], edgecolor="#222222", linewidth=0.7)
    for _, r in best.iterrows():
        ax3.text(r["pi_stable"] + 0.015, r["brier"], r["cohort_label"], va="center", fontsize=9)
    ax3.set_xlabel("Held-out stable-endpoint fraction")
    ax3.set_ylabel("Winner Brier")
    ax3.set_title("c  Endpoint composition is not the only axis", loc="left", fontweight="bold")
    ax3.set_xlim(0.15, 0.88)
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.grid(color="#dddddd", linewidth=0.6)

    _save(fig, "V78_NMI_raw_loco_stress")


def nbe_figure() -> None:
    d = json.loads(NBE_JSON.read_text(encoding="utf-8"))
    rows = []
    for metric, vals in d["clustered_means"].items():
        rows.append({"type": "mean", "metric": metric, **vals})
    for name, vals in d["paired_deltas"].items():
        rows.append({"type": "delta", "metric": name, **vals})
    for metric, vals in d["coverage_failure_rates"].items():
        row = {"type": "failure", "metric": metric}
        row.update(vals)
        rows.append(row)
    pd.DataFrame(rows).to_csv(NBE_SRC, index=False)

    means = d["clustered_means"]
    failures = d["coverage_failure_rates"]
    paired = d["paired_deltas"]

    coverage_metrics = [
        ("future_inside_dose95_pct", "Dose >=95% Rx"),
        ("future_inside_dose100_pct", "Dose >=100% Rx"),
        ("future_inside_heat80_pct", "Heat >=0.80"),
        ("future_inside_heat50_pct", "Heat >=0.50"),
    ]
    dose_metrics = [
        ("gtv_v95_pct", "Baseline GTV"),
        ("heat80_v95_pct", "Heat >=0.80"),
        ("heat50_v95_pct", "Heat >=0.50"),
    ]

    fig = plt.figure(figsize=(12.8, 6.8))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.9], wspace=0.32, hspace=0.42)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, :])

    x = np.arange(len(coverage_metrics))
    vals = [means[k]["mean"] for k, _ in coverage_metrics]
    lo = [means[k]["mean"] - means[k]["ci95_lo"] for k, _ in coverage_metrics]
    hi = [means[k]["ci95_hi"] - means[k]["mean"] for k, _ in coverage_metrics]
    ax1.bar(x, vals, color=["#4c78a8", "#4c78a8", "#f58518", "#f58518"], edgecolor="white", linewidth=0.6)
    ax1.errorbar(x, vals, yerr=[lo, hi], fmt="none", color="#222222", capsize=3)
    ax1.set_xticks(x)
    ax1.set_xticklabels([lab for _, lab in coverage_metrics], rotation=20, ha="right")
    ax1.set_ylabel("Future lesion covered (%)")
    ax1.set_title("a  Future-lesion coverage is incomplete", loc="left", fontweight="bold")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", color="#dddddd", linewidth=0.6)

    x2 = np.arange(len(dose_metrics))
    vals2 = [means[k]["mean"] for k, _ in dose_metrics]
    lo2 = [means[k]["mean"] - means[k]["ci95_lo"] for k, _ in dose_metrics]
    hi2 = [means[k]["ci95_hi"] - means[k]["mean"] for k, _ in dose_metrics]
    ax2.bar(x2, vals2, color=["#4c78a8", "#f58518", "#f58518"], edgecolor="white", linewidth=0.6)
    ax2.errorbar(x2, vals2, yerr=[lo2, hi2], fmt="none", color="#222222", capsize=3)
    ax2.set_xticks(x2)
    ax2.set_xticklabels([lab for _, lab in dose_metrics], rotation=20, ha="right")
    ax2.set_ylabel("Volume receiving >=95% Rx (%)")
    ax2.set_title("b  Heat regions track plan geometry, not benefit", loc="left", fontweight="bold")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.grid(axis="y", color="#dddddd", linewidth=0.6)

    metrics = [m for m, _ in coverage_metrics]
    y = np.arange(len(metrics))
    fail50 = [failures[m]["pct_rows_below_50"] for m in metrics]
    ax3.barh(y, fail50, color=["#4c78a8", "#4c78a8", "#f58518", "#f58518"], edgecolor="white", linewidth=0.6)
    ax3.set_yticks(y)
    ax3.set_yticklabels([lab for _, lab in coverage_metrics])
    ax3.set_xlabel("Follow-up rows with <50% future-lesion coverage (%)")
    ax3.set_title("c  Boundary failure rate at a clinically visible threshold", loc="left", fontweight="bold")
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.grid(axis="x", color="#dddddd", linewidth=0.6)
    note = paired["heat50_vs_heat80"]
    ax3.text(
        0.99, 0.08,
        f"Heat>=0.50 - Heat>=0.80: {note['mean_delta']:.1f} pp "
        f"(95% CI {note['ci95_lo']:.1f} to {note['ci95_hi']:.1f})",
        transform=ax3.transAxes, ha="right", va="bottom", fontsize=9,
    )

    _save(fig, "V78_NBE_proteas_boundary")


def main() -> None:
    nmi_figure()
    nbe_figure()
    print(f"Saved {FIGS / 'V78_NMI_raw_loco_stress.png'}")
    print(f"Saved {FIGS / 'V78_NBE_proteas_boundary.png'}")
    print(f"Saved {NMI_SRC}")
    print(f"Saved {NBE_SRC}")


if __name__ == "__main__":
    main()
