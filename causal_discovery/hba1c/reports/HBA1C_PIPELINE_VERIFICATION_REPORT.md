# Next Task: Resolve and Validate the HbA1c Outcome-Timing Defect

Read these existing files before making changes:

- `causal_discovery/hba1c/reports/HBA1C_PIPELINE_VERIFICATION_REPORT.md`
- `causal_discovery/hba1c/reports/HBA1C_CAUSAL_DISCOVERY_REPORT.md`
- `causal_discovery/hba1c/data_preparation.py`
- `causal_discovery/hba1c/config.yaml`
- The saved 90-day, 180-day, and 365-day discovery datasets
- The source admission chronology, MI admission records, observation-end data, and demographic/diagnosis files used to construct the discovery cohort

## Objective

Resolve the discrepancy between the intended research question—antecedent HbA1c and subsequent MI after baseline discharge—and the existing outcome implementation, which marks MI admissions occurring after baseline admission time.

The verification report identified that the current outcome does not enforce baseline discharge and does not implement the described death or administrative censoring.

**Do not rerun PC, GES, FCI, bootstrap, or other discovery analyses during this task. Do not overwrite existing outputs.**

### Step 1 — Trace the outcome construction

Inspect the actual source code and identify:

- How the baseline admission is selected.
- How baseline admission and discharge timestamps are obtained.
- How prior MI history is defined.
- How subsequent MI admissions are identified.
- Whether the current implementation compares MI admission time against baseline admission or discharge.
- Whether event times, death, and observation-end timestamps are retained.

Trace every relevant field to its source file and column. Do not infer that a field is valid merely because it exists.

### Step 2 — Define the intended temporal rules

Evaluate the following proposed ordering:

1. The antecedent HbA1c measurement strictly precedes the baseline admission date.
2. The patient belongs to the eligible diabetes population at baseline.
3. The baseline encounter is an eligible non-MI admission.
4. Follow-up begins at baseline discharge.
5. The outcome is the first qualifying MI admission strictly after baseline discharge.
6. Death and the end of recorded observation are handled explicitly.

Document the exact inequalities and timestamp conventions.

Clarify how same-day events, overlapping admissions, missing timestamps, in-hospital death, and MI occurring during the baseline hospitalization should be handled.

Do not silently choose a policy when the source data do not resolve it. Record unresolved choices.

### Step 3 — Validate the source chronology

Using the available source records, determine:

- Number of patients in the existing candidate cohort.
- Number with at least one MI admission after baseline admission.
- Number whose first qualifying MI admission occurs before baseline discharge.
- Number whose first qualifying MI admission occurs strictly after baseline discharge.
- Number with no qualifying subsequent MI during observable follow-up.
- Number censored by death and number censored administratively, using mutually exclusive and clearly defined categories.
- Number with missing or contradictory chronology.

Where categories overlap, explain the overlap and provide a mutually exclusive accounting.

Use the actual source timestamps. The existing discovery CSV does not contain sufficient event-time information to quantify this defect by itself.

### Step 4 — Separate the outcome label from the follow-up process

Determine whether a simple binary `subsequent_mi` outcome is sufficient for the intended estimand or whether the cohort needs an explicit follow-up record containing:

- Baseline discharge time.
- First qualifying post-discharge MI admission time.
- Death time, where available.
- Administrative observation-end time.
- Event indicator.
- Follow-up duration.
- Censoring reason.

Do not claim that censoring has been implemented unless the actual code implements it.

Document the implications of single-center outcome ascertainment and unobserved events outside the available hospital network.

### Step 5 — Propose the corrected dataset schema

Provide a proposed schema for the corrected prospective cohort.

Preserve the existing variables and source provenance where appropriate. Keep event timestamps and censoring fields so future audits can verify temporal ordering.

Do not regenerate the discovery datasets yet.

### Step 6 — Preserve the existing results

Treat the current discovery datasets and graphs as a historical, potentially mislabelled run.

Do not delete, overwrite, or silently edit them.

If the corrected outcome changes the cohort, event counts, or target estimand, recommend versioned outputs, for example:

- `hba1c_discovery_180d_v2.csv`
- `outcome_timing_audit_v2.md`

Do not create these final datasets until the temporal rules and unresolved decisions are documented and approved.

### Step 7 — Deliverables

Create:

`causal_discovery/hba1c/reports/HBA1C_OUTCOME_TIMING_AUDIT_V2.md`

