# Phase 5 — z_ecg Representation and Causal-Role Audit

## A. Phase 5 objective

Audit the provenance, representation properties, and possible causal roles of the 64-dimensional `z_ecg` block. Representation choice and causal-role assessment are kept separate. This is not causal modeling.

## B. VAE provenance audit

### Phase 5 Input Audit

| Item | Status | Evidence |
|---|---|---|
| z_ecg source | PARTIALLY VERIFIED | Local VAE documentation describes 12-lead raw waveform input and a Conv1D beta-VAE; VAE implementation and waveform files are absent. |
| Exact VAE architecture | PARTIALLY VERIFIED | Documentation specifies layer widths, kernels, strides, activations, and 82,448,332 parameters; no model source/checkpoint is present to verify exact implementation or padding. |
| Latent dimension | VERIFIED | The master parquet schema contains 64 columns from z_ecg_1 through z_ecg_64. |
| Stored VAE output | PARTIALLY VERIFIED | Documentation says the deterministic encoder mean mu is saved; extraction source is absent. |
| Embedding generation | PARTIALLY VERIFIED | Documentation describes encoder-only extraction with a best checkpoint reported as epoch 109; extraction code and run artifacts are absent. |
| Embedding join key | PARTIALLY VERIFIED | Documentation identifies study_id; the master has unique study_id rows and all 64 dimensions, but the source embedding join cannot be reconstructed locally. |
| Waveform preprocessing | UNRESOLVED | Documentation reports 12 leads x 5000 samples at 500 Hz and WFDB/HDF5 conversion, but local dataset/conversion code and waveform arrays are absent; filtering, normalization, resampling, and learned parameters cannot be checked. |
| Feature preprocessing before VAE | PARTIALLY VERIFIED | Documentation depicts raw waveforms as VAE input and discusses engineered ECG features separately; no source code establishes the exact waveform-to-model transform. |
| VAE train/validation/test split | PARTIALLY VERIFIED | Master parquet split sizes and labels are directly inspectable; VAE documentation label counts disagree with current validation/test parquet counts, and training code/logs are absent. |
| Subject separation across VAE splits | PARTIALLY VERIFIED | SubjectID sets in the actual master train/validation/test files are disjoint; actual VAE loader membership is not verifiable. |
| Checkpoint identity and use | PARTIALLY VERIFIED | Documentation names a checkpoint run and best epoch 109, but the checkpoint and extraction run metadata are absent, so its use for these embeddings is unverified. |
| VAE training membership | UNRESOLVED | No VAE training code, logs, split manifests, or checkpoint metadata are locally present. |
| Validation/test ECGs in optimization | UNRESOLVED | Documentation describes validation loss/checkpoint selection and a separate test split, but absent training source/logs prevent confirmation of gradient or model-selection use. |
| Post-MI ECGs in VAE training | UNRESOLVED | Documentation says MI_Post-Incident was excluded, but actual training membership and waveform-to-label map are absent; master dataset itself has no MI_Post-Incident label category. |
| Train-only preprocessing fitting | UNRESOLVED | No preprocessing code or fitted parameter artifacts are present to establish fit partition or validation/test influence. |
| Outcome/treatment independence | NOT AVAILABLE | NOT VERIFIED — documentation describes the VAE as unsupervised, but the training/dataloader source is unavailable; use of labels, treatment, diagnosis, or downstream event information cannot be confirmed. |

The local VAE document describes a Conv1D β-VAE using 12×5000 ECG waveforms, 82,448,332 reported parameters, latent size 64, β=4 and free-bits=2 per dimension. It states that the deterministic encoder mean (`mu`) was extracted. These architecture and extraction details are **documentation-only**, not verified against executable source or a checkpoint.

Documentation identifies `best_model.pt` at epoch 109, while also reporting training stopped at epoch 129; its overview says 109 epochs trained. The documentation reports best checkpoint epoch 109 and training stopping at epoch 129; its overview also says 109 epochs trained. Without run files, the actual selected checkpoint and completed epoch count cannot be independently confirmed.

