# Phase 8 Longitudinal and Medication Validation

**Validation date:** 2026-10-22  
**Scope:** file availability, schema/integrity checks, medication-artifact reuse, and
statin-cohort prerequisite assessment. No PC, GES, FCI, ATE, CATE, or final cohort
construction was run.

## 1. Files actually found

The archive `longitudinal.rar` contains the following members. It was extracted
non-destructively to `longitudinal_extracted/longitudinal/` for validation:

| File | Format | Size (bytes) | Rows | Columns | Role |
|---|---|---:|---:|---:|---|
| `admissions_chronology.parquet` | Parquet | 30,335,545 | 431,231 | 20 | admission chronology and derived neighbors |
| `diagnoses_all.parquet` | Parquet | 29,405,308 | 4,756,326 | 8 | diagnosis-level history |
| `diagnoses_mi_codes.parquet` | Parquet | 858,867 | 26,824 | 8 | MI-coded diagnosis rows |
| `d_labitems.parquet` | Parquet | 25,617 | 1,622 | 4 | laboratory dictionary |
| `lab_coverage_catalogue.parquet` | Parquet | 12,881 | 26 | 17 | candidate laboratory coverage |
| `mi_admissions.parquet` | Parquet | 615,770 | 25,755 | 8 | distinct MI-coded admissions |
| `observation_end.parquet` | Parquet | 6,655,085 | 180,733 | 7 | patient-level death/follow-up summary |
| `omr_coverage_catalogue.parquet` | Parquet | 5,344 | 13 | 7 | OMR coverage summary |
| `patients_demographics.parquet` | Parquet | 2,433,392 | 299,712 | 6 | demographics and date of death |
| `vitals_coverage_catalogue.parquet` | Parquet | 6,884 | 14 | 9 | vital-sign coverage summary |

The archive's `phase1_stats.json` and `phase2_stats.json` were also present. The
previous claim that these machine-readable longitudinal outputs were unavailable
was therefore an artifact-availability finding from the earlier workspace, not a
finding about the archive contents.

### Machine-readable schemas

- `admissions_chronology`: `subject_id`, `hadm_id`, `admittime`, `dischtime`,
  `deathtime`, `edregtime`, `edouttime`, `admission_type`,
  `admission_location`, `discharge_location`, `insurance`, `race`,
  `hospital_expire_flag`, `admission_seq`, `previous_hadm_id`,
  `previous_dischtime`, `next_hadm_id`, `next_admittime`, `anchor_time`,
  `total_admissions`.
- `diagnoses_all` and `diagnoses_mi_codes`: `subject_id`, `hadm_id`,
  `icd_code`, `icd_version`, `seq_num`, `admittime`, `dischtime`,
  `is_mi_code`.
- `mi_admissions`: `subject_id`, `hadm_id`, `mi_icd_codes`, `min_seq_num`,
  `admittime`, `mi_admission_seq`, `total_mi_admissions`,
  `is_first_mi_admission`.
- `patients_demographics`: `subject_id`, `gender`, `anchor_age`,
  `anchor_year`, `anchor_year_group`, `dod`.
- `observation_end`: `subject_id`, `last_discharge`, `last_admittime`,
  `in_hospital_deathtime`, `dod`, `is_dead`, `observation_end`.
- `d_labitems`: `itemid`, `label`, `fluid`, `category`.
- `lab_coverage_catalogue`: `itemid`, `lab_name`, `fluid`, `category`,
  `total_measurements`, `unique_patients`, `unique_admissions`,
  `cohort_patients`, `cohort_measurements`, `earliest_measurement`,
  `latest_measurement`, `mean_value`, `median_value`, `std_value`,
  `min_value`, `max_value`, `common_unit`.
- `omr_coverage_catalogue`: `result_name`, `total_records`,
  `unique_patients`, `cohort_patients`, `cohort_records`, `earliest`,
  `latest`.
- `vitals_coverage_catalogue`: `itemid`, `vital_name`, `total_records`,
  `unique_patients`, `unique_admissions`, `cohort_admissions`,
  `cohort_records`, `mean_value`, `median_value`.

## 2. Structural and temporal validation

### Admission chronology

- `subject_id` and `hadm_id` are complete; there are 180,733 unique patients and
  431,231 unique admissions.
- Duplicate `(subject_id, hadm_id)` rows: **0**.
- Invalid `admittime`/`dischtime` parses: **0** each.
- `dischtime < admittime`: **139** admissions.
- `previous_dischtime > admittime`: **59**.
- `dischtime > next_admittime`: **59**.
- `admission_seq` is present and consistent with the stored within-patient order.
- The 139 invalid admission intervals and 59 neighbor-order anomalies must be
  excluded or explicitly adjudicated before final time-zero locking.

### Diagnoses and MI admissions

