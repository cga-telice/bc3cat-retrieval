# Sprint LW-03 — Full Training Run

**Tasks from backlog:** B2 (training run), B3 (sanity test on dev samples)
**Prerequisites:** Sprint LW-02 complete (model + training script verified)

---

## Context

The multi-head E5 classifier and training loop are implemented and verified (Sprint LW-02 sanity test: 100 samples, 1 epoch, CPU). This sprint runs the full training on GPU and evaluates results.

---

## Objectives

### 1. Full training run

```bash
python -m src.pipeline.training.train_classifier \
    --epochs 5 --batch-size 32 --lr 2e-5 --device cuda
```

- Train: 38,007 samples, Val: 4,750 samples
- Expected: ~30-60 min on GPU
- Outputs in `models/e5_classifier/`: `model.pt`, `config.json`, `training_log.json`

### 2. Analyze results

After training completes:
- Report per-epoch loss, val_axis_acc, val_query_acc from `training_log.json`
- Compare final val_query_acc against baselines:
  - Rules: 100% per-query on 20-query dev sample
  - Phi-4 classify: 100% per-query on 20-query dev sample
  - Llama extract: 70% per-query on 20-query dev sample

### 3. Quick inference test

Run the trained model on a few sample queries to verify predictions are sensible (not random):
- Use `ClassifierParamExtractor` to extract parameters from 5 known queries
- Compare predictions against ground truth

---

## Acceptance Criteria

- [ ] 5-epoch training run completes on GPU
- [ ] `models/e5_classifier/model.pt` contains the best checkpoint
- [ ] `training_log.json` shows improving val accuracy across epochs
- [ ] val_axis_acc > 80% (minimum viable; rules baseline is 100%)
- [ ] Inference test: ≥3/5 queries return correct parameters
- [ ] No existing files modified

---

## Out of Scope

- Pipeline integration (Phase C)
- Full 16,590-query evaluation (Phase C)
- Hyperparameter tuning (backlog)
