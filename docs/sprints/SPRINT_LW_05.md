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

- [x] Both conditions complete on 16,590 queries
- [x] `runs/<condition>/metrics_dual.json` produced for each
- [x] Results compared against baselines (rules, Phi-4, Llama)

## Note (post-sprint)

Results from this sprint (96.6% item Acc@1) are **invalidated** due to data leakage: the classifier was trained on `OEB_short_norm.parquet`, the same distribution as the 16,590 evaluation queries. See Sprint LW-06 for the fix.
