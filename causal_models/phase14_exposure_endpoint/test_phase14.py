from __future__ import annotations

import unittest

import pandas as pd

from causal_models.phase14_exposure_endpoint.analyze_phase14 import (
    _normalize_record,
    build_exposure_outputs,
    classify_episode,
    is_acute_mi_code,
    timing_status,
)


class Phase14Tests(unittest.TestCase):
    def test_timing_validation_uses_closed_index_interval(self) -> None:
        start = pd.Timestamp("2020-01-01 10:00")
        end = pd.Timestamp("2020-01-02 10:00")
        self.assertEqual(timing_status(start, start, end), "within_index_admission")
        self.assertEqual(timing_status(end, start, end), "within_index_admission")
        self.assertEqual(
            timing_status(start - pd.Timedelta(seconds=1), start, end),
            "before_index_admission",
        )
        self.assertEqual(
            timing_status(end + pd.Timedelta(seconds=1), start, end),
            "after_index_discharge",
        )

    def test_acute_mi_code_rule(self) -> None:
        self.assertTrue(is_acute_mi_code("410.71", 9))
        self.assertTrue(is_acute_mi_code("I21.4", 10))
        self.assertTrue(is_acute_mi_code("I22.2", 10))
        self.assertFalse(is_acute_mi_code("412", 9))

    def test_episode_labels_keep_early_events_and_are_not_adjudications(self) -> None:
        classification, _ = classify_episode(0.5, False, False, False)
        self.assertEqual(classification, "possible continuation of index MI episode")
        classification, _ = classify_episode(10, True, False, False)
        self.assertEqual(classification, "possible transfer/readmission for the same episode")
        classification, _ = classify_episode(60, False, False, False)
        self.assertEqual(classification, "candidate distinct acute MI")
        classification, _ = classify_episode(60, False, False, True)
        self.assertEqual(classification, "candidate distinct acute MI")
        classification, _ = classify_episode(20, False, False, False)
        self.assertEqual(classification, "uncertain episode classification")

    def test_first_administration_timing_and_unmatched_admission_are_preserved(self) -> None:
        exposed = pd.DataFrame(
            {
                "subject_id": [101, 102],
                "hadm_id": [1001, 1002],
                "index_admittime": pd.to_datetime(["2020-01-01 08:00", "2020-01-01 08:00"]),
                "index_dischtime": pd.to_datetime(["2020-01-02 16:00", "2020-01-02 16:00"]),
            }
        )
        raw = pd.DataFrame(
            {
                "subject_id": [101],
                "hadm_id": [1001],
                "charttime": pd.to_datetime(["2020-01-01 10:30"]),
                "medication": ["atorvastatin 40 mg"],
                "emar_id": ["e1"],
                "emar_seq": ["1"],
                "event_txt": ["Administered"],
                "storetime": pd.to_datetime(["2020-01-01 10:35"]),
            }
        )
        administrations = _normalize_record(
            raw,
            exposed,
            "emar_recorded_administration",
            "charttime",
            "medication",
            "emar.csv",
        )
        administrations["emar_id"] = raw["emar_id"].to_numpy()
        administrations["emar_seq"] = raw["emar_seq"].to_numpy()
        administrations["event_txt"] = raw["event_txt"].to_numpy()
        administrations["storetime"] = raw["storetime"].to_numpy()
        timestamps, linkage, first, _ = build_exposure_outputs(
            exposed,
            administrations,
            pd.DataFrame(),
            {"emar": "raw_emar", "prescriptions": "source_unavailable"},
        )
        first_row = first.loc[first["subject_id"].eq(101)].iloc[0]
        self.assertEqual(first_row["hours_admission_to_first"], 2.5)
        self.assertEqual(first_row["hours_first_to_discharge"], 29.5)
        self.assertEqual(first_row["administration_record_count"], 1)
        unmatched = timestamps.loc[timestamps["subject_id"].eq(102)].iloc[0]
        self.assertEqual(unmatched["timing_validation_status"], "no_matched_emar_record")
        self.assertEqual(linkage.iloc[0]["administrations_linked"], 1)


if __name__ == "__main__":
    unittest.main()
