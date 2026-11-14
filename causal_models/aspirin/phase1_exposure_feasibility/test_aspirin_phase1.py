from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from .analyze_aspirin_phase1 import (
    _aspirin_emar_record_count,
    collapse_admission_exposures,
    summarize_binary,
    write_assessment,
)


ROOT = Path(__file__).resolve().parents[3]


class AspirinPhase1Tests(unittest.TestCase):
    def test_binary_summary_keeps_missing_separate(self) -> None:
        summary = summarize_binary(
            pd.DataFrame({"aspirin_before": [1, 0, None]}),
            "aspirin_before",
            "test",
            "index admissions",
        )
        self.assertEqual(summary["positive_or_record_count"], 1)
        self.assertEqual(summary["negative_count"], 1)
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(summary["percent_positive_of_observed"], 50.0)

    def test_absent_variable_is_not_reported_as_all_missing(self) -> None:
        summary = summarize_binary(pd.DataFrame({"hadm_id": [1, 2]}), "aspirin_after", "test", "admissions")
        self.assertEqual(summary["status"], "column_absent")
        self.assertTrue(pd.isna(summary["missing_count"]))

    def test_collapse_rejects_conflicting_admission_values(self) -> None:
        frame = pd.DataFrame(
            {
                "subject_id": [10, 10],
                "hadm_id": [20, 20],
                "aspirin_before": [0, 1],
            }
        )
        with self.assertRaisesRegex(ValueError, "varies within an admission"):
            collapse_admission_exposures(frame, ("aspirin_before",))

    def test_reads_aggregate_emar_count_without_claiming_linkage(self) -> None:
        audit = "Target administrations by class | statin: 1, aspirin: 316,542, beta: 2"
        self.assertEqual(_aspirin_emar_record_count(audit), 316542)
        self.assertIsNone(_aspirin_emar_record_count("No aspirin counts available"))

    def test_generated_assessment_has_expected_cohort_and_exposure_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = write_assessment(ROOT, Path(temporary))
            self.assertEqual(len(paths), 6)
            exposure = pd.read_csv(paths["exposure_csv"])
            cohort = pd.read_csv(paths["cohort_csv"])
            outcomes = pd.read_csv(paths["outcome_csv"])

            index_before = exposure.loc[
                (exposure["scope"] == "eligible_previous_mi_index_admissions")
                & (exposure["variable"] == "aspirin_before")
            ].iloc[0]
            self.assertEqual(index_before["denominator"], 7545)
            self.assertEqual(index_before["positive_or_record_count"], 779)
            self.assertEqual(index_before["negative_count"], 3877)
            self.assertEqual(index_before["missing_count"], 2889)
            self.assertTrue(
                cohort.loc[
                    cohort["measure"] == "eligible_previous_mi_index_patients", "count"
                ].eq(7545).all()
            )
            self.assertEqual(
                int(
                    cohort.loc[
                        cohort["measure"]
                        == "aspirin_before_positive_index_admissions_with_valid_administration",
                        "count",
                    ].iloc[0]
                ),
                21,
            )
            self.assertEqual(
                int(
                    cohort.loc[
                        cohort["measure"]
                        == "timestamped_aspirin_emar_rows_outside_index_admission",
                        "count",
                    ].iloc[0]
                ),
                309,
            )
            acute = outcomes.loc[
                (outcomes["endpoint"] == "acute_code_only_endpoint")
                & (outcomes["measure"] == "first subsequent coded events"),
                "count",
            ]
            self.assertEqual(int(acute.iloc[0]), 555)
            history_code = outcomes.loc[
                (outcomes["endpoint"] == "existing_broad_MI_code_class")
                & (outcomes["measure"] == "icd9_412_only"),
                "count",
            ]
            self.assertEqual(int(history_code.iloc[0]), 1339)
            self.assertTrue(paths["exposure_audit"].is_file())
            self.assertTrue(paths["feasibility_report"].is_file())
            self.assertTrue(paths["completion_report"].is_file())
            source_summary_path = (
                ROOT
                / "causal_models"
                / "aspirin"
                / "phase1_exposure_feasibility"
                / "ASPIRIN_TIMESTAMP_SOURCE_SUMMARY.json"
            )
            source_summary = json.loads(source_summary_path.read_text(encoding="utf-8"))
            self.assertEqual(source_summary["index_admissions_with_aspirin_emar_record"], 2540)
            self.assertEqual(source_summary["index_admissions_with_valid_administered_charttime"], 2509)
            self.assertEqual(source_summary["administered_rows_with_invalid_or_missing_charttime"], 0)
            self.assertEqual(source_summary["duplicate_emar_event_key_rows"], 0)
            first_timing = source_summary["first_administration_timing_by_index_admission"]
            self.assertEqual(first_timing["before_index_admission"], 268)
            self.assertEqual(first_timing["within_index_admission"], 2241)
            self.assertEqual(sum(first_timing.values()), 2509)
            self.assertEqual(
                sum(
                    source_summary[
                        "first_administration_timing_among_aspirin_before_positive_admissions"
                    ].values()
                ),
                21,
            )


if __name__ == "__main__":
    unittest.main()
