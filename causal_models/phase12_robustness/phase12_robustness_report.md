# Phase 12: Statin Causal Forest Robustness and Sensitivity

This analysis reuses the saved Phase 11 test predictions and fitted models. It does not refit the forest, alter cohorts, or change split assignments.

## Propensity overlap

- Test complete-case sample: 499 patients (317 treated, 182 controls).
- Control propensity min/median/max: 0.084/0.633/0.799; treated: 0.083/0.713/0.828.
- Common support: [0.084, 0.799]. Outside support: 17 (3.4%). No observations were removed.
- Scores below 0.01 / above 0.99: 0 / 0; below 0.05 / above 0.95: 0 / 0; below 0.10 / above 0.90: 6 / 0.
- Quantile-level distributions by treatment arm are in `propensity_overlap.csv`; the plot preserves all observations.

## Weight and censoring diagnostics

- Untruncated treatment-IPW maximum: 12.10; overall ESS: 359.2 of 499. The top 1% of untruncated treatment weights contribute 4.6% of total weight.
- Stabilized censoring IPCW maximum: 1.45; the censoring risk set includes 725 records, with 499 observed outcomes and 226 incomplete follow-ups.
- Predicted P(observed follow-up) ranged 0.457–0.909 (median 0.680); observed-case stabilized IPCW p95/p99/max were 1.23/1.37/1.45.
- Combined treatment-IPW/IPCW maximum: 12.29; overall ESS: 366.4 of 499.
- Train-fitted censoring model test AUC: 0.636. This is a discrimination measure, not evidence that censoring is adequately controlled.
- 5th/95th percentile arm-wise truncation shifted the treatment-IPW point estimate by 0.85 pp and the combined-weight point estimate by 0.81 pp. Truncation changes the weighting estimator and can introduce bias.
- Truncating only the censoring-weight component at 5th/95th percentiles shifted the combined estimate by 0.10 percentage points.
- Complete weight distributions, arm-specific ESS, and top-1%-weight concentration are in `weight_diagnostics.csv`. Censor probabilities are summarized in `censoring_summary.json`.

## Estimator comparison

Risk differences are on the percentage-point scale. Bootstrap intervals use 1000 patient-level resamples; truncation limits are recomputed within each resample.

| estimator | risk_difference_pp | ci_lower_95_pp | ci_upper_95_pp | n | risk_set_n | incomplete_followup_n | excluded_from_test_split | treated_n | control_n | ess_all | ess_treated | ess_control | weighting_specification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CausalForestDML | 3.22 | -7.70 | 14.15 | 499 | 499 | 0 | 576 | 317 | 182 | - | - | - | No weights; existing Phase 11 fitted CausalForestDML |
| Propensity-IPW (none) | 5.12 | -5.22 | 15.14 | 499 | 499 | 0 | 576 | 317 | 182 | 359.2 | 206.9 | 155.6 | Untruncated |
| Treatment-IPW + IPCW, combined-weight truncation (none) | 4.75 | -5.07 | 14.53 | 499 | 725 | 226 | 350 | 317 | 182 | 366.4 | 214.6 | 154.6 | Untruncated |
| Propensity-IPW (p01_p99) | 5.42 | -5.05 | 15.38 | 499 | 499 | 0 | 576 | 317 | 182 | 371.5 | 223.0 | 155.7 | Arm-wise winsorization (0.01, 0.99) |
| Treatment-IPW + IPCW, combined-weight truncation (p01_p99) | 5.05 | -4.93 | 14.56 | 499 | 725 | 226 | 350 | 317 | 182 | 379.5 | 231.2 | 154.6 | Arm-wise winsorization (0.01, 0.99) |
| Treatment-IPW + IPCW, censor-component truncation (p01_p99) | 4.73 | -5.87 | 14.01 | 499 | 725 | 226 | 350 | 317 | 182 | 366.4 | 214.5 | 154.6 | Global censor-weight winsorization (0.01, 0.99) |
| Propensity-IPW (p05_p95) | 4.27 | -5.33 | 14.11 | 499 | 499 | 0 | 576 | 317 | 182 | 407.1 | 293.8 | 156.3 | Arm-wise winsorization (0.05, 0.95) |
| Treatment-IPW + IPCW, combined-weight truncation (p05_p95) | 3.94 | -5.25 | 12.95 | 499 | 725 | 226 | 350 | 317 | 182 | 412.2 | 288.4 | 155.4 | Arm-wise winsorization (0.05, 0.95) |
| Treatment-IPW + IPCW, censor-component truncation (p05_p95) | 4.65 | -6.03 | 13.98 | 499 | 725 | 226 | 350 | 317 | 182 | 366.0 | 214.1 | 154.7 | Global censor-weight winsorization (0.05, 0.95) |

CausalForestDML and unweighted propensity-IPW use the 499 observed-outcome complete-case test admissions. IPCW estimates use those 499 observed outcomes weighted to represent the 725-record test risk set with complete baseline features and known treatment; the estimands differ and rely on conditional independent censoring. No common-support trimming was applied.

## CATE distribution

- n=499; mean=0.0322, median=0.0343, SD=0.0458.
- p10=-0.0302; p25=0.0055; p75=0.0603; p90=0.0819.
- Stored population ATE 95% interval: [-0.0770340606514765, 0.1415172577902662]. Per-patient forest intervals are shown in `figures/cate_uncertainty.png`.
- Variation in predicted CATEs and subgroup patterns does not by itself establish clinically meaningful effect heterogeneity.

## Interpretation

All prespecified primary point estimates are positive.
All reported 95% intervals include zero. The current point estimates are directionally consistent, but weighting changes their magnitude and truncation sensitivity should be interpreted as a different weighting estimator.
Empirical overlap is substantial but not complete: most patients fall inside the observed common-support interval, while the reported outside-support fraction remains untrimmed in all estimates. No near-zero/near-one scores were observed at the prespecified 0.05/0.95 thresholds.
IPCW conclusions remain assumption-dependent. Censoring associations and the AUC do not verify conditional independent censoring; death remains a competing event coded as no recurrent MI by the horizon in this binary outcome. Patient bootstrap intervals hold saved nuisance-model predictions fixed and do not include uncertainty from estimating those models.

The experiment remains exploratory. `statin_during` is an in-hospital exposure, not proven initiation or adherence; the endpoint is MI-coded recurrence, not clinically adjudicated recurrence. These estimates do not establish a clinical causal effect. Estimates and confidence intervals are test-set/model-dependent, and the Phase 11 forest estimate interval was reused without refitting.

## Reproducibility

Run from the repository root with:

```powershell
.\.venv\Scripts\python.exe -m causal_models.phase12_robustness.analyze_statin_robustness
```

Bootstrap seed: 20261212; replicates: 1000.
