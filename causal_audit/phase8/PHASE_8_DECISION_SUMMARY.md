# Phase 8 - Decision Summary

## What was inspected

The Phase 8 review inspected the existing variable-role, statin design, exposure provenance, treatment timing, readiness, estimand, temporal-gap, cross-admission, Phase 6 constraint, longitudinal foundation, and medication timestamp audit documents. It also machine-validated the longitudinal Parquet members in `longitudinal.rar` after extracting them to `longitudinal_extracted/longitudinal/`, and reused the existing medication Parquet outputs without rerunning extraction. Detailed results are in `PHASE_8_LONGITUDINAL_VALIDATION_REPORT.md`.

## What was created

- `PHASE_8_CAUSAL_QUESTION.md`
- `PHASE_8_VARIABLE_ROLES.md`
- `PHASE_8_CANDIDATE_STATIN_DAG.md`
- `PHASE_8_IDENTIFICATION_ASSESSMENT.md`
- This decision summary

All new outputs are under `causal_audit/phase8/`. Existing frozen files were not modified.

## Decisions

1. The preferred design hypothesis remains a first eligible non-MI baseline admission per patient, selected without requiring a future MI or future admission.
2. The preferred outcome hypothesis is the first distinct later MI-coded admission, not simply the next admission.
3. Follow-up should begin after the baseline exposure window and preferably after baseline discharge for the cross-admission design, with death treated as a competing event.
4. `statin_before` is retained as a recent prescription/order proxy only. It is not treated as statin initiation, administration, adherence, or a causal assignment time.
5. `statin_during`, `statin_after`, outcome timing fields, and ECG representations are excluded from the primary baseline adjustment set unless a separate temporal design validates them.
6. The DAG is explicitly provisional and not clinically validated.

## What remains unresolved

The longitudinal outputs are now confirmed available in the extracted archive and pass core key/join checks, but they contain 139 invalid admission intervals, 59 neighboring chronology reversals, and 8,383 observation-end values earlier than last discharge. The medication orders and EMAR outputs are non-empty and reusable, but contain timestamp containment problems; `emar_detail.csv` remains absent. The ECG input remains unavailable and `ecg_medication_timing.parquet` has zero rows, so ECG-medication linkage did not succeed.

Treatment initiation, prior use, adherence, a valid baseline ECG, incident MI ascertainment, complete observation time, censoring, positivity, and exchangeability remain unresolved. A first non-MI baseline and later MI-coded outcome are structurally constructible, but the available medication timestamps do not establish a defensible statin assignment time or prior-use window.

## Causal conclusion

A defensible **candidate research question** exists, but a defensible **identified causal effect** does not exist from the current design. The appropriate current output is a provisional DAG plus a transparent associational/descriptive design decision. Do not proceed to ATE/CATE estimation.

## Highest-priority next action

**Resolve the medication time-zero blocker:** adjudicate invalid order/administration timestamps, obtain or document the missing outpatient/prior-use evidence, and supply an ECG master only if ECG linkage remains part of the design. Then rerun a targeted treatment-history reconciliation before any cohort lock or effect estimation. The longitudinal tables themselves no longer constitute an availability blocker.

## Additional data genuinely required

The next action may use existing original MIMIC-IV sources if they are available in the data environment; downloading new datasets is not required by this Phase 8 review. If those sources cannot be recovered, the project lacks the evidence required for a causal statin question and should remain descriptive/associational.
