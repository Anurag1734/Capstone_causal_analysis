# Branch status

**Stage:** discovery / data feasibility  
**Decision:** not currently feasible with the files present  
**Problem classification:** BOTH dataset and causal-question problems  
**DAG / estimation:** not started

## Established facts

- Current master contains 375,930 ECG rows, 191,369 admissions, and 99,256
  patients.
- `anchor_age`, `sex_male`, `diabetes`, `hypertension`, `ckd`, and `prior_mi`
  are present with no missing values in the admission-collapsed master; age
  has 73 distinct observed values, sex has two, and each comorbidity flag has
  both binary values.
- No clinical laboratory or vital variables are columns in the master.
- Existing Phase F documentation says extracted lab and vital files had 738
  and 1,457 rows respectively, each below 1% row coverage, and were dropped.
- Source documentation describes MIMIC `labevents`, `omr`, `chartevents`,
  admissions, and diagnosis tables, but the raw tables/extracts were not found
  in the current project workspace.
- Admission/discharge timestamps and complete outcome ascertainment are
  required to define temporal order and follow-up; they are absent from the
  current master.

## Open blockers

1. Obtain authorized access to the relevant MIMIC source tables or a
   documented extraction with subject/admission keys, values, and actual
   measurement timestamps.
2. Verify item IDs, units, repeat-measurement rules, and candidate-specific
   coverage/variation in the intended baseline population.
3. Reconstruct complete admission chronology, diagnoses, baseline eligibility,
   and follow-up end/competing death without using future information at
   baseline.
4. Obtain clinical input on which factors have meaningful and well-defined
   intervention strategies and which time separation is defensible; do not
   invent a lag or follow-up horizon.
5. Check confounding by indication/testing and measurement selection.

## Smallest next analyses

1. Make admissions, diagnoses, `labevents`, `d_labitems`, `omr`, and if needed
   relevant charted-vitals tables available in this separate branch.
2. Produce a source-level catalog: item ID/name, units, distinct patients and
   admissions, non-null values, timestamps, setting, and distribution.
3. For each plausible candidate, quantify measurements strictly before a
   proposed baseline time and characterize how testing relates to admission
   and later MI ascertainment.
4. Construct a patient-level baseline-to-follow-up timeline and tabulate
   eligible patients, exposure support, subsequent MI events, death, and
   observation end. Do not estimate effects.
5. Review candidate intervention definitions and timing with domain experts
   before choosing a causal question or DAG.

The full rationale and variable-level details are in the sibling branch's
`data_inventory/`, `temporal_audit/`, `causal_design/`, `leakage_audit/`, and
`ECG_relationship/` reports.
