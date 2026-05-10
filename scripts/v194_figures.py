"""v194 figures (Fig 39-40): kernel -> survival HONEST NEGATIVE."""
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


def kaplan_meier(times, events):
    """Return (t, S(t)) Kaplan-Meier survival curve."""
    order = np.argsort(times)
    t = np.array(times)[order]
    e = np.array(events)[order]
    n = len(t)
    n_at_risk = n
    S = 1.0
    out_t = [0.0]
    out_S = [1.0]
    for i in range(n):
        if e[i] == 1:
            S *= 1 - 1.0 / n_at_risk
            out_t.append(t[i])
            out_S.append(S)
        n_at_risk -= 1
    out_t.append(t[-1] * 1.05)
    out_S.append(S)
    return np.array(out_t), np.array(out_S)


def figure_39_kaplan_meier():
    print("Figure 39: KM curves median-split by V_kernel sigma=3", flush=True)
    csv_path = RESULTS / "v194_kernel_survival_per_patient.csv"
    rows = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                os_d = float(row["OS_days"])
                event = int(row["event"])
                v_k = float(row["V_kernel_sigma3"])
            except (ValueError, KeyError):
                continue
            rows.append({"OS": os_d, "event": event, "V": v_k})

    v = np.array([r["V"] for r in rows])
    median = float(np.median(v))
    high = [r for r in rows if r["V"] > median]
    low = [r for r in rows if r["V"] <= median]

    fig, ax = plt.subplots(figsize=(9.0, 6.5))
    t_h, S_h = kaplan_meier([r["OS"] for r in high],
                              [r["event"] for r in high])
    t_l, S_l = kaplan_meier([r["OS"] for r in low],
                              [r["event"] for r in low])

    ax.step(t_h, S_h, where="post", color="#D55E00", linewidth=2,
              label=f"High V_kernel (n={len(high)}, median {np.median([r['OS'] for r in high]):.0f}d)")
    ax.step(t_l, S_l, where="post", color="#0072B2", linewidth=2,
              label=f"Low V_kernel (n={len(low)}, median {np.median([r['OS'] for r in low]):.0f}d)")

    ax.set_xlabel("Days from baseline")
    ax.set_ylabel("Survival probability")
    ax.set_title(f"v194 HONEST NEGATIVE: Kaplan-Meier curves stratified by\n"
                  f"V_kernel σ=3 median split (RHUH-GBM, n={len(rows)})\n"
                  f"Log-rank χ² = 0.043, p = 0.83 — NO SEPARATION")
    ax.legend(loc="upper right", fontsize=10)
    ax.set_ylim(0, 1.05)
    return save_fig(fig, "fig39_kaplan_meier_kernel_split")


def figure_40_correlation_scatter():
    print("Figure 40: V_kernel vs OS scatter", flush=True)
    csv_path = RESULTS / "v194_kernel_survival_per_patient.csv"
    rows = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "OS": float(row["OS_days"]),
                    "PFS": float(row["PFS_days"]) if row["PFS_days"] else None,
                    "event": int(row["event"]),
                    "V_s1": float(row["V_kernel_sigma1"]),
                    "V_s3": float(row["V_kernel_sigma3"]),
                    "V_s7": float(row["V_kernel_sigma7"]),
                    "V_s15": float(row["V_kernel_sigma15"]),
                    "BV": float(row["baseline_mask_volume"]),
                })
            except (ValueError, KeyError):
                continue

    fig, axes = plt.subplots(2, 3, figsize=(14.0, 8.5))

    for ax, key, label in zip(axes.flatten(),
                                  ["BV", "V_s1", "V_s3", "V_s7", "V_s15"],
                                  ["Baseline mask volume",
                                   "V_kernel σ=1", "V_kernel σ=3",
                                   "V_kernel σ=7", "V_kernel σ=15"]):
        xs = np.array([r[key] for r in rows])
        ys = np.array([r["OS"] for r in rows])
        events = np.array([r["event"] for r in rows])
        # Color by event
        colors = ["#D55E00" if e == 1 else "#0072B2" for e in events]
        ax.scatter(xs, ys, c=colors, s=50, alpha=0.7,
                    edgecolor="black", linewidth=0.4)
        from scipy.stats import spearmanr
        rho, p = spearmanr(xs, ys)
        ax.set_xlabel(label + " (voxels)")
        ax.set_ylabel("Overall survival (days)")
        ax.set_title(f"{label}: Spearman rho = {rho:+.3f}, p = {p:.3f}")
        ax.set_xscale("symlog")

    # last panel: legend for event
    axes[1, 2].axis("off")
    axes[1, 2].text(0.05, 0.7, "Color legend:", fontsize=11, fontweight="bold")
    axes[1, 2].scatter([0.1], [0.55], c="#D55E00", s=80, edgecolor="black")
    axes[1, 2].text(0.18, 0.55, "Event = 1 (deceased)", fontsize=10)
    axes[1, 2].scatter([0.1], [0.45], c="#0072B2", s=80, edgecolor="black")
    axes[1, 2].text(0.18, 0.45, "Event = 0 (right-censored)", fontsize=10)
    axes[1, 2].text(0.05, 0.30, "All Spearman p-values > 0.5",
                       fontsize=10, color="red")
    axes[1, 2].text(0.05, 0.20, "Kernel volume does NOT predict OS",
                       fontsize=10, color="red", fontweight="bold")
    axes[1, 2].set_xlim(0, 1)
    axes[1, 2].set_ylim(0, 1)

    fig.suptitle("v194 HONEST NEGATIVE: kernel-predicted outgrowth volume "
                  "does NOT correlate with OS in RHUH-GBM (n=39)\n"
                  "Confirms the kernel measures spatial extent, NOT "
                  "biological aggressiveness",
                  fontsize=11, y=1.00)
    fig.tight_layout()
    return save_fig(fig, "fig40_kernel_vs_OS_scatter")


def main():
    figure_39_kaplan_meier()
    figure_40_correlation_scatter()
    print("done", flush=True)


if __name__ == "__main__":
    main()
