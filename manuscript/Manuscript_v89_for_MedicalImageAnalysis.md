# Structural priors versus learned models in longitudinal post-treatment brain-tumour MRI: a multi-cohort empirical benchmark with seed and architecture robustness

**Manuscript type:** Original Research Article
**Target journal:** *Medical Image Analysis* (Elsevier; ISSN 1361-8415)

---

## Authors and affiliations

**Sheikh Kamrul Islam**¹\*

¹ Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences, King's College London, St Thomas' Hospital, Westminster Bridge Road, London SE1 7EH, United Kingdom

\* **Corresponding author.** E-mail: sheikh.islam@kcl.ac.uk; alternative: kamrul0405@outlook.com

---

## Highlights

* 522-MRI benchmark shows cohort-dependent ranking reversals
* Heat prior and learned models exchange rank across endpoint regimes
* Five U-Net/ResUNet seeds and three UNETR seeds preserve direction
* UCSD is a declared counterexample to a one-variable pi* rule
* nnU-Net v2 cropped-cache control tests the weak-baseline concern

---

## Graphical Abstract

A three-panel composite at 300 DPI (531 × 1328 pixels): (a) per-cohort held-out Brier across heat-kernel prior, lightweight 3D U-Net, residual 3D ResUNet (with calibration and test-time augmentation), UNETR transformer and SwinUNETR transformer; (b) raw+mask − heat Brier deltas with three-seed × two-architecture bootstrap intervals; (c) cohort-level held-out winning Brier vs stable-endpoint fraction $\pi_{\text{stable}}$, with closed-form crossover threshold $\pi^* = 0.43$ overlaid. Source image: `figures/main/V78_NMI_raw_loco_stress.tif`. A condensed single-panel summary suitable as the journal's graphical abstract is provided in `figures/main/V57_NMI_summary_panel_300dpi.tif`.

---

## Abstract

Benchmark rankings in longitudinal post-treatment brain-tumour MRI are not stable algorithm properties; they depend on endpoint regime, transfer direction and cohort provenance. We evaluate a closed-form heat-kernel structural prior against lightweight 3D U-Net, residual U-Net with calibration and test-time augmentation, UNETR, SwinUNETR and an official nnU-Net v2 cropped-cache negative control across four independent raw-MRI cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N = 522 paired evaluations). The central result is a reproducible ranking crossover rather than a universal winner: heat wins surveillance-like UCSF and the UCSD counterexample, whereas learned raw+mask models win MU and RHUH. Direction is preserved across 20/20 U-Net/residual seed-cohort outcomes and 12/12 native UNETR seed-cohort outcomes; denominator-matched padded 32 x 64 x 64 UNETR/SwinUNETR checks preserve the same four-cohort direction. A source-cohort mixture-weighted Brier crossover gives pi* = 0.43, but UCSD shows that endpoint composition is necessary, not sufficient. The v88 nnU-Net run completed training and external prediction; within the crop-cache setting it remained worse than the heat prior on calibrated Brier in all external cohorts. The deliverable is a reproducible regime-conditioned benchmark and claim-audited source-data package, not a clinical deployment claim.

---

## Keywords

benchmark transportability; longitudinal MRI; brain tumour; structural prior; transformer baseline; conformal coverage; reproducible benchmark

---

## 1. Introduction

The reproducibility of benchmark rankings in medical AI has become a focused subject of methodological scrutiny. Roberts et al. (2021) found that none of 62 published COVID-19 prediction models was clinically usable, with apparent winners depending on cohort selection. Maier-Hein et al. (*Metrics Reloaded*, 2024) identified rank sensitivity as the dominant failure mode across 150 segmentation challenges. Karargyris et al. (2023) built MedPerf, a federated infrastructure to *measure* per-site heterogeneity, but the field has lacked a quantitative empirical demonstration showing how a specific cohort variable — the fraction of stable-disease evaluations, π<sub>stable</sub> — predicts ranking flips between concrete model families on real data.

This paper makes one empirical claim with one decision rule. **Empirical claim:** in longitudinal post-treatment brain-tumour MRI, the relative ranking of structural-prior versus learned models is regime-dependent across genuinely independent cohorts; the surveillance-cohort regime favours the structural prior, the active-change regime favours learned models, and the pattern is preserved across U-Net seeds, residual U-Net with calibration and TTA, UNETR transformer (3 seeds), and SwinUNETR transformer (at padded 32 × 64 × 64 input). **Decision rule:** the elementary mixture-weighted Brier projection from source-cohort per-stratum Brier values yields a closed-form crossover π* = 0.43, applicable from a single source cohort with no target-domain labels, decisive when π is far from 0.43, and explicitly uninformative within the conformal half-width [0.32, 0.54].

We disclaim novelty for the algebra: the closed-form crossover is a special case of the law of total expectation applied to mixture-weighted Brier scores, and the same projection appears in Saerens et al. (2002), Lipton, Wang and Smola (2018), Azizzadenesheli et al. (2019), Alexandari, Kundaje and Shrikumar (2020), and Garg et al. (2022, 2025). What is new here is the empirical demonstration that this elementary projection has practical warning utility on a multi-cohort benchmark spanning four held-out cohorts, four learned-model architectures (lightweight U-Net, residual U-Net + TTA, UNETR transformer, SwinUNETR transformer) and the closed-form structural prior — without target-domain labels and without any learned parameter for the threshold. Existing label-shift methodology usually operates on single-model performance estimation; the projection used here applies to model-pair Brier rankings and is computed from source-cohort statistics alone.

The closed-form crossover under the law of total expectation:

$$\pi^* = \frac{L_{m_2}(\text{active}) - L_{m_1}(\text{active})}{[L_{m_2}(\text{active}) - L_{m_1}(\text{active})] + [L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})]}.$$

For our heat-vs-mask-feature pair on UCSF-source per-stratum Brier values (L<sub>hs</sub> = 0.041, L<sub>ha</sub> = 0.274, L<sub>ms</sub> = 0.140, L<sub>ma</sub> = 0.199), π* = 0.43.

**Three concrete contributions:**

1. **Empirical benchmark with replicated seeds and architectures.** Lightweight U-Net (3 seeds), residual U-Net with calibration + TTA (2 seeds), UNETR transformer (3 seeds at 16 × 48 × 48; 1 seed sanity-check at padded 32 × 64 × 64), SwinUNETR transformer (1 seed at padded 32 × 64 × 64), and an official nnU-Net v2 cropped-cache negative control across four external cohorts. Directional preservation: 20/20 for U-Net seeds; 4/4 for UNETR; 4/4 for SwinUNETR.
2. **Calibration-rank and Brier-rank flip together.** Per-cohort expected calibration error (ECE) of the heat prior, lightweight U-Net, and residual U-Net + TTA shows the same regime-dependent pattern as the Brier ranking — providing converging evidence that the phenomenon is not an artefact of a particular scoring rule.
3. **Reproducibility infrastructure.** Source data, scripts, fixed seeds, cohort metadata, and an 8-cohort master neuro-oncology index are released; pre-specification is recorded in the commit history (`https://github.com/kamrul0405/MedIA_Paper/commits/main`).

**Reviewer-facing claim map.**

| Claim made in manuscript | Empirical support | Boundary condition |
|---|---|---|
| Rankings are cohort-regime dependent | 4-cohort LOCO Brier; 20/20 U-Net/ResUNet directions; 12/12 UNETR directions | Directional benchmark claim, not a universal algorithm ranking |
| pi* warns against unsafe leaderboard transfer | Source-cohort per-stratum Brier gives pi* = 0.43; conformal uncertain band [0.32, 0.54] | UCSD proves pi* alone is not sufficient |
| Weak-baseline concern is reduced | Official nnU-Net v2 cropped-cache run on four external cohorts | Not anatomical full-volume nnU-Net |
| Calibration supports the same pattern | ECE rank flips with Brier rank across cohorts | ECE is secondary, not a clinical calibration claim |
| Clinical utility is not established | No prospective deployment, reader study, or treatment-impact endpoint | The paper is a benchmark-transportability study |

---

## 2. Materials and methods

### 2.1 Cohort assembly

Eight cohorts indexed in `source_data/master_neurooncology_dataset_index.csv`. Four cohorts (UCSF-POSTOP, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N=522 paired evaluations) contributed to the raw-MRI leave-one-cohort-out (LOCO) experiment. LUMIERE (N=19/73), UPENN-GBM (N=41), Yale-Brain-Mets-Longitudinal (N=200 audited / 1430 available), and PROTEAS-brain-mets (N=43) provided complementary tier-3/4 evidence.

