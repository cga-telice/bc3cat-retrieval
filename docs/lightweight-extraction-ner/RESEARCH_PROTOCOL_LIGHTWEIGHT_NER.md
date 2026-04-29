# Research Protocol: Token-Level Tagging (BIO/NER) for Parametric Extraction in Structure-Aware Retrieval

**Branch:** `lightweight-extraction-ner`
**Repo:** `bc3cat-retrieval`
**Author:** César · April 2026
**Target:** Third investigation (follow-up to SEPLN 2026 paper and `lightweight-extraction` branch)
**Parent branch:** `research/lightweight-extraction` (CLS multi-head classifier — closed)

---

## 1. Purpose and Scope

This protocol is the **implementation roadmap** for a third Stage 2 investigation, following the SEPLN 2026 paper (rules, LLMs) and the `lightweight-extraction` branch (multi-head CLS classifier). The CLS classifier branch produced a clean negative result with a precise mechanistic explanation: trained on long-text (documents), it reached 99.6% val accuracy on its own distribution but collapsed to 20.9% on short-text queries (cross-distribution). The per-axis breakdown showed that numerical axes transferred perfectly (100%) while text-based axes whose surface-form differs between long and short formats collapsed (TRABAJO 52.5%, BANDA 62.9%, TIPO DE TERRENO 69.1%). The mechanism: the CLS classifier learned to condition on explicit axis labels (`trabajo:`, `banda de mantenimiento:`) that are present in the long text and absent in the short text, rather than on the value tokens themselves, which are present in both.

**This branch tests an architectural alternative that targets that mechanism directly: token-level BIO tagging (NER) followed by deterministic span normalization.** The hypothesis is that a tagger conditioned on token-level evidence (where the value tokens *do* transfer across distributions) should not exhibit the same collapse, while still producing constrained, normalized outputs with no LLM-style hallucination risk.

**Research question:** Can a fine-tuned encoder with a single shared BIO tagging head (~27 token labels) followed by deterministic span normalization match or exceed rule-based extraction accuracy on the BC3CAT benchmark, **while generalizing across text distributions** (long-text training → short-text evaluation) where the CLS classifier failed?

**Key methodological commitment:** *Same training/evaluation regime as `lightweight-extraction`*. We train on `OEB_long_norm.parquet` (the long catalog text) and evaluate on the 16,590 short-text queries used throughout the project. This is identical to the LW-06 setup and is intentional: the cross-distribution gap is treated as a property to be tested architecturally, not as a confound to be removed by changing the data source. Mixed training and short-text training are explicitly *not* part of this protocol — they belong to a different experimental axis.

**Branch structure:**

The `lightweight-extraction-ner` branch is created from `research/lightweight-extraction`. Documents from prior phases remain read-only references. New documents live in `docs/lightweight-extraction-ner/`.

**Companion documents:**

| Document | Role | When updated |
|---|---|---|
| `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md` | This file; roadmap and backlog | When tasks are added/reprioritized |
| `CLAUDE.md` | Persistent context for Claude Code | After every sprint |
| `docs/lightweight-extraction-ner/RESEARCH_LOG_LIGHTWEIGHT_NER.md` | Running record of decisions, results, issues | After every sprint |
| `sprints/SPRINT_LWN_NN.md` | Individual sprint prompt for Claude Code | Written just before each sprint |

**Prior research (read-only reference):**

| Document | Location |
|---|---|
| SEPLN paper | `docs/structured-retrieval/sepln_paper.tex` |
| SEPLN protocol | `docs/structured-retrieval/RESEARCH_PROTOCOL.md` |
| SEPLN log | `docs/structured-retrieval/RESEARCH_LOG.md` |
| LW protocol (CLS classifier) | `docs/lightweight-extraction/RESEARCH_PROTOCOL_LIGHTWEIGHT.md` |
| LW log (CLS classifier) | `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT.md` |
| LW-06 cross-distribution analysis | `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT-06_Analysis.md` |

**Relationship to prior work:**

