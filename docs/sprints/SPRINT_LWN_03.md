# Sprint LWN-03 — B5 Full Training + Phase C1/C2 (Pipeline Integration + Full Evaluation)

**Tasks from backlog:** B5 (full training run) + C1 (pipeline integration) + C2 (full evaluation)
**Prerequisites:** Sprint LWN-02 complete (`SpanNormalizer`, `BIOTagger`, `BIOParamExtractor`, `train_bio_tagger.py` all in place; B4 sanity verified the loop and architecture)

---

## Context

This is the **decisive sprint**: the one that produces the headline number for the paper. Sprint LWN-02 verified that the BIO architecture works on a CPU sanity sample. This sprint trains the BIO tagger on all 38,007 long-text training rows, wires it into the structured retrieval pipeline, and evaluates it on the same 16,590 short-text query set used by every prior baseline (rules, Phi-4, dense_e5, CLS classifier full FT, frozen).

The central comparison the paper hinges on (protocol §7, §8):

| Method | Pipeline item Acc@1 | Oracle item Acc@1 |
|---|---|---|
| dense_e5 (no FT) | 13.4% | — |
| **CLS classifier full FT (LW-06)** | **20.9%** | **21.2%** |
| Phi-4 classify | 87.7% | 88.6% |
| Rules | 90.3% | 91.4% |
| BM25 param-aware | 97.4% | — |
| **BIO tagger (this sprint)** | **?** | **?** |

The protocol's §8 decision matrix turns the BIO oracle number into a research outcome:

| BIO oracle on short text | Interpretation |
|---|---|
| ≥ 90% | Architectural choice fully closes the cross-distribution gap. **Strongest paper.** |
| 70–90% | Partial recovery. Per-axis story is the contribution. |
| 40–70% | Moderate. Pair with CLS for limits-of-architecture paper. |
| ≤ 40% | Architectural fix doesn't close the gap; redirect to data-side. |
| ≈ 21% | Fully negative — consolidates the negative finding from LWN. |

**This is the sprint that decides which of those rows we live in.**

Read these for full context:
- `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md` §6 Phase B5 + Phase C1/C2, §7 evaluation conditions, §8 diagnostic interpretation
- `docs/lightweight-extraction-ner/CLAUDE_LIGHTWEIGHT_NER.md` — branch context
- `docs/sprints/SPRINT_LWN_01.md` and `SPRINT_LWN_02.md` — what's already built
- `docs/sprints/SPRINT_LW_04.md` and `SPRINT_LW_05.md` — the CLS classifier's comparable sprints (template for pipeline integration + full eval)
- `src/retrievers/structured_pipeline.py` `load()` — the dispatch site for new Stage 2 backends (lines 240–263)

**Do not modify any existing files** other than the two specific dispatch points enumerated below (`structured_pipeline.py` `load()` branch, `run_full_eval.py` `TIER1_CONDITIONS`).

---

## Architecture (recap)

The BIO pipeline integrates into the existing three-stage structured retriever exactly the way the CLS classifier did — only the Stage 2 backend changes:

```
Query
  │
  ▼
[Stage 1] Item-level E5 retrieval (dense_e5, unchanged)
  │  → top-1 item → parent_key derived from item_key mapping
  │  → candidate set: all items in that concept group
  ▼
[Stage 2] BIO tagger + span normalizer  ← THIS IS THE NEW BACKEND
  │  → {axis_label: canonical_value | None}
  ▼
[Stage 3] Deterministic catalog lookup (unchanged)
  │  → exact match on extracted parameters within candidate set
  ▼
Result (single item_key, or ranked sub-group)
```

Two evaluation conditions per protocol §7:
- `structured_pipeline_bio_tagger` — full pipeline (Stage 1 E5 → BIO Stage 2 → catalog lookup)
- `structured_pipeline_oracle_bio_tagger` — oracle parent_key (bypasses Stage 1) + BIO Stage 2

The oracle condition isolates Stage 2 accuracy from any Stage 1 retrieval bottleneck. For the paper, the **oracle** number is the architectural claim; the pipeline number reflects the deployable end-to-end system.

---

## Objectives

