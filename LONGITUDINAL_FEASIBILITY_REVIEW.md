# 1. Executive conclusion

The five recovered longitudinal parquet files are sufficient to validate the MI cohort structure and chronology, but they are not sufficient to finalize a causal clinical or treatment design. The longitudinal MI cohort is identifiable and internally coherent, but baseline lab timing and treatment timing remain unresolved without additional raw event-level data.

Bottom line:

- Clinical branch: CONDITIONALLY READY
- Treatment branch: NOT READY

The main blocker is not cohort construction; it is that the current files do not include the necessary timestamped exposures needed to distinguish pre-admission baseline labs and medications from acute inpatient values.

# 2. Files inspected

The audit used the recovered longitudinal files in `longitudinal/longitudinal/`:

| File | Rows | Key fields | Main use |
|------|------|------------|----------|
| `admissions_chronology.parquet` | 431,231 | `subject_id`, `hadm_id`, `admittime`, `dischtime`, `anchor_time`, `admission_seq`, `previous_hadm_id`, `previous_dischtime`, `next_hadm_id`, `next_admittime` | chronology and baseline admission ordering |
| `mi_admissions.parquet` | 25,755 | `subject_id`, `hadm_id`, `mi_icd_codes`, `admittime`, `mi_admission_seq`, `total_mi_admissions`, `is_first_mi_admission` | MI cohort definition |
| `observation_end.parquet` | 180,733 | `subject_id`, `last_discharge`, `last_admittime`, `in_hospital_deathtime`, `dod`, `observation_end` | follow-up and censoring |
| `patients_demographics.parquet` | 299,712 | `subject_id`, `gender`, `anchor_age`, `anchor_year`, `anchor_year_group`, `dod` | demographics |
| `lab_coverage_catalogue.parquet` | 26 | `itemid`, `lab_name`, `category`, `total_measurements`, `unique_patients`, `cohort_patients`, `cohort_measurements`, `common_unit` | coverage screen for candidate labs |

This is a feasibility audit only; no causal estimation, DAG finalization, or adjustment-set selection was performed.

# 3. Admission chronology validation

## Core validation results

`admissions_chronology.parquet` passes the key structural checks:

| Check | Result |
|-------|--------|
| duplicate `subject_id` + `hadm_id` rows | 0 |
| missing `admittime` | 0 |
| missing `dischtime` | 0 |
| missing `admission_seq` | 0 |
| missing `anchor_time` | 0 |
| unique `subject_id` | 180,733 |
| unique `hadm_id` | 431,231 |
| `previous_dischtime > admittime` | 59 |
| `dischtime > next_admittime` | 59 |
| `admission_seq` mismatch within subject | 0 |

Interpretation:

- The chronology file is generally sound. There are no duplicate admission keys and no missing core timestamps.
- The strict ordering rule is violated for 59 admissions in each direction, which is a non-zero anomaly count but not a broad data failure.
- The fact that `admission_seq` remains perfectly consistent with within-subject time order means the derived admission ordering is coherent even when neighboring admissions have small overlap or reversal edge cases.

## Date range

- `admittime`: 2105-10-04 17:26:00 to 2212-04-06 12:13:00
- `dischtime`: 2105-10-12 11:11:00 to 2212-04-12 14:06:00

This supports a long-running longitudinal cohort and a realistic patient follow-up window. The 59 chronology edge cases should be reviewed before final cohort locking, but they do not invalidate the broader structure.

# 4. Subsequent-MI cohort validation

## MI representation

`mi_admissions.parquet` contains 25,755 MI admissions across 14,905 unique patients.

Key properties:

- `mi_icd_codes` is a semicolon-delimited MI code list
- `min_seq_num` gives the earliest MI-related diagnosis priority within an admission
- `mi_admission_seq` gives within-patient MI ordering
- `total_mi_admissions` gives recurrent MI count per patient
- `is_first_mi_admission` distinguishes index vs recurrent MI

The file clearly supports:

- first MI admission per patient
- recurrent MI admissions per patient
- patient-level linkage between `subject_id` and `hadm_id`

## MI counts

