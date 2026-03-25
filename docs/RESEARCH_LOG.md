# Research Log

**Project:** Structure-Aware Retrieval for Parametric Catalogs
**Branch:** `structured-retrieval`
**Started:** March 2026

---

## How to Use This Log

Append an entry after every sprint. Each entry should capture:
- What was attempted and what was accomplished
- Key results (numbers, observations)
- Decisions made and their rationale
- Problems encountered and how they were resolved (or not)
- What changed in the plan as a result

Be concrete. Write numbers, not impressions. This log serves two purposes: (1) context recovery if we lose track of where we are, and (2) source material for the paper's methodology section.

---

## Log Entries

*Newest entries at the top.*

---

### Sprint D1 — Error Analysis
**Date:** 2026-03-13
**Sprint file:** `SPRINT_D1.md`
**Tasks from backlog:** D1 (error analysis of Sprint 13 results for paper)

**What was done:**
- Created `scripts/error_analysis.py` (~580 lines) — classifies all 13,110 failed queries across 6 Tier 1 conditions into error categories
- Re-runs Stage 2 rules extraction on failed queries for sub-classification (fast, ~5 seconds)
- LLM conditions classified as E2-UNSPECIFIED (would need `--rerun-llm` and Ollama for sub-classification)
- Produced 6 output files in `analysis/`: error_distribution.csv, errors_by_concept_group.csv, errors_by_axis.csv, error_examples.json, rules_vs_llm_comparison.csv, error_analysis_summary.md

**Error distribution (Table A):**

| Error type | Rules pipeline | Rules oracle | Llama pipeline | Llama oracle | Phi-4 pipeline | Phi-4 oracle |
|---|---|---|---|---|---|---|
| E1-WRONG_CONCEPT | 252 | 0 | 252 | 0 | 252 | 0 |
| E2-PARTIAL_EXTRACT | 1,352 | 1,434 | — | — | — | — |
| E2-UNSPECIFIED | — | — | 2,918 | 2,976 | 1,787 | 1,887 |
| **Total** | **1,604** | **1,434** | **3,170** | **2,976** | **2,039** | **1,887** |

**Per-axis accuracy (rules oracle, Table C):**

| Axis | Accuracy | Main failure mode |
|---|---|---|
| TRABAJO | 93.9% | 1,017 null extractions (query text abbreviates "franja horaria") |
| CONDICIONES DE EJECUCIÓN | 99.8% | 34 null extractions |
| BANDA DE MANTENIMIENTO | 99.8% | 28 null extractions |
| TUBO | 81.4% | 8 null extractions (low count, only 43 occurrences) |
| All other axes | 100.0% | — |

**Key findings:**
1. **All rules errors are E2-PARTIAL_EXTRACT** — rules never produce wrong values (0 E2-WRONG_VALUE, 0 E2-ALL_NULL, 0 E3-SCHEMA_MISMATCH). They either match correctly or return null.
2. **TRABAJO axis is the bottleneck** — accounts for ~70% of rules oracle errors. Queries abbreviate "cualquier frana horaria" (typo for "franja") which the rules can't match.
3. **252 E1 errors are shared** — all 3 pipeline conditions have the same 252 Stage 1 misses (E5 confuses similar concept groups like 110mm↔160mm, mano↔máquina).
4. **Hardest concept groups:** OEB190$ (ZANJA...A MANO, 35.8% error rate) and OEB200$ (ZANJA...A MÁQUINA, 33.6%). These have PROFUNDIDAD axis with range-format values that rules sometimes miss.
5. **has_numbers dominance:** 99.8% of errors come from queries with numeric parameters. The 29 no_numbers queries have 0% error rate for rules.
6. **Rules vs LLMs (oracle):** Rules are net-better. 887 queries where rules fails but Llama succeeds vs 2,429 where Llama fails but rules succeeds. Rules vs Phi-4: 804 vs 1,257.

**Problems encountered:**
- Sprint 13 did NOT save intermediate results (extracted params, Stage 1 predictions). Solved by re-running rules extraction (fast, deterministic). LLM conditions get coarser classification (E2-UNSPECIFIED).
- Initial bug: used raw `text` instead of `text_norm` for re-extraction (Sprint 13 pipeline used `text_norm`). Fixed to match pipeline behavior.

**Changes to plan:**
- None — all artifacts produced as planned

**CLAUDE.md updated:** No
**Next step:** Sprint D2 — Paper Draft

---

### Sprint 13 — Full Evaluation Run (C3)
**Date:** 2026-03-12 to 2026-03-13
**Sprint file:** `SPRINT_13.md`
**Tasks from backlog:** C3 (full evaluation on 16,590 queries)

**What was done:**
- Created `scripts/run_full_eval.py` (~450 lines) — self-contained evaluation script
  - CLI: `python scripts/run_full_eval.py <condition> [--resume] [--k 100] [--device cpu] [--compile-table]`
  - Checkpointing every 500 queries (uncompressed JSONL temp file, gzip on completion)
  - Progress reporting every 100 queries with ETA
  - Built-in metrics computation matching `metrics.ipynb` (item/parent targets × overall/has_numbers/no_numbers scopes)
  - `--compile-table` mode loads all conditions + baselines for formatted comparison
- Sampled 16,590 queries with `random_state=42`, saved to `runs/structured_eval_queries.json`
- Ran all 6 Tier 1 conditions sequentially, 0 errors across all runs

**Full evaluation results (N=16,590 queries):**

| Condition | item Acc@1 | parent Acc@1 | MRR | nDCG@10 | Runtime |
|---|---|---|---|---|---|
| Rules (pipeline) | 90.33% | 98.48% | 91.68% | 92.85% | 10m 50s (39ms/q) |
| Rules (oracle) | 91.36% | 100.00% | 92.72% | 93.90% | 13m 05s (47ms/q) |
| Phi-4 classify (pipeline) | 87.71% | 98.48% | 87.74% | 87.75% | 5h 17m (1147ms/q) |
| Phi-4 classify (oracle) | 88.63% | 100.00% | 88.67% | 88.68% | 5h 16m (1146ms/q) |
| Llama extract (pipeline) | 80.89% | 98.48% | 85.66% | 88.43% | 3h 27m (750ms/q) |
| Llama extract (oracle) | 82.06% | 100.00% | 86.95% | 89.76% | 3h 27m (751ms/q) |

**has_numbers vs no_numbers breakdown (item Acc@1):**

| Condition | has_numbers (N=16561) | no_numbers (N=29) |
|---|---|---|
| Rules (pipeline) | 90.31% | 100.00% |
| Rules (oracle) | 91.34% | 100.00% |
| Phi-4 classify (pipeline) | 87.69% | 96.55% |
| Phi-4 classify (oracle) | 88.61% | 96.55% |
| Llama extract (pipeline) | 80.88% | 89.66% |
| Llama extract (oracle) | 82.05% | 89.66% |

**Comparison with existing baselines (item Acc@1):**

| Method | item Acc@1 | parent Acc@1 |
|---|---|---|
| BM25 param-aware tokens | 97.37% | 98.52% |
| **Rules (pipeline)** | **90.33%** | 98.48% |
| BM25 standard unigram | 86.91% | 97.29% |
| **Phi-4 classify (pipeline)** | **87.71%** | 98.48% |
| **Llama extract (pipeline)** | **80.89%** | 98.48% |
| BGE-M3 ColBERT | 44.80% | 99.66% |
| Dense E5 | 13.42% | 98.18% |

