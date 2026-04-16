# Research Log: Lightweight Classifiers for Parametric Extraction

**Branch:** `lightweight-extraction`
**Started:** April 2026

---

*Newest entries at the top. Updated after every sprint.*

---

## Sprint LW-06 — Fix Training Data Source (short→long) + Re-evaluation

**Date:** 2026-04-16
**What changed:**
- Discovered data leakage: classifier was trained on `OEB_short_norm.parquet`, same distribution as 16,590 eval queries
- Changed `data_prep.py` to use `OEB_long_norm.parquet` (long text / documents)
- Regenerated `classifier_training_data.parquet` (47,508 rows, avg 511 chars vs 141 chars)
- Retrained model on RTX 4090: 5 epochs, best val_query_acc: 99.6%
- Ran full evaluation on 16,590 queries for both conditions

**Training results (long text):**

| Epoch | Loss | val_axis_acc | val_query_acc | Time |
|---|---|---|---|---|
| 1 | 1.084 | 98.1% | 93.1% | 374s |
| 2 | 0.248 | 99.6% | 98.6% | 369s |
| 3 | 0.112 | 99.8% | 99.2% | 368s |
| 4 | 0.069 | 99.9% | 99.6% | 370s |
| 5 | 0.053 | **99.9%** | **99.6%** | 370s |

Val accuracy on long text is comparable to LW-03 (99.6% vs 99.7%) — the model learns parameter extraction equally well from longer text.

**Evaluation results (16,590 short-text queries — cross-distribution test):**

| Condition | item Acc@1 | parent Acc@1 | Runtime |
|---|---|---|---|
| E5 classifier (pipeline) | **20.9%** | 98.5% | 12m 16s |
| E5 classifier (oracle) | **21.2%** | 100.0% | 12m 27s |

**Comparison with LW-05 (invalidated) and baselines:**

| Condition | LW-06 (long→short) | LW-05 (short→short, LEAKED) | Rules | Phi-4 classify |
|---|---|---|---|---|
| Pipeline item Acc@1 | 20.9% | ~~96.6%~~ | 90.3% | 87.7% |
| Oracle item Acc@1 | 21.2% | ~~97.6%~~ | 91.4% | 88.6% |

**Key findings:**
- The classifier achieves near-perfect accuracy on long text validation (99.6%), proving it can extract parameters from detailed descriptions
- But when evaluated on short text queries (cross-distribution), accuracy collapses to ~21% — the classifier does NOT generalize across text distributions
- The ~75 pp drop from LW-05 confirms the prior results were almost entirely data leakage
- Parent Acc@1 is unaffected (98.5%/100%) — this is driven by Stage 1 E5 retrieval, not the classifier
- Oracle gap is tiny (20.9% → 21.2%) — the bottleneck is Stage 2, not Stage 1
- 13,117 missed queries (pipeline) — the classifier fails catastrophically on short text it hasn't seen

**Error analysis (detailed: [RESEARCH_LOG_LIGHTWEIGHT-06_Analysis.md](RESEARCH_LOG_LIGHTWEIGHT-06_Analysis.md)):**

The failure is caused by **surface-level formatting mismatch**, not a semantic understanding problem. Long text encodes parameters as explicit key-value pairs (`trabajo: diurno banda de mantenimiento: i < 3 horas`), while short text uses compressed parenthetical notation (`(diurno/i < "3" horas/volumen escaso)`). Per-axis accuracy on 2,000-query sample:

| Axis | Accuracy | Why |
|---|---|---|
| Nº TUBOS, PROFUNDIDAD, DIÁMETROS | 100% | Numbers transfer across formats |
| CONDICIONES DE EJECUCIÓN | 95.6% | Values identical in both formats |
| TIPO DE TERRENO | 69.1% | Short text abbreviates (`rocoso` vs `en terreno rocoso`) |
| BANDA DE MANTENIMIENTO | 62.9% | Operators differ: `i < "3"` vs `i < 3 horas` |
| TRABAJO | 52.5% | Worst — classifier adds "excepcional" to predictions without label context |

