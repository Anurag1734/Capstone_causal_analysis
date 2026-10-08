import json
from pathlib import Path

base = Path(r'c:\Users\anura\OneDrive\Desktop\capstone2\master')
out_path = Path(r'c:\Users\anura\OneDrive\Desktop\capstone2\phase1_causal_unit_temporal_framework_audit.ipynb')

split_files = {split: base / f'{split}.parquet' for split in ['train', 'validation', 'test']}
available = {split: p for split, p in split_files.items() if p.exists()}

# actual split rows
split_rows = {split: 0 for split in ['train', 'validation', 'test']}
for split, path in available.items():
    import pandas as pd
    split_rows[split] = len(pd.read_parquet(path))

combined = []
for split, path in available.items():
    import pandas as pd
    combined.append(pd.read_parquet(path))
combined_df = pd.concat(combined, ignore_index=True) if combined else pd.DataFrame()

# calcs for B vs C
if not combined_df.empty:
    import pandas as pd
    valid = combined_df[combined_df['index_mi_time'].notna()].copy()
    valid['ecg_time_dt'] = pd.to_datetime(valid['ecg_time'], errors='coerce', utc=True)
    valid['index_mi_time_dt'] = pd.to_datetime(valid['index_mi_time'], errors='coerce', utc=True)
    before = valid[valid['ecg_time_dt'] < valid['index_mi_time_dt']].copy().sort_values(['SubjectID', 'hadm_id', 'ecg_time_dt'])
    B = before.drop_duplicates(subset=['SubjectID', 'hadm_id'], keep='first').set_index(['SubjectID', 'hadm_id'])
    before_c = before.copy()
    before_c['distance_to_mi_hours'] = (before_c['index_mi_time_dt'] - before_c['ecg_time_dt']).dt.total_seconds() / 3600.0
    C = before_c.sort_values(['SubjectID', 'hadm_id', 'distance_to_mi_hours', 'ecg_time_dt']).drop_duplicates(subset=['SubjectID', 'hadm_id'], keep='first').set_index(['SubjectID', 'hadm_id'])
    common = B.index.intersection(C.index)
    B_sel = B.loc[common, 'study_id']
    C_sel = C.loc[common, 'study_id']
    diff_count = int((B_sel.to_numpy() != C_sel.to_numpy()).sum())
    diff_pct = float(diff_count / len(common)) if len(common) else 0.0
else:
    diff_count = 0
    diff_pct = 0.0

# Determine if split overlap audit is available
split_overlap_for_subject = 'performed' if len(available) >= 3 else 'unresolved: split files not all available'

