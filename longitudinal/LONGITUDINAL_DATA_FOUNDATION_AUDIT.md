# LONGITUDINAL DATA FOUNDATION AUDIT

> **Date**: October 8, 2026
> **Purpose**: Document all recovered source data, coverage, timestamps, and longitudinal feasibility for the causal MI analysis.

---

## A. SOURCE FILES FOUND

### hosp/ (Hospital module)

| File | Size | Status | Used for |
|------|------|--------|----------|
| `admissions.csv` | 73 MB | **FOUND** | Admission chronology, anchor times |
| `patients.csv` | 9.9 MB | **FOUND** | Demographics, date of death |
| `diagnoses_icd.csv` | 135 MB | **FOUND** | MI diagnosis history |
| `d_icd_diagnoses.csv` | 8.8 MB | **FOUND** | ICD code dictionary |
| `labevents.csv` | 13.7 GB | **FOUND** | Clinical lab measurements |
| `d_labitems.csv` | 64 KB | **FOUND** | Lab item dictionary (1,622 items) |
| `omr.csv` | 266 MB | **FOUND** | Outpatient measurements (BP, BMI, weight) |
| `prescriptions.csv` | 2.6 GB | **FOUND** | Medication orders/prescriptions |
| `emar.csv` | 3.9 GB | **FOUND** | Medication administration records |
| `emar_detail.csv` | 5.5 GB | **FOUND** | Medication dose details |
| `pharmacy.csv` | 3.0 GB | **FOUND** | Pharmacy order details |
| `transfers.csv` | 157 MB | **FOUND** | Ward/unit transfers |
| `services.csv` | 21 MB | **FOUND** | Clinical service assignments |
| `procedures_icd.csv` | 26 MB | **FOUND** | Procedure codes |
| `microbiologyevents.csv` | 741 MB | **FOUND** | Microbiology cultures |
| `poe.csv` | 3.8 GB | **FOUND** | Provider order entry |
| `drgcodes.csv` | 42 MB | **FOUND** | DRG billing codes |

### icu/ (ICU module)

| File | Size | Status | Used for |
|------|------|--------|----------|
| `chartevents.csv` | 30.2 GB | **FOUND** | ICU vital signs |
| `d_items.csv` | 369 KB | **FOUND** | ICU item dictionary |
| `icustays.csv` | 11.5 MB | **FOUND** | ICU stay records |
| `inputevents.csv` | 2.3 GB | **FOUND** | IV fluid/medication inputs |
| `outputevents.csv` | 365 MB | **FOUND** | Urine/drain outputs |
| `procedureevents.csv` | 129 MB | **FOUND** | ICU procedures |
| `ingredientevents.csv` | 2.0 GB | **FOUND** | IV ingredient details |
| `datetimeevents.csv` | 778 MB | **FOUND** | Datetime-valued charted events |

## B. SOURCE FILES MISSING

| File | Expected | Status | Impact |
|------|----------|--------|--------|
| Outpatient pharmacy / community Rx | Not in MIMIC-IV | **STRUCTURALLY ABSENT** | Cannot establish true outpatient medication exposure |
| Outpatient lab results (non-OMR) | Not in MIMIC-IV | **STRUCTURALLY ABSENT** | Cannot get outpatient lipid panels from labevents |
| Social history / smoking | Not as structured table | **ABSENT** | Would need NLP on clinical notes |

> All required MIMIC-IV source files are physically present. The missing data elements are structural limitations of the MIMIC-IV data model, not file-level omissions.

---

## C. VARIABLES RECOVERED

### C.1 Admission Chronology

**Output**: `data/longitudinal/admissions_chronology.parquet` (431,231 rows, 30.3 MB)

