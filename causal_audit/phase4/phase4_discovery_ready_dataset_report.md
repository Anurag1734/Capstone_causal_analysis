# Phase 4 — Discovery-Ready Dataset Construction

## A. Objective

Construct and document a layered, provisional data representation for later causal discovery. No DAG, discovery algorithm, treatment-effect estimation, final treatment, time zero, index ECG, or adjustment set is selected.

## B. Input dataset

Actual splits: train 262,813; validation 56,319; test 56,798; combined 375,930 ECG rows, 191,369 admissions, 99,256 patients, 184 original variables.

## C. Unit of analysis

Admission-level remains the primary observational unit. `hadm_id` is the admission key, `SubjectID` is retained for patient dependence, and `study_id` links ECG observations. Identifiers are not causal covariates.

Repeated ECGs: 85,609 admissions (44.735%) have multiple ECGs; maximum 107. Repeated admissions: 34,625 patients; maximum 72 admissions per patient.

## D. ECG selection

| Candidate rule | Admissions represented | Excluded | MI admissions | Control-only admissions | Outcome/time dependent | Status |
|---|---:|---:|---:|---:|---|---|
| A_first_ecg_admission | 191,369 | 0 | 7,362 | 184,007 | False | PROVISIONAL / CANDIDATE |
| B_first_ecg_before_MI | 4,521 | 186,848 | 4,521 | 0 | True | PROVISIONAL / CANDIDATE |
| C_closest_ecg_before_MI | 4,521 | 186,848 | 4,521 | 0 | True | PROVISIONAL / CANDIDATE |

Among B/C's 4,521 common eligible admissions, the rules select different ECGs in 2,452 admissions (54.24%).

Rule A selects the earliest ECG timestamp per admission where timestamp is valid; it is operationally neutral but not established as pre-treatment. Rules B/C require MI-labeled admissions with a unique non-null MI timestamp and use that event time to select an ECG; they are outcome/time-dependent and do not represent controls. Rule D is blocked because no clinical eligibility criterion is available. No final causal index ECG is declared and no candidate feature dataset is persisted as final.

## E. Variable inventory

All 184 original variables are accounted for in `phase4_discovery_ready_dataset_results.json`. Family counts: G. Identifiers: 3, F. Temporal/index variables: 1, E. Outcome variables: 4, C. Candidate latent ECG variables: 64, B. Candidate ECG variables: 95, A. Candidate baseline clinical variables: 6, D. Treatment/exposure variables: 11.

## F. Candidate discovery variables

- Candidate clinical baseline: `anchor_age`, `sex_male`, `diabetes`, `hypertension`, `ckd`, `prior_mi` (provisional, admission-consistency checked, provenance/timing still needs verification).
- Candidate ECG representation: 95 ECG features and all 64 `z_ecg` dimensions, quarantined until index ECG and time zero are established.
- Treatment variables remain separate. Outcomes, temporal fields, and identifiers are excluded from the covariate matrix.

Admission-level clinical candidate variables were checked for within-admission consistency; treatment flags are treated as admission-level metadata in line with Phase 2. Full missingness, prevalence, constant/near-constant, duplicated-column, range/outlier, correlation, split-shift, and value-domain diagnostics are in the JSON artifact. No feature was removed.

## G. Preprocessing

Phase 4 performed diagnostics only. No imputation, scaling, clipping, feature removal, or PCA was performed. Missing values are reported; exact duplicates and correlations are reported but retained. Documentation describes upstream winsorization, Yeo-Johnson transformation, and robust scaling for ECG features, but local scripts/fitted objects needed to verify train-only fit scope were not present.

## H. Leakage audit

Exclude `Label_Troponin`, `is_MI`, `index_mi_time`, and `time_diff_hours` from the discovery covariate matrix. The actual master schema contains no troponin-named feature; project rule remains NEVER USE TROPONIN AS A FEATURE. Keep post-discharge and acute treatment flags separate. ECG and latent representations may encode MI morphology but cannot be called leakage-free baseline covariates until the index ECG is resolved.

## I. Split integrity

