# Sprint D1 — Error Analysis

**Prerequisites:** Sprint 13 complete (full evaluation on 16,590 queries, all 6 Tier 1 conditions)
**Purpose:** Understand *where* and *why* the structured pipeline fails, producing analysis and artifacts for the paper's error analysis section.

---

## Context

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

Sprint 13 produced the full evaluation results:

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| Rules (pipeline) | 90.3% | ~98% |
| Rules (oracle) | 91.4% | 100% |
| Phi-4 classify (pipeline) | 87.7% | ~98% |
| Phi-4 classify (oracle) | 88.6% | 100% |
| Llama extract (pipeline) | 80.9% | ~98% |
| Llama extract (oracle) | 82.1% | 100% |

The pipeline → oracle gap is only ~1.1 pp across all conditions, so Stage 1 is not the bottleneck. The remaining ~9.7% errors (rules) to ~17.9% errors (Llama extract) come from Stage 2 parameter extraction. This sprint digs into those errors.

**Existing outputs available for analysis:**
- `runs/<method>/results_perquery_summary.csv` — per-query accuracy flags (item_hit, parent_hit)
- `runs/<method>/results_top100.jsonl.gz` — per-query ranked results
- `runs/<method>/metrics_dual.json` — aggregate metrics with has_numbers / no_numbers splits
- `data/processed/OEB_concept_schema.json` — 25 concept groups with axes and values
- `runs/structured_eval_queries.json` — the 16,590 query IDs used in Sprint 13
- The query parquet files with ground truth item_key, parent_key, and text

---

## Objectives

### 1. Build the error analysis script

Create `scripts/error_analysis.py` that loads Sprint 13 results and produces a structured error report. For each Tier 1 condition, classify every failed query (item Acc@1 = 0) into one of these error categories:

**Stage 1 errors** (pipeline conditions only — oracle has none by definition):
- **E1-WRONG_CONCEPT**: Stage 1 retrieved the wrong concept group (wrong parent_key). The query never had a chance because the schema was wrong.

**Stage 2 errors** (the interesting ones — present in both pipeline and oracle):
- **E2-PARTIAL_EXTRACT**: Stage 2 extracted some axes correctly but left others as null (or wrong), resulting in a sub-group match rather than a unique item. The returned item list includes the correct item, but Acc@1 counts it as a miss.
- **E2-WRONG_VALUE**: Stage 2 extracted a wrong value for at least one axis (not null, but incorrect), leading to a different item entirely.
- **E2-ALL_NULL**: Stage 2 returned null for all axes, returning the entire concept group.

**Stage 3 / edge case errors:**
- **E3-SCHEMA_MISMATCH**: The query's ground truth item has parameter values that don't match any schema value (data inconsistency). Should be rare or zero.

