# Sprint LW-01 — Training Data Generation

**Tasks from backlog:** A2 (training data generation)
**Prerequisites:** Branch setup complete (Sprint LW-00)

---

## Context

This is the first implementation sprint on the `lightweight-extraction` branch. The goal is to prepare the training dataset for the multi-head E5 classifier that will replace LLM-based parameter extraction in Stage 2.

Read these for full context:
- `CLAUDE.md` at repo root — project overview + branch pointers
- `docs/lightweight-extraction/CLAUDE_LIGHTWEIGHT.md` — this branch's pipeline context
- `docs/lightweight-extraction/RESEARCH_PROTOCOL_LIGHTWEIGHT.md` — full roadmap (Section 4 for architecture, Section 6 for task A2)

**Do not modify any existing files.** This sprint only adds new files under `src/pipeline/training/` and `data/processed/`.

---

## Data Landscape

| Source | Path | Rows | Notes |
|---|---|---|---|
| Short queries (normalized) | `data/processed/OEB_short_norm.parquet` | 47,513 | `text_norm` column is the query text; `parameters` column has ground-truth labels |
| Concept schema | `data/processed/OEB_concept_schema.json` | 25 groups | 97 (group, axis) pairs, 459 (group, axis, value) triplets |

Key facts:
- `parameters` is a dict: `{"A": {"label": "TERRENO", "values": [{"label": "a", "value": "blando"}]}, "B": ..., "D": None, ...}`
- Axis keys with `None` value mean that axis is unused for this concept group — skip them
- Each leaf item has exactly one value per axis in `values[0]["value"]`
- 5 non-leaf rows exist (parent_key doesn't end in `$`: OEB060, OEB210, OEB220, OEB260, OEB270) — exclude them
- 47,508 leaf items remain after filtering

---

## Objectives

### 1. Create the training package

Create `src/pipeline/training/` with `__init__.py` and `data_prep.py`.

### 2. Build the training data generator

Write `src/pipeline/training/data_prep.py` that:

1. Loads `OEB_short_norm.parquet` and `OEB_concept_schema.json`
2. Filters to leaf items only (parent_key ends in `$`)
3. For each row, extracts:
   - `query_text`: from `text_norm` column
   - `item_key`: the item identifier
   - `parent_key`: the concept group
   - `labels`: a dict `{axis_label: value}` for each non-None axis in `parameters`
     - Example: `{"TERRENO": "blando", "PAVIMENTO": "sin reposición", "CONDICIONES DE EJECUCIÓN": "Volumen relevante"}`
   - Axis labels should be stripped of leading/trailing whitespace (the raw data has spaces like `" TERRENO "`)
   - Values should also be stripped
4. Builds a label encoder mapping: for each (parent_key, axis_label), maps value strings to integer class indices. Index 0 = null class, indices 1..N = sorted axis values from the schema.
5. Saves:
   - `data/processed/classifier_training_data.parquet` — columns: `query_text`, `item_key`, `parent_key`, `labels` (dict as JSON string)
   - `data/processed/classifier_label_encoders.json` — the label encoder mapping:
     ```json
     {
       "OEB010$": {
         "TERRENO": {"null": 0, "blando": 1, "Bajo vías": 2, "Rocoso": 3},
         "PAVIMENTO": {"null": 0, "con reposición": 1, "sin reposición": 2},
         ...
       },
       ...
     }
     ```
6. Splits the data: 80/10/10 train/val/test, stratified by `parent_key` (concept group). Adds a `split` column to the parquet.

### 3. Run and verify

Run the script and print:
- Total rows per split (train/val/test)
- Number of concept groups represented in each split
- Distribution of axis values for 2-3 concept groups (verify no class is missing from train)
- Verify label encoders: total heads (expected: 97), total classes including null
- Spot-check 3 rows: verify labels match the raw `parameters` column

---

## Acceptance Criteria

- [ ] `src/pipeline/training/__init__.py` exists
- [ ] `src/pipeline/training/data_prep.py` exists and is runnable standalone (`python -m src.pipeline.training.data_prep` or as script)
- [ ] `data/processed/classifier_training_data.parquet` is produced with columns: `query_text`, `item_key`, `parent_key`, `labels`, `split`
- [ ] `data/processed/classifier_label_encoders.json` is produced with correct structure
- [ ] 47,508 leaf rows in the output (5 non-leaf rows excluded)
- [ ] 97 (group, axis) heads in label encoders
- [ ] 80/10/10 split stratified by parent_key
- [ ] All axis values from schema appear in train split
- [ ] Spot-check of 3 rows passes
- [ ] No existing files modified

---

## Out of Scope

- Model implementation (that's Sprint LW-02, Phase B1)
- Training loop (Sprint LW-02/03)
- Query augmentation (Phase D, much later)
- Installing new dependencies (pandas, scikit-learn are already available)
