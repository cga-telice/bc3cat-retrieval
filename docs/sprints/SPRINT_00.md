# Sprint 00 — Branch Setup and Schema Extraction

**Tasks from backlog:** A1 (branch setup), A2 (schema extraction)
**Prerequisites:** None (first sprint)

---

## Context

This is the first sprint on the `structured-retrieval` branch. The branch has just been created from `main` and the context documents are already in place:

- `CLAUDE.md` at repo root — read this first for full project context
- `docs/RESEARCH_PROPOSAL.md` — research goals and motivation
- `docs/RESEARCH_PROTOCOL.md` — implementation roadmap and design decisions
- `docs/RESEARCH_LOG.md` — running log (has only the pre-sprint entry)

The existing codebase on `main` is a retrieval benchmark for the BC3CAT construction catalog. **Do not modify any existing files.** This sprint only adds new files.

---

## Objectives

### 1. Create the pipeline package

Create `src/pipeline/` with an empty `__init__.py`. This is where all new pipeline code will live.

### 2. Extract the concept schema

Write `src/pipeline/schema_extractor.py` that:

1. Loads `data/processed/OEB_long_norm.parquet`
2. For each unique `parent_key` that has leaf items (i.e., items with non-empty `parameters`):
   - Extracts the `concept` text (shared by all items in the group)
   - Extracts the parameter axes: for each axis key (A, B, C, ...), the axis label and the full set of distinct values across all items in the group
   - Collects all `item_key` values belonging to that group
3. Saves the result to `data/processed/OEB_concept_schema.json`

**Expected output format:**

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
    "num_items": 24
  },
  ...
}
```

**Important notes about the data:**

- The `parameters` column in the parquet is a dict (may be stored as string — check and parse if needed). Structure: `{"A": {"label": "TRABAJO", "values": [{"label": "a", "value": "Diurno"}]}, ...}`
- Each leaf item has exactly one value per axis (the `values` list has one element per axis for leaf items)
- Chapter-level rows (e.g., `item_key` ending in `#`) have empty parameters — skip these
- The `parent_key` for leaf items ends in `$` (e.g., `OEB030$`)
- Use axis `label` as the key in `axes` (e.g., "TRABAJO"), not the axis letter (e.g., "A")
- Values in `axes` should be the **sorted unique set** of values across all items in the group

### 3. Run the extraction and verify

Run the script and verify:

- Total number of concept groups (expected: ~25, but verify from the data)
- Each group has at least one axis and at least one item
- Spot-check 3 groups: verify axes/values match what's in the parquet
- Print a summary: group name, number of axes, number of items per group

---

## Acceptance Criteria

- [ ] `src/pipeline/__init__.py` exists (can be empty)
- [ ] `src/pipeline/schema_extractor.py` exists and is runnable
- [ ] `data/processed/OEB_concept_schema.json` is produced
- [ ] Schema has the expected number of concept groups
- [ ] Each group has: `concept` (string), `axes` (dict of label → sorted value list), `item_keys` (list), `num_items` (int)
- [ ] Spot-check of 3 groups passes (axes and values match parquet)
- [ ] Summary printed: group name, #axes, #items for all groups
- [ ] No existing files modified

---

## Out of Scope

- Building any index (that's Sprint 01+)
- Installing new dependencies (pandas, pyarrow are already in requirements.txt)
- Modifying existing code
- LLM or Ollama setup
