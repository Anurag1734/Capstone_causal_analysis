# Phase Index

| Phase | Purpose | Main outcome | Status |
|---|---|---|---|
| Phase 1 | Audit the causal unit and temporal framework for the ECG/MI dataset. | Admission-level is the primary causal unit; repeated ECGs and repeated admissions are not treated as independent units. | Historical audit complete; key conclusions frozen. |
| Phase 2 | Audit treatment timing, clinical eligibility, and outcome/time semantics for the discovery question. | Rule-A ECG selection and treatment/outcome timing were reviewed; a final treatment-specific time zero remained unresolved. | Historical audit complete; causal timing unresolved. |
| Phase 3 | Audit baseline covariate provenance and eligibility. | Candidate baseline variables were assessed; `z_ecg` was not treated as a confirmed baseline confounder. | Historical audit complete; baseline role remains partially unresolved. |
| Phase 4 | Construct a discovery-ready dataset audit and provisional candidate layering. | Candidate rules A/B/C were documented; no final index ECG or final discovery matrix was approved. | Historical audit complete; discovery matrix blocked. |
| Phase 5 | Audit `z_ecg` provenance, representation, and causal role. | `z_ecg` dimensions exist and are complete, but provenance, training membership, and temporal eligibility remain unresolved. | Historical audit complete; `z_ecg` causal role remains unresolved. |
| Phase 6 | Encode background knowledge and causal constraints without claiming a discovered DAG. | A machine-readable constraint specification was built; it is background knowledge, not a final causal model. | Historical audit complete; constraint set exists but is not a final discovery result. |
| Phase 7 | Gate whether a defensible treatment-specific discovery analysis can proceed. | All four candidate treatments remain blocked because time zero, index ECG, and outcome definition remain unresolved. | Historical readiness gate complete; all treatments blocked. |

## Phase progression summary

- Phase 1 → causal unit / temporal framework
- Phase 2 → treatment / outcome audit
- Phase 3 → baseline covariate audit
- Phase 4 → discovery-ready dataset audit
- Phase 5 → `z_ecg` causal-role / provenance audit
- Phase 6 → background causal constraints
- Phase 7 → causal-discovery readiness gate
