# DELIVERIES — `research/synthetic-oe`

**Record.** Append-only, unbounded, searched rather than read wholesale. One section per upstream
delivery: what arrived, when, its digests, what was verified about it, and which limitations it
carries into which sprint.

Split out of [`INTAKE.md`](INTAKE.md) on 2026-09-27, when that contract passed its 12 KB budget.
The reason is the documentation model, not housekeeping: `INTAKE.md` is a **contract** — where the
data goes, what its schema is, what breaks on it — and a contract that accumulates one section per
delivery is an archive wearing a contract's name, and stops being read. Delivery history changes
every time upstream ships, so it is a record. The original intake of 2026-09-08 stays in
`INTAKE.md §2` as the branch's founding provenance; everything after it lives here.

Newest first.

---

## 2026-10-16 — v2 of the four query sets, and the back-translated queries · **taken** (intake 2026-10-18)

Delivered at `bc3cat-dataset` `synthetic` `2677ced6` (handoff note
`docs/synthetic/HANDOFF_retrieval_2026-10-16.md`); the v2 files were packaged at `d43a30e8` by
`scripts/repair_broken_paraphrases.py`, the BT files at `045fb8c1` by `scripts/build_bt_sentences.py --assemble`
(seed 42). Every digest below was re-hashed here against the handoff note and upstream's `MANIFEST.md`; the
corpus files and every v1 file are unchanged (`tests/test_intake_20261016.py`, 27 tests).

| File | Records | SHA-256 prefix | Taken |
|---|---:|---|---|
| `OE_stacked_texto_v2.json` | 4,998 | `bc1ed968f60933d9` | yes, as `stacked_texto_v2` |
| `OE_single_texto_v2.json` | 4,439 | `b3c58fcb38fd294f` | yes, as `single_texto_v2` |
| `OE_dose_texto_v2.json` | 3,000 | `8becd49ad0fd1f37` | yes, as `dose_texto_v2` |
| `OE_isolated_texto_v2.json` | 5,400 | `95c0c2edaef0c7dc` | yes, as `isolated_texto_v2` |
| `OE_v2_changes.jsonl` | 3,175 | `981896771092f6a9` | yes (the change list: `set`, `item_key`, `paraphrase_id`, `old`, `new`) |
| `OE_v2_provenance.json` | — | `1c9e4d6db1a7569b` | yes |
| `OE_bt_texto.json` | 4,670 | `421b3ca3a3d3f61f` | yes, as `bt_texto` |
| `OE_bt_modifications.jsonl` | 4,670 | `c1ffe3bfafa2736d` | yes (sidecar) |
| `OE_bt_provenance.json` | — | `d17653030a0b0cc3` | yes |
| `OE_stacked_P_exclusion.json` | 324 keys | `bbe36522fdccb4fa` | yes, as the STACKED-P filter (`utils.exclusions.stacked_p`) |
| `OE_known_drift_rewrites.json` | 14 | `1431f19dfb4791f2` | yes |

**v2: 163 broken template paraphrases repaired.** An upstream audit of the 828 TEXTO template paraphrases in
use found 163 that put a value in a slot that is not its own («de 200 mm y diámetro *en cruce bajo vías*»;
134) or present a value as a reference document («se detallan en *Nocturno*»; 29). César had only those two
kinds repaired (2026-10-16); doubled units («40 mm mm»), clumsy grammar and meaning shifts stay on purpose.
Each paraphrase was corrected with the smallest change and the same slots, and every affected query
re-rendered with its own values. Recorded as **P10** in `DATASET_DEFECTS.md`.

**Checked here, every claim re-derived from the files:**
- **Same records, same order, only `text`.** In each v2 set n is v1's, `id` / `item_key` / `gold_item_key` /
  `parent_key` are identical row for row, and no field other than `text` differs in any record. `text` differs
  on exactly the queries `OE_v2_changes.jsonl` lists — **STACKED 2,039 of 4,998, SINGLE 241 of 4,439, dose 547
  of 3,000, isolated 348 of 5,400** (3,175 lines, 163 distinct `paraphrase_id`) — where `old` is v1's text and
  `new` is v2's. Every changed query carries `template_paraphrase`.
