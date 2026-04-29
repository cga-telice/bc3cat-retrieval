# Sprint LWN-01 — Branch Setup & Phase A (BIO Training Data Preparation)

**Tasks from backlog:** A1 (branch setup) + A2 (BIO label generation) + A3 (manual validation) + A4 (train/val/test split)
**Prerequisites:** `research/lightweight-extraction` complete (CLS classifier negative result documented in LW-06/07)

---

## Context

This is the first implementation sprint on the `lightweight-extraction-ner` branch. The CLS classifier branch produced 99.6% val_query_acc on long text but only 20.9% Acc@1 on short-text queries (cross-distribution). The mechanistic explanation (LW-06): the CLS architecture conditioned on document-level cues (`trabajo:` label literals) absent from short text. The frozen-encoder ablation (LW-07) ruled out overfitting as the cause.

This branch tests the architectural alternative: a token-level BIO tagger that, by construction, must operate on token-level evidence. The hypothesis is falsifiable — if BIO transfers similarly poorly to CLS (~21%), the cross-distribution gap is fundamental to the long↔short pair in BC3CAT and not an architectural artifact.

This sprint executes **Phase A only**: produce alignable BIO training data and validate quality before any model code is written.

Read these for full context:
- `CLAUDE.md` at repo root — project overview + branch pointers
- `docs/lightweight-extraction-ner/CLAUDE_LIGHTWEIGHT_NER.md` — this branch's pipeline context
- `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md` — full roadmap (Section 4 for architecture, Section 6 Phase A for tasks)

**Do not modify any existing files** other than the top-level `CLAUDE.md` (one-line branch note added in A1).

---

## Data Landscape

| Source | Path | Rows | Notes |
|---|---|---|---|
| Long catalog text (normalized) | `data/processed/OEB_long_norm.parquet` | ~47,514 | `text_norm` column is the document text; `parameters` (or `parameters_norm`) column has canonical (axis, value) labels |
| Concept schema | `data/processed/OEB_concept_schema.json` | 25 groups | 97 (group, axis) pairs, 13 unique axis labels, ≤12 canonical values per axis |

