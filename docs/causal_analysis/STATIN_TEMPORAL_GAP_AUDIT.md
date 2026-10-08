# Statin temporal-gap audit

**Scope:** Temporal gap check only. No source-window reconstruction, master
dataset changes, DAG work, or effect estimation was performed.

## Result

The current master has **7,362 MI admissions** (`is_MI == 1`), after
deduplicating ECG rows by `hadm_id`.

| `index_mi_time` status | MI admissions | Percent of MI admissions |
|---|---:|---:|
| Non-null | 4,871 | 66.16% |
| Null | 2,491 | 33.84% |

The requested quantity is
`index_mi_time - anchor_time`, where the frozen definition is
`anchor_time = COALESCE(edregtime, admittime)`. It **cannot be computed from
the available current master/source files**:

- None of the three master parquet files contains `anchor_time`, `edregtime`,
  or `admittime` (the master has 184 columns).
- No `admissions.csv` or `admissions.parquet` is present under the project
  workspace.
- `ecg_time` and `final_index_time` are not substitutes for `anchor_time` and
  were not used.

Therefore the following gap statistics are **not computable**, not zero:

| Gap statistic, hours | Result |
|---|---:|
| Minimum | Not computable |
| Q1 | Not computable |
| Median | Not computable |
| Q3 | Not computable |
| Maximum | Not computable |
| Mean | Not computable |
| Standard deviation | Not computable |

### Gap categories

Counts and percentages cannot be assigned to any category because no
admission-level `anchor_time` is available. The required denominator for the
category percentages is all **7,362 MI admissions**; for gap-distribution
summaries restricted to non-null `index_mi_time`, the denominator is **4,871**.

| `index_mi_time - anchor_time` | Count | Percent of 7,362 MI admissions |
|---|---:|---:|
| `< 0` hours | Not computable | Not computable |
| `= 0` / effectively zero | Not computable | Not computable |
| `> 0` to `<= 1` hour | Not computable | Not computable |
| `> 1` to `<= 2` hours | Not computable | Not computable |
| `> 2` to `<= 6` hours | Not computable | Not computable |
| `> 6` to `<= 24` hours | Not computable | Not computable |
| `> 24` hours | Not computable | Not computable |
| Clearly positive gap (`> 0`) | Not computable | Not computable |

The gap distribution specifically among the **4,871 admissions with
non-null `index_mi_time`** is also not computable for the same missing-anchor
reason. No clinical minimum-gap threshold was applied or inferred.

## Interpretation of `index_mi_time`

According to the current cohort-labeling pipeline documentation,
`index_mi_time` is the `charttime` of the first troponin measurement that
exceeds the applicable assay threshold for the admission. It is a timestamp
for a qualifying measured biomarker result, **not the true biological onset
time of MI**. In 2,491 MI admissions (33.84%), this timestamp is null in the
current master, so it cannot anchor a gap for those admissions at all.

## Temporal-design decision

The current master cannot establish whether the non-null troponin-event
timestamps are meaningfully after `anchor_time`, and one third of MI admissions
have no `index_mi_time`. This is **not evidence that the observed gaps are
mostly zero or negative**; the requested comparison is unavailable, so positive
temporal separation cannot be defended from the current data. Per the gate,
the within-admission design is **NOT VIABLE with the current master data**.

The recommended fallback is a cross-admission design: define the prescription
exposure on a pre-existing baseline admission, then ascertain the unchanged
`is_MI` outcome on a later, separate admission. That design would require its
own eligibility and temporal specification; it was not constructed or
estimated here.

## Verdict

**WITHIN-ADMISSION DESIGN: NOT VIABLE**

`index_mi_time` is potentially an event-related measurement timestamp, but the
current master lacks the admission anchor needed to calculate its temporal gap,
and 2,491 MI admissions also lack the index timestamp. Therefore the master
cannot demonstrate scientifically defensible within-admission temporal
separation; this verdict reflects insufficient temporal evidence, not an
observed finding that gaps are short.
