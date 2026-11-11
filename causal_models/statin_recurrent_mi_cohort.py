from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LOGGER = logging.getLogger(__name__)
DEFAULT_LONGITUDINAL_DIR = Path("longitudinal/longitudinal")
DEFAULT_MASTER_DIR = Path("master")
DEFAULT_OUTPUT_DIR = Path("causal_models/data")
MASTER_SPLITS = ("train", "validation", "test")
BASELINE_FEATURES = (
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "statin_before",
    "statin_during",
    "statin_after",
    "aspirin_before",
    "beta_blocker_before",
    "acei_before",
)
TREATMENT_COLUMNS = ("statin_before", "statin_during", "statin_after")
EVENT_TYPES = {
    "recurrent_mi",
    "competing_death",
    "event_free",
    "incomplete_followup",
    "event_order_uncertain",
}


@dataclass(frozen=True)
class CohortPaths:
    longitudinal_dir: Path = DEFAULT_LONGITUDINAL_DIR
    master_dir: Path = DEFAULT_MASTER_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    followup_months: int = 12


def _read_longitudinal(longitudinal_dir: Path) -> dict[str, pd.DataFrame]:
    filenames = {
        "admissions": "admissions_chronology.parquet",
        "mi": "mi_admissions.parquet",
        "observation": "observation_end.parquet",
        "demographics": "patients_demographics.parquet",
    }
    tables: dict[str, pd.DataFrame] = {}
    for key, filename in filenames.items():
        path = longitudinal_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required longitudinal artifact is missing: {path}")
        tables[key] = pd.read_parquet(path)
    return tables


def _check_unique_keys(frame: pd.DataFrame, keys: list[str], name: str) -> None:
    if frame[keys].isna().any().any():
        raise ValueError(f"{name} contains null key values in {keys}")
    duplicates = frame.duplicated(keys, keep=False)
    if duplicates.any():
        sample = frame.loc[duplicates, keys].head(10).to_dict("records")
        raise ValueError(f"{name} has duplicate keys {keys}: {sample}")


def _collapse_master_features(master_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    columns = [
        "SubjectID",
        "hadm_id",
        *BASELINE_FEATURES,
    ]
    frames: list[pd.DataFrame] = []
    patient_split: dict[Any, str] = {}
    split_sizes: dict[str, dict[str, int]] = {}
    for split in MASTER_SPLITS:
        path = master_dir / f"{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Required processed master split is missing: {path}")
        schema_columns = set(pd.read_parquet(path, columns=["SubjectID"]).columns)
        if "SubjectID" not in schema_columns:
            raise ValueError(f"SubjectID is missing from {path}")
        try:
            frame = pd.read_parquet(path, columns=columns)
        except (KeyError, ValueError) as error:
            raise ValueError(
                f"Processed split {path} lacks one or more validated baseline fields: "
                f"{BASELINE_FEATURES}"
            ) from error
        if frame[["SubjectID", "hadm_id"]].isna().any().any():
            raise ValueError(f"Processed split {path} has null patient/admission identifiers.")
        patients = frame["SubjectID"].drop_duplicates().tolist()
        for patient in patients:
            prior_split = patient_split.setdefault(patient, split)
            if prior_split != split:
                raise ValueError(
                    f"Patient {patient} appears in both {prior_split} and {split} master splits."
                )
        split_sizes[split] = {
            "ecg_rows": int(len(frame)),
            "patients": int(frame["SubjectID"].nunique()),
            "admissions": int(frame["hadm_id"].nunique()),
        }
        frames.append(frame)

    raw = pd.concat(frames, ignore_index=True).drop_duplicates()
    value_columns = list(BASELINE_FEATURES)
    nunique = raw.groupby("hadm_id", dropna=False)[value_columns].nunique(dropna=True)
    conflicting = nunique.gt(1).any(axis=1)
    if conflicting.any():
        admissions = conflicting[conflicting].index[:10].tolist()
        raise ValueError(
            "Processed master features vary within an admission; refusing arbitrary "
            f"row selection. Example hadm_id values: {admissions}"
        )

    def first_present(values: pd.Series) -> Any:
        non_null = values.dropna()
        return non_null.iloc[0] if not non_null.empty else pd.NA

    collapsed = (
        raw.groupby(["SubjectID", "hadm_id"], as_index=False, dropna=False)[value_columns]
        .agg(first_present)
        .reset_index(drop=True)
    )
    collapsed["subject_id"] = pd.to_numeric(collapsed["SubjectID"], errors="raise").astype("int64")
    split_by_patient = pd.Series(patient_split, name="source_split")
    collapsed["source_split"] = collapsed["subject_id"].map(split_by_patient)
    return collapsed.drop(columns="SubjectID"), {
        "source_split_sizes": split_sizes,
        "master_admissions_with_features": int(len(collapsed)),
        "master_patients_with_features": int(collapsed["subject_id"].nunique()),
    }


