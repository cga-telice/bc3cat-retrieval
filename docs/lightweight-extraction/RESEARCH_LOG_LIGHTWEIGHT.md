# Research Log: Lightweight Classifiers for Parametric Extraction

**Branch:** `lightweight-extraction`
**Started:** April 2026

---

*Newest entries at the top. Updated after every sprint.*

---

## Sprint LW-01 — Training Data Generation

**Date:** 2026-04-15
**What changed:**
- Created `src/pipeline/training/` package with `data_prep.py`
- Script loads `OEB_short_norm.parquet` + `OEB_concept_schema.json`, filters to 47,508 leaf items, extracts per-axis labels from `parameters` column, splits 80/10/10 stratified by concept group
- Produced `data/processed/classifier_training_data.parquet` — columns: `query_text`, `item_key`, `parent_key`, `labels` (JSON dict), `split`
- Produced `data/processed/classifier_label_encoders.json` — 97 (group, axis) heads, 556 total classes (incl. null)

**Key stats:**
- Train: 38,007 / Val: 4,750 / Test: 4,751
- 25 concept groups in train, 24 in val/test (OEB160$ has only 3 items → all in train)
- All axis values from schema present in train split
- 3 spot-checks passed

**Known issues:**
- None

---

## Sprint LW-00 — Branch Setup

**Date:** 2026-04-15
**What changed:**
- Created `lightweight-extraction` branch from `structured-retrieval` (commit `97870b1`)
- Moved prior docs to `docs/structured-retrieval/`
- Created `docs/lightweight-extraction/` with protocol, log, Claude Code context
- Updated `CLAUDE.md` with branch-specific pointers

**Known issues:**
- None
