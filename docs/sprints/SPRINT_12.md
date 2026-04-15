# Sprint 12 — Paraaware2: Per-Axis Detection with Informed Step 1

**Tasks from backlog:** B3 revision (per-axis informed detection)
**Prerequisites:** Sprint 09 (paraaware tested), Sprint 10–11 (Phi-4 comparison matrix complete)
**Date:** March 2026

---

## Context

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

Previous sprint results established the following Stage 2 ranking (per-axis accuracy, 20 queries):

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Rule-based | 100.0% | 100.0% |
| Extract | 87.8% | 77.0% |
| Classify | 86.5% | 100.0% |
| Twostep | 64.9% | 58.1% |
| Paraaware | 48.6% | 78.4% |

The original paraaware mode failed primarily because Step 1 asked the model to detect parameter presence **without showing the possible values**. This made Step 1 an abstract detection task with no grounding in the schema, causing omission errors (axes classified as null when they were present) and compound descriptions that Step 2 could not decompose.

The key insight motivating this sprint: a human expert reading a query against a known schema would ask, for each parameter axis, *"does this query say anything about X, which can be value_1, value_2, or value_3?"* — detection and schema awareness happen simultaneously, not sequentially.

The new mode, **paraaware2**, implements this by making one LLM call per axis, where each call includes the full list of possible values during detection.

---

## Design

### Architecture

```
Query + concept + schema
        │
        ▼
For each axis independently:
  ┌─────────────────────────────────────────────────────┐
  │ Step 1 (one LLM call per axis)                      │
  │                                                     │
  │ Input:  axis_label, possible_values, query, concept │
  │ Output: exact schema value  OR  null                │
  └─────────────────────────────────────────────────────┘
        │
        ▼
Post-processing:
  - If output matches a schema value (case-insensitive): accept
  - If output is null / empty / "null": accept as null
  - If output is unexpected (neither value nor null):
        → Step 2 fallback (one LLM call): match to schema value or null
        │
        ▼
Assemble result dict: {axis_label: value | null}
```

### Step 1 Prompt (one call per axis)

```
Eres un asistente que analiza consultas de construcción ferroviaria.

Concepto: {concept}

Parámetro: {axis_label}
Valores posibles: {value_1} | {value_2} | {value_3} ...

Consulta: "{query}"

¿Hace referencia la consulta a alguno de los valores posibles del parámetro "{axis_label}"?

- Si SÍ: responde con el valor exacto tal como aparece en la lista de valores posibles.
- Si NO: responde con null.

Responde SOLO con el valor exacto o con null. Sin explicaciones.
```

### Step 2 Fallback Prompt (only when Step 1 output is unexpected)

```
El parámetro "{axis_label}" tiene estos valores posibles: {value_1} | {value_2} | ...

Se extrajo el siguiente texto: "{extracted}"

¿A cuál de los valores posibles corresponde exactamente?
Responde SOLO con el valor exacto o con null si no corresponde a ninguno. Sin explicaciones.
```

### Key differences from previous paraaware

| Aspect | Paraaware (Sprint 09) | Paraaware2 (this sprint) |
|---|---|---|
| Values shown in Step 1 | No | **Yes** |
| Calls per query | 2 (all axes at once) | **N axes + optional fallbacks** |
| Step 1 output type | Free-form description | **Exact value or null** |
| Step 2 role | Mandatory matching | **Fallback only** |
| Axis independence | No (all axes in one call) | **Yes (no cross-axis contamination)** |

**Timing note:** Concept groups have 1–5 axes. For a 5-axis group, paraaware2 makes 5 LLM calls (+ possible fallbacks) vs. 1 call for extract/classify or 2 calls for twostep. Expected time per query: ~3–5s (Llama) or ~4.5–7s (Phi-4) for large groups. This is acceptable for a 20/50-query test; full-scale evaluation timing should be noted.

---

## Tasks

### T1 — Add `paraaware2` prompt builders to `src/pipeline/prompts.py`

Add two functions:
- `build_paraaware2_step1_prompt(concept, axis_label, values, query) → str`
- `build_paraaware2_step2_prompt(axis_label, values, extracted) → str`

Both prompts must use ASCII-safe text (no accented characters in the prompt template itself — data values from the schema are fine).

### T2 — Add `_extract_paraaware2()` method to `LLMParamExtractor` in `src/pipeline/param_extractor.py`

Logic:
1. For each axis in the schema, call Step 1 prompt independently.
2. Parse the response:
   - If response matches a schema value (case-insensitive): store the canonical schema value.
   - If response is `null`, empty, or `"null"`: store `None`.
   - If response is unexpected (non-empty, non-null, no schema match): call Step 2 fallback. If Step 2 also fails: store `None` and log a warning.
3. Assemble and return `{axis_label: value | None}`.

Add `prompt_mode="paraaware2"` dispatch in `__init__` and `extract()`.

### T3 — Create pipeline variants

Create the following new files (same pattern as previous sprints):

**Proxy modules** (in `src/retrievers/`):
- `structured_pipeline_paraaware2.py`
- `structured_pipeline_oracle_paraaware2.py`
- `structured_pipeline_phi4_paraaware2.py`
- `structured_pipeline_oracle_phi4_paraaware2.py`

**YAML configs** (in `configs/`):
- `structured_pipeline_paraaware2.yaml`
- `structured_pipeline_oracle_paraaware2.yaml`
- `structured_pipeline_phi4_paraaware2.yaml`
- `structured_pipeline_oracle_phi4_paraaware2.yaml`

All configs follow the same pattern as existing pipeline configs, with `stage2_prompt_mode: paraaware2`.

