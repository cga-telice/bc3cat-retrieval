# Sprint LW-07 — Frozen Encoder Baseline Experiment

**Prerequisites:** Sprint LW-06 complete (training data fix, full FT results documented)

---

## Problem

Sprint LW-06 showed full fine-tuning of E5 achieves 99.6% val query accuracy on long text but collapses to ~21% item Acc@1 on short-text queries. The error analysis (`RESEARCH_LOG_LIGHTWEIGHT-06_Analysis.md`) pointed to **format-specific pattern matching**: the model learns surface patterns of the long-text format rather than semantic parameter extraction.

## Hypothesis

If we freeze the E5 encoder and only train the 97 classification heads, the model must rely on E5's pretrained multilingual semantic representations. Two possible outcomes:

- **Frozen >70% on short text** → full FT is counterproductive (learns format-specific patterns that hurt generalization); frozen heads over E5 are enough
- **Frozen ≈ 21% on short text or worse** → the problem is elsewhere (E5's pretrained CLS does not encode enough parameter signal; task requires genuine representation adaptation)

## Experimental Setup

- **Model architecture:** same 97 multi-head classifier
- **Training data:** same `OEB_long_norm.parquet` long text
- **Hyperparameters:** same 5 epochs, batch 32, lr 2e-5
- **Only difference:** `--freeze-encoder` flag added to `train_classifier.py` — encoder `requires_grad=False`, only ~45K head parameters trained
- **Evaluation:** same 16,590 short-text query set, both pipeline and oracle conditions

## Steps

### Step 1: Add `--freeze-encoder` flag to training script

Modified `src/pipeline/training/train_classifier.py` to support encoder freezing before optimizer construction.

### Step 2: Train frozen encoder (5 epochs, RTX 4090)

```bash
docker exec jupyter-pytorch bash -c "cd /work && python -m src.pipeline.training.train_classifier \
    --epochs 5 --batch-size 32 --device cuda \
    --freeze-encoder --output-dir models/e5_classifier_frozen"
```

### Step 3: Create pipeline infrastructure for frozen variant

- `index/structured_pipeline_classifier_frozen/` (meta.json points to `models/e5_classifier_frozen`)
- `index/structured_pipeline_oracle_classifier_frozen/` (oracle variant)
- `src/retrievers/structured_pipeline_classifier_frozen.py` (proxy re-exporting `load`)
- `src/retrievers/structured_pipeline_oracle_classifier_frozen.py` (proxy re-exporting `load`)

### Step 4: Full evaluation (16,590 queries, both conditions)

```bash
docker exec jupyter-pytorch bash -c "cd /work && python scripts/run_full_eval.py structured_pipeline_classifier_frozen --device cuda"
docker exec jupyter-pytorch bash -c "cd /work && python scripts/run_full_eval.py structured_pipeline_oracle_classifier_frozen --device cuda"
```

## Acceptance Criteria

- [x] `--freeze-encoder` flag implemented and tested
- [x] Frozen model trained — checkpoint at `models/e5_classifier_frozen/model.pt`
- [x] Pipeline infrastructure (index dirs + proxies) created
- [x] Both full evaluations complete on 16,590 queries
- [x] `metrics_dual.json` produced for both conditions
- [x] Comparison table added to research log
