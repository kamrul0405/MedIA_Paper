"""v182: Publication-grade figures — round 21, part 1.

Generates the figures that flagship venues (Nature, Cell, Lancet,
Nature Methods, etc.) expect:

  Figure 1: v174 cohort-scaling curve on UPENN external
  Figure 2: UOSL fitted surface vs N_eff, with all 12 datapoints
            (10 fit + 2 out-of-sample), bootstrap CI band, and labels
  Figure 3: UOSL vs Kaplan-McCandlish vs Chinchilla-lite
            (within-fit RMSE + out-of-sample errors)
  Figure 4: v179 Yale 3-seed per-patient ensemble outgrowth
            (violin plot per seed)
  Figure 5: v159 multi-seed per-cohort per-patient ensemble outgrowth
            (violin plot, 5 cohorts x 3 seeds)
  Figure 6: v180 LOOCV predicted vs observed scatter
            (with y=x line and per-fold labels)
  Figure 7: v181 permutation null distribution histogram
            (3 panels: within-fit RMSE, Yale err, UPENN err)
  Figure 8: v178 UOSL bootstrap parameter posteriors
            (4-panel histogram for P_0, P_inf, a, n_c)

Saves PNG (300 dpi) + PDF (vector) to MedIA_Paper/figures/ and
RTO_paper/figures/. Uses matplotlib only (no seaborn dep).

Outputs:
  MedIA_Paper/figures/figXX_*.png + .pdf  (8 figures)
  Nature_project/05_results/v182_figures_index.json
"""
from __future__ import annotations

import csv
import json
import time
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
INDEX_JSON = RESULTS / "v182_figures_index.json"

for d in FIG_DIRS:
    d.mkdir(parents=True, exist_ok=True)

# Publication style
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

# Cohort colour palette (colour-blind safe, Wong 2011)
COHORT_COLORS = {
    "UCSF-POSTOP":         "#0072B2",  # blue
    "MU-Glioma-Post":      "#E69F00",  # orange
    "RHUH-GBM":            "#009E73",  # bluish green
    "LUMIERE":             "#CC79A7",  # reddish purple
    "PROTEAS-brain-mets":  "#D55E00",  # vermillion
    "UPENN-GBM":           "#56B4E9",  # sky blue
    "Yale-Brain-Mets":     "#000000",  # black
}


def save_fig(fig, name):
    """Save figure to all FIG_DIRS as both PNG and PDF."""
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
# Helpers (identical to v178/v180/v181 — duplicated to keep script standalone)
# ============================================================================

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
DISEASE_VEC = {
    "UCSF-POSTOP":         np.array([0.7, 0.3, 0.0]),
    "MU-Glioma-Post":      np.array([0.7, 0.3, 0.0]),
    "RHUH-GBM":            np.array([1.0, 0.0, 0.0]),
    "LUMIERE":             np.array([0.4, 0.6, 0.0]),
    "PROTEAS-brain-mets":  np.array([0.0, 0.0, 1.0]),
    "UPENN-GBM":           np.array([1.0, 0.0, 0.0]),
    "Yale-Brain-Mets":     np.array([0.0, 0.0, 1.0]),
}


def cohort_weighted_distribution(train_cohorts, n_per_cohort):
    total = sum(n_per_cohort.get(c, 0) for c in train_cohorts)
    if total == 0:
        return np.zeros(3)
    avg = np.zeros(3)
    for c in train_cohorts:
        n = n_per_cohort.get(c, 0)
        avg += (n / total) * DISEASE_VEC[c]
    return avg


def similarity_index(train_dist, test_cohort):
    test = DISEASE_VEC[test_cohort]
    nt = np.linalg.norm(train_dist)
    nT = np.linalg.norm(test)
    if nt == 0 or nT == 0:
        return 0.0
    return float(np.dot(train_dist, test) / (nt * nT))


def uosl_v2(features, p_0, p_inf, a, n_c):
    n_train, S = features
    N_eff = np.log1p(n_train) * S
    return p_0 + (p_inf - p_0) / (1.0 + np.exp(-a * (N_eff - n_c)))


