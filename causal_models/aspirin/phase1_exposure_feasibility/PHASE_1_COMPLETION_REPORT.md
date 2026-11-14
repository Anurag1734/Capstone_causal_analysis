# Phase 1 completion report — aspirin exposure and data feasibility

## Status

**Completed as an assessment only.** No treatment-effect estimation, causal forest, propensity weighting, SCM, DAG, or causal-effect claim was produced.

## Work completed

- Audited the two present master indicators (`aspirin_before`, `aspirin_during`) and confirmed `aspirin_after` is absent.
- Quantified indicator distributions at ECG-row, admission, and eligible prior-MI index-admission levels.
- Reused the existing 12-month longitudinal cohort and outcome artifacts without changing them or selecting on statin treatment.
- Linked aspirin-name/product-detail eMAR rows to the previous-MI index admissions, separated exact `Administered` events from order/status rows, validated timestamps, and classified each first administration relative to the index admission.
- Documented candidate aspirin-specific baseline confounders, likely post-treatment variables, data limitations, and the conditional next-step decision.
- Added focused validation tests for binary distributions, absent variables, inconsistent admission indicators, the source-audit aggregate, and generated artifact counts.

## Key counts and decision

- Eligible previous-MI index admissions: 7,545.
- Aspirin exposure proxy observed: 4,656/7,545; `aspirin_before=1`: 779; missing: 2,889.
- In-hospital aspirin indicator observed: 4,656/7,545; positive: 2,979.
- Aspirin eMAR: 2509 admissions with valid documented administration; first events before/during/after index: 268/2241/0.
- Linked eMAR rows: 12903; invalid administration timestamps: 0; duplicate event keys: 0.
- Acute-coded subsequent-MI candidates: 555; broad recurrent-MI-coded endpoint: 1,833; incomplete follow-up (broad endpoint): 2,560.
- **Decision B:** feasible to continue aspirin study design work after resolving exposure timing/linkage, clinical endpoint validation, and aspirin-specific confounding/contraindication information.

## Required outputs

- `ASPIRIN_EXPOSURE_AUDIT.md`
- `ASPIRIN_DATA_FEASIBILITY_REPORT.md`
- `ASPIRIN_COHORT_AVAILABILITY.csv`
- `ASPIRIN_EXPOSURE_SUMMARY.csv`
- `ASPIRIN_OUTCOME_AVAILABILITY.csv`
- `ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json`
- `scan_aspirin_source_timestamps.py`
- `analyze_aspirin_phase1.py`
- `test_aspirin_phase1.py`

All files are confined to `causal_models/aspirin/phase1_exposure_feasibility/`; the statin branch was not modified.