**Key observations:**
1. **Stage 1 is not the bottleneck.** Pipeline vs oracle differences are small: Rules 1.0%, Phi-4 0.9%, Llama 1.2%. E5 item-level retrieval achieves 98.48% parent Acc@1, leaving little room for Stage 1 improvement.
2. **Stage 2 normalization is the bottleneck.** The gap between rules (90.3%) and LLM methods (80.9%–87.7%) comes from LLM value normalization failures (e.g., extracting "0.80 m" when catalog expects "hasta 0,80 m").
3. **Phi-4 classify beats BM25 standard unigram.** 87.7% vs 86.9% — a larger LLM with classification prompt can outperform generic lexical search.
4. **50-query samples were pessimistic.** Full-run results are significantly higher: Llama extract 68%→80.9%, Phi-4 classify 80%→87.7%, Rules 84%→90.3%. The 50-query sample had higher variance than expected.
5. **no_numbers queries are easy.** Only 29 queries (0.17% of sample) lack numeric parameters; all methods score >89% on them. The challenge is entirely in parametric items.
6. **BM25 param-aware tokens still dominates.** At 97.4%, domain-specific tokenization (which handles parameter formatting natively) remains far ahead. The structured pipeline's advantage is interpretability and modularity, not raw accuracy.

**Problems encountered:**
- Phi-4 conditions took ~5h 17m each (vs estimated 4.1h) — actual throughput was 1.15s/query vs estimated 0.9s/query
- LLM normalization warnings are pervasive but not fatal — catalog lookup handles unknown values gracefully by treating them as null

**Changes to plan:**
- None — all 6 Tier 1 conditions completed as planned

**CLAUDE.md updated:** No
**Next step:** Sprint D1 — Error Analysis

---

### Sprint 12 — Paraaware2: Per-Axis Detection with Informed Step 1
**Date:** 2026-03-11
**Sprint file:** `SPRINT_12.md`
**Tasks from backlog:** Fix paraaware's detection failures by showing possible values in each per-axis LLM call

**What was done:**
- Implemented paraaware2 prompt mode: one LLM call per axis, each showing possible values
- Added `build_paraaware2_step1_prompt()` and `build_paraaware2_step2_prompt()` to `prompts.py`
- Added `_extract_paraaware2()` to `LLMParamExtractor` with Step 2 fallback tracking
- Created 4 pipeline variants (paraaware2 × {Llama, Phi-4} × {pipeline, oracle}), 4 proxy modules, 4 YAML configs, 4 pseudo-index dirs (22 total)
- Extended CLI test with `--paraaware2` flag
- Ran 20-query Stage 2 tests with both models
- Ran 50-query pipeline sanity test with all 22 conditions

**Key results — Per-axis detection with values fixes original paraaware failures.**

20-query Stage 2 comparison:
- Rule-based: 100.0% per-axis (74/74), 100.0% per-query (20/20), 0.015ms/query
- Llama paraaware2: 82.4% per-axis (61/74), 55.0% per-query (11/20), 647ms/query, 5 Step 2 fallbacks
- Phi-4 paraaware2: 93.2% per-axis (69/74), 80.0% per-query (16/20), 726ms/query, 9 Step 2 fallbacks

Improvement over original paraaware (per-axis accuracy):
- Llama: 48.6% → 82.4% (+33.8 pp)
- Phi-4: 78.4% → 93.2% (+14.8 pp)

Comparison against all Sprint 09-11 methods (per-axis accuracy):

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Extract | 87.8% | 77.0% |
| Classify | 86.5% | 100.0% |
| Twostep | 64.9% | 58.1% |
| Paraaware | 48.6% | 78.4% |
| Paraaware2 | 82.4% | 93.2% |

**Decisions and rationale:**
- Chose bare-value responses (not JSON) to eliminate JSON parsing failures entirely
- Step 2 fallback only for unexpected outputs — low fallback count (5-9) confirms this is the right design
- One call per axis is ~Nx slower than single-call classify, but provides axis-level isolation

**Problems encountered:**
- Phi-4 occasionally concatenates multiple axis values in one response (e.g., "Diurno/3 <== i < 5 horas/Volumen escaso"), causing Step 2 fallbacks
- BANDA DE MANTENIMIENTO confusion persists across all LLM methods — the time interval format is inherently difficult
- Docker was unavailable during testing; ran tests directly with local Python and Ollama at localhost:11434

**Analysis:**
- Showing possible values upfront completely eliminates the abstract detection failures that plagued original paraaware (Sprint 09)
- Phi-4 paraaware2 (93.2%) is the second-best LLM method after Phi-4 classify (100.0%)
- Llama paraaware2 (82.4%) still below Llama extract (87.8%) — multi-call approach doesn't help Llama vs single-call with full schema
- The N-call approach adds latency without accuracy benefit over classify — classify remains the optimal prompt mode
- Rules remain unbeatable (100.0%) and orders of magnitude faster

50-query pipeline sanity test results:

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| Llama paraaware2 | 50.0% | 92.0% | 872.1ms |
| Llama oracle paraaware2 | 58.0% | 100.0% | 789.2ms |
| Phi-4 paraaware2 | 60.0% | 92.0% | 852.1ms |
| Phi-4 oracle paraaware2 | 68.0% | 100.0% | 772.9ms |

Pipeline ranking (oracle item Acc@1, 50 queries): rules 92.0% > Phi-4 classify 88.0% > Llama extract 74.0% > Phi-4 extract 72.0% > Phi-4 paraaware2 68.0% > Llama classify 60.0% > Llama paraaware2 58.0% > Phi-4 paraaware 50.0% > Phi-4 twostep 40.0% > Llama twostep 26.0% > Llama paraaware 22.0%.

Paraaware2 pipeline improvements over original paraaware (oracle item Acc@1): Llama 22.0% → 58.0% (+36 pp), Phi-4 50.0% → 68.0% (+18 pp). Significant improvement, but classify remains better: Llama classify 60.0%, Phi-4 classify 88.0%.

**What changed in the plan:** None. Sprint 12 was an exploratory sprint testing whether per-axis isolation could improve extraction. Result confirms classify is the optimal LLM prompt mode for both models.

---

### Sprint 11 — Phi-4 Twostep and Paraaware (Complete Model Comparison)
**Date:** 2026-03-09
**Sprint file:** `SPRINT_11.md`
**Tasks from backlog:** Complete the 2 models × 4 prompt modes comparison matrix

**What was done:**
- Created 4 new Phi-4 pipeline variants for twostep and paraaware modes (each with pipeline and oracle conditions):
  - 4 proxy modules (`structured_pipeline_phi4_twostep.py`, `structured_pipeline_oracle_phi4_twostep.py`, `structured_pipeline_phi4_paraaware.py`, `structured_pipeline_oracle_phi4_paraaware.py`)
  - 4 YAML configs
  - 4 pseudo-index dirs (via `setup_structured_index.py`)
  - Total: 18 variants (14 existing + 4 new)
- Added 4 Phi-4 twostep/paraaware conditions to pipeline sanity test in `structured_pipeline.py`
- Ran 20-query Stage 2 comparison and 50-query pipeline test with all 18 conditions
- Completes the full 2×4 model×prompt_mode comparison matrix

**Key results — Asymmetric model scaling effects confirmed across all prompt modes.**

**Stage 2 comparison (20 queries, Phi-4 14B, twostep + paraaware):**

| Method | Per-axis | Per-query | Time/query | Errors |
|---|---|---|---|---|
| Rule-based | 74/74 = 100.0% | 20/20 = 100.0% | 0.015ms | N/A |
| Phi-4 extract | 57/74 = 77.0% | 13/20 = 65.0% | 1092ms | 17 |
| Phi-4 twostep | 43/74 = 58.1% | 7/20 = 35.0% | 1905ms | 23 |
| Phi-4 paraaware | 58/74 = 78.4% | 9/20 = 45.0% | 2207ms | 16 |

- Phi-4 paraaware (78.4%) is BETTER than both Phi-4 extract (77.0%) and Phi-4 twostep (58.1%)
- Phi-4 twostep (58.1%) is WORSE than Llama twostep (64.9%) — consistent degradation pattern

**Complete 2×4 Stage 2 matrix (20 queries, per-axis accuracy):**

