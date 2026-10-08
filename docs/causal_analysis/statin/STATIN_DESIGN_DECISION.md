# Statin design decision

## Classification

Status: C. NOT READY

This design is not ready for treatment-specific DAG work because the current data do not support a defensible treatment time zero or a pre-treatment index ECG.

## 1. Exposure definition

Current working definition:

`statin_before` is a binary admission-level flag indicating that the patient had a qualifying statin prescription in the recent pre-admission prescription window.

This is a valid descriptive epidemiologic feature, but it is not yet a valid causal treatment definition.

## 2. Exposure source

Source: MIMIC-IV `hosp/prescriptions.csv`

Relevant fields: `subject_id`, `hadm_id`, `starttime`, `stoptime`, `drug`, `drug_type`, `route`, `dose_val_rx` and related medication-order fields.

## 3. Exact temporal window

The project documentation supports a pre-admission window defined as approximately:

- prior discharge → admission anchor
- approximately 7 days prior to admission, bounded by prior discharge

This is a feature-engineering window, not a causal exposure start time.

## 4. Source timestamp availability

Prescription dates and times are available at the record level (`starttime`, `stoptime`) in the source table. However, these timestamps are not currently reconciled into a validated treatment-time-zero variable for the master dataset.

## 5. Treatment-time-zero candidates

Candidate 1: earliest qualifying prescription start time
- Observable only from source records
- Rejected because it does not necessarily represent the actual treatment assignment or initiation event

Candidate 2: prescription stop time
- Rejected because it is after the exposure window and not a valid treatment start time

Candidate 3: admission anchor time
- Rejected because it is not a treatment time

Candidate 4: no valid time zero from current workflow
- Best-supported conclusion

## 6. Recommended treatment-time-zero candidate

None.

The current data do not justify selecting a treatment-time-zero candidate for causal analysis. If a treatment-time-zero is to be recovered, additional source evidence is needed.

## 7. Reasons for rejecting alternatives

- no exact medication administration time is available in the master table
- `statin_before` is a prevalent-user or recent-prescription indicator, not a new-user initiation indicator
- prescription timing does not guarantee drug use or time of clinical action
- outcome-based temporal labels cannot justify a treatment-time zero without circular logic

## 8. Candidate index ECG rules

Candidates evaluated:

- earliest ECG in admission
- latest ECG before treatment
- first ECG before treatment
- ECG closest to treatment from before
- MI-relative ECG timing

All are either blocked or non-defensible because the treatment time is unresolved.

## 9. Recommended index ECG rule

None under the current design.

The most defensible statement is that the current master dataset does not support a valid pre-treatment ECG rule for the statin exposure.

## 10. Eligible cohort definition

The project cannot define a valid eligible cohort for statin causal design until the treatment-time-zero and baseline ECG ordering are resolved.

The current `statin_before` indicator may define a treatment-exposure cohort for descriptive epidemiology, but not for causal estimand construction.

## 11. Outcome timing implications

`index_mi_time`, `time_diff_hours`, and `Label_Troponin` cannot be used as a basis to infer treatment-time zero without circularity. The outcome timing is downstream of the causal design and is not a substitute for a treatment-time assignment.

## 12. Baseline covariate temporal eligibility

Candidate variables such as `anchor_age`, `sex_male`, `diabetes`, `hypertension`, `ckd`, and `prior_mi` may be available before treatment, but this alone does not establish a confounding design. They need treatment-specific temporal eligibility review and causal role assessment before any adjustment logic.

## 13. ECG and `z_ecg` temporal eligibility

Not established.

Without a valid treatment time, the selected ECG and latent representation cannot be guaranteed to precede exposure. The engineered 95-feature block and the 64-dimensional `z_ecg` block are therefore temporally unresolved and not acceptable as baseline covariates in a statin-specific causal model.

## 14. Prevalent-user/new-user assessment

The current statin feature is fundamentally prevalent-user / recent-prescription based rather than new-user based.

This matters because:

- prevalent users are not comparable to new users
- continuation of prior therapy differs from initiation
- the data do not reveal the medication initiation process reliably
- the effect measure would be muddled by existing treatment rather than treatment assignment

## 15. Immortal-time and reverse-causality risks

Significant risks remain:

- treatment indicator could be based on a prescription before a clinically relevant window rather than a true baseline assignment
- the selected ECG may occur after the relevant prescription or after some clinical deterioration
- medication history could reflect current illness severity or prior admissions rather than baseline treatment assignment
- the outcome and time labels are time-dependent and must not be used to recover the exposure time without risk of circularity

## 16. Positivity considerations

The exposure prevalence may be nontrivial, but the current design lacks a valid eligible cohort and a compatible baseline definition. Positivity cannot be meaningfully assessed until the denominator and treatment-time ordering are established.

## 17. Remaining assumptions

The following assumptions are still required before the design could move toward readiness:

- a verified medication start or assignment time
- a valid treatment-specific ECG rule guaranteed to precede treatment
- a defensible cohort definition and treatment comparison
- clear outcome definition and index horizon
- explicit handling of prevalent-user vs new-user status
- temporal verification of baseline covariates and ECG representations

## Final conclusion

The current `statin_before` variable supports only a coarse description of recent prescription exposure, not a defensible causal time zero or a valid treatment-specific baseline ECG design. The statin-specific causal design is therefore NOT READY.

Additional data required to move toward readiness would include: exact medication start/administration timestamps, a verified medication administration source, a defensible treatment-time assignment rule, and a treatment-specific ECG selection rule known to be pre-treatment.
