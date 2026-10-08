from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PHASE1_PATH = ROOT / "phase1_audit_results.json"
PHASE2_PATH = ROOT / "phase2_audit_results.json"
PHASE3_PATH = ROOT / "phase3_audit_results.json"
PHASE4_PATH = ROOT / "phase4_discovery_ready_dataset_results.json"
PHASE5_PATH = ROOT / "phase5_z_ecg_causal_role_audit_results.json"
MASTER_DOC_PATH = ROOT / "docs" / "Phase F — Master Dataset.md"
VAE_DOC_PATH = ROOT / "docs" / "VAE Embedding Pipeline.md"
JSON_PATH = ROOT / "phase6_background_causal_constraints_results.json"
NOTEBOOK_PATH = ROOT / "phase6_background_causal_constraints.ipynb"
REPORT_PATH = ROOT / "phase6_background_causal_constraints_report.md"

TREATMENT_SPECS = {
    "aspirin": {
        "exposure": "aspirin_before",
        "during": "aspirin_during",
        "after": None,
        "contrast": "Pre-admission aspirin-use indicator vs no recorded pre-admission aspirin-use indicator; not an identified assignment intervention.",
        "clinical_note": "Phase F describes aspirin_before as use before admission and aspirin_during as in-hospital use; exact administration or initiation times are unavailable.",
    },
    "statin": {
        "exposure": "statin_before",
        "during": "statin_during",
        "after": "statin_after",
        "contrast": "Pre-admission statin-use indicator vs no recorded pre-admission statin-use indicator; not an identified assignment intervention.",
        "clinical_note": "Phase F describes statin_before as use before admission, statin_during as in-hospital use, and statin_after as post-discharge use; exact times are unavailable.",
    },
    "beta_blocker": {
        "exposure": "beta_blocker_before",
        "during": "beta_blocker_during",
        "after": None,
        "contrast": "Pre-admission beta-blocker-use indicator vs no recorded pre-admission beta-blocker-use indicator; not an identified assignment intervention.",
        "clinical_note": "Phase F describes beta_blocker_before as use before admission and beta_blocker_during as in-hospital use; exact administration or initiation times are unavailable.",
    },
    "acei": {
        "exposure": "acei_before",
        "during": "acei_during",
        "after": None,
        "contrast": "Pre-admission ACE-inhibitor-use indicator vs no recorded pre-admission ACE-inhibitor-use indicator; not an identified assignment intervention.",
        "clinical_note": "Phase F describes acei_before as use before admission and acei_during as in-hospital use; exact administration or initiation times are unavailable.",
    },
}

DEMOGRAPHICS = ["anchor_age", "sex_male"]
HISTORY = ["diabetes", "hypertension", "ckd", "prior_mi"]
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
OUTCOME_METADATA = ["Label_Troponin", "is_MI", "index_mi_time", "time_diff_hours"]
ADMIN_METADATA = ["study_id", "SubjectID", "hadm_id", "ecg_time"]
CAUSAL_OUTCOME_NODE = "MI_event"


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Frozen Phase input is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def phase_inputs() -> dict[str, Any]:
    phase1 = read_json(PHASE1_PATH)
    phase2 = read_json(PHASE2_PATH)
    phase3 = read_json(PHASE3_PATH)
    phase4 = read_json(PHASE4_PATH)
    phase5 = read_json(PHASE5_PATH)
    master_doc = (
        MASTER_DOC_PATH.read_text(encoding="utf-8")
        if MASTER_DOC_PATH.is_file()
        else ""
    )
    vae_doc = VAE_DOC_PATH.read_text(encoding="utf-8") if VAE_DOC_PATH.is_file() else ""

    phase4_inventory = phase4.get("complete_variable_inventory", [])
    if not phase4_inventory:
        raise ValueError("Phase 4 variable inventory is empty; cannot enumerate nodes.")
    actual_names = [row["variable"] for row in phase4_inventory]
    if len(actual_names) != len(set(actual_names)):
        raise ValueError("Phase 4 inventory contains duplicate variable names.")

    return {
        "phase1": phase1,
        "phase2": phase2,
        "phase3": phase3,
        "phase4": phase4,
        "phase5": phase5,
        "phase4_inventory": phase4_inventory,
        "master_document_available": bool(master_doc),
        "vae_document_available": bool(vae_doc),
        "phase0_artifact_available": any(
            path.is_file()
            for path in ROOT.glob("phase0*")
            if path.suffix.lower() in {".json", ".md", ".txt", ".ipynb"}
        ),
    }


def variable_role(name: str, phase4_item: dict[str, Any]) -> dict[str, Any]:
    group = phase4_item.get("variable_family", phase4_item.get("group", ""))
    if name in ADMIN_METADATA:
        return {
            "role_group": "administrative/indexing",
            "causal_node": False,
            "temporal_status": (
                "ECG-time dependent; timestamp semantics do not establish treatment-specific baseline"
                if name == "ecg_time"
                else "administrative identifier"
            ),
            "causal_use": "Keep for linkage, time ordering, admission clustering, or repeated-patient dependence only; not an ordinary causal node.",
            "evidence_status": "VERIFIED in frozen Phase 1/4 role decisions",
        }
    if name == "Label_Troponin":
        return {
            "role_group": "outcome-label metadata",
            "causal_node": False,
            "temporal_status": "Categorical MI temporal cohort label; outcome definition for causal analysis remains unresolved",
            "causal_use": "Use as cohort/label metadata; not a separate causal node alongside the conceptual MI event.",
            "evidence_status": "VERIFIED as frozen label taxonomy; causal outcome suitability UNRESOLVED",
        }
    if name == "is_MI":
        return {
            "role_group": "candidate outcome measurement",
            "causal_node": False,
            "temporal_status": "Binary event indicator with unresolved causal outcome definition and horizon",
            "causal_use": f"Candidate observed measurement of {CAUSAL_OUTCOME_NODE}; do not include alongside Label_Troponin as another node.",
            "evidence_status": "VERIFIED as binary field; causal outcome definition UNRESOLVED",
        }
    if name in {"index_mi_time", "time_diff_hours"}:
        return {
            "role_group": "outcome/event timing metadata",
            "causal_node": False,
            "temporal_status": (
                "Event timestamp; validity/unique MI-time status is admission dependent"
                if name == "index_mi_time"
                else "MI-relative only for MI patients; control values use admission anchor/fallback"
            ),
            "causal_use": "Temporal audit/indexing only; never an ordinary causal node or universal ECG-to-MI clock.",
            "evidence_status": "VERIFIED in Phase 2 semantics; causal outcome horizon UNRESOLVED",
        }
    if name in DEMOGRAPHICS:
        return {
            "role_group": "demographic candidate",
            "causal_node": True,
            "temporal_status": "Historical/fixed patient attribute as recorded at admission",
            "causal_use": "Plausible upstream cause/proxy for treatment and MI; soft constraints only.",
            "evidence_status": "Observed in master; causal relations plausible, not established",
        }
    if name in HISTORY:
        description = {
            "diabetes": "ICD-coded diabetes from prior admissions",
            "hypertension": "ICD-coded hypertension from prior admissions",
            "ckd": "ICD-coded chronic kidney disease from prior admissions",
            "prior_mi": "MI in a previous admission",
        }[name]
        return {
            "role_group": "historical/comorbidity candidate",
            "causal_node": True,
            "temporal_status": f"Documented as prior-admission history ({description}); exact source-window audit remains limited",
            "causal_use": "Plausible historical cause/proxy for treatment, ECG state, and MI; soft constraints only.",
            "evidence_status": "Phase F documentation; exact feature construction code unavailable",
        }
    if name in TREATMENTS:
        if name.endswith("_before"):
            temporal = "Pre-admission exposure window per Phase F; exact medication start/administration time unknown"
            causal_use = "Potential historical exposure; not equivalent to assignment at an ECG-based time zero."
        elif name.endswith("_after"):
            temporal = "Post-discharge exposure per Phase F; downstream of the admission period"
            causal_use = "Downstream/post-discharge metadata; exclude from baseline exposure/covariate nodes."
        else:
            temporal = "In-hospital window per Phase F; order relative to ECG and MI unresolved"
            causal_use = "Potential acute/in-hospital exposure or downstream marker; not universally post-treatment."
        return {
            "role_group": "treatment/exposure",
            "causal_node": True,
            "temporal_status": temporal,
            "causal_use": causal_use,
            "evidence_status": "Phase F variable semantics; exact assignment time UNRESOLVED",
        }
    if name.startswith("z_ecg_"):
        return {
            "role_group": "ECG latent representation",
            "causal_node": True,
            "temporal_status": "ECG-time dependent; treatment-relative order UNRESOLVED",
            "causal_use": "Retain only within quarantined latent block; causal role not assigned.",
            "evidence_status": "Phase 5; provenance partial, outcome/treatment independence not verified",
        }
    if group == "B. Candidate ECG variables":
        return {
            "role_group": "engineered ECG representation",
            "causal_node": True,
            "temporal_status": "ECG-time dependent; treatment-relative order UNRESOLVED",
            "causal_use": "Retain as quarantined candidate ECG feature block; do not treat as established baseline.",
            "evidence_status": "Phase 3/4/5; temporal eligibility and upstream lineage unresolved",
        }
    if group == "C. Candidate latent ECG variables":
        return {
            "role_group": "ECG latent representation",
            "causal_node": True,
            "temporal_status": "ECG-time dependent; treatment-relative order UNRESOLVED",
            "causal_use": "Retain only within quarantined latent block; causal role not assigned.",
            "evidence_status": "Phase 5; provenance partial, outcome/treatment independence not verified",
        }
    return {
        "role_group": "unresolved/other",
        "causal_node": False,
        "temporal_status": "UNRESOLVED",
        "causal_use": "Exclude from discovery nodes pending explicit provenance review.",
        "evidence_status": "UNRESOLVED",
    }