Exact pairwise split intersections: `study_id` pass=True, `hadm_id` pass=True, `SubjectID` pass=True. No split recreation was performed. Train-only preprocessing fit scope is UNRESOLVED — project documentation describes preprocessing, but local source code and fitted transformer artifacts needed to verify train-only fitting were not found.

## J. ECG representation

Retain both raw handcrafted ECG variables and `z_ecg` only as separate candidate representations, not a combined confirmed baseline matrix. Correlations, duplication, ranges, missingness, constant/near-constant columns, and split shifts are quantified in the JSON. No feature is removed solely for correlation. Predictive performance is not evidence of a causal role.

## K. Discovery readiness

Ready: split-preserving admission metadata architecture, variable inventories, and descriptive candidate diagnostics. BLOCKED: causal discovery covariate matrix; the final index ECG, treatment-specific time zero, causal outcome specification, and upstream preprocessing leakage checks remain unresolved.

## L. Phase 5 handoff

Phase 5 must audit z_ecg source lineage: confirm the waveform/study_id mapping, exact train/validation/test membership used to fit the VAE, checkpoint provenance, preprocessing fit scope, and whether any held-out or future ECG waveforms entered training. It must keep latent timing relative to treatment and outcome unresolved until an index ECG/time zero is established.

## Phase 4 Decision Record

1. Discovery-ready observational unit: Admission-level, preserved.
2. Admission representation: One metadata row per hadm_id; patient ID retained for dependence; ECG-linked values kept in separate provisional selections.
3. Candidate ECG-selection rules constructed: A_first_ecg_admission, B_first_ecg_before_MI, C_closest_ecg_before_MI
4. Preferred operational representation: Rule A is a neutral provisional operational selection by earliest ecg_time, not a preferred causal baseline. No final rule is chosen.
5. Candidate clinical variables: anchor_age, sex_male, diabetes, hypertension, ckd, prior_mi
6. ECG variables retained: {'raw_feature_count': 95, 'latent_dimension_count': 64, 'removed': []}
7. z_ecg handling: Retain all 64 dimensions in the quarantined candidate layer; no PCA. Timing and training-preprocessing lineage unresolved.
8. Treatment variables: Separate treatment layer; no primary treatment selected; not generic baseline covariates.
9. Outcome variables excluded: Label_Troponin, is_MI, index_mi_time, time_diff_hours
10. Leakage variables excluded: Label_Troponin, is_MI, index_mi_time, time_diff_hours, statin_after, statin_during, beta_blocker_during, acei_during, aspirin_during, vasopressor_during, mech_vent_during
11. Preprocessing performed: Audit/diagnostics only; no transforms, imputation, clipping, or feature removal.
12. Split integrity result: True
13. Remaining unresolved issues: Final index ECG and treatment-specific causal time zero.; Exact treatment assignment relative to selected ECG.; Upstream ECG preprocessing fit partitions and whether outcome/treatment influenced fit or selection.; Comorbidity/history feature extraction windows and possible current-admission information.; VAE training membership/checkpoint lineage and timing of each ECG representation relative to treatment/outcome.; Outcome definition and event horizon remain frozen as unresolved from Phase 2.
14. Blockers: BLOCKED — no final causal ECG-level selection without treatment-specific time zero.; BLOCKED — raw ECG and z_ecg temporal eligibility cannot be established.; BLOCKED — cannot verify train-only preprocessing fitting from local scripts/artifacts.
15. Phase 5 handoff: Phase 5 must audit z_ecg source lineage: confirm the waveform/study_id mapping, exact train/validation/test membership used to fit the VAE, checkpoint provenance, preprocessing fit scope, and whether any held-out or future ECG waveforms entered training. It must keep latent timing relative to treatment and outcome unresolved until an index ECG/time zero is established.
16. Phase 7 readiness: Partially ready for data architecture and descriptive diagnostics only. BLOCKED for causal discovery input matrix because index ECG, treatment time zero, outcome definition, and upstream preprocessing leakage checks remain unresolved.

No Phase 5 or Phase 7 analysis was performed.