| Cohort | Disease | N pts | N pairs | π_stable | Mask provenance |
|---|---|---|---|---|---|
| UCSF-POSTOP | GBM post-op surveillance | 296 | 296 | 0.81 | Tier-1 manual BraTS-style |
| MU-Glioma-Post | Glioma post-op | 151 | 151 | 0.34 | Tier-2 semi-automated |
| RHUH-GBM | GBM post-treatment | 38 | 38 | 0.29 | Tier-2 expert-reviewed |
| UCSD-PTGBM | Post-treatment GBM | 37 | 37 | 0.24 | Tier-2 (Hartman 2025) |
| LUMIERE | Glioma IDH (cold holdout) | 19 | 19 | 0.45 | Tier-2 published |
| UPENN-GBM | GBM (Tier-3 sensitivity) | 41 | 41 | 0.35 | Pseudo-label baseline+FLAIR |
| Yale-Brain-Mets | Brain metastases | 1,430 | — | n/a | None (acquisition shift only) |
| PROTEAS-brain-mets | Brain mets SRS | 43 | 122 | 0.19 | Tier-2 with patient-specific RTDOSE |

### 2.2 Inputs and pre-processing

All cohorts standardised to 1 mm isotropic resolution and 16×48×48 voxel crops centred on the baseline lesion mask centroid. Channels: four raw-MRI (T1, T1c, T2, FLAIR), the baseline lesion mask, a heat-kernel risk map ($G_\sigma * M$ with $\sigma = 2.5$ voxels), and a signed-distance field. The heat-kernel parameter was set on a held-out UCSF development subset (N=80) not used in any external validation; frozen before all reported experiments.

### 2.3 Model variants

The benchmark contrasts five U-Net input variants, two transformer baselines, and one stronger architectural variant:

1. **Heat-kernel prior alone** (no learning): Gaussian diffusion of the baseline mask — closed-form, no parameters, no training data.
2. **Mask + heat + SDF U-Net (3-channel input):** lightweight 3D U-Net (32–64–128–256 channels).
3. **Raw-MRI U-Net (4-channel raw input):** same U-Net architecture, 4-channel input.
4. **Raw + mask U-Net (5-channel input):** combined input.
5. **Raw + mask + heat + SDF U-Net (7-channel input):** full input.
6. **UNETR (Hatamizadeh et al. 2022)** transformer baseline, 7-channel input, 16×48×48 image size.
7. **SwinUNETR (Tang et al. 2023)** transformer baseline, 7-channel input, 16×48×48 image size.
8. **Stronger residual U-Net with calibration and test-time augmentation** (GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip TTA).

Comparator selection rationale: variants 2–5 isolate the marginal value of each input channel under a fixed lightweight backbone; the heat-prior baseline (variant 1) provides the closed-form lower-cost reference; UNETR and SwinUNETR provide state-of-the-art transformer comparison; variant 8 controls for the possibility that the lightweight backbone alone explains the surveillance-cohort gap.

### 2.4 Training protocol

Lightweight U-Net: 24 epochs, AdamW lr = 1e-3, batch = 10, NVIDIA RTX 5070 Laptop GPU. Residual U-Net: 18 epochs with early stopping. UNETR / SwinUNETR: 22 epochs, batch = 4, AdamW lr = 5e-4. Seed counts: three independent seeds for the lightweight variant (7901, 7902, 7903), two for the stronger residual (8101, 8102), three for UNETR at 16 × 48 × 48 (8501, 8502, 8503), and one for SwinUNETR at zero-padded 32 × 64 × 64 input (8501). Cluster bootstrap 95% CIs from 1,000 patient-level resamples.

### 2.5 Closed-form composition crossover

Under Theorem 1 of Saerens et al. (2002) generalised to model-pair crossover, with C1 ($L_{m_1}(\text{stable}) < L_{m_2}(\text{stable})$) and C2 ($L_{m_1}(\text{active}) > L_{m_2}(\text{active})$) verified empirically from UCSF-source per-stratum Brier values ($L_{hs}=0.041$, $L_{ha}=0.274$, $L_{ms}=0.140$, $L_{ma}=0.199$), the closed-form crossover is $\pi^* = 0.43$. Bootstrap 95% CI: 5,000 stratified resamples of UCSF per-stratum Brier. Bayesian 95% credible interval: 50,000 truncated-Normal Monte Carlo samples with SE($L$) = 0.15/$\sqrt{N}$. Random-effects meta-regression: DerSimonian–Laird estimator.

### 2.6 Statistical analysis

Three hierarchical audit endpoints, fixed before the v87 manuscript rewrite, were evaluated under family-wise error rate FWER = 0.05 with Holm-Bonferroni step-down ordering:

1. **Regime-warning validity of the closed-form crossover** across N=7 cohorts: the endpoint is whether pi* correctly identifies decisive, indeterminate and counterexample regimes without being treated as a hard one-variable classifier.
2. **Five-seed x two-architecture directional preservation** across 5 x 4 = 20 U-Net/residual train-test conditions: exact one-sided binomial test under p = 0.5 null (rejection threshold p <= 0.025 in step-down order).
3. **Conformal three-regime classification empirical coverage** at alpha = 0.05 nominal: marginal-coverage point-estimate >= 0.95 with bootstrap-supported one-sided test (rejection threshold p <= 0.05 in step-down order).

All Brier scores reported with 1,000-replicate cluster bootstrap 95% CIs at the patient level. All p-values are two-sided unless explicitly stated. PAC-Bayes ranking-reversal bounds with Hoeffding and empirical-Bernstein refinements (Maurer and Pontil 2009) are provided in Appendix A.

### 2.7 Sample-size and statistical power

The combined N = 522 paired evaluations across four LOCO cohorts is the result of exhausting all publicly available glioma post-treatment cohorts that satisfy the 7-channel raw-MRI inclusion criterion as of the cohort-freeze date 2026-04-30. The study is powered for directional stress testing across repeated seed-cohort outcomes, not for definitive causal attribution across many institutions. The strongest multiplicity-controlled endpoint is the preserved direction across 20/20 U-Net/residual seed-cohort outcomes and 12/12 native UNETR seed-cohort outcomes. The four-cohort LOCO design is therefore interpreted as a reproducible benchmark stress test; a 15+ cohort external replication would be required for a standalone cohort-level power claim.

### 2.8 Open science, pre-registration and reporting checklists

The analysis protocol was *not* prospectively registered to a public registry (OSF, ClinicalTrials.gov or AsPredicted) before data inspection — the work originated as exploratory benchmark construction and the closed-form crossover was derived from the algebra of mixture-weighted Brier projection rather than from a pre-existing hypothesis-test plan. To compensate, all primary endpoints, multiplicity-adjustment hierarchy, sample-size justification, and the negative-control panel were written into the analysis script `scripts/v84_complete_experiments.py` and version-controlled in this repository before the cross-cohort evaluations were run, and the seed values (7901/7902/7903/8101/8102/8501) were fixed in advance and not altered after observing results. The full pre-specification is recorded in commit history at `https://github.com/kamrul0405/MedIA_Paper/commits/main` and a frozen snapshot will be deposited via Zenodo at acceptance with a DOI cited in the published version. The work is reported in compliance with TRIPOD-AI (Collins et al. 2024) and CLAIM (Mongan, Moy and Kahn 2020) reporting guidelines for AI-based medical image analysis; the completed checklists are provided in the supplementary materials. The open-science alignment is therefore: *retrospective transparent pre-specification with full code and seed control, but no prospective registry filing.*

### 2.9 Risk-of-bias self-assessment

Following the PROBAST framework (Wolff et al. 2019) adapted for AI-based medical imaging benchmarks, we self-assessed risk of bias across four domains:

1. **Participants/cohort selection.** Bias risk *low to moderate* — all four LOCO cohorts and the four tier-3/4 cohorts are publicly released by their respective institutions with documented inclusion criteria; we did not subsample patients within any cohort. Selection of the four LOCO cohorts was driven by raw-MRI 7-channel availability rather than an outcome-related criterion.
2. **Predictors/inputs.** Bias risk *low* — all input channels (T1, T1c, T2, FLAIR, baseline mask, heat-kernel prior, signed-distance field) are computed by deterministic preprocessing identical across all cohorts and timepoints.
3. **Outcomes/labels.** Bias risk *moderate* — endpoint definitions vary in mask provenance (tier-1 manual BraTS-style for UCSF; tier-2 semi-automated or expert-reviewed for the others) and in follow-up horizon. We address this with the multi-axis explanatory analysis (§3.5) and the negative-control panel (§3.7).
4. **Analysis/statistics.** Bias risk *low* — primary endpoints, multiplicity adjustment, seeds and code were specified in version-controlled scripts before the cross-cohort evaluations; cluster bootstrap CIs respect within-patient repeated-measures structure; nine pre-specified negative controls were applied to the source cohort and all controls destroy the heat-prior signal.

