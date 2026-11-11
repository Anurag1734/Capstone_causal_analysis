# Phase 16 missing treatment and selection assessment

## Distinct selection mechanisms

| Stage | N | Interpretation |
|---|---:|---|
| Eligible prior-MI index admissions alive at discharge | 7,545 | One selected index admission per patient |
| Known `statin_during` | 4,656 | 2,986 exposed; 1,670 controls |
| Missing `statin_during` | 2,889 | Unknown; not imputed or recovered |
| Exposed with filtered exact-ID EMAR link | 1,505 | Linked administration-like statin records |
| Exposed without such EMAR link | 1,481 | Not proof of no administration |
| Exposed with valid first in-admission timestamp | 1,500 | First recorded administration falls in index interval |
| Complete follow-up (all treatment statuses) | 4,985 | Includes outcome-known treatment-missing patients |
| Incomplete/uncertain follow-up | 2,560 | Not outcome-negative |
| Phase 11 complete-case population | 3,230 | 499 held-out test rows; saved estimates use this sample |

The missing-treatment population (2,889) is not the EMAR-unmatched population (1,481 exposed patients), and neither is the same as incomplete follow-up (2,560 overall; 1,426 among known-treatment patients). EMAR linkage was attempted only for admissions already marked exposed; no link cannot be used to reconstruct a negative treatment value. The archive-backed Phase 14 extraction does not retain declined/not-administered rows or an inclusion/exclusion audit for unmatched patients.

## Selection implications

The Phase 11 complete-case set is 3,230 of 4,656 known-treatment admissions with baseline features. Follow-up completion is 2,014/2,986 (67.45%) among treated and 1,216/1,670 (72.81%) among controls, a 5.37 percentage-point difference. Differential outcome ascertainment/retention is plausible. Another 2,889 eligible records lack treatment and the corresponding processed baseline feature row. Of these, 2,338 appear in the existing split files and 551 do not; retained artifacts do not provide a patient-level reason for the latter.

Selection into processed ECG/master data may depend on care pathways, utilization, clinical state, or data availability; no retained per-record exclusion audit resolves this. Restricting to prior-MI survivors and observed treatment/features can further condition on selection variables. IPCW for incomplete follow-up addresses neither missing treatment classification nor ECG/master-feature selection, and only works under its own conditional independent-censoring assumptions.

**Decision:** do not impute or infer treatment for missing or EMAR-unmatched records. Report all populations separately. The held-out Phase 11 sample and Phase 12 robustness analyses remain exploratory only.
