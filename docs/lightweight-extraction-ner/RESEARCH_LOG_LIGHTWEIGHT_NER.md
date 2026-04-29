# Research Log: Token-Level BIO/NER Tagging for Parametric Extraction

**Branch:** `lightweight-extraction-ner`
**Started:** 2026-04-30
**Parent branch:** `research/lightweight-extraction` (CLS multi-head classifier — closed)
**Protocol:** `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md`

---

*Newest entries at the top. Updated after every sprint.*

---

## Sprint LWN-01 — Branch Setup & Phase A (BIO Training Data Preparation)

**Date:** 2026-04-30
**Tasks completed:** A1 (branch + docs), A2 (BIO label generator), A3 (manual validation), A4 (split + parity check)

### What changed
- Created branch `lightweight-extraction-ner` from `research/lightweight-extraction` at `d38b0b1`.
- Created `docs/lightweight-extraction-ner/` with the protocol, an empty research log, and `CLAUDE_LIGHTWEIGHT_NER.md` (branch context for Claude Code).
- Added third **Branch note** line to top-level `CLAUDE.md`.
- Created `docs/sprints/SPRINT_LWN_01.md` documenting this sprint with full A2/A3/A4 reports.
- Implemented `src/pipeline/training/data_prep_bio.py` — produces `bio_training_data.parquet` and `bio_label_inventory.json`.
- Implemented `src/pipeline/training/validate_bio_alignment.py` — A3 validation tool (programmatic span reconstruction + canonical-value comparison on a 200-row stratified sample).
- Produced output artifacts in `data/processed/`: `bio_training_data.parquet`, `bio_label_inventory.json`, `bio_training_data_samples.txt`, `bio_validation_report.md`, `bio_validation_summary.json`.

### Key technical decisions

| Decision | Choice | Rationale |
|---|---|---|
| Source column | `parameters_norm` (richer; has `value_norm` pre-computed) | Matches protocol §4.5 reference; cleaner than the raw `parameters` field used by the CLS classifier code |
| Anchoring strategy | Unified `_find_anchored_unoccupied` matcher (non-alphanumeric boundaries on both sides) | Replaces `\b…\b` regex which fails on values containing `''` (DIÁMETROS), `<`, `>`, `=`, `/`. One algorithm handles numeric and text axes. |
| Same-surface collisions | Per-row occupancy tracking | When TRABAJO and BANDA both equal `no aplica` (OEB250$, 18 rows), each axis aligns to its own occurrence rather than colliding. |
| `Normal` terrain (5,760 rows) | `SURFACE_OVERRIDES` table mapping `(TIPO DE TERRENO, normal)` → `[cualquier clase de terreno, cualquier tipo de terreno]` | The canonical value `Normal` has no literal surface form in long text; both observed phrases are catalog-stable so the override is auditable. |
| BIO label scheme | 27 labels: `O` + 13 × `B-{axis}` + 13 × `I-{axis}` | Single shared head (protocol §4.2): consolidates training signal for axes recurring across multiple groups. |
| Split | `random_state=42`, concept-group stratified 80/10/10 | Identical to `data_prep.py`; verified 47,508/47,508 item_keys match split assignments in `classifier_training_data.parquet`, guaranteeing direct LW-06 comparability. |
| Tokenizer | `intfloat/multilingual-e5-base` with `return_offsets_mapping=True`, `max_length=512` | Same encoder as Stage 1 + CLS classifier; offsets enable char→subword propagation of BIO labels. |

### Alignment results (full corpus, 47,508 leaf rows)

| Bucket | Count |
|---|---|
| `high` (direct anchored match) | 230,235 |
| `surface` (override applied) | 5,760 |
| `failed` | 0 |
| `failed_overlap` / `failed_truncated` | 0 |
| **Total axis occurrences** | **235,995 (100.0% aligned)** |

Per-axis success rate: every one of the 13 axes at 100.0%. Of note:
- `BANDA DE MANTENIMIENTO`, `TRABAJO`, `Nº TUBOS`: 47k+ occurrences each, all aligned via direct match.
- `DIÁMETROS` (2,520 rows in OEB170$, inches notation): aligned via the new boundary-aware anchored matcher.
- `TIPO DE TERRENO=Normal` (5,760 rows): aligned via surface override.
- `DIÁMETRO`, `MATERIAL`, `TUBO`, `PROFUNDIDAD`, `PAVIMENTO`, `TERRENO`, `TIPO DE ACCIÓN`: low-count axes (15–1,080 rows), all 100%.

### Manual validation (A3, 200 rows)

| Metric | Value |
|---|---|
| Sampled rows (stratified across 13 axes, seed=42) | 200 unique |
| Fully correct rows | **200 (100.0%)** |
| Gate (protocol §10) | ≥95% — **passed** |

Method: programmatic span-text reconstruction (using token offsets) compared against the canonical `value_norm` (or surface override). Per-row markdown details in `data/processed/bio_validation_report.md`.

### Known limitations carried forward
- The corpus's `TIPO DE TERRENO=Normal` cases are aligned to a surface phrase that does not contain the canonical value `Normal`. The downstream span normalizer (Sprint LWN-02 / B2) will need an explicit rule mapping `cualquier clase/tipo de terreno` → `Normal`. Documented in protocol §4.4 risk: the deterministic normalizer must accept these surface variants.
- All training data is catalog-generated (long text). The cross-distribution test against short-text queries is the deliberate property under test (protocol §1) and will be the central comparison in Sprint LWN-03.

### Next sprint
**Sprint LWN-02:** Phase B — model class (`param_extractor_bio.py`), span normalizer (`span_normalizer.py`), training script (`train_bio_tagger.py`), CPU sanity test (B4). Stops before the full GPU training run (B5) so loss curves, val span-F1, and end-to-end query accuracy can be reviewed first.

---
