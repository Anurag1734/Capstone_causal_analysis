from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from causal_models.phase14_exposure_endpoint.analyze_phase14 import is_acute_mi_code


ROOT = Path(__file__).resolve().parents[2]
COHORT_PATH = ROOT / "causal_models" / "data" / "statin_recurrent_mi_cohort.parquet"
COHORT_SUMMARY_PATH = (
    ROOT / "causal_models" / "data" / "statin_recurrent_mi_cohort_summary.json"
)
SPLIT_DIR = ROOT / "causal_models" / "data" / "statin_recurrent_mi_forest_splits"
EXPOSURE_PATH = ROOT / "causal_models" / "phase14_exposure_endpoint" / "statin_exposure_timestamps.parquet"
FIRST_ADMIN_PATH = (
    ROOT / "causal_models" / "phase14_exposure_endpoint" / "statin_first_administration_summary.csv"
)
EPISODE_PATH = (
    ROOT / "causal_models" / "phase14_exposure_endpoint" / "acute_mi_episode_validation.csv"
)
EPISODE_SUMMARY_PATH = (
    ROOT / "causal_models" / "phase14_exposure_endpoint" / "acute_mi_episode_summary.json"
)
ADMISSIONS_PATH = ROOT / "longitudinal" / "longitudinal" / "admissions_chronology.parquet"
MI_ADMISSIONS_PATH = ROOT / "longitudinal" / "longitudinal" / "mi_admissions.parquet"
DIAGNOSES_PATH = ROOT / "longitudinal" / "longitudinal" / "diagnoses_all.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent

BASELINE_VARIABLES = {
    "anchor_age": "continuous",
    "sex_male": "binary",
    "diabetes": "binary",
    "hypertension": "binary",
    "ckd": "binary",
    "statin_before": "binary_proxy",
    "aspirin_before": "binary_proxy",
    "beta_blocker_before": "binary_proxy",
    "acei_before": "binary_proxy",
    "prior_mi_coded_admission_count": "continuous_proxy",
    "days_since_last_prior_mi_code": "continuous_proxy",
    "prior_admission_count": "continuous_proxy",
    "insurance": "categorical_proxy",
}
INDEX_VARIABLES = {
    "admission_type": "categorical",
    "admission_location": "categorical",
    "race": "categorical",
    "length_of_stay_days": "continuous_index",
    "index_acute_mi_code": "binary_index_diagnosis",
    "heart_failure_code": "binary_index_diagnosis",
    "cardiogenic_shock_code": "binary_index_diagnosis",
    "acute_kidney_injury_code": "binary_index_diagnosis",
    "acute_respiratory_failure_code": "binary_index_diagnosis",
}


def _standardized_mean_difference(
    left: pd.Series,
    right: pd.Series,
    variable_type: str,
) -> float:
    """Return a pooled-SD SMD for continuous or binary/proportion variables."""
    x = pd.to_numeric(left, errors="coerce").dropna().astype(float)
    y = pd.to_numeric(right, errors="coerce").dropna().astype(float)
    if not len(x) or not len(y):
        return float("nan")
    if variable_type in {"binary", "binary_proxy", "binary_index_diagnosis", "categorical"}:
        p1, p0 = float(x.mean()), float(y.mean())
        p_pooled = (len(x) * p1 + len(y) * p0) / (len(x) + len(y))
        pooled = np.sqrt(p_pooled * (1 - p_pooled))
    else:
        pooled = np.sqrt((x.var(ddof=1) + y.var(ddof=1)) / 2)
        p1, p0 = float(x.mean()), float(y.mean())
    if not np.isfinite(pooled) or pooled == 0:
        return float("nan")
    return float((p1 - p0) / pooled)


def _numeric_row(
    frame: pd.DataFrame,
    comparison: str,
    group_col: str,
    left_group: Any,
    right_group: Any,
    variable: str,
    variable_type: str,
    level: Any = None,
) -> dict[str, Any]:
    left_frame = frame.loc[frame[group_col].eq(left_group)]
    right_frame = frame.loc[frame[group_col].eq(right_group)]
    left = pd.to_numeric(left_frame[variable], errors="coerce")
    right = pd.to_numeric(right_frame[variable], errors="coerce")
    if variable_type == "categorical":
        left_nonmissing = left_frame[variable].notna()
        right_nonmissing = right_frame[variable].notna()
        left_values = left_frame.loc[left_nonmissing, variable].eq(level).astype(float)
        right_values = right_frame.loc[right_nonmissing, variable].eq(level).astype(float)
        missing_left = int((~left_nonmissing).sum())
        missing_right = int((~right_nonmissing).sum())
        displayed_variable = f"{variable}={level}"
        smd_type = "binary"
    else:
        left_values = left.dropna()
        right_values = right.dropna()
        missing_left = int(left.isna().sum())
        missing_right = int(right.isna().sum())
        displayed_variable = variable
        smd_type = variable_type
    left_n = int(len(left_frame))
    right_n = int(len(right_frame))
    left_mean = float(left_values.mean()) if len(left_values) else np.nan
    right_mean = float(right_values.mean()) if len(right_values) else np.nan
    return {
        "comparison": comparison,
        "variable": displayed_variable,
        "variable_type": variable_type,
        "level": level,
        "left_group": str(left_group),
        "left_n": left_n,
        "left_missing_n": missing_left,
        "left_missing_percent": (100 * missing_left / left_n) if left_n else np.nan,
        "left_mean_or_prevalence": left_mean,
        "left_sd": float(left_values.std(ddof=1)) if len(left_values) > 1 else np.nan,
        "left_median": float(left_values.median()) if len(left_values) else np.nan,
        "right_group": str(right_group),
        "right_n": right_n,
        "right_missing_n": missing_right,
        "right_missing_percent": (100 * missing_right / right_n) if right_n else np.nan,
        "right_mean_or_prevalence": right_mean,
        "right_sd": float(right_values.std(ddof=1)) if len(right_values) > 1 else np.nan,
        "right_median": float(right_values.median()) if len(right_values) else np.nan,
        "smd": _standardized_mean_difference(left_values, right_values, smd_type),
    }


