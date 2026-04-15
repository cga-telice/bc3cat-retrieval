# Structured Retrieval — Branch Context for Claude Code

**Branch:** `structured-retrieval`
**Goal:** Three-stage retrieval pipeline separating concept retrieval from parameter resolution.
**Do not modify existing files from `main`.** All new work lives in new files on this branch.

---

## The Problem in One Paragraph

The BC3CAT dataset has 47,508 catalog items organized into 25 concept groups. Neural retrieval methods achieve 96–99% accuracy at the concept (parent) level but only 12–45% at the item level, because items within a concept group differ only in parametric values (e.g., terrain type, number of tubes) and embeddings collapse these differences. The three-stage pipeline fixes this by: (1) retrieving the correct concept group with dense embeddings, (2) extracting parameter values from the query with an LLM, (3) looking up the exact item deterministically.

## Reference Documents

- `docs/RESEARCH_PROPOSAL.md` — research goals, motivation, baseline results, contributions
- `docs/RESEARCH_PROTOCOL.md` — implementation roadmap, design decisions, task backlog
- `docs/RESEARCH_LOG.md` — running record of what happened in each sprint
- `sprints/SPRINT_NN.md` — the current sprint's objectives and acceptance criteria

---

## Pipeline Architecture

```
Query
  │
  ▼
[Stage 1] Item-level E5 retrieval (intfloat/multilingual-e5-base)
  │  → top-1 item → parent_key derived from item_key mapping
  │  → candidate set: all items in that concept group
  ▼
[Stage 2] LLM parameter extraction (Llama 3.1 8B via Ollama)
  │  → extracted: {axis_label: value | null, ...}
  ▼
[Stage 3] Deterministic catalog lookup
  │  → exact match on extracted parameters within candidate set
  ▼
Result (single item_key, or ranked sub-group if extraction is partial)
```

## Design Decisions

| Decision | Value | Rationale |
|---|---|---|
| Stage 1 model | E5 (`intfloat/multilingual-e5-base`) | Lightest benchmarked model; item-level: 98.2% parent Acc@1. Concept-level only 85.6% (Sprint 02) due to near-identical concept texts across 6 tube-diameter groups |
| Stage 1 retrieval unit | Item-level (`text` field), parent_key from top-1 result's mapping | Concept-level vectors (Sprint 02) reached only 86% parent Acc@1 due to near-identical concept texts. Item-level vectors carry diameter info, achieving 98.2% |
| Stage 2 model | Llama 3.1 8B via Ollama | Single model, practical, multilingual |
| Stage 2 prompt language | Spanish | Matches catalog language |
| Stage 2 temperature | 0.0 | Deterministic for reproducibility |
| Schema in prompt | Full value lists per axis | Maximum extraction information |
| Partial extraction | Return sub-group of matching items | No arbitrary priors |
| Ollama version | 0.17.7 (Docker) | Pinned for reproducibility; `latest` tag lags releases |

### Stage 1 Integration Note

`DenseE5Searcher` from `src/retrievers/dense_e5.py` is used directly as Stage 1 — **no adapter or wrapper needed**. The pipeline only needs an `{item_key: parent_key}` lookup dict built from the parquet.

**Flow:**
```
searcher = load("index/dense_e5")
item_to_parent = dict(zip(long_df["item_key"], long_df["parent_key"]))

top_idx, scores = searcher.search(query, k=1)
item_key = searcher.external_ids[top_idx[0]]
parent_key = item_to_parent[item_key]
# → proceed with Stage 2 using parent_key and concept schema
```

---

## Data Structures

**Concept schema** (`data/processed/OEB_concept_schema.json` — produced in Sprint 00):
```json
{
  "OEB030$": {
    "concept": "CANALIZACIÓN CON TUBOS DE POLIETILENO...",
    "axes": {
      "TRABAJO": ["Diurno", "Nocturno"],
      "Nº TUBOS": ["1", "2", "3", "4"],
      "TIPO DE TERRENO": ["Sin clasificar", "Bajo vías", "Rocoso"]
    },
    "item_keys": ["OEB030aaa", "OEB030aab", ...],
    "num_items": 6336
  },
  ...
}
```
25 concept groups total. Sizes range from 3 items (1 axis) to 6,336 items (5 axes).

**Parameter column in parquet** (`parameters` field per row):
```json
{
  "A": {"label": "TRABAJO", "values": [{"label": "a", "value": "Diurno"}]},
  "B": {"label": "TIPO DE TERRENO", "values": [{"label": "a", "value": "Sin clasificar"}]},
  ...
}
```
Each leaf item has exactly one value per axis (the `values` list always has one element per axis for leaf items).

**Long-format parquet files** (`data/processed/`):
- `OEB_long_norm.parquet` — normalized text, used by dense methods (E5, BGE-M3)
- `OEB_long_feats.parquet` — extra tokenized columns, used by lexical methods (BM25, TF-IDF)
- Both contain: `item_key`, `parent_key`, `concept`, `parameters`, `text`. 47,514 rows.

---

## New Files in This Branch

