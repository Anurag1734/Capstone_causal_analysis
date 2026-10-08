# Treatment readiness review

## Objective

This file documents the current readiness of each candidate treatment for treatment-specific causal modeling. The working standard is strict: a treatment must have a defensible exposure definition, a valid causal time zero, a valid baseline ECG, and a justified outcome definition before it becomes eligible for DAG construction.

## Current treatment readiness table

| Treatment | Definition verified | Time zero | Baseline ECG | Outcome | Positivity | DAG ready? |
|---|---|---|---|---|---|---|
| statin_before | Yes in schema; no exact medication timestamp available | Unresolved | Unresolved | Unresolved | Marginal prevalence known; conditional overlap unknown | No |
| aspirin_before | Yes in schema; no exact medication timestamp available | Unresolved | Unresolved | Unresolved | Marginal prevalence known; conditional overlap unknown | No |
| beta_blocker_before | Yes in schema; no exact medication timestamp available | Unresolved | Unresolved | Unresolved | Marginal prevalence known; conditional overlap unknown | No |
| acei_before | Yes in schema; no exact medication timestamp available | Unresolved | Unresolved | Unresolved | Marginal prevalence known; conditional overlap unknown | No |

## Treatment-specific notes

### statin_before

- The master dataset contains a pre-admission statin indicator.
- This is a window-coded treatment flag rather than a verified timestamped exposure record.
- The project documentation states that `*_before` captures recent inpatient prescription patterns, not necessarily true outpatient baseline medication use.
- Because exact timing is unavailable, the exposure cannot be treated as a validated baseline treatment assignment without further evidence.

### aspirin_before

- The master dataset contains a pre-admission aspirin indicator.
- The same timing caveat applies as for other `*_before` variables.
- Aspirin could plausibly be a candidate treatment, but the current data do not establish whether the treatment was assigned before a valid treatment-specific ECG or before the relevant MI time window.

### beta_blocker_before

- `beta_blocker_before` is available in the schema.
- However, the exact administration timing is not available in the current master dataset.
- Low prevalence elevates the risk of poor conditional positivity in a finalized eligible cohort.

### acei_before

- `acei_before` is available in the schema.
- Exact timing and valid baseline ordering remain unresolved.
- Low prevalence and small treatment counts create a strong positivity risk when conditioning on baseline covariates.

## Treatments that should remain out of the primary baseline treatment set

- `vasopressor_during` — likely acute/severity downstream variable
- `mech_vent_during` — likely acute/severity downstream variable
- `statin_after` — post-discharge exposure, not a baseline cause of the current MI outcome
- `*_during` variables generally — not valid baseline exposures without a strong causal-time argument

## Practical decision rule

A treatment is considered ready for treatment-specific DAG work only if all of the following are documented:

- exposure definition is clear and clinically interpretable
- timing of exposure is known or can be justified from source data
- ECG selected for analysis is definitely measured before exposure time
- the candidate outcome is defined and temporally bounded
- the cohort is clearly defined and eligible for the question
- overlap/positivity is acceptable in the finalized cohort

## Current conclusion

None of the four primary candidate treatments is currently ready for DAG construction, discovery, or effect estimation. The historical causal audit is consistent with this conclusion: the causal-analysis foundation remains blocked by unresolved exposure timing, treatment-specific ECG timing, and outcome definition.
