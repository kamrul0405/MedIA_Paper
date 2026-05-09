"""v150: Triple-cohort training (UCSF + MU + RHUH) -> LOCO test on LUMIERE.

Extends v148 (UCSF+MU train, n=448) by adding RHUH-GBM (n=39),
total training cohort n=487. Tests on LUMIERE LOCO (n=22).

Compare results across:
- v141 (UCSF train, n=297) -> LUMIERE: ens-out 56.46%
- v148 (UCSF+MU train, n=448) -> LUMIERE: ens-out 67.69%
- v150 (UCSF+MU+RHUH train, n=487) -> LUMIERE: ?

If outgrowth scales further with the addition of RHUH (small but
diverse cohort), it confirms a scaling-with-cohort-diversity law.

Outputs:
    Nature_project/05_results/v150_triple_cohort_training.json
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
OUT_JSON = RESULTS / "v150_triple_cohort_training.json"
OUT_CSV = RESULTS / "v150_triple_cohort_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

TRAIN_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM"]
TEST_LOCO = ["LUMIERE"]
SIGMA_BROAD = 7.0
EPOCHS = 25
LR = 1e-3
SEED = 42


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
        if (ep + 1) % 5 == 0:
            print(f"    epoch {ep+1}/{epochs}: avg loss = "
                  f"{float(loss.item()):.4f}", flush=True)
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
                "learned_overall": overall_coverage(d["fu"], pred_region),
                "learned_outgrowth": outgrowth_coverage(d["fu"], d["mask"], pred_region),
                "bimodal_overall": overall_coverage(d["fu"], bimodal_region),
                "bimodal_outgrowth": outgrowth_coverage(d["fu"], d["mask"], bimodal_region),
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
            })
    return rows


def main():
    print("=" * 78, flush=True)
    print(f"v150 TRIPLE-COHORT TRAINING ({' + '.join(TRAIN_COHORTS)} -> LUMIERE LOCO)",
          flush=True)
    print(f"  device: {DEVICE}; epochs={EPOCHS}; seed={SEED}", flush=True)
    print("=" * 78, flush=True)

    print("\nLoading cohorts...", flush=True)
    cohorts_data = {}
    for cohort in TRAIN_COHORTS + TEST_LOCO:
        cohorts_data[cohort] = load_cohort(cohort)
        print(f"  {cohort}: {len(cohorts_data[cohort])} patients", flush=True)

    train_data = []
    for c in TRAIN_COHORTS:
        train_data.extend(cohorts_data[c])
    print(f"\n  Combined training: {len(train_data)} patients", flush=True)

    t0 = time.time()
    model = train_unet(train_data, SEED)
    print(f"  training done in {time.time()-t0:.0f}s", flush=True)

    print(f"\n=== LOCO test on LUMIERE (N=22) ===", flush=True)
    rows = evaluate(model, cohorts_data["LUMIERE"])

    learned_out = float(np.nanmean([r["learned_outgrowth"] for r in rows]) * 100)
    bim_out = float(np.nanmean([r["bimodal_outgrowth"] for r in rows]) * 100)
    ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in rows]) * 100)
    learned_ovr = float(np.nanmean([r["learned_overall"] for r in rows]) * 100)
    ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in rows]) * 100)

    print(f"  learned:  overall {learned_ovr:5.2f}%  outgrowth {learned_out:5.2f}%",
          flush=True)
    print(f"  bimodal:  outgrowth {bim_out:5.2f}%", flush=True)
    print(f"  ensemble: overall {ens_ovr:5.2f}%  outgrowth {ens_out:5.2f}%",
          flush=True)

    # Comparison
    v141 = {"learned_out": 42.26, "bim_out": 46.24, "ens_out": 56.46,
            "learned_ovr": 18.35, "ens_ovr": 65.39}
    v148 = {"learned_out": 60.00, "bim_out": 46.24, "ens_out": 67.69,
            "learned_ovr": 30.56, "ens_ovr": 74.52}

    print(f"\n=== SCALING COMPARISON on LUMIERE (LOCO held-out) ===", flush=True)
    print(f"  {'Train':<25s} {'N':>4s} {'learn-out':>10s} {'ens-out':>10s} {'ens-ovr':>10s}",
          flush=True)
    print(f"  {'v141 UCSF':<25s} {297:>4d} {v141['learned_out']:>9.2f}% "
          f"{v141['ens_out']:>9.2f}% {v141['ens_ovr']:>9.2f}%", flush=True)
    print(f"  {'v148 UCSF+MU':<25s} {448:>4d} {v148['learned_out']:>9.2f}% "
          f"{v148['ens_out']:>9.2f}% {v148['ens_ovr']:>9.2f}%", flush=True)
    print(f"  {'v150 UCSF+MU+RHUH':<25s} {487:>4d} {learned_out:>9.2f}% "
          f"{ens_out:>9.2f}% {ens_ovr:>9.2f}%", flush=True)
    print(f"  {'gain v148->v150 (pp)':<25s} {'':>4s} "
          f"{learned_out - v148['learned_out']:>+9.2f} "
          f"{ens_out - v148['ens_out']:>+9.2f} "
          f"{ens_ovr - v148['ens_ovr']:>+9.2f}", flush=True)
    print(f"  {'gain v141->v150 (pp)':<25s} {'':>4s} "
          f"{learned_out - v141['learned_out']:>+9.2f} "
          f"{ens_out - v141['ens_out']:>+9.2f} "
          f"{ens_ovr - v141['ens_ovr']:>+9.2f}", flush=True)

    # Save per-patient CSV
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    out = {"version": "v150",
           "experiment": "Triple-cohort training (UCSF+MU+RHUH) -> LUMIERE LOCO",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "training_cohorts": TRAIN_COHORTS,
           "n_train": len(train_data),
           "test_cohort": "LUMIERE",
           "n_test": len(rows),
           "results_lumiere": {
               "learned_outgrowth_pct": learned_out,
               "bimodal_outgrowth_pct": bim_out,
               "ensemble_outgrowth_pct": ens_out,
               "learned_overall_pct": learned_ovr,
               "ensemble_overall_pct": ens_ovr,
           },
           "scaling_comparison_lumiere": {
               "v141_ucsf_only_n297": v141,
               "v148_ucsf_mu_n448": v148,
               "v150_ucsf_mu_rhuh_n487": {
                   "learned_out": learned_out, "ens_out": ens_out, "ens_ovr": ens_ovr,
               },
               "gain_v141_to_v150_ens_out_pp": ens_out - v141["ens_out"],
               "gain_v148_to_v150_ens_out_pp": ens_out - v148["ens_out"],
           },
           }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
