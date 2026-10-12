# Clinical Baseline-Window Audit

## Scope and interpretation

This is a descriptive temporal audit of the 8 requested candidate variables
against four antecedent lookback windows. No causal effect, DAG, adjustment
set, causal discovery, or predictive optimization was performed. No final
factor, exposure definition, baseline rule, or lookback window is selected.
Later MI counts below are descriptive only and were not used to select a
measurement or window.

The operational comparison uses the earliest non-MI admission per patient in
the recovered chronology as the prospective baseline candidate. This follows
the branch's non-MI first-baseline direction and does not use a future MI to
define eligibility. The design document says “first eligible baseline,” but
does not completely operationalize eligibility; therefore, earliest
non-MI admission is a candidate implementation, not a settled rule. No
30-day-follow-up filter was imposed.

## 1. Extraction and baseline summary

- The comparison uses only numeric finite values for itemids 50852, 50904,
  50905, 50906, 50907, 51000, 50912, and 51006 from
  `clinical_factor_timing_audit.parquet`.
- Baseline: 174,055 patients and 174,055 baseline admissions; every baseline
  had a valid admission and discharge timestamp.
- Each baseline admission was compared with patient-level charttime.
  Measurement dates on the baseline calendar date were conservatively
  excluded, even when time-of-day might precede admission. `storetime` was
  not used as clinical measurement time.
- For each patient × baseline × variable × window, the most recent eligible
  measurement was selected. Windows are inclusive at 30, 90, 180, or 365 days
  before baseline, with no use of measurements after baseline. Equal
  charttime ties were resolved deterministically; their counts appear below.
- There are 630,097 selected patient-variable-window records across the 32
  variable-window combinations. The CSV contains one row per combination.
- `clinical_baseline_window_summary.csv` is the machine-readable summary.
  The earlier timing extract and main project artifacts were not modified.

## 2. Coverage comparison

Coverage is measured among all 174,055 candidate baseline patients/admissions.
The median gap is shown for the 365-day window. It is not a recommended window.

| Variable | 30d coverage | 90d coverage | 180d coverage | 365d coverage | 365d median gap | Main provenance concern |
|---|---:|---:|---:|---:|---:|---|
| HbA1c | 3.49% | 6.10% | 8.62% | 11.69% | 83.6 days | 97.3% unlinked at 365d; chronic marker, but encounter context unknown |
| HDL | 2.03% | 5.34% | 9.30% | 14.89% | 134.3 days | 98.6% unlinked at 365d |
| Calculated LDL | 1.85% | 4.88% | 8.54% | 13.74% | 136.0 days | 98.6% unlinked at 365d; extreme upper values merit clinical review |
| Measured LDL | 0.30% | 0.75% | 1.30% | 2.21% | 148.2 days | 99.0% unlinked at 365d and very sparse |
| Total cholesterol | 2.13% | 5.51% | 9.55% | 15.26% | 133.5 days | 98.6% unlinked at 365d |
| Triglycerides | 1.96% | 5.11% | 8.88% | 14.16% | 133.7 days | 98.3% unlinked at 365d; maximum selected value is 6,498 mg/dL |
| Creatinine | 17.34% | 24.04% | 29.23% | 34.81% | 30.3 days | 97.7% unlinked at 365d; temporal priority does not establish stable renal function |
| BUN | 16.19% | 22.43% | 27.44% | 32.95% | 31.9 days | 97.6% unlinked at 365d; temporal priority does not establish stable renal function |

Wider windows increase coverage, but also admit older measurements. Lipid
median gaps in the 365-day window are about 134–148 days, while HbA1c is 83.6
days. The renal markers have higher coverage and nearer median gaps, but a
recent value can still reflect acute illness or treatment. Even the
closest-window lipid coverage is only about 2% (measured LDL 0.3%); the
365-day window's higher coverage does not resolve the unknown provenance of
most selected events.

## 3. Detailed variable × window results

