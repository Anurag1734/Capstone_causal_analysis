# Statistical Causal Discovery Report: Antecedent HbA1c and Subsequent Myocardial Infarction

> **MANDATORY SCIENTIFIC STATUS STATEMENTS:**  
> 1. *"The discovered graphs are statistical causal-discovery outputs and do not by themselves establish causal truth."*  
> 2. *"The existing domain-informed DAG remains a candidate hypothesis until reconciliation with statistical evidence, literature, and expert clinical validation."*  
>  
> *Safeguards Enforced: No causal effects (ATE/CATE) have been estimated, no adjustment sets have been finalized, and no algorithmic output has been declared the final causal DAG.*

## Run-State / Continuation Audit

The existing artifacts show that the following stages had completed before interruption:

| Stage | Existing completion evidence |
|:---|:---|
| Cohort/data preparation | `data/hba1c_discovery_90d.csv`, `data/hba1c_discovery_180d.csv`, and `data/hba1c_discovery_365d.csv` exist; `results/data_quality_diagnostics.json` exists. |
| Primary PC, GES, and FCI runs | Each method has a saved graph text file and edge CSV in `results/`; PC also has `results/pc_sepsets.json`. The saved graphs identify the 180-day data and report N=6,575. |
| Bootstrap stability | `results/bootstrap_edge_frequency.csv` contains all 21 candidate pairs and frequencies in 0.2-percentage-point increments, consistent with the configured 500 replicates. |
| Cross-method comparison and sensitivity analyses | `results/algorithm_comparison.csv`, `results/domain_vs_discovery.csv`, and `results/sensitivity_analysis_summary.json` exist. |
| Report | Sections 1–25 of this report were already present. This reconciliation updates the interpretation; it does not restart those analyses. |

No run log or checkpoint file is present, so stage completion is inferred from saved artifacts rather than a recorded process exit status. No image-format graphs or final DAG are present. `bootstrap_stability.py` documents a `bootstrap_summary.json` output, but its current implementation writes only `bootstrap_edge_frequency.csv`; that JSON is absent and was not treated as a required completed artifact. Only this report reconciliation is being continued.

---

## 1. Objective

The objective of this stage is to move from the domain-informed candidate DAG specified in `HBA1C_CAUSAL_FRAMEWORK.md` into the **Statistical Causal Discovery Stage** for the HbA1c clinical-risk-factor branch.

Specifically, we deploy a principled, reproducible discovery pipeline to evaluate:
1. Which relationships between antecedent glycemic state, clinical covariates, and subsequent MI are statistically supported by observational data.
2. Which dependencies remain stable under 500 bootstrap resampling replicates.
3. Where constraint-based (PC), score-based (GES), and latent-variable (FCI) algorithms agree or disagree.
4. How data-driven structural findings compare against the domain-informed prior hypothesis.
5. Whether the estimated PAG marks are compatible with latent-confounding structures under FCI's assumptions.

---

## 2. Reconstructed Existing Causal Question

In accordance with `HBA1C_CAUSAL_FRAMEWORK.md`, the causal question is preserved exactly as formulated:

> *"Among adult hospitalized patients with established diabetes mellitus who have a qualifying antecedent HbA1c measurement prior to prospective baseline, what is the effect of antecedent glycemic state (e.g., controlled HbA1c < 7.0% vs. above-target HbA1c $\ge$ 7.0%) on the risk of a subsequent MI-coded hospital admission during prospective post-discharge follow-up?"*

### Core Architectural Fields
- **Target Population:** Adult patients with diagnosed diabetes mellitus (ICD-9 250*, ICD-10 E08–E13) on or before baseline admission, who survive and are discharged from an eligible non-MI baseline hospital admission.
- **Candidate Exposure ($A$):** Antecedent HbA1c state dichotomized at the standard ADA threshold ($0 = < 7.0\%$, $1 = \ge 7.0\%$). Continuous HbA1c is evaluated in sensitivity analyses.
- **Exposure Timing:** Most recent valid measurement within a strictly antecedent lookback window (Primary: 180 days; Sensitivities: 90 days and 365 days). All measurements strictly precede the calendar date of the baseline admission ($t_{\text{lab}} < t_0$).
- **Baseline / Time Zero ($t_0$):** Earliest eligible non-MI hospital admission per patient (`admittime` / `dischtime`).
- **Target Outcome ($Y$):** First subsequent acute myocardial infarction hospital admission occurring strictly after baseline discharge ($t_{\text{MI}} > t_0$).
- **Outcome Timing:** Formal hospital admission timestamp (`admittime`) of the subsequent MI encounter.
- **Follow-up Horizon:** From baseline time zero until first subsequent MI admission, all-cause in-hospital death / documented state death, or end of recorded observation horizon (`observation_end`).
- **Censoring Information:** Administrative censoring at `observation_end`; right-censoring at death (`dod`) without documented MI readmission.
- **Candidate Baseline Confounders ($L$):** Chronological age (`anchor_age`), biological sex (`sex_male`), hypertension history, chronic kidney disease (`ckd`), prior myocardial infarction history (`prior_mi`).
- **Quarantined Variables:** All 95 engineered ECG features and all 64 $z_{\text{ecg}}$ dimensions (identified as post-exposure descendants, mediators, or colliders).
- **Unresolved Assumptions:** Compound treatment versions (consistency assumption for biomarker states); absence of outpatient longitudinal prescription fill history; single-center outcome ascertainment at BIDMC.

---

## 3. Existing Domain-Informed Candidate DAG (Prior Hypothesis)

Extracted directly from `HBA1C_CAUSAL_FRAMEWORK.md`, the candidate DAG serves as the prior structural hypothesis against which statistical discovery is compared.

