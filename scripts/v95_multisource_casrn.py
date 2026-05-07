"""v95: Multi-source CASRN training to address single-source pi-estimator failure.

The previous CASRN (v83/v84_E1) trained the pi-estimator on UCSF source only,
which over-estimated pi for active-change cohorts (RHUH-GBM in particular,
where CASRN under-performed the learned baseline by 0.118 Brier).

This script trains a multi-source CASRN with the pi-estimator trained on
three source cohorts (UCSF + MU + RHUH; held-one-out via cohort-permutation
internally) instead of UCSF-only. For each held-out target cohort the
pi-estimator is trained on the remaining three cohorts' per-patient
statistics, then applied at test time.

Outputs:
  C:/Users/kamru/Downloads/Nature_project/05_results/v95_multisource_casrn.json
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

EPOCHS_UNET = 18
EPOCHS_PI = 12
BATCH = 6
SIGMA = 2.5
COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM", "UCSD-PTGBM"]


def patient_brier(pred, target):
    pred = np.clip(pred, 1e-6, 1 - 1e-6)
    return float(((pred - target) ** 2).mean())


class LightUNet3D(nn.Module):
    """Lightweight 3D feed-forward network for raw+mask 5-channel input.
    No skip connections — simpler than full U-Net but adequate for the
    routing-network demonstration."""

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


class PiEstimator(nn.Module):
    """Predicts pi_stable from cohort summary statistics."""

    def __init__(self, in_dim=8, hidden=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.GELU(),
            nn.Linear(hidden, hidden), nn.GELU(),
            nn.Linear(hidden, 1), nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


def cohort_features(raw, mask, heat, sdf):
    """Per-patient feature vector for pi-estimator."""
    return np.array([
        float(np.mean(raw)),
        float(np.std(raw)),
        float(np.mean(mask)),
        float(np.mean(heat)),
        float(np.mean(sdf)),
        float(np.percentile(raw, 95)),
        float(np.std(heat)),
        float(np.mean(mask) * np.mean(heat)),
    ], dtype=np.float32)


def main():
    print("=" * 78)
    print("v95 MULTI-SOURCE CASRN")
    print("=" * 78)
    cache = dict(np.load(CACHE, allow_pickle=True))
    cohorts_arr = cache["cohorts"]
    raw, mask, heat, sdf = cache["raw"], cache["mask"], cache["heat"], cache["sdf"]
    target = cache["target"]
    stable = cache["stable"]

    # Compute per-patient features
    print("Computing per-patient features...")
    feats = np.stack([cohort_features(raw[i], mask[i], heat[i], sdf[i])
                      for i in range(len(raw))])
    pi_per_cohort = {c: float(stable[cohorts_arr == c].mean()) for c in COHORTS}
    print(f"Per-cohort pi_stable: {pi_per_cohort}")

    results = []
    for held in COHORTS:
        print(f"\n--- LOCO held-out: {held} ---")
        train_idx = np.where(cohorts_arr != held)[0]
        test_idx = np.where(cohorts_arr == held)[0]
        print(f"  Train N={len(train_idx)}; Test N={len(test_idx)}")

        # Train multi-source pi-estimator on the three non-held cohorts'
        # patient features; target is the patient-level stable label.
        X_pi = torch.from_numpy(feats[train_idx]).float().to(DEVICE)
        y_pi = torch.from_numpy(stable[train_idx].astype(np.float32)).to(DEVICE)
        pi_model = PiEstimator(in_dim=X_pi.shape[1]).to(DEVICE)
        pi_opt = torch.optim.AdamW(pi_model.parameters(), lr=2e-3)
        bce_pi = nn.BCELoss()
        for ep in range(EPOCHS_PI):
            pi_model.train()
            pi_opt.zero_grad()
            pred = pi_model(X_pi)
            loss = bce_pi(pred, y_pi)
            loss.backward()
            pi_opt.step()
        pi_model.eval()
        with torch.no_grad():
            X_pi_test = torch.from_numpy(feats[test_idx]).float().to(DEVICE)
            pi_est = float(pi_model(X_pi_test).mean().item())

        # Train light U-Net on three non-held cohorts (raw+mask 5-channel)
        X_un = np.concatenate([raw[train_idx], mask[train_idx][:, None]], axis=1)
        Y_un = target[train_idx][:, None]
        X_un_t = torch.from_numpy(X_un).float()
        Y_un_t = torch.from_numpy(Y_un).float()
        loader = DataLoader(TensorDataset(X_un_t, Y_un_t), batch_size=BATCH, shuffle=True)
        unet = LightUNet3D(in_ch=5).to(DEVICE)
        opt = torch.optim.AdamW(unet.parameters(), lr=1e-3)
        bce = nn.BCEWithLogitsLoss()
        t0 = time.time()
        for ep in range(EPOCHS_UNET):
            unet.train()
            for xb, yb in loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits = unet(xb)
                loss = bce(logits, yb)
                opt.zero_grad(); loss.backward(); opt.step()
        print(f"  U-Net trained in {time.time()-t0:.0f}s")

        # Closed-form crossover routing: alpha = (pi_est - 0.43)+ clipped to [0,1]
        alpha = max(0.0, min(1.0, (pi_est - 0.0) / 1.0))  # naive: alpha = pi_est

        # Evaluate
        unet.eval()
        casrn_briers, learned_briers, heat_briers = [], [], []
        with torch.no_grad():
            for i in test_idx:
                xb = torch.from_numpy(np.concatenate([raw[i], mask[i][None]], axis=0)).float().unsqueeze(0).to(DEVICE)
                logits = unet(xb)
                p_learned = torch.sigmoid(logits).cpu().numpy()[0, 0]
                p_heat = heat[i]
                p_casrn = alpha * p_heat + (1 - alpha) * p_learned
                casrn_briers.append(patient_brier(p_casrn, target[i]))
                learned_briers.append(patient_brier(p_learned, target[i]))
                heat_briers.append(patient_brier(p_heat, target[i]))

        results.append({
            "held_out": held,
            "pi_observed": pi_per_cohort[held],
            "pi_estimated_multi_source": pi_est,
            "alpha_routing": alpha,
            "casrn_brier_mean": float(np.mean(casrn_briers)),
            "casrn_brier_sd": float(np.std(casrn_briers)),
            "learned_brier_mean": float(np.mean(learned_briers)),
            "learned_brier_sd": float(np.std(learned_briers)),
            "heat_brier_mean": float(np.mean(heat_briers)),
        })
        print(f"  pi_observed={pi_per_cohort[held]:.3f}  pi_est={pi_est:.3f}  alpha={alpha:.3f}")
        print(f"  CASRN={np.mean(casrn_briers):.4f}  learned={np.mean(learned_briers):.4f}  heat={np.mean(heat_briers):.4f}")

    out = {
        "version": "v95",
        "experiment": "Multi-source CASRN with pi-estimator trained on 3 source cohorts",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cohorts_per_pi_observed": pi_per_cohort,
        "results": results,
    }
    out_path = RESULTS / "v95_multisource_casrn.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
