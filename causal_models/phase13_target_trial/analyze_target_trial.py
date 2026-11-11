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
COHORT_PATH = ROOT / "causal_models" / "data" / "statin_recurrent_mi_cohort.parquet"
MI_ADMISSIONS_PATH = ROOT / "longitudinal" / "longitudinal" / "mi_admissions.parquet"
DIAGNOSES_PATH = ROOT / "longitudinal" / "longitudinal" / "diagnoses_mi_codes.parquet"
SPLIT_DIR = ROOT / "causal_models" / "data" / "statin_recurrent_mi_forest_splits"
OUTPUT_DIR = Path(__file__).resolve().parent
BASELINE_FEATURES = [
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
CAUSES = ("acute_recurrent_mi", "competing_death")


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


def _as_timestamp(value: Any) -> pd.Timestamp | pd.NaT:
    if pd.isna(value):
        return pd.NaT
    return pd.Timestamp(value)


def classify_acute_endpoint(
    index_discharge: Any,
    horizon_end: Any,
    observation_end: Any,
    death_date: Any,
    death_time_is_precise: bool,
    acute_events: pd.DataFrame,
) -> dict[str, Any]:
    """Classify the earliest observed acute-coded event, death, or censoring."""
    origin = _as_timestamp(index_discharge)
    horizon = _as_timestamp(horizon_end)
    observation = _as_timestamp(observation_end)
    death = _as_timestamp(death_date)
    if pd.isna(origin) or pd.isna(horizon):
        raise ValueError("Index discharge and follow-up horizon are required")

    candidates = acute_events.copy()
    if not candidates.empty:
        candidates["admittime"] = pd.to_datetime(candidates["admittime"])
        candidates = candidates.loc[
            candidates["admittime"].gt(origin)
            & candidates["admittime"].le(horizon)
        ]
        if pd.notna(observation):
            observation_is_date_only = observation == observation.normalize()
            observed_by_end = (
                candidates["admittime"].dt.normalize().le(observation.normalize())
                if observation_is_date_only
                else candidates["admittime"].le(observation)
            )
            candidates = candidates.loc[observed_by_end]
        candidates = candidates.sort_values(["admittime", "hadm_id"])
    first = None if candidates.empty else candidates.iloc[0]
    mi_time = pd.NaT if first is None else pd.Timestamp(first["admittime"])
    death_in_window = pd.notna(death) and origin < death <= horizon

    event_type = "incomplete_followup"
    if pd.notna(mi_time) and death_in_window:
        same_day = mi_time.normalize() == death.normalize()
        if same_day and not death_time_is_precise:
            event_type = "event_order_uncertain"
        elif death < mi_time:
            event_type = "competing_death"
        else:
            event_type = "acute_recurrent_mi"
    elif pd.notna(mi_time):
        event_type = "acute_recurrent_mi"
    elif death_in_window:
        event_type = "competing_death"
    elif pd.notna(observation) and observation >= horizon:
        event_type = "event_free"

    if event_type == "acute_recurrent_mi":
        end_time = mi_time
    elif event_type == "competing_death":
        end_time = death
    elif event_type == "event_free":
        end_time = horizon
    elif event_type == "event_order_uncertain":
        end_time = min(mi_time, death)
    else:
        end_time = observation if pd.notna(observation) else origin
        end_time = max(origin, min(end_time, horizon))
    duration = max(0.0, (end_time - origin).total_seconds() / 86400)
    return {
        "acute_recurrent_mi": (
            1
            if event_type == "acute_recurrent_mi"
            else 0
            if event_type in ("event_free", "competing_death")
            else pd.NA
        ),
        "acute_first_hadm_id": None if first is None else first["hadm_id"],
        "acute_first_admittime": mi_time,
        "acute_event_type": event_type,
        "acute_followup_end_date": end_time,
        "acute_followup_days": duration,
    }


def cumulative_incidence(
    frame: pd.DataFrame,
    horizons: tuple[int, ...] = (30, 90, 180, 365),
) -> list[dict[str, Any]]:
    """Aalen-Johansen descriptive CIFs with incomplete/uncertain rows censored."""
    required = {"duration_days", "event_type"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(frame.columns))}")
    usable = frame.loc[
        frame["duration_days"].notna()
        & frame["duration_days"].ge(0)
        & frame["event_type"].isin((*CAUSES, "event_free", "incomplete_followup", "event_order_uncertain"))
    ].copy()
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        survival = 1.0
        cif = {cause: 0.0 for cause in CAUSES}
        event_times = np.sort(
            usable.loc[usable["event_type"].isin(CAUSES), "duration_days"].unique()
        )
        for event_time in event_times[event_times <= horizon]:
            at_risk = int((usable["duration_days"] >= event_time).sum())
            at_time = usable.loc[usable["duration_days"].eq(event_time), "event_type"]
            if at_risk == 0:
                continue
            counts = {cause: int(at_time.eq(cause).sum()) for cause in CAUSES}
            for cause in CAUSES:
                cif[cause] += survival * counts[cause] / at_risk
            survival *= 1.0 - sum(counts.values()) / at_risk
        rows.append(
            {
                "horizon_days": horizon,
                "n": len(usable),
                "input_n": len(frame),
                "excluded_n": len(frame) - len(usable),
                "acute_mi_cif": cif["acute_recurrent_mi"],
                "death_cif": cif["competing_death"],
            }
        )
    return rows