| Source | Target | Hypothesized Relationship | Clinical / Methodological Rationale | Evidence Type | Status |
|:---|:---|:---:|:---|:---|:---|
| `anchor_age` | `hba1c_state` | Direct Cause | Aging drives progressive pancreatic beta-cell dysfunction and insulin resistance | domain_knowledge | Candidate Confounder Edge |
| `anchor_age` | `subsequent_mi` | Direct Cause | Aging is the strongest independent predictor of arterial plaque rupture and MI | domain_knowledge | Candidate Confounder Edge |
| `sex_male` | `hba1c_state` | Direct Cause | Sex differences in visceral adiposity, androgen levels, and insulin sensitivity | domain_knowledge | Candidate Confounder Edge |
| `sex_male` | `subsequent_mi` | Direct Cause | Male sex is an established strong risk factor for earlier onset and higher CAD incidence | domain_knowledge | Candidate Confounder Edge |
| `hypertension` | `hba1c_state` | Shared Factor | Shared metabolic syndrome, endothelial dysfunction, common outpatient care targets | domain_knowledge | Candidate Confounder Edge |
| `hypertension` | `subsequent_mi` | Direct Cause | Endothelial shear stress, arterial remodeling, increased myocardial oxygen demand | domain_knowledge | Candidate Confounder Edge |
| `ckd` | `hba1c_state` | Measurement/Target | Altered RBC turnover, reduced insulin clearance, intentional guideline target relaxation | domain_knowledge | Candidate Confounder Edge |
| `ckd` | `subsequent_mi` | Direct Cause | Vascular calcification, volume overload, systemic uremic cardiotoxicity | domain_knowledge | Candidate Confounder Edge |
| `prior_mi` | `hba1c_state` | Clinical Target Modifier | Secondary CAD prevention alters glycemic goals to prevent arrhythmia-inducing hypoglycemia | domain_knowledge | Candidate Confounder Edge |
| `prior_mi` | `subsequent_mi` | Direct Cause | Established coronary atherothrombosis indicates vastly elevated recurrence risk | domain_knowledge | Candidate Confounder Edge |
| `hba1c_state` | `subsequent_mi` | **Target Causal Edge** | Chronic hyperglycemia causes advanced glycation end-products, oxidative stress, thrombosis | domain_knowledge | **Primary Target Causal Edge** |
| `hypertension` | `ckd` | Direct Cause | Hypertensive nephrosclerosis drives progressive renal microvascular destruction | domain_knowledge | Intra-Covariate Edge |
| `prior_mi` | `ckd` | Shared / Bidirectional | Cardiorenal syndrome and generalized systemic atherosclerosis | domain_knowledge | Intra-Covariate Edge |
| `anchor_age` | `ckd` | Direct Cause | Age-related nephrosclerosis and progressive decline in GFR | domain_knowledge | Intra-Covariate Edge |
| `anchor_age` | `hypertension` | Direct Cause | Age-related arterial stiffening and essential hypertension | domain_knowledge | Intra-Covariate Edge |
| `anchor_age` | `prior_mi` | Direct Cause | Cumulative lifetime exposure to atherogenic risk factors | domain_knowledge | Intra-Covariate Edge |
| `sex_male` | `prior_mi` | Direct Cause | Premenopausal female vascular protection leads to higher male CAD events | domain_knowledge | Intra-Covariate Edge |
| `sex_male` | `ckd` | Risk Determinant | Male sex associated with differing etiology and progression of renal failure | domain_knowledge | Intra-Covariate Edge |

---

## 4. Discovery Dataset Definition

The discovery dataset was constructed from the verified longitudinal MIMIC-IV cohort files (`admissions_chronology.parquet`, `diagnoses_all.parquet`, `mi_admissions.parquet`, `patients_demographics.parquet`, and `clinical_factor_timing_audit.parquet`).

- **Primary Analytic Cohort (180-Day Antecedent Window):**
  - **Sample Size ($N$):** **6,575** adult diabetic patients.
  - **Observed Subsequent MI Events:** **763** patients (11.60% cumulative incidence).
  - **File Location:** `causal_discovery/hba1c/data/hba1c_discovery_180d.csv`.
- **Sensitivity Cohort A (90-Day Antecedent Window):**
  - **Sample Size ($N$):** **4,818** adult diabetic patients.
  - **Observed Subsequent MI Events:** **534** patients (11.08% cumulative incidence).
  - **File Location:** `causal_discovery/hba1c/data/hba1c_discovery_90d.csv`.
- **Sensitivity Cohort B (365-Day Antecedent Window):**
  - **Sample Size ($N$):** **8,042** adult diabetic patients.
  - **Observed Subsequent MI Events:** **949** patients (11.80% cumulative incidence).
  - **File Location:** `causal_discovery/hba1c/data/hba1c_discovery_365d.csv`.

---

## 5. Temporal Eligibility Hierarchy

The causal discovery dataset strictly adheres to the directed prospective hierarchy:

$$\text{Pre-baseline Antecedent Information } (t_{\text{lab}} < t_0) \longrightarrow \text{Baseline Time Zero } (t_0) \longrightarrow \text{Future Outcome } (t_{\text{MI}} > t_0)$$

1. **No Inpatient Exposure Leakage:** Every selected HbA1c occurred on a calendar date strictly prior to baseline admission (`chartdate < basedate`). Measurements from the baseline admission or same-day ED visits were excluded.
2. **Pre-Existing Comorbidity Diagnoses:** Hypertension, CKD, and diabetes were restricted to diagnoses recorded on or before the baseline admission date.
3. **Prior MI History:** Restricted to acute MI hospital admissions that concluded strictly prior to baseline admission (`admittime_mi < admittime_base`).
4. **Prospective Outcome:** Restricted to MI hospital admissions occurring strictly after baseline admission (`admittime_mi > admittime_base`).

---

## 6. Variable Inclusion and Exclusion Decisions