| Field | Type | Coverage | Source |
|-------|------|----------|--------|
| subject_id | int | 100% | admissions.csv |
| hadm_id | int | 100% | admissions.csv |
| admittime | timestamp | 100% | admissions.csv |
| dischtime | timestamp | 100% | admissions.csv |
| deathtime | timestamp | 2.0% (8,598 admissions) | admissions.csv |
| edregtime | timestamp | 69.4% (299,282 admissions) | admissions.csv |
| edouttime | timestamp | present | admissions.csv |
| admission_type | string | 100% | admissions.csv |
| admission_location | string | 100% | admissions.csv |
| discharge_location | string | 100% | admissions.csv |
| insurance | string | 100% | admissions.csv |
| race | string | 100% | admissions.csv |
| hospital_expire_flag | int | 100% | admissions.csv |
| admission_seq | int | 100% | **Derived** — chronological position |
| previous_hadm_id | int | present for seq > 1 | **Derived** |
| previous_dischtime | timestamp | present for seq > 1 | **Derived** |
| next_hadm_id | int | present except last | **Derived** |
| next_admittime | timestamp | present except last | **Derived** |
| anchor_time | timestamp | 100% | **Derived** — COALESCE(edregtime, admittime) |
| total_admissions | int | 100% | **Derived** — per patient |

### C.2 Patient Demographics

**Output**: `data/longitudinal/patients_demographics.parquet` (299,712 rows, 2.4 MB)

| Field | Type | Coverage | Source |
|-------|------|----------|--------|
| subject_id | int | 100% | patients.csv |
| gender | string | 100% (M: 141,159 / F: 158,553) | patients.csv |
| anchor_age | int | 100% (range: 18-91, median: 48) | patients.csv |
| anchor_year | int | 100% | patients.csv |
| anchor_year_group | string | 100% | patients.csv |
| dod | date | 9.7% (29,076 patients) | patients.csv |

### C.3 MI / Diagnosis History

**Output**: `data/longitudinal/diagnoses_all.parquet` (4,756,326 rows, 29.4 MB)
**Output**: `data/longitudinal/diagnoses_mi_codes.parquet` (26,824 rows, 0.9 MB)
**Output**: `data/longitudinal/mi_admissions.parquet` (25,755 rows, 0.6 MB)

| Field | Type | Coverage | Source |
|-------|------|----------|--------|
| subject_id | int | 100% | diagnoses_icd.csv |
| hadm_id | int | 100% | diagnoses_icd.csv |
| icd_code | string | 100% | diagnoses_icd.csv |
| icd_version | int | 100% (ICD-9 and ICD-10) | diagnoses_icd.csv |
| seq_num | int | 100% | diagnoses_icd.csv |
| is_mi_code | binary | 100% | **Derived** — ICD-10: I21/I22/I23; ICD-9: 410/412 |
| mi_admission_seq | int | MI admissions only | **Derived** — chronological MI admission number |
| total_mi_admissions | int | MI patients only | **Derived** |
| is_first_mi_admission | binary | MI patients only | **Derived** |

### C.4 Observation End / Death

**Output**: `data/longitudinal/observation_end.parquet` (180,733 rows, 6.7 MB)

| Field | Type | Coverage | Source |
|-------|------|----------|--------|
| subject_id | int | 100% | Multiple |
| last_discharge | timestamp | 100% | admissions.csv (MAX) |
| last_admittime | timestamp | 100% | admissions.csv (MAX) |
| in_hospital_deathtime | timestamp | 4.8% (8,592 patients) | admissions.csv |
| dod | date | 15.5% (27,980 patients) | patients.csv |
| is_dead | binary | 100% | **Derived** |
| observation_end | string | 100% | **Derived** — COALESCE(dod, deathtime, last_discharge) |

### C.5 ECG Information (PRESERVED, NOT REBUILT)

| Field | Source | Status |
|-------|--------|--------|
| 95 ECG features | Existing pipeline | **Preserved** — not modified |
| 64 z_ecg embeddings | Existing pipeline | **Preserved** — not modified |
| study_id | Existing labels | **Preserved** |
| ecg_time | Existing labels | **Preserved** |
| hadm_id | Existing labels | **Preserved** |
| SubjectID | Existing labels | **Preserved** |

---

## D. TIMESTAMP COVERAGE