In the table, coverage is selected patients / eligible patients; “missing”
means eligible patients without an eligible numeric result in that window.
Gap is days from measurement to baseline; value summaries use the selected
numeric value. “Linked / unlinked” reports selected rows with/without a
`hadm_id`. “Prior source” counts measurements either linked to an encounter
whose discharge preceded baseline or unlinked but falling inside a recorded
prior admission interval; its percentage is of selected measurements.
“Overlap/unknown discharge” counts linked selected rows whose linked
encounter discharge was after baseline or unavailable. Previous-discharge gap
summaries use only linked encounters discharged by baseline. Ambiguity counts
are the numeric same-baseline-date rows/patients excluded and are repeated
for each window because they are common to that variable.

| Variable | Window | Coverage; missing | Gap days: median [Q1, Q3]; min–max | Linked / unlinked | Prior source; overlapping/unknown linked discharge | Previous-discharge gap, days: median [Q1, Q3] | Ambiguous rows / patients excluded | Value: median [Q1, Q3]; min–max | Later MI cases | Unit |
|---|---:|---:|---|---:|---|---|---:|---|---:|---|
| HbA1c | 30d | 6,076/174,055 (3.49%); 167,979 | 9.8 [5.5, 17.0]; 0.04–29.98 | 184 / 5,892 | 187 (3.08%); 1 | 8.0 [3.5, 14.8] | 7,046 / 6,847 | 6.0 [5.5, 6.9]; 3.3–18.2 | 385 | % |
| HbA1c | 90d | 10,615/174,055 (6.10%); 163,440 | 22.8 [8.1, 53.6]; 0.04–89.99 | 373 / 10,242 | 376 (3.54%); 1 | 18.6 [7.6, 40.5] | 7,046 / 6,847 | 6.0 [5.6, 6.9]; 3.3–18.2 | 759 | % |
| HbA1c | 180d | 15,002/174,055 (8.62%); 159,053 | 47.9 [12.8, 99.6]; 0.04–179.98 | 455 / 14,547 | 458 (3.05%); 1 | 25.5 [9.9, 61.0] | 7,046 / 6,847 | 6.0 [5.6, 6.8]; 3.3–18.2 | 1,078 | % |
| HbA1c | 365d | 20,348/174,055 (11.69%); 153,707 | 83.6 [21.1, 187.0]; 0.04–364.97 | 550 / 19,798 | 555 (2.73%); 1 | 38.4 [12.5, 111.9] | 7,046 / 6,847 | 5.9 [5.5, 6.7]; 3.3–18.2 | 1,404 | % |
| HDL | 30d | 3,529/174,055 (2.03%); 170,526 | 13.8 [6.4, 21.5]; 0.32–29.98 | 99 / 3,430 | 98 (2.78%); 1 | 8.3 [3.1, 15.4] | 3,723 / 3,653 | 51 [41, 64]; 4–178 | 265 | mg/dL |
| HDL | 90d | 9,302/174,055 (5.34%); 164,753 | 41.3 [18.6, 64.8]; 0.32–89.99 | 223 / 9,079 | 223 (2.40%); 1 | 22.3 [8.6, 46.4] | 3,723 / 3,653 | 52 [42, 65]; 4–280 | 699 | mg/dL |
| HDL | 180d | 16,191/174,055 (9.30%); 157,864 | 76.7 [35.1, 123.5]; 0.32–179.98 | 279 / 15,912 | 279 (1.72%); 1 | 31.1 [12.0, 68.6] | 3,723 / 3,653 | 53 [43, 65]; 4–280 | 1,143 | mg/dL |
| HDL | 365d | 25,923/174,055 (14.89%); 148,132 | 134.3 [60.0, 234.4]; 0.32–364.98 | 350 / 25,573 | 350 (1.35%); 1 | 51.1 [15.7, 126.1] | 3,723 / 3,653 | 53 [44, 66]; 3–280 | 1,693 | mg/dL |
| Calculated LDL | 30d | 3,214/174,055 (1.85%); 170,841 | 13.9 [6.5, 21.6]; 0.32–29.98 | 94 / 3,120 | 93 (2.89%); 1 | 8.4 [3.1, 15.0] | 3,519 / 3,458 | 97 [74, 124]; 10–279 | 239 | mg/dL |
| Calculated LDL | 90d | 8,490/174,055 (4.88%); 165,565 | 41.4 [18.8, 65.0]; 0.32–89.99 | 215 / 8,275 | 215 (2.53%); 1 | 22.7 [8.8, 47.5] | 3,519 / 3,458 | 99 [76, 126]; 8–391 | 628 | mg/dL |
| Calculated LDL | 180d | 14,860/174,055 (8.54%); 159,195 | 77.2 [35.3, 124.2]; 0.32–179.98 | 269 / 14,591 | 269 (1.81%); 1 | 31.2 [12.3, 68.3] | 3,519 / 3,458 | 100 [77, 126]; 5–650 | 1,042 | mg/dL |
| Calculated LDL | 365d | 23,918/174,055 (13.74%); 150,137 | 136.0 [61.0, 235.7]; 0.32–364.97 | 339 / 23,579 | 339 (1.42%); 1 | 51.3 [15.7, 127.3] | 3,519 / 3,458 | 100 [78, 125]; 5–650 | 1,562 | mg/dL |
| Measured LDL | 30d | 527/174,055 (0.30%); 173,528 | 14.3 [7.0, 21.9]; 0.34–29.98 | 11 / 516 | 11 (2.09%); 0 | 7.2 [3.0, 15.6] | 336 / 331 | 110 [86, 138]; 19–302 | 48 | mg/dL |
| Measured LDL | 90d | 1,303/174,055 (0.75%); 172,752 | 38.0 [17.7, 63.0]; 0.34–89.84 | 22 / 1,281 | 22 (1.69%); 0 | 21.2 [4.2, 46.7] | 336 / 331 | 110 [86, 138]; 19–328 | 114 | mg/dL |
| Measured LDL | 180d | 2,263/174,055 (1.30%); 171,792 | 74.6 [32.6, 125.4]; 0.34–179.98 | 27 / 2,236 | 27 (1.19%); 0 | 31.1 [10.4, 78.2] | 336 / 331 | 109 [85, 137]; 19–463 | 195 | mg/dL |
| Measured LDL | 365d | 3,853/174,055 (2.21%); 170,202 | 148.2 [61.9, 247.1]; 0.34–364.73 | 39 / 3,814 | 39 (1.01%); 0 | 68.7 [16.6, 197.8] | 336 / 331 | 109 [86, 136]; 19–463 | 324 | mg/dL |
| Total cholesterol | 30d | 3,700/174,055 (2.13%); 170,355 | 13.6 [6.4, 21.4]; 0.32–29.98 | 102 / 3,598 | 101 (2.73%); 1 | 8.3 [3.1, 15.0] | 3,918 / 3,844 | 181 [151, 212]; 9–834 | 278 | mg/dL |
| Total cholesterol | 90d | 9,587/174,055 (5.51%); 164,468 | 40.7 [18.2, 64.4]; 0.32–89.99 | 227 / 9,360 | 227 (2.37%); 1 | 21.9 [8.4, 44.4] | 3,918 / 3,844 | 183 [154, 214]; 9–974 | 728 | mg/dL |
| Total cholesterol | 180d | 16,623/174,055 (9.55%); 157,432 | 76.2 [34.4, 123.2]; 0.32–179.98 | 289 / 16,334 | 289 (1.74%); 1 | 31.2 [12.3, 73.9] | 3,918 / 3,844 | 184 [156, 214]; 9–974 | 1,179 | mg/dL |
| Total cholesterol | 365d | 26,555/174,055 (15.26%); 147,500 | 133.5 [59.2, 233.8]; 0.32–364.98 | 362 / 26,193 | 362 (1.36%); 1 | 51.3 [15.6, 127.1] | 3,918 / 3,844 | 184 [158, 213]; 9–974 | 1,738 | mg/dL |
| Creatinine | 30d | 30,178/174,055 (17.34%); 143,877 | 7.7 [4.0, 14.4]; 0.005–30.00 | 722 / 29,456 | 721 (2.39%); 2 | 8.1 [3.4, 16.4] | 154,070 / 129,425 | 0.9 [0.7, 1.1]; 0.1–23.7 | 1,621 | mg/dL |
| Creatinine | 90d | 41,837/174,055 (24.04%); 132,218 | 12.9 [5.7, 34.3]; 0.005–89.99 | 1,038 / 40,799 | 1,038 (2.48%); 2 | 15.1 [5.3, 35.5] | 154,070 / 129,425 | 0.9 [0.7, 1.1]; 0.1–23.7 | 2,368 | mg/dL |
| Creatinine | 180d | 50,869/174,055 (29.23%); 123,186 | 18.8 [6.7, 66.3]; 0.005–179.99 | 1,188 / 49,681 | 1,190 (2.34%); 2 | 19.5 [6.2, 52.9] | 154,070 / 129,425 | 0.9 [0.7, 1.1]; 0.1–24.2 | 2,865 | mg/dL |
| Creatinine | 365d | 60,592/174,055 (34.81%); 113,463 | 30.3 [7.7, 120.1]; 0.005–365.00 | 1,387 / 59,205 | 1,389 (2.29%); 2 | 27.1 [7.7, 90.3] | 154,070 / 129,425 | 0.9 [0.7, 1.1]; 0.1–24.2 | 3,318 | mg/dL |
| Triglycerides | 30d | 3,411/174,055 (1.96%); 170,644 | 13.8 [6.4, 21.4]; 0.15–29.98 | 126 / 3,285 | 125 (3.66%); 1 | 7.4 [3.1, 15.0] | 4,649 / 4,528 | 118 [83, 176]; 25–6,498 | 263 | mg/dL |
| Triglycerides | 90d | 8,893/174,055 (5.11%); 165,162 | 41.0 [18.4, 64.5]; 0.15–89.99 | 270 / 8,623 | 270 (3.04%); 1 | 21.0 [8.1, 44.3] | 4,649 / 4,528 | 120 [84, 174]; 20–6,498 | 669 | mg/dL |
| Triglycerides | 180d | 15,451/174,055 (8.88%); 158,604 | 76.4 [34.6, 123.4]; 0.15–179.98 | 340 / 15,111 | 340 (2.20%); 1 | 29.6 [11.9, 68.1] | 4,649 / 4,528 | 120 [84, 173]; 17–6,498 | 1,099 | mg/dL |
| Triglycerides | 365d | 24,648/174,055 (14.16%); 149,407 | 133.7 [59.4, 233.7]; 0.15–364.97 | 419 / 24,229 | 419 (1.70%); 1 | 47.8 [15.0, 123.6] | 4,649 / 4,528 | 117 [82, 169]; 14–6,498 | 1,633 | mg/dL |
| BUN | 30d | 28,183/174,055 (16.19%); 145,872 | 7.7 [4.1, 14.2]; 0.005–30.00 | 725 / 27,458 | 724 (2.57%); 2 | 8.1 [3.4, 16.4] | 151,500 / 127,655 | 16 [13, 22]; 2–184 | 1,577 | mg/dL |
| BUN | 90d | 39,033/174,055 (22.43%); 135,022 | 12.9 [5.7, 34.3]; 0.005–89.99 | 1,044 / 37,989 | 1,044 (2.67%); 2 | 15.1 [5.4, 36.1] | 151,500 / 127,655 | 16 [12, 22]; 2–184 | 2,295 | mg/dL |
| BUN | 180d | 47,765/174,055 (27.44%); 126,290 | 18.9 [6.7, 68.4]; 0.005–179.99 | 1,195 / 46,570 | 1,197 (2.51%); 2 | 19.7 [6.3, 53.0] | 151,500 / 127,655 | 16 [12, 21]; 1–184 | 2,779 | mg/dL |
| BUN | 365d | 57,358/174,055 (32.95%); 116,697 | 31.9 [7.8, 125.6]; 0.005–365.00 | 1,398 / 55,960 | 1,400 (2.44%); 2 | 27.2 [7.8, 92.3] | 151,500 / 127,655 | 16 [12, 21]; 1–184 | 3,227 | mg/dL |