def make_variable_inventory(inputs: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    inventory = []
    causal_nodes: list[str] = []
    for item in inputs["phase4_inventory"]:
        name = item["variable"]
        role = variable_role(name, item)
        inventory.append(
            {
                "name": name,
                "phase4_group": item.get("group"),
                **role,
                "phase3_eligibility": item.get("eligibility_classification"),
                "phase4_temporal_status": item.get("temporal_status"),
            }
        )
        if role["causal_node"]:
            causal_nodes.append(name)
    if CAUSAL_OUTCOME_NODE in causal_nodes:
        raise ValueError(f"{CAUSAL_OUTCOME_NODE} collides with source schema.")
    causal_nodes.append(CAUSAL_OUTCOME_NODE)
    return inventory, causal_nodes


def edge(
    source: str,
    target: str,
    constraint: str,
    evidence: str,
    confidence: str,
    reason: str,
    *,
    temporal_status: str = "established",
    evidence_status: str = "project_definition",
    treatment_specific: str | None = None,
    applicability: str = "unconditional",
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "constraint": constraint,
        "temporal_status": temporal_status,
        "evidence": evidence,
        "evidence_status": evidence_status,
        "confidence": confidence,
        "rationale": reason,
        "treatment_specific": treatment_specific,
        "applicability": applicability,
    }


def construct_background_edges() -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    upstream_candidates = DEMOGRAPHICS + HISTORY
    treatment_nodes = TREATMENTS

    for source in upstream_candidates:
        for target in treatment_nodes:
            edges.append(
                edge(
                    source,
                    target,
                    "PERMITTED",
                    "Demographic or recorded prior-admission history could inform prescribing/use; the dataset has no causal assignment evidence.",
                    "LOW",
                    "Plausible upstream relationship only; do not force the edge or infer confounding from association.",
                    temporal_status="partially established",
                    evidence_status="domain_plausibility_plus_project_temporal_description",
                )
            )
        edges.append(
            edge(
                source,
                CAUSAL_OUTCOME_NODE,
                "PERMITTED",
                "Demographics and chronic/prior history may precede and relate causally to a later MI event; frozen artifacts do not identify directed effects.",
                "LOW",
                "Soft background knowledge only; no effect estimates or predictive associations are used to orient edges.",
                temporal_status="partially established",
                evidence_status="domain_plausibility_plus_project_temporal_description",
            )
        )
        for feature_block in ("z_ecg_block", "engineered_ecg_block"):
            edges.append(
                edge(
                    source,
                    feature_block,
                    "PERMITTED",
                    "Chronic history or demographic attributes may be reflected in a later ECG measurement.",
                    "LOW",
                    "Potential relation is not verified; ECG timing and representation provenance are incomplete.",
                    temporal_status="unresolved",
                    evidence_status="domain_plausibility_only",
                )
            )

    for feature_block in ("z_ecg_block", "engineered_ecg_block"):
        edges.append(
            edge(
                CAUSAL_OUTCOME_NODE,
                feature_block,
                "FORBIDDEN",
                "If the selected ECG is verified to precede the same MI event by timestamp and the endpoint refers to that event.",
                "HIGH",
                "An event cannot cause a measurement already established to precede it. Current pooled ECG blocks include unresolved/mixed timing, so this prohibition is conditional and not globally applied.",
                temporal_status="conditional on verified pre-event selection",
                evidence_status="temporal_logic_conditional_on_phase1_timestamps",
                applicability="only_for_a_validated_pre_event_ECG_subgroup",
            )
        )

    for treatment in ("aspirin_before", "statin_before", "beta_blocker_before", "acei_before"):
        edges.append(
            edge(
                treatment,
                CAUSAL_OUTCOME_NODE,
                "UNKNOWN",
                "The pre-admission exposure window is documented, but the MI label may describe an event before or during admission and no causal follow-up horizon is defined.",
                "UNRESOLVED",
                "Treatment-to-incident-MI direction cannot be established until the event horizon and exposure status relative to that event are defined.",
                temporal_status="UNRESOLVED",
                evidence_status="Phase_F_window_semantics; Phase_2_outcome_unresolved",
                treatment_specific=treatment.removesuffix("_before"),
            )
        )
        edges.append(
            edge(
                treatment,
                "z_ecg_block",
                "PERMITTED",
                "A pre-admission medication could physiologically affect a subsequent ECG; exact medication history and ECG timing are unavailable.",
                "LOW",
                "The window is pre-admission and the ECG belongs to the current admission, so the exposure flag precedes the measurement by project semantics; actual medication initiation/dose and physiological effect are unknown.",
                temporal_status="partially established",
                evidence_status="domain_plausibility_only",
                treatment_specific=treatment.removesuffix("_before"),
            )
        )
        edges.append(
            edge(
                treatment,
                "engineered_ecg_block",
                "PERMITTED",
                "A pre-admission medication could physiologically affect a subsequent ECG; exact medication history and ECG timing are unavailable.",
                "LOW",
                "The window is pre-admission and the ECG belongs to the current admission, so the exposure flag precedes the measurement by project semantics; actual medication initiation/dose and physiological effect are unknown.",
                temporal_status="partially established",
                evidence_status="domain_plausibility_only",
                treatment_specific=treatment.removesuffix("_before"),
            )
        )
        for feature_block in ("z_ecg_block", "engineered_ecg_block"):
            edges.append(
                edge(
                    feature_block,
                    treatment,
                    "FORBIDDEN",
                    "The exposure flag is defined as medication use before admission; the ECG representation is measured during the current admission.",
                    "HIGH",
                    "A current-admission ECG cannot cause an already-recorded pre-admission medication-use flag. This is a temporal statement about these measured variables, not a claim that earlier ECGs never influenced care.",
                    temporal_status="temporally impossible",
                    evidence_status="Phase_F_pre_admission_window_semantics",
                    treatment_specific=treatment.removesuffix("_before"),
                )
            )

    for treatment in (
        "aspirin_during",
        "statin_during",
        "beta_blocker_during",
        "acei_during",
    ):
        for target in (CAUSAL_OUTCOME_NODE, "z_ecg_block", "engineered_ecg_block"):
            edges.append(
                edge(
                    treatment,
                    target,
                    "UNKNOWN",
                    "The indicator records in-hospital use but not when it began relative to the ECG or MI.",
                    "UNRESOLVED",
                    "Treatment-before-target and target-before-treatment orderings may both occur; variable name/window does not orient this edge.",
                    temporal_status="UNRESOLVED",
                    evidence_status="Phase_2_exact_times_unavailable",
                    treatment_specific=treatment.removesuffix("_during"),
                )
            )

    for treatment in ("statin_after",):
        edges.append(
            edge(
                treatment,
                "z_ecg_block",
                "FORBIDDEN",
                "Project definition states statin_after is post-discharge; an in-admission ECG precedes discharge.",
                "HIGH",
                "The later post-discharge medication flag cannot causally produce an already recorded in-admission ECG, although the ECG/event can influence later prescribing.",
                temporal_status="temporally impossible",
                evidence_status="explicit_project_window_definition",
            )
        )
        edges.append(
            edge(
                treatment,
                "engineered_ecg_block",
                "FORBIDDEN",
                "Project definition states statin_after is post-discharge; an in-admission ECG precedes discharge.",
                "HIGH",
                "The later post-discharge medication flag cannot causally produce an already recorded in-admission ECG.",
                temporal_status="temporally impossible",
                evidence_status="explicit_project_window_definition",
            )
        )
        edges.append(
            edge(
                treatment,
                CAUSAL_OUTCOME_NODE,
                "UNKNOWN",
                "Post-discharge treatment follows the admission period; outcome event timing/horizon is not defined.",
                "UNRESOLVED",
                "Cannot determine whether the target is the index MI already occurred during admission or a later event; do not impose a direction without outcome horizon.",
                temporal_status="UNRESOLVED",
                evidence_status="Phase_2_outcome_horizon_unresolved",
            )
        )
        for source in ("z_ecg_block", "engineered_ecg_block", CAUSAL_OUTCOME_NODE):
            edges.append(
                edge(
                    source,
                    treatment,
                    "PERMITTED",
                    "Post-discharge statin use can follow an in-admission ECG or MI event and may reflect subsequent clinical decisions.",
                    "LOW",
                    "Plausible downstream relationship only; exact post-discharge medication and event times are unavailable.",
                    temporal_status="partially established",
                    evidence_status="Phase_F_post_discharge_window_semantics",
                )
            )

    for treatment in ("vasopressor_during", "mech_vent_during"):
        for target in (CAUSAL_OUTCOME_NODE, "z_ecg_block", "engineered_ecg_block"):
            edges.append(
                edge(
                    treatment,
                    target,
                    "UNKNOWN",
                    "These are in-hospital supportive/severity-associated indicators without exact start times.",
                    "UNRESOLVED",
                    "Intervention may precede or follow ECG/MI and may respond to acute severity; neither direction is established.",
                    temporal_status="UNRESOLVED",
                    evidence_status="Phase_2_exact_times_unavailable",
                )
            )
        for source in (CAUSAL_OUTCOME_NODE, "z_ecg_block", "engineered_ecg_block"):
            edges.append(
                edge(
                    source,
                    treatment,
                    "UNKNOWN",
                    "MI, acute ECG state, or severity may precede and trigger a supportive intervention, but precise times are absent.",
                    "UNRESOLVED",
                    "The reverse ordering is possible and must not be replaced with a universal intervention-to-outcome arrow.",
                    temporal_status="UNRESOLVED",
                    evidence_status="Phase_2_exact_times_unavailable",
                )
            )

    for treatment in (
        "aspirin_during",
        "statin_during",
        "beta_blocker_during",
        "acei_during",
    ):
        for source in (CAUSAL_OUTCOME_NODE, "z_ecg_block", "engineered_ecg_block"):
            edges.append(
                edge(
                    source,
                    treatment,
                    "UNKNOWN",
                    "MI, ECG findings, or acute severity could precede and inform an in-hospital treatment decision.",
                    "UNRESOLVED",
                    "No exact medication or ECG timestamps establish treatment assignment order.",
                    temporal_status="UNRESOLVED",
                    evidence_status="Phase_2_exact_times_unavailable",
                    treatment_specific=treatment.removesuffix("_during"),
                )
            )

    for feature_block in ("z_ecg_block", "engineered_ecg_block"):
        for source, target in (
            (feature_block, CAUSAL_OUTCOME_NODE),
            (CAUSAL_OUTCOME_NODE, feature_block),
        ):
            edges.append(
                edge(
                    source,
                    target,
                    "UNKNOWN",
                    "Candidate ECGs may precede, coincide with, or follow a recorded MI timestamp; index ECG and outcome horizon are unresolved.",
                    "UNRESOLVED",
                    "Do not orient ECG/MI edges without a selected ECG, validated timestamp semantics, and incident-outcome definition.",
                    temporal_status="UNRESOLVED",
                    evidence_status="Phase_1_temporal_audit_and_Phase_2_outcome_audit",
                )
            )

    for source in TREATMENTS:
        for target in upstream_candidates:
            if source.endswith("_before") or source.endswith("_during") or source.endswith("_after"):
                temporally_later = (
                    source.endswith("_during") or source.endswith("_after")
                )
                if temporally_later:
                    edges.append(
                        edge(
                            source,
                            target,
                            "FORBIDDEN",
                            "Phase F defines these exposure indicators as during-admission or post-discharge; the target is demographics or recorded prior-admission history.",
                            "HIGH",
                            "A later exposure cannot cause immutable demographic attributes or a condition/history explicitly recorded from prior admissions.",
                            temporal_status="temporally impossible",
                            evidence_status="explicit_project_variable_definition",
                        )
                    )

    for source in ("MI_event",):
        for target in DEMOGRAPHICS + HISTORY:
            edges.append(
                edge(
                    source,
                    target,
                    "FORBIDDEN",
                    "anchor_age/sex_male are demographic attributes and Phase F describes comorbidity/prior_mi as prior-admission history.",
                    "HIGH",
                    "The current target MI event cannot cause demographic attributes or a history explicitly defined as prior to the current admission.",
                    temporal_status="temporally impossible",
                    evidence_status="explicit_project_variable_definition",
                )
            )
    contextual_targets = [
        *TREATMENTS,
        CAUSAL_OUTCOME_NODE,
        "z_ecg_block",
        "engineered_ecg_block",
    ]
    for target in contextual_targets:
        edges.append(
            edge(
                "acute_severity_unmeasured",
                target,
                "PERMITTED",
                "Acute clinical severity or indication could plausibly precede and influence this treatment, ECG state, or MI event.",
                "LOW",
                "This is an unmeasured contextual hypothesis, not a verified master variable or edge; it must not be passed to a discovery algorithm unless measured and operationalized.",
                temporal_status="unresolved",
                evidence_status="domain_plausibility_only_unmeasured_context",
                applicability="contextual_not_observed_graph_node",
            )
        )
    return edges


def treatment_question_templates() -> dict[str, Any]:
    result = {}
    historical_candidate_covariates = DEMOGRAPHICS + HISTORY
    for name, spec in TREATMENT_SPECS.items():
        exposure = spec["exposure"]
        result[name] = {
            "candidate_treatment_variable": exposure,
            "related_during_window_variable": spec["during"],
            "related_post_discharge_variable": spec["after"],
            "candidate_time_zero": "UNRESOLVED — exact medication assignment/administration time is unavailable.",
            "intended_contrast": spec["contrast"],
            "outcome": {
                "conceptual_node": CAUSAL_OUTCOME_NODE,
                "candidate_observed_fields": ["is_MI", "Label_Troponin"],
                "status": "UNRESOLVED — later causal outcome definition and event horizon required.",
            },
            "candidate_baseline_covariates": {
                "historical_candidates": historical_candidate_covariates,
                "ecg_features": "z_ecg_block and engineered_ecg_block only if an ECG is proven before this treatment-specific time zero; currently TEMPORALLY UNRESOLVED.",
                "eligibility_status": "Candidate schema only; no final adjustment set.",
            },
            "possible_post_treatment_variables": [
                spec["during"],
                "vasopressor_during",
                "mech_vent_during",
                "z_ecg_block",
                "engineered_ecg_block",
            ],
            "treatment_assignment_causes_to_consider": [
                *historical_candidate_covariates,
                "acute_severity_unmeasured",
                "prior_ecg_state_before_admission (not separately represented in the current selected-ECG block)",
            ],
            "outcome_causes_to_consider": [
                *historical_candidate_covariates,
                "z_ecg_block",
                "engineered_ecg_block",
                "acute_severity_unmeasured",
            ],
            "treatment_specific_temporal_requirements": [
                "Establish exact exposure/assignment time and exposure version for this treatment.",
                "Establish whether each candidate baseline variable, especially the selected ECG representation, is measured before assignment.",
                "Define whether the outcome is an incident MI after assignment or a cohort label reflecting an already-present/previous event.",
                "Resolve treatment overlap, contraindications, and time-varying treatment before defining the contrast.",
            ],
            "treatment_definition": spec["clinical_note"],
            "status": "TEMPLATE ONLY — no treatment, time zero, DAG, or causal effect selected.",
        }
    return result


def forbidden_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in edges if item["constraint"] == "FORBIDDEN"]


