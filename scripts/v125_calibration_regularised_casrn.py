"""v125: Calibration-regularised CASRN — adds explicit penalty on
the per-test-batch mean pi-estimator output, drawing it toward the
training-cohort observed pi mean.

Motivation. v121 showed that scaling embedding capacity (3D CNN
encoder, 128-d image embedding) makes the RHUH-GBM regret WORSE
(+0.094 -> +0.133). The pi-estimator memorises source-cohort
distributions. v125 tests an alternative remedy: instead of more
capacity, explicit calibration regularisation that penalises the
pi-estimator from drifting too far from the training-cohort
observed pi mean.

Method:
  - Use the v110 architecture (cohort-conditional MLP with
    cohort-dropout 0.3).
  - Compute pi_train_mean across the training-cohort observed
    stable rate.
  - At training time, add penalty: lambda * (mean(pi_hat_batch) -
    pi_train_mean)^2.
  - This is a population-level calibration constraint; it does not
    use the held-out cohort's labels (no information leak).

If RHUH-GBM regret CI excludes zero (or just markedly improves),
this is a publishable methodology contribution for Proposal D
(federated CASRN with calibration constraints).

Outputs:
    Nature_project/05_results/v125_calibration_regularised_casrn.json
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

LAMBDA_CAL = 5.0      # calibration-regularisation strength
COHORT_DROPOUT = 0.3
EPOCHS_PI = 30
EPOCHS_UNET = 18
BATCH_PI = 16
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


def main():
    print("=" * 78)
    print("v125 CALIBRATION-REGULARISED CASRN")
    print(f"  device: {DEVICE}")
    print(f"  cohort_dropout = {COHORT_DROPOUT}; lambda_cal = {LAMBDA_CAL}")
    print(f"  pi-estimator epochs: {EPOCHS_PI}; U-Net epochs: {EPOCHS_UNET}")
    print("=" * 78)

    cache = dict(np.load(CACHE, allow_pickle=True))
    cohorts_arr = cache["cohorts"]
    raw, mask, heat, sdf = cache["raw"], cache["mask"], cache["heat"], cache["sdf"]
    target = cache["target"]
    stable = cache["stable"]

    print("Computing per-patient features...")
    feats = np.stack([cohort_features(raw[i], mask[i], heat[i], sdf[i])
                       for i in range(len(raw))])

    pi_per_cohort = {c: float(stable[cohorts_arr == c].mean()) for c in COHORTS}
    print(f"Observed pi per cohort: {pi_per_cohort}")

    results = []
    for held in COHORTS:
        print(f"\n--- LOCO held-out: {held} ---")
        train_idx = np.where(cohorts_arr != held)[0]
        test_idx = np.where(cohorts_arr == held)[0]
        train_cohorts_present = [c for c in COHORTS if c != held]
        cohort_to_idx = {c: i for i, c in enumerate(train_cohorts_present)}

        # Training-cohort overall pi mean (target for calibration regulariser)
        pi_train_mean = float(stable[train_idx].mean())
        print(f"  pi_train_mean (calibration target) = {pi_train_mean:.4f}")

        # Build cohort one-hot for train, with cohort dropout
        train_cohort_oh = np.zeros((len(train_idx), 3), dtype=np.float32)
        for ti, idx in enumerate(train_idx):
            train_cohort_oh[ti, cohort_to_idx[cohorts_arr[idx]]] = 1.0
        rng = np.random.default_rng(12501)
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
            ep_loss_bce = 0.0
            ep_loss_cal = 0.0
            n_batches = 0
            for xb, yb in loader:
                pred = pi_model(xb)
                loss_bce = bce(pred, yb)
                # Calibration penalty: pull batch-mean pi_hat toward
                # training-cohort observed pi mean
                cal_target = torch.tensor(pi_train_mean, device=DEVICE,
                                            dtype=torch.float32)
                loss_cal = (pred.mean() - cal_target) ** 2
                loss = loss_bce + LAMBDA_CAL * loss_cal
                pi_opt.zero_grad(); loss.backward(); pi_opt.step()
                ep_loss_bce += float(loss_bce.item())
                ep_loss_cal += float(loss_cal.item())
                n_batches += 1
            if (ep + 1) % 5 == 0:
                print(f"  ep {ep+1}/{EPOCHS_PI}: BCE = {ep_loss_bce/n_batches:.4f} "
                      f"cal_pen = {ep_loss_cal/n_batches:.5f}")

        pi_model.eval()
        with torch.no_grad():
            Xte = torch.from_numpy(X_pi_test).float().to(DEVICE)
            pi_est_per_patient = pi_model(Xte).cpu().numpy()
            pi_est = float(pi_est_per_patient.mean())

        # Train light U-Net (5-channel raw + mask)
        X_un = np.concatenate([raw[train_idx], mask[train_idx][:, None]], axis=1)
        Y_un = target[train_idx][:, None]
        unet = LightUNet3D(in_ch=5).to(DEVICE)
        opt = torch.optim.AdamW(unet.parameters(), lr=1e-3)
        bce2 = nn.BCEWithLogitsLoss()
        loader2 = DataLoader(TensorDataset(torch.from_numpy(X_un).float(),
                                             torch.from_numpy(Y_un).float()),
                               batch_size=BATCH_UNET, shuffle=True)
        t0 = time.time()
        for ep in range(EPOCHS_UNET):
            unet.train()
            for xb, yb in loader2:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits = unet(xb)
                loss = bce2(logits, yb)
                opt.zero_grad(); loss.backward(); opt.step()
        print(f"  U-Net trained in {time.time()-t0:.0f}s")

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
            "pi_train_mean_calibration_target": pi_train_mean,
            "pi_estimated_calibrated": pi_est,
            "pi_estimated_per_patient_std": float(pi_est_per_patient.std()),
            "alpha_routing": alpha,
            "casrn_brier_mean": casrn_mean,
            "learned_brier_mean": learned_mean,
            "heat_brier_mean": heat_mean,
            "regret_vs_best_individual": regret,
        })
        best = "heat" if heat_mean < learned_mean else "learned"
        print(f"  pi_obs={pi_per_cohort[held]:.3f}  pi_train_mean={pi_train_mean:.3f}  "
              f"pi_est={pi_est:.3f}  alpha={alpha:.3f}")
        print(f"  CASRN={casrn_mean:.4f}  learned={learned_mean:.4f}  heat={heat_mean:.4f}")
        print(f"  best individual={best}; regret = {regret:+.4f}")

    out = {
        "version": "v125",
        "experiment": ("Calibration-regularised CASRN with lambda * "
                       "(mean_pi_hat - pi_train_mean)^2 penalty"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "lambda_cal": LAMBDA_CAL,
        "cohort_dropout": COHORT_DROPOUT,
        "epochs_pi": EPOCHS_PI,
        "epochs_unet": EPOCHS_UNET,
        "cohorts_pi_observed": pi_per_cohort,
        "results": results,
    }

    out_path = RESULTS / "v125_calibration_regularised_casrn.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")

    # Summary comparison
    print("\n=== REGRET COMPARISON: v95 vs v110 vs v121 vs v125 ===")
    v95 = {"UCSF-POSTOP": 0.022, "MU-Glioma-Post": 0.002,
           "RHUH-GBM": 0.118, "UCSD-PTGBM": 0.005}
    v110 = {"UCSF-POSTOP": 0.015, "MU-Glioma-Post": 0.004,
            "RHUH-GBM": 0.094, "UCSD-PTGBM": -0.0016}
    v121 = {"UCSF-POSTOP": 0.023, "MU-Glioma-Post": 0.016,
            "RHUH-GBM": 0.133, "UCSD-PTGBM": 0.003}
    print(f"  {'Cohort':<20s} {'v95':>10s} {'v110':>10s} {'v121':>10s} "
          f"{'v125':>10s} {'delta-v110':>12s}")
    for r in results:
        c = r["held_out"]
        v125_reg = r["regret_vs_best_individual"]
        delta = v125_reg - v110[c]
        print(f"  {c:<20s} {v95[c]:>+10.4f} {v110[c]:>+10.4f} "
              f"{v121[c]:>+10.4f} {v125_reg:>+10.4f} {delta:>+12.4f}")


if __name__ == "__main__":
    main()
