"""v163: Multi-seed v157 DHEPL universal foundation 5-fold LOCO.

Replicates v157 DHEPL across 3 seeds (42, 123, 999). For each seed
records:
  - Per-cohort ensemble outgrowth, learned outgrowth
  - Per-cohort learned sigma routing weights (avg over patients)

Tests whether the v157 emergent interpretability finding is
seed-robust:
  - UCSF/MU/LUMIERE -> sigma=2 (small smoothing, persistence)
  - RHUH -> sigma=10 (broad outgrowth)
  - PROTEAS -> sigma=4 (middle, brain-mets bimodal)

Outputs:
    Nature_project/05_results/v163_dhepl_multiseed.json
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
import torch.nn.functional as F
from scipy.ndimage import zoom

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
DATA_ZIP = Path(r"C:\Users\kamru\Downloads\Datasets\PKG - PROTEAS-brain-mets-zenodo-17253793.zip")
OUT_JSON = RESULTS / "v163_dhepl_multiseed.json"
OUT_CSV = RESULTS / "v163_dhepl_multiseed_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_GRID = [2.0, 4.0, 7.0, 10.0]
KERNEL_SIZE = 21
EPOCHS = 20  # slightly reduced from 25 to save time across 3 seeds
LR = 1e-3
SEEDS = [42, 123, 999]
TARGET_SHAPE = (16, 48, 48)


def make_gaussian_kernel_3d(sigma, kernel_size=KERNEL_SIZE):
    k = torch.arange(-(kernel_size // 2), (kernel_size // 2) + 1, dtype=torch.float32)
    g = torch.exp(-(k ** 2) / (2 * sigma ** 2))
    g = g / g.sum()
    kx = g.view(1, 1, -1); ky = g.view(1, -1, 1); kz = g.view(-1, 1, 1)
    return (kx * ky * kz).unsqueeze(0).unsqueeze(0)


class DHEPL(nn.Module):
    def __init__(self, sigma_grid=SIGMA_GRID, kernel_size=KERNEL_SIZE):
        super().__init__()
        self.sigma_grid = sigma_grid
        kernels = [make_gaussian_kernel_3d(s, kernel_size) for s in sigma_grid]
        self.register_buffer("kernel_bank", torch.cat(kernels, dim=0))
        self.router = nn.Sequential(
            nn.Conv3d(1, 8, 3, padding=1), nn.GroupNorm(4, 8), nn.GELU(),
            nn.Conv3d(8, 16, 3, padding=1), nn.GroupNorm(4, 16), nn.GELU(),
            nn.AdaptiveAvgPool3d(1), nn.Flatten(),
            nn.Linear(16, len(sigma_grid)),
        )

    def forward(self, mask, return_weights=False):
        B = mask.shape[0]; K = KERNEL_SIZE
        n_sigma = len(self.sigma_grid)
        heat_maps = []
        for i in range(n_sigma):
            kernel = self.kernel_bank[i:i+1]
            heat = F.conv3d(mask, kernel, padding=K // 2)
            heat = heat / (heat.amax(dim=[-3, -2, -1], keepdim=True) + 1e-9)
            heat_maps.append(heat)
        heat_stack = torch.stack(heat_maps, dim=1)
        logits = self.router(mask)
        weights = F.softmax(logits, dim=1)
        weights_exp = weights.view(B, n_sigma, 1, 1, 1, 1)
        weighted_heat = (heat_stack * weights_exp).sum(dim=1)
        out = torch.maximum(mask, weighted_heat)
        if return_weights:
            return out, weights
        return out


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


class DHEPL_UNet(nn.Module):
    def __init__(self, base=24):
        super().__init__()
        self.dhepl = DHEPL()
        self.unet = UNet3D(in_ch=2, base=base)

    def forward(self, mask, return_weights=False):
        if return_weights:
            heat, weights = self.dhepl(mask, return_weights=True)
        else:
            heat = self.dhepl(mask)
        x = torch.cat([mask, heat], dim=1)
        logits = self.unet(x)
        if return_weights:
            return logits, heat, weights
        return logits, heat


def focal_dice_loss(logits, target, alpha=0.95, gamma=2.0, smooth=1e-5):
    p = torch.sigmoid(logits)
    p_t = p * target + (1 - p) * (1 - target)
    alpha_t = alpha * target + (1 - alpha) * (1 - target)
    focal = -alpha_t * (1 - p_t) ** gamma * torch.log(p_t.clamp(1e-7, 1 - 1e-7))
    return focal.mean() + (1 - (2 * (p * target).sum() + smooth) /
                              (p.sum() + target.sum() + smooth))


def overall_coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0: return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def outgrowth_coverage(future_mask, baseline_mask, region_mask):
    fut = future_mask.astype(bool); base = baseline_mask.astype(bool)
    out = fut & (~base)
    if out.sum() == 0: return float("nan")
    return float((out & region_mask.astype(bool)).sum() / out.sum())


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
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth})
    return rows


def resize_to_target(arr, target_shape):
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v163_") as td:
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
                        m_r = resize_to_target(base_mask.astype(np.float32), TARGET_SHAPE) > 0.5
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
                                "mask": m_r.astype(np.float32),
                                "fu": fu_r.astype(np.float32),
                                "outgrowth": outgrowth_r.astype(np.float32),
                            })
                finally:
                    shutil.rmtree(patient_tmp, ignore_errors=True)
                    try: nested_path.unlink()
                    except OSError: pass
                if i % 10 == 0 or i == len(entries):
                    print(f"    {i}/{len(entries)} ({time.time()-t0:.0f}s)", flush=True)
    return rows


def train(model, train_data, seed, epochs=EPOCHS, batch_size=4):
    torch.manual_seed(seed); np.random.seed(seed)
    n = len(train_data)
    X = np.stack([d["mask"][None] for d in train_data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE); Yt = torch.from_numpy(Y).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n)
        for i in range(0, n, batch_size):
            idx = perm[i:i+batch_size]
            xb = Xt[idx]; yb = Yt[idx]
            logits, _ = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad(); loss.backward(); opt.step()
    return model


def evaluate(model, test_data, seed):
    model.eval()
    rows = []
    with torch.no_grad():
        for d in test_data:
            x = torch.from_numpy(d["mask"][None][None]).float().to(DEVICE)
            logits, heat, weights = model(x, return_weights=True)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            heat_np = heat.cpu().numpy()[0, 0]
            w_np = weights.cpu().numpy()[0]
            pred_region = pred >= 0.5
            ensemble_heat = np.maximum(pred, heat_np)
            ensemble_region = ensemble_heat >= 0.5
            row = {
                "pid": d["pid"], "cohort": d["cohort"], "seed": seed,
                "learned_outgrowth": outgrowth_coverage(d["fu"], d["mask"], pred_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
            }
            for i_sig, sigma in enumerate(SIGMA_GRID):
                row[f"weight_sigma_{sigma}"] = float(w_np[i_sig])
            rows.append(row)
    return rows


def main():
    print("=" * 78, flush=True)
    print("v163 MULTI-SEED v157 DHEPL UNIVERSAL FOUNDATION 5-FOLD LOCO", flush=True)
    print(f"  cohorts: {ALL_COHORTS}", flush=True)
    print(f"  seeds: {SEEDS}; sigma grid: {SIGMA_GRID}", flush=True)
    print(f"  device: {DEVICE}; epochs={EPOCHS}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading all 5 cohorts...", flush=True)
    cohorts_data = {}
    for cohort in ALL_COHORTS:
        if cohort == "PROTEAS-brain-mets":
            cohorts_data[cohort] = load_proteas()
        else:
            cohorts_data[cohort] = load_glioma_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])} patients/follow-ups", flush=True)

    all_results = []
    for seed in SEEDS:
        print(f"\n=== seed = {seed} ===", flush=True)
        for held_cohort in ALL_COHORTS:
            t0 = time.time()
            train_data = []
            for c in ALL_COHORTS:
                if c != held_cohort:
                    train_data.extend(cohorts_data[c])
            test_data = cohorts_data[held_cohort]
            model = DHEPL_UNet(base=24).to(DEVICE)
            train(model, train_data, seed)
            rows = evaluate(model, test_data, seed)
            for r in rows:
                r["fold_held_out"] = held_cohort
            all_results.extend(rows)
            del model; torch.cuda.empty_cache(); gc.collect()
            ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in rows]) * 100)
            ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in rows]) * 100)
            avg_weights = {f"sigma_{s}": float(np.mean([r[f"weight_sigma_{s}"] for r in rows]))
                            for s in SIGMA_GRID}
            preferred_sigma = max(avg_weights, key=avg_weights.get).replace("sigma_", "sigma=")
            print(f"  seed={seed} held-out={held_cohort:18s}: "
                  f"ens-out {ens_out:.2f}% ens-ovr {ens_ovr:.2f}% "
                  f"preferred {preferred_sigma} ({time.time()-t0:.0f}s)", flush=True)

    # Save per-patient CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_results:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader(); w.writerows(all_results)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    # Multi-seed aggregate
    out = {"version": "v163",
           "experiment": "Multi-seed v157 DHEPL universal foundation 5-fold LOCO",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "seeds": SEEDS, "by_cohort": {}}
    print(f"\n=== MULTI-SEED AGGREGATE ON DHEPL (mean +/- SE across 3 seeds) ===",
          flush=True)
    print(f"  {'Held-out':<22s} {'metric':<22s} {'mean':>8s} {'SE':>6s} "
          f"{'min':>8s} {'max':>8s}", flush=True)
    metrics = ["learned_outgrowth", "ensemble_outgrowth", "ensemble_overall"]
    for cohort in ALL_COHORTS:
        cohort_rows = [r for r in all_results if r["cohort"] == cohort]
        per_seed = {}
        for s in SEEDS:
            seed_rows = [r for r in cohort_rows if r["seed"] == s]
            per_seed[s] = {m: float(np.nanmean([r[m] for r in seed_rows]) * 100)
                            for m in metrics}
            for sigma in SIGMA_GRID:
                per_seed[s][f"weight_sigma_{sigma}"] = float(
                    np.mean([r[f"weight_sigma_{sigma}"] for r in seed_rows]))
        agg = {"per_seed": per_seed}
        for m in metrics:
            vals = [per_seed[s][m] for s in SEEDS]
            agg[f"{m}_mean"] = float(np.mean(vals))
            agg[f"{m}_se"] = float(np.std(vals, ddof=1) / np.sqrt(len(SEEDS)))
            print(f"  {cohort:<22s} {m:<22s} {agg[f'{m}_mean']:>7.2f}% "
                  f"{agg[f'{m}_se']:>5.2f} {min(vals):>7.2f}% {max(vals):>7.2f}%",
                  flush=True)
        # Multi-seed sigma weights
        for sigma in SIGMA_GRID:
            vals = [per_seed[s][f"weight_sigma_{sigma}"] for s in SEEDS]
            agg[f"weight_sigma_{sigma}_mean"] = float(np.mean(vals))
            agg[f"weight_sigma_{sigma}_se"] = float(np.std(vals, ddof=1) / np.sqrt(len(SEEDS)))
        out["by_cohort"][cohort] = agg
        print(flush=True)

    # 5-cohort mean of seed means
    cohort_mean_per_seed = {s: {m: float(np.mean(
        [out["by_cohort"][c]["per_seed"][s][m] for c in ALL_COHORTS]))
        for m in metrics} for s in SEEDS}
    cohort_mean_summary = {}
    print("=== 5-COHORT MEAN (mean of cohort means; mean +/- SE across 3 seeds) ===",
          flush=True)
    for m in metrics:
        vals = [cohort_mean_per_seed[s][m] for s in SEEDS]
        cohort_mean_summary[m] = {"mean": float(np.mean(vals)),
                                    "se": float(np.std(vals, ddof=1) / np.sqrt(len(SEEDS))),
                                    "min": float(min(vals)), "max": float(max(vals))}
        print(f"  {m:<25s}: {cohort_mean_summary[m]['mean']:5.2f}% +/- "
              f"{cohort_mean_summary[m]['se']:.2f} (range "
              f"[{cohort_mean_summary[m]['min']:.2f}, "
              f"{cohort_mean_summary[m]['max']:.2f}])", flush=True)
    out["cohort_mean_summary"] = cohort_mean_summary

    # Per-cohort sigma routing across seeds
    print(f"\n=== Per-cohort DHEPL learned sigma weights (mean across 3 seeds) ===", flush=True)
    print(f"  {'Held-out':<22s} {'sigma=2':>8s} {'sigma=4':>8s} {'sigma=7':>8s} {'sigma=10':>8s} "
          f"{'preferred':>15s}", flush=True)
    for cohort in ALL_COHORTS:
        agg = out["by_cohort"][cohort]
        weights = {f"sigma={int(s)}": agg[f"weight_sigma_{s}_mean"] for s in SIGMA_GRID}
        preferred = max(weights, key=weights.get)
        print(f"  {cohort:<22s} {weights['sigma=2']:>7.3f} {weights['sigma=4']:>7.3f} "
              f"{weights['sigma=7']:>7.3f} {weights['sigma=10']:>7.3f} {preferred:>15s}",
              flush=True)

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