```
src/
  pipeline/                          # Pipeline components
    __init__.py                      # ✅ Sprint 00
    schema_extractor.py              # ✅ Sprint 00
    catalog_lookup.py                # ✅ Sprint 01 — Stage 3
    verify_stage1.py                 # ✅ Sprint 03 — Stage 1 verification
    param_extractor.py               # ✅ Sprint 04 — Stage 2 LLM extractor
    param_extractor_rules.py         # ✅ Sprint 05 — Stage 2 rule-based baseline
    prompts.py                       # ✅ Sprint 04 — prompt templates (+ classify prompt, Sprint 07)
  index_builders/
    concept_dense_e5.py              # ✅ Sprint 02 — exploratory, not used in final pipeline
  retrievers/
    structured_pipeline.py           # ✅ Sprint 06 — full pipeline searcher + sanity test
    structured_pipeline_rules.py     # ✅ Sprint 06 — proxy module (re-exports load())
    structured_pipeline_oracle.py    # ✅ Sprint 06 — proxy module (re-exports load())
    structured_pipeline_oracle_rules.py # ✅ Sprint 06 — proxy module (re-exports load())
    structured_pipeline_classify.py  # ✅ Sprint 07 — proxy module (re-exports load())
    structured_pipeline_oracle_classify.py # ✅ Sprint 07 — proxy module (re-exports load())
    structured_pipeline_twostep.py   # ✅ Sprint 08 — proxy module (re-exports load())
    structured_pipeline_oracle_twostep.py # ✅ Sprint 08 — proxy module (re-exports load())
    structured_pipeline_paraaware.py # ✅ Sprint 09 — proxy module (re-exports load())
    structured_pipeline_oracle_paraaware.py # ✅ Sprint 09 — proxy module (re-exports load())
    structured_pipeline_phi4_extract.py # ✅ Sprint 10 — proxy module (re-exports load())
    structured_pipeline_oracle_phi4_extract.py # ✅ Sprint 10 — proxy module (re-exports load())
    structured_pipeline_phi4_classify.py # ✅ Sprint 10 — proxy module (re-exports load())
    structured_pipeline_oracle_phi4_classify.py # ✅ Sprint 10 — proxy module (re-exports load())
    structured_pipeline_phi4_twostep.py # ✅ Sprint 11 — proxy module (re-exports load())
    structured_pipeline_oracle_phi4_twostep.py # ✅ Sprint 11 — proxy module (re-exports load())
    structured_pipeline_phi4_paraaware.py # ✅ Sprint 11 — proxy module (re-exports load())
    structured_pipeline_oracle_phi4_paraaware.py # ✅ Sprint 11 — proxy module (re-exports load())
    structured_pipeline_paraaware2.py # ✅ Sprint 12 — proxy module (re-exports load())
    structured_pipeline_oracle_paraaware2.py # ✅ Sprint 12 — proxy module (re-exports load())
    structured_pipeline_phi4_paraaware2.py # ✅ Sprint 12 — proxy module (re-exports load())
    structured_pipeline_oracle_phi4_paraaware2.py # ✅ Sprint 12 — proxy module (re-exports load())

configs/
  concept_dense_e5.yaml              # ✅ Sprint 02 — exploratory, not used in final pipeline
  structured_pipeline.yaml           # ✅ Sprint 06 — E5 + LLM + catalog
  structured_pipeline_rules.yaml     # ✅ Sprint 06 — E5 + rules + catalog
  structured_pipeline_oracle.yaml    # ✅ Sprint 06 — oracle + LLM + catalog
  structured_pipeline_oracle_rules.yaml # ✅ Sprint 06 — oracle + rules + catalog
  structured_pipeline_classify.yaml    # ✅ Sprint 07 — E5 + LLM-classify + catalog
  structured_pipeline_oracle_classify.yaml # ✅ Sprint 07 — oracle + LLM-classify + catalog
  structured_pipeline_twostep.yaml     # ✅ Sprint 08 — E5 + LLM-twostep + catalog
  structured_pipeline_oracle_twostep.yaml # ✅ Sprint 08 — oracle + LLM-twostep + catalog
  structured_pipeline_paraaware.yaml     # ✅ Sprint 09 — E5 + LLM-paraaware + catalog
  structured_pipeline_oracle_paraaware.yaml # ✅ Sprint 09 — oracle + LLM-paraaware + catalog
  structured_pipeline_phi4_extract.yaml    # ✅ Sprint 10 — E5 + Phi-4 extract + catalog
  structured_pipeline_oracle_phi4_extract.yaml # ✅ Sprint 10 — oracle + Phi-4 extract + catalog
  structured_pipeline_phi4_classify.yaml   # ✅ Sprint 10 — E5 + Phi-4 classify + catalog
  structured_pipeline_oracle_phi4_classify.yaml # ✅ Sprint 10 — oracle + Phi-4 classify + catalog
  structured_pipeline_phi4_twostep.yaml        # ✅ Sprint 11 — E5 + Phi-4 twostep + catalog
  structured_pipeline_oracle_phi4_twostep.yaml  # ✅ Sprint 11 — oracle + Phi-4 twostep + catalog
  structured_pipeline_phi4_paraaware.yaml       # ✅ Sprint 11 — E5 + Phi-4 paraaware + catalog
  structured_pipeline_oracle_phi4_paraaware.yaml # ✅ Sprint 11 — oracle + Phi-4 paraaware + catalog
  structured_pipeline_paraaware2.yaml          # ✅ Sprint 12 — E5 + LLM paraaware2 + catalog
  structured_pipeline_oracle_paraaware2.yaml   # ✅ Sprint 12 — oracle + LLM paraaware2 + catalog
  structured_pipeline_phi4_paraaware2.yaml     # ✅ Sprint 12 — E5 + Phi-4 paraaware2 + catalog
  structured_pipeline_oracle_phi4_paraaware2.yaml # ✅ Sprint 12 — oracle + Phi-4 paraaware2 + catalog

scripts/
  setup_structured_index.py          # ✅ Sprint 06 — creates pseudo-index dirs for all variants
  run_full_eval.py                   # ✅ Sprint 13 — full 16,590-query evaluation with checkpointing
  error_analysis.py                  # ✅ Sprint D1 — error classification, tables, qualitative examples

analysis/                              # ✅ Sprint D1 — error analysis outputs
  error_distribution.csv             # Table A: error category × 6 conditions
  errors_by_concept_group.csv        # Table B: hardest concept groups (rules pipeline)
  errors_by_axis.csv                 # Table C: per-axis accuracy (rules oracle)
  error_examples.json                # 3-5 qualitative examples per error type
  rules_vs_llm_comparison.csv        # Queries where rules and LLMs disagree
  error_analysis_summary.md          # Narrative summary with all tables (paper-ready)

data/processed/
  OEB_concept_schema.json            # ✅ Sprint 00

index/
  concept_dense_e5/                  # ✅ Sprint 02 — 25 vectors, shape (25, 768)
    data/embeddings.npy
    mapping.jsonl
    meta.json
    fields.json
  structured_pipeline/               # ✅ Sprint 06 — pseudo-index dir (E5 + LLM)
  structured_pipeline_rules/         # ✅ Sprint 06 — pseudo-index dir (E5 + rules)
  structured_pipeline_oracle/        # ✅ Sprint 06 — pseudo-index dir (oracle + LLM)
  structured_pipeline_oracle_rules/  # ✅ Sprint 06 — pseudo-index dir (oracle + rules)
  structured_pipeline_classify/      # ✅ Sprint 07 — pseudo-index dir (E5 + LLM-classify)
  structured_pipeline_oracle_classify/ # ✅ Sprint 07 — pseudo-index dir (oracle + LLM-classify)
  structured_pipeline_twostep/       # ✅ Sprint 08 — pseudo-index dir (E5 + LLM-twostep)
  structured_pipeline_oracle_twostep/ # ✅ Sprint 08 — pseudo-index dir (oracle + LLM-twostep)
  structured_pipeline_paraaware/     # ✅ Sprint 09 — pseudo-index dir (E5 + LLM-paraaware)
  structured_pipeline_oracle_paraaware/ # ✅ Sprint 09 — pseudo-index dir (oracle + LLM-paraaware)
  structured_pipeline_phi4_extract/    # ✅ Sprint 10 — pseudo-index dir (E5 + Phi-4 extract)
  structured_pipeline_oracle_phi4_extract/ # ✅ Sprint 10 — pseudo-index dir (oracle + Phi-4 extract)
  structured_pipeline_phi4_classify/   # ✅ Sprint 10 — pseudo-index dir (E5 + Phi-4 classify)
  structured_pipeline_oracle_phi4_classify/ # ✅ Sprint 10 — pseudo-index dir (oracle + Phi-4 classify)
  structured_pipeline_phi4_twostep/        # ✅ Sprint 11 — pseudo-index dir (E5 + Phi-4 twostep)
  structured_pipeline_oracle_phi4_twostep/ # ✅ Sprint 11 — pseudo-index dir (oracle + Phi-4 twostep)
  structured_pipeline_phi4_paraaware/      # ✅ Sprint 11 — pseudo-index dir (E5 + Phi-4 paraaware)
  structured_pipeline_oracle_phi4_paraaware/ # ✅ Sprint 11 — pseudo-index dir (oracle + Phi-4 paraaware)
  structured_pipeline_paraaware2/            # ✅ Sprint 12 — pseudo-index dir (E5 + LLM paraaware2)
  structured_pipeline_oracle_paraaware2/     # ✅ Sprint 12 — pseudo-index dir (oracle + LLM paraaware2)
  structured_pipeline_phi4_paraaware2/       # ✅ Sprint 12 — pseudo-index dir (E5 + Phi-4 paraaware2)
  structured_pipeline_oracle_phi4_paraaware2/ # ✅ Sprint 12 — pseudo-index dir (oracle + Phi-4 paraaware2)

docs/
  RESEARCH_PROPOSAL.md
  RESEARCH_PROTOCOL.md
  RESEARCH_LOG.md
  CLAUDE_STRUCTURED_RETRIEVAL.md     # This file

sprints/
  SPRINT_00.md                       # ✅ Complete
  SPRINT_01.md                       # ✅ Complete
  SPRINT_02.md                       # ✅ Complete
  SPRINT_03.md                       # ✅ Complete
  SPRINT_04.md                       # ✅ Complete
  SPRINT_05.md                       # ✅ Complete
  SPRINT_06.md                       # ✅ Complete
  SPRINT_07.md                       # ✅ Complete
  SPRINT_08.md                       # ✅ Complete
  SPRINT_09.md                       # ✅ Complete
  SPRINT_10.md                       # ✅ Complete
  SPRINT_11.md                       # ✅ Complete
  SPRINT_12.md                       # ✅ Complete
```

