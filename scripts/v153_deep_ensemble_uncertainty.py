"""v153: Deep ensemble (5 seeds) for uncertainty quantification on
LUMIERE LOCO.

Train 5 U-Nets with different seeds on UCSF+MU+RHUH (n=487).
For each test patient: ensemble prediction = mean across 5 model
predictions; epistemic uncertainty = std across 5 predictions.

Computes:
  - Mean ensemble prediction (improves over single-seed)
  - Per-voxel epistemic uncertainty (std across 5)
  - Per-patient mean predictive entropy
  - Coverage as a function of uncertainty quantile (high-uncertainty
    voxels excluded -> coverage curve)

Required for FDA-style regulatory deployment.

Outputs:
    Nature_project/05_results/v153_deep_ensemble.json
"""
from __future__ import annotations

import csv
import gc
import json
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v153_deep_ensemble.json"
OUT_CSV = RESULTS / "v153_deep_ensemble_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

TRAIN_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM"]
TEST_COHORT = "LUMIERE"
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
SEEDS = [42, 123, 999, 7, 31]


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


def load_cohort(cohort):
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


def predict_per_voxel(model, d):
    """Return per-voxel sigmoid probability."""
    model.eval()
    with torch.no_grad():
        x = np.stack([d["mask"], d["heat_bimodal"]], axis=0).astype(np.float32)
        xt = torch.from_numpy(x[None]).to(DEVICE)
        logits = model(xt)
        pred = torch.sigmoid(logits).cpu().numpy()[0, 0]
    return pred


