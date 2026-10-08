# ECG and `z_ecg` role analysis

## Current branch decision

Keep all 95 engineered ECG variables and all 64 `z_ecg` dimensions
**quarantined** from the clinical-factor exposure and adjustment set. This
branch does not alter or repeat the existing ECG/`z_ecg` audits.

The current master links ECG features and embeddings to `ecg_time`, but lacks
the admission anchor and timestamped clinical-factor measurements needed to
establish:

`clinical factor → ECG measurement → subsequent MI`

or whether a candidate ECG precedes the clinical factor, acute illness,
treatment, or outcome. The `z_ecg` role is additionally limited by incomplete
waveform/training/preprocessing provenance already documented in the separate
project.

## Hypotheses only

For a future design, the following are possible structures, not accepted
causal edges:

- a chronic risk factor may affect physiological state and ECG phenotype;
- ECG phenotype may mediate some effect on later MI;
- the clinical factor may also affect MI through pathways not represented by
  ECG;
- ECG may be a marker of pre-existing disease, an acute consequence, a
  mediator, a collider, or a predictor depending on measurement timing and
  selection.

No lab-to-ECG, ECG-to-MI, or `z_ecg` causal relationship is established by
predictive performance or the fact that features were derived from ECGs.

## Use conditions for later review

Before considering ECG variables for any causal role, establish the factor
measurement time, ECG time, baseline time zero, illness/event chronology, and
whether the ECG was acquired because of suspected MI. Then assess the ECG's
role for the specific estimand. Do not adjust for a mediator when targeting a
total effect; do not condition on a collider or outcome-affected ECG; do not
use an ECG after baseline as if it were a baseline confounder.

No ECG feature selection, latent-space reanalysis, DAG finalization, or causal
discovery was performed in this branch.
