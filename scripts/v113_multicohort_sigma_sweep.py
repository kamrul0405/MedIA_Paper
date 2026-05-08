"""v113: Multi-cohort heat-equation σ sweep — extends v109 from PROTEAS-only
to all four LOCO cohorts using cache_3d binary mask data.

Tests Proposal H's hypothesis that σ-selection should be cohort-conditional
(normalised by lesion size) rather than absolute. v109 found σ = 1.0 voxels
optimal on PROTEAS-brain-mets (small lesions, single-fraction SRS); this
extension tests whether UCSF, MU, RHUH, UCSD have different optima.

Uses cache_3d/ binary lesion masks (1018 16x48x48 .npy files):
    UCSF-POSTOP   N=297 (594 b/r files)
    MU-Glioma-Post N=151 (302 files)
    RHUH-GBM      N=39  (78 files)
    LUMIERE       N=22  (44 files; included as cold cohort)

For each cohort and each σ in {1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0} voxels,
computes future-lesion coverage at heat ≥ 0.50 and heat ≥ 0.80, plus
median lesion-equivalent radius for normalised-σ analysis.

Outputs:
    C:/Users/kamru/Downloads/Nature_project/05_results/v113_multicohort_sigma.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v113_multicohort_sigma.json"

SIGMA_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
HEAT_THRESHOLDS = [0.5, 0.8]
COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]


def heat_kernel(mask, sigma):
    if mask.sum() == 0:
        return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0:
        h = h / h.max()
    return h.astype(np.float32)


def coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0:
        return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def equivalent_radius(mask):
    """Lesion-equivalent radius in voxels for a 3D binary mask."""
    n = float(mask.sum())
    if n == 0:
        return 0.0
    return float((3 * n / (4 * np.pi)) ** (1 / 3))


def load_cohort(cohort: str):
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    masks, targets, lesion_radii = [], [], []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists():
            continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        masks.append(m)
        targets.append(t)
        lesion_radii.append(equivalent_radius(m))
    return np.stack(masks) if masks else np.empty((0, 16, 48, 48)), \
           np.stack(targets) if targets else np.empty((0, 16, 48, 48)), \
           np.array(lesion_radii)


def main():
    print("=" * 78)
    print("v113 MULTI-COHORT HEAT-EQUATION SIGMA SWEEP")
    print(f"  cohorts: {COHORTS}")
    print(f"  sigma grid: {SIGMA_GRID} voxels")
    print("=" * 78)

    out = {"version": "v113", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "sigma_grid_voxels": SIGMA_GRID, "cohorts": {}}

    for cohort in COHORTS:
        print(f"\n--- {cohort} ---")
        masks, targets, radii = load_cohort(cohort)
        n = len(masks)
        if n == 0:
            print(f"  no data")
            continue
        median_radius = float(np.median(radii))
        print(f"  N = {n}; median lesion-equivalent radius = {median_radius:.2f} voxels")

        cohort_results = []
        for sig in SIGMA_GRID:
            cov_05 = []
            cov_08 = []
            for i in range(n):
                h = heat_kernel(masks[i], sig)
                cov_05.append(coverage(targets[i], h >= 0.5))
                cov_08.append(coverage(targets[i], h >= 0.8))
            cov_05 = np.array(cov_05)
            cov_08 = np.array(cov_08)
            cohort_results.append({
                "sigma_voxels": sig,
                "evolution_time_t": sig ** 2 / 2,
                "sigma_over_radius": round(sig / max(median_radius, 1e-6), 3),
                "heat_ge_0.5_mean_pct": round(float(np.nanmean(cov_05) * 100), 2),
                "heat_ge_0.8_mean_pct": round(float(np.nanmean(cov_08) * 100), 2),
            })

        # Find per-cohort optima
        best_05 = max(cohort_results, key=lambda r: r["heat_ge_0.5_mean_pct"])
        best_08 = max(cohort_results, key=lambda r: r["heat_ge_0.8_mean_pct"])

        out["cohorts"][cohort] = {
            "n": n,
            "median_lesion_radius_voxels": round(median_radius, 2),
            "sigma_sweep": cohort_results,
            "optimal_sigma_at_heat_05": best_05["sigma_voxels"],
            "optimal_sigma_at_heat_08": best_08["sigma_voxels"],
            "optimal_sigma_over_radius_at_heat_05": best_05["sigma_over_radius"],
            "optimal_sigma_over_radius_at_heat_08": best_08["sigma_over_radius"],
        }

        print(f"  sigma\t heat>=0.5   heat>=0.8")
        for r in cohort_results:
            mark_05 = "*" if r["sigma_voxels"] == best_05["sigma_voxels"] else " "
            mark_08 = "*" if r["sigma_voxels"] == best_08["sigma_voxels"] else " "
            print(f"  {r['sigma_voxels']:.1f}\t {r['heat_ge_0.5_mean_pct']:5.2f}{mark_05}     {r['heat_ge_0.8_mean_pct']:5.2f}{mark_08}")
        print(f"  -> optimal sigma at heat>=0.5: {best_05['sigma_voxels']} ({best_05['heat_ge_0.5_mean_pct']:.2f}%)")
        print(f"  -> optimal sigma at heat>=0.8: {best_08['sigma_voxels']} ({best_08['heat_ge_0.8_mean_pct']:.2f}%)")

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
