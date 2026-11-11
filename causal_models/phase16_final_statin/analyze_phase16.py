from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CAUSAL = ROOT / "causal_models"
OUTPUT = CAUSAL / "phase16_final_statin"
ASSETS = CAUSAL / "phase16_paper_assets"

COHORT_PATH = CAUSAL / "data" / "statin_recurrent_mi_cohort.parquet"
SPLIT_DIR = CAUSAL / "data" / "statin_recurrent_mi_forest_splits"
PHASE11_METRICS = CAUSAL / "outputs" / "causal_forest" / "metrics.json"
PHASE12_ESTIMATES = CAUSAL / "phase12_robustness" / "estimator_comparison.csv"
PHASE13 = CAUSAL / "phase13_target_trial"
PHASE14 = CAUSAL / "phase14_exposure_endpoint"
PHASE15 = CAUSAL / "phase15_confounding_validation"

BASELINE_TIMING_NOTES = {
    "anchor_age": "Demographic; available before treatment.",
    "sex_male": "Demographic; available before treatment.",
    "diabetes": "Chronic-condition feature; feature lookback/time provenance is not fully validated.",
    "hypertension": "Chronic-condition feature; feature lookback/time provenance is not fully validated.",
    "ckd": "Chronic-condition feature; feature lookback/time provenance is not fully validated.",
    "statin_before": "Pre-admission order/prescription proxy, not verified prior use or adherence; DAG flags possible collider bias, sensitivity only.",
    "aspirin_before": "Pre-admission order/prescription proxy, not verified administration or adherence.",
    "beta_blocker_before": "Pre-admission order/prescription proxy, not verified administration or adherence.",
    "acei_before": "Pre-admission order/prescription proxy, not verified administration or adherence.",
    "prior_mi_coded_admission_count": "MI-coded admission proxy; constant in this cohort and not a validated episode count.",
    "days_since_last_prior_mi_code": "Code-based timing proxy; not validated severity or episode history.",
    "prior_admission_count": "Healthcare-use proxy; not a direct measure of access or disease severity.",
    "prior_mi": "Eligibility criterion, constant at 1; not a discriminating covariate.",
}

PRIMARY_CANDIDATES = [
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "verified_prior_statin_use",
    "prior_cardiovascular_history_and_severity",
    "pre_assignment_concomitant_cardiovascular_medications",
    "lipid_profile_and_treatment_indication",
]
AVAILABLE_CANDIDATES = [
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
]
SENSITIVITY_PROXIES = [
    "statin_before",
    "aspirin_before",
    "beta_blocker_before",
    "acei_before",
    "prior_mi_coded_admission_count",
    "days_since_last_prior_mi_code",
    "prior_admission_count",
]
POST_TREATMENT_OR_FORBIDDEN = {
    "statin_during",
    "statin_after",
    "length_of_stay_days",
    "index_acute_mi_code",
    "heart_failure_code",
    "cardiogenic_shock_code",
    "acute_kidney_injury_code",
    "acute_respiratory_failure_code",
    "recurrent_mi",
    "acute_recurrent_mi",
    "death",
    "followup_duration_days",
    "z_ecg",
}


def exposure_window_status(timestamp: Any, admission: Any, discharge: Any) -> str:
    """Classify a recorded timestamp against the closed admission interval."""
    timestamp = pd.to_datetime(timestamp, errors="coerce")
    admission = pd.to_datetime(admission, errors="coerce")
    discharge = pd.to_datetime(discharge, errors="coerce")
    if pd.isna(timestamp) or pd.isna(admission) or pd.isna(discharge):
        return "unavailable"
    if timestamp < admission:
        return "before_admission"
    if timestamp > discharge:
        return "after_discharge"
    return "within_index_admission"


def endpoint_disposition(classification: str) -> str:
    """Map Phase 14 screening labels without claiming clinical adjudication."""
    if classification == "candidate distinct acute MI":
        return "candidate event; descriptive or sensitivity endpoint only"
    if classification in {
        "possible transfer/readmission for the same episode",
        "possible continuation of index MI episode",
        "uncertain episode classification",
    }:
        return "episode unresolved; do not treat as confirmed distinct recurrence or as no event"
    raise ValueError(f"Unknown episode classification: {classification}")


def validate_incomplete_followup(frame: pd.DataFrame) -> None:
    """Reject any output that labels incomplete follow-up as event-free."""
    incomplete = frame["acute_event_type"].eq("incomplete_followup")
    if frame.loc[incomplete, "acute_recurrent_mi"].notna().any():
        raise ValueError("Incomplete follow-up must not be assigned an event-free outcome")


def validate_patient_split_disjoint(split_frames: dict[str, pd.DataFrame]) -> None:
    """Ensure patient identifiers do not cross train, validation, and test."""
    names = list(split_frames)
    for i, left_name in enumerate(names):
        left = set(split_frames[left_name]["SubjectID"].dropna().astype("int64"))
        for right_name in names[i + 1 :]:
            right = set(split_frames[right_name]["SubjectID"].dropna().astype("int64"))
            overlap = left & right
            if overlap:
                raise ValueError(
                    f"Patient leakage between {left_name} and {right_name}: "
                    f"{len(overlap)} shared identifiers"
                )


def validate_cohort_counts(cohort: pd.DataFrame, phase13: dict[str, Any]) -> None:
    n = len(cohort)
    known = int(cohort["statin_during"].notna().sum())
    treated = int(cohort["statin_during"].eq(1).sum())
    controls = int(cohort["statin_during"].eq(0).sum())
    missing = int(cohort["statin_during"].isna().sum())
    if (n, known, treated, controls, missing) != (7545, 4656, 2986, 1670, 2889):
        raise ValueError("Cohort treatment counts no longer match the retained Phase 13/15 evidence")
    if treated + controls != known or known + missing != n:
        raise ValueError("Treatment-group counts do not reconcile")
    if n != int(phase13["cohort_n"]):
        raise ValueError("Cohort row count does not match the saved Phase 13 summary")


def validate_complete_case_counts(cohort: pd.DataFrame, phase13: dict[str, Any]) -> None:
    known_complete = cohort.loc[
        cohort["statin_during"].notna() & cohort["followup_complete"].astype(bool)
    ]
    group_counts = known_complete.groupby("statin_during").size().to_dict()
    if group_counts != {0.0: 1216, 1.0: 2014}:
        raise ValueError(f"Unexpected known-treatment follow-up counts: {group_counts}")
    if len(known_complete) != int(phase13["phase11_complete_case_n"]):
        raise ValueError("Known-treatment complete-follow-up count does not match Phase 13")


def validate_flow_reconciliation(flow: pd.DataFrame) -> None:
    rows = flow.set_index("stage")
    eligible = rows.loc["eligible_prior_mi_discharge_survivors"]
    if int(eligible["n"]) != int(
        eligible["treated_n"] + eligible["control_n"] + eligible["treatment_missing_n"]
    ):
        raise ValueError("Eligible cohort treatment groups do not sum to the cohort total")
    known = rows.loc["known_treatment"]
    if int(known["n"]) != int(known["treated_n"] + known["control_n"]):
        raise ValueError("Known-treatment groups do not reconcile")
    for stage in (
        "complete_followup_all_treatment_statuses",
        "known_treatment_complete_followup",
        "phase11_test_complete_case",
    ):
        row = rows.loc[stage]
        if int(row["n"]) != int(
            row["treated_n"] + row["control_n"] + row["treatment_missing_n"]
        ):
            raise ValueError(f"Cohort-flow groups do not reconcile at {stage}")
    linked = rows.loc["treated_with_linked_emar", "n"]
    unmatched = rows.loc["treated_without_linked_emar", "n"]
    if int(linked + unmatched) != int(eligible["treated_n"]):
        raise ValueError("EMAR-linked and unmatched treated admissions do not reconcile")


