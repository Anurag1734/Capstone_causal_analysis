# Variable-role inventory and eligibility notes

## Purpose

This document records the current working classification of the candidate variables in the master dataset, with a strong emphasis on what remains unresolved for treatment-specific causal analysis. This is not a final DAG.

## Variable groups

### Identifiers

- `study_id` — administrative identifier; not a causal variable
- `SubjectID` — patient-level identifier used for dependence handling; not a causal covariate
- `hadm_id` — admission identifier used for clustering and repeated-admission logic; not a causal covariate

### Outcome and time variables

- `Label_Troponin` — cohort label; not a standalone causal node
- `is_MI` — candidate MI outcome indicator; causal outcome definition and horizon remain unresolved
- `index_mi_time` — event timing variable; not a baseline covariate
- `time_diff_hours` — not a universal MI-relative clock; for controls uses a fallback anchor and is not a general causal variable

### ECG latent block

- `z_ecg_1` ... `z_ecg_64` — 64-dimensional VAE embedding block
- Current status: temporally unresolved and causally unvalidated
- Do not automatically classify as a confounder
- Do not automatically place in the adjustment set
- Keep as a quarantined representation until provenance and timing are established

### Engineered ECG features

- 95 engineered features
- Current status: available at the selected ECG time, but not causally validated as pre-treatment unless the index ECG and time-zero rule are established
- These features should be treated as a candidate representation layer rather than as proven baseline variables

### Baseline clinical variables

- `anchor_age` — likely baseline and admission-level, but must be checked against causal timing and eligibility for each treatment
- `sex_male` — likely baseline and admission-level, but must be checked against causal timing and eligibility for each treatment
- `diabetes` — prior-admission comorbidity; a plausible baseline covariate, but its temporal and causal role must be verified per treatment
- `hypertension` — prior-admission comorbidity; candidate baseline variable, not automatically valid adjustment variable
- `ckd` — prior-admission comorbidity; candidate baseline variable, not automatically valid adjustment variable
- `prior_mi` — prior-admission comorbidity; candidate baseline variable, not automatically valid adjustment variable

### Treatment variables

- `statin_before` — window-coded treatment indicator; not equivalent to exact treatment timing
- `statin_during` — acute/in-hospital treatment; likely post-treatment or severity-linked and not a baseline primary cause for the current MI outcome
- `statin_after` — post-discharge treatment; not a baseline cause of the current MI outcome
- `beta_blocker_before` — window-coded pre-admission indicator; requires exact timing review
- `beta_blocker_during` — acute treatment; not a baseline candidate without a strong time-order argument
- `acei_before` — window-coded pre-admission indicator; requires exact timing review
- `acei_during` — acute treatment; not a baseline candidate without a strong time-order argument
- `aspirin_before` — window-coded pre-admission indicator; requires exact timing review
- `aspirin_during` — acute treatment; not a baseline candidate without a strong time-order argument
- `vasopressor_during` — acute intervention; likely downstream severity variable
- `mech_vent_during` — acute intervention; likely downstream severity variable

## Variable-role classification summary

| Variable family | Current role | Causal status |
|---|---|---|
| Identifiers | administrative | not causal |
| Outcome/time fields | outcome metadata | unresolved for causal use |
| z_ecg block | latent representation | unresolved |
| engineered ECG features | candidate representation | unresolved |
| demographics | candidate baseline | conditionally eligible |
| comorbidities | candidate baseline | conditionally eligible |
| pre-admission treatments | candidate exposure | not yet valid without time-zero evidence |
| during-admission and post-discharge treatments | acute/post-treatment variables | not baseline primary candidates |

## Rules for the current working state

- Do not treat `z_ecg` as a confounder automatically.
- Do not place any variable in the adjustment set only because it predicts MI.
- Do not adjust for mediators when estimating a total effect.
- Do not infer treatment timing from the `*_before` name alone.
- Do not treat `*_during` or `*_after` variables as baseline causes without explicit temporal justification.
- Do not treat the historical Phase 6 constraints as final causal truth.

## Open decisions needed before DAG work

- treatment-specific causal time zero for each candidate treatment
- valid temporal ordering between treatment and selected ECG
- valid MI outcome definition and horizon
- eligible treatment cohort definition
- clinically justified baseline covariate set by treatment
- confirmed `z_ecg` provenance and temporal eligibility

## Final working conclusion

The master dataset is rich and useful, but the current variable-role inventory does not yet support a final treatment-specific DAG or adjustment set. The safe working stance is: keep everything quarantined, document unresolved temporal status, and proceed only once the treatment-specific causal design questions are answered.
