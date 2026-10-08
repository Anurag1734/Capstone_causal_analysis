# Phase D.4 — VAE Embedding Pipeline: Complete Documentation

> **Date**: August 20–21, 2026  
> **Pipeline Reference**: [longitudinal_mi_cohort_extraction.md](file:///C:/Users/Acer/Desktop/Pipeline/longitudinal_mi_cohort_extraction.md), Phase D.4  
> **Goal**: Train a Conv1D β-VAE on 12-lead ECGs and extract 64-dimensional latent embeddings (z_ecg) for use in the Structural Causal Model.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Data Pipeline](#2-data-pipeline)
3. [HDF5 Conversion](#3-hdf5-conversion)
4. [Model Architecture](#4-model-architecture)
5. [Training Configuration](#5-training-configuration)
6. [Training Results](#6-training-results)
7. [Embedding Extraction](#7-embedding-extraction)
8. [Embedding Validation](#8-embedding-validation)
9. [File Reference](#9-file-reference)
10. [How to Reproduce](#10-how-to-reproduce)
11. [Known Issues & Fixes](#11-known-issues--fixes)
12. [Next Steps](#12-next-steps)

---

## 1. Overview

The VAE embedding pipeline transforms raw 12-lead ECG waveforms (12 channels × 5000 samples at 500 Hz = 10 seconds) into compact 64-dimensional latent vectors. These vectors capture the morphological characteristics of each ECG without any label supervision, making them suitable as the `z_ecg` node in the downstream Structural Causal Model (SCM).

```
Raw ECG Signal          →  Conv1D β-VAE Encoder  →  z_ecg (64-dim)
(12 × 5000, float32)       82M parameters           (64, float32)
~240 KB per ECG             109 epochs trained        ~256 bytes per ECG
```

---

## 2. Data Pipeline

### 2.1 Input Data

| Item | Details |
|---|---|
| **Source** | MIMIC-IV-ECG v1.0 |
| **Format** | WFDB (.dat + .hea per study) |
| **Location** | `C:\Users\Acer\Desktop\Capstone\Capstone\data\raw\MIMIC-IV-ECG-1.0\files\` |
| **Total ECGs** | 377,113 valid recordings |
| **Resolution** | 12 leads × 5000 samples (500 Hz, 10 seconds) |

### 2.2 Pre-Built Splits

The training uses **subject-level stratified splits** pre-built by the earlier data preprocessing pipeline. These splits ensure:
- No subject appears in multiple splits (preventing data leakage)
- Label proportions are maintained across splits
- Post-MI ECGs (`MI_Post-Incident`) are excluded from training

| Split | ECGs | Control_Symptomatic | MI_Pre-Incident | MI_Acute_Presentation |
|---|---|---|---|---|
| **Train** | 262,813 | 253,334 | 4,179 | 5,300 |
| **Validation** | 56,319 | 54,302 | 888 | 1,129 |
| **Test** | 56,798 | 54,748 | 919 | 1,131 |
| **Total** | 375,930 | 362,384 | 5,986 | 7,560 |

Split files are stored at:
- [`data/modeling/labels/train.csv`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/labels/train.csv)
- [`data/modeling/labels/validation.csv`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/labels/validation.csv)
- [`data/modeling/labels/test.csv`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/labels/test.csv)

### 2.3 Data Loading

Two loading modes are supported:

| Mode | Speed | Use Case |
|---|---|---|
| **WFDB** (individual files) | ~2.7 it/s (bs=8) | Debugging, small experiments |
| **HDF5** (single file) | ~8.9 it/s (bs=128) | Full training |

The training script **auto-detects** HDF5 mode if `data/processed/ecg_signals.h5` exists.

---

## 3. HDF5 Conversion

### 3.1 Problem

Loading 377K individual WFDB files from disk introduces extreme I/O overhead:
- Each ECG requires opening 2 files (.dat + .hea), parsing headers, reading binary data
- At ~2.7 batches/sec with batch_size=8, one epoch took **~3.5 hours**
- 160 epochs would take **~23 days** — infeasible

### 3.2 Solution

A one-time conversion script packs all ECGs into a single HDF5 file with memory-mapped access:

**Script**: [`src/data/convert_to_hdf5.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/data/convert_to_hdf5.py)

```
Input:  377,113 individual WFDB file pairs
Output: data/processed/ecg_signals.h5 (90.57 GB)
        ├── signals:   float32 array [377113, 12, 5000]
        └── study_ids: int64 array   [377113]
```

### 3.3 Conversion Results

| Metric | Value |
|---|---|
| Valid ECGs | 377,113 / 377,113 (100%) |
| Failed | 0 (0.00%) |
| Output size | 90.57 GB |
| Conversion time | 234 minutes (~4 hours) |
| Rate | 27 ECGs/second |
| Verification | 20/20 random samples MATCH against WFDB source |

### 3.4 Speed Improvement

| Mode | Batch Loading | Epoch Time | 160 Epochs |
|---|---|---|---|
| WFDB (old) | ~200-400ms/batch | ~3.5 hours | ~23 days |
| **HDF5 (new)** | **~5-10ms/batch** | **~4 minutes** | **~10 hours** |

### 3.5 Multiprocessing Fix

HDF5 file handles cannot be pickled, which causes crashes when PyTorch DataLoader uses `num_workers > 0`. This was fixed by implementing a **lazy-open pattern** in [`ECGDatasetHDF5`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/data/ecg_dataset.py):

```python
# Instead of opening in __init__ (which gets pickled):
def _ensure_h5_open(self):
    """Lazily open the HDF5 file (safe for multiprocessing workers)."""
    if self._h5f is None:
        self._h5f = h5py.File(self.h5_path, "r")
        self._signals = self._h5f["signals"]
```

Each worker process opens its own file handle on first `__getitem__` call, avoiding the pickle error.

---

## 4. Model Architecture

**Model**: [`src/models/vae_conv1d.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/vae_conv1d.py)

### 4.1 Encoder

```
Input: (batch, 12, 5000)
  → Conv1d(12→32, k=7, s=2)  → BN → LeakyReLU    → (batch, 32, 2500)
  → Conv1d(32→64, k=5, s=2)  → BN → LeakyReLU    → (batch, 64, 1250)
  → Conv1d(64→128, k=5, s=2) → BN → LeakyReLU    → (batch, 128, 625)
  → Conv1d(128→256, k=3, s=2) → BN → LeakyReLU   → (batch, 256, 312)
  → Conv1d(256→512, k=3, s=2) → BN → LeakyReLU   → (batch, 512, 156)
  → Flatten                                        → (batch, 79872)
  → Linear(79872 → 512) → LeakyReLU
  → Linear(512 → 64)  [mu]
  → Linear(512 → 64)  [logvar]
Output: mu (batch, 64), logvar (batch, 64)
```

### 4.2 Decoder

```
Input: z (batch, 64)
  → Linear(64 → 512) → LeakyReLU
  → Linear(512 → 79872) → LeakyReLU
  → Reshape                                        → (batch, 512, 156)
  → ConvTranspose1d(512→256) → BN → LeakyReLU     → (batch, 256, 312)
  → ConvTranspose1d(256→128) → BN → LeakyReLU     → (batch, 128, 625)
  → ConvTranspose1d(128→64)  → BN → LeakyReLU     → (batch, 64, 1250)
  → ConvTranspose1d(64→32)   → BN → LeakyReLU     → (batch, 32, 2500)
  → ConvTranspose1d(32→12)   → Tanh               → (batch, 12, 5000)
Output: reconstructed ECG (batch, 12, 5000)
```

### 4.3 Loss Function

```
L = L_recon + β * L_kl

L_recon = MSE(input, reconstruction)
L_kl   = max(KL_raw, free_bits)     # free_bits = 2.0 per dimension
KL_raw = -0.5 * sum(1 + logvar - mu² - exp(logvar))
```

### 4.4 Key Parameters

| Parameter | Value |
|---|---|
| Total parameters | 82,448,332 |
| Latent dimension (z_dim) | 64 |
| β (disentanglement) | 4.0 |
| Free bits | 2.0 per dimension |
| Activation | LeakyReLU (encoder/decoder), Tanh (output) |

---

## 5. Training Configuration

**Script**: [`src/models/train_vae.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/train_vae.py)

### 5.1 Hyperparameters

| Parameter | Value |
|---|---|
| Batch size | 128 |
| Learning rate | 1e-4 (initial) |
| Optimizer | Adam (weight_decay=1e-5) |
| LR scheduler | ReduceLROnPlateau (patience=10, factor=0.5) |
| Early stopping | Patience = 20 epochs |
| Gradient clipping | max_norm = 5.0 |
| Epochs (max) | 160 |
| Epochs (actual) | 129 (early stopped) |

### 5.2 Cyclical β-Annealing

Instead of a fixed β, the training uses **cyclical annealing** to prevent posterior collapse:

```
β schedule: 4 cycles × 40 epochs each
  Cycle 1: epochs  1–40  → β ramps 0.0 → 4.0
  Cycle 2: epochs 41–80  → β ramps 0.0 → 4.0
  Cycle 3: epochs 81–120 → β ramps 0.0 → 4.0
  Cycle 4: epochs 121–160 → β ramps 0.0 → 4.0 (partially completed)
```

Each cycle start temporarily drops the KL pressure, allowing the model to "reset" its latent encoding strategy. This is visible as small val_loss spikes at epochs 41, 81, and 121.

### 5.3 Learning Rate Schedule (Actual)

| Epoch | LR | Trigger |
|---|---|---|
| 1–85 | 1.00e-04 | Initial |
| 86–105 | 5.00e-05 | 10 epochs without improvement (3rd cycle reset) |
| 106–115 | 2.50e-05 | 10 more epochs without improvement |
| 116–129 | 1.25e-05 | 10 more epochs without improvement |

Each LR drop produced a burst of improvement, characteristic of well-timed learning rate decay.

### 5.4 Checkpointing & Resume

The training is fully resumable. Checkpoints are saved:
- `best_model.pt` — whenever val_loss improves
- `checkpoint_epoch_N.pt` — every 10 epochs
- `checkpoint_epoch_N_final.pt` — at training end

Each checkpoint stores: model weights, optimizer state, scheduler state, early stopping counter, full training history, and epoch number.

**Resume command**:
```bash
python src/models/train_vae.py --batch_size 128 --epochs 160 --resume \
  --checkpoint_path models/checkpoints/<run_dir>/best_model.pt
```

---

## 6. Training Results

**Run directory**: [`models/checkpoints/vae_zdim64_beta4.0_20260821_030245/`](file:///C:/Users/Acer/Desktop/Capstone/SCM/models/checkpoints/vae_zdim64_beta4.0_20260821_030245)

### 6.1 Final Metrics

| Metric | Start (Epoch 1) | Best (Epoch 109) | Change |
|---|---|---|---|
| Val Loss | 56,518 | **16,904** | -70% |
| Val Recon Loss | 30,795 | **16,566** | -46% |
| Train Loss | 38,300 | 14,061 | -63% |
| KL_raw | 3,902 | **212** | Healthy (>> 1.0) |
| Learning Rate | 1e-4 | 2.5e-5 | 3 reductions |
| β | 0.0 | 2.8 | Cyclical |

### 6.2 Training Curves

![Training Curves](file:///C:/Users/Acer/Desktop/Capstone/SCM/models/checkpoints/vae_zdim64_beta4.0_20260821_030245/training_curves.png)

**Key observations**:
- **Total Loss**: Smooth convergence with expected bumps at cycle boundaries (41, 81, 121)
- **Reconstruction Loss**: Steady decrease — model continuously improves signal reconstruction
- **KL Raw**: Stabilized around 210–220, well above collapse threshold of 1.0
- **β Schedule**: Clean cyclical pattern, 3 full cycles completed
- **Learning Rate**: Three stepwise reductions, each unlocking further convergence
- **Early stopping**: Triggered at epoch 129 after 20 epochs without improvement

### 6.3 Training Duration

| Phase | Duration | Notes |
|---|---|---|
| Epochs 1–18 (bs=32, nw=0) | ~4 hours | Initial run |
| Epochs 19–96 (bs=128, nw=4) | ~5.5 hours | Resumed with larger batch |
| Epochs 96–129 (bs=128, nw=4) | ~2.5 hours | Resumed after interruption |
| **Total training time** | **~12 hours** | |
| HDF5 conversion | ~4 hours | One-time cost |

### 6.4 Train-Val Gap

- Train loss: 13,299 vs Val loss: 17,326 at final epoch (~23% gap)
- This moderate overfitting is acceptable because:
  1. The model has 82M parameters vs 263K training samples
  2. We use the embeddings for downstream SCM, not for direct reconstruction
  3. The embeddings are well-calibrated (mean≈0, std≈1) on validation data too

---

## 7. Embedding Extraction

**Script**: [`src/models/extract_embeddings.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/extract_embeddings.py)

### 7.1 Process

The extraction script:
1. Loads the best checkpoint (epoch 109)
2. Passes each ECG through the encoder only
3. Extracts the `mu` (mean) vector as the deterministic embedding
4. Saves study_id + SubjectID + 64 z_ecg dimensions to CSV

### 7.2 Results

| Split | ECGs | Output Size | Time |
|---|---|---|---|
| Train | 262,813 | 179.9 MB | 3 min 5 sec |
| Validation | 56,319 | 38.6 MB | 55 sec |
| Test | 56,798 | 38.9 MB | 55 sec |
| **Total** | **375,930** | **257.4 MB** | **~5 min** |

### 7.3 Output Format

Each CSV contains 66 columns:
```
study_id, SubjectID, z_ecg_1, z_ecg_2, ..., z_ecg_64
```

Files:
- [`data/modeling/ecg_embeddings/train.csv`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/ecg_embeddings/train.csv)
- [`data/modeling/ecg_embeddings/validation.csv`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/ecg_embeddings/validation.csv)
- [`data/modeling/ecg_embeddings/test.csv`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/ecg_embeddings/test.csv)

---

## 8. Embedding Validation

**Script**: [`src/models/validate_embeddings.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/validate_embeddings.py)

### 8.1 Basic Statistics — PASSED

| Metric | Train | Validation | Test |
|---|---|---|---|
| Shape | (262813, 66) | (56319, 66) | (56798, 66) |
| NaN | 0 | 0 | 0 |
| Inf | 0 | 0 | 0 |
| Z mean | 0.0011 | 0.0011 | 0.0002 |
| Z std | 0.9956 | 0.9958 | 0.9935 |
| Z range | [-6.64, 5.77] | [-5.23, 5.87] | [-5.29, 5.43] |

The embeddings are nearly perfectly calibrated to N(0,1) — excellent alignment with the VAE prior.

### 8.2 Dimension Usage — PASSED (64/64 active)

![Dimension Variance](file:///C:/Users/Acer/Desktop/Capstone/SCM/models/checkpoints/vae_zdim64_beta4.0_20260821_030245/dimension_variance.png)

All 64 dimensions have variance between 0.79 and 1.01. The remarkably flat profile shows the model is utilizing its entire latent capacity — no dead dimensions. This is a sign of effective free-bits regularization and cyclical annealing.

### 8.3 t-SNE Visualization

![t-SNE Embeddings](file:///C:/Users/Acer/Desktop/Capstone/SCM/models/checkpoints/vae_zdim64_beta4.0_20260821_030245/tsne_embeddings.png)

MI and Control points are largely overlapping, which is **expected** for an unsupervised VAE. The model was trained to reconstruct ECG morphology, not to classify MI. The latent space organizes ECGs by waveform similarity, not by clinical label. Some clustering structure is visible — certain regions have higher MI density — indicating the embeddings do capture some MI-correlated cardiac features.

### 8.4 Downstream Discriminability — AUC = 0.66

A simple logistic regression on the 64 z_ecg features:

| Metric | Value |
|---|---|
| ROC AUC | 0.6606 |
| MI Recall | 60% |
| Control Recall | 64% |

An AUC of 0.66 from purely unsupervised embeddings is a positive signal. The embeddings capture enough cardiac morphology to partially distinguish MI from control patients, even without any label information during training. When combined with comorbidities, demographics, and treatments in the SCM, predictive performance is expected to improve substantially.

---

## 9. File Reference

### 9.1 Source Code

| File | Purpose |
|---|---|
| [`src/data/ecg_dataset.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/data/ecg_dataset.py) | `ECGDataset` (WFDB) + `ECGDatasetHDF5` (fast) + split loaders |
| [`src/data/convert_to_hdf5.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/data/convert_to_hdf5.py) | One-time WFDB → HDF5 converter with verification |
| [`src/data/__init__.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/data/__init__.py) | Package init |
| [`src/models/vae_conv1d.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/vae_conv1d.py) | Conv1D β-VAE architecture (82M parameters) |
| [`src/models/train_vae.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/train_vae.py) | Training loop with cyclical annealing + checkpointing |
| [`src/models/extract_embeddings.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/extract_embeddings.py) | Embedding extraction from best checkpoint |
| [`src/models/validate_embeddings.py`](file:///C:/Users/Acer/Desktop/Capstone/SCM/src/models/validate_embeddings.py) | 4-check embedding quality validation |

### 9.2 Data Files

| File | Size | Purpose |
|---|---|---|
| `data/processed/ecg_signals.h5` | 90.57 GB | All 377K ECGs in HDF5 format |
| `data/modeling/labels/{train,validation,test}.csv` | ~42 MB | Pre-built stratified splits |
| `data/modeling/ecg_embeddings/{train,validation,test}.csv` | ~257 MB | **Final output**: 64-dim z_ecg vectors |

### 9.3 Model Artifacts

| File | Size | Purpose |
|---|---|---|
| `models/checkpoints/.../best_model.pt` | 989 MB | Best checkpoint (epoch 109) |
| `models/checkpoints/.../checkpoint_epoch_129_final.pt` | 989 MB | Final checkpoint |
| `models/checkpoints/.../training_history.json` | 28 KB | Per-epoch metrics |
| `models/checkpoints/.../training_curves.png` | 522 KB | 6-panel training visualization |
| `models/checkpoints/.../tsne_embeddings.png` | — | t-SNE scatter plot |
| `models/checkpoints/.../dimension_variance.png` | — | Latent dimension usage bar chart |
| `models/checkpoints/.../config.json` | 616 B | Training configuration |
| `models/log.txt` | 47 KB | Full console training log |

---

## 10. How to Reproduce

### 10.1 Prerequisites

```bash
# Activate CUDA environment
& "C:\Users\Acer\Desktop\Capstone\Capstone\cuda_env\Scripts\Activate.ps1"

# Required packages: torch, h5py, pandas, numpy, tqdm, matplotlib, scikit-learn, wfdb
```

### 10.2 Step 1: Convert ECGs to HDF5 (one-time, ~4 hours)

```bash
cd C:\Users\Acer\Desktop\Capstone\SCM
python src/data/convert_to_hdf5.py --verify
```

### 10.3 Step 2: Train the VAE (~12 hours)

```bash
# Full training (auto-detects HDF5)
python src/models/train_vae.py --batch_size 128 --epochs 160 --num_workers 4

# Smoke test (30 seconds)
python src/models/train_vae.py --batch_size 8 --epochs 2 --max_batches 20

# Resume from checkpoint
python src/models/train_vae.py --batch_size 128 --epochs 160 --num_workers 4 \
  --resume --checkpoint_path models/checkpoints/<run_dir>/best_model.pt
```

### 10.4 Step 3: Extract Embeddings (~5 minutes)

```bash
python src/models/extract_embeddings.py \
  --checkpoint models/checkpoints/<run_dir>/best_model.pt
```

### 10.5 Step 4: Validate Embeddings (~2 minutes)

```bash
$env:PYTHONIOENCODING="utf-8"
python src/models/validate_embeddings.py
```

---

## 11. Known Issues & Fixes

### 11.1 HDF5 + num_workers > 0 crash

**Problem**: `TypeError: h5py objects cannot be pickled`  
**Cause**: PyTorch DataLoader pickles the Dataset to send to worker processes. HDF5 file handles can't be pickled.  
**Fix**: Lazy-open pattern — file is opened on first `__getitem__`, not in `__init__`. Each worker gets its own handle.

### 11.2 `__del__` AttributeError on failed init

**Problem**: `AttributeError: 'ECGDatasetHDF5' object has no attribute '_h5f'`  
**Cause**: When `__init__` fails mid-way, `_h5f` is never set. GC calls `__del__` → `close()` → crash.  
**Fix**: Changed `if self._h5f` to `if getattr(self, '_h5f', None) is not None`.

### 11.3 sklearn TSNE `n_iter` renamed

**Problem**: `TypeError: TSNE.__init__() got an unexpected keyword argument 'n_iter'`  
**Cause**: Newer sklearn renamed `n_iter` to `max_iter`.  
**Fix**: Changed to `max_iter=1000`.

### 11.4 Windows Unicode console encoding

**Problem**: `UnicodeEncodeError: 'charmap' codec can't encode character '\u2713'`  
**Cause**: Windows cp1252 console can't render Unicode symbols.  
**Fix**: Set `$env:PYTHONIOENCODING="utf-8"` before running scripts.

---

## 12. Next Steps

Per the [pipeline specification](file:///C:/Users/Acer/Desktop/Pipeline/longitudinal_mi_cohort_extraction.md):

> [!IMPORTANT]
> **Phase D.4 (VAE Embeddings) is COMPLETE.**

The next phase is **Phase E — Feature Assembly**, which involves:

1. **E.1**: Merge ECG embeddings with comorbidities (`features_comorbidities.csv`)
2. **E.2**: Merge with treatments (`features_treatments.csv`)
3. **E.3**: Merge with vitals and labs (`features_vitals.csv`, `features_labs.csv`)
4. **E.6**: Merge with demographics (`demographics.csv`)
5. **E.7**: Assemble the final modeling tables for the SCM

All required input files already exist in [`data/modeling/`](file:///C:/Users/Acer/Desktop/Capstone/SCM/data/modeling/).
