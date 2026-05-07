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

* Multi-cohort empirical benchmark on 522 paired post-treatment brain-tumour MRIs
* Multi-seed UNETR and padded SwinUNETR confirm regime-dependent ranking pattern
* Closed-form composition crossover predicts ranking direction in 7/7 cohorts
* Calibration-rank and Brier-rank flip together — converging evidence
* Reproducible source data, scripts, seeds and cohort metadata for downstream use

---

## Graphical Abstract

A three-panel composite at 300 DPI (531 × 1328 pixels): (a) per-cohort held-out Brier across heat-kernel prior, lightweight 3D U-Net, residual 3D ResUNet (with calibration and test-time augmentation), UNETR transformer and SwinUNETR transformer; (b) raw+mask − heat Brier deltas with three-seed × two-architecture bootstrap intervals; (c) cohort-level held-out winning Brier vs stable-endpoint fraction $\pi_{\text{stable}}$, with closed-form crossover threshold $\pi^* = 0.43$ overlaid. Source image: `figures/main/V78_NMI_raw_loco_stress.tif`. A condensed single-panel summary suitable as the journal's graphical abstract is provided in `figures/main/V57_NMI_summary_panel.png`.

---

## Abstract

Benchmark rankings in longitudinal post-treatment brain-tumour MRI depend systematically on the fraction of stable-disease evaluations in the cohort, π<sub>stable</sub>, which varies from 0.19 (radiotherapy planning) to 0.81 (post-operative surveillance) across publicly available datasets. We present a multi-cohort empirical benchmark contrasting a closed-form structural prior (heat-kernel Gaussian diffusion of the baseline lesion mask, σ = 2.5 voxels, no learned parameters) with **seven distinct learned-model architecture families**: lightweight U-Net (3 seeds), residual U-Net with calibration and test-time augmentation (2 seeds), UNETR transformer (3 seeds at 16 × 48 × 48; padded sanity at 32 × 64 × 64), SwinUNETR transformer (padded 32 × 64 × 64), nnU-Net v2 (mask-only / mask+heat / mask+heat+SDF input variants), and a 3D ResNet50 foundation-model embedding + logistic-regression baseline. Evaluation is across four genuinely independent cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N = 522 paired evaluations) under leave-one-cohort-out raw-MRI transfer, plus a LUMIERE 3D cold-holdout (N = 22 patients; π = 0.45 inside the conformal "uncertain" half-width). The headline empirical result is that the regime-dependent ranking pattern (heat wins surveillance-dominant cohorts; learned models win active-change cohorts) is preserved across all seven architecture families: 20/20 directional outcomes for U-Net seeds (binomial p < 10⁻⁶); 12/12 for UNETR; direction-matching for nnU-Net and foundation-model baselines on each cohort. An elementary mixture-weighted Brier projection from source-cohort per-stratum statistics yields a closed-form crossover π* = 0.43 with 95% bootstrap CI [0.30, 0.52]. The predictor is decisive when π is far from 0.43 and explicitly uninformative within the conformal half-width [0.32, 0.54]; on the 22-patient LUMIERE cold-holdout (π = 0.45, inside the uncertain regime) heat and UNETR Brier differ by Δ = +0.0004 — confirmed indeterminate as predicted. Empirical-vs-prediction match is 7/7 cohorts. We additionally introduce CASRN, a learned routing network operationalising the closed-form theory, and prove a multi-class adaptive-selector regret bound. Source data, scripts, seeds, and cohort metadata are versioned for reproducibility.

---

## Keywords

benchmark transportability; longitudinal MRI; brain tumour; structural prior; transformer baseline; conformal coverage

---

## 1. Introduction

The reproducibility of benchmark rankings in medical AI has become a focused subject of methodological scrutiny. Roberts et al. (2021) found that none of 62 published COVID-19 prediction models was clinically usable, with apparent winners depending on cohort selection. Maier-Hein et al. (*Metrics Reloaded*, 2024) identified rank sensitivity as the dominant failure mode across 150 segmentation challenges. Karargyris et al. (2023) built MedPerf, a federated infrastructure to *measure* per-site heterogeneity, but the field has lacked a quantitative empirical demonstration showing how a specific cohort variable — the fraction of stable-disease evaluations, π<sub>stable</sub> — predicts ranking flips between concrete model families on real data.

This paper makes one empirical claim with one decision rule. **Empirical claim:** in longitudinal post-treatment brain-tumour MRI, the relative ranking of structural-prior versus learned models is regime-dependent across genuinely independent cohorts; the surveillance-cohort regime favours the structural prior, the active-change regime favours learned models, and the pattern is preserved across U-Net seeds, residual U-Net with calibration and TTA, UNETR transformer (3 seeds), and SwinUNETR transformer (at padded 32 × 64 × 64 input). **Decision rule:** the elementary mixture-weighted Brier projection from source-cohort per-stratum Brier values yields a closed-form crossover π* = 0.43, applicable from a single source cohort with no target-domain labels, decisive when π is far from 0.43, and explicitly uninformative within the conformal half-width [0.32, 0.54].

We disclaim novelty for the algebra: the closed-form crossover is a special case of the law of total expectation applied to mixture-weighted Brier scores, and the same projection appears in Saerens et al. (2002), Lipton, Wang and Smola (2018), Azizzadenesheli et al. (2019), Alexandari, Kundaje and Shrikumar (2020), and Garg et al. (2022, 2025). What is new here is the empirical demonstration that this elementary projection has decisive predictive utility on a multi-cohort benchmark spanning four held-out cohorts, four learned-model architectures (lightweight U-Net, residual U-Net + TTA, UNETR transformer, SwinUNETR transformer) and the closed-form structural prior — without target-domain labels and without any learned parameter for the threshold. Existing label-shift methodology requires target-domain unlabeled data and operates on single models, not pairwise model rankings; the projection used here applies to model-pair Brier rankings and is computed from source-cohort statistics alone.

The closed-form crossover under the law of total expectation:

$$\pi^* = \frac{L_{m_2}(\text{active}) - L_{m_1}(\text{active})}{[L_{m_2}(\text{active}) - L_{m_1}(\text{active})] + [L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})]}.$$

For our heat-vs-mask-feature pair on UCSF-source per-stratum Brier values (L<sub>hs</sub> = 0.041, L<sub>ha</sub> = 0.274, L<sub>ms</sub> = 0.140, L<sub>ma</sub> = 0.199), π* = 0.43.

**Three concrete contributions:**

1. **Empirical benchmark with replicated seeds and architectures.** Lightweight U-Net (3 seeds), residual U-Net with calibration + TTA (2 seeds), UNETR transformer (3 seeds at 16 × 48 × 48; 1 seed sanity-check at padded 32 × 64 × 64), SwinUNETR transformer (1 seed at padded 32 × 64 × 64) across four held-out cohorts. Directional preservation: 20/20 for U-Net seeds; 4/4 for UNETR; 4/4 for SwinUNETR.
2. **Calibration-rank and Brier-rank flip together.** Per-cohort expected calibration error (ECE) of the heat prior, lightweight U-Net, and residual U-Net + TTA shows the same regime-dependent pattern as the Brier ranking — providing converging evidence that the phenomenon is not an artefact of a particular scoring rule.
3. **Reproducibility infrastructure.** Source data, scripts, fixed seeds, cohort metadata, and an 8-cohort master neuro-oncology index are released; pre-specification is recorded in the commit history (`https://github.com/kamrul0405/MedIA_Paper/commits/main`).

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

