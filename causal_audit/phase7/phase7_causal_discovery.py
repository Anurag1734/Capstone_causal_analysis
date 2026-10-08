from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PHASE_INPUTS = {
    "phase1": ROOT / "phase1_audit_results.json",
    "phase2": ROOT / "phase2_audit_results.json",
    "phase3": ROOT / "phase3_audit_results.json",
    "phase4": ROOT / "phase4_discovery_ready_dataset_results.json",
    "phase5": ROOT / "phase5_z_ecg_causal_role_audit_results.json",
    "phase6": ROOT / "phase6_background_causal_constraints_results.json",
}
MASTER_DOC = ROOT / "docs" / "Phase F — Master Dataset.md"
JSON_PATH = ROOT / "phase7_causal_discovery_results.json"
NOTEBOOK_PATH = ROOT / "phase7_causal_discovery.ipynb"
REPORT_PATH = ROOT / "phase7_causal_discovery_report.md"

TREATMENTS = {
    "aspirin": {
        "exposure": "aspirin_before",
        "acute": "aspirin_during",
        "additional": [],
        "positivity_key": "aspirin_before",
    },
    "statin": {
        "exposure": "statin_before",
        "acute": "statin_during",
        "additional": ["statin_after"],
        "positivity_key": "statin_before",
    },
    "beta_blocker": {
        "exposure": "beta_blocker_before",
        "acute": "beta_blocker_during",
        "additional": [],
        "positivity_key": "beta_blocker_before",
    },
    "acei": {
        "exposure": "acei_before",
        "acute": "acei_during",
        "additional": [],
        "positivity_key": "acei_before",
    },
}

CLINICAL = [
    "anchor_age",
    "sex_male",
    "diabetes",
    "hypertension",
    "ckd",
    "prior_mi",
]
OUTCOME_METADATA = [
    "Label_Troponin",
    "index_mi_time",
    "time_diff_hours",
]
ECG_FAMILIES = {
    "engineered": "B. Candidate ECG variables",
    "latent": "C. Candidate latent ECG variables",
}


def load_inputs() -> dict[str, Any]:
    inputs = {}
    for name, path in PHASE_INPUTS.items():
        if not path.is_file():
            raise FileNotFoundError(f"Frozen Phase {name[5:]} artifact is missing: {path}")
        inputs[name] = json.loads(path.read_text(encoding="utf-8"))
    if not MASTER_DOC.is_file():
        raise FileNotFoundError(f"Master dataset documentation is missing: {MASTER_DOC}")
    inputs["master_document_text"] = MASTER_DOC.read_text(encoding="utf-8")
    return inputs


def readiness_item(
    item_id: str,
    status: str,
    finding: str,
    evidence: str,
    blocks_discovery: bool,
    treatment_specific: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "status": status,
        "finding": finding,
        "evidence": evidence,
        "blocks_causal_discovery": blocks_discovery,
        "treatment_specific_status": treatment_specific or {},
    }


def candidate_missingness(
    phase4: dict[str, Any],
    treatment: str,
) -> dict[str, Any]:
    inventory = {
        item["variable"]: item
        for item in phase4["complete_variable_inventory"]
    }
    candidate_names = [
        *CLINICAL,
        treatment,
        "is_MI",
        *OUTCOME_METADATA,
    ]
    for family in ECG_FAMILIES.values():
        candidate_names.extend(
            item["variable"]
            for item in phase4["complete_variable_inventory"]
            if item["variable_family"] == family
        )
    values = {
        name: {
            "missing_count": inventory[name]["missing_count"],
            "missing_percentage": inventory[name]["missing_percentage"],
        }
        for name in candidate_names
    }
    core_names = [*CLINICAL, treatment, "is_MI"]
    ecg_names = [
        name for name in candidate_names if name.startswith("z_ecg_")
        or name in {
            item["variable"]
            for item in phase4["complete_variable_inventory"]
            if item["variable_family"] == ECG_FAMILIES["engineered"]
        }
    ]
    return {
        "candidate_field_count": len(candidate_names),
        "per_variable": values,
        "core_clinical_treatment_outcome_missing_cells": sum(
            values[name]["missing_count"] for name in core_names
        ),
        "ecg_representation_missing_cells": sum(
            values[name]["missing_count"] for name in ecg_names
        ),
        "missing_data_strategy": "NOT SELECTED — no discovery matrix authorized; no imputation or row deletion performed.",
    }


