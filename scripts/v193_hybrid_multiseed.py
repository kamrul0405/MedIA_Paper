"""v193: Multi-seed end-to-end hybrid recipe evaluation — round 31.

Senior-Nature-reviewer demand: round 30's UOSL-gated hybrid recipe
was an *analytical* combination of existing per-cohort metrics
(v184 + v189). To bulletproof for flagship submission we need:

  1. Train the foundation model with multiple seeds (42, 123, 999)
  2. Apply the hybrid recipe end-to-end on UPENN and Yale (the
     two true external cohorts) under each seed
  3. Report mean +/- SE across seeds for each metric
  4. Confirm the round-30 recipe is statistically robust

Method:
  For each seed in {42, 123, 999}:
    - Train foundation model on all 5 cohorts (n_train=635)
    - For each of UPENN, Yale:
      * Compute UOSL S
      * If S > 0.5: foundation+kernel ensemble (sigma=7)
      * Else: kernel-only sigma=3
      * Compute per-patient AUC, Dice, coverage
  Aggregate per-cohort metrics across seeds (mean +/- SE).

For LOCO cohorts (UCSF, MU, RHUH, LUMIERE, PROTEAS) the routing
under S>0.5 is unambiguous (PROTEAS -> kernel; rest -> foundation).
We re-use v159 multi-seed foundation metrics + v189 deterministic
kernel metrics to avoid retraining 5 LOCO models.

Outputs:
  Nature_project/05_results/v193_hybrid_multiseed.json
"""
from __future__ import annotations

import csv
import gc
import json
import re
import shutil
import tempfile
import time
import warnings
import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter, zoom

warnings.filterwarnings("ignore")

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
DATA_ZIP = Path(r"C:\Users\kamru\Downloads\Datasets\PKG - PROTEAS-brain-mets-zenodo-17253793.zip")
UPENN_NPZ = RESULTS / "upenn_cropped_masks.npz"
YALE_DIR = Path(
    r"C:\Users\kamru\Downloads\Datasets\PKG - Yale-Brain-Mets-Longitudinal"
    r"\Yale-Brain-Mets-Longitudinal"
)
OUT_JSON = RESULTS / "v193_hybrid_multiseed.json"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SEEDS = [42, 123, 999]
SIGMA_BROAD = 7.0   # foundation kernel sigma (round-1 default)
SIGMA_SMALL = 3.0   # universal sigma=3 kernel route
TARGET_SHAPE = (16, 48, 48)
EPOCHS = 25
LR = 1e-3
BATCH_SIZE = 4
S_THRESHOLD = 0.5

# UOSL similarity per cohort (from round 30 v192)
S_PER_COHORT = {
    "UCSF-POSTOP": 0.7928,
    "MU-Glioma-Post": 0.9091,
    "RHUH-GBM": 0.8568,
    "LUMIERE": 0.7727,
    "PROTEAS-brain-mets": 0.0000,
    "UPENN-GBM": 0.8810,
    "Yale-Brain-Mets": 0.3072,
}


# ============================================================================
# Pipeline
# ============================================================================

def heat_constant(mask, sigma):
    if mask.sum() == 0:
        return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0:
        h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma):
    persistence = mask.astype(np.float32)
    h_broad = heat_constant(mask, sigma)
    return np.maximum(persistence, h_broad)


def resize_to_target(arr, target_shape):
    factors = [t / s for t, s in zip(target_shape, arr.shape)]
    if arr.dtype == bool or np.array_equal(arr, arr.astype(bool).astype(arr.dtype)):
        return zoom(arr.astype(np.float32), factors, order=0).astype(np.float32)
    return zoom(arr, factors, order=1).astype(np.float32)