def unresolved_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in edges
        if item["constraint"] == "UNKNOWN"
        or item["temporal_status"].casefold() == "unresolved"
    ]


def hard_constraints(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in edges
        if item["constraint"] == "FORBIDDEN"
        and item["temporal_status"] in {
            "temporally impossible",
            "conditional on verified pre-event selection",
        }
        and item["confidence"] == "HIGH"
    ]


def soft_constraints(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in edges
        if item["constraint"] == "PERMITTED"
        or item["constraint"] == "REQUIRED"
    ]


def potential_confounder_assessment() -> list[dict[str, Any]]:
    result = []
    for treatment in TREATMENT_SPECS:
        for covariate in DEMOGRAPHICS + HISTORY:
            result.append(
                {
                    "treatment": treatment,
                    "candidate": covariate,
                    "classification": "plausible confounder candidate — not established",
                    "treatment_path": "Could plausibly affect treatment selection; project provides no causal assignment evidence.",
                    "outcome_path": "Could plausibly influence MI risk; no causal effect is established here.",
                    "temporal_status": "Historical/partially established; exact construction and analysis baseline need verification.",
                    "decision": "Soft constraint only; not a final adjustment variable.",
                    "confidence": "LOW",
                }
            )
        for candidate in ("z_ecg_block", "engineered_ecg_block"):
            result.append(
                {
                    "treatment": treatment,
                    "candidate": candidate,
                    "classification": "temporally unresolved; possible proxy/confounder or predictor only",
                    "treatment_path": "An ECG may inform treatment if acquired before assignment; order is unavailable.",
                    "outcome_path": "ECG morphology may be prognostic or proxy underlying state; predictive evidence alone is not causal evidence.",
                    "temporal_status": "UNRESOLVED",
                    "decision": "No confounder designation; block remains quarantined.",
                    "confidence": "UNRESOLVED",
                }
            )
    return result