| Method | Llama 3.1 8B | Phi-4 14B | Delta |
|---|---|---|---|
| Extract | 87.8% | 77.0% | -10.8 pp |
| Classify | 86.5% | 100.0% | +13.5 pp |
| Twostep | 64.9% | 58.1% | -6.8 pp |
| Paraaware | 48.6% | 78.4% | +29.8 pp |

**50-query pipeline sanity test (new Phi-4 conditions):**

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| `structured_pipeline_phi4_twostep` | 36.0% | 92.0% | ~2267ms |
| `structured_pipeline_oracle_phi4_twostep` | 40.0% | 100.0% | ~2232ms |
| `structured_pipeline_phi4_paraaware` | 44.0% | 92.0% | ~2922ms |
| `structured_pipeline_oracle_phi4_paraaware` | 50.0% | 100.0% | ~2560ms |

**Cross-model pipeline comparison (all methods, pipeline item Acc@1):**

| Method | Llama 3.1 8B | Phi-4 14B | Delta |
|---|---|---|---|
| Extract | 66.0% | 64.0% | -2.0 pp |
| Classify | 52.0% | 80.0% | +28.0 pp |
| Twostep | 22.0% | 36.0% | +14.0 pp |
| Paraaware | 18.0% | 44.0% | +26.0 pp |

**Failure analysis:**
- **Model scaling has asymmetric effects by prompt mode:** The 2×4 matrix reveals a clear pattern — closed-set selection tasks (classify, paraaware Step 2 matching) benefit dramatically from scaling. Open-ended extraction tasks (extract, twostep Step 1) do NOT benefit or degrade.
- **Why paraaware benefits most (+29.8 pp):** Llama's paraaware failures were concentrated in Step 1 detection errors (incorrectly nulling axes) and Step 2 matching confusion. Phi-4's better reasoning avoids both: it detects parameters more reliably AND matches extracted values to schema values more accurately. Paraaware's Step 2 is fundamentally a closed-set selection task (match extracted value to one of N schema values), which is exactly where Phi-4 excels.
- **Why twostep degrades (-6.8 pp):** Twostep's Step 1 is unconstrained free-form extraction (describe what the query says about each axis). Phi-4's verbosity produces longer, more compound descriptions ("instalacion diurna con intervalo de descanso de 5 horas o mas") that Step 2 cannot decompose into individual schema values. The larger model's tendency toward comprehensive responses hurts when the task requires brief, decomposable outputs.
- **Final ranking (pipeline item Acc@1):** Rules 84% >> Phi-4 classify 80% > Llama extract 66% ≈ Phi-4 extract 64% > Llama classify 52% > Phi-4 paraaware 44% > Phi-4 twostep 36% > Llama twostep 22% > Llama paraaware 18%

**Decisions made:**
- Reused existing `--model` flag infrastructure from Sprint 10 — no T3 code changes needed
- Only added pipeline configs, proxy modules, and index dirs — all prompt logic and LLM infrastructure already existed
- Sprint 11 is purely a configuration+evaluation sprint — no algorithm changes

**Problems encountered:**
- None — all code changes, setup, and test runs completed successfully on first attempt

**Changes to plan:**
- The complete 2×4 matrix provides strong evidence for the paper's key finding: task framing (closed-set vs open-ended) determines whether model scaling helps
- Two orthogonal findings:
  1. **Prompt design matters more than model size:** Rules (0.015ms) > Phi-4 classify (886ms) > all other LLM methods
  2. **Model scaling is only effective for closed-set selection:** Classify and paraaware benefit; extract and twostep do not
- The interaction between prompt mode and model is highly non-linear — simple "bigger is better" does not apply
- Ready for Sprint C3 (full 16,590-query evaluation) with final method selection

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 11 entry with complete 2×4 matrix, cross-model analysis)
**Next step:** Sprint C3 (Full Evaluation on 16,590 queries) — complete model comparison provides context for paper

---

### Sprint 10 — Reproduce Results with Phi-4 14B
**Date:** 2026-03-09
**Sprint file:** `SPRINT_10.md`
**Tasks from backlog:** Model scaling ablation — Phi-4 14B vs Llama 3.1 8B

**What was done:**
- Pulled Microsoft Phi-4 14B (`phi4:latest`, 9.1 GB) into Docker Ollama alongside existing Llama 3.1 8B (`llama3.1:8b`, 4.9 GB)
- Created 4 new pipeline variants for Phi-4 (extract + classify modes, each with pipeline and oracle conditions):
  - 4 proxy modules (`structured_pipeline_phi4_extract.py`, `structured_pipeline_phi4_classify.py`, + oracle variants)
  - 4 YAML configs
  - 4 pseudo-index dirs (via `setup_structured_index.py`)
  - Total: 14 variants (10 existing + 4 Phi-4)
- Added `--model` CLI flag to `param_extractor_rules.py` T3 test — enables testing any Ollama model (default: `llama3.1:8b`)
  - Flexible model availability check using `model.split(":")[0]` for base name matching
  - All 4 LLM extractor instantiations now use `model=model` parameter instead of hardcoded values
- Added 4 Phi-4 conditions to pipeline sanity test in `structured_pipeline.py`

**Key results — MIXED: Phi-4 classify dramatically better, Phi-4 extract worse.**

**Stage 2 comparison (20 queries, Phi-4 14B):**

| Method | Per-axis | Per-query | Time/query | Errors |
|---|---|---|---|---|
| Rule-based | 74/74 = 100.0% | 20/20 = 100.0% | 0.016ms | N/A |
| Phi-4 extract | 57/74 = 77.0% | 13/20 = 65.0% | 1450ms | 17 |
| Phi-4 classify | 74/74 = 100.0% | 20/20 = 100.0% | 886ms | 0 |

- **Phi-4 classify achieves PERFECT 100%/100%** — matches rule-based baseline exactly
- **Phi-4 extract is WORSE than Llama extract** (77.0% vs 87.8%) — 17 errors (all omissions) vs Llama's 9
- Phi-4 classify is ~1.5x slower than Llama classify (886ms vs 570ms) — expected for larger model

**Cross-model Stage 2 comparison (20 queries):**

| Method | Llama 3.1 8B | Phi-4 14B | Delta |
|---|---|---|---|
| Extract per-axis | 87.8% | 77.0% | -10.8 pp |
| Extract per-query | 70.0% | 65.0% | -5.0 pp |
| Classify per-axis | 86.5% | 100.0% | +13.5 pp |
| Classify per-query | 65.0% | 100.0% | +35.0 pp |

**50-query pipeline sanity test (all 14 conditions):**

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% | 97ms |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% | 82ms |
| `structured_pipeline` (Llama extract) | 68.0% | 92.0% | 710ms |
| `structured_pipeline_oracle` (Llama extract) | 76.0% | 100.0% | 706ms |
| `structured_pipeline_classify` (Llama classify) | 52.0% | 92.0% | 690ms |
| `structured_pipeline_oracle_classify` (Llama classify) | 60.0% | 100.0% | 682ms |
| `structured_pipeline_phi4_extract` | 64.0% | 92.0% | ~1500ms |
| `structured_pipeline_oracle_phi4_extract` | 72.0% | 100.0% | ~1500ms |
| `structured_pipeline_phi4_classify` | 80.0% | 92.0% | ~900ms |
| `structured_pipeline_oracle_phi4_classify` | 88.0% | 100.0% | ~900ms |

- Phi-4 classify (80.0%/88.0%) approaches rules (84.0%/92.0%) — best LLM result achieved
- Phi-4 extract (64.0%/72.0%) is WORSE than Llama extract (68.0%/76.0%)
- Parent Acc@1 unchanged across all methods (92% E5 / 100% oracle) — confirms Stage 2 doesn't affect Stage 1

**Cross-model pipeline comparison:**

