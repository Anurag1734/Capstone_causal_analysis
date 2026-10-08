from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2")
DATA_DIR = ROOT / "master"
OUTPUT_JSON = ROOT / "phase3_audit_results.json"
NOTEBOOK_PATH = ROOT / "phase3_baseline_covariate_audit.ipynb"
SPLITS = ("train", "validation", "test")

IDENTIFIERS = {"study_id", "SubjectID", "hadm_id"}
OUTCOME_TEMPORAL = {"Label_Troponin", "is_MI", "index_mi_time", "time_diff_hours"}
DEMOGRAPHICS = {"anchor_age", "sex_male"}
COMORBIDITIES = {"diabetes", "hypertension", "ckd", "prior_mi"}
TREATMENTS = {
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
}
Z_ECG = {f"z_ecg_{i}" for i in range(1, 65)}


def read_master() -> tuple[pd.DataFrame, dict[str, int]]:
    split_frames: list[pd.DataFrame] = []
    split_rows: dict[str, int] = {}
    for split in SPLITS:
        frame = pd.read_parquet(DATA_DIR / f"{split}.parquet")
        split_rows[split] = int(len(frame))
        split_frames.append(frame)
    return pd.concat(split_frames, ignore_index=True), split_rows


def group_for(name: str) -> str:
    if name in IDENTIFIERS:
        return "identifier / administrative"
    if name in OUTCOME_TEMPORAL:
        return "outcome / temporal"
    if name in DEMOGRAPHICS:
        return "demographic"
    if name in COMORBIDITIES:
        return "comorbidity / prior history"
    if name in TREATMENTS:
        return "treatment / exposure"
    if name in Z_ECG:
        return "ECG representation (VAE latent)"
    if name in {"ecg_time"}:
        return "ECG timestamp"
    if name.startswith("z_ecg_"):
        return "ECG representation (VAE latent)"
    if name.startswith(("Q_", "R_", "S_", "T_", "ST_", "P_", "PQ_", "QRS_", "RR_")):
        return "ECG-derived feature"
    return "other"


def provenance_for(name: str) -> str:
    group = group_for(name)
    if group == "identifier / administrative":
        return {
            "study_id": "Phase F master schema: unique ECG study identifier.",
            "SubjectID": "Phase F master schema: patient identifier.",
            "hadm_id": "Phase F master schema: hospital admission identifier.",
        }[name]
    if name == "Label_Troponin":
        return "Phase F master schema: label backbone; categorical cohort label."
    if name == "is_MI":
        return "Phase F master schema: binary MI flag; derived from project labeling workflow according to Phase 2 audit."
    if name == "index_mi_time":
        return "Phase F master schema: MI event timestamp; row-level source construction/timing provenance is not locally available."
    if name == "time_diff_hours":
        return "Phase F schema calls this hours between ECG and MI; Phase 2 pipeline audit qualifies semantics: MI rows use ECG minus index_mi_time; controls use admission-time anchor/fallback."
    if name == "ecg_time":
        return "Phase F master schema: ECG recording timestamp."
    if name in DEMOGRAPHICS:
        return "Phase F master schema: demographics joined on SubjectID; age described as age at admission and sex as binary indicator."
    if name in COMORBIDITIES:
        return "Phase F master schema: ICD-coded history features joined on hadm_id and described as from prior admissions; exact source query/window is not present locally."
    if name in TREATMENTS:
        definitions = {
            "statin_before": "pre-admission statin use",
            "statin_during": "in-hospital statin use",
            "statin_after": "post-discharge statin use",
            "beta_blocker_before": "before/pre-admission beta-blocker use",
            "beta_blocker_during": "in-hospital beta-blocker use",
            "acei_before": "before/pre-admission ACE inhibitor use",
            "acei_during": "in-hospital ACE inhibitor use",
            "aspirin_before": "before/pre-admission aspirin use",
            "aspirin_during": "in-hospital aspirin use",
            "vasopressor_during": "vasopressor administration during admission",
            "mech_vent_during": "mechanical ventilation during admission",
        }
        return (
            f"Phase F master schema: {definitions[name]}; treatment source described as "
            "clinical/features_treatments.csv, joined on hadm_id. Exact source query is not locally available."
        )
    if group == "ECG representation (VAE latent)":
        return "Phase F/VAE documentation: deterministic VAE encoder mu dimension; embedding joined by study_id."
    if group == "ECG-derived feature":
        return "Phase F/capstone feature documentation: ECG morphology/timing feature joined by study_id; extracted ECG feature pipeline documented as ECG-Deli plus preprocessing."
    return "No specific source documentation identified in the local project docs."


