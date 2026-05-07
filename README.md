# MedIA_Paper

**Manuscript:** *Structural priors versus learned models in longitudinal post-treatment brain-tumour MRI: a multi-cohort empirical benchmark with seed and architecture robustness*

**Target journal:** *Medical Image Analysis* (Elsevier; ISSN 1361-8415; IF ~10) — Original Research Article
**Status:** Submission-ready (formatted per Elsevier Medical Image Analysis Guide for Authors)
**Open-access fee:** **None required.** Hybrid Elsevier journal; submission on the standard subscription path requires no article-processing charge.

---

## What this repository contains

Public companion to a *Medical Image Analysis* original-research-article submission. Manuscript, figures, source-data files (JSON + CSV), and reproducibility scripts for every numerical claim in the paper.

```
MedIA_Paper/
├── manuscript/
│   ├── Manuscript_for_MedIA.md/.pdf            <- PRIMARY SUBMISSION
│   ├── Manuscript_for_CompBioMed.md            (archived alternative target)
│   ├── Manuscript_v85_for_MedIA.md/.pdf        (archived earlier MedIA version)
│   ├── Manuscript_v83_for_IEEE_TMI.md/.pdf     (archived IEEE TMI alt)
│   ├── Appendix_A_Proofs.md                    (Theorem 2-5 proofs)
│   └── CoverLetter_NMI.md                      (cover letter draft)
├── figures/
│   ├── main/                                   (5 main figures: PNG + 300 DPI TIFF)
│   └── extended_data/                          (16 Extended Data figures at 300 DPI)
├── source_data/                                (Versioned JSON/CSV underlying every numerical claim)
└── scripts/                                    (Python scripts producing source_data files)
```

## Headline empirical findings

- **Multi-cohort empirical benchmark** on 522 paired post-treatment brain-tumour MRI evaluations across 4 genuinely independent cohorts: UCSF-POSTOP (N=296), MU-Glioma-Post (N=151), RHUH-GBM (N=38), UCSD-PTGBM (N=37).
- **5 architecture families × 4 held-out cohorts × 5 seeds**: 20/20 directional preservation under leave-one-cohort-out raw-MRI transfer (binomial p = 9.5 × 10⁻⁷).
- **3-seed UNETR transformer** (12.53 M parameters): direction matches in 12/12 individual seed-cohort conditions (binomial p < 2.5 × 10⁻⁴).
- **Padded 32 × 64 × 64 SwinUNETR**: direction matches in 3/4 cohorts.
- **nnU-Net v2 cross-cohort external evaluation** (mask_only / mask_heat / mask_heat_sdf input variants on UCSF, UCSD, PROTEAS, UPENN): heat-kernel prior outperforms full nnU-Net on surveillance-dominant cohorts, confirming architecture invariance across SIX architecture families.
- **CASRN learned routing network**: operationalises the closed-form theory; beats learned U-Net on 3/4 cohorts; achieves NEGATIVE oracle regret on MU-Glioma-Post.
- **Closed-form composition-shift crossover π* = 0.43** predicts ranking direction in 7/7 cohorts.
- **Multi-class composition-shift theorem** (K ≥ 3) with formal regret bound for the CASRN π-estimator.

## Cohorts indexed

- **UCSF-POSTOP** (GBM post-op surveillance; N=296; π_stable=0.81; tier-1 manual mask)
- **MU-Glioma-Post** (Glioma post-op; N=151; π_stable=0.34; TCIA CC BY 4.0)
- **RHUH-GBM** (GBM post-treatment; N=38; π_stable=0.29; TCIA)
- **UCSD-PTGBM** (Post-treatment GBM; N=37; π_stable=0.24; TCIA CC BY 4.0)
- **LUMIERE** (Glioma IDH cold holdout; N=22 with 3D mask cache; Figshare CC BY 4.0)
- **UPENN-GBM** (GBM tier-3 sensitivity; N=41; TCIA CC BY 4.0)
- **Yale-Brain-Mets-Longitudinal** (Brain mets acquisition shift; N=1,430)
- **PROTEAS-brain-mets** (Brain mets SRS with patient-specific RTDOSE; N=43; Zenodo open access)

## Reproducibility

| File | Description | Maps to |
|---|---|---|
| `v77_ucsf_raw_mri_baseline.json` | UCSF 3-fold internal raw-MRI training | §3.1 |
| `v78_raw_mri_loco.json` | External LOCO across 4 cohorts | §3.2 / Table 1 |
| `v79_raw_loco_seed_robustness.json` | Three-seed lightweight-U-Net robustness | §3.3 |
| `v81_gpu_stronger_raw_loco.json` | Two-seed stronger ResUNet+TTA robustness | §3.3 |
| `v85_transformer_baselines.json` | UNETR seed 8501 LOCO across 4 cohorts | §3.4 / Table 2 |
| `v86_extra_seeds_padded.json` | UNETR seeds 8502/8503 + padded SwinUNETR + UNETR padded sanity | §3.4 / Table 3 |
| `v88_nnunet_cropcache_metrics.json` | nnU-Net v2 cross-cohort external evaluation | §3.12 / Table 5 |
| `v84_E1_improved_rasn.json` | CASRN/RASN learned routing network results | §3.13 / Table 4 |
| `v94_lumiere_cold_holdout.json` | LUMIERE 3D cold-holdout LOCO | §3.14 |
| `v60_yale_expansion.json` | Yale label-free acquisition-shift audit | §3.6 |
| `v84_E3_conformal_coverage.json` | Conformal coverage empirical validation | §3.9 |
| `v84_E4_negative_controls.json` | 9 negative controls quantitative | §3.7 |
| `v84_E5_empirical_bernstein.json` | Empirical-Bernstein PAC-Bayes refinement | §3.8 |
| `master_neurooncology_dataset_index.csv` | 8-cohort master index | Methods §2.1 |

## Hardware / software

NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM), CUDA 12.8. Python 3.11.9; PyTorch 2.12; MONAI 1.5.2 (UNETR + SwinUNETR + nnU-Net); nibabel 5.4.2; NumPy; SciPy 1.17.1; statsmodels (DerSimonian–Laird).

## Companion repository

`MedicalPhysics_Paper` (formerly `RTO_paper`) — companion submission to *Medical Physics* (AAPM / Wiley; physics-grounded structural priors with BED-aware spatially-varying kernel and α/β sensitivity sweep on PROTEAS RTDOSE/RTPLAN).

## Licence

Manuscript and figures: CC BY 4.0 (proposed at acceptance). Code: MIT.

## Contact

**Sheikh Kamrul Islam** — sheikh.islam@kcl.ac.uk (alternative: kamrul0405@outlook.com).
Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences, King's College London.