| Prompt mode | Llama 3.1 8B item Acc@1 | Phi-4 14B item Acc@1 | Delta |
|---|---|---|---|
| Extract (pipeline) | 68.0% | 64.0% | -4.0 pp |
| Extract (oracle) | 76.0% | 72.0% | -4.0 pp |
| Classify (pipeline) | 52.0% | 80.0% | +28.0 pp |
| Classify (oracle) | 60.0% | 88.0% | +28.0 pp |

**Failure analysis:**
- **Classify mode benefits enormously from model scaling:** Phi-4 14B achieves perfect Stage 2 accuracy (100%/100% on 20 queries) and near-rules pipeline accuracy (80% vs 84%). The classify prompt (closed-set selection from pipe-separated options) plays to Phi-4's strengths as a reasoning model. Llama 3.1 8B's classify failures (omission errors, returning null instead of selecting from list) were fundamentally a model capability limitation.
- **Extract mode does NOT benefit from scaling:** Phi-4 14B actually performs WORSE on extract (77.0% vs 87.8% per-axis). The errors are all omissions — Phi-4 returns null for axes that Llama correctly extracts. This suggests the extract task's difficulty is inherent to the open-ended extraction framing, not model capability. Larger models may over-think and become more conservative.
- **Remaining gap:** Phi-4 classify (80%) doesn't quite match rules (84%) in the 50-query pipeline test despite perfect Stage 2 accuracy on 20 queries. The 4 pp gap likely comes from harder queries in the larger sample. Oracle Phi-4 classify (88%) vs oracle rules (92%) shows the same 4 pp gap.

**Decisions made:**
- Used `phi4:latest` tag (not `phi4:14b`) — this is how Ollama registers the model
- Only tested extract and classify modes with Phi-4 (not twostep or paraaware) — those modes were already demonstrated as negative results in Sprints 08-09 and not worth the compute
- Added `--model` flag to T3 test for reusability — any future model can be tested without code changes

**Problems encountered:**
- `phi4:14b` tag not found in Ollama — resolved by pulling with just `phi4` (registered as `phi4:latest`)
- No other issues — all code changes ran correctly on first attempt

**Changes to plan:**
- Phi-4 classify is the strongest LLM-based method discovered, approaching rule-based accuracy
- For the paper: model scaling has dramatically asymmetric effects depending on prompt mode. Classify mode benefits from better reasoning (selection from closed set), while extract mode does not benefit (or even degrades) from larger models
- Two key findings for the paper:
  1. The classify prompt mode's poor performance with Llama was a model capability limitation, not a prompt design issue
  2. The extract prompt mode's errors are inherent to open-ended extraction, not solvable by scaling model size

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 10 entry with full results, cross-model analysis)
**Next step:** Sprint C3 (Full Evaluation on 16,590 queries) — rules-based confirmed as best, Phi-4 classify as strongest LLM alternative

---

### Sprint 09 — Parameter-Aware Two-Step LLM Extraction
**Date:** 2026-03-09
**Sprint file:** `SPRINT_09.md`
**Tasks from backlog:** Stage 2 parameter-aware two-step extraction mode

**What was done:**
- Added a parameter-aware two-step LLM extraction mode (`prompt_mode="paraaware"`) that attempts to improve on Sprint 08's failed twostep by: (1) framing Step 1 as explicit parameter detection ("does the query contain info about X?") rather than open extraction, and (2) optimizing Step 2 to only process non-null axes from Step 1
- Hypothesis: Sprint 08's twostep failed because Step 1 was too unconstrained (open extraction) — explicit detection framing should reduce verbose compound descriptions, and filtering null axes before Step 2 should reduce matching confusion
- Added `build_paraaware_extract_prompt()` and `build_paraaware_match_prompt()` to `src/pipeline/prompts.py`:
  - Step 1 asks "Analiza... y determina si contiene informacion sobre cada parametro" (detection framing)
  - Step 2 receives only axes where Step 1 found relevant information (non-null filtering)
- Added `_extract_paraaware()` method to `LLMParamExtractor`:
  - After Step 1: classifies axes into `non_null_extracted` and `null_axes`
  - If all axes null, skips Step 2 entirely (optimization — observed in practice with OEB160$)
  - Step 2 receives only non-null axes via filtered extracted dict
  - Final result merges null axes with validated Step 2 results
- Created 2 new pipeline variants (`structured_pipeline_paraaware`, `structured_pipeline_oracle_paraaware`):
  - 2 proxy modules, 2 YAML configs, 2 pseudo-index dirs (via `setup_structured_index.py`)
  - Total: 10 variants (8 existing + 2 paraaware)
- Extended T3 test to five-way comparison: rules vs LLM-extract vs LLM-classify vs LLM-twostep vs LLM-paraaware
  - Added `--paraaware` CLI flag

**Key results — NEGATIVE RESULT: paraaware performs even worse than twostep.**

**Five-way Stage 2 comparison (20 queries):**

| Method | Per-axis | Per-query | Time/query | Errors |
|---|---|---|---|---|
| Rule-based | 74/74 = 100.0% | 20/20 = 100.0% | 0.015ms | N/A |
| LLM-extract | 65/74 = 87.8% | 14/20 = 70.0% | 584ms | 9 |
| LLM-classify | 64/74 = 86.5% | 13/20 = 65.0% | 570ms | 10 |
| LLM-twostep | 48/74 = 64.9% | 7/20 = 35.0% | 1153ms | 25 |
| LLM-paraaware | 36/74 = 48.6% | 0/20 = 0.0% | 1128ms | 38 |

- LLM-paraaware has 0% per-query accuracy on 20 queries — every query has at least one axis error
- Omission errors increased from 25 (twostep) to 38 (paraaware) — the worst of all methods
- Parent Acc@1 unchanged (92% E5 / 100% oracle) as expected

**Failure analysis:**
- The detection framing ("does the query contain info about X?") did not reduce compound descriptions — Step 1 still produces verbose compound descriptions (e.g., "Diurno/i >=5 horas/Volumen relevante" for TRABAJO) identical to twostep's failure mode
- Detection framing actually made things worse: the LLM now sometimes treats genuinely present parameters as "not mentioned" (null), especially PAVIMENTO ("sin reposicion de pavimento" nulled because the LLM doesn't recognize it as a separate parameter from the concept description), CONDICIONES DE EJECUCION (treated as part of concept rather than parameter), and BANDA DE MANTENIMIENTO
- The null filtering optimization backfires: axes incorrectly classified as null in Step 1 can never be recovered in Step 2
- The Step 2 skip optimization triggered for OEB160$ (1-axis concept) — the LLM incorrectly nulled the only axis, skipping Step 2 entirely
- Fundamental issue: llama3.1:8b cannot decompose compound schema values that combine multiple sub-parameters (TRABAJO + BANDA DE MANTENIMIENTO + CONDICIONES DE EJECUCION are semantic clusters in the query text, not separable parameters)

**Decisions made:**
- Kept the paraaware implementation in the codebase as a documented negative result
- This conclusively demonstrates that two-step LLM approaches are not viable for this dataset/model combination
- The problem is not prompt framing (detection vs extraction) but the fundamental inability of llama3.1:8b to separate compound parameter clusters

**Problems encountered:**
- None — all code changes compiled and ran correctly on first attempt
- Poor results are a genuine methodological finding, not an implementation bug

**Changes to plan:**
- Two-step approaches (both twostep and paraaware) are definitively ruled out
- All LLM methods rank: extract (87.8%) >> classify (86.5%) >> twostep (64.9%) >> paraaware (48.6%)
- Rules-based extractor (100%) remains the clear best Stage 2 method for this dataset
- For the paper: negative results demonstrate that (1) task decomposition hurts when values appear as literal substrings, (2) detection framing is worse than extraction framing for this task, (3) null filtering optimizations can amplify Step 1 errors

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 09 entry with full results, analysis)
**Next step:** Sprint C3 (Full Evaluation on 16,590 queries) — rules-based extractor confirmed as best Stage 2 method

