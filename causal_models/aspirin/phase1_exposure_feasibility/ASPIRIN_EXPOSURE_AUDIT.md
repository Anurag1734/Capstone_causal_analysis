# Aspirin exposure audit

## Scope and inputs

This assessment reuses the processed master splits, the existing prior-MI longitudinal cohort, saved acute-endpoint outputs, and the prior medication audit. It also reads the already extracted compressed eMAR source tables through the existing aspirin matcher; it does not extract the raw archive or estimate treatment effects. No statin artifact is changed.

## Candidate master variables

The processed master contains 375,930 ECG rows across 191,369 distinct admissions. `aspirin_before` and `aspirin_during` are present; `aspirin_after` is absent.

| Variable | Project definition/provenance | What the data establish | Missingness and distribution | Interpretation |
|---|---|---|---|---|
| `aspirin_before` | Project provenance documentation identifies `hosp/prescriptions.csv`, aspirin/aspirin-combination medication-name matching, and a recent pre-admission prescription window. The exact lookback duration, qualifying order fields, and matching implementation are not independently present in the processed workspace. | Binary master indicator at admission level; prescription/order proxy, not verified administration, initiation, adherence, or treatment time zero. | 30,621/375,930 ECG rows positive; 14,927/191,369 admissions positive; 0 ECG-row values missing. Eligible index cohort: 779 positive, 3,877 negative, 2,889 missing. | Can distinguish the recorded proxy's 1/0 values when present; cannot distinguish an actual aspirin user from a non-user with validated exposure semantics. Missing is not untreated. |
| `aspirin_during` | Phase F documentation describes this as in-hospital aspirin use. No aspirin-specific source mapping or event-time definition for this field was verified in the local processed outputs. | Binary per-admission indicator; it is not shown to mean a recorded EMAR administration. | 158,397/375,930 ECG rows positive; 68,655/191,369 admissions positive; 0 ECG-row values missing. Eligible index cohort: 2,979 positive, 1,677 negative, 2,889 missing. | Exposure timing relative to index admission and subsequent follow-up is not recoverable from the indicator. It can reflect acute care and must not be treated as baseline therapy. |
| `aspirin_after` | Not found in the processed master schema; project documentation lists no aspirin-after field. | No variable to inspect. | Absent, not an all-missing measured field. | No post-discharge prescription or adherence contrast is supported by this column. |

Full binary distributions by ECG row, master admission, and eligible index admission are in `ASPIRIN_EXPOSURE_SUMMARY.csv`.

## Timestamped medication evidence

The prior medication-source audit reports 316542 retained aspirin EMAR administration rows across its source-wide scan. The existing aspirin timestamp-recovery utility was run against the already extracted `hosp/*.csv.gz` source tables (no archive re-extraction); linked event-level rows were summarized and not exported. Among the 7,545 eligible index admissions, 2,540 have at least one aspirin-matched eMAR row; 2,509 have an `event_txt == 'Administered'` row with valid `charttime`. Of these first valid administrations, 268 occur before index admission, 2,241 during the index admission, and 0 after index discharge.

The cohort linkage yielded 12903 eMAR rows, of which 12057 had exact `event_txt == 'Administered'` and valid `charttime`; 0 qualifying administration rows had missing/invalid timestamps. Duplicate event-key rows: 0. Among all timestamped eMAR statuses, 307 rows predate the index admission and 2 occur after index discharge. Prescription `starttime`/POE `ordertime` are order timestamps, not administrations. Status counts and detailed quality metrics are in `ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json`; the aggregate source-wide count alone is not evidence for any individual admission.

## Exposure conclusion

There are two distinct binary proxies with materially different distributions: `aspirin_before` records 779 positive and 3,877 negative index admissions among 4,656 with observed values, while `aspirin_during` records 2,979 positive and 1,677 negative admissions among the same number with observed values. Among the 779 `aspirin_before=1` admissions, 21 have a linked valid in-hospital eMAR administration; no match does not establish non-use. These indicators are not interchangeable arms for a causal comparison and neither establishes aspirin assignment time; do not construct treatment effects or a DAG from them alone.