## Evaluation Conditions

| Condition | Stage 1 | Stage 2 | Stage 3 | Purpose |
|---|---|---|---|---|
| `structured_pipeline` | E5 item-level retrieval | Llama 3.1 8B | Catalog lookup | Main result |
| `structured_pipeline_rules` | E5 item-level retrieval | Rule-based | Catalog lookup | Rules baseline (no LLM) |
| `structured_pipeline_oracle` | Ground-truth parent_key | Llama 3.1 8B | Catalog lookup | Isolate Stage 2 from Stage 1 errors |
| `structured_pipeline_oracle_rules` | Ground-truth parent_key | Rule-based | Catalog lookup | Upper bound (perfect Stage 1 + rules) |
| `structured_pipeline_classify` | E5 item-level retrieval | Llama 3.1 8B (classify) | Catalog lookup | LLM classification prompt (Sprint 07) |
| `structured_pipeline_oracle_classify` | Ground-truth parent_key | Llama 3.1 8B (classify) | Catalog lookup | Oracle + LLM classification prompt |
| `structured_pipeline_twostep` | E5 item-level retrieval | Llama 3.1 8B (twostep) | Catalog lookup | Two-step extraction+match (Sprint 08) |
| `structured_pipeline_oracle_twostep` | Ground-truth parent_key | Llama 3.1 8B (twostep) | Catalog lookup | Oracle + two-step extraction+match |
| `structured_pipeline_paraaware` | E5 item-level retrieval | Llama 3.1 8B (paraaware) | Catalog lookup | Parameter-aware two-step (Sprint 09) |
| `structured_pipeline_oracle_paraaware` | Ground-truth parent_key | Llama 3.1 8B (paraaware) | Catalog lookup | Oracle + parameter-aware two-step |
| `structured_pipeline_phi4_extract` | E5 item-level retrieval | Phi-4 14B (extract) | Catalog lookup | Phi-4 extract mode (Sprint 10) |
| `structured_pipeline_oracle_phi4_extract` | Ground-truth parent_key | Phi-4 14B (extract) | Catalog lookup | Oracle + Phi-4 extract mode |
| `structured_pipeline_phi4_classify` | E5 item-level retrieval | Phi-4 14B (classify) | Catalog lookup | Phi-4 classify mode (Sprint 10) |
| `structured_pipeline_oracle_phi4_classify` | Ground-truth parent_key | Phi-4 14B (classify) | Catalog lookup | Oracle + Phi-4 classify mode |
| `structured_pipeline_phi4_twostep` | E5 item-level retrieval | Phi-4 14B (twostep) | Catalog lookup | Phi-4 two-step extraction+match (Sprint 11) |
| `structured_pipeline_oracle_phi4_twostep` | Ground-truth parent_key | Phi-4 14B (twostep) | Catalog lookup | Oracle + Phi-4 two-step extraction+match |
| `structured_pipeline_phi4_paraaware` | E5 item-level retrieval | Phi-4 14B (paraaware) | Catalog lookup | Phi-4 parameter-aware two-step (Sprint 11) |
| `structured_pipeline_oracle_phi4_paraaware` | Ground-truth parent_key | Phi-4 14B (paraaware) | Catalog lookup | Oracle + Phi-4 parameter-aware two-step |
| `structured_pipeline_paraaware2` | E5 item-level retrieval | Llama 3.1 8B (paraaware2) | Catalog lookup | Per-axis detection with values (Sprint 12) |
| `structured_pipeline_oracle_paraaware2` | Ground-truth parent_key | Llama 3.1 8B (paraaware2) | Catalog lookup | Oracle + per-axis detection with values |
| `structured_pipeline_phi4_paraaware2` | E5 item-level retrieval | Phi-4 14B (paraaware2) | Catalog lookup | Phi-4 per-axis detection with values (Sprint 12) |
| `structured_pipeline_oracle_phi4_paraaware2` | Ground-truth parent_key | Phi-4 14B (paraaware2) | Catalog lookup | Oracle + Phi-4 per-axis detection with values |

---

## Sprint History

*Newest entries at the top.*

### After Sprint D1 — Error Analysis
**Date:** March 2026
**What changed:**
- Created `scripts/error_analysis.py` — classifies every failed query (item Acc@1 = 0) into error categories (E1-WRONG_CONCEPT, E2-PARTIAL_EXTRACT, E2-WRONG_VALUE, E2-ALL_NULL, E3-SCHEMA_MISMATCH) across all 6 Tier 1 conditions
- Re-runs Stage 2 rules extraction on failed queries for sub-classification (LLM conditions classified as E2-UNSPECIFIED unless `--rerun-llm` flag)
- Produces 6 output files in `analysis/` directory (see File Inventory above)
**Key findings:**

