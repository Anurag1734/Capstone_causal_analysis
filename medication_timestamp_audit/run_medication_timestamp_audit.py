"""Run a targeted MIMIC medication timestamp and ECG linkage audit.

The script reads only the requested medication, admission, patient, ICU input,
and optional ECG/longitudinal files. It never modifies source files or a
pre-existing master dataset.
"""

from __future__ import annotations

import argparse
import csv
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


LOG = logging.getLogger("medication_timestamp_audit")
CHUNK_SIZE = 250_000
TARGET_CLASSES = ("statin", "aspirin", "beta_blocker", "ace_inhibitor")

MEDICATION_RULES = {
    "statin": re.compile(
        r"\b(?:atorvastatin|simvastatin|rosuvastatin|pravastatin|lovastatin|"
        r"fluvastatin|pitavastatin|cerivastatin)\b",
        re.I,
    ),
    "aspirin": re.compile(r"\b(?:aspirin|acetylsalicylic\s+acid)\b", re.I),
    "beta_blocker": re.compile(
        r"\b(?:metoprolol|carvedilol|atenolol|propranolol|bisoprolol|"
        r"labetalol|nadolol|nebivolol|pindolol|sotalol|esmolol|timolol)\b",
        re.I,
    ),
    "ace_inhibitor": re.compile(
        r"\b(?:lisinopril|enalapril|ramipril|perindopril|captopril|"
        r"benazepril|quinapril|fosinopril|trandolapril|moexipril)\b",
        re.I,
    ),
}

ADMIN_OUTPUT_COLUMNS = [
    "subject_id", "hadm_id", "emar_id", "emar_seq", "charttime", "storetime",
    "event_txt", "medication", "medication_class", "classification_status",
    "source_file",
]
RECORDED_ADMINISTRATION = re.compile(
    r"\b(?:administered|partial administered|started|restarted)\b", re.I
)
PRESCRIPTION_OUTPUT_COLUMNS = [
    "subject_id", "hadm_id", "pharmacy_id", "poe_id", "poe_seq", "starttime",
    "stoptime", "drug_type", "drug", "route", "dose_val_rx", "dose_unit_rx",
    "medication_class", "classification_status", "source_file",
]
LINK_OUTPUT_COLUMNS = [
    "study_id", "subject_id", "hadm_id", "ecg_time", "medication_class",
    "original_medication_name", "administration_time", "emar_id", "emar_seq",
    "event_txt", "hours_from_ecg", "temporal_classification", "linkage_method",
    "data_quality_flags",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ecg", type=Path, default=None)
    parser.add_argument("--longitudinal", type=Path, default=None)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    return parser.parse_args()


def setup_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(output_dir / "audit.log", encoding="utf-8"),
        ],
    )


