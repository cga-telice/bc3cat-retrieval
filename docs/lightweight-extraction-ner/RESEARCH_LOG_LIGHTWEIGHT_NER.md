# Research Log: Token-Level BIO/NER Tagging for Parametric Extraction

**Branch:** `lightweight-extraction-ner`
**Started:** 2026-04-30
**Parent branch:** `research/lightweight-extraction` (CLS multi-head classifier — closed)
**Protocol:** `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md`

---

*Newest entries at the top. Updated after every sprint.*

---

## Sprint LWN-03 — B5 Full Training + C1 Pipeline Integration + C2 Full Evaluation (the headline)

**Date:** 2026-04-30
**Tasks completed:** B5, C1.a–C1.f, C2 (oracle + pipeline), C2 v2 (with normalizer typo fix), per-axis diagnostic on 1,630-query stratified sample

### Headline result

**The BIO tagger collapses to 3.13% item Acc@1 on the cross-distribution short-text test (16,590 queries), worse than the CLS classifier's 21.2%.**

| Method | Pipeline item Acc@1 | Oracle item Acc@1 | val (long) query_acc |
|---|---|---|---|
| **BIO tagger full FT (this sprint)** | **3.10%** | **3.13%** | **99.2%** |
| CLS classifier full FT (LW-06) | 20.9% | 21.2% | 99.6% |
| Frozen CLS encoder (LW-07) | 0.56% | 0.58% | 11.4% |
| Rules baseline (SEPLN) | 90.3% | 91.4% | — |
| Phi-4 classify (SEPLN) | 87.7% | 88.6% | — |
| dense_e5 (no FT, main) | 13.4% | — | — |

The cross-distribution gap **widens** from 99.2% (val, long) → 3.13% (test, short) — a 96-percentage-point drop. Oracle vs pipeline delta is 0.03 pp; Stage 1 is not the bottleneck.

### Mechanism (per-axis diagnostic)

Per-axis recall on a 1,630-query stratified short-text sample (`analysis/bio_per_axis_short_text.csv`):

