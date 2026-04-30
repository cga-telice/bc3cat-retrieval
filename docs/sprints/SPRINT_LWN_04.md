# Sprint LWN-04 — Phase C3/C4 + Phase D (Diagnostic Ablations + Robustness)

**Tasks from backlog:** C3 (per-axis vs CLS, span-vs-query errors, confusion vs CLS, typo tracer), C4 (speed benchmark), D1 (cross-format diagnostic), D3 (frozen-encoder BIO ablation)
**Prerequisites:** Sprint LWN-03 complete (BIO oracle/pipeline = 3.13%/3.10% on 16,590 queries; per-axis recall already characterized)

---

## Context

Sprint LWN-03 produced the headline negative result: BIO oracle Acc@1 = 3.13%, below the CLS classifier's 21.2%. The CONDICIONES DE EJECUCIÓN axis collapses to 5.4% recall on short text — the binding bottleneck.

This sprint produces the **diagnostic ablations** that explain *why* both architectures fail and that turn LWN-03's headline number into a paper-worthy result. Five concrete deliverables, each grounded in already-collected eval data or short additional GPU passes:

1. **C3.a — Confusion vs CLS classifier on the same queries.** Do the two architectures fail on the SAME queries (data-driven gap) or DIFFERENT queries (architecture-specific failures)? The Venn between BIO-correct and CLS-correct sets is the answer.
2. **C3.b — Span-level vs query-level error split.** For each missed BIO query, categorize: (E3-TAGGER_MISS) tagger emitted no span; (E3-NORMALIZER_MISS) tagger emitted a span but normalizer rejected it; (E3-CATALOG_MISS) extraction was correct but Stage 3 failed.
3. **C3.c — `frana horaria` typo tracer.** A small set of queries with the surface typo "frana horaria" (canonical "franja horaria"); does either architecture handle it?
4. **C4 — Speed benchmark.** Mean and p95 latency per query for rules, CLS, BIO, Phi-4, on CPU and GPU.
5. **D1 — Cross-format diagnostic.** Run BIO on the 500 (long, short) pairs of the same `item_key`; per-axis transfer rate is the cleanest measurement of long↔short generalization for this architecture.

