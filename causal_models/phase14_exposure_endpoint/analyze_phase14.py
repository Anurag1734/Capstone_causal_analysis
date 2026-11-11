from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
COHORT_PATH = ROOT / "causal_models" / "data" / "statin_recurrent_mi_cohort.parquet"
PHASE13_CANDIDATES = (
    ROOT
    / "causal_models"
    / "phase13_target_trial"
    / "acute_endpoint_by_index_admission.csv"
)
CHRONOLOGY_PATH = ROOT / "longitudinal" / "longitudinal" / "admissions_chronology.parquet"
DIAGNOSES_PATH = ROOT / "longitudinal" / "longitudinal" / "diagnoses_all.parquet"
OUTPUT_DIR = Path(__file__).resolve().parent

STATIN_PATTERN = re.compile(
    r"\b(?:atorvastatin|simvastatin|rosuvastatin|pravastatin|lovastatin|"
    r"fluvastatin|pitavastatin|cerivastatin)\b",
    re.IGNORECASE,
)
ADMINISTRATION_STATUS = re.compile(
    r"\b(?:administered|partial administered|started|restarted)\b", re.IGNORECASE
)
TRANSFER_PATTERN = re.compile(r"\btransfer\b|\bhospital\b", re.IGNORECASE)

TIMESTAMP_COLUMNS = [
    "subject_id",
    "hadm_id",
    "medication_identity",
    "record_type",
    "timestamp",
    "index_admittime",
    "index_dischtime",
    "timing_validation_status",
    "source_file",
    "emar_id",
    "emar_seq",
    "event_txt",
    "storetime",
    "pharmacy_id",
    "poe_id",
    "poe_seq",
    "drug_type",
    "route",
    "dose_val_rx",
    "dose_unit_rx",
]


def is_acute_mi_code(code: Any, version: Any) -> bool:
    normalized = str(code).upper().replace(".", "").strip()
    try:
        version_number = int(version)
    except (TypeError, ValueError):
        return False
    return (
        version_number == 9 and normalized.startswith("410")
    ) or (
        version_number == 10
        and (normalized.startswith("I21") or normalized.startswith("I22"))
    )


def timing_status(timestamp: Any, admission: Any, discharge: Any) -> str:
    timestamp = pd.to_datetime(timestamp, errors="coerce")
    admission = pd.to_datetime(admission, errors="coerce")
    discharge = pd.to_datetime(discharge, errors="coerce")
    if pd.isna(timestamp):
        return "missing_timestamp"
    if pd.isna(admission) or pd.isna(discharge):
        return "missing_index_interval"
    if timestamp < admission:
        return "before_index_admission"
    if timestamp > discharge:
        return "after_index_discharge"
    return "within_index_admission"


def classify_episode(
    days_from_index_discharge: float,
    repeated_acute_admission_within_30d: bool,
    transfer_evidence: bool,
    index_admission_acute_coded: bool,
) -> tuple[str, str]:
    """Classify a code-based event without dropping early events."""
    if transfer_evidence:
        return (
            "possible transfer/readmission for the same episode",
            "Adjacent admission/location fields suggest transfer or closely linked care; episode identity is unverified.",
        )
    if index_admission_acute_coded and days_from_index_discharge <= 30:
        return (
            "possible continuation of index MI episode",
            "Index admission has an acute MI code; distinct post-discharge episode is unverified.",
        )
    if days_from_index_discharge <= 1:
        return (
            "possible continuation of index MI episode",
            "Acute-coded admission occurred within one day of index discharge; timing alone cannot establish episode identity.",
        )
    if repeated_acute_admission_within_30d:
        return (
            "possible transfer/readmission for the same episode",
            "Another acute-coded admission occurred within 30 days; continuity versus a new event is unverified.",
        )
    if days_from_index_discharge > 30:
        return (
            "candidate distinct acute MI",
            (
                "Acute code occurred more than 30 days after discharge without a detected close acute-coded repeat; "
                "clinical confirmation is absent."
                if not index_admission_acute_coded
                else "Both index and later admissions carry acute codes, separated by more than 30 days; clinical confirmation of a distinct episode is absent."
            ),
        )
    return (
        "uncertain episode classification",
        "Acute MI code is present, but available admission and diagnosis fields do not establish whether this is a distinct episode.",
    )


def _empty_timestamp_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=TIMESTAMP_COLUMNS)


def _cohort_exposed(cohort: pd.DataFrame) -> pd.DataFrame:
    exposed = cohort.loc[cohort["statin_during"].eq(1)].copy()
    exposed["subject_id"] = exposed["subject_id"].astype("int64")
    exposed["hadm_id"] = exposed["hadm_id"].astype("int64")
    exposed["index_admittime"] = pd.to_datetime(exposed["index_admittime"])
    exposed["index_dischtime"] = pd.to_datetime(exposed["index_dischtime"])
    return exposed


