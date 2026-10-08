# Phase 7 — Causal Discovery Readiness Gate

## A. Phase 7 objective

Evaluate whether a defensible, treatment-specific discovery analysis can be run. This gate is not causal discovery. All four candidate treatments are blocked, so PC, GES, FCI, CI testing, graph stability, and graph comparison are intentionally not run.

## B. Frozen inputs

- Phase 1 frozen results: `C:\Users\anura\OneDrive\Desktop\capstone2\phase1_audit_results.json`
- Phase 2 frozen results: `C:\Users\anura\OneDrive\Desktop\capstone2\phase2_audit_results.json`
- Phase 3 frozen results: `C:\Users\anura\OneDrive\Desktop\capstone2\phase3_audit_results.json`
- Phase 4 frozen results: `C:\Users\anura\OneDrive\Desktop\capstone2\phase4_discovery_ready_dataset_results.json`
- Phase 5 frozen results: `C:\Users\anura\OneDrive\Desktop\capstone2\phase5_z_ecg_causal_role_audit_results.json`
- Phase 6 frozen results: `C:\Users\anura\OneDrive\Desktop\capstone2\phase6_background_causal_constraints_results.json`
- Phase 0 estimand artifact: not found locally; contents were not inferred.
- Master data: train 262,813, validation 56,319, test 56,798; combined 375,930 ECG rows; 191,369 admissions; 99,256 patients.
- Unit remains admission-level; `SubjectID` is for dependence/clustering only.

## C. Discovery readiness gate

| Requirement | Status | Finding | Evidence |
|---|---|---|---|
| causal_unit | PARTIALLY_READY | Admission-level observational unit is frozen; repeated admissions require dependence-aware analysis. | Phase 1/4 decision; 34,625 patients have repeated admissions. Preserve SubjectID for dependence, not as a causal feature; handling is unresolved. |
| treatment_specific_time_zero | BLOCKED | Exact treatment assignment time is absent for aspirin, statin, beta blocker, and ACE inhibitor. | UNRESOLVED for aspirin, statin, beta blocker, and ACE inhibitor because exact treatment assignment time is unavailable. |
| index_ecg_rule | BLOCKED | No final causal index ECG is selected; first ECG or MI-relative rules are not validated treatment baselines. | BLOCKED — no final causal ECG-level selection without treatment-specific time zero.; BLOCKED — raw ECG and z_ecg temporal eligibility cannot be established.; BLOCKED — cannot verify train-only preprocessing fitting from local scripts/artifacts. |
| outcome_definition | BLOCKED | MI outcome definition and post-treatment follow-up horizon are unresolved. | Current definition: binary `is_MI` linked to the categorical Label_Troponin cohort labels. The master dataset contains zero MI_Post-Incident rows because that category was intentionally excluded during modeling-data construction. |
| ecg_temporal_eligibility | BLOCKED | Neither z_ecg nor engineered ECG features are established before treatment-specific time zero. | Phase 3 eligibility and Phase 5 treatment-relative temporal status are unresolved. |
| treatment_timestamp_availability | BLOCKED | Master schema provides window-coded flags only; exact medication time fields are absent. |  |
| z_ecg_provenance | BLOCKED | The 64 embeddings exist and are complete in the master table, but waveform join, checkpoint, training membership, and leakage independence are unverified. | NO FINAL REPRESENTATION DECISION YET. Keep all 64 dimensions identified as one quarantined z_ecg block in the schema; do not use the block as a causal discovery input until provenance and the target treatment-specific time zero are established. |
| engineered_feature_provenance | BLOCKED | Upstream engineered ECG preprocessing and fit scope are not verified. | Phase 4 reports documented transforms but no local scripts/fitted transformer artifacts to verify train-only scope. |
| preprocessing_provenance | BLOCKED | Train-only preprocessing scope is unresolved for engineered ECG features and VAE inputs/embeddings. | Phase 4/5 frozen audit results. |
| missingness_handling | PARTIALLY_READY | Missingness counts exist in frozen Phase 4 inventory, but no strategy is authorized until a valid treatment-specific matrix is defined. | Candidate matrix variable-level counts will be reported; no imputation/complete-case processing performed. |
| treatment_prevalence_positivity | PARTIALLY_READY | Marginal admission prevalence is reported; conditional positivity in a finalized eligible cohort and covariate strata is unknown. | Phase 2 admission-level exposure counts; stratified positivity is not audited for any selected baseline cohort. |
| phase6_constraints | READY | Phase 6 provides machine-readable hard, soft, forbidden, permitted, and unresolved constraints; soft relationships must remain nonbinding. | Specification present; 60 hard constraint records and 109 soft relationship records. |

**Overall: BLOCKED for each treatment.** The Phase 6 constraint specification exists, but it does not supply a valid outcome, treatment time zero, or index ECG. The causal discovery input matrix is not approved.

## D. Treatment-specific discovery questions

| Treatment | Status | Candidate exposure | Time zero | Index ECG | Outcome | Algorithms |
|---|---|---|---|---|---|---|
| aspirin | BLOCKED | aspirin_before | BLOCKED — UNRESOLVED | BLOCKED — no final index ECG rule | BLOCKED — causal outcome definition/horizon unresolved | PC/GES/FCI NOT RUN |
| statin | BLOCKED | statin_before | BLOCKED — UNRESOLVED | BLOCKED — no final index ECG rule | BLOCKED — causal outcome definition/horizon unresolved | PC/GES/FCI NOT RUN |
| beta_blocker | BLOCKED | beta_blocker_before | BLOCKED — UNRESOLVED | BLOCKED — no final index ECG rule | BLOCKED — causal outcome definition/horizon unresolved | PC/GES/FCI NOT RUN |
| acei | BLOCKED | acei_before | BLOCKED — UNRESOLVED | BLOCKED — no final index ECG rule | BLOCKED — causal outcome definition/horizon unresolved | PC/GES/FCI NOT RUN |

| Treatment | Exposed admissions | Unexposed admissions | Marginal exposure | Positivity assessment |
|---|---|---|---|---|
| aspirin | 14927 | 176442 | 7.800% | PARTIALLY_READY — marginal exposure/unexposed counts available; conditional positivity by eligible cohort/strata not assessed. |
| statin | 13203 | 178166 | 6.899% | PARTIALLY_READY — marginal exposure/unexposed counts available; conditional positivity by eligible cohort/strata not assessed. |
| beta_blocker | 6099 | 185270 | 3.187% | PARTIALLY_READY — marginal exposure/unexposed counts available; conditional positivity by eligible cohort/strata not assessed. |
| acei | 6196 | 185173 | 3.238% | PARTIALLY_READY — marginal exposure/unexposed counts available; conditional positivity by eligible cohort/strata not assessed. |

These are marginal counts only. They do not establish positivity in an eligible causal cohort or within covariate strata. No candidate treatment-specific graph is run.

## E. Discovery matrices

The options below are schema-level size descriptions, not constructed matrices. No admission was reduced to a selected ECG, and no outcome/treatment-specific rows were filtered.