Expected source/data artifact presence:

| Artifact | Available locally | Expected path |
|---|---|---|
| VAE model source | False | C:\Users\anura\OneDrive\Desktop\capstone2\src\models\vae_conv1d.py |
| VAE training source | False | C:\Users\anura\OneDrive\Desktop\capstone2\src\models\train_vae.py |
| Embedding extraction source | False | C:\Users\anura\OneDrive\Desktop\capstone2\src\models\extract_embeddings.py |
| Waveform dataset source | False | C:\Users\anura\OneDrive\Desktop\capstone2\src\data\ecg_dataset.py |
| HDF5 conversion source | False | C:\Users\anura\OneDrive\Desktop\capstone2\src\data\convert_to_hdf5.py |
| VAE checkpoint directory | False | C:\Users\anura\OneDrive\Desktop\capstone2\models\checkpoints |
| Processed waveform HDF5 | False | C:\Users\anura\OneDrive\Desktop\capstone2\data\processed\ecg_signals.h5 |
| Standalone embedding directory | False | C:\Users\anura\OneDrive\Desktop\capstone2\data\modeling\ecg_embeddings |

Unavailable referenced artifact categories: VAE model source, VAE training source, Embedding extraction source, Waveform dataset source, HDF5 conversion source, VAE checkpoint directory, Processed waveform HDF5, Standalone embedding directory. The three master split parquet files are available and were directly audited.

## C. Waveform → study_id → z_ecg linkage audit

- Master ECG rows: **375,930**; nonmissing `study_id`: **375,930**; unique `study_id`: **375,930**.
- Duplicate `study_id` rows: **0**; duplicate ID groups: **0**.
- Rows with all 64 dimensions present: **375,930**; rows with any missing dimension: **0**; missing cells: **0**.
- Nonfinite embedding cells: **0**; distinct 64D vectors: **375,769**; duplicate vector rows beyond first: **161**; rows in duplicate-vector groups: **190**.

Observed master-row uniqueness and nonmissingness do not independently prove that each latent vector was produced by the exact raw waveform attached to that row. Separate embedding CSVs, waveform/HDF5 files, and the original join implementation are not available locally; that mapping remains **PARTIALLY VERIFIED**.

## D. VAE split/training audit

The master files are the exact train/validation/test files specified in local documentation. The direct split checks below establish their present-day ID disjointness, not which rows were actually loaded into VAE optimization or checkpoint selection.

| Identifier | Unique IDs by split | Pairwise overlaps | No overlap |
|---|---|---|---|
| study_id | {'train': 262813, 'validation': 56319, 'test': 56798} | {'train__validation': 0, 'train__test': 0, 'validation__test': 0} | True |
| SubjectID | {'train': 69479, 'validation': 14888, 'test': 14889} | {'train__validation': 0, 'train__test': 0, 'validation__test': 0} | True |
| hadm_id | {'train': 133771, 'validation': 28676, 'test': 28922} | {'train__validation': 0, 'train__test': 0, 'validation__test': 0} | True |

Observed master rows: 375,930. Pairwise `study_id`, `SubjectID`, and `hadm_id` overlap checks pass: **True**. Documentation claims subject-level stratified prebuilt splits and exclusion of MI_Post-Incident ECGs; actual VAE membership, optimization exposure, test use, and post-MI exclusion remain **UNRESOLVED** because manifests, source, logs, and checkpoint are absent.

Documented split sizes: `{'train': 262813, 'validation': 56319, 'test': 56798}`. See `observed_master_label_counts_by_split` in the JSON for counts read directly from the current parquet files; those counts do not verify VAE training membership.