| Quantity | Value |
|----------|-------|
| total admissions | 431,231 |
| total unique patients | 180,733 |
| MI admissions | 25,755 |
| patients with >= 1 MI | 14,905 |
| patients with > 1 MI | 4,608 |

## Baseline rule comparison

The exact count of “non-MI baseline admission → later MI” depends strongly on the baseline rule. The five-file audit directly evaluated three candidate rules.

| Rule | Eligible baseline admissions | Eligible patients | Later MI patients | Later MI admissions |
|------|---------------------------|------------------|------------------|--------------------|
| A. first non-MI admission per patient | 174,055 | 174,055 | 5,774 | 11,590 |
| B. most recent non-MI before first MI | 4,857 | 4,857 | 4,857 | 9,147 |
| C. first non-MI admission with >= 30-day follow-up | 20,222 | 20,222 | 2,641 | 6,021 |

Interpretation:

- Rule A is the broadest and most permissive; it is useful for a very broad “all-patient” cohort but admits large heterogeneity.
- Rule B is a tighter, more clinically interpretable historical baseline rule, but it is restricted to patients who had a prior non-MI admission before their first MI.
- Rule C is a prospective-style rule with follow-up screening, but it sharply reduces sample size and is a design choice rather than a universal cohort definition.

This is exactly the scientific decision point the project must settle before any final DAG or treatment design. The files support the comparison, but they do not settle the “correct” rule.

# 5. Follow-up validation

`observation_end.parquet` contains one row per patient.

| Metric | Value |
|--------|-------|
| total subjects | 180,733 |
| `is_dead = 1` | 27,980 |
| in-hospital deathtime present | 8,592 |
| `dod` present | 27,980 |
| observation_end before `last_discharge` | 8,383 |

This is an important detail:

- `observation_end` is not simply “last discharge.”
- It is effectively a patient-level endpoint defined from the last known clinical endpoint; for many subjects it is the death date or in-hospital death time, not discharge.
- The 8,383 cases in which observation_end is before the patient’s last discharge are not necessarily impossible. They are consistent with patients whose final clinically relevant event is a death or inpatient endpoint before a later discharge record.

The recovered data therefore support a patient-level censoring framework, but they do not yet define a single follow-up horizon for all comparisons.

# 6. Demographic validation

`patients_demographics.parquet` contains 299,712 rows and 299,712 unique `subject_id` values.

| Variable | Result |
|----------|--------|
| gender counts | F = 158,553; M = 141,159 |
| `anchor_age` min | 18 |
| `anchor_age` max | 91 |
| `anchor_age` median | 48 |
| `dod` present | 29,076 |
| missing `dod` | 270,636 |

Important caveat:

- `anchor_age` is not automatically the patient’s age at every admission.
- It is a patient-level anchor age tied to the de-identification anchor year, not a direct age-at-each-hadm_id field.
- To attach demographic information to an admission, the project must compute age-at-admission using the patient’s anchor reference plus the relevant admission year, rather than assuming `anchor_age` is universally valid for every encounter.

# 7. Clinical-factor candidate review

The current catalogue is not a full clinical-risk-factor table; it is a lab coverage screen. It includes 26 lab rows and does not include all clinically relevant markers. The catalogue strongly supports routine chemistry and hematology labs, but not all candidate baseline factors are equally usable.

## A. HIGH-PRIORITY CANDIDATES

These are the most clinically interpretable and coverage-strong candidates in the current file:

| Factor | Itemid | Cohort patients | Cohort measurements | Coverage note |
|--------|--------|-----------------|--------------------|---------------|
| Creatinine | 50912 | 98,963 | 2,552,590 | extremely high coverage; clinically interpretable but often acute/inpatient |
| BUN | 51006 | 98,945 | 2,496,628 | high coverage |
| Potassium | 50971 | 98,736 | 2,495,355 | high coverage |
| Sodium | 50983 | 98,705 | 2,471,406 | high coverage |
| Glucose | 50931 | 98,623 | 2,154,698 | high coverage; must separate repeated inpatient values |
| Hemoglobin | 51222 | 98,876 | 2,406,218 | high coverage |
| Hematocrit | 51221 | 98,973 | 2,514,019 | high coverage |
| WBC | 51301 | 98,879 | 2,390,888 | high coverage |
| Platelets | 51265 | 98,956 | 2,428,934 | high coverage |
| HbA1c | 50852 | 41,959 | 143,921 | moderate coverage; meaningful but sparse |
| CRP | 50889 | 23,103 | 74,641 | sparse but biologically meaningful |
| NT-proBNP | 50963 | 23,133 | 57,527 | sparse but clinically relevant |

