# Sprint 11 — Phi-4 Twostep and Paraaware (Complete Model Comparison)

**Tasks from backlog:** Model scaling ablation — complete Phi-4 prompt matrix
**Prerequisites:** Sprint 10 complete (Phi-4 extract and classify tested)

---

## Context

Sprint 10 revealed a dramatic asymmetry in model scaling:

| Prompt mode | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Extract per-axis | 87.8% | 77.0% (worse) |
| Classify per-axis | 86.5% | 100.0% (perfect) |
| Twostep per-axis | 64.9% | ? |
| Paraaware per-axis | 48.6% | ? |

Phi-4 classify went from 65% to 100% — proving the classify prompt's failures with Llama were a model capability issue, not a prompt design flaw. The same might be true for twostep and paraaware: Llama's catastrophic failures (35% and 0% per-query) might stem from insufficient reasoning capability for multi-step tasks, not from fundamental strategy flaws.

This sprint completes the 2 models × 4 prompt modes matrix.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Verify Phi-4 is available

Phi-4 should already be pulled from Sprint 10:

```bash
docker-compose exec ollama ollama list
# Should show llama3.1:8b and phi4:latest
```

### 2. Create Phi-4 twostep and paraaware configs

Create 4 new pipeline configs:

- **`configs/structured_pipeline_phi4_twostep.yaml`** — E5 + Phi-4 twostep + catalog
- **`configs/structured_pipeline_phi4_paraaware.yaml`** — E5 + Phi-4 paraaware + catalog
- **`configs/structured_pipeline_oracle_phi4_twostep.yaml`** — Oracle + Phi-4 twostep
- **`configs/structured_pipeline_oracle_phi4_paraaware.yaml`** — Oracle + Phi-4 paraaware

Follow the exact same pattern as Sprint 10's Phi-4 configs. The only difference is `prompt_mode: twostep` or `prompt_mode: paraaware`. Create proxy modules and pseudo-index dirs as in previous sprints.

### 3. Run 20-query Stage 2 comparison (complete 2×4 matrix)

Run the same 20 queries (same `random_state=42`, same stratified sampling) with the two new Phi-4 modes. Combine with all previous results into the complete matrix:

**Complete 2 models × 4 prompts matrix (20 queries):**

| Method | Llama 3.1 8B | Phi-4 14B |
|---|---|---|
| Extract per-axis | 87.8% | 77.0% |
| Extract per-query | 70.0% | 65.0% |
| Classify per-axis | 86.5% | 100.0% |
| Classify per-query | 65.0% | 100.0% |
| Twostep per-axis | 64.9% | ? |
| Twostep per-query | 35.0% | ? |
| Paraaware per-axis | 48.6% | ? |
| Paraaware per-query | 0.0% | ? |

Report for the new Phi-4 conditions:
- Per-axis accuracy
- Per-query accuracy
- Error breakdown: normalization errors vs. omission errors
- Average time per query

**Key questions:**
- Does Phi-4 twostep recover from Llama's 35% per-query? If classify went 65→100, can twostep go 35→something competitive?
- Does Phi-4 paraaware recover from Llama's 0% per-query?
- Does the pattern hold: stronger model helps closed-set tasks (classify, step 2 matching) but not open-ended extraction?

### 4. Run 50-query pipeline sanity test

Run the 4 new conditions on 50 queries. Add to the master table:

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| **Rules** | | |
| `structured_pipeline_rules` | 84.0% | 92.0% |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% |
| **Llama 3.1 8B** | | |
| `structured_pipeline` (extract) | 68.0% | 92.0% |
| `structured_pipeline_oracle` (extract) | 76.0% | 100.0% |
| `structured_pipeline_classify` | 52.0% | 92.0% |
| `structured_pipeline_oracle_classify` | 60.0% | 100.0% |
| `structured_pipeline_twostep` | 22.0% | 92.0% |
| `structured_pipeline_oracle_twostep` | 26.0% | 100.0% |
| **Phi-4 14B** | | |
| `structured_pipeline_phi4_extract` | 64.0% | 92.0% |
| `structured_pipeline_oracle_phi4_extract` | 72.0% | 100.0% |
| `structured_pipeline_phi4_classify` | 80.0% | 92.0% |
| `structured_pipeline_oracle_phi4_classify` | 88.0% | 100.0% |
| `structured_pipeline_phi4_twostep` | ? | ? |
| `structured_pipeline_oracle_phi4_twostep` | ? | ? |
| `structured_pipeline_phi4_paraaware` | ? | ? |
| `structured_pipeline_oracle_phi4_paraaware` | ? | ? |

### 5. Interpret and document

The complete matrix tells us:

- **Per prompt mode**: Does model scaling help consistently, or only for certain prompt strategies?
- **Per model**: What is the best prompt strategy for each model?
- **Overall**: Which combinations are worth running at full scale in Sprint C3?

Update `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` and `docs/RESEARCH_LOG.md` with the complete 2×4 matrix and analysis.

---

## Acceptance Criteria

- [ ] 4 new pipeline configs created (Phi-4 × {twostep, paraaware} × {pipeline, oracle})
- [ ] Proxy modules and pseudo-index dirs created
- [ ] 20-query comparison: complete 2 models × 4 prompt modes matrix filled
- [ ] 50-query pipeline test: 4 new Phi-4 conditions run, results in master table
- [ ] Error breakdown for Phi-4 twostep and paraaware
- [ ] Timing reported
- [ ] No breaking changes to existing code
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3 — next)
- Other models beyond Phi-4 and Llama
- New prompt strategies
- Fine-tuning
