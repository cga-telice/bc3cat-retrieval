# Research Log: Token-Level BIO/NER Tagging for Parametric Extraction

**Branch:** `lightweight-extraction-ner`
**Started:** 2026-04-30
**Parent branch:** `research/lightweight-extraction` (CLS multi-head classifier — closed)
**Protocol:** `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md`

---

*Newest entries at the top. Updated after every sprint.*

---

## Sprint LWN-05 — Phase E (Comparative Error Taxonomy + Paper Draft)

**Date:** 2026-04-30
**Tasks completed:** E1 (comparative error taxonomy across rules / CLS / BIO), E2 (paper draft)

### What changed

- `analysis/comparative_error_taxonomy.csv` + `..._per_axis.csv` — uniform error categorization across the three Stage 2 methods on the same 16,590-query short-text test.
- `docs/lightweight-extraction-ner/PAPER_DRAFT.md` — 10-section markdown draft, ~7 pages, every numerical claim source-pointed to a sprint or analysis CSV.

### E1 — The comparative error structure (the LWN-04/05 punchline)

| Method | ALL_CORRECT | PARTIAL | WRONG_VALUE | ALL_NULL |
|---|---|---|---|---|
| Rules | 93.51% | 6.49% | 0.00% | 0.00% |
| CLS classifier (full FT) | 21.57% | 78.37% | 0.05% | 0.00% |
| BIO tagger (full FT) | 0.51% | 97.44% | 0.00% | 2.04% |

Three distinct failure profiles (per-axis NULL vs WRONG counts on missed queries):

- **Rules** — high accuracy on the patterns it hand-encodes; failures are NULL extractions on out-of-template surface forms (TRABAJO 1,017).
- **CLS** — confident-wrong: softmax forces a commit. TRABAJO 7,777 wrong, BANDA 6,382 wrong, TIPO DE TERRENO 4,718 wrong.
- **BIO** — conservative-null: per-token decision returns no canonical when the span is uninterpretable. CONDICIONES 16,439 NULL, Nº TUBOS 13,837 NULL.

**Stage 3 amplifies the asymmetry.** NULLs are ignored by the catalog lookup (partial-match recovery still works); WRONGs actively exclude the correct item. This is why BIO reaches 3.13% Acc@1 from 0.51% all-axes-correct (catalog lookup tolerates NULLs) while CLS reaches 21.2% from 21.6% all-axes-correct (lookup is unforgiving of WRONGs).

### E2 — Paper draft

10 sections covering: cross-distribution test framing, both architectures, the deterministic schema-bounded normalizer, all five LWN-04 diagnostics, the comparative error taxonomy, and the discussion of why BIO is worse than CLS in every regime tested. Title: *Architectural Choices in Lightweight Parameter Extraction: When CLS Classifiers Exploit Format-Specific Cues and What Survives at the Token Level.*

The discussion (§6) frames the central counter-intuitive finding: **per-token loss creates *stronger* per-token sensitivity to local context.** In a corpus where the local context is the very label-prefix anchor that doesn't transfer across formats, the BIO architecture ends up more anchor-bound than the CLS architecture — opposite of the prior on token-level robustness.

The conclusion (§8) closes the architectural-axis question and points at the data-side directions (mixed training, anchor-removal augmentation) that future work needs to take.

### Files added

- `analysis/comparative_error_taxonomy.csv`
- `analysis/comparative_error_taxonomy_per_axis.csv`
- `docs/lightweight-extraction-ner/PAPER_DRAFT.md`
- `docs/sprints/SPRINT_LWN_05.md`

### Out of scope (deferred)

- D2 — query perturbation evaluation (the paper has enough diagnostic depth without it; would be a follow-up if a venue requests additional robustness data).
- LaTeX submission-ready formatting and BibTeX bibliography (deferred until a venue is chosen).
- Camera-ready figures (markdown tables suffice for the draft; figure generation comes later).

### Next sprint (suggested)

The protocol's Phase E is now complete. Possible next steps:
- **LWN-06: paper finalization** — translate to LaTeX, add figures, line up references, target a venue.
- **LWN-06 alt: data-side experiments** — mixed training (long + labeled-short with proper holdout), anchor-removal augmentation. The natural follow-up implied by §6.5 of the paper.
- **LWN-06 alt: D2 query perturbation** — synthetic perturbed queries to test architectural robustness more broadly.

---

## Sprint LWN-04 — Phase C3/C4 + Phase D (Diagnostic Ablations)

