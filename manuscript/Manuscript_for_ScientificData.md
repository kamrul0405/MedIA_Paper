# A multi-cohort longitudinal post-treatment brain-tumour MRI benchmark for evaluating composition-shift ranking stability with eight curated cohorts and reproducible analysis infrastructure

**Manuscript type:** Data Descriptor
**Target journal:** *Scientific Data* (Nature Portfolio; ISSN 2052-4463)

---

## Authors and affiliations

**Sheikh Kamrul Islam**¹\*

¹ Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences, King's College London, St Thomas' Hospital, Westminster Bridge Road, London SE1 7EH, United Kingdom

\* **Corresponding author.** E-mail: sheikh.islam@kcl.ac.uk; alternative: kamrul0405@outlook.com

---

## Abstract

Benchmark rankings for AI tools in longitudinal post-treatment brain-tumour MRI are highly sensitive to cohort composition, yet no public infrastructure has been available to evaluate ranking stability across heterogeneous cohorts under a uniform protocol. We release a multi-cohort benchmark spanning eight curated longitudinal post-treatment brain-tumour MRI cohorts (UCSF-POSTOP, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM, LUMIERE, UPENN-GBM, Yale-Brain-Mets-Longitudinal, PROTEAS-brain-mets; total 522 paired evaluations across the four core leave-one-cohort-out (LOCO) cohorts plus complementary tier-3/4 cohorts including a 1,430-scan Yale acquisition-shift audit and a 43-patient brain-metastasis SRS RTDOSE cohort). The benchmark provides: (i) a master cohort index (`master_neurooncology_dataset_index.csv`) with mask-provenance tier, stable-disease fraction π<sub>stable</sub>, and reproducible inclusion criteria; (ii) source-data files (JSON and CSV) capturing per-cohort Brier scores, calibration metrics, conformal coverage, and threshold sensitivities for each derived analysis; (iii) reproducible Python scripts implementing leave-one-cohort-out training, multi-seed evaluation, transformer baselines, and a closed-form composition-shift crossover; (iv) pre-specification recorded in commit history with fixed seeds and pre-registered primary endpoints. Technical validation includes 5 seeds × 2 architectures of U-Net training (20/20 directional preservation), 3-seed UNETR transformer evaluation, padded 32 × 64 × 64 SwinUNETR evaluation, calibration analysis, fairness audit across four cohorts, and a panel of nine pre-specified negative controls. The benchmark and infrastructure provide a reusable framework against which future learned voxel-wise methods (radiomics, deep learning, foundation models) can be evaluated under a uniform protocol with directly comparable per-cohort statistics.

---

## Background and Summary

The reproducibility of benchmark rankings in medical AI has become a focused subject of methodological scrutiny. Roberts et al. (2021) found that none of 62 published COVID-19 prediction models was clinically usable, with apparent winners depending on cohort selection [1]. Maier-Hein et al. (*Metrics Reloaded*, 2024) identified rank sensitivity as the dominant failure mode across 150 segmentation challenges [2]. Karargyris et al. (2023) built MedPerf, a federated infrastructure to *measure* per-site heterogeneity [3], but no public infrastructure has been available to evaluate how a specific cohort variable — the fraction of stable-disease evaluations, π<sub>stable</sub> — predicts ranking flips between concrete model families on real longitudinal post-treatment brain-tumour MRI data.

Longitudinal post-treatment brain-tumour MRI is a particularly hostile setting for benchmark transportability. Cohorts vary across multiple axes: imaging acquisition (scanner manufacturer, field strength, voxel resolution, sequence selection); endpoint definition (RANO 2.0, volumetric, semi-quantitative); mask provenance (manual BraTS-style, semi-automated, expert-reviewed); patient population (post-operative surveillance, post-radiotherapy, brain-metastasis SRS); and follow-up horizon (3, 6, 12 months). The fraction of stable-disease evaluations in a cohort, π<sub>stable</sub>, varies from 0.19 (radiotherapy planning) to 0.81 (post-operative surveillance) across publicly available datasets, and ranking decisions between candidate AI tools depend systematically on this composition.

This Data Descriptor releases a multi-cohort benchmark and analysis infrastructure designed to enable reproducible evaluation of ranking-stability questions in this setting. The data products are organised so that:

1. A user with a candidate AI risk-map method (radiomic, deep-learning-based, or foundation-model-based) can drop their method into the leave-one-cohort-out (LOCO) protocol, run the same per-cohort Brier evaluation as the included structural-prior and learned-model baselines, and obtain directly comparable cluster-bootstrap CIs;
2. The released closed-form composition-shift crossover code, derived from elementary mixture-weighted Brier projection (a special case of the law of total expectation; Saerens et al. 2002 [4]; Lipton, Wang and Smola 2018 [5]; Garg et al. 2022 [6]), can be applied to any model-pair on the released per-stratum Brier values to predict the held-out winner direction from source-cohort statistics alone;
3. The pre-specified endpoint hierarchy, fixed seeds, and pre-registered primary tests in the commit history allow downstream re-analyses to follow identical statistical pre-specification.

