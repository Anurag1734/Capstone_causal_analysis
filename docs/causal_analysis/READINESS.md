# Causal-analysis readiness report

## Purpose

This report summarizes what is already available for treatment-specific causal analysis in the current SCM repository and which design decisions remain required before DAG construction.

## Evidence reviewed

- `master/train.parquet`, `master/validation.parquet`, and `master/test.parquet` are present and have the expected 184-column schema.
- `docs/Phase F — Master Dataset.md` documents the current master dataset and variable inventory.
- `causal_audit/CURRENT_STATUS.md` captures the current understanding after the historical Phase 1-7 audit.
- `causal_audit/phase4/phase4_discovery_ready_dataset_report.md` documents the discovery-ready dataset audit and its blockers.
- `causal_audit/phase7/phase7_causal_discovery_report.md` explicitly states that all treatment-specific discovery questions remain blocked.

## Current readiness snapshot

| Treatment | Definition verified | Time zero | Baseline ECG | Outcome | Positivity | DAG ready? |
|---|---|---|---|---|---|---|
| statin_before | Partially: window-coded flag exists in master dataset, but exact medication timing is not available | Unresolved | Unresolved | Unresolved | Unclear; marginal exposure known but conditional positivity unknown | No |
| aspirin_before | Partially: window-coded flag exists in master dataset, but exact medication timing is not available | Unresolved | Unresolved | Unresolved | Unclear; marginal exposure known but conditional positivity unknown | No |
| beta_blocker_before | Partially: window-coded flag exists in master dataset, but exact medication timing is not available | Unresolved | Unresolved | Unresolved | Unclear; marginal exposure known but conditional positivity unknown | No |
| acei_before | Partially: window-coded flag exists in master dataset, but exact medication timing is not available | Unresolved | Unresolved | Unresolved | Unclear; marginal exposure known but conditional positivity unknown | No |

## What is already available

- A current master dataset exists with the documented schema.
- The primary causal unit is admission-level.
- The data include the required treatment exposure flags and baseline clinical variables.
- A frozen historical audit says repeated ECGs and repeated admissions are not independent causal units.
- The project recognizes the distinction between pre-admission treatment flags and exact treatment timing.
- The data define `Label_Troponin` as a temporal outcome label but do not itself establish a final causal outcome definition.
- The historical audit keeps `z_ecg` as a quarantined latent representation pending provenance and timing review.

## Remaining design decisions required before DAG construction

1. Treatment-specific time zero
   - For each candidate treatment, determine whether an exact or defensible exposure timestamp exists.
   - If it cannot be established, document the limitation and decide whether an observational estimand remains valid.

2. Defensible index ECG selection rule
   - Determine whether the ECG used in the analysis is measured before the treatment-specific time zero.
   - If no valid rule can be established, document the blocker explicitly.

3. Outcome definition and horizon
   - Define the final MI outcome and the relevant follow-up window.
   - Confirm whether the analysis targets admission-level MI diagnosis, a troponin-defined event, or another explicitly justified endpoint.

4. Temporal eligibility for ECG features and `z_ecg`
   - Confirm whether the selected ECG and latent representation are measured before treatment exposure.
   - Confirm provenance of the VAE pipeline and training split membership.

5. Baseline covariate eligibility
   - Determine which variables are baseline confounders, prognostic variables, mediators, colliders, or post-treatment variables for each treatment.
   - Keep `z_ecg` out of the adjustment set unless supported by timing and provenance.

6. Treatment-specific estimand specification
   - Define target population, exposure condition, control condition, time zero, outcome, and horizon for each candidate treatment.

7. Positivity and overlap checks
   - Assess whether clinically meaningful treatment-control overlap exists after filtering to a valid eligible cohort.

8. Dependence handling
   - Use `SubjectID` and `hadm_id` appropriately in the design, not as ordinary causal covariates.

## Decision gate status

The historical Phase 7 gate remains correct in the current workspace: all primary treatment questions are blocked until the above design variables are resolved.

No DAG construction, PC/GES/FCI run, or effect estimation should be started from this current foundation state.

## Bottom line

The repository has a strong data foundation and a preserved audit trail, but the causal-analysis foundation is not yet ready for treatment-specific DAG construction.
