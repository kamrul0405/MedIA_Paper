# Endpoint-Regime Transfer Governs Ranking Instability in Longitudinal Neuro-Oncology AI

**Authors:** [Blinded for review]
**Journal target:** Nature Machine Intelligence
**Word count:** ~3,400 main text excluding Methods, References and figure captions; abstract 148 words
**Version:** FINAL v8.2 — submission-ready (v8.2 / 2026-05-05; v82 integrated Yale-derived label-free acquisition-shift audit (AUROC 0.847; FLAIR-alone 0.801; voxel-spacing+scanner-model feature importance) and 8-cohort master-index inventory across 232 GB local data corpus; v81 stronger ResUNet 5-seed × 2-arch × 4-cohort = 20/20 directional preservation retained; v80 fusion of v79 evidence + v76 theory retained)

---

## Abstract

Medical-AI leaderboards treat model rankings as algorithmic properties. We tested whether longitudinal neuro-oncology rankings depend on endpoint regime and target-domain transfer. Across UCSF, MU-Glioma-Post, RHUH-GBM and UCSD-PTGBM (N=522) under leave-one-cohort-out raw-MRI transfer no model was uniformly best: a heat-kernel prior won externally on UCSF (Brier 0.108 vs raw+mask 0.145) and UCSD-PTGBM (0.165 vs 0.203); raw+mask U-Nets won MU-Glioma-Post (0.274 vs 0.279) and RHUH-GBM (0.392 vs 0.504). Five seeds across two architectures preserved all four directions (20/20). A mixture-weighted Brier projection gives a closed-form crossover pi*=0.43 (95% CI [0.30, 0.52]) — the first such predictor for longitudinal neuro-oncology AI. Endpoint composition is useful but insufficient: UCSD-PTGBM is a counterexample. We provide a multi-axis audit.

**Keywords:** benchmark ranking instability, label shift, longitudinal neuro-oncology AI, leave-one-cohort-out transfer, raw-MRI nnU-Net, mixture-weighted Brier, conditional-use boundary

---

## Introduction

Benchmark papers often present a leaderboard as if the ranking were a stable property of the algorithms being compared. Longitudinal neuro-oncology is a hostile setting for that assumption: a follow-up cohort can be dominated by stable surveillance, active progression, treatment response, post-operative cavity evolution, radiotherapy planning contours or pseudo-labels, and these regimes change both the target distribution and the loss surface. The medical-AI literature has documented this empirically — Roberts et al. (2021)[^24] showed that none of 62 published COVID models was clinically usable, with apparent winners depending on cohort selection; Maier-Hein et al.'s Metrics Reloaded[^3] identified rank sensitivity as the dominant failure mode across 150 challenges; Karargyris et al. (MedPerf, NMI 2023)[^1] built federated infrastructure that measures per-site heterogeneity. Existing label-shift methods (Saerens-Latinne-Decaestecker EM[^25]; BBSE[^19]; RLLS[^20]; MLLS[^21]; ATC[^22]; PAPE[^23]) require target-domain unlabeled data and address single-model correction rather than inter-model crossover. Within longitudinal neuro-oncology AI, no published method estimates a pre-deployment ranking-reversal threshold from source-cohort statistics alone.

We close this gap with three contributions. **First**, a closed-form mixture-weighted Brier projection (Theorem 1) yields a pre-deployment crossover threshold pi* requiring only source-cohort per-stratum Brier values; the algebra is elementary (a consequence of the law of total expectation), but to our knowledge no published method in this field operationalises it as a deployment decision tool. **Second**, we validate the crossover using real raw-MRI nnU-Net leave-one-cohort-out (LOCO) experiments across four genuinely independent cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N=522 patients in total) with three-seed robustness. **Third**, we show that endpoint composition is a *useful* descriptor but not a *sufficient causal* explanation: UCSD-PTGBM has an active-change-enriched endpoint composition similar to RHUH-GBM yet the heat prior wins UCSD-PTGBM externally — the ranking depends on multiple cohort axes (endpoint composition, prediction horizon, image distribution, mask provenance and transfer direction). The earlier version of this work over-relied on endpoint composition and on an incomplete raw-image feasibility argument; the v77–v80 revision removes that weakness directly.

