"""v141: Cross-cohort learned 3D U-Net for outgrowth prediction.

Train on UCSF-POSTOP (N=297, the largest cohort) with the bimodal
kernel (sigma=7) as auxiliary input; test LOCO on:
  - UCSF (5-fold CV; held-out fold)
  - MU-Glioma-Post (LOCO; never seen during training)
  - RHUH-GBM (LOCO; never seen)
  - LUMIERE (LOCO; never seen)

Tests whether a learned outgrowth predictor generalises to held-out
cohorts. If yes -> deployment-ready. If no -> hand-crafted bimodal
wins on robustness.

Architecture:
  - 3D U-Net (24 base channels; 3 levels: 32 -> 64 -> 128)
  - Input channels: (mask, bimodal heat at sigma=7)
  - Loss: focal BCE (alpha=0.95, gamma=2) + Dice
  - 30 epochs, AdamW @ lr=1e-3
  - Volumes resized to (16, 48, 48) for the cache_3d native shape

Outputs:
    Nature_project/05_results/v141_cross_cohort_unet.json
    Nature_project/05_results/v141_cross_cohort_unet_per_patient.csv
"""
from __future__ import annotations

import csv
import gc
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "cache_3d"
OUT_JSON = RESULTS / "v141_cross_cohort_unet.json"
OUT_CSV = RESULTS / "v141_cross_cohort_unet_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

TRAIN_COHORT = "UCSF-POSTOP"
TEST_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
N_FOLDS_UCSF = 5  # 5-fold CV within UCSF (use one fold as test, rest as train)


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
    focal_loss = focal.mean()
    intersection = (p * target).sum()
    dice_loss = 1 - (2 * intersection + smooth) / (p.sum() + target.sum() + smooth)
    return focal_loss + dice_loss


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