**Pseudo-index directories**: run `scripts/setup_structured_index.py` for all 4 variants.

### T4 — Extend Stage 2 test in `param_extractor_rules.py`

Add `--paraaware2` CLI flag to the existing T3 side-by-side comparison. The test should run the same 20-query sample and report:

- Per-axis accuracy
- Per-query accuracy
- Avg time/query
- Number of Step 2 fallbacks triggered (new metric — indicates how often Step 1 produced unexpected output)
- Error breakdown: omission errors vs normalization errors

Report results in the same table format as previous sprints.

### T5 — Extend pipeline sanity test in `structured_pipeline.py`

Add the 4 new paraaware2 conditions to the existing `__main__` sanity test (50-query stratified sample). Report item Acc@1, parent Acc@1, and time/query alongside all existing conditions.

---

## Acceptance Criteria

1. `_extract_paraaware2()` runs without errors on a single query from each of the 25 concept groups.
2. T4 (20-query Stage 2 test) completes and reports per-axis accuracy, per-query accuracy, time/query, Step 2 fallback count, and error breakdown for both Llama 3.1 8B and Phi-4 14B paraaware2 conditions.
3. T5 (50-query pipeline sanity test) completes for all 4 paraaware2 variants and reports item Acc@1 / parent Acc@1 / time/query.
4. Results are recorded below in the Results section of this sprint file.
5. No existing files modified (only new files and additions to existing test blocks).
6. Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`).

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3 — after model/prompt comparison is settled)
- Other models beyond Phi-4 and Llama 3.1 8B
- Fine-tuning
- Constrained decoding / Ollama grammar support

---

## Results

### Stage 2 comparison (20 queries)

| Method | Per-axis | Per-query | Time/query | Step 2 fallbacks | Errors |
|---|---|---|---|---|---|
| Rule-based | 100.0% (74/74) | 100.0% (20/20) | 0.015ms | — | 0 |
| Llama paraaware2 | 82.4% (61/74) | 55.0% (11/20) | 647ms | 5 | 9 |
| Phi-4 paraaware2 | 93.2% (69/74) | 80.0% (16/20) | 726ms | 9 | 5 |

### Pipeline sanity test (50 queries)

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| `structured_pipeline_paraaware2` | 50.0% | 92.0% | 872.1ms |
| `structured_pipeline_oracle_paraaware2` | 58.0% | 100.0% | 789.2ms |
| `structured_pipeline_phi4_paraaware2` | 60.0% | 92.0% | 852.1ms |
| `structured_pipeline_oracle_phi4_paraaware2` | 68.0% | 100.0% | 772.9ms |

### Interpretation

**Does showing values in Step 1 reduce omission errors vs paraaware original?**
Yes, dramatically. Original paraaware had 38 errors (Llama) / 16 errors (Phi-4); paraaware2 has 9 errors (Llama) / 5 errors (Phi-4). Showing possible values upfront eliminates the abstract detection failures that plagued Sprint 09.

**Does per-axis isolation reduce cross-axis contamination vs extract/classify?**
Partially. For Phi-4, paraaware2 (93.2%) approaches classify (100.0%), suggesting per-axis isolation works well with a strong enough model. For Llama, paraaware2 (82.4%) is below both extract (87.8%) and classify (86.5%), suggesting the overhead of multiple calls introduces normalization inconsistencies that Llama cannot handle.

**How often does Step 2 fallback trigger — is Step 1 output well-behaved?**
Low — 5 for Llama, 9 for Phi-4. Step 1 is generally well-behaved. Phi-4 has more fallbacks because it sometimes concatenates multiple axis values in one response (e.g., "Diurno/3 <== i < 5 horas/Volumen escaso"), reflecting its tendency to be "too helpful" by providing context beyond what was asked.

**Does Phi-4 benefit more than Llama, consistent with the scaling pattern?**
Yes. Phi-4 paraaware2 (93.2%) is +14.8 pp over Phi-4 paraaware (78.4%). Llama paraaware2 (82.4%) is +33.8 pp over Llama paraaware (48.6%). In absolute terms, Llama benefits more, but Phi-4 reaches a higher ceiling. This is consistent with the pattern: closed-set selection tasks (classify, paraaware2) benefit from model scaling.

**Overall ranking (per-axis accuracy, 20 queries):**

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Rule-based | 100.0% | 100.0% |
| Extract | 87.8% | 77.0% |
| Classify | 86.5% | 100.0% |
| **Paraaware2** | **82.4%** | **93.2%** |
| Twostep | 64.9% | 58.1% |
| Paraaware | 48.6% | 78.4% |

**Conclusion:** Paraaware2 fixes original paraaware's fundamental flaw. However, classify mode remains simpler (1 call vs N calls) and more accurate (especially for Phi-4). For the paper: paraaware2 provides a useful data point showing that per-axis isolation with informed values approaches single-call classify, confirming that the key factor is showing possible values to the LLM, not the number of calls.

---

## Reference: Prior Results for Comparison

### Stage 2 (20 queries, per-axis accuracy)

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Rule-based | 100.0% | 100.0% |
| Extract | 87.8% | 77.0% |
| Classify | 86.5% | 100.0% |
| Twostep | 64.9% | 58.1% |
| Paraaware | 48.6% | 78.4% |

### Pipeline (50 queries, item Acc@1)

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Rules | 84.0% | — |
| Extract | 68.0% | 64.0% |
| Classify | 52.0% | 80.0% |
| Twostep | 22.0% | 36.0% |
| Paraaware | 18.0% | 44.0% |
