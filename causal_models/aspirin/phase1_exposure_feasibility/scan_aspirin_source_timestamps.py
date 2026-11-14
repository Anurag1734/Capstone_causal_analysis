from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
COHORT_PATH = Path("causal_models/data/statin_recurrent_mi_cohort.parquet")
RECOVERY_SCRIPT = Path("causal_audit/phase2/phase2_aspirin_timestamp_recovery.py")
OUTPUT_NAME = "ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json"


def _load_existing_recovery_utility(root: Path) -> Any:
    utility_path = root / RECOVERY_SCRIPT
    spec = importlib.util.spec_from_file_location("aspirin_timestamp_recovery", utility_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load existing aspirin audit utility: {utility_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _first_administration_status(
    administrations: pd.DataFrame, index_admissions: pd.DataFrame, utility: Any
) -> tuple[pd.DataFrame, dict[str, int]]:
    if administrations.empty:
        first = pd.DataFrame(columns=["subject_id", "hadm_id", "charttime_parsed"])
    else:
        valid = administrations.loc[
            administrations["charttime_parsed"].notna()
        ].copy()
        first = (
            valid.sort_values(["hadm_id", "charttime_parsed"], kind="mergesort")
            .drop_duplicates("hadm_id", keep="first")
            [["subject_id", "hadm_id", "charttime_parsed"]]
        )
    index = index_admissions[
        ["subject_id", "hadm_id", "admittime", "dischtime"]
    ].copy()
    for column in ("subject_id", "hadm_id"):
        index[column] = utility.clean_key(index[column])
        first[column] = utility.clean_key(first[column])
    index["admittime"] = utility.parse_wall_time(index["admittime"])
    index["dischtime"] = utility.parse_wall_time(index["dischtime"])
    linked = first.merge(
        index,
        on=["subject_id", "hadm_id"],
        how="left",
        validate="one_to_one",
    )
    if linked[["admittime", "dischtime"]].isna().any().any():
        raise ValueError("A timestamped aspirin admission lacks a valid index interval.")
    linked["first_administration_timing"] = "within_index_admission"
    linked.loc[
        linked["charttime_parsed"].lt(linked["admittime"]),
        "first_administration_timing",
    ] = "before_index_admission"
    linked.loc[
        linked["charttime_parsed"].gt(linked["dischtime"]),
        "first_administration_timing",
    ] = "after_index_discharge"
    categories = {
        category: int(count)
        for category, count in linked["first_administration_timing"]
        .value_counts()
        .items()
    }
    return linked, categories


def scan_source_timestamps(
    root: Path, mimic_root: Path, output_path: Path
) -> dict[str, Any]:
    utility = _load_existing_recovery_utility(root)
    cohort_path = root / COHORT_PATH
    if not cohort_path.is_file():
        raise FileNotFoundError(f"Existing prior-MI cohort is missing: {cohort_path}")
    index = pd.read_parquet(
        cohort_path,
        columns=["subject_id", "hadm_id", "admittime", "dischtime", "aspirin_before"],
    )
    if index.duplicated(["subject_id", "hadm_id"]).any():
        raise ValueError("Existing prior-MI cohort contains duplicate index admissions.")
    index["subject_id"] = utility.clean_key(index["subject_id"])
    index["hadm_id"] = utility.clean_key(index["hadm_id"])
    if index[["subject_id", "hadm_id"]].isna().any().any():
        raise ValueError("Existing prior-MI cohort contains missing patient/admission identifiers.")
    index_lookup = (
        index[["subject_id", "hadm_id"]]
        .rename(columns={"subject_id": "SubjectID"})
        .set_index("hadm_id")
    )
    patient_ids = set(index["subject_id"].astype(str))

    detail_spec = utility.SOURCE_TABLES["emar_detail"]
    detail, detail_schema = utility.scan_medication_table(
        mimic_root / detail_spec["path"],
        detail_spec["columns"],
        detail_spec["match_columns"],
    )
    detail = utility.parse_detail_ids(detail)
    detail = detail.loc[detail["subject_id"].isin(patient_ids)].copy()
    detail_keys = set(
        zip(
            detail["subject_id"].astype(str),
            detail["emar_id"].astype(str),
            detail["emar_seq"].astype(str),
        )
    )

    emar_spec = utility.SOURCE_TABLES["emar"]
    emar, emar_schema = utility.scan_emar(
        mimic_root / emar_spec["path"],
        emar_spec["columns"],
        detail_keys,
    )
    emar = utility.exact_master_pair_filter(emar, index_lookup)
    emar["charttime_parsed"] = utility.parse_wall_time(emar["charttime"])
    event_status = emar["event_txt"].fillna("").astype(str).str.strip().str.casefold()
    administered_mask = event_status.eq("administered")
    administered = emar.loc[administered_mask].copy()
    valid_administered = administered.loc[
        administered["charttime_parsed"].notna()
    ].copy()
    first, first_timing = _first_administration_status(
        valid_administered, index, utility
    )

    all_times = emar.loc[emar["charttime_parsed"].notna()].copy()
    all_times["event_timing"] = "within_index_admission"
    index_intervals = index[["subject_id", "hadm_id", "admittime", "dischtime"]].copy()
    index_intervals["admittime"] = utility.parse_wall_time(index_intervals["admittime"])
    index_intervals["dischtime"] = utility.parse_wall_time(index_intervals["dischtime"])
    for column in ("subject_id", "hadm_id"):
        index_intervals[column] = utility.clean_key(index_intervals[column])
        all_times[column] = utility.clean_key(all_times[column])
    all_times = all_times.merge(
        index_intervals,
        on=["subject_id", "hadm_id"],
        how="left",
        validate="many_to_one",
    )
    if all_times[["admittime", "dischtime"]].isna().any().any():
        raise ValueError("A linked aspirin eMAR row lacks a valid index interval.")
    all_times.loc[
        all_times["charttime_parsed"].lt(all_times["admittime"]), "event_timing"
    ] = "before_index_admission"
    all_times.loc[
        all_times["charttime_parsed"].gt(all_times["dischtime"]), "event_timing"
    ] = "after_index_discharge"
    event_timing_counts = {
        category: int(count)
        for category, count in all_times["event_timing"].value_counts().items()
    }

    positive_ids = set(
        index.loc[pd.to_numeric(index["aspirin_before"], errors="coerce").eq(1), "hadm_id"]
    )
    first_positive = first.loc[first["hadm_id"].isin(positive_ids)]
    positive_first_timing = {
        category: int(count)
        for category, count in first_positive["first_administration_timing"]
        .value_counts()
        .items()
    }
    event_keys = emar[["subject_id", "emar_id", "emar_seq"]].drop_duplicates()
    summary = {
        "source_root": str(mimic_root),
        "source_tables": {
            "emar_detail": {
                "rows_scanned": detail_schema["rows_scanned"],
                "aspirin_match_rows_scanned": detail_schema["aspirin_match_rows"],
            },
            "emar": {
                "rows_scanned": emar_schema["rows_scanned"],
                "aspirin_or_detail_match_rows_scanned": emar_schema[
                    "aspirin_or_detail_link_match_rows"
                ],
            },
        },
        "eligible_prior_mi_index_admissions": int(len(index)),
        "index_admissions_with_aspirin_emar_record": int(emar["hadm_id"].nunique()),
        "index_admissions_with_administered_event": int(
            administered["hadm_id"].nunique()
        ),
        "index_admissions_with_valid_administered_charttime": int(
            valid_administered["hadm_id"].nunique()
        ),
        "aspirin_emar_rows_linked_to_index_admissions": int(len(emar)),
        "aspirin_emar_rows_with_valid_charttime": int(
            emar["charttime_parsed"].notna().sum()
        ),
        "administered_rows": int(len(administered)),
        "administered_rows_with_valid_charttime": int(len(valid_administered)),
        "administered_rows_with_invalid_or_missing_charttime": int(
            administered["charttime_parsed"].isna().sum()
        ),
        "event_status_counts": {
            str(status) if status else "<blank>": int(count)
            for status, count in event_status.value_counts(dropna=False).items()
        },
        "duplicate_emar_event_key_rows": int(len(emar) - len(event_keys)),
        "first_administration_timing_by_index_admission": first_timing,
        "index_admissions_with_first_admin_time": int(len(first)),
        "index_admissions_without_first_admin_time": int(len(index) - len(first)),
        "first_administration_timing_among_aspirin_before_positive_admissions": (
            positive_first_timing
        ),
        "first_admin_within_index_admission_n": first_timing.get(
            "within_index_admission", 0
        ),
        "emar_event_row_timing": event_timing_counts,
        "interpretation": (
            "Only eMAR rows with event_txt exactly 'Administered' and a valid charttime "
            "count as documented administration evidence. First-event categories are "
            "relative to the existing index admission interval; they do not establish "
            "outpatient use, adherence, or randomized treatment assignment."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Link existing MIMIC-IV aspirin eMAR records to the prior-MI index cohort."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mimic-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    output = args.output or (
        Path(__file__).resolve().parent / OUTPUT_NAME
    )
    result = scan_source_timestamps(
        args.root.resolve(), args.mimic_root.resolve(), output.resolve()
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"output: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