| Source Table | Timestamp Field | Coverage | Granularity | Notes |
|-------------|----------------|----------|-------------|-------|
| admissions.csv | admittime | 100% | datetime | Formal admission time |
| admissions.csv | dischtime | 100% | datetime | Discharge time |
| admissions.csv | deathtime | 2.0% | datetime | In-hospital death only |
| admissions.csv | edregtime | 69.4% | datetime | ED registration; null for direct admits |
| labevents.csv | charttime | 100% of rows used | datetime | Lab collection/measurement time |
| omr.csv | chartdate | 100% | **date only** | No time-of-day — same-day ambiguity |
| emar.csv | charttime | **0 nulls** | datetime | Administration time |
| prescriptions.csv | starttime | 99.9% | datetime | Prescription start |
| prescriptions.csv | stoptime | 99.9% | datetime | Prescription stop |
| chartevents.csv | charttime | 100% | datetime | ICU vital recording time |
| ECG labels | ecg_time | 100% | datetime | ECG acquisition time |

### Critical Timestamp Limitations

1. **OMR has date-only resolution** (`chartdate`). Same-day measurements from OMR cannot be temporally ordered relative to same-day ECGs, labs, or admissions.
2. **EMAR timestamps are inpatient only**. They cannot establish pre-admission medication timing (documented in EMAR_RECONSTRUCTION_DECISION.md).
3. **Prescription starttime/stoptime** are order times, not actual administration times.

---

## E. PATIENT / ADMISSION COVERAGE

### E.1 Full MIMIC-IV Population

| Metric | Count |
|--------|-------|
| Total patients (patients.csv) | 299,712 |
| Total patients with admissions | 180,733 |
| Total admissions | 431,231 |
| Single-admission patients | 101,198 (56.0%) |
| Multi-admission patients | 79,535 (44.0%) |
| Discharge-before-admission errors | 139 (0.03%) |

### E.2 MI Admissions (Full MIMIC-IV)

| Metric | Count |
|--------|-------|
| Admissions with any MI ICD code | 25,755 |
| Patients with any MI admission | 14,905 |
| Patients with exactly 1 MI admission | 10,297 (69.1%) |
| Patients with >1 MI admission | 4,608 (30.9%) |

### E.3 Current ECG Cohort (Existing Master Dataset)

| Metric | Count |
|--------|-------|
| Cohort patients (with ECGs) | 99,256 |
| Cohort hadm_ids | 191,369 |
| Total admissions for cohort patients | 311,633 |
| Single-admission cohort patients | 42,784 (43.1%) |
| Multi-admission cohort patients | 56,472 (56.9%) |
| Cohort patients with any MI admission | 12,250 |
| **Cohort patients with non-MI admission THEN later MI** | **5,460** |
| **Total subsequent-MI admissions** | **11,223** |

> **CRITICAL LONGITUDINAL NUMBER**: 5,460 cohort patients have at least one non-MI admission followed by a later MI-coded admission. These are the candidates for a "subsequent MI" longitudinal design.

### E.4 Death / Observation End

| Metric | Count |
|--------|-------|
| Patients with known date of death (dod) | 27,980 (15.5% of admitted patients) |
| Patients with in-hospital death timestamp | 8,592 (4.8%) |
| Patients alive or censored | 152,753 (84.5%) |

---

## F. CLINICAL FACTOR COVERAGE

### F.1 Laboratory Measurements (labevents.csv)

Ordered by cohort coverage:

| Category | Lab Name | itemid | Cohort Patients | Coverage % | Cohort Measurements | Unit | Median |
|----------|----------|--------|-----------------|------------|---------------------|------|--------|
| **Hematology** | Hematocrit | 51221 | 98,973 | **99.7%** | 2,514,019 | % | 33.3 |
| **Renal** | Creatinine | 50912 | 98,963 | **99.7%** | 2,552,590 | mg/dL | 0.9 |
| **Hematology** | Platelet Count | 51265 | 98,956 | **99.7%** | 2,428,934 | K/uL | 219.0 |
| **Renal** | BUN | 51006 | 98,945 | **99.7%** | 2,496,628 | mg/dL | 18.0 |
| **Hematology** | WBC | 51301 | 98,879 | **99.6%** | 2,390,888 | K/uL | 7.6 |
| **Hematology** | Hemoglobin | 51222 | 98,876 | **99.6%** | 2,406,218 | g/dL | 11.0 |
| **Electrolyte** | Potassium | 50971 | 98,736 | **99.5%** | 2,495,355 | mEq/L | 4.1 |
| **Electrolyte** | Sodium | 50983 | 98,705 | **99.4%** | 2,471,406 | mEq/L | 139.0 |
| **Electrolyte** | Chloride | 50902 | 98,697 | **99.4%** | 2,445,915 | mEq/L | 102.0 |
| **Electrolyte** | Bicarbonate | 50882 | 98,630 | **99.4%** | 2,356,113 | mEq/L | 26.0 |
| **Glycemia** | Glucose (blood) | 50931 | 98,623 | **99.4%** | 2,154,698 | mg/dL | 110.0 |
| **Electrolyte** | Calcium, Total | 50893 | 90,536 | **91.2%** | 1,801,841 | mg/dL | 8.8 |
| **Electrolyte** | Magnesium | 50960 | 90,531 | **91.2%** | 1,796,421 | mg/dL | 2.0 |
| **Electrolyte** | Phosphate | 50970 | 89,554 | **90.2%** | 1,722,256 | mg/dL | 3.4 |
| **Coagulation** | INR(PT) | 51237 | 87,950 | **88.6%** | 1,148,631 | — | 1.3 |
| **Coagulation** | PT | 51274 | 87,947 | **88.6%** | 1,148,154 | sec | 14.1 |
| **Coagulation** | PTT | 51275 | 87,025 | **87.7%** | 1,034,023 | sec | 32.9 |
| **Liver** | ALT | 50861 | 79,429 | **80.0%** | 995,208 | IU/L | 24.0 |
| **Liver** | AST | 50878 | 79,217 | **79.8%** | 986,073 | IU/L | 27.0 |
| **Liver** | Bilirubin, Total | 50885 | 76,571 | **77.1%** | 895,514 | mg/dL | 0.5 |
| **Nutrition** | Albumin | 50862 | 71,400 | **71.9%** | 573,695 | g/dL | 3.9 |
| **Glycemia** | HbA1c | 50852 | 41,959 | **42.3%** | 143,921 | % | 6.1 |
| **Glycemia** | Glucose (blood gas) | 50809 | 33,023 | **33.3%** | 173,954 | mg/dL | 129.0 |
| **Cardiac** | NT-proBNP | 50963 | 23,133 | **23.3%** | 57,527 | pg/mL | 1,449 |
| **Inflammatory** | CRP | 50889 | 23,103 | **23.3%** | 74,641 | mg/L | 5.9 |

### F.2 Lipid Panel (DISCOVERED BUT NOT YET EXTRACTED)

These itemids were found in d_labitems but were NOT in the initial Phase 2 scan. Coverage counts are from full MIMIC-IV (not cohort-specific yet):

| Lab Name | itemid | Total Measurements | Total Patients | Status |
|----------|--------|--------------------|----------------|--------|
| Cholesterol, Total | 50907 | 250,248 | 83,893 | **Available** |
| Triglycerides | 51000 | 250,001 | 84,519 | **Available** |
| Cholesterol, HDL | 50904 | 244,256 | 82,555 | **Available** |
| Cholesterol Ratio (Total/HDL) | 50903 | 243,329 | 82,219 | **Available** |
| Cholesterol, LDL, Calculated | 50905 | 222,310 | 78,444 | **Available** |
| Cholesterol, LDL, Measured | 50906 | 39,282 | 19,339 | **Available** |

> Lipids are available with substantial coverage (~78K-84K patients). These are almost certainly inpatient draws. Outpatient lipid panels are NOT in labevents.

### F.3 eGFR (DISCOVERED)