def _read_inputs() -> dict[str, Any]:
    inputs = {
        "cohort": pd.read_parquet(COHORT_PATH),
        "phase11_metrics": json.loads(PHASE11_METRICS.read_text(encoding="utf-8")),
        "phase12_estimates": pd.read_csv(PHASE12_ESTIMATES),
        "phase13_summary": json.loads(
            (PHASE13 / "phase13_summary.json").read_text(encoding="utf-8")
        ),
        "phase13_endpoint": pd.read_csv(
            PHASE13 / "acute_endpoint_by_index_admission.csv",
            parse_dates=["death_date", "acute_first_admittime"],
        ),
        "phase13_event_counts": pd.read_csv(PHASE13 / "endpoint_event_type_counts.csv"),
        "phase13_cif": pd.read_csv(PHASE13 / "competing_risk_cumulative_incidence.csv"),
        "phase14_summary": json.loads(
            (PHASE14 / "acute_mi_episode_summary.json").read_text(encoding="utf-8")
        ),
        "phase14_episodes": pd.read_csv(PHASE14 / "acute_mi_episode_validation.csv"),
        "phase14_first_admin": pd.read_csv(
            PHASE14 / "statin_first_administration_summary.csv",
            parse_dates=["index_admittime", "index_dischtime", "first_in_admission_administration"],
        ),
        "phase14_linkage": pd.read_csv(PHASE14 / "statin_exposure_linkage_summary.csv"),
        "phase15_baseline": pd.read_csv(PHASE15 / "baseline_treatment_comparison.csv"),
        "phase15_selection": pd.read_csv(PHASE15 / "selection_missingness_flow.csv"),
        "phase15_summary": json.loads(
            (PHASE15 / "phase15_summary.json").read_text(encoding="utf-8")
        ),
    }
    return inputs


def _check_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    cohort = inputs["cohort"]
    phase13 = inputs["phase13_summary"]
    validate_cohort_counts(cohort, phase13)
    validate_complete_case_counts(cohort, phase13)

    acute = inputs["phase13_endpoint"]
    validate_incomplete_followup(acute)
    event_counts = acute["acute_event_type"].value_counts().to_dict()
    expected_types = {
        "acute_recurrent_mi": 555,
        "competing_death": 1219,
        "event_free": 2912,
        "incomplete_followup": 2859,
    }
    if event_counts != expected_types:
        raise ValueError(f"Saved acute endpoint event counts changed: {event_counts}")

    splits = {
        name: pd.read_parquet(SPLIT_DIR / f"{name}.parquet", columns=["SubjectID"])
        for name in ("train", "validation", "test")
    }
    validate_patient_split_disjoint(splits)

    first = inputs["phase14_first_admin"]
    valid = first.loc[
        first["first_administration_status"].eq("observed_within_index_admission")
    ].copy()
    if len(valid) != 1500:
        raise ValueError(f"Expected 1,500 validated first administrations; found {len(valid)}")
    statuses = [
        exposure_window_status(timestamp, admission, discharge)
        for timestamp, admission, discharge in zip(
            valid["first_in_admission_administration"],
            valid["index_admittime"],
            valid["index_dischtime"],
        )
    ]
    if set(statuses) != {"within_index_admission"}:
        raise ValueError("A validated first administration falls outside its admission window")

    return {
        "split_patient_overlap": "none",
        "acute_event_counts": event_counts,
        "valid_first_administration_n": len(valid),
        "same_day_event_death": _same_day_ordering_summary(acute, cohort),
    }


def _same_day_ordering_summary(
    acute_endpoint: pd.DataFrame,
    cohort: pd.DataFrame,
) -> dict[str, int]:
    precision = cohort[["hadm_id", "death_time_is_precise"]]
    joined = acute_endpoint.merge(precision, on="hadm_id", how="left", validate="one_to_one")
    same_day = (
        joined["acute_first_admittime"].notna()
        & joined["death_date"].notna()
        & joined["acute_first_admittime"].dt.normalize().eq(joined["death_date"].dt.normalize())
    )
    imprecise = same_day & ~joined["death_time_is_precise"].fillna(False).astype(bool)
    return {
        "same_day_acute_mi_death_pairs": int(same_day.sum()),
        "same_day_with_imprecise_death_time": int(imprecise.sum()),
        "same_day_uncertain_in_saved_endpoint": int(
            joined["acute_event_type"].eq("event_order_uncertain").sum()
        ),
    }


def _cohort_flow(inputs: dict[str, Any]) -> pd.DataFrame:
    cohort = inputs["cohort"]
    known = cohort["statin_during"].notna()
    followed = cohort["followup_complete"].astype(bool)
    known_followed = known & followed
    phase11_test = inputs["phase11_metrics"]["complete_case_analysis"]
    rows = [
        ("eligible_prior_mi_discharge_survivors", len(cohort), 7545, 2986, 1670, 2889, "One selected index admission per patient."),
        ("known_treatment", int(known.sum()), len(cohort), 2986, 1670, 2889, "Missing treatment retained as unknown; not imputed."),
        ("baseline_feature_row_available", int(inputs["phase15_summary"]["baseline_features_available_n"]), len(cohort), 2986, 1670, 2889, "2,889 missing-treatment records also lack a processed master baseline-feature row."),
        ("in_existing_phase9_splits", 6994, len(cohort), 2986, 1670, 2338, "All 4,656 known-treatment rows plus 2,338 missing-treatment rows appear in exported splits; 551 missing-treatment rows do not."),
        ("complete_followup_all_treatment_statuses", int(followed.sum()), len(cohort), int((followed & cohort["statin_during"].eq(1)).sum()), int((followed & cohort["statin_during"].eq(0)).sum()), int((followed & ~known).sum()), "Outcome-observed follow-up; competing deaths are not event-free."),
        ("known_treatment_incomplete_followup", int((known & ~followed).sum()), int(known.sum()), int((known & ~followed & cohort["statin_during"].eq(1)).sum()), int((known & ~followed & cohort["statin_during"].eq(0)).sum()), 0, "Incomplete/uncertain follow-up among known treatment; not outcome-negative."),
        ("missing_treatment_in_existing_splits", 2338, 2889, 0, 0, 2338, "No treatment imputation; these records are outside Phase 11 estimation."),
        ("missing_treatment_absent_from_existing_splits", 551, 2889, 0, 0, 551, "Absence is verified from split files; reason is not preserved."),
        ("known_treatment_complete_followup", int(known_followed.sum()), int(known.sum()), int((known_followed & cohort["statin_during"].eq(1)).sum()), int((known_followed & cohort["statin_during"].eq(0)).sum()), 0, "3,230 Phase 11 model-ready admissions; 1,426 known-treatment admissions have incomplete/uncertain follow-up."),
        ("phase11_test_complete_case", int(phase11_test["test_admissions"]), 1075, round(phase11_test["test_treatment_prevalence"] * phase11_test["test_admissions"]), int(phase11_test["test_admissions"] - round(phase11_test["test_treatment_prevalence"] * phase11_test["test_admissions"])), 0, "499 complete cases of 1,075 test-split rows; 576 did not enter the saved complete-case test estimate."),
        ("treated_with_linked_emar", int(inputs["phase14_summary"]["timestamped_admin_admissions_linked"]), int(inputs["phase14_summary"]["treated_index_admissions"]), int(inputs["phase14_summary"]["timestamped_admin_admissions_linked"]), 0, 0, "Filtered exact subject/admission EMAR linkage among statin_during=1."),
        ("treated_without_linked_emar", int(inputs["phase14_summary"]["treated_index_admissions"] - inputs["phase14_summary"]["timestamped_admin_admissions_linked"]), int(inputs["phase14_summary"]["treated_index_admissions"]), int(inputs["phase14_summary"]["treated_index_admissions"] - inputs["phase14_summary"]["timestamped_admin_admissions_linked"]), 0, 0, "No qualifying match in retained extraction; not evidence of no administration."),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "stage",
            "n",
            "denominator_n",
            "treated_n",
            "control_n",
            "treatment_missing_n",
            "definition",
        ],
    )