## 4. Timing, provenance, and repeated measurements

- Every selected result has a `charttime` strictly earlier than baseline and
  on an earlier calendar date. Same-day ambiguous measurements were not
  selected.
- No selected result came from the baseline `hadm_id`. The selected same
  baseline-admission percentage is 0% for all 32 combinations.
- In the entire observed candidate baseline cohort, there are 11,587 later
  MI-coded admissions among 5,771 patients. All 11,587 are at or before the
  patient's `observation_end`; none had a missing end or fell after it. The
  table reports later-MI patients among those selected for that
  variable-window only. These counts describe recorded follow-up and are not
  treatment effects or evidence of causation.
- Most selected events have null `hadm_id`: this is unknown encounter
  provenance, not proof of outpatient measurement. Only a small fraction of
  selected values can be affirmatively assigned to a previous admission that
  ended before baseline. A few linked events refer to admissions that overlap
  baseline or have no linked discharge timestamp; they are quantified
  separately and should not be described as previous completed admissions.
- Unlinked events were checked against recorded admission intervals. Only
  the counts in “prior source” were positively located within a prior
  admission; unlinked rows outside those intervals remain of unknown
  provenance and could still reflect care not represented by the chronology.
- Repeated measurements within a window were reduced to the most recent
  eligible row, as specified. Across the selected rows, exact-charttime tie
  counts (where multiple candidates shared the winning charttime) were 37
  HbA1c, 44 HDL, 40 calculated LDL, 7 measured LDL, 44 total cholesterol, 43
  triglycerides, 184 creatinine, and 122 BUN. Deterministic tie-breaking was
  used; this is not a count of all repeats in the source.