A documentation discrepancy was found and is reported without changing frozen Phases 1–4: {"validation": {"MI_Acute_Presentation": {"actual_master_count": 1145, "documented_count": 1129, "actual_minus_documented": 16}, "MI_Pre-Incident": {"actual_master_count": 872, "documented_count": 888, "actual_minus_documented": -16}}, "test": {"Control_Symptomatic": {"actual_master_count": 54736, "documented_count": 54748, "actual_minus_documented": -12}, "MI_Acute_Presentation": {"actual_master_count": 1159, "documented_count": 1131, "actual_minus_documented": 28}, "MI_Pre-Incident": {"actual_master_count": 903, "documented_count": 919, "actual_minus_documented": -16}}}. The VAE document's validation/test label counts do not match the current master parquet counts. This must be resolved against the original split manifest before asserting VAE training membership.

## E. Preprocessing lineage audit

The documentation specifies WFDB records converted into an HDF5 signal array and a nominal input shape of 12×5000 at 500 Hz. It does not provide locally auditable executable logic or fitted parameters for filtering, resampling, waveform/lead normalization, clipping, interpolation, or any learned signal transform. The HDF5 conversion, ECG dataset loader, and preprocessing source files are unavailable. The Phase 4 documentation of winsorization/Yeo-Johnson/robust scaling concerns engineered ECG feature columns and is not evidence that those transforms were applied to raw VAE waveforms.

Whether any parameters were learned, which data fit them, and whether validation/test data influenced preprocessing are **UNRESOLVED**. Unsupervised model type alone does not establish leakage-free preprocessing.

## F. Outcome/treatment leakage audit

The VAE documentation describes training as unsupervised and morphology-reconstruction based. Actual training/dataloader code, split labels supplied to the loader, run logs, and checkpoint metadata are absent. Use of MI/troponin labels, diagnoses, treatments, downstream events, or treatment response is therefore **NOT VERIFIED**. Do not describe the embeddings as proven label-independent or leakage-free.

## G. Temporal eligibility audit

The master schema contains 0 medication/treatment timestamp columns matching medication/treatment time/date naming patterns. It contains window-coded treatment flags but no exact assignment/administered-at time. Consequently `ecg_time < treatment assignment time` cannot be tested for any treatment. Status for Rule A and all other candidates: **TEMPORALLY UNRESOLVED**. Rule A being earliest by `ecg_time` is not evidence of pre-treatment status.

| Candidate ECG rule | Treatment-relative status | Assignment time available | ECG before treatment established | Reason |
|---|---|---|---|---|
| A_first_ecg_admission | TEMPORALLY UNRESOLVED | False | False | The selection rule does not supply an exact medication assignment time; even Rule A's earliest ECG and Rules B/C's pre-MI ECGs cannot establish pre-treatment ordering. |
| B_first_ecg_before_MI | TEMPORALLY UNRESOLVED | False | False | The selection rule does not supply an exact medication assignment time; even Rule A's earliest ECG and Rules B/C's pre-MI ECGs cannot establish pre-treatment ordering. |
| C_closest_ecg_before_MI | TEMPORALLY UNRESOLVED | False | False | The selection rule does not supply an exact medication assignment time; even Rule A's earliest ECG and Rules B/C's pre-MI ECGs cannot establish pre-treatment ordering. |

## H. MI timing audit

Among **7,362** MI-labeled admissions, **4,871** have exactly one distinct non-null `index_mi_time`; **2,491** do not.

Timestamp comparisons below use parsed `ecg_time` and a unique `index_mi_time` within MI-labeled admissions. No arbitrary 'near' threshold is introduced; exact same-timestamp observations are reported separately. `time_diff_hours` is not used as a universal MI clock. `Label_Troponin` remains a categorical cohort label. Temporal ordering before MI does **not** imply ordering before treatment.