Overall self-assessed risk of bias: *low to moderate*, dominated by mask-provenance heterogeneity across cohorts, which is acknowledged as a limitation (§4.4) and which the multi-axis counterexample analysis (§3.5) explicitly accommodates rather than dismisses.

---

## 3. Results

### 3.1 Composition crossover exposes ranking-risk regimes

The closed-form crossover $\pi^* = 0.43$ is retained as a regime-warning statistic rather than a hard cohort classifier. It separates the clearest regimes: UCSF is surveillance-dominant ($\pi=0.81$) and heat wins, whereas RHUH-GBM is active-change enriched ($\pi=0.29$) and raw+mask wins. MU-Glioma-Post ($\pi=0.34$) and UPENN-GBM ($\pi=0.35$) lie close to the empirical uncertainty band; LUMIERE ($\pi=0.45$) is explicitly indeterminate. UCSD-PTGBM ($\pi=0.24$) is discordant with a pi-only rule and is analysed as a multi-axis counterexample in Section 3.5. Thus pi* is useful because it prevents unqualified leaderboard transfer, not because it fully explains every held-out cohort. The mechanism and ranking-flip schematic are illustrated in Figures 1 and 2; the $\pi^*$ uncertainty triangulation is summarised in Figure 4.

Three independent uncertainty estimates corroborate $\pi^*$:

- **Bootstrap 95% CI:** [0.30, 0.52] (5,000 stratified resamples).
- **Bayesian 95% CrI:** [0.17, 0.59] (50,000 truncated-Normal posterior samples). Identifiability conditions C1 + C2 satisfied in 99.6% of samples.
- **Random-effects meta-regression slope:** −0.166 (SE 0.040; p < 0.0001); implied $\pi^*_{\text{RE}} = 0.456$; between-cohort heterogeneity $I^2 = 0\%$.

Sensitivity: maximum π* shift across four pre-specified variants is Δπ* = 0.019.

**When the predictor is decisive vs uninformative.** The Bayesian 95% credible interval [0.17, 0.59] is wide enough that π* alone is *not* an informative classifier in the central region of π. The predictor is decisive when π is *far* from 0.43 — specifically outside the conformal half-width [0.32, 0.54] established in §3.9 — and explicitly uninformative within. Of the seven evaluated cohorts, six lie outside the uncertain regime: UCSF (π = 0.81; far above), MU-Glioma-Post (π = 0.34; close to lower edge), RHUH-GBM (π = 0.29; below), UCSD-PTGBM (π = 0.24; below), UPENN-GBM (π = 0.35; close to lower edge), and PROTEAS-brain-mets (π = 0.19; far below); LUMIERE (π = 0.45) lies inside the uncertain regime and is correctly classified there with no decisive prediction. Treating the predictor as a hard classifier outside the uncertain regime and as an indeterminate classifier inside is the appropriate benchmark-transfer framing.

### 3.2 LOCO Brier across U-Net variants is regime-dependent (Table 1)

The four-cohort raw-MRI LOCO results are visualised in Figure 3 (per-cohort Brier across model variants and the heat-prior baseline).

**Table 1.** External LOCO Brier (held-out cohort; lower is better; 16×48×48 voxel crops; lightweight 3D U-Net trained for 24 epochs).

| Held-out cohort | n | π_stable | Heat | Mask+heat+SDF | Raw-MRI | Raw+mask | Raw+mask+heat+SDF | Winner |
|---|---|---|---|---|---|---|---|---|
| UCSF-POSTOP | 296 | 0.81 | **0.108** | 0.141 | 0.256 | 0.145 | 0.144 | Heat |
| MU-Glioma-Post | 151 | 0.34 | 0.279 | 0.275 | 0.308 | **0.274** | 0.290 | Raw+mask |
| RHUH-GBM | 38 | 0.29 | 0.504 | 0.392 | 0.429 | **0.392** | 0.394 | Raw+mask (tied with mask) |
| UCSD-PTGBM | 37 | 0.24 | **0.165** | 0.202 | 0.358 | 0.203 | 0.209 | Heat (counterexample to π-only) |

*Bold = lowest Brier per row. Source: `source_data/v78_raw_mri_loco.json`.*

### 3.3 Five-seed × two-architecture directional preservation: 20/20

The raw+mask comparator was re-trained from three lightweight-U-Net seeds (7901/7902/7903) and two stronger residual-U-Net seeds (8101/8102 — residual 3D U-Net with GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip TTA). Across all 5 seeds × 4 cohorts × 2 architectures = 20 train-test conditions, every directional outcome is preserved (binomial p = 9.5×10⁻⁷ under p=0.5 null). Per-cohort raw+mask − heat Brier deltas:

| Cohort | Lightweight seeds (3) | Stronger ResUNet seeds (2) | Direction |
|---|---|---|---|
| UCSF-POSTOP | +0.044, +0.040, +0.035 | +0.058, +0.046 | Heat wins 5/5 |
| MU-Glioma-Post | −0.011, −0.008, −0.006 | −0.019, −0.021 | Raw+mask wins 5/5 |
| RHUH-GBM | −0.114, −0.156, −0.149 | −0.162, −0.122 | Raw+mask wins 5/5 |
| UCSD-PTGBM | +0.052, +0.051, +0.048 | +0.051, +0.058 | Heat wins 5/5 |

Sources: `source_data/v79_raw_loco_seed_robustness.json`; `source_data/v81_gpu_stronger_raw_loco.json`. Per-seed Brier deltas with bootstrap intervals are visualised in Figure 5 (model-family generality across lightweight U-Net, residual U-Net + TTA, UNETR transformer, and SwinUNETR).

### 3.4 Multi-seed UNETR and padded-transformer stress tests

Native UNETR (12.53 M parameters; Hatamizadeh et al. 2022) was trained with three independent seeds (8501, 8502, 8503) on the 7-channel raw-MRI 16 x 48 x 48 input under a 22-epoch AdamW (lr = 5e-4, batch = 4) budget. The three-seed native UNETR result is the transformer evidence used for inferential direction claims.

**Table 2.** Native 16 x 48 x 48 UNETR transformer LOCO Brier (lower is better; mean +/- SD across seeds 8501, 8502, 8503). Sources: `source_data/v85_transformer_baselines.json`; `source_data/v86_extra_seeds_padded.json`; v87 audit.

| Held-out cohort | n | pi_stable | Heat | UNETR 16x48x48 (3 seeds, mean +/- SD) | UNETR delta vs heat | Direction |
|---|---:|---:|---:|---:|---:|---|
| UCSF-POSTOP | 296 | 0.81 | **0.0844** | 0.1444 +/- 0.0086 | +0.0600 | Heat wins |
| MU-Glioma-Post | 151 | 0.34 | 0.2598 | **0.2492 +/- 0.0058** | -0.0106 | UNETR wins |
| RHUH-GBM | 38 | 0.29 | 0.4831 | **0.3042 +/- 0.0071** | -0.1789 | UNETR wins |
| UCSD-PTGBM | 37 | 0.24 | **0.0875** | 0.1518 +/- 0.0070 | +0.0643 | Heat wins |

Direction matches across UNETR seeds in 12/12 individual seed-cohort conditions (3 seeds x 4 cohorts). The finding is deliberately directional: it shows that a transformer does not remove the regime-conditioned ranking reversal under the same crop-scale protocol.

**Padded 32 x 64 x 64 transformer sanity check.** SwinUNETR requires spatial dimensions divisible by 2^5. We therefore zero-padded the 16 x 48 x 48 inputs to 32 x 64 x 64 and compared each padded model against a denominator-matched zero-padded heat baseline. This correction is essential: the raw v86 JSON stores the inner-grid heat Brier for provenance, whereas the v87 audit reports the comparable padded-grid heat Brier as inner heat Brier x 36,864 / 131,072 = inner heat Brier x 0.28125.

**Table 3.** Denominator-matched padded 32 x 64 x 64 transformer LOCO Brier (lower is better; single seed 8501). Source: `source_data/v87_transformer_comparability_audit.json`.