Unlinked percentages below are the selected rows with null `hadm_id` divided
by selected measurements for that variable-window. Together with the
previous table's explicit linked and unlinked counts, this quantifies the
provenance gap at each window.

| Variable | 30d unlinked | 90d unlinked | 180d unlinked | 365d unlinked |
|---|---:|---:|---:|---:|
| HbA1c | 96.97% | 96.49% | 96.97% | 97.30% |
| HDL | 97.19% | 97.60% | 98.28% | 98.65% |
| Calculated LDL | 97.08% | 97.47% | 98.19% | 98.58% |
| Measured LDL | 97.91% | 98.31% | 98.81% | 98.99% |
| Total cholesterol | 97.24% | 97.63% | 98.26% | 98.64% |
| Triglycerides | 96.31% | 96.96% | 97.80% | 98.30% |
| Creatinine | 97.61% | 97.52% | 97.66% | 97.71% |
| BUN | 97.43% | 97.33% | 97.50% | 97.56% |

## 5. Candidate ranking

| Candidate | Classification | Temporal/coverage basis |
|---|---|---|
| HbA1c | POSSIBLE BUT LIMITED | Clinically interpretable as longer-term glycemia; 3.49% covered at 30d and 11.69% at 365d, with 97.3% of 365d selected rows unlinked. |
| HDL | POSSIBLE BUT LIMITED | Direct lipid measure with consistent units; coverage is 2.03% at 30d and 14.89% at 365d, while 98.6% of 365d rows lack encounter linkage. |
| Calculated LDL | POSSIBLE BUT LIMITED | Clinically relevant direct candidate and 13.74% coverage at 365d; only 1.85% at 30d, provenance is mostly unlinked, and extreme values warrant validation. |
| Measured LDL | POOR CANDIDATE | Kept distinct from calculated LDL; only 0.30% coverage at 30d and 2.21% at 365d, with 99.0% unlinked at 365d. |
| Total cholesterol | POSSIBLE BUT LIMITED | Highest lipid coverage (2.13% at 30d; 15.26% at 365d), but measurement provenance remains largely unknown. |
| Triglycerides | POSSIBLE BUT LIMITED | 1.96% coverage at 30d and 14.16% at 365d; almost all events are unlinked, and very high values need clinical/unit/value validation. |
| Creatinine | POSSIBLE BUT LIMITED | Highest coverage (17.34% at 30d; 34.81% at 365d), but a timestamp before baseline does not establish stable chronic renal function; 97.7% of 365d values are unlinked. |
| BUN | POSSIBLE BUT LIMITED | Secondary renal candidate with 16.19% coverage at 30d and 32.95% at 365d; same unresolved distinction between chronic status and acute illness applies. |