---

### Sprint 08 — Two-Step LLM Extraction (Extract then Match)
**Date:** 2026-03-09
**Sprint file:** `SPRINT_08.md`
**Tasks from backlog:** Stage 2 two-step extraction mode

**What was done:**
- Added a two-step LLM extraction mode (`prompt_mode="twostep"`) that separates understanding (Step 1: free-form extraction without showing schema values) from normalization (Step 2: match free-form descriptions to exact schema values)
- Hypothesis: extract mode fails on normalization (reformats values), classify mode fails on omission (returns null too often) — two-step separates these concerns so each LLM call can focus on one task
- Added `build_twostep_extract_prompt()` and `build_twostep_match_prompt()` to `src/pipeline/prompts.py`:
  - Step 1 lists axis labels only (no schema values) — LLM freely describes what each parameter is
  - Step 2 shows both extracted values AND schema values side-by-side for matching
- Added `_extract_twostep()` method to `LLMParamExtractor` with graceful degradation:
  - Step 1 parse failure after retry -> all None
  - Step 2 parse failure after retry -> fall back to direct validation of Step 1 values
- Created 2 new pipeline variants (`structured_pipeline_twostep`, `structured_pipeline_oracle_twostep`):
  - 2 proxy modules, 2 YAML configs, 2 pseudo-index dirs (via `setup_structured_index.py`)
  - Total: 8 variants (6 existing + 2 twostep)
- Extended T3 test to four-way comparison: rules vs LLM-extract vs LLM-classify vs LLM-twostep
  - Added `--twostep` CLI flag
  - Added error breakdown tracking (normalization errors, omission errors)
- Added twostep conditions to pipeline sanity test in `structured_pipeline.py`

**Key results — NEGATIVE RESULT: twostep significantly worse than both single-step modes.**

**Four-way Stage 2 comparison (20 queries):**

| Method | Per-axis | Per-query | Time/query | Errors |
|---|---|---|---|---|
| Rule-based | 74/74 = 100.0% | 20/20 = 100.0% | 0.015ms | N/A |
| LLM-extract | 65/74 = 87.8% | 14/20 = 70.0% | 687ms | 9 |
| LLM-classify | 64/74 = 86.5% | 13/20 = 65.0% | 568ms | 10 |
| LLM-twostep | 48/74 = 64.9% | 7/20 = 35.0% | 1147ms | 25 |

**50-query pipeline sanity test (all 8 conditions):**

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% | 97ms |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% | 82ms |
| `structured_pipeline` (LLM-extract) | 68.0% | 92.0% | 710ms |
| `structured_pipeline_oracle` (LLM-extract) | 76.0% | 100.0% | 706ms |
| `structured_pipeline_classify` (LLM-classify) | 52.0% | 92.0% | 702ms |
| `structured_pipeline_oracle_classify` (LLM-classify) | 60.0% | 100.0% | 694ms |
| `structured_pipeline_twostep` (LLM-twostep) | 22.0% | 92.0% | 1362ms |
| `structured_pipeline_oracle_twostep` (LLM-twostep) | 26.0% | 100.0% | 1342ms |

- Parent Acc@1 unchanged across all methods (92% E5 / 100% oracle) — confirms Stage 2 changes don't affect Stage 1
- Twostep is ~2x slower (two LLM calls) and far less accurate than single-step modes

**Failure analysis:**
- The two-step approach massively increases omission errors (25 errors vs 9 for extract and 10 for classify)
- Step 1 produces verbose/compound descriptions (e.g., "Nocturno excepcional/no necesita intervalo/volumen relevante" for TRABAJO) that Step 2 cannot match to individual schema values
- Step 2 sometimes fails to parse JSON entirely, triggering fallback to Step 1 direct validation (which is essentially extract mode without seeing schema values)
- The separation hypothesis was wrong for this task: showing the LLM the full context (query + schema values) in a single call produces better results than splitting the task. The LLM needs to see schema values while reading the query to understand the mapping

**Decisions made:**
- Kept the twostep implementation in the codebase as a documented negative result — valuable for the paper's methodology section
- Two-step prompt design matches the plan exactly (Step 1 shows axis labels only, Step 2 shows both extracted values and schema values)
- Graceful degradation implemented: Step 2 failure falls back to Step 1 direct validation against schema

**Problems encountered:**
- None — all code changes compiled and ran correctly on first attempt
- The poor results are a genuine methodological finding, not an implementation bug

**Changes to plan:**
- Two-step approach does not improve accuracy. The three Stage 2 methods now rank: rules (100%) >> extract (87.8%) >> classify (86.5%) >> twostep (64.9%). Rules-based extractor remains the clear best method for this dataset.
- For the paper: the negative result demonstrates that task decomposition is not always beneficial — when the source text contains exact parameter values as substrings, a single-pass extraction or selection is more effective than a two-pass approach that loses context between steps.

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 08 entry with full results, analysis)
**Next step:** Sprint C3 (Full Evaluation on 16,590 queries) — rules-based extractor confirmed as best Stage 2 method

---

### Sprint 07 — LLM Classification Prompt (Stage 2 Revision)
**Date:** 2026-03-09
**Sprint file:** `SPRINT_07.md`
**Tasks from backlog:** Stage 2 prompt redesign (extraction -> classification)

**What was done:**
- Redesigned the LLM prompt from extraction mode (LLM copies/paraphrases values) to classification mode (LLM selects from a closed set of schema values)
- Added `build_classification_prompt()` to `src/pipeline/prompts.py` alongside existing `build_extraction_prompt()`:
  - Pipe-separated values (`value_a | value_b | value_c`) instead of commas to emphasize discrete options
  - "clasifica" framing instead of "extrae" — the LLM picks from a list rather than copying from the query
  - Explicit instruction: "NO modifiques, reformatees ni parafrasees los valores" and "copiado exactamente"
  - ASCII-safe text (no accented characters) to avoid Windows cp1252 encoding issues
- Threaded `prompt_mode` parameter through the pipeline:
  - `LLMParamExtractor.__init__(prompt_mode="classify")` — dispatches to correct prompt builder
  - `load()` reads `stage2_prompt_mode` from `meta.json` params (default `"extract"` for backward compat)
- Created 2 new pipeline variants (`structured_pipeline_classify`, `structured_pipeline_oracle_classify`):
  - 2 proxy modules, 2 YAML configs, 2 pseudo-index dirs (via `setup_structured_index.py`)
  - Total: 6 variants (4 existing + 2 classify)
- Extended T3 test in `param_extractor_rules.py` to three-way comparison:
  - `--classify` CLI flag enables side-by-side: rules vs LLM-extract vs LLM-classify
  - Added normalization error counting per LLM method
- Added classify conditions to pipeline sanity test in `structured_pipeline.py`

**Key results (50-query pipeline sanity test, all 6 conditions):**

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% | 97ms |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% | 82ms |
| `structured_pipeline` (LLM-extract) | 68.0% | 92.0% | 710ms |
| `structured_pipeline_oracle` (LLM-extract) | 76.0% | 100.0% | 706ms |
| `structured_pipeline_classify` (LLM-classify) | 52.0% | 92.0% | 690ms |
| `structured_pipeline_oracle_classify` (LLM-classify) | 60.0% | 100.0% | 682ms |

- **Classification prompt is worse than extraction:** 52% vs 68% (E5), 60% vs 76% (oracle)
- Parent Acc@1 unchanged across all methods (92% E5 / 100% oracle) — confirms Stage 2 changes don't affect Stage 1

**Three-way Stage 2 comparison (20 queries):**

| Method | Per-axis | Per-query | Time/query | Norm. errors |
|---|---|---|---|---|
| Rule-based | 74/74 = 100.0% | 20/20 = 100.0% | 0.015ms | N/A |
| LLM-extract | 65/74 = 87.8% | 14/20 = 70.0% | 1101ms | 9 |
| LLM-classify | 64/74 = 86.5% | 13/20 = 65.0% | 572ms | 10 |

