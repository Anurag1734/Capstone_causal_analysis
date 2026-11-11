# Phase 16 final scientific decision

## Decision: C — endpoint or data limitations prevent a meaningful treatment-effect comparison

The statin branch closes as a feasibility and exploratory analysis. The saved Phase 11–12 estimates may be retained transparently as exploratory model results, but no effect estimate is approved as a substantive or causal result for the paper.

Why:

1. The broad 1,833-event MI-coded outcome includes 1,339 ICD-9 `412`-only admissions, which do not establish acute recurrent infarction. The acute screen finds 555 candidate admissions, but 211 “candidate distinct” classifications are based on code/chronology screening without clinical adjudication; 344 remain classified as possible transfer/readmission, possible continuation, or uncertain.
2. The treatment contrast is recorded statin exposure during the index hospitalization, not initiation at discharge. A valid first in-admission administration timestamp is retained for 1,500 of 2,986 already-exposed admissions; the other 1,481 unmatched exposed admissions cannot be reclassified as untreated.
3. Treatment is missing for 2,889 of 7,545 eligible patients. Known-treatment follow-up and feature selection reduce the Phase 11 population to 3,230; only 499 form its held-out complete-case test set.
4. Baseline imbalances and strong clinical indication/confounding are plausible, while lipid burden, coronary disease burden, clinician indication, validated prior medication use, and prior MI severity are unavailable or inadequately timed. No measured adjustment set establishes conditional exchangeability.
5. Death is a competing event; incomplete follow-up is unknown, and same-day event ordering requires explicit handling. The saved Phase 13 acute-screen output contains no event-order-uncertain rows, but endpoint uncertainty remains.

## What can be reported

Report the cohort-construction, treatment linkage, endpoint screening, competing-death, missingness, and descriptive baseline findings as a feasibility study. Preserve previous model estimates in a clearly labeled exploratory appendix/table only, with their original endpoint and sample definition. Do not claim a clinical treatment benefit/harm, causal effect, discharge-initiation effect, adherence effect, or treatment-effect heterogeneity.

No Phase 17 or further statin investigation is proposed in this closure.