| Variable | Decision | Justification |
|:---|:---:|:---|
| `anchor_age` | **INCLUDED** | Baseline demographic confounder; verified available at baseline. |
| `sex_male` | **INCLUDED** | Baseline demographic confounder; invariant biological characteristic. |
| `hypertension` | **INCLUDED** | Documented pre-existing vascular comorbidity diagnosed on/before $t_0$. |
| `ckd` | **INCLUDED** | Documented chronic renal disease diagnosed on/before $t_0$. |
| `prior_mi` | **INCLUDED** | Confirmed prior acute MI event preceding baseline admission. |
| `hba1c_state` / `hba1c` | **INCLUDED** | Primary antecedent exposure; strictly preceding baseline time zero. |
| `subsequent_mi` | **INCLUDED** | Primary prospective target outcome; strictly following baseline discharge. |
| Identifiers (`study_id`, `SubjectID`, `hadm_id`) | **EXCLUDED** | Administrative keys; non-causal. |
| `Label_Troponin`, `index_mi_time`, `time_diff_hours` | **EXCLUDED** | Inpatient troponin outcome metadata; cause of index-admission leakage. |
| `is_MI` (master stay) | **EXCLUDED** | Retrospective index-stay flag; induces Berkson's collider bias. |
| Post-baseline medications (`*_during`, `*_after`) | **EXCLUDED** | Downstream inpatient/discharge treatments; violate baseline temporal ordering. |
| Pre-baseline medications (`*_before`) | **EXCLUDED** | Outpatient prescription fill times are unlinked in master; excluded to avoid temporal misclassification. |
| 95 Engineered ECG Features | **QUARANTINED** | Recorded at hospital presentation ($t_{\text{ecg}} \approx t_0$), temporally following antecedent HbA1c ($t_{\text{lab}} < t_{\text{ecg}}$). Descendants/mediators. |
| 64 $z_{\text{ecg}}$ Latent Dimensions | **QUARANTINED** | Latent representation of cardiac electrophysiology at presentation. Adjusting induces overcontrolling and collider bias. |

---

## 7. Data-Quality Diagnostics (Step 5 Audit)

A comprehensive data quality diagnostic audit was executed across all variables in the primary discovery cohort ($N = 6,575$):

| Variable | Data Type | Missing Count (%) | Unique Values | Mean (Std) | Median [Q1, Q3] | Range [Min, Max] | Variance |
|:---|:---:|---:|---:|:---:|:---:|:---:|---:|
| `anchor_age` | Continuous | 0 (0.0%) | 73 | 64.23 (14.03) | 65.0 [55.0, 75.0] | [18.0, 91.0] | 196.81 |
| `sex_male` | Binary | 0 (0.0%) | 2 | 0.505 (0.500) | 1.0 [0.0, 1.0] | [0.0, 1.0] | 0.250 |
| `hypertension` | Binary | 0 (0.0%) | 2 | 0.603 (0.489) | 1.0 [0.0, 1.0] | [0.0, 1.0] | 0.239 |
| `ckd` | Binary | 0 (0.0%) | 2 | 0.201 (0.401) | 0.0 [0.0, 0.0] | [0.0, 1.0] | 0.161 |
| `prior_mi` | Binary | 0 (0.0%) | 2 | 0.088 (0.284) | 0.0 [0.0, 0.0] | [0.0, 1.0] | 0.081 |
| `hba1c` | Continuous | 0 (0.0%) | 117 | 7.40 (1.65) | 7.0 [6.3, 8.0] | [4.4, 18.2] | 2.73 |
| `hba1c_state` | Binary | 0 (0.0%) | 2 | 0.501 (0.500) | 1.0 [0.0, 1.0] | [0.0, 1.0] | 0.250 |
| `subsequent_mi` | Binary | 0 (0.0%) | 2 | 0.116 (0.320) | 0.0 [0.0, 0.0] | [0.0, 1.0] | 0.103 |

**Key Diagnostic Findings:**
- Zero missing values across all seven primary discovery variables ($0.0\%$ missingness).
- Non-zero variance across all covariates; no constant or near-constant variables.
- Ideal positivity balance for the primary exposure `hba1c_state`: 50.1% $\ge 7.0\%$ vs. 49.9% $< 7.0\%$.
- There were 763 subsequent MI events. Event count alone does not establish power for a particular conditional-independence test; no formal power or sparse-cell diagnostic is saved.

---

## 8. Variable Types and Encoding Strategy

The dataset exhibits mixed variable types:
- **Continuous:** `anchor_age` (years), `hba1c` (percentage).
- **Binary Indicators:** `sex_male`, `hypertension`, `ckd`, `prior_mi`, `hba1c_state`, `subsequent_mi`.

To prevent invalid distributional assumptions:
1. **Primary Representation (Mixed / Linear-Gaussian Approximation):** Continuous `anchor_age`, binary covariates encoded as $\{0, 1\}$, binary `hba1c_state` $\{0, 1\}$, binary `subsequent_mi` $\{0, 1\}$. Evaluated via Fisher's $Z$ test in PC/FCI and BIC in GES.
2. **Sensitivity Representation (Fully Discretized):** `anchor_age` discretized into standard clinical age brackets ($<50$, $50-64$, $65-74$, $\ge 75$), all comorbidity indicators $\{0, 1\}$, binary `hba1c_state`, binary `subsequent_mi`. Evaluated via Chi-square ($\chi^2$) conditional independence tests in PC/FCI and BDeu scoring in GES.

---

## 9. Missing-Data Strategy

Because every patient selected into the prospective cohort possesses complete records for demographics, antecedent HbA1c, prior diagnoses, and longitudinal event follow-up:
- **Missingness Handling:** Complete case analysis was executed without imputation.
- **Selection into Testing ($R_{\text{test}}$):** Missingness of antecedent HbA1c in the general baseline population reflects clinical testing decisions. As established in the candidate framework, the target trial is formally conditioned on patients having a qualifying test.

---

## 10. PC Algorithm Methodology

- **Implementation:** `causallearn.search.ConstraintBased.PC.pc` (causal-learn v0.1.4.8).
- **Conditional Independence Test:** Fisher's $Z$ test (`fisherz`), with Chi-square test (`chisq`) in discrete sensitivity.
- **Significance Threshold ($\alpha$):** 0.05 (primary); sensitivity tested at $\alpha = 0.01$ and $\alpha = 0.10$.
- **Maximum Conditioning Set Size:** Depth limit = 4.
- **Random Seed:** 42.

---

## 11. GES Algorithm Methodology

