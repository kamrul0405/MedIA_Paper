"""v228/v229 figures (Fig 82-83): multi-horizon DCA + calibration +
SHAP; attention-weighted kernel."""
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


def figure_82_dca_calib_shap():
    print("Figure 82: DCA + calibration + SHAP", flush=True)
    v228 = json.loads(
        (RESULTS / "v228_dca_calibration_shap.json").read_text())
    dca = v228["dca"]
    cal = v228["calibration_at_365"]
    shap = v228["shap_attribution"]

    fig = plt.figure(figsize=(16.5, 10.0))
    gs = fig.add_gridspec(2, 3, hspace=0.45, wspace=0.32)

    # Panel A: multi-horizon mean ΔNB
    horizons = sorted([int(k) for k in dca.keys()])
    delta_nbs = [dca[str(H)]["delta_nb_mean"] for H in horizons]
    ax_a = fig.add_subplot(gs[0, 0])
    colors_a = ["#009E73" if d > 0 else "#D55E00"
                  for d in delta_nbs]
    ax_a.bar(range(len(horizons)), delta_nbs,
              color=colors_a, edgecolor="black", linewidth=0.5)
    for i, d in enumerate(delta_nbs):
        ax_a.text(i, d + 0.002, f"{d:+.4f}",
                    ha="center", fontsize=10,
                    fontweight="bold")
    ax_a.axhline(0, color="black", linewidth=0.8)
    ax_a.axhline(0.0135, color="#0072B2", linestyle="--",
                   alpha=0.6,
                   label="Round 40 single-σ at 365 d (+0.014)")
    ax_a.set_xticks(range(len(horizons)))
    ax_a.set_xticklabels([f"{H} d" for H in horizons])
    ax_a.set_ylabel("Mean Δ NB across 19 thresholds")
    ax_a.set_title("A. Multi-horizon DCA (multi-σ vs clinical)\n"
                    "365 d Δ NB=0.055 — 4× round 40 single-σ")
    ax_a.legend(loc="upper right", fontsize=8)

    # Panel B: DCA curves at H=365
    ax_b = fig.add_subplot(gs[0, 1])
    h365 = dca["365"]
    th = h365["thresholds"]
    ax_b.plot(th, h365["nb_clin"], "-", color="#0072B2",
                linewidth=2, label="Clinical only")
    ax_b.plot(th, h365["nb_full"], "-", color="#D55E00",
                linewidth=2,
                label="**Clin + multi-σ V_kernel**")
    ax_b.plot(th, h365["nb_treat_all"], "--",
                color="grey", alpha=0.7, label="Treat all")
    ax_b.axhline(0, color="black", linestyle=":",
                   alpha=0.5, label="Treat none")
    ax_b.set_xlabel("Threshold probability p_t")
    ax_b.set_ylabel("Net Benefit at H=365 d")
    ax_b.set_title(f"B. DCA at H=365 d\n"
                    f"prevalence={h365['prevalence']:.2f}, "
                    f"full > clin at "
                    f"{h365['n_thresholds_full_better']}/19")
    ax_b.legend(loc="upper right", fontsize=8)
    ax_b.set_xlim(0.05, 0.95)

    # Panel C: calibration reliability diagram
    ax_c = fig.add_subplot(gs[0, 2])
    bins = cal["bins"]
    pred = [b["mean_predicted"] for b in bins]
    obs = [b["observed_pos_rate"] for b in bins]
    ns = [b["n"] for b in bins]
    ax_c.plot([0, 1], [0, 1], "--", color="grey",
                alpha=0.7, label="Perfect calibration")
    ax_c.scatter(pred, obs, s=[n * 8 for n in ns],
                   color="#D55E00", edgecolor="black",
                   linewidth=0.5, alpha=0.8,
                   label="Multi-σ (size ∝ n)")
    ax_c.plot(pred, obs, "-", color="#D55E00", alpha=0.4)
    ax_c.set_xlabel("Mean predicted probability")
    ax_c.set_ylabel("Observed positive rate")
    ax_c.set_title(f"C. Calibration at H=365 d\n"
                    f"HL χ² = {cal['hl_chi2']:.2f} (df="
                    f"{cal['df']}); round 40 was 3.30")
    ax_c.legend(loc="upper left", fontsize=9)
    ax_c.set_xlim(0.4, 1.05)
    ax_c.set_ylim(0.4, 1.05)

    # Panel D: per-σ contribution standard deviations
    ax_d = fig.add_subplot(gs[1, 0])
    per_sigma = shap["per_sigma_stats"]
    sigs = ["v_kernel_s2", "v_kernel_s3", "v_kernel_s4",
              "v_kernel_s5"]
    sigs_short = ["σ=2", "σ=3", "σ=4", "σ=5"]
    sds = [per_sigma[s]["std"] for s in sigs]
    means_p = [per_sigma[s]["mean"] for s in sigs]
    colors_d = ["#0072B2", "#56B4E9", "#D55E00", "#009E73"]
    ax_d.bar(range(len(sigs)), sds, color=colors_d,
              edgecolor="black", linewidth=0.5)
    for i, sd in enumerate(sds):
        ax_d.text(i, sd + 0.05, f"σ={sd:.2f}",
                    ha="center", fontsize=10,
                    fontweight="bold")
    ax_d.set_xticks(range(len(sigs)))
    ax_d.set_xticklabels(sigs_short)
    ax_d.set_ylabel("Per-patient log-odds contribution std")
    ax_d.set_title("D. Per-σ SHAP std (log-odds units)\n"
                    "σ=5 has widest patient-level effect\n"
                    "(but multicollinearity-adjusted)")

    # Panel E: top 5 patients with largest |kernel_contrib|
    ax_e = fig.add_subplot(gs[1, 1:])
    top5 = shap["top_5_high_kernel_contribution_patients"]
    n_p = len(top5)
    pids = [p["pid"][-4:] for p in top5]
    clin_c = [p["clinical_contribution"] for p in top5]
    kern_c = [p["kernel_contribution"] for p in top5]
    ys = [p["y"] for p in top5]
    pps = [p["p_pred"] for p in top5]
    width = 0.35
    x = np.arange(n_p)
    ax_e.bar(x - width/2, clin_c, width,
              color="#0072B2", edgecolor="black",
              linewidth=0.5, label="Clinical contribution")
    ax_e.bar(x + width/2, kern_c, width,
              color="#D55E00", edgecolor="black",
              linewidth=0.5, label="Kernel contribution")
    for i, (cc, kc, y, p) in enumerate(
            zip(clin_c, kern_c, ys, pps)):
        ax_e.text(i - width/2, cc + 0.15 * np.sign(cc),
                    f"{cc:+.2f}", ha="center", fontsize=9,
                    fontweight="bold")
        ax_e.text(i + width/2, kc + 0.15 * np.sign(kc),
                    f"{kc:+.2f}", ha="center", fontsize=9,
                    fontweight="bold")
        ax_e.text(i, -7,
                    f"y={y}\np={p:.2f}",
                    ha="center", fontsize=9)
    ax_e.axhline(0, color="black", linewidth=0.8)
    ax_e.set_xticks(x)
    ax_e.set_xticklabels([f"Pt {p}" for p in pids],
                            fontsize=10)
    ax_e.set_ylabel("Log-odds contribution")
    ax_e.set_title("E. Per-patient SHAP-like decomposition "
                    "(top 5 high-|kernel|)\n"
                    "All correctly predicted; kernel "
                    "appropriately positive (events) or "
                    "negative (non-event)")
    ax_e.set_ylim(-7.5, 6.5)
    ax_e.legend(loc="upper right", fontsize=9)

    fig.suptitle("v228 BEYOND-NMI multi-horizon DCA + "
                  "calibration + SHAP attribution: multi-σ "
                  "Δ NB at 365 d = +0.055 (4× round 40 "
                  "single-σ); HL χ²=2.47 (better than 3.30 "
                  "single-σ); per-patient SHAP shows "
                  "clinically-interpretable kernel "
                  "contributions ±5 log-odds for some patients.",
                  fontsize=10.5, y=0.995)
    return save_fig(fig, "fig82_v228_dca_calib_shap")


