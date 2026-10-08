from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2\master")
OUTPUT_JSON = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2\phase1_audit_results.json")


def load_data() -> pd.DataFrame:
    frames = []
    for split in ["train", "validation", "test"]:
        df = pd.read_parquet(DATA_DIR / f"{split}.parquet")
        frames.append(df)
    full = pd.concat(frames, ignore_index=True)
    full["ecg_time_dt"] = pd.to_datetime(full["ecg_time"], errors="coerce", utc=True)
    full["index_mi_time_dt"] = pd.to_datetime(full["index_mi_time"], errors="coerce", utc=True)
    return full


def compute_causal_unit_summary(df: pd.DataFrame) -> dict:
    subject_counts = df.groupby("SubjectID").size()
    hadm_counts = df.groupby("hadm_id").size()
    patient_admissions = df.groupby("SubjectID")["hadm_id"].nunique()
    patient_ecgs = df.groupby("SubjectID").size()
    subject_multi_adm = (patient_admissions > 1).mean()
    subject_multi_ecg = (patient_ecgs > 1).mean()

    admission_summary = (
        df.groupby("hadm_id")
        .agg(
            n_ecgs=("study_id", "count"),
            n_subjects=("SubjectID", "nunique"),
            n_mi=("is_MI", "sum"),
            has_mi=("index_mi_time", lambda s: s.notna().any()),
        )
        .reset_index()
    )
    repeated_admissions = admission_summary[admission_summary["n_ecgs"] > 1]
    admission_mult_ecg = repeated_admissions["n_ecgs"].gt(1).mean()

    patient_summary = (
        df.groupby("SubjectID")
        .agg(
            n_admissions=("hadm_id", "nunique"),
            n_ecgs=("study_id", "count"),
            mi_obs=("is_MI", "sum"),
        )
        .reset_index()
    )

    q = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    return {
        "n_patients": int(df["SubjectID"].nunique()),
        "n_admissions": int(df["hadm_id"].nunique()),
        "n_ecgs": int(len(df)),
        "admissions_per_patient": {
            "min": int(patient_admissions.min()),
            "max": int(patient_admissions.max()),
            "mean": float(patient_admissions.mean()),
            "median": float(patient_admissions.median()),
            "quantiles": {str(k): float(v) for k, v in zip(q, patient_admissions.quantile(q).values)},
        },
        "ecgs_per_patient": {
            "min": int(patient_ecgs.min()),
            "max": int(patient_ecgs.max()),
            "mean": float(patient_ecgs.mean()),
            "median": float(patient_ecgs.median()),
            "quantiles": {str(k): float(v) for k, v in zip(q, patient_ecgs.quantile(q).values)},
        },
        "ecgs_per_admission": {
            "min": int(admission_summary["n_ecgs"].min()),
            "max": int(admission_summary["n_ecgs"].max()),
            "mean": float(admission_summary["n_ecgs"].mean()),
            "median": float(admission_summary["n_ecgs"].median()),
            "quantiles": {str(k): float(v) for k, v in zip(q, admission_summary["n_ecgs"].quantile(q).values)},
            "prop_gt_1": float((admission_summary["n_ecgs"] > 1).mean()),
        },
        "patient_admission_repeat": {
            "fraction_with_multiple_admissions": float(subject_multi_adm),
            "fraction_with_multiple_ecgs": float(subject_multi_ecg),
            "n_patients_with_multiple_admissions": int((patient_admissions > 1).sum()),
            "n_patients_with_multiple_ecgs": int((patient_ecgs > 1).sum()),
        },
        "repeated_ecg_within_admission": {
            "n_admissions_with_multiple_ecgs": int((admission_summary["n_ecgs"] > 1).sum()),
            "fraction_admissions_with_multiple_ecgs": float((admission_summary["n_ecgs"] > 1).mean()),
            "count_distribution": admission_summary["n_ecgs"].value_counts().sort_index().astype(int).to_dict(),
        },
        "patients_with_repeated_admissions": {
            "n": int((patient_admissions > 1).sum()),
            "top_counts": patient_admissions.value_counts().head(10).to_dict(),
        },
    }