- **Implementation:** `causallearn.search.ScoreBased.GES.ges` (causal-learn v0.1.4.8).
- **Score Function:** Local BIC score (`local_score_BIC`), with BDeu score (`local_score_BDeu`) in discrete sensitivity.
- **Search Strategy:** Two-phase greedy search (forward equivalence addition followed by backward equivalence elimination).
- **Random Seed:** 42.

---

## 12. FCI Algorithm Methodology

- **Implementation:** `causallearn.search.ConstraintBased.FCI.fci` (causal-learn v0.1.4.8).
- **Purpose:** Specifically selected to detect **latent/unmeasured confounding** without assuming causal sufficiency.
- **Conditional Independence Test:** Fisher's $Z$ test (`fisherz`), with Chi-square test (`chisq`) in discrete sensitivity.
- **Significance Threshold ($\alpha$):** 0.05.
- **Edge Mark Semantics:**
  - `-->` (Tail to Arrow): A directed ancestral mark in the estimated PAG, not by itself proof of a causal effect.
  - `<->` (Arrow to Arrow / Bidirected): An arrowhead at both endpoints; compatible with latent-confounding structures under FCI's assumptions, but does not identify a particular unmeasured variable or prove that confounding is the true explanation.
  - `o->` (Circle to Arrow): Partially oriented PAG edge; the circle endpoint is unresolved.
  - `o-o` (Circle to Circle): Adjacency with both endpoints unresolved.

---

## 13. Bootstrap Stability Methodology

- **Replicates:** **500 independent bootstrap samples** drawn with replacement ($N = 6,575$).
- **Metrics Computed for All 21 Candidate Pairs:**
  1. *Adjacency Selection Frequency (%):* Proportion of bootstrap replicates in which the algorithm retained an edge.
  2. *Primary Orientation Selection Frequency (%):* Proportion of replicates yielding the dominant edge direction/mark.
  3. *Cross-Method Mean Frequency (%):* Average adjacency frequency across PC, GES, and FCI.
- **Strict Terminology:** Results are reported strictly as *"bootstrap edge-selection stability"*, **never** as "causal probability."

---

## 14. PC Discovery Results

On the primary discovery dataset ($N = 6,575$), PC discovered **12 edges**:
1. `hypertension -> anchor_age` (TAIL $\to$ ARROW)
2. `ckd -> anchor_age` (TAIL $\to$ ARROW)
3. `hba1c_state -> anchor_age` (TAIL $\to$ ARROW)
4. `anchor_age -> subsequent_mi` (TAIL $\to$ ARROW)
5. `ckd -> sex_male` (TAIL $\to$ ARROW)
6. `prior_mi -> sex_male` (TAIL $\to$ ARROW)
7. `hba1c_state -> sex_male` (TAIL $\to$ ARROW)
8. `hypertension -> ckd` (TAIL $\to$ ARROW)
9. `prior_mi -> ckd` (TAIL $\to$ ARROW)
10. `ckd -> subsequent_mi` (TAIL $\to$ ARROW)
11. `prior_mi -> subsequent_mi` (TAIL $\to$ ARROW)
12. **`hba1c_state -> subsequent_mi`** (TAIL $\to$ ARROW)

---

## 15. GES Discovery Results

GES discovered **11 edges** (saved BIC score = $-2,858.6289673833535$):
1. `hypertension -> anchor_age`
2. `ckd -> anchor_age`
3. `hba1c_state -> anchor_age`
4. `anchor_age -> subsequent_mi`
5. `ckd -> sex_male`
6. `prior_mi -> sex_male`
7. `hypertension -> ckd`
8. `prior_mi -> ckd`
9. `ckd -> subsequent_mi`
10. `prior_mi -> subsequent_mi`
11. **`hba1c_state -> subsequent_mi`**

*Agreement with PC:* GES agrees with PC on 11 of 12 edges, omitting only the weak `hba1c_state -> sex_male` edge.

---

## 16. FCI Discovery Results (Partial Ancestral Graph)

FCI discovered **12 PAG edges**:
1. `hypertension -> anchor_age` (TAIL $\to$ ARROW)
2. `ckd -> anchor_age` (TAIL $\to$ ARROW)
3. `anchor_age <-> hba1c_state` (ARROW $\leftrightarrow$ ARROW PAG mark)
4. `anchor_age -> subsequent_mi` (TAIL $\to$ ARROW)
5. `ckd -> sex_male` (TAIL $\to$ ARROW)
6. `prior_mi -> sex_male` (TAIL $\to$ ARROW)
7. `sex_male <-> hba1c_state` (ARROW $\leftrightarrow$ ARROW PAG mark)
8. `hypertension o-> ckd` (CIRCLE $\to$ ARROW)
9. `prior_mi o-> ckd` (CIRCLE $\to$ ARROW)
10. `ckd -> subsequent_mi` (TAIL $\to$ ARROW)
11. `prior_mi -> subsequent_mi` (TAIL $\to$ ARROW)
12. **`hba1c_state <-> subsequent_mi`** (ARROW $\leftrightarrow$ ARROW PAG mark)

The `hba1c_state <-> subsequent_mi` endpoint pattern is FCI's estimated PAG mark. It is compatible with latent-confounding explanations under the FCI model, but does not establish that the observed association is in fact driven by any particular unmeasured factor.

---

## 17. Bootstrap Stability Analysis (500 Replicates)

The complete bootstrap stability results across all 21 variable pairs are summarized below:

| Variable Pair | PC Adjacency (%) | PC Dominant Orientation (%) | GES Adjacency (%) | GES Dominant Orientation (%) | FCI Adjacency (%) | FCI Dominant Orientation (%) | Mean Adjacency (%) | Stability Tier |
|:---|---:|:---|---:|:---|---:|:---|---:|:---:|
| `anchor_age - hypertension` | 100.0% | `anchor_age -> htn` (100%) | 100.0% | `anchor_age -> htn` (95.8%) | 100.0% | `htn -> anchor_age` (70.4%) | **100.0%** | Highly Stable |
| `anchor_age - hba1c_state` | 100.0% | `anchor_age -> hba1c` (100%) | 100.0% | `anchor_age -> hba1c` (97.2%) | 100.0% | `age <-> hba1c` (85.6%) | **100.0%** | Highly Stable |
| `anchor_age - ckd` | 100.0% | `anchor_age -> ckd` (100%) | 100.0% | `anchor_age -> ckd` (99.8%) | 100.0% | `ckd -> anchor_age` (73.8%) | **100.0%** | Highly Stable |
| `ckd - sex_male` | 100.0% | `ckd -> sex_male` (97.8%) | 100.0% | `ckd -> sex_male` (100%) | 100.0% | `ckd -> sex_male` (49.8%) | **100.0%** | Highly Stable |
| `anchor_age - subsequent_mi` | 100.0% | `anchor_age -> mi` (98.8%) | 100.0% | `anchor_age -> mi` (97.0%) | 100.0% | `anchor_age -> mi` (39.8%) | **100.0%** | Highly Stable |
| `ckd - subsequent_mi` | 100.0% | `ckd -> mi` (98.6%) | 100.0% | `ckd -> mi` (100%) | 100.0% | `ckd -> mi` (48.2%) | **100.0%** | Highly Stable |
| `prior_mi - subsequent_mi` | 100.0% | `prior_mi -> mi` (95.2%) | 100.0% | `prior_mi -> mi` (92.0%) | 100.0% | `prior_mi -> mi` (50.2%) | **100.0%** | Highly Stable |
| `ckd - hypertension` | 100.0% | `ckd -> htn` (97.2%) | 100.0% | `ckd -> htn` (99.8%) | 100.0% | `htn o-> ckd` (88.6%) | **100.0%** | Highly Stable |
| `ckd - prior_mi` | 100.0% | `ckd -> prior_mi` (93.4%) | 100.0% | `ckd -> prior_mi` (100%) | 100.0% | `prior_mi o-> ckd` (79.4%) | **100.0%** | Highly Stable |
| `prior_mi - sex_male` | 99.2% | `prior_mi -> sex_male` (94.0%) | 95.6% | `prior_mi -> sex_male` (94.8%) | 99.0% | `prior_mi -> sex_male` (39.0%) | **97.9%** | Highly Stable |
| **`hba1c_state - subsequent_mi`** | **88.4%** | `hba1c -> mi` (83.4%) | **77.0%** | `hba1c -> mi` (57.2%) | **88.4%** | **`hba1c <-> mi` (70.8%)** | **84.6%** | **Moderately Stable** |
| `hba1c_state - sex_male` | 71.4% | `hba1c -> sex_male` (71.4%) | 38.6% | `hba1c -> sex_male` (38.4%) | 71.4% | `hba1c <-> sex_male` (69.6%) | **60.5%** | Moderate / Mixed |
| `anchor_age - prior_mi` | 12.6% | `anchor_age -> prior_mi` | 71.4% | `anchor_age -> prior_mi` | 12.0% | `anchor_age <-> prior_mi` | **32.0%** | Weak / Unstable |
| `ckd - hba1c_state` | 0.4% | `ckd -> hba1c` | 45.8% | `ckd -> hba1c` | 0.4% | `ckd <-> hba1c` | **15.5%** | Weak / Disagreeing |
| `hypertension - subsequent_mi` | 9.8% | `htn -> mi` | 5.6% | `htn -> mi` | 9.8% | `htn o-> mi` | **8.4%** | Absent / Screened Off |
| `sex_male - subsequent_mi` | 10.6% | `sex_male -> mi` | 2.4% | `sex_male -> mi` | 10.6% | `sex_male <-> mi` | **7.9%** | Absent / Screened Off |
| `anchor_age - sex_male` | 8.8% | `anchor_age -> sex_male` | 2.8% | `anchor_age -> sex_male` | 8.8% | `anchor_age <-> sex_male` | **6.8%** | Absent |
| `hypertension - sex_male` | 8.4% | `htn -> sex_male` | 2.8% | `htn -> sex_male` | 5.2% | `htn <-> sex_male` | **5.5%** | Absent |
| `hypertension - prior_mi` | 5.4% | `htn -> prior_mi` | 1.8% | `htn -> prior_mi` | 5.4% | `htn o-> prior_mi` | **4.2%** | Absent |
| `hba1c_state - hypertension` | 3.4% | `hba1c -> htn` | 0.4% | `hba1c -> htn` | 3.2% | `hba1c <-> htn` | **2.3%** | Absent |
| `hba1c_state - prior_mi` | 1.0% | `prior_mi - hba1c` | 0.8% | `prior_mi - hba1c` | 1.0% | `hba1c <-> prior_mi` | **0.9%** | Absent |

---

## 18. Cross-Algorithm Comparison (PC vs. GES vs. FCI)

| Category | Description | Edge Pairs |
|:---|:---|:---|
| **A. Adjacency in all three primary graphs** | Pair appears in PC, GES, and FCI; endpoint marks and orientations are not necessarily the same. | `anchor_age - hypertension`, `anchor_age - ckd`, `ckd - sex_male`, `anchor_age - subsequent_mi`, `ckd - subsequent_mi`, `prior_mi - subsequent_mi`, `ckd - hypertension`, `ckd - prior_mi`, `prior_mi - sex_male`, **`hba1c_state - subsequent_mi`**, `anchor_age - hba1c_state` |
| **B. Different primary-graph adjacency selection** | Present in PC and FCI but absent in GES. | `hba1c_state - sex_male` (bootstrap adjacency: PC 71.4%, GES 38.6%, FCI 71.4%) |
| **C. Absent from all three primary graphs** | No adjacency in the saved 180-day point-estimate graphs; this is not proof of conditional independence in the population. | `anchor_age - prior_mi`, `ckd - hba1c_state`, `hypertension - subsequent_mi`, `sex_male - subsequent_mi`, `anchor_age - sex_male`, `hypertension - sex_male`, `hypertension - prior_mi`, `hba1c_state - hypertension`, `hba1c_state - prior_mi` |

