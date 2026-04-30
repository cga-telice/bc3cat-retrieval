# Lightweight Extraction (NER) — Branch Context for Claude Code

**Branch:** `lightweight-extraction-ner`
**Goal:** Replace the multi-head CLS classifier (Stage 2) with a token-level BIO tagger followed by deterministic span normalization, and test whether token-level evidence eliminates the cross-distribution gap that defeated the CLS architecture.
**Do not modify existing files from `main`, `structured-retrieval`, or `lightweight-extraction`.** All new work lives in new files on this branch.

---

## The Problem in One Paragraph

The `lightweight-extraction` branch closed with a clean negative result for the multi-head CLS classifier: 99.6% val_query_acc on the long-text training distribution, 20.9% on short-text queries (cross-distribution). LW-06 isolated the failure mechanism — the CLS classifier learned to condition on document-level cues (axis label literals like `trabajo:`, position within the text) that exist only in the long-text format. LW-07's frozen-encoder ablation ruled out overfitting as the cause: representation adaptation is necessary, but the adaptation that works also entangles surface-form patterns with semantic content. This branch tests the architectural alternative: a token-level BIO tagger that, by construction, must operate on token-level evidence — where the value tokens *do* transfer across distributions.

## Reference Documents

- `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md` — research goals, approach, task backlog
- `docs/lightweight-extraction-ner/RESEARCH_LOG_LIGHTWEIGHT_NER.md` — running record of what happened in each sprint
- `docs/sprints/SPRINT_LWN_NN.md` — the current sprint's objectives and acceptance criteria

**Prior research (read-only):**
- `docs/lightweight-extraction/` — CLS classifier branch documents (the negative result this branch follows up on)
- `docs/structured-retrieval/` — SEPLN paper documents (rules + LLM baselines)

## Sprint Closure Checklist

After completing each sprint, **always** do the following before moving on:

1. Commit sprint code changes
2. Update `docs/lightweight-extraction-ner/RESEARCH_LOG_LIGHTWEIGHT_NER.md` with results
3. Update this file's Sprint History section (if new context is needed)
4. Commit doc updates
5. Push

---

## Pipeline Architecture (unchanged from structured-retrieval / lightweight-extraction)

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

## New Stage 2: Shared BIO Tagger + Deterministic Span Normalizer

### Architecture

```
Token sequence (after tokenizer, with WordPiece subwords)
  |
  v
[E5 encoder] (intfloat/multilingual-e5-base, 278M params, full FT)
  |
  v
Per-token hidden states (T tokens × 768)
  |
  v
[BIO classification head]  single shared Linear(768, 27)
  |  labels: O, B-{axis}, I-{axis} for 13 unique axes -> 27 BIO labels
  |
  v
[Span extraction] (B-X / I-X tokens grouped into spans)
  |
  v
[Deterministic span normalizer]
  |  for each (axis, surface_text):
  |    1. Look up valid canonical values for (concept_group, axis) from schema
  |    2. Normalize span text (lowercase, strip, axis-specific rules)
  |    3. Exact match -> fuzzy match (Levenshtein <= 0.15) -> null
  |  output: {axis: canonical_value | None}
  v
[Stage 3] catalog lookup, unchanged
```

At inference, the head is shared across concept groups; the per-(group, axis) constraint is applied downstream by the normalizer.

### Key Design Decisions

| Decision | Value | Rationale |
|---|---|---|
| Base encoder | `intfloat/multilingual-e5-base` | Same as Stage 1 and prior CLS classifier — single-model pipeline; direct comparability |
| Head structure | **One shared Linear(768, 27)** across all concept groups | More data per head (~85% of corpus per axis) instead of fragmenting; consolidates training signal |
| Training data | `OEB_long_norm.parquet` (long catalog text) | Same as LW-06 — cross-distribution generalization is the property under test |
| Split strategy | Concept-group-stratified 80/10/10 | Same as LW-06 for direct comparability |
| Encoder freezing | Full fine-tuning (frozen variant in backlog) | LW-07 already showed frozen E5 cannot reach baseline performance |
| Normalization | Deterministic lookup against schema with edit-distance fallback | Eliminates LLM-style hallucination; closed set per (group, axis) ≤ 12 |
| Decoding | Greedy argmax + BIO post-processing | Simplest baseline; CRF in backlog |

