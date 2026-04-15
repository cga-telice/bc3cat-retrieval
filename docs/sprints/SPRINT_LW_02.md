# Sprint LW-02 — Multi-Head Classifier Implementation

**Tasks from backlog:** B1 (model implementation)
**Prerequisites:** Sprint LW-01 complete (training data + label encoders available)

---

## Context

Training data is ready:
- `data/processed/classifier_training_data.parquet` — 47,508 rows with `query_text`, `parent_key`, `labels` (JSON dict), `split`
- `data/processed/classifier_label_encoders.json` — 97 (group, axis) heads, each mapping value strings to integer indices (0 = null)

This sprint implements the model and training loop. The extractor must match the interface of `RuleBasedParamExtractor` and `LLMParamExtractor`:
```python
extractor.extract(parent_key, query_text) -> {axis_label: value | None, ...}
extractor.extract_batch(parent_keys, query_texts) -> list[dict]
```

Read `docs/lightweight-extraction/CLAUDE_LIGHTWEIGHT.md` for the full architecture description.

**Do not modify any existing files.**

---

## Architecture Recap

```
Query text → E5 encoder → [CLS] embedding (768-dim)
                              |
                              ├→ Head_(OEB010$, TERRENO): Linear(768, 4) → softmax
                              ├→ Head_(OEB010$, PAVIMENTO): Linear(768, 3) → softmax
                              ├→ ...97 heads total
                              └→ only heads for the query's parent_key are active
```

Each head output dim = number of values + 1 (null class at index 0).

---

## Objectives

### 1. Implement the classifier model

Create `src/pipeline/param_extractor_classifier.py` with:

**`MultiHeadClassifier(nn.Module)`:**
- `__init__(self, encoder_name, label_encoders)`:
  - Loads `intfloat/multilingual-e5-base` via `transformers.AutoModel`
  - Creates one `nn.Linear(768, num_classes)` per (parent_key, axis) pair
  - Stores heads in a `nn.ModuleDict` keyed by `"{parent_key}__{axis_label}"` (double underscore separator to avoid collisions with axis names containing single underscores)
- `forward(self, input_ids, attention_mask, head_keys)`:
  - Runs encoder, extracts [CLS] token (index 0)
  - Returns dict `{head_key: logits}` for requested head_keys only
- `predict(self, parent_key, query_text, tokenizer)`:
  - Tokenizes with E5 "query: " prefix (same as retrieval)
  - Runs forward for all heads of the given parent_key
  - Returns `{axis_label: value | None}` (argmax per head, index 0 → None)

**`ClassifierParamExtractor`:**
- Same interface as `RuleBasedParamExtractor` / `LLMParamExtractor`
- `__init__(self, model_dir, device="cpu")`: loads checkpoint + label encoders + tokenizer
- `extract(self, parent_key, query_text) -> dict`: delegates to `model.predict()`
- `extract_batch(self, parent_keys, query_texts) -> list[dict]`: batched inference

### 2. Implement the training script

Create `src/pipeline/training/train_classifier.py` with:

- Loads `classifier_training_data.parquet` and `classifier_label_encoders.json`
- `ClassifierDataset(Dataset)`: returns tokenized query + target indices for active heads
- Training loop:
  - Optimizer: AdamW, lr=2e-5, weight_decay=0.01
  - Scheduler: linear warmup (10% of steps) + linear decay
  - Epochs: 5 (configurable via `--epochs`)
  - Batch size: 32 (configurable via `--batch-size`)
  - Loss: sum of cross-entropy over active heads per sample
  - Validation: per-axis accuracy and per-query accuracy after each epoch
  - Early stopping: save best checkpoint by val per-query accuracy
- Saves to `models/e5_classifier/`:
  - `model.pt` — state dict (encoder + all heads)
  - `config.json` — hyperparams, label encoders path, encoder name
  - `training_log.json` — per-epoch metrics

**CLI:**
```
python -m src.pipeline.training.train_classifier \
    --data-dir data/processed \
    --output-dir models/e5_classifier \
    --epochs 5 \
    --batch-size 32 \
    --lr 2e-5 \
    --device cuda
```

### 3. Sanity test (no full training yet)

- Verify the model instantiates correctly: 97 heads, correct output dims
- Run 1 epoch on a small subset (100 samples) to confirm the training loop works end-to-end
- Verify `ClassifierParamExtractor.extract()` returns correct format (even with untrained model — values will be random)

---

## Implementation Notes

- **E5 query prefix:** The E5 model expects `"query: "` prepended to queries at inference. The training data `query_text` does NOT have this prefix — add it during tokenization in the Dataset/predict methods.
- **Tokenizer max length:** 512 tokens (E5's max). Queries are short (~50-100 tokens), so truncation is unlikely.
- **Head key format:** `"{parent_key}__{axis_label}"` — e.g., `"OEB010$__TERRENO"`. Use `nn.ModuleDict` which requires string keys.
- **Inverse label encoders:** For inference, build `{parent_key: {axis: {index: value}}}` to map predictions back to strings.
- **Gradient:** Fine-tune the full encoder (no frozen layers). Per the protocol, we try full fine-tuning first; LoRA/adapters are in the backlog.
- **Mixed precision:** Use `torch.cuda.amp` if on GPU for faster training.

---

## Acceptance Criteria

- [ ] `src/pipeline/param_extractor_classifier.py` exists with `MultiHeadClassifier` and `ClassifierParamExtractor`
- [ ] `src/pipeline/training/train_classifier.py` exists with `ClassifierDataset` and training loop
- [ ] Model instantiates with 97 heads, correct output dimensions
- [ ] 1-epoch sanity run on 100 samples completes without errors
- [ ] `ClassifierParamExtractor.extract(parent_key, query)` returns `{axis: value|None}` dict
- [ ] `ClassifierParamExtractor.extract_batch()` works
- [ ] Checkpoint saves/loads correctly
- [ ] No existing files modified

---

## Out of Scope

- Full training run (Sprint LW-03)
- Pipeline integration / proxy modules (Phase C)
- Hyperparameter tuning
- Alternative encoders (BETO, RoBERTa-BNE)
