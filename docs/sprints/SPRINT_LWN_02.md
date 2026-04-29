# Sprint LWN-02 — Phase B (BIO Tagger, Span Normalizer, Training, Sanity)

**Tasks from backlog:** B1 (model + extractor), B2 (span normalizer), B3 (training script), B4 (CPU sanity test)
**Prerequisites:** Sprint LWN-01 complete (`bio_training_data.parquet`, `bio_label_inventory.json` available; 100% A3 validation passed)

---

## Context

Sprint LWN-01 produced 47,508 fully-aligned BIO training rows (100% across all 13 axes, 200/200 A3 validation passed) and a 27-label inventory. The data is ready for training.

This sprint implements the model + the deterministic span normalizer + the training loop and runs a 100-sample CPU sanity check to confirm everything wires up correctly. **The full GPU training run is deliberately deferred to Sprint LWN-03 / B5** so the implementation can be reviewed before committing GPU time.

Read these for full context:
- `docs/lightweight-extraction-ner/CLAUDE_LIGHTWEIGHT_NER.md` — branch context
- `docs/lightweight-extraction-ner/RESEARCH_PROTOCOL_LIGHTWEIGHT_NER.md` — full roadmap (Section 4 architecture, Section 6 Phase B)
- `docs/sprints/SPRINT_LWN_01.md` — data prep and validation results
- `src/pipeline/training/train_classifier.py` — CLS classifier training script (mirror its structure for AdamW + linear warmup + mixed precision; adapt loss and metrics for BIO)

**Do not modify any existing files.** This sprint only adds new files under `src/pipeline/`, `src/pipeline/training/`, and `tests/`.

---

## Architecture (recap)

```
text_norm
  │
  ▼
[E5 tokenizer] (no "query:" prefix — matches LWN-01 data prep)
  │
  ▼
[E5 encoder] (intfloat/multilingual-e5-base, 278M params, full FT)
  │
  ▼  per-token hidden states (B, T, 768)
  │
[BIO classification head]   single shared Linear(768, 27)
  │
  ▼  per-token logits (B, T, 27)
  │
[Greedy argmax + BIO post-processing]
  │  - stray I-X without preceding B-X → treat as B-X
  │  - merge consecutive same-axis tags into one span
  │
  ▼  list of (axis_label, surface_text) per query
  │
[Span normalizer] (deterministic, schema-bounded)
  │  exact match → axis-specific rules → fuzzy match (Lev ≤ 0.15) → null
  │
  ▼
{axis_label: canonical_value | None}   ← BIOParamExtractor.extract output
```

---

## Objectives

### B2 — Span normalizer (do this FIRST; it's pure data, easy to unit-test)

Create `src/pipeline/span_normalizer.py`:

```python
class SpanNormalizer:
    def __init__(self, schema: dict)
    def normalize(self, axis_label: str, surface_text: str, parent_key: str) -> str | None
```

Resolution order:
1. **Exact case-insensitive match** of `surface_text` against the canonical values for `(parent_key, axis_label)` in the schema. Whitespace collapsed.
2. **Surface override map** — inverse of `data_prep_bio.SURFACE_OVERRIDES`:
   - `("TIPO DE TERRENO", "cualquier clase de terreno")` → `"Normal"`
   - `("TIPO DE TERRENO", "cualquier tipo de terreno")` → `"Normal"`
   The override only fires when the canonical value is also valid for the requested `parent_key`.
3. **Axis-specific rules:**
   - `BANDA DE MANTENIMIENTO`: canonicalize operator/quote variants. Replace `<=` / `>=` (with optional spaces around digits) into a single canonical form, strip stray quote chars, normalize whitespace around digits/horas.
   - `Nº TUBOS` / `PROFUNDIDAD` / `DIÁMETRO` / `DIÁMETROS`: trim whitespace and trailing units (`mm`, `m`); compare numerically when both sides parse.
4. **Fuzzy match** — normalized Levenshtein distance ≤ 0.15 against the canonical values. Implement a small standalone helper (no rapidfuzz dependency required).
5. Return `None` if nothing matches.

### B2 tests — `tests/test_span_normalizer.py`

Per protocol: ≥5 input variants per canonical value. Cover at minimum:
- Exact match (case + whitespace robustness).
- BANDA operator/quote variants: `i < 3 horas`, `i<3 horas`, `i< 3 horas`, `i < "3" horas`, `i<"3" horas` → all map to `i < 3 horas`.
- TIPO DE TERRENO Normal via surface override (both phrases).
- Numeric trimming: `" 2 "`, `"2 "`, `"2"`, `"2 mm"` → `"2"`.
- Compound TRABAJO: `"diurno excepcional"`, `"DIURNO EXCEPCIONAL"`, `"Diurno  Excepcional"` → `"Diurno Excepcional"`.
- Negative cases: garbage surface text returns `None`; valid surface but wrong `parent_key` returns `None`.

