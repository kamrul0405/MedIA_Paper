"""v222/v223 figures (Fig 76-77): IPCW multi-horizon multi-σ +
SimCLR-multi-σ hybrid logistic."""
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


def figure_76_ipcw_multi_horizon():
    print("Figure 76: IPCW multi-horizon multi-σ", flush=True)
    v222 = json.loads(
        (RESULTS / "v222_ipcw_multi_horizon.json").read_text())
    h_results = v222["horizon_results"]
    horizons = sorted(int(k) for k in h_results.keys())

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: AUC across horizons (clin vs single-σ vs multi-σ)
    aucs_clin = [h_results[str(H)]["ipcw"]["auc_clin"]
                  for H in horizons]
    aucs_s3 = [h_results[str(H)]["ipcw"]["auc_Vk_s3"]
                for H in horizons]
    aucs_multi = [h_results[str(H)]["ipcw"]["auc_multi_sigma"]
                   for H in horizons]
    ax = axes[0]
    ax.plot(horizons, aucs_clin, "-o", color="#0072B2",
              linewidth=2, markersize=10, label="Clinical only")
    ax.plot(horizons, aucs_s3, "-s", color="#56B4E9",
              linewidth=2, markersize=10,
              label="Clin + V_k σ=3 (round 39)")
    ax.plot(horizons, aucs_multi, "-D", color="#D55E00",
              linewidth=2.5, markersize=11,
              label="**Clin + V_k multi-σ (round 49)**")
    for H, a in zip(horizons, aucs_multi):
        ax.text(H, a + 0.012, f"{a:.3f}", ha="center",
                  fontsize=9, fontweight="bold")
    ax.axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                 label="chance")
    ax.set_xticks(horizons)
    ax.set_xlabel("PFS horizon (days)")
    ax.set_ylabel("IPCW-weighted AUC")
    ax.set_title("A. IPCW multi-horizon AUC\n"
                   "Multi-σ AUC peaks at 365 d (0.815)")
    ax.legend(loc="lower center", fontsize=8)
    ax.set_ylim(0.5, 0.92)

    # Panel B: Δ AUC (multi-σ vs clin) with bootstrap CIs
    deltas = [h_results[str(H)]["ipcw"]["delta_multi_sigma"]
                for H in horizons]
    bootstrap = [h_results[str(H)]["bootstrap_ipcw_multi_sigma"]
                  for H in horizons]
    ci_los = [b["95_CI"][0] for b in bootstrap]
    ci_his = [b["95_CI"][1] for b in bootstrap]
    p_vals = [b["p_one_sided"] for b in bootstrap]
    err_lo = [d - lo for d, lo in zip(deltas, ci_los)]
    err_hi = [hi - d for d, hi in zip(deltas, ci_his)]
    ax = axes[1]
    colors_b = ["#009E73" if p < 0.05 else
                  "#D55E00" if p < 0.10 else "#999999"
                  for p in p_vals]
    ax.errorbar(horizons, deltas, yerr=[err_lo, err_hi],
                  fmt="none", ecolor="grey", capsize=4)
    for h, d, c, p in zip(horizons, deltas, colors_b, p_vals):
        ax.scatter(h, d, s=200, color=c,
                     edgecolor="black", linewidth=0.5, zorder=3)
        sig = "✓✓✓" if p < 0.001 else "✓" if p < 0.05 else \
            "~" if p < 0.10 else ""
        ax.text(h, d + 0.015,
                  f"Δ={d:+.3f}{sig}\nP={p:.4f}",
                  ha="center", fontsize=9, fontweight="bold")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axhspan(270, 450, color="#009E73", alpha=0.10,
                 label="Significant window 270-450 d")
    ax.axvspan(270, 450, color="#009E73", alpha=0.10)
    ax.set_xticks(horizons)
    ax.set_xlabel("PFS horizon (days)")
    ax.set_ylabel("Δ AUC (multi-σ − clinical)")
    ax.set_title("B. Multi-σ Δ AUC bootstrap CIs\n"
                   "270/365/450 d all significant (vs round 40 "
                   "single-σ: only 365 d)")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_ylim(-0.05, 0.40)

    # Panel C: comparison single-σ vs multi-σ across horizons
    deltas_s3 = [h_results[str(H)]["ipcw"]["delta_Vk_s3"]
                  for H in horizons]
    width = 0.35
    x = np.arange(len(horizons))
    ax = axes[2]
    ax.bar(x - width/2, deltas_s3, width, color="#56B4E9",
              edgecolor="black", linewidth=0.5,
              label="single-σ (V_k σ=3)")
    ax.bar(x + width/2, deltas, width, color="#D55E00",
              edgecolor="black", linewidth=0.5,
              label="**multi-σ (V_k σ=2,3,4,5)**")
    for i, (s, m) in enumerate(zip(deltas_s3, deltas)):
        ax.text(i - width/2, s + 0.005, f"{s:+.3f}",
                  ha="center", fontsize=8)
        ax.text(i + width/2, m + 0.005, f"{m:+.3f}",
                  ha="center", fontsize=9, fontweight="bold")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{H} d" for H in horizons])
    ax.set_xlabel("PFS horizon")
    ax.set_ylabel("Δ AUC vs clinical-only")
    ax.set_title("C. Multi-σ vs single-σ across horizons\n"
                   "Multi-σ wins on every horizon")
    ax.legend(loc="upper right", fontsize=9)

    fig.suptitle("v222 BEYOND-NMI multi-horizon IPCW analysis: "
                  "multi-σ V_kernel extends the bootstrap-"
                  "significant horizon window from 1 (round 40 "
                  "single-σ at 365 d) to **3 (270/365/450 d)** "
                  "with peak Δ AUC=+0.193 at 365 d (P<0.001).",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig76_v222_ipcw_multi_horizon")


def figure_77_simclr_hybrid():
    print("Figure 77: SimCLR-multi-σ hybrid logistic",
          flush=True)
    v223 = json.loads(
        (RESULTS / "v223_simclr_hybrid_logistic.json"
         ).read_text())
    res = v223["results"]
    deltas = v223["bootstrap_deltas"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: per-fold + pooled OOF AUC
    methods = [
        ("**Multi-σ only**\n(7 features)\nv218 round 47",
         "multi_sigma_only", "#D55E00"),
        ("SimCLR only\n(96 features)\nv215 round 45",
         "simclr_only", "#56B4E9"),
        ("**Hybrid**\n(103 features)\nSimCLR + multi-σ",
         "hybrid_simclr_plus_multi_sigma", "#999999"),
    ]
    labels_a = [m[0] for m in methods]
    aucs = [res[m[1]]["pooled_oof_auc"] for m in methods]
    fold_aucs_lists = [res[m[1]]["fold_aucs"] for m in methods]
    colors = [m[2] for m in methods]
    bars = axes[0].bar(range(len(methods)), aucs,
                        color=colors, edgecolor="black",
                        linewidth=0.5)
    for i, a in enumerate(aucs):
        axes[0].text(i, a + 0.012, f"{a:.3f}", ha="center",
                       fontsize=11, fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7, label="chance")
    axes[0].axhline(0.728, color="#009E73",
                     linestyle="--", alpha=0.6,
                     label="v218 logistic in-sample = 0.728")
    axes[0].set_xticks(range(len(methods)))
    axes[0].set_xticklabels(labels_a, fontsize=8)
    axes[0].set_ylabel("Pooled OOF AUC (5-fold CV)")
    axes[0].set_title("A. SimCLR-features + multi-σ "
                       "HONEST NEGATIVE\n"
                       "Hybrid HURTS (0.708 → 0.599); "
                       "multi-σ alone is sufficient")
    axes[0].set_ylim(0.45, 0.80)
    axes[0].legend(loc="upper right", fontsize=9)

    # Panel B: per-fold AUC
    n_folds = 5
    width = 0.27
    x = np.arange(n_folds)
    for i, (lab, key, col) in enumerate(methods):
        fa = res[key]["fold_aucs"]
        axes[1].bar(x + i * width - width, fa, width,
                      color=col, edgecolor="black",
                      linewidth=0.5,
                      label=lab.split("\n")[0])
    axes[1].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"Fold {f+1}"
                                for f in range(n_folds)])
    axes[1].set_ylabel("Per-fold AUC")
    axes[1].set_title("B. Per-fold AUC distribution\n"
                       "Hybrid has high variance — "
                       "over-parameterized")
    axes[1].set_ylim(0.4, 1.05)
    axes[1].legend(loc="lower right", fontsize=8)

    # Panel C: bootstrap pairwise Δ AUC
    pair_data = [
        ("**hybrid − multi-σ**",
         deltas["hybrid_minus_multi_sigma"], "#D55E00"),
        ("**hybrid − simclr**",
         deltas["hybrid_minus_simclr"], "#56B4E9"),
        ("**multi-σ − simclr**",
         deltas["multi_sigma_minus_simclr"], "#009E73"),
    ]
    labels_c = [d[0] for d in pair_data]
    means = [d[1]["mean"] for d in pair_data]
    cis = [d[1]["95_CI"] for d in pair_data]
    ps = [d[1]["p_one_sided"] for d in pair_data]
    err_lo = [max(0, m - c[0]) for m, c in zip(means, cis)]
    err_hi = [max(0, c[1] - m) for m, c in zip(means, cis)]
    colors_c = [d[2] for d in pair_data]
    axes[2].bar(range(len(pair_data)), means,
                  yerr=[err_lo, err_hi], color=colors_c,
                  edgecolor="black", linewidth=0.5,
                  capsize=6)
    for i, (m, p) in enumerate(zip(means, ps)):
        sig = "✓" if p < 0.05 else "" if p < 0.5 else "✗"
        axes[2].text(i, m + 0.015 * np.sign(
            m if m != 0 else 1),
                       f"Δ={m:+.3f}{sig}\nP={p:.3f}",
                       ha="center", fontsize=9,
                       fontweight="bold",
                       va="bottom" if m >= 0 else "top")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_xticks(range(len(pair_data)))
    axes[2].set_xticklabels(labels_c, fontsize=8)
    axes[2].set_ylabel("Δ pooled OOF AUC")
    axes[2].set_title("C. Bootstrap pairwise Δ\n"
                       "multi-σ - simclr P=0.032 ✓; "
                       "hybrid HURTS multi-σ")
    axes[2].set_ylim(-0.20, 0.30)

    fig.suptitle("v223 BEYOND-NMI HONEST NEGATIVE: adding 96-"
                  "dim SimCLR encoder features to the 7-feature "
                  "multi-σ logistic HURTS performance (0.708 → "
                  "0.599 OOF). At MU n=130, the 103-feature "
                  "hybrid is over-parameterized; **multi-σ kernel "
                  "alone is sufficient and recommended**.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig77_v223_simclr_hybrid")


def main():
    figure_76_ipcw_multi_horizon()
    figure_77_simclr_hybrid()
    print("done", flush=True)


if __name__ == "__main__":
    main()
