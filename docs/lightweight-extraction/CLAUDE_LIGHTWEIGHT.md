# Lightweight Extraction — Branch Context for Claude Code

**Branch:** `lightweight-extraction`
**Goal:** Replace LLM-based parameter extraction (Stage 2) with a fine-tuned multi-head classifier (~100M params).
**Do not modify existing files from `main` or `structured-retrieval`.** All new work lives in new files on this branch.

---

## The Problem in One Paragraph

The SEPLN 2026 paper showed that in the three-stage structured retrieval pipeline, Stage 2 (parameter extraction) is the bottleneck. LLMs (Llama 3.1 8B, Phi-4 14B) are overkill: a rule-based substring matcher achieves 90.3% item Acc@1 while being 60,000x faster. But rules are brittle — they fail when queries deviate from catalog-generated text. This branch investigates whether a fine-tuned encoder (BERT-class) can combine the language understanding of neural models with the output reliability of constrained classification.

## Reference Documents

- `docs/lightweight-extraction/RESEARCH_PROTOCOL_LIGHTWEIGHT.md` — research goals, approach, task backlog
- `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT.md` — running record of what happened in each sprint
- `sprints/SPRINT_LW_NN.md` — the current sprint's objectives and acceptance criteria

**Prior research (read-only):**
- `docs/structured-retrieval/` — all SEPLN paper documents (proposal, protocol, log, Claude context)

## Sprint Closure Checklist

After completing each sprint, **always** do the following before moving on:

1. Commit sprint code changes
2. Update `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT.md` with results
3. Update this file's Sprint History section (if new context is needed)
4. Commit doc updates
5. Push

---

## Pipeline Architecture (unchanged from structured-retrieval)

```
Query
  |
  v
[Stage 1] Item-level E5 retrieval (intfloat/multilingual-e5-base)
  |  -> top-1 item -> parent_key derived from item_key mapping
  |  -> candidate set: all items in that concept group
  v
[Stage 2] Parameter extraction   <<<--- THIS IS WHAT WE'RE REPLACING
  |  -> extracted: {axis_label: value | null, ...}
  v
[Stage 3] Deterministic catalog lookup
  |  -> exact match on extracted parameters within candidate set
  v
Result (single item_key, or ranked sub-group if extraction is partial)
```

Stage 1 and Stage 3 are reused as-is. Only Stage 2 changes.

---

## New Stage 2: Multi-Head E5 Classifier

### Architecture

```
Query text
  |
  v
[E5 encoder] (intfloat/multilingual-e5-base, 278M params, 768-dim)
  |
  v
[CLS] token embedding (768-dim)
  |
  +---> Head_(OEB010$, TERRENO):     Linear(768, 3+1) -> softmax
  +---> Head_(OEB010$, PAVIMENTO):   Linear(768, 2+1) -> softmax
  +---> Head_(OEB030$, TRABAJO):     Linear(768, 8+1) -> softmax
  +---> ...one head per (concept_group, axis) pair
  +---> ~60-80 heads total, each with a small output space (+1 = null class)
```

At inference, only heads for the query's concept group are active.

### Key Design Decisions

| Decision | Value | Rationale |
|---|---|---|
| Base encoder | `intfloat/multilingual-e5-base` | Same as Stage 1 — enables single-model pipeline |
| Head structure | One per (concept_group, axis) pair | Avoids cross-group value confusion |
| Null class | Explicit per head | Queries may not mention all parameters |
| Training data | 47,508 pairs from `OEB_long_norm.parquet` | Train on documents; short text queries are held-out cross-distribution eval |
| Split strategy | Concept-group-aware | Tests generalization to unseen axis combinations |

### Extractor Interface

Same contract as `LLMParamExtractor` and `RuleBasedParamExtractor`:
```python
extractor.extract(parent_key, query_text) -> {axis_label: value | None, ...}
extractor.extract_batch(parent_keys, query_texts) -> list[dict]
```

---

## Data Structures (unchanged)

**Concept schema** (`data/processed/OEB_concept_schema.json`):
25 concept groups. 13 unique axis labels. Total (axis, value) pairs < 200.

**Parquet files** (`data/processed/`):
- `OEB_long_norm.parquet` / `OEB_long_feats.parquet` — 47,514 rows with `item_key`, `parent_key`, `concept`, `parameters`, `text`

---

## Baseline Results (from SEPLN paper, 16,590 queries)

| Stage 2 Method | item Acc@1 | parent Acc@1 | Speed |
|---|---|---|---|
| Rules (pipeline) | 90.3% | 98.5% | 0.015ms/query |
| Rules (oracle) | 91.4% | 100.0% | 0.015ms/query |
| Phi-4 classify (pipeline) | 87.7% | 98.5% | ~886ms/query |
| Phi-4 classify (oracle) | 88.6% | 100.0% | ~886ms/query |
| Llama extract (pipeline) | 80.9% | 98.5% | ~585ms/query |
| Llama extract (oracle) | 82.1% | 100.0% | ~585ms/query |

