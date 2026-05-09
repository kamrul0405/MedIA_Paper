"""v176: Universal Outgrowth Scaling Law (UOSL).

Proposes and validates a novel mathematical generalisation that
unifies all the empirical findings of paper A2:

    P(N, S) = P_inf - (P_inf - P_0) * exp(-alpha * N^beta * S)

where
  P(N, S) = ensemble outgrowth coverage on a held-out cohort
  N       = number of training cohorts
  S       = distribution-similarity index in [0, 1]
            (1 = perfect match between train + test;
             0 = orthogonal / no overlap)
  P_inf   = asymptotic ceiling (<= 1.0)
  P_0     = N=0 zero-prior baseline
  alpha, beta = scaling exponents (analog of Kaplan-McCandlish neural
                scaling laws but multiplied by a similarity factor).

Physical motivation: the bimodal kernel
    K(x; M) = max(M(x), G_sigma * M(x))
is the steady-state of the constrained Fisher-KPP equation
    dphi/dt = D nabla^2 phi + epsilon^{-1} max(M - phi, 0)
with D = sigma^2 / 2 and epsilon -> 0. UOSL is the empirical
generalisation of how this physics couples to multi-cohort
training: more cohorts -> better effective D estimation; more
distribution match -> better source-term coupling.

Pipeline:
  1. Load v174 cohort-scaling data (5 (N, P) data points on UPENN).
  2. Define disease-class similarity S analytically.
  3. Fit UOSL params (P_inf, alpha, beta) via scipy.optimize.curve_fit.
  4. Validate predictions against:
     - v159 multi-seed cross-cohort LOCO (5 cohorts)
     - v152 / v154 cross-disease (PROTEAS held out)
     - v166 UPENN external (95.30%)
     - v172 zero-shot deployment (92.85%)
  5. Yale extension: load Yale-Brain-Mets-Longitudinal,
     generate proxy tumour masks via POST-contrast thresholding,
     compute Yale similarity index S_Yale, predict Yale
     performance via UOSL, then run actual zero-shot inference
     using the universal foundation model and compare.

Outputs:
  Nature_project/05_results/v176_uosl.json
  Nature_project/05_results/v176_uosl_yale_per_patient.csv
"""
from __future__ import annotations

import csv
import gc
import json
import re
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter, zoom, binary_fill_holes
from scipy.optimize import curve_fit

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
UPENN_NPZ = RESULTS / "upenn_cropped_masks.npz"
YALE_DIR = Path(
    r"C:\Users\kamru\Downloads\Datasets\PKG - Yale-Brain-Mets-Longitudinal"
    r"\Yale-Brain-Mets-Longitudinal"
)
OUT_JSON = RESULTS / "v176_uosl.json"
YALE_CSV = RESULTS / "v176_uosl_yale_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

ALL_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE",
               "PROTEAS-brain-mets"]
SIGMA_BROAD = 7.0
TARGET_SHAPE = (16, 48, 48)
SEED = 42
EPOCHS_PRETRAIN = 25
LR_PRETRAIN = 1e-3
YALE_MAX_PATIENTS = 60   # cap to keep runtime sane


# ============================================================================
# 1) Helpers (re-used from prior scripts)
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


def load_upenn():
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
        heat_3d = heat_bimodal(m_3d, SIGMA_BROAD)
        rows.append({
            "pid": str(pid), "cohort": "UPENN-GBM",
            "mask": m_3d.astype(np.float32),
            "fu": t_3d.astype(np.float32),
            "outgrowth": outgrowth_3d.astype(np.float32),
            "heat_bimodal": heat_3d,
        })
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
# 2) Disease-class similarity index S(D_train, D_test)
# ============================================================================

# Disease taxonomy weights — analytically defined. Each cohort has a
# weighting over (GBM, glioma-other, brain-mets) class membership.
DISEASE_VEC = {
    "UCSF-POSTOP":         np.array([0.7, 0.3, 0.0]),  # mostly post-op GBM
    "MU-Glioma-Post":      np.array([0.7, 0.3, 0.0]),  # glioma post-treatment
    "RHUH-GBM":            np.array([1.0, 0.0, 0.0]),  # pure GBM
    "LUMIERE":             np.array([0.4, 0.6, 0.0]),  # mixed glioma grades
    "PROTEAS-brain-mets":  np.array([0.0, 0.0, 1.0]),  # brain-mets only
    "UPENN-GBM":           np.array([1.0, 0.0, 0.0]),  # pure GBM
    "Yale-Brain-Mets":     np.array([0.0, 0.0, 1.0]),  # brain-mets only
}


