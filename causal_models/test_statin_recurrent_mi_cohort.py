from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from causal_models.statin_recurrent_mi_cohort import (
    BASELINE_FEATURES,
    assign_existing_patient_splits,
    build_recurrent_mi_cohort,
    export_causal_forest_splits,
)


ORIGIN = pd.Timestamp("2020-01-01")


def _admission(
    patient: int,
    hadm: int,
    admission_day: int,
    discharge_day: int,
    *,
    mi: bool = False,
    death_day: int | None = None,
    hospital_expire: int = 0,
) -> dict[str, object]:
    return {
        "subject_id": patient,
        "hadm_id": hadm,
        "admittime": ORIGIN + pd.Timedelta(days=admission_day),
        "dischtime": ORIGIN + pd.Timedelta(days=discharge_day),
        "deathtime": (
            ORIGIN + pd.Timedelta(days=death_day)
            if death_day is not None
            else pd.NaT
        ),
        "hospital_expire_flag": hospital_expire,
        "admission_seq": hadm,
    }


def _synthetic_inputs() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    admissions = [
        _admission(1, 101, -30, -28, mi=True),
        _admission(1, 102, -5, -3, mi=True),
        _admission(1, 103, 10, 12),
        _admission(1, 104, 35, 38, mi=True),
        _admission(2, 201, -30, -28, mi=True),
        _admission(2, 202, 10, 12),
        _admission(3, 301, -30, -28, mi=True),
        _admission(3, 302, 10, 12),
        _admission(4, 401, -30, -28, mi=True),
        _admission(4, 402, 10, 12),
        _admission(5, 501, -30, -28, mi=True),
        _admission(5, 502, 10, 12),
        _admission(5, 503, 380, 382, mi=True),
        _admission(6, 601, -30, -28, mi=True),
        _admission(6, 602, 10, 12),
        _admission(6, 603, 20, 22, mi=True),
        _admission(7, 701, -30, -28, mi=True),
        _admission(7, 702, 10, 12),
        _admission(7, 703, 20, 21, mi=True),
        _admission(8, 801, -30, -28, mi=True, death_day=-27, hospital_expire=1),
        _admission(8, 802, 10, 12),
        _admission(9, 901, 10, 12),
    ]
    chronology = pd.DataFrame(admissions)
    mi_hadm_ids = {
        101, 102, 104, 201, 301, 401, 501, 503, 601, 603, 701, 703, 801
    }
    mi = chronology.loc[
        chronology["hadm_id"].isin(mi_hadm_ids),
        ["subject_id", "hadm_id", "admittime"],
    ].rename(columns={"admittime": "admittime"})
    obs_rows = []
    for patient in range(1, 10):
        death = None
        observation_end = ORIGIN + pd.DateOffset(months=18)
        precise_death = None
        if patient == 2:
            death = ORIGIN + pd.Timedelta(days=30)
            precise_death = death
            observation_end = death
        elif patient == 4:
            observation_end = ORIGIN + pd.DateOffset(months=5)
        elif patient == 6:
            death = ORIGIN + pd.Timedelta(days=35)
            precise_death = death
        elif patient == 7:
            death = ORIGIN + pd.Timedelta(days=20)
            observation_end = death
        if patient % 2:
            observation_end = observation_end.strftime("%Y-%m-%d")
        else:
            observation_end = observation_end.strftime("%Y-%m-%d %H:%M:%S")
        obs_rows.append(
            {
                "subject_id": patient,
                "last_discharge": ORIGIN + pd.Timedelta(days=12),
                "last_admittime": ORIGIN + pd.Timedelta(days=10),
                "in_hospital_deathtime": precise_death,
                "dod": death,
                "is_dead": int(death is not None),
                "observation_end": observation_end,
            }
        )
    demographics = pd.DataFrame(
        {
            "subject_id": range(1, 10),
            "gender": ["M", "F"] * 4 + ["M"],
            "anchor_age": [50] * 9,
            "anchor_year": [2020] * 9,
            "anchor_year_group": ["2017 - 2019"] * 9,
            "dod": [row["dod"] for row in obs_rows],
        }
    )
    tables = {
        "admissions": chronology,
        "mi": mi,
        "observation": pd.DataFrame(obs_rows),
        "demographics": demographics,
    }
    master_rows = []
    for patient in range(1, 9):
        index_hadm = patient * 100 + 2
        if patient == 1:
            index_hadm = 102
        elif patient == 2:
            index_hadm = 202
        elif patient == 3:
            index_hadm = 302
        elif patient == 4:
            index_hadm = 402
        elif patient == 5:
            index_hadm = 502
        elif patient == 6:
            index_hadm = 602
        elif patient == 7:
            index_hadm = 702
        else:
            index_hadm = 802
        values = {
            "anchor_age": 50 + patient,
            "sex_male": patient % 2,
            "diabetes": patient % 2,
            "hypertension": 1,
            "ckd": 0,
            "statin_before": patient % 2,
            "statin_during": patient % 2,
            "statin_after": 0,
            "aspirin_before": 0,
            "beta_blocker_before": 1,
            "acei_before": 0,
        }
        master_rows.append(
            {"subject_id": patient, "hadm_id": index_hadm, **values, "source_split": "train"}
        )
    return tables, pd.DataFrame(master_rows, columns=["subject_id", "hadm_id", *BASELINE_FEATURES, "source_split"])