- Classification prompt **fixed** normalization errors: PROFUNDIDAD `1,10 m` now extracted correctly (rows 18-19 in T3), BANDA DE MANTENIMIENTO fixed in row 19
- Classification prompt **introduced** new omission errors: LLM returns None for axes it previously extracted correctly (Nº TUBOS in OEB040$/OEB230$, BANDA DE MANTENIMIENTO/CONDICIONES in OEB100$)
- Net effect: classify trades 3 normalization fixes for 4 new omissions — slightly worse overall

**Decisions made:**
- Classification prompt over extraction prompt — root cause of Sprint 04's 87.8% accuracy was output normalization failures (LLM understood the query correctly but reformatted values like `1,10 m` -> `1.10`). Classification mode eliminates this by presenting values as a closed set to select from
- Pipe-separated values (`|`) over comma-separated — stronger visual delimiter for the LLM to recognize options as distinct choices
- ASCII-safe prompt text — avoids cp1252 encoding issues that have caused problems in previous sprints
- Default `prompt_mode` in `load()` is `"extract"` (not "classify") for backward compatibility — existing meta.json files without `stage2_prompt_mode` continue using extraction mode unchanged
- Default in `LLMParamExtractor.__init__()` is `"classify"` per sprint spec — direct instantiation uses the new mode

**Problems encountered:**
- None — all code changes and setup ran successfully on first attempt
- Classification prompt underperformance was unexpected — the hypothesis that closed-set selection would eliminate errors was partially correct (normalization errors fixed) but the prompt format caused more omission errors, especially on bare numeric values in pipe-separated lists

**Changes to plan:**
- Classification prompt does not close the accuracy gap as hoped. The LLM struggles with the pipe-separated format for short numeric values. Future work could try: (1) few-shot examples in the classify prompt, (2) hybrid approach (classify for text axes, extract for numeric), (3) post-processing LLM-extract output with fuzzy matching

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 07 entry with full LLM results, analysis)
**Next step:** Sprint C3 (Full Evaluation on 16,590 queries) — rules-based extractor remains the best Stage 2 method

---

### Sprint 06 — Pipeline Integration (C1)
**Date:** 2026-03-09
**Sprint file:** `SPRINT_06.md`
**Tasks from backlog:** C1 (Pipeline Assembly)

**What was done:**
- Created `src/retrievers/structured_pipeline.py` with `StructuredPipelineSearcher` class implementing the Searcher contract (`search`, `search_batch`, `external_ids`)
- Three-stage pipeline: E5 dense retrieval (Stage 1) -> parameter extraction (Stage 2) -> catalog lookup (Stage 3) -> three-tier ranked output
- `load(index_dir)` factory reads `meta.json` from pseudo-index dir to configure pipeline variant (stage2_method, oracle flag, Ollama settings)
- Created 3 proxy retriever modules (1-line files re-exporting `load()`) for `dynamic_load_retriever` import resolution
- Created 4 YAML configs matching the 4 evaluation conditions
- Created `scripts/setup_structured_index.py` — generates pseudo-index directories with meta.json, fields.json, mapping.jsonl (copied from E5), and empty data/ dir
- Added `device_override` parameter to `load()` for running on non-CUDA hosts (Windows CPU)
- Integrated `__main__` sanity test: stratified sampling, runs all variant conditions, prints accuracy table

**Key results (50-query sanity test, rules variants):**

| Condition | item Acc@1 | parent Acc@1 | time/query |
|---|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% | 110ms |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% | 94ms |

- Oracle achieves 100% parent Acc@1 (ground-truth parent_key bypass)
- 8% item Acc@1 gap between oracle (92%) and non-oracle (84%) reflects Stage 1 errors propagating to Stage 3
- 92% parent Acc@1 for non-oracle is consistent with E5's ~97.5% parent Acc@1 on 200-query sample (smaller sample variability expected)
- Output arrays: shape (50, 100), dtypes int64/float32 -- assertions pass

**Decisions made:**
- **Pseudo-index directories:** `retrieve.ipynb` requires `index/{method}/` with standard artifact files. Since the structured pipeline reuses the E5 index internally, each variant gets a lightweight dir with its own meta.json (pipeline config) and a copy of E5's mapping.jsonl
- **Proxy modules:** `dynamic_load_retriever` imports `retrievers.{method_name}`. All 4 variants share the same `StructuredPipelineSearcher` code, so proxy modules simply re-export `load()`. The variant's behavior is determined by the meta.json in its index dir
- **Three-tier ranking:** Tier 1 = matched items (score ~1.0), Tier 2 = remaining concept group items (~0.5), Tier 3 = E5 fallback (<0.5). Ensures exactly k results are always returned
- **device_override:** E5 meta.json has `device: "cuda"` from when the index was built in Docker. Added `device_override` param to `load()` so sanity tests can run on Windows CPU. Does not affect production Docker workflow

**Problems encountered:**
- CUDA not available on Windows (PyTorch CPU-only): `DenseE5Searcher` loads model with `device="cuda"` from meta.json -> `AssertionError: Torch not compiled with CUDA enabled`. Fixed by adding `device_override` parameter to `load()` that patches `e5.device` after construction
- Windows cp1252 encoding: Unicode characters in print statements (`->`, box-drawing `---`, em-dash, arrows) cause `UnicodeEncodeError`. Fixed by replacing all non-ASCII characters in print/log output with ASCII equivalents
- `groupby().apply()` with `include_groups=False` drops the groupby column from the result DataFrame, causing `KeyError: 'parent_key'`. Fixed by rewriting stratified sampling with explicit for-loop over groups

**Changes to plan:**
- LLM variants not tested on Windows (requires Ollama + CUDA). Will be tested in Docker environment for full evaluation (Sprint C3)

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md -- Sprint 06 entry, new files, evaluation conditions, sprints list)
**Next step:** Sprint C3 (Full Evaluation on 16,590 queries) or run LLM variants in Docker

---

### Sprint 05 — Rule-Based Parameter Extractor (Stage 2 Baseline)
**Date:** 2026-03-09
**Sprint file:** `SPRINT_05.md`
**Tasks from backlog:** B4 (Rule-based parameter extractor)

