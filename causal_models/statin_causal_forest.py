from __future__ import annotations

import argparse
import importlib.util
import json
import logging
from importlib.metadata import PackageNotFoundError, version
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


LOGGER = logging.getLogger(__name__)
SPLITS = ("train", "validation", "test")
TREATMENT = "statin_during"
OUTCOME = "recurrent_mi"
ELIGIBILITY = "prior_mi"
IDENTIFIERS = ("SubjectID", "hadm_id")
BASELINE_FEATURES = (
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "statin_before",
    "aspirin_before",
    "beta_blocker_before",
    "acei_before",
)
PRIMARY_ADJUSTMENT_FEATURES = tuple(
    feature for feature in BASELINE_FEATURES if feature != "statin_before"
)
FORBIDDEN_OUTCOMES = {
    "is_MI": "Admission-level MI label, not a subsequent/recurrent outcome.",
    "Label_Troponin": (
        "ECG/troponin cohort label relative to the index MI, not a subsequent "
        "recurrent-MI outcome."
    ),
}
FORBIDDEN_FEATURES = {
    "statin_after",
    "statin_during",
    "is_MI",
    "Label_Troponin",
    "index_mi_time",
    "time_diff_hours",
    "ecg_time",
    "z_ecg",
}
FEATURE_NOTES = {
    "statin_before": (
        "Baseline order-derived history proxy; it does not establish prior receipt "
        "or adherence. Excluded from primary adjustment because it may proxy a "
        "collider; included only in a sensitivity specification."
    ),
    "prior_mi": "Eligibility filter (constant at 1 in the analysis cohort), not an X feature.",
}


@dataclass(frozen=True)
class ExperimentConfig:
    data_dir: Path = Path("master")
    output_dir: Path = Path("causal_models/outputs/causal_forest")
    source_cohort_path: Path = Path(
        "causal_models/data/statin_recurrent_mi_cohort.parquet"
    )
    outcome: str = OUTCOME
    treatment: str = TREATMENT
    eligibility: str = ELIGIBILITY
    features: tuple[str, ...] = PRIMARY_ADJUSTMENT_FEATURES
    sensitivity_features: tuple[str, ...] = BASELINE_FEATURES
    seed: int = 2026
    cv_folds: int = 3
    bootstrap_replicates: int = 500
    temporal_order_validated: bool = False
    recurrence_outcome_validated: bool = False
    allow_exploratory_estimation: bool = False
    n_jobs: int = -1
    forest_specs: tuple[dict[str, Any], ...] = field(
        default_factory=lambda: (
            {"max_depth": 8, "min_samples_leaf": 10},
            {"max_depth": 12, "min_samples_leaf": 20},
        )
    )


def _column_inventory(data_dir: Path) -> tuple[dict[str, list[str]], dict[str, int]]:
    columns: dict[str, list[str]] = {}
    rows: dict[str, int] = {}
    for split in SPLITS:
        path = data_dir / f"{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Required processed split is missing: {path}")
        parquet = pq.ParquetFile(path)
        columns[split] = list(parquet.schema.names)
        rows[split] = int(parquet.metadata.num_rows)
    return columns, rows


def assess_readiness(config: ExperimentConfig) -> dict[str, Any]:
    """Check hard prerequisites without substituting an existing index-event label."""
    split_columns, split_rows = _column_inventory(config.data_dir)
    required_features = set(config.features) | set(config.sensitivity_features)
    required = {*IDENTIFIERS, config.eligibility, config.treatment, *required_features}
    missing_by_split = {
        split: sorted(required - set(columns))
        for split, columns in split_columns.items()
    }
    outcome_available = {
        split: config.outcome in split_columns[split]
        for split in SPLITS
    }
    blockers: list[str] = []
    warnings: list[str] = []
    if any(missing_by_split.values()):
        blockers.append(f"Required treatment/cohort/features are missing: {missing_by_split}")
    if not all(outcome_available.values()):
        available_outcomes = sorted(
            set.intersection(
                *(
                    set(split_columns[split])
                    for split in SPLITS
                )
            )
            & set(FORBIDDEN_OUTCOMES)
        )
        blockers.append(
            f"Required recurrent-MI outcome '{config.outcome}' is absent from one or more "
            f"processed splits. Existing outcomes present in all splits: {available_outcomes}."
        )
    if config.outcome in FORBIDDEN_OUTCOMES:
        blockers.append(
            f"Outcome '{config.outcome}' cannot stand in for recurrent MI: "
            f"{FORBIDDEN_OUTCOMES[config.outcome]}"
        )
    if config.outcome in {*FORBIDDEN_FEATURES, *IDENTIFIERS, config.treatment}:
        blockers.append(
            f"Outcome '{config.outcome}' is not a distinct, permitted follow-up endpoint."
        )
    if config.treatment != TREATMENT or config.eligibility != ELIGIBILITY:
        blockers.append(
            "This experiment is restricted to statin_during among prior_mi == 1."
        )
    if not config.recurrence_outcome_validated:
        message = (
            "A distinct subsequent/recurrent-MI outcome has not been clinically and "
            "temporally validated."
        )
        (warnings if config.allow_exploratory_estimation else blockers).append(message)
    if not config.temporal_order_validated:
        message = (
            "Treatment-before-outcome ordering for statin_during has not been validated; "
            "the field denotes in-hospital treatment without an assignment timestamp."
        )
        (warnings if config.allow_exploratory_estimation else blockers).append(message)
    if importlib.util.find_spec("econml") is None:
        blockers.append("EconML is not installed in the selected Python environment.")

    if all("SubjectID" in split_columns[split] for split in SPLITS):
        patient_sets = {
            split: set(
                pd.read_parquet(
                    config.data_dir / f"{split}.parquet",
                    columns=["SubjectID"],
                )["SubjectID"].dropna().unique()
            )
            for split in SPLITS
        }
        split_overlap = {
            f"{left}_vs_{right}": len(patient_sets[left] & patient_sets[right])
            for index, left in enumerate(SPLITS)
            for right in SPLITS[index + 1 :]
        }
        if any(split_overlap.values()):
            blockers.append(f"Patient leakage across splits: {split_overlap}")
    else:
        split_overlap = "not checkable: SubjectID missing"

    return {
        "status": (
            "blocked"
            if blockers
            else "exploratory"
            if warnings
            else "ready"
        ),
        "blockers": blockers,
        "warnings": warnings,
        "split_rows": split_rows,
        "outcome_column_available": outcome_available,
        "required_field_missing_by_split": missing_by_split,
        "patient_level_split_validation": split_overlap,
        "model_fitted": False,
        "estimand_note": (
            "No ATE/CATE is estimated unless a valid subsequent outcome and "
            "treatment-relative time ordering are supplied; exploratory mode "
            "permits model fitting without claiming those validations."
        ),
    }


def load_split(
    data_dir: Path,
    split: str,
    outcome: str = OUTCOME,
    treatment: str = TREATMENT,
    eligibility: str = ELIGIBILITY,
    features: tuple[str, ...] = BASELINE_FEATURES,
) -> pd.DataFrame:
    if split not in SPLITS:
        raise ValueError(f"Unknown split: {split}")
    path = data_dir / f"{split}.parquet"
    columns = list(pq.ParquetFile(path).schema.names)
    missing = sorted(
        {outcome, treatment, eligibility, *IDENTIFIERS, *features}
        - set(columns)
    )
    if missing:
        raise ValueError(f"Split {split} lacks required causal-model fields: {missing}")
    if (
        outcome in FORBIDDEN_OUTCOMES
        or outcome in FORBIDDEN_FEATURES
        or outcome in BASELINE_FEATURES
    ):
        raise ValueError(f"Refusing non-follow-up outcome: {outcome}")
    return pd.read_parquet(
        path,
        columns=[*IDENTIFIERS, eligibility, treatment, outcome, *features],
    )