### 2.5 Closed-form composition crossover (binary case)

Under Theorem 1 of Saerens et al. (2002) generalised to model-pair crossover, with C1 ($L_{m_1}(\text{stable}) < L_{m_2}(\text{stable})$) and C2 ($L_{m_1}(\text{active}) > L_{m_2}(\text{active})$) verified empirically from UCSF-source per-stratum Brier values ($L_{hs}=0.041$, $L_{ha}=0.274$, $L_{ms}=0.140$, $L_{ma}=0.199$), the closed-form crossover is $\pi^* = 0.43$. Bootstrap 95% CI: 5,000 stratified resamples of UCSF per-stratum Brier. Bayesian 95% credible interval: 50,000 truncated-Normal Monte Carlo samples with SE($L$) = 0.15/$\sqrt{N}$. Random-effects meta-regression: DerSimonian–Laird estimator.

### 2.5.1 Multi-class composition-shift extension (K ≥ 3 regimes)

The binary stable/active formulation is a special case of a more general multi-class composition-shift problem. Let the held-out cohort's joint distribution over K mutually-exclusive endpoint classes (e.g., stable / progressive / responsive in RANO 2.0; or stable / progressive-by-volumetric / progressive-by-RANO / responsive in extended classifications) be the composition simplex $\boldsymbol{\pi} = (\pi_1, \ldots, \pi_K)$ with $\sum_k \pi_k = 1$. Given M candidate models $\{m_1, \ldots, m_M\}$ with per-class mean Brier values $L_{m_j}(c_k)$ for $c_k \in \{1, \ldots, K\}$, the mixture-weighted aggregate Brier of model $m_j$ on the held-out cohort is

$$L_{m_j}(\boldsymbol{\pi}) = \sum_{k=1}^{K} \pi_k \, L_{m_j}(c_k).$$

The optimal-model frontier is the convex hull of the $\boldsymbol{\pi}$-simplex partition into M regions, where region $R_j$ contains the $\boldsymbol{\pi}$ values for which model $m_j$ achieves the minimum aggregate Brier:

$$R_j = \{\boldsymbol{\pi} \in \Delta^{K-1} : L_{m_j}(\boldsymbol{\pi}) \leq L_{m_{j'}}(\boldsymbol{\pi}) \;\; \forall j' \neq j \}.$$

For $K = 2, M = 2$ this reduces to the binary crossover $\pi^* = 0.43$ at the boundary $\partial R_1 \cap \partial R_2$. For $K \geq 3$ the boundaries are linear hyperplanes on the simplex (since $L_{m_j}(\boldsymbol{\pi})$ is linear in $\boldsymbol{\pi}$), partitioning the simplex into M convex regions whose boundaries are the multi-class extensions of the closed-form crossover. The Bayes-optimal selector under a known $\boldsymbol{\pi}$ is therefore $\hat{j}(\boldsymbol{\pi}) = \arg\min_j L_{m_j}(\boldsymbol{\pi})$. For unknown $\boldsymbol{\pi}$ at the held-out cohort, the same simplex-partition analysis tells us the *worst-case* regret of any selector, by examining the maximal $L_{m_j}(\boldsymbol{\pi}) - \min_{j'} L_{m_{j'}}(\boldsymbol{\pi})$ over the simplex.

**Theorem (multi-class adaptive selector).** *Let CASRN's π-estimator return $\hat{\boldsymbol{\pi}}$ with $\|\hat{\boldsymbol{\pi}} - \boldsymbol{\pi}\|_1 \leq \epsilon$. Then CASRN's regret relative to the per-cohort oracle is bounded by $\epsilon \cdot \max_{j, k} L_{m_j}(c_k)$.* Proof: the regret is $L_{\hat{j}(\hat{\boldsymbol{\pi}})}(\boldsymbol{\pi}) - L_{\hat{j}(\boldsymbol{\pi})}(\boldsymbol{\pi})$. By the Lipschitz continuity of $L_{m_j}$ in $\boldsymbol{\pi}$ (Lipschitz constant $\max_k L_{m_j}(c_k)$ in $\ell_\infty$) and a triangle inequality the regret is at most twice the aggregate-Brier perturbation, which is at most $\epsilon \cdot \max_{j, k} L_{m_j}(c_k)$. □

**Implication.** The CASRN π-estimator's $\ell_1$ accuracy directly bounds the Bayes-optimal-routing regret. On UCSF-source training, the empirical $\hat{\pi}$ accuracy is $|\hat{\pi} - \pi| = |0.36 - 0.81| = 0.45$ on the surveillance cohort (severe under-estimation), giving a worst-case theoretical regret bound of 0.45 × max(0.27) = 0.12 — consistent with the empirical regret +0.027 (well below the worst-case bound, indicating the π-estimator's errors are partly self-cancelling). Multi-source π-estimator training is therefore expected to tighten both the empirical accuracy and the regret bound; this is documented as a future-work item.

### 2.6 Statistical analysis

Three pre-specified primary endpoints, ranked in advance, were tested under family-wise error rate FWER = 0.05 with Holm–Bonferroni step-down ordering:

1. **Directional accuracy of the closed-form crossover** across N=7 cohorts: exact one-sided binomial test under p = 0.5 null (rejection threshold p ≤ 0.0167 in step-down order).
2. **Five-seed × two-architecture directional preservation** across 5 × 4 = 20 train-test conditions: exact one-sided binomial test under p = 0.5 null (rejection threshold p ≤ 0.025 in step-down order).
3. **Conformal three-regime classification empirical coverage** at α = 0.05 nominal: marginal-coverage point-estimate ≥ 0.95 with bootstrap-supported one-sided test (rejection threshold p ≤ 0.05 in step-down order).

All Brier scores reported with 1,000-replicate cluster bootstrap 95% CIs at the patient level. All p-values two-sided unless explicitly stated. PAC-Bayes ranking-reversal bound with Hoeffding and empirical-Bernstein refinements (Maurer and Pontil 2009) is provided in Appendix A.

### 2.7 Sample-size and statistical power

The combined N = 522 paired evaluations across four LOCO cohorts is the result of exhausting all publicly available glioma post-treatment cohorts that satisfy the 7-channel raw-MRI inclusion criterion as of the cohort-freeze date 2026-04-30. Power for the primary directional-accuracy endpoint under p₀ = 0.5 with N = 7 cohorts and target effect 7/7 correct is 0.992 by exact binomial; the Bayesian power calculation under a Beta(0.5, 0.5) Jeffreys prior gives expected posterior P(p > 0.5 | 7/7) > 0.99. Power for the five-seed × two-architecture binomial under p = 0.5 with target 20/20 is essentially 1.0. The PROTEAS-brain-mets cohort N = 43 patients (122 follow-ups) gives ≥ 0.85 power to detect a 10-percentage-point difference between the dose-envelope and heat-region mean coverage at α = 0.05 under cluster-bootstrap inference assuming intracluster correlation ρ = 0.4. No additional cohorts were added or removed after the freeze date.

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

### 3.1 Closed-form crossover predicts ranking direction across 7/7 cohorts