def compare_groups(
    frame: pd.DataFrame,
    comparison: str,
    group_col: str,
    left_group: Any,
    right_group: Any,
    variables: dict[str, str],
) -> pd.DataFrame:
    rows = []
    for variable, variable_type in variables.items():
        if variable not in frame:
            continue
        if variable_type == "categorical":
            levels = sorted(
                set(
                    frame.loc[
                        frame[group_col].isin([left_group, right_group]), variable
                    ].dropna().astype(str)
                )
            )
            for level in levels:
                work = frame.copy()
                work[variable] = work[variable].astype("string")
                rows.append(
                    _numeric_row(
                        work,
                        comparison,
                        group_col,
                        left_group,
                        right_group,
                        variable,
                        variable_type,
                        level,
                    )
                )
        else:
            rows.append(
                _numeric_row(
                    frame,
                    comparison,
                    group_col,
                    left_group,
                    right_group,
                    variable,
                    variable_type,
                )
            )
    return pd.DataFrame(rows)


def _diagnosis_features(cohort: pd.DataFrame, diagnoses: pd.DataFrame) -> pd.DataFrame:
    cohort_ids = set(cohort["hadm_id"].astype("int64"))
    subset = diagnoses.loc[diagnoses["hadm_id"].isin(cohort_ids)].copy()
    subset["code"] = (
        subset["icd_code"].astype(str).str.upper().str.replace(".", "", regex=False)
    )
    subset["version"] = pd.to_numeric(subset["icd_version"], errors="coerce")
    subset["acute_mi"] = [
        is_acute_mi_code(code, version)
        for code, version in zip(subset["icd_code"], subset["icd_version"])
    ]
    features = []
    for hadm_id, group in subset.groupby("hadm_id"):
        codes9 = group.loc[group["version"].eq(9), "code"]
        codes10 = group.loc[group["version"].eq(10), "code"]
        features.append(
            {
                "hadm_id": int(hadm_id),
                "index_acute_mi_code": int(group["acute_mi"].any()),
                "heart_failure_code": int(
                    codes9.str.startswith("428").any() or codes10.str.startswith("I50").any()
                ),
                "cardiogenic_shock_code": int(
                    codes9.isin({"78551", "78559"}).any()
                    or codes10.str.startswith("R570").any()
                ),
                "acute_kidney_injury_code": int(
                    codes9.str.startswith("584").any() or codes10.str.startswith("N17").any()
                ),
                "acute_respiratory_failure_code": int(
                    codes9.isin({"51881", "51882", "51884"}).any()
                    or codes10.str.startswith("J96").any()
                ),
            }
        )
    return pd.DataFrame(features)


def _prior_mi_history(
    cohort: pd.DataFrame,
    mi_admissions: pd.DataFrame,
) -> pd.DataFrame:
    mi = mi_admissions.copy()
    mi["admittime"] = pd.to_datetime(mi["admittime"], errors="coerce")
    idx = cohort[["subject_id", "hadm_id", "index_admittime"]].copy()
    idx["index_admittime"] = pd.to_datetime(idx["index_admittime"], errors="coerce")
    joined = idx.merge(mi[["subject_id", "hadm_id", "admittime"]], on="subject_id", how="left")
    prior = joined.loc[
        joined["admittime"].lt(joined["index_admittime"])
        & joined["hadm_id_y"].ne(joined["hadm_id_x"])
    ].copy()
    summary = (
        prior.groupby(["subject_id", "hadm_id_x"], as_index=False)
        .agg(
            prior_mi_coded_admission_count=("hadm_id_y", "nunique"),
            most_recent_prior_mi_time=("admittime", "max"),
        )
        .rename(columns={"hadm_id_x": "hadm_id"})
    )
    output = idx[["subject_id", "hadm_id", "index_admittime"]].merge(
        summary, on=["subject_id", "hadm_id"], how="left", validate="one_to_one"
    )
    output["prior_mi_coded_admission_count"] = (
        output["prior_mi_coded_admission_count"].fillna(0).astype(int)
    )
    output["days_since_last_prior_mi_code"] = (
        output["index_admittime"] - output["most_recent_prior_mi_time"]
    ).dt.total_seconds() / 86400
    return output.drop(columns=["index_admittime", "most_recent_prior_mi_time"])


