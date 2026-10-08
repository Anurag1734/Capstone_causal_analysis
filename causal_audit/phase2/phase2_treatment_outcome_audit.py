from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2\master")
OUTPUT_JSON = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2\phase2_audit_results.json")
NOTEBOOK_PATH = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2\phase2_treatment_outcome_audit.ipynb")

TREATMENT_VARS = [
    "statin_before",
    "statin_during",
    "statin_after",
    "beta_blocker_before",
    "beta_blocker_during",
    "acei_before",
    "acei_during",
    "aspirin_before",
    "aspirin_during",
    "vasopressor_during",
    "mech_vent_during",
]

OUTCOME_VARS = ["Label_Troponin", "is_MI", "index_mi_time", "time_diff_hours"]
REQUIRED_COLUMNS = [
    "study_id",
    "SubjectID",
    "hadm_id",
    "ecg_time",
    *OUTCOME_VARS,
    *TREATMENT_VARS,
]


def load_data() -> tuple[pd.DataFrame, dict[str, int]]:
    split_files = {split: DATA_DIR / f"{split}.parquet" for split in ["train", "validation", "test"]}
    split_rows = {}
    frames = []
    for split, path in split_files.items():
        df = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
        split_rows[split] = int(len(df))
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined["ecg_time_dt"] = pd.to_datetime(combined["ecg_time"], errors="coerce", utc=True)
    combined["index_mi_time_dt"] = pd.to_datetime(combined["index_mi_time"], errors="coerce", utc=True)
    return combined, split_rows


def row_level_prevalence(df: pd.DataFrame, cols: list[str]) -> dict:
    result = {}
    for col in cols:
        s = df[col]
        exposed = int(s.eq(1).sum())
        unexposed = int(s.eq(0).sum())
        missing = int(s.isna().sum())
        total = int(len(s))
        result[col] = {
            "exposed_count": exposed,
            "unexposed_count": unexposed,
            "missing_count": missing,
            "exposure_percentage": float(exposed / total) if total else 0.0,
        }
    return result


def admission_level_prevalence(df: pd.DataFrame, cols: list[str]) -> dict:
    result = {}
    adm = df.groupby("hadm_id", dropna=False)[cols].max().reset_index()
    total_admissions = int(len(adm))
    for col in cols:
        s = adm[col].fillna(0)
        exposed = int((s > 0).sum())
        unexposed = int((s == 0).sum())
        missing = int(adm[col].isna().sum())
        result[col] = {
            "exposed_count": exposed,
            "unexposed_count": unexposed,
            "missing_count": missing,
            "exposure_percentage": float(exposed / total_admissions) if total_admissions else 0.0,
        }
    return result


def consistency_within_admission(df: pd.DataFrame, cols: list[str]) -> dict:
    result = {}
    for col in cols:
        by_hadm = df.groupby("hadm_id", dropna=False)[col].agg(lambda x: set(pd.Series(x).dropna().unique().tolist()))
        inconsistent = int((by_hadm.apply(lambda v: len(v) > 1)).sum())
        total_hadm = int(len(by_hadm))
        result[col] = {
            "n_admissions_with_inconsistent_values": inconsistent,
            "percentage_of_admissions_affected": float(inconsistent / total_hadm) if total_hadm else 0.0,
            "example_unique_values": sorted({v for vals in by_hadm for v in vals}) if by_hadm.size else [],
        }
    return result


