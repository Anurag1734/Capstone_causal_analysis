# Phase 8 - Identification Assessment

## Bottom line

A causal statin effect is **not identifiable from the current design and workspace evidence**. The graph can expose required assumptions, but drawing it does not establish exchangeability or a valid treatment time.

## Threat assessment

| Threat | Assessment | Current status |
|---|---|---|
| Confounding by indication | Statin prescribing likely reflects dyslipidemia, established CVD, prior MI, HF, clinician judgment, and risk burden. The listed fields are incomplete proxies. | Likely limitation preventing causal identification |
| Baseline cardiovascular risk | `prior_mi`, diabetes, hypertension, CKD, age, and sex are candidate controls, but completeness and cutoff are not verified. | Potentially addressable after targeted validation; not sufficient alone |
| Prior statin exposure | `statin_before` mixes continuation, recent order, and possible initiation. Prior use cannot be reconstructed as a clean new-user history from the current master. | Unresolved |
| Healthy-user/access effects | Medication documentation, adherence, follow-up, and healthcare contact are not equivalent to treatment receipt and may affect outcome observation. | Unresolved; likely residual confounding |
| Severity/presentation | Acute illness can influence prescriptions and subsequent MI risk. Baseline timing of candidate severity fields is not fixed. | Potentially addressable only with source-level time validation |
| Prescription vs administration | Orders are not administrations; EMAR timestamps are not in the master and were not linked to ECG in the audit. | Unresolved and central blocker |
| Cohort selection | ECG-linked master is not a verified complete admission census. Selecting a future admission or future MI would condition on future care/outcome. | Likely limitation; first-baseline design required |
| Repeated admissions | Multiple admissions per patient create dependence and treatment-history carryover. | Addressable in principle with one baseline per patient or a repeated-risk-set design |
| Informative censoring | Death and observation end can prevent a subsequent MI from being observed and may depend on exposure/risk. | Requires competing-risk and censoring specification; local outputs absent |
| Positivity | Overall `statin_before` prevalence is not conditional overlap in the eligible target population. | Cannot assess until cohort and covariates are finalized |
| Consistency | "A statin prescription" has multiple drugs, doses, durations, and adherence states; intervention version is not well defined. | Unresolved |
| Reverse causation | Recent prescribing may reflect evolving symptoms or an incipient event, especially near admission. | Likely limitation for the current window |
| Immortal-time bias | Assigning treatment over a window while starting follow-up earlier can create immortal time; future eligibility can also create it. | Addressable only by explicit window end and follow-up origin |
| Missing/misaligned covariates | ECG timing, treatment timing, clinical history, and outpatient information are incomplete or unavailable in current workspace artifacts. | Central blocker |

## Time-zero assessment

For a window exposure, the exposure assessment period has a beginning and end. If follow-up starts before the window closes, treated patients must survive and remain observable long enough to be classified, producing immortal-time risk. If follow-up starts at baseline discharge, the window and follow-up are sequential, but the exposure is still a prevalent/recent prescription proxy and not a point intervention. Using the admission anchor as treatment time would incorrectly equate hospital entry with treatment assignment. Using `index_mi_time` would be outcome-dependent and circular.

The least problematic future arrangement is: define eligibility before looking forward; define the prescription strategy in a prespecified window ending at a known baseline boundary; start follow-up after that boundary, preferably baseline discharge for the cross-admission outcome; and exclude the baseline MI admission. This arrangement is only a design template until the source joins are executable.

## Candidate adjustment sets

No definitive adjustment set is approved.

If a future, validated graph defines a prescription-strategy total effect and confirms all variables are pre-exposure, a **candidate measured set** could include:

`{anchor_age, sex_male, diabetes, hypertension, ckd, prior_mi, validated baseline cardiovascular history, validated pre-exposure clinical state}`.

This set is not sufficient on the current evidence because important common causes remain unmeasured. ECG features and `z_ecg` are excluded until treatment-relative timing and provenance are proven. `statin_during`, `statin_after`, acute support variables, future admissions, and outcome timing metadata are excluded as post-origin, mediator, collider, or outcome-defined variables.

Under an alternative graph in which validated pre-exposure ECG state is a genuine common cause of prescription and later MI, a pre-exposure ECG block could be added. That is a sensitivity/design alternative, not a current recommendation. Predictive selection, stepwise regression, and feature importance cannot choose the causal set.

## Identification verdict by candidate exposure

- **Recent prescription indicator:** descriptive/associational contrast only; causal interpretation not identified.
- **In-hospital administration:** potentially reconstructable, but not a baseline prevention question and likely severely confounded by acute indication.
- **New-user initiation:** scientifically preferable, but not supported until prior use, initiation, eligibility, and administration/assignment time are reconstructed.
- **Baseline prescription strategy:** potentially target-trial-like after source validation; currently not identified.

## Minimum evidence needed before estimation

1. Recover or regenerate machine-readable admission chronology, diagnoses/MI admissions, death, and observation-end tables from the documented sources.
2. Reconstruct the exact prescription window and prior statin history independently of future MI.
3. Decide whether the intervention is a prescription strategy or actual administration; do not interchange them.
4. Define the first eligible non-MI baseline admission without future outcome conditioning.
5. Validate outcome completeness outside the ECG-linked master and specify the MI horizon.
6. Quantify conditional treatment overlap and missingness after the cohort and covariates are fixed.
7. Obtain clinical review of the DAG and treatment definition before any effect estimate.

Until these conditions are met, stop at descriptive or explicitly associational analysis.