def mediator_candidates() -> list[dict[str, Any]]:
    return [
        {
            "treatment": treatment,
            "candidate_mediator": variable,
            "possible_structure": f"{TREATMENT_SPECS[treatment]['exposure']} → {variable} → MI_event",
            "temporal_requirement": "Treatment assignment precedes the mediator, which precedes the incident MI outcome.",
            "evidence_available": "Window-coded treatment or repeated ECG representation exists.",
            "evidence_missing": "Exact treatment, ECG, and outcome ordering; treatment-specific time zero and incident outcome horizon.",
            "status": "POSSIBLE BUT UNRESOLVED",
            "warning": "Biological plausibility alone does not establish mediation.",
        }
        for treatment in TREATMENT_SPECS
        for variable in (
            TREATMENT_SPECS[treatment]["during"],
            "z_ecg_block",
            "engineered_ecg_block",
        )
    ]


def collider_candidates() -> list[dict[str, Any]]:
    structures = [
        (
            "z_ecg_block / engineered_ecg_block",
            ["treatment (if before ECG)", "acute severity / underlying disease"],
            "Treatment and acute process both precede ECG acquisition.",
        ),
        (
            "acute in-hospital treatment indicators",
            ["MI event / acute severity", "baseline history or clinical state"],
            "Multiple causes precede the treatment indicator; exact treatment time and indication are observed.",
        ),
        (
            "vasopressor_during",
            ["acute severity", "hemodynamic condition / treatment decision"],
            "Both causes precede supportive intervention; exact timing and severity variables are measured.",
        ),
        (
            "mech_vent_during",
            ["acute severity", "respiratory status / treatment decision"],
            "Both causes precede ventilation; exact timing and clinical indication are measured.",
        ),
    ]
    return [
        {
            "candidate": node,
            "possible_parents": parents,
            "temporal_requirement": requirement,
            "conditioning_risk": "Conditioning could open a noncausal path if this collider structure holds.",
            "current_structure_identified": False,
            "reason_unresolved": "Current data lack sufficient exact treatment timing and/or full acute-severity/indication measurements.",
            "status": "POTENTIAL ONLY — do not label as an established collider.",
        }
        for node, parents, requirement in structures
    ]