- **Where the changes fall** (dev / test): STACKED 1,183 / 856 over 46 concepts (21 dev); SINGLE 145 / 96 over 31
  (18 dev); dose 337 / 210 and isolated 214 / 134, both over all seven E3 concepts (`OEB020$ 030$ 230$ 290$` dev,
  `OEB040$ 280$ 300$` test). The SINGLE changes are all in the `template_paraphrase` cell: **241 of its 600
  queries, 145 of 302 on dev**; the other eight cells are byte for byte v1's. The isolated changes are all
  `template_paraphrase` too: 348 of 600, **214 of the 328 dev leaves (65 %)**. In dose the changed queries per
  rung 1–5 are 34 / 69 / 114 / 158 / 172 against 70 / 140 / 211 / 279 / 300 queries carrying the type (dev:
  23 / 46 / 72 / 95 / 101 of 328 per rung).
- **No v2 dev query is undecidable**, by S4 work item 4's test: none equals a leaf's `texto` except P7's
  `reorder` query, which carries no paraphrase and is untouched; none shares its text with a query of another
  gold; no U+FFFD.
- **The derived tables inherit this exactly.** `build_v2_query_tables.py` proves the v1 path on all four v1 sets
  (each re-derives to its stored norm and feats tables), then derives the v2 tables, which equal the v1 tables
  on every unchanged row, column for column, and on the changed rows move only the columns derived from
  `text` (digests in `MANIFEST.md`).

**BT: 4,670 back-translated queries, one per STACKED-P leaf.** Each is the gold `texto` of its leaf translated
sentence by sentence with OPUS-MT (ES→EN→ES and ES→EN→{FR, IT, DE}→ES, beam 4, no sampling; the first approved
translation per sentence, else the original), values masked during translation and then replaced by audited
variants (`value_back_translation`, 3,787 queries, half the time with the axis label in front), and half the
trade terms replaced by audited synonyms (`glossary_synonym`, 2,898). No LLM touched it. Schema: STACKED's plus
`condition` (`bt_origv_en`), `source_item_key`, `source_text_sha256`, `bt`, `bt_sentences`,
`characterization_check`, `texto_modification_types_post_bt`, `reverted_types`; `item_key` is the gold's plus
`_btorigv_en`.
- **Paired to STACKED-P leaf for leaf.** All 4,670 golds resolve in the corpus with the stated parent; each is a
  STACKED-P leaf, and `item_key` = gold + `_btorigv_en`. Four STACKED-P leaves have no BT query (`OEB160a`,
  `OEE020bca`, `OEE020bda`, `OEE020cab`). 79 concepts, **40 dev / 39 test; 2,331 dev / 2,339 test queries**.
  Absent from the corpus's 83: `OEB160$`, `OEB310$`, `OEC140$`, `OEE020$` (`OEC140$` has no stacked query;
  `OEB310$`'s one is outside STACKED-P).
- **The source text is this tree's corpus.** `source_text_sha256` equals the SHA-256 of our `OE_texto.json`
  text for all 4,670. Upstream's provenance stamps `OE_texto.json` `54c83faa…`, which is the corpus file with
  `duplicate_texto_group` inside, refused here under D-033 (2026-09-27); the per-record digests show its texts
  are ours.
- **New and decidable.** No BT text equals a leaf's `texto` or any delivered query (v1, v2, L2); all 4,670 are
  distinct; no U+FFFD. `modification_types` ⊆ {`back_translation`, `value_back_translation`,
  `glossary_synonym`}, always with `back_translation`; count equals the type count; the sidecar names the same
  types per query, in the same order of records.
- **Gentler than STACKED.** Mean fraction of translated sentences 0.48 (label sentences such as «Trabajo: X.»
  usually come back identical); mean length 67.0 words against 75.9 for STACKED-P v2 and 69.6 for the gold.
- **55 BT golds are D-033 duplicates** (the same 55 as in STACKED-P), excluded at item level as everywhere. No
  P7 / P8 key.
- **F-BT-1, closed upstream, carried as a caveat:** 3,153 BT queries say «de hormigón»; for 2,718 of them the
  gold says «hormigonada» (substring counts here; upstream counts 2,713 by its own rule).

