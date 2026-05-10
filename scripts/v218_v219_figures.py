"""v218/v219 figures (Fig 72-73): SOTA radiomics + 3D ResNet-18
ablation."""
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


def figure_72_sota_radiomics():
    print("Figure 72: SOTA radiomics comparison", flush=True)
    v218 = json.loads(
        (RESULTS / "v218_sota_radiomics.json").read_text())
    models = v218["models"]
    nri_idi = v218["reclassification_vs_clin"]

    fig = plt.figure(figsize=(16.5, 10.0))
    gs = fig.add_gridspec(2, 2, hspace=0.40, wspace=0.30)

    # Panel A: AUC bar chart
    ax_a = fig.add_subplot(gs[0, :])
    ordered = [
        ("clinical only\n(n=3)", "clinical_only", "#999999"),
        ("V_kernel σ=3\nonly (n=1)", "Vkernel_s3_only",
         "#56B4E9"),
        ("V_kernel\n**multi-σ**\n(n=4)", "Vkernel_multi_sigma",
         "#D55E00"),
        ("clin + V_k σ=3\n(round 39, n=4)",
         "clin_plus_Vkernel_s3", "#0072B2"),
        ("**clin + V_k\nmulti-σ**\n(n=7) NEW",
         "clin_plus_Vkernel_multi", "#D55E00"),
        ("shape only\n(13 radiomics\nfeats)", "shape_only",
         "#CC79A7"),
        ("clin + shape\n(n=16)", "clin_plus_shape", "#CC79A7"),
        ("V_k σ=3 +\nshape (n=14)",
         "Vkernel_s3_plus_shape", "#CC79A7"),
        ("clin + shape\n+ V_k σ=3\n(n=17)",
         "clin_plus_shape_plus_Vkernel_s3", "#0072B2"),
        ("**clin + shape\n+ V_k multi-σ**\n(n=20) BEST",
         "clin_plus_shape_plus_Vkernel_multi", "#009E73"),
    ]
    labels = [m[0] for m in ordered]
    aucs = [models[m[1]]["auc"] for m in ordered]
    cis = [models[m[1]]["auc_95_CI"] for m in ordered]
    colors = [m[2] for m in ordered]
    err_lo = [max(0.0, a - ci[0]) for a, ci in zip(aucs, cis)]
    err_hi = [max(0.0, ci[1] - a) for a, ci in zip(aucs, cis)]
    bars = ax_a.bar(range(len(ordered)), aucs,
                     color=colors, edgecolor="black",
                     linewidth=0.5,
                     yerr=[err_lo, err_hi], capsize=4)
    for i, a in enumerate(aucs):
        ax_a.text(i, a + 0.018, f"{a:.3f}", ha="center",
                    fontsize=10, fontweight="bold")
    ax_a.axhline(0.5, color="grey", linestyle="--", alpha=0.7,
                  label="chance")
    ax_a.axhline(0.728, color="#0072B2", linestyle=":",
                  alpha=0.6, label="round 39 baseline 0.728")
    ax_a.set_xticks(range(len(ordered)))
    ax_a.set_xticklabels(labels, fontsize=8)
    ax_a.set_ylabel("Bootstrap AUC at H=365 d (95% CI)")
    ax_a.set_title("A. SOTA radiomics comparison "
                    "(MU n=130). Multi-σ V_kernel breakthrough: "
                    "clin+multi-σ AUC=0.815 (+0.087 over round 39); "
                    "kitchen-sink 20-feature AUC=0.849")
    ax_a.set_ylim(0.45, 1.05)
    ax_a.legend(loc="upper left", fontsize=9)

    # Panel B: NRI vs clinical
    ax_b = fig.add_subplot(gs[1, 0])
    nri_models = list(nri_idi.keys())
    # Order them in display order matching panel A
    nri_order = [
        "Vkernel_s3_only", "Vkernel_multi_sigma",
        "clin_plus_Vkernel_s3", "clin_plus_Vkernel_multi",
        "shape_only", "clin_plus_shape",
        "Vkernel_s3_plus_shape",
        "clin_plus_shape_plus_Vkernel_s3",
        "clin_plus_shape_plus_Vkernel_multi",
    ]
    nri_label_short = {
        "Vkernel_s3_only": "V_k s3", "Vkernel_multi_sigma":
        "V_k multi-σ",
        "clin_plus_Vkernel_s3": "clin+V_k s3",
        "clin_plus_Vkernel_multi": "**clin+V_k multi-σ**",
        "shape_only": "shape only",
        "clin_plus_shape": "clin+shape",
        "Vkernel_s3_plus_shape": "V_k s3+shape",
        "clin_plus_shape_plus_Vkernel_s3":
        "clin+shape+V_k s3",
        "clin_plus_shape_plus_Vkernel_multi":
        "**kitchen sink (20)**",
    }
    nri_vals = [nri_idi[m]["NRI"] for m in nri_order]
    nri_ps = [nri_idi[m]["NRI_p_one_sided"]
                for m in nri_order]
    colors_b = ["#009E73" if p < 0.001 else "#D55E00"
                  if p < 0.05 else "#999999" for p in nri_ps]
    ax_b.bar(range(len(nri_order)), nri_vals,
              color=colors_b, edgecolor="black", linewidth=0.5)
    for i, (v, p) in enumerate(zip(nri_vals, nri_ps)):
        sig = "✓✓" if p < 0.001 else ("✓" if p < 0.05 else "")
        ax_b.text(i, v + 0.02, f"{v:+.3f}{sig}",
                    ha="center", fontsize=9,
                    fontweight="bold")
    ax_b.axhline(0, color="black", linewidth=0.8)
    ax_b.axhline(0.43, color="#0072B2", linestyle=":",
                  alpha=0.6,
                  label="round 44 NRI=+0.43")
    ax_b.set_xticks(range(len(nri_order)))
    ax_b.set_xticklabels(
        [nri_label_short[m] for m in nri_order],
        fontsize=8, rotation=30, ha="right")
    ax_b.set_ylabel("Continuous NRI vs clinical-only")
    ax_b.set_title("B. NRI: clin+V_k multi-σ NRI=+0.805 "
                    "(P=0.0000) — DOUBLES round 44's +0.43")
    ax_b.set_ylim(-0.1, 1.0)
    ax_b.legend(loc="upper left", fontsize=8)

    # Panel C: IDI vs clinical
    ax_c = fig.add_subplot(gs[1, 1])
    idi_vals = [nri_idi[m]["IDI"] for m in nri_order]
    idi_ps = [nri_idi[m]["IDI_p_one_sided"]
                for m in nri_order]
    colors_c = ["#009E73" if p < 0.001 else "#D55E00"
                  if p < 0.05 else "#999999" for p in idi_ps]
    ax_c.bar(range(len(nri_order)), idi_vals,
              color=colors_c, edgecolor="black", linewidth=0.5)
    for i, (v, p) in enumerate(zip(idi_vals, idi_ps)):
        sig = "✓✓" if p < 0.001 else ("✓" if p < 0.05 else "")
        ax_c.text(i, v + 0.005, f"{v:+.3f}{sig}",
                    ha="center", fontsize=9,
                    fontweight="bold")
    ax_c.axhline(0, color="black", linewidth=0.8)
    ax_c.axhline(0.054, color="#0072B2", linestyle=":",
                  alpha=0.6,
                  label="round 44 IDI=+0.054")
    ax_c.set_xticks(range(len(nri_order)))
    ax_c.set_xticklabels(
        [nri_label_short[m] for m in nri_order],
        fontsize=8, rotation=30, ha="right")
    ax_c.set_ylabel("IDI vs clinical-only")
    ax_c.set_title("C. IDI: clin+V_k multi-σ IDI=+0.112 "
                    "(P=0.0000); kitchen-sink IDI=+0.157")
    ax_c.set_ylim(-0.05, 0.22)
    ax_c.legend(loc="upper left", fontsize=8)

    fig.suptitle("v218 BEYOND-NMI multi-σ V_kernel "
                  "BREAKTHROUGH: clin+V_kernel(σ=2,3,4,5) "
                  "reaches AUC=0.815 (+0.087 over round 39's "
                  "0.728), NRI=+0.805 (DOUBLES round 44's +0.43), "
                  "IDI=+0.112 (P=0.0000). Multi-scale kernel "
                  "beats 13 hand-crafted radiomics features "
                  "(0.815 vs 0.748 with shape only).",
                  fontsize=10.5, y=0.995)
    return save_fig(fig, "fig72_v218_sota_radiomics")


