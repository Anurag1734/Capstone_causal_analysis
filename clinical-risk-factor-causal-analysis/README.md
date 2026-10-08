# Clinical risk-factor causal analysis for MI

**Separate feasibility branch.** This folder is outside the treatment-causal
project. It contains no copied datasets or pipelines and does not modify the
existing project, master data, or closed Phases 1–7.

## Purpose

Assess whether MIMIC-derived baseline clinical or physiological factors can
support a future causal analysis of subsequent MI. This is a discovery and
design-feasibility investigation only. It does not establish causal effects,
select a final exposure, construct a final DAG, or run estimation.

## Initial conclusion

The current master has complete admission-level demographics and four
historical comorbidity indicators, but no laboratory or vital measurements.
Historical documentation says extracted labs and vitals were dropped from the
master for less than 1% row coverage. Potential raw sources (`labevents`,
outpatient `omr`, ICU `chartevents`) are described in the source documentation
but are not present in the current workspace. The master also lacks admission
and discharge timestamps and is ECG-linked rather than a verified complete
admission roster.

Therefore the idea is **not yet feasible with the files currently available**.
The problem is **BOTH** a data-availability/temporal-resolution problem and a
causal-question/intervention-definition problem. Source tables could make a
better timed cohort possible, but a measured biomarker is not automatically a
well-defined causal intervention.

## Branch contents

- [data_inventory/clinical_variable_inventory.md](data_inventory/clinical_variable_inventory.md) — observed master variables and documented candidate clinical sources
- [temporal_audit/baseline_timing_audit.md](temporal_audit/baseline_timing_audit.md) — timestamp availability and ordering requirements
- [causal_design/candidate_estimands.md](causal_design/candidate_estimands.md) — candidate question formulations, not a selected estimand
- [leakage_audit/outcome_leakage_audit.md](leakage_audit/outcome_leakage_audit.md) — troponin, acute measurements, and post-outcome leakage risks
- [ECG_relationship/ecg_z_ecg_role_analysis.md](ECG_relationship/ecg_z_ecg_role_analysis.md) — hypotheses and quarantine rules for ECG representations
- [STATUS.md](STATUS.md) — gate status and minimal next work

## Evidence boundary

The existing project is referenced, not copied:

- Master schema and source coverage: `../capstone2/docs/Phase F — Master Dataset.md`
- MIMIC source-table documentation: `../capstone2/docs/raw_data_analysis.md`
- Longitudinal extraction concepts: `../capstone2/docs/longitudinal_mi_cohort_extraction.md`
- Existing ECG temporal/provenance audit: `../capstone2/docs/causal_analysis/statin/ECG_SELECTION_AUDIT.md`

Those documents provide prior documentation, not raw data or proof that a
source table is accessible in this branch. No conclusion here reopens or
changes the separate medication-causal analysis.

## Scientific guardrails

- Define measurement before time zero and before follow-up; do not infer it
  from column names or from the MI cohort label.
- Do not use troponin as a candidate exposure.
- Separate stable baseline physiology from acute illness measurements.
- Keep all ECG and `z_ecg` causal roles unresolved and quarantined from
  adjustment until a separate temporal design supports their use.
- Do not equate predictive association with a causal effect.
- Do not proceed to final DAGs, causal discovery, or effect estimation until
  the data and intervention definition pass feasibility review.