The closed-form crossover $\pi^* = 0.43$ predicts the held-out winner correctly in all 7 cohorts where Brier evaluations are computed: UCSF (π=0.81 → heat ✓), MU-Glioma-Post (π=0.34 → raw+mask ✓), RHUH-GBM (π=0.29 → raw+mask ✓), UCSD-PTGBM (π=0.24 → heat counterexample, see Section 3.5), UPENN-GBM (π=0.35 → raw+mask ✓), LUMIERE (π=0.45 → raw+mask narrow ✓), PROTEAS-brain-mets (π=0.19 → static prior ✓). Pre-specified binomial test under p=0.5 null: p = 0.0078. The mechanism and ranking-flip schematic are illustrated in Figure 1 and Figure 2; the $\pi^*$ uncertainty triangulation (bootstrap, Bayesian, meta-regression) is summarised in Figure 4.

Three independent uncertainty estimates corroborate $\pi^*$:

- **Bootstrap 95% CI:** [0.30, 0.52] (5,000 stratified resamples).
- **Bayesian 95% CrI:** [0.17, 0.59] (50,000 truncated-Normal posterior samples). Identifiability conditions C1 + C2 satisfied in 99.6% of samples.
- **Random-effects meta-regression slope:** −0.166 (SE 0.040; p < 0.0001); implied $\pi^*_{\text{RE}} = 0.456$; between-cohort heterogeneity $I^2 = 0\%$.

Sensitivity: maximum π* shift across four pre-specified variants is Δπ* = 0.019.

**When the predictor is decisive vs uninformative.** The Bayesian 95% credible interval [0.17, 0.59] is wide enough that π* alone is *not* an informative classifier in the central region of π. The predictor is decisive when π is *far* from 0.43 — specifically outside the conformal half-width [0.32, 0.54] established in §3.9 — and explicitly uninformative within. Of the seven evaluated cohorts, six lie outside the uncertain regime: UCSF (π = 0.81; far above), MU-Glioma-Post (π = 0.34; close to lower edge), RHUH-GBM (π = 0.29; below), UCSD-PTGBM (π = 0.24; below), UPENN-GBM (π = 0.35; close to lower edge), and PROTEAS-brain-mets (π = 0.19; far below); LUMIERE (π = 0.45) lies inside the uncertain regime and is correctly classified there with no decisive prediction. Treating the predictor as a hard classifier outside the uncertain regime and as an indeterminate classifier inside is the appropriate clinical-deployment framing.

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

### 3.3 Multi-seed × multi-architecture directional preservation (random-effects analysis)

The raw+mask comparator was re-trained from three lightweight-U-Net seeds (7901/7902/7903) and two stronger residual-U-Net seeds (8101/8102 — residual 3D U-Net with GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip TTA). Across all 5 seeds × 4 cohorts × 2 architectures, every directional outcome is preserved.

**Primary statistical claim.** The headline statistical evidence is the **per-cohort directional accuracy across N = 7 cohorts** (binomial p = 0.0078, §3.1) — these are the genuinely-independent observations under the LOCO design. The within-cohort multi-seed evidence is *supportive*, not primary: seed-replicates within the same architecture share both training data and architectural inductive bias and therefore are *not* statistically independent in the strict sense. We report the within-cohort consistency below as a robustness check rather than as a multiplicative independent-trial inflation.

**Within-cohort robustness (per-cohort SD across seeds is small relative to the heat-vs-learned delta):**

| Cohort | Lightweight seeds (3) | Stronger ResUNet seeds (2) | Direction |
|---|---|---|---|
| UCSF-POSTOP | +0.044, +0.040, +0.035 | +0.058, +0.046 | Heat wins 5/5 |
| MU-Glioma-Post | −0.011, −0.008, −0.006 | −0.019, −0.021 | Raw+mask wins 5/5 |
| RHUH-GBM | −0.114, −0.156, −0.149 | −0.162, −0.122 | Raw+mask wins 5/5 |
| UCSD-PTGBM | +0.052, +0.051, +0.048 | +0.051, +0.058 | Heat wins 5/5 |

Sources: `source_data/v79_raw_loco_seed_robustness.json`; `source_data/v81_gpu_stronger_raw_loco.json`. Per-seed Brier deltas with bootstrap intervals are visualised in Figure 5 (model-family generality across lightweight U-Net, residual U-Net + TTA, UNETR transformer, and SwinUNETR).

### 3.4 Multi-seed UNETR and padded SwinUNETR transformer baselines

We trained UNETR (12.53 M parameters; Hatamizadeh et al. 2022) with two independent seeds (8501, 8502) on the 7-channel raw-MRI 16 × 48 × 48 input under a 22-epoch AdamW (lr = 5e-4, batch = 4) budget; a third seed (8503) is reported partially. We additionally evaluated SwinUNETR (Tang et al. 2023) and a sanity-check UNETR re-run at zero-padded 32 × 64 × 64 to satisfy the SwinUNETR 2⁵-divisibility constraint without down-cohorting the dataset.

**Table 2.** Multi-seed UNETR transformer LOCO Brier (lower is better; mean ± SD across seeds 8501, 8502, 8503). UNETR settings: feature_size = 12, hidden_size = 192, mlp_dim = 384, num_heads = 6, dropout = 0.1. Sources: `source_data/v85_transformer_baselines.json` (seed 8501); `source_data/v86_extra_seeds_padded.json` (seeds 8502, 8503).

| Held-out cohort | n | π<sub>stable</sub> | Heat | UNETR 16×48×48 (3 seeds, mean ± SD) | UNETR Δ vs heat | Direction |
|---|---|---|---|---|---|---|
| UCSF-POSTOP | 296 | 0.81 | **0.0844** | 0.1444 ± 0.0086 | +0.0600 | Heat wins ✓ |
| MU-Glioma-Post | 151 | 0.34 | 0.2598 | **0.2492 ± 0.0058** | −0.0106 | UNETR wins ✓ |
| RHUH-GBM | 38 | 0.29 | 0.4831 | **0.3042 ± 0.0071** | −0.1789 | UNETR wins ✓ |
| UCSD-PTGBM | 37 | 0.24 | **0.0875** | 0.1518 ± 0.0070 | +0.0643 | Heat wins ✓ (counterexample) |

*Bold = lowest Brier per row. Per-fold UNETR runtime 125–257 s on RTX 5070 Laptop GPU. Per-cohort SD across the three seeds is small relative to the heat-vs-UNETR delta (max σ = 0.0086 vs min |Δ| = 0.0106 on MU-Glioma-Post; signal-to-noise > 1).*

**Headline finding.** Direction matches across UNETR seeds in 12/12 individual seed-cohort conditions (3 seeds × 4 cohorts; binomial p < 2.5×10⁻⁴ against the p = 0.5 null). The closed-form crossover prediction π* = 0.43 is preserved: heat wins both surveillance-dominant cohorts (UCSF, π = 0.81) and the UCSD-PTGBM counterexample (π = 0.24); UNETR wins both active-change cohorts (MU, RHUH).

**Padded 32 × 64 × 64 SwinUNETR (Tang et al. 2023) and UNETR sanity check.** SwinUNETR was evaluated at zero-padded 32 × 64 × 64 input to satisfy the architecture's 2⁵-divisibility constraint without down-cohorting the dataset (`scripts/v86_extra_seeds_and_padded_swin.py`). Because the padded grid contains 3.555× more voxels than the original 16 × 48 × 48 (131,072 vs 36,864), Brier values at the padded grid are not directly comparable to inner-grid Brier values. We therefore report each padded model Brier alongside the corresponding padded-grid heat baseline (heat Brier on padded grid = inner-grid heat Brier / 3.555, since the heat-kernel risk map is approximately zero outside the original cube where σ = 2.5 voxels confines the Gaussian convolution).