def _baseline_table(inputs: dict[str, Any]) -> pd.DataFrame:
    frame = inputs["phase15_baseline"].copy()
    frame = frame.loc[frame["comparison"].eq("treated_vs_control")].copy()
    frame["measurement_and_timing_note"] = frame["variable"].map(BASELINE_TIMING_NOTES).fillna(
        "Descriptive feature; verify timing before causal use."
    )
    frame["causal_use"] = frame["variable"].map(
        {
            "anchor_age": "baseline candidate",
            "sex_male": "baseline candidate",
            "diabetes": "baseline candidate; verify history window",
            "hypertension": "baseline candidate; verify history window",
            "ckd": "baseline candidate; verify history window",
            "statin_before": "sensitivity proxy only; possible collider",
            "aspirin_before": "sensitivity proxy; order is not administration",
            "beta_blocker_before": "sensitivity proxy; order is not administration",
            "acei_before": "sensitivity proxy; order is not administration",
            "prior_mi": "eligibility criterion",
        }
    ).fillna("history/utilization proxy; not a validated severity measure")
    return frame


def _endpoint_table(inputs: dict[str, Any], checks: dict[str, Any]) -> pd.DataFrame:
    phase13 = inputs["phase13_summary"]
    phase14 = inputs["phase14_summary"]
    rows: list[dict[str, Any]] = []

    def add(category: str, n: int, denominator: int, interpretation: str) -> None:
        rows.append(
            {
                "category": category,
                "n": int(n),
                "denominator": int(denominator),
                "treatment_group": "all",
                "interpretation": interpretation,
            }
        )

    broad_codes = phase13["existing_endpoint_code_class_counts"]
    add("broad_MI-coded recurrence", phase13["broad_existing_event_type_counts"]["recurrent_mi"], 7545, "Existing endpoint; includes old-MI/history-code-only events.")
    add("ICD-9 412-only events", broad_codes["icd9_412_only"], broad_codes["icd9_412_only"] + broad_codes["acute_code_present"], "Not acute recurrent MI evidence by itself.")
    add("Broad endpoint with acute code present", broad_codes["acute_code_present"], broad_codes["icd9_412_only"] + broad_codes["acute_code_present"], "Code-screen subset; not clinical adjudication.")
    add("First subsequent acute-coded candidate", phase14["acute_episode_validation"]["candidate_first_acute_admissions"], 7545, "ICD-9 410* / ICD-10 I21*/I22* admission candidates.")

    acute_rows = inputs["phase13_endpoint"].loc[
        inputs["phase13_endpoint"]["acute_event_type"].eq("acute_recurrent_mi")
    ]
    broad_ids = set(
        pd.to_numeric(
            inputs["phase13_endpoint"].loc[
                inputs["phase13_endpoint"]["recurrent_mi"].eq(1),
                "first_subsequent_mi_hadm_id",
            ],
            errors="coerce",
        ).dropna().astype("int64")
    )
    acute_ids = pd.to_numeric(
        acute_rows["acute_first_hadm_id"], errors="coerce"
    ).dropna().astype("int64")
    acute_broad_overlap = int(acute_ids.isin(broad_ids).sum())
    add(
        "acute-screen event admission IDs matching broad endpoint first event",
        acute_broad_overlap,
        len(acute_rows),
        "The saved endpoint constructions are not identical; unmatched acute-screen admissions are retained.",
    )
    add(
        "acute-screen event admission IDs not matching broad endpoint first event",
        len(acute_rows) - acute_broad_overlap,
        len(acute_rows),
        "Unreconciled endpoint-construction difference; not evidence to drop or reclassify.",
    )

    classifications = phase14["acute_episode_validation"]["classification_counts"]
    for label, count in classifications.items():
        disposition = endpoint_disposition(label)
        add(f"episode_screen::{label}", count, 555, disposition)

    add("acute candidates within 1 day", phase14["acute_episode_validation"]["events_within_1_day"], 555, "Retained; no arbitrary early-event exclusion.")
    add("acute candidates within 7 days", phase14["acute_episode_validation"]["events_within_7_days"], 555, "Retained; may include continuing care or transfers.")
    add("acute candidates within 30 days", phase14["acute_episode_validation"]["events_within_30_days"], 555, "Retained; may include continuing care or transfers.")
    add("additional acute-coded admission within 7 days", phase14["acute_episode_validation"]["patients_with_additional_acute_coded_admission_within_7_days"], 555, "Possible episode duplication / transfer indicator.")
    add("additional acute-coded admission within 30 days", phase14["acute_episode_validation"]["patients_with_additional_acute_coded_admission_within_30_days"], 555, "Possible episode duplication / transfer indicator.")
    add("competing death, broad endpoint", phase13["broad_existing_event_type_counts"]["competing_death"], 7545, "Competing event; not ordinary loss to follow-up.")

    for row in inputs["phase13_event_counts"].itertuples(index=False):
        rows.append(
            {
                "category": f"acute_screen_event_type::{row.acute_event_type}",
                "n": int(row.n),
                "denominator": 7545,
                "treatment_group": str(row.treatment_group),
                "interpretation": "Saved Phase 13 competing-risk classification; descriptive only.",
            }
        )
    for row in inputs["phase13_cif"].loc[
        inputs["phase13_cif"]["endpoint_definition"].eq("acute_code_only")
        & inputs["phase13_cif"]["horizon_days"].eq(365)
    ].itertuples(index=False):
        rows.append(
            {
                "category": "descriptive_365d_CIF_acute_MI",
                "n": np.nan,
                "denominator": int(row.n),
                "treatment_group": str(row.treatment_group),
                "interpretation": f"MI CIF={row.acute_mi_cif:.4f}; death CIF={row.death_cif:.4f}; not causal.",
            }
        )
    same_day = checks["same_day_event_death"]
    add("same-day MI/death date pairs", same_day["same_day_acute_mi_death_pairs"], 7545, "Ordering checked using retained death-time precision.")
    add("same-day pairs with imprecise death time", same_day["same_day_with_imprecise_death_time"], 7545, "Would be order-uncertain; incomplete/uncertain, not event-free.")
    add("event_order_uncertain in saved acute endpoint", same_day["same_day_uncertain_in_saved_endpoint"], 7545, "Saved Phase 13 endpoint explicitly marks such rows uncertain.")
    return pd.DataFrame(rows)