**Date:** 2026-04-30
**Tasks completed:** C3.a (confusion vs CLS), C3.b (error taxonomy), C3.c (typo tracer), per-axis recall on full 16,590 eval (replaces stratified-sample analysis from LWN-03), C4 (speed benchmark), D1 (cross-format diagnostic), D3 (frozen-encoder BIO ablation)

### Five diagnostics that explain the LWN-03 negative result

#### C3.a — CLS ⊕ BIO contingency (16,590 oracle queries)

|             | CLS correct | CLS wrong | Total |
|-------------|-------------|-----------|-------|
| BIO correct |    199      |    321    |   520 |
| BIO wrong   |   3,321     |  12,749   | 16,070 |
| Total       |   3,520     |  13,070   | 16,590 |

- BIO Acc@1 = 3.13%, CLS Acc@1 = 21.22%
- **Both correct: 199 (1.20%) — the two architectures share only 38% of BIO's correct queries**
- **BIO-only correct: 321 (1.93%)** — non-zero, so BIO has *some* unique strengths over CLS
- **CLS-only correct: 3,321 (20.02%)** — CLS has 10× more unique correct queries than BIO
- **Union: 23.15%** — even an oracle ensemble of CLS and BIO would not reach the rules baseline (90.3%); 12,749 queries (76.85%) are wrong under both methods

The two architectures are not redundant, but neither approaches the rules baseline. The 76.85% intersection of failures defines a hard core of queries that no architectural choice within the long-only-training paradigm can solve.

#### C3.b — Error taxonomy on the 16,070 missed BIO queries

| Top-level category | Count | % of misses |
|---|---|---|
| TAGGER_MISS (model emitted no span for a required axis) | 13,882 | 86.4% |
| NORMALIZER_MISS (span emitted, normalizer rejected) | 2,187 | 13.6% |
| WRONG_VALUE (span emitted and normalized, but to the wrong canonical) | 1 | 0.0% |
| ALL_AXES_OK_BUT_CATALOG_MISS | 0 | 0.0% |