def _cohort_flow(cohort: pd.DataFrame, split_ids: set[tuple[int, int]]) -> pd.DataFrame:
    treatment_known = cohort["statin_during"].notna()
    baseline_complete = cohort[BASELINE_FEATURES].notna().all(axis=1)
    model_rows = pd.Series(
        [(int(s), int(h)) in split_ids for s, h in zip(cohort.subject_id, cohort.hadm_id)],
        index=cohort.index,
    )
    endpoint_observed = cohort["recurrent_mi"].notna()
    complete_followup = cohort["followup_complete"].fillna(False).astype(bool)
    final = treatment_known & baseline_complete & endpoint_observed & model_rows
    steps = [
        ("eligible_prior_mi_survived_index_discharge", pd.Series(True, index=cohort.index)),
        ("known_statin_during", treatment_known),
        ("baseline_covariates_available", baseline_complete),
        ("complete_followup", complete_followup),
        ("existing_phase11_estimation_population", final),
    ]
    output = []
    for step, mask in steps:
        for arm, arm_mask in (
            ("all", pd.Series(True, index=cohort.index)),
            ("treated", cohort["statin_during"].eq(1).fillna(False)),
            ("control", cohort["statin_during"].eq(0).fillna(False)),
            ("treatment_missing", cohort["statin_during"].isna()),
        ):
            output.append(
                {
                    "selection_step": step,
                    "treatment_group": arm,
                    "n": int((mask & arm_mask).sum()),
                    "denominator_n": int(arm_mask.sum()),
                }
            )
    return pd.DataFrame(output)