def temporal_hierarchy() -> list[dict[str, Any]]:
    return [
        {
            "category": "Clearly historical / immutable",
            "variables": DEMOGRAPHICS,
            "position": "Partially established at admission; not causes of earlier attributes or prior events.",
            "causal_graph_handling": "Observed candidate nodes; only soft outgoing relationships.",
        },
        {
            "category": "Prior-admission history",
            "variables": HISTORY,
            "position": "Phase F documents previous admissions; exact feature-source construction not locally available.",
            "causal_graph_handling": "Candidate observed nodes; prior-to-current-event direction can prohibit current event → history, but no incoming/outgoing biological effect is forced.",
        },
        {
            "category": "ECG-time dependent",
            "variables": ["z_ecg_1 … z_ecg_64", "95 engineered ECG features"],
            "position": "ECG timestamp identifies recording time; relative to treatment assignment unresolved.",
            "causal_graph_handling": "Quarantined ECG blocks; no baseline status inferred from first ECG or MI-time ordering.",
        },
        {
            "category": "Treatment-window dependent",
            "variables": TREATMENTS,
            "position": "Pre-admission, in-hospital, or post-discharge windows per Phase F; exact assignment/administration times unavailable.",
            "causal_graph_handling": "Candidate exposures, acute variables, or downstream metadata as specified per treatment question; `_during` not universally post-treatment.",
        },
        {
            "category": "Outcome/event dependent",
            "variables": OUTCOME_METADATA,
            "position": "Categorical label and binary MI flag available; causal endpoint and horizon unresolved. index_mi_time is event timing; time_diff_hours has MI/control-specific semantics.",
            "causal_graph_handling": "Outcome metadata; do not include as ordinary covariates. Use one future endpoint definition, not redundant label/time nodes.",
        },
        {
            "category": "Administrative/indexing",
            "variables": ADMIN_METADATA,
            "position": "IDs are noncausal keys; ecg_time is measurement timestamp with treatment-relative order unresolved.",
            "causal_graph_handling": "Exclude IDs/time from graph nodes; retain for joins, split/unit handling, and temporal audits.",
        },
        {
            "category": "Unmeasured acute severity/context",
            "variables": ["acute_severity_unmeasured (conceptual; not a master column)"],
            "position": "Not measured as an identified variable in the audited master schema.",
            "causal_graph_handling": "Context for possible confounding/collider structures only; do not pass as an observed node.",
        },
    ]