Include:

1. Source-code trace.
2. Source-field provenance.
3. Formal temporal definitions.
4. Chronology validation.
5. Counts of events before and after baseline discharge.
6. Death and administrative censoring accounting.
7. Missing/contradictory timestamp findings.
8. Proposed corrected outcome and follow-up schema.
9. Unresolved scientific decisions.
10. Explicit recommendation on whether the existing discovery results remain suitable for the intended research question.

For every reported count, identify the source table, selection rule, and denominator.

If the source files needed for an exact count are unavailable, state that limitation instead of estimating the count.

## Strict boundaries

- No PC/GES/FCI reruns.
- No bootstrap rerun.
- No ATE/CATE.
- No adjustment-set selection.
- No final DAG.
- No overwriting historical artifacts.
- No unsupported causal claims.

Stop after producing the audit and recommended next decision.# HbA1c Causal Discovery Pipeline Verification Report

**Audit scope:** Read-only verification of the existing implementation and outputs. No discovery algorithm, bootstrap, dataset preparation, or sensitivity analysis was run during this audit. No existing graph, edge table, dataset, or report was modified for this verification.

## Executive conclusion

The saved primary PC, GES, and FCI graph artifacts are internally consistent with their edge CSVs and the saved 180-day dataset. They are credible artifact-based evidence that output generation completed, but there are no execution logs, checkpoints, or run manifests to prove which process invocation produced them. Sensitivity summary counts match the saved window datasets; individual sensitivity graphs/edge lists are not saved, so those graph results cannot be independently verified from outputs.

The saved primary HbA1c–subsequent-MI adjacency is present in all three methods. The FCI graph uses arrowheads at both endpoints; this is a PAG mark and not proof of an actual latent confounder. The bootstrap CSV is arithmetically consistent with 500 replicates, and its target-pair adjacency frequencies are 88.4% / 77.0% / 88.4% for PC / GES / FCI. The exact resampling run cannot be replayed from the saved CSV because individual replicate results and a run manifest are absent. Bootstrap orientation labels have a normalization defect, so orientation frequencies should not be used as verified evidence.

**Material outcome-definition defect:** `data_preparation.py` marks an MI as subsequent when its admission time is after the baseline **admission**, not after baseline **discharge**. The dataset contains `dischtime`, but the outcome predicate does not use it. It also does not implement the report's stated death/administrative censoring. The saved data do not retain the MI event timestamp, so the number of affected records cannot be determined without consulting the source data and rebuilding the outcome. As a result, these outputs are not verified as answering the stated post-discharge research question.

## Status legend

- **VERIFIED** — Directly checked against saved output and/or implementation; evidence supports the specific claim.
- **PARTIALLY VERIFIED** — Some evidence agrees, but direct execution or required artifacts are missing.
- **NOT VERIFIED** — Required evidence is absent; this is not a claim that the stage failed.
- **DEFECT FOUND** — Code or saved interpretation has an identified issue with material implications.
- **NOT APPLICABLE** — The check does not apply to that item.

Status is scoped to the exact claim in its row. A saved artifact can be structurally verified without proving how or when it was produced.

## 1. Scope and files inspected

Inspected the listed scripts, configuration, primary report, all three window datasets, primary graph/edge outputs, bootstrap CSV, sensitivity JSON, comparison CSVs, data-quality JSON, and PC separation-set JSON under `causal_discovery/hba1c/`.

Implementation and configuration:

- [`data_preparation.py`](../data_preparation.py)
- [`run_pc.py`](../run_pc.py)
- [`run_ges.py`](../run_ges.py)
- [`run_fci.py`](../run_fci.py)
- [`bootstrap_stability.py`](../bootstrap_stability.py)
- [`compare_dags.py`](../compare_dags.py)
- [`config.yaml`](../config.yaml)

Saved data and results:

- `data/hba1c_discovery_{90,180,365}d.csv`
- `results/{pc,ges,fci}_{graph.txt,edges.csv}`
- `results/pc_sepsets.json`
- `results/bootstrap_edge_frequency.csv`
- `results/sensitivity_analysis_summary.json`
- `results/algorithm_comparison.csv`
- `results/domain_vs_discovery.csv`
- `results/data_quality_diagnostics.json`

Reports:

- [`HBA1C_CAUSAL_DISCOVERY_REPORT.md`](./HBA1C_CAUSAL_DISCOVERY_REPORT.md)

