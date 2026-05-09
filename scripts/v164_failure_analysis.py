"""v164: Patient-level failure-mode analysis on v156 universal foundation
model.

Identifies the bottom-10% per-cohort failures (lowest ensemble outgrowth
coverage) and characterises them by:
  - Lesion size (baseline mask voxel count, equivalent radius)
  - Per-patient outgrowth volume (future_mask AND NOT baseline_mask)
  - Cohort

Tests whether failures are concentrated in particular lesion-size strata
(small vs medium vs large lesions). Required for clinical-journal
subgroup / failure-mode reporting.

Outputs:
    Nature_project/05_results/v164_failure_analysis.json
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import zoom

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
INPUT_CSV = RESULTS / "v156_universal_foundation_per_patient.csv"
OUT_JSON = RESULTS / "v164_failure_analysis.json"

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]


def equivalent_radius_voxels(volume_voxels):
    if volume_voxels <= 0: return 0.0
    return float((3 * volume_voxels / (4 * np.pi)) ** (1 / 3))


def main():
    print("=" * 78, flush=True)
    print("v164 PATIENT-LEVEL FAILURE-MODE ANALYSIS ON v156", flush=True)
    print("=" * 78, flush=True)

    rows = list(csv.DictReader(open(INPUT_CSV)))
    print(f"\nLoaded {len(rows)} per-patient rows", flush=True)

    # For each patient, extract lesion volume + outgrowth volume from cache_3d
    # Note: PROTEAS volumes are at TARGET_SHAPE=(16,48,48) so we just count voxels
    # uniformly across cohorts at the same shape
    print("\nLoading lesion volumes...", flush=True)
    lesion_volumes = {}
    for cohort in ALL_COHORTS:
        if cohort == "PROTEAS-brain-mets":
            # Skip — PROTEAS volumes computed at (16,48,48) inside v156 already
            # We can use the rows' learned/bimodal/ensemble values directly
            continue
        files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
        for fb in files:
            pid = fb.stem.replace("_b", "")
            fr = CACHE / f"{pid}_r.npy"
            if not fr.exists(): continue
            m = (np.load(fb) > 0)
            t = (np.load(fr) > 0)
            lesion_volumes[pid] = {
                "cohort": cohort,
                "baseline_voxels": int(m.sum()),
                "future_voxels": int(t.sum()),
                "outgrowth_voxels": int((t & ~m).sum()),
                "r_eq_baseline_voxels": equivalent_radius_voxels(int(m.sum())),
            }
    print(f"  Loaded {len(lesion_volumes)} glioma patient volumes", flush=True)

    out = {"version": "v164", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "by_cohort": {}}

    print("\n=== Per-cohort failure-mode analysis (bottom-10% lowest ens-out) ===\n",
          flush=True)
    for cohort in ALL_COHORTS:
        sub = [r for r in rows if r["fold_held_out"] == cohort]
        if not sub: continue
        # Sort by ensemble_outgrowth ascending
        sub_sorted = sorted(sub, key=lambda r: float(r["ensemble_outgrowth"]))
        n = len(sub_sorted)
        n_failures = max(int(n * 0.10), 1)
        failures = sub_sorted[:n_failures]
        successes = sub_sorted[n_failures:]

        cohort_results = {"n": n, "n_failures_bottom_10pct": n_failures}

        # Stats on failures vs successes
        if cohort != "PROTEAS-brain-mets":
            fail_baseline = []; fail_outgrowth_vol = []; fail_r_eq = []
            succ_baseline = []; succ_outgrowth_vol = []; succ_r_eq = []
            for r in failures:
                pid = r["pid"]
                if pid in lesion_volumes:
                    lv = lesion_volumes[pid]
                    fail_baseline.append(lv["baseline_voxels"])
                    fail_outgrowth_vol.append(lv["outgrowth_voxels"])
                    fail_r_eq.append(lv["r_eq_baseline_voxels"])
            for r in successes:
                pid = r["pid"]
                if pid in lesion_volumes:
                    lv = lesion_volumes[pid]
                    succ_baseline.append(lv["baseline_voxels"])
                    succ_outgrowth_vol.append(lv["outgrowth_voxels"])
                    succ_r_eq.append(lv["r_eq_baseline_voxels"])

            if fail_baseline and succ_baseline:
                cohort_results["failure_vs_success_lesion_size"] = {
                    "fail_median_baseline_voxels": float(np.median(fail_baseline)),
                    "succ_median_baseline_voxels": float(np.median(succ_baseline)),
                    "fail_median_outgrowth_voxels": float(np.median(fail_outgrowth_vol)),
                    "succ_median_outgrowth_voxels": float(np.median(succ_outgrowth_vol)),
                    "fail_median_r_eq_voxels": float(np.median(fail_r_eq)),
                    "succ_median_r_eq_voxels": float(np.median(succ_r_eq)),
                }

        # Distribution of ens-out per cohort
        ens_out = [float(r["ensemble_outgrowth"]) * 100 for r in sub]
        cohort_results["ens_out_distribution_pct"] = {
            "min": float(min(ens_out)),
            "p10": float(np.percentile(ens_out, 10)),
            "p25": float(np.percentile(ens_out, 25)),
            "median": float(np.percentile(ens_out, 50)),
            "p75": float(np.percentile(ens_out, 75)),
            "p90": float(np.percentile(ens_out, 90)),
            "max": float(max(ens_out)),
            "mean": float(np.mean(ens_out)),
            "n_at_zero": int(sum(1 for x in ens_out if x == 0)),
            "n_lt_50": int(sum(1 for x in ens_out if x < 50)),
            "n_gte_80": int(sum(1 for x in ens_out if x >= 80)),
        }

        print(f"  {cohort:<22s}  N={n:>3d}", flush=True)
        d = cohort_results["ens_out_distribution_pct"]
        print(f"    Distribution: min {d['min']:5.1f}%  p10 {d['p10']:5.1f}%  "
              f"p25 {d['p25']:5.1f}%  median {d['median']:5.1f}%  p75 {d['p75']:5.1f}%  "
              f"p90 {d['p90']:5.1f}%  max {d['max']:5.1f}%", flush=True)
        print(f"    n at 0%: {d['n_at_zero']}; n < 50%: {d['n_lt_50']}; "
              f"n >= 80%: {d['n_gte_80']}", flush=True)

        if "failure_vs_success_lesion_size" in cohort_results:
            f = cohort_results["failure_vs_success_lesion_size"]
            print(f"    Failures (bottom 10%, n={n_failures}): "
                  f"median lesion {f['fail_median_baseline_voxels']:.0f} vox  "
                  f"median outgrowth {f['fail_median_outgrowth_voxels']:.0f} vox", flush=True)
            print(f"    Success (top 90%): "
                  f"median lesion {f['succ_median_baseline_voxels']:.0f} vox  "
                  f"median outgrowth {f['succ_median_outgrowth_voxels']:.0f} vox", flush=True)

        # Lesion-size stratified analysis
        if cohort != "PROTEAS-brain-mets":
            tertiles_data = []
            for r in sub:
                pid = r["pid"]
                if pid in lesion_volumes:
                    lv = lesion_volumes[pid]
                    tertiles_data.append({
                        "ens_out": float(r["ensemble_outgrowth"]) * 100,
                        "baseline_vox": lv["baseline_voxels"],
                        "r_eq": lv["r_eq_baseline_voxels"],
                    })
            if tertiles_data:
                # Sort by lesion size, partition into tertiles
                tertiles_data.sort(key=lambda x: x["baseline_vox"])
                n_t = len(tertiles_data) // 3
                small = tertiles_data[:n_t]
                medium = tertiles_data[n_t:2*n_t]
                large = tertiles_data[2*n_t:]
                tertile_summary = {}
                for label, group in [("small", small), ("medium", medium), ("large", large)]:
                    if not group: continue
                    ens_outs = [p["ens_out"] for p in group]
                    rqs = [p["r_eq"] for p in group]
                    tertile_summary[label] = {
                        "n": len(group),
                        "median_r_eq_voxels": float(np.median(rqs)),
                        "mean_ens_out_pct": float(np.mean(ens_outs)),
                        "median_ens_out_pct": float(np.median(ens_outs)),
                    }
                cohort_results["lesion_size_tertiles"] = tertile_summary
                print(f"    Lesion-size tertiles ens-out (mean / median):", flush=True)
                for label in ["small", "medium", "large"]:
                    if label in tertile_summary:
                        ts = tertile_summary[label]
                        print(f"      {label:8s} (n={ts['n']:>3d}, r~{ts['median_r_eq_voxels']:.1f} vox): "
                              f"{ts['mean_ens_out_pct']:5.2f}% / "
                              f"{ts['median_ens_out_pct']:5.2f}%", flush=True)

        out["by_cohort"][cohort] = cohort_results
        print(flush=True)

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