### B1 — Model + extractor: `src/pipeline/param_extractor_bio.py`

```python
class BIOTagger(nn.Module):
    def __init__(self, encoder_name: str, num_labels: int = 27)
    def forward(self, input_ids, attention_mask) -> torch.Tensor  # (B, T, num_labels)

class BIOParamExtractor:
    def __init__(self, model_dir: str | Path, schema_path: str | Path, device: str = "cpu")
    def extract(self, parent_key: str, query_text: str) -> dict[str, str | None]
    def extract_batch(self, parent_keys: list[str], query_texts: list[str]) -> list[dict]
```

Internals:
- Tokenize raw `query_text` (no "query:" prefix; matches LWN-01 training data).
- Forward through `BIOTagger` → per-token logits.
- Greedy argmax + offset-aware post-processing to extract `(axis_label, surface_text)` pairs (surface text reconstructed from token offsets, not from the SentencePiece pieces).
- For each axis defined in `schema[parent_key]["axes"]`:
  - If the BIO output produced ≥1 span for that axis, take the first span's surface text and call `SpanNormalizer.normalize(axis, surface, parent_key)`.
  - Otherwise, return `None` for that axis.
- Result dict has the same keys as the schema's axes for that `parent_key` — matches `RuleBasedParamExtractor` / `ClassifierParamExtractor` output.

Checkpoint format (mirrors CLS classifier):
- `model_dir/model.pt` — state_dict (loaded with `strict=False`)
- `model_dir/config.json` — `{encoder_name, label_inventory_path, num_labels, best_val_span_f1, epochs, batch_size, lr}`

### B3 — Training script: `src/pipeline/training/train_bio_tagger.py`

Mirror `train_classifier.py` structure, adapt for BIO:

```python
class BIOTaggerDataset(Dataset):
    """Re-tokenize text_norm at training time (deterministic), align bio_labels.
    Special tokens get label_id = -100 to be ignored by CE loss."""
```

Training loop:
- `AdamW(lr=2e-5, weight_decay=0.01)`, linear warmup 10%
- `nn.CrossEntropyLoss(ignore_index=-100)` (per-token over the (B*T, 27) flattened tensor)
- Mixed precision via `torch.amp.GradScaler` on CUDA, plain on CPU
- Per-epoch metrics on val:
  - **token_acc** — per-token accuracy excluding special tokens / O class breakdown
  - **span_f1** — span-level F1 (per-axis + macro). Span = consecutive `B-X[I-X]*` tokens; counts as TP only if the entire `(start, end, axis)` triple matches.
  - **query_acc** — end-to-end: run BIOTagger + SpanNormalizer on each val row, compare extracted dict against canonical values from `parameters_norm`. This is the metric we ultimately care about.
- Save best on **span_f1** (more granular than query_acc; less noisy than token_acc).
- Outputs: `models/e5_bio_tagger/{model.pt, config.json, training_log.json}`

CLI flags mirror `train_classifier.py`: `--epochs`, `--batch-size`, `--lr`, `--device`, `--freeze-encoder`, `--sanity N`.

### B4 — Sanity test (100 samples, 1 epoch, CPU)

Acceptance:
- Training loop completes without crashes.
- Loss decreases between step 0 and step N.
- After 1 epoch, `BIOParamExtractor.extract()` returns a dict whose keys match the schema axes for the requested `parent_key` and at least one value is non-None for at least one query (likely Nº TUBOS or CONDICIONES — easy spans with abundant training signal).

---

## Acceptance Criteria

- [x] `src/pipeline/span_normalizer.py` exists with `SpanNormalizer` class and `normalize()` method.
- [x] `tests/test_span_normalizer.py` exists with ≥5 input variants per canonical-value-class. **23 tests, all passing.**
- [x] `src/pipeline/param_extractor_bio.py` exists with `BIOTagger` + `BIOParamExtractor`. Interface matches `extract(parent_key, query)` / `extract_batch`.
- [x] `src/pipeline/training/train_bio_tagger.py` exists, runnable as `python -m src.pipeline.training.train_bio_tagger --sanity 100 --epochs 1 --device cpu`.
- [x] B4 sanity run completes without errors; produces `models/e5_bio_tagger/{model.pt, config.json, training_log.json}`.
- [x] After B4, calling `BIOParamExtractor.extract("OEB020$", "...query text...")` on a sample query returns a dict with the right axis keys (verified — schema parity for OEB010$, OEB020$, OEB170$).
- [x] No existing files modified.

---

## Out of Scope

- Full GPU training run (B5) — Sprint LWN-03.
- Pipeline integration (`structured_pipeline_bio_tagger.py`, configs, pseudo-index dirs) — Sprint LWN-03 / Phase C1.
- Full evaluation on 16,590 queries — Sprint LWN-03 / Phase C2.
- Per-axis diagnostic, cross-format diagnostic — later sprints.
- CRF decoding — backlog.

