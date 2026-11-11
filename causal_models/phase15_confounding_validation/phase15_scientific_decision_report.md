# Phase 15: Cohort Selection, Confounding and Endpoint Validation

## Scope and estimand

This report reuses the saved Phase 14 EMAR/prescription linkages, episode classifications, existing cohort, diagnosis records and patient-level splits. No treatment indicators, datasets, or models were rebuilt or modified; no treatment-effect estimates were calculated. The descriptive treatment comparison is `statin_during=1` versus `0` in the known-treatment subset, not an initiation-at-discharge effect.

## Workstream A — EMAR linkage selection

Of 2,986 already exposed admissions, 1,505 (50.40%) had at least one statin-named EMAR row satisfying Phase 14’s recorded-administration filter and exact `subject_id`+`hadm_id` match. 1,481 (49.60%) had no such row. The validated first in-admission timestamp was available for 1,500. The 1,481 are **unmatched by this extraction/linkage rule**, not untreated or proven administration failures. Phase 14 retained 7,608 EMAR rows on 1,505 admissions; 7,574 timestamps were within the index interval, 33 before admission and one after discharge.

The saved EMAR output is already filtered to statin medication-name matches, administration-like event statuses, and exact admission identifiers. It does not retain declined/not-administered statin rows or non-statin EMAR context for unmatched admissions, so it cannot determine whether absence reflects a non-administration status, drug-name mapping, missing/invalid ID, a different admission, or deliberate preprocessing. Prescription-order presence is separately included in the comparison; it is not proof of administration.

**Index admission availability:** all 7,545 cohort `hadm_id`s are present in `admissions_chronology.parquet`; the treated linked and unmatched admissions all have the processed master baseline row and Phase 9 split membership. Therefore, missing EMAR linkage is not explained by a missing index-admission chronology record or absent processed feature row in these groups. It is not possible to determine whether upstream ECG cleaning affected EMAR processing; no per-admission EMAR exclusion log was retained. A present feature row does not establish an ECG from the index admission specifically.

| Measure | EMAR-linked | No linked EMAR | SMD |
|---|---:|---:|---:|
| Variable | Left mean/prevalence | Right mean/prevalence | SMD | Missing L/R |
|---|---:|---:|---:|---:|
| anchor_age | 69.227 | 70.601 | -0.111 | 0/0 |
| sex_male | 0.627 | 0.632 | -0.011 | 0/0 |
| diabetes | 0.498 | 0.466 | 0.064 | 0/0 |
| hypertension | 0.862 | 0.847 | 0.043 | 0/0 |
| ckd | 0.389 | 0.313 | 0.161 | 0/0 |
| statin_before | 0.001 | 0.073 | -0.385 | 0/0 |
| prior_mi_coded_admission_count | 1.000 | 1.000 | NA | 0/0 |
| length_of_stay_days | 6.143 | 5.330 | 0.130 | 0/0 |
| has_index_admission_record | 1.000 | 1.000 | NA | 0/0 |
| has_master_baseline_features | 1.000 | 1.000 | NA | 0/0 |
| has_phase9_split_row | 1.000 | 1.000 | NA | 0/0 |

Full group statistics, categories, missingness, and SMDs: `emar_linkage_comparison.csv`; row membership and order/admin counts: `emar_linkage_membership.csv`.

## Workstream B — Baseline and index-admission differences

There are 2,986 treated and 1,670 controls with known `statin_during`; 2,889 additional patients have missing treatment and are not reclassified. Group summaries and SMDs below are descriptive, unadjusted. Large absolute SMDs flag observed imbalance; they do not prove causal confounding or its absence.

### Baseline variables

| Variable | Left mean/prevalence | Right mean/prevalence | SMD | Missing L/R |
|---|---:|---:|---:|---:|
| anchor_age | 69.908 | 68.363 | 0.116 | 0/0 |
| sex_male | 0.629 | 0.602 | 0.057 | 0/0 |
| diabetes | 0.482 | 0.411 | 0.142 | 0/0 |
| hypertension | 0.854 | 0.807 | 0.129 | 0/0 |
| ckd | 0.351 | 0.278 | 0.156 | 0/0 |
| statin_before | 0.037 | 0.337 | -0.854 | 0/0 |
| aspirin_before | 0.081 | 0.321 | -0.642 | 0/0 |
| beta_blocker_before | 0.030 | 0.122 | -0.378 | 0/0 |
| acei_before | 0.026 | 0.158 | -0.506 | 0/0 |
| prior_mi_coded_admission_count | 1.000 | 1.000 | NA | 0/0 |
| days_since_last_prior_mi_code | 379.522 | 351.927 | 0.048 | 0/0 |

