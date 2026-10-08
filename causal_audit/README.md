# Causal Audit Workspace

This directory contains the historical causal-audit work for the ECG/MI project. It is a research and handoff workspace, not the active SCM project repository.

The files here are organized to preserve the audit trail from Phase 1 through Phase 7 without mixing it into the live preprocessing or modeling pipeline.

## Scope

This workspace is intentionally limited to:

- causal unit and temporal framework auditing
- treatment/outcome and eligibility review
- baseline covariate checks
- discovery-ready dataset audit
- `z_ecg` provenance and causal-role review
- background causal constraints
- discovery-readiness gate assessment

It is not the active:

- ECG feature extraction pipeline
- current SCM preprocessing
- VAE training pipeline
- final causal effect estimation workflow

## Phase progression

The work is organized as a staged audit sequence:

- Phase 1: causal unit and temporal framework
- Phase 2: treatment and outcome audit
- Phase 3: baseline covariate audit
- Phase 4: discovery-ready dataset audit
- Phase 5: `z_ecg` causal-role and provenance audit
- Phase 6: background causal constraints
- Phase 7: causal discovery readiness gate

## Workspace separation

The top-level workspace keeps the following separate:

- `causal_audit/`: historical causal methodology audit artifacts
- `00_dataset_audit/`: dataset-level verification material
- `master/`: master dataset-related artifacts
- `docs/`: project documentation
- `capstone_dag_roadmap.pdf` and `capstone_dag_roadmap_final.pdf`: roadmap history retained at the workspace root

## Roadmap files

The roadmap PDFs remain at the workspace root because they document the project history rather than a phase-specific audit artifact.

- `capstone_dag_roadmap.pdf`: original roadmap draft
- `capstone_dag_roadmap_final.pdf`: final roadmap version

The final version supersedes the earlier draft, but both are preserved for traceability.

## Important caution

The historical audit files here are intentionally frozen snapshots. They should not be rewritten to match later repository discoveries. If new facts arise, they should be documented in `CURRENT_STATUS.md` rather than altering the historical record.
