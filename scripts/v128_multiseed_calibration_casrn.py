"""v128: Multi-seed replication of v125 calibration-regularised CASRN.

Motivation. v125 found RHUH-GBM regret of +0.049 vs v110's +0.094, a
52% reduction. The honest caveat was that the learned-model U-Net
seed varies between runs and could account for some of the
improvement. v128 runs 3 seeds (42, 123, 999) for both the
pi-estimator and the U-Net, reporting mean +/- SE per cohort.

If the seed-averaged RHUH-GBM regret is markedly < +0.094 (v110's
value), the calibration-regulariser remedy is robust to seed
variation and the 52% reduction is real.

Outputs:
    Nature_project/05_results/v128_multiseed_calibration_casrn.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
CACHE = RESULTS / "v78_raw_mri_loco_cache.npz"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]

LAMBDA_CAL = 5.0
COHORT_DROPOUT = 0.3
EPOCHS_PI = 30
EPOCHS_UNET = 18
BATCH_PI = 16
BATCH_UNET = 6
SEEDS = [42, 123, 999]


def patient_brier(pred, target):
    pred = np.clip(pred, 1e-6, 1 - 1e-6)
    return float(((pred - target) ** 2).mean())


class LightUNet3D(nn.Module):
    def __init__(self, in_ch=5, base=24):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv3d(in_ch, base, 3, padding=1), nn.GroupNorm(8, base), nn.GELU(),
            nn.Conv3d(base, base * 2, 3, padding=1), nn.GroupNorm(8, base * 2), nn.GELU(),
            nn.Conv3d(base * 2, base * 2, 3, padding=1), nn.GroupNorm(8, base * 2), nn.GELU(),
            nn.Conv3d(base * 2, base, 3, padding=1), nn.GroupNorm(8, base), nn.GELU(),
            nn.Conv3d(base, 1, 1),
        )

    def forward(self, x):
        return self.net(x)


class CohortConditionalPiEstimator(nn.Module):
    def __init__(self, feat_dim=8, n_train_cohorts=3, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(feat_dim + n_train_cohorts, hidden), nn.GELU(),
            nn.Linear(hidden, hidden), nn.GELU(),
            nn.Linear(hidden, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def cohort_features(raw, mask, heat, sdf):
    return np.array([
        float(np.mean(raw)), float(np.std(raw)),
        float(np.mean(mask)), float(np.mean(heat)),
        float(np.mean(sdf)), float(np.percentile(raw, 95)),
        float(np.std(heat)), float(np.mean(mask) * np.mean(heat)),
    ], dtype=np.float32)


def run_seed(seed, cache, feats, pi_per_cohort):
    torch.manual_seed(seed)
    np.random.seed(seed)

    cohorts_arr = cache["cohorts"]
    raw, mask, heat = cache["raw"], cache["mask"], cache["heat"]
    target = cache["target"]
    stable = cache["stable"]

    seed_results = []
    for held in COHORTS:
        train_idx = np.where(cohorts_arr != held)[0]
        test_idx = np.where(cohorts_arr == held)[0]
        train_cohorts_present = [c for c in COHORTS if c != held]
        cohort_to_idx = {c: i for i, c in enumerate(train_cohorts_present)}

        pi_train_mean = float(stable[train_idx].mean())

        train_cohort_oh = np.zeros((len(train_idx), 3), dtype=np.float32)
        for ti, idx in enumerate(train_idx):
            train_cohort_oh[ti, cohort_to_idx[cohorts_arr[idx]]] = 1.0
        rng = np.random.default_rng(seed + 1000)
        drop_mask = rng.random(len(train_idx)) < COHORT_DROPOUT
        train_cohort_oh[drop_mask] = 0.0

        X_pi_train = np.concatenate([feats[train_idx], train_cohort_oh], axis=1)
        y_pi_train = stable[train_idx].astype(np.float32)
        X_pi_test = np.concatenate(
            [feats[test_idx], np.zeros((len(test_idx), 3), dtype=np.float32)], axis=1)

        pi_model = CohortConditionalPiEstimator(feat_dim=feats.shape[1],
                                                  n_train_cohorts=3).to(DEVICE)
        pi_opt = torch.optim.AdamW(pi_model.parameters(), lr=2e-3)
        bce = nn.BCELoss()
        Xt = torch.from_numpy(X_pi_train).float().to(DEVICE)
        yt = torch.from_numpy(y_pi_train).float().to(DEVICE)
        loader = DataLoader(TensorDataset(Xt, yt), batch_size=BATCH_PI, shuffle=True)

        for ep in range(EPOCHS_PI):
            pi_model.train()
            for xb, yb in loader:
                pred = pi_model(xb)
                loss_bce = bce(pred, yb)
                cal_target = torch.tensor(pi_train_mean, device=DEVICE,
                                           dtype=torch.float32)
                loss_cal = (pred.mean() - cal_target) ** 2
                loss = loss_bce + LAMBDA_CAL * loss_cal
                pi_opt.zero_grad(); loss.backward(); pi_opt.step()

        pi_model.eval()
        with torch.no_grad():
            Xte = torch.from_numpy(X_pi_test).float().to(DEVICE)
            pi_est = float(pi_model(Xte).mean().item())

        X_un = np.concatenate([raw[train_idx], mask[train_idx][:, None]], axis=1)
        Y_un = target[train_idx][:, None]
        unet = LightUNet3D(in_ch=5).to(DEVICE)
        opt = torch.optim.AdamW(unet.parameters(), lr=1e-3)
        bce2 = nn.BCEWithLogitsLoss()
        loader2 = DataLoader(TensorDataset(torch.from_numpy(X_un).float(),
                                             torch.from_numpy(Y_un).float()),
                               batch_size=BATCH_UNET, shuffle=True)
        for ep in range(EPOCHS_UNET):
            unet.train()
            for xb, yb in loader2:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits = unet(xb)
                loss = bce2(logits, yb)
                opt.zero_grad(); loss.backward(); opt.step()

        alpha = max(0.0, min(1.0, pi_est))
        unet.eval()
        casrn_briers, learned_briers, heat_briers = [], [], []
        with torch.no_grad():
            for i in test_idx:
                xb = torch.from_numpy(np.concatenate([raw[i], mask[i][None]],
                                                       axis=0)).float().unsqueeze(0).to(DEVICE)
                logits = unet(xb)
                p_learned = torch.sigmoid(logits).cpu().numpy()[0, 0]
                p_heat = heat[i]
                p_casrn = alpha * p_heat + (1 - alpha) * p_learned
                casrn_briers.append(patient_brier(p_casrn, target[i]))
                learned_briers.append(patient_brier(p_learned, target[i]))
                heat_briers.append(patient_brier(p_heat, target[i]))

        learned_mean = float(np.mean(learned_briers))
        heat_mean = float(np.mean(heat_briers))
        casrn_mean = float(np.mean(casrn_briers))
        regret = casrn_mean - min(learned_mean, heat_mean)

        seed_results.append({
            "seed": seed,
            "held_out": held,
            "pi_observed": pi_per_cohort[held],
            "pi_train_mean": pi_train_mean,
            "pi_est": pi_est,
            "casrn_brier": casrn_mean,
            "learned_brier": learned_mean,
            "heat_brier": heat_mean,
            "regret": regret,
        })
        print(f"  seed={seed} {held:18s}: pi_est={pi_est:.3f} "
              f"CASRN={casrn_mean:.4f} learned={learned_mean:.4f} "
              f"heat={heat_mean:.4f} regret={regret:+.4f}")
    return seed_results


def main():
    print("=" * 78)
    print("v128 MULTI-SEED v125 CALIBRATION-REGULARISED CASRN")
    print(f"  device: {DEVICE}; seeds: {SEEDS}")
    print(f"  lambda_cal = {LAMBDA_CAL}; cohort_dropout = {COHORT_DROPOUT}")
    print("=" * 78)

    cache = dict(np.load(CACHE, allow_pickle=True))
    raw, mask, heat, sdf = cache["raw"], cache["mask"], cache["heat"], cache["sdf"]
    stable = cache["stable"]
    cohorts_arr = cache["cohorts"]

    feats = np.stack([cohort_features(raw[i], mask[i], heat[i], sdf[i])
                       for i in range(len(raw))])
    pi_per_cohort = {c: float(stable[cohorts_arr == c].mean()) for c in COHORTS}

    all_results = []
    for seed in SEEDS:
        print(f"\n--- seed = {seed} ---")
        t0 = time.time()
        seed_res = run_seed(seed, cache, feats, pi_per_cohort)
        all_results.extend(seed_res)
        print(f"  seed {seed} done in {time.time()-t0:.0f}s")

    # Aggregate per-cohort: mean +/- SE across seeds
    print("\n=== MULTI-SEED AGGREGATE (mean +/- SE across 3 seeds) ===")
    agg = {}
    for c in COHORTS:
        cohort_rows = [r for r in all_results if r["held_out"] == c]
        regrets = np.array([r["regret"] for r in cohort_rows])
        casrns = np.array([r["casrn_brier"] for r in cohort_rows])
        learneds = np.array([r["learned_brier"] for r in cohort_rows])
        heats = np.array([r["heat_brier"] for r in cohort_rows])
        pi_ests = np.array([r["pi_est"] for r in cohort_rows])
        agg[c] = {
            "n_seeds": len(SEEDS),
            "regret_mean": float(regrets.mean()),
            "regret_se": float(regrets.std(ddof=1) / np.sqrt(len(SEEDS))),
            "regret_min": float(regrets.min()),
            "regret_max": float(regrets.max()),
            "casrn_brier_mean": float(casrns.mean()),
            "casrn_brier_se": float(casrns.std(ddof=1) / np.sqrt(len(SEEDS))),
            "learned_brier_mean": float(learneds.mean()),
            "learned_brier_se": float(learneds.std(ddof=1) / np.sqrt(len(SEEDS))),
            "heat_brier_mean": float(heats.mean()),
            "pi_est_mean": float(pi_ests.mean()),
            "pi_est_se": float(pi_ests.std(ddof=1) / np.sqrt(len(SEEDS))),
        }
        print(f"  {c:18s}: regret = {regrets.mean():+.4f} +/- {regrets.std(ddof=1)/np.sqrt(len(SEEDS)):.4f} "
              f"(range [{regrets.min():+.4f}, {regrets.max():+.4f}])")

    # Compare to v110 baseline
    print("\n=== COMPARISON vs v110 (single-seed) ===")
    v110 = {"UCSF-POSTOP": 0.015, "MU-Glioma-Post": 0.004,
            "RHUH-GBM": 0.094, "UCSD-PTGBM": -0.0016}
    for c in COHORTS:
        delta = agg[c]["regret_mean"] - v110[c]
        marker = "**WIN**" if delta < -0.01 else ("**LOSS**" if delta > 0.01 else "")
        print(f"  {c:18s}: v128_seed_mean = {agg[c]['regret_mean']:+.4f} "
              f"vs v110 = {v110[c]:+.4f}, delta = {delta:+.4f} {marker}")

    out = {
        "version": "v128",
        "experiment": ("Multi-seed (42/123/999) v125 calibration-regularised CASRN "
                       "for robustness audit"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seeds": SEEDS,
        "lambda_cal": LAMBDA_CAL,
        "cohort_dropout": COHORT_DROPOUT,
        "per_seed_results": all_results,
        "aggregate": agg,
        "v110_baseline": v110,
    }
    OUT = RESULTS / "v128_multiseed_calibration_casrn.json"
    OUT.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT}")


if __name__ == "__main__":
    main()