No separate execution log, checkpoint, raw per-bootstrap result, sensitivity graph, or sensitivity edge table was present in the inspected HBA1C directory.

## 2. Verification matrix

| Stage / claim | Status | Evidence and limitation |
|:---|:---|:---|
| Dataset preparation: 90-day cohort | **PARTIALLY VERIFIED** | Saved CSV has 4,818 rows, 4,818 unique `subject_id` values, 534 positive outcome labels, and no missing values in the seven algorithm variables. No build log or source-data checksum proves the file was freshly generated by the current script. |
| Dataset preparation: 180-day cohort | **PARTIALLY VERIFIED** | Saved CSV has 6,575 rows/unique subjects and 763 positive outcome labels; the saved diagnostic JSON reports N=6,575 and zero missing values. The data-generation code has a material outcome-timing defect described below. |
| Dataset preparation: 365-day cohort | **PARTIALLY VERIFIED** | Saved CSV has 8,042 rows/unique subjects and 949 positive outcome labels. No build log or source-data checksum is present. |
| Primary PC | **PARTIALLY VERIFIED** | Graph text, 12-row edge CSV, and 7×7 matrix agree; graph text reports the 180-day file and N=6,575, matching the CSV. No execution log or run manifest proves a successful invocation. |
| Primary GES | **PARTIALLY VERIFIED** | Graph text, 11-row edge CSV, and 7×7 matrix agree; graph text reports the 180-day file and N=6,575. The saved score is -2858.6289673833535. No execution log or run manifest proves a successful invocation. |
| Primary FCI | **PARTIALLY VERIFIED** | Graph text, 12-row edge CSV, and 7×7 matrix agree; graph text reports the 180-day file and N=6,575. PAG endpoints match the matrix. No execution log or run manifest proves a successful invocation. |
| Bootstrap adjacency frequencies | **PARTIALLY VERIFIED** | CSV has 21 unordered pairs. Every one of its 63 method-specific percentages lies on a 0.2 percentage-point grid, consistent with 500 replicates. Target pair values match the report. Raw resample results are absent; exact frequencies cannot be regenerated or independently recounted from the aggregate CSV. |
| Bootstrap dominant orientations | **DEFECT FOUND** | The canonical-orientation conversion reverses some PC/GES directions when algorithm edge-node order differs from lexical pair order. For example, primary PC/GES and FCI outputs say `hypertension -> anchor_age`, while the bootstrap CSV labels PC/GES as `anchor_age -> hypertension`. FCI circle-mark labels are not consistently canonicalized either. |
| Cross-algorithm comparison | **PARTIALLY VERIFIED** | Saved primary comparison rows agree on presence/absence and orientations with the primary edge CSVs; the target is present in all three. `compare_dags.py` assigns interpretive categories from the FCI arrow-arrow flag and mean bootstrap cutoff, including unsupported “screened off/d-separated” language. |
| Sensitivity analyses | **PARTIALLY VERIFIED** | Saved JSON cohort sizes and event counts match the 90/180/365 CSVs. Summary detection flags and edge counts agree with the saved summary values and script structure, but per-analysis graphs/edges are not saved, and there is no execution log. The fully discrete result is not independently graph-verified. |
| Existing report consistency | **PARTIALLY VERIFIED** | Its principal 180-day adjacency claims and target bootstrap adjacency frequencies match the saved artifacts. The report's stated post-discharge outcome, censoring, some bootstrap orientations, and some causal interpretations do not match the implementation/artifacts. Recommended corrections are listed below. |

## 3. Execution evidence versus artifact-based inference

No stdout/stderr log, completion marker, serialized algorithm object, process record, or run manifest was found. Therefore:

- The graph and CSV pairs are **credible artifact-based evidence**: they are readable, have valid 7×7 adjacency matrices, contain the expected node set, and agree on their edge lists and endpoint marks.
- Saved graph headers identify `hba1c_discovery_180d.csv`, report N=6,575, and record causal-learn v0.1.4.8. Those values match the currently saved primary dataset and installed script's configured variable set.
- File timestamps are chronologically plausible (datasets/diagnostics earlier than primary graphs, bootstrap, and comparison outputs), but timestamps do not prove which command generated a file or rule out an overwrite.
- Successful completion of each exact process invocation is **not directly verified**. The statuses remain PARTIALLY VERIFIED, not VERIFIED.
- The three window CSVs have unique patient IDs, which is consistent with row-level patient resampling in the bootstrap. This checks the saved data, not provenance.