**STACKED-P.** 324 STACKED `item_key`s outside STACKED-P: 321 carry one of the 14 known drift rewrites of
`OE_known_drift_rewrites.json` (8 `paraphrase`, 6 `expansion`; the 321 queries are exactly the file's lists, and
each rewrite's `new` string is in its v1 and its v2 query), 2 duplicate a delivered query, 1 is degenerate
(gate G1). 189 dev / 135 test, over 10 concepts. STACKED-P is **4,674 queries, one per leaf, 81 concepts**. It
applies by `item_key`, so it is the same population on v1 and v2 (César: the drift audit is not repeated on
v2). Implemented as a filter, not a query set: a stacked result is reported on all its queries and on STACKED-P.

**Registered.** `run_context.V2_QUERY_SETS`, `BT_QUERY_SETS`, `STACKED_P_SETS`; `exclusions.stacked_p`;
tables by `build_v2_query_tables.py` (`BT_FIELDS` adds `condition` and `source_item_key` to the projection).
The v1 names stay registered and their files unchanged, so every earlier run resolves. **Decision raised:**
D-061 — v2 replaces v1 as the reference for S12 and for the re-run amendments; v1 results stay as a sensitivity
analysis beside v2.

## 2026-09-30 — the SINGLE modifications sidecar, taken from the release · **taken** (S6 work item 1)

Not a new delivery. It is the release's own sidecar, which `RESEARCH_PLAN.md` §5 lists as requested in S1
and consumed in S6, and which was never handed off. S3 therefore flagged the D-004 pantry artefacts from
the text alone (D-038 amendment). The file was taken from upstream, not requested again.

| File | Records | SHA-256 prefix | Taken |
|---|---:|---|---|
| `OE_single_modifications.jsonl` | 4,439 | `f492d9a0b7e133bf` | yes, as the D-004 cross-check (S6 design) |

**Where it comes from.**
- **Path:** `bc3cat-dataset` `data/synthetic/processed_OE_ablation_single/BC3CAT_Syn_modifications.jsonl`.
- **Blob:** `d5f2f86b` at the corpus release `8998875`, at `a89eca4` (the last commit to touch it; an
  ancestor of the release) and at `synthetic` HEAD `0923284`. The file has not changed since the
  release.
- **Line endings:** the digest above is of the CRLF checkout that was copied. The LF blob git stores
  hashes to `e2bcc95f77caa4ca`. This is the same situation as P8.

**Checked here** (`tests/test_intake_s6.py`):
- **Keys:** its 4,439 keys are exactly `OE_single_texto.json`'s.
- **Types:** each row's applied modification names the type its query carries.

**Against S3's text detector, dev only (2,206 queries):**
- **L1 and L2 rewrites (1,598 queries):** the sidecar can locate every rewrite in its query, and it
  agrees with the detector on every one. 185 are flagged doubled by both.
- **L3 rewrites (608 queries):** each is a template with `$`/`%` placeholders. Its literal words meet
  the placeholder values only when the template is rendered, so the sidecar cannot decide doubling
  there. Those queries are returned as undecidable, not clean, and L3 doubling rests on the detector
  alone. 35 of them are detector-flagged.
- **The *topografía* drift:** 19 queries, the same 19 both ways.
- **`OE_single_l2_texto.json`'s own sidecar, dev (518 queries):** no doubling either way. The drift is
  on 17 queries, the same 17 both ways.
- **Code:** the cross-check is `src/utils/pantry_flags.py`. It locates the rewrite without consulting
  the detector.

## 2026-09-30 — `single_l2_texto` wired · **registered, tables derived** (S6 work item 1)

The L2 delivery below (2026-09-29, evening), now registered as the query set `single_l2_texto`
(`run_context.QUERY_SETS`).

**Tables.** `build_s6_query_tables.py` derives them along `single_texto`'s own path in `data.ipynb` /
`features.ipynb`. Before writing, it re-derives `single_texto` and requires the stored
`OE_single_texto_norm` / `_feats` back column for column and row for row. They came back exactly, on the
host interpreter.

| File | Rows | SHA-256 prefix |
|---|---:|---|
| `OE_single_l2_texto_norm.parquet` | 1,092 | `c9ab1aa263b8b909` |
| `OE_single_l2_texto_feats.parquet` | 1,092 | `9612ad99bbba0a8d` |

**Checked** (`tests/test_intake_s6.py`, text on dev only):
- every gold resolves to a leaf of its concept;
- `modification_count` is 1 everywhere, and the types are exactly the three L2 types;
- dev breadth is 179 / 180 / 159 queries over 9 / 9 / 8 concepts;
- no dev gold is a D-033 duplicate;
- no key is on a P7 or P8 list;
- no key is shared with `single_texto`.

No run yet: that is work item 3.

## 2026-09-29 (night) — the P8 answer and test list · **taken**; menu fixed at the next build (B)

| File | Records | SHA-256 prefix | Taken |
|---|---:|---|---|
| `OE_P8_test_exclusion.json` | 2 keys | `6cda7fa05aa6e32f` | yes, D-044 |

Upstream's answer to [`requests/SYNONYM_CASE_ONLY.md`](requests/SYNONYM_CASE_ONLY.md):
- **Cause.** The frozen `synonym_label` menu holds **four** approved case-only candidates, not one:
  `semi-rocoso` under two entries, `rocoso` and `elevada`. The review never compared a candidate with
  its own label after lower-casing.
- **Reach, counted upstream on every delivered file.** `OE_single_texto.json` 4 dev (our count) and
  **2 test**. Every other file, `OE_single_l2_texto.json` included, has 0 on both splits: its queries
  always carry other changes too.
- **Fix.** The menu generator now drops a candidate equal to its label after lower-casing and whitespace
  clean-up, with a test. It is committed at `bc3cat-dataset` `0923284aef6f` on `synthetic`, pushed. The
  commit also holds the audit script (it prints counts only) and the list file. Verified here: the
  commit is on `origin/synthetic` and touches those four files.
- **No re-delivery.** Every delivered digest holds; `OE_single_texto.json` re-hashed here matches
  (`b6a43961…`).

The list holds keys only: `reason`, `file`, `split` (`test`), `item_keys`. It was checked without
reading any query text. Both keys resolve in `OE_single_texto.json`, both are `synonym_label`, and both
concepts (`OED160$`, `OED180$`) are test under `SPLITS.md`. Despite its name it excludes nothing: under
D-044, S12 keeps the two queries and also shows each `synonym_label` cell without them.

**Line endings and digests.** Both digests are of the same content, with identical keys:
- `6cda7fa05aa6e32f…` is the file with CRLF line endings. This is the copy in `data/processed/`, and
  the digest `MANIFEST.md` checks.
- `9b007b1c47bf7430…` is the LF blob git stores at `0923284`.

Both were verified here.

**Menu: option B** (César, D-044 note). The frozen menu is unchanged, and the four entries go at the
next corpus build.

## 2026-09-29 (evening) — wider L2 slices, option A · **taken, not yet wired**

Delivered at `bc3cat-dataset` `synthetic` `b0e23f1`, generated at `90a318f` by
`scripts/build_single_l2.py` from the frozen menus.

| File | Records | SHA-256 prefix | Taken |
|---|---:|---|---|
| `OE_single_l2_texto.json` | 1,092 | `fff7dd3be023125b` | yes |
| `OE_single_l2_modifications.jsonl` | 1,092 | `e1e5adbb8824bd34` | yes (sidecar) |
| `OE_single_l2_provenance.json` | — | `6885a7b2de28ae9c` | yes |

**D-043's four conditions, each checked here, not quoted:**
1. **Fixes committed before the build.** On `synthetic` the order is `7bff777` (P7 validator), then
   `4687059` (builder), then `90a318f` (list-form L2 engine, its tests and a replay script), then
   `b0e23f1` (delivery). The generating commit is an ancestor of the delivery.
2. **Regression.** `scripts/regress_render_replay.py`, run here read-only at `b0e23f1`, re-renders
   every delivered query from its sidecar. SINGLE 4,439, STACKED 4,998, dose 3,000 and isolated 5,400
   are all byte-identical, and no recorded modification stopped applying. No run on those sets can
   move.
3. **Frozen menus, at most 9 / 9 / 8 dev concepts.** Measured: `paraphrase` 179 dev queries over 9
   concepts, `expansion` 180 over 9, `compression` 159 over 8. The five concepts `OE_single_texto.json`
   covers per type are among them.
4. **New file, own sidecar and digest.** Every digest above matches upstream's.

**Also checked:**
- **Schema and metadata, both splits (keys and parents only):** the schema is SINGLE's field for field.
  Every gold resolves to a leaf of the stated concept. Each record has exactly one modification. Keys
  are unique, and no key is shared with SINGLE.
- **Text, dev only:** no query equals any leaf's `texto`, none duplicates another, none shares a text
  with SINGLE, none carries `$` / `%` residue, and no gold is a D-033 duplicate.
- **Test:** 574 queries over 11 / 11 / 9 concepts, counted from keys; test text not read (operating
  rule 2).

**Not wired.** No query-set name, no feature tables, no runs. That is S6's intake (`RESEARCH_PLAN.md`
§S6), as S3 left E3 registered and unwired. The limitation S6 states: L2 breadth is 9 / 9 / 8 dev
concepts under the frozen menus, against a grammar ceiling of 13.

