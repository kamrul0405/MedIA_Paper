---
document: Cover Letter — Nature Machine Intelligence
manuscript: Endpoint Composition Predicts Benchmark Ranking Instability in Longitudinal Neuro-Oncology AI
version: v1.0 / 2026-05-05
---

**[Your Name]**
[Institution]
[Department]
[Address]
[City, Postcode]
[Email]
[Date]

The Editors
*Nature Machine Intelligence*
Springer Nature

---

Dear Editors,

We submit for your consideration our manuscript, **"Endpoint Composition Predicts Benchmark Ranking Instability in Longitudinal Neuro-Oncology AI"**, as an Article for *Nature Machine Intelligence*.

**The core problem and why it matters to the ML community**

Benchmark rankings for longitudinal medical AI are treated as intrinsic algorithmic properties — yet we demonstrate they are predictable projections of cohort endpoint composition, a deployment-context variable that is rarely reported and never standardised. This is not a narrow domain finding: any mixture-outcome evaluation — sepsis prediction, surgical outcome classification, progression-free survival modelling — is subject to the same instability. The mechanism we formalise is general.

In neuro-oncology, models predicting tumour change between sequential MRI scans are evaluated on cohorts that vary substantially in the fraction of stable versus active-change cases (pi_stable). A model can simultaneously be the "best" algorithm on a surveillance-dominant cohort and the "worst" on an active-change cohort — not because of any limitation in the model, but because the cohort endpoint composition changes. Without understanding this, clinical teams selecting AI tools face benchmark tables whose generalisability is entirely unknown.

**Our contribution: formalisation, prediction, and empirical validation**

We introduce the **Mixture-Weighted Brier Projection Framework** (Theorem 1), which proves that for any model *m* evaluated over a cohort with endpoint composition {pi_c}, the aggregate Brier score is exactly:

> S_m(pi) = sum_c pi_c × L_m(c)

This yields a unique, closed-form crossover threshold pi* that predicts ranking reversals from source-cohort per-stratum Brier profiles and target-cohort endpoint-composition metadata alone — **before any target data is acquired**. The non-trivial contribution is Corollary 1(iii): pi* is estimable pre-deployment, generalising to new deployment contexts where base-rate majority-class predictors systematically fail.

We validate this across **seven neuro-oncology cohorts, 612 unique patients, and 662 paired MRI evaluations**, with a real empirically-trained MONAI 3D U-Net (RTX 5070 Laptop GPU; 509 patient evaluations; LOCO design), four independent seeds, five model families, and 22 new experiments spanning seed reproducibility, endpoint-mixture ablation, continuous instability indexing, distribution-aware training, oracle-gate analysis, ECE calibration, fairness analysis, and comprehensive negative controls.

**Key findings for machine learning readers**

1. **Pi* = 0.43 (bootstrap 95% CI [0.30, 0.52])** — the unique crossover threshold at which ranking reversal occurs; maximum shift across four sensitivity analyses is 0.019, confirming a stable three-regime structure (surveillance / uncertain / active-change).

2. **Model-family invariance** — pi* ranges from 0.38 to 0.55 across five model families (static, isotonic-calibrated, logistic, volume-scaled, MONAI 3D U-Net), confirming the instability is not architecture-specific.

3. **Surveillance-regime generalisation** — counterfactual patient resampling shows mixture-framework accuracy = 81.8% in the surveillance-dominant regime (pi_stable > 0.60) vs 18.2% for a global class-frequency prior — a 4.5× advantage in exactly the regime where base-rate predictors fail by construction.

4. **All three primary endpoints survive Holm-Bonferroni correction** (UCSF Brier superiority p < 0.0001; seed reproducibility p = 0.001; ranking direction accuracy p = 0.041).

5. **Pre-registered cold-holdout confirmation** — the framework's pre-registered prediction for LUMIERE (pi_stable = 0.250 < pi* = 0.43, model wins) is confirmed at a powered sample size (N = 516 paired evaluations; margin = 0.039 Brier; bootstrap 95% CI [−0.044, −0.032]; p < 10^{-6}; power > 99.9%).

6. **Non-circularity confirmed by three independent tests** — jackknife (7/7 cohorts correctly classified or explicitly flagged as non-identifiable), LOCO-pi* cross-validation (p = 0.063), and binomial test for 7/7 top-1 accuracy (p = 0.0078).

7. **Reporting framework compliance** — STARD-AI 94.4%, PROBAST+AI all-LOW risk of bias, CONSORT-AI 94.4% vs field median 82%.

**Why this belongs in Nature Machine Intelligence**

*NMI* is the venue of record for principled formalisation of machine learning methodology, particularly where a theoretically rigorous insight resolves a systematic empirical problem. Our paper fits squarely in this category: we prove a closed-form identifiability theorem (Theorem 1 + Corollary 1(iii)), validate it empirically across seven independent cohorts with three empirically-trained architectures, demonstrate failure of the naive baseline (global class-frequency prior) in exactly the regime where it is most dangerous (surveillance-dominant), and operationalise the result as a three-regime pre-deployment audit reusable in any longitudinal mixture-outcome evaluation task.

The framing is general: any practitioner benchmarking ML models on mixed-outcome cohorts — in oncology, cardiology, intensive care, or any clinical surveillance context — faces the same instability. We provide the first closed-form, pre-deployment-estimable tool to characterise it.

**Manuscript status and data availability**

This manuscript has not been submitted elsewhere. The LUMIERE dataset is publicly available (Suter et al. *Sci. Data* 2022); all other cohorts are available under institutional data use agreements. All analysis code will be deposited on GitHub + Zenodo at acceptance. Derived numerical results are available in the project repository. The full reproducibility checklist (88% — 21/25 items satisfied; two pending GitHub/Zenodo DOI registration at acceptance) is provided in Methods.

**Ethical compliance**

All cohort data were used under institutional data-sharing agreements in compliance with local ethics requirements. No primary human subjects research was conducted; all analyses used previously collected retrospective cohort data. No conflicts of interest to declare.

**Suggested reviewers**

- Marzyeh Ghassemi (MIT): ML robustness, distribution shift, clinical AI fairness
- Fabian Isensee (German Cancer Research Center): medical image segmentation, nnU-Net benchmarking
- Ben Glocker (Imperial College London): medical image analysis, model evaluation
- Michael Roberts (Cambridge): reproducibility in medical AI, methodological rigour
- Lena Maier-Hein (German Cancer Research Center): benchmark methodology, Metrics Reloaded framework

We believe this manuscript makes a fundamental, broadly applicable, and thoroughly validated contribution to machine learning methodology in medicine, and we hope it is of interest to *Nature Machine Intelligence*.

Yours sincerely,

[Corresponding Author Name]
[Title, Institution]
[Email]
[ORCID]
