from __future__ import annotations

import json
import math
import re
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2")
DATA_DIR = ROOT / "master"
PHASE3_PATH = ROOT / "phase3_audit_results.json"
PHASE2_PATH = ROOT / "phase2_audit_results.json"
JSON_PATH = ROOT / "phase4_discovery_ready_dataset_results.json"
NOTEBOOK_PATH = ROOT / "phase4_discovery_ready_dataset.ipynb"
REPORT_PATH = ROOT / "phase4_discovery_ready_dataset_report.md"
SPLITS = ("train", "validation", "test")

IDENTIFIERS = ["study_id", "SubjectID", "hadm_id"]
CLINICAL_CANDIDATES = [
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "prior_mi",
]
TREATMENTS = [
    "statin_before",
    "statin_during",
    "statin_after",
    "beta_blocker_before",
    "beta_blocker_during",
    "acei_before",
    "acei_during",
    "aspirin_before",
    "aspirin_during",
    "vasopressor_during",
    "mech_vent_during",
]
OUTCOME_TEMPORAL = ["Label_Troponin", "is_MI", "index_mi_time", "time_diff_hours"]
TIMESTAMP = ["ecg_time"]
OUTCOME_MI_LABELS = {"MI_Pre-Incident", "MI_Acute_Presentation"}
NEAR_CONSTANT_DOMINANT_THRESHOLD = 0.999
CORRELATION_SAMPLE_MAX = 50_000
HIGH_CORRELATION_THRESHOLD = 0.98


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_splits() -> tuple[pd.DataFrame, dict[str, int], dict[str, pd.DataFrame]]:
    split_frames: dict[str, pd.DataFrame] = {}
    split_rows: dict[str, int] = {}
    for split in SPLITS:
        frame = pd.read_parquet(DATA_DIR / f"{split}.parquet")
        split_frames[split] = frame
        split_rows[split] = int(len(frame))
    combined = pd.concat(
        [frame.assign(_split=split) for split, frame in split_frames.items()],
        ignore_index=True,
    )
    return combined, split_rows, split_frames


def load_phase3_groups(columns: list[str]) -> dict[str, str]:
    if PHASE3_PATH.exists():
        phase3 = json.loads(PHASE3_PATH.read_text(encoding="utf-8"))
        return {
            item["variable"]: item["group"]
            for item in phase3.get("complete_variable_inventory", [])
        }
    return {name: variable_family(name) for name in columns}


def variable_family(name: str) -> str:
    if name in IDENTIFIERS:
        return "G. Identifiers"
    if name in CLINICAL_CANDIDATES:
        return "A. Candidate baseline clinical"
    if name in TREATMENTS:
        return "D. Treatment/exposure"
    if name in OUTCOME_TEMPORAL:
        return "E. Outcome variables"
    if name in TIMESTAMP:
        return "F. Temporal/index variables"
    if re.fullmatch(r"z_ecg_\d+", name):
        return "C. Candidate latent ECG"
    if name.startswith(("Q_", "R_", "S_", "T_", "ST_", "P_", "PQ_", "QRS_", "RR_")):
        return "B. Candidate ECG"
    return "I. Unresolved / other"


def data_source(name: str) -> str:
    family = variable_family(name)
    if name in IDENTIFIERS:
        return "labels backbone / master identifiers (Phase F documentation)"
    if name in {"Label_Troponin", "is_MI", "index_mi_time", "time_diff_hours"}:
        return "labels backbone and MI temporal construction; exact source generation not locally available"
    if name == "ecg_time":
        return "ECG record/labels backbone (Phase F master schema)"
    if name in CLINICAL_CANDIDATES[:2]:
        return "demographics source joined on SubjectID (Phase F documentation)"
    if name in CLINICAL_CANDIDATES[2:]:
        return "clinical comorbidities source joined on hadm_id; ICD-coded history (Phase F documentation)"
    if name in TREATMENTS:
        return "clinical treatment features joined on hadm_id; source queries not present locally"
    if family == "B. Candidate ECG":
        return "ECG features split files joined by study_id (Phase F documentation)"
    if family == "C. Candidate latent ECG":
        return "VAE deterministic mu embeddings joined by study_id (VAE/Phase F documentation)"
    return "No local source evidence identified"


def category_for(name: str) -> str:
    family = variable_family(name)
    return {
        "G. Identifiers": "G. Identifiers",
        "A. Candidate baseline clinical": "A. Candidate baseline clinical variables",
        "B. Candidate ECG": "B. Candidate ECG variables",
        "C. Candidate latent ECG": "C. Candidate latent ECG variables",
        "D. Treatment/exposure": "D. Treatment/exposure variables",
        "E. Outcome variables": "E. Outcome variables",
        "F. Temporal/index variables": "F. Temporal/index variables",
        "I. Unresolved / other": "I. Unresolved variables",
    }.get(family, "H. Downstream/leakage-prone variables")


def temporal_status(name: str) -> str:
    if name in IDENTIFIERS:
        return "administrative; not a causal feature"
    if name in CLINICAL_CANDIDATES:
        return "candidate baseline; provenance/time relative to treatment-specific baseline requires verification"
    if name in TREATMENTS:
        if name.endswith("_before"):
            return "pre-admission window indicator; not proven before eventual causal index ECG"
        if name.endswith("_after"):
            return "post-discharge; downstream"
        return "in-hospital/acute window; ordering relative to ECG/treatment baseline unresolved"
    if name in OUTCOME_TEMPORAL:
        return "outcome/temporal metadata; excluded from causal covariate matrix"
    if name == "ecg_time":
        return "index/temporal metadata; timestamp semantics do not define causal baseline"
    if re.fullmatch(r"z_ecg_\d+", name) or variable_family(name) == "B. Candidate ECG":
        return "UNRESOLVED until an admission ECG is selected relative to treatment-specific baseline"
    return "UNRESOLVED"


def preprocessing_status(name: str) -> str:
    if name in IDENTIFIERS or name in OUTCOME_TEMPORAL or name in TIMESTAMP:
        return "no transformation performed in Phase 4; metadata retained in its own layer"
    if name in CLINICAL_CANDIDATES or name in TREATMENTS:
        return "no imputation, scaling, or re-encoding performed in Phase 4"
    if variable_family(name) in {"B. Candidate ECG", "C. Candidate latent ECG"}:
        return (
            "Master features/embeddings were already produced upstream. Documentation describes winsorization, "
            "Yeo-Johnson transformation, robust scaling for ECG features, and VAE extraction for z_ecg; "
            "fit scope/parameters could not be verified from local source code."
        )
    return "no transformation performed in Phase 4"


def feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    raw = [c for c in df.columns if variable_family(c) == "B. Candidate ECG"]
    latent = [c for c in df.columns if variable_family(c) == "C. Candidate latent ECG"]
    return raw, sorted(latent, key=lambda c: int(c.rsplit("_", 1)[1]))


