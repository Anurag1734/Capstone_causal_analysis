# Phase 11: Initial statin causal analysis

Exploratory admission-level analysis of 12-month MI-coded recurrence in the selected prior-MI cohort.
The exposure is the existing in-hospital `statin_during` indicator, not confirmed initiation, discharge continuation, or adherence.

The run is exploratory; unresolved endpoint validation and treatment-timing assumptions are retained in `metrics.json` and do not support a clinical causal claim.

## Preliminary split counts

| Split | Admissions | Patients | Treated | Control | Tx missing | Tx prevalence* | Recurrent MI | Death | Event-free | Incomplete | Outcome prevalence** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 4882 | 4882 | 2086 | 1153 | 1643 | 0.644 | 1252 | 626 | 1462 | 1542 | 0.375 |
| validation | 1037 | 1037 | 429 | 263 | 345 | 0.620 | 260 | 131 | 317 | 329 | 0.367 |
| test | 1075 | 1075 | 471 | 254 | 350 | 0.650 | 261 | 149 | 336 | 329 | 0.350 |

* Treatment prevalence is among records with known treatment. ** Outcome prevalence is among records with observed follow-up.

- In the test subset with complete baseline covariates and known treatment, incomplete-follow-up rates were 28.3% for controls and 32.7% for treated admissions; the largest absolute covariate SMD comparing incomplete with observed follow-up was ckd (0.308).
- The train-fitted censoring model's test AUC was 0.636.

## Complete-case test estimates

- Test complete-case admissions: 499.
- Treatment prevalence: 0.635.
- Observed recurrent-MI prevalence: 0.337.
- Logistic outcome model: AUC 0.559, Brier 0.221, calibration slope 0.871.
- Logistic g-computation risk difference: 0.0418 (patient-cluster bootstrap 95% interval conditional on the fitted model; model-fit uncertainty is excluded: [0.041561517803794704, 0.04197797356707684]).
- Propensity-weighted risk difference: 0.0512 (patient-cluster bootstrap 95% interval [-0.045542138407476264, 0.13916531987016284]).
- CausalForestDML test ATE: 0.0322 (95% interval [-0.0770340606514765, 0.1415172577902662]).
- Test CATE mean/SD: 0.0322/0.0458; CATE quartiles: [0.005544423697929896, 0.03433178696588295, 0.06027654507643265].
- Test propensity common-support exclusion: 3.4%; maximum absolute SMD in the complete-case test set changed from 0.574 before weighting to 0.239 after weighting.
- IPCW plus treatment-IPW sensitivity risk difference: 0.0475 (patient-cluster bootstrap 95% interval [-0.052924802022855204, 0.14238421018773564]).

## Subgroup effects

| Subgroup | N | Treated | Control | Estimated risk difference (95% interval) |
|---|---:|---:|---:|---:|
| Age <65 | 170 | 103 | 67 | 0.0468 (-0.0642, 0.1578) |
| Age >=65 | 329 | 214 | 115 | 0.0247 (-0.0836, 0.1331) |
| Female | 219 | 135 | 84 | 0.0194 (-0.0838, 0.1226) |
| Male | 280 | 182 | 98 | 0.0423 (-0.0715, 0.1561) |
| Diabetes: no | 252 | 158 | 94 | 0.0227 (-0.0829, 0.1282) |
| Diabetes: yes | 247 | 159 | 88 | 0.0420 (-0.0710, 0.1550) |

## Sensitivity

- {'max_depth': 8, 'min_samples_leaf': 10}: test ATE 0.0309; CATE correlation with primary 0.929; mean absolute CATE difference 0.0234.
- include_statin_before_proxy: test ATE 0.0469; CATE correlation with primary 0.929; mean absolute CATE difference 0.0215.

## Limitations

- Complete-case estimates are exploratory; 12-month follow-up censoring is associated with observed treatment/covariates, and selection may bias estimates.
- IPCW assumes censoring is conditionally independent given the measured baseline variables and treatment and requires censoring positivity; it is a sensitivity analysis, not a correction guaranteed to remove bias.
- The outcome is based on MI-coded admissions. Death before recurrence is treated as a competing event and coded as no recurrence by the horizon for the binary cumulative-incidence estimand.
- Treatment timing within the admission is not known to precede index discharge; this is not a trial of discharge initiation and may not establish treatment-before-follow-up ordering.
- The existing master lacks baseline features for some eligible index admissions; the analysis uses admissions with a match and complete treatment/covariates/outcome.
- Estimates are not established clinical causal effects; conditional exchangeability, consistency, positivity, correct time ordering, accurate classification, and adequate censoring adjustment remain assumptions.

## Environment

- econml: 0.16.0
- numpy: 2.4.6
- scipy: 1.17.1
- scikit-learn: 1.6.1
- pandas: 3.0.6
- pyarrow: 25.0.1
- matplotlib: 3.11.2

Selected forest specification: `{'max_depth': 12, 'min_samples_leaf': 20}`.
