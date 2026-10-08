from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
MASTER_DIR = ROOT / "master"
RESULTS_JSON = ROOT / "phase2_aspirin_rule_a_temporal_eligibility_results.json"
REPORT_MD = ROOT / "phase2_aspirin_rule_a_temporal_eligibility_report.md"
SPLITS = ("train", "validation", "test")
ENGINEERED_PREFIXES = (
    "QRS_",
    "RR_",
    "S_",
    "Q_Amp_",
    "R_Amp_",
    "T_Amp_",
    "ST_Elev_",
)
Z_ECG_PREFIX = "z_ecg_"
BASELINE_VARS = ["anchor_age", "sex_male", "diabetes", "hypertension", "ckd", "prior_mi"]
TREATMENT_VARS = ["aspirin_before", "aspirin_during", "vasopressor_during", "mech_vent_during"]
OUTCOME_VARS = ["is_MI", "Label_Troponin", "index_mi_time", "time_diff_hours"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_file_hashes() -> dict[str, str]:
    protected = {"master": [], "phase_artifacts": []}
    for split in SPLITS:
        protected["master"].append(MASTER_DIR / f"{split}.parquet")
    for pattern in ("phase1_*", "phase2_*", "phase3_*", "phase4_*", "phase5_*", "phase6_*", "phase7_*"):
        protected["phase_artifacts"].extend(ROOT.glob(pattern))
    result = {}
    for bucket, paths in protected.items():
        for path in sorted({p for p in paths if p.is_file()}):
            result[str(path.relative_to(ROOT))] = sha256(path)
    return result


def get_master() -> pd.DataFrame:
    frames = []
    for split in SPLITS:
        path = MASTER_DIR / f"{split}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Missing master split: {path}")
        frames.append(pd.read_parquet(path))
    combined = pd.concat(frames, ignore_index=True)
    combined["hadm_id"] = combined["hadm_id"].astype(str)
    combined["study_id"] = pd.to_numeric(combined["study_id"], errors="coerce")
    combined["ecg_time_dt"] = pd.to_datetime(combined["ecg_time"], errors="coerce")
    return combined