## 4. PC implementation audit

**Status: PARTIALLY VERIFIED.**

- `run_pc.py` defaults to the configured primary window and passes the seven columns in this order: `anchor_age`, `sex_male`, `hypertension`, `ckd`, `prior_mi`, `hba1c_state`, `subsequent_mi`. The saved matrix is 7×7 and the edge CSV's nodes are exactly these variables.
- The saved primary header records `fisherz`, alpha 0.05, depth 4, and causal-learn v0.1.4.8; these agree with `config.yaml` and the call to `pc`.
- `np.random.seed(42)` is applied, but the graph file does not record the seed. No background knowledge or temporal constraints are passed to `pc`.
- Endpoint extraction is faithful to the saved PC matrix: TAIL/ARROW are recorded in the edge CSV with the corresponding source/target endpoints; all 12 CSV rows match the text graph and matrix.
- PC's directed marks are CPDAG marks under the PC assumptions; they are not interchangeable with FCI PAG marks and do not, on their own, prove direct causal effects.
- The primary run uses Fisher-Z with continuous age and binary 0/1 variables. No nonlinear or discrete CI test was used for the primary result.
- The optional parameter expression `alpha = alpha or config[...]` treats an explicit zero as “use the configured alpha.” This does not affect the saved alpha=0.05 run but is an API override edge case.
- **Run execution: PARTIALLY VERIFIED**, because no process log or run manifest is available.

## 5. GES implementation audit

**Status: PARTIALLY VERIFIED.**

- `run_ges.py` passes the same 180-day dataset and seven variables in the same order as PC/FCI.
- The saved graph records `local_score_BIC`, N=6,575, and causal-learn v0.1.4.8, matching the primary config and implementation.
- `maxP` is an optional argument, but the normal call does not set it, so the library default is used. The code does not specify an explicit BIC penalty discount or record the resolved library default parameters. GES has no alpha threshold or CI conditioning-depth parameter in this call.
- `np.random.seed(42)` is called, but the graph output does not record the seed. No temporal/background constraints are supplied.
- All 11 text edges match the edge CSV and matrix endpoint marks. GES output is a score-based equivalence graph; its directed marks should not be interpreted as proof of causal direction or truth.
- No fallback to another algorithm is present: the script imports and calls GES directly, and exceptions are not caught or replaced with a success-shaped output.
- **Run execution: PARTIALLY VERIFIED**, because no process log or run manifest is available.

## 6. FCI implementation audit

**Status: PARTIALLY VERIFIED.**

- `run_fci.py` uses the same primary dataset, column order, and node names as PC/GES.
- The saved graph records `fisherz`, alpha 0.05, depth 4, and causal-learn v0.1.4.8, consistent with the script/config.
- No temporal or other background knowledge is passed to FCI.
- All 12 edge rows agree with the graph text and adjacency-matrix endpoint values. The target pair is present as ARROW/ARROW.
- The output extraction maps the endpoint pair correctly as a PAG mark, but sets `latent_confounding=True` for every ARROW/ARROW edge and serializes the direction label as `bidirected_latent_confounded`. That label overstates what this endpoint pattern establishes. An arrowhead at both endpoints is an estimated PAG mark compatible with latent-confounding structures under FCI assumptions; it does not prove a particular latent cause or that latent confounding is the true explanation. This is a **semantic interpretation defect**, not evidence that the saved endpoint extraction itself is wrong.
- As with PC, this primary Fisher-Z test is applied to mixed continuous and binary-coded input. No nonlinear CI test is in this run.
- No fallback method is called if FCI fails; errors are not broadly caught or silently substituted.
- **Run execution: PARTIALLY VERIFIED**, because no process log or run manifest is available.

## 7. Bootstrap implementation and frequency verification

### Resampling and settings

`bootstrap_stability.py` reads the configured primary-window CSV and resamples rows with replacement using `np.random.choice(n_samples, size=n_samples, replace=True)`. Each row is one unique `subject_id` in the saved 180-day file, so this is patient-row bootstrap sampling for the current dataset. Each replicate reruns PC, GES, and FCI; it does not reuse the primary graph.

There is a configuration mismatch:

- `config.yaml` says `bootstrap.n_replicates: 100`, `sample_fraction: 1.0`, `replace: true`, and seed 42.
- The implementation does not read these bootstrap configuration keys. Its function defaults to 500 and its `__main__` invocation explicitly passes 500 and seed 42. It always samples N rows with replacement.
- The output grid is consistent with 500 replicates but does not prove that the saved CSV came from that invocation. The report should identify the entry-point setting and disclose the unused YAML value.
- The bootstrap code uses PC's alpha/test/depth values for FCI as well. They happen to equal the configured FCI values now; separate FCI configuration is not read. A future divergence in PC and FCI configuration would silently make the FCI bootstrap settings differ from `config.yaml`.
- GES in bootstrap uses the GES score setting and no explicit `maxP`, consistent with the primary function's default behavior.

### Frequency checks

`bootstrap_edge_frequency.csv` contains 21 unordered pairs (all pairs of seven variables), and all method-specific adjacency percentages are multiples of 0.2%. For the target pair it contains:

| Pair | PC adjacency | GES adjacency | FCI adjacency | Mean |
|:---|---:|---:|---:|---:|
| `hba1c_state - subsequent_mi` | 88.4% | 77.0% | 88.4% | 84.6% |

The same values are in the existing causal-discovery report. The aggregate output is internally consistent with 500 replicates. Exact reproducibility/recounting is **NOT VERIFIED** without per-replicate samples/edges or a run manifest; rerunning would be required to reproduce the computation, and was not done.

### Orientation extraction defect

For PC/GES, the bootstrap code attempts to canonicalize endpoint direction relative to a lexically sorted pair. In the branch where `pair[0] != u`, the tail/arrow mappings reverse some node directions. The saved output itself demonstrates the mismatch: primary PC and GES say `hypertension -> anchor_age`, whereas bootstrap dominant orientation says `anchor_age -> hypertension` at 100.0% and 95.8% respectively. Thus:

- **Adjacency frequencies:** not affected by this specific orientation-string defect and remain arithmetically consistent.
- **Dominant orientation strings/frequencies:** not reliable across all pairs and are not fully verifiable from aggregate CSV.
- **Target HbA1c–MI adjacency percentages:** consistent with the saved artifacts and report. Its dominant orientation strings match the primary endpoint direction in the CSV, but individual bootstrap graphs are absent, so their exact orientation counts cannot be independently checked.
- FCI ARROW/ARROW orientation labels are canonicalized, but circle-arrow labels retain algorithm edge-node order. FCI partial-mark orientation frequency strings therefore also need a tested endpoint-normalization pass before being treated as comparable labels.

## 8. Sensitivity-analysis verification

`compare_dags.py` runs the sensitivity calls and writes only `sensitivity_analysis_summary.json`; it does not persist sensitivity graph text, edge CSVs, p-values, scores, or FCI marks.

### Window sensitivity

| Window | Saved dataset rows / unique subjects | Saved dataset positive labels | JSON sample size / events | JSON target adjacency PC / GES / FCI |
|:---|---:|---:|---:|:---|
| 90d | 4,818 / 4,818 | 534 | 4,818 / 534 | yes / no / yes |
| 180d | 6,575 / 6,575 | 763 | 6,575 / 763 | yes / yes / yes |
| 365d | 8,042 / 8,042 | 949 | 8,042 / 949 | yes / yes / yes |

**Status: PARTIALLY VERIFIED.** Dataset counts and events match exactly; target flags and edge counts are present in JSON and correspond to the calls encoded in the script. No run log or per-window graph/edge artifacts exist, so the algorithm-produced window results are not independently verifiable without rerunning.

### Other sensitivities

- **Continuous HbA1c:** JSON records the target pair in all three methods. The script swaps `hba1c_state` for `hba1c`; all other method settings remain Fisher-Z/BIC. No alternate graph or marks are saved. **PARTIALLY VERIFIED.**
- **Alpha:** JSON records PC and FCI target detection at 0.01, 0.05, and 0.1, with 12 edges at each level. This matches the script's alpha loop. No GES alpha sensitivity exists, because GES is score-based. No outputs beyond counts/flags are saved. **PARTIALLY VERIFIED.**
- **Fully discrete:** JSON records PC=no, GES=no, FCI=yes for the target. The code changes age to `age_bracket`, CI test to `chisq`, and GES score to `local_score_BDeu`; N remains the 180-day cohort. This changes multiple methodological choices simultaneously, so it cannot isolate age encoding from test/score choice. No discrete graph, edge table, contingency-cell diagnostic, or power analysis is saved. **PARTIALLY VERIFIED.**
- **Sensitivity marks/orientations:** **NOT VERIFIED.** The JSON summary does not record endpoint marks, orientations, p-values, or scores.

