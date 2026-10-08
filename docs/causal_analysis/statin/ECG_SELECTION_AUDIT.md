# Statin-specific ECG selection audit

## Purpose

This audit evaluates whether there exists a defensible ECG selection rule that is guaranteed to be before the statin treatment time zero. The current evidence does not support such a guaranteed rule.

## Candidate ECG rules reviewed

### Rule 1: earliest ECG in admission

Status: operationally available, but not treatment validated.

What it does:

- selects the first valid ECG timestamp per admission
- can be implemented without using the treatment variable or outcome variable

Why it is not sufficient:

- it does not guarantee that the ECG occurred before the treatment-under-study
- if the patient was already on statin therapy before the admission or had a recent prescription, the first ECG may still occur after the relevant exposure or after the medication was prescribed
- it does not reflect a treatment-specific time zero

### Rule 2: latest ECG before treatment

Status: not usable without a valid treatment-time zero.

Why it is blocked:

- we do not have a verified treatment time to define the "before" cutoff
- selecting an ECG based on an undefined treatment time would be circular and non-defensible

### Rule 3: first ECG before treatment

Status: blocked for the same reason as Rule 2.

### Rule 4: ECG closest to treatment from before

Status: blocked because treatment time is undefined.

### Rule 5: MI-relative ECG timing

Status: outcome-dependent and not valid for a treatment-specific baseline rule.

Why it fails:

- it uses outcome timing (`index_mi_time`) to choose the ECG
- this is valid only for a post hoc label definition, not a treatment-specific baseline exposure design
- it is unsuitable for controls and not generalizable to a causal pre-treatment design

## What can be concluded

A valid baseline ECG rule for statin exposure would require:

- a valid treatment time zero
- an ECG timestamp that is definitely before that treatment time
- no use of future outcome or MI timing to define the selection rule

Because the treatment time zero is unresolved, there is no defensible index-ECG rule that can currently be considered valid.

## Implications for ECG representations

The candidate representations include:

- 95 engineered ECG features
- 64 `z_ecg` variables

These are only valid as ECG representations if the selection rule ensures the ECG is before treatment. Without that guarantee:

- the engineered ECG features are temporally unresolved
- the `z_ecg` block is temporally unresolved
- neither can be treated as validated baseline variables for the statin design

## Final ECG audit verdict

The statin-specific design does not currently have a valid pre-treatment index ECG. The only available operational rule is the earliest ECG in an admission, but this is not a causal baseline rule and cannot be accepted as pre-treatment evidence without treatment timing.
