# MedIA_Paper

**Manuscript:** *A multi-cohort longitudinal post-treatment brain-tumour MRI benchmark for evaluating composition-shift ranking stability with eight curated cohorts and reproducible analysis infrastructure*

**Target journal:** *Scientific Data* (Nature Portfolio; ISSN 2052-4463) — Data Descriptor
**Status:** Submission-ready (formatted per Scientific Data Data-Descriptor template)

> **Note on repository name.** This repository was originally created targeting *Medical Image Analysis* (Elsevier) and retains the `MedIA_Paper` name for URL stability and commit-history continuity. The current submission target is *Scientific Data* (Nature Portfolio). The Medical Image Analysis version of the manuscript is preserved at `manuscript/Manuscript_v85_for_MedIA.md` for archival reference.

---

## What this repository contains

Public companion to a Data Descriptor submission to *Scientific Data*. Manuscript, figures, source-data files (JSON + CSV), and reproducibility scripts for every numerical claim in the paper.

```
MedIA_Paper/
├── manuscript/
│   ├── Manuscript_for_ScientificData.md/.pdf   <- PRIMARY SUBMISSION
│   ├── Manuscript_v85_for_MedIA.md/.pdf        (archived MedIA version)
│   ├── Manuscript_v83_for_IEEE_TMI.md/.pdf     (archived IEEE TMI alt)
│   ├── Appendix_A_Proofs.md                    (Theorem 2-5 proofs)
│   └── CoverLetter_NMI.md                      (cover letter draft; rename to CoverLetter_ScientificData)
├── figures/
│   ├── main/                                   (5 main figures: PNG + 300 DPI TIFF)
│   └── extended_data/                          (16 Extended Data figures at 300 DPI)
├── source_data/                                (Versioned JSON/CSV underlying every numerical claim)
└── scripts/                                    (Python scripts producing source_data files)
```

## Released data products

This Data Descriptor releases three concrete data products:

1. **An eight-cohort master neuro-oncology dataset index** (`source_data/master_neurooncology_dataset_index.csv`) with mask-provenance tier, π_stable, N pairs, license terms, and pointer to the originating data source.
2. **Reproducible per-cohort Brier and calibration source-data files** (JSON and CSV) with one-to-one mapping from each numerical claim to a versioned source-data file.
3. **Open-source reproducibility scripts** (Python; MIT licence) implementing leave-one-cohort-out training, multi-seed evaluation, transformer baselines (UNETR + zero-padded SwinUNETR), the closed-form composition-shift crossover, calibration, fairness, and a panel of nine pre-specified negative controls.

## Cohorts indexed

- **UCSF-POSTOP** (GBM post-op surveillance; N = 296; π_stable = 0.81; tier-1 manual mask)
- **MU-Glioma-Post** (Glioma post-op; N = 151; π_stable = 0.34; tier-2 semi-automated; TCIA CC BY 4.0)
- **RHUH-GBM** (GBM post-treatment; N = 38; π_stable = 0.29; tier-2 expert-reviewed; TCIA)
- **UCSD-PTGBM** (Post-treatment GBM; N = 37; π_stable = 0.24; tier-2; TCIA CC BY 4.0; Hartman 2025)
- **LUMIERE** (Glioma IDH cold holdout; N = 19; π_stable = 0.45; Figshare CC BY 4.0)
- **UPENN-GBM** (GBM tier-3 sensitivity; N = 41; π_stable = 0.35; TCIA CC BY 4.0)
- **Yale-Brain-Mets-Longitudinal** (Brain mets acquisition shift; N = 1,430; Yale data-use agreement)
- **PROTEAS-brain-mets** (Brain mets SRS with patient-specific RTDOSE; N = 43 / 122 follow-ups; π_stable = 0.19; Zenodo open access)

## Technical-validation summary

- **5 architecture families × 4 held-out cohorts × 5 seeds**: 20/20 directional preservation under leave-one-cohort-out raw-MRI transfer (binomial p = 9.5 × 10⁻⁷).
- **3-seed UNETR transformer** (12.53 M parameters): direction matches in 12/12 individual seed-cohort conditions (binomial p < 2.5 × 10⁻⁴).
- **Padded 32 × 64 × 64 SwinUNETR**: direction matches in 3/4 cohorts; UCSD-PTGBM is a within-noise tie rather than a flip.
- **Closed-form composition-shift crossover π* = 0.43** (bootstrap 95% CI [0.30, 0.52]; Bayesian credible interval [0.17, 0.59]; random-effects meta-regression p < 0.0001) predicts ranking direction in 7/7 cohorts.
- **Yale label-free acquisition-shift screen** (N = 200 / 1430) achieves AUROC 0.847.
- **Nine pre-specified negative controls** all destroy the signal (1.85×–5.17× fold increase in Brier).
- **Conformal three-regime classifier** achieves 1.00 empirical coverage at α = 0.05 nominal (target ≥ 0.95) across leave-one-cohort-out on N = 7 cohorts.

## Reproducibility

Every numerical claim in the manuscript maps to a versioned `source_data/*.json` or `*.csv` file. Each `scripts/v*.py` is the Python script that produced the corresponding source-data file.

| File | Description | Maps to |
|---|---|---|
| `v77_ucsf_raw_mri_baseline.json` | UCSF 3-fold internal raw-MRI training | Methods (π* derivation) |
| `v78_raw_mri_loco.json` | External LOCO across 4 cohorts (lightweight U-Net) | Technical Validation §1 |
| `v79_raw_loco_seed_robustness.json` | Three-seed lightweight-U-Net robustness | Technical Validation §2 |
| `v81_gpu_stronger_raw_loco.json` | Two-seed stronger ResUNet + TTA robustness | Technical Validation §2 |
| `v85_transformer_baselines.json` | UNETR seed 8501 LOCO across 4 cohorts | Technical Validation §3 |
| `v86_extra_seeds_padded.json` | UNETR seeds 8502/8503 + padded SwinUNETR + padded UNETR sanity | Technical Validation §3 |
| `v76_nature_upgrade.json` | Bayesian + RE meta-regression + permutation power | Methods (π* uncertainty) |
| `v60_yale_expansion.json` | Yale label-free acquisition-shift audit | Technical Validation §6 |
| `v84_E3_conformal_coverage.json` | Conformal coverage empirical validation | Technical Validation §4 |
| `v84_E4_negative_controls.json` | 9 negative controls quantitative | Technical Validation §5 |
| `v84_E5_empirical_bernstein.json` | Empirical-Bernstein PAC-Bayes refinement | Technical Validation §7 |
| `master_neurooncology_dataset_index.csv` | 8-cohort master index | Methods (cohort assembly) |

## Hardware / software

NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM), CUDA 12.8. Python 3.11.9; PyTorch 2.12; MONAI 1.5.2 (UNETR + SwinUNETR); nibabel 5.4.2; NumPy; SciPy 1.17.1; statsmodels (DerSimonian–Laird). Total compute approximately 12 hours.

## Companion repository

`RTO_paper` — companion submission to *Cancers* (MDPI; brain-metastasis SRS future-lesion coverage on PROTEAS RTDOSE).

## Licence

Manuscript and figures: CC BY 4.0 (proposed at acceptance). Code: MIT.

## Contact

**Sheikh Kamrul Islam** — sheikh.islam@kcl.ac.uk (alternative: kamrul0405@outlook.com).
Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences, King's College London.