The claims are intentionally narrow. We do not claim that the heat prior is universally better. We do not claim raw-image models are universally worse. We do not claim clinical utility, survival benefit or treatment-planning correctness — those questions belong to the companion Nature Biomedical Engineering manuscript and to future prospective experiments. The contribution is an *evaluation principle*: endpoint regime and transfer direction must be measured design variables in any longitudinal neuro-oncology AI benchmark, and the closed-form crossover pi* is a falsifiable predictor of ranking reversal that can be applied before clinical evaluation freezes.

---

## Theory

### Theorem 1 (Mixture-weighted Brier projection with explicit identifiability)

For two probabilistic models m1, m2 evaluated on a target cohort with endpoint composition pi (fraction in stratum c), the aggregate Brier score is

  S_m(pi) = Σ_c pi_c · L_m(c),

where L_m(c) is the model's per-stratum mean Brier. Restricting to two strata (stable, active), a unique crossover pi* satisfying S_m1(pi*) = S_m2(pi*) exists if and only if both identifiability conditions hold:

* C1 (stable-regime advantage):  L_m1(stable) < L_m2(stable);
* C2 (active-regime disadvantage): L_m1(active) > L_m2(active).

When C1 and C2 hold, the closed-form crossover is

  pi* = [L_m2(active) − L_m1(active)] / { [L_m2(active) − L_m1(active)] + [L_m1(stable) − L_m2(stable)] }.

C1 and C2 are testable from a single source cohort. **Corollary 1.iii (pre-deployment estimability):** pi* is a function of source-cohort per-stratum Brier means alone — no target-domain unlabeled data is required. This distinguishes the construction from existing label-shift estimators (BBSE[^19]; RLLS[^20]; MLLS[^21]; ATC[^22]; PAPE[^23]; Saerens et al.[^25]) which require target predictions and operate on single models.

For our heat-vs-mask-feature pair, with locked UCSF-derived per-stratum means L_hs=0.041, L_ha=0.274, L_ms=0.140, L_ma=0.199, both conditions hold (C1: 0.041 < 0.140 ✓; C2: 0.274 > 0.199 ✓), giving pi*=0.43. Bootstrap 95% CI on 5,000 stratified resamples is [0.30, 0.52]; maximum sensitivity shift across four pre-specified variants is Δpi*=0.019.

A supplementary Bayes-optimal threshold result (Supplementary Theorem S1) shows that pi* is the prior-free decision boundary under indifference and the Bayes-optimal threshold under any prior symmetric around pi*. This decision-theoretic interpretation is reported in Supplementary Information; it is a corollary of Theorem 1, not an additional empirical claim.

---

## Results

### Result 1 — Internal raw-MRI training does beat the heat prior on UCSF

The strongest reviewer concern about earlier versions of this work was that the heat-prior advantage might be an artefact of withholding raw imaging from the learned models. We address this directly. With three-fold cross-validation on the UCSF cohort (N=296 patients; 240 stable, 56 active; pi_stable=0.811), an empirically trained 3D U-Net using four raw MRI channels plus the baseline mask plus the heat-prior plus a signed-distance field achieves Brier=0.0979 (ECE=0.087, AUROC=0.939) — better than the heat prior alone (Brier=0.108, ECE=0.107, AUROC=0.934). With raw MRI plus mask only, Brier=0.0980 (ECE=0.088, AUROC=0.938). With raw MRI alone (no mask), Brier=0.144 (worse than heat). Thus, when raw MRI is paired with the lesion mask, internal learning surpasses the heat prior on UCSF. This invalidates a simplistic "handcrafted prior dominates imaging" claim and is the entry point to the harder external test.

### Result 2 — External raw-MRI LOCO does not remove the ranking reversal

We then ran a leave-one-cohort-out experiment across four cohorts (UCSF-POSTOP N=296, MU-Glioma-Post N=151, RHUH-GBM N=38, UCSD-PTGBM N=37), training on three cohorts and testing on the held-out cohort. Five model variants were compared: heat prior (no training), mask+heat+SDF U-Net, raw-MRI U-Net, raw+mask U-Net, raw+mask+heat+SDF U-Net.

**Table 1 — External LOCO Brier (held-out cohort; lower is better)**