## 2026-09-29 (later) — the P7 test exclusion list · **taken**; the L2 reach corrected

| File | Records | SHA-256 prefix | Taken |
|---|---:|---|---|
| `OE_P7_test_exclusion.json` | 2 keys | `96fe3854f2b6d935` | yes, D-043 ruling 1 |

It holds keys only: `reason`, `file` (`OE_single_texto.json`), `split` (`test`) and `item_keys`. The
file was checked without reading any query text. Both keys resolve in `OE_single_texto.json`, which
is unchanged (`b6a43961…`), and both belong to test concepts under `SPLITS.md`. It is applied at item
level in S12 and nowhere before.

**The wider-L2 reach was wrong.** Upstream built `OE_single_l2_texto.json` from the frozen menus and
found it adds **no concepts**: 478 queries on the same 5 dev / 3 test concepts per type. The
reachability check tested visibility in the TEXTO, not whether the render engine can apply the
rewrite. 17 of the 25 concepts with a text variable store it as an axis-indexed list (`$T(%A)`), which
the engine cannot yet rewrite. The file is **not taken**; the choice upstream offered is pending with
César.

## 2026-09-29 — answers to the P7 and wider-L2 requests · **no files**

Upstream answered both S4 requests in `bc3cat-dataset/docs/synthetic/REORDER_LOOKUP_RESPONSE.md` and
`WIDER_THIN_SLICES_RESPONSE.md`, on `synthetic` over `f2457fa`. **No file was delivered**:
`OE_single_texto.json` still hashes `b6a43961…`, re-checked here, so no S4 run moves.

