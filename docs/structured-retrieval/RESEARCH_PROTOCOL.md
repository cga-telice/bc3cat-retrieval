# Research Protocol: Structure-Aware Retrieval for Parametric Catalogs

**Branch:** `structured-retrieval`
**Repo:** `bc3cat-retrieval`
**Author:** César · March 2026
**Target:** SEPLN Congress — end of March 2026

---

## 1. Purpose and Scope

This protocol is the **implementation roadmap** for the research described in [RESEARCH_PROPOSAL.md](RESEARCH_PROPOSAL.md). It documents the repo context, design decisions, what needs to be built, and the task backlog. It does *not* prescribe rigid sprint boundaries — those are determined just-in-time as work progresses.

**Companion documents:**

| Document | Role | When updated |
|---|---|---|
| `RESEARCH_PROPOSAL.md` | Goals, motivation, contributions | Rarely; only if scope changes |
| `RESEARCH_PROTOCOL.md` | This file; roadmap and backlog | When tasks are added/reprioritized |
| `CLAUDE.md` | Persistent context for Claude Code | After every sprint |
| `RESEARCH_LOG.md` | Running record of decisions, results, issues | After every sprint |
| `sprints/SPRINT_NN.md` | Individual sprint prompt for Claude Code | Written just before each sprint |

---

## 2. Sprint Workflow

Sprints are **not pre-planned in detail**. Instead:

1. **Before each sprint**, César drafts a `sprints/SPRINT_NN.md` file with:
   - Context: what changed in previous sprints (or pointer to CLAUDE.md)
   - Objectives: specific tasks for this sprint
   - Acceptance criteria: how to verify it worked
   - Relevant code pointers and design decisions

2. **During the sprint**, Claude Code executes the sprint file. The sprint file is the prompt.

3. **After each sprint**, César:
   - Updates `RESEARCH_LOG.md` with what happened, what worked, what didn't
   - Updates `CLAUDE.md` with any new context Claude Code needs going forward
   - Decides what the next sprint should tackle (may split, reorder, or add tasks)
   - Drafts the next `sprints/SPRINT_NN.md`

This allows sprints to be split if too big, reordered based on results, and adapted as we learn.

---

## 3. Repository Context

### 3.1 Current State (main branch)

```
bc3cat-retrieval/
├── src/
│   ├── index_builders/       # One module per method (dense_e5.py, bm25_unigram.py, ...)
│   ├── retrievers/           # Matching retriever modules (load() → Searcher)
│   ├── utils/                # evaluation.py, config.py, data_utils.py, text_processing.py
│   ├── index_builder.ipynb   # Config-driven: YAML → index artifacts
│   ├── retrieve.ipynb        # Config-driven: index → ranked results → runs/<method>/
│   └── eval.ipynb            # Aggregates runs/ into eval/ leaderboards
├── configs/                  # One YAML per method variant
├── data/processed/           # OEB_long_norm.parquet, OEB_short_norm.parquet, ...
├── index/                    # Pre-built indexes (dense_e5/, bm25_unigram/, ...)
├── runs/                     # Per-method results (metrics_dual.json, results_top100.jsonl.gz)
├── eval/                     # Aggregated leaderboards and plots
└── CLAUDE.md
```

### 3.2 Builder/Retriever Contract

Every retrieval method follows the same pattern:

**Index builder** (`src/index_builders/<method>.py`):
- `select_field(feats_meta) → str`
- `build(cfg, long_df, text_field) → (artifacts, transformer, X_docs)`

**Retriever** (`src/retrievers/<method>.py`):
- `load(index_dir) → Searcher`
- `Searcher.search(query, k) → (top_indices, scores)`
- `Searcher.search_batch(queries, k) → (indices[B,K], scores[B,K])`

**Config** (`configs/<method>.yaml`) drives `index_builder.ipynb` → `retrieve.ipynb` → `eval.ipynb`.

**Eval output** (`runs/<method>/`): `metrics_dual.json`, `results_top100.jsonl.gz`, per-query CSVs.

### 3.3 Key Data Facts