**Important correction:** In the primary 180-day result, PC and GES both detect the `hba1c_state - subsequent_mi` adjacency. Their endpoint marks differ from FCI's; this is an orientation/mark disagreement, not a disagreement about whether the pair is adjacent. GES does omit `hba1c_state - sex_male` in this primary graph.

---

## 19. Domain DAG vs. Statistical Discovery Comparison

Below is the edge-by-edge reconciliation between the domain-informed candidate DAG and statistical discovery:

| Edge Pair | Hypothesized Domain Edge | Discovered Statistical Status | Bootstrap Frequency | Classification Category | Scientific Interpretation |
|:---|:---:|:---:|---:|:---:|:---|
| `hba1c_state - subsequent_mi` | $hba1c \to MI$ (domain hypothesis) | Adjacent in all three; PC/GES directed marks, FCI bidirected mark | **84.6%** | **Adjacency supported; interpretation unresolved** | The adjacency is not a causal effect estimate. The FCI mark is compatible with latent-confounding structures, not proof of a specific confounder. |
| `anchor_age - subsequent_mi` | $Age \to MI$ | Adjacent in all three; directed mark in saved graphs | **100.0%** | **Stable adjacency; causal direction not established by discovery alone** | Bootstrap stability describes edge selection, not causal probability or causal truth. |
| `ckd - subsequent_mi` | $CKD \to MI$ | Adjacent in all three; directed mark in saved graphs | **100.0%** | **Stable adjacency; causal direction not established by discovery alone** | Bootstrap stability describes edge selection, not causal probability or causal truth. |
| `prior_mi - subsequent_mi` | $Prior\_MI \to MI$ | Adjacent in all three; directed mark in saved graphs | **100.0%** | **Stable adjacency; causal direction not established by discovery alone** | Bootstrap stability describes edge selection, not causal probability or causal truth. |
| `ckd - hypertension` | $HTN \to CKD$ | Directed in PC/GES; $HTN \circ\!\!\to CKD$ in FCI | **100.0%** | **1. Domain + Statistically Supported** | Robust cardiorenal vascular dependency. |
| `ckd - prior_mi` | $Prior\_MI \to CKD$ | Directed in PC/GES; $Prior\_MI \circ\!\!\to CKD$ in FCI | **100.0%** | **1. Domain + Statistically Supported** | Cardiorenal comorbidity dependency. |
| `anchor_age - hypertension` | $Age \to HTN$ | Adjacent in all; PC/GES point to hypertension -> age, FCI to hypertension -> age | **100.0%** | **Orientation differs from candidate DAG** | The estimated marks differ from the domain hypothesis; the search did not impose temporal background constraints, and the output alone does not adjudicate direction. |
| `anchor_age - ckd` | $Age \to CKD$ | Adjacent in all; PC/GES/FCI point to CKD -> age | **100.0%** | **Orientation differs from candidate DAG** | The estimated marks differ from the domain hypothesis; the output alone does not establish the temporal or causal direction. |
| `prior_mi - sex_male` | $Sex \to Prior\_MI$ | Adjacent in all; PC/GES/FCI point to prior_mi -> sex_male | **97.9%** | **Orientation differs from candidate DAG** | The estimated marks differ from the domain hypothesis; no diagnostic here isolates why, and the output alone does not establish causal direction. |
| `hypertension - subsequent_mi` | $HTN \to MI$ | **No primary adjacency** | **8.4%** | **Not selected in primary graph; low bootstrap selection** | This does not establish population conditional independence, absence of a causal effect, or mediation. |
| `sex_male - subsequent_mi` | $Sex \to MI$ | **No primary adjacency** | **7.9%** | **Not selected in primary graph; low bootstrap selection** | This does not establish population conditional independence, absence of a causal effect, or mediation. |
| `ckd - hba1c_state` | $CKD \to hba1c$ | **No primary adjacency** | **15.5%** | **Not selected in primary graph; low bootstrap selection** | Non-selection is not proof of conditional independence. |
| `hypertension - hba1c_state` | $HTN \to hba1c$ | **No primary adjacency** | **2.3%** | **Not selected in primary graph; low bootstrap selection** | Non-selection is not proof of conditional independence. |
| `prior_mi - hba1c_state` | $Prior\_MI \to hba1c$ | **No primary adjacency** | **0.9%** | **Not selected in primary graph; low bootstrap selection** | Non-selection is not proof of conditional independence. |

---

## 20. Methodological Reconciliation of the HbA1c-Related Disagreements

### 20.1 Primary run: data and configuration actually used

All three saved primary graphs use `hba1c_discovery_180d.csv`, with **N = 6,575** and the same seven columns: `anchor_age`, `sex_male`, `hypertension`, `ckd`, `prior_mi`, `hba1c_state`, and `subsequent_mi`. The files identify causal-learn v0.1.4.8.

| Method | Saved primary configuration | Significance / score penalty |
|:---|:---|:---|
| PC | `fisherz`, $\alpha=0.05$, depth/max conditioning-set size 4, seed 42 | $\alpha=0.05$ is the CI decision threshold. |
| GES | `local_score_BIC`, `maxP` not specified by the run script (left at the library default), seed 42 | No $\alpha$ applies. BIC supplies the score's complexity penalty; the run script does not set or record a separate penalty discount. Saved score: $-2,858.6289673833535$. |
| FCI | `fisherz`, $\alpha=0.05$, depth/max conditioning-set size 4, seed 42 | $\alpha=0.05$ is the CI decision threshold. |

The data-quality diagnostic reports zero missing values for every discovery variable, including both the exposure and outcome. The cohort is therefore complete for the analyzed columns; the described approach is complete-case selection with no imputation. This does not remove selection into having a qualifying antecedent HbA1c test, and no alternative missingness strategy was compared.

In the primary representation, `anchor_age` is continuous and the other six graph variables (including binary `hba1c_state` and `subsequent_mi`) are 0/1. The continuous-HbA1c sensitivity substitutes `hba1c` for `hba1c_state`; the discrete sensitivity uses four `age_bracket` categories plus the five binary variables. The saved sensitivity summary does not report missingness changes or per-variable diagnostics for alternative cohorts.