| Finding | Detail |
|---|---|
| E1-WRONG_CONCEPT | 252 queries (15.7% of rules pipeline errors) — the pipeline→oracle gap. All 3 pipeline conditions share the same 252 Stage 1 misses. |
| E2-PARTIAL_EXTRACT | 100% of rules oracle errors (1,434 queries). Rules never produce wrong values — only null when they can't match. 0 E2-WRONG_VALUE, 0 E2-ALL_NULL, 0 E3-SCHEMA_MISMATCH. |
| Hardest axis | TRABAJO: 93.9% accuracy (1,017 null extractions out of 16,571 occurrences). Other axes are >99.7% or 100%. |
| Hardest concept group | OEB190$ (ZANJA...A MANO): 35.8% error rate. OEB200$ (ZANJA...A MÁQUINA): 33.6%. |
| has_numbers dominance | 99.8% of errors come from queries with numeric parameters (3,167/3,170 for rules pipeline). The 29 no_numbers queries have 0% error rate for rules. |
| Rules vs Llama (oracle) | 887 queries where rules fails but Llama succeeds, 2,429 where Llama fails but rules succeeds. Rules are significantly better overall. |
| Rules vs Phi-4 (oracle) | 804 rules-only failures, 1,257 Phi-4-only failures. Phi-4 classify is closer to rules but still worse. |

**Insights for paper:**
- The structured pipeline's error ceiling is set by Stage 2 parameter extraction, specifically the TRABAJO axis which accounts for ~70% of rules oracle errors
- Rules extraction never produces wrong values — it either matches correctly or returns null. This makes it predictable and debuggable.
- The 252 Stage 1 errors are exclusively concept confusions between similar groups (e.g., 110mm↔160mm, mano↔máquina)

### After Sprint 13 — Full Evaluation Run (C3)
**Date:** March 2026
**What changed:**
- Created `scripts/run_full_eval.py` — self-contained evaluation script with CLI, checkpointing (every 500 queries), streaming JSONL output, and built-in metrics computation
- Ran all 6 Tier 1 conditions on 16,590 queries (fixed seed=42, shared query set via `runs/structured_eval_queries.json`)
- Output files in `runs/<condition>/` matching existing format: `results_top100.jsonl.gz`, `metrics_dual.json/csv`, `results_perquery_summary.csv`, etc.
**Key results (item Acc@1 on 16,590 queries):**

| Condition | item Acc@1 | parent Acc@1 | has_num | no_num | Runtime |
|---|---|---|---|---|---|
| Rules (pipeline) | 90.3% | 98.5% | 90.3% | 100% | 10m 50s |
| Rules (oracle) | 91.4% | 100.0% | 91.3% | 100% | 13m 05s |
| Phi-4 classify (pipeline) | 87.7% | 98.5% | 87.7% | 96.6% | 5h 17m |
| Phi-4 classify (oracle) | 88.6% | 100.0% | 88.6% | 96.6% | 5h 16m |
| Llama extract (pipeline) | 80.9% | 98.5% | 80.9% | 89.7% | 3h 27m |
| Llama extract (oracle) | 82.1% | 100.0% | 82.0% | 89.7% | 3h 27m |

