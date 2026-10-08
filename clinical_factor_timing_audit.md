# Timestamped Clinical-Factor Timing Audit

## 1. Extraction summary

Extracted only the 23 requested itemids from the local `labevents` table in `mimic_database.duckdb` using a read-only DuckDB connection. The raw CSV was not present in the active workspace; the database table has the requested MIMIC labevent fields. No master dataset, Phase 1-7 artifact, or ECG/z_ecg output was changed.

**Output:** `clinical_factor_timing_audit.parquet` contains the selected lab rows plus linked admission times, `hours_from_admission`, `days_from_admission`, and `timing_class`. It preserves `charttime` and `storetime`; `storetime` was not used to assign timing.

| Extraction metric | Result |
|---|---:|
| Requested itemids | 23 |
| Extracted rows | 38,749,039 |
| Distinct patients across extracted rows | 246,619 |
| Rows with null `hadm_id` | 16,371,863 (42.3%) |
| Non-null `hadm_id` missing from admissions chronology | 0 |
| Rows with null `charttime` | 0 |

Timing is classified against the linked admission's **formal `admittime` and `dischtime`**, not `anchor_time`. Measurements on the calendar date of admission are marked ambiguous even if their time-of-day precedes or follows formal admission. Rows with no `hadm_id` cannot be assigned to a specific admission and are explicitly retained as unknown; their timestamps are still usable for patient-level pre-baseline coverage if strictly earlier than the candidate baseline date.

## 2. Coverage by factor

### 2.1 Coverage, missingness, date range, and units

'Admissions' means distinct non-null `hadm_id` values. Missing-value columns list null `value` / `valuenum`, followed by null `valueuom` / `flag` / `storetime` / `charttime`. Units are listed with event counts and within-item percentages.

| Itemid | Factor | Measurements | Patients | Linked admissions | Missing value / valuenum | Missing valueuom / flag / storetime / charttime | Charttime range | Unit distribution |
|---:|---|---:|---:|---:|---:|---|---|---|
| 50903 | Cholesterol Ratio (Total/HDL) | 243,329 | 82,219 | 21,294 | 2 / 2 | 0 / 243,329 / 0 / 0 | 2106-04-18 to 2212-09-05 | Ratio: 243,329 (100.0%) |
| 50904 | Cholesterol, HDL | 244,256 | 82,555 | 21,608 | 346 / 346 | 0 / 235,523 / 0 / 0 | 2106-04-18 to 2212-09-05 | mg/dL: 244,256 (100.0%) |
| 50905 | Cholesterol, LDL, Calculated | 222,310 | 78,444 | 20,512 | 25 / 25 | 0 / 174,022 / 0 / 0 | 2106-04-18 to 2212-09-05 | mg/dL: 222,310 (100.0%) |
| 50906 | Cholesterol, LDL, Measured | 39,282 | 19,339 | 2,120 | 1,197 / 1,197 | 0 / 27,306 / 0 / 0 | 2109-02-13 to 2211-09-20 | mg/dL: 39,282 (100.0%) |
| 50907 | Cholesterol, Total | 250,248 | 83,893 | 22,207 | 29 / 29 | 0 / 160,706 / 0 / 0 | 2106-04-18 to 2212-09-05 | mg/dL: 250,248 (100.0%) |
| 51000 | Triglycerides | 250,001 | 84,519 | 29,427 | 30 / 31 | 0 / 161,779 / 0 / 0 | 2106-04-18 to 2212-09-05 | mg/dL: 250,001 (100.0%) |
| 50852 | % Hemoglobin A1c | 223,327 | 74,733 | 30,188 | 83 / 83 | 0 / 98,696 / 0 / 0 | 2109-02-11 to 2212-11-15 | %: 223,327 (100.0%) |
| 50931 | Glucose | 2,749,562 | 234,501 | 317,303 | 364 / 364 | 0 / 994,276 / 1 / 0 | 2105-10-04 to 2212-12-19 | mg/dL: 2,749,562 (100.0%) |
| 50912 | Creatinine | 3,282,278 | 239,869 | 324,843 | 978 / 978 | 0 / 2,252,991 / 2 / 0 | 2105-10-04 to 2213-02-13 | mg/dL: 3,282,278 (100.0%) |
| 51006 | Urea Nitrogen | 3,189,474 | 238,019 | 322,136 | 1,793 / 1,794 | 0 / 1,810,251 / 2 / 0 | 2105-10-04 to 2213-02-13 | mg/dL: 3,189,474 (100.0%) |
| 50920 | Estimated GFR (MDRD equation) | 1,373,686 | 239,583 | 171,074 | 1,373,686 / 1,373,686 | 1,373,686 / 1,373,686 / 0 / 0 | 2105-10-04 to 2212-12-19 | <NULL>: 1,373,686 (100.0%) |
| 52026 | Estimated GFR (MDRD equation) | 3,720 | 3,356 | 895 | 3,720 / 3,720 | 3,720 / 3,720 / 0 / 0 | 2110-01-18 to 2212-05-24 | <NULL>: 3,720 (100.0%) |
| 50971 | Potassium | 3,150,261 | 233,334 | 322,010 | 1,603 / 1,603 | 0 / 2,868,773 / 2 / 0 | 2105-10-04 to 2213-02-13 | mEq/L: 3,150,261 (100.0%) |
| 50983 | Sodium | 3,119,778 | 233,212 | 320,439 | 439 / 439 | 0 / 2,741,391 / 2 / 0 | 2105-10-04 to 2213-02-13 | mEq/L: 3,119,778 (100.0%) |
| 50882 | Bicarbonate | 2,972,827 | 232,116 | 317,808 | 778 / 778 | 0 / 2,409,903 / 1 / 0 | 2105-10-04 to 2213-02-13 | mEq/L: 2,972,827 (100.0%) |
| 50893 | Calcium, Total | 2,190,816 | 165,643 | 288,520 | 296 / 296 | 0 / 1,540,032 / 1 / 0 | 2105-10-04 to 2213-02-13 | mg/dL: 2,190,816 (100.0%) |
| 50960 | Magnesium | 2,154,209 | 158,136 | 294,137 | 305 / 305 | 0 / 1,984,497 / 1 / 0 | 2105-10-04 to 2213-02-13 | mg/dL: 2,154,209 (100.0%) |
| 51221 | Hematocrit | 3,325,700 | 243,057 | 336,978 | 7,561 / 7,562 | 0 / 1,022,267 / 0 / 0 | 2105-01-19 to 2213-02-13 | %: 3,325,700 (100.0%) |
| 51222 | Hemoglobin | 3,188,835 | 242,733 | 329,516 | 5,406 / 5,406 | 0 / 910,411 / 0 / 0 | 2105-01-19 to 2213-02-13 | g/dL: 3,188,835 (100.0%) |
| 51301 | White Blood Cells | 3,171,798 | 242,689 | 329,274 | 7,367 / 7,372 | 0 / 2,078,661 / 0 / 0 | 2105-01-19 to 2213-02-13 | K/uL: 3,171,798 (100.0%) |
| 51265 | Platelet Count | 3,216,656 | 242,794 | 331,662 | 10,318 / 10,319 | 0 / 2,265,433 / 0 / 0 | 2105-01-19 to 2213-02-13 | K/uL: 3,216,656 (100.0%) |
| 50963 | NTproBNP | 66,944 | 28,816 | 17,629 | 2,495 / 2,495 | 0 / 18,890 / 0 / 0 | 2109-04-03 to 2212-08-27 | pg/mL: 66,944 (100.0%) |
| 50889 | C-Reactive Protein | 119,742 | 42,187 | 21,546 | 1,844 / 1,844 | 31 / 56,476 / 0 / 0 | 2105-01-19 to 2213-02-13 | mg/L: 119,711 (100.0%); <NULL>: 31 (0.0%) |

