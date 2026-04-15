# Research Protocol: Lightweight Classifiers for Parametric Extraction in Structure-Aware Retrieval

**Branch:** `lightweight-extraction`
**Repo:** `bc3cat-retrieval`
**Author:** César · April 2026
**Target:** Second publication (follow-up to SEPLN 2026 paper)

---

## 1. Purpose and Scope

This protocol is the **implementation roadmap** for a follow-up study to the SEPLN 2026 paper on structure-aware retrieval. The SEPLN paper showed that Stage 2 (parameter extraction) is the pipeline bottleneck and that LLMs are overkill: a rule-based extractor outperforms Phi-4 14B while being 60,000× faster. This study investigates whether **lightweight trained classifiers** can replace both rules and LLMs in Stage 2, combining the language understanding of neural models with the output reliability of constrained classification.

**Research question:** Can a fine-tuned encoder (BERT-class, ~100M parameters) match or exceed LLM-based extraction accuracy on the BC3CAT benchmark, while approaching rule-based speed? And critically — does it generalize better than rules when queries deviate from catalog-generated text?

**Branch structure:**

The `lightweight-extraction` branch is created from `structured-retrieval`. Prior research documents have been moved to `docs/structured-retrieval/`. New documents live in `docs/lightweight-extraction/`.

**Companion documents:**

| Document | Role | When updated |
|---|---|---|
| `docs/lightweight-extraction/RESEARCH_PROTOCOL_LIGHTWEIGHT.md` | This file; roadmap and backlog | When tasks are added/reprioritized |
| `CLAUDE.md` | Persistent context for Claude Code | After every sprint |
| `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT.md` | Running record of decisions, results, issues | After every sprint |
| `sprints/SPRINT_LW_NN.md` | Individual sprint prompt for Claude Code | Written just before each sprint |

**Prior research (read-only reference):**

| Document | Location |
|---|---|
| SEPLN paper | `docs/structured-retrieval/sepln_paper.tex` |
| Research proposal | `docs/structured-retrieval/RESEARCH_PROPOSAL.md` |
| Research protocol | `docs/structured-retrieval/RESEARCH_PROTOCOL.md` |
| Research log | `docs/structured-retrieval/RESEARCH_LOG.md` |
| Claude Code context | `docs/structured-retrieval/CLAUDE_STRUCTURED_RETRIEVAL.md` |

**Relationship to prior work:**

| What | Reuse from `structured-retrieval` | Build new |
|---|---|---|
| Stage 1 (E5 concept retrieval) | ✅ As-is | — |
| Stage 2 (parameter extraction) | Baselines only (rules, LLMs) | **Multi-head classifier** |
| Stage 3 (catalog lookup) | ✅ As-is | — |
| Evaluation infra | ✅ `run_full_eval.py`, query set, metrics | New conditions only |
| Schema / data | ✅ `OEB_concept_schema.json`, parquet files | Training set generation |

---

## 2. Sprint Workflow

Same as the SEPLN protocol: sprints are not pre-planned in detail. César drafts `sprints/SPRINT_LW_NN.md` just-in-time, Claude Code executes, César updates logs and context.

---

## 3. Motivation and Prior Evidence

### 3.1 Why LLMs Are Overkill

The SEPLN results provide three pieces of evidence:

1. **The task is classification, not generation.** Each parameter axis has 2–8 discrete values plus null. The LLM's generative capacity is wasted — worse, it introduces normalization errors (returning "1.10" instead of "1,10 m") that a classifier cannot produce by design.

2. **Rules already set a high bar without any understanding.** The rule-based extractor achieves 90.3% item Acc@1 (91.4% oracle) using pure substring matching. Its failures are concentrated on a single axis (TRABAJO, 93.9% accuracy) where compound textual values resist simple matching.

3. **The best LLM prompt mode is already classification.** Phi-4 classify (closed-set selection) achieves 100% per-axis accuracy on the 20-query dev sample and 87.7% on the full benchmark. This is literally a classification task dressed up as text generation.

### 3.2 What a Lightweight Classifier Could Add

- **Over rules:** Language understanding for the TRABAJO axis (the 1,017 null extractions that account for ~70% of rules oracle errors), and robustness to paraphrased/abbreviated queries where substring matching fails.
- **Over LLMs:** Guaranteed output normalization (class indices, not generated text), 100–1000× faster inference (~1–5ms vs 585–886ms), no GPU-heavy infrastructure for inference, deterministic behavior.

### 3.3 The Label Space

From `OEB_concept_schema.json`, the 25 concept groups use 13 unique axis labels. The full label inventory:

| Axis label | Distinct values | Concept groups using it | Notes |
|---|---|---|---|
| TRABAJO | 2–8 | ~20 | Compound values combining shift type + conditions. Hardest axis. |
| CONDICIONES DE EJECUCIÓN | 2–4 | ~20 | "Volumen relevante", "Volumen escaso", etc. |
| TIPO DE TERRENO | 3 | ~6 | "Sin clasificar", "Bajo vías", "Rocoso" |
| Nº TUBOS | 4 | ~6 | "1", "2", "3", "4" |
| BANDA DE MANTENIMIENTO | 2–4 | ~12 | Time interval ranges |
| PAVIMENTO | 2–3 | ~6 | "Con reposición", "Sin reposición" |
| PROFUNDIDAD | 3–8 | ~4 | Range-format values: "hasta 0,80 m", "de 0,81 a 1,10 m" |
| TUBO | 2–3 | ~2 | Pipe diameter in inches |
| DIÁMETROS | 2–4 | ~2 | Diameter values |
| DIÁMETRO | 2–4 | ~2 | Diameter values (variant naming) |
| TIPO DE MAQUINARIA | 2 | 1 | "Retroexcavadora", "Miniretroexcavadora" |
| TIPO DE REFUERZO | 2 | 1 | Reinforcement type |
| TIPO | 2–3 | 1 | Generic type label |

Key observation: the total number of (axis, value) pairs across all concept groups is small — likely under 200. This is a tiny classification problem.

---

## 4. Proposed Approach: Multi-Head Classifier with Per-Group Heads

### 4.1 Architecture

```
Query text
  │
  ▼
[E5 encoder] (intfloat/multilingual-e5-base, 278M params, 768-dim)
  │
  ▼
[CLS] token embedding (768-dim)
  │
  ├──► Head_(OEB010$, TERRENO):     Linear(768, 3+1) → softmax
  ├──► Head_(OEB010$, PAVIMENTO):   Linear(768, 2+1) → softmax
  ├──► Head_(OEB010$, CONDICIONES): Linear(768, 4+1) → softmax
  ├──► Head_(OEB030$, TRABAJO):     Linear(768, 8+1) → softmax
  ├──► Head_(OEB030$, NUM_TUBOS):   Linear(768, 4+1) → softmax
  ├──► ...one head per (concept_group, axis) pair
  └──► ~60–80 heads total, each with a small output space
```

Each head is a linear layer that outputs a distribution over the axis's value set **plus a `null` class** (parameter not mentioned in query). At inference time, only the heads corresponding to the query's concept group are active; all others are ignored. The +1 in each head's output dimension is the null class.

We use `intfloat/multilingual-e5-base` as the backbone because it is already used in Stage 1 — this enables a single-model pipeline where the same encoder handles both concept retrieval and parameter classification.

### 4.2 Training

- **Input:** `(query_text, concept_group_id)` — the concept group tells us which heads to activate
- **Labels:** one ground-truth value per axis (from the `parameters` column), or `null` if the query doesn't mention that axis
- **Loss:** sum of cross-entropy over active heads only — the model is never penalized for inactive heads
- **Data:** 47,508 (query, label_vector) training pairs from `OEB_short_norm.parquet`

### 4.3 Why Per-Group Heads

Each (concept_group, axis) pair gets its own classification head. This means the OEB010$ TERRENO head only ever chooses among {"Sin clasificar", "Bajo vías", "Rocoso", null} — it never sees values from other groups.

The parameter overhead is negligible: ~80 heads × 768 input × ~10 output ≈ 600K parameters on top of the encoder's 278M.

**Alternative architectures considered (not pursued for now):**
- *Shared heads:* One head per unique axis label (13 heads), shared across all concept groups using that axis. Would test cross-group generalization but requires unionizing value sets and risks confusion between group-specific values.
- *Single universal head:* One head over all ~200 (axis, value) pairs. Simplest, but mixes unrelated axes.
- *NER / sequence labeling:* Tag parameter spans at the token level using BIO scheme, then normalize spans to canonical values. More interpretable (shows which tokens triggered each extraction) but requires a span-to-value normalization step that reintroduces the same normalization errors that plague LLMs. Kept in the backlog as a secondary experiment.

---

## 5. Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Base encoder model | **`intfloat/multilingual-e5-base`** (278M params) | Already used in Stage 1 — enables single-model pipeline. If performance is poor, consider BETO or other Spanish encoders as fallback. |
| Classifier architecture | **Per-group heads** | One head per (concept_group, axis) pair. Avoids cross-group vocabulary confusion; negligible parameter overhead. |
| Training data source | **`OEB_short_norm.parquet`** (query text from `text_norm` column) + labels from `parameters` column | Both short and long parquet files share the same `item_key`, `parent_key`, and `parameters` columns. Short descriptions are used as queries throughout the evaluation. |
| Train/val/test split | **Concept-group-aware split.** Hold out concept groups, not random items. | Tests generalization to unseen axis combinations. Also do random split for comparison. |
| Query text field | **`text_norm`** (normalized text) | Matches what the existing pipeline uses in evaluation |
| Null label handling | **Explicit null class per head** | Queries may not mention all parameters; the model must learn to predict "not specified" |
| Training: which heads to activate | **Only heads for axes present in the query's concept group** | Avoids penalizing the model for unrelated axes |
| Evaluation | **Same 16,590 queries, same metrics, same `run_full_eval.py`** | Direct comparability with all prior results |