| What | Reuse | Build new |
|---|---|---|
| Stage 1 (E5 concept retrieval) | ✅ As-is | — |
| Stage 2 (parameter extraction) | Baselines only (rules, LLMs, CLS classifier) | **BIO tagger + deterministic normalizer** |
| Stage 3 (catalog lookup) | ✅ As-is | — |
| Evaluation infra | ✅ `run_full_eval.py`, query set, metrics | New conditions only |
| Schema / data | ✅ `OEB_concept_schema.json`, parquet files | BIO label generation |
| Extractor interface | ✅ `extract(parent_key, query) → {axis: value\|None}` | New implementation |

---

## 2. Sprint Workflow

Same as prior protocols: sprints are not pre-planned in detail. César drafts `sprints/SPRINT_LWN_NN.md` just-in-time, Claude Code executes, César updates logs and context.

---

## 3. Motivation and Prior Evidence

### 3.1 What the CLS Classifier Branch Established

The `lightweight-extraction` branch produced four outcomes that frame this work:

1. **The architecture is learnable on its training distribution.** Full fine-tuning on long text reaches 99.6% val_query_acc. The per-axis classification problem is well-specified and the CLS head + 97 softmax decoders solve it within the long-text format.

2. **It does not transfer across formats.** On 16,590 short-text queries (cross-distribution), accuracy collapses to 20.9% (pipeline) / 21.2% (oracle). The Stage 1 E5 retrieval is not the bottleneck (oracle gap < 0.4 pp): the bottleneck is entirely in Stage 2.

3. **The collapse has a clean mechanistic signature.** Per-axis accuracy on a 2,000-query sample shows perfect transfer for numerical axes (Nº TUBOS, PROFUNDIDAD, DIÁMETROS: 100%) and degraded transfer for text-based axes whose long-text encoding includes an explicit label prefix (`trabajo: nocturno`) that is absent in short text (`(nocturno/...)`). Top confusions are systematic substitutions within an axis (e.g. `Diurno` predicted as `Diurno Excepcional` 295 times) rather than random noise.

4. **The frozen-encoder ablation rules out overfitting as the cause.** With the encoder frozen and only the 97 heads learnable, val accuracy collapses to 11.4% on long text and 0.56% on short. The CLS embedding of pretrained E5 does not encode enough parameter-relevant signal for linear projection. Representation adaptation is *necessary*, not *counterproductive* — but the adaptation that does work also entangles surface-form patterns with semantic content.

The simplest reading: the CLS classifier learned to condition on **document-level cues** (axis label literals, position within the text) rather than **token-level evidence** (the value tokens themselves). This protocol tests whether changing the architecture to one that operates at the token level — and is therefore forced to use token-level evidence — eliminates the cross-distribution collapse.

### 3.2 Why a BIO Tagger Targets the Specific Failure Mode

In the long-text training distribution, the value `Rocoso` appears as the substring `rocoso` in contexts like `... en terreno rocoso, incluso ...`. In short-text queries, it appears as `rocoso` in contexts like `..., rocoso. (nocturno/...)`. The token `rocoso` is identical in both. What differs is everything around it.

A token-level tagger has, by construction, only two ways to label a token:
- via its own representation (which depends primarily on the token itself in WordPiece vocabularies),
- via the contextualized representations from surrounding tokens.

When trained on long text, the model can use either signal. At evaluation on short text, the contextual signal degrades (the "trabajo:" anchor is gone) but the token-level signal is preserved. If the model learns a robust mixture that does not rely *exclusively* on the contextual anchor — and BIO loss applied to every token in the sequence creates pressure for this — the cross-distribution penalty should be substantially smaller than for the CLS architecture, where the entire decision is conditioned on a single 768-dim vector aggregated over the whole sequence.

This is a falsifiable prediction. If BIO transfers similarly poorly to CLS (~21% short-text Acc@1), then the cross-distribution gap is fundamental to the long↔short pair in BC3CAT and not an architectural artifact, and that itself is a publishable result that closes the question.