def outcome_summary(df: pd.DataFrame) -> dict:
    is_mi = df["is_MI"]
    label_counts = df["Label_Troponin"].value_counts(dropna=False).to_dict()
    label_by_mi = pd.crosstab(
        df["Label_Troponin"].fillna("<missing>"),
        df["is_MI"].fillna("<missing>").astype(str),
        dropna=False,
    )
    label_timing = {}
    for label in ["Control_Symptomatic", "MI_Pre-Incident", "MI_Acute_Presentation", "MI_Post-Incident"]:
        rows = df[df["Label_Troponin"] == label]
        diff = pd.to_numeric(rows["time_diff_hours"], errors="coerce")
        label_timing[label] = {
            "row_count": int(len(rows)),
            "index_mi_time_nonnull_count": int(rows["index_mi_time"].notna().sum()),
            "index_mi_time_missing_count": int(rows["index_mi_time"].isna().sum()),
            "time_diff_hours_nonnull_count": int(diff.notna().sum()),
            "time_diff_hours_min": float(diff.min()) if diff.notna().any() else None,
            "time_diff_hours_median": float(diff.median()) if diff.notna().any() else None,
            "time_diff_hours_max": float(diff.max()) if diff.notna().any() else None,
        }
    return {
        "is_MI_binary": bool(is_mi.nunique() <= 2),
        "is_MI_values": sorted({bool(v) for v in is_mi.dropna().unique().tolist()}),
        "Label_Troponin_counts": {str(k): int(v) for k, v in label_counts.items()},
        "Label_Troponin_expected_categories_including_excluded": {
            label: int(label_counts.get(label, 0))
            for label in [
                "Control_Symptomatic",
                "MI_Pre-Incident",
                "MI_Acute_Presentation",
                "MI_Post-Incident",
            ]
        },
        "is_MI_by_Label_Troponin": {
            str(label): {str(value): int(count) for value, count in values.items()}
            for label, values in label_by_mi.to_dict(orient="index").items()
        },
        "Label_Troponin_missing": int(df["Label_Troponin"].isna().sum()),
        "is_MI_missing": int(df["is_MI"].isna().sum()),
        "index_mi_time_missing": int(df["index_mi_time"].isna().sum()),
        "index_mi_time_nonnull": int(df["index_mi_time"].notna().sum()),
        "time_diff_hours_missing": int(df["time_diff_hours"].isna().sum()),
        "time_diff_hours_nonnull": int(df["time_diff_hours"].notna().sum()),
        "temporal_summary_by_Label_Troponin": label_timing,
        "time_diff_hours_semantics": {
            "MI_patients": "ecg_time - index_mi_time; this arithmetic describes ECG-to-MI timing only for MI patients.",
            "Control_Symptomatic": "Based on the admission-time anchor/fallback; it is not time relative to an MI event.",
            "interpretation_rule": "Do not use time_diff_hours alone to classify rows as before/after MI or to replace Label_Troponin.",
            "label_grouped_values_are_descriptive_only": True,
        },
        "MI_Post-Incident_rows_in_master_dataset": int(label_counts.get("MI_Post-Incident", 0)),
        "outcome_definition_assessment": "UNRESOLVED — requires later causal outcome definition/audit.",
    }


def variable_definition_table() -> dict:
    return {
        "statin_before": {
            "definition": "Pre-admission statin use; before hospital admission.",
            "reference_event": "hospital admission / pre-admission baseline",
            "exact_timing_available": "No",
            "evidence": "Phase F master dataset schema and longitudinal MI cohort extraction guide describe statin_before as before admission/pre-admission use."
        },
        "statin_during": {
            "definition": "In-hospital statin use during the admission.",
            "reference_event": "admission stay / in-hospital period",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists statin_during as During admission."
        },
        "statin_after": {
            "definition": "Post-discharge statin use.",
            "reference_event": "after discharge",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists statin_after as After discharge."
        },
        "beta_blocker_before": {
            "definition": "Pre-admission beta-blocker use.",
            "reference_event": "hospital admission / pre-admission baseline",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists beta_blocker_before as Before."
        },
        "beta_blocker_during": {
            "definition": "In-hospital beta-blocker use.",
            "reference_event": "admission stay",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists beta_blocker_during as During."
        },
        "acei_before": {
            "definition": "Pre-admission ACE inhibitor use.",
            "reference_event": "hospital admission / pre-admission baseline",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists acei_before as Before."
        },
        "acei_during": {
            "definition": "In-hospital ACE inhibitor use.",
            "reference_event": "admission stay",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists acei_during as During."
        },
        "aspirin_before": {
            "definition": "Pre-admission aspirin use.",
            "reference_event": "hospital admission / pre-admission baseline",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists aspirin_before as Before."
        },
        "aspirin_during": {
            "definition": "In-hospital aspirin use.",
            "reference_event": "admission stay",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists aspirin_during as During."
        },
        "vasopressor_during": {
            "definition": "Vasopressor administration during the admission.",
            "reference_event": "in-hospital clinical escalation / acute support",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists vasopressor_during as During and describes it as vasopressor administration."
        },
        "mech_vent_during": {
            "definition": "Mechanical ventilation during the admission.",
            "reference_event": "in-hospital acute supportive care",
            "exact_timing_available": "No",
            "evidence": "Phase F schema lists mech_vent_during as During and describes it as mechanical ventilation."
        },
    }


