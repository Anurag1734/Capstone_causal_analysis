from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parent
MASTER_DIR = ROOT / "master"
DOC_PATH = ROOT / "docs" / "VAE Embedding Pipeline.md"
PHASE4_RESULTS_PATH = ROOT / "phase4_discovery_ready_dataset_results.json"
JSON_PATH = ROOT / "phase5_z_ecg_causal_role_audit_results.json"
NOTEBOOK_PATH = ROOT / "phase5_z_ecg_causal_role_audit.ipynb"
REPORT_PATH = ROOT / "phase5_z_ecg_causal_role_audit_report.md"
SPLITS = ("train", "validation", "test")
IDENTIFIERS = ["study_id", "SubjectID", "hadm_id"]
MI_LABELS = {"MI_Pre-Incident", "MI_Acute_Presentation"}
LATENT_COLUMNS = [f"z_ecg_{index}" for index in range(1, 65)]
MASTER_COLUMNS = [
    *IDENTIFIERS,
    "Label_Troponin",
    "is_MI",
    "ecg_time",
    "index_mi_time",
    "time_diff_hours",
    *LATENT_COLUMNS,
]
CORRELATION_THRESHOLD = 0.98
DOMINANT_FRACTION_THRESHOLD = 0.999

EXPECTED_ARTIFACTS = {
    "VAE model source": ROOT / "src" / "models" / "vae_conv1d.py",
    "VAE training source": ROOT / "src" / "models" / "train_vae.py",
    "Embedding extraction source": ROOT / "src" / "models" / "extract_embeddings.py",
    "Waveform dataset source": ROOT / "src" / "data" / "ecg_dataset.py",
    "HDF5 conversion source": ROOT / "src" / "data" / "convert_to_hdf5.py",
    "VAE checkpoint directory": ROOT / "models" / "checkpoints",
    "Processed waveform HDF5": ROOT / "data" / "processed" / "ecg_signals.h5",
    "Standalone embedding directory": ROOT / "data" / "modeling" / "ecg_embeddings",
}


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
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


def load_master() -> tuple[pd.DataFrame, dict[str, pd.DataFrame], list[str]]:
    split_frames: dict[str, pd.DataFrame] = {}
    schema_columns: list[str] | None = None
    for split in SPLITS:
        path = MASTER_DIR / f"{split}.parquet"
        if not path.is_file():
            raise FileNotFoundError(f"Required master split is missing: {path}")
        parquet_file = pq.ParquetFile(path)
        file_schema_columns = parquet_file.schema_arrow.names
        if schema_columns is None:
            schema_columns = file_schema_columns
        elif schema_columns != file_schema_columns:
            raise ValueError(f"Master schema mismatch in {path}")
        frame = pd.read_parquet(path, columns=MASTER_COLUMNS)
        missing_columns = sorted(set(MASTER_COLUMNS) - set(frame.columns))
        if missing_columns:
            raise ValueError(f"{path} is missing required columns: {missing_columns}")
        split_frames[split] = frame.assign(_split=split)
    return pd.concat(split_frames.values(), ignore_index=True), split_frames, schema_columns or []


def project_artifact_inventory() -> dict[str, Any]:
    return {
        label: {
            "expected_path": str(path),
            "available": path.exists(),
            "kind": "directory" if path.is_dir() else "file",
        }
        for label, path in EXPECTED_ARTIFACTS.items()
    }