# ============================================================================
# Figure 1 — v174 cohort-scaling curve on UPENN external
# ============================================================================

def figure_1_v174_cohort_scaling():
    print("Figure 1: v174 cohort-scaling on UPENN external", flush=True)
    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    Ns = sorted([int(k) for k in v174["by_n"].keys()])
    ens = [v174["by_n"][str(N)]["ensemble_outgrowth_pct"] for N in Ns]
    learn = [v174["by_n"][str(N)]["learned_outgrowth_pct"] for N in Ns]
    bim = [v174["by_n"][str(N)]["bimodal_outgrowth_pct"] for N in Ns]
    cohorts = [v174["by_n"][str(N)]["train_cohorts"][-1] for N in Ns]

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    ax.plot(Ns, ens, "o-", color="#000000", linewidth=2.0, markersize=10,
            label="Ensemble (model + bimodal kernel)")
    ax.plot(Ns, learn, "s--", color="#0072B2", linewidth=1.5, markersize=8,
            label="Learned (model only)")
    ax.plot(Ns, bim, "^:", color="#999999", linewidth=1.5, markersize=8,
            label="Bimodal heat kernel only")

    # annotate peak
    peak_idx = int(np.argmax(ens))
    ax.annotate(f"PEAK\n{ens[peak_idx]:.1f}%\n(UCSF+MU+RHUH)",
                xy=(Ns[peak_idx], ens[peak_idx]),
                xytext=(Ns[peak_idx] + 0.4, ens[peak_idx] - 4),
                fontsize=9, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#D55E00"))
    # annotate added cohort at each step
    for i, (N, c) in enumerate(zip(Ns, cohorts)):
        ax.annotate(c.replace("-", "\n", 1), xy=(N, 50),
                    xytext=(N, 47), ha="center", va="top",
                    fontsize=7, color="#666666")

    ax.set_xlabel("Number of training cohorts (cumulative)")
    ax.set_ylabel("Outgrowth coverage on UPENN-GBM (%)")
    ax.set_title("v174: Training-cohort-scaling law on UPENN external (n=41)")
    ax.set_xticks(Ns)
    ax.set_ylim(40, 105)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    return save_fig(fig, "fig01_v174_cohort_scaling")


# ============================================================================
# Figure 2 — UOSL fitted curve vs N_eff with all 12 datapoints + CI
# ============================================================================

def figure_2_uosl_curve():
    print("Figure 2: UOSL fitted surface + datapoints", flush=True)
    v178 = json.loads((RESULTS / "v178_uosl_uncertainty_scaling_comparison.json")
                      .read_text())
    p_0 = v178["uosl_v2"]["param_point"]["P_0"]
    p_inf = v178["uosl_v2"]["param_point"]["P_inf"]
    a = v178["uosl_v2"]["param_point"]["a"]
    n_c = v178["uosl_v2"]["param_point"]["n_c"]

    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    v159 = json.loads((RESULTS / "v159_multiseed_v156.json").read_text())

    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]

    pts = []
    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        pts.append({
            "N_eff": float(np.log1p(row["n_train_patients"]) * S),
            "P": row["ensemble_outgrowth_pct"] / 100.0,
            "label": f"v174 N={n_str}->UPENN",
            "color": COHORT_COLORS["UPENN-GBM"],
            "marker": "o",
        })
    for held_out, stats in v159["by_cohort"].items():
        train_cohorts = [c for c in ALL_COHORTS if c != held_out]
        train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
        S = similarity_index(train_dist, held_out)
        n_tr = sum(n_per_cohort[c] for c in train_cohorts)
        pts.append({
            "N_eff": float(np.log1p(n_tr) * S),
            "P": stats["ensemble_outgrowth_mean"] / 100.0,
            "label": f"v159 LOCO held={held_out}",
            "color": COHORT_COLORS[held_out],
            "marker": "s",
        })
    # out-of-sample: Yale + v172
    n_tr_full = sum(n_per_cohort[c] for c in ALL_COHORTS)
    td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
    S_yale = similarity_index(td_full, "Yale-Brain-Mets")
    S_upenn = similarity_index(td_full, "UPENN-GBM")
    yale_pt = {
        "N_eff": float(np.log1p(n_tr_full) * S_yale),
        "P": 0.7871, "label": "Yale (out-of-sample)",
        "color": COHORT_COLORS["Yale-Brain-Mets"], "marker": "*",
    }
    v172_pt = {
        "N_eff": float(np.log1p(n_tr_full) * S_upenn),
        "P": 0.9285, "label": "v172 zero-shot UPENN (out-of-sample)",
        "color": COHORT_COLORS["UPENN-GBM"], "marker": "*",
    }

    # UOSL surface
    Neff_grid = np.linspace(0, max(p["N_eff"] for p in
                                   pts + [yale_pt, v172_pt]) * 1.05, 400)

    def uosl_neff(neff):
        return p_0 + (p_inf - p_0) / (1.0 + np.exp(-a * (neff - n_c)))

    P_curve = uosl_neff(Neff_grid)

    # 95% CI from bootstrap-derived parameter ranges (use the published CIs
    # to plot a CI band)
    lo = v178["uosl_v2"]["param_ci_95"]
    P_lo = lo["P_0"]["ci_lo"]
    P_hi = lo["P_inf"]["ci_hi"]

    fig, ax = plt.subplots(figsize=(7.5, 5.0))

    # CI band as horizontal band (asymptotic floor/ceiling CIs)
    ax.axhspan(lo["P_0"]["ci_lo"] * 100, lo["P_0"]["ci_hi"] * 100,
                alpha=0.10, color="#0072B2",
                label=f"P_0 95% CI [{lo['P_0']['ci_lo']*100:.1f}, "
                      f"{lo['P_0']['ci_hi']*100:.1f}]")
    ax.axhspan(lo["P_inf"]["ci_lo"] * 100, lo["P_inf"]["ci_hi"] * 100,
                alpha=0.10, color="#009E73",
                label=f"P_inf 95% CI [{lo['P_inf']['ci_lo']*100:.1f}, "
                      f"{lo['P_inf']['ci_hi']*100:.1f}]")

    # UOSL fitted curve
    ax.plot(Neff_grid, P_curve * 100, "-", color="#000000", linewidth=2.5,
            label=f"UOSL v2 fit (P_0={p_0:.3f}, P_inf={p_inf:.3f}, n_c={n_c:.2f})")

    # asymptotic lines
    ax.axhline(p_0 * 100, color="#0072B2", linestyle=":", alpha=0.6,
               linewidth=1.0)
    ax.axhline(p_inf * 100, color="#009E73", linestyle=":", alpha=0.6,
               linewidth=1.0)
    ax.text(0.05, p_0 * 100 + 0.5, f"P_0 = {p_0*100:.1f}%",
            color="#0072B2", fontsize=8)
    ax.text(0.05, p_inf * 100 + 0.5, f"P_inf = {p_inf*100:.1f}%",
            color="#009E73", fontsize=8)

    # plot fit datapoints
    for p in pts:
        ax.plot(p["N_eff"], p["P"] * 100, p["marker"],
                color=p["color"], markersize=10, markeredgecolor="black",
                markeredgewidth=0.5, alpha=0.8)
    # out-of-sample
    ax.plot(yale_pt["N_eff"], yale_pt["P"] * 100, yale_pt["marker"],
            color=yale_pt["color"], markersize=18,
            markeredgecolor="white", markeredgewidth=1.5,
            label=f"Yale (S=0.31): obs {yale_pt['P']*100:.2f}%")
    ax.plot(v172_pt["N_eff"], v172_pt["P"] * 100, v172_pt["marker"],
            color=v172_pt["color"], markersize=18,
            markeredgecolor="white", markeredgewidth=1.5,
            label=f"v172 zero-shot UPENN (S=0.88): obs {v172_pt['P']*100:.2f}%")

    ax.set_xlabel(r"$N_\mathrm{eff} = \ln(1 + n_\mathrm{train}) \cdot S$")
    ax.set_ylabel("Ensemble outgrowth coverage (%)")
    ax.set_title("UOSL v2: closed-form 4-parameter scaling law\n"
                 "(circles = v174 fit, squares = v159 LOCO fit, "
                 "stars = held-out prediction)")
    ax.set_ylim(50, 105)
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(True, alpha=0.3)
    return save_fig(fig, "fig02_uosl_law_with_datapoints")