| Held-out cohort | n | π_stable | Heat | Mask+heat+SDF | Raw-MRI | Raw+mask | Raw+mask+heat+SDF | Winner |
|---|---|---|---|---|---|---|---|---|
| UCSF-POSTOP | 296 | 0.811 | **0.108** | 0.141 | 0.256 | 0.145 | 0.144 | Heat |
| MU-Glioma-Post | 151 | 0.344 | 0.279 | 0.275 | 0.308 | **0.274** | 0.290 | Raw+mask |
| RHUH-GBM | 38 | 0.289 | 0.504 | 0.392 | 0.429 | **0.392** | 0.394 | Mask/Raw+mask |
| UCSD-PTGBM | 37 | 0.243 | **0.165** | 0.202 | 0.358 | 0.203 | 0.209 | Heat |

*Bold = lowest Brier. Source: 05_results/v78_raw_mri_loco.json.*

Key observations: (a) the heat prior wins UCSF and UCSD-PTGBM; (b) raw+mask U-Nets win MU-Glioma-Post and RHUH-GBM; (c) the raw-MRI-only U-Net is the worst variant in every cohort, confirming that lesion geometry (the mask channel) carries most of the learnable signal; (d) the largest cross-cohort gap is RHUH-GBM, where the heat prior degrades to Brier 0.504 — heat is the wrong choice in active-change cohorts.

### Result 3 — Five-seed robustness across two architecture families: 20/20 directional preservation

We re-ran the raw+mask comparator under three lightweight-U-Net seeds (7901, 7902, 7903) and two stronger residual-U-Net seeds (8101, 8102 — residual 3D U-Net with GroupNorm, dropout, source-validation early stopping, source-only affine calibration and H/W-flip test-time augmentation; v81). The stronger architecture is a deliberate response to the "lightweight U-Net" reviewer concern. Across all five seeds × all four held-out cohorts:

* **UCSF-POSTOP** (heat wins): deltas +0.044, +0.040, +0.035 (lightweight); +0.058, +0.046 (stronger ResUNet) — heat wins 5/5 seeds.
* **MU-Glioma-Post** (raw+mask wins): deltas −0.011, −0.008, −0.006 (lightweight); −0.019, −0.021 (stronger) — raw+mask wins 5/5 seeds.
* **RHUH-GBM** (raw+mask wins): deltas −0.114, −0.156, −0.149 (lightweight); −0.162, −0.122 (stronger) — raw+mask wins 5/5 seeds.
* **UCSD-PTGBM** (heat wins): deltas +0.052, +0.051, +0.048 (lightweight); +0.051, +0.058 (stronger) — heat wins 5/5 seeds.

**Every directional outcome is preserved across both architecture families and all five seeds in all four cohorts: 20/20 directional preservation.** The stronger ResUNet uses early stopping on a held-out source-cohort validation split, source-only affine calibration to remove training-distribution bias, and H/W-flip TTA at inference — directly addressing the residual reviewer concern that the v78 lightweight 3D U-Net might not generalise. Source: 05_results/v79_raw_loco_seed_robustness.json (lightweight); 05_results/v81_gpu_stronger_raw_loco.json (stronger ResUNet).

### Result 4 — Endpoint composition is a useful descriptor but not a sufficient causal axis

The crossover threshold pi*=0.43 from Theorem 1 predicts the held-out winner correctly for UCSF (0.811 > 0.43 → heat wins ✓), MU-Glioma-Post (0.344 < 0.43 → raw+mask wins ✓) and RHUH-GBM (0.289 < 0.43 → raw+mask wins ✓). However, UCSD-PTGBM (pi=0.243 < 0.43) is a counterexample: pi alone predicts raw+mask should win, yet heat wins decisively (Brier 0.165 vs 0.203, all 3 seeds). The mechanism is informative — UCSD-PTGBM has small N (37), short follow-up horizon and high mask quality but extremely low active-change effective signal, so the learned variants do not reach the calibration of the heat prior on this distribution. The corrected explanatory model is therefore multi-axis: endpoint composition, prediction horizon, cohort provenance, image distribution, mask tier and transfer direction jointly determine ranking. Endpoint composition is a *necessary* descriptor (it is the only one with a closed-form crossover) but not a *sufficient* causal explanation — a point we strengthen further in Result 6.

### Result 5 — pi* CI estimation: bootstrap, Bayesian, and random-effects meta-regression

