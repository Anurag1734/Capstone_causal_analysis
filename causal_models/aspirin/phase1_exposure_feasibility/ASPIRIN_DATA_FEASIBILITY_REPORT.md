# Aspirin data feasibility report

## Provisional question and scope

Provisional question: among patients with a previous myocardial infarction, what is the effect of aspirin exposure on subsequent MI? This phase assesses data support only. No causal effect, target-trial treatment contrast, adjustment set, DAG, or causal model is specified.

## Population and exposure availability

The reusable longitudinal artifact contains **7,545 unique patients/index admissions** selected under the existing rule: an index admission after a previous MI-coded admission, with survival to discharge. All 7,545 carry the cohort's prior-MI eligibility flag. The prior event is diagnosis-code based, not clinically adjudicated. The existing cohort was not filtered by statin treatment; aspirin indicators were reattached from the master by index admission.

| Measure | Count |
|---|---:|
| Eligible previous-MI index admissions | 7,545 |
| `aspirin_before=1` | 779 |
| `aspirin_before=0` | 3,877 |
| `aspirin_before` missing | 2,889 |
| `aspirin_during=1` | 2,979 |
| `aspirin_during=0` | 1,677 |
| `aspirin_after` variable | Absent |
| Index admissions with aspirin eMAR records | 2540 |
| Index admissions with valid administered aspirin timestamp | 2509 |
| First valid administration: before / during / after index | 268 / 2241 / 0 |

The eMAR scan linked 2540 eligible index admissions to aspirin-matched records; 2509 had at least one exact `Administered` event with valid charttime. The first valid event was before index admission in 268 admissions, during the admission in 2241, and after discharge in 0. Lack of a recorded administration does not establish non-use. The current data therefore support exposure-feasibility counts, not a validated aspirin-versus-no-aspirin treatment comparison. No missing exposure is recoded as untreated, and the prior statin complete-case/model population is not reused.

## Follow-up and subsequent MI outcome availability

The existing outcome framework begins follow-up at index discharge and has a 12-month horizon. It distinguishes competing death and incomplete observation. Existing endpoint event counts are: 1,833 subsequent MI-coded admissions, 994 competing deaths, 2,158 event-free through horizon, and 2,560 incomplete follow-up. Among the 1,833 broad MI-coded admissions, 1,339 are ICD-9 412-only and 494 have an acute code; the broad endpoint is therefore not a clinically validated acute recurrence endpoint.

The saved acute-code screen identifies **555** first subsequent admissions with ICD-9 410 / ICD-10 I21-I22 codes. It is an improved code-specificity screen, not proof of distinct recurrent infarction. Acute-endpoint statuses are {'event_free': 2912, 'incomplete_followup': 2859, 'competing_death': 1219, 'acute_recurrent_mi': 555}. The episode audit reports 233 candidates with an acute code on the index admission, 136 with a transfer proxy, and 54 patients with another acute-coded admission within 30 days. 14 events are within one day, 103 within seven days, and 226 within 30 days of discharge. These signals raise continuation/transfer/readmission concerns; local artifacts have no clinical adjudication.

Observation-end and death artifacts support the current competing-risk/incomplete-follow-up framework, but MIMIC-derived hospital observation is not complete community follow-up. Outcome definitions and known limitations must be carried forward rather than called clinically validated.

## Confounding and aspirin-specific design considerations

Potential baseline common causes of aspirin prescribing and later MI include prior MI/CVD history and severity, diabetes, hypertension, CKD, age/sex, other chronic cardiovascular drugs, prior antiplatelet/anticoagulant use, bleeding risk, contraindications, and healthcare utilization.

Existing candidate data:
- `anchor_age`: 7545/7545 non-missing in the existing index cohort.
- `sex_male`: 7545/7545 non-missing in the existing index cohort.
- `diabetes`: 4656/7545 non-missing in the existing index cohort.
- `hypertension`: 4656/7545 non-missing in the existing index cohort.
- `ckd`: 4656/7545 non-missing in the existing index cohort.
- `beta_blocker_before`: 4656/7545 non-missing in the existing index cohort.
- `acei_before`: 4656/7545 non-missing in the existing index cohort.
- Admission type/location, prior-admission chronology, demographics, and diagnosis-coded MI history are present in existing longitudinal artifacts.
- Master has beta-blocker and ACE-inhibitor prescription proxies; these, like aspirin, are not validated administration times.
- No prebuilt bleeding-risk, aspirin-contraindication, antiplatelet-other-than-aspirin, or anticoagulant baseline indicator was found in the processed master. Availability in underlying diagnosis text/codes has not been validated for this aspirin question.
- ECG variables and `aspirin_during`, in-hospital medicines, and admission severity/management may occur after presentation or treatment and could be treatment consequences or acute-episode markers; they are not automatically baseline confounders. The existing ECG/latent provenance and temporal eligibility limitations remain.

This is a candidate-variable inventory, **not** a finalized adjustment set. A clinical indication and contraindication assessment, medication time zero, and temporal ordering are required before a DAG or adjustment design.

## Decision

**B — Aspirin research is feasible, but specific data limitations must be resolved first.**

Evidence: (1) the previous-MI longitudinal population and competing-death/incomplete-follow-up framework are available; (2) a prescription-window proxy and a distinct in-hospital indicator are each observed in 4,656 of 7,545 eligible admissions; (3) aspirin eMAR records link to 2540 index admissions, with 2509 having valid documented administrations; (4) only 21 of the 779 `aspirin_before=1` index admissions have a linked valid eMAR administration; and (5) acute-coded MI candidates have transfer/continuation uncertainty and no clinical adjudication. Lack of a documented in-hospital administration does not negate a pre-admission prescription or prove non-use. Exposure semantics, missing exposure, clinical endpoint, and confounding information must be addressed before causal design or estimation.

## Reproducibility

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m causal_models.aspirin.phase1_exposure_feasibility.scan_aspirin_source_timestamps --mimic-root <existing-extracted-mimic-iv-root>
.\.venv\Scripts\python.exe -m causal_models.aspirin.phase1_exposure_feasibility.analyze_aspirin_phase1
```

The source scanner reads the already extracted compressed CSV tables and does not extract the `.rar` archive. The report generator reuses processed master splits, longitudinal cohort/outcome outputs, and the timestamp summary; both scripts write only under this aspirin Phase 1 directory.