- **P7.** Upstream confirmed the diagnosis and fixed the placeholder validator: whole calls,
  arguments in order, literal rows included. The pantry loader now re-checks approved rules and
  drops 28: 9 `reorder`, 16 `template_paraphrase`, 3 `omission`. **The fix was uncommitted when
  answered** ("pending owner review"). Scope:
  - **Dev:** our own test finds only the one query. No other dev query in any delivered set was
    built from a withdrawn rule.
  - **Test** (counts only, from upstream): 0 by our test. **2** `single_texto` `reorder` queries come
    from a different withdrawn rule, which swaps a literal lookup row and drops a field. They match
    no leaf, so our test cannot see them, but they are not referent-preserving.
  - The `$U` permutations reached no delivered file.
- **Wider L2.** Not built yet. Reachable with the frozen menus: `paraphrase` 9, `expansion` 9,
  `compression` 8 dev concepts (today 5), at about 180 / 180 / 160 dev queries with ≤ 20 leaves per
  concept. **Hard ceiling: 13 dev / 12 test concepts.** Only those concepts render a text variable in
  their TEXTO, so no menu can reach ≥ 15.

César's rulings are recorded in D-043.

## 2026-09-27 — duplicate-`texto` sidecar and the corrected stacked set

**Taken in:** S3 work item 1 · **Decisions:** D-031, D-033, D-025

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

## 2026-09-17 — E3 balanced dose set

**Taken in:** S3 work item 2 (2026-09-27) · **Decision:** D-009