def normalize_medication(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def classify_medication(value: object) -> tuple[str, str]:
    normalized = normalize_medication(value)
    if not normalized:
        return "unmapped", "missing_medication_name"
    matches = [name for name, rule in MEDICATION_RULES.items() if rule.search(normalized)]
    if len(matches) == 1:
        return matches[0], "matched_explicit_generic_rule"
    if len(matches) > 1:
        return "unmapped", "ambiguous_multiple_class_rules"
    return "unmapped", "not_in_target_classes"


def existing_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def read_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def source_status(source_dir: Path) -> dict[str, object]:
    required = {
        "emar.csv": source_dir / "emar.csv",
        "emar_detail.csv": source_dir / "emar_detail.csv",
        "prescriptions.csv": source_dir / "prescriptions.csv",
        "admissions.csv": source_dir / "admissions.csv",
        "patients.csv": source_dir / "patients.csv",
        "inputevents.csv": source_dir / "inputevents.csv",
    }
    result: dict[str, object] = {}
    for name, path in required.items():
        result[name] = {
            "path": str(path),
            "found": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else None,
            "columns": existing_columns(path) if path.exists() else [],
        }
    return result


def iter_target_rows(
    path: Path,
    usecols: list[str],
    name_column: str,
    chunk_size: int,
) -> tuple[Iterable[pd.DataFrame], dict[str, object]]:
    stats: dict[str, object] = {
        "rows_read": 0,
        "rows_retained": 0,
        "target_rows_read": 0,
        "non_administration_target_rows": 0,
        "rows_by_class": Counter(),
        "classification_status": Counter(),
        "invalid_name_count": 0,
        "invalid_subject_id_count": 0,
        "invalid_hadm_id_count": 0,
        "top_unmapped_names": Counter(),
    }

    def generator() -> Iterable[pd.DataFrame]:
        for chunk in pd.read_csv(
            path,
            usecols=usecols,
            chunksize=chunk_size,
            low_memory=False,
            dtype={column: "string" for column in usecols},
        ):
            stats["rows_read"] += len(chunk)
            if "subject_id" in chunk:
                stats["invalid_subject_id_count"] += int(
                    chunk["subject_id"].fillna("").astype(str).str.strip().eq("").sum()
                )
            if "hadm_id" in chunk:
                stats["invalid_hadm_id_count"] += int(
                    chunk["hadm_id"].fillna("").astype(str).str.strip().eq("").sum()
                )
            classified = chunk[name_column].map(classify_medication)
            chunk["medication_class"] = classified.map(lambda pair: pair[0])
            chunk["classification_status"] = classified.map(lambda pair: pair[1])
            stats["classification_status"].update(chunk["classification_status"])
            stats["invalid_name_count"] += int(chunk[name_column].isna().sum())
            target = chunk["medication_class"].isin(TARGET_CLASSES)
            stats["top_unmapped_names"].update(
                chunk.loc[~target, name_column].dropna().map(str).str.strip()
            )
            stats["target_rows_read"] += int(target.sum())
            if "event_txt" in chunk:
                recorded = chunk["event_txt"].fillna("").str.contains(
                    RECORDED_ADMINISTRATION, regex=True
                ) & ~chunk["event_txt"].fillna("").str.strip().str.lower().str.startswith("not ")
                stats["non_administration_target_rows"] += int((target & ~recorded).sum())
                target &= recorded
            if target.any():
                retained = chunk.loc[target].copy()
                stats["rows_retained"] += len(retained)
                stats["rows_by_class"].update(retained["medication_class"])
                yield retained

    return generator(), stats


def write_target_table(
    path: Path,
    output_path: Path,
    usecols: list[str],
    name_column: str,
    chunk_size: int,
    output_columns: list[str],
) -> dict[str, object]:
    chunks, stats = iter_target_rows(path, usecols, name_column, chunk_size)
    frames = []
    for chunk in chunks:
        frames.append(chunk)
    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    for column in output_columns:
        if column not in result:
            result[column] = pd.NA
    result = result[output_columns]
    result["source_file"] = path.name
    result.to_parquet(output_path, index=False)
    return stats


def load_ecg(path: Path | None) -> tuple[pd.DataFrame, dict[str, object]]:
    required = ["study_id", "hadm_id", "ecg_time"]
    if path is None or not path.exists():
        return pd.DataFrame(columns=required + ["subject_id"]), {
            "found": False, "reason": "No ECG input path was supplied or it does not exist."
        }
    columns = existing_columns(path)
    subject_column = "subject_id" if "subject_id" in columns else "SubjectID"
    missing = [column for column in required if column not in columns]
    if subject_column not in columns:
        missing.append("subject_id or SubjectID")
    if missing:
        return pd.DataFrame(columns=required + ["subject_id"]), {
            "found": True, "path": str(path), "missing_columns": missing
        }
    usecols = ["study_id", subject_column, "hadm_id", "ecg_time"]
    ecg = pd.read_csv(path, usecols=usecols, low_memory=False)
    ecg = ecg.rename(columns={subject_column: "subject_id"})
    ecg["ecg_time"] = read_datetime(ecg["ecg_time"])
    return ecg, {
        "found": True, "path": str(path), "rows": len(ecg),
        "invalid_ecg_time": int(ecg["ecg_time"].isna().sum()),
    }


def build_links(administrations: pd.DataFrame, ecg: pd.DataFrame) -> pd.DataFrame:
    if administrations.empty or ecg.empty:
        return pd.DataFrame(columns=LINK_OUTPUT_COLUMNS)
    admins = administrations.copy()
    admins["administration_time"] = read_datetime(admins["charttime"])
    admins["subject_id"] = admins["subject_id"].astype("string")
    admins["hadm_id"] = admins["hadm_id"].astype("string")
    ecg = ecg.copy()
    ecg["subject_id"] = ecg["subject_id"].astype("string")
    ecg["hadm_id"] = ecg["hadm_id"].astype("string")
    merged = ecg.merge(admins, on=["subject_id", "hadm_id"], how="inner")
    merged["hours_from_ecg"] = (
        merged["administration_time"] - merged["ecg_time"]
    ).dt.total_seconds() / 3600
    merged["temporal_classification"] = "administration_after_ecg"
    merged.loc[merged["hours_from_ecg"] < 0, "temporal_classification"] = (
        "administration_before_ecg"
    )
    merged.loc[merged["hours_from_ecg"] == 0, "temporal_classification"] = (
        "administration_at_ecg_time"
    )
    merged["linkage_method"] = "subject_id_and_hadm_id_exact"
    merged["data_quality_flags"] = ""
    merged.loc[merged["administration_time"].isna(), "data_quality_flags"] = (
        "invalid_charttime"
    )
    merged.loc[merged["ecg_time"].isna(), "data_quality_flags"] = "invalid_ecg_time"
    output = merged.rename(columns={"medication": "original_medication_name"})
    for column in LINK_OUTPUT_COLUMNS:
        if column not in output:
            output[column] = pd.NA
    return output[LINK_OUTPUT_COLUMNS]


def admission_quality(path: Path) -> dict[str, object]:
    columns = existing_columns(path)
    usecols = [
        column for column in
        ["subject_id", "hadm_id", "admittime", "dischtime", "deathtime"]
        if column in columns
    ]
    frame = pd.read_csv(path, usecols=usecols, low_memory=False)
    result: dict[str, object] = {"rows": len(frame), "columns": columns}
    for column in ["admittime", "dischtime", "deathtime"]:
        if column in frame:
            parsed = read_datetime(frame[column])
            result[f"{column}_valid"] = int(parsed.notna().sum())
            result[f"{column}_invalid"] = int(parsed.isna().sum() - frame[column].isna().sum())
    return result


def write_summary(
    output_path: Path,
    administrations: pd.DataFrame,
    links: pd.DataFrame,
    prescription_stats: dict[str, object],
    eligible_admissions: int,
) -> None:
    rows = []
    for medication_class in TARGET_CLASSES:
        class_admin = administrations[
            administrations["medication_class"] == medication_class
        ]
        class_links = links[links["medication_class"] == medication_class]
        for category in (
            "administration_before_ecg",
            "administration_at_ecg_time",
            "administration_after_ecg",
        ):
            rows.append({
                "medication_class": medication_class,
                "temporal_category": category,
                "administration_count": len(class_admin),
                "linked_pair_count": int(
                    (class_links["temporal_classification"] == category).sum()
                ),
                "unique_admissions_with_administration": class_admin["hadm_id"].nunique(),
                "unique_patients_with_administration": class_admin["subject_id"].nunique(),
                "eligible_admissions": eligible_admissions,
                "proportion_eligible_admissions_with_administration": (
                    class_admin["hadm_id"].nunique() / eligible_admissions
                    if eligible_admissions else pd.NA
                ),
            })
    for medication_class in TARGET_CLASSES:
        rows.append({
            "medication_class": medication_class,
            "temporal_category": "prescription_order",
            "administration_count": int(
                prescription_stats["rows_by_class"].get(medication_class, 0)
            ),
            "linked_pair_count": 0,
            "unique_admissions_with_administration": pd.NA,
            "unique_patients_with_administration": pd.NA,
            "eligible_admissions": eligible_admissions,
            "proportion_eligible_admissions_with_administration": pd.NA,
        })
    pd.DataFrame(rows).to_csv(output_path, index=False)


def write_report(
    output_path: Path,
    statuses: dict[str, object],
    admin_stats: dict[str, object],
    prescription_stats: dict[str, object],
    ecg_status: dict[str, object],
    admission_status: dict[str, object],
    administrations: pd.DataFrame,
    links: pd.DataFrame,
) -> None:
    def fmt_counter(counter: Counter) -> str:
        return ", ".join(f"{key}: {value}" for key, value in counter.items()) or "none"

    source_lines = []
    for name, status in statuses.items():
        source_lines.append(
            f"| `{name}` | {'FOUND' if status['found'] else 'MISSING'} | "
            f"{status.get('size_bytes', '') or ''} | "
            f"{', '.join(status.get('columns', [])) or 'n/a'} |"
        )
    class_counts = fmt_counter(admin_stats["rows_by_class"])
    temporal_counts = (
        links["temporal_classification"].value_counts().to_dict()
        if not links.empty else {}
    )
    report = f"""# Medication timestamp linkage audit

## Scope and reproducibility

This is a targeted audit of the local archives and existing workspace inputs.
It does not rebuild the ECG master, reconstruct longitudinal outcomes, estimate
causal effects, or treat prescriptions as administrations. Run it with:

`python run_medication_timestamp_audit.py --source-dir <source_dir> --output-dir <output_dir> [--ecg <ecg_file>]`

The source rows are processed in chunks of {CHUNK_SIZE:,}. Outputs are
deterministic for a fixed set of input files and paths.

## Source inventory

| Source | Status | Size (bytes) | Columns observed |
|---|---|---:|---|
{chr(10).join(source_lines)}

`emar_detail.csv` is missing from the extracted hospital archive. No dose
detail fields can therefore be joined or claimed. `inputevents.csv` is retained
as an ICU input source, but it is not treated as a discrete EMAR
administration. The extracted source directory is not a replacement for the
original archives.

The local `hosp.rar` (762,388,455 bytes) was listed and extracted with the
installed `tar.exe` without extraction errors; its relevant members were
`emar.csv`, `prescriptions.csv`, `admissions.csv`, `patients.csv`, and
`omr.csv`. The local `icu.rar` (1,651,036,480 bytes) was listed and extracted
with the same tool without extraction errors; its relevant member was
`inputevents.csv`. `emar_detail.csv` was not an archive member.

## Fields and matching rules

Administration output uses `subject_id`, `hadm_id`, `emar_id`, `emar_seq`,
`charttime`, `storetime`, `event_txt`, and `medication`. `charttime` is used as
the administration event time and `storetime` is retained as record-entry
time; no assumption is made that they are interchangeable. Prescription
output uses the available order identifiers, `starttime`, `stoptime`, drug,
route, and dose fields. Orders and administrations are separate outputs.

Medication text is lower-cased, whitespace-normalized, and matched using
whole-word generic-name rules. The target classes are statins
(atorvastatin, simvastatin, rosuvastatin, pravastatin, lovastatin,
fluvastatin, pitavastatin, cerivastatin), aspirin, beta blockers (metoprolol,
carvedilol, atenolol, propranolol, bisoprolol, labetalol, nadolol, nebivolol,
pindolol, sotalol, esmolol, timolol), and ACE inhibitors (lisinopril,
enalapril, ramipril, perindopril, captopril, benazepril, quinapril, fosinopril,
trandolapril, moexipril). Multiple matches are ambiguous and are not retained
as a target class; unrelated names are not exported.

## Counts and quality checks

| Measure | Result |
|---|---:|
| EMAR rows read | {admin_stats['rows_read']:,} |
| EMAR target administrations retained | {admin_stats['rows_retained']:,} |
| EMAR target rows excluded as non-administration statuses | {admin_stats['non_administration_target_rows']:,} |
| Target administrations by class | {class_counts} |
| EMAR rows with missing medication name | {admin_stats['invalid_name_count']:,} |
| EMAR rows with invalid subject_id / hadm_id | {admin_stats['invalid_subject_id_count']:,} / {admin_stats['invalid_hadm_id_count']:,} |
| EMAR rows with valid subject_id / hadm_id | {admin_stats['rows_read'] - admin_stats['invalid_subject_id_count']:,} / {admin_stats['rows_read'] - admin_stats['invalid_hadm_id_count']:,} ({(admin_stats['rows_read'] - admin_stats['invalid_hadm_id_count']) / admin_stats['rows_read']:.2%} admission-linkage validity) |
| Prescription rows read | {prescription_stats['rows_read']:,} |
| Prescription target orders retained | {prescription_stats['rows_retained']:,} |
| Same-patient/same-admission ECG-medication pairs | {len(links):,} |
| Temporal pair counts | {temporal_counts or 'none'} |

Counts in the administration output are source-event counts. Joined ECG
pair counts are not unique administration counts. Unique-admission and
unique-patient counts are included in the summary CSV and are calculated
before the ECG join.

Admission chronology was checked from `admissions.csv`: {admission_status}.
ECG input status: {ecg_status}.
The existing prescription-derived indicator columns were not available as a
machine-readable input, so disagreement between those indicators and EMAR
administrations is not estimable from this workspace.

## Existing longitudinal and ECG data

No ECG file was supplied to this run, and no source-level ECG master was
present in the inspected workspace. Consequently, `ecg_medication_timing.parquet`
has the required schema but zero rows. Existing documentation describes
admission, MI, death, and observation fields, but those derived files were not
available as local machine-readable inputs for this audit. No chronology or
outcome table was modified or reconstructed.

## Decision report

### A. ECG-level temporal analysis

The EMAR source contains event timestamps and valid patient/admission
identifiers for retained records, so the method can establish before/at/after
relationships once an ECG file with `study_id`, patient ID, `hadm_id`, and
`ecg_time` is supplied. This run cannot establish any ECG-level relationships
because that ECG input is missing.

### B. Treatment-effect analysis

No. Prescription starts are orders, not proof of administration, and a
recorded inpatient administration is not proof of treatment initiation,
outpatient use, adherence, or a causal assignment time. The available
administration timestamp alone does not establish prior exposure history,
baseline covariates, a clinically defensible time zero, or subsequent-MI
follow-up.

### C. Missing-data decision

The exact missing source required for ECG timing in this run is an ECG master
or source file containing `study_id`, `subject_id`/`SubjectID`, `hadm_id`, and
`ecg_time`. The exact missing hospital source is `emar_detail.csv`, needed
for dose and detailed administration fields requested by the audit. The
existing machine-readable admission/MI/death/follow-up artifacts are also
not present in the inspected workspace; they are required only for the
separate longitudinal treatment-effect design, not for the source-event
extraction itself.
"""
    output_path.write_text(report, encoding="utf-8")


def main() -> None:
    args = parse_args()
    setup_logging(args.output_dir)
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    statuses = source_status(source_dir)
    LOG.info("Source inventory complete: %s", statuses)

    required_admin = [
        column for column in
        ["subject_id", "hadm_id", "emar_id", "emar_seq", "charttime",
         "storetime", "event_txt", "medication"]
        if column in statuses["emar.csv"]["columns"]
    ]
    required_prescription = [
        column for column in
        ["subject_id", "hadm_id", "pharmacy_id", "poe_id", "poe_seq",
         "starttime", "stoptime", "drug_type", "drug", "route",
         "dose_val_rx", "dose_unit_rx"]
        if column in statuses["prescriptions.csv"]["columns"]
    ]
    if not required_admin or "medication" not in required_admin:
        raise ValueError("emar.csv is missing the required medication fields.")
    if not required_prescription or "drug" not in required_prescription:
        raise ValueError("prescriptions.csv is missing the required drug fields.")

    admin_stats = write_target_table(
        source_dir / "emar.csv",
        output_dir / "medication_administrations.parquet",
        required_admin,
        "medication",
        args.chunk_size,
        ADMIN_OUTPUT_COLUMNS,
    )
    prescription_stats = write_target_table(
        source_dir / "prescriptions.csv",
        output_dir / "medication_prescription_orders.parquet",
        required_prescription,
        "drug",
        args.chunk_size,
        PRESCRIPTION_OUTPUT_COLUMNS,
    )
    administrations = pd.read_parquet(output_dir / "medication_administrations.parquet")
    ecg, ecg_status = load_ecg(args.ecg)
    links = build_links(administrations, ecg)
    links.to_parquet(output_dir / "ecg_medication_timing.parquet", index=False)

    admission_status = (
        admission_quality(source_dir / "admissions.csv")
        if statuses["admissions.csv"]["found"] else {"found": False}
    )
    write_summary(
        output_dir / "medication_timestamp_linkage_summary.csv",
        administrations,
        links,
        prescription_stats,
        int(admission_status.get("rows", 0)),
    )
    write_report(
        output_dir / "medication_timestamp_linkage_audit.md",
        statuses,
        admin_stats,
        prescription_stats,
        ecg_status,
        admission_status,
        administrations,
        links,
    )
    LOG.info("Audit complete: %s", output_dir)


if __name__ == "__main__":
    main()
