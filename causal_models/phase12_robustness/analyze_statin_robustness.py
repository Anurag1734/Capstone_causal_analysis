from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE11_DIR = ROOT / "causal_models" / "outputs" / "causal_forest"
DEFAULT_COHORT = ROOT / "causal_models" / "data" / "statin_recurrent_mi_cohort.parquet"
DEFAULT_SPLITS = ROOT / "causal_models" / "data" / "statin_recurrent_mi_forest_splits"
FEATURES = (
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "aspirin_before",
    "beta_blocker_before",
    "acei_before",
)
TRUNCATION_LEVELS = {
    "p01_p99": (0.01, 0.99),
    "p05_p95": (0.05, 0.95),
}
BOOTSTRAP_REPLICATES = 1000
SEED = 20261212


def _as_float(value: Any) -> float:
    return float(np.asarray(value, dtype=float).reshape(-1)[0])


def _arm_weights(
    weights: np.ndarray,
    treatment: np.ndarray,
    limits: tuple[float, float] | None = None,
) -> np.ndarray:
    values = np.asarray(weights, dtype=float).copy()
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Weights must be finite and strictly positive.")
    if limits is None:
        return values
    lower_q, upper_q = limits
    if not 0 <= lower_q < upper_q <= 1:
        raise ValueError("Weight truncation quantiles must satisfy 0 <= lower < upper <= 1.")
    for arm in (0, 1):
        arm_mask = treatment == arm
        if not arm_mask.any():
            raise ValueError(f"No observations found for treatment arm {arm}.")
        lower, upper = np.quantile(values[arm_mask], [lower_q, upper_q])
        values[arm_mask] = np.clip(values[arm_mask], lower, upper)
    return values


def _global_winsorize(
    weights: np.ndarray,
    limits: tuple[float, float] | None,
) -> np.ndarray:
    values = np.asarray(weights, dtype=float).copy()
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Weights must be finite and strictly positive.")
    if limits is None:
        return values
    lower_q, upper_q = limits
    if not 0 <= lower_q < upper_q <= 1:
        raise ValueError("Weight truncation quantiles must satisfy 0 <= lower < upper <= 1.")
    lower, upper = np.quantile(values, [lower_q, upper_q])
    return np.clip(values, lower, upper)


def effective_sample_size(weights: np.ndarray) -> float:
    weights = np.asarray(weights, dtype=float)
    if weights.size == 0 or not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("ESS requires a nonempty finite, nonnegative weight vector.")
    total = weights.sum()
    squared = np.square(weights).sum()
    return float(total**2 / squared) if squared > 0 else 0.0


def weight_diagnostic_rows(
    name: str,
    weights: np.ndarray,
    treatment: np.ndarray,
) -> list[dict[str, Any]]:
    weights = np.asarray(weights, dtype=float)
    treatment = np.asarray(treatment, dtype=int)
    if weights.shape != treatment.shape:
        raise ValueError("Weights and treatment must have matching shapes.")
    rows: list[dict[str, Any]] = []
    total_weight = weights.sum()
    for arm_name, mask in (
        ("all", np.ones(len(weights), dtype=bool)),
        ("control", treatment == 0),
        ("treated", treatment == 1),
    ):
        arm_weights = weights[mask]
        if not arm_weights.size:
            continue
        top_count = max(1, math.ceil(len(arm_weights) * 0.01))
        top_share_arm = float(np.sort(arm_weights)[-top_count:].sum() / arm_weights.sum())
        top_share_total = float(np.sort(arm_weights)[-top_count:].sum() / total_weight)
        quantiles = np.quantile(arm_weights, [0.5, 0.95, 0.99])
        rows.append(
            {
                "weight_type": name,
                "group": arm_name,
                "n": int(len(arm_weights)),
                "minimum": float(arm_weights.min()),
                "maximum": float(arm_weights.max()),
                "median": float(quantiles[0]),
                "p95": float(quantiles[1]),
                "p99": float(quantiles[2]),
                "ess": effective_sample_size(arm_weights),
                "top_1pct_share_of_group_weight": top_share_arm,
                "top_1pct_share_of_total_weight": top_share_total,
            }
        )
    return rows


