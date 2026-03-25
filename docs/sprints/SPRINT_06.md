# Sprint 06 — Pipeline Integration (C1)

**Tasks from backlog:** C1 (pipeline assembly)
**Prerequisites:** All components built — Stage 1 (item-level E5, Sprint 03), Stage 2 LLM (Sprint 04), Stage 2 rules (Sprint 05), Stage 3 (catalog lookup, Sprint 01)

---

## Context

All independent components are ready:

| Component | Module | Status |
|---|---|---|
| Stage 1: Dense retrieval → parent_key | `src/retrievers/dense_e5.py` (existing) | ✅ Reuse as-is |
| Stage 2: LLM parameter extraction | `src/pipeline/param_extractor.py` | ✅ Sprint 04 |
| Stage 2: Rule-based extraction | `src/pipeline/param_extractor_rules.py` | ✅ Sprint 05 |
| Stage 3: Deterministic lookup | `src/pipeline/catalog_lookup.py` | ✅ Sprint 01 |
| Concept schema | `data/processed/OEB_concept_schema.json` | ✅ Sprint 00 |

This sprint wires them into a unified retriever that follows the existing `Searcher` contract, so we can evaluate it through the standard `eval.ipynb` workflow.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

### Key insight from Sprint 05

The rule-based extractor achieved 100% accuracy on 20 queries (vs. LLM's 70%). This means the pipeline should support **swappable Stage 2 extractors** — the config decides which one to use.

---

## Objectives

### 1. Create the pipeline retriever

Create `src/retrievers/structured_pipeline.py`:

```python
class StructuredPipelineSearcher:
    """Three-stage retriever: dense retrieval → parameter extraction → catalog lookup."""

    def __init__(self, e5_searcher, param_extractor, catalog_lookup,
                 item_to_parent: dict[str, str], mapping: list[dict]):
        """
        Args:
            e5_searcher: Loaded DenseE5Searcher (item-level index)
            param_extractor: LLMParamExtractor or RuleBasedParamExtractor
            catalog_lookup: CatalogLookup instance
            item_to_parent: {item_key → parent_key} mapping from parquet
            mapping: The index mapping (doc_id → item_key)
        """
        ...

    def search(self, query: str, k: int = 100) -> tuple:
        """
        Three-stage search:
        1. Use e5_searcher to retrieve top-1 item → derive parent_key
        2. Use param_extractor to extract parameters for that concept group
        3. Use catalog_lookup to find matching item(s)
        
        Returns:
            (top_indices, scores) matching the Searcher contract
            
        Result ranking:
        - If lookup returns a single item → that item at rank 1, score 1.0
        - If lookup returns a sub-group (partial extraction) → all matching items,
          score 1.0 for all (or decreasing scores for ranking)
        - Remaining items from the concept group fill out to k, lower scores
        - If Stage 1 fails (unknown parent_key) → fall back to raw E5 ranking
        """
        ...

    def search_batch(self, queries: list[str], k: int = 100) -> tuple:
        """
        Batch search. Calls search() for each query.
        Returns (indices[B,K], scores[B,K]).
        Includes progress reporting for large batches.
        """
        ...
```

**Critical: mapping from indices to item_keys and back.**

The existing eval pipeline works with `doc_id` indices (0 to N-1) that map to `item_key` via `mapping.jsonl`. The `search()` method must return indices in this same space. This means:

- The E5 searcher returns `doc_id` indices → map to `item_key` via mapping → map to `parent_key` via parquet
- After catalog lookup returns `item_key(s)` → map back to `doc_id` indices for the return value
- Build a reverse mapping `{item_key → doc_id}` at init time

### 2. Create a factory function

```python
def load(index_dir: str, config: dict) -> StructuredPipelineSearcher:
    """
    Factory following the retriever contract.
    
    Config fields:
        stage1_index: path to E5 index dir (e.g., "index/dense_e5")
        stage2_method: "llm" or "rules"
        stage2_ollama_url: Ollama base URL (only for "llm")
        stage2_model: Ollama model name (only for "llm")
        schema_path: path to OEB_concept_schema.json
        parquet_path: path to long-format parquet
    """
    ...
```

### 3. Create configs

**`configs/structured_pipeline.yaml`** — main pipeline with LLM extractor:
- `method.name: structured_pipeline`
- `method.impl: structured_pipeline`
- Stage 2: LLM (`llm`)
- References: `index/dense_e5/`, `data/processed/OEB_concept_schema.json`

**`configs/structured_pipeline_rules.yaml`** — pipeline with rule-based extractor:
- `method.name: structured_pipeline_rules`
- Stage 2: rules

**`configs/structured_pipeline_oracle.yaml`** — oracle variant (Stage 1 bypassed):
- `method.name: structured_pipeline_oracle`
- Stage 1: ground truth (uses query's known parent_key instead of E5 retrieval)
- Stage 2: LLM

**`configs/structured_pipeline_oracle_rules.yaml`** — oracle + rules:
- Stage 1: ground truth
- Stage 2: rules

The oracle variants need the `StructuredPipelineSearcher` to accept an optional `oracle_parents` dict `{query_text → parent_key}` that bypasses Stage 1. Alternatively, the oracle can be implemented by passing a mock Stage 1 that always returns the correct parent. Choose whichever is cleaner.

### 4. Sanity test on 50 queries

Run the pipeline (both LLM and rules variants) on 50 queries and verify:

1. Output format matches what `eval.ipynb` expects: `(indices[B,K], scores[B,K])`
2. The top-1 result for rule-based pipeline has high accuracy (matching Sprint 05's signal)
3. The LLM pipeline runs without errors
4. Oracle variants work correctly (should show higher accuracy than non-oracle)

Print: method, item Acc@1, parent Acc@1 for all 4 conditions on the 50-query sample.

---

## Acceptance Criteria

- [ ] `src/retrievers/structured_pipeline.py` exists with `StructuredPipelineSearcher` and `load()` factory
- [ ] Supports swappable Stage 2 (LLM or rules) via config
- [ ] Supports oracle mode (bypass Stage 1) via config
- [ ] `configs/structured_pipeline.yaml` exists
- [ ] `configs/structured_pipeline_rules.yaml` exists
- [ ] `configs/structured_pipeline_oracle.yaml` exists
- [ ] `configs/structured_pipeline_oracle_rules.yaml` exists
- [ ] Output format compatible with eval pipeline: `(indices[B,K], scores[B,K])`
- [ ] 50-query sanity test: all 4 conditions run, results printed
- [ ] No existing files modified (except adding new configs)
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3)
- Error analysis (Sprint D1)
- Prompt optimization
- Modifying eval.ipynb or any existing evaluation code
