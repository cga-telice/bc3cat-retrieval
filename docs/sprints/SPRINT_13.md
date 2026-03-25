# Sprint 13 — Full Evaluation Run (C3)

**Tasks from backlog:** C3 (full evaluation on 16,590 queries)
**Prerequisites:** All pipeline variants built and sanity-tested (Sprints 00–12)

---

## Context

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

Twelve sprints of development and experimentation have produced:
- 3 pipeline stages (E5 retrieval → parameter extraction → catalog lookup)
- 2 models (Llama 3.1 8B, Phi-4 14B)
- 6 prompt strategies (extract, classify, twostep, paraaware, paraaware2, rules)
- 22 pipeline variants (11 conditions × pipeline/oracle)

The complete 50-query ranking (pipeline item Acc@1):

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Rules | 84.0% | — |
| Classify | 52.0% | 80.0% |
| Extract | 68.0% | 64.0% |
| Paraaware2 | 50.0% | 60.0% |
| Paraaware | 18.0% | 44.0% |
| Twostep | 22.0% | 36.0% |

This sprint runs the full 16,590-query evaluation for the conditions that will appear in the paper's main results table.

---

## Conditions to Run

### Tier 1 — Full 16,590-query evaluation (paper's main results)

These conditions represent the key comparisons: best overall (rules), best LLM (Phi-4 classify), LLM baseline (Llama extract), and their oracle variants for Stage 1/Stage 2 isolation.

| # | Condition | Stage 1 | Stage 2 | Rationale |
|---|---|---|---|---|
| 1 | `structured_pipeline_rules` | E5 | Rules | **Main result** — best overall |
| 2 | `structured_pipeline_oracle_rules` | Oracle | Rules | Stage 2 ceiling |
| 3 | `structured_pipeline_phi4_classify` | E5 | Phi-4 classify | **Best LLM** — shows model scaling payoff |
| 4 | `structured_pipeline_oracle_phi4_classify` | Oracle | Phi-4 classify | LLM ceiling without Stage 1 noise |
| 5 | `structured_pipeline` (Llama extract) | E5 | Llama extract | LLM baseline — shows normalization problem |
| 6 | `structured_pipeline_oracle` (Llama extract) | Oracle | Llama extract | LLM baseline ceiling |

### Tier 2 — Reported from 50-query samples (paper's discussion/supplementary)

All other conditions (Llama classify/twostep/paraaware/paraaware2, Phi-4 extract/twostep/paraaware/paraaware2) — reported from 50-query samples in the paper with a note about sample size. No full run needed.

---

## Timing Estimates

Based on 50-query sanity tests:

| Condition | Est. time/query | Est. total (16,590 queries) |
|---|---|---|
| Rules (pipeline) | ~97ms | ~27 min |
| Rules (oracle) | ~82ms | ~23 min |
| Llama extract (pipeline) | ~710ms | ~3.3 hours |
| Llama extract (oracle) | ~706ms | ~3.2 hours |
| Phi-4 classify (pipeline) | ~900ms | ~4.1 hours |
| Phi-4 classify (oracle) | ~900ms | ~4.1 hours |

**Total estimated runtime: ~18 hours.** The LLM conditions should run overnight.

---

## Objectives

### 1. Create the full evaluation script

Create `scripts/run_full_eval.py` that:

1. Loads queries from `OEB_short_norm.parquet` (or `OEB_short_feats.parquet` — either works, both contain `item_key`, `parent_key`, `text`/`text_norm`)
2. **Draws a fresh random sample of 16,590 queries** with a fixed seed (e.g., `seed=42`). The original baselines also used independent random samples of the same size — since N=16,590 is the statistically-determined sample size (99% CI, ±1% margin), a fresh draw is comparable. The seed ensures reproducibility across conditions within this sprint.
3. For a given pipeline condition (specified via config or CLI argument):
   - Instantiates the appropriate `StructuredPipelineSearcher`
   - Runs search on all 16,590 queries
   - Produces output in the format expected by the existing evaluation pipeline
4. Supports running one condition at a time (CLI argument: config name or method name)
5. **Saves the sampled query IDs** (e.g., `runs/structured_eval_queries.json`) so that all 6 conditions use the exact same query set, and for future reference

**Output format — match existing `runs/` structure:**

Check what exists in `runs/` (e.g., `runs/dense_e5/`) and match the exact format. The key files:

- `runs/<method>/results_top100.jsonl.gz` — one JSON line per query with ranked results
- `runs/<method>/metrics_dual.json` — metrics by scope (overall, has_numbers, no_numbers) × target (item, parent)
- `runs/<method>/results_perquery_summary.csv` — per-query accuracy flags

Examine the existing files to determine the exact JSON structure, field names, and conventions. The output must be compatible with `eval.ipynb` and `src/utils/evaluation.py`.

**Important implementation details:**

- **Checkpointing**: Save progress every 500 queries to a temporary file. If the script crashes or is interrupted, it can resume from the last checkpoint. This is critical for LLM conditions that run 3–4 hours.
- **Progress reporting**: Print progress every 100 queries (query number, elapsed time, estimated time remaining).
- **Memory**: Use streaming writes (append to JSONL) rather than accumulating all results in memory. 16,590 queries × top 100 = 1.66M result entries.
- **GPU contention**: Only one LLM condition should run at a time. Rules conditions don't use GPU for Stage 2 (only for Stage 1 E5 encoding).

### 2. Run the evaluation

Execute all 6 Tier 1 conditions. Suggested order (to get results incrementally):

