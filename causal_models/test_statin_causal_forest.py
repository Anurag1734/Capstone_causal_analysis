from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from causal_models.statin_causal_forest import (
    BASELINE_FEATURES,
    ExperimentConfig,
    PRIMARY_ADJUSTMENT_FEATURES,
    assess_readiness,
    build_admission_cohort,
    _scalar_float,
    validate_patient_splits,
)


def _admission_rows() -> pd.DataFrame:
    rows = []
    for index in range(6):
        treatment = index % 2
        row = {
            "study_id": 1000 + index,
            "SubjectID": 2000 + index,
            "hadm_id": 3000 + index,
            "prior_mi": 1 if index < 5 else 0,
            "recurrent_mi": treatment,
            "statin_during": treatment,
            "anchor_age": 50 + index,
            "sex_male": index % 2,
            "diabetes": index % 2,
            "hypertension": (index // 2) % 2,
            "ckd": (index // 3) % 2,
            "statin_before": (index // 2) % 2,
            "aspirin_before": index % 2,
            "beta_blocker_before": (index // 3) % 2,
            "acei_before": (index // 2) % 2,
            "statin_after": 1,
            "is_MI": 1,
            "Label_Troponin": "MI_Acute_Presentation",
            "ecg_time": "2099-01-01",
            "z_ecg_1": 1.0,
        }
        rows.extend([row.copy(), row.copy()])
    return pd.DataFrame(rows)


class StatinCausalForestTests(unittest.TestCase):
    def test_normalizes_single_value_estimator_arrays(self) -> None:
        self.assertAlmostEqual(_scalar_float([0.125]), 0.125)
        with self.assertRaisesRegex(ValueError, "Expected a scalar"):
            _scalar_float([0.1, 0.2])

    def test_builds_prior_mi_admission_cohort_and_excludes_leakage_fields(self) -> None:
        cohort, stats = build_admission_cohort(_admission_rows())
        self.assertEqual(len(cohort), 5)
        self.assertEqual(cohort["hadm_id"].nunique(), 5)
        self.assertEqual(stats["admissions_with_conflicting_rows"], 0)
        self.assertEqual(stats["feature_count"], len(BASELINE_FEATURES))
        self.assertTrue(cohort["prior_mi"].eq(1).all())
        self.assertFalse(
            {"statin_after", "is_MI", "Label_Troponin", "ecg_time", "z_ecg_1"}
            & set(cohort.columns)
        )
        self.assertNotIn("statin_before", PRIMARY_ADJUSTMENT_FEATURES)
        self.assertIn("statin_before", BASELINE_FEATURES)

    def test_rejects_conflicting_ecg_rows_within_admission(self) -> None:
        frame = _admission_rows()
        frame.loc[1, "statin_during"] = 1 - frame.loc[1, "statin_during"]
        with self.assertRaisesRegex(ValueError, "conflicting covariates"):
            build_admission_cohort(frame)

    def test_rejects_index_event_label_as_recurrent_outcome(self) -> None:
        with self.assertRaisesRegex(ValueError, "Refusing non-follow-up outcome"):
            build_admission_cohort(_admission_rows(), outcome="is_MI")

    def test_rejects_unapproved_post_treatment_predictors(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicitly approved"):
            build_admission_cohort(
                _admission_rows(),
                features=(*BASELINE_FEATURES, "statin_after"),
            )

    def test_patient_split_validation_detects_overlap(self) -> None:
        frames = {
            "train": pd.DataFrame({"SubjectID": [1, 2]}),
            "validation": pd.DataFrame({"SubjectID": [3]}),
            "test": pd.DataFrame({"SubjectID": [2, 4]}),
        }
        with self.assertRaisesRegex(ValueError, "Patient leakage"):
            validate_patient_splits(frames)

    def test_readiness_blocks_missing_recurrent_endpoint_without_substitution(self) -> None:
        rows = _admission_rows().drop(
            columns=["recurrent_mi", "statin_after", "ecg_time", "z_ecg_1"]
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            for split_index, split in enumerate(("train", "validation", "test")):
                split_rows = rows.copy()
                split_rows["SubjectID"] += split_index * 100
                split_rows["hadm_id"] += split_index * 100
                split_rows.to_parquet(data_dir / f"{split}.parquet", index=False)
            readiness = assess_readiness(
                ExperimentConfig(
                    data_dir=data_dir,
                    output_dir=data_dir / "outputs",
                    recurrence_outcome_validated=False,
                    temporal_order_validated=False,
                )
            )
        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["model_fitted"])
        self.assertIn("is_MI", readiness["blockers"][0])
        self.assertEqual(
            readiness["patient_level_split_validation"],
            {
                "train_vs_validation": 0,
                "train_vs_test": 0,
                "validation_vs_test": 0,
            },
        )

    def test_exploratory_readiness_preserves_unvalidated_assumptions_as_warnings(self) -> None:
        rows = _admission_rows()
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            for split_index, split in enumerate(("train", "validation", "test")):
                split_rows = rows.copy()
                split_rows["SubjectID"] += split_index * 100
                split_rows["hadm_id"] += split_index * 100
                split_rows.to_parquet(data_dir / f"{split}.parquet", index=False)
            readiness = assess_readiness(
                ExperimentConfig(
                    data_dir=data_dir,
                    output_dir=data_dir / "outputs",
                    allow_exploratory_estimation=True,
                )
            )
        self.assertEqual(readiness["status"], "exploratory")
        self.assertEqual(readiness["blockers"], [])
        self.assertEqual(len(readiness["warnings"]), 2)


if __name__ == "__main__":
    unittest.main()