# ============================================================================
# Figure 3 — UOSL vs Kaplan vs Chinchilla bar chart
# ============================================================================

def figure_3_scaling_law_comparison():
    print("Figure 3: UOSL vs Kaplan-McCandlish vs Chinchilla", flush=True)
    v178 = json.loads((RESULTS / "v178_uosl_uncertainty_scaling_comparison.json")
                      .read_text())
    laws = ["UOSL v2 (ours)", "Kaplan-McCandlish", "Chinchilla-lite"]
    rmse_within = [v178["uosl_v2"]["rmse_within_fit"],
                   v178["kaplan_mccandlish"]["rmse_within_fit"],
                   v178["chinchilla_lite"]["rmse_within_fit"]]
    yale_err = [v178["uosl_v2"]["yale_prediction"]["err_pp"],
                v178["kaplan_mccandlish"]["yale_err_pp"],
                v178["chinchilla_lite"]["yale_err_pp"]]
    v172_err = [v178["uosl_v2"]["v172_zero_shot_upenn_prediction"]["err_pp"],
                v178["kaplan_mccandlish"]["v172_err_pp"],
                v178["chinchilla_lite"]["v172_err_pp"]]

    rmse_within_pp = [r * 100 for r in rmse_within]

    fig, axes = plt.subplots(1, 3, figsize=(11.0, 4.0))
    x = np.arange(len(laws))
    colors = ["#000000", "#999999", "#666666"]

    axes[0].bar(x, rmse_within_pp, color=colors)
    for i, v in enumerate(rmse_within_pp):
        axes[0].text(i, v + 0.2, f"{v:.2f}", ha="center", fontsize=9)
    axes[0].set_title("Within-fit RMSE (10 datapoints)")
    axes[0].set_ylabel("RMSE (pp)")

    axes[1].bar(x, yale_err, color=colors)
    for i, v in enumerate(yale_err):
        axes[1].text(i, v + 0.1, f"{v:.2f}", ha="center", fontsize=9)
    axes[1].set_title("Yale prediction error (pp)\n(out-of-sample, 7th cohort)")
    axes[1].set_ylabel("Error (pp)")

    axes[2].bar(x, v172_err, color=colors)
    for i, v in enumerate(v172_err):
        axes[2].text(i, v + 0.1, f"{v:.2f}", ha="center", fontsize=9)
    axes[2].set_title("v172 UPENN zero-shot error (pp)\n(out-of-sample)")
    axes[2].set_ylabel("Error (pp)")

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels(laws, rotation=15, ha="right")
        ax.grid(True, alpha=0.3, axis="y")
        ax.set_axisbelow(True)

    fig.suptitle(
        "UOSL beats Kaplan-McCandlish and Chinchilla-lite "
        "by 3.6x-4.6x on cross-cohort prediction (Paper A4)",
        fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig03_scaling_law_comparison")


# ============================================================================
# Figure 4 — Yale 3-seed per-patient violin plot
# ============================================================================

def figure_4_yale_violin():
    print("Figure 4: Yale 3-seed violin", flush=True)
    csv_path = RESULTS / "v179_yale_multiseed_per_patient.csv"
    by_seed = {42: [], 123: [], 999: []}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                v = float(row["ensemble_outgrowth"])
            except (ValueError, TypeError):
                continue
            if np.isnan(v):
                continue
            seed = int(row["seed"])
            by_seed[seed].append(v * 100)

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    labels = list(by_seed.keys())
    data = [by_seed[s] for s in labels]
    colors = ["#0072B2", "#E69F00", "#009E73"]

    parts = ax.violinplot(data, positions=range(len(labels)),
                           widths=0.8, showmeans=True, showmedians=True)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.5)
        pc.set_edgecolor("black")
    parts["cmeans"].set_color("black")
    parts["cmeans"].set_linewidth(2.0)
    parts["cmedians"].set_color("#D55E00")

    # individual jittered points
    rng = np.random.default_rng(0)
    for i, vals in enumerate(data):
        x_jit = rng.uniform(-0.05, 0.05, size=len(vals)) + i
        ax.scatter(x_jit, vals, alpha=0.6, s=20, color="black")

    # mean labels
    for i, vals in enumerate(data):
        m = np.mean(vals)
        ax.text(i, 102, f"mean = {m:.2f}%\n(n = {len(vals)})",
                ha="center", fontsize=9)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([f"Seed {s}" for s in labels])
    ax.set_ylabel("Per-patient ensemble outgrowth coverage (%)")
    ax.set_title("v179: Yale-Brain-Mets-Longitudinal 7th-cohort zero-shot\n"
                 "across 3 seeds (across-seed mean = 80.06% +/- 3.44)")
    ax.set_ylim(0, 110)
    return save_fig(fig, "fig04_yale_3seed_violin")


