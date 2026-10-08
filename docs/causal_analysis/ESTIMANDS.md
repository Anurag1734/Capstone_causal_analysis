# Phase 0 estimand specification foundation

This document is a working specification for the treatment-specific estimands that must be defined before any DAG construction or causal discovery. It is intentionally conservative and does not claim that any treatment is currently estimable.

## General principle

A treatment-specific estimand requires a justified causal time zero, a valid index ECG, and a clearly defined outcome and follow-up horizon. If those cannot be established from the available data, the estimand stays unresolved rather than being assumed.

## Candidate primary treatments

The current project explicitly prioritizes the following candidate treatments:

- `statin_before`
- `aspirin_before`
- `beta_blocker_before`
- `acei_before`

The following should not be treated as baseline primary candidates without additional justification:

- `vasopressor_during`
- `mech_vent_during`
- `statin_after`
- any treatment measured during the admission as an acute intervention likely downstream of the clinical severity process

## Required estimand fields

For each candidate treatment, the analysis must document:

- target population
- treatment/exposure
- control condition
- causal time zero
- outcome
- outcome horizon
- estimand
- intervention interpretation
- inclusion/exclusion criteria

## Current status by treatment

### 1. statin_before

Target population:
- Not yet finalized; likely admission-level patients eligible for pre-admission baseline treatment modeling

Treatment/exposure:
- `statin_before` indicator in the master dataset

Control condition:
- `statin_before == 0`

Causal time zero:
- Unresolved. The current variable is a window-coded flag, not a timestamped medication administration record.

Outcome:
- MI outcome not yet finalized; current project uses `is_MI` and `Label_Troponin`, but their causal role requires explicit definition and temporal justification.

Outcome horizon:
- Unresolved

Estimand:
- Unspecified until time zero and index ECG are justified

Intervention interpretation:
- Not valid yet, because exposure timing cannot be linked to a defensible treatment assignment time

Inclusion/exclusion criteria:
- Not yet finalized

### 2. aspirin_before

Target population:
- Unknown; requires treatment-specific eligibility review

Treatment/exposure:
- `aspirin_before`

Control condition:
- `aspirin_before == 0`

Causal time zero:
- Unresolved

Outcome:
- Unresolved

Outcome horizon:
- Unresolved

Estimand:
- Not yet valid

Intervention interpretation:
- Not valid until exact timing and temporal ordering are documented

### 3. beta_blocker_before

Target population:
- Unknown; requires treatment-specific eligibility review

Treatment/exposure:
- `beta_blocker_before`

Control condition:
- `beta_blocker_before == 0`

Causal time zero:
- Unresolved

Outcome:
- Unresolved

Outcome horizon:
- Unresolved

Estimand:
- Not yet valid

### 4. acei_before

Target population:
- Unknown; requires treatment-specific eligibility review

Treatment/exposure:
- `acei_before`

Control condition:
- `acei_before == 0`

Causal time zero:
- Unresolved

Outcome:
- Unresolved

Outcome horizon:
- Unresolved

Estimand:
- Not yet valid

## Required documentation before estimand approval

The following must be explicitly established before any treatment-specific estimand can be approved:

1. exact treatment timing or a documented reason why exact timing is unavailable
2. a valid causal ECG selection rule
3. a valid treat-before-ECG temporal ordering
4. an accepted MI outcome definition and horizon
5. a defensible eligible cohort definition
6. treatment positivity and overlap checks

## Formal conclusion for Phase 0

At this stage, the project has a master dataset and historical audit artifacts, but it does not yet have a valid treatment-specific estimand for any candidate treatment. This is a design blocker, not a modeling issue.
