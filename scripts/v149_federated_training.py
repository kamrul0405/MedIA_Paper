"""v149: Federated training simulation (FedAvg).

Simulates federated learning by training one U-Net per cohort
(UCSF, MU, RHUH) locally, then averaging weights via FedAvg
(McMahan et al. 2017). Tests LOCO on LUMIERE.

For comparison:
- v148 centralized (UCSF+MU train) -> LUMIERE: ens-out 67.69%
- v150 centralized (UCSF+MU+RHUH train) -> LUMIERE: ?
- v149 federated (UCSF+MU+RHUH FedAvg) -> LUMIERE: ?

Federated rounds:
  For round r in 1..R:
    For each client c:
      Initialize w_c <- w_global
      Train E_local epochs on local data
    w_global <- weighted average of w_c (weighted by n_c)

This simulates privacy-preserving multi-institutional collaboration.

Outputs:
    Nature_project/05_results/v149_federated_training.json
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
OUT_JSON = RESULTS / "v149_federated_training.json"
OUT_CSV = RESULTS / "v149_federated_per_patient.csv"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CLIENT_COHORTS = ["UCSF-POSTOP", "MU-Glioma-Post", "RHUH-GBM"]
TEST_COHORT = "LUMIERE"
SIGMA_BROAD = 7.0
N_ROUNDS = 5  # federated rounds
LOCAL_EPOCHS = 5  # per round per client
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


def local_train(model, data, epochs, batch_size=4):
    n = len(data)
    X = np.stack([np.stack([d["mask"], d["heat_bimodal"]], axis=0)
                   for d in data]).astype(np.float32)
    Y = np.stack([d["outgrowth"] for d in data]).astype(np.float32)[:, None]
    Xt = torch.from_numpy(X).to(DEVICE); Yt = torch.from_numpy(Y).to(DEVICE)
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


def fedavg(client_state_dicts, client_weights):
    """Federated averaging: weighted average of state dicts."""
    keys = list(client_state_dicts[0].keys())
    averaged = {}
    total_w = sum(client_weights)
    for k in keys:
        # Stack and weighted mean per-key
        stacked = torch.stack([sd[k].float() * (w / total_w)
                                for sd, w in zip(client_state_dicts, client_weights)])
        averaged[k] = stacked.sum(dim=0).to(client_state_dicts[0][k].dtype)
    return averaged


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
                "ensemble_overall": overall_coverage(d["fu"], ensemble_region),
                "ensemble_outgrowth": outgrowth_coverage(d["fu"], d["mask"], ensemble_region),
                "bimodal_outgrowth": outgrowth_coverage(d["fu"], d["mask"], bimodal_region),
            })
    return rows


def main():
    print("=" * 78, flush=True)
    print("v149 FEDERATED TRAINING SIMULATION (FedAvg)", flush=True)
    print(f"  device: {DEVICE}; clients: {CLIENT_COHORTS}", flush=True)
    print(f"  N_ROUNDS = {N_ROUNDS}; local_epochs = {LOCAL_EPOCHS}; seed = {SEED}",
          flush=True)
    print("=" * 78, flush=True)

    torch.manual_seed(SEED); np.random.seed(SEED)

    print("\nLoading cohorts...", flush=True)
    client_data = {}
    for cohort in CLIENT_COHORTS:
        client_data[cohort] = load_cohort(cohort)
        print(f"  client {cohort}: {len(client_data[cohort])} patients", flush=True)
    test_data = load_cohort(TEST_COHORT)
    print(f"  test {TEST_COHORT}: {len(test_data)} patients", flush=True)

    # Initialize global model
    global_model = UNet3D(in_ch=2, base=24).to(DEVICE)

    print(f"\n=== Federated training: {N_ROUNDS} rounds ===", flush=True)
    for r in range(N_ROUNDS):
        t0 = time.time()
        client_state_dicts = []
        client_weights = []
        for client in CLIENT_COHORTS:
            local_model = UNet3D(in_ch=2, base=24).to(DEVICE)
            local_model.load_state_dict(global_model.state_dict())
            local_train(local_model, client_data[client], LOCAL_EPOCHS)
            client_state_dicts.append({k: v.detach().clone()
                                         for k, v in local_model.state_dict().items()})
            client_weights.append(len(client_data[client]))
            del local_model; torch.cuda.empty_cache()
        # FedAvg
        averaged = fedavg(client_state_dicts, client_weights)
        global_model.load_state_dict(averaged)
        # Eval after each round
        rows = evaluate(global_model, test_data)
        ens_out = float(np.nanmean([r_row["ensemble_outgrowth"] for r_row in rows]) * 100)
        learned_out = float(np.nanmean([r_row["learned_outgrowth"] for r_row in rows]) * 100)
        ens_ovr = float(np.nanmean([r_row["ensemble_overall"] for r_row in rows]) * 100)
        print(f"  round {r+1}/{N_ROUNDS}: weights {client_weights}; "
              f"LUMIERE learned-out={learned_out:.2f}% ens-out={ens_out:.2f}% "
              f"ens-ovr={ens_ovr:.2f}% ({time.time()-t0:.0f}s)", flush=True)

    # Final eval
    print(f"\n=== Final federated model on LUMIERE ===", flush=True)
    final_rows = evaluate(global_model, test_data)
    learned_out = float(np.nanmean([r["learned_outgrowth"] for r in final_rows]) * 100)
    bim_out = float(np.nanmean([r["bimodal_outgrowth"] for r in final_rows]) * 100)
    ens_out = float(np.nanmean([r["ensemble_outgrowth"] for r in final_rows]) * 100)
    learned_ovr = float(np.nanmean([r["learned_overall"] for r in final_rows]) * 100)
    ens_ovr = float(np.nanmean([r["ensemble_overall"] for r in final_rows]) * 100)
    print(f"  learned:  overall {learned_ovr:5.2f}%  outgrowth {learned_out:5.2f}%",
          flush=True)
    print(f"  bimodal:  outgrowth {bim_out:5.2f}%", flush=True)
    print(f"  ensemble: overall {ens_ovr:5.2f}%  outgrowth {ens_out:5.2f}%",
          flush=True)

    # Comparison
    v141 = {"ens_out": 56.46, "ens_ovr": 65.39}
    v148 = {"ens_out": 67.69, "ens_ovr": 74.52}
    print(f"\n=== COMPARISON federated vs centralized on LUMIERE ===", flush=True)
    print(f"  v141 centralized (UCSF n=297):       ens-out 56.46%  ens-ovr 65.39%",
          flush=True)
    print(f"  v148 centralized (UCSF+MU n=448):    ens-out 67.69%  ens-ovr 74.52%",
          flush=True)
    print(f"  v149 federated  (UCSF+MU+RHUH 487):  ens-out {ens_out:.2f}%  "
          f"ens-ovr {ens_ovr:.2f}%", flush=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(final_rows[0].keys()))
        w.writeheader(); w.writerows(final_rows)
    print(f"\nWrote per-patient CSV: {OUT_CSV}", flush=True)

    out = {"version": "v149",
           "experiment": "Federated training simulation (FedAvg) across UCSF+MU+RHUH, test LUMIERE",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "client_cohorts": CLIENT_COHORTS,
           "test_cohort": TEST_COHORT,
           "n_rounds": N_ROUNDS,
           "local_epochs": LOCAL_EPOCHS,
           "seed": SEED,
           "client_n_patients": {c: len(client_data[c]) for c in CLIENT_COHORTS},
           "n_test": len(final_rows),
           "results_lumiere": {
               "learned_outgrowth_pct": learned_out,
               "bimodal_outgrowth_pct": bim_out,
               "ensemble_outgrowth_pct": ens_out,
               "learned_overall_pct": learned_ovr,
               "ensemble_overall_pct": ens_ovr,
           },
           "comparison": {
               "v141_centralized_ucsf_only": v141,
               "v148_centralized_ucsf_mu": v148,
               "v149_federated_ucsf_mu_rhuh": {
                   "ens_out": ens_out, "ens_ovr": ens_ovr,
               },
               "federated_vs_v148_centralized_ens_out_pp_diff": ens_out - v148["ens_out"],
               "federated_relative_to_v148_centralized_pct": (ens_out / v148["ens_out"] * 100),
           }}
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"Saved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
