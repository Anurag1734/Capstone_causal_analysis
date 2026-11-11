# Phase 16 manuscript notes

## Proposed title

**Feasibility of Estimating the Association Between In-Hospital Statin Exposure and Subsequent Myocardial Infarction in Patients With Prior MI: A MIMIC-IV Cohort Assessment**

## Research question and design

Assess whether existing MIMIC-IV/MIMIC-IV-ECG data support an interpretable analysis of in-hospital statin exposure and subsequent MI-coded admissions among patients with a prior MI. This is a retrospective, single-health-system data-feasibility and exploratory observational analysis, not a target-trial emulation with validated treatment assignment.

## Cohort and exposure

The retained eligible cohort contains 7,545 patients with a prior MI who survived the selected index admission to discharge. `statin_during` is the existing index-hospitalization exposure indicator. Treatment was known for 4,656 (2,986 exposed; 1,670 controls) and missing for 2,889. Phase 14 linked filtered statin EMAR records to 1,505 exposed admissions; a valid in-admission first administration time was available for 1,500. Order records and administrations remain distinct; neither inpatient administration nor prescription orders establish discharge therapy or outpatient adherence.

## Outcome and statistical methods

The saved Phase 11 analysis used a 12-month MI-coded recurrence outcome in a complete-case cohort; its final held-out test set contained 499 patients. Phase 13 screened acute-coded subsequent admissions (ICD-9 `410*`, ICD-10 `I21*`/`I22*`) and treated death as a competing event; Phase 14 categorized 555 candidate admissions using diagnoses and chronology. No clinical episode adjudication was available. Descriptive competing-risk cumulative incidence estimates are unadjusted. Phase 11–12 effect estimates are historical exploratory results only; Phase 16 did not fit models or re-estimate effects.

## Results to report

- Cohort: 7,545 eligible; 4,656 known treatment; 2,889 treatment missing.
- Of 2,986 existing exposed admissions, 1,505 have a filtered EMAR link; 1,481 are unmatched, not untreated. First timestamp in the admission is available for 1,500.
- Broad endpoint: 1,833 MI-coded admissions, including 1,339 ICD-9 `412`-only cases. Acute-code screen: 555 candidates; 211 candidate distinct, 167 possible transfer/readmission, 114 possible continuation, 63 uncertain.
- Known-treatment complete-case population: 3,230; held-out test sample: 499.
- Treated/control imbalances include CKD 35.1% versus 27.8% (SMD 0.156). Prior medication fields are order proxies with uncertain timing/adherence.
- Existing model estimates are in `phase16_paper_assets/final_estimates.csv`; all are explicitly exploratory and not causal.

## Limitations and claim boundaries

The exposure is not discharge initiation; treatment status is missing for many eligible patients; EMAR linkage is incomplete; a distinct recurrent infarction endpoint is not adjudicated; treatment indication and important severity/lipid/coronary variables are missing or poorly timed; complete-case and ECG/master selection may limit generalizability; and death competes with recurrent MI. The analysis does not support a clinical causal effect or heterogeneity claim.

Supported claims: these files contain an eligible cohort, an existing in-hospital exposure indicator, incomplete linked timestamped administration evidence, and acute-code-screened candidate admissions with episode uncertainty.

Claims not supported: statin initiation at discharge caused a change in MI risk; prescription or inpatient administration proves long-term adherence; any candidate is a confirmed new MI without adjudication; or CATE variability establishes effect heterogeneity.

## Suggested abstract structure

1. **Background:** the need to assess data suitability for medication-effect analyses in prior-MI patients.
2. **Objective:** evaluate exposure linkage, endpoint screening, confounding, and selection for an in-hospital statin comparison.
3. **Methods:** describe the retained cohort and prior Phase 11–15 evidence; distinguish orders, administrations, competing death, and incomplete follow-up.
4. **Results:** give cohort counts, EMAR linkage, endpoint screening categories, observed imbalances, and selection into the 499-person held-out estimate sample.
5. **Conclusion:** state that the study supports a feasibility/exploratory description, not a causal treatment-effect conclusion.

## External verification still required

Verify clinical interpretation of ICD coding, MIMIC-IV/MIMIC-IV-ECG dataset descriptions, and prior literature using appropriate external sources before manuscript submission. No external references or clinical guideline claims are supplied here.