class StatinRecurrentMICohortTests(unittest.TestCase):
    def test_selects_first_eligible_surviving_index_and_excludes_index_mi(self) -> None:
        tables, features = _synthetic_inputs()
        cohort, _ = build_recurrent_mi_cohort(tables, features, followup_months=12)
        patient_one = cohort.set_index("subject_id").loc[1]
        self.assertEqual(patient_one["hadm_id"], 102)
        self.assertEqual(patient_one["first_subsequent_mi_hadm_id"], 104)
        self.assertEqual(patient_one["recurrent_mi"], 1)
        self.assertEqual(patient_one["event_type"], "recurrent_mi")
        self.assertEqual(patient_one["prior_mi_hadm_id"], 101)
        self.assertNotIn(9, set(cohort["subject_id"]))
        self.assertNotIn(8, set(cohort["subject_id"]))
        self.assertTrue(
            {"subject_id", "hadm_id", "admittime", "dischtime"}.issubset(cohort.columns)
        )

    def test_competing_death_event_free_censoring_and_horizon(self) -> None:
        tables, features = _synthetic_inputs()
        cohort, _ = build_recurrent_mi_cohort(tables, features, followup_months=12)
        indexed = cohort.set_index("subject_id")
        self.assertEqual(indexed.loc[2, "event_type"], "competing_death")
        self.assertEqual(indexed.loc[2, "recurrent_mi"], 0)
        self.assertEqual(indexed.loc[3, "event_type"], "event_free")
        self.assertEqual(indexed.loc[3, "recurrent_mi"], 0)
        self.assertEqual(indexed.loc[4, "event_type"], "incomplete_followup")
        self.assertTrue(pd.isna(indexed.loc[4, "recurrent_mi"]))
        self.assertEqual(indexed.loc[5, "event_type"], "event_free")
        self.assertEqual(indexed.loc[5, "first_subsequent_mi_hadm_id"], 503)
        self.assertEqual(indexed.loc[6, "event_type"], "recurrent_mi")
        self.assertEqual(indexed.loc[6, "death_indicator"], 1)
        self.assertEqual(indexed.loc[7, "event_type"], "event_order_uncertain")
        self.assertTrue(pd.isna(indexed.loc[7, "recurrent_mi"]))

    def test_retains_treatment_indicators_and_horizon_duration(self) -> None:
        tables, features = _synthetic_inputs()
        cohort, summary = build_recurrent_mi_cohort(tables, features, followup_months=12)
        self.assertTrue(
            {"statin_before", "statin_during", "statin_after"}.issubset(cohort.columns)
        )
        self.assertTrue(cohort["eligible_prior_mi"].eq(1).all())
        self.assertTrue(cohort["survived_to_index_discharge"].eq(1).all())
        self.assertEqual(summary["recurrent_mi_events"], 2)
        self.assertEqual(summary["competing_deaths_before_mi"], 1)
        self.assertEqual(summary["incomplete_followup"], 1)
        self.assertEqual(summary["event_order_uncertain"], 1)

    def test_missing_observation_end_remains_censored_without_fake_duration(self) -> None:
        tables, features = _synthetic_inputs()
        tables["admissions"] = pd.concat(
            [
                tables["admissions"],
                pd.DataFrame(
                    [
                        _admission(10, 1001, -30, -28, mi=True),
                        _admission(10, 1002, 10, 12),
                    ]
                ),
            ],
            ignore_index=True,
        )
        tables["mi"] = pd.concat(
            [
                tables["mi"],
                pd.DataFrame(
                    [
                        {
                            "subject_id": 10,
                            "hadm_id": 1001,
                            "admittime": ORIGIN - pd.Timedelta(days=30),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        tables["demographics"] = pd.concat(
            [
                tables["demographics"],
                pd.DataFrame(
                    [
                        {
                            "subject_id": 10,
                            "gender": "F",
                            "anchor_age": 60,
                            "anchor_year": 2020,
                            "anchor_year_group": "2017 - 2019",
                            "dod": pd.NaT,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        values = {feature: 0 for feature in BASELINE_FEATURES}
        values.update({"anchor_age": 60, "sex_male": 0, "statin_during": 0})
        features = pd.concat(
            [
                features,
                pd.DataFrame(
                    [
                        {
                            "subject_id": 10,
                            "hadm_id": 1002,
                            **values,
                            "source_split": "train",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        cohort, _ = build_recurrent_mi_cohort(tables, features)
        patient = cohort.set_index("subject_id").loc[10]
        self.assertEqual(patient["event_type"], "incomplete_followup")
        self.assertTrue(pd.isna(patient["recurrent_mi"]))
        self.assertTrue(pd.isna(patient["followup_end_date"]))
        self.assertTrue(pd.isna(patient["followup_duration_days"]))

    def test_existing_split_adapter_preserves_patient_boundaries(self) -> None:
        tables, features = _synthetic_inputs()
        cohort, _ = build_recurrent_mi_cohort(tables, features)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            master_dir = root / "master"
            out_dir = root / "out"
            master_dir.mkdir()
            for split, patients in (
                ("train", [1, 2, 3, 4]),
                ("validation", [5, 6]),
                ("test", [7, 8]),
            ):
                pd.DataFrame({"SubjectID": patients}).to_parquet(
                    master_dir / f"{split}.parquet",
                    index=False,
                )
            assigned, counts = assign_existing_patient_splits(cohort, master_dir)
            self.assertEqual(counts["train"], 4)
            self.assertEqual(counts["validation"], 2)
            self.assertEqual(counts["test"], 1)
            self.assertEqual(counts["not_in_existing_master_splits"], 0)
            exported = export_causal_forest_splits(cohort, master_dir, out_dir)
            self.assertEqual(exported["train"], 4)
            train = pd.read_parquet(
                out_dir / "statin_recurrent_mi_forest_splits" / "train.parquet"
            )
            self.assertIn("SubjectID", train.columns)
            self.assertIn("recurrent_mi", train.columns)
            self.assertTrue(train["prior_mi"].eq(1).all())
            self.assertNotIn("is_MI", train.columns)


if __name__ == "__main__":
    unittest.main()