### Extractor Interface

Same contract as `LLMParamExtractor`, `RuleBasedParamExtractor`, and `ClassifierParamExtractor`:
```python
extractor.extract(parent_key, query_text) -> {axis_label: value | None, ...}
extractor.extract_batch(parent_keys, query_texts) -> list[dict]
```

---

## Data Structures (unchanged)

**Concept schema** (`data/processed/OEB_concept_schema.json`):
25 concept groups. 13 unique axis labels. 97 total (group, axis) pairs. Per-axis canonical value sets ≤ 12 entries.

**Parquet files** (`data/processed/`):
- `OEB_long_norm.parquet` / `OEB_long_feats.parquet` — ~47k rows with `item_key`, `parent_key`, `concept`, `parameters`, `text_norm`

**New BIO artifacts** (this branch):
- `data/processed/bio_training_data.parquet` — `(item_key, parent_key, text_norm, tokens, bio_labels, alignment_confidence, split)`
- `data/processed/bio_label_inventory.json` — 27 BIO labels and integer indices

---

## Baseline Results to Beat

| Method | item Acc@1 (pipeline) | parent Acc@1 | Notes |
|---|---|---|---|
| dense_e5 (no FT, direct retrieval) | 13.4% | 98.2% | Lower bound for "fine-tuning helps" comparison |
| CLS classifier full FT | 20.9% | 98.5% | The cross-distribution failure being targeted |
| CLS classifier full FT (oracle) | 21.2% | 100.0% | Stage 2 ceiling for the CLS architecture |
| Phi-4 classify (pipeline) | 87.7% | 98.5% | LLM baseline (SEPLN) |
| Rules (pipeline) | 90.3% | 98.5% | Rule-based string matcher (SEPLN) |
| Rules (oracle) | 91.4% | 100.0% | Stage 2 ceiling for rules |
| BM25 param-aware | 97.4% | — | Domain-specific tokenization upper bound |

**Decision thresholds (protocol §8):**
- BIO oracle ≥ 90% → architectural choice fully closes the cross-distribution gap (strongest result)
- BIO oracle 70–90% → partial recovery; per-axis story as contribution
- BIO oracle 40–70% → moderate improvement; combine with CLS for limits-of-architecture paper
- BIO oracle ≤ 40% → cross-distribution gap is fundamental; close architectural axis cleanly
- BIO oracle ≈ CLS oracle (~21%) → fully negative architectural result

---

## New Files in This Branch (planned)

```
src/
  pipeline/
    param_extractor_bio.py             # B1 — BIO tagger + extractor
    span_normalizer.py                 # B2 — Deterministic span -> canonical normalizer
    training/
      data_prep_bio.py                 # A2 — BIO label generation from long-text alignment
      train_bio_tagger.py              # B3 — Training script
  retrievers/
    structured_pipeline_bio_tagger.py        # C1 — proxy module
    structured_pipeline_oracle_bio_tagger.py # C1 — proxy module

configs/
    structured_pipeline_bio_tagger.yaml
    structured_pipeline_oracle_bio_tagger.yaml

data/processed/
    bio_training_data.parquet          # A2 output
    bio_label_inventory.json           # A2 output

models/
    e5_bio_tagger/                     # B5 — trained tagger checkpoints

docs/lightweight-extraction-ner/
    RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md
    RESEARCH_LOG_LIGHTWEIGHT_NER.md
    CLAUDE_LIGHTWEIGHT_NER.md          # This file

docs/sprints/
    SPRINT_LWN_NN.md                   # One per sprint (NN = sequential)
```

---

## Evaluation Conditions (planned)

| Condition | Stage 1 | Stage 2 | Purpose |
|---|---|---|---|
| `structured_pipeline_bio_tagger` | E5 retrieval | E5 + BIO tagger + normalizer | Main result |
| `structured_pipeline_oracle_bio_tagger` | Ground-truth concept | E5 + BIO tagger + normalizer | Isolate Stage 2 accuracy |

