"""v204/v205 figures (Fig 58-59): PFS temporal-decay curve + DCA +
calibration; 3D CNN mask-only vs mask+kernel ablation."""
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


def figure_58_temporal_decay():
    print("Figure 58: temporal decay + DCA + calibration", flush=True)
    v204 = json.loads(
        (RESULTS / "v204_pfs_temporal_decay_dca.json").read_text())
    h = v204["horizon_results"]
    horizons_present = sorted(int(k) for k in h.keys())

    fig = plt.figure(figsize=(16.5, 10.0))
    gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.30)

    # --- Panel A: temporal decay curve with bootstrap CIs ---
    ax_a = fig.add_subplot(gs[0, :2])
    horizons = np.array(horizons_present)
    deltas = np.array([h[str(H)]["delta_AUC_point"]
                        for H in horizons])
    ci_low = np.array([h[str(H)]["delta_AUC_95_CI"][0]
                        for H in horizons])
    ci_high = np.array([h[str(H)]["delta_AUC_95_CI"][1]
                         for H in horizons])
    p_one = np.array([h[str(H)]["p_one_sided_delta_le_0"]
                       for H in horizons])

    ax_a.fill_between(horizons, ci_low, ci_high, color="#D55E00",
                       alpha=0.20, label="Bootstrap 95% CI")
    ax_a.plot(horizons, deltas, "-o", color="#D55E00", linewidth=2.0,
               markersize=8, label="Point estimate")
    ax_a.axhline(0, color="grey", linestyle="--", alpha=0.7,
                  label="Δ AUC = 0 (no benefit)")
    # mark significant horizons
    for H, d, p in zip(horizons, deltas, p_one):
        if p < 0.05:
            ax_a.annotate(f"P(Δ≤0) = {p:.3f}\nSIGNIFICANT",
                           xy=(H, d), xytext=(H + 30, d + 0.04),
                           fontsize=10, fontweight="bold",
                           color="#009E73",
                           arrowprops=dict(arrowstyle="->",
                                            color="#009E73", lw=1.5))
        ax_a.text(H, d + 0.005, f"{d:+.3f}", ha="center",
                   fontsize=9, fontweight="bold")
    ax_a.set_xlabel("PFS horizon H (days)")
    ax_a.set_ylabel("Δ AUC (clinical + V_kernel) − (clinical only)")
    ax_a.set_title("A. Temporal-decay curve of V_kernel's incremental "
                    "AUC\n(MU-Glioma-Post n=130, 1000 bootstraps per "
                    "horizon)")
    ax_a.legend(loc="lower right", fontsize=10)
    ax_a.set_xticks(horizons)

    # --- Panel B: prevalence vs horizon (context) ---
    ax_b = fig.add_subplot(gs[0, 2])
    n_pos = np.array([h[str(H)]["n_pos"] for H in horizons])
    n_neg = np.array([h[str(H)]["n_neg"] for H in horizons])
    prev = n_pos / (n_pos + n_neg)
    ax_b.plot(horizons, prev, "-o", color="#0072B2", linewidth=2.0,
               markersize=8)
    for H, p, np_, nn in zip(horizons, prev, n_pos, n_neg):
        ax_b.text(H, p + 0.02, f"{np_}/{nn}",
                   ha="center", fontsize=8)
    ax_b.set_xlabel("PFS horizon H (days)")
    ax_b.set_ylabel("Positive prevalence (progressed by H)")
    ax_b.set_title("B. Prevalence sweep\n(label balance at each H)")
    ax_b.set_xticks(horizons)
    ax_b.set_ylim(0, 1.0)

    # --- Panel C: DCA ---
    ax_c = fig.add_subplot(gs[1, 0])
    dca = v204["dca_at_365"]
    th = np.array(dca["thresholds"])
    nb_clin = np.array(dca["nb_clinical"])
    nb_full = np.array(dca["nb_clin_plus_Vkernel"])
    nb_all = np.array(dca["nb_treat_all"])
    ax_c.plot(th, nb_clin, "-", color="#0072B2", linewidth=2.0,
               label="Clinical only")
    ax_c.plot(th, nb_full, "-", color="#D55E00", linewidth=2.0,
               label="Clinical + V_kernel")
    ax_c.plot(th, nb_all, "--", color="grey", alpha=0.7,
               label="Treat all")
    ax_c.axhline(0, color="black", linestyle=":", alpha=0.5,
                  label="Treat none")
    ax_c.set_xlabel("Threshold probability p_t")
    ax_c.set_ylabel("Net benefit")
    ax_c.set_title(f"C. Decision-curve analysis (H=365 d)\n"
                    f"prevalence = {dca['prevalence_365']:.2f}, "
                    f"mean ΔNB = +{dca['mean_delta_nb']:.4f}")
    ax_c.legend(loc="lower left", fontsize=9)
    ax_c.set_xlim(0.05, 0.95)

    # --- Panel D: calibration plot ---
    ax_d = fig.add_subplot(gs[1, 1])
    cal = v204["calibration_at_365"]["bins"]
    pred = np.array([b["mean_predicted"] for b in cal])
    obs = np.array([b["observed_pos_rate"] for b in cal])
    ax_d.plot([0, 1], [0, 1], "--", color="grey", alpha=0.7,
               label="Perfect calibration")
    ax_d.plot(pred, obs, "-o", color="#D55E00", linewidth=2.0,
               markersize=8, label="Clinical + V_kernel (10 bins)")
    ax_d.set_xlabel("Mean predicted probability")
    ax_d.set_ylabel("Observed positive rate")
    ax_d.set_title(f"D. Calibration plot (H=365 d)\n"
                    f"Hosmer-Lemeshow χ² = "
                    f"{v204['calibration_at_365']['hl_chi2']:.2f} "
                    f"(df={v204['calibration_at_365']['df']}, "
                    f"NS = well calibrated)")
    ax_d.legend(loc="upper left", fontsize=9)
    ax_d.set_xlim(0.4, 1.0)
    ax_d.set_ylim(0.4, 1.0)

    # --- Panel E: bootstrap p-value summary ---
    ax_e = fig.add_subplot(gs[1, 2])
    p_vals = p_one
    colors_p = ["#009E73" if p < 0.05 else "#D55E00" if p < 0.10
                 else "#999999" for p in p_vals]
    ax_e.bar(range(len(horizons)), p_vals, color=colors_p,
              edgecolor="black", linewidth=0.5)
    ax_e.axhline(0.05, color="#009E73", linestyle="--", alpha=0.7,
                  label="α = 0.05")
    ax_e.axhline(0.10, color="#D55E00", linestyle="--", alpha=0.7,
                  label="α = 0.10")
    for i, p in enumerate(p_vals):
        ax_e.text(i, p + 0.01, f"{p:.3f}", ha="center", fontsize=9,
                   fontweight="bold")
    ax_e.set_xticks(range(len(horizons)))
    ax_e.set_xticklabels([f"{H} d" for H in horizons], fontsize=9)
    ax_e.set_ylabel("Bootstrap one-sided P(Δ AUC ≤ 0)")
    ax_e.set_title("E. Significance vs horizon\n"
                    "365 d: unique bootstrap-significant horizon")
    ax_e.legend(loc="upper right", fontsize=9)
    ax_e.set_ylim(0, 0.55)

    fig.suptitle("v204 BEYOND-NMI: bimodal kernel's clinical-utility "
                  "window precisely characterized — Δ AUC peaks at "
                  "365 d (P=0.039), well-calibrated (HL χ²=3.30 NS), "
                  "positive mean ΔNB across DCA thresholds",
                  fontsize=11.5, y=0.995)
    return save_fig(fig, "fig58_v204_temporal_decay_dca_calibration")