**What was done:**
- Created `src/pipeline/param_extractor_rules.py` with `RuleBasedParamExtractor` class
- Same interface as `LLMParamExtractor` (`extract`, `extract_batch`) — pipeline can swap without code changes
- Two matching strategies:
  1. **Text matching** (`_match_text`): Normalized substring matching. Both query and schema values are lowercased, accent-stripped, tokenized with `\w+`, and rejoined. Entries sorted longest-first. Subsumption filter removes shorter matches that are substrings of longer ones (e.g., "Diurno" subsumed by "Diurno Excepcional"). Returns value if exactly 1 match survives; None if 0 or 2+ matches.
  2. **Numeric matching** (`_match_numeric`): For axes with short digit values (Nº TUBOS, TUBO, DIÁMETROS). Three-strategy cascade: (a) raw unit match for values with non-digit chars (3", 3'', 40mm), (b) multi-word normalized match (1 o 2), (c) context regex patterns for bare digits adjacent to tube-related keywords.
- Axis classification: "text" if all normalized values > 2 chars, "numeric" if any ≤ 2 chars
- Reuses `normalize_text()` from `src/utils/text_processing.py` for accent stripping
- Tests in `__main__` block: T1 single extraction, T2 batch of 20 queries, T3 side-by-side LLM comparison
- CLI: `--n-queries`, `--base-url`, `--skip-llm`

**Key results:**
- T1 Single extraction (OEB010$): PASS — 3/3 axes correct, 0.033ms
- T2 Batch of 20 queries (same sample as Sprint 04):
  - **Per-axis accuracy: 100.0%** (74/74 axes correct)
  - **Per-query accuracy: 100.0%** (20/20 queries fully correct)
  - Avg time/query: 0.015ms
  - Total time: <1ms for all 20 queries
- T3 Side-by-side comparison with LLM:
  - Rule-based: 74/74 = 100.0% per-axis, 20/20 = 100.0% per-query, 0.015ms/query
  - LLM:        65/74 = 87.8% per-axis, 14/20 = 70.0% per-query, 900ms/query
  - Speed advantage: ~60,000× faster than LLM
- LLM failure analysis (9 axis errors across 6 queries):
  - Nº TUBOS (OEB030$): LLM returned None — failed to extract tube count
  - TUBO (OEB090$): LLM returned "3" instead of `3"` — stripped unit character
  - PROFUNDIDAD (OEB190$, OEB200$): LLM returned "1.10"/"1.1" instead of `1,10 m` — wrong decimal separator and missing unit
  - BANDA DE MANTENIMIENTO (OEB110$, OEB150$, OEB200$): LLM returned None or truncated value
  - CONDICIONES DE EJECUCIÓN (OEB110$, OEB150$): LLM returned None

**Decisions made:**
- Axis classification by normalized value length (≤2 chars → numeric) instead of label-based rules — correctly identifies Nº TUBOS, TUBO, DIÁMETROS as needing context matching while keeping DIÁMETRO (values like "40mm") as text-safe
- Subsumption-based disambiguation instead of longest-match-only — correctly handles cases where "Diurno" and "Diurno Excepcional" both appear in query text
- No synonym dictionary needed — the 20-query test showed 100% accuracy without synonyms because query text contains exact parameter values

**Problems encountered:**
- DeprecationWarning from pandas `DataFrameGroupBy.apply` in test sampling code — cosmetic, not blocking (same as Sprint 04)
- Windows terminal encoding (cp1252) garbles accented characters in output — cosmetic, not affecting correctness

**Changes to plan:**
- The rule-based extractor significantly outperforms the LLM on this 20-query sample. This is expected because catalog queries contain exact parameter values as substrings — the data generation process embeds parameters literally in query text. The LLM's failures come from reformatting values (changing decimal separators, stripping units) rather than understanding failures. For the full 16,590-query evaluation (Sprint C3), rule-based may still dominate, but edge cases (typos, paraphrased queries, abbreviated forms) could favor the LLM.

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 05 entry, new files, sprints list)
**Next step:** Sprint C1 (Pipeline Assembly)

---

### Sprint 04 — LLM Parameter Extractor (Stage 2) with Ollama
**Date:** 2026-03-09
**Sprint file:** `SPRINT_04.md`
**Tasks from backlog:** B3 (LLM parameter extractor), partial infrastructure

**What was done:**
- Added Ollama 0.17.7 as Docker service to `docker-compose.yml` — GPU-enabled, `ollama-models` named volume, on existing `bc3cat-retrieval` bridge network
- Pulled `llama3.1:8b` model (4.9GB) into Docker container
- Created `src/pipeline/prompts.py` with `build_extraction_prompt()` — Spanish prompt template listing concept name, axis labels with allowed values, and query text
- Created `src/pipeline/param_extractor.py` with `LLMParamExtractor` class:
  - `extract(parent_key, query)` → `{axis_label: value | None}`
  - `extract_batch(items)` — sequential with progress reporting
  - JSON parsing handles markdown code fences, trailing commas
  - Retry once on parse failure, all-None fallback
  - Case-insensitive value validation against schema
- Wrote comprehensive tests in `__main__` block (T1–T4)

**Key results:**
- T1 Connectivity: PASS — Ollama reachable at localhost:11434, llama3.1:8b model available
- T2 Single extraction (OEB010$): PASS
  - 3/3 axes correct: TERRENO=blando, PAVIMENTO=sin reposicion, CONDICIONES DE EJECUCION=Volumen relevante
  - First call: 34,317ms (model loading into GPU memory)
- T3 Batch of 20 queries:
  - **Per-axis accuracy: 87.8%** (65/74 axes correct)
  - **Per-query accuracy: 70.0%** (14/20 queries fully correct)
  - Avg time/query: 585ms (after model warm-up)
  - Total time: 11.7s for 20 queries
- T4 JSON parsing robustness: 5/5 edge cases PASS (code fences, trailing commas, empty dict, malformed text, empty string)
- Failure analysis:
  - Numeric/range values: LLM returns '3' but schema expects full tube name, '1.10' vs exact schema depth format
  - Some axes not extracted (returned null when value was present in query)
  - Value validation correctly catches unknown values and logs warnings

**Decisions made:**
- Use Ollama REST API directly via `requests` — no `ollama` Python package dependency (per sprint spec)
- Pin Ollama to version 0.17.7 for reproducibility
- Temperature 0.0 for deterministic extraction
- Pre-build lowercase lookup dict for efficient value validation
- Default `ollama_base_url` to `http://ollama:11434` (Docker service name) with configurable override

**Problems encountered:**
- Docker Desktop initially not running — started manually
- Local Ollama (v0.1.38) too old for llama3.1:8b — used Docker-based Ollama 0.17.7 instead
- `_get_ground_truth()` crashed on `NoneType` — some parameter slots (D, F) in parquet are None for items that don't use all 5 possible axis positions. Fixed by adding `if axis_data is None: continue`
- DeprecationWarning from pandas `DataFrameGroupBy.apply` in test sampling code (cosmetic, not blocking)

**Changes to plan:**
- None. Stage 2 is functional. Per-axis accuracy of 87.8% on initial 20-query sample is a reasonable starting point. Accuracy may improve with prompt optimization (future work, out of scope for this sprint).

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md — Sprint 04 entry, design decisions, new files)
**Next step:** Sprint C1 (Pipeline Assembly) or Sprint B4 (Rule-based Extractor)

---

### Sprint 03 — Pivot Stage 1 to Item-Level E5 Retrieval
**Date:** 2026-03-09
**Sprint file:** `SPRINT_03.md`
**Tasks from backlog:** B1 (revised)

**What was done:**
- Pivoted Stage 1 from concept-level index (25 vectors, 85.6% parent Acc@1) to existing item-level E5 index (`index/dense_e5/`, 47,514 vectors, 97.5% parent Acc@1)
- Created `src/pipeline/verify_stage1.py` — verification script confirming item-level retrieval works for Stage 1
- Updated `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` with pivot decision: architecture, design decisions, new files, evaluation conditions, stage 1 integration note
- Confirmed `DenseE5Searcher` from `src/retrievers/dense_e5.py` can be used directly as Stage 1 — no adapter or wrapper needed

**Key results:**
- Verification on 200 queries (random seed 42):
  - **Parent Acc@1 = 97.5%** (195/200) — confirming expected ~98%
  - 5 failures all from tube-diameter groups: OEB230$ (3), OEB030$ (1), OEB290$ (1)
  - Search time: 4.92s total (24.6ms/query on CPU)
- API check confirmed:
  - `searcher.search(query, k=1)` returns `(indices, scores)` — numpy arrays
  - `searcher.external_ids[idx]` gives item_key (e.g., `"OEB230dfdda"`)
  - Pipeline only needs `{item_key: parent_key}` lookup dict from parquet — no new code required
- Concept-level index artifacts (Sprint 02) kept as evidence but marked as exploratory

**Decisions made:**
- Use existing item-level E5 index for Stage 1 instead of concept-level index — 97.5% vs 85.6% parent Acc@1
- No adapter needed: `DenseE5Searcher.search()` + `external_ids` + parquet lookup dict gives the full Stage 1 flow
- Concept-level experiment (Sprint 02) documented as exploratory work, not discarded

**Problems encountered:**
- Item-level index's `meta.json` has `device: "cuda"` — local Windows Python has CPU-only PyTorch. Fixed by overriding `searcher.device = "cpu"` in verification script when CUDA unavailable