def figure_83_attention_kernel():
    print("Figure 83: attention-weighted kernel", flush=True)
    v229 = json.loads(
        (RESULTS / "v229_attention_weighted_kernel.json"
         ).read_text())
    res = v229["results"]
    delta = v229["bootstrap_delta_b_minus_a"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: AUC comparison
    methods = [
        ("Fixed multi-σ\nlogistic\n(round 47)",
         res["A_fixed_multi_sigma_logistic"]
            ["pooled_oof_auc"], "#0072B2"),
        ("**Attention-weighted\nmulti-σ**\n(round 52 NEW)",
         res["B_attention_weighted"]["pooled_oof_auc"],
         "#D55E00"),
    ]
    labels = [m[0] for m in methods]
    aucs = [m[1] for m in methods]
    colors = [m[2] for m in methods]
    axes[0].bar(range(len(methods)), aucs,
                  color=colors, edgecolor="black",
                  linewidth=0.5)
    for i, a in enumerate(aucs):
        axes[0].text(i, a + 0.012, f"{a:.4f}",
                       ha="center", fontsize=12,
                       fontweight="bold")
    axes[0].axhline(0.5, color="grey", linestyle="--",
                     alpha=0.7, label="chance")
    axes[0].set_xticks(range(len(methods)))
    axes[0].set_xticklabels(labels, fontsize=9)
    axes[0].set_ylabel("Pooled OOF AUC")
    axes[0].set_title("A. Attention-weighted vs fixed multi-σ\n"
                       "Δ=+0.037 (NS, P=0.346)")
    axes[0].set_ylim(0.45, 0.85)
    axes[0].legend(loc="upper right", fontsize=9)

    # Panel B: attention weights per fold
    attns = res["B_attention_weighted"][
        "learned_attention_per_fold"]
    folds = list(range(1, len(attns) + 1))
    width = 0.18
    x = np.arange(len(folds))
    sigs = ["σ=2", "σ=3", "σ=4", "σ=5"]
    colors_attn = ["#0072B2", "#D55E00", "#009E73", "#56B4E9"]
    for i, sg in enumerate(sigs):
        weights = [attn[i] for attn in attns]
        axes[1].bar(x + (i - 1.5) * width, weights, width,
                      color=colors_attn[i],
                      edgecolor="black", linewidth=0.5,
                      label=sg)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([f"Fold {f}" for f in folds])
    axes[1].set_ylabel("Mean attention weight on test")
    axes[1].set_title("B. Per-fold learned attention weights\n"
                       "High variability across folds")
    axes[1].set_ylim(0, 1.0)
    axes[1].legend(loc="upper right", fontsize=8)

    # Panel C: average attention + bootstrap
    ax_c = axes[2]
    attn_mean = res["B_attention_weighted"][
        "learned_attention_mean"]
    bars = ax_c.bar(sigs, attn_mean,
                     color=colors_attn, edgecolor="black",
                     linewidth=0.5)
    for i, w in enumerate(attn_mean):
        ax_c.text(i, w + 0.015, f"{w:.3f}",
                    ha="center", fontsize=11,
                    fontweight="bold")
    ax_c.axhline(0.25, color="grey", linestyle="--",
                  alpha=0.7,
                  label="Uniform 0.25")
    ax_c.set_ylabel("Mean attention weight (5-fold avg)")
    ax_c.set_title(f"C. Average attention across folds\n"
                    f"σ_5 dominates (0.354); bootstrap "
                    f"P={delta['p_one_sided']:.3f}")
    ax_c.set_ylim(0, 0.55)
    ax_c.legend(loc="upper right", fontsize=9)

    fig.suptitle("v229 BEYOND-LANCET attention-weighted "
                  "multi-σ kernel: per-patient softmax over σ "
                  "values gives modest +0.037 OOF AUC over "
                  "fixed multi-σ but NOT statistically "
                  "significant (P=0.346). High fold-to-fold "
                  "attention variability suggests overfitting; "
                  "**fixed multi-σ logistic remains "
                  "recommended**.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig83_v229_attention_kernel")


def main():
    figure_82_dca_calib_shap()
    figure_83_attention_kernel()
    print("done", flush=True)


if __name__ == "__main__":
    main()