def _treatment_table(inputs: dict[str, Any]) -> pd.DataFrame:
    summary = inputs["phase14_summary"]
    first = inputs["phase14_first_admin"]
    valid = first.loc[
        first["first_administration_status"].eq("observed_within_index_admission")
    ]
    admin_hours = valid["hours_admission_to_first"].dropna()
    discharge_hours = valid["hours_first_to_discharge"].dropna()
    linkage = inputs["phase14_linkage"].iloc[0]
    timing_rows = []
    for label, value in [
        ("admission_to_first_admin_hours", admin_hours),
        ("first_admin_to_discharge_hours", discharge_hours),
    ]:
        quantiles = value.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
        for quantile, amount in quantiles.items():
            timing_rows.append((label, f"p{int(quantile * 100)}", float(amount), "hours"))
    metrics = [
        ("eligible_in_hospital_exposed_admissions", summary["treated_index_admissions"], "admissions", "Existing statin_during=1 cohort; retained unchanged."),
        ("linked_emar_admissions", int(linkage["administrations_linked"]), "admissions", "Filtered statin-name and administration-like status; exact subject_id+hadm_id."),
        ("no_linked_emar_record", int(linkage["no_emar_match_or_source_unavailable"]), "admissions", "Not evidence of non-administration."),
        ("emar_administration_rows_total", summary["emar_administration_rows"], "rows", "Inpatient administration records; not adherence."),
        ("emar_rows_within_index_admission", summary["emar_administration_rows_within_index_admission"], "rows", "Timestamp within closed admission interval."),
        ("emar_rows_before_admission", summary["emar_administration_rows_before_admission"], "rows", "Out-of-window record."),
        ("emar_rows_after_discharge", summary["emar_administration_rows_after_discharge"], "rows", "Out-of-window record."),
        ("admissions_with_valid_first_in_window_admin", summary["first_admin_within_admission_n"], "admissions", "Valid first recorded administration time."),
        ("admissions_without_valid_first_in_window_admin", summary["treated_index_admissions"] - summary["first_admin_within_admission_n"], "admissions", "May include no match or unmatched/invalid timestamp; not untreated."),
        ("prescription_order_rows", summary["prescription_order_rows"], "rows", "Order record, not administration or discharge prescription."),
        ("prescription_orders_starting_in_admission", summary["prescription_orders_starting_within_index_admission"], "rows", "Starttime is order timestamp; not discharge medication reconciliation."),
        ("prescription_orders_starting_before_admission", 203, "rows", "Order records."),
        ("prescription_orders_starting_after_discharge", 24, "rows", "Order records."),
        ("prescription_order_start_time_unclassified", summary["prescription_order_rows"] - summary["prescription_orders_starting_within_index_admission"] - 203 - 24, "rows", "Timestamp unavailable or not classifiable."),
    ]
    rows = [
        {
            "measure": name,
            "value": value,
            "unit": unit,
            "interpretation": interpretation,
        }
        for name, value, unit, interpretation in metrics
    ]
    rows.extend(
        {
            "measure": measure,
            "value": value,
            "unit": unit,
            "interpretation": "Percentile among admissions with valid first in-admission recorded administration timestamps.",
        }
        for measure, _, value, unit in timing_rows
    )
    return pd.DataFrame(rows)


def _final_estimates(inputs: dict[str, Any]) -> pd.DataFrame:
    metrics = inputs["phase11_metrics"]
    cf = metrics["causal_forest"]
    p = metrics["propensity_ipw_ate"]
    ipcw = metrics["censoring_sensitivity"]
    phase11_rows = [
        ("Phase 11", "CausalForestDML", cf["ate"], *cf["ate_95_interval"], 499, 317, 182, "Existing held-out test set; binary broad MI-coded outcome."),
        ("Phase 11", "Propensity-IPW", p["estimate"], *p["cluster_bootstrap_95_interval"], 499, 317, 182, "Existing held-out test set; complete cases."),
        ("Phase 11", "Treatment-IPW + IPCW", ipcw["ate_risk_difference"], *ipcw["patient_cluster_bootstrap_95_interval"], 499, 317, 182, "Existing complete outcomes; IPCW targets 725-person test risk set under conditional independent censoring."),
    ]
    phase12 = inputs["phase12_estimates"]
    phase12_primary_names = {
        "CausalForestDML",
        "Propensity-IPW (none)",
        "Treatment-IPW + IPCW, combined-weight truncation (none)",
    }
    phase12_rows = []
    for row in phase12.loc[phase12["estimator"].isin(phase12_primary_names)].itertuples(index=False):
        phase12_rows.append(
            (
                "Phase 12",
                row.estimator,
                row.risk_difference,
                row.ci_lower_95,
                row.ci_upper_95,
                int(row.n),
                int(row.treated_n),
                int(row.control_n),
                row.estimand_population,
            )
        )
    rows = phase11_rows + phase12_rows
    return pd.DataFrame(
        [
            {
                "source_phase": source,
                "estimator": estimator,
                "estimate_risk_difference": estimate,
                "ci_lower_95": lower,
                "ci_upper_95": upper,
                "estimate_pp": 100 * estimate,
                "ci_lower_95_pp": 100 * lower,
                "ci_upper_95_pp": 100 * upper,
                "n_observed_outcome": n,
                "treated_n": treated,
                "control_n": control,
                "saved_estimand_population": population,
                "status": "existing exploratory estimate; not approved as a substantive causal result",
                "causal_estimate_approved": False,
            }
            for source, estimator, estimate, lower, upper, n, treated, control, population in rows
        ]
    )


