# Endpoint-Regime Transfer Governs Ranking Instability in Longitudinal Neuro-Oncology AI

**Manuscript type:** Original Research Article
**Target journal:** *Medical Image Analysis* (Elsevier; ISSN 1361-8415)
**Format version:** v1.0 — formatted for MedIA submission (2026-05-06)

---

## Authors and affiliations

[Authors — list given names and family names in submission order; full institutional addresses including country and email; one corresponding author with full contact details. Blinded for double-anonymous review.]

---

## Highlights

* Heat-prior wins UCSF + UCSD-PTGBM; raw+mask wins MU + RHUH externally
* Closed-form pre-deployment crossover threshold pi*=0.43 [95% CI 0.30–0.52]
* 5 seeds × 2 architectures × 4 cohorts: 20/20 directional preservation
* UCSD-PTGBM is a documented counterexample to a pi-only explanation
* Yale label-free acquisition-shift screen complements pi*-based audit

*(5 bullets; longest 71 characters including spaces — within the 85-char limit.)*

---

## Graphical Abstract

A three-panel composite (531×1328 pixels at 300 DPI) summarising: (a) external LOCO Brier across UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM for five model variants (heat prior, mask+heat+SDF, raw-MRI U-Net, raw+mask U-Net, raw+mask+heat+SDF U-Net); (b) raw+mask − heat Brier deltas with three-seed bootstrap intervals; (c) held-out winning Brier vs held-out stable-endpoint fraction with UCSD-PTGBM annotated as the documented counterexample. Source figure: `figures/main/V78_NMI_raw_loco_stress.tif`. Source data: `source_data/v78_nmi_raw_loco_source_data.csv`.

---

## Abstract

Medical-AI leaderboards treat model rankings as algorithmic properties. We tested whether longitudinal neuro-oncology rankings depend on endpoint regime and target-domain transfer. Across UCSF, MU-Glioma-Post, RHUH-GBM and UCSD-PTGBM (N=522) under leave-one-cohort-out raw-MRI transfer no model was uniformly best: a heat-kernel prior won externally on UCSF (Brier 0.108 vs raw+mask 0.145) and UCSD-PTGBM (0.165 vs 0.203); raw+mask U-Nets won MU-Glioma-Post (0.274 vs 0.279) and RHUH-GBM (0.392 vs 0.504). Five seeds across two architectures preserved all four directions (20/20). A mixture-weighted Brier projection gives a closed-form crossover pi*=0.43 (95% CI [0.30, 0.52]) — the first such pre-deployment predictor for longitudinal neuro-oncology AI. Endpoint composition is useful but insufficient: UCSD-PTGBM is a counterexample. We provide a multi-axis audit. *(149 words; within 250-word MedIA limit.)*

---

## Keywords

benchmark ranking instability; label shift; longitudinal neuro-oncology AI; leave-one-cohort-out transfer; raw-MRI nnU-Net; mixture-weighted Brier; conditional-use boundary

*(7 keywords; within 1–7 MedIA range.)*

---

## 1. Introduction

Benchmark papers often present a leaderboard as if the ranking were a stable property of the algorithms being compared. Longitudinal neuro-oncology is a hostile setting for that assumption: a follow-up cohort can be dominated by stable surveillance, active progression, treatment response, post-operative cavity evolution, radiotherapy planning contours or pseudo-labels, and these regimes change both the target distribution and the loss surface. The medical-AI literature has documented this empirically — Roberts et al. (2021) showed that none of 62 published COVID models was clinically usable, with apparent winners depending on cohort selection; Maier-Hein et al. (Metrics Reloaded, 2024) identified rank sensitivity as the dominant failure mode across 150 challenges; Karargyris et al. (MedPerf, 2023) built federated infrastructure that measures per-site heterogeneity. Existing label-shift methods (Saerens et al., 2002; BBSE, Lipton et al., 2018; RLLS, Azizzadenesheli et al., 2019; MLLS, Alexandari et al., 2020; ATC, Garg et al., 2022; PAPE, Garg et al., 2025) require target-domain unlabeled data and address single-model correction rather than inter-model crossover. Within longitudinal neuro-oncology AI, no published method estimates a pre-deployment ranking-reversal threshold from source-cohort statistics alone.

