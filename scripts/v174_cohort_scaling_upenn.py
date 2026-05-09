"""v174: Training-cohort-scaling law on UPENN external.

For each N in {1, 2, 3, 4, 5}, train a foundation model on the
first N cohorts (incrementally adding UCSF, MU, RHUH, LUMIERE,
PROTEAS) and evaluate on UPENN-GBM (external held-out).

Maps the 'training cohort diversity -> external generalisation'
scaling curve.

Outputs:
    Nature_project/05_results/v174_cohort_scaling_upenn.json
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
OUT_JSON = RESULTS / "v174_cohort_scaling_upenn.json"
OUT_CSV = RESULTS / "v174_cohort_scaling_upenn_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Order in which cohorts are added (largest first for stability)
COHORT_ORDER = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
                "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
SEED = 42
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
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v174_") as td:
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
    return model


def evaluate(model, test_data):
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
                "pid": d["pid"], "cohort": d["cohort"],
                "learned_outgrowth": outgrowth_coverage(d["fu"], d["mask"], pred_region),
                "bimodal_outgrowth": outgrowth_coverage(d["fu"], d["mask"], bimodal_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
            })
    return rows


def main():
    print("=" * 78, flush=True)
    print("v174 TRAINING-COHORT-SCALING LAW ON UPENN EXTERNAL", flush=True)
    print(f"  Cohort order: {COHORT_ORDER}", flush=True)
    print(f"  Test: UPENN-GBM (always external)", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading all 5 cohorts...", flush=True)
    cohorts_data = {}
    for cohort in COHORT_ORDER:
        if cohort == "PROTEAS-brain-mets":
            cohorts_data[cohort] = load_proteas()
        else:
            cohorts_data[cohort] = load_glioma_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])}", flush=True)

    print(f"\nLoading UPENN-GBM external test...", flush=True)
    upenn_data = load_upenn()
    print(f"  UPENN: {len(upenn_data)}", flush=True)

    all_results = []
    summary = {}
    for n in [1, 2, 3, 4, 5]:
        t0 = time.time()
        train_cohorts = COHORT_ORDER[:n]
        train_data = []
        for c in train_cohorts:
            train_data.extend(cohorts_data[c])
        print(f"\n=== N={n} cohorts: {train_cohorts} (total n={len(train_data)}) ===",
              flush=True)
        model = train_unet(train_data, SEED)
        rows = evaluate(model, upenn_data)
        for r in rows:
            r["n_train_cohorts"] = n
            r["train_cohorts"] = "+".join(train_cohorts)
        all_results.extend(rows)

        ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in rows]) * 100)
        ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in rows]) * 100)
        learned_out = float(np.nanmean([r["learned_outgrowth"] for r in rows]) * 100)
        bim_out = float(np.nanmean([r["bimodal_outgrowth"] for r in rows]) * 100)
        summary[n] = {
            "n_train_cohorts": n,
            "train_cohorts": train_cohorts,
            "n_train_patients": len(train_data),
            "n_test_upenn": len(rows),
            "learned_outgrowth_pct": learned_out,
            "bimodal_outgrowth_pct": bim_out,
            "ensemble_outgrowth_pct": ens_out,
            "ensemble_overall_pct": ens_ovr,
            "time_s": time.time() - t0,
        }
        print(f"  N={n} (n_train={len(train_data)}): UPENN learned-out {learned_out:.2f}% "
              f"bim-out {bim_out:.2f}% ens-out {ens_out:.2f}% ens-ovr {ens_ovr:.2f}% "
              f"({time.time()-t0:.0f}s)", flush=True)
        del model; torch.cuda.empty_cache(); gc.collect()

    # Save per-patient CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_results:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader(); w.writerows(all_results)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    # Final summary
    print(f"\n=== Training-cohort-scaling on UPENN external ===", flush=True)
    print(f"  {'N':<3s} {'cohorts':<60s} {'n_train':<8s} {'ens-out':>10s} "
          f"{'ens-ovr':>10s}", flush=True)
    for n in [1, 2, 3, 4, 5]:
        s = summary[n]
        cohort_str = " + ".join(s["train_cohorts"])
        print(f"  {n:<3d} {cohort_str:<60s} {s['n_train_patients']:<8d} "
              f"{s['ensemble_outgrowth_pct']:>9.2f}% "
              f"{s['ensemble_overall_pct']:>9.2f}%", flush=True)

    out = {"version": "v174",
           "experiment": "Training-cohort-scaling law on UPENN external",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "cohort_order": COHORT_ORDER,
           "test_cohort": "UPENN-GBM",
           "by_n": summary,
           }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