### 3.3 Comparison to dense_e5 Baseline (Main Branch)

A relevant question raised during analysis: is a fine-tuned encoder on Stage 2 just a re-skin of dense retrieval with embeddings? The numbers from main branch's `dense_e5` baseline (E5 without fine-tuning, direct retrieval, 16,590 queries) are:

| Method | item Acc@1 | parent Acc@1 |
|---|---|---|
| dense_e5 (no FT, direct retrieval) | 13.4% | 98.2% |
| E5 CLS classifier (full FT, structured pipeline) | 21.2% (oracle) | 100% (oracle) |

The +7.8 pp item Acc@1 from full FT is real but modest. A NER architecture changes the comparison qualitatively: a BIO tagger is *not* doing similarity-based retrieval, it is doing token-level structured prediction with a deterministic post-processor. If the NER variant substantially outperforms both dense_e5 (13.4%) and CLS classifier (21.2%) on cross-distribution short text — say, ≥70% — it establishes that the architectural choice matters beyond "fine-tuning the encoder," which would not be true if the result remains in the 21% region.

---

## 4. Proposed Approach: Shared BIO Tagger + Deterministic Span Normalizer

### 4.1 Architecture

```
Token sequence (after tokenizer, with WordPiece subwords)
  │
  ▼
[E5 encoder] (intfloat/multilingual-e5-base, 278M params, full FT)
  │
  ▼
Per-token hidden states (T tokens × 768)
  │
  ▼
[BIO classification head]   single shared Linear(768, 2K+1)
  │   where K = 13 unique axis labels in the schema
  │   labels: O, B-NUM_TUBOS, I-NUM_TUBOS, B-TIPO_DE_TERRENO, I-TIPO_DE_TERRENO,
  │           B-TRABAJO, I-TRABAJO, B-BANDA_DE_MANTENIMIENTO, I-..., ...
  │   ⇒ 27 BIO labels total, single-head softmax per token
  │
  ▼
Per-token BIO predictions
  │
  ▼
[Span extraction] — adjacent B-X / I-X tokens grouped into spans
  │  output: list of (axis_label, surface_text) pairs
  │
  ▼
[Deterministic span → canonical-value normalizer]
  │  for each (axis_label, surface_text):
  │    1. Look up the set of valid canonical values for (concept_group, axis_label)
  │       from OEB_concept_schema.json. This set has 2-12 elements.
  │    2. Apply minimal text normalization to the span (lowercase, strip,
  │       fix common operator/quote variants for BANDA-like axes).
  │    3. Try exact match against canonical values.
  │    4. If no exact match, try fuzzy match (normalized Levenshtein
  │       distance ≤ 0.15) against canonical values.
  │    5. If still no match → null for this axis.
  │  output: {axis_label: canonical_value | None}
  │
  ▼
[Stage 3 deterministic catalog lookup, unchanged]
  │
  ▼
Result (single item_key, or ranked sub-group)
```

### 4.2 Why a Single Shared BIO Head Instead of Per-Group Heads

The CLS classifier branch used 97 per-(concept_group, axis) softmax heads. This worked on its own distribution but was likely a contributor to the cross-distribution failure: each head saw only the queries for its concept group, fragmenting the training signal for axes that span multiple groups (e.g. TRABAJO is used in 21 of 25 groups). With ~38k training rows across 97 heads, each head sees on average ~390 examples — far less than ideal for a 768→9 softmax.

The BIO head is **shared across all concept groups**. The label `B-TRABAJO` is the same label whether the query belongs to `OEB010$` or `OEB290$`. This means the head is trained on all rows that mention TRABAJO (~85% of the corpus, ~40k rows) instead of being splintered by concept group. The price for this consolidation is that the label space becomes coarser (axis-level rather than axis+value-level), but the value resolution is recovered downstream by the deterministic normalizer working against the per-(group, axis) value sets from the schema.

This is a strict regularization win: more data per head, smaller output space per decision, identical final output cardinality after normalization.

