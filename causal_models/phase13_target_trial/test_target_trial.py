from __future__ import annotations

import unittest

import pandas as pd

from causal_models.phase13_target_trial.analyze_target_trial import (
    classify_acute_endpoint,
    cumulative_incidence,
    is_acute_mi_code,
)


class TargetTrialTests(unittest.TestCase):
    def test_acute_code_rule(self) -> None:
        self.assertTrue(is_acute_mi_code("410.71", 9))
        self.assertTrue(is_acute_mi_code("I21.4", 10))
        self.assertTrue(is_acute_mi_code("I22.2", 10))
        self.assertFalse(is_acute_mi_code("412", 9))
        self.assertFalse(is_acute_mi_code("I25.2", 10))

    def test_classifies_acute_event_and_ignores_index_or_post_horizon_events(self) -> None:
        events = pd.DataFrame(
            {
                "hadm_id": [1, 2, 3],
                "admittime": pd.to_datetime(
                    ["2020-01-01", "2020-02-01", "2021-02-01"]
                ),
            }
        )
        result = classify_acute_endpoint(
            "2020-01-01",
            "2021-01-01",
            "2021-01-01",
            pd.NaT,
            False,
            events,
        )
        self.assertEqual(result["acute_event_type"], "acute_recurrent_mi")
        self.assertEqual(result["acute_first_hadm_id"], 2)
        self.assertAlmostEqual(result["acute_followup_days"], 31)

    def test_same_day_imprecise_death_is_uncertain(self) -> None:
        result = classify_acute_endpoint(
            "2020-01-01",
            "2021-01-01",
            "2020-03-01",
            "2020-03-01",
            False,
            pd.DataFrame({"hadm_id": [8], "admittime": pd.to_datetime(["2020-03-01 09:00"])}),
        )
        self.assertEqual(result["acute_event_type"], "event_order_uncertain")
        self.assertTrue(pd.isna(result["acute_recurrent_mi"]))

    def test_incomplete_followup_does_not_get_a_negative_endpoint(self) -> None:
        result = classify_acute_endpoint(
            "2020-01-01",
            "2021-01-01",
            "2020-02-01",
            pd.NaT,
            False,
            pd.DataFrame(columns=["hadm_id", "admittime"]),
        )
        self.assertEqual(result["acute_event_type"], "incomplete_followup")
        self.assertTrue(pd.isna(result["acute_recurrent_mi"]))

    def test_cumulative_incidence_keeps_competing_death_distinct(self) -> None:
        frame = pd.DataFrame(
            {
                "duration_days": [1.0, 2.0, 3.0, 4.0],
                "event_type": [
                    "acute_recurrent_mi",
                    "competing_death",
                    "event_free",
                    "incomplete_followup",
                ],
            }
        )
        result = cumulative_incidence(frame, (4,))[0]
        self.assertAlmostEqual(result["acute_mi_cif"], 0.25)
        self.assertAlmostEqual(result["death_cif"], 0.25)
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["input_n"], 4)
        self.assertEqual(result["excluded_n"], 0)


if __name__ == "__main__":
    unittest.main()