| Axis | Recall | What it tells us |
|---|---|---|
| TRABAJO | **90.0%** | Token-level signal transfers cleanly when the surface form ("Diurno", "Nocturno") is preserved across formats |
| TIPO DE TERRENO | 58.5% | Surface override (LWN-01's `cualquier clase de terreno → Normal`) recovers ~58%; the rest fails because the tagger split compound spans |
| BANDA DE MANTENIMIENTO | 55.8% | Operator/quote canonicalization handles typo variants; remainder fails on multi-token span continuity |
| Nº TUBOS | 39.0% | Model learned to anchor on " tubos" / " mm" in long text; short text uses " t," which the model didn't link to Nº TUBOS — instead it (correctly per the supervision) emits a TUBO span that gets filtered by the per-(parent, axis) gate |
| **CONDICIONES DE EJECUCIÓN** | **5.4%** | **The binding bottleneck.** Long text always carries the explicit label prefix `condiciones de ejecución:` before the value; short text uses `(.../volumen relevante)` with no label anchor. The BIO tagger learned to fire B-CONDICIONES on `volumen` ONLY when preceded by the label, so short text gets no span. |
| MATERIAL, PAVIMENTO, TERRENO | 0% | All in tiny groups (OEB010$ / OEB160$); surface forms aren't recovered |
| TIPO DE ACCIÓN, TUBO, DIÁMETRO, DIÁMETROS | 100% | Small but well-anchored axes (single concept group; clean surface forms) |

Queries with **all** axes correct: 38 / 1,630 = 2.3% (matches the 3.13% headline within sampling noise).

### §8 interpretation

The BIO tagger lands in the **most negative row** of the protocol's decision matrix:

- `BIO oracle ≤ 40%` → "fundamental cross-distribution gap; redirect to data-side solutions"
- `BIO oracle ≈ CLS oracle (~21%)` → "fully negative architectural result"
- And — *not anticipated by the protocol* — **strictly below CLS at 21.2%**

**The hypothesis from protocol §3.2 is rejected.** Token-level evidence does NOT transfer better than CLS aggregation across the long↔short pair in BC3CAT. The opposite happens: per-token loss creates stronger per-token sensitivity to local context, which in this corpus is the very label-prefix anchor that doesn't transfer. The CLS architecture's sequence-level aggregation, despite being the alleged source of LW-06's failure, gave it more redundancy at query level — letting it land at 21% where BIO lands at 3%.

The CLS and BIO results together establish a stronger negative claim than either alone: **for this corpus, no purely architectural change in the long-only-training regime closes the cross-distribution gap.** Future work must address representation alignment or training-distribution mixing — the data side, not the architecture side.

### What got built (and committed)

| Component | Path | Notes |
|---|---|---|
| BIO tagger checkpoint | `models/e5_bio_tagger/{model.pt, model_best.pt, config.json, training_log.json}` | 1.1 GB; .gitignored per repo convention. `config.json` + `training_log.json` are committed. |
| Pipeline dispatch | `src/retrievers/structured_pipeline.py` `load()` | Added `bio_tagger` branch; one new `elif` block. |
| Proxy modules | `src/retrievers/structured_pipeline_bio_tagger.py`, `..._oracle_bio_tagger.py` | Both one-line re-exports of `load`. |
| YAML configs | `configs/structured_pipeline_bio_tagger.yaml`, `..._oracle_bio_tagger.yaml` | Mirror the CLS classifier configs. |
| Pseudo-index dirs | `index/structured_pipeline_bio_tagger/meta.json`, `..._oracle_bio_tagger/meta.json` | `stage2_method=bio_tagger`, oracle flag set. |
| TIER1 registration | `scripts/run_full_eval.py` | Both new conditions added. |
| Eval results | `runs/structured_pipeline_bio_tagger/`, `..._oracle_bio_tagger/` | `metrics_dual.json` + per-query summaries. |
| Per-axis diagnostic | `analysis/bio_per_axis_short_text.csv` | 1,630 stratified queries; the §8 mechanism table is built from this. |
| Normalizer fix | `src/pipeline/span_normalizer.py` `_normalize_banda` | Placeholder-based rewrite: `<==`/`>==` typos collapse to canonical `<=`/`>=`. Five new tests added (25/25 passing). Headline-neutral but locks in correct behavior. |

### Out of scope (deferred to LWN-04)

- C3 — diagnostic ablations: per-axis breakdown vs CLS classifier on the same queries (deeper than this sprint's per-axis recall), span-vs-query error split, confusion matrix vs CLS, `frana horaria` typo set tracer.
- C4 — speed benchmark: CPU + GPU mean and p95 for rules / CLS / BIO / Phi-4.
- D1 — cross-format diagnostic on 500 long↔short pairs.
- D2 — query perturbation evaluation.
- D3 — frozen-encoder BIO ablation (mirroring LW-07).

### Next sprint
**Sprint LWN-04:** Phase C3/C4 + Phase D — diagnostic ablations, speed benchmark, cross-format diagnostic, optional frozen-encoder ablation. Then **Phase E** (paper drafting) follows in LWN-05.

---

## Sprint LWN-02 — Phase B (BIO tagger, normalizer, training, sanity)

**Date:** 2026-04-30
**Tasks completed:** B1 (`BIOTagger` + `BIOParamExtractor`), B2 (`SpanNormalizer` + 23 unit tests), B3 (`train_bio_tagger.py`), B4 (100-sample CPU sanity + 200×3-epoch class-weight diagnostic)

### What changed
- `src/pipeline/span_normalizer.py` — schema-bounded deterministic normalizer (exact → surface override → axis-specific rules → fuzzy match Lev≤0.15 → None).
- `tests/__init__.py` + `tests/test_span_normalizer.py` — 23 tests, all passing in 0.03s. Coverage: each canonical value class with ≥5 variants, BANDA operator/quote canonicalization, surface override gating, negative cases.
- `src/pipeline/param_extractor_bio.py` — `BIOTagger` (E5 + single shared Linear(768,27)) + `BIOParamExtractor` matching the `extract(parent_key, query)` contract.
  - Includes `decode_bio_spans` (offset-aware span extraction with stray-I-X-as-B-X recovery) and `merge_adjacent_same_axis` (catches mid-span B-X re-labeling).
- `src/pipeline/training/train_bio_tagger.py` — mirrors `train_classifier.py` structure (AdamW, linear warmup, mixed precision); BIO-specific:
  - Per-token CE with `ignore_index=-100` for special/pad tokens
  - Per-epoch metrics: `token_acc`, macro `span_f1`, end-to-end `query_acc` via `BIOTagger + SpanNormalizer`
  - Best checkpoint on `span_f1`; latest checkpoint always saved (`model.pt`) so downstream code can load even mid-run
  - `--class-weight-o` flag for the protocol §4.6 collapse fallback

### B2 — Span normalizer test results
```
Ran 23 tests in 0.030s
OK
```

### B4 — Sanity test results

| Run | Loss | token_acc | span_f1 | query_acc | Time |
|---|---|---|---|---|---|
| 100 × 1 epoch, unweighted CE | 1.97 | 89.4% | 0.0% | 0.0% | 49s |
| 200 × 5 epochs, unweighted CE | 1.79→0.40 | 88.6% (flat) | 0.0% (flat) | 0.0% | ~7 min |
| 200 × 3 epochs, **class-weight-o=0.1** | 2.58→1.41 | 88.6%→92.0% | 0.0%→6.4% | 0.0% | ~4 min |

**Key finding:** with unweighted CE, the model collapses to all-O on small samples — exactly the failure mode anticipated by protocol §4.6. Loss falls 4.5× (model is "learning") but only refines confidence in the trivial all-O solution. The recommended fallback (`--class-weight-o`) breaks the model out of this minimum and produces non-zero span F1 on val. The architecture is sound.

For the full B5 run (38,007 train rows × 5 epochs on RTX 4090), the much larger training set should dilute the class imbalance enough that unweighted CE works directly. Class-weighted CE remains as a fallback.

### Files added
- `src/pipeline/span_normalizer.py`
- `src/pipeline/param_extractor_bio.py`
- `src/pipeline/training/train_bio_tagger.py`
- `tests/__init__.py`, `tests/test_span_normalizer.py`

### Out of scope (deferred to LWN-03)
- Full GPU training run (B5)
- Pipeline integration: `structured_pipeline_bio_tagger.py`, configs, pseudo-index dirs (Phase C1)
- Full evaluation on 16,590 short-text queries (Phase C2)
- Per-axis breakdown vs CLS classifier on the same queries (Phase C3)

### Next sprint
**Sprint LWN-03:** B5 full training + Phase C (pipeline integration + 16,590-query eval). The full eval against rules / Phi-4 / CLS classifier / dense_e5 baselines is the central comparison the paper hinges on.

---

## Sprint LWN-01 — Branch Setup & Phase A (BIO Training Data Preparation)

**Date:** 2026-04-30
**Tasks completed:** A1 (branch + docs), A2 (BIO label generator), A3 (manual validation), A4 (split + parity check)

### What changed
- Created branch `lightweight-extraction-ner` from `research/lightweight-extraction` at `d38b0b1`.
- Created `docs/lightweight-extraction-ner/` with the protocol, an empty research log, and `CLAUDE_LIGHTWEIGHT_NER.md` (branch context for Claude Code).
- Added third **Branch note** line to top-level `CLAUDE.md`.
- Created `docs/sprints/SPRINT_LWN_01.md` documenting this sprint with full A2/A3/A4 reports.
- Implemented `src/pipeline/training/data_prep_bio.py` — produces `bio_training_data.parquet` and `bio_label_inventory.json`.
- Implemented `src/pipeline/training/validate_bio_alignment.py` — A3 validation tool (programmatic span reconstruction + canonical-value comparison on a 200-row stratified sample).
- Produced output artifacts in `data/processed/`: `bio_training_data.parquet`, `bio_label_inventory.json`, `bio_training_data_samples.txt`, `bio_validation_report.md`, `bio_validation_summary.json`.

### Key technical decisions

| Decision | Choice | Rationale |
|---|---|---|
| Source column | `parameters_norm` (richer; has `value_norm` pre-computed) | Matches protocol §4.5 reference; cleaner than the raw `parameters` field used by the CLS classifier code |
| Anchoring strategy | Unified `_find_anchored_unoccupied` matcher (non-alphanumeric boundaries on both sides) | Replaces `\b…\b` regex which fails on values containing `''` (DIÁMETROS), `<`, `>`, `=`, `/`. One algorithm handles numeric and text axes. |
| Same-surface collisions | Per-row occupancy tracking | When TRABAJO and BANDA both equal `no aplica` (OEB250$, 18 rows), each axis aligns to its own occurrence rather than colliding. |
| `Normal` terrain (5,760 rows) | `SURFACE_OVERRIDES` table mapping `(TIPO DE TERRENO, normal)` → `[cualquier clase de terreno, cualquier tipo de terreno]` | The canonical value `Normal` has no literal surface form in long text; both observed phrases are catalog-stable so the override is auditable. |
| BIO label scheme | 27 labels: `O` + 13 × `B-{axis}` + 13 × `I-{axis}` | Single shared head (protocol §4.2): consolidates training signal for axes recurring across multiple groups. |
| Split | `random_state=42`, concept-group stratified 80/10/10 | Identical to `data_prep.py`; verified 47,508/47,508 item_keys match split assignments in `classifier_training_data.parquet`, guaranteeing direct LW-06 comparability. |
| Tokenizer | `intfloat/multilingual-e5-base` with `return_offsets_mapping=True`, `max_length=512` | Same encoder as Stage 1 + CLS classifier; offsets enable char→subword propagation of BIO labels. |

### Alignment results (full corpus, 47,508 leaf rows)

| Bucket | Count |
|---|---|
| `high` (direct anchored match) | 230,235 |
| `surface` (override applied) | 5,760 |
| `failed` | 0 |
| `failed_overlap` / `failed_truncated` | 0 |
| **Total axis occurrences** | **235,995 (100.0% aligned)** |

Per-axis success rate: every one of the 13 axes at 100.0%. Of note:
- `BANDA DE MANTENIMIENTO`, `TRABAJO`, `Nº TUBOS`: 47k+ occurrences each, all aligned via direct match.
- `DIÁMETROS` (2,520 rows in OEB170$, inches notation): aligned via the new boundary-aware anchored matcher.
- `TIPO DE TERRENO=Normal` (5,760 rows): aligned via surface override.
- `DIÁMETRO`, `MATERIAL`, `TUBO`, `PROFUNDIDAD`, `PAVIMENTO`, `TERRENO`, `TIPO DE ACCIÓN`: low-count axes (15–1,080 rows), all 100%.

### Manual validation (A3, 200 rows)

| Metric | Value |
|---|---|
| Sampled rows (stratified across 13 axes, seed=42) | 200 unique |
| Fully correct rows | **200 (100.0%)** |
| Gate (protocol §10) | ≥95% — **passed** |

Method: programmatic span-text reconstruction (using token offsets) compared against the canonical `value_norm` (or surface override). Per-row markdown details in `data/processed/bio_validation_report.md`.

### Known limitations carried forward
- The corpus's `TIPO DE TERRENO=Normal` cases are aligned to a surface phrase that does not contain the canonical value `Normal`. The downstream span normalizer (Sprint LWN-02 / B2) will need an explicit rule mapping `cualquier clase/tipo de terreno` → `Normal`. Documented in protocol §4.4 risk: the deterministic normalizer must accept these surface variants.
- All training data is catalog-generated (long text). The cross-distribution test against short-text queries is the deliberate property under test (protocol §1) and will be the central comparison in Sprint LWN-03.

### Next sprint
**Sprint LWN-02:** Phase B — model class (`param_extractor_bio.py`), span normalizer (`span_normalizer.py`), training script (`train_bio_tagger.py`), CPU sanity test (B4). Stops before the full GPU training run (B5) so loss curves, val span-F1, and end-to-end query accuracy can be reviewed first.

---