def data_unit(name: str) -> str:
    group = group_for(name)
    if name == "SubjectID":
        return "patient"
    if name == "hadm_id":
        return "admission key; repeated across ECG rows"
    if name == "study_id":
        return "ECG key"
    if group in {"demographic", "comorbidity / prior history", "treatment / exposure"}:
        return "admission/patient attribute repeated across ECGs; treatment flags verified constant within admission in Phase 2"
    if name in OUTCOME_TEMPORAL or name == "ecg_time":
        return "ECG row; MI time may be shared across rows/admission"
    if group in {"ECG-derived feature", "ECG representation (VAE latent)"}:
        return "ECG associated with study_id; admissions may contain repeated ECG rows"
    return "row-level; precise unit requires provenance"


def temporal_status(name: str) -> str:
    group = group_for(name)
    if name in IDENTIFIERS:
        return "administrative/identifier"
    if name in OUTCOME_TEMPORAL:
        return "outcome-derived / temporal; not baseline"
    if name == "ecg_time":
        return "temporally unresolved relative to treatment-specific baseline/index ECG"
    if name in DEMOGRAPHICS:
        return "likely measured at admission; relation to treatment-specific baseline unresolved"
    if name in COMORBIDITIES:
        return "potentially pre-existing history, but source window/construction not verified"
    if name in TREATMENTS:
        if name.endswith("_after") or name in {"vasopressor_during", "mech_vent_during"}:
            return "post-baseline/downstream or acute episode; exact ordering unresolved"
        if name.endswith("_during"):
            return "in-hospital; post-baseline/downstream or concurrent; exact ordering unresolved"
        return "pre-admission exposure, but not proven before treatment-specific baseline/index ECG"
    if group in {"ECG-derived feature", "ECG representation (VAE latent)"}:
        return "temporally unresolved until index ECG and treatment-specific time zero are selected"
    return "temporally unresolved"


def outcome_information(name: str) -> str:
    if name in OUTCOME_TEMPORAL:
        return "direct outcome/temporal information"
    if name in {"ecg_time"}:
        return "supports temporal linkage; not itself the outcome"
    if group_for(name) in {"ECG-derived feature", "ECG representation (VAE latent)"}:
        return "may encode ECG morphology associated with acute MI; MI information possible, not outcome label itself"
    return "no direct outcome encoding documented; indirect association possible"


def treatment_outcome_effects(name: str) -> tuple[str, str]:
    if name in TREATMENTS and name.endswith("_before"):
        return (
            "Pre-admission window exposure may reflect earlier treatment history; exact order versus treatment-specific baseline is unresolved.",
            "The current MI event is not expected to determine pre-admission exposure, but prior MI/disease history may influence it; exact window is not locally verified.",
        )
    if name in TREATMENTS and (name.endswith("_during") or name.endswith("_after")):
        return (
            "Possible; in-hospital/post-discharge treatment may follow treatment assignment or clinical changes.",
            "Possible; acute treatment/support may follow MI diagnosis, deterioration, or hospital course; post-discharge use is downstream.",
        )
    if group_for(name) in {"ECG-derived feature", "ECG representation (VAE latent)"}:
        return (
            "Possible if the feature's ECG occurred after treatment; timing relative to treatment-specific baseline is unresolved.",
            "Possible because ECG morphology/representation may reflect acute MI or subsequent evolution.",
        )
    if name in DEMOGRAPHICS | COMORBIDITIES:
        return (
            "Not apparent for fixed demographics/history, but precise provenance and time window require verification.",
            "Not apparent for fixed demographics/history; possible for comorbidity/history flags if construction includes current/future information.",
        )
    return "Not applicable or unresolved", "Outcome/temporal variable or unresolved"