The report's statement that GES omits the target adjacency in 90 days and that PC/GES omit it in the fully discrete setting matches the saved JSON. It should be labeled summary-artifact evidence, not independently validated graph evidence.

## 9. Report-versus-artifact consistency checks

| Report claim | Status | Audit result |
|:---|:---|:---|
| Primary PC retains `hba1c_state - subsequent_mi` | **VERIFIED** | PC graph text and edge CSV both include `hba1c_state -> subsequent_mi`; matrix confirms adjacency and endpoints. |
| Primary GES retains the same adjacency | **VERIFIED** | GES graph text and edge CSV include `hba1c_state -> subsequent_mi`; matrix confirms endpoints. |
| Primary FCI retains the adjacency with ARROW/ARROW | **VERIFIED** | FCI graph text and edge CSV include `hba1c_state <-> subsequent_mi`; matrix confirms ARROW at both endpoints. |
| Primary sample size is 6,575 | **VERIFIED** | All three graph headers say N=6,575; saved primary CSV has 6,575 rows. |
| Primary target bootstrap adjacency rates are 88.4% / 77.0% / 88.4% | **PARTIALLY VERIFIED** | Exact values are in the CSV and are consistent with the 500-replicate grid; no raw replicate output independently verifies the run. |
| GES misses target adjacency at 90 days | **PARTIALLY VERIFIED** | Sensitivity JSON says false; no 90-day graph/edge file or execution log to inspect. |
| PC and GES miss target in the fully discrete sensitivity | **PARTIALLY VERIFIED** | Sensitivity JSON says false for both; no discrete graph/edge file or cell/power diagnostic. |
| Current report accurately describes the outcome as post-discharge | **DEFECT FOUND** | Data-preparation code compares MI `admittime` with baseline `admittime`, not baseline `dischtime`. The dataset does not save the event time needed to quantify affected rows. |
| Current report accurately describes censoring/death handling | **DEFECT FOUND** | The discovery builder creates a binary ever-after-baseline-admission flag. It does not use death, observation-end, or follow-up censoring fields. |
| Current report bootstrap dominant directions are reliable | **DEFECT FOUND** | At least the age–hypertension row contradicts primary PC/GES edge orientation due to canonicalization logic. |
| Comparison CSV interpretation is supported | **DEFECT FOUND** | `domain_vs_discovery.csv` labels results “screened off/d-separated” based on a mean bootstrap cutoff; the script does not establish d-separation/mediation from that threshold. |

The saved primary graph files are readable: each has a 7×7 integer adjacency matrix, a node set matching the seven algorithm input variables, and edge lines matching the edge CSV orientations. Matrix endpoint values were compared with the CSV endpoint columns for every edge: zero mismatches for PC (12 edges), GES (11), and FCI (12).

## 10. Scientific interpretation audit

Keep these claims separate:

1. **Adjacency detection — supported by saved primary graph artifacts.** All three primary graphs connect `hba1c_state` and `subsequent_mi`.
2. **Orientation / endpoint marks — supported as recorded graph outputs, not causal truth.** PC/GES show a directed-marked edge `hba1c_state -> subsequent_mi`; FCI shows ARROW/ARROW. PC/GES CPDAG marks and FCI PAG marks represent different graph objects and assumptions.
3. **Bootstrap selection stability — supported as aggregate output, not causal probability.** The CSV reports 88.4% / 77.0% / 88.4% adjacency frequency. Do not call these probabilities that the edge is true or causal. Dominant orientation frequencies are compromised by the code defect above.
4. **Evidence for a causal relationship — not established by these outputs alone.** Algorithmic graphs are conditional on variable selection, data quality, causal assumptions, test/score, and the incorrect/under-specified event timing. A bidirected FCI mark is not proof of latent confounding.
5. **Identification of a causal effect — not applicable / not performed.** No ATE/CATE, adjustment set, or final DAG was estimated or selected.

### Temporal constraints and variable scope