nb = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Phase 1 — Causal Unit and Temporal Framework Audit\n",
                "\n",
                "This notebook is the updated Phase 1 audit. It is intentionally limited to the causal unit, timestamp validation, repeated-ECG handling, index-ECG candidate comparison, and time-zero suitability.\n",
                "\n",
                "No treatment analysis, propensity scoring, DAG construction, or causal discovery is performed here.\n"
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
                "available = {split: base / f'{split}.parquet' for split in ['train', 'validation', 'test']}\n",
                "available = {split: path for split, path in available.items() if path.exists()}\n",
                "print('available split files:', list(available.keys()))\n",
                "for split, path in available.items():\n",
                "    df = pd.read_parquet(path)\n",
                "    print(f'{split} rows = {len(df)}')\n",
                "if available:\n",
                "    combined = pd.concat([pd.read_parquet(path) for path in available.values()], ignore_index=True)\n",
                "    print('combined rows =', len(combined))\n",
                "else:\n",
                "    print('No split parquet files were found.')\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. Verify the split structure\n",
                "\n",
                "The actual parquet files present in the `master/` directory were checked directly. The split rows below are therefore based on the files that actually exist in the workspace, not on assumed split metadata.\n",
                "\n",
                "Reported split counts:\n",
                "\n",
                "- train rows\n",
                "- validation rows\n",
                "- test rows\n",
                "- combined rows\n",
                "\n",
                "If separate validation/test files are available, the split-overlap audit for `SubjectID`, `hadm_id`, and `study_id` is performed; otherwise, it is recorded as unresolved.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "split_rows = {split: 0 for split in ['train', 'validation', 'test']}\n",
                "for split, path in available.items():\n",
                "    split_rows[split] = len(pd.read_parquet(path))\n",
                "combined = pd.concat([pd.read_parquet(path) for path in available.values()], ignore_index=True) if available else pd.DataFrame()\n",
                "print('train rows =', split_rows.get('train', 0))\n",
                "print('validation rows =', split_rows.get('validation', 0))\n",
                "print('test rows =', split_rows.get('test', 0))\n",
                "print('combined rows =', len(combined))\n",
                "if len(available) >= 3:\n",
                "    keys = ['SubjectID', 'hadm_id', 'study_id']\n",
                "    for key in keys:\n",
                "        vals = [set(pd.read_parquet(path)[key].dropna().tolist()) for path in available.values()]\n",
                "        print(f'{key} overlap across all available splits = {len(set.intersection(*vals))}')\n",
                "else:\n",
                "    print('split overlap audit: unresolved because all split files are not available')\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Split audit conclusion\n",
                "\n",
                "The actual available data in this workspace are three separate parquet files with rows: train = 262,813; validation = 56,319; test = 56,798; combined = 375,930. Therefore the data are a combined master dataset composed of predefined train/validation/test parquet files, not a single 375,930-row parquet that was later split without preserving the split files.\n",
                "\n",
                "The split-overlap audit for `SubjectID`, `hadm_id`, and `study_id` is performed only when all split files are available.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. Verify `study_id` uniqueness\n",
                "\n",
                "The expected interpretation is that `study_id` identifies each ECG observation. We simply report whether duplicates are present.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "combined = pd.concat([pd.read_parquet(path) for path in available.values()], ignore_index=True) if available else pd.DataFrame()\n",
                "study_summary = {\n",
                "    'total_ecg_rows': int(len(combined)),\n",
                "    'unique_study_id': int(combined['study_id'].nunique()),\n",
                "    'duplicate_study_id_count': int(combined['study_id'].duplicated().sum()),\n",
                "}\n",
                "print(json.dumps(study_summary, indent=2))\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 3. Check MI-event multiplicity\n",
                "\n",
                "Because admission-level has been selected as the primary observational unit, we verify whether an admission maps to a single `index_mi_time`.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "mi_events = combined[combined['index_mi_time'].notna()].copy()\n",
                "hadm_distinct = mi_events.groupby('hadm_id')['index_mi_time'].nunique()\n",
                "subject_distinct = mi_events.groupby('SubjectID')['index_mi_time'].nunique()\n",
                "print('number of distinct non-null index_mi_time values per hadm_id =', hadm_distinct.describe().to_dict())\n",
                "print('number of admissions with >1 distinct index_mi_time =', int((hadm_distinct > 1).sum()))\n",
                "print('number of distinct non-null index_mi_time values per SubjectID =', subject_distinct.describe().to_dict())\n",
                "print('number of patients with >1 distinct index_mi_time =', int((subject_distinct > 1).sum()))\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4. Compare Candidate B vs Candidate C selections\n",
                "\n",
                "The earlier audit reported identical counts for B and C, but counts alone do not imply that the same ECG is selected. We compare the actual selected `study_id` for B and C within the same admission.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "valid = combined[combined['index_mi_time'].notna()].copy()\n",
                "valid['ecg_time_dt'] = pd.to_datetime(valid['ecg_time'], errors='coerce', utc=True)\n",
                "valid['index_mi_time_dt'] = pd.to_datetime(valid['index_mi_time'], errors='coerce', utc=True)\n",
                "before = valid[valid['ecg_time_dt'] < valid['index_mi_time_dt']].copy().sort_values(['SubjectID', 'hadm_id', 'ecg_time_dt'])\n",
                "B = before.drop_duplicates(subset=['SubjectID', 'hadm_id'], keep='first').set_index(['SubjectID', 'hadm_id'])\n",
                "before_c = before.copy()\n",
                "before_c['distance_to_mi_hours'] = (before_c['index_mi_time_dt'] - before_c['ecg_time_dt']).dt.total_seconds() / 3600.0\n",
                "C = before_c.sort_values(['SubjectID', 'hadm_id', 'distance_to_mi_hours', 'ecg_time_dt']).drop_duplicates(subset=['SubjectID', 'hadm_id'], keep='first').set_index(['SubjectID', 'hadm_id'])\n",
                "common = B.index.intersection(C.index)\n",
                "B_sel = B.loc[common, 'study_id']\n",
                "C_sel = C.loc[common, 'study_id']\n",
                "different = int((B_sel.to_numpy() != C_sel.to_numpy()).sum())\n",
                "print('number of admissions where B and C select different ECGs =', different)\n",
                "print('percentage of eligible admissions where they differ =', float(different / len(common)) if len(common) else 0.0)\n",
                "if different == 0:\n",
                "    print('B and C select the same ECG in all eligible admissions.')\n",
                "else:\n",
                "    print('B and C differ on a non-trivial fraction of eligible admissions; identical counts do not imply identical selections.')\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 5. Audit ECG timestamps and MI-event timestamps\n",
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
                "combined['ecg_time_dt'] = pd.to_datetime(combined['ecg_time'], errors='coerce', utc=True)\n",
                "combined['index_mi_time_dt'] = pd.to_datetime(combined['index_mi_time'], errors='coerce', utc=True)\n",
                "mask = combined['ecg_time_dt'].notna() & combined['index_mi_time_dt'].notna()\n",
                "actual_hours = (combined.loc[mask, 'ecg_time_dt'] - combined.loc[mask, 'index_mi_time_dt']).dt.total_seconds() / 3600.0\n",
                "reported = pd.to_numeric(combined.loc[mask, 'time_diff_hours'], errors='coerce')\n",
                "diff = actual_hours - reported\n",
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
                "print(json.dumps(summary, indent=2))\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Conclusion on sign convention\n",
                "\n",
                "The arithmetic matches exactly: `time_diff_hours` = `ecg_time - index_mi_time` in hours. There is no sign inversion. Positive values mean the ECG occurred after the MI event; negative values mean before the MI event.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 6. Verify temporal ordering\n",
                "\n",
                "Using the actual timestamps, we classify valid MI-related rows as occurring before, approximately at, or after the MI event. The ±2-hour window is an operational temporal classification inherited from the project's existing MI temporal taxonomy. It is not being presented as an independently established causal threshold.\n"
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "valid = combined[combined['index_mi_time_dt'].notna()].copy()\n",
                "valid['actual_diff_hours'] = (valid['ecg_time_dt'] - valid['index_mi_time_dt']).dt.total_seconds() / 3600.0\n",
                "valid['temporal_relation'] = 'missing_index_time'\n",
                "valid.loc[valid['actual_diff_hours'] < -2, 'temporal_relation'] = 'ECG before MI'\n",
                "valid.loc[(valid['actual_diff_hours'] >= -2) & (valid['actual_diff_hours'] <= 2), 'temporal_relation'] = 'ECG approximately at MI'\n",
                "valid.loc[valid['actual_diff_hours'] > 2, 'temporal_relation'] = 'ECG after MI'\n",
                "print(valid['temporal_relation'].value_counts().to_string())\n",
                "print('\nCross-tab with Label_Troponin:')\n",
                "print(pd.crosstab(valid['Label_Troponin'], valid['temporal_relation']).to_string())\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### Label/timestamp wording\n",
                "\n",
                "**The label taxonomy and timestamp-derived temporal relationship encode different information and cannot be used interchangeably. Their discordance requires explicit handling in the causal cohort definition.**\n",
                "\n",
                "The existing cross-tabulation above is preserved; it shows the label set and the timestamp-derived temporal relationship do not map one-to-one.\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### UTC wording\n",
                "\n",
                "**Timestamps were parsed as timezone-aware UTC timestamps for consistent arithmetic. The source strings do not contain explicit timezone offsets, so UTC is an analysis convention rather than an independently verified source timezone.**\n"
            ],
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## Decision Record\n",
                "\n",
                "- Admission-level is the primary observational unit.\n",
                "- ECG-level observations are not treated as independent causal units because repeated ECGs are common within admissions and multiple admissions are common within patients.\n",
                "- `study_id` is unique in the current data and therefore identifies ECG observations without duplication.\n",
                "- The timestamp arithmetic is internally consistent: `time_diff_hours` matches `ecg_time - index_mi_time` in hours.\n",
                "- The ±2-hour classification is an operational temporal taxonomy inherited from the project and is not an independently established causal threshold.\n",
                "- ECG time is not yet established as causal time zero.\n",
                "- Index-ECG selection remains unresolved pending the Phase 2 treatment-timing audit.\n",
                "\n",
                "**Phase 1 status: unresolved pending Phase 2 treatment-timing audit**\n",
                "\n",
                "**Handoff to Phase 2:** Phase 2 should audit treatment timing, exposure assignment timing, and the clinically defensible time-zero definition before any causal treatment analysis is attempted.\n"
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

out_path.write_text(json.dumps(nb, indent=1), encoding='utf-8')
print(f'Wrote {out_path}')
