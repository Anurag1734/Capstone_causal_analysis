# Phase 16 completion report

## Work completed

- Finalized endpoint disposition and documented competing death, incomplete follow-up, episode uncertainty, and same-day event ordering.
- Assessed confounding, indication, adjustment candidates, prior statin proxy DAG role, and selection/missingness.
- Made final decision C: feasibility/exploratory study only; no causal estimate is approved as a substantive paper result.
- Created paper tables and figures. Existing Phase 11–12 estimates are copied as exploratory only; no new model or effect estimate was generated.

## Existing artifacts reused

Phase 11 saved metrics and test-set model results; Phase 12 robustness estimator table; Phase 13 target-trial report, cohort selection, acute endpoint event types and competing-risk CIFs; Phase 14 exposure timestamps, linkage summary, first administration summary and episode classifications; Phase 15 group comparisons and selection flow; existing cohort and patient-level splits; provisional statin DAG.

No raw EMAR/prescription files were searched or re-extracted. No Phases 1–15 outputs, cohort, treatment indicators, splits, or models were modified.

## Final counts and decisions

- Cohort: 7,545; known treatment 4,656 (2,986 treated, 1,670 controls); treatment missing 2,889.
- Phase 14: 1,505 EMAR-linked exposed admissions; 1,500 valid first in-admission timestamps; 1,481 exposed admissions without a qualifying EMAR link.
- Phase 11 complete-case population: 3,230; held-out complete-case test: 499.
- Endpoint: 555 acute-coded candidates; 211 candidate distinct, 167 possible transfer/readmission, 114 possible continuation, 63 uncertain; not clinically adjudicated.
- Confounding: measurable imbalances and important unmeasured/poorly timed indication factors; exchangeability not supported.
- Selection: missing treatment, EMAR linkage absence, and incomplete follow-up retained as distinct mechanisms.
- Final scientific decision: **C — feasibility/exploratory study only**.
- Causal estimate approved for substantive paper presentation: **No**. Prior estimates are retained as exploratory outputs only.

## Reproducibility and tests

Run the Phase 16 artifact builder from the repository root:

```powershell
.\.venv\Scripts\python.exe -m causal_models.phase16_final_statin.analyze_phase16
```

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m unittest causal_models.phase16_final_statin.test_phase16 -v
```

Input validation confirmed treatment counts, Phase 11 complete-case counts, split patient disjointness (`none`), 1,500 in-window first administration timestamps, and retained acute-screen categories. The focused Phase 16 test suite was executed: **10 tests passed, 0 failed**.

## New files to commit

- `causal_models/phase16_final_statin/analyze_phase16.py`
- `causal_models/phase16_final_statin/test_phase16.py`
- `causal_models/phase16_final_statin/phase16_endpoint_finalization.md`
- `causal_models/phase16_final_statin/phase16_confounding_decision.md`
- `causal_models/phase16_final_statin/phase16_selection_assessment.md`
- `causal_models/phase16_final_statin/phase16_final_statin_results.md`
- `causal_models/phase16_final_statin/PHASE_16_FINAL_SCIENTIFIC_DECISION.md`
- `causal_models/phase16_final_statin/phase16_manuscript_notes.md`
- `causal_models/phase16_final_statin/PHASE_16_COMPLETION_REPORT.md`
- All generated CSV/PNG/JSON artifacts under `causal_models\phase16_paper_assets`
