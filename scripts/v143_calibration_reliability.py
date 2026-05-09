"""v143: Calibration analysis (Expected Calibration Error + reliability
diagram bins) for the bimodal kernel across all 5 cohorts.

For each cohort:
  - For each voxel, treat the bimodal heat value as a predicted
    probability of being in the future-lesion mask.
  - Bin voxels by predicted heat in deciles (0.0-0.1, 0.1-0.2, ..., 0.9-1.0).
  - For each bin, compute (a) mean predicted probability,
    (b) empirical observed frequency (= proportion of voxels in
    future-lesion).
  - Expected Calibration Error: ECE = sum_b (n_b/N) * |mean_pred_b -
    obs_freq_b|.

Outputs:
    Nature_project/05_results/v143_calibration_reliability.json
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v143_calibration_reliability.json"

COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_BROAD = 7.0
N_BINS = 10  # decile binning


def heat_constant(mask, sigma):
    if mask.sum() == 0: return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0: h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma_broad)
    return np.maximum(persistence, h_broad)


def calibration_bins(pred_probs, obs_binary, n_bins=N_BINS):
    """Compute mean predicted prob, observed frequency, count per bin."""
    pred_probs = np.asarray(pred_probs, dtype=float)
    obs_binary = np.asarray(obs_binary, dtype=int)
    edges = np.linspace(0, 1, n_bins + 1)
    bins = []
    for i in range(n_bins):
        if i == n_bins - 1:
            mask = (pred_probs >= edges[i]) & (pred_probs <= edges[i + 1])
        else:
            mask = (pred_probs >= edges[i]) & (pred_probs < edges[i + 1])
        n = int(mask.sum())
        if n == 0:
            bins.append({"bin_edges": [edges[i], edges[i + 1]],
                         "n": 0, "mean_pred": (edges[i] + edges[i + 1]) / 2,
                         "obs_freq": float("nan")})
            continue
        mp = float(pred_probs[mask].mean())
        of = float(obs_binary[mask].mean())
        bins.append({"bin_edges": [float(edges[i]), float(edges[i + 1])],
                     "n": n, "mean_pred": mp, "obs_freq": of})
    return bins


def ece(bins):
    """Expected calibration error."""
    n_total = sum(b["n"] for b in bins)
    if n_total == 0: return float("nan")
    err = 0.0
    for b in bins:
        if b["n"] == 0: continue
        err += (b["n"] / n_total) * abs(b["mean_pred"] - b["obs_freq"])
    return float(err)


def main():
    print("=" * 78, flush=True)
    print("v143 CALIBRATION + RELIABILITY DIAGRAMS", flush=True)
    print(f"  cohorts: {COHORTS}", flush=True)
    print(f"  bimodal sigma_broad = {SIGMA_BROAD}", flush=True)
    print(f"  bins: {N_BINS}", flush=True)
    print("=" * 78, flush=True)

    out = {"version": "v143", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "sigma_broad": SIGMA_BROAD, "n_bins": N_BINS, "cohorts": {}}

    for cohort in COHORTS:
        print(f"\n--- {cohort} ---", flush=True)
        files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
        # Aggregate predictions and observations across all patients
        all_preds = []
        all_obs = []
        for fb in files:
            pid = fb.stem.replace("_b", "")
            fr = CACHE / f"{pid}_r.npy"
            if not fr.exists(): continue
            m = (np.load(fb) > 0).astype(np.float32)
            t = (np.load(fr) > 0).astype(np.float32)
            if m.sum() == 0 or t.sum() == 0: continue
            heat = heat_bimodal(m, SIGMA_BROAD)
            all_preds.append(heat.flatten())
            all_obs.append(t.astype(int).flatten())
        if not all_preds:
            print(f"  no data; skipping", flush=True)
            continue
        all_preds = np.concatenate(all_preds)
        all_obs = np.concatenate(all_obs)
        # Subsample to avoid memory blow-up (still 1M+ voxels for ECE)
        if len(all_preds) > 5_000_000:
            rng = np.random.default_rng(14301)
            idx = rng.choice(len(all_preds), size=5_000_000, replace=False)
            all_preds = all_preds[idx]; all_obs = all_obs[idx]

        bins = calibration_bins(all_preds, all_obs)
        ece_val = ece(bins)

        # Brier score
        brier = float(np.mean((all_preds - all_obs) ** 2))

        # Print reliability diagram
        print(f"  N voxels: {len(all_preds):,}", flush=True)
        print(f"  ECE = {ece_val:.4f}; Brier = {brier:.4f}", flush=True)
        print(f"  {'bin':>10s}  {'n':>10s}  {'pred':>8s}  {'obs':>8s}  {'gap':>8s}",
              flush=True)
        for b in bins:
            gap = (b["mean_pred"] - b["obs_freq"]) if not np.isnan(b["obs_freq"]) else float("nan")
            print(f"  [{b['bin_edges'][0]:.1f}, {b['bin_edges'][1]:.1f}] "
                  f" {b['n']:>10,}  {b['mean_pred']:>7.4f}  "
                  f"{b['obs_freq'] if not np.isnan(b['obs_freq']) else 0:>7.4f}  "
                  f"{gap if not np.isnan(gap) else 0:>+7.4f}", flush=True)

        out["cohorts"][cohort] = {
            "n_voxels_evaluated": int(len(all_preds)),
            "ece": ece_val,
            "brier": brier,
            "reliability_bins": bins,
        }

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    print(f"\n=== ECE summary ===", flush=True)
    for c, agg in out["cohorts"].items():
        print(f"  {c:18s}: ECE = {agg['ece']:.4f}, Brier = {agg['brier']:.4f}",
              flush=True)


if __name__ == "__main__":
    main()
