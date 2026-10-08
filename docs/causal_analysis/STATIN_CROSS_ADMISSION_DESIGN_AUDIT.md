# Statin cross-admission design audit

**Decision: C. NOT VIABLE with the currently available master data.**

This is a descriptive design audit only. No master data were modified; no DAG,
causal-discovery analysis, propensity scores, matching, IPW, ATE/CATE, or other
effect estimation was performed. The within-admission design remains closed
as not viable.

## 1. Question under evaluation

The proposed longitudinal question is:

> Among patients with an eligible baseline admission, what is the effect of
> having a qualifying pre-admission statin prescription during that baseline
> admission's prescription window on the risk of a subsequent
> MI-coded hospital admission?

The exposure is the existing `statin_before` indicator, interpreted only as a
qualifying prescription/order in the frozen approximately 7-day pre-admission
window dynamically bounded by the previous admission discharge:

`window_before_start = max(prev_discharge_time, anchor_time - 7 days)`

`anchor_time = COALESCE(edregtime, admittime)`

This is not confirmed outpatient use, adherence, treatment initiation, or
chronic therapy. The future outcome admission must not contribute any
information to this baseline exposure.

## 2. What the current master establishes

The audit read the three current master parquet splits and collapsed repeated
ECG rows by `hadm_id`. The resulting descriptive structure is:

| Current-master fact | Count |
|---|---:|
| ECG rows | 375,930 |
| Unique patients (`SubjectID`) | 99,256 |
| Unique admissions (`hadm_id`) | 191,369 |
| Admissions with `is_MI == 1` | 7,362 |
| Admissions with `is_MI == 0` | 184,007 |
| Admissions with `statin_before == 1` | 13,203 |
| Admissions with `statin_before == 0` | 178,166 |
| Patients with more than one admission represented | 34,625 |
| Maximum admissions represented for one patient | 72 |
| Patients with at least one represented MI admission | 6,239 |
| Patients with more than one represented MI admission | 819 |
| Maximum represented MI admissions for one patient | 9 |

`is_MI` and `statin_before` were internally consistent across the repeated
ECG rows within each admission in this audit. Those facts allow admission and
patient linkage, but they do not establish admission order or incident
follow-up.

### Required chronology is absent

The current master schema has `ecg_time` and `index_mi_time`, but does not have
`anchor_time`, `edregtime`, `admittime`, or `dischtime`. The MIMIC admissions
and diagnosis source tables needed to recover all admissions, their times, and
outcomes are not available in the current workspace. Project documentation
describes those upstream sources, but documentation is not a substitute for
the records needed to perform the requested joins.

`ecg_time` is not a defensible substitute for admission time or discharge
time. The audit did not order admissions by ECG timestamp, infer discharge
from ECGs, or use `final_index_time`. Further, the master is an ECG-linked
modeling cohort, not a verified census of every hospital admission and
diagnosis during follow-up.

Consequently, it is not possible from the available source data to determine
which represented admission is earlier, whether a distinct later admission
exists, or the time from baseline discharge to that later admission.

## 3. Baseline admission rule evaluation

| Candidate rule | Assessment |
|---|---|
| **A. Any admission followed by a later admission** | Not recommended. Eligibility would depend on future admission, select patients with observed recurrent care, permit multiple baselines per person, and create within-person dependence. It cannot be evaluated without admission chronology. |
| **B. Non-MI baseline followed by later MI** | Reject as the cohort-entry rule. Requiring a future MI selects on the outcome and provides no valid denominator for estimating subsequent risk. A later MI should be the outcome, not an inclusion criterion. |
| **C. First eligible admission per patient** | **Preferred design rule if required source data become available.** Select one pre-specified first eligible non-MI baseline admission per patient, without requiring any later admission or MI. Start follow-up after baseline discharge. This avoids repeated baseline entries and defines a clear temporal origin. It still requires ascertainment of complete prior admission history to implement the prescription-window boundary and eligibility correctly. |
| **D. Other rule: sequential risk-set baseline** | A sequence of eligible non-MI admissions could be used only with a repeated-measures target-trial design and explicit handling of treatment history and patient dependence. It adds complexity and is not justified for the first design. |

Rule C is selected for its interpretation and protection against
outcome-conditioned cohort entry, not for sample size. Its number of eligible
patients or admissions cannot be calculated from the current files.

## 4. Candidate longitudinal specification (not executable yet)