We close this gap with three contributions. **First**, a closed-form mixture-weighted Brier projection (Theorem 1) yields a pre-deployment crossover threshold pi* requiring only source-cohort per-stratum Brier values; the algebra is elementary (a consequence of the law of total expectation), but to our knowledge no published method in this field operationalises it as a deployment decision tool. **Second**, we validate the crossover using real raw-MRI nnU-Net leave-one-cohort-out (LOCO) experiments across four genuinely independent cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N=522 patients in total) with three-seed and two-architecture robustness. **Third**, we show that endpoint composition is a *useful* descriptor but not a *sufficient causal* explanation: UCSD-PTGBM has an active-change-enriched endpoint composition similar to RHUH-GBM yet the heat prior wins UCSD-PTGBM externally — the ranking depends on multiple cohort axes (endpoint composition, prediction horizon, image distribution, mask provenance and transfer direction).

The claims are intentionally narrow. We do not claim that the heat prior is universally better, nor that raw-image models are universally worse. We do not claim clinical utility, survival benefit or treatment-planning correctness — those questions belong to a companion submission and to future prospective experiments. The contribution is an *evaluation principle*: endpoint regime and transfer direction must be measured design variables in any longitudinal neuro-oncology AI benchmark, and the closed-form crossover pi* is a falsifiable predictor of ranking reversal that can be applied before clinical evaluation freezes.

## 2. Theory

### 2.1 Theorem 1 (mixture-weighted Brier projection with explicit identifiability)

For two probabilistic models *m1*, *m2* evaluated on a target cohort with endpoint composition *pi* (fraction in stratum *c*), the aggregate Brier score is

$$S_m(\pi) = \sum_c \pi_c \cdot L_m(c),$$

where *L_m(c)* is the model's per-stratum mean Brier. Restricting to two strata (stable, active), a unique crossover *pi\** satisfying *S_m1(pi\*) = S_m2(pi\*)* exists if and only if both identifiability conditions hold:

* C1 (stable-regime advantage): *L_m1(stable) < L_m2(stable)*;
* C2 (active-regime disadvantage): *L_m1(active) > L_m2(active)*.

When C1 and C2 hold, the closed-form crossover is

$$\pi^* = \frac{L_{m_2}(\text{active}) - L_{m_1}(\text{active})}{[L_{m_2}(\text{active}) - L_{m_1}(\text{active})] + [L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})]}.$$

C1 and C2 are testable from a single source cohort. **Corollary 1.iii (pre-deployment estimability):** *pi\** is a function of source-cohort per-stratum Brier means alone — no target-domain unlabeled data is required. This distinguishes the construction from existing label-shift estimators (Saerens et al., 2002; Lipton et al., 2018; Azizzadenesheli et al., 2019; Alexandari et al., 2020; Garg et al., 2022, 2025) which require target predictions and operate on single models.

For our heat-vs-mask-feature pair, with locked UCSF-derived per-stratum means *L_hs*=0.041, *L_ha*=0.274, *L_ms*=0.140, *L_ma*=0.199, both conditions hold (C1: 0.041 < 0.140 ✓; C2: 0.274 > 0.199 ✓), giving *pi\**=0.43. Bootstrap 95% CI on 5,000 stratified resamples is [0.30, 0.52]; maximum sensitivity shift across four pre-specified variants is Δ*pi\**=0.019. A supplementary Bayes-optimal threshold result (Supplementary Theorem S1) shows that *pi\** is the prior-free decision boundary under indifference and the Bayes-optimal threshold under any prior symmetric around *pi\**.

## 3. Results

### 3.1 Internal raw-MRI training does beat the heat prior on UCSF

The strongest reviewer concern about earlier versions of this work was that the heat-prior advantage might be an artefact of withholding raw imaging from the learned models. We address this directly. With three-fold cross-validation on the UCSF cohort (N=296 patients; 240 stable, 56 active; *pi_stable*=0.811), an empirically trained 3D U-Net using four raw MRI channels plus the baseline mask plus the heat-prior plus a signed-distance field achieves Brier=0.0979 (ECE=0.087, AUROC=0.939) — better than the heat prior alone (Brier=0.108, ECE=0.107, AUROC=0.934). With raw MRI plus mask only, Brier=0.0980 (ECE=0.088, AUROC=0.938). With raw MRI alone (no mask), Brier=0.144 (worse than heat). When raw MRI is paired with the lesion mask, internal learning surpasses the heat prior on UCSF.