**Interpretation:**
The classifier learns format-specific pattern matching, not semantic parameter extraction. Numerical axes transfer perfectly; text-based axes fail because their surface encoding is completely different between long and short text. The classifier needs same-distribution training, or the architecture needs explicit cross-distribution transfer.

**Next steps to consider:**
1. Train on short text WITH proper held-out evaluation (concept-group holdout avoids leakage)
2. Mixed training: combine long + short text for distribution-invariant representations
3. Augment queries to bridge the distribution gap (Phase D from backlog)
4. Accept same-distribution training is required and reframe the research question

---

## Sprint LW-05 — Full Evaluation (16,590 queries) ⚠️ INVALIDATED

**Date:** 2026-04-16
**⚠️ These results have data leakage — classifier trained on same distribution as eval queries. See Sprint LW-06.**
**What changed:**
- Ran `run_full_eval.py` for both classifier conditions on RTX 4090 (Docker)
- Pipeline condition: 12m 52s (~47ms/query)
- Oracle condition: 11m 02s (~40ms/query)

**Results (16,590 queries):**

| Condition | item Acc@1 | parent Acc@1 | Runtime |
|---|---|---|---|
| E5 classifier (pipeline) | **96.6%** | 98.5% | 12m 52s |
| E5 classifier (oracle) | **97.6%** | 100.0% | 11m 02s |
| Rules (pipeline) | 90.3% | 98.5% | 10m 50s |
| Rules (oracle) | 91.4% | 100.0% | 13m 05s |
| Phi-4 classify (pipeline) | 87.7% | 98.5% | 5h 17m |
| Llama extract (pipeline) | 80.9% | 98.5% | 3h 27m |
| BM25 param-aware tokens | 97.4% | — | — |

**Key findings:**
- Classifier beats all structured pipeline baselines: +6.3 pp over rules, +8.9 pp over Phi-4 classify
- Oracle gap is only 1.0 pp (96.6% → 97.6%) — Stage 1 E5 retrieval is not the bottleneck
- Approaches BM25 param-aware (97.4%) to within 0.8 pp — and BM25 uses domain-specific tokenization
- 18x faster than Phi-4 (47ms vs 886ms), though slower than rules (47ms vs 0.015ms)
- The classifier learned to solve the TRABAJO axis problem that accounted for ~70% of rules oracle errors
- 569 missed queries (pipeline) vs 397 (oracle) — classifier errors are smaller and different from rules errors

**Known issues:**
- Queries are catalog-generated (same distribution as training) — robustness testing (Phase D) will reveal generalization

---

## Sprint LW-04 — Pipeline Integration

**Date:** 2026-04-16
**What changed:**
- Added `classifier` branch to `load()` in `src/retrievers/structured_pipeline.py`
- Created 2 proxy modules: `structured_pipeline_classifier.py`, `structured_pipeline_oracle_classifier.py`
- Created 2 YAML configs: `structured_pipeline_classifier.yaml`, `structured_pipeline_oracle_classifier.yaml`
- Added 2 classifier variants to `scripts/setup_structured_index.py` (24 total)
- Created pseudo-index dirs with `stage2_method: classifier`
- Fixed Docker/Windows path resolution for `model_dir` and `label_encoders_path`
- Fixed `strict=False` in model loading for cross-PyTorch-version compatibility (`position_ids` key)

**Pipeline test:**
- `load('index/structured_pipeline_classifier')` → loads E5 + classifier + catalog lookup
- `search()` and `search_batch()` return correct shapes and scores
- Integration verified on CPU

**Known issues:**
- None — ready for full evaluation (Sprint LW-05)

---

## Sprint LW-03 — Full Training Run

**Date:** 2026-04-16
**What changed:**
- Ran full training on RTX 4090: 38,007 train samples, 4,750 val samples, 5 epochs, batch 32, lr 2e-5
- Fixed `torch.amp` compatibility for older PyTorch in Docker container
- Best checkpoint saved at epoch 5