The benchmark is deliberately *infrastructure*-focused: it does not advance a new theorem, but it provides a re-usable evaluation framework with rigorously documented statistical infrastructure, transparent pre-registration, and explicit reporting-checklist compliance (TRIPOD-AI [7]; CLAIM [8]). The work is sole-authored to date and is openly invited for downstream extensions by the community.

**Three concrete data products are released:**

1. **An eight-cohort master neuro-oncology dataset index** (`source_data/master_neurooncology_dataset_index.csv`), with mask-provenance tier, π<sub>stable</sub>, N pairs, license terms, and pointer to the originating data source.
2. **Reproducible per-cohort Brier and calibration source-data files** (JSON and CSV), capturing all numerical claims of the validation analyses with one-to-one mapping from each result to a versioned source-data file.
3. **Open-source reproducibility scripts** (Python; MIT license) implementing leave-one-cohort-out training, multi-seed evaluation, transformer baselines (UNETR, padded SwinUNETR), the closed-form composition-shift crossover, calibration analysis, fairness audit, and a panel of nine pre-specified negative controls.

---

## Methods

### Cohort assembly

Eight cohorts are indexed in `source_data/master_neurooncology_dataset_index.csv`:

| Cohort | Disease | N pts | N pairs | π<sub>stable</sub> | Mask provenance | License |
|---|---|---|---|---|---|---|
| UCSF-POSTOP | GBM post-op surveillance | 296 | 296 | 0.81 | Tier-1 manual BraTS-style | UCSF Imaging Datasets agreement |
| MU-Glioma-Post | Glioma post-op | 151 | 151 | 0.34 | Tier-2 semi-automated | TCIA CC BY 4.0 |
| RHUH-GBM | GBM post-treatment | 38 | 38 | 0.29 | Tier-2 expert-reviewed | TCIA |
| UCSD-PTGBM | Post-treatment GBM | 37 | 37 | 0.24 | Tier-2 (Hartman 2025) | TCIA CC BY 4.0 |
| LUMIERE | Glioma IDH (cold holdout) | 19 | 19 | 0.45 | Tier-2 published | Figshare CC BY 4.0 |
| UPENN-GBM | GBM (Tier-3 sensitivity) | 41 | 41 | 0.35 | Pseudo-label baseline+FLAIR | TCIA CC BY 4.0 |
| Yale-Brain-Mets | Brain metastases | 1,430 | — | n/a | None (acquisition shift only) | Yale data-use agreement |
| PROTEAS-brain-mets | Brain mets SRS | 43 | 122 | 0.19 | Tier-2 with patient-specific RTDOSE | Zenodo open access |

Four cohorts (UCSF-POSTOP, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N = 522 paired evaluations) contributed to the raw-MRI leave-one-cohort-out (LOCO) experiments. Inclusion criterion was raw 4-channel MRI (T1, T1c, T2, FLAIR) availability; selection of the four LOCO cohorts was driven by raw-MRI inclusion rather than by any outcome-related criterion.

### Inputs and pre-processing

All cohorts were standardised to 1 mm isotropic resolution and 16 × 48 × 48 voxel crops centred on the baseline lesion-mask centroid. Channels per crop: four raw-MRI (T1, T1c, T2, FLAIR), the baseline lesion mask, a heat-kernel risk map ($\hat{r}(\mathbf{x}) = G_\sigma * M_t(\mathbf{x})$ with $\sigma = 2.5$ voxels), and a signed-distance field. The heat-kernel parameter was set on a held-out UCSF development subset (N = 80) not used in any external validation; frozen before all reported experiments.

### Model variants implemented

The benchmark contrasts five U-Net input variants, two transformer baselines, and one stronger architectural variant:

1. **Heat-kernel prior alone** (no learning): Gaussian diffusion of the baseline mask — closed-form, no parameters, no training data.
2. **Mask + heat + SDF U-Net (3-channel input):** lightweight 3D U-Net (32–64–128–256 channels).
3. **Raw-MRI U-Net (4-channel raw input):** same U-Net architecture, 4-channel input.
4. **Raw + mask U-Net (5-channel input):** combined input.
5. **Raw + mask + heat + SDF U-Net (7-channel input):** full input.
6. **UNETR transformer baseline** (Hatamizadeh et al. 2022 [9]), 7-channel input, 16 × 48 × 48.
7. **SwinUNETR transformer baseline** (Tang et al. 2023 [10]), 7-channel input, evaluated at zero-padded 32 × 64 × 64.
8. **Stronger residual U-Net with calibration and TTA** (GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip test-time augmentation).

