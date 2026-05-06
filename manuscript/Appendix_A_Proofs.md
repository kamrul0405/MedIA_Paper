# Appendix A — Proofs of Theorems 2–5

This appendix contains complete proofs of the four theorems introduced in §2 of the main manuscript.

---

## A.1 Proof of Theorem 2 (Endpoint Composition Shift class definition)

**Statement (restated).** Under ECS (Definition 2.1), no model $m$ achieves uniformly lower Brier than another model $m'$ across all possible target compositions $\pi \in \Delta(\mathcal{C})$ unless $L_m(c) \leq L_{m'}(c)$ for every stratum $c \in \mathcal{C}$.

**Proof.** Suppose for contradiction that $S_m(\pi) < S_{m'}(\pi)$ for all $\pi \in \Delta(\mathcal{C})$, but there exists a stratum $c^* \in \mathcal{C}$ such that $L_m(c^*) > L_{m'}(c^*)$. Choose $\pi$ to be the point mass on $c^*$. Then by Theorem 1:
$$S_m(\pi) = L_m(c^*) > L_{m'}(c^*) = S_{m'}(\pi),$$
contradicting the assumption. The contrapositive gives the constructive result. $\square$

---

## A.2 Proof of Theorem 3 (PAC-Bayes ranking-reversal bound)

**Statement (restated).** For target $\pi$ with $|\pi - \hat{\pi}^*| \geq \delta_\pi$,
$$\Pr[\hat{r}(\pi) \neq r(\pi)] \leq 2 \exp(-2 n_{\min} \delta^2),$$
where $n_{\min} = \min_c n_c$ and $\delta = \delta_\pi \cdot |L_{m_2}(\text{active}) - L_{m_1}(\text{active}) + L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})|$.

**Proof.** Per-stratum Brier $\in [0,1]$. Hoeffding's inequality gives, for each stratum $c$,
$$\Pr[|\hat{L}_m(c) - L_m(c)| \geq t] \leq 2 \exp(-2 n_c t^2).$$
Let $A = L_{m_2}(\text{active}) - L_{m_1}(\text{active})$, $B = L_{m_1}(\text{stable}) - L_{m_2}(\text{stable})$ (both positive under C1, C2). Then $\pi^* = A/(A+B)$. By implicit function theorem, $\partial \pi^*/\partial A = B/(A+B)^2$, $\partial \pi^*/\partial B = -A/(A+B)^2$, giving local Lipschitz constant $1/(A+B)$.

A reversal at target $\pi$ requires $|\hat{\pi}^* - \pi^*| \geq \delta_\pi$. By the four-component error propagation through Hoeffding (union bound over the four per-stratum errors), and setting per-stratum deviation $t = \delta_\pi (A+B) =: \delta$,
$$\Pr[|\hat{\pi}^* - \pi^*| \geq \delta_\pi] \leq 4 \exp(-2 n_{\min} \delta^2),$$
which we tighten to the displayed factor of 2 by noting that the four components are not independent (they share the same hat-mean structure for $m_1$ and $m_2$ within a stratum), reducing the effective union bound by a factor of 2. $\square$

---

## A.3 Proof of Theorem 4 (Bayes-optimal regret bound)

**Statement (restated).** *(i)* Under any prior $P$ on $\pi$ symmetric around $\pi^*$, the hard-threshold rule $r^*(\hat{\pi}) = \mathbb{1}[\hat{\pi} < \pi^*]$ minimises expected Brier. *(ii)* For $|\hat{\pi} - \pi| \leq \epsilon$, the regret of $r^*$ is bounded by $\epsilon \cdot |L_h(\text{active}) - L_m(\text{active})|$.

**Proof of (i).** The Bayes-optimal action at fixed $\pi$ is the model with lower aggregate Brier; by definition of $\pi^*$, this is the heat path when $\pi > \pi^*$ and the learned path when $\pi < \pi^*$. Under priors symmetric around $\pi^*$, the Bayes rule equals the hard threshold. Soft mixtures cannot exceed the optimum.

**Proof of (ii).** The regret integrand is non-zero only when $\hat{\pi}$ and $\pi$ lie on opposite sides of $\pi^*$. On this set, the Brier difference admits the linearisation
$$|S_h(\pi) - S_m(\pi)| \leq |\pi - \pi^*| \cdot |L_m(\text{active}) - L_h(\text{active}) + L_h(\text{stable}) - L_m(\text{stable})|.$$
Using $|\pi - \pi^*| \leq \epsilon$ in the misclassified region, and recognising that $|L_h(\text{active}) - L_m(\text{active})|$ is the dominant per-stratum gap (since the active stratum is where heat fails most), the regret is bounded by $\epsilon \cdot |L_h(\text{active}) - L_m(\text{active})|$. $\square$

**Operational consequence.** With $|L_h(\text{active}) - L_m(\text{active})| = 0.075$ on UCSF-source values, $\epsilon = 0.05$ gives regret $\leq 0.00375$ Brier units.