If the complete admission/diagnosis sources become available, the most
defensible initial specification to evaluate would be:

- **Population entry:** patients with a first eligible baseline admission in
  the defined observation cohort, whose baseline admission has `is_MI == 0`.
  Entry must not require a subsequent admission or MI.
- **Baseline admission:** the first eligible non-MI admission per patient under
  a prespecified observation and history rule. The baseline admission itself
  cannot count as the outcome.
- **Exposure:** that baseline admission's `statin_before` value, with the
  frozen seven-day, previous-discharge-bounded window and the stated
  prescription/order interpretation.
- **Follow-up start:** baseline `dischtime`; this follows the baseline
  exposure window and avoids counting an MI-coded baseline admission as a
  later outcome. It does not remove potential indication or reverse-causality
  bias arising before/during the baseline admission.
- **Outcome:** the first distinct later admission for the same patient with
  the unchanged `is_MI == 1` outcome.
- **Follow-up end:** ideally end of complete MIMIC admission ascertainment,
  death, or other clearly defined loss of observation, whichever occurs
  first. The observation end and death fields are not available in the
  current master, so neither dates nor censoring can be implemented here.
- **Event timing:** time from baseline discharge to the first subsequent
  MI-coded admission, calculated from actual admission timestamps. Do not
  invent a fixed follow-up horizon.

Among the offered choices, following from baseline discharge until the end of
available admission observation, with the first subsequent MI-coded admission
as the event, is the most coherent candidate. Death should be treated as a
competing event rather than silently assumed independent censoring. The data
must also establish whether admissions outside the ECG-linked master are
captured; otherwise “no MI admission” cannot be interpreted as an observed
event-free follow-up.

“Until next admission” alone would answer a narrower question about the next
recorded admission and miss a later MI after an intervening non-MI admission.
A fixed horizon is not supported by the current data and must not be invented.

## 5. Requested longitudinal counts and prevalence

The available counts are marginal counts over all admissions represented in
the master, not counts in the proposed eligible longitudinal cohort:

| Requested quantity | Result |
|---|---|
| Eligible patients | Not computable: no admission chronology, complete admission roster, or baseline eligibility can be constructed. |
| Eligible baseline admissions | Not computable for the same reason. |
| Exposed eligible baseline admissions/patients | Not computable. The 13,203 exposed admissions above are all represented admissions, not eligible baselines. |
| Unexposed eligible baseline admissions/patients | Not computable. The 178,166 unexposed admissions above are all represented admissions, not eligible baselines. |
| Subsequent MI events | Not computable: `is_MI` rows cannot be ordered after baseline discharge. The 7,362 count is total represented MI admissions, not incident follow-up events. |
| Patients with subsequent MI / without subsequent MI | Not computable: follow-up start, end, and full outcome ascertainment are unavailable. |
| Time from baseline discharge to subsequent admission | Not computable: `dischtime` and later `admittime` are absent. |
| Event rate by baseline exposure | Not computable and not estimated. |
| Patients with multiple eligible baseline admissions | Not computable. The preferred first-baseline-per-person rule would cap this at one by design, but actual eligibility cannot be identified. |
| Patients with multiple subsequent MI admissions | Among all admissions represented in the master, 819 patients have more than one MI-coded admission. This is not restricted to eligible baseline patients or to follow-up after an eligible baseline. |

These limitations are not repaired by the marginal exposure and outcome counts;
comparing them would not estimate a cross-admission event rate.

## 6. Temporal bias and leakage checks

The necessary temporal checks cannot be executed at the admission level because
the admission and discharge timestamps are absent. The design rule, if
implemented with full sources, would require all of the following:

1. Confirm `baseline_admittime < outcome_admittime` and
   `baseline_dischtime < outcome_admittime` using actual admission records.
2. Compute baseline exposure only from the baseline admission's
   pre-admission window, ending at its `anchor_time`; never read exposure from
   the future outcome admission.
3. Exclude a baseline admission with `is_MI == 1`; count only MI on a distinct
   later admission as the primary event.
4. Select baseline without looking ahead for later MI or later treatment.
5. Do not use future admission covariates, treatments, ECGs, diagnosis
   metadata, or labels as baseline predictors.
6. Establish a complete observation end and handle death/other end of
   observation without treating unobserved outcomes as “no MI.”

The current master cannot certify these conditions. No future-admission
information was used to create any computed exposure or outcome count in this
audit.

## 7. Baseline covariate feasibility

