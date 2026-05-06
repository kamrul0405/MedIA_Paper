# MedIA_Paper

**Manuscript:** *Structural priors versus learned models in longitudinal post-treatment brain-tumour MRI: a multi-cohort empirical benchmark with seed and architecture robustness*

**Target journal:** Medical Image Analysis (Elsevier; ISSN 1361-8415)
**Submission version:** v85 (2026-05-06)
**Status:** Submission-ready (formatted per Elsevier MedIA Guide for Authors)

---

## What this repository contains

Public companion to a methodology submission to *Medical Image Analysis*. Manuscript, figures, source-data files (JSON + CSV), and reproducibility scripts for every numerical claim in the paper.

```
MedIA_Paper/
├── manuscript/
│   ├── Manuscript_v85_for_MedIA.md/.pdf       <- PRIMARY SUBMISSION
│   ├── Manuscript_for_MedIA.md/.pdf           (v8.2 formatted; superseded by v85)
│   ├── Manuscript_v83_for_IEEE_TMI.md/.pdf    (theoretical companion / IEEE TMI alt)
│   ├── Final_Nature_MI.md/.pdf                (v8.2 master)
│   ├── Appendix_A_Proofs.md                   (Theorem 2-5 proofs)
│   └── CoverLetter_NMI.md                     (cover letter; rename to CoverLetter_MedIA at submission)
├── figures/
│   ├── main/                                  (Main Fig 1: PNG + 300 DPI TIFF)
│   └── extended_data/                         (16 Extended Data figures at 300 DPI)
├── source_data/                               (Versioned JSON/CSV underlying every numerical claim)
└── scripts/                                   (Python scripts producing source_data files)
```

## Headline empirical findings

- **Multi-cohort empirical benchmark** on 522 paired post-treatment brain-tumour MRI evaluations across 4 genuinely independent cohorts: UCSF-POSTOP (N=296), MU-Glioma-Post (N=151), RHUH-GBM (N=38), UCSD-PTGBM (N=37).
- **5 architecture families × 4 held-out cohorts × 5 seeds = 200+ training runs** preserve all 20/20 directional outcomes (binomial p ≈ 9.5×10⁻⁷ under p=0.5 null).
- **UNETR transformer baseline (12.53 M parameters)** preserves the regime-dependent ranking pattern: heat wins UCSF (+0.071) and UCSD (+0.071); UNETR wins MU narrowly (−0.003) and RHUH decisively (−0.169).
- **Closed-form composition crossover threshold π\*=0.43** (bootstrap 95% CI [0.30, 0.52]; Bayesian credible interval [0.17, 0.59]; random-effects meta-regression p<0.0001) predicts ranking direction in 7/7 cohorts.
- **Yale label-free acquisition-shift screen** (N=200/1430) achieves AUROC 0.847 as a complementary deployment audit.
- **9 negative controls** all destroy the heat-kernel signal (1.85×–5.17× fold increase in Brier).
- **Conformal three-regime classifier** achieves 1.00 empirical coverage at α=0.05 nominal (target ≥0.95) across leave-one-cohort-out on N=7.

## Reproducibility

Every numerical claim in the manuscript maps to a versioned `source_data/*.json` or `*.csv` file. Each `scripts/v*.py` is the Python script that produced the corresponding source-data file.

| File | Description | Maps to |
|---|---|---|
| `v77_ucsf_raw_mri_baseline.json` | UCSF 3-fold internal raw-MRI training | §3.1 |
| `v78_raw_mri_loco.json` | External LOCO across 4 cohorts | §3.2 / Table 1 |
| `v79_raw_loco_seed_robustness.json` | Three-seed lightweight-U-Net robustness | §3.3 |
| `v81_gpu_stronger_raw_loco.json` | Two-seed stronger ResUNet+TTA robustness | §3.3 |
| `v85_transformer_baselines.json` | UNETR transformer LOCO across 4 cohorts | §3.4 / Table 2 |
| `v76_nature_upgrade.json` | Bayesian + RE meta-regression + permutation power | §3.1, §3.5 |
| `v60_yale_expansion.json` | Yale label-free acquisition-shift audit | §3.6 |
| `v84_E3_conformal_coverage.json` | Conformal coverage empirical validation | §3.5 |
| `v84_E4_negative_controls.json` | 9 negative controls quantitative | §3.7 |
| `v84_E5_empirical_bernstein.json` | Empirical-Bernstein PAC-Bayes refinement | §3.8 |
| `master_neurooncology_dataset_index.csv` | 8-cohort master index | Methods §2.1 |

## Hardware / software

NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM), CUDA 12.8. Python 3.11.9; PyTorch 2.12; MONAI 1.5.2 (UNETR); nibabel 5.4.2; NumPy 2.4.4; SciPy 1.17.1; statsmodels.

## Companion repository

`RTO_paper` — companion submission to *Radiotherapy and Oncology* (brain-metastasis SRS recurrence-pattern paper using PROTEAS RTDOSE).

## License

Manuscript and figures: CC BY 4.0 (proposed at acceptance). Code: MIT.

## Contact

[Authors blinded for review.]
