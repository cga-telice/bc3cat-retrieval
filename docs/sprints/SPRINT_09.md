# Sprint 09 — Parameter-Aware Two-Step LLM Extraction

**Tasks from backlog:** B3 revision (parameter-aware two-step)
**Prerequisites:** Sprint 08 complete (previous two-step tested and documented)

---

## Context

All LLM prompt strategies tested so far have underperformed the rule-based extractor on catalog-generated queries:

| Method | Oracle item Acc@1 | Pipeline item Acc@1 |
|---|---|---|
| Rules | 92.0% | 84.0% |
| LLM-extract | 76.0% | 68.0% |
| LLM-classify | 60.0% | 52.0% |
| LLM-twostep (Sprint 08) | 26.0% | 22.0% |

Sprint 08's two-step failed because Step 1 produced vague free-form descriptions that didn't map cleanly to schema values in Step 2. The approach was too unconstrained.

**New approach: parameter-aware two-step.**

The key difference is that Step 1 is explicitly **parameter-aware** — the LLM is told what parameters to look for and must decide, for each one, whether the query contains relevant information and what that information is. This is a comprehension task ("does the query say anything about terrain type?"), not an open extraction task ("what values do you see?").

Step 2 then receives focused, parameter-specific extractions and maps them to schema values. This is a simpler matching task because the input is already structured around the right axes.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Design the parameter-aware two-step prompts

Update `src/pipeline/prompts.py` with two new functions:

```python
def build_paraaware_extract_prompt(concept: str, axes: dict[str, list[str]], query: str) -> str:
    """
    Step 1: Parameter-aware extraction.
    For each axis, ask the LLM if the query contains information related to
    that parameter, and if so, extract the relevant value in its own words.
    """
    ...

def build_paraaware_match_prompt(concept: str, axes: dict[str, list[str]], 
                                  extracted: dict[str, str | None]) -> str:
    """
    Step 2: Map extracted values to schema values.
    Given each axis's extracted value from Step 1, select the closest
    matching schema value or null.
    """
    ...
```

**Step 1 prompt** (Spanish):

```
Eres un asistente que analiza consultas de construcción ferroviaria.

Concepto: {concept}

Analiza la siguiente consulta y determina si contiene información sobre 
cada uno de los parámetros indicados.

Parámetros a buscar:
- {axis_label_1}
- {axis_label_2}
...

Consulta: "{query}"

Para cada parámetro:
- Si la consulta contiene información relevante, indica qué dice la consulta 
  sobre ese parámetro (en tus propias palabras, brevemente).
- Si la consulta NO contiene información sobre ese parámetro, indica null.

Responde SOLO con un JSON con las claves de los parámetros.

Respuesta:
```

Key aspects of Step 1:
- Lists the parameter names so the LLM knows exactly what to look for
- Does NOT show the allowed values — the LLM describes what it finds freely
- Explicitly asks the LLM to determine IF the query contains relevant information (detection) before extracting
- The LLM uses its own words — no formatting pressure

**Step 2 prompt** (Spanish):

```
Eres un asistente que asocia valores extraídos con valores de un catálogo oficial.

Concepto: {concept}

De una consulta se han extraído los siguientes valores para cada parámetro:
{axis_label_1}: {extracted_value_1}
{axis_label_2}: {extracted_value_2}
...

Los valores oficiales del catálogo para cada parámetro son:
{axis_label_1}: {value_1_a} | {value_1_b} | ...
{axis_label_2}: {value_2_a} | {value_2_b} | ...
...

Para cada parámetro, indica cuál de los valores oficiales corresponde al 
valor extraído. Debes responder con el valor exacto del catálogo, copiado 
tal cual, o null si el valor extraído no corresponde a ninguno.

Responde SOLO con un JSON con las claves de los parámetros.

Respuesta:
```

Key aspects of Step 2:
- Shows both the extracted values AND the schema values side by side
- Asks to match — not to extract, not to understand, just to map
- Explicitly says "copiado tal cual" (copied exactly as-is)
- If Step 1 returned null for an axis, Step 2 should also return null (no need to process)

