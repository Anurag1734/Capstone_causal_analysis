from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[3]
MASTER_SPLITS = ("train", "validation", "test")
EXPOSURES = ("aspirin_before", "aspirin_during", "aspirin_after")
COHORT_COVARIATES = (
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "beta_blocker_before",
    "acei_before",
)

COHORT_PATH = Path("causal_models/data/statin_recurrent_mi_cohort.parquet")
MASTER_DIR = Path("master")
ACUTE_ENDPOINT_PATH = Path(
    "causal_models/phase13_target_trial/acute_endpoint_by_index_admission.csv"
)
PHASE14_SUMMARY_PATH = Path(
    "causal_models/phase14_exposure_endpoint/acute_mi_episode_summary.json"
)
ENDPOINT_TIMING_PATH = Path(
    "causal_models/phase13_target_trial/endpoint_timing_summary.csv"
)
ENDPOINT_CODE_COUNTS_PATH = Path(
    "causal_models/phase13_target_trial/existing_endpoint_code_class_counts.csv"
)
MEDICATION_AUDIT_PATH = Path(
    "medication_timestamp_audit/medication_timestamp_linkage_audit.md"
)
TIMESTAMP_SUMMARY_PATH = Path(
    "causal_models/aspirin/phase1_exposure_feasibility/ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json"
)


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], name: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def collapse_admission_exposures(
    master: pd.DataFrame, variables: tuple[str, ...]
) -> pd.DataFrame:
    """Collapse ECG rows to one admission row, rejecting conflicting indicators."""
    identifiers = ["subject_id", "hadm_id"]
    _require_columns(master, tuple(identifiers), "Processed master")
    present = [variable for variable in variables if variable in master.columns]
    grouped = master.groupby(identifiers, dropna=False, sort=False)
    if grouped.size().index.to_frame(index=False)[identifiers].isna().any().any():
        raise ValueError("Processed master contains missing patient/admission identifiers.")
    for variable in present:
        values = pd.to_numeric(master[variable], errors="coerce")
        invalid = values.dropna().loc[lambda series: ~series.isin([0, 1])]
        if not invalid.empty:
            raise ValueError(f"{variable} contains values outside binary 0/1.")
        if grouped[variable].nunique(dropna=True).gt(1).any():
            raise ValueError(f"{variable} varies within an admission.")
    if not present:
        return master[identifiers].drop_duplicates().reset_index(drop=True)
    return grouped[present].first().reset_index()


def summarize_binary(
    frame: pd.DataFrame, variable: str, scope: str, unit: str
) -> dict[str, Any]:
    denominator = len(frame)
    if variable not in frame.columns:
        return {
            "scope": scope,
            "variable": variable,
            "unit": unit,
            "denominator": denominator,
            "positive_or_record_count": pd.NA,
            "negative_count": pd.NA,
            "missing_count": pd.NA,
            "percent_positive_of_observed": pd.NA,
            "status": "column_absent",
        }
    values = pd.to_numeric(frame[variable], errors="coerce")
    invalid = values.dropna().loc[lambda series: ~series.isin([0, 1])]
    if not invalid.empty:
        raise ValueError(f"{variable} contains values outside binary 0/1.")
    positive = int(values.eq(1).sum())
    negative = int(values.eq(0).sum())
    missing = int(values.isna().sum())
    observed = positive + negative
    return {
        "scope": scope,
        "variable": variable,
        "unit": unit,
        "denominator": denominator,
        "positive_or_record_count": positive,
        "negative_count": negative,
        "missing_count": missing,
        "percent_positive_of_observed": (
            round(100 * positive / observed, 2) if observed else pd.NA
        ),
        "status": "available",
    }


def _read_master(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    ecg_frames: list[pd.DataFrame] = []
    split_sizes: dict[str, int] = {}
    master_columns = ("SubjectID", "hadm_id", *EXPOSURES)
    for split in MASTER_SPLITS:
        path = root / MASTER_DIR / f"{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Processed master split is missing: {path}")
        available = set(pq.ParquetFile(path).schema.names)
        if not {"SubjectID", "hadm_id"}.issubset(available):
            raise ValueError(f"Processed master split lacks patient/admission identifiers: {path}")
        columns = [column for column in master_columns if column in available]
        frame = pd.read_parquet(path, columns=columns).rename(
            columns={"SubjectID": "subject_id"}
        )
        if frame[["subject_id", "hadm_id"]].isna().any().any():
            raise ValueError(f"Processed master split has null identifiers: {path}")
        ecg_frames.append(frame)
        split_sizes[split] = len(frame)
    master = pd.concat(ecg_frames, ignore_index=True)
    _require_columns(master, ("aspirin_before", "aspirin_during"), "Processed master")
    admission_exposures = collapse_admission_exposures(master, EXPOSURES)
    return master, admission_exposures, split_sizes