def split_integrity(split_frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    id_results = {}
    for key in IDENTIFIERS:
        sets = {split: set(frame[key].dropna().tolist()) for split, frame in split_frames.items()}
        overlaps = {}
        for left, right in combinations(SPLITS, 2):
            overlaps[f"{left}__{right}"] = int(len(sets[left] & sets[right]))
        id_results[key] = {
            "distinct_by_split": {split: int(len(values)) for split, values in sets.items()},
            "pairwise_overlap_counts": overlaps,
            "integrity_pass": all(count == 0 for count in overlaps.values()),
        }
    return {
        "method": "Exact set intersection of non-null IDs in the three actual parquet files.",
        "id_results": id_results,
        "all_identifier_overlap_checks_pass": all(v["integrity_pass"] for v in id_results.values()),
        "split_recreation_performed": False,
        "preprocessing_fit_leakage": (
            "UNRESOLVED — project documentation describes preprocessing, but local source code and fitted "
            "transformer artifacts needed to verify train-only fitting were not found."
        ),
    }


def numeric_diagnostics(df: pd.DataFrame, cols: list[str]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    constant: list[str] = []
    near_constant: list[str] = []
    for col in cols:
        s = pd.to_numeric(df[col], errors="coerce")
        nonnull = s.dropna()
        n_unique = int(nonnull.nunique())
        top_fraction = float(nonnull.value_counts(normalize=True, dropna=True).iloc[0]) if len(nonnull) else None
        if n_unique <= 1:
            constant.append(col)
        if top_fraction is not None and top_fraction >= NEAR_CONSTANT_DOMINANT_THRESHOLD and n_unique > 1:
            near_constant.append(col)
        if len(nonnull):
            q01, q25, q50, q75, q99, q999 = nonnull.quantile(
                [0.01, 0.25, 0.5, 0.75, 0.99, 0.999]
            ).tolist()
            iqr = q75 - q25
            details[col] = {
                "count_nonmissing": int(nonnull.size),
                "missing_count": int(s.isna().sum()),
                "unique_count": n_unique,
                "constant": n_unique <= 1,
                "near_constant": bool(top_fraction is not None and top_fraction >= NEAR_CONSTANT_DOMINANT_THRESHOLD and n_unique > 1),
                "dominant_value_fraction": top_fraction,
                "min": float(nonnull.min()),
                "q01": float(q01),
                "q25": float(q25),
                "median": float(q50),
                "q75": float(q75),
                "q99": float(q99),
                "q999": float(q999),
                "max": float(nonnull.max()),
                "iqr": float(iqr),
                "outside_q01_q99_count": int(((nonnull < q01) | (nonnull > q99)).sum()),
                "extreme_values_flagged": (
                    "Values outside empirical 1st/99th percentiles are reported, not removed; "
                    "no universal clinical bounds were available for every ECG feature."
                ),
            }
        else:
            details[col] = {
                "count_nonmissing": 0,
                "missing_count": int(s.isna().sum()),
                "unique_count": 0,
                "constant": True,
                "near_constant": False,
                "dominant_value_fraction": None,
                "min": None,
                "max": None,
            }
    return {
        "feature_column_count": len(cols),
        "near_constant_threshold": NEAR_CONSTANT_DOMINANT_THRESHOLD,
        "constant_columns": constant,
        "near_constant_columns": near_constant,
        "per_variable": details,
    }


def exact_duplicate_columns(df: pd.DataFrame, cols: list[str]) -> list[dict[str, str]]:
    hashes: dict[int, list[str]] = {}
    for col in cols:
        series_hash = int(pd.util.hash_pandas_object(df[col], index=False).sum())
        hashes.setdefault(series_hash, []).append(col)
    duplicates = []
    for candidates in hashes.values():
        if len(candidates) < 2:
            continue
        representatives: list[str] = []
        for col in candidates:
            matched = False
            for representative in representatives:
                if df[col].equals(df[representative]):
                    duplicates.append({"duplicate": col, "matches": representative})
                    matched = True
                    break
            if not matched:
                representatives.append(col)
    return duplicates


def correlation_diagnostics(df: pd.DataFrame, cols: list[str]) -> dict[str, Any]:
    sample_n = min(len(df), CORRELATION_SAMPLE_MAX)
    sample = df[cols].sample(n=sample_n, random_state=42) if sample_n else df[cols]
    numeric = sample.apply(pd.to_numeric, errors="coerce")
    corr = numeric.corr(method="pearson", min_periods=max(100, int(sample_n * 0.5)))
    upper = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1))
    pairs = []
    for col in upper.columns:
        for other, value in upper[col].dropna().items():
            if abs(float(value)) >= HIGH_CORRELATION_THRESHOLD:
                pairs.append(
                    {
                        "variable_1": str(other),
                        "variable_2": str(col),
                        "correlation": float(value),
                    }
                )
    pairs.sort(key=lambda row: abs(row["correlation"]), reverse=True)
    return {
        "feature_count": len(cols),
        "sample_size": sample_n,
        "random_state": 42,
        "method": "Pearson correlation on deterministic row sample; pairwise valid data; no features removed.",
        "high_correlation_threshold_absolute": HIGH_CORRELATION_THRESHOLD,
        "high_correlation_pair_count": len(pairs),
        "high_correlation_pairs_top_100": pairs[:100],
        "interpretation": "Correlation flags redundancy for representation decisions only; no correlated variable was removed.",
    }


def split_distribution_diagnostics(
    split_frames: dict[str, pd.DataFrame], cols: list[str]
) -> dict[str, Any]:
    result = {}
    for col in cols:
        per_split = {}
        for split, frame in split_frames.items():
            s = pd.to_numeric(frame[col], errors="coerce").astype("float64")
            per_split[split] = {
                "count": int(s.notna().sum()),
                "missing_count": int(s.isna().sum()),
                "mean": float(s.mean()) if s.notna().any() else None,
                "std": float(s.std()) if s.notna().any() else None,
                "median": float(s.median()) if s.notna().any() else None,
                "q25": float(s.quantile(0.25)) if s.notna().any() else None,
                "q75": float(s.quantile(0.75)) if s.notna().any() else None,
                "positive_prevalence": float(s.gt(0).mean()) if s.notna().any() else None,
            }
        train_mean = per_split["train"]["mean"]
        train_std = per_split["train"]["std"]
        for split in ("validation", "test"):
            mean = per_split[split]["mean"]
            per_split[split]["standardized_mean_difference_vs_train"] = (
                float((mean - train_mean) / train_std)
                if mean is not None and train_mean is not None and train_std not in (None, 0)
                else None
            )
        result[col] = per_split
    return {
        "variables": result,
        "method": "Descriptive split summaries; no split distribution used for variable selection or transformation fitting.",
    }