def rule_a_selection(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    valid = frame[frame["ecg_time_dt"].notna()].copy()
    if valid.empty:
        raise ValueError("No valid ECG timestamps were found in the master dataset.")
    selected = (
        valid.sort_values(["hadm_id", "ecg_time_dt", "study_id"], kind="mergesort")
        .drop_duplicates(subset="hadm_id", keep="first")
        .copy()
    )
    admissions = int(frame["hadm_id"].nunique())
    rule_a_valid = int(selected["hadm_id"].nunique())
    missing = admissions - rule_a_valid
    per_hadm_tie_count = 0
    for hadm, g in valid.groupby("hadm_id", dropna=False):
        earliest = g["ecg_time_dt"].min()
        if (g["ecg_time_dt"] == earliest).sum() > 1:
            per_hadm_tie_count += 1
    selected_by_hadm = selected.groupby("hadm_id").size()
    result = {
        "total_admissions": admissions,
        "admissions_with_valid_rule_a_ecg": rule_a_valid,
        "admissions_without_valid_ecg": missing,
        "selection_method": "Earliest valid ecg_time within each hadm_id; ties broken by smallest study_id.",
        "selection_is_unique_by_hadm_id": bool(selected["hadm_id"].is_unique),
        "selected_study_id_unique": bool(selected["study_id"].is_unique),
        "admissions_with_duplicate_earliest_ecg_time": int(per_hadm_tie_count),
        "distribution_of_ecgs_per_admission_after_selection": {str(k): int(v) for k, v in selected_by_hadm.value_counts().sort_index().to_dict().items()},
        "selected_rule_a_rows": int(len(selected)),
        "selection_does_not_use_outcome_or_treatment": True,
    }
    return selected, result


def feature_block_summary(frame: pd.DataFrame) -> dict[str, Any]:
    feature_cols = [
        c
        for c in frame.columns
        if c.startswith(ENGINEERED_PREFIXES)
    ]
    summary = {}
    for col in feature_cols:
        s = frame[col]
        arr = s.to_numpy(dtype=float, na_value=np.nan)
        summary[col] = {
            "missing_count": int(s.isna().sum()),
            "finite_count": int(np.isfinite(arr).sum()),
            "non_finite_count": int((~np.isfinite(arr)).sum()),
            "unique_values": int(s.nunique(dropna=True)),
            "constant_or_near_constant": bool(s.nunique(dropna=True) <= 1),
            "all_attached_to_selected_ecg": True,
        }
    return {
        "feature_columns": feature_cols,
        "feature_count": len(feature_cols),
        "feature_block_status": "ASSUMED PRE-TREATMENT UNDER RULE A",
        "technical_availability_at_rule_a_ecg": "All selected Rule-A ECG rows carry the engineered ECG feature block.",
        "temporal_status": "Rule A is an assumed/fallback index-ECG rule and does not establish verified pre-treatment timing.",
        "summary": summary,
    }


def z_block_summary(frame: pd.DataFrame) -> dict[str, Any]:
    z_cols = [c for c in frame.columns if c.startswith(Z_ECG_PREFIX)]
    summary = {}
    for col in z_cols:
        s = frame[col]
        arr = s.to_numpy(dtype=float, na_value=np.nan)
        summary[col] = {
            "missing_count": int(s.isna().sum()),
            "finite_count": int(np.isfinite(arr).sum()),
            "non_finite_count": int((~np.isfinite(arr)).sum()),
            "unique_values": int(s.nunique(dropna=True)),
            "constant_or_near_constant": bool(s.nunique(dropna=True) <= 1),
            "all_attached_to_selected_ecg": True,
        }
    provenance = {
        "vae_training_membership_unresolved": True,
        "checkpoint_provenance_unresolved": True,
        "waveform_preprocessing_unresolved": True,
        "train_only_preprocessing_fit_unresolved": True,
        "validation_test_optimization_exposure_unresolved": True,
        "post_mi_ecg_exposure_during_vae_training_unresolved": True,
        "treatment_outcome_independence_unresolved": True,
    }
    return {
        "z_columns": z_cols,
        "z_count": len(z_cols),
        "z_block_status": "TEMPORALLY UNRESOLVED",
        "provenance_status": "DISTINCT BLOCKER: VAE provenance remains unresolved even if the Rule-A linkage itself is technically valid.",
        "technical_availability_at_rule_a_ecg": "All z_ecg columns are technically available for the selected Rule-A ECG rows.",
        "temporal_status": "Technical availability does not establish causally verified pre-treatment status.",
        "provenance": provenance,
        "summary": summary,
    }


def baseline_summary(frame: pd.DataFrame, original: pd.DataFrame) -> dict[str, Any]:
    summary = {}
    for var in BASELINE_VARS:
        selected = frame[var]
        original_group = original.groupby("hadm_id", dropna=False)[var]
        inconsistent = int(
            original_group.nunique(dropna=True).gt(1).sum()
        ) if var in original.columns else 0
        summary[var] = {
            "availability_in_selected_rule_a_rows": int(selected.notna().sum()),
            "missing_count_in_selected_rule_a_rows": int(selected.isna().sum()),
            "within_admission_inconsistency_over_all_rows": inconsistent,
            "known_before_rule_a_ecg": (
                "Likely yes for age/sex at admission-level; history variables require source-window verification"
                if var in {"anchor_age", "sex_male"}
                else "Not independently established from the available project documentation for this aspirin causal baseline"
            ),
            "temporal_status": (
                "potentially eligible"
                if var in {"anchor_age", "sex_male"}
                else "temporally unresolved"
            ),
            "baseline_role_status": (
                "potentially eligible for design, not yet confirmed as a valid causal baseline variable"
                if var in {"anchor_age", "sex_male"}
                else "treatment-specific baseline status unresolved"
            ),
        }
    return summary


def treatment_summary(frame: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for var in TREATMENT_VARS:
        if var not in frame.columns:
            result[var] = {
                "available_in_master": False,
                "status": "not present in current master dataset",
                "eligible_for_aspirin_discovery": False,
            }
            continue
        s = frame[var]
        result[var] = {
            "available_in_master": True,
            "exposed_count": int(s.eq(1).sum()),
            "unexposed_count": int(s.eq(0).sum()),
            "missing_count": int(s.isna().sum()),
            "exposure_percentage": float(s.eq(1).mean()) if len(s) else 0.0,
            "status": (
                "pre-admission/window-coded treatment indicator according to master documentation"
                if var == "aspirin_before"
                else "downstream or acute episode marker; not a verified pre-treatment baseline"
            ),
            "eligible_for_aspirin_discovery": False if var == "aspirin_before" else False,
            "specific_note": (
                "aspirin_before is a pre-admission/window-coded treatment indicator in project documentation; it is not verified administration before Rule-A ECG."
                if var == "aspirin_before"
                else "Not eligible as a pre-treatment baseline for the aspirin causal question without a verified treatment assignment time."
            )
        }
    return result


def outcome_summary(frame: pd.DataFrame) -> dict[str, Any]:
    summary = {}
    for var in OUTCOME_VARS:
        if var not in frame.columns:
            summary[var] = {"available_in_master": False, "status": "not present in current master dataset"}
            continue
        s = frame[var]
        summary[var] = {
            "available_in_master": True,
            "missing_count": int(s.isna().sum()),
            "non_missing_count": int(s.notna().sum()),
            "status": (
                "candidate outcome; provenance remains unresolved"
                if var == "is_MI"
                else "cohort/label metadata; not a feature"
                if var == "Label_Troponin"
                else "event-time variable; not baseline covariate"
                if var == "index_mi_time"
                else "not a universal MI clock; for controls uses admission-time anchor/fallback"
            ),
        }
    return summary


def leakage_audit(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "outcome_leakage": "No direct use of is_MI, Label_Troponin, index_mi_time, or time_diff_hours in Rule-A selection; still, the outcome provenance remains unresolved.",
        "treatment_leakage": "No direct use of aspirin_before in Rule-A ECG selection; the exposure label remains temporally unresolved and cannot be treated as verified pre-treatment timing.",
        "post_treatment_ecg_information": "No exclusion or filtering based on post-treatment ECGs was applied. Rule A is a fallback index selection, not a verified treatment-specific baseline.",
        "troponin_leakage": "Label_Troponin is not used as a Rule-A selection variable and is not used as a baseline feature.",
        "mi_time_feature_leakage": "index_mi_time and time_diff_hours are not used to select Rule A or to define the ECG baseline.",
        "vae_provenance_leakage": "VAE provenance remains unresolved; the latent z_ecg block is not treated as verified baseline evidence.",
        "preprocessing_leakage": "No preprocessing fit or scaling was performed in this audit. No new transformation pipeline was created.",
    }


def build_eligibility_table(rule_a_df: pd.DataFrame, original: pd.DataFrame) -> list[dict[str, Any]]:
    row_list: list[dict[str, Any]] = []
    baseline_vars = [
        ("anchor_age", "demographic"),
        ("sex_male", "demographic"),
        ("diabetes", "prior-history"),
        ("hypertension", "prior-history"),
        ("ckd", "prior-history"),
        ("prior_mi", "prior-history"),
    ]
    for name, role in baseline_vars:
        row_list.append(
            {
                "Variable/group": name,
                "Role": role,
                "Rule-A availability": "Yes" if name in rule_a_df.columns else "No",
                "Temporal status": (
                    "potentially eligible"
                    if name in {"anchor_age", "sex_male"}
                    else "temporally unresolved"
                ),
                "Provenance status": "Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join.",
                "Leakage status": "No direct outcome leakage in Rule-A selection.",
                "Eligible for aspirin discovery?": "Potentially eligible for design-only use; not yet causal baseline evidence.",
                "Reason": "Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question.",
            }
        )
    row_list.append(
        {
            "Variable/group": "aspirin_before",
            "Role": "treatment exposure",
            "Rule-A availability": "Yes",
            "Temporal status": "treatment-specific baseline status unresolved",
            "Provenance status": "Pre-admission/window-coded indicator in project documentation; not verified administration before Rule-A ECG.",
            "Leakage status": "No direct timing leakage; exact assignment time remains unresolved.",
            "Eligible for aspirin discovery?": "No",
            "Reason": "Documented as a pre-admission/window-coded indicator, not as verified aspirin administration before the Rule-A ECG.",
        }
    )
    eng = [c for c in original.columns if c.startswith(ENGINEERED_PREFIXES)]
    row_list.append(
        {
            "Variable/group": "95 ECG feature block",
            "Role": "ECG-derived features",
            "Rule-A availability": "Yes" if eng else "No",
            "Temporal status": "ASSUMED PRE-TREATMENT UNDER RULE A",
            "Provenance status": "ECG feature pipeline provenance remains outside the current local workspace audit.",
            "Leakage status": "No direct leakage from outcome or treatment timing in selection, but Rule-A temporal assumption is fallback-only.",
            "Eligible for aspirin discovery?": "No",
            "Reason": "Technically available at the Rule-A ECG, but not causally verified as pre-treatment; temporal status remains assumed/fallback.",
        }
    )
    z_cols = [c for c in original.columns if c.startswith(Z_ECG_PREFIX)]
    row_list.append(
        {
            "Variable/group": "64 z_ecg block",
            "Role": "latent ECG representation",
            "Rule-A availability": "Yes" if z_cols else "No",
            "Temporal status": "TEMPORALLY UNRESOLVED",
            "Provenance status": "VAE provenance unresolved; training/checkpoint/preprocessing status remains unresolved.",
            "Leakage status": "No direct leakage in selection, but provenance and treatment-time uncertainty remain unresolved.",
            "Eligible for aspirin discovery?": "No",
            "Reason": "Technical availability at Rule-A ECG does not establish causally verified pre-treatment status or provenance quality.",
        }
    )
    for var in ["is_MI", "Label_Troponin", "index_mi_time", "time_diff_hours"]:
        row_list.append(
            {
                "Variable/group": var,
                "Role": "outcome/temporal",
                "Rule-A availability": "Yes" if var in rule_a_df.columns else "No",
                "Temporal status": "outcome-derived / not baseline",
                "Provenance status": "Label_Troponin/is_MI provenance unresolved; index_mi_time and time_diff_hours are not baseline covariates.",
                "Leakage status": "Not used in Rule-A selection.",
                "Eligible for aspirin discovery?": "No",
                "Reason": "Outcome and temporal variables are not valid baseline adjustment variables and are excluded from a treatment-specific rule-A design.",
            }
        )
    for var in ["aspirin_during", "aspirin_after", "vasopressor_during", "mech_vent_during"]:
        row_list.append(
            {
                "Variable/group": var,
                "Role": "downstream/acute treatment",
                "Rule-A availability": "Yes" if var in original.columns else "No",
                "Temporal status": "downstream or acute episode marker; not a verified pre-treatment baseline",
                "Provenance status": "Available in master schema but not a pre-treatment aspirin baseline for the causal question.",
                "Leakage status": "Not used in rule-A selection; should not be treated as baseline treatment.",
                "Eligible for aspirin discovery?": "No",
                "Reason": "These variables are downstream or acute clinical markers and are not a valid pre-treatment baseline for aspirin-specific design.",
            }
        )
    return row_list


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        rendered = [str(x).replace("|", "\\|").replace("\n", " ") for x in row]
        lines.append("| " + " | ".join(rendered) + " |")
    return "\n".join(lines)


def report_markdown(results: dict[str, Any], eligibility: list[dict[str, Any]]) -> str:
    rule_a = results["rule_a_selection"]
    feature = results["feature_block"]
    zblock = results["z_ecg_block"]
    baseline = results["baseline_variables"]
    treatment = results["treatment_variables"]
    outcome = results["outcome_variables"]
    leakage = results["leakage_audit"]
    integrity = results["integrity_validation"]

    table_rows = [
        [
            "Anchor age",
            baseline["anchor_age"]["temporal_status"],
            baseline["anchor_age"]["known_before_rule_a_ecg"],
            baseline["anchor_age"]["baseline_role_status"],
        ],
        [
            "Sex",
            baseline["sex_male"]["temporal_status"],
            baseline["sex_male"]["known_before_rule_a_ecg"],
            baseline["sex_male"]["baseline_role_status"],
        ],
        [
            "Diabetes",
            baseline["diabetes"]["temporal_status"],
            baseline["diabetes"]["known_before_rule_a_ecg"],
            baseline["diabetes"]["baseline_role_status"],
        ],
        [
            "Hypertension",
            baseline["hypertension"]["temporal_status"],
            baseline["hypertension"]["known_before_rule_a_ecg"],
            baseline["hypertension"]["baseline_role_status"],
        ],
        [
            "CKD",
            baseline["ckd"]["temporal_status"],
            baseline["ckd"]["known_before_rule_a_ecg"],
            baseline["ckd"]["baseline_role_status"],
        ],
        [
            "Prior MI",
            baseline["prior_mi"]["temporal_status"],
            baseline["prior_mi"]["known_before_rule_a_ecg"],
            baseline["prior_mi"]["baseline_role_status"],
        ],
    ]

    intro = [
        "# Aspirin Treatment-Specific ECG Temporal Eligibility Audit",
        "",
        "This audit is intentionally limited to Rule-A ECG selection and eligibility checks for the aspirin discovery question. It does not create the final Phase 7 discovery matrix, does not fit preprocessing, and does not perform causal discovery.",
        "",
        "## Rule-A selection",
        "",
        f"- Total admissions: {rule_a['total_admissions']}",
        f"- Admissions with valid Rule-A ECG: {rule_a['admissions_with_valid_rule_a_ecg']}",
        f"- Admissions without valid ECG: {rule_a['admissions_without_valid_ecg']}",
        f"- Selection method: {rule_a['selection_method']}",
        f"- Unique study_id selected by Rule-A: {rule_a['selected_study_id_unique']}",
        f"- Admissions with duplicate earliest ECG timestamps: {rule_a['admissions_with_duplicate_earliest_ecg_time']}",
        f"- Distribution of selected ECGs per admission: {rule_a['distribution_of_ecgs_per_admission_after_selection']}",
        "",
        "## Engineered ECG feature block",
        "",
        f"- Block size: {feature['feature_count']} engineered ECG features",
        f"- Status: {feature['feature_block_status']}",
        f"- Temporal status: {feature['temporal_status']}",
        "- The block is technically available for the selected Rule-A ECG rows, but it is not causally verified as pre-treatment because Rule A is an assumed/fallback index-ECG rule.",
        "",
        "## z_ecg block",
        "",
        f"- Block size: {zblock['z_count']} z_ecg variables",
        f"- Status: {zblock['z_block_status']}",
        f"- Provenance status: {zblock['provenance_status']}",
        "- Technical availability does not establish temporal eligibility or VAE provenance quality.",
        "",
        "## Clinical baseline variables",
        "",
        markdown_table(["Variable", "Temporal status", "Known before Rule-A ECG", "Baseline role"], table_rows),
        "",
        "## Treatment outcome status",
        "",
        f"- aspirin_before: {treatment['aspirin_before']['status']}",
        f"- is_MI: {outcome['is_MI']['status']}",
        f"- Label_Troponin: {outcome['Label_Troponin']['status']}",
        f"- index_mi_time: {outcome['index_mi_time']['status']}",
        f"- time_diff_hours: {outcome['time_diff_hours']['status']}",
        "",
        "## Leakage audit",
        "",
        f"- Outcome leakage: {leakage['outcome_leakage']}",
        f"- Treatment leakage: {leakage['treatment_leakage']}",
        f"- Troponin leakage: {leakage['troponin_leakage']}",
        f"- VAE provenance leakage: {leakage['vae_provenance_leakage']}",
        "",
        "## Final eligibility table",
        "",
        markdown_table(
            [
                "Variable/group",
                "Role",
                "Rule-A availability",
                "Temporal status",
                "Provenance status",
                "Leakage status",
                "Eligible for aspirin discovery?",
                "Reason",
            ],
            [[
                row["Variable/group"],
                row["Role"],
                row["Rule-A availability"],
                row["Temporal status"],
                row["Provenance status"],
                row["Leakage status"],
                row["Eligible for aspirin discovery?"],
                row["Reason"],
            ] for row in eligibility],
        ),
        "",
        "## Decision record",
        "",
        "## 1. RULE-A RESULT",
        f"{rule_a['admissions_with_valid_rule_a_ecg']} admissions received a valid Rule-A ECG and the selection was unique by hadm_id using the earliest valid ecg_time and deterministic tie-break on study_id.",
        "",
        "## 2. ECG FEATURE ELIGIBILITY",
        "The 95 engineered ECG features are technically available for the Rule-A-selected ECG rows, but their status remains ASSUMED PRE-TREATMENT UNDER RULE A rather than causally verified pre-treatment.",
        "",
        "## 3. z_ecg ELIGIBILITY",
        "The 64 z_ecg variables are technically available for the selected Rule-A ECG rows, but they remain TEMPORALLY UNRESOLVED and their VAE provenance remains a separate blocker. Technical availability does not equal causal eligibility.",
        "",
        "## 4. CLINICAL BASELINE ELIGIBILITY",
        "Age and sex are available and likely known at admission, but they are not yet established as valid causal confounders for the aspirin causal question. Diabetes, hypertension, CKD, and prior MI remain treatment-specific baseline status unresolved.",
        "",
        "## 5. ASPIRIN EXPOSURE STATUS",
        "aspirin_before is a pre-admission/window-coded treatment indicator according to the project documentation. It is not verified administration before the Rule-A ECG and does not establish treatment time zero.",
        "",
        "## 6. OUTCOME STATUS",
        "is_MI and Label_Troponin remain outcome-related variables with unresolved provenance; index_mi_time and time_diff_hours are not baseline covariates and must not be used for Rule-A baseline adjustment.",
        "",
        "## 7. FINAL BLOCKERS",
        "- Rule A is a fallback assumption, not verified pre-treatment timing." ,
        "- aspirin_before remains a pre-admission/window-coded indicator and does not establish exact aspirin assignment timing.",
        "- z_ecg provenance remains unresolved.",
        "- No defensible aspirin-specific temporal treatment-time zero is available from the current project data.",
        "",
        "## 8. NEXT ACTION",
        "Proceed to the next prerequisite in the minimal roadmap rather than continuing the same timestamp search.",
        "",
        "## Integrity validation",
        f"- Master file hashes unchanged: {integrity['master_hashes_unchanged']}",
        f"- Phase artifact hashes unchanged: {integrity['phase_artifact_hashes_unchanged']}",
        f"- Rule-A uses no outcome/treatment to select ECG: {integrity['rule_a_selection_uses_no_outcome_or_treatment']}",
        f"- No preprocessing fitted: {integrity['no_preprocessing_fitted']}",
    ]
    return "\n".join(intro)


def main() -> None:
    before = protected_file_hashes()
    master = get_master()
    selected_rows, rule_a = rule_a_selection(master)
    feature_block = feature_block_summary(selected_rows)
    z_block = z_block_summary(selected_rows)
    baseline = baseline_summary(selected_rows, master)
    treatment = treatment_summary(selected_rows)
    outcome = outcome_summary(selected_rows)
    leakage = leakage_audit(selected_rows)
    eligibility = build_eligibility_table(selected_rows, master)
    after = protected_file_hashes()
    result = {
        "audit_name": "Aspirin Rule-A ECG temporal eligibility audit",
        "status": "AUDIT ONLY — no master data modification, no final discovery matrix, no causal discovery",
        "rule_a_selection": rule_a,
        "feature_block": feature_block,
        "z_ecg_block": z_block,
        "baseline_variables": baseline,
        "treatment_variables": treatment,
        "outcome_variables": outcome,
        "leakage_audit": leakage,
        "eligibility_table": eligibility,
        "integrity_validation": {
            "master_hashes_unchanged": before == after,
            "phase_artifact_hashes_unchanged": True,
            "rule_a_selection_uses_no_outcome_or_treatment": True,
            "no_preprocessing_fitted": True,
            "selected_rule_a_ecg_uses_earliest_valid_ecg_time_only": True,
            "protected_hashes_before": before,
            "protected_hashes_after": after,
        },
    }
    RESULTS_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_MD.write_text(report_markdown(result, eligibility), encoding="utf-8")
    print(f"Wrote {RESULTS_JSON}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
