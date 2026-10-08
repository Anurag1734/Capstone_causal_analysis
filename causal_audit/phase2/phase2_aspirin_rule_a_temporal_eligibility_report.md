# Aspirin Treatment-Specific ECG Temporal Eligibility Audit

This audit is intentionally limited to Rule-A ECG selection and eligibility checks for the aspirin discovery question. It does not create the final Phase 7 discovery matrix, does not fit preprocessing, and does not perform causal discovery.

## Rule-A selection

- Total admissions: 191369
- Admissions with valid Rule-A ECG: 191369
- Admissions without valid ECG: 0
- Selection method: Earliest valid ecg_time within each hadm_id; ties broken by smallest study_id.
- Unique study_id selected by Rule-A: True
- Admissions with duplicate earliest ECG timestamps: 141
- Distribution of selected ECGs per admission: {'1': 191369}

## Engineered ECG feature block

- Block size: 95 engineered ECG features
- Status: ASSUMED PRE-TREATMENT UNDER RULE A
- Temporal status: Rule A is an assumed/fallback index-ECG rule and does not establish verified pre-treatment timing.
- The block is technically available for the selected Rule-A ECG rows, but it is not causally verified as pre-treatment because Rule A is an assumed/fallback index-ECG rule.

## z_ecg block

- Block size: 64 z_ecg variables
- Status: TEMPORALLY UNRESOLVED
- Provenance status: DISTINCT BLOCKER: VAE provenance remains unresolved even if the Rule-A linkage itself is technically valid.
- Technical availability does not establish temporal eligibility or VAE provenance quality.

## Clinical baseline variables

| Variable | Temporal status | Known before Rule-A ECG | Baseline role |
|---|---|---|---|
| Anchor age | potentially eligible | Likely yes for age/sex at admission-level; history variables require source-window verification | potentially eligible for design, not yet confirmed as a valid causal baseline variable |
| Sex | potentially eligible | Likely yes for age/sex at admission-level; history variables require source-window verification | potentially eligible for design, not yet confirmed as a valid causal baseline variable |
| Diabetes | temporally unresolved | Not independently established from the available project documentation for this aspirin causal baseline | treatment-specific baseline status unresolved |
| Hypertension | temporally unresolved | Not independently established from the available project documentation for this aspirin causal baseline | treatment-specific baseline status unresolved |
| CKD | temporally unresolved | Not independently established from the available project documentation for this aspirin causal baseline | treatment-specific baseline status unresolved |
| Prior MI | temporally unresolved | Not independently established from the available project documentation for this aspirin causal baseline | treatment-specific baseline status unresolved |

## Treatment outcome status

- aspirin_before: pre-admission/window-coded treatment indicator according to master documentation
- is_MI: candidate outcome; provenance remains unresolved
- Label_Troponin: cohort/label metadata; not a feature
- index_mi_time: event-time variable; not baseline covariate
- time_diff_hours: not a universal MI clock; for controls uses admission-time anchor/fallback

## Leakage audit

- Outcome leakage: No direct use of is_MI, Label_Troponin, index_mi_time, or time_diff_hours in Rule-A selection; still, the outcome provenance remains unresolved.
- Treatment leakage: No direct use of aspirin_before in Rule-A ECG selection; the exposure label remains temporally unresolved and cannot be treated as verified pre-treatment timing.
- Troponin leakage: Label_Troponin is not used as a Rule-A selection variable and is not used as a baseline feature.
- VAE provenance leakage: VAE provenance remains unresolved; the latent z_ecg block is not treated as verified baseline evidence.

## Final eligibility table