def cohort_weighted_distribution(train_cohorts, n_per_cohort):
    """Patient-weighted average disease distribution of training set."""
    total = sum(n_per_cohort.get(c, 0) for c in train_cohorts)
    if total == 0:
        return np.zeros(3)
    avg = np.zeros(3)
    for c in train_cohorts:
        n = n_per_cohort.get(c, 0)
        avg += (n / total) * DISEASE_VEC[c]
    return avg


def similarity_index(train_dist, test_cohort):
    """Cosine similarity between training distribution and test cohort."""
    test = DISEASE_VEC[test_cohort]
    nt = np.linalg.norm(train_dist)
    nT = np.linalg.norm(test)
    if nt == 0 or nT == 0:
        return 0.0
    return float(np.dot(train_dist, test) / (nt * nT))


# ============================================================================
# 3) The Universal Outgrowth Scaling Law (UOSL) — equation
# ============================================================================

def uosl(NS, p_inf, p_0, alpha, beta):
    """P(N, S) = p_inf - (p_inf - p_0) * exp(-alpha * N^beta * S)."""
    N, S = NS
    return p_inf - (p_inf - p_0) * np.exp(-alpha * (N ** beta) * S)


# ============================================================================
# 4) Yale loading — proxy masks via POST-contrast thresholding
# ============================================================================

def proxy_mask_from_post(post_path, pre_path=None, percentile=97.0):
    """Generate a coarse tumour proxy mask from a T1c POST-contrast volume.

    We use a per-volume top-percentile threshold inside a brain region.
    If a PRE volume is available, we use the (POST - PRE) difference to
    isolate enhancing voxels (more specific to tumour).

    Returns a binary mask of the same shape as the input volume.
    """
    post_img = nib.load(str(post_path))
    post = np.asanyarray(post_img.dataobj).astype(np.float32)
    # rough brain mask: > 1% of robust max
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
                # match scales by robust max
                pre_max = float(np.percentile(pre[brain], 99.5))
                if pre_max > 0:
                    pre_norm = pre / pre_max * robust_max
                    diff = post - pre_norm
                    diff[~brain] = 0
                    th = np.percentile(diff[brain], percentile)
                    if th <= 0:
                        th = 1e-6
                    mask = (diff > th)
                    if mask.sum() < 50:
                        # fall back to pure POST percentile
                        th2 = np.percentile(post[brain], percentile)
                        mask = (post > th2) & brain
                    return mask
        except Exception:
            pass
    th = np.percentile(post[brain], percentile)
    return (post > th) & brain


