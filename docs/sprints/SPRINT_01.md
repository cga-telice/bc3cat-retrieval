# Sprint 01 — Deterministic Catalog Lookup (Stage 3)

**Tasks from backlog:** B2
**Prerequisites:** Sprint 00 complete (schema JSON exists)

---

## Context

Sprint 00 produced `data/processed/OEB_concept_schema.json` with 25 concept groups. Each group has:
- `concept`: human-readable name
- `axes`: dict of `{axis_label: [sorted unique values]}`
- `item_keys`: list of all item keys in the group
- `num_items`: count

This sprint builds Stage 3 of the pipeline — the deterministic lookup that maps extracted parameters to a specific item. This component has no external dependencies (no GPU, no LLM) and can be fully tested with synthetic inputs.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Build the catalog lookup module

Create `src/pipeline/catalog_lookup.py` that provides:

```python
class CatalogLookup:
    def __init__(self, schema_path: str, parquet_path: str):
        """Load the concept schema and build the lookup structures."""
        ...

    def lookup(self, parent_key: str, extracted_params: dict) -> list[str]:
        """
        Given a parent_key and a dict of {axis_label: value | None},
        return matching item_key(s).
        
        - All axes resolved → single item_key (list of 1)
        - Some axes None → sub-group of matching items
        - All axes None → all items in the concept group
        - Unknown parent_key → empty list
        - Unknown value for an axis → treat as None for that axis
        """
        ...
    
    def get_schema(self, parent_key: str) -> dict | None:
        """Return the schema for a concept group (axes, values), or None."""
        ...
    
    def get_all_parent_keys(self) -> list[str]:
        """Return all known parent_keys."""
        ...
```

**Implementation notes:**

- The lookup needs to match extracted parameter values to specific items. The schema JSON has the *axes and their possible values per group*, but it does NOT have the mapping from a specific parameter combination to a specific `item_key`. That mapping must be built from the parquet.
- Load the parquet (`OEB_long_norm.parquet` or `OEB_long_feats.parquet` — either works) and for each concept group, build an index: `{(axis_A_value, axis_B_value, ...): item_key}`.
- The `parameters` column in the parquet has the structure: `{"A": {"label": "TRABAJO", "values": [{"label": "a", "value": "Diurno"}]}, ...}`. Parse each item's parameters to extract its specific value per axis.
- The order of axes must be consistent (use the axis letter keys A, B, C, ... sorted alphabetically).
- When `extracted_params` has `None` for an axis, match all values on that axis.

### 2. Test the lookup

Write tests (can be in a `if __name__ == "__main__"` block or a separate test script) that verify:

1. **Full match**: provide all axis values for a known item → returns exactly that item_key
2. **Partial match (one null)**: provide all axes except one → returns the correct sub-group size
3. **All null**: provide only parent_key with all None → returns all items in group
4. **Unknown parent_key**: → returns empty list
5. **Unknown value for an axis**: e.g., a value not in the schema → treat as None for that axis, log a warning
6. **Concept groups of different sizes**: test on a small group (e.g., OEB160$ with 3 items) and a large group (e.g., OEB030$ with 6,336 items)

Print test results clearly.

---

## Acceptance Criteria

- [ ] `src/pipeline/catalog_lookup.py` exists and is importable
- [ ] `CatalogLookup` loads from schema JSON + parquet without errors
- [ ] Full match returns exactly 1 item_key, verified correct
- [ ] Partial match returns correct sub-group size
- [ ] All-null returns full concept group
- [ ] Unknown parent_key returns empty list
- [ ] Unknown axis value handled gracefully (warning, not crash)
- [ ] Tested on at least one small and one large concept group
- [ ] No existing files modified

---

## Out of Scope

- Building any index (Stage 1)
- LLM or Ollama setup (Stage 2)
- Pipeline integration (that's C1)
- Performance optimization (correctness first)
