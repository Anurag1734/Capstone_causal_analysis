# Exposure provenance across all primary treatments

## Objective

This document traces the current provenance of the four candidate primary treatments in the master dataset:

- `statin_before`
- `aspirin_before`
- `beta_blocker_before`
- `acei_before`

## High-level conclusion

All four current treatment variables appear to be built from the same class of source data: MIMIC-IV medication prescriptions. They are admission-level, binary, window-coded indicators that summarize recent medication prescribing activity in the pre-admission period. They are not yet validated treatment assignment or initiation times.

## Common construction pattern

Based on the project documentation, the common workflow is:

1. pull medication records from `hosp/prescriptions.csv`
2. identify qualifying drug families by name or class
3. restrict to a pre-admission window relative to the current admission anchor
4. aggregate to a binary per-admission indicator
5. store as `*_before`

This pattern is consistent across the candidate exposures and explains why their current causal interpretation is limited.

## Treatment-specific provenance

### 1. statin_before

Source:
- `hosp/prescriptions.csv`

Identification logic:
- statin class via drug-name matching, including names such as atorvastatin, simvastatin, rosuvastatin, pravastatin, lovastatin, fluvastatin, pitavastatin

Temporal logic:
- recent prescription in a pre-admission window relative to anchor time

Interpretation:
- recent statin prescription indicator
- not necessarily new-user or initiation indicator
- not a validated administration timestamp

### 2. aspirin_before

Source:
- `hosp/prescriptions.csv`

Identification logic:
- medication-name matching for aspirin and aspirin-containing combinations as supported in the prescription source

Temporal logic:
- pre-admission recent prescription window

Interpretation:
- recent aspirin prescription indicator
- does not define treatment assignment time

### 3. beta_blocker_before

Source:
- `hosp/prescriptions.csv`

Identification logic:
- medication-name/class matching for beta blockers (e.g., metoprolol, atenolol, propranolol, carvedilol, bisoprolol, etc.)

Temporal logic:
- recent prescription in the pre-admission window

Interpretation:
- recent beta-blocker prescription indicator
- not a valid treatment initiation time without additional evidence

### 4. acei_before

Source:
- `hosp/prescriptions.csv`

Identification logic:
- medication-name/class matching for ACE inhibitor drugs (e.g., lisinopril, enalapril, captopril, ramipril, etc.)

Temporal logic:
- recent prescription in the pre-admission window

Interpretation:
- recent ACE inhibitor prescription indicator
- not a verified time-zero variable

## Common limitation across all four

The design limitation is shared across all candidate primary treatments:

- the current variables are summary prescription indicators
- they do not equal actual treatment administration
- they do not encode a validated treatment start or initiation time
- they do not ensure the selected ECG occurred before the treatment under study
- they mix prevalent-use and recent-use patterns without distinguishing new vs continuing therapy

## Comparison across treatments

| Treatment | Current exposure meaning | Best source | Administration data available? | Best current time concept | Causal time zero status |
|---|---|---|---|---|---|
| statin_before | recent pre-admission statin prescription | `prescriptions.csv` | potentially via `emar.csv`, not yet linked into the master design | prescription starttime if available | unresolved |
| aspirin_before | recent pre-admission aspirin prescription | `prescriptions.csv` | potentially via `emar.csv`, not yet linked into the master design | prescription starttime if available | unresolved |
| beta_blocker_before | recent pre-admission beta-blocker prescription | `prescriptions.csv` | potentially via `emar.csv`, not yet linked into the master design | prescription starttime if available | unresolved |
| acei_before | recent pre-admission ACE inhibitor prescription | `prescriptions.csv` | potentially via `emar.csv`, not yet linked into the master design | prescription starttime if available | unresolved |

## Critical conclusion

The master dataset does not yet expose a unified, validated treatment-time framework for the four candidate exposures. Prescription timestamps exist in the source data, but they are not currently used to define a treatment assignment time in a way that is causal and defensible.