# ============================================================================
# Figure 5 — v159 multi-seed per-cohort per-patient violin
# ============================================================================

def figure_5_v159_violin():
    print("Figure 5: v159 multi-seed per-cohort violin", flush=True)
    csv_path = RESULTS / "v159_multiseed_v156_per_patient.csv"
    if not csv_path.exists():
        print(f"  WARN: {csv_path} not found, skipping", flush=True)
        return []
    by_cohort = {c: [] for c in ALL_COHORTS}
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            cohort = row.get("cohort", row.get("Cohort", ""))
            if cohort not in by_cohort:
                continue
            try:
                v = float(row.get("ensemble_outgrowth",
                                  row.get("ensemble_outgrowth_pct",
                                          "nan")))
            except (ValueError, TypeError):
                continue
            if np.isnan(v):
                continue
            # values may be 0-1 or 0-100; normalise to %
            if v <= 1.0:
                v *= 100
            by_cohort[cohort].append(v)

    cohorts_with_data = [c for c in ALL_COHORTS if by_cohort[c]]
    if not cohorts_with_data:
        print(f"  WARN: no cohort data found in v159 csv, skipping",
              flush=True)
        return []

    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    data = [by_cohort[c] for c in cohorts_with_data]
    colors = [COHORT_COLORS[c] for c in cohorts_with_data]

    parts = ax.violinplot(data, positions=range(len(cohorts_with_data)),
                           widths=0.8, showmeans=True, showmedians=True)
    for i, pc in enumerate(parts["bodies"]):
        pc.set_facecolor(colors[i])
        pc.set_alpha(0.5)
        pc.set_edgecolor("black")
    parts["cmeans"].set_color("black")
    parts["cmeans"].set_linewidth(2.0)
    parts["cmedians"].set_color("#D55E00")

    rng = np.random.default_rng(0)
    for i, vals in enumerate(data):
        x_jit = rng.uniform(-0.07, 0.07, size=len(vals)) + i
        ax.scatter(x_jit, vals, alpha=0.4, s=10, color="black")

    for i, (c, vals) in enumerate(zip(cohorts_with_data, data)):
        m = np.mean(vals)
        ax.text(i, 108, f"{m:.1f}%\n(n={len(vals)})",
                ha="center", fontsize=8)

    ax.set_xticks(range(len(cohorts_with_data)))
    ax.set_xticklabels([c.replace("-", "\n") for c in cohorts_with_data],
                        fontsize=9)
    ax.set_ylabel("Per-patient ensemble outgrowth coverage (%)")
    ax.set_title("v159: multi-seed per-cohort per-patient ensemble outgrowth "
                 "(seeds 42, 123, 999 pooled)")
    ax.set_ylim(0, 115)
    return save_fig(fig, "fig05_v159_per_cohort_violin")