## 3. Timing relative to admission

Each measurement's relative-time category is assigned as follows: earlier calendar date than linked `admittime` = `PREVIOUS-ADMISSION / PRE-BASELINE`; same calendar date = `SAME-DAY / AMBIGUOUS`; after admission and no later than linked discharge = `AFTER ADMISSION`; later than discharge = `AFTER DISCHARGE`. Unlinked events are not forced into one of these categories.

### 3.1 Timing classifications by itemid

Counts below partition the extracted rows. The extra 'no admission link' category is necessary because 16.37 million extracted rows have null `hadm_id`; it is not evidence that those values are pre-admission or outpatient.

| Itemid | Factor | Previous/pre-baseline | Same-day ambiguous | After admission | After discharge | No admission link | Missing charttime |
|---:|---|---:|---:|---:|---:|---:|---:|
| 50904 | Cholesterol, HDL | 417 | 4,400 | 17,660 | 6 | 221,773 | 0 |
| 50905 | Cholesterol, LDL, Calculated | 396 | 4,141 | 16,670 | 5 | 201,098 | 0 |
| 50906 | Cholesterol, LDL, Measured | 60 | 439 | 1,715 | 0 | 37,068 | 0 |
| 50907 | Cholesterol, Total | 421 | 4,587 | 18,276 | 6 | 226,958 | 0 |
| 51000 | Triglycerides | 570 | 5,550 | 31,651 | 19 | 212,211 | 0 |
| 50903 | Cholesterol Ratio (Total/HDL) | 412 | 4,353 | 17,345 | 5 | 221,214 | 0 |
| 50852 | % Hemoglobin A1c | 365 | 8,406 | 22,425 | 17 | 192,114 | 0 |
| 50931 | Glucose | 47,572 | 119,674 | 1,667,259 | 999 | 914,058 | 0 |
| 50912 | Creatinine | 48,878 | 127,385 | 1,715,362 | 1,024 | 1,389,629 | 0 |
| 50920 | Estimated GFR (MDRD equation) | 42,845 | 44,599 | 147,719 | 67 | 1,138,456 | 0 |
| 52026 | Estimated GFR (MDRD equation) | 374 | 148 | 404 | 2 | 2,792 | 0 |
| 51006 | Urea Nitrogen | 48,882 | 125,224 | 1,703,611 | 1,015 | 1,310,742 | 0 |
| 50971 | Potassium | 47,807 | 134,132 | 1,762,622 | 1,060 | 1,204,640 | 0 |
| 50983 | Sodium | 47,735 | 129,847 | 1,747,876 | 1,053 | 1,193,267 | 0 |
| 50882 | Bicarbonate | 47,675 | 124,009 | 1,686,468 | 1,003 | 1,113,672 | 0 |
| 50893 | Calcium, Total | 14,706 | 104,945 | 1,478,166 | 883 | 592,116 | 0 |
| 50960 | Magnesium | 14,738 | 112,817 | 1,575,598 | 919 | 450,137 | 0 |
| 51221 | Hematocrit | 48,759 | 148,285 | 1,714,770 | 1,050 | 1,412,836 | 0 |
| 51222 | Hemoglobin | 48,591 | 131,090 | 1,607,141 | 981 | 1,401,032 | 0 |
| 51301 | White Blood Cells | 48,654 | 129,973 | 1,597,270 | 983 | 1,394,918 | 0 |
| 51265 | Platelet Count | 48,583 | 134,187 | 1,625,954 | 1,003 | 1,406,929 | 0 |
| 50963 | NTproBNP | 4,215 | 3,852 | 12,483 | 18 | 46,376 | 0 |
| 50889 | C-Reactive Protein | 2,046 | 3,841 | 26,018 | 10 | 87,827 | 0 |