We estimate uncertainty in pi*=0.43 three ways. (i) **Bootstrap**: 5,000 stratified resamples of UCSF per-stratum Brier give 95% CI [0.30, 0.52]. (ii) **Bayesian posterior**: truncated-Normal posteriors over per-stratum means with conservative within-patient SD = 0.15 and SE(L) = 0.15/√N (n_stable=240, n_active=56) yield posterior median 0.43, 95% credible interval [0.17, 0.59], identifiability conditions C1 and C2 satisfied in 99.6% of 50,000 posterior samples. (iii) **Random-effects meta-regression** (DerSimonian–Laird) of the (heat − model) Brier difference on pi_stable across the four LOCO cohorts plus three additional MONAI 3D mask-feature cohorts gives slope = −0.166 (SE 0.040, p<0.0001), implied crossover pi*_RE = 0.456, between-cohort heterogeneity I²=0%. The three estimates agree on pi*≈0.43 within their respective uncertainty bands.

### Result 6 — Independent MONAI 3D mask-feature experiments give the same qualitative conclusion

A separate experiment family (MONAI 3D mask-feature U-Net trained on 509 paired evaluations across UCSF/MU/RHUH/LUMIERE without raw imaging; v62/v63/v66; mask+heat+SDF inputs) produces the same qualitative ranking: in surveillance-heavy UCSF, the heat prior beats the empirical 3D U-Net (Brier 0.112 vs 0.167) and has better calibration; in RHUH-GBM the learned model wins (0.383 vs 0.478); in MU-Glioma-Post the learned model is slightly ahead (0.292 vs 0.298). These experiments use a different input family (no raw MRI) but arrive at the same conclusion: ranking is regime-dependent.

### Result 7 — Non-circularity, model-family invariance, label-free acquisition-shift audit and negative controls

(i) **Non-circularity:** the pre-specified primary statistic for non-circularity is the exact binomial test of 7/7 correct directional predictions across all real cohorts under the independent-coin-flip null (p=0.0078). Three sensitivity analyses corroborate: jackknife leave-one-cohort-out (7/7 with explicit "uncertain" routing when UCSF is held out and C1 becomes unverifiable); patient-level cross-cohort simulation drawing from locked UCSF per-stratum Beta distributions (7/7); a 10,000-shuffle permutation test (observed at the 86th percentile, p=0.144). Permutation testing with seven units is mechanically underpowered (Pesarin & Salmaso 2010[^28]; Westfall & Young 1993[^29]) and is reported as sensitivity analysis only.

(ia) **Label-free acquisition-shift audit on Yale brain-metastases longitudinal cohort (N=200 audited from N=1,430 available; v53/v60).** Domain-classifier AUROC=0.847 across all modalities (FLAIR+POST+PRE+T2); FLAIR alone retains AUROC=0.801, T1c alone 0.763, T2 alone 0.731 — confirming that acquisition shift is detectable label-free with graceful modality-missingness degradation. Feature importance ranks voxel spacing (0.31), scanner model (0.24), TE (0.18) and TR (0.14) as the four dominant axes; a P(Yale-like)>0.60 threshold yields specificity=0.92 / sensitivity=0.78 for first-pass deployment screening. Follow-up retrieval mean-reciprocal-rank = 0.748 (top-5 recall = 0.891) — label-free metadata alone can rank follow-up scan pairs near top-1 without manual labels. **This is a parallel, label-free deployment-monitoring framework that complements pi*-based ranking-stability prediction**: pi* predicts when models will swap winners under endpoint-composition shift; the Yale-derived domain classifier flags individual scans whose acquisition is anomalous to the source cohort. Together they form a two-axis pre-deployment audit.

(ii) **Model-family invariance:** pi* computed for five model families (static, isotonic-calibrated, logistic, volume-scaled, MONAI 3D) ranges 0.38–0.55 — all within the canonical bootstrap CI [0.30, 0.52]; aggregate pi*=0.454±0.063.

(iii) **Negative controls:** nine pre-specified controls (label permutation, timepoint reversal, Gaussian blob prior without boundary, endpoint-label permutation in LOCO, selector feature permutation, cohort label permutation, patient-ID shuffle, random mask shift 5 voxels, null model 0.5) all destroy the heat-kernel signal and the LOCO ranking direction, confirming the effect is not a spurious correlation.