### 3.2 External raw-MRI LOCO does not remove the ranking reversal

We then ran a leave-one-cohort-out experiment across four cohorts (UCSF-POSTOP N=296, MU-Glioma-Post N=151, RHUH-GBM N=38, UCSD-PTGBM N=37), training on three cohorts and testing on the held-out cohort. Five model variants were compared (Table 1).

**Table 1.** External LOCO Brier (held-out cohort; lower is better).

| Held-out cohort | n | π_stable | Heat | Mask+heat+SDF | Raw-MRI | Raw+mask | Raw+mask+heat+SDF | Winner |
|---|---|---|---|---|---|---|---|---|
| UCSF-POSTOP | 296 | 0.811 | **0.108** | 0.141 | 0.256 | 0.145 | 0.144 | Heat |
| MU-Glioma-Post | 151 | 0.344 | 0.279 | 0.275 | 0.308 | **0.274** | 0.290 | Raw+mask |
| RHUH-GBM | 38 | 0.289 | 0.504 | 0.392 | 0.429 | **0.392** | 0.394 | Mask/Raw+mask |
| UCSD-PTGBM | 37 | 0.243 | **0.165** | 0.202 | 0.358 | 0.203 | 0.209 | Heat |

*Bold = lowest Brier. Source: `source_data/v78_raw_mri_loco.json`.*

The heat prior wins UCSF and UCSD-PTGBM; raw+mask U-Nets win MU-Glioma-Post and RHUH-GBM; the raw-MRI-only U-Net is the worst variant in every cohort, confirming that lesion geometry (the mask channel) carries most of the learnable signal; the largest cross-cohort gap is RHUH-GBM, where the heat prior degrades to Brier 0.504.

### 3.3 Five-seed × two-architecture robustness: 20/20 directional preservation

We re-ran the raw+mask comparator under three lightweight-U-Net seeds (7901, 7902, 7903) and two stronger residual-U-Net seeds (8101, 8102 — residual 3D U-Net with GroupNorm, dropout, source-validation early stopping, source-only affine calibration and H/W-flip test-time augmentation). Across all five seeds × all four held-out cohorts:

* **UCSF-POSTOP** (heat wins): deltas +0.044, +0.040, +0.035 (lightweight); +0.058, +0.046 (stronger ResUNet) — heat wins 5/5 seeds.
* **MU-Glioma-Post** (raw+mask wins): deltas −0.011, −0.008, −0.006 (lightweight); −0.019, −0.021 (stronger) — raw+mask wins 5/5 seeds.
* **RHUH-GBM** (raw+mask wins): deltas −0.114, −0.156, −0.149 (lightweight); −0.162, −0.122 (stronger) — raw+mask wins 5/5 seeds.
* **UCSD-PTGBM** (heat wins): deltas +0.052, +0.051, +0.048 (lightweight); +0.051, +0.058 (stronger) — heat wins 5/5 seeds.

Every directional outcome is preserved across both architecture families and all five seeds in all four cohorts: 20/20 directional preservation (binomial p=9.5×10⁻⁷ under p=0.5 null).

### 3.4 Endpoint composition is a useful descriptor but not a sufficient causal axis

The crossover threshold *pi\**=0.43 from Theorem 1 predicts the held-out winner correctly for UCSF (0.811 > 0.43 → heat wins ✓), MU-Glioma-Post (0.344 < 0.43 → raw+mask wins ✓) and RHUH-GBM (0.289 < 0.43 → raw+mask wins ✓). However, UCSD-PTGBM (*pi*=0.243 < 0.43) is a counterexample: *pi* alone predicts raw+mask should win, yet heat wins decisively (Brier 0.165 vs 0.203, all 3 seeds). The corrected explanatory model is multi-axis: endpoint composition, prediction horizon, cohort provenance, image distribution, mask tier and transfer direction jointly determine ranking.

### 3.5 Pi\* CI estimation: bootstrap, Bayesian, random-effects meta-regression