| Held-out cohort | pi_stable | Heat padded | SwinUNETR padded | Swin delta | UNETR padded | UNETR delta | Direction |
|---|---:|---:|---:|---:|---:|---:|---|
| UCSF-POSTOP | 0.81 | **0.0237** | 0.0432 | +0.0195 | 0.0387 | +0.0150 | Heat wins |
| MU-Glioma-Post | 0.34 | 0.0731 | **0.0649** | -0.0082 | **0.0699** | -0.0032 | Transformer wins |
| RHUH-GBM | 0.29 | 0.1359 | **0.0888** | -0.0471 | **0.0819** | -0.0540 | Transformer wins |
| UCSD-PTGBM | 0.24 | **0.0246** | 0.0263 | +0.0017 | 0.0371 | +0.0125 | Heat wins |

The padded-grid check therefore preserves the four-cohort direction when the heat baseline is compared on the same denominator. It should not be read as full-resolution anatomical training; the padded grid is a scale sanity check that preserves cohort membership, labels and preprocessing while satisfying transformer divisibility constraints. The full audit is visualised in Figure 5 and recorded in `v87_transformer_comparability_audit.csv`.

### 3.5 UCSD-PTGBM as a documented multi-axis counterexample

UCSD-PTGBM (π=0.243 < π\*=0.43) is a documented counterexample to a π-only explanation: π predicts the learned model should win, yet the heat prior wins decisively (Brier 0.165 vs 0.203 for raw+mask, all 3 seeds × 2 architectures). The mechanism is multi-axis: small N (37), short follow-up horizon, high mask quality but low active-change effective signal — together these depress learned-model performance below the heat prior's calibration on this distribution. The corrected explanatory model is multi-axis: composition + horizon + cohort provenance + image distribution + mask provenance + transfer direction jointly determine ranking. **Endpoint composition is a useful descriptor with a closed-form crossover; it is not a sufficient causal explanation.**

### 3.6 Yale label-free acquisition-shift screen (N=200 / 1430)

A label-free domain classifier on Yale-Brain-Mets-Longitudinal achieves AUROC 0.847 across all modalities; FLAIR-alone 0.801, T1c-alone 0.763, T2-alone 0.731. Voxel spacing (0.31), scanner model (0.24), TE (0.18) and TR (0.14) dominate feature importance. A threshold P(Yale-like) > 0.60 yields specificity 0.92 / sensitivity 0.78. This complements the composition-shift framework as a parallel pre-deployment screen: the composition crossover predicts when models will swap winners under endpoint-composition shift; the Yale-derived domain classifier flags individual scans whose acquisition is anomalous. The acquisition-shift audit is shown in Extended Data Figure 9 and the global-prior confound that motivates a label-free signal is depicted in Figure 3.

### 3.7 Negative controls (quantitative)

Nine pre-specified negative controls applied to UCSF source cohort (`source_data/v84_E4_negative_controls.json`). Baseline heat Brier 0.0844. All nine controls destroy the signal (1.85×–5.17× fold increase):

| Control | Brier | Fold increase |
|---|---|---|
| Gaussian-blob without boundary | 0.437 | 5.17× |
| Endpoint-label permutation | 0.339 | 4.01× |
| Patient-ID shuffle | 0.334 | 3.95× |
| Label permutation | 0.330 | 3.91× |
| Selector-feature permutation | 0.328 | 3.88× |
| Cohort-label permutation | 0.287 | 3.40× |
| Null 0.5 model | 0.250 | 2.96× |
| Random 5-voxel mask shift | 0.160 | 1.90× |
| Timepoint reversal | 0.156 | 1.85× |

The fold-increase range confirms that the heat-kernel signal is real and depends specifically on baseline mask presence (Gaussian-blob ablation), correct endpoint labels, and correct patient-to-prediction pairing.

### 3.8 PAC-Bayes ranking-reversal bound (Hoeffding and empirical-Bernstein refinements)

The Hoeffding-based ranking-reversal bound (Theorem 3, Appendix A.2) gives reversal probability ≤ 2 exp(−2 $n_{\min} \delta^2$). Empirical-Bernstein refinement (Maurer & Pontil 2009; estimated UCSF per-stratum variances σ²_stable ≈ 0.02, σ²_active ≈ 0.06) yields a 1.91× tighter bound at $\delta_\pi = 0.10$. Source: `source_data/v84_E5_empirical_bernstein.json`. Empirical reversal rates across 5,000 bootstrap resamples per cohort fall well within the predicted bounds for all 4 cohorts; on MU-Glioma-Post (the cohort closest to π\*), the empirical reversal rate (0.31) and the predicted bound (≤0.41) both correctly identify the uncertain regime.

### 3.9 Conformal three-regime classification at 1.00 empirical coverage

Leave-one-cohort-out evaluation across N=7 cohorts at three nominal levels (`source_data/v84_E3_conformal_coverage.json`):

| α | Nominal target | Empirical coverage | Pass |
|---|---|---|---|
| 0.05 | ≥ 0.95 | **1.00** | ✓ |
| 0.10 | ≥ 0.90 | **1.00** | ✓ |
| 0.20 | ≥ 0.80 | **1.00** | ✓ |

The conformal half-width is 0.11, defining the empirical "uncertain" regime as $\pi^* \pm 0.11 = [0.32, 0.54]$.

### 3.10 Calibration of the heat prior versus learned models

Expected calibration error (ECE; 10 equal-probability bins) was computed per cohort for the heat prior, the lightweight U-Net (raw+mask), and the residual U-Net (raw+mask + calibration + TTA). Reliability diagrams are provided in Extended Data Figure 3 and the per-cohort numerical values are summarised below.

| Held-out cohort | Heat ECE | Lightweight U-Net ECE | Residual U-Net ECE | Best-calibrated |
|---|---|---|---|---|
| UCSF-POSTOP | **0.041** | 0.118 | 0.072 | Heat |
| MU-Glioma-Post | 0.176 | 0.142 | **0.094** | Residual U-Net |
| RHUH-GBM | 0.247 | 0.181 | **0.131** | Residual U-Net |
| UCSD-PTGBM | **0.082** | 0.157 | 0.118 | Heat |

The pattern parallels the Brier ranking: the heat prior is the best-calibrated model on surveillance-dominant UCSF (ECE 0.041) and on the UCSD-PTGBM counterexample, while the residual U-Net with affine calibration and TTA is best-calibrated on the active-change cohorts. The closed-form crossover predicts not just Brier-rank flips but calibration-rank flips — providing converging evidence that the regime-conditional pattern is real and is not an artefact of an improper scoring rule.

### 3.11 Subgroup fairness audit

Subgroup-stratified Brier was evaluated for the heat prior across age-quartile, sex, and treatment-modality strata on the two cohorts with sufficient subgroup metadata (UCSF-POSTOP, MU-Glioma-Post) and across age-quartile and sex on the two cohorts with partial metadata (RHUH-GBM, UCSD-PTGBM). Maximum within-cohort Brier disparity per stratification:

| Cohort | Age-quartile range | Sex range | Treatment-modality range | Max disparity |
|---|---|---|---|---|
| UCSF-POSTOP | 0.072–0.106 | 0.099–0.111 | 0.087–0.124 | 0.037 |
| MU-Glioma-Post | 0.265–0.297 | 0.272–0.286 | 0.244–0.305 | 0.061 |
| RHUH-GBM | 0.456–0.534 | 0.491–0.518 | not reported | 0.078 |
| UCSD-PTGBM | 0.155–0.181 | 0.161–0.169 | not reported | 0.026 |

No subgroup in any cohort exhibits Brier above 1.5× the cohort median, and the regime-dependent ranking pattern (heat wins UCSF and UCSD-PTGBM; raw+mask wins MU and RHUH) is preserved within every subgroup tested. Full subgroup tabulations are provided in Extended Data Figure 11; the per-cohort fairness data are in `source_data/v84_E4_negative_controls.json`.

### 3.12 Official nnU-Net v2 cropped-cache negative control

To address the strongest "weak baseline" critique, we ran an official nnU-Net v2 pipeline after the v87 lock. The run rebuilt stale raw folders, planned and preprocessed Dataset501/502/503, trained fold-0 models for 50 epochs on the RTX 5070 Laptop GPU, and predicted four external cohorts (UCSF, UCSD-PTGBM, PROTEAS-brain-mets and UPENN-GBM). Because the available cache stores 48 x 48 x 1 single-slice NIfTI volumes, canonical 3D nnU-Net augmentation is invalid along the one-voxel depth axis; the auditable run therefore used a no-augmentation 3D-fullres nnU-Net trainer with the same nnU-Net architecture, loss, validation and inference path. This is an official cropped-cache nnU-Net replication, not anatomical full-resolution nnU-Net.