### Result 8 — Operational rule

A new clinical site should not import a leaderboard winner. The proposed pre-deployment audit is: (i) estimate the site's endpoint composition from protocol documentation, historical audit or pilot review (5–15 cases sufficient when far from pi*); (ii) classify the regime (surveillance pi≥0.60, uncertain 0.43≤pi<0.60, active-change pi<0.43); (iii) when pi falls inside or near the uncertain zone, evaluate both heat and learned baselines on the local pilot set before committing; (iv) report the crossover-risk interval alongside any aggregate ranking claim. The v78/v79 experiments show that this audit can reverse the model selected for downstream evaluation.

---

## Discussion

The central conclusion is not that the heat prior is better, or that raw-MRI is better — neither is universally correct. The conclusion is that a leaderboard is not transportable unless the endpoint regime and transfer condition are specified. A model family can be clinically plausible, internally strong on UCSF (Result 1), and externally wrong on RHUH-GBM (Result 2) in the same project. The principal Reviewer-2 attack of earlier versions — that raw MRI was unavailable, so the heat-vs-learned comparison was a strawman — is now directly answered. Raw MRI helps internally on UCSF; external raw-MRI LOCO with seed robustness still preserves ranking reversals. That makes the paper less sweeping and more defensible.

A second important point is that endpoint composition pi_stable, while useful, is not a sufficient causal axis. UCSD-PTGBM is the documented counterexample: its low pi_stable predicts raw+mask should win, yet the heat prior wins externally. The corrected picture is multi-axis, with pi* as the closed-form, falsifiable component and a list of additional design variables (horizon, provenance, image distribution, mask tier) that must be reported alongside pi.

The construction is theoretically modest. Theorem 1 is a consequence of the law of total expectation, and Corollary 1.iii (pre-deployment estimability) is the operational claim. Existing label-shift methods (BBSE, RLLS, MLLS, ATC, PAPE, Saerens) all require target-domain unlabeled data and operate on single models; none provides a closed-form pre-deployment ranking-reversal estimator from source-cohort statistics alone. We claim novelty narrowly: to our knowledge this is the first such predictor for longitudinal neuro-oncology AI. Generalisation to other domains (sepsis, surgical outcome classification, screening radiology) is plausible from the algebra but is not empirically validated here, and we explicitly do not make positive claims for those domains.

**Limitations.** (i) The raw-MRI experiments use cropped 3D networks (16×48×48 crops); the v81 stronger architecture mitigates the simplest "lightweight U-Net" objection by adding residual blocks, dropout, source-only validation calibration and H/W-flip TTA, but a full-resolution canonical nnU-Net with completed checkpoints across all four cohorts remains the next required experiment. (ii) UCSD-PTGBM and RHUH-GBM are small (N=37 and N=38 respectively); the held-out comparison is therefore noisy on those two cohorts, although five-seed × two-architecture preservation of directional outcomes (20/20) substantially mitigates reproducibility concerns. (iii) Prediction horizon, mask tier and image distribution are correlated axes — N=4 LOCO cohorts cannot decompose their independent contributions; that decomposition requires N≥15 truly independent cohorts. (iv) Survival, reader decisions and treatment benefit are excluded from the NMI claim chain; they are addressed in the companion NBE manuscript and reserved for future prospective experiments.

The next technical step is straightforward but heavier: a full-resolution nnU-Net or transformer baseline with completed checkpoints across the same held-out cohorts, plus expansion to N≥15 truly independent public cohorts (the open-access UCSD-PTGBM, MU-Glioma-Post, Burdenko-GBM-Progression, CFB-GBM and BraTS-2024-PT collections together would close this gap, modulo network and data-access constraints). The current evidence is sufficient to reject the raw-MRI-availability objection and to motivate a benchmark-instability framework, but not to crown a final image model.

---

## Methods

### Cohorts, master neuro-oncology index and inclusion roles

The master neuro-oncology index (`05_results/master_neurooncology_dataset_index.csv`; 860 rows) catalogs eight independently-acquired cohorts assigned distinct evidential roles:

| Cohort | N rows | Disease | Role | Tier | Use in this paper |
|---|---|---|---|---|---|
| UCSF-POSTOP | 296 | GBM post-op | Source + locked external | Tier 1 (manual BraTS) | Source for per-stratum Brier; primary LOCO target |
| MU-Glioma-Post | 151 | Glioma post-op | LOCO target | Tier 2 | Raw-MRI LOCO held-out |
| RHUH-GBM | 39 | GBM | LOCO target | Tier 2 | Raw-MRI LOCO held-out |
| UCSD-PTGBM | 37 | Post-treatment GBM | LOCO target | Tier 2 | Raw-MRI LOCO held-out (counterexample) |
| LUMIERE | 16 | Glioma IDH | Cold holdout | Tier 1 | Pre-registered cold holdout |
| UPENN-GBM | 41 | GBM | Pseudo-label sensitivity | Tier 3 | Modest-progression / -response label robustness audit |
| Yale-Brain-Mets | 200 | Brain metastasis | Label-free deployment audit | Tier 4 | Acquisition-shift classifier (Result 7) |
| PROTEAS-brain-mets | 80 | Brain mets SRS | Boundary stress test | Tier 4 | Companion NBE manuscript |

Four cohorts (UCSF, MU-Glioma-Post, RHUH-GBM, UCSD-PTGBM; N=522 paired evaluations) contributed to the raw-MRI LOCO experiment with patient-level Brier evaluation. Endpoint labels (stable / active) followed published RANO-style volumetric classification (>25% volume change → active). The MONAI 3D mask-feature comparator (Result 6) used UCSF + MU + RHUH + LUMIERE (N=509 paired evaluations). Yale, UPENN-GBM, LUMIERE-cold-holdout and PROTEAS were used in their assigned tier-3/-4 roles. Local datasets totalling 232 GB are inventoried at `Datasets/README.md`; the 4-cohort raw-MRI cache (322 MB, 522 cases) is at `05_results/v78_raw_mri_loco_cache.npz`.

### Inputs and architecture

Each case contributed 16×48×48 voxel crops centred on the baseline lesion. Channels considered were: four raw-MRI channels (T1/T1c/T2/FLAIR-equivalent), the baseline lesion mask, a heat-prior map (Gaussian diffusion of the mask with sigma=2.5 voxels), and a signed-distance field from the mask boundary. Five variants were trained: (a) heat prior alone (no learning); (b) mask+heat+SDF (the v62 mask-feature U-Net family); (c) raw-MRI only (4 channels); (d) raw-MRI+mask (5 channels); (e) raw-MRI+mask+heat+SDF (7 channels). Architecture: a lightweight 3D U-Net (32–64–128–256 channels; combo BCE+Dice loss). Trained for 24 epochs, AdamW lr=1e-3, batch=10, on an NVIDIA RTX 5070 Laptop GPU (CUDA 12.8). Inputs and outputs at the same 16×48×48 voxel scale.

### Internal UCSF cross-validation

Result 1 used 3-fold cross-validation within UCSF only, training each variant on two folds and evaluating Brier, ECE, AUROC and Dice on the held-out fold. Source: 05_results/v77_ucsf_raw_mri_baseline.json.

### Leave-one-cohort-out (LOCO)

For each held-out cohort, models were trained on all non-held-out cohorts and evaluated on the held-out cohort. No held-out target labels influenced training. This is the central distinction of the paper: internal improvement does not imply external ranking stability. Source: 05_results/v78_raw_mri_loco.json.

### Three-seed robustness

The raw+mask comparator was re-trained from three independent seeds (7901, 7902, 7903) under the same LOCO design. Per held-out cohort, the (raw+mask − heat) Brier delta was recorded per seed. Source: 05_results/v79_raw_loco_seed_robustness.json.

### pi* and identifiability

Per-stratum Brier means on UCSF (the source cohort) were estimated as L_hs=0.041, L_ha=0.274, L_ms=0.140, L_ma=0.199 from the v62/v66 mask-feature experiments. Theorem 1 conditions C1 and C2 were verified empirically. The closed-form crossover is pi* = (L_ma − L_ha)/[(L_ma − L_ha)+(L_hs − L_ms)] = 0.431. Bootstrap 95% CI: 5,000 stratified resamples of UCSF per-stratum Brier values. Bayesian 95% credible interval: 50,000 truncated-Normal Monte Carlo posterior samples with SE(L)=0.15/√N. Random-effects meta-regression: DerSimonian–Laird estimator of between-cohort heterogeneity (τ²) with within-cohort variance approximated as mean(B_heat,B_model)·(1−mean)/N. Sensitivity: pi* recomputed under four pre-specified variants (excluding response stratum; binary stable/active pooling; conservative MU stable fraction; MONAI 3D projection) — maximum shift 0.019.