- **Background knowledge: VERIFIED absent.** The PC/GES/FCI calls pass no temporal background-knowledge object, tier constraints, or forbidden-edge list. The saved primary outputs include arrows into `anchor_age` and `sex_male`, consistent with an unconstrained search; the edge CSVs and graph text agree on those marks.
- **Variable set: PARTIALLY VERIFIED adequate only for a seven-node exploratory analysis.** The scripts consistently use age, sex, hypertension, CKD, prior MI, HbA1c state, and subsequent MI. That is not sufficient to rule out confounding by unmeasured or omitted factors relevant to glycemic control and MI (for example diabetes duration/severity, treatment, smoking, BMI, and healthcare-use/selection factors); no claim about those factors is tested here. FCI does not make omitted variables observed.
- **Mixed-data limitation: VERIFIED.** Primary PC and FCI use `fisherz` with continuous age and binary-coded variables; GES uses BIC on that mixed numeric matrix. These routines do not implement a dedicated mixed categorical/continuous model in the shown calls. The report should call this an approximation and not imply that binary coding makes Fisher-Z/BIC a correctly specified general mixed-data model.
- **Nonlinearity: NOT VERIFIED.** No nonlinear CI test, flexible functional-form diagnostic, or alternative nonlinear score is run or saved. Nonlinearity cannot be asserted as the explanation.
- **Discrete sensitivity: VERIFIED as a bundled change.** It changes age encoding, PC/FCI CI test, and GES score together, so the sensitivity cannot attribute result changes to any one of these choices.
- **Terminology: DEFECT FOUND in the broader framing.** “Statistical validation” overstates what conditional/score-based graph selection establishes. Prefer “data-driven structural evidence under specified assumptions,” with explicit limits.

## 11. Implementation defects and implications

### DEFECT FOUND — outcome time is after baseline admission, not discharge

`data_preparation.py` retains baseline `dischtime` but builds `later_mis` by filtering `admittime_mi > admittime_base`. This admits a later MI admission that occurs after the baseline admission starts but before it ends. The report describes the target as after discharge and describes death/administrative censoring; neither condition is implemented in the saved outcome label. The saved discovery CSV has no MI event-time field or censoring field, so impact size is unknown. **Implication:** primary and sensitivity graph results are not verified for the stated post-discharge estimand; no causal interpretation for that question should proceed from these outputs without resolving the label.

### DEFECT FOUND — bootstrap orientation canonicalization

The PC/GES bootstrap orientation strings reverse some directions when the library's edge node order is opposite the sorted pair order. Demonstrated contradiction: primary edge files show `hypertension -> anchor_age`, while bootstrap CSV reports `anchor_age -> hypertension` as the dominant PC/GES orientation. FCI's circle-arrow strings are also not consistently normalized to a stable pair ordering. **Implication:** retain adjacency frequencies only as provisional aggregate output; do not cite the affected dominant endpoint/orientation labels until corrected and regenerated.

### DEFECT FOUND — FCI arrow-arrow overlabeling

`run_fci.py` sets `latent_confounding=True` and labels the relation `bidirected_latent_confounded` whenever both endpoints are arrowheads. **Implication:** saved CSV/text and comparison categories overstate the evidentiary meaning. The endpoint pattern may be described as an estimated bidirected PAG mark, compatible with latent-confounding explanations under assumptions, not detection/proof of a specific latent confounder.

### DEFECT FOUND — comparator converts stability cutoff to causal/d-separation language

`compare_dags.py` uses mean adjacency frequency >=70% as `stat_supported`, then labels domain edges below that cutoff “statistically weak (Screened off/d-separated).” Its text explanations further assert mediation/screening-off and treat bootstrap summaries as causal evidence. A bootstrap threshold is not a conditional-independence test or d-separation proof. The saved comparison CSV retains those old interpretations. **Implication:** do not rely on its status/interpretation prose; its raw detected flags/orientations can be read alongside the primary outputs, but need careful semantics.

### DEFECT FOUND — bootstrap YAML settings are not authoritative

The YAML says 100 replicates, while the script entry point explicitly requests 500; `sample_fraction`, `replace`, and bootstrap `random_seed` config fields are not read by the function. **Implication:** configuration and implementation can diverge without warning. The output is consistent with 500 but not conclusively attributable to it from a manifest.

### PARTIALLY VERIFIED — stale/overwritten outputs cannot be ruled out

Timestamps are chronologically plausible, graph and CSV pairs agree, and the sensitivity JSON matches dataset counts. However, outputs have no run ID, input hash, script/config hash, command log, or completion marker. It is impossible to establish whether any file is stale or was overwritten by another run. No positive contradiction in primary graph contents was found.