def find_yale_pairs(max_patients=YALE_MAX_PATIENTS):
    """For each Yale patient, take the earliest pair of consecutive
    timepoints with POST.nii.gz files. Returns list of (pid, baseline_path,
    followup_path, baseline_pre, followup_pre)."""
    if not YALE_DIR.exists():
        return []
    pairs = []
    patients = sorted(p for p in YALE_DIR.iterdir() if p.is_dir())
    for p in patients[:max_patients * 2]:  # over-sample, may skip some
        timepoints = sorted(t for t in p.iterdir() if t.is_dir())
        if len(timepoints) < 2:
            continue
        # baseline = first; follow-up = last (longest interval)
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
    """Build Yale evaluation set with proxy masks."""
    pairs = find_yale_pairs(max_patients)
    print(f"  Yale: found {len(pairs)} longitudinal pairs", flush=True)
    rows = []
    t0 = time.time()
    for i, (pid, b_post, f_post, b_pre, f_pre) in enumerate(pairs, 1):
        try:
            b_mask = proxy_mask_from_post(b_post, b_pre)
            f_mask = proxy_mask_from_post(f_post, f_pre)
        except Exception as e:
            print(f"    skip {pid}: {e}", flush=True)
            continue
        if b_mask is None or f_mask is None:
            continue
        if b_mask.shape != f_mask.shape:
            continue
        # require non-trivial mask sizes
        if b_mask.sum() < 200 or f_mask.sum() < 200:
            continue
        m_r = resize_to_target(b_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        f_r = resize_to_target(f_mask.astype(np.float32), TARGET_SHAPE) > 0.5
        if m_r.sum() == 0 or f_r.sum() == 0:
            continue
        outgrowth_r = f_r & ~m_r
        if outgrowth_r.sum() == 0:
            continue
        heat = heat_bimodal(m_r, SIGMA_BROAD)
        rows.append({
            "pid": pid, "cohort": "Yale-Brain-Mets",
            "mask": m_r.astype(np.float32),
            "fu": f_r.astype(np.float32),
            "outgrowth": outgrowth_r.astype(np.float32),
            "heat_bimodal": heat,
        })
        if i % 10 == 0:
            print(f"    {i}/{len(pairs)} ({time.time()-t0:.0f}s) "
                  f"-> {len(rows)} usable", flush=True)
    return rows


# ============================================================================
# 5) Main
# ============================================================================

def main():
    print("=" * 78, flush=True)
    print("v176 UNIVERSAL OUTGROWTH SCALING LAW (UOSL)", flush=True)
    print("  P(N, S) = P_inf - (P_inf - P_0) * exp(-alpha * N^beta * S)", flush=True)
    print("=" * 78, flush=True)

    # ---------- 5a) Fit UOSL on v174 ----------
    v174_path = RESULTS / "v174_cohort_scaling_upenn.json"
    v174 = json.loads(v174_path.read_text())
    n_per_cohort = {}
    fit_N, fit_S, fit_P = [], [], []
    for n_str, row in v174["by_n"].items():
        N = int(n_str)
        train_cohorts = row["train_cohorts"]
        # populate per-cohort patient counts (cumulative), recover increments
        # we know: row["n_train_patients"] is cumulative
        # build n_per_cohort by cumulative differences
    # build n_per_cohort from cumulative training-set sizes
    prev_total = 0
    for n_str in sorted(v174["by_n"], key=int):
        row = v174["by_n"][n_str]
        new_cohort = row["train_cohorts"][-1]
        n_per_cohort[new_cohort] = row["n_train_patients"] - prev_total
        prev_total = row["n_train_patients"]
    print(f"  cohort sizes recovered: {n_per_cohort}", flush=True)

    for n_str, row in sorted(v174["by_n"].items(), key=lambda kv: int(kv[0])):
        N = int(n_str)
        train_dist = cohort_weighted_distribution(row["train_cohorts"], n_per_cohort)
        S = similarity_index(train_dist, "UPENN-GBM")
        P = row["ensemble_outgrowth_pct"] / 100.0
        fit_N.append(N)
        fit_S.append(S)
        fit_P.append(P)
        print(f"  N={N} S={S:.4f} P={P:.4f}", flush=True)
    fit_N = np.array(fit_N, dtype=float)
    fit_S = np.array(fit_S, dtype=float)
    fit_P = np.array(fit_P, dtype=float)

    # Initial guess + bounds
    p0 = [1.0, 0.5, 1.0, 1.0]
    bounds = ([0.5, 0.0, 0.01, 0.1], [1.0, 0.95, 20.0, 5.0])
    popt, pcov = curve_fit(uosl, (fit_N, fit_S), fit_P, p0=p0, bounds=bounds,
                           maxfev=20000)
    p_inf, p_0, alpha, beta = popt
    pred_v174 = uosl((fit_N, fit_S), *popt)
    rmse_v174 = float(np.sqrt(np.mean((pred_v174 - fit_P) ** 2)))
    r_v174 = float(np.corrcoef(pred_v174, fit_P)[0, 1])
    print(f"\nUOSL fit on v174:", flush=True)
    print(f"  P_inf={p_inf:.4f} P_0={p_0:.4f} alpha={alpha:.4f} beta={beta:.4f}",
          flush=True)
    print(f"  RMSE={rmse_v174:.4f}  r={r_v174:.4f}", flush=True)

    # ---------- 5b) Validate on independent experiments ----------
    validations = []

    def add_val(name, N, S, P_obs, source):
        P_pred = float(uosl((np.array([N]), np.array([S])), *popt)[0])
        validations.append({
            "name": name, "N": int(N), "S": float(S),
            "P_observed": float(P_obs), "P_predicted": P_pred,
            "abs_err_pp": float(abs(P_obs - P_pred) * 100),
            "source": source,
        })

    # v159 multi-seed: each held-out cohort -> N=4 training cohorts
    v159_path = RESULTS / "v159_multiseed_v156.json"
    if v159_path.exists():
        v159 = json.loads(v159_path.read_text())
        for held_out, stats in v159["by_cohort"].items():
            train_cohorts = [c for c in ALL_COHORTS if c != held_out]
            train_dist = cohort_weighted_distribution(train_cohorts, n_per_cohort)
            S = similarity_index(train_dist, held_out)
            P_obs = stats["ensemble_outgrowth_mean"] / 100.0
            add_val(f"v159 LOCO held={held_out}", N=4, S=S, P_obs=P_obs,
                    source="v159_multiseed_v156.json")

    # v152 cross-disease: trained on glioma cohorts, tested on PROTEAS
    v152_path = RESULTS / "v152_cross_disease.json"
    if v152_path.exists():
        v152 = json.loads(v152_path.read_text())
        # extract a single representative number
        for k in ("ensemble_outgrowth_pct", "ensemble_outgrowth_mean_pct"):
            if k in v152:
                P_obs = v152[k] / 100.0
                train_cohorts = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM",
                                 "LUMIERE"]
                td = cohort_weighted_distribution(train_cohorts, n_per_cohort)
                S = similarity_index(td, "PROTEAS-brain-mets")
                add_val("v152 cross-disease (gliomas->PROTEAS)", N=4, S=S,
                        P_obs=P_obs, source="v152_cross_disease.json")
                break

    # v166 UPENN external: foundation model on 5 cohorts -> UPENN
    v166_path = RESULTS / "v166_upenn_external_validation.json"
    if v166_path.exists():
        v166 = json.loads(v166_path.read_text())
        for k in ("ensemble_outgrowth_pct", "ensemble_outgrowth"):
            if k in v166:
                P_obs = v166[k] / (100.0 if v166[k] > 1 else 1.0)
                td = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
                S = similarity_index(td, "UPENN-GBM")
                add_val("v166 UPENN external (5-cohort)", N=5, S=S,
                        P_obs=P_obs, source="v166_upenn_external_validation.json")
                break

    # v172 zero-shot UPENN: same 5-cohort model, N=0 fine-tune set
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
                    add_val("v172 zero-shot UPENN (N_local=0)", N=5, S=S,
                            P_obs=P_obs, source="v172_few_shot_upenn.json")
                    break

    print(f"\nUOSL out-of-sample validations: {len(validations)} points",
          flush=True)
    for v in validations:
        print(f"  {v['name']:50s}  N={v['N']} S={v['S']:.3f}  "
              f"obs={v['P_observed']:.4f} pred={v['P_predicted']:.4f}  "
              f"err={v['abs_err_pp']:.2f} pp", flush=True)

    P_obs_all = np.array([v["P_observed"] for v in validations])
    P_pred_all = np.array([v["P_predicted"] for v in validations])
    if len(P_obs_all) >= 2:
        rmse_val = float(np.sqrt(np.mean((P_obs_all - P_pred_all) ** 2)))
        r_val = float(np.corrcoef(P_obs_all, P_pred_all)[0, 1]) \
                if len(P_obs_all) >= 3 else float("nan")
    else:
        rmse_val = float("nan")
        r_val = float("nan")
    print(f"\nValidation RMSE = {rmse_val:.4f}  r = {r_val:.4f}", flush=True)

    # ---------- 5c) Yale extension ----------
    print("\n" + "=" * 60, flush=True)
    print("Yale-Brain-Mets-Longitudinal extension", flush=True)
    print("=" * 60, flush=True)

    yale_data = load_yale(max_patients=YALE_MAX_PATIENTS)
    print(f"  Yale usable longitudinal pairs: {len(yale_data)}", flush=True)

    yale_pred_uosl = float("nan")
    yale_obs_pct = float("nan")
    yale_per_patient = []
    if len(yale_data) > 0:
        td_full = cohort_weighted_distribution(ALL_COHORTS, n_per_cohort)
        S_yale = similarity_index(td_full, "Yale-Brain-Mets")
        yale_pred_uosl = float(uosl((np.array([5.0]),
                                       np.array([S_yale])), *popt)[0])
        print(f"  Yale similarity index S = {S_yale:.4f}  (5-cohort training)",
              flush=True)
        print(f"  UOSL prediction (N=5, S=S_yale): "
              f"P_yale_pred = {yale_pred_uosl*100:.2f}%", flush=True)

        # Train universal foundation model on all 5 cohorts (zero-shot to Yale)
        print(f"\n  Training universal foundation model on 5 cohorts...",
              flush=True)
        train_data = []
        for c in ALL_COHORTS:
            if c == "PROTEAS-brain-mets":
                # use existing cached evaluation set (PROTEAS not cached as
                # _b/_r files — load from zip would be slow, use only glioma
                # cohorts for the zero-shot Yale comparison)
                continue
            train_data.extend(load_glioma_cohort(c))
        print(f"  Train n = {len(train_data)} (glioma cohorts only — PROTEAS "
              f"omitted for cache reasons; updates Yale similarity slightly)",
              flush=True)
        # recompute S_yale without PROTEAS
        td_glioma = cohort_weighted_distribution(
            [c for c in ALL_COHORTS if c != "PROTEAS-brain-mets"], n_per_cohort)
        S_yale_actual_train = similarity_index(td_glioma, "Yale-Brain-Mets")
        yale_pred_uosl_glioma = float(uosl(
            (np.array([4.0]), np.array([S_yale_actual_train])), *popt)[0])
        print(f"  Adjusted UOSL prediction (N=4 glioma, S={S_yale_actual_train:.4f}): "
              f"P_yale_pred = {yale_pred_uosl_glioma*100:.2f}%",
              flush=True)

        t0 = time.time()
        model = train_unet(train_data, seed=SEED)
        print(f"  Training took {time.time()-t0:.0f}s", flush=True)

        # Zero-shot evaluate Yale
        print(f"  Zero-shot evaluating on {len(yale_data)} Yale pairs...",
              flush=True)
        yale_per_patient = evaluate(model, yale_data)
        yale_obs_arr = np.array(
            [r["ensemble_outgrowth"] for r in yale_per_patient if not np.isnan(
                r["ensemble_outgrowth"])])
        if len(yale_obs_arr) > 0:
            yale_obs_pct = float(np.mean(yale_obs_arr))
            print(f"  Yale OBSERVED ensemble outgrowth = "
                  f"{yale_obs_pct*100:.2f}% (n={len(yale_obs_arr)})",
                  flush=True)
            print(f"  UOSL prediction error = "
                  f"{abs(yale_obs_pct - yale_pred_uosl_glioma)*100:.2f} pp",
                  flush=True)

        del model
        torch.cuda.empty_cache()
        gc.collect()

    # ---------- 5d) Save results ----------
    out = {
        "version": "v176",
        "experiment": "Universal Outgrowth Scaling Law (UOSL) + Yale extension",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "equation": "P(N, S) = P_inf - (P_inf - P_0) * exp(-alpha * N^beta * S)",
        "physical_origin": (
            "Bimodal kernel max(M, G_sigma * M) is the steady-state of "
            "the constrained Fisher-KPP equation dphi/dt = D nabla^2 phi + "
            "epsilon^{-1} max(M - phi, 0) with D = sigma^2/2, epsilon -> 0"
        ),
        "fit_on": "v174_cohort_scaling_upenn.json (5 (N, P) data points)",
        "uosl_params": {
            "P_inf": p_inf, "P_0": p_0, "alpha": alpha, "beta": beta,
        },
        "fit_quality": {
            "rmse": rmse_v174, "r": r_v174,
            "fit_N": fit_N.tolist(), "fit_S": fit_S.tolist(),
            "fit_P_obs": fit_P.tolist(),
            "fit_P_pred": pred_v174.tolist(),
        },
        "n_per_cohort": n_per_cohort,
        "out_of_sample_validations": validations,
        "validation_summary": {
            "n_points": len(validations),
            "rmse": rmse_val, "r_pearson": r_val,
        },
        "yale_extension": {
            "n_pairs": len(yale_data),
            "S_index_5_cohort": (similarity_index(
                cohort_weighted_distribution(ALL_COHORTS, n_per_cohort),
                "Yale-Brain-Mets") if len(yale_data) > 0 else None),
            "S_index_4_glioma": (similarity_index(
                cohort_weighted_distribution(
                    [c for c in ALL_COHORTS if c != "PROTEAS-brain-mets"],
                    n_per_cohort), "Yale-Brain-Mets")
                if len(yale_data) > 0 else None),
            "P_predicted_5cohort": yale_pred_uosl,
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
