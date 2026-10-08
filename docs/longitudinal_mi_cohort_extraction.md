# Longitudinal MI Cohort Extraction Guide (MIMIC-IV)

> **Objective**: Create an encounter-level, longitudinal dataset from MIMIC-IV where the primary unit of analysis is the **MI Admission** (not the patient), capturing demographics, vitals, labs, and treatments across three distinct temporal windows (Before, During, and After the event).

---

## 1. Core Architecture: The Encounter-Level Design

To achieve an encounter-level dataset, the primary key of your final table must be `hadm_id` (the hospital admission ID), not `subject_id`.

**Rule of Independence:**
If a single patient (`subject_id = 1001`) has an MI admission in 2025 (`hadm_id = 5001`) and another in 2027 (`hadm_id = 5002`), these are treated as **two completely independent rows** in your dataset.

### The Temporal Anchor
For each MI row, the temporal anchor ($T_0$) is the **start of the admission**. 
* Use `edregtime` (Emergency Department registration time) if the patient came through the ED.
* Fall back to `admittime` if `edregtime` is missing.

### The Three Time Windows
To capture the longitudinal nature of the data, every dynamic feature (Labs, Vitals, Meds) must be suffixed by its time window relative to the anchor:

1. **Before MI (Baseline)**: $T \in [\text{Anchor} - 12 \text{ months}, \text{Anchor})$
   * *Purpose*: Captures baseline risk. Prior statin use, baseline LDL/HDL, chronic resting BP.
2. **During MI (Acute)**: $T \in [\text{Anchor}, \text{Discharge Time}]$
   * *Purpose*: Captures the severity of the event and acute interventions. Peak troponin, lowest SpO2, acute beta-blocker administration. (Often restricted to the first 24-48 hours for standardization).
3. **After MI (Follow-up)**: $T \in (\text{Discharge Time}, \text{Discharge Time} + 12 \text{ months}]$
   * *Purpose*: Captures post-event adherence and recovery. Are they still taking statins 6 months later? What is their follow-up BP?

---

## 2. Table Mapping & Feature Origins

Here is where your required features live in the MIMIC-IV-2.2 `hosp` and `icu` modules:

| Category | Feature | MIMIC-IV Source Table | Notes |
|----------|---------|-----------------------|-------|
| **Demographics** | Age | `patients.csv` + `admissions.csv` | Calculate: `admittime.year - anchor_year + anchor_age` |
| | Gender | `patients.csv` | Column: `gender` |
| | Ethnicity | `admissions.csv` | Column: `race` |
| **Vital Signs** | BP, HR, SpO2, Temp, RR | `icu/chartevents.csv` | High-frequency acute data (During MI). Filter by `itemid`. |
| | Outpatient Vitals | `hosp/omr.csv` | Sparser, but excellent for "Before MI" and "After MI" baseline BP/BMI. |
| **Labs** | LDL, HDL, Creatinine, BUN, Glucose, Potassium, BNP | `hosp/labevents.csv` | Filter by `itemid` (mapped via `d_labitems.csv`). |
| **Treatments**| Statins, Beta-blockers, ACEi, Aspirin | `hosp/prescriptions.csv` | Best for "Before" and "After" (what was prescribed). |
| | Acute Administration | `hosp/emar.csv` | Best for "During" (what was actually swallowed/infused during the hospital stay). |

---

## 3. Step-by-Step Data Engineering Logic

### Step 1: Define the Index MI Admissions
First, identify all admissions where an acute MI occurred. 

```sql
-- Step 1: Get all MI admissions (The Base Cohort)
WITH mi_admissions AS (
    SELECT DISTINCT 
        a.subject_id, 
        a.hadm_id, 
        COALESCE(a.edregtime, a.admittime) AS anchor_time,
        a.dischtime
    FROM `mimiciv_hosp.admissions` a
    JOIN `mimiciv_hosp.diagnoses_icd` d ON a.hadm_id = d.hadm_id
    WHERE (d.icd_version = 10 AND (d.icd_code LIKE 'I21%' OR d.icd_code LIKE 'I22%'))
       OR (d.icd_version = 9  AND d.icd_code LIKE '410%')
)
```

### Step 2: Feature Engineering - The Prior MI Flag (`had_prior_mi_admission`)
You need to know if the patient had an MI admission *before* this specific anchor time.

```sql
-- Step 2: Calculate prior history for EACH specific encounter
, encounter_with_history AS (
    SELECT 
        m1.subject_id,
        m1.hadm_id,
        m1.anchor_time,
        m1.dischtime,
        -- Check if there exists ANY admission for this patient with an earlier date
        CASE WHEN EXISTS (
            SELECT 1 
            FROM mi_admissions m2 
            WHERE m2.subject_id = m1.subject_id 
              AND m2.anchor_time < m1.anchor_time
        ) THEN True ELSE False END AS had_prior_mi_admission
    FROM mi_admissions m1
)
```