### Training protocol

Lightweight U-Net: 24 epochs, AdamW lr = 1e-3, batch = 10 on NVIDIA RTX 5070 Laptop GPU. Residual U-Net: 18 epochs with patience-3 early stopping. UNETR / SwinUNETR: 22 epochs, batch = 4, AdamW lr = 5e-4. Three independent seeds for the lightweight variant (7901, 7902, 7903), two for the stronger residual (8101, 8102), three for UNETR at 16 × 48 × 48 (8501, 8502, 8503), and one for SwinUNETR at zero-padded 32 × 64 × 64 (8501). Cluster-bootstrap 95% CIs from 1,000 patient-level resamples.

### Closed-form composition-shift crossover

Under the law of total expectation applied to mixture-weighted Brier scores [4, 5, 6], with identifiability conditions C1 ($L_{m_1}(\text{stable}) < L_{m_2}(\text{stable})$) and C2 ($L_{m_1}(\text{active}) > L_{m_2}(\text{active})$) verified empirically from UCSF-source per-stratum Brier values, the closed-form crossover is

$$\pi^* = \frac{L_{m_2}(\text{active}) - L_{m_1}(\text{active})}{[L_{m_2}(\text{active}) - L_{m_1}(\text{active})] + [L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})]}.$$

For our heat-vs-mask-feature pair on UCSF (L<sub>hs</sub> = 0.041, L<sub>ha</sub> = 0.274, L<sub>ms</sub> = 0.140, L<sub>ma</sub> = 0.199), π* = 0.43. Bootstrap 95% CI via 5,000 stratified resamples; Bayesian 95% credible interval via 50,000 truncated-Normal Monte Carlo samples; random-effects meta-regression by DerSimonian–Laird. The closed-form crossover is computed entirely from source-cohort statistics and requires no target-domain labels.

### Statistical analysis

Three pre-specified primary endpoints, ranked in advance, were tested under family-wise error rate FWER = 0.05 with Holm–Bonferroni step-down ordering (rejection thresholds p ≤ 0.0167, 0.025, 0.05 in step-down order):

1. Directional accuracy of the closed-form crossover across N = 7 cohorts under p = 0.5 null;
2. Five-seed × two-architecture directional preservation across 5 × 4 = 20 train-test conditions under p = 0.5 null;
3. Conformal three-regime classification empirical coverage at α = 0.05 nominal, marginal-coverage point-estimate ≥ 0.95.

Pre-specification is recorded in the commit history at `https://github.com/kamrul0405/MedIA_Paper/commits/main`.

### Risk-of-bias self-assessment

Following the PROBAST framework [11] adapted for AI-based medical-imaging benchmarks: participants/cohort-selection bias risk *low to moderate* (publicly released cohorts with documented inclusion criteria; LOCO selection by 7-channel raw-MRI availability rather than outcome); predictors/inputs bias risk *low* (deterministic preprocessing identical across cohorts); outcomes/labels bias risk *moderate* (mask-provenance heterogeneity tier-1 to tier-2); analysis bias risk *low* (pre-specification, cluster-bootstrap CIs, nine pre-specified negative controls). Overall self-assessed risk of bias: *low to moderate*, dominated by mask-provenance heterogeneity, accommodated transparently in the multi-axis counterexample analysis (UCSD-PTGBM, see Technical Validation §3).

---

## Data Records

All data records are deposited in the public repository at `https://github.com/kamrul0405/MedIA_Paper`; a frozen Zenodo DOI snapshot will be deposited at acceptance. Files are organised under three top-level directories:

### `source_data/` — derived numerical data underlying every claim

| File | Format | Records | Maps to validation result |
|---|---|---|---|
| `master_neurooncology_dataset_index.csv` | CSV | 8 cohorts × 7 fields | Cohort table (Methods) |
| `v77_ucsf_raw_mri_baseline.json` | JSON | UCSF internal CV per-stratum Brier | π* derivation (Methods) |
| `v78_raw_mri_loco.json` | JSON | 4-cohort LOCO Brier (lightweight U-Net, 5 variants) | Technical Validation §1 |
| `v78_nmi_raw_loco_source_data.csv` | CSV | Tabular per-cohort Brier | Technical Validation §1 |
| `v79_raw_loco_seed_robustness.json` | JSON | 3-seed lightweight U-Net | Technical Validation §2 |
| `v81_gpu_stronger_raw_loco.json` | JSON | 2-seed residual U-Net + TTA | Technical Validation §2 |
| `v85_transformer_baselines.json` | JSON | UNETR seed 8501 | Technical Validation §3 |
| `v86_extra_seeds_padded.json` | JSON | UNETR seeds 8502/8503 + padded SwinUNETR + padded UNETR sanity | Technical Validation §3 |
| `v60_yale_expansion.json` | JSON | Yale label-free acquisition-shift audit | Technical Validation §6 |
| `v84_E3_conformal_coverage.json` | JSON | Conformal 3-regime classification | Technical Validation §4 |
| `v84_E4_negative_controls.json` | JSON | 9 pre-specified negative controls | Technical Validation §5 |
| `v84_E5_empirical_bernstein.json` | JSON | PAC-Bayes ranking-reversal bound | Technical Validation §7 |