def classify_treatment_variables() -> dict:
    return {
        "Potential baseline treatment": [
            "statin_before",
            "beta_blocker_before",
            "acei_before",
            "aspirin_before",
        ],
        "Potential acute treatment": [
            "statin_during",
            "beta_blocker_during",
            "acei_during",
            "aspirin_during",
        ],
        "Potential downstream treatment": [
            "statin_after",
        ],
        "Likely downstream/supportive intervention": [
            "vasopressor_during",
            "mech_vent_during",
        ],
        "Timing unresolved": [
            "statin_before",
            "statin_during",
            "statin_after",
            "beta_blocker_before",
            "beta_blocker_during",
            "acei_before",
            "acei_during",
            "aspirin_before",
            "aspirin_during",
            "vasopressor_during",
            "mech_vent_during",
        ],
    }


def treatment_timing_relative_ecg() -> dict:
    return {
        "statin": "Treatment assignment relative to ECG is not directly known. Before variables represent pre-admission medication and do not establish exact timing before a specific ECG; during variables represent in-hospital treatment around the episode.",
        "beta_blocker": "Before variables are pre-admission/chronic use; during variables are in-hospital use. Exact pre-ECG assignment cannot be established from the binary columns alone.",
        "ACE inhibitor": "Before variables are pre-admission/chronic use; during variables are in-hospital use. Exact baseline timing relative to ECG is unavailable.",
        "aspirin": "Before variables are pre-admission/chronic use; during variables are in-hospital use. Exact timing relative to ECG is unresolved."
    }


def treatment_timing_relative_mi(df: pd.DataFrame) -> dict:
    return {
        col: {
            "treatment_indicator_count_on_MI_label_rows": int(
                df.loc[df["Label_Troponin"].isin(["MI_Pre-Incident", "MI_Acute_Presentation"]), col]
                .eq(1)
                .sum()
            ),
            "timing_classification": "UNKNOWN",
            "assessment": (
                "The treatment feature is an admission-window indicator without medication timestamps. "
                "Its name does not establish timing relative to index_mi_time."
            ),
        }
        for col in TREATMENT_VARS
    }


def temporal_ordering_audit(df: pd.DataFrame) -> dict:
    mi_labels = df["Label_Troponin"].isin(["MI_Pre-Incident", "MI_Acute_Presentation"])
    mi_time_rows = df.loc[mi_labels]
    has_both_times = mi_time_rows["ecg_time_dt"].notna() & mi_time_rows["index_mi_time_dt"].notna()
    return {
        "Label_Troponin_is_the_established_MI_temporal_cohort_label": True,
        "MI_Post-Incident_rows": int((df["Label_Troponin"] == "MI_Post-Incident").sum()),
        "MI_label_rows_with_both_ecg_and_index_mi_timestamps": int(has_both_times.sum()),
        "timestamp_fields_reclassify_Label_Troponin": False,
        "treatment_orderings": {
            ordering: "UNRESOLVED — exact treatment assignment/admin timestamps are unavailable."
            for ordering in [
                "ECG -> treatment -> MI",
                "treatment -> ECG -> MI",
                "ECG -> MI -> treatment",
                "treatment -> MI -> ECG",
            ]
        },
        "time_diff_hours_warning": (
            "time_diff_hours is ECG minus index_mi_time for MI patients, but for Control_Symptomatic "
            "it uses an admission-time anchor/fallback and is not MI-relative. Do not infer MI ordering "
            "or post-MI status for controls from this field."
        ),
    }


