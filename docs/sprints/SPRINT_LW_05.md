# Sprint LW-05 — Full Evaluation (16,590 queries)

**Tasks from backlog:** C2 (full evaluation run)
**Prerequisites:** Sprint LW-04 complete (pipeline integration verified)

---

## Objectives

1. Run `run_full_eval.py` for both classifier conditions on 16,590 queries
2. Compare item Acc@1 against all baselines

## Commands

```bash
# In Docker (jupyter-pytorch container)
python scripts/run_full_eval.py structured_pipeline_classifier --device cuda
python scripts/run_full_eval.py structured_pipeline_oracle_classifier --device cuda
```

## Acceptance Criteria

- [ ] Both conditions complete on 16,590 queries
- [ ] `runs/<condition>/metrics_dual.json` produced for each
- [ ] Results compared against baselines (rules, Phi-4, Llama)