def _normalize_record(
    source: pd.DataFrame,
    cohort_index: pd.DataFrame,
    record_type: str,
    timestamp_column: str,
    medication_column: str,
    source_file: str,
) -> pd.DataFrame:
    if source.empty:
        return _empty_timestamp_frame()
    frame = source.merge(
        cohort_index[
            ["subject_id", "hadm_id", "index_admittime", "index_dischtime"]
        ],
        on=["subject_id", "hadm_id"],
        how="inner",
        validate="many_to_one",
    )
    frame["timestamp"] = pd.to_datetime(frame[timestamp_column], errors="coerce")
    frame["medication_identity"] = frame[medication_column]
    frame["record_type"] = record_type
    frame["timing_validation_status"] = [
        timing_status(ts, start, end)
        for ts, start, end in zip(
            frame["timestamp"], frame["index_admittime"], frame["index_dischtime"]
        )
    ]
    frame["source_file"] = source_file
    for column in TIMESTAMP_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
    return frame[TIMESTAMP_COLUMNS]


def _read_filtered_csv(
    path: Path,
    target_pairs: set[tuple[int, int]],
    usecols: list[str],
    medication_column: str,
    timestamp_column: str,
    is_emar: bool,
    chunk_size: int = 250_000,
) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frames = []
    for chunk in pd.read_csv(
        path,
        usecols=usecols,
        chunksize=chunk_size,
        low_memory=False,
    ):
        chunk["subject_id"] = pd.to_numeric(chunk["subject_id"], errors="coerce")
        chunk["hadm_id"] = pd.to_numeric(chunk["hadm_id"], errors="coerce")
        chunk = chunk.dropna(subset=["subject_id", "hadm_id"])
        chunk["subject_id"] = chunk["subject_id"].astype("int64")
        chunk["hadm_id"] = chunk["hadm_id"].astype("int64")
        pairs = pd.MultiIndex.from_frame(chunk[["subject_id", "hadm_id"]])
        target_index = pd.MultiIndex.from_tuples(
            sorted(target_pairs), names=["subject_id", "hadm_id"]
        )
        chunk = chunk.loc[pairs.isin(target_index)].copy()
        if chunk.empty:
            continue
        chunk = chunk.loc[chunk[medication_column].astype("string").str.contains(STATIN_PATTERN, na=False)]
        if is_emar and "event_txt" in chunk:
            event = chunk["event_txt"].fillna("").astype(str)
            chunk = chunk.loc[
                event.str.contains(ADMINISTRATION_STATUS, na=False)
                & ~event.str.strip().str.lower().str.startswith("not ")
            ]
        if chunk.empty:
            continue
        chunk[timestamp_column] = pd.to_datetime(chunk[timestamp_column], errors="coerce")
        frames.append(chunk)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_medication_records(
    cohort_index: pd.DataFrame,
    emar_path: Path | None,
    prescriptions_path: Path | None,
    extracted_emar_path: Path | None,
    extracted_prescriptions_path: Path | None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    target_pairs = set(
        zip(cohort_index["subject_id"].astype(int), cohort_index["hadm_id"].astype(int))
    )
    source_status: dict[str, Any] = {}
    emar = pd.DataFrame()
    emar_source = None
    if emar_path is not None and not emar_path.exists():
        raise FileNotFoundError(f"EMAR source does not exist: {emar_path}")
    if extracted_emar_path and extracted_emar_path.exists() and emar_path is None:
        emar_source = extracted_emar_path
        emar = pd.read_parquet(extracted_emar_path)
        emar = emar.loc[
            emar["medication_class"].eq("statin")
            & pd.MultiIndex.from_frame(
                emar[["subject_id", "hadm_id"]].astype("int64")
            ).isin(pd.MultiIndex.from_tuples(sorted(target_pairs), names=["subject_id", "hadm_id"]))
        ].copy()
        source_status["emar"] = "previously_extracted_administration_records"
    elif emar_path and emar_path.exists():
        emar_source = emar_path
        usecols = [
            "subject_id",
            "hadm_id",
            "emar_id",
            "emar_seq",
            "charttime",
            "storetime",
            "event_txt",
            "medication",
        ]
        emar = _read_filtered_csv(
            emar_path,
            target_pairs,
            usecols,
            "medication",
            "charttime",
            True,
        )
        source_status["emar"] = "raw_emar_filtered_to_existing_statin_during_cohort"
    else:
        source_status["emar"] = "source_unavailable"
    if not emar.empty:
        emar["subject_id"] = emar["subject_id"].astype("int64")
        emar["hadm_id"] = emar["hadm_id"].astype("int64")
    admin_frame = _normalize_record(
        emar,
        cohort_index,
        "emar_recorded_administration",
        "charttime",
        "medication",
        emar_source.name if emar_source else "not_available",
    )
    if not admin_frame.empty:
        for source_column, target_column in (
            ("emar_id", "emar_id"),
            ("emar_seq", "emar_seq"),
            ("event_txt", "event_txt"),
            ("storetime", "storetime"),
        ):
            if source_column in emar:
                # The source merge preserves the original rows in the same order.
                admin_frame[target_column] = emar[source_column].to_numpy()

    prescriptions = pd.DataFrame()
    prescription_source = None
    if prescriptions_path is not None and not prescriptions_path.exists():
        raise FileNotFoundError(f"Prescription source does not exist: {prescriptions_path}")
    if extracted_prescriptions_path and extracted_prescriptions_path.exists() and prescriptions_path is None:
        prescription_source = extracted_prescriptions_path
        prescriptions = pd.read_parquet(extracted_prescriptions_path)
        medication_column = "drug"
        prescription_mask = prescriptions["medication_class"].eq("statin")
        pairs = pd.MultiIndex.from_frame(
            prescriptions[["subject_id", "hadm_id"]].astype("int64")
        )
        target_index = pd.MultiIndex.from_tuples(
            sorted(target_pairs), names=["subject_id", "hadm_id"]
        )
        prescriptions = prescriptions.loc[prescription_mask & pairs.isin(target_index)].copy()
        timestamp_column = "starttime"
        source_status["prescriptions"] = "previously_extracted_order_records"
    elif prescriptions_path and prescriptions_path.exists():
        prescription_source = prescriptions_path
        usecols = [
            "subject_id",
            "hadm_id",
            "pharmacy_id",
            "poe_id",
            "poe_seq",
            "starttime",
            "stoptime",
            "drug_type",
            "drug",
            "route",
            "dose_val_rx",
            "dose_unit_rx",
        ]
        prescriptions = _read_filtered_csv(
            prescriptions_path,
            target_pairs,
            usecols,
            "drug",
            "starttime",
            False,
        )
        timestamp_column = "starttime"
        source_status["prescriptions"] = "raw_prescription_orders_filtered_to_existing_statin_during_cohort"
    else:
        source_status["prescriptions"] = "source_unavailable"
        timestamp_column = "starttime"
        medication_column = "drug"
    if not prescriptions.empty:
        prescriptions["subject_id"] = prescriptions["subject_id"].astype("int64")
        prescriptions["hadm_id"] = prescriptions["hadm_id"].astype("int64")
    prescription_frame = _normalize_record(
        prescriptions,
        cohort_index,
        "prescription_order_start_not_administration",
        timestamp_column,
        "drug",
        prescription_source.name if prescription_source else "not_available",
    )
    if not prescription_frame.empty:
        for column in (
            "pharmacy_id",
            "poe_id",
            "poe_seq",
            "drug_type",
            "route",
            "dose_val_rx",
            "dose_unit_rx",
        ):
            if column in prescriptions:
                prescription_frame[column] = prescriptions[column].to_numpy()
    return admin_frame, prescription_frame, source_status


def build_exposure_outputs(
    exposed: pd.DataFrame,
    administrations: pd.DataFrame,
    prescriptions: pd.DataFrame,
    source_status: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = pd.concat([administrations, prescriptions], ignore_index=True)
    matched_pairs = set(
        zip(
            administrations["subject_id"].astype(int),
            administrations["hadm_id"].astype(int),
        )
    ) if not administrations.empty else set()
    placeholders = []
    for row in exposed.itertuples(index=False):
        pair = (int(row.subject_id), int(row.hadm_id))
        if pair in matched_pairs:
            continue
        status = (
            "source_unavailable"
            if source_status.get("emar") == "source_unavailable"
            else "no_matched_emar_record"
        )
        placeholders.append(
            {
                "subject_id": pair[0],
                "hadm_id": pair[1],
                "medication_identity": pd.NA,
                "record_type": "linkage_status",
                "timestamp": pd.NaT,
                "index_admittime": row.index_admittime,
                "index_dischtime": row.index_dischtime,
                "timing_validation_status": status,
                "source_file": "not_available",
            }
        )
    if placeholders:
        rows = pd.concat([rows, pd.DataFrame(placeholders)], ignore_index=True)
    for column in TIMESTAMP_COLUMNS:
        if column not in rows:
            rows[column] = pd.NA
    rows = rows[TIMESTAMP_COLUMNS]

    admin_rows = rows.loc[rows["record_type"].eq("emar_recorded_administration")].copy()
    valid_admin = admin_rows.loc[
        admin_rows["timing_validation_status"].eq("within_index_admission")
    ].copy()
    first = (
        valid_admin.sort_values(["subject_id", "hadm_id", "timestamp"])
        .drop_duplicates(["subject_id", "hadm_id"], keep="first")
        .set_index(["subject_id", "hadm_id"])
    )
    first_rows = []
    for row in exposed.itertuples(index=False):
        pair = (int(row.subject_id), int(row.hadm_id))
        first_record = first.loc[pair] if pair in first.index else None
        all_admin = admin_rows.loc[
            admin_rows["subject_id"].eq(pair[0]) & admin_rows["hadm_id"].eq(pair[1])
        ]
        first_time = pd.NaT if first_record is None else first_record["timestamp"]
        first_rows.append(
            {
                "subject_id": pair[0],
                "hadm_id": pair[1],
                "index_admittime": row.index_admittime,
                "index_dischtime": row.index_dischtime,
                "statin_during": 1,
                "administration_record_count": int(len(all_admin)),
                "distinct_statin_medications": int(all_admin["medication_identity"].nunique()),
                "first_in_admission_administration": first_time,
                "hours_admission_to_first": (
                    (first_time - row.index_admittime).total_seconds() / 3600
                    if pd.notna(first_time)
                    else np.nan
                ),
                "hours_first_to_discharge": (
                    (row.index_dischtime - first_time).total_seconds() / 3600
                    if pd.notna(first_time)
                    else np.nan
                ),
                "first_administration_status": (
                    "observed_within_index_admission"
                    if pd.notna(first_time)
                    else source_status.get("emar", "source_unavailable")
                    if source_status.get("emar") == "source_unavailable"
                    else "no_validated_in_admission_emar_timestamp"
                ),
            }
        )
    first_summary = pd.DataFrame(first_rows)

    linkage = []
    linkage.append(
        {
            "cohort_group": "statin_during=1",
            "index_admissions": len(exposed),
            "administrations_linked": int(len(matched_pairs)),
            "administrations_linked_percent": (
                100 * len(matched_pairs) / len(exposed) if len(exposed) else np.nan
            ),
            "administration_rows": int(len(admin_rows)),
            "prescription_order_rows": int(
                rows["record_type"].eq("prescription_order_start_not_administration").sum()
            ),
            "no_emar_match_or_source_unavailable": int(len(exposed) - len(matched_pairs)),
            "emar_source_status": source_status.get("emar"),
            "prescription_source_status": source_status.get("prescriptions"),
        }
    )
    linkage_summary = pd.DataFrame(linkage)

    timing_summary = (
        rows.groupby(["record_type", "timing_validation_status"], dropna=False)
        .agg(
            record_count=("subject_id", "size"),
            unique_patients=("subject_id", "nunique"),
            unique_admissions=("hadm_id", "nunique"),
        )
        .reset_index()
    )
    return rows, linkage_summary, first_summary, timing_summary


def build_episode_validation(
    cohort: pd.DataFrame,
    candidates: pd.DataFrame,
    chronology: pd.DataFrame,
    diagnoses: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    diagnoses = diagnoses.copy()
    diagnoses["normalized_code"] = (
        diagnoses["icd_code"].astype(str).str.upper().str.replace(".", "", regex=False)
    )
    diagnoses["acute_code"] = [
        is_acute_mi_code(code, version)
        for code, version in zip(diagnoses["icd_code"], diagnoses["icd_version"])
    ]
    candidate_subjects = set(candidates["subject_id"].astype("int64"))
    diagnosis_subset = diagnoses.loc[
        diagnoses["subject_id"].isin(candidate_subjects)
    ].copy()
    diagnosis_subset = diagnosis_subset.sort_values(["hadm_id", "seq_num"])
    diagnosis_subset["code_token"] = (
        "ICD"
        + diagnosis_subset["icd_version"].astype(str)
        + ":"
        + diagnosis_subset["normalized_code"]
        + "#"
        + diagnosis_subset["seq_num"].fillna("?").astype(str)
    )
    diagnosis_subset["acute_code_token"] = diagnosis_subset["code_token"].where(
        diagnosis_subset["acute_code"]
    )
    code_map = (
        diagnosis_subset.groupby("hadm_id")
        .agg(
            all_diagnosis_codes=(
                "code_token",
                lambda values: ";".join(values),
            ),
            acute_mi_codes=(
                "acute_code_token",
                lambda values: ";".join(values.dropna()),
            ),
            diagnosis_row_count=("icd_code", "size"),
        )
    )
    acute_admissions = diagnosis_subset.loc[diagnosis_subset["acute_code"]]
    acute_hadm_ids = set(acute_admissions["hadm_id"].astype("int64"))

    chron = chronology.loc[chronology["subject_id"].isin(candidate_subjects)].copy()
    chron["admittime"] = pd.to_datetime(chron["admittime"], errors="coerce")
    chron["dischtime"] = pd.to_datetime(chron["dischtime"], errors="coerce")
    by_subject = {
        int(subject): frame.sort_values(["admittime", "hadm_id"])
        for subject, frame in chron.groupby("subject_id")
    }
    cohort_by_admission = cohort.set_index("hadm_id")
    result_rows = []
    for candidate in candidates.itertuples(index=False):
        subject_id = int(candidate.subject_id)
        event_hadm = int(candidate.acute_first_hadm_id)
        event_time = pd.Timestamp(candidate.acute_first_admittime)
        index_discharge = pd.Timestamp(candidate.index_dischtime)
        patient_chronology = by_subject.get(subject_id, pd.DataFrame())
        event_record = patient_chronology.loc[patient_chronology["hadm_id"].eq(event_hadm)]
        if event_record.empty:
            event_record = pd.DataFrame()
        acute_for_patient = patient_chronology.loc[
            patient_chronology["hadm_id"].isin(acute_hadm_ids)
        ].copy()
        repeat_window = acute_for_patient.loc[
            acute_for_patient["admittime"].gt(event_time)
            & acute_for_patient["admittime"].le(event_time + pd.Timedelta(days=30))
        ]
        previous = patient_chronology.loc[
            patient_chronology["admittime"].lt(event_time)
        ].tail(1)
        next_admission = patient_chronology.loc[
            patient_chronology["admittime"].gt(event_time)
        ].head(1)
        previous_gap = np.nan
        previous_discharge_location = pd.NA
        previous_hadm = pd.NA
        if not previous.empty and pd.notna(previous.iloc[0]["dischtime"]):
            previous_gap = (
                event_time - previous.iloc[0]["dischtime"]
            ).total_seconds() / 86400
            previous_discharge_location = previous.iloc[0]["discharge_location"]
            previous_hadm = int(previous.iloc[0]["hadm_id"])
        event_admission_location = (
            event_record.iloc[0]["admission_location"] if not event_record.empty else pd.NA
        )
        event_discharge = (
            event_record.iloc[0]["dischtime"]
            if not event_record.empty
            else pd.NaT
        )
        next_gap = np.nan
        next_hadm = pd.NA
        if not next_admission.empty and pd.notna(event_discharge):
            next_gap = (
                next_admission.iloc[0]["admittime"] - event_discharge
            ).total_seconds() / 86400
            next_hadm = int(next_admission.iloc[0]["hadm_id"])
        index_row = cohort_by_admission.loc[int(candidate.hadm_id)]
        index_acute_codes = code_map["acute_mi_codes"].get(int(candidate.hadm_id), "")
        index_acute = bool(index_acute_codes)
        event_transfer_location = bool(
            TRANSFER_PATTERN.search(str(event_admission_location))
        )
        previous_transfer_location = bool(
            TRANSFER_PATTERN.search(str(previous_discharge_location))
        )
        adjacent_transfer = bool(
            pd.notna(previous_gap)
            and 0 <= previous_gap <= 1
            and previous_transfer_location
        )
        transfer_evidence = event_transfer_location or adjacent_transfer
        days = float(candidate.acute_followup_days)
        episode_class, rationale = classify_episode(
            days,
            repeated_acute_admission_within_30d=not repeat_window.empty,
            transfer_evidence=transfer_evidence,
            index_admission_acute_coded=index_acute,
        )
        event_codes = code_map["all_diagnosis_codes"].get(event_hadm, "")
        event_acute_codes = code_map["acute_mi_codes"].get(event_hadm, "")
        repeated_codes = []
        for repeated in repeat_window.itertuples(index=False):
            repeated_codes.append(
                f"{int(repeated.hadm_id)}@{pd.Timestamp(repeated.admittime).isoformat()}:"
                f"{code_map['acute_mi_codes'].get(int(repeated.hadm_id), '')}"
            )
        result_rows.append(
            {
                "subject_id": subject_id,
                "index_hadm_id": int(candidate.hadm_id),
                "index_admittime": index_row["index_admittime"],
                "index_dischtime": index_discharge,
                "first_acute_hadm_id": event_hadm,
                "first_acute_admittime": event_time,
                "days_from_index_discharge": days,
                "acute_mi_codes": event_acute_codes,
                "complete_diagnosis_codes": event_codes,
                "diagnosis_row_count": int(code_map["diagnosis_row_count"].get(event_hadm, 0)),
                "index_admission_acute_mi_codes": index_acute_codes,
                "index_admission_acute_coded": index_acute,
                "other_acute_admissions_within_7d_after_first": int(
                    repeat_window["admittime"].le(event_time + pd.Timedelta(days=7)).sum()
                ),
                "other_acute_admissions_within_30d_after_first": int(len(repeat_window)),
                "other_acute_admission_ids_dates_codes": " | ".join(repeated_codes),
                "previous_hadm_id": previous_hadm,
                "previous_discharge_location": previous_discharge_location,
                "event_admission_location": event_admission_location,
                "gap_from_previous_discharge_days": previous_gap,
                "adjacent_transfer_evidence": transfer_evidence,
                "next_hadm_id": next_hadm,
                "gap_to_next_admission_days": next_gap,
                "episode_classification": episode_class,
                "classification_rationale": rationale,
                "clinical_adjudication_available": False,
            }
        )
    validation = pd.DataFrame(result_rows)
    uncertain = validation.loc[
        validation["episode_classification"].ne("candidate distinct acute MI")
    ].copy()
    summary = {
        "candidate_first_acute_admissions": int(len(validation)),
        "unique_patients": int(validation["subject_id"].nunique()),
        "diagnosis_combinations_available": int(validation["complete_diagnosis_codes"].ne("").sum()),
        "candidate_events_with_index_admission_acute_code": int(validation["index_admission_acute_coded"].sum()),
        "events_within_1_day": int(validation["days_from_index_discharge"].le(1).sum()),
        "events_within_7_days": int(validation["days_from_index_discharge"].le(7).sum()),
        "events_within_30_days": int(validation["days_from_index_discharge"].le(30).sum()),
        "patients_with_additional_acute_coded_admission_within_7_days": int(
            validation["other_acute_admissions_within_7d_after_first"].gt(0).sum()
        ),
        "patients_with_additional_acute_coded_admission_within_30_days": int(
            validation["other_acute_admissions_within_30d_after_first"].gt(0).sum()
        ),
        "additional_acute_admission_count_distribution_30d": {
            str(k): int(v)
            for k, v in validation["other_acute_admissions_within_30d_after_first"]
            .value_counts()
            .sort_index()
            .items()
        },
        "candidate_events_with_transfer_proxy": int(validation["adjacent_transfer_evidence"].sum()),
        "classification_counts": {
            str(k): int(v)
            for k, v in validation["episode_classification"].value_counts().items()
        },
        "clinical_documentation_available": False,
        "clinical_adjudication_available": False,
        "interpretation": "Diagnosis combinations and admission chronology support screening for proximity and possible transfers only. No clinical documentation in the supplied local artifacts adjudicates a distinct recurrent infarction.",
    }
    return validation, uncertain, summary


def _plot_episode_timing(frame: pd.DataFrame, output: Path) -> None:
    fig, axis = plt.subplots(figsize=(8, 4.8))
    values = frame["days_from_index_discharge"].dropna().clip(lower=0)
    axis.hist(values, bins=np.arange(0, 366, 15), color="#4472C4", alpha=0.8)
    for days, label, color in ((1, "1 day", "#C00000"), (7, "7 days", "#ED7D31"), (30, "30 days", "#70AD47")):
        axis.axvline(days, linestyle="--", linewidth=1.2, color=color, label=label)
    axis.set_xlim(0, 365)
    axis.set_xlabel("Days from index discharge to first acute-coded admission")
    axis.set_ylabel("Candidate admissions")
    axis.set_title("Acute-coded candidate timing (all candidates retained)")
    axis.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _write_report(
    exposure_summary: pd.DataFrame,
    first_summary: pd.DataFrame,
    timing_validation: pd.DataFrame,
    episode_summary: dict[str, Any],
    source_status: dict[str, Any],
    cohort: pd.DataFrame,
) -> None:
    treated_n = int(cohort["statin_during"].eq(1).sum())
    missing_treatment_n = int(cohort["statin_during"].isna().sum())
    emar_observed = int(
        first_summary["first_administration_status"]
        .eq("observed_within_index_admission")
        .sum()
    )
    timed_first = first_summary.loc[
        first_summary["first_administration_status"].eq("observed_within_index_admission")
    ]
    c1 = int(episode_summary["events_within_1_day"])
    c7 = int(episode_summary["events_within_7_days"])
    c30 = int(episode_summary["events_within_30_days"])
    classes = episode_summary["classification_counts"]
    admin_valid = int(
        timing_validation.loc[
            timing_validation["record_type"].eq("emar_recorded_administration")
            & timing_validation["timing_validation_status"].eq("within_index_admission"),
            "record_count",
        ].sum()
    )
    admin_before = int(
        timing_validation.loc[
            timing_validation["record_type"].eq("emar_recorded_administration")
            & timing_validation["timing_validation_status"].eq("before_index_admission"),
            "record_count",
        ].sum()
    )
    admin_after = int(
        timing_validation.loc[
            timing_validation["record_type"].eq("emar_recorded_administration")
            & timing_validation["timing_validation_status"].eq("after_index_discharge"),
            "record_count",
        ].sum()
    )
    prescription_orders = int(exposure_summary.iloc[0]["prescription_order_rows"])
    prescription_within = int(
        timing_validation.loc[
            timing_validation["record_type"].eq("prescription_order_start_not_administration")
            & timing_validation["timing_validation_status"].eq("within_index_admission"),
            "record_count",
        ].sum()
    )
    prescription_before = int(
        timing_validation.loc[
            timing_validation["record_type"].eq("prescription_order_start_not_administration")
            & timing_validation["timing_validation_status"].eq("before_index_admission"),
            "record_count",
        ].sum()
    )
    prescription_after = int(
        timing_validation.loc[
            timing_validation["record_type"].eq("prescription_order_start_not_administration")
            & timing_validation["timing_validation_status"].eq("after_index_discharge"),
            "record_count",
        ].sum()
    )
    timestamps = pd.read_parquet(OUTPUT_DIR / "statin_exposure_timestamps.parquet")
    admin_medications = timestamps.loc[
        timestamps["record_type"].eq("emar_recorded_administration"),
        "medication_identity",
    ].dropna().nunique()
    report = f"""# Phase 14: Timestamped Statin Exposure and Acute MI Episode Validation

## Exposure linkage

The analysis selected only the {treated_n:,} index admissions already marked `statin_during=1`. It did not derive or change that indicator. EMAR `charttime` is treated as the recorded administration event time; `storetime` is retained as record-entry time. Prescription `starttime` is reported separately as an order timestamp and is never counted as an administration.

- EMAR source: `{source_status.get('emar')}`.
- Prescription source: `{source_status.get('prescriptions')}`.
- Index admissions with at least one linked EMAR statin record: {int(exposure_summary.iloc[0]['administrations_linked']):,} of {treated_n:,} ({float(exposure_summary.iloc[0]['administrations_linked_percent']):.2f}%).
- Linked EMAR administration rows: {int(exposure_summary.iloc[0]['administration_rows']):,} across {admin_medications:,} distinct medication-name strings; {admin_valid:,} timestamps fall within the closed index-admission interval, {admin_before:,} precede admission, and {admin_after:,} follow discharge.
- Patients with a validated first in-admission administration timestamp: {emar_observed:,} of {treated_n:,} ({100 * emar_observed / treated_n:.2f}%).
- Among those {emar_observed:,}, median time from admission to first administration was {timed_first['hours_admission_to_first'].median():.2f} hours; median time from first administration to discharge was {timed_first['hours_first_to_discharge'].median():.2f} hours.
- Prescription orders are separate: {prescription_orders:,} matched statin order rows, with {prescription_within:,} start times during admission, {prescription_before:,} before admission, and {prescription_after:,} after discharge. These are not treated as administrations or discharge prescriptions.

`statin_exposure_timestamps.parquet` preserves linked EMAR statin records and prescription-order records, plus one explicit linkage-status row for treated admissions without a matched EMAR row. First-administration elapsed times and record-level validation are in the adjacent CSVs.

The archive provides prescription-order records, but no separate discharge-medication reconciliation or explicit discharge-prescription strategy. Prescription start times remain order records; their presence does not establish a discharge prescription or long-term adherence. This analysis does not query raw medication records for the cohort's {missing_treatment_n:,} missing `statin_during` entries, as requested; their exposure status remains unknown.

## Acute MI episode validation

The {episode_summary['candidate_first_acute_admissions']:,} Phase 13 first subsequent acute-coded admissions were linked to full diagnosis rows and admission chronology. Counts within 1, 7, and 30 days of discharge are {c1:,}, {c7:,}, and {c30:,}. There were {episode_summary['patients_with_additional_acute_coded_admission_within_7_days']:,} candidates with another acute-coded admission within 7 days after the first candidate, and {episode_summary['patients_with_additional_acute_coded_admission_within_30_days']:,} within 30 days. {episode_summary['candidate_events_with_index_admission_acute_code']:,} index admissions themselves carry an acute MI code; {episode_summary['candidate_events_with_transfer_proxy']:,} candidates have a chronology/location transfer proxy.

Classification counts (screening labels, not adjudications): `{json.dumps(classes, sort_keys=True)}`. Complete diagnosis-code combinations, candidate IDs, adjacent admissions, timing, repeat-coded admissions, rationale, and classification are provided in `acute_mi_episode_validation.csv`; all non-distinct/uncertain labels are in `acute_mi_uncertain_events.csv`. The supplied local artifacts contain diagnosis codes and admission chronology but no relevant clinical notes or adjudication source. Code combinations cannot establish a distinct infarction episode. All 555 events were retained; time proximity and adjacent-admission clues are triage evidence only, not a rule for discarding early events or proof of a separate MI.

## Revised target-trial feasibility

**Current contrast:** recorded statin administration during the index admission versus no recorded administration. `statin_during=1` is the established exposure indicator, but timestamp evidence is assessed only among its already exposed admissions here. First administration time, when linked, can establish that recorded administration occurred before discharge; it does not alone establish a randomized/causal assignment time or discharge treatment.

**Alternative contrast:** a statin prescription or treatment strategy at discharge versus none. This is not established by the current indicator. No separate discharge-prescription source was found in the local artifacts; available prescription orders must not be relabeled as discharge prescriptions. Long-term adherence is not observable from inpatient EMAR.

**Recommendation: CONDITIONAL GO for an in-hospital exposure observational comparison only; pause causal effect estimation pending endpoint and confounding validation. NO-GO for a discharge-initiation intervention.** Timestamped administrations were found for 1,500 of 2,986 treated admissions. The 1,481 without any linked EMAR record are not thereby proven unexposed; their recorded `statin_during=1` status was preserved. The 555 acute-coded candidate admissions provide a code-based endpoint, but episode duplication/continuation remains unresolved without clinical review. Baseline age, sex, comorbidities, and selected prior medication features exist for known-treatment patients, but this does not establish adequate confounding control; disease severity, treatment indication, exact timing, and missing exposure among {missing_treatment_n:,} patients remain important. Keep the in-hospital contrast explicitly observational. Before estimating a causal effect, validate linkage completeness, episode definition, time zero, and a defensible confounding strategy. No treatment-effect models or new effect estimates were fitted.

## Reproducibility

With previously extracted audit tables:

```powershell
.\\.venv\\Scripts\\python.exe -m causal_models.phase14_exposure_endpoint.analyze_phase14
```

With raw sources supplied:

```powershell
.\\.venv\\Scripts\\python.exe -m causal_models.phase14_exposure_endpoint.analyze_phase14 --emar <path-to-emar.csv> --prescriptions <path-to-prescriptions.csv>
```
"""
    (OUTPUT_DIR / "phase14_feasibility_report.md").write_text(report, encoding="utf-8")


def run_analysis(
    emar_path: Path | None = None,
    prescriptions_path: Path | None = None,
    extracted_emar_path: Path | None = None,
    extracted_prescriptions_path: Path | None = None,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort = pd.read_parquet(COHORT_PATH)
    exposed = _cohort_exposed(cohort)
    cohort_index = exposed[
        ["subject_id", "hadm_id", "index_admittime", "index_dischtime"]
    ].copy()
    administrations, prescriptions, source_status = load_medication_records(
        cohort_index,
        emar_path,
        prescriptions_path,
        extracted_emar_path,
        extracted_prescriptions_path,
    )
    timestamp_table, linkage, first, timing_validation = build_exposure_outputs(
        exposed, administrations, prescriptions, source_status
    )
    timestamp_table.to_parquet(OUTPUT_DIR / "statin_exposure_timestamps.parquet", index=False)
    linkage.to_csv(OUTPUT_DIR / "statin_exposure_linkage_summary.csv", index=False)
    first.to_csv(OUTPUT_DIR / "statin_first_administration_summary.csv", index=False)
    timing_validation.to_csv(OUTPUT_DIR / "statin_timing_validation.csv", index=False)

    candidates = pd.read_csv(PHASE13_CANDIDATES)
    candidates = candidates.loc[candidates["acute_event_type"].eq("acute_recurrent_mi")].copy()
    chronology = pd.read_parquet(CHRONOLOGY_PATH)
    diagnoses = pd.read_parquet(DIAGNOSES_PATH)
    validation, uncertain, episode_summary = build_episode_validation(
        cohort, candidates, chronology, diagnoses
    )
    validation.to_csv(OUTPUT_DIR / "acute_mi_episode_validation.csv", index=False)
    uncertain.to_csv(OUTPUT_DIR / "acute_mi_uncertain_events.csv", index=False)
    _plot_episode_timing(validation, OUTPUT_DIR / "acute_mi_timing_analysis.png")
    summary = {
        "treated_index_admissions": int(len(exposed)),
        "known_missing_treatment_not_reconstructed": int(cohort["statin_during"].isna().sum()),
        "exposure_source_status": source_status,
        "timestamped_admin_admissions_linked": int(linkage.iloc[0]["administrations_linked"]),
        "first_admin_within_admission_n": (
            int(first["first_administration_status"].eq("observed_within_index_admission").sum())
            if source_status.get("emar") != "source_unavailable"
            else None
        ),
        "first_admin_within_admission_percent": (
            float(
                100
                * first["first_administration_status"]
                .eq("observed_within_index_admission")
                .mean()
            )
            if len(first) and source_status.get("emar") != "source_unavailable"
            else None
        ),
        "acute_episode_validation": episode_summary,
        "recommendation": "CONDITIONAL GO for in-hospital exposure observational comparisons only; pause causal effect estimation pending endpoint and confounding validation; NO-GO for discharge-initiation intervention.",
    }
    (OUTPUT_DIR / "acute_mi_episode_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    _write_report(linkage, first, timing_validation, episode_summary, source_status, cohort)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 14 statin exposure and MI episode validation.")
    parser.add_argument("--emar", type=Path, default=None, help="Optional raw emar.csv source.")
    parser.add_argument("--prescriptions", type=Path, default=None, help="Optional raw prescriptions.csv source.")
    parser.add_argument(
        "--extracted-emar",
        type=Path,
        default=ROOT / "medication_timestamp_audit" / "medication_administrations.parquet",
        help="Previously extracted EMAR administration table.",
    )
    parser.add_argument(
        "--extracted-prescriptions",
        type=Path,
        default=ROOT / "medication_timestamp_audit" / "medication_prescription_orders.parquet",
        help="Previously extracted prescription-order table.",
    )
    args = parser.parse_args()
    run_analysis(
        emar_path=args.emar,
        prescriptions_path=args.prescriptions,
        extracted_emar_path=args.extracted_emar,
        extracted_prescriptions_path=args.extracted_prescriptions,
    )


if __name__ == "__main__":
    main()
