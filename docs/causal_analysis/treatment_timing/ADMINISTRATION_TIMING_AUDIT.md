# Medication administration timing audit

## Objective

Evaluate whether an actual medication administration source exists and whether it can support a defensible treatment time for the four primary treatments.

## Source inventory and meaning

The project documentation identifies the following medication source layers:

- `hosp/prescriptions.csv` — prescription/order records
- `hosp/emar.csv` — actual admin log
- `hosp/emar_detail.csv` — granular administration data
- `hosp/pharmacy.csv` — dispensation/preparation records
- `icu/inputevents.csv` — ICU infusion events

This means the project does have a medication-administration layer in the underlying MIMIC-IV data model. The key design question is not whether the data exist in principle, but whether they are available and reliable enough to be linked to the current admission cohort and used to define a treatment-specific causal time zero.

## Critical distinction

The following are not the same:

- a prescription order timestamp
- an administration timestamp
- a time of first drug receipt
- a time of active drug effect
- a treatment assignment time

For causal design, only the most source-validated and clinically interpretable of these can serve as a candidate time zero. The current master variables are not that.

## What the administration layer can offer

If linked correctly, EMAR records can provide:

- a medication name
- a timestamp of administration
- administration status and route
- dose information
- event-level confirmation of actual drug receipt

This is the strongest available information for identifying treatment initiation or drug receipt after admission, especially for inpatient or active hospital treatment.

## What the administration layer does not automatically provide

Even with EMAR data, the following remain nontrivial:

- whether the medication was active long before the admission
- whether the treatment is chronic ongoing therapy rather than new therapy
- whether the patient was on home therapy before admission
- whether the patient was dispensed medication but did not consume it
- whether the patient’s baseline ECG was measured before the administration event

## Treatment-by-treatment administration feasibility

### statin

Potentially feasible if EMAR data are linked to the relevant drug names for statin medications. But this would capture administered medication during the admission, not necessarily home prescription or baseline therapy.

Interpretation:
- if a statin is administered during the current hospitalization, this is not a baseline causal exposure for an admission-level pre-treatment ECG design
- if a pre-admission statin prescription exists but no actual admin record is available, the treatment remains a prevalent-user or recent-prescription exposure, not a clean causal design

### aspirin

Potentially feasible via EMAR if aspirin administration is recorded on the admission. This still reflects inpatient medication usage and may be confounded by the clinical event.

Interpretation:
- aspirin administration during admission is not the same as a pre-admission baseline exposure
- in-hospital administration may be downstream of severity and therefore not a base cause of the current MI outcome

### beta blockers

Potentially feasible via EMAR or ICU input events depending on drug class and route. Beta blockers are often given acutely in cardiovascular management.

Interpretation:
- if the administration occurs after or during acute care, it may be part of acute treatment rather than baseline exposure

### ACE inhibitors

Potentially feasible through EMAR or prescription records, but again strongly affected by clinical indication and inpatient context.

Interpretation:
- pre-admission ACE inhibitor prescription history may not reflect genuine baseline exposure timing
- no clean new-user design is guaranteed without additional source data and filtering

## Current conclusion

The raw MIMIC-IV architecture includes a credible medication administration layer, but the project’s master dataset has not yet reconstructed a treatment-specific time-zero from that layer. Therefore:

- available administration evidence: yes, in the underlying source data model
- usable clinical causal treatment time in the current cross-treatment design: not established

This is not a data-availability failure; it is an unresolved temporal-design problem.