### 4.3 Schema-Derived Label Inventory

From `OEB_concept_schema.json`:

| Property | Value |
|---|---|
| Concept groups | 25 |
| Unique axis labels (across all groups) | 13 |
| Total (concept_group, axis) pairs | 97 |
| Unique canonical values per axis | 2 to 12 |
| BIO labels (this protocol) | 2 × 13 + 1 = **27** |
| Heads in CLS classifier (`lightweight-extraction`) | 97 |

The 13 axis labels are: TRABAJO (9 values, 21 groups), CONDICIONES DE EJECUCIÓN (3, 24), BANDA DE MANTENIMIENTO (6, 21), Nº TUBOS (12, 11), TIPO DE TERRENO (11, 9), TERRENO (3, 2), PAVIMENTO (2, 2), PROFUNDIDAD (3, 2), DIÁMETRO (5, 1), TUBO (2, 1), DIÁMETROS (7, 1), MATERIAL (2, 1), TIPO DE ACCIÓN (2, 1).

### 4.4 The Normalizer is Deterministic and Bounded

A reasonable concern raised in the parent protocol about NER-style approaches was: "the span-to-value normalization step reintroduces the same normalization errors that plague LLMs." This is only true if the normalization is open-ended generation. In the design above, normalization is a **lookup against a finite set of canonical values** specific to each (concept_group, axis) pair. The cardinality of that set is at most 12 in this corpus and typically 2-4. A trivial lowercase + strip + edit-distance lookup can be exhaustive.

This means: the model cannot hallucinate "Diurno excepcional turbo" or invent a new BANDA expression. Whatever span the BIO head produces, the normalizer either maps it to one of the ≤12 catalog values for that (group, axis) or returns null. The behavior is auditable and easy to extend with axis-specific rules where useful (for example, the BANDA axis would benefit from a small regex set that normalizes operator notation: `i < "3" horas` and `i < 3 horas` and `i<3 horas` all map to `i < 3 horas`).

### 4.5 Training Data Generation

Each training row in `OEB_long_norm.parquet` provides:
- `text_norm` — the (long) normalized text to be tagged,
- `parameters_norm` — the canonical (axis, value) labels for this item,
- `parent_key` — the concept group.

Generating BIO labels requires aligning each canonical value to a span in the text. The strategy is:

1. **Direct substring search.** For values like `Rocoso` → search for `rocoso` in `text_norm`. For numbers like `16` (Nº TUBOS) → search for `\b16\b` near a tubos-related context. Most values resolve at this stage.
2. **Axis-specific rules** for compound values:
   - BANDA: `i < 3 horas` is generated by the catalog as a postfix label that may or may not appear verbatim in the text body. Search for the postfix block first; if absent, search for the natural-language equivalent in the text body.
   - TRABAJO compound values (`Nocturno Excepcional`): align as adjacent multi-word spans, requiring B-TRABAJO + I-TRABAJO.
   - Numeric values: anchor by surrounding tokens (`tubos`, `mm`, `m`).
3. **Validation.** A fraction of generated alignments must be hand-verified (target: 200 random rows, all axes covered, ≥95% correct) before training. This is the most error-prone step in the pipeline; budget for iteration.
4. **Failure handling.** Rows where one or more values cannot be aligned are tagged with a flag and either dropped from training or kept with the unalignable axis labeled as all-O. Both options require empirical evaluation in Phase A.

The output is a parquet file with columns `(item_key, parent_key, tokens, bio_labels, alignment_confidence)`. The alignment is offline and deterministic.

### 4.6 Loss and Decoding

- **Loss:** standard token-level cross-entropy on BIO labels. No CRF in the first iteration — most BC3CAT spans are 1-3 tokens, and CRF complexity is not justified before evidence that simple greedy decoding fails.
- **Decoding at inference:** greedy argmax per token, then BIO-consistent post-processing (a stray `I-X` without preceding `B-X` is treated as `B-X`; multiple adjacent `B-X` for the same axis are merged into one span — i.e. the span continues until a different label or O appears).
- **Class imbalance:** O is the majority class. Use a weighted loss only if epoch 1 evaluation shows the model collapsing to all-O. Default: unweighted CE.

