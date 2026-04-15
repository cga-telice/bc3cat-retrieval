# Sprint 05 — Rule-Based Parameter Extractor (Stage 2 Baseline)

**Tasks from backlog:** B4
**Prerequisites:** Sprint 00 (schema JSON), Sprint 01 (catalog lookup for comparison)

---

## Context

Sprint 04 built the LLM parameter extractor (Llama 3.1 8B), achieving 87.8% per-axis accuracy and 70% per-query accuracy on a 20-query sample. This sprint builds the rule-based baseline that answers: **how much does the LLM add over simple string matching?**

If the rule-based extractor gets close to 87.8% per-axis, the LLM isn't earning its complexity. If it's significantly worse, the LLM extraction is justified.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Create the rule-based parameter extractor

Create `src/pipeline/param_extractor_rules.py`:

```python
class RuleBasedParamExtractor:
    def __init__(self, schema_path: str):
        """Load schema."""
        ...

    def extract(self, parent_key: str, query: str) -> dict[str, str | None]:
        """
        Extract parameter values from a query using string matching.
        
        Returns:
            {axis_label: extracted_value | None} for each axis in the schema
        """
        ...

    def extract_batch(self, items: list[tuple[str, str]]) -> list[dict[str, str | None]]:
        """Batch extraction. Should be fast (no LLM calls)."""
        ...
```

**The interface must match `LLMParamExtractor`** — same method signatures, same input/output format. This way the pipeline (Sprint C1) can swap extractors without code changes.

### 2. Matching strategy

The extractor should try these approaches, from most to least specific:

1. **Exact substring match**: Check if any of the schema's allowed values for each axis appear as a substring in the query (case-insensitive, accent-normalized). For example, if the axis "TIPO DE TERRENO" has values ["Sin clasificar", "Bajo vías", "Rocoso"], check if any of these strings appear in the query.

2. **Numeric matching**: For axes whose values are numeric strings (e.g., "1", "2", "3" for "Nº TUBOS"), look for those numbers in the query. Be careful with false positives — a "2" might appear in a date or a different numeric context. Consider matching patterns like "2 tubos" or digits adjacent to axis-related keywords.

3. **Keyword/synonym matching** (optional, if time permits): For common axes like "TRABAJO" with values ["Diurno", "Nocturno"], also match synonyms or related terms (e.g., "noche" → "Nocturno", "día" → "Diurno"). Keep this minimal — a handful of hardcoded mappings at most.

**Important considerations:**
- Normalize both query and values: lowercase, strip accents (the repo already has `src/utils/text_processing.py` with accent normalization — reuse it)
- Handle ambiguity: if multiple values for the same axis match, return None for that axis (ambiguous = unresolved)
- If no value matches for an axis, return None
- This should be fast — no external calls, just string operations

### 3. Test and compare with LLM

Run the **same 20 queries** from Sprint 04's batch test. For each query, report:
- Rule-based extracted params vs. LLM extracted params vs. ground truth
- Per-axis accuracy (rule-based vs. LLM)
- Per-query accuracy (rule-based vs. LLM)

Print a side-by-side comparison table.

Also report timing: rule-based should be orders of magnitude faster than 585ms/query.

---

## Acceptance Criteria

- [ ] `src/pipeline/param_extractor_rules.py` exists and is importable
- [ ] `RuleBasedParamExtractor` has the same interface as `LLMParamExtractor` (`extract`, `extract_batch`)
- [ ] Tested on the same 20 queries as Sprint 04
- [ ] Side-by-side comparison printed: rule-based vs. LLM vs. ground truth
- [ ] Per-axis and per-query accuracy reported for both extractors
- [ ] Timing reported for rule-based (expected: <1ms/query)
- [ ] No existing files modified
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Pipeline integration (C1)
- Full 16,590-query evaluation (C3)
- Extensive synonym dictionaries — keep it simple
- Modifying the LLM extractor