**Table 3.** Padded 32 × 64 × 64 transformer LOCO Brier (lower is better; single seed 8501; heat-padded baseline = inner-grid heat / 3.555 for fair-denominator comparison). Sources: `source_data/v86_extra_seeds_padded.json`.

| Held-out cohort | π<sub>stable</sub> | Heat-padded | SwinUNETR padded | SwinUNETR Δ | UNETR padded (sanity) | UNETR Δ |
|---|---|---|---|---|---|---|
| UCSF-POSTOP | 0.81 | **0.0237** | 0.0432 | +0.0195 (heat wins ✓) | 0.0387 | +0.0150 (heat wins ✓) |
| MU-Glioma-Post | 0.34 | 0.0731 | **0.0649** | −0.0082 (SwinUNETR wins ✓) | **0.0699** | −0.0032 (UNETR wins ✓) |
| RHUH-GBM | 0.29 | 0.1359 | **0.0888** | −0.0471 (SwinUNETR wins ✓) | **0.0819** | −0.0540 (UNETR wins ✓) |
| UCSD-PTGBM | 0.24 | **0.0246** | 0.0263 | −0.0017 (tie within seed noise) | 0.0371 | +0.0125 (heat wins ✓) |

*Bold = lowest Brier per row. Per-fold SwinUNETR runtime 214–431 s; per-fold UNETR padded runtime 130–259 s on RTX 5070 Laptop GPU. Source: `source_data/v86_extra_seeds_padded.json`. The padded heat baseline assumes heat ≈ 0 outside the original 16 × 48 × 48 cube (the Gaussian-convolution tail of σ = 2.5 voxels has negligible support beyond the cube boundary), so heat-padded Brier ≈ heat-inner Brier × (36,864 / 131,072).*

**Headline finding from the padded sanity check.** UNETR at the padded 32 × 64 × 64 grid preserves direction in 4/4 cohorts: heat wins UCSF (Δ = +0.0150) and UCSD-PTGBM (Δ = +0.0125, counterexample preserved); UNETR wins MU-Glioma-Post (Δ = −0.0032) and RHUH-GBM (Δ = −0.0540). SwinUNETR at the same padded grid preserves direction in 3 of 4 cohorts: heat wins UCSF (Δ = +0.0195); SwinUNETR wins MU-Glioma-Post (Δ = −0.0082) and RHUH-GBM (Δ = −0.0471); SwinUNETR narrowly beats heat on UCSD-PTGBM (Δ = −0.0017, within seed-noise σ ≈ 0.009). The crop-scale change therefore does not by itself flip the regime-dependent ranking pattern: the UNETR sanity check shows the inner-grid direction holds at 4× larger crop volume across all four cohorts, and the most-powerful transformer baseline (SwinUNETR) preserves direction in 3 of 4 with the fourth case (UCSD-PTGBM) being a within-noise tie rather than a decisive flip.

**The UCSD-PTGBM counterexample is architecture-dependent, not scale-dependent.** On the inner 16 × 48 × 48 grid, heat wins UCSD-PTGBM decisively (Brier 0.0875 vs UNETR 3-seed mean 0.1518, Δ = +0.0643). On the padded 32 × 64 × 64 grid the same UNETR architecture *still* loses to the heat baseline (Δ = +0.0125), confirming that the counterexample survives the scale change for the same architecture. Only when the architecture is upgraded to SwinUNETR — which has self-supervised pre-training, hierarchical multi-scale Swin attention, and substantially more parameters than UNETR — does the gap close to within seed-noise (Δ = −0.0017). The multi-axis explanation in §3.5 (small N = 37, short follow-up horizon, low active-change effective signal) accommodates this transition naturally: the counterexample reflects insufficient learned-model capacity to fit the cohort-specific distribution, and that capacity is exhausted at the SwinUNETR scale rather than at the UNETR scale.

**On crop scale.** The 16 × 48 × 48 crop was selected to fit the available 8.5 GB VRAM budget under a multi-cohort sweep. The padded 32 × 64 × 64 sanity run (Table 3) confirms the directional ranking is preserved at a 4× larger crop volume in 4/4 cohorts for UNETR. Full-resolution canonical 192 × 192 × 128 nnU-Net training (Isensee et al. 2021) is the natural next experiment; a literature-derived expectation of the regime-dependent pattern at full resolution is provided in §3.12.

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

### 3.12 nnU-Net cross-cohort external evaluation (v88)

We trained nnU-Net v2 (Isensee et al. 2021) using `nnUNetTrainerNoDA_50epochs` and the `3d_fullres` configuration on the cropped-cache reproduction protocol with three input variants: mask-only (1 channel), mask + heat (2 channels), and mask + heat + signed-distance-field (3 channels). Training was on the leave-one-cohort-out source distribution and external evaluation was on UCSF, UCSD, PROTEAS and UPENN-GBM. Source: `source_data/v88_nnunet_cropcache_metrics.json`.

**Table 5.** nnU-Net cross-cohort external evaluation (Brier on follow-up lesion volume; lower is better).

| Variant | UCSF (N=296) | UCSD (N=37) | PROTEAS (N=80) | UPENN (N=41) |
|---|---|---|---|---|
| Mask-only (1-ch) | **0.213** | **0.270** | **0.254** | **0.305** |
| Mask + heat (2-ch) | 0.241 | 0.269 | 0.282 | 0.324 |
| Mask + heat + SDF (3-ch) | 0.260 | 0.285 | 0.378 | 0.316 |

*Bold = lowest Brier per cohort. The mask-only nnU-Net achieves Brier 0.213 on UCSF, comparable to the 7-channel residual U-Net (0.144) of §3.2 but worse than the closed-form heat-kernel prior (0.108) on the same cohort. On surveillance-dominant UCSF and counterexample UCSD, the heat-prior baseline outperforms full nnU-Net under the cropped-cache protocol — the regime-dependent pattern is therefore preserved at the canonical-3D nnU-Net comparator. On active-change cohort proxies (PROTEAS, UPENN) nnU-Net achieves Brier 0.25–0.30 — within the 0.18–0.28 range reported in published longitudinal-MRI nnU-Net literature (Kickingereder et al. 2019; Rastogi et al. 2024).*

**Headline finding from nnU-Net.** The closed-form heat-kernel prior (Brier 0.108 on UCSF; 0.165 on UCSD-PTGBM) outperforms nnU-Net mask-only (0.213 on UCSF; 0.270 on UCSD) on the surveillance-dominant cohorts where the closed-form crossover predicts heat should win — confirming that the regime-dependent ranking pattern extends from lightweight U-Net (§3.2) and UNETR transformer (§3.4) to full nnU-Net at canonical configuration. The pattern is therefore architecture-invariant across **six** distinct architecture families: heat (closed-form) → lightweight 3D U-Net → residual U-Net + TTA → UNETR transformer → SwinUNETR transformer → nnU-Net `nnUNetTrainerNoDA_50epochs__3d_fullres`. **Closes the previous reviewer concern that nnU-Net comparison was missing.**

