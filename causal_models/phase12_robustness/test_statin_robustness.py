from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from causal_models.phase12_robustness.analyze_statin_robustness import (
    _arm_weights,
    cluster_bootstrap_interval,
    _global_winsorize,
    cate_summary,
    effective_sample_size,
    propensity_overlap_rows,
    weight_diagnostic_rows,
    weighted_risk_difference,
)


class StatinRobustnessTests(unittest.TestCase):
    def test_propensity_overlap_reports_common_support_and_extremes(self) -> None:
        rows, summary = propensity_overlap_rows(
            np.array([0.05, 0.20, 0.70, 0.95]),
            np.array([0, 0, 1, 1]),
        )
        self.assertEqual(len(rows), 22)
        self.assertEqual(summary["common_support"], [0.7, 0.2])
        self.assertEqual(summary["outside_common_support_n"], 4)
        self.assertEqual(summary["outside_common_support_percent"], 100.0)
        self.assertEqual(summary["near_extreme_thresholds"]["less_than_0_10"], 1)
        self.assertEqual(summary["by_group"]["treated"]["median"], 0.825)

    def test_ess_and_weight_diagnostics_include_arms_and_concentration(self) -> None:
        weights = np.array([1.0, 1.0, 2.0, 4.0])
        treatment = np.array([0, 0, 1, 1])
        self.assertAlmostEqual(effective_sample_size(weights), 64 / 22)
        rows = weight_diagnostic_rows("ipw", weights, treatment)
        by_group = {row["group"]: row for row in rows}
        self.assertEqual(set(by_group), {"all", "control", "treated"})
        self.assertAlmostEqual(by_group["control"]["ess"], 2.0)
        self.assertAlmostEqual(by_group["treated"]["ess"], 36 / 20)
        self.assertAlmostEqual(by_group["all"]["top_1pct_share_of_group_weight"], 0.5)

    def test_truncation_respects_armwise_and_global_cutoffs(self) -> None:
        weights = np.array([1.0, 2.0, 3.0, 4.0, 100.0, 200.0])
        treatment = np.array([0, 0, 0, 1, 1, 1])
        armwise = _arm_weights(weights, treatment, (0.05, 0.95))
        global_values = _global_winsorize(weights, (0.05, 0.95))
        self.assertLess(armwise.max(), weights.max())
        self.assertLess(global_values.max(), weights.max())
        self.assertAlmostEqual(armwise[:3].max(), 2.9)
        self.assertEqual(global_values.min(), 1.25)

    def test_weighted_risk_difference_uses_arm_specific_weighted_risks(self) -> None:
        result = weighted_risk_difference(
            np.array([1, 0, 1, 0]),
            np.array([1, 1, 0, 0]),
            np.ones(4),
        )
        self.assertEqual(result, 0.0)
        with self.assertRaisesRegex(ValueError, "Both binary treatment arms"):
            weighted_risk_difference(
                np.array([1, 0]),
                np.array([1, 1]),
                np.ones(2),
            )

    def test_cate_summary_reports_quantiles_and_existing_intervals(self) -> None:
        predictions = pd.DataFrame(
            {
                "cate": [0.0, 0.1, 0.2, 0.3, 0.4],
                "cate_lower_95": [-0.1, 0.0, 0.1, 0.2, 0.3],
                "cate_upper_95": [0.1, 0.2, 0.3, 0.4, 0.5],
            }
        )
        summary = cate_summary(
            predictions,
            {"causal_forest": {"ate": 0.2, "ate_95_interval": [-0.1, 0.5]}},
        )
        self.assertAlmostEqual(summary["mean"], 0.2)
        self.assertAlmostEqual(summary["median"], 0.2)
        self.assertAlmostEqual(summary["quantiles"]["p10"], 0.04)
        self.assertEqual(summary["population_ate_95_interval"], [-0.1, 0.5])

    def test_patient_bootstrap_interval_is_reproducible(self) -> None:
        treatment = np.tile([0, 1], 20)
        outcome = np.tile([0, 1, 1, 0], 10)
        weights = np.where(treatment == 1, 1.5, 1.2)
        frame = pd.DataFrame({"SubjectID": np.arange(40)})
        first = cluster_bootstrap_interval(
            frame,
            weights,
            "treatment_ipw",
            np.ones(40),
            weights,
            treatment,
            outcome,
            None,
            replicates=100,
            seed=12,
        )
        second = cluster_bootstrap_interval(
            frame,
            weights,
            "treatment_ipw",
            np.ones(40),
            weights,
            treatment,
            outcome,
            None,
            replicates=100,
            seed=12,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)


if __name__ == "__main__":
    unittest.main()
