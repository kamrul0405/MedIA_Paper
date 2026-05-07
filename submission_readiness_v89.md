# v89 Medical Image Analysis submission readiness

Generated: 2026-05-07

## Added evidence

- Completed official nnU-Net v2 cropped-cache run: Dataset501/502/503, fold 0, 50 epochs, external prediction on UCSF, UCSD, PROTEAS and UPENN.
- Aligned probability scoring fixed the nnU-Net `.npz` versus NIfTI axis mismatch; every scored case used permutation `2,1,0`.
- The nnU-Net result is a negative control: heat prior beats the best nnU-Net variant on calibrated Brier in all four external cohorts.

## Outputs

- Manuscript MD: `manuscript/Manuscript_for_MedicalImageAnalysis.md`
- Manuscript PDF: `manuscript/Manuscript_for_MedicalImageAnalysis.pdf`
- Versioned copies: `manuscript/Manuscript_v89_for_MedicalImageAnalysis.md` and `.pdf`
- New figure: `figures/main/V88_MedIA_nnunet_negative_control.png` and `.tif`
- New source data: `source_data/v88_nnunet_negative_control_source_data.csv`, `source_data/v88_nnunet_cropcache_metrics_aligned.json`, `source_data/v88_nnunet_cropcache_summary.json`

## Validation

- PDF rebuilt successfully: 31 pages.
- New figure is 300 DPI.
- Source-image audit: no missing source images.
- Source-data audit: no missing source-data references.
- Old unresolved phrase “Full-resolution nnU-Net remains an external validation requirement” removed.

## Remaining honest limitation

The completed nnU-Net experiment is a cropped-cache benchmark on 48 x 48 x 1 single-slice NIfTI inputs, not anatomical full-volume nnU-Net. The manuscript now says this explicitly.

