"""v197 figures (Fig 46-48): per-patient lambda -> survival."""
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


def figure_46_lambda_vs_OS():
    print("Figure 46: lambda vs OS scatter", flush=True)
    csv_path = RESULTS / "v197_lambda_survival_per_patient.csv"
    rows = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                if row["lambda_obs"] in ("", "None"):
                    continue
                rows.append({
                    "lam": float(row["lambda_obs"]),
                    "OS": float(row["os"]),
                    "event": int(row["event"]),
                    "pid": row["pid"],
                })
            except (ValueError, KeyError):
                continue

    fig, ax = plt.subplots(figsize=(9.0, 6.5))
    lams = np.array([r["lam"] for r in rows])
    os_d = np.array([r["OS"] for r in rows])
    events = np.array([r["event"] for r in rows])
    colors = ["#D55E00" if e == 1 else "#0072B2" for e in events]
    ax.scatter(lams, os_d, c=colors, s=120, alpha=0.75,
                edgecolor="black", linewidth=0.5)
    for r in rows:
        ax.annotate(r["pid"].replace("RHUH-", ""), (r["lam"], r["OS"]),
                     xytext=(5, 3), textcoords="offset points",
                     fontsize=7)
    from scipy.stats import spearmanr
    rho, p = spearmanr(lams, os_d)
    ax.set_xlabel("Per-patient UODSL λ (voxels)")
    ax.set_ylabel("Overall survival (days)")
    ax.set_title(f"v197: Per-patient λ vs OS (RHUH-GBM, n={len(rows)})\n"
                  f"Spearman rho = {rho:+.3f}, p = {p:.3f}")

    # legend
    ax.scatter([], [], c="#D55E00", s=80, edgecolor="black",
                label=f"Event=1 (deceased, n={int(events.sum())})")
    ax.scatter([], [], c="#0072B2", s=80, edgecolor="black",
                label=f"Event=0 (censored, n={int((1-events).sum())})")
    ax.legend(loc="upper right", fontsize=9)
    return save_fig(fig, "fig46_per_patient_lambda_vs_OS")


def figure_47_cindex_comparison():
    print("Figure 47: M0 vs M1 vs M2 C-index", flush=True)
    v197 = json.loads((RESULTS / "v197_lambda_survival.json").read_text())
    mc = v197["multivariate_cox"]

    fig, ax = plt.subplots(figsize=(10.0, 5.5))

    models = ["M0\nClinical only",
                "M1\nClinical + λ",
                "M2\nClinical + λ + V_kernel"]
    cs = [mc["M0_clinical_only_c_index"],
            mc["M1_clinical_plus_lambda_c_index"],
            mc["M2_clinical_plus_lambda_plus_kernel_c_index"]]
    colors = ["#999999", "#56B4E9", "#009E73"]
    bars = ax.bar(models, cs, color=colors, edgecolor="black",
                    linewidth=0.5)
    for i, c in enumerate(cs):
        ax.text(i, c + 0.01, f"{c:.4f}", ha="center", fontsize=11,
                fontweight="bold")
    ax.axhline(0.5, color="grey", linestyle="--", alpha=0.5,
                 label="C = 0.5 (chance)")

    # Annotate LRT p-values
    lrt01 = mc["LRT_M0_vs_M1"]["p_value"]
    lrt02 = mc["LRT_M0_vs_M2"]["p_value"]
    ax.text(1, 0.45, f"LRT vs M0: p = {lrt01:.3f}\n(NS)",
              ha="center", fontsize=10)
    ax.text(2, 0.45, f"LRT vs M0: p = {lrt02:.4f}\n(***SIGNIFICANT)",
              ha="center", fontsize=10, color="#009E73",
              fontweight="bold")

    ax.set_ylabel("Harrell's C-index")
    ax.set_title(f"v197 PRELIMINARY EVIDENCE: λ + V_kernel "
                  f"SYNERGISTICALLY improve clinical Cox (n={mc['n_complete_case']})\n"
                  f"M0 = 0.78; +λ alone = 0.80 (NS); "
                  f"+λ + V_kernel = 0.88 (LRT p = 0.0018)\n"
                  f"CAUTION: n={mc['n_complete_case']} is small — "
                  f"replication on larger cohorts needed")
    ax.set_ylim(0.4, 1.0)
    ax.legend(loc="lower right", fontsize=9)
    return save_fig(fig, "fig47_cindex_M0_M1_M2_comparison")


def figure_48_kaplan_meier_lambda_split():
    print("Figure 48: KM curves median-split by lambda", flush=True)
    csv_path = RESULTS / "v197_lambda_survival_per_patient.csv"
    rows = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                if row["lambda_obs"] in ("", "None"):
                    continue
                rows.append({
                    "lam": float(row["lambda_obs"]),
                    "OS": float(row["os"]),
                    "event": int(row["event"]),
                })
            except (ValueError, KeyError):
                continue

    lams = np.array([r["lam"] for r in rows])
    median = float(np.median(lams))
    high = [r for r in rows if r["lam"] > median]
    low = [r for r in rows if r["lam"] <= median]

    fig, ax = plt.subplots(figsize=(9.0, 6.5))
    t_h, S_h = kaplan_meier([r["OS"] for r in high],
                              [r["event"] for r in high])
    t_l, S_l = kaplan_meier([r["OS"] for r in low],
                              [r["event"] for r in low])

    ax.step(t_h, S_h, where="post", color="#D55E00", linewidth=2.5,
              label=f"High λ (n={len(high)}, median {np.median([r['OS'] for r in high]):.0f}d)")
    ax.step(t_l, S_l, where="post", color="#0072B2", linewidth=2.5,
              label=f"Low λ (n={len(low)}, median {np.median([r['OS'] for r in low]):.0f}d)")

    ax.set_xlabel("Days from baseline")
    ax.set_ylabel("Survival probability")
    ax.set_title(f"v197: Kaplan-Meier curves stratified by per-patient λ\n"
                  f"(RHUH-GBM, n={len(rows)} with valid λ; "
                  f"median λ = {median:.2f} voxels)")
    ax.legend(loc="upper right", fontsize=10)
    ax.set_ylim(0, 1.05)
    return save_fig(fig, "fig48_kaplan_meier_lambda_split")


def main():
    figure_46_lambda_vs_OS()
    figure_47_cindex_comparison()
    figure_48_kaplan_meier_lambda_split()
    print("done", flush=True)


if __name__ == "__main__":
    main()