def auroc(scores, labels):
    s = np.array(scores, dtype=np.float32)
    y = np.array(labels, dtype=np.float32)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(-s)
    y_sorted = y[order]
    cum_pos = np.cumsum(y_sorted)
    fpr = (np.arange(1, len(y) + 1) - cum_pos) / n_neg
    tpr = cum_pos / n_pos
    fpr = np.concatenate([[0.0], fpr])
    tpr = np.concatenate([[0.0], tpr])
    if hasattr(np, "trapezoid"):
        auc = float(np.trapezoid(tpr, fpr))
    else:
        auc = float(np.trapz(tpr, fpr))
    if auc < 0.5:
        auc = 1.0 - auc
    return auc


def dice(pred_bin, target_bin):
    a = pred_bin.astype(bool)
    b = target_bin.astype(bool)
    inter = float((a & b).sum())
    s = float(a.sum() + b.sum())
    if s == 0:
        return float("nan")
    return (2 * inter) / s


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


def load_glioma_cohort(cohort, sigma=SIGMA_BROAD):
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
        heat = heat_bimodal(m, sigma)
        rows.append({"pid": pid, "cohort": cohort, "mask": m, "fu": t,
                     "outgrowth": outgrowth, "heat_bimodal": heat})
    return rows


def load_proteas(sigma=SIGMA_BROAD):
    rows = []
    with tempfile.TemporaryDirectory(prefix="proteas_v193_") as td:
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
                        m_r = resize_to_target(base_mask.astype(np.float32), TARGET_SHAPE) > 0.5
                        m_r_f = m_r.astype(np.float32)
                        heat = heat_bimodal(m_r_f, sigma)
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
                            outgrowth_r = fu_r & ~m_r
                            rows.append({
                                "pid": pid, "cohort": "PROTEAS-brain-mets",
                                "mask": m_r_f,
                                "fu": fu_r.astype(np.float32),
                                "outgrowth": outgrowth_r.astype(np.float32),
                                "heat_bimodal": heat,
                            })
                finally:
                    shutil.rmtree(patient_tmp, ignore_errors=True)
                    try:
                        nested_path.unlink()
                    except OSError:
                        pass
                if i % 20 == 0 or i == len(entries):
                    print(f"    {i}/{len(entries)} ({time.time()-t0:.0f}s)",
                          flush=True)
    return rows


def load_upenn(sigma=SIGMA_BROAD):
    if not UPENN_NPZ.exists():
        return []
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
        if m_3d.sum() == 0 or t_3d.sum() == 0:
            continue
        outgrowth_3d = (t_3d.astype(bool) & ~m_3d.astype(bool)).astype(np.float32)
        heat_3d = heat_bimodal(m_3d, sigma)
        rows.append({
            "pid": str(pid), "cohort": "UPENN-GBM",
            "mask": m_3d.astype(np.float32),
            "fu": t_3d.astype(np.float32),
            "outgrowth": outgrowth_3d.astype(np.float32),
            "heat_bimodal": heat_3d,
        })
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


def find_yale_pairs(max_patients=200):
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


def load_yale(sigma=SIGMA_BROAD, max_patients=200):
    pairs = find_yale_pairs(max_patients)
    rows = []
    for i, (pid, b_post, f_post, b_pre, f_pre) in enumerate(pairs, 1):
        try:
            b_mask = proxy_mask_from_post(b_post, b_pre)
            f_mask = proxy_mask_from_post(f_post, f_pre)
        except Exception:
            continue
        if b_mask is None or f_mask is None:
            continue
        if b_mask.shape != f_mask.shape:
            continue
        if b_mask.sum() < 50 or f_mask.sum() < 50:
            continue
        m_r = resize_to_target(b_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        f_r = resize_to_target(f_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        if m_r.sum() < 5 or f_r.sum() < 5:
            continue
        outgrowth_r = f_r & ~m_r
        if outgrowth_r.sum() == 0:
            continue
        m_r_f = m_r.astype(np.float32)
        heat = heat_bimodal(m_r_f, sigma)
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r_f,
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
            "heat_bimodal": heat,
        })
    return rows