---

## 6. Task Backlog

### Phase A — Data Preparation

- **A1. Branch setup.** Create `lightweight-extraction` from `structured-retrieval`. Move prior docs to `docs/structured-retrieval/`. Set up `docs/lightweight-extraction/` with protocol, log, CLAUDE.md. Create `sprints/` directory for new sprint files.

- **A2. Training data generation.** From `OEB_short_norm.parquet` + `OEB_concept_schema.json`:
  - For each query row: extract `(text_norm, parent_key, {axis_label: value})` from the `parameters` column
  - Produce a clean dataset: `data/processed/classifier_training_data.parquet` with columns: `query_text`, `parent_key`, `axis_labels`, `axis_values` (dict)
  - Verify: 47,508 rows, all axis values present in schema
  - Split: stratified by concept group. 80/10/10 train/val/test.

### Phase B — Multi-Head Classifier

- **B1. Model implementation.** `src/pipeline/param_extractor_classifier.py`:
  - `ParameterClassifier` class wrapping `intfloat/multilingual-e5-base` + per-group classification heads
  - Same interface as `LLMParamExtractor` and `RuleBasedParamExtractor`: `extract(parent_key, query)` → `{axis: value | None}`
  - Training loop with active-head masking (only compute loss on relevant axes)
  - Checkpoint saving/loading

- **B2. Training run.** Train E5 backbone + per-group heads.
  - Hyperparameters: lr=2e-5, batch=32, epochs=5–10, warmup=10%
  - Track per-axis val accuracy at each epoch
  - Save best checkpoint by val item-level accuracy

- **B3. Sanity test.** Run classifier on the 20-query dev sample and 50-query pipeline sample. Compare per-axis accuracy against rules (100%) and LLMs (77–100%).

### Phase C — Integration and Full Evaluation

- **C1. Pipeline integration.** Wire classifier into `structured_pipeline.py` as a new Stage 2 variant. Create proxy modules, configs, pseudo-index dirs. Conditions:
  - `structured_pipeline_classifier` (pipeline + E5 classifier)
  - `structured_pipeline_oracle_classifier` (oracle + E5 classifier)

- **C2. Full evaluation run.** Both conditions on 16,590 queries. Produce `metrics_dual.json`. Compare against all prior baselines.

- **C3. Speed benchmark.** Measure inference time per query for each method on CPU and GPU:
  - Rules (~0.015ms)
  - E5 classifier (~?ms — expected 1–5ms)
  - Llama 3.1 8B (~585ms)
  - Phi-4 14B (~886ms)

### Phase D — Robustness Analysis

- **D1. Query augmentation.** Generate perturbed queries to test generalization:
  - **Synonym substitution:** Replace parameter values with synonyms/paraphrases (e.g., "Nocturno" → "turno de noche", "3 tubos" → "triple tubo")
  - **Abbreviation:** Truncate/abbreviate query text (e.g., "canalización hormigonada" → "canal. hormig.")
  - **Number format variation:** Change numeric formats (e.g., "3" → "tres", "1,10 m" → "1.1m")
  - **Noise injection:** Typos, missing words, reordered phrases
  - Method: LLM-generated paraphrases (via API) + manual review of a sample

- **D2. Robustness evaluation.** Run rules, classifier, and best LLM on augmented queries. Compare degradation curves. The hypothesis: classifier degrades less than rules, comparably to LLMs.

- **D3. Cross-validation by concept group.** Leave-one-group-out evaluation: train on 24 groups, test on the held-out group. Tests whether the classifier generalizes to unseen axis value combinations.

### Phase E — Analysis and Paper

- **E1. Error analysis.** Classify failures by the same taxonomy as SEPLN: E1-WRONG_CONCEPT, E2-PARTIAL_EXTRACT, E2-WRONG_VALUE. Compare error profiles across methods.

- **E2. Paper draft.** Focus on the efficiency vs. accuracy tradeoff. Key narrative: "LLMs are overkill for structured parameter extraction in parametric catalogs — a 278M-parameter fine-tuned encoder matches a 14B-parameter LLM while being 100× faster and eliminating normalization errors by design."

### Backlog (if time permits)