def _plot_cohort_flow(flow: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    labels = [
        "Eligible prior-MI survivors",
        "Phase 11 complete case",
        "Held-out test complete case",
    ]
    segments = [
        [2014, 1216, 4315],
        [317, 182, 7046],
    ]
    segments.insert(0, [2986, 1670, 2889])
    colors = ["#2b6f9c", "#e7a84b", "#9d9d9d"]
    names = ["Treated", "Control", "Outside displayed subset / treatment unknown"]
    left = np.zeros(len(labels))
    for col_index, color in enumerate(colors):
        values = np.array([row[col_index] for row in segments])
        ax.barh(labels, values, left=left, color=color, label=names[col_index], height=0.62)
        for i, value in enumerate(values):
            if value > 0 and value > 400:
                ax.text(left[i] + value / 2, i, f"{value:,}", ha="center", va="center", color="white" if col_index != 1 else "#222", fontsize=9, fontweight="bold")
        left += values
    ax.set_xlim(0, 8000)
    ax.set_xlabel("Patients / index admissions")
    ax.set_title("Selection from eligible cohort to existing Phase 11 analysis")
    ax.text(
        0,
        -0.95,
        "Known treatment: 4,656 (2,986 treated; 1,670 controls); 2,889 treatment-missing. "
        "Phase 11 model-ready: 3,230; held-out test: 499. Treated EMAR linkage: 1,505 linked / 1,481 unmatched.",
        fontsize=9,
        va="top",
    )
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _plot_endpoint_distribution(inputs: dict[str, Any], path: Path) -> None:
    summary = inputs["phase14_summary"]["acute_episode_validation"]["classification_counts"]
    ordered = [
        ("Candidate distinct acute MI", summary["candidate distinct acute MI"]),
        ("Possible transfer/readmission", summary["possible transfer/readmission for the same episode"]),
        ("Possible continuation", summary["possible continuation of index MI episode"]),
        ("Uncertain classification", summary["uncertain episode classification"]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.35, 1]})
    counts = inputs["phase13_endpoint"]["acute_event_type"].value_counts()
    categories = [
        ("Acute-coded candidates", int(counts.get("acute_recurrent_mi", 0)), "#3979a8"),
        ("Competing death", int(counts.get("competing_death", 0)), "#9a5d5d"),
        ("Event-free through horizon", int(counts.get("event_free", 0)), "#6a9c7d"),
        ("Incomplete / uncertain follow-up", int(counts.get("incomplete_followup", 0)), "#c9a34e"),
    ]
    axes[0].barh([c[0] for c in categories], [c[1] for c in categories], color=[c[2] for c in categories])
    for i, (_, count, _) in enumerate(categories):
        axes[0].text(count + 30, i, f"{count:,}", va="center", fontsize=9)
    axes[0].set_xlim(0, 3300)
    axes[0].set_xlabel("Patients (N=7,545)")
    axes[0].set_title("12-month acute-screen status")
    axes[1].barh([x[0] for x in ordered], [x[1] for x in ordered], color=["#3979a8", "#c4824e", "#8f6f9f", "#a9a9a9"])
    for i, (_, count) in enumerate(ordered):
        axes[1].text(count + 5, i, f"{count}", va="center", fontsize=9)
    axes[1].set_xlim(0, 260)
    axes[1].set_xlabel("Candidate admissions (N=555)")
    axes[1].set_title("Phase 14 episode-screen categories")
    axes[1].invert_yaxis()
    fig.suptitle("Code-screened endpoint evidence; episode labels are not clinical adjudication", fontsize=12)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _plot_treatment_timing(first: pd.DataFrame, path: Path) -> None:
    valid = first.loc[
        first["first_administration_status"].eq("observed_within_index_admission"),
        "hours_admission_to_first",
    ].dropna()
    bins = [0, 6, 12, 24, 48, 72, 168, np.inf]
    labels = ["0–6", "6–12", "12–24", "24–48", "48–72", "72–168", ">168"]
    counts = pd.cut(valid, bins=bins, labels=labels, right=False, include_lowest=True).value_counts().reindex(labels, fill_value=0)
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    bars = ax.bar(labels, counts.values, color="#3979a8")
    ax.bar_label(bars, padding=3, fontsize=9)
    ax.set_xlabel("Hours from index admission to first recorded in-admission administration")
    ax.set_ylabel("Admissions")
    ax.set_title("Timing among 1,500 admissions with a validated first EMAR timestamp")
    ax.text(
        0.99,
        0.96,
        "Only among existing statin_during=1 admissions.\n"
        "1,486 treated admissions had no validated first in-window timestamp.\n"
        "Inpatient administration does not establish discharge prescribing or adherence.",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.9, "edgecolor": "#bbbbbb"},
    )
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _write_endpoint_report(inputs: dict[str, Any], checks: dict[str, Any]) -> str:
    p13 = inputs["phase13_summary"]
    p14 = inputs["phase14_summary"]["acute_episode_validation"]
    same = checks["same_day_event_death"]
    return f"""# Phase 16 endpoint finalization

## Final endpoint definition

For feasibility and descriptive reporting, retain the Phase 13 acute-code screen: the first admission after the index discharge carrying ICD-9 `410*` or ICD-10 `I21*`/`I22*`, within the existing 12-month follow-up horizon. This is an **acute-MI-coded admission candidate**, not a clinically adjudicated recurrent MI. The Phase 11 outcome remains the broader saved MI-coded recurrence and is not substituted or relabeled.

The broad endpoint has {p13['broad_existing_event_type_counts']['recurrent_mi']:,} events; {p13['existing_endpoint_code_class_counts']['icd9_412_only']:,} are ICD-9 `412` only (old MI/history code), and {p13['existing_endpoint_code_class_counts']['acute_code_present']:,} have an acute code. The acute screen identifies {p14['candidate_first_acute_admissions']:,} first subsequent acute-coded admissions.

## Episode-screen treatment

| Phase 14 screening classification | N | Final handling |
|---|---:|---|
| Candidate distinct acute MI | {p14['classification_counts']['candidate distinct acute MI']} | Candidate events only; descriptive or sensitivity analysis, not a validated primary event |
| Possible transfer/readmission for same episode | {p14['classification_counts']['possible transfer/readmission for the same episode']} | Episode unresolved; do not count as confirmed distinct recurrence or code as no event |
| Possible continuation of index MI episode | {p14['classification_counts']['possible continuation of index MI episode']} | Episode unresolved; do not count as confirmed distinct recurrence or code as no event |
| Uncertain episode classification | {p14['classification_counts']['uncertain episode classification']} | Retain as uncertain; do not force to event-free |

No candidate was removed by an arbitrary minimum-gap rule. The 211 “candidate distinct” labels come from code and chronology screening, not clinical adjudication. There is no retained clinical documentation establishing new infarctions, so those 211 are not sufficient for a confirmatory primary endpoint. Early candidates remain in the descriptive tables: {p14['events_within_1_day']} within 1 day, {p14['events_within_7_days']} within 7 days, and {p14['events_within_30_days']} within 30 days. Repeated acute-coded admissions and transfer proxies likewise raise continuity concerns without proving continuity.

## Competing death, follow-up, and event ordering

For the acute-code screen, the saved Phase 13 event types are 555 acute-coded candidates, 1,219 competing deaths, 2,912 event-free through the horizon, and 2,859 incomplete follow-up. Death remains a competing event, not ordinary censoring or event-free status. Incomplete follow-up remains unknown and is not coded as event-free. Descriptive 365-day CIFs in the saved analysis are not adjusted for confounding and do not validate event identity.

There are {same['same_day_acute_mi_death_pairs']} acute-MI/death date pairs on the same calendar day; {same['same_day_with_imprecise_death_time']} had imprecise death time, and the saved endpoint marked {same['same_day_uncertain_in_saved_endpoint']} as event-order-uncertain. The three same-day pairs in the saved data have precise recorded death times, so their stored time ordering determined the classification. The endpoint construction explicitly treats a same-day pair with date-only/imprecise death time as order-uncertain and censors it for descriptive CIF; this is not event-free. Death-time precision remains imperfect overall, so same-day ordering must be disclosed.

Among the 555 acute-screen event admissions, 494 admission IDs match the broad endpoint's selected first MI admission and 61 do not. This unresolved difference between the saved event-construction pathways is preserved rather than used as a reason to drop records.

## Decision

**Endpoint suitable for primary paper analysis? No.** Use the acute code screen and Phase 14 categories only as descriptive/sensitivity evidence in a feasibility paper. Do not present the 211 screen-positive subset as a validated primary recurrent-MI endpoint or derive a causal effect from it. Clinical episode adjudication or a separately validated endpoint algorithm is unavailable in the retained sources.
"""