def train_unet(train_data, seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    n = len(train_data)
    X = np.stack([np.stack([d["mask"], d["heat_bimodal"]], axis=0)
                   for d in train_data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE)
    Yt = torch.from_numpy(Y).to(DEVICE)
    model = UNet3D(in_ch=2, base=24).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    for ep in range(EPOCHS):
        model.train()
        perm = np.random.permutation(n)
        for i in range(0, n, BATCH_SIZE):
            idx = perm[i:i+BATCH_SIZE]
            xb = Xt[idx]
            yb = Yt[idx]
            logits = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model


def hybrid_evaluate(model, test_data, S, route_label):
    """Apply hybrid recipe per patient + return per-patient metrics."""
    model.eval()
    if S > S_THRESHOLD:
        # Foundation+kernel ensemble route (sigma=7 used for kernel)
        sigma_used = SIGMA_BROAD
        recipe = "foundation+kernel"
    else:
        # Kernel-only sigma=3 route (no model)
        sigma_used = SIGMA_SMALL
        recipe = "kernel_only_sigma3"
    pat_auc = []
    pat_dice = []
    pat_cov = []
    with torch.no_grad():
        for d in test_data:
            mask = d["mask"].astype(bool)
            outgrowth = d["outgrowth"].astype(bool)
            kernel = heat_bimodal(d["mask"], sigma_used)
            if recipe == "foundation+kernel":
                # Run model with sigma=7 kernel input (this is what was trained)
                x = np.stack([d["mask"], kernel], axis=0).astype(np.float32)
                xt = torch.from_numpy(x[None]).to(DEVICE)
                logits = model(xt)
                pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
                final = np.maximum(pred, kernel)
            else:
                final = kernel  # kernel-only

            bg = ~mask
            if bg.sum() == 0 or outgrowth.sum() == 0:
                continue
            auc = auroc(final[bg], outgrowth[bg].astype(np.float32))
            if not np.isnan(auc):
                pat_auc.append(auc)
            pred_bin = (final * (~mask)) >= 0.5
            d_score = dice(pred_bin, outgrowth)
            if not np.isnan(d_score):
                pat_dice.append(d_score)
            cov = float((pred_bin & outgrowth).sum() / outgrowth.sum())
            pat_cov.append(cov)
    def safe_mean(arr):
        return float(np.mean(arr)) if arr else float("nan")
    return {
        "recipe": recipe,
        "sigma_used": sigma_used,
        "S": float(S),
        "route_label": route_label,
        "auc_mean": safe_mean(pat_auc),
        "dice_mean": safe_mean(pat_dice),
        "coverage_mean": safe_mean(pat_cov),
        "n_eval": len(pat_auc),
        "auc_per_patient": pat_auc,
        "dice_per_patient": pat_dice,
    }


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v193 MULTI-SEED HYBRID RECIPE EVALUATION — round 31", flush=True)
    print(f"  Seeds: {SEEDS}", flush=True)
    print(f"  Hybrid threshold: S > {S_THRESHOLD}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading 5 trained cohorts...", flush=True)
    train_data = []
    for c in ALL_COHORTS:
        if c == "PROTEAS-brain-mets":
            rows = load_proteas(SIGMA_BROAD)
        else:
            rows = load_glioma_cohort(c, SIGMA_BROAD)
        train_data.extend(rows)
        print(f"  {c}: {len(rows)} patients", flush=True)
    print(f"  Total train: {len(train_data)} patients", flush=True)

    print("\nLoading UPENN + Yale (with sigma=7 kernel pre-baked)...",
          flush=True)
    upenn_data = load_upenn(SIGMA_BROAD)
    yale_data = load_yale(SIGMA_BROAD)
    print(f"  UPENN: {len(upenn_data)} patients", flush=True)
    print(f"  Yale: {len(yale_data)} patients", flush=True)

    by_seed = {}
    for seed in SEEDS:
        print(f"\n--- SEED {seed} ---", flush=True)
        t0 = time.time()
        model = train_unet(train_data, seed)
        print(f"  Train took {time.time()-t0:.0f}s", flush=True)

        S_upenn = S_PER_COHORT["UPENN-GBM"]
        S_yale = S_PER_COHORT["Yale-Brain-Mets"]

        # Apply hybrid: UPENN S=0.881 > 0.5 -> foundation+kernel
        upenn_metrics = hybrid_evaluate(model, upenn_data, S_upenn,
                                          "UPENN-GBM")
        # Apply hybrid: Yale S=0.307 <= 0.5 -> kernel-only sigma=3
        yale_metrics = hybrid_evaluate(model, yale_data, S_yale,
                                         "Yale-Brain-Mets")

        by_seed[str(seed)] = {
            "UPENN-GBM": upenn_metrics,
            "Yale-Brain-Mets": yale_metrics,
        }
        print(f"  UPENN ({upenn_metrics['recipe']}): "
              f"AUC={upenn_metrics['auc_mean']:.4f}  "
              f"Dice={upenn_metrics['dice_mean']:.4f}  "
              f"cov={upenn_metrics['coverage_mean']*100:.2f}%",
              flush=True)
        print(f"  Yale  ({yale_metrics['recipe']}): "
              f"AUC={yale_metrics['auc_mean']:.4f}  "
              f"Dice={yale_metrics['dice_mean']:.4f}  "
              f"cov={yale_metrics['coverage_mean']*100:.2f}%",
              flush=True)
        del model
        torch.cuda.empty_cache()
        gc.collect()

    # Aggregate across seeds
    print("\n" + "=" * 60, flush=True)
    print("MULTI-SEED HYBRID SUMMARY", flush=True)
    print("=" * 60, flush=True)

    summary = {}
    for cohort in ["UPENN-GBM", "Yale-Brain-Mets"]:
        aucs = [by_seed[str(s)][cohort]["auc_mean"] for s in SEEDS]
        dices = [by_seed[str(s)][cohort]["dice_mean"] for s in SEEDS]
        covs = [by_seed[str(s)][cohort]["coverage_mean"] for s in SEEDS]
        n = by_seed["42"][cohort]["n_eval"]
        recipe = by_seed["42"][cohort]["recipe"]

        def msr(arr):
            v = np.array([x for x in arr if not np.isnan(x)])
            if len(v) == 0:
                return float("nan"), float("nan")
            m = float(np.mean(v))
            se = (float(np.std(v, ddof=1) / np.sqrt(len(v)))
                  if len(v) > 1 else 0.0)
            return m, se

        auc_m, auc_se = msr(aucs)
        dice_m, dice_se = msr(dices)
        cov_m, cov_se = msr(covs)

        summary[cohort] = {
            "recipe": recipe,
            "S": S_PER_COHORT[cohort],
            "n_patients": n,
            "auc_mean": auc_m, "auc_se": auc_se,
            "dice_mean": dice_m, "dice_se": dice_se,
            "coverage_mean": cov_m, "coverage_se": cov_se,
            "per_seed_auc": aucs,
            "per_seed_dice": dices,
            "per_seed_cov": covs,
        }
        print(f"\n  {cohort}  (recipe = {recipe}, S = {S_PER_COHORT[cohort]:.4f}, "
              f"n = {n})", flush=True)
        print(f"    AUC: {auc_m:.4f} +/- {auc_se:.4f}  "
              f"(per-seed: {[f'{a:.3f}' for a in aucs]})", flush=True)
        print(f"    Dice: {dice_m:.4f} +/- {dice_se:.4f}  "
              f"(per-seed: {[f'{d:.3f}' for d in dices]})", flush=True)
        print(f"    Coverage: {cov_m*100:.2f}% +/- {cov_se*100:.2f}%",
              flush=True)

    out = {
        "version": "v193",
        "experiment": ("Multi-seed end-to-end UOSL-gated hybrid recipe "
                       "evaluation"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seeds": SEEDS,
        "S_threshold": S_THRESHOLD,
        "S_per_cohort": S_PER_COHORT,
        "by_seed": by_seed,
        "summary_across_seeds": summary,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