def categorical_split_counts(split_frames: dict[str, pd.DataFrame], cols: list[str]) -> dict[str, Any]:
    return {
        col: {
            split: {
                str(key): int(value)
                for key, value in frame[col].value_counts(dropna=False).items()
            }
            for split, frame in split_frames.items()
        }
        for col in cols
    }


def value_domain_checks(df: pd.DataFrame) -> dict[str, Any]:
    binary_fields = [
        "sex_male",
        "diabetes",
        "hypertension",
        "ckd",
        "prior_mi",
        "is_MI",
        *TREATMENTS,
    ]
    observed_binary = {}
    for col in binary_fields:
        values = pd.to_numeric(df[col], errors="coerce")
        outside = values.notna() & ~values.isin([0, 1])
        observed_binary[col] = {
            "nonmissing_unique_values": json_safe(values.dropna().unique().tolist()),
            "values_outside_0_1_count": int(outside.sum()),
            "binary_domain_check_pass": not bool(outside.any()),
        }
    age = pd.to_numeric(df["anchor_age"], errors="coerce")
    return {
        "binary_field_checks": observed_binary,
        "anchor_age": {
            "negative_count": int(age.lt(0).sum()),
            "missing_count": int(age.isna().sum()),
            "minimum": float(age.min()) if age.notna().any() else None,
            "maximum": float(age.max()) if age.notna().any() else None,
            "clinical_bounds_applied": False,
            "reason": "No supported bound for de-identified anchor_age was specified; values are reported without silently filtering.",
        },
        "ecg_physiologic_impossible_value_rules": (
            "Not applied: source documentation did not provide validated universal bounds for all 95 ECG feature families."
        ),
    }


def admission_consistency(df: pd.DataFrame, cols: list[str]) -> dict[str, Any]:
    result = {}
    for col in cols:
        n_unique = df.groupby("hadm_id", dropna=False)[col].nunique(dropna=True)
        result[col] = {
            "admissions": int(n_unique.size),
            "inconsistent_admissions": int(n_unique.gt(1).sum()),
            "inconsistent_percentage": float(n_unique.gt(1).mean() * 100) if len(n_unique) else 0.0,
            "constant_within_admission": bool(not n_unique.gt(1).any()),
        }
    return result


