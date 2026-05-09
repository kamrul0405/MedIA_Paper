"""v154: Multi-seed v152 cross-disease robustness audit.

Replicates v152 cross-disease test (4 glioma cohorts -> PROTEAS-brain-mets)
across 3 seeds (42, 123, 999) to bulletproof the paradigm-shifting
v152 finding for Nature/Cell-tier review.

Outputs:
    Nature_project/05_results/v154_multiseed_cross_disease.json
"""
from __future__ import annotations

import csv
import gc
import json
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter, zoom

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
DATA_ZIP = Path(r"C:\Users\kamru\Downloads\Datasets\PKG - PROTEAS-brain-mets-zenodo-17253793.zip")
OUT_JSON = RESULTS / "v154_multiseed_cross_disease.json"
OUT_CSV = RESULTS / "v154_multiseed_cross_disease_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

GLIOMA_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
SEEDS = [42, 123, 999]
TARGET_SHAPE = (16, 48, 48)


def heat_constant(mask, sigma):
    if mask.sum() == 0: return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0: h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma_broad)
    return np.maximum(persistence, h_broad)


def overall_coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0: return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def outgrowth_coverage(future_mask, baseline_mask, region_mask):
    fut = future_mask.astype(bool); base = baseline_mask.astype(bool)
    out = fut & (~base)
    if out.sum() == 0: return float("nan")
    return float((out & region_mask.astype(bool)).sum() / out.sum())


class UNet3D(nn.Module):
    def __init__(self, in_ch=2, base=24):
        super().__init__()
        self.enc1 = self._block(in_ch, base)
        self.enc2 = self._block(base, base * 2)
        self.enc3 = self._block(base * 2, base * 4)
        self.dec2 = self._block(base * 4 + base * 2, base * 2)
        self.dec1 = self._block(base * 2 + base, base)
        self.out = nn.Conv3d(base, 1, 1)
        self.pool = nn.MaxPool3d(2)
        self.up = nn.Upsample(scale_factor=2, mode="trilinear", align_corners=False)

    def _block(self, in_ch, out_ch):
        return nn.Sequential(
            nn.Conv3d(in_ch, out_ch, 3, padding=1),
            nn.GroupNorm(8, out_ch), nn.GELU(),
            nn.Conv3d(out_ch, out_ch, 3, padding=1),
            nn.GroupNorm(8, out_ch), nn.GELU(),
        )

    def forward(self, x):
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        d2 = self.dec2(torch.cat([self.up(e3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up(d2), e1], dim=1))
        return self.out(d1)


def focal_dice_loss(logits, target, alpha=0.95, gamma=2.0, smooth=1e-5):
    p = torch.sigmoid(logits)
    p_t = p * target + (1 - p) * (1 - target)
    alpha_t = alpha * target + (1 - alpha) * (1 - target)
    focal = -alpha_t * (1 - p_t) ** gamma * torch.log(p_t.clamp(1e-7, 1 - 1e-7))
    return focal.mean() + (1 - (2 * (p * target).sum() + smooth) /
                              (p.sum() + target.sum() + smooth))


def load_glioma_cohort(cohort):
    files = sorted(CACHE.glob(f"{cohort}_*_b.npy"))
    rows = []
    for fb in files:
        pid = fb.stem.replace("_b", "")
        fr = CACHE / f"{pid}_r.npy"
        if not fr.exists(): continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0: continue
        outgrowth = (t.astype(bool) & ~m.astype(bool)).astype(np.float32)
        heat = heat_bimodal(m, SIGMA_BROAD)
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth, "heat_bimodal": heat})
    return rows