def causal_role(name: str) -> str:
    if name in IDENTIFIERS:
        return "administrative/dependence handling; not a causal covariate"
    if name in OUTCOME_TEMPORAL:
        return "outcome, outcome-derived variable, or temporal anchor; exclude from baseline covariates"
    if name == "ecg_time":
        return "temporal index/selection support; causal role unresolved"
    if name in DEMOGRAPHICS:
        return "candidate common-cause indicator and/or effect modifier; causal role not established"
    if name in COMORBIDITIES:
        return "candidate common-cause/proxy indicator and/or effect modifier; causal role not established"
    if name in TREATMENTS:
        return "treatment/exposure or downstream treatment; not a generic adjustment covariate"
    if group_for(name) in {"ECG-derived feature", "ECG representation (VAE latent)"}:
        return "baseline state/proxy, mediator, collider, or predictive-only feature depending on timing/mechanism; unresolved"
    return "causal role unresolved"


def eligibility(name: str) -> tuple[str, str]:
    group = group_for(name)
    if name in IDENTIFIERS:
        return "G. IDENTIFIER / ADMINISTRATIVE VARIABLE", "Use for linking, admission-level unit, or repeated-patient dependence; do not enter as ordinary adjustment covariate."
    if name in OUTCOME_TEMPORAL:
        return "E. OUTCOME-DERIVED / LEAKAGE-PRONE", "Outcome, outcome-derived, or temporal-anchor information; not an ordinary baseline covariate. Never use troponin as a feature."
    if name == "ecg_time":
        return "H. OTHER EXCLUSION — WITH EXPLICIT REASON", "Timestamp used for temporal audit/index selection, not an adjustment covariate."
    if name in TREATMENTS:
        return "F. TREATMENT / EXPOSURE VARIABLE", "Retain as treatment/exposure metadata, not a generic baseline covariate; timing remains as established in frozen Phase 2."
    if name in DEMOGRAPHICS | COMORBIDITIES:
        return "B. POTENTIALLY ELIGIBLE — TEMPORAL/PROVENANCE VERIFICATION REQUIRED", (
            "Potential baseline candidate only. Admission-index timing and/or source-window provenance must be checked against the eventual treatment-specific baseline; no final adjustment inclusion is decided."
        )
    if group_for(name) in {"ECG-derived feature", "ECG representation (VAE latent)"}:
        return "C. TEMPORALLY UNRESOLVED", (
            "Feature is linked to a study_id ECG, but the eventual index ECG/time zero is unselected; the ECG may be acute, post-treatment, or outcome-associated."
        )
    return "H. OTHER EXCLUSION — WITH EXPLICIT REASON", "No documented basis for baseline-covariate use; requires provenance review."