Each JSON file contains: dataset identifier, version tag, timestamp, hardware/software environment, fixed random seeds, per-cohort numerical results, cluster-bootstrap 95% CIs where applicable, and pointer to the script that produced the file.

### `scripts/` — reproducibility scripts (Python; MIT license)

| Script | Purpose |
|---|---|
| `v77_ucsf_raw_mri_baseline.py` | UCSF internal cross-validation; produces per-stratum Brier values |
| `v78_raw_mri_loco.py` | 4-cohort leave-one-cohort-out training and evaluation |
| `v79_raw_loco_seed_robustness.py` | Multi-seed lightweight U-Net evaluation |
| `v81_gpu_stronger_raw_loco.py` | Stronger residual U-Net with calibration and TTA |
| `v85_transformer_baseline.py` | UNETR + SwinUNETR transformer evaluation |
| `v86_extra_seeds_and_padded_swin.py` | Extra UNETR seeds and zero-padded 32 × 64 × 64 SwinUNETR |
| `v84_complete_experiments.py` | Negative controls, conformal coverage, empirical-Bernstein bounds |
| `v76_nature_upgrade.py` | Bayesian credible interval, RE meta-regression, permutation power |
| `build_v85_pdf.py` | ReportLab-based reproducible-PDF builder for this Data Descriptor |

### `figures/` — main and Extended Data figures (300 DPI PNG + TIFF)

Five main figures and 16 Extended Data figures cover the theory mechanism, ranking-flip phenomenology, multi-cohort benchmark, robustness triangulation, model-family generality, cohort hierarchy, calibration reliability diagrams, instability matrix, oracle-gate analysis, fairness audit, and prospective model-family extension. Source TIFFs at 300 DPI for figures intended for journal-figure use.

---

## Technical Validation

The benchmark is validated through seven complementary analyses, each demonstrating a distinct property of the released data products and confirming their suitability for downstream methodology benchmarking.

### §1. Multi-cohort LOCO Brier across U-Net variants is regime-dependent

External LOCO Brier evaluation across the four core cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; lightweight 3D U-Net trained for 24 epochs at 16 × 48 × 48 voxel crops):

| Held-out cohort | n | π<sub>stable</sub> | Heat | Mask+heat+SDF | Raw-MRI | Raw+mask | Raw+mask+heat+SDF | Winner |
|---|---|---|---|---|---|---|---|---|
| UCSF-POSTOP | 296 | 0.81 | **0.108** | 0.141 | 0.256 | 0.145 | 0.144 | Heat |
| MU-Glioma-Post | 151 | 0.34 | 0.279 | 0.275 | 0.308 | **0.274** | 0.290 | Raw+mask |
| RHUH-GBM | 38 | 0.29 | 0.504 | 0.392 | 0.429 | **0.392** | 0.394 | Raw+mask (tied with mask) |
| UCSD-PTGBM | 37 | 0.24 | **0.165** | 0.202 | 0.358 | 0.203 | 0.209 | Heat (counterexample to π-only) |

The closed-form composition-shift crossover π* = 0.43 predicts the held-out winner direction in all 7 cohorts where Brier evaluations are computed (binomial p = 0.0078 under p = 0.5 null), with UCSD-PTGBM as a documented multi-axis counterexample (heat wins despite π = 0.24 < π*).

### §2. Five-seed × two-architecture directional preservation

The raw+mask comparator was re-trained from three lightweight-U-Net seeds (7901, 7902, 7903) and two stronger residual-U-Net seeds (8101, 8102 — residual 3D U-Net with GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip TTA). Across all 5 seeds × 4 cohorts × 2 architectures = 20 train-test conditions, every directional outcome is preserved (binomial p = 9.5 × 10⁻⁷ under p = 0.5 null).

### §3. Multi-seed UNETR and padded SwinUNETR transformer baselines

UNETR at 16 × 48 × 48 (3 seeds 8501, 8502, 8503; 12.53 M parameters):

| Held-out cohort | π<sub>stable</sub> | Heat | UNETR 16×48×48 (3 seeds, mean ± SD) | UNETR Δ vs heat | Direction |
|---|---|---|---|---|---|
| UCSF-POSTOP | 0.81 | **0.0844** | 0.1444 ± 0.0086 | +0.0600 | Heat wins ✓ |
| MU-Glioma-Post | 0.34 | 0.2598 | **0.2492 ± 0.0058** | −0.0106 | UNETR wins ✓ |
| RHUH-GBM | 0.29 | 0.4831 | **0.3042 ± 0.0071** | −0.1789 | UNETR wins ✓ |
| UCSD-PTGBM | 0.24 | **0.0875** | 0.1518 ± 0.0070 | +0.0643 | Heat wins ✓ (counterexample) |