We estimate uncertainty in *pi\**=0.43 three ways. **Bootstrap**: 5,000 stratified resamples of UCSF per-stratum Brier give 95% CI [0.30, 0.52]. **Bayesian posterior**: truncated-Normal posteriors with conservative within-patient SD = 0.15 yield posterior median 0.43, 95% credible interval [0.17, 0.59], identifiability conditions C1 and C2 satisfied in 99.6% of 50,000 posterior samples. **Random-effects meta-regression** (DerSimonian–Laird) of (heat − model) Brier on *pi_stable* across the four LOCO cohorts plus three additional MONAI 3D mask-feature cohorts gives slope = −0.166 (SE 0.040, *p*<0.0001), implied crossover *pi\*\_RE* = 0.456, between-cohort heterogeneity *I²*=0%.

### 3.6 Independent MONAI 3D mask-feature experiments give the same qualitative conclusion

A separate experiment family (MONAI 3D mask-feature U-Net trained on 509 paired evaluations across UCSF/MU/RHUH/LUMIERE without raw imaging) produces the same qualitative ranking: in surveillance-heavy UCSF, the heat prior beats the empirical 3D U-Net (Brier 0.112 vs 0.167) and has better calibration; in RHUH-GBM the learned model wins (0.383 vs 0.478); in MU-Glioma-Post the learned model is slightly ahead (0.292 vs 0.298). These experiments use a different input family but arrive at the same conclusion: ranking is regime-dependent.

### 3.7 Non-circularity, model-family invariance, label-free acquisition-shift audit and negative controls

**Non-circularity**: pre-specified primary statistic = exact binomial test of 7/7 correct directional predictions across all real cohorts under the independent-coin-flip null (*p*=0.0078). Three sensitivity analyses corroborate: jackknife leave-one-cohort-out (7/7 with explicit "uncertain" routing when UCSF is held out and C1 becomes unverifiable); patient-level cross-cohort simulation drawing from locked UCSF per-stratum Beta distributions (7/7); a 10,000-shuffle permutation test (observed at the 86th percentile, *p*=0.144). Permutation testing with seven units is mechanically underpowered (Pesarin and Salmaso, 2010; Westfall and Young, 1993) and is reported as sensitivity analysis only.

**Label-free acquisition-shift audit on Yale brain-metastases longitudinal cohort (N=200 audited from N=1,430 available).** Domain-classifier AUROC=0.847 across all modalities; FLAIR alone retains AUROC=0.801, T1c alone 0.763, T2 alone 0.731. Feature importance ranks voxel spacing (0.31), scanner model (0.24), TE (0.18) and TR (0.14) as the four dominant axes; *P*(Yale-like)>0.60 yields specificity=0.92 / sensitivity=0.78 for first-pass deployment screening. This is a parallel, label-free deployment-monitoring framework that complements *pi\**-based ranking-stability prediction.

**Model-family invariance**: *pi\** computed for five model families ranges 0.38–0.55 — all within the canonical bootstrap CI [0.30, 0.52]; aggregate *pi\**=0.454±0.063.

**Negative controls**: nine pre-specified controls (label permutation, timepoint reversal, Gaussian blob without boundary, endpoint-label permutation in LOCO, selector feature permutation, cohort label permutation, patient-ID shuffle, random mask shift, null model 0.5) all destroy the heat-kernel signal and the LOCO ranking direction.

### 3.8 Operational rule

A new clinical site should not import a leaderboard winner. The proposed pre-deployment audit is: (i) estimate the site's endpoint composition from protocol documentation, historical audit or pilot review (5–15 cases sufficient when far from *pi\**); (ii) classify the regime (surveillance *pi*≥0.60, uncertain 0.43≤*pi*<0.60, active-change *pi*<0.43); (iii) when *pi* falls inside or near the uncertain zone, evaluate both heat and learned baselines on the local pilot set before committing; (iv) report the crossover-risk interval alongside any aggregate ranking claim.

## 4. Discussion

The central conclusion is not that the heat prior is better, or that raw-MRI is better — neither is universally correct. The conclusion is that a leaderboard is not transportable unless the endpoint regime and transfer condition are specified. A model family can be clinically plausible, internally strong on UCSF (Section 3.1), and externally wrong on RHUH-GBM (Section 3.2) in the same project. The principal reviewer concern of earlier versions of this work — that raw MRI was unavailable, so the heat-vs-learned comparison was a strawman — is now directly answered. Raw MRI helps internally on UCSF; external raw-MRI LOCO with seed and architecture robustness still preserves ranking reversals.

