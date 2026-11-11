from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd


BASELINE_FEATURES = (
    "age",
    "sex",
    "diabetes",
    "hypertension",
    "ckd",
    "prior_cvd",
    "lipid_burden",
    "prior_mi_episode_count",
    "time_since_most_recent_mi",
    "prior_mi_severity",
    "prior_cv_interventions",
    "prior_statin_use",
    "baseline_clinical_state",
    "other_baseline_medications",
    "healthcare_access",
)


@dataclass(frozen=True)
class ExogenousDisturbances:
    """Explicit exogenous draws used by the baseline and event mechanisms."""

    baseline: Mapping[str, np.ndarray]
    u_prior_mi_documentation: np.ndarray
    u_index_discharge_survival: np.ndarray
    u_treatment_assignment: np.ndarray
    u_post_assignment_receipt: np.ndarray
    u_recurrent_mi: np.ndarray
    u_death: np.ndarray

    @classmethod
    def draw(cls, size: int, rng: np.random.Generator) -> ExogenousDisturbances:
        if size < 1:
            raise ValueError("Disturbance size must be positive.")
        return cls(
            baseline={
                "u_age": rng.normal(size=size),
                "u_sex": rng.random(size),
                "u_diabetes": rng.random(size),
                "u_hypertension": rng.random(size),
                "u_ckd": rng.random(size),
                "u_prior_cvd": rng.random(size),
                "u_lipid_burden": rng.normal(size=size),
                "u_prior_mi_count": rng.random(size),
                "u_time_since_mi": rng.random(size),
                "u_prior_mi_severity": rng.normal(size=size),
                "u_prior_cv_interventions": rng.random(size),
                "u_prior_statin_use": rng.random(size),
                "u_baseline_clinical_state": rng.normal(size=size),
                "u_other_baseline_medications": rng.random(size),
                "u_healthcare_access": rng.normal(size=size),
            },
            u_prior_mi_documentation=rng.random(size),
            u_index_discharge_survival=rng.random(size),
            u_treatment_assignment=rng.random(size),
            u_post_assignment_receipt=rng.random(size),
            u_recurrent_mi=rng.random(size),
            u_death=rng.random(size),
        )

    def take(self, indices: np.ndarray) -> ExogenousDisturbances:
        return ExogenousDisturbances(
            baseline={name: values[indices] for name, values in self.baseline.items()},
            u_prior_mi_documentation=self.u_prior_mi_documentation[indices],
            u_index_discharge_survival=self.u_index_discharge_survival[indices],
            u_treatment_assignment=self.u_treatment_assignment[indices],
            u_post_assignment_receipt=self.u_post_assignment_receipt[indices],
            u_recurrent_mi=self.u_recurrent_mi[indices],
            u_death=self.u_death[indices],
        )


@dataclass(frozen=True)
class LogisticEquation:
    """A logistic structural equation with explicit, named parent coefficients."""

    intercept: float
    coefficients: Mapping[str, float]

    def linear_predictor(
        self,
        data: pd.DataFrame,
        extra: Mapping[str, np.ndarray] | None = None,
    ) -> np.ndarray:
        linear_predictor = np.full(len(data), self.intercept, dtype=float)
        for name, coefficient in self.coefficients.items():
            if extra is not None and name in extra:
                values = np.asarray(extra[name], dtype=float)
            elif name in data:
                values = data[name].to_numpy(dtype=float)
            else:
                raise ValueError(f"Structural equation parent is missing: {name}")
            if values.shape != (len(data),):
                raise ValueError(f"Parent {name} must have one value per row.")
            linear_predictor += coefficient * values
        return np.clip(linear_predictor, -35.0, 35.0)

    def probability(
        self,
        data: pd.DataFrame,
        extra: Mapping[str, np.ndarray] | None = None,
    ) -> np.ndarray:
        return _sigmoid(self.linear_predictor(data, extra))