def _prepare_longitudinal_tables(
    tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    admissions = tables["admissions"].copy()
    mi = tables["mi"].copy()
    observation = tables["observation"].copy()
    demographics = tables["demographics"].copy()

    _check_unique_keys(admissions, ["hadm_id"], "admissions_chronology")
    _check_unique_keys(mi, ["hadm_id"], "mi_admissions")
    _check_unique_keys(observation, ["subject_id"], "observation_end")
    _check_unique_keys(demographics, ["subject_id"], "patients_demographics")
    admissions["admittime"] = pd.to_datetime(admissions["admittime"], errors="coerce")
    admissions["dischtime"] = pd.to_datetime(admissions["dischtime"], errors="coerce")
    admissions["deathtime"] = pd.to_datetime(admissions["deathtime"], errors="coerce")
    mi["admittime"] = pd.to_datetime(mi["admittime"], errors="coerce")
    observation["observation_end"] = pd.to_datetime(
        observation["observation_end"],
        errors="coerce",
        format="mixed",
    )
    observation["dod"] = pd.to_datetime(observation["dod"], errors="coerce")
    observation["in_hospital_deathtime"] = pd.to_datetime(
        observation["in_hospital_deathtime"],
        errors="coerce",
    )
    demographics["dod"] = pd.to_datetime(demographics["dod"], errors="coerce")
    if admissions[["admittime", "dischtime"]].isna().any().any():
        raise ValueError("Admissions chronology has invalid admission/discharge timestamps.")
    if mi["admittime"].isna().any():
        raise ValueError("MI admissions contain invalid admission timestamps.")

    deaths_from_admissions = (
        admissions.dropna(subset=["deathtime"])
        .groupby("subject_id", as_index=False)["deathtime"]
        .min()
        .rename(columns={"deathtime": "admission_deathtime"})
    )
    followup = observation.merge(
        demographics[
            ["subject_id", "dod", "anchor_age", "gender"]
        ].rename(
            columns={
                "dod": "demographic_dod",
                "anchor_age": "demographic_anchor_age",
                "gender": "demographic_gender",
            }
        ),
        on="subject_id",
        how="outer",
        validate="one_to_one",
    ).merge(
        deaths_from_admissions,
        on="subject_id",
        how="left",
        validate="one_to_one",
    )
    followup["death_date"] = followup["in_hospital_deathtime"].combine_first(
        followup["admission_deathtime"]
    )
    followup["death_date"] = followup["death_date"].combine_first(followup["dod"])
    followup["death_date"] = followup["death_date"].combine_first(
        followup["demographic_dod"]
    )
    followup["death_time_is_precise"] = (
        followup["in_hospital_deathtime"].notna()
        | followup["admission_deathtime"].notna()
    )

    mi_rows = mi[["subject_id", "hadm_id", "admittime"]].copy()
    mi_rows = mi_rows.rename(
        columns={
            "hadm_id": "mi_hadm_id",
            "admittime": "mi_admittime",
        }
    )
    mi_rows = mi_rows.sort_values(["subject_id", "mi_admittime", "mi_hadm_id"])
    return admissions, mi_rows, followup


def select_index_admissions(admissions: pd.DataFrame, mi_rows: pd.DataFrame) -> pd.DataFrame:
    """Choose each patient's earliest discharge survivor after a prior MI discharge."""
    prior_mi_admissions = mi_rows.merge(
        admissions[["hadm_id", "dischtime"]],
        left_on="mi_hadm_id",
        right_on="hadm_id",
        how="inner",
        validate="many_to_one",
    ).drop(columns="hadm_id")
    prior_mi_admissions = prior_mi_admissions.rename(
        columns={
            "mi_hadm_id": "prior_mi_hadm_id",
            "mi_admittime": "prior_mi_admittime",
            "dischtime": "prior_mi_dischtime",
        }
    )
    prior_mi_admissions = prior_mi_admissions.sort_values(
        ["prior_mi_dischtime", "subject_id", "prior_mi_hadm_id"]
    )

    survivors = admissions.loc[
        admissions["dischtime"].notna()
        & admissions["hospital_expire_flag"].eq(0)
        & (
            admissions["deathtime"].isna()
            | admissions["deathtime"].gt(admissions["dischtime"])
        )
    ].copy()
    patient_deaths = (
        admissions.dropna(subset=["deathtime"])
        .groupby("subject_id", as_index=False)["deathtime"]
        .min()
        .rename(columns={"deathtime": "first_known_death"})
    )
    survivors = survivors.merge(
        patient_deaths,
        on="subject_id",
        how="left",
        validate="many_to_one",
    )
    survivors = survivors.loc[
        survivors["first_known_death"].isna()
        | survivors["first_known_death"].gt(survivors["admittime"])
    ].drop(columns="first_known_death")
    survivors = survivors.sort_values(["admittime", "subject_id", "hadm_id"])
    eligible = pd.merge_asof(
        survivors,
        prior_mi_admissions,
        left_on="admittime",
        right_on="prior_mi_dischtime",
        by="subject_id",
        direction="backward",
        allow_exact_matches=True,
    )
    eligible = eligible.loc[eligible["prior_mi_hadm_id"].notna()].copy()
    eligible = eligible.sort_values(["subject_id", "admittime", "hadm_id"])
    index = eligible.drop_duplicates("subject_id", keep="first").copy()
    index["prior_mi"] = 1
    index["eligible_prior_mi"] = 1
    index["survived_to_index_discharge"] = 1
    return index.reset_index(drop=True)


def build_recurrent_mi_cohort(
    tables: dict[str, pd.DataFrame],
    master_features: pd.DataFrame,
    followup_months: int = 12,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if followup_months < 1:
        raise ValueError("followup_months must be at least one.")
    admissions, mi_rows, followup = _prepare_longitudinal_tables(tables)
    index = select_index_admissions(admissions, mi_rows)
    index["followup_horizon_end"] = index["dischtime"] + pd.DateOffset(
        months=followup_months
    )
    index = index.merge(
        followup[
            [
                "subject_id",
                "observation_end",
                "death_date",
                "death_time_is_precise",
                "is_dead",
                "demographic_anchor_age",
                "demographic_gender",
            ]
        ],
        on="subject_id",
        how="left",
        validate="one_to_one",
    )
    index = index.merge(
        master_features,
        on=["subject_id", "hadm_id"],
        how="left",
        validate="one_to_one",
    )
    index["anchor_age"] = pd.to_numeric(index["anchor_age"], errors="coerce").fillna(
        index["demographic_anchor_age"]
    )
    index["sex_male"] = pd.to_numeric(index["sex_male"], errors="coerce").fillna(
        index["demographic_gender"].map({"M": 1, "F": 0})
    )

    mi_by_patient = {
        patient: group.sort_values(["mi_admittime", "mi_hadm_id"])
        for patient, group in mi_rows.groupby("subject_id", sort=False)
    }
    output_rows: list[dict[str, Any]] = []
    for row in index.itertuples(index=False):
        record = row._asdict()
        origin = record["dischtime"]
        horizon_end = record["followup_horizon_end"]
        observation_end = record.get("observation_end")
        death_date = record.get("death_date")

        patient_mi = mi_by_patient.get(record["subject_id"])
        later_mi = pd.DataFrame(columns=["mi_hadm_id", "mi_admittime"])
        if patient_mi is not None:
            later_mi = patient_mi.loc[patient_mi["mi_admittime"].gt(origin)]
        first_mi = later_mi.iloc[0] if not later_mi.empty else None
        first_mi_time = first_mi["mi_admittime"] if first_mi is not None else pd.NaT
        first_mi_hadm = first_mi["mi_hadm_id"] if first_mi is not None else pd.NA

        death_after_origin = (
            pd.notna(death_date)
            and death_date > origin
            and death_date <= horizon_end
        )
        first_mi_observed = (
            pd.notna(first_mi_time)
            and first_mi_time <= horizon_end
            and (
                pd.isna(observation_end)
                or first_mi_time <= observation_end
            )
        )
        observed_to_horizon = (
            pd.notna(observation_end)
            and observation_end >= horizon_end
        )
        event_type = "incomplete_followup"
        recurrent_mi: Any = pd.NA
        ambiguous_order = False

        if first_mi_observed and death_after_origin:
            precise_death = bool(record["death_time_is_precise"])
            same_calendar_day = death_date.normalize() == first_mi_time.normalize()
            if precise_death and death_date < first_mi_time:
                event_type = "competing_death"
                recurrent_mi = 0
            elif death_date < first_mi_time and not same_calendar_day:
                event_type = "competing_death"
                recurrent_mi = 0
            elif same_calendar_day and not precise_death:
                event_type = "event_order_uncertain"
                ambiguous_order = True
            elif first_mi_time < death_date:
                event_type = "recurrent_mi"
                recurrent_mi = 1
            else:
                event_type = "event_order_uncertain"
                ambiguous_order = True
        elif first_mi_observed:
            event_type = "recurrent_mi"
            recurrent_mi = 1
        elif death_after_origin:
            event_type = "competing_death"
            recurrent_mi = 0
        elif observed_to_horizon:
            event_type = "event_free"
            recurrent_mi = 0

        if event_type in {"recurrent_mi", "competing_death"}:
            event_end = (
                first_mi_time if event_type == "recurrent_mi" else death_date
            )
            followup_end = event_end
        elif event_type == "event_free":
            followup_end = horizon_end
        elif event_type == "event_order_uncertain":
            followup_end = min(first_mi_time, death_date)
        elif pd.notna(observation_end) and observation_end >= origin:
            followup_end = min(observation_end, horizon_end)
        else:
            followup_end = pd.NaT

        record.update(
            {
                "first_subsequent_mi_hadm_id": first_mi_hadm,
                "first_subsequent_mi_admittime": first_mi_time,
                "recurrent_mi": recurrent_mi,
                "death_indicator": int(death_after_origin),
                "death_date": death_date,
                "followup_end_date": followup_end,
                "followup_duration_days": (
                    (followup_end - origin).total_seconds() / 86400.0
                    if pd.notna(followup_end) and followup_end >= origin
                    else pd.NA
                ),
                "observation_end_available": int(pd.notna(observation_end)),
                "observation_end_before_index": int(
                    pd.notna(observation_end) and observation_end < origin
                ),
                "followup_horizon_months": followup_months,
                "followup_complete": bool(
                    event_type in {"recurrent_mi", "competing_death", "event_free"}
                ),
                "event_type": event_type,
                "event_order_uncertain": int(ambiguous_order),
                "treatment_observed": int(pd.notna(record.get("statin_during"))),
            }
        )
        output_rows.append(record)

    cohort = pd.DataFrame(output_rows)
    cohort["index_admittime"] = cohort["admittime"]
    cohort["index_dischtime"] = cohort["dischtime"]
    for column in ("statin_before", "statin_during", "statin_after"):
        if column in cohort:
            cohort[column] = pd.to_numeric(cohort[column], errors="coerce").astype("Int64")
    cohort["recurrent_mi"] = pd.array(cohort["recurrent_mi"], dtype="Int64")
    cohort["prior_mi"] = cohort["prior_mi"].astype("int8")
    cohort["eligible_prior_mi"] = cohort["eligible_prior_mi"].astype("int8")
    cohort["survived_to_index_discharge"] = cohort[
        "survived_to_index_discharge"
    ].astype("int8")
    summary = summarize_cohort(cohort, followup_months)
    return cohort, summary


def summarize_cohort(cohort: pd.DataFrame, followup_months: int) -> dict[str, Any]:
    treatment_known = cohort["statin_during"].notna()
    return {
        "followup_horizon_months": followup_months,
        "index_admissions": int(len(cohort)),
        "unique_patients": int(cohort["subject_id"].nunique()),
        "eligible_prior_mi_patients": int(cohort["eligible_prior_mi"].eq(1).sum()),
        "survived_to_index_discharge": int(
            cohort["survived_to_index_discharge"].eq(1).sum()
        ),
        "treatment_known_admissions": int(treatment_known.sum()),
        "treated_statin_during": int(cohort["statin_during"].eq(1).sum()),
        "control_no_statin_during": int(cohort["statin_during"].eq(0).sum()),
        "treatment_missing": int((~treatment_known).sum()),
        "recurrent_mi_events": int(cohort["event_type"].eq("recurrent_mi").sum()),
        "competing_deaths_before_mi": int(
            cohort["event_type"].eq("competing_death").sum()
        ),
        "event_free_through_horizon": int(cohort["event_type"].eq("event_free").sum()),
        "incomplete_followup": int(
            cohort["event_type"].eq("incomplete_followup").sum()
        ),
        "event_order_uncertain": int(
            cohort["event_type"].eq("event_order_uncertain").sum()
        ),
        "followup_complete": int(cohort["followup_complete"].sum()),
        "followup_incomplete_or_uncertain": int((~cohort["followup_complete"]).sum()),
        "endpoint_missing_due_to_incomplete_or_uncertain_followup": int(
            cohort["recurrent_mi"].isna().sum()
        ),
        "observation_end_missing": int(cohort["observation_end_available"].eq(0).sum()),
        "observation_end_before_index": int(
            cohort["observation_end_before_index"].eq(1).sum()
        ),
        "prescription_and_emar_joined": False,
        "medication_source_note": (
            "Treatment indicators are retained as supplied in the processed master. "
            "No machine-readable prescription/EMAR target-class artifact is available "
            "in the current workspace for admission-level linkage."
        ),
        "index_admission_rule": (
            "Earliest admission per patient that survives to discharge and starts "
            "after the discharge of at least one earlier MI-coded admission."
        ),
        "endpoint_rule": (
            "MI-coded admission strictly after index discharge and within the "
            "follow-up horizon; death before recurrence is a competing event; "
            "unobserved incomplete follow-up is not coded as outcome zero."
        ),
    }


def assign_existing_patient_splits(
    cohort: pd.DataFrame,
    master_dir: Path,
) -> tuple[pd.DataFrame, dict[str, int]]:
    patient_splits: dict[int, str] = {}
    for split in MASTER_SPLITS:
        path = master_dir / f"{split}.parquet"
        patients = pd.read_parquet(path, columns=["SubjectID"])["SubjectID"].dropna().unique()
        for patient in patients:
            key = int(patient)
            existing = patient_splits.setdefault(key, split)
            if existing != split:
                raise ValueError(
                    f"Patient {key} crosses existing master splits: {existing}, {split}"
                )
    result = cohort.copy()
    result["source_split"] = result["subject_id"].map(patient_splits)
    missing = result["source_split"].isna()
    counts = {
        split: int(result["source_split"].eq(split).sum())
        for split in MASTER_SPLITS
    }
    counts["not_in_existing_master_splits"] = int(missing.sum())
    return result, counts


def export_causal_forest_splits(
    cohort: pd.DataFrame,
    master_dir: Path,
    output_dir: Path,
) -> dict[str, int]:
    """Write admission-level Phase 9 inputs using existing patient split membership."""
    assigned, counts = assign_existing_patient_splits(cohort, master_dir)
    columns = [
        "SubjectID",
        "hadm_id",
        "prior_mi",
        "statin_during",
        "recurrent_mi",
        *(
            feature
            for feature in (
                "anchor_age",
                "sex_male",
                "diabetes",
                "hypertension",
                "ckd",
                "aspirin_before",
                "beta_blocker_before",
                "acei_before",
                "statin_before",
            )
            if feature in assigned.columns
        ),
    ]
    export_dir = output_dir / "statin_recurrent_mi_forest_splits"
    export_dir.mkdir(parents=True, exist_ok=True)
    for split in MASTER_SPLITS:
        split_rows = assigned.loc[assigned["source_split"].eq(split)].copy()
        split_rows = split_rows.rename(columns={"subject_id": "SubjectID"})
        split_rows["SubjectID"] = split_rows["SubjectID"].astype("int64")
        split_rows.loc[:, columns].to_parquet(
            export_dir / f"{split}.parquet",
            index=False,
        )
    adjustment_features = [
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
    counts["model_ready_complete_case_admissions"] = int(
        assigned[
            [
                "source_split",
                "statin_during",
                "recurrent_mi",
                *adjustment_features,
            ]
        ]
        .dropna()
        .shape[0]
    )
    return counts


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, default=_json_default, allow_nan=False),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        converted = float(value)
        return converted if np.isfinite(converted) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    raise TypeError(f"Cannot serialize {type(value).__name__} to JSON.")


def run_cohort(paths: CohortPaths) -> tuple[pd.DataFrame, dict[str, Any]]:
    if paths.followup_months < 1:
        raise ValueError("followup_months must be at least one.")
    tables = _read_longitudinal(paths.longitudinal_dir)
    master_features, master_summary = _collapse_master_features(paths.master_dir)
    cohort, summary = build_recurrent_mi_cohort(
        tables,
        master_features,
        followup_months=paths.followup_months,
    )
    split_counts = export_causal_forest_splits(
        cohort,
        paths.master_dir,
        paths.output_dir,
    )
    summary.update(master_summary)
    summary["forest_split_admissions"] = split_counts
    summary["index_admissions_with_master_baseline_features"] = int(
        cohort["source_split"].notna().sum()
    )
    summary["index_admissions_without_master_baseline_features"] = int(
        cohort["source_split"].isna().sum()
    )
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    cohort.to_parquet(
        paths.output_dir / "statin_recurrent_mi_cohort.parquet",
        index=False,
    )
    write_json(
        paths.output_dir / "statin_recurrent_mi_cohort_summary.json",
        summary,
    )
    return cohort, summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a discharge-indexed prior-MI recurrent-event cohort."
    )
    parser.add_argument("--longitudinal-dir", type=Path, default=DEFAULT_LONGITUDINAL_DIR)
    parser.add_argument("--master-dir", type=Path, default=DEFAULT_MASTER_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--followup-months", type=int, default=12)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _, summary = run_cohort(
        CohortPaths(
            longitudinal_dir=args.longitudinal_dir,
            master_dir=args.master_dir,
            output_dir=args.output_dir,
            followup_months=args.followup_months,
        )
    )
    LOGGER.info(
        "Built %s index admissions: recurrent MI=%s, competing death=%s, "
        "event-free=%s, incomplete=%s, uncertain order=%s",
        summary["index_admissions"],
        summary["recurrent_mi_events"],
        summary["competing_deaths_before_mi"],
        summary["event_free_through_horizon"],
        summary["incomplete_followup"],
        summary["event_order_uncertain"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