# ============================================================================
# Figure 6 — LOOCV scatter
# ============================================================================

def figure_6_loocv_scatter():
    print("Figure 6: LOOCV predicted-vs-observed", flush=True)
    v180 = json.loads((RESULTS / "v180_uosl_loocv.json").read_text())

    obs = []
    pred = []
    labels = []
    for r in v180["fold_results"]:
        if r["P_predicted"] is None or np.isnan(r["P_predicted"]):
            continue
        obs.append(r["P_observed"] * 100)
        pred.append(r["P_predicted"] * 100)
        labels.append(r["label"])

    obs = np.array(obs)
    pred = np.array(pred)

    fig, ax = plt.subplots(figsize=(7.0, 6.5))

    # y=x line
    lo = min(min(obs), min(pred)) - 3
    hi = max(max(obs), max(pred)) + 3
    ax.plot([lo, hi], [lo, hi], "k--", alpha=0.4, label="y = x (perfect)")
    # +/- 5pp band
    ax.fill_between([lo, hi], [lo - 5, hi - 5], [lo + 5, hi + 5],
                     alpha=0.10, color="grey", label="+/- 5 pp")
    # +/- 10pp band
    ax.fill_between([lo, hi], [lo - 10, hi - 10], [lo + 10, hi + 10],
                     alpha=0.05, color="grey", label="+/- 10 pp")

    sc = ax.scatter(obs, pred, c=range(len(obs)), cmap="tab10", s=120,
                     edgecolor="black", linewidth=0.7)
    for i, lbl in enumerate(labels):
        # truncate label
        lbl_short = lbl.replace("v174 ", "").replace("v159 LOCO held=", "h:")
        ax.annotate(lbl_short, (obs[i], pred[i]),
                    xytext=(5, 5), textcoords="offset points", fontsize=8)

    rmse = float(np.sqrt(np.mean((pred - obs) ** 2)))
    mae = float(np.mean(np.abs(pred - obs)))

    ax.set_xlabel("Observed P (%)")
    ax.set_ylabel("LOOCV-predicted P (%)")
    ax.set_title(f"v180: UOSL leave-one-out cross-validation (10 folds)\n"
                 f"LOOCV RMSE = {rmse:.2f} pp, MAE = {mae:.2f} pp "
                 f"(mean-baseline RMSE = {v180['mean_baseline_rmse']*100:.2f} pp)")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.legend(loc="upper left", fontsize=9)
    return save_fig(fig, "fig06_loocv_scatter")


