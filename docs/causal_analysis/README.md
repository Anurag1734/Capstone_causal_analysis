# Causal analysis foundation

This folder contains the causal-analysis design artifacts for the ECG/MI
project. The current treatment-specific design proposal is
[PRESCRIPTION_WINDOW_CAUSAL_DESIGN.md](./PRESCRIPTION_WINDOW_CAUSAL_DESIGN.md).
It begins DAG design for the strongest candidate exposure, `statin_before`,
while explicitly blocking effect estimation until exposure-window provenance,
outcome ordering, and covariate timing are resolved.

The final within-admission temporal-gap gate is documented in
[STATIN_TEMPORAL_GAP_AUDIT.md](./STATIN_TEMPORAL_GAP_AUDIT.md). It reports that
the current master does not contain the admission-anchor fields required to
compare `index_mi_time` with `anchor_time`; the within-admission design is not
viable with the available master data.

The [cross-admission design audit](./STATIN_CROSS_ADMISSION_DESIGN_AUDIT.md)
finds the longitudinal concept clearer in principle, but not viable with the
current master because it lacks admission/discharge chronology and a complete
admission outcome roster.

The older Phase 0 documents and Phase 1–7 audit artifacts remain preserved as
historical records. Where their earlier status statements conflict with the
current prescription-window design, the new design report is the current
working decision; it does not overwrite the historical audit evidence.

## Scope

This folder does not redo the completed feature-engineering work or estimate
ATE/CATE. The current report contains one provisional treatment-specific DAG;
it does not claim a final, validated DAG and does not run causal discovery or
effect estimation.

It is focused on:

- confirming the available evidence in the current SCM repository
- preserving the historical audit record
- documenting the treatment-specific estimand design boundary
- identifying the remaining decisions required before DAG construction
- establishing a clean causal-analysis starting point

## Canonical evidence currently available

The current repository contains the following relevant artifacts:

- `master/train.parquet`
- `master/validation.parquet`
- `master/test.parquet`
- `causal_audit/README.md`
- `causal_audit/CURRENT_STATUS.md`
- `causal_audit/PHASE_INDEX.md`
- `causal_audit/phase4/phase4_discovery_ready_dataset_report.md`
- `causal_audit/phase7/phase7_causal_discovery_report.md`
- `docs/Phase F — Master Dataset.md`
- `docs/longitudinal_mi_cohort_extraction.md`

On the current workspace, the master parquet files are verified to have 184 columns and the documented schema, including:

- identifiers: `study_id`, `SubjectID`, `hadm_id`
- labels: `Label_Troponin`, `is_MI`
- time: `ecg_time`, `index_mi_time`, `time_diff_hours`
- latent ECG: `z_ecg_1` ... `z_ecg_64`
- engineered ECG features: 95 columns
- comorbidities: `diabetes`, `hypertension`, `ckd`, `prior_mi`
- treatments: `statin_before`, `statin_during`, `statin_after`, `beta_blocker_before`, `beta_blocker_during`, `acei_before`, `acei_during`, `aspirin_before`, `aspirin_during`, `vasopressor_during`, `mech_vent_during`
- demographics: `anchor_age`, `sex_male`

These are treated as the current dataset facts for this causal-analysis foundation.

## Important provenance note

The project documentation references a `master_dataset_construction.md` and a source script such as `src/features/build_master_dataset.py`, but those artifacts were not present in the current workspace at the time of this review. This is a provenance gap and should be treated as unresolved rather than silently patched over.

This means the causal-analysis foundation must rely on the current master parquet files and the preserved historical audit documents, while explicitly documenting that the upstream construction script provenance remains incomplete.

## Files in this folder

- [PRESCRIPTION_WINDOW_CAUSAL_DESIGN.md](./PRESCRIPTION_WINDOW_CAUSAL_DESIGN.md) — current prescription-window estimand, treatment ranking, statin-specific DAG, candidate adjustment set, assumptions, and blockers
- [STATIN_TEMPORAL_GAP_AUDIT.md](./STATIN_TEMPORAL_GAP_AUDIT.md) — final within-admission temporal gap check and design-gate verdict
- [STATIN_CROSS_ADMISSION_DESIGN_AUDIT.md](./STATIN_CROSS_ADMISSION_DESIGN_AUDIT.md) — descriptive feasibility audit for the cross-admission fallback
- [READINESS.md](./READINESS.md) — overall readiness summary and blockers
- [ESTIMANDS.md](./ESTIMANDS.md) — Phase 0 estimand specifications
- [VARIABLE_ROLES.md](./VARIABLE_ROLES.md) — variable-role classifications and eligibility notes
- [TREATMENT_READINESS.md](./TREATMENT_READINESS.md) — treatment-by-treatment readiness table
- [statin/](./statin) — treatment-specific temporal design audit for `statin_before`
- [treatment_timing/](./treatment_timing) — cross-treatment medication temporal audit across the four primary candidate treatments

## Historical conclusions preserved in older Phase 0 documents

The following statements remain preserved as dated historical conclusions;
they do not supersede the current prescription-window design report:

- admission-level is the primary causal unit
- repeated ECGs and repeated admissions are not independent causal units
- an exact medication time zero is not represented by the prescription-window flag
- a final causal index ECG is not selected
- `is_MI` is the candidate endpoint but its occurrence after the prescription window is not established
- `z_ecg` causal role is unresolved unless provenance and temporal eligibility are established

## Current gate status

The current status for causal analysis is:

- Prescription-window design: drafted for `statin_before`; not approved for estimation
- Phase 1-7 historical audit: preserved and not rewritten
- Effect estimation: blocked pending design review and temporal/provenance resolution
- Statin-specific candidate DAG: drafted in the prescription-window design report
- ECG-derived and `z_ecg` variables: quarantined from adjustment
