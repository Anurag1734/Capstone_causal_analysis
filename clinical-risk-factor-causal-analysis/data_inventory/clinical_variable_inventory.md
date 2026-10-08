# Clinical variable inventory

This inventory separates variables actually present in the current master
from candidates merely named in project/source documentation. No raw MIMIC
tables or extracted lab/vital files were found in the current project
workspace; source-table descriptions below are documentation, not local
availability.

## Current master

Master evidence is the three parquet splits under
`capstone2/master/`, 375,930 ECG rows across 191,369 admissions and 99,256
patients. The six non-ECG baseline candidates below have no missing values in
the admission-collapsed master audit. These are coverage facts in the
ECG-linked cohort, not coverage in a valid longitudinal at-risk population.

| Variable | Current source / semantics | Timestamp in master | Observed coverage and variation | Candidate role and timing caveat |
|---|---|---|---|---|
| `anchor_age` | Master demographics; age at admission per Phase F | None for source age calculation; admission anchor absent | 191,369/191,369 admissions nonmissing; 73 distinct observed values | Baseline confounder/prognostic factor candidate and possible effect modifier. Verify age is baseline-specific and identify its value date. Not a modifiable exposure itself. |
| `sex_male` | Master demographics | No timestamp; likely patient-level | 191,369/191,369; 2 values | Baseline confounder/prognostic candidate, not an intervention. Verify mapping and source. |
| `diabetes` | ICD-coded prior-admission comorbidity per Phase F | No diagnosis date or history cutoff in master | 191,369/191,369; binary with both values | Candidate baseline confounder/risk factor only if diagnoses were known before baseline time zero. Potential actionable condition, but this flag is not a specific intervention. |
| `hypertension` | ICD-coded prior-admission comorbidity per Phase F | No diagnosis date or history cutoff in master | 191,369/191,369; binary with both values | Same status as diabetes; timing and ascertainment completeness are unresolved. |
| `ckd` | ICD-coded prior-admission comorbidity per Phase F | No diagnosis date or history cutoff in master | 191,369/191,369; binary with both values | Baseline confounder/prognostic candidate if history is strictly pre-baseline. Does not substitute for timed renal-function measurements. |
| `prior_mi` | Had MI in a previous admission per Phase F | No source admission timestamp or cutoff in master | 191,369/191,369; binary with both values | Important baseline confounder candidate only if computed using history before baseline, not future admissions. Construction cutoff is unverified. |
| `is_MI` | Admission-level ICD-10 MI flag | No within-admission event time | 191,369 admissions; 7,362 positive | Outcome candidate only. Does not establish event time or subsequent MI by itself. |
| `Label_Troponin` | Cohort label derived from MI/troponin process | ECG/event-derived; do not treat as baseline | 375,930 rows; documented categories | Outcome/cohort metadata, not an independent causal outcome or exposure. |
| `index_mi_time` | First qualifying Acute_MI troponin event charttime, per pipeline documentation | Present for a subset of MI rows; not admission anchor | Present in master, but missing for many MI rows; not a universal endpoint time | Outcome-derived timing variable. Not a baseline exposure or covariate. |
| 95 engineered ECG features | ECG waveform processing | `ecg_time` exists, but no admission anchor or factor time ordering | Present for all master ECG rows per Phase F | ECG representation; predictive/physiological candidate, causal role unresolved. Quarantine from exposure and adjustment. |
| `z_ecg_1` … `z_ecg_64` | VAE embeddings of ECG | ECG timestamp can be linked in master, but measurement and training provenance incomplete | Present for all master ECG rows per Phase F | Predictive representation; not automatically mediator/confounder/outcome. Keep quarantined. |

## Potential clinical/lab/vital candidates (not in current master)

The source guide documents these potential candidates. It does not provide
verified item IDs, source extracts, candidate-specific coverage, distributions,
or eligible-baseline overlap in this workspace.