def candidate_primary_treatments(row_prev: dict, adm_prev: dict, consistency: dict) -> dict:
    candidates = {}
    for var in ["aspirin", "statin", "beta_blocker", "acei"]:
        # map to variables
        if var == "aspirin":
            row_vars = ["aspirin_before", "aspirin_during"]
        elif var == "statin":
            row_vars = ["statin_before", "statin_during", "statin_after"]
        elif var == "beta_blocker":
            row_vars = ["beta_blocker_before", "beta_blocker_during"]
        else:
            row_vars = ["acei_before", "acei_during"]
        row_total = sum(row_prev[v]["exposed_count"] for v in row_vars)
        adm_total = sum(adm_prev[v]["exposed_count"] for v in row_vars)
        consistency_score = max(consistency[v]["percentage_of_admissions_affected"] for v in row_vars)
        candidates[var] = {
            "row_exposed_total": row_total,
            "admission_exposed_total": adm_total,
            "temporal_clarity": "UNRESOLVED unless exact medication timestamps are added",
            "assignment_information": "Binary administrative window indicators only; no exact treatment assignment timestamps",
            "potential_positivity_concerns": "Possible if near-universal exposure in some strata; requires later modeling cohort definition",
            "confounding_by_indication_concerns": "High; chronic and acute medication use are likely correlated with disease severity and clinical indication",
            "compatibility_with_ECG_question": "Partial, but timing relative to ECG is not established well enough for definitive baseline treatment",
            "baseline_establishability": "UNRESOLVED",
            "treatment_specific_time_zero": "UNRESOLVED; exact medication assignment time not in the parquet",
            "consistency_percentage_max": consistency_score,
        }
    return candidates


