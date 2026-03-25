# Sprint 03 — Pivot Stage 1 to Item-Level E5 Retrieval

**Tasks from backlog:** B1 (revised)
**Prerequisites:** Sprint 02 findings documented

---

## Context

Sprint 02 built a concept-level E5 index (25 vectors, one per concept group). Sanity check showed **86% parent Acc@1** — below the expected >95%. Root cause: 6 concept groups share near-identical `concept` text, differing only in tube diameter (110mm, 160mm, etc.). The E5 encoder can't reliably distinguish them. However, Acc@3 was 99.4%.

The existing **item-level** E5 index (`index/dense_e5/`, 47,514 vectors) achieves **98.2% parent Acc@1** because each item's text includes the specific diameter. The parent accuracy was measured by checking if the retrieved item's `parent_key` matched the query's ground-truth `parent_key`.

**Decision: Use the existing item-level E5 index for Stage 1.** Retrieve the top-1 item, take its `parent_key`, and proceed with Stage 2 + Stage 3.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Update context documents

Update `docs/CLAUDE_STRUCTURED_RETRIEVAL.md`:

- In the **Pipeline Architecture** section, change Stage 1 description from "concept-level index" to "item-level E5 index, parent_key derived from top-1 result"
- In the **Design Decisions** table:
  - Change "Stage 1 retrieval unit" from "Concept-level (`concept` field text)" to "Item-level (`text_norm` field), parent_key from top-1 result's mapping"
  - Add rationale: "Concept-level vectors (Sprint 02) reached only 86% parent Acc@1 due to near-identical concept texts across 6 tube-diameter groups. Item-level vectors carry diameter info, achieving 98.2%."
- In the **New Files** section, mark `concept_dense_e5.py` as "exploratory — not used in final pipeline"
- Update sprint history with Sprint 02 findings and the pivot decision

Update `docs/RESEARCH_LOG.md`:

- Add Sprint 02 entry documenting the concept-level experiment, the 86% vs 98.2% finding, and the decision to pivot

### 2. Verify item-level retrieval as Stage 1

Write a short verification script (can be in `src/pipeline/` or as a standalone script) that:

1. Loads the existing item-level E5 index from `index/dense_e5/`
2. Loads its `mapping.jsonl` to get `{doc_id → item_key}` mapping
3. Loads the parquet to get `{item_key → parent_key}` mapping
4. For a sample of 200 queries from `OEB_short_norm.parquet`:
   - Encodes the query with E5
   - Retrieves top-1 from the item-level index
   - Maps result to `parent_key`
   - Checks against ground truth
5. Reports parent-level Acc@1

Expected: ~98% (matching the published benchmark).

This confirms the existing index works for our Stage 1 needs without modification.

### 3. Confirm no adapter needed

Check whether the existing `DenseE5Searcher` from `src/retrievers/dense_e5.py` can be used directly as Stage 1 in the pipeline:

- Does `search(query, k=1)` return the `doc_id` we need?
- Can we map `doc_id → item_key → parent_key` from the existing artifacts?

If yes, document that no adapter or wrapper is needed — the pipeline (Sprint C1) will just use `DenseE5Searcher` directly.

If there's a gap (e.g., the searcher returns indices but we need external_ids), note what the pipeline integration will need to handle.

---

## Acceptance Criteria

- [ ] `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` updated with pivot decision and revised architecture
- [ ] `docs/RESEARCH_LOG.md` updated with Sprint 02 entry
- [ ] Verification script confirms ~98% parent Acc@1 on 200-query sample using item-level index
- [ ] Clear documentation of whether `DenseE5Searcher` can be used as-is or needs wrapping
- [ ] No existing files modified (only docs and new scripts)

---

## Out of Scope

- Deleting Sprint 02 artifacts (keep them as evidence)
- LLM or Ollama setup (Stage 2 — next sprint)
- Pipeline integration (Sprint C1)
- Full 16,590-query benchmark (Sprint C3)