| Candidate | Documented MIMIC source | Source timestamp fields documented | Current master coverage | Likely baseline potential / downstream risk | Candidate role |
|---|---|---|---|---|---|
| LDL / other lipids | `hosp/labevents.csv`, mapped by `d_labitems.csv` | Lab `charttime`, `storetime` | Not present; historical `features_labs.csv` had 738 rows (<1% of master rows), source guide says dropped | Strong biological risk-factor candidate if a stable/pre-baseline result is available; acute testing may follow suspected MI, and lipid levels may be altered by illness/treatment. | Potential exposure only after timed coverage and intervention definition; currently timing unresolved. |
| Glucose | `hosp/labevents.csv` | `charttime`, `storetime` | Not present; aggregate lab extract reported <1% coverage | Chronic glycemia differs from stress hyperglycemia. Admission glucose may be measured after deterioration or influenced by acute MI. HbA1c, if available and correctly identified, may better represent antecedent glycemia. | Candidate only for pre-baseline/chronic measure; acute value likely downstream/prognostic. |
| Creatinine / eGFR, BUN | `hosp/labevents.csv` | `charttime`, `storetime` | Not present; aggregate lab extract reported <1% coverage | Chronic renal function can be a risk factor/confounder; inpatient values can reflect acute kidney injury, hemodynamic compromise, contrast, or treatment. eGFR is derived and requires age/sex plus assay/time policy. | Candidate only with stable pre-baseline definition; acute measurements are downstream/prognostic. |
| Potassium | `hosp/labevents.csv` | `charttime`, `storetime` | Not present; aggregate lab extract reported <1% coverage | Chronic dysregulation may be relevant, but acute results can reflect illness, renal dysfunction, medications, and resuscitation. | Timing unresolved; acute values primarily prognostic/downstream candidate. |
| BNP | `hosp/labevents.csv` | `charttime`, `storetime` | Not present; aggregate lab extract reported <1% coverage | Marker of cardiac strain/heart failure, commonly ordered because illness is suspected; may reflect pre-existing disease or acute MI severity. | Often prognostic/indication marker; only prior stable measurement could be baseline. |
| Blood pressure, BMI, weight, height | `hosp/omr.csv` | `chartdate` (date only), `result_name`, `result_value` | Not present; historical `features_vitals.csv` had 1,457 rows (<1%), then dropped | Outpatient measurements could support baseline physiology if dated before time zero. Same-day date without time creates ordering ambiguity; inpatient values often respond to acute state and treatment. | Potential exposure or confounder candidate if pre-baseline, otherwise timing unresolved/downstream. |
| Heart rate, blood pressure, SpO2, temperature, respiratory rate, rhythm | ICU `chartevents.csv`, dictionary `d_items.csv` | `charttime`, `storetime` | Not present in master; historical vitals extract had <1% coverage | High-frequency ICU values are usually recorded during severe inpatient illness and may follow MI suspicion, interventions, or deterioration. | Primarily acute severity/prognostic and treatment-affected; exclude from baseline exposure absent prior timing. |
| Troponin I/T | `hosp/labevents.csv`, mapped by `d_labitems.csv` | `charttime`, `storetime` | Some event timing reflected as `index_mi_time` | Direct input to the current MI temporal-label pipeline. | **Exclude as candidate exposure** due to outcome construction/leakage. |

### Coverage and variation conclusion

For the six present demographic/comorbidity fields, the current
ECG-linked master reports complete admission-level coverage and observed
variation. Their coverage in the actual eligible subsequent-MI cohort is
unknown. For all laboratory and vital candidates, master coverage is zero
because these values are not columns in the master. The historical extracted
lab and vital files were exceptionally sparse (<1% row coverage overall);
variable-specific coverage and meaningful exposure variation cannot be
recovered from documentation alone.

Continuous labs/vitals do not have a meaningful “positivity” assessment until
an intervention contrast (e.g., a clinically defined policy or range) and
eligible population are specified. Sparse observed tests may create selection
by indication as well as poor overlap.