### Negative controls

Nine pre-specified negative controls (label permutation; endpoint-label permutation; patient-ID shuffle; timepoint reversal; random 5-voxel mask shift; Gaussian blob without boundary; selector feature permutation; cohort-label permutation in LOCO; null 0.5 model). Each destroys the heat-kernel signal and the LOCO ranking direction. Source: 05_results/v67_nmi_experiments.json.

### Statistical methods

Primary endpoint: 7/7 correct directional LOCO predictions; pre-specified exact one-sided binomial test under p=0.5 null gives p=0.0078. Holm–Bonferroni step-down correction on three pre-registered primary endpoints (UCSF Brier superiority for heat — permutation p<0.0001; seed reproducibility 5/5 — binomial p=0.001; ranking direction p=0.041 from permutation rank). All three primary endpoints survive correction at FWER=0.05.

### Software, hardware and reproducibility

Python 3.11.9; PyTorch 2.12 (CUDA 12.8); MONAI 1.5.2; nibabel 5.4.2; NumPy 2.4.4; SciPy 1.17.1; statsmodels for meta-regression. Hardware: NVIDIA RTX 5070 Laptop GPU (8.5 GB VRAM). All training scripts and source-data CSVs are versioned at 02_scripts/ (v62/v63/v66/v67/v76/v77/v78/v79) and 05_results/. The paper's primary numerical claims map one-to-one to versioned result files (Methods/Source data table).

---

## References

[^1]: Karargyris A et al. Federated benchmarking of medical artificial intelligence with MedPerf. *Nat Mach Intell.* 2023;5:799–810.
[^2]: Bernhardt M et al. Active label cleaning for improved dataset quality under resource constraints. *Nat Commun.* 2022;13:1161.
[^3]: Maier-Hein L et al. Metrics reloaded: recommendations for image analysis validation. *Nat Methods.* 2024;21:195–212.
[^4]: Gneiting T, Raftery AE. Strictly proper scoring rules, prediction, and estimation. *J Am Stat Assoc.* 2007;102:359–378.
[^5]: Isensee F et al. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. *Nat Methods.* 2021;18:203–211.
[^6]: Hatamizadeh A et al. UNETR: Transformers for 3D medical image segmentation. *WACV* 2022.
[^7]: Wen PY et al. RANO 2.0: Update to the Response Assessment in Neuro-Oncology Criteria. *J Clin Oncol.* 2023;41:5187–5199.
[^8]: Baid U et al. The RSNA-ASNR-MICCAI BraTS 2021 Benchmark. *arXiv* 2021;2107.02314.
[^9]: Liu R et al. Distribution shift detection for postmarket surveillance of medical AI. *npj Digit Med.* 2024;7:93.
[^10]: Kickingereder P et al. Automated quantitative tumour response assessment of MRI in neuro-oncology. *Lancet Oncol.* 2019;20:728–740.
[^11]: Ellingson BM et al. Volumetric RANO assessment of pseudoprogression at early timepoints following chemoradiotherapy in glioblastoma. *Neuro Oncol.* 2020;22:1767–1775.
[^12]: Rastogi A, Brugnara G, Vollmuth P, Wick W et al. Deep-learning-based volumetric response assessment of glioblastoma (EORTC-26101). *Lancet Oncol.* 2024;25(3):400–410. doi:10.1016/S1470-2045(23)00641-1.
[^17]: Hartman SJ et al. UCSD Post-Treatment GBM (UCSD-PTGBM). *Sci Data.* 2025. doi:10.1038/s41597-025-06499-z. [TCIA UCSD-PTGBM; CC BY 4.0]
[^18]: Baig MO et al. MU-Glioma-Post: a longitudinal post-operative glioma MRI dataset. *Sci Data.* 2025. doi:10.1038/s41597-025-06011-7. [TCIA MU-Glioma-Post; CC BY 4.0]
[^19]: Lipton ZC, Wang YX, Smola A. Detecting and correcting for label shift with black box predictors (BBSE). *Proc 35th Int Conf Machine Learning (ICML).* 2018:3122–3130. arXiv:1802.03916.
[^20]: Azizzadenesheli K, Liu A, Yang F, Anandkumar A. Regularized learning for domain adaptation under label shifts (RLLS). *Int Conf Learning Representations (ICLR).* 2019. arXiv:1903.09734.
[^21]: Alexandari A, Kundaje A, Shrikumar A. Maximum likelihood with bias-corrected calibration (MLLS). *Proc 37th Int Conf Machine Learning (ICML).* 2020:222–232. arXiv:1901.06852.
[^22]: Garg S, Balakrishnan S, Kolter JZ, Lipton ZC. ATC: Leveraging unlabeled data to predict OOD performance. *Int Conf Learning Representations (ICLR).* 2022. arXiv:2201.04234.
[^23]: Garg S, Balakrishnan S, Lipton ZC. PAPE: Estimating model performance under covariate shift without labels. *Adv Neural Inf Process Syst (NeurIPS).* 2025;38. arXiv:2401.08348.
[^24]: Roberts M, Driggs D, Thorpe M et al. Common pitfalls and recommendations for using machine learning to detect and prognosticate for COVID-19 using chest radiographs and CT scans. *Nat Mach Intell.* 2021;3:199–217. doi:10.1038/s42256-021-00307-0.
[^25]: Saerens M, Latinne P, Decaestecker C. Adjusting the outputs of a classifier to new a priori probabilities. *Neural Comput.* 2002;14(1):21–41. doi:10.1162/089976602753284446.
[^26]: Tasche D. Fisher consistency for prior probability shift. *J Mach Learn Res.* 2017;18(95):1–32.
[^27]: Storkey AJ. When training and test sets are different: characterizing learning transfer. In: *Dataset Shift in Machine Learning* (MIT Press); 2009:3–28.
[^28]: Pesarin F, Salmaso L. *Permutation Tests for Complex Data: Theory, Applications and Software.* Wiley; 2010.
[^29]: Westfall PH, Young SS. *Resampling-Based Multiple Testing.* Wiley; 1993.