| Variable/group | Role | Rule-A availability | Temporal status | Provenance status | Leakage status | Eligible for aspirin discovery? | Reason |
|---|---|---|---|---|---|---|---|
| anchor_age | demographic | Yes | potentially eligible | Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join. | No direct outcome leakage in Rule-A selection. | Potentially eligible for design-only use; not yet causal baseline evidence. | Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question. |
| sex_male | demographic | Yes | potentially eligible | Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join. | No direct outcome leakage in Rule-A selection. | Potentially eligible for design-only use; not yet causal baseline evidence. | Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question. |
| diabetes | prior-history | Yes | temporally unresolved | Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join. | No direct outcome leakage in Rule-A selection. | Potentially eligible for design-only use; not yet causal baseline evidence. | Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question. |
| hypertension | prior-history | Yes | temporally unresolved | Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join. | No direct outcome leakage in Rule-A selection. | Potentially eligible for design-only use; not yet causal baseline evidence. | Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question. |
| ckd | prior-history | Yes | temporally unresolved | Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join. | No direct outcome leakage in Rule-A selection. | Potentially eligible for design-only use; not yet causal baseline evidence. | Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question. |
| prior_mi | prior-history | Yes | temporally unresolved | Phase F master schema; age/sex from demographics joined on SubjectID; prior-history variables from clinical history join. | No direct outcome leakage in Rule-A selection. | Potentially eligible for design-only use; not yet causal baseline evidence. | Available at admission level and not used to choose Rule A, but causal baseline role is not yet verified for the aspirin question. |
| aspirin_before | treatment exposure | Yes | treatment-specific baseline status unresolved | Pre-admission/window-coded indicator in project documentation; not verified administration before Rule-A ECG. | No direct timing leakage; exact assignment time remains unresolved. | No | Documented as a pre-admission/window-coded indicator, not as verified aspirin administration before the Rule-A ECG. |
| 95 ECG feature block | ECG-derived features | Yes | ASSUMED PRE-TREATMENT UNDER RULE A | ECG feature pipeline provenance remains outside the current local workspace audit. | No direct leakage from outcome or treatment timing in selection, but Rule-A temporal assumption is fallback-only. | No | Technically available at the Rule-A ECG, but not causally verified as pre-treatment; temporal status remains assumed/fallback. |
| 64 z_ecg block | latent ECG representation | Yes | TEMPORALLY UNRESOLVED | VAE provenance unresolved; training/checkpoint/preprocessing status remains unresolved. | No direct leakage in selection, but provenance and treatment-time uncertainty remain unresolved. | No | Technical availability at Rule-A ECG does not establish causally verified pre-treatment status or provenance quality. |
| is_MI | outcome/temporal | Yes | outcome-derived / not baseline | Label_Troponin/is_MI provenance unresolved; index_mi_time and time_diff_hours are not baseline covariates. | Not used in Rule-A selection. | No | Outcome and temporal variables are not valid baseline adjustment variables and are excluded from a treatment-specific rule-A design. |
| Label_Troponin | outcome/temporal | Yes | outcome-derived / not baseline | Label_Troponin/is_MI provenance unresolved; index_mi_time and time_diff_hours are not baseline covariates. | Not used in Rule-A selection. | No | Outcome and temporal variables are not valid baseline adjustment variables and are excluded from a treatment-specific rule-A design. |
| index_mi_time | outcome/temporal | Yes | outcome-derived / not baseline | Label_Troponin/is_MI provenance unresolved; index_mi_time and time_diff_hours are not baseline covariates. | Not used in Rule-A selection. | No | Outcome and temporal variables are not valid baseline adjustment variables and are excluded from a treatment-specific rule-A design. |
| time_diff_hours | outcome/temporal | Yes | outcome-derived / not baseline | Label_Troponin/is_MI provenance unresolved; index_mi_time and time_diff_hours are not baseline covariates. | Not used in Rule-A selection. | No | Outcome and temporal variables are not valid baseline adjustment variables and are excluded from a treatment-specific rule-A design. |
| aspirin_during | downstream/acute treatment | Yes | downstream or acute episode marker; not a verified pre-treatment baseline | Available in master schema but not a pre-treatment aspirin baseline for the causal question. | Not used in rule-A selection; should not be treated as baseline treatment. | No | These variables are downstream or acute clinical markers and are not a valid pre-treatment baseline for aspirin-specific design. |
| aspirin_after | downstream/acute treatment | No | downstream or acute episode marker; not a verified pre-treatment baseline | Available in master schema but not a pre-treatment aspirin baseline for the causal question. | Not used in rule-A selection; should not be treated as baseline treatment. | No | These variables are downstream or acute clinical markers and are not a valid pre-treatment baseline for aspirin-specific design. |
| vasopressor_during | downstream/acute treatment | Yes | downstream or acute episode marker; not a verified pre-treatment baseline | Available in master schema but not a pre-treatment aspirin baseline for the causal question. | Not used in rule-A selection; should not be treated as baseline treatment. | No | These variables are downstream or acute clinical markers and are not a valid pre-treatment baseline for aspirin-specific design. |
| mech_vent_during | downstream/acute treatment | Yes | downstream or acute episode marker; not a verified pre-treatment baseline | Available in master schema but not a pre-treatment aspirin baseline for the causal question. | Not used in rule-A selection; should not be treated as baseline treatment. | No | These variables are downstream or acute clinical markers and are not a valid pre-treatment baseline for aspirin-specific design. |

## Decision record

## 1. RULE-A RESULT
191369 admissions received a valid Rule-A ECG and the selection was unique by hadm_id using the earliest valid ecg_time and deterministic tie-break on study_id.

## 2. ECG FEATURE ELIGIBILITY
The 95 engineered ECG features are technically available for the Rule-A-selected ECG rows, but their status remains ASSUMED PRE-TREATMENT UNDER RULE A rather than causally verified pre-treatment.

## 3. z_ecg ELIGIBILITY
The 64 z_ecg variables are technically available for the selected Rule-A ECG rows, but they remain TEMPORALLY UNRESOLVED and their VAE provenance remains a separate blocker. Technical availability does not equal causal eligibility.

## 4. CLINICAL BASELINE ELIGIBILITY
Age and sex are available and likely known at admission, but they are not yet established as valid causal confounders for the aspirin causal question. Diabetes, hypertension, CKD, and prior MI remain treatment-specific baseline status unresolved.

## 5. ASPIRIN EXPOSURE STATUS
aspirin_before is a pre-admission/window-coded treatment indicator according to the project documentation. It is not verified administration before the Rule-A ECG and does not establish treatment time zero.

## 6. OUTCOME STATUS
is_MI and Label_Troponin remain outcome-related variables with unresolved provenance; index_mi_time and time_diff_hours are not baseline covariates and must not be used for Rule-A baseline adjustment.

## 7. FINAL BLOCKERS
- Rule A is a fallback assumption, not verified pre-treatment timing.
- aspirin_before remains a pre-admission/window-coded indicator and does not establish exact aspirin assignment timing.
- z_ecg provenance remains unresolved.
- No defensible aspirin-specific temporal treatment-time zero is available from the current project data.

## 8. NEXT ACTION
Proceed to the next prerequisite in the minimal roadmap rather than continuing the same timestamp search.

## Integrity validation
- Master file hashes unchanged: True
- Phase artifact hashes unchanged: True
- Rule-A uses no outcome/treatment to select ECG: True
- No preprocessing fitted: True