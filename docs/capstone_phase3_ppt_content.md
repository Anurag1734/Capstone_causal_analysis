# UE23CS441A — Capstone Project Phase 3
# Project Progress Review – 1

**Project Title:** Causal Model for Myocardial Infarction Risk Analysis  
**Project ID:** PW26_PB_02  
**Project Guide:** Prof. Priya Badrinath  

**Team:**
| Name | SRN |
|---|---|
| Anurag | PES1UG23AM058 |
| Ashwin | PES1UG23CS117 |
| Ashish Kumar B | PES1UG23CS114 |
| Bharath K C | PES1UG23CS143 |

---

# 1. Abstract and Scope of the Project

## Problem Statement

Myocardial Infarction (MI), commonly known as a heart attack, remains one of the leading causes of mortality worldwide. Existing predictive models rely heavily on correlation-based approaches (logistic regression, random forests) that capture statistical associations but fail to answer critical interventional questions such as:

- **"What would happen to this patient's MI risk if we prescribe a statin?"**
- **"Which ECG waveform changes are caused by cardiac ischemia vs. artifact?"**

These questions require **causal reasoning**, which standard ML models cannot provide. Furthermore, traditional models suffer from confounding bias (e.g., sicker patients receive more aggressive treatments, making treatments appear correlated with worse outcomes) and distribution shift (e.g., different ECG machine models produce systematically different waveform characteristics).

## Motivation

1. **Clinical Need**: Clinicians need actionable "what-if" insights — not just risk scores — to guide treatment decisions at the bedside.
2. **ECG Availability**: 12-lead ECGs are ubiquitous, non-invasive, and inexpensive. If ECG morphology causally predicts MI risk, it enables population-level screening.
3. **Causal Gap in Literature**: While predictive models for MI exist (AUROC ~0.85–0.92), almost none provide interpretable causal effects of treatments on outcomes.
4. **Methodological Advancement**: Combining deep generative models (β-VAE) with structural causal models (DoWhy) on large-scale clinical data (MIMIC-IV + MIMIC-IV-ECG) is a novel integration.

## Objectives

1. Build an end-to-end data pipeline from raw MIMIC-IV hospital records and MIMIC-IV-ECG waveforms to a structured, analysis-ready master dataset.
2. Extract clinically meaningful ECG morphological features (ST elevation, T-wave amplitude, QRS duration) using validated signal processing tools.
3. Learn unsupervised latent representations of ECG waveforms using a Convolutional β-Variational Autoencoder (β-VAE).
4. Train baseline predictive models (Logistic Regression, XGBoost) and validate with post-hoc calibration.
5. Design and specify a Structural Causal Model (SCM) using Directed Acyclic Graphs (DAGs) and the DoWhy framework.
6. Estimate Average Treatment Effects (ATE) and Conditional Average Treatment Effects (CATE) of pharmaceutical interventions on MI risk.
7. Generate patient-level counterfactual scenarios (e.g., "What if this patient had been on statins?").

## Proposed Solution

A **13-phase pipeline** that integrates:
- **Data Engineering** (Phases A–F): MIMIC-IV ingestion, cohort labeling, troponin-based MI definition, ECG-to-diagnosis linking, feature extraction, and master dataset construction.
- **Representation Learning** (Phase D): Conv1D β-VAE trained on 375,930 ECGs to produce 64-dimensional latent embeddings (`z_ecg`).
- **Predictive Modeling** (Phase H): 4 baseline models with post-hoc isotonic calibration for probability alignment.
- **Causal Inference** (Phases I–K): DAG specification, SCM implementation with DoWhy, ATE/CATE estimation, and patient-level counterfactual generation.
- **Validation** (Phase L): Sensitivity analyses, refutation tests, and robustness checks.

## Scope of the Project

| In Scope | Out of Scope |
|---|---|
| MIMIC-IV (hospital records) + MIMIC-IV-ECG (waveforms) | Real-time clinical deployment |
| Retrospective cohort study design | Prospective clinical trial |
| Troponin-based MI definition (ACC/AHA guidelines) | ICD-code-only MI labels |
| 12-lead ECG morphological features | Beat-level HRV analysis |
| β-VAE for unsupervised ECG encoding | Supervised deep classifiers (CNN, Transformer) |
| DoWhy causal inference (ATE, CATE) | Multi-stage dynamic treatment regimes |
| Statin, aspirin, beta-blocker treatment effects | Surgical intervention outcomes |

---

# 2. Summary of Work Done in Capstone Project Phase 1

## Work Completed in Phase 1