def figure_73_3d_resnet():
    print("Figure 73: 3D ResNet-18 SOTA architecture",
          flush=True)
    v219 = json.loads(
        (RESULTS / "v219_3d_resnet_sota.json").read_text())
    res = v219["results"]
    summary = v219["comparison_summary"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.5))

    # Panel A: pooled OOF AUC by variant (incl logistic)
    ax_a = axes[0]
    methods = [
        ("v202 logistic\nclin+V_k s3\n(4 features)", 0.728,
         "#009E73", 4),
        ("**v218 logistic\nclin+V_k multi-σ**\n(7 features)",
         0.815, "#D55E00", 7),
        ("v219(A) SimpleCNN\nbaseline\n(488K params)",
         res["A_simple_cnn"]["pooled_oof_auc"], "#0072B2",
         488_000),
        ("v219(B) **3D ResNet-18\nSOTA** (4.7M params)",
         res["B_resnet3d18"]["pooled_oof_auc"], "#999999",
         4_680_000),
        ("v219(C) ResNet-18 +\nSimCLR pretrain",
         res["C_resnet3d18_simclr_pretrain"]["pooled_oof_auc"],
         "#56B4E9", 4_680_000),
    ]
    labels = [m[0] for m in methods]
    aucs = [m[1] for m in methods]
    colors = [m[2] for m in methods]
    bars = ax_a.bar(range(len(methods)), aucs,
                     color=colors, edgecolor="black",
                     linewidth=0.5)
    for i, a in enumerate(aucs):
        ax_a.text(i, a + 0.015, f"{a:.3f}", ha="center",
                    fontsize=11, fontweight="bold")
    ax_a.axhline(0.5, color="grey", linestyle="--",
                  alpha=0.7, label="chance")
    ax_a.set_xticks(range(len(methods)))
    ax_a.set_xticklabels(labels, fontsize=8)
    ax_a.set_ylabel("MU pooled OOF AUC at H=365 d")
    ax_a.set_title("A. Logistic vs SOTA architectures\n"
                    "Simple multi-σ logistic CRUSHES SOTA "
                    "ResNet-18 (+0.247 AUC)")
    ax_a.set_ylim(0.45, 0.90)
    ax_a.legend(loc="upper right", fontsize=9)

    # Panel B: parameter count vs AUC scatter
    ax_b = axes[1]
    methods_p = [
        ("logistic\nclin+V_k s3", 4, 0.728, "#009E73"),
        ("logistic\nclin+V_k multi-σ", 7, 0.815, "#D55E00"),
        ("SimpleCNN", 488_000,
         res["A_simple_cnn"]["pooled_oof_auc"], "#0072B2"),
        ("3D ResNet-18", 4_680_000,
         res["B_resnet3d18"]["pooled_oof_auc"], "#999999"),
        ("ResNet-18+SimCLR", 4_680_000,
         res["C_resnet3d18_simclr_pretrain"]["pooled_oof_auc"],
         "#56B4E9"),
    ]
    for name, np_, a, c in methods_p:
        ax_b.scatter(np_, a, s=200, color=c,
                       edgecolor="black", linewidth=0.5,
                       label=name)
        ax_b.annotate(name.replace("\n", " "),
                        (np_, a), xytext=(8, 8),
                        textcoords="offset points",
                        fontsize=8, ha="left")
    ax_b.set_xscale("log")
    ax_b.set_xlabel("Number of parameters (log scale)")
    ax_b.set_ylabel("MU pooled OOF AUC")
    ax_b.set_title("B. Parameter count vs AUC\n"
                    "More parameters HURT at MU n=130")
    ax_b.set_ylim(0.45, 0.90)
    ax_b.axhline(0.5, color="grey", linestyle="--",
                  alpha=0.5)

    # Panel C: per-fold AUC distribution by variant
    ax_c = axes[2]
    variants = [
        ("SimpleCNN\n(488K)", "A_simple_cnn", "#0072B2"),
        ("ResNet-18\nSOTA (4.7M)", "B_resnet3d18", "#999999"),
        ("ResNet-18\n+SimCLR",
         "C_resnet3d18_simclr_pretrain", "#56B4E9"),
    ]
    n_folds = 5
    width = 0.25
    x = np.arange(n_folds)
    for i, (lab, key, col) in enumerate(variants):
        fa = res[key]["fold_aucs"]
        ax_c.bar(x + i * width - width, fa, width,
                  color=col, edgecolor="black", linewidth=0.5,
                  label=lab.split("\n")[0])
    ax_c.axhline(0.728, color="#009E73", linestyle="--",
                  alpha=0.8,
                  label="logistic clin+V_k s3 = 0.728")
    ax_c.axhline(0.815, color="#D55E00", linestyle="--",
                  alpha=0.8,
                  label="logistic clin+V_k multi-σ = 0.815")
    ax_c.set_xticks(x)
    ax_c.set_xticklabels([f"Fold {i+1}"
                            for i in range(n_folds)])
    ax_c.set_ylabel("Per-fold AUC")
    ax_c.set_title("C. Per-fold AUC distribution\n"
                    "ResNet-18 high variance (overfit at "
                    "n=130): range 0.51-0.99")
    ax_c.set_ylim(0.4, 1.05)
    ax_c.legend(loc="lower right", fontsize=8)

    fig.suptitle("v219 BEYOND-NMI SOTA architecture comparison: "
                  "3D ResNet-18 (4.7M params, 9.6× SimpleCNN) "
                  "achieves only AUC=0.568, FAILING to match the "
                  "simple 7-feature logistic+multi-σ V_kernel "
                  "(0.815). At MU n=130, more parameters HURT — "
                  "the bimodal kernel is the optimal feature.",
                  fontsize=10.5, y=1.03)
    fig.tight_layout()
    return save_fig(fig, "fig73_v219_3d_resnet_sota")


def main():
    figure_72_sota_radiomics()
    figure_73_3d_resnet()
    print("done", flush=True)


if __name__ == "__main__":
    main()