Overall timing totals: **564,701** previous/pre-baseline linked rows; **1,605,884** same-day; **20,194,463** after admission; **12,128** after discharge; **16,371,863** without admission linkage; **0** missing charttime.

### 3.2 Hours relative to linked admission

Quantiles use only records with an admission-time link. Hours are calculated from exact timestamps; positive values include inpatient measurements, while negative values include pre-admission results. These are descriptive event-level quantiles, not baseline-value summaries.

| Itemid | Factor | q10 h | q25 h | Median h | q75 h | q90 h |
|---:|---|---:|---:|---:|---:|---:|
| 50904 | Cholesterol, HDL | 3.4 | 7.3 | 13.3 | 34.1 | 109.2 |
| 50905 | Cholesterol, LDL, Calculated | 3.4 | 7.3 | 13.2 | 33.2 | 104.4 |
| 50906 | Cholesterol, LDL, Measured | 3.0 | 7.6 | 14.6 | 41.3 | 133.6 |
| 50907 | Cholesterol, Total | 3.3 | 7.3 | 13.4 | 35.7 | 122.0 |
| 51000 | Triglycerides | 4.0 | 9.7 | 28.5 | 136.3 | 357.4 |
| 50903 | Cholesterol Ratio (Total/HDL) | 3.4 | 7.3 | 13.2 | 33.5 | 105.1 |
| 50852 | % Hemoglobin A1c | 2.5 | 5.8 | 13.2 | 36.4 | 101.9 |
| 50931 | Glucose | 8.6 | 28.0 | 77.2 | 182.5 | 395.5 |
| 50912 | Creatinine | 8.5 | 27.4 | 76.1 | 180.6 | 391.5 |
| 50920 | Estimated GFR (MDRD equation) | -5.1 | 1.9 | 24.9 | 180.6 | 372.5 |
| 52026 | Estimated GFR (MDRD equation) | -14.4 | -5.5 | 5.7 | 71.2 | 282.0 |
| 51006 | Urea Nitrogen | 8.5 | 27.5 | 76.5 | 181.0 | 392.4 |
| 50971 | Potassium | 8.6 | 27.6 | 76.8 | 181.5 | 392.3 |
| 50983 | Sodium | 8.7 | 27.9 | 77.1 | 182.0 | 393.0 |
| 50882 | Bicarbonate | 8.6 | 27.8 | 76.9 | 181.8 | 394.3 |
| 50893 | Calcium, Total | 10.0 | 30.1 | 80.4 | 194.9 | 416.4 |
| 50960 | Magnesium | 10.2 | 30.6 | 80.9 | 192.5 | 409.6 |
| 51221 | Hematocrit | 7.9 | 24.7 | 68.2 | 173.3 | 378.1 |
| 51222 | Hemoglobin | 7.7 | 25.4 | 70.7 | 176.2 | 387.3 |
| 51301 | White Blood Cells | 7.7 | 25.4 | 70.8 | 176.2 | 387.5 |
| 51265 | Platelet Count | 7.7 | 25.3 | 71.3 | 178.0 | 394.1 |
| 50963 | NTproBNP | -5.7 | 1.1 | 14.7 | 92.3 | 236.4 |
| 50889 | C-Reactive Protein | 2.8 | 11.1 | 39.7 | 128.8 | 284.1 |

### 3.3 Repeated measurements per linked admission

An admission is counted as repeated when it has more than one row for that itemid. Unlinked events cannot be assigned to an admission and are excluded from this repeat statistic.

| Itemid | Factor | Linked admissions with item | Repeated admissions | Median rows/admission | Maximum rows/admission |
|---:|---|---:|---:|---:|---:|
| 50904 | Cholesterol, HDL | 21,608 | 794 (3.7%) | 1.0 | 7 |
| 50905 | Cholesterol, LDL, Calculated | 20,512 | 654 (3.2%) | 1.0 | 7 |
| 50906 | Cholesterol, LDL, Measured | 2,120 | 83 (3.9%) | 1.0 | 4 |
| 50907 | Cholesterol, Total | 22,207 | 917 (4.1%) | 1.0 | 12 |
| 51000 | Triglycerides | 29,427 | 3,832 (13.0%) | 1.0 | 85 |
| 50903 | Cholesterol Ratio (Total/HDL) | 21,294 | 754 (3.5%) | 1.0 | 7 |
| 50852 | % Hemoglobin A1c | 30,188 | 986 (3.3%) | 1.0 | 4 |
| 50931 | Glucose | 317,303 | 242,523 (76.4%) | 3.0 | 480 |
| 50912 | Creatinine | 324,843 | 247,149 (76.1%) | 3.0 | 461 |
| 50920 | Estimated GFR (MDRD equation) | 171,074 | 34,721 (20.3%) | 1.0 | 44 |
| 52026 | Estimated GFR (MDRD equation) | 895 | 26 (2.9%) | 1.0 | 4 |
| 51006 | Urea Nitrogen | 322,136 | 245,500 (76.2%) | 3.0 | 468 |
| 50971 | Potassium | 322,010 | 248,877 (77.3%) | 3.0 | 486 |
| 50983 | Sodium | 320,439 | 246,788 (77.0%) | 3.0 | 480 |
| 50882 | Bicarbonate | 317,808 | 243,403 (76.6%) | 3.0 | 478 |
| 50893 | Calcium, Total | 288,520 | 212,462 (73.6%) | 3.0 | 463 |
| 50960 | Magnesium | 294,137 | 221,790 (75.4%) | 3.0 | 458 |
| 51221 | Hematocrit | 336,978 | 257,217 (76.3%) | 3.0 | 404 |
| 51222 | Hemoglobin | 329,516 | 249,105 (75.6%) | 3.0 | 393 |
| 51301 | White Blood Cells | 329,274 | 248,774 (75.6%) | 3.0 | 392 |
| 51265 | Platelet Count | 331,662 | 251,046 (75.7%) | 3.0 | 402 |
| 50963 | NTproBNP | 17,629 | 2,184 (12.4%) | 1.0 | 39 |
| 50889 | C-Reactive Protein | 21,546 | 4,582 (21.3%) | 1.0 | 105 |