def build_results(inputs: dict[str, Any]) -> dict[str, Any]:
    inventory, _causal_nodes = make_variable_inventory(inputs)
    edges = construct_background_edges()
    treatment_templates = treatment_question_templates()
    phase2 = inputs["phase2"]
    phase3 = inputs["phase3"]
    phase4 = inputs["phase4"]
    phase5 = inputs["phase5"]
    return {
        "phase": "Phase 6 — Background Knowledge and Causal Constraints",
        "objective": "Create a domain-informed, temporally aware, treatment-specific constraint specification for later discovery; do not discover a DAG.",
        "frozen_assumptions": {
            "causal_unit": "Admission-level observational unit.",
            "patient_dependence": "Retain SubjectID for repeated-patient dependence/clustering; it is not an ordinary causal node.",
            "repeated_ecgs": "Repeated ECGs within an admission do not create independent causal units.",
            "phase1_conclusion": "ECG time is not established as causal time zero; index ECG selection remains unresolved pending treatment timing.",
            "phase2_treatment_time_zero": "UNRESOLVED for aspirin, statin, beta blocker, and ACE inhibitor.",
            "phase2_outcome_definition": "UNRESOLVED — requires later causal outcome definition/audit.",
            "phase4_final_causal_discovery_matrix": "Not approved; index ECG, treatment-specific time zero, outcome definition, and preprocessing provenance remain unresolved.",
            "phase5_z_ecg": "Causal role unresolved; not currently a confounder or baseline adjustment variable.",
            "phase0": (
                "No dedicated Phase 0 file was found in the project root; estimand/problem-definition wording remains unverified."
            ),
            "frozen_phase_inputs_used": {
                "phase1": str(PHASE1_PATH),
                "phase2": str(PHASE2_PATH),
                "phase3": str(PHASE3_PATH),
                "phase4": str(PHASE4_PATH),
                "phase5": str(PHASE5_PATH),
            },
            "phase2_time_diff_semantics": phase2.get("outcome_summary", {}).get(
                "time_diff_hours_semantics",
                phase2.get("outcome_audit", {}).get("time_diff_hours_semantics"),
            ),
            "phase3_inventory_count": len(phase3.get("complete_variable_inventory", [])),
            "phase4_inventory_count": len(inputs["phase4_inventory"]),
            "phase5_z_ecg_linkage_finding": phase5.get(
                "waveform_embedding_study_id_linkage", {}
            ).get("linkage_interpretation"),
        },
        "variable_roles": inventory,
        "variable_role_summary": {
            "total_source_variables": len(inventory),
            "observed_causal_candidate_nodes": [
                variable["name"] for variable in inventory if variable["causal_node"]
            ],
            "conceptual_outcome_node": {
                "name": CAUSAL_OUTCOME_NODE,
                "candidate_measurement": "is_MI",
                "alternate_cohort_label": "Label_Troponin",
                "status": "Candidate endpoint only; outcome definition/horizon remain unresolved.",
            },
            "administrative_excluded_variables": [
                item["name"] for item in inventory if item["role_group"] == "administrative/indexing"
            ],
            "outcome_metadata_not_graph_nodes": [
                item["name"]
                for item in inventory
                if item["role_group"]
                in {
                    "outcome-label metadata",
                    "candidate outcome measurement",
                    "outcome/event timing metadata",
                }
            ],
            "high_dimensional_blocks": {
                "z_ecg_block": [f"z_ecg_{index}" for index in range(1, 65)],
                "engineered_ecg_block": [
                    item["name"]
                    for item in inventory
                    if item["role_group"] == "engineered ECG representation"
                ],
                "graph_encoding_rule": (
                    "A future discovery run must choose block-level or individual-dimension nodes, not both. "
                    "Block endpoints in constraints are selectors requiring explicit expansion; they are not literal master columns."
                ),
            },
            "unobserved_context_nodes_not_in_graph": ["acute_severity_unmeasured"],
        },
        "nodes": {
            "observed_causal_candidate_nodes": [
                variable["name"] for variable in inventory if variable["causal_node"]
            ],
            "candidate_outcome_node": {
                "name": CAUSAL_OUTCOME_NODE,
                "candidate_measurement": "is_MI",
                "alternate_cohort_label": "Label_Troponin",
                "status": "Outcome definition/horizon unresolved.",
            },
            "administrative_and_time_fields_excluded": [
                item["name"]
                for item in inventory
                if item["role_group"] == "administrative/indexing"
            ],
            "outcome_and_event_time_metadata_excluded": [
                item["name"]
                for item in inventory
                if item["role_group"]
                in {
                    "outcome-label metadata",
                    "candidate outcome measurement",
                    "outcome/event timing metadata",
                }
            ],
            "block_selectors": {
                "z_ecg_block": [f"z_ecg_{index}" for index in range(1, 65)],
                "engineered_ecg_block": [
                    item["name"]
                    for item in inventory
                    if item["role_group"] == "engineered ECG representation"
                ],
                "not_literal_master_columns": True,
                "future_expansion_rule": (
                    "Choose either each dimension/feature or its block representation; do not include both encodings."
                ),
            },
            "unmeasured_context_not_an_observed_node": ["acute_severity_unmeasured"],
        },
        "treatment_specific_causal_questions": treatment_templates,
        "treatment_specific_constraints": {
            treatment: {
                "time_zero": details["candidate_time_zero"],
                "exposure": details["candidate_treatment_variable"],
                "candidate_baseline_covariates": details[
                    "candidate_baseline_covariates"
                ],
                "temporally_unresolved": details[
                    "treatment_specific_temporal_requirements"
                ],
                "possible_post_treatment_variables": details[
                    "possible_post_treatment_variables"
                ],
            }
            for treatment, details in treatment_templates.items()
        },
        "background_causal_knowledge": edges,
        "constraint_sets": {
            "required_edges": [
                item for item in edges if item["constraint"] == "REQUIRED"
            ],
            "forbidden_edges": forbidden_edges(edges),
            "permitted_edges": [
                item for item in edges if item["constraint"] == "PERMITTED"
            ],
            "unknown_edges": [item for item in edges if item["constraint"] == "UNKNOWN"],
            "temporally_unresolved_edges": unresolved_edges(edges),
            "hard_constraints": hard_constraints(edges),
            "soft_constraints": soft_constraints(edges),
        },
        "required_edges": [
            item for item in edges if item["constraint"] == "REQUIRED"
        ],
        "forbidden_edges": forbidden_edges(edges),
        "permitted_edges": [
            item for item in edges if item["constraint"] == "PERMITTED"
        ],
        "temporally_unresolved_edges": unresolved_edges(edges),
        "hard_constraints": hard_constraints(edges),
        "soft_constraints": soft_constraints(edges),
        "temporal_hierarchy": temporal_hierarchy(),
        "potential_confounders_by_treatment": potential_confounder_assessment(),
        "potential_mediators": mediator_candidates(),
        "potential_colliders": collider_candidates(),
        "treatment_specific_constraint_matrices": {
            treatment: {
                "candidate_exposure": spec["exposure"],
                "time_zero": "UNRESOLVED",
                "candidate_soft_parent_edges": [
                    f"{candidate} -> {spec['exposure']}"
                    for candidate in DEMOGRAPHICS + HISTORY + ["acute_severity_unmeasured"]
                ],
                "candidate_outcome_relationships": [
                    {
                        "source": candidate,
                        "target": CAUSAL_OUTCOME_NODE,
                        "constraint": (
                            "PERMITTED"
                            if candidate in DEMOGRAPHICS + HISTORY
                            else "UNKNOWN"
                        ),
                        "rationale": (
                            "Historical candidates may precede and influence MI; soft hypothesis only."
                            if candidate in DEMOGRAPHICS + HISTORY
                            else "ECG timing relative to treatment/outcome is unresolved."
                        ),
                    }
                    for candidate in DEMOGRAPHICS
                    + HISTORY
                    + ["z_ecg_block", "engineered_ecg_block"]
                ],
                    "temporally_unresolved_edges": [
                        f"{spec['during']} <-> MI_event",
                        f"{spec['during']} <-> MI_event",
                        f"{spec['during']} <-> z_ecg_block",
                        f"{spec['during']} <-> engineered_ecg_block",
                ],
                "potential_post_treatment_variables": [
                    spec["during"],
                    "vasopressor_during",
                    "mech_vent_during",
                    "z_ecg_block",
                    "engineered_ecg_block",
                ],
                "no_final_dag_or_adjustment_set": True,
            }
            for treatment, spec in TREATMENT_SPECS.items()
        },
        "methodological_safeguards": {
            "biological_plausibility_is_causal_proof": False,
            "correlation_or_prediction_oriented_edges": False,
            "before_mi_means_before_treatment": False,
            "first_ecg_means_baseline": False,
            "admission_flag_means_exact_assignment": False,
            "z_ecg_assumed_confounder_or_baseline": False,
            "during_window_universally_post_treatment": False,
            "unsupervised_vae_assumed_leakage_free": False,
            "domain_knowledge_treated_as_unquestionable_truth": False,
            "one_universal_treatment_dag_used": False,
        },
        "phase7_readiness": {
            "constraint_specification_complete": True,
            "causal_discovery_structurally_constrained": False,
            "reason": (
                "The specification provides only cautious candidate constraints; data readiness is still blocked by "
                "treatment-specific time zero, outcome definition/horizon, final ECG eligibility, and Phase 5 provenance."
            ),
            "causal_discovery_run": False,
            "dag_constructed": False,
            "adjustment_set_selected": False,
            "ate_cate_estimated": False,
        },
        "phase7_handoff": [
            "Select and justify one treatment-specific estimand and obtain its exact treatment assignment/administration time.",
            "Define an incident MI outcome and follow-up horizon suitable for that treatment question; do not use both Label_Troponin and is_MI as separate outcome nodes.",
            "Establish ECG and covariate timing relative to each treatment-specific time zero; Rule A and MI-time-dependent Rules B/C are not automatically valid baselines.",
            "Resolve Phase 5 VAE training/checkpoint/preprocessing and leakage provenance before including z_ecg.",
            "At discovery setup, exclude identifiers, timestamps, outcome timing, and post-discharge flags from ordinary nodes; preserve SubjectID only for dependence handling.",
            "Expand block-level ECG constraints only after choosing block nodes or individual dimensions; never duplicate both encodings.",
            "Use listed soft constraints as review prompts, not algorithmically forced edges; apply only hard temporal exclusions supported by project definitions.",
            "Do not run discovery until the Phase 4 matrix and treatment-specific outcome/time-zero blockers are resolved.",
        ],
    }


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += [
        "| "
        + " | ".join(
            str(value).replace("|", "\\|").replace("\n", " ").replace("\r", "")
            for value in row
        )
        + " |"
        for row in rows
    ]
    return "\n".join(lines)


