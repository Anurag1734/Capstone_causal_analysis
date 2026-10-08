# Statin exposure provenance audit

## Audit objective

This audit traces the provenance of the current `statin_before` variable and evaluates whether it can support a defensible treatment-specific causal time zero and a valid pre-treatment ECG rule.

## Short conclusion

`statin_before` is not currently a validated treatment-timing variable. It is a binary pre-admission indicator derived from medication prescription records within a historical prescription window. The available data support a statement such as:

- "the patient had a qualifying statin prescription in the recent pre-admission period"

but not a stronger statement such as:

- "the patient was newly prescribed statin therapy before the ECG"
- "the patient began statin therapy at time T"
- "the treatment was definitely administered before the ECG"
- "the ECG was definitely measured before treatment exposure"

This is why the current design remains NOT READY for treatment-specific DAG work.

## Provenance chain

The current evidence in the project documentation supports the following provenance chain:

1. Source system: MIMIC-IV hospital data
2. Source table: `hosp/prescriptions.csv`
3. Relevant record fields: `subject_id`, `hadm_id`, `starttime`, `stoptime`, `drug_type`, `drug`, `route`, `dose_val_rx`, `form_rx`, `order_provider_id`, etc.
4. Source semantics: medication orders/prescriptions, not a validated administration log
5. Statin identification: rows where the medication name maps to a statin class (e.g., atorvastatin, simvastatin, rosuvastatin, pravastatin, lovastatin, fluvastatin, pitavastatin)
6. Temporal filtering: a recent pre-admission window near the current admission anchor
7. Admission linkage: join on `subject_id` and/or `hadm_id` according to the admission anchor logic
8. Exposure construction: aggregate to a binary per-admission `statin_before` indicator
9. Interpretation in the project docs: recent inpatient prescription pattern, not necessarily verified outpatient baseline medication use

## Source evidence from the repository

The project documentation explicitly describes the source in a way consistent with this conclusion:

- `docs/longitudinal_mi_cohort_extraction.md` states that treatments are constructed from `hosp/prescriptions.csv` and describes the windowed logic as "Before" and "After" using prescription data.
- It also states a `statin_before` feature is created as a binary flag using the pre-admission window.
- `docs/raw_data_analysis.md` defines `prescriptions.csv` as a medication prescriptions table, not as a medication administration table.
- The same source document identifies `starttime` and `stoptime` as the key prescription timestamps.
- The project documentation warns that the `*_before` variables capture recent prescription patterns rather than true outpatient baseline medication use.

The key point is that the current schema is defined around medication records, not around a verified treatment start time.

## Exact source semantics

`prescriptions.csv` records medication orders/prescriptions, which are not the same as:

- actual drug administration
- dispensation
- home medication state
- recorded patient self-report
- confirmed outpatient drug coverage
- validated treatment initiation at an exact point in time

Therefore the exposure is best described as a pre-admission statin prescription indicator, not a causal treatment administration time.

## Temporal window logic

The project documentation indicates that the pre-admission statin window is approximately:

- prior discharge → admission anchor
- with an approximately 7-day lookback bounded by prior discharge

This window is a design convenience for a medication-prescription feature, not a validated treatment-assignment time. It is not the same as a treatment start time or a treatment decision time.

## What the current source can and cannot support

### What the source supports

- a patient-level or admission-level indicator for recent statin prescription presence in a pre-admission window
- a coarse understanding that a statin was prescribed prior to the current admission
- possible reconstruction of prescription start and stop times for some patients

### What the source does not clearly support

- exact treatment initiation time for the current relevant exposure
- whether the patient was a new vs continuing user
- whether the prescription was filled or consumed
- whether the drug was active at the selected ECG time
- whether the prescription was initiated before the patient’s underlying clinical deterioration
- whether the selected ECG was captured before treatment exposure

## Provenance verdict

The available evidence supports the following precise wording:

`statin_before` is a binary admission-level indicator for a recent pre-admission statin prescription in the MIMIC-IV prescriptions table. It is not a verified treatment-assignment timestamp and cannot be treated as a causal time zero without additional source-time evidence.

This is the core reason the statin-specific design remains NOT READY.