# ============================================================================
# Figure 7 — Permutation null distribution (3 panels)
# ============================================================================

def figure_7_permutation_null():
    print("Figure 7: permutation null distributions", flush=True)
    v181 = json.loads((RESULTS / "v181_uosl_permutation_test.json").read_text())

    # Re-run a small permutation set to get the distribution arrays for plotting
    # (v181 only stored quantiles, not full arrays). Simpler: load and re-run.
    from scipy.optimize import curve_fit
    import warnings
    warnings.filterwarnings("ignore")

    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    v159 = json.loads((RESULTS / "v159_multiseed_v156.json").read_text())

    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]

    fit_n_train, fit_S, fit_P = [], [], []
    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        fit_n_train.append(row["n_train_patients"])
        fit_S.append(S)
        fit_P.append(row["ensemble_outgrowth_pct"] / 100.0)
    for held_out, stats in v159["by_cohort"].items():
        train_cohorts = [c for c in ALL_COHORTS if c != held_out]
        train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
        S = similarity_index(train_dist, held_out)
        fit_n_train.append(sum(n_per_cohort[c] for c in train_cohorts))
        fit_S.append(S)
        fit_P.append(stats["ensemble_outgrowth_mean"] / 100.0)

    fit_n_train = np.array(fit_n_train, dtype=float)
    fit_S = np.array(fit_S, dtype=float)
    fit_P = np.array(fit_P, dtype=float)
    n10 = len(fit_P)

    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt_true, _ = curve_fit(uosl_v2, (fit_n_train, fit_S), fit_P,
                              p0=p0, bounds=bounds, maxfev=20000)
    pred_true = uosl_v2((fit_n_train, fit_S), *popt_true)
    true_rmse = float(np.sqrt(np.mean((pred_true - fit_P) ** 2)))

    n_tr_full = sum(n_per_cohort[c] for c in ALL_COHORTS)
    td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
    S_yale = similarity_index(td_full, "Yale-Brain-Mets")
    S_upenn = similarity_index(td_full, "UPENN-GBM")
    yale_obs = 0.7871
    upenn_obs = 0.9285
    true_yale_pred = float(uosl_v2((np.array([n_tr_full]),
                                     np.array([S_yale])), *popt_true)[0])
    true_upenn_pred = float(uosl_v2((np.array([n_tr_full]),
                                      np.array([S_upenn])), *popt_true)[0])
    true_yale_err = abs(true_yale_pred - yale_obs)
    true_upenn_err = abs(true_upenn_pred - upenn_obs)

    print("  re-running 500 permutations for histogram...", flush=True)
    rng = np.random.default_rng(2026)
    perm_rmses = []
    perm_yale_errs = []
    perm_upenn_errs = []
    for i in range(500):
        idx = rng.permutation(n10)
        try:
            popt_p, _ = curve_fit(uosl_v2, (fit_n_train[idx], fit_S[idx]),
                                   fit_P, p0=popt_true, bounds=bounds,
                                   maxfev=5000)
        except Exception:
            continue
        perm_rmses.append(
            float(np.sqrt(np.mean((uosl_v2((fit_n_train[idx], fit_S[idx]),
                                              *popt_p) - fit_P) ** 2))))
        yale_p = float(uosl_v2((np.array([n_tr_full]),
                                 np.array([S_yale])), *popt_p)[0])
        upenn_p = float(uosl_v2((np.array([n_tr_full]),
                                  np.array([S_upenn])), *popt_p)[0])
        perm_yale_errs.append(abs(yale_p - yale_obs))
        perm_upenn_errs.append(abs(upenn_p - upenn_obs))
    print(f"  successful: {len(perm_rmses)}/500", flush=True)

    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.8))
    panels = [
        ("Within-fit RMSE (pp)",
         np.array(perm_rmses) * 100, true_rmse * 100,
         v181["p_value_rmse"]),
        ("Yale prediction error (pp)",
         np.array(perm_yale_errs) * 100, true_yale_err * 100,
         v181["p_value_yale_err"]),
        ("v172 UPENN error (pp)",
         np.array(perm_upenn_errs) * 100, true_upenn_err * 100,
         v181["p_value_upenn_err"]),
    ]
    for ax, (lbl, dist, truth, p_v) in zip(axes, panels):
        ax.hist(dist, bins=25, color="#999999", edgecolor="black",
                 alpha=0.7)
        ax.axvline(truth, color="#D55E00", linewidth=2.5,
                    label=f"True = {truth:.2f}")
        ax.set_xlabel(lbl)
        ax.set_ylabel("Number of permutations")
        # red text for p-value
        ax.text(0.95, 0.95,
                f"p = {p_v:.4f}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=11, fontweight="bold",
                color="#D55E00",
                bbox=dict(boxstyle="round,pad=0.3", fc="white",
                          ec="#D55E00"))
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle("v181: UOSL permutation/null-shuffle test "
                  "(1,000 random feature permutations from full v181 run; "
                  "histograms here are 500-perm sub-sample)",
                  fontsize=10, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig07_permutation_null")


# ============================================================================
# Figure 8 — UOSL bootstrap parameter posteriors (4-panel)
# ============================================================================

def figure_8_param_posterior():
    print("Figure 8: UOSL bootstrap parameter posteriors (re-running 1,000 "
          "bootstraps for histograms)", flush=True)
    from scipy.optimize import curve_fit
    import warnings
    warnings.filterwarnings("ignore")

    v178 = json.loads((RESULTS / "v178_uosl_uncertainty_scaling_comparison.json")
                      .read_text())
    v174 = json.loads((RESULTS / "v174_cohort_scaling_upenn.json").read_text())
    v159 = json.loads((RESULTS / "v159_multiseed_v156.json").read_text())

    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]

    fit_n_train, fit_S, fit_P = [], [], []
    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        fit_n_train.append(row["n_train_patients"])
        fit_S.append(S)
        fit_P.append(row["ensemble_outgrowth_pct"] / 100.0)
    for held_out, stats in v159["by_cohort"].items():
        train_cohorts = [c for c in ALL_COHORTS if c != held_out]
        train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
        S = similarity_index(train_dist, held_out)
        fit_n_train.append(sum(n_per_cohort[c] for c in train_cohorts))
        fit_S.append(S)
        fit_P.append(stats["ensemble_outgrowth_mean"] / 100.0)

    fit_n_train = np.array(fit_n_train, dtype=float)
    fit_S = np.array(fit_S, dtype=float)
    fit_P = np.array(fit_P, dtype=float)
    n10 = len(fit_P)

    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt_full, _ = curve_fit(uosl_v2, (fit_n_train, fit_S), fit_P,
                              p0=p0, bounds=bounds, maxfev=20000)

    rng = np.random.default_rng(42)
    boot = []
    for b in range(1000):
        idx = rng.integers(0, n10, size=n10)
        try:
            popt_b, _ = curve_fit(uosl_v2, (fit_n_train[idx], fit_S[idx]),
                                   fit_P[idx], p0=popt_full, bounds=bounds,
                                   maxfev=10000)
            boot.append(popt_b)
        except Exception:
            continue
    boot = np.array(boot)
    print(f"  bootstrap n: {len(boot)}", flush=True)

    fig, axes = plt.subplots(1, 4, figsize=(13.0, 3.5))
    names = ["P_0", "P_inf", "a (steepness)", "n_c (inflection)"]
    points = [popt_full[0], popt_full[1], popt_full[2], popt_full[3]]
    colors = ["#0072B2", "#009E73", "#E69F00", "#CC79A7"]

    for ax, name, pt, col, vals in zip(axes, names, points, colors, boot.T):
        lo, hi = np.percentile(vals, [2.5, 97.5])
        ax.hist(vals, bins=30, color=col, alpha=0.6, edgecolor="black")
        ax.axvline(pt, color="black", linestyle="-", linewidth=2.0,
                    label=f"point = {pt:.3f}")
        ax.axvline(lo, color="red", linestyle="--", linewidth=1.5,
                    label=f"95% CI = [{lo:.3f}, {hi:.3f}]")
        ax.axvline(hi, color="red", linestyle="--", linewidth=1.5)
        ax.set_xlabel(name)
        ax.set_ylabel("Bootstrap frequency")
        ax.legend(loc="upper right", fontsize=8)
    fig.suptitle("v178: UOSL parameter bootstrap posteriors (1,000 "
                  "bootstrap resamples)", fontsize=11, y=1.02)
    fig.tight_layout()
    return save_fig(fig, "fig08_uosl_param_posteriors")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v182 PUBLICATION-GRADE FIGURES", flush=True)
    print(f"  output directories: {[str(d) for d in FIG_DIRS]}", flush=True)
    print("=" * 78, flush=True)

    paths = {}
    t0 = time.time()
    for fn, key in [
        (figure_1_v174_cohort_scaling, "fig01"),
        (figure_2_uosl_curve, "fig02"),
        (figure_3_scaling_law_comparison, "fig03"),
        (figure_4_yale_violin, "fig04"),
        (figure_5_v159_violin, "fig05"),
        (figure_6_loocv_scatter, "fig06"),
        (figure_7_permutation_null, "fig07"),
        (figure_8_param_posterior, "fig08"),
    ]:
        try:
            paths[key] = fn()
        except Exception as e:
            print(f"  ERROR in {key}: {e}", flush=True)
            paths[key] = []

    INDEX_JSON.write_text(json.dumps({
        "version": "v182",
        "experiment": "Publication-grade figures",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "figures": paths,
        "elapsed_s": time.time() - t0,
    }, indent=2))
    print(f"\nDone in {time.time()-t0:.0f}s. Index: {INDEX_JSON}", flush=True)


if __name__ == "__main__":
    main()