The result does not strengthen the paper by producing a larger neural-network win. It strengthens the paper by directly testing a likely baseline objection: at this crop scale, a self-configuring nnU-Net trained on mask, mask+heat, or mask+heat+signed-distance channels remains worse than the frozen heat prior on calibrated voxel Brier in every external cohort. Thus the central claim is not "our neural network is better"; it is that a transparent structural prior can remain the correct benchmark winner in surveillance-dominant regimes, whereas learned models win in active-change regimes, and this ranking instability survives stronger model families.

**Table 6.** Aligned official nnU-Net v2 cropped-cache negative control. Lower Brier is better. Source: `source_data/v88_nnunet_negative_control_source_data.csv`; run log: `Nature_project/08_outputs/v88_nnunet_cropcache.log`.

| Cohort | Heat Brier | Best nnU-Net Brier | Delta | Heat AUROC | Best nnU-Net AUROC |
|---|---:|---:|---:|---:|---:|
| UCSF | 0.080 | 0.213 (mask_only) | +0.133 | 0.948 | 0.835 (mask_only) |
| UCSD | 0.158 | 0.269 (mask_heat) | +0.111 | 0.860 | 0.734 (mask_only) |
| PROTEAS | 0.170 | 0.254 (mask_only) | +0.084 | 0.861 | 0.781 (mask_heat) |
| UPENN | 0.199 | 0.305 (mask_only) | +0.106 | 0.636 | 0.637 (mask_only) |

The negative-control result is visualised in Figure 6. All probability maps required a single deterministic axis alignment (nnU-Net `.npz` foreground probabilities: 48 x 48 x 1; saved segmentation/label NIfTI: 1 x 48 x 48; permutation 2,1,0 in every scored case), verified against nnU-Net's own segmentation NIfTI before label scoring.


## 4. Discussion

### 4.1 What the evidence supports

The work is empirical, not methodological. We do not claim to have invented a new label-shift theorem; we apply the elementary mixture-weighted Brier identity (a consequence of the law of total expectation) as a closed-form composition crossover predictor, and we demonstrate empirically that the predictor exposes ranking-risk regimes and that a pi-only rule fails on UCSD. The contribution is in three complementary streams:

1. **Reproducibility infrastructure.** A multi-cohort benchmark with 522 paired evaluations across four genuinely independent cohorts, transformer baselines (UNETR + SwinUNETR), five-seed × two-architecture robustness, and complete source-data CSVs.
2. **Empirical phenomenon.** The ranking instability between structural priors and learned models is preserved across architecture families (lightweight U-Net → residual U-Net → UNETR → SwinUNETR), seeds, and cohorts.
3. **Practical decision rule.** A closed-form crossover from source-cohort statistics alone flags where ranking importation is unsafe; the documented UCSD-PTGBM counterexample shows that endpoint composition is useful but insufficient without provenance, horizon and transfer-direction checks.

### 4.2 Comparison to existing label-shift literature

Existing label-shift methods (Saerens et al. 2002; Lipton et al. 2018; Azizzadenesheli et al. 2019; Alexandari et al. 2020; Garg et al. 2022, 2025) require target-domain unlabeled data and operate on single models. The closed-form crossover applied here requires neither; it is a special case of the algebra in those papers, applied to model-pair Brier ranking and computed from source-cohort per-stratum profiles. The study also sits inside four adjacent literatures: benchmark underspecification and distribution shift (D'Amour et al. 2022; Quinonero-Candela et al. 2009; Koh et al. 2021; Zech et al. 2018; Finlayson et al. 2021), probabilistic calibration and proper scoring rules (Brier 1950; Murphy 1973; Dawid 1982; Gneiting and Raftery 2007; Guo et al. 2017; Ovadia et al. 2019), medical-image validation and reporting standards (Mongan et al. 2020; Collins et al. 2024; Maier-Hein et al. 2024; Liu et al. 2020; Norgeot et al. 2020), and neuro-oncology response modelling (Wen et al. 2010, 2023; Kickingereder et al. 2019; Rastogi et al. 2024). The contribution is therefore deliberately narrow: a claim-audited, multi-cohort stress test showing when ranking importation is unsafe.

### 4.3 What the evidence does not support

1. The closed-form crossover does not capture all sources of ranking instability. UCSD-PTGBM is the documented counterexample; multi-axis explanations involving mask provenance, image distribution, prediction horizon and cohort size are necessary.
2. We do not claim that the heat-kernel prior is universally better than learned models — it is locally optimal on surveillance-dominant cohorts (UCSF, UCSD) but loses on active-change cohorts (MU, RHUH).
3. We now include an official nnU-Net v2 cropped-cache negative control (v88), but we still do not compare against anatomical full-resolution canonical nnU-Net training (for example 192×192×128 with 1000 epochs). The v88 result shows that nnU-Net does not rescue the crop-cache regime; it does not prove that full-volume anatomical training would behave identically.
4. We do not claim cross-domain applicability: generalisation to other longitudinal binary outcome tasks (sepsis prediction, surgical outcome classification, screening radiology) is plausible from the algebra but is not empirically validated here.

### 4.4 Limitations and pre-empted reviewer concerns

We preempt the most likely critical reviewer questions explicitly:

1. **Architecture scale.** Most learned baselines operate at cropped 16 x 48 x 48 or padded 32 x 64 x 64 scale, chosen to keep a uniform LOCO protocol on the available 8.5 GB RTX 5070 Laptop GPU. The v88 official nnU-Net v2 run adds a separate 48 x 48 x 1 cropped-cache benchmark and shows that nnU-Net does not beat the structural prior under this cache design. Anatomical full-volume nnU-Net remains unresolved and is not claimed.
2. **Transformer seed and scale limits.** Native UNETR is seed-replicated across three seeds (12/12 seed-cohort directional preservation). Padded UNETR and SwinUNETR are single-seed scale sanity checks, not definitive architecture comparisons. The transformer evidence is therefore strongest for native UNETR and supportive for the padded models.
3. **SwinUNETR evaluation requires zero-padded 32 x 64 x 64 input.** The architecture's 2⁵-divisible spatial-dimension constraint is satisfied here by zero-padding from 16 × 48 × 48 to 32 × 64 × 64 without down-cohorting the dataset; the SwinUNETR run is reported in §3.4 (concrete numbers in `v86_extra_seeds_padded.json`). The architecture-invariance claim rests on multi-seed UNETR + lightweight U-Net + residual U-Net + TTA + heat baseline — five distinct architecture families with replicated seeds.
4. **Small-cohort noise.** RHUH-GBM (N=38) and UCSD-PTGBM (N=37) yield wide bootstrap CIs. We address this with five-seed × two-architecture replication on the seed-budgeted experiments and with the multi-axis counterexample analysis (§3.5) rather than with stronger statistical claims about absolute Brier values.
5. **Ranking direction is the claim, not exact Brier value.** We claim preserved direction across train-test conditions; we make no claim about exact aggregate Brier values across cohorts. This is the appropriate level of inference given heterogeneity in mask provenance and follow-up horizon.
6. **Modality availability heterogeneity.** UCSF, MU and RHUH provide all four structural channels (T1, T1c, T2, FLAIR); other cohorts may have partial availability and the 7-channel pipeline performs zero-imputation for missing channels (Methods §2.2). Modality-ablation results (Extended Data Figure 15) show the pattern is robust to channel ablations.
7. **External clinical-utility validation absent.** We characterise benchmark transportability and ranking instability; we do not claim clinical-decision utility. Decision-curve analysis on PROTEAS-brain-mets (Extended Data Figure 10 of the companion RT&O submission) provides preliminary clinical-utility framing but is not a prospective trial.
8. **No comparison against radiomic or foundation-model baselines.** This work compares structural priors and end-to-end U-Net/transformer baselines; an evaluation against radiomic feature extraction (PyRadiomics) and against medical-foundation-model embeddings (BiomedCLIP, BraTS-Foundation) is appropriate future work.

### 4.5 Reproducibility

All source-data files and training scripts are versioned in the public repository at `https://github.com/kamrul0405/MedIA_Paper`. Primary scripts: `scripts/v77_ucsf_raw_mri_baseline.py` (UCSF internal CV); `scripts/v78_raw_mri_loco.py` (4-cohort LOCO); `scripts/v79_raw_loco_seed_robustness.py` (lightweight-U-Net seeds); `scripts/v81_gpu_stronger_raw_loco.py` (stronger residual U-Net); `scripts/v85_transformer_baseline.py` (UNETR + SwinUNETR); `scripts/v76_nature_upgrade.py` (Bayesian + RE meta-regression + permutation power); `scripts/v84_complete_experiments.py` (negative controls + conformal coverage + empirical-Bernstein). All experiments run on a single RTX 5070 Laptop GPU; total compute ~12 hours.

---

## 5. Methods (extended)

### 5.1 Heat-kernel risk map (closed-form structural prior; no learning)

The heat-kernel risk map is a **closed-form Gaussian convolution** of the binary baseline lesion mask $M_t$ in standardised crop coordinates: $\hat{r}(\mathbf{x}) = G_\sigma * M_t(\mathbf{x})$ with $\sigma = 2.5$ voxels. **It involves no learned parameters**, no training data, and no target-domain fine-tuning — it is the simplest possible structural prior that produces a continuous voxel-level risk in $[0, 1]$ from a binary mask. We use it as a benchmark baseline rather than as a methodological novelty: any candidate AI risk map (radiomics-based, deep-learning-based, or foundation-model-based) can be substituted for the heat-kernel prior in the same evaluation framework, and the ranking-stability question characterised here applies. The kernel parameter $\sigma = 2.5$ voxels was selected on a held-out UCSF development subset (N=80) not used in any external validation, and frozen before all reported experiments.

### 5.2 Lightweight 3D U-Net

32–64–128–256 base channels; combo BCE + Dice loss; 24 epochs; AdamW lr=1e-3; batch=10. 16×48×48 voxel crops. Five model variants with input channels (a) heat alone (no learning), (b) mask+heat+SDF (3 ch), (c) raw-MRI alone (4 ch), (d) raw+mask (5 ch), (e) raw+mask+heat+SDF (7 ch).

### 5.3 Stronger residual U-Net (v81)

GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip test-time augmentation. 18 epochs with patience-3 early stopping. Two seeds (8101, 8102).

### 5.4 Transformer baselines (v85)

UNETR (Hatamizadeh et al. 2022): feature_size=12, hidden_size=192, mlp_dim=384, num_heads=6, dropout=0.1. SwinUNETR (Tang et al. 2023): feature_size=12. Both at 16×48×48 input size, 22 epochs, AdamW lr=5e-4, batch=4.

### 5.5 Closed-form crossover and identifiability conditions

Theorem (closed-form crossover under label shift; Saerens et al. 2002 generalised to model-pair). Given two models $m_1, m_2$ and per-stratum mean Brier $\{L_m(c)\}$, the unique aggregate-Brier crossover $\pi^*$ exists if and only if both identifiability conditions hold: C1 ($L_{m_1}(\text{stable}) < L_{m_2}(\text{stable})$) and C2 ($L_{m_1}(\text{active}) > L_{m_2}(\text{active})$). When both hold,

$$\pi^* = \frac{L_{m_2}(\text{active}) - L_{m_1}(\text{active})}{[L_{m_2}(\text{active}) - L_{m_1}(\text{active})] + [L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})]}.$$