def build_notebook() -> dict:
    nb = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": [
                "# Phase 2 — Treatment and Outcome Audit\n",
                "\n",
                "Phase 1 is complete and frozen. This notebook audits treatment variables and the current outcome definition without performing causal modeling.\n",
                "\n",
                "The goal is to determine whether the existing treatment variables can support a defensible treatment-specific time zero and whether the outcome definition is suitable for later causal work.\n"
            ]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "import json\n",
                "from pathlib import Path\n",
                "\n",
                "import pandas as pd\n",
                "\n",
                "DATA_DIR = Path(r'c:/Users/anura/OneDrive/Desktop/capstone2/master')\n",
                "cols = ['study_id', 'SubjectID', 'hadm_id', 'ecg_time', 'Label_Troponin', 'is_MI', 'index_mi_time', 'time_diff_hours', 'statin_before', 'statin_during', 'statin_after', 'beta_blocker_before', 'beta_blocker_during', 'acei_before', 'acei_during', 'aspirin_before', 'aspirin_during', 'vasopressor_during', 'mech_vent_during']\n",
                "files = [DATA_DIR / 'train.parquet', DATA_DIR / 'validation.parquet', DATA_DIR / 'test.parquet']\n",
                "df = pd.concat([pd.read_parquet(p, columns=cols) for p in files], ignore_index=True)\n",
                "print('combined_rows', len(df))\n",
                "print('split_rows', {split: len(pd.read_parquet(DATA_DIR / f'{split}.parquet')) for split in ['train','validation','test']})\n",
                "print('treatment_columns', [c for c in df.columns if any(k in c.lower() for k in ['statin','beta','acei','aspirin','vasopressor','vent'])])\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## 1. Use the actual three-way dataset\n",
                "\n",
                "The verified split files are used directly: train = 262,813 rows, validation = 56,319 rows, test = 56,798 rows, combined = 375,930 rows.\n",
                "\n",
                "The main treatment audit uses the combined dataset to describe prevalence and temporal structure, while split-specific checks are preserved and reported separately when needed.\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## 2. Treatment variables and underlying meaning\n",
                "\n",
                "The Phase F dataset schema states that the treatment columns are windowed indicators, not exact medication timestamps. In particular:\n",
                "\n",
                "- `*_before` indicates pre-admission / pre-encounter medication use\n",
                "- `*_during` indicates in-hospital use during the admission\n",
                "- `statin_after` indicates post-discharge use after discharge\n",
                "\n",
                "This means the parquet contains binary treatment indicators tied to encounter windows, not drug administration timestamps. The exact administration times are not available in the current dataset.\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## 3. Treatment prevalence\n",
                "\n",
                "The next code cells quantify exposure prevalence at ECG-row and admission levels.\n"
            ]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "cols = ['statin_before','statin_during','statin_after','beta_blocker_before','beta_blocker_during','acei_before','acei_during','aspirin_before','aspirin_during','vasopressor_during','mech_vent_during']\n",
                "rows = {c: {'exposed_count': int(df[c].eq(1).sum()), 'unexposed_count': int(df[c].eq(0).sum()), 'missing_count': int(df[c].isna().sum()), 'exposure_percentage': round(float(df[c].eq(1).mean() * 100), 3)} for c in cols}\n",
                "adm = df.groupby('hadm_id')[cols].max().reset_index()\n",
                "admissions = {c: {'exposed_count': int(adm[c].fillna(0).gt(0).sum()), 'unexposed_count': int(adm[c].fillna(0).eq(0).sum()), 'missing_count': int(adm[c].isna().sum()), 'exposure_percentage': round(float(adm[c].fillna(0).gt(0).mean() * 100), 3)} for c in cols}\n",
                "print(json.dumps({'ecg_row_level': rows, 'admission_level': admissions}, indent=2))\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## 4. Treatment consistency within admission\n",
                "\n",
                "Because Phase 1 established admission-level as the primary unit, binary treatment values should be consistent within `hadm_id` when they describe an admission-level treatment flag. The next code checks this.\n"
            ]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "consistency = {}\n",
                "for c in cols:\n",
                "    vals = df.groupby('hadm_id')[c].agg(lambda x: set(pd.Series(x).dropna().unique().tolist()))\n",
                "    bad = int(vals.apply(lambda v: len(v) > 1).sum())\n",
                "    consistency[c] = {'n_admissions_with_inconsistent_values': bad, 'percentage_of_admissions_affected': round(100 * bad / len(vals), 3) if len(vals) else 0.0}\n",
                "print(json.dumps(consistency, indent=2))\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## Temporal interpretation correction\n",
                "\n",
                "`time_diff_hours` is not a universal ECG-to-MI variable. For MI patients it is `ecg_time - index_mi_time`; for `Control_Symptomatic` rows it is based on the admission-time anchor/fallback and is not relative to an MI event. Use `Label_Troponin` for the established MI temporal cohort labels. The master modeling dataset contains zero `MI_Post-Incident` rows because that category was excluded during dataset construction. Do not classify control rows as post-MI from a positive `time_diff_hours`, and do not use this field alone to establish whether a covariate preceded the treatment-specific causal baseline/index ECG.\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## 5. Outcome audit\n",
                "\n",
                "The categorical cohort label and raw temporal variable are distinct. `Label_Troponin` carries the established cohort categories; `time_diff_hours` is a raw field whose reference differs between MI patients and controls. The master dataset contains no `MI_Post-Incident` rows: that category was intentionally excluded during modeling-data construction.\n"
            ]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "print('is_MI_is_binary', bool(df['is_MI'].nunique() <= 2))\n",
                "print('Label_Troponin_counts', df['Label_Troponin'].value_counts(dropna=False).to_dict())\n",
                "print('is_MI_by_Label_Troponin')\n",
                "print(pd.crosstab(df['Label_Troponin'], df['is_MI'], dropna=False).to_string())\n",
                "print('label-specific index_mi_time/time_diff_hours availability')\n",
                "print(df.groupby('Label_Troponin', dropna=False).agg(rows=('study_id','size'), index_mi_time_nonnull=('index_mi_time','count'), time_diff_hours_nonnull=('time_diff_hours','count')).to_string())\n",
                "print('time_diff_hours is not a universal ECG-to-MI variable; do not use it to infer MI ordering for controls.')\n",
                "print('outcome_definition_assessment', 'UNRESOLVED — requires later causal outcome definition/audit.')\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## 6. Temporal ordering and baseline eligibility\n",
                "\n",
                "Exact medication timestamps are unavailable, so the ordering of treatment assignment relative to ECG and MI cannot be established from the treatment flags. `time_diff_hours` does not establish whether variables were measured before a treatment-specific causal baseline/index ECG. It is only an ECG-to-index-MI difference for MI patients; for controls it uses an admission-time anchor/fallback. The established categorical MI temporal labels remain `Label_Troponin`, not classifications inferred from the sign of this field.\n"
            ]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "mi_labels = df['Label_Troponin'].isin(['MI_Pre-Incident', 'MI_Acute_Presentation'])\n",
                "mi_times = df.loc[mi_labels].copy()\n",
                "both_times = mi_times['ecg_time'].notna() & mi_times['index_mi_time'].notna()\n",
                "print('MI_Post-Incident rows', int(df['Label_Troponin'].eq('MI_Post-Incident').sum()))\n",
                "print('MI-label rows with both ECG and index MI timestamps', int(both_times.sum()))\n",
                "print('time_diff_hours is retained as a raw variable and is not used here to reclassify Label_Troponin.')\n",
                "print('Treatment orderings: UNRESOLVED because exact treatment assignment/admin timestamps are unavailable.')\n"
            ]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                "## Decision Record\n",
                "\n",
                "Primary candidate treatment(s):\n",
                "- UNRESOLVED. The available data do not provide exact treatment assignment timing for a defensible ECG-based baseline treatment.\n",
                "\n",
                "Reason:\n",
                "- The treatment variables are binary window indicators (`*_before`, `*_during`, `*_after`) defined relative to admission/discharge windows, not exact medication administration timestamps.\n",
                "\n",
                "Treatments excluded from primary analysis:\n",
                "- vasopressor_during, mech_vent_during are excluded from primary exposure modeling because they are acute supportive interventions rather than stable baseline treatments.\n",
                "\n",
                "Treatment timing:\n",
                "What is known:\n",
                "- `*_before` variables are pre-admission baseline indicators.\n",
                "- `*_during` variables are in-hospital, acute-treatment indicators.\n",
                "- `statin_after` is post-discharge and therefore downstream relative to the MI episode.\n",
                "\n",
                "What is unknown:\n",
                "- Exact medication start or administration time relative to ECG and MI.\n",
                "- Whether a binary `*_before` flag reflects treatment assigned at the clinically relevant baseline time rather than chronic pre-existing therapy.\n",
                "\n",
                "Outcome definition:\n",
                "Current definition:\n",
                "- `is_MI` is a binary MI indicator derived from `Label_Troponin` and the project MI labeling workflow.\n",
                "- `Label_Troponin` is the established categorical MI temporal cohort label. The master modeling dataset has zero `MI_Post-Incident` rows because that category was intentionally excluded during dataset construction.\n",
                "- `index_mi_time` availability is reported from the observed data by label; it is not assumed to be missing for all controls.\n",
                "- `time_diff_hours` is ECG minus `index_mi_time` for MI patients. For `Control_Symptomatic` rows it uses the admission-time anchor/fallback and does not represent time relative to MI.\n",
                "\n",
                "Outcome timing:\n",
                "Assessment:\n",
                "- Do not classify master-dataset rows as post-MI merely because `time_diff_hours > 0`; do not use that field alone to assess whether a covariate precedes the treatment-specific baseline/index ECG. The causal outcome definition remains unresolved.\n",
                "\n",
                "Temporal ordering:\n",
                "- Exact treatment-to-ECG-to-MI ordering is UNRESOLVED because treatment timestamps are unavailable. For controls, `time_diff_hours` is not MI-relative.\n",
                "\n",
                "Causal time zero:\n",
                "Status:\n",
                "- UNRESOLVED for all candidate treatments because exact treatment-assignment timing is unavailable.\n",
                "\n",
                "Treatment-specific time zero:\n",
                "- UNRESOLVED for aspirin, statin, beta blocker, and ACE inhibitor.\n",
                "\n",
                "Potential baseline treatments:\n",
                "- statin_before, beta_blocker_before, acei_before, aspirin_before — only as chronic/pre-admission exposure indicators, not as exact baseline treatment assignment.\n",
                "\n",
                "Potential acute treatments:\n",
                "- statin_during, beta_blocker_during, acei_during, aspirin_during — likely acute or in-hospital treatment exposure, but they are not exact assignment indicators.\n",
                "\n",
                "Potential downstream treatments:\n",
                "- statin_after\n",
                "\n",
                "Positivity concerns:\n",
                "- Potentially important if some treatment strata are sparse or nearly all treated; requires later design-specific assessment.\n",
                "\n",
                "Confounding-by-indication concerns:\n",
                "- High. Medication use is likely correlated with disease severity and clinical indication, and the current data do not separate pre-existing treatment from treatment triggered by the acute episode.\n",
                "\n",
                "Temporal inconsistencies:\n",
                "- No within-admission treatment-flag inconsistencies were observed. This does not supply medication timestamps or resolve treatment ordering. Do not interpret `time_diff_hours` as a universal ECG-to-MI variable.\n",
                "\n",
                "Unresolved issues:\n",
                "- Exact treatment assignment timing relative to ECG and MI.\n",
                "- Whether the binary `*_before` flag can serve as a valid baseline treatment for causal analysis.\n",
                "- Whether the current MI label/time definition is sufficiently precise for future causal outcome analysis.\n",
                "\n",
                "Phase 3 handoff:\n",
                "- Phase 3 should only proceed after a separate causal outcome specification and a treatment-timing source audit is completed. The current Phase 2 result is that a defensible causal treatment time zero is not established from the existing parquet data.\n"
            ]}
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"}
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    return nb


