# Phase 8 - Causal Question

## Status

**Design status: NOT READY for causal effect estimation.** This document defines a provisional target question and records why the current workspace cannot yet support an intervention-level statin estimand.

## Target question under evaluation

> Among patients entering an eligible first non-MI baseline hospital admission, what would be the effect of assignment to a qualifying statin strategy during a prespecified baseline period on the risk of a first distinct subsequent MI-coded hospital admission?

The wording is intentionally stronger than the currently observed data. The observed `statin_before` field cannot currently operationalize the word "assignment".

## Candidate exposure definitions

| Candidate | Exposure contrast | Time zero and window | Outcome and follow-up | Causal interpretation | Current support |
|---|---|---|---|---|---|
| A. Recent prescription window | `statin_before = 1` versus `0`, defined from a qualifying prescription/order in the documented approximately 7-day pre-admission window bounded by prior discharge | Window is approximately `max(previous_discharge, anchor_time - 7 days)` through `anchor_time`, where `anchor_time = COALESCE(edregtime, admittime)`; the exposure window end is not itself a verified treatment assignment time | First distinct later admission with `is_MI = 1`; ideally follow from baseline discharge to observation end, death, or first event | At most an association with a recent recorded prescription pattern. Not an intervention on taking or initiating statin | **Available as a master indicator; not causally interpretable without further validation** |
| B. In-hospital recorded administration | A qualifying EMAR administration before a prespecified cutoff versus no such administration | Requires exact `emar.charttime`, a clinically justified administration window, and eligibility before treatment; current audit did not link EMAR to ECG | Requires an outcome after the treatment cutoff, not the current admission event unless the event is demonstrably subsequent | Could represent an acute inpatient treatment strategy, but is highly vulnerable to confounding by acute indication and reverse causation | **Not supported as a baseline treatment; potentially reconstructable only after targeted design work** |
| C. New-user initiation | First qualifying statin administration or assignment among patients with no prior use, versus no initiation | Requires reliable prior treatment history, a verified initiation/assignment time, and a common eligibility time | First subsequent MI admission after initiation, with explicit competing death handling | Most clinically interpretable treatment-effect question among the candidates | **Not established; current `statin_before` is a prevalent/recent-use flag** |
| D. Baseline prescription strategy | A prespecified order strategy at baseline, with follow-up beginning after the assignment window | Requires a source-defined assignment rule and exclusion of patients already on therapy if a new-user interpretation is intended | First distinct subsequent MI-coded admission after the strategy window | A possible target-trial emulation, but only if order timing, prior use, eligibility, and follow-up are reconstructed | **Not currently identified** |

## Provisional population and longitudinal structure

If the required source artifacts are recovered and validated, the preferred initial population is one baseline admission per patient: the first eligible non-MI admission under a prespecified observation/history rule. Eligibility must not depend on a future MI, future admission, or future treatment. The baseline admission itself is not a subsequent outcome.

The documented design preference is to begin follow-up after baseline discharge. This prevents an MI coded during the baseline admission from being counted as a later event and creates a clean boundary after the prescription window. It does **not** solve treatment assignment ambiguity within the pre-admission window, indication bias, or missing adherence.

The primary outcome candidate is the first distinct later admission for the same patient with `is_MI = 1`, rather than the next admission. A later MI after an intervening non-MI admission must remain observable. Follow-up ends at the first subsequent MI, death, the end of complete admission observation, or another prespecified censoring event. Death should be treated as a competing event for a risk-of-MI estimand, not silently treated as independent censoring.

## Candidate estimands

- **Preferred future estimand:** the intention-to-treat-like effect of assignment to a clearly specified statin initiation or prescription strategy at baseline on the cumulative incidence of first subsequent MI by a prespecified horizon.
- **Possible but weaker estimand:** the contrast in subsequent MI risk associated with `statin_before = 1` versus `0` among eligible baseline admissions. This is an associational prescription-pattern contrast, not the effect of statin use, receipt, adherence, or initiation.
- **Not supported:** the effect of taking statin, active drug exposure, or treatment initiation from the current master alone.

## Required assumptions for a causal estimand

A causal interpretation would require well-defined treatment versions, consistency, exchangeability conditional on measured pre-treatment history, positivity, correct temporal ordering, complete or appropriately handled outcome/follow-up ascertainment, and a defensible censoring/competing-risk strategy. In particular, a prescription order cannot be treated as administration, and an EMAR event cannot automatically be treated as initiation.

## Decision

The most defensible Phase 8 decision is to retain the cross-admission question as a **design hypothesis**, not an approved estimand. The current data support a limited descriptive or associational analysis of a recent pre-admission prescription indicator only after the longitudinal cohort is actually reconstructed and validated. They do not support ATE/CATE estimation or a claim about the causal effect of statin treatment.

## Unresolved assumptions

- The machine-readable admission chronology, MI-admission table, and observation-end files described by the longitudinal audit are absent from the current workspace.
- The `medication_timestamp_audit` folder contains the report, script, and summary CSV, but the named parquet outputs are absent from the workspace search; the report says the ECG-linked output had zero rows because no ECG input was supplied.
- No treatment initiation time or complete prior medication history is established.
- `is_MI` is an admission-level diagnosis indicator, not yet a validated incident clinical MI endpoint for this estimand.
- Prescription-window construction, patient eligibility, treatment history, and outcome ascertainment require source-level validation before analysis.