def compute_time_diff_summary(df: pd.DataFrame) -> dict:
    mask = df["ecg_time_dt"].notna() & df["index_mi_time_dt"].notna()
    actual_hours = (df.loc[mask, "ecg_time_dt"] - df.loc[mask, "index_mi_time_dt"]).dt.total_seconds() / 3600.0
    diff_series = pd.to_numeric(df.loc[mask, "time_diff_hours"], errors="coerce")
    errors = actual_hours - diff_series
    q = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    summary = {
        "n_valid_pairs": int(mask.sum()),
        "missing_index_mi_time": int(df["index_mi_time"].isna().sum()),
        "time_diff_hours": {
            "min": float(diff_series.min()),
            "max": float(diff_series.max()),
            "mean": float(diff_series.mean()),
            "median": float(diff_series.median()),
            "std": float(diff_series.std(ddof=1)),
            "quantiles": {str(k): float(v) for k, v in zip(q, diff_series.quantile(q).values)},
            "n_positive": int((diff_series > 0).sum()),
            "n_negative": int((diff_series < 0).sum()),
            "n_approx_zero": int((diff_series.abs() < 1e-9).sum()),
        },
        "timestamp_math_check": {
            "max_abs_difference_hours": float(errors.abs().max()),
            "median_abs_difference_hours": float(errors.abs().median()),
            "fraction_exact_match": float((errors.abs() < 1e-9).mean()),
            "fraction_close_within_1min": float((errors.abs() < 1 / 60).mean()),
        },
        "timezone_assumption": "UTC inferred from pd.to_datetime(..., utc=True); all timestamps were treated as timezone-aware timestamps in UTC. "
        "The data appear to be stored in ISO strings without timezone offsets, so UTC is a safe explicit assumption for arithmetic.",
    }
    return summary