PC and FCI test conditioning sets only up to size 4. With seven graph variables, a pair has five other variables available, so conditioning on all five simultaneously was outside the configured depth limit. The saved PC separation-set file concerns pairs removed from the graph; it supplies no separating set for a pair retained as adjacent. GES has no CI alpha or conditioning-set depth parameter in this invocation; `maxP` was omitted.

Fisher-Z is a partial-correlation test, and the primary graph mixes a continuous variable with 0/1 binary variables. The saved run includes no nonlinear CI test, nonlinear functional-form check, residual diagnostic, or alternative nonlinear score. Nonlinearity is therefore a possible untested limitation, **not an evidenced explanation** of these disagreements.

### 20.2 What the primary graphs and bootstrap actually say

| Pair | PC primary result | GES primary result | FCI primary result | Bootstrap adjacency frequency (PC / GES / FCI) | Dominant bootstrap mark/orientation frequency (PC / GES / FCI) |
|:---|:---|:---|:---|:---:|:---|
| `hba1c_state - subsequent_mi` | Adjacent, `hba1c_state -> subsequent_mi` | Adjacent, `hba1c_state -> subsequent_mi` | Adjacent, `hba1c_state <-> subsequent_mi` | **88.4% / 77.0% / 88.4%** | **83.4% / 57.2% / 70.8%** |
| `hba1c_state - sex_male` | Adjacent, `hba1c_state -> sex_male` | No adjacency | Adjacent, `sex_male <-> hba1c_state` | **71.4% / 38.6% / 71.4%** | **71.4% / 38.4% / 69.6%** |

The bootstrap file is based on 500 resamples of size 6,575 with replacement. These frequencies are edge-selection stability across resamples, not probabilities that an edge is true. Thus the target HbA1c–MI pair is **not an FCI-only adjacency in the primary run**: all three algorithms select the pair, while FCI differs in endpoint marks. The HbA1c–sex pair is the primary graph's PC/FCI adjacency that GES omits; its lower GES bootstrap frequency shows instability across resamples, not a demonstrated cause.

### 20.3 Sensitivity evidence and what it does not establish

| Diagnostic already run | HbA1c–MI adjacency result | Supported conclusion |
|:---|:---|:---|
| Lookback window (90d, N=4,818; 180d, N=6,575; 365d, N=8,042) | PC: yes in all; FCI: yes in all; GES: no at 90d, yes at 180d and 365d | GES selection varies across the tested windows/cohorts. Window and sample size change together, so this does not isolate a sample-size or power effect. |
| Continuous `hba1c` in place of binary `hba1c_state` (180d) | Yes in PC, GES, and FCI | The adjacency is not lost in this tested exposure-encoding substitution. The sensitivity summary only records adjacency, not mark, p-value, or effect size. |
| PC/FCI $\alpha=0.01, 0.05, 0.10$ (180d) | Yes at each tested alpha; reported PC/FCI graph edge count is 12 at each | No target-edge sensitivity to these three PC/FCI alpha settings was observed. This does not test GES, whose score has no alpha parameter. |
| Fully discrete: four-level `age_bracket`, `chisq` for PC/FCI, BDeu for GES (180d, N=6,575) | PC: no; GES: no; FCI: yes | Detection differs under this combined encoding/test/score change. Because several inputs change together and no cell-count diagnostic is saved, this establishes sensitivity to the analysis bundle, not a specific sparse-cell or low-power mechanism. |

These results support classifying the disagreement as **algorithmic-assumption difference** (PC/GES use causal-sufficiency interpretations; FCI permits latent variables) and **parameter/representation sensitivity** where adjacencies change in the tested settings. They do **not** establish **possible low power** as a cause: no formal power analysis, matched-size resampling comparison, or sparse-cell diagnostic was performed. No missingness sensitivity was run. Nonlinearity was not tested. The reason for GES's window-dependent selection and the discrete PC/GES omissions therefore remains **unresolved**.

**Classification using the requested categories:**

| Pair / observed disagreement | Supported classification(s) | Not supported by these diagnostics |
|:---|:---|:---|
| `hba1c_state - subsequent_mi`: all primary graphs adjacent but FCI uses arrowheads at both endpoints; GES misses the pair at 90d; PC and GES miss it in the fully discrete analysis bundle | **algorithmic assumption difference**; **latent-confounding sensitivity** for the FCI mark (compatibility only); **parameter sensitivity** across tested windows/settings; **variable-encoding sensitivity** for the fully discrete bundle; **unresolved** as to why detections change | **possible low power**, **missing-data sensitivity**, or **nonlinear relationship** as an established explanation |
| `hba1c_state - sex_male`: PC and FCI adjacent, GES absent in the primary graph; bootstrap frequencies 71.4% / 38.6% / 71.4% | **algorithmic assumption difference** and **unresolved**; the FCI mark is latent-confounding-compatible, not proof | Pair-specific parameter/encoding sensitivity, **possible low power**, missingness, or nonlinearity were not diagnosed |

### 20.4 Adjacency, direction, and causal truth are distinct

1. **FCI detects an adjacency:** In the saved primary PAG, `hba1c_state` and `subsequent_mi` share an edge; the same pair is also adjacent in the saved PC and GES graphs. An adjacency reports the learned graph's retained connection, not a causal-effect estimate.
2. **FCI establishes a causal direction:** It does **not** establish `hba1c_state -> subsequent_mi`; the primary FCI edge has arrowheads at both endpoints. An arrowhead pattern is an endpoint mark in the estimated PAG, not an identified intervention direction.
3. **FCI establishes causal truth:** It does **not** establish that the adjacency or its latent-confounding-compatible mark is the true causal structure, nor does it identify a specific unmeasured confounder. Results depend on algorithmic assumptions, measured variables, tests, and conditioning limits.

For the same reasons, a directed mark from PC or GES is not by itself proof of a true causal effect. No ATE/CATE, adjustment set, or final DAG is produced here.

---

## 21. Comprehensive Sensitivity Analyses (Step 13)

