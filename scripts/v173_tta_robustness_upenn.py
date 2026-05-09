"""v173: Test-time augmentation (TTA) robustness analysis on UPENN-GBM.

Trains the universal foundation model on 5 cohorts and applies 8
test-time augmentations to UPENN-GBM evaluation:
  - Original
  - Flip along D axis
  - Flip along H axis
  - Flip along W axis
  - Flip along (D, H)
  - Flip along (D, W)
  - Flip along (H, W)
  - Flip along (D, H, W)

For each augmentation, runs the foundation model and inverts the
augmentation on the predicted heat map. Final TTA prediction is the
mean across all 8 augmented predictions.

Reports:
  - Mean per-augmentation ensemble outgrowth (stability)
  - TTA-ensemble outgrowth (averaged) vs single-pass
  - Standard deviation across augmentations (per-patient stability)

Outputs:
    Nature_project/05_results/v173_tta_robustness_upenn.json
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
UPENN_NPZ = RESULTS / "upenn_cropped_masks.npz"
OUT_JSON = RESULTS / "v173_tta_robustness_upenn.json"
OUT_CSV = RESULTS / "v173_tta_robustness_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
SEED = 42
TARGET_SHAPE = (16, 48, 48)

# Augmentations: list of (axes_to_flip, name)
AUGMENTATIONS = [
    ([], "original"),
    ([0], "flip_D"),
    ([1], "flip_H"),
    ([2], "flip_W"),
    ([0, 1], "flip_DH"),
    ([0, 2], "flip_DW"),
    ([1, 2], "flip_HW"),
    ([0, 1, 2], "flip_DHW"),
]


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
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v173_") as td:
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


def load_upenn():
    if not UPENN_NPZ.exists(): return []
    data = np.load(UPENN_NPZ, allow_pickle=True)
    pids = data["pids"]
    base48 = data["base48"]
    rec48 = data["rec48"]
    rows = []
    for i, pid in enumerate(pids):
        m_2d = (base48[i] > 0).astype(np.float32)
        t_2d = (rec48[i] > 0).astype(np.float32)
        m_3d = np.tile(m_2d[None, :, :], (16, 1, 1))
        t_3d = np.tile(t_2d[None, :, :], (16, 1, 1))
        if m_3d.sum() == 0 or t_3d.sum() == 0: continue
        outgrowth_3d = (t_3d.astype(bool) & ~m_3d.astype(bool)).astype(np.float32)
        heat_3d = heat_bimodal(m_3d, SIGMA_BROAD)
        rows.append({
            "pid": str(pid), "cohort": "UPENN-GBM",
            "mask": m_3d.astype(np.float32),
            "fu": t_3d.astype(np.float32),
            "outgrowth": outgrowth_3d.astype(np.float32),
            "heat_bimodal": heat_3d,
        })
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
        if (ep + 1) % 5 == 0:
            print(f"    epoch {ep+1}/{epochs}: loss = "
                  f"{float(loss.item()):.4f}", flush=True)
    return model


def apply_aug(arr, axes):
    """Apply axis flips along given axes. Works for 3D or 4D arrays.
    Axis indexing: 0=D, 1=H, 2=W (treated as last 3 dims)."""
    out = arr
    for ax in axes:
        out = np.flip(out, axis=ax + (out.ndim - 3))
    return out.copy()


def evaluate_with_tta(model, test_data):
    model.eval()
    rows = []
    aug_mean_outgrowth = {name: [] for _, name in AUGMENTATIONS}
    with torch.no_grad():
        for d in test_data:
            # Per-augmentation predicted heat maps
            aug_heats = {}
            for axes, name in AUGMENTATIONS:
                m_aug = apply_aug(d["mask"], axes)
                heat_aug = apply_aug(d["heat_bimodal"], axes)
                x = np.stack([m_aug, heat_aug], axis=0).astype(np.float32)
                xt = torch.from_numpy(x[None]).to(DEVICE)
                logits = model(xt)
                pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
                # Invert the augmentation back to original coordinates
                pred_orig = apply_aug(pred, axes)
                aug_heats[name] = pred_orig
            # Per-augmentation outgrowth coverage (no TTA averaging)
            per_aug_outgrowth = {}
            for name, ph in aug_heats.items():
                pred_region = ph >= 0.5
                ens_heat = np.maximum(ph, d["heat_bimodal"])
                ens_region = ens_heat >= 0.5
                per_aug_outgrowth[name] = outgrowth_coverage(d["fu"], d["mask"],
                                                                ens_region)
                aug_mean_outgrowth[name].append(per_aug_outgrowth[name])

            # TTA-averaged prediction
            all_preds = np.stack(list(aug_heats.values()))
            tta_mean_pred = all_preds.mean(axis=0)
            tta_pred_region = tta_mean_pred >= 0.5
            tta_ens_heat = np.maximum(tta_mean_pred, d["heat_bimodal"])
            tta_ens_region = tta_ens_heat >= 0.5

            single_pass = aug_heats["original"]
            single_pred_region = single_pass >= 0.5
            single_ens_heat = np.maximum(single_pass, d["heat_bimodal"])
            single_ens_region = single_ens_heat >= 0.5

            # Per-patient stability: std of outgrowth coverage across augmentations
            aug_values = np.array([per_aug_outgrowth[n] for _, n in AUGMENTATIONS], dtype=float)
            patient_stability = float(np.nanstd(aug_values))

            row = {
                "pid": d["pid"], "cohort": d["cohort"],
                "single_pass_outgrowth": outgrowth_coverage(d["fu"], d["mask"],
                                                              single_ens_region),
                "tta_ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"],
                                                                tta_ens_region),
                "patient_stability_std": patient_stability,
                "aug_min": float(np.nanmin(aug_values)),
                "aug_max": float(np.nanmax(aug_values)),
            }
            for ax, name in AUGMENTATIONS:
                row[f"out_{name}"] = per_aug_outgrowth[name]
            rows.append(row)

    # Per-augmentation cohort means
    cohort_aug_means = {name: float(np.nanmean(vals) * 100)
                          for name, vals in aug_mean_outgrowth.items()}
    return rows, cohort_aug_means


def main():
    print("=" * 78, flush=True)
    print("v173 TEST-TIME AUGMENTATION (TTA) ROBUSTNESS ON UPENN-GBM", flush=True)
    print(f"  8 augmentations (3-axis flip combinations)", flush=True)
    print(f"  device: {DEVICE}; epochs={EPOCHS}; seed={SEED}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading 5 training cohorts + UPENN test...", flush=True)
    train_data = []
    for cohort in ALL_COHORTS:
        if cohort == "PROTEAS-brain-mets":
            rows = load_proteas()
        else:
            rows = load_glioma_cohort(cohort)
        train_data.extend(rows)
        print(f"  {cohort}: {len(rows)}", flush=True)
    upenn_data = load_upenn()
    print(f"  UPENN: {len(upenn_data)}", flush=True)

    print(f"\n=== Training universal foundation model ===", flush=True)
    t0 = time.time()
    model = train_unet(train_data, SEED)
    print(f"  done in {time.time()-t0:.0f}s", flush=True)

    print(f"\n=== Evaluating with 8-augmentation TTA on UPENN ===", flush=True)
    t0 = time.time()
    rows, aug_means = evaluate_with_tta(model, upenn_data)
    print(f"  TTA eval done in {time.time()-t0:.0f}s", flush=True)

    single = float(np.nanmean([r["single_pass_outgrowth"] for r in rows]) * 100)
    tta = float(np.nanmean([r["tta_ensemble_outgrowth"] for r in rows]) * 100)
    stability = float(np.nanmean([r["patient_stability_std"] for r in rows]))

    print(f"\n=== UPENN TTA results (n={len(rows)}) ===", flush=True)
    print(f"  Single-pass ensemble outgrowth: {single:.2f}%", flush=True)
    print(f"  TTA-ensemble outgrowth: {tta:.2f}% (Diff {tta - single:+.2f} pp)",
          flush=True)
    print(f"  Mean per-patient stability (std across 8 augs): {stability:.4f}",
          flush=True)
    print(f"\n  Per-augmentation cohort-mean ensemble outgrowth:", flush=True)
    for name in [n for _, n in AUGMENTATIONS]:
        print(f"    {name:<14s}: {aug_means[name]:5.2f}%", flush=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    out = {"version": "v173",
           "experiment": "Test-time augmentation robustness on UPENN-GBM",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "n_test": len(rows),
           "augmentations": [name for _, name in AUGMENTATIONS],
           "single_pass_ens_out_pct": single,
           "tta_ensemble_ens_out_pct": tta,
           "tta_minus_single_pp": tta - single,
           "mean_patient_stability_std": stability,
           "per_aug_cohort_mean_pct": aug_means,
           }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