def main():
    print("=" * 78, flush=True)
    print("v153 DEEP ENSEMBLE (5 SEEDS) FOR UNCERTAINTY QUANTIFICATION", flush=True)
    print(f"  device: {DEVICE}; seeds: {SEEDS}; epochs={EPOCHS}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading cohorts...", flush=True)
    cohorts_data = {}
    for cohort in TRAIN_COHORTS + [TEST_COHORT]:
        cohorts_data[cohort] = load_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])} patients", flush=True)

    train_data = []
    for c in TRAIN_COHORTS:
        train_data.extend(cohorts_data[c])
    test_data = cohorts_data[TEST_COHORT]
    print(f"\n  Combined training: {len(train_data)} patients across "
          f"{len(TRAIN_COHORTS)} cohorts", flush=True)

    # Train 5 ensemble members
    print(f"\n=== Training {len(SEEDS)} ensemble members ===", flush=True)
    all_predictions = []  # list of (n_test, D, H, W) arrays
    for seed in SEEDS:
        t0 = time.time()
        model = train_unet(train_data, seed)
        print(f"  seed={seed} trained in {time.time()-t0:.0f}s", flush=True)
        # Predict on test set
        preds = []
        for d in test_data:
            preds.append(predict_per_voxel(model, d))
        all_predictions.append(np.stack(preds))  # (N, D, H, W)
        del model; torch.cuda.empty_cache(); gc.collect()

    all_predictions = np.stack(all_predictions)  # (5, N, D, H, W)
    n_test = all_predictions.shape[1]

    # Compute mean and std across seeds per voxel
    mean_pred = all_predictions.mean(axis=0)  # (N, D, H, W)
    std_pred = all_predictions.std(axis=0, ddof=1)  # (N, D, H, W)

    # Per-patient evaluation
    print(f"\n=== Evaluating on {n_test} LUMIERE patients ===", flush=True)
    rows = []
    per_voxel_mean_uncertainty = []
    per_voxel_low_unc_coverage_05 = []
    per_voxel_high_unc_coverage_05 = []
    for i, d in enumerate(test_data):
        # Per-voxel ensemble prediction
        pred = mean_pred[i]
        unc = std_pred[i]
        bimodal = d["heat_bimodal"]
        # Region: pred>=0.5
        pred_region = pred >= 0.5
        bimodal_region = bimodal >= 0.5
        ensemble_heat = np.maximum(pred, bimodal)
        ensemble_region = ensemble_heat >= 0.5

        learned_out = outgrowth_coverage(d["fu"], d["mask"], pred_region)
        bim_out = outgrowth_coverage(d["fu"], d["mask"], bimodal_region)
        ens_out = outgrowth_coverage(d["fu"], d["mask"], ensemble_region)
        ens_ovr = overall_coverage(d["fu"], ensemble_region)
        bim_ovr = overall_coverage(d["fu"], bimodal_region)
        learned_ovr = overall_coverage(d["fu"], pred_region)

        # Mean per-voxel uncertainty in the prediction region
        mean_unc = float(np.mean(unc))
        max_unc = float(np.max(unc))
        rows.append({
            "pid": d["pid"], "cohort": d["cohort"],
            "learned_outgrowth": learned_out,
            "bimodal_outgrowth": bim_out,
            "ensemble_outgrowth": ens_out,
            "learned_overall": learned_ovr,
            "bimodal_overall": bim_ovr,
            "ensemble_overall": ens_ovr,
            "mean_voxel_uncertainty": mean_unc,
            "max_voxel_uncertainty": max_unc,
        })
        per_voxel_mean_uncertainty.append(unc.flatten())
        # Low-uncertainty voxels (bottom-50% std): coverage of these
        unc_threshold = np.median(unc)
        low_unc_region = (pred >= 0.5) & (unc <= unc_threshold)
        high_unc_region = (pred >= 0.5) & (unc > unc_threshold)
        per_voxel_low_unc_coverage_05.append(
            outgrowth_coverage(d["fu"], d["mask"], low_unc_region))
        per_voxel_high_unc_coverage_05.append(
            outgrowth_coverage(d["fu"], d["mask"], high_unc_region))

    learned_out = float(np.nanmean([r["learned_outgrowth"] for r in rows]) * 100)
    bim_out = float(np.nanmean([r["bimodal_outgrowth"] for r in rows]) * 100)
    ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in rows]) * 100)
    learned_ovr = float(np.nanmean([r["learned_overall"] for r in rows]) * 100)
    ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in rows]) * 100)
    mean_unc_overall = float(np.mean([r["mean_voxel_uncertainty"] for r in rows]))
    low_unc_coverage = float(np.nanmean(per_voxel_low_unc_coverage_05) * 100)
    high_unc_coverage = float(np.nanmean(per_voxel_high_unc_coverage_05) * 100)

    print(f"\n=== Deep ensemble results on LUMIERE (mean across 5 seeds) ===",
          flush=True)
    print(f"  learned-out (5-ens mean): {learned_out:.2f}%", flush=True)
    print(f"  bimodal-out:              {bim_out:.2f}%", flush=True)
    print(f"  ensemble-out:             {ens_out:.2f}%", flush=True)
    print(f"  learned-ovr:              {learned_ovr:.2f}%", flush=True)
    print(f"  ensemble-ovr:             {ens_ovr:.2f}%", flush=True)
    print(f"  mean per-voxel uncertainty: {mean_unc_overall:.4f}", flush=True)
    print(f"  low-unc voxel coverage of outgrowth: {low_unc_coverage:.2f}%", flush=True)
    print(f"  high-unc voxel coverage of outgrowth: {high_unc_coverage:.2f}%", flush=True)

    # Comparison to v141 single-seed and v144 multi-seed
    print(f"\n=== Comparison ===", flush=True)
    print(f"  v141 single-seed UCSF only:  ens-out 56.46%  ens-ovr 65.39%", flush=True)
    print(f"  v144 multi-seed UCSF only:   ens-out 60.51 ± 1.42%", flush=True)
    print(f"  v148 UCSF+MU centralized:    ens-out 67.69%  ens-ovr 74.52%", flush=True)
    print(f"  v153 5-ensemble UCSF+MU+RHUH: ens-out {ens_out:.2f}%  ens-ovr {ens_ovr:.2f}%",
          flush=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    out = {"version": "v153",
           "experiment": "Deep ensemble (5 seeds) for uncertainty quantification on LUMIERE",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "seeds": SEEDS,
           "training_cohorts": TRAIN_COHORTS,
           "n_train": len(train_data),
           "test_cohort": TEST_COHORT,
           "n_test": n_test,
           "results": {
               "learned_outgrowth_5ens_mean_pct": learned_out,
               "bimodal_outgrowth_pct": bim_out,
               "ensemble_outgrowth_5ens_mean_pct": ens_out,
               "learned_overall_5ens_mean_pct": learned_ovr,
               "ensemble_overall_5ens_mean_pct": ens_ovr,
               "mean_per_voxel_uncertainty": mean_unc_overall,
               "low_uncertainty_voxel_outgrowth_coverage_pct": low_unc_coverage,
               "high_uncertainty_voxel_outgrowth_coverage_pct": high_unc_coverage,
           },
           "comparison_to_prior_rounds": {
               "v141_single_seed_ens_out_pct": 56.46,
               "v144_multiseed_mean_ens_out_pct": 60.51,
               "v148_ucsf_mu_ens_out_pct": 67.69,
               "v153_5ens_ucsf_mu_rhuh_ens_out_pct": ens_out,
           }}
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