---

## 5. Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Base encoder | **`intfloat/multilingual-e5-base`** | Same as Stage 1 and prior CLS classifier — single-model pipeline; direct comparability with the LW-06 negative result |
| Architecture | **Shared BIO tagger** | Single Linear(768, 27) head, applied per token. Shares signal across concept groups for axes that recur. |
| Training data source | **`OEB_long_norm.parquet`** (long catalog text) | Same as LW-06. This is a deliberate methodological commitment: cross-distribution generalization is the property under test. |
| Label generation | **Offline alignment** of `parameters_norm` to substrings in `text_norm`, with validation | Not a runtime task; deterministic and auditable |
| Train/val/test split | **Concept-group-stratified 80/10/10** | Same as LW-06 for direct comparability |
| Encoder freezing | **Full fine-tuning** (frozen variant in backlog) | LW-07 already established that frozen E5 cannot reach baseline performance on this task |
| Span normalization | **Deterministic lookup against schema with edit-distance fallback** | Eliminates LLM-style hallucination; closed set per (group, axis) ≤ 12 |
| Decoding | **Greedy argmax + BIO post-processing** | Simplest baseline; CRF in backlog |
| Evaluation | **Same 16,590 short-text queries, same metrics, same `run_full_eval.py`** | Direct comparability with all prior runs (rules, LLMs, CLS classifier) |

---

## 6. Task Backlog

### Phase A — Data Preparation

- **A1. Branch setup.** Create `lightweight-extraction-ner` from `research/lightweight-extraction`. Set up `docs/lightweight-extraction-ner/` with this protocol, a fresh log, and a CLAUDE_LIGHTWEIGHT_NER.md branch context. Update `CLAUDE.md` with the new branch pointer.

- **A2. BIO label generator.** Implement `src/pipeline/training/data_prep_bio.py`:
  - Load `OEB_long_norm.parquet` and `OEB_concept_schema.json`.
  - For each row, tokenize `text_norm` with the E5 tokenizer (subword-aware) and align each canonical value from `parameters_norm` to a token span.
  - Apply substring + axis-specific rules from §4.5; record an `alignment_confidence` field (`high` for unambiguous direct match, `medium` for fuzzy/contextual, `low` or `failed` for residual).
  - Output: `data/processed/bio_training_data.parquet` with columns `(item_key, parent_key, tokens, token_ids, bio_labels, alignment_confidence)`.
  - Output: `data/processed/bio_label_inventory.json` listing the 27 BIO labels and their integer indices.
  - Sanity report: per-axis alignment success rate, count of rows fully aligned, sample of 20 rendered (token, BIO_label) sequences for manual inspection.

- **A3. Manual validation.** Hand-check 200 random rows from `bio_training_data.parquet` (stratified across axes). Target: ≥95% rows fully correct. Document failure modes in the sprint log.

- **A4. Train/val/test split.** Concept-group-stratified 80/10/10, identical methodology to the CLS classifier branch (so split idiosyncrasies do not confound comparison). OEB160$ (3 items) goes entirely to train.

### Phase B — Tagger Implementation and Training

- **B1. Model implementation.** `src/pipeline/param_extractor_bio.py`:
  - `BIOTagger` class wrapping `intfloat/multilingual-e5-base` with a single `Linear(768, 27)` head.
  - `BIOParamExtractor` implementing the same interface as `RuleBasedParamExtractor` and `ClassifierParamExtractor`: `extract(parent_key, query) → {axis: value | None}` and `extract_batch`.
  - Internal flow: tokenize → encode → BIO predict → group spans → normalize spans against schema for `parent_key` → return dict.
  - Checkpoint save/load.

