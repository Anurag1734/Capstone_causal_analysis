# Candidate causal questions and estimands

**No final causal question or estimand is selected.** A baseline biomarker
association is not automatically a causal effect: one must specify a
well-defined intervention or policy on the factor and a valid longitudinal
population.

## Candidate formulations

### 1. Baseline risk-factor intervention (causal target, conditional)

> Among patients eligible at a defined baseline, what is the effect on risk of
> a subsequent MI-coded admission of a specified, clinically implementable
> strategy that achieves or maintains a target range for factor X, compared
> with a specified alternative strategy?

Potential X: blood-pressure control, glycemic management, lipid level
management, or renal-risk management. This is compatible with a causal
question only after defining eligibility, intervention versions, baseline
measurement, co-interventions, follow-up, outcome ascertainment, and
adjustment strategy. It estimates the effect of a strategy, not necessarily a
unit change in a lab number.

### 2. Baseline abnormality contrast (possible but not automatically causal)

> Among patients with a valid pre-baseline measurement of X, what is the
> subsequent MI risk under a defined clinically abnormal X range versus a
> defined reference range?

This is a candidate contrast if thresholds are clinically justified and
measurement precedes time zero. It is not causal merely because it is framed
as an abnormality comparison: versions of treatment, confounding, selection
into testing, measurement error, and reverse causality remain.

### 3. Pre-baseline biomarker and subsequent MI (descriptive/prognostic)

> Among patients with a recorded pre-baseline X measurement, how is the last
> eligible X value associated with a later MI-coded admission?

This is a feasible descriptive/prognostic question if source data establish
timing and follow-up. It should not be described as a causal effect without a
defensible intervention and identification argument. It may be the smallest
bridge analysis for assessing data coverage and temporal ordering.

## Potential first candidates (not selected)

- Outpatient or otherwise stable pre-baseline blood pressure: potentially
  actionable via a treatment/monitoring policy, but `omr.chartdate` is
  date-only and timing/coverage are unverified.
- Antecedent lipid measure: clinically meaningful and potentially actionable,
  but no values are in master, coverage is unknown, and the intervention is
  not simply “set LDL.”
- Antecedent chronic glycemia (`HbA1c` if available): distinguish chronic
  glycemia from acute stress glucose; no local item-level availability or
  coverage evidence.
- Stable pre-baseline renal function: potentially a risk marker or management
  target, but inpatient creatinine can be acute kidney injury and treatment-
  affected.

## What current data support

The current master alone supports neither a biomarker causal estimand nor a
subsequent-MI outcome. It can describe admission-level demographic and
comorbidity fields in an ECG-linked cohort, but has no lab/vital values,
admission chronology, or complete event follow-up. The causal question is
therefore not yet compatible with the available analytic files.

## Estimand fields still required

- Target population and eligibility that do not condition on future MI.
- Baseline factor measurement and clinical intervention contrast.
- Time zero and evidence that measurement precedes it and outcome risk.
- Subsequent MI-coded admission definition and ascertainment completeness.
- Follow-up horizon or defensible end-of-observation rule; do not invent one.
- Competing death, loss of observation, and recurrent event handling.
- Sufficient pre-exposure confounders, including factors driving measurement
  and clinical testing.

This document does not finalize a DAG, adjustment set, or estimator.
