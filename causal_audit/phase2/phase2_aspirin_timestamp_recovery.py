from __future__ import annotations

import argparse
from bisect import bisect_left
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_MASTER_DIR = PROJECT_ROOT / "master"
DEFAULT_MIMIC_ROOT = (
    PROJECT_ROOT.parent
    / "Capstone"
    / "Causal_Model_for_ECG_analysis_on_MI"
    / "data"
    / "Compressed"
    / "mimic-iv-2.2"
)
OUTPUT_JSON = PROJECT_ROOT / "phase2_aspirin_timestamp_recovery_results.json"
OUTPUT_REPORT = PROJECT_ROOT / "phase2_aspirin_timestamp_recovery_report.md"
OUTPUT_NOTEBOOK = PROJECT_ROOT / "phase2_aspirin_timestamp_recovery.ipynb"

SPLITS = ("train", "validation", "test")
FROZEN_GLOBS = (
    "phase1_*",
    "phase2_*",
    "phase3_*",
    "phase4_*",
    "phase5_*",
    "phase6_*",
)
ASPIRIN_PATTERN = re.compile(
    r"\baspirin\b|\bacetylsalicylic(?:\s+acid)?\b|\bacetylsalicylate\b"
    r"|\basa\b|\becotrin\b|\bbufferin\b|\bdisprin\b",
    re.IGNORECASE,
)
SOURCE_TABLES = {
    "prescriptions": {
        "path": Path("hosp/prescriptions.csv.gz"),
        "columns": [
            "subject_id",
            "hadm_id",
            "pharmacy_id",
            "poe_id",
            "starttime",
            "stoptime",
            "drug_type",
            "drug",
            "gsn",
            "ndc",
            "route",
        ],
        "match_columns": ["drug"],
    },
    "pharmacy": {
        "path": Path("hosp/pharmacy.csv.gz"),
        "columns": [
            "subject_id",
            "hadm_id",
            "pharmacy_id",
            "poe_id",
            "starttime",
            "stoptime",
            "medication",
            "proc_type",
            "status",
            "entertime",
            "verifiedtime",
        ],
        "match_columns": ["medication"],
    },
    "emar": {
        "path": Path("hosp/emar.csv.gz"),
        "columns": [
            "subject_id",
            "hadm_id",
            "emar_id",
            "emar_seq",
            "poe_id",
            "pharmacy_id",
            "charttime",
            "medication",
            "event_txt",
            "scheduletime",
            "storetime",
        ],
        "match_columns": ["medication"],
    },
    "emar_detail": {
        "path": Path("hosp/emar_detail.csv.gz"),
        "columns": [
            "subject_id",
            "emar_id",
            "emar_seq",
            "administration_type",
            "complete_dose_not_given",
            "dose_due",
            "dose_given",
            "dose_given_unit",
            "product_code",
            "product_description",
            "product_description_other",
            "route",
        ],
        "match_columns": ["product_description", "product_description_other"],
    },
    "poe": {
        "path": Path("hosp/poe.csv.gz"),
        "columns": [
            "poe_id",
            "poe_seq",
            "subject_id",
            "hadm_id",
            "ordertime",
            "order_type",
            "order_subtype",
            "transaction_type",
            "discontinue_of_poe_id",
            "discontinued_by_poe_id",
            "order_status",
        ],
        "match_columns": [],
    },
    "admissions": {
        "path": Path("hosp/admissions.csv.gz"),
        "columns": [
            "subject_id",
            "hadm_id",
            "admittime",
            "dischtime",
        ],
        "match_columns": [],
    },
    "patients": {
        "path": Path("hosp/patients.csv.gz"),
        "columns": ["subject_id"],
        "match_columns": [],
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_file_manifest() -> dict[str, str]:
    paths: set[Path] = set()
    for pattern in FROZEN_GLOBS:
        paths.update(PROJECT_ROOT.glob(pattern))
    paths.update((DEFAULT_MASTER_DIR / f"{split}.parquet") for split in SPLITS)
    manifest = {}
    for path in sorted(paths):
        if path.is_file():
            manifest[str(path.relative_to(PROJECT_ROOT))] = sha256(path)
    return manifest


def table_schema(path: Path, requested_columns: Iterable[str]) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required source table not found: {path}")
    header = list(pd.read_csv(
        path,
        compression="gzip",
        nrows=0,
        encoding="utf-8",
    ).columns)
    missing = sorted(set(requested_columns) - set(header))
    if missing:
        raise ValueError(f"{path.name} is missing required fields: {missing}")
    return {
        "available": True,
        "compressed_bytes": path.stat().st_size,
        "columns_in_source": header,
        "columns_read": list(requested_columns),
    }


def scan_medication_table(
    path: Path,
    columns: list[str],
    match_columns: list[str],
    chunksize: int = 250_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    schema = table_schema(path, columns)
    matches: list[pd.DataFrame] = []
    rows_scanned = 0
    if not match_columns:
        raise ValueError("At least one text field is required to identify medication rows.")
    for chunk in pd.read_csv(
        path,
        compression="gzip",
        usecols=columns,
        dtype="string",
        keep_default_na=False,
        chunksize=chunksize,
        encoding="utf-8",
        low_memory=False,
    ):
        rows_scanned += len(chunk)
        mask = pd.Series(False, index=chunk.index)
        for column in match_columns:
            mask |= chunk[column].str.contains(ASPIRIN_PATTERN, na=False)
        if mask.any():
            matches.append(chunk.loc[mask].copy())
    result = (
        pd.concat(matches, ignore_index=True)
        if matches
        else pd.DataFrame(columns=columns)
    )
    schema["rows_scanned"] = rows_scanned
    schema["aspirin_match_rows"] = len(result)
    schema["matching_rule"] = ASPIRIN_PATTERN.pattern
    return result, schema


def scan_emar(
    path: Path,
    columns: list[str],
    detail_keys: set[tuple[str, str, str]],
    chunksize: int = 250_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    schema = table_schema(path, columns)
    matches: list[pd.DataFrame] = []
    rows_scanned = 0
    for chunk in pd.read_csv(
        path,
        compression="gzip",
        usecols=columns,
        dtype="string",
        keep_default_na=False,
        chunksize=chunksize,
        encoding="utf-8",
        low_memory=False,
    ):
        rows_scanned += len(chunk)
        medication_match = chunk["medication"].str.contains(
            ASPIRIN_PATTERN, na=False
        )
        chunk_keys = zip(
            clean_key(chunk["subject_id"]).fillna("").astype(str),
            clean_key(chunk["emar_id"]).fillna("").astype(str),
            clean_key(chunk["emar_seq"]).fillna("").astype(str),
        )
        detail_match = pd.Series(
            [key in detail_keys for key in chunk_keys],
            index=chunk.index,
        )
        selected = medication_match | detail_match
        if selected.any():
            matches.append(chunk.loc[selected].copy())
    result = (
        pd.concat(matches, ignore_index=True)
        if matches
        else pd.DataFrame(columns=columns)
    )
    schema["rows_scanned"] = rows_scanned
    schema["aspirin_or_detail_link_match_rows"] = len(result)
    schema["matching_rule"] = ASPIRIN_PATTERN.pattern
    schema["detail_link_key"] = ["subject_id", "emar_id", "emar_seq"]
    return result, schema


def scan_by_ids(
    path: Path,
    columns: list[str],
    key_column: str,
    keys: set[str],
    chunksize: int = 250_000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    schema = table_schema(path, columns)
    matches: list[pd.DataFrame] = []
    rows_scanned = 0
    for chunk in pd.read_csv(
        path,
        compression="gzip",
        usecols=columns,
        dtype="string",
        keep_default_na=False,
        chunksize=chunksize,
        encoding="utf-8",
        low_memory=False,
    ):
        rows_scanned += len(chunk)
        selected = chunk[key_column].isin(keys)
        if selected.any():
            matches.append(chunk.loc[selected].copy())
    result = (
        pd.concat(matches, ignore_index=True)
        if matches
        else pd.DataFrame(columns=columns)
    )
    schema["rows_scanned"] = rows_scanned
    schema["linked_rows"] = len(result)
    schema["link_key"] = key_column
    return result, schema


def clean_key(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().replace("", pd.NA)


def parse_wall_time(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip().replace("", pd.NA)
    has_offset = values.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True, na=False)
    if has_offset.any():
        raise ValueError(
            "Explicit timezone offsets found in a timestamp source. "
            "Do not compare with naive timestamps without resolving timezone semantics."
        )
    return pd.to_datetime(values, errors="coerce")


def resolution_summary(values: pd.Series) -> dict[str, int]:
    text = values.astype("string").str.strip()
    valid = text.notna() & text.ne("")
    seconds = text.str.contains(r"\d{2}:\d{2}:\d{2}", regex=True, na=False)
    fractional = text.str.contains(r"\d{2}:\d{2}:\d{2}\.\d+", regex=True, na=False)
    return {
        "nonempty_timestamp_strings": int(valid.sum()),
        "second_or_finer_format": int((valid & seconds).sum()),
        "fractional_second_format": int((valid & fractional).sum()),
        "minute_only_or_coarser_format": int((valid & ~seconds).sum()),
    }


def load_master(master_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    frames = []
    split_counts = {}
    for split in SPLITS:
        path = master_dir / f"{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Required master split is missing: {path}")
        schema = pq.ParquetFile(path).schema_arrow.names
        required = {"SubjectID", "hadm_id", "study_id", "ecg_time", "aspirin_before"}
        if not required.issubset(schema):
            raise ValueError(
                f"{path.name} does not contain required audit columns: "
                f"{sorted(required - set(schema))}"
            )
        frame = pd.read_parquet(
            path,
            columns=["SubjectID", "hadm_id", "study_id", "ecg_time", "aspirin_before"],
        )
        split_counts[split] = len(frame)
        frames.append(frame)
    master = pd.concat(frames, ignore_index=True)
    master["SubjectID"] = clean_key(master["SubjectID"])
    master["hadm_id"] = clean_key(master["hadm_id"])
    master["study_id"] = clean_key(master["study_id"])
    master["ecg_time_raw"] = master["ecg_time"].astype("string")
    master["ecg_time_parsed"] = parse_wall_time(master["ecg_time_raw"])
    master["aspirin_before"] = pd.to_numeric(
        master["aspirin_before"], errors="coerce"
    )
    if master["hadm_id"].isna().any() or master["SubjectID"].isna().any():
        raise ValueError("Master data contain missing linkage identifiers.")
    mapping_counts = master.groupby("hadm_id")["SubjectID"].nunique()
    if (mapping_counts > 1).any():
        raise ValueError("At least one hadm_id maps to multiple SubjectID values.")
    per_admission_flag_counts = master.groupby("hadm_id")["aspirin_before"].nunique(
        dropna=False
    )
    if (per_admission_flag_counts > 1).any():
        inconsistent = int((per_admission_flag_counts > 1).sum())
    else:
        inconsistent = 0
    first_rows = master.drop_duplicates("hadm_id").set_index("hadm_id")
    admission_frame = first_rows[["SubjectID", "aspirin_before"]].copy()
    ecg_stats = master.groupby("hadm_id").agg(
        ecg_count=("study_id", "nunique"),
        valid_ecg_count=("ecg_time_parsed", "count"),
        ecg_min=("ecg_time_parsed", "min"),
        ecg_max=("ecg_time_parsed", "max"),
    )
    admission_frame = admission_frame.join(ecg_stats)
    admission_frame["valid_ecg_time"] = admission_frame["valid_ecg_count"] > 0
    return admission_frame, {
        "split_rows": split_counts,
        "combined_ecg_rows": len(master),
        "unique_admissions": int(admission_frame.shape[0]),
        "unique_patients": int(master["SubjectID"].nunique()),
        "unique_study_id": bool(master["study_id"].is_unique),
        "aspirin_before_admissions_exposed": int(
            (admission_frame["aspirin_before"] == 1).sum()
        ),
        "aspirin_before_admissions_unexposed": int(
            (admission_frame["aspirin_before"] == 0).sum()
        ),
        "aspirin_before_admissions_missing": int(
            admission_frame["aspirin_before"].isna().sum()
        ),
        "admissions_with_inconsistent_aspirin_before_rows": inconsistent,
        "admissions_with_any_valid_ecg_time": int(
            admission_frame["valid_ecg_time"].sum()
        ),
        "ecg_rows_with_valid_time": int(master["ecg_time_parsed"].notna().sum()),
        "ecg_rows_with_missing_or_invalid_time": int(
            master["ecg_time_parsed"].isna().sum()
        ),
        "ecg_time_format_resolution": resolution_summary(master["ecg_time_raw"]),
        "admissions": admission_frame,
    }


def parse_detail_ids(frame: pd.DataFrame) -> pd.DataFrame:
    for column in ("subject_id", "emar_id", "emar_seq"):
        frame[column] = clean_key(frame[column])
    return frame


def compare_event_rows_to_ecgs(
    admission_frame: pd.DataFrame,
    events: pd.DataFrame,
    timestamp_column: str,
    event_group_columns: tuple[str, ...] = ("hadm_id",),
) -> dict[str, Any]:
    valid_events = events.loc[events[timestamp_column].notna()].copy()
    per_admission: dict[str, list[pd.Timestamp]] = defaultdict(list)
    for row in valid_events[["hadm_id", timestamp_column]].itertuples(index=False):
        per_admission[str(row[0])].append(row[1])

    category_counts = Counter()
    compareable = set()
    multi_record_admissions = set()
    conflicting = set()

    for hadm_id, event_times in per_admission.items():
        if hadm_id not in admission_frame.index:
            continue
        row = admission_frame.loc[hadm_id]
        if not bool(row["valid_ecg_time"]):
            continue
        compareable.add(hadm_id)
        if len(event_times) > 1:
            multi_record_admissions.add(hadm_id)
        earliest_ecg = row["ecg_min"]
        latest_ecg = row["ecg_max"]
        earliest_event = min(event_times)
        latest_event = max(event_times)
        if latest_event < earliest_ecg:
            classification = "clearly_before_all_ecgs"
        elif earliest_event > latest_ecg:
            classification = "clearly_after_all_ecgs"
        else:
            classification = "temporally_ambiguous_or_mixed"
        category_counts[classification] += 1
        before_some_ecg = min(event_times) < latest_ecg
        after_some_ecg = max(event_times) > earliest_ecg
        if before_some_ecg and after_some_ecg:
            conflicting.add(hadm_id)

    return {
        "admissions_with_recoverable_timestamp": len(per_admission),
        "admissions_with_timestamp_and_valid_ecg_comparable": len(compareable),
        "admissions_with_timestamp_but_no_valid_ecg_time": len(per_admission)
        - len(compareable)
        - sum(
            hadm_id not in admission_frame.index
            for hadm_id in per_admission
        ),
        "clearly_before_all_ecgs": category_counts["clearly_before_all_ecgs"],
        "clearly_after_all_ecgs": category_counts["clearly_after_all_ecgs"],
        "temporally_ambiguous_or_mixed": category_counts[
            "temporally_ambiguous_or_mixed"
        ],
        "admissions_with_multiple_timestamped_records": len(multi_record_admissions),
        "admissions_with_records_on_both_sides_of_ecg_window": len(conflicting),
        "classification_rule": (
            "No index ECG was selected. For each admission, compare every valid medication "
            "timestamp with the full observed ECG-time interval [earliest ECG, latest ECG]. "
            "Clearly before/after means every relevant event is strictly outside that interval. "
            "Any overlap, equality, or mixed ordering is temporally ambiguous. No arbitrary "
            "hour-based 'around' window was introduced."
        ),
    }


def records_by_admission(
    frame: pd.DataFrame,
    admission_lookup: pd.DataFrame,
    admission_column: str = "hadm_id",
    subject_column: str = "subject_id",
) -> pd.DataFrame:
    result = frame.copy()
    for column in (admission_column, subject_column):
        if column in result:
            result[column] = clean_key(result[column])
    if admission_column in result:
        result = result.loc[result[admission_column].isin(admission_lookup.index)].copy()
    if subject_column in result:
        result = result.loc[
            result[subject_column].isin(set(admission_lookup["SubjectID"]))
        ].copy()
    return result


def exact_master_pair_filter(
    frame: pd.DataFrame,
    admission_lookup: pd.DataFrame,
) -> pd.DataFrame:
    result = frame.copy()
    result["hadm_id"] = clean_key(result["hadm_id"])
    result["subject_id"] = clean_key(result["subject_id"])
    exact_pairs = set(
        zip(
            admission_lookup.index.astype(str),
            admission_lookup["SubjectID"].astype(str),
        )
    )
    mask = pd.Series(
        [
            (str(hadm), str(subject)) in exact_pairs
            for hadm, subject in zip(result["hadm_id"], result["subject_id"])
        ],
        index=result.index,
    )
    return result.loc[mask].copy()


def summarize_medication_records(
    name: str,
    frame: pd.DataFrame,
    schema: dict[str, Any],
    admission_frame: pd.DataFrame,
    candidate_flag_value: int = 1,
) -> dict[str, Any]:
    frame = records_by_admission(frame, admission_frame)
    if "hadm_id" not in frame:
        return {"source_rows_for_master_patients": 0}
    frame["hadm_id"] = clean_key(frame["hadm_id"])
    frame = frame.loc[frame["hadm_id"].isin(admission_frame.index)].copy()
    admission_counts = frame.groupby("hadm_id").size()
    cohort = admission_frame.loc[admission_frame["aspirin_before"] == candidate_flag_value]
    return {
        "source_rows_for_master_admissions": int(len(frame)),
        "master_admissions_with_one_or_more_matching_rows": int(
            frame["hadm_id"].nunique()
        ),
        "matching_source_rows_in_aspirin_before_positive_admissions": int(
            frame["hadm_id"].isin(cohort.index).sum()
        ),
        "aspirin_before_positive_admissions_with_matching_rows": int(
            frame.loc[frame["hadm_id"].isin(cohort.index), "hadm_id"].nunique()
        ),
        "aspirin_before_positive_admissions_without_matching_rows": int(
            len(cohort)
            - frame.loc[frame["hadm_id"].isin(cohort.index), "hadm_id"].nunique()
        ),
        "admissions_with_multiple_matching_rows": int(
            (admission_counts > 1).sum()
        ),
        "admissions_with_multiple_matching_rows_within_aspirin_before_positive": int(
            admission_counts.reindex(cohort.index, fill_value=0).gt(1).sum()
        ),
        "rows_with_valid_starttime": int(
            frame.get("starttime_parsed", pd.Series(dtype="datetime64[ns]")).notna().sum()
        ),
        "timestamp_semantics": schema.get("timestamp_semantics"),
    }


def build_audit(mimic_root: Path, master_dir: Path) -> dict[str, Any]:
    missing_paths = [
        str(mimic_root / info["path"])
        for info in SOURCE_TABLES.values()
        if not (mimic_root / info["path"]).is_file()
    ]
    if missing_paths:
        raise FileNotFoundError(
            "The available MIMIC-IV source directory is incomplete: "
            + ", ".join(missing_paths)
        )

    protected_before = frozen_file_manifest()
    admission_frame, master_summary = load_master(master_dir)
    all_admission_ids = set(admission_frame.index)
    master_subject_ids = set(admission_frame["SubjectID"])

    admissions_spec = SOURCE_TABLES["admissions"]
    admissions_rows, admissions_schema = scan_by_ids(
        mimic_root / admissions_spec["path"],
        admissions_spec["columns"],
        "hadm_id",
        all_admission_ids,
    )
    admissions_rows["hadm_id"] = clean_key(admissions_rows["hadm_id"])
    admissions_rows["subject_id"] = clean_key(admissions_rows["subject_id"])
    admissions_rows["admittime_parsed"] = parse_wall_time(admissions_rows["admittime"])
    admissions_rows["dischtime_parsed"] = parse_wall_time(admissions_rows["dischtime"])
    source_admission_links = admissions_rows.drop_duplicates("hadm_id").set_index(
        "hadm_id"
    )["subject_id"]
    master_subject_lookup = admission_frame["SubjectID"]
    shared_admissions = master_subject_lookup.index.intersection(
        source_admission_links.index
    )
    bad_subject_links = int(
        (
            master_subject_lookup.loc[shared_admissions]
            != source_admission_links.loc[shared_admissions]
        ).sum()
    )
    linked_admissions = len(shared_admissions)
    admission_frame = admission_frame.join(
        admissions_rows.drop_duplicates("hadm_id")
        .set_index("hadm_id")[["admittime_parsed", "dischtime_parsed"]],
        how="left",
    )

    data: dict[str, pd.DataFrame] = {}
    source_schemas: dict[str, Any] = {"admissions": admissions_schema}
    for table in ("prescriptions", "pharmacy", "emar_detail"):
        spec = SOURCE_TABLES[table]
        path = mimic_root / spec["path"]
        print(f"Scanning {table} for aspirin-related records...", flush=True)
        frame, schema = scan_medication_table(
            path,
            spec["columns"],
            spec["match_columns"],
        )
        data[table] = frame
        source_schemas[table] = schema

    detail = parse_detail_ids(data["emar_detail"])
    detail = detail.loc[detail["subject_id"].isin(master_subject_ids)].copy()
    detail_aspirin_keys = set(
        zip(
            detail["subject_id"].astype(str),
            detail["emar_id"].astype(str),
            detail["emar_seq"].astype(str),
        )
    )
    emar_spec = SOURCE_TABLES["emar"]
    print("Scanning eMAR and matching aspirin product details...", flush=True)
    emar, emar_schema = scan_emar(
        mimic_root / emar_spec["path"],
        emar_spec["columns"],
        detail_aspirin_keys,
    )
    source_schemas["emar"] = emar_schema

    prescriptions_all = data["prescriptions"].copy()
    prescriptions_all["hadm_id"] = clean_key(prescriptions_all["hadm_id"])
    prescriptions_all["subject_id"] = clean_key(prescriptions_all["subject_id"])
    prescriptions_all = prescriptions_all.loc[
        prescriptions_all["subject_id"].isin(master_subject_ids)
    ].copy()
    pharmacy = exact_master_pair_filter(data["pharmacy"], admission_frame)
    emar = exact_master_pair_filter(emar, admission_frame)
    prescriptions = exact_master_pair_filter(
        prescriptions_all.loc[
            prescriptions_all["hadm_id"].isin(all_admission_ids)
        ],
        admission_frame,
    )

    emar["emar_id"] = clean_key(emar["emar_id"])
    emar["emar_seq"] = clean_key(emar["emar_seq"])
    detail_join_keys = set(
        zip(
            emar["subject_id"].dropna().astype(str),
            emar["emar_id"].dropna().astype(str),
            emar["emar_seq"].dropna().astype(str),
        )
    )
    detail["_join_key"] = list(
        zip(
            detail["subject_id"].astype(str),
            detail["emar_id"].astype(str),
            detail["emar_seq"].astype(str),
        )
    )
    detail = detail.loc[detail["_join_key"].isin(detail_join_keys)].copy()
    emar["_join_key"] = list(
        zip(
            emar["subject_id"].astype(str),
            emar["emar_id"].astype(str),
            emar["emar_seq"].astype(str),
        )
    )
    emar_detail_counts = detail.groupby("_join_key").size()
    emar["matched_detail_rows"] = emar["_join_key"].map(emar_detail_counts).fillna(0)

    # Prescription order IDs connect the medication name to the POE order timestamp.
    poe_keys = set(clean_key(prescriptions_all["poe_id"]).dropna().astype(str))
    poe_spec = SOURCE_TABLES["poe"]
    print("Linking aspirin prescription rows to POE order timestamps...", flush=True)
    poe_rows, poe_schema = scan_by_ids(
        mimic_root / poe_spec["path"],
        poe_spec["columns"],
        "poe_id",
        poe_keys,
    )
    poe_rows["poe_id"] = clean_key(poe_rows["poe_id"])
    prescriptions_all["poe_id"] = clean_key(prescriptions_all["poe_id"])
    prescriptions_all = prescriptions_all.merge(
        poe_rows[["poe_id", "ordertime", "order_status", "transaction_type"]],
        on="poe_id",
        how="left",
        suffixes=("", "_poe"),
    )
    prescriptions = exact_master_pair_filter(
        prescriptions_all.loc[
            prescriptions_all["hadm_id"].isin(all_admission_ids)
        ],
        admission_frame,
    )
    patients_spec = SOURCE_TABLES["patients"]
    patient_rows, patient_schema = scan_by_ids(
        mimic_root / patients_spec["path"],
        patients_spec["columns"],
        "subject_id",
        master_subject_ids,
    )

    for field in ("starttime", "stoptime", "ordertime"):
        if field in prescriptions_all:
            prescriptions_all[f"{field}_parsed"] = parse_wall_time(
                prescriptions_all[field]
            )
    for frame, fields in [
        (prescriptions, ["starttime", "stoptime", "ordertime"]),
        (pharmacy, ["starttime", "stoptime", "entertime", "verifiedtime"]),
        (emar, ["charttime", "scheduletime", "storetime"]),
    ]:
        for field in fields:
            if field in frame.columns:
                frame[f"{field}_parsed"] = parse_wall_time(frame[field])

    emar_event_status_counts = (
        emar["event_txt"].fillna("").astype(str).str.strip().value_counts(dropna=False)
    )
    administered_mask = (
        emar["event_txt"].fillna("").astype(str).str.strip().str.casefold()
        == "administered"
    )
    emar_admin = emar.loc[administered_mask].copy()
    emar_admin["charttime_parsed"] = parse_wall_time(emar_admin["charttime"])
    emar_admin_valid = emar_admin.loc[
        emar_admin["charttime_parsed"].notna()
    ].copy()

    presc_time = prescriptions["starttime_parsed"]
    pharmacy_start = pharmacy["starttime_parsed"]
    emar_charttime = emar_admin["charttime_parsed"]
    prescription_starttime_res = resolution_summary(prescriptions["starttime"])
    pharmacy_time_res = resolution_summary(pharmacy["starttime"])
    emar_charttime_res = resolution_summary(emar["charttime"])
    emar_sched_res = resolution_summary(emar["scheduletime"])

    admin_timing_all = compare_event_rows_to_ecgs(
        admission_frame,
        emar_admin_valid,
        "charttime_parsed",
    )
    candidate_admissions = set(
        admission_frame.index[admission_frame["aspirin_before"] == 1]
    )
    candidate_frame = admission_frame.loc[sorted(candidate_admissions)]
    admin_timing_candidate = compare_event_rows_to_ecgs(
        candidate_frame,
        emar_admin_valid.loc[
            emar_admin_valid["hadm_id"].isin(candidate_admissions)
        ],
        "charttime_parsed",
    )
    order_timing_all = compare_event_rows_to_ecgs(
        admission_frame,
        prescriptions.assign(
            starttime_parsed=prescriptions["starttime_parsed"]
        ).loc[prescriptions["starttime_parsed"].notna()],
        "starttime_parsed",
    )
    order_timing_candidate = compare_event_rows_to_ecgs(
        candidate_frame,
        prescriptions.loc[
            prescriptions["hadm_id"].isin(candidate_admissions)
            & prescriptions["starttime_parsed"].notna()
        ],
        "starttime_parsed",
    )
    ordertime_timing_all = compare_event_rows_to_ecgs(
        admission_frame,
        prescriptions.loc[prescriptions["ordertime_parsed"].notna()],
        "ordertime_parsed",
    )
    ordertime_timing_candidate = compare_event_rows_to_ecgs(
        candidate_frame,
        prescriptions.loc[
            prescriptions["hadm_id"].isin(candidate_admissions)
            & prescriptions["ordertime_parsed"].notna()
        ],
        "ordertime_parsed",
    )
    sorted_order_times_by_subject = {
        str(subject_id): sorted(group["starttime_parsed"].dropna().tolist())
        for subject_id, group in prescriptions_all.groupby("subject_id")
    }
    candidate_prior_order_counts: dict[str, int] = {}
    candidate_latest_prior_orders: list[dict[str, Any]] = []
    all_admission_prior_order_count = 0
    for hadm_id, row in admission_frame.iterrows():
        admit_time = row["admittime_parsed"]
        if pd.isna(admit_time):
            continue
        subject_id = str(row["SubjectID"])
        order_times = sorted_order_times_by_subject.get(subject_id, [])
        prior_count = bisect_left(order_times, admit_time)
        all_admission_prior_order_count += prior_count
        if row["aspirin_before"] == 1:
            candidate_prior_order_counts[str(hadm_id)] = prior_count
            if prior_count:
                candidate_latest_prior_orders.append(
                    {
                        "hadm_id": str(hadm_id),
                        "starttime_parsed": order_times[prior_count - 1],
                    }
                )
    historical_candidate_orders = pd.DataFrame(candidate_latest_prior_orders)
    if not historical_candidate_orders.empty:
        historical_candidate_timing = compare_event_rows_to_ecgs(
            candidate_frame,
            historical_candidate_orders,
            "starttime_parsed",
        )
    else:
        historical_candidate_timing = {
            "admissions_with_recoverable_timestamp": 0,
            "admissions_with_timestamp_and_valid_ecg_comparable": 0,
            "admissions_with_timestamp_but_no_valid_ecg_time": 0,
            "clearly_before_all_ecgs": 0,
            "clearly_after_all_ecgs": 0,
            "temporally_ambiguous_or_mixed": 0,
            "admissions_with_multiple_timestamped_records": 0,
            "admissions_with_records_on_both_sides_of_ecg_window": 0,
            "classification_rule": "No prior aspirin order records linked to positive candidate admissions.",
        }
    ordertime_timing_all = compare_event_rows_to_ecgs(
        admission_frame,
        prescriptions.loc[prescriptions["ordertime_parsed"].notna()],
        "ordertime_parsed",
    )
    sorted_order_times_by_subject = {
        str(subject_id): sorted(group["starttime_parsed"].dropna().tolist())
        for subject_id, group in prescriptions_all.groupby("subject_id")
    }
    historical_prior_order_counts: dict[str, int] = {}
    latest_prior_orders: list[dict[str, Any]] = []
    for hadm_id, row in admission_frame.iterrows():
        admit_time = row["admittime_parsed"]
        if pd.isna(admit_time):
            continue
        subject_id = str(row["SubjectID"])
        ordered_times = sorted_order_times_by_subject.get(subject_id, [])
        prior_count = bisect_left(ordered_times, admit_time)
        historical_prior_order_counts[str(hadm_id)] = prior_count
        if prior_count and row["aspirin_before"] == 1:
            latest_prior_orders.append(
                {
                    "hadm_id": str(hadm_id),
                    "starttime_parsed": ordered_times[prior_count - 1],
                }
            )
    historical_candidate_orders = pd.DataFrame(latest_prior_orders)
    if not historical_candidate_orders.empty:
        historical_candidate_timing = compare_event_rows_to_ecgs(
            admission_frame.loc[admission_frame["aspirin_before"] == 1],
            historical_candidate_orders,
            "starttime_parsed",
        )
    else:
        historical_candidate_timing = {
            "admissions_with_recoverable_timestamp": 0,
            "admissions_with_timestamp_and_valid_ecg_comparable": 0,
            "clearly_before_all_ecgs": 0,
            "clearly_after_all_ecgs": 0,
            "temporally_ambiguous_or_mixed": 0,
            "admissions_with_multiple_timestamped_records": 0,
            "admissions_with_records_on_both_sides_of_ecg_window": 0,
        }

    def actual_status_counts(frame: pd.DataFrame) -> dict[str, int]:
        if frame.empty:
            return {"matched_emar_rows": 0}
        return {
            "matched_emar_rows": int(len(frame)),
            "rows_with_event_txt_administered": int(
                frame["event_txt"].fillna("").astype(str).str.strip().str.casefold().eq("administered").sum()
            ),
            "rows_with_valid_charttime": int(
                frame["charttime_parsed"].notna().sum()
            ),
            "administered_rows_with_valid_charttime": int(
                (
                    frame["event_txt"].fillna("").astype(str).str.strip().str.casefold().eq("administered")
                    & frame["charttime_parsed"].notna()
                ).sum()
            ),
            "unique_admissions_with_emar_row": int(frame["hadm_id"].nunique()),
            "unique_admissions_with_administered_event": int(
                frame.loc[
                    frame["event_txt"].fillna("").astype(str).str.strip().str.casefold().eq("administered"),
                    "hadm_id",
                ].nunique()
            ),
            "unique_admissions_with_administered_valid_time": int(
                frame.loc[
                    frame["event_txt"].fillna("").astype(str).str.strip().str.casefold().eq("administered")
                    & frame["charttime_parsed"].notna(),
                    "hadm_id",
                ].nunique()
            ),
            "unique_admissions_with_multiple_administered_rows": int(
                (
                    frame.loc[
                        frame["event_txt"].fillna("").astype(str).str.strip().str.casefold().eq("administered")
                    ]
                    .groupby("hadm_id")
                    .size()
                    .gt(1)
                ).sum()
            ),
            "unique_eMAR_event_keys": int(
                frame[["subject_id", "emar_id", "emar_seq"]].drop_duplicates().shape[0]
            ),
            "eMAR_rows_with_duplicate_event_key": int(
                len(frame)
                - frame[["subject_id", "emar_id", "emar_seq"]].drop_duplicates().shape[0]
            ),
        }

    all_admin_counts = actual_status_counts(emar)
    candidate_admin_counts = actual_status_counts(
        emar.loc[emar["hadm_id"].isin(candidate_admissions)]
    )
    admin_events_per_hadm = (
        emar_admin_valid.groupby("hadm_id").size()
        if not emar_admin_valid.empty
        else pd.Series(dtype="int64")
    )
    candidate_timing_recovered = int(
        admin_events_per_hadm.reindex(candidate_frame.index, fill_value=0).gt(0).sum()
    )
    candidate_no_timing = int(len(candidate_frame) - candidate_timing_recovered)

    medication_name_counts: dict[str, Any] = {}
    for table_name, frame, columns in [
        ("prescriptions", prescriptions, ["drug"]),
        ("pharmacy", pharmacy, ["medication"]),
        ("emar", emar, ["medication"]),
        (
            "emar_detail",
            detail,
            ["product_description", "product_description_other"],
        ),
    ]:
        counter: Counter[str] = Counter()
        for column in columns:
            if column in frame.columns:
                counter.update(
                    frame[column].fillna("").astype(str).str.strip().value_counts().to_dict()
                )
        medication_name_counts[table_name] = {
            "distinct_matching_descriptions": len(counter),
            "matched_description_rows": int(sum(counter.values())),
        }

    source_schemas["poe"] = poe_schema
    source_schemas["admissions"] = admissions_schema
    source_schemas["patients"] = patient_schema
    for name, semantic in {
        "prescriptions": "Medication prescription/order record; starttime/stoptime describe the prescription interval, not proof of administration.",
        "pharmacy": "Pharmacy order/processing record; starttime, stoptime, entertime, and verifiedtime do not independently establish a dose was administered.",
        "emar": "Medication administration record; charttime is the recorded event time and event_txt carries administration status. Only rows with event_txt exactly 'Administered' are counted as administration evidence here.",
        "emar_detail": "Detail linked to eMAR by subject_id + emar_id + emar_seq; product/dose fields corroborate the medication/event but do not independently provide a separate administration timestamp.",
        "poe": "Provider order-entry record; ordertime is order-entry time, not administration time.",
        "admissions": "Admission linkage and admission-time anchor.",
        "patients": "Patient identifier dictionary; subject_id matches the master SubjectID namespace.",
    }.items():
        source_schemas[name]["timestamp_semantics"] = semantic

    eMAR_detail_matching_count = int(len(detail))
    eMAR_detail_linked_events = int(detail["_join_key"].nunique()) if not detail.empty else 0
    eMAR_aspirin_med_admin_details = int(
        detail["complete_dose_not_given"].fillna("").astype(str).str.casefold().isin(
            {"false", "0", "no"}
        ).sum()
    ) if not detail.empty else 0

    protected_after = frozen_file_manifest()
    integrity_preserved = protected_before == protected_after
    if not integrity_preserved:
        raise RuntimeError(
            "Integrity check failed: one or more master/Phase 1–6 files changed during the audit."
        )

    candidate_comparable = admin_timing_candidate[
        "admissions_with_timestamp_and_valid_ecg_comparable"
    ]
    candidate_multiple = int(
        admin_events_per_hadm.reindex(candidate_frame.index, fill_value=0).gt(1).sum()
    )
    result = {
        "audit_name": "Phase 2 aspirin timestamp recovery",
        "status": "COMPLETED — focused source-data investigation only",
        "scope": {
            "treatment_flag_under_investigation": "aspirin_before",
            "no_final_index_ecg_selected": True,
            "no_master_data_written": True,
            "no_frozen_phase_outputs_written": True,
            "no_causal_discovery_performed": True,
            "interpretation_limit": (
                "This audit distinguishes prior prescriptions/orders from documented in-hospital "
                "administration events. It does not treat aspirin_before as proof of a dose before ECG."
            ),
        },
        "paths": {
            "project_root": str(PROJECT_ROOT),
            "mimic_iv_root": str(mimic_root),
            "master_dir": str(master_dir),
        },
        "master_data": {
            key: value
            for key, value in master_summary.items()
            if key != "admissions"
        },
        "cohort_definition": {
            "aspirin_candidate_positive": (
                "Unique master hadm_id values with aspirin_before == 1."
            ),
            "candidate_positive_admissions": len(candidate_admissions),
            "all_master_admissions_assessed_for_linkage": len(admission_frame),
            "all_master_admissions_with_valid_ecg_timestamp": int(
                admission_frame["valid_ecg_time"].sum()
            ),
        },
        "source_tables": source_schemas,
        "source_linkage": {
            "admission_key": "hadm_id",
            "patient_key": "MIMIC subject_id == master SubjectID",
            "eMAR_to_detail_keys": ["subject_id", "emar_id", "emar_seq"],
            "prescription_to_poe_key": "poe_id",
            "master_admissions_found_in_mimic_admissions": linked_admissions,
            "master_admissions_not_found_in_mimic_admissions": (
                len(admission_frame) - linked_admissions
            ),
            "subject_id_mismatches_for_linked_hadm_id": bad_subject_links,
            "aspirin_prescription_rows_linked_to_poe": int(
                prescriptions["ordertime"].notna().sum()
            ),
            "aspirin_prescription_rows_without_poe_ordertime": int(
                prescriptions["ordertime"].isna().sum()
            ),
            "aspirin_eMAR_rows_with_linked_detail": int(
                emar["matched_detail_rows"].gt(0).sum()
            ),
            "aspirin_eMAR_rows_without_linked_detail": int(
                emar["matched_detail_rows"].eq(0).sum()
            ),
            "linked_aspirin_detail_rows": eMAR_detail_matching_count,
            "linked_eMAR_events_with_aspirin_product_detail": eMAR_detail_linked_events,
            "detail_rows_with_complete_dose_not_given_false_or_zero": eMAR_aspirin_med_admin_details,
            "medication_description_summary": medication_name_counts,
            "subject_level_prior_prescription_search": {
                "aspirin_prescription_rows_for_master_patients": int(
                    len(prescriptions_all)
                ),
                "rows_with_valid_starttime": int(
                    prescriptions_all["starttime_parsed"].notna().sum()
                ),
                "prior_prescription_row_occurrences_across_master_admissions": int(
                    all_admission_prior_order_count
                ),
                "aspirin_before_positive_admissions_with_any_prior_prescription": int(
                    sum(count > 0 for count in candidate_prior_order_counts.values())
                ),
                "aspirin_before_positive_admissions_without_any_prior_prescription": int(
                    len(candidate_admissions)
                    - sum(count > 0 for count in candidate_prior_order_counts.values())
                ),
                "latest_prior_prescription_start_relative_to_ecg_interval": historical_candidate_timing,
                "interpretation": (
                    "Subject-level prior prescription search mirrors the pattern of the tracked statin feature code. "
                    "It establishes a historical order start only, not an active outpatient medication or administration."
                ),
            },
        },
        "order_evidence": {
            "prescription_order_records": summarize_medication_records(
                "prescriptions", prescriptions, source_schemas["prescriptions"], admission_frame
            ),
            "pharmacy_records": summarize_medication_records(
                "pharmacy", pharmacy, source_schemas["pharmacy"], admission_frame
            ),
            "eMAR_status_values_in_matching_rows": {
                str(key) if str(key) else "<blank>": int(value)
                for key, value in emar_event_status_counts.items()
            },
            "prescription_starttime_string_precision": prescription_starttime_res,
            "pharmacy_starttime_string_precision": pharmacy_time_res,
            "prescription_starttime_valid_count": int(presc_time.notna().sum()),
            "pharmacy_starttime_valid_count": int(pharmacy_start.notna().sum()),
            "poe_ordertime_valid_count": int(
                parse_wall_time(prescriptions["ordertime"]).notna().sum()
            ),
            "aspirin_order_start_relative_to_all_ecgs": {
                key: value
                for key, value in order_timing_all.items()
            },
            "aspirin_order_start_relative_to_candidate_admission_ecgs": order_timing_candidate,
            "poe_order_entry_time_relative_to_all_ecgs": ordertime_timing_all,
            "poe_order_entry_time_relative_to_candidate_admission_ecgs": ordertime_timing_candidate,
            "latest_prior_order_time_relative_to_candidate_admission_ecgs": historical_candidate_timing,
            "semantics": (
                "Order/start/verification timestamps are reported as order-process evidence. They are not counted as administration."
            ),
        },
        "administration_evidence": {
            "eMAR_aspirin_rows_in_all_master_admissions": all_admin_counts,
            "eMAR_aspirin_rows_in_aspirin_before_positive_admissions": candidate_admin_counts,
            "eMAR_charttime_string_precision": emar_charttime_res,
            "eMAR_scheduletime_string_precision": emar_sched_res,
            "actual_administration_rule": (
                "Only matching eMAR rows with event_txt exactly equal to 'Administered' "
                "and a valid charttime are treated as recoverable documented administration timing."
            ),
            "all_admissions_timing_relative_to_all_ecgs": {
                key: value
                for key, value in admin_timing_all.items()
                if key != "admission_classifications"
            },
            "aspirin_before_positive_admissions_timing_relative_to_all_ecgs": {
                key: value
                for key, value in admin_timing_candidate.items()
                if key != "admission_classifications"
            },
            "candidate_positive_admissions_with_recoverable_admin_timing": candidate_timing_recovered,
            "candidate_positive_admissions_without_recoverable_admin_timing": candidate_no_timing,
            "candidate_positive_admissions_with_timing_comparable_to_ecg": candidate_comparable,
            "candidate_positive_admissions_with_multiple_admin_records": candidate_multiple,
            "candidate_positive_admissions_with_multiple_or_conflicting_records": int(
                admin_timing_candidate["admissions_with_records_on_both_sides_of_ecg_window"]
            ),
        },
        "aspirin_before_provenance": {
            "status": "UNRESOLVED",
            "documented_master_definition": (
                "Phase F documentation describes aspirin_before as use before admission / pre-admission use."
            ),
            "documented_source_file": (
                "clinical/features_treatments.csv joined on hadm_id; that file is not present in the current project workspace."
            ),
            "local_feature_generation_code": (
                "No tracked local script constructing aspirin_before was found. The available upstream Phase E script "
                "constructs a statin_use feature from prescriptions by matching drug names and p.starttime < target admittime, "
                "joining on subject_id without requiring a current-admission hadm_id or proving active use/dose administration. "
                "This is analogous prior-order logic only; it is not evidence that aspirin_before uses the same code."
            ),
            "flag_interpretation": (
                "aspirin_before == 1 is not verified as an administration before ECG, active pre-admission use, or even a specific order time."
            ),
        },
        "decision_record": {},
        "integrity_validation": {
            "protected_file_count": len(protected_before),
            "master_parquet_and_phase1_to_phase6_hashes_unchanged": integrity_preserved,
            "protected_file_sha256_before": protected_before,
            "protected_file_sha256_after": protected_after,
            "master_parquet_writes": 0,
            "phase1_to_phase6_writes": 0,
            "source_tables_modified": False,
        },
        "stop_condition": (
            "STOP after timestamp recovery. No final index ECG selection, ECG feature eligibility audit, "
            "treatment selection, matrix construction, Phase 7 discovery, DAG, ATE, or CATE."
        ),
    }
    result["decision_record"] = decide(result)
    return result


def decide(result: dict[str, Any]) -> dict[str, Any]:
    admin = result["administration_evidence"]
    cohort_count = result["cohort_definition"]["candidate_positive_admissions"]
    recoverable = admin["candidate_positive_admissions_with_recoverable_admin_timing"]
    order_records = result["order_evidence"]["prescription_order_records"][
        "aspirin_before_positive_admissions_with_matching_rows"
    ]
    if recoverable > 0:
        option = "OPTION 1 — Reliable administration-event timing recovered for a subset of admissions."
        status = "PARTIALLY VERIFIED"
        next_step = (
            "Do not select an index ECG yet. A subsequent decision may define an aspirin-specific eligibility "
            "rule only for admissions with a qualifying documented eMAR administration and a valid ECG-time "
            "comparison; admissions without such evidence remain timing-unknown. First decide whether this "
            "partial eMAR coverage and the distinction from aspirin_before answer the intended treatment question."
        )
    elif order_records > 0:
        option = "OPTION 2 — Only order timing recovered; administration timing remains unresolved."
        status = "PARTIALLY VERIFIED"
        next_step = (
            "Do not equate order time with administration and do not select an order-based baseline ECG rule "
            "without an explicit decision that order assignment is the intended treatment. If not, use Rule A "
            "only as an ASSUMED/FALLBACK first-ECG representation, not verified pre-treatment timing."
        )
    else:
        option = "OPTION 3 — No usable aspirin treatment timing can be recovered for the candidate cohort."
        status = "UNRESOLVED"
        next_step = (
            "Use Rule A (first ECG in admission) only as an ASSUMED/FALLBACK candidate for the next decision; "
            "it is not verified pre-treatment. Do not use Rule B or Rule C as a general treatment/control baseline."
        )
    return {
        "option": option,
        "evidence_status": status,
        "reliable_aspirin_before_flag_time_zero": "UNRESOLVED",
        "why": (
            "The eMAR and/or order records provide evidence only for their own documented in-hospital event/order "
            "semantics. They do not establish that the master aspirin_before flag is a dose before a selected ECG."
        ),
        "exact_index_ecg_implication": next_step,
        "candidate_admission_count": cohort_count,
        "candidate_admissions_with_admin_time": recoverable,
        "candidate_admissions_without_admin_time": cohort_count - recoverable,
        "next_step_is_a_decision_not_an_automatic_phase_transition": True,
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "\\|").replace("\n", " ").replace("\r", "")
                for value in row
            )
            + " |"
        )
    return "\n".join(lines)


def report_markdown(result: dict[str, Any]) -> str:
    cohort = result["cohort_definition"]
    master = result["master_data"]
    links = result["source_linkage"]
    order = result["order_evidence"]
    administration = result["administration_evidence"]
    candidate = administration[
        "aspirin_before_positive_admissions_timing_relative_to_all_ecgs"
    ]
    decision = result["decision_record"]
    sources = []
    for table in (
        "prescriptions",
        "pharmacy",
        "emar",
        "emar_detail",
        "poe",
        "admissions",
        "patients",
    ):
        item = result["source_tables"][table]
        sources.append(
            [
                table,
                ", ".join(item["columns_in_source"]),
                item.get("rows_scanned", "schema only"),
                item.get("aspirin_match_rows", item.get("linked_rows", "n/a")),
                item["timestamp_semantics"],
            ]
        )
    count_rows = [
        ["Master admissions in the aspirin timing audit", master["unique_admissions"]],
        ["aspirin_before == 1 admissions", cohort["candidate_positive_admissions"]],
        ["aspirin_before == 0 admissions", master["aspirin_before_admissions_unexposed"]],
        ["aspirin_before missing admissions", master["aspirin_before_admissions_missing"]],
        ["Admissions with >=1 valid ECG timestamp", master["admissions_with_any_valid_ecg_time"]],
        [
            "Positive candidate admissions with eMAR Administered + valid charttime",
            administration["candidate_positive_admissions_with_recoverable_admin_timing"],
        ],
        [
            "Positive candidate admissions without eMAR administration timing",
            administration["candidate_positive_admissions_without_recoverable_admin_timing"],
        ],
        [
            "Positive candidate admissions with timing comparable to ECG interval",
            administration["candidate_positive_admissions_with_timing_comparable_to_ecg"],
        ],
        ["Clearly before every ECG in admission", candidate["clearly_before_all_ecgs"]],
        ["Clearly after every ECG in admission", candidate["clearly_after_all_ecgs"]],
        ["Ambiguous/mixed relative to ECG interval", candidate["temporally_ambiguous_or_mixed"]],
        [
            "Positive candidate admissions with multiple eMAR administration records",
            administration["candidate_positive_admissions_with_multiple_admin_records"],
        ],
        [
            "Positive candidate admissions with records on both sides of ECG interval",
            administration["candidate_positive_admissions_with_multiple_or_conflicting_records"],
        ],
        [
            "Positive candidate admissions with an aspirin prescription row in their own hadm_id",
            order["prescription_order_records"]["aspirin_before_positive_admissions_with_matching_rows"],
        ],
    ]
    integrity = result["integrity_validation"]
    return "\n".join(
        [
            "# Phase 2 Addendum — Aspirin Timestamp Recovery",
            "",
            "## Scope and stopping rule",
            "",
            "This is a new, focused source-data investigation. It does not change frozen Phase 1–6 conclusions or the Phase 2 finding that the master parquet contains no exact treatment assignment timestamps. It does not select a final index ECG, assess feature eligibility, construct a discovery matrix, or run causal discovery.",
            "",
            "## Source tables inspected",
            "",
            markdown_table(
                ["Table", "Relevant source fields", "Rows scanned/linked", "Aspirin rows/linked rows", "Timestamp semantics"],
                sources,
            ),
            "",
            "Available source files were found under the local MIMIC-IV 2.2 `hosp` directory. The master parquet itself contains only `ecg_time`, `index_mi_time`, `time_diff_hours`, and binary aspirin flags among time/treatment-related fields; it contains no prescription, eMAR, POE, or administration timestamps.",
            "",
            "## Aspirin identification and linkage",
            "",
            f"Aspirin candidates were identified in medication/product descriptions using case-insensitive text matching for aspirin, acetylsalicylic/acetylsalicylate, ASA, Ecotrin, Bufferin, and Disprin. This is a reproducible name-based candidate rule, not a medication-code-complete drug ontology. Prescription/pharmacy/eMAR rows were linked to the master by both `hadm_id` and MIMIC `subject_id == SubjectID`. eMAR details were linked by `(subject_id, emar_id, emar_seq)`; prescriptions were linked to POE order records by `poe_id`.",
            "",
            f"Of {links['master_admissions_found_in_mimic_admissions']:,} master admissions found in MIMIC admissions, there were {links['subject_id_mismatches_for_linked_hadm_id']:,} patient-ID mismatches on shared `hadm_id` values. {links['aspirin_eMAR_rows_with_linked_detail']:,} aspirin-matching eMAR rows had matching detail records; {links['aspirin_eMAR_rows_without_linked_detail']:,} did not.",
            "",
            "## `aspirin_before` provenance",
            "",
            f"**{result['aspirin_before_provenance']['status']}** — {result['aspirin_before_provenance']['documented_master_definition']} {result['aspirin_before_provenance']['documented_source_file']} The corresponding feature CSV and aspirin-specific construction script are not present in the inspected workspace. The upstream Phase E script contains only a statin prior-prescription construction; that code is not evidence for aspirin-specific derivation.",
            "",
            "The available statin code joins prescriptions by patient and tests `p.starttime < target admittime`, without restricting to the target `hadm_id` or verifying an active medication or administration. This makes a historical order a plausible *documented* analogue, not a verified definition of `aspirin_before`. Therefore `aspirin_before == 1` is not interpreted as a dose before ECG.",
            "",
            "## Timing evidence and semantics",
            "",
            "The most defensible actual administration source is `hosp/emar.csv.gz`, joined to `hosp/emar_detail.csv.gz`. The analysis treats `charttime` as the eMAR recorded event time and only `event_txt == 'Administered'` plus valid `charttime` as documented administration timing. This is not an independently verified ingestion time; eMAR charting is the source evidence. `emar_detail` product/dose fields are corroboration, not separate timestamps.",
            "",
            "The `prescriptions` table supplies `starttime`/`stoptime` on prescription records; these describe prescription timing, not proof of administration. POE `ordertime` is order-entry time; pharmacy `entertime`/`verifiedtime`/start/stop describe pharmacy-order processing. These are retained as order evidence and are not relabeled as administration.",
            "",
            "The source timestamps and ECG timestamps are compared as recorded wall-clock times. No UTC conversion or time-zone assertion is made because the source fields have no explicit offset evidence. Exact/equal and overlapping/mixed orderings are marked ambiguous; no arbitrary before/after hour window is introduced.",
            "",
            "## Linkage and coverage",
            "",
            markdown_table(["Coverage measure", "Count"], count_rows),
            "",
            f"Candidate cohort definition: unique admissions with `aspirin_before == 1` ({cohort['candidate_positive_admissions']:,}). The source coverage for eMAR administration timing is {administration['candidate_positive_admissions_with_recoverable_admin_timing']:,}/{cohort['candidate_positive_admissions']:,}; admissions without a qualifying recorded eMAR administration are unknown for actual aspirin administration, not assumed unexposed. All-master-admission timing summaries and source-row counts are retained in the JSON.",
            "",
            "For ECG comparisons, the final index ECG was deliberately not selected. Each admission was represented by its full observed ECG timestamp interval from earliest to latest. Medication timing was classified as clearly before only when every qualifying event was strictly before every ECG; clearly after only when every event was strictly after every ECG; otherwise it is ambiguous/mixed. This is a coverage audit, not an index-ECG selection rule.",
            "",
            "## Decision Record",
            "",
            f"**{decision['option']}**",
            "",
            f"- Evidence status: **{decision['evidence_status']}**.",
            f"- Recovered timing does **not** establish that `aspirin_before == 1` denotes administration before a selected ECG: **{decision['reliable_aspirin_before_flag_time_zero']}**.",
            f"- Index-ECG implication: {decision['exact_index_ecg_implication']}",
            "",
            "## Validation and integrity",
            "",
            f"- Master split counts were read and reconciled to {master['combined_ecg_rows']:,} rows; the audit reads only five master columns and never writes to any master file.",
            f"- Protected master/Phase 1–6 files hashed before and after: {integrity['protected_file_count']}; all SHA-256 hashes unchanged: **{integrity['master_parquet_and_phase1_to_phase6_hashes_unchanged']}**.",
            f"- Master parquet writes: {integrity['master_parquet_writes']}; Phase 1–6 writes: {integrity['phase1_to_phase6_writes']}; MIMIC source-table writes: none.",
            "- No causal discovery, final index ECG selection, feature-eligibility analysis, treatment selection, matrix construction, DAG construction, or effect estimation was performed.",
            "",
            "## 1. RESULT",
            "",
            f"Reliable aspirin treatment timing was **{('partially recovered' if decision['evidence_status'] == 'PARTIALLY VERIFIED' else 'not recovered')}** for the target master flag. The eMAR can provide documented in-hospital administration-event timing for the reported subset; this does not verify the provenance or administration time represented by `aspirin_before`.",
            "",
            "## 2. EVIDENCE",
            "",
            "The local MIMIC-IV 2.2 source includes `prescriptions`, `pharmacy`, `poe`, `emar`, `emar_detail`, `admissions`, and `patients`. `emar.charttime` with an `Administered` status, corroborated where possible by linked detail, is the strongest available administration evidence. Prescription start/stop and POE ordertime are order evidence only. Linkage uses `hadm_id` plus `subject_id == SubjectID`, with eMAR detail linked by its event key. The coverage table above reports the candidate and full-admission counts; no unlinked/ambiguous admission is silently dropped.",
            "",
            "## 3. CAUSAL INTERPRETATION",
            "",
            "Administration-event time is recoverable only for admissions with a qualifying eMAR record and a valid timestamp; it is not universal for the `aspirin_before` cohort. The eMAR establishes a recorded in-hospital event, not necessarily the time of ingestion or the actual origin of the binary pre-admission flag. Prescription/POE timing alone would not establish administration time zero. Therefore the `aspirin_before` exposure's causal time zero relative to ECG remains **UNRESOLVED**.",
            "",
            "## 4. INDEX-ECG IMPLICATION",
            "",
            f"{decision['exact_index_ecg_implication']}",
            "",
            "No final index ECG has been selected. Rule A, if later used, remains **ASSUMED/FALLBACK**, not verified pre-treatment. Rules B and C are not used as general treatment/control baseline rules.",
            "",
            "## 5. REMAINING BLOCKERS",
            "",
            "- Aspirin-specific source construction for `aspirin_before` and the referenced `clinical/features_treatments.csv` are unavailable in the inspected workspace.",
            "- eMAR administration timestamps are available only for a subset; lack of a matching administered row is not proof of non-use.",
            "- eMAR records are administration documentation; ingestion/actual exposure is not independently verified.",
            "- No final treatment-specific index ECG has been selected; this audit compared medication events to the full admission ECG interval only.",
            "- Source timezone semantics remain unverified; comparisons use recorded wall-clock timestamps without UTC conversion.",
            "",
            "## 6. NEXT ACTION",
            "",
            "Decide whether the treatment of interest is pre-admission aspirin use (which remains UNRESOLVED from these inpatient records) or documented in-hospital administered aspirin (for which subset timing is PARTIALLY VERIFIED); do not choose an index ECG until that exposure interpretation is approved.",
            "",
        ]
    )


def notebook_document() -> dict[str, Any]:
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "# Phase 2 Addendum — Aspirin Timestamp Recovery\n",
                    "\n",
                    "Focused source-table audit only. Does not select a final index ECG or perform causal discovery. Run from the capstone2 project root with the local MIMIC-IV directory available.\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Run the reproducible audit\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "from phase2_aspirin_timestamp_recovery import build_audit, write_outputs\n",
                    "from pathlib import Path\n",
                    "result = build_audit(Path(r'C:\\Users\\anura\\OneDrive\\Desktop\\Capstone\\Causal_Model_for_ECG_analysis_on_MI\\data\\Compressed\\mimic-iv-2.2'), Path('master'))\n",
                    "write_outputs(result)\n",
                    "result['decision_record']\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["## Coverage summary\n"],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    "result['cohort_definition'], result['administration_evidence']\n",
                ],
            },
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    "The detailed report and JSON are generated beside this notebook. The audit stops at timestamp evidence and does not select an index ECG.\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_outputs(result: dict[str, Any]) -> None:
    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    OUTPUT_REPORT.write_text(report_markdown(result), encoding="utf-8")
    OUTPUT_NOTEBOOK.write_text(
        json.dumps(notebook_document(), indent=1, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mimic-root", type=Path, default=DEFAULT_MIMIC_ROOT)
    parser.add_argument("--master-dir", type=Path, default=DEFAULT_MASTER_DIR)
    args = parser.parse_args()
    results = build_audit(args.mimic_root, args.master_dir)
    write_outputs(results)
    print(
        json.dumps(
            {
                "decision": results["decision_record"]["option"],
                "candidate_admissions": results["cohort_definition"][
                    "candidate_positive_admissions"
                ],
                "candidate_with_admin_timing": results[
                    "administration_evidence"
                ]["candidate_positive_admissions_with_recoverable_admin_timing"],
                "candidate_without_admin_timing": results[
                    "administration_evidence"
                ]["candidate_positive_admissions_without_recoverable_admin_timing"],
                "timing_comparison": results["administration_evidence"][
                    "aspirin_before_positive_admissions_timing_relative_to_all_ecgs"
                ],
                "integrity": results["integrity_validation"][
                    "master_parquet_and_phase1_to_phase6_hashes_unchanged"
                ],
                "outputs": [
                    str(OUTPUT_JSON),
                    str(OUTPUT_REPORT),
                    str(OUTPUT_NOTEBOOK),
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