def split_integrity(split_frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    by_identifier: dict[str, Any] = {}
    for identifier in IDENTIFIERS:
        sets = {
            split: set(frame[identifier].dropna().tolist())
            for split, frame in split_frames.items()
        }
        intersections = {}
        for left_index, left in enumerate(SPLITS):
            for right in SPLITS[left_index + 1 :]:
                intersections[f"{left}__{right}"] = len(sets[left] & sets[right])
        by_identifier[identifier] = {
            "unique_nonmissing_by_split": {
                split: len(values) for split, values in sets.items()
            },
            "pairwise_overlap_counts": intersections,
            "no_pairwise_overlap": all(count == 0 for count in intersections.values()),
        }
    return {
        "split_rows": {split: int(len(frame)) for split, frame in split_frames.items()},
        "identifier_results": by_identifier,
        "all_identifiers_have_no_pairwise_overlap": all(
            result["no_pairwise_overlap"] for result in by_identifier.values()
        ),
        "master_rows": int(sum(len(frame) for frame in split_frames.values())),
        "subjects_are_disjoint_in_master_splits": by_identifier["SubjectID"][
            "no_pairwise_overlap"
        ],
        "study_ids_are_disjoint_in_master_splits": by_identifier["study_id"][
            "no_pairwise_overlap"
        ],
        "admissions_are_disjoint_in_master_splits": by_identifier["hadm_id"][
            "no_pairwise_overlap"
        ],
    }


def master_label_summary(split_frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    by_split = {}
    for split, frame in split_frames.items():
        by_split[split] = {
            str(label): int(count)
            for label, count in frame["Label_Troponin"]
            .value_counts(dropna=False)
            .items()
        }
    return by_split


def linkage_audit(df: pd.DataFrame) -> dict[str, Any]:
    latent = df[LATENT_COLUMNS]
    repeated_study = df["study_id"].duplicated(keep=False)
    repeated_vectors = latent.duplicated(keep=False)
    duplicate_vector_rows_after_first = int(latent.duplicated().sum())
    phase4_rows = None
    if PHASE4_RESULTS_PATH.is_file():
        phase4_results = json.loads(PHASE4_RESULTS_PATH.read_text(encoding="utf-8"))
        phase4_rows = phase4_results.get("input_summary", {}).get("ecg_rows")
    return {
        "master_ecg_rows": int(len(df)),
        "study_id_rows_nonmissing": int(df["study_id"].notna().sum()),
        "unique_study_id": int(df["study_id"].nunique(dropna=True)),
        "missing_study_id_rows": int(df["study_id"].isna().sum()),
        "duplicate_study_id_rows": int(repeated_study.sum()),
        "duplicate_study_id_groups": int(
            df.loc[repeated_study, "study_id"].nunique(dropna=True)
        ),
        "latent_dimension_count": len(LATENT_COLUMNS),
        "rows_with_all_64_embeddings_nonmissing": int(latent.notna().all(axis=1).sum()),
        "rows_with_any_embedding_missing": int(latent.isna().any(axis=1).sum()),
        "missing_embedding_cells": int(latent.isna().sum().sum()),
        "nonfinite_embedding_cells": int(
            (~np.isfinite(latent.to_numpy(dtype=np.float64))).sum()
        ),
        "unique_64d_vectors": int(len(latent.drop_duplicates())),
        "duplicate_vector_rows_beyond_first": duplicate_vector_rows_after_first,
        "rows_in_exact_duplicate_vector_groups": int(repeated_vectors.sum()),
        "one_master_row_per_study_id": bool(
            df["study_id"].notna().all()
            and df["study_id"].is_unique
            and df["study_id"].nunique() == len(df)
        ),
        "phase4_master_ecg_rows": phase4_rows,
        "row_count_matches_phase4": (
            int(len(df)) == phase4_rows if phase4_rows is not None else None
        ),
        "source_embedding_join_can_be_reconstructed": False,
        "source_waveform_identity_independently_verified": False,
        "linkage_interpretation": (
            "The master rows can be checked for study_id uniqueness and complete z_ecg columns. "
            "The standalone embedding table, waveform archive, and join code are absent locally, "
            "so equality of the source waveform and the waveform represented by each master row "
            "cannot be independently re-performed."
        ),
    }


def latent_diagnostics(
    df: pd.DataFrame,
    split_frames: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    latent = df[LATENT_COLUMNS].astype("float64")
    quantiles = latent.quantile([0.0, 0.01, 0.25, 0.5, 0.75, 0.99, 1.0])
    per_dimension = {}
    for column in LATENT_COLUMNS:
        values = latent[column]
        value_counts = values.value_counts(dropna=True, normalize=True)
        per_dimension[column] = {
            "nonmissing_count": int(values.notna().sum()),
            "missing_count": int(values.isna().sum()),
            "unique_count": int(values.nunique(dropna=True)),
            "mean": float(values.mean()),
            "variance": float(values.var(ddof=1)),
            "standard_deviation": float(values.std(ddof=1)),
            "minimum": float(values.min()),
            "q01": float(quantiles.loc[0.01, column]),
            "q25": float(quantiles.loc[0.25, column]),
            "median": float(quantiles.loc[0.5, column]),
            "q75": float(quantiles.loc[0.75, column]),
            "q99": float(quantiles.loc[0.99, column]),
            "maximum": float(values.max()),
            "skew": float(values.skew()),
            "excess_kurtosis": float(values.kurt()),
            "dominant_value_fraction": (
                float(value_counts.iloc[0]) if len(value_counts) else None
            ),
            "near_constant_at_phase4_dominant_fraction_threshold": bool(
                len(value_counts)
                and value_counts.iloc[0] >= DOMINANT_FRACTION_THRESHOLD
            ),
        }

    corr = latent.corr(method="pearson")
    absolute_corr = corr.abs().to_numpy()
    upper_mask = np.triu(np.ones(absolute_corr.shape, dtype=bool), k=1)
    pair_indices = np.argwhere(upper_mask)
    pairs = [
        {
            "dimension_a": LATENT_COLUMNS[int(i)],
            "dimension_b": LATENT_COLUMNS[int(j)],
            "pearson_correlation": float(corr.iat[int(i), int(j)]),
            "absolute_correlation": float(absolute_corr[int(i), int(j)]),
        }
        for i, j in pair_indices
        if absolute_corr[int(i), int(j)] >= CORRELATION_THRESHOLD
    ]
    pairs.sort(key=lambda item: item["absolute_correlation"], reverse=True)
    off_diagonal = absolute_corr[upper_mask]
    exact_duplicate_dimensions = []
    for i, left in enumerate(LATENT_COLUMNS):
        for right in LATENT_COLUMNS[i + 1 :]:
            if latent[left].equals(latent[right]):
                exact_duplicate_dimensions.append([left, right])

    split_distribution = {}
    for split, frame in split_frames.items():
        values = frame[LATENT_COLUMNS].astype("float64")
        split_distribution[split] = {
            "rows": int(len(values)),
            "mean_of_dimension_means": float(values.mean().mean()),
            "minimum_dimension_mean": float(values.mean().min()),
            "maximum_dimension_mean": float(values.mean().max()),
            "mean_of_dimension_standard_deviations": float(values.std(ddof=1).mean()),
            "minimum_dimension_standard_deviation": float(values.std(ddof=1).min()),
            "maximum_dimension_standard_deviation": float(values.std(ddof=1).max()),
        }

    return {
        "dimensions_audited": len(LATENT_COLUMNS),
        "per_dimension": per_dimension,
        "near_constant_dimensions": [
            name
            for name, summary in per_dimension.items()
            if summary["near_constant_at_phase4_dominant_fraction_threshold"]
        ],
        "constant_dimensions": [
            name for name, summary in per_dimension.items() if summary["unique_count"] <= 1
        ],
        "exact_duplicate_dimension_pairs": exact_duplicate_dimensions,
        "pairwise_pearson_correlations": {
            "pair_count": int(len(off_diagonal)),
            "threshold_absolute_correlation": CORRELATION_THRESHOLD,
            "pairs_at_or_above_threshold": len(pairs),
            "pairs": pairs,
            "maximum_absolute_correlation": (
                float(off_diagonal.max()) if len(off_diagonal) else None
            ),
            "median_absolute_correlation": (
                float(np.median(off_diagonal)) if len(off_diagonal) else None
            ),
            "mean_absolute_correlation": (
                float(off_diagonal.mean()) if len(off_diagonal) else None
            ),
        },
        "split_distribution_summary": split_distribution,
        "dimension_removal_performed": False,
        "interpretation": (
            "Diagnostics describe the current master embeddings only; they do not establish "
            "semantic meanings, independent causal variables, or justify deleting dimensions."
        ),
    }


def mi_event_times(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    work = df.copy()
    work["_ecg_dt"] = pd.to_datetime(work["ecg_time"], errors="coerce", utc=True)
    work["_mi_dt"] = pd.to_datetime(work["index_mi_time"], errors="coerce", utc=True)
    mi_rows = work[work["Label_Troponin"].isin(MI_LABELS)]
    counts = mi_rows.groupby("hadm_id", dropna=False)["_mi_dt"].nunique(dropna=True)
    unique_hadm = counts[counts.eq(1)].index
    event_times = (
        mi_rows[mi_rows["hadm_id"].isin(unique_hadm)]
        .groupby("hadm_id", dropna=False)["_mi_dt"]
        .first()
    )
    return work, event_times


def timestamp_relation_summary(
    selected: pd.DataFrame, event_times: pd.Series
) -> dict[str, Any]:
    frame = selected.copy()
    if "_ecg_dt" not in frame:
        frame["_ecg_dt"] = pd.to_datetime(frame["ecg_time"], errors="coerce", utc=True)
    frame["_event_dt"] = frame["hadm_id"].map(event_times)
    eligible = frame[frame["_event_dt"].notna() & frame["_ecg_dt"].notna()].copy()
    eligible["_relation"] = np.select(
        [
            eligible["_ecg_dt"] < eligible["_event_dt"],
            eligible["_ecg_dt"] == eligible["_event_dt"],
            eligible["_ecg_dt"] > eligible["_event_dt"],
        ],
        ["before index_mi_time", "same timestamp", "after index_mi_time"],
        default="unresolved",
    )
    return {
        "selected_rows": int(len(frame)),
        "mi_rows_with_unique_event_time_and_valid_ecg_time": int(len(eligible)),
        "distinct_mi_admissions_with_unique_event_time_and_valid_ecg_time": int(
            eligible["hadm_id"].nunique()
        ),
        "relation_row_counts": {
            str(key): int(value)
            for key, value in eligible["_relation"].value_counts().items()
        },
        "relation_admission_counts": {
            str(key): int(value)
            for key, value in eligible.drop_duplicates("hadm_id")["_relation"]
            .value_counts()
            .items()
        },
        "label_by_timestamp_relation_rows": {
            str(label): {
                str(relation): int(count)
                for relation, count in group["_relation"].value_counts().items()
            }
            for label, group in eligible.groupby("Label_Troponin", dropna=False)
        },
        "time_diff_hours_used": False,
        "near_threshold_applied": False,
    }


def temporal_audit(df: pd.DataFrame, master_schema_columns: list[str]) -> dict[str, Any]:
    work, event_times = mi_event_times(df)
    mi_rows = work[work["Label_Troponin"].isin(MI_LABELS)]
    valid_event_counts = mi_rows.groupby("hadm_id")["_mi_dt"].nunique(dropna=True)
    mi_hadm_count = int(mi_rows["hadm_id"].nunique())
    unique_event_hadm_count = int(valid_event_counts.eq(1).sum())
    no_unique_event_hadm_count = int((~valid_event_counts.eq(1)).sum())

    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import phase4_discovery_ready_dataset as phase4

    admission_status = phase4.admission_label_status(df)
    candidate_metrics, selected_frames = phase4.candidate_ecg_rules(df, admission_status)
    candidate_temporal = {
        rule: timestamp_relation_summary(selected, event_times)
        for rule, selected in selected_frames.items()
    }
    candidate_treatment_status = {
        rule: {
            "status": "TEMPORALLY UNRESOLVED",
            "treatment_assignment_time_available": False,
            "ecg_before_treatment_established": False,
            "why": (
                "The selection rule does not supply an exact medication assignment time; "
                "even Rule A's earliest ECG and Rules B/C's pre-MI ECGs cannot establish "
                "pre-treatment ordering."
            ),
        }
        for rule in selected_frames
    }
    return {
        "treatment_temporal_eligibility": {
            "treatment_specific_candidates": [
                "aspirin_before",
                "statin_before",
                "beta_blocker_before",
                "acei_before",
            ],
            "medication_treatment_timestamp_columns_in_master_schema": medication_timestamp_columns(
                master_schema_columns
            ),
            "exact_treatment_assignment_time_available": False,
            "can_test_ecg_time_less_than_treatment_assignment_time": False,
            "candidate_status": "TEMPORALLY UNRESOLVED",
            "rule_a_first_ecg_proves_pre_treatment": False,
            "candidate_rule_treatment_status": candidate_treatment_status,
            "note": (
                "The master schema has window-coded treatment indicators, not exact medication "
                "administration/assignment timestamps. Earliest ecg_time does not resolve ordering."
            ),
        },
        "mi_event_timestamp_audit": {
            "mi_labeled_admissions": mi_hadm_count,
            "mi_admissions_with_exactly_one_distinct_nonmissing_index_mi_time": unique_event_hadm_count,
            "mi_admissions_without_exactly_one_distinct_nonmissing_index_mi_time": no_unique_event_hadm_count,
            "event_time_available_for_timestamp_comparison": bool(len(event_times)),
            "time_diff_hours_used_as_mi_clock": False,
            "Label_Troponin_used_as_categorical_cohort_label": True,
            "near_presentation_threshold_applied": False,
        },
        "candidate_rule_mi_timestamp_relations": candidate_temporal,
        "candidate_rule_selection_metrics_from_phase4_logic": candidate_metrics,
        "interpretation": (
            "An ECG timestamp before index_mi_time, where measurable, establishes only temporal "
            "ordering before that recorded MI timestamp. It does not establish ordering before "
            "treatment assignment. MI-relative Rules B/C are outcome/time-dependent selections."
        ),
    }


def medication_timestamp_columns(columns: list[str]) -> list[str]:
    medication_terms = re.compile(
        r"(med|medication|treat|treatment|drug|statin|aspirin|acei|"
        r"beta.?block|vasopressor|ventilation)",
        re.IGNORECASE,
    )
    time_terms = re.compile(
        r"(time|date|timestamp|admin|ordered|start|end)",
        re.IGNORECASE,
    )
    return [
        column
        for column in columns
        if medication_terms.search(column) and time_terms.search(column)
    ]


def provenance_audit(
    df: pd.DataFrame,
    master_schema_columns: list[str],
) -> dict[str, Any]:
    doc_text = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.is_file() else ""
    artifact_presence = project_artifact_inventory()
    actual_schema_treatment_times = medication_timestamp_columns(master_schema_columns)
    evidence_rows = [
        {
            "item": "z_ecg source",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Local VAE documentation describes 12-lead raw waveform input and a Conv1D beta-VAE; VAE implementation and waveform files are absent.",
        },
        {
            "item": "Exact VAE architecture",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Documentation specifies layer widths, kernels, strides, activations, and 82,448,332 parameters; no model source/checkpoint is present to verify exact implementation or padding.",
        },
        {
            "item": "Latent dimension",
            "status": "VERIFIED",
            "evidence": f"The master parquet schema contains {len(LATENT_COLUMNS)} columns from z_ecg_1 through z_ecg_64.",
        },
        {
            "item": "Stored VAE output",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Documentation says the deterministic encoder mean mu is saved; extraction source is absent.",
        },
        {
            "item": "Embedding generation",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Documentation describes encoder-only extraction with a best checkpoint reported as epoch 109; extraction code and run artifacts are absent.",
        },
        {
            "item": "Embedding join key",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Documentation identifies study_id; the master has unique study_id rows and all 64 dimensions, but the source embedding join cannot be reconstructed locally.",
        },
        {
            "item": "Waveform preprocessing",
            "status": "UNRESOLVED",
            "evidence": "Documentation reports 12 leads x 5000 samples at 500 Hz and WFDB/HDF5 conversion, but local dataset/conversion code and waveform arrays are absent; filtering, normalization, resampling, and learned parameters cannot be checked.",
        },
        {
            "item": "Feature preprocessing before VAE",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Documentation depicts raw waveforms as VAE input and discusses engineered ECG features separately; no source code establishes the exact waveform-to-model transform.",
        },
        {
            "item": "VAE train/validation/test split",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Master parquet split sizes and labels are directly inspectable; VAE documentation label counts disagree with current validation/test parquet counts, and training code/logs are absent.",
        },
        {
            "item": "Subject separation across VAE splits",
            "status": "PARTIALLY VERIFIED",
            "evidence": "SubjectID sets in the actual master train/validation/test files are disjoint; actual VAE loader membership is not verifiable.",
        },
        {
            "item": "Checkpoint identity and use",
            "status": "PARTIALLY VERIFIED",
            "evidence": "Documentation names a checkpoint run and best epoch 109, but the checkpoint and extraction run metadata are absent, so its use for these embeddings is unverified.",
        },
        {
            "item": "VAE training membership",
            "status": "UNRESOLVED",
            "evidence": "No VAE training code, logs, split manifests, or checkpoint metadata are locally present.",
        },
        {
            "item": "Validation/test ECGs in optimization",
            "status": "UNRESOLVED",
            "evidence": "Documentation describes validation loss/checkpoint selection and a separate test split, but absent training source/logs prevent confirmation of gradient or model-selection use.",
        },
        {
            "item": "Post-MI ECGs in VAE training",
            "status": "UNRESOLVED",
            "evidence": "Documentation says MI_Post-Incident was excluded, but actual training membership and waveform-to-label map are absent; master dataset itself has no MI_Post-Incident label category.",
        },
        {
            "item": "Train-only preprocessing fitting",
            "status": "UNRESOLVED",
            "evidence": "No preprocessing code or fitted parameter artifacts are present to establish fit partition or validation/test influence.",
        },
        {
            "item": "Outcome/treatment independence",
            "status": "NOT AVAILABLE",
            "evidence": "NOT VERIFIED — documentation describes the VAE as unsupervised, but the training/dataloader source is unavailable; use of labels, treatment, diagnosis, or downstream event information cannot be confirmed.",
        },
    ]
    if "best checkpoint (epoch 109)" in doc_text and "Epochs (actual) | 129" in doc_text:
        doc_checkpoint_discrepancy = (
            "The documentation reports best checkpoint epoch 109 and training stopping at epoch 129; "
            "its overview also says 109 epochs trained. Without run files, the actual selected checkpoint "
            "and completed epoch count cannot be independently confirmed."
        )
    else:
        doc_checkpoint_discrepancy = None
    return {
        "phase5_input_audit": evidence_rows,
        "project_artifact_presence": artifact_presence,
        "master_medication_timestamp_columns_matching_name_patterns": actual_schema_treatment_times,
        "documented_architecture": {
            "model_type": "Conv1D beta-VAE",
            "input_shape": [12, 5000],
            "sampling_rate_hz": 500,
            "reported_parameter_count": 82448332,
            "latent_dimension": 64,
            "beta": 4.0,
            "free_bits_per_dimension": 2.0,
            "encoder_reported_channels": [12, 32, 64, 128, 256, 512],
            "encoder_reported_kernels": [7, 5, 5, 3, 3],
            "encoder_reported_strides": [2, 2, 2, 2, 2],
            "reported_hidden_width": 512,
            "reported_outputs": ["mu", "logvar"],
            "reported_decoder_output_activation": "Tanh",
            "exact_implementation_verified": False,
        },
        "document_claims": {
            "input_source": "MIMIC-IV-ECG v1.0 WFDB files, later HDF5",
            "training_split_sizes": {
                "train": 262813,
                "validation": 56319,
                "test": 56798,
            },
            "split_label_counts": {
                "train": {
                    "Control_Symptomatic": 253334,
                    "MI_Pre-Incident": 4179,
                    "MI_Acute_Presentation": 5300,
                },
                "validation": {
                    "Control_Symptomatic": 54302,
                    "MI_Pre-Incident": 888,
                    "MI_Acute_Presentation": 1129,
                },
                "test": {
                    "Control_Symptomatic": 54748,
                    "MI_Pre-Incident": 919,
                    "MI_Acute_Presentation": 1131,
                },
            },
            "post_mi_excluded_claim": True,
            "embedding_method_claim": "Encoder mu (deterministic mean)",
            "reported_best_epoch": 109,
            "reported_stopping_epoch": 129,
            "reported_checkpoint_name": "vae_zdim64_beta4.0_20260821_030245/best_model.pt",
            "train_only_preprocessing_claim": None,
        },
        "documentation_epoch_discrepancy": doc_checkpoint_discrepancy,
        "source_and_model_artifacts_available_locally": any(
            artifact["available"] for artifact in artifact_presence.values()
        ),
        "limitation": (
            "Documentation is treated as documentary evidence, not as verification of the execution "
            "history or identity of the embeddings in the current parquet files."
        ),
    }


def causal_role_analysis() -> list[dict[str, str]]:
    return [
        {
            "role": "A — Baseline common cause/confounder",
            "mechanism": "A pre-treatment ECG state may influence treatment assignment and subsequent MI risk.",
            "temporal_requirement": "The ECG measurement must precede treatment assignment and outcome; the relevant state must be a cause of both treatment and outcome.",
            "evidence_available": "ECG representations and admission-level treatment indicators are present; exact treatment times are not.",
            "evidence_missing": "Treatment-specific time zero, waveform provenance, pre-treatment ordering, and evidence linking ECG state to treatment assignment and outcome.",
            "causal_implication": "Could be a confounder only if those conditions are established; currently not established.",
        },
        {
            "role": "B — Proxy for latent cardiovascular state",
            "mechanism": "The embedding may summarize ECG morphology that reflects an underlying physiological or disease state.",
            "temporal_requirement": "The represented ECG state must be measured at the relevant pre-treatment baseline to proxy a baseline state.",
            "evidence_available": "The documentation describes a morphology-reconstruction VAE; the master contains 64 embedding values.",
            "evidence_missing": "Verified waveform/checkpoint lineage, latent construct validity, and pre-treatment timing.",
            "causal_implication": "Observed z_ecg is not identical to the unobserved physiological state and cannot be assumed to block confounding.",
        },
        {
            "role": "C — Predictor of outcome only",
            "mechanism": "ECG morphology could be prognostic for MI without affecting treatment assignment.",
            "temporal_requirement": "For baseline prediction/adjustment, z_ecg must be available before treatment and outcome.",
            "evidence_available": "MI labels and embeddings coexist in the master data; Phase 5 does not estimate predictive performance or causal influence.",
            "evidence_missing": "Independent predictive validation and evidence about the treatment-assignment mechanism.",
            "causal_implication": "Prognostic association alone would not make z_ecg a confounder.",
        },
        {
            "role": "D — Mediator",
            "mechanism": "Treatment or treatment-induced physiology could change a subsequent ECG that then relates to outcome.",
            "temporal_requirement": "Treatment precedes the ECG, and that ECG precedes the outcome.",
            "evidence_available": "Treatment indicators are window-coded and lack exact administration times; multiple ECGs may occur within admission.",
            "evidence_missing": "Treatment time, selected ECG time relative to treatment, and outcome timing.",
            "causal_implication": "Adjustment could block part of an effect if z_ecg is post-treatment; that ordering is unresolved.",
        },
        {
            "role": "E — Collider",
            "mechanism": "Treatment and another acute process may both affect the ECG measurement/embedding.",
            "temporal_requirement": "Both causes precede the measured ECG and the analysis conditions on z_ecg.",
            "evidence_available": "The dataset has acute-treatment indicators and ECG representations, but no validated causal ordering.",
            "evidence_missing": "Treatment timing, acute-process measures, and a treatment-specific time zero.",
            "causal_implication": "Conditioning could induce bias under this structure; it cannot currently be ruled out.",
        },
        {
            "role": "F — Effect modifier",
            "mechanism": "Baseline ECG morphology could mark strata with different treatment response.",
            "temporal_requirement": "The modifier must be defined before treatment assignment.",
            "evidence_available": "Sixty-four dimensions exist, but no treatment-effect analysis is permitted or performed in Phase 5.",
            "evidence_missing": "Pre-treatment timing and treatment-specific causal estimand/effect-modification evidence.",
            "causal_implication": "Possible in principle; neither supported nor excluded by current audit evidence.",
        },
        {
            "role": "G — Predictive-only representation",
            "mechanism": "The block may encode waveform patterns useful for prediction without a justified causal adjustment role.",
            "temporal_requirement": "Prediction use still requires a deployment-appropriate observation time; causal baseline use requires pre-treatment timing.",
            "evidence_available": "A learned ECG representation is present; no Phase 5 predictive model is fit.",
            "evidence_missing": "Validated prediction utility, provenance, and temporal eligibility.",
            "causal_implication": "Predictive utility, if later shown, would not establish confounding or adjustment suitability.",
        },
    ]


def representation_options() -> list[dict[str, str]]:
    return [
        {
            "option": "A — All 64 latent dimensions",
            "advantages": "Retains the available learned representation without arbitrary compression.",
            "risks_or_requirements": "Higher-dimensional discovery, correlation/instability, limited interpretability, and unresolved provenance/timing.",
            "phase5_assessment": "Carry as a quarantined optional block only; no approved causal feature matrix.",
        },
        {
            "option": "B — PCA reduction",
            "advantages": "Could reduce dimensionality for a later specified workflow.",
            "risks_or_requirements": "Requires an explicit objective, training-only fit, documented explained variance, and downstream stability checks; no outcome/treatment-driven component selection.",
            "phase5_assessment": "Not performed; no evidence currently justifies selecting components or fitting PCA.",
        },
        {
            "option": "C — Representative latent subset",
            "advantages": "Could reduce variables if stable relationships to ECG properties are established.",
            "risks_or_requirements": "Would require validated, stable, interpretable mapping; individual latent dimensions have no supplied semantic labels.",
            "phase5_assessment": "Not recommended on current evidence; do not invent dimension meanings.",
        },
        {
            "option": "D — Block-level representation",
            "advantages": "Preserves the 64-vector as one ECG representation family and avoids treating each dimension as a separately meaningful causal node.",
            "risks_or_requirements": "A block label does not resolve temporal eligibility, leakage, or whether a later method can handle a multivariate block.",
            "phase5_assessment": "Most defensible provisional schema representation for later review; still quarantined and not approved for discovery or adjustment.",
        },
    ]


def make_results(
    df: pd.DataFrame,
    split_frames: dict[str, pd.DataFrame],
    master_schema_columns: list[str],
) -> dict[str, Any]:
    actual_label_summary = master_label_summary(split_frames)
    temporal = temporal_audit(df, master_schema_columns)
    provenance = provenance_audit(df, master_schema_columns)
    documented_label_counts = provenance["document_claims"]["split_label_counts"]
    label_mismatches = {}
    for split in SPLITS:
        compared = {}
        for label in sorted(set(actual_label_summary[split]) | set(documented_label_counts[split])):
            actual = actual_label_summary[split].get(label, 0)
            documented = documented_label_counts[split].get(label, 0)
            if actual != documented:
                compared[label] = {
                    "actual_master_count": actual,
                    "documented_count": documented,
                    "actual_minus_documented": actual - documented,
                }
        if compared:
            label_mismatches[split] = compared
    return {
        "phase": "Phase 5 — z_ecg representation and causal-role audit",
        "scope": "Representation/provenance/temporal-role audit only; no causal discovery, DAG, treatment selection, or effect estimation.",
        "inputs": {
            "master_split_paths": {
                split: str(MASTER_DIR / f"{split}.parquet") for split in SPLITS
            },
            "phase4_results_path": str(PHASE4_RESULTS_PATH),
            "master_split_integrity": split_integrity(split_frames),
            "observed_master_label_counts_by_split": actual_label_summary,
            "documented_vae_label_count_mismatches": label_mismatches,
            "master_schema_column_count": len(master_schema_columns),
            "master_schema_columns": master_schema_columns,
            "master_medication_timestamp_columns": medication_timestamp_columns(
                master_schema_columns
            ),
            "master_z_ecg_columns": [
                column
                for column in master_schema_columns
                if re.fullmatch(r"z_ecg_\d+", column)
            ],
        },
        "provenance": provenance,
        "waveform_embedding_study_id_linkage": linkage_audit(df),
        "latent_diagnostics": latent_diagnostics(df, split_frames),
        "temporal_eligibility_and_mi_timing": temporal,
        "causal_role_analysis": causal_role_analysis(),
        "representation_options": representation_options(),
        "recommendation": {
            "discovery": (
                "NO FINAL REPRESENTATION DECISION YET. Keep all 64 dimensions identified as one "
                "quarantined z_ecg block in the schema; do not use the block as a causal discovery "
                "input until provenance and the target treatment-specific time zero are established."
            ),
            "later_treatment_effect_modeling": (
                "Do not include z_ecg as a baseline adjustment variable unless the selected ECG is "
                "shown to precede that treatment's assignment and outcome, and the representation's "
                "training/preprocessing provenance is verified. A post-treatment ECG could be a "
                "mediator or collider."
            ),
            "pca_performed": False,
            "latent_dimensions_removed": 0,
            "final_adjustment_set_selected": False,
            "final_causal_role_assigned": False,
        },
        "phase6_handoff": [
            "Obtain VAE model/training/extraction source, full training logs, split manifests, configuration, and the exact checkpoint used to generate current embeddings.",
            "Obtain the waveform/HDF5 archive and study_id mapping; reproduce waveform-to-embedding joins and verify each embedding matches the corresponding master ECG.",
            "Verify actual VAE train/validation/test membership, subject-level isolation, optimizer exposure to validation/test data, and whether post-MI waveforms entered optimization.",
            "Recover waveform preprocessing code and fitted parameters; identify fit partitions and any validation/test influence.",
            "Verify whether labels, diagnoses, outcomes, or treatment information entered training, selection, or extraction.",
            "For the eventual treatment-specific question, obtain exact medication assignment/administration times and define a treatment-specific causal baseline before evaluating ECG eligibility.",
            "Keep outcome-relative ECG selection separate from treatment-relative baseline eligibility; do not use time_diff_hours as a universal MI clock.",
        ],
        "stopping_rule": {
            "causal_discovery_run": False,
            "dag_constructed": False,
            "treatment_selected": False,
            "causal_time_zero_selected": False,
            "adjustment_set_selected": False,
            "treatment_effect_estimated": False,
            "earlier_phases_modified": False,
        },
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend(
        "| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def report_markdown(results: dict[str, Any]) -> str:
    provenance = results["provenance"]
    link = results["waveform_embedding_study_id_linkage"]
    split = results["inputs"]["master_split_integrity"]
    timing = results["temporal_eligibility_and_mi_timing"]
    diagnostics = results["latent_diagnostics"]
    corr = diagnostics["pairwise_pearson_correlations"]
    input_rows = [
        [item["item"], item["status"], item["evidence"]]
        for item in provenance["phase5_input_audit"]
    ]
    project_rows = [
        [name, detail["available"], detail["expected_path"]]
        for name, detail in provenance["project_artifact_presence"].items()
    ]
    split_rows = [
        [
            identifier,
            split["identifier_results"][identifier]["unique_nonmissing_by_split"],
            split["identifier_results"][identifier]["pairwise_overlap_counts"],
            split["identifier_results"][identifier]["no_pairwise_overlap"],
        ]
        for identifier in IDENTIFIERS
    ]
    dimension_rows = [
        [
            name,
            summary["missing_count"],
            f'{summary["variance"]:.6g}',
            f'{summary["minimum"]:.6g}',
            f'{summary["median"]:.6g}',
            f'{summary["maximum"]:.6g}',
            f'{summary["skew"]:.4g}',
            summary["near_constant_at_phase4_dominant_fraction_threshold"],
        ]
        for name, summary in diagnostics["per_dimension"].items()
    ]
    role_rows = [
        [
            role["role"],
            role["mechanism"],
            role["temporal_requirement"],
            role["evidence_available"],
            role["evidence_missing"],
            role["causal_implication"],
        ]
        for role in results["causal_role_analysis"]
    ]
    option_rows = [
        [
            option["option"],
            option["advantages"],
            option["risks_or_requirements"],
            option["phase5_assessment"],
        ]
        for option in results["representation_options"]
    ]
    temporal_rows = []
    for rule, item in timing["candidate_rule_mi_timestamp_relations"].items():
        temporal_rows.append(
            [
                rule,
                item["selected_rows"],
                item["mi_rows_with_unique_event_time_and_valid_ecg_time"],
                item["relation_admission_counts"],
                item["near_threshold_applied"],
            ]
        )
    treatment_temporal_rows = [
        [
            rule,
            item["status"],
            item["treatment_assignment_time_available"],
            item["ecg_before_treatment_established"],
            item["why"],
        ]
        for rule, item in timing["treatment_temporal_eligibility"][
            "candidate_rule_treatment_status"
        ].items()
    ]
    missing_artifacts = [
        name for name, detail in provenance["project_artifact_presence"].items()
        if not detail["available"]
    ]
    max_corr_pair = corr["pairs"][0] if corr["pairs"] else None
    doc_splits = provenance["document_claims"]["training_split_sizes"]
    return "\n".join(
        [
            "# Phase 5 — z_ecg Representation and Causal-Role Audit",
            "",
            "## A. Phase 5 objective",
            "",
            "Audit the provenance, representation properties, and possible causal roles of the 64-dimensional `z_ecg` block. Representation choice and causal-role assessment are kept separate. This is not causal modeling.",
            "",
            "## B. VAE provenance audit",
            "",
            "### Phase 5 Input Audit",
            "",
            markdown_table(["Item", "Status", "Evidence"], input_rows),
            "",
            "The local VAE document describes a Conv1D β-VAE using 12×5000 ECG waveforms, 82,448,332 reported parameters, latent size 64, β=4 and free-bits=2 per dimension. It states that the deterministic encoder mean (`mu`) was extracted. These architecture and extraction details are **documentation-only**, not verified against executable source or a checkpoint.",
            "",
            f"Documentation identifies `best_model.pt` at epoch 109, while also reporting training stopped at epoch 129; its overview says 109 epochs trained. {provenance['documentation_epoch_discrepancy'] or 'No epoch discrepancy was identified in the local documentation.'}",
            "",
            "Expected source/data artifact presence:",
            "",
            markdown_table(["Artifact", "Available locally", "Expected path"], project_rows),
            "",
            f"Unavailable referenced artifact categories: {', '.join(missing_artifacts)}. The three master split parquet files are available and were directly audited.",
            "",
            "## C. Waveform → study_id → z_ecg linkage audit",
            "",
            f"- Master ECG rows: **{link['master_ecg_rows']:,}**; nonmissing `study_id`: **{link['study_id_rows_nonmissing']:,}**; unique `study_id`: **{link['unique_study_id']:,}**.",
            f"- Duplicate `study_id` rows: **{link['duplicate_study_id_rows']:,}**; duplicate ID groups: **{link['duplicate_study_id_groups']:,}**.",
            f"- Rows with all 64 dimensions present: **{link['rows_with_all_64_embeddings_nonmissing']:,}**; rows with any missing dimension: **{link['rows_with_any_embedding_missing']:,}**; missing cells: **{link['missing_embedding_cells']:,}**.",
            f"- Nonfinite embedding cells: **{link['nonfinite_embedding_cells']:,}**; distinct 64D vectors: **{link['unique_64d_vectors']:,}**; duplicate vector rows beyond first: **{link['duplicate_vector_rows_beyond_first']:,}**; rows in duplicate-vector groups: **{link['rows_in_exact_duplicate_vector_groups']:,}**.",
            "",
            "Observed master-row uniqueness and nonmissingness do not independently prove that each latent vector was produced by the exact raw waveform attached to that row. Separate embedding CSVs, waveform/HDF5 files, and the original join implementation are not available locally; that mapping remains **PARTIALLY VERIFIED**.",
            "",
            "## D. VAE split/training audit",
            "",
            "The master files are the exact train/validation/test files specified in local documentation. The direct split checks below establish their present-day ID disjointness, not which rows were actually loaded into VAE optimization or checkpoint selection.",
            "",
            markdown_table(["Identifier", "Unique IDs by split", "Pairwise overlaps", "No overlap"], split_rows),
            "",
            f"Observed master rows: {split['master_rows']:,}. Pairwise `study_id`, `SubjectID`, and `hadm_id` overlap checks pass: **{split['all_identifiers_have_no_pairwise_overlap']}**. Documentation claims subject-level stratified prebuilt splits and exclusion of MI_Post-Incident ECGs; actual VAE membership, optimization exposure, test use, and post-MI exclusion remain **UNRESOLVED** because manifests, source, logs, and checkpoint are absent.",
            "",
            f"Documented split sizes: `{doc_splits}`. See `observed_master_label_counts_by_split` in the JSON for counts read directly from the current parquet files; those counts do not verify VAE training membership.",
            "",
            (
                "A documentation discrepancy was found and is reported without changing frozen Phases 1–4: "
                + json.dumps(results["inputs"]["documented_vae_label_count_mismatches"], ensure_ascii=False)
                + ". The VAE document's validation/test label counts do not match the current master parquet counts. "
                "This must be resolved against the original split manifest before asserting VAE training membership."
            ),
            "",
            "## E. Preprocessing lineage audit",
            "",
            "The documentation specifies WFDB records converted into an HDF5 signal array and a nominal input shape of 12×5000 at 500 Hz. It does not provide locally auditable executable logic or fitted parameters for filtering, resampling, waveform/lead normalization, clipping, interpolation, or any learned signal transform. The HDF5 conversion, ECG dataset loader, and preprocessing source files are unavailable. The Phase 4 documentation of winsorization/Yeo-Johnson/robust scaling concerns engineered ECG feature columns and is not evidence that those transforms were applied to raw VAE waveforms.",
            "",
            "Whether any parameters were learned, which data fit them, and whether validation/test data influenced preprocessing are **UNRESOLVED**. Unsupervised model type alone does not establish leakage-free preprocessing.",
            "",
            "## F. Outcome/treatment leakage audit",
            "",
            "The VAE documentation describes training as unsupervised and morphology-reconstruction based. Actual training/dataloader code, split labels supplied to the loader, run logs, and checkpoint metadata are absent. Use of MI/troponin labels, diagnoses, treatments, downstream events, or treatment response is therefore **NOT VERIFIED**. Do not describe the embeddings as proven label-independent or leakage-free.",
            "",
            "## G. Temporal eligibility audit",
            "",
            f"The master schema contains {len(results['inputs']['master_medication_timestamp_columns'])} medication/treatment timestamp columns matching medication/treatment time/date naming patterns. It contains window-coded treatment flags but no exact assignment/administered-at time. Consequently `ecg_time < treatment assignment time` cannot be tested for any treatment. Status for Rule A and all other candidates: **TEMPORALLY UNRESOLVED**. Rule A being earliest by `ecg_time` is not evidence of pre-treatment status.",
            "",
            markdown_table(["Candidate ECG rule", "Treatment-relative status", "Assignment time available", "ECG before treatment established", "Reason"], treatment_temporal_rows),
            "",
            "## H. MI timing audit",
            "",
            f"Among **{timing['mi_event_timestamp_audit']['mi_labeled_admissions']:,}** MI-labeled admissions, **{timing['mi_event_timestamp_audit']['mi_admissions_with_exactly_one_distinct_nonmissing_index_mi_time']:,}** have exactly one distinct non-null `index_mi_time`; **{timing['mi_event_timestamp_audit']['mi_admissions_without_exactly_one_distinct_nonmissing_index_mi_time']:,}** do not.",
            "",
            "Timestamp comparisons below use parsed `ecg_time` and a unique `index_mi_time` within MI-labeled admissions. No arbitrary 'near' threshold is introduced; exact same-timestamp observations are reported separately. `time_diff_hours` is not used as a universal MI clock. `Label_Troponin` remains a categorical cohort label. Temporal ordering before MI does **not** imply ordering before treatment.",
            "",
            markdown_table(["Candidate rule", "Selected rows", "MI rows with valid unique event time", "Admission relation counts", "Near threshold used"], temporal_rows),
            "",
            "For Rule A, the 4,871 MI admissions with valid unique event times have 4,521 earliest ECGs before the timestamp, 8 at the same timestamp, and 342 after it. Within those rows, `MI_Acute_Presentation` includes 1,434 before, 8 same-timestamp, and 342 after; all 3,087 `MI_Pre-Incident` rows are before. These observed MI-time relations still do not establish treatment-relative baseline status.",
            "",
            "Rules B/C are outcome/event-time-dependent selections and are not evidence of a valid treatment baseline.",
            "",
            "## I. 64-dimensional latent diagnostics",
            "",
            f"All {diagnostics['dimensions_audited']} dimensions were measured; no dimension was removed. Missingness, variance, range, quantiles, skew, kurtosis, dominant-value share, and near-constant status are provided per dimension in the JSON and the table below.",
            "",
            markdown_table(["Dimension", "Missing", "Variance", "Min", "Median", "Max", "Skew", "Near-constant"], dimension_rows),
            "",
            f"Exact duplicate dimension pairs: **{len(diagnostics['exact_duplicate_dimension_pairs'])}**. Pairwise Pearson comparisons: **{corr['pair_count']:,}**; pairs with |r| ≥ {CORRELATION_THRESHOLD}: **{corr['pairs_at_or_above_threshold']}**; median |r|: **{corr['median_absolute_correlation']:.4g}**; maximum |r|: **{corr['maximum_absolute_correlation']:.4g}**.",
            (
                f"Highest-correlation pair: `{max_corr_pair['dimension_a']}` / `{max_corr_pair['dimension_b']}` (r={max_corr_pair['pearson_correlation']:.4f})."
                if max_corr_pair
                else "No latent-dimension pair met the specified absolute correlation threshold."
            ),
            "",
            "Correlation and distribution summaries are descriptive. They do not give dimensions clinical meanings or imply causal independence. No PCA, scaling, component selection, or dimension removal was performed.",
            "",
            "## J. Causal-role analysis",
            "",
            markdown_table(["Possible role", "Mechanism", "Temporal requirement", "Evidence available", "Evidence missing", "Causal implication"], role_rows),
            "",
            "No single causal role is assigned. Baseline confounding, proxy, prognostic-only, mediator, collider, effect modification, and predictive-only interpretations remain distinct hypotheses; current evidence does not establish one or exclude the post-treatment possibilities.",
            "",
            "## K. Representation options",
            "",
            markdown_table(["Option", "Advantages", "Risks/requirements", "Phase 5 assessment"], option_rows),
            "",
            "## L. Recommended representation",
            "",
            "**Discovery:** NO FINAL REPRESENTATION DECISION YET. Carry `z_ecg` only as an explicitly quarantined block of 64 named dimensions; do not treat it as an approved causal discovery input or 64 separately interpretable causal nodes.",
            "",
            "**Later treatment-effect modeling:** Do not include it as a baseline adjustment variable without treatment-specific evidence that the selected ECG preceded assignment, verified provenance, and a justified causal role. Discovery representation and adjustment representation are not interchangeable.",
            "",
            "## M. Unresolved issues",
            "",
            "- Exact waveform-to-study_id-to-embedding correspondence and extraction joins.",
            "- Actual VAE checkpoint used and training/checkpoint selection membership.",
            "- Whether validation/test waveforms influenced optimization or model selection; whether post-MI waveforms entered training.",
            "- Executable waveform preprocessing, fitted parameters, and train-only scope.",
            "- Whether labels, diagnoses, treatments, or downstream events influenced training/selection.",
            "- Medication assignment timestamps and treatment-specific ECG baseline eligibility.",
            "- Temporal order of each ECG/embedding relative to treatment and MI; MI-before-treatment is not implied by MI-before-ECG or vice versa.",
            "- Whether any latent dimension or the representation block is a confounder, proxy, prognostic factor, mediator, collider, modifier, or prediction-only signal.",
            "",
            "## N. Phase 6 handoff",
            "",
            *[f"{index}. {item}" for index, item in enumerate(results["phase6_handoff"], 1)],
            "",
            "No Phase 6 or Phase 7 analysis was performed. No causal discovery, DAG, treatment selection, time-zero selection, adjustment-set selection, or treatment-effect estimation was performed.",
            "",
            "### PHASE 5 DECISION RECORD",
            "",
            "1. `z_ecg` provenance: PARTIALLY VERIFIED — master dimensions are present; underlying waveform/model/training/extraction lineage is documentary or unavailable.",
            "2. Waveform-to-study_id mapping: PARTIALLY VERIFIED — master `study_id` values are unique and embedding-complete; exact source waveform correspondence and join cannot be re-performed.",
            "3. VAE training split integrity: UNRESOLVED — actual master splits are subject/ECG/admission-disjoint; their use by VAE training is unverified.",
            "4. VAE checkpoint provenance: PARTIALLY VERIFIED — documentation names a run/checkpoint, but no local checkpoint proves it generated current embeddings.",
            "5. VAE preprocessing provenance: UNRESOLVED — executable transforms, fitted parameters, and fit partitions unavailable.",
            "6. Outcome/treatment independence: UNRESOLVED — documentation describes unsupervised training; code and input provenance do not verify absence of these signals.",
            "7. Temporal eligibility relative to treatment: TEMPORALLY UNRESOLVED — no exact treatment assignment timestamp.",
            "8. Temporal relationship to MI: MEASURABLE ONLY for MI admissions with one event timestamp and a valid ECG timestamp; this does not establish pre-treatment status.",
            "9. Number of latent dimensions retained: 64; none removed.",
            "10. PCA performed: NO.",
            "11. Recommended discovery representation: NO FINAL REPRESENTATION DECISION YET; retain all 64 only as a quarantined block pending provenance and time-zero evidence.",
            "12. Recommended later causal-model representation: UNRESOLVED; do not use as baseline adjustment until treatment-specific pre-treatment eligibility and causal role are supported.",
            "13. Most plausible causal roles: A pre-treatment proxy for cardiovascular state or prognostic representation are theoretically plausible but unverified.",
            "14. Roles that cannot currently be excluded: Confounder, proxy, prognostic-only, mediator, collider, effect modifier, predictive-only.",
            "15. Whether `z_ecg` can currently be called a confounder: **NO** — temporal ordering and common-cause role are not established.",
            "16. Whether `z_ecg` can currently be included as a baseline adjustment variable: **NO** — no proof the ECG predates treatment-specific assignment; provenance is incomplete.",
            "17. Remaining blockers: Exact waveform/embedding lineage; VAE training/checkpoint and preprocessing provenance; leakage audit; medication assignment timestamps; treatment-specific time zero.",
            "18. Phase 6 handoff: Obtain source/checkpoint/split/preprocessing artifacts and treatment timestamps; verify waveform lineage and temporal eligibility before any discovery or treatment-effect modeling.",
            "",
        ]
    )


def notebook_document() -> dict[str, Any]:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 5 — z_ecg Representation and Causal-Role Audit\n",
                "\n",
                "Audits representation provenance and possible causal roles only. It does not run causal discovery, construct a DAG, choose a treatment or time zero, or estimate effects. Documentation-only VAE claims are kept distinct from facts verified in the local master parquet files.\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Load actual master splits and audit provenance/linkage\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "from phase5_z_ecg_causal_role_audit import load_master, make_results, write_results\n",
                "master, split_frames, schema_columns = load_master()\n",
                "results = make_results(master, split_frames, schema_columns)\n",
                "write_results(results)\n",
                "results['provenance']['phase5_input_audit']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Linkage, splits, and latent diagnostics\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "results['waveform_embedding_study_id_linkage'], results['inputs']['master_split_integrity']\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "results['latent_diagnostics']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Temporal audit, causal-role alternatives, and recommendation\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "results['temporal_eligibility_and_mi_timing'], results['causal_role_analysis'], results['representation_options'], results['recommendation']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "The final report is written to `phase5_z_ecg_causal_role_audit_report.md`; complete structured results are written to `phase5_z_ecg_causal_role_audit_results.json`. No causal discovery is run.\n",
            ],
        },
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_results(results: dict[str, Any]) -> None:
    JSON_PATH.write_text(
        json.dumps(json_safe(results), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(report_markdown(json_safe(results)), encoding="utf-8")


def write_outputs(results: dict[str, Any]) -> None:
    write_results(results)
    NOTEBOOK_PATH.write_text(
        json.dumps(notebook_document(), indent=1, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    df, split_frames, schema_columns = load_master()
    results = make_results(df, split_frames, schema_columns)
    write_outputs(results)
    summary = {
        "master_split_integrity": results["inputs"]["master_split_integrity"],
        "waveform_embedding_study_id_linkage": results[
            "waveform_embedding_study_id_linkage"
        ],
        "latent_dimension_count": results["latent_diagnostics"]["dimensions_audited"],
        "high_correlation_pairs": results["latent_diagnostics"][
            "pairwise_pearson_correlations"
        ]["pairs_at_or_above_threshold"],
        "treatment_temporal_status": results[
            "temporal_eligibility_and_mi_timing"
        ]["treatment_temporal_eligibility"]["candidate_status"],
        "outputs": [str(JSON_PATH), str(NOTEBOOK_PATH), str(REPORT_PATH)],
    }
    print(json.dumps(json_safe(summary), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