## B. POSSIBLE CANDIDATES

| Factor | Coverage note | Clinical interpretation |
|--------|---------------|------------------------|
| Calcium, Total | moderate coverage | plausible but often acute/medical illness related |
| Magnesium | moderate coverage | plausible but often non-specific |
| Phosphate | moderate coverage | plausible but acute/inpatient heavy |
| Albumin | moderate coverage | useful but likely downstream/illness marker |
| ALT / AST / bilirubin | moderate to high coverage | liver-related but not direct MI risk factor |

## C. ACUTE / LIKELY DOWNSTREAM CANDIDATES

These are clinically relevant, but they are poor baseline exposures unless there is a strong pre-episode definition:

- bicarbonate
- INR/PT/PTT
- blood gas glucose (item 50809)
- any acute inpatient measure that is expected to shift during illness

These are not “baseline risk-factor” candidates by default.

## D. EXCLUDE (FOR CURRENT FEASIBILITY REVIEW)

- lipid panel items 50903, 50904, 50905, 50906, 50907, 51000: not present in the current catalogue
- any candidate marker without stable pre-admission timing in the current file set

# 8. Lipid-specific review

This part is decisive for feasibility:

The project-specific lipid item IDs named in the task were:

- 50903 — cholesterol ratio
- 50904 — HDL
- 50905 — calculated LDL
- 50906 — measured LDL
- 50907 — total cholesterol
- 51000 — triglycerides

These are not present in `lab_coverage_catalogue.parquet`.

A direct query of the recovered catalogue returned zero rows for this exact set.

Conclusion: lipid analysis is NOT currently feasible from the recovered five-file bundle alone.

The only way to assess lipid feasibility is to extract timed rows from the raw MIMIC `labevents` table for the relevant itemids and then align them to baseline admissions.

The required extraction should include at minimum:

- `subject_id`
- `hadm_id`
- `itemid`
- `charttime`
- `value`
- `valuenum`
- `valueuom`
- `flag`
- `storetime` (if available)

The exact itemids still required are:

- 50903
- 50904
- 50905
- 50906
- 50907
- 51000

If lipid data are extracted, the next step is to determine:

1. how many cohort patients have each lipid
2. how many eligible baseline admissions have each lipid
3. what proportion are measured before baseline
4. what proportion are inpatient-only
5. whether enough coverage remains after the timing restriction to make a real epidemiologic candidate

At present, the answer is: not enough evidence, and the lipids are a data blocker, not a solved analysis feature.

# 9. Treatment feasibility review

The project already establishes the treatment branch as a prescription-window proxy problem, not a directly timed medication exposure problem.

The repo’s current authoritative treatment definition is approximately:

- `anchor_time = COALESCE(edregtime, admittime)`
- `window_before_start = max(previous_discharge_time, anchor_time - 7 days)`

The current candidate proxies are:

- `statin_before`
- `aspirin_before`
- `beta_blocker_before`
- `acei_before`

These are useful exposure proxies only for a screening analysis. They are not valid treatment-time-zero variables and they do not resolve incident-user vs prevalent-user status.

This means:

- prevalence can be discussed at a coarse window level
- effect estimation remains inappropriate
- a valid causal treatment question cannot be defined until a true treatment initiation time is resolved

The treatment branch is therefore not ready for final DAG work with the current file set.

# 10. Baseline-rule comparison

The key scientific choice is not whether a cohort exists; it is which baseline definition defines the target population.

The recovered data support comparison of the following rules:

| Rule | Eligible patients | Eligible admissions | Later MI patients | Scientific tradeoff |
|------|------------------|--------------------|------------------|--------------------|
| A. first non-MI admission | 174,055 | 174,055 | 5,774 | broadest and most inclusive, but allows heterogeneous risk and may capture patients with long pre-baseline disease histories |
| B. most recent non-MI before first MI | 4,857 | 4,857 | 4,857 | clinically coherent when a first MI is the event, but restricted to a specific subset |
| C. first non-MI with sufficient observability | 20,222 | 20,222 | 2,641 | good prospective structure, but sample loss and follow-up censoring are major |

The files do not automatically justify one final rule. Different rules answer different scientific questions.

# 11. Clinical branch verdict

CLINICAL BRANCH: CONDITIONALLY READY

Why this is still conditional:

- the longitudinal MI cohort is recoverable and coherent
- chronology checks are generally acceptable
- candidate factors are available with meaningful coverage
- the main barrier is that actual baseline timing is not yet established for most clinical variables

What is still missing before a final clinical causal design:

- exact pre-admission timing rules for candidate labs
- raw timestamped labevents for selected items
- confirmation that the chosen covariates precede the index event rather than acting as acute illness markers

# 12. Treatment branch verdict

TREATMENT BRANCH: NOT READY

Reason:

- current treatment variables are prescription-window proxies rather than true medication exposure time-zero variables
- no valid treatment initiation time is established in the current recovered bundle
- the exposure design requires raw medication-source validation before any causal conclusion

# 13. Data blockers

The major data blockers are:

1. no raw timed lab rows for the lipid panel
2. no direct validation of pre-admission vs inpatient lab timing for candidate baseline markers
3. no validated treatment initiation time for the medication exposures
4. no true outpatient medication source available from the recovered five-file bundle alone
5. OMR is date-only and is not enough to resolve same-day temporal ordering

# 14. Scientific decisions still required

Before a causal design is defensible, these decisions must be made:

- define the baseline admission rule
- define the exact time zero for the index event
- define the follow-up horizon and censoring rules
- define whether the analysis is first-event or recurrent-event based
- define a valid pre-exposure window for each candidate marker
- separate “clinical risk factor” from “treatment exposure” as distinct causal questions

# 15. Exact next data extraction required

If the project proceeds to the next phase, the exact additional data needed are:

## A. Raw lab events required for clinical baseline factors

Minimum extraction from `hosp/labevents.csv`:

- `subject_id`
- `hadm_id`
- `itemid`
- `charttime`
- `value`
- `valuenum`
- `valueuom`
- `flag`
- `storetime` (if available)
- any row-level `source` or `fluid` metadata available in the table

Required itemids for the highest-priority clinical path:

- Lipids: 50903, 50904, 50905, 50906, 50907, 51000
- Glycemia: 50852, 50931, 50809
- Renal: 50912, 51006
- Electrolytes: 50971, 50983, 50882, 50893, 50960
- Cardiac: 50963
- Hematology: 51221, 51222, 51301, 51265
- Inflammation: 50889

These rows are needed to determine:

- measurement before admission
- measurement after admission
- measurement during admission
- measurement after discharge

without which the analysis cannot validly label a factor as “baseline.”

## B. Raw medication data required for treatment branch

Minimum extraction from `hosp/prescriptions.csv` and, if needed, `emar.csv`:

- `subject_id`
- `hadm_id`
- `drug`
- `starttime`
- `stoptime`
- `dose_val_rx`
- `dose_unit_rx`
- `route`
- `ndc`
- any medication class mapping required to identify statins, aspirin, beta-blockers, ACE inhibitors

These data are needed to replace the current prescription-window proxy design with actual event-level medication timing.

# 16. Recommended next step

The current recovered files are useful for cohort definition, chronology checks, and candidate-factor screening, but they are not enough to proceed to a final causal design.

Recommended next step:

1. extract and time-align the relevant `labevents` rows for the candidate baseline labs and lipids
2. validate pre-admission vs inpatient timing using `charttime` and admission windows
3. keep the clinical and treatment questions conceptually separate
4. only after timing is resolved should the project choose a final baseline rule and proceed to a defensible exposure design

At present, the dataset supports a longitudinal feasibility review, not a final causal analysis.

---

Final scientific guardrail:

The project should not equate high coverage with baseline validity, nor association with causality. The next phase must be a timing check and cohort design exercise before any DAG, treatment effect, or final adjustment set is attempted.