No method silently falls back to a different algorithm: PC, GES, and FCI are imported and invoked explicitly; no broad exception handlers or success-shaped fallbacks were found in the audited scripts.

## 12. Methodological limitations

- **Target/outcome alignment:** post-discharge timing and censoring are not implemented as described; event timing is absent from the saved analysis CSV.
- **Selection:** every discovery record has a qualifying HbA1c measurement, so this analysis is selected on testing; the code does not model the testing/selection process.
- **Observed-variable scope:** the seven-node graph omits plausible causes/proxies of glycemic state and MI. FCI's latent-variable framework does not establish what those omitted factors are.
- **Mixed data:** Fisher-Z and BIC are applied to continuous age and binary-coded fields without a dedicated mixed-data method or validated link/score specification.
- **Conditioning limit:** PC/FCI use depth 4. In a seven-node graph, a pair has five other nodes available; conditioning on all five is not searched.
- **No nonlinearity diagnostic:** nonlinear dependence could be missed or misrepresented, but there is no evidence that it explains this result.
- **Sensitivity confounding:** the all-discrete sensitivity changes age representation, CI test, and score function together.
- **Selection frequency:** bootstrap edge frequency measures algorithm output stability under row resampling, not truth probability, causal effect, or confidence interval.
- **Execution provenance:** no logs, per-resample outputs, method objects, or complete run manifest.
- **No causal effects/adjustment:** no ATE/CATE, adjustment set, or final DAG is identified by this audit.

## 13. Corrections recommended for the existing causal-discovery report

The current [`HBA1C_CAUSAL_DISCOVERY_REPORT.md`](./HBA1C_CAUSAL_DISCOVERY_REPORT.md) should, in the next authorized documentation update:

1. State that the code's current binary outcome means “MI admission after baseline admission time,” not verified “MI after discharge”; remove claims that the code implements death/administrative censoring unless a corresponding implementation is added.
2. Qualify whether the discovered output answers the intended post-discharge question until the event definition is resolved.
3. Correct Section 17 bootstrap dominant orientations affected by canonicalization; preserve adjacency percentages separately and explicitly note their artifact-only verification.
4. Describe FCI output as a bidirected PAG mark compatible with latent structures, not “latent confounding detected” or proof of an actual confounder.
5. Correct the run-state audit: YAML replicates=100; script default and entry point=500; the saved 0.2% grid is consistent with 500 but does not prove execution provenance.
6. Replace `domain_vs_discovery.csv` “screened off/d-separated,” mediation, and direct-causal-effect claims with graph non-selection / resampling-stability descriptions.
7. Narrow “statistically supported/validated” wording to data-driven structural evidence under the stated assumptions; retain distinctions among adjacency, endpoint marks, causal truth, and effect identification.
8. Add that the primary mixed-data Fisher-Z/BIC analysis is an approximation and that no nonlinear diagnostics or individual sensitivity graphs were saved.

No corrections above were applied to existing graph, edge, bootstrap, comparison, or causal-discovery report outputs during this audit.

## 14. Exact next steps

1. **First and most important:** Resolve the event-time definition against baseline discharge and follow-up/censoring requirements using the source admission times. The saved discovery CSV alone cannot establish which positive labels occurred before discharge. Do not interpret the current graph outputs as the stated post-discharge analysis until this is settled.
2. If the outcome definition must change, version the corrected cohort and document the changed row/event counts before obtaining approval to rerun the affected discovery stages. Do not overwrite the current artifacts.
3. Before relying on bootstrap orientations, correct the normalization logic, reconcile YAML and code settings, and only then obtain approval for any bootstrap rerun. Until then, do not use dominant orientation frequencies.
4. Correct comparator interpretation and report language without treating graph absence as proof of independence or mediation.
5. Preserve the current outputs as an auditable historical run; add a run manifest (dataset/config/script/library hashes, command, timestamp, exit status) for future authorized runs.

**Readiness decision:** The primary graph artifacts are suitable for a cautious implementation review and preliminary literature/expert discussion of *data-driven adjacencies under the stated algorithm settings*. They are **not ready as validated evidence for the stated post-discharge causal question**, because the outcome timing/censoring mismatch is unresolved. They do not identify a causal effect, final adjustment set, or final DAG.