@dataclass(frozen=True)
class StatinSCMParameters:
    """User-supplied structural coefficients; no empirical fit is performed here."""

    treatment_assignment: LogisticEquation
    post_assignment_receipt: LogisticEquation
    recurrent_mi: LogisticEquation
    death: LogisticEquation

    @classmethod
    def synthetic_test_parameters(cls) -> StatinSCMParameters:
        """Return illustrative coefficients for synthetic interface tests only."""
        return cls(
            treatment_assignment=LogisticEquation(
                intercept=-0.65,
                coefficients={
                    "age": 0.008,
                    "diabetes": 0.25,
                    "prior_cvd": 0.45,
                    "lipid_burden": 0.30,
                    "prior_mi_episode_count": 0.15,
                    "prior_mi_severity": 0.18,
                    "prior_cv_interventions": 0.12,
                    "prior_statin_use": 0.65,
                    "healthcare_access": 0.18,
                },
            ),
            post_assignment_receipt=LogisticEquation(
                intercept=-0.15,
                coefficients={
                    "statin_initiation": 1.35,
                    "prior_statin_use": 0.35,
                    "healthcare_access": 0.20,
                },
            ),
            recurrent_mi=LogisticEquation(
                intercept=-2.9,
                coefficients={
                    "age": 0.012,
                    "diabetes": 0.30,
                    "hypertension": 0.12,
                    "ckd": 0.22,
                    "prior_cvd": 0.32,
                    "lipid_burden": 0.36,
                    "prior_mi_episode_count": 0.20,
                    "time_since_most_recent_mi": -0.035,
                    "prior_mi_severity": 0.24,
                    "prior_cv_interventions": 0.16,
                    "baseline_clinical_state": 0.25,
                    "other_baseline_medications": 0.05,
                    "post_assignment_receipt": -0.55,
                },
            ),
            death=LogisticEquation(
                intercept=-3.6,
                coefficients={
                    "age": 0.028,
                    "ckd": 0.32,
                    "prior_cvd": 0.28,
                    "prior_mi_episode_count": 0.16,
                    "prior_mi_severity": 0.30,
                    "baseline_clinical_state": 0.42,
                    "post_assignment_receipt": -0.12,
                },
            ),
        )


def _sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-values))