def _read_inputs(root: Path) -> dict[str, Any]:
    cohort_path = root / COHORT_PATH
    acute_path = root / ACUTE_ENDPOINT_PATH
    summary_path = root / PHASE14_SUMMARY_PATH
    timing_path = root / ENDPOINT_TIMING_PATH
    code_counts_path = root / ENDPOINT_CODE_COUNTS_PATH
    medication_audit_path = root / MEDICATION_AUDIT_PATH
    for path in (
        cohort_path,
        acute_path,
        summary_path,
        timing_path,
        code_counts_path,
        medication_audit_path,
    ):
        if not path.is_file():
            raise FileNotFoundError(f"Required existing assessment input is missing: {path}")

    cohort = pd.read_parquet(cohort_path)
    _require_columns(
        cohort,
        (
            "subject_id",
            "hadm_id",
            "prior_mi",
            "eligible_prior_mi",
            "survived_to_index_discharge",
            "event_type",
            "observation_end",
            "followup_horizon_end",
            "index_dischtime",
            "death_indicator",
            *COHORT_COVARIATES,
        ),
        "Existing longitudinal cohort",
    )
    if cohort.duplicated(["subject_id", "hadm_id"]).any():
        raise ValueError("Existing longitudinal cohort has duplicate index admissions.")
    if not cohort["prior_mi"].eq(1).all() or not cohort["eligible_prior_mi"].eq(1).all():
        raise ValueError("Existing cohort does not consistently meet its previous-MI eligibility flag.")
    if not cohort["survived_to_index_discharge"].eq(1).all():
        raise ValueError("Existing cohort includes patients not marked as index-discharge survivors.")

    master_rows, admission_exposures, split_sizes = _read_master(root)
    master_exposures = admission_exposures[
        ["subject_id", "hadm_id", *[c for c in EXPOSURES if c in admission_exposures]]
    ]
    joined = cohort.drop(columns=[c for c in EXPOSURES if c in cohort], errors="ignore").merge(
        master_exposures,
        on=["subject_id", "hadm_id"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    if "aspirin_before" in cohort:
        comparison = joined[["aspirin_before"]].join(
            cohort["aspirin_before"].reset_index(drop=True).rename("cohort_aspirin_before")
        )
        matched = comparison["aspirin_before"].notna()
        if not comparison.loc[matched, "aspirin_before"].eq(
            comparison.loc[matched, "cohort_aspirin_before"]
        ).all():
            raise ValueError("Existing cohort aspirin_before disagrees with processed master.")

    # Keep the existing cohort outcome fields while attaching aspirin indicators
    # directly from the processed master, without filtering on statin exposure.
    joined = cohort.drop(columns=[c for c in EXPOSURES if c in cohort], errors="ignore").merge(
        master_exposures,
        on=["subject_id", "hadm_id"],
        how="left",
        validate="one_to_one",
    )
    acute = pd.read_csv(acute_path)
    _require_columns(acute, ("subject_id", "hadm_id", "acute_recurrent_mi", "acute_event_type"), "Acute endpoint")
    episode_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    timing = pd.read_csv(timing_path)
    endpoint_code_counts = pd.read_csv(code_counts_path)
    audit_text = medication_audit_path.read_text(encoding="utf-8")
    timestamp_summary_path = root / TIMESTAMP_SUMMARY_PATH
    timestamp_summary = (
        json.loads(timestamp_summary_path.read_text(encoding="utf-8"))
        if timestamp_summary_path.is_file()
        else None
    )
    timestamp_artifact_exists = any(
        (root / relative_path).is_file()
        for relative_path in (
            Path("causal_models/aspirin/phase1_exposure_feasibility/aspirin_exposure_timestamps.parquet"),
            Path("causal_models/phase14_exposure_endpoint/aspirin_exposure_timestamps.parquet"),
        )
    ) or timestamp_summary is not None
    return {
        "cohort": cohort,
        "master_rows": master_rows,
        "admission_exposures": admission_exposures,
        "joined": joined,
        "acute": acute,
        "episode_summary": episode_summary,
        "timing": timing,
        "endpoint_code_counts": endpoint_code_counts,
        "audit_text": audit_text,
        "split_sizes": split_sizes,
        "timestamp_artifact_exists": timestamp_artifact_exists,
        "timestamp_summary": timestamp_summary,
    }


def _aspirin_emar_record_count(audit_text: str) -> int | None:
    match = re.search(
        r"Target administrations by class \|[^|]*aspirin:\s*([\d,]+)",
        audit_text,
        flags=re.IGNORECASE,
    )
    return int(match.group(1).replace(",", "")) if match else None


def _exposure_rows(data: dict[str, Any]) -> pd.DataFrame:
    master_rows = data["master_rows"]
    admission_exposures = data["admission_exposures"]
    joined = data["joined"]
    rows = []
    scopes = (
        ("all_master_ecg_rows", master_rows, "ECG rows"),
        ("all_master_admissions", admission_exposures, "admissions"),
        ("eligible_previous_mi_index_admissions", joined, "index admissions"),
    )
    for scope, frame, unit in scopes:
        for variable in EXPOSURES:
            row = summarize_binary(frame, variable, scope, unit)
            row["source_status"] = (
                "aspirin_before: prescription-order proxy per project provenance documentation"
                if variable == "aspirin_before"
                else (
                    "aspirin_during: in-hospital master indicator; source and event semantics not validated"
                    if variable == "aspirin_during"
                    else "aspirin_after: absent from processed master schema"
                )
            )
            rows.append(row)
    emar_count = _aspirin_emar_record_count(data["audit_text"])
    rows.append(
        {
            "scope": "prior_source_audit_aggregate",
            "variable": "aspirin_emar_administration_records",
            "unit": "source administration records",
            "denominator": pd.NA,
            "positive_or_record_count": emar_count if emar_count is not None else pd.NA,
            "negative_count": pd.NA,
            "missing_count": pd.NA,
            "percent_positive_of_observed": pd.NA,
            "status": "aggregate_only_no_admission_level_rows",
            "source_status": (
                "Existing medication source audit; not linked to the eligible cohort and not timestamp-validated here"
            ),
        }
    )
    timestamp_summary = data["timestamp_summary"]
    if timestamp_summary is not None:
        for variable, value, unit, denominator, interpretation in (
            (
                "aspirin_emar_rows_linked_to_index_admissions",
                timestamp_summary["aspirin_emar_rows_linked_to_index_admissions"],
                "eMAR rows",
                timestamp_summary["eligible_prior_mi_index_admissions"],
                "Record-level eMAR matches after exact patient/admission linkage.",
            ),
            (
                "administered_rows_with_valid_charttime",
                timestamp_summary["administered_rows_with_valid_charttime"],
                "eMAR administration rows",
                timestamp_summary["aspirin_emar_rows_linked_to_index_admissions"],
                "Only event_txt exactly Administered and valid charttime.",
            ),
            (
                "index_admissions_with_valid_administered_charttime",
                timestamp_summary["index_admissions_with_valid_administered_charttime"],
                "index admissions",
                timestamp_summary["eligible_prior_mi_index_admissions"],
                "Admissions with at least one linked, valid documented administration.",
            ),
            (
                "aspirin_before_positive_index_admissions_with_valid_administration",
                sum(
                    timestamp_summary[
                        "first_administration_timing_among_aspirin_before_positive_admissions"
                    ].values()
                ),
                "index admissions",
                int(joined["aspirin_before"].eq(1).sum()),
                "Documented in-hospital eMAR administration among pre-admission prescription-proxy positives.",
            ),
        ):
            rows.append(
                {
                    "scope": "eligible_previous_mi_index_admissions",
                    "variable": variable,
                    "unit": unit,
                    "denominator": denominator,
                    "positive_or_record_count": value,
                    "negative_count": pd.NA,
                    "missing_count": pd.NA,
                    "percent_positive_of_observed": pd.NA,
                    "status": "linked_source_audit",
                    "source_status": interpretation,
                }
            )
    return pd.DataFrame(rows)


def _cohort_availability_rows(data: dict[str, Any]) -> pd.DataFrame:
    cohort = data["cohort"]
    joined = data["joined"]
    acute = data["acute"]
    summary = data["episode_summary"]
    rows: list[dict[str, Any]] = []

    def add(
        measure: str,
        count: Any,
        denominator: Any,
        unit: str,
        status: str,
        details: str,
    ) -> None:
        rows.append(
            {
                "section": "cohort_and_followup",
                "measure": measure,
                "count": count,
                "denominator": denominator,
                "unit": unit,
                "status": status,
                "details": details,
            }
        )

    n = len(cohort)
    add("eligible_previous_mi_index_patients", n, n, "patients", "available", "Prior-MI-coded admission; index selection follows the existing longitudinal cohort rule.")
    add("index_admission_available", int(cohort["hadm_id"].notna().sum()), n, "index admissions", "available", "One index admission per patient in the existing cohort.")
    add("previous_mi_eligibility_flag", int(cohort["eligible_prior_mi"].eq(1).sum()), n, "patients", "available", "Code-based prior-MI eligibility; not a clinical adjudication.")
    add("survived_to_index_discharge", int(cohort["survived_to_index_discharge"].eq(1).sum()), n, "patients", "available", "The cohort's index admission ends in discharge survival.")
    for variable in ("aspirin_before", "aspirin_during", "aspirin_after"):
        if variable not in joined:
            add(f"{variable}_available", pd.NA, n, "index admissions", "column_absent", "No such variable in processed master.")
        else:
            available = int(joined[variable].notna().sum())
            add(f"{variable}_available", available, n, "index admissions", "available", "Availability describes a proxy/indicator, not validated aspirin assignment.")
            add(f"{variable}_missing", n - available, n, "index admissions", "available", "Missing is not classified as untreated.")
            if variable in ("aspirin_before", "aspirin_during"):
                add(
                    f"{variable}_positive",
                    int(pd.to_numeric(joined[variable], errors="coerce").eq(1).sum()),
                    n,
                    "index admissions",
                    "available",
                    "Positive count among all eligible index admissions; missing values remain separate.",
                )

    add(
        "aspirin_specific_timestamp_summary_exists",
        int(data["timestamp_artifact_exists"]),
        1,
        "artifact",
        "available",
        "A record-level linked summary is retained separately; raw event rows are not exported.",
    )
    timestamp_summary = data["timestamp_summary"]
    if timestamp_summary is None:
        add(
            "eligible_index_admissions_with_valid_aspirin_administration",
            pd.NA,
            n,
            "index admissions",
            "not_assessable",
            "No aspirin eMAR timestamp summary exists; this is unknown, not zero.",
        )
        add(
            "first_aspirin_administration_timing_relative_to_index",
            pd.NA,
            pd.NA,
            "index admissions",
            "not_assessable",
            "Before/during/after index timing cannot be computed without linked charttime rows.",
        )
    else:
        add(
            "index_admissions_with_any_aspirin_emar_record",
            timestamp_summary["index_admissions_with_aspirin_emar_record"],
            n,
            "index admissions",
            "linked_source_audit",
            "Exact patient/admission linkage of aspirin-name or product-detail eMAR matches.",
        )
        add(
            "index_admissions_with_valid_aspirin_administration",
            timestamp_summary["index_admissions_with_valid_administered_charttime"],
            n,
            "index admissions",
            "linked_source_audit",
            "At least one event_txt=Administered row with valid charttime.",
        )
        add(
            "administered_aspirin_rows_with_valid_charttime",
            timestamp_summary["administered_rows_with_valid_charttime"],
            timestamp_summary["aspirin_emar_rows_linked_to_index_admissions"],
            "eMAR rows",
            "linked_source_audit",
            "Prescription orders are not counted as administrations.",
        )
        for status, label in (
            ("before_index_admission", "first_aspirin_administration_before_index"),
            ("within_index_admission", "first_aspirin_administration_during_index"),
            ("after_index_discharge", "first_aspirin_administration_after_index"),
        ):
            add(
                label,
                timestamp_summary["first_administration_timing_by_index_admission"].get(status, 0),
                n,
                "index admissions",
                "linked_source_audit",
                "Timing of each admission's first valid documented administration.",
            )
        positive_admin_count = sum(
            timestamp_summary[
                "first_administration_timing_among_aspirin_before_positive_admissions"
            ].values()
        )
        add(
            "aspirin_before_positive_index_admissions_with_valid_administration",
            positive_admin_count,
            int(joined["aspirin_before"].eq(1).sum()),
            "index admissions",
            "linked_source_audit",
            "An absent linked eMAR administration does not negate the pre-admission prescription proxy.",
        )
        for measure, count, denominator, details in (
            (
                "aspirin_emar_rows_with_valid_charttime",
                timestamp_summary["aspirin_emar_rows_with_valid_charttime"],
                timestamp_summary["aspirin_emar_rows_linked_to_index_admissions"],
                "Number of linked aspirin-matched eMAR rows with valid charttime.",
            ),
            (
                "administered_rows_with_invalid_or_missing_charttime",
                timestamp_summary["administered_rows_with_invalid_or_missing_charttime"],
                timestamp_summary["administered_rows"],
                "Only exact Administered statuses are included in this quality check.",
            ),
            (
                "duplicate_aspirin_emar_event_key_rows",
                timestamp_summary["duplicate_emar_event_key_rows"],
                timestamp_summary["aspirin_emar_rows_linked_to_index_admissions"],
                "Duplicate key is subject_id + emar_id + emar_seq.",
            ),
            (
                "timestamped_aspirin_emar_rows_outside_index_admission",
                timestamp_summary["emar_event_row_timing"].get("before_index_admission", 0)
                + timestamp_summary["emar_event_row_timing"].get("after_index_discharge", 0),
                timestamp_summary["aspirin_emar_rows_with_valid_charttime"],
                "All matched eMAR statuses, not only documented administrations.",
            ),
        ):
            add(
                measure,
                count,
                denominator,
                "eMAR rows",
                "linked_source_audit",
                details,
            )

    add(
        "followup_horizon",
        12,
        12,
        "months",
        "available",
        "Existing recurrent-MI cohort follow-up horizon begins at index discharge.",
    )
    for event_type, count in cohort["event_type"].value_counts(dropna=False).items():
        add(
            f"existing_broad_endpoint_{event_type}",
            int(count),
            n,
            "index admissions",
            "available",
            "Existing broad MI-coded endpoint; not clinically validated as distinct acute recurrent MI.",
        )
    for event_type, count in acute["acute_event_type"].value_counts(dropna=False).items():
        add(
            f"acute_code_endpoint_{event_type}",
            int(count),
            n,
            "index admissions",
            "available",
            "ICD-9 410 / ICD-10 I21-I22 code screen; distinct episode not clinically adjudicated.",
        )
    for covariate in COHORT_COVARIATES:
        add(
            f"candidate_covariate_{covariate}_available",
            int(cohort[covariate].notna().sum()),
            n,
            "index admissions",
            "available",
            "Availability does not establish a valid baseline time window or adequate confounding control.",
        )
    return pd.DataFrame(rows)


def _outcome_rows(data: dict[str, Any]) -> pd.DataFrame:
    cohort = data["cohort"]
    acute = data["acute"]
    episode = data["episode_summary"]["acute_episode_validation"]
    timing = data["timing"]
    rows = []

    def add(endpoint: str, measure: str, count: Any, denominator: Any, limitation: str) -> None:
        rows.append(
            {
                "endpoint": endpoint,
                "measure": measure,
                "count": count,
                "denominator": denominator,
                "limitation": limitation,
            }
        )

    n = len(cohort)
    add("broad_MI_coded", "subsequent MI-coded admissions", int(cohort["event_type"].eq("recurrent_mi").sum()), n, "Broad MI code set includes history codes; not a validated acute recurrence.")
    for _, row in data["endpoint_code_counts"].iterrows():
        add(
            "existing_broad_MI_code_class",
            str(row["endpoint_code_class"]),
            int(row["n"]),
            int(cohort["event_type"].eq("recurrent_mi").sum()),
            "Code class is descriptive; ICD-9 412-only codes indicate old MI/history and do not validate acute recurrence.",
        )
    for _, row in timing.iterrows():
        endpoint = str(row["endpoint"])
        add(endpoint, "first subsequent coded events", int(row["n_events"]), n, "Timing summary is diagnosis-code based; it does not prove a distinct new infarction episode.")
        if endpoint == "acute_code_only_endpoint":
            add(endpoint, "median days after index discharge", row["median_days"], int(row["n_events"]), "Event clock is admission-time relative to discharge.")
            for days in (1, 7, 30):
                timing_column = f"within_{days}_day" if days == 1 else f"within_{days}_days"
                add(endpoint, f"events within {days} day(s)", int(row[timing_column]), int(row["n_events"]), "Early readmission or continuation of the same episode is possible.")
    for key, measure in (
        ("candidate_events_with_index_admission_acute_code", "acute-coded candidate with acute code on index admission"),
        ("candidate_events_with_transfer_proxy", "acute-coded candidate with transfer proxy"),
        ("patients_with_additional_acute_coded_admission_within_30_days", "patients with another acute-coded admission within 30 days"),
    ):
        add("acute_code_episode_review", measure, int(episode[key]), int(episode["candidate_first_acute_admissions"]), "Transfer and repeat-admission flags are screening signals, not episode adjudication.")
    add(
        "death_competing",
        "death before acute-coded recurrence in 12 months",
        int(acute["acute_event_type"].eq("competing_death").sum()),
        n,
        "Death is represented as a competing event in the existing endpoint framework.",
    )
    add(
        "followup",
        "incomplete acute-endpoint follow-up",
        int(acute["acute_event_type"].eq("incomplete_followup").sum()),
        n,
        "Incomplete observation must not be coded as no subsequent MI.",
    )
    return pd.DataFrame(rows)


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    table = frame[columns].copy()
    return table.to_markdown(index=False)


def write_assessment(root: Path, output_dir: Path) -> dict[str, Path]:
    data = _read_inputs(root)
    exposures = _exposure_rows(data)
    cohort_availability = _cohort_availability_rows(data)
    outcomes = _outcome_rows(data)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "exposure_audit": output_dir / "ASPIRIN_EXPOSURE_AUDIT.md",
        "feasibility_report": output_dir / "ASPIRIN_DATA_FEASIBILITY_REPORT.md",
        "cohort_csv": output_dir / "ASPIRIN_COHORT_AVAILABILITY.csv",
        "exposure_csv": output_dir / "ASPIRIN_EXPOSURE_SUMMARY.csv",
        "outcome_csv": output_dir / "ASPIRIN_OUTCOME_AVAILABILITY.csv",
        "completion_report": output_dir / "PHASE_1_COMPLETION_REPORT.md",
    }
    exposures.to_csv(paths["exposure_csv"], index=False)
    cohort_availability.to_csv(paths["cohort_csv"], index=False)
    outcomes.to_csv(paths["outcome_csv"], index=False)

    joined = data["joined"]
    episode = data["episode_summary"]["acute_episode_validation"]
    n = len(data["cohort"])
    aspirin_before = joined["aspirin_before"]
    before_positive = int(pd.to_numeric(aspirin_before, errors="coerce").eq(1).sum())
    before_negative = int(pd.to_numeric(aspirin_before, errors="coerce").eq(0).sum())
    before_missing = int(aspirin_before.isna().sum())
    during = pd.to_numeric(joined["aspirin_during"], errors="coerce")
    during_positive = int(during.eq(1).sum())
    during_negative = int(during.eq(0).sum())
    during_missing = int(during.isna().sum())
    source_emar_count = _aspirin_emar_record_count(data["audit_text"])
    timestamp_summary = data["timestamp_summary"]
    aspirin_before_admin_count = (
        sum(
            timestamp_summary[
                "first_administration_timing_among_aspirin_before_positive_admissions"
            ].values()
        )
        if timestamp_summary
        else None
    )
    acute_n = int(data["acute"]["acute_recurrent_mi"].eq(1).sum())
    broad = data["cohort"]["event_type"].value_counts().to_dict()
    acute_counts = data["acute"]["acute_event_type"].value_counts().to_dict()
    covariate_lines = "\n".join(
        f"- `{name}`: {int(data['cohort'][name].notna().sum())}/{n} non-missing in the existing index cohort."
        for name in COHORT_COVARIATES
    )
    if timestamp_summary is None:
        timestamp_details = (
            "A linked aspirin timestamp summary has not yet been generated; rerun "
            "`scan_aspirin_source_timestamps.py` using the existing extracted source directory."
        )
    else:
        first_timing = timestamp_summary["first_administration_timing_by_index_admission"]
        timestamp_details = (
            f"Among the {timestamp_summary['eligible_prior_mi_index_admissions']:,} eligible "
            f"index admissions, {timestamp_summary['index_admissions_with_aspirin_emar_record']:,} "
            f"have at least one aspirin-matched eMAR row; "
            f"{timestamp_summary['index_admissions_with_valid_administered_charttime']:,} "
            "have an `event_txt == 'Administered'` row with valid `charttime`. Of these "
            f"first valid administrations, {first_timing.get('before_index_admission', 0):,} "
            f"occur before index admission, "
            f"{first_timing.get('within_index_admission', 0):,} during the index admission, "
            f"and {first_timing.get('after_index_discharge', 0):,} after index discharge."
        )

    exposure_text = f"""# Aspirin exposure audit

## Scope and inputs

This assessment reuses the processed master splits, the existing prior-MI longitudinal cohort, saved acute-endpoint outputs, and the prior medication audit. It also reads the already extracted compressed eMAR source tables through the existing aspirin matcher; it does not extract the raw archive or estimate treatment effects. No statin artifact is changed.

## Candidate master variables

The processed master contains {len(data['master_rows']):,} ECG rows across {len(data['admission_exposures']):,} distinct admissions. `aspirin_before` and `aspirin_during` are present; `aspirin_after` is absent.

| Variable | Project definition/provenance | What the data establish | Missingness and distribution | Interpretation |
|---|---|---|---|---|
| `aspirin_before` | Project provenance documentation identifies `hosp/prescriptions.csv`, aspirin/aspirin-combination medication-name matching, and a recent pre-admission prescription window. The exact lookback duration, qualifying order fields, and matching implementation are not independently present in the processed workspace. | Binary master indicator at admission level; prescription/order proxy, not verified administration, initiation, adherence, or treatment time zero. | {int(data['master_rows']['aspirin_before'].eq(1).sum()):,}/{len(data['master_rows']):,} ECG rows positive; {int(data['admission_exposures']['aspirin_before'].eq(1).sum()):,}/{len(data['admission_exposures']):,} admissions positive; {int(data['master_rows']['aspirin_before'].isna().sum()):,} ECG-row values missing. Eligible index cohort: {before_positive:,} positive, {before_negative:,} negative, {before_missing:,} missing. | Can distinguish the recorded proxy's 1/0 values when present; cannot distinguish an actual aspirin user from a non-user with validated exposure semantics. Missing is not untreated. |
| `aspirin_during` | Phase F documentation describes this as in-hospital aspirin use. No aspirin-specific source mapping or event-time definition for this field was verified in the local processed outputs. | Binary per-admission indicator; it is not shown to mean a recorded EMAR administration. | {int(data['master_rows']['aspirin_during'].eq(1).sum()):,}/{len(data['master_rows']):,} ECG rows positive; {int(data['admission_exposures']['aspirin_during'].eq(1).sum()):,}/{len(data['admission_exposures']):,} admissions positive; {int(data['master_rows']['aspirin_during'].isna().sum()):,} ECG-row values missing. Eligible index cohort: {during_positive:,} positive, {during_negative:,} negative, {during_missing:,} missing. | Exposure timing relative to index admission and subsequent follow-up is not recoverable from the indicator. It can reflect acute care and must not be treated as baseline therapy. |
| `aspirin_after` | Not found in the processed master schema; project documentation lists no aspirin-after field. | No variable to inspect. | Absent, not an all-missing measured field. | No post-discharge prescription or adherence contrast is supported by this column. |

Full binary distributions by ECG row, master admission, and eligible index admission are in `ASPIRIN_EXPOSURE_SUMMARY.csv`.

## Timestamped medication evidence

The prior medication-source audit reports {source_emar_count if source_emar_count is not None else 'an unavailable number of'} retained aspirin EMAR administration rows across its source-wide scan. The existing aspirin timestamp-recovery utility was run against the already extracted `hosp/*.csv.gz` source tables (no archive re-extraction); linked event-level rows were summarized and not exported. {timestamp_details}

The cohort linkage yielded {timestamp_summary['aspirin_emar_rows_linked_to_index_admissions'] if timestamp_summary else 'an unassessed number of'} eMAR rows, of which {timestamp_summary['administered_rows_with_valid_charttime'] if timestamp_summary else 'an unassessed number'} had exact `event_txt == 'Administered'` and valid `charttime`; {timestamp_summary['administered_rows_with_invalid_or_missing_charttime'] if timestamp_summary else 'an unassessed number'} qualifying administration rows had missing/invalid timestamps. Duplicate event-key rows: {timestamp_summary['duplicate_emar_event_key_rows'] if timestamp_summary else 'not assessed'}. Among all timestamped eMAR statuses, {timestamp_summary['emar_event_row_timing'].get('before_index_admission', 0) if timestamp_summary else 'not assessed'} rows predate the index admission and {timestamp_summary['emar_event_row_timing'].get('after_index_discharge', 0) if timestamp_summary else 'not assessed'} occur after index discharge. Prescription `starttime`/POE `ordertime` are order timestamps, not administrations. Status counts and detailed quality metrics are in `ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json`; the aggregate source-wide count alone is not evidence for any individual admission.

## Exposure conclusion

There are two distinct binary proxies with materially different distributions: `aspirin_before` records 779 positive and 3,877 negative index admissions among 4,656 with observed values, while `aspirin_during` records 2,979 positive and 1,677 negative admissions among the same number with observed values. Among the 779 `aspirin_before=1` admissions, {aspirin_before_admin_count if aspirin_before_admin_count is not None else 'an unassessed number'} have a linked valid in-hospital eMAR administration; no match does not establish non-use. These indicators are not interchangeable arms for a causal comparison and neither establishes aspirin assignment time; do not construct treatment effects or a DAG from them alone.
"""
    paths["exposure_audit"].write_text(exposure_text, encoding="utf-8")

    feasibility_text = f"""# Aspirin data feasibility report

## Provisional question and scope

Provisional question: among patients with a previous myocardial infarction, what is the effect of aspirin exposure on subsequent MI? This phase assesses data support only. No causal effect, target-trial treatment contrast, adjustment set, DAG, or causal model is specified.

## Population and exposure availability

The reusable longitudinal artifact contains **{n:,} unique patients/index admissions** selected under the existing rule: an index admission after a previous MI-coded admission, with survival to discharge. All {n:,} carry the cohort's prior-MI eligibility flag. The prior event is diagnosis-code based, not clinically adjudicated. The existing cohort was not filtered by statin treatment; aspirin indicators were reattached from the master by index admission.

| Measure | Count |
|---|---:|
| Eligible previous-MI index admissions | {n:,} |
| `aspirin_before=1` | {before_positive:,} |
| `aspirin_before=0` | {before_negative:,} |
| `aspirin_before` missing | {before_missing:,} |
| `aspirin_during=1` | {during_positive:,} |
| `aspirin_during=0` | {during_negative:,} |
| `aspirin_after` variable | Absent |
| Index admissions with aspirin eMAR records | {timestamp_summary['index_admissions_with_aspirin_emar_record'] if timestamp_summary else 'Not assessed'} |
| Index admissions with valid administered aspirin timestamp | {timestamp_summary['index_admissions_with_valid_administered_charttime'] if timestamp_summary else 'Not assessed'} |
| First valid administration: before / during / after index | {timestamp_summary['first_administration_timing_by_index_admission'].get('before_index_admission', 0) if timestamp_summary else 'Not assessed'} / {timestamp_summary['first_administration_timing_by_index_admission'].get('within_index_admission', 0) if timestamp_summary else 'Not assessed'} / {timestamp_summary['first_administration_timing_by_index_admission'].get('after_index_discharge', 0) if timestamp_summary else 'Not assessed'} |

The eMAR scan linked {timestamp_summary['index_admissions_with_aspirin_emar_record'] if timestamp_summary else 'an unassessed number of'} eligible index admissions to aspirin-matched records; {timestamp_summary['index_admissions_with_valid_administered_charttime'] if timestamp_summary else 'a subset'} had at least one exact `Administered` event with valid charttime. The first valid event was before index admission in {timestamp_summary['first_administration_timing_by_index_admission'].get('before_index_admission', 0) if timestamp_summary else 'an unassessed number'} admissions, during the admission in {timestamp_summary['first_administration_timing_by_index_admission'].get('within_index_admission', 0) if timestamp_summary else 'an unassessed number'}, and after discharge in {timestamp_summary['first_administration_timing_by_index_admission'].get('after_index_discharge', 0) if timestamp_summary else 'an unassessed number'}. Lack of a recorded administration does not establish non-use. The current data therefore support exposure-feasibility counts, not a validated aspirin-versus-no-aspirin treatment comparison. No missing exposure is recoded as untreated, and the prior statin complete-case/model population is not reused.

## Follow-up and subsequent MI outcome availability

The existing outcome framework begins follow-up at index discharge and has a 12-month horizon. It distinguishes competing death and incomplete observation. Existing endpoint event counts are: {broad.get('recurrent_mi', 0):,} subsequent MI-coded admissions, {broad.get('competing_death', 0):,} competing deaths, {broad.get('event_free', 0):,} event-free through horizon, and {broad.get('incomplete_followup', 0):,} incomplete follow-up. Among the 1,833 broad MI-coded admissions, 1,339 are ICD-9 412-only and 494 have an acute code; the broad endpoint is therefore not a clinically validated acute recurrence endpoint.

The saved acute-code screen identifies **{acute_n:,}** first subsequent admissions with ICD-9 410 / ICD-10 I21-I22 codes. It is an improved code-specificity screen, not proof of distinct recurrent infarction. Acute-endpoint statuses are {dict(acute_counts)}. The episode audit reports {episode['candidate_events_with_index_admission_acute_code']} candidates with an acute code on the index admission, {episode['candidate_events_with_transfer_proxy']} with a transfer proxy, and {episode['patients_with_additional_acute_coded_admission_within_30_days']} patients with another acute-coded admission within 30 days. {episode['events_within_1_day']} events are within one day, {episode['events_within_7_days']} within seven days, and {episode['events_within_30_days']} within 30 days of discharge. These signals raise continuation/transfer/readmission concerns; local artifacts have no clinical adjudication.

Observation-end and death artifacts support the current competing-risk/incomplete-follow-up framework, but MIMIC-derived hospital observation is not complete community follow-up. Outcome definitions and known limitations must be carried forward rather than called clinically validated.

## Confounding and aspirin-specific design considerations

Potential baseline common causes of aspirin prescribing and later MI include prior MI/CVD history and severity, diabetes, hypertension, CKD, age/sex, other chronic cardiovascular drugs, prior antiplatelet/anticoagulant use, bleeding risk, contraindications, and healthcare utilization.

Existing candidate data:
{covariate_lines}
- Admission type/location, prior-admission chronology, demographics, and diagnosis-coded MI history are present in existing longitudinal artifacts.
- Master has beta-blocker and ACE-inhibitor prescription proxies; these, like aspirin, are not validated administration times.
- No prebuilt bleeding-risk, aspirin-contraindication, antiplatelet-other-than-aspirin, or anticoagulant baseline indicator was found in the processed master. Availability in underlying diagnosis text/codes has not been validated for this aspirin question.
- ECG variables and `aspirin_during`, in-hospital medicines, and admission severity/management may occur after presentation or treatment and could be treatment consequences or acute-episode markers; they are not automatically baseline confounders. The existing ECG/latent provenance and temporal eligibility limitations remain.

This is a candidate-variable inventory, **not** a finalized adjustment set. A clinical indication and contraindication assessment, medication time zero, and temporal ordering are required before a DAG or adjustment design.

## Decision

**B — Aspirin research is feasible, but specific data limitations must be resolved first.**

Evidence: (1) the previous-MI longitudinal population and competing-death/incomplete-follow-up framework are available; (2) a prescription-window proxy and a distinct in-hospital indicator are each observed in 4,656 of 7,545 eligible admissions; (3) aspirin eMAR records link to {timestamp_summary['index_admissions_with_aspirin_emar_record'] if timestamp_summary else 'an unassessed number of'} index admissions, with {timestamp_summary['index_admissions_with_valid_administered_charttime'] if timestamp_summary else 'an unassessed number'} having valid documented administrations; (4) only {aspirin_before_admin_count if aspirin_before_admin_count is not None else 'an unassessed number'} of the {before_positive} `aspirin_before=1` index admissions have a linked valid eMAR administration; and (5) acute-coded MI candidates have transfer/continuation uncertainty and no clinical adjudication. Lack of a documented in-hospital administration does not negate a pre-admission prescription or prove non-use. Exposure semantics, missing exposure, clinical endpoint, and confounding information must be addressed before causal design or estimation.

## Reproducibility

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m causal_models.aspirin.phase1_exposure_feasibility.scan_aspirin_source_timestamps --mimic-root <existing-extracted-mimic-iv-root>
.\\.venv\\Scripts\\python.exe -m causal_models.aspirin.phase1_exposure_feasibility.analyze_aspirin_phase1
```

The source scanner reads the already extracted compressed CSV tables and does not extract the `.rar` archive. The report generator reuses processed master splits, longitudinal cohort/outcome outputs, and the timestamp summary; both scripts write only under this aspirin Phase 1 directory.
"""
    paths["feasibility_report"].write_text(feasibility_text, encoding="utf-8")

    completion_text = f"""# Phase 1 completion report — aspirin exposure and data feasibility

## Status

**Completed as an assessment only.** No treatment-effect estimation, causal forest, propensity weighting, SCM, DAG, or causal-effect claim was produced.

## Work completed

- Audited the two present master indicators (`aspirin_before`, `aspirin_during`) and confirmed `aspirin_after` is absent.
- Quantified indicator distributions at ECG-row, admission, and eligible prior-MI index-admission levels.
- Reused the existing 12-month longitudinal cohort and outcome artifacts without changing them or selecting on statin treatment.
- Linked aspirin-name/product-detail eMAR rows to the previous-MI index admissions, separated exact `Administered` events from order/status rows, validated timestamps, and classified each first administration relative to the index admission.
- Documented candidate aspirin-specific baseline confounders, likely post-treatment variables, data limitations, and the conditional next-step decision.
- Added focused validation tests for binary distributions, absent variables, inconsistent admission indicators, the source-audit aggregate, and generated artifact counts.

## Key counts and decision

- Eligible previous-MI index admissions: {n:,}.
- Aspirin exposure proxy observed: {before_positive + before_negative:,}/{n:,}; `aspirin_before=1`: {before_positive:,}; missing: {before_missing:,}.
- In-hospital aspirin indicator observed: {during_positive + during_negative:,}/{n:,}; positive: {during_positive:,}.
- Aspirin eMAR: {timestamp_summary['index_admissions_with_valid_administered_charttime'] if timestamp_summary else 'not assessed'} admissions with valid documented administration; first events before/during/after index: {timestamp_summary['first_administration_timing_by_index_admission'].get('before_index_admission', 0) if timestamp_summary else 'n/a'}/{timestamp_summary['first_administration_timing_by_index_admission'].get('within_index_admission', 0) if timestamp_summary else 'n/a'}/{timestamp_summary['first_administration_timing_by_index_admission'].get('after_index_discharge', 0) if timestamp_summary else 'n/a'}.
- Linked eMAR rows: {timestamp_summary['aspirin_emar_rows_linked_to_index_admissions'] if timestamp_summary else 'not assessed'}; invalid administration timestamps: {timestamp_summary['administered_rows_with_invalid_or_missing_charttime'] if timestamp_summary else 'n/a'}; duplicate event keys: {timestamp_summary['duplicate_emar_event_key_rows'] if timestamp_summary else 'n/a'}.
- Acute-coded subsequent-MI candidates: {acute_n:,}; broad recurrent-MI-coded endpoint: {broad.get('recurrent_mi', 0):,}; incomplete follow-up (broad endpoint): {broad.get('incomplete_followup', 0):,}.
- **Decision B:** feasible to continue aspirin study design work after resolving exposure timing/linkage, clinical endpoint validation, and aspirin-specific confounding/contraindication information.

## Required outputs

- `ASPIRIN_EXPOSURE_AUDIT.md`
- `ASPIRIN_DATA_FEASIBILITY_REPORT.md`
- `ASPIRIN_COHORT_AVAILABILITY.csv`
- `ASPIRIN_EXPOSURE_SUMMARY.csv`
- `ASPIRIN_OUTCOME_AVAILABILITY.csv`
- `ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json`
- `scan_aspirin_source_timestamps.py`
- `analyze_aspirin_phase1.py`
- `test_aspirin_phase1.py`

All files are confined to `causal_models/aspirin/phase1_exposure_feasibility/`; the statin branch was not modified.
"""
    paths["completion_report"].write_text(completion_text, encoding="utf-8")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit existing aspirin exposure and outcome feasibility.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root containing processed inputs.")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    paths = write_assessment(args.root.resolve(), args.output_dir.resolve())
    for label, path in paths.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