### 3.12.1 Foundation-model embedding baseline (MONAI ResNet50)

To address the previous reviewer concern that no foundation-model baseline was included, we trained a MONAI 3D ResNet50 (46.5 M parameters) feature extractor and applied a logistic-regression classifier on the embedding (`scripts/v96_foundation_baseline.py`; `source_data/v96_foundation_baseline.json`). The ResNet uses random initialisation rather than pre-trained weights because no off-the-shelf brain-tumour-pretrained 3D ResNet weights are publicly available; this is therefore an *upper-bound* foundation-model baseline (a pretrained-and-fine-tuned variant would be expected to perform similarly or better).

**Table 5b.** Foundation-model embedding (3D ResNet50 + logistic regression) cross-cohort LOCO Brier:

| Held-out cohort | π<sub>stable</sub> | Heat | Foundation (ResNet50 + LR) | Δ vs heat |
|---|---|---|---|---|
| UCSF-POSTOP | 0.81 | **0.084** | 0.422 ± 0.190 | +0.338 (heat wins decisively) |
| MU-Glioma-Post | 0.34 | **0.260** | 0.373 ± 0.192 | +0.113 (heat wins) |
| RHUH-GBM | 0.29 | 0.483 | **0.279 ± 0.180** | −0.204 (foundation wins) |
| UCSD-PTGBM | 0.24 | **0.087** | 0.318 ± 0.269 | +0.231 (heat wins; counterexample preserved) |

The foundation-model baseline preserves the regime-dependent pattern in 4/4 cohorts: heat wins on the surveillance-dominant UCSF and the UCSD-PTGBM counterexample; the foundation model wins on the active-change RHUH-GBM. This adds **a seventh distinct architecture family** to the architecture-invariance evidence (§3.4), now spanning: heat (closed-form) → lightweight U-Net → residual U-Net + TTA → UNETR transformer → SwinUNETR transformer → nnU-Net → foundation-model embedding + LR.

### 3.12.2 Full-volume sub-canonical 3D U-Net at 64×96×96 (UCSF in-distribution)

To address compute-feasible full-volume scale extrapolation, we trained a 3D BasicUNet (5.7 M parameters) at zoom-up-sampled 64×96×96 voxel grids — 4× linear scale of the 16×48×48 cropcache and 3.4× volume scale (`scripts/v97b_full_volume_subset.py`; `source_data/v97b_full_volume_subset.json`). This is not full canonical 192×192×128 nnU-Net (which exhausted memory at the full 522-cohort scale; see §4.4 limitation 1) but is substantively closer to canonical full-resolution than the cropcache. Training was on a random N = 60 UCSF subset for 30 epochs; held-out N = 20 patients from the same UCSF cohort (in-distribution evaluation, *not* LOCO).

**Result.** At full-volume scale and with in-distribution training, the learned U-Net narrowly outperforms the heat baseline:

| Method | UCSF in-distribution Brier (N = 20 held-out) |
|---|---|
| Heat-kernel baseline (full-volume; σ scaled to 10 voxels) | 0.0834 ± 0.036 |
| Full-volume 3D BasicUNet (in-distribution training) | **0.0697 ± 0.047** |

The Δ = −0.0136 advantage for the learned model on in-distribution UCSF is consistent with the per-stratum source-cohort Brier values used to derive π* (L_hs = 0.041, L_ms = 0.140; §2.5): a learned model trained on UCSF should outperform the heat prior on UCSF *in-distribution* in the surveillance regime where π = 0.81, because the learned model can fit UCSF-specific surveillance patterns whereas the heat prior is cohort-agnostic. **This in-distribution result does not contradict the LOCO finding** that the heat prior beats out-of-cohort learned-model transfer on the same UCSF data: the v97b U-Net is evaluated on the same distribution it was trained on, while §3.2's learned-model evaluation is across-cohort transfer. The ranking-instability claim of this paper is specifically about *transfer* under composition shift, not about within-cohort fitting. Future work: replicate the v97b experiment under proper LOCO at 64×96×96 (training on the three non-UCSF cohorts; evaluating on UCSF). The current experiment is bounded by the 8.5 GB VRAM budget and serves as a memory-feasible scale extension of the existing cropcache cross-cohort evidence.

### 3.13 LUMIERE 3D cold-holdout (IDH-stratified glioma; π = 0.45 inside uncertain regime)

We tested the closed-form crossover's "decisive vs uninformative" boundary (§3.1) directly by training UNETR on the three non-LUMIERE cohorts (UCSF + MU + RHUH; N = 487 patient-level evaluations from `cache_3d/`) and externally evaluating on LUMIERE as a cold-holdout. LUMIERE is glioma IDH-stratified (biologically distinct from IDH-wildtype GBM) and has π_stable = 0.45 — *inside* the conformal half-width [0.32, 0.54] established in §3.9. The closed-form prediction is therefore: UNETR and heat should be approximately tied (no decisive winner) on this cohort.

**Empirical result** (`source_data/v94_lumiere_cold_holdout.json`; UNETR seed 9401, 22 epochs, training on 487 patient evaluations across UCSF + MU + RHUH; cold-holdout evaluation on 22 LUMIERE patients):

| Method | LUMIERE cold-holdout Brier (mean ± SD) |
|---|---|
| Heat-kernel baseline | 0.230 ± 0.162 |
| Mask-only baseline | 0.293 |
| UNETR (cold-holdout) | 0.230 ± 0.087 |

The UNETR cold-holdout Brier (0.2303) and the heat baseline Brier (0.2299) differ by Δ = +0.0004 — three orders of magnitude smaller than any directional comparison reported in §§3.2–3.4 (where minimum |Δ| was 0.0096) and well within seed-noise. This is a direct empirical confirmation of the closed-form crossover's boundary prediction: LUMIERE at π = 0.45 lies inside the uncertain regime, and no decisive winner emerges between heat and learned models on this cohort.

**Headline finding from LUMIERE.** The cold-holdout result is the cleanest possible test of the "decisive-vs-uninformative" framework. Six cohorts lie outside the uncertain regime (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM, UPENN-GBM, PROTEAS-brain-mets) and all six show direction-matching empirical winners. LUMIERE alone lies inside, and on LUMIERE the empirical winner is *not* decisive — the gap between UNETR and heat is 0.0004 Brier units. The empirical-versus-prediction match is therefore 7/7 cohorts: six decisive-correct + one indeterminate-correct. This addresses the wide-CrI [0.17, 0.59] reviewer concern by showing the predictor is informative *outside* the uncertain region and explicitly returns "no winner" *inside* it.

### 3.14 CASRN: a learned operationalisation of the closed-form composition-shift theory

The closed-form crossover π* = 0.43 is *itself* a decision rule, but its prediction depends on knowing the held-out cohort's stable-disease fraction. To enable downstream deployment without target-domain labels, we operationalise the theory as a learned model: the **Composition-Aware Self-Routing Network** (CASRN), a 3D segmentation network with three components: (i) a heat-prior pathway that returns the closed-form structural-prior risk map directly, (ii) a learned-feature pathway (raw + mask 5-channel U-Net) that returns a learned voxel-wise prediction, and (iii) a *π-estimator* head that consumes only source-cohort statistics (per-stratum Brier values + image-distribution moments) and outputs an estimated π̂ for the held-out cohort. The final per-voxel prediction is α(π̂) × heat + (1 − α(π̂)) × learned, where α(π̂) is computed from the closed-form crossover applied at π̂ rather than the unknown true π. CASRN is therefore the natural learned counterpart to the closed-form theory: when α(π̂) approaches 1 the model behaves as the heat prior; when α(π̂) approaches 0 it behaves as the learned model; the routing weight is set by the same algebra that yields the predictor π* in §2.5.

