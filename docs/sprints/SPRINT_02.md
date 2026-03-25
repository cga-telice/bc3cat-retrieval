# Sprint 02 — Concept-Level E5 Index (Stage 1)

**Tasks from backlog:** B1
**Prerequisites:** Sprint 00 complete (schema JSON exists)

---

## Context

We have the concept schema (`data/processed/OEB_concept_schema.json`) with 25 concept groups and the catalog lookup (Sprint 01). This sprint builds Stage 1 of the pipeline — the concept-level dense index.

The existing E5 index (`index/dense_e5/`) has 47,514 item-level vectors. We need a **new** index with exactly one vector per concept group (25 vectors), using the `concept` field text as the document to embed. This way, a query retrieves a `parent_key`, not an `item_key`.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

### Existing E5 infrastructure to reuse

- **Index builder**: `src/index_builders/dense_e5.py` — implements `select_field()` and `build(cfg, long_df, text_field)`. Produces `embeddings.npy`, `mapping.jsonl`, `meta.json`, `fields.json`.
- **Retriever**: `src/retrievers/dense_e5.py` — `DenseE5Searcher` with `load()`, `search()`, `search_batch()`. Uses `intfloat/multilingual-e5-base` with query prefix `"query: Busca el documento que más se parezca a la siguiente consulta: "`.
- **Config**: `configs/dense_e5.yaml` — reference for YAML structure.
- **Notebook workflow**: `index_builder.ipynb` loads a config, imports the builder, calls `build()`, saves artifacts. `retrieve.ipynb` loads the index and runs queries.

### Key design decision

- Index the `concept` field text (one vector per `parent_key`), not aggregated item text.
- The `mapping.jsonl` should map `doc_id` → `parent_key` (e.g., `external_id: "OEB030$"`), not to `item_key`.

---

## Objectives

### 1. Create the concept-level index builder

Create `src/index_builders/concept_dense_e5.py` that:

1. Loads the concept schema JSON
2. Builds a DataFrame with one row per concept group: columns `parent_key` and `concept` (the text to embed)
3. Encodes the `concept` texts using `intfloat/multilingual-e5-base` with the doc prefix `"passage: "`
4. L2-normalizes the embeddings (consistent with existing E5 convention)
5. Saves the standard index artifact layout:
   - `data/embeddings.npy` — shape `(N_concepts, dim)`, float32
   - `mapping.jsonl` — `{doc_id: int, external_id: parent_key}`
   - `meta.json` — metadata including model name, dim, num_docs
   - `fields.json` — `{"text_field": "concept"}`

**Approach options** (pick whichever is simpler):
- **Option A**: Write a standalone builder that doesn't go through `index_builder.ipynb`. Just a script that loads schema → encodes → saves. Simpler and self-contained.
- **Option B**: Follow the existing builder contract (`select_field` + `build`) and write a matching config, so it integrates with `index_builder.ipynb`. More consistent with the repo.

Either is fine — use your judgment. The retriever side matters more than the builder side.

### 2. Create the config

Create `configs/concept_dense_e5.yaml` following the existing `dense_e5.yaml` pattern. Key differences:
- `method.name: concept_dense_e5`
- `method.impl: concept_dense_e5`
- Index output: `index/concept_dense_e5/`

### 3. Build the index

Run the builder to produce `index/concept_dense_e5/`. Verify:
- `embeddings.npy` has shape `(25, 768)` (25 groups, E5-base dim = 768)
- `mapping.jsonl` has 25 entries with `external_id` values matching the schema's parent_keys

### 4. Sanity-check retrieval

Test concept-level retrieval on a small sample (20–50 queries from `OEB_short_norm.parquet`):
- Encode query texts using E5 with query prefix
- Compute cosine similarity against the 25 concept vectors
- Check: does the top-1 result match the query's `parent_key`?
- Report parent-level Acc@1 on the sample

We expect >95% on a small sample (the full benchmark shows 98.2% at parent level for item-level E5, and concept-level should be at least as good).

**Note**: The existing `DenseE5Searcher` from `src/retrievers/dense_e5.py` can likely be reused as-is for this sanity check — it loads `embeddings.npy` + `mapping.jsonl` and does cosine search. Just point it at `index/concept_dense_e5/`.

---

## Acceptance Criteria

- [ ] `src/index_builders/concept_dense_e5.py` exists
- [ ] `configs/concept_dense_e5.yaml` exists
- [ ] `index/concept_dense_e5/` is produced with: `data/embeddings.npy`, `mapping.jsonl`, `meta.json`, `fields.json`
- [ ] Embeddings shape is `(25, 768)` — one vector per concept group
- [ ] Mapping has 25 entries with correct parent_keys
- [ ] Sanity check on 20–50 queries: parent-level Acc@1 reported (expected >95%)
- [ ] No existing files modified

---

## Out of Scope

- Full benchmark evaluation on 16,590 queries (that's Sprint C3)
- LLM or Ollama setup (Stage 2)
- Pipeline integration (that's C1)
- Modifying the existing item-level E5 index
