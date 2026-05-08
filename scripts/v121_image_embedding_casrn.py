"""v121: Image-embedding CASRN — replaces the v110 per-patient feature-
aggregate pi-estimator input with a 3D CNN image embedding trained
jointly with the pi-estimator head.

Motivation: v110 (cohort-conditional CASRN) only partially closed the
RHUH-GBM regret gap (+0.118 -> +0.094, a 20% reduction). The
structural failure mode is information-bottleneck-like: per-patient
8-d feature aggregates cannot separate active-change patients from
the source-cohort training pool sufficiently to learn cohort-specific
pi predictions. This script tests whether a learned 3D CNN embedding
of the raw multi-channel volume closes the gap.

Architecture:
  - 3D CNN encoder: 5 -> 32 -> 64 -> 128 channels (stride-2 downsamples)
  - Global average pool over spatial dimensions -> 128-d embedding
  - 2-layer MLP head: 128 -> 64 -> 1 (sigmoid pi estimate)
  - Per-cohort one-hot residual (matching v110) concatenated to the
    embedding before the head
  - Joint training with cross-entropy on stable/active labels

Outputs:
    Nature_project/05_results/v121_image_embedding_casrn.json
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

EMBED_DIM = 128
EPOCHS_PI = 35
EPOCHS_UNET = 18
BATCH_PI = 8
BATCH_UNET = 6


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


class ImageEncoder3D(nn.Module):
    """5-channel input -> 128-d embedding via stride-2 downsamples + GAP."""

    def __init__(self, in_ch=5, embed_dim=EMBED_DIM):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv3d(in_ch, 32, 3, stride=2, padding=1),
            nn.GroupNorm(8, 32), nn.GELU(),
            nn.Conv3d(32, 64, 3, stride=2, padding=1),
            nn.GroupNorm(8, 64), nn.GELU(),
            nn.Conv3d(64, 128, 3, stride=2, padding=1),
            nn.GroupNorm(8, 128), nn.GELU(),
            nn.Conv3d(128, embed_dim, 3, padding=1),
            nn.GroupNorm(8, embed_dim), nn.GELU(),
        )
        self.pool = nn.AdaptiveAvgPool3d(1)

    def forward(self, x):
        h = self.encoder(x)
        z = self.pool(h).flatten(1)  # (B, embed_dim)
        return z


class ImageEmbeddingPiEstimator(nn.Module):
    def __init__(self, embed_dim=EMBED_DIM, n_cohorts=3, hidden=64):
        super().__init__()
        self.encoder = ImageEncoder3D(in_ch=5, embed_dim=embed_dim)
        self.head = nn.Sequential(
            nn.Linear(embed_dim + n_cohorts, hidden), nn.GELU(),
            nn.Linear(hidden, hidden), nn.GELU(),
            nn.Linear(hidden, 1), nn.Sigmoid(),
        )

    def forward(self, x, cohort_oh):
        z = self.encoder(x)
        z_cat = torch.cat([z, cohort_oh], dim=1)
        return self.head(z_cat).squeeze(-1)


def main():
    print("=" * 78)
    print("v121 IMAGE-EMBEDDING CASRN")
    print(f"  device: {DEVICE}; embed_dim={EMBED_DIM}")
    print(f"  pi-estimator epochs: {EPOCHS_PI}; U-Net epochs: {EPOCHS_UNET}")
    print("=" * 78)

    cache = dict(np.load(CACHE, allow_pickle=True))
    cohorts_arr = cache["cohorts"]
    raw, mask, target = cache["raw"], cache["mask"], cache["target"]
    heat, sdf = cache["heat"], cache["sdf"]
    stable = cache["stable"]

    pi_per_cohort = {c: float(stable[cohorts_arr == c].mean()) for c in COHORTS}
    print(f"Observed pi per cohort: {pi_per_cohort}")

    results = []
    for held in COHORTS:
        print(f"\n--- LOCO held-out: {held} ---")
        train_idx = np.where(cohorts_arr != held)[0]
        test_idx = np.where(cohorts_arr == held)[0]

        train_cohorts_present = [c for c in COHORTS if c != held]
        cohort_to_idx = {c: i for i, c in enumerate(train_cohorts_present)}

        # Stack 5-channel input (raw 4-channel + mask)
        X_train_full = np.concatenate([raw[train_idx], mask[train_idx][:, None]], axis=1)
        X_test_full = np.concatenate([raw[test_idx], mask[test_idx][:, None]], axis=1)
        y_train = stable[train_idx].astype(np.float32)
        y_target_train = target[train_idx][:, None].astype(np.float32)
        cohort_oh_train = np.zeros((len(train_idx), 3), dtype=np.float32)
        for ti, idx in enumerate(train_idx):
            cohort_oh_train[ti, cohort_to_idx[cohorts_arr[idx]]] = 1.0

        # Train the image-embedding pi-estimator
        pi_model = ImageEmbeddingPiEstimator(embed_dim=EMBED_DIM, n_cohorts=3).to(DEVICE)
        pi_opt = torch.optim.AdamW(pi_model.parameters(), lr=2e-4)
        bce = nn.BCELoss()

        Xt = torch.from_numpy(X_train_full).float()
        yt = torch.from_numpy(y_train).float()
        coh_t = torch.from_numpy(cohort_oh_train).float()
        loader = DataLoader(TensorDataset(Xt, yt, coh_t),
                            batch_size=BATCH_PI, shuffle=True)
        t0 = time.time()
        last_loss = None
        for ep in range(EPOCHS_PI):
            pi_model.train()
            losses = []
            for xb, yb, ob in loader:
                xb, yb, ob = xb.to(DEVICE), yb.to(DEVICE), ob.to(DEVICE)
                pred = pi_model(xb, ob)
                loss = bce(pred, yb)
                pi_opt.zero_grad(); loss.backward(); pi_opt.step()
                losses.append(loss.item())
            last_loss = np.mean(losses)
            if (ep + 1) % 5 == 0:
                print(f"  pi-estimator ep {ep+1}/{EPOCHS_PI}: train BCE = {last_loss:.4f}")
        print(f"  pi-estimator trained in {time.time()-t0:.0f}s; final BCE = {last_loss:.4f}")

        # Evaluate pi_est on the held-out cohort (cohort one-hot zero)
        pi_model.eval()
        coh_test_zero = torch.zeros((len(test_idx), 3), dtype=torch.float32).to(DEVICE)
        with torch.no_grad():
            X_test_t = torch.from_numpy(X_test_full).float().to(DEVICE)
            pi_est_per_patient = pi_model(X_test_t, coh_test_zero).cpu().numpy()
        pi_est = float(pi_est_per_patient.mean())

        # Train light U-Net (per v110)
        unet = LightUNet3D(in_ch=5).to(DEVICE)
        opt = torch.optim.AdamW(unet.parameters(), lr=1e-3)
        bce2 = nn.BCEWithLogitsLoss()
        loader_unet = DataLoader(TensorDataset(torch.from_numpy(X_train_full).float(),
                                                torch.from_numpy(y_target_train).float()),
                                  batch_size=BATCH_UNET, shuffle=True)
        t1 = time.time()
        for ep in range(EPOCHS_UNET):
            unet.train()
            for xb, yb in loader_unet:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits = unet(xb)
                loss = bce2(logits, yb)
                opt.zero_grad(); loss.backward(); opt.step()
        print(f"  U-Net trained in {time.time()-t1:.0f}s")

        # Routing alpha = pi_est
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

        learned_mean = float(np.mean(learned_briers))
        heat_mean = float(np.mean(heat_briers))
        casrn_mean = float(np.mean(casrn_briers))
        regret = casrn_mean - min(learned_mean, heat_mean)

        results.append({
            "held_out": held,
            "pi_observed": pi_per_cohort[held],
            "pi_estimated_image_embedding": pi_est,
            "pi_estimated_per_patient_std": float(pi_est_per_patient.std()),
            "alpha_routing": alpha,
            "casrn_brier_mean": casrn_mean,
            "casrn_brier_sd": float(np.std(casrn_briers)),
            "learned_brier_mean": learned_mean,
            "heat_brier_mean": heat_mean,
            "regret_vs_best_individual": regret,
        })
        best = "heat" if heat_mean < learned_mean else "learned"
        print(f"  pi_obs={pi_per_cohort[held]:.3f}  pi_est={pi_est:.3f}  alpha={alpha:.3f}")
        print(f"  CASRN={casrn_mean:.4f}  learned={learned_mean:.4f}  heat={heat_mean:.4f}")
        print(f"  best individual={best}; regret = {regret:+.4f}")

    out = {
        "version": "v121",
        "experiment": "Image-embedding CASRN with 3D CNN encoder + cohort one-hot residual",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "embed_dim": EMBED_DIM,
        "epochs_pi": EPOCHS_PI,
        "epochs_unet": EPOCHS_UNET,
        "cohorts_pi_observed": pi_per_cohort,
        "results": results,
    }

    out_path = RESULTS / "v121_image_embedding_casrn.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")

    # Summary comparison vs v95 / v110
    print("\n=== REGRET COMPARISON: v95 vs v110 vs v121 ===")
    v95_regrets = {
        "UCSF-POSTOP": 0.022, "MU-Glioma-Post": 0.002,
        "RHUH-GBM": 0.118, "UCSD-PTGBM": 0.005,
    }
    v110_regrets = {
        "UCSF-POSTOP": 0.015, "MU-Glioma-Post": 0.004,
        "RHUH-GBM": 0.094, "UCSD-PTGBM": -0.0016,
    }
    print(f"  {'Cohort':<20s} {'v95':>10s} {'v110':>10s} {'v121':>10s} {'delta-v110':>12s}")
    for r in results:
        c = r["held_out"]
        v121_reg = r["regret_vs_best_individual"]
        delta = v121_reg - v110_regrets[c]
        print(f"  {c:<20s} {v95_regrets[c]:>+10.4f} {v110_regrets[c]:>+10.4f} "
              f"{v121_reg:>+10.4f} {delta:>+12.4f}")


if __name__ == "__main__":
    main()
