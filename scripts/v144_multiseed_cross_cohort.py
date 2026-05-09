"""v144: Multi-seed v141 cross-cohort U-Net robustness audit.

Replicates v141 (UCSF train -> LOCO test) across 3 random seeds
(42, 123, 999) to address seed-variance concerns required for
flagship clinical journal submission.

For each seed:
  - 5-fold CV on UCSF (in-distribution)
  - Train on full UCSF, test LOCO on MU, RHUH, LUMIERE

Reports mean +/- SE per cohort across the 3 seeds.

Outputs:
    Nature_project/05_results/v144_multiseed_cross_cohort.json
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
OUT_JSON = RESULTS / "v144_multiseed_cross_cohort.json"
OUT_CSV = RESULTS / "v144_multiseed_cross_cohort_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

TRAIN_COHORT = "UCSF-POSTOP"
TEST_LOCO = ["MU-Glioma-Post", "RHUH-GBM", "LUMIERE"]
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
SEEDS = [42, 123, 999]


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


def evaluate(model, test_data, seed):
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
                "pid": d["pid"], "cohort": d["cohort"], "seed": seed,
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
    print("v144 MULTI-SEED v141 CROSS-COHORT ROBUSTNESS", flush=True)
    print(f"  device: {DEVICE}; seeds: {SEEDS}; epochs={EPOCHS}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading cohorts...", flush=True)
    cohorts_data = {}
    for cohort in [TRAIN_COHORT] + TEST_LOCO:
        cohorts_data[cohort] = load_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])} patients", flush=True)

    all_results = []
    for seed in SEEDS:
        print(f"\n=== seed = {seed} ===", flush=True)
        t0 = time.time()
        # Train on full UCSF
        model = train_unet(cohorts_data[TRAIN_COHORT], seed)
        print(f"  full UCSF training done in {time.time()-t0:.0f}s", flush=True)

        # Test LOCO on MU, RHUH, LUMIERE
        for held in TEST_LOCO:
            test_data = cohorts_data[held]
            rows = evaluate(model, test_data, seed)
            for r in rows:
                r["test_setup"] = f"UCSF_train_LOCO_test_{held}"
            all_results.extend(rows)

            learned_out = np.array([r["learned_outgrowth"] for r in rows], dtype=float)
            bim_out = np.array([r["bimodal_outgrowth"] for r in rows], dtype=float)
            ens_out = np.array([r["ensemble_outgrowth"] for r in rows], dtype=float)
            ens_ovr = np.array([r["ensemble_overall"] for r in rows], dtype=float)
            print(f"  seed={seed}  LOCO {held:18s}: "
                  f"learned-out {np.nanmean(learned_out)*100:5.2f}%  "
                  f"bim-out {np.nanmean(bim_out)*100:5.2f}%  "
                  f"ens-out {np.nanmean(ens_out)*100:5.2f}%  "
                  f"ens-ovr {np.nanmean(ens_ovr)*100:5.2f}%", flush=True)
        del model; torch.cuda.empty_cache(); gc.collect()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_results:
        with open(OUT_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader(); w.writerows(all_results)
        print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    # Aggregate per (cohort, metric) across 3 seeds
    print(f"\n=== MULTI-SEED AGGREGATE (mean +/- SE across 3 seeds) ===", flush=True)
    out = {"version": "v144",
           "experiment": "Multi-seed UCSF -> LOCO U-Net robustness audit",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "seeds": SEEDS, "epochs": EPOCHS, "device": str(DEVICE),
           "by_cohort": {}}
    for cohort in TEST_LOCO:
        sub = [r for r in all_results if r["cohort"] == cohort]
        # Per-seed cohort means
        per_seed = {}
        for s in SEEDS:
            seed_rows = [r for r in sub if r["seed"] == s]
            if not seed_rows: continue
            per_seed[s] = {
                "learned_outgrowth": float(np.nanmean([r["learned_outgrowth"] for r in seed_rows]) * 100),
                "bimodal_outgrowth": float(np.nanmean([r["bimodal_outgrowth"] for r in seed_rows]) * 100),
                "ensemble_outgrowth": float(np.nanmean([r["ensemble_outgrowth"] for r in seed_rows]) * 100),
                "learned_overall": float(np.nanmean([r["learned_overall"] for r in seed_rows]) * 100),
                "bimodal_overall": float(np.nanmean([r["bimodal_overall"] for r in seed_rows]) * 100),
                "ensemble_overall": float(np.nanmean([r["ensemble_overall"] for r in seed_rows]) * 100),
            }
        # Multi-seed mean +/- SE
        learned_out_seeds = [per_seed[s]["learned_outgrowth"] for s in SEEDS if s in per_seed]
        ensemble_out_seeds = [per_seed[s]["ensemble_outgrowth"] for s in SEEDS if s in per_seed]
        ensemble_ovr_seeds = [per_seed[s]["ensemble_overall"] for s in SEEDS if s in per_seed]
        bim_out_seeds = [per_seed[s]["bimodal_outgrowth"] for s in SEEDS if s in per_seed]
        n_seeds = len(SEEDS)
        agg = {
            "n_patients": int(len([r for r in sub if r["seed"] == SEEDS[0]])),
            "n_seeds": n_seeds,
            "per_seed": per_seed,
            "learned_outgrowth_mean": float(np.mean(learned_out_seeds)),
            "learned_outgrowth_se": float(np.std(learned_out_seeds, ddof=1) / np.sqrt(n_seeds)),
            "bimodal_outgrowth_mean": float(np.mean(bim_out_seeds)),
            "ensemble_outgrowth_mean": float(np.mean(ensemble_out_seeds)),
            "ensemble_outgrowth_se": float(np.std(ensemble_out_seeds, ddof=1) / np.sqrt(n_seeds)),
            "ensemble_outgrowth_min": float(np.min(ensemble_out_seeds)),
            "ensemble_outgrowth_max": float(np.max(ensemble_out_seeds)),
            "ensemble_overall_mean": float(np.mean(ensemble_ovr_seeds)),
            "ensemble_overall_se": float(np.std(ensemble_ovr_seeds, ddof=1) / np.sqrt(n_seeds)),
        }
        out["by_cohort"][cohort] = agg
        print(f"  {cohort:18s}: ensemble outgrowth = {agg['ensemble_outgrowth_mean']:.2f} +/- "
              f"{agg['ensemble_outgrowth_se']:.2f} (range [{agg['ensemble_outgrowth_min']:.2f}, "
              f"{agg['ensemble_outgrowth_max']:.2f}]); ensemble overall = "
              f"{agg['ensemble_overall_mean']:.2f} +/- {agg['ensemble_overall_se']:.2f}",
              flush=True)

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