Producer: `bc3cat-dataset` `synthetic`, `scripts/build_dose_ladder.py`, config
`configs/synthetic/variant_budgets_OE_dose.yaml`, **seed 42**, run `e3-20260917T093057Z`,
generated at `e057907`, repackaged at `903d07b8`. Upstream reports the run reproduces byte for
byte. Answered point by point in `bc3cat-dataset/docs/synthetic/E3_DELIVERY_RESPONSE.md`.

| File | Records | SHA-256 prefix |
|---|---:|---|
| `OE_dose_texto.json` | 3,000 | `555fab84d134886f` |
| `OE_isolated_texto.json` | 5,400 | `054041ff05349fae` |
| `OE_leaf_applicability.jsonl` | 1,500 | `eda12d17c323add4` |

**It arrived on 2026-09-17 and was recorded on 2026-09-27**, having sat unregistered for ten days
while `STATE.md` said it was blocked and waiting. See the D-009 note; the delay is recorded because
the provenance failure is the interesting part, not the files.

**Every claim the response makes was re-derived from the files** (`tests/test_intake_e3.py`, 23
tests), and all of them held:

- 600 leaves, each carrying the **complete ladder 1–5**, exactly 600 queries per rung.
- The ladder is **nested**: the types at count *k* are the types at *k*−1 **plus exactly one**, so
  consecutive rungs on one leaf differ by a single modification. This is what makes the dose slope
  a within-item contrast and admits paired rung-to-rung comparisons.
- The isolated set is the same 600 leaves × the 9 types, one modification each — so "the sum of the
  isolated effects" in H4 is a sum over the *same* population as the ladder.
- All 8,400 `gold_item_key` resolve against the 70,242-leaf corpus, every `parent_key` agrees with
  it, and no query is byte-identical to its target.
- `modification_count` equals the distinct type count everywhere: these sets are exact, so they
  carry no `texto_modification_*` field and need none (contrast D-025).
- `available_types` ⊆ `applicable_types` on all 1,500 probed leaves; `in_pool` marks exactly the 600
  ladder leaves; every ladder leaf admits all nine types.

**Three limitations, measured here and binding on S8.**

1. **Two interactions are not identifiable.** `reorder` × `template_paraphrase` and
   `unit_conversion` × `unit_expansion` never co-occur, by construction — each pair rewrites the
   same span. S8 must not claim those interactions. The tests pin this, so that a later delivery
   changing it fails loudly instead of being inherited in silence.
2. **Coverage is 7 of 83 concepts**, all OEB canalizations: `OEB020$` 61 leaves, `OEB030$` 87,
   `OEB040$` 96, `OEB230$` 93, `OEB280$` 87, `OEB290$` 87, `OEB300$` 89. Upstream explains this as
   structural: a clean count-5 cell needs leaves admitting ≥6 types on distinct TEXTO spans, and
   only these families have them; relaxing it would fix the composition at count 5 and bring back
   the very confound E3 exists to remove. **They straddle our split** — dev `OEB020$ 030$ 230$
   290$` (328 leaves, 1,640 dose / 2,952 isolated queries), test `OEB040$ 280$ 300$` (272 leaves,
   1,360 / 2,448). So a dev-side slope rests on 328 leaves — well powered *within* item — but a
   **concept-clustered interval on it resamples four clusters**, and under D-030 that is what a
   threshold is read against. S8 states this rather than discovers it.
3. **`unit_conversion` is thin**: 39 items at count 1 against ≥70 for the other eight (18 on the
   dev side), because these concepts admit only four approved rewrites and each is capped at 40
   uses so that a type's effect is not one repeated edit.

**D-033 costs nothing here:** no ladder leaf shares its `texto` with a sibling — the duplicate
groups are confined to `OEA050$` and `OEG050$`, and E3 covers only OEB.

**Not wired into the harness.** These are registered, not runnable: `run_context.QUERY_SETS`
reserves the single name `balanced_texto` (D-008 amended) and the delivery is **two** query sets.
Naming them, and deciding whether the isolated set is a query set or the reference the dose slope
is measured against, is S8's first design question — S3 deliberately leaves it open rather than
half-wiring it.