No variable is classified PROMISING on the present evidence: good clinical
meaning alone cannot compensate for sparse near-baseline coverage and
unresolved provenance/stability. In particular, “possible” means worth a
targeted follow-up audit, not selected or validated for causal analysis.

## 6. Lipid-specific results

- **HDL (50904):** 3,529 patients (2.03%) have a selected antecedent value
  within 30d; 25,923 (14.89%) within 365d. At 365d, 350 are encounter-linked,
  25,573 are unlinked, and 350 have a positively identified prior-admission
  source. The selected unit is mg/dL throughout.
- **Calculated LDL (50905):** 3,214 (1.85%) within 30d; 23,918 (13.74%) within
  365d. The 365d selected value distribution is median 100 mg/dL [78, 125],
  range 5–650. It remains separate from measured LDL.
- **Measured LDL (50906):** 527 (0.30%) within 30d; 3,853 (2.21%) within
  365d. The 365d selected value distribution is median 109 mg/dL [86, 136],
  range 19–463. It is too sparse to pool with calculated LDL without a
  separate scientific rationale and prespecified measurement definition.
- **Total cholesterol (50907):** 3,700 (2.13%) within 30d; 26,555 (15.26%)
  within 365d. The selected unit is mg/dL throughout.
- **Triglycerides (51000):** 3,411 (1.96%) within 30d; 24,648 (14.16%) within
  365d. The selected unit is mg/dL throughout; the maximum selected value,
  6,498 mg/dL, requires source/value review before any substantive use.