**Also for reference:** BM25 param-aware tokens: 97.4% (best overall, domain-specific tokenization).

---

## New Files in This Branch

```
src/
  pipeline/
    param_extractor_classifier.py    # Multi-head E5 classifier (Phase B)
    training/
      __init__.py
      data_prep.py                   # Training data generation (Phase A)
      train_classifier.py            # Training script (Phase B)
      augment_queries.py             # Query augmentation (Phase D)
  retrievers/
    structured_pipeline_classifier.py        # Proxy module (Phase C)
    structured_pipeline_oracle_classifier.py  # Proxy module (Phase C)

configs/
    structured_pipeline_classifier.yaml
    structured_pipeline_oracle_classifier.yaml

data/processed/
    classifier_training_data.parquet   # Training data
    augmented_queries.parquet          # Augmented queries (Phase D)

models/
    e5_classifier/                     # Trained model checkpoints

docs/lightweight-extraction/
    RESEARCH_PROTOCOL_LIGHTWEIGHT.md
    RESEARCH_LOG_LIGHTWEIGHT.md
    CLAUDE_LIGHTWEIGHT.md              # This file
```

---

## Evaluation Conditions

| Condition | Stage 1 | Stage 2 | Purpose |
|---|---|---|---|
| `structured_pipeline_classifier` | E5 retrieval | E5 multi-head classifier | Main result |
| `structured_pipeline_oracle_classifier` | Ground-truth concept | E5 multi-head classifier | Isolate classifier accuracy |

---

## Sprint History

*Newest entries at the top.*

### Sprint LW-07 — Frozen Encoder Baseline Experiment
**Date:** April 2026
**What changed:**
- Added `--freeze-encoder` flag; trained variant with only classification heads learnable (~45K params)
- Created separate pipeline infrastructure (2 index dirs, 2 proxies)
- Frozen val accuracy (long): 11.4% (vs 99.6% full FT)
- Frozen cross-dist (short): **0.56%** pipeline / **0.58%** oracle (vs 20.9% / 21.2% full FT)
- Hypothesis "full FT counterproductive" REJECTED. E5 pretrained CLS insufficient; representation adaptation is necessary.

### Sprint LW-06 — Fix Training Data Source (short→long) + Re-evaluation
**Date:** April 2026
**What changed:**
- Fixed data leakage: retrained classifier on `OEB_long_norm.parquet` (long text)
- Val accuracy on long text: 99.6% (comparable to LW-03's 99.7%)
- Cross-distribution eval (short text queries): **20.9% item Acc@1** — classifier does not generalize
- LW-05's 96.6% was entirely data leakage; real cross-distribution performance is ~21%

### Sprint LW-05 — Full Evaluation (16,590 queries) — INVALIDATED
**Date:** April 2026
**What changed:**
- Full eval on 16,590 queries: classifier pipeline 96.6%, oracle 97.6% item Acc@1
- ⚠️ Results invalidated: data leakage (trained on same distribution as eval queries)

### Sprint LW-04 — Pipeline Integration
**Date:** April 2026
**What changed:**
- Classifier wired into `structured_pipeline.py` as `stage2_method: "classifier"`
- 2 proxy modules, 2 YAML configs, 2 pseudo-index dirs (24 total variants)
- Docker/Windows path resolution and cross-PyTorch compatibility fixed
- Pipeline test passed: `search()` and `search_batch()` work end-to-end

### Sprint LW-03 — Full Training Run
**Date:** April 2026
**What changed:**
- Trained on RTX 4090: 5 epochs, ~30 min total
- Best val_query_acc: 99.7%, val_axis_acc: 99.9%
- Checkpoint saved at `models/e5_classifier/model.pt`

### Sprint LW-02 — Multi-Head Classifier Implementation
**Date:** April 2026
**What changed:**
- Created `src/pipeline/param_extractor_classifier.py` — model + extractor with same interface as rules/LLM
- Created `src/pipeline/training/train_classifier.py` — full training loop with validation and early stopping
- 97 heads, 278.5M params. Sanity test passed (100 samples, 1 epoch).

### Sprint LW-01 — Training Data Generation
**Date:** April 2026
**What changed:**
- Created `src/pipeline/training/data_prep.py`
- Produced `classifier_training_data.parquet` (47,508 rows, 80/10/10 split) and `classifier_label_encoders.json` (97 heads, 556 classes)
- OEB160$ (3 items) placed entirely in train due to small size

### Sprint LW-00 — Branch Setup
**Date:** April 2026
**What changed:**
- Created branch from `structured-retrieval` (commit `97870b1`)
- Moved prior docs to `docs/structured-retrieval/`
- Created documentation: protocol, log, Claude Code context
- Updated `CLAUDE.md` with branch pointers