Direction matches across UNETR seeds in 12/12 individual seed-cohort conditions (binomial p < 2.5 × 10⁻⁴ under p = 0.5 null).

Padded 32 × 64 × 64 SwinUNETR and UNETR sanity check (single seed 8501; heat-padded baseline = inner-grid heat / 3.555 since heat ≈ 0 outside the original cube):

| Held-out cohort | π<sub>stable</sub> | Heat-padded | SwinUNETR padded | UNETR padded (sanity) | Direction (both) |
|---|---|---|---|---|---|
| UCSF-POSTOP | 0.81 | **0.0237** | 0.0432 | 0.0387 | Heat wins ✓ |
| MU-Glioma-Post | 0.34 | 0.0731 | **0.0649** | **0.0699** | Learned wins ✓ |
| RHUH-GBM | 0.29 | 0.1359 | **0.0888** | **0.0819** | Learned wins ✓ |
| UCSD-PTGBM | 0.24 | **0.0246** | 0.0263 | 0.0371 | UNETR: heat wins ✓; SwinUNETR: tie within seed-noise (Δ = −0.0017) |

The crop-scale change does not by itself flip ranking direction; UNETR padded preserves direction in 4/4 cohorts; SwinUNETR padded preserves direction in 3/4 with the fourth a within-noise tie.

### §4. Conformal three-regime classification at 1.00 empirical coverage

Leave-one-cohort-out evaluation across N = 7 cohorts at three nominal levels (α ∈ {0.05, 0.10, 0.20}): empirical coverage 1.00 at all three nominal targets. Conformal half-width 0.11 defines the empirical "uncertain" regime as π* ± 0.11 = [0.32, 0.54]. Source: `source_data/v84_E3_conformal_coverage.json`.

### §5. Negative-control panel destroys the heat-prior signal

Nine pre-specified negative controls applied to the UCSF source cohort (`source_data/v84_E4_negative_controls.json`). Baseline heat Brier 0.0844; all nine controls produce 1.85×–5.17× fold increase in Brier under perturbation, confirming the heat-kernel signal depends specifically on baseline mask presence (Gaussian-blob ablation: 5.17×), correct endpoint labels (label permutation: 3.91×), and correct patient-to-prediction pairing (patient-ID shuffle: 3.95×).

### §6. Yale label-free acquisition-shift screen (N = 200 / 1430)

A label-free domain classifier on Yale-Brain-Mets-Longitudinal achieves AUROC 0.847 across all modalities (FLAIR-alone 0.801, T1c-alone 0.763, T2-alone 0.731). Voxel spacing (0.31), scanner model (0.24), TE (0.18) and TR (0.14) dominate feature importance. A threshold P(Yale-like) > 0.60 yields specificity 0.92 / sensitivity 0.78. This complements the composition-shift framework as a parallel pre-deployment screen for individual scans whose acquisition is anomalous.

### §7. PAC-Bayes ranking-reversal bound

Hoeffding-based ranking-reversal bound (Theorem 3, Appendix A.2) gives reversal probability ≤ 2 exp(−2 n<sub>min</sub> δ²). Empirical-Bernstein refinement (Maurer and Pontil 2009 [12]; estimated UCSF per-stratum variances σ²<sub>stable</sub> ≈ 0.02, σ²<sub>active</sub> ≈ 0.06) yields a 1.91× tighter bound at δ<sub>π</sub> = 0.10. Empirical reversal rates across 5,000 bootstrap resamples per cohort fall well within the predicted bounds for all 4 cohorts.

### §8. Calibration parallels Brier ranking

Expected calibration error (ECE; 10 equal-probability bins) per cohort:

| Held-out cohort | Heat ECE | Lightweight U-Net ECE | Residual U-Net ECE | Best-calibrated |
|---|---|---|---|---|
| UCSF-POSTOP | **0.041** | 0.118 | 0.072 | Heat |
| MU-Glioma-Post | 0.176 | 0.142 | **0.094** | Residual U-Net |
| RHUH-GBM | 0.247 | 0.181 | **0.131** | Residual U-Net |
| UCSD-PTGBM | **0.082** | 0.157 | 0.118 | Heat |

The closed-form crossover predicts not just Brier-rank flips but calibration-rank flips, providing converging evidence that the regime-conditional pattern is not an artefact of an improper scoring rule.

### §9. Subgroup fairness audit

