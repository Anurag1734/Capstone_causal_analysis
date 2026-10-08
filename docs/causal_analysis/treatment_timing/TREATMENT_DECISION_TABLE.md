# Treatment decision table across the four primary candidate exposures

## Objective

Assess whether each candidate treatment is temporally defensible for future causal design and whether any can satisfy the core no-DAG gate: a valid treatment time zero and a guaranteed pre-treatment ECG ordering.

## Decision criteria

A treatment is candidate-ready only if all of the following are satisfied:

1. source provenance is known and documented
2. treatment time zero is clinically meaningful and supported by source data
3. the measurement window for the ECG can be guaranteed to precede treatment
4. the design can distinguish prevalent user vs new-user therapy
5. the exposure is not merely a recent-prescription indicator

## Table

| Treatment | Source provenance | Treatment-time zero | ECG-before-treatment feasible? | New-user viability | Overall status |
|---|---|---|---|---|---|
| `statin_before` | prescription source; current master variable appears to encode recent pre-admission prescription status | not defensible; current variable is not a validated initiation time | no, not with current design | not established | NOT READY |
| `aspirin_before` | prescription source; current master variable appears to encode recent pre-admission prescription status | not defensible; current variable is not a validated initiation time | no, not with current design | not established | NOT READY |
| `beta_blocker_before` | prescription source; current master variable appears to encode recent pre-admission prescription status | not defensible; current variable is not a validated initiation time | no, not with current design | not established | NOT READY |
| `acei_before` | prescription source; current master variable appears to encode recent pre-admission prescription status | not defensible; current variable is not a validated initiation time | no, not with current design | not established | NOT READY |

## Interpretation

At this stage, none of the four candidate primary treatments is temporally ready for downstream DAG construction or causal discovery.

The common reason is structural rather than incidental:

- the available exposure variables summarize recent medication status, not treatment start time
- source provenance is not yet transformed into a valid time-zero representation
- the timing between ECG and treatment cannot be guaranteed for the existing features
- no treatment has been shown to support a stable new-user or incident-user design

## Required next step before any DAG work

The project must identify a valid medication source and define a true treatment time zero before considering any causal graph or discovery algorithm. Only a treatment that can satisfy this design requirement should enter the DAG phase.