Only fields from the selected baseline admission could be candidate baseline
covariates. They must be verified to be measured at or before the baseline
exposure window, and no values from a later MI admission may be carried
backward.

| Candidate variable | Longitudinal interpretation and current limitation |
|---|---|
| `anchor_age` | Use age recorded/calculated for the baseline admission, not the future event admission. Confirm that the master value is admission-specific. |
| `sex_male` | Patient attribute likely time-invariant; use baseline patient record. Verify source semantics and handle missing/unknown states correctly. |
| `diabetes`, `hypertension`, `ckd` | Use baseline-row values only if their coding is based solely on history available by baseline. Current documentation calls them prior-admission comorbidities, but the construction code/history cutoff is unavailable; no temporal guarantee is established. |
| `prior_mi` | Must mean MI history before the baseline admission, never a flag recalculated using the future outcome admission. Current schema describes previous-admission MI history, but source construction and cutoff are not available to confirm this for the selected baseline. |
| ECG-derived features and `z_ecg` | Remain quarantined. No ECG or latent feature is needed to establish admission chronology, and their baseline temporal eligibility/provenance remains unresolved. |
| Identifiers | `SubjectID`/`subject_id` and `hadm_id` are for linkage and repeated-patient handling, not adjustment covariates. |

Even if these six candidate covariates are correctly timed, they are not
plausibly sufficient by themselves to control confounding.

## 8. Identification concerns

- **Confounding by indication:** cardiovascular risk and clinical indication
  influence statin prescription and later MI. The six listed variables do not
  capture dyslipidemia, atherosclerotic burden, established coronary disease
  comprehensively, heart failure, smoking, frailty, or clinical decision
  context.
- **Healthy-user/access bias:** prescription documentation and healthcare
  contact may reflect access, follow-up, adherence-related behaviors, and
  comorbidity management not measured in the master.
- **Prior cardiovascular disease:** `prior_mi` and comorbidities could help
  only if strictly cut off at baseline and accurately measured. Future MI
  information must not enter these baseline values.
- **Recurrent-admission dependence:** 34,625 patients have multiple admissions
  represented, and 819 have multiple MI-coded admissions. Repeated rows are
  not independent. A one-baseline-per-patient design is preferred; recurrent
  outcome events require a defined first-event or recurrent-event estimand.
- **Treatment-history carryover:** `statin_before` is not initiation. Prior
  treatment before the defined window, continuing prescription history, and
  treatment after baseline may affect outcome. The binary flag does not
  identify these trajectories.
- **Informative censoring and competing risk:** death, end of available data,
  and loss of observable hospital contact may be associated with exposure and
  MI. Current master data do not provide follow-up end/death information.
- **Selection bias:** the master is ECG-linked and does not verify a complete
  admission/outcome roster. Requiring a later admission would select on future
  healthcare utilization. Conditioning on baseline being non-MI may also
  define a population distinct from all admissions, which should be stated.
- **Positivity:** 13,203 of 191,369 represented admissions are exposed
  (6.90%) overall, but conditional overlap in first eligible non-MI baselines
  cannot be assessed. Sparse exposure strata may occur after restrictions.
- **Covariate sufficiency:** the six candidates alone are unlikely to suffice
  for exchangeability. Residual confounding is substantial even if
  temporality is reconstructed.

## 9. Final decision and next step

### Decision: C. NOT VIABLE with the currently available data

The cross-admission concept has a clearer temporal interpretation than the
rejected within-admission design, and a first eligible non-MI baseline
admission followed from discharge is a defensible *candidate* rule. But the
available master lacks admission and discharge times and is not a complete
hospital-admission outcome roster, so it cannot identify which exposure
precedes which later MI admission, calculate follow-up/censoring, or provide
the requested eligible cohort counts. Further, baseline covariate cutoffs and
complete future outcome ascertainment are unverified; therefore this is not
ready for DAG finalization.

**Most defensible alternative research question with the current master:**
“Among ECG-linked admissions represented in the master, how does the
admission-level `statin_before` prescription-window flag co-occur with the
admission-level ICD-10 MI flag?” This is a descriptive admission-level
association only; it does not establish temporal direction or a causal effect.

**Recommended next step:** do not estimate. If the longitudinal causal
question remains the goal, first make the complete admissions and diagnosis
records available for all relevant observation time, then construct and audit
the patient-level chronology and baseline eligibility counts before
considering a DAG.
