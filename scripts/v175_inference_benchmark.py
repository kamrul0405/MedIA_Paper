"""v175: Inference cost benchmark for the universal foundation model.

Benchmarks deployment cost:
  - Single-pass forward inference time per patient (CPU and GPU)
  - 8-augmentation TTA inference time per patient (GPU)
  - 5-deep-ensemble inference time per patient (GPU)
  - Model size on disk (MB)
  - Trainable parameter count
  - Bimodal heat preprocessing time (CPU)

Required clinical-deployment-paper section.

Outputs:
    Nature_project/05_results/v175_inference_benchmark.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from scipy.ndimage import gaussian_filter

ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
OUT_JSON = RESULTS / "v175_inference_benchmark.json"

DEVICE_GPU = torch.device("cuda" if torch.cuda.is_available() else "cpu")
DEVICE_CPU = torch.device("cpu")
TARGET_SHAPE = (16, 48, 48)
SIGMA_BROAD = 7.0
N_PATIENTS = 50  # benchmark patients
N_AUGS = 8


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


def heat_constant(mask, sigma):
    if mask.sum() == 0: return np.zeros_like(mask, dtype=np.float32)
    h = gaussian_filter(mask.astype(np.float32), sigma=sigma)
    if h.max() > 0: h = h / h.max()
    return h.astype(np.float32)


def heat_bimodal(mask, sigma_broad):
    return np.maximum(mask.astype(np.float32),
                       heat_constant(mask, sigma_broad))


def main():
    print("=" * 78, flush=True)
    print("v175 INFERENCE COST BENCHMARK", flush=True)
    print(f"  N benchmark patients: {N_PATIENTS}", flush=True)
    print(f"  Target shape: {TARGET_SHAPE}", flush=True)
    print("=" * 78, flush=True)

    # Generate synthetic test masks (small lesions)
    print("\nGenerating synthetic test masks...", flush=True)
    rng = np.random.default_rng(17501)
    test_masks = []
    for i in range(N_PATIENTS):
        # Random sphere with center in middle, radius ~5 voxels
        m = np.zeros(TARGET_SHAPE, dtype=np.float32)
        cz, cy, cx = TARGET_SHAPE[0] // 2, TARGET_SHAPE[1] // 2, TARGET_SHAPE[2] // 2
        r = rng.integers(3, 8)
        for z in range(TARGET_SHAPE[0]):
            for y in range(TARGET_SHAPE[1]):
                for x in range(TARGET_SHAPE[2]):
                    if (z-cz)**2 + (y-cy)**2 + (x-cx)**2 <= r**2:
                        m[z, y, x] = 1.0
        test_masks.append(m)
    print(f"  Generated {len(test_masks)} synthetic masks", flush=True)

    # Bimodal heat preprocessing (CPU only)
    print(f"\n=== Step 1: Bimodal heat preprocessing (CPU) ===", flush=True)
    t0 = time.time()
    heat_maps = [heat_bimodal(m, SIGMA_BROAD) for m in test_masks]
    bimodal_total_s = time.time() - t0
    bimodal_per_patient_ms = (bimodal_total_s / N_PATIENTS) * 1000
    print(f"  Total: {bimodal_total_s:.2f}s for {N_PATIENTS} patients", flush=True)
    print(f"  Per-patient: {bimodal_per_patient_ms:.2f} ms (CPU)", flush=True)

    out = {"version": "v175",
           "experiment": "Inference cost benchmark",
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "device_gpu": str(DEVICE_GPU),
           "n_benchmark_patients": N_PATIENTS,
           "target_shape": list(TARGET_SHAPE),
           "bimodal_preprocessing_total_s": bimodal_total_s,
           "bimodal_preprocessing_per_patient_ms": bimodal_per_patient_ms,
           }

    # Initialize the foundation model
    print(f"\n=== Step 2: Foundation model size ===", flush=True)
    model = UNet3D(in_ch=2, base=24)
    n_params = sum(p.numel() for p in model.parameters())
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    # Estimate model size (4 bytes per fp32 parameter)
    model_size_mb = n_params * 4 / (1024 ** 2)
    print(f"  Total parameters: {n_params:,}", flush=True)
    print(f"  Trainable parameters: {n_trainable:,}", flush=True)
    print(f"  Estimated size on disk (fp32): {model_size_mb:.3f} MB", flush=True)
    out["n_parameters"] = n_params
    out["n_trainable"] = n_trainable
    out["model_size_mb_fp32"] = model_size_mb

    # CPU single-pass inference time
    print(f"\n=== Step 3: Single-pass inference (CPU) ===", flush=True)
    model_cpu = model.to(DEVICE_CPU).eval()
    # Warmup
    x_warmup = torch.from_numpy(np.stack([test_masks[0], heat_maps[0]], axis=0)
                                  )[None].float()
    with torch.no_grad():
        _ = model_cpu(x_warmup)

    t0 = time.time()
    with torch.no_grad():
        for i in range(N_PATIENTS):
            x = torch.from_numpy(np.stack([test_masks[i], heat_maps[i]], axis=0)
                                   )[None].float()
            _ = model_cpu(x)
    cpu_total_s = time.time() - t0
    cpu_per_patient_ms = (cpu_total_s / N_PATIENTS) * 1000
    print(f"  Total: {cpu_total_s:.2f}s for {N_PATIENTS} patients", flush=True)
    print(f"  Per-patient: {cpu_per_patient_ms:.2f} ms (CPU)", flush=True)
    out["cpu_single_pass_total_s"] = cpu_total_s
    out["cpu_single_pass_per_patient_ms"] = cpu_per_patient_ms

    # GPU single-pass inference time
    if DEVICE_GPU.type == "cuda":
        print(f"\n=== Step 4: Single-pass inference (GPU) ===", flush=True)
        model_gpu = model.to(DEVICE_GPU).eval()
        x_warmup_gpu = x_warmup.to(DEVICE_GPU)
        with torch.no_grad():
            for _ in range(3):
                _ = model_gpu(x_warmup_gpu)
        torch.cuda.synchronize()

        t0 = time.time()
        with torch.no_grad():
            for i in range(N_PATIENTS):
                x = torch.from_numpy(np.stack([test_masks[i], heat_maps[i]], axis=0)
                                       )[None].float().to(DEVICE_GPU)
                _ = model_gpu(x)
        torch.cuda.synchronize()
        gpu_total_s = time.time() - t0
        gpu_per_patient_ms = (gpu_total_s / N_PATIENTS) * 1000
        print(f"  Total: {gpu_total_s:.3f}s for {N_PATIENTS} patients", flush=True)
        print(f"  Per-patient: {gpu_per_patient_ms:.2f} ms (GPU)", flush=True)
        out["gpu_single_pass_total_s"] = gpu_total_s
        out["gpu_single_pass_per_patient_ms"] = gpu_per_patient_ms

        # GPU memory footprint
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        with torch.no_grad():
            x = torch.from_numpy(np.stack([test_masks[0], heat_maps[0]], axis=0)
                                   )[None].float().to(DEVICE_GPU)
            _ = model_gpu(x)
        peak_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
        print(f"  GPU peak memory (single inference): {peak_mb:.2f} MB", flush=True)
        out["gpu_peak_memory_mb_single"] = peak_mb

        # 8-augmentation TTA inference time
        print(f"\n=== Step 5: 8-augmentation TTA inference (GPU) ===", flush=True)
        AUGS = [[], [0], [1], [2], [0,1], [0,2], [1,2], [0,1,2]]
        t0 = time.time()
        with torch.no_grad():
            for i in range(N_PATIENTS):
                m = test_masks[i]; h = heat_maps[i]
                for axes in AUGS:
                    m_aug = m.copy()
                    h_aug = h.copy()
                    for ax in axes:
                        m_aug = np.flip(m_aug, axis=ax).copy()
                        h_aug = np.flip(h_aug, axis=ax).copy()
                    x = torch.from_numpy(np.stack([m_aug, h_aug], axis=0)
                                           )[None].float().to(DEVICE_GPU)
                    _ = model_gpu(x)
        torch.cuda.synchronize()
        tta_total_s = time.time() - t0
        tta_per_patient_ms = (tta_total_s / N_PATIENTS) * 1000
        print(f"  Total: {tta_total_s:.3f}s for {N_PATIENTS} patients × 8 augmentations",
              flush=True)
        print(f"  Per-patient (8 augs): {tta_per_patient_ms:.2f} ms", flush=True)
        out["gpu_tta_8augs_total_s"] = tta_total_s
        out["gpu_tta_8augs_per_patient_ms"] = tta_per_patient_ms

        # 5-deep-ensemble inference time (5 separate models)
        print(f"\n=== Step 6: 5-deep-ensemble inference (GPU) ===", flush=True)
        t0 = time.time()
        with torch.no_grad():
            for i in range(N_PATIENTS):
                # Simulate 5 ensemble members by re-running same model 5 times
                # (in production this would be 5 different model weights)
                x = torch.from_numpy(np.stack([test_masks[i], heat_maps[i]], axis=0)
                                       )[None].float().to(DEVICE_GPU)
                for _ in range(5):
                    _ = model_gpu(x)
        torch.cuda.synchronize()
        ens_total_s = time.time() - t0
        ens_per_patient_ms = (ens_total_s / N_PATIENTS) * 1000
        print(f"  Total: {ens_total_s:.3f}s for {N_PATIENTS} patients × 5 ensemble",
              flush=True)
        print(f"  Per-patient (5 ensemble): {ens_per_patient_ms:.2f} ms", flush=True)
        out["gpu_5_ensemble_total_s"] = ens_total_s
        out["gpu_5_ensemble_per_patient_ms"] = ens_per_patient_ms

    # Summary table
    print(f"\n=== SUMMARY ===", flush=True)
    print(f"  Foundation model:", flush=True)
    print(f"    Parameters: {n_params:,} (size {model_size_mb:.3f} MB)", flush=True)
    print(f"  Per-patient cost:", flush=True)
    print(f"    Bimodal preprocessing (CPU): {bimodal_per_patient_ms:.2f} ms",
          flush=True)
    print(f"    Single-pass forward (CPU):    {cpu_per_patient_ms:.2f} ms",
          flush=True)
    if DEVICE_GPU.type == "cuda":
        print(f"    Single-pass forward (GPU):    {gpu_per_patient_ms:.2f} ms",
              flush=True)
        print(f"    8-aug TTA (GPU):              {tta_per_patient_ms:.2f} ms",
              flush=True)
        print(f"    5-ensemble (GPU):             {ens_per_patient_ms:.2f} ms",
              flush=True)
        print(f"  GPU peak memory: {peak_mb:.2f} MB", flush=True)
    print(f"  Total deployment recipe (CPU bimodal + GPU single):", flush=True)
    if DEVICE_GPU.type == "cuda":
        total_deploy_ms = bimodal_per_patient_ms + gpu_per_patient_ms
        print(f"    {total_deploy_ms:.2f} ms per patient = "
              f"{1000 / total_deploy_ms:.1f} patients/sec at deployment", flush=True)
        out["deployment_total_per_patient_ms"] = total_deploy_ms
        out["deployment_throughput_patients_per_sec"] = 1000 / total_deploy_ms

    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