**Changes to plan:**
- Stage 1 is now fully confirmed. Next steps are Stage 2 (LLM parameter extraction, Sprint B3) and pipeline assembly (Sprint C1).

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md)
**Next step:** Sprint B3 (LLM Parameter Extractor) or Sprint C1 (Pipeline Assembly)

---

### Sprint 02 — Concept-Level E5 Index (Stage 1)
**Date:** 2026-03-09
**Sprint file:** `SPRINT_02.md`
**Tasks from backlog:** B1

**What was done:**
- Created `src/index_builders/concept_dense_e5.py` — standalone builder (Option A: loads schema -> encodes -> saves, no notebook dependency)
- Created `configs/concept_dense_e5.yaml` — config for consistency with repo pattern
- Built index at `index/concept_dense_e5/` with standard artifact layout
- Reused existing `DenseE5Searcher` from `src/retrievers/dense_e5.py` for sanity check — no retriever modifications needed

**Key results:**
- Index artifacts verified:
  - `data/embeddings.npy` shape (25, 768) — one vector per concept group
  - `mapping.jsonl` — 25 entries, external_ids match all schema parent_keys
  - `meta.json` and `fields.json` present and correct
- Sanity check on 500 queries (random seed 42):
  - **Acc@1 = 85.6%** (428/500) — below expected >95%
  - **Acc@3 = 99.4%** (497/500) — correct concept almost always in top-3
- All Acc@1 failures from 6 near-identical concept groups:
  - OEB030$ (110mm), OEB040$ (160mm), OEB230$ (200mm), OEB280$ (40mm), OEB290$ (50mm), OEB300$ (90mm)
  - All share base text "CANALIZACIÓN HORMIGONADA DE TUBO DE POLIETILENO Xmm", differing only in tube diameter
  - Failure breakdown (200-query sample): OEB230$ 9, OEB290$ 4, OEB040$ 4, OEB030$ 2, OEB170$ 2, OEB300$ 2, OEB120$ 1
- Tested with and without "passage: " doc prefix — negligible difference (88.0% vs 87.5% on 200 queries)

**Decisions made:**
- Option A (standalone script) over Option B (builder contract) — simpler, self-contained, sprint spec allows either
- "passage: " doc prefix used per E5 convention and sprint spec; performance effectively identical without it
- Existing `DenseE5Searcher` reused as-is — just point `load()` at new index directory
- `SentenceTransformer.encode(normalize_embeddings=True)` for L2 normalization (simpler than manual normalization in existing builder)

**Problems encountered:**
- `sentence-transformers` not installed in local Windows Python env — installed via pip
- Acc@1 (85.6%) below sprint expectation of >95% — not a code bug but a property of near-duplicate concept texts. The sprint assumption "concept-level should be at least as good as item-level (98.2%)" was incorrect: item-level vectors contain full parameter text (including diameter), making them more discriminative than short concept-level text

**Changes to plan:**
- Concept-level Acc@1 is ~86%, not >95% as assumed in protocol. Pipeline may benefit from retrieving top-K concepts at Stage 1 instead of top-1 (Acc@3 = 99.4%). This is a design consideration for Sprint C1 (pipeline assembly).

**CLAUDE.md updated:** Yes (CLAUDE_STRUCTURED_RETRIEVAL.md)
**Next step:** Sprint B3 (LLM Parameter Extractor) or Sprint B4 (Rule-based Extractor)

---

### Sprint 01 — Deterministic Catalog Lookup
**Date:** 2026-03-09
**Sprint file:** `SPRINT_01.md`
**Tasks from backlog:** B2

**What was done:**
- Created `src/pipeline/catalog_lookup.py` with `CatalogLookup` class
- Class loads schema JSON + parquet, builds per-group item index from `parameters_norm`
- Provides `lookup(parent_key, extracted_params)`, `get_schema(parent_key)`, `get_all_parent_keys()`
- Wrote 7 tests in `__main__` block, all passing

**Key results:**
- 7/7 tests pass:
  - T1: Full match (3 axes, OEB010$) returns exactly `["OEB010aaa"]`
  - T2: Partial match (1 of 3 axes) returns 6 items (2 pav x 3 cond)
  - T3: All null (OEB160$, 1 axis) returns all 3 items
  - T4: Unknown parent_key returns `[]`
  - T5: Unknown axis value logs warning, treats as wildcard, returns all 3 items
  - T6: Large group all-null (OEB030$, 5 axes) returns all 6,336 items
  - T6b: Large group 1-axis (OEB030$, Nº TUBOS=1) returns 576 items (8x6x4x3)
- Index built from `parameters_norm` column (lowercased, stripped, accents preserved)
- Validation against schema catches unknown labels and values, falls back to wildcard

**Decisions made:**
- Use `parameters_norm` (not raw `parameters`) for building the lookup index — already lowercased and stripped
- Preserve accents in normalization (only `.strip().lower()`, no accent removal) — avoids collisions, matches what LLM will see in schema prompts
- List-of-dicts index with linear filtering — simple and correct; 6,336 items is fast enough
- Unknown axis values treated as None (wildcard) with logged warning — graceful degradation

**Problems encountered:**
- Windows terminal (cp1252) can't print Unicode arrow characters — replaced with ASCII `->` in print statements

**Changes to plan:**
- None

**CLAUDE.md updated:** No
**Next step:** Sprint 02 — Concept-level E5 Index (B1) or LLM Parameter Extractor (B3)

---

### Sprint 00 — Branch Setup and Schema Extraction
**Date:** 2026-03-09
**Sprint file:** `SPRINT_00.md`
**Tasks from backlog:** A1 (branch setup), A2 (schema extraction)

**What was done:**
- Created `src/pipeline/__init__.py`
- Created `src/pipeline/schema_extractor.py`
- Produced `data/processed/OEB_concept_schema.json`

**Key results:**
- 25 concept groups extracted (matching the 25 parent_key values ending in `$`)
- Each group has `concept`, `axes`, `item_keys`, `num_items`
- Groups range from 1 axis / 3 items (OEB160$) to 5 axes / 6,336 items (OEB030$, OEB040$, etc.)
- Spot-checked OEB010$, OEB030$, OEB160$ — all axes, values, and item keys match raw parquet exactly

**Decisions made:**
- None (followed protocol)

**Problems encountered:**
- None

**Changes to plan:**
- None

**CLAUDE.md updated:** No
**Next step:** Sprint 01 — Deterministic Catalog Lookup (B2)

---

### Pre-Sprint — Project Setup
**Date:** March 2026

**Context documents created:**
- `RESEARCH_PROPOSAL.md` v0.4 — revised with colleague feedback, BM25 baselines, catalog-query caveat
- `RESEARCH_PROTOCOL.md` v0.1 — flexible sprint approach, single LLM (Llama 3.1 8B), task backlog
- `CLAUDE.md` — branch context for Claude Code
- `RESEARCH_LOG.md` — this file

**Key decisions made during planning:**
- Single LLM model (Llama 3.1 8B) — no multi-model ablation for now
- E5 for Stage 1 (lightest model, 98.2% parent Acc@1)
- Spanish prompts (matching catalog language)
- Full parameter schema in prompts
- Partial extraction returns sub-group (no priors)
- Concept-level indexing on `concept` field text

**Repo observations from analysis:**
- Existing E5 index is item-level (47,514 vectors), not concept-level — new index needed
- Parameter structure already in `parameters` column of parquet — schema extraction is straightforward
- `OEB_long_norm.parquet` columns available: `item_key`, `parent_key`, `concept`, `parameters`, `text`, `text_norm`, `text_word_params`, `numbers`, `param_tokens`
- Eval output format: `runs/<method>/metrics_dual.json` with scopes (overall, has_numbers, no_numbers) × targets (item, parent)
- 25 concept groups, largest has 6,336 items across 5 axes

**Next step:** Sprint 00 — branch creation + schema extraction

---

