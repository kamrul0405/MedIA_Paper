"""v110: Cohort-conditional CASRN — extends v95 multi-source with explicit
cohort-indicator embeddings to attempt to fix the RHUH-GBM failure mode.

The v95 multi-source CASRN failed on RHUH-GBM (regret +0.128 over learned)
because the pi-estimator over-estimated π for active-change cohorts when
trained with cohort-pooled features. v110 adds:

  (a) one-hot cohort indicator concatenated to the per-patient feature
      vector for the pi-estimator;
  (b) a small two-layer MLP that maps the (features + cohort) representation
      to a cohort-conditional pi estimate;
  (c) train-time cohort dropout to prevent the pi-estimator from over-fitting
      to the single source distribution.

If v110 reduces RHUH-GBM regret while preserving UCSF/MU/UCSD performance,
the paper's main remaining limitation is closed.

Outputs:
    C:/Users/kamru/Downloads/Nature_project/05_results/v110_cohort_conditional_casrn.json
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
COHORT_DROPOUT = 0.3
EPOCHS_UNET = 18
EPOCHS_PI = 25
BATCH = 6


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
    """Per-patient features (8-d) + one-hot cohort (3-d for held-one-out
    LOCO; 3 train cohorts) -> sigmoid pi estimate."""

    def __init__(self, feat_dim=8, n_train_cohorts=3, hidden=64):
        super().__init__()
        self.feat_dim = feat_dim
        self.n_train_cohorts = n_train_cohorts
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


def main():
    print("=" * 78)
    print("v110 COHORT-CONDITIONAL CASRN")
    print(f"  cohort dropout = {COHORT_DROPOUT}")
    print("=" * 78)
    cache = dict(np.load(CACHE, allow_pickle=True))
    cohorts_arr = cache["cohorts"]
    raw, mask, heat, sdf = cache["raw"], cache["mask"], cache["heat"], cache["sdf"]
    target = cache["target"]
    stable = cache["stable"]

    # Compute features
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

        # Build cohort one-hot for train cohorts
        train_cohorts_present = [c for c in COHORTS if c != held]
        cohort_to_idx = {c: i for i, c in enumerate(train_cohorts_present)}

        # Train data: features + cohort one-hot
        train_cohort_oh = np.zeros((len(train_idx), 3), dtype=np.float32)
        for ti, idx in enumerate(train_idx):
            train_cohort_oh[ti, cohort_to_idx[cohorts_arr[idx]]] = 1.0
        # Apply cohort dropout: with prob COHORT_DROPOUT zero out the one-hot
        # so the pi-estimator learns to handle missing cohort identity
        rng = np.random.default_rng(11001)
        drop_mask = rng.random(len(train_idx)) < COHORT_DROPOUT
        train_cohort_oh_dropout = train_cohort_oh.copy()
        train_cohort_oh_dropout[drop_mask] = 0.0

        # Concatenate
        X_pi_train = np.concatenate([feats[train_idx], train_cohort_oh_dropout], axis=1)
        y_pi_train = stable[train_idx].astype(np.float32)

        # Test: cohort one-hot is zero (held-out cohort doesn't have a train index)
        X_pi_test = np.concatenate([feats[test_idx], np.zeros((len(test_idx), 3), dtype=np.float32)], axis=1)

        # Train pi-estimator
        pi_model = CohortConditionalPiEstimator(feat_dim=feats.shape[1],
                                                  n_train_cohorts=3).to(DEVICE)
        pi_opt = torch.optim.AdamW(pi_model.parameters(), lr=2e-3)
        bce = nn.BCELoss()
        Xt = torch.from_numpy(X_pi_train).float().to(DEVICE)
        yt = torch.from_numpy(y_pi_train).float().to(DEVICE)
        for ep in range(EPOCHS_PI):
            pi_model.train()
            pi_opt.zero_grad()
            pred = pi_model(Xt)
            loss = bce(pred, yt)
            loss.backward()
            pi_opt.step()
        pi_model.eval()
        with torch.no_grad():
            Xte = torch.from_numpy(X_pi_test).float().to(DEVICE)
            pi_est = float(pi_model(Xte).mean().item())

        # Train light U-Net (raw + mask 5-channel)
        X_un = np.concatenate([raw[train_idx], mask[train_idx][:, None]], axis=1)
        Y_un = target[train_idx][:, None]
        unet = LightUNet3D(in_ch=5).to(DEVICE)
        opt = torch.optim.AdamW(unet.parameters(), lr=1e-3)
        bce2 = nn.BCEWithLogitsLoss()
        loader = DataLoader(TensorDataset(torch.from_numpy(X_un).float(),
                                            torch.from_numpy(Y_un).float()),
                             batch_size=BATCH, shuffle=True)
        t0 = time.time()
        for ep in range(EPOCHS_UNET):
            unet.train()
            for xb, yb in loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits = unet(xb)
                loss = bce2(logits, yb)
                opt.zero_grad(); loss.backward(); opt.step()
        print(f"  U-Net trained in {time.time()-t0:.0f}s")

        # Routing alpha = pi_est (heat weight)
        alpha = max(0.0, min(1.0, pi_est))

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
            "pi_estimated_cohort_conditional": pi_est,
            "alpha_routing": alpha,
            "casrn_brier_mean": float(np.mean(casrn_briers)),
            "casrn_brier_sd": float(np.std(casrn_briers)),
            "learned_brier_mean": float(np.mean(learned_briers)),
            "heat_brier_mean": float(np.mean(heat_briers)),
            "regret_vs_best_individual": float(np.mean(casrn_briers) - min(np.mean(learned_briers), np.mean(heat_briers))),
        })
        best = "heat" if np.mean(heat_briers) < np.mean(learned_briers) else "learned"
        print(f"  pi_obs={pi_per_cohort[held]:.3f}  pi_est={pi_est:.3f}  alpha={alpha:.3f}")
        print(f"  CASRN={np.mean(casrn_briers):.4f}  learned={np.mean(learned_briers):.4f}  heat={np.mean(heat_briers):.4f}  best individual={best}")

    out = {
        "version": "v110",
        "experiment": "Cohort-conditional CASRN with cohort-dropout-trained pi-estimator",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cohort_dropout_rate": COHORT_DROPOUT,
        "cohorts_pi_observed": pi_per_cohort,
        "results": results,
    }
    out_path = RESULTS / "v110_cohort_conditional_casrn.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