- **B2. Span normalizer module.** `src/pipeline/span_normalizer.py`:
  - `normalize(axis_label, surface_text, parent_key, schema) → canonical_value | None`
  - Pluggable axis-specific normalizers (BANDA operator/quote canonicalization, numeric anchor parsing, etc.).
  - Unit tests covering each axis with at least 5 input variants per canonical value.

- **B3. Training script.** `src/pipeline/training/train_bio_tagger.py`:
  - AdamW + linear warmup, lr 2e-5, batch 16, epochs 5-10, mixed precision.
  - Track at each epoch: token-level BIO accuracy, span-level F1 (per axis and overall), end-to-end query-level extraction accuracy on val (using the deterministic normalizer downstream of the tagger).
  - Early stopping on val span-level F1.
  - Save best checkpoint to `models/e5_bio_tagger/`.

- **B4. Sanity test.** 100-sample, 1-epoch run on CPU. Verify training loop completes, `extract()` returns the correct format, and at least the high-confidence axes (Nº TUBOS, CONDICIONES) are predicted.

- **B5. Full training run.** RTX 4090 / Docker. Expected ~30-60 min based on LW-03 timings. Save metrics per epoch.

### Phase C — Pipeline Integration and Full Evaluation

- **C1. Pipeline integration.** Add `bio_tagger` branch to `load()` in `src/retrievers/structured_pipeline.py`. Create proxy modules `structured_pipeline_bio_tagger.py` and `structured_pipeline_oracle_bio_tagger.py`. Create YAML configs and pseudo-index dirs. Conditions:
  - `structured_pipeline_bio_tagger` (Stage 1 E5 retrieval + BIO tagger Stage 2)
  - `structured_pipeline_oracle_bio_tagger` (oracle concept + BIO tagger Stage 2)

- **C2. Full evaluation run.** Both conditions on 16,590 queries. Produce `metrics_dual.json`. Compare against:
  - Rules pipeline / oracle (90.3% / 91.4%)
  - Phi-4 classify pipeline / oracle (87.7% / 88.6%)
  - CLS classifier full FT pipeline / oracle (20.9% / 21.2%) — *the key comparison*
  - dense_e5 (13.4%) — *establishes the architectural delta beyond fine-tuning*
  - BM25 param-aware (97.4%) — *upper-bound reference*

- **C3. Diagnostic ablations.**
  - **Per-axis breakdown.** Same 2,000-query analysis used in LW-06 for the CLS classifier. Report per-axis accuracy on short text. The expected pattern under the hypothesis: numerical axes still 100%, text-based axes (TRABAJO, BANDA, TIPO DE TERRENO) substantially higher than the CLS classifier's 52-69%.
  - **Span-level vs query-level errors.** For each missed query, report whether the failure was (a) tagger missed the span entirely, (b) tagger produced a span but normalizer could not match it, (c) extracted parameters were correct but Stage 3 lookup failed.
  - **Confusion matrix vs CLS classifier on the same queries.** Identify queries where each method succeeds and the other fails. The `frana horaria` typo set is a known tracer.

- **C4. Speed benchmark.** Inference time per query on CPU and GPU for: rules, CLS classifier, BIO tagger, Phi-4 classify. Report mean and p95.

### Phase D — Robustness and Comparative Analysis

- **D1. Cross-format diagnostic.** Construct a held-out set of 500 (long_text, short_text) pairs for the same item_keys. Run the BIO tagger on both. The per-axis transfer rate (long-acc → short-acc) is the cleanest measurement of cross-distribution robustness for this architecture.

- **D2. Query perturbation evaluation.** Reuse Phase D from the CLS protocol if implemented; otherwise, generate a small set (~200) of perturbed queries (synonym substitution, abbreviation, typo injection) and measure degradation curves for rules, CLS classifier, and BIO tagger. The hypothesis: BIO tagger degrades less than rules.

- **D3. Frozen-encoder ablation (optional).** Repeat LW-07's frozen-encoder experiment with the BIO architecture. If frozen BIO reaches a substantially higher cross-distribution accuracy than frozen CLS (which got 0.56%), that further isolates the architectural contribution.

### Phase E — Analysis and Paper