| Lab Name | itemid | Status |
|----------|--------|--------|
| Estimated GFR (MDRD equation) | 50920 | **Available** in labevents |
| Estimated GFR (MDRD equation) | 52026 | **Available** in blood gas |

### F.4 Itemid Mapping Corrections

| Original Category | itemid | Actual Label | Correct? |
|-------------------|--------|-------------|----------|
| BNP | 50963 | NTproBNP | Yes — this IS NT-proBNP |
| NT_proBNP | 50964 | Osmolality, Measured | **NO — wrong mapping** |

> itemid 50964 is Osmolality, not NT-proBNP. There is no separate BNP itemid. Only NT-proBNP (50963) is available.

### F.5 Lab Timing Relative to Admission (Cohort Only)

| Lab | Total Cohort | Before Admission | During Admission | After Discharge |
|-----|-------------|------------------|------------------|-----------------|
| Potassium | 1,277,909 | 23,612 (1.8%) | 1,253,598 (98.1%) | 699 (0.1%) |
| Sodium | 1,264,995 | 23,605 (1.9%) | 1,240,685 (98.1%) | 705 (0.1%) |
| Creatinine | 1,232,258 | 24,208 (2.0%) | 1,207,376 (97.9%) | 674 (0.1%) |
| Bicarbonate | 1,214,448 | 23,563 (1.9%) | 1,190,216 (98.0%) | 669 (0.1%) |
| Glucose | 1,196,808 | 23,504 (2.0%) | 1,172,637 (98.0%) | 667 (0.1%) |
| Hemoglobin | 1,127,017 | 23,912 (2.1%) | 1,102,447 (97.8%) | 658 (0.1%) |
| WBC | 1,117,810 | 23,917 (2.1%) | 1,093,235 (97.8%) | 658 (0.1%) |
| Calcium | 1,054,783 | 8,208 (0.8%) | 1,045,970 (99.2%) | 605 (0.1%) |

> **97-99% of lab measurements are inpatient (during admission).** Only ~2% are pre-admission. This is the same structural pattern as EMAR: MIMIC-IV is fundamentally an inpatient database.

### F.6 OMR Outpatient Measurements

| Result Name | Total Records | Cohort Patients | Cohort Coverage % | Cohort Records |
|-------------|---------------|-----------------|-------------------|----------------|
| Weight (Lbs) | 1,889,542 | 68,310 | **68.8%** | 1,179,762 |
| BMI (kg/m2) | 1,662,112 | 64,167 | **64.6%** | 1,041,860 |
| Height (Inches) | 706,906 | 62,826 | **63.3%** | 442,714 |
| Blood Pressure | 2,169,549 | 59,863 | **60.3%** | 1,316,642 |
| Blood Pressure Sitting | 3,400 | 1,288 | 1.3% | 2,365 |
| Blood Pressure Lying | 2,764 | 1,064 | 1.1% | 1,912 |
| BP Standing (1 min) | 2,560 | 1,038 | 1.0% | 1,750 |
| eGFR (OMR) | 240 | 151 | 0.2% | 199 |

> **OMR provides genuine outpatient measurements** for weight (69%), BMI (65%), height (63%), and blood pressure (60%). These have **date-only** granularity (chartdate, no time-of-day). OMR eGFR coverage is negligible (0.2%).

### F.7 ICU Vital Signs (chartevents.csv)

