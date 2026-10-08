# Phase F — Master Dataset: Complete Documentation

> **Date**: August 21, 2026  
> **Pipeline Reference**: [longitudinal_mi_cohort_extraction.md](file:///C:/Users/Acer/Desktop/Pipeline/longitudinal_mi_cohort_extraction.md), Phase F  
> **Goal**: Merge all data sources into a single master modeling table per split.

---

## 1. Overview

The master dataset merges **5 data sources** into a unified table with **184 columns** and **375,930 rows** across train/validation/test splits. This is the single source of truth for all downstream modeling (Phase H: baselines, Phase I: causal inference, Phase J: counterfactuals).

```
Labels (backbone)  ─┐
ECG Embeddings     ─┤  study_id
ECG Features       ─┤
Comorbidities      ─┤  hadm_id      ──→  master/{train,validation,test}.parquet
Treatments         ─┤  hadm_id           (375,930 rows × 184 columns)
Demographics       ─┘  SubjectID
```

---

## 2. Data Sources & Join Strategy

All joins are **LEFT JOIN** from the labels backbone to preserve every ECG record.

| Source | File | Rows | Join Key | Coverage |
|---|---|---|---|---|
| **Labels** (backbone) | `labels/{split}.csv` | 375,930 | — | 100% |
| **ECG Embeddings** | `ecg_embeddings/{split}.csv` | 375,930 | `study_id` | **100%** |
| **ECG Features** | `ecg_features/{split}.csv` | 375,930 | `study_id` | **100%** |
| **Comorbidities** | `clinical/features_comorbidities.csv` | 194,587 | `hadm_id` | **100%** |
| **Treatments** | `clinical/features_treatments.csv` | 194,587 | `hadm_id` | **100%** |
| **Demographics** | `demographics/demographics.csv` | 99,256 | `SubjectID` | **100%** |

### Dropped Sources (by design)
| Source | Rows | Reason |
|---|---|---|
| **Labs** (`features_labs.csv`) | 738 | <1% coverage — would be 99%+ NULL |
| **Vitals** (`features_vitals.csv`) | 1,457 | <1% coverage — would be 99%+ NULL |

### Excluded Columns
| Column | Reason |
|---|---|
| `peak_troponin_before` | **Pipeline E.1**: "NEVER USE TROPONIN AS A FEATURE" — prevents circular prediction |

---

## 3. Column Schema (184 columns)

### Identifiers (3 columns)
| Column | Type | Description |
|---|---|---|
| `study_id` | int64 | Unique ECG study identifier |
| `SubjectID` | int64 | Patient identifier |
| `hadm_id` | int64 | Hospital admission identifier |

### Labels (2 columns)
| Column | Type | Description |
|---|---|---|
| `Label_Troponin` | str | `Control_Symptomatic`, `MI_Pre-Incident`, or `MI_Acute_Presentation` |
| `is_MI` | bool | Binary MI flag |

### Time (3 columns)
| Column | Type | Description |
|---|---|---|
| `ecg_time` | str | Timestamp of the ECG recording |
| `index_mi_time` | str | Timestamp of MI event (NULL for controls — 87% missing, expected) |
| `time_diff_hours` | float64 | Hours between ECG and MI event |

### ECG Embeddings (64 columns)
| Columns | Type | Description |
|---|---|---|
| `z_ecg_1` ... `z_ecg_64` | float64 | 64-dim VAE latent representation of the raw 12-lead ECG |

### ECG Features (95 columns)
| Category | Example Columns | Count |
|---|---|---|
| Global timing | `QRS_Dur_Global`, `RR_Mean_Global` | 5 |
| S-wave amplitudes | `S_Amp_V1`, `S_Amp_V2`, `S_Amp_V3` | 6 |
| Lead-specific (I, II, III, aVR, aVL, aVF, V1–V6) | `Q_Amp_*`, `R_Amp_*`, `T_Amp_*`, `ST_Elev_*` | 84 |

Each amplitude feature has an `_iqr` variant capturing beat-to-beat variability.

### Comorbidities (4 columns)
| Column | Type | Description |
|---|---|---|
| `diabetes` | float64 | ICD-coded diabetes from prior admissions |
| `hypertension` | float64 | ICD-coded hypertension from prior admissions |
| `ckd` | float64 | ICD-coded chronic kidney disease from prior admissions |
| `prior_mi` | float64 | Had MI in a previous admission |

### Treatments (11 columns)
| Column | Type | Window | Description |
|---|---|---|---|
| `statin_before` | float64 | Before admission | Pre-admission statin use |
| `statin_during` | float64 | During admission | In-hospital statin use |
| `statin_after` | float64 | After discharge | Post-discharge statin use |
| `beta_blocker_before` | float64 | Before | Beta-blocker use |
| `beta_blocker_during` | float64 | During | Beta-blocker use |
| `acei_before` | float64 | Before | ACE inhibitor use |
| `acei_during` | float64 | During | ACE inhibitor use |
| `aspirin_before` | float64 | Before | Aspirin use |
| `aspirin_during` | float64 | During | Aspirin use |
| `vasopressor_during` | float64 | During | Vasopressor administration |
| `mech_vent_during` | float64 | During | Mechanical ventilation |

### Demographics (2 columns)
| Column | Type | Description |
|---|---|---|
| `anchor_age` | float64 | Patient age at admission |
| `sex_male` | int64 | Binary sex indicator (1 = Male) |

---

## 4. Missingness Analysis

| Column | Missing | Rate | Explanation |
|---|---|---|---|
| `index_mi_time` | 229,005 | 87.1% | **Expected** — only MI patients have an MI event time. All controls are NULL. |
| All other columns | 0 | 0% | Perfect coverage |

No `_missing` flags were needed — all feature columns have <5% missingness.

---

## 5. Label Distribution

| Label | Train | Validation | Test | Total |
|---|---|---|---|---|
| Control_Symptomatic | 253,334 | 54,302 | 54,736 | 362,372 |
| MI_Acute_Presentation | 5,300 | 1,145 | 1,159 | 7,604 |
| MI_Pre-Incident | 4,179 | 872 | 903 | 5,954 |
| **Total** | **262,813** | **56,319** | **56,798** | **375,930** |

The class imbalance (96.4% Control vs 3.6% MI) is inherent to the clinical data and will be addressed with class weighting / stratified sampling in Phase H.

---

## 6. Output Files

| File | Rows | Cols | Size |
|---|---|---|---|
| [`master/train.parquet`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/master/train.parquet) | 262,813 | 184 | 360.7 MB |
| [`master/validation.parquet`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/master/validation.parquet) | 56,319 | 184 | 84.6 MB |
| [`master/test.parquet`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/master/test.parquet) | 56,798 | 184 | 85.3 MB |

---

## 7. Build Script

**Script**: [`src/features/build_master_dataset.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/features/build_master_dataset.py)

```bash
# Reproduce
cd C:\Users\Acer\Desktop\Capstone\SCM
python src/features/build_master_dataset.py
```

### Verification Performed
- Row count preserved after every join (no fanout from duplicate keys) ✅
- 100% match rate on all 5 data sources ✅
- Label distributions identical before and after merge ✅
- No unexpected missing values ✅
- Troponin excluded from feature set ✅

---

## 8. Pipeline Progress

| Phase | Description | Status |
|---|---|---|
| A | Infrastructure & Governance | ✅ Complete |
| B | Ingestion & Database | ✅ Complete |
| C | Cohort, Labeling & Power Analysis | ✅ Complete |
| D | ECG Feature & Latent Space Engineering | ✅ Complete |
| E | Clinical Features (Leakage-Vetted) | ✅ Complete |
| **F** | **Merge Master Dataset** | **✅ Complete** |
| G | Environment Definition & Robustness (IRM) | Next |
| H | Baseline Predictive Models | Next |
| I | Causal Inference (DoWhy, DAG) | Upcoming |
| J | Counterfactual Analysis | Upcoming |
