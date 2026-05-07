# v90 Medical Image Analysis submission readiness

Generated: 2026-05-07

## Manuscript hardening

- Reduced highlights to 5 bullets, all <=85 characters.
- Added a reviewer-facing claim map linking each headline claim to evidence and boundary conditions.
- Reframed pi* as a benchmark-transfer warning statistic, not a clinical deployment rule.
- Reworded the nnU-Net section to state exactly what was tested: official nnU-Net v2 cropped-cache, not anatomical full-volume nnU-Net.
- Removed duplicate Figure 6 caption.

## Additional checks run

- GPU heat-Brier recheck on RTX 5070 Laptop GPU: `source_data/v90_gpu_heat_brier_recheck.json`.
- CPU rerun of conformal coverage, negative controls and empirical-Bernstein audit via `scripts/v84_e3_e4_e5_only.py`.
- Synced v84 audit outputs into `source_data/`.

## Outputs

- Markdown: `manuscript/Manuscript_v90_for_MedicalImageAnalysis.md`
- PDF: `manuscript/Manuscript_v90_for_MedicalImageAnalysis.pdf`
- Audit JSON: `submission_readiness_v90.json`

## Audit result

- PDF rebuilt successfully: 30 pages.
- Missing source images: 0.
- Missing source data files: 0.
- Highlight count/length: pass.
- Main Figure 6 captions: 1 after correction.
- Main residual limitation: evidence remains crop-scale for most learned baselines and cropped-cache for nnU-Net; no anatomical full-volume nnU-Net claim is made.