| Vital Sign | itemid | Cohort Admissions | Cohort Records | Median |
|-----------|--------|-------------------|----------------|--------|
| Heart Rate | 220045 | 46,846 | 4,999,337 | 85.0 |
| Respiratory Rate | 220210 | 46,829 | 4,957,313 | 19.0 |
| SpO2 | 220277 | 46,813 | 4,897,199 | 97.0 |
| Heart Rhythm | 220048 | 46,699 | 4,602,545 | (categorical) |
| NIBP Systolic | 220179 | 46,449 | 3,111,120 | 117.0 |
| NIBP Diastolic | 220180 | 46,448 | 3,110,423 | 63.0 |
| NIBP Mean | 220181 | 46,450 | 3,110,346 | 77.0 |
| Temp (F) | 223761 | 46,218 | 1,168,097 | 98.4 |
| ABP Systolic | 220050 | 19,313 | 1,816,808 | 117.0 |
| ABP Diastolic | 220051 | 19,317 | 1,816,512 | 57.0 |
| ABP Mean | 220052 | 19,468 | 1,823,355 | 77.0 |
| Daily Weight | 224639 | 27,496 | 156,599 | 86.4 |
| Height (cm) | 226730 | 24,907 | 25,335 | 170.0 |
| Temp (C) | 223762 | 5,639 | 211,996 | 37.0 |

> ICU vitals cover ~46K of 191K cohort admissions (24%). These are ICU-only measurements and are **acute inpatient observations**, not baseline.

---

## G. TREATMENT COVERAGE

### G.1 Prescriptions Source

| Metric | Value |
|--------|-------|
| Total prescription rows | 15,416,708 |
| Unique admissions | 365,442 |
| Cohort admissions | 168,387 (88.0% of 191,369) |
| With starttime | 15,399,765 (99.9%) |
| With stoptime | 15,394,109 (99.9%) |

### G.2 EMAR Source (Documented in EMAR_RECONSTRUCTION_DECISION.md)

| Metric | Value |
|--------|-------|
| Total EMAR rows | 26,850,359 |
| Charttime coverage | **100%** (zero nulls) |
| Limitation | **Inpatient administration only** — cannot establish pre-admission baseline |

### G.3 Per-Treatment Coverage

| Treatment | Existing `*_before` | EMAR cohort admin | Rx cohort coverage | EMAR usable for baseline? |
|-----------|--------------------|--------------------|-------------------|--------------------------|
| Statin | 13,203 hadm_ids (6.9%) | 36,610 hadm_ids (19.1%) | via prescriptions.csv | **No** |
| Aspirin | 14,927 hadm_ids (7.8%) | 38,304 hadm_ids (20.0%) | via prescriptions.csv | **No** |
| Beta Blocker | 6,099 hadm_ids (3.2%) | 41,560 hadm_ids (21.7%) | via prescriptions.csv | **No** |
| ACEi | 6,196 hadm_ids (3.2%) | 16,312 hadm_ids (8.5%) | via prescriptions.csv | **No** |

### G.4 Treatment Timing Availability

| Source | Start Time | Stop Time | Administration Time | Baseline Exposure? |
|--------|-----------|-----------|--------------------|--------------------|
| prescriptions.csv | starttime (99.9%) | stoptime (99.9%) | N/A — order times only | **Proxy only** — 7-day pre-admission window |
| emar.csv | N/A | N/A | charttime (100%) | **No** — inpatient only |
| pharmacy.csv | present | present | N/A | Unverified |

---

## H. LONGITUDINAL FEASIBILITY

### Can we establish: factor/treatment → baseline → follow-up → later MI?

#### H.1 Admission Chronology — YES

- 56,472 cohort patients (57%) have multiple admissions
- Chronological admission sequencing is complete
- Previous/next admission linkage is built
- Median 3.1 admissions per multi-admission patient

#### H.2 Baseline Selection — CONDITIONALLY YES

**For a "prior non-MI admission" baseline:**
- 5,460 cohort patients have a non-MI admission followed by at least one later MI admission
- These patients contribute 11,223 subsequent-MI admissions
- Baseline time = anchor_time of the non-MI admission
- This is a workable longitudinal cohort for "subsequent MI" analysis

**Limitation:** Baseline must be defined carefully:
- The first non-MI admission? Any non-MI admission before the first MI?
- This requires a scientific/domain decision

#### H.3 Clinical Factor Measurement at Baseline — CONDITIONALLY YES

**High-coverage labs available during baseline admission (>99%):**
- Creatinine, BUN, glucose, potassium, sodium, hemoglobin, WBC, platelets, hematocrit