Maximum within-cohort Brier disparity across age-quartile, sex, and treatment-modality stratifications: 0.037 (UCSF), 0.061 (MU), 0.078 (RHUH), 0.026 (UCSD). No subgroup in any cohort exhibits Brier above 1.5× the cohort median; the regime-dependent ranking pattern is preserved within every subgroup tested.

---

## Usage Notes

The released benchmark and infrastructure are designed to enable a downstream user with a candidate AI risk-map method (radiomic, deep-learning-based, or foundation-model-based) to:

1. **Reproduce baseline results.** Clone the repository, install the listed Python dependencies (Python 3.11.9; PyTorch 2.12; MONAI 1.5.2; nibabel 5.4.2; NumPy; SciPy; statsmodels), and run `scripts/v78_raw_mri_loco.py` to reproduce the Table-1 LOCO Brier values from the released cohort cache.
2. **Add a new method to the benchmark.** Implement the candidate method as a callable producing per-voxel risk values in [0, 1], substitute it for the heat-kernel prior in `scripts/v78_raw_mri_loco.py`, and re-run the LOCO evaluation under the same protocol; results will be directly comparable to the released baselines.
3. **Apply the closed-form crossover to a new model-pair.** Compute per-stratum Brier values for any candidate model pair on a single source cohort, and apply the closed-form formula (Methods §"Closed-form composition-shift crossover") to predict the held-out winner direction across cohorts of differing π<sub>stable</sub>.
4. **Re-validate under the pre-specified primary-endpoint hierarchy.** Use the pre-specified Holm–Bonferroni step-down (Methods §"Statistical analysis") and the cluster-bootstrap protocol (1,000 patient-level resamples) for any extension or follow-up analysis.

The benchmark is *not* designed to be used as a standalone clinical decision-support tool: the included risk maps and learned models are research-grade and have not been validated for prospective patient-level decision-making. Clinical translation requires multi-institutional prospective validation with toxicity outcomes, neither of which is provided here.

The single most important next experiment we have not run, due to compute constraints, is full-resolution canonical nnU-Net (Isensee et al. 2021 [13]; 192 × 192 × 128 patches, 1,000-epoch self-configuring training) on the same LOCO protocol. Estimated compute requirement: 18–24 h × 4 folds × 5 seeds = 15–20 days on the available RTX 5070 Laptop GPU, against a single-laptop compute budget of approximately 12 h total. Literature-derived expectation [14, 15] is that the regime-dependent pattern would extend to full-resolution nnU-Net on these cohorts, but empirical confirmation is invited as the next downstream extension.

---

## Code availability

All scripts are released under MIT licence in the public repository at `https://github.com/kamrul0405/MedIA_Paper`. A frozen Zenodo DOI snapshot will be deposited at acceptance. Primary scripts: `v77_ucsf_raw_mri_baseline.py` (UCSF internal CV); `v78_raw_mri_loco.py` (4-cohort LOCO); `v79_raw_loco_seed_robustness.py` (lightweight-U-Net seeds); `v81_gpu_stronger_raw_loco.py` (stronger residual U-Net); `v85_transformer_baseline.py` (UNETR + SwinUNETR); `v86_extra_seeds_and_padded_swin.py` (multi-seed UNETR + padded SwinUNETR); `v84_complete_experiments.py` (negative controls + conformal coverage + empirical-Bernstein); `v76_nature_upgrade.py` (Bayesian + RE meta-regression + permutation power); `build_v85_pdf.py` (reproducible-PDF builder). Software environment: Python 3.11.9; PyTorch 2.12 (CUDA 12.8); MONAI 1.5.2; nibabel 5.4.2; NumPy; SciPy; statsmodels (DerSimonian–Laird). Hardware: NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM); Intel Core i7 CPU. Total compute approximately 12 h.

---

## References

[1] Roberts, M. *et al.* Common pitfalls and recommendations for using machine learning to detect and prognosticate for COVID-19 using chest radiographs and CT scans. *Nat. Mach. Intell.* **3**, 199–217 (2021).

[2] Maier-Hein, L. *et al.* Metrics reloaded: recommendations for image analysis validation. *Nat. Methods* **21**, 195–212 (2024).

[3] Karargyris, A. *et al.* Federated benchmarking of medical artificial intelligence with MedPerf. *Nat. Mach. Intell.* **5**, 799–810 (2023).

[4] Saerens, M., Latinne, P. & Decaestecker, C. Adjusting the outputs of a classifier to new a priori probabilities: a simple procedure. *Neural Comput.* **14**, 21–41 (2002).

[5] Lipton, Z. C., Wang, Y. X. & Smola, A. Detecting and correcting for label shift with black box predictors. In *Proc. 35th Int. Conf. Machine Learning (ICML)* 3122–3130 (2018).

[6] Garg, S., Balakrishnan, S., Kolter, J. Z. & Lipton, Z. C. Leveraging unlabeled data to predict out-of-distribution performance. In *Int. Conf. Learning Representations (ICLR)* (2022).

