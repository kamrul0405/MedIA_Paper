"""v177: Refined Universal Outgrowth Scaling Law (UOSL v2).

v176 fit UOSL only on v174 (5 data points where N varies and S is
nearly constant, ~0.88-0.93). Out-of-sample RMSE on v159 LOCO was
19 pp because v174 cannot constrain the S-dependence.

v177 fixes this by:
  (a) jointly fitting on v174 (N varies) + v159 LOCO (S varies)
      --> 10 data points spanning both axes;
  (b) replacing the unbounded exponent beta with a physically
      motivated sigmoid form:

          P(N_eff) = P_0 + (P_inf - P_0) * sigmoid(a * (N_eff - n_c))

      where the effective training count is

          N_eff = log(1 + n_train) * S

      which captures both Kaplan-McCandlish log-scale dataset
      effects AND distribution-match effects in a single feature.

  (c) Including PROTEAS in the final foundation-model training and
      loosening Yale proxy-mask filtering to get more usable
      longitudinal pairs (~30+ instead of 2).

Outputs:
  Nature_project/05_results/v177_uosl_refined.json
  Nature_project/05_results/v177_uosl_yale_per_patient.csv
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
from scipy.optimize import curve_fit

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
DATA_ZIP = Path(r"C:\Users\kamru\Downloads\Datasets\PKG - PROTEAS-brain-mets-zenodo-17253793.zip")
UPENN_NPZ = RESULTS / "upenn_cropped_masks.npz"
YALE_DIR = Path(
    r"C:\Users\kamru\Downloads\Datasets\PKG - Yale-Brain-Mets-Longitudinal"
    r"\Yale-Brain-Mets-Longitudinal"
)
OUT_JSON = RESULTS / "v177_uosl_refined.json"
YALE_CSV = RESULTS / "v177_uosl_yale_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
TARGET_SHAPE = (16, 48, 48)
SEED = 42
EPOCHS_PRETRAIN = 25
LR_PRETRAIN = 1e-3
YALE_MAX_PATIENTS = 200   # try harder to harvest pairs

DISEASE_VEC = {
    "UCSF-POSTOP":         np.array([0.7, 0.3, 0.0]),
    "MU-Glioma-Post":      np.array([0.7, 0.3, 0.0]),
    "RHUH-GBM":            np.array([1.0, 0.0, 0.0]),
    "LUMIERE":             np.array([0.4, 0.6, 0.0]),
    "PROTEAS-brain-mets":  np.array([0.0, 0.0, 1.0]),
    "UPENN-GBM":           np.array([1.0, 0.0, 0.0]),
    "Yale-Brain-Mets":     np.array([0.0, 0.0, 1.0]),
}


# ============================================================================
# Helpers (re-used)
# ============================================================================

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


def cohort_weighted_distribution(train_cohorts, n_per_cohort):
    total = sum(n_per_cohort.get(c, 0) for c in train_cohorts)
    if total == 0:
        return np.zeros(3)
    avg = np.zeros(3)
    for c in train_cohorts:
        n = n_per_cohort.get(c, 0)
        avg += (n / total) * DISEASE_VEC[c]
    return avg


def similarity_index(train_dist, test_cohort):
    test = DISEASE_VEC[test_cohort]
    nt = np.linalg.norm(train_dist)
    nT = np.linalg.norm(test)
    if nt == 0 or nT == 0:
        return 0.0
    return float(np.dot(train_dist, test) / (nt * nT))


# ============================================================================
# UOSL v2 (Sigmoid form)
# ============================================================================

def uosl_v2(features, p_0, p_inf, a, n_c):
    """P(N_eff) = p_0 + (p_inf - p_0) * sigmoid(a * (N_eff - n_c))

    where N_eff = log(1 + n_train) * S
    """
    n_train, S = features
    N_eff = np.log1p(n_train) * S
    return p_0 + (p_inf - p_0) / (1.0 + np.exp(-a * (N_eff - n_c)))


# ============================================================================
# Data loaders
# ============================================================================

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
    with tempfile.TemporaryDirectory(prefix="proteas_v177_") as td:
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
    """Generate a coarse tumour proxy mask from a T1c POST-contrast volume."""
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
    t0 = time.time()
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
        if i % 25 == 0:
            print(f"    {i}/{len(pairs)} ({time.time()-t0:.0f}s) "
                  f"-> {len(rows)} usable, {skipped} skipped", flush=True)
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


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v177 REFINED UNIVERSAL OUTGROWTH SCALING LAW (UOSL v2)", flush=True)
    print("  P = P_0 + (P_inf - P_0) * sigmoid(a * (N_eff - n_c))", flush=True)
    print("  N_eff = log(1 + n_train) * S", flush=True)
    print("=" * 78, flush=True)

    # ---------- 1) build training table from v174 + v159 ----------
    v174_path = RESULTS / "v174_cohort_scaling_upenn.json"
    v174 = json.loads(v174_path.read_text())
    n_per_cohort = {}
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]

    fit_n_train, fit_S, fit_P, fit_label = [], [], [], []
    # v174: 5 datapoints (varying N on UPENN)
    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        N = int(n_str)
        train_dist = cohort_weighted_distribution(row["train_cohorts"],
                                                   n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        P = row["ensemble_outgrowth_pct"] / 100.0
        fit_n_train.append(row["n_train_patients"])
        fit_S.append(S)
        fit_P.append(P)
        fit_label.append(f"v174 N={N}->UPENN")

    # v159 LOCO: 5 datapoints (varying held-out cohort, N=4 always)
    v159 = json.loads((RESULTS / "v159_multiseed_v156.json").read_text())
    for held_out, stats in v159["by_cohort"].items():
        train_cohorts = [c for c in ALL_COHORTS if c != held_out]
        train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
        S = similarity_index(train_dist, held_out)
        P = stats["ensemble_outgrowth_mean"] / 100.0
        n_tr = sum(n_per_cohort[c] for c in train_cohorts)
        fit_n_train.append(n_tr)
        fit_S.append(S)
        fit_P.append(P)
        fit_label.append(f"v159 LOCO held={held_out}")

    fit_n_train = np.array(fit_n_train, dtype=float)
    fit_S = np.array(fit_S, dtype=float)
    fit_P = np.array(fit_P, dtype=float)
    print(f"\nFitting UOSL v2 on {len(fit_P)} datapoints (v174 + v159)",
          flush=True)
    for lbl, nt, S, P in zip(fit_label, fit_n_train, fit_S, fit_P):
        print(f"  {lbl:35s}  n_train={int(nt):4d}  S={S:.4f}  P={P:.4f}",
              flush=True)

    # initial guess + bounds
    p0 = [0.5, 1.0, 1.0, 4.0]
    bounds = ([0.0, 0.5, 0.01, 0.0], [0.95, 1.0, 50.0, 20.0])
    popt, pcov = curve_fit(uosl_v2, (fit_n_train, fit_S), fit_P,
                            p0=p0, bounds=bounds, maxfev=50000)
    p_0, p_inf, a, n_c = popt
    pred_fit = uosl_v2((fit_n_train, fit_S), *popt)
    rmse_fit = float(np.sqrt(np.mean((pred_fit - fit_P) ** 2)))
    r_fit = float(np.corrcoef(pred_fit, fit_P)[0, 1])
    print(f"\nUOSL v2 fit:", flush=True)
    print(f"  P_0={p_0:.4f} P_inf={p_inf:.4f} a={a:.4f} n_c={n_c:.4f}",
          flush=True)
    print(f"  RMSE = {rmse_fit:.4f}  r = {r_fit:.4f}", flush=True)
    for lbl, P_obs, P_pred in zip(fit_label, fit_P, pred_fit):
        print(f"  {lbl:35s}  obs={P_obs:.4f} pred={P_pred:.4f} "
              f"err={abs(P_obs - P_pred)*100:.2f} pp", flush=True)

    # ---------- 2) Out-of-sample validation: v152 / v166 / v172 ----------
    validations = []

    def add_val(name, n_train, S, P_obs, source):
        P_pred = float(uosl_v2((np.array([n_train]),
                                 np.array([S])), *popt)[0])
        validations.append({
            "name": name, "n_train": int(n_train), "S": float(S),
            "P_observed": float(P_obs), "P_predicted": P_pred,
            "abs_err_pp": float(abs(P_obs - P_pred) * 100),
            "source": source,
        })

    v166_path = RESULTS / "v166_upenn_external_validation.json"
    if v166_path.exists():
        v166 = json.loads(v166_path.read_text())
        for k in ("ensemble_outgrowth_pct", "ensemble_outgrowth"):
            if k in v166:
                P_obs = v166[k] / (100.0 if v166[k] > 1 else 1.0)
                td = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
                S = similarity_index(td, "UPENN-GBM")
                n_tr = sum(n_per_cohort[c] for c in ALL_COHORTS)
                add_val("v166 UPENN external (5-cohort)", n_tr, S,
                        P_obs, "v166_upenn_external_validation.json")
                break

    v172_path = RESULTS / "v172_few_shot_upenn.json"
    if v172_path.exists():
        v172 = json.loads(v172_path.read_text())
        if "by_n" in v172 and "0" in v172["by_n"]:
            row = v172["by_n"]["0"]
            for k in ("ensemble_outgrowth_pct", "ensemble_outgrowth_mean_pct"):
                if k in row:
                    P_obs = row[k] / 100.0
                    td = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
                    S = similarity_index(td, "UPENN-GBM")
                    n_tr = sum(n_per_cohort[c] for c in ALL_COHORTS)
                    add_val("v172 zero-shot UPENN (N_local=0)",
                            n_tr, S, P_obs, "v172_few_shot_upenn.json")
                    break

    print(f"\nUOSL v2 out-of-sample validations: {len(validations)} points",
          flush=True)
    for v in validations:
        print(f"  {v['name']:50s}  n_tr={v['n_train']:4d} S={v['S']:.3f}  "
              f"obs={v['P_observed']:.4f} pred={v['P_predicted']:.4f}  "
              f"err={v['abs_err_pp']:.2f} pp", flush=True)

    if len(validations) >= 2:
        P_obs_v = np.array([v["P_observed"] for v in validations])
        P_pred_v = np.array([v["P_predicted"] for v in validations])
        rmse_val = float(np.sqrt(np.mean((P_obs_v - P_pred_v) ** 2)))
    else:
        rmse_val = float("nan")

    # ---------- 3) Yale extension with full 5-cohort foundation model ----------
    print("\n" + "=" * 60, flush=True)
    print("Yale-Brain-Mets-Longitudinal extension (full 5-cohort)", flush=True)
    print("=" * 60, flush=True)

    yale_data = load_yale(max_patients=YALE_MAX_PATIENTS)

    yale_pred = float("nan")
    yale_obs_pct = float("nan")
    yale_per_patient = []
    if len(yale_data) > 0:
        td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
        S_yale = similarity_index(td_full, "Yale-Brain-Mets")
        n_tr_full = sum(n_per_cohort[c] for c in ALL_COHORTS)
        yale_pred = float(uosl_v2((np.array([n_tr_full]),
                                     np.array([S_yale])), *popt)[0])
        print(f"\n  Yale similarity index S = {S_yale:.4f}", flush=True)
        print(f"  UOSL v2 prediction (n_train={n_tr_full}, S={S_yale:.4f}): "
              f"P_yale_pred = {yale_pred*100:.2f}%", flush=True)

        # Train universal foundation on ALL 5 cohorts (incl. PROTEAS)
        print(f"\n  Loading all 5 cohorts (including PROTEAS)...", flush=True)
        train_data = []
        for c in ALL_COHORTS:
            if c == "PROTEAS-brain-mets":
                rows = load_proteas()
            else:
                rows = load_glioma_cohort(c)
            print(f"    {c}: {len(rows)} patients", flush=True)
            train_data.extend(rows)
        print(f"  Train n = {len(train_data)} (5 cohorts)", flush=True)

        t0 = time.time()
        model = train_unet(train_data, seed=SEED)
        print(f"  Training took {time.time()-t0:.0f}s", flush=True)

        print(f"  Zero-shot evaluating on {len(yale_data)} Yale pairs...",
              flush=True)
        yale_per_patient = evaluate(model, yale_data)
        yale_obs_arr = np.array(
            [r["ensemble_outgrowth"] for r in yale_per_patient
             if not np.isnan(r["ensemble_outgrowth"])])
        if len(yale_obs_arr) > 0:
            yale_obs_pct = float(np.mean(yale_obs_arr))
            print(f"  Yale OBSERVED ensemble outgrowth = "
                  f"{yale_obs_pct*100:.2f}% (n={len(yale_obs_arr)})",
                  flush=True)
            print(f"  UOSL v2 prediction error = "
                  f"{abs(yale_obs_pct - yale_pred)*100:.2f} pp", flush=True)

        del model
        torch.cuda.empty_cache()
        gc.collect()

    # ---------- 4) Save ----------
    out = {
        "version": "v177",
        "experiment": "Refined UOSL (v2) + Yale full 5-cohort extension",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "equation": ("P = P_0 + (P_inf - P_0) * sigmoid(a * (N_eff - n_c)),  "
                     "N_eff = log(1 + n_train) * S"),
        "physical_origin": (
            "Bimodal kernel max(M, G_sigma * M) is the steady-state of "
            "constrained Fisher-KPP diffusion dphi/dt = D nabla^2 phi + "
            "epsilon^{-1} max(M - phi, 0) with D = sigma^2/2."
        ),
        "fit_on": "v174 (5 datapoints) + v159 LOCO (5 datapoints) = 10 points",
        "uosl_v2_params": {
            "P_0": p_0, "P_inf": p_inf, "a": a, "n_c": n_c,
        },
        "fit_quality": {
            "rmse": rmse_fit, "r": r_fit,
            "fit_labels": fit_label,
            "fit_n_train": fit_n_train.tolist(),
            "fit_S": fit_S.tolist(),
            "fit_P_obs": fit_P.tolist(),
            "fit_P_pred": pred_fit.tolist(),
        },
        "out_of_sample_validations": validations,
        "validation_summary": {
            "n_points": len(validations),
            "rmse": rmse_val,
        },
        "yale_extension": {
            "n_pairs": len(yale_data),
            "S_index_5_cohort": (similarity_index(
                cohort_weighted_distribution(ALL_COHORTS, n_per_cohort),
                "Yale-Brain-Mets") if len(yale_data) > 0 else None),
            "P_predicted": yale_pred,
            "P_observed_zero_shot": yale_obs_pct,
            "n_eval": int(np.sum([1 for r in yale_per_patient
                                    if not np.isnan(r["ensemble_outgrowth"])])),
        },
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    if yale_per_patient:
        with YALE_CSV.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(yale_per_patient[0].keys()))
            w.writeheader()
            w.writerows(yale_per_patient)
        print(f"Saved {YALE_CSV}", flush=True)


if __name__ == "__main__":
    main()
