"""v135: Cross-cohort sigma_broad sweep for the bimodal kernel.

Extends v133 (PROTEAS-only sigma_broad sweep) to all 4 cache_3d
cohorts (UCSF, MU, RHUH, LUMIERE). For each cohort, computes the
optimum sigma_broad and the per-cohort coverage at heat>=0.50 / 0.80.

Outputs:
    Nature_project/05_results/v135_cross_cohort_sigma_broad.json
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
OUT_JSON = RESULTS / "v135_cross_cohort_sigma_broad.json"

COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_BROAD_GRID = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
HEAT_THRESHOLDS = [0.5, 0.8]
N_BOOT = 10000
RNG = np.random.default_rng(13501)


def heat_constant(mask, sigma):
    if mask.sum() == 0: return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0: h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad):
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
    values = np.asarray(values, dtype=float)
    valid = ~np.isnan(values)
    if valid.sum() == 0:
        return float("nan"), float("nan"), float("nan")
    v = values[valid]
    n = len(v)
    sample_idx = RNG.integers(0, n, size=(N_BOOT, n))
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
    print("v135 CROSS-COHORT BIMODAL sigma_broad SWEEP", flush=True)
    print(f"  cohorts: {COHORTS}", flush=True)
    print(f"  sigma_broad grid: {SIGMA_BROAD_GRID}", flush=True)
    print(f"  N_BOOT = {N_BOOT}", flush=True)
    print("=" * 78, flush=True)

    out = {"version": "v135", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "sigma_broad_grid": SIGMA_BROAD_GRID, "cohorts": {}}

    for cohort in COHORTS:
        rows = load_cohort(cohort)
        n = len(rows)
        if n == 0:
            print(f"\n--- {cohort}: no data; skipping ---", flush=True)
            continue
        print(f"\n--- {cohort} (N = {n}) ---", flush=True)
        cohort_results = {"n": n, "thresholds": {}}

        # Compute per-patient coverage for each (sigma_broad, threshold)
        cov_per_sb = {sb: {thr: [] for thr in HEAT_THRESHOLDS}
                      for sb in SIGMA_BROAD_GRID}
        out_per_sb = {sb: {thr: [] for thr in HEAT_THRESHOLDS}
                      for sb in SIGMA_BROAD_GRID}

        t0 = time.time()
        for r in rows:
            m = r["mask"]; tgt = r["target"]
            for sb in SIGMA_BROAD_GRID:
                heat = heat_bimodal(m, sb)
                for thr in HEAT_THRESHOLDS:
                    cov_per_sb[sb][thr].append(coverage(tgt, heat >= thr))
                    out_per_sb[sb][thr].append(outgrowth_coverage(tgt, m, heat >= thr))
        print(f"  per-patient computation: {time.time()-t0:.1f}s", flush=True)

        for thr in HEAT_THRESHOLDS:
            print(f"\n  threshold heat >= {thr}:", flush=True)
            thr_results = {"sigma_broad_results": {}}
            for sb in SIGMA_BROAD_GRID:
                arr_o = np.array(cov_per_sb[sb][thr], dtype=float)
                arr_x = np.array(out_per_sb[sb][thr], dtype=float)
                m_o, lo_o, hi_o = vectorised_cluster_bootstrap(arr_o)
                m_x, lo_x, hi_x = vectorised_cluster_bootstrap(arr_x)
                thr_results["sigma_broad_results"][f"sb_{sb}"] = {
                    "overall_mean_pct": round(m_o * 100, 2),
                    "overall_ci95_pct": [round(lo_o * 100, 2), round(hi_o * 100, 2)],
                    "outgrowth_mean_pct": round(m_x * 100, 2),
                    "outgrowth_ci95_pct": [round(lo_x * 100, 2), round(hi_x * 100, 2)],
                }
                print(f"    sigma_broad = {sb}: overall {m_o*100:5.2f}% "
                      f"[{lo_o*100:.2f}, {hi_o*100:.2f}]  | outgrowth {m_x*100:5.2f}% "
                      f"[{lo_x*100:.2f}, {hi_x*100:.2f}]", flush=True)
            # Find optimum
            best_overall = max(thr_results["sigma_broad_results"].items(),
                                key=lambda kv: kv[1]["overall_mean_pct"])
            best_outgrowth = max(thr_results["sigma_broad_results"].items(),
                                  key=lambda kv: kv[1]["outgrowth_mean_pct"])
            thr_results["best_overall_sigma_broad"] = best_overall[0]
            thr_results["best_outgrowth_sigma_broad"] = best_outgrowth[0]
            print(f"    -> best overall:   {best_overall[0]} "
                  f"({best_overall[1]['overall_mean_pct']:.2f}%)", flush=True)
            print(f"    -> best outgrowth: {best_outgrowth[0]} "
                  f"({best_outgrowth[1]['outgrowth_mean_pct']:.2f}%)", flush=True)
            cohort_results["thresholds"][f"heat_ge_{thr}"] = thr_results

        out["cohorts"][cohort] = cohort_results

    # Cross-cohort summary at heat >= 0.50
    print("\n=== CROSS-COHORT SIGMA_BROAD OPTIMA at heat >= 0.50 ===", flush=True)
    print(f"  {'Cohort':<18s} {'Best (overall)':>16s} {'Best (outgrowth)':>18s}",
          flush=True)
    for cohort in COHORTS:
        if cohort not in out["cohorts"]: continue
        thr_res = out["cohorts"][cohort]["thresholds"].get("heat_ge_0.5")
        if not thr_res: continue
        b_o = thr_res["best_overall_sigma_broad"]
        b_x = thr_res["best_outgrowth_sigma_broad"]
        print(f"  {cohort:<18s} {b_o:>16s} {b_x:>18s}", flush=True)

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