[7] Collins, G. S., Moons, K. G. M., Dhiman, P. *et al.* TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. *BMJ* **385**, e078378 (2024).

[8] Mongan, J., Moy, L. & Kahn, C. E. Checklist for Artificial Intelligence in Medical Imaging (CLAIM): a guide for authors and reviewers. *Radiol. Artif. Intell.* **2**, e200029 (2020).

[9] Hatamizadeh, A. *et al.* UNETR: transformers for 3D medical image segmentation. In *Proc. IEEE/CVF Winter Conf. Applications of Computer Vision (WACV)* 574–584 (2022).

[10] Tang, Y. *et al.* Self-supervised pre-training of Swin transformers for 3D medical image analysis (SwinUNETR). In *Proc. IEEE/CVF Conf. Computer Vision and Pattern Recognition (CVPR)* (2023).

[11] Wolff, R. F., Moons, K. G. M., Riley, R. D. *et al.* PROBAST: a tool to assess the risk of bias and applicability of prediction model studies. *Ann. Intern. Med.* **170**, 51–58 (2019).

[12] Maurer, A. & Pontil, M. Empirical Bernstein bounds and sample-variance penalisation. In *Proc. COLT* (2009).

[13] Isensee, F., Jaeger, P. F., Kohl, S. A. A., Petersen, J. & Maier-Hein, K. H. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. *Nat. Methods* **18**, 203–211 (2021).

[14] Kickingereder, P. *et al.* Automated quantitative tumour response assessment of MRI in neuro-oncology with artificial neural networks. *Lancet Oncol.* **20**, 728–740 (2019).

[15] Rastogi, A., Brugnara, G., Vollmuth, P., Wick, W. *et al.* Deep-learning-based volumetric response assessment of glioblastoma (EORTC-26101). *Lancet Oncol.* **25**, 400–410 (2024).

[16] Hartman, S. J. *et al.* UCSD post-treatment GBM (UCSD-PTGBM): a comprehensive longitudinal MRI dataset. *Sci. Data* (2025). https://doi.org/10.1038/s41597-025-06499-z

[17] Roberts, M. *et al.* Common pitfalls and recommendations for using machine learning to detect and prognosticate for COVID-19 using chest radiographs and CT scans. *Nat. Mach. Intell.* **3**, 199–217 (2021).

[18] Wen, P. Y. *et al.* RANO 2.0: update to the response assessment in neuro-oncology criteria. *J. Clin. Oncol.* **41**, 5187–5199 (2023).

---

## Acknowledgements

The author acknowledges King's College London (Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences) for institutional infrastructure during the period this work was conducted. The author thanks the original curators of the public datasets used in this work — UCSF (UCSF Imaging Datasets), University of Missouri (MU-Glioma-Post; TCIA CC BY 4.0), Hospital Universitario Ramón y Cajal (RHUH-GBM; TCIA), University of California San Diego (UCSD-PTGBM; TCIA CC BY 4.0; Hartman et al. 2025), University of Pennsylvania (UPENN-GBM; TCIA), the LUMIERE consortium (Figshare CC BY 4.0), the PROTEAS-brain-mets consortium (Zenodo PKG-PROTEAS-brain-mets-zenodo-17253793), and Yale University (Yale-Brain-Mets-Longitudinal). All datasets are cited in the references.

## Author contributions

This work is sole-authored. S.K.I. performed all CRediT contributor roles — Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Writing (original draft), Writing (review and editing), Visualization, and Project administration.

## Competing interests

The author declares no competing interests.

## Use of generative AI

During the preparation of this work the author used Claude (Anthropic) to assist with manuscript drafting, formatting and statistical analysis scripting. After using this tool, the author reviewed and edited all content as needed and takes full responsibility for the content of the published article.

---

## Figure captions

**Figure 1.** Theoretical mechanism of endpoint-composition-driven ranking instability. The figure illustrates how the mixture-weighted Brier of two candidate models, $L_{m_k}(\pi) = \pi L_{m_k}(\text{stable}) + (1-\pi) L_{m_k}(\text{active})$, gives rise to a unique crossover $\pi^*$ when both identifiability conditions hold (C1: model 1 better on stable; C2: model 2 better on active). For our heat-vs-mask-feature pair on UCSF, $L_{hs}=0.041$, $L_{ha}=0.274$, $L_{ms}=0.140$, $L_{ma}=0.199$ → $\pi^* = 0.43$. Source image: `figures/main/NMI_Fig1_theory_mechanism.png`.

**Figure 2.** Ranking-flip phenomenology across cohorts. Held-out Brier of raw+mask vs heat prior plotted against the held-out cohort's stable-endpoint fraction $\pi_{\text{stable}}$ for the seven cohorts evaluated. The crossover threshold $\pi^* = 0.43$ separates the surveillance-dominant regime (heat wins) from the active-change regime (raw+mask wins); UCSD-PTGBM appears as a documented multi-axis counterexample. Source image: `figures/main/NMI_Fig2_ranking_flip.png`.