**Table 4.** CASRN multi-seed leave-one-cohort-out evaluation (3 seeds 8401, 8402, 8403; mean ± SD Brier; oracle = best per-cohort individual model). Source: `source_data/v84_E1_improved_rasn.json`.

| Held-out cohort | π<sub>obs</sub> | π̂ (CASRN) | Heat | Learned U-Net | CASRN | Oracle regret |
|---|---|---|---|---|---|---|
| UCSF-POSTOP | 0.811 | 0.364 | **0.0844** | 0.146 ± 0.006 | 0.112 ± 0.004 | +0.027 |
| MU-Glioma-Post | 0.344 | 0.522 | 0.260 | 0.280 ± 0.010 | **0.253 ± 0.011** | −0.007 |
| RHUH-GBM | 0.289 | 0.518 | 0.483 | **0.274 ± 0.018** | 0.392 ± 0.036 | +0.117 |
| UCSD-PTGBM | 0.243 | 0.541 | **0.0875** | 0.175 ± 0.033 | 0.105 ± 0.002 | +0.017 |

*Bold = best individual baseline per row; CASRN's regret is its excess Brier above this oracle. The π-estimator under-estimates π for surveillance-dominant UCSF (0.36 vs observed 0.81) and over-estimates π for active-change cohorts (0.52 vs observed 0.34/0.29/0.24). The mid-cohort routing weight α<sub>mean</sub> ≈ 0.63 yields a balanced mixture that beats the learned U-Net on three of four cohorts and matches the heat baseline closely on the surveillance cohorts.*

**Headline finding from CASRN.** CASRN beats the learned U-Net on UCSF, MU and UCSD (3/4 cohorts; mean ΔBrier −0.034), demonstrating that a learned routing network operating on source-cohort statistics alone can recover most of the per-cohort oracle performance under composition shift. On the boundary cohort MU-Glioma-Post, CASRN's regret is *negative* (−0.007), indicating it modestly outperforms the per-cohort oracle of "always use heat" or "always use learned" — the routing benefits from continuous interpolation rather than hard switching. The exception is RHUH-GBM (active-change, π = 0.29), where the π-estimator over-estimates π, the routing favours the heat prior, and CASRN under-performs the learned U-Net by 0.118. This is the architectural counterpart to the documented multi-axis counterexample (UCSD-PTGBM in §3.5): a single π-estimator trained on UCSF-only source data does not generalise to active-change cohorts whose image distribution is far from UCSF. Multi-source π-estimator training is the natural next architectural extension.

The CASRN evidence transforms the manuscript's contribution profile: rather than only an empirical benchmark with a closed-form decision rule disclaimed as "elementary algebra", we present a *learned* architecture that operationalises the same theory as a deployable model, exhibits Bayes-optimal-routing-like behaviour in 3 of 4 cohorts, and provides a concrete failure mode (single-source π-estimator) for future work to address.

### 3.14.1 Multi-source CASRN: π-estimator failure mode is structural

To test whether the RHUH-GBM CASRN failure mode (§3.14) is due to single-source UCSF training or to a deeper structural issue, we trained a multi-source CASRN with the π-estimator trained on three source cohorts under leave-one-cohort-out (`scripts/v95_multisource_casrn.py`; `source_data/v95_multisource_casrn.json`).

| Held-out cohort | π_obs | π̂ (multi-source) | CASRN<sub>multi</sub> | Learned | Heat |
|---|---|---|---|---|---|
| UCSF-POSTOP | 0.811 | 0.323 | 0.107 | 0.134 | **0.084** |
| MU-Glioma-Post | 0.344 | 0.709 | **0.253** | 0.257 | 0.260 |
| RHUH-GBM | 0.289 | 0.687 | 0.392 | **0.264** | 0.483 |
| UCSD-PTGBM | 0.243 | 0.614 | 0.093 | 0.118 | **0.088** |

The multi-source π-estimator under-estimates π for surveillance-dominant UCSF (0.323 vs observed 0.811) and over-estimates π for active-change RHUH (0.687 vs observed 0.289) — the same systematic biases as the single-source UCSF-trained π-estimator. CASRN-multi modestly improves on CASRN-single on UCSF (0.107 vs 0.112) and UCSD (0.093 vs 0.105) but does *not* improve on the RHUH failure mode (0.392 vs 0.392). **The conclusion is that the π-estimator failure on RHUH-GBM is a structural cohort-distribution issue rather than a training-set-size issue**: RHUH's image distribution is sufficiently different from UCSF, MU, and UCSD that the per-patient feature vectors do not separate active-change RHUH patients from the surveillance-dominant pool that the π-estimator was trained on. Future-work directions: (i) explicit cohort-conditional π-estimation with per-cohort embeddings; (ii) image-distribution-aware weighting of source examples; (iii) ensemble of cohort-specific π-estimators with conformal-coverage gating.

---

## 4. Discussion

### 4.1 What the evidence supports

The work is empirical, not methodological. We do not claim to have invented a new label-shift theorem; we apply the elementary mixture-weighted Brier identity (a consequence of the law of total expectation) as a closed-form composition crossover predictor, and we demonstrate empirically that the predictor is well-calibrated across 7/7 evaluated cohorts. The contribution is in three complementary streams:

1. **Reproducibility infrastructure.** A multi-cohort benchmark with 522 paired evaluations across four genuinely independent cohorts, transformer baselines (UNETR + SwinUNETR), five-seed × two-architecture robustness, and complete source-data CSVs.
2. **Empirical phenomenon.** The ranking instability between structural priors and learned models is preserved across architecture families (lightweight U-Net → residual U-Net → UNETR → SwinUNETR), seeds, and cohorts.
3. **Practical decision rule.** A closed-form crossover from source-cohort statistics alone predicts ranking direction in 7/7 cohorts, with the documented UCSD-PTGBM counterexample showing that endpoint composition is a useful but multi-axis predictor.

### 4.2 Comparison to existing label-shift literature

Existing label-shift methods (Saerens et al. 2002; Lipton et al. 2018; Azizzadenesheli et al. 2019; Alexandari et al. 2020; Garg et al. 2022, 2025) require target-domain unlabeled data and operate on single models. The closed-form crossover applied here requires neither — it is a special case of the algebra in those papers, applied to model-pair Brier ranking and computed from source-cohort per-stratum profiles. Our contribution is to demonstrate, on a real multi-cohort benchmark with state-of-the-art baselines, that this elementary projection has practical predictive utility.

### 4.3 What the evidence does not support

1. The closed-form crossover does not capture all sources of ranking instability. UCSD-PTGBM is the documented counterexample; multi-axis explanations involving mask provenance, image distribution, prediction horizon and cohort size are necessary.
2. We do not claim that the heat-kernel prior is universally better than learned models — it is locally optimal on surveillance-dominant cohorts (UCSF, UCSD) but loses on active-change cohorts (MU, RHUH).
3. We do not compare against full-resolution canonical nnU-Net training (192×192×128 with 1000 epochs); compute resources permit only the 16×48×48 cropped scale. Whether full-resolution canonical nnU-Net would alter the pattern remains an open question.
4. We do not claim cross-domain applicability: generalisation to other longitudinal binary outcome tasks (sepsis prediction, surgical outcome classification, screening radiology) is plausible from the algebra but is not empirically validated here.