def matrix_descriptors(
    inputs: dict[str, Any],
    treatment: str,
) -> dict[str, Any]:
    phase4 = inputs["phase4"]
    summary = phase4["input_summary"]
    inventory = phase4["complete_variable_inventory"]
    engineered = [
        item["variable"]
        for item in inventory
        if item["variable_family"] == ECG_FAMILIES["engineered"]
    ]
    latent = [
        item["variable"]
        for item in inventory
        if item["variable_family"] == ECG_FAMILIES["latent"]
    ]
    n = int(summary["admissions"])
    common = [*CLINICAL, treatment, "is_MI"]

    def descriptor(name: str, variables: list[Any], continuous: int, binary: int, authorized: bool) -> dict[str, Any]:
        block_count = sum(isinstance(value, dict) for value in variables)
        p = len(variables) - block_count + sum(
            value.get("dimension_count", 0)
            for value in variables
            if isinstance(value, dict)
        )
        return {
            "name": name,
            "candidate_schema_only": True,
            "authorized_for_discovery": authorized,
            "N_admissions_upper_bound": n,
            "variable_count": p,
            "N_per_variable_naive": n / p if p else None,
            "binary_variable_count": binary,
            "continuous_variable_count": continuous,
            "missingness": "See per-variable counts; descriptive only, no handling performed.",
            "variables_or_block": variables,
            "limitations": [
                "Admission rows are not known to be independent because some patients contribute repeated admissions.",
                "Naive N/p is not a guarantee of reliable discovery or adequate conditional-independence power.",
                "No candidate baseline or outcome definition is finalized.",
            ],
        }

    return {
        "matrix_A_clinical_history_treatment_outcome": descriptor(
            "A — clinical/history + one candidate treatment + candidate outcome",
            common,
            continuous=1,
            binary=7,
            authorized=False,
        ),
        "matrix_B_clinical_history_engineered_ecg_treatment_outcome": descriptor(
            "B — Matrix A + 95 engineered ECG measurements",
            [*common, {"block": "engineered_ecg_block", "dimension_count": len(engineered)}],
            continuous=1 + len(engineered),
            binary=7,
            authorized=False,
        ),
        "matrix_C_clinical_history_z_ecg_treatment_outcome": descriptor(
            "C — Matrix A + 64 learned ECG representation dimensions",
            [*common, {"block": "z_ecg_block", "dimension_count": len(latent)}],
            continuous=1 + len(latent),
            binary=7,
            authorized=False,
        ),
        "matrix_D_block_reduced": {
            "name": "D — reduced ECG block",
            "candidate_schema_only": True,
            "authorized_for_discovery": False,
            "variables_or_block": [],
            "status": "NOT AVAILABLE — Phase 5 performed no PCA or other justified reduction.",
        },
        "interpretation": (
            "These are bookkeeping descriptions only. No admission-level design matrix was constructed: doing so would require selecting a baseline ECG, outcome, and treatment-specific time zero that remain unresolved."
        ),
    }