def structural_baseline_equations(
    disturbances: ExogenousDisturbances,
) -> pd.DataFrame:
    """Generate synthetic baseline fields and prior-MI/discharge selection indicators."""
    u = disturbances.baseline
    size = len(disturbances.u_prior_mi_documentation)
    if any(len(values) != size for values in u.values()):
        raise ValueError("All baseline disturbances must have the same length.")

    age = np.clip(58.0 + 13.0 * u["u_age"], 18.0, 95.0)
    sex = (u["u_sex"] < 0.48).astype(int)
    diabetes = (
        u["u_diabetes"] < _sigmoid(-2.2 + 0.025 * (age - 55.0))
    ).astype(int)
    hypertension = (
        u["u_hypertension"] < _sigmoid(-1.0 + 0.026 * (age - 55.0))
    ).astype(int)
    ckd = (
        u["u_ckd"] < _sigmoid(-2.4 + 0.028 * (age - 60.0))
    ).astype(int)
    lipid_burden = (
        0.32 * diabetes
        + 0.12 * sex
        + u["u_lipid_burden"]
    )
    healthcare_access = u["u_healthcare_access"]
    prior_cvd = (
        u["u_prior_cvd"]
        < _sigmoid(
            -1.2
            + 0.018 * (age - 55.0)
            + 0.42 * diabetes
            + 0.20 * hypertension
            + 0.18 * ckd
        )
    ).astype(int)

    episode_intensity = np.exp(
        np.clip(
            -0.8
            + 0.014 * (age - 55.0)
            + 0.28 * diabetes
            + 0.24 * prior_cvd,
            -4.0,
            1.4,
        )
    )
    episode_zero_probability = np.exp(-episode_intensity)
    episode_count = np.floor(
        np.log1p(-u["u_prior_mi_count"])
        / np.log1p(-episode_zero_probability)
    ).astype(int)
    time_since_mi = -np.log1p(-u["u_time_since_mi"]) * 5.0
    severity_score = (
        0.60 * prior_cvd
        + 0.20 * diabetes
        + u["u_prior_mi_severity"]
    )
    prior_mi_severity = np.digitize(severity_score, [-0.5, 0.6]).astype(int) + 1
    prior_cv_interventions = np.floor(
        u["u_prior_cv_interventions"]
        * (1.0 + episode_count + 2.0 * prior_cvd)
    ).astype(int)
    prior_statin_use = (
        u["u_prior_statin_use"]
        < _sigmoid(
            -1.0
            + 0.55 * prior_cvd
            + 0.30 * lipid_burden
            + 0.25 * healthcare_access
        )
    ).astype(int)
    baseline_clinical_state = (
        0.32 * ckd
        + 0.28 * prior_cvd
        + 0.18 * prior_mi_severity
        + 0.12 * diabetes
        + u["u_baseline_clinical_state"]
    )
    other_baseline_medications = (
        u["u_other_baseline_medications"]
        < _sigmoid(
            -0.8
            + 0.45 * prior_cvd
            + 0.20 * prior_statin_use
            + 0.15 * healthcare_access
        )
    ).astype(int)
    prior_mi_documented_probability = _sigmoid(
        1.2 + 0.65 * healthcare_access + 0.20 * prior_cvd
    )
    prior_mi_eligibility = (
        (episode_count >= 1)
        & (disturbances.u_prior_mi_documentation < prior_mi_documented_probability)
    )
    survival_probability = _sigmoid(
        3.2
        - 0.035 * (age - 55.0)
        - 0.48 * ckd
        - 0.32 * prior_cvd
        - 0.28 * prior_mi_severity
        - 0.28 * baseline_clinical_state
    )
    survived_to_index_discharge = (
        disturbances.u_index_discharge_survival < survival_probability
    )

    frame = pd.DataFrame(
        {
            "age": age,
            "sex": sex,
            "diabetes": diabetes,
            "hypertension": hypertension,
            "ckd": ckd,
            "prior_cvd": prior_cvd,
            "lipid_burden": lipid_burden,
            "prior_mi_episode_count": episode_count,
            "time_since_most_recent_mi": time_since_mi,
            "prior_mi_severity": prior_mi_severity,
            "prior_cv_interventions": prior_cv_interventions,
            "prior_statin_use": prior_statin_use,
            "baseline_clinical_state": baseline_clinical_state,
            "other_baseline_medications": other_baseline_medications,
            "healthcare_access": healthcare_access,
            "prior_mi_eligibility": prior_mi_eligibility.astype(int),
            "survived_to_index_discharge": survived_to_index_discharge.astype(int),
        }
    )
    return frame