### 21.1 Lookback Window Sensitivity (90d vs. 180d vs. 365d)
| Window | Sample Size ($N$) | Subsequent MI Events | PC Detection | GES Detection | FCI Detection | FCI Mark |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **90 days** | 4,818 | 534 | **YES** | NO | **YES** | Mark not recorded in sensitivity summary |
| **180 days** | 6,575 | 763 | **YES** | **YES** | **YES** | Bidirected ($<->$) |
| **365 days** | 8,042 | 949 | **YES** | **YES** | **YES** | Mark not recorded in sensitivity summary |

*Conclusion:* PC and FCI detect the adjacency in each tested window; GES does not at 90 days and does at 180 and 365 days. Because window and N vary together, this is not evidence that a sample-size threshold or power caused the difference. FCI endpoint marks outside the primary run are not included in the saved summary.

### 21.2 Continuous vs. Binary HbA1c Representation
- **Continuous HbA1c (%):** The sensitivity summary records adjacency in PC, GES, and FCI; it does not save p-values, BIC comparisons, or edge marks.
- **Binary HbA1c ($< 7\%$ vs. $\ge 7\%$):** The primary 180-day graphs contain the pair in all three methods.
- *Conclusion:* The pair remains adjacent in both the tested continuous and binary exposure encodings. This does not establish equivalence of their functional forms or causal interpretations.

### 21.3 Significance Threshold Sensitivity ($\alpha = 0.01, 0.05, 0.10$)
- At each tested $\alpha = 0.01, 0.05, 0.10$, the sensitivity summary records the target adjacency in PC and FCI, with 12 edges in each reported graph.
- *Conclusion:* Target adjacency selection was unchanged across these saved PC/FCI settings. The summary does not report exact p-values; a claim such as $p \ll 0.01$ is not supported by this output.

### 21.4 Fully Discrete Representation ($\chi^2$ Independence & BDeu Scoring)
- In this 180-day sensitivity, `anchor_age` is binned into four clinical age brackets; PC/FCI use `chisq` and GES uses BDeu:
  - PC and GES omit the `hba1c_state - subsequent_mi` adjacency; FCI retains it.
  - This sensitivity simultaneously changes age encoding, PC/FCI CI test, and GES score. The saved results contain no cell-count or power diagnostic, so the omission is evidence of analysis-representation sensitivity, not proof of low power or sparse cells.

---

## 22. Scientific Synthesis & Interpretation

1. **Reproducible but non-causal adjacency evidence:**  
   In the 180-day bootstrap, the HbA1c–MI adjacency frequencies are 88.4% (PC), 77.0% (GES), and 88.4% (FCI). This is selection stability under resampling, not a causal probability, effect, or adjustment result.
2. **Different graph assumptions and marks:**  
   PC and GES select a directed-marked adjacency in the saved primary graph; FCI selects a bidirected-marked adjacency. FCI allows latent variables, unlike the causal-sufficiency interpretation of PC/GES, but its output does not prove actual latent confounding or causal direction.
3. **Some pairs are not selected:**  
   Hypertension–MI and sex–MI are absent in the saved primary graphs, but the absence alone neither proves conditional independence in the population nor establishes mediation or screening-off.
4. **Reconciliation remains open:**  
   Window and discrete-representation sensitivities change detection in some methods. Available diagnostics do not isolate power, nonlinearity, missingness, or an individual parameter as the cause.

---

## 23. Methodological Limitations

1. **Unconstrained Temporal Search:** The saved PC/GES searches include no temporal background constraints, and some estimated marks point into age/sex relative to the domain hypothesis. This report does not infer why those marks arose or impose constraints/finalize a graph.
2. **Mixed-data and functional-form limits:** The primary analysis uses Fisher-Z with continuous and binary-coded variables, and no nonlinear CI/score comparison was saved. The discrete sensitivity changes several settings at once; neither nonlinear misspecification nor low power was diagnosed.
3. **Conditioning depth:** PC and FCI were limited to conditioning sets of size 4, below the 5 other variables available for a pair in this seven-variable graph.
4. **Single-Center EHR Censoring:** Outcome ascertainment is restricted to BIDMC readmissions; out-of-hospital deaths and admissions to outside hospital networks are unobserved.

---

## 24. Specific Edges Requiring Literature Validation

The following structural findings should be cross-referenced with cardiovascular and diabetes literature:
1. **Hypertension-MI Relationship:** How does clinical epidemiological evidence bear on the absent hypertension–subsequent-MI adjacency, without interpreting non-selection as proof of conditional independence or a mediated pathway?
2. **Sex-MI Relationship:** How should the unselected sex–subsequent-MI adjacency in this discovery run be interpreted alongside clinical evidence, without treating graph non-selection as proof of no direct effect or mediation?

---

## 25. Specific Questions for Clinical Expert Validation

Before any statistical causal effect estimation is attempted, the clinical advisory committee must formally adjudicate:

1. **Adjudication of the FCI PAG Mark:**  
   *Given that FCI estimated a bidirected PAG mark between HbA1c and subsequent MI ($hba1c \leftrightarrow MI$), which unmeasured clinical factors, if any, merit investigation as possible explanations, recognizing that the mark does not prove latent confounding or identify a specific factor?*
2. **Enforcement of Temporal Background Knowledge:**  
   *Does the expert committee approve imposing background temporal constraints (Tier 1: Demographics $\to$ Tier 2: Pre-existing Comorbidities $\to$ Tier 3: Antecedent HbA1c $\to$ Tier 4: Baseline Encounter $\to$ Tier 5: Subsequent MI) to forbid algorithmically discovered backwards arrows into Age and Sex?*
3. **Adjustment Set Implications:**  
   *Given that the saved discovery graphs omit the Hypertension–MI and Sex–MI adjacencies, what further evidence is needed before those variables' causal roles or any adjustment decision can be adjudicated?*

---

> **MANDATORY CONCLUDING REMARKS:**  
> The discovered graphs are statistical causal-discovery outputs and do not by themselves establish causal truth.  
> The existing domain-informed DAG remains a candidate hypothesis until reconciliation with statistical evidence, literature, and expert clinical validation.