---

## Sprint History

*Newest entries at the top.*

### Sprint LWN-03 — B5 Full Training + C1 Pipeline Integration + C2 Full Evaluation
**Date:** 2026-04-30
**Status:** complete — **the headline number is in**
**What changed:**
- B5: trained on RTX 4090, 5 epochs × 38,007 rows, ~32 min. Final val (long): span_f1 **97.4%**, query_acc **99.2%**. No class-imbalance collapse with unweighted CE on the full corpus.
- C1: dispatch branch in `structured_pipeline.py`; 2 proxy modules; 2 YAML configs; 2 pseudo-index dirs; both conditions registered in `run_full_eval.py` `TIER1_CONDITIONS`.
- C2: full eval on 16,590 short-text queries — **BIO oracle 3.13% / pipeline 3.10% item Acc@1**.
- Per-axis diagnostic on 1,630 stratified queries → `analysis/bio_per_axis_short_text.csv`.
- Normalizer fix: BANDA `<==`/`>==` typo handling (placeholder-based rewrite) + 5 new tests (25/25 passing). Headline-neutral.

**Key result:** the BIO architecture is **strictly worse than the CLS classifier** on the cross-distribution test (3.13% vs 21.2% oracle). Per protocol §8 this lands in the most negative interpretation row. The mechanism is per-axis collapse on axes whose surface form lacks a transferable token-level anchor — **CONDICIONES DE EJECUCIÓN at 5.4% recall** is the binding bottleneck, dragging the headline below the all-axes-correct threshold even when the other axes work (TRABAJO 90%, BANDA 56%, etc.).

The hypothesis from protocol §3.2 — that token-level supervision would force the model away from anchor-dependence — is rejected. The two negative results (CLS in LW-06, BIO in LWN-03) together establish: **no architectural fix in the long-only-training regime closes the cross-distribution gap on this corpus.**

### Sprint LWN-02 — Phase B (BIO tagger, normalizer, training, sanity)
**Date:** 2026-04-30
**Status:** complete
**What changed:**
- `src/pipeline/span_normalizer.py` — deterministic schema-bounded normalizer (exact / surface override / axis rules / fuzzy ≤0.15) — **23 unit tests pass**
- `src/pipeline/param_extractor_bio.py` — `BIOTagger` + `BIOParamExtractor` (interface match with rules / classifier extractors)
- `src/pipeline/training/train_bio_tagger.py` — training loop with `token_acc / span_f1 / query_acc` metrics + `--class-weight-o` fallback
- B4 sanity verified: model architecture can learn spans (span_f1 0% → 6.4% on 200 × 3 epochs with class weight 0.1); pure unweighted CE collapses to all-O on small samples (anticipated by protocol §4.6)
- Output paths: `models/e5_bio_tagger/{model.pt, model_best.pt, config.json, training_log.json}`

### Sprint LWN-01 — Branch Setup & Phase A (BIO Training Data Preparation)
**Date:** 2026-04-30
**Status:** complete
**What changed:**
- Branch + docs scaffolding (`docs/lightweight-extraction-ner/`, `CLAUDE.md` branch note, `docs/sprints/SPRINT_LWN_01.md`)
- `src/pipeline/training/data_prep_bio.py` — produces `bio_training_data.parquet` (47,508 rows × 7 cols) and `bio_label_inventory.json` (27 BIO labels)
- `src/pipeline/training/validate_bio_alignment.py` — A3 validation tool
- **Alignment success:** 235,995 / 235,995 axis occurrences = **100.0%** across all 13 axes
- **A3 validation:** 200 / 200 rows fully correct = **100.0%** (gate ≥95% passed)
- **Split parity:** 47,508 / 47,508 item_keys match CLS classifier `split` assignment, guaranteeing direct LW-06 comparability
- Three key data-cleaning decisions documented in research log: unified anchored-substring matcher (replaces regex `\b`), per-row occupancy tracking (handles TRABAJO/BANDA same-surface collisions), `SURFACE_OVERRIDES` for `TIPO DE TERRENO=Normal` → `cualquier clase/tipo de terreno`
