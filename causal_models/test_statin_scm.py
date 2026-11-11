from __future__ import annotations

import unittest
from dataclasses import replace

import numpy as np

from causal_models.statin_scm import (
    ExogenousDisturbances,
    StatinSCM,
    StatinSCMParameters,
    structural_baseline_equations,
)


class StatinSCMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parameters = StatinSCMParameters.synthetic_test_parameters()
        cls.model = StatinSCM(cls.parameters)
        cls.synthetic = cls.model.simulate_selected_cohort(size=300, seed=913)

    def test_synthetic_cohort_matches_target_population(self) -> None:
        self.assertEqual(len(self.synthetic), 300)
        self.assertTrue(self.synthetic["is_synthetic"].all())
        self.assertTrue((self.synthetic["prior_mi_eligibility"] == 1).all())
        self.assertTrue((self.synthetic["survived_to_index_discharge"] == 1).all())

    def test_model_rejects_population_without_verified_selection_fields(self) -> None:
        incomplete = self.synthetic.drop(columns=["prior_mi_eligibility"])
        with self.assertRaisesRegex(ValueError, "target-population fields"):
            self.model.predict_observational(incomplete)
        noneligible = self.synthetic.copy()
        noneligible.loc[noneligible.index[0], "survived_to_index_discharge"] = 0
        with self.assertRaisesRegex(ValueError, "index-discharge survivors"):
            self.model.counterfactual_risks(noneligible, 1)

    def test_exogenous_disturbances_are_explicit_and_drive_baseline_equations(self) -> None:
        disturbances = ExogenousDisturbances.draw(10, np.random.default_rng(42))
        baseline = structural_baseline_equations(disturbances)
        self.assertIn("u_prior_mi_count", disturbances.baseline)
        self.assertEqual(len(baseline), 10)
        self.assertIn("prior_mi_episode_count", baseline)
        self.assertIn("prior_mi_eligibility", baseline)

    def test_observational_prediction_marginalizes_assignment_and_receipt(self) -> None:
        prediction = self.model.predict_observational(self.synthetic)
        self.assertTrue(
            np.allclose(
                prediction[
                    ["recurrent_mi_risk", "death_competing_risk", "event_free_probability"]
                ].sum(axis=1),
                1.0,
            )
        )
        self.assertTrue(prediction["treatment_probability"].between(0.0, 1.0).all())

    def test_intervention_replaces_assignment_equation(self) -> None:
        alternate_parameters = replace(
            self.parameters,
            treatment_assignment=replace(
                self.parameters.treatment_assignment,
                intercept=25.0,
            ),
        )
        alternate_model = StatinSCM(alternate_parameters)
        original_risk = self.model.counterfactual_risks(
            self.synthetic,
            treatment_value=1,
        )["recurrent_mi_risk"].to_numpy()
        alternate_risk = alternate_model.counterfactual_risks(
            self.synthetic,
            treatment_value=1,
        )["recurrent_mi_risk"].to_numpy()
        np.testing.assert_allclose(original_risk, alternate_risk)
        self.assertGreater(
            alternate_model.predict_observational(self.synthetic)[
                "treatment_probability"
            ].mean(),
            0.99,
        )

    def test_counterfactual_comparison_is_a_model_implied_population_risk(self) -> None:
        comparison = self.model.compare_interventions(self.synthetic)
        self.assertIn("not_an_empirical_effect_estimate", comparison["status"])
        self.assertGreaterEqual(comparison["risk_do_1"], 0.0)
        self.assertLessEqual(comparison["risk_do_1"], 1.0)
        treated = self.model.counterfactual_risks(self.synthetic, 1)
        self.assertTrue(
            treated["risk_status"]
            .eq("model_implied_not_observed_individual_counterfactual")
            .all()
        )
        self.assertNotEqual(
            comparison["risk_do_1"],
            comparison["risk_do_0"],
        )
        with self.assertRaises(ValueError):
            self.model.counterfactual_risks(self.synthetic, 2)


if __name__ == "__main__":
    unittest.main()