| Treatment | Candidate strategy | N upper bound | p | Naive N/p | Binary | Continuous | Authorized |
|---|---|---|---|---|---|---|---|
| aspirin | A — clinical/history + one candidate treatment + candidate outcome | 191369 | 8 | 23921.1 | 7 | 1 | False |
| aspirin | B — Matrix A + 95 engineered ECG measurements | 191369 | 103 | 1858.0 | 7 | 96 | False |
| aspirin | C — Matrix A + 64 learned ECG representation dimensions | 191369 | 72 | 2657.9 | 7 | 65 | False |
| statin | A — clinical/history + one candidate treatment + candidate outcome | 191369 | 8 | 23921.1 | 7 | 1 | False |
| statin | B — Matrix A + 95 engineered ECG measurements | 191369 | 103 | 1858.0 | 7 | 96 | False |
| statin | C — Matrix A + 64 learned ECG representation dimensions | 191369 | 72 | 2657.9 | 7 | 65 | False |
| beta_blocker | A — clinical/history + one candidate treatment + candidate outcome | 191369 | 8 | 23921.1 | 7 | 1 | False |
| beta_blocker | B — Matrix A + 95 engineered ECG measurements | 191369 | 103 | 1858.0 | 7 | 96 | False |
| beta_blocker | C — Matrix A + 64 learned ECG representation dimensions | 191369 | 72 | 2657.9 | 7 | 65 | False |
| acei | A — clinical/history + one candidate treatment + candidate outcome | 191369 | 8 | 23921.1 | 7 | 1 | False |
| acei | B — Matrix A + 95 engineered ECG measurements | 191369 | 103 | 1858.0 | 7 | 96 | False |
| acei | C — Matrix A + 64 learned ECG representation dimensions | 191369 | 72 | 2657.9 | 7 | 65 | False |

Matrix A is 6 clinical/history candidates + one treatment flag + provisional `is_MI`. Matrix B adds the 95 engineered ECG measures; Matrix C adds the 64 learned `z_ecg` dimensions. Matrix D is unavailable: Phase 5 did not fit PCA or justify another reduction. High `N/p` alone does not establish graph reliability; patient clustering and causal eligibility remain unresolved.

## F. Missing-data handling

Phase 4 inventory missingness was carried into the JSON for candidate clinical, treatment, outcome, and ECG variables. No imputation, complete-case restriction, or row drop was performed. A final approach cannot be selected until a valid matrix and estimand are defined.

