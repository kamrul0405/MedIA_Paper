"""v179: Yale-Brain-Mets multi-seed zero-shot bootstrap.

Round 19, part 2.

Reproduces the v177 Yale 7th-cohort zero-shot evaluation under three
training seeds {42, 123, 999} and reports:
  - Per-seed Yale ensemble outgrowth coverage
  - Patient-level cluster-bootstrap 95% CI (10,000 resamples)
  - Across-seed mean +/- standard error

This bulletproofs the v177 Yale 78.71% finding against
single-seed-fluke risk (per the same protocol used for v159 -> v156).

Outputs:
  Nature_project/05_results/v179_yale_multiseed.json
  Nature_project/05_results/v179_yale_multiseed_per_patient.csv
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
YALE_DIR = Path(
    r"C:\Users\kamru\Downloads\Datasets\PKG - Yale-Brain-Mets-Longitudinal"
    r"\Yale-Brain-Mets-Longitudinal"
)
OUT_JSON = RESULTS / "v179_yale_multiseed.json"
OUT_CSV = RESULTS / "v179_yale_multiseed_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
TARGET_SHAPE = (16, 48, 48)
EPOCHS_PRETRAIN = 25
LR_PRETRAIN = 1e-3
SEEDS = [42, 123, 999]
YALE_MAX_PATIENTS = 200
N_BOOT = 10000


def heat_constant(mask, sigma):
    if mask.sum() == 0:
        return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0:
        h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma_broad)
    return np.maximum(persistence, h_broad)


def overall_coverage(future_mask, region_mask):
    fm = future_mask.astype(bool)
    if fm.sum() == 0:
        return float("nan")
    return float((fm & region_mask.astype(bool)).sum() / fm.sum())


def outgrowth_coverage(future_mask, baseline_mask, region_mask):
    fut = future_mask.astype(bool)
    base = baseline_mask.astype(bool)
    out = fut & (~base)
    if out.sum() == 0:
        return float("nan")
    return float((out & region_mask.astype(bool)).sum() / out.sum())


def resize_to_target(arr, target_shape):
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


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
        if not fr.exists():
            continue
        m = (np.load(fb) > 0).astype(np.float32)
        t = (np.load(fr) > 0).astype(np.float32)
        if m.sum() == 0 or t.sum() == 0:
            continue
        outgrowth = (t.astype(bool) & ~m.astype(bool)).astype(np.float32)
        heat = heat_bimodal(m, SIGMA_BROAD)
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth, "heat_bimodal": heat})
    return rows


def load_proteas():
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v179_") as td:
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
                        if baseline not in names:
                            continue
                        out_path = patient_tmp / Path(baseline).name
                        out_path.write_bytes(inner.read(baseline))
                        base_arr = np.asanyarray(nib.load(str(out_path)).dataobj).astype(np.float32)
                        base_mask = base_arr > 0
                        if base_mask.sum() == 0:
                            continue
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
                            if fu_mask.shape != base_mask.shape or not fu_mask.any():
                                continue
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
                    try:
                        nested_path.unlink()
                    except OSError:
                        pass
                if i % 20 == 0 or i == len(entries):
                    print(f"    {i}/{len(entries)} ({time.time()-t0:.0f}s)", flush=True)
    return rows


def proxy_mask_from_post(post_path, pre_path=None, percentile=98.0):
    post_img = nib.load(str(post_path))
    post = np.asanyarray(post_img.dataobj).astype(np.float32)
    robust_max = float(np.percentile(post, 99.5))
    if robust_max <= 0:
        return None
    brain = post > 0.01 * robust_max
    if not brain.any():
        return None
    if pre_path is not None and pre_path.exists():
        try:
            pre_img = nib.load(str(pre_path))
            pre = np.asanyarray(pre_img.dataobj).astype(np.float32)
            if pre.shape == post.shape:
                pre_max = float(np.percentile(pre[brain], 99.5))
                if pre_max > 0:
                    pre_norm = pre / pre_max * robust_max
                    diff = post - pre_norm
                    diff[~brain] = 0
                    th = np.percentile(diff[brain], percentile)
                    if th <= 0:
                        th = 1e-6
                    mask = (diff > th)
                    if mask.sum() < 30:
                        th2 = np.percentile(post[brain], percentile)
                        mask = (post > th2) & brain
                    return mask
        except Exception:
            pass
    th = np.percentile(post[brain], percentile)
    return (post > th) & brain


def find_yale_pairs(max_patients=YALE_MAX_PATIENTS):
    if not YALE_DIR.exists():
        return []
    pairs = []
    patients = sorted(p for p in YALE_DIR.iterdir() if p.is_dir())
    for p in patients[:max_patients * 3]:
        timepoints = sorted(t for t in p.iterdir() if t.is_dir())
        if len(timepoints) < 2:
            continue
        b_dir = timepoints[0]
        f_dir = timepoints[-1]
        b_post = next(b_dir.glob("*POST.nii.gz"), None)
        f_post = next(f_dir.glob("*POST.nii.gz"), None)
        if b_post is None or f_post is None:
            continue
        b_pre = next(b_dir.glob("*PRE.nii.gz"), None)
        f_pre = next(f_dir.glob("*PRE.nii.gz"), None)
        pairs.append((p.name, b_post, f_post, b_pre, f_pre))
        if len(pairs) >= max_patients:
            break
    return pairs


def load_yale(max_patients=YALE_MAX_PATIENTS):
    pairs = find_yale_pairs(max_patients)
    print(f"  Yale: found {len(pairs)} longitudinal pairs", flush=True)
    rows = []
    skipped = 0
    for i, (pid, b_post, f_post, b_pre, f_pre) in enumerate(pairs, 1):
        try:
            b_mask = proxy_mask_from_post(b_post, b_pre)
            f_mask = proxy_mask_from_post(f_post, f_pre)
        except Exception:
            skipped += 1
            continue
        if b_mask is None or f_mask is None:
            skipped += 1
            continue
        if b_mask.shape != f_mask.shape:
            skipped += 1
            continue
        if b_mask.sum() < 50 or f_mask.sum() < 50:
            skipped += 1
            continue
        m_r = resize_to_target(b_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        f_r = resize_to_target(f_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        if m_r.sum() < 5 or f_r.sum() < 5:
            skipped += 1
            continue
        outgrowth_r = f_r & ~m_r
        if outgrowth_r.sum() == 0:
            skipped += 1
            continue
        heat = heat_bimodal(m_r, SIGMA_BROAD)
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r.astype(np.float32),
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
            "heat_bimodal": heat,
        })
    print(f"    DONE: {len(rows)} usable Yale pairs (skipped {skipped})",
          flush=True)
    return rows


def train_unet(train_data, seed, epochs=EPOCHS_PRETRAIN, batch_size=4, lr=LR_PRETRAIN):
    torch.manual_seed(seed)
    np.random.seed(seed)
    n = len(train_data)
    X = np.stack([np.stack([d["mask"], d["heat_bimodal"]], axis=0)
                   for d in train_data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE)
    Yt = torch.from_numpy(Y).to(DEVICE)
    model = UNet3D(in_ch=2, base=24).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n)
        for i in range(0, n, batch_size):
            idx = perm[i:i+batch_size]
            xb = Xt[idx]
            yb = Yt[idx]
            logits = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
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


def cluster_bootstrap_ci(values, n_boot=N_BOOT, seed=42):
    rng = np.random.default_rng(seed)
    v = np.array([x for x in values if not np.isnan(x)])
    n = len(v)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, n, size=(n_boot, n))
    means = v[idx].mean(axis=1)
    return float(np.mean(v)), float(np.percentile(means, 2.5)), \
        float(np.percentile(means, 97.5))


def main():
    print("=" * 78, flush=True)
    print("v179 YALE MULTI-SEED ZERO-SHOT BOOTSTRAP", flush=True)
    print(f"  Seeds: {SEEDS}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading all 5 training cohorts...", flush=True)
    train_data = []
    for c in ALL_COHORTS:
        if c == "PROTEAS-brain-mets":
            rows = load_proteas()
        else:
            rows = load_glioma_cohort(c)
        print(f"  {c}: {len(rows)} patients", flush=True)
        train_data.extend(rows)
    print(f"  Total train n = {len(train_data)}", flush=True)

    print("\nLoading Yale longitudinal pairs...", flush=True)
    yale_data = load_yale(max_patients=YALE_MAX_PATIENTS)

    if not yale_data:
        print("ERROR: no usable Yale pairs", flush=True)
        return

    all_per_patient = []
    by_seed = {}
    for seed in SEEDS:
        print(f"\n--- SEED {seed} ---", flush=True)
        t0 = time.time()
        model = train_unet(train_data, seed=seed)
        print(f"  Training took {time.time()-t0:.0f}s", flush=True)
        per_patient = evaluate(model, yale_data)
        del model
        torch.cuda.empty_cache()
        gc.collect()

        learned = [r["learned_outgrowth"] for r in per_patient
                   if not np.isnan(r["learned_outgrowth"])]
        bimodal = [r["bimodal_outgrowth"] for r in per_patient
                   if not np.isnan(r["bimodal_outgrowth"])]
        ensemble = [r["ensemble_outgrowth"] for r in per_patient
                    if not np.isnan(r["ensemble_outgrowth"])]
        overall = [r["ensemble_overall"] for r in per_patient
                   if not np.isnan(r["ensemble_overall"])]

        m_lo = float(np.mean(learned)) if learned else float("nan")
        m_bi = float(np.mean(bimodal)) if bimodal else float("nan")
        m_en, ci_en_lo, ci_en_hi = cluster_bootstrap_ci(ensemble, seed=seed)
        m_ov, ci_ov_lo, ci_ov_hi = cluster_bootstrap_ci(overall, seed=seed)

        by_seed[str(seed)] = {
            "learned_outgrowth_pct": m_lo * 100,
            "bimodal_outgrowth_pct": m_bi * 100,
            "ensemble_outgrowth_pct": m_en * 100,
            "ensemble_outgrowth_ci_lo_pct": ci_en_lo * 100,
            "ensemble_outgrowth_ci_hi_pct": ci_en_hi * 100,
            "ensemble_overall_pct": m_ov * 100,
            "ensemble_overall_ci_lo_pct": ci_ov_lo * 100,
            "ensemble_overall_ci_hi_pct": ci_ov_hi * 100,
            "n_patients": len(ensemble),
        }
        print(f"  learned outgrowth        = {m_lo*100:.2f}%", flush=True)
        print(f"  bimodal outgrowth        = {m_bi*100:.2f}%", flush=True)
        print(f"  ensemble outgrowth       = {m_en*100:.2f}%   "
              f"95% CI [{ci_en_lo*100:.2f}, {ci_en_hi*100:.2f}]", flush=True)
        print(f"  ensemble overall         = {m_ov*100:.2f}%   "
              f"95% CI [{ci_ov_lo*100:.2f}, {ci_ov_hi*100:.2f}]", flush=True)

        for r in per_patient:
            r["seed"] = seed
        all_per_patient.extend(per_patient)

    # Across-seed aggregate
    seeds_means = {
        "learned_outgrowth_pct":
            [by_seed[str(s)]["learned_outgrowth_pct"] for s in SEEDS],
        "bimodal_outgrowth_pct":
            [by_seed[str(s)]["bimodal_outgrowth_pct"] for s in SEEDS],
        "ensemble_outgrowth_pct":
            [by_seed[str(s)]["ensemble_outgrowth_pct"] for s in SEEDS],
        "ensemble_overall_pct":
            [by_seed[str(s)]["ensemble_overall_pct"] for s in SEEDS],
    }
    print("\n=== Across-seed mean +/- SE (n_seeds = "
          f"{len(SEEDS)}) ===", flush=True)
    summary = {}
    for k, vals in seeds_means.items():
        v = np.array(vals)
        m = float(np.mean(v))
        se = float(np.std(v, ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0
        mn = float(np.min(v))
        mx = float(np.max(v))
        summary[k] = {"mean": m, "se": se, "min": mn, "max": mx,
                      "values": vals}
        print(f"  {k:35s} {m:.2f} +/- {se:.2f}   range [{mn:.2f}, {mx:.2f}]",
              flush=True)

    out = {
        "version": "v179",
        "experiment": "Yale-Brain-Mets-Longitudinal multi-seed zero-shot bootstrap",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seeds": SEEDS,
        "n_yale_eval": len(yale_data),
        "by_seed": by_seed,
        "summary_across_seeds": summary,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if all_per_patient:
        with OUT_CSV.open("w", newline="") as f:
            keys = list(all_per_patient[0].keys())
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(all_per_patient)
        print(f"Saved {OUT_CSV}", flush=True)


if __name__ == "__main__":
    main()