def report_markdown(results: dict[str, Any]) -> str:
    inventory_rows = [
        [
            item["name"],
            item["role_group"],
            item["causal_node"],
            item["temporal_status"],
            item["causal_use"],
            item["evidence_status"],
        ]
        for item in results["variable_roles"]
    ]
    background_rows = [
        [
            item["source"],
            item["target"],
            item["constraint"],
            item["temporal_status"],
            item["evidence_status"],
            item["confidence"],
            item["rationale"],
        ]
        for item in results["background_causal_knowledge"]
    ]
    treatment_rows = [
        [
            name,
            spec["candidate_treatment_variable"],
            spec["candidate_time_zero"],
            spec["intended_contrast"],
            spec["outcome"]["status"],
            spec["candidate_baseline_covariates"]["eligibility_status"],
        ]
        for name, spec in results["treatment_specific_causal_questions"].items()
    ]
    temporal_rows = [
        [
            item["category"],
            ", ".join(item["variables"]),
            item["position"],
            item["causal_graph_handling"],
        ]
        for item in results["temporal_hierarchy"]
    ]
    confounder_rows = [
        [
            item["treatment"],
            item["candidate"],
            item["classification"],
            item["temporal_status"],
            item["decision"],
        ]
        for item in results["potential_confounders_by_treatment"]
    ]
    mediator_rows = [
        [
            item["treatment"],
            item["candidate_mediator"],
            item["possible_structure"],
            item["temporal_requirement"],
            item["status"],
        ]
        for item in results["potential_mediators"]
    ]
    collider_rows = [
        [
            item["candidate"],
            ", ".join(item["possible_parents"]),
            item["temporal_requirement"],
            item["conditioning_risk"],
            item["status"],
        ]
        for item in results["potential_colliders"]
    ]
    hard = results["constraint_sets"]["hard_constraints"]
    soft = results["constraint_sets"]["soft_constraints"]
    forbidden = results["constraint_sets"]["forbidden_edges"]
    input_lines = [
        f"- Phase {phase} JSON: `{path}` — available."
        for phase, path in (
            ("1", PHASE1_PATH),
            ("2", PHASE2_PATH),
            ("3", PHASE3_PATH),
            ("4", PHASE4_PATH),
            ("5", PHASE5_PATH),
        )
    ]
    phase2_status = results["frozen_assumptions"]["phase2_outcome_definition"].rstrip(".")
    return "\n".join(
        [
            "# Phase 6 — Background Knowledge and Causal Constraints",
            "",
            "## A. Objective",
            "",
            "Build a domain-informed, temporally aware, treatment-specific constraint specification for a later discovery stage. This is background knowledge, not a statistically discovered DAG, final DAG, adjustment set, treatment choice, or causal conclusion.",
            "",
            "## B. Inputs and frozen assumptions",
            "",
            *input_lines,
            "- Phase F master schema and VAE embedding documentation: available locally; documentation is distinguished from executable provenance.",
            "- Phase 0 dedicated output: not found locally; estimand/problem-definition wording was not independently re-audited.",
            "",
            "Causal unit remains **admission-level**. Repeated ECGs are not independent causal units; `SubjectID` is retained for patient dependence, not as an ordinary covariate. The Phase 1/4 conclusion remains frozen: ECG time is not established as causal time zero and index ECG selection is unresolved. Treatment-specific time zero is **UNRESOLVED**. Outcome status: " + phase2_status + ". `time_diff_hours` is ECG minus MI time only for MI patients; for controls it uses an admission-time anchor/fallback and is not MI-relative. Phase 5 leaves z_ecg causal role and provenance unresolved.",
            "",
            "## C. Variable-role inventory",
            "",
            "All source fields from the Phase 4 inventory are enumerated below (184 fields). `MI_event` is a conceptual candidate endpoint, not an extra source column. The future graph should use `is_MI` or another newly justified endpoint definition as its measurement, not also represent `Label_Troponin` as a second outcome node. Identifiers and time fields are excluded from ordinary causal nodes.",
            "",
            md_table(["Variable", "Role group", "Causal node?", "Temporal status", "Causal use", "Evidence status"], inventory_rows),
            "",
            "High-dimensional ECG handling: `z_ecg_block` contains 64 dimensions and `engineered_ecg_block` contains the 95 named engineered measurements. A future graph must select block-level or individual-dimension nodes—not both. Block labels in this report/specification are selectors, not master columns.",
            "",
            "## D. Treatment-specific causal questions",
            "",
            md_table(["Treatment", "Candidate exposure", "Candidate time zero", "Intended contrast", "Outcome status", "Baseline status"], treatment_rows),
            "",
            "Each treatment is a distinct question template; none defines a valid assignment intervention today. Candidate historical variables are `anchor_age`, `sex_male`, `diabetes`, `hypertension`, `ckd`, and `prior_mi`. ECG blocks can be baseline candidates only if pre-assignment timing is demonstrated. During-window treatments, vasopressor, ventilation, and ECGs may be post-treatment depending on exact times.",
            "",
            "## E. Background causal knowledge",
            "",
            "The edge table includes cautious plausible directions and temporal exclusions. `REQUIRED` is empty: no causal edge is forced by the available evidence. Permitted edges are suggestions for later interpretation, not restrictions that an algorithm must orient. Each edge includes evidence status, confidence, and rationale.",
            "",
            md_table(["Source", "Target", "Constraint", "Temporal status", "Evidence", "Confidence", "Reason"], background_rows),
            "",
            "No edge was oriented using correlation, regression coefficients, feature importance, latent correlations, or prediction.",
            "",
            "## F. Temporal constraints",
            "",
            md_table(["Temporal category", "Variables", "Position", "Graph handling"], temporal_rows),
            "",
            "For the four pre-admission flags, the documented window places use before an ECG from the current admission; a current-admission ECG therefore cannot cause that pre-admission flag. However, initiation time, dose, continuity, treatment assignment, and physiological effects are not established. In-hospital `*_during` flags may precede or follow a given ECG/MI, so both treatment→ECG and ECG→treatment remain unresolved for those variables. Post-discharge statin cannot cause an in-admission ECG. Before-MI is not before-treatment, and first ECG is not automatically baseline ECG.",
            "",
            "## G. Hard constraints",
            "",
            f"Hard list contains **{len(hard)}** high-confidence temporal prohibitions, including conditional rules. Conditional entries apply only after the specified pre-event ECG subgroup is verified; they are not unconditional constraints on the current pooled ECG block. These are prohibitions only; no biologically plausible edge is enforced. Each entry appears in the JSON `constraint_sets.hard_constraints` and `forbidden_edges`.",
            "",
            md_table(["Forbidden source → target", "Evidence", "Confidence", "Reason"], [[f'{item["source"]} → {item["target"]}', item["evidence"], item["confidence"], item["rationale"]] for item in hard]),
            "",
            "No REQUIRED causal edge is specified.",
            "",
            "## H. Soft constraints",
            "",
            f"There are **{len(soft)}** permitted relationship candidates. They remain soft; do not pass them as required arrows. Examples include historical candidate → treatment and historical candidate → MI outcome, each low-confidence and plausibility-based. Some `acute_severity_unmeasured` entries are context hypotheses only, not observed nodes and not directly usable by a discovery algorithm.",
            "",
            "## I. Forbidden edges",
            "",
            "The explicitly forbidden directions are supported by project temporal construction: current MI event → demographic attributes/prior-admission history; during-admission or post-discharge treatment flags → immutable demographic or prior-admission history; and post-discharge statin → ECG recorded during the admission. These restrictions do not imply the variables are statistically independent or prohibit the reverse direction. `MI_event` here is a later/current event endpoint, not an arbitrary categorical row label.",
            "",
            md_table(["Source", "Target", "Temporal status", "Evidence status", "Reason"], [[item["source"], item["target"], item["temporal_status"], item["evidence_status"], item["rationale"]] for item in forbidden]),
            "",
            "Causal direction forbidden is not statistical association forbidden. Association may remain due to common causes, selection, or measurement construction.",
            "",
            "## J. Potential confounders",
            "",
            md_table(["Treatment", "Candidate", "Classification", "Temporal status", "Decision"], confounder_rows),
            "",
            "Demographics/history are plausible common causes only as hypotheses. An ECG block is temporally unresolved and may instead be proxy, prognostic-only, mediator, collider, or predictive-only. No candidate is declared a definitive confounder.",
            "",
            "## K. Potential mediators",
            "",
            md_table(["Treatment", "Candidate mediator", "Possible structure", "Temporal requirement", "Status"], mediator_rows),
            "",
            "A variable cannot be declared a mediator merely because the mechanism is biologically plausible; observed treatment → mediator → incident outcome order must be established.",
            "",
            "## L. Potential colliders",
            "",
            md_table(["Candidate", "Possible parents", "Temporal requirement", "Conditioning risk", "Status"], collider_rows),
            "",
            "No collider structure is established. In particular, conditioning on acute ECG/treatment/supportive interventions could induce bias only if the described multiple-parent structure and ordering hold; current data cannot verify them.",
            "",
            "## M. `z_ecg` causal-role implications",
            "",
            "Keep baseline-state → treatment and baseline-state → MI as permitted hypotheses conditional on pre-treatment ECG. Treatment → ECG and ECG → treatment both remain temporally unresolved at admission level; acute severity may affect ECG, treatment, and MI but is not measured as an identified master variable. The Phase 5 low latent-dimension correlations do not imply causal independence. Do not treat z_ecg as a confounder or baseline covariate by default.",
            "",
            "## N. Treatment-specific constraint matrices",
            "",
            "Four separate template matrices are in `treatment_specific_constraint_matrices` in the JSON. They expose candidate soft parents/outcome causes, treatment-specific unresolved temporal relationships, and potentially downstream variables. They do not represent final DAGs.",
            "",
            "## O. Discovery handoff",
            "",
            *[f"{index}. {item}" for index, item in enumerate(results["phase7_handoff"], 1)],
            "",
            "## P. Limitations",
            "",
            "- Phase 0 dedicated output not available locally; no estimand text has been invented.",
            "- Phase 2 outcome definition and event horizon remain unresolved; `Label_Troponin` and `is_MI` are not separate graph outcomes.",
            "- Exact medication assignment times are absent; no treatment-specific time zero or definitive ECG baseline can be set.",
            "- Prior-history construction is documented, but source SQL/code is unavailable.",
            "- VAE training/checkpoint/preprocessing lineage and label/treatment independence are unverified in Phase 5.",
            "- Acute severity/clinical indication are not represented by verified master variables; they appear only as unmeasured context.",
            "- Soft domain constraints could be wrong or cohort-specific; they must not force the final graph.",
            "- No statistical discovery, DAG construction, effect estimation, or adjustment-set selection was performed.",
            "",
            "## Q. Phase 6 Decision Record",
            "",
            "1. **Causal unit**: Admission-level; patient dependence retained through `SubjectID`; repeated ECGs do not become independent units.",
            "2. **Treatments considered**: Aspirin, statin, beta blocker, ACE inhibitor; treatment-specific templates are separate.",
            "3. **Treatment-specific time zero**: UNRESOLVED for each; exact assignment/administration times unavailable.",
            "4. **Outcome definition used for constraint construction**: Conceptual `MI_event`, candidate measurement `is_MI`, cohort-label metadata `Label_Troponin`; final causal endpoint/horizon UNRESOLVED.",
            "5. **Historical variables**: `anchor_age`, `sex_male`, `diabetes`, `hypertension`, `ckd`, `prior_mi`; history windows per project documentation, source construction incompletely verified.",
            "6. **Potential baseline variables**: Historical candidates; ECG features and z_ecg only if demonstrated before treatment-specific assignment. None finalized.",
            "7. **Potential downstream variables**: `statin_after`; potentially each `*_during`, `vasopressor_during`, `mech_vent_during`, and ECG blocks depending on treatment-specific ordering.",
            "8. **Potential mediators**: During-window treatment variables and ECG blocks, conditional on treatment → variable → incident MI ordering; unresolved.",
            "9. **Potential colliders**: Acute ECG blocks, acute treatments, vasopressor and mechanical ventilation may be colliders under specified multiple-parent structures; none established.",
            "10. **Potential confounders**: Demographics/history are plausible candidates; ECG blocks are temporally unresolved possible proxies/confounders or predictors only. No definitive confounder.",
            "11. **Hard causal constraints**: Only high-confidence temporal impossibilities from explicit variable windows/history semantics; zero required causal edges.",
            "12. **Soft causal constraints**: Low-confidence plausible historical-to-treatment/outcome and chronic-state-to-ECG relationships; not algorithmically enforced.",
            "13. **Forbidden edges**: Current MI event → immutable demographics/prior history; later during/post-discharge treatment → those past variables; statin_after → in-admission ECG.",
            "14. **Temporally unresolved relationships**: Treatment ↔ ECG, during treatment ↔ ECG/MI, outcome event horizon ↔ post-discharge statin, and acute severity parentage.",
            "15. **`z_ecg` status**: Role unresolved; not currently established as confounder or baseline adjustment variable; remains quarantined.",
            "16. **Treatment-specific differences**: Four separate candidate exposures and windows; statin uniquely has a post-discharge indicator; no universal treatment DAG.",
            "17. **Whether one universal DAG is permitted**: NO — each treatment and time zero requires its own causal question/temporal constraints.",
            "18. **Whether causal discovery is now structurally constrained**: NOT READY — cautious constraint specification exists, but blockers prevent a valid discovery input.",
            "19. **Remaining blockers**: Estimand/Phase 0 confirmation; treatment assignment timestamps/time zero; outcome definition/horizon; index ECG eligibility; VAE and feature provenance; acute severity/indication measurement.",
            "20. **Phase 7 handoff**: Resolve treatment-specific estimand, exact assignment and event times, outcome horizon, eligible baseline covariates/ECG, and preprocessing provenance; then map this constraint spec without forcing soft edges.",
            "",
        ]
    )