**Comparison with best baselines:**
- BM25 param-aware tokens: 97.4% (still best overall — domain-specific tokenization)
- BM25 standard unigram: 86.9% (Phi-4 classify beats it at 87.7%)
- Dense E5 item-level: 13.4% (structured pipeline's Stage 1 component)

**Key observations:**
- Rules pipeline (90.3%) vs oracle (91.4%): only 1.1% lost to Stage 1 E5 errors — E5 retrieval is not the bottleneck
- Llama extract pipeline (80.9%) vs oracle (82.1%): only 1.2% difference — LLM normalization is the bottleneck, not retrieval
- Phi-4 classify pipeline (87.7%) vs oracle (88.6%): 0.9% difference — same pattern
- 50-query samples were pessimistic: Llama extract 68%→80.9%, Phi-4 classify 80%→87.7%, Rules 84%→90.3%
- `no_numbers` queries (N=29) show near-perfect accuracy across all methods — parametric items are the challenge
**Known issues:**
- LLM normalization failures remain (e.g., "Unknown value '0.80 m' for axis 'PROFUNDIDAD'") — values extracted by LLM don't always match catalog's axis value format

### After Sprint 12 — Paraaware2: Per-Axis Detection with Informed Step 1
**Date:** March 2026
**What changed:**
- Added `build_paraaware2_step1_prompt()` and `build_paraaware2_step2_prompt()` to `src/pipeline/prompts.py` — one LLM call per axis showing all possible values; returns bare value (not JSON); Step 2 fallback only for unexpected outputs
- Added `_extract_paraaware2()` method to `LLMParamExtractor` — dispatches via `prompt_mode="paraaware2"`; tracks Step 2 fallback count via `self._paraaware2_step2_fallbacks`
- Updated `extract()` dispatch: `prompt_mode="paraaware2"` routes to `_extract_paraaware2()` before paraaware check
- Added 4 paraaware2 variants to `scripts/setup_structured_index.py` (22 total variants)
- Created 4 proxy modules and 4 YAML configs for paraaware2 × {Llama, Phi-4} × {pipeline, oracle}
- Extended T3 test with `--paraaware2` flag and Step 2 fallback count metric
- Added 4 paraaware2 conditions to pipeline sanity test (22 conditions total)
**Key design differences (paraaware2 vs original paraaware):**
- N calls (one per axis) returning bare values vs 2 calls returning JSON dicts
- Each call shows full list of possible values — detection and classification happen simultaneously
- No JSON parsing needed — simple string cleanup replaces `_parse_json_response()`
- Step 2 is a fallback only for unexpected outputs, not a mandatory second pass
**Key results — Significant improvement over original paraaware; Phi-4 approaches classify.**
**20-query Stage 2 comparison:**
- Llama paraaware2: 82.4% per-axis (61/74), 55.0% per-query (11/20), 647ms/query, 5 Step 2 fallbacks, 9 norm errors
- Phi-4 paraaware2: 93.2% per-axis (69/74), 80.0% per-query (16/20), 726ms/query, 9 Step 2 fallbacks, 5 norm errors
**Comparison with original paraaware (per-axis accuracy):**

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Paraaware (Sprint 09) | 48.6% | 78.4% |
| Paraaware2 (Sprint 12) | 82.4% | 93.2% |
| Delta | +33.8 pp | +14.8 pp |

**Analysis:**
- Paraaware2 dramatically improves over original paraaware for both models: showing possible values upfront eliminates the abstract detection failures from Sprint 09
- Phi-4 paraaware2 (93.2%) approaches Phi-4 classify (100.0%) — the per-axis approach with values shown is nearly as effective as classify for Phi-4
- Llama paraaware2 (82.4%) is below Llama extract (87.8%) and classify (86.5%) — Llama still makes normalization errors on multi-call approach
- Step 2 fallbacks are low (5-9) confirming Step 1 is well-behaved; Phi-4 has more because it sometimes concatenates multiple axis values
- Main failure mode: BANDA DE MANTENIMIENTO confusion (time intervals) and TUBO/DIAMETROS normalization
**50-query pipeline sanity test:**

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| Llama paraaware2 | 50.0% | 92.0% | 872.1ms |
| Llama oracle paraaware2 | 58.0% | 100.0% | 789.2ms |
| Phi-4 paraaware2 | 60.0% | 92.0% | 852.1ms |
| Phi-4 oracle paraaware2 | 68.0% | 100.0% | 772.9ms |

Pipeline ranking (item Acc@1, oracle, 50 queries): rules 92.0% > Phi-4 classify 88.0% > Phi-4 extract 72.0% > Phi-4 paraaware2 68.0% > Llama extract 74.0% > Llama classify 60.0% > Llama paraaware2 58.0% > Phi-4 paraaware 50.0% > Phi-4 twostep 40.0% > Llama twostep 26.0% > Llama paraaware 22.0%.

**Conclusion:** Per-axis detection with informed values fixes the fundamental problem of original paraaware. However, it doesn't surpass single-call classify mode, which remains simpler (1 call vs N calls) and more accurate (especially for Phi-4). The N-call approach adds latency proportional to axis count without accuracy benefit over classify.

### After Sprint 11 — Phi-4 Twostep and Paraaware (Complete Model Comparison)
**Date:** March 2026
**What changed:**
- Created 4 Phi-4 twostep + paraaware pipeline variants (phi4_twostep, phi4_paraaware × {pipeline, oracle}):
  - 4 proxy modules, 4 YAML configs, 4 pseudo-index dirs (via `setup_structured_index.py`)
  - Total: 18 variants (14 existing + 4 new)
- Added 4 Phi-4 twostep/paraaware conditions to pipeline sanity test in `structured_pipeline.py` (18 conditions total)
- Completes the 2 models × 4 prompt modes comparison matrix
**Key results — Phi-4 paraaware shows dramatic improvement over Llama; twostep degrades.**
**20-query Stage 2 comparison (Phi-4, twostep + paraaware):**
- Rule-based: 100.0% per-axis (74/74), 100.0% per-query (20/20), 0.015ms/query
- Phi-4 extract: 77.0% per-axis (57/74), 65.0% per-query (13/20), 1092ms/query
- Phi-4 twostep: 58.1% per-axis, 35.0% per-query (7/20), 1905ms/query, 23 errors
- Phi-4 paraaware: 78.4% per-axis, 45.0% per-query (9/20), 2207ms/query, 16 errors
**Complete 2×4 Stage 2 matrix (20 queries, per-axis accuracy):**

| Method | Llama 3.1 8B | Phi-4 14B | Delta |
|---|---|---|---|
| Extract | 87.8% | 77.0% | -10.8 pp |
| Classify | 86.5% | 100.0% | +13.5 pp |
| Twostep | 64.9% | 58.1% | -6.8 pp |
| Paraaware | 48.6% | 78.4% | +29.8 pp |

**50-query pipeline sanity test (all 18 conditions, new Phi-4 results):**

| Condition | item Acc@1 | parent Acc@1 | time |
|---|---|---|---|
| `structured_pipeline_phi4_twostep` | 36.0% | 92.0% | ~2267ms/q |
| `structured_pipeline_oracle_phi4_twostep` | 40.0% | 100.0% | ~2232ms/q |
| `structured_pipeline_phi4_paraaware` | 44.0% | 92.0% | ~2922ms/q |
| `structured_pipeline_oracle_phi4_paraaware` | 50.0% | 100.0% | ~2560ms/q |

**Cross-model pipeline comparison (all methods, pipeline item Acc@1):**

| Method | Llama | Phi-4 | Delta |
|---|---|---|---|
| Extract | 66.0% | 64.0% | -2.0 pp |
| Classify | 52.0% | 80.0% | +28.0 pp |
| Twostep | 22.0% | 36.0% | +14.0 pp |
| Paraaware | 18.0% | 44.0% | +26.0 pp |

**Analysis:**
- **Model scaling has asymmetric effects by prompt mode:** Closed-set selection tasks (classify, paraaware Step 2) benefit dramatically from scaling. Open-ended extraction tasks (extract, twostep Step 1) do NOT benefit or slightly degrade.
- **Paraaware shows biggest absolute improvement** with Phi-4 (+29.8 pp per-axis, +26 pp pipeline) because its Step 2 (match non-null axes to schema values) is a closed-set selection task that benefits from better reasoning. Llama's failures were concentrated in Step 1 detection errors that Phi-4 avoids.
- **Twostep degrades with Phi-4** (-6.8 pp per-axis) — its Step 1 is unconstrained free-form extraction where larger models produce more verbose/compound descriptions, making Step 2 matching harder.
- **Final ranking (pipeline item Acc@1):** Rules 84% >> Phi-4 classify 80% > Phi-4 extract 64% ≈ Llama extract 66% > Phi-4 paraaware 44% > Phi-4 twostep 36% > Llama twostep 22% > Llama paraaware 18%
- **Phi-4 classify remains the best LLM method** (80%/88% pipeline/oracle), approaching rules (84%/92%)
**Conclusion:** The complete 2×4 matrix confirms that prompt mode × model interactions are highly non-linear. The key finding for the paper: task framing (closed-set vs open-ended) determines whether model scaling helps. Rules remain the best overall method.

### After Sprint 10 — Reproduce Results with Phi-4 14B (Model Comparison)
**Date:** March 2026
**What changed:**
- Pulled Phi-4 14B model in Ollama (tag: `phi4:latest`, 9.1 GB, Microsoft's reasoning-focused architecture)
- Created 4 Phi-4 pipeline configs and proxy modules (phi4_extract, phi4_classify x {pipeline, oracle})
- Added 4 Phi-4 variants to `scripts/setup_structured_index.py` (14 total variants)
- Added `--model` CLI flag to `param_extractor_rules.py` — allows switching LLM model for T3 comparison (default: `llama3.1:8b`)
- Added 4 Phi-4 conditions to pipeline sanity test in `structured_pipeline.py` (14 conditions total)
**Key results — MIXED: Phi-4 classify achieves perfect Stage 2 accuracy, but Phi-4 extract is worse than Llama.**
**20-query Stage 2 comparison (Phi-4 vs rules):**
- Rule-based: 100.0% per-axis (74/74), 100.0% per-query (20/20), 0.016ms/query
- Phi-4 extract: 77.0% per-axis (57/74), 65.0% per-query (13/20), 1450ms/query
- Phi-4 classify: **100.0% per-axis (74/74), 100.0% per-query (20/20)**, 886ms/query
- Phi-4 extract errors: 17 (all omissions — WORSE than Llama's 9)
- Phi-4 classify errors: 0 (PERFECT)
**Cross-model comparison (20-query Stage 2):**
- Extract mode: Llama 87.8% > Phi-4 77.0% — larger model is WORSE at open extraction
- Classify mode: Phi-4 100.0% >> Llama 86.5% — larger model EXCELS at closed-set selection
**50-query pipeline sanity test (Phi-4 conditions):**
- `structured_pipeline_phi4_extract`: item Acc@1 = 64.0%, parent Acc@1 = 92.0%
- `structured_pipeline_oracle_phi4_extract`: item Acc@1 = 72.0%, parent Acc@1 = 100.0%
- `structured_pipeline_phi4_classify`: item Acc@1 = 80.0%, parent Acc@1 = 92.0%
- `structured_pipeline_oracle_phi4_classify`: item Acc@1 = 88.0%, parent Acc@1 = 100.0%
**Full 50-query comparison table:**

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% |
| `structured_pipeline` (Llama extract) | 66.0% | 92.0% |
| `structured_pipeline_classify` (Llama) | 52.0% | 92.0% |
| `structured_pipeline_phi4_extract` | 64.0% | 92.0% |
| `structured_pipeline_phi4_classify` | **80.0%** | 92.0% |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% |
| `structured_pipeline_oracle` (Llama extract) | 74.0% | 100.0% |
| `structured_pipeline_oracle_classify` (Llama) | 60.0% | 100.0% |
| `structured_pipeline_oracle_phi4_extract` | 72.0% | 100.0% |
| `structured_pipeline_oracle_phi4_classify` | **88.0%** | 100.0% |

**Analysis:**
- **Classify mode benefits enormously from model scaling:** Llama classify 52%/60% → Phi-4 classify 80%/88% (+28pp pipeline, +28pp oracle). The gap with rules narrows from 32pp to 4pp.
- **Extract mode does NOT benefit from scaling:** Llama extract 66%/74% → Phi-4 extract 64%/72% — actually slightly WORSE. Open-ended extraction is inherently harder, and larger models produce more selective/compact responses, increasing omissions.
- **In isolated Stage 2 (20-query):** Phi-4 classify achieves 100%/100%, proving the problem WAS model capability for closed-set selection. Llama 3.1 8B simply lacked the reasoning ability to reliably select from pipe-separated option lists.
- **In full pipeline (50-query):** Phi-4 classify (80%) approaches rules (84%) but doesn't match — the remaining 4pp gap comes from harder edge cases (normalization errors on depth/band values) that surface in the larger sample.
- **Oracle Phi-4 classify (88%) approaches oracle rules (92%)** — the 4pp gap is genuine Stage 2 errors on harder concept groups (OEB190$, OEB200$ with depth/band values that Phi-4 still reformats).
- **Timing:** Phi-4 is ~1.5-2x slower than Llama (886-1450ms vs 570-700ms per query) due to larger model size (9.1 GB vs 4.9 GB).
**Conclusion:** The results are a mix of Sprint 10's scenarios 2 and 3. For classify mode, the problem WAS model capability (Phi-4 matches rules on 20-query). For extract mode, the problem is inherent to open-ended extraction regardless of model. **Phi-4 classify is the best LLM method overall**, approaching rules-based extraction. However, rules remain faster (0.016ms vs 886ms), simpler, and slightly more accurate on the full 50-query set.

### After Sprint 09 — Parameter-Aware Two-Step LLM Extraction (Stage 2 Revision)
**Date:** March 2026
**What changed:**
- Added `build_paraaware_extract_prompt()` and `build_paraaware_match_prompt()` to `src/pipeline/prompts.py` — Step 1 frames task as parameter detection ("does the query contain info about X?") rather than open extraction; Step 2 only processes non-null axes from Step 1
- Added `_extract_paraaware()` method to `LLMParamExtractor` — key optimization: separates axes into non-null and null after Step 1, skips Step 2 entirely if all axes are null, Step 2 receives only non-null axes
- Updated `extract()` dispatch: `prompt_mode="paraaware"` routes to `_extract_paraaware()` before twostep/extract/classify checks
- Added 2 paraaware variants to `scripts/setup_structured_index.py` (10 total variants)
- Created 2 proxy modules (`structured_pipeline_paraaware.py`, `structured_pipeline_oracle_paraaware.py`) and 2 YAML configs
- Extended T3 test to five-way comparison (rules, extract, classify, twostep, paraaware) with `--paraaware` flag
- Added paraaware conditions to pipeline sanity test (10 conditions total)
**Key design differences (paraaware vs twostep):**
- Step 1 framing: "Analiza... y determina si contiene informacion" (detection) vs twostep's "describe brevemente que valor indica" (extraction)
- Step 2 optimization: only non-null axes from Step 1 are sent to Step 2, reducing matching task
- If all axes null after Step 1, Step 2 is skipped entirely (optimization)
**Key results — NEGATIVE RESULT: paraaware performs even worse than twostep.**
**Five-way Stage 2 comparison (20 queries):**
- Rule-based: 100.0% per-axis (74/74), 100.0% per-query (20/20), 0.015ms/query
- LLM-extract: 87.8% per-axis (65/74), 70.0% per-query (14/20), 584ms/query
- LLM-classify: 86.5% per-axis (64/74), 65.0% per-query (13/20), 570ms/query
- LLM-twostep: 64.9% per-axis (48/74), 35.0% per-query (7/20), 1153ms/query
- LLM-paraaware: 48.6% per-axis (36/74), 0.0% per-query (0/20), 1128ms/query
- Error breakdown: LLM-extract=9, LLM-classify=10, LLM-twostep=25, LLM-paraaware=38
**Analysis:**
- Paraaware performs the worst of all methods — even worse than twostep (48.6% vs 64.9% per-axis)
- Massive omission errors (38 vs 25 for twostep) — the detection framing causes the LLM to produce verbose compound descriptions AND incorrectly null-out axes that should have values
- Step 1 still produces compound descriptions (e.g., "Diurno/i >=5 horas/Volumen relevante" for TRABAJO) that Step 2 cannot match
- The null filtering optimization backfires: incorrectly-nulled axes never get a chance at Step 2
- Both two-step approaches fundamentally fail because llama3.1:8b cannot decompose compound schema values (TRABAJO, CONDICIONES DE EJECUCION) that combine multiple sub-parameters
**Conclusion:** Parameter-aware two-step extraction is another negative result. All LLM methods rank: extract (87.8%) >> classify (86.5%) >> twostep (64.9%) >> paraaware (48.6%). Rules-based extractor (100%) remains the clear best Stage 2 method. Next: proceed to Sprint C3 (full evaluation on 16,590 queries) with rules-based extraction.

### After Sprint 08 — Two-Step LLM Extraction (Stage 2 Revision)
**Date:** March 2026
**What changed:**
- Added `build_twostep_extract_prompt()` and `build_twostep_match_prompt()` to `src/pipeline/prompts.py` — Step 1 freely extracts without schema values, Step 2 maps to schema
- Added `_extract_twostep()` method to `LLMParamExtractor` — two sequential Ollama calls with graceful degradation (Step 2 failure falls back to Step 1 direct validation)
- Updated `extract()` dispatch: `prompt_mode="twostep"` routes to `_extract_twostep()` before classify/extract check
- Added 2 twostep variants to `scripts/setup_structured_index.py` (8 total variants)
- Created 2 proxy modules (`structured_pipeline_twostep.py`, `structured_pipeline_oracle_twostep.py`) and 2 YAML configs
- Extended T3 test to four-way comparison (rules, extract, classify, twostep) with `--twostep` flag
- Added twostep conditions to pipeline sanity test (8 conditions total)
**Key design differences (twostep vs extract/classify):**
- Two LLM calls: Step 1 lists axis labels only (no values), LLM describes freely; Step 2 shows both LLM descriptions and schema values for matching
- Separate understanding from normalization — hypothesis: free extraction captures semantics better, schema-guided matching normalizes better
- ~2x time cost per query (two Ollama calls vs one)
**Key results (50-query sanity test, all 8 conditions):**
- `structured_pipeline_twostep`: item Acc@1 = 22.0%, parent Acc@1 = 92.0%
- `structured_pipeline_oracle_twostep`: item Acc@1 = 26.0%, parent Acc@1 = 100.0%
**Four-way comparison (20 queries):**
- Rule-based: 100.0% per-axis (74/74), 100.0% per-query (20/20), 0.015ms/query
- LLM-extract: 87.8% per-axis (65/74), 70.0% per-query (14/20), 687ms/query
- LLM-classify: 86.5% per-axis (64/74), 65.0% per-query (13/20), 568ms/query
- LLM-twostep: 64.9% per-axis (48/74), 35.0% per-query (7/20), 1147ms/query
- Error breakdown: LLM-extract=9, LLM-classify=10, LLM-twostep=25
**Analysis:**
- Two-step approach performs significantly WORSE than both extract and classify modes
- Massive increase in omission errors (25 vs 9/10) — Step 1 free-form descriptions don't map cleanly to schema values in Step 2
- Step 1 produces verbose/compound descriptions (e.g., "Nocturno excepcional/no necesita intervalo/volumen relevante" for TRABAJO) that Step 2 cannot match to individual schema values
- Step 2 sometimes fails to parse JSON entirely (fallback to Step 1 direct validation)
- The separation hypothesis was wrong: giving the LLM both the query AND schema values in a single call (extract mode) works better than separating the two steps
- 2x time cost with 3x worse accuracy makes this approach unviable
**Conclusion:** Two-step extraction is a negative result. The original extract prompt remains the best LLM approach. Rules-based extractor remains the overall best Stage 2 method. Next: proceed to Sprint C3 (full evaluation on 16,590 queries) with rules-based extraction.

### After Sprint 07 — LLM Classification Prompt (Stage 2 Revision)
**Date:** March 2026
**What changed:**
- Added `build_classification_prompt()` to `src/pipeline/prompts.py` — pipe-separated values, "clasifica" framing, explicit "NO modifiques" instruction, ASCII-safe text
- Added `prompt_mode` parameter to `LLMParamExtractor.__init__()` (default: `"classify"`); dispatches to `build_classification_prompt()` or `build_extraction_prompt()` based on mode
- Threaded `stage2_prompt_mode` through `load()` in `structured_pipeline.py` (reads from `meta.json` params, default `"extract"` for backward compatibility)
- Added 2 classify variants to `scripts/setup_structured_index.py` (6 total variants)
- Created 2 proxy modules (`structured_pipeline_classify.py`, `structured_pipeline_oracle_classify.py`) and 2 YAML configs
- Extended T3 test in `param_extractor_rules.py` to three-way comparison (rules vs LLM-extract vs LLM-classify) with `--classify` flag and normalization error counting
- Added classify conditions to pipeline sanity test in `structured_pipeline.py`
**Key design differences (classify vs extract prompt):**
- Values separated with `|` (pipe) instead of commas — emphasizes discrete options
- "clasifica" instead of "extrae" — selects from closed set vs copies from query
- Explicit: "NO modifiques, reformatees ni parafrasees los valores" — prevents reformatting
- "copiado exactamente" — demands exact schema value copying
**Backward compatibility:**
- `stage2_prompt_mode` defaults to `"extract"` in `load()`, so existing variants without this key in meta.json continue unchanged
- `prompt_mode` defaults to `"classify"` in `LLMParamExtractor.__init__()` per sprint spec
**Key results (50-query sanity test, all 6 conditions):**
- `structured_pipeline_rules`: item Acc@1 = 84.0%, parent Acc@1 = 92.0%
- `structured_pipeline_oracle_rules`: item Acc@1 = 92.0%, parent Acc@1 = 100.0%
- `structured_pipeline` (LLM-extract): item Acc@1 = 68.0%, parent Acc@1 = 92.0%
- `structured_pipeline_oracle` (LLM-extract): item Acc@1 = 76.0%, parent Acc@1 = 100.0%
- `structured_pipeline_classify` (LLM-classify): item Acc@1 = 52.0%, parent Acc@1 = 92.0%
- `structured_pipeline_oracle_classify` (LLM-classify): item Acc@1 = 60.0%, parent Acc@1 = 100.0%
**Three-way comparison (20 queries):**
- Rule-based: 100.0% per-axis (74/74), 100.0% per-query (20/20), 0.015ms/query
- LLM-extract: 87.8% per-axis (65/74), 70.0% per-query (14/20), 1101ms/query
- LLM-classify: 86.5% per-axis (64/74), 65.0% per-query (13/20), 572ms/query
- Normalization errors: LLM-extract=9, LLM-classify=10
**Analysis:**
- Classification prompt fixed normalization errors (PROFUNDIDAD `1,10 m` now correct) but introduced more omission errors (LLM returns None more often for axes it previously extracted correctly)
- Net effect: classify is worse than extract on both 20-query (86.5% vs 87.8%) and 50-query (52%/60% vs 68%/76%) samples
- The classification prompt trades normalization errors for omission errors — the LLM struggles to match bare numeric values (e.g., Nº TUBOS "3") to pipe-separated option lists
**Known issues:**
- Classification prompt underperforms extraction prompt — further prompt engineering may help (e.g., few-shot examples, different value formatting)

### After Sprint 06 — Pipeline Integration (C1)
**Date:** March 2026
**What changed:**
- Created `src/retrievers/structured_pipeline.py` — `StructuredPipelineSearcher` class wrapping all three stages behind the Searcher contract (`search`, `search_batch`, `external_ids`)
- Created 3 proxy retriever modules (`structured_pipeline_rules.py`, `structured_pipeline_oracle.py`, `structured_pipeline_oracle_rules.py`) — each re-exports `load()` so `dynamic_load_retriever` can import them
- Created 4 YAML configs matching the 4 evaluation conditions
- Created `scripts/setup_structured_index.py` — generates pseudo-index directories (meta.json, fields.json, mapping.jsonl copy, empty data/) for each variant
- `load(index_dir)` factory reads pipeline config from `meta.json`, instantiates appropriate extractor (LLM or rules), handles oracle mode
- Three-tier ranking: Tier 1 = matched items (score ~1.0), Tier 2 = remaining concept group items (score ~0.5), Tier 3 = E5 fallback (scores < 0.5)
- Added `device_override` parameter to `load()` for non-CUDA hosts
**Key results (50-query sanity test, rules variants):**
- `structured_pipeline_rules`: item Acc@1 = 84.0%, parent Acc@1 = 92.0%, 110ms/query
- `structured_pipeline_oracle_rules`: item Acc@1 = 92.0%, parent Acc@1 = 100.0%, 94ms/query
- Oracle gives perfect parent accuracy (bypasses E5 Stage 1), confirming pipeline integration works
- 8% item Acc@1 gap between oracle and non-oracle shows Stage 1 errors propagate (~8% parent misses)
- Output shapes verified: (B, K) arrays with int64/float32 dtypes
**Design decisions:**
- Pseudo-index directories: pipeline reuses E5 index internally, but `retrieve.ipynb` requires `index/{method}/` with meta.json + fields.json + mapping.jsonl + data/. Solved by creating lightweight dirs with variant-specific meta.json configs and a shared mapping.jsonl (copied from E5)
- Proxy modules: `dynamic_load_retriever` imports `retrievers.{method_name}`. Since all 4 variants share the same `StructuredPipelineSearcher`, proxy modules simply re-export `load()`. Variant behavior is determined by the index dir's meta.json, not the module.
- Three-tier ranking ensures k results are always returned, even for small concept groups or failed extraction
**Known issues:**
- LLM variants not tested on Windows (requires Ollama + CUDA); will test in Docker for Sprint C3
- 50-query sanity test is not the full evaluation — Sprint C3 will run all 16,590 queries

### After Sprint 05 — Rule-Based Parameter Extractor (Stage 2 Baseline)
**Date:** March 2026
**What changed:**
- Created `src/pipeline/param_extractor_rules.py` — `RuleBasedParamExtractor` class using string matching
- Same interface as `LLMParamExtractor` (`extract`, `extract_batch`) for drop-in replacement
- Two matching strategies: (1) normalized substring matching with longest-match-wins and subsumption filtering for text axes, (2) context-aware regex matching for numeric axes (Nº TUBOS, TUBO, DIÁMETROS)
- Axis classification: "text" vs "numeric" based on whether any normalized value is ≤ 2 characters
- Reuses existing `normalize_text()` from `src/utils/text_processing.py` for accent stripping and tokenization
**Key results:**
- Per-axis accuracy: 100.0% (74/74) on 20-query sample — vs LLM's 87.8% (65/74)
- Per-query accuracy: 100.0% (20/20) — vs LLM's 70.0% (14/20)
- Speed: 0.015ms/query — vs LLM's 900ms/query (60,000× faster)
- LLM failures were all on exact-format values (PROFUNDIDAD "1,10 m" vs LLM "1.10", TUBO '3"' vs LLM "3", BANDA DE MANTENIMIENTO ranges returned as None)
- Rule-based matches perfectly because parameter values appear as literal substrings in query text
**Known issues:**
- 100% accuracy on 20-query sample may not hold on full 16,590-query evaluation (Sprint C3) — queries are generated from catalog items, so substring matching is expected to work well on this dataset. The comparison's value is methodological: it quantifies the LLM's failure modes rather than proving rules are universally better.

### After Sprint 04 — LLM Parameter Extractor (Stage 2)
**Date:** March 2026
**What changed:**
- Added Ollama 0.17.7 as Docker service in `docker-compose.yml` (GPU-enabled, `ollama-models` volume)
- Created `src/pipeline/prompts.py` — Spanish prompt template for parameter extraction
- Created `src/pipeline/param_extractor.py` — `LLMParamExtractor` class using Ollama REST API
- Uses `requests.post()` to call `/api/generate` (no `ollama` Python package)
- JSON parsing handles markdown code fences, trailing commas, with retry on failure
- Value validation: case-insensitive comparison against schema, unknown values → None
**Key results:**
- Single extraction (OEB010$): 3/3 axes correct, 34s first call (model loading), ~585ms steady-state
- Batch of 20 queries: per-axis accuracy 87.8% (65/74), per-query accuracy 70.0% (14/20), avg 585ms/query
- Failures from: LLM returning values not in schema (e.g., numeric shorthand '3' instead of full tube name), some axes not extracted
- JSON parsing edge cases: all 5 test cases pass (code fences, trailing commas, empty, malformed)
**Known issues:**
- Some concept groups with numeric/range-based axis values (PROFUNDIDAD, BANDA DE MANTENIMIENTO) see lower extraction accuracy — LLM returns approximate rather than exact schema values

### After Sprint 03 — Pivot to Item-Level E5 Retrieval (Stage 1)
**Date:** March 2026
**What changed:**
- Pivoted Stage 1 from concept-level index (25 vectors) to existing item-level E5 index (`index/dense_e5/`, 47,514 vectors)
- Pipeline derives `parent_key` from top-1 item's `item_key` via parquet lookup
- Created `src/pipeline/verify_stage1.py` — confirms item-level retrieval works for Stage 1
- Marked `concept_dense_e5.py` and `.yaml` as exploratory (not used in final pipeline)
- Existing `DenseE5Searcher` from `src/retrievers/dense_e5.py` used directly — no adapter needed
**Key results:**
- Item-level parent Acc@1 = 97.5% (195/200) on 200-query sample (vs 85.6% concept-level)
- `DenseE5Searcher.search(query, k=1)` → `external_ids[idx]` → item_key → lookup dict → parent_key
- No new index or retriever code required — reuses existing item-level infrastructure
**Known issues:**
- None

### After Sprint 02 — Concept-Level E5 Index (Stage 1)
**Date:** March 2026
**What changed:**
- Created `src/index_builders/concept_dense_e5.py` — standalone builder encoding 25 concept texts with `intfloat/multilingual-e5-base`
- Created `configs/concept_dense_e5.yaml`
- Built `index/concept_dense_e5/` — shape (25, 768), one vector per concept group
- Existing `DenseE5Searcher` reused as-is for retrieval (no modifications)
**Key results:**
- Acc@1 = 85.6%, Acc@3 = 99.4% on 500-query sample
- All failures from 6 groups with near-identical concept texts (differ only in tube diameter: 40/50/90/110/160/200mm)
- "passage: " doc prefix makes negligible difference
**Known issues:**
- Acc@1 below expected >95%. Pipeline should consider top-K concepts at Stage 1, not just top-1.

### After Sprint 01 — Deterministic Catalog Lookup (Stage 3)
**Date:** March 2026
**What changed:**
- Created `src/pipeline/catalog_lookup.py` — `CatalogLookup` class with `lookup()`, `get_schema()`, `get_all_parent_keys()`
- Builds reverse index from parquet: (parameter combination) → item_key
**Key results:**
- Full match → single item_key ✅
- Partial match (null axes) → correct sub-group size ✅
- All-null → full concept group ✅
- Unknown parent_key → empty list ✅
- Unknown axis value → handled gracefully ✅
- Tested on small (OEB160$, 3 items) and large (OEB030$, 6,336 items) groups
**Known issues:**
- None

### After Sprint 00 — Branch Setup and Schema Extraction
**Date:** March 2026
**What changed:**
- Created `src/pipeline/` package with `__init__.py` and `schema_extractor.py`
- Produced `data/processed/OEB_concept_schema.json` — 25 concept groups verified
**Key results:**
- Groups range from 1 axis / 3 items (OEB160$) to 5 axes / 6,336 items (OEB030$, OEB040$)
- Spot-checked OEB010$, OEB030$, OEB160$ — all match raw parquet
**Known issues:**
- None
