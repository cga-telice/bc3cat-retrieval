# Sprint S91 — Coded vs decoded `resumen` · design

> **Frozen at:** `09d11f7` · `2026-09-28`
> This section is read-only from that commit. Changes go in **Amendments** below, dated and
> justified — never as in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S91` · probe |
| **Status** | planned → active |
| **Serves** | Validity of the replication (D-037, D-039); the D-039 open question (query-side decoder); an input to H5 |
| **Depends on** | S3 (`done`); D-039 |
| **Decisions applied** | D-010, D-018, D-023, D-030, D-032, D-033, D-036, D-039 |
| **Effort** | 3 working days, time-boxed (see Stopping criterion) |
| **Predecessor / successor** | S3 / S4 (independent: S4's query sets carry no codes) |

## Goal

The catalogue's own `resumen` ends in a three-code suffix naming the work-regime axes, e.g.
`(N/<3/R)`. The previous study expanded those codes into their values before querying
(D-039). At the end of this probe we will know, **paired on the same OE dev leaves against the
same indexes**, how much of each arm's `resumen→texto` accuracy depends on that rendering. The
probe separates two effects:
- **code → nothing** (strip the suffix): do the codes actively hurt? D-039 records the
  untested observation that several codes are near-absent corpus tokens (`e` appears in 72 of
  70,242 documents), so IDF may send lexical arms to unrelated documents.
- **nothing → value** (decode the suffix): do the spelled-out values help?

We will also know whether a decoder can be built from the catalogue alone, without the concept
and without gold, which decides whether it is a deployable component.

## Entry state

Each item was checked in the tree on 2026-09-28, not taken from the registry:

- **S3 `done`**: `SPRINTS.md` row and log; three audits in `SPRINT_S3_AUDIT.md`, the last PASS WITH FINDINGS, resolved at `8c75e01`.
- **D-039 committed** at `acd3212`.
- **`OE_resumen.json`** hashes `0cd380e9…`, matching `MANIFEST.md`.
- **`OE_short_feats.parquet` `f041a8e8…` and `OE_short_norm.parquet` `28d09f40…`** hash as recorded in `MANIFEST.md`. These are the coded condition's query tables.
- **The coded condition already exists**: `runs/OE/resumen/` holds the ten E0(b) arms at 0.60/0.35, plus `bm25_unigram` at 0.80/0.35. All are `code_dirty: false`, split `dev`, and resolve under `check_run_inputs.py` (S3 exit criterion 3).
- **All ten indexes exist** under `index/OE/`. No index is rebuilt in this probe.
- **Suffix structure, measured on dev only (35,422 leaves):**
  - 28,150 leaves carry a suffix, always exactly three codes, in the order TRABAJO / BANDA DE MANTENIMIENTO / CONDICIONES DE EJECUCIÓN; 7,272 carry none.
  - By position, every code maps to a single value except TRABAJO `-` (splits between *cualquier franja horaria* and its *excepcional* variant). Minor exceptions: `D`/`N` also cover a *con/sin corte de tensión* variant on 288 leaves each; spelling variants such as `i< 3 horas` normalise away.
  - 22,716 of the 28,150 decode exactly on all three axes.
- **`resumen` has undecidable siblings.** 9,346 dev leaves (4,673 groups) share their `resumen` text with another leaf; 200 of them are also `texto` duplicates. For a text-only query this caps item-level accuracy at about 0.868. S3's replication did not account for it.

## Work

1. **Build the renderings.** A committed generator, `src/utils/build_resumen_renderings.py`, reads `OE_resumen.json` and the dev concept list from `SPLITS.md`.
   - **Decoder table.** Keyed by *(suffix position, code)*, derived from **dev leaves only**. Each entry maps to the words common to every value that code takes on dev, after `normalize_param_string`. So TRABAJO `-` decodes to *cualquier franja horaria*, the part both of its values share. A code with no common words decodes to nothing. The table uses neither the concept nor the gold.
   - **`OE_resumen_decoded.json`.** The suffix is replaced by `(v1/v2/v3)`, each value written in its most frequent catalogue spelling on dev.
   - **`OE_resumen_stripped.json`.** The suffix is removed.
   - **Everything else is copied unchanged**: text outside the suffix, `parameters`, `item_key`, `parent_key`. Each record gains `gold_item_key = item_key`.
   - The generator emits all 70,242 records, so the files have the corpus's shape, but **reads only dev to fit the table**. Test records are transformed and never run.
   - **Digests** of the two files and the table go into `MANIFEST.md`.
2. **Register the query sets.** Add `resumen_decoded` and `resumen_stripped` to `run_context.QUERY_SETS`. No other harness change is expected; see the Stopping criterion.
3. **Derive their feature tables** (`_norm`, `_feats`) through the existing `data.ipynb` / `features.ipynb` path, in `bc3cat-s3`.
4. **Test before any run**, in `tests/test_resumen_renderings.py`:
   - Records agree with `OE_resumen.json` on every field except `text` and the added `gold_item_key`.
   - Suffix-less leaves have byte-identical text in all three renderings.
   - `stripped` equals coded minus the suffix.
   - In the feature tables, `param_tokens` and every column not derived from `text` are identical row for row to `OE_short_feats` / `OE_short_norm`. This matters for the oracle arm: the manipulation must touch the query words only.
   - The decoder table contains no concept key.
5. **Run.** Ten arms × `resumen_decoded`, `resumen_stripped`: **20 runs**, split `dev`, BM25 at 0.60/0.35 (D-036), against the existing indexes.
   - The coded condition reuses the S3 E0(b) runs by digest.
   - Reuse is verified first: `git diff` of the retrieval path between each reused run's commit and the new runs' commit must show no change to that arm's retriever or builder. Otherwise the coded arm is re-run too, and that is recorded.
   - All runs from a clean tree, stamped.
6. **Analyse** with a committed generator, `src/utils/build_results_s91.py`, added to `tests/test_generated_prose.py`. Output goes to `docs/synthetic-oe/results/S91/`:
   - **T1 — decoder:** the table, its dev coverage and its exactness per axis.
   - **T2 — the three conditions per arm.** For each arm:
     - item and parent Acc@1, with n;
     - query-level and concept-clustered CIs;
     - the per-condition `resumen` ceiling;
     - the three paired contrasts (stripped − coded, decoded − stripped, decoded − coded), each with CI, p and flip counts.
   - **T3 — lexical and numeric coverage** of each rendering against its gold `texto`, the S3 overlap statistic.
   - **T4 — per subchapter, descriptive:** OEB against the rest, with concept counts.
   - **T5 — rare-code diagnostic, descriptive, lexical arms, coded condition:** among item misses, the share whose rank-1 document contains a suffix code token that the gold does not.
7. **Report** `SPRINT_S91_REPORT.md`, then `/audit S91` in a fresh session.

## Design constraints

- **Paired by query, always.** Every effect is a within-leaf difference between two renderings, on the same index and arm. No contrast across arms is claimed; T2 prints arms side by side as reference only.
- **Primary population P:** dev leaves that carry a suffix and whose gold `texto` is unique (D-033). Suffix-less leaves are identical across conditions, so their delta is zero by construction and they would only dilute the estimate. All-query figures are printed as secondary, with their n.
- **`resumen`-identical siblings are not excluded.** Which leaves are identical changes with the condition (decoding splits some groups, stripping merges more), so excluding them would break the pairing. Instead each condition prints its own text-only ceiling on P: one findable member per identical group (D-032). Oracle arms get the parameter-token ceiling, since their query carries the gold's tokens (D-010).
- **Parent level is scored on all of P**, every contrast at both levels (dual-target protocol).
- **Statistics.** Paired bootstrap, B = 10,000, seeded, percentile 95 %, with query-level and concept-clustered intervals. A claim is read on the **concept-clustered** interval (D-030): dev OE is 71 % OEB (25,203 of 35,422 leaves, 13 concepts). Within each contrast family, Holm–Bonferroni across the ten arms; Benjamini–Hochberg printed alongside.
- **Registered predictions** (written now, read against the clustered interval):
  - **P1:** decoded − coded > 0 at item level for `bm25_unigram_params`, `bm25_unigram` and `tfidf_phrases_replace`.
  - **P2:** stripped − coded > 0 at **parent** level for `bm25_unigram` and `bm25_unigram_params` (codes actively hurt). If both intervals straddle 0, D-039's rare-code observation is withdrawn.
  - **Neural arms:** no directional prediction. Reported, not claimed.
- **The oracle arm stays an oracle** (D-010). `bm25_unigram_params` receives the gold's parameter tokens in every condition, so its contrasts measure only the effect of query *words* beside those tokens. It is quoted with `bm25_unigram` beside it.
- **Not a contrast with the previous study** (D-039). The decoded condition reproduces the previous study's *kind* of edit, not its text: e.g. `i < 3 horas` against its `i < "3" horas`, and the leaves where `-` decodes only partly. Its figures may be printed beside 0.974 as reference, naming the remaining confounds (chapter, corpus size, split, and those rendering residues). No delta against 0.974 is computed.
- **A deployable decoder** uses only the code string and its position. The table is fitted on dev queries, which is tuning on dev (operating rule 2) and allowed; test is never read to fit it, and no test run is made.
- **Dev only.** No S12 artefact is touched.
- **No typed numbers.** Every figure in S91's prose is interpolated by the generator.

## Exit criteria

1. `OE_resumen_decoded.json`, `OE_resumen_stripped.json` and the decoder table exist, and their digests are in `MANIFEST.md`.
2. `tests/test_resumen_renderings.py` passes, and the full suite passes.
3. 20 new runs exist under `runs/OE/resumen_{decoded,stripped}/`: all `code_dirty: false`, split `dev`, resolving under `check_run_inputs.py`. Reuse of the ten coded runs is justified by a recorded retrieval-path diff.
4. `results/S91/` holds T1–T5, generated by `build_results_s91.py` and regenerating byte-identically. Every item-level figure carries its n, and every accuracy its per-condition ceiling.
5. P1 and P2 are each read as **supported**, **not supported** or **contradicted**, on the concept-clustered interval after Holm.
6. The report states whether a catalogue-only decoder is viable: T1 exactness, plus the ambiguity it cannot resolve.
7. D-039's open question is answered by an amendment to D-039. D-037 is amended if T3 changes what its coverage figures mean.

## Stopping criterion — probes only

- **Time:** 3 working days from the freeze commit. If the runs are not complete by then, the probe is `abandoned` and the reason recorded; no partial result is reported.
- **Scope:** if running the renderings needs any change to a retriever, index builder or index, the probe **stops**, because that is S9's territory (query-side normalisation). Allowed changes are the new query-set names, the new generators and the tests. The needed change is recorded for S9.
- **Pointless:** none is foreseen before running. Every outcome of P1/P2, including two nulls, answers D-039's open question.

## Out of scope

- **Document-side expansion** (indexing each leaf's codes): a new index, and the stronger design. It goes to S9, or to a probe of its own, only if this one shows the rendering matters.
- **Human shorthand** that is not the catalogue's own codes: covered synthetically by the L1 types (S4).
- **Re-tuning `k1`/`b` on any `resumen` rendering** (D-036 stands).
- **Re-reading S3's conclusions:** S3 is closed. This probe informs D-037 and D-039 by amendment.
- **Test split, S12.**
- **A duplicate-`resumen` exclusion policy** analogous to D-033: reported here as a ceiling. Whether it becomes a scoring rule is a decision for César after this probe.

## Risks

| Risk | Handling |
|---|---|
| TRABAJO `-` cannot be decoded; about a fifth of suffix leaves decode only partly | Decode to the shared words; report exactness per axis in T1. The residual is a property of the catalogue's codes, not of the decoder |
| The decoded surface form (spelling, separators) is an arbitrary choice that neural arms may be sensitive to | Frozen here: most frequent dev spelling, `(v1/v2/v3)`. Any other form is an amendment |
| OEB dominates dev (71 %), so one chapter drives pooled figures | Concept-clustered intervals carry the claims; T4 prints the subchapter split, descriptively |
| Adding query-set names breaks existing resolution or the OEB fixture | Suite and fixture run before any S91 run; exit criterion 2 |
| Reusing the coded runs pairs results from different commits | Retrieval-path diff recorded; re-run the coded arm if its path changed (work item 5) |
| The 9,346 `resumen`-identical leaves blur item-level contrasts | Per-condition ceilings in T2; parent level is unaffected |

## Amendments

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
| 2026-09-28 | **A1. The shared-words rule ignores a value seen on under 1 % of a code's dev occurrences** (`MIN_SHARE = 0.01` in `build_resumen_renderings.py`). Also written down, as an interpretation rather than a change: an occurrence where the leaf has **no** axis at that position (`-` meaning "axis absent", 53 TRABAJO and 6 CONDICIONES leaves on dev) contributes no value to the intersection. | Applied literally, the rule let `OEB160a/b` decide an entry for 9,380 leaves. The catalogue puts their CONDICIONES code in position 1, `(R/-/-)`, so CONDICIONES `-` took *Volumen relevante* and *Volumen escaso* once each beside *Cualquier condición de ejecución* 9,380 times, and decoded to nothing. The floor drops only those two values; the smallest genuine variant, *diurno con/sin corte de tensión* under `D`, is at 2.9 % and stays. Counting an absent axis as an empty value would have emptied every `-` entry, defeating the rule César chose. Referred to César, who chose this option over literal application or excluding `OEB160` by name. No run existed. | None on any result: made before any S91 run. CONDICIONES `-` decodes to *Cualquier condición de ejecución*; every other entry is unchanged. The position-only decoder still writes a value for an axis the leaf lacks, on those 59 dev occurrences (53 + 6). That is the cost of not reading the leaf's parameters (D-010), and T1 counts it. |
| 2026-09-29 | **A2. Three execution choices the design left open or named differently.** (a) Work item 3 derives the renderings' `_norm`/`_feats` with a new generator, `build_s91_query_tables.py`, not through `data.ipynb`/`features.ipynb`. (b) A prediction is read **supported** when its concept-clustered interval excludes 0 on the predicted side **and** its Holm-adjusted p, taken from the clustered draws, is below α; **contradicted** in the mirror case; **not supported** otherwise. (c) T5 is reported at parent level as well as item level, and T2 prints each condition's ceiling once per condition rather than in every cell. | (a) With `SAVE=True` the notebooks rewrite every table of the collection, including `OE_short_norm`/`OE_short_feats`, whose digests stamp the coded runs this probe pairs against; and `data.ipynb` would fail on the renderings, which carry no `modification_count`. The generator takes the coded `resumen`'s own path and proves it first: it re-derives the coded tables and refuses to write unless they equal the stored ones. (b) The design says "read on the concept-clustered interval after Holm" without saying how the two combine. This reading was committed in `build_results_s91.py` at `50d2c08`, before any S91 accuracy was read. (c) Additive. | (a) None: the existing digests are unchanged and the pairing is tested (`tests/test_resumen_renderings.py`). (b) It decides one reading: `bm25_unigram_params` under P2 has an interval excluding 0 and a Holm p of 0.0700, so it is **not supported**. |
| 2026-09-29 | **A3. A false sentence in the design constraints.** "Decoding splits some groups" of identical `resumen` text is wrong. The decoded text is a function of the coded text, so decoding can merge such groups but never split them. | Found when the per-condition ceilings came out equal to four decimals. The sentence is left as written, per the freeze rule, and corrected here. | None on any figure: the ceilings are computed from the texts, not from this sentence. The generator's prose was corrected at `ed52d1d`. |
