# Endpoint-Regime Transfer Governs Ranking Instability in Longitudinal Neuro-Oncology AI

**Target journal:** Nature Machine Intelligence
**Manuscript version:** v8.2 (submission-ready, 2026-05-06)
**Status:** Submission-ready

This repository contains the source manuscript, figures, source-data files and reproducibility scripts for the Nature Machine Intelligence submission.

## Repository structure

```
Nature_MI_paper/
├── manuscript/
│   ├── Final_Nature_MI.md        # Markdown source (v8.2; 149-word abstract; ~2,647 main words)
│   ├── Final_Nature_MI.pdf       # Submission PDF (36 KB)
│   └── CoverLetter_NMI.md        # Cover letter for Nature Machine Intelligence editor
├── figures/
│   ├── main/                     # Main Figure 1 (.png + .tif at 300 DPI)
│   └── extended_data/            # 16 Extended Data figures (.png at 300 DPI)
├── source_data/                  # Versioned JSON/CSV underlying every numerical claim
└── scripts/                      # Python scripts that produced source_data files
```

## Headline results

- Real raw-MRI nnU-Net leave-one-cohort-out (LOCO) experiments across **4 cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N=522 patients)**.
- **Five seeds × two architectures × four cohorts = 20/20 directional preservation** of the heat-prior-vs-raw-MRI ranking outcome.
- Heat prior wins UCSF (Brier 0.108) and UCSD-PTGBM (0.165); raw+mask U-Nets win MU-Glioma-Post (0.274) and RHUH-GBM (0.392).
- Closed-form pre-deployment crossover threshold **pi*=0.43 (95% bootstrap CI [0.30, 0.52]; Bayesian 95% credible interval [0.17, 0.59]; random-effects meta-regression p<0.0001)**.
- UCSD-PTGBM is a **documented counterexample** to a pi-only explanation, demonstrating multi-axis ranking dependence.
- Yale label-free acquisition-shift audit on N=200/1430 patients: domain-classifier AUROC=0.847.

## Reproducibility

Every numerical claim in the manuscript maps to a versioned `source_data/*.json` or `*.csv` file. Each `scripts/v*.py` file is the script that produced one of the JSON/CSV files; see file headers for details.

### Key source-data files

| File | Description |
|---|---|
| `v77_ucsf_raw_mri_baseline.json` | UCSF 3-fold internal raw-MRI training (Result 1) |
| `v78_raw_mri_loco.json` | External LOCO across 4 cohorts (Result 2; Table 1) |
| `v79_raw_loco_seed_robustness.json` | Three-seed lightweight-U-Net robustness (Result 3) |
| `v81_gpu_stronger_raw_loco.json` | Two-seed stronger ResUNet+TTA robustness (Result 3) |
| `v76_nature_upgrade.json` | Bayesian + RE meta-regression + permutation power (Result 5) |
| `v60_yale_expansion.json` | Yale label-free acquisition-shift audit (Result 7ia) |
| `v78_nmi_raw_loco_source_data.csv` | Per-cohort, per-variant Brier values (figure source data) |
| `master_neurooncology_dataset_index.csv` | 8-cohort master index (Methods) |

## Hardware / software

Trained on NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM), CUDA 12.8. Python 3.11.9; PyTorch 2.12; MONAI 1.5.2; nibabel 5.4.2; NumPy 2.4.4; SciPy 1.17.1.

## Companion manuscript

A companion submission is in preparation for *Nature Biomedical Engineering* (`Nature_BME_paper` repository) addressing the orthogonal engineering questions of conditional-use deployment boundaries.

## Citation

[To be added at acceptance.]

## License

Manuscript and figures: CC BY 4.0 (proposed at acceptance).
Code: MIT.

## Contact

Authors blinded for review.
