"""
data_preparation.py

Extracts and prepares the dedicated HbA1c causal discovery datasets:
- Primary prospective baseline cohort (180-day antecedent window)
- Sensitivity prospective cohorts (90-day and 365-day antecedent windows)
- Continuous and discretized versions
- Generates data-quality and variable-type diagnostic reports
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Set fixed seed
np.random.seed(42)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
REPORTS_DIR = BASE_DIR / "reports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def build_cohorts():
    # 1. Admissions chronology
    adm = pq.read_table("longitudinal/longitudinal/admissions_chronology.parquet").to_pandas()
    adm["admittime"] = pd.to_datetime(adm["admittime"], format="ISO8601")
    adm["dischtime"] = pd.to_datetime(adm["dischtime"], format="ISO8601")

    # 2. MI admissions
    mi_adm = pq.read_table("longitudinal/longitudinal/mi_admissions.parquet").to_pandas()
    mi_adm["admittime"] = pd.to_datetime(mi_adm["admittime"], format="ISO8601")
    mi_hadms = set(mi_adm["hadm_id"])
    adm["is_mi_adm"] = adm["hadm_id"].isin(mi_hadms)

    # 3. Earliest non-MI admission per patient
    adm = adm.sort_values(["subject_id", "admittime", "admission_seq"])
    non_mi = adm[~adm["is_mi_adm"]].drop_duplicates(subset=["subject_id"], keep="first").copy()
    non_mi = non_mi[["subject_id", "hadm_id", "admittime", "dischtime"]]

    # 4. Demographics
    demo = pq.read_table("longitudinal/longitudinal/patients_demographics.parquet").to_pandas()
    demo["sex_male"] = (demo["gender"] == "M").astype(int)

    # 5. Diagnoses
    diag = pq.read_table("longitudinal/longitudinal/diagnoses_all.parquet", 
                         columns=["subject_id", "hadm_id", "icd_code", "icd_version", "admittime"]).to_pandas()
    diag["admittime"] = pd.to_datetime(diag["admittime"], format="ISO8601")

    # Diagnoses on or before baseline admission
    diag_base = diag.merge(non_mi[["subject_id", "admittime"]], on="subject_id", suffixes=("_diag", "_base"))
    diag_prior = diag_base[diag_base["admittime_diag"] <= diag_base["admittime_base"]]

    # Diabetes codes
    is_dm_icd9 = (diag_prior["icd_version"] == 9) & diag_prior["icd_code"].str.startswith("250")
    is_dm_icd10 = (diag_prior["icd_version"] == 10) & diag_prior["icd_code"].str.match("^E(08|09|10|11|13)")
    dm_subjs = set(diag_prior[is_dm_icd9 | is_dm_icd10]["subject_id"])

    # Hypertension codes
    is_htn_icd9 = (diag_prior["icd_version"] == 9) & diag_prior["icd_code"].str.startswith("401")
    is_htn_icd10 = (diag_prior["icd_version"] == 10) & diag_prior["icd_code"].str.match("^I10")
    htn_subjs = set(diag_prior[is_htn_icd9 | is_htn_icd10]["subject_id"])

    # CKD codes
    is_ckd_icd9 = (diag_prior["icd_version"] == 9) & diag_prior["icd_code"].str.startswith("585")
    is_ckd_icd10 = (diag_prior["icd_version"] == 10) & diag_prior["icd_code"].str.match("^N18")
    ckd_subjs = set(diag_prior[is_ckd_icd9 | is_ckd_icd10]["subject_id"])

    # Prior MI (strictly prior to baseline admission)
    prior_mis = mi_adm.merge(non_mi[["subject_id", "admittime"]], on="subject_id", suffixes=("_mi", "_base"))
    prior_mi_subjs = set(prior_mis[prior_mis["admittime_mi"] < prior_mis["admittime_base"]]["subject_id"])

    # Subsequent MI (strictly after baseline admission)
    later_mis = mi_adm.merge(non_mi[["subject_id", "admittime"]], on="subject_id", suffixes=("_mi", "_base"))
    later_mis = later_mis[later_mis["admittime_mi"] > later_mis["admittime_base"]]
    later_mi_subjs = set(later_mis["subject_id"])

    # Baseline diabetic cohort
    cohort = non_mi[non_mi["subject_id"].isin(dm_subjs)].copy()
    cohort = cohort.merge(demo[["subject_id", "anchor_age", "sex_male"]], on="subject_id", how="left")
    cohort["hypertension"] = cohort["subject_id"].isin(htn_subjs).astype(int)
    cohort["ckd"] = cohort["subject_id"].isin(ckd_subjs).astype(int)
    cohort["prior_mi"] = cohort["subject_id"].isin(prior_mi_subjs).astype(int)
    cohort["subsequent_mi"] = cohort["subject_id"].isin(later_mi_subjs).astype(int)

    # 6. Antecedent HbA1c
    table = pq.read_table("clinical_factor_timing_audit.parquet",
                          filters=[("itemid", "=", 50852)],
                          columns=["subject_id", "charttime", "valuenum"])
    hba1c = table.to_pandas()
    hba1c["charttime"] = pd.to_datetime(hba1c["charttime"], format="ISO8601")
    hba1c = hba1c[hba1c["valuenum"].notna() & np.isfinite(hba1c["valuenum"])]

    m = hba1c.merge(cohort[["subject_id", "admittime"]], on="subject_id")
    m["gap_days"] = (m["admittime"] - m["charttime"]).dt.total_seconds() / 86400.0
    m["chartdate"] = m["charttime"].dt.normalize()
    m["basedate"] = m["admittime"].dt.normalize()
    m_ant = m[(m["chartdate"] < m["basedate"]) & (m["gap_days"] >= 0)].copy()

    windows = [90, 180, 365]
    datasets = {}

    for w in windows:
        w_sub = m_ant[m_ant["gap_days"] <= w].copy()
        w_sub = w_sub.sort_values(["subject_id", "charttime"], ascending=[True, False]).drop_duplicates(subset=["subject_id"])
        
        df = cohort.merge(w_sub[["subject_id", "valuenum", "gap_days"]], on="subject_id", how="inner")
        df = df.rename(columns={"valuenum": "hba1c"})
        df["hba1c_state"] = (df["hba1c"] >= 7.0).astype(int)
        
        # Discretized age brackets for discrete sensitivity analysis
        # <50: 0, 50-64: 1, 65-74: 2, >=75: 3
        df["age_bracket"] = pd.cut(df["anchor_age"], bins=[-np.inf, 49, 64, 74, np.inf], labels=[0, 1, 2, 3]).astype(int)
        
        # Save CSV and Parquet
        csv_path = DATA_DIR / f"hba1c_discovery_{w}d.csv"
        df.to_csv(csv_path, index=False)
        datasets[w] = df
        print(f"Window {w}d dataset saved: {df.shape[0]} patients, {df['subsequent_mi'].sum()} subsequent MIs.")

    # Generate data quality diagnostic report
    diagnostics = {}
    primary_df = datasets[180]
    
    core_cols = ["anchor_age", "sex_male", "hypertension", "ckd", "prior_mi", "hba1c", "hba1c_state", "subsequent_mi"]
    for col in core_cols:
        s = primary_df[col]
        diagnostics[col] = {
            "type": "continuous" if col in ["anchor_age", "hba1c"] else "binary",
            "count": int(s.count()),
            "missing_count": int(s.isna().sum()),
            "missing_pct": float(s.isna().mean() * 100),
            "unique_values": int(s.nunique()),
            "mean": float(s.mean()),
            "std": float(s.std()),
            "min": float(s.min()),
            "q25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "q75": float(s.quantile(0.75)),
            "max": float(s.max()),
            "variance": float(s.var()),
        }

    diag_path = RESULTS_DIR / "data_quality_diagnostics.json"
    with open(diag_path, "w", encoding="utf-8") as f:
        json.dump(diagnostics, f, indent=2)
    print(f"Data quality diagnostics saved to {diag_path}")

    return datasets


if __name__ == "__main__":
    build_cohorts()