def resize_to_target(arr, target_shape):
    factors = [t/s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v154_") as td:
        work = Path(td)
        with zipfile.ZipFile(DATA_ZIP) as outer:
            entries = sorted(
                [e for e in outer.infolist() if re.fullmatch(r"P\d+[ab]?\.zip", e.filename)],
                key=lambda e: e.filename,
            )
            print(f"  PROTEAS: {len(entries)} patient zips found", flush=True)
            t0 = time.time()
            for i, entry in enumerate(entries, 1):
                pid = Path(entry.filename).stem
                nested_path = work / entry.filename
                with outer.open(entry) as src, open(nested_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                patient_tmp = work / f"{pid}_files"
                patient_tmp.mkdir(exist_ok=True)
                try:
                    with zipfile.ZipFile(nested_path) as inner:
                        names = inner.namelist()
                        prefix = f"{pid}/"
                        seg_dirs = [f"{prefix}tumor segmentation/", f"{prefix}tumor_segmentation/"]
                        baseline = next(
                            (f"{seg_dir}{pid}_tumor_mask_baseline.nii.gz" for seg_dir in seg_dirs
                             if f"{seg_dir}{pid}_tumor_mask_baseline.nii.gz" in names),
                            f"{prefix}tumor segmentation/{pid}_tumor_mask_baseline.nii.gz",
                        )
                        followups = sorted([
                            n for n in names
                            if any(n.startswith(f"{seg_dir}{pid}_tumor_mask_fu") for seg_dir in seg_dirs)
                            and n.endswith(".nii.gz")
                        ])
                        if baseline not in names: continue
                        out_path = patient_tmp / Path(baseline).name
                        out_path.write_bytes(inner.read(baseline))
                        base_arr = np.asanyarray(nib.load(str(out_path)).dataobj).astype(np.float32)
                        base_mask = base_arr > 0
                        if base_mask.sum() == 0: continue
                        heat = heat_bimodal(base_mask, SIGMA_BROAD)
                        m_r = resize_to_target(base_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                        heat_r = resize_to_target(heat, TARGET_SHAPE)
                        for fu_name in followups:
                            try:
                                fu_path = patient_tmp / Path(fu_name).name
                                fu_path.write_bytes(inner.read(fu_name))
                                fu_arr = np.asanyarray(nib.load(str(fu_path)).dataobj).astype(np.float32)
                            except Exception:
                                continue
                            fu_mask = fu_arr > 0
                            if fu_mask.shape != base_mask.shape or not fu_mask.any(): continue
                            fu_r = resize_to_target(fu_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                            outgrowth_r = resize_to_target(
                                (fu_mask & ~base_mask).astype(np.float32), TARGET_SHAPE) > 0.5
                            rows.append({
                                "pid": pid, "cohort": "PROTEAS-brain-mets",
                                "fu_name": Path(fu_name).stem,
                                "mask": m_r.astype(np.float32),
                                "fu": fu_r.astype(np.float32),
                                "outgrowth": outgrowth_r.astype(np.float32),
                                "heat_bimodal": heat_r,
                            })
                finally:
                    shutil.rmtree(patient_tmp, ignore_errors=True)
                    try: nested_path.unlink()
                    except OSError: pass
                if i % 10 == 0 or i == len(entries):
                    print(f"    {i}/{len(entries)} ({time.time()-t0:.0f}s)", flush=True)
    return rows


def train_unet(train_data, seed, epochs=EPOCHS, batch_size=4):
    torch.manual_seed(seed); np.random.seed(seed)
    n = len(train_data)
    X = np.stack([np.stack([d["mask"], d["heat_bimodal"]], axis=0)
                   for d in train_data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE); Yt = torch.from_numpy(Y).to(DEVICE)
    model = UNet3D(in_ch=2, base=24).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n)
        for i in range(0, n, batch_size):
            idx = perm[i:i+batch_size]
            xb = Xt[idx]; yb = Yt[idx]
            logits = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad(); loss.backward(); opt.step()
    return model


def evaluate(model, test_data, seed):
    model.eval()
    rows = []
    with torch.no_grad():
        for d in test_data:
            x = np.stack([d["mask"], d["heat_bimodal"]], axis=0).astype(np.float32)
            xt = torch.from_numpy(x[None]).to(DEVICE)
            logits = model(xt)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            pred_region = pred >= 0.5
            bimodal_region = d["heat_bimodal"] >= 0.5
            ensemble_heat = np.maximum(pred, d["heat_bimodal"])
            ensemble_region = ensemble_heat >= 0.5
            rows.append({
                "pid": d["pid"], "cohort": d["cohort"], "seed": seed,
                "fu_name": d.get("fu_name", ""),
                "learned_overall": overall_coverage(d["fu"], pred_region),
                "learned_outgrowth": outgrowth_coverage(d["fu"], d["mask"], pred_region),
                "bimodal_outgrowth": outgrowth_coverage(d["fu"], d["mask"], bimodal_region),
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
            })
    return rows


def main():
    print("=" * 78, flush=True)
    print("v154 MULTI-SEED v152 CROSS-DISEASE ROBUSTNESS AUDIT", flush=True)
    print(f"  Train: 4 glioma cohorts; Test: PROTEAS-brain-mets LOPO", flush=True)
    print(f"  device: {DEVICE}; seeds: {SEEDS}; epochs={EPOCHS}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading glioma training cohorts...", flush=True)
    train_data = []
    for cohort in GLIOMA_COHORTS:
        rows = load_glioma_cohort(cohort)
        train_data.extend(rows)
        print(f"  {cohort}: {len(rows)} patients", flush=True)
    print(f"  Combined glioma training: {len(train_data)} patients", flush=True)

    print(f"\nLoading PROTEAS-brain-mets and resizing to {TARGET_SHAPE}...", flush=True)
    test_data = load_proteas()
    print(f"  PROTEAS: {len(test_data)} follow-ups across "
          f"{len(set(d['pid'] for d in test_data))} patients", flush=True)

    all_results = []
    for seed in SEEDS:
        t0 = time.time()
        model = train_unet(train_data, seed)
        rows = evaluate(model, test_data, seed)
        all_results.extend(rows)
        del model; torch.cuda.empty_cache(); gc.collect()
        ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in rows]) * 100)
        learned_out = float(np.nanmean([r["learned_outgrowth"] for r in rows]) * 100)
        ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in rows]) * 100)
        print(f"  seed={seed}: PROTEAS learned-out={learned_out:.2f}% "
              f"ens-out={ens_out:.2f}% ens-ovr={ens_ovr:.2f}% "
              f"({time.time()-t0:.0f}s)", flush=True)

    # Multi-seed aggregate
    print(f"\n=== MULTI-SEED AGGREGATE on PROTEAS (mean +/- SE across {len(SEEDS)} seeds) ===",
          flush=True)
    per_seed = {}
    for s in SEEDS:
        seed_rows = [r for r in all_results if r["seed"] == s]
        per_seed[s] = {
            "learned_outgrowth": float(np.nanmean([r["learned_outgrowth"] for r in seed_rows]) * 100),
            "bimodal_outgrowth": float(np.nanmean([r["bimodal_outgrowth"] for r in seed_rows]) * 100),
            "ensemble_outgrowth": float(np.nanmean([r["ensemble_outgrowth"] for r in seed_rows]) * 100),
            "learned_overall": float(np.nanmean([r["learned_overall"] for r in seed_rows]) * 100),
            "ensemble_overall": float(np.nanmean([r["ensemble_overall"] for r in seed_rows]) * 100),
        }
    metrics_to_summarize = ["learned_outgrowth", "ensemble_outgrowth",
                              "learned_overall", "ensemble_overall"]
    summary = {}
    for m in metrics_to_summarize:
        vals = [per_seed[s][m] for s in SEEDS]
        mean = float(np.mean(vals))
        se = float(np.std(vals, ddof=1) / np.sqrt(len(SEEDS)))
        summary[m] = {"mean": mean, "se": se,
                      "min": float(min(vals)), "max": float(max(vals))}
        print(f"  {m:25s}: {mean:5.2f}% +/- {se:.2f} "
              f"(range [{min(vals):.2f}, {max(vals):.2f}])", flush=True)

    # Save per-patient CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_results:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader(); w.writerows(all_results)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    # Comparison vs v152 single-seed
    print(f"\n=== COMPARISON: v154 multi-seed vs v152 single-seed ===", flush=True)
    print(f"  v152 single-seed (seed=42): ens-out 79.16%  ens-ovr 92.28%", flush=True)
    print(f"  v154 multi-seed mean: ens-out {summary['ensemble_outgrowth']['mean']:.2f}% "
          f"+/- {summary['ensemble_outgrowth']['se']:.2f} "
          f"(range [{summary['ensemble_outgrowth']['min']:.2f}, "
          f"{summary['ensemble_outgrowth']['max']:.2f}])", flush=True)

    # Comparison to v140 in-disease baseline
    print(f"\n=== COMPARISON to v140 in-disease (PROTEAS-trained) baseline ===",
          flush=True)
    print(f"  v140 in-disease ens-out (PROTEAS LOPO): 44.93%", flush=True)
    print(f"  v154 cross-disease ens-out (3-seed mean): "
          f"{summary['ensemble_outgrowth']['mean']:.2f}%", flush=True)
    print(f"  v154 cross-disease GAIN over in-disease: "
          f"{summary['ensemble_outgrowth']['mean'] - 44.93:+.2f} pp", flush=True)

    out = {"version": "v154",
           "experiment": "Multi-seed v152 cross-disease robustness audit",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "seeds": SEEDS,
           "training_cohorts": GLIOMA_COHORTS,
           "n_train": len(train_data),
           "test_cohort": "PROTEAS-brain-mets",
           "n_test_followups": len(test_data),
           "n_test_patients": int(len(set(d["pid"] for d in test_data))),
           "per_seed_aggregate_pct": per_seed,
           "multi_seed_summary_pct": summary,
           "comparison_to_in_disease": {
               "v140_in_disease_ens_out_pct": 44.93,
               "v154_cross_disease_ens_out_mean_pct": summary["ensemble_outgrowth"]["mean"],
               "gain_pp": summary["ensemble_outgrowth"]["mean"] - 44.93,
           }}
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
