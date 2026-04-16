# Sprint LW-06 — Fix Training Data Source (short→long) + Re-evaluation

**Prerequisites:** Sprint LW-05 complete (revealed data leakage issue)

---

## Problem

The classifier was trained on `OEB_short_norm.parquet` (short text / resumen) — the same distribution as the 16,590 evaluation queries. This creates two issues:

1. **Data leakage:** Many evaluation queries were in the training set (80% of 47,508 items → 38,007 in train)
2. **No generalization test:** Training and testing on the same catalog-generated text cannot answer the research question about robustness to novel queries

## Fix

Train on `OEB_long_norm.parquet` (long text / texto) instead. Both parquets share identical `item_key`, `parent_key`, and `parameters` columns. Short text queries become a fully held-out cross-distribution test.

Validation during training uses long text (same distribution as training). The full short text evaluation (16,590 queries) is the held-out cross-distribution test.

## Steps

### Step 1: Regenerate training data

```bash
python src/pipeline/training/data_prep.py --data-dir data/processed
```

Verify: same 47,508 rows, same label distribution, but text is now long-form (~511 chars avg vs ~141 chars).

### Step 2: Retrain the model

```bash
# In Docker (jupyter-pytorch container)
python -m src.pipeline.training.train_classifier --epochs 5 --batch-size 32 --device cuda
```

### Step 3: Full evaluation (16,590 queries)

```bash
python scripts/run_full_eval.py structured_pipeline_classifier --device cuda
python scripts/run_full_eval.py structured_pipeline_oracle_classifier --device cuda
```

## Acceptance Criteria

- [ ] `data_prep.py` reads `OEB_long_norm.parquet` (not short)
- [ ] `classifier_training_data.parquet` regenerated with long text
- [ ] Model retrained — checkpoint saved at `models/e5_classifier/model.pt`
- [ ] Both conditions complete on 16,590 queries
- [ ] `runs/<condition>/metrics_dual.json` produced for each
- [ ] Results compared against LW-05 baselines and prior results
- [ ] Research log updated: LW-05 results marked as invalidated, LW-06 results added
