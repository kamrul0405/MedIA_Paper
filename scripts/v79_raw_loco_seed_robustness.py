"""v79_raw_loco_seed_robustness.py

Focused seed-robustness check for the v78 raw-MRI LOCO experiment.

The v78 full run tests five methods, but the reviewer-critical question is
whether the raw+mask learned comparator changes the external ranking under
different random initialisations. This script reruns only `raw4_mask` across
all four held-out cohorts and multiple seeds, using the already-built v78 cache.

Output:
  05_results/v79_raw_loco_seed_robustness.json
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "05_results"
V78_PATH = ROOT / "02_scripts" / "v78_raw_mri_loco.py"
OUT = RESULTS / "v79_raw_loco_seed_robustness.json"

EPOCHS = 24
BATCH = 10
SEEDS = [7901, 7902, 7903]
HELD = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]


def load_v78():
    spec = importlib.util.spec_from_file_location("v78_raw_mri_loco", V78_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {V78_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    start = time.time()
    v78 = load_v78()
    data = v78.build_cache(rebuild=False)
    cohorts = data["cohorts"].astype(str)
    raw = data["raw"]
    mask = data["mask"]
    heat = data["heat"]
    y = data["target"][:, None]
    stable = data["stable"]
    x = np.concatenate([raw, mask[:, None]], axis=1)

    heat_by_cohort = {}
    seed_results = {held: [] for held in HELD}
    for held in HELD:
        test_idx = np.where(cohorts == held)[0]
        heat_metrics = v78.eval_arrays(heat[test_idx], y[test_idx, 0], mask[test_idx], stable[test_idx])
        heat_by_cohort[held] = heat_metrics

    for seed in SEEDS:
        print(f"\n=== Seed {seed} ===")
        v78.SEED = seed
        torch.manual_seed(seed)
        np.random.seed(seed)
        for held in HELD:
            test_idx = np.where(cohorts == held)[0]
            train_idx = np.where(cohorts != held)[0]
            tag = f"raw4_mask seed {seed} -> {held}"
            pred = v78.train_model(
                x[train_idx], y[train_idx],
                x[test_idx], y[test_idx],
                in_c=x.shape[1], tag=tag, epochs=EPOCHS, batch=BATCH,
            )
            metrics = v78.eval_arrays(pred, y[test_idx, 0], mask[test_idx], stable[test_idx])
            delta = metrics["brier_mean"] - heat_by_cohort[held]["brier_mean"]
            seed_results[held].append({
                "seed": seed,
                "raw4_mask_brier": metrics["brier_mean"],
                "heat_brier": heat_by_cohort[held]["brier_mean"],
                "delta_raw4_mask_minus_heat": delta,
                "raw4_mask_wins": bool(delta < 0),
                "ece": metrics["ece_mean"],
                "auroc": metrics["auroc_mean"],
            })
            print(f"{held}: raw4_mask={metrics['brier_mean']:.4f}, heat={heat_by_cohort[held]['brier_mean']:.4f}, delta={delta:.4f}")

    summary = {}
    for held, rows in seed_results.items():
        deltas = np.array([r["delta_raw4_mask_minus_heat"] for r in rows], dtype=float)
        summary[held] = {
            "n_seeds": len(rows),
            "mean_delta_raw4_mask_minus_heat": float(deltas.mean()),
            "sd_delta": float(deltas.std(ddof=1)) if len(deltas) > 1 else 0.0,
            "raw4_mask_win_count": int(np.sum(deltas < 0)),
            "heat_win_count": int(np.sum(deltas > 0)),
            "direction": "raw4_mask" if float(deltas.mean()) < 0 else "heat",
            "all_seed_deltas": [float(x) for x in deltas],
        }

    output = {
        "version": "v79_raw_loco_seed_robustness",
        "status": "RAW4_MASK_SEED_ROBUSTNESS_FOR_V78_LOCO",
        "date": time.strftime("%Y-%m-%d"),
        "epochs": EPOCHS,
        "batch_size": BATCH,
        "seeds": SEEDS,
        "held_cohorts": HELD,
        "device": str(v78.DEVICE),
        "gpu": torch.cuda.get_device_name(0) if v78.DEVICE.type == "cuda" else None,
        "heat_by_cohort": heat_by_cohort,
        "seed_results": seed_results,
        "summary": summary,
        "interpretation": (
            "Positive delta means heat beats raw+mask for that held-out cohort; negative delta "
            "means raw+mask beats heat. This robustness check targets the reviewer-critical "
            "external raw-MRI comparator, not every exploratory input variant."
        ),
        "runtime_s": round(time.time() - start, 2),
    }
    OUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print("\nSaved ->", OUT)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