def build_admission_cohort(
    frame: pd.DataFrame,
    outcome: str = OUTCOME,
    treatment: str = TREATMENT,
    eligibility: str = ELIGIBILITY,
    features: tuple[str, ...] = BASELINE_FEATURES,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Collapse ECG rows to one admission, rejecting within-admission conflicts."""
    forbidden = set(FORBIDDEN_FEATURES)
    if (
        outcome in FORBIDDEN_OUTCOMES
        or outcome in FORBIDDEN_FEATURES
        or outcome in BASELINE_FEATURES
    ):
        raise ValueError(f"Refusing non-follow-up outcome: {outcome}")
    if treatment in {"statin_after", outcome} or treatment not in frame:
        raise ValueError(f"Invalid or unavailable treatment field: {treatment}")
    disallowed_features = set(features) & forbidden
    unknown_features = set(features) - set(BASELINE_FEATURES)
    if disallowed_features or unknown_features:
        raise ValueError(
            "Features must be explicitly approved pre-treatment variables; "
            f"disallowed={sorted(disallowed_features)}, unknown={sorted(unknown_features)}"
        )
    required = {"SubjectID", "hadm_id", eligibility, outcome, treatment, *features}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing cohort fields: {missing}")

    selected = frame.loc[frame[eligibility].eq(1)].copy()
    consistency_columns = ["SubjectID", eligibility, outcome, treatment, *features]
    unique_counts = selected.groupby("hadm_id", dropna=False)[consistency_columns].nunique(
        dropna=False
    )
    inconsistent = unique_counts.gt(1).any(axis=1)
    inconsistent_count = int(inconsistent.sum())
    if inconsistent_count:
        examples = inconsistent[inconsistent].index[:10].tolist()
        raise ValueError(
            f"{inconsistent_count} prior-MI admissions have conflicting covariates, "
            f"treatment, outcome, or patient ID across ECG rows; examples={examples}"
        )

    cohort_columns = [
        column for column in IDENTIFIERS if column in selected.columns
    ] + [eligibility, treatment, outcome, *features]
    cohort = selected.loc[:, cohort_columns].drop_duplicates("hadm_id", keep="first").copy()
    before_drop = len(cohort)
    complete_fields = [outcome, treatment, *features]
    complete = cohort[complete_fields].notna().all(axis=1)
    cohort = cohort.loc[complete].copy()
    cohort[outcome] = pd.to_numeric(cohort[outcome], errors="raise").astype(int)
    cohort[treatment] = pd.to_numeric(cohort[treatment], errors="raise").astype(int)
    for feature in features:
        cohort[feature] = pd.to_numeric(cohort[feature], errors="raise")
    if not cohort[outcome].isin([0, 1]).all():
        raise ValueError(f"Outcome {outcome} must be binary.")
    if not cohort[treatment].isin([0, 1]).all():
        raise ValueError(f"Treatment {treatment} must be binary.")
    if not cohort["SubjectID"].notna().all():
        raise ValueError("Patient IDs must be present to preserve group boundaries.")

    constant = [feature for feature in features if cohort[feature].nunique() <= 1]
    eligible_features = [feature for feature in features if feature not in constant]
    if set(eligible_features) & forbidden:
        raise ValueError("A forbidden post-treatment or outcome-derived field entered X.")

    return cohort, {
        "prior_mi_admissions_before_complete_case_filter": before_drop,
        "complete_admissions": len(cohort),
        "dropped_missing_treatment_outcome_or_covariate": before_drop - len(cohort),
        "admissions_with_conflicting_rows": inconsistent_count,
        "constant_features_excluded": constant,
        "features_used": eligible_features,
        "feature_count": len(eligible_features),
    }


def validate_patient_splits(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    patient_sets = {
        split: set(frame["SubjectID"].dropna().unique())
        for split, frame in frames.items()
    }
    overlaps: dict[str, int] = {}
    for left_index, left in enumerate(SPLITS):
        for right in SPLITS[left_index + 1 :]:
            overlap = patient_sets[left] & patient_sets[right]
            overlaps[f"{left}_vs_{right}"] = len(overlap)
    if any(overlaps.values()):
        raise ValueError(f"Patient leakage across train/validation/test splits: {overlaps}")
    return overlaps


def _standardized_mean_differences(
    data: pd.DataFrame,
    treatment: str,
    features: tuple[str, ...],
    weights: np.ndarray | None = None,
) -> dict[str, float]:
    treated = data[treatment].to_numpy(dtype=int) == 1
    control = ~treated
    results: dict[str, float] = {}
    for feature in features:
        values = data[feature].to_numpy(dtype=float)
        if weights is None:
            mean_treated = values[treated].mean()
            mean_control = values[control].mean()
            var_treated = values[treated].var(ddof=1)
            var_control = values[control].var(ddof=1)
        else:
            treated_weights = weights[treated]
            control_weights = weights[control]
            mean_treated = np.average(values[treated], weights=treated_weights)
            mean_control = np.average(values[control], weights=control_weights)
            var_treated = np.average(
                (values[treated] - mean_treated) ** 2,
                weights=treated_weights,
            )
            var_control = np.average(
                (values[control] - mean_control) ** 2,
                weights=control_weights,
            )
        pooled_sd = np.sqrt((var_treated + var_control) / 2.0)
        results[feature] = (
            float((mean_treated - mean_control) / pooled_sd)
            if pooled_sd > 0
            else 0.0
        )
    return results


def _weighted_ate(
    data: pd.DataFrame,
    propensity: np.ndarray,
    outcome: str,
    treatment: str,
) -> tuple[float, np.ndarray]:
    treatment_values = data[treatment].to_numpy(dtype=int)
    outcome_values = data[outcome].to_numpy(dtype=float)
    clipped = np.clip(propensity, 0.01, 0.99)
    weights = np.where(treatment_values == 1, 1.0 / clipped, 1.0 / (1.0 - clipped))
    estimate = float(
        np.average(outcome_values[treatment_values == 1], weights=weights[treatment_values == 1])
        - np.average(
            outcome_values[treatment_values == 0],
            weights=weights[treatment_values == 0],
        )
    )
    return estimate, weights


def _cluster_bootstrap_interval(
    data: pd.DataFrame,
    propensity: np.ndarray,
    outcome: str,
    treatment: str,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    patient_ids = data["SubjectID"].to_numpy()
    unique_patients = pd.unique(patient_ids)
    rows_by_patient = {
        patient: np.flatnonzero(patient_ids == patient) for patient in unique_patients
    }
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        sampled = rng.choice(unique_patients, size=len(unique_patients), replace=True)
        indices = np.concatenate([rows_by_patient[patient] for patient in sampled])
        sample = data.iloc[indices]
        if sample[treatment].nunique() != 2:
            continue
        estimate, _ = _weighted_ate(
            sample,
            propensity[indices],
            outcome,
            treatment,
        )
        estimates.append(estimate)
    if len(estimates) < max(30, replicates // 2):
        raise ValueError("Too few valid patient-cluster bootstrap replicates for an interval.")
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return float(lower), float(upper)


def _weighted_risk_difference(
    data: pd.DataFrame,
    weights: np.ndarray,
    outcome: str,
    treatment: str,
) -> float:
    treatment_values = data[treatment].to_numpy(dtype=int)
    outcome_values = data[outcome].to_numpy(dtype=float)
    treated_weights = weights[treatment_values == 1]
    control_weights = weights[treatment_values == 0]
    return float(
        np.average(
            outcome_values[treatment_values == 1],
            weights=treated_weights,
        )
        - np.average(
            outcome_values[treatment_values == 0],
            weights=control_weights,
        )
    )


def _cluster_bootstrap_weighted_interval(
    data: pd.DataFrame,
    weights: np.ndarray,
    outcome: str,
    treatment: str,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    patient_ids = data["SubjectID"].to_numpy()
    unique_patients = pd.unique(patient_ids)
    rows_by_patient = {
        patient: np.flatnonzero(patient_ids == patient) for patient in unique_patients
    }
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        sampled = rng.choice(unique_patients, size=len(unique_patients), replace=True)
        indices = np.concatenate([rows_by_patient[patient] for patient in sampled])
        sample = data.iloc[indices]
        if sample[treatment].nunique() != 2:
            continue
        estimates.append(
            _weighted_risk_difference(
                sample,
                weights[indices],
                outcome,
                treatment,
            )
        )
    if len(estimates) < max(30, replicates // 2):
        raise ValueError("Too few valid patient-cluster bootstrap replicates for weighted interval.")
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return float(lower), float(upper)


def _cluster_bootstrap_gcomp_interval(
    data: pd.DataFrame,
    risk_control: np.ndarray,
    risk_treated: np.ndarray,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    patient_ids = data["SubjectID"].to_numpy()
    unique_patients = pd.unique(patient_ids)
    rows_by_patient = {
        patient: np.flatnonzero(patient_ids == patient) for patient in unique_patients
    }
    individual_effects = risk_treated - risk_control
    rng = np.random.default_rng(seed)
    estimates = [
        float(individual_effects[
            np.concatenate(
                [
                    rows_by_patient[patient]
                    for patient in rng.choice(
                        unique_patients,
                        size=len(unique_patients),
                        replace=True,
                    )
                ]
            )
        ].mean())
        for _ in range(replicates)
    ]
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return float(lower), float(upper)


def _distribution_summary(values: np.ndarray) -> dict[str, Any]:
    quantiles = np.quantile(values, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {
        "n": int(len(values)),
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "quantiles_1_5_25_50_75_95_99": quantiles.tolist(),
    }


def _scalar_float(value: Any) -> float:
    scalar = np.asarray(value, dtype=float).reshape(-1)
    if scalar.size != 1:
        raise ValueError(f"Expected a scalar estimator result, got shape {np.shape(value)}.")
    return float(scalar[0])


def _split_prevalence_and_balance(
    frame: pd.DataFrame,
    features: tuple[str, ...],
) -> dict[str, Any]:
    treatment = frame[TREATMENT].to_numpy(dtype=int)
    propensity = frame["propensity_score"].to_numpy(dtype=float)
    weights = np.where(
        treatment == 1,
        1.0 / np.clip(propensity, 0.01, 0.99),
        1.0 / (1.0 - np.clip(propensity, 0.01, 0.99)),
    )
    smd_before = _standardized_mean_differences(frame, TREATMENT, features)
    smd_after = _standardized_mean_differences(
        frame,
        TREATMENT,
        features,
        weights,
    )
    treated_ps = propensity[treatment == 1]
    control_ps = propensity[treatment == 0]
    common_lower = max(float(treated_ps.min()), float(control_ps.min()))
    common_upper = min(float(treated_ps.max()), float(control_ps.max()))
    outside = (propensity < common_lower) | (propensity > common_upper)
    return {
        "propensity_balance_sample_size": int(len(frame)),
        "treatment_prevalence_in_propensity_balance_sample": float(
            np.mean(treatment)
        ),
        "propensity_auc_source_fit": float(frame["propensity_auc"].iloc[0]),
        "propensity_overlap": {
            "treated": _distribution_summary(treated_ps),
            "control": _distribution_summary(control_ps),
            "common_support": [common_lower, common_upper],
            "fraction_outside_common_support": float(outside.mean()),
        },
        "covariate_balance_smd": {
            feature: {
                "before": smd_before[feature],
                "after_ipw": smd_after[feature],
            }
            for feature in features
        },
    }


def _preliminary_and_censoring_analysis(
    config: ExperimentConfig,
    split_frames: dict[str, pd.DataFrame],
    features: tuple[str, ...],
) -> tuple[
    dict[str, Any],
    dict[str, pd.DataFrame],
    dict[str, np.ndarray],
    dict[str, Any],
]:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score

    if not config.source_cohort_path.is_file():
        raise FileNotFoundError(
            f"Source cohort required for competing-event and censoring diagnostics: "
            f"{config.source_cohort_path}"
        )
    source = pd.read_parquet(config.source_cohort_path)
    source["SubjectID"] = source["subject_id"].astype("int64")
    if source.duplicated(["SubjectID", "hadm_id"]).any():
        raise ValueError("Source cohort contains duplicate patient-admission keys.")
    source_feature_columns = tuple(
        dict.fromkeys((*features, *config.sensitivity_features))
    )
    expected_event_types = {
        "recurrent_mi",
        "competing_death",
        "event_free",
        "incomplete_followup",
    }
    diagnostic_frames: dict[str, pd.DataFrame] = {}
    source_counts: dict[str, Any] = {}
    for split in SPLITS:
        split_model = split_frames[split].loc[
            :,
            [
                "SubjectID",
                "hadm_id",
                TREATMENT,
                OUTCOME,
                *source_feature_columns,
            ],
        ]
        split_keys = set(zip(split_model["SubjectID"], split_model["hadm_id"]))
        split_source = source.loc[
            [
                key in split_keys
                for key in zip(source["SubjectID"], source["hadm_id"])
            ]
        ].copy()
        if len(split_source) != len(split_frames[split]):
            raise ValueError(
                f"Source cohort rows ({len(split_source)}) do not match {split} "
                f"forest split ({len(split_frames[split])})."
            )
        keys_source = set(zip(split_source["SubjectID"], split_source["hadm_id"]))
        if keys_source != split_keys:
            raise ValueError(f"{split} source cohort admissions differ from forest split.")
        source_values = split_source.set_index(
            ["SubjectID", "hadm_id"]
        ).sort_index()
        split_values = split_model.set_index(
            ["SubjectID", "hadm_id"]
        ).sort_index()
        for column in (TREATMENT, OUTCOME, *source_feature_columns):
            source_column = pd.to_numeric(
                source_values[column],
                errors="coerce",
            )
            split_column = pd.to_numeric(
                split_values[column],
                errors="coerce",
            )
            matches = source_column.eq(split_column) | (
                source_column.isna() & split_column.isna()
            )
            if not matches.all():
                raise ValueError(
                    f"{split} source cohort values for {column} differ from the "
                    "existing split; refusing mismatched diagnostics."
                )
        unexpected_event_types = set(split_source["event_type"].dropna()) - expected_event_types
        if unexpected_event_types:
            raise ValueError(
                f"{split} source cohort has unresolved event types: "
                f"{sorted(unexpected_event_types)}."
            )
        assigned_splits = split_source["source_split"].dropna().unique()
        if len(assigned_splits) and set(assigned_splits) != {split}:
            raise ValueError(
                f"Source-cohort split assignments conflict with {split} split IDs."
            )
        if split_source["event_type"].isna().any():
            raise ValueError(f"{split} source cohort has missing event types.")
        split_source["treatment"] = pd.to_numeric(
            split_source[TREATMENT],
            errors="coerce",
        )
        split_source["outcome"] = pd.to_numeric(
            split_source[OUTCOME],
            errors="coerce",
        )
        split_source["censored"] = split_source["event_type"].eq(
            "incomplete_followup"
        ).astype("int8")
        diagnostic_frames[split] = split_source
        source_counts[split] = {
            "admissions": int(len(split_source)),
            "unique_patients": int(split_source["subject_id"].nunique()),
            "treated": int(split_source[TREATMENT].eq(1).sum()),
            "control": int(split_source[TREATMENT].eq(0).sum()),
            "treatment_missing": int(split_source[TREATMENT].isna().sum()),
            "treatment_prevalence_among_known": (
                float(
                    split_source[TREATMENT].eq(1).sum()
                    / split_source[TREATMENT].notna().sum()
                )
                if split_source[TREATMENT].notna().any()
                else None
            ),
            "recurrent_mi_events": int(split_source["event_type"].eq("recurrent_mi").sum()),
            "competing_deaths": int(
                split_source["event_type"].eq("competing_death").sum()
            ),
            "event_free": int(split_source["event_type"].eq("event_free").sum()),
            "incomplete_followup": int(
                split_source["event_type"].eq("incomplete_followup").sum()
            ),
            "outcome_observed": int(split_source[OUTCOME].notna().sum()),
            "outcome_missing_due_to_followup": int(
                split_source[OUTCOME].isna().sum()
            ),
            "outcome_prevalence_among_observed": (
                float(split_source[OUTCOME].dropna().mean())
                if split_source[OUTCOME].notna().any()
                else None
            ),
            "censoring_prevalence": float(split_source["censored"].mean()),
            "recurrent_mi_prevalence_among_observed": (
                float(split_source[OUTCOME].dropna().mean())
                if split_source[OUTCOME].notna().any()
                else None
            ),
        }

    train_source = diagnostic_frames["train"]
    train_covariate_complete = train_source.loc[
        :, list(features)
    ].notna().all(axis=1)
    train_known_treatment = train_source[TREATMENT].notna()
    train_propensity_rows = train_covariate_complete & train_known_treatment
    propensity_model = LogisticRegression(max_iter=2000, solver="lbfgs")
    propensity_model.fit(
        train_source.loc[train_propensity_rows, list(features)],
        train_source.loc[train_propensity_rows, TREATMENT].astype(int),
    )
    for split, data in diagnostic_frames.items():
        valid = (
            data[TREATMENT].notna()
            & data.loc[:, list(features)].notna().all(axis=1)
        )
        data["propensity_score"] = np.nan
        data.loc[valid, "propensity_score"] = propensity_model.predict_proba(
            data.loc[valid, list(features)]
        )[:, 1]
        data["propensity_auc"] = np.nan
        if data.loc[valid, TREATMENT].nunique() == 2:
            data.loc[valid, "propensity_auc"] = float(
                roc_auc_score(
                    data.loc[valid, TREATMENT].astype(int),
                    data.loc[valid, "propensity_score"],
                )
            )

    train_censor_mask = train_covariate_complete & train_known_treatment
    train_censor = train_source.loc[train_censor_mask].copy()
    censor_model = LogisticRegression(max_iter=2000, solver="lbfgs")
    censor_model.fit(
        train_censor.loc[:, [*features, TREATMENT]],
        1 - train_censor["censored"],
    )
    observed_probability_by_split: dict[str, np.ndarray] = {}
    censoring_diagnostics: dict[str, Any] = {}
    for split, data in diagnostic_frames.items():
        valid = (
            data[TREATMENT].notna()
            & data.loc[:, list(features)].notna().all(axis=1)
        )
        predicted_observed = censor_model.predict_proba(
            data.loc[valid, [*features, TREATMENT]]
        )[:, 1]
        data["probability_observed"] = np.nan
        data.loc[valid, "probability_observed"] = predicted_observed
        observed_probability = np.full(len(data), np.nan, dtype=float)
        observed_probability[valid.to_numpy()] = predicted_observed
        observed_probability_by_split[split] = observed_probability
        complete = data["censored"].eq(0) & valid
        incomplete = data["censored"].eq(1) & valid
        censor_smd: dict[str, float | None] = {}
        for feature in features:
            mean_complete = data.loc[complete, feature].mean()
            mean_incomplete = data.loc[incomplete, feature].mean()
            var_complete = data.loc[complete, feature].var(ddof=1)
            var_incomplete = data.loc[incomplete, feature].var(ddof=1)
            pooled = np.sqrt((var_complete + var_incomplete) / 2.0)
            censor_smd[feature] = (
                float((mean_incomplete - mean_complete) / pooled)
                if np.isfinite(pooled) and pooled > 0
                else None
            )
        treatment_censor = pd.crosstab(
            data.loc[valid, TREATMENT],
            data.loc[valid, "censored"],
            dropna=False,
            normalize="index",
        )
        censoring_diagnostics[split] = {
            "complete_baseline_and_treatment_admissions": int(valid.sum()),
            "incomplete_followup_in_analysis_subset": int(
                (data["censored"].eq(1) & valid).sum()
            ),
            "censoring_prevalence_by_treatment": {
                str(index): float(row.get(1, 0.0))
                for index, row in treatment_censor.iterrows()
            },
            "absolute_smd_incomplete_vs_observed": censor_smd,
            "conditional_observation_probability": _distribution_summary(
                predicted_observed
            ),
            "minimum_conditional_observation_probability": float(
                predicted_observed.min()
            ),
        }

    test_valid = (
        diagnostic_frames["test"][TREATMENT].notna()
        & diagnostic_frames["test"].loc[:, list(features)].notna().all(axis=1)
    )
    test_observed = 1 - diagnostic_frames["test"].loc[
        test_valid, "censored"
    ].to_numpy()
    censor_auc = (
        float(
            roc_auc_score(
                test_observed,
                observed_probability_by_split["test"][test_valid.to_numpy()],
            )
        )
        if np.unique(test_observed).size == 2
        else None
    )

    split_diagnostics: dict[str, Any] = {}
    for split, data in diagnostic_frames.items():
        known = data[TREATMENT].notna()
        balance_rows = known & data.loc[:, list(features)].notna().all(axis=1)
        split_diagnostics[split] = {
            **source_counts[split],
            **_split_prevalence_and_balance(
                data.loc[balance_rows].copy(),
                features,
            ),
        }
    preliminary = {
        "analysis_population": (
            "Source-cohort admissions matched by patient/admission identifiers to "
            "the existing Phase 9 splits; null source_split values do not exclude "
            "otherwise matched admissions."
        ),
        "split_summary": split_diagnostics,
        "censoring_assessment": {
            "definition": (
                "Incomplete follow-up is the censoring outcome; recurrent MI, death, "
                "and confirmed event-free 12-month follow-up are observed endpoints."
            ),
            "train_fitted_logistic_model_test_auc": censor_auc,
            "by_split": censoring_diagnostics,
            "interpretation": (
                "Associations diagnose measured predictors of incomplete follow-up; "
                "they do not establish independent censoring."
            ),
        },
    }
    return (
        preliminary,
        diagnostic_frames,
        observed_probability_by_split,
        {
            "preliminary_propensity_model": propensity_model,
            "censoring_model": censor_model,
        },
    )


def _ipcw_sensitivity(
    test: pd.DataFrame,
    source_test: pd.DataFrame,
    propensity: np.ndarray,
    observed_probability: np.ndarray,
    config: ExperimentConfig,
    outcome: str,
    treatment: str,
) -> dict[str, Any]:
    observed = source_test["censored"].to_numpy() == 0
    valid_for_censor_model = source_test["probability_observed"].notna().to_numpy()
    if not valid_for_censor_model.any():
        raise ValueError("No test records have complete predictors for IPCW.")
    source_complete = source_test.loc[observed].copy()
    complete_keys = set(zip(test["SubjectID"], test["hadm_id"]))
    source_complete_keys = set(
        zip(source_complete["SubjectID"], source_complete["hadm_id"])
    )
    if not complete_keys.issubset(source_complete_keys):
        raise ValueError(
            "Complete-case test cohort does not align with observed follow-up records "
            "for IPCW analysis."
        )
    probability_by_key = pd.Series(
        observed_probability,
        index=pd.MultiIndex.from_frame(
            source_test[["SubjectID", "hadm_id"]]
        ),
    )
    test_keys = pd.MultiIndex.from_frame(test[["SubjectID", "hadm_id"]])
    censor_probability = np.clip(
        probability_by_key.reindex(test_keys).to_numpy(dtype=float),
        0.05,
        1.0,
    )
    if not np.isfinite(censor_probability).all():
        raise ValueError("IPCW model predictions failed to align to the complete test cohort.")
    marginal_observation = float(observed[valid_for_censor_model].mean())
    ipcw = marginal_observation / censor_probability
    propensity_clipped = np.clip(propensity, 0.01, 0.99)
    treatment_values = test[treatment].to_numpy(dtype=int)
    treatment_weights = np.where(
        treatment_values == 1,
        1.0 / propensity_clipped,
        1.0 / (1.0 - propensity_clipped),
    )
    combined = treatment_weights * ipcw
    estimate = _weighted_risk_difference(test, combined, outcome, treatment)
    interval = _cluster_bootstrap_weighted_interval(
        test,
        combined,
        outcome,
        treatment,
        config.bootstrap_replicates,
        config.seed + 11,
    )
    return {
        "method": "stabilized IPCW multiplied by inverse-propensity weights",
        "censor_model": (
            "Logistic regression for observed outcome follow-up using train split; "
            "predictors are primary adjustment covariates and statin_during."
        ),
        "observed_probability_floor": 0.05,
        "observed_followup_fraction_test": marginal_observation,
        "censor_weight_distribution": _distribution_summary(ipcw),
        "combined_weight_effective_sample_size": float(
            combined.sum() ** 2 / np.square(combined).sum()
        ),
        "ate_risk_difference": estimate,
        "patient_cluster_bootstrap_95_interval": list(interval),
        "is_sensitivity_only": True,
        "limitations": (
            "IPCW requires conditional independent censoring and positivity given "
            "measured baseline variables; estimates do not account for unmeasured "
            "reasons for loss to observation."
        ),
        "_ipcw_weights": ipcw,
        "_combined_weights": combined,
    }


def _package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for package in (
        "econml",
        "numpy",
        "scipy",
        "scikit-learn",
        "pandas",
        "pyarrow",
        "matplotlib",
    ):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def _write_experiment_report(
    path: Path,
    metrics: dict[str, Any],
    packages: dict[str, str | None],
) -> None:
    forest = metrics["causal_forest"]
    cc = metrics["complete_case_analysis"]
    source_lines = [
        "| Split | Admissions | Patients | Treated | Control | Tx missing | Tx prevalence* | Recurrent MI | Death | Event-free | Incomplete | Outcome prevalence** |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for split, row in metrics["preliminary_source_cohort"].items():
        source_lines.append(
            f"| {split} | {row['admissions']} | {row['unique_patients']} | "
            f"{row['treated']} | {row['control']} | {row['treatment_missing']} | "
            f"{row['treatment_prevalence_among_known']:.3f} | "
            f"{row['recurrent_mi_events']} | {row['competing_deaths']} | "
            f"{row['event_free']} | {row['incomplete_followup']} | "
            f"{row['outcome_prevalence_among_observed']:.3f} |"
        )
    test_censoring = metrics["censoring_assessment"]["by_split"]["test"]
    control_censoring = test_censoring["censoring_prevalence_by_treatment"]["0"]
    treated_censoring = test_censoring["censoring_prevalence_by_treatment"]["1"]
    censor_smds = {
        feature: abs(value)
        for feature, value in test_censoring[
            "absolute_smd_incomplete_vs_observed"
        ].items()
        if value is not None
    }
    max_censor_feature = max(censor_smds, key=censor_smds.get)
    test_metrics = metrics["test_outcome_metrics"]
    max_smd_before = max(
        abs(value)
        for value in metrics["propensity_ipw_ate"]["smd_before"].values()
    )
    max_smd_after = max(
        abs(value)
        for value in metrics["propensity_ipw_ate"]["smd_after"].values()
    )
    subgroup_lines = [
        "| Subgroup | N | Treated | Control | Estimated risk difference (95% interval) |",
        "|---|---:|---:|---:|---:|",
    ]
    subgroup_lines.extend(
        f"| {row['subgroup']} | {row['admissions']} | {row['treated']} | "
        f"{row['control']} | {row['ate']:.4f} "
        f"({row['ci_lower_95']:.4f}, {row['ci_upper_95']:.4f}) |"
        for row in metrics["subgroup_effects"]
        if row["status"] == "model_estimate"
    )
    report = "\n".join(
        [
            "# Phase 11: Initial statin causal analysis",
            "",
            "Exploratory admission-level analysis of 12-month MI-coded recurrence in the selected prior-MI cohort.",
            "The exposure is the existing in-hospital `statin_during` indicator, not confirmed initiation, discharge continuation, or adherence.",
            "",
            "The run is exploratory; unresolved endpoint validation and treatment-timing assumptions are retained in `metrics.json` and do not support a clinical causal claim.",
            "",
            "## Preliminary split counts",
            "",
            *source_lines,
            "",
            "* Treatment prevalence is among records with known treatment. ** Outcome prevalence is among records with observed follow-up.",
            "",
            f"- In the test subset with complete baseline covariates and known treatment, incomplete-follow-up rates were {control_censoring:.1%} for controls and {treated_censoring:.1%} for treated admissions; the largest absolute covariate SMD comparing incomplete with observed follow-up was {max_censor_feature} ({censor_smds[max_censor_feature]:.3f}).",
            f"- The train-fitted censoring model's test AUC was {metrics['censoring_assessment']['train_fitted_logistic_model_test_auc']:.3f}.",
            "",
            "## Complete-case test estimates",
            "",
            f"- Test complete-case admissions: {cc['test_admissions']}.",
            f"- Treatment prevalence: {cc['test_treatment_prevalence']:.3f}.",
            f"- Observed recurrent-MI prevalence: {cc['test_outcome_prevalence']:.3f}.",
            f"- Logistic outcome model: AUC {test_metrics['roc_auc']:.3f}, Brier {test_metrics['brier_score']:.3f}, calibration slope {test_metrics['calibration_slope']:.3f}.",
            f"- Logistic g-computation risk difference: "
            f"{cc['test_logistic_g_computation_ate']['estimate']:.4f} "
            f"(patient-cluster bootstrap 95% interval conditional on the fitted model; "
            f"model-fit uncertainty is excluded: "
            f"{cc['test_logistic_g_computation_ate']['patient_cluster_bootstrap_95_interval']}).",
            f"- Propensity-weighted risk difference: {cc['test_propensity_ipw_ate']['estimate']:.4f} "
            f"(patient-cluster bootstrap 95% interval "
            f"{cc['test_propensity_ipw_ate']['patient_cluster_bootstrap_95_interval']}).",
            f"- CausalForestDML test ATE: {forest['ate']:.4f} "
            f"(95% interval {forest['ate_95_interval']}).",
            f"- Test CATE mean/SD: {forest['cate_distribution']['mean']:.4f}/"
            f"{forest['cate_distribution']['std']:.4f}; CATE quartiles: "
            f"{forest['cate_distribution']['quantiles'][2:5]}.",
            f"- Test propensity common-support exclusion: "
            f"{metrics['test_propensity_overlap']['fraction_outside_common_support']:.1%}; "
            f"maximum absolute SMD in the complete-case test set changed from "
            f"{max_smd_before:.3f} before weighting to {max_smd_after:.3f} after weighting.",
            f"- IPCW plus treatment-IPW sensitivity risk difference: "
            f"{metrics['censoring_sensitivity']['ate_risk_difference']:.4f} "
            f"(patient-cluster bootstrap 95% interval "
            f"{metrics['censoring_sensitivity']['patient_cluster_bootstrap_95_interval']}).",
            "",
            "## Subgroup effects",
            "",
            *subgroup_lines,
            "",
            "## Sensitivity",
            "",
            *[
                f"- {result['spec']}: test ATE {result['test_ate']:.4f}; "
                f"CATE correlation with primary {result.get('test_cate_correlation_with_selected', result.get('test_cate_correlation_with_primary')):.3f}; "
                f"mean absolute CATE difference "
                f"{result['mean_absolute_cate_difference']:.4f}."
                for result in forest["sensitivity_specs"]
            ],
            "",
            "## Limitations",
            "",
            "- Complete-case estimates are exploratory; 12-month follow-up censoring is associated with observed treatment/covariates, and selection may bias estimates.",
            "- IPCW assumes censoring is conditionally independent given the measured baseline variables and treatment and requires censoring positivity; it is a sensitivity analysis, not a correction guaranteed to remove bias.",
            "- The outcome is based on MI-coded admissions. Death before recurrence is treated as a competing event and coded as no recurrence by the horizon for the binary cumulative-incidence estimand.",
            "- Treatment timing within the admission is not known to precede index discharge; this is not a trial of discharge initiation and may not establish treatment-before-follow-up ordering.",
            "- The existing master lacks baseline features for some eligible index admissions; the analysis uses admissions with a match and complete treatment/covariates/outcome.",
            "- Estimates are not established clinical causal effects; conditional exchangeability, consistency, positivity, correct time ordering, accurate classification, and adequate censoring adjustment remain assumptions.",
            "",
            "## Environment",
            "",
            *[f"- {name}: {value or 'not installed'}" for name, value in packages.items()],
            "",
            f"Selected forest specification: `{forest['selected_spec']}`.",
            "",
        ]
    )
    path.write_text(report, encoding="utf-8")


def _classification_metrics(
    y_true: np.ndarray,
    probability: np.ndarray,
) -> dict[str, float]:
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

    clipped = np.clip(probability, 1e-6, 1.0 - 1e-6)
    metrics = {
        "brier_score": float(brier_score_loss(y_true, clipped)),
        "log_loss": float(log_loss(y_true, clipped, labels=[0, 1])),
    }
    metrics["roc_auc"] = (
        float(roc_auc_score(y_true, clipped))
        if np.unique(y_true).size == 2
        else float("nan")
    )
    logit = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    from sklearn.linear_model import LogisticRegression

    calibrator = LogisticRegression(solver="lbfgs")
    calibrator.fit(logit, y_true)
    metrics["calibration_intercept"] = float(calibrator.intercept_[0])
    metrics["calibration_slope"] = float(calibrator.coef_[0, 0])
    return metrics


def _subgroup_effects(
    test: pd.DataFrame,
    x_test: pd.DataFrame,
    forest: Any,
    treatment: str,
) -> list[dict[str, Any]]:
    subgroup_masks = {
        "Age <65": test["anchor_age"].to_numpy() < 65,
        "Age >=65": test["anchor_age"].to_numpy() >= 65,
        "Female": test["sex_male"].to_numpy() == 0,
        "Male": test["sex_male"].to_numpy() == 1,
        "Diabetes: no": test["diabetes"].to_numpy() == 0,
        "Diabetes: yes": test["diabetes"].to_numpy() == 1,
    }
    results: list[dict[str, Any]] = []
    treatment_values = test[treatment].to_numpy()
    for label, mask in subgroup_masks.items():
        subgroup_treatment = treatment_values[mask]
        row: dict[str, Any] = {
            "subgroup": label,
            "admissions": int(mask.sum()),
            "treated": int(np.sum(subgroup_treatment == 1)),
            "control": int(np.sum(subgroup_treatment == 0)),
            "ate": None,
            "ci_lower_95": None,
            "ci_upper_95": None,
        }
        if mask.sum() < 10 or np.unique(subgroup_treatment).size != 2:
            row["status"] = "not_estimated_insufficient_size_or_treatment_overlap"
            results.append(row)
            continue
        lower, upper = forest.ate_interval(
            X=x_test.loc[mask],
            T0=0,
            T1=1,
            alpha=0.05,
        )
        row.update(
            {
                "ate": _scalar_float(
                    forest.ate(X=x_test.loc[mask], T0=0, T1=1)
                ),
                "ci_lower_95": float(np.asarray(lower).squeeze()),
                "ci_upper_95": float(np.asarray(upper).squeeze()),
                "status": "model_estimate",
            }
        )
        results.append(row)
    return results


def _make_forest(
    spec: dict[str, Any],
    seed: int,
    cv_splits: list[tuple[np.ndarray, np.ndarray]],
    n_jobs: int,
) -> Any:
    from econml.dml import CausalForestDML
    from sklearn.linear_model import LogisticRegression

    return CausalForestDML(
        model_y=LogisticRegression(max_iter=2000, solver="lbfgs"),
        model_t=LogisticRegression(max_iter=2000, solver="lbfgs"),
        discrete_outcome=True,
        discrete_treatment=True,
        categories=[0, 1],
        cv=cv_splits,
        n_estimators=400,
        criterion="mse",
        max_depth=spec["max_depth"],
        min_samples_split=20,
        min_samples_leaf=spec["min_samples_leaf"],
        max_samples=0.45,
        min_balancedness_tol=0.25,
        honest=True,
        inference=True,
        n_jobs=n_jobs,
        random_state=seed,
    )


def fit_and_evaluate(config: ExperimentConfig) -> dict[str, Any]:
    """Fit on train, choose forest spec on validation, and evaluate test once."""
    write_json(
        config.output_dir / "experiment_config.json",
        _jsonable(asdict(config)),
    )
    readiness = assess_readiness(config)
    if readiness["blockers"]:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        write_json(config.output_dir / "experiment_status.json", readiness)
        raise RuntimeError("Experiment blocked: " + " ".join(readiness["blockers"]))

    all_features = tuple(dict.fromkeys((*config.features, *config.sensitivity_features)))
    frames = {
        split: load_split(
            config.data_dir,
            split,
            config.outcome,
            config.treatment,
            config.eligibility,
            all_features,
        )
        for split in SPLITS
    }
    split_overlap = validate_patient_splits(frames)
    preliminary, source_frames, observed_probability, diagnostic_models = (
        _preliminary_and_censoring_analysis(
            config,
            frames,
            config.features,
        )
    )
    config.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        config.output_dir / "preliminary_metrics.json",
        _jsonable(preliminary),
    )
    pd.DataFrame(
        [
            {
                "split": split,
                "feature": feature,
                **diagnostics["covariate_balance_smd"][feature],
            }
            for split, diagnostics in preliminary["split_summary"].items()
            for feature in config.features
        ]
    ).to_csv(config.output_dir / "preliminary_covariate_balance.csv", index=False)
    cohorts: dict[str, pd.DataFrame] = {}
    cohort_stats: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        cohorts[split], cohort_stats[split] = build_admission_cohort(
            frames[split],
            config.outcome,
            config.treatment,
            config.eligibility,
            all_features,
        )
    features = tuple(
        feature
        for feature in config.features
        if cohorts["train"][feature].nunique() > 1
    )
    if not features:
        raise ValueError("No non-constant baseline features in the training cohort.")

    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    import joblib

    train = cohorts["train"]
    validation = cohorts["validation"]
    test = cohorts["test"]
    x_train = train.loc[:, features]
    x_validation = validation.loc[:, features]
    x_test = test.loc[:, features]
    y_train = train[config.outcome].to_numpy()
    y_validation = validation[config.outcome].to_numpy()
    y_test = test[config.outcome].to_numpy()
    t_train = train[config.treatment].to_numpy()
    t_validation = validation[config.treatment].to_numpy()
    t_test = test[config.treatment].to_numpy()
    if any(np.unique(values).size != 2 for values in (y_train, t_train, y_validation, t_validation, y_test, t_test)):
        raise ValueError("Every split must contain both binary outcome and treatment values.")

    group_kfold = GroupKFold(n_splits=config.cv_folds)
    train_cv = list(
        group_kfold.split(x_train, t_train, groups=train["SubjectID"])
    )
    for fit_indices, heldout_indices in train_cv:
        fit_patients = set(train.iloc[fit_indices]["SubjectID"])
        heldout_patients = set(train.iloc[heldout_indices]["SubjectID"])
        if fit_patients & heldout_patients:
            raise ValueError("Patient overlap found in nuisance cross-fitting folds.")

    outcome_model = LogisticRegression(max_iter=2000, solver="lbfgs")
    outcome_model.fit(
        train.loc[:, [*features, config.treatment]],
        y_train,
    )
    baseline_test = test.loc[:, [*features, config.treatment]].copy()
    baseline_test[config.treatment] = 0
    baseline_risk_test = outcome_model.predict_proba(baseline_test)[:, 1]
    treated_baseline_test = test.loc[:, [*features, config.treatment]].copy()
    treated_baseline_test[config.treatment] = 1
    baseline_risk_statin_test = outcome_model.predict_proba(
        treated_baseline_test
    )[:, 1]
    logistic_gcomp_ate = float(
        np.mean(baseline_risk_statin_test - baseline_risk_test)
    )
    logistic_gcomp_interval = _cluster_bootstrap_gcomp_interval(
        test,
        baseline_risk_test,
        baseline_risk_statin_test,
        config.bootstrap_replicates,
        config.seed + 23,
    )
    outcome_probability_test = outcome_model.predict_proba(
        test.loc[:, [*features, config.treatment]]
    )[:, 1]

    propensity_model = LogisticRegression(max_iter=2000, solver="lbfgs")
    propensity_model.fit(x_train, t_train)
    propensity_test = propensity_model.predict_proba(x_test)[:, 1]
    ps_ate, ipw = _weighted_ate(
        test,
        propensity_test,
        config.outcome,
        config.treatment,
    )
    ps_interval = _cluster_bootstrap_interval(
        test,
        propensity_test,
        config.outcome,
        config.treatment,
        config.bootstrap_replicates,
        config.seed,
    )
    smd_before = _standardized_mean_differences(test, config.treatment, features)
    smd_after = _standardized_mean_differences(test, config.treatment, features, ipw)
    ipcw_results = _ipcw_sensitivity(
        test,
        source_frames["test"].copy(),
        propensity_test,
        observed_probability["test"],
        config,
        config.outcome,
        config.treatment,
    )
    ipcw_weights = ipcw_results.pop("_ipcw_weights")
    combined_ipcw_weights = ipcw_results.pop("_combined_weights")

    candidate_results: list[dict[str, Any]] = []
    for spec in config.forest_specs:
        forest = _make_forest(spec, config.seed, train_cv, config.n_jobs)
        forest.fit(
            y_train,
            t_train,
            X=x_train,
            groups=train["SubjectID"].to_numpy(),
        )
        validation_score = float(
            forest.score(
                y_validation,
                t_validation,
                X=x_validation,
            )
        )
        candidate_results.append(
            {"spec": spec, "validation_r_loss": validation_score}
        )
    best_index = int(np.argmin([item["validation_r_loss"] for item in candidate_results]))
    selected_spec = config.forest_specs[best_index]

    train_validation = pd.concat([train, validation], ignore_index=True)
    x_train_validation = train_validation.loc[:, features]
    t_train_validation = train_validation[config.treatment].to_numpy()
    combined_cv = list(
        group_kfold.split(
            x_train_validation,
            t_train_validation,
            groups=train_validation["SubjectID"],
        )
    )
    forest = _make_forest(selected_spec, config.seed, combined_cv, config.n_jobs)
    forest.fit(
        train_validation[config.outcome].to_numpy(),
        t_train_validation,
        X=x_train_validation,
        groups=train_validation["SubjectID"].to_numpy(),
    )
    cate = np.asarray(forest.effect(x_test, T0=0, T1=1)).reshape(-1)
    cate_lower, cate_upper = forest.effect_interval(x_test, T0=0, T1=1, alpha=0.05)
    cate_lower = np.asarray(cate_lower).reshape(-1)
    cate_upper = np.asarray(cate_upper).reshape(-1)
    ate = _scalar_float(forest.ate(X=x_test, T0=0, T1=1))
    ate_interval = forest.ate_interval(X=x_test, T0=0, T1=1, alpha=0.05)
    ate_lower, ate_upper = (float(np.asarray(value).squeeze()) for value in ate_interval)

    sensitivity_results: list[dict[str, Any]] = []
    for spec in config.forest_specs:
        if spec == selected_spec:
            continue
        alternative = _make_forest(spec, config.seed, combined_cv, config.n_jobs)
        alternative.fit(
            train_validation[config.outcome].to_numpy(),
            t_train_validation,
            X=x_train_validation,
            groups=train_validation["SubjectID"].to_numpy(),
        )
        alternative_cate = np.asarray(
            alternative.effect(x_test, T0=0, T1=1)
        ).reshape(-1)
        sensitivity_results.append(
            {
                "spec": spec,
                "test_ate": _scalar_float(
                    alternative.ate(X=x_test, T0=0, T1=1)
                ),
                "test_cate_correlation_with_selected": float(
                    np.corrcoef(cate, alternative_cate)[0, 1]
                ),
                "mean_absolute_cate_difference": float(
                    np.mean(np.abs(cate - alternative_cate))
                ),
            }
        )
    statin_history_features = tuple(
        feature
        for feature in config.sensitivity_features
        if cohorts["train"][feature].nunique() > 1
    )
    if "statin_before" in statin_history_features and "statin_before" not in features:
        history_model = _make_forest(
            selected_spec,
            config.seed,
            combined_cv,
            config.n_jobs,
        )
        history_model.fit(
            train_validation[config.outcome].to_numpy(),
            t_train_validation,
            X=train_validation.loc[:, statin_history_features],
            groups=train_validation["SubjectID"].to_numpy(),
        )
        history_cate = np.asarray(
            history_model.effect(
                test.loc[:, statin_history_features],
                T0=0,
                T1=1,
            )
        ).reshape(-1)
        sensitivity_results.append(
            {
                "spec": "include_statin_before_proxy",
                "features": list(statin_history_features),
                "test_ate": _scalar_float(
                    history_model.ate(
                        X=test.loc[:, statin_history_features],
                        T0=0,
                        T1=1,
                    )
                ),
                "test_cate_correlation_with_primary": float(
                    np.corrcoef(cate, history_cate)[0, 1]
                ),
                "mean_absolute_cate_difference": float(
                    np.mean(np.abs(cate - history_cate))
                ),
            }
        )
    subgroup_results = _subgroup_effects(test, x_test, forest, config.treatment)

    predictions = test.loc[
        :, ["SubjectID", "hadm_id", config.treatment, config.outcome, *features]
    ].copy()
    predictions["propensity_score"] = propensity_test
    predictions["ipcw_weight"] = ipcw_weights
    predictions["combined_treatment_ipcw_weight"] = combined_ipcw_weights
    predictions["baseline_risk_no_statin"] = baseline_risk_test
    predictions["baseline_risk_statin"] = baseline_risk_statin_test
    predictions["cate"] = cate
    predictions["cate_lower_95"] = cate_lower
    predictions["cate_upper_95"] = cate_upper

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "outcome_model": outcome_model,
            "propensity_model": propensity_model,
            **diagnostic_models,
            "causal_forest": forest,
            "features": features,
            "selected_forest_spec": selected_spec,
        },
        output_dir / "models.joblib",
    )
    predictions.to_parquet(output_dir / "test_predictions.parquet", index=False)
    pd.DataFrame(
        {
            "feature": features,
            "smd_before": [smd_before[feature] for feature in features],
            "smd_after_ipw": [smd_after[feature] for feature in features],
        }
    ).to_csv(output_dir / "covariate_balance.csv", index=False)
    pd.DataFrame(subgroup_results).to_csv(
        output_dir / "subgroup_effects.csv",
        index=False,
    )

    metrics = {
        "status": "model_estimates_not_established_clinical_effects",
        "split_patient_overlap": split_overlap,
        "cohort_sizes": {
            split: {
                **cohort_stats[split],
                "treated": int(cohorts[split][config.treatment].eq(1).sum()),
                "control": int(cohorts[split][config.treatment].eq(0).sum()),
                "outcome_events": int(cohorts[split][config.outcome].sum()),
                "patients": int(cohorts[split]["SubjectID"].nunique()),
            }
            for split in SPLITS
        },
        "preliminary_source_cohort": preliminary["split_summary"],
        "censoring_assessment": preliminary["censoring_assessment"],
        "complete_case_analysis": {
            "interpretation": (
                "Exploratory complete-case analysis restricted to admissions with "
                "observed outcome follow-up and required baseline covariates."
            ),
            "train_admissions": len(train),
            "validation_admissions": len(validation),
            "test_admissions": len(test),
            "test_outcome_prevalence": float(y_test.mean()),
            "test_treatment_prevalence": float(t_test.mean()),
            "test_propensity_ipw_ate": {
                "estimate": ps_ate,
                "patient_cluster_bootstrap_95_interval": list(ps_interval),
            },
            "test_logistic_g_computation_ate": {
                "estimate": logistic_gcomp_ate,
                "patient_cluster_bootstrap_95_interval": list(
                    logistic_gcomp_interval
                ),
                "description": (
                    "Standardized logistic-model risk difference over the test "
                    "covariate distribution; interval resamples test patients."
                ),
            },
        },
        "preflight_status": readiness["status"],
        "preflight_warnings": readiness["warnings"],
        "censoring_sensitivity": ipcw_results,
        "features": list(features),
        "software_versions": _package_versions(),
        "feature_notes": FEATURE_NOTES,
        "subgroup_effects": subgroup_results,
        "test_outcome_metrics": _classification_metrics(y_test, outcome_probability_test),
        "test_propensity_auc": float(
            roc_auc_score(t_test, propensity_test)
        ),
        "test_propensity_overlap": {
            "treated_quantiles": np.quantile(
                propensity_test[t_test == 1], [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
            ).tolist(),
            "control_quantiles": np.quantile(
                propensity_test[t_test == 0], [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
            ).tolist(),
            "fraction_outside_common_support": float(
                np.mean(
                    (propensity_test < max(propensity_test[t_test == 0].min(), propensity_test[t_test == 1].min()))
                    | (propensity_test > min(propensity_test[t_test == 0].max(), propensity_test[t_test == 1].max()))
                )
            ),
            "effective_sample_size_ipw": float(ipw.sum() ** 2 / np.square(ipw).sum()),
        },
        "propensity_ipw_ate": {
            "estimate": ps_ate,
            "cluster_bootstrap_95_interval": list(ps_interval),
            "smd_before": smd_before,
            "smd_after": smd_after,
        },
        "causal_forest": {
            "validation_candidates": candidate_results,
            "selected_spec": selected_spec,
            "sensitivity_specs": sensitivity_results,
            "ate": ate,
            "ate_95_interval": [ate_lower, ate_upper],
            "cate_distribution": {
                "mean": float(cate.mean()),
                "std": float(cate.std(ddof=1)),
                "quantiles": np.quantile(cate, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).tolist(),
            },
            "heterogeneity_sd": float(cate.std(ddof=1)),
            "ate_vs_propensity_sensitivity_difference": float(ate - ps_ate),
        },
        "interpretation": (
            "Estimates rely on conditional exchangeability, positivity, consistency, "
            "correct temporal ordering, and accurate outcome/treatment measurement; "
            "predictive performance does not establish these assumptions. The "
            "complete-case analysis is exploratory; IPCW additionally requires "
            "conditional independent censoring and censoring positivity."
        ),
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "experiment_config.json", _jsonable(asdict(config)))
    _write_experiment_report(
        output_dir / "experiment_report.md",
        metrics,
        metrics["software_versions"],
    )
    _write_figures(
        output_dir,
        test,
        config,
        features,
        propensity_test,
        smd_before,
        smd_after,
        cate,
        cate_lower,
        cate_upper,
        baseline_risk_test,
        outcome_probability_test,
        predictions,
        subgroup_results,
    )
    return metrics


def _write_figures(
    output_dir: Path,
    test: pd.DataFrame,
    config: ExperimentConfig,
    features: tuple[str, ...],
    propensity: np.ndarray,
    smd_before: dict[str, float],
    smd_after: dict[str, float],
    cate: np.ndarray,
    cate_lower: np.ndarray,
    cate_upper: np.ndarray,
    baseline_risk: np.ndarray,
    outcome_probability: np.ndarray,
    predictions: pd.DataFrame,
    subgroup_results: list[dict[str, Any]],
) -> None:
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    treatment = test[config.treatment].to_numpy()
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(7, 5))
    for value, label, color in ((0, "Control", "#4472C4"), (1, "Treated", "#C44E52")):
        axis.hist(propensity[treatment == value], bins=30, density=True, alpha=0.45, label=label, color=color)
    axis.set(xlabel="Estimated propensity score", ylabel="Density", title="Propensity-score overlap (test)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "propensity_overlap.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, max(4, len(features) * 0.35)))
    positions = np.arange(len(features))
    axis.scatter([abs(smd_before[name]) for name in features], positions, label="Before", marker="o")
    axis.scatter([abs(smd_after[name]) for name in features], positions, label="After IPW", marker="x")
    axis.axvline(0.1, color="red", linestyle="--", linewidth=1)
    axis.set_yticks(positions, features)
    axis.invert_yaxis()
    axis.set(xlabel="Absolute standardized mean difference", title="Covariate balance (test)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "covariate_balance.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7, 5))
    axis.hist(cate, bins=35, color="#4C72B0", alpha=0.8)
    axis.axvline(0, color="black", linewidth=1)
    axis.set(xlabel="Estimated CATE (risk difference)", ylabel="Admissions", title="CATE distribution (test)")
    figure.tight_layout()
    figure.savefig(figure_dir / "cate_distribution.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(7, 5))
    axis.scatter(baseline_risk, cate, alpha=0.3, s=12)
    axis.axhline(0, color="black", linewidth=1)
    axis.set(xlabel="Baseline predicted risk without statin", ylabel="Estimated CATE", title="CATE versus baseline risk")
    figure.tight_layout()
    figure.savefig(figure_dir / "cate_vs_baseline_risk.png", dpi=160)
    plt.close(figure)

    subgroup_rows = [
        row
        for row in subgroup_results
        if row["status"] == "model_estimate"
    ]
    figure, axis = plt.subplots(figsize=(8, max(4, len(subgroup_rows) * 0.55)))
    for row_index, row in enumerate(subgroup_rows):
        estimate = row["ate"]
        lower = row["ci_lower_95"]
        upper = row["ci_upper_95"]
        axis.errorbar(
            estimate,
            row_index,
            xerr=[[estimate - lower], [upper - estimate]],
            fmt="o",
        )
    axis.axvline(0, color="black", linewidth=1)
    axis.set_yticks(range(len(subgroup_rows)), [row["subgroup"] for row in subgroup_rows])
    axis.invert_yaxis()
    axis.set(xlabel="Model-estimated subgroup effect", title="Subgroup effects (test)")
    figure.tight_layout()
    figure.savefig(figure_dir / "subgroup_effects.png", dpi=160)
    plt.close(figure)

    sample_indices = np.argsort(cate)
    if len(sample_indices) > 250:
        sample_indices = sample_indices[np.linspace(0, len(sample_indices) - 1, 250).astype(int)]
    figure, axis = plt.subplots(figsize=(9, 5))
    axis.errorbar(
        np.arange(len(sample_indices)),
        cate[sample_indices],
        yerr=[
            cate[sample_indices] - cate_lower[sample_indices],
            cate_upper[sample_indices] - cate[sample_indices],
        ],
        fmt=".",
        alpha=0.6,
        capsize=1,
    )
    axis.axhline(0, color="black", linewidth=1)
    axis.set(xlabel="Test admissions sorted by CATE", ylabel="CATE with 95% interval", title="Treatment-effect uncertainty")
    figure.tight_layout()
    figure.savefig(figure_dir / "cate_uncertainty.png", dpi=160)
    plt.close(figure)

    fraction_positive, mean_predicted = calibration_curve(
        predictions[config.outcome].to_numpy(),
        outcome_probability,
        n_bins=10,
        strategy="quantile",
    )
    figure, axis = plt.subplots(figsize=(6, 6))
    axis.plot(mean_predicted, fraction_positive, marker="o")
    axis.plot([0, 1], [0, 1], linestyle="--", color="black")
    axis.set(xlabel="Mean predicted risk", ylabel="Observed outcome rate", title="Outcome-model calibration")
    figure.tight_layout()
    figure.savefig(figure_dir / "outcome_calibration.png", dpi=160)
    plt.close(figure)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, allow_nan=False),
        encoding="utf-8",
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        converted = float(value)
        return converted if np.isfinite(converted) else None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fit a statin CausalForestDML only after outcome/timing prerequisites validate."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("master"))
    parser.add_argument(
        "--source-cohort",
        type=Path,
        default=Path("causal_models/data/statin_recurrent_mi_cohort.parquet"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("causal_models/outputs/causal_forest"),
    )
    parser.add_argument("--outcome", default=OUTCOME)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--bootstrap-replicates", type=int, default=500)
    parser.add_argument(
        "--recurrence-outcome-validated",
        action="store_true",
        help="Assert that the selected outcome is a verified subsequent/recurrent-MI endpoint.",
    )
    parser.add_argument(
        "--temporal-order-validated",
        action="store_true",
        help="Assert that statin assignment precedes the recurrent-MI follow-up window.",
    )
    parser.add_argument(
        "--allow-exploratory-estimation",
        action="store_true",
        help=(
            "Fit despite unvalidated endpoint/timing assumptions; retain explicit "
            "warnings and do not claim a clinical causal effect."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = ExperimentConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        source_cohort_path=args.source_cohort,
        outcome=args.outcome,
        recurrence_outcome_validated=args.recurrence_outcome_validated,
        temporal_order_validated=args.temporal_order_validated,
        allow_exploratory_estimation=args.allow_exploratory_estimation,
        seed=args.seed,
        n_jobs=args.n_jobs,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    write_json(
        config.output_dir / "experiment_config.json",
        _jsonable(asdict(config)),
    )
    readiness = assess_readiness(config)
    if readiness["blockers"]:
        write_json(config.output_dir / "experiment_status.json", readiness)
        LOGGER.error("Statin causal forest blocked: %s", "; ".join(readiness["blockers"]))
        return 2
    try:
        metrics = fit_and_evaluate(config)
    except (ValueError, RuntimeError, ImportError) as error:
        LOGGER.exception("Statin causal forest failed.")
        write_json(
            config.output_dir / "experiment_status.json",
            {"status": "failed", "error": str(error), "model_fitted": False},
        )
        return 1
    LOGGER.info(
        "Completed model-estimated CATE experiment; outputs: %s",
        config.output_dir,
    )
    write_json(
        config.output_dir / "experiment_status.json",
        {"status": "completed", "model_fitted": True, "metrics_file": "metrics.json"},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
