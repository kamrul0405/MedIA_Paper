"""v131: Cross-cohort universality test of the v130 PROTEAS-specific
bimodal kernel max(persistence, sigma=4).

Vectorised cluster-bootstrap (10000 resamples) for 4 cache_3d cohorts.

Outputs:
    Nature_project/05_results/v131_cross_cohort_bimodal_universality.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v131_cross_cohort_bimodal_universality.json"

COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_BASELINE_GRID = [0.5, 1.0, 2.5, 4.0]
SIGMA_BROAD = 4.0
HEAT_THRESHOLDS = [0.5, 0.8]
N_BOOT = 10000
RNG = np.random.default_rng(13101)


def heat_constant(mask, sigma):
    if mask.sum() == 0: return np.zeros_like(mask, dtype=np.float32)
    if sigma <= 0:
        h = mask.astype(np.float32)
    else:
        h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0: h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad=SIGMA_BROAD):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma_broad)
    return np.maximum(persistence, h_broad)


def coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0: return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def outgrowth_coverage(future_mask, baseline_mask, region_mask):
    fut = future_mask.astype(bool); base = baseline_mask.astype(bool)
    out = fut & (~base)
    if out.sum() == 0: return float("nan")
    return float((out & region_mask.astype(bool)).sum() / out.sum())


def vectorised_cluster_bootstrap(values, alpha=0.05):
    """Vectorised bootstrap: each 'patient' contributes 1 value, so we can
    sample N_BOOT * n indices in one shot."""
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    if valid.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    v = values[valid]
    n = len(v)
    sample_idx = RNG.integers(0, n, size=(N_BOOT, n))  # uniform with replacement
    boot_means = v[sample_idx].mean(axis=1)
    lo = float(np.percentile(boot_means, 100 * alpha / 2))
    hi = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return float(boot_means.mean()), lo, hi


def load_cohort(cohort: str):
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    rows = []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists(): continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0: continue
        rows.append({"pid": pid, "mask": m, "target": t})
    return rows


def main():
    print("=" * 78, flush=True)
    print("v131 CROSS-COHORT BIMODAL KERNEL UNIVERSALITY TEST (vectorised)", flush=True)
    print(f"  bimodal: heat = max(persistence, gaussian(mask, sigma={SIGMA_BROAD}))", flush=True)
    print(f"  cohorts: {COHORTS}", flush=True)
    print(f"  N_BOOT = {N_BOOT}", flush=True)
    print("=" * 78, flush=True)

    out = {"version": "v131", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "sigma_broad": SIGMA_BROAD, "cohorts": {}}

    for cohort in COHORTS:
        rows = load_cohort(cohort)
        n = len(rows)
        if n == 0:
            print(f"\n--- {cohort}: no data; skipping ---", flush=True)
            continue
        print(f"\n--- {cohort} (N = {n}) ---", flush=True)
        cohort_results = {"n": n, "thresholds": {}}

        # Pre-compute per-patient coverage values
        cov_per_method = {}
        out_per_method = {}
        for thr in HEAT_THRESHOLDS:
            cov_per_method[thr] = {"pers": [], "bimodal": []}
            out_per_method[thr] = {"pers": [], "bimodal": []}
            for sig in SIGMA_BASELINE_GRID:
                cov_per_method[thr][f"sigma_{sig}"] = []
                out_per_method[thr][f"sigma_{sig}"] = []

        t0 = time.time()
        for i, r in enumerate(rows):
            m = r["mask"]; t = r["target"]
            persistence_h = m.astype(np.float32)
            sigma_h = {sig: heat_constant(m, sig) for sig in SIGMA_BASELINE_GRID}
            bimodal_h = heat_bimodal(m, SIGMA_BROAD)
            for thr in HEAT_THRESHOLDS:
                cov_per_method[thr]["pers"].append(coverage(t, persistence_h >= thr))
                cov_per_method[thr]["bimodal"].append(coverage(t, bimodal_h >= thr))
                for sig in SIGMA_BASELINE_GRID:
                    cov_per_method[thr][f"sigma_{sig}"].append(
                        coverage(t, sigma_h[sig] >= thr))
                out_per_method[thr]["pers"].append(
                    outgrowth_coverage(t, m, persistence_h >= thr))
                out_per_method[thr]["bimodal"].append(
                    outgrowth_coverage(t, m, bimodal_h >= thr))
                for sig in SIGMA_BASELINE_GRID:
                    out_per_method[thr][f"sigma_{sig}"].append(
                        outgrowth_coverage(t, m, sigma_h[sig] >= thr))
        print(f"  per-patient coverage computation: {time.time()-t0:.1f}s", flush=True)

        for thr in HEAT_THRESHOLDS:
            print(f"  threshold heat >= {thr}:", flush=True)
            thr_results = {"overall": {}, "outgrowth": {},
                           "paired_deltas_bimodal_minus": {}}
            method_keys = ["pers"] + [f"sigma_{s}" for s in SIGMA_BASELINE_GRID] + ["bimodal"]
            print(f"    overall coverage:", flush=True)
            for k in method_keys:
                arr = np.array(cov_per_method[thr][k], dtype=float)
                m, lo, hi = vectorised_cluster_bootstrap(arr)
                thr_results["overall"][k] = {
                    "mean_pct": round(m * 100, 2),
                    "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)],
                }
                print(f"      {k:10s}: {m*100:5.2f}% [{lo*100:.2f}, {hi*100:.2f}]", flush=True)
            print(f"    outgrowth coverage:", flush=True)
            for k in method_keys:
                arr = np.array(out_per_method[thr][k], dtype=float)
                valid = ~np.isnan(arr)
                if valid.sum() == 0: continue
                m, lo, hi = vectorised_cluster_bootstrap(arr)
                thr_results["outgrowth"][k] = {
                    "mean_pct": round(m * 100, 2),
                    "ci95_pct": [round(lo * 100, 2), round(hi * 100, 2)],
                    "n_with_outgrowth": int(valid.sum()),
                }
                print(f"      {k:10s}: {m*100:5.2f}% [{lo*100:.2f}, {hi*100:.2f}]", flush=True)
            # Paired-delta bimodal vs each baseline (vectorised)
            print(f"    paired delta (bimodal - X):", flush=True)
            bim_overall = np.array(cov_per_method[thr]["bimodal"], dtype=float)
            bim_out = np.array(out_per_method[thr]["bimodal"], dtype=float)
            for k in method_keys:
                if k == "bimodal": continue
                base_overall = np.array(cov_per_method[thr][k], dtype=float)
                d_o = bim_overall - base_overall
                m_o, lo_o, hi_o = vectorised_cluster_bootstrap(d_o)
                base_out = np.array(out_per_method[thr][k], dtype=float)
                d_x = bim_out - base_out
                m_x, lo_x, hi_x = vectorised_cluster_bootstrap(d_x)
                thr_results["paired_deltas_bimodal_minus"][k] = {
                    "overall": {"mean_pp": round(m_o * 100, 2),
                                  "ci95_pp": [round(lo_o * 100, 2), round(hi_o * 100, 2)],
                                  "excludes_zero": bool(lo_o > 0 or hi_o < 0)},
                    "outgrowth": {"mean_pp": round(m_x * 100, 2),
                                  "ci95_pp": [round(lo_x * 100, 2), round(hi_x * 100, 2)],
                                  "excludes_zero": bool(lo_x > 0 or hi_x < 0)},
                }
                sig_o = "**SIG**" if (lo_o > 0 or hi_o < 0) else ""
                sig_x = "**SIG**" if (lo_x > 0 or hi_x < 0) else ""
                print(f"      bim - {k:10s}: overall {m_o*100:+6.2f} pp "
                      f"[{lo_o*100:+.2f}, {hi_o*100:+.2f}] {sig_o:7s} | "
                      f"out {m_x*100:+6.2f} pp [{lo_x*100:+.2f}, {hi_x*100:+.2f}] {sig_x}",
                      flush=True)
            cohort_results["thresholds"][f"heat_ge_{thr}"] = thr_results

        out["cohorts"][cohort] = cohort_results

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    print("\n=== UNIVERSALITY SUMMARY at heat >= 0.50 ===", flush=True)
    print(f"  {'Cohort':<18s} {'Persist':>8s} {'Bimodal':>8s} {'Δ (pp)':>10s} {'CI excl 0?':>12s}",
          flush=True)
    for cohort in COHORTS:
        if cohort not in out["cohorts"]: continue
        thr_res = out["cohorts"][cohort]["thresholds"].get("heat_ge_0.5")
        if not thr_res: continue
        pers = thr_res["overall"]["pers"]["mean_pct"]
        bimodal = thr_res["overall"]["bimodal"]["mean_pct"]
        d = thr_res["paired_deltas_bimodal_minus"]["pers"]
        marker = "YES" if d["excludes_zero"] else "no"
        print(f"  {cohort:<18s} {pers:>7.2f}% {bimodal:>7.2f}% "
              f"{d['mean_pp']:>+9.2f} {marker:>12s}", flush=True)


if __name__ == "__main__":
    main()