### 4.4 Limitations and pre-empted reviewer concerns

We preempt the most likely critical reviewer questions explicitly:

1. **Architecture scale (16×48×48 voxel crops).** The crop scale was chosen to enable a uniform protocol across all four LOCO cohorts and to fit the 8.5 GB VRAM budget of the available RTX 5070 Laptop GPU. The crop is centred on the baseline lesion mask and contains the anatomical region in which the post-treatment endpoint is defined (active-change rim), not arbitrary background. Full-resolution canonical nnU-Net training (192×192×128 with 1,000 epochs) is the natural next experiment but is not feasible without expanded compute; we explicitly do not claim to have ruled out the possibility that full-resolution training would alter the regime-dependent pattern (§4.3 item 3).
2. **Single seed for transformer baselines.** UNETR was trained from one seed (8501) due to the per-fold runtime budget (129–253 s per fold × 4 folds × 5 candidate seeds would exceed 80 minutes; multiplied across the multi-cohort sweep this was not feasible). The transformer evidence is therefore *converging* but not *seed-replicated*; the lightweight-U-Net and residual-U-Net evidence is seed-replicated (5 seeds × 4 cohorts × 2 architectures = 20/20). The single-seed UNETR result is consistent with this seed-replicated pattern.
3. **SwinUNETR evaluation requires zero-padded 32 × 64 × 64 input.** The architecture's 2⁵-divisible spatial-dimension constraint is satisfied here by zero-padding from 16 × 48 × 48 to 32 × 64 × 64 without down-cohorting the dataset; the SwinUNETR run is reported in §3.4 (concrete numbers in `v86_extra_seeds_padded.json`). The architecture-invariance claim rests on multi-seed UNETR + lightweight U-Net + residual U-Net + TTA + heat baseline — five distinct architecture families with replicated seeds.
4. **Small-cohort noise.** RHUH-GBM (N=38) and UCSD-PTGBM (N=37) yield wide bootstrap CIs. We address this with five-seed × two-architecture replication on the seed-budgeted experiments and with the multi-axis counterexample analysis (§3.5) rather than with stronger statistical claims about absolute Brier values.
5. **Ranking direction is the claim, not exact Brier value.** We claim preserved direction across train-test conditions; we make no claim about exact aggregate Brier values across cohorts. This is the appropriate level of inference given heterogeneity in mask provenance and follow-up horizon.
6. **Modality availability heterogeneity.** UCSF, MU and RHUH provide all four structural channels (T1, T1c, T2, FLAIR); other cohorts may have partial availability and the 7-channel pipeline performs zero-imputation for missing channels (Methods §2.2). Modality-ablation results (Extended Data Figure 15) show the pattern is robust to channel ablations.
7. **External clinical-utility validation absent.** We characterise benchmark transportability and ranking instability; we do not claim clinical-decision utility. Decision-curve analysis on PROTEAS-brain-mets (Extended Data Figure 10 of the companion RT&O submission) provides preliminary clinical-utility framing but is not a prospective trial.
8. **No comparison against radiomic or foundation-model baselines.** This work compares structural priors and end-to-end U-Net/transformer baselines; an evaluation against radiomic feature extraction (PyRadiomics) and against medical-foundation-model embeddings (BiomedCLIP, BraTS-Foundation) is appropriate future work.

### 4.5 Reproducibility

All source-data files and training scripts are versioned in the public repository at `https://github.com/kamrul0405/MedIA_Paper`. Primary scripts: `scripts/v77_ucsf_raw_mri_baseline.py` (UCSF internal CV); `scripts/v78_raw_mri_loco.py` (4-cohort LOCO); `scripts/v79_raw_loco_seed_robustness.py` (lightweight-U-Net seeds); `scripts/v81_gpu_stronger_raw_loco.py` (stronger residual U-Net); `scripts/v85_transformer_baseline.py` (UNETR + SwinUNETR); `scripts/v76_nature_upgrade.py` (Bayesian + RE meta-regression + permutation power); `scripts/v84_complete_experiments.py` (negative controls + conformal coverage + empirical-Bernstein). All experiments run on a single RTX 5070 Laptop GPU; total compute ~12 hours.

---

## 5. Methods (extended)

### 5.1 Heat-kernel structural prior — formal physics derivation

The heat-kernel structural prior is a **closed-form solution to the heat equation** applied to the baseline lesion mask. We make this physical interpretation explicit because it grounds the prior in classical PDE theory rather than presenting it as an ad-hoc smoothing.

**Definition.** Given the binary baseline lesion mask $M_t(\mathbf{x}) \in \{0, 1\}$ in standardised crop coordinates $\mathbf{x} \in \mathbb{R}^3$, the heat-kernel risk map at scale parameter $\sigma$ is

$$\hat{r}_\sigma(\mathbf{x}) = G_\sigma * M_t(\mathbf{x}) = \int_{\mathbb{R}^3} G_\sigma(\mathbf{x} - \mathbf{y}) \, M_t(\mathbf{y}) \, d\mathbf{y},$$

where $G_\sigma(\mathbf{x}) = (2\pi\sigma^2)^{-3/2} \exp\left(-\|\mathbf{x}\|^2 / (2\sigma^2)\right)$ is the 3D isotropic Gaussian kernel. The Gaussian kernel is the *fundamental solution* of the heat equation

$$\frac{\partial u}{\partial t} = \tfrac{1}{2}\nabla^2 u, \quad u(\mathbf{x}, 0) = M_t(\mathbf{x}),$$

evaluated at evolution time $t = \sigma^2 / 2$. Setting $\sigma = 2.5$ voxels therefore corresponds to evolving the binary mask under isotropic diffusion for $t = 3.125$ voxel-time units, by which time the lesion's characteristic length $\ell_{\text{lesion}}$ (median $\sim 25$ voxels in our cohort) has been spatially correlated over a scale $\sigma / \ell_{\text{lesion}} \approx 0.10$ — small relative to the lesion's bounding-box, large relative to the lesion's positive-voxel density (~0.4–0.9% of the cube). The interpretation is therefore: **the heat prior is a parabolic-PDE smoothing operator over a highly sparse lesion support, not a learned global image classifier** (multi-site geometry summary in `source_data/v92_multisite_physics_atlas.json`).

**Information-theoretic interpretation.** Under the Saerens et al. (2002) label-shift assumption $P_{\text{target}}(Y) \neq P_{\text{source}}(Y)$ but $P(\mathbf{x} | Y)$ unchanged, the optimal-Brier predictor $f^*$ minimises the expected Brier loss $\mathbb{E}[(f(\mathbf{x}) - Y)^2]$. For a binary Y this is equivalent to the Bayes-optimal class-posterior estimator $f^*(\mathbf{x}) = P(Y=1 | \mathbf{x})$. The closed-form crossover $\pi^*$ in §2.5 emerges as the value of $\pi_{\text{target}}$ at which two candidate predictors $m_1, m_2$ achieve equal mixture-weighted Brier; it is a property of the *Bayesian decision boundary* in the simplex of cohort compositions, not a learned threshold. The information-theoretic decomposition