`statin_before`, aspirin, beta-blocker, and ACE-inhibitor `*_before` indicators are prescription/order proxies with uncertain timing and adherence. Prior MI is 1 for every cohort member by eligibility; prior MI admission count/recency are based on MI-coded admissions and may not equal distinct clinical episodes. Age and sex are available across the cohort; most other master-derived baseline fields are available only in the 4,656 known-treatment rows.

### Index stay and diagnosis-derived severity proxies

| Variable | Left mean/prevalence | Right mean/prevalence | SMD | Missing L/R |
|---|---:|---:|---:|---:|
| length_of_stay_days | 5.740 | 4.148 | 0.262 | 0/0 |
| index_acute_mi_code | 0.188 | 0.060 | 0.364 | 0/0 |
| heart_failure_code | 0.491 | 0.339 | 0.307 | 0/0 |
| cardiogenic_shock_code | 0.019 | 0.008 | 0.087 | 0/0 |
| acute_kidney_injury_code | 0.249 | 0.160 | 0.215 | 0/0 |
| acute_respiratory_failure_code | 0.062 | 0.037 | 0.111 | 0/0 |

These are index-admission diagnoses or completed length of stay without reliable timing relative to first statin administration. They may reflect post-exposure severity, mediators, or indication and are **not primary baseline adjustment variables**. Diagnosis codes were left missing when no index-admission diagnosis record was available rather than recoded to absence; diagnosis coverage was available for 7,541/7,545 admissions. The diagnosis-derived fields indicate a code somewhere in the admission, not when it occurred or severity. ICU admission, ventilation and vasopressor measures are unavailable in the retained local tables; they were not fabricated. Full comparisons and missingness are in `index_severity_comparison.csv`.

## Workstream C — Adjustment strategy against the existing provisional DAG

## Adjustment-set recommendation (provisional DAG)

**Primary candidates, only for a newly defined baseline that precedes assignment:** age, sex, diabetes, hypertension, CKD, prior cardiovascular history/severity and recency, verified prior statin use, and pre-assignment concomitant aspirin, beta-blocker, and ACE-inhibitor use. The retained `*_before` medication variables are prescription/order proxies with uncertain history window and adherence; they are not confirmed use and should be sensitivity proxies, not substitutes for verified pre-treatment history. Prior MI eligibility is fixed at 1 in this restricted cohort, so it is not a discriminating adjustment covariate. Admission sequence, insurance, and admission location are imperfect healthcare-utilization/access proxies and should be considered only as sensitivity covariates.

**Sensitivity/indication proxies, not primary adjustment by default:** index-admission diagnosis codes for MI, heart failure, cardiogenic shock, AKI, and respiratory failure; admission type and admission location; and length of stay. These describe the hospitalization, but available diagnosis rows are not timestamped relative to the first statin dose, and length of stay is necessarily determined after admission and may follow treatment. Adjusting for these can condition on post-treatment severity, mediators, or selection/collider variables. A diagnosis code is not a validated severity score or treatment indication.

**Unavailable or inadequate:** measured lipid burden, detailed coronary anatomy, prior MI severity/adjudicated episode count, clinician treatment indication, frailty, outpatient adherence, and complete healthcare access are not present as validated baseline covariates. The retained local data have no ICU-stay, ventilation, or vasopressor table; no such feature was fabricated. EMAR/medication data can inform recorded treatment but do not recover these confounders.

**Exclude from baseline X:** `statin_during` is the exposure; `statin_after` is post-discharge; any post-dose/index-stay severity, procedures, length-of-stay consequences, subsequent medications, recurrent-MI codes, follow-up, and death are outcomes, mediators, or post-treatment variables—not baseline confounders. The existing provisional DAG marks `statin_before` as an imperfect proxy and possible collider of prior use and healthcare access; preserve it as a prespecified sensitivity analysis rather than assuming it is safe primary adjustment. Concomitant `*_before` proxies also need true pre-assignment timing.

The DAG’s selected prior-MI survivor restriction can induce selection bias. Conditioning further on an ECG-linked/model-ready subset or complete follow-up may add selection; IPCW for outcome censoring does not repair missing exposure, absent index features, or selection into ECG data. The available measured set is not sufficient to assert conditional exchangeability.

## Workstream D — Acute MI endpoint

The Phase 14 classification of all 555 acute-code candidates is retained unchanged:

- candidate distinct acute MI: 211
- possible transfer/readmission for the same episode: 167
- possible continuation of index MI episode: 114
- uncertain episode classification: 63

There were 14 events within 1 day, 103 within 7 days, and 226 within 30 days of discharge. The retained review found 54 candidates with another acute-coded admission within 30 days after the first event and 136 with a transfer/location chronology proxy. The index admission itself had acute MI codes in 233 candidates. Diagnosis combinations and chronology identify candidates and continuity/transfer concerns, but no clinical notes or adjudication establish distinct MI episodes. The 555-event endpoint cannot currently be treated as a clinically validated count of distinct recurrent MIs. No early candidate was removed.

## Workstream E — Selection and missingness (kept separate)

| Selection stage | N | Definition / note |
|---|---:|---|
| eligible_prior_mi_discharge_survivors | 7545 | index cohort; one admission per patient |
| statin_during_known | 4656 | missing treatment separately: 2889 |
| baseline_feature_set_complete | 4656 | missing any required Phase 11 baseline field: 2889 |
| followup_endpoint_observed | 4985 | incomplete or uncertain endpoint: 2560 |
| in_existing_phase9_split_files | 6994 | not found in exported split files: 551 |
| known_treatment_in_phase9_split_files | 4656 | known-treatment rows available to Phase 11 split selection |
| phase11_complete_case_population | 3230 | requires known treatment, observed outcome, baseline features, and split membership |
| phase11_known_treatment_in_split_with_incomplete_followup | 1426 | not treated as outcome-negative |
| known_treatment_absent_from_phase9_split_files | 0 | absence is established; reason is not retained |
| phase11_removed_due_to_missing_treatment_among_split_rows | 2338 | treatment not reconstructed |
| phase11_removed_due_to_missing_baseline_features_among_split_rows | 0 | baseline features unavailable in this index row |
| statin_exposed_admissions | 2986 | existing statin_during=1 indicator |
| exposed_with_linked_emar_statins | 1505 | at least one filtered statin EMAR administration row by subject_id+hadm_id |
| exposed_without_linked_emar_statins | 1481 | link absence is not evidence of no administration |
| acute_coded_candidate_events | 555 | Phase 14 candidates; classification retained |

All 4,656 known-treatment rows are present in the exported split files. Of these, 3,230 entered the Phase 11 complete-case population and 1,426 had incomplete/uncertain follow-up. Separately, 2,338 of the 2,889 missing-treatment rows appear in the split files, while 551 are absent from them. The 1,481 EMAR-unmatched exposed admissions are another distinct linkage category and must not be merged with either source of missingness.

The saved preprocessing summary reports 2,889 index admissions without a matching master baseline-feature row and 551 not present in the Phase 9 patient split files. The retained data do not preserve a row-level cleaning/exclusion reason, so the 551 absent split rows cannot be labeled a proven intentional preprocessing exclusion; they are all in the missing-treatment group. The known-treatment rows are present in the split set, and the complete-case reduction among those is due to incomplete/uncertain outcome follow-up. Selection into ECG-linked features may limit generalizability. IPCW for incomplete follow-up does not correct absent treatment, missing baseline features, EMAR linkage, or ECG selection.

## Workstream F — Scientific decision

### **B. CONDITIONAL GO — descriptive in-hospital exposure comparison only; pause further causal effect estimation**

The existing exposure indicator and covariates permit descriptive comparisons, and timestamped EMAR administrations were linked for 1,500 admissions. However, 1,481 treated admissions lack a filtered exact-ID EMAR match with no retained audit trail that explains why. The acute-code endpoint includes 555 candidates but cannot identify which are distinct clinical episodes. Confounding by indication and severity is incompletely controlled: lipid burden, coronary disease burden, clinical indication, and prior MI severity are not measured as validated baseline fields; index-stay severity timestamps and strong ICU supports are unavailable. The observed baseline and utilization variables do not establish exchangeability, and selected prior-MI survivor plus ECG/master/complete-case selection remain concerns.

**Do not fit another ATE/CATE model yet. Next exact research action:** generate and retain an EMAR inclusion/exclusion audit for all treated index admissions from raw `emar.csv`, separately tallying medication-name matches, status/event-text inclusion/exclusion, missing/unmatched IDs, and admission mismatch; in parallel, obtain clinical adjudication or a validated episode-linkage rule for the 555 candidates. Then construct a timestamp-aligned confounding set using only pre-dose covariates and explicitly address missing-treatment/ECG selection before deciding whether causal estimation is justified.

No causal effect is established by these descriptive comparisons.