def main() -> None:
    combined, split_rows = load_data()
    row_prev = row_level_prevalence(combined, TREATMENT_VARS)
    adm_prev = admission_level_prevalence(combined, TREATMENT_VARS)
    consistency = consistency_within_admission(combined, TREATMENT_VARS)
    outcome = outcome_summary(combined)
    vars_def = variable_definition_table()
    treatment_classification = classify_treatment_variables()
    timing_ecg = treatment_timing_relative_ecg()
    timing_mi = treatment_timing_relative_mi(combined)
    temporal_order = temporal_ordering_audit(combined)
    candidate_treat = candidate_primary_treatments(row_prev, adm_prev, consistency)

    phase2_result = {
        "dataset": {
            "train_rows": int(split_rows["train"]),
            "validation_rows": int(split_rows["validation"]),
            "test_rows": int(split_rows["test"]),
            "combined_rows": int(len(combined)),
            "split_rows": split_rows,
        },
        "treatment_variables": {
            "row_level_prevalence": row_prev,
            "admission_level_prevalence": adm_prev,
            "consistency_within_admission": consistency,
            "classification": treatment_classification,
            "variable_definition": vars_def,
            "relative_to_ecg": timing_ecg,
            "relative_to_mi": timing_mi,
            "temporal_ordering_audit": temporal_order,
        },
        "outcome_variables": outcome,
        "temporal_ordering_audit": temporal_order,
        "candidate_primary_treatments": candidate_treat,
        "phase2_decision_record": {
            "Primary candidate treatment(s)": "UNRESOLVED",
            "Reason": "The parquet provides window-coded treatment indicators but not exact treatment assignment timestamps; a defensible ECG-based baseline treatment cannot be established from the current dataset alone.",
            "Treatments excluded from primary analysis": ["vasopressor_during", "mech_vent_during"],
            "Reason_exclusion": "These are acute supportive interventions rather than stable baseline exposures and are more plausibly downstream severity markers.",
            "Treatment timing": {
                "What is known": "The `*_before` columns represent pre-admission medication exposure, `*_during` columns represent in-hospital use, and `statin_after` is post-discharge use.",
                "What is unknown": "Exact treatment administration times relative to the ECG and MI event; whether a chronic `*_before` medication was assigned at a meaningful baseline time."
            },
            "Outcome definition": "Current definition: binary `is_MI` linked to the categorical Label_Troponin cohort labels. The master dataset contains zero MI_Post-Incident rows because that category was intentionally excluded during modeling-data construction.",
            "Outcome timing": "Assessment: use Label_Troponin for established MI temporal cohort labels. time_diff_hours is ECG minus index_mi_time for MI patients; for Control_Symptomatic it uses the admission-time anchor/fallback and is not MI-relative. Do not classify controls as post-MI from a positive value.",
            "time_diff_hours interpretation": "Do not treat time_diff_hours as a universal ECG-to-MI variable. Do not use it alone to infer whether a variable was measured before the treatment-specific causal baseline/index ECG.",
            "Causal time zero": "Status: UNRESOLVED for all candidate treatments.",
            "Treatment-specific time zero": "UNRESOLVED for aspirin, statin, beta blocker, and ACE inhibitor because exact treatment assignment time is unavailable.",
            "Potential baseline treatments": ["statin_before", "beta_blocker_before", "acei_before", "aspirin_before"],
            "Potential acute treatments": ["statin_during", "beta_blocker_during", "acei_during", "aspirin_during"],
            "Potential downstream treatments": ["statin_after"],
            "Positivity concerns": "UNRESOLVED; requires later modeling-specific assessment.",
            "Confounding-by-indication concerns": "High; disease severity and clinical indication are likely to drive both treatment and outcome.",
            "Temporal inconsistencies": "No within-admission treatment-flag inconsistencies were observed. Exact treatment ordering remains unresolved; time_diff_hours is not MI-relative for controls.",
            "Unresolved issues": [
                "Exact medication start or administration time relative to ECG and MI.",
                "Whether a binary `*_before` flag can serve as a valid baseline treatment for later causal analysis.",
                "Whether the current MI label/time definition is sufficiently precise for later causal outcome analysis."
            ],
            "Phase 3 handoff": "Phase 3 should proceed only after a separate causal outcome specification and a treatment timing audit from the original medication source data are completed. A defensible causal treatment time zero is not established by the current parquet dataset alone."
        }
    }

    OUTPUT_JSON.write_text(json.dumps(phase2_result, indent=2, default=str), encoding="utf-8")
    NOTEBOOK_PATH.write_text(json.dumps(build_notebook(), indent=1), encoding="utf-8")
    print(json.dumps({
        "dataset": phase2_result["dataset"],
        "outcome": phase2_result["outcome_variables"],
        "phase2_status": "completed"
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
