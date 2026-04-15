# Sprint 07 — LLM Classification Prompt (Stage 2 Revision)

**Tasks from backlog:** B3 revision (prompt redesign)
**Prerequisites:** Sprint 04 (LLM extractor), Sprint 06 (pipeline integration)

---

## Context

Sprint 04's LLM extractor achieved 87.8% per-axis accuracy vs. the rule-based extractor's 100% (Sprint 05). The LLM errors were all **output normalization failures** — the LLM understood the query correctly but reformatted values: `1,10 m` → `1.10`, `3"` → `3`, etc. The extracted values didn't match the schema's exact strings, causing lookup failures.

The root cause: the original prompt asks the LLM to **extract** parameter values from the query. This is the wrong task. The LLM should **classify** each parameter axis into one of the predefined schema values. The difference:

- **Extraction**: "What value does the query mention for this axis?" → LLM copies/paraphrases from query → lexical mismatch
- **Classification**: "Which of these specific schema values does the query correspond to?" → LLM selects from closed set → guaranteed valid output

This distinction matters most for real-world queries. A field engineer might write "canalización de UN conducto" instead of "1", or "por la noche" instead of "Nocturno". The rule-based extractor would fail on these; the classification LLM can map "UN" → "1" and "por la noche" → "Nocturno".

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Design the classification prompt

Update `src/pipeline/prompts.py` to add a new function:

```python
def build_classification_prompt(concept: str, axes: dict[str, list[str]], query: str) -> str:
    """
    Build a classification prompt that asks the LLM to SELECT from schema values
    rather than extract from the query.
    """
    ...
```

The prompt should make it unmistakably clear that:
- The LLM must respond with **exactly one of the listed values** or `null` per axis
- The LLM must NOT rephrase, reformat, translate, or abbreviate the values
- The LLM should use its understanding of the query to determine which schema value is the best match, even if the query uses different phrasing

Proposed prompt (in Spanish):

```
Eres un asistente que clasifica consultas de construcción ferroviaria según los parámetros de un concepto.

Concepto: {concept}

Para cada parámetro, indica cuál de los valores permitidos corresponde a la consulta.
Responde ÚNICAMENTE con uno de los valores exactos listados o null.
NO modifiques, reformatees ni parafrasees los valores.

Parámetros y valores permitidos:
{axis_label_1}: {value_1_a} | {value_1_b} | ...
{axis_label_2}: {value_2_a} | {value_2_b} | ...
...

Consulta: "{query}"

Responde SOLO con un JSON con exactamente las claves indicadas.
Cada valor debe ser uno de los listados arriba (copiado exactamente) o null.

Respuesta:
```

**Key changes from the original prompt:**
- "clasifica" instead of "extrae"
- "cuál de los valores permitidos corresponde" instead of "extrae el valor"
- Values separated with `|` to emphasize they are distinct options to choose from
- Explicit instruction: "NO modifiques, reformatees ni parafrasees los valores"
- "copiado exactamente" — copy exactly

Keep the original `build_extraction_prompt()` unchanged — we need it for comparison.

### 2. Add classification mode to LLMParamExtractor

Update `src/pipeline/param_extractor.py` to support both prompt modes:

```python
class LLMParamExtractor:
    def __init__(self, schema_path: str, ollama_base_url: str = "http://ollama:11434",
                 model: str = "llama3.1:8b", temperature: float = 0.0,
                 prompt_mode: str = "classify"):  # NEW: "extract" or "classify"
        ...
```

- `prompt_mode="extract"` → uses original `build_extraction_prompt()` (Sprint 04 behavior)
- `prompt_mode="classify"` → uses new `build_classification_prompt()`
- Default to `"classify"` (the improved version)

### 3. Add configs for classification pipeline

Create or update configs to support the classification variant:

**`configs/structured_pipeline_classify.yaml`** — E5 + LLM (classify mode) + catalog
**`configs/structured_pipeline_oracle_classify.yaml`** — Oracle + LLM (classify mode) + catalog

The existing `structured_pipeline.yaml` (LLM extract mode) should remain unchanged for comparison.

### 4. Test all three Stage 2 methods on the same 20 queries

Run the same 20 queries from Sprint 04/05 with all three Stage 2 methods:

1. **Rules** — `RuleBasedParamExtractor` (Sprint 05 baseline)
2. **LLM-extract** — `LLMParamExtractor(prompt_mode="extract")` (Sprint 04 behavior)
3. **LLM-classify** — `LLMParamExtractor(prompt_mode="classify")` (new)

For each query, print a side-by-side comparison: rules vs. LLM-extract vs. LLM-classify vs. ground truth.

Report:
- Per-axis accuracy for all three methods
- Per-query accuracy for all three methods
- Number of normalization errors in LLM-extract vs. LLM-classify
- Average time per query for all three

Expected outcome: LLM-classify should close the gap with rules (eliminating normalization errors) while maintaining the LLM's semantic understanding advantage.

### 5. Run 50-query pipeline sanity test with classification

Run the `structured_pipeline_classify` and `structured_pipeline_oracle_classify` conditions on 50 queries (same as Sprint 06). Compare against the Sprint 06 rules results:

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% |
| `structured_pipeline_classify` | ? | ? |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% |
| `structured_pipeline_oracle_classify` | ? | ? |

---

## Acceptance Criteria

- [ ] `src/pipeline/prompts.py` updated with `build_classification_prompt()` (original `build_extraction_prompt()` preserved)
- [ ] `src/pipeline/param_extractor.py` updated with `prompt_mode` parameter
- [ ] `configs/structured_pipeline_classify.yaml` exists
- [ ] `configs/structured_pipeline_oracle_classify.yaml` exists
- [ ] 20-query comparison: all three methods tested side-by-side, accuracy reported
- [ ] LLM-classify normalization errors < LLM-extract normalization errors
- [ ] 50-query pipeline test: classify conditions run, results compared with Sprint 06
- [ ] No breaking changes to existing code (extract mode still works as before)
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3)
- Constrained decoding (would require Ollama grammar support — future work)
- Prompt optimization beyond the extract/classify distinction
- Additional LLM models
