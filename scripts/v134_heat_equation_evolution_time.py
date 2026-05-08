"""v134: Heat-equation evolution-time physics interpretation of the
v124 / v132 disease-stratified scaling laws.

Heat-equation theory (Lindeberg 1994; Witkin 1983) gives the
fundamental solution G_sigma(x) = exp(-x^2/(2 sigma^2)) / (2 pi sigma^2)^{d/2}
for the diffusion equation du/dt = Delta u, where the evolution-time
parameter is t = sigma^2 / 2.

The v124 LMM gave for gliomas:
  log(sigma_opt) = -3.094 + 1.273 * log(r_eq)
  =>  sigma_opt = exp(-3.094) * r_eq^1.273 = 0.0453 * r_eq^1.273

Converting to evolution-time:
  t_opt = sigma_opt^2 / 2 = (1/2) * exp(-6.188) * r_eq^2.546
        = 0.001025 * r_eq^2.546
  Equivalently, log(t_opt) = log(0.5) + 2 * log(0.0453) + 2.546 * log(r_eq)
                            = -6.881 + 2.546 * log(r_eq)

Slope on log(t) vs log(r) is 2 * 1.273 = 2.546, which is close to
3 (volume scaling). For brain-mets v127 found beta = -0.383, giving
slope on log(t) vs log(r) of -0.766 (negative — anti-volume).

This script:
  (a) Computes the evolution-time scaling laws explicitly for both
      diseases.
  (b) Interprets the glioma exponent 2.546 in terms of the heat-
      equation Brownian-motion physics: the diffusion time required
      to fill a sphere of radius r scales as r^2 (random walk variance
      proportional to t). Our 2.546 is between 2 (random walk) and 3
      (volume).
  (c) Documents the brain-mets's negative scaling as anti-physics:
      bigger lesions wanting smaller diffusion time, consistent with
      the bimodal recurrence morphology where large lesions are
      typically persistence-only (sigma -> 0).

Outputs:
    Nature_project/05_results/v134_evolution_time_physics.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

OUT = Path(r"C:\Users\kamru\Downloads\Nature_project\05_results\v134_evolution_time_physics.json")

# v124 + v132 fitted disease-stratified slopes
GLIOMA_INTERCEPT = -3.0944
GLIOMA_SLOPE = 1.2733
GLIOMA_SLOPE_CI = [1.158, 1.389]

BRAIN_METS_INTERCEPT_DELTA = 3.8303    # add to glioma intercept
BRAIN_METS_SLOPE_DELTA = -1.6563       # add to glioma slope
BRAIN_METS_INTERCEPT = GLIOMA_INTERCEPT + BRAIN_METS_INTERCEPT_DELTA
BRAIN_METS_SLOPE = GLIOMA_SLOPE + BRAIN_METS_SLOPE_DELTA


def evolution_time_law(intercept, slope):
    """Convert sigma_opt = exp(intercept) * r^slope to t_opt = sigma^2/2."""
    # log(sigma) = intercept + slope * log(r)
    # log(t) = log(0.5) + 2*log(sigma) = log(0.5) + 2*intercept + 2*slope*log(r)
    log_t_intercept = np.log(0.5) + 2 * intercept
    t_slope = 2 * slope
    return {
        "log_t_intercept": float(log_t_intercept),
        "t_intercept_voxel_time": float(np.exp(log_t_intercept)),
        "t_slope_on_log_r": float(t_slope),
        "interpretation": (f"t_opt = {np.exp(log_t_intercept):.6e} * r_eq^{t_slope:.4f}")
    }


def interpret_t_slope(slope):
    """Compare to canonical exponents: 0 (constant t), 2 (random walk), 3 (volume)."""
    return {
        "is_random_walk_like": bool(abs(slope - 2.0) < 0.5),
        "is_volume_like": bool(abs(slope - 3.0) < 0.5),
        "is_constant": bool(abs(slope - 0.0) < 0.5),
        "is_anti_physics": bool(slope < 0),
        "distance_from_random_walk": float(abs(slope - 2.0)),
        "distance_from_volume": float(abs(slope - 3.0)),
    }


def main():
    print("=" * 78)
    print("v134 HEAT-EQUATION EVOLUTION-TIME PHYSICS INTERPRETATION")
    print(f"  v124 glioma: log(sigma) = {GLIOMA_INTERCEPT:+.4f} + {GLIOMA_SLOPE:+.4f}*log(r)")
    print(f"  v132 brain-mets: log(sigma) = {BRAIN_METS_INTERCEPT:+.4f} + "
          f"{BRAIN_METS_SLOPE:+.4f}*log(r)")
    print("=" * 78)

    glioma_t = evolution_time_law(GLIOMA_INTERCEPT, GLIOMA_SLOPE)
    metast_t = evolution_time_law(BRAIN_METS_INTERCEPT, BRAIN_METS_SLOPE)

    print("\n=== EVOLUTION-TIME SCALING LAWS (t = sigma^2/2) ===")
    print(f"  Glioma:     t_opt = {glioma_t['t_intercept_voxel_time']:.6e} * "
          f"r_eq^{glioma_t['t_slope_on_log_r']:.4f}")
    print(f"  Brain-mets: t_opt = {metast_t['t_intercept_voxel_time']:.6e} * "
          f"r_eq^{metast_t['t_slope_on_log_r']:.4f}")

    glioma_interp = interpret_t_slope(glioma_t["t_slope_on_log_r"])
    metast_interp = interpret_t_slope(metast_t["t_slope_on_log_r"])

    print("\n=== PHYSICS INTERPRETATION ===")
    print(f"  Glioma t-slope = {glioma_t['t_slope_on_log_r']:.4f}")
    print(f"    distance from random-walk (slope=2): "
          f"{glioma_interp['distance_from_random_walk']:.3f}")
    print(f"    distance from volume scaling (slope=3): "
          f"{glioma_interp['distance_from_volume']:.3f}")
    if glioma_interp["is_random_walk_like"]:
        print(f"    => random-walk-like diffusion (Brownian motion at lesion surface)")
    elif glioma_interp["is_volume_like"]:
        print(f"    => volume-like growth (recurrence proportional to lesion volume)")
    else:
        print(f"    => intermediate scaling between Brownian and volumetric growth")

    print(f"\n  Brain-mets t-slope = {metast_t['t_slope_on_log_r']:.4f}")
    if metast_interp["is_anti_physics"]:
        print(f"    => ANTI-PHYSICS scaling: larger lesions have shorter diffusion time")
        print(f"    => Consistent with bimodal recurrence morphology (v127):")
        print(f"       persistence (no diffusion) for large lesions; broad outgrowth for small")
    else:
        print(f"    => positive scaling")

    # Concrete predictions for typical lesion radii
    radii = [5, 10, 15, 20, 25]
    print("\n=== CONCRETE PREDICTIONS at typical r_eq values (voxels) ===")
    print(f"  {'r_eq':>6s} {'glioma sigma':>14s} {'brain-mets sigma':>18s} "
          f"{'glioma t':>12s} {'brain-mets t':>16s}")
    for r in radii:
        log_r = np.log(r)
        sigma_g = np.exp(GLIOMA_INTERCEPT + GLIOMA_SLOPE * log_r)
        sigma_b = np.exp(BRAIN_METS_INTERCEPT + BRAIN_METS_SLOPE * log_r)
        t_g = sigma_g ** 2 / 2
        t_b = sigma_b ** 2 / 2
        print(f"  {r:>6d} {sigma_g:>14.3f} {sigma_b:>18.3f} "
              f"{t_g:>12.4f} {t_b:>16.4f}")

    out = {
        "version": "v134",
        "experiment": ("Heat-equation evolution-time physics interpretation of "
                       "disease-stratified sigma scaling laws"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "glioma_sigma_law": {
            "intercept": GLIOMA_INTERCEPT, "slope": GLIOMA_SLOPE,
            "slope_ci": GLIOMA_SLOPE_CI,
            "formula": f"sigma = exp({GLIOMA_INTERCEPT}) * r_eq^{GLIOMA_SLOPE}",
        },
        "brain_mets_sigma_law": {
            "intercept": BRAIN_METS_INTERCEPT, "slope": BRAIN_METS_SLOPE,
            "formula": f"sigma = exp({BRAIN_METS_INTERCEPT}) * r_eq^{BRAIN_METS_SLOPE}",
        },
        "glioma_t_law": glioma_t,
        "brain_mets_t_law": metast_t,
        "glioma_t_interpretation": glioma_interp,
        "brain_mets_t_interpretation": metast_interp,
        "concrete_predictions": [
            {"r_eq_voxels": r,
             "glioma_sigma": float(np.exp(GLIOMA_INTERCEPT + GLIOMA_SLOPE * np.log(r))),
             "brain_mets_sigma": float(np.exp(BRAIN_METS_INTERCEPT + BRAIN_METS_SLOPE * np.log(r))),
             "glioma_t_voxel_time": float(np.exp(GLIOMA_INTERCEPT + GLIOMA_SLOPE * np.log(r)) ** 2 / 2),
             "brain_mets_t_voxel_time": float(np.exp(BRAIN_METS_INTERCEPT + BRAIN_METS_SLOPE * np.log(r)) ** 2 / 2)}
            for r in radii
        ],
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