def _event_tables(
    cohort: pd.DataFrame, diagnoses: pd.DataFrame, mi_admissions: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    diagnosis = diagnoses.copy()
    diagnosis["acute_code"] = [
        is_acute_mi_code(code, version)
        for code, version in zip(diagnosis["icd_code"], diagnosis["icd_version"])
    ]
    mi_ids = set(mi_admissions["hadm_id"].astype("int64"))
    mi_diagnoses = diagnosis.loc[diagnosis["hadm_id"].isin(mi_ids)].copy()
    acute_codes = mi_diagnoses.loc[mi_diagnoses["acute_code"]].copy()
    grouped = (
        acute_codes.groupby(["subject_id", "hadm_id"], as_index=False)
        .agg(
            acute_codes=("icd_code", lambda values: ";".join(sorted(set(map(str, values))))),
            admittime=("admittime", "min"),
        )
    )
    grouped_all_codes = (
        mi_diagnoses.groupby(["subject_id", "hadm_id"], as_index=False)
        .agg(
            all_codes=(
                "icd_code",
                lambda values: ";".join(
                    sorted(set(str(value).upper().replace(".", "") for value in values))
                ),
            )
        )
    )
    event_groups = {sid: group for sid, group in grouped.groupby("subject_id")}

    results = []
    for row in cohort.itertuples(index=False):
        patient_events = event_groups.get(row.subject_id)
        if patient_events is None:
            patient_events = pd.DataFrame(columns=["subject_id", "hadm_id", "acute_codes", "admittime"])
        classified = classify_acute_endpoint(
            row.index_dischtime,
            row.followup_horizon_end,
            row.observation_end,
            row.death_date,
            bool(row.death_time_is_precise),
            patient_events,
        )
        results.append(
            {
                "subject_id": row.subject_id,
                "hadm_id": row.hadm_id,
                "statin_during": row.statin_during,
                "index_dischtime": row.index_dischtime,
                "followup_horizon_end": row.followup_horizon_end,
                "observation_end": row.observation_end,
                "death_date": row.death_date,
                "death_indicator": row.death_indicator,
                "first_subsequent_mi_hadm_id": row.first_subsequent_mi_hadm_id,
                "first_subsequent_mi_admittime": row.first_subsequent_mi_admittime,
                "recurrent_mi": row.recurrent_mi,
                "event_type": row.event_type,
                **classified,
            }
        )
    endpoint = pd.DataFrame(results)
    endpoint["acute_first_codes"] = endpoint["acute_first_hadm_id"].map(
        grouped.set_index("hadm_id")["acute_codes"].to_dict()
    )

    broad_events = cohort.loc[cohort["recurrent_mi"].eq(1)].copy()
    broad_acute_codes = broad_events["first_subsequent_mi_hadm_id"].map(
        grouped.set_index("hadm_id")["acute_codes"].to_dict()
    )
    broad_all_codes = broad_events["first_subsequent_mi_hadm_id"].map(
        grouped_all_codes.set_index("hadm_id")["all_codes"].to_dict()
    )
    broad_events["endpoint_code_class"] = "nonacute_code_only"
    broad_events.loc[broad_all_codes.eq("412"), "endpoint_code_class"] = "icd9_412_only"
    broad_events.loc[broad_acute_codes.notna(), "endpoint_code_class"] = "acute_code_present"
    broad_events["days_from_discharge"] = (
        pd.to_datetime(broad_events["first_subsequent_mi_admittime"])
        - pd.to_datetime(broad_events["index_dischtime"])
    ).dt.total_seconds() / 86400
    code_table = broad_events[
        [
            "subject_id",
            "hadm_id",
            "first_subsequent_mi_hadm_id",
            "first_subsequent_mi_admittime",
            "days_from_discharge",
            "endpoint_code_class",
        ]
    ].copy()
    code_table["acute_codes"] = broad_acute_codes.values
    code_table["all_mi_codes"] = broad_all_codes.values

    broad_timing = broad_events["days_from_discharge"]
    acute_events = endpoint.loc[endpoint["acute_event_type"].eq("acute_recurrent_mi")]
    acute_timing = acute_events["acute_followup_days"]
    summary = []
    for label, series in (
        ("existing_broad_mi_coded_endpoint", broad_timing),
        ("acute_code_only_endpoint", acute_timing),
    ):
        valid = series.dropna()
        summary.append(
            {
                "endpoint": label,
                "n_events": int(len(valid)),
                "median_days": float(valid.median()) if len(valid) else None,
                "p10_days": float(valid.quantile(0.10)) if len(valid) else None,
                "p90_days": float(valid.quantile(0.90)) if len(valid) else None,
                "within_1_day": int(valid.le(1).sum()),
                "within_7_days": int(valid.le(7).sum()),
                "within_30_days": int(valid.le(30).sum()),
            }
        )
    return endpoint, code_table, pd.DataFrame(summary)


def _split_ids() -> set[tuple[int, int]]:
    ids: set[tuple[int, int]] = set()
    for split in ("train", "validation", "test"):
        frame = pd.read_parquet(SPLIT_DIR / f"{split}.parquet")
        ids.update(
            (int(subject), int(admission))
            for subject, admission in zip(frame["SubjectID"], frame["hadm_id"])
        )
    return ids


def _plot_cif(cif: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for axis, outcome, title in (
        (axes[0], "acute_mi_cif", "Acute-code MI"),
        (axes[1], "death_cif", "Competing death"),
    ):
        for group, values in cif.groupby("treatment_group"):
            axis.plot(values["horizon_days"], values[outcome], marker="o", label=group)
        axis.set_title(title)
        axis.set_xlabel("Days since index discharge")
        axis.set_ylabel("Descriptive cumulative incidence")
        axis.set_ylim(bottom=0)
        axis.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def _markdown_table(frame: pd.DataFrame, floatfmt: str = ".2f") -> str:
    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        cells = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                cells.append(format(value, floatfmt))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def run_analysis() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort = pd.read_parquet(COHORT_PATH)
    mi_admissions = pd.read_parquet(MI_ADMISSIONS_PATH)
    diagnoses = pd.read_parquet(DIAGNOSES_PATH)
    endpoint, code_table, timing = _event_tables(cohort, diagnoses, mi_admissions)
    ids = _split_ids()
    flow = _cohort_flow(cohort, ids)

    event_counts = (
        endpoint.groupby(["acute_event_type", "statin_during"], dropna=False)
        .size()
        .rename("n")
        .reset_index()
    )
    event_counts["treatment_group"] = event_counts["statin_during"].map(
        {0: "control", 1: "treated"}
    ).fillna("treatment_missing")
    event_counts = event_counts.drop(columns="statin_during")
    code_counts = code_table.groupby("endpoint_code_class").size().rename("n").reset_index()

    cif_rows = []
    known = endpoint.loc[endpoint["statin_during"].notna()].copy()
    for definition, duration_col, type_col in (
        ("acute_code_only", "acute_followup_days", "acute_event_type"),
        ("existing_broad_mi_code", None, None),
    ):
        for treatment, group in known.groupby("statin_during"):
            if definition == "acute_code_only":
                frame = group[[duration_col, type_col]].rename(
                    columns={duration_col: "duration_days", type_col: "event_type"}
                )
            else:
                broad = cohort.loc[cohort["statin_during"].eq(treatment)].copy()
                broad["duration_days"] = broad["followup_duration_days"]
                broad["event_type"] = broad["event_type"].replace(
                    {"recurrent_mi": "acute_recurrent_mi"}
                )
                frame = broad
            estimates = cumulative_incidence(frame)
            for item in estimates:
                cif_rows.append(
                    {
                        "endpoint_definition": definition,
                        "treatment_group": "treated" if int(treatment) == 1 else "control",
                        **item,
                    }
                )
    cif = pd.DataFrame(cif_rows)
    _plot_cif(cif.loc[cif["endpoint_definition"].eq("acute_code_only")], OUTPUT_DIR / "acute_code_competing_risk_cif.png")

    cohort["treatment_group"] = cohort["statin_during"].map({0: "control", 1: "treated"}).fillna("treatment_missing")
    selection = []
    for group, frame in cohort.groupby("treatment_group", dropna=False):
        n = len(frame)
        selection.append(
            {
                "treatment_group": group,
                "cohort_n": n,
                "treatment_known_n": int(frame["statin_during"].notna().sum()),
                "baseline_complete_n": int(frame[BASELINE_FEATURES].notna().all(axis=1).sum()),
                "complete_followup_n": int(frame["followup_complete"].fillna(False).sum()),
                "followup_complete_percent": float(100 * frame["followup_complete"].fillna(False).mean()) if n else None,
                "assigned_to_existing_split_n": int(
                    frame[["subject_id", "hadm_id"]].apply(
                        lambda r: (int(r.subject_id), int(r.hadm_id)) in ids, axis=1
                    ).sum()
                ),
                "final_complete_case_n": int(
                    (
                        frame["statin_during"].notna()
                        & frame["recurrent_mi"].notna()
                        & frame[BASELINE_FEATURES].notna().all(axis=1)
                        & frame[["subject_id", "hadm_id"]].apply(
                            lambda r: (int(r.subject_id), int(r.hadm_id)) in ids, axis=1
                        )
                    ).sum()
                ),
            }
        )
    selection_frame = pd.DataFrame(selection)

    timing.to_csv(OUTPUT_DIR / "endpoint_timing_summary.csv", index=False)
    event_counts.to_csv(OUTPUT_DIR / "endpoint_event_type_counts.csv", index=False)
    code_counts.to_csv(OUTPUT_DIR / "existing_endpoint_code_class_counts.csv", index=False)
    code_table.to_csv(OUTPUT_DIR / "existing_endpoint_event_codes.csv", index=False)
    endpoint.to_csv(OUTPUT_DIR / "acute_endpoint_by_index_admission.csv", index=False)
    flow.to_csv(OUTPUT_DIR / "cohort_selection_flow.csv", index=False)
    selection_frame.to_csv(OUTPUT_DIR / "cohort_selection_by_treatment.csv", index=False)
    cif.to_csv(OUTPUT_DIR / "competing_risk_cumulative_incidence.csv", index=False)

    broad_counts = cohort["event_type"].value_counts(dropna=False).to_dict()
    acute_counts = endpoint["acute_event_type"].value_counts(dropna=False).to_dict()
    summary = {
        "cohort_n": int(len(cohort)),
        "unique_patients": int(cohort["subject_id"].nunique()),
        "treatment_known_n": int(cohort["statin_during"].notna().sum()),
        "treated_n": int(cohort["statin_during"].eq(1).sum()),
        "control_n": int(cohort["statin_during"].eq(0).sum()),
        "treatment_missing_n": int(cohort["statin_during"].isna().sum()),
        "baseline_complete_known_treatment_n": int(
            (
                cohort["statin_during"].notna()
                & cohort[BASELINE_FEATURES].notna().all(axis=1)
            ).sum()
        ),
        "phase11_complete_case_n": int(
            (
                cohort["statin_during"].notna()
                & cohort["recurrent_mi"].notna()
                & cohort[BASELINE_FEATURES].notna().all(axis=1)
                & cohort[["subject_id", "hadm_id"]].apply(
                    lambda r: (int(r.subject_id), int(r.hadm_id)) in ids, axis=1
                )
            ).sum()
        ),
        "broad_existing_event_type_counts": {str(k): int(v) for k, v in broad_counts.items()},
        "acute_endpoint_event_type_counts": {str(k): int(v) for k, v in acute_counts.items()},
        "existing_endpoint_code_class_counts": {
            str(row.endpoint_code_class): int(row.n) for row in code_counts.itertuples(index=False)
        },
        "acute_code_definition": "ICD-9 410* or ICD-10 I21*/I22* on an admission present in mi_admissions.parquet",
        "followup_origin": "index discharge",
        "followup_horizon": "existing per-row followup_horizon_end (12 months)",
        "same_day_imprecise_death_order": "event_order_uncertain and censored for the descriptive CIF",
        "scientific_decision": "C - retain exploratory status",
        "reason": "The treatment is admission-level in-hospital exposure with no verified timing relative to discharge, and the existing outcome includes admissions coded only with ICD-9 412; acute-code classification is not clinical adjudication.",
        "treatment_timing_limitation": "The cohort summary notes that no machine-readable prescription/EMAR target-class artifact is available for admission-level linkage; statin_during has no medication timestamp in the saved cohort.",
        "next_modeling_action": "Validate acute MI episodes and medication exposure timing before estimating a competing-risk-aware causal effect; do not reinterpret statin_during as discharge initiation.",
    }
    (OUTPUT_DIR / "phase13_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_report(summary, timing, selection_frame, code_counts, cif)
    return summary


def _write_report(
    summary: dict[str, Any],
    timing: pd.DataFrame,
    selection: pd.DataFrame,
    code_counts: pd.DataFrame,
    cif: pd.DataFrame,
) -> None:
    acute = timing.loc[timing["endpoint"].eq("acute_code_only_endpoint")].iloc[0]
    broad = timing.loc[timing["endpoint"].eq("existing_broad_mi_coded_endpoint")].iloc[0]
    code_counts_text = ", ".join(
        f"{row.endpoint_code_class}: {row.n:,}" for row in code_counts.itertuples(index=False)
    )
    selection_text = _markdown_table(selection)
    cif_text = _markdown_table(cif, floatfmt=".4f")
    report = f"""# Phase 13: Target-Trial Alignment and Endpoint Validation

## Estimand and alignment

The current contrast is among patients with a previously MI-coded admission who survived the selected index admission to discharge: `statin_during=1` versus `statin_during=0`, with follow-up starting at index discharge and a 12-month horizon. It is an association between in-hospital exposure and subsequent outcomes, **not** a statin-initiation-at-discharge intervention. `statin_during` has no verified exposure timestamp in this cohort, so exposure status before follow-up begins is not established. The cohort summary records that admission-level prescription/EMAR linkage to a timestamped target-class exposure is unavailable. Consequently, treatment assignment can incorporate exposure after admission and potentially near discharge; a discharge-initiation causal interpretation risks temporal misalignment and immortal-time/selection bias. No treatment variable was redefined.

## Cohort selection and missingness

There are {summary['cohort_n']:,} eligible index admissions/patients. Treatment is known for {summary['treatment_known_n']:,} ({summary['treated_n']:,} treated; {summary['control_n']:,} controls); {summary['treatment_missing_n']:,} records have no treatment indicator and were not imputed. All {summary['baseline_complete_known_treatment_n']:,} known-treatment records have the available Phase 11 baseline feature set. The existing split-restricted complete-case population is {summary['phase11_complete_case_n']:,}. Baseline covariate and follow-up selection by treatment group are in `cohort_selection_by_treatment.csv`; the complete flow is in `cohort_selection_flow.csv`.

{selection_text}

Follow-up completion in known-treatment patients differs by treatment: treated {selection.loc[selection.treatment_group.eq('treated'), 'followup_complete_percent'].iloc[0]:.2f}% and controls {selection.loc[selection.treatment_group.eq('control'), 'followup_complete_percent'].iloc[0]:.2f}% (a {selection.loc[selection.treatment_group.eq('control'), 'followup_complete_percent'].iloc[0] - selection.loc[selection.treatment_group.eq('treated'), 'followup_complete_percent'].iloc[0]:.2f} percentage-point difference). Complete-case selection is therefore differential; it should not be presumed ignorable.

## Endpoint evidence

The existing broad endpoint has {broad.n_events:,} recurrent MI-coded admissions; median time from discharge is {broad.median_days:.2f} days, with {broad.within_1_day:,} within 1 day, {broad.within_7_days:,} within 7 days, and {broad.within_30_days:,} within 30 days. Among its event admissions, code class counts are {code_counts_text}. ICD-9 `412` alone denotes old MI/history rather than acute infarction. The broad endpoint therefore cannot be interpreted as validated acute recurrent MI.

Using diagnosis rows and MI-admission candidates, the acute-code screen (ICD-9 `410*`, ICD-10 `I21*`/`I22*`) identified {acute.n_events:,} first subsequent acute-coded admissions within observed follow-up. Median time was {acute.median_days:.2f} days; {acute.within_1_day:,} occurred within 1 day, {acute.within_7_days:,} within 7 days, and {acute.within_30_days:,} within 30 days. These remain code-based admissions, not clinically adjudicated recurrent episodes; early admissions may represent continuing care or readmission for the same episode. The files do not establish clinical episode boundaries. The derived `acute_recurrent_mi` indicator is missing for incomplete or event-order-uncertain follow-up; competing deaths are explicitly labeled as competing events, not event-free.

Existing cohort event types: `{json.dumps(summary['broad_existing_event_type_counts'], sort_keys=True)}`. Acute-screen event types, including incomplete follow-up and same-day event-order uncertainty, are `{json.dumps(summary['acute_endpoint_event_type_counts'], sort_keys=True)}`. The admission-level event/code and timing tables preserve the underlying IDs and dates.

## Competing-risk description

The attached cumulative-incidence estimates use index discharge as time origin, acute-coded MI and death as separate event types, and incomplete or same-day order-uncertain follow-up as censored. Treatment-stratified estimates are descriptive only and do not adjust for confounding. Broad-endpoint results are also included, but include history-code events and are not acute-MI cumulative incidence.

{cif_text}

## Decision: C — retain exploratory status

The current data do not support a defensible causal claim for statin initiation at discharge. The exposure lacks event-time ordering relative to discharge, treatment is missing for {summary['treatment_missing_n']:,} of {summary['cohort_n']:,} patients, and the original recurrent-MI outcome contains a large history-code-only component. The acute-code screen improves code specificity but cannot distinguish a new infarction episode from ongoing care, nor validate diagnosis accuracy. Competing death and incomplete observation must remain distinct.

**Next modeling action:** establish timestamped medication administration/order exposure relative to the index discharge and validate acute MI episodes (including same-episode readmissions) using an agreed clinical/code-based rule. Then define a discharge-aligned target trial and estimate cumulative incidence with death as a competing event, with explicit handling of censoring and confounding. Until those checks are possible, retain the Phase 11–12 analyses as exploratory and do not reinterpret them as effects of discharge initiation.

## Reproducibility

From the repository root run:

```powershell
.\\.venv\\Scripts\\python.exe -m causal_models.phase13_target_trial.analyze_target_trial
```

The script reads the existing cohort, MI-admission, diagnosis-code, and split artifacts only; it does not modify them or refit models.
"""
    (OUTPUT_DIR / "phase13_target_trial_report.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    run_analysis()