| Task | Description | Status |
|---|---|---|
| PhysioNet Data Access | Obtained credentialed access to MIMIC-IV v2.2 and MIMIC-IV-ECG v1.0 | ✅ |
| Literature Survey | Reviewed 15+ papers on ECG-based MI prediction, causal inference in healthcare, and VAE architectures | ✅ |
| Pipeline Specification | Designed the 13-phase implementation plan (Phases A–M) with detailed sub-steps | ✅ |
| Raw Data Analysis | Analyzed 10 MIMIC-IV tables (patients, admissions, labevents, chartevents, diagnoses_icd, prescriptions, etc.) | ✅ |
| ECG Format Understanding | Studied WFDB format (.dat/.hea files), 12-lead electrode placement, and signal characteristics | ✅ |
| Technology Selection | Finalized stack: Python 3.12+, PyTorch with CUDA 12.1, DuckDB, scikit-learn, DoWhy, ECGdeli (MATLAB) | ✅ |

## Suggestions Received from Guide / Review Panel

1. **"Validate ECG feature extraction against a gold-standard dataset"** — Addressed by comparing our MATLAB ECGdeli features against PTB-XL+ annotations.
2. **"Clarify the causal vs. predictive distinction"** — The pipeline now explicitly separates predictive baselines (Phase H) from causal analysis (Phase I–K).
3. **"Ensure no data leakage from troponin into prediction features"** — Enforced by strict rule: **troponin is NEVER used as a feature** — it defines the label only.
4. **"Consider class imbalance handling"** — Addressed via `scale_pos_weight` in XGBoost and `class_weight='balanced'` in Logistic Regression, with post-hoc isotonic calibration.

## Improvements Made Based on Suggestions

- Added validation pipeline comparing ECGdeli-extracted features against PTB-XL+ ground truth (univariate, multivariate, and comparative analysis modules).
- Separated troponin completely from feature space — `peak_troponin_before` is explicitly excluded during master dataset construction.
- Added post-hoc calibration (Phase H.1) using Isotonic Regression to align predicted probabilities with true prevalence.
- Designed strict temporal windowing in feature extraction to prevent future-to-past leakage (`fix_temporal_features.py`).

---

# 3. Inferences Drawn from Literature Survey

## Papers / Research Works Studied

| # | Paper / Reference | Key Focus |
|---|---|---|
| 1 | Ribeiro et al. (2020) — "Automatic diagnosis of the 12-lead ECG using a deep neural network" | CNN-based ECG classification; established AUROC benchmarks |
| 2 | Attia et al. (2019) — "AI-Enabled ECG for Assessment of Age and Sex" | Demonstrated ECG waveform encodes demographic information |
| 3 | Strodthoff et al. (2020) — "Deep Learning for ECG Analysis" | Survey of DL architectures for ECG; highlighted limitations of supervised approaches |
| 4 | Higgins et al. (2017) — "β-VAE: Learning Basic Visual Concepts" | Proposed β-VAE for disentangled representation learning |
| 5 | Pearl (2009) — "Causality: Models, Reasoning, and Inference" | Foundational work on SCMs, do-calculus, and counterfactual reasoning |
| 6 | Sharma & Kiciman (2020) — "DoWhy: An End-to-End Library for Causal Inference" | Python framework for causal identification and estimation |
| 7 | Arjovsky et al. (2019) — "Invariant Risk Minimization" | Learning representations invariant to environment/domain shift |
| 8 | Rajkomar et al. (2018) — "Scalable and Accurate Deep Learning with EHR" | ML on structured EHR data; demonstrated importance of temporal feature engineering |
| 9 | Thygesen et al. (2018) — "Fourth Universal Definition of MI" | ACC/AHA clinical guidelines for troponin-based MI diagnosis |
| 10 | Johnson et al. (2023) — "MIMIC-IV: A Freely Accessible EHR Dataset" | Description of the MIMIC-IV data schema and access protocols |

## Key Findings from Literature

1. **ECG waveforms encode clinically actionable information** beyond what static features capture — deep models (CNN, VAE) on raw signals outperform hand-crafted features alone.
2. **β-VAE with free bits** prevents posterior collapse and produces disentangled latent spaces suitable for downstream causal analysis.
3. **Causal inference requires explicit DAG specification** — correlational models cannot distinguish confounding from causation.
4. **Treatment-during features are leaky** — medications administered during an MI event (e.g., aspirin_during) are consequences of the diagnosis, not predictors.
5. **Class imbalance (<3% MI prevalence) breaks probability calibration** — models trained with class weighting must be post-hoc calibrated for clinical use.
6. **Isotonic regression outperforms Platt scaling** for non-linear miscalibration patterns typical of tree-based models.

## Limitations Identified in Existing Works

- Most ECG-MI papers use **supervised learning only** — no causal or counterfactual reasoning.
- Existing causal studies on MI typically use **tabular EHR data only** — none integrate raw ECG waveforms as a causal mediator.
- Few papers address **ECG machine model bias** (distribution shift from different hardware).
- Prior calibration studies rarely apply to **rare-event clinical predictions** with <3% prevalence.