def classify_temporal_relation(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    mask = out["ecg_time_dt"].notna() & out["index_mi_time_dt"].notna()
    diff_hours = pd.Series(np.nan, index=out.index, dtype=float)
    diff_hours.loc[mask] = (
        out.loc[mask, "ecg_time_dt"] - out.loc[mask, "index_mi_time_dt"]
    ).dt.total_seconds() / 3600.0
    out["actual_time_diff_hours"] = diff_hours
    out["temporal_relation"] = "missing_index_time"
    out.loc[mask & (diff_hours < -2), "temporal_relation"] = "ECG before MI"
    out.loc[mask & (diff_hours >= -2) & (diff_hours <= 2), "temporal_relation"] = "ECG approximately at MI"
    out.loc[mask & (diff_hours > 2), "temporal_relation"] = "ECG after MI"
    return out


def summarize_temporal_relation(df: pd.DataFrame) -> dict:
    classified = classify_temporal_relation(df)
    mask = classified["index_mi_time_dt"].notna()
    relation_counts = classified.loc[mask, "temporal_relation"].value_counts(normalize=True)
    label_relation = pd.crosstab(classified.loc[mask, "Label_Troponin"], classified.loc[mask, "temporal_relation"]).fillna(0)
    return {
        "counts": {k: int(v) for k, v in classified.loc[mask, "temporal_relation"].value_counts().items()},
        "percentages": {k: float(v) for k, v in classified.loc[mask, "temporal_relation"].value_counts(normalize=True).items()},
        "label_vs_temporal_relation": label_relation.astype(int).to_dict(),
    }


def evaluate_candidate_rules(df: pd.DataFrame) -> dict:
    classified = classify_temporal_relation(df)
    results = {}

    # Candidate A: first ECG within an admission
    if "hadm_id" in df.columns:
        first_admission = (
            df.sort_values(["hadm_id", "ecg_time_dt"])
            .drop_duplicates(subset=["hadm_id"], keep="first")
        )
        results["A_first_ecg_within_admission"] = {
            "eligible": int(len(first_admission)),
            "excluded": int(len(df) - len(first_admission)),
            "MI_retained": int(first_admission["is_MI"].sum()),
            "control_retained": int((~first_admission["is_MI"]).sum()),
        }

    # Candidate B: first ECG before MI event
    mi_df = classified[classified["index_mi_time_dt"].notna()].copy()
    before_mi = mi_df[mi_df["ecg_time_dt"] < mi_df["index_mi_time_dt"]].sort_values(["SubjectID", "hadm_id", "ecg_time_dt"])
    if not before_mi.empty:
        first_before = before_mi.drop_duplicates(subset=["SubjectID", "hadm_id"], keep="first")
        results["B_first_before_MI"] = {
            "eligible": int(len(first_before)),
            "excluded": int(len(mi_df) - len(first_before)),
            "MI_retained": int(first_before["is_MI"].sum()),
            "control_retained": 0,
        }
    else:
        results["B_first_before_MI"] = {"eligible": 0, "excluded": 0, "MI_retained": 0, "control_retained": 0}

    # Candidate C: closest ECG before MI event
    if not mi_df.empty:
        before_mi = mi_df[mi_df["ecg_time_dt"] < mi_df["index_mi_time_dt"]].copy()
        before_mi["distance_to_MI_hours"] = (before_mi["index_mi_time_dt"] - before_mi["ecg_time_dt"]).dt.total_seconds() / 3600.0
        closest = before_mi.sort_values(["SubjectID", "hadm_id", "distance_to_MI_hours", "ecg_time_dt"]).drop_duplicates(subset=["SubjectID", "hadm_id"], keep="first")
        results["C_closest_before_MI"] = {
            "eligible": int(len(closest)),
            "excluded": int(len(mi_df) - len(closest)),
            "MI_retained": int(closest["is_MI"].sum()),
            "control_retained": 0,
        }
    else:
        results["C_closest_before_MI"] = {"eligible": 0, "excluded": 0, "MI_retained": 0, "control_retained": 0}

    # Candidate D: first clinically eligible ECG in admission. This cannot be judged without an explicit eligibility rule.
    results["D_first_clinically_eligible"] = {
        "eligible": "Not directly identifiable without an explicit clinical eligibility criterion",
        "excluded": "No data-defined rule; cannot be implemented from the current parquet files alone",
        "MI_retained": "Undefined without a pre-specified eligibility definition",
        "control_retained": "Undefined without a pre-specified eligibility definition",
    }
    return results


def analyze_repeated_ecgs(df: pd.DataFrame) -> dict:
    hadm_ecg_counts = df.groupby("hadm_id").size()
    patient_adm_counts = df.groupby("SubjectID")["hadm_id"].nunique()
    patient_ecg_counts = df.groupby("SubjectID").size()
    mi_df = df[df["is_MI"] == 1].copy()
    mi_times = mi_df.groupby(["SubjectID", "hadm_id", "index_mi_time_dt"]).size().reset_index(name="n_ecgs_same_event")
    return {
        "admission_level": {
            "n_ecgs_per_admission_min": int(hadm_ecg_counts.min()),
            "n_ecgs_per_admission_max": int(hadm_ecg_counts.max()),
            "n_ecgs_per_admission_mean": float(hadm_ecg_counts.mean()),
            "n_ecgs_per_admission_median": float(hadm_ecg_counts.median()),
            "proportion_admissions_gt_1_ecg": float((hadm_ecg_counts > 1).mean()),
            "n_admissions_with_gt_1_ecg": int((hadm_ecg_counts > 1).sum()),
        },
        "patient_level": {
            "n_admissions_per_subject_min": int(patient_adm_counts.min()),
            "n_admissions_per_subject_max": int(patient_adm_counts.max()),
            "n_ecgs_per_subject_min": int(patient_ecg_counts.min()),
            "n_ecgs_per_subject_max": int(patient_ecg_counts.max()),
            "fraction_subjects_with_multiple_admissions": float((patient_adm_counts > 1).mean()),
            "fraction_subjects_with_multiple_ecgs": float((patient_ecg_counts > 1).mean()),
        },
        "mi_cases_with_multiple_ecgs_near_index": {
            "n_mi_rows": int(len(mi_df)),
            "n_mi_hadm_ids_with_multiple_ecgs": int(mi_df.groupby("hadm_id").size().gt(1).sum()),
            "n_mi_subjects_with_multiple_ecgs": int(mi_df.groupby("SubjectID").size().gt(1).sum()),
        },
    }


def main() -> None:
    split_rows = {
        split: int((DATA_DIR / f"{split}.parquet").exists())
        for split in ["train", "validation", "test"]
    }
    split_rows = {split: int(pd.read_parquet(DATA_DIR / f"{split}.parquet").shape[0]) for split in ["train", "validation", "test"]}
    df = load_data()
    causal_unit = compute_causal_unit_summary(df)
    time_summary = compute_time_diff_summary(df)
    temporal_summary = summarize_temporal_relation(df)
    repeated_summary = analyze_repeated_ecgs(df)
    candidate_summary = evaluate_candidate_rules(df)

    final = {
        "dataset": {
            "train_rows": split_rows["train"],
            "validation_rows": split_rows["validation"],
            "test_rows": split_rows["test"],
            "combined_rows": int(len(df)),
            "splits": split_rows,
            "subject_count": int(df["SubjectID"].nunique()),
            "admission_count": int(df["hadm_id"].nunique()),
            "ecg_count": int(len(df)),
        },
        "causal_unit_summary": causal_unit,
        "time_diff_summary": time_summary,
        "temporal_relation_summary": temporal_summary,
        "repeated_ecg_summary": repeated_summary,
        "candidate_index_ecg_rules": candidate_summary,
        "phase_1_status": "Admission-level is the primary observational unit; ECG time is not yet established as causal time zero; index ECG selection remains unresolved pending the Phase 2 treatment-timing audit.",
    }
    OUTPUT_JSON.write_text(json.dumps(final, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "causal_unit": causal_unit,
        "time_diff": time_summary,
        "temporal": temporal_summary,
        "repeated": repeated_summary,
        "candidate_rules": candidate_summary,
        "phase_1_status": final["phase_1_status"],
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