## 4. Coverage under baseline rules A/B/C

All candidate rules select at most one baseline admission per patient. Pre-baseline coverage below counts patients (equal to baseline admissions for these rules) with at least one extracted event whose `charttime` is on an earlier calendar date than that baseline's `admittime`; same-day events are excluded as ambiguous. Coverage requires a non-null `valuenum`; these counts include rows with null `hadm_id`, because patient and timestamp still identify whether the event precedes that candidate baseline. No value after the baseline date is used. Window counts are within 30, 90, or 365 days before admission; 'any pre' has no lookback bound and may be stale.

| Rule | Candidate definition | Eligible baseline admissions / patients |
|---|---|---:|
| A | First non-MI admission per patient; does not require an MI-naive history | 174,055 / 174,055 |
| B | Most recent non-MI admission before first MI (retrospective; eligibility uses future MI) | 4,857 / 4,857 |
| C | First non-MI admission per patient, retained only if observation_end is at least 30 days after discharge | 71,110 / 71,110 |

**Rule C reconciliation:** the preceding feasibility review reported 20,222. Re-parsing the mixed date-only / timestamp `observation_end` strings and applying the stated rule yields 71,110. The timing audit uses the explicit definition above; this is a denominator reconciliation, not a baseline-rule selection. Rule B is retrospective by construction. Rule C conditions on observable follow-up and is not a neutral prospective eligibility rule.

### A. First non-MI admission (denominator: 174,055 patients / baseline admissions)

| Itemid | Factor | Any earlier date n (%) | Within 30d n (%) | Within 90d n (%) | Within 365d n (%) |
|---:|---|---:|---:|---:|---:|
| 50904 | Cholesterol, HDL | 30,790 (17.7%) | 3,741 (2.1%) | 9,510 (5.5%) | 26,117 (15.0%) |
| 50905 | Cholesterol, LDL, Calculated | 28,677 (16.5%) | 3,419 (2.0%) | 8,692 (5.0%) | 24,106 (13.8%) |
| 50906 | Cholesterol, LDL, Measured | 5,424 (3.1%) | 555 (0.3%) | 1,331 (0.8%) | 3,881 (2.2%) |
| 50907 | Cholesterol, Total | 31,485 (18.1%) | 3,914 (2.2%) | 9,797 (5.6%) | 26,751 (15.4%) |
| 51000 | Triglycerides | 29,468 (16.9%) | 3,690 (2.1%) | 9,167 (5.3%) | 24,902 (14.3%) |
| 50903 | Cholesterol Ratio (Total/HDL) | 30,717 (17.6%) | 3,723 (2.1%) | 9,466 (5.4%) | 26,046 (15.0%) |
| 50852 | % Hemoglobin A1c | 23,534 (13.5%) | 6,237 (3.6%) | 10,771 (6.2%) | 20,490 (11.8%) |
| 50931 | Glucose | 72,644 (41.7%) | 39,977 (23.0%) | 50,269 (28.9%) | 66,905 (38.4%) |
| 50912 | Creatinine | 80,227 (46.1%) | 48,017 (27.6%) | 58,572 (33.7%) | 75,232 (43.2%) |
| 50920 | Estimated GFR (MDRD equation) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 52026 | Estimated GFR (MDRD equation) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 51006 | Urea Nitrogen | 77,643 (44.6%) | 46,219 (26.6%) | 56,051 (32.2%) | 72,369 (41.6%) |
| 50971 | Potassium | 74,012 (42.5%) | 43,819 (25.2%) | 52,700 (30.3%) | 68,515 (39.4%) |
| 50983 | Sodium | 73,845 (42.4%) | 43,738 (25.1%) | 52,583 (30.2%) | 68,317 (39.3%) |
| 50882 | Bicarbonate | 71,483 (41.1%) | 42,504 (24.4%) | 50,780 (29.2%) | 65,732 (37.8%) |
| 50893 | Calcium, Total | 35,571 (20.4%) | 13,103 (7.5%) | 19,152 (11.0%) | 30,862 (17.7%) |
| 50960 | Magnesium | 26,700 (15.3%) | 11,736 (6.7%) | 15,382 (8.8%) | 22,685 (13.0%) |
| 51221 | Hematocrit | 83,169 (47.8%) | 50,851 (29.2%) | 62,148 (35.7%) | 78,375 (45.0%) |
| 51222 | Hemoglobin | 82,884 (47.6%) | 50,646 (29.1%) | 61,770 (35.5%) | 78,087 (44.9%) |
| 51301 | White Blood Cells | 82,848 (47.6%) | 50,603 (29.1%) | 61,715 (35.5%) | 78,038 (44.8%) |
| 51265 | Platelet Count | 82,915 (47.6%) | 50,633 (29.1%) | 61,764 (35.5%) | 78,092 (44.9%) |
| 50963 | NTproBNP | 3,500 (2.0%) | 1,547 (0.9%) | 2,003 (1.2%) | 2,972 (1.7%) |
| 50889 | C-Reactive Protein | 8,726 (5.0%) | 2,390 (1.4%) | 3,817 (2.2%) | 6,928 (4.0%) |

