import json
from pathlib import Path

nb = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 1 — Causal Unit and Temporal Framework Audit\n",
                "\n",
                "This notebook audits the observational unit and temporal relationships in the ECG master dataset before causal treatment analysis. This phase is intentionally limited to: causal unit choice, timestamp validation, repeated-ECG handling, index-ECG candidate evaluation, and a cautious statement on time-zero suitability.\n",
                "\n",
                "It explicitly does not estimate treatment effects, fit propensity models, or construct DAGs.\n"
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
                "\n",
                "import pandas as pd\n",
                "\n",
                "base = Path(r'c:/Users/anura/OneDrive/Desktop/capstone2/master')\n",
                "dfs = [pd.read_parquet(base / f'{split}.parquet') for split in ['train', 'validation', 'test']]\n",
                "df = pd.concat(dfs, ignore_index=True)\n",
                "df['ecg_time_dt'] = pd.to_datetime(df['ecg_time'], errors='coerce', utc=True)\n",
                "df['index_mi_time_dt'] = pd.to_datetime(df['index_mi_time'], errors='coerce', utc=True)\n",
                "print('rows=', len(df))\n",
                "print('patients=', df['SubjectID'].nunique())\n",
                "print('admissions=', df['hadm_id'].nunique())\n",
                "print('MI rows=', df['is_MI'].sum())\n",
                "print('valid MI timestamps=', df['index_mi_time_dt'].notna().sum())\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1) Appropriate causal unit\n",
                "\n",
                "We compare patient-level, admission-level, and ECG-level units using repeated observations, within-patient multiple admissions, and repeated ECGs in a single admission.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "patient_admissions = df.groupby('SubjectID')['hadm_id'].nunique()\n",
                "patient_ecgs = df.groupby('SubjectID').size()\n",
                "admission_ecgs = df.groupby('hadm_id').size()\n",
                "\n",
                "summary = {\n",
                "    'patients_with_multiple_admissions': int((patient_admissions > 1).sum()),\n",
                "    'patients_with_multiple_ecgs': int((patient_ecgs > 1).sum()),\n",
                "    'admissions_with_multiple_ecgs': int((admission_ecgs > 1).sum()),\n",
                "    'admissions_per_patient_mean': float(patient_admissions.mean()),\n",
                "    'admissions_per_patient_median': float(patient_admissions.median()),\n",
                "    'ecgs_per_patient_mean': float(patient_ecgs.mean()),\n",
                "    'ecgs_per_admission_mean': float(admission_ecgs.mean()),\n",
                "    'fraction_admissions_with_multiple_ecgs': float((admission_ecgs > 1).mean()),\n",
                "}\n",
                "print(json.dumps(summary, indent=2))\n",
                "print('\\nPatients with 1/2/3+ admissions:')\n",
                "print(pd.Series(patient_admissions).value_counts().head(10).to_string())\n",
                "print('\\nECGs per admission distribution (top):')\n",
                "print(pd.Series(admission_ecgs).value_counts().head(10).to_string())\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Recommendation\n",
                "\n",
                "The data do not support treating each ECG as an independent unit. Repeated ECGs occur frequently within the same admission and across multiple admissions for the same patient. The ECG level is too granular for a causal unit because the same patient/admission can contribute many observations. The patient level is also unstable if repeat admissions are treated as independent, because a single patient may contribute multiple hospitalizations. For a causal audit focused on a single MI event/admission, the admission-level unit is the most defensible primary observational unit, while the patient-level unit remains relevant for repeated-hospitalization structure and for handling patient-level clustering.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2) Audit ECG timestamps and MI-event timestamps\n",
                "\n",
                "We verify whether `time_diff_hours` matches `ecg_time - index_mi_time` in hours and report summary statistics on the valid pairs.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "mask = df['ecg_time_dt'].notna() & df['index_mi_time_dt'].notna()\n",
                "actual_hours = (df.loc[mask, 'ecg_time_dt'] - df.loc[mask, 'index_mi_time_dt']).dt.total_seconds() / 3600.0\n",
                "reported = pd.to_numeric(df.loc[mask, 'time_diff_hours'], errors='coerce')\n",
                "diff = actual_hours - reported\n",
                "\n",
                "summary = {\n",
                "    'n_valid_pairs': int(mask.sum()),\n",
                "    'time_diff_min': float(reported.min()),\n",
                "    'time_diff_max': float(reported.max()),\n",
                "    'time_diff_mean': float(reported.mean()),\n",
                "    'time_diff_median': float(reported.median()),\n",
                "    'time_diff_std': float(reported.std(ddof=1)),\n",
                "    'n_positive': int((reported > 0).sum()),\n",
                "    'n_negative': int((reported < 0).sum()),\n",
                "    'n_approx_zero': int((reported.abs() < 1e-9).sum()),\n",
                "    'max_abs_error_hours': float(diff.abs().max()),\n",
                "    'fraction_exact_match': float((diff.abs() < 1e-9).mean()),\n",
                "}\n",
                "print(json.dumps(summary, indent=2))\n",
                "print('\\nQuantiles:')\n",
                "print(reported.quantile([0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]).to_string())\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Conclusion on sign convention\n",
                "\n",
                "The arithmetic matches exactly: `time_diff_hours` = `ecg_time - index_mi_time` in hours. There is no sign inversion. Positive values mean the ECG occurred after the MI event; negative values mean before the MI event. We therefore treat the sign convention as observationally valid and do not reinterpret the field.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3) Verify temporal ordering\n",
                "\n",
                "Using the actual timestamps, we classify valid MI-related rows as occurring before, approximately at, or after the MI event.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "valid = df[df['index_mi_time_dt'].notna()].copy()\n",
                "valid['actual_diff_hours'] = (valid['ecg_time_dt'] - valid['index_mi_time_dt']).dt.total_seconds() / 3600.0\n",
                "valid['temporal_relation'] = 'missing_index_time'\n",
                "valid.loc[valid['actual_diff_hours'] < -2, 'temporal_relation'] = 'ECG before MI'\n",
                "valid.loc[(valid['actual_diff_hours'] >= -2) & (valid['actual_diff_hours'] <= 2), 'temporal_relation'] = 'ECG approximately at MI'\n",
                "valid.loc[valid['actual_diff_hours'] > 2, 'temporal_relation'] = 'ECG after MI'\n",
                "\n",
                "relation_counts = valid['temporal_relation'].value_counts()\n",
                "print(relation_counts.to_string())\n",
                "print('\\nPercentages:')\n",
                "print((relation_counts / len(valid)).to_string())\n",
                "print('\\nCross-tab with Label_Troponin:')\n",
                "print(pd.crosstab(valid['Label_Troponin'], valid['temporal_relation']).to_string())\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Temporal label audit\n",
                "\n",
                "The labels are not fully logically consistent with the event-time ordering. The `Label_Troponin` field includes `Control_Symptomatic`, `MI_Acute_Presentation`, and `MI_Pre-Incident` but not a dedicated `MI_Post-Incident` category. In the timestamp-based analysis, a substantial minority of ECGs with a valid MI timestamp occur after the event (`ECG after MI`), and these are not represented as a distinct label in the existing taxonomy. This is a clear sign that the label schema and the actual timestamp logic should not be treated as interchangeable.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4) Repeated ECGs\n",
                "\n",
                "Repeated ECGs are frequent and matter for the observational unit.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "hadm_counts = df.groupby('hadm_id').size()\n",
                "patient_admissions = df.groupby('SubjectID')['hadm_id'].nunique()\n",
                "patient_ecgs = df.groupby('SubjectID').size()\n",
                "mi_df = df[df['is_MI'] == 1].copy()\n",
                "\n",
                "print('admissions with >1 ECG:', int((hadm_counts > 1).sum()))\n",
                "print('fraction admissions >1 ECG:', float((hadm_counts > 1).mean()))\n",
                "print('min/max ECGs per admission:', int(hadm_counts.min()), int(hadm_counts.max()))\n",
                "print('patients with multiple admissions:', int((patient_admissions > 1).sum()))\n",
                "print('patients with multiple ECGs:', int((patient_ecgs > 1).sum()))\n",
                "print('MI rows:', len(mi_df))\n",
                "print('MI hadm_ids with multiple ECGs:', int(mi_df.groupby('hadm_id').size().gt(1).sum()))\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "The same patient often appears across multiple hospital admissions, and the same admission frequently contains multiple ECGs. This makes a single ECG-based observational unit vulnerable to within-cluster dependence and repeated measures.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 5) Candidate index-ECG definitions\n",
                "\n",
                "We evaluate candidate rules A-D using the actual data and do not force a selection if the data do not justify it.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# Candidate A\n",
                "first_adm = df.sort_values(['hadm_id', 'ecg_time_dt']).drop_duplicates(subset=['hadm_id'], keep='first')\n",
                "# Candidate B\n",
                "mi_df = df[df['index_mi_time_dt'].notna()].copy()\n",
                "before_mi = mi_df[mi_df['ecg_time_dt'] < mi_df['index_mi_time_dt']].sort_values(['SubjectID', 'hadm_id', 'ecg_time_dt'])\n",
                "first_before = before_mi.drop_duplicates(subset=['SubjectID', 'hadm_id'], keep='first')\n",
                "# Candidate C\n",
                "before_mi = before_mi.copy()\n",
                "before_mi['distance_to_mi_hours'] = (before_mi['index_mi_time_dt'] - before_mi['ecg_time_dt']).dt.total_seconds() / 3600.0\n",
                "closest_before = before_mi.sort_values(['SubjectID', 'hadm_id', 'distance_to_mi_hours', 'ecg_time_dt']).drop_duplicates(subset=['SubjectID', 'hadm_id'], keep='first')\n",
                "\n",
                "results = {\n",
                "    'A_first_ECG_within_admission': {\n",
                "        'eligible': len(first_adm),\n",
                "        'excluded': len(df) - len(first_adm),\n",
                "        'MI_retained': int(first_adm['is_MI'].sum()),\n",
                "        'control_retained': int((~first_adm['is_MI']).sum()),\n",
                "    },\n",
                "    'B_first_ECG_before_MI': {\n",
                "        'eligible': len(first_before),\n",
                "        'excluded': len(mi_df) - len(first_before),\n",
                "        'MI_retained': int(first_before['is_MI'].sum()),\n",
                "        'control_retained': 0,\n",
                "    },\n",
                "    'C_closest_ECG_before_MI': {\n",
                "        'eligible': len(closest_before),\n",
                "        'excluded': len(mi_df) - len(closest_before),\n",
                "        'MI_retained': int(closest_before['is_MI'].sum()),\n",
                "        'control_retained': 0,\n",
                "    },\n",
                "    'D_first_clinically_eligible': {\n",
                "        'eligible': 'not identifiable without an explicit clinical eligibility definition',\n",
                "        'excluded': 'not identifiable without a clinical rule',\n",
                "        'MI_retained': 'undefined without explicit eligibility',\n",
                "        'control_retained': 'undefined without explicit eligibility',\n",
                "    },\n",
                "}\n",
                "print(json.dumps(results, indent=2))\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Interpretation\n",
                "\n",
                "- Candidate A is easy to compute but is highly sensitive to same-admission repeats and does not respect the MI event timing.\n",
                "- Candidate B is event-aware but only applies to MI cases; it offers no natural analogue for controls.\n",
                "- Candidate C is arguably the most clinically intuitive of the MI-specific rules, since it chooses the ECG closest to the event while still preceding it, but it still leaves no straightforward control analogue and does not resolve repeated measures.\n",
                "- Candidate D is not operationally identifiable from the parquet files alone because a clinical eligibility rule is not defined in the current data schema.\n",
                "\n",
                "The data do not support a single universally defensible index-ECG rule across all observations. Since treatment timing has not yet been audited, the safest Phase 1 interpretation is to avoid selecting a definitive index ECG for causal analysis until the next phase.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 6) Can ECG time be used as time zero?\n",
                "\n",
                "This is a critical causal decision. The audit shows that ECG acquisition time is an observable timestamp that is often close to the MI event, but it is not the same concept as treatment assignment time or event onset time. Treatment timing is not yet audited in this phase, so we do not claim that ECG time is the valid causal time zero.\n",
                "\n",
                "If the evidence is insufficient, the correct status is:\n",
                "\n",
                "`Phase 1 status: unresolved pending Phase 2 treatment-timing audit`\n",
                "\n",
                "This is preferable to claiming an unsupported causal time-zero definition before treatment timing and assignment are explicitly audited.\n"
            ],
        },
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out_path = Path(r"c:\Users\anura\OneDrive\Desktop\capstone2\phase1_causal_unit_temporal_framework_audit.ipynb")
out_path.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"Notebook created at: {out_path}")