**Training results:**

| Epoch | Loss | val_axis_acc | val_query_acc | Time |
|---|---|---|---|---|
| 1 | 1.034 | 98.9% | 96.5% | 365s |
| 2 | 0.207 | 99.6% | 98.6% | 364s |
| 3 | 0.090 | 99.8% | 99.3% | 364s |
| 4 | 0.055 | 99.9% | 99.6% | 366s |
| 5 | 0.042 | **99.9%** | **99.7%** | 366s |

**Comparison with baselines (val set, same data distribution):**

| Method | per-axis acc | per-query acc | Speed |
|---|---|---|---|
| **E5 classifier** | **99.9%** | **99.7%** | ~1-5ms/query (est.) |
| Rules | 100% (20-q dev) | 100% (20-q dev) | 0.015ms/query |
| Phi-4 classify | 100% (20-q dev) | 100% (20-q dev) | 886ms/query |
| Llama extract | 87.8% (20-q dev) | 70% (20-q dev) | 585ms/query |

**Key observations:**
- 99.7% val_query_acc surpasses all LLM baselines on validation data
- Rapid convergence: 96.5% query accuracy after just 1 epoch
- Total training time: ~30 min on RTX 4090
- Note: val set has same distribution as train (catalog-generated queries) — real test is the full 16,590-query evaluation and robustness testing

**Known issues:**
- `torch.amp.GradScaler` API differs between PyTorch versions — added compatibility fallback
- Full evaluation (16,590 queries) not yet run — val results may not generalize identically

---

## Sprint LW-02 — Multi-Head Classifier Implementation

**Date:** 2026-04-16
**What changed:**
- Created `src/pipeline/param_extractor_classifier.py` — `MultiHeadClassifier` (E5 encoder + 97 per-(group, axis) heads) and `ClassifierParamExtractor` (drop-in replacement for rules/LLM extractors)
- Created `src/pipeline/training/train_classifier.py` — training loop with AdamW + linear warmup, per-axis/per-query validation, early stopping, mixed precision support
- Model: 278.5M parameters (278M E5 encoder + ~0.5M classification heads)

**Sanity test (100 samples, 1 epoch, CPU):**
- Training loop completes without errors (loss 1.61, 47s on CPU)
- val_query_acc 0% expected — too few samples for learning
- `extract()` and `extract_batch()` return correct format
- Checkpoint save/load verified

**Known issues:**
- `extract_batch()` iterates per-query (no batching across queries with same parent_key) — acceptable for now, optimization in backlog

---

## Sprint LW-01 — Training Data Generation

**Date:** 2026-04-15
**What changed:**
- Created `src/pipeline/training/` package with `data_prep.py`
- Script originally loaded `OEB_short_norm.parquet` (fixed to `OEB_long_norm.parquet` in Sprint LW-06); loads concept schema, filters to 47,508 leaf items, extracts per-axis labels from `parameters` column, splits 80/10/10 stratified by concept group
- Produced `data/processed/classifier_training_data.parquet` — columns: `query_text`, `item_key`, `parent_key`, `labels` (JSON dict), `split`
- Produced `data/processed/classifier_label_encoders.json` — 97 (group, axis) heads, 556 total classes (incl. null)

**Key stats:**
- Train: 38,007 / Val: 4,750 / Test: 4,751
- 25 concept groups in train, 24 in val/test (OEB160$ has only 3 items → all in train)
- All axis values from schema present in train split
- 3 spot-checks passed

**Known issues:**
- None

---

## Sprint LW-00 — Branch Setup

**Date:** 2026-04-15
**What changed:**
- Created `lightweight-extraction` branch from `structured-retrieval` (commit `97870b1`)
- Moved prior docs to `docs/structured-retrieval/`
- Created `docs/lightweight-extraction/` with protocol, log, Claude Code context
- Updated `CLAUDE.md` with branch-specific pointers

**Known issues:**
- None