def train_unet(train_data, epochs=EPOCHS, batch_size=4):
    n = len(train_data)
    X = np.stack([np.stack([d["mask"], d["heat_bimodal"]], axis=0)
                   for d in train_data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in train_data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE)
    Yt = torch.from_numpy(Y).to(DEVICE)
    model = UNet3D(in_ch=2, base=24).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    for ep in range(epochs):
        model.train()
        perm = np.random.permutation(n)
        ep_loss = 0.0
        for i in range(0, n, batch_size):
            idx = perm[i:i+batch_size]
            xb = Xt[idx]; yb = Yt[idx]
            logits = model(xb)
            loss = focal_dice_loss(logits, yb)
            opt.zero_grad(); loss.backward(); opt.step()
            ep_loss += float(loss.item())
        if (ep + 1) % 5 == 0:
            print(f"    epoch {ep+1}/{epochs}: avg loss = {ep_loss / max(n // batch_size, 1):.4f}",
                  flush=True)
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
            row = {
                "pid": d["pid"], "cohort": d["cohort"],
                "learned_overall": overall_coverage(d["fu"], pred_region),
                "learned_outgrowth": outgrowth_coverage(d["fu"], d["mask"], pred_region),
                "bimodal_overall": overall_coverage(d["fu"], bimodal_region),
                "bimodal_outgrowth": outgrowth_coverage(d["fu"], d["mask"], bimodal_region),
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
            }
            rows.append(row)
    return rows


def main():
    print("=" * 78, flush=True)
    print("v141 CROSS-COHORT LEARNED 3D U-NET (UCSF -> LOCO)", flush=True)
    print(f"  device: {DEVICE}; epochs={EPOCHS}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading cohorts...", flush=True)
    cohorts_data = {}
    for cohort in TEST_COHORTS:
        cohorts_data[cohort] = load_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])} patients", flush=True)

    all_results = []

    # 5-fold CV on UCSF
    print(f"\n=== UCSF 5-fold CV ===", flush=True)
    ucsf_data = cohorts_data[TRAIN_COHORT]
    rng = np.random.default_rng(14101)
    n = len(ucsf_data)
    perm = rng.permutation(n)
    fold_size = n // N_FOLDS_UCSF
    for fold in range(N_FOLDS_UCSF):
        t0 = time.time()
        test_idx = perm[fold * fold_size:(fold + 1) * fold_size if fold < N_FOLDS_UCSF - 1 else n]
        train_idx = np.array([i for i in range(n) if i not in set(test_idx.tolist())])
        train_data = [ucsf_data[i] for i in train_idx]
        test_data = [ucsf_data[i] for i in test_idx]
        print(f"  fold {fold+1}/{N_FOLDS_UCSF}: train {len(train_data)}, test {len(test_data)}",
              flush=True)
        model = train_unet(train_data)
        rows = evaluate(model, test_data)
        for r in rows:
            r["test_setup"] = f"UCSF_5fold_fold{fold+1}"
        all_results.extend(rows)
        del model; torch.cuda.empty_cache(); gc.collect()
        print(f"    fold {fold+1} done in {time.time()-t0:.0f}s", flush=True)

    # Train on full UCSF, test LOCO on MU, RHUH, LUMIERE
    print(f"\n=== Training on FULL UCSF ({len(ucsf_data)}), LOCO testing ===", flush=True)
    t0 = time.time()
    full_model = train_unet(ucsf_data)
    print(f"  full UCSF training done in {time.time()-t0:.0f}s", flush=True)

    for held_cohort in ["MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]:
        test_data = cohorts_data[held_cohort]
        rows = evaluate(full_model, test_data)
        for r in rows:
            r["test_setup"] = f"UCSF_train_LOCO_test_{held_cohort}"
        all_results.extend(rows)
        # Per-cohort summary
        learned_out = np.array([r["learned_outgrowth"] for r in rows], dtype=float)
        bim_out = np.array([r["bimodal_outgrowth"] for r in rows], dtype=float)
        ens_out = np.array([r["ensemble_outgrowth"] for r in rows], dtype=float)
        learned_ovr = np.array([r["learned_overall"] for r in rows], dtype=float)
        bim_ovr = np.array([r["bimodal_overall"] for r in rows], dtype=float)
        ens_ovr = np.array([r["ensemble_overall"] for r in rows], dtype=float)
        print(f"\n  LOCO test on {held_cohort} (N={len(rows)}):", flush=True)
        print(f"    learned:  overall {np.nanmean(learned_ovr)*100:5.2f}%  "
              f"outgrowth {np.nanmean(learned_out)*100:5.2f}%", flush=True)
        print(f"    bimodal:  overall {np.nanmean(bim_ovr)*100:5.2f}%  "
              f"outgrowth {np.nanmean(bim_out)*100:5.2f}%", flush=True)
        print(f"    ensemble: overall {np.nanmean(ens_ovr)*100:5.2f}%  "
              f"outgrowth {np.nanmean(ens_out)*100:5.2f}%", flush=True)

    # Save per-patient CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_results:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader(); w.writerows(all_results)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    # Aggregate summaries
    out = {"version": "v141",
           "experiment": "Cross-cohort learned 3D U-Net (UCSF train -> LOCO test)",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "device": str(DEVICE),
           "epochs": EPOCHS,
           "n_total_test_followups": len(all_results),
           "by_setup": {}}

    setups = sorted(set(r["test_setup"] for r in all_results))
    for setup in setups:
        sub = [r for r in all_results if r["test_setup"] == setup]
        learned_ovr = np.array([r["learned_overall"] for r in sub], dtype=float)
        learned_out = np.array([r["learned_outgrowth"] for r in sub], dtype=float)
        bim_ovr = np.array([r["bimodal_overall"] for r in sub], dtype=float)
        bim_out = np.array([r["bimodal_outgrowth"] for r in sub], dtype=float)
        ens_ovr = np.array([r["ensemble_overall"] for r in sub], dtype=float)
        ens_out = np.array([r["ensemble_outgrowth"] for r in sub], dtype=float)
        d_learned_bim_out = learned_out - bim_out
        d_ens_bim_out = ens_out - bim_out
        out["by_setup"][setup] = {
            "n": len(sub),
            "learned_overall_mean_pct": float(np.nanmean(learned_ovr) * 100),
            "learned_outgrowth_mean_pct": float(np.nanmean(learned_out) * 100),
            "bimodal_overall_mean_pct": float(np.nanmean(bim_ovr) * 100),
            "bimodal_outgrowth_mean_pct": float(np.nanmean(bim_out) * 100),
            "ensemble_overall_mean_pct": float(np.nanmean(ens_ovr) * 100),
            "ensemble_outgrowth_mean_pct": float(np.nanmean(ens_out) * 100),
            "delta_learned_minus_bimodal_outgrowth_pp": float(np.nanmean(d_learned_bim_out) * 100),
            "delta_ensemble_minus_bimodal_outgrowth_pp": float(np.nanmean(d_ens_bim_out) * 100),
        }

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)

    print(f"\n=== FINAL CROSS-COHORT SUMMARY ===", flush=True)
    print(f"  {'Setup':<35s} {'N':>4s} {'learn-out':>10s} {'bim-out':>10s} {'ens-out':>10s}",
          flush=True)
    for setup, agg in out["by_setup"].items():
        print(f"  {setup:<35s} {agg['n']:>4d} "
              f"{agg['learned_outgrowth_mean_pct']:>9.2f}% "
              f"{agg['bimodal_outgrowth_mean_pct']:>9.2f}% "
              f"{agg['ensemble_outgrowth_mean_pct']:>9.2f}%", flush=True)


if __name__ == "__main__":
    main()
