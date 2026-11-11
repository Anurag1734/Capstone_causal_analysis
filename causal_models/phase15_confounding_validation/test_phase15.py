from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from causal_models.phase15_confounding_validation.analyze_phase15 import (
    _attach_diagnosis_features,
    _standardized_mean_difference,
    compare_groups,
)


class Phase15Tests(unittest.TestCase):
    def test_continuous_smd_uses_pooled_standard_deviation(self) -> None:
        left = pd.Series([2.0, 4.0, 6.0])
        right = pd.Series([0.0, 2.0, 4.0])
        expected = 2.0 / np.sqrt((4.0 + 4.0) / 2)
        self.assertAlmostEqual(
            _standardized_mean_difference(left, right, "continuous"), expected
        )

    def test_binary_smd_and_missingness_are_reported(self) -> None:
        frame = pd.DataFrame(
            {
                "group": ["treated", "treated", "treated", "control", "control"],
                "x": [1.0, 1.0, np.nan, 0.0, 0.0],
            }
        )
        result = compare_groups(
            frame,
            "treatment",
            "group",
            "treated",
            "control",
            {"x": "binary"},
        ).iloc[0]
        self.assertEqual(result["left_missing_n"], 1)
        self.assertAlmostEqual(result["left_missing_percent"], 100 / 3)
        self.assertEqual(result["right_missing_n"], 0)
        self.assertAlmostEqual(result["smd"], 2.0)

    def test_categorical_variables_expand_to_category_prevalences(self) -> None:
        frame = pd.DataFrame(
            {
                "group": ["a", "a", "b", "b"],
                "insurance": ["X", "Y", "X", "X"],
            }
        )
        result = compare_groups(
            frame,
            "linked",
            "group",
            "a",
            "b",
            {"insurance": "categorical"},
        )
        self.assertEqual(set(result["variable"]), {"insurance=X", "insurance=Y"})
        self.assertEqual(len(result), 2)

    def test_missing_diagnosis_records_remain_missing_not_no_code(self) -> None:
        cohort = pd.DataFrame({"hadm_id": [10, 20]})
        diagnosis_features = pd.DataFrame(
            {"hadm_id": [10], "index_acute_mi_code": [0]}
        )
        result = _attach_diagnosis_features(cohort, diagnosis_features)
        self.assertEqual(result["has_index_diagnosis_record"].tolist(), [1, 0])
        self.assertEqual(result.loc[0, "index_acute_mi_code"], 0)
        self.assertTrue(pd.isna(result.loc[1, "index_acute_mi_code"]))


if __name__ == "__main__":
    unittest.main()
