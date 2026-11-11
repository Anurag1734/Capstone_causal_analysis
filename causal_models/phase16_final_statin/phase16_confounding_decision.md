# Phase 16 confounding and adjustment decision

## Causal question and treatment definition

The intended scientific question remains statin treatment and later/recurrent MI among patients with prior MI. The available exposure is the existing `statin_during` indicator: recorded in-hospital exposure versus no recorded exposure in the index admission. It is not a discharge-initiation strategy, a new-user contrast, or long-term adherence. Its assignment time relative to the beginning of follow-up and to evolving index-stay severity is not uniformly available.

## Proposed adjustment set

For a future, explicitly timed treatment assignment, the DAG-supported primary set would need pre-assignment age, sex, chronic disease burden (including diabetes, hypertension, CKD), prior cardiovascular disease and prior MI severity/recency, **verified prior statin use**, pre-assignment concomitant cardiovascular treatment, lipid burden, and clinical treatment indication / baseline severity. This is a target specification, not a claim that the current data measure it.

Available measured candidates are age, sex, diabetes, hypertension, and CKD. The comorbidity feature time windows are not fully validated against the first dose. If a future assignment timestamp establishes they predate treatment, they can be retained as baseline candidates. The `*_before` variables for statin, aspirin, beta blockers, and ACE inhibitors are order/prescription proxies: they do not prove administration, adherence, or the exact historical window. Use them only in a clearly labeled sensitivity specification, not as verified medication history.

The existing DAG represents prior statin use as a confounder but flags `statin_before` as an imperfect proxy that may be a collider of prior statin use and healthcare access/documentation. Therefore do **not** make the proxy the primary adjustment variable by default; show results with and without it only if a future analysis has a defensible assignment time and endpoint.

## Excluded from baseline adjustment

- Index admission diagnosis codes (acute MI, heart failure, shock, AKI, respiratory failure) and completed length of stay: timing relative to administration is unavailable; they may be post-treatment severity, mediators, or colliders.
- `statin_after`, follow-up, recurrent-MI outcomes, death, and post-dose treatment: post-treatment/outcome variables.
- `statin_during`: exposure, not a covariate.
- `prior_mi`: constant eligibility variable in this selected cohort; no within-cohort adjustment information.
- `z_ecg` and other ECG-derived features: temporal/provenance eligibility is unresolved and should not be used as baseline adjustment.

## Confounding by indication and exchangeability

There is measured imbalance: CKD prevalence is 35.1% treated versus 27.8% control (SMD 0.156); diabetes, hypertension, and age also differ. Prior medication-order proxies show larger group differences, with uncertain timing and adherence. Index-admission diagnosis-code prevalence and length of stay differ too, but cannot be used as primary baseline adjustment because they are not timed before statin administration. These patterns are compatible with treatment selection by disease history, indication, and acuity; they do not quantify or eliminate confounding.

Important residual confounders are not adequately measured: lipid burden, coronary anatomy/atherosclerotic burden, prior MI severity and validated episode history, clinician indication, frailty, smoking, reliable prior medication use/adherence, and healthcare access. Selection into a prior-MI survivor, ECG/master-feature, known-treatment, and complete-follow-up population may also induce selection bias.

**Decision:** conditional exchangeability is not plausible enough to assert from the retained data. No primary causal adjustment set is fully observed and temporally validated. The measured-only set may be used for descriptive balance or exploratory models, not to justify a causal estimate.