- NER / sequence labeling approach: BIO token tagging + span-to-value normalization (more complex, but more interpretable)
- Alternative encoder backbones: BETO (`dccuchile/bert-base-spanish-wwm-cased`), RoBERTa-BNE (`PlanTL-GOB-ES/roberta-base-bne`)
- Shared heads (A1 architecture): one head per unique axis label, shared across concept groups
- Distillation: use LLM extraction outputs as soft labels for training the classifier
- Ensemble: rules + classifier voting
- Adapter/LoRA instead of full fine-tuning
- SetFit or other few-shot approaches for low-data concept groups
- Multi-task learning across concept groups (shared lower layers, group-specific heads)

---

## 7. Evaluation Conditions

| Condition | Stage 1 | Stage 2 | Purpose |
|---|---|---|---|
| `structured_pipeline_classifier` | E5 retrieval | E5 multi-head classifier | **Main result** |
| `structured_pipeline_oracle_classifier` | Ground-truth concept | E5 multi-head classifier | Isolate classifier accuracy |

Existing baselines for comparison (no re-running):
- Rules pipeline/oracle: 90.3% / 91.4%
- Phi-4 classify pipeline/oracle: 87.7% / 88.6%
- Llama extract pipeline/oracle: 80.9% / 82.1%
- BM25 param-aware: 97.4%
- BM25 standard: 86.9%
- All neural baselines (ColBERT, E5, BGE-M3)

---

## 8. Diagnostic Interpretation

| Observation | Interpretation |
|---|---|
| Classifier oracle > rules oracle (91.4%) | Classifier learns language understanding that rules lack (especially TRABAJO axis) |
| Classifier oracle ≈ rules oracle | Classifier learns the same substring patterns; no understanding advantage on this benchmark |
| Classifier oracle ≈ Phi-4 classify oracle (88.6%) | Classifier matches LLM with 100× less compute — the main efficiency result |
| Classifier oracle > Phi-4 classify oracle | Classifier benefits from task-specific training vs. zero-shot LLM |
| Classifier augmented > rules augmented | Classifier generalizes better to paraphrased queries (key hypothesis) |
| Classifier augmented ≈ rules augmented | Task is fundamentally pattern matching — understanding doesn't help (also publishable) |

---

## 9. New File Map

```
src/
  pipeline/
    param_extractor_classifier.py    # B1 — Multi-head E5 classifier
    training/
      __init__.py
      train_classifier.py            # B2 — Training script for multi-head classifier
      data_prep.py                   # A2 — Training data generation
      augment_queries.py             # D1 — Query augmentation
  retrievers/
    structured_pipeline_classifier.py        # C1 — proxy module
    structured_pipeline_oracle_classifier.py  # C1 — proxy module

configs/
    structured_pipeline_classifier.yaml
    structured_pipeline_oracle_classifier.yaml

data/processed/
    classifier_training_data.parquet   # A2 output
    augmented_queries.parquet          # D1 output

models/
    e5_classifier/                     # B2 — trained E5 model + per-group heads

analysis/
    robustness_comparison.csv          # D2 output
    classifier_error_analysis.csv      # E1 output

docs/lightweight-extraction/
    RESEARCH_PROTOCOL_LIGHTWEIGHT.md   # This file
    RESEARCH_LOG_LIGHTWEIGHT.md        # Running log

docs/structured-retrieval/             # Prior research (read-only reference)
    sepln_paper.tex
    RESEARCH_PROPOSAL.md
    RESEARCH_PROTOCOL.md
    RESEARCH_LOG.md
    CLAUDE_STRUCTURED_RETRIEVAL.md
```

---

## 10. Risk Register

| Risk | Mitigation |
|---|---|
| Training data is all catalog-generated (same limitation as eval) | Phase D augmentation tests robustness; acknowledge as limitation |
| 47,508 training pairs may be redundant (same concept group → similar queries) | Concept-group-aware splitting; monitor for overfitting on val set |
| Per-group heads require concept group to be known at inference time | Stage 1 provides this; oracle condition isolates classifier from Stage 1 errors |
| Small concept groups (3 items) → very few training examples for some heads | Cross-group head sharing (shared-heads architecture) as fallback; data augmentation |
| E5 encoder may not be optimal for classification (trained for retrieval, not classification) | If performance is notably poor, try BETO or RoBERTa-BNE as fallback encoders |
| Classifier may just learn the same substring patterns as rules | Phase D robustness test is the key differentiator; if no improvement, that is itself a publishable finding |

---

## 11. Changelog

| Version | Date | Changes |
|---|---|---|
| v0.1 | April 2026 | Initial protocol — multi-head E5 classifier, per-group heads, task backlog, robustness evaluation plan |

---

*This document is the stable roadmap. Sprint-level detail lives in `sprints/SPRINT_LW_NN.md` files, written just-in-time.*