def admission_label_status(df: pd.DataFrame) -> pd.DataFrame:
    mi_labels = OUTCOME_MI_LABELS
    rows = []
    for hadm_id, group in df.groupby("hadm_id", sort=False, dropna=False):
        labels = set(group["Label_Troponin"].dropna().astype(str))
        is_mi_admission = bool(labels & mi_labels)
        has_control = "Control_Symptomatic" in labels
        if is_mi_admission and has_control:
            status = "mixed MI/control labels within admission"
        elif is_mi_admission:
            status = "MI-labeled admission"
        else:
            status = "Control_Symptomatic-only admission" if has_control else "unclassified admission"
        rows.append(
            {
                "hadm_id": hadm_id,
                "SubjectID": group["SubjectID"].dropna().iloc[0] if group["SubjectID"].notna().any() else None,
                "split": group["_split"].iloc[0],
                "admission_label_status": status,
                "is_mi_admission": is_mi_admission,
                "n_ecg_rows": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def candidate_ecg_rules(df: pd.DataFrame, admission_status: pd.DataFrame) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    work = df.copy()
    work["_ecg_dt"] = pd.to_datetime(work["ecg_time"], errors="coerce", utc=True)
    if "index_mi_time" in work:
        work["_mi_dt"] = pd.to_datetime(work["index_mi_time"], errors="coerce", utc=True)
    work = work.sort_values(["hadm_id", "_ecg_dt", "study_id"], kind="mergesort", na_position="last")

    candidates: dict[str, pd.DataFrame] = {}
    first = work[work["_ecg_dt"].notna()].drop_duplicates("hadm_id", keep="first").copy()
    candidates["A_first_ecg_admission"] = first

    label_mi_admissions = set(
        admission_status.loc[admission_status["is_mi_admission"], "hadm_id"].tolist()
    )
    mi_label_rows = work[
        work["hadm_id"].isin(label_mi_admissions)
        & work["Label_Troponin"].isin(OUTCOME_MI_LABELS)
        & work["_mi_dt"].notna()
    ].copy()
    event_counts = mi_label_rows.groupby("hadm_id")["_mi_dt"].nunique()
    consistent_event_admissions = set(event_counts[event_counts.eq(1)].index)
    event_time = mi_label_rows.groupby("hadm_id")["_mi_dt"].first()
    # Select from every ECG in an eligible admission, not only rows carrying an MI label.
    mi_rows = work[work["hadm_id"].isin(consistent_event_admissions)].copy()
    mi_rows["_event_time"] = mi_rows["hadm_id"].map(event_time)
    before = mi_rows[
        mi_rows["_ecg_dt"].notna()
        & mi_rows["_event_time"].notna()
        & (mi_rows["_ecg_dt"] < mi_rows["_event_time"])
    ].copy()
    first_before = before.sort_values(["hadm_id", "_ecg_dt", "study_id"], kind="mergesort").drop_duplicates(
        "hadm_id", keep="first"
    )
    nearest_before = before.assign(
        _distance_hours=(before["_event_time"] - before["_ecg_dt"]).dt.total_seconds() / 3600
    ).sort_values(["hadm_id", "_distance_hours", "_ecg_dt", "study_id"], kind="mergesort").drop_duplicates(
        "hadm_id", keep="first"
    )
    candidates["B_first_ecg_before_MI"] = first_before
    candidates["C_closest_ecg_before_MI"] = nearest_before

    common_bc = first_before.set_index("hadm_id").index.intersection(
        nearest_before.set_index("hadm_id").index
    )
    b_ids = first_before.set_index("hadm_id").loc[common_bc, "study_id"]
    c_ids = nearest_before.set_index("hadm_id").loc[common_bc, "study_id"]
    bc_different = int(b_ids.ne(c_ids).sum())

    status = admission_status.set_index("hadm_id")
    metrics = {}
    total_admissions = int(len(admission_status))
    mi_admission_ids = set(admission_status.loc[admission_status["is_mi_admission"], "hadm_id"])
    control_ids = set(admission_status.loc[~admission_status["is_mi_admission"], "hadm_id"])
    for rule, selected in candidates.items():
        selected_ids = set(selected["hadm_id"].tolist())
        represented = selected_ids & set(status.index)
        metrics[rule] = {
            "admissions_represented": int(len(represented)),
            "admissions_excluded_from_all_admissions": int(total_admissions - len(represented)),
            "MI_admissions_represented": int(len(represented & mi_admission_ids)),
            "control_only_admissions_represented": int(len(represented & control_ids)),
            "mixed_label_admissions_represented": int(
                status.loc[list(represented), "admission_label_status"].eq("mixed MI/control labels within admission").sum()
            ) if represented else 0,
            "selected_rows_with_valid_ecg_time": int(selected["_ecg_dt"].notna().sum()),
            "selection_uses_Label_Troponin_or_is_MI": rule != "A_first_ecg_admission",
            "selection_uses_index_mi_time": rule != "A_first_ecg_admission",
            "uses_future_or_outcome_time_information": rule != "A_first_ecg_admission",
            "treatment_specific_baseline_compatibility": (
                "UNRESOLVED; even earliest ECG is not proven before treatment assignment"
                if rule == "A_first_ecg_admission"
                else "Not established; MI/outcome-time-dependent selection and exact treatment timing unavailable"
            ),
            "causal_discovery_use": "PROVISIONAL / CANDIDATE REPRESENTATION ONLY; not final causal baseline",
        }
    eligible_mi_time_ids = consistent_event_admissions
    metrics["B_first_ecg_before_MI"]["MI_admissions_with_valid_unique_event_time"] = len(eligible_mi_time_ids)
    metrics["C_closest_ecg_before_MI"]["MI_admissions_with_valid_unique_event_time"] = len(eligible_mi_time_ids)
    metrics["B_first_ecg_before_MI"]["MI_admissions_with_no_pre_MI_ECG_excluded"] = int(
        len(eligible_mi_time_ids - set(first_before["hadm_id"]))
    )
    metrics["C_closest_ecg_before_MI"]["MI_admissions_with_no_pre_MI_ECG_excluded"] = int(
        len(eligible_mi_time_ids - set(nearest_before["hadm_id"]))
    )
    invalid_mi_time_admissions = label_mi_admissions - consistent_event_admissions
    metrics["B_first_ecg_before_MI"]["MI_admissions_excluded_missing_or_nonunique_index_mi_time"] = len(invalid_mi_time_admissions)
    metrics["C_closest_ecg_before_MI"]["MI_admissions_excluded_missing_or_nonunique_index_mi_time"] = len(invalid_mi_time_admissions)
    metrics["D_first_clinically_eligible"] = {
        "admissions_represented": None,
        "admissions_excluded_from_all_admissions": None,
        "MI_admissions_represented": None,
        "control_only_admissions_represented": None,
        "selection_uses_Label_Troponin_or_is_MI": "UNRESOLVED",
        "selection_uses_index_mi_time": "UNRESOLVED",
        "uses_future_or_outcome_time_information": "UNRESOLVED",
        "treatment_specific_baseline_compatibility": "BLOCKED — no prespecified clinical eligibility criterion or exact treatment timing.",
        "causal_discovery_use": "Not constructable from current data without inventing clinical eligibility criteria.",
    }
    metrics["B_vs_C_selected_study_id_comparison"] = {
        "common_eligible_admissions": int(len(common_bc)),
        "admissions_selecting_different_study_id": bc_different,
        "percentage_of_common_eligible_admissions_different": (
            float(bc_different / len(common_bc) * 100) if len(common_bc) else 0.0
        ),
        "identical_selections": bc_different == 0,
        "interpretation": (
            "Identical eligible counts do not imply identical ECG selection; both rules remain outcome/time-dependent candidates."
        ),
    }
    metrics["_admission_classification"] = {
        "MI_labeled_admissions": int(len(mi_admission_ids)),
        "control_only_admissions": int(len(control_ids)),
        "mixed_MI_control_label_admissions": int(
            admission_status["admission_label_status"].eq("mixed MI/control labels within admission").sum()
        ),
        "unclassified_admissions": int(admission_status["admission_label_status"].eq("unclassified admission").sum()),
    }
    return metrics, candidates


def feature_diagnostics(df: pd.DataFrame, raw_features: list[str], latent_features: list[str]) -> dict[str, Any]:
    all_features = raw_features + latent_features
    raw_diag = numeric_diagnostics(df, raw_features)
    latent_diag = numeric_diagnostics(df, latent_features)
    duplicates = exact_duplicate_columns(df, all_features)
    return {
        "raw_ecg": raw_diag,
        "z_ecg": latent_diag,
        "exact_duplicate_features": duplicates,
        "correlation_redundancy": correlation_diagnostics(df, all_features),
        "split_distribution": split_distribution_diagnostics(
            {split: frame for split, frame in _SPLIT_FRAMES.items()},
            all_features,
        ),
        "no_features_removed": True,
    }


_SPLIT_FRAMES: dict[str, pd.DataFrame] = {}


def variable_inventory(
    df: pd.DataFrame,
    raw_features: list[str],
    latent_features: list[str],
    numeric: dict[str, Any],
    admission_consistency_results: dict[str, Any],
) -> list[dict[str, Any]]:
    inventory = []
    feature_details = {
        **numeric["raw_ecg"]["per_variable"],
        **numeric["z_ecg"]["per_variable"],
    }
    for name in df.columns:
        if name == "_split":
            continue
        family = category_for(name)
        series = df[name]
        n_unique = int(series.nunique(dropna=True))
        feat_detail = feature_details.get(name, {})
        if name in admission_consistency_results:
            consistency = admission_consistency_results[name]
        else:
            consistency = None
        inclusion = False
        exclusion_reason = ""
        if name in CLINICAL_CANDIDATES:
            inclusion = True
            exclusion_reason = "Candidate only; temporal/provenance verification remains required."
        elif name in raw_features or name in latent_features:
            exclusion_reason = "Quarantined until an index ECG is selected and treatment/outcome timing is resolved."
        elif name in TREATMENTS:
            exclusion_reason = "Maintained in separate treatment/exposure layer; not generic baseline matrix."
        elif name in OUTCOME_TEMPORAL:
            exclusion_reason = "Outcome/temporal metadata; explicitly excluded from discovery covariate matrix."
        elif name in IDENTIFIERS:
            exclusion_reason = "Metadata/linkage only; identifiers are not ordinary causal covariates."
        elif name == "ecg_time":
            exclusion_reason = "Temporal metadata for ECG selection, not a covariate."
        else:
            exclusion_reason = "Unresolved/unclassified field; excluded pending provenance review."
        inventory.append(
            {
                "variable": name,
                "source_table_or_file": data_source(name),
                "variable_family": family,
                "data_type": str(series.dtype),
                "unit": (
                    "years" if name == "anchor_age" else
                    "binary indicator" if name in {"sex_male", *TREATMENTS, "is_MI", "diabetes", "hypertension", "ckd", "prior_mi"} else
                    "hours" if name == "time_diff_hours" else
                    "timestamp string" if name in {"ecg_time", "index_mi_time"} else
                    "latent dimension (unitless)" if name in latent_features else
                    "ECG feature; source units not fully documented" if name in raw_features else None
                ),
                "granularity": (
                    "patient" if name == "SubjectID" else
                    "admission" if name == "hadm_id" else
                    "ECG" if name == "study_id" or name == "ecg_time" or name in raw_features or name in latent_features else
                    "admission/patient value repeated across ECG rows" if name in CLINICAL_CANDIDATES or name in TREATMENTS else
                    "ECG row / event metadata"
                ),
                "missing_count": int(series.isna().sum()),
                "missing_percentage": float(series.isna().mean() * 100),
                "cardinality": n_unique,
                "constant": n_unique <= 1,
                "near_constant_dominant_fraction_ge_99_9pct": bool(feat_detail.get("near_constant", False)),
                "range_min": feat_detail.get("min"),
                "range_max": feat_detail.get("max"),
                "temporal_status": temporal_status(name),
                "preprocessing_status": preprocessing_status(name),
                "admission_level_consistency": consistency,
                "included_in_candidate_discovery_schema": inclusion,
                "exclusion_reason": exclusion_reason,
                "unresolved_issue": (
                    "Index ECG / time-zero ordering and source provenance remain unresolved."
                    if name in raw_features or name in latent_features
                    else "Verify provenance/time window relative to treatment-specific baseline."
                    if name in CLINICAL_CANDIDATES
                    else None
                ),
            }
        )
    return inventory


def clinical_and_treatment_summaries(df: pd.DataFrame, admission_status: pd.DataFrame) -> dict[str, Any]:
    adm = df.sort_values(["hadm_id", "study_id"], kind="mergesort").drop_duplicates("hadm_id")
    summary = {}
    for name in CLINICAL_CANDIDATES + TREATMENTS:
        series = adm[name]
        summary[name] = {
            "admission_count": int(series.size),
            "nonmissing_count": int(series.notna().sum()),
            "missing_count": int(series.isna().sum()),
            "positive_count": int(series.eq(1).sum()) if pd.api.types.is_numeric_dtype(series) else None,
            "positive_percentage": float(series.eq(1).mean() * 100) if pd.api.types.is_numeric_dtype(series) else None,
            "unique_values": json_safe(series.dropna().unique().tolist())[:20],
        }
    return {
        "admission_level_value_summary": summary,
        "clinical_variable_prevalence": {
            name: summary[name] for name in CLINICAL_CANDIDATES
        },
        "treatment_prevalence": {
            name: summary[name] for name in TREATMENTS
        },
        "admission_classification": {
            "MI_labeled": int(admission_status["is_mi_admission"].sum()),
            "control_only": int((~admission_status["is_mi_admission"]).sum()),
            "mixed_label": int(admission_status["admission_label_status"].eq("mixed MI/control labels within admission").sum()),
        },
    }


def build_layer_tables(
    df: pd.DataFrame,
    raw: list[str],
    latent: list[str],
    selected_frames: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    admission_rows = (
        df.sort_values(["hadm_id", "study_id"], kind="mergesort")
        .drop_duplicates("hadm_id", keep="first")
    )
    layer1_cols = ["hadm_id", "SubjectID", "_split"]
    layer1 = admission_rows[layer1_cols].copy()
    layer2 = admission_rows[layer1_cols + CLINICAL_CANDIDATES].copy()
    layer4 = admission_rows[layer1_cols + TREATMENTS].copy()
    layer5_cols = IDENTIFIERS + ["_split", "ecg_time"] + OUTCOME_TEMPORAL
    layer5 = df[layer5_cols].copy()
    tables = {
        "layer_1_admission_metadata": layer1,
        "layer_2_candidate_clinical_baseline": layer2,
        "layer_4_treatment_exposure": layer4,
        "layer_5_outcome_temporal_metadata": layer5,
    }
    feature_cols = IDENTIFIERS + ["_split"] + raw + latent
    for rule in ("A_first_ecg_admission", "B_first_ecg_before_MI", "C_closest_ecg_before_MI"):
        selected = selected_frames[rule]
        tables[f"layer_3_{rule}"] = selected[feature_cols].copy()
    return tables


def layer_architecture(
    df: pd.DataFrame,
    raw: list[str],
    latent: list[str],
    tables: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    unique_admissions = int(df["hadm_id"].nunique())
    table_summaries = {
        name: {
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
            "schema": list(frame.columns),
            "physically_exported": False,
        }
        for name, frame in tables.items()
    }
    return {
        "layer_1_admission_metadata": {
            "schema": ["hadm_id", "SubjectID", "_split"],
            "rows": int(len(tables["layer_1_admission_metadata"])),
            "causal_features": False,
            "use": "unit, split preservation, linkage, patient dependence",
        },
        "layer_2_candidate_clinical_baseline": {
            "schema": CLINICAL_CANDIDATES,
            "rows": int(len(tables["layer_2_candidate_clinical_baseline"])),
            "status": "PROVISIONAL; one value/admission only after verifying within-admission consistency; temporal provenance still unresolved",
            "causal_features": "candidate schema only, not confirmed adjustment set",
        },
        "layer_3_candidate_ecg_representations": {
            "raw_ecg_feature_count": len(raw),
            "raw_ecg_features": raw,
            "latent_feature_count": len(latent),
            "latent_features": latent,
            "representations": ["A_first_ecg_admission", "B_first_ecg_before_MI", "C_closest_ecg_before_MI"],
            "candidate_table_shapes": {
                name.removeprefix("layer_3_"): summary["rows"]
                for name, summary in table_summaries.items()
                if name.startswith("layer_3_")
            },
            "status": "quarantined provisional representations; not a final causal index ECG",
            "physically_exported": False,
        },
        "layer_4_treatment_exposure": {
            "schema": TREATMENTS,
            "rows": int(len(tables["layer_4_treatment_exposure"])),
            "status": "separate metadata layer; timing unresolved; not included in generic covariate matrix",
        },
        "layer_5_outcome_temporal_metadata": {
            "schema": OUTCOME_TEMPORAL + TIMESTAMP,
            "rows": int(len(tables["layer_5_outcome_temporal_metadata"])),
            "status": "separate audit/index layer; excluded from discovery covariates",
        },
        "in_memory_table_summaries": table_summaries,
        "tables_persisted": False,
        "persistence_reason": (
            "The ECG tables are retained only as separate candidate representations; no final causal selection exists, "
            "so no potentially misleading discovery-ready feature matrix is exported."
        ),
        "operational_recommendation": (
            "Keep admission metadata, clinical candidates, ECG candidate representations, treatments, and "
            "outcome/temporal metadata in separate layers. No single merged causal feature matrix is emitted."
        ),
    }


def leakage_checks(raw_features: list[str], latent_features: list[str], inventory: list[dict[str, Any]]) -> dict[str, Any]:
    troponin_like = [r["variable"] for r in inventory if "troponin" in r["variable"].lower()]
    outcome_cols = OUTCOME_TEMPORAL
    treatment_cols = TREATMENTS
    post_discharge = ["statin_after"]
    return {
        "explicit_outcome_columns_excluded": outcome_cols,
        "troponin_named_columns_in_actual_schema": troponin_like,
        "troponin_rule": "NEVER USE TROPONIN AS A FEATURE; no troponin-named master feature is present in the 184-column schema.",
        "post_discharge_columns_excluded_from_baseline": post_discharge,
        "acute_treatment_columns_separate": [
            c for c in treatment_cols if c.endswith("_during") or c in {"vasopressor_during", "mech_vent_during"}
        ],
        "future_ecg_leakage": (
            "Candidate ECG rules select one ECG per admission for evaluation only. No future ECGs are aggregated; "
            "the A rule is earliest timestamp, while B/C use MI outcome time and are explicitly outcome/time-dependent."
        ),
        "indirect_label_leakage": (
            "ECG features and z_ecg may encode MI morphology. This is not proven leakage by itself, but baseline use is "
            "blocked until the selected ECG is temporally eligible."
        ),
        "preprocessing_leakage": (
            "UNRESOLVED — project documentation lists winsorization, Yeo-Johnson, and robust scaling; local fitting code "
            "and fitted artifacts were not found to establish training-only fitting or confirm outcome/treatment independence."
        ),
        "candidate_feature_counts": {"raw_ecg": len(raw_features), "z_ecg": len(latent_features)},
        "no_label_or_treatment_guided_preprocessing_in_phase4": True,
    }


def make_results(
    df: pd.DataFrame, split_rows: dict[str, int], split_frames: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    global _SPLIT_FRAMES
    _SPLIT_FRAMES = split_frames
    raw, latent = feature_columns(df)
    if len(raw) != 95 or len(latent) != 64:
        raise ValueError(f"Expected 95 raw ECG features and 64 z_ecg dimensions; found {len(raw)} and {len(latent)}.")
    status = admission_label_status(df)
    selection, selected_frames = candidate_ecg_rules(df, status)
    layer_tables = build_layer_tables(df, raw, latent, selected_frames)
    consistency_cols = CLINICAL_CANDIDATES + TREATMENTS
    consistency = admission_consistency(df, consistency_cols)
    features = feature_diagnostics(df, raw, latent)
    inventory = variable_inventory(df.drop(columns=["_split"]), raw, latent, features, consistency)
    # Include split as metadata explicitly, not as one of the original master variables.
    for row in inventory:
        if row["variable"] in IDENTIFIERS:
            row["split_integrity_role"] = "identifier overlap assessed separately across parquet splits"
    all_numeric = [
        c for c in df.columns
        if c != "_split" and c not in IDENTIFIERS and pd.api.types.is_numeric_dtype(df[c])
    ]
    categorical_labels = categorical_split_counts(split_frames, ["Label_Troponin"])
    split_integrity_result = split_integrity(split_frames)
    return {
        "input_summary": {
            "split_rows": split_rows,
            "combined_rows": int(len(df)),
            "column_count_original": int(len(df.columns) - 1),
            "patients": int(df["SubjectID"].nunique()),
            "admissions": int(df["hadm_id"].nunique()),
            "ecg_rows": int(len(df)),
            "study_id_unique": bool(df["study_id"].is_unique),
            "primary_observational_unit": "admission",
            "identifiers": IDENTIFIERS,
            "repeated_ecg": {
                "admissions_with_multiple_ecgs": int(df.groupby("hadm_id").size().gt(1).sum()),
                "fraction_admissions_with_multiple_ecgs": float(df.groupby("hadm_id").size().gt(1).mean()),
                "maximum_ecgs_per_admission": int(df.groupby("hadm_id").size().max()),
            },
            "repeated_admissions": {
                "patients_with_multiple_admissions": int(df.groupby("SubjectID")["hadm_id"].nunique().gt(1).sum()),
                "fraction_patients_with_multiple_admissions": float(df.groupby("SubjectID")["hadm_id"].nunique().gt(1).mean()),
                "maximum_admissions_per_patient": int(df.groupby("SubjectID")["hadm_id"].nunique().max()),
            },
        },
        "split_integrity": split_integrity_result,
        "admission_level_consistency": consistency,
        "candidate_rule_comparison": selection,
        "candidate_rule_selection_records": {
            name: {
                "selected_rows": int(len(frame)),
                "selected_study_id_unique": bool(frame["study_id"].is_unique),
                "persisted_as_final_dataset": False,
                "representation_status": "PROVISIONAL / CANDIDATE REPRESENTATION",
            }
            for name, frame in selected_frames.items()
        },
        "feature_diagnostics": features,
        "value_domain_checks": value_domain_checks(df),
        "all_numeric_columns_count": len(all_numeric),
        "clinical_variable_prevalence": clinical_and_treatment_summaries(df, status)["clinical_variable_prevalence"],
        "treatment_prevalence": clinical_and_treatment_summaries(df, status)["treatment_prevalence"],
        "clinical_and_treatment_admission_summary": clinical_and_treatment_summaries(df, status),
        "distribution_shifts": split_distribution_diagnostics(split_frames, all_numeric),
        "categorical_split_counts": categorical_labels,
        "complete_variable_inventory": inventory,
        "discovery_layers": layer_architecture(df, raw, latent, layer_tables),
        "leakage_checks": leakage_checks(raw, latent, inventory),
        "preprocessing_specification": {
            "phase4_transformations_applied": [],
            "missing_values": "No imputation; report missingness and preserve existing values.",
            "categorical_binary_encoding": "No re-encoding; preserve source encoding.",
            "scaling": "No new scaling; any upstream ECG-feature scaling is documented but fit scope is unverified.",
            "constant_columns": "Diagnosed and retained; no automatic column removal.",
            "correlated_columns": "Diagnosed and retained; correlation alone is not an exclusion reason.",
            "extreme_values": "Quantile ranges reported; no winsorization or clipping in Phase 4.",
            "learned_transformers": "None fit in Phase 4; no whole-data fitting or outcome/treatment-guided transformation.",
            "upstream_preprocessing_fit_scope": "UNRESOLVED pending access to original fit scripts and artifacts.",
        },
        "clinical_and_treatment_prevalence_method": (
            "Admission-level value summaries from the one-per-hadm_id consistency-checked representation; "
            "does not treat repeated ECG rows as independent treatment assignments."
        ),
        "decision_record": {
            "discovery_ready_observational_unit": "Admission-level, preserved.",
            "admission_representation": "One metadata row per hadm_id; patient ID retained for dependence; ECG-linked values kept in separate provisional selections.",
            "candidate_ecg_selection_rules_constructed": ["A_first_ecg_admission", "B_first_ecg_before_MI", "C_closest_ecg_before_MI"],
            "preferred_operational_representation": (
                "Rule A is a neutral provisional operational selection by earliest ecg_time, not a preferred causal baseline. "
                "No final rule is chosen."
            ),
            "candidate_clinical_variables": CLINICAL_CANDIDATES,
            "ecg_variables_retained": {"raw_feature_count": len(raw), "latent_dimension_count": len(latent), "removed": []},
            "z_ecg_handling": "Retain all 64 dimensions in the quarantined candidate layer; no PCA. Timing and training-preprocessing lineage unresolved.",
            "treatment_variables": "Separate treatment layer; no primary treatment selected; not generic baseline covariates.",
            "outcome_variables_excluded": OUTCOME_TEMPORAL,
            "leakage_variables_excluded": OUTCOME_TEMPORAL + ["statin_after"] + [
                c for c in TREATMENTS if c.endswith("_during")
            ],
            "preprocessing_performed": "Audit/diagnostics only; no transforms, imputation, clipping, or feature removal.",
            "split_integrity_result": split_integrity_result["all_identifier_overlap_checks_pass"],
            "remaining_unresolved_issues": [
                "Final index ECG and treatment-specific causal time zero.",
                "Exact treatment assignment relative to selected ECG.",
                "Upstream ECG preprocessing fit partitions and whether outcome/treatment influenced fit or selection.",
                "Comorbidity/history feature extraction windows and possible current-admission information.",
                "VAE training membership/checkpoint lineage and timing of each ECG representation relative to treatment/outcome.",
                "Outcome definition and event horizon remain frozen as unresolved from Phase 2.",
            ],
            "blockers": [
                "BLOCKED — no final causal ECG-level selection without treatment-specific time zero.",
                "BLOCKED — raw ECG and z_ecg temporal eligibility cannot be established.",
                "BLOCKED — cannot verify train-only preprocessing fitting from local scripts/artifacts.",
            ],
            "phase5_handoff": (
                "Phase 5 must audit z_ecg source lineage: confirm the waveform/study_id mapping, exact train/validation/test "
                "membership used to fit the VAE, checkpoint provenance, preprocessing fit scope, and whether any held-out "
                "or future ECG waveforms entered training. It must keep latent timing relative to treatment and outcome unresolved "
                "until an index ECG/time zero is established."
            ),
            "phase7_readiness": (
                "Partially ready for data architecture and descriptive diagnostics only. BLOCKED for causal discovery input "
                "matrix because index ECG, treatment time zero, outcome definition, and upstream preprocessing leakage checks "
                "remain unresolved."
            ),
            "phase5_or_phase7_performed": False,
        },
    }


def report_markdown(results: dict[str, Any]) -> str:
    summary = results["input_summary"]
    split = results["split_integrity"]
    rules = results["candidate_rule_comparison"]
    decision = results["decision_record"]
    group_counts = {}
    for row in results["complete_variable_inventory"]:
        group_counts[row["variable_family"]] = group_counts.get(row["variable_family"], 0) + 1
    lines = [
        "# Phase 4 — Discovery-Ready Dataset Construction",
        "",
        "## A. Objective",
        "",
        "Construct and document a layered, provisional data representation for later causal discovery. No DAG, discovery algorithm, treatment-effect estimation, final treatment, time zero, index ECG, or adjustment set is selected.",
        "",
        "## B. Input dataset",
        "",
        f"Actual splits: train {summary['split_rows']['train']:,}; validation {summary['split_rows']['validation']:,}; test {summary['split_rows']['test']:,}; combined {summary['ecg_rows']:,} ECG rows, {summary['admissions']:,} admissions, {summary['patients']:,} patients, {results['input_summary']['column_count_original']} original variables.",
        "",
        "## C. Unit of analysis",
        "",
        "Admission-level remains the primary observational unit. `hadm_id` is the admission key, `SubjectID` is retained for patient dependence, and `study_id` links ECG observations. Identifiers are not causal covariates.",
        "",
        f"Repeated ECGs: {summary['repeated_ecg']['admissions_with_multiple_ecgs']:,} admissions ({summary['repeated_ecg']['fraction_admissions_with_multiple_ecgs']:.3%}) have multiple ECGs; maximum {summary['repeated_ecg']['maximum_ecgs_per_admission']}. Repeated admissions: {summary['repeated_admissions']['patients_with_multiple_admissions']:,} patients; maximum {summary['repeated_admissions']['maximum_admissions_per_patient']} admissions per patient.",
        "",
        "## D. ECG selection",
        "",
        "| Candidate rule | Admissions represented | Excluded | MI admissions | Control-only admissions | Outcome/time dependent | Status |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for rule in ["A_first_ecg_admission", "B_first_ecg_before_MI", "C_closest_ecg_before_MI"]:
        row = rules[rule]
        lines.append(
            f"| {rule} | {row['admissions_represented']:,} | {row['admissions_excluded_from_all_admissions']:,} | "
            f"{row['MI_admissions_represented']:,} | {row['control_only_admissions_represented']:,} | "
            f"{row['uses_future_or_outcome_time_information']} | PROVISIONAL / CANDIDATE |"
        )
    bc = rules["B_vs_C_selected_study_id_comparison"]
    lines += [
        "",
        f"Among B/C's {bc['common_eligible_admissions']:,} common eligible admissions, the rules select different ECGs in {bc['admissions_selecting_different_study_id']:,} admissions ({bc['percentage_of_common_eligible_admissions_different']:.2f}%).",
        "",
        "Rule A selects the earliest ECG timestamp per admission where timestamp is valid; it is operationally neutral but not established as pre-treatment. Rules B/C require MI-labeled admissions with a unique non-null MI timestamp and use that event time to select an ECG; they are outcome/time-dependent and do not represent controls. Rule D is blocked because no clinical eligibility criterion is available. No final causal index ECG is declared and no candidate feature dataset is persisted as final.",
        "",
        "## E. Variable inventory",
        "",
        f"All {summary['column_count_original']} original variables are accounted for in `phase4_discovery_ready_dataset_results.json`. Family counts: " + ", ".join(f"{k}: {v}" for k, v in group_counts.items()) + ".",
        "",
        "## F. Candidate discovery variables",
        "",
        "- Candidate clinical baseline: `anchor_age`, `sex_male`, `diabetes`, `hypertension`, `ckd`, `prior_mi` (provisional, admission-consistency checked, provenance/timing still needs verification).",
        "- Candidate ECG representation: 95 ECG features and all 64 `z_ecg` dimensions, quarantined until index ECG and time zero are established.",
        "- Treatment variables remain separate. Outcomes, temporal fields, and identifiers are excluded from the covariate matrix.",
        "",
        "Admission-level clinical candidate variables were checked for within-admission consistency; treatment flags are treated as admission-level metadata in line with Phase 2. Full missingness, prevalence, constant/near-constant, duplicated-column, range/outlier, correlation, split-shift, and value-domain diagnostics are in the JSON artifact. No feature was removed.",
        "",
        "## G. Preprocessing",
        "",
        "Phase 4 performed diagnostics only. No imputation, scaling, clipping, feature removal, or PCA was performed. Missing values are reported; exact duplicates and correlations are reported but retained. Documentation describes upstream winsorization, Yeo-Johnson transformation, and robust scaling for ECG features, but local scripts/fitted objects needed to verify train-only fit scope were not present.",
        "",
        "## H. Leakage audit",
        "",
        "Exclude `Label_Troponin`, `is_MI`, `index_mi_time`, and `time_diff_hours` from the discovery covariate matrix. The actual master schema contains no troponin-named feature; project rule remains NEVER USE TROPONIN AS A FEATURE. Keep post-discharge and acute treatment flags separate. ECG and latent representations may encode MI morphology but cannot be called leakage-free baseline covariates until the index ECG is resolved.",
        "",
        "## I. Split integrity",
        "",
        f"Exact pairwise split intersections: `study_id` pass={split['id_results']['study_id']['integrity_pass']}, `hadm_id` pass={split['id_results']['hadm_id']['integrity_pass']}, `SubjectID` pass={split['id_results']['SubjectID']['integrity_pass']}. No split recreation was performed. Train-only preprocessing fit scope is {split['preprocessing_fit_leakage']}",
        "",
        "## J. ECG representation",
        "",
        "Retain both raw handcrafted ECG variables and `z_ecg` only as separate candidate representations, not a combined confirmed baseline matrix. Correlations, duplication, ranges, missingness, constant/near-constant columns, and split shifts are quantified in the JSON. No feature is removed solely for correlation. Predictive performance is not evidence of a causal role.",
        "",
        "## K. Discovery readiness",
        "",
        "Ready: split-preserving admission metadata architecture, variable inventories, and descriptive candidate diagnostics. BLOCKED: causal discovery covariate matrix; the final index ECG, treatment-specific time zero, causal outcome specification, and upstream preprocessing leakage checks remain unresolved.",
        "",
        "## L. Phase 5 handoff",
        "",
        decision["phase5_handoff"],
        "",
        "## Phase 4 Decision Record",
        "",
        f"1. Discovery-ready observational unit: {decision['discovery_ready_observational_unit']}",
        f"2. Admission representation: {decision['admission_representation']}",
        f"3. Candidate ECG-selection rules constructed: {', '.join(decision['candidate_ecg_selection_rules_constructed'])}",
        f"4. Preferred operational representation: {decision['preferred_operational_representation']}",
        f"5. Candidate clinical variables: {', '.join(decision['candidate_clinical_variables'])}",
        f"6. ECG variables retained: {decision['ecg_variables_retained']}",
        f"7. z_ecg handling: {decision['z_ecg_handling']}",
        f"8. Treatment variables: {decision['treatment_variables']}",
        f"9. Outcome variables excluded: {', '.join(decision['outcome_variables_excluded'])}",
        f"10. Leakage variables excluded: {', '.join(decision['leakage_variables_excluded'])}",
        f"11. Preprocessing performed: {decision['preprocessing_performed']}",
        f"12. Split integrity result: {decision['split_integrity_result']}",
        f"13. Remaining unresolved issues: {'; '.join(decision['remaining_unresolved_issues'])}",
        f"14. Blockers: {'; '.join(decision['blockers'])}",
        f"15. Phase 5 handoff: {decision['phase5_handoff']}",
        f"16. Phase 7 readiness: {decision['phase7_readiness']}",
        "",
        "No Phase 5 or Phase 7 analysis was performed.",
        "",
    ]
    return "\n".join(lines)


def notebook_document() -> dict[str, Any]:
    code = [
        "from pathlib import Path\nimport json\nimport pandas as pd\nfrom IPython.display import display\n\nROOT = Path(r'c:/Users/anura/OneDrive/Desktop/capstone2')\n",
        "from phase4_discovery_ready_dataset import read_splits, make_results, report_markdown, JSON_PATH, REPORT_PATH\n\ndf, split_rows, split_frames = read_splits()\nresults = make_results(df, split_rows, split_frames)\nJSON_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding='utf-8')\nREPORT_PATH.write_text(report_markdown(results), encoding='utf-8')\nprint(results['input_summary'])\n",
        "inventory = pd.DataFrame(results['complete_variable_inventory'])\ndisplay(inventory)\n",
        "print(json.dumps(results['split_integrity'], indent=2))\nprint(json.dumps(results['candidate_rule_comparison'], indent=2))\n",
        "display(pd.DataFrame(results['feature_diagnostics']['raw_ecg']['per_variable']).T)\ndisplay(pd.DataFrame(results['feature_diagnostics']['z_ecg']['per_variable']).T)\nprint('Exact duplicates:', results['feature_diagnostics']['exact_duplicate_features'])\nprint(json.dumps(results['feature_diagnostics']['correlation_redundancy'], indent=2))\n",
        "print(json.dumps(results['discovery_layers'], indent=2))\nprint(json.dumps(results['decision_record'], indent=2, ensure_ascii=False))\n",
    ]
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 4 — Discovery-Ready Dataset Construction\n\n",
                "Phases 0–3 remain frozen. This notebook constructs and documents separate provisional data layers for later causal discovery. It does not select a final treatment, time zero, index ECG, adjustment set, or causal graph, and it does not run Phase 5 or Phase 7.\n",
            ],
        }
    ]
    titles = [
        "## Load verified split files",
        "## Build diagnostics and output report",
        "## Complete variable inventory",
        "## Split integrity and candidate ECG rules",
        "## Feature properties and redundancy",
        "## Layered discovery representation and decision record",
    ]
    for index, source in enumerate(code):
        if index > 0:
            cells.append({"cell_type": "markdown", "metadata": {}, "source": [titles[index]]})
        cells.append(
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": source.splitlines(keepends=True),
            }
        )
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    df, split_rows, split_frames = read_splits()
    results = make_results(df, split_rows, split_frames)
    JSON_PATH.write_text(
        json.dumps(json_safe(results), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    NOTEBOOK_PATH.write_text(
        json.dumps(notebook_document(), indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(report_markdown(results), encoding="utf-8")
    print(
        json.dumps(
            {
                "input_summary": results["input_summary"],
                "split_integrity_pass": results["split_integrity"]["all_identifier_overlap_checks_pass"],
                "candidate_rules": results["candidate_rule_comparison"],
                "feature_counts": {
                    "raw_ecg": len(feature_columns(df)[0]),
                    "z_ecg": len(feature_columns(df)[1]),
                },
                "outputs": [str(JSON_PATH), str(NOTEBOOK_PATH), str(REPORT_PATH)],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