Per-axis TAGGER_MISS counts (model didn't emit a span):
- **Nº TUBOS: 13,681 (85.1% of misses)** — the model anchors on " tubos" / " mm" in long text, but the short-text format `<digit> t,` doesn't trigger Nº TUBOS. The digit gets tagged as `B-TUBO` (the singular axis present only in OEB160$) and gets filtered out at the per-(parent, axis) gate because TUBO isn't in the schema for OEB020/030/etc.
- TIPO DE TERRENO: 1,946
- everything else: ≤ 19

Per-axis NORMALIZER_MISS counts (span emitted but unnormalizable):
- **CONDICIONES DE EJECUCIÓN: 15,988 (99.5% of misses!)** — the model emits a B-CONDICIONES span but typically truncated to a single token like `cualquier` or `volumen` or `relevante`. The normalizer can't fuzzy-match a single word to compound canonicals like `Cualquier condición de ejecución` or `Volumen relevante` (Lev distance > 0.15).
- TRABAJO: 7,866
- BANDA DE MANTENIMIENTO: 7,257
- TIPO DE TERRENO: 3,175

The dominant failure pattern (87% of missed queries match this exact signature):
```
TAGGER_MISS:Nº TUBOS | NORMALIZER_MISS:CONDICIONES DE EJECUCIÓN
```

Saved: `analysis/bio_error_taxonomy.csv` (one row per missed query).

#### C3.c — `frana horaria` typo tracer

The short-text corpus contains 2,904 queries with the typo "frana horaria" (missing `j`). Comparing TRABAJO axis accuracy on 200 typo queries vs 200 correctly-spelled queries:

| Surface | n | BIO | CLS |
|---|---|---|---|
| `frana horaria` (typo) | 200 | **96.0%** | 98.0% |
| `franja horaria` (correct) | 200 | 85.5% | **100.0%** |

Both architectures are robust to this typo at the TRABAJO axis level. CLS is more accurate on the canonical surface; BIO is comparable on the typo. Curiously, BIO does better on the typo than on the canonical surface — likely because the typo set has fewer compound TRABAJO values like `Cualquier franja horaria excepcional` that BIO truncates.

Saved: `analysis/franja_horaria_typo_tracer.csv`.

#### Per-axis recall on FULL 16,590 eval (replaces LWN-03's stratified sample)

The LWN-03 sample (1,630 stratified queries) over-represented easy parents and gave inflated numbers. The canonical full-corpus numbers:

| Axis | Total | Correct | Recall (full) | Recall (sample, LWN-03) |
|---|---|---|---|---|
| TRABAJO | 16,571 | 15,220 | **91.8%** | 90.0% |
| TIPO DE TERRENO | 15,259 | 9,948 | 65.2% | 58.5% |
| PROFUNDIDAD | 377 | 249 | 66.0% | 69.4% |
| BANDA DE MANTENIMIENTO | 16,571 | 9,261 | 55.9% | 55.8% |
| **Nº TUBOS** | 15,986 | 2,149 | **13.4%** | 39.0% |
| **CONDICIONES DE EJECUCIÓN** | 16,580 | 141 | **0.9%** | 5.4% |
| MATERIAL, PAVIMENTO, TERRENO | small | 0 | 0% | 0% |
| TIPO DE ACCIÓN, TUBO, DIÁMETRO, DIÁMETROS | small | all | 100% | 100% |

The bottleneck axes are clearer in the full corpus:
- **CONDICIONES at 0.9%** is essentially never correct on short text
- **Nº TUBOS at 13.4%** fails 86.6% of the time (the `<digit> t,` format mismatch)

Queries with **all** axes correct: 85/16,590 (0.51%). The 3.13% item Acc@1 from the eval is achievable because Stage 3 catalog lookup can return the right item from partial parameter matches when the other parents in the group differ on the wrong axes only. The pure all-axes-correct rate is much lower.

Saved: `analysis/bio_per_axis_short_text_full.csv` (replaces the misleading sample-based CSV from LWN-03).

#### C4 — Speed benchmark (200 queries, mean ms / p95 ms)

| Method | CPU mean | CPU p95 | GPU mean | GPU p95 |
|---|---|---|---|---|
| Rules | 0.02 ms | 0.02 ms | — | — |
| CLS classifier | 23.88 ms | 28.26 ms | 5.43 ms | 6.46 ms |
| BIO tagger | 22.94 ms | 28.55 ms | 5.87 ms | 7.73 ms |
| Phi-4 (reference, SEPLN log) | — | — | ~886 ms | — |

BIO and CLS have effectively identical inference latency (within 1 ms). The architectural change is speed-neutral. Both are ~1,200× slower than rules and ~150× faster than Phi-4. The "speed cost of fine-tuning" is paid once at training time; inference cost is the same as the CLS classifier.

Saved: `analysis/speed_benchmark.csv`.

#### D1 — Cross-format diagnostic (500 matched (long, short) pairs)

For each `item_key` present in both long and short corpora, run BIO on both. Per-axis transfer rate = fraction of long-correct that survives to short:

| Axis | Long acc | Short acc | Transfer rate |
|---|---|---|---|
| TRABAJO | 100% | 91.0% | 91.0% |
| TIPO DE TERRENO | 100% | 62.8% | 62.8% |
| BANDA DE MANTENIMIENTO | 100% | 56.7% | 56.7% |
| Nº TUBOS | 100% | 38.6% | 38.6% |
| **CONDICIONES DE EJECUCIÓN** | 100% | 6.8% | **6.8%** |
| MATERIAL, PAVIMENTO, TERRENO | 100% | 0% | 0% |
| DIÁMETRO, DIÁMETROS, TIPO DE ACCIÓN, TUBO | 100% | 100% | 100% |

**`short_only` correct never happens** in any of the 474 pairs. Whenever the short-text format produces a correct prediction, the long-text format also did. The cross-distribution gap is strictly one-directional: long → short, never the reverse.

This is the cleanest possible measurement of cross-distribution loss for this architecture. The CONDICIONES axis loses 93.2 percentage points moving from long to short text on the SAME `item_key`s.

Saved: `analysis/cross_format_diagnostic.csv`.

#### D3 — Frozen-encoder BIO ablation (mirrors LW-07)

Train BIO with `--freeze-encoder` so only the 27-class head (~21k parameters) is learnable. The encoder is the pretrained `intfloat/multilingual-e5-base` with no fine-tuning.

Training (RTX 4090, 5 epochs × 38,007 rows, ~12 min):

| Epoch | Loss | token_acc (long val) | span_f1 (long val) | query_acc (long val) |
|---|---|---|---|---|
| 1 | 1.6752 | 87.7% | 0.0% | 0.0% |
| 2 | 0.8419 | 88.7% | 4.9% | 0.0% |
| 3 | 0.6013 | 90.4% | 6.7% | 0.0% |
| 4 | 0.4885 | 91.1% | 6.9% | 0.0% |
| 5 | 0.4445 | 91.3% | **7.0%** | 0.0% |

Frozen BIO reaches only 7.0% span_f1 on its own training distribution after 5 epochs. Compare to:
- Full FT BIO (LWN-03): span_f1 97.4%, query_acc 99.2% on the same val
- Frozen CLS (LW-07): val_query_acc 11.4% on long text

The frozen BIO is **even worse on long text than the frozen CLS was**, despite operating on the same encoder. The linear projection from frozen E5 token-level representations over a 27-class space is harder than the per-(group, axis) softmaxes the CLS classifier uses.

**Frozen BIO oracle eval result on 16,590 short-text queries:**

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| Frozen BIO oracle | **0.07%** | 100.00% |

Comparison table (LW-06/07 baselines + LWN-03/04):

| Setup | val (long) query_acc | cross-dist oracle Acc@1 | Trainable params |
|---|---|---|---|
| BIO full FT (LWN-03) | 99.2% | 3.13% | 278M |
| BIO frozen encoder (LWN-04) | 0.0% | **0.07%** | 21k |
| CLS full FT (LW-06) | 99.6% | 21.2% | 278M |
| CLS frozen encoder (LW-07) | 11.4% | 0.58% | 45k |

**The frozen BIO is worse than the frozen CLS** (0.07% vs 0.58%) on the cross-distribution test. Three ways the BIO architecture is more brittle than CLS:
1. On its own training distribution: BIO frozen reaches 0.0% query_acc vs CLS frozen's 11.4% (the linear projection from frozen E5 to 27-class BIO is harder than to 97 small softmaxes)
2. On cross-distribution test: BIO frozen 0.07% vs CLS frozen 0.58%
3. With full FT: BIO 3.13% vs CLS 21.2%

Across all three regimes, the BIO architecture trails CLS. The hypothesis that token-level supervision improves cross-distribution robustness (protocol §3.2) is rejected from every angle.

### What this sprint adds to the paper

1. **CLS and BIO are non-redundant but jointly capped at 23%.** No architectural choice within the long-only-training regime gets close to the rules baseline.
2. **The BIO failure mode is dominated by two specific signatures:** TAGGER_MISS:Nº TUBOS (the digit-anchor mismatch in short text) and NORMALIZER_MISS:CONDICIONES (compound-span truncation). Both are mechanically explained and would need targeted fixes — not architecture-level changes.
3. **Cross-distribution loss is strictly one-directional.** No (long, short) pair has the BIO correct only on short. Every short-format degradation reflects information loss vs the long format.
4. **Speed is architecture-invariant.** BIO and CLS have identical inference latency. The architectural choice doesn't change deployment cost.
5. **Frozen encoder ablations confirm representation adaptation is necessary.** BIO frozen reaches only 7% on its own training distribution; full FT is required even to reach the (low) ceiling demonstrated by full-FT cross-distribution numbers.

### Files added

| Artifact | Path |
|---|---|
| Confusion matrix | `analysis/cls_vs_bio_confusion.csv`, `analysis/bio_only_correct_sample.csv` |
| Error taxonomy | `analysis/bio_error_taxonomy.csv` |
| Typo tracer | `analysis/franja_horaria_typo_tracer.csv` |
| Per-axis (full corpus) | `analysis/bio_per_axis_short_text_full.csv` |
| Speed benchmark | `analysis/speed_benchmark.csv` |
| Cross-format | `analysis/cross_format_diagnostic.csv` |
| Frozen BIO checkpoint | `models/e5_bio_tagger_frozen/{model.pt, config.json, training_log.json}` (gitignored) |
| Frozen pipeline | `src/retrievers/structured_pipeline_oracle_bio_tagger_frozen.py`, `configs/structured_pipeline_oracle_bio_tagger_frozen.yaml`, `index/structured_pipeline_oracle_bio_tagger_frozen/meta.json` |

### Out of scope (deferred)

- D2 — query perturbation evaluation (LWN-05+; needs synthetic-query generation)
- E1/E2 — paper draft (LWN-05+)

### Next sprint
**Sprint LWN-05:** Phase E — paper draft. The negative-architecture story is now fully characterized; the paper can be written with the central comparison (CLS vs BIO vs rules vs Phi-4) and the mechanistic per-axis breakdown as the contribution.

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