## How the Literature Survey Influenced Our Project Design

- Adopted **β-VAE over standard VAE** with free bits constraint (from Higgins et al.) to prevent posterior collapse.
- Chose **DoWhy** over manual SCM implementation for reproducible causal analysis (from Sharma & Kiciman).
- Used **ACC/AHA troponin thresholds** (Thygesen et al.) instead of ICD-code-based MI labels for higher sensitivity.
- Designed the pipeline to explicitly handle **temporal leakage** (treatment_during features) informed by Rajkomar et al.

---

# 4. Design of Overall Architecture

## Overall System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RAW DATA SOURCES                                     │
│  ┌──────────────────┐    ┌──────────────────────┐                          │
│  │  MIMIC-IV v2.2   │    │  MIMIC-IV-ECG v1.0   │                          │
│  │  (Hospital EHR)  │    │  (12-Lead Waveforms)  │                          │
│  │  - patients       │    │  - 377,113 ECGs       │                          │
│  │  - admissions     │    │  - WFDB format        │                          │
│  │  - labevents      │    │  - 500 Hz, 10 sec     │                          │
│  │  - prescriptions  │    │                        │                          │
│  │  - diagnoses_icd  │    │                        │                          │
│  └──────┬───────────┘    └──────────┬─────────────┘                          │
└─────────┼───────────────────────────┼───────────────────────────────────────┘
          │                           │
          ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE A–C: DATA ENGINEERING                               │
│                                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐    │
│  │ DuckDB Database  │  │ Troponin Assay   │  │  Cohort Labeling       │    │
│  │ Ingestion        │─▶│ Identification   │─▶│  (MI vs Control)       │    │
│  │ (Phase B)        │  │ + Thresholds     │  │  4 classes defined     │    │
│  └─────────────────┘  │ (Phase C.1–C.2)  │  └────────┬────────────────┘    │
│                        └──────────────────┘           │                      │
└───────────────────────────────────────────────────────┼──────────────────────┘
                                                        │
          ┌─────────────────────────────────────────────┘
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE D–E: FEATURE ENGINEERING                            │
│                                                                              │
│  ┌──────────────────────┐  ┌────────────────────────────────────────────┐   │
│  │  ECG Feature          │  │  Clinical Feature Extraction              │   │
│  │  Extraction           │  │  ┌──────────────┐ ┌──────────────────┐   │   │
│  │  (MATLAB ECGdeli)     │  │  │ Comorbidities│ │ Treatments       │   │   │
│  │  95 morphological     │  │  │ (ICD codes)  │ │ (prescriptions)  │   │   │
│  │  features per ECG     │  │  └──────────────┘ └──────────────────┘   │   │
│  └──────────┬────────────┘  │  ┌──────────────┐ ┌──────────────────┐   │   │
│             │               │  │ Demographics │ │ Labs & Vitals    │   │   │
│             │               │  │ (age, sex)   │ │ (temporal window)│   │   │
│             │               │  └──────────────┘ └──────────────────┘   │   │
│  ┌──────────▼────────────┐  └────────────────────────┬─────────────────┘   │
│  │  Conv1D β-VAE         │                           │                      │
│  │  (12×5000 → 64-dim)   │                           │                      │
│  │  82M params, 109 ep.  │                           │                      │
│  │  → z_ecg embeddings   │                           │                      │
│  └──────────┬────────────┘                           │                      │
└─────────────┼────────────────────────────────────────┼──────────────────────┘
              │                                        │
              ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE F: MASTER DATASET                                   │