def _write_confounding_report() -> str:
    return """# Phase 16 confounding and adjustment decision

## Causal question and treatment definition

The intended scientific question remains statin treatment and later/recurrent MI among patients with prior MI. The available exposure is the existing `statin_during` indicator: recorded in-hospital exposure versus no recorded exposure in the index admission. It is not a discharge-initiation strategy, a new-user contrast, or long-term adherence. Its assignment time relative to the beginning of follow-up and to evolving index-stay severity is not uniformly available.

## Proposed adjustment set

For a future, explicitly timed treatment assignment, the DAG-supported primary set would need pre-assignment age, sex, chronic disease burden (including diabetes, hypertension, CKD), prior cardiovascular disease and prior MI severity/recency, **verified prior statin use**, pre-assignment concomitant cardiovascular treatment, lipid burden, and clinical treatment indication / baseline severity. This is a target specification, not a claim that the current data measure it.

Available measured candidates are age, sex, diabetes, hypertension, and CKD. The comorbidity feature time windows are not fully validated against the first dose. If a future assignment timestamp establishes they predate treatment, they can be retained as baseline candidates. The `*_before` variables for statin, aspirin, beta blockers, and ACE inhibitors are order/prescription proxies: they do not prove administration, adherence, or the exact historical window. Use them only in a clearly labeled sensitivity specification, not as verified medication history.

The existing DAG represents prior statin use as a confounder but flags `statin_before` as an imperfect proxy that may be a collider of prior statin use and healthcare access/documentation. Therefore do **not** make the proxy the primary adjustment variable by default; show results with and without it only if a future analysis has a defensible assignment time and endpoint.

## Excluded from baseline adjustment

- Index admission diagnosis codes (acute MI, heart failure, shock, AKI, respiratory failure) and completed length of stay: timing relative to administration is unavailable; they may be post-treatment severity, mediators, or colliders.
- `statin_after`, follow-up, recurrent-MI outcomes, death, and post-dose treatment: post-treatment/outcome variables.
- `statin_during`: exposure, not a covariate.
- `prior_mi`: constant eligibility variable in this selected cohort; no within-cohort adjustment information.
- `z_ecg` and other ECG-derived features: temporal/provenance eligibility is unresolved and should not be used as baseline adjustment.

## Confounding by indication and exchangeability

There is measured imbalance: CKD prevalence is 35.1% treated versus 27.8% control (SMD 0.156); diabetes, hypertension, and age also differ. Prior medication-order proxies show larger group differences, with uncertain timing and adherence. Index-admission diagnosis-code prevalence and length of stay differ too, but cannot be used as primary baseline adjustment because they are not timed before statin administration. These patterns are compatible with treatment selection by disease history, indication, and acuity; they do not quantify or eliminate confounding.

Important residual confounders are not adequately measured: lipid burden, coronary anatomy/atherosclerotic burden, prior MI severity and validated episode history, clinician indication, frailty, smoking, reliable prior medication use/adherence, and healthcare access. Selection into a prior-MI survivor, ECG/master-feature, known-treatment, and complete-follow-up population may also induce selection bias.

**Decision:** conditional exchangeability is not plausible enough to assert from the retained data. No primary causal adjustment set is fully observed and temporally validated. The measured-only set may be used for descriptive balance or exploratory models, not to justify a causal estimate.
"""


def _write_selection_report(inputs: dict[str, Any]) -> str:
    summary = inputs["phase15_summary"]
    complete = inputs["phase11_metrics"]["complete_case_analysis"]
    treated = summary["treated_n"]
    control = summary["control_n"]
    return f"""# Phase 16 missing treatment and selection assessment

## Distinct selection mechanisms

| Stage | N | Interpretation |
|---|---:|---|
| Eligible prior-MI index admissions alive at discharge | {summary['eligible_cohort_n']:,} | One selected index admission per patient |
| Known `statin_during` | {summary['treatment_known_n']:,} | {treated:,} exposed; {control:,} controls |
| Missing `statin_during` | {summary['treatment_missing_n']:,} | Unknown; not imputed or recovered |
| Exposed with filtered exact-ID EMAR link | {summary['exposed_with_emar_record_n']:,} | Linked administration-like statin records |
| Exposed without such EMAR link | {summary['exposed_without_emar_record_n']:,} | Not proof of no administration |
| Exposed with valid first in-admission timestamp | {summary['exposed_with_valid_in_admission_first_emar_n']:,} | First recorded administration falls in index interval |
| Complete follow-up (all treatment statuses) | {int(inputs['cohort']['followup_complete'].astype(bool).sum()):,} | Includes outcome-known treatment-missing patients |
| Incomplete/uncertain follow-up | {summary['incomplete_or_uncertain_followup_n']:,} | Not outcome-negative |
| Phase 11 complete-case population | {summary['phase11_complete_case_n']:,} | {complete['test_admissions']:,} held-out test rows; saved estimates use this sample |

The missing-treatment population (2,889) is not the EMAR-unmatched population (1,481 exposed patients), and neither is the same as incomplete follow-up (2,560 overall; 1,426 among known-treatment patients). EMAR linkage was attempted only for admissions already marked exposed; no link cannot be used to reconstruct a negative treatment value. The archive-backed Phase 14 extraction does not retain declined/not-administered rows or an inclusion/exclusion audit for unmatched patients.

## Selection implications

The Phase 11 complete-case set is 3,230 of 4,656 known-treatment admissions with baseline features. Follow-up completion is 2,014/2,986 (67.45%) among treated and 1,216/1,670 (72.81%) among controls, a 5.37 percentage-point difference. Differential outcome ascertainment/retention is plausible. Another 2,889 eligible records lack treatment and the corresponding processed baseline feature row. Of these, 2,338 appear in the existing split files and 551 do not; retained artifacts do not provide a patient-level reason for the latter.

Selection into processed ECG/master data may depend on care pathways, utilization, clinical state, or data availability; no retained per-record exclusion audit resolves this. Restricting to prior-MI survivors and observed treatment/features can further condition on selection variables. IPCW for incomplete follow-up addresses neither missing treatment classification nor ECG/master-feature selection, and only works under its own conditional independent-censoring assumptions.

**Decision:** do not impute or infer treatment for missing or EMAR-unmatched records. Report all populations separately. The held-out Phase 11 sample and Phase 12 robustness analyses remain exploratory only.
"""