| Candidate rule | Selected rows | MI rows with valid unique event time | Admission relation counts | Near threshold used |
|---|---|---|---|---|
| A_first_ecg_admission | 191369 | 4871 | {'before index_mi_time': 4521, 'after index_mi_time': 342, 'same timestamp': 8} | False |
| B_first_ecg_before_MI | 4521 | 4521 | {'before index_mi_time': 4521} | False |
| C_closest_ecg_before_MI | 4521 | 4521 | {'before index_mi_time': 4521} | False |

For Rule A, the 4,871 MI admissions with valid unique event times have 4,521 earliest ECGs before the timestamp, 8 at the same timestamp, and 342 after it. Within those rows, `MI_Acute_Presentation` includes 1,434 before, 8 same-timestamp, and 342 after; all 3,087 `MI_Pre-Incident` rows are before. These observed MI-time relations still do not establish treatment-relative baseline status.

Rules B/C are outcome/event-time-dependent selections and are not evidence of a valid treatment baseline.

## I. 64-dimensional latent diagnostics

All 64 dimensions were measured; no dimension was removed. Missingness, variance, range, quantiles, skew, kurtosis, dominant-value share, and near-constant status are provided per dimension in the JSON and the table below.

| Dimension | Missing | Variance | Min | Median | Max | Skew | Near-constant |
|---|---|---|---|---|---|---|---|
| z_ecg_1 | 0 | 0.958377 | -4.91639 | 0.271599 | 5.13527 | 0.01106 | False |
| z_ecg_2 | 0 | 0.893383 | -4.8758 | -0.116652 | 5.21837 | 0.03371 | False |
| z_ecg_3 | 0 | 0.845773 | -5.17323 | -0.317113 | 4.36286 | 0.005642 | False |
| z_ecg_4 | 0 | 0.969652 | -4.49007 | 0.33182 | 5.76969 | -0.01475 | False |
| z_ecg_5 | 0 | 0.928271 | -4.85752 | -0.103513 | 4.92327 | 0.07186 | False |
| z_ecg_6 | 0 | 0.910171 | -4.98074 | -0.0468775 | 5.86581 | 0.1137 | False |
| z_ecg_7 | 0 | 0.923986 | -4.92952 | -0.310886 | 4.43084 | 0.003467 | False |
| z_ecg_8 | 0 | 0.87156 | -4.53012 | 0.22194 | 5.2405 | -0.0362 | False |
| z_ecg_9 | 0 | 0.906981 | -4.80746 | -0.222428 | 4.87474 | 0.04224 | False |
| z_ecg_10 | 0 | 0.876523 | -4.75166 | -0.160035 | 5.06273 | -8.846e-05 | False |
| z_ecg_11 | 0 | 0.923047 | -4.95185 | 0.0146493 | 4.5912 | -0.1653 | False |
| z_ecg_12 | 0 | 0.994419 | -4.3417 | 0.209723 | 4.75106 | -0.06212 | False |
| z_ecg_13 | 0 | 0.902924 | -5.08224 | -0.403123 | 5.08903 | -0.002247 | False |
| z_ecg_14 | 0 | 0.947143 | -4.73436 | -0.0847344 | 4.26112 | -0.07046 | False |
| z_ecg_15 | 0 | 0.85941 | -5.54757 | -0.0838965 | 4.62878 | -0.08421 | False |
| z_ecg_16 | 0 | 0.84523 | -4.3179 | 0.581859 | 5.28798 | 0.04136 | False |
| z_ecg_17 | 0 | 0.900298 | -4.63293 | 0.23841 | 5.27159 | -0.01593 | False |
| z_ecg_18 | 0 | 0.860533 | -4.43986 | 0.334127 | 5.09956 | 0.007594 | False |
| z_ecg_19 | 0 | 0.90113 | -5.08474 | -0.310716 | 4.41208 | -0.03496 | False |
| z_ecg_20 | 0 | 0.904677 | -4.33868 | 0.26592 | 5.43207 | 0.07352 | False |
| z_ecg_21 | 0 | 0.919283 | -3.6763 | 0.283235 | 5.31116 | 0.03015 | False |
| z_ecg_22 | 0 | 0.905669 | -5.01022 | -0.345044 | 4.9722 | 0.03876 | False |
| z_ecg_23 | 0 | 0.98825 | -4.89814 | -0.260258 | 4.19672 | -0.1014 | False |
| z_ecg_24 | 0 | 0.896796 | -4.9676 | -0.304582 | 5.10309 | -0.02254 | False |
| z_ecg_25 | 0 | 0.90974 | -4.61718 | 0.0764216 | 4.94943 | 0.02469 | False |
| z_ecg_26 | 0 | 0.91072 | -4.67908 | 0.210956 | 5.63705 | 0.007883 | False |
| z_ecg_27 | 0 | 0.863563 | -3.8593 | 0.368642 | 4.9106 | 0.005305 | False |
| z_ecg_28 | 0 | 0.91836 | -4.91464 | 0.298792 | 5.4985 | -0.04934 | False |
| z_ecg_29 | 0 | 0.954414 | -4.74335 | 0.0118983 | 4.57449 | -0.06141 | False |
| z_ecg_30 | 0 | 0.899016 | -4.30408 | 0.326417 | 4.98426 | 0.1644 | False |
| z_ecg_31 | 0 | 0.833246 | -3.7149 | 0.507769 | 5.01121 | 0.03191 | False |
| z_ecg_32 | 0 | 0.903591 | -4.39992 | 0.3997 | 5.54751 | 0.09974 | False |
| z_ecg_33 | 0 | 0.939345 | -5.58842 | -0.367039 | 5.33842 | -0.01107 | False |
| z_ecg_34 | 0 | 0.94684 | -4.65937 | -0.0223237 | 4.83569 | 0.08221 | False |
| z_ecg_35 | 0 | 0.917216 | -4.6452 | 0.0349287 | 5.34974 | 0.02456 | False |
| z_ecg_36 | 0 | 0.913157 | -4.30147 | 0.045503 | 4.68082 | -0.02268 | False |
| z_ecg_37 | 0 | 0.935258 | -5.09506 | -0.264694 | 4.18922 | -0.01623 | False |
| z_ecg_38 | 0 | 0.900944 | -4.56644 | 0.287934 | 5.24647 | 0.05687 | False |
| z_ecg_39 | 0 | 0.793708 | -5.01391 | -0.407817 | 4.13576 | 0.1067 | False |
| z_ecg_40 | 0 | 0.887924 | -4.7672 | 0.127901 | 5.10747 | 0.03744 | False |
| z_ecg_41 | 0 | 0.889254 | -4.8213 | -0.189928 | 4.58827 | 0.07028 | False |
| z_ecg_42 | 0 | 0.909972 | -6.64072 | -0.0985037 | 4.75735 | -0.04821 | False |
| z_ecg_43 | 0 | 0.930028 | -5.89675 | -0.442501 | 3.70689 | -0.1159 | False |
| z_ecg_44 | 0 | 1.00776 | -4.41513 | 0.246358 | 5.29 | 0.07506 | False |
| z_ecg_45 | 0 | 0.854407 | -4.20467 | 0.316403 | 5.04806 | 0.09533 | False |
| z_ecg_46 | 0 | 0.840645 | -3.92532 | 0.365239 | 4.8934 | 0.1698 | False |
| z_ecg_47 | 0 | 0.878353 | -5.60349 | -0.328492 | 4.41498 | -0.03637 | False |
| z_ecg_48 | 0 | 0.861937 | -5.25564 | -0.503748 | 3.99043 | -0.04917 | False |
| z_ecg_49 | 0 | 0.846974 | -4.91484 | 0.0344784 | 4.99881 | 0.004746 | False |
| z_ecg_50 | 0 | 0.949834 | -5.52252 | -0.16871 | 4.35109 | -0.1363 | False |
| z_ecg_51 | 0 | 0.873672 | -3.99268 | 0.295729 | 5.07261 | 0.01756 | False |
| z_ecg_52 | 0 | 0.904968 | -4.87329 | -0.462561 | 4.22478 | 0.008981 | False |
| z_ecg_53 | 0 | 0.898138 | -5.23062 | -0.445165 | 4.0052 | -0.08656 | False |
| z_ecg_54 | 0 | 0.949085 | -4.64772 | -0.394949 | 4.46391 | -0.04351 | False |
| z_ecg_55 | 0 | 0.884189 | -5.23703 | -0.288204 | 5.25123 | 0.03262 | False |
| z_ecg_56 | 0 | 0.838506 | -4.69266 | 0.322656 | 4.92613 | 0.06271 | False |
| z_ecg_57 | 0 | 0.893826 | -5.16786 | -0.0253417 | 4.55223 | -0.05523 | False |
| z_ecg_58 | 0 | 0.9329 | -4.86752 | -0.306791 | 4.56064 | -0.0419 | False |
| z_ecg_59 | 0 | 0.901333 | -5.10659 | 0.533261 | 5.28183 | 0.09249 | False |
| z_ecg_60 | 0 | 0.976964 | -4.68276 | -0.025479 | 4.61657 | -0.05885 | False |
| z_ecg_61 | 0 | 0.842776 | -4.5054 | -0.135849 | 4.53976 | 0.05346 | False |
| z_ecg_62 | 0 | 0.875285 | -4.44648 | 0.305746 | 5.34119 | -0.007061 | False |
| z_ecg_63 | 0 | 0.891225 | -5.66044 | 0.202047 | 4.87582 | -0.1436 | False |
| z_ecg_64 | 0 | 0.938368 | -5.16401 | -0.0598082 | 4.97917 | -0.02595 | False |