| Treatment | Candidate variable | Missing count | Missing rate |
|---|---|---|---|
| aspirin | anchor_age | 0 | 0.000000% |
| aspirin | sex_male | 0 | 0.000000% |
| aspirin | diabetes | 0 | 0.000000% |
| aspirin | hypertension | 0 | 0.000000% |
| aspirin | ckd | 0 | 0.000000% |
| aspirin | prior_mi | 0 | 0.000000% |
| aspirin | aspirin_before | 0 | 0.000000% |
| aspirin | is_MI | 0 | 0.000000% |
| aspirin | Label_Troponin | 0 | 0.000000% |
| aspirin | index_mi_time | 327700 | 87.170484% |
| aspirin | time_diff_hours | 0 | 0.000000% |
| aspirin | QRS_Dur_Global | 0 | 0.000000% |
| aspirin | QRS_Dur_Global_iqr | 0 | 0.000000% |
| aspirin | QRS_Dur_Global_count | 0 | 0.000000% |
| aspirin | RR_Mean_Global | 0 | 0.000000% |
| aspirin | RR_Mean_Global_iqr | 0 | 0.000000% |
| aspirin | S_Amp_V1 | 0 | 0.000000% |
| aspirin | S_Amp_V1_iqr | 0 | 0.000000% |
| aspirin | S_Amp_V2 | 0 | 0.000000% |
| aspirin | S_Amp_V2_iqr | 0 | 0.000000% |
| aspirin | S_Amp_V3 | 0 | 0.000000% |
| aspirin | S_Amp_V3_iqr | 0 | 0.000000% |
| aspirin | Q_Amp_I | 0 | 0.000000% |
| aspirin | Q_Amp_I_iqr | 0 | 0.000000% |
| aspirin | R_Amp_I | 0 | 0.000000% |
| aspirin | R_Amp_I_iqr | 0 | 0.000000% |
| aspirin | T_Amp_I | 0 | 0.000000% |
| aspirin | T_Amp_I_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_I | 0 | 0.000000% |
| aspirin | Q_Amp_II | 0 | 0.000000% |
| aspirin | Q_Amp_II_iqr | 0 | 0.000000% |
| aspirin | R_Amp_II | 0 | 0.000000% |
| aspirin | R_Amp_II_iqr | 0 | 0.000000% |
| aspirin | T_Amp_II | 0 | 0.000000% |
| aspirin | T_Amp_II_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_II | 0 | 0.000000% |
| aspirin | Q_Amp_III | 0 | 0.000000% |
| aspirin | Q_Amp_III_iqr | 0 | 0.000000% |
| aspirin | R_Amp_III | 0 | 0.000000% |
| aspirin | R_Amp_III_iqr | 0 | 0.000000% |
| aspirin | T_Amp_III | 0 | 0.000000% |
| aspirin | T_Amp_III_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_III | 0 | 0.000000% |
| aspirin | Q_Amp_aVR | 0 | 0.000000% |
| aspirin | Q_Amp_aVR_iqr | 0 | 0.000000% |
| aspirin | R_Amp_aVR | 0 | 0.000000% |
| aspirin | R_Amp_aVR_iqr | 0 | 0.000000% |
| aspirin | T_Amp_aVR | 0 | 0.000000% |
| aspirin | T_Amp_aVR_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_aVR | 0 | 0.000000% |
| aspirin | Q_Amp_aVL | 0 | 0.000000% |
| aspirin | Q_Amp_aVL_iqr | 0 | 0.000000% |
| aspirin | R_Amp_aVL | 0 | 0.000000% |
| aspirin | R_Amp_aVL_iqr | 0 | 0.000000% |
| aspirin | T_Amp_aVL | 0 | 0.000000% |
| aspirin | T_Amp_aVL_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_aVL | 0 | 0.000000% |
| aspirin | Q_Amp_aVF | 0 | 0.000000% |
| aspirin | Q_Amp_aVF_iqr | 0 | 0.000000% |
| aspirin | R_Amp_aVF | 0 | 0.000000% |
| aspirin | R_Amp_aVF_iqr | 0 | 0.000000% |
| aspirin | T_Amp_aVF | 0 | 0.000000% |
| aspirin | T_Amp_aVF_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_aVF | 0 | 0.000000% |
| aspirin | Q_Amp_V1 | 0 | 0.000000% |
| aspirin | Q_Amp_V1_iqr | 0 | 0.000000% |
| aspirin | R_Amp_V1 | 0 | 0.000000% |
| aspirin | R_Amp_V1_iqr | 0 | 0.000000% |
| aspirin | T_Amp_V1 | 0 | 0.000000% |
| aspirin | T_Amp_V1_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_V1 | 0 | 0.000000% |
| aspirin | Q_Amp_V2 | 0 | 0.000000% |
| aspirin | Q_Amp_V2_iqr | 0 | 0.000000% |
| aspirin | R_Amp_V2 | 0 | 0.000000% |
| aspirin | R_Amp_V2_iqr | 0 | 0.000000% |
| aspirin | T_Amp_V2 | 0 | 0.000000% |
| aspirin | T_Amp_V2_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_V2 | 0 | 0.000000% |
| aspirin | Q_Amp_V3 | 0 | 0.000000% |
| aspirin | Q_Amp_V3_iqr | 0 | 0.000000% |
| aspirin | R_Amp_V3 | 0 | 0.000000% |
| aspirin | R_Amp_V3_iqr | 0 | 0.000000% |
| aspirin | T_Amp_V3 | 0 | 0.000000% |
| aspirin | T_Amp_V3_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_V3 | 0 | 0.000000% |
| aspirin | Q_Amp_V4 | 0 | 0.000000% |
| aspirin | Q_Amp_V4_iqr | 0 | 0.000000% |
| aspirin | R_Amp_V4 | 0 | 0.000000% |
| aspirin | R_Amp_V4_iqr | 0 | 0.000000% |
| aspirin | T_Amp_V4 | 0 | 0.000000% |
| aspirin | T_Amp_V4_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_V4 | 0 | 0.000000% |
| aspirin | Q_Amp_V5 | 0 | 0.000000% |
| aspirin | Q_Amp_V5_iqr | 0 | 0.000000% |
| aspirin | R_Amp_V5 | 0 | 0.000000% |
| aspirin | R_Amp_V5_iqr | 0 | 0.000000% |
| aspirin | T_Amp_V5 | 0 | 0.000000% |
| aspirin | T_Amp_V5_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_V5 | 0 | 0.000000% |
| aspirin | Q_Amp_V6 | 0 | 0.000000% |
| aspirin | Q_Amp_V6_iqr | 0 | 0.000000% |
| aspirin | R_Amp_V6 | 0 | 0.000000% |
| aspirin | R_Amp_V6_iqr | 0 | 0.000000% |
| aspirin | T_Amp_V6 | 0 | 0.000000% |
| aspirin | T_Amp_V6_iqr | 0 | 0.000000% |
| aspirin | ST_Elev_V6 | 0 | 0.000000% |
| aspirin | z_ecg_1 | 0 | 0.000000% |
| aspirin | z_ecg_2 | 0 | 0.000000% |
| aspirin | z_ecg_3 | 0 | 0.000000% |
| aspirin | z_ecg_4 | 0 | 0.000000% |
| aspirin | z_ecg_5 | 0 | 0.000000% |
| aspirin | z_ecg_6 | 0 | 0.000000% |
| aspirin | z_ecg_7 | 0 | 0.000000% |
| aspirin | z_ecg_8 | 0 | 0.000000% |
| aspirin | z_ecg_9 | 0 | 0.000000% |
| aspirin | z_ecg_10 | 0 | 0.000000% |
| aspirin | z_ecg_11 | 0 | 0.000000% |
| aspirin | z_ecg_12 | 0 | 0.000000% |
| aspirin | z_ecg_13 | 0 | 0.000000% |
| aspirin | z_ecg_14 | 0 | 0.000000% |
| aspirin | z_ecg_15 | 0 | 0.000000% |
| aspirin | z_ecg_16 | 0 | 0.000000% |
| aspirin | z_ecg_17 | 0 | 0.000000% |
| aspirin | z_ecg_18 | 0 | 0.000000% |
| aspirin | z_ecg_19 | 0 | 0.000000% |
| aspirin | z_ecg_20 | 0 | 0.000000% |
| aspirin | z_ecg_21 | 0 | 0.000000% |
| aspirin | z_ecg_22 | 0 | 0.000000% |
| aspirin | z_ecg_23 | 0 | 0.000000% |
| aspirin | z_ecg_24 | 0 | 0.000000% |
| aspirin | z_ecg_25 | 0 | 0.000000% |
| aspirin | z_ecg_26 | 0 | 0.000000% |
| aspirin | z_ecg_27 | 0 | 0.000000% |
| aspirin | z_ecg_28 | 0 | 0.000000% |
| aspirin | z_ecg_29 | 0 | 0.000000% |
| aspirin | z_ecg_30 | 0 | 0.000000% |
| aspirin | z_ecg_31 | 0 | 0.000000% |
| aspirin | z_ecg_32 | 0 | 0.000000% |
| aspirin | z_ecg_33 | 0 | 0.000000% |
| aspirin | z_ecg_34 | 0 | 0.000000% |
| aspirin | z_ecg_35 | 0 | 0.000000% |
| aspirin | z_ecg_36 | 0 | 0.000000% |
| aspirin | z_ecg_37 | 0 | 0.000000% |
| aspirin | z_ecg_38 | 0 | 0.000000% |
| aspirin | z_ecg_39 | 0 | 0.000000% |
| aspirin | z_ecg_40 | 0 | 0.000000% |
| aspirin | z_ecg_41 | 0 | 0.000000% |
| aspirin | z_ecg_42 | 0 | 0.000000% |
| aspirin | z_ecg_43 | 0 | 0.000000% |
| aspirin | z_ecg_44 | 0 | 0.000000% |
| aspirin | z_ecg_45 | 0 | 0.000000% |
| aspirin | z_ecg_46 | 0 | 0.000000% |
| aspirin | z_ecg_47 | 0 | 0.000000% |
| aspirin | z_ecg_48 | 0 | 0.000000% |
| aspirin | z_ecg_49 | 0 | 0.000000% |
| aspirin | z_ecg_50 | 0 | 0.000000% |
| aspirin | z_ecg_51 | 0 | 0.000000% |
| aspirin | z_ecg_52 | 0 | 0.000000% |
| aspirin | z_ecg_53 | 0 | 0.000000% |
| aspirin | z_ecg_54 | 0 | 0.000000% |
| aspirin | z_ecg_55 | 0 | 0.000000% |
| aspirin | z_ecg_56 | 0 | 0.000000% |
| aspirin | z_ecg_57 | 0 | 0.000000% |
| aspirin | z_ecg_58 | 0 | 0.000000% |
| aspirin | z_ecg_59 | 0 | 0.000000% |
| aspirin | z_ecg_60 | 0 | 0.000000% |
| aspirin | z_ecg_61 | 0 | 0.000000% |
| aspirin | z_ecg_62 | 0 | 0.000000% |
| aspirin | z_ecg_63 | 0 | 0.000000% |
| aspirin | z_ecg_64 | 0 | 0.000000% |
| statin | anchor_age | 0 | 0.000000% |
| statin | sex_male | 0 | 0.000000% |
| statin | diabetes | 0 | 0.000000% |
| statin | hypertension | 0 | 0.000000% |
| statin | ckd | 0 | 0.000000% |
| statin | prior_mi | 0 | 0.000000% |
| statin | statin_before | 0 | 0.000000% |
| statin | is_MI | 0 | 0.000000% |
| statin | Label_Troponin | 0 | 0.000000% |
| statin | index_mi_time | 327700 | 87.170484% |
| statin | time_diff_hours | 0 | 0.000000% |
| statin | QRS_Dur_Global | 0 | 0.000000% |
| statin | QRS_Dur_Global_iqr | 0 | 0.000000% |
| statin | QRS_Dur_Global_count | 0 | 0.000000% |
| statin | RR_Mean_Global | 0 | 0.000000% |
| statin | RR_Mean_Global_iqr | 0 | 0.000000% |
| statin | S_Amp_V1 | 0 | 0.000000% |
| statin | S_Amp_V1_iqr | 0 | 0.000000% |
| statin | S_Amp_V2 | 0 | 0.000000% |
| statin | S_Amp_V2_iqr | 0 | 0.000000% |
| statin | S_Amp_V3 | 0 | 0.000000% |
| statin | S_Amp_V3_iqr | 0 | 0.000000% |
| statin | Q_Amp_I | 0 | 0.000000% |
| statin | Q_Amp_I_iqr | 0 | 0.000000% |
| statin | R_Amp_I | 0 | 0.000000% |
| statin | R_Amp_I_iqr | 0 | 0.000000% |
| statin | T_Amp_I | 0 | 0.000000% |
| statin | T_Amp_I_iqr | 0 | 0.000000% |
| statin | ST_Elev_I | 0 | 0.000000% |
| statin | Q_Amp_II | 0 | 0.000000% |
| statin | Q_Amp_II_iqr | 0 | 0.000000% |
| statin | R_Amp_II | 0 | 0.000000% |
| statin | R_Amp_II_iqr | 0 | 0.000000% |
| statin | T_Amp_II | 0 | 0.000000% |
| statin | T_Amp_II_iqr | 0 | 0.000000% |
| statin | ST_Elev_II | 0 | 0.000000% |
| statin | Q_Amp_III | 0 | 0.000000% |
| statin | Q_Amp_III_iqr | 0 | 0.000000% |
| statin | R_Amp_III | 0 | 0.000000% |
| statin | R_Amp_III_iqr | 0 | 0.000000% |
| statin | T_Amp_III | 0 | 0.000000% |
| statin | T_Amp_III_iqr | 0 | 0.000000% |
| statin | ST_Elev_III | 0 | 0.000000% |
| statin | Q_Amp_aVR | 0 | 0.000000% |
| statin | Q_Amp_aVR_iqr | 0 | 0.000000% |
| statin | R_Amp_aVR | 0 | 0.000000% |
| statin | R_Amp_aVR_iqr | 0 | 0.000000% |
| statin | T_Amp_aVR | 0 | 0.000000% |
| statin | T_Amp_aVR_iqr | 0 | 0.000000% |
| statin | ST_Elev_aVR | 0 | 0.000000% |
| statin | Q_Amp_aVL | 0 | 0.000000% |
| statin | Q_Amp_aVL_iqr | 0 | 0.000000% |
| statin | R_Amp_aVL | 0 | 0.000000% |
| statin | R_Amp_aVL_iqr | 0 | 0.000000% |
| statin | T_Amp_aVL | 0 | 0.000000% |
| statin | T_Amp_aVL_iqr | 0 | 0.000000% |
| statin | ST_Elev_aVL | 0 | 0.000000% |
| statin | Q_Amp_aVF | 0 | 0.000000% |
| statin | Q_Amp_aVF_iqr | 0 | 0.000000% |
| statin | R_Amp_aVF | 0 | 0.000000% |
| statin | R_Amp_aVF_iqr | 0 | 0.000000% |
| statin | T_Amp_aVF | 0 | 0.000000% |
| statin | T_Amp_aVF_iqr | 0 | 0.000000% |
| statin | ST_Elev_aVF | 0 | 0.000000% |
| statin | Q_Amp_V1 | 0 | 0.000000% |
| statin | Q_Amp_V1_iqr | 0 | 0.000000% |
| statin | R_Amp_V1 | 0 | 0.000000% |
| statin | R_Amp_V1_iqr | 0 | 0.000000% |
| statin | T_Amp_V1 | 0 | 0.000000% |
| statin | T_Amp_V1_iqr | 0 | 0.000000% |
| statin | ST_Elev_V1 | 0 | 0.000000% |
| statin | Q_Amp_V2 | 0 | 0.000000% |
| statin | Q_Amp_V2_iqr | 0 | 0.000000% |
| statin | R_Amp_V2 | 0 | 0.000000% |
| statin | R_Amp_V2_iqr | 0 | 0.000000% |
| statin | T_Amp_V2 | 0 | 0.000000% |
| statin | T_Amp_V2_iqr | 0 | 0.000000% |
| statin | ST_Elev_V2 | 0 | 0.000000% |
| statin | Q_Amp_V3 | 0 | 0.000000% |
| statin | Q_Amp_V3_iqr | 0 | 0.000000% |
| statin | R_Amp_V3 | 0 | 0.000000% |
| statin | R_Amp_V3_iqr | 0 | 0.000000% |
| statin | T_Amp_V3 | 0 | 0.000000% |
| statin | T_Amp_V3_iqr | 0 | 0.000000% |
| statin | ST_Elev_V3 | 0 | 0.000000% |
| statin | Q_Amp_V4 | 0 | 0.000000% |
| statin | Q_Amp_V4_iqr | 0 | 0.000000% |
| statin | R_Amp_V4 | 0 | 0.000000% |
| statin | R_Amp_V4_iqr | 0 | 0.000000% |
| statin | T_Amp_V4 | 0 | 0.000000% |
| statin | T_Amp_V4_iqr | 0 | 0.000000% |
| statin | ST_Elev_V4 | 0 | 0.000000% |
| statin | Q_Amp_V5 | 0 | 0.000000% |
| statin | Q_Amp_V5_iqr | 0 | 0.000000% |
| statin | R_Amp_V5 | 0 | 0.000000% |
| statin | R_Amp_V5_iqr | 0 | 0.000000% |
| statin | T_Amp_V5 | 0 | 0.000000% |
| statin | T_Amp_V5_iqr | 0 | 0.000000% |
| statin | ST_Elev_V5 | 0 | 0.000000% |
| statin | Q_Amp_V6 | 0 | 0.000000% |
| statin | Q_Amp_V6_iqr | 0 | 0.000000% |
| statin | R_Amp_V6 | 0 | 0.000000% |
| statin | R_Amp_V6_iqr | 0 | 0.000000% |
| statin | T_Amp_V6 | 0 | 0.000000% |
| statin | T_Amp_V6_iqr | 0 | 0.000000% |
| statin | ST_Elev_V6 | 0 | 0.000000% |
| statin | z_ecg_1 | 0 | 0.000000% |
| statin | z_ecg_2 | 0 | 0.000000% |
| statin | z_ecg_3 | 0 | 0.000000% |
| statin | z_ecg_4 | 0 | 0.000000% |
| statin | z_ecg_5 | 0 | 0.000000% |
| statin | z_ecg_6 | 0 | 0.000000% |
| statin | z_ecg_7 | 0 | 0.000000% |
| statin | z_ecg_8 | 0 | 0.000000% |
| statin | z_ecg_9 | 0 | 0.000000% |
| statin | z_ecg_10 | 0 | 0.000000% |
| statin | z_ecg_11 | 0 | 0.000000% |
| statin | z_ecg_12 | 0 | 0.000000% |
| statin | z_ecg_13 | 0 | 0.000000% |
| statin | z_ecg_14 | 0 | 0.000000% |
| statin | z_ecg_15 | 0 | 0.000000% |
| statin | z_ecg_16 | 0 | 0.000000% |
| statin | z_ecg_17 | 0 | 0.000000% |
| statin | z_ecg_18 | 0 | 0.000000% |
| statin | z_ecg_19 | 0 | 0.000000% |
| statin | z_ecg_20 | 0 | 0.000000% |
| statin | z_ecg_21 | 0 | 0.000000% |
| statin | z_ecg_22 | 0 | 0.000000% |
| statin | z_ecg_23 | 0 | 0.000000% |
| statin | z_ecg_24 | 0 | 0.000000% |
| statin | z_ecg_25 | 0 | 0.000000% |
| statin | z_ecg_26 | 0 | 0.000000% |
| statin | z_ecg_27 | 0 | 0.000000% |
| statin | z_ecg_28 | 0 | 0.000000% |
| statin | z_ecg_29 | 0 | 0.000000% |
| statin | z_ecg_30 | 0 | 0.000000% |
| statin | z_ecg_31 | 0 | 0.000000% |
| statin | z_ecg_32 | 0 | 0.000000% |
| statin | z_ecg_33 | 0 | 0.000000% |
| statin | z_ecg_34 | 0 | 0.000000% |
| statin | z_ecg_35 | 0 | 0.000000% |
| statin | z_ecg_36 | 0 | 0.000000% |
| statin | z_ecg_37 | 0 | 0.000000% |
| statin | z_ecg_38 | 0 | 0.000000% |
| statin | z_ecg_39 | 0 | 0.000000% |
| statin | z_ecg_40 | 0 | 0.000000% |
| statin | z_ecg_41 | 0 | 0.000000% |
| statin | z_ecg_42 | 0 | 0.000000% |
| statin | z_ecg_43 | 0 | 0.000000% |
| statin | z_ecg_44 | 0 | 0.000000% |
| statin | z_ecg_45 | 0 | 0.000000% |
| statin | z_ecg_46 | 0 | 0.000000% |
| statin | z_ecg_47 | 0 | 0.000000% |
| statin | z_ecg_48 | 0 | 0.000000% |
| statin | z_ecg_49 | 0 | 0.000000% |
| statin | z_ecg_50 | 0 | 0.000000% |
| statin | z_ecg_51 | 0 | 0.000000% |
| statin | z_ecg_52 | 0 | 0.000000% |
| statin | z_ecg_53 | 0 | 0.000000% |
| statin | z_ecg_54 | 0 | 0.000000% |
| statin | z_ecg_55 | 0 | 0.000000% |
| statin | z_ecg_56 | 0 | 0.000000% |
| statin | z_ecg_57 | 0 | 0.000000% |
| statin | z_ecg_58 | 0 | 0.000000% |
| statin | z_ecg_59 | 0 | 0.000000% |
| statin | z_ecg_60 | 0 | 0.000000% |
| statin | z_ecg_61 | 0 | 0.000000% |
| statin | z_ecg_62 | 0 | 0.000000% |
| statin | z_ecg_63 | 0 | 0.000000% |
| statin | z_ecg_64 | 0 | 0.000000% |
| beta_blocker | anchor_age | 0 | 0.000000% |
| beta_blocker | sex_male | 0 | 0.000000% |
| beta_blocker | diabetes | 0 | 0.000000% |
| beta_blocker | hypertension | 0 | 0.000000% |
| beta_blocker | ckd | 0 | 0.000000% |
| beta_blocker | prior_mi | 0 | 0.000000% |
| beta_blocker | beta_blocker_before | 0 | 0.000000% |
| beta_blocker | is_MI | 0 | 0.000000% |
| beta_blocker | Label_Troponin | 0 | 0.000000% |
| beta_blocker | index_mi_time | 327700 | 87.170484% |
| beta_blocker | time_diff_hours | 0 | 0.000000% |
| beta_blocker | QRS_Dur_Global | 0 | 0.000000% |
| beta_blocker | QRS_Dur_Global_iqr | 0 | 0.000000% |
| beta_blocker | QRS_Dur_Global_count | 0 | 0.000000% |
| beta_blocker | RR_Mean_Global | 0 | 0.000000% |
| beta_blocker | RR_Mean_Global_iqr | 0 | 0.000000% |
| beta_blocker | S_Amp_V1 | 0 | 0.000000% |
| beta_blocker | S_Amp_V1_iqr | 0 | 0.000000% |
| beta_blocker | S_Amp_V2 | 0 | 0.000000% |
| beta_blocker | S_Amp_V2_iqr | 0 | 0.000000% |
| beta_blocker | S_Amp_V3 | 0 | 0.000000% |
| beta_blocker | S_Amp_V3_iqr | 0 | 0.000000% |
| beta_blocker | Q_Amp_I | 0 | 0.000000% |
| beta_blocker | Q_Amp_I_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_I | 0 | 0.000000% |
| beta_blocker | R_Amp_I_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_I | 0 | 0.000000% |
| beta_blocker | T_Amp_I_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_I | 0 | 0.000000% |
| beta_blocker | Q_Amp_II | 0 | 0.000000% |
| beta_blocker | Q_Amp_II_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_II | 0 | 0.000000% |
| beta_blocker | R_Amp_II_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_II | 0 | 0.000000% |
| beta_blocker | T_Amp_II_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_II | 0 | 0.000000% |
| beta_blocker | Q_Amp_III | 0 | 0.000000% |
| beta_blocker | Q_Amp_III_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_III | 0 | 0.000000% |
| beta_blocker | R_Amp_III_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_III | 0 | 0.000000% |
| beta_blocker | T_Amp_III_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_III | 0 | 0.000000% |
| beta_blocker | Q_Amp_aVR | 0 | 0.000000% |
| beta_blocker | Q_Amp_aVR_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_aVR | 0 | 0.000000% |
| beta_blocker | R_Amp_aVR_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_aVR | 0 | 0.000000% |
| beta_blocker | T_Amp_aVR_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_aVR | 0 | 0.000000% |
| beta_blocker | Q_Amp_aVL | 0 | 0.000000% |
| beta_blocker | Q_Amp_aVL_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_aVL | 0 | 0.000000% |
| beta_blocker | R_Amp_aVL_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_aVL | 0 | 0.000000% |
| beta_blocker | T_Amp_aVL_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_aVL | 0 | 0.000000% |
| beta_blocker | Q_Amp_aVF | 0 | 0.000000% |
| beta_blocker | Q_Amp_aVF_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_aVF | 0 | 0.000000% |
| beta_blocker | R_Amp_aVF_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_aVF | 0 | 0.000000% |
| beta_blocker | T_Amp_aVF_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_aVF | 0 | 0.000000% |
| beta_blocker | Q_Amp_V1 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V1_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_V1 | 0 | 0.000000% |
| beta_blocker | R_Amp_V1_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_V1 | 0 | 0.000000% |
| beta_blocker | T_Amp_V1_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_V1 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V2 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V2_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_V2 | 0 | 0.000000% |
| beta_blocker | R_Amp_V2_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_V2 | 0 | 0.000000% |
| beta_blocker | T_Amp_V2_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_V2 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V3 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V3_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_V3 | 0 | 0.000000% |
| beta_blocker | R_Amp_V3_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_V3 | 0 | 0.000000% |
| beta_blocker | T_Amp_V3_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_V3 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V4 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V4_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_V4 | 0 | 0.000000% |
| beta_blocker | R_Amp_V4_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_V4 | 0 | 0.000000% |
| beta_blocker | T_Amp_V4_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_V4 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V5 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V5_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_V5 | 0 | 0.000000% |
| beta_blocker | R_Amp_V5_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_V5 | 0 | 0.000000% |
| beta_blocker | T_Amp_V5_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_V5 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V6 | 0 | 0.000000% |
| beta_blocker | Q_Amp_V6_iqr | 0 | 0.000000% |
| beta_blocker | R_Amp_V6 | 0 | 0.000000% |
| beta_blocker | R_Amp_V6_iqr | 0 | 0.000000% |
| beta_blocker | T_Amp_V6 | 0 | 0.000000% |
| beta_blocker | T_Amp_V6_iqr | 0 | 0.000000% |
| beta_blocker | ST_Elev_V6 | 0 | 0.000000% |
| beta_blocker | z_ecg_1 | 0 | 0.000000% |
| beta_blocker | z_ecg_2 | 0 | 0.000000% |
| beta_blocker | z_ecg_3 | 0 | 0.000000% |
| beta_blocker | z_ecg_4 | 0 | 0.000000% |
| beta_blocker | z_ecg_5 | 0 | 0.000000% |
| beta_blocker | z_ecg_6 | 0 | 0.000000% |
| beta_blocker | z_ecg_7 | 0 | 0.000000% |
| beta_blocker | z_ecg_8 | 0 | 0.000000% |
| beta_blocker | z_ecg_9 | 0 | 0.000000% |
| beta_blocker | z_ecg_10 | 0 | 0.000000% |
| beta_blocker | z_ecg_11 | 0 | 0.000000% |
| beta_blocker | z_ecg_12 | 0 | 0.000000% |
| beta_blocker | z_ecg_13 | 0 | 0.000000% |
| beta_blocker | z_ecg_14 | 0 | 0.000000% |
| beta_blocker | z_ecg_15 | 0 | 0.000000% |
| beta_blocker | z_ecg_16 | 0 | 0.000000% |
| beta_blocker | z_ecg_17 | 0 | 0.000000% |
| beta_blocker | z_ecg_18 | 0 | 0.000000% |
| beta_blocker | z_ecg_19 | 0 | 0.000000% |
| beta_blocker | z_ecg_20 | 0 | 0.000000% |
| beta_blocker | z_ecg_21 | 0 | 0.000000% |
| beta_blocker | z_ecg_22 | 0 | 0.000000% |
| beta_blocker | z_ecg_23 | 0 | 0.000000% |
| beta_blocker | z_ecg_24 | 0 | 0.000000% |
| beta_blocker | z_ecg_25 | 0 | 0.000000% |
| beta_blocker | z_ecg_26 | 0 | 0.000000% |
| beta_blocker | z_ecg_27 | 0 | 0.000000% |
| beta_blocker | z_ecg_28 | 0 | 0.000000% |
| beta_blocker | z_ecg_29 | 0 | 0.000000% |
| beta_blocker | z_ecg_30 | 0 | 0.000000% |
| beta_blocker | z_ecg_31 | 0 | 0.000000% |
| beta_blocker | z_ecg_32 | 0 | 0.000000% |
| beta_blocker | z_ecg_33 | 0 | 0.000000% |
| beta_blocker | z_ecg_34 | 0 | 0.000000% |
| beta_blocker | z_ecg_35 | 0 | 0.000000% |
| beta_blocker | z_ecg_36 | 0 | 0.000000% |
| beta_blocker | z_ecg_37 | 0 | 0.000000% |
| beta_blocker | z_ecg_38 | 0 | 0.000000% |
| beta_blocker | z_ecg_39 | 0 | 0.000000% |
| beta_blocker | z_ecg_40 | 0 | 0.000000% |
| beta_blocker | z_ecg_41 | 0 | 0.000000% |
| beta_blocker | z_ecg_42 | 0 | 0.000000% |
| beta_blocker | z_ecg_43 | 0 | 0.000000% |
| beta_blocker | z_ecg_44 | 0 | 0.000000% |
| beta_blocker | z_ecg_45 | 0 | 0.000000% |
| beta_blocker | z_ecg_46 | 0 | 0.000000% |
| beta_blocker | z_ecg_47 | 0 | 0.000000% |
| beta_blocker | z_ecg_48 | 0 | 0.000000% |
| beta_blocker | z_ecg_49 | 0 | 0.000000% |
| beta_blocker | z_ecg_50 | 0 | 0.000000% |
| beta_blocker | z_ecg_51 | 0 | 0.000000% |
| beta_blocker | z_ecg_52 | 0 | 0.000000% |
| beta_blocker | z_ecg_53 | 0 | 0.000000% |
| beta_blocker | z_ecg_54 | 0 | 0.000000% |
| beta_blocker | z_ecg_55 | 0 | 0.000000% |
| beta_blocker | z_ecg_56 | 0 | 0.000000% |
| beta_blocker | z_ecg_57 | 0 | 0.000000% |
| beta_blocker | z_ecg_58 | 0 | 0.000000% |
| beta_blocker | z_ecg_59 | 0 | 0.000000% |
| beta_blocker | z_ecg_60 | 0 | 0.000000% |
| beta_blocker | z_ecg_61 | 0 | 0.000000% |
| beta_blocker | z_ecg_62 | 0 | 0.000000% |
| beta_blocker | z_ecg_63 | 0 | 0.000000% |
| beta_blocker | z_ecg_64 | 0 | 0.000000% |
| acei | anchor_age | 0 | 0.000000% |
| acei | sex_male | 0 | 0.000000% |
| acei | diabetes | 0 | 0.000000% |
| acei | hypertension | 0 | 0.000000% |
| acei | ckd | 0 | 0.000000% |
| acei | prior_mi | 0 | 0.000000% |
| acei | acei_before | 0 | 0.000000% |
| acei | is_MI | 0 | 0.000000% |
| acei | Label_Troponin | 0 | 0.000000% |
| acei | index_mi_time | 327700 | 87.170484% |
| acei | time_diff_hours | 0 | 0.000000% |
| acei | QRS_Dur_Global | 0 | 0.000000% |
| acei | QRS_Dur_Global_iqr | 0 | 0.000000% |
| acei | QRS_Dur_Global_count | 0 | 0.000000% |
| acei | RR_Mean_Global | 0 | 0.000000% |
| acei | RR_Mean_Global_iqr | 0 | 0.000000% |
| acei | S_Amp_V1 | 0 | 0.000000% |
| acei | S_Amp_V1_iqr | 0 | 0.000000% |
| acei | S_Amp_V2 | 0 | 0.000000% |
| acei | S_Amp_V2_iqr | 0 | 0.000000% |
| acei | S_Amp_V3 | 0 | 0.000000% |
| acei | S_Amp_V3_iqr | 0 | 0.000000% |
| acei | Q_Amp_I | 0 | 0.000000% |
| acei | Q_Amp_I_iqr | 0 | 0.000000% |
| acei | R_Amp_I | 0 | 0.000000% |
| acei | R_Amp_I_iqr | 0 | 0.000000% |
| acei | T_Amp_I | 0 | 0.000000% |
| acei | T_Amp_I_iqr | 0 | 0.000000% |
| acei | ST_Elev_I | 0 | 0.000000% |
| acei | Q_Amp_II | 0 | 0.000000% |
| acei | Q_Amp_II_iqr | 0 | 0.000000% |
| acei | R_Amp_II | 0 | 0.000000% |
| acei | R_Amp_II_iqr | 0 | 0.000000% |
| acei | T_Amp_II | 0 | 0.000000% |
| acei | T_Amp_II_iqr | 0 | 0.000000% |
| acei | ST_Elev_II | 0 | 0.000000% |
| acei | Q_Amp_III | 0 | 0.000000% |
| acei | Q_Amp_III_iqr | 0 | 0.000000% |
| acei | R_Amp_III | 0 | 0.000000% |
| acei | R_Amp_III_iqr | 0 | 0.000000% |
| acei | T_Amp_III | 0 | 0.000000% |
| acei | T_Amp_III_iqr | 0 | 0.000000% |
| acei | ST_Elev_III | 0 | 0.000000% |
| acei | Q_Amp_aVR | 0 | 0.000000% |
| acei | Q_Amp_aVR_iqr | 0 | 0.000000% |
| acei | R_Amp_aVR | 0 | 0.000000% |
| acei | R_Amp_aVR_iqr | 0 | 0.000000% |
| acei | T_Amp_aVR | 0 | 0.000000% |
| acei | T_Amp_aVR_iqr | 0 | 0.000000% |
| acei | ST_Elev_aVR | 0 | 0.000000% |
| acei | Q_Amp_aVL | 0 | 0.000000% |
| acei | Q_Amp_aVL_iqr | 0 | 0.000000% |
| acei | R_Amp_aVL | 0 | 0.000000% |
| acei | R_Amp_aVL_iqr | 0 | 0.000000% |
| acei | T_Amp_aVL | 0 | 0.000000% |
| acei | T_Amp_aVL_iqr | 0 | 0.000000% |
| acei | ST_Elev_aVL | 0 | 0.000000% |
| acei | Q_Amp_aVF | 0 | 0.000000% |
| acei | Q_Amp_aVF_iqr | 0 | 0.000000% |
| acei | R_Amp_aVF | 0 | 0.000000% |
| acei | R_Amp_aVF_iqr | 0 | 0.000000% |
| acei | T_Amp_aVF | 0 | 0.000000% |
| acei | T_Amp_aVF_iqr | 0 | 0.000000% |
| acei | ST_Elev_aVF | 0 | 0.000000% |
| acei | Q_Amp_V1 | 0 | 0.000000% |
| acei | Q_Amp_V1_iqr | 0 | 0.000000% |
| acei | R_Amp_V1 | 0 | 0.000000% |
| acei | R_Amp_V1_iqr | 0 | 0.000000% |
| acei | T_Amp_V1 | 0 | 0.000000% |
| acei | T_Amp_V1_iqr | 0 | 0.000000% |
| acei | ST_Elev_V1 | 0 | 0.000000% |
| acei | Q_Amp_V2 | 0 | 0.000000% |
| acei | Q_Amp_V2_iqr | 0 | 0.000000% |
| acei | R_Amp_V2 | 0 | 0.000000% |
| acei | R_Amp_V2_iqr | 0 | 0.000000% |
| acei | T_Amp_V2 | 0 | 0.000000% |
| acei | T_Amp_V2_iqr | 0 | 0.000000% |
| acei | ST_Elev_V2 | 0 | 0.000000% |
| acei | Q_Amp_V3 | 0 | 0.000000% |
| acei | Q_Amp_V3_iqr | 0 | 0.000000% |
| acei | R_Amp_V3 | 0 | 0.000000% |
| acei | R_Amp_V3_iqr | 0 | 0.000000% |
| acei | T_Amp_V3 | 0 | 0.000000% |
| acei | T_Amp_V3_iqr | 0 | 0.000000% |
| acei | ST_Elev_V3 | 0 | 0.000000% |
| acei | Q_Amp_V4 | 0 | 0.000000% |
| acei | Q_Amp_V4_iqr | 0 | 0.000000% |
| acei | R_Amp_V4 | 0 | 0.000000% |
| acei | R_Amp_V4_iqr | 0 | 0.000000% |
| acei | T_Amp_V4 | 0 | 0.000000% |
| acei | T_Amp_V4_iqr | 0 | 0.000000% |
| acei | ST_Elev_V4 | 0 | 0.000000% |
| acei | Q_Amp_V5 | 0 | 0.000000% |
| acei | Q_Amp_V5_iqr | 0 | 0.000000% |
| acei | R_Amp_V5 | 0 | 0.000000% |
| acei | R_Amp_V5_iqr | 0 | 0.000000% |
| acei | T_Amp_V5 | 0 | 0.000000% |
| acei | T_Amp_V5_iqr | 0 | 0.000000% |
| acei | ST_Elev_V5 | 0 | 0.000000% |
| acei | Q_Amp_V6 | 0 | 0.000000% |
| acei | Q_Amp_V6_iqr | 0 | 0.000000% |
| acei | R_Amp_V6 | 0 | 0.000000% |
| acei | R_Amp_V6_iqr | 0 | 0.000000% |
| acei | T_Amp_V6 | 0 | 0.000000% |
| acei | T_Amp_V6_iqr | 0 | 0.000000% |
| acei | ST_Elev_V6 | 0 | 0.000000% |
| acei | z_ecg_1 | 0 | 0.000000% |
| acei | z_ecg_2 | 0 | 0.000000% |
| acei | z_ecg_3 | 0 | 0.000000% |
| acei | z_ecg_4 | 0 | 0.000000% |
| acei | z_ecg_5 | 0 | 0.000000% |
| acei | z_ecg_6 | 0 | 0.000000% |
| acei | z_ecg_7 | 0 | 0.000000% |
| acei | z_ecg_8 | 0 | 0.000000% |
| acei | z_ecg_9 | 0 | 0.000000% |
| acei | z_ecg_10 | 0 | 0.000000% |
| acei | z_ecg_11 | 0 | 0.000000% |
| acei | z_ecg_12 | 0 | 0.000000% |
| acei | z_ecg_13 | 0 | 0.000000% |
| acei | z_ecg_14 | 0 | 0.000000% |
| acei | z_ecg_15 | 0 | 0.000000% |
| acei | z_ecg_16 | 0 | 0.000000% |
| acei | z_ecg_17 | 0 | 0.000000% |
| acei | z_ecg_18 | 0 | 0.000000% |
| acei | z_ecg_19 | 0 | 0.000000% |
| acei | z_ecg_20 | 0 | 0.000000% |
| acei | z_ecg_21 | 0 | 0.000000% |
| acei | z_ecg_22 | 0 | 0.000000% |
| acei | z_ecg_23 | 0 | 0.000000% |
| acei | z_ecg_24 | 0 | 0.000000% |
| acei | z_ecg_25 | 0 | 0.000000% |
| acei | z_ecg_26 | 0 | 0.000000% |
| acei | z_ecg_27 | 0 | 0.000000% |
| acei | z_ecg_28 | 0 | 0.000000% |
| acei | z_ecg_29 | 0 | 0.000000% |
| acei | z_ecg_30 | 0 | 0.000000% |
| acei | z_ecg_31 | 0 | 0.000000% |
| acei | z_ecg_32 | 0 | 0.000000% |
| acei | z_ecg_33 | 0 | 0.000000% |
| acei | z_ecg_34 | 0 | 0.000000% |
| acei | z_ecg_35 | 0 | 0.000000% |
| acei | z_ecg_36 | 0 | 0.000000% |
| acei | z_ecg_37 | 0 | 0.000000% |
| acei | z_ecg_38 | 0 | 0.000000% |
| acei | z_ecg_39 | 0 | 0.000000% |
| acei | z_ecg_40 | 0 | 0.000000% |
| acei | z_ecg_41 | 0 | 0.000000% |
| acei | z_ecg_42 | 0 | 0.000000% |
| acei | z_ecg_43 | 0 | 0.000000% |
| acei | z_ecg_44 | 0 | 0.000000% |
| acei | z_ecg_45 | 0 | 0.000000% |
| acei | z_ecg_46 | 0 | 0.000000% |
| acei | z_ecg_47 | 0 | 0.000000% |
| acei | z_ecg_48 | 0 | 0.000000% |
| acei | z_ecg_49 | 0 | 0.000000% |
| acei | z_ecg_50 | 0 | 0.000000% |
| acei | z_ecg_51 | 0 | 0.000000% |
| acei | z_ecg_52 | 0 | 0.000000% |
| acei | z_ecg_53 | 0 | 0.000000% |
| acei | z_ecg_54 | 0 | 0.000000% |
| acei | z_ecg_55 | 0 | 0.000000% |
| acei | z_ecg_56 | 0 | 0.000000% |
| acei | z_ecg_57 | 0 | 0.000000% |
| acei | z_ecg_58 | 0 | 0.000000% |
| acei | z_ecg_59 | 0 | 0.000000% |
| acei | z_ecg_60 | 0 | 0.000000% |
| acei | z_ecg_61 | 0 | 0.000000% |
| acei | z_ecg_62 | 0 | 0.000000% |
| acei | z_ecg_63 | 0 | 0.000000% |
| acei | z_ecg_64 | 0 | 0.000000% |