The earlier timing extract reports a single mg/dL unit for each lipid item,
and the selected-value summaries show the same units. No lipid composite or
ratio was created. The 365d coverage gain is accompanied by a median
measurement-to-baseline gap of about 134–148 days for lipids.

## 7. HbA1c versus glucose

HbA1c (50852) is the only glycemia candidate in this audit. It has antecedent
numeric values for 6,076 patients within 30d and 20,348 within 365d. This
supports its clinical relevance as a chronic glycemia marker, but coverage
and encounter provenance are limited. Routine blood glucose (50931) was
intentionally not included as a primary candidate: it is not equivalent to
chronic glycemia and can reflect acute illness or stress.

## 8. Renal markers

Creatinine (50912) and BUN (51006) have the highest candidate coverage, but
the selected values are not proof of stable baseline kidney function.
Creatinine's 365d selected median is 0.9 mg/dL [0.7, 1.1], range 0.1–24.2;
BUN's is 16 mg/dL [12, 21], range 1–184. The median baseline gap is 30.3
days for creatinine and 31.9 days for BUN under the 365d window. Most selected
events have no encounter link, so their inpatient/outpatient context cannot
be resolved. A separate stability/acute-admission audit is needed before
calling either a baseline renal factor. eGFR remains excluded because the
previous extract contained no usable numeric values.

## 9. Variables excluded or deferred

- **Measured LDL** is retained as a separate reported candidate but ranks
  poor because coverage is extremely low; it is not merged with calculated
  LDL.