Exact duplicate dimension pairs: **0**. Pairwise Pearson comparisons: **2,016**; pairs with |r| ≥ 0.98: **0**; median |r|: **0.02955**; maximum |r|: **0.2136**.
No latent-dimension pair met the specified absolute correlation threshold.

Correlation and distribution summaries are descriptive. They do not give dimensions clinical meanings or imply causal independence. No PCA, scaling, component selection, or dimension removal was performed.

## J. Causal-role analysis

| Possible role | Mechanism | Temporal requirement | Evidence available | Evidence missing | Causal implication |
|---|---|---|---|---|---|
| A — Baseline common cause/confounder | A pre-treatment ECG state may influence treatment assignment and subsequent MI risk. | The ECG measurement must precede treatment assignment and outcome; the relevant state must be a cause of both treatment and outcome. | ECG representations and admission-level treatment indicators are present; exact treatment times are not. | Treatment-specific time zero, waveform provenance, pre-treatment ordering, and evidence linking ECG state to treatment assignment and outcome. | Could be a confounder only if those conditions are established; currently not established. |
| B — Proxy for latent cardiovascular state | The embedding may summarize ECG morphology that reflects an underlying physiological or disease state. | The represented ECG state must be measured at the relevant pre-treatment baseline to proxy a baseline state. | The documentation describes a morphology-reconstruction VAE; the master contains 64 embedding values. | Verified waveform/checkpoint lineage, latent construct validity, and pre-treatment timing. | Observed z_ecg is not identical to the unobserved physiological state and cannot be assumed to block confounding. |
| C — Predictor of outcome only | ECG morphology could be prognostic for MI without affecting treatment assignment. | For baseline prediction/adjustment, z_ecg must be available before treatment and outcome. | MI labels and embeddings coexist in the master data; Phase 5 does not estimate predictive performance or causal influence. | Independent predictive validation and evidence about the treatment-assignment mechanism. | Prognostic association alone would not make z_ecg a confounder. |
| D — Mediator | Treatment or treatment-induced physiology could change a subsequent ECG that then relates to outcome. | Treatment precedes the ECG, and that ECG precedes the outcome. | Treatment indicators are window-coded and lack exact administration times; multiple ECGs may occur within admission. | Treatment time, selected ECG time relative to treatment, and outcome timing. | Adjustment could block part of an effect if z_ecg is post-treatment; that ordering is unresolved. |
| E — Collider | Treatment and another acute process may both affect the ECG measurement/embedding. | Both causes precede the measured ECG and the analysis conditions on z_ecg. | The dataset has acute-treatment indicators and ECG representations, but no validated causal ordering. | Treatment timing, acute-process measures, and a treatment-specific time zero. | Conditioning could induce bias under this structure; it cannot currently be ruled out. |
| F — Effect modifier | Baseline ECG morphology could mark strata with different treatment response. | The modifier must be defined before treatment assignment. | Sixty-four dimensions exist, but no treatment-effect analysis is permitted or performed in Phase 5. | Pre-treatment timing and treatment-specific causal estimand/effect-modification evidence. | Possible in principle; neither supported nor excluded by current audit evidence. |
| G — Predictive-only representation | The block may encode waveform patterns useful for prediction without a justified causal adjustment role. | Prediction use still requires a deployment-appropriate observation time; causal baseline use requires pre-treatment timing. | A learned ECG representation is present; no Phase 5 predictive model is fit. | Validated prediction utility, provenance, and temporal eligibility. | Predictive utility, if later shown, would not establish confounding or adjustment suitability. |

