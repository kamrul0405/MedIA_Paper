"""v157: Differentiable Heat-Equation Physics Layer (DHEPL) embedded
in the universal foundation model 5-fold LOCO.

DHEPL replaces the fixed bimodal kernel max(persistence, sigma=7-Gauss)
with a learnable physics layer:
  - A small CNN router takes the input mask and produces softmax
    weights over a sigma grid {2, 4, 7, 10}.
  - Pre-computed Gaussian kernels at each sigma are applied as
    F.conv3d.
  - DHEPL = max(persistence, sum_i w_i * Gaussian(mask, sigma_i)).
  - All differentiable; trained jointly with the U-Net.

The key novelty: per-patient adaptive sigma learned end-to-end from
data, instead of a fixed handcrafted hyperparameter. The bimodal
kernel becomes a special case (uniform weighting on sigma=7).

For each held-out cohort c in {UCSF, MU, RHUH, LUMIERE, PROTEAS},
train on the OTHER 4 cohorts and evaluate on c.

Outputs:
    Nature_project/05_results/v157_dhepl_universal_loco.json
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
OUT_JSON = RESULTS / "v157_dhepl_universal_loco.json"
OUT_CSV = RESULTS / "v157_dhepl_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_GRID = [2.0, 4.0, 7.0, 10.0]
KERNEL_SIZE = 21
EPOCHS = 25
LR = 1e-3
SEED = 42
TARGET_SHAPE = (16, 48, 48)


def make_gaussian_kernel_3d(sigma, kernel_size=KERNEL_SIZE):
    k = torch.arange(-(kernel_size // 2), (kernel_size // 2) + 1, dtype=torch.float32)
    gauss_1d = torch.exp(-(k ** 2) / (2 * sigma ** 2))
    gauss_1d = gauss_1d / gauss_1d.sum()
    kx = gauss_1d.view(1, 1, -1)
    ky = gauss_1d.view(1, -1, 1)
    kz = gauss_1d.view(-1, 1, 1)
    return (kx * ky * kz).unsqueeze(0).unsqueeze(0)  # (1, 1, k, k, k)


class DHEPL(nn.Module):
    """Differentiable Heat-Equation Physics Layer.

    Input: mask (B, 1, D, H, W) — binary baseline mask
    Output: heat (B, 1, D, H, W) — bimodal physics-informed prior
    Side: weights (B, n_sigma) — per-patient learned routing
    """
    def __init__(self, sigma_grid=SIGMA_GRID, kernel_size=KERNEL_SIZE):
        super().__init__()
        self.sigma_grid = sigma_grid
        kernels = [make_gaussian_kernel_3d(s, kernel_size) for s in sigma_grid]
        self.register_buffer("kernel_bank",
                              torch.cat(kernels, dim=0))  # (n_sigma, 1, k, k, k)
        # CNN router
        self.router = nn.Sequential(
            nn.Conv3d(1, 8, 3, padding=1),
            nn.GroupNorm(4, 8), nn.GELU(),
            nn.Conv3d(8, 16, 3, padding=1),
            nn.GroupNorm(4, 16), nn.GELU(),
            nn.AdaptiveAvgPool3d(1),
            nn.Flatten(),
            nn.Linear(16, len(sigma_grid)),
        )

    def forward(self, mask, return_weights=False):
        B = mask.shape[0]
        K = KERNEL_SIZE
        # Apply each Gaussian kernel
        # Use grouped conv: replicate input across n_sigma channels, apply kernels
        n_sigma = len(self.sigma_grid)
        # Manual loop is fine for small n_sigma
        heat_maps = []
        for i in range(n_sigma):
            kernel = self.kernel_bank[i:i+1]  # (1, 1, k, k, k)
            heat = F.conv3d(mask, kernel, padding=K // 2)
            # Normalize per-batch: divide by max
            max_val = heat.amax(dim=[-3, -2, -1], keepdim=True) + 1e-9
            heat = heat / max_val
            heat_maps.append(heat)
        heat_stack = torch.stack(heat_maps, dim=1)  # (B, n_sigma, 1, D, H, W)

        # Router: per-patient soft weights over sigma
        logits = self.router(mask)  # (B, n_sigma)
        weights = F.softmax(logits, dim=1)  # (B, n_sigma)
        weights_exp = weights.view(B, n_sigma, 1, 1, 1, 1)
        weighted_heat = (heat_stack * weights_exp).sum(dim=1)  # (B, 1, D, H, W)

        # Bimodal: max(persistence, weighted)
        out = torch.maximum(mask, weighted_heat)
        if return_weights:
            return out, weights
        return out


class DHEPL_UNet(nn.Module):
    """U-Net with DHEPL as the heat-prior generator. Input mask -> DHEPL
    produces learned heat -> [mask, heat] -> U-Net -> outgrowth."""
    def __init__(self, base=24):
        super().__init__()
        self.dhepl = DHEPL()
        self.unet = self._make_unet(in_ch=2, base=base)

    @staticmethod
    def _make_unet(in_ch=2, base=24):
        return UNet3D(in_ch=in_ch, base=base)

    def forward(self, mask, return_weights=False):
        if return_weights:
            heat, weights = self.dhepl(mask, return_weights=True)
        else:
            heat = self.dhepl(mask)
        x = torch.cat([mask, heat], dim=1)  # (B, 2, D, H, W)
        logits = self.unet(x)
        if return_weights:
            return logits, heat, weights
        return logits, heat


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
    with tempfile.TemporaryDirectory(prefix="proteas_v157_") as td:
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
                                "fu_name": Path(fu_name).stem,
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
    X = np.stack([d["mask"][None] for d in train_data]).astype(np.float32)  # (N, 1, D, H, W)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE); Yt = torch.from_numpy(Y).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n)
        ep_loss = 0.0; nb = 0
        for i in range(0, n, batch_size):
            idx = perm[i:i+batch_size]
            xb = Xt[idx]; yb = Yt[idx]
            logits, _ = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad(); loss.backward(); opt.step()
            ep_loss += float(loss.item()); nb += 1
        if (ep + 1) % 5 == 0:
            print(f"    epoch {ep+1}/{epochs}: avg loss = {ep_loss/nb:.4f}", flush=True)
    return model


def evaluate(model, test_data):
    model.eval()
    rows = []
    with torch.no_grad():
        for d in test_data:
            x = torch.from_numpy(d["mask"][None][None]).float().to(DEVICE)
            logits, heat, weights = model(x, return_weights=True)
            pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
            heat_np = heat.cpu().numpy()[0, 0]
            w_np = weights.cpu().numpy()[0]  # (n_sigma,)
            pred_region = pred >= 0.5
            heat_region = heat_np >= 0.5
            ensemble_heat = np.maximum(pred, heat_np)
            ensemble_region = ensemble_heat >= 0.5
            row = {
                "pid": d["pid"], "cohort": d["cohort"],
                "fu_name": d.get("fu_name", ""),
                "learned_overall": overall_coverage(d["fu"], pred_region),
                "learned_outgrowth": outgrowth_coverage(d["fu"], d["mask"], pred_region),
                "dhepl_outgrowth": outgrowth_coverage(d["fu"], d["mask"], heat_region),
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
            }
            for i_sig, sigma in enumerate(SIGMA_GRID):
                row[f"weight_sigma_{sigma}"] = float(w_np[i_sig])
            rows.append(row)
    return rows


def main():
    print("=" * 78, flush=True)
    print("v157 DIFFERENTIABLE PHYSICS LAYER (DHEPL) UNIVERSAL FOUNDATION 5-FOLD LOCO",
          flush=True)
    print(f"  All cohorts: {ALL_COHORTS}", flush=True)
    print(f"  sigma grid: {SIGMA_GRID}; kernel size: {KERNEL_SIZE}", flush=True)
    print(f"  device: {DEVICE}; epochs={EPOCHS}; seed={SEED}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading all 5 cohorts...", flush=True)
    cohorts_data = {}
    for cohort in ALL_COHORTS:
        if cohort == "PROTEAS-brain-mets":
            cohorts_data[cohort] = load_proteas()
        else:
            cohorts_data[cohort] = load_glioma_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])} patients/follow-ups",
              flush=True)

    all_results = []
    cohort_summary = {}
    for held_cohort in ALL_COHORTS:
        t0 = time.time()
        print(f"\n=== LOCO fold: held-out = {held_cohort} ===", flush=True)
        train_data = []
        for c in ALL_COHORTS:
            if c != held_cohort:
                train_data.extend(cohorts_data[c])
        test_data = cohorts_data[held_cohort]
        print(f"  train: {len(train_data)} patients (4 cohorts)", flush=True)
        print(f"  test:  {len(test_data)} patients (held-out: {held_cohort})", flush=True)

        model = DHEPL_UNet(base=24).to(DEVICE)
        train(model, train_data, SEED)
        rows = evaluate(model, test_data)
        for r in rows:
            r["fold_held_out"] = held_cohort
        all_results.extend(rows)
        del model; torch.cuda.empty_cache(); gc.collect()

        ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in rows]) * 100)
        learned_out = float(np.nanmean([r["learned_outgrowth"] for r in rows]) * 100)
        dhepl_out = float(np.nanmean([r["dhepl_outgrowth"] for r in rows]) * 100)
        ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in rows]) * 100)
        # Average DHEPL routing weights per held-out cohort
        avg_weights = {f"sigma_{s}": float(np.mean([r[f"weight_sigma_{s}"] for r in rows]))
                        for s in SIGMA_GRID}
        cohort_summary[held_cohort] = {
            "n": len(rows),
            "learned_outgrowth_pct": learned_out,
            "dhepl_outgrowth_pct": dhepl_out,
            "ensemble_outgrowth_pct": ens_out,
            "ensemble_overall_pct": ens_ovr,
            "avg_dhepl_weights": avg_weights,
        }
        print(f"  RESULT held-out {held_cohort}: "
              f"learned-out {learned_out:.2f}%  dhepl-out {dhepl_out:.2f}%  "
              f"ens-out {ens_out:.2f}%  ens-ovr {ens_ovr:.2f}%  "
              f"({time.time()-t0:.0f}s)", flush=True)
        print(f"  DHEPL avg weights on {held_cohort}: "
              f"{ {s: round(v, 3) for s, v in avg_weights.items()} }", flush=True)

    # Save per-patient CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_results:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader(); w.writerows(all_results)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    print(f"\n=== FINAL DHEPL UNIVERSAL FOUNDATION MODEL SUMMARY ===", flush=True)
    print(f"  {'Held-out':<22s} {'N':>4s} {'learn-out':>10s} {'dhepl-out':>10s} "
          f"{'ens-out':>10s} {'ens-ovr':>10s}", flush=True)
    for cohort in ALL_COHORTS:
        if cohort not in cohort_summary: continue
        s = cohort_summary[cohort]
        print(f"  {cohort:<22s} {s['n']:>4d} "
              f"{s['learned_outgrowth_pct']:>9.2f}% {s['dhepl_outgrowth_pct']:>9.2f}% "
              f"{s['ensemble_outgrowth_pct']:>9.2f}% {s['ensemble_overall_pct']:>9.2f}%",
              flush=True)

    metrics = ["learned_outgrowth_pct", "dhepl_outgrowth_pct",
               "ensemble_outgrowth_pct", "ensemble_overall_pct"]
    cohort_mean = {}
    print(f"\n  {'5-cohort MEAN':<22s} {'':>4s} ", end="", flush=True)
    for m in metrics:
        v = float(np.mean([cohort_summary[c][m] for c in ALL_COHORTS
                            if c in cohort_summary]))
        cohort_mean[m] = v
        print(f"{v:>9.2f}%", end=" ", flush=True)
    print(flush=True)

    # Comparison vs v156 fixed bimodal kernel
    v156 = {
        "UCSF-POSTOP": {"learned_out": 96.44, "ens_out": 97.18, "ens_ovr": 98.72},
        "MU-Glioma-Post": {"learned_out": 62.17, "ens_out": 70.96, "ens_ovr": 86.63},
        "RHUH-GBM": {"learned_out": 89.10, "ens_out": 89.34, "ens_ovr": 95.38},
        "LUMIERE": {"learned_out": 65.69, "ens_out": 72.05, "ens_ovr": 76.90},
        "PROTEAS-brain-mets": {"learned_out": 52.31, "ens_out": 72.16, "ens_ovr": 87.85},
    }
    print(f"\n=== COMPARISON: v157 DHEPL vs v156 fixed-bimodal ===", flush=True)
    print(f"  {'Cohort':<22s} {'metric':<10s} {'v156':>8s} {'v157':>8s} {'Δ (pp)':>8s}",
          flush=True)
    for c in ALL_COHORTS:
        s = cohort_summary[c]
        for metric, v157_key in [("learned-out", "learned_outgrowth_pct"),
                                    ("ens-out", "ensemble_outgrowth_pct"),
                                    ("ens-ovr", "ensemble_overall_pct")]:
            v156_key = "learned_out" if metric == "learned-out" else (
                "ens_out" if metric == "ens-out" else "ens_ovr")
            d = s[v157_key] - v156[c][v156_key]
            print(f"  {c:<22s} {metric:<10s} {v156[c][v156_key]:>7.2f}% "
                  f"{s[v157_key]:>7.2f}% {d:>+7.2f}", flush=True)

    out = {"version": "v157",
           "experiment": "DHEPL universal foundation model 5-fold LOCO",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "all_cohorts": ALL_COHORTS,
           "sigma_grid": SIGMA_GRID, "kernel_size": KERNEL_SIZE,
           "epochs": EPOCHS, "seed": SEED,
           "n_total_test_followups": len(all_results),
           "by_cohort": cohort_summary,
           "cohort_mean_pct": cohort_mean,
           "comparison_to_v156_fixed_bimodal": v156,
           }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