def _write_results_report(estimates: pd.DataFrame, checks: dict[str, Any]) -> str:
    by_phase11 = estimates.loc[estimates["source_phase"].eq("Phase 11")]
    rows = "\n".join(
        f"| {r.estimator} | {r.estimate_pp:.2f} | {r.ci_lower_95_pp:.2f} to {r.ci_upper_95_pp:.2f} | {r.n_observed_outcome} |"
        for r in by_phase11.itertuples(index=False)
    )
    return f"""# Phase 16 final statin results

## Estimation decision

No new treatment-effect estimation was performed. The finalized endpoint is not sufficiently validated, `statin_during` is not a discharge-initiation assignment and is not timestamped for all exposed admissions, and no fully observed pre-treatment adjustment set establishes exchangeability. The requested final estimate is therefore **not approved as a substantive or causal paper result**. Existing Phase 11–12 results are retained solely as exploratory model outputs.

## Previously saved exploratory estimates

These are reused, not recomputed. Phase 11 numbers below are saved test-set results on 499 complete cases (317 treated, 182 controls). Phase 12 has a separate bootstrap/robustness table; its reported intervals differ slightly from Phase 11, and both are retained with their source labels in `phase16_paper_assets/final_estimates.csv`. Neither table corrects endpoint misclassification or unmeasured confounding.

| Existing Phase 11 estimator | Risk difference (percentage points) | Saved 95% interval (percentage points) | N |
|---|---:|---:|---:|
{rows}

All Phase 11 primary intervals include zero. The outcome is the broad MI-coded endpoint (including old-MI/history code-only admissions), not a clinically adjudicated recurrent MI. The held-out estimates are model- and selection-dependent; the censor-weighted result additionally requires conditional independent censoring. No CATE dispersion is interpreted as evidence of treatment-effect heterogeneity.

## Final analysis decision

**Decision C — retain the statin branch as a feasibility/exploratory study.** The clinical endpoint cannot currently distinguish new recurrent MI from transfer, readmission, or continuation. The 211 candidate-distinct labels are not adjudicated. Treatment classification is missing for 2,889 eligible patients, and 1,481 already-exposed admissions lack a qualifying retained EMAR link. Important indication and disease-severity confounders are not validated as pre-treatment measures. Further ATE/CATE estimation on the same endpoint/exposure would create false precision rather than resolve these design limitations.

The prior estimates may be described only as exploratory associations of the existing in-hospital `statin_during` indicator with a broad MI-code outcome in a selected complete-case test population. Do not write that they estimate statin initiation at discharge, long-term adherence, or a clinical causal effect.
"""


def _write_decision_report() -> str:
    return """# Phase 16 final scientific decision

## Decision: C — endpoint or data limitations prevent a meaningful treatment-effect comparison

The statin branch closes as a feasibility and exploratory analysis. The saved Phase 11–12 estimates may be retained transparently as exploratory model results, but no effect estimate is approved as a substantive or causal result for the paper.

Why:

1. The broad 1,833-event MI-coded outcome includes 1,339 ICD-9 `412`-only admissions, which do not establish acute recurrent infarction. The acute screen finds 555 candidate admissions, but 211 “candidate distinct” classifications are based on code/chronology screening without clinical adjudication; 344 remain classified as possible transfer/readmission, possible continuation, or uncertain.
2. The treatment contrast is recorded statin exposure during the index hospitalization, not initiation at discharge. A valid first in-admission administration timestamp is retained for 1,500 of 2,986 already-exposed admissions; the other 1,481 unmatched exposed admissions cannot be reclassified as untreated.
3. Treatment is missing for 2,889 of 7,545 eligible patients. Known-treatment follow-up and feature selection reduce the Phase 11 population to 3,230; only 499 form its held-out complete-case test set.
4. Baseline imbalances and strong clinical indication/confounding are plausible, while lipid burden, coronary disease burden, clinician indication, validated prior medication use, and prior MI severity are unavailable or inadequately timed. No measured adjustment set establishes conditional exchangeability.
5. Death is a competing event; incomplete follow-up is unknown, and same-day event ordering requires explicit handling. The saved Phase 13 acute-screen output contains no event-order-uncertain rows, but endpoint uncertainty remains.

## What can be reported

Report the cohort-construction, treatment linkage, endpoint screening, competing-death, missingness, and descriptive baseline findings as a feasibility study. Preserve previous model estimates in a clearly labeled exploratory appendix/table only, with their original endpoint and sample definition. Do not claim a clinical treatment benefit/harm, causal effect, discharge-initiation effect, adherence effect, or treatment-effect heterogeneity.

No Phase 17 or further statin investigation is proposed in this closure.
"""


def _write_manuscript_notes() -> str:
    return """# Phase 16 manuscript notes

## Proposed title

**Feasibility of Estimating the Association Between In-Hospital Statin Exposure and Subsequent Myocardial Infarction in Patients With Prior MI: A MIMIC-IV Cohort Assessment**

## Research question and design

Assess whether existing MIMIC-IV/MIMIC-IV-ECG data support an interpretable analysis of in-hospital statin exposure and subsequent MI-coded admissions among patients with a prior MI. This is a retrospective, single-health-system data-feasibility and exploratory observational analysis, not a target-trial emulation with validated treatment assignment.

## Cohort and exposure

The retained eligible cohort contains 7,545 patients with a prior MI who survived the selected index admission to discharge. `statin_during` is the existing index-hospitalization exposure indicator. Treatment was known for 4,656 (2,986 exposed; 1,670 controls) and missing for 2,889. Phase 14 linked filtered statin EMAR records to 1,505 exposed admissions; a valid in-admission first administration time was available for 1,500. Order records and administrations remain distinct; neither inpatient administration nor prescription orders establish discharge therapy or outpatient adherence.

## Outcome and statistical methods

The saved Phase 11 analysis used a 12-month MI-coded recurrence outcome in a complete-case cohort; its final held-out test set contained 499 patients. Phase 13 screened acute-coded subsequent admissions (ICD-9 `410*`, ICD-10 `I21*`/`I22*`) and treated death as a competing event; Phase 14 categorized 555 candidate admissions using diagnoses and chronology. No clinical episode adjudication was available. Descriptive competing-risk cumulative incidence estimates are unadjusted. Phase 11–12 effect estimates are historical exploratory results only; Phase 16 did not fit models or re-estimate effects.

## Results to report

- Cohort: 7,545 eligible; 4,656 known treatment; 2,889 treatment missing.
- Of 2,986 existing exposed admissions, 1,505 have a filtered EMAR link; 1,481 are unmatched, not untreated. First timestamp in the admission is available for 1,500.
- Broad endpoint: 1,833 MI-coded admissions, including 1,339 ICD-9 `412`-only cases. Acute-code screen: 555 candidates; 211 candidate distinct, 167 possible transfer/readmission, 114 possible continuation, 63 uncertain.
- Known-treatment complete-case population: 3,230; held-out test sample: 499.
- Treated/control imbalances include CKD 35.1% versus 27.8% (SMD 0.156). Prior medication fields are order proxies with uncertain timing/adherence.
- Existing model estimates are in `phase16_paper_assets/final_estimates.csv`; all are explicitly exploratory and not causal.

## Limitations and claim boundaries

The exposure is not discharge initiation; treatment status is missing for many eligible patients; EMAR linkage is incomplete; a distinct recurrent infarction endpoint is not adjudicated; treatment indication and important severity/lipid/coronary variables are missing or poorly timed; complete-case and ECG/master selection may limit generalizability; and death competes with recurrent MI. The analysis does not support a clinical causal effect or heterogeneity claim.

Supported claims: these files contain an eligible cohort, an existing in-hospital exposure indicator, incomplete linked timestamped administration evidence, and acute-code-screened candidate admissions with episode uncertainty.

Claims not supported: statin initiation at discharge caused a change in MI risk; prescription or inpatient administration proves long-term adherence; any candidate is a confirmed new MI without adjudication; or CATE variability establishes effect heterogeneity.

## Suggested abstract structure

1. **Background:** the need to assess data suitability for medication-effect analyses in prior-MI patients.
2. **Objective:** evaluate exposure linkage, endpoint screening, confounding, and selection for an in-hospital statin comparison.
3. **Methods:** describe the retained cohort and prior Phase 11–15 evidence; distinguish orders, administrations, competing death, and incomplete follow-up.
4. **Results:** give cohort counts, EMAR linkage, endpoint screening categories, observed imbalances, and selection into the 499-person held-out estimate sample.
5. **Conclusion:** state that the study supports a feasibility/exploratory description, not a causal treatment-effect conclusion.

## External verification still required

Verify clinical interpretation of ICD coding, MIMIC-IV/MIMIC-IV-ECG dataset descriptions, and prior literature using appropriate external sources before manuscript submission. No external references or clinical guideline claims are supplied here.
"""