**Moderate-coverage labs (77-91%):**
- Calcium, magnesium, phosphate, albumin, bilirubin, ALT, AST, INR/PT/PTT

**Lower-coverage but important (23-42%):**
- HbA1c (42%), NT-proBNP (23%), CRP (23%)

**Lipids (not yet extracted for cohort, ~78-84K patients in full MIMIC):**
- LDL, HDL, total cholesterol, triglycerides — likely ~40-50% cohort coverage

**KEY LIMITATION:** ~98% of lab measurements are **during admission**. Only ~2% are pre-admission. Labs measured during the baseline admission reflect the acute clinical state, not the patient's outpatient baseline. This is a confounder/mediator concern, not a data-availability issue.

#### H.4 Outpatient Baseline — PARTIALLY YES (OMR ONLY)

**OMR provides genuine outpatient data for:**
- Blood pressure (60% cohort coverage, date-only)
- BMI (65% coverage, date-only)
- Weight (69% coverage, date-only)

**OMR does NOT provide:**
- Outpatient lipids, HbA1c, creatinine, or any lab values
- Time-of-day ordering

#### H.5 Treatment Exposure at Baseline — CONDITIONALLY YES

**Existing `*_before` variables** provide prescription-window proxy for:
- Statin (6.9%), aspirin (7.8%), beta blocker (3.2%), ACEi (3.2%)

These are low prevalence but usable if the target population is correctly understood. The prescription-window design (7-day pre-admission) is the best available approximation. EMAR cannot improve it (documented).

#### H.6 Follow-up — CONDITIONALLY YES

**For patients with subsequent admissions:**
- Next admission time is known
- Death date (dod) available for 15.5% of admitted patients
- Observation end = COALESCE(dod, last_discharge)

**Limitation:** Patients who do not return to BIDMC are censored at their last discharge. We cannot distinguish "no MI" from "MI at another hospital." This is a standard administrative-data limitation.

#### H.7 Outcome (Later MI) — YES

- 5,460 patients have verified subsequent MI admissions
- MI coding based on ICD-10 I21/I22/I23 and ICD-9 410/412
- Temporal ordering verified through admission chronology
- First MI vs recurrent MI distinguishable

---

## I. PROBLEM CLASSIFICATION

### CLINICAL BRANCH (Risk Factors / Biomarkers → MI)

**Status: CONDITIONALLY READY**

| Criterion | Status | Details |
|-----------|--------|---------|
| Baseline population definable? | YES | 5,460 patients with non-MI→MI trajectory |
| Baseline time definable? | YES | Anchor time of prior non-MI admission |
| Clinical measurements available? | YES | 99%+ coverage for core labs during admission |
| Outpatient measurements? | PARTIAL | OMR: BP (60%), BMI (65%); no outpatient labs |
| Follow-up determinable? | YES | Next admission time + death date |
| Outcome verifiable? | YES | Subsequent MI admission with ICD codes |
| **Main condition**: | | Scientific decision needed on whether **inpatient labs during a prior non-MI admission** constitute a defensible "baseline" for risk-factor analysis, given that they reflect acute clinical state |

### TREATMENT BRANCH (Medication → MI)

**Status: CONDITIONALLY READY — WITH KNOWN LIMITATIONS**

| Criterion | Status | Details |
|-----------|--------|---------|
| Baseline population definable? | YES | Same 5,460 patients |
| Baseline time definable? | YES | Anchor time of prior non-MI admission |
| Treatment exposure measurable? | PARTIAL | `*_before` prescription-window proxy (3-8% prevalence); EMAR does not help |
| Actual administration verifiable? | NO | EMAR is inpatient-only; cannot verify outpatient compliance |
| Pre-admission exposure? | PROXY ONLY | Prescription window, not true outpatient pharmacy |
| Follow-up determinable? | YES | Same as clinical branch |
| Outcome verifiable? | YES | Same as clinical branch |
| **Main condition**: | | Treatment exposure is a **weak proxy** with low prevalence. Positivity violations likely for low-prevalence treatments (3.2% ACEi, 3.2% beta blocker) |