To classify errors, the script needs to:
1. Load the per-query results from `results_perquery_summary.csv` or `results_top100.jsonl.gz`
2. For each failed query, determine the predicted parent_key (from Stage 1 output)
3. Compare predicted parent_key to ground-truth parent_key → E1 or E2
4. For E2 errors, re-run Stage 2 extraction (or load cached extraction results if Sprint 13's script saved them) to get the extracted parameters, then compare axis-by-axis to ground truth
5. Classify the extraction error as PARTIAL, WRONG_VALUE, or ALL_NULL

**Important: Check what Sprint 13's `run_full_eval.py` saved.** If it saved intermediate results (extracted parameters per query, Stage 1 predictions), use those. If not, the analysis script may need to re-run extraction for the ~1,600 failed queries (rules) or load them from the JSONL results.

### 2. Error distribution tables

Produce these tables for the paper:

**Table A — Error category breakdown by condition:**

| Error type | Rules (pipeline) | Rules (oracle) | Phi-4 classify (pipeline) | Phi-4 classify (oracle) | Llama extract (pipeline) | Llama extract (oracle) |
|---|---|---|---|---|---|---|
| E1-WRONG_CONCEPT | ? | 0 | ? | 0 | ? | 0 |
| E2-PARTIAL_EXTRACT | ? | ? | ? | ? | ? | ? |
| E2-WRONG_VALUE | ? | ? | ? | ? | ? | ? |
| E2-ALL_NULL | ? | ? | ? | ? | ? | ? |
| E3-SCHEMA_MISMATCH | ? | ? | ? | ? | ? | ? |
| **Total errors** | ~1,610 | ~1,430 | ~2,040 | ~1,890 | ~3,170 | ~2,970 |

**Table B — Errors by concept group (top 10 hardest groups):**

For the rules (pipeline) condition, show which concept groups contribute the most errors:

| parent_key | concept (truncated) | num_items | num_axes | total_queries | errors | error_rate |
|---|---|---|---|---|---|---|
| OEB030$ | CANALIZACIÓN CON TUBOS... | 6336 | 5 | ? | ? | ? |
| ... | | | | | | |

This reveals whether errors are concentrated in a few complex groups or spread uniformly.

**Table C — Errors by axis (for rules condition):**

For the rules (oracle) condition, which axes are hardest to extract:

| axis_label | total_occurrences | correct | wrong_value | null_when_present | accuracy |
|---|---|---|---|---|---|
| TRABAJO | ? | ? | ? | ? | ? |
| TIPO DE TERRENO | ? | ? | ? | ? | ? |
| ... | | | | | |

### 3. has_numbers vs no_numbers breakdown

The `metrics_dual.json` files already have this split, but dig deeper:

- What is the error rate for queries *with* numeric parameters vs *without*?
- For numeric parameters specifically (e.g., "Nº TUBOS", diameters, lengths), what is the per-axis extraction accuracy?
- Are rules better than LLMs at numeric extraction, or vice versa?

This is the key explanatory finding: the structured pipeline should excel on numeric parameters because they're the ones embeddings collapse most.

### 4. Qualitative error examples

For each error type, extract 3–5 representative examples showing:
- The query text (in Spanish)
- The ground truth item and its parameters
- What Stage 2 extracted
- Why the error occurred (brief analysis)

Focus on errors that illustrate patterns — e.g., systematic normalization failures (the LLM writes "diurno" but the schema has "Diurno"), schema ambiguity (the query mentions a value that maps to multiple axes), or queries where the parameter is genuinely absent from the text.

Save these examples to `analysis/error_examples.json` (structured) and produce a readable summary in `analysis/error_analysis_summary.md`.

### 5. Rules vs LLM error comparison

For the oracle conditions (same Stage 1, different Stage 2), compare:

- Queries that rules get right but LLMs get wrong (and vice versa)
- Are there systematic categories where LLMs add value over rules?
- What fraction of LLM errors are normalization issues (correct concept but wrong surface form)?

This directly supports the paper's discussion about when LLMs are worth the cost.

### 6. Output artifacts

Produce the following files in `analysis/`:

```
analysis/
  error_analysis_summary.md     — Narrative summary with all tables (paper-ready)
  error_distribution.csv        — Table A in CSV format
  errors_by_concept_group.csv   — Table B
  errors_by_axis.csv            — Table C
  error_examples.json           — Qualitative examples (structured)
  rules_vs_llm_comparison.csv   — Queries where rules and LLMs disagree
```

### 7. Document

Update `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` and `docs/RESEARCH_LOG.md` with:
- Key error analysis findings
- Pointers to the analysis artifacts
- Any surprises or insights that should shape the paper's discussion

---

## Acceptance Criteria

- [ ] `scripts/error_analysis.py` exists and runs on Sprint 13 outputs
- [ ] Error classification covers all failed queries across 6 Tier 1 conditions
- [ ] Table A (error category breakdown) produced for all 6 conditions
- [ ] Table B (errors by concept group) produced for rules pipeline
- [ ] Table C (errors by axis) produced for rules oracle
- [ ] has_numbers vs no_numbers analysis with per-axis numeric accuracy
- [ ] 3–5 qualitative error examples per error type saved to `analysis/error_examples.json`
- [ ] Rules vs LLM comparison: queries where they disagree, with analysis
- [ ] `analysis/error_analysis_summary.md` contains a narrative summary with all tables
- [ ] No existing files modified (except documentation updates)
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Important Notes

- **No GPU or Ollama needed for this sprint** — it's pure analysis of existing outputs. If extracted parameters aren't cached, the script may need to re-derive them from the per-query results, but it should not need to re-run the LLM.
- **The `results_perquery_summary.csv` is the key input.** Check its exact columns first — it likely has `query_id`, `item_hit`, `parent_hit`, and possibly `predicted_item`, `predicted_parent` fields.
- **Existing eval infrastructure:** `src/utils/evaluation.py` and the eval notebooks may have helper functions for loading results. Reuse them.
- **Focus on actionable insights for the paper.** The error analysis should answer: "Why does the pipeline top out at 90.3% instead of approaching 97.4% (BM25)?" and "What would it take to close the gap?"

---

## Out of Scope

- Paper draft (Sprint D2)
- Figures and plots (Sprint D3 — though this sprint's tables will feed into D3)
- Re-running any pipeline conditions
- Running analysis on Tier 2 conditions (50-query samples)
