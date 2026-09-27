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

### 2.1 Second delivery — 2026-09-27 (taken in S3 work item 1, under D-033)

Producer: `bc3cat-dataset`, branch `synthetic` @ `f2457fa`; the files themselves were
repackaged at `903d07b8` from the generation run `e3-20260917T093057Z` (seed 42, generated at
`e057907`). Verified by re-hashing `D:/…/bc3cat-dataset/data/synthetic/handoff_OE/` against that
repository's own `MANIFEST.md`, not by trusting either.

| File | SHA-256 prefix | Taken |
|---|---|---|
| `OE_duplicate_texto_groups.json` | `b3cfcad47c71c5eb` | yes — the D-031 flag as a sidecar |
| `OE_stacked_texto.json` | `c34a222ae2af05a0` | yes — adds `texto_modification_{count,types}` |
| `OE_texto.json` / `OE_resumen.json` with `duplicate_texto_group` inside | — | **no**, deliberately |

**Why the corpus files were refused.** They carry the same grouping as the sidecar, but embedding
it changes their digest although no text changes — and every S2 run is stamped against
`OE_long_feats.parquet` `643f1a72…` / `OE_long_norm.parquet` `75477221…` derived from them. The
sidecar delivers the same information at no provenance cost (D-033).

**The superseded stacked query set is kept, and so are its derived tables.** S2's three stacked
runs are stamped against the *feature table* `7b0894e6…`, not the JSON, so versioning the JSON
alone would have left them dangling. All three survive under digest-stamped names:
`OE_stacked_texto__1bde2115.json`, `OE_stacked_texto_norm__81cd501b.parquet`,
`OE_stacked_texto_feats__7b0894e6.parquet`. They are not a query set — `run_context` resolves
query sets by exact canonical name — so nothing can be run on them; they exist so that a stamp
still resolves. `src/utils/check_run_inputs.py` is what demonstrates it.

**What the re-derivation actually moved.** `data.ipynb` + `features.ipynb` re-run on
`COLLECTION=OE` at commit `17d36ba` (`logs/S3/rederive_stacked.sh`, container `bc3cat-s3`).
Seven of the nine OE derived tables came out **byte-identical**, including every digest S2's
other twelve runs depend on. Only the stacked pair moved: norm `81cd501b…` → `4939d99f…`, feats
`7b0894e6…` → `f34c1798…`. Inside the new feature table, **all 26 pre-existing columns are
identical row for row** and only `texto_modification_count` / `texto_modification_types` are
appended — so S2's stacked Acc@1 describes exactly the inputs it described before, and the digest
change is metadata. Asserted by `tests/test_intake_20260927.py`, not by this paragraph.

**The corrected dose, which is the point of the delivery.** `texto_modification_count` runs 1–6
(mode 4: 5 · 1,252 · 1,465 · 1,799 · 401 · 76) where the original `modification_count` runs 2–8
(mode 5). Five stacked queries carry a single visible modification. S3 work item 4 re-stratifies
S2's by-dose table on the corrected field; `modification_count` is not used for any
stratification again (D-025).

**Digests of the delivered files as taken in are in [`MANIFEST.md`](MANIFEST.md)**, which now also
covers the derived tables — it listed only the deliveries until S3, so every OE run made before
then was stamped against a digest this branch did not record.

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