### Step 3: Extract Windowed Features (Example: Statins)
To extract medications across the three windows, you join the prescriptions table to your MI cohort table, conditionally aggregating based on the timestamp.

```sql
-- Step 3: Extract Statin use across the 3 time windows
, statin_features AS (
    SELECT 
        e.hadm_id,
        -- BEFORE MI: Was a statin prescribed in the 365 days prior?
        MAX(CASE WHEN p.starttime BETWEEN DATETIME_SUB(e.anchor_time, INTERVAL 365 DAY) AND e.anchor_time 
                 THEN 1 ELSE 0 END) AS statin_before_mi,
                 
        -- DURING MI: Was a statin prescribed during the hospital stay?
        MAX(CASE WHEN p.starttime BETWEEN e.anchor_time AND e.dischtime 
                 THEN 1 ELSE 0 END) AS statin_during_mi,
                 
        -- AFTER MI: Was a statin prescribed in the 365 days after discharge?
        MAX(CASE WHEN p.starttime BETWEEN e.dischtime AND DATETIME_ADD(e.dischtime, INTERVAL 365 DAY) 
                 THEN 1 ELSE 0 END) AS statin_after_mi
                 
    FROM encounter_with_history e
    LEFT JOIN `mimiciv_hosp.prescriptions` p 
        ON e.subject_id = p.subject_id
        AND LOWER(p.drug) LIKE '%vastatin%' -- Simple regex for statins
    GROUP BY e.hadm_id
)
```

### Step 4: Extract Windowed Labs (Example: LDL & Troponin)
For continuous variables like labs and vitals, you usually want specific aggregations (e.g., the *last* measurement before admission, the *peak* measurement during admission).

```sql
-- Step 4: Extract Lab values
, lab_features AS (
    SELECT 
        e.hadm_id,
        -- BEFORE: The most recent LDL value prior to admission
        -- (Requires a WINDOW function in practice, but conceptually:)
        MAX(CASE WHEN l.itemid = 50947 /* LDL */ 
                 AND l.charttime BETWEEN DATETIME_SUB(e.anchor_time, INTERVAL 365 DAY) AND e.anchor_time 
                 THEN l.valuenum END) AS ldl_before_mi,
                 
        -- DURING: The Peak (max) Creatinine during the acute event
        MAX(CASE WHEN l.itemid = 50912 /* Creatinine */ 
                 AND l.charttime BETWEEN e.anchor_time AND e.dischtime 
                 THEN l.valuenum END) AS peak_creatinine_during_mi
                 
    FROM encounter_with_history e
    LEFT JOIN `mimiciv_hosp.labevents` l 
        ON e.subject_id = l.subject_id
    GROUP BY e.hadm_id
)
```

---

## 4. The Final Target Schema (Wide Format)

Your final analytical dataset should be a "wide" table where every row is exactly one `hadm_id`. By joining the CTEs above together (`encounter_with_history` + `statin_features` + `lab_features` + `demographics`), you get:

| Column | Type | Origin/Calculation |
|--------|------|--------------------|
| `hadm_id` | Int (PK)| The MI Admission identifier |
| `subject_id` | Int | Patient identifier |
| `anchor_time` | Datetime | Encounter start time |
| `age_at_event` | Float | Demographics |
| `gender` | String | Demographics |
| `race` | String | Demographics |
| `had_prior_mi_admission`| Boolean | **Feature Engineered** (True if prior MI hadm_id exists) |
| `statin_before` | Binary | Prescriptions (Anchor - 365d to Anchor) |
| `statin_during` | Binary | Prescriptions (Anchor to Discharge) |
| `statin_after` | Binary | Prescriptions (Discharge to Discharge + 365d) |
| `ldl_before` | Float | Labs (Most recent in 365d prior) |
| `peak_trop_during` | Float | Labs (Max value during stay) |
| `min_spo2_during` | Float | Vitals (Min value during stay) |

### Key Advantages of this Structure:
1. **Solves the "History" leakage**: By indexing strictly on the `anchor_time` of the *current* admission, you completely prevent future data from leaking into past events.
2. **Handles Recurrence Naturally**: If a patient has an MI in 2020 and 2022, the 2022 row will correctly have `had_prior_mi_admission = True`, while the 2020 row will have `False`. Their "Before" medications will be evaluated independently for each date.
3. **Causal Ready**: By separating variables into Before (Confounders/Baseline), During (Acute Mediators), and After (Outcomes/Adherence), the dataset is perfectly aligned for Directed Acyclic Graph (DAG) analysis.
