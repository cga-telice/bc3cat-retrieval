# Sprint 10 — Reproduce Results with Phi-4 14B

**Tasks from backlog:** LLM model comparison
**Prerequisites:** Sprint 09 complete, Ollama running in Docker

---

## Context

All LLM prompt strategies with Llama 3.1 8B underperformed the rule-based extractor on catalog-generated queries. The best LLM result was `extract` mode at 87.8% per-axis / 70% per-query, vs. rules at 100% / 100%.

Open question: **is this a model capability issue or inherent to the task?** Phi-4 14B is a significantly stronger reasoning model (14B params, Microsoft's reasoning-focused architecture) that fits in the RTX 4090's 24GB VRAM. If Phi-4 closes the gap with rules, the problem was model capability. If not, the task genuinely favors string matching on this dataset.

We test Phi-4 with the same prompt conditions to get a clean comparison.

Read `CLAUDE.md` and `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for full project context.

---

## Objectives

### 1. Pull Phi-4 14B in Ollama

```bash
docker-compose exec ollama ollama pull phi4:14b
```

Verify it's available:
```bash
docker-compose exec ollama ollama list
# Should show both llama3.1:8b and phi4:14b
```

**Note:** Check the exact model tag available in Ollama. It might be `phi4`, `phi4:14b`, `phi4:latest`, or similar. Use `docker-compose exec ollama ollama search phi4` or check `ollama.com/library/phi4` if needed. Document the exact tag used.

### 2. Create Phi-4 pipeline configs

Create configs for Phi-4 with the two most informative prompt modes — `extract` (best LLM result) and `classify` (tests closed-set selection with a stronger model):

- **`configs/structured_pipeline_phi4_extract.yaml`** — E5 + Phi-4 extract + catalog
- **`configs/structured_pipeline_phi4_classify.yaml`** — E5 + Phi-4 classify + catalog
- **`configs/structured_pipeline_oracle_phi4_extract.yaml`** — Oracle + Phi-4 extract
- **`configs/structured_pipeline_oracle_phi4_classify.yaml`** — Oracle + Phi-4 classify

These should be identical to the existing Llama configs except for `model: phi4:14b` (or whatever the exact tag is). Create proxy modules and pseudo-index dirs as needed.

The `LLMParamExtractor` already accepts a `model` parameter, so no code changes should be needed — just config changes.

### 3. Run the 20-query Stage 2 comparison

Run the same 20 queries (same `random_state=42`, same stratified sampling) with:

1. **Rules** — baseline (expected: 100% / 100%)
2. **Llama 3.1 8B extract** — Sprint 04 reference (expected: 87.8% / 70.0%)
3. **Llama 3.1 8B classify** — Sprint 07 reference (expected: 86.5% / 65.0%)
4. **Phi-4 14B extract** — new
5. **Phi-4 14B classify** — new

Report for each:
- Per-axis accuracy
- Per-query accuracy
- Error breakdown: normalization errors vs. omission errors
- Average time per query

**Key comparison:** Does Phi-4 extract beat Llama extract (87.8%)? Does Phi-4 classify beat Llama classify (86.5%)? Does either Phi-4 variant approach rules (100%)?

### 4. Run 50-query pipeline sanity test

Run the 4 Phi-4 pipeline conditions on 50 queries. Compare with the existing results:

| Condition | item Acc@1 | parent Acc@1 |
|---|---|---|
| `structured_pipeline_rules` | 84.0% | 92.0% |
| `structured_pipeline` (Llama extract) | 68.0% | 92.0% |
| `structured_pipeline_classify` (Llama) | 52.0% | 92.0% |
| `structured_pipeline_phi4_extract` | ? | ? |
| `structured_pipeline_phi4_classify` | ? | ? |
| `structured_pipeline_oracle_rules` | 92.0% | 100.0% |
| `structured_pipeline_oracle` (Llama extract) | 76.0% | 100.0% |
| `structured_pipeline_oracle_classify` (Llama) | 60.0% | 100.0% |
| `structured_pipeline_oracle_phi4_extract` | ? | ? |
| `structured_pipeline_oracle_phi4_classify` | ? | ? |

### 5. Interpret and document

The results will fall into one of these scenarios:

- **Phi-4 ≈ Llama** → The problem is inherent to the task, not model capability. LLMs add no value on catalog-generated queries regardless of model size. Strong paper conclusion.
- **Phi-4 > Llama but < Rules** → Larger models help but can't match string matching on this input distribution. Scaling helps but doesn't solve the fundamental issue.
- **Phi-4 ≈ Rules** → The problem WAS model capability. Phi-4's reasoning is sufficient for precise parameter extraction. Changes the paper narrative significantly.

Document the Phi-4 model tag, VRAM usage, and any observations about response quality (does Phi-4 still reformats values? still omits? different error patterns?).

---

## Acceptance Criteria

- [ ] Phi-4 14B pulled and verified in Ollama
- [ ] 4 new pipeline configs created (Phi-4 × {extract, classify} × {pipeline, oracle})
- [ ] Proxy modules and pseudo-index dirs created
- [ ] 20-query comparison: all 5 methods tested (rules, Llama extract/classify, Phi-4 extract/classify)
- [ ] 50-query pipeline test: 4 Phi-4 conditions run, results compared
- [ ] Error breakdown: normalization vs. omission for Phi-4 vs. Llama
- [ ] Timing reported for Phi-4 (expected: slower than Llama due to larger model)
- [ ] VRAM usage noted
- [ ] No breaking changes to existing code
- [ ] Documentation updated (`docs/CLAUDE_STRUCTURED_RETRIEVAL.md`, `docs/RESEARCH_LOG.md`)

---

## Out of Scope

- Full 16,590-query evaluation (Sprint C3 — after model comparison is settled)
- Phi-4 with twostep or paraaware prompts (those strategies are ruled out regardless of model)
- Other models (Qwen, DeepSeek, etc.)
- Fine-tuning