def propensity_overlap_rows(
    propensity: np.ndarray,
    treatment: np.ndarray,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    propensity = np.asarray(propensity, dtype=float)
    treatment = np.asarray(treatment, dtype=int)
    if propensity.shape != treatment.shape:
        raise ValueError("Propensity and treatment arrays must have matching shapes.")
    if not np.isfinite(propensity).all() or ((propensity < 0) | (propensity > 1)).any():
        raise ValueError("Propensity scores must be finite and in [0, 1].")
    quantile_levels = [0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 1.0]
    rows: list[dict[str, Any]] = []
    group_values: dict[int, np.ndarray] = {}
    by_group: dict[str, Any] = {}
    for arm in (0, 1):
        values = propensity[treatment == arm]
        if not values.size:
            raise ValueError(f"No observations found for treatment arm {arm}.")
        group_values[arm] = values
        quantiles = np.quantile(values, quantile_levels)
        by_group["treated" if arm else "control"] = {
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "median": float(np.median(values)),
            "quantiles": {
                f"p{int(level * 100):02d}": float(value)
                for level, value in zip(quantile_levels, quantiles)
            },
        }
        rows.extend(
            {
                "group": "treated" if arm else "control",
                "statistic": "propensity_quantile",
                "quantile": f"p{int(level * 100):02d}",
                "quantile_level": level,
                "value": float(value),
                "n": int(len(values)),
            }
            for level, value in zip(quantile_levels, quantiles)
        )
    lower = max(group_values[0].min(), group_values[1].min())
    upper = min(group_values[0].max(), group_values[1].max())
    outside = (propensity < lower) | (propensity > upper)
    summary = {
        "common_support": [float(lower), float(upper)],
        "outside_common_support_n": int(outside.sum()),
        "outside_common_support_percent": float(100 * outside.mean()),
        "outside_common_support_by_group": {
            "control": int(np.sum(outside & (treatment == 0))),
            "treated": int(np.sum(outside & (treatment == 1))),
        },
        "near_extreme_thresholds": {
            "less_than_0_01": int(np.sum(propensity < 0.01)),
            "greater_than_0_99": int(np.sum(propensity > 0.99)),
            "less_than_0_05": int(np.sum(propensity < 0.05)),
            "greater_than_0_95": int(np.sum(propensity > 0.95)),
            "less_than_0_10": int(np.sum(propensity < 0.10)),
            "greater_than_0_90": int(np.sum(propensity > 0.90)),
        },
        "score_minimum": float(propensity.min()),
        "score_maximum": float(propensity.max()),
        "score_median": float(np.median(propensity)),
        "sample_size": int(len(propensity)),
        "treated": int(np.sum(treatment == 1)),
        "control": int(np.sum(treatment == 0)),
        "by_group": by_group,
    }
    return rows, summary


def weighted_risk_difference(
    outcome: np.ndarray,
    treatment: np.ndarray,
    weights: np.ndarray,
) -> float:
    outcome = np.asarray(outcome, dtype=float)
    treatment = np.asarray(treatment, dtype=int)
    weights = np.asarray(weights, dtype=float)
    if not (outcome.shape == treatment.shape == weights.shape):
        raise ValueError("Outcome, treatment, and weights must have matching shapes.")
    if not np.isfinite(outcome).all() or not np.isin(outcome, [0, 1]).all():
        raise ValueError("Observed outcomes must be binary and finite.")
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Weights must be finite and strictly positive.")
    if not np.isin(treatment, [0, 1]).all() or np.unique(treatment).size != 2:
        raise ValueError("Both binary treatment arms must be represented.")
    return float(
        np.average(outcome[treatment == 1], weights=weights[treatment == 1])
        - np.average(outcome[treatment == 0], weights=weights[treatment == 0])
    )


def cluster_bootstrap_interval(
    frame: pd.DataFrame,
    weights: np.ndarray,
    weight_strategy: str,
    censor_weights: np.ndarray,
    treatment_weights: np.ndarray,
    treatment: np.ndarray,
    outcome: np.ndarray,
    limits: tuple[float, float] | None,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> list[float]:
    patient_ids = frame["SubjectID"].to_numpy()
    unique_patients = pd.unique(patient_ids)
    if len(unique_patients) != len(patient_ids):
        raise ValueError("The test bootstrap input must contain one row per patient.")
    rows_by_patient = {
        patient: np.flatnonzero(patient_ids == patient) for patient in unique_patients
    }
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        sampled = rng.choice(unique_patients, size=len(unique_patients), replace=True)
        indices = np.concatenate([rows_by_patient[patient] for patient in sampled])
        sampled_treatment = treatment[indices]
        if np.unique(sampled_treatment).size != 2:
            continue
        if weight_strategy == "treatment_ipw":
            raw = treatment_weights[indices]
            sampled_weights = _arm_weights(raw, sampled_treatment, limits)
        elif weight_strategy == "combined_final":
            raw = treatment_weights[indices] * censor_weights[indices]
            sampled_weights = _arm_weights(raw, sampled_treatment, limits)
        elif weight_strategy == "censor_component":
            sampled_censor = _global_winsorize(censor_weights[indices], limits)
            sampled_weights = treatment_weights[indices] * sampled_censor
        else:
            raise ValueError(f"Unknown bootstrap weighting strategy: {weight_strategy}")
        estimates.append(
            weighted_risk_difference(
                outcome[indices],
                sampled_treatment,
                sampled_weights,
            )
        )
    if len(estimates) < max(30, replicates // 2):
        raise ValueError("Too few valid patient-cluster bootstrap replicates.")
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return [float(lower), float(upper)]


def cate_summary(predictions: pd.DataFrame, phase11_metrics: dict[str, Any]) -> dict[str, Any]:
    cate = predictions["cate"].to_numpy(dtype=float)
    if not np.isfinite(cate).all():
        raise ValueError("CATE predictions contain non-finite values.")
    quantiles = np.quantile(cate, [0.10, 0.25, 0.50, 0.75, 0.90])
    return {
        "n": int(len(cate)),
        "mean": float(cate.mean()),
        "median": float(quantiles[2]),
        "standard_deviation": float(cate.std(ddof=1)),
        "quantiles": {
            "p10": float(quantiles[0]),
            "p25": float(quantiles[1]),
            "p50": float(quantiles[2]),
            "p75": float(quantiles[3]),
            "p90": float(quantiles[4]),
        },
        "individual_interval_95_mean_lower": float(
            predictions["cate_lower_95"].mean()
        ),
        "individual_interval_95_mean_upper": float(
            predictions["cate_upper_95"].mean()
        ),
        "population_ate_95_interval": phase11_metrics["causal_forest"][
            "ate_95_interval"
        ],
        "population_ate": phase11_metrics["causal_forest"]["ate"],
        "note": (
            "Individual CATE intervals are the stored forest prediction intervals; "
            "the population interval is the Phase 11 forest ATE interval. CATE "
            "spread alone is not evidence of clinically meaningful heterogeneity."
        ),
    }


def _summary_distribution(name: str, values: np.ndarray) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    if not values.size or not np.isfinite(values).all():
        raise ValueError(f"{name} must be a nonempty finite vector.")
    probs = [0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99, 1.0]
    quantiles = np.quantile(values, probs)
    return {
        "measure": name,
        "n": int(len(values)),
        **{
            f"p{int(prob * 100):02d}": float(value)
            for prob, value in zip(probs, quantiles)
        },
        "mean": float(values.mean()),
    }


def _bootstrap_comparison_row(
    *,
    name: str,
    estimand: str,
    frame: pd.DataFrame,
    outcome: np.ndarray,
    treatment: np.ndarray,
    raw_weights: np.ndarray,
    treatment_weights: np.ndarray,
    censor_weights: np.ndarray,
    weight_strategy: str,
    limits: tuple[float, float] | None,
    truncation_name: str,
    risk_set_n: int | None = None,
    incomplete_followup_n: int = 0,
    test_split_n: int | None = None,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    if weight_strategy == "treatment_ipw":
        weights = _arm_weights(raw_weights, treatment, limits)
    elif weight_strategy == "combined_final":
        weights = _arm_weights(raw_weights, treatment, limits)
    elif weight_strategy == "censor_component":
        truncated_censor = _global_winsorize(censor_weights, limits)
        weights = treatment_weights * truncated_censor
    else:
        raise ValueError(f"Unknown weighting strategy: {weight_strategy}")
    estimate = weighted_risk_difference(outcome, treatment, weights)
    interval = cluster_bootstrap_interval(
        frame,
        weights,
        weight_strategy,
        censor_weights,
        treatment_weights,
        treatment,
        outcome,
        limits,
        replicates,
        seed,
    )
    return {
        "estimator": name,
        "estimand_population": estimand,
        "risk_difference": estimate,
        "risk_difference_pp": 100 * estimate,
        "ci_lower_95": interval[0],
        "ci_upper_95": interval[1],
        "ci_lower_95_pp": 100 * interval[0],
        "ci_upper_95_pp": 100 * interval[1],
        "n": int(len(frame)),
        "risk_set_n": int(risk_set_n if risk_set_n is not None else len(frame)),
        "incomplete_followup_n": int(incomplete_followup_n),
        "treated_n": int(np.sum(treatment == 1)),
        "control_n": int(np.sum(treatment == 0)),
        "excluded_from_test_split": (
            int(
                test_split_n
                - (risk_set_n if risk_set_n is not None else len(frame))
            )
            if test_split_n is not None
            else None
        ),
        "ess_all": effective_sample_size(weights),
        "ess_treated": effective_sample_size(weights[treatment == 1]),
        "ess_control": effective_sample_size(weights[treatment == 0]),
        "weighting_specification": truncation_name,
        "ci_method": "patient-cluster percentile bootstrap; truncation cutoffs re-estimated per replicate",
    }


def _load_phase11_artifacts(
    phase11_dir: Path,
    cohort_path: Path,
    split_dir: Path,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    dict[str, Any],
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    required = [
        phase11_dir / "models.joblib",
        phase11_dir / "test_predictions.parquet",
        phase11_dir / "metrics.json",
        cohort_path,
        split_dir / "test.parquet",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Required Phase 11 artifacts are missing: {missing}")
    model_bundle = joblib.load(phase11_dir / "models.joblib")
    predictions = pd.read_parquet(phase11_dir / "test_predictions.parquet")
    metrics = json.loads((phase11_dir / "metrics.json").read_text(encoding="utf-8"))
    cohort = pd.read_parquet(cohort_path)
    test_split = pd.read_parquet(split_dir / "test.parquet")
    test_keys = set(
        zip(test_split["SubjectID"].astype("int64"), test_split["hadm_id"])
    )
    cohort["SubjectID"] = cohort["subject_id"].astype("int64")
    source_test = cohort.loc[
        [
            key in test_keys
            for key in zip(cohort["SubjectID"], cohort["hadm_id"])
        ]
    ].copy()
    if len(source_test) != len(test_split):
        raise ValueError("Source cohort does not align one-to-one with the existing test split.")
    source_test["SubjectID"] = source_test["subject_id"].astype("int64")
    split_keys = set(zip(test_split["SubjectID"].astype("int64"), test_split["hadm_id"]))
    source_keys = set(zip(source_test["SubjectID"], source_test["hadm_id"]))
    if split_keys != source_keys:
        raise ValueError("Source cohort patient/admission keys differ from the existing test split.")
    features = tuple(model_bundle["features"])
    eligible = (
        test_split["statin_during"].notna()
        & test_split.loc[:, list(features)].notna().all(axis=1)
    )
    analysis_source = source_test.set_index(["SubjectID", "hadm_id"])
    eligible_split = test_split.loc[eligible].copy()
    eligible_keys = pd.MultiIndex.from_frame(
        eligible_split[["SubjectID", "hadm_id"]]
    )
    aligned_source = analysis_source.reindex(eligible_keys)
    if aligned_source["event_type"].isna().any():
        raise ValueError("Eligible source cohort records failed patient/admission alignment.")
    censor_model = model_bundle["censoring_model"]
    predicted_observed = censor_model.predict_proba(
        eligible_split.loc[:, [*features, "statin_during"]]
    )[:, 1]
    observed_indicator = (~aligned_source["event_type"].eq("incomplete_followup")).to_numpy()
    marginal_observation = float(observed_indicator.mean())
    censor_weights = marginal_observation / np.clip(predicted_observed, 0.05, 1.0)
    obs_probability_by_key = pd.Series(predicted_observed, index=eligible_keys)
    complete_case_keys = pd.MultiIndex.from_frame(
        predictions[["SubjectID", "hadm_id"]]
    )
    if not complete_case_keys.isin(eligible_keys).all():
        raise ValueError("Phase 11 complete-case predictions are not within the censoring risk set.")
    predicted_observed_cc = obs_probability_by_key.reindex(complete_case_keys).to_numpy()
    observed_fraction = marginal_observation
    recovered_ipcw = observed_fraction / np.clip(predicted_observed_cc, 0.05, 1.0)
    if not np.allclose(recovered_ipcw, predictions["ipcw_weight"].to_numpy(), rtol=1e-8, atol=1e-8):
        raise ValueError("Saved Phase 11 IPCW weights do not match the saved censoring model.")
    if not np.allclose(
        recovered_ipcw * (1.0 / np.where(
            predictions["statin_during"].to_numpy(dtype=int) == 1,
            predictions["propensity_score"].to_numpy(),
            1.0 - predictions["propensity_score"].to_numpy(),
        )),
        predictions["combined_treatment_ipcw_weight"].to_numpy(),
        rtol=1e-8,
        atol=1e-8,
    ):
        raise ValueError("Saved combined weights do not match saved treatment and censoring weights.")
    test_cate = np.asarray(
        model_bundle["causal_forest"].effect(
            predictions.loc[:, list(features)],
            T0=0,
            T1=1,
        )
    ).reshape(-1)
    if not np.allclose(test_cate, predictions["cate"].to_numpy(), rtol=1e-8, atol=1e-8):
        raise ValueError("Saved forest does not reproduce Phase 11 test CATE predictions.")
    return (
        predictions,
        eligible_split,
        metrics,
        model_bundle,
        censor_weights,
        predicted_observed,
        observed_indicator,
    )


def _make_plots(
    output_dir: Path,
    predictions: pd.DataFrame,
    propensity_summary: dict[str, Any],
    weight_arrays: dict[str, np.ndarray],
) -> None:
    figure_dir = output_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 5))
    for arm, label, color in ((0, "Control", "tab:blue"), (1, "Treated", "tab:orange")):
        values = predictions.loc[
            predictions["statin_during"].eq(arm), "propensity_score"
        ]
        axis.hist(values, bins=25, density=True, alpha=0.45, label=label, color=color)
    low, high = propensity_summary["common_support"]
    axis.axvspan(low, high, color="grey", alpha=0.12, label="Common support")
    axis.set(xlabel="Estimated propensity score", ylabel="Density", title="Test-set propensity overlap")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "propensity_overlap.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(figsize=(8, 5))
    labels = ["Treatment IPW", "Censoring IPCW", "Combined"]
    values = [
        weight_arrays["treatment"],
        weight_arrays["censor"],
        weight_arrays["combined"],
    ]
    axes.boxplot(values, tick_labels=labels, showfliers=True)
    axes.set(ylabel="Weight", title="Observed-outcome test-set weight distributions")
    figure.tight_layout()
    figure.savefig(figure_dir / "weight_distributions.png", dpi=160)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(8, 5))
    cate = predictions["cate"].to_numpy()
    axis.hist(cate, bins=30, color="tab:purple", alpha=0.75, edgecolor="white")
    axis.axvline(cate.mean(), color="black", linestyle="--", label=f"Mean {cate.mean():.3f}")
    axis.axvline(np.median(cate), color="tab:red", linestyle=":", label=f"Median {np.median(cate):.3f}")
    axis.axvline(0, color="grey", linewidth=1)
    axis.set(xlabel="CATE (risk difference)", ylabel="Admissions", title="Causal Forest test-set CATE distribution")
    axis.legend()
    figure.tight_layout()
    figure.savefig(figure_dir / "cate_distribution.png", dpi=160)
    plt.close(figure)

    ordered = np.argsort(cate)
    if len(ordered) > 250:
        ordered = ordered[np.linspace(0, len(ordered) - 1, 250).astype(int)]
    figure, axis = plt.subplots(figsize=(9, 5))
    selected = predictions.iloc[ordered]
    selected_cate = selected["cate"].to_numpy()
    axis.errorbar(
        np.arange(len(selected)),
        selected_cate,
        yerr=[
            selected_cate - selected["cate_lower_95"].to_numpy(),
            selected["cate_upper_95"].to_numpy() - selected_cate,
        ],
        fmt=".",
        alpha=0.55,
        capsize=1,
    )
    axis.axhline(0, color="black", linewidth=1)
    axis.set(xlabel="Test admissions sorted by CATE", ylabel="CATE with 95% interval", title="CATE prediction uncertainty")
    figure.tight_layout()
    figure.savefig(figure_dir / "cate_uncertainty.png", dpi=160)
    plt.close(figure)


def run_analysis(
    phase11_dir: Path = DEFAULT_PHASE11_DIR,
    cohort_path: Path = DEFAULT_COHORT,
    split_dir: Path = DEFAULT_SPLITS,
    output_dir: Path | None = None,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> dict[str, Any]:
    if replicates < 100:
        raise ValueError("Use at least 100 bootstrap replicates for reported intervals.")
    output_dir = output_dir or ROOT / "causal_models" / "phase12_robustness"
    (
        predictions,
        eligible_split,
        phase11_metrics,
        model_bundle,
        censor_weights_eligible,
        eligible_observed_probability,
        eligible_observed,
    ) = _load_phase11_artifacts(phase11_dir, cohort_path, split_dir)
    treatment = predictions["statin_during"].to_numpy(dtype=int)
    outcome = predictions["recurrent_mi"].to_numpy(dtype=int)
    propensity = predictions["propensity_score"].to_numpy(dtype=float)
    treatment_weights = np.where(
        treatment == 1,
        1.0 / np.clip(propensity, 0.01, 0.99),
        1.0 / (1.0 - np.clip(propensity, 0.01, 0.99)),
    )
    censor_weights = predictions["ipcw_weight"].to_numpy(dtype=float)
    combined_weights = predictions["combined_treatment_ipcw_weight"].to_numpy(dtype=float)
    observed_outcome_count = int(eligible_split["recurrent_mi"].notna().sum())
    if len(predictions) != observed_outcome_count:
        raise ValueError("Complete-case predictions and eligible outcome population do not align.")
    propensity_rows, propensity_summary = propensity_overlap_rows(propensity, treatment)
    for metric, value in (
        ("common_support_lower", propensity_summary["common_support"][0]),
        ("common_support_upper", propensity_summary["common_support"][1]),
        ("outside_common_support_n", propensity_summary["outside_common_support_n"]),
        (
            "outside_common_support_percent",
            propensity_summary["outside_common_support_percent"],
        ),
        ("score_minimum", propensity_summary["score_minimum"]),
        ("score_maximum", propensity_summary["score_maximum"]),
        ("score_median", propensity_summary["score_median"]),
        *propensity_summary["near_extreme_thresholds"].items(),
    ):
        propensity_rows.append(
            {
                "group": "overall",
                "statistic": "summary",
                "quantile": metric,
                "quantile_level": np.nan,
                "value": float(value),
                "n": int(len(propensity)),
            }
        )

    diagnostic_rows: list[dict[str, Any]] = []
    diagnostic_rows.extend(weight_diagnostic_rows("treatment_ipw", treatment_weights, treatment))
    diagnostic_rows.extend(weight_diagnostic_rows("censoring_ipcw", censor_weights, treatment))
    diagnostic_rows.extend(weight_diagnostic_rows("combined_ipw_ipcw", combined_weights, treatment))
    for truncation_name, limits in TRUNCATION_LEVELS.items():
        diagnostic_rows.extend(
            weight_diagnostic_rows(
                f"treatment_ipw_{truncation_name}",
                _arm_weights(treatment_weights, treatment, limits),
                treatment,
            )
        )
        diagnostic_rows.extend(
            weight_diagnostic_rows(
                f"censoring_ipcw_{truncation_name}",
                _global_winsorize(censor_weights, limits),
                treatment,
            )
        )
        diagnostic_rows.extend(
            weight_diagnostic_rows(
                f"combined_final_{truncation_name}",
                _arm_weights(combined_weights, treatment, limits),
                treatment,
            )
        )

    comparison: list[dict[str, Any]] = []
    n = len(predictions)
    test_split_n = int(len(pd.read_parquet(split_dir / "test.parquet")))
    censor_risk_set_n = int(len(eligible_split))
    censor_incomplete_n = int((~eligible_observed).sum())
    for estimator_name, estimate, interval in (
        (
            "CausalForestDML",
            phase11_metrics["causal_forest"]["ate"],
            phase11_metrics["causal_forest"]["ate_95_interval"],
        ),
    ):
        comparison.append(
            {
                "estimator": estimator_name,
                "estimand_population": "Observed outcome, complete-case test admissions",
                "risk_difference": estimate,
                "risk_difference_pp": 100 * estimate,
                "ci_lower_95": interval[0],
                "ci_upper_95": interval[1],
                "ci_lower_95_pp": 100 * interval[0],
                "ci_upper_95_pp": 100 * interval[1],
                "n": n,
                "risk_set_n": n,
                "incomplete_followup_n": 0,
                "treated_n": int((treatment == 1).sum()),
                "control_n": int((treatment == 0).sum()),
                "excluded_from_test_split": int(test_split_n - n),
                "ess_all": None,
                "ess_treated": None,
                "ess_control": None,
                "weighting_specification": "No weights; existing Phase 11 fitted CausalForestDML",
                "ci_method": "Existing Phase 11 forest inference interval",
            }
        )
    for truncation_name, limits in [("none", None), *TRUNCATION_LEVELS.items()]:
        comparison.append(
            _bootstrap_comparison_row(
                name=f"Propensity-IPW ({truncation_name})",
                estimand="Observed outcome, complete-case test admissions",
                frame=predictions,
                outcome=outcome,
                treatment=treatment,
                raw_weights=treatment_weights,
                treatment_weights=treatment_weights,
                censor_weights=censor_weights,
                weight_strategy="treatment_ipw",
                limits=limits,
                truncation_name=(
                    "Untruncated" if limits is None else f"Arm-wise winsorization {limits}"
                ),
                test_split_n=test_split_n,
                replicates=replicates,
                seed=seed,
            )
        )
        comparison.append(
            _bootstrap_comparison_row(
                name=f"Treatment-IPW + IPCW, combined-weight truncation ({truncation_name})",
                estimand=(
                    "Observed outcomes among 499 of 725 complete-baseline, known-treatment "
                    "test admissions; IPCW targets that 725-record risk set under conditional "
                    "independent censoring."
                ),
                frame=predictions,
                outcome=outcome,
                treatment=treatment,
                raw_weights=combined_weights,
                treatment_weights=treatment_weights,
                censor_weights=censor_weights,
                weight_strategy="combined_final",
                limits=limits,
                truncation_name=(
                    "Untruncated" if limits is None else f"Arm-wise winsorization {limits}"
                ),
                risk_set_n=censor_risk_set_n,
                incomplete_followup_n=censor_incomplete_n,
                test_split_n=test_split_n,
                replicates=replicates,
                seed=seed + 1,
            )
        )
        if limits is not None:
            comparison.append(
                _bootstrap_comparison_row(
                    name=f"Treatment-IPW + IPCW, censor-component truncation ({truncation_name})",
                    estimand=(
                        "Observed outcomes among 499 of 725 complete-baseline, known-treatment "
                        "test admissions; censor weights are globally winsorized."
                    ),
                    frame=predictions,
                    outcome=outcome,
                    treatment=treatment,
                    raw_weights=combined_weights,
                    treatment_weights=treatment_weights,
                    censor_weights=censor_weights,
                    weight_strategy="censor_component",
                    limits=limits,
                    truncation_name=f"Global censor-weight winsorization {limits}",
                    risk_set_n=censor_risk_set_n,
                    incomplete_followup_n=censor_incomplete_n,
                    test_split_n=test_split_n,
                    replicates=replicates,
                    seed=seed + 2,
                )
            )
    comparison_frame = pd.DataFrame(comparison)
    for column in ("risk_difference", "ci_lower_95", "ci_upper_95"):
        comparison_frame[f"{column}_pp"] = comparison_frame[column] * 100

    observed = eligible_observed
    marginal_observed = float(observed.mean())
    censor_probability_rows = [
        _summary_distribution(
            "P(observed 12-month follow-up)",
            eligible_observed_probability,
        ),
        _summary_distribution(
            "P(incomplete follow-up) = 1 - P(observed)",
            1 - eligible_observed_probability,
        ),
        _summary_distribution(
            "Stabilized IPCW among observed-outcome complete cases",
            censor_weights,
        ),
    ]
    censoring_summary = {
        "complete_baseline_known_treatment_test_risk_set_n": int(len(eligible_split)),
        "observed_followup_n": int(observed.sum()),
        "incomplete_followup_n": int((~observed).sum()),
        "observed_followup_fraction": marginal_observed,
        "test_censoring_model_auc": phase11_metrics["censoring_assessment"][
            "train_fitted_logistic_model_test_auc"
        ],
        "probability_distributions": censor_probability_rows,
        "interpretation": (
            "AUC describes discrimination only and does not establish that censoring "
            "is conditionally independent given measured variables."
        ),
    }

    cate = cate_summary(predictions, phase11_metrics)
    propensity_frame = pd.DataFrame(propensity_rows)
    diagnostic_frame = pd.DataFrame(diagnostic_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    propensity_frame.to_csv(output_dir / "propensity_overlap.csv", index=False)
    diagnostic_frame.to_csv(output_dir / "weight_diagnostics.csv", index=False)
    comparison_frame.to_csv(output_dir / "estimator_comparison.csv", index=False)
    (output_dir / "cate_summary.json").write_text(
        json.dumps(cate, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    (output_dir / "censoring_summary.json").write_text(
        json.dumps(censoring_summary, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    (output_dir / "analysis_config.json").write_text(
        json.dumps(
            {
                "phase11_artifact_directory": str(phase11_dir),
                "source_cohort": str(cohort_path),
                "patient_level_split_directory": str(split_dir),
                "test_split_unchanged": True,
                "cohort_or_treatment_rebuilt": False,
                "forest_refit": False,
                "bootstrap_replicates": replicates,
                "bootstrap_seed": seed,
                "truncation_quantiles": TRUNCATION_LEVELS,
                "treatment_weight_truncation": "within treatment arm",
                "combined_weight_truncation": "within treatment arm",
                "censoring_weight_truncation": "globally among observed-outcome cases",
                "common_support_trimming": False,
            },
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    _make_plots(
        output_dir,
        predictions,
        propensity_summary,
        {
            "treatment": treatment_weights,
            "censor": censor_weights,
            "combined": combined_weights,
        },
    )
    report = _write_report(
        propensity_summary,
        diagnostic_frame,
        comparison_frame,
        cate,
        censoring_summary,
        n,
        int(len(eligible_split)),
        replicates,
        seed,
    )
    (output_dir / "phase12_robustness_report.md").write_text(report, encoding="utf-8")
    return {
        "propensity_summary": propensity_summary,
        "censoring_summary": censoring_summary,
        "cate_summary": cate,
        "comparison": comparison_frame,
        "weight_diagnostics": diagnostic_frame,
    }


def _write_report(
    propensity: dict[str, Any],
    weights: pd.DataFrame,
    comparison: pd.DataFrame,
    cate: dict[str, Any],
    censoring: dict[str, Any],
    complete_case_n: int,
    censor_risk_set_n: int,
    replicates: int,
    seed: int,
) -> str:
    support_low, support_high = propensity["common_support"]
    prop_extremes = propensity["near_extreme_thresholds"]
    control_scores = propensity["by_group"]["control"]
    treated_scores = propensity["by_group"]["treated"]
    directional = [
        float(row["risk_difference"])
        for row in comparison.to_dict("records")
        if row["estimator"] in {
            "CausalForestDML",
            "Propensity-IPW (none)",
            "Treatment-IPW + IPCW, combined-weight truncation (none)",
        }
    ]
    signs = {int(np.sign(value)) for value in directional}
    ci_includes_zero = bool(
        (
            (comparison["ci_lower_95"] <= 0)
            & (comparison["ci_upper_95"] >= 0)
        ).all()
    )
    raw_combined = comparison.loc[
        comparison["estimator"].eq(
            "Treatment-IPW + IPCW, combined-weight truncation (none)"
        )
    ].iloc[0]
    truncated_combined = comparison.loc[
        comparison["estimator"].eq(
            "Treatment-IPW + IPCW, combined-weight truncation (p05_p95)"
        )
    ].iloc[0]
    truncation_shift_pp = abs(
        truncated_combined["risk_difference_pp"] - raw_combined["risk_difference_pp"]
    )
    propensity_ipw_raw = comparison.loc[
        comparison["estimator"].eq("Propensity-IPW (none)")
    ].iloc[0]
    propensity_ipw_595 = comparison.loc[
        comparison["estimator"].eq("Propensity-IPW (p05_p95)")
    ].iloc[0]
    propensity_truncation_shift_pp = abs(
        propensity_ipw_595["risk_difference_pp"]
        - propensity_ipw_raw["risk_difference_pp"]
    )
    censor_truncated = comparison.loc[
        comparison["estimator"].eq(
            "Treatment-IPW + IPCW, censor-component truncation (p05_p95)"
        )
    ].iloc[0]
    censor_truncation_shift_pp = abs(
        censor_truncated["risk_difference_pp"] - raw_combined["risk_difference_pp"]
    )
    max_ipw = weights.loc[
        weights["weight_type"].eq("treatment_ipw") & weights["group"].eq("all"),
        "maximum",
    ].iloc[0]
    max_combined = weights.loc[
        weights["weight_type"].eq("combined_ipw_ipcw") & weights["group"].eq("all"),
        "maximum",
    ].iloc[0]
    max_censor = weights.loc[
        weights["weight_type"].eq("censoring_ipcw") & weights["group"].eq("all"),
        "maximum",
    ].iloc[0]
    censor_distribution = censoring["probability_distributions"]
    p_observed = censor_distribution[0]
    censor_weight_distribution = censor_distribution[2]
    ipw_ess = weights.loc[
        weights["weight_type"].eq("treatment_ipw") & weights["group"].eq("all"),
        "ess",
    ].iloc[0]
    combined_ess = weights.loc[
        weights["weight_type"].eq("combined_ipw_ipcw") & weights["group"].eq("all"),
        "ess",
    ].iloc[0]
    rows = comparison[
        [
            "estimator",
            "risk_difference_pp",
            "ci_lower_95_pp",
            "ci_upper_95_pp",
            "n",
            "risk_set_n",
            "incomplete_followup_n",
            "excluded_from_test_split",
            "treated_n",
            "control_n",
            "ess_all",
            "ess_treated",
            "ess_control",
            "weighting_specification",
        ]
    ].copy()
    rows["risk_difference_pp"] = rows["risk_difference_pp"].map(lambda x: f"{x:.2f}")
    for name in ("ci_lower_95_pp", "ci_upper_95_pp"):
        rows[name] = rows[name].map(lambda x: f"{x:.2f}")
    for name in ("ess_all", "ess_treated", "ess_control"):
        rows[name] = rows[name].map(lambda x: "-" if pd.isna(x) else f"{x:.1f}")
    headers = list(rows.columns)
    table_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for record in rows.to_dict("records"):
        table_lines.append(
            "| "
            + " | ".join(
                "-" if pd.isna(record[header]) else str(record[header])
                for header in headers
            )
            + " |"
        )
    table = "\n".join(table_lines)
    direction_text = (
        "All prespecified primary point estimates are positive."
        if signs == {1}
        else "Primary point-estimate directions differ across estimators."
    )
    overlap_assessment = (
        "Empirical overlap is substantial but not complete: most patients fall "
        "inside the observed common-support interval, while the reported outside-"
        "support fraction remains untrimmed in all estimates. No near-zero/near-one "
        "scores were observed at the prespecified 0.05/0.95 thresholds."
        if propensity["outside_common_support_percent"] < 10
        and prop_extremes["less_than_0_05"] == 0
        and prop_extremes["greater_than_0_95"] == 0
        else "Empirical overlap is limited or includes near-extreme scores; the "
        "observed support findings warrant caution and were not used to silently "
        "trim the primary estimates."
    )
    significance_text = (
        "At least one reported 95% interval excludes zero."
        if not ci_includes_zero
        else "All reported 95% intervals include zero."
    )
    return "\n".join(
        [
            "# Phase 12: Statin Causal Forest Robustness and Sensitivity",
            "",
            "This analysis reuses the saved Phase 11 test predictions and fitted models. It does not refit the forest, alter cohorts, or change split assignments.",
            "",
            "## Propensity overlap",
            "",
            f"- Test complete-case sample: {propensity['sample_size']} patients "
            f"({propensity['treated']} treated, {propensity['control']} controls).",
            f"- Control propensity min/median/max: {control_scores['minimum']:.3f}/"
            f"{control_scores['median']:.3f}/{control_scores['maximum']:.3f}; "
            f"treated: {treated_scores['minimum']:.3f}/"
            f"{treated_scores['median']:.3f}/{treated_scores['maximum']:.3f}.",
            f"- Common support: [{support_low:.3f}, {support_high:.3f}]. "
            f"Outside support: {propensity['outside_common_support_n']} "
            f"({propensity['outside_common_support_percent']:.1f}%). No observations were removed.",
            f"- Scores below 0.01 / above 0.99: {prop_extremes['less_than_0_01']} / {prop_extremes['greater_than_0_99']}; "
            f"below 0.05 / above 0.95: {prop_extremes['less_than_0_05']} / {prop_extremes['greater_than_0_95']}; "
            f"below 0.10 / above 0.90: {prop_extremes['less_than_0_10']} / {prop_extremes['greater_than_0_90']}.",
            "- Quantile-level distributions by treatment arm are in `propensity_overlap.csv`; the plot preserves all observations.",
            "",
            "## Weight and censoring diagnostics",
            "",
            f"- Untruncated treatment-IPW maximum: {max_ipw:.2f}; overall ESS: {ipw_ess:.1f} of {complete_case_n}. The top 1% of untruncated treatment weights contribute {weights.loc[weights['weight_type'].eq('treatment_ipw') & weights['group'].eq('all'), 'top_1pct_share_of_group_weight'].iloc[0]:.1%} of total weight.",
            f"- Stabilized censoring IPCW maximum: {max_censor:.2f}; the censoring risk set includes {censor_risk_set_n} records, with {censoring['observed_followup_n']} observed outcomes and {censoring['incomplete_followup_n']} incomplete follow-ups.",
            f"- Predicted P(observed follow-up) ranged {p_observed['p00']:.3f}–{p_observed['p100']:.3f} (median {p_observed['p50']:.3f}); observed-case stabilized IPCW p95/p99/max were {censor_weight_distribution['p95']:.2f}/{censor_weight_distribution['p99']:.2f}/{censor_weight_distribution['p100']:.2f}.",
            f"- Combined treatment-IPW/IPCW maximum: {max_combined:.2f}; overall ESS: {combined_ess:.1f} of {complete_case_n}.",
            f"- Train-fitted censoring model test AUC: {censoring['test_censoring_model_auc']:.3f}. This is a discrimination measure, not evidence that censoring is adequately controlled.",
            f"- 5th/95th percentile arm-wise truncation shifted the treatment-IPW point estimate by {propensity_truncation_shift_pp:.2f} pp and the combined-weight point estimate by {truncation_shift_pp:.2f} pp. Truncation changes the weighting estimator and can introduce bias.",
            f"- Truncating only the censoring-weight component at 5th/95th percentiles shifted the combined estimate by {censor_truncation_shift_pp:.2f} percentage points.",
            "- Complete weight distributions, arm-specific ESS, and top-1%-weight concentration are in `weight_diagnostics.csv`. Censor probabilities are summarized in `censoring_summary.json`.",
            "",
            "## Estimator comparison",
            "",
            f"Risk differences are on the percentage-point scale. Bootstrap intervals use {replicates} patient-level resamples; truncation limits are recomputed within each resample.",
            "",
            table,
            "",
            "CausalForestDML and unweighted propensity-IPW use the 499 observed-outcome complete-case test admissions. IPCW estimates use those 499 observed outcomes weighted to represent the 725-record test risk set with complete baseline features and known treatment; the estimands differ and rely on conditional independent censoring. No common-support trimming was applied.",
            "",
            "## CATE distribution",
            "",
            f"- n={cate['n']}; mean={cate['mean']:.4f}, median={cate['median']:.4f}, SD={cate['standard_deviation']:.4f}.",
            f"- p10={cate['quantiles']['p10']:.4f}; p25={cate['quantiles']['p25']:.4f}; p75={cate['quantiles']['p75']:.4f}; p90={cate['quantiles']['p90']:.4f}.",
            f"- Stored population ATE 95% interval: {cate['population_ate_95_interval']}. Per-patient forest intervals are shown in `figures/cate_uncertainty.png`.",
            "- Variation in predicted CATEs and subgroup patterns does not by itself establish clinically meaningful effect heterogeneity.",
            "",
            "## Interpretation",
            "",
            direction_text,
            f"{significance_text} The current point estimates are directionally consistent, but weighting changes their magnitude and truncation sensitivity should be interpreted as a different weighting estimator.",
            overlap_assessment,
            "IPCW conclusions remain assumption-dependent. Censoring associations and the AUC do not verify conditional independent censoring; death remains a competing event coded as no recurrent MI by the horizon in this binary outcome. Patient bootstrap intervals hold saved nuisance-model predictions fixed and do not include uncertainty from estimating those models.",
            "",
            "The experiment remains exploratory. `statin_during` is an in-hospital exposure, not proven initiation or adherence; the endpoint is MI-coded recurrence, not clinically adjudicated recurrence. These estimates do not establish a clinical causal effect. Estimates and confidence intervals are test-set/model-dependent, and the Phase 11 forest estimate interval was reused without refitting.",
            "",
            "## Reproducibility",
            "",
            "Run from the repository root with:",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -m causal_models.phase12_robustness.analyze_statin_robustness",
            "```",
            "",
            f"Bootstrap seed: {seed}; replicates: {replicates}.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 12 statin robustness analyses.")
    parser.add_argument("--phase11-dir", type=Path, default=DEFAULT_PHASE11_DIR)
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLITS)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "causal_models" / "phase12_robustness",
    )
    parser.add_argument("--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    run_analysis(
        args.phase11_dir,
        args.cohort,
        args.split_dir,
        args.output_dir,
        args.bootstrap_replicates,
        args.seed,
    )
    print(f"Phase 12 robustness outputs written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