1. `structured_pipeline_rules` (~27 min) — main result, get it first
2. `structured_pipeline_oracle_rules` (~23 min) — Stage 2 ceiling
3. `structured_pipeline` Llama extract (~3.3 hrs)
4. `structured_pipeline_oracle` Llama extract (~3.2 hrs)
5. `structured_pipeline_phi4_classify` (~4.1 hrs)
6. `structured_pipeline_oracle_phi4_classify` (~4.1 hrs)

Conditions 1–2 can run during the day (~50 min total). Conditions 3–6 should run overnight (~15 hours sequential).

### 3. Compute metrics via existing notebooks

**Do not reimplement evaluation logic.** The metrics should be computed using the existing notebook pipeline:

1. The evaluation script (`run_full_eval.py`) writes `results_top100.jsonl.gz` and `results_perquery_summary.csv` to `runs/<method>/` in the exact format expected by the notebooks
2. Then run `eval.ipynb` (or `eval_all_runs.ipynb` in `eval/`) to compute `metrics_dual.json` for each new condition — just like the baselines were evaluated
3. If needed, the script can also call `src/utils/evaluation.py` programmatically (since the notebooks use it internally), but the notebooks are the reference

The existing evaluation pipeline uses `ranx` v0.3.7 and already computes the standard metrics and the `has_numbers` / `no_numbers` split. Report:

- **item Acc@1** — exact item match (primary metric)
- **parent Acc@1** — concept group match
- **Recall@5, Recall@10** — if applicable
- **MRR, nDCG@10** — if applicable

All metrics should be broken down by:
- **overall** — all 16,590 queries
- **has_numbers** — queries with numeric parameters
- **no_numbers** — queries without numeric parameters

### 4. Compile the paper's main results table

Combine the structured pipeline results with existing baselines from `runs/`:

| Method | item Acc@1 | parent Acc@1 | Notes |
|---|---|---|---|
| **Existing baselines (from `runs/`)** | | | |
| BM25 (param-aware tokens) | 97.4% | 98.5% | Lexical, catalog-specific tokenization |
| BM25 (standard unigram) | 86.9% | 97.3% | Lexical, generic |
| Dense E5 (item-level) | 13.4% | 98.2% | Neural, item-level vectors |
| BGE-M3 Dense | 12.7% | 96.0% | Neural, dense |
| BGE-M3 Sparse | 12.5% | 99.4% | Neural, sparse |
| BGE-M3 ColBERT | 44.8% | 99.7% | Neural, token-level |
| **Structured Pipeline (this work)** | | | |
| Rules (pipeline) | ? | ? | E5 → rules → lookup |
| Rules (oracle) | ? | ? | GT concept → rules → lookup |
| Phi-4 classify (pipeline) | ? | ? | E5 → Phi-4 classify → lookup |
| Phi-4 classify (oracle) | ? | ? | GT concept → Phi-4 classify → lookup |
| Llama extract (pipeline) | ? | ? | E5 → Llama extract → lookup |
| Llama extract (oracle) | ? | ? | GT concept → Llama extract → lookup |

**Do not re-run existing baselines.** Load their existing `metrics_dual.json` files.

The `has_numbers` vs `no_numbers` split is important because parametric items with numeric values are where the structured pipeline should show the most improvement over dense methods.

### 5. Document

Update `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` and `docs/RESEARCH_LOG.md` with:
- Full evaluation results for all 6 Tier 1 conditions
- Comparison with existing baselines
- The `has_numbers` vs `no_numbers` breakdown
- Runtime statistics (actual, not estimated)
- Any discrepancies between 50-query samples and full run
- Notable observations or surprises

---

## Acceptance Criteria

- [ ] `scripts/run_full_eval.py` exists, is runnable, and supports checkpointing
- [ ] All 6 Tier 1 conditions evaluated on 16,590 queries
- [ ] Output files in `runs/<method>/` for each condition
- [ ] `metrics_dual.json` computed for each condition
- [ ] Results table compiled: structured pipeline conditions + existing baselines
- [ ] `has_numbers` vs `no_numbers` breakdown reported
- [ ] Actual runtime per condition reported
- [ ] No existing baseline files, evaluation code, or other existing files modified
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Important Notes

- **Query set**: We draw a fresh random sample of 16,590 queries (fixed seed for reproducibility across conditions). The existing baselines used their own independent samples of the same size. Since N=16,590 gives 99% CI ±1% margin, results are directly comparable across independent samples. All 6 Tier 1 conditions in this sprint share the same sample.
- **Evaluation pipeline**: Use the existing `eval.ipynb` / `eval_all_runs.ipynb` notebooks (which use `ranx` v0.3.7 and `src/utils/evaluation.py`) to compute metrics. Do not reimplement evaluation logic — the output format of `run_full_eval.py` must match what the notebooks expect.
- **GPU contention**: Ollama (Phi-4/Llama) and E5 (sentence-transformers) may compete for GPU memory. Only one LLM-based condition should run at a time. Consider whether E5 encoding needs to happen on GPU or can be done on CPU for the pipeline conditions. Rules conditions use GPU only for E5 Stage 1.
- **Reproducibility**: Temperature is 0.0 for all LLM calls. Results should be deterministic for the same Ollama model version (pinned at 0.17.7).
- **Existing baselines**: The baseline numbers (BM25, E5, BGE-M3) are already in `runs/` from prior work on the `main` branch. They should be accessible from the `structured-retrieval` branch. If the `runs/` directory doesn't contain them on this branch, check `eval/` or reference the numbers from `docs/RESEARCH_PROPOSAL.md`.

---

## Out of Scope

- Error analysis by failure type (Sprint D1)
- Paper draft (Sprint D2)
- Figures and tables generation (Sprint D3)
- Re-running existing baselines
- Running Tier 2 conditions at full scale