No single causal role is assigned. Baseline confounding, proxy, prognostic-only, mediator, collider, effect modification, and predictive-only interpretations remain distinct hypotheses; current evidence does not establish one or exclude the post-treatment possibilities.

## K. Representation options

| Option | Advantages | Risks/requirements | Phase 5 assessment |
|---|---|---|---|
| A — All 64 latent dimensions | Retains the available learned representation without arbitrary compression. | Higher-dimensional discovery, correlation/instability, limited interpretability, and unresolved provenance/timing. | Carry as a quarantined optional block only; no approved causal feature matrix. |
| B — PCA reduction | Could reduce dimensionality for a later specified workflow. | Requires an explicit objective, training-only fit, documented explained variance, and downstream stability checks; no outcome/treatment-driven component selection. | Not performed; no evidence currently justifies selecting components or fitting PCA. |
| C — Representative latent subset | Could reduce variables if stable relationships to ECG properties are established. | Would require validated, stable, interpretable mapping; individual latent dimensions have no supplied semantic labels. | Not recommended on current evidence; do not invent dimension meanings. |
| D — Block-level representation | Preserves the 64-vector as one ECG representation family and avoids treating each dimension as a separately meaningful causal node. | A block label does not resolve temporal eligibility, leakage, or whether a later method can handle a multivariate block. | Most defensible provisional schema representation for later review; still quarantined and not approved for discovery or adjustment. |