- **Long-format corpus**: `OEB_long_norm.parquet` — 47,514 rows. Columns: `item_key`, `parent_key`, `concept`, `parameters`, `text`, `text_norm`, `text_word_params`, `numbers`, `param_tokens`, ...
- **Short-format queries**: `OEB_short_norm.parquet` — same structure, used as queries.
- **Query sample**: 16,590 queries (99% confidence, ±1% margin).
- **Concept groups**: 25 groups, sizes 3 to 6,336 items. Largest: 5 axes × 3–8 values each.
- **Parameter structure**: `parameters` column is a dict: `{"A": {"label": "TRABAJO", "values": [{"label": "a", "value": "Diurno"}, ...]}, ...}`.
- **Existing E5 index**: `index/dense_e5/` — 47,514 vectors (item-level), `intfloat/multilingual-e5-base`. **Not concept-level** — a new concept-level index must be built.
- **Parameter data also in bc3cat-dataset repo**: `data/intermediate/OBRA CIVIL/OBRA CIVIL_stage7.json` has the full parametric structure per item.

### 3.4 What Exists vs. What Needs Building

| Component | Exists? | Notes |
|---|---|---|
| E5 item-level index | ✅ | `index/dense_e5/` — indexes all items, not concepts |
| E5 concept-level index | ❌ | One vector per `parent_key` using `concept` text |
| Parameter schema per concept | ❌ | Extract from `parameters` column in parquet |
| LLM parameter extractor | ❌ | Ollama client + prompt + JSON parsing |
| Deterministic catalog lookup | ❌ | Match extracted params → item_key |
| Structured pipeline retriever | ❌ | Wraps Stages 1+2+3, implements Searcher contract |
| Rule-based extractor | ❌ | Regex + string matching baseline (no LLM) |
| Evaluation infra | ✅ | `eval.ipynb`, `ranx`, `metrics_dual.json` — reuse as-is |
| Baseline results | ✅ | All in `runs/` and `eval/` — no re-running needed |

---

## 4. Design Decisions

| Question | Decision | Rationale |
|---|---|---|
| Stage 1 retrieval unit | **Concept-level text** (`concept` field) | Shorter, more discriminative; avoids parameter noise |
| Stage 1 model | **E5** (`intfloat/multilingual-e5-base`) | Lightest benchmarked model, 98.2% parent Acc@1 |
| Stage 2 model | **Llama 3.1 8B** via Ollama | Single model; practical, good multilingual performance |
| Stage 2 prompt language | **Spanish** | Matches catalog language |
| Schema exposure in prompt | **Full value lists** per axis | Maximum information for extraction |
| Partial extraction fallback | **Return sub-group** (items matching resolved axes) | Avoid arbitrary priors; let eval measure impact |
| Evaluation scope | **Item-level ground truth** | Consistent with prior benchmarks |
| Stage 2 temperature | **0.0** | Deterministic for reproducibility |

---

## 5. Task Backlog

Ordered by dependency and priority. Tasks will be grouped into sprints as work progresses — a task may be split into multiple sprints or combined with others depending on what we learn.

### Phase A — Data Preparation

- **A1. Branch setup.** Create `structured-retrieval` from `main`. Set up `sprints/` directory, initial `CLAUDE.md`, `RESEARCH_LOG.md`.

- **A2. Schema extraction.** Parse `OEB_long_norm.parquet` → produce `OEB_concept_schema.json` with per-concept-group structure: concept text, axis labels, value sets, item_key lists. Verify: 25 groups, correct axes/values.

### Phase B — Pipeline Components (independently testable)

- **B1. Concept-level E5 index (Stage 1).** New E5 index with one vector per `parent_key` using the `concept` field. Reuse `dense_e5` builder pattern. Sanity-check: >95% parent Acc@1 on a small sample.

- **B2. Deterministic catalog lookup (Stage 3).** Given `(parent_key, {axis: value | null})` → return matching `item_key`(s). Handle full match, partial match, all-null, unknown values. Testable with synthetic inputs.

- **B3. LLM parameter extractor (Stage 2).** Ollama client for Llama 3.1 8B. Prompt construction from schema. JSON response parsing with retry/fallback. Test on 20 hand-picked queries.

- **B4. Rule-based parameter extractor (Stage 2 baseline).** Regex + exact string matching. Handles numerics and verbatim parameter strings. Establishes the floor.

### Phase C — Integration and Evaluation