## G. CI testing

NOT SELECTED / NOT RUN. Candidate variables combine binary indicators with continuous age and ECG measures. With no authorized matrix and repeated admissions within patients, no CI test can be selected as justified for the target graph. Conditional-independence test count and multiple-testing burden are zero because no test was performed.

## H. PC results

NOT RUN — readiness gate BLOCKED for all treatments. No skeleton, oriented/partially oriented edges, separating sets, CI results, alpha, conditioning limit, or orientation settings exist.

## I. GES results

NOT RUN — readiness gate BLOCKED for all treatments. No score, penalty, initialization, or candidate graph exists.

## J. FCI results

NOT RUN — readiness gate BLOCKED for all treatments. No PAG, directed/bidirected/circle endpoints, CI configuration, or selection-bias model exists.

## K. Stability analysis

NOT RUN — no valid matrix or raw graphs exist to resample. Bootstrap frequencies are empty. Any later high resampling frequency indicates stability under resampling, not causal truth.

## L. Algorithm comparison

NOT APPLICABLE — PC/GES/FCI were not run. No edge comparison or majority-vote graph is produced.

## M. ECG representation analysis

All 95 engineered ECG features and 64 `z_ecg` dimensions remain outside discovery matrices. Phase 3/4/5 left baseline timing unresolved; Phase 5 found embeddings complete in the master table but provenance unresolved. Dimensions are not individual physiological causes; low pairwise latent correlation is not causal independence. No dense ECG edge cluster can be assessed without a graph.