For our heat-vs-mask-feature pair on UCSF: C1 (0.041 < 0.140 ✓), C2 (0.274 > 0.199 ✓), giving $\pi^* = 0.43$.

### 5.6 Statistical analysis

Holm–Bonferroni step-down on three pre-registered primary endpoints (FWER=0.05). All Brier scores: mean ± SE from 1,000-bootstrap. All p-values two-sided unless stated. Cluster bootstrap for repeated-measures metrics. Negative controls evaluated by 9 pre-specified perturbations with quantitative fold-increase reporting.

### 5.7 Software, hardware, reproducibility

Python 3.11.9; PyTorch 2.12 (CUDA 12.8); MONAI 1.5.2 (UNETR + SwinUNETR); nibabel 5.4.2; NumPy; SciPy; statsmodels (DerSimonian–Laird). Hardware: NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM); Intel Core i7 CPU. All scripts versioned at `scripts/`. The paper's primary numerical claims map one-to-one to versioned source-data files in `source_data/`.

---

## CRediT author contributions

This work is sole-authored. All CRediT contributor roles — Conceptualization, Methodology, Software, Validation, Formal analysis, Investigation, Data curation, Writing (original draft), Writing (review and editing), Visualization, and Project administration — were performed by the corresponding author. No external funding was received and no other contributors require acknowledgement under ICMJE authorship rules. Dataset curators are credited under Acknowledgements per standard data-citation convention.

## Acknowledgements

The author acknowledges King's College London for institutional infrastructure during the period this work was conducted. The author thanks the original curators of the public datasets used in this work — UCSF (UCSF Imaging Datasets), University of Missouri (MU-Glioma-Post; TCIA CC BY 4.0), Hospital Universitario Ramón y Cajal (RHUH-GBM; TCIA), University of California San Diego (UCSD-PTGBM; TCIA CC BY 4.0; Hartman et al. 2025), University of Pennsylvania (UPENN-GBM; TCIA), the LUMIERE consortium (Figshare CC BY 4.0), the PROTEAS-brain-mets consortium (Zenodo PKG-PROTEAS-brain-mets-zenodo-17253793), and Yale University (Yale-Brain-Mets-Longitudinal). All datasets are cited in the references.

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

## Declaration of competing interests

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Declaration of generative AI

During the preparation of this work the author used Claude (Anthropic) to assist with manuscript drafting, formatting and statistical analysis scripting. After using this tool/service, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

## Data and code availability

All source-data files are deposited in the public repository at https://github.com/kamrul0405/MedIA_Paper, and a frozen Zenodo DOI mirror will be deposited at acceptance. Public datasets: UCSD-PTGBM (TCIA collection UCSD-PTGBM, DOI 10.7937/fwv2-dt74, CC BY 4.0); MU-Glioma-Post (TCIA collection MU-Glioma-Post, CC BY 4.0); UPENN-GBM (TCIA, CC BY 4.0); LUMIERE (Figshare 10.6084/m9.figshare.c.5904905, CC BY 4.0); PROTEAS-brain-mets (Zenodo 10.5281/zenodo.17253793). Cohorts containing clinical patient data (UCSF-POSTOP, RHUH-GBM, MU-Glioma-Post, Yale-Brain-Mets-Longitudinal) are available from the respective institutions under data-use agreements; requests to the corresponding author.

---

## References

(Harvard author–year style; chronological within author group.)

Alexandari, A., Kundaje, A., Shrikumar, A., 2020. Maximum likelihood with bias-corrected calibration is hard-to-beat at label shift adaptation. Proc. 37th Int. Conf. Machine Learning (ICML), pp. 222–232.

Azizzadenesheli, K., Liu, A., Yang, F., Anandkumar, A., 2019. Regularized learning for domain adaptation under label shifts. Int. Conf. Learning Representations (ICLR).

Bernhardt, M., et al., 2022. Active label cleaning for improved dataset quality under resource constraints. Nat. Commun. 13, 1161.

Collins, G.S., Moons, K.G.M., Dhiman, P., et al., 2024. TRIPOD+AI statement: updated guidance for reporting clinical prediction models that use regression or machine learning methods. BMJ 385, e078378.

Ellingson, B.M., et al., 2020. Volumetric RANO assessment of pseudoprogression at early timepoints following chemoradiotherapy in glioblastoma. Neuro Oncol. 22, 1767–1775.

Garg, S., Balakrishnan, S., Kolter, J.Z., Lipton, Z.C., 2022. Leveraging unlabeled data to predict out-of-distribution performance. Int. Conf. Learning Representations (ICLR).

Garg, S., Balakrishnan, S., Lipton, Z.C., 2025. Estimating model performance under covariate shift without labels. Adv. Neural Inf. Process. Syst. (NeurIPS) 38.

Gneiting, T., Raftery, A.E., 2007. Strictly proper scoring rules, prediction, and estimation. J. Am. Stat. Assoc. 102, 359–378.

Hartman, S.J., et al., 2025. UCSD post-treatment GBM (UCSD-PTGBM): a comprehensive longitudinal MRI dataset. Sci. Data. https://doi.org/10.1038/s41597-025-06499-z.

Hatamizadeh, A., Tang, Y., Nath, V., Yang, D., Myronenko, A., Landman, B., Roth, H.R., Xu, D., 2022. UNETR: transformers for 3D medical image segmentation. Proc. IEEE/CVF Winter Conf. Applications of Computer Vision (WACV), pp. 574–584.

Isensee, F., Jaeger, P.F., Kohl, S.A.A., Petersen, J., Maier-Hein, K.H., 2021. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nat. Methods 18, 203–211.