### B. Most recent non-MI before first MI (denominator: 4,857 patients / baseline admissions)

| Itemid | Factor | Any earlier date n (%) | Within 30d n (%) | Within 90d n (%) | Within 365d n (%) |
|---:|---|---:|---:|---:|---:|
| 50904 | Cholesterol, HDL | 2,002 (41.2%) | 251 (5.2%) | 569 (11.7%) | 1,410 (29.0%) |
| 50905 | Cholesterol, LDL, Calculated | 1,903 (39.2%) | 226 (4.7%) | 514 (10.6%) | 1,294 (26.6%) |
| 50906 | Cholesterol, LDL, Measured | 572 (11.8%) | 46 (0.9%) | 89 (1.8%) | 274 (5.6%) |
| 50907 | Cholesterol, Total | 2,057 (42.4%) | 263 (5.4%) | 591 (12.2%) | 1,451 (29.9%) |
| 51000 | Triglycerides | 2,004 (41.3%) | 256 (5.3%) | 572 (11.8%) | 1,398 (28.8%) |
| 50903 | Cholesterol Ratio (Total/HDL) | 1,997 (41.1%) | 250 (5.1%) | 565 (11.6%) | 1,404 (28.9%) |
| 50852 | % Hemoglobin A1c | 1,900 (39.1%) | 382 (7.9%) | 702 (14.5%) | 1,409 (29.0%) |
| 50931 | Glucose | 3,573 (73.6%) | 1,785 (36.8%) | 2,383 (49.1%) | 3,184 (65.6%) |
| 50912 | Creatinine | 3,792 (78.1%) | 2,133 (43.9%) | 2,786 (57.4%) | 3,509 (72.2%) |
| 50920 | Estimated GFR (MDRD equation) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 52026 | Estimated GFR (MDRD equation) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 51006 | Urea Nitrogen | 3,759 (77.4%) | 2,102 (43.3%) | 2,740 (56.4%) | 3,466 (71.4%) |
| 50971 | Potassium | 3,718 (76.5%) | 2,065 (42.5%) | 2,684 (55.3%) | 3,419 (70.4%) |
| 50983 | Sodium | 3,699 (76.2%) | 2,059 (42.4%) | 2,679 (55.2%) | 3,405 (70.1%) |
| 50882 | Bicarbonate | 3,637 (74.9%) | 1,991 (41.0%) | 2,596 (53.4%) | 3,327 (68.5%) |
| 50893 | Calcium, Total | 3,019 (62.2%) | 1,095 (22.5%) | 1,665 (34.3%) | 2,509 (51.7%) |
| 50960 | Magnesium | 2,866 (59.0%) | 1,009 (20.8%) | 1,514 (31.2%) | 2,304 (47.4%) |
| 51221 | Hematocrit | 3,746 (77.1%) | 2,114 (43.5%) | 2,722 (56.0%) | 3,441 (70.8%) |
| 51222 | Hemoglobin | 3,711 (76.4%) | 2,114 (43.5%) | 2,710 (55.8%) | 3,411 (70.2%) |
| 51301 | White Blood Cells | 3,707 (76.3%) | 2,106 (43.4%) | 2,703 (55.7%) | 3,406 (70.1%) |
| 51265 | Platelet Count | 3,735 (76.9%) | 2,111 (43.5%) | 2,711 (55.8%) | 3,427 (70.6%) |
| 50963 | NTproBNP | 1,051 (21.6%) | 247 (5.1%) | 413 (8.5%) | 720 (14.8%) |
| 50889 | C-Reactive Protein | 848 (17.5%) | 138 (2.8%) | 248 (5.1%) | 501 (10.3%) |

### C. First non-MI admission with >=30-day follow-up (denominator: 71,110 patients / baseline admissions)