class StatinSCM:
    """Parameterized SCM skeleton; supplied parameters are not fitted to MIMIC."""

    def __init__(self, parameters: StatinSCMParameters) -> None:
        self.parameters = parameters

    @staticmethod
    def _validate_baseline(data: pd.DataFrame) -> None:
        missing = sorted(set(BASELINE_FEATURES) - set(data.columns))
        missing.extend(
            name
            for name in ("prior_mi_eligibility", "survived_to_index_discharge")
            if name not in data.columns
        )
        if missing:
            raise ValueError(f"Missing baseline or target-population fields: {missing}")
        if data.empty:
            raise ValueError("At least one eligible baseline row is required.")
        try:
            baseline_values = data.loc[:, BASELINE_FEATURES].to_numpy(dtype=float)
        except (TypeError, ValueError) as error:
            raise ValueError("All baseline structural parents must be numeric.") from error
        if not np.isfinite(baseline_values).all():
            raise ValueError("Baseline structural parents must not contain missing or infinite values.")
        if not (data["prior_mi_eligibility"] == 1).all():
            raise ValueError("SCM input must be restricted to documented prior-MI eligibility.")
        if not (
            data["survived_to_index_discharge"] == 1
        ).all():
            raise ValueError("SCM input must be restricted to index-discharge survivors.")
        if (data["prior_mi_episode_count"] < 1).any():
            raise ValueError("Eligible rows must have at least one prior MI episode.")
        for column in (
            "sex",
            "diabetes",
            "hypertension",
            "ckd",
            "prior_cvd",
            "prior_statin_use",
            "other_baseline_medications",
            "prior_mi_eligibility",
            "survived_to_index_discharge",
        ):
            if not data[column].isin([0, 1]).all():
                raise ValueError(f"{column} must be binary.")

    def treatment_probability(self, data: pd.DataFrame) -> np.ndarray:
        self._validate_baseline(data)
        return self.parameters.treatment_assignment.probability(data)

    def receipt_probability(
        self,
        data: pd.DataFrame,
        treatment_value: int | np.ndarray,
    ) -> np.ndarray:
        treatment = np.broadcast_to(np.asarray(treatment_value, dtype=float), (len(data),))
        if not np.isin(treatment, [0.0, 1.0]).all():
            raise ValueError("Treatment intervention must be binary (0 or 1).")
        return self.parameters.post_assignment_receipt.probability(
            data,
            {"statin_initiation": treatment},
        )

    def _event_probabilities(
        self,
        data: pd.DataFrame,
        receipt: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        extra = {"post_assignment_receipt": receipt}
        mi_logit = self.parameters.recurrent_mi.linear_predictor(data, extra)
        death_logit = self.parameters.death.linear_predictor(data, extra)
        logits = np.column_stack((np.zeros(len(data)), mi_logit, death_logit))
        logits -= logits.max(axis=1, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=1, keepdims=True)
        return probabilities[:, 1], probabilities[:, 2], probabilities[:, 0]

    def predict_observational(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return model-implied risks averaged over assignment and receipt mechanisms."""
        self._validate_baseline(data)
        treatment_probability = self.parameters.treatment_assignment.probability(data)
        mi_risk = np.zeros(len(data), dtype=float)
        death_risk = np.zeros(len(data), dtype=float)
        event_free = np.zeros(len(data), dtype=float)
        receipt_marginal = np.zeros(len(data), dtype=float)

        for treatment_value in (0, 1):
            p_treatment = (
                treatment_probability
                if treatment_value == 1
                else 1.0 - treatment_probability
            )
            receipt_probability = self.receipt_probability(data, treatment_value)
            receipt_marginal += p_treatment * receipt_probability
            for receipt_value in (0, 1):
                p_receipt = (
                    receipt_probability if receipt_value == 1 else 1.0 - receipt_probability
                )
                p_state = p_treatment * p_receipt
                p_mi, p_death, p_no_event = self._event_probabilities(
                    data,
                    np.full(len(data), receipt_value, dtype=float),
                )
                mi_risk += p_state * p_mi
                death_risk += p_state * p_death
                event_free += p_state * p_no_event

        return pd.DataFrame(
            {
                "treatment_probability": treatment_probability,
                "post_assignment_receipt_probability": receipt_marginal,
                "recurrent_mi_risk": mi_risk,
                "death_competing_risk": death_risk,
                "event_free_probability": event_free,
            },
            index=data.index,
        )

    def counterfactual_risks(
        self,
        data: pd.DataFrame,
        treatment_value: int,
    ) -> pd.DataFrame:
        """Compute risks under do(statin=t), replacing the assignment equation."""
        self._validate_baseline(data)
        if treatment_value not in (0, 1):
            raise ValueError("Treatment intervention must be 0 or 1.")

        receipt_probability = self.receipt_probability(data, treatment_value)
        mi_risk = np.zeros(len(data), dtype=float)
        death_risk = np.zeros(len(data), dtype=float)
        event_free = np.zeros(len(data), dtype=float)
        for receipt_value in (0, 1):
            p_receipt = (
                receipt_probability if receipt_value == 1 else 1.0 - receipt_probability
            )
            p_mi, p_death, p_no_event = self._event_probabilities(
                data,
                np.full(len(data), receipt_value, dtype=float),
            )
            mi_risk += p_receipt * p_mi
            death_risk += p_receipt * p_death
            event_free += p_receipt * p_no_event
        return pd.DataFrame(
            {
                "intervention": f"do(statin_initiation={treatment_value})",
                "recurrent_mi_risk": mi_risk,
                "death_competing_risk": death_risk,
                "event_free_probability": event_free,
                "risk_status": "model_implied_not_observed_individual_counterfactual",
            },
            index=data.index,
        )

    def compare_interventions(self, data: pd.DataFrame) -> dict[str, float | str]:
        """Compare population-average model risks under do(statin=1) and do(statin=0)."""
        treated = self.counterfactual_risks(data, 1)
        untreated = self.counterfactual_risks(data, 0)
        risk_treated = float(treated["recurrent_mi_risk"].mean())
        risk_untreated = float(untreated["recurrent_mi_risk"].mean())
        return {
            "risk_do_1": risk_treated,
            "risk_do_0": risk_untreated,
            "risk_difference_do_1_minus_do_0": risk_treated - risk_untreated,
            "status": "parameterized_model_comparison_not_an_empirical_effect_estimate",
        }

    def simulate_selected_cohort(
        self,
        size: int,
        seed: int,
        max_batches: int = 100,
    ) -> pd.DataFrame:
        """Generate synthetic prior-MI survivors and structural variables for testing."""
        if size < 1:
            raise ValueError("Requested synthetic cohort size must be positive.")
        rng = np.random.default_rng(seed)
        selected_frames: list[pd.DataFrame] = []
        remaining = size
        for _ in range(max_batches):
            batch_size = max(64, remaining * 3)
            disturbances = ExogenousDisturbances.draw(batch_size, rng)
            candidates = structural_baseline_equations(disturbances)
            mask = (
                candidates["prior_mi_eligibility"].eq(1)
                & candidates["survived_to_index_discharge"].eq(1)
            ).to_numpy()
            selected_indices = np.flatnonzero(mask)[:remaining]
            if not len(selected_indices):
                continue
            baseline = candidates.iloc[selected_indices].copy()
            exogenous = disturbances.take(selected_indices)
            assignment_probability = self.treatment_probability(baseline)
            treatment = (
                exogenous.u_treatment_assignment < assignment_probability
            ).astype(int)
            receipt_probability = self.receipt_probability(baseline, treatment)
            receipt = (
                exogenous.u_post_assignment_receipt < receipt_probability
            ).astype(int)
            p_mi, p_death, _ = self._event_probabilities(baseline, receipt)
            recurrent_mi = (exogenous.u_recurrent_mi < p_mi).astype(int)
            conditional_death_probability = np.divide(
                p_death,
                1.0 - p_mi,
                out=np.zeros_like(p_death),
                where=(1.0 - p_mi) > 0,
            )
            death = (
                (recurrent_mi == 0)
                & (exogenous.u_death < conditional_death_probability)
            ).astype(int)
            baseline["statin_initiation"] = treatment
            baseline["post_assignment_receipt"] = receipt
            baseline["recurrent_mi"] = recurrent_mi
            baseline["death_before_mi"] = death
            baseline["is_synthetic"] = True
            selected_frames.append(baseline)
            remaining -= len(selected_indices)
            if remaining == 0:
                return pd.concat(selected_frames, ignore_index=True)
        raise RuntimeError(
            f"Could not generate the requested selected cohort size ({size}) "
            f"within {max_batches} synthetic batches."
        )
