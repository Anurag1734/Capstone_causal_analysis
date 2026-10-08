# Medication source inventory for candidate treatments

## Scope

This audit inventories the medication-related data sources that are relevant to the primary candidate treatments:

- `statin_before`
- `aspirin_before`
- `beta_blocker_before`
- `acei_before`

It is a source audit for medication temporal design only. It does not build a DAG or estimate effects.

## Core finding

The local project documentation and source inventory support two distinct medication-source layers:

1. Prescription/order layer
   - `hosp/prescriptions.csv`
   - captures medication orders and prescription metadata
   - provides timestamps such as `starttime` and `stoptime`
   - does not by itself prove treatment administration

2. Administration layer
   - `hosp/emar.csv` and `hosp/emar_detail.csv`
   - capture medication administration events
   - provide actual administration timing and per-administration details
   - are the best available source for a treatment administration or treatment-start design

The local repository documentation explicitly describes these tables and distinguishes them functionally. The prescription layer is the current basis for the `*_before` variables, but the administration layer is the most relevant place to look for a defensible causal exposure time.

## Source inventory

### 1. `hosp/prescriptions.csv`

Meaning:
- medication prescription / order records

Identifiers:
- `subject_id`
- `hadm_id`
- `pharmacy_id`
- `poe_id`
- `poe_seq`
- `order_provider_id`

Relevant timestamps:
- `starttime`
- `stoptime`

Relevant fields:
- `drug_type`
- `drug`
- `route`
- `dose_val_rx`
- `dose_unit_rx`
- `form_rx`
- `form_val_disp`
- `form_unit_disp`
- `doses_per_24_hrs`

Interpretation:
- good for medication ordering history
- not equivalent to administration
- not a validated treatment assignment time

Usefulness for current main exposure:
- this is the source that underlies the current `*_before` binary flags

### 2. `hosp/emar.csv`

Meaning:
- electronic medication administration record (actual administration log)

Identifiers:
- `subject_id`
- `hadm_id`
- `emar_id`
- `emar_seq`
- `poe_id`
- `pharmacy_id`
- `enter_provider_id`

Relevant timestamps:
- `charttime`
- `scheduletime`
- `storetime`

Relevant fields:
- `medication`
- `event_txt`

Interpretation:
- records actual administration or administration status
- `event_txt` can indicate administered, held, refused, or other states
- this is the strongest candidate source for actual treatment administration timing

Usefulness:
- best opportunity to define a real treatment-start or treatment-receipt time if the admission and medication family are linkable

### 3. `hosp/emar_detail.csv`

Meaning:
- detailed per-administration data

Identifiers:
- `emar_id`
- `subject_id`
- `hadm_id`
- `pharmacy_id`
- `poe_id`

Relevant timestamps:
- administration event timing embedded in the EMAR record structure

Relevant fields:
- dose, route, site, infusion rate and related administration specifics

Interpretation:
- provides granular actual administration metadata
- useful for confirming whether an administration was delivered and how it was administered

Usefulness:
- important for confirming the actual administration event and dose details

### 4. `hosp/pharmacy.csv`

Meaning:
- pharmacy dispensation records

Identifiers:
- `subject_id`
- `hadm_id`
- `pharmacy_id`
- `poe_id`

Relevant timestamps:
- `starttime`
- `stoptime`

Relevant fields:
- `medication`
- `proc_type`
- `status`
- `route`
- `frequency`
- `infusion_type`
- `duration`

Interpretation:
- useful for linking order-to-dispensation or preparation records
- can help understand whether a drug was dispensed, but it is not necessarily the same as administration

### 5. ICU input records (`icu/inputevents.csv`)

Meaning:
- i.v. fluid and medication inputs to the ICU

Identifiers:
- `subject_id`, `hadm_id`, `stay_id`, `orderid`

Relevant timestamps:
- `starttime`, `endtime`

Interpretation:
- relevant for acute infusion-type medications and ICU interventions
- not a general outpatient medication source
- useful for emergency medication administration timing in the inpatient context

### 6. `hosp/admissions.csv`

Meaning:
- hospital admission registry

Relevant identifiers:
- `subject_id`, `hadm_id`, `admittime`, `dischtime`, `edregtime`, `edouttime`

Interpretation:
- essential for linking medication records to a current admission
- used to define pre-admission windows and current-admission medication timing

### 7. `patients.csv`

Meaning:
- patient-level demographics

Relevant variables:
- `subject_id`, `anchor_age`, `sex`, `anchor_year`

Interpretation:
- useful baseline covariate information, but not a medication timestamp source

## Availability conclusion

The local project documentation supports the presence of both prescription and administration data. Specifically:

- prescription source: available and used in the current `*_before` feature logic
- administration source: available in the raw MIMIC-IV data model as `emar.csv` and `emar_detail.csv`
- linkage to patient/admission: supported by `subject_id` and `hadm_id`

The project’s active master dataset does not currently expose the administration timestamps in a way that defines the treatment-time zero for the four primary candidate exposures. This means the data source exists, but the temporal design has not yet been reconstructed from it.