| Itemid | Factor | Any earlier date n (%) | Within 30d n (%) | Within 90d n (%) | Within 365d n (%) |
|---:|---|---:|---:|---:|---:|
| 50904 | Cholesterol, HDL | 16,783 (23.6%) | 2,059 (2.9%) | 5,449 (7.7%) | 14,707 (20.7%) |
| 50905 | Cholesterol, LDL, Calculated | 15,622 (22.0%) | 1,895 (2.7%) | 4,965 (7.0%) | 13,553 (19.1%) |
| 50906 | Cholesterol, LDL, Measured | 2,997 (4.2%) | 306 (0.4%) | 786 (1.1%) | 2,281 (3.2%) |
| 50907 | Cholesterol, Total | 17,220 (24.2%) | 2,149 (3.0%) | 5,622 (7.9%) | 15,115 (21.3%) |
| 51000 | Triglycerides | 16,074 (22.6%) | 2,034 (2.9%) | 5,231 (7.4%) | 14,019 (19.7%) |
| 50903 | Cholesterol Ratio (Total/HDL) | 16,732 (23.5%) | 2,049 (2.9%) | 5,416 (7.6%) | 14,656 (20.6%) |
| 50852 | % Hemoglobin A1c | 12,166 (17.1%) | 2,762 (3.9%) | 5,456 (7.7%) | 10,779 (15.2%) |
| 50931 | Glucose | 35,441 (49.8%) | 18,106 (25.5%) | 23,833 (33.5%) | 33,026 (46.4%) |
| 50912 | Creatinine | 39,612 (55.7%) | 22,504 (31.6%) | 28,747 (40.4%) | 37,681 (53.0%) |
| 50920 | Estimated GFR (MDRD equation) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 52026 | Estimated GFR (MDRD equation) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| 51006 | Urea Nitrogen | 38,247 (53.8%) | 21,529 (30.3%) | 27,401 (38.5%) | 36,195 (50.9%) |
| 50971 | Potassium | 36,793 (51.7%) | 20,519 (28.9%) | 25,916 (36.4%) | 34,615 (48.7%) |
| 50983 | Sodium | 36,702 (51.6%) | 20,476 (28.8%) | 25,864 (36.4%) | 34,516 (48.5%) |
| 50882 | Bicarbonate | 35,415 (49.8%) | 19,738 (27.8%) | 24,802 (34.9%) | 33,114 (46.6%) |
| 50893 | Calcium, Total | 19,810 (27.9%) | 6,804 (9.6%) | 10,618 (14.9%) | 17,612 (24.8%) |
| 50960 | Magnesium | 14,480 (20.4%) | 5,556 (7.8%) | 7,916 (11.1%) | 12,497 (17.6%) |
| 51221 | Hematocrit | 40,878 (57.5%) | 23,928 (33.6%) | 30,234 (42.5%) | 38,965 (54.8%) |
| 51222 | Hemoglobin | 40,727 (57.3%) | 23,824 (33.5%) | 30,039 (42.2%) | 38,815 (54.6%) |
| 51301 | White Blood Cells | 40,700 (57.2%) | 23,794 (33.5%) | 30,002 (42.2%) | 38,780 (54.5%) |
| 51265 | Platelet Count | 40,749 (57.3%) | 23,816 (33.5%) | 30,040 (42.2%) | 38,823 (54.6%) |
| 50963 | NTproBNP | 2,115 (3.0%) | 782 (1.1%) | 1,085 (1.5%) | 1,797 (2.5%) |
| 50889 | C-Reactive Protein | 4,550 (6.4%) | 1,067 (1.5%) | 1,889 (2.7%) | 3,704 (5.2%) |

## 5. Candidate ranking and pre-existing-factor assessment

Classifications consider timing, biological interpretation, coverage, repeated inpatient testing, and whether the observed values could plausibly be a pre-existing factor. 'Possible' means a separately defined, strictly antecedent measurement could be investigated; it does not mean the factor is validated or selected. No factor receives the 'promising' label yet: antecedent lipid/HbA1c coverage is limited, while the high-volume routine labs are predominantly acute inpatient measurements or may reflect prior acute admissions.

| Follow-up tier | Itemid | Factor | Classification | Rationale / principal concern |
|---:|---:|---|---|---|
| 1 | 50852 | % Hemoglobin A1c | B. POSSIBLE BUT TIMING LIMITED | HbA1c reflects antecedent glycemia biologically, but pre-baseline measurement coverage is modest and test ordering is selective. |
| 2 | 50904 | Cholesterol, HDL | B. POSSIBLE BUT TIMING LIMITED | HDL is interpretable, and earlier measurements exist; most candidate baselines lack a recent antecedent value. |
| 2 | 50905 | Cholesterol, LDL, Calculated | B. POSSIBLE BUT TIMING LIMITED | Calculated LDL is interpretable; strictly antecedent coverage is modest and values are mostly unlinked to an admission. |
| 2 | 50907 | Cholesterol, Total | B. POSSIBLE BUT TIMING LIMITED | Total cholesterol has a plausible baseline interpretation, but recent pre-baseline coverage is modest. |
| 2 | 51000 | Triglycerides | B. POSSIBLE BUT TIMING LIMITED | Triglycerides are interpretable, but recent antecedent coverage is limited and fasting status is not established. |
| 3 | 50912 | Creatinine | B. POSSIBLE BUT TIMING LIMITED | Prior creatinine measurements are available for many; values linked to the current admission are predominantly post-admission and may reflect acute kidney injury. |
| 3 | 51006 | Urea Nitrogen | B. POSSIBLE BUT TIMING LIMITED | Antecedent BUN values are common, but previous inpatient illness can make them poor measures of stable baseline renal function. |
| 4 | 50931 | Glucose | C. MOSTLY ACUTE/DOWNSTREAM | Blood glucose is predominantly measured after admission; acute stress and fasting status complicate baseline interpretation. |
| 5 | 50882 | Bicarbonate | C. MOSTLY ACUTE/DOWNSTREAM | Bicarbonate is frequently repeated during admission; acute illness and treatment strongly affect values. |
| 5 | 50893 | Calcium, Total | C. MOSTLY ACUTE/DOWNSTREAM | Calcium is predominantly measured after admission and often repeated in acute care. |
| 5 | 50960 | Magnesium | C. MOSTLY ACUTE/DOWNSTREAM | Magnesium is predominantly measured after admission and repeatedly during inpatient care. |
| 5 | 50971 | Potassium | C. MOSTLY ACUTE/DOWNSTREAM | Potassium is frequently repeated during admission and is mostly recorded after admission. |
| 5 | 50983 | Sodium | C. MOSTLY ACUTE/DOWNSTREAM | Sodium is frequently repeated during admission and is mostly recorded after admission. |
| 5 | 51221 | Hematocrit | C. MOSTLY ACUTE/DOWNSTREAM | Hematocrit is a high-frequency inpatient measure and can reflect bleeding, fluids, or acute illness. |
| 5 | 51222 | Hemoglobin | C. MOSTLY ACUTE/DOWNSTREAM | Hemoglobin is a high-frequency inpatient measure and can reflect acute illness, bleeding, or treatment. |
| 5 | 51265 | Platelet Count | C. MOSTLY ACUTE/DOWNSTREAM | Platelets are measured predominantly after admission and vary with acute illness and treatment. |
| 5 | 51301 | White Blood Cells | C. MOSTLY ACUTE/DOWNSTREAM | WBC is measured predominantly after admission and is highly sensitive to acute inflammation/infection. |
| 5 | 50963 | NTproBNP | C. MOSTLY ACUTE/DOWNSTREAM | NT-proBNP is sparse and often measured during an acute cardiopulmonary evaluation. |
| 5 | 50889 | C-Reactive Protein | C. MOSTLY ACUTE/DOWNSTREAM | CRP is sparse, selectively ordered, and predominantly associated with inpatient/acute evaluation. |
| 6 | 50906 | Cholesterol, LDL, Measured | D. INSUFFICIENT DATA | Measured LDL has much lower sample size and low antecedent coverage than calculated LDL; keep distinct, do not merge. |
| 6 | 50920 | Estimated GFR (MDRD equation) | D. INSUFFICIENT DATA | All rows have null value and valuenum in the extracted database; no quantitative eGFR can be analyzed. |
| 6 | 52026 | Estimated GFR (MDRD equation) | D. INSUFFICIENT DATA | All rows have null value and valuenum; small catalogue volume and no analyzable value. |
| 7 | 50903 | Cholesterol Ratio (Total/HDL) | E. EXCLUDE | Derived total/HDL ratio, not a distinct direct lipid factor; severe timing/coverage limitations. |