- **Routine admission glucose, eGFR, lipid ratios, electrolytes, CBC, CRP,
  and NTproBNP** are not expanded as candidates here, consistent with the
  requested scope and previous evidence.
- **BUN** remains a secondary candidate, not a chosen exposure.
- No selected-value thresholding, winsorization, transformation, or clinical
  outlier removal was performed.

## 10. Validation and unexpected findings

| Check | Result |
|---|---|
| Candidate baseline rows / unique patients | 174,055 / 174,055 |
| Missing baseline timestamp / discharge timestamp | 0 / 0 |
| Selected measurements after baseline | 0 |
| Selected same-day ambiguous measurements | 0 |
| Selected same baseline admission | 0 |
| Selected values that were nonnumeric/nonfinite | 0 |
| Selected rows with missing measurement/baseline timestamp | 0 |
| Duplicate patient × baseline × variable × window keys | 0 |
| Units | HbA1c in `%`; all seven lipid/renal items in `mg/dL`; no selected unit mixing observed |
| Measurement timestamp preservation | Exact source `charttime` was retained for timing and selection; storetime was not substituted |
| Same-charttime winning ties | Present; deterministic tie-breaking applied (counts above) |
| Later MI after baseline but beyond observation_end | 0 across 11,587 later MI-coded admissions in the candidate cohort |

Same-day numeric ambiguity and measurements linked to the candidate baseline
admission were excluded before selecting windows. The table records their
counts by variable. The exact eligible baseline definition remains an
operational proxy because the branch's “first eligible” criteria are not
fully specified.

## 11. Exact remaining blockers

1. **Baseline eligibility:** the prospective target says first eligible
   non-MI baseline, but the additional eligibility criteria are unresolved.
   The earliest non-MI admission was used only as the current operational
   candidate.
2. **Encounter provenance:** most selected labs have null `hadm_id`. These
   rows cannot be assumed outpatient, and unlinked prior acute admissions
   outside recorded intervals cannot be ruled out.
3. **Acute-admission contamination/stability:** some positively linked
   prior-admission values are identified, but this is not a complete
   assessment of clinical stability or acute kidney injury.
4. **Window/lag and same-day policy:** no scientific choice has been made
   between proximity and coverage; same-day ambiguous events remain
   conservatively excluded.
5. **Selective measurement/missingness:** the low and nonuniform coverage
   may reflect clinical testing decisions; coverage is not random by
   assumption.
6. **Value validation:** extreme lipid and renal values need source-level
   review and clinically defined data-quality rules before exposure use.
7. **Causal exposure definition:** there is no defined intervention,
   treatment strategy, abnormality contrast, or clinically meaningful
   manipulation of a lab value. The candidate-estimands document explicitly
   leaves these choices open.
8. **Outcome follow-up:** recorded later MIs fall within available
   observation_end, but the data's censoring/ascertainment limits still
   prevent treating the observed horizon as complete lifetime follow-up.

## 12. Recommended next scientific decision

First decide whether the target baseline is the earliest non-MI admission
under a fully specified prospective eligibility rule. Then decide whether
candidate antecedent measurements must be separated from recent acute
hospital care, and what clinical stability/lag criteria would be defensible.
After that, review HbA1c and the separate lipid measurements (especially
total cholesterol, HDL, and calculated LDL) alongside creatinine, with
particular attention to the 90–365d coverage-versus-recency trade-off and
unlinked provenance. Only after these decisions should the team define a
candidate clinical exposure or intervention and audit its confounding and
measurement process. This report does not choose a final window or causal
exposure.

STATUS:
"Baseline-window comparison complete; final clinical exposure/window not yet selected."

NEXT SCIENTIFIC DECISION:
Decide the prospective baseline eligibility rule and whether prior-acutely
hospitalized or otherwise unstable measurements qualify as baseline; then
specify a clinical exposure/intervention and its acceptable antecedent
measurement window for a separate audit.
