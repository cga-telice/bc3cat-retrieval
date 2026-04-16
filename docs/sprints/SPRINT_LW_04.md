# Sprint LW-04 — Pipeline Integration

**Tasks from backlog:** C1 (pipeline integration)
**Prerequisites:** Sprint LW-03 complete (trained model checkpoint)

---

## Context

Classifier trained (99.7% val_query_acc). This sprint wires it into the structured pipeline as a new Stage 2 variant.

## Objectives

1. Add `classifier` branch to `load()` in `structured_pipeline.py`
2. Create proxy modules and YAML configs for pipeline + oracle variants
3. Add variants to `setup_structured_index.py` and create pseudo-index dirs
4. Test full pipeline: `search()` and `search_batch()` return correct results

## Acceptance Criteria

- [x] `load('index/structured_pipeline_classifier')` loads correctly
- [x] `search()` returns top-K indices and scores
- [x] `search_batch()` handles multiple queries
- [x] 24 total index directories verified
- [x] No existing pipeline functionality broken
