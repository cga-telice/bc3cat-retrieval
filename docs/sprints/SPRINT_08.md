# Sprint 08 — Two-Step LLM Extraction (Extract then Match)

**Tasks from backlog:** B3 revision (two-step approach)
**Prerequisites:** Sprint 07 complete (all three Stage 2 methods tested)

---

## Context

Sprint 07 results on 20 queries:

| Method | Per-axis | Per-query |
|---|---|---|
| Rules | 100.0% | 100.0% |
| LLM-extract | 87.8% | 70.0% |
| LLM-classify | 86.5% | 65.0% |

The two LLM prompt strategies fail in complementary ways:
- **Extract** understands the query and produces a value, but reformats it → normalization mismatch
- **Classify** is told to pick from the list, but becomes too conservative → returns null more often

The classification prompt made things worse because it combined two tasks in a single step: understand the query AND select the exact schema value. The LLM, being overly cautious about exact matching, defaults to null when uncertain.

**Solution: separate the two tasks into two LLM calls.**

- **Step 1 (Extract)**: Ask the LLM to freely extract what it understands from the query for each axis. No constraints on output format — the LLM describes what it found in natural language or its own formatting.
- **Step 2 (Match)**: Given the LLM's extraction AND the schema values, ask the LLM to match each extracted value to the closest schema value (or null if no match).

This way, Step 1 captures the LLM's understanding without the pressure of exact formatting, and Step 2 uses the LLM's reasoning to bridge the gap between the extracted text and the schema values. Neither step has to do both tasks at once.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Design the two-step prompts

Update `src/pipeline/prompts.py` to add two new functions:

```python
def build_twostep_extract_prompt(concept: str, axes: dict[str, list[str]], query: str) -> str:
    """
    Step 1: Free extraction. Ask the LLM what each axis's value is
    based on the query, in its own words. No formatting constraints.
    """
    ...

def build_twostep_match_prompt(concept: str, axes: dict[str, list[str]], 
                                extracted: dict[str, str | None]) -> str:
    """
    Step 2: Match extracted values to schema values. Given what Step 1 
    produced, select the closest schema value for each axis (or null).
    """
    ...
```

**Step 1 prompt** (Spanish):

```
Eres un asistente que analiza consultas de construcción ferroviaria.

Concepto: {concept}

La consulta describe un elemento con estos parámetros:
{axis_label_1}
{axis_label_2}
...

Consulta: "{query}"

Para cada parámetro, describe brevemente qué valor indica la consulta.
Si la consulta no menciona un parámetro, indica "no especificado".

Responde con un JSON con las claves de los parámetros.

Respuesta:
```

Note: Step 1 does NOT show the allowed values. The LLM describes freely what it sees.

**Step 2 prompt** (Spanish):

```
Eres un asistente que asocia valores extraídos con los valores oficiales de un catálogo.

Concepto: {concept}

Valores extraídos de una consulta:
{axis_label_1}: {extracted_value_1}
{axis_label_2}: {extracted_value_2}
...

Valores permitidos en el catálogo:
{axis_label_1}: {value_1_a} | {value_1_b} | ...
{axis_label_2}: {value_2_a} | {value_2_b} | ...
...

Para cada parámetro, indica cuál de los valores del catálogo corresponde
al valor extraído. Responde con el valor exacto del catálogo o null si
no hay correspondencia.

Responde SOLO con un JSON con exactamente las claves indicadas.

Respuesta:
```

Note: Step 2 sees both the freely extracted values AND the schema values. It maps between them.

### 2. Add two-step mode to LLMParamExtractor

Update `src/pipeline/param_extractor.py` to support the two-step mode:

```python
class LLMParamExtractor:
    def __init__(self, ..., prompt_mode: str = "twostep"):
        # prompt_mode: "extract", "classify", or "twostep"
        ...

    def _extract_twostep(self, parent_key: str, query: str) -> dict[str, str | None]:
        """
        Two-step extraction:
        1. Call LLM with Step 1 prompt → get free-form extracted values
        2. Parse Step 1 response
        3. Call LLM with Step 2 prompt (extracted values + schema) → get matched values
        4. Parse Step 2 response
        5. Validate: each value must be in schema or null
        """
        ...
```

**Error handling for two-step:**
- If Step 1 fails (malformed JSON), retry once. If still fails, return all-null.
- If Step 2 fails (malformed JSON), retry once. If still fails, use Step 1's raw output and attempt exact string matching against schema values (graceful degradation to extract mode).
- If Step 2 returns a value not in the schema, treat as null for that axis.
- Log both Step 1 and Step 2 responses for debugging.

### 3. Add configs for two-step pipeline

Create:
- **`configs/structured_pipeline_twostep.yaml`** — E5 + LLM (twostep) + catalog
- **`configs/structured_pipeline_oracle_twostep.yaml`** — Oracle + LLM (twostep) + catalog

With proxy modules and pseudo-index dirs as in previous sprints.

### 4. Test on the same 20 queries (four-way comparison)

Run all four Stage 2 methods on the same 20 queries:

1. **Rules** — baseline
2. **LLM-extract** — Sprint 04 original
3. **LLM-classify** — Sprint 07
4. **LLM-twostep** — new

Report for each:
- Per-axis accuracy
- Per-query accuracy
- Normalization errors (values that are semantically correct but lexically wrong)
- Omission errors (null when ground truth has a value)
- Average time per query

### 5. Run 50-query pipeline sanity test

Run all pipeline conditions including twostep:

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% |
| `structured_pipeline` (extract) | 68.0% | 92.0% |
| `structured_pipeline_classify` | 52.0% | 92.0% |
| `structured_pipeline_twostep` | ? | ? |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% |
| `structured_pipeline_oracle` (extract) | 76.0% | 100.0% |
| `structured_pipeline_oracle_classify` | 60.0% | 100.0% |
| `structured_pipeline_oracle_twostep` | ? | ? |

---

## Acceptance Criteria

- [ ] `src/pipeline/prompts.py` updated with `build_twostep_extract_prompt()` and `build_twostep_match_prompt()`
- [ ] `src/pipeline/param_extractor.py` updated with `prompt_mode="twostep"` support
- [ ] `configs/structured_pipeline_twostep.yaml` exists
- [ ] `configs/structured_pipeline_oracle_twostep.yaml` exists
- [ ] Proxy modules and pseudo-index dirs created for twostep variants
- [ ] 20-query four-way comparison: all methods tested, accuracy reported
- [ ] Error breakdown: normalization errors vs. omission errors per method
- [ ] 50-query pipeline test: twostep conditions run, results compared
- [ ] Average time per query for twostep reported (expected: ~2× extract time)
- [ ] No breaking changes to existing code
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3)
- Constrained decoding / Ollama grammar support
- Additional LLM models
- Prompt optimization beyond the four variants