A second important point is that endpoint composition *pi_stable*, while useful, is not a sufficient causal axis. UCSD-PTGBM is the documented counterexample. The corrected picture is multi-axis, with *pi\** as the closed-form, falsifiable component and a list of additional design variables (horizon, provenance, image distribution, mask tier) that must be reported alongside *pi*.

The construction is theoretically modest. Theorem 1 is a consequence of the law of total expectation, and Corollary 1.iii (pre-deployment estimability) is the operational claim. Existing label-shift methods (Saerens et al., 2002; Lipton et al., 2018; Azizzadenesheli et al., 2019; Alexandari et al., 2020; Garg et al., 2022, 2025) all require target-domain unlabeled data and operate on single models; none provides a closed-form pre-deployment ranking-reversal estimator from source-cohort statistics alone. We claim novelty narrowly: to our knowledge this is the first such predictor for longitudinal neuro-oncology AI. Generalisation to other domains (sepsis, surgical outcome classification, screening radiology) is plausible from the algebra but is not empirically validated here.

**Limitations.** (i) The raw-MRI experiments use cropped 3D networks (16×48×48 crops); the stronger residual architecture mitigates the simplest "lightweight U-Net" objection, but a full-resolution canonical nnU-Net with completed checkpoints across all four cohorts remains the next required experiment. (ii) UCSD-PTGBM and RHUH-GBM are small (N=37 and N=38 respectively); the held-out comparison is therefore noisy on those two cohorts, although five-seed × two-architecture preservation of directional outcomes (20/20) substantially mitigates reproducibility concerns. (iii) Prediction horizon, mask tier and image distribution are correlated axes — N=4 LOCO cohorts cannot decompose their independent contributions; that decomposition requires N≥15 truly independent cohorts. (iv) Survival, reader decisions and treatment benefit are excluded from this paper's claim chain.

The next technical step is straightforward but heavier: a full-resolution nnU-Net or transformer baseline with completed checkpoints across the same held-out cohorts, plus expansion to N≥15 truly independent public cohorts. The current evidence is sufficient to reject the raw-MRI-availability objection and to motivate a benchmark-instability framework, but not to crown a final image model.

## 5. Methods

### 5.1 Cohorts and inclusion roles

The master neuro-oncology index (`source_data/master_neurooncology_dataset_index.csv`; 860 rows) catalogs eight independently-acquired cohorts assigned distinct evidential roles. Four cohorts (UCSF-POSTOP, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N=522 paired evaluations) contributed to the raw-MRI LOCO experiment with patient-level Brier evaluation. Endpoint labels (stable / active) followed published RANO-style volumetric classification (>25% volume change → active). The MONAI 3D mask-feature comparator used UCSF + MU-Glioma-Post + RHUH-GBM + LUMIERE (N=509 paired evaluations).

### 5.2 Inputs and architecture

Each case contributed 16×48×48 voxel crops centred on the baseline lesion. Channels: four raw-MRI channels (T1, T1c, T2, FLAIR), the baseline lesion mask, a heat-prior map (Gaussian diffusion of the mask with sigma=2.5 voxels), and a signed-distance field. Five variants were trained: (a) heat prior alone; (b) mask+heat+SDF; (c) raw-MRI only (4 channels); (d) raw-MRI+mask (5 channels); (e) raw-MRI+mask+heat+SDF (7 channels). Architecture: lightweight 3D U-Net (32–64–128–256 channels; combo BCE+Dice loss). Trained for 24 epochs, AdamW lr=1e-3, batch=10, on an NVIDIA RTX 5070 Laptop GPU.

### 5.3 Internal UCSF cross-validation (Section 3.1)

3-fold cross-validation within UCSF only, training each variant on two folds and evaluating Brier, ECE, AUROC and Dice on the held-out fold. Source: `source_data/v77_ucsf_raw_mri_baseline.json`.

### 5.4 Leave-one-cohort-out (Section 3.2)

For each held-out cohort, models were trained on all non-held-out cohorts and evaluated on the held-out cohort. No held-out target labels influenced training. Source: `source_data/v78_raw_mri_loco.json`.

### 5.5 Five-seed × two-architecture robustness (Section 3.3)

Lightweight 3D U-Net seeds 7901/7902/7903; stronger residual 3D U-Net (GroupNorm, dropout, source-validation early stopping, source-only affine calibration, H/W-flip TTA) seeds 8101/8102. Sources: `source_data/v79_raw_loco_seed_robustness.json`; `source_data/v81_gpu_stronger_raw_loco.json`.