## L. Recommended representation

**Discovery:** NO FINAL REPRESENTATION DECISION YET. Carry `z_ecg` only as an explicitly quarantined block of 64 named dimensions; do not treat it as an approved causal discovery input or 64 separately interpretable causal nodes.

**Later treatment-effect modeling:** Do not include it as a baseline adjustment variable without treatment-specific evidence that the selected ECG preceded assignment, verified provenance, and a justified causal role. Discovery representation and adjustment representation are not interchangeable.

## M. Unresolved issues

- Exact waveform-to-study_id-to-embedding correspondence and extraction joins.
- Actual VAE checkpoint used and training/checkpoint selection membership.
- Whether validation/test waveforms influenced optimization or model selection; whether post-MI waveforms entered training.
- Executable waveform preprocessing, fitted parameters, and train-only scope.
- Whether labels, diagnoses, treatments, or downstream events influenced training/selection.
- Medication assignment timestamps and treatment-specific ECG baseline eligibility.
- Temporal order of each ECG/embedding relative to treatment and MI; MI-before-treatment is not implied by MI-before-ECG or vice versa.
- Whether any latent dimension or the representation block is a confounder, proxy, prognostic factor, mediator, collider, modifier, or prediction-only signal.

## N. Phase 6 handoff

1. Obtain VAE model/training/extraction source, full training logs, split manifests, configuration, and the exact checkpoint used to generate current embeddings.
2. Obtain the waveform/HDF5 archive and study_id mapping; reproduce waveform-to-embedding joins and verify each embedding matches the corresponding master ECG.
3. Verify actual VAE train/validation/test membership, subject-level isolation, optimizer exposure to validation/test data, and whether post-MI waveforms entered optimization.
4. Recover waveform preprocessing code and fitted parameters; identify fit partitions and any validation/test influence.
5. Verify whether labels, diagnoses, outcomes, or treatment information entered training, selection, or extraction.
6. For the eventual treatment-specific question, obtain exact medication assignment/administration times and define a treatment-specific causal baseline before evaluating ECG eligibility.
7. Keep outcome-relative ECG selection separate from treatment-relative baseline eligibility; do not use time_diff_hours as a universal MI clock.