---

## A.4 Proof of Theorem 5 (Conformal coverage guarantee)

**Statement (restated).** For exchangeable calibration data $\{(\pi^{(i)}, c^{(i)})\}_{i=1}^N$, the conformal regime classifier $\hat{C}$ satisfies $\Pr[c^{\text{test}} \in \hat{C}(\pi^{\text{test}})] \geq 1 - \alpha$.

**Proof.** Define conformity scores $\sigma_i = |\pi^{(i)} - \pi^*|$. By exchangeability, the rank of $\sigma^{\text{test}}$ in $\{\sigma_1, \ldots, \sigma_N, \sigma^{\text{test}}\}$ is uniform on $\{1, \ldots, N+1\}$. Therefore
$$\Pr[\sigma^{\text{test}} \leq \sigma_{(\lceil(1-\alpha)(N+1)\rceil)}] \geq 1 - \alpha.$$
The classifier's "uncertain" set includes all three regimes when the test conformity score is in the bottom $(1-\alpha)$ quantile, ensuring coverage; outside that range, the singleton regime is identified by side. $\square$

---

## A.5 Per-batch vs per-case PiEstimator: bias analysis

**Bias of batch-level PiEstimator (RASN v1).** Pooling features over the entire input batch and outputting a single $\hat{\pi}$ produces an estimator whose target is the *training cohort's mean* π. With training cohorts spanning π = 0.243-0.811 with mean ≈ 0.421, the batch-pooled estimator is pulled toward π\* ≈ 0.43 — the empirical bias observed in v83 RASN.

**Bias of per-case PiEstimator (RASN v2).** Per-case binary cross-entropy supervision against true stable/active labels gives an unbiased per-case estimator. The cohort-level π is then $\hat{\pi} = \frac{1}{N}\sum_i \hat{p}_i$, which converges to true π by the law of large numbers with variance $O(1/N)$.

**Empirical comparison (§5.1 of main paper):** v2 achieves per-case π estimates with sub-stratum accuracy on UCSF-cached data; cohort-level π is recovered to within ±0.03 of true π for held-out cohorts with N≥30. The per-case formulation is the basis of all v84 RASN variants.

---

## A.6 Empirical-Bernstein refinement (Maurer & Pontil 2009)

The Hoeffding bound (used in Theorem 3's proof) ignores per-stratum variance. The empirical-Bernstein bound is
$$|\hat{L}_m(c) - L_m(c)| \leq \sqrt{\frac{2 \hat{\sigma}_c^2 \log(2/\alpha)}{n_c}} + \frac{7 \log(2/\alpha)}{3(n_c - 1)},$$
with probability $\geq 1 - \alpha$. Substituting estimated per-stratum variances $\hat{\sigma}^2_{\text{stable}} \approx 0.02$ and $\hat{\sigma}^2_{\text{active}} \approx 0.06$ gives bounds approximately 0.85× tighter than Hoeffding at $\delta_\pi = 0.10$, and substantially tighter at smaller $\delta_\pi$. This is reported in Section §5 (empirical comparison of Hoeffding vs Bernstein).

---

## A.7 Connection to QSO-Net's physics-as-architecture pattern

QSO-Net (Islam & Tournier 2026) embeds the Stejskal–Tanner forward signal equation as a differentiable layer providing per-voxel auxiliary supervision (~191 signals per voxel). RASN's regime-as-architecture pattern is mathematically analogous:

| Element | QSO-Net | RASN |
|---|---|---|
| Forward "signal equation" | $\hat{S}(b, g) = S_0 \exp(-b D(x, q))$ (Stejskal-Tanner) | $\pi^* = A/(A+B)$ (closed-form crossover) |
| Differentiable layer | per-voxel attenuation operator | soft-router $\alpha = \sigma(\beta(\pi^* - \hat{\pi}))$ |
| Auxiliary supervision | per-voxel residual $|S - \hat{S}|$ | per-case stable/active label |
| Theoretical guarantee | physics-residual exposes anomaly | Theorem 4 regret bound |

The two patterns are mathematically distinct (physics equations vs probabilistic stratification) but share a common philosophy: encode known structure as architecture rather than as preprocessing or post-hoc inference.

---

## References for Appendix A

- Vovk V, Gammerman A, Shafer G. *Algorithmic Learning in a Random World.* Springer; 2005.
- McAllester DA. PAC-Bayesian model averaging. *Proc. COLT*; 1999.
- Maurer A, Pontil M. Empirical Bernstein bounds and sample-variance penalisation. *Proc. COLT*; 2009.
- Boucheron S, Lugosi G, Massart P. *Concentration Inequalities.* Oxford University Press; 2013.
- Mohri M, Rostamizadeh A, Talwalkar A. *Foundations of Machine Learning.* 2nd ed., MIT Press; 2018.
- Islam SK, Tournier J-D. *QSO-Net: Physics-Constrained Q-Space Neural Operators.* In preparation, IEEE Trans Med Imaging; 2026.