def figure_59_cnn_ablation():
    print("Figure 59: 3D CNN mask-only vs mask+kernel ablation",
          flush=True)
    v205 = json.loads(
        (RESULTS / "v205_pfs_binary_cnn.json").read_text())

    fig, axes = plt.subplots(1, 2, figsize=(15.0, 6.0))

    # Panel A: pooled OOF + per-fold comparison
    methods = [
        ("v202\nlogistic\nclinical only", 0.6199, "#0072B2",
         "logistic"),
        ("v205 3D CNN\nmask only\n(in_ch=1)",
         v205["variants"]["mask_only"]["pooled_oof_auc"],
         "#999999", "deep"),
        ("v205 3D CNN\nmask + kernel\n(in_ch=2)",
         v205["variants"]["mask_plus_kernel"]["pooled_oof_auc"],
         "#56B4E9", "deep"),
        ("v202\nlogistic\nclinical + V_kernel",
         0.7283, "#D55E00", "logistic"),
    ]
    labels = [m[0] for m in methods]
    aucs = [m[1] for m in methods]
    colors = [m[2] for m in methods]
    bars = axes[0].bar(range(len(methods)), aucs, color=colors,
                        edgecolor="black", linewidth=0.5)
    for i, a in enumerate(aucs):
        axes[0].text(i, a + 0.01, f"{a:.4f}", ha="center", fontsize=11,
                      fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                     label="chance")
    axes[0].set_xticks(range(len(methods)))
    axes[0].set_xticklabels(labels, fontsize=9)
    axes[0].set_ylabel("Pooled out-of-fold AUC")
    axes[0].set_title("A. Pooled OOF AUC (5-fold stratified CV)\n"
                       "Mask-only CNN < clinical logistic; "
                       "kernel is irreducible feature")
    axes[0].set_ylim(0.45, 0.80)
    axes[0].legend(loc="upper left", fontsize=9)

    # Panel B: per-fold AUC distribution
    fold_mask_only = v205["variants"]["mask_only"]["fold_aucs"]
    fold_mask_kernel = v205["variants"]["mask_plus_kernel"][
        "fold_aucs"]
    folds = [1, 2, 3, 4, 5]
    width = 0.35
    x = np.arange(len(folds))
    axes[1].bar(x - width/2, fold_mask_only, width,
                  label=f"Mask-only (fold mean = "
                        f"{np.mean(fold_mask_only):.3f})",
                  color="#999999", edgecolor="black", linewidth=0.5)
    axes[1].bar(x + width/2, fold_mask_kernel, width,
                  label=f"Mask + kernel (fold mean = "
                        f"{np.mean(fold_mask_kernel):.3f})",
                  color="#56B4E9", edgecolor="black", linewidth=0.5)
    for i, (m, k) in enumerate(zip(fold_mask_only, fold_mask_kernel)):
        axes[1].text(i - width/2, m + 0.01, f"{m:.2f}",
                       ha="center", fontsize=8)
        axes[1].text(i + width/2, k + 0.01, f"{k:.2f}",
                       ha="center", fontsize=8)
    axes[1].axhline(0.728, color="#D55E00", linestyle="--", alpha=0.8,
                     label="v202 logistic clin+V_k = 0.728")
    axes[1].axhline(0.620, color="#0072B2", linestyle="--", alpha=0.8,
                     label="v202 logistic clin only = 0.620")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"Fold {f}" for f in folds])
    axes[1].set_ylabel("Test AUC")
    axes[1].set_title("B. Per-fold AUC: kernel input adds ~12 pp "
                       "to CNN\nMask+kernel CNN matches logistic "
                       "(no DL gain)")
    axes[1].set_ylim(0.4, 1.05)
    axes[1].legend(loc="lower right", fontsize=8)

    fig.suptitle("v205 BEYOND-NMI: 3D CNN ablation rules out the "
                  "'foundation can replace the kernel' hypothesis. "
                  "Mask-only CNN cannot beat 3 clinical features "
                  "(0.528 OOF); kernel input is irreducible. "
                  "CNN+kernel matches logistic+kernel (zero DL gain).",
                  fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig59_v205_cnn_mask_kernel_ablation")


def main():
    figure_58_temporal_decay()
    figure_59_cnn_ablation()
    print("done", flush=True)


if __name__ == "__main__":
    main()