No Phase 6 or Phase 7 analysis was performed. No causal discovery, DAG, treatment selection, time-zero selection, adjustment-set selection, or treatment-effect estimation was performed.

### PHASE 5 DECISION RECORD

1. `z_ecg` provenance: PARTIALLY VERIFIED — master dimensions are present; underlying waveform/model/training/extraction lineage is documentary or unavailable.
2. Waveform-to-study_id mapping: PARTIALLY VERIFIED — master `study_id` values are unique and embedding-complete; exact source waveform correspondence and join cannot be re-performed.
3. VAE training split integrity: UNRESOLVED — actual master splits are subject/ECG/admission-disjoint; their use by VAE training is unverified.
4. VAE checkpoint provenance: PARTIALLY VERIFIED — documentation names a run/checkpoint, but no local checkpoint proves it generated current embeddings.
5. VAE preprocessing provenance: UNRESOLVED — executable transforms, fitted parameters, and fit partitions unavailable.
6. Outcome/treatment independence: UNRESOLVED — documentation describes unsupervised training; code and input provenance do not verify absence of these signals.
7. Temporal eligibility relative to treatment: TEMPORALLY UNRESOLVED — no exact treatment assignment timestamp.
8. Temporal relationship to MI: MEASURABLE ONLY for MI admissions with one event timestamp and a valid ECG timestamp; this does not establish pre-treatment status.
9. Number of latent dimensions retained: 64; none removed.
10. PCA performed: NO.
11. Recommended discovery representation: NO FINAL REPRESENTATION DECISION YET; retain all 64 only as a quarantined block pending provenance and time-zero evidence.
12. Recommended later causal-model representation: UNRESOLVED; do not use as baseline adjustment until treatment-specific pre-treatment eligibility and causal role are supported.
13. Most plausible causal roles: A pre-treatment proxy for cardiovascular state or prognostic representation are theoretically plausible but unverified.
14. Roles that cannot currently be excluded: Confounder, proxy, prognostic-only, mediator, collider, effect modifier, predictive-only.
15. Whether `z_ecg` can currently be called a confounder: **NO** — temporal ordering and common-cause role are not established.
16. Whether `z_ecg` can currently be included as a baseline adjustment variable: **NO** — no proof the ECG predates treatment-specific assignment; provenance is incomplete.
17. Remaining blockers: Exact waveform/embedding lineage; VAE training/checkpoint and preprocessing provenance; leakage audit; medication assignment timestamps; treatment-specific time zero.
18. Phase 6 handoff: Obtain source/checkpoint/split/preprocessing artifacts and treatment timestamps; verify waveform lineage and temporal eligibility before any discovery or treatment-effect modeling.
