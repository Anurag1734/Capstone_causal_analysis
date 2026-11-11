# Phase 16 final statin results

## Estimation decision

No new treatment-effect estimation was performed. The finalized endpoint is not sufficiently validated, `statin_during` is not a discharge-initiation assignment and is not timestamped for all exposed admissions, and no fully observed pre-treatment adjustment set establishes exchangeability. The requested final estimate is therefore **not approved as a substantive or causal paper result**. Existing Phase 11–12 results are retained solely as exploratory model outputs.

## Previously saved exploratory estimates

These are reused, not recomputed. Phase 11 numbers below are saved test-set results on 499 complete cases (317 treated, 182 controls). Phase 12 has a separate bootstrap/robustness table; its reported intervals differ slightly from Phase 11, and both are retained with their source labels in `phase16_paper_assets/final_estimates.csv`. Neither table corrects endpoint misclassification or unmeasured confounding.

| Existing Phase 11 estimator | Risk difference (percentage points) | Saved 95% interval (percentage points) | N |
|---|---:|---:|---:|
| CausalForestDML | 3.22 | -7.70 to 14.15 | 499 |
| Propensity-IPW | 5.12 | -4.55 to 13.92 | 499 |
| Treatment-IPW + IPCW | 4.75 | -5.29 to 14.24 | 499 |

All Phase 11 primary intervals include zero. The outcome is the broad MI-coded endpoint (including old-MI/history code-only admissions), not a clinically adjudicated recurrent MI. The held-out estimates are model- and selection-dependent; the censor-weighted result additionally requires conditional independent censoring. No CATE dispersion is interpreted as evidence of treatment-effect heterogeneity.

## Final analysis decision

**Decision C — retain the statin branch as a feasibility/exploratory study.** The clinical endpoint cannot currently distinguish new recurrent MI from transfer, readmission, or continuation. The 211 candidate-distinct labels are not adjudicated. Treatment classification is missing for 2,889 eligible patients, and 1,481 already-exposed admissions lack a qualifying retained EMAR link. Important indication and disease-severity confounders are not validated as pre-treatment measures. Further ATE/CATE estimation on the same endpoint/exposure would create false precision rather than resolve these design limitations.

The prior estimates may be described only as exploratory associations of the existing in-hospital `statin_during` indicator with a broad MI-code outcome in a selected complete-case test population. Do not write that they estimate statin initiation at discharge, long-term adherence, or a clinical causal effect.
