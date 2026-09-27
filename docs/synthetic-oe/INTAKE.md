# BC3CAT-Syn on OE — branch intake

**Branch:** `research/synthetic-oe` (opened 2026-09-08, based on `main` @ `da4f3d0`).
**Goal:** run the retrieval/evaluation pipeline of this repo on the ADIF 2026 *OE* chapter
(OBRA CIVIL, 7 subchapters OEA–OEG) using the BC3CAT-Syn synthetic query sets produced in
`bc3cat-dataset` (branch `synthetic`), alongside the original resumen→texto baseline.

This document records where the data goes, where it came from, what its schema is, and
which parts of the pipeline are known to break on it. It is an intake note, not a design:
method scope, parameter handling and run layout are still open (see §5).

---

## 1. Data placement

All files live under `data/processed/` (git-ignored), next to the existing `OEB_*` files,
so the `/work/data/processed/{COLLECTION}_*` convention keeps working with `COLLECTION = "OE"`.

| File | Role | Status |
|---|---|---|
| `data/processed/OE_texto.json` | document corpus — original TEXTO, deduplicated (retrieval **targets**) | in place (2026-09-08) |
| `data/processed/OE_resumen.json` | original RESUMEN of the same leaves (resumen→texto **baseline** queries) | in place (2026-09-08) |
| `data/processed/OE_single_texto.json` | synthetic queries, **one** modification each | in place |
| `data/processed/OE_stacked_texto.json` | synthetic queries, **all** applicable modifications stacked | in place |
| `data/processed/OE_concept_schema.json` | per concept: name, axes, item_keys, num_items | in place |
| `data/processed/OE_handoff_README.md` | the handoff README shipped with the query sets | in place |

Validated on 2026-09-08 after copying from `D:/Users/cesar/Downloads/BC3CAT_Syn_OE_handoff`:
`OE_texto.json` / `OE_resumen.json` are JSON lists of `{id, item_key, parent_key, ud, concept,
parameters, text}`, **70 242 records each**, 83 distinct `parent_key`, no template rows (`#`/`$`),
no empty text, `item_key` unique and in identical order in both files, `parameters` nested in
every corpus record. All 4 439 single and 4 998 stacked `gold_item_key` exist in the corpus and
their `parent_key` matches the corpus parent. 4 leaves have resumen identical to texto.

Working-copy note: the branch is checked out in the main checkout
(`D:/Users/cesar/Dev/Phd/bc3cat-retrieval`), which is what `docker-compose` mounts as `/work`.
The app worktree `.claude/worktrees/corpus-synthetic-queries-785c03` used to open the branch is
left on a detached HEAD and can be removed; its `data/ index/ runs/ logs/ hf-cache/` entries are
NTFS junctions to the main checkout, not copies.

## 2. Provenance

- Producer: `bc3cat-dataset`, branch `synthetic`, `scripts/package_for_retrieval.py`.
- Query sets + schema versioned in `bc3cat-dataset` commit `8998875` (2026-09-08).
  SHA-256 prefixes at copy time: single `b6a43961295cc2ca`, stacked `1bde21157ef97421`,
  schema `2d3273ddb3e443a1`, texto `02a2c270d7ffe147`, resumen `0cd380e9e44ad8c5` (the two corpus files are
  git-ignored in `bc3cat-dataset` and were delivered as the folder `BC3CAT_Syn_OE_handoff`).
- Corpus source parquets: `data/synthetic/processed_OE/OE_target_long.parquet` /
  `OE_target_short.parquet` (after cross-concept twin drop OED170$→OED020$ and intra-concept
  collapse OEG010$; see `docs/synthetic/OE_dedup_report.md` there).
- Generation is deterministic and LLM-free at corpus time (LLM only authored the frozen
  rewrite menus). Reports: `docs/synthetic/OE_*_report.md`, `HANDOFF.md`, `DATA_CARD.md`
  in `bc3cat-dataset`.

### 2.1 Later deliveries

Upstream has shipped twice more since the founding delivery above. Each one — its digests, what was
verified, and the limitations it binds on which sprint — is recorded in
[`DELIVERIES.md`](DELIVERIES.md), which is a record rather than part of this contract:

| Delivered | Taken in | What |
|---|---|---|
| 2026-09-17 | S3 work item 2 | **E3 balanced dose set** (D-009): dose ladder, isolated effects, per-leaf applicability |
| 2026-09-27 | S3 work item 1 | **Duplicate-`texto` sidecar** (D-031) and the **corrected stacked set** (D-025) |

## 3. Schema as observed

Corpus record (`OE_texto.json` / `OE_resumen.json`) — same as OEB:

```json
{"id": "…", "item_key": "OEA010aaab", "parent_key": "OEA010$", "ud": "m",
 "concept": "CANALETA PVC",
 "parameters": {"A": {"label": "DIMENSIONES", "values": [{"label": "a", "value": "30x15 mm"}]}, "F": null},
 "text": "Canaleta PVC de 30x15 mm con tapa.\nTrabajo: Diurno.\n…"}
```

Synthetic query record (`OE_single_texto.json` / `OE_stacked_texto.json`):

```json
{"id": "…", "item_key": "OEA010aaba_syn_3348c2069a08",
 "parent_key": "OEA010$",            // gold at concept level
 "gold_item_key": "OEA010aaba",      // gold at item level
 "ud": "m", "concept": "CANALETA PVC",
 "parameters": {"A": "3x1.5 cm", "B": "Diurno", "F": null},   // FLAT, values may be rewritten
 "text": "Se ha implementado una canaleta PVC de 3x1.5 cm con tapa, …",   // modified TEXTO
 "modification_types": ["template_paraphrase", "template_paraphrase", "synonym_label", "unit_expansion", "unit_conversion"],
 "modification_count": 5}
```

Differences from OEB that matter:

| Aspect | OEB | OE synthetic queries |
|---|---|---|
| query ↔ gold join | `item_key == item_key` | `gold_item_key` (item), `parent_key` (concept) |
| `parameters` | nested `{label, values:[{label,value}]}` | flat `{axis: "value"}`, values possibly rewritten, `null` axes |
| query text | RESUMEN, ~14 words | modified TEXTO, ~74–78 words |
| queries per gold leaf | 1 | single: 4 439 queries over 2 917 leaves; stacked: 1 per leaf |
| slices | has_numbers | + `modification_types`, `modification_count` (condition = `single_<type>` if count==1 else `all_combined`) |

Counts profiled on 2026-09-08: single 4 439 (9 types: template_paraphrase 600, num_to_text 600,
reorder 595, synonym_label 588, unit_conversion 549, compression 548, unit_expansion 542,
paraphrase 211, expansion 206); stacked 4 998 (modification_count 2–8, mode 5). Every
`gold_item_key` exists in the corpus.

## 4. Known pipeline breakpoints

1. **Gold decoupled from `item_key`.** `src/retrieve.ipynb` computes quick metrics and writes
   `query_item_key` assuming it equals the gold doc key; `src/metrics.ipynb` does
   `gold = qkey` and skips queries whose key is not in the corpus — every synthetic query
   would be silently dropped.
2. **Flat `parameters`.** `normalize_parameters_field` / `build_param_tokens` in
   `src/data.ipynb` expect nested blocks (`block.get("label")`); a flat string value raises.
   Affects `param_tokens`, `text_word_params`, `param_phrases`, i.e. the inputs of
   `bm25_unigram_params` and the `tfidf_unigram_phrases_*` methods.
3. **One query set per collection.** `data.ipynb` → `features.ipynb` → `*_short_feats.parquet`
   is a single short/long pair keyed by `COLLECTION`; here one corpus has three query sets
   (resumen, single, stacked). Extra columns (`gold_item_key`, `modification_*`) are dropped by
   the loader's fixed record projection.
4. **Path collisions with OEB.** All 77 `configs/*.yaml` hard-code `collection: "OEB"`;
   indexes go to `/work/index/{method}` and runs to `/work/runs/{method}` regardless of
   collection or query set; `retrieve.ipynb` hard-codes `OEB_features_meta.json`; the
   eval/bootstrap/error-analysis notebooks scan a flat `/work/runs`.
5. **Slices.** `metrics.ipynb` only knows `has_numbers`; the synthetic sets need per-condition
   and per-count slices, and `eval.ipynb`'s leaderboards need to key on query set as well as
   method.

## 5. Open decisions (owner: César)

- **Method scope** on OE: canonical set from the paper, with or without a BM25 k1/b re-sweep
  (query length changes ~5×, so OEB's tuned k1=0.60/b=0.35 may not transfer), or the full grid.
- **Parameters at query time** for synthetic queries: rebuild param tokens from the flat dict
  using axis labels from `OE_concept_schema.json`, or treat synthetic queries as text-only.
- **Index/run layout**: `index/{collection}/{method}` + `runs/{collection}/{queryset}/{method}`
  versus name-mangled flat dirs; affects every notebook that scans `/work/runs`.
- **Branch hygiene**: like `research/structured-retrieval`, this is a parallel branch; whether it
  ever merges to `main` is undecided.
