# Phase 14: Timestamped Statin Exposure and Acute MI Episode Validation

## Exposure linkage

The analysis selected only the 2,986 index admissions already marked `statin_during=1`. It did not derive or change that indicator. EMAR `charttime` is treated as the recorded administration event time; `storetime` is retained as record-entry time. Prescription `starttime` is reported separately as an order timestamp and is never counted as an administration.

- EMAR source: `raw_emar_filtered_to_existing_statin_during_cohort`.
- Prescription source: `raw_prescription_orders_filtered_to_existing_statin_during_cohort`.
- Index admissions with at least one linked EMAR statin record: 1,505 of 2,986 (50.40%).
- Linked EMAR administration rows: 7,608 across 6 distinct medication-name strings; 7,574 timestamps fall within the closed index-admission interval, 33 precede admission, and 1 follow discharge.
- Patients with a validated first in-admission administration timestamp: 1,500 of 2,986 (50.23%).
- Among those 1,500, median time from admission to first administration was 13.45 hours; median time from first administration to discharge was 78.55 hours.
- Prescription orders are separate: 3,837 matched statin order rows, with 3,609 start times during admission, 203 before admission, and 24 after discharge. These are not treated as administrations or discharge prescriptions.

`statin_exposure_timestamps.parquet` preserves linked EMAR statin records and prescription-order records, plus one explicit linkage-status row for treated admissions without a matched EMAR row. First-administration elapsed times and record-level validation are in the adjacent CSVs.

The archive provides prescription-order records, but no separate discharge-medication reconciliation or explicit discharge-prescription strategy. Prescription start times remain order records; their presence does not establish a discharge prescription or long-term adherence. This analysis does not query raw medication records for the cohort's 2,889 missing `statin_during` entries, as requested; their exposure status remains unknown.

## Acute MI episode validation

The 555 Phase 13 first subsequent acute-coded admissions were linked to full diagnosis rows and admission chronology. Counts within 1, 7, and 30 days of discharge are 14, 103, and 226. There were 12 candidates with another acute-coded admission within 7 days after the first candidate, and 54 within 30 days. 233 index admissions themselves carry an acute MI code; 136 candidates have a chronology/location transfer proxy.

Classification counts (screening labels, not adjudications): `{"candidate distinct acute MI": 211, "possible continuation of index MI episode": 114, "possible transfer/readmission for the same episode": 167, "uncertain episode classification": 63}`. Complete diagnosis-code combinations, candidate IDs, adjacent admissions, timing, repeat-coded admissions, rationale, and classification are provided in `acute_mi_episode_validation.csv`; all non-distinct/uncertain labels are in `acute_mi_uncertain_events.csv`. The supplied local artifacts contain diagnosis codes and admission chronology but no relevant clinical notes or adjudication source. Code combinations cannot establish a distinct infarction episode. All 555 events were retained; time proximity and adjacent-admission clues are triage evidence only, not a rule for discarding early events or proof of a separate MI.

## Revised target-trial feasibility

**Current contrast:** recorded statin administration during the index admission versus no recorded administration. `statin_during=1` is the established exposure indicator, but timestamp evidence is assessed only among its already exposed admissions here. First administration time, when linked, can establish that recorded administration occurred before discharge; it does not alone establish a randomized/causal assignment time or discharge treatment.

**Alternative contrast:** a statin prescription or treatment strategy at discharge versus none. This is not established by the current indicator. No separate discharge-prescription source was found in the local artifacts; available prescription orders must not be relabeled as discharge prescriptions. Long-term adherence is not observable from inpatient EMAR.

**Recommendation: CONDITIONAL GO for an in-hospital exposure observational comparison only; pause causal effect estimation pending endpoint and confounding validation. NO-GO for a discharge-initiation intervention.** Timestamped administrations were found for 1,500 of 2,986 treated admissions. The 1,481 without any linked EMAR record are not thereby proven unexposed; their recorded `statin_during=1` status was preserved. The 555 acute-coded candidate admissions provide a code-based endpoint, but episode duplication/continuation remains unresolved without clinical review. Baseline age, sex, comorbidities, and selected prior medication features exist for known-treatment patients, but this does not establish adequate confounding control; disease severity, treatment indication, exact timing, and missing exposure among 2,889 patients remain important. Keep the in-hospital contrast explicitly observational. Before estimating a causal effect, validate linkage completeness, episode definition, time zero, and a defensible confounding strategy. No treatment-effect models or new effect estimates were fitted.

## Reproducibility

With previously extracted audit tables:

```powershell
.\.venv\Scripts\python.exe -m causal_models.phase14_exposure_endpoint.analyze_phase14
```

With raw sources supplied:

```powershell
.\.venv\Scripts\python.exe -m causal_models.phase14_exposure_endpoint.analyze_phase14 --emar <path-to-emar.csv> --prescriptions <path-to-prescriptions.csv>
```