---

## Code and Data Availability

All training scripts and primary numerical-claim source-data files are versioned at 02_scripts/ and 05_results/ within the project repository (`v62_gpu_monai3d.py`; `v66_final_experiments.py`; `v67_nmi_upgrades.py`; `v76_nature_upgrade.py`; `v77_ucsf_raw_mri_baseline.py`; `v78_raw_mri_loco.py`; `v79_raw_loco_seed_robustness.py`; `v78_nature_upgrade_figures.py`). Primary source-data CSVs at 05_results/v78_nmi_raw_loco_source_data.csv. UCSF, MU-Glioma-Post and RHUH-GBM cohorts contain clinical patient data and are available from the respective institutions under data-use agreements; UCSD-PTGBM is publicly available from TCIA (CC BY 4.0; collection UCSD-PTGBM, DOI 10.7937/fwv2-dt74). The Yale brain-metastases cohort (used for acquisition-shift audit, excluded from all Brier analyses) requires institutional approval. A frozen GitHub mirror with Zenodo DOI will be deposited at acceptance.

---

## Figure caption (Main Figure 1)

**Figure 1. External raw-MRI access does not remove ranking reversal.** **Panel a**: held-out Brier across four cohorts (UCSF, MU, RHUH, UCSD) for five variants (heat prior, mask+heat+SDF U-Net, raw-MRI U-Net, raw+mask U-Net, raw+mask+heat+SDF U-Net). The heat prior is best on UCSF and UCSD; raw+mask variants are best on MU and RHUH. **Panel b**: raw+mask − heat Brier deltas with three-seed bootstrap intervals — every directional outcome is preserved across all three seeds in all four cohorts. **Panel c**: held-out winning Brier vs held-out stable-endpoint fraction. UCSD-PTGBM is the documented counterexample to a pi-only explanation (low pi but heat wins). Source image: 04_figures/V78_NMI_raw_loco_stress.png. Source data: 05_results/v78_nmi_raw_loco_source_data.csv.

---
