# Medication timestamp linkage audit

## Scope and reproducibility

This is a targeted audit of the local archives and existing workspace inputs.
It does not rebuild the ECG master, reconstruct longitudinal outcomes, estimate
causal effects, or treat prescriptions as administrations. Run it with:

`python run_medication_timestamp_audit.py --source-dir <source_dir> --output-dir <output_dir> [--ecg <ecg_file>]`

The source rows are processed in chunks of 250,000. Outputs are
deterministic for a fixed set of input files and paths.

## Source inventory

| Source | Status | Size (bytes) | Columns observed |
|---|---|---:|---|
| `emar.csv` | FOUND | 3898627865 | subject_id, hadm_id, emar_id, emar_seq, poe_id, pharmacy_id, enter_provider_id, charttime, medication, event_txt, scheduletime, storetime |
| `emar_detail.csv` | MISSING |  | n/a |
| `prescriptions.csv` | FOUND | 2646662732 | subject_id, hadm_id, pharmacy_id, poe_id, poe_seq, order_provider_id, starttime, stoptime, drug_type, drug, formulary_drug_cd, gsn, ndc, prod_strength, form_rx, dose_val_rx, dose_unit_rx, form_val_disp, form_unit_disp, doses_per_24_hrs, route |
| `admissions.csv` | FOUND | 73099499 | subject_id, hadm_id, admittime, dischtime, deathtime, admission_type, admit_provider_id, admission_location, discharge_location, insurance, language, marital_status, race, edregtime, edouttime, hospital_expire_flag |
| `patients.csv` | FOUND | 9881607 | subject_id, gender, anchor_age, anchor_year, anchor_year_group, dod |
| `inputevents.csv` | FOUND | 2345841395 | subject_id, hadm_id, stay_id, caregiver_id, starttime, endtime, storetime, itemid, amount, amountuom, rate, rateuom, orderid, linkorderid, ordercategoryname, secondaryordercategoryname, ordercomponenttypedescription, ordercategorydescription, patientweight, totalamount, totalamountuom, isopenbag, continueinnextdept, statusdescription, originalamount, originalrate |

`emar_detail.csv` is missing from the extracted hospital archive. No dose
detail fields can therefore be joined or claimed. `inputevents.csv` is retained
as an ICU input source, but it is not treated as a discrete EMAR
administration. The extracted source directory is not a replacement for the
original archives.

The local `hosp.rar` (762,388,455 bytes) was listed and extracted with the
installed `tar.exe` without extraction errors; its relevant members were
`emar.csv`, `prescriptions.csv`, `admissions.csv`, `patients.csv`, and
`omr.csv`. The local `icu.rar` (1,651,036,480 bytes) was listed and extracted
with the same tool without extraction errors; its relevant member was
`inputevents.csv`. `emar_detail.csv` was not an archive member.

## Fields and matching rules

Administration output uses `subject_id`, `hadm_id`, `emar_id`, `emar_seq`,
`charttime`, `storetime`, `event_txt`, and `medication`. `charttime` is used as
the administration event time and `storetime` is retained as record-entry
time; no assumption is made that they are interchangeable. Prescription
output uses the available order identifiers, `starttime`, `stoptime`, drug,
route, and dose fields. Orders and administrations are separate outputs.

Medication text is lower-cased, whitespace-normalized, and matched using
whole-word generic-name rules. The target classes are statins
(atorvastatin, simvastatin, rosuvastatin, pravastatin, lovastatin,
fluvastatin, pitavastatin, cerivastatin), aspirin, beta blockers (metoprolol,
carvedilol, atenolol, propranolol, bisoprolol, labetalol, nadolol, nebivolol,
pindolol, sotalol, esmolol, timolol), and ACE inhibitors (lisinopril,
enalapril, ramipril, perindopril, captopril, benazepril, quinapril, fosinopril,
trandolapril, moexipril). Multiple matches are ambiguous and are not retained
as a target class; unrelated names are not exported.

## Counts and quality checks

| Measure | Result |
|---|---:|
| EMAR rows read | 26,850,359 |
| EMAR target administrations retained | 1,515,317 |
| EMAR target rows excluded as non-administration statuses | 142,802 |
| Target administrations by class | statin: 312471, aspirin: 316542, beta_blocker: 763666, ace_inhibitor: 122638 |
| EMAR rows with missing medication name | 1,409,475 |
| EMAR rows with invalid subject_id / hadm_id | 0 / 1,814,608 |
| EMAR rows with valid subject_id / hadm_id | 26,850,359 / 25,036,751 (93.24% admission-linkage validity) |
| Prescription rows read | 15,416,708 |
| Prescription target orders retained | 881,020 |
| Same-patient/same-admission ECG-medication pairs | 0 |
| Temporal pair counts | none |

Counts in the administration output are source-event counts. Joined ECG
pair counts are not unique administration counts. Unique-admission and
unique-patient counts are included in the summary CSV and are calculated
before the ECG join.

Admission chronology was checked from `admissions.csv`: {'rows': 431231, 'columns': ['subject_id', 'hadm_id', 'admittime', 'dischtime', 'deathtime', 'admission_type', 'admit_provider_id', 'admission_location', 'discharge_location', 'insurance', 'language', 'marital_status', 'race', 'edregtime', 'edouttime', 'hospital_expire_flag'], 'admittime_valid': 431231, 'admittime_invalid': 0, 'dischtime_valid': 431231, 'dischtime_invalid': 0, 'deathtime_valid': 8598, 'deathtime_invalid': 0}.
ECG input status: {'found': False, 'reason': 'No ECG input path was supplied or it does not exist.'}.
The existing prescription-derived indicator columns were not available as a
machine-readable input, so disagreement between those indicators and EMAR
administrations is not estimable from this workspace.

## Existing longitudinal and ECG data

No ECG file was supplied to this run, and no source-level ECG master was
present in the inspected workspace. Consequently, `ecg_medication_timing.parquet`
has the required schema but zero rows. Existing documentation describes
admission, MI, death, and observation fields, but those derived files were not
available as local machine-readable inputs for this audit. No chronology or
outcome table was modified or reconstructed.

## Decision report

### A. ECG-level temporal analysis

The EMAR source contains event timestamps and valid patient/admission
identifiers for retained records, so the method can establish before/at/after
relationships once an ECG file with `study_id`, patient ID, `hadm_id`, and
`ecg_time` is supplied. This run cannot establish any ECG-level relationships
because that ECG input is missing.

### B. Treatment-effect analysis

No. Prescription starts are orders, not proof of administration, and a
recorded inpatient administration is not proof of treatment initiation,
outpatient use, adherence, or a causal assignment time. The available
administration timestamp alone does not establish prior exposure history,
baseline covariates, a clinically defensible time zero, or subsequent-MI
follow-up.

### C. Missing-data decision

The exact missing source required for ECG timing in this run is an ECG master
or source file containing `study_id`, `subject_id`/`SubjectID`, `hadm_id`, and
`ecg_time`. The exact missing hospital source is `emar_detail.csv`, needed
for dose and detailed administration fields requested by the audit. The
existing machine-readable admission/MI/death/follow-up artifacts are also
not present in the inspected workspace; they are required only for the
separate longitudinal treatment-effect design, not for the source-event
extraction itself.