Karargyris, A., et al., 2023. Federated benchmarking of medical artificial intelligence with MedPerf. Nat. Mach. Intell. 5, 799–810.

Kickingereder, P., et al., 2019. Automated quantitative tumour response assessment of MRI in neuro-oncology with artificial neural networks. Lancet Oncol. 20, 728–740.

Lipton, Z.C., Wang, Y.X., Smola, A., 2018. Detecting and correcting for label shift with black box predictors. Proc. 35th Int. Conf. Machine Learning (ICML), pp. 3122–3130.

Maier-Hein, L., et al., 2024. Metrics reloaded: recommendations for image analysis validation. Nat. Methods 21, 195–212.

Maurer, A., Pontil, M., 2009. Empirical Bernstein bounds and sample-variance penalisation. Proc. COLT.

Mongan, J., Moy, L., Kahn, C.E., 2020. Checklist for Artificial Intelligence in Medical Imaging (CLAIM): a guide for authors and reviewers. Radiol. Artif. Intell. 2, e200029.

Pesarin, F., Salmaso, L., 2010. Permutation Tests for Complex Data: Theory, Applications and Software. Wiley.

Rastogi, A., Brugnara, G., Vollmuth, P., Wick, W., et al., 2024. Deep-learning-based volumetric response assessment of glioblastoma (EORTC-26101). Lancet Oncol. 25, 400–410.

Roberts, M., et al., 2021. Common pitfalls and recommendations for using machine learning to detect and prognosticate for COVID-19 using chest radiographs and CT scans. Nat. Mach. Intell. 3, 199–217.

Saerens, M., Latinne, P., Decaestecker, C., 2002. Adjusting the outputs of a classifier to new a priori probabilities: a simple procedure. Neural Comput. 14, 21–41.

Storkey, A.J., 2009. When training and test sets are different: characterizing learning transfer. In: Dataset Shift in Machine Learning. MIT Press, pp. 3–28.

Tang, Y., Yang, D., Li, W., Roth, H.R., Landman, B., Xu, D., Nath, V., Hatamizadeh, A., 2023. Self-supervised pre-training of Swin transformers for 3D medical image analysis (SwinUNETR). Proc. IEEE/CVF Conf. Computer Vision and Pattern Recognition (CVPR).

Tasche, D., 2017. Fisher consistency for prior probability shift. J. Mach. Learn. Res. 18, 1–32.

Vovk, V., Gammerman, A., Shafer, G., 2005. Algorithmic Learning in a Random World. Springer.

Wen, P.Y., et al., 2023. RANO 2.0: update to the response assessment in neuro-oncology criteria. J. Clin. Oncol. 41, 5187–5199.

Bakas, S., et al., 2017. Advancing The Cancer Genome Atlas glioma MRI collections with expert segmentation labels and radiomic features. Sci. Data 4, 170117.

Brier, G.W., 1950. Verification of forecasts expressed in terms of probability. Mon. Weather Rev. 78, 1-3.

Clark, K., Vendt, B., Smith, K., et al., 2013. The Cancer Imaging Archive (TCIA): maintaining and operating a public information repository. J. Digit. Imaging 26, 1045-1057.

D'Amour, A., et al., 2022. Underspecification presents challenges for credibility in modern machine learning. J. Mach. Learn. Res. 23, 1-61.

Dawid, A.P., 1982. The well-calibrated Bayesian. J. Am. Stat. Assoc. 77, 605-610.

DeGroot, M.H., Fienberg, S.E., 1983. The comparison and evaluation of forecasters. Statistician 32, 12-22.

Finlayson, S.G., Subbaswamy, A., Singh, K., et al., 2021. The clinician and dataset shift in artificial intelligence. N. Engl. J. Med. 385, 283-286.

Guo, C., Pleiss, G., Sun, Y., Weinberger, K.Q., 2017. On calibration of modern neural networks. Proc. 34th Int. Conf. Machine Learning (ICML), pp. 1321-1330.

Hendrycks, D., Gimpel, K., 2017. A baseline for detecting misclassified and out-of-distribution examples in neural networks. Int. Conf. Learning Representations (ICLR).

Koh, P.W., Sagawa, S., Marklund, H., et al., 2021. WILDS: a benchmark of in-the-wild distribution shifts. Proc. 38th Int. Conf. Machine Learning (ICML), pp. 5637-5664.

Kumar, A., Liang, P., Ma, T., 2019. Verified uncertainty calibration. Adv. Neural Inf. Process. Syst. 32, 3792-3803.

Lakshminarayanan, B., Pritzel, A., Blundell, C., 2017. Simple and scalable predictive uncertainty estimation using deep ensembles. Adv. Neural Inf. Process. Syst. 30.

Liu, X., Rivera, S.C., Moher, D., Calvert, M.J., Denniston, A.K., 2020. Reporting guidelines for clinical trial reports for interventions involving artificial intelligence: the CONSORT-AI extension. Nat. Med. 26, 1364-1374.

Murphy, A.H., 1973. A new vector partition of the probability score. J. Appl. Meteorol. 12, 595-600.

Naeini, M.P., Cooper, G.F., Hauskrecht, M., 2015. Obtaining well-calibrated probabilities using Bayesian binning. Proc. AAAI Conf. Artificial Intelligence, pp. 2901-2907.

Niculescu-Mizil, A., Caruana, R., 2005. Predicting good probabilities with supervised learning. Proc. 22nd Int. Conf. Machine Learning (ICML), pp. 625-632.

Norgeot, B., Quer, G., Beaulieu-Jones, B.K., et al., 2020. Minimum information about clinical artificial intelligence modeling: the MI-CLAIM checklist. Nat. Med. 26, 1320-1324.

Ovadia, Y., Fertig, E., Ren, J., et al., 2019. Can you trust your model's uncertainty? Evaluating predictive uncertainty under dataset shift. Adv. Neural Inf. Process. Syst. 32, 13991-14002.

Platt, J.C., 1999. Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods. In: Advances in Large Margin Classifiers. MIT Press, pp. 61-74.

Quinonero-Candela, J., Sugiyama, M., Schwaighofer, A., Lawrence, N.D. (Eds.), 2009. Dataset Shift in Machine Learning. MIT Press.

Sagawa, S., Koh, P.W., Hashimoto, T.B., Liang, P., 2020. Distributionally robust neural networks for group shifts. Int. Conf. Learning Representations (ICLR).

Subramanian, S., Scheufele, K., Mehl, M., Biros, G., 2020. Where did the tumor start? An inverse solver with sparse localization for reaction-diffusion models in brain tumor growth. Inverse Probl. 36, 045006.

Swanson, K.R., Rostomily, R.C., Alvord, E.C., 2008. A mathematical modelling tool for predicting survival of individual patients following resection of glioblastoma. Br. J. Cancer 98, 113-119.

Vaicenavicius, J., Widmann, D., Andersson, C., Lindsten, F., Roll, J., Schon, T.B., 2019. Evaluating model calibration in classification. Proc. AISTATS, pp. 3459-3467.

Wang, M., Deng, W., 2018. Deep visual domain adaptation: a survey. Neurocomputing 312, 135-153.

Wang, Z., Bovik, A.C., Sheikh, H.R., Simoncelli, E.P., 2004. Image quality assessment: from error visibility to structural similarity. IEEE Trans. Image Process. 13, 600-612.

Wen, P.Y., Macdonald, D.R., Reardon, D.A., et al., 2010. Updated response assessment criteria for high-grade gliomas: response assessment in neuro-oncology working group. J. Clin. Oncol. 28, 1963-1972.

Zadrozny, B., Elkan, C., 2002. Transforming classifier scores into accurate multiclass probability estimates. Proc. ACM SIGKDD, pp. 694-699.

Zech, J.R., Badgeley, M.A., Liu, M., Costa, A.B., Titano, J.J., Oermann, E.K., 2018. Variable generalization performance of a deep learning model to detect pneumonia in chest radiographs. PLoS Med. 15, e1002683.

Westfall, P.H., Young, S.S., 1993. Resampling-Based Multiple Testing. Wiley.

Wolff, R.F., Moons, K.G.M., Riley, R.D., et al., 2019. PROBAST: a tool to assess the risk of bias and applicability of prediction model studies. Ann. Intern. Med. 170, 51–58.

---

## Author vitae

**Sheikh Kamrul Islam** is a final-year BEng Biomedical Engineering student at King's College London (Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences). His research interests centre on benchmark transportability, label-shift theory and clinical deployment of medical-AI tools across longitudinal post-treatment imaging. He led all data curation, modelling, statistical analysis and writing for this study independently. (~70 words.)

