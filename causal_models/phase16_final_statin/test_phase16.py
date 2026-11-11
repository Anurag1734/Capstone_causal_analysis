from __future__ import annotations

import unittest

import pandas as pd

from causal_models.phase16_final_statin.analyze_phase16 import (
    _baseline_table,
    _check_inputs,
    _cohort_flow,
    _endpoint_table,
    _final_estimates,
    _read_inputs,
    endpoint_disposition,
    exposure_window_status,
    validate_flow_reconciliation,
    validate_complete_case_counts,
    validate_incomplete_followup,
    validate_patient_split_disjoint,
)


class Phase16Tests(unittest.TestCase):
    def test_episode_categories_are_not_promoted_to_confirmed_primary_events(self) -> None:
        self.assertIn("sensitivity", endpoint_disposition("candidate distinct acute MI"))
        for category in (
            "possible transfer/readmission for the same episode",
            "possible continuation of index MI episode",
            "uncertain episode classification",
        ):
            disposition = endpoint_disposition(category)
            self.assertIn("or as no event", disposition)
            self.assertIn("not treat as confirmed distinct recurrence", disposition)

    def test_unknown_episode_category_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            endpoint_disposition("adjudicated recurrent MI")

    def test_competing_death_and_event_free_are_distinct(self) -> None:
        rows = pd.DataFrame(
            {
                "acute_event_type": ["acute_recurrent_mi", "competing_death", "event_free"],
                "acute_recurrent_mi": [1, 0, 0],
            }
        )
        validate_incomplete_followup(rows)
        self.assertNotEqual(rows.loc[1, "acute_event_type"], rows.loc[2, "acute_event_type"])

    def test_incomplete_followup_cannot_be_event_free(self) -> None:
        rows = pd.DataFrame(
            {
                "acute_event_type": ["incomplete_followup"],
                "acute_recurrent_mi": [0],
            }
        )
        with self.assertRaises(ValueError):
            validate_incomplete_followup(rows)

    def test_incomplete_followup_may_remain_unknown(self) -> None:
        rows = pd.DataFrame(
            {
                "acute_event_type": ["incomplete_followup"],
                "acute_recurrent_mi": [pd.NA],
            }
        )
        validate_incomplete_followup(rows)

    def test_exposure_timing_uses_closed_index_admission_interval(self) -> None:
        admission = pd.Timestamp("2020-01-01 10:00")
        discharge = pd.Timestamp("2020-01-03 10:00")
        self.assertEqual(
            exposure_window_status(admission, admission, discharge),
            "within_index_admission",
        )
        self.assertEqual(
            exposure_window_status(discharge, admission, discharge),
            "within_index_admission",
        )
        self.assertEqual(
            exposure_window_status("2020-01-01 09:59", admission, discharge),
            "before_admission",
        )
        self.assertEqual(
            exposure_window_status("2020-01-03 10:01", admission, discharge),
            "after_discharge",
        )

    def test_patient_level_splits_must_be_disjoint(self) -> None:
        disjoint = {
            "train": pd.DataFrame({"SubjectID": [1, 2]}),
            "validation": pd.DataFrame({"SubjectID": [3]}),
            "test": pd.DataFrame({"SubjectID": [4]}),
        }
        validate_patient_split_disjoint(disjoint)
        overlapping = {
            "train": pd.DataFrame({"SubjectID": [1, 2]}),
            "validation": pd.DataFrame({"SubjectID": [2]}),
            "test": pd.DataFrame({"SubjectID": [4]}),
        }
        with self.assertRaises(ValueError):
            validate_patient_split_disjoint(overlapping)

    def test_saved_cohort_and_complete_case_counts_reconcile(self) -> None:
        inputs = _read_inputs()
        checks = _check_inputs(inputs)
        self.assertEqual(inputs["phase13_summary"]["phase11_complete_case_n"], 3230)
        self.assertEqual(checks["valid_first_administration_n"], 1500)
        self.assertEqual(checks["split_patient_overlap"], "none")

    def test_generated_paper_tables_are_reproducible(self) -> None:
        inputs = _read_inputs()
        checks = _check_inputs(inputs)
        flow = _cohort_flow(inputs)
        validate_flow_reconciliation(flow)
        self.assertEqual(
            flow.set_index("stage").loc["eligible_prior_mi_discharge_survivors", "n"],
            7545,
        )
        self.assertEqual(
            flow.set_index("stage").loc["known_treatment_complete_followup", "n"],
            3230,
        )
        table_builders = (
            lambda: _cohort_flow(inputs),
            lambda: _baseline_table(inputs),
            lambda: _endpoint_table(inputs, checks),
            lambda: _final_estimates(inputs),
        )
        for build in table_builders:
            pd.testing.assert_frame_equal(build(), build())

    def test_primary_adjustment_candidates_exclude_post_treatment_features(self) -> None:
        from causal_models.phase16_final_statin.analyze_phase16 import (
            AVAILABLE_CANDIDATES,
            POST_TREATMENT_OR_FORBIDDEN,
            PRIMARY_CANDIDATES,
        )

        self.assertFalse(set(PRIMARY_CANDIDATES) & POST_TREATMENT_OR_FORBIDDEN)
        self.assertFalse(set(AVAILABLE_CANDIDATES) & POST_TREATMENT_OR_FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