- **E1. Error taxonomy.** Same categories as SEPLN: E1-WRONG_CONCEPT, E2-PARTIAL_EXTRACT, E2-WRONG_VALUE, plus new: E3-TAGGER_MISS, E3-NORMALIZER_MISS. Compare error distributions across rules, CLS classifier, BIO tagger.

- **E2. Paper draft.** Likely combined paper with the CLS classifier negative result. Possible narrative: *"Architectural choices in lightweight parameter extraction: when CLS classifiers exploit format-specific cues and what survives at the token level."* Three-way comparison (rules, CLS, BIO) with the cross-distribution diagnostic as the central methodological contribution.

### Backlog (if time permits)

- CRF decoding head on top of BIO logits (transition matrix learned).
- BIO loss with span-level F1 reward (structured perceptron / span-based loss).
- Alternative encoder backbones: BETO (`dccuchile/bert-base-spanish-wwm-cased`), RoBERTa-BNE (`PlanTL-GOB-ES/roberta-base-bne`).
- Adapter / LoRA fine-tuning instead of full FT.
- Hybrid: BIO tagger output as features for a lightweight per-(group, axis) head — combines token-level and aggregated signal.
- Distillation: use rule-based extraction outputs as silver labels to expand training data.

---

## 7. Evaluation Conditions

| Condition | Stage 1 | Stage 2 | Purpose |
|---|---|---|---|
| `structured_pipeline_bio_tagger` | E5 retrieval | E5 + BIO tagger + normalizer | **Main result** |
| `structured_pipeline_oracle_bio_tagger` | Ground-truth concept | E5 + BIO tagger + normalizer | Isolate Stage 2 accuracy |

Existing baselines for comparison (no re-running needed):

| Method | Pipeline item Acc@1 | Oracle item Acc@1 | Source |
|---|---|---|---|
| dense_e5 (no FT, direct retrieval) | 13.4% | — | main |
| CLS classifier full FT | 20.9% | 21.2% | LW-06 |
| Phi-4 classify | 87.7% | 88.6% | SEPLN |
| Rules | 90.3% | 91.4% | SEPLN |
| BM25 param-aware | 97.4% | — | main |

---

## 8. Diagnostic Interpretation

| Observation on short-text 16,590-query eval | Interpretation |
|---|---|
| BIO oracle ≥ 90% (≈ rules) | The architectural choice fully closes the cross-distribution gap. Token-level evidence is sufficient and the long↔short gap is an artifact of CLS-level aggregation. Strongest result for the paper. |
| BIO oracle ∈ [70%, 90%) | Partial recovery. The tagger generalizes much better than CLS but not as well as rules. The per-axis breakdown will show which axes still fail; likely the operator-heavy ones (BANDA). Publishable with the per-axis story as the contribution. |
| BIO oracle ∈ [40%, 70%) | Architectural improvement is real but moderate. CLS at 21% set a low floor; BIO substantially exceeds it but is still far from rules. Suggests neither aggregation level alone solves cross-distribution transfer; cross-format training is needed. Combine with the CLS result for a paper on the limits of single-distribution training in this domain. |
| BIO oracle ≤ 40% | The cross-distribution gap is fundamental to the long↔short pair in BC3CAT; architectural choice within the long-only-training regime cannot close it. This closes the architectural axis of investigation cleanly and redirects effort to data-side solutions (mixed training, augmentation). Still publishable as a negative architectural result paired with the CLS branch. |
| BIO oracle ≈ CLS oracle (≈ 21%) | Fully negative architectural result. The bottleneck is information that is genuinely absent from the short-text format and no purely architectural change recovers it. Highest-confidence negative result; consolidates the conclusion. |

| Observation per-axis on short text | Interpretation |
|---|---|
| Numerical axes 100%, text axes ≥ 80% | Tagger learned token-level signal robustly; the CLS classifier's collapse on text axes was indeed an artifact of the architecture. |
| Numerical axes 100%, text axes ~50-70% (similar to CLS) | Tagger replicated the CLS failure mode despite operating at the token level. The mechanism is more subtle than CLS-level aggregation — possibly the contextual representations themselves entangle format. |
| Tagger spans correct but normalizer fails | The span detector works; the normalizer needs more axis-specific rules. Easy to fix incrementally. |