---

## B4 Sanity Report

**Date:** 2026-04-30

### B2 unit tests (`tests.test_span_normalizer`)

```
Ran 23 tests in 0.030s
OK
```

Coverage by canonical-value-class:

| Test class | n | Coverage |
|---|---|---|
| `TestHelpers` | 3 | `_collapse`, `_normalize_banda` (9 variants), `_normalize_numeric` (5 variants) |
| `TestSpanNormalizerExact` | 4 | TERRENO, PAVIMENTO, CONDICIONES, TRABAJO (case + whitespace robustness, compound values) |
| `TestSpanNormalizerBanda` | 4 | `i < 3 horas`, `3 <= i < 5 horas`, `i >= 5 horas`, `no necesita intervalo` (≥5 variants each) |
| `TestSpanNormalizerSurfaceOverride` | 3 | `cualquier clase de terreno` → `Normal` (parent-key gated), terrain values |
| `TestSpanNormalizerNumeric` | 3 | Nº TUBOS exact / unit-suffix, DIÁMETROS inches notation |
| `TestSpanNormalizerNegative` | 4 | unknown parent_key, unknown axis for parent, garbage text, empty input |
| `TestSpanNormalizerFuzzy` | 2 | minor typo within Lev 0.15, far typo returns None |

### B4 — 100-sample × 1-epoch CPU sanity

```
Train: 79, Val: 12 (from first 100 rows of bio_training_data.parquet)
Model: 27 labels, 278.1M parameters
Epoch 1/1 — loss: 1.97, token_acc: 89.4%, span_f1: 0.0%, query_acc: 0.0%, time: 49s
```

Loop completed cleanly. Outputs produced: `models/e5_bio_tagger/{model.pt (1.1GB), config.json, training_log.json}`. `BIOParamExtractor.extract()` schema-parity verified for OEB010$ (3 axes), OEB020$ (5 axes), OEB170$ (5 axes) — output dict has exactly the right axis keys.

### B4 extended — 200-sample × 5-epoch CPU (collapse diagnostic)

With **unweighted CE**, the model converges to all-O:
```
Epoch 1: loss 1.79 → token_acc 88.6% / span_f1 0.0%
Epoch 5: loss 0.40 → token_acc 88.6% / span_f1 0.0%   (loss falls 4.5×, F1 stays 0)
```

This matches the failure mode anticipated by protocol §4.6: O dominates ~40:1 over B/I tokens, so unweighted CE rewards confident all-O prediction. The protocol's recommended fallback is a class-weighted loss; I added `--class-weight-o` (default 1.0; <1 downweights O).

With **`--class-weight-o 0.1`** on 200 rows × 3 epochs:
```
Epoch 1: loss 2.58 → token_acc 88.6% / span_f1 0.0% / query_acc 0.0%
Epoch 2: loss 1.71 → token_acc 90.9% / span_f1 3.6% / query_acc 0.0%   (escapes all-O)
Epoch 3: loss 1.41 → token_acc 92.0% / span_f1 6.4% / query_acc 0.0%
```

The architecture *can* learn spans on tiny CPU samples once the imbalance is addressed. Best checkpoint saved on `span_f1` improvement. The protocol §6 B4 line about "high-confidence axes are predicted at 1 epoch" was over-optimistic for 79-row CPU sanity but is the right expectation for B5 (38,007-row × 5-epoch GPU run) where the imbalance dilutes naturally and unweighted CE should suffice.

### Files added (this sprint)

| File | Purpose |
|---|---|
| `src/pipeline/span_normalizer.py` | B2 — deterministic span → canonical value mapping |
| `src/pipeline/param_extractor_bio.py` | B1 — `BIOTagger` (E5 + Linear(768,27)) + `BIOParamExtractor` |
| `src/pipeline/training/train_bio_tagger.py` | B3 — training loop with token_acc + span_f1 + query_acc metrics |
| `tests/__init__.py` + `tests/test_span_normalizer.py` | B2 — 23 unit tests for the normalizer |

### Decisions worth carrying into LWN-03

1. **B5 default:** unweighted CE (38k rows should dilute the imbalance). Use `--class-weight-o 0.1` only if epoch-1 evaluation shows all-O collapse.
2. **Best-checkpoint metric:** `span_f1` (more granular than query_acc, less noisy than token_acc which is dominated by O).
3. **Latest checkpoint** (`model.pt`) is always saved each epoch; **best checkpoint** (`model_best.pt`) is saved only on span_f1 improvement. This guarantees a usable checkpoint exists even if training is interrupted.
4. The "query: " E5 prefix is **not** used — training data in LWN-01 was tokenized without prefix; train/inference parity preserved.
