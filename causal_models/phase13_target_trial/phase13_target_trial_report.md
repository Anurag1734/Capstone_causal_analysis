# Phase 13: Target-Trial Alignment and Endpoint Validation

## Estimand and alignment

The current contrast is among patients with a previously MI-coded admission who survived the selected index admission to discharge: `statin_during=1` versus `statin_during=0`, with follow-up starting at index discharge and a 12-month horizon. It is an association between in-hospital exposure and subsequent outcomes, **not** a statin-initiation-at-discharge intervention. `statin_during` has no verified exposure timestamp in this cohort, so exposure status before follow-up begins is not established. The cohort summary records that admission-level prescription/EMAR linkage to a timestamped target-class exposure is unavailable. Consequently, treatment assignment can incorporate exposure after admission and potentially near discharge; a discharge-initiation causal interpretation risks temporal misalignment and immortal-time/selection bias. No treatment variable was redefined.

## Cohort selection and missingness

There are 7,545 eligible index admissions/patients. Treatment is known for 4,656 (2,986 treated; 1,670 controls); 2,889 records have no treatment indicator and were not imputed. All 4,656 known-treatment records have the available Phase 11 baseline feature set. The existing split-restricted complete-case population is 3,230. Baseline covariate and follow-up selection by treatment group are in `cohort_selection_by_treatment.csv`; the complete flow is in `cohort_selection_flow.csv`.

| treatment_group | cohort_n | treatment_known_n | baseline_complete_n | complete_followup_n | followup_complete_percent | assigned_to_existing_split_n | final_complete_case_n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| control | 1670 | 1670 | 1670 | 1216 | 72.81 | 1670 | 1216 |
| treated | 2986 | 2986 | 2986 | 2014 | 67.45 | 2986 | 2014 |
| treatment_missing | 2889 | 0 | 0 | 1755 | 60.75 | 2338 | 0 |

Follow-up completion in known-treatment patients differs by treatment: treated 67.45% and controls 72.81% (a 5.37 percentage-point difference). Complete-case selection is therefore differential; it should not be presumed ignorable.

## Endpoint evidence

The existing broad endpoint has 1,833 recurrent MI-coded admissions; median time from discharge is 54.25 days, with 31 within 1 day, 250 within 7 days, and 679 within 30 days. Among its event admissions, code class counts are acute_code_present: 494, icd9_412_only: 1,339. ICD-9 `412` alone denotes old MI/history rather than acute infarction. The broad endpoint therefore cannot be interpreted as validated acute recurrent MI.

Using diagnosis rows and MI-admission candidates, the acute-code screen (ICD-9 `410*`, ICD-10 `I21*`/`I22*`) identified 555 first subsequent acute-coded admissions within observed follow-up. Median time was 47.70 days; 14 occurred within 1 day, 103 within 7 days, and 226 within 30 days. These remain code-based admissions, not clinically adjudicated recurrent episodes; early admissions may represent continuing care or readmission for the same episode. The files do not establish clinical episode boundaries. The derived `acute_recurrent_mi` indicator is missing for incomplete or event-order-uncertain follow-up; competing deaths are explicitly labeled as competing events, not event-free.

Existing cohort event types: `{"competing_death": 994, "event_free": 2158, "incomplete_followup": 2560, "recurrent_mi": 1833}`. Acute-screen event types, including incomplete follow-up and same-day event-order uncertainty, are `{"acute_recurrent_mi": 555, "competing_death": 1219, "event_free": 2912, "incomplete_followup": 2859}`. The admission-level event/code and timing tables preserve the underlying IDs and dates.

## Competing-risk description

The attached cumulative-incidence estimates use index discharge as time origin, acute-coded MI and death as separate event types, and incomplete or same-day order-uncertain follow-up as censored. Treatment-stratified estimates are descriptive only and do not adjust for confounding. Broad-endpoint results are also included, but include history-code events and are not acute-MI cumulative incidence.

| endpoint_definition | treatment_group | horizon_days | n | input_n | excluded_n | acute_mi_cif | death_cif |
| --- | --- | --- | --- | --- | --- | --- | --- |
| acute_code_only | control | 30 | 1670 | 1670 | 0 | 0.0229 | 0.0551 |
| acute_code_only | control | 90 | 1670 | 1670 | 0 | 0.0364 | 0.1133 |
| acute_code_only | control | 180 | 1670 | 1670 | 0 | 0.0505 | 0.1645 |
| acute_code_only | control | 365 | 1670 | 1670 | 0 | 0.0722 | 0.2346 |
| acute_code_only | treated | 30 | 2986 | 2986 | 0 | 0.0467 | 0.0537 |
| acute_code_only | treated | 90 | 2986 | 2986 | 0 | 0.0740 | 0.1019 |
| acute_code_only | treated | 180 | 2986 | 2986 | 0 | 0.0927 | 0.1584 |
| acute_code_only | treated | 365 | 2986 | 2986 | 0 | 0.1260 | 0.2376 |
| existing_broad_mi_code | control | 30 | 1670 | 1670 | 0 | 0.1163 | 0.0517 |
| existing_broad_mi_code | control | 90 | 1670 | 1670 | 0 | 0.1953 | 0.0947 |
| existing_broad_mi_code | control | 180 | 1670 | 1670 | 0 | 0.2576 | 0.1355 |
| existing_broad_mi_code | control | 365 | 1670 | 1670 | 0 | 0.3413 | 0.1784 |
| existing_broad_mi_code | treated | 30 | 2985 | 2986 | 1 | 0.1245 | 0.0490 |
| existing_broad_mi_code | treated | 90 | 2985 | 2986 | 1 | 0.2110 | 0.0871 |
| existing_broad_mi_code | treated | 180 | 2985 | 2986 | 1 | 0.2715 | 0.1322 |
| existing_broad_mi_code | treated | 365 | 2985 | 2986 | 1 | 0.3426 | 0.1963 |

## Decision: C — retain exploratory status

The current data do not support a defensible causal claim for statin initiation at discharge. The exposure lacks event-time ordering relative to discharge, treatment is missing for 2,889 of 7,545 patients, and the original recurrent-MI outcome contains a large history-code-only component. The acute-code screen improves code specificity but cannot distinguish a new infarction episode from ongoing care, nor validate diagnosis accuracy. Competing death and incomplete observation must remain distinct.

**Next modeling action:** establish timestamped medication administration/order exposure relative to the index discharge and validate acute MI episodes (including same-episode readmissions) using an agreed clinical/code-based rule. Then define a discharge-aligned target trial and estimate cumulative incidence with death as a competing event, with explicit handling of censoring and confounding. Until those checks are possible, retain the Phase 11–12 analyses as exploratory and do not reinterpret them as effects of discharge initiation.

## Reproducibility

From the repository root run:

```powershell
.\.venv\Scripts\python.exe -m causal_models.phase13_target_trial.analyze_target_trial
```

The script reads the existing cohort, MI-admission, diagnosis-code, and split artifacts only; it does not modify them or refit models.
