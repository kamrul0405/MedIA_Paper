"""v99: Cross-task generalisation pilot — closed-form composition-shift
crossover applied to a synthetic non-imaging task.

Demonstrates that the closed-form pi* framework (MedIA paper section 2.5) is
mathematically domain-agnostic by verifying it on a synthetic multi-cohort
longitudinal binary-outcome task constructed to mimic the MedIA mechanism:
  - Predictor m1 ('low-bias prior'): outputs a fixed mid-low value 0.30 for
    all inputs. Mid-low because the task's stable-class predictions should
    be near zero (most patients are stable in surveillance regimes).
  - Predictor m2 ('learned classifier'): a logistic-regression trained on a
    source cohort. Source training uses partial-label noise so the LR is
    imperfect and miscalibrated (this is what the MedIA learned-model
    classifier would face on out-of-distribution cohorts).

Per-stratum Brier values on the source cohort satisfy the closed-form
crossover identifiability conditions C1 and C2; pi* is computed; 7 target
cohorts at pi in {0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90} are tested.

Outputs:
  C:/Users/kamru/Downloads/Nature_project/05_results/v99_cross_task_pi_star.json
"""
import json
import time
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from scipy.stats import binomtest


ROOT = Path(r"C:\Users\kamru\Downloads\Nature_project")
RESULTS = ROOT / "05_results"
RNG = np.random.default_rng(9901)

LOW_BIAS_PRIOR_VALUE = 0.30  # constant-prior predictor output
LABEL_NOISE_RATE = 0.20  # source-training label noise (mimics overconfident learned classifier)


def synthesise_cohort(n: int, pi_stable: float, seed: int):
    """Synthesise a 16-d feature vector + binary outcome cohort."""
    rng = np.random.default_rng(seed)
    y = rng.binomial(1, 1 - pi_stable, size=n)  # 1 = active change
    mu_shift = 1.5
    X = rng.normal(0, 1, size=(n, 16))
    X[y == 1] += mu_shift
    return X, y


def low_bias_prior(X):
    """Constant low-mid prior; analogue of heat-kernel predicting moderate-low
    peri-lesional risk regardless of input."""
    return np.full(len(X), LOW_BIAS_PRIOR_VALUE)