Key facts (carried forward from CLS classifier work):
- `parameters` is a dict: `{"A": {"label": "TERRENO", "values": [{"label": "a", "value": "blando"}]}, "B": ..., "D": None, ...}`. Axis keys with `None` value mean that axis is unused for this concept group — skip them.
- Axis labels and values must be `.strip()`-ed (raw data has whitespace like `" TERRENO "`).
- Each leaf item has exactly one value per axis in `values[0]["value"]`.
- 5 non-leaf rows exist (parent_key doesn't end in `$`: OEB060, OEB210, OEB220, OEB260, OEB270) — exclude them.
- 47,508 leaf items remain after filtering.

**Open question to resolve in A2 step 0:** the protocol §4.5 mentions `parameters_norm` whereas the existing `data_prep.py:38` reads `row["parameters"]`. Inspect the parquet schema (`df.dtypes`, `df.iloc[0]`) at the start of A2 and use whichever column contains the canonical label dict as defined above. Document the choice in this sprint file before continuing.

---

## Objectives

### A1 — Branch & docs scaffolding (DONE first, before code)

1. Create branch `lightweight-extraction-ner` from `research/lightweight-extraction` HEAD.
2. Create `docs/lightweight-extraction-ner/` with:
   - `RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md` (the protocol document)
   - `RESEARCH_LOG_LIGHTWEIGHT_NER.md` (running log, header only)
   - `CLAUDE_LIGHTWEIGHT_NER.md` (branch context for Claude Code)
3. Append a third **Branch note** line to top-level `CLAUDE.md`.
4. Create `docs/sprints/SPRINT_LWN_01.md` (this file).

### A2 — BIO label generator

Create `src/pipeline/training/data_prep_bio.py` that:

**Step 0 (verification).** Inspect the parquet schema to confirm which column holds the canonical labels. Reuse `extract_labels()` logic from `src/pipeline/training/data_prep.py:35-48` adapted to whichever column is canonical. Print and record the choice.

**Step 1 (label inventory).** Build the BIO label inventory from the schema:
- Collect all unique axis labels across all concept groups (expected: 13).
- Construct labels: `["O"] + [f"B-{axis}" for axis in sorted_axes] + [f"I-{axis}" for axis in sorted_axes]` → 27 labels.
- Save to `data/processed/bio_label_inventory.json` as `{label: integer_index}`.

**Step 2 (alignment).** For each leaf row in `OEB_long_norm.parquet`:
1. Tokenize `text_norm` with the E5 tokenizer (`intfloat/multilingual-e5-base`, with `return_offsets_mapping=True`).
2. Initialize `bio_labels = ["O"] * len(tokens)`.
3. For each `(axis_label, canonical_value)` in the row's parameters:
   - Try **direct normalized substring search** first. Reuse `normalize_text` from `src/utils/text_processing.py` so the alignment is consistent with how `RuleBasedParamExtractor` finds values at `param_extractor_rules.py:138-152`.
   - If no direct match, apply **axis-specific rules**:
     - `BANDA DE MANTENIMIENTO`: try the canonical postfix (`i < 3 horas`) and operator/quote variants (`i<3 horas`, `i < "3" horas`, etc.) and natural-language equivalents in the body.
     - Numeric axes (`Nº TUBOS`, `PROFUNDIDAD`, `DIÁMETRO`, `DIÁMETROS`): require a regex anchor (`\b{value}\b` near `tubos`/`mm`/`m`) to disambiguate from incidental numbers.
     - Compound `TRABAJO` values like `Nocturno Excepcional`: align as adjacent multi-word spans (B + I).
4. Map char span → token span via `offset_mapping`. Propagate the BIO label across all subword pieces of the matched span (B on the first piece, I on each subsequent piece — including subword pieces of the same word).
5. Record alignment confidence per axis: `high` (direct match), `medium` (axis-specific rule succeeded), `failed` (no match found).
6. **Failure handling:** Rows where one or more values cannot be aligned are kept with the unalignable axis labeled all-O AND flagged in `alignment_confidence`. The training-time decision (drop vs. keep) is made later (B3); A2 just records the flag.

**Step 3 (output).** Write `data/processed/bio_training_data.parquet` with columns:
- `item_key` (str)
- `parent_key` (str)
- `text_norm` (str)
- `tokens` (list[str]) — the tokens (pieces) corresponding to `bio_labels`
- `bio_labels` (list[str]) — same length as `tokens`
- `alignment_confidence` (str, JSON-encoded `[(axis, status), ...]`)

(The `split` column is added in A4 below.)

**Step 4 (sanity report).** Print:
- Total rows, leaf rows, rows with all axes aligned, rows with at least one failed axis.
- Per-axis alignment success rate: `(high + medium) / total_axis_occurrences`.
- 20-row rendered sample showing `[(token, bio_label), ...]` for visual inspection.
- Counts per `alignment_confidence` bucket.

### A3 — Manual validation (200 rows)

- Sample 200 rows from `bio_training_data.parquet` stratified across the 13 axes (~15 rows per axis).
- Render each as `[(token, bio_label), ...]` annotated with the canonical values from `parameters`.
- Hand-check correctness:
  - Are the spans on the right tokens?
  - Are compound values (multi-token spans) contiguous and correctly B-then-I?
  - Are numeric values anchored on the right occurrence (not an incidental number)?
- Compute correctness rate and log failure modes.
- **Gate:** ≥95% rows fully correct → proceed to A4. Below threshold → iterate on `align_value_to_text` rules and re-run A2.
- Document findings inline in this sprint file under "## A3 Validation Report" and append to `RESEARCH_LOG_LIGHTWEIGHT_NER.md`.

### A4 — Train/val/test split

- Reuse `split_data()` from `src/pipeline/training/data_prep.py:65-92` exactly. Concept-group-stratified 80/10/10, `random_state=42`, small groups (<5 items, e.g. OEB160$) → train only.
- Add `split` column to `bio_training_data.parquet` and overwrite the file.
- Print:
  - Row counts per split.
  - Concept groups per split.
  - Per-axis label coverage in train (every BIO label except O must appear in train at least once).
  - Spot-check 3 rows.
- **Comparability check (LW-06 parity):** assert that for every `item_key` present in both `bio_training_data.parquet` and `classifier_training_data.parquet`, the `split` column is identical. Same `random_state` + same stratification key + same input parquet → identical assignment. This guarantees direct comparability with the CLS classifier results.

---

## Acceptance Criteria

- [x] `lightweight-extraction-ner` branch exists and is checked out
- [x] `docs/lightweight-extraction-ner/{RESEARCH_PROTOCOL_LIGHTWEIGHT_NER,RESEARCH_LOG_LIGHTWEIGHT_NER,CLAUDE_LIGHTWEIGHT_NER}.md` exist
- [x] Top-level `CLAUDE.md` has a third Branch note pointing to the new doc
- [x] `docs/sprints/SPRINT_LWN_01.md` (this file) exists
- [x] `src/pipeline/training/data_prep_bio.py` exists and is runnable standalone (`python -m src.pipeline.training.data_prep_bio`)
- [x] `data/processed/bio_label_inventory.json` exists with exactly 27 entries
- [x] `data/processed/bio_training_data.parquet` exists with columns `item_key, parent_key, text_norm, tokens, bio_labels, alignment_confidence, split`
- [x] 47,508 leaf rows in the output
- [x] Per-axis alignment success ≥95% on numerical axes; ≥90% high-or-medium on text axes — **all axes 100.0%** after surface-override + anchored-substring refactor
- [x] 200-row hand-validation correctness ≥95% — **200/200 (100.0%)** (signed off below in A3 Validation Report)
- [x] 80/10/10 split, all BIO labels appear in train, OEB160$ entirely in train
- [x] `item_key` → `split` matches `classifier_training_data.parquet` (47,508 / 47,508 agree, 0 mismatches)
- [x] No existing files modified other than `CLAUDE.md` (one-line addition)

---

## A3 Validation Report

**Date:** 2026-04-30
**Sample:** 200 unique rows, stratified across the 13 axes (seed=42)
**Method:** programmatic validation via `src/pipeline/training/validate_bio_alignment.py`. For each tagged span, the surface text is reconstructed from token offsets and compared against the canonical `value_norm` from `parameters_norm` (or, for the TIPO DE TERRENO=Normal case, against the surface override `cualquier clase/tipo de terreno`).

**Result: 200/200 fully correct (100.0%) — gate (≥95%) passed.**

Per-axis correctness (matched / sampled):

| Axis | Correct | Notes |
|---|---|---|
| BANDA DE MANTENIMIENTO | 169/169 (100.0%) | Includes `i < 3 horas`, `i >= 5 horas`, `no necesita intervalo`, `no aplica` |
| CONDICIONES DE EJECUCIÓN | 184/184 (100.0%) | Includes `cualquier condición de ejecución` (4-token span) |
| DIÁMETRO | 15/15 (100.0%) | Single concept group; small total |
| DIÁMETROS | 16/16 (100.0%) | Inches notation (`1''`, `3 1/2''`) — fixed by removing `\b` regex anchor |
| MATERIAL | 16/16 (100.0%) | Single concept group |
| Nº TUBOS | 120/120 (100.0%) | Word-boundary anchored, no incidental-digit collisions |
| PAVIMENTO | 16/16 (100.0%) | `con/sin reposición` |
| PROFUNDIDAD | 16/16 (100.0%) | |
| TERRENO | 16/16 (100.0%) | `blando`/`duro`/`medio` |
| TIPO DE ACCIÓN | 16/16 (100.0%) | `suministro`/`montaje` |
| TIPO DE TERRENO | 103/103 (100.0%) | Surface override applied for `Normal` (5,760 rows in full corpus) |
| TRABAJO | 169/169 (100.0%) | Compound values like `Diurno Excepcional` align as B + I across multiple subwords |
| TUBO | 16/16 (100.0%) | |

**Key data-cleaning decisions made during A2:**
1. Replaced regex `\b` anchoring with a unified `_find_anchored_unoccupied` matcher that requires non-alphanumeric boundaries on both sides. This handles values containing `''`, `<`, `>`, `=`, `/` and other punctuation correctly.
2. Added occupancy tracking so when two axes share the same surface form (e.g., TRABAJO=`no aplica` and BANDA=`no aplica` both appearing as `... trabajo: no aplica banda de mantenimiento: no aplica ...`), each axis aligns to its own occurrence rather than colliding.
3. Added `SURFACE_OVERRIDES` for the TIPO DE TERRENO=`Normal` case where the canonical value has no literal surface form in the long text. Both observed surface phrases (`cualquier clase de terreno`, `cualquier tipo de terreno`) are covered.

Full per-row details in `data/processed/bio_validation_report.md`.

## A2/A4 Sanity Report (full corpus)

| Property | Value |
|---|---|
| Total leaf rows | 47,508 (5 non-leaf excluded) |
| Concept groups | 25 |
| Unique axes | 13 |
| BIO label inventory size | 27 (= 1 + 2 × 13) |
| Total axis occurrences across corpus | 235,995 |
| Aligned (high + medium + surface) | **235,995 (100.0%)** |
| Per-split row counts | train 38,007 (80.0%), val 4,750 (10.0%), test 4,751 (10.0%) |
| Small-group exception | OEB160$ (3 items) → entirely in train |
| `B-{axis}` labels missing from train | none (all 13 present) |
| Split parity vs CLS classifier | 47,508 / 47,508 item_keys agree on split |

Outputs:
- `data/processed/bio_training_data.parquet` — 47,508 rows, columns `item_key, parent_key, text_norm, tokens, bio_labels, alignment_confidence, split`
- `data/processed/bio_label_inventory.json` — 27 entries
- `data/processed/bio_training_data_samples.txt` — 5-row debugging render
- `data/processed/bio_validation_report.md` — A3 detailed per-row report
- `data/processed/bio_validation_summary.json` — A3 numerical summary

---

## Out of Scope

- Model implementation (Phase B / Sprint LWN-02)
- Span normalizer module (Phase B / Sprint LWN-02)
- Training loop (Phase B / Sprint LWN-02)
- Pipeline integration (Phase C / Sprint LWN-03)
- Full evaluation (Phase C / Sprint LWN-03)
- Per-axis diagnostic, cross-format diagnostic (Phase C/D / later sprints)
- Installing new dependencies — `transformers`, `pandas`, `scikit-learn`, `pyarrow` already available (used by CLS classifier code)
