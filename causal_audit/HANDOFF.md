# Handoff Note

This workspace is a separate audit/research workspace for the ECG/MI causal-analysis effort. It is not the main SCM repository, and it is not intended to be copied wholesale into the main project.

The purpose of this directory is to preserve the audit record, keep the causal methodology work organized, and make it easier for the main repository maintainer to selectively integrate only the relevant pieces later.

## 1. What I completed

- Organized the historical Phase 1-7 work into a clear `causal_audit/` structure.
- Kept the dataset audit and master-related materials separate from the causal methodology archive.
- Preserved the original historical Phase 1-7 artifact files without rewriting or “repairing” their conclusions.
- Created a concise set of handoff documents:
  - `README.md`
  - `PHASE_INDEX.md`
  - `CURRENT_STATUS.md`
  - `HANDOFF.md`
- Reviewed the roadmap PDFs and preserved both the original and final versions while documenting that the final document supersedes the earlier draft.
- Assessed the notebook-builder script and retained it as a phase-1 artifact rather than deleting it blindly.
- Removed clearly disposable cache artifacts (`__pycache__`) without deleting protected historical files.

## 2. What files belong to each phase

- `causal_audit/phase1/` — causal unit and temporal framework audit artifacts
- `causal_audit/phase2/` — treatment and outcome audit artifacts
- `causal_audit/phase3/` — baseline covariate audit artifacts
- `causal_audit/phase4/` — discovery-ready dataset audit artifacts
- `causal_audit/phase5/` — `z_ecg` provenance and causal-role audit artifacts
- `causal_audit/phase6/` — background causal constraints artifacts
- `causal_audit/phase7/` — causal discovery readiness gate artifacts

## 3. Important verified findings

- The historical audit consistently points to admission-level as the primary causal unit.
- Repeated ECGs and repeated admissions are common enough that they cannot be treated as independent causal units.
- The main active SCM preprocessing pipeline uses SubjectID-level splitting with zero train/validation/test SubjectID overlap.
- The current preprocessing pipeline fits winsorization, transformations, and scaling only using training data.
- The input pipeline dimension reduction was verified as 160 columns to 95 ECG features after excluding SubjectID.
- Phase 7 concluded that all candidate treatment discovery questions are blocked because the required causal design inputs are not established.
- `z_ecg` remains a quarantined latent block whose causal role is unresolved unless provenance and timing are established.

## 4. Important unresolved issues

- Treatment-specific causal time zero remains unresolved.
- Final index ECG selection remains unresolved.
- Outcome definition and post-treatment horizon remain unresolved.
- ECG temporal eligibility relative to treatment remains unresolved.
- `z_ecg` provenance and training lineage remain unresolved.
- The exact 192 → 160 feature transition has not been fully traced in this workspace unless additional evidence exists elsewhere.
- Any final discovery or causal estimation claim would be premature without resolving these issues.

## 5. What should NOT be assumed

- Do not treat the historical audit files as if they are the current SCM implementation.
- Do not assume the causal audit directory is the active project codebase.
- Do not assume `z_ecg` is a baseline confounder or valid causal covariate without explicit timing and provenance evidence.
- Do not assume the final discovery matrix has already been validated.
- Do not assume the historical results should be rewritten to match later observations; instead, record new understanding in `CURRENT_STATUS.md`.
- Do not copy the entire audit workspace into the main SCM repository wholesale.

## 6. What the next person should inspect

- The current SCM preprocessing pipeline for split strategy, feature retention, and leakage control.
- The original VAE model/training artifacts and checkpoint provenance for `z_ecg`.
- The exact treatment timestamp logic, including any medication time fields or pre-admission definitions.
- The final outcome definition, event labeling, and follow-up horizon for MI.
- The final index-ECG rule and whether it is causally valid relative to treatment.
- Any upstream ECG preprocessing and feature-transformation scripts that the historical audit could not verify locally.

## 7. Which artifacts should eventually be copied or referenced in the main repository

Only the pieces that are directly useful to the main SCM repository should be selectively integrated. Examples include:

- the final validated causal design decision record
- the final treatment-specific time-zero specification
- the final index-ECG rule once it is established
- any final outcome definition and horizon decision
- any provenance or leakage audit notes that are relevant to the project’s reproducibility documentation

The historical audit artifacts should remain traceable as research history, but they should not be merged in bulk into the main repository without curation.

## Summary

This is a preserved audit archive for causal-methodology work, not an active repository fork. The key responsibility for the next person is to integrate only the validated, final causal design pieces into the main SCM codebase while leaving the historical audit snapshots intact.