def notebook_document() -> dict[str, Any]:
    source = [
        "from phase6_background_causal_constraints import build_results, phase_inputs, write_outputs\n",
        "inputs = phase_inputs()\n",
        "results = build_results(inputs)\n",
        "write_outputs(results)\n",
        "results['constraint_sets']\n",
    ]
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 6 — Background Knowledge and Causal Constraints\n",
                "\n",
                "This notebook assembles a machine-readable, treatment-specific constraint specification from frozen Phases 1–5. It does not run causal discovery, construct a DAG, choose treatment/time zero, or estimate effects.\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Load frozen inputs and create role/constraint inventory\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": source,
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Treatment-specific questions and hard/soft constraints\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "results['treatment_specific_causal_questions'], results['constraint_sets']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Temporal hierarchy, confounders, mediators, colliders, and handoff\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "results['temporal_hierarchy'], results['potential_confounders_by_treatment'], results['potential_mediators'], results['potential_colliders'], results['phase7_handoff']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "The report and JSON specification are written beside this notebook. No discovery algorithm is invoked.\n",
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


def write_outputs(results: dict[str, Any]) -> None:
    JSON_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(report_markdown(results), encoding="utf-8")
    NOTEBOOK_PATH.write_text(
        json.dumps(notebook_document(), indent=1, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    inputs = phase_inputs()
    results = build_results(inputs)
    write_outputs(results)
    print(
        json.dumps(
            {
                "source_variable_count": results["variable_role_summary"][
                    "total_source_variables"
                ],
                "causal_candidate_nodes": len(
                    results["variable_role_summary"]["observed_causal_candidate_nodes"]
                ),
                "background_edge_records": len(
                    results["background_causal_knowledge"]
                ),
                "hard_forbidden_edges": len(
                    results["constraint_sets"]["hard_constraints"]
                ),
                "soft_relationships": len(results["constraint_sets"]["soft_constraints"]),
                "required_edges": len(results["constraint_sets"]["required_edges"]),
                "treatments": list(results["treatment_specific_causal_questions"]),
                "outputs": [str(JSON_PATH), str(NOTEBOOK_PATH), str(REPORT_PATH)],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