def patient_brier(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(np.mean((p - y) ** 2))


def closed_form_pi_star(L_m1_s, L_m1_a, L_m2_s, L_m2_a):
    num = L_m2_a - L_m1_a
    den = (L_m2_a - L_m1_a) + (L_m1_s - L_m2_s)
    if den == 0:
        return float("nan")
    return num / den


def main():
    print("=" * 78)
    print("v99 CROSS-TASK GENERALISATION PILOT")
    print("=" * 78)
    print("Goal: demonstrate that the closed-form pi* framework is")
    print("      mathematically domain-agnostic. Synthetic non-imaging")
    print("      multi-cohort longitudinal binary-outcome task.")
    print()

    # --- Source cohort: train LR with label-noise injection ---
    n_source = 600
    pi_source = 0.5
    X_source, y_source = synthesise_cohort(n_source, pi_source, seed=9001)
    # Inject label noise to make the LR imperfect and overconfident-on-stable
    rng = np.random.default_rng(9002)
    flip_idx = rng.choice(n_source, size=int(LABEL_NOISE_RATE * n_source), replace=False)
    y_train_noisy = y_source.copy()
    y_train_noisy[flip_idx] = 1 - y_train_noisy[flip_idx]
    learned = LogisticRegression(max_iter=2000, C=0.1)  # mild regularisation
    learned.fit(X_source, y_train_noisy)

    # Evaluate per-stratum Brier on the *true* (non-noisy) source labels
    p_const_source = low_bias_prior(X_source)
    p_learned_source = learned.predict_proba(X_source)[:, 1]
    stable_idx = (y_source == 0)
    active_idx = (y_source == 1)
    L_m1_s = patient_brier(p_const_source[stable_idx], y_source[stable_idx])
    L_m1_a = patient_brier(p_const_source[active_idx], y_source[active_idx])
    L_m2_s = patient_brier(p_learned_source[stable_idx], y_source[stable_idx])
    L_m2_a = patient_brier(p_learned_source[active_idx], y_source[active_idx])

    print(f"Per-stratum Brier on source cohort (pi_source = {pi_source}, n = {n_source}):")
    print(f"  m1 (low-bias prior 0.3):  L_stable = {L_m1_s:.4f}    L_active = {L_m1_a:.4f}")
    print(f"  m2 (learned LR):          L_stable = {L_m2_s:.4f}    L_active = {L_m2_a:.4f}")

    c1 = L_m1_s < L_m2_s
    c2 = L_m1_a > L_m2_a
    print(f"\nIdentifiability:")
    print(f"  C1 (m1_stable < m2_stable): {c1}")
    print(f"  C2 (m1_active > m2_active): {c2}")

    if not (c1 and c2):
        print("\nWARNING: C1 and/or C2 do not hold. The closed-form crossover may not apply.")

    pi_star = closed_form_pi_star(L_m1_s, L_m1_a, L_m2_s, L_m2_a)
    print(f"\nClosed-form pi* = {pi_star:.4f}")
    print(f"  -> at pi > pi*, m1 (low-bias prior) is predicted to win;")
    print(f"  -> at pi < pi*, m2 (learned) is predicted to win.")

    # --- 7 target cohorts at varying pi ---
    target_pis = [0.10, 0.25, 0.40, 0.50, 0.60, 0.75, 0.90]
    n_target = 300
    cohort_results = []
    correct = 0

    print(f"\nEvaluating 7 target cohorts (n = {n_target} each):")
    for i, pi in enumerate(target_pis):
        X_t, y_t = synthesise_cohort(n_target, pi, seed=9100 + i)
        p_const = low_bias_prior(X_t)
        p_learned = learned.predict_proba(X_t)[:, 1]
        L_const = patient_brier(p_const, y_t)
        L_learned = patient_brier(p_learned, y_t)
        predicted_winner = "m1_low_bias" if pi > pi_star else "m2_learned"
        actual_winner = "m1_low_bias" if L_const < L_learned else "m2_learned"
        match = predicted_winner == actual_winner
        correct += int(match)
        cohort_results.append({
            "pi": pi,
            "L_m1_aggregate": float(L_const),
            "L_m2_aggregate": float(L_learned),
            "predicted_winner": predicted_winner,
            "actual_winner": actual_winner,
            "match": match,
        })
        marker = "OK" if match else "--"
        print(f"  pi={pi:.2f}  L_m1={L_const:.4f}  L_m2={L_learned:.4f}  "
              f"predicted={predicted_winner}  actual={actual_winner}  {marker}")

    accuracy = correct / len(target_pis)
    p_value = binomtest(correct, len(target_pis), 0.5, alternative="greater").pvalue

    print(f"\nDirectional accuracy: {correct}/{len(target_pis)} ({accuracy*100:.1f}%)")
    print(f"Binomial p-value (one-sided, p=0.5 null): {p_value:.4f}")

    out = {
        "version": "v99",
        "experiment": "Cross-task generalisation pilot — closed-form pi* on synthetic multi-cohort longitudinal task",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "task_type": "synthetic non-imaging longitudinal binary-outcome (16-d Gaussian; LR trained with 20% label noise)",
        "low_bias_prior_value": LOW_BIAS_PRIOR_VALUE,
        "label_noise_rate": LABEL_NOISE_RATE,
        "source_cohort_n": n_source,
        "source_cohort_pi": pi_source,
        "per_stratum_brier_source": {
            "L_m1_stable": float(L_m1_s),
            "L_m1_active": float(L_m1_a),
            "L_m2_stable": float(L_m2_s),
            "L_m2_active": float(L_m2_a),
        },
        "identifiability_C1": bool(c1),
        "identifiability_C2": bool(c2),
        "pi_star_predicted": float(pi_star),
        "target_cohort_n_per": n_target,
        "target_cohorts": cohort_results,
        "directional_accuracy": float(accuracy),
        "n_correct": correct,
        "n_total": len(target_pis),
        "binomial_p_value": float(p_value),
    }
    out_path = RESULTS / "v99_cross_task_pi_star.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
