# Provisional statin causal model

`statin_dag.json` is the machine-readable model, including node roles, edge
rationales, data status, unresolved edges, and target-trial hypothesis.
Prior-MI eligibility is distinct from episode count, recency, severity, and
previous interventions. The `statin_before` proxy is not an adjustment
candidate: it is an imperfect measurement and a potential collider of prior
use and healthcare access. `statin_dag.svg` visualizes active edges (solid:
proposed; dashed: assumptions needing validation).

Run the graph checks and regenerate the visualization with:

```powershell
.\.venv\Scripts\python.exe -m causal_models.statin_dag
```

The graph command enumerates open backdoor paths for measured and expanded
candidate sets under prior-MI/discharge-survivor selection. Listings are
bounded and report truncation. This is a structural assessment, not evidence
of exchangeability or causal identification.

`statin_scm.py` provides parameterized structural equations for baseline
history, statin assignment, post-assignment receipt, recurrent MI, and
competing death. Event probabilities currently refer to a single,
not-yet-defined follow-up horizon; this is not a time-to-event or longitudinal
survival model. Supply `StatinSCMParameters` explicitly. The bundled
`synthetic_test_parameters()` are illustrative and for synthetic testing only;
the module does not fit parameters or load the master dataset.

```python
from causal_models.statin_scm import StatinSCM, StatinSCMParameters

scm = StatinSCM(your_validated_parameters)
observational = scm.predict_observational(eligible_survivors)
comparison = scm.compare_interventions(eligible_survivors)
```

`compare_interventions` contrasts model-implied risks under `do(statin=1)` and
`do(statin=0)`. It replaces the treatment-assignment mechanism, propagates
receipt/adherence, and accounts for competing event probabilities. It does
not produce observed individual counterfactuals or an empirical effect
estimate. Cohort, treatment, and follow-up horizon definitions remain
unvalidated.

Run the focused synthetic tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest causal_models.test_statin_dag causal_models.test_statin_scm -v
```

`statin_causal_forest.py` contains a gated empirical workflow for the existing
patient-level train/validation/test splits. It restricts to prior-MI admissions,
collapses repeated ECG rows to one admission, and uses an explicit list of
pre-treatment features. The order-derived `statin_before` proxy is excluded
from primary adjustment because its measurement/collider role is unresolved;
it is available as a sensitivity specification. The runner refuses to treat
`is_MI` or `Label_Troponin` as a subsequent recurrent-MI endpoint.

Check readiness and write the blocker report with:

```powershell
.\.venv\Scripts\python.exe -m causal_models.statin_causal_forest
```

By default the runner blocks estimation until the endpoint and temporal-order
assumptions are validated. To run the current cohort as an explicitly
exploratory analysis without asserting validation, use:

```powershell
.\.venv\Scripts\python.exe -m causal_models.statin_causal_forest `
  --data-dir causal_models\data\statin_recurrent_mi_forest_splits `
  --source-cohort causal_models\data\statin_recurrent_mi_cohort.parquet `
  --outcome recurrent_mi --allow-exploratory-estimation
```

The gated experiment uses train for fitting, validation for forest selection,
and test for final evaluation. The exploratory run reports split-level
competing-event and censoring counts, propensity overlap and balance, complete-
case estimates, and an IPCW sensitivity analysis. It writes models,
predictions, metrics, balance tables, and figures under
`causal_models/outputs/causal_forest/`. Estimates remain model-dependent and
are not established clinical effects.

## Longitudinal recurrent-MI cohort

Build the discharge-indexed, 12-month prior-MI cohort from the existing
longitudinal artifacts and processed master indicators with:

```powershell
.\.venv\Scripts\python.exe -m causal_models.statin_recurrent_mi_cohort
```

The index is each patient's earliest discharge-surviving admission after a
previous MI-coded admission has discharged. Follow-up starts at index
discharge. Death before recurrence is recorded as a competing event; event-free
follow-up shorter than the horizon is censored with a missing binary outcome,
not classified as no MI. Date-only death records on the same day as an MI
admission are retained as event-order uncertain. The output cohort and concise
summary are written under `causal_models/data/`; admission-level train,
validation, and test files inherit patient assignment from the existing master
splits under `statin_recurrent_mi_forest_splits/`.

The three `statin_*` indicators are copied as supplied by the processed master.
The cohort builder does not infer a prescription or administration timestamp,
and does not rebuild or join the source medication archives.

To pass the new admission-level split files to the existing Phase 9 runner:

```powershell
.\.venv\Scripts\python.exe -m causal_models.statin_causal_forest `
  --data-dir causal_models\data\statin_recurrent_mi_forest_splits `
  --source-cohort causal_models\data\statin_recurrent_mi_cohort.parquet `
  --outcome recurrent_mi --allow-exploratory-estimation
```

The adapter inherits the patient-level train/validation/test assignment and
does not manufacture an ECG `study_id`. The runner's empirical estimates remain exploratory unless the study team's
validation of the endpoint and treatment-timing assumptions is supplied.