def scalar(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def variable_inventory(df: pd.DataFrame) -> list[dict[str, Any]]:
    inventory = []
    for name in df.columns:
        s = df[name]
        unique_values = s.dropna().unique()
        category, reason = eligibility(name)
        treatment_effect, outcome_effect = treatment_outcome_effects(name)
        inventory.append(
            {
                "variable": name,
                "group": group_for(name),
                "data_type": str(s.dtype),
                "missing_count": int(s.isna().sum()),
                "missing_percentage": float(s.isna().mean() * 100),
                "cardinality_nonmissing": int(len(unique_values)),
                "unique_values_if_cardinality_le_20": (
                    [scalar(v) for v in unique_values.tolist()] if len(unique_values) <= 20 else None
                ),
                "sample_values_if_cardinality_gt_20": (
                    [scalar(v) for v in unique_values[:8].tolist()] if len(unique_values) > 20 else None
                ),
                "documented_source": provenance_for(name),
                "measurement_unit": data_unit(name),
                "temporal_status": temporal_status(name),
                "could_be_affected_by_treatment": treatment_effect,
                "could_be_affected_by_MI_event": outcome_effect,
                "contains_outcome_information": outcome_information(name),
                "leakage_risk": (
                    "high/direct; outcome or temporal variable"
                    if name in OUTCOME_TEMPORAL
                    else "high/possible; post-discharge or acute-treatment/hospital-course feature"
                    if name in TREATMENTS and (name.endswith("_during") or name.endswith("_after"))
                    else "possible; ECG may be during/after MI or after treatment"
                    if group_for(name) in {"ECG-derived feature", "ECG representation (VAE latent)"}
                    else "unresolved pending source-window verification"
                    if name in COMORBIDITIES
                    else "low direct leakage concern; timing relative to baseline still requires verification"
                    if name in DEMOGRAPHICS
                    else "not a causal covariate"
                    if name in IDENTIFIERS
                    else "temporal metadata, not a covariate"
                    if name == "ecg_time"
                    else "unresolved"
                ),
                "potential_causal_role": causal_role(name),
                "eligibility_classification": category,
                "eligibility_reason": reason,
            }
        )
    return inventory


def feature_provenance_audit(df: pd.DataFrame) -> dict[str, Any]:
    ecg_features = [c for c in df.columns if group_for(c) == "ECG-derived feature"]
    embeddings = [c for c in df.columns if c in Z_ECG]
    docs_path = ROOT / "docs" / "VAE Embedding Pipeline.md"
    docs = docs_path.read_text(encoding="utf-8") if docs_path.exists() else ""
    train_only = bool(re.search(r"training.*(?:train split|training split|262,813)", docs, re.IGNORECASE | re.DOTALL))
    return {
        "ecg_feature_count_observed": len(ecg_features),
        "ecg_feature_variables": ecg_features,
        "feature_linkage": "Phase F documentation describes ECG feature join on study_id; each master row is an ECG study row.",
        "specific_ecg_identified": True,
        "eventual_index_ecg_identified": False,
        "multiple_ecgs_per_admission": "Yes; Phase 1 found 44.7% admissions contain >1 ECG. The feature pipeline documentation describes per-study feature extraction and no multiple-ECG aggregation into one ECG row.",
        "multi_ecg_aggregation_evidence": "No multiple-ECG feature aggregation is documented for the master ECG row; cannot verify original implementation because source build scripts/raw feature files are not present in this workspace.",
        "acute_mi_or_treatment_effect_possible": True,
        "pre_treatment_pre_baseline_status": "UNRESOLVED pending index ECG/time-zero selection and treatment timing.",
        "z_ecg_count_observed": len(embeddings),
        "z_ecg_dimensions": sorted(embeddings, key=lambda s: int(s.rsplit("_", 1)[1])),
        "z_ecg_source": "Documented deterministic VAE mu vectors from the ECG associated with study_id, joined by study_id.",
        "vae_supervision": "Documentation describes VAE training as unsupervised/reconstruction-based; labels were not described as the training target.",
        "vae_training_data_scope": (
            "Documentation describes pre-built train/validation/test splits and train/validation monitoring; "
            "the exact checkpoint training membership and whether any held-out ECG waveforms entered training cannot be verified from local model artifacts."
        ),
        "vae_leakage_assessment": (
            "No label-supervised leakage is documented, but latent dimensions can encode MI-related morphology. "
            "Temporal leakage remains possible because embeddings represent ECGs of unresolved timing relative to treatment and outcome."
        ),
        "causal_role_assessment": "Do not label z_ecg as a confounder based on predictive performance; baseline-state/proxy, mediator, collider, or predictive-only roles remain unresolved.",
    }


def treatment_confounding_candidates() -> dict[str, list[dict[str, str]]]:
    base = {
        "anchor_age": "Age may influence chronic/acute treatment indication and MI risk; admission timing versus treatment-specific baseline is not established.",
        "sex_male": "Sex may influence treatment patterns and MI risk; exact baseline relation is not documented, though it is a patient-level demographic.",
        "diabetes": "Diabetes may influence medication indication and MI risk; ICD history is described as prior-admission data, but extraction window/provenance requires verification.",
        "hypertension": "Hypertension may influence treatment indication and MI risk; exact code window and pre-baseline status require verification.",
        "ckd": "CKD may influence treatment choices and cardiovascular risk; source window and pre-baseline status require verification.",
        "prior_mi": "Prior MI may influence secondary-prevention prescribing and future MI risk; exact historical construction requires verification.",
        "ECG-derived state": "Underlying cardiac state may influence treatment and MI risk, but the measured ECG's time and relation to treatment are unresolved; it could be downstream/mediating/collider information.",
        "z_ecg representation": "May proxy ECG state but predictive performance does not establish confounding; index ECG timing and causal role are unresolved.",
    }
    return {
        treatment: [
            {
                "candidate_variable": variable,
                "plausible_shared_cause_rationale": rationale,
                "measured_before_treatment_baseline": "UNRESOLVED",
                "alternative_role_or_caveat": (
                    "Could be post-treatment, mediator, collider, or predictive-only if derived from an ECG after treatment/clinical deterioration."
                    if variable in {"ECG-derived state", "z_ecg representation"}
                    else "Candidate only; not automatically a confounder and not selected into an adjustment set."
                ),
            }
            for variable, rationale in base.items()
        ]
        for treatment in ["aspirin", "statin", "beta_blocker", "acei"]
    }


def decision_record(inventory: list[dict[str, Any]], features: dict[str, Any], confounders: dict) -> dict[str, Any]:
    by_class: dict[str, list[str]] = {}
    for row in inventory:
        by_class.setdefault(row["eligibility_classification"], []).append(row["variable"])
    return {
        "clearly_eligible_baseline_covariates": by_class.get("A. CLEARLY ELIGIBLE BASELINE COVARIATE", []),
        "potentially_eligible_pending_verification": by_class.get("B. POTENTIALLY ELIGIBLE — TEMPORAL/PROVENANCE VERIFICATION REQUIRED", []),
        "temporally_unresolved": by_class.get("C. TEMPORALLY UNRESOLVED", []),
        "post_baseline_or_downstream_treatment_variables": {
            "statin_after": "Post-discharge window; downstream of the in-hospital admission episode.",
            "in_hospital_treatment_flags": {
                "variables": sorted(name for name in TREATMENTS if name.endswith("_during")),
                "status": "Acute/in-hospital. May be before, around, or after an ECG; classify as potential post-baseline/downstream, not definitively downstream, until index ECG and administration times are known.",
            },
            "acute_supportive_interventions": {
                "variables": ["vasopressor_during", "mech_vent_during"],
                "status": "Likely downstream/supportive and severity-related, but precise ordering relative to ECG remains unresolved.",
            },
        },
        "outcome_derived_leakage_prone": by_class.get("E. OUTCOME-DERIVED / LEAKAGE-PRONE", []),
        "treatment_exposure_variables": by_class.get("F. TREATMENT / EXPOSURE VARIABLE", []),
        "identifier_administrative_variables": by_class.get("G. IDENTIFIER / ADMINISTRATIVE VARIABLE", []),
        "candidate_confounders_by_treatment": confounders,
        "causal_roles_unresolved": [
            "ECG-derived features",
            "z_ecg_1 through z_ecg_64",
            "potential history covariates until source-window provenance is verified",
        ],
        "final_adjustment_set_can_be_established": False,
        "final_adjustment_set_status": "UNRESOLVED — Phase 3 identifies eligibility candidates only; DAG/domain constraints and a selected treatment/time zero are not established.",
        "index_ecg_required_for_classifying_ecg_features": True,
        "data_provenance_gaps": [
            "Exact source queries/build scripts for demographics and comorbidities are not present locally.",
            "Underlying preprocessing timestamps/windows for comorbidities are not locally verifiable.",
            "Final index ECG and treatment-specific causal time zero remain unselected/unresolved.",
            "Raw ECG feature extraction and exact study-level preprocessing lineage cannot be verified from available workspace source artifacts.",
            "VAE checkpoint training membership cannot be independently verified from local model artifacts.",
            "No guarantees that admission-age or history covariates precede the eventual treatment-specific baseline are possible until that baseline is defined.",
        ],
        "phase4_handoff": {
            "phase": "DISCOVERY-READY DATASET CONSTRUCTION",
            "potential_inputs": "Identifiers only for linkage/grouping; candidate baseline demographics/history pending provenance/timing verification; ECG features/embeddings only after index ECG, timestamp eligibility, and preprocessing lineage are resolved.",
            "remain_excluded": [
                *sorted(OUTCOME_TEMPORAL),
                "treatment variables from generic covariate set (keep treatment metadata separate)",
                "post-discharge and acute supportive treatment variables as baseline adjustment covariates",
                *sorted(IDENTIFIERS),
                "any troponin feature (project rule: NEVER USE TROPONIN AS A FEATURE)",
            ],
            "require_index_ecg_resolution": ["all 95 ECG-derived features", *sorted(Z_ECG)],
            "require_temporal_or_provenance_resolution": sorted(DEMOGRAPHICS | COMORBIDITIES),
            "treatment_outcome_unresolved": [
                "primary treatment selection",
                "treatment-specific assignment time and causal time zero",
                "causal outcome definition and event horizon",
                "use of pre-admission medications as baseline exposures versus treatment histories",
            ],
            "preprocessing_representation_decisions": [
                "choose one ECG per admission using a pre-specified rule; do not silently aggregate repeated ECGs",
                "verify feature/embedding preprocessing is fit on training data only and applied without held-out leakage",
                "verify winsorization, Yeo-Johnson transforms, and robust scaling fit scope from source pipeline",
                "decide whether to use handcrafted ECG features, z_ecg, or neither after index ECG/timing review; do not treat predictive performance as causal-role evidence",
                "preserve SubjectID grouping/dependence across repeated admissions and respect existing splits",
                "exclude outcome/time-label columns from discovery inputs; maintain treatment and outcome metadata outside generic covariates",
            ],
            "not_performed": "No DAG, discovery algorithm, effect estimation, propensity modeling, treatment selection, or adjustment-set finalization.",
        },
    }


def build_results(df: pd.DataFrame, split_rows: dict[str, int]) -> dict[str, Any]:
    inventory = variable_inventory(df)
    features = feature_provenance_audit(df)
    confounders = treatment_confounding_candidates()
    decision = decision_record(inventory, features, confounders)
    class_counts: dict[str, int] = {}
    for row in inventory:
        group = row["group"]
        class_counts[group] = class_counts.get(group, 0) + 1
    return {
        "dataset_summary": {
            "split_rows": split_rows,
            "combined_rows": int(len(df)),
            "column_count": int(len(df.columns)),
            "patient_count": int(df["SubjectID"].nunique()) if "SubjectID" in df else None,
            "admission_count": int(df["hadm_id"].nunique()) if "hadm_id" in df else None,
            "ecg_row_count": int(df["study_id"].nunique()) if "study_id" in df else None,
            "variables_by_group": class_counts,
        },
        "complete_variable_inventory": inventory,
        "ecg_provenance_assessment": features,
        "treatment_handling": {
            "treatment_variables": sorted(TREATMENTS),
            "phase2_frozen_conclusion": "Window-coded treatment/exposure variables; no exact medication administration times; treatment-specific time zero UNRESOLVED.",
            "phase3_handling": "Keep treatment variables separate from generic baseline covariates. No treatment selected and no adjustment set finalized.",
            "vasopressor_mechanical_ventilation": "Acute supportive interventions; do not treat as primary baseline covariates.",
        },
        "outcome_temporal_variable_exclusions": {
            name: {
                "eligibility": "E. OUTCOME-DERIVED / LEAKAGE-PRONE",
                "role": "outcome/temporal anchor/derived time variable",
                "reason": "Not an ordinary baseline adjustment covariate; time_diff_hours is not a universal ECG-to-MI variable and must not determine baseline eligibility.",
            }
            for name in sorted(OUTCOME_TEMPORAL)
        },
        "identifier_handling": {
            "study_id": "Not a covariate; required for ECG linkage and index ECG selection.",
            "hadm_id": "Not a covariate; required to preserve primary admission-level unit and repeated-ECG grouping.",
            "SubjectID": "Not a covariate by identifier value; retain to account for repeated admissions/patient dependence and split checks.",
        },
        "preliminary_confounding_candidates": confounders,
        "unresolved_issues": decision["data_provenance_gaps"],
        "phase3_decision_record": decision,
    }


def notebook_document() -> dict[str, Any]:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 3 — Baseline Covariate Eligibility Audit\n",
                "\n",
                "Phases 0–2 are frozen. This notebook audits variable eligibility and causal-role possibilities only; it does not construct a DAG, select treatment/time zero/index ECG, estimate effects, fit propensity scores, or finalize an adjustment set.\n",
                "\n",
                "Evidence insufficient to classify a variable is recorded as unresolved. The notebook relies on the actual three split parquet files and local project documentation.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import json\n",
                "from pathlib import Path\n",
                "import pandas as pd\n",
                "from IPython.display import display\n",
                "\n",
                "ROOT = Path(r'c:/Users/anura/OneDrive/Desktop/capstone2')\n",
                "DATA_DIR = ROOT / 'master'\n",
                "SPLITS = ['train', 'validation', 'test']\n",
                "frames = {split: pd.read_parquet(DATA_DIR / f'{split}.parquet') for split in SPLITS}\n",
                "split_rows = {split: len(frame) for split, frame in frames.items()}\n",
                "df = pd.concat(list(frames.values()), ignore_index=True)\n",
                "print({'split_rows': split_rows, 'combined_rows': len(df), 'columns': len(df.columns)})\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Variable inventory and eligibility\n",
                "\n",
                "The inventory is generated from every actual master column, not just the expected handwritten list. It includes type, missingness, cardinality, documented provenance, measurement unit, temporal status, possible treatment/outcome effects, outcome information, leakage risk, causal-role possibilities, and eligibility reason.\n",
                "\n",
                "The audit categories are A–H as specified. A category A is not assigned without clear temporal evidence.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import sys\n",
                "sys.path.insert(0, str(ROOT))\n",
                "from phase3_baseline_covariate_audit import build_results\n",
                "results = build_results(df, split_rows)\n",
                "inventory = pd.DataFrame(results['complete_variable_inventory'])\n",
                "print(results['dataset_summary'])\n",
                "display(inventory[['variable','group','data_type','missing_count','cardinality_nonmissing','eligibility_classification','temporal_status']])\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Demographics, history, and ECG provenance\n",
                "\n",
                "Demographic and comorbidity values are candidates only pending temporal and provenance verification. ECG features and `z_ecg` are linked to a `study_id`, but the final index ECG has not been selected. Their relation to treatment and MI can therefore not be assumed to be baseline.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "display(inventory[inventory['group'].isin(['demographic','comorbidity / prior history'])])\n",
                "print(json.dumps(results['ecg_provenance_assessment'], indent=2))\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Treatment confounding candidates\n",
                "\n",
                "These are hypotheses about plausible shared causes, not a final confounder list or adjustment set. A variable is not called a confounder solely because it predicts treatment or outcome; measurement before the relevant baseline and a plausible causal relation to both are still required.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "for treatment, candidates in results['preliminary_confounding_candidates'].items():\n",
                "    print('\\n', treatment)\n",
                "    display(pd.DataFrame(candidates))\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Phase 3 Decision Record\n",
                "\n",
                "No final treatment, time zero, index ECG, or adjustment set is selected. The eligible output consists of candidates requiring later verification; all timing, leakage, and causal-role limits remain explicit.\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "print(json.dumps(results['phase3_decision_record'], indent=2))\n",
                "print('\\nPhase 4 handoff:')\n",
                "print(json.dumps(results['phase3_decision_record']['phase4_handoff'], indent=2))\n",
            ],
        },
    ]
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
    df, split_rows = read_master()
    results = build_results(df, split_rows)
    OUTPUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    NOTEBOOK_PATH.write_text(json.dumps(notebook_document(), indent=1, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "dataset_summary": results["dataset_summary"],
                "eligibility_counts": pd.Series(
                    [row["eligibility_classification"] for row in results["complete_variable_inventory"]]
                ).value_counts().to_dict(),
                "clearly_eligible": results["phase3_decision_record"]["clearly_eligible_baseline_covariates"],
                "phase4_handoff": results["phase3_decision_record"]["phase4_handoff"]["phase"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