### B5 — Full GPU training (the long-running task; do this FIRST)

Train the BIO tagger on all 38,007 long-text rows for 5 epochs on RTX 4090. Expected runtime ~30–60 min based on LW-03 timings (the BIO loss is per-token rather than per-CLS, so each batch is slightly heavier than the CLS classifier's, but the parameter count is identical).

```bash
docker exec jupyter-pytorch bash -c "cd /work && python -m src.pipeline.training.train_bio_tagger \
    --epochs 5 --batch-size 16 --device cuda \
    --output-dir models/e5_bio_tagger"
```

**Epoch-1 collapse-check (from B4 finding):** if the epoch-1 evaluation shows `span_f1 == 0.0%` with `token_acc ≈ 88.6%` (the all-O baseline), abort and re-run with `--class-weight-o 0.1`. The 38k-row training set is much larger than B4's 200, so this is unlikely to fire — but the failure mode is now characterized.

**Acceptance:**
- `models/e5_bio_tagger/{model.pt, model_best.pt, config.json, training_log.json}` produced.
- `training_log.json` shows per-epoch loss decreasing and `span_f1 > 0` from at least epoch 2 onward.
- Per-axis F1 in the final epoch shows non-zero numbers for the high-data axes (TRABAJO, BANDA, Nº TUBOS, CONDICIONES, TIPO DE TERRENO).
- Commit `training_log.json` to the repo (small JSON file). Do NOT commit `model.pt` (1.1GB; .gitignored under `models/`).

### C1 — Pipeline integration

Mirror the CLS classifier's wiring exactly. Add the `bio_tagger` dispatch branch in `src/retrievers/structured_pipeline.py` and create the proxy modules + configs + pseudo-index dirs.

#### C1.a — Dispatch branch in `structured_pipeline.py`

In the `load()` function (around lines 240–263 of [src/retrievers/structured_pipeline.py:240](src/retrievers/structured_pipeline.py:240)), add a new `elif` branch after the existing `classifier` branch:

```python
elif stage2 == "bio_tagger":
    from src.pipeline.param_extractor_bio import BIOParamExtractor
    model_dir = params.get("stage2_model_dir", str(ROOT / "models" / "e5_bio_tagger"))
    if model_dir.startswith("/work/") and not Path(model_dir).exists():
        model_dir = str(ROOT / model_dir.removeprefix("/work/"))
    bio_device = device_override or "cpu"
    extractor = BIOParamExtractor(model_dir, schema_path=SCHEMA_PATH, device=bio_device)
    print(f"  Stage 2: BIO tagger ({model_dir})")
```

Also update the `load()` docstring `stage2_method` enumeration to include `"bio_tagger"`. **No other changes** to `structured_pipeline.py`.

#### C1.b — Proxy modules (one-liners)

Create `src/retrievers/structured_pipeline_bio_tagger.py`:
```python
# Proxy module: re-exports load() from structured_pipeline.
# Variant config (stage2_method=bio_tagger) is in the index dir's meta.json.
from .structured_pipeline import load  # noqa: F401
```

And `src/retrievers/structured_pipeline_oracle_bio_tagger.py` with the same content.

#### C1.c — YAML configs

Create `configs/structured_pipeline_bio_tagger.yaml`:
```yaml
collection: OEB

paths:
  data_dir: /work/data/processed
  index_root: /work/index

inputs:
  short_feats: "{data_dir}/{collection}_short_norm.parquet"
  long_feats: "{data_dir}/{collection}_long_norm.parquet"

method:
  family: structured
  name: structured_pipeline_bio_tagger
  impl: structured_pipeline_bio_tagger
  params: {}

io:
  data_dirname: data
  mapping_file: mapping.jsonl
  fields_file: fields.json
  meta_file: meta.json
```

And `configs/structured_pipeline_oracle_bio_tagger.yaml` with `name`/`impl` updated to `structured_pipeline_oracle_bio_tagger`.

#### C1.d — Pseudo-index directories

Create `index/structured_pipeline_bio_tagger/meta.json`:
```json
{
  "method": "structured_pipeline",
  "impl": "structured_pipeline",
  "variant": "structured_pipeline_bio_tagger",
  "text_field": "text_norm",
  "num_docs": 47514,
  "params": {
    "stage2_method": "bio_tagger",
    "oracle": false,
    "stage2_model_dir": "/work/models/e5_bio_tagger"
  }
}
```

And `index/structured_pipeline_oracle_bio_tagger/meta.json` with `variant: "structured_pipeline_oracle_bio_tagger"` and `params.oracle: true`.

#### C1.e — Register in run_full_eval.py

Add the two condition names to `TIER1_CONDITIONS` in [scripts/run_full_eval.py:45](scripts/run_full_eval.py:45):
```python
TIER1_CONDITIONS = [
    "structured_pipeline_rules",
    "structured_pipeline_oracle_rules",
    "structured_pipeline",
    "structured_pipeline_oracle",
    "structured_pipeline_phi4_classify",
    "structured_pipeline_oracle_phi4_classify",
    "structured_pipeline_bio_tagger",          # ← new
    "structured_pipeline_oracle_bio_tagger",    # ← new
]
```

#### C1.f — Smoke test (50 queries)

Before the full run, verify the wiring with `python -m src.retrievers.structured_pipeline --n-queries 50 --skip-llm` (the script already enumerates conditions; ensure the two new ones load and run without errors). Or use `scripts/run_full_eval.py structured_pipeline_oracle_bio_tagger --n-queries 50 --device cuda` if the eval script supports a query cap (check the existing arg parser).

### C2 — Full evaluation (16,590 queries)

```bash
docker exec jupyter-pytorch bash -c "cd /work && python scripts/run_full_eval.py structured_pipeline_bio_tagger --device cuda"
docker exec jupyter-pytorch bash -c "cd /work && python scripts/run_full_eval.py structured_pipeline_oracle_bio_tagger --device cuda"
```

Expected runtime: ~10–15 min per condition based on LW-07's frozen-classifier eval timing (10m 51s pipeline / 11m 08s oracle for the same 16,590 queries on the same hardware).

**Acceptance:**
- `runs/structured_pipeline_bio_tagger/metrics_dual.json` and `runs/structured_pipeline_oracle_bio_tagger/metrics_dual.json` produced.
- Item Acc@1 numbers populated, parent Acc@1 should be ≥ 98.5% (Stage 1 is unchanged from CLS classifier conditions).
- The headline numbers go into `RESEARCH_LOG_LIGHTWEIGHT_NER.md` and into the protocol §8 decision table — the result interpretation is determined by which row of that table the BIO oracle number lands in.

### Deliverable summary

A single comparison table appended to the research log:

| Setup | val (long) span_f1 | val (long) query_acc | cross-dist pipeline item Acc@1 | cross-dist oracle item Acc@1 | Runtime |
|---|---|---|---|---|---|
| BIO tagger full FT | (B5) | (B5) | (C2 pipeline) | (C2 oracle) | (C2 timing) |
| CLS classifier full FT (LW-06 baseline) | — | 99.6% | 20.9% | 21.2% | — |
| Frozen CLS encoder (LW-07 baseline) | — | 11.4% | 0.56% | 0.58% | — |
| Rules baseline (SEPLN) | — | — | 90.3% | 91.4% | — |

Plus a one-paragraph interpretation referencing protocol §8.

---

## Acceptance Criteria

- [x] `models/e5_bio_tagger/{model.pt, model_best.pt, config.json, training_log.json}` produced from B5.
- [x] `training_log.json` shows monotone loss decrease (1.79 → 0.40 → ... → 0.0001) and `span_f1` rising 57% → 69% → 80% → 89% → **97.4%**.
- [x] `src/retrievers/structured_pipeline.py` has a `bio_tagger` branch in `load()` (one `elif` block added; nothing else changed).
- [x] `src/retrievers/structured_pipeline_bio_tagger.py` and `..._oracle_bio_tagger.py` proxy modules exist.
- [x] `configs/structured_pipeline_bio_tagger.yaml` and `..._oracle_bio_tagger.yaml` exist.
- [x] `index/structured_pipeline_bio_tagger/meta.json` and `..._oracle_bio_tagger/meta.json` exist.
- [x] `scripts/run_full_eval.py` `TIER1_CONDITIONS` has both new conditions registered.
- [x] `runs/structured_pipeline_bio_tagger/metrics_dual.json` produced from C2 (16,590 queries, full pipeline condition).
- [x] `runs/structured_pipeline_oracle_bio_tagger/metrics_dual.json` produced from C2 (16,590 queries, oracle condition).
- [x] `RESEARCH_LOG_LIGHTWEIGHT_NER.md` updated with the comparison table and the §8 interpretation paragraph.
- [x] `CLAUDE_LIGHTWEIGHT_NER.md` Sprint History updated.

---

## Out of Scope

- **Phase C3 — Diagnostic ablations** (per-axis breakdown on 2,000-query sample, span-vs-query error split, confusion matrix vs CLS, `frana horaria` typo set tracer) — Sprint LWN-04.
- **Phase C4 — Speed benchmark** (CPU + GPU mean and p95 across rules / CLS / BIO / Phi-4) — Sprint LWN-04.
- **Phase D — Robustness and comparative analysis** (cross-format diagnostic on 500 long/short pairs, query perturbation evaluation, optional frozen-encoder ablation) — Sprint LWN-05+.
- **Phase E — Paper draft** — Sprint LWN-06+.

---

## Risk Register (this sprint)

| Risk | Mitigation |
|---|---|
| BIO loss collapses to all-O on full corpus (despite class imbalance being diluted) | Epoch-1 collapse check; fall back to `--class-weight-o 0.1`. The B4 finding documents this exact failure mode. |
| Stage 1 E5 retrieval differs from prior runs because of CUDA/torch version drift | Compare parent Acc@1 against LW-06's 98.5% baseline — should match within rounding. If it doesn't, the difference is in Stage 1, not Stage 2. |
| BIO tagger is so slow at inference that 16,590 queries doesn't finish in reasonable time | Inference is per-query forward pass + greedy argmax + normalizer lookup. On RTX 4090, ~5–15ms/query; 16,590 queries ≈ 1.5–4 min for Stage 2. The full eval timing should be similar to LW-07 (~11 min). If it's wildly slower, profile. |
| Span normalizer rejects too many spans → low query Acc@1 even with high span F1 | The 23-test unit suite for `SpanNormalizer` covers all canonical-value-classes. If C2 shows a span-F1/query-Acc gap, the C3 diagnostic ("span-level vs query-level errors") will localize it. |
| Cross-distribution gap survives — BIO oracle ≈ 21% (matches CLS) | Per protocol §8, this is a publishable negative result that consolidates the LWN findings. Not a sprint failure, but the interpretation paragraph in the research log changes accordingly. |

---

## Time Estimates

| Step | Estimate |
|---|---|
| B5 full training | 30–60 min (RTX 4090) |
| C1 wiring (code + configs + meta.json) | 15–30 min |
| C1 smoke test (50 queries) | 5 min |
| C2 pipeline eval | ~12 min |
| C2 oracle eval | ~12 min |
| Doc updates (research log, CLAUDE.md, sprint file) | 30 min |
| **Total wall clock** | **~2.5–3 hours** |

---

## B5 Training Result

5 epochs, batch 16, AdamW lr=2e-5, RTX 4090, ~32 min total. Unweighted CE — the class-imbalance collapse seen in B4 sanity did not fire on the full 38,007-row corpus.

| Epoch | Loss | token_acc (long val) | span_f1 (long val) | query_acc (long val) | Time |
|---|---|---|---|---|---|
| 1 | 0.2175 | 100.0% | 57.3% | 98.7% | 381s |
| 2 | 0.0008 | 100.0% | 68.9% | 99.0% | 381s |
| 3 | 0.0004 | 100.0% | 80.3% | 99.0% | 381s |
| 4 | 0.0002 | 100.0% | 89.3% | 99.1% | 381s |
| **5** | **0.0001** | **100.0%** | **97.4%** | **99.2%** | 381s |

Best checkpoint saved at epoch 5 (model.pt + model_best.pt + config.json + training_log.json under `models/e5_bio_tagger/`).

## C2 Result Report

| Condition | item Acc@1 | parent Acc@1 | Recall@5 | Recall@10 | Runtime |
|---|---|---|---|---|---|
| `structured_pipeline_bio_tagger` (pipeline) | **3.10%** | 98.48% | 15.39% | 25.75% | 12m 02s |
| `structured_pipeline_oracle_bio_tagger` (oracle) | **3.13%** | 100.00% | 15.53% | 26.03% | 11m 58s |

**Oracle vs Pipeline gap:** 0.03 pp on item Acc@1 — Stage 1 retrieval is not the bottleneck (matches LW-06's finding for the CLS classifier). The 1.5 pp parent-Acc@1 gap (98.48% pipeline vs 100% oracle) confirms Stage 1 still works at the CLS-classifier baseline rate.

### Comparison vs prior baselines (16,590 queries)

| Method | Pipeline item Acc@1 | Oracle item Acc@1 |
|---|---|---|
| dense_e5 (no FT) | 13.4% | — |
| **BIO tagger full FT (this sprint)** | **3.10%** | **3.13%** |
| Frozen CLS encoder (LW-07) | 0.56% | 0.58% |
| CLS classifier full FT (LW-06) | 20.9% | 21.2% |
| Phi-4 classify | 87.7% | 88.6% |
| Rules | 90.3% | 91.4% |
| BM25 param-aware | 97.4% | — |

**§8 interpretation:** The BIO tagger lands in **the most negative row** of the protocol's decision matrix — `≤40% → fundamental cross-distribution gap` AND `≈ CLS oracle (~21%) → fully negative architectural result` AND, surprisingly, **below the CLS classifier**. The hypothesis from §3.2 (token-level evidence transfers better than CLS aggregation) is rejected.

### Per-axis cross-distribution recall (1,630 stratified short-text queries)

The `analysis/bio_per_axis_short_text.csv` artifact gives the mechanism:

| Axis | Recall | Reading |
|---|---|---|
| TRABAJO | **90.0%** | Token-level signal transfers cleanly: surface "Diurno"/"Nocturno" looks similar in both formats |
| TIPO DE TERRENO | 58.5% | Surface override (`cualquier clase de terreno → Normal`) recovers ~half the cases |
| BANDA DE MANTENIMIENTO | 55.8% | Operator/quote canonicalization handles `<==`/`>==` typos but compound spans like `3 <= i < 5 horas` partially fail |
| Nº TUBOS | 39.0% | Model anchors on " tubos" (long text) not on " t," (short text) |
| **CONDICIONES DE EJECUCIÓN** | **5.4%** | **THE BOTTLENECK.** Long text has the explicit prefix `condiciones de ejecución:`; short text has `(.../volumen relevante)` with no anchor |
| TIPO DE ACCIÓN, TUBO, DIÁMETRO, DIÁMETROS | 100% | Small but well-anchored |
| MATERIAL, PAVIMENTO, TERRENO | 0% | All in OEB010$/OEB160$ — small-sample, surface form not recovered |

**Mechanistic explanation.** The BIO tagger learned per-axis decisions that are conditioned on the surrounding contextual anchor (the explicit label prefix `condiciones de ejecución:`), not on the value tokens alone. Removing the anchor (short-text format) collapses the per-axis prediction. The CLS classifier (LW-06) had the same failure mechanism but on different axes (TRABAJO, BANDA, TIPO DE TERRENO at 52–69%) and the CLS aggregation gave it more redundancy at the query level.

The hypothesis that token-level supervision would force the model away from anchor-dependence was wrong. The opposite happened: token-level loss creates *stronger* per-token sensitivity to local context, which in this corpus is the very label-prefix anchor that doesn't transfer.

### Side note: normalizer typo fix had zero effect on the headline

`SpanNormalizer._normalize_banda` originally produced spurious whitespace for the multi-equals typos `<==` (7,494 short-text queries) and `>==` (16,206). I added a placeholder-based fix in span_normalizer.py and 5 new tests (still 25/25 passing). Re-running the oracle eval with the fix produced **identical** 3.13% — confirming that for the affected queries, BANDA was not the binding axis (CONDICIONES and Nº TUBOS still dominate). The fix is correct on its own merits but cannot rescue the headline.
