# Current Status

This document records the current state after the Phase 1-7 audit work and the later SCM preprocessing inspection. It is intended to distinguish the frozen historical audit record from the present working understanding.

## A. Completed and verified

- The current SCM preprocessing pipeline uses SubjectID-level splitting.
- Train/validation/test SubjectID overlap is zero.
- Winsorization is fitted using training data only.
- Transformations are fitted using training data only.
- Scaling is fitted using training data only.
- The current SCM preprocessing input contains 160 columns.
- Exactly 64 features are removed.
- 96 columns remain including SubjectID.
- Therefore 95 ECG model features remain after excluding SubjectID.
- The 160 → 95 feature reduction is verified.
- The Phase 1 audit concluded that the primary causal unit is admission-level.
- Repeated ECGs are not automatically independent causal units.
- Multiple admissions per patient exist.
- Patient dependence must be considered.
- Historical Phase 1-7 materials remain in place as frozen audit artifacts.
- Phase 7 explicitly concluded that all treatment-specific discovery questions remain blocked because the causal design inputs are not established.

## B. Previously unresolved but now clarified

- The primary causal unit is admission-level rather than patient-level or ECG-level.
- Repeated ECGs within the same admission and repeated admissions within the same patient are not independent causal observations.
- The Phase 1/4 judgment that `SubjectID` must be retained for dependence handling is consistent with the current preprocessing split design.
- The current preprocessing pipeline does fit some transformations using only training data, which is important for leakage control in the active pipeline.
- The 160 → 95 reduction is a verified count-based fact in the current SCM preprocessing pipeline; this should be treated as a present pipeline fact, not as a causal discovery result.

## C. Still unresolved

- Treatment-specific causal time zero remains unresolved unless explicitly established.
- Final index ECG remains unresolved unless explicitly established.
- Outcome definition and horizon remain important causal-design issues.
- ECG temporal eligibility relative to treatment remains unresolved.
- `z_ecg` should not automatically be treated as a baseline confounder.
- `z_ecg` causal role remains unresolved unless timing and provenance establish it.
- The exact 192 → 160 transition has not yet been fully traced in this workspace unless other evidence is present.
- There is no verified final selection rule for a causal ECG index.
- There is no verified final treatment-specific exposure timing for the current discovery questions.
- The outcome provenance and event horizon remain unresolved in the causal design sense.

## D. Blockers for causal discovery

- No final treatment-specific time zero.
- No final index ECG rule.
- No final outcome definition/horizon that is causally justified.
- No verified temporal eligibility for engineered ECG features or `z_ecg`.
- No confirmed `z_ecg` provenance from the underlying VAE/training pipeline.
- Model performance or statistical association is not evidence of causal role.
- Statistical causal discovery must not be treated as causal truth.

## E. Recommended next step

1. Establish the treatment-specific causal time zero and the treatment-assignment timing logic.
2. Define the final outcome variable and the follow-up horizon explicitly.
3. Resolve which ECG observation is the valid causal index ECG for each treatment question.
4. Confirm the provenance of `z_ecg`, including training split membership and any leakage from future or post-outcome ECGs.
5. Reconcile the preprocessing pipeline facts with the historical audit materials without rewriting the scientific history.
6. Only then construct a treatment-specific discovery matrix and proceed to a justified causal analysis.

## Bottom line

The historical audit work establishes a careful, frozen record of unresolved causal-design issues. The current SCM preprocessing facts clarify leakage-control behavior in the active pipeline, but they do not by themselves resolve the causal questions that remain blocked in the audit.
