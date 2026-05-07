# v87 submission-readiness checklist - Medical Image Analysis

Target: Medical Image Analysis, original research article.

## Package status

- Manuscript source: `manuscript/Manuscript_for_MedicalImageAnalysis.md`
- Submission PDF: `manuscript/Manuscript_for_MedicalImageAnalysis.pdf`
- Claim audit: `source_data/v87_transformer_comparability_audit.json`
- Main added figure: `figures/main/V87_MedIA_transformer_comparability.png`
- 300-DPI print figure: `figures/main/V87_MedIA_transformer_comparability.tif`
- Build script: `scripts/build_v87_media_pdf.py`
- Validation report: `C:/Users/kamru/Downloads/Nature_project/05_results/v87_q1_validation.json`

## Passed checks

- PDF build succeeds from Markdown.
- PDF page count: 29.
- Main references: 56.
- Main figures: 5.
- Extended Data figures: 16.
- Tables: 3.
- Source images referenced in captions: 24.
- Missing caption/source-data references: 0.
- DPI issues among referenced figure files: 0.
- Removed hard "7/7 prediction" claim.
- Removed literature-derived full-resolution nnU-Net support claim.
- Corrected padded transformer comparison to denominator-matched heat baseline.
- Retained UCSD-PTGBM as a declared counterexample to a pi-only rule.

## Remaining reviewer risks

- Full-resolution nnU-Net remains unresolved and is explicitly labelled as future external validation.
- Native UNETR is three-seed, but padded UNETR/SwinUNETR are single-seed sanity checks.
- The four raw-MRI LOCO cohorts are strong for stress testing but not enough for a universal clinical generalisation claim.
- No prospective clinical utility or reader-study endpoint is claimed.

## Submission posture

This version is materially stronger than the earlier Nature-style draft because it no longer overclaims the crossover algebra and it treats transformer evidence honestly. It is a credible Q1 medical-imaging manuscript candidate, with the key residual risk being whether reviewers demand full-resolution nnU-Net before acceptance.