**Best current candidate group:** antecedent lipid measurements and HbA1c are the most interpretable candidates for a pre-existing metabolic state, but only as timing-restricted, coverage-limited possibilities. No single lipid is selected. Creatinine/BUN are also possible only when an antecedent measurement is used; a value from the index admission must not be relabeled baseline.

## 6. Lipid-specific results

Items 50904 (HDL), 50905 (calculated LDL), 50906 (measured LDL), 50907 (total cholesterol), and 51000 (triglycerides) were found in the actual catalogue. All have a single observed unit (`mg/dL`). The ratio, 50903, is retained in the extract but excluded as a separate candidate because it is a derived ratio, not a distinct lipid measurement. Calculated and measured LDL are reported separately and are not combined.

| Itemid | Lipid | Total measurements | Unique patients | Linked admissions | Null valuenum | Pre-baseline coverage under A (any / 30d / 90d / 365d) | B (any / 30d / 90d / 365d) | C (any / 30d / 90d / 365d) |
|---:|---|---:|---:|---:|---:|---|---|---|
| 50904 | Cholesterol, HDL | 244,256 | 82,555 | 21,608 | 346 | 30,790 (17.7%) / 3,741 (2.1%) / 9,510 (5.5%) / 26,117 (15.0%) | 2,002 (41.2%) / 251 (5.2%) / 569 (11.7%) / 1,410 (29.0%) | 16,783 (23.6%) / 2,059 (2.9%) / 5,449 (7.7%) / 14,707 (20.7%) |
| 50905 | Cholesterol, LDL, Calculated | 222,310 | 78,444 | 20,512 | 25 | 28,677 (16.5%) / 3,419 (2.0%) / 8,692 (5.0%) / 24,106 (13.8%) | 1,903 (39.2%) / 226 (4.7%) / 514 (10.6%) / 1,294 (26.6%) | 15,622 (22.0%) / 1,895 (2.7%) / 4,965 (7.0%) / 13,553 (19.1%) |
| 50906 | Cholesterol, LDL, Measured | 39,282 | 19,339 | 2,120 | 1,197 | 5,424 (3.1%) / 555 (0.3%) / 1,331 (0.8%) / 3,881 (2.2%) | 572 (11.8%) / 46 (0.9%) / 89 (1.8%) / 274 (5.6%) | 2,997 (4.2%) / 306 (0.4%) / 786 (1.1%) / 2,281 (3.2%) |
| 50907 | Cholesterol, Total | 250,248 | 83,893 | 22,207 | 29 | 31,485 (18.1%) / 3,914 (2.2%) / 9,797 (5.6%) / 26,751 (15.4%) | 2,057 (42.4%) / 263 (5.4%) / 591 (12.2%) / 1,451 (29.9%) | 17,220 (24.2%) / 2,149 (3.0%) / 5,622 (7.9%) / 15,115 (21.3%) |
| 51000 | Triglycerides | 250,001 | 84,519 | 29,427 | 31 | 29,468 (16.9%) / 3,690 (2.1%) / 9,167 (5.3%) / 24,902 (14.3%) | 2,004 (41.3%) / 256 (5.3%) / 572 (11.8%) / 1,398 (28.8%) | 16,074 (22.6%) / 2,034 (2.9%) / 5,231 (7.4%) / 14,019 (19.7%) |

Interpretation: antecedent lipid results are not uniformly available near time zero. For rule A, only a few percent of patients have a prior-date result within 30 days, and roughly 14-15% have one within 365 days for HDL/calculated LDL/total cholesterol/triglycerides; measured LDL is substantially sparser. Most lipid rows have null `hadm_id`, so exact patient-level timing is available but their encounter context cannot be proven from these files. A high proportion of unlinked rows must not be called 'outpatient' without independent evidence. Unit consistency is good; completeness and temporal coverage are limiting.