- **C1. Pipeline assembly.** Wire Stages 1+2+3 into `structured_pipeline.py` implementing the Searcher contract. End-to-end test on 50 queries.

- **C2. Oracle pipeline variant.** Stage 1 bypassed (ground-truth concept given). Config: `structured_pipeline_oracle.yaml`.

- **C3. Full evaluation run.** Pipeline + oracle on all 16,590 queries. Produce `metrics_dual.json`. Compare against all baselines.

- **C4. Rule-based oracle evaluation.** Oracle + rule-based extractor. Floor without LLM.

### Phase D — Analysis and Paper

- **D1. Error analysis.** Classify failures: (a) wrong concept, (b) wrong extraction, (c) ambiguous query.

- **D2. Paper draft.** SEPLN format. All numbers from `metrics_dual.json`.

- **D3. Figures and tables.** Pipeline diagram, results table, error breakdown. Code-generated.

### Backlog (if time permits)

- Additional LLM model sizes for ablation
- Cross-domain generalization discussion
- Formal mathematical framing

---

## 6. Evaluation Conditions

| Condition | Stage 1 | Stage 2 | Purpose |
|---|---|---|---|
| `structured_pipeline` | E5 concept retrieval | Llama 3.1 8B | **Main result** |
| `structured_pipeline_oracle` | Ground-truth concept | Llama 3.1 8B | Isolate Stage 2 accuracy |
| `oracle_rule` | Ground-truth concept | Rule-based (regex) | Floor without LLM |

Existing baselines already in `runs/` and `eval/` — no re-running.

**Diagnostic interpretation:**
- `oracle` ≫ `pipeline` → Stage 1 is the bottleneck
- `oracle` ≈ `pipeline` → Stage 2 or ambiguity is the bottleneck
- `oracle_rule` ≈ `oracle` LLM → LLM adds little over simple matching
- `oracle_rule` ≪ `oracle` LLM → LLM extraction is essential

---

## 7. New File Map

```
src/
  pipeline/                          # NEW directory
    __init__.py
    schema_extractor.py              # A2
    catalog_lookup.py                # B2
    param_extractor.py               # B3
    param_extractor_rules.py         # B4
    prompts.py                       # B3
  index_builders/
    concept_dense_e5.py              # B1
  retrievers/
    structured_pipeline.py           # C1

configs/
  concept_dense_e5.yaml              # B1
  structured_pipeline.yaml           # C1
  structured_pipeline_oracle.yaml    # C2

data/processed/
  OEB_concept_schema.json            # A2 output

sprints/
  SPRINT_00.md, SPRINT_01.md, ...    # Written just-in-time

CLAUDE.md                            # Updated each sprint
RESEARCH_LOG.md                      # Running log
```

---

## 8. Stage 2 Prompt Template

```
Eres un asistente que extrae parámetros de consultas de construcción ferroviaria.

Concepto: {concept}

Esquema de parámetros:
{axis_label_1}: {value_1_a}, {value_1_b}, ...
{axis_label_2}: {value_2_a}, {value_2_b}, ...
...

Consulta: "{query}"

Extrae el valor de cada parámetro que se pueda inferir de la consulta.
Responde SOLO con un JSON con exactamente las claves del esquema.
Si no puedes determinar el valor de un eje, usa null.

Respuesta:
```

Temperature: 0.0. Malformed responses: one retry, then fallback to all-null.

---

## 9. Risk Register

| Risk | Mitigation |
|---|---|
| Ollama / Llama 3.1 8B not available | Document hardware reqs; test early in B3 |
| LLM JSON output unreliable | Robust parsing with retry; structured output mode if available |
| Concept-level E5 worse than expected | Oracle condition isolates this; can swap model if needed |
| 16,590 × LLM inference is slow | Batch; small sample first; estimate time in B3 before full run |
| Pipeline doesn't beat ColBERT (44.8%) | Error analysis still valuable; oracle provides insight |
| Sprints take longer than expected | Backlog is prioritized; paper can be written with core results only |

---

## 10. Changelog

| Version | Date | Changes |
|---|---|---|
| v0.1 | March 2026 | Initial protocol — flexible sprint approach, single LLM (Llama 3.1 8B), task backlog |

---

*This document is the stable roadmap. Sprint-level detail lives in `sprints/SPRINT_NN.md` files, written just-in-time.*