## N. Constraint violations / suspicious structures

No graph was produced, so no edge violations or graph structures can be inspected. Phase 6 hard/soft distinction is preserved: hard constraints will be applied only after validating node expansion; soft relationships remain nonbinding. Suspicious structures cannot be assessed without algorithm outputs.

## O. Raw algorithmic graphs

None. `raw_graphs` is empty; no algorithmic output is fabricated.

## P. Stable candidate graphs

None. `stable_candidate_graphs` is empty; no stability threshold or candidate graph is asserted.

## Q. Interpretation boundaries

This report does not claim algorithmic discovery, candidate causal structure, a true DAG, a treatment effect, or an adjustment set. It does not infer treatment time from window labels, first ECG, MI timestamps, or `time_diff_hours`; it does not equate prediction/correlation with causation. Preserve the pipeline distinction: for MI patients `time_diff_hours = ecg_time - index_mi_time`, while Control_Symptomatic values use an admission-time anchor/fallback and are not MI-relative. The master data have zero `MI_Post-Incident` rows. Therefore the categorical `Label_Troponin` cohort label is not interchangeable with the raw temporal variable, and no row is classified as post-MI from `time_diff_hours > 0`.

## R. Limitations

- Exact treatment assignment/administration times are unavailable.
- No final index ECG is selected; `first ECG = baseline` is not assumed.
- The causal outcome definition and event horizon are unresolved.
- Phase 3 has no clearly eligible baseline covariate.
- ECG and VAE preprocessing provenance remain unresolved.
- Several patients contribute repeated admissions (see JSON); effective independent sample size and a cluster-aware CI/score procedure are not established.
- Marginal exposure prevalence exists but conditional positivity in a final cohort is unassessed.
- A dedicated Phase 0 output was not found locally.
- This is a blocked readiness gate, not completion of statistical causal discovery.