│                                                                              │
│  Labels + ECG Features (95) + VAE Embeddings (64) + Clinical (17) = 176 cols│
│  Train: 262,813 │ Validation: 56,319 │ Test: 56,798                         │
│  Parquet format │ Subject-level stratified split │ Seed=42                   │
│                                                                              │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
┌────────────────────┐ ┌──────────────────┐ ┌─────────────────────────┐
│  PHASE H           │ │  PHASE I–J       │ │  PHASE K                │
│  Baseline Models   │ │  Causal Inference│ │  Counterfactuals        │
│                    │ │                  │ │                         │
│  - LogReg          │ │  - DAG Design    │ │  - Patient-level        │
│  - XGBoost ×3      │ │  - SCM (DoWhy)   │ │    "what-if" scenarios  │
│  - Calibration     │ │  - ATE / CATE    │ │  - Treatment response   │
│  - AUROC: 0.867    │ │  (UPCOMING)      │ │  (UPCOMING)             │
└────────────────────┘ └──────────────────┘ └─────────────────────────┘
```

## Major Modules / Components

| Module | Phase | Description |
|---|---|---|
| **Data Ingestion** | A–B | Load MIMIC-IV CSV tables into DuckDB; index by subject_id, hadm_id |
| **Cohort Definition** | C | Identify troponin assays, define MI thresholds, label 4 cohorts |
| **ECG-Diagnosis Linking** | C | Map each ECG (study_id) to its hospital admission (hadm_id) and MI status |
| **ECG Feature Extraction** | D.2 | MATLAB ECGdeli pipeline extracting 95 morphological features per ECG |
| **ECG Preprocessing** | D.2+ | Deduplication, feature removal, winsorization, Yeo-Johnson transform, scaling |
| **VAE Training** | D.3 | Conv1D β-VAE (82M params) trained on 262K ECGs for 109 epochs |
| **Embedding Extraction** | D.4 | Extract 64-dim z_ecg vectors for all 375K ECGs |
| **Clinical Feature Extraction** | E | Comorbidities (ICD), treatments (prescriptions), demographics, labs, vitals |
| **Master Dataset Builder** | F | Merge all features into train/val/test parquet files (176 columns) |
| **Baseline Models** | H | LogReg + 3 XGBoost variants with subgroup fairness and calibration |
| **Causal Model** | I–J | DAG specification, DoWhy SCM, ATE/CATE estimation (upcoming) |
| **Counterfactuals** | K | Patient-level what-if scenarios (upcoming) |

## Data Flow Between Modules

```
MIMIC-IV CSVs ──→ DuckDB ──→ cohort_labels.csv ──→ final_ecg_cohorts_troponin.csv
                                    │                          │
                                    ▼                          ▼
                              features_comorbidities.csv   ecg_mapping.csv
                              features_treatments.csv           │
                              demographics.csv                  ▼
                                    │              MATLAB ECGdeli ──→ extracted_ecg_features.csv
                                    │                                        │
                                    ▼                                        ▼
                            Preprocessing Pipeline        Preprocessing Pipeline
                            (winsorize, transform,        (winsorize, transform,
                             scale)                        scale)
                                    │                          │
                                    │     WFDB → HDF5 → β-VAE │
                                    │         → z_ecg embeddings
                                    │              │           │
                                    └──────────────┼───────────┘
                                                   ▼
                                    build_master_dataset.py
                                                   │
                                    ┌──────────────┼──────────────┐
                                    ▼              ▼              ▼
                              train.parquet  validation.parquet  test.parquet
                                    │
                                    ▼
                            train_baselines.py ──→ results.json + .pkl models
                            calibrate_baselines.py ──→ calibrated .pkl models