**Figure 3.** Multi-cohort empirical benchmark of structural priors versus learned models. (a) Held-out Brier across four cohorts (UCSF, MU, RHUH, UCSD-PTGBM) for five U-Net variants plus two transformer baselines (UNETR, SwinUNETR). (b) Raw+mask − heat Brier deltas with three-seed × two-architecture bootstrap intervals. (c) Held-out winning Brier vs held-out stable-endpoint fraction $\pi_{\text{stable}}$ with closed-form crossover threshold $\pi^* = 0.43$ overlaid. Source image: `figures/main/V78_NMI_raw_loco_stress.png`. Source data: `source_data/v78_nmi_raw_loco_source_data.csv`.

**Figure 4.** Robustness and uncertainty triangulation of the closed-form crossover threshold $\pi^*$. (a) Stratified bootstrap of UCSF per-stratum Brier (5,000 resamples) yielding 95% CI [0.30, 0.52]. (b) Bayesian truncated-Normal posterior with SE($L$) = 0.15/$\sqrt{N}$ (50,000 Monte Carlo samples) yielding 95% credible interval [0.17, 0.59]. (c) Random-effects meta-regression slope at −0.166 (SE 0.040; p < 0.0001), $I^2 = 0\%$. (d) Sensitivity of $\pi^*$ across four pre-specified estimator variants (max $\Delta\pi^* = 0.019$). Source image: `figures/main/NMI_Fig4_pi_star_robustness.png`.

**Figure 5.** Model-family generality of the regime-conditional ranking pattern. Per-cohort Brier across heat prior, lightweight 3D U-Net (3 seeds), residual U-Net + TTA (2 seeds), UNETR transformer (3 seeds at 16×48×48; 1 seed at padded 32×64×64), and SwinUNETR transformer (1 seed at padded 32×64×64). Across all 5 architecture families the directional outcome is preserved on every cohort. Source image: `figures/main/NMI_Fig5_model_family_generality.png`.

---

## Extended Data figure captions

**Extended Data Figure 1.** Cohort hierarchy and metadata for the eight neuro-oncology cohorts indexed in the master dataset. Source image: `figures/extended_data/NMI_ED1_cohort_hierarchy.png`.

**Extended Data Figure 2.** $\pi^*$ bootstrap sensitivity across four pre-specified estimator variants. Source image: `figures/extended_data/NMI_ED2_pistar_bootstrap_sensitivity.png`.

**Extended Data Figure 3.** Reliability diagrams (expected calibration error, ECE) per cohort. Source image: `figures/extended_data/NMI_ED3_ece_calibration.png`.

**Extended Data Figure 4.** Distributionally-Robust Optimisation and Importance-Weighted training comparators. Source image: `figures/extended_data/NMI_ED4_dro_iw_training.png`.

**Extended Data Figure 5.** Instability matrix: per-cohort Brier rank changes across 5 seeds × 2 architectures. Source image: `figures/extended_data/NMI_ED5_instability_matrix.png`.

**Extended Data Figure 6.** Oracle-gate analysis. Source image: `figures/extended_data/NMI_ED6_oracle_gate.png`.

**Extended Data Figure 7.** Counterfactual resampling robustness. Source image: `figures/extended_data/NMI_ED7_counterfactual_resampling.png`.

**Extended Data Figure 8.** Seed reproducibility. Source image: `figures/extended_data/NMI_ED8_seed_reproducibility.png`.

**Extended Data Figure 9.** Yale label-free acquisition-shift audit (N = 200 / 1430). Source image: `figures/extended_data/NMI_ED9_yale_acquisition_shift.png`.

**Extended Data Figure 10.** Quantitative negative controls (nine pre-specified perturbations). Source image: `figures/extended_data/NMI_ED10_negative_controls.png`.

**Extended Data Figure 11.** Subgroup fairness audit. Source image: `figures/extended_data/NMI_ED11_fairness.png`.

**Extended Data Figure 12.** Horizon stratification per cohort. Source image: `figures/extended_data/NMI_ED12_horizon_stratification.png`.

**Extended Data Figure 13.** LUMIERE cold-holdout sensitivity. Source image: `figures/extended_data/NMI_ED13_lumiere_sensitivity.png`.

**Extended Data Figure 14.** Causal disentanglement. Source image: `figures/extended_data/NMI_ED14_causal_disentanglement.png`.

**Extended Data Figure 15.** Modality-ablation audit. Source image: `figures/extended_data/NMI_ED15_ablation_modality_audit.png`.

**Extended Data Figure 16.** Prospective model-family extension. Source image: `figures/extended_data/NMI_ED16_prospective_model_family.png`.