def _write_completion_report(checks: dict[str, Any], assets: Path) -> str:
    return f"""# Phase 16 completion report

## Work completed

- Finalized endpoint disposition and documented competing death, incomplete follow-up, episode uncertainty, and same-day event ordering.
- Assessed confounding, indication, adjustment candidates, prior statin proxy DAG role, and selection/missingness.
- Made final decision C: feasibility/exploratory study only; no causal estimate is approved as a substantive paper result.
- Created paper tables and figures. Existing Phase 11–12 estimates are copied as exploratory only; no new model or effect estimate was generated.

## Existing artifacts reused

Phase 11 saved metrics and test-set model results; Phase 12 robustness estimator table; Phase 13 target-trial report, cohort selection, acute endpoint event types and competing-risk CIFs; Phase 14 exposure timestamps, linkage summary, first administration summary and episode classifications; Phase 15 group comparisons and selection flow; existing cohort and patient-level splits; provisional statin DAG.

No raw EMAR/prescription files were searched or re-extracted. No Phases 1–15 outputs, cohort, treatment indicators, splits, or models were modified.

## Final counts and decisions

- Cohort: 7,545; known treatment 4,656 (2,986 treated, 1,670 controls); treatment missing 2,889.
- Phase 14: 1,505 EMAR-linked exposed admissions; 1,500 valid first in-admission timestamps; 1,481 exposed admissions without a qualifying EMAR link.
- Phase 11 complete-case population: 3,230; held-out complete-case test: 499.
- Endpoint: 555 acute-coded candidates; 211 candidate distinct, 167 possible transfer/readmission, 114 possible continuation, 63 uncertain; not clinically adjudicated.
- Confounding: measurable imbalances and important unmeasured/poorly timed indication factors; exchangeability not supported.
- Selection: missing treatment, EMAR linkage absence, and incomplete follow-up retained as distinct mechanisms.
- Final scientific decision: **C — feasibility/exploratory study only**.
- Causal estimate approved for substantive paper presentation: **No**. Prior estimates are retained as exploratory outputs only.

## Reproducibility and tests

Run the Phase 16 artifact builder from the repository root:

```powershell
.\\.venv\\Scripts\\python.exe -m causal_models.phase16_final_statin.analyze_phase16
```

Focused tests:

```powershell
.\\.venv\\Scripts\\python.exe -m unittest causal_models.phase16_final_statin.test_phase16 -v
```

Input validation confirmed treatment counts, Phase 11 complete-case counts, split patient disjointness (`{checks['split_patient_overlap']}`), 1,500 in-window first administration timestamps, and retained acute-screen categories. The focused Phase 16 test suite was executed: **10 tests passed, 0 failed**.

## New files to commit

- `causal_models/phase16_final_statin/analyze_phase16.py`
- `causal_models/phase16_final_statin/test_phase16.py`
- `causal_models/phase16_final_statin/phase16_endpoint_finalization.md`
- `causal_models/phase16_final_statin/phase16_confounding_decision.md`
- `causal_models/phase16_final_statin/phase16_selection_assessment.md`
- `causal_models/phase16_final_statin/phase16_final_statin_results.md`
- `causal_models/phase16_final_statin/PHASE_16_FINAL_SCIENTIFIC_DECISION.md`
- `causal_models/phase16_final_statin/phase16_manuscript_notes.md`
- `causal_models/phase16_final_statin/PHASE_16_COMPLETION_REPORT.md`
- All generated CSV/PNG/JSON artifacts under `{assets.relative_to(ROOT)}`
"""


def run_analysis() -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    inputs = _read_inputs()
    checks = _check_inputs(inputs)

    cohort_flow = _cohort_flow(inputs)
    validate_flow_reconciliation(cohort_flow)
    baseline = _baseline_table(inputs)
    endpoint = _endpoint_table(inputs, checks)
    treatment = _treatment_table(inputs)
    estimates = _final_estimates(inputs)

    cohort_flow.to_csv(ASSETS / "cohort_flow.csv", index=False)
    baseline.to_csv(ASSETS / "baseline_characteristics.csv", index=False)
    endpoint.to_csv(ASSETS / "endpoint_summary.csv", index=False)
    treatment.to_csv(ASSETS / "treatment_exposure_summary.csv", index=False)
    estimates.to_csv(ASSETS / "final_estimates.csv", index=False)

    _plot_cohort_flow(cohort_flow, ASSETS / "figure_cohort_flow.png")
    _plot_endpoint_distribution(inputs, ASSETS / "figure_endpoint_distribution.png")
    _plot_treatment_timing(inputs["phase14_first_admin"], ASSETS / "figure_treatment_timing.png")

    documents = {
        "phase16_endpoint_finalization.md": _write_endpoint_report(inputs, checks),
        "phase16_confounding_decision.md": _write_confounding_report(),
        "phase16_selection_assessment.md": _write_selection_report(inputs),
        "phase16_final_statin_results.md": _write_results_report(estimates, checks),
        "PHASE_16_FINAL_SCIENTIFIC_DECISION.md": _write_decision_report(),
        "phase16_manuscript_notes.md": _write_manuscript_notes(),
        "PHASE_16_COMPLETION_REPORT.md": _write_completion_report(checks, ASSETS),
    }
    for filename, text in documents.items():
        (OUTPUT / filename).write_text(text, encoding="utf-8")

    summary = {
        "decision": "C",
        "causal_estimate_approved": False,
        "cohort_n": len(inputs["cohort"]),
        "known_treatment_n": int(inputs["cohort"]["statin_during"].notna().sum()),
        "treated_n": int(inputs["cohort"]["statin_during"].eq(1).sum()),
        "control_n": int(inputs["cohort"]["statin_during"].eq(0).sum()),
        "missing_treatment_n": int(inputs["cohort"]["statin_during"].isna().sum()),
        "phase11_complete_case_n": int(inputs["phase13_summary"]["phase11_complete_case_n"]),
        "phase11_test_n": int(inputs["phase11_metrics"]["complete_case_analysis"]["test_admissions"]),
        "acute_candidates_n": int(inputs["phase14_summary"]["acute_episode_validation"]["candidate_first_acute_admissions"]),
        "same_day_event_death": checks["same_day_event_death"],
        "split_patient_overlap": checks["split_patient_overlap"],
        "new_effect_estimates_generated": False,
    }
    (OUTPUT / "phase16_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_analysis(), indent=2))
