# Baseline timing audit

## Current conclusion

The current master cannot establish the sequence

`clinical factor measurement → time zero → follow-up → subsequent MI`.

It lacks admission/discharge timestamps and has no laboratory or vital
columns. `ecg_time` and `index_mi_time` do not repair this: the first is an ECG
timestamp, while the latter is outcome-derived and is missing for many MI
admissions. Neither is a substitute for admission chronology or a timestamp
for a pre-baseline biomarker.

The project documents original MIMIC sources, including `hosp/labevents.csv`,
`hosp/omr.csv`, `icu/chartevents.csv`, `hosp/admissions.csv`,
`hosp/diagnoses_icd.csv`, and their item dictionaries. These files are not
present in the current workspace. Existing sources therefore provide
documented schemas, not actual measurement values or timeline proof.

## Source timestamp capability (documented, not locally verified)

| Source | Documented time fields | Temporal capability and limitation |
|---|---|---|
| `hosp/labevents.csv` | `charttime`, `storetime` | Supports ordering lab collection/charting relative to admission and event if the source is available. `storetime` is record-entry time, not specimen collection time. Timing a result before admission does not itself prove it predates symptoms or MI suspicion. |
| `hosp/omr.csv` | `chartdate` | Outpatient measurement may precede hospital presentation, but date-only precision may not order a same-day measurement versus time zero. Result names and values need parsing and unit harmonization. |
| `icu/chartevents.csv` | `charttime`, `storetime` | Fine-grained times but generally ICU/inpatient measurements; likely illness-, treatment-, and severity-responsive. A timestamp alone does not make it baseline. |
| `hosp/admissions.csv` | `edregtime`, `admittime`, `dischtime` | Required to define encounter order, anchor and follow-up; unavailable in current workspace. |
| `hosp/diagnoses_icd.csv` | No event time beyond admission linkage | Links diagnoses to admissions; cannot on its own timestamp MI onset within a stay. |
| `hosp/labevents.csv` troponin | `charttime`, `storetime` | First qualifying troponin charttime is the documented `index_mi_time`; it is a measured biomarker event time, not biological MI onset, and must not be used as a baseline factor. |

## Factor-by-factor ordering feasibility

| Candidate | Can current master establish pre-time-zero measurement? | Potential temporal design if source access is restored | Current status |
|---|---|---|---|
| LDL / lipids | No values or measurement times in master. | Use only an explicitly selected pre-baseline outpatient or prior-period `charttime`; define how recency and repeat results are handled. Ensure measurement precedes baseline time zero and is not obtained in response to current event suspicion. | Unresolved; promising biological candidate but unknown coverage. |
| Chronic glycemia / HbA1c | No values/timestamps in master. | Prefer an antecedent measure that represents chronic glycemia and predates baseline; distinguish it from same-admission glucose. | Unresolved. |
| Glucose | No values/timestamps in master. | Separate pre-baseline glucose from admission/stress glucose; latter is potentially consequence of acute illness. | Unresolved; acute measurements unsuitable as baseline by default. |
| Renal function (creatinine/eGFR/BUN) | No values/timestamps in master. | Require prior stable measurements or a clinically justified repeated-measure summary before baseline; distinguish CKD from acute kidney injury. | Unresolved. |
| Blood pressure/BMI | No values/timestamps in master. | OMR `chartdate` could provide outpatient baseline values, but date-only precision requires excluding or adjudicating ambiguous same-day values; define measurement aggregation. | Potentially promising if data and dates support it. |
| ICU vitals | No values/timestamps in master. | Could be baseline only if measurements occur before illness/outcome and before treatment, which is unlikely for ICU charting. | Usually downstream/prognostic; quarantine. |
| Diabetes, hypertension, CKD diagnoses | Flags present, no diagnosis dates in master. | Reconstruct diagnoses known before baseline admission from prior records; do not use codes from baseline/future admissions to define baseline history. | Candidate confounders, timing unverified. |

No minimum lookback, lag, or follow-up horizon is selected here. A lag would
need clinical justification because measurements close to an event may be
consequences of symptoms or diagnostic workup even if charted before an
administrative admission time.

## Required target timeline

If complete data become available, specify before analysis:

1. Target population and first eligible baseline date/encounter.
2. Exposure measurement window with actual `charttime`/`chartdate`; ensure no
   measurement is after baseline time zero.
3. Baseline time zero and follow-up start, with a clinically justified
   separation from measured factor and from any suspected/ongoing MI.
4. Outcome as a later, distinct ICD-coded admission, not the baseline
   admission.
5. Follow-up end, observation completeness, death/competing event, and
   censoring.

Until these elements can be constructed and checked, temporal order is a
dataset/design blocker rather than an assumption that can be granted.