### 2. Add parameter-aware mode to LLMParamExtractor

Update `src/pipeline/param_extractor.py`:

```python
class LLMParamExtractor:
    def __init__(self, ..., prompt_mode: str = "paraaware"):
        # prompt_mode: "extract", "classify", "twostep", or "paraaware"
        ...

    def _extract_paraaware(self, parent_key: str, query: str) -> dict[str, str | None]:
        """
        Parameter-aware two-step:
        1. Call LLM with parameter-aware extract prompt
           → for each axis: free-form description or null
        2. Filter out null axes (skip them in Step 2)
        3. Call LLM with match prompt (only for non-null axes)
           → for each axis: exact schema value or null
        4. Validate: each value must be in schema or null
        """
        ...
```

**Optimization for Step 2:** If Step 1 returns null for ALL axes, skip Step 2 entirely and return all-null. If Step 1 returns non-null for only some axes, Step 2 only needs to process those axes (include only non-null axes in the Step 2 prompt). This reduces the matching task and avoids confusing the LLM with axes that have no extracted value.

**Error handling:**
- Step 1 failure: retry once, then return all-null
- Step 2 failure: retry once, then fall back to attempting exact string matching of Step 1's raw output against schema values
- Step 2 value not in schema: treat as null
- Log both Step 1 and Step 2 raw responses

### 3. Add configs and infrastructure

Create:
- **`configs/structured_pipeline_paraaware.yaml`** — E5 + LLM (paraaware) + catalog
- **`configs/structured_pipeline_oracle_paraaware.yaml`** — Oracle + LLM (paraaware) + catalog
- Proxy modules and pseudo-index dirs as in previous sprints

### 4. Test on the same 20 queries (five-way comparison)

Run all five Stage 2 methods:

1. **Rules** — baseline (100% / 100%)
2. **LLM-extract** — Sprint 04 (87.8% / 70.0%)
3. **LLM-classify** — Sprint 07 (86.5% / 65.0%)
4. **LLM-twostep** — Sprint 08 (worst performer)
5. **LLM-paraaware** — new

Report for each:
- Per-axis accuracy
- Per-query accuracy
- Error breakdown: normalization errors vs. omission errors
- Average time per query

### 5. Run 50-query pipeline sanity test

Add paraaware results to the full comparison table:

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% |
| `structured_pipeline` (extract) | 68.0% | 92.0% |
| `structured_pipeline_classify` | 52.0% | 92.0% |
| `structured_pipeline_twostep` | 22.0% | 92.0% |
| `structured_pipeline_paraaware` | ? | ? |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% |
| `structured_pipeline_oracle` (extract) | 76.0% | 100.0% |
| `structured_pipeline_oracle_classify` | 60.0% | 100.0% |
| `structured_pipeline_oracle_twostep` | 26.0% | 100.0% |
| `structured_pipeline_oracle_paraaware` | ? | ? |

---

## Acceptance Criteria

- [ ] `src/pipeline/prompts.py` updated with `build_paraaware_extract_prompt()` and `build_paraaware_match_prompt()`
- [ ] `src/pipeline/param_extractor.py` updated with `prompt_mode="paraaware"` support
- [ ] Step 2 optimization: null axes from Step 1 are skipped in Step 2 prompt
- [ ] `configs/structured_pipeline_paraaware.yaml` exists
- [ ] `configs/structured_pipeline_oracle_paraaware.yaml` exists
- [ ] Proxy modules and pseudo-index dirs created
- [ ] 20-query five-way comparison: all methods tested, accuracy and error breakdown reported
- [ ] 50-query pipeline test: paraaware conditions run, results compared
- [ ] Average time per query reported
- [ ] No breaking changes to existing code
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3 — next if results are satisfactory)
- Constrained decoding / Ollama grammar support
- Additional LLM models
- Further prompt variants beyond paraaware