**D2 (query perturbation) is deferred to LWN-05** — it requires synthetic-query generation that's higher-effort and lower-payoff than the diagnostics above. **D3 (frozen-encoder BIO) is included** — it's a single GPU training pass (~13 min based on LW-07's frozen-CLS timing) and locks in the negative-architecture story.

Read these for full context:
- `docs/lightweight-extraction-ner/RESEARCH_LOG_LIGHTWEIGHT_NER.md` Sprint LWN-03 entry
- `docs/sprints/SPRINT_LWN_03.md` for the per-axis baseline
- `docs/lightweight-extraction/RESEARCH_LOG_LIGHTWEIGHT-06_Analysis.md` for the CLS-classifier per-axis baseline (the comparison target)

---

## Objectives

### C3.a — Confusion vs CLS classifier (same queries)

Both `runs/structured_pipeline_oracle_bio_tagger/results_perquery_summary.csv` and `runs/structured_pipeline_oracle_classifier/results_perquery_summary.csv` exist for the same 16,590 queries. Build a 2×2 contingency:

|             | CLS correct | CLS wrong |
|-------------|-------------|-----------|
| BIO correct |   N₁₁       |   N₁₀     |
| BIO wrong   |   N₀₁       |   N₀₀     |

Output: `analysis/cls_vs_bio_confusion.csv` with the contingency, plus a list of "BIO-only correct" queries (interesting if non-empty — would suggest BIO has *some* unique strengths).

### C3.b — Span-level vs query-level error split

For each of the 16,070 missed BIO oracle queries, run the BIO extractor and categorize the failure:
- `E3-TAGGER_MISS_X` — model emitted no span for a required axis X
- `E3-NORMALIZER_MISS_X` — model emitted a span but normalizer returned None for X
- `E3-WRONG_VALUE_X` — model emitted a span and normalizer mapped it to a canonical value, but the value was wrong
- `E3-ALL_AXES_OK_BUT_CATALOG_MISS` — every extracted axis matches gold but Stage 3 still didn't return the right item_key

Output: `analysis/bio_error_taxonomy.csv` with one row per missed query (item_key, parent_key, error_class, axes_with_issue).

### C3.c — `frana horaria` typo tracer

`franja horaria` appears in canonical schema (`Cualquier franja horaria`, `Cualquier franja horaria excepcional`). Search the short-text corpus for the typo `frana horaria` (no `j`); also check `franj horaria`, `franjas horaria`, etc. For each typo query, run both BIO and CLS, report the result. Output: `analysis/franja_horaria_typo_tracer.csv`.

### C4 — Speed benchmark

Measure mean and p95 query latency for each Stage 2 method, on CPU and GPU.
- Sample 200 queries (stratified by parent_key)
- For each method, time `extract_batch(parents, queries)` end-to-end on CPU and on GPU (where applicable)
- Methods: `RuleBasedParamExtractor`, `ClassifierParamExtractor`, `BIOParamExtractor`, Phi-4 classify (HTTP call to Ollama; CPU path only as the LLM is shared)
- Output: `analysis/speed_benchmark.csv` with columns (method, device, mean_ms, p95_ms, n)

### D1 — Cross-format diagnostic (500 (long, short) pairs)

Sample 500 `item_key`s present in both `OEB_long_norm.parquet` and `OEB_short_norm.parquet`. For each:
- Run BIO on the long text → predicted dict₁
- Run BIO on the short text → predicted dict₂
- Per-axis: count cases where long is correct AND short is correct (preserved); long correct AND short wrong (degraded); long wrong AND short correct (rare); both wrong.

Output: `analysis/cross_format_diagnostic.csv` showing per-axis transfer rate.

The cleanest signal for the paper: the long-text per-axis accuracy upper-bounds the short-text per-axis accuracy by a known amount, isolated from any other factor.

### D3 — Frozen-encoder BIO ablation

Mirrors LW-07's frozen-CLS ablation. Train BIO with `--freeze-encoder` so only the 27-class head is learnable (~21k parameters):

```bash
docker exec jupyter-pytorch bash -c "cd /work && python -m src.pipeline.training.train_bio_tagger \
    --epochs 5 --batch-size 16 --device cuda \
    --freeze-encoder --output-dir models/e5_bio_tagger_frozen"
```

Then create the parallel pipeline infrastructure:
- `index/structured_pipeline_bio_tagger_frozen/meta.json`, `..._oracle_bio_tagger_frozen/meta.json`
- `src/retrievers/structured_pipeline_bio_tagger_frozen.py`, `..._oracle_bio_tagger_frozen.py`
- Register in `TIER1_CONDITIONS`

Run full eval on 16,590 queries (oracle only is enough — pipeline parent_acc is unchanged from LW-07's 98.5% baseline).

Comparison table:

| Setup | val (long) span_f1 | val (long) query_acc | cross-dist oracle Acc@1 |
|---|---|---|---|
| BIO full FT (LWN-03) | 97.4% | 99.2% | 3.13% |
| BIO frozen encoder (this) | TBD | TBD | TBD |
| CLS frozen encoder (LW-07 baseline) | — | 11.4% | 0.58% |
| CLS full FT (LW-06 baseline) | — | 99.6% | 21.2% |

---

## Acceptance Criteria

- [x] `analysis/cls_vs_bio_confusion.csv` with the 2×2 contingency (BIO∩CLS=199, BIO-only=321, CLS-only=3,321, both wrong=12,749)
- [x] `analysis/bio_error_taxonomy.csv` with one row per missed query (TAGGER_MISS:Nº TUBOS in 13,681 cases; NORMALIZER_MISS:CONDICIONES in 15,988)
- [x] `analysis/franja_horaria_typo_tracer.csv` (BIO 96% / CLS 98% on the typo)
- [x] `analysis/speed_benchmark.csv` (BIO ≈ CLS within 1 ms; ~5.5 ms GPU, ~23 ms CPU)
- [x] `analysis/cross_format_diagnostic.csv` (CONDICIONES transfer rate 6.8%; TRABAJO 91.0%)
- [x] `analysis/bio_per_axis_short_text_full.csv` (canonical full-corpus per-axis numbers)
- [x] `models/e5_bio_tagger_frozen/{model.pt, model_best.pt, config.json, training_log.json}`
- [x] `runs/structured_pipeline_oracle_bio_tagger_frozen/metrics_dual.json` — **0.07% item Acc@1** (worse than frozen CLS at 0.58%)
- [x] `RESEARCH_LOG_LIGHTWEIGHT_NER.md` updated with all five diagnostics
- [x] `CLAUDE_LIGHTWEIGHT_NER.md` Sprint History updated

---

## Out of Scope

- D2 — query perturbation evaluation (deferred to LWN-05; needs higher-effort synthetic-query generation)
- E1/E2 — error taxonomy paper draft + paper draft (Sprint LWN-05+)

---

## Time Estimates

| Step | Estimate |
|---|---|
| C3.a confusion vs CLS | 5 min (read existing CSVs) |
| C3.b error taxonomy | 15 min (run BIO on 16,070 missed; categorize) |
| C3.c typo tracer | 5 min (text search + 2 model runs on small set) |
| C4 speed benchmark | 15 min |
| D1 cross-format diagnostic | 10 min (500 × 2 forwards) |
| D3 frozen training | ~13 min (LW-07 timing) |
| D3 frozen pipeline integration | 10 min |
| D3 full eval on 16,590 | ~12 min |
| Doc updates + commit | 30 min |
| **Total** | **~2 hours** |