---

## J. REMAINING BLOCKERS

### J.1 Actual Blockers (Cannot Proceed Without Resolution)

| # | Blocker | Branch | Resolution |
|---|---------|--------|------------|
| 1 | **Baseline definition requires scientific decision** | Both | Must choose: first non-MI admission? Most recent pre-MI admission? Any eligible admission? |
| 2 | **Inpatient labs as "baseline" is clinically debatable** | Clinical | Need domain justification: are labs drawn early in a non-MI hospitalization defensible as "pre-MI risk factor" measurements? |
| 3 | **Lipid panel coverage not yet quantified for cohort** | Clinical | Need to run cohort-specific lipid extraction (itemids 50903-50907, 51000) |
| 4 | **OMR date-only ambiguity** | Clinical | Same-day OMR + admission creates ordering ambiguity |

### J.2 Known Limitations (Documented, Not Blocking)

| # | Limitation | Branch | Impact |
|---|-----------|--------|--------|
| 1 | No outpatient pharmacy data | Treatment | Cannot verify true outpatient medication compliance |
| 2 | No outpatient lab data | Clinical | Cannot get "healthy baseline" lipid/metabolic panel |
| 3 | Censoring at last discharge | Both | Patients who have MI at another hospital appear as censored |
| 4 | Low treatment prevalence (3-8%) | Treatment | Positivity concerns for treatment-effect estimation |
| 5 | 139 discharge-before-admission errors | Both | Negligible (0.03%) — exclude from analysis |

---

## K. FINAL RECOMMENDATION

### What Can Proceed Now

1. **Finalize baseline definition** — scientific/domain decision on which admission qualifies as "baseline" for the 5,460 subsequent-MI patients
2. **Extract cohort-specific lipid panel coverage** (itemids 50903-50907, 51000) — one additional labevents scan
3. **Extract cohort-specific eGFR coverage** (itemids 50920, 52026)
4. **Build the analysis-ready longitudinal table** once baseline is defined — merge baseline labs, OMR, treatments, and ECG onto the chronological admission spine

### What Requires Scientific Decision First

| Decision | Options | Who Decides |
|----------|---------|-------------|
| Baseline admission selection rule | First non-MI admission / most recent pre-MI / any eligible | Domain expert + investigator |
| Whether inpatient labs qualify as "baseline" | Accept with caveat / restrict to first-24h labs / use OMR only | Domain expert |
| Target causal question | Risk factor → MI / Treatment → MI / Both | Investigator |
| Clinical exposure selection | Single factor (e.g., creatinine) / composite / multiple | Investigator |
| Treatment exposure definition | Keep `*_before` as-is / attempt enhancement | Investigator |
| Follow-up horizon | Next admission / 1 year / all available | Investigator |
| Time zero definition | Admission anchor / discharge / ECG time | Investigator |

### Data Architecture Delivered

```
data/longitudinal/
├── admissions_chronology.parquet    (431K rows — full admission spine)
├── patients_demographics.parquet    (300K rows — demographics + death)
├── diagnoses_all.parquet            (4.8M rows — all ICD diagnoses)
├── diagnoses_mi_codes.parquet       (27K rows — MI codes only)
├── mi_admissions.parquet            (26K rows — MI admission summary)
├── observation_end.parquet          (181K rows — death/censoring)
├── lab_coverage_catalogue.parquet   (coverage for 26 priority labs)
├── omr_coverage_catalogue.parquet   (coverage for 13 OMR measures)
├── vitals_coverage_catalogue.parquet (coverage for 14 ICU vitals)
├── d_labitems.parquet               (lab dictionary)
├── phase1_stats.json                (admission/MI/cohort statistics)
└── phase2_stats.json                (lab/OMR/vital/Rx statistics)
```

The existing master dataset (`data/modeling/`) remains **untouched**.

### Next Phase

Once baseline definition is decided, the next step is to extract the actual lab/OMR/treatment values for the eligible baseline admissions and build the analysis-ready longitudinal dataset.