```

---

# 5. List of Tasks / Modules

## Data Collection & Preparation

| Task | Description | Output |
|---|---|---|
| PhysioNet Access | CITI training, credentialed data download | MIMIC-IV v2.2, MIMIC-IV-ECG v1.0 |
| Database Setup | DuckDB in-memory database for SQL queries | Indexed tables for fast joins |
| Troponin Identification | Query `d_labitems` for troponin assays (itemid: 51002, 51003, 52642) | Troponin threshold table |
| MI Event Definition | Troponin > URL + ≥20% delta criterion (ACC/AHA) | Binary MI labels |
| Cohort Labeling | Time-anchored labels: Control_Symptomatic, MI_Acute_Presentation, MI_Pre-Incident, MI_Post-Incident | `cohort_labels.csv` (194K admissions) |
| ECG-to-Diagnosis Linking | Map study_id → hadm_id → MI status with temporal windows | `final_ecg_cohorts_troponin.csv` (375K ECGs) |

## Data Preprocessing

| Task | Description | Output |
|---|---|---|
| ECG Feature Extraction | MATLAB ECGdeli (parallelized, 4 workers) on 407K ECGs | `extracted_ecg_features.csv` (95 features) |
| Feature Quality Validation | Univariate statistics, outlier analysis, missingness reports, PTB-XL+ comparison | QA reports in `capstone_preprocessing/` |
| Deduplication | Remove duplicate ECG records | Cleaned feature set |
| Winsorization | Clip extreme values (0.5th–99.5th percentile) | Bounded distributions |
| Power Transform | Yeo-Johnson transformation for non-normal features | Gaussian-like distributions |
| Scaling | RobustScaler on all continuous features | Zero-median, unit-IQR features |
| HDF5 Conversion | Convert 375K WFDB files → single HDF5 (84 GB) | `ecg_signals.h5` |

## Data Input

| Source | Format | Size | Records |
|---|---|---|---|
| MIMIC-IV v2.2 Hospital | CSV (10 tables) | ~15 GB | ~330K patients |
| MIMIC-IV-ECG v1.0 | WFDB (.dat/.hea) | ~90 GB | 407K ECGs |
| Extracted ECG Features | CSV | 864 MB | 407K rows × 95 features |
| HDF5 Waveforms | HDF5 | 84 GB | 375K ECGs × 12 × 5000 |

## Model Training

| Model | Architecture | Parameters | Training |
|---|---|---|---|
| Conv1D β-VAE | 3-layer Conv1D encoder + decoder, z_dim=64 | 82,448,332 | 109 epochs, cyclical β-annealing, NVIDIA RTX 4050 |
| Logistic Regression | Linear (17 clinical features) | ~17 | class_weight='balanced' |
| XGBoost (ECG + Clinical) | Gradient boosted trees (112 features) | ~2.3M | scale_pos_weight=48.59 |
| XGBoost (Embeddings + Clinical) | Gradient boosted trees (81 features) | ~2.3M | scale_pos_weight=48.59 |
| XGBoost (All Features) | Gradient boosted trees (176 features) | ~2.3M | scale_pos_weight=48.59 |
| Isotonic Calibration | Non-parametric monotonic remapping | N/A | Fit on validation set (56K samples) |

## SDKs, APIs, and Tools Used

### Programming Languages & Frameworks

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Primary language for all ML/data pipelines |
| MATLAB | R2024a | ECG feature extraction (ECGdeli toolbox) |
| PyTorch | 2.5.1+cu121 | β-VAE deep learning framework |
| CUDA | 12.1 | GPU acceleration for VAE training |

### Core Libraries

| Library | Version | Purpose |
|---|---|---|
| pandas | 2.3.3 | DataFrame operations, data manipulation |
| numpy | 1.26.4 | Numerical computing |
| scikit-learn | 1.7.2 | Logistic Regression, isotonic calibration, preprocessing |
| XGBoost | 2.1.4 | Gradient boosted baseline models |
| DuckDB | 1.4.1 | In-memory SQL analytics on MIMIC-IV CSVs |
| h5py | 3.15.1 | HDF5 file I/O for ECG waveforms |
| wfdb | 4.3.0 | WFDB format ECG signal loading |
| pyarrow | 21.0.0 | Parquet file I/O |
| scipy | 1.16.2 | Statistical tests, transformations |
| matplotlib | 3.10.7 | Plotting and visualization |
| seaborn | 0.13.2 | Statistical visualizations |

### Medical / Signal Processing

| Tool | Version | Purpose |
|---|---|---|
| ECGdeli | 1.1 (MATLAB) | Clinical ECG feature extraction (QRS, ST, T-wave) |
| WFDB Software Package | 10.7.0 | C-core for WFDB format reading |
| neurokit2 | 0.2.12 | ECG feature extraction validation |

### Development Tools

| Tool | Purpose |
|---|---|
| Git | Version control |
| VS Code | Primary IDE |
| Jupyter Notebook | Interactive analysis |
| NVIDIA RTX 4050 (6 GB VRAM) | GPU for VAE training |
| Windows 11 | Development OS |

### Planned (Upcoming Phases)

| Library | Purpose |
|---|---|
| DoWhy | Causal inference (DAG, SCM, estimation) |
| EconML | CATE estimation (DML, causal forests) |
| dagitty | DAG visualization and identification |

---

# 6. Individual Contribution

| Team Member | Tasks / Modules Assigned | Work Completed | LOC |
|---|---|---|---|
| **Anurag** (PES1UG23AM058) | ECG Feature Extraction (MATLAB), ECGdeli integration, Feature Quality Validation, PTB-XL+ comparison | MATLAB extraction pipeline (311 LOC), ECGdeli validation reports, feature selection (95 → 177 features post-preprocessing) | ~1,500 |
| **Ashwin** (PES1UG23CS117) | Cohort Labeling (Phase C), Troponin extraction, MI event definition, Clinical feature extraction | cohort_labeling.py (967 LOC), extract_troponin_cohorts.py (135 LOC), extract_comorbidities.py (120 LOC), fix_temporal_features.py (110 LOC) | ~1,700 |
| **Ashish Kumar B** (PES1UG23CS114) | Data Preprocessing Pipeline, Quality Validation, Feature analysis, Analysis pipeline | Preprocessing pipeline (8 modules, ~400 LOC), Analysis pipeline (6 modules, ~1,700 LOC), build_modeling_data.py (498 LOC) | ~2,600 |
| **Bharath K C** (PES1UG23CS143) | VAE Architecture & Training, ECG Dataset/HDF5, Baseline Models, Calibration, Master Dataset Builder | vae_conv1d.py (221 LOC), train_vae.py (531 LOC), ecg_dataset.py (441 LOC), convert_to_hdf5.py (247 LOC), train_baselines.py (573 LOC), calibrate_baselines.py (232 LOC), build_master_dataset.py (188 LOC), extract_embeddings.py (144 LOC) | ~2,700 |

**Total Project LOC:** ~8,086 (Python) + 291 (MATLAB) + 2,616 (Documentation/Markdown) = **~10,993 lines**

> [!NOTE]
> LOC counts are approximate and represent authored code only (excludes auto-generated files, virtualenv, and __pycache__).

---

# 7. Gantt Chart / Project Timeline

| # | Task / Module | Start Date | End Date | Duration | Status |
|---|---|---|---|---|---|
| 1 | Phase A — Infrastructure & Planning | Oct 2025 | Nov 2025 | 4 weeks | ✅ Completed |
| 2 | Phase B — Data Ingestion (DuckDB) | Nov 2025 | Dec 2025 | 4 weeks | ✅ Completed |
| 3 | Phase C — Cohort Definition & Labeling | Dec 2025 | Feb 2026 | 8 weeks | ✅ Completed |
| 4 | Phase D.1 — Feature Extractor Validation | Jan 2026 | Mar 2026 | 8 weeks | ✅ Completed |
| 5 | Phase D.2 — ECG Feature Extraction (MATLAB) | Feb 2026 | Apr 2026 | 8 weeks | ✅ Completed |
| 6 | Phase D.3 — Data Preprocessing & Quality | Mar 2026 | May 2026 | 8 weeks | ✅ Completed |
| 7 | Phase E — Clinical Feature Extraction | Apr 2026 | Jun 2026 | 8 weeks | ✅ Completed |
| 8 | Phase F — Master Dataset Construction | Jun 2026 | Jul 2026 | 4 weeks | ✅ Completed |
| 9 | Phase D.3–D.5 — VAE Training & Embeddings | Jul 2026 | Aug 2026 | 6 weeks | ✅ Completed |
| 10 | Phase H — Baseline Models + Calibration | Aug 2026 | Aug 2026 | 2 weeks | ✅ Completed |
| 11 | Phase G — Environment / IRM | Sep 2026 | Sep 2026 | 3 weeks | 🔜 Upcoming |
| 12 | Phase I — DAG Design & SCM Specification | Sep 2026 | Oct 2026 | 4 weeks | 🔜 Upcoming |
| 13 | Phase J — ATE / CATE Estimation | Oct 2026 | Oct 2026 | 3 weeks | ⏳ Pending |
| 14 | Phase K — Patient-Level Counterfactuals | Oct 2026 | Nov 2026 | 3 weeks | ⏳ Pending |
| 15 | Phase L — Sensitivity & Validation | Nov 2026 | Nov 2026 | 2 weeks | ⏳ Pending |
| 16 | Phase M — Documentation & Delivery | Nov 2026 | Dec 2026 | 4 weeks | ⏳ Pending |

**Overall Progress: ~65% complete (Phases A–F, D.3–D.5, H fully done)**

---

# 8. Demonstration and Testing of Completed Modules

---

## Module 1: Cohort Definition & Labeling (Phase C)

**Purpose:** Identify MI patients from MIMIC-IV hospital records using troponin biomarker criteria and create clinically meaningful patient cohorts.

**Input:**
- MIMIC-IV `labevents.csv` (troponin measurements)
- MIMIC-IV `d_labitems.csv` (troponin assay identifiers)
- MIMIC-IV `admissions.csv`, `patients.csv`

**Process:**
1. Identify troponin assays (itemid: 51002 Troponin I, 51003 Troponin T, 52642 hs-Troponin I)
2. Apply ACC/AHA thresholds: Troponin T > 0.014 ng/mL, Troponin I > 0.040 ng/mL
3. Apply delta criterion: ≥20% relative change between serial measurements (distinguishes acute MI from chronic myocardial injury)
4. Time-anchor ECGs relative to MI event and assign labels

**Output — Cohort Label Distribution:**

| Label | Count | Percentage |
|---|---|---|
| Control_Symptomatic | 362,384 | 96.4% |
| MI_Acute_Presentation | 7,560 | 2.0% |
| MI_Pre-Incident | 5,986 | 1.6% |
| MI_Post-Incident (excluded) | — | — |

**Results:** 375,930 ECGs across 194,587 hospital admissions successfully labeled with 4 clinically distinct categories.

---

## Module 2: ECG Feature Extraction (Phase D.2)

**Purpose:** Extract clinically meaningful morphological features from 12-lead ECG waveforms using the ECGdeli MATLAB toolbox.

**Input:** 407,504 WFDB ECG files (12 leads × 5000 samples at 500 Hz)

**Process:**
1. Parallel processing (4 MATLAB workers)
2. ECGdeli fiducial point detection (P-wave, QRS, ST-segment, T-wave)
3. Feature calculation: amplitudes, durations, intervals, elevations
4. Per-lead extraction across all 12 leads + global metrics

**Output:** 95 morphological features per ECG, including:

| Feature Category | Examples | Count |
|---|---|---|
| QRS Duration | QRS_Dur_Global, QRS_Dur_I, QRS_Dur_II, ... | 13 |
| R-wave Amplitude | R_Amp_I, R_Amp_V1, R_Amp_V6, ... | 12 |
| ST Elevation | ST_Elev_I, ST_Elev_aVF, ST_Elev_V5, ... | 12 |
| T-wave Amplitude | T_Amp_I, T_Amp_III, T_Amp_aVF, ... | 12 |
| RR Interval | RR_Mean_Global | 1 |
| Other | Q_Amp, S_Amp per lead | 24+ |

**Results:** `extracted_ecg_features.csv` — 864 MB, 407,504 rows × 95 feature columns + metadata.

---

## Module 3: Data Preprocessing & Quality Validation (Phase D.2+)

**Purpose:** Clean, validate, and normalize extracted ECG features for downstream modeling.

**Input:** Raw extracted ECG features (95 columns, 407K rows)

**Process:**
1. **Deduplication:** Remove exact duplicate ECG records
2. **Feature Removal:** Regex-based removal of low-information features (e.g., all `_iqr` variants of ST_Elev, redundant `_count` features)
3. **Winsorization:** Clip extreme values at 0.5th / 99.5th percentiles to bound outliers
4. **Yeo-Johnson Transform:** Power transformation for near-Gaussian distributions
5. **Robust Scaling:** Center at median, scale by IQR for outlier-resistant normalization

**Quality Validation (PTB-XL+ Comparison):**

| Metric | Result |
|---|---|
| Pearson correlation (MIMIC vs PTB-XL) | 0.72–0.95 per feature |
| Feature coverage | 95/95 features extracted |
| Missingness (MIMIC-IV) | < 5% for all features |
| Batch effect (MIMIC vs PTB-XL) | Detected in amplitude features (expected due to different patient populations) |

**Output:** Preprocessed features split into train/val/test CSVs in `data/modeling/ecg_features/`

---

## Module 4: Conv1D β-VAE Training (Phase D.3)

**Purpose:** Learn unsupervised 64-dimensional latent representations of ECG waveforms for use in the Structural Causal Model.

**Input:** 262,813 training ECGs (12 × 5000 float32 arrays) from HDF5 file (84 GB)

**Process:**
1. **Architecture:** 3-layer Conv1D encoder (12→32→64→128 channels) → FC layers → 64-dim latent space → symmetric decoder
2. **Training:** Cyclical β-annealing (4 cycles × 40 epochs), free bits constraint (λ=2.0), Adam optimizer (lr=1e-4)
3. **Hardware:** NVIDIA RTX 4050 Laptop GPU (6 GB VRAM), batch size 128

**Training Results:**

| Metric | Value |
|---|---|
| Best epoch | 109 |
| Best validation loss | 16,904.65 |
| Reconstruction loss | ~13,200 |
| KL divergence (raw) | ~263 (64 active latent dims) |
| Training time | ~7.5 hours (109 epochs × ~4 min/epoch) |
| Total parameters | 82,448,332 |

**Output:** Trained model checkpoint (`best_model.pt`) and 64-dim embeddings for all 375K ECGs.

---

## Module 5: Master Dataset Construction (Phase F)

**Purpose:** Merge all feature sources into a single analysis-ready dataset.

**Input:**
- Labels (study_id, hadm_id, Label_Troponin)
- ECG features (95 preprocessed morphological features)
- VAE embeddings (64-dim z_ecg)
- Comorbidities (diabetes, hypertension, CKD, prior_MI)
- Treatments (statin, aspirin, beta_blocker, ACEI — before/during/after)
- Demographics (age, sex_male)

**Process:**
1. Start with labels as backbone (indexed by study_id)
2. Left-join ECG features on study_id
3. Left-join VAE embeddings on study_id
4. Left-join comorbidities on hadm_id
5. Left-join treatments on hadm_id
6. Left-join demographics on SubjectID
7. Create binary missing-value flags for features with >10% missingness
8. Save as Parquet files

**Output:**

| Split | Rows | Columns | File Size |
|---|---|---|---|
| Train | 262,813 | 176 | 378 MB |
| Validation | 56,319 | 176 | 89 MB |
| Test | 56,798 | 176 | 89 MB |

---

## Module 6: Baseline Predictive Models (Phase H)

**Purpose:** Train and evaluate predictive models for MI risk as a performance benchmark before causal analysis.

**Input:** Master dataset (176 features, 375K ECGs)

**Process:**
1. Define binary target: `Label_Troponin == 'MI_Acute_Presentation'` (prevalence: 2.02%)
2. Train 4 models: LogReg (clinical-only), XGBoost (ECG+Clinical), XGBoost (Embeddings+Clinical), XGBoost (All)
3. Evaluate: AUROC, AUPRC, Brier score, ECE, sensitivity/specificity, subgroup fairness
4. Post-hoc calibration: Isotonic regression on validation set

**Results (Test Set):**

| Model | Features | AUROC | AUPRC | Brier | ECE (After Cal.) |
|---|---|---|---|---|---|
| Logistic Regression | 17 (clinical) | 0.816 | 0.065 | 0.019 | 0.0003 |
| **XGBoost (ECG+Clinical)** | **112** | **0.867** | **0.175** | **0.018** | **0.0014** |
| XGBoost (Embeddings+Clinical) | 81 | 0.841 | 0.104 | 0.019 | 0.0004 |
| XGBoost (All Features) | 176 | 0.867 | 0.168 | 0.018 | 0.0011 |

**Key Findings:**
- ECG features add **+5% AUROC** over clinical-only baseline (0.816 → 0.867)
- Hand-crafted ECG features **outperform** VAE embeddings (0.175 vs 0.104 AUPRC) for MI discrimination
- Post-hoc calibration reduces ECE by **99%** (0.32 → 0.0003) and Brier score by **85%**
- Subgroup fairness: Prior MI patients show 12.4% AUROC gap (flagged for causal analysis)

**Subgroup Fairness (Best Model — XGBoost ECG+Clinical):**

| Subgroup | Best AUROC | Worst AUROC | Gap |
|---|---|---|---|
| Age Group | <50: 0.934 | >70: 0.825 | 10.8% ⚠️ |
| Sex | Female: 0.875 | Male: 0.856 | 1.9% ✅ |
| Diabetes | No: 0.879 | Yes: 0.826 | 5.3% ✅ |
| Prior MI | No: 0.879 | Yes: 0.753 | **12.4%** ⚠️ |

---

## Module 7: Post-Hoc Isotonic Calibration (Phase H.1)

**Purpose:** Align raw predicted probabilities (inflated by class weighting) with true MI prevalence for clinical use.

**Input:** Raw model predictions on validation set (56,319 samples)

**Process:** Fit isotonic regression mapping raw probabilities → observed frequencies, then evaluate on test set.

**Calibration Results:**

| Model | ECE Before | ECE After | Δ ECE | Brier Before | Brier After |
|---|---|---|---|---|---|
| LogReg | 0.321 | **0.0003** | −0.321 | 0.185 | **0.019** |
| XGBoost ECG+Clin | 0.248 | **0.0014** | −0.247 | 0.128 | **0.018** |
| XGBoost Emb+Clin | 0.273 | **0.0004** | −0.273 | 0.147 | **0.019** |
| XGBoost All | 0.247 | **0.0011** | −0.246 | 0.126 | **0.018** |

**Key Insight:** AUROC is preserved (≤0.001 change) because isotonic regression is a monotonic transform — rankings stay the same, but probability values are corrected.

---

## Testing Summary

### Testing Methodology

| Test Type | Description |
|---|---|
| Train/Val/Test Split | Subject-level stratified (no patient appears in multiple splits) |
| Label Integrity | Verified no troponin features leak into prediction features |
| Feature Validation | Cross-referenced ECGdeli features against PTB-XL+ gold standard |
| Model Evaluation | AUROC, AUPRC, Brier, ECE on held-out test set (56,798 ECGs) |
| Subgroup Fairness | AUROC stratified by age, sex, diabetes, prior MI |
| Calibration | Before/after reliability diagrams (10-bin quantile strategy) |

### Test Cases

| Test Case | Expected | Actual | Status |
|---|---|---|---|
| MI prevalence in splits is consistent (~2%) | ~2% in each | Train: 2.02%, Val: 2.01%, Test: 1.99% | ✅ Pass |
| No subject overlap between train/val/test | 0 shared subjects | 0 shared subjects | ✅ Pass |
| Troponin not in feature set | 0 troponin features | 0 troponin features | ✅ Pass |
| XGBoost AUROC > LogReg | XGB > 0.82 | 0.867 > 0.816 | ✅ Pass |
| Post-calibration ECE < 0.01 | ECE < 0.01 | All < 0.002 | ✅ Pass |
| Sex-based AUROC gap < 5% | < 5% | 1.9% | ✅ Pass |
| VAE latent dims active (no posterior collapse) | ≥50/64 active | 64/64 active (KL > 0 per dim) | ✅ Pass |

---

# 10. Thank You

**Thank You**

**Questions & Discussion**

---

## Contact

| Name | SRN | Email |
|---|---|---|
| Anurag | PES1UG23AM058 | — |
| Ashwin | PES1UG23CS117 | — |
| Ashish Kumar B | PES1UG23CS114 | — |
| Bharath K C | PES1UG23CS143 | — |

**Project Guide:** Prof. Priya Badrinath