## S. Phase 7 Decision Record

1. **Discovery unit**: Admission-level; repeated ECGs are not independent units and patient dependence remains.
2. **Treatments evaluated**: Aspirin, statin, beta blocker, and ACE inhibitor; each separately gated.
3. **Outcome representation**: Not used in discovery. `is_MI` is only a provisional candidate; `Label_Troponin` is cohort metadata; outcome definition/horizon unresolved.
4. **Discovery matrices used**: None. A/B/C are schema-level candidates only; D reduction was not performed.
5. **PC configuration**: NOT RUN — readiness blocked; no alpha or CI test selected.
6. **GES configuration**: NOT RUN — readiness blocked; no score or penalty selected.
7. **FCI configuration**: NOT RUN — readiness blocked; no CI configuration selected.
8. **CI tests**: None selected or performed; mixed-data and clustering method needs justification after valid matrix definition.
9. **Missing-data strategy**: Descriptive audit only; no imputation, complete-case restriction, or row dropping.
10. **Hard constraints applied**: None to a graph because no graph was generated; Phase 6 hard rules preserved for later use.
11. **Soft constraints used**: Not forced; Phase 6 soft edges remain nonbinding.
12. **Raw graph summary**: None; PC/GES/FCI not run.
13. **Stable candidate graph summary**: None; no resampling/parameter analyses run.
14. **Bootstrap/stability results**: None; stability is not evidence of causal truth even when later computed.
15. **PC/GES/FCI agreement**: Not assessed.
16. **Major algorithm disagreements**: Not assessable because no algorithm was run.
17. **Important temporal violations**: No graph edges available to assess; core temporal blockers are treatment time zero, ECG baseline, and outcome horizon.
18. **`z_ecg` treatment**: Excluded from any matrix; remains quarantined pending provenance and treatment-relative eligibility.
19. **Most stable candidate relationships**: None identified; no discovery/stability calculations performed.
20. **Relationships requiring literature audit**: Any future soft candidate relationship selected for follow-up; none is treated as discovered here.
21. **Relationships requiring expert validation**: Treatment assignment, ECG timing, severity/indication, and outcome-horizon relationships before modeling.
22. **Whether a final DAG exists**: NO.
23. **Whether an adjustment set exists**: NO.
24. **Whether ATE/CATE was performed**: NO.
25. **Remaining blockers**: Exact treatment time zero, incident outcome/horizon, final ECG eligibility, ECG/VAE preprocessing provenance, no clearly eligible baseline covariates, and patient-cluster-aware discovery method.
26. **Phase 8 handoff**: Resolve these prerequisites before discovery; then run per-treatment PC/GES/FCI with nonbinding soft knowledge, hard constraints, and stability analysis.

Stopping rule satisfied: no causal effect estimation, adjustment-set selection, final DAG declaration, or algorithmic causal truth claim.