## 7. HbA1c and glucose

| Itemid | Factor | Measurements | Unique patients | Rule A pre-date (any / 30d / 90d / 365d) | Linked-event median hours from admission | Timing assessment |
|---:|---|---:|---:|---|---:|---|
| 50852 | % Hemoglobin A1c | 223,327 | 74,733 | 23,534 (13.5%) / 6,237 (3.6%) / 10,771 (6.2%) / 20,490 (11.8%) | 13.2 h | B. POSSIBLE BUT TIMING LIMITED |
| 50931 | Glucose | 2,749,562 | 234,501 | 72,644 (41.7%) / 39,977 (23.0%) / 50,269 (28.9%) / 66,905 (38.4%) | 77.2 h | C. MOSTLY ACUTE/DOWNSTREAM |

HbA1c is not interchangeable with contemporaneous glucose: it is a longer-term glycemia marker, but an HbA1c measured during admission may be selectively ordered and its timestamp alone does not establish that the recorded test was collected before the baseline. Strictly antecedent HbA1c exists but is limited in the broad rule-A cohort (20,497 within 365 days; 6,239 within 30 days). Blood glucose is a poor chronic-glycemia proxy here: the linked-event median is about 77 hours after admission and repeated acute measurements are common.

## 8. Renal results

| Itemid | Renal factor | Measurements | Unique patients | Rule A pre-date any / 30d / 90d / 365d | Linked-event timing | Missing numeric values |
|---:|---|---:|---:|---|---|---:|
| 50912 | Creatinine | 3,282,278 | 239,869 | 80,227 (46.1%) / 48,017 (27.6%) / 58,572 (33.7%) / 75,232 (43.2%) | median 76.1 h; after admission 1,715,362 linked rows | 978 |
| 50920 | Estimated GFR (MDRD equation) | 1,373,686 | 239,583 | 0 (0.0%) / 0 (0.0%) / 0 (0.0%) / 0 (0.0%) | median 24.9 h; after admission 147,719 linked rows | 1,373,686 |
| 52026 | Estimated GFR (MDRD equation) | 3,720 | 3,356 | 0 (0.0%) / 0 (0.0%) / 0 (0.0%) / 0 (0.0%) | median 5.7 h; after admission 404 linked rows | 3,720 |
| 51006 | Urea Nitrogen | 3,189,474 | 238,019 | 77,643 (44.6%) / 46,219 (26.6%) / 56,051 (32.2%) / 72,369 (41.6%) | median 76.5 h; after admission 1,703,611 linked rows | 1,794 |

Creatinine and BUN are measured repeatedly during hospitalization (linked-event medians are about 76 hours after admission; around half or more of linked records are post-admission). Their high overall volume therefore reflects inpatient monitoring and does not itself establish baseline renal function. Antecedent values exist for a meaningful subset, but may themselves come from prior acute admissions; stable chronic renal function is not distinguished. Itemids 50920 and 52026 are both labeled estimated GFR in `d_labitems`, but every extracted row has null `value` and `valuenum` (1,373,686 and 3,720 rows respectively), so these are not analyzable numeric eGFR measures.

## 9. Variables to exclude or defer

- **Exclude 50903 cholesterol ratio as a standalone candidate**: it is a derived total/HDL ratio and does not add an independent direct lipid measure here. It remains in the compact extract for transparent accounting. Do not create a lipid composite from this audit.
- **Defer 50906 measured LDL**: lower measurement volume and antecedent coverage than calculated LDL; keep it distinct, and do not combine without a prespecified clinical rationale.
- **Do not use 50920 or 52026 as eGFR**: all value fields are null.
- **Do not use admission glucose, electrolytes, CBC, CRP, or NT-proBNP as baseline exposures merely because coverage is high**: their linked rows are predominantly collected after admission or are sparse/selectively ordered. An antecedent-only analysis would be a different, timing-restricted candidate and needs explicit measurement rules.

## 10. Exact remaining blockers

1. **No selected lookback window or measurement summarization rule.** The audit reports prior-date, 30-day, 90-day, and 365-day coverage but does not choose the 'last value', mean, or other summary.
2. **Encounter context is absent for many labevents.** 16,371,863 rows have null `hadm_id`; patient-level timestamps allow an earlier-than-baseline check, but do not establish whether they were outpatient, from an ED visit, or otherwise linked to a care episode.
3. **Same-day measurements remain ambiguous.** Date-only proximity does not establish whether a value was measured before or after index presentation; those records were excluded from strict antecedent coverage.
4. **Prior-admission measurements may reflect acute illness.** A result preceding the index admission is temporally prior but is not necessarily a stable chronic factor.
5. **Testing/selection bias and missingness remain.** Lipids, HbA1c, CRP, and NT-proBNP are selectively measured; coverage is not random.
6. **No numeric eGFR values in the extracted rows.** A derived eGFR would require a separately specified computation and covariate handling; none was fabricated.

## 11. Recommended next scientific decision

Do not select a final baseline rule or causal exposure from this audit. First decide (without looking at future MI outcomes) a clinically defensible antecedent window and whether the exposure is the most recent valid pre-baseline value. Then review the resulting candidate-specific coverage under rules A/B/C, treating unlinked event provenance and same-day measurements conservatively. The strongest next candidate review is separately timed HbA1c and each lipid (HDL, calculated LDL, measured LDL, total cholesterol, triglycerides), followed by antecedent-only creatinine/BUN. No causal effects, DAG, adjustment set, or causal discovery were run.