def _attach_diagnosis_features(
    cohort: pd.DataFrame,
    diagnosis_features: pd.DataFrame,
) -> pd.DataFrame:
    frame = cohort[["hadm_id"]].merge(
        diagnosis_features, on="hadm_id", how="left", validate="one_to_one"
    )
    frame["has_index_diagnosis_record"] = frame["index_acute_mi_code"].notna().astype(int)
    return frame


def _make_analysis_frame(
    cohort: pd.DataFrame,
    admissions: pd.DataFrame,
    mi_admissions: pd.DataFrame,
    diagnoses: pd.DataFrame,
    timestamps: pd.DataFrame,
    first_admin: pd.DataFrame,
    split_keys: set[tuple[int, int]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = cohort.copy()
    frame["subject_id"] = frame["subject_id"].astype("int64")
    frame["hadm_id"] = frame["hadm_id"].astype("int64")
    frame["index_admittime"] = pd.to_datetime(frame["index_admittime"])
    frame["index_dischtime"] = pd.to_datetime(frame["index_dischtime"])
    frame["treatment_group"] = frame["statin_during"].map(
        {0: "control", 1: "treated"}
    ).fillna("treatment_missing")
    frame["has_master_baseline_features"] = frame["source_split"].notna().astype(int)
    frame["has_phase9_split_row"] = [
        (int(subject), int(hadm)) in split_keys
        for subject, hadm in zip(frame["subject_id"], frame["hadm_id"])
    ]
    frame["has_index_admission_record"] = frame["hadm_id"].isin(
        admissions["hadm_id"].astype("int64")
    ).astype(int)
    frame["length_of_stay_days"] = (
        frame["index_dischtime"] - frame["index_admittime"]
    ).dt.total_seconds() / 86400
    frame.loc[frame["length_of_stay_days"].lt(0), "length_of_stay_days"] = np.nan
    frame["prior_admission_count"] = (
        pd.to_numeric(frame["admission_seq"], errors="coerce") - 1
    ).clip(lower=0)

    history = _prior_mi_history(cohort, mi_admissions)
    frame = frame.merge(history, on=["subject_id", "hadm_id"], how="left", validate="one_to_one")
    severity = _diagnosis_features(cohort, diagnoses)
    diagnosis_frame = _attach_diagnosis_features(cohort, severity)
    frame = frame.merge(diagnosis_frame, on="hadm_id", how="left", validate="one_to_one")

    linked_ids = set(
        zip(
            timestamps.loc[
                timestamps["record_type"].eq("emar_recorded_administration"),
                "subject_id",
            ].astype("int64"),
            timestamps.loc[
                timestamps["record_type"].eq("emar_recorded_administration"),
                "hadm_id",
            ].astype("int64"),
        )
    )
    frame["emar_linkage_group"] = [
        "linked_emar" if (int(subject), int(hadm)) in linked_ids else "no_linked_emar"
        for subject, hadm in zip(frame["subject_id"], frame["hadm_id"])
    ]
    record_counts = (
        timestamps.loc[timestamps["record_type"].eq("emar_recorded_administration")]
        .groupby(["subject_id", "hadm_id"], as_index=False)
        .agg(
            emar_statins_record_count=("record_type", "size"),
            emar_distinct_medication_names=("medication_identity", "nunique"),
        )
    )
    frame = frame.merge(record_counts, on=["subject_id", "hadm_id"], how="left", validate="one_to_one")
    frame[["emar_statins_record_count", "emar_distinct_medication_names"]] = frame[
        ["emar_statins_record_count", "emar_distinct_medication_names"]
    ].fillna(0)
    frame = frame.merge(
        first_admin[
            [
                "subject_id",
                "hadm_id",
                "first_administration_status",
                "hours_admission_to_first",
                "hours_first_to_discharge",
            ]
        ],
        on=["subject_id", "hadm_id"],
        how="left",
        validate="one_to_one",
    )
    order_counts = (
        timestamps.loc[
            timestamps["record_type"].eq("prescription_order_start_not_administration")
        ]
        .groupby(["subject_id", "hadm_id"])
        .size()
        .rename("statin_order_count")
    )
    frame = frame.join(order_counts, on=["subject_id", "hadm_id"])
    frame["statin_order_count"] = frame["statin_order_count"].fillna(0).astype(int)
    return frame, severity


def _selection_flow(
    cohort: pd.DataFrame,
    frame: pd.DataFrame,
    episode_summary: dict[str, Any],
    linkage_summary: pd.DataFrame,
) -> pd.DataFrame:
    known = cohort["statin_during"].notna()
    outcome_known = cohort["recurrent_mi"].notna()
    base_complete = cohort[
        [
            "anchor_age",
            "sex_male",
            "diabetes",
            "hypertension",
            "ckd",
            "statin_before",
            "aspirin_before",
            "beta_blocker_before",
            "acei_before",
        ]
    ].notna().all(axis=1)
    split = frame["has_phase9_split_row"].astype(bool)
    complete_case = (
        known
        & outcome_known
        & base_complete
        & split
    )
    rows = [
        ("eligible_prior_mi_discharge_survivors", len(cohort), "index cohort; one admission per patient"),
        ("statin_during_known", int(known.sum()), f"missing treatment separately: {int((~known).sum())}"),
        ("baseline_feature_set_complete", int(base_complete.sum()), f"missing any required Phase 11 baseline field: {int((~base_complete).sum())}"),
        ("followup_endpoint_observed", int(outcome_known.sum()), f"incomplete or uncertain endpoint: {int((~outcome_known).sum())}"),
        ("in_existing_phase9_split_files", int(split.sum()), f"not found in exported split files: {int((~split).sum())}"),
        ("known_treatment_in_phase9_split_files", int((known & split).sum()), "known-treatment rows available to Phase 11 split selection"),
        ("phase11_complete_case_population", int(complete_case.sum()), "requires known treatment, observed outcome, baseline features, and split membership"),
        ("phase11_known_treatment_in_split_with_incomplete_followup", int((known & base_complete & ~outcome_known & split).sum()), "not treated as outcome-negative"),
        ("known_treatment_absent_from_phase9_split_files", int((known & ~split).sum()), "absence is established; reason is not retained"),
        ("phase11_removed_due_to_missing_treatment_among_split_rows", int((~known & split).sum()), "treatment not reconstructed"),
        ("phase11_removed_due_to_missing_baseline_features_among_split_rows", int((known & ~base_complete & split).sum()), "baseline features unavailable in this index row"),
    ]
    linkage_n = int(linkage_summary.iloc[0]["administrations_linked"])
    treated_n = int(cohort["statin_during"].eq(1).sum())
    rows.extend(
        [
            ("statin_exposed_admissions", treated_n, "existing statin_during=1 indicator"),
            ("exposed_with_linked_emar_statins", linkage_n, "at least one filtered statin EMAR administration row by subject_id+hadm_id"),
            ("exposed_without_linked_emar_statins", treated_n - linkage_n, "link absence is not evidence of no administration"),
            ("acute_coded_candidate_events", int(episode_summary["candidate_first_acute_admissions"]), "Phase 14 candidates; classification retained"),
        ]
    )
    return pd.DataFrame(rows, columns=["selection_stage", "n", "definition_or_note"])


def _acute_endpoint_summary(episodes: pd.DataFrame) -> pd.DataFrame:
    categories = [
        ("within_1_day", episodes["days_from_index_discharge"].le(1)),
        ("within_7_days", episodes["days_from_index_discharge"].le(7)),
        ("within_30_days", episodes["days_from_index_discharge"].le(30)),
        ("additional_acute_admission_within_7d", episodes["other_acute_admissions_within_7d_after_first"].gt(0)),
        ("additional_acute_admission_within_30d", episodes["other_acute_admissions_within_30d_after_first"].gt(0)),
        ("index_admission_acute_code", episodes["index_admission_acute_coded"].astype(bool)),
        ("transfer_or_readmission_proxy", episodes["adjacent_transfer_evidence"].astype(bool)),
    ]
    rows = [
        {"measure": name, "n": int(mask.sum()), "denominator": int(len(episodes))}
        for name, mask in categories
    ]
    for category, count in episodes["episode_classification"].value_counts().items():
        rows.append(
            {
                "measure": f"classification::{category}",
                "n": int(count),
                "denominator": int(len(episodes)),
            }
        )
    return pd.DataFrame(rows)


def _load_splits() -> tuple[set[tuple[int, int]], dict[str, int]]:
    keys: set[tuple[int, int]] = set()
    counts = {}
    for split in ("train", "validation", "test"):
        data = pd.read_parquet(SPLIT_DIR / f"{split}.parquet")
        counts[split] = len(data)
        keys.update(
            (int(subject), int(admission))
            for subject, admission in zip(data["SubjectID"], data["hadm_id"])
        )
    return keys, counts


def _baseline_recommendation() -> str:
    return """## Adjustment-set recommendation (provisional DAG)

**Primary candidates, only for a newly defined baseline that precedes assignment:** age, sex, diabetes, hypertension, CKD, prior cardiovascular history/severity and recency, verified prior statin use, and pre-assignment concomitant aspirin, beta-blocker, and ACE-inhibitor use. The retained `*_before` medication variables are prescription/order proxies with uncertain history window and adherence; they are not confirmed use and should be sensitivity proxies, not substitutes for verified pre-treatment history. Prior MI eligibility is fixed at 1 in this restricted cohort, so it is not a discriminating adjustment covariate. Admission sequence, insurance, and admission location are imperfect healthcare-utilization/access proxies and should be considered only as sensitivity covariates.

**Sensitivity/indication proxies, not primary adjustment by default:** index-admission diagnosis codes for MI, heart failure, cardiogenic shock, AKI, and respiratory failure; admission type and admission location; and length of stay. These describe the hospitalization, but available diagnosis rows are not timestamped relative to the first statin dose, and length of stay is necessarily determined after admission and may follow treatment. Adjusting for these can condition on post-treatment severity, mediators, or selection/collider variables. A diagnosis code is not a validated severity score or treatment indication.

**Unavailable or inadequate:** measured lipid burden, detailed coronary anatomy, prior MI severity/adjudicated episode count, clinician treatment indication, frailty, outpatient adherence, and complete healthcare access are not present as validated baseline covariates. The retained local data have no ICU-stay, ventilation, or vasopressor table; no such feature was fabricated. EMAR/medication data can inform recorded treatment but do not recover these confounders.

**Exclude from baseline X:** `statin_during` is the exposure; `statin_after` is post-discharge; any post-dose/index-stay severity, procedures, length-of-stay consequences, subsequent medications, recurrent-MI codes, follow-up, and death are outcomes, mediators, or post-treatment variables—not baseline confounders. The existing provisional DAG marks `statin_before` as an imperfect proxy and possible collider of prior use and healthcare access; preserve it as a prespecified sensitivity analysis rather than assuming it is safe primary adjustment. Concomitant `*_before` proxies also need true pre-assignment timing.

The DAG’s selected prior-MI survivor restriction can induce selection bias. Conditioning further on an ECG-linked/model-ready subset or complete follow-up may add selection; IPCW for outcome censoring does not repair missing exposure, absent index features, or selection into ECG data. The available measured set is not sufficient to assert conditional exchangeability."""


def run_analysis() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort = pd.read_parquet(COHORT_PATH)
    admissions = pd.read_parquet(ADMISSIONS_PATH)
    mi_admissions = pd.read_parquet(MI_ADMISSIONS_PATH)
    diagnoses = pd.read_parquet(DIAGNOSES_PATH)
    timestamps = pd.read_parquet(EXPOSURE_PATH)
    first_admin = pd.read_csv(FIRST_ADMIN_PATH)
    episodes = pd.read_csv(EPISODE_PATH)
    episode_summary = json.loads(EPISODE_SUMMARY_PATH.read_text(encoding="utf-8"))
    cohort_summary = json.loads(COHORT_SUMMARY_PATH.read_text(encoding="utf-8"))
    split_keys, split_counts = _load_splits()

    frame, _ = _make_analysis_frame(
        cohort, admissions, mi_admissions, diagnoses, timestamps, first_admin, split_keys
    )
    frame["linked_group"] = frame["emar_linkage_group"].replace(
        {"linked_emar": "linked", "no_linked_emar": "unmatched"}
    )
    treated = frame.loc[frame["statin_during"].eq(1)].copy()
    matched_group = treated["linked_group"].value_counts().to_dict()
    if matched_group.get("linked", 0) != int(
        timestamps.loc[timestamps["record_type"].eq("emar_recorded_administration"), "hadm_id"].nunique()
    ):
        raise ValueError("Phase 14 EMAR linkage counts do not match unique-admission linkage status.")

    baseline_variables = dict(BASELINE_VARIABLES)
    baseline_variables["prior_mi"] = "binary"
    baseline_comparison = compare_groups(
        frame.loc[frame["statin_during"].notna()],
        "treated_vs_control",
        "treatment_group",
        "treated",
        "control",
        baseline_variables,
    )
    baseline_comparison.to_csv(OUTPUT_DIR / "baseline_treatment_comparison.csv", index=False)
    index_variables = dict(INDEX_VARIABLES)
    index_comparison = compare_groups(
        frame.loc[frame["statin_during"].notna()],
        "treated_vs_control_index_descriptive",
        "treatment_group",
        "treated",
        "control",
        index_variables,
    )
    index_comparison.to_csv(OUTPUT_DIR / "index_severity_comparison.csv", index=False)

    emar_variables = dict(BASELINE_VARIABLES)
    emar_variables.update(INDEX_VARIABLES)
    emar_variables.update(
        {
            "has_index_admission_record": "binary",
            "has_master_baseline_features": "binary",
            "has_phase9_split_row": "binary",
            "emar_statins_record_count": "continuous",
            "emar_distinct_medication_names": "continuous",
            "statin_order_count": "continuous",
        }
    )
    link_comparison = compare_groups(
        treated,
        "linked_vs_unmatched_emar_within_statin_during_1",
        "linked_group",
        "linked",
        "unmatched",
        emar_variables,
    )
    link_comparison.to_csv(OUTPUT_DIR / "emar_linkage_comparison.csv", index=False)

    selection = _selection_flow(cohort, frame, episode_summary["acute_episode_validation"], pd.read_csv(
        ROOT / "causal_models" / "phase14_exposure_endpoint" / "statin_exposure_linkage_summary.csv"
    ))
    selection.to_csv(OUTPUT_DIR / "selection_missingness_flow.csv", index=False)
    acute = _acute_endpoint_summary(episodes)
    acute.to_csv(OUTPUT_DIR / "acute_mi_endpoint_validation_summary.csv", index=False)

    # Keep a row-level table for the linkage comparison, avoiding aggregation-only reporting.
    linkage_rows = treated[
        [
            "subject_id",
            "hadm_id",
            "linked_group",
            "has_index_admission_record",
            "has_master_baseline_features",
            "has_phase9_split_row",
            "first_administration_status",
            "emar_statins_record_count",
            "statin_order_count",
        ]
    ].copy()
    linkage_rows.to_csv(OUTPUT_DIR / "emar_linkage_membership.csv", index=False)

    known = frame.loc[frame["statin_during"].notna()]
    complete_case_n = int(
        (
            known["recurrent_mi"].notna()
            & known["has_phase9_split_row"]
            & known[list(BASELINE_VARIABLES)[:9]].notna().all(axis=1)
        ).sum()
    )
    flow_map = dict(zip(selection["selection_stage"], selection["n"]))
    prior_count_known = int(frame["prior_mi_coded_admission_count"].notna().sum())
    los_invalid = int(
        (
            pd.to_datetime(cohort["dischtime"])
            < pd.to_datetime(cohort["admittime"])
        ).sum()
    )
    stats = {
        "eligible_cohort_n": int(len(cohort)),
        "unique_patients": int(cohort["subject_id"].nunique()),
        "treatment_known_n": int(cohort["statin_during"].notna().sum()),
        "treated_n": int(cohort["statin_during"].eq(1).sum()),
        "control_n": int(cohort["statin_during"].eq(0).sum()),
        "treatment_missing_n": int(cohort["statin_during"].isna().sum()),
        "all_index_admissions_match_admissions_chronology": bool(frame["has_index_admission_record"].eq(1).all()),
        "baseline_features_available_n": int(frame["has_master_baseline_features"].sum()),
        "not_in_phase9_split_files_n": int((~frame["has_phase9_split_row"]).sum()),
        "phase9_split_sizes": split_counts,
        "phase9_unique_admission_rows": int(len(split_keys)),
        "phase11_complete_case_n": complete_case_n,
        "observed_endpoint_n": int(cohort["recurrent_mi"].notna().sum()),
        "incomplete_or_uncertain_followup_n": int(cohort["recurrent_mi"].isna().sum()),
        "phase11_known_treatment_incomplete_followup_n": int(
            (cohort["statin_during"].notna() & cohort["recurrent_mi"].isna()).sum()
        ),
        "missing_baseline_feature_n": int(
            (~cohort[list(BASELINE_VARIABLES)[:9]].notna().all(axis=1)).sum()
        ),
        "exposed_with_emar_record_n": int(matched_group.get("linked", 0)),
        "exposed_without_emar_record_n": int(matched_group.get("unmatched", 0)),
        "exposed_with_valid_in_admission_first_emar_n": int(
            first_admin["first_administration_status"]
            .eq("observed_within_index_admission")
            .sum()
        ),
        "prescription_order_records_for_exposed_n": int(
            timestamps["record_type"]
            .eq("prescription_order_start_not_administration")
            .sum()
        ),
        "prior_mi_coded_admission_count_available_n": prior_count_known,
        "negative_or_invalid_index_length_of_stay_n": los_invalid,
        "index_diagnosis_record_missing_n": int(frame["has_index_diagnosis_record"].eq(0).sum()),
        "severity_code_feature_missing_n": int(frame["index_acute_mi_code"].isna().sum()),
        "phase14_acute_candidate_n": int(len(episodes)),
        "phase14_acute_classification_counts": {
            str(k): int(v)
            for k, v in episodes["episode_classification"].value_counts().items()
        },
        "phase14_timing_counts": {
            "within_1_day": int(episodes["days_from_index_discharge"].le(1).sum()),
            "within_7_days": int(episodes["days_from_index_discharge"].le(7).sum()),
            "within_30_days": int(episodes["days_from_index_discharge"].le(30).sum()),
        },
        "confirmed_prior_preprocessing_exclusion_n": 0,
        "index_admissions_absent_from_phase9_splits_n": int((~frame["has_phase9_split_row"]).sum()),
        "previous_preprocessing_exclusion_interpretation": "551 index admissions are absent from the exported Phase 9 split rows. The retained artifacts do not contain a per-admission exclusion log that distinguishes deliberate ECG/data filtering from absent ECG/master coverage. Do not equate this with a confirmed preprocessing exclusion.",
        "index_severity_timing_caveat": "Diagnosis codes and length of stay are index-stay summaries with no timing relative to first dose; they are descriptive/sensitivity variables only.",
        "selection_note": "IPCW for incomplete outcome follow-up cannot correct missing treatment, missing index master features, or ECG-linked selection.",
        "recommendation": "B - conditional go for descriptive in-hospital exposure comparisons; pause further causal effect estimation pending endpoint, linkage selection, and confounding validation.",
    }
    (OUTPUT_DIR / "phase15_summary.json").write_text(
        json.dumps(stats, indent=2, default=str), encoding="utf-8"
    )
    report = _build_report(
        stats,
        baseline_comparison,
        index_comparison,
        link_comparison,
        selection,
        acute,
        cohort_summary,
    )
    (OUTPUT_DIR / "phase15_scientific_decision_report.md").write_text(report, encoding="utf-8")
    return stats


def _fmt_smd_table(frame: pd.DataFrame, variables: list[str], cap: int = 15) -> str:
    subset = frame.loc[frame["variable"].isin(variables)].copy()
    if subset.empty:
        return "_No requested measures were available._"
    subset = subset.head(cap)
    lines = [
        "| Variable | Exposed mean/prevalence | Control mean/prevalence | SMD | Missing exposed/control |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in subset.itertuples(index=False):
        lines.append(
            f"| {row.variable} | {row.left_mean_or_prevalence:.3f} | "
            f"{row.right_mean_or_prevalence:.3f} | {row.smd:.3f} | "
            f"{row.left_missing_n}/{row.right_missing_n} |"
        )
    return "\n".join(lines)


def _build_report(
    stats: dict[str, Any],
    baseline: pd.DataFrame,
    index: pd.DataFrame,
    linkage: pd.DataFrame,
    selection: pd.DataFrame,
    acute: pd.DataFrame,
    cohort_summary: dict[str, Any],
) -> str:
    base_vars = [
        "anchor_age",
        "sex_male",
        "diabetes",
        "hypertension",
        "ckd",
        "statin_before",
        "aspirin_before",
        "beta_blocker_before",
        "acei_before",
        "prior_mi_coded_admission_count",
        "days_since_last_prior_mi_code",
    ]
    key_link_vars = [
        "anchor_age",
        "sex_male",
        "diabetes",
        "hypertension",
        "ckd",
        "statin_before",
        "prior_mi_coded_admission_count",
        "length_of_stay_days",
        "has_index_admission_record",
        "has_master_baseline_features",
        "has_phase9_split_row",
    ]
    cohort_flow = "\n".join(
        [
            "| Selection stage | N | Definition / note |",
            "|---|---:|---|",
            *(
                f"| {row.selection_stage} | {row.n} | {row.definition_or_note} |"
                for row in selection.itertuples(index=False)
            ),
        ]
    )
    linked_summary = _fmt_smd_table(linkage, key_link_vars)
    baseline_summary = _fmt_smd_table(baseline, base_vars, cap=20)
    index_summary = _fmt_smd_table(
        index,
        [
            "length_of_stay_days",
            "index_acute_mi_code",
            "heart_failure_code",
            "cardiogenic_shock_code",
            "acute_kidney_injury_code",
            "acute_respiratory_failure_code",
        ],
        cap=20,
    )
    class_lines = "\n".join(
        f"- {name}: {count:,}"
        for name, count in stats["phase14_acute_classification_counts"].items()
    )
    p1, p0 = int(stats["treated_n"]), int(stats["control_n"])
    missing_treatment = int(stats["treatment_missing_n"])
    incomplete_known = int(stats["phase11_known_treatment_incomplete_followup_n"])
    unmatched = int(stats["exposed_without_emar_record_n"])
    phase11_n = int(stats["phase11_complete_case_n"])
    # Explain controlled comparisons without presenting a causal interpretation.
    return f"""# Phase 15: Cohort Selection, Confounding and Endpoint Validation

## Scope and estimand

This report reuses the saved Phase 14 EMAR/prescription linkages, episode classifications, existing cohort, diagnosis records and patient-level splits. No treatment indicators, datasets, or models were rebuilt or modified; no treatment-effect estimates were calculated. The descriptive treatment comparison is `statin_during=1` versus `0` in the known-treatment subset, not an initiation-at-discharge effect.

## Workstream A — EMAR linkage selection

Of {stats['treated_n']:,} already exposed admissions, {stats['exposed_with_emar_record_n']:,} ({100*stats['exposed_with_emar_record_n']/stats['treated_n']:.2f}%) had at least one statin-named EMAR row satisfying Phase 14’s recorded-administration filter and exact `subject_id`+`hadm_id` match. {unmatched:,} ({100*unmatched/stats['treated_n']:.2f}%) had no such row. The validated first in-admission timestamp was available for {stats['exposed_with_valid_in_admission_first_emar_n']:,}. The 1,481 are **unmatched by this extraction/linkage rule**, not untreated or proven administration failures. Phase 14 retained 7,608 EMAR rows on 1,505 admissions; 7,574 timestamps were within the index interval, 33 before admission and one after discharge.

The saved EMAR output is already filtered to statin medication-name matches, administration-like event statuses, and exact admission identifiers. It does not retain declined/not-administered statin rows or non-statin EMAR context for unmatched admissions, so it cannot determine whether absence reflects a non-administration status, drug-name mapping, missing/invalid ID, a different admission, or deliberate preprocessing. Prescription-order presence is separately included in the comparison; it is not proof of administration.

**Index admission availability:** all {stats['eligible_cohort_n']:,} cohort `hadm_id`s are present in `admissions_chronology.parquet`; the treated linked and unmatched admissions all have the processed master baseline row and Phase 9 split membership. Therefore, missing EMAR linkage is not explained by a missing index-admission chronology record or absent processed feature row in these groups. It is not possible to determine whether upstream ECG cleaning affected EMAR processing; no per-admission EMAR exclusion log was retained. A present feature row does not establish an ECG from the index admission specifically.

| Measure | EMAR-linked | No linked EMAR | SMD |
|---|---:|---:|---:|
{_table_rows(linkage, key_link_vars)}

Full group statistics, categories, missingness, and SMDs: `emar_linkage_comparison.csv`; row membership and order/admin counts: `emar_linkage_membership.csv`.

## Workstream B — Baseline and index-admission differences

There are {p1:,} treated and {p0:,} controls with known `statin_during`; {missing_treatment:,} additional patients have missing treatment and are not reclassified. Group summaries and SMDs below are descriptive, unadjusted. Large absolute SMDs flag observed imbalance; they do not prove causal confounding or its absence.

### Baseline variables

{_table_rows(baseline, base_vars)}

`statin_before`, aspirin, beta-blocker, and ACE-inhibitor `*_before` indicators are prescription/order proxies with uncertain timing and adherence. Prior MI is 1 for every cohort member by eligibility; prior MI admission count/recency are based on MI-coded admissions and may not equal distinct clinical episodes. Age and sex are available across the cohort; most other master-derived baseline fields are available only in the 4,656 known-treatment rows.

### Index stay and diagnosis-derived severity proxies

{_table_rows(index, ['length_of_stay_days','index_acute_mi_code','heart_failure_code','cardiogenic_shock_code','acute_kidney_injury_code','acute_respiratory_failure_code'])}

These are index-admission diagnoses or completed length of stay without reliable timing relative to first statin administration. They may reflect post-exposure severity, mediators, or indication and are **not primary baseline adjustment variables**. Diagnosis codes were left missing when no index-admission diagnosis record was available rather than recoded to absence; diagnosis coverage was available for {stats['eligible_cohort_n'] - stats['index_diagnosis_record_missing_n']:,}/{stats['eligible_cohort_n']:,} admissions. The diagnosis-derived fields indicate a code somewhere in the admission, not when it occurred or severity. ICU admission, ventilation and vasopressor measures are unavailable in the retained local tables; they were not fabricated. Full comparisons and missingness are in `index_severity_comparison.csv`.

## Workstream C — Adjustment strategy against the existing provisional DAG

{_baseline_recommendation()}

## Workstream D — Acute MI endpoint

The Phase 14 classification of all 555 acute-code candidates is retained unchanged:

{class_lines}

There were {stats['phase14_timing_counts']['within_1_day']} events within 1 day, {stats['phase14_timing_counts']['within_7_days']} within 7 days, and {stats['phase14_timing_counts']['within_30_days']} within 30 days of discharge. The retained review found 54 candidates with another acute-coded admission within 30 days after the first event and 136 with a transfer/location chronology proxy. The index admission itself had acute MI codes in 233 candidates. Diagnosis combinations and chronology identify candidates and continuity/transfer concerns, but no clinical notes or adjudication establish distinct MI episodes. The 555-event endpoint cannot currently be treated as a clinically validated count of distinct recurrent MIs. No early candidate was removed.

## Workstream E — Selection and missingness (kept separate)

{cohort_flow}

All 4,656 known-treatment rows are present in the exported split files. Of these, {phase11_n:,} entered the Phase 11 complete-case population and {incomplete_known:,} had incomplete/uncertain follow-up. Separately, 2,338 of the 2,889 missing-treatment rows appear in the split files, while 551 are absent from them. The 1,481 EMAR-unmatched exposed admissions are another distinct linkage category and must not be merged with either source of missingness.

The saved preprocessing summary reports {cohort_summary.get('index_admissions_without_master_baseline_features', 'unknown'):,} index admissions without a matching master baseline-feature row and {cohort_summary.get('forest_split_admissions', {}).get('not_in_existing_master_splits', 'unknown'):,} not present in the Phase 9 patient split files. The retained data do not preserve a row-level cleaning/exclusion reason, so the 551 absent split rows cannot be labeled a proven intentional preprocessing exclusion; they are all in the missing-treatment group. The known-treatment rows are present in the split set, and the complete-case reduction among those is due to incomplete/uncertain outcome follow-up. Selection into ECG-linked features may limit generalizability. IPCW for incomplete follow-up does not correct absent treatment, missing baseline features, EMAR linkage, or ECG selection.

## Workstream F — Scientific decision

### **B. CONDITIONAL GO — descriptive in-hospital exposure comparison only; pause further causal effect estimation**

The existing exposure indicator and covariates permit descriptive comparisons, and timestamped EMAR administrations were linked for 1,500 admissions. However, 1,481 treated admissions lack a filtered exact-ID EMAR match with no retained audit trail that explains why. The acute-code endpoint includes 555 candidates but cannot identify which are distinct clinical episodes. Confounding by indication and severity is incompletely controlled: lipid burden, coronary disease burden, clinical indication, and prior MI severity are not measured as validated baseline fields; index-stay severity timestamps and strong ICU supports are unavailable. The observed baseline and utilization variables do not establish exchangeability, and selected prior-MI survivor plus ECG/master/complete-case selection remain concerns.

**Do not fit another ATE/CATE model yet. Next exact research action:** generate and retain an EMAR inclusion/exclusion audit for all treated index admissions from raw `emar.csv`, separately tallying medication-name matches, status/event-text inclusion/exclusion, missing/unmatched IDs, and admission mismatch; in parallel, obtain clinical adjudication or a validated episode-linkage rule for the 555 candidates. Then construct a timestamp-aligned confounding set using only pre-dose covariates and explicitly address missing-treatment/ECG selection before deciding whether causal estimation is justified.

No causal effect is established by these descriptive comparisons.
"""


def _table_rows(frame: pd.DataFrame, variables: list[str]) -> str:
    subset = frame.loc[frame["variable"].isin(variables)]
    if subset.empty:
        return "| No measurements | | | | |\n|---|---:|---:|---:|---:|"
    lines = [
        "| Variable | Left mean/prevalence | Right mean/prevalence | SMD | Missing L/R |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in subset.itertuples(index=False):
        smd = "NA" if pd.isna(row.smd) else f"{row.smd:.3f}"
        left = "NA" if pd.isna(row.left_mean_or_prevalence) else f"{row.left_mean_or_prevalence:.3f}"
        right = "NA" if pd.isna(row.right_mean_or_prevalence) else f"{row.right_mean_or_prevalence:.3f}"
        lines.append(
            f"| {row.variable} | {left} | {right} | {smd} | "
            f"{row.left_missing_n}/{row.right_missing_n} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    run_analysis()
