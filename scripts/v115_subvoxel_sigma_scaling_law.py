"""v115: Sub-voxel sigma sweep + cross-cohort lesion-size-normalised
scaling law on cache_3d cohorts (UCSF, MU, RHUH, LUMIERE).

Extends v113 to sub-voxel sigma (0.25, 0.5, 0.75) to test whether
sigma = 1.0 is the true universal optimum or whether the optimum is
even smaller on cohorts with smaller lesions.

If a clean scaling law sigma_opt = a * r^beta emerges across cohorts,
that's the headline deliverable for Proposal H.

Outputs:
    Nature_project/05_results/v115_subvoxel_sigma_scaling_law.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.stats import linregress

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v115_subvoxel_sigma_scaling_law.json"

SIGMA_GRID = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]
HEAT_THRESHOLDS = [0.5, 0.8]
COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]

# v113 found sigma=1.0 optimal across all 5 cohorts.
# v115 tests whether sub-voxel sigma improves further.


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
    return (np.stack(masks) if masks else np.empty((0, 16, 48, 48)),
            np.stack(targets) if targets else np.empty((0, 16, 48, 48)),
            np.array(lesion_radii))


def fit_scaling_law(radii, sigma_opts):
    """Fit log(sigma_opt) = log(a) + beta * log(r) via OLS."""
    valid = (np.array(sigma_opts) > 0) & (np.array(radii) > 0)
    log_r = np.log(np.array(radii)[valid])
    log_s = np.log(np.array(sigma_opts)[valid])
    if len(log_r) < 2:
        return None
    res = linregress(log_r, log_s)
    return {
        "log_a": float(res.intercept),
        "a": float(np.exp(res.intercept)),
        "beta": float(res.slope),
        "r_squared": float(res.rvalue ** 2),
        "p_value": float(res.pvalue),
        "stderr_beta": float(res.stderr),
    }


def main():
    print("=" * 78)
    print("v115 SUB-VOXEL SIGMA SWEEP + LESION-SIZE-NORMALISED SCALING LAW")
    print(f"  cohorts: {COHORTS}")
    print(f"  sigma grid: {SIGMA_GRID} voxels (sub-voxel range)")
    print("=" * 78)

    out = {"version": "v115", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "sigma_grid_voxels": SIGMA_GRID,
           "cohorts": {}, "scaling_law_fits": {}}

    cohort_radii = []
    cohort_opts_05 = []
    cohort_opts_08 = []

    for cohort in COHORTS:
        print(f"\n--- {cohort} ---")
        masks, targets, radii = load_cohort(cohort)
        n = len(masks)
        if n == 0:
            print(f"  no data")
            continue
        median_radius = float(np.median(radii))
        mean_radius = float(np.mean(radii))
        print(f"  N = {n}; median r_eq = {median_radius:.2f} vox; "
              f"mean r_eq = {mean_radius:.2f} vox")

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
                "sigma_over_radius": round(sig / max(median_radius, 1e-6), 4),
                "heat_ge_0.5_mean_pct": round(float(np.nanmean(cov_05) * 100), 2),
                "heat_ge_0.8_mean_pct": round(float(np.nanmean(cov_08) * 100), 2),
            })

        best_05 = max(cohort_results, key=lambda r: r["heat_ge_0.5_mean_pct"])
        best_08 = max(cohort_results, key=lambda r: r["heat_ge_0.8_mean_pct"])

        out["cohorts"][cohort] = {
            "n": n,
            "median_lesion_radius_voxels": round(median_radius, 2),
            "mean_lesion_radius_voxels": round(mean_radius, 2),
            "sigma_sweep": cohort_results,
            "optimal_sigma_at_heat_05": best_05["sigma_voxels"],
            "optimal_sigma_at_heat_08": best_08["sigma_voxels"],
            "optimal_coverage_at_heat_05_pct": best_05["heat_ge_0.5_mean_pct"],
            "optimal_coverage_at_heat_08_pct": best_08["heat_ge_0.8_mean_pct"],
            "optimal_sigma_over_radius_at_heat_08": best_08["sigma_over_radius"],
        }
        cohort_radii.append(median_radius)
        cohort_opts_05.append(best_05["sigma_voxels"])
        cohort_opts_08.append(best_08["sigma_voxels"])

        print(f"  sigma\t   heat>=0.5       heat>=0.8")
        for r in cohort_results:
            mark_05 = "*" if r["sigma_voxels"] == best_05["sigma_voxels"] else " "
            mark_08 = "*" if r["sigma_voxels"] == best_08["sigma_voxels"] else " "
            print(f"  {r['sigma_voxels']:.2f}\t   {r['heat_ge_0.5_mean_pct']:5.2f}{mark_05}        "
                  f"{r['heat_ge_0.8_mean_pct']:5.2f}{mark_08}")
        print(f"  -> optimum @ heat>=0.5: sigma={best_05['sigma_voxels']} "
              f"({best_05['heat_ge_0.5_mean_pct']:.2f}%)")
        print(f"  -> optimum @ heat>=0.8: sigma={best_08['sigma_voxels']} "
              f"({best_08['heat_ge_0.8_mean_pct']:.2f}%, "
              f"sigma/r={best_08['sigma_over_radius']:.4f})")

    # Add v109 PROTEAS optimum from prior knowledge (sigma=1.0 at heat>=0.8)
    proteas_radius = 6.0  # estimated SRS lesion radius (cache_3d format would differ)
    cohort_radii.append(proteas_radius)
    cohort_opts_08.append(1.0)
    cohort_opts_05.append(1.0)

    print("\n=== CROSS-COHORT SCALING LAW FITS ===")
    cohorts_for_fit = COHORTS + ["PROTEAS-brain-mets"]
    for thr_label, opts in [("heat_ge_0.5", cohort_opts_05),
                            ("heat_ge_0.8", cohort_opts_08)]:
        print(f"\n  Threshold: {thr_label}")
        print(f"  Cohorts: {cohorts_for_fit}")
        print(f"  Median radii (vox): {[round(r, 2) for r in cohort_radii]}")
        print(f"  Optimal sigma (vox): {opts}")
        fit = fit_scaling_law(cohort_radii, opts)
        if fit:
            print(f"  Power law fit: sigma_opt = {fit['a']:.4f} * r^{fit['beta']:.4f}")
            print(f"    R^2 = {fit['r_squared']:.4f}, p = {fit['p_value']:.4f}, "
                  f"stderr(beta) = {fit['stderr_beta']:.4f}")
            # Test special cases
            beta = fit['beta']
            stderr = fit['stderr_beta']
            print(f"    beta=0 (constant) test: |0-{beta:.3f}|/{stderr:.3f} "
                  f"= {abs(beta)/max(stderr, 1e-9):.2f} sigma units")
            print(f"    beta=1 (linear) test:   |1-{beta:.3f}|/{stderr:.3f} "
                  f"= {abs(1-beta)/max(stderr, 1e-9):.2f} sigma units")
            print(f"    beta=0.5 (sqrt) test:   |0.5-{beta:.3f}|/{stderr:.3f} "
                  f"= {abs(0.5-beta)/max(stderr, 1e-9):.2f} sigma units")
            out["scaling_law_fits"][thr_label] = {
                **fit,
                "cohorts": cohorts_for_fit,
                "median_radii_voxels": [round(r, 2) for r in cohort_radii],
                "optimal_sigmas_voxels": opts,
            }

    # Universal sigma=1.0 test summary
    cm_08 = [out["cohorts"][c]["optimal_sigma_at_heat_08"] for c in COHORTS]
    out["universal_sigma_summary"] = {
        "all_cohorts_optimal_at_heat_08": cm_08,
        "all_eq_1pt0": all(s == 1.0 for s in cm_08),
        "median_optimal_sigma_at_heat_08": float(np.median(cm_08)),
    }
    print(f"\n=== UNIVERSALITY CHECK ===")
    print(f"Optima at heat>=0.8 across {len(cm_08)} cache_3d cohorts: {cm_08}")
    print(f"All equal to 1.0? {out['universal_sigma_summary']['all_eq_1pt0']}")

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