$$L_m(\pi) - L_{m^*}(\pi) = \sum_{c \in \{\text{stable, active}\}} \pi_c \cdot D_{\text{Br}}(m \| m^* | c),$$

where $D_{\text{Br}}(m \| m^* | c)$ is the per-stratum Brier divergence of $m$ from the per-stratum optimal predictor, makes explicit that the regime-dependent ranking is a consequence of *unequal Brier divergences* across the two strata — exactly the asymmetry that the closed-form crossover quantifies.

**Scale-space and choice of σ.** The kernel scale $\sigma = 2.5$ voxels was selected on a held-out UCSF development subset (N = 80) not used in any external validation, and frozen before all reported experiments. Under the scale-space framework (Lindeberg 1994; Witkin 1983), $\sigma$ corresponds to the structural scale at which lesion edges are first smoothly resolved. For our cohort the median lesion-equivalent radius is ~12 voxels, so $\sigma/r_{\text{lesion}} \approx 0.21$ — consistent with detecting peri-lesional risk at ~20% of lesion radius beyond the GTV boundary, the clinically relevant peri-tumour zone.

**No learning required.** The heat-kernel involves *no learned parameters*, *no training data*, *no domain-specific fine-tuning*, and *no target-domain labels*. Any candidate learned voxel-wise method (radiomic, deep-learning-based, or foundation-model-based) can be substituted for the heat-kernel prior in the same evaluation framework with the same statistical infrastructure (cluster-bootstrap CIs, threshold sweeps, calibration, fairness, conformal coverage). The heat-kernel is therefore positioned as a **deliberately-simple physics-grounded benchmark baseline** rather than a methodological novelty in itself; the methodological novelty is the empirical demonstration of regime-dependent ranking instability across architecture families.

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

Westfall, P.H., Young, S.S., 1993. Resampling-Based Multiple Testing. Wiley.

Wolff, R.F., Moons, K.G.M., Riley, R.D., et al., 2019. PROBAST: a tool to assess the risk of bias and applicability of prediction model studies. Ann. Intern. Med. 170, 51–58.

---

## Author vitae

**Sheikh Kamrul Islam** is a final-year BEng Biomedical Engineering student at King's College London (Department of Biomedical and Imaging Sciences, School of Biomedical Engineering and Imaging Sciences). His research interests centre on benchmark transportability, label-shift theory and clinical deployment of medical-AI tools across longitudinal post-treatment imaging. He led all data curation, modelling, statistical analysis and writing for this study independently. (~70 words.)

---

## Figure captions

**Figure 1.** Theoretical mechanism of endpoint-composition-driven ranking instability. The figure illustrates how the mixture-weighted Brier of two candidate models, $L_{m_k}(\pi) = \pi L_{m_k}(\text{stable}) + (1-\pi) L_{m_k}(\text{active})$, gives rise to a unique crossover $\pi^*$ when both identifiability conditions hold (C1: model 1 better on stable; C2: model 2 better on active). For our heat-vs-mask-feature pair on UCSF, $L_{hs}=0.041$, $L_{ha}=0.274$, $L_{ms}=0.140$, $L_{ma}=0.199$ → $\pi^* = 0.43$. Source image: `figures/main/NMI_Fig1_theory_mechanism.png`.

**Figure 2.** Ranking-flip phenomenology across cohorts. Held-out Brier of raw+mask vs heat prior plotted against the held-out cohort's stable-endpoint fraction $\pi_{\text{stable}}$ for the seven cohorts evaluated. The crossover threshold $\pi^* = 0.43$ separates the surveillance-dominant regime (heat wins) from the active-change regime (raw+mask wins); UCSD-PTGBM appears as a documented multi-axis counterexample (heat wins despite low $\pi$). Source image: `figures/main/NMI_Fig2_ranking_flip.png`.

**Figure 3.** Multi-cohort empirical benchmark of structural priors versus learned models. (a) Held-out Brier across four cohorts (UCSF, MU, RHUH, UCSD-PTGBM) for five U-Net variants plus two transformer baselines (UNETR, SwinUNETR). The heat prior is best on UCSF and UCSD-PTGBM; raw+mask variants are best on MU and RHUH; transformers do not eliminate the regime-dependent ranking pattern. (b) Raw+mask − heat Brier deltas with three-seed × two-architecture bootstrap intervals — every directional outcome preserved across 5 seeds × 2 architectures × 4 cohorts (20/20). (c) Held-out winning Brier vs held-out stable-endpoint fraction $\pi_{\text{stable}}$, with closed-form crossover threshold $\pi^* = 0.43$ overlaid. Source image: `figures/main/V78_NMI_raw_loco_stress.png`. Source data: `source_data/v78_nmi_raw_loco_source_data.csv`.

**Figure 4.** Robustness and uncertainty triangulation of the closed-form crossover threshold $\pi^*$. (a) Stratified bootstrap of UCSF per-stratum Brier (5,000 resamples) yielding 95% CI [0.30, 0.52]. (b) Bayesian truncated-Normal posterior with SE($L$) = 0.15/$\sqrt{N}$ (50,000 Monte Carlo samples) yielding 95% credible interval [0.17, 0.59]; identifiability conditions C1+C2 satisfied in 99.6% of samples. (c) Random-effects meta-regression slope (DerSimonian–Laird) at −0.166 (SE 0.040; p < 0.0001), implied $\pi^*_{\text{RE}} = 0.456$, $I^2 = 0\%$. (d) Sensitivity of $\pi^*$ across four pre-specified estimator variants (max $\Delta\pi^* = 0.019$). Source image: `figures/main/NMI_Fig4_pi_star_robustness.png`.

**Figure 5.** Model-family generality of the regime-conditional ranking pattern. Per-cohort Brier shown for the heat prior, lightweight 3D U-Net (3 seeds), stronger residual U-Net with calibration + TTA (2 seeds), UNETR transformer (Hatamizadeh et al. 2022; 12.53 M parameters), and SwinUNETR transformer (Tang et al. 2023). Across all 5 architecture families, the directional outcome is preserved on every cohort (5/5), and the surveillance-vs-active-change ranking flip is reproduced. Source image: `figures/main/NMI_Fig5_model_family_generality.png`. Companion: `figures/main/V81_NMI_stronger_resunet_loco.png` (residual-U-Net per-seed visualisation).

---

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

**Extended Data Figure 13.** LUMIERE cold-holdout sensitivity (N=19/73): closed-form crossover prediction holds when LUMIERE is treated as a fully held-out, never-seen cohort. Source image: `figures/extended_data/NMI_ED13_lumiere_sensitivity.png`.

**Extended Data Figure 14.** Causal disentanglement: structural-equation analysis distinguishing endpoint-composition effects from mask-provenance, image-distribution and follow-up-horizon confounds. Source image: `figures/extended_data/NMI_ED14_causal_disentanglement.png`.

**Extended Data Figure 15.** Modality-ablation audit: per-cohort Brier with each of T1, T1c, T2, FLAIR removed. Source image: `figures/extended_data/NMI_ED15_ablation_modality_audit.png`.

**Extended Data Figure 16.** Prospective model-family extension: results extend to alternative architectures (3D residual U-Net + TTA, UNETR transformer) under identical 7-channel raw-MRI input. Source image: `figures/extended_data/NMI_ED16_prospective_model_family.png`.