- `diagnoses_all.parquet` has 4,756,326 diagnosis-level rows. Repeated
  `(subject_id, hadm_id)` keys are expected because this is not an admission-level
  table; 4,325,474 repeated-key rows were observed.
- `diagnoses_mi_codes.parquet` has 26,824 MI diagnosis rows across 25,755 unique
  admissions and 14,905 unique patients. Its 1,069 repeated admission keys are
  multiple MI diagnosis codes in the same admission, not duplicate MI admissions.
- Every MI admission key joins to `admissions_chronology.parquet` (25,755/25,755).
- MI admission dates parse successfully; 16 MI diagnosis rows have
  `dischtime < admittime`, inherited from the source chronology.
- The table supports a first distinct later MI-coded admission, but it does not by
  itself prove incident clinical MI or distinguish recurrent disease from a
  coding event.

### Demographics and follow-up

- `patients_demographics.parquet` has 299,712 unique, non-null `subject_id` values.
  All 180,733 admission patients join to it.
- `observation_end.parquet` has one row per 180,733 admission patient, with no
  duplicate or missing patient key. All admission patients join to it.
- `dod` is present for 27,980 patients; in-hospital death time is present for
  8,592; `is_dead` agrees with the presence of either death field (0 mismatches).
- `observation_end` is missing for 152,753 censored/alive patients only in the
  sense that the source value is a date derived from last known follow-up; it is
  not a null field in the Parquet table.
- `observation_end < last_discharge` occurs for 8,383 patients and
  `observation_end < first admission` for 327. These cases require source-level
  review or conservative exclusion before survival follow-up is finalized.
- `anchor_age` is a de-identification anchor age, not automatically age at every
  admission; age-at-admission must be derived if age is used.

## 3. Medication artifacts reused

Existing outputs were read without rerunning the expensive source extraction:

| File | Rows | Status |
|---|---:|---|
| `medication_prescription_orders.parquet` | 881,020 | Valid non-empty statin/aspirin/beta-blocker/ACE-inhibitor order output |
| `medication_administrations.parquet` | 1,515,317 | Valid non-empty retained EMAR administration output |
| `ecg_medication_timing.parquet` | 0 | Schema present, no linked rows |

The existing audit reports 312,471 statin EMAR administrations and 881,020 target
prescription orders overall. The medication outputs preserve the distinction
between orders and recorded administrations. Neither output establishes
outpatient use, adherence, initiation, or causal assignment.

Additional validation of the saved outputs found:

- All 881,020 retained prescription rows join to an admissions key.
- 160 prescription `starttime` and 346 `stoptime` values are null.
- 60,703 prescription rows have `stoptime < starttime`.
- 106,460 prescription starts fall outside the linked admission interval.
- 1,437,479 of 1,515,317 retained EMAR rows join to an admissions key; the
  remainder retain invalid or unavailable admission identifiers from the source.
- EMAR `charttime` and `storetime` are non-null in the retained output.
- 17,470 retained EMAR timestamps fall outside their linked admission interval.
- `emar_detail.csv` is still absent, so dose-detail fields cannot be claimed.
- No ECG/master dataset containing `study_id`, patient ID, `hadm_id`, and
  `ecg_time` was found. The zero-row ECG linkage Parquet is therefore not evidence
  of successful ECG-medication linkage.

## 4. Statin-design prerequisite diagnostics

Using only admission chronology and MI-admission keys, a diagnostic (not final
cohort) first non-MI admission rule gives:

- 174,055 baseline admissions for 174,055 patients.
- 4,857 have a later first MI-coded admission.

This verifies that a baseline admission and subsequent coded outcome can be
constructed without selecting on a future MI. It does not establish treatment
validity. Among these diagnostic baseline admissions:

- 43,832 admissions have a statin prescription order; 9,396 orders start before
  admission and 44,744 start at/after admission.
- 18,224 admissions have a statin EMAR administration; 450 retained EMAR events
  are before admission and 80,452 are within the admission window.

These counts are deliberately not used as exposure assignments. Orders starting
after admission and inpatient administrations are compatible with acute-care
treatment rather than a pre-exposure statin strategy. A prior-use window cannot be
validated from the current outputs because outpatient medication history and
adherence are not observed.

## 5. Validation decision

**Passed:** archive availability, Parquet readability, core identifiers, MI-to-
admission joins, patient-to-demographics joins, patient-to-follow-up joins, and
non-empty prescription/EMAR extraction outputs.

**Failed or incomplete:** admission interval integrity, some observation-end
ordering, prescription timestamp integrity, EMAR admission-time containment,
ECG linkage, dose-detail availability, outpatient prior-use ascertainment, and a
defensible statin initiation/assignment boundary.

Because the exposure boundary and prior-use definition are not validated, a
reproducible statin cohort would currently encode an unsupported proxy. No cohort
construction script or final cohort was created.