def treatment_gate(
    name: str,
    spec: dict[str, Any],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    p1 = inputs["phase1"]
    p2 = inputs["phase2"]
    p3 = inputs["phase3"]
    p4 = inputs["phase4"]
    p5 = inputs["phase5"]
    p6 = inputs["phase6"]
    prevalence = p2["treatment_variables"]["admission_level_prevalence"][
        spec["positivity_key"]
    ]
    total_admissions = int(p4["input_summary"]["admissions"])
    phase3_clearly_eligible = p3["phase3_decision_record"].get(
        "clearly_eligible_baseline_covariates", []
    )
    phase1_decision = p1.get("phase_1_status", {})
    time_zero = p2["phase2_decision_record"].get(
        "Treatment-specific time zero", {}
    )
    p6_specific = p6["treatment_specific_causal_questions"][name]
    missingness = candidate_missingness(p4, spec["exposure"])
    blockers = [
        "Exact treatment assignment/administration timestamp is unavailable; treatment-specific time zero is unresolved.",
        "No final index ECG has been selected, and the treatment-relative eligibility of all ECG variables remains unresolved.",
        "Phase 2 outcome definition and event horizon remain unresolved; a candidate MI label is not yet an incident post-treatment endpoint.",
        "Phase 3 identified no clearly eligible baseline covariate; all six clinical candidates remain pending provenance/temporal verification.",
        "Phase 5 did not verify z_ecg waveform, checkpoint, training, preprocessing, or outcome/treatment-independence provenance.",
        "Engineered ECG preprocessing lineage and train-only fitting scope remain unresolved.",
        "Repeated admissions within patient require dependence-aware discovery, but effective sample size and supported cluster-aware CI/score procedure have not been established.",
    ]
    if not phase3_clearly_eligible:
        baseline_status = "BLOCKED — Phase 3 has no clearly eligible baseline covariates."
    else:
        baseline_status = "PARTIALLY_READY"
    return {
        "readiness": "BLOCKED",
        "candidate_treatment": spec["exposure"],
        "candidate_outcome": "is_MI (provisional; causal endpoint/horizon unresolved)",
        "time_zero_status": "BLOCKED — UNRESOLVED",
        "index_ecg_status": "BLOCKED — no final index ECG rule",
        "outcome_status": "BLOCKED — causal outcome definition/horizon unresolved",
        "baseline_covariate_status": baseline_status,
        "treatment_timestamp_status": "BLOCKED — exact timestamp unavailable",
        "ecg_temporal_eligibility_status": "BLOCKED — cannot establish ECG before treatment assignment",
        "z_ecg_provenance_status": "BLOCKED — Phase 5 unresolved/partially verified",
        "engineered_ecg_provenance_status": "BLOCKED — upstream preprocessing provenance unresolved",
        "missingness_status": (
            "PARTIALLY_READY — audit counts available; strategy not selected because no matrix is authorized."
        ),
        "positivity_status": (
            "PARTIALLY_READY — marginal exposure/unexposed counts available; conditional positivity by eligible cohort/strata not assessed."
        ),
        "constraint_status": (
            "PARTIALLY_READY — Phase 6 machine-readable constraints exist; only hard rules could be enforced, while soft relationships remain nonbinding."
        ),
        "marginal_exposure": {
            **prevalence,
            "total_admissions": total_admissions,
            "unexposed_percentage": float(
                prevalence["unexposed_count"] / total_admissions * 100
            ),
        },
        "candidate_matrix_descriptors": matrix_descriptors(inputs, spec["exposure"]),
        "candidate_missingness": missingness,
        "phase1_unit": p4["input_summary"]["primary_observational_unit"],
        "phase1_conclusion_snapshot": {
            "admission_level_unit": "Primary causal unit remains admission-level.",
            "ecg_time_is_causal_time_zero": "NOT ESTABLISHED",
            "phase1_decision_record": phase1_decision,
        },
        "phase2_time_zero_record": time_zero,
        "phase6_question_template": p6_specific,
        "blocking_reasons": blockers,
        "algorithm_status": {
            "PC": "NOT RUN — readiness gate BLOCKED",
            "GES": "NOT RUN — readiness gate BLOCKED",
            "FCI": "NOT RUN — readiness gate BLOCKED",
            "stability_analysis": "NOT RUN — no valid discovery matrix or algorithm outputs",
        },
        "discovery_matrix_constructed": False,
        "raw_graph": None,
        "stable_candidate_graph": None,
        "bootstrap_frequencies": [],
    }


def readiness_assessment(inputs: dict[str, Any]) -> dict[str, Any]:
    p2, p3, p4, p5, p6 = (
        inputs["phase2"],
        inputs["phase3"],
        inputs["phase4"],
        inputs["phase5"],
        inputs["phase6"],
    )
    unit = p4["input_summary"]
    repeated = unit["repeated_admissions"]
    p2_record = p2["phase2_decision_record"]
    treatment_status = {
        name: "BLOCKED" for name in TREATMENTS
    }
    checks = [
        readiness_item(
            "causal_unit",
            "PARTIALLY_READY",
            "Admission-level observational unit is frozen; repeated admissions require dependence-aware analysis.",
            f"Phase 1/4 decision; {unit['repeated_admissions']['patients_with_multiple_admissions']:,} patients have repeated admissions. Preserve SubjectID for dependence, not as a causal feature; handling is unresolved.",
            True,
            treatment_status,
        ),
        readiness_item(
            "treatment_specific_time_zero",
            "BLOCKED",
            "Exact treatment assignment time is absent for aspirin, statin, beta blocker, and ACE inhibitor.",
            p2_record.get("Treatment-specific time zero"),
            True,
            treatment_status,
        ),
        readiness_item(
            "index_ecg_rule",
            "BLOCKED",
            "No final causal index ECG is selected; first ECG or MI-relative rules are not validated treatment baselines.",
            p4["decision_record"].get("blockers"),
            True,
            treatment_status,
        ),
        readiness_item(
            "outcome_definition",
            "BLOCKED",
            "MI outcome definition and post-treatment follow-up horizon are unresolved.",
            p2_record.get("Outcome definition"),
            True,
            treatment_status,
        ),
        readiness_item(
            "ecg_temporal_eligibility",
            "BLOCKED",
            "Neither z_ecg nor engineered ECG features are established before treatment-specific time zero.",
            "Phase 3 eligibility and Phase 5 treatment-relative temporal status are unresolved.",
            True,
            treatment_status,
        ),
        readiness_item(
            "treatment_timestamp_availability",
            "BLOCKED",
            "Master schema provides window-coded flags only; exact medication time fields are absent.",
            p5["inputs"].get("master_medication_timestamp_columns"),
            True,
            treatment_status,
        ),
        readiness_item(
            "z_ecg_provenance",
            "BLOCKED",
            "The 64 embeddings exist and are complete in the master table, but waveform join, checkpoint, training membership, and leakage independence are unverified.",
            p5["recommendation"]["discovery"],
            True,
            treatment_status,
        ),
        readiness_item(
            "engineered_feature_provenance",
            "BLOCKED",
            "Upstream engineered ECG preprocessing and fit scope are not verified.",
            "Phase 4 reports documented transforms but no local scripts/fitted transformer artifacts to verify train-only scope.",
            True,
            treatment_status,
        ),
        readiness_item(
            "preprocessing_provenance",
            "BLOCKED",
            "Train-only preprocessing scope is unresolved for engineered ECG features and VAE inputs/embeddings.",
            "Phase 4/5 frozen audit results.",
            True,
            treatment_status,
        ),
        readiness_item(
            "missingness_handling",
            "PARTIALLY_READY",
            "Missingness counts exist in frozen Phase 4 inventory, but no strategy is authorized until a valid treatment-specific matrix is defined.",
            "Candidate matrix variable-level counts will be reported; no imputation/complete-case processing performed.",
            True,
            treatment_status,
        ),
        readiness_item(
            "treatment_prevalence_positivity",
            "PARTIALLY_READY",
            "Marginal admission prevalence is reported; conditional positivity in a finalized eligible cohort and covariate strata is unknown.",
            "Phase 2 admission-level exposure counts; stratified positivity is not audited for any selected baseline cohort.",
            True,
            treatment_status,
        ),
        readiness_item(
            "phase6_constraints",
            "READY",
            "Phase 6 provides machine-readable hard, soft, forbidden, permitted, and unresolved constraints; soft relationships must remain nonbinding.",
            f"Specification present; {len(p6.get('hard_constraints', []))} hard constraint records and {len(p6.get('soft_constraints', []))} soft relationship records.",
            False,
            treatment_status,
        ),
    ]
    gate_status = {
        name: "BLOCKED"
        for name in TREATMENTS
    }
    return {
        "overall_status": "BLOCKED",
        "per_treatment": gate_status,
        "checks": checks,
        "phase0_artifact": (
            "NOT AVAILABLE locally; estimand/problem definition not reconstructed."
        ),
        "repeated_patient_dependence": {
            "patients": unit["patients"],
            "admissions": unit["admissions"],
            "patients_with_multiple_admissions": repeated["patients_with_multiple_admissions"],
            "fraction_patients_with_multiple_admissions": repeated[
                "fraction_patients_with_multiple_admissions"
            ],
            "effective_sample_size": "UNRESOLVED — requires within-patient dependence/ICC and target cohort.",
        },
        "decision": (
            "Do not run PC, GES, FCI, discovery configurations, or bootstrap stability analysis. "
            "For all four treatments, missing time zero, outcome horizon, baseline ECG eligibility, and unresolved provenance prevent a defensible causal discovery matrix. Any forced run would be exploratory association structure and would not satisfy the requested causal discovery objective."
        ),
    }


def build_results(inputs: dict[str, Any]) -> dict[str, Any]:
    phase2 = inputs["phase2"]
    phase4 = inputs["phase4"]
    phase6 = inputs["phase6"]
    if not phase6["constraint_sets"]["hard_constraints"]:
        raise ValueError("Phase 6 hard constraints are missing; Phase 7 gate cannot verify constraints.")
    treatment_results = {
        name: treatment_gate(name, spec, inputs)
        for name, spec in TREATMENTS.items()
    }
    return {
        "phase": "Phase 7 — Causal Discovery Readiness Gate",
        "scope": (
            "The requested gate was evaluated. Causal discovery was not run because every treatment-specific "
            "analysis is BLOCKED by frozen unresolved prerequisites."
        ),
        "frozen_inputs": {
            "phase_files": {key: str(value) for key, value in PHASE_INPUTS.items()},
            "phase0_artifact_available": False,
            "master_document": str(MASTER_DOC),
            "causal_unit": phase4["input_summary"]["primary_observational_unit"],
            "split_rows": phase4["input_summary"]["split_rows"],
            "combined_ecg_rows": phase4["input_summary"]["combined_rows"],
            "admissions": phase4["input_summary"]["admissions"],
            "patients": phase4["input_summary"]["patients"],
            "repeated_ecg_admissions": phase4["input_summary"]["repeated_ecg"][
                "admissions_with_multiple_ecgs"
            ],
            "patients_with_repeated_admissions": phase4["input_summary"][
                "repeated_admissions"
            ]["patients_with_multiple_admissions"],
            "phase2_treatment_time_zero": phase2["phase2_decision_record"].get(
                "Treatment-specific time zero"
            ),
            "phase2_outcome_definition": phase2["phase2_decision_record"].get(
                "Outcome definition"
            ),
            "phase6_hard_constraint_count": len(
                phase6["constraint_sets"]["hard_constraints"]
            ),
            "phase6_soft_constraint_count": len(
                phase6["constraint_sets"]["soft_constraints"]
            ),
            "phase6_required_edge_count": len(
                phase6["constraint_sets"]["required_edges"]
            ),
        },
        "readiness_assessment": readiness_assessment(inputs),
        "treatment_specific_readiness": treatment_results,
        "candidate_discovery_matrices": {
            name: result["candidate_matrix_descriptors"]
            for name, result in treatment_results.items()
        },
        "algorithm_configurations": {
            "PC": {
                "status": "NOT RUN",
                "reason": "Readiness gate BLOCKED for every treatment.",
                "alpha_grid": [],
                "ci_test": None,
                "orientation_settings": None,
            },
            "GES": {
                "status": "NOT RUN",
                "reason": "Readiness gate BLOCKED for every treatment.",
                "score": None,
                "penalty_grid": [],
                "initialization": None,
            },
            "FCI": {
                "status": "NOT RUN",
                "reason": "Readiness gate BLOCKED for every treatment.",
                "alpha_grid": [],
                "ci_test": None,
                "selection_bias_model": None,
            },
        },
        "ci_tests": {
            "status": "NOT SELECTED / NOT RUN",
            "reason": (
                "Matrix is not authorized, outcome is unresolved, and mixed binary/continuous variables plus "
                "patient clustering require a justified method before testing."
            ),
            "candidate_variables": "Not finalized",
            "sample_size": "Admission counts are known, but effective independent sample size is unresolved.",
            "multiple_testing": "Not applicable; no CI tests performed.",
        },
        "missing_data": {
            "status": "AUDITED DESCRIPTIVELY; NO HANDLING PERFORMED",
            "method": None,
            "imputation": False,
            "complete_case_rows_dropped": 0,
            "reason": "No discovery matrix authorized; no imputation or complete-case selection performed.",
        },
        "stability_analysis": {
            "status": "NOT RUN",
            "bootstrap_frequencies": [],
            "reason": "No valid discovery matrix or raw algorithmic graph.",
            "interpretation_warning": (
                "Even if later estimated, high bootstrap frequency indicates resampling stability only, not causal truth."
            ),
        },
        "algorithm_comparison": {
            "status": "NOT APPLICABLE — no algorithms were run.",
            "edge_comparison_matrix": [],
            "major_disagreements": [],
        },
        "raw_graphs": {},
        "stable_candidate_graphs": {},
        "suspicious_structure_flags": [],
        "constraint_application": {
            "hard_constraints": "Would be enforced only after validating graph nodes and block expansions.",
            "soft_constraints": "Nonbinding; not converted to mandatory arrows.",
            "constraint_violations": [],
        },
        "phase8_handoff": [
            "Resolve treatment-specific time zero using exact medication assignment/administration times for one candidate treatment at a time.",
            "Define a post-assignment incident MI outcome and a defensible follow-up horizon; choose one outcome representation.",
            "Resolve baseline variable eligibility and a treatment-specific ECG rule without assuming earliest ECG is baseline.",
            "Audit engineered ECG preprocessing and train-only fit scope; complete Phase 5 VAE checkpoint/training/embedding linkage provenance.",
            "Specify admission-level dependence handling for repeated patients and a valid effective sample-size/CI-test strategy.",
            "Assess conditional treatment positivity in the finalized eligible population and specify missing-data handling.",
            "Only then map Phase 6 hard constraints to the finalized matrix; preserve its soft constraints as nonbinding.",
            "If all gates are satisfied, run PC/GES/FCI separately by treatment, retain partial orientations/PAG endpoints, and perform configuration and resampling stability analysis.",
        ],
    }


def markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
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
    gate = results["readiness_assessment"]
    treatments = results["treatment_specific_readiness"]
    check_rows = [
        [
            check["id"],
            check["status"],
            check["finding"],
            "; ".join(check["evidence"])
            if isinstance(check["evidence"], list)
            else check["evidence"],
        ]
        for check in gate["checks"]
    ]
    treatment_rows = [
        [
            name,
            item["readiness"],
            item["candidate_treatment"],
            item["time_zero_status"],
            item["index_ecg_status"],
            item["outcome_status"],
            "PC/GES/FCI NOT RUN",
        ]
        for name, item in treatments.items()
    ]
    matrix_rows = []
    for name, treatment in treatments.items():
        for matrix in treatment["candidate_matrix_descriptors"].values():
            if not isinstance(matrix, dict) or "variable_count" not in matrix:
                continue
            matrix_rows.append(
                [
                    name,
                    matrix["name"],
                    matrix["N_admissions_upper_bound"],
                    matrix["variable_count"],
                    f'{matrix["N_per_variable_naive"]:.1f}',
                    matrix["binary_variable_count"],
                    matrix["continuous_variable_count"],
                    matrix["authorized_for_discovery"],
                ]
            )
    missing_rows = []
    for name, treatment in treatments.items():
        for variable, values in treatment["candidate_missingness"]["per_variable"].items():
            missing_rows.append(
                [
                    name,
                    variable,
                    values["missing_count"],
                    f'{values["missing_percentage"]:.6f}%',
                ]
            )
    exposure_rows = [
        [
            name,
            item["candidate_treatment"],
            item["marginal_exposure"]["exposed_count"],
            item["marginal_exposure"]["unexposed_count"],
            f'{item["marginal_exposure"]["exposure_percentage"] * 100:.3f}%',
            item["positivity_status"],
        ]
        for name, item in treatments.items()
    ]
    blockers = []
    for name, item in treatments.items():
        blockers.append(
            [
                name,
                *item["blocking_reasons"],
            ]
        )
    final_decisions = [
        "1. **Discovery unit**: Admission-level; repeated ECGs are not independent units and patient dependence remains.",
        "2. **Treatments evaluated**: Aspirin, statin, beta blocker, and ACE inhibitor; each separately gated.",
        "3. **Outcome representation**: Not used in discovery. `is_MI` is only a provisional candidate; `Label_Troponin` is cohort metadata; outcome definition/horizon unresolved.",
        "4. **Discovery matrices used**: None. A/B/C are schema-level candidates only; D reduction was not performed.",
        "5. **PC configuration**: NOT RUN — readiness blocked; no alpha or CI test selected.",
        "6. **GES configuration**: NOT RUN — readiness blocked; no score or penalty selected.",
        "7. **FCI configuration**: NOT RUN — readiness blocked; no CI configuration selected.",
        "8. **CI tests**: None selected or performed; mixed-data and clustering method needs justification after valid matrix definition.",
        "9. **Missing-data strategy**: Descriptive audit only; no imputation, complete-case restriction, or row dropping.",
        "10. **Hard constraints applied**: None to a graph because no graph was generated; Phase 6 hard rules preserved for later use.",
        "11. **Soft constraints used**: Not forced; Phase 6 soft edges remain nonbinding.",
        "12. **Raw graph summary**: None; PC/GES/FCI not run.",
        "13. **Stable candidate graph summary**: None; no resampling/parameter analyses run.",
        "14. **Bootstrap/stability results**: None; stability is not evidence of causal truth even when later computed.",
        "15. **PC/GES/FCI agreement**: Not assessed.",
        "16. **Major algorithm disagreements**: Not assessable because no algorithm was run.",
        "17. **Important temporal violations**: No graph edges available to assess; core temporal blockers are treatment time zero, ECG baseline, and outcome horizon.",
        "18. **`z_ecg` treatment**: Excluded from any matrix; remains quarantined pending provenance and treatment-relative eligibility.",
        "19. **Most stable candidate relationships**: None identified; no discovery/stability calculations performed.",
        "20. **Relationships requiring literature audit**: Any future soft candidate relationship selected for follow-up; none is treated as discovered here.",
        "21. **Relationships requiring expert validation**: Treatment assignment, ECG timing, severity/indication, and outcome-horizon relationships before modeling.",
        "22. **Whether a final DAG exists**: NO.",
        "23. **Whether an adjustment set exists**: NO.",
        "24. **Whether ATE/CATE was performed**: NO.",
        "25. **Remaining blockers**: Exact treatment time zero, incident outcome/horizon, final ECG eligibility, ECG/VAE preprocessing provenance, no clearly eligible baseline covariates, and patient-cluster-aware discovery method.",
        "26. **Phase 8 handoff**: Resolve these prerequisites before discovery; then run per-treatment PC/GES/FCI with nonbinding soft knowledge, hard constraints, and stability analysis.",
    ]
    return "\n".join(
        [
            "# Phase 7 — Causal Discovery Readiness Gate",
            "",
            "## A. Phase 7 objective",
            "",
            "Evaluate whether a defensible, treatment-specific discovery analysis can be run. This gate is not causal discovery. All four candidate treatments are blocked, so PC, GES, FCI, CI testing, graph stability, and graph comparison are intentionally not run.",
            "",
            "## B. Frozen inputs",
            "",
            *[
                f"- Phase {name[-1]} frozen results: `{path}`"
                for name, path in results["frozen_inputs"]["phase_files"].items()
            ],
            "- Phase 0 estimand artifact: not found locally; contents were not inferred.",
            f"- Master data: train {results['frozen_inputs']['split_rows']['train']:,}, validation {results['frozen_inputs']['split_rows']['validation']:,}, test {results['frozen_inputs']['split_rows']['test']:,}; combined {results['frozen_inputs']['combined_ecg_rows']:,} ECG rows; {results['frozen_inputs']['admissions']:,} admissions; {results['frozen_inputs']['patients']:,} patients.",
            "- Unit remains admission-level; `SubjectID` is for dependence/clustering only.",
            "",
            "## C. Discovery readiness gate",
            "",
            markdown_table(["Requirement", "Status", "Finding", "Evidence"], check_rows),
            "",
            f"**Overall: {gate['overall_status']} for each treatment.** The Phase 6 constraint specification exists, but it does not supply a valid outcome, treatment time zero, or index ECG. The causal discovery input matrix is not approved.",
            "",
            "## D. Treatment-specific discovery questions",
            "",
            markdown_table(["Treatment", "Status", "Candidate exposure", "Time zero", "Index ECG", "Outcome", "Algorithms"], treatment_rows),
            "",
            markdown_table(["Treatment", "Exposed admissions", "Unexposed admissions", "Marginal exposure", "Positivity assessment"], [[row[0], row[2], row[3], row[4], row[5]] for row in exposure_rows]),
            "",
            "These are marginal counts only. They do not establish positivity in an eligible causal cohort or within covariate strata. No candidate treatment-specific graph is run.",
            "",
            "## E. Discovery matrices",
            "",
            "The options below are schema-level size descriptions, not constructed matrices. No admission was reduced to a selected ECG, and no outcome/treatment-specific rows were filtered.",
            "",
            markdown_table(["Treatment", "Candidate strategy", "N upper bound", "p", "Naive N/p", "Binary", "Continuous", "Authorized"], matrix_rows),
            "",
            "Matrix A is 6 clinical/history candidates + one treatment flag + provisional `is_MI`. Matrix B adds the 95 engineered ECG measures; Matrix C adds the 64 learned `z_ecg` dimensions. Matrix D is unavailable: Phase 5 did not fit PCA or justify another reduction. High `N/p` alone does not establish graph reliability; patient clustering and causal eligibility remain unresolved.",
            "",
            "## F. Missing-data handling",
            "",
            "Phase 4 inventory missingness was carried into the JSON for candidate clinical, treatment, outcome, and ECG variables. No imputation, complete-case restriction, or row drop was performed. A final approach cannot be selected until a valid matrix and estimand are defined.",
            "",
            markdown_table(["Treatment", "Candidate variable", "Missing count", "Missing rate"], missing_rows),
            "",
            "## G. CI testing",
            "",
            "NOT SELECTED / NOT RUN. Candidate variables combine binary indicators with continuous age and ECG measures. With no authorized matrix and repeated admissions within patients, no CI test can be selected as justified for the target graph. Conditional-independence test count and multiple-testing burden are zero because no test was performed.",
            "",
            "## H. PC results",
            "",
            "NOT RUN — readiness gate BLOCKED for all treatments. No skeleton, oriented/partially oriented edges, separating sets, CI results, alpha, conditioning limit, or orientation settings exist.",
            "",
            "## I. GES results",
            "",
            "NOT RUN — readiness gate BLOCKED for all treatments. No score, penalty, initialization, or candidate graph exists.",
            "",
            "## J. FCI results",
            "",
            "NOT RUN — readiness gate BLOCKED for all treatments. No PAG, directed/bidirected/circle endpoints, CI configuration, or selection-bias model exists.",
            "",
            "## K. Stability analysis",
            "",
            "NOT RUN — no valid matrix or raw graphs exist to resample. Bootstrap frequencies are empty. Any later high resampling frequency indicates stability under resampling, not causal truth.",
            "",
            "## L. Algorithm comparison",
            "",
            "NOT APPLICABLE — PC/GES/FCI were not run. No edge comparison or majority-vote graph is produced.",
            "",
            "## M. ECG representation analysis",
            "",
            "All 95 engineered ECG features and 64 `z_ecg` dimensions remain outside discovery matrices. Phase 3/4/5 left baseline timing unresolved; Phase 5 found embeddings complete in the master table but provenance unresolved. Dimensions are not individual physiological causes; low pairwise latent correlation is not causal independence. No dense ECG edge cluster can be assessed without a graph.",
            "",
            "## N. Constraint violations / suspicious structures",
            "",
            "No graph was produced, so no edge violations or graph structures can be inspected. Phase 6 hard/soft distinction is preserved: hard constraints will be applied only after validating node expansion; soft relationships remain nonbinding. Suspicious structures cannot be assessed without algorithm outputs.",
            "",
            "## O. Raw algorithmic graphs",
            "",
            "None. `raw_graphs` is empty; no algorithmic output is fabricated.",
            "",
            "## P. Stable candidate graphs",
            "",
            "None. `stable_candidate_graphs` is empty; no stability threshold or candidate graph is asserted.",
            "",
            "## Q. Interpretation boundaries",
            "",
            "This report does not claim algorithmic discovery, candidate causal structure, a true DAG, a treatment effect, or an adjustment set. It does not infer treatment time from window labels, first ECG, MI timestamps, or `time_diff_hours`; it does not equate prediction/correlation with causation. Preserve the pipeline distinction: for MI patients `time_diff_hours = ecg_time - index_mi_time`, while Control_Symptomatic values use an admission-time anchor/fallback and are not MI-relative. The master data have zero `MI_Post-Incident` rows. Therefore the categorical `Label_Troponin` cohort label is not interchangeable with the raw temporal variable, and no row is classified as post-MI from `time_diff_hours > 0`.",
            "",
            "## R. Limitations",
            "",
            "- Exact treatment assignment/administration times are unavailable.",
            "- No final index ECG is selected; `first ECG = baseline` is not assumed.",
            "- The causal outcome definition and event horizon are unresolved.",
            "- Phase 3 has no clearly eligible baseline covariate.",
            "- ECG and VAE preprocessing provenance remain unresolved.",
            "- Several patients contribute repeated admissions (see JSON); effective independent sample size and a cluster-aware CI/score procedure are not established.",
            "- Marginal exposure prevalence exists but conditional positivity in a final cohort is unassessed.",
            "- A dedicated Phase 0 output was not found locally.",
            "- This is a blocked readiness gate, not completion of statistical causal discovery.",
            "",
            "## S. Phase 7 Decision Record",
            "",
            *final_decisions,
            "",
            "Stopping rule satisfied: no causal effect estimation, adjustment-set selection, final DAG declaration, or algorithmic causal truth claim.",
            "",
        ]
    )


def notebook_document() -> dict[str, Any]:
    cells = [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 7 — Causal Discovery Readiness Gate\n",
                "\n",
                "This notebook evaluates frozen Phases 1–6 and produces readiness and matrix descriptors only. All four treatment-specific questions are currently BLOCKED. PC/GES/FCI and stability analysis are intentionally not executed.\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Load frozen phase results and evaluate readiness\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "from phase7_causal_discovery import build_results, load_inputs, write_outputs\n",
                "inputs = load_inputs()\n",
                "results = build_results(inputs)\n",
                "write_outputs(results)\n",
                "results['readiness_assessment']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": ["## Treatment-specific gate and candidate matrices\n"],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "results['treatment_specific_readiness'], results['candidate_discovery_matrices']\n",
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "All algorithm configurations are marked NOT RUN while prerequisites remain unresolved. The generated report and JSON preserve this stopping decision; no graph is fabricated.\n",
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
    inputs = load_inputs()
    results = build_results(inputs)
    write_outputs(results)
    print(
        json.dumps(
            {
                "overall_readiness": results["readiness_assessment"]["overall_status"],
                "treatments": {
                    name: item["readiness"]
                    for name, item in results["treatment_specific_readiness"].items()
                },
                "algorithms_run": [],
                "matrix_constructed": False,
                "outputs": [str(JSON_PATH), str(NOTEBOOK_PATH), str(REPORT_PATH)],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
