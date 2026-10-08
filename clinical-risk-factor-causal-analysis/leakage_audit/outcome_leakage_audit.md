# Outcome leakage and acute-measurement audit

## Hard exclusion

**Troponin is not a candidate exposure or baseline covariate.** The current
cohort pipeline uses a qualifying troponin measurement to define
`index_mi_time` and MI-temporal labels. Troponin values and derivatives
therefore directly encode the outcome construction and are outcome/leakage
variables for the proposed subsequent-MI analysis.

`is_MI` remains the admission-level ICD-10 outcome flag. `Label_Troponin` is
cohort-label metadata, not an independent causal endpoint. `index_mi_time` is
the first qualifying Acute_MI troponin charttime per project pipeline
documentation; it is not true biological onset and not a baseline exposure.

## Candidate measurements by leakage/timing risk

| Variable family | Leakage / temporal risk | Current treatment |
|---|---|---|
| Troponin I/T and troponin-derived summaries | Directly involved in event timing/labeling; may be collected because MI is suspected or after injury begins. | Exclude from candidate exposures and baseline adjustment. |
| Admission glucose, creatinine, potassium, BNP, CBC and similar labs | May be ordered due to symptoms or acute deterioration; may reflect MI physiology, renal injury, stress response, contrast, or treatment. | Do not treat as baseline solely by source/table. Require actual timestamp and antecedent clinical window. Often acute prognostic/downstream candidate. |
| ICU vitals / hemodynamic measures | Typically charted during hospitalization/ICU after illness recognition; can be effects of MI, shock, or treatment. | Exclude from baseline exposure absent evidence of pre-event measurement. |
| OMR outpatient BP/BMI | Potentially antecedent, but measurement may be same-day/date-only, selected by care access, and affected by earlier treatment. | Candidate if dated before baseline and context/units verified. |
| BNP, stress glucose, acute renal-function measures | Often reflect acute state or suspicion; can be downstream or common response to severity and care. | Treat as acute severity/prognostic variables unless pre-baseline evidence establishes otherwise. |
| `index_mi_time`, `time_diff_hours`, `Label_Troponin` | Outcome-derived timing/label fields. | Never use to define baseline exposure or as ordinary confounders. |
| `is_MI` on baseline admission | Baseline outcome status. | Exclude baseline MI admissions for a first subsequent-event design; do not use future MI to select baseline. |
| Future-admission labs, vitals, diagnoses, and treatments | Post-baseline and may be consequences of event/clinical care. | Prohibit in baseline covariates/exposure definitions. |
| During/after treatment variables | May be mediators, treatment responses, colliders, or downstream of baseline risk. | Keep out of baseline adjustment by default; role would need a separate time-indexed design. |

## Selection through testing

Laboratory measurements are not missing at random by default. A patient may
be tested because a clinician suspects MI or because comorbidity/clinical
severity prompts testing. Restricting to patients with a measured candidate
biomarker may condition on healthcare contact or clinical suspicion and induce
selection bias. The audit must report who is tested, when, and in what care
setting, not only value distributions among tested patients.

## Required controls before any analysis

1. Use specimen/measurement time (`charttime` where available), not only
   database entry time (`storetime`).
2. Exclude measurements after baseline time zero and address ambiguous
   same-day ordering.
3. Distinguish pre-existing chronic measurements from admission/acute
   measurements and use no outcome-derived time to choose the measurement.
4. Keep baseline covariates restricted to information available by baseline.
5. Audit measurement indication and coverage to evaluate testing-selection
   bias.

No filtering or lag is chosen here; clinical experts must justify any
separation period.