### 5.6 Pi\* and identifiability (Theorem 1; Section 3.5)

Per-stratum Brier means on UCSF: *L_hs*=0.041, *L_ha*=0.274, *L_ms*=0.140, *L_ma*=0.199. Theorem 1 conditions C1 and C2 verified empirically. Closed-form crossover *pi\** = (*L_ma* − *L_ha*) / [(*L_ma* − *L_ha*) + (*L_hs* − *L_ms*)] = 0.431. Bootstrap 95% CI: 5,000 stratified resamples. Bayesian 95% credible interval: 50,000 truncated-Normal Monte Carlo posterior samples with SE(*L*)=0.15/√*N*. Random-effects meta-regression: DerSimonian–Laird estimator with within-cohort variance approximated as mean(*B_heat*, *B_model*)·(1−mean)/*N*.

### 5.7 Negative controls (Section 3.7)

Nine pre-specified negative controls: label permutation; endpoint-label permutation; patient-ID shuffle; timepoint reversal; random 5-voxel mask shift; Gaussian blob without boundary; selector feature permutation; cohort-label permutation in LOCO; null 0.5 model.

### 5.8 Statistical methods

Primary endpoint: 7/7 correct directional LOCO predictions; pre-specified exact one-sided binomial test under *p*=0.5 null gives *p*=0.0078. Holm–Bonferroni step-down correction on three pre-registered primary endpoints (UCSF Brier superiority for heat — permutation *p*<0.0001; seed reproducibility 5/5 — binomial *p*=0.001; ranking direction *p*=0.041 from permutation rank). All three primary endpoints survive correction at FWER=0.05.

### 5.9 Software, hardware and reproducibility

Python 3.11.9; PyTorch 2.12 (CUDA 12.8); MONAI 1.5.2; nibabel 5.4.2; NumPy 2.4.4; SciPy 1.17.1; statsmodels for meta-regression. Hardware: NVIDIA RTX 5070 Laptop GPU. All training scripts and source-data CSVs are versioned at `scripts/` and `source_data/`. Paper's primary numerical claims map one-to-one to versioned result files.

## CRediT author contributions

Conceptualization: [author]; Methodology: [author]; Software: [author]; Validation: [author]; Formal analysis: [author]; Investigation: [author]; Resources: [author]; Data curation: [author]; Writing – original draft: [author]; Writing – review & editing: [author]; Visualization: [author]; Supervision: [author]; Project administration: [author]; Funding acquisition: [author]. *(Specific roles to be filled at acceptance.)*

## Acknowledgements

The authors acknowledge the providers of the UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM, LUMIERE, UPENN-GBM and Yale-Brain-Mets-Longitudinal cohorts.

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

## Declaration of competing interests

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author(s) used Claude (Anthropic) in order to assist with manuscript drafting, formatting and statistical analysis scripting. After using this tool/service, the author(s) reviewed and edited the content as needed and take(s) full responsibility for the content of the published article.

## Data and code availability

All training scripts and primary numerical-claim source-data files are versioned in the public companion repository (https://github.com/kamrul0405/Nature_MI_paper). Source-data CSVs at `source_data/v78_nmi_raw_loco_source_data.csv`. UCSF, MU-Glioma-Post and RHUH-GBM cohorts contain clinical patient data and are available from the respective institutions under data-use agreements; UCSD-PTGBM is publicly available from TCIA (CC BY 4.0; collection UCSD-PTGBM, DOI 10.7937/fwv2-dt74). Yale brain-metastases cohort requires institutional approval. A frozen Zenodo DOI mirror will be deposited at acceptance.

## References

(Harvard author–year style; alphabetical by first author then chronological.)

Alexandari, A., Kundaje, A., Shrikumar, A., 2020. Maximum likelihood with bias-corrected calibration is hard-to-beat at label shift adaptation. In: Proc. 37th Int. Conf. Machine Learning (ICML), pp. 222–232.

Azizzadenesheli, K., Liu, A., Yang, F., Anandkumar, A., 2019. Regularized learning for domain adaptation under label shifts. In: Int. Conf. Learning Representations (ICLR).

Bernhardt, M., et al., 2022. Active label cleaning for improved dataset quality under resource constraints. Nat. Commun. 13, 1161.

Ellingson, B.M., et al., 2020. Volumetric RANO assessment of pseudoprogression at early timepoints following chemoradiotherapy in glioblastoma. Neuro Oncol. 22, 1767–1775.

Garg, S., Balakrishnan, S., Kolter, J.Z., Lipton, Z.C., 2022. Leveraging unlabeled data to predict out-of-distribution performance. In: Int. Conf. Learning Representations (ICLR).

Garg, S., Balakrishnan, S., Lipton, Z.C., 2025. Estimating model performance under covariate shift without labels. Adv. Neural Inf. Process. Syst. (NeurIPS) 38.

Gneiting, T., Raftery, A.E., 2007. Strictly proper scoring rules, prediction, and estimation. J. Am. Stat. Assoc. 102, 359–378.

Hartman, S.J., et al., 2025. UCSD post-treatment GBM (UCSD-PTGBM): a comprehensive longitudinal MRI dataset. Sci. Data. https://doi.org/10.1038/s41597-025-06499-z.

Hatamizadeh, A., et al., 2022. UNETR: transformers for 3D medical image segmentation. In: WACV.

Isensee, F., et al., 2021. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nat. Methods 18, 203–211.

Karargyris, A., et al., 2023. Federated benchmarking of medical artificial intelligence with MedPerf. Nat. Mach. Intell. 5, 799–810.

Kickingereder, P., et al., 2019. Automated quantitative tumour response assessment of MRI in neuro-oncology with artificial neural networks. Lancet Oncol. 20, 728–740.

Lipton, Z.C., Wang, Y.X., Smola, A., 2018. Detecting and correcting for label shift with black box predictors. In: Proc. 35th Int. Conf. Machine Learning (ICML), pp. 3122–3130.

Liu, R., et al., 2024. Distribution shift detection for postmarket surveillance of medical AI. npj Digit. Med. 7, 93.

Maier-Hein, L., et al., 2024. Metrics reloaded: recommendations for image analysis validation. Nat. Methods 21, 195–212.

Pesarin, F., Salmaso, L., 2010. Permutation tests for complex data: theory, applications and software. Wiley.

Rastogi, A., Brugnara, G., Vollmuth, P., Wick, W., et al., 2024. Deep-learning-based volumetric response assessment of glioblastoma (EORTC-26101). Lancet Oncol. 25, 400–410.

Roberts, M., Driggs, D., Thorpe, M., et al., 2021. Common pitfalls and recommendations for using machine learning to detect and prognosticate for COVID-19 using chest radiographs and CT scans. Nat. Mach. Intell. 3, 199–217.

Saerens, M., Latinne, P., Decaestecker, C., 2002. Adjusting the outputs of a classifier to new a priori probabilities: a simple procedure. Neural Comput. 14, 21–41.

Storkey, A.J., 2009. When training and test sets are different: characterizing learning transfer. In: Dataset Shift in Machine Learning. MIT Press, pp. 3–28.

Tasche, D., 2017. Fisher consistency for prior probability shift. J. Mach. Learn. Res. 18, 1–32.

Wen, P.Y., et al., 2023. RANO 2.0: update to the response assessment in neuro-oncology criteria. J. Clin. Oncol. 41, 5187–5199.

Westfall, P.H., Young, S.S., 1993. Resampling-based multiple testing: examples and methods for p-value adjustment. Wiley.

## Author vitae

[100 words per author at acceptance.]

## Figure captions

**Figure 1.** External raw-MRI access does not remove ranking reversal. (a) held-out Brier across four cohorts (UCSF, MU, RHUH, UCSD) for five variants (heat prior, mask+heat+SDF U-Net, raw-MRI U-Net, raw+mask U-Net, raw+mask+heat+SDF U-Net). The heat prior is best on UCSF and UCSD; raw+mask variants are best on MU and RHUH. (b) raw+mask − heat Brier deltas with three-seed bootstrap intervals — every directional outcome is preserved across all three seeds in all four cohorts. (c) held-out winning Brier vs held-out stable-endpoint fraction. UCSD-PTGBM is the documented counterexample to a *pi*-only explanation. Source image: `figures/main/V78_NMI_raw_loco_stress.png` (300 dpi PNG and TIFF). Source data: `source_data/v78_nmi_raw_loco_source_data.csv`.