---

## 9. New File Map

```
src/
  pipeline/
    param_extractor_bio.py             # B1 — BIO tagger + extractor
    span_normalizer.py                 # B2 — Deterministic span → canonical normalizer
    training/
      data_prep_bio.py                 # A2 — BIO label generation from long-text alignment
      train_bio_tagger.py              # B3 — Training script
  retrievers/
    structured_pipeline_bio_tagger.py        # C1 — proxy module
    structured_pipeline_oracle_bio_tagger.py  # C1 — proxy module

configs/
    structured_pipeline_bio_tagger.yaml
    structured_pipeline_oracle_bio_tagger.yaml

data/processed/
    bio_training_data.parquet          # A2 output
    bio_label_inventory.json           # A2 output

models/
    e5_bio_tagger/                     # B5 — trained tagger checkpoints

analysis/
    bio_per_axis.csv                   # C3 output
    bio_vs_cls_query_overlap.csv       # C3 output
    cross_format_diagnostic.csv        # D1 output

docs/lightweight-extraction-ner/
    RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md   # This file
    RESEARCH_LOG_LIGHTWEIGHT_NER.md        # Running log
    CLAUDE_LIGHTWEIGHT_NER.md              # Branch context for Claude Code
```

---

## 10. Risk Register

| Risk | Mitigation |
|---|---|
| BIO label alignment from long text is noisy → training labels are wrong | Phase A3 manual validation of 200 rows; failure threshold ≥ 95% correctness before B5 training |
| Compound values (`Nocturno Excepcional`, `i < 3 horas`) require multi-token spans the tagger struggles to keep contiguous | BIO post-processing rule: adjacent same-axis B-tags merge into one span; if persistent failure, add CRF decoding (backlog) |
| BANDA axis with operator/quote variants resists the deterministic normalizer | Axis-specific normalizer with explicit canonicalization rules for `<`, `<=`, `<==`, with/without quotes; iterate on B2 unit tests |
| Tagger learns the same `trabajo:` anchor as CLS and exhibits the same collapse | Confronted directly by the per-axis diagnostic in C3. If true, frozen-encoder ablation in D3 will further isolate the cause; result is a stronger negative finding rather than a failure of the protocol. |
| Training data is still all catalog-generated (same limitation as LW-06) | Acknowledged. This protocol is not the experiment for "does the tagger help on real-world queries" — that requires Phase D2 perturbation eval and is a secondary contribution. |
| Some axes have very few training examples (DIÁMETROS, MATERIAL, etc. are in a single concept group) | Shared head means these axes still see all the rows that mention them. If still insufficient, fall back to per-(group, axis) heads for low-count axes only. |
| Span normalizer Levenshtein threshold (0.15) is wrong for some axes | Per-axis thresholds; tune on val before final eval. |
| Tokenizer subword splits split a value across tokens (`16` → `1`, `##6`) and BIO becomes misaligned | Use word-level alignment with the tokenizer's offset_mapping; propagate the BIO label to all subword pieces of a word; merge predictions back at the word level. Standard practice. |
| Model checkpoint size (full E5 + small head ≈ 1.1 GB) | Acceptable; same as LW. |

---

## 11. Changelog

| Version | Date | Changes |
|---|---|---|
| v0.1 | April 2026 | Initial protocol — shared BIO tagger + deterministic normalizer, long-text training, short-text evaluation, full task backlog with cross-distribution diagnostic as central contribution |

---

*This document is the stable roadmap for the `lightweight-extraction-ner` branch. Sprint-level detail lives in `sprints/SPRINT_LWN_NN.md` files, written just-in-time. The companion log `RESEARCH_LOG_LIGHTWEIGHT_NER.md` is updated after each sprint.*