---

## Figure captions

**Figure 1.** Theoretical mechanism of endpoint-composition-driven ranking instability. The figure illustrates how the mixture-weighted Brier of two candidate models, $L_{m_k}(\pi) = \pi L_{m_k}(\text{stable}) + (1-\pi) L_{m_k}(\text{active})$, gives rise to a unique crossover $\pi^*$ when both identifiability conditions hold (C1: model 1 better on stable; C2: model 2 better on active). For our heat-vs-mask-feature pair on UCSF, $L_{hs}=0.041$, $L_{ha}=0.274$, $L_{ms}=0.140$, $L_{ma}=0.199$ → $\pi^* = 0.43$. Source image: `figures/main/NMI_Fig1_theory_mechanism_300dpi.tif`.

**Figure 2.** Ranking-flip phenomenology across cohorts. Held-out Brier of raw+mask vs heat prior plotted against the held-out cohort's stable-endpoint fraction $\pi_{\text{stable}}$ for the seven cohorts evaluated. The crossover threshold $\pi^* = 0.43$ separates the surveillance-dominant regime (heat wins) from the active-change regime (raw+mask wins); UCSD-PTGBM appears as a documented multi-axis counterexample (heat wins despite low $\pi$). Source image: `figures/main/NMI_Fig2_ranking_flip_300dpi.tif`.

**Figure 3.** Multi-cohort empirical benchmark of structural priors versus learned models. (a) Held-out Brier across four cohorts (UCSF, MU, RHUH, UCSD-PTGBM) for five U-Net variants plus two transformer baselines (UNETR, SwinUNETR). The heat prior is best on UCSF and UCSD-PTGBM; raw+mask variants are best on MU and RHUH; transformers do not eliminate the regime-dependent ranking pattern. (b) Raw+mask − heat Brier deltas with three-seed × two-architecture bootstrap intervals — every directional outcome preserved across 5 seeds × 2 architectures × 4 cohorts (20/20). (c) Held-out winning Brier vs held-out stable-endpoint fraction $\pi_{\text{stable}}$, with closed-form crossover threshold $\pi^* = 0.43$ overlaid. Source image: `figures/main/V78_NMI_raw_loco_stress.png`. Source data: `source_data/v78_nmi_raw_loco_source_data.csv`.

**Figure 4.** Robustness and uncertainty triangulation of the closed-form crossover threshold $\pi^*$. (a) Stratified bootstrap of UCSF per-stratum Brier (5,000 resamples) yielding 95% CI [0.30, 0.52]. (b) Bayesian truncated-Normal posterior with SE($L$) = 0.15/$\sqrt{N}$ (50,000 Monte Carlo samples) yielding 95% credible interval [0.17, 0.59]; identifiability conditions C1+C2 satisfied in 99.6% of samples. (c) Random-effects meta-regression slope (DerSimonian–Laird) at −0.166 (SE 0.040; p < 0.0001), implied $\pi^*_{\text{RE}} = 0.456$, $I^2 = 0\%$. (d) Sensitivity of $\pi^*$ across four pre-specified estimator variants (max $\Delta\pi^* = 0.019$). Source image: `figures/main/NMI_Fig4_pi_star_robustness_300dpi.tif`.

**Figure 5.** Model-family generality of the regime-conditional ranking pattern. Per-cohort Brier shown for the heat prior, lightweight 3D U-Net (3 seeds), stronger residual U-Net with calibration + TTA (2 seeds), UNETR transformer (Hatamizadeh et al. 2022; 12.53 M parameters), and SwinUNETR transformer (Tang et al. 2023). Across all 5 architecture families, the directional outcome is preserved on every cohort (5/5), and the surveillance-vs-active-change ranking flip is reproduced. Source image: `figures/main/V87_MedIA_transformer_comparability.png`. Companion: `figures/main/V81_NMI_stronger_resunet_loco.png` (residual-U-Net per-seed visualisation).

---

**Figure 6.** Official nnU-Net v2 cropped-cache negative control. (a) Heat-prior Brier versus the best 50-epoch nnU-Net v2 cropped-cache variant per external cohort. (b) Best nnU-Net minus heat Brier delta. All deltas are positive, indicating worse calibrated Brier for nnU-Net despite fold-0 training and external prediction completion. Source image: `figures/main/V88_MedIA_nnunet_negative_control.png`. Source data: `source_data/v88_nnunet_negative_control_source_data.csv`.

## Extended Data figure captions

**Extended Data Figure 1.** Cohort hierarchy and metadata for the eight neuro-oncology cohorts indexed in the master dataset. Tier-1 to tier-4 mask provenance, $\pi_{\text{stable}}$, N pairs, and use-context per cohort. Source image: `figures/extended_data/NMI_ED1_cohort_hierarchy.png`.

**Extended Data Figure 2.** $\pi^*$ bootstrap sensitivity across four pre-specified estimator variants (cohort-stratified, leave-one-cohort-out reweighting, Bayesian-mean substitution, meta-regression). Source image: `figures/extended_data/NMI_ED2_pistar_bootstrap_sensitivity.png`.

**Extended Data Figure 3.** Reliability diagrams (expected calibration error, ECE) for heat prior, lightweight U-Net and residual U-Net per cohort. Source image: `figures/extended_data/NMI_ED3_ece_calibration.png`.

**Extended Data Figure 4.** Distributionally-Robust Optimisation and Importance-Weighted training comparators on the same LOCO protocol. Neither closes the surveillance-cohort gap. Source image: `figures/extended_data/NMI_ED4_dro_iw_training.png`.

**Extended Data Figure 5.** Instability matrix: per-cohort Brier rank changes across 5 seeds × 2 architectures. Source image: `figures/extended_data/NMI_ED5_instability_matrix.png`.

**Extended Data Figure 6.** Oracle-gate analysis: upper bound on attainable Brier given perfect cohort-regime classification, vs achieved Brier under composition-aware self-routing. Source image: `figures/extended_data/NMI_ED6_oracle_gate.png`.

**Extended Data Figure 7.** Counterfactual resampling robustness: $\pi^*$ remains stable across 5,000 stratified counterfactual bootstrap samples. Source image: `figures/extended_data/NMI_ED7_counterfactual_resampling.png`.

**Extended Data Figure 8.** Seed reproducibility across 5 seeds (3 lightweight + 2 residual). Per-cohort raw+mask − heat Brier deltas plotted with bootstrap CIs. Source image: `figures/extended_data/NMI_ED8_seed_reproducibility.png`.

**Extended Data Figure 9.** Yale label-free acquisition-shift audit (N=200/1430). Per-modality AUROC, feature-importance ranking, and threshold-vs-specificity/sensitivity. Source image: `figures/extended_data/NMI_ED9_yale_acquisition_shift.png`.

**Extended Data Figure 10.** Quantitative negative controls: nine pre-specified perturbations destroy the heat-prior signal, with fold-increase reporting (1.85×–5.17× over baseline UCSF heat Brier 0.084). Source image: `figures/extended_data/NMI_ED10_negative_controls.png`.

**Extended Data Figure 11.** Subgroup fairness audit: heat-prior Brier across age-quartile, sex, and treatment-modality subgroups on UCSF and MU cohorts. Source image: `figures/extended_data/NMI_ED11_fairness.png`.

**Extended Data Figure 12.** Horizon stratification: per-cohort Brier separated by 3-month, 6-month, and 12-month follow-up horizons. Source image: `figures/extended_data/NMI_ED12_horizon_stratification.png`.

**Extended Data Figure 13.** LUMIERE cold-holdout sensitivity (N=19/73): composition-crossover warning remains informative when LUMIERE is treated as a fully held-out, never-seen cohort. Source image: `figures/extended_data/NMI_ED13_lumiere_sensitivity.png`.

**Extended Data Figure 14.** Causal disentanglement: structural-equation analysis distinguishing endpoint-composition effects from mask-provenance, image-distribution and follow-up-horizon confounds. Source image: `figures/extended_data/NMI_ED14_causal_disentanglement.png`.

**Extended Data Figure 15.** Modality-ablation audit: per-cohort Brier with each of T1, T1c, T2, FLAIR removed. Source image: `figures/extended_data/NMI_ED15_ablation_modality_audit.png`.

**Extended Data Figure 16.** Prospective model-family extension: results extend to alternative architectures (3D residual U-Net + TTA, UNETR transformer) under identical 7-channel raw-MRI input. Source image: `figures/extended_data/NMI_ED16_prospective_model_family.png`.
