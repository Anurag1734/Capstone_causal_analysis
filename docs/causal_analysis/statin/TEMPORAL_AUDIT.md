# Statin temporal audit

## Scope

This document evaluates whether the current `statin_before` exposure can support a defensible treatment-specific causal design. It does not estimate treatment effects and it does not assume the answer is yes or no.

## Executive summary

The current project data support a binary pre-admission statin prescription flag, but not a precise statin treatment-time zero. The exact medication timing is not established in the current master dataset or in the available project documentation.

Therefore the relevant classification is:

- exposure definition: available
- treatment time zero: not established
- pre-treatment ECG ordering: not established
- status: NOT READY for treatment-specific DAG design

## Observed time variables

The master dataset includes the following relevant fields:

- `ecg_time`
- `admission anchor` / `anchor_time` conceptually from the MIMIC cohort logic
- `index_mi_time`
- `time_diff_hours`

The key design problem is that the current master table lets us observe an ECG timestamp and an MI event timestamp, but it does not provide a validated prescription-level treatment assignment timestamp for each `statin_before` flag.

## Source timeline logic

The project documentation indicates a medication-provenance chain like this:

- patient admission occurs
- prior discharge defines a pre-admission boundary
- prescription records in the prior period are considered
- any qualifying statin prescription in a recent window yields `statin_before = 1`

This is a valid feature-engineering rule for prediction, but it is not sufficient for a causal treatment-time zero.

## Time-zero candidates considered

### Candidate A: earliest qualifying statin prescription in the pre-admission window

Status: theoretically observable in `prescriptions.csv` if a starttime exists, but not guaranteed to represent treatment assignment.

Problems:

- could be a continuing medication, not a new initiation
- could reflect prescription before a clinically relevant period rather than treatment assignment
- may not align with the causal question for the selected ECG
- may not be comparable across patients with different prescription histories

### Candidate B: prescription start time

Status: observable only if the exact source record includes `starttime`, but still not a validated treatment-assignment time.

Problems:

- it is a prescription time, not necessarily drug administration or uptake
- may be recorded long before the relevant ECG or clinical event
- may encode prevalent-user status rather than causal initiation

### Candidate C: prescription end time

Status: may exist in `stoptime`, but not a defensible treatment assignment time.

Problems:

- it is after the treatment period and may be influenced by ongoing clinical management
- it is also not a true intervention start time

### Candidate D: admission anchor time

Status: not a valid causal treatment-time zero for statin exposure.

Problems:

- the anchor time is a hospital time boundary, not a medication start time
- using the anchor as the treatment time would conflate exposure with hospital-entry timing rather than treatment assignment

### Candidate E: no defensible time zero from current data

Status: the most defensible conclusion from the current evidence.

Reason:

- the dataset only records a window indicator, not the exact treatment assignment time
- we do not know whether the drug was actually taken, filled, or active before the ECG

## Why the current time zero is not defensible

A valid causal time zero generally requires a treatment assignment or initiation moment that is:

- clinically interpretable
- observed in the source data
- temporally ordered before the selected ECG
- not defined using the outcome
- not selected after seeing the outcome or MI timing

The current `statin_before` indicator fails these criteria because it is a historical prescription-window flag derived from MIMIC-IV medication rows, not a point treatment time. It therefore cannot define a reliable treatment-specific causal design.

## Treatment-time-zero takeaway

The best supported conclusion is:

- `statin_before` is a summary indicator of recent pre-admission statin exposure.
- It is not sufficient to define a treatment-specific causal time zero.
- There is no defensible treatment-time-zero candidate that is both source-supported and clinically interpretable from the current master dataset alone.

## Outcome timing implications

The project uses `index_mi_time`, `time_diff_hours`, and labels such as `MI_Acute_Presentation` and `MI_Pre-Incident` to construct the temporal cohort. However, these fields are outcome-defined and cannot be used to recover an exact pre-admission statin treatment time without circularity.

In other words:

- MI timing cannot be used to justify the statin treatment time zero
- the treatment variable must be defined independently of the MI event
- the current `statin_before` feature is not independent enough to serve as a causal exposure definition in the presence of temporal ambiguity

## Temporal design verdict

`statin_before` is NOT READY for a treatment-specific causal design because the current data support only a recent-prescription indicator, not a validated treatment initiation or assignment time.
