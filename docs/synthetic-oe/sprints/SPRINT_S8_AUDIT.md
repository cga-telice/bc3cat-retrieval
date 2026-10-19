# Sprint S8, amendment A8 (v2 re-run): audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-19 · report `docs/synthetic-oe/sprints/SPRINT_S8_REPORT.md`, last changed at `e083dc9` (blob `54a8dc8`), sections "v2 re-run (A8, 2026-10-18)" and "Audit response (v2 re-run)" · HEAD `23a162f` when the audit started. `d9c4d62` and `2d0b51a` landed during the audit; they touch S14 only and change no S8 file · runs: `runs/OE/dose_texto_v2/` (18 arms), `runs/OE/isolated_texto_v2/` (18 arms), `runs/OE/texto/` (identity), with `runs/OE/dose_texto/` and `runs/OE/isolated_texto/` read for the v1 side.

## Verified
- **Stamps, all 36 cited runs.** For every run in `results/S8/v2/run_provenance.md` (T11) I checked `run_meta.json` field by field: run_id, config SHA-256, `code_commit` 8d1ffd2, `code_dirty: false`, `split: dev`, 1,640 / 2,952 queries, `dropped` 0. Each config digest resolves against `configs/*.yaml`, allowing for the H5 line-ending variants. Each `query_set_sha256` equals the actual digest of the feature table the run read: `OE_dose_texto_v2_feats.parquet` = `ac0cb6a5…`, `OE_isolated_texto_v2_feats.parquet` = `35de7967…`. The JSON digests match A8: `8becd49a…` and `95c0c2ed…`. Script: scratchpad `stamps.py`; result 36 checked, 0 mismatches.
- **Amendment recorded before the runs, and first-time runs.** A8 was committed at `4f56a39` (19:54:58Z). The first v2 run started at 19:55:12Z and the first dose/isolated run at 21:00:58Z (`logs/v2/run_v2_base.out`). The first attempt (`run_v2_base.attempt1.out`) stopped on `stacked_texto_v2` and never reached dose or isolated. The script's `guard` refuses any run directory that already exists. `logs/` is git-ignored, so this evidence is on disk only.
- **Batch commit versus stamp.** The batch started at `022ff2a` (dirty=0). The runs are stamped `8d1ffd2` because that docs-only commit (`DATASET_DEFECTS.md`, `STATE.md`) landed mid-batch. `git diff 022ff2a 8d1ffd2 -- src configs` is empty, so the stamp correctly describes the code the runs used.
- **Tables reproduce.** I re-ran `build_results_s8.py --v2` at `23a162f` in `bc3cat-s3`, writing to container `/tmp` with the output directory monkeypatched (wrapper `regen_s8.py` in the scratchpad). All 16 outputs, including `fig6_ladder.png`, are byte-identical to the committed `results/S8/v2/`, and to `logs/v2/tables_gen1.sha256` and `tables_gen2.sha256`.
- **Independent recomputation from the raw `results_top100.jsonl.gz`** (tie-free = uniform break of the rank-1 tie), without the generator:
  - ColBERT, isolated `template_paraphrase` Acc@1: 0.6551 → 0.6629, so δ −0.3449 → −0.3371 against identity 1.0000. Matches.
  - `dense_e5`, same cell: 0.1402 → 0.1555, so δ −0.2470 → −0.2317. Matches.
  - Oracle BM25, same cell: 0.4878 → 0.4939. Matches.
  - ColBERT rung 5: 0.2923 → 0.2844. Matches.
- **Holm.** I recomputed it from the 21 raw p's in `predictions.md` and `v2/predictions.md`: 0 mismatches on either version. The report's account of the flip is exact:
  - v1: `bge_m3_dense` p 0.0054 at rank 13 (×9 = 0.0486); `bm25_unigram` p 0.0060 at rank 14 (×8 = 0.048, lifted to 0.0486).
  - v2: `bm25_unigram` 0.0060 at rank 13 (×9 = 0.0540); `bge_m3_dense` 0.0062 at rank 14 (×8 = 0.0496, lifted to 0.0540).
- **Report figures against `v2/comparison.md`:**
  - Changed queries: 337 rung queries (23/46/72/95/101) and 214 isolated, all of them `template_paraphrase`.
  - X1: ColBERT +0.0199 → +0.0151 (−0.0048 [−0.0147, +0.0051]); `bge_m3_dense` +0.0343 → +0.0320; `dense_e5` −0.0671 → −0.0678.
  - X2: `bm25_unigram` +0.0643 with Holm 0.0486 → 0.0540; `bge_m3_dense` +0.0738 → +0.0742, with 9 rung and 13 isolated hits moved.
  - Rung 5 prediction 0.2762 → 0.2807. ColBERT has 53 isolated hits moved. The oracle BM25 twin moves 2 hits, +0.0061 [+0.0000, +0.0152].
  - The T3 bar is identical for the three lexical arms. H4 reads *partly supported* on both versions.
  - X2 is supported for 4 arms on v2 against 6 on v1; X1 for `dense_e5` only; X3 for all 7.
- **Known-wrong 5 against `v2/d004.md`.** Flagged counts 481/316 on v1 and 447/296 on v2. On the clean subset: `dense_e5` X1 −0.0561, not supported; `bge_m3_dense` X2 +0.0922 [+0.0307, +0.1554], Holm 0.0280, supported. All match.
- **The v1 column of `comparison.md` equals the recorded v1 tables** (`predictions.md`, `isolated.md`, `ladder.md`, `additivity.md`). No v1 table has changed since 2026-10-03.
- **One sample per comparison.** `same_design()` asserts that golds, concepts, keys, membership and added types are identical across versions before the comparison is written. Every comparison uses 328 dev leaves in 4 concepts, with one identity run. Only dev is read: `split=dev` in every run, and the generator calls `load_split("dev")`.
- **Design freeze.** `git diff 4f62d5a..HEAD -- SPRINT_S8_DESIGN.md` changes only the freeze-SHA line. The amendments file is append-only: A8 is one inserted line at `4f56a39`. D-052 and D-053 are untouched.
- **Tests.** `tests/test_report_traceability.py`, `test_generated_prose.py` and `test_intake_20261016.py` give 63 passed and 1 skipped (the S14 report is not yet written).
- **Quoted repair.** The example «se detallan en» → «son:» is present in `data/processed/OE_v2_changes.jsonl`.

## Findings

### F1 (major): "finding 4 does not change" is stated without the v2 as-run figure that decides it, and that figure now sits 0.0008 below the bar
- **What the report says.** The lexical arms are "indifferent to the repair in outcome": for `bm25_unigram` and the oracle TF-IDF every X1–X3 estimate is identical on v1 and v2. And "finding 4 does not change: no X2 excess is attributed to interaction."
- **What the artefacts say.** The identity holds only tie-free.
  - As run, the oracle arms move in all three tests (`predictions.md` against `v2/predictions.md`, as-run column, A5). `tfidf_phrases_replace` X1 −0.0175 → −0.0191, X3 −0.1928 → −0.1935. `bm25_unigram_params` X2 +0.0927 → +0.0889.
  - Most importantly, `tfidf_phrases_replace` X2 as run goes from **+0.0768 to +0.0855**, against an unchanged bar of **0.0863**.
- **Why it matters.** Finding 4 credits no interaction to `tfidf_phrases_replace` for one reason only: its as-run excess falls below the bar, although its tie-free excess (+0.1010) is above it. On v2 that margin shrinks from 0.0095 to 0.0008. The section reports the Holm flips carefully as boundary cases but says nothing about this one. Finding 4 also still cites +0.0768, and that is not the v2 value the manuscript will quote (D-061).
- **What must change.**
  - State the v2 as-run figure (+0.0855 [+0.0503, +0.1219] against 0.0863) and call it the same kind of boundary case.
  - Scope the "indifferent" claim to tie-free scoring.
  - Make sure the manuscript does not carry +0.0768.

### F2 (minor): D-061 is described as "proposed, not accepted", but it has been accepted
The report says "(proposed)" at line 188 and "D-061 is proposed, not accepted … pending César" at line 230. `DECISIONS.md` D-061 has been **Accepted** since `10868c8` (2026-10-19 09:10), which is after the report's last change at `e083dc9`. Add a dated note; the reports are a record, so do not rewrite the sentence in place.

### F3 (minor): the H8 batch-noise floor is printed but not reported, and the audit response still lists it as unverifiable
- **What the table shows.** "The unchanged queries (the H8 floor)" in `comparison.md` shows **0** moved hits on all 1,303 unchanged rung queries and all 2,738 unchanged isolated queries, for every arm, tie-free and as run.
- **What I checked.** The ColBERT `results_top100` records for those 4,041 queries are identical between v1 and v2 (scratchpad `h8check.py`).
- **Why it matters.** With a floor of 0, ColBERT's 77 rung and 53 isolated moved hits are all on changed queries and can be attributed to the repair. The section should say so, and the "Unverifiable: … H8 as a floor" row is wrong.

### F4 (minor): the registered comparison does not print n for each version
- **What D-061 and A8 require.** D-061 (2) and A8 ask for "n, concepts and stamps for both" versions.
- **What `comparison.md` prints.** One population line for v2, plus a sentence the generator asserts. X2's denominator is the at-risk mass, and it differs between versions: `bge_m3_dense` 420 → 418, ColBERT 739.13 → 741.85 (`marginal.md` against `v2/marginal.md`).
- **What must change.** The X1–X3 table should carry each version's n. S9's audit F1 raised the same gap, and S9 fixed it at `70f2776`; S8 was not fixed.

### F5 (minor): the H4 sentence does not name the 4 concepts or the draw-noise limitation
The design says "Every H4 sentence names the 4 concepts and the draw-noise limitation." The A8 bullet ("H4 under the design's rule reads *partly supported* on both versions …") does neither. It relies on D-054 by reference.

## Unverifiable
- **Full test suite at HEAD.** `logs/v2/pytest_20261019d.out` shows 2,098 passed, but the log carries no commit stamp. I ran only the three suites listed above.
- **The first-time-run guarantee.** It rests on `logs/v2/*.out` and `run_v2_base.sh`, which are git-ignored. They are consistent with the run timestamps (`created_utc` from 21:01Z on) but are not committed evidence.

## Exit criteria (applied to the v2 re-run)
| Criterion | Met | Evidence |
|---|---|---|
| A8 recorded before any v2 run | Yes | `4f56a39` at 19:54:58Z; first v2 run at 19:55:12Z |
| 1. v2 sets resolve; intake tests pass | Yes | `run_context.py:98` `V2_QUERY_SETS`; `test_intake_20261016.py` passes |
| 2. 36 runs: clean, dev, resolving, stamped against the feature-table digest | Yes | `stamps.py`: 36/36; `check_run_inputs.eol.out`: 557/557 |
| 3a. T1–T13 and Fig. 6 generated and byte-identical on regeneration | Yes | re-run at `23a162f`: 16/16 identical |
| 3b. Prose guard and traceability | Yes | tests pass |
| 3c. n, both intervals and per-concept signs on every contrast in T1–T13 | Yes | `v2/*.md` |
| A8: `comparison.md` gives concepts and stamps for both versions | Yes | Sources section, `same_design()` |
| A8: `comparison.md` gives n for each version | No | F4 |
| 4. X1–X3 read tie-free and as run, with D-004 and T3 beside | Yes | `v2/predictions.md`, `v2/d004.md` |
| 5a. H4 resolved under the frozen rule | Yes | *partly supported* on both versions; recomputed |
| 5b. The H4 sentence names the 4 concepts and the draw-noise limitation | No | F5 |
| 5c. Readings that move on v2 are named, with their uncertainty | No | F1: the as-run TF-IDF X2 boundary is not disclosed |
| 6. D-052 and D-053 unchanged | Yes | no edits after the freeze |
| 7. Full suite passes | Unverifiable at HEAD | log only; 3 relevant suites re-run and passing |

Scratch work: `C:/Users/cesar/AppData/Local/Temp/claude/D--Users-cesar-Dev-Phd-bc3cat-retrieval/10f97cf9-08cf-4a1f-a3fa-ba7f0f308208/scratchpad/` (`regen_s8.py`, `stamps.py`, `holm.py`, `h8check.py`, `regen/`, `committed.sha256`, `regen.sha256`). No repository file was modified. `SPRINT_S11_AUDIT.md` shows as modified in the working tree; another session did that, not this audit.

---

# Sprint S8 — audit of amendment A8 (v2 re-run)

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-19 · report `858d15c` (section "## v2 re-run (A8, 2026-10-18)" of `SPRINT_S8_REPORT.md`; A8 row at `4f56a39`) · results `docs/synthetic-oe/results/S8/v2/` @ `858d15c` (on-disk SHA-256 of all 16 files equals both `logs/v2/tables_gen1.sha256` and `tables_gen2.sha256`) · runs `runs/OE/dose_texto_v2/<arm>/`, `runs/OE/isolated_texto_v2/<arm>/` (18 S8 arms each; 5 further `structured_pipeline_*` directories in each are later S9/S11 runs at `858d15c`, not read by any S8 table), identity `runs/OE/texto/<arm>/`, references `runs/OE/single_texto_v2/`, `runs/OE/stacked_texto_v2/`.

## Verified
- Provenance (check 1) — all 36 S8 v2 `run_meta.json`: `code_commit` `8d1ffd2d…`, `code_dirty: false`, `code_dirty_paths: []`, `split: dev`, 1,640 / 2,952 queries (3,000 / 5,400 before split, 0 dropped); `query_set_sha256` `ac0cb6a5e287bf68…` and `35de79679ed15f4b…` equal the host SHA-256 of `OE_dose_texto_v2_feats.parquet` and `OE_isolated_texto_v2_feats.parquet`; the input digests `8becd49ad0fd1f37` / `95c0c2edaef0c7dc` / `02a2c270d7ffe147` / `b3c58fcb38fd294f` in `run_provenance.md` equal the host digests of the four JSON files. The 7 config stamps equal the host YAML digests as-is (LF). T11 lists `single_texto_v2` (18 runs, `8d1ffd2`) and `stacked_texto_v2` (3 lexical at `4f56a39`, 15 at `8d1ffd2`, all clean) as T2's and T8's references, as A8 states. The identity side is the same `texto` runs as v1 (`31bf1a1`, `922ae53`, `a5700a6`, `2e49566`).
- v1 untouched — `git diff 4f56a39..HEAD -- results/S8/*.md results/S8/figures` is empty and the working tree is clean for them; v1 run files carry mtimes 2026-10-02 and stamps `f330ee3`, `ef8c6295…`/`701dd1da…`. No `dose_texto*`/`isolated_texto*` run is in `runs/_archive/dirty/2026-10-18/`.
- Sample identity (check 3) — recomputed from the JSON files: v2 = v1 record for record, same order, every field equal except `text`, which differs on exactly the 547 dose and 348 isolated keys `OE_v2_changes.jsonl` lists. On dev: 328 leaves (`OEB020$` 61, `OEB030$` 87, `OEB230$` 93, `OEB290$` 87), 1,640 rung and 2,952 isolated queries; identical golds, concepts, rung keys, isolated keys, member sets and added-type sequence on both versions; 337 rung queries changed (23 / 46 / 72 / 95 / 101 by rung, 0 without `template_paraphrase`) and 214 isolated, all `template_paraphrase` (214 / 328 = 65 %). Pairing: `summarise` seeds `strat_weights` from the cell label alone (`_rng("strat|"+label)`), `evaluate` uses the same label `s8|{test}|{arm}|{variant}` for both versions, `same_design` asserts equal concept arrays before `write_comparison`, and `paired_diff` subtracts `draws_all` draw by draw after checking length and `clusters_key` — so the v2 − v1 intervals are paired.
- X2 `bm25_unigram` — `OE/dose_texto_v2/bm25_unigram__k1-0.60__b-0.35__OE` + `OE/isolated_texto_v2/…`: recomputed +0.0643 on both versions, at-risk mass 228.7, per concept +0.0720 · +0.0577 · +0.0788 · +0.0466; matches T10 v1/v2 and `comparison.md`.
- Holm (check 4) — recomputed from the 21 raw p's of each `predictions.md`: equals every tabled Holm p. v1: `bge_m3_dense` p 0.0054 rank 13 (×9 = 0.0486), `bm25_unigram` p 0.0060 rank 14 (×8 = 0.0480, carried up to 0.0486). v2: `bm25_unigram` 0.0060 rank 13 (×9 = 0.0540), `bge_m3_dense` 0.0062 rank 14 (×8 = 0.0496, carried up to 0.0540). The 12 p's at 0.0002 and the X1 p's (0.0522 → 0.0706, 0.3736 → 0.5059, 0.2532 → 0.1054) are the rest of the family.
- ColBERT rung 5 — `OE/dose_texto_v2/bge_m3_colbert__OE`: recomputed 0.2923 → 0.2844, prediction 0.2762 → 0.2807, 19 leaves moved; my own stratified bootstrap of the per-leaf difference gives [−0.0241, +0.0081] / [−0.0241, +0.0086] / [−0.0244, +0.0084] over three seeds, against the table's [−0.0241, +0.0086].
- ColBERT isolated `template_paraphrase` — `OE/isolated_texto_v2/bge_m3_colbert__OE`: δ recomputed −0.3449 → −0.3371 (+0.0078), 53 leaves moved, my interval [−0.0185, +0.0333] against the table's [−0.0181, +0.0334]. Also recomputed: `dense_e5` −0.2470 → −0.2317, `bge_m3_dense` −0.8902 → −0.8811; X1 ColBERT +0.0199 → +0.0151, `bge_m3_dense` +0.0343 → +0.0320, `dense_e5` −0.0671 → −0.0678; X2 `bge_m3_dense` +0.0738 → +0.0742; draw-noise bar ColBERT 0.2171 → 0.2130, lexical bars unchanged; text-equal leaves 89 on both.
- Lexical arms, X1–X3 — recomputed identical on v1 and v2 for `bm25_unigram`, `bm25_unigram_params` and `tfidf_phrases_replace` (X1 −0.0015 / −0.0129 / +0.0069, X2 +0.0643 / +0.0974 / +0.1010, X3 −0.1730 / −0.1918 / −0.1892), every rung accuracy identical, 0 rung hits moved. Isolated: 0 hits moved for `bm25_unigram` and `tfidf_phrases_replace`; **2 moved for `bm25_unigram_params`** (see F1).
- H8 floor — 0 tie-free and 0 as-run hits moved on any of the 1,303 unchanged rung and 2,738 unchanged isolated queries for all 18 arms (table) and for the 7 recomputed.
- H4 label (check 6) — v2 T10: X1 supported for `dense_e5` only, X2 for four arms, no arm both, none contradicted → *partly supported* by the frozen rule, same as v1; `comparison.md` prints both. "Exceeds noise" is no for `bm25_unigram` and `bge_m3_dense` X2 on both versions; the only "yes" (`tfidf_phrases_replace`, tie-free) is unchanged from v1, so D-054's final restatement is in the same position on v2 as on v1. Known-wrong 5's counts 481 / 316 → 447 / 296 match v1 and v2 `d004.md`.
- Order (check 5) — the A8 row entered at `4f56a39`, committed 2026-10-18 19:54:58 UTC and not edited since; the runs stamp `8d1ffd2` (committed 20:35:57 UTC); the earliest S8 v2 run started 21:00 UTC (`logs/v2/.start__dose_texto_v2__bm25_unigram…`, `created_utc` 21:01:05 UTC); the last isolated run 21:40 UTC; the v2 tables were written 23:04–23:09 UTC and committed with the report section at `858d15c` (23:18:53 UTC).
- Generator — `git diff 2fc7bc3 a8277ce` on `build_results_s8.py` adds `configure`, `require_runs`, `assemble`, `same_design`, `write_comparison` and the `draws_all`/`clusters_key` fields of `summarise`; `terms`, `predicted`, `read`, `evaluate`, `h4_resolution`, `draw_noise` and the bootstrap are untouched, so "A2–A7 apply unchanged" holds; unchanged since `a8277ce`.
- Line endings (check 7) — no S8 v2 stamp or digest is a CRLF phantom: config, feature-table and JSON digests all reproduce from the host files as they are. The v1 tables are checked out CRLF (`i/lf w/crlf`) while the v2 tables are LF; git normalises both, content is identical, and nothing below rests on it. S8 does not digest `SPLITS.md`.

## Findings
### F1 — major — The "lexical arms are indifferent" sentence is contradicted by the oracle twin's own row in `comparison.md`
The section says: for `bm25_unigram`, "its oracle twin and the oracle TF-IDF every X1–X3 estimate, every rung and every isolated cell is identical on v1 and v2 (0 hits moved among the changed queries)". `comparison.md` T2 (line 179) and the H8-floor table (line 379) print for `bm25_unigram_params` isolated `template_paraphrase` 0.4878 → 0.4939, δ −0.5122 → −0.5061, v2 − v1 +0.0061 [+0.0000, +0.0152], **2 hits moved** among the 214 changed queries; recomputed from `OE/isolated_texto_v2/bm25_unigram_params__k1-0.60__b-0.35__OE`: 2 moved. The X1–X3 estimates, the five rungs and the T3 bar are identical for all three arms (verified), but "every isolated cell" and "0 hits moved" are false for one of the three. The mechanism offered, "moving a value to its right slot does not change a bag of words", is also not what the data show: the repairs replace words (`OE_v2_changes.jsonl`: "se detallan en" → "son:"), the bag changes, and the two moved hits are the proof; the arms are indifferent in outcome on these leaves, not by construction. Restrict the sentence to `bm25_unigram` and `tfidf_phrases_replace`, state the oracle twin's 2 moved isolated hits and its δ, and replace the mechanism with the observation.

### F2 — minor — The Holm explanation is right for `bm25_unigram`, half right for `bge_m3_dense`, and omits that the flip sits inside the bootstrap's Monte Carlo resolution
The section says both readings move "because the Holm family's other p-values moved". For `bm25_unigram` that is exact: its raw p is 0.0060 on both versions and it moved from rank 14 (×8) to rank 13 (×9) because `bge_m3_dense`'s p crossed it. For `bge_m3_dense` its **own** raw p moved, 0.0054 → 0.0062 (its per-concept X2 moved, +0.0420 → +0.0333 and +0.0865 → +0.0980, with 9 rung and 13 isolated hits); at rank 14 its own Holm value is 0.0496 < α, and it reads 0.0540 only because Holm's step-down carries `bm25_unigram`'s 0.0540 upward. Both raw p's differ between versions by 1–4 draws in 10,000 (p resolution 0.0002); my own stratified bootstrap over ten seeds gives p in [0.0046, 0.0078] for both arms on both versions, so the supported / not-supported label on each version is a coin of the bootstrap seed, not of the data. The report should say so: the two X2 readings are at the α boundary under either version, and the version difference is within Monte Carlo noise of the registered procedure. No estimate, interval or table is wrong.

### F3 — minor — Directional sentences without their intervals
"The order-sensitive arms move, a little, towards less damage" quotes +0.0078, +0.0152, +0.0091 and three X1 shifts without intervals; the paired stratified intervals in `comparison.md` all include 0 (ColBERT [−0.0181, +0.0334], `dense_e5` [−0.0030, +0.0366], `bge_m3_dense` [−0.0122, +0.0305]; X1 ColBERT [−0.0147, +0.0051], `bge_m3_dense` [−0.0091, +0.0046], `dense_e5` [−0.0076, +0.0069]). "The gap between observed and predicted closes a little" rests on T4's +0.0161 [−0.0402, +0.0717] → +0.0037 [−0.0541, +0.0608], neither interval excluding 0 and no interval on the change. Operating rule 1 and D-061 (v2 − v1 "carries an interval and no reading") want the intervals beside each delta, or the sentence recast as "no v2 − v1 difference is resolved for any order-sensitive arm".

### F4 — minor — "(checked before anything was written)" is not what the generator does, and the section cites nothing else
The same-leaves / same-keys / same-structure check in the code is `same_design`, called inside `write_comparison`, after T1–T13 and Fig. 6 have been written to `results/S8/v2/` (order of `main`). The fact is true — verified here independently, and `tests/test_intake_20261016.py::test_v2_keeps_every_record_in_order_and_changes_only_text` exists from the 2026-10-16 intake — but the section's phrasing attributes the check to a point no artefact records. Cite the intake test (or the A8 row's "verified by `tests/test_intake_20261016.py`") instead.

### F5 — minor — The known-wrong 5 re-read is pointed to but not stated, and its direction reverses on v2
The section says the three v1 readings that changed without pantry artefacts "are re-read in `results/S8/v2/d004.md`" and stops. That table shows: X1 `dense_e5` still not robust (clean −0.0561, not supported); X2 `bm25_unigram` now *not supported* in both full and clean readings; X2 `bge_m3_dense` full *not supported* but clean **supported** (+0.0922 [+0.0307, +0.1554], Holm 0.0280). On v1 the report's known-wrong 5 said all three changed "toward *not supported*"; on v2 one changes the other way. State the three outcomes in the section; with F2, it is the same boundary case seen from the other side.

## Unverifiable
- "36 first-time runs" — no earlier `dose_texto_v2`/`isolated_texto_v2` run exists on disk or in `runs/_archive`, and the `.start` markers in `logs/v2/` are the first for these names, but a run deleted rather than archived would leave no trace; nothing suggests one.
- H8 as a floor — the table prints 0 moved hits on unchanged queries for every arm, including ColBERT; whether that is because the v2 batch composition happened to reproduce v1's near-tie outcomes or because none were near a tie cannot be told from the top-100 files alone (no logged re-measurement for these two sets).
- The report's statement that the section's figures were "generated, never typed" is verified for every number traced above; the two-generation byte-identity itself rests on the implementer's `logs/v2/tables_gen1.sha256` and `tables_gen2.sha256` (git-ignored), which I compared with the files on disk but could not re-run (the generators overwrite the shared results directories).

---

*The record below is the sprint's earlier audit(s), kept as written.*

# Sprint S8 — audit (second, fresh session)

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-02 · report `ac89864` · runs `runs/OE/dose_texto/` (18), `runs/OE/isolated_texto/` (18), `runs/OE/texto/` (identity, 7 base arms)

## Verified
- **Run stamps, all 36.** Every `run_meta.json`: split `dev`, `code_dirty: false`, commit `f330ee3`, query-set digest `ef8c6295` (dose, 1,640) / `701dd1da` (isolated, 2,952). Every `config_sha256` equals the SHA-256 of the config file in the tree. Data digests re-hashed: `OE_dose_texto.json` `555fab84`, `OE_isolated_texto.json` `054041ff`. `check_run_inputs.py --collection OE`: 280 of 280 resolve.
- **Split.** The feature tables hold all 7 concepts (3,000 / 5,400 rows), but every S8 run contains only `OEB020$ 030$ 230$ 290$`. No test-side query was scored. Nothing was tuned, and every config SHA equals the S4/S5 frozen arm.
- **Regeneration.** I ran `build_results_s8.main()` at HEAD in `bc3cat-s3` with `OUT` redirected to `/tmp`. All 14 tables and `fig6_ladder.png` are byte-identical to the committed `results/S8/`. `src/` has not changed since `2fc7bc3`, and the tree was clean before and after.
- **Independent recomputation** from `results_perquery.parquet` (as run). All of these match T1, T10 and T13:
  - X1 `dense_e5` −0.0671 (headline X1)
  - X2 ColBERT +0.1193, `tfidf_phrases_replace` +0.0768 (the ⚐ case), `bm25_unigram` +0.0609, `bm25_unigram_params` +0.0927
  - X1 for all 7 arms
  - rung-5 item Acc@1 `bm25_unigram` 0.0000 and parent 0.0884; ColBERT 0.2835 item
  - T13 reference `bm25_unigram_params` −0.0586 and `dense_e5` −0.0909 (at-risk mass 99)
  - text-equal count 89 of 328
- **Prose against tables.** Checked against T1, T2, T4, T6, T8, T9, T10, T12 and T13: findings 1, 2, 3, 4 and 7, known-wrong 4–5, and the floor-bound shares. All quoted values match. This includes the T12 ceiling/floor rates (−0.3694 / +0.3024 / −0.4785 / +0.0690 / −0.2800 / +0.0243), the T9 clean X1 `dense_e5` −0.0524, and the pantry counts 481/1,640 and 316/2,952.
- **Executed path.** The tie-free hits, the clipped prediction, the D-004 clean masks and the D-053 sign rule are all called from `evaluate()` (`build_results_s8.py` l.192–299). The as-run/tie-free consistency guard (l.128–132) is active.
- **Design freeze.** `git diff 4f62d5a..HEAD -- SPRINT_S8_DESIGN.md` shows only the freeze header (`75798ee`). Amendments A1–A7 are append-only: every later commit to the file adds 1 line and deletes 0. D-052 and D-053 are unchanged since the freeze.
- **Tests.** `test_intake_s8` + `test_report_traceability`: 19 passed. `test_generated_prose`: 12 passed. Full suite: 1334 passed, 2 skipped, 1 xfailed, which matches exit criterion 7.

## Findings
### F1 — major — A reference chosen after the results were seen is used to recast the registered X2 outcome. The table that produces it says it must not be used that way.
- **What the artefacts say.** T13's header says the reference is "never cited as evidence for or against H4".
- **What the report does.** The Hypotheses H4 row, finding 4 ("Read against it, the excess is not draw noise for four or five arms") and D-054's revised manuscript sentence ("within the registered draw-noise bar but not within a signed draw reference adopted after the fact") all use it to move the registered result to "ambiguous".
- **Self-contradiction.** D-054 then says "S8's post-hoc X2 reading does not enter the manuscript as a result", while its own proposed manuscript text carries that reading.
- **Under the frozen rule** (design, "Isolated and ladder edits are different draws"), no X2 excess is attributed to interaction. The only exception is `tfidf_phrases_replace`, and only tie-free (T10).
- **"Near 0 for every arm" (finding 4, known-wrong 2) is not what T13 shows.** As run, `bm25_unigram_params` is −0.0586 [−0.1134, −0.0044], which excludes 0. `dense_e5` is −0.0909 [−0.1828, +0.0000]. A non-zero signed draw gap also weakens known-wrong 2's premise that X2's expectation under draw noise is 0.
- **What must change.**
  - State the registered outcome as the result.
  - Present T13 only as the motivation for what S12 must register.
  - Remove "four or five clear" from the H4 row and from D-054's manuscript sentence.
  - Quote the reference with its intervals instead of "near 0".

### F2 — minor — The range of text-different noise rates in finding 5 is wrong.
- **What the report says.** "text-different rates of 0.1659 to 0.2469" for the six arms other than TF-IDF.
- **What T3 says.** `dense_e5` is 0.1255.
- **Why the test missed it.** The traceability test passes because both endpoints appear in T3.
- **What must change.** Restate the range as 0.1255–0.2469.

### F3 — minor — The prediction-region split in T12 is signed by construction, but the report reads it as a substantive rate.
- **Why.** Ceiling-bound and floor-bound are defined by the isolated outcome, and the isolated queries are a different draw from the rung queries. With any draw disagreement, the ceiling-bound term is < 0 and the floor-bound term is > 0 even with no interaction at all (regression on a noisy predictor).
- **What the report says.** Finding 2 ("Where every single edit survives alone, the stack still fails") and known-wrong 3 ("the net of a super-additive and a sub-additive rate") read the two terms as real effects.
- **What must change.** Say that the signs are expected under draw noise alone. Do not call either rate super- or sub-additive.

### F4 — minor — Comparisons across different populations are still framed as comparisons.
- **Finding 8's heading.** It says the two gradients are "of the same order". At dose 2, BM25 is −0.5606 on S7 (query CI [−0.5988, −0.5229], 26 excluded, 27 concepts) against −0.7510 on the ladder [−0.7959, −0.7066]. The intervals do not overlap.
- **Known-wrong 4.** It still sets −0.9192 against −0.4153 as a correction.
- **What the design says.** T8 and T2's S4 column are "never read as a contrast".
- **What must change.** Drop the comparative heading and keep the table descriptive.

### F5 — minor — The S10/S11 recommendation is not supported over its alternatives.
- **What the report says.** The reranker "needs a first stage of the ColBERT kind".
- **What T1 shows.** `dense_e5` and the oracle TF-IDF also keep parent Acc@1 at 1.0000 at rung 5.
- **What must change.** Name all three, or state why ColBERT is preferred.

## Unverifiable
- **A2's process claims** ("no metrics file opened", "fixed before first run"). Only the commit order can be checked, and it is consistent.
- **Generator runs `run1`–`run7`.** Their logs carry no commit (the report's debt list states this). This is moot for the current outputs, which I regenerated byte-identically.
- **OEB fixture as a separate gate.** I did not identify it separately; it is covered only insofar as it sits inside the 1334-test suite.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1. Sets resolve, `balanced_texto` gone, zero undecidable | yes | `test_intake_s8.py` passes; runs hold only the 4 dev concepts |
| 2. 36 clean runs on the two digests, resolving | yes | 36 `run_meta.json`: dev, clean, `f330ee3`, `ef8c6295`/`701dd1da`, config SHAs match; `check_run_inputs` 280/280 |
| 3a. T1–T11 + Fig. 6 generated, byte-identical | yes | Regenerated at HEAD: 14 .md + PNG identical |
| 3b. Prose guard | yes | `test_generated_prose` 12 passed |
| 3c. n excluded, both intervals, per-concept on every contrast | yes | T1–T10 columns present (A4/A5); T3 holds rates, not contrasts |
| 4. X1–X3 read tie-free, as run, clean, noise beside | yes | T10 (as-run columns A5), T9 |
| 5a. H4 resolved under the frozen rule | yes | T10 "partly supported", as A3 corrected; the report's post-hoc gloss is F1 |
| 5b. G3 in the design's words; 4-concept scope; non-identifiable pairs; different-draw limitation | yes | Finding 6, Hypotheses, T7 |
| 6. D-052, D-053 unchanged | yes | No diff to either in `DECISIONS.md` since `4f62d5a` |
| 7. Full suite and OEB fixture | yes | 1334 passed, 2 skipped, 1 xfailed (rerun) |

Files: `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\sprints\SPRINT_S8_REPORT.md`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S8\draw_reference.md`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S8\draw_noise.md`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S8\x1_split.md`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S8\s7_reference.md`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\DECISIONS.md` (D-054, l.1439)

---

*The first audit of this sprint (PASS WITH FINDINGS, report `9b53476`) follows unchanged.*

# Sprint S8 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-02 · report `9b53476` (HEAD `2f6cf7d`) · runs `runs/OE/dose_texto/` (18), `runs/OE/isolated_texto/` (18), `runs/OE/texto/` (identity side)

None of the FAIL triggers applies. Every number I traced reproduces. No comparison mixes samples. The design changed after the freeze only by filling in its freeze stamp. The findings are about interpretation, and four of them are major. They matter because D-054 proposes manuscript wording built on them.

## Verified
- **Freeze.** `git diff 4f62d5a..HEAD -- SPRINT_S8_DESIGN.md` is one line: the `Frozen at` placeholder replaced by `4f62d5a · 2026-10-01`. Amendments A1–A4 are dated and each one is committed before the outputs it governs. The 36 runs ran 21:52–22:46 UTC, after A1 (`f330ee3`, 21:51 UTC). The generator `cd81248` was committed at 22:48 UTC, after the last run.
- **Runs.** All 36 are at `f330ee3`, `code_dirty: false`, split `dev`, 1,640 / 2,952 queries, `dropped` 0, digests `ef8c6295` / `701dd1da`. `check_run_inputs.py --collection OE`: 280 of 280 resolve. Every config SHA matches the arm's identity run.
- **Inputs re-hashed.** `OE_dose_texto.json` `555fab84`, `OE_isolated_texto.json` `054041ff`, `OE_long_feats` `643f1a72`, `OE_long_norm` `75477221`: all match the report header.
- **Regeneration.** `build_results_s8.py` at HEAD (no change since `907990f`) was run in `bc3cat-s3` with OUT redirected to `/tmp`. All 12 tables and `fig6_ladder.png` are byte-identical to `docs/synthetic-oe/results/S8/`.
- **Independent recomputation** from `results_perquery.parquet` (my own script, not the generator), as run:
  - T1 as-run item and parent Acc@1 match for `bm25_unigram` (0.9360 → 0.0000), `bge_m3_colbert` (0.2835 at rung 5), `dense_es_hiiamsid` (0.0488) and `bge_m3_dense`. Parent at rung 5: 0.0884, 0.9970 (tie-free), 1.0000 (`dense_e5`).
  - X1 `dense_e5` −0.0671: traced to `OE/dose_texto/dense_e5__OE` + `isolated_texto` + `texto`, and it matches.
  - X1 `bge_m3_dense` +0.0343 and X2 +0.0738 match. X2 `dense_es_hiiamsid` +0.1080 matches.
  - `bge_m3_dense` and `dense_e5` have the same rung-4/5 values (0.1463, 0.1280). This is real in the raw runs, not a generator mix-up.
- **Report figures traced to their tables.** All match:
  - T1: rung-5 item and parent values; slopes −0.0551 to −0.1918 (T6).
  - T2: `unit_expansion` −0.9192 (S4 −0.4153) and `num_to_text` −0.8716.
  - T3: draw-noise rates 0.0863 / 0.1489 / 0.2171 / 0.0593.
  - T4: floor-bound shares 0.8018–0.9817.
  - T8: −0.5606 / −0.7510 and −0.6000 / −0.5174.
  - T9: flag counts 481/1,640 and 316/2,952, and the clean `dense_e5` estimate −0.0524.
  - T10: all 21 estimates, intervals, Holm p values and readings quoted in the report.
- **Sample and split.**
  - Every contrast is within leaf on the same 328 dev leaves (`OEB020$ 030$ 230$ 290$`).
  - `ladder_design` filters on dev parents, and no test-side ladder query enters any table.
  - Nothing is tuned: every config SHA is the one frozen in S4/S5.
  - The `OE_long_norm` identity exception for ColBERT and `bge_m3_dense` is disclosed in the header, as S7's audit required.
- **Mechanisms the report credits.** All execute on the reported path, in `evaluate`/`terms`/`read`: the tie-free reading, the D-004 clean subset, the stratified bootstrap, the D-053 sign rule (`SIGN_MIN`), Holm across the 21 tests, the floor rule, the X2 at-risk threshold and the ⚑ flag.
- **Tests.**
  - `test_intake_s8`, `test_report_traceability` and `test_generated_prose`: 31 passed.
  - Full suite: 1334 passed, 2 skipped, 1 xfailed, as the report states.

## Findings

### F1 — major — X1 is floor-bound for most arms, not only BM25. "Tracks the prediction closely" and D-054's "roughly as the clipped sum predicts" are not supported.
- **Report.** Finding 3 confines the problem ("with the prediction at 0, a leaf can only count as sub-additive") to BM25. Finding 2 and D-054 say the cumulative loss is close to the clipped-additive prediction "for six of seven arms".
- **T4's floor-bound column, rungs 2–5:**

  | Arm | Floor-bound share |
  |---|---|
  | `bm25_unigram_params` | 0.67–0.97 |
  | `bge_m3_dense` | 0.67–0.94 |
  | `dense_es_hiiamsid` | 0.70–0.96 |
  | `tfidf_phrases_replace` | 0.35–0.89 |
  | `bge_m3_colbert` | 0.29–0.66 |

  `bge_m3_dense`'s rung-5 excess of +0.0640 sits on 0.9360 floor-bound leaves.
- **Why it matters.** X1 has little power against super-additivity wherever the prediction is 0. A non-significant X1 there is not evidence of additivity, and no equivalence margin was registered.
- **What must change.** Extend finding 3's caveat to every arm, with its floor-bound share. Rewrite finding 2 as "X1 not supported" with no closeness claim. Remove "roughly as the clipped sum of their isolated effects predicts" from D-054's proposed manuscript wording.

### F2 — major — The only supported X1 reading (`dense_e5`) comes entirely from leaves the arm misses at identity.
- **Report.** "X1 is supported only for `dense_e5`, −0.0671 [−0.1029, −0.0328], negative in all four concepts."
- **My recomputation** (as run equals tie-free for this arm; the pooled value reproduces exactly):

  | Leaves | n | X1 |
  |---|---|---|
  | Hit at identity | 127 | **+0.0512** |
  | Missed at identity | 201 | −0.1418 |

- **Why.** On an identity miss, any isolated hit raises the clipped prediction above 0. The "excess loss" is then the loss of a lucky isolated hit, not damage beyond the additive sum. On the leaves where the question is meaningful, the sign is sub-additive.
- **What must change.** State this decomposition beside the reading. Do not offer it as evidence of super-additivity, quite apart from its D-004 non-robustness.

### F3 — major — The one X2 excess that "clears the draw-noise bar" holds only tie-free, and nothing in the tables shows this.
- **Report** (finding 4, D-054): "only one excess clears the draw-noise bar … `tfidf_phrases_replace`", +0.1010 against 0.0863.
- **Recomputed with the generator's own `evaluate`:**
  - As run, `tfidf_phrases_replace` X2 is **+0.0768**, below 0.0863.
  - This is the arm with the most rank-1 ties (text-equal disagreement 0.1489).
  - ColBERT's X1 also changes sign (+0.0199 tie-free, −0.0168 as run), as does TF-IDF's (+0.0069 / −0.0175).
- **Why it is invisible.** T10 prints as-run *readings* only, never as-run estimates. The design's ⚑ rule fires on a change of reading, not on a change of the noise exceedance.
- **What must change.**
  - Print as-run estimates and intervals for X1/X2.
  - Flag noise exceedance that differs between the two readings.
  - Restate D-054's "one of those excesses exceeds the draw noise" as not robust to tie handling.

### F4 — major — Deceleration is used as evidence against H4. On this outcome it cannot be.
- **Report.** Finding 1: "No arm shows the accelerating curve that super-additivity predicts." Known-wrong 3: H4's mechanism "predicts an accelerating loss. Every arm's curve decelerates." D-054's context cites the same.
- **Why the inference fails.** Item hit is bounded at 0, and BM25-like arms reach about 0 by rung 3–4. A positive quadratic is therefore mechanical; T6's own header says "a floor bends the curve upward". Independent per-edit survival (p^k) is already convex, so super-additivity does not imply a concave curve.
- **"Every arm's quadratic term is positive" is stated without its interval.** `dense_e5` is +0.0051 [+0.0000, +0.0101], concept interval [−0.0011, +0.0086], one concept negative (−0.0047).
- **What must change.** Drop known-wrong 3. Report the quadratic as descriptive, which is what the design says it is.

### F5 — minor — "The encoders keep [the concept]" (finding 7) is false for two of the four encoders.
- At rung 5, parent δ is −0.1128 [−0.1463, −0.0793] for `bge_m3_dense` and −0.1402 [−0.1768, −0.1037] for `dense_es_hiiamsid` (T1, parent level).
- **What must change.** Restrict the claim to ColBERT and `dense_e5`.

### F6 — minor — Directional language on intervals that include 0.
- Finding 2 says ColBERT and `bge_m3_dense` do "slightly *better* than predicted": +0.0199 [−0.0234, +0.0643] and +0.0343 [+0.0000, +0.0694] (p 0.0522).
- ColBERT's sign reverses as run (F3).
- **What must change.** Remove the directional wording.

### F7 — minor — The noise-bar characterisation contradicts T3's own numbers.
- Finding 5, known-wrong 2 and D-054's "Open with it" call BM25's bar "overstated" and ColBERT's "slightly inflated".
- T3's text-equal (tie-only) rates say the reverse: `bm25_unigram` 0.0404 and `bm25_unigram_params` 0.0348, against ColBERT 0.0593. Only TF-IDF (0.1489) has a material tie component.
- **What must change.** Restate the characterisation from T3's numbers.

### F8 — minor — Between-population numbers are read as contrasts, against the design.
- **Known-wrong 4.** S4's isolated δ "would have been wrong by a wide margin" (−0.9192 vs −0.4153). The design says S4's figures are "never read as a contrast", and S4's interval [−0.7625, −0.0653] is not quoted.
- **Finding 8's heading.** "was not just family" is drawn from T8, which the same paragraph says is not a contrast. The within-leaf claim can be supported from X3; cite that instead.

### F9 — minor — The same ladder δ is printed with two different stratified intervals in T1 and T8.
- `bm25_unigram` rung 2: T1 [−0.7959, −0.7066], T8 [−0.7955, −0.7046]. ColBERT rung 3: [−0.5661, −0.4685] vs [−0.5657, −0.4690].
- This is the defect of S7 audit F7 again (`write_s7_reference` draws its own bootstrap label).
- **What must change.** T8 should reuse T1's draws.

### F10 — minor — The D-004 robustness caveat is applied unevenly.
- The Hypotheses row and D-054's manuscript sentence ("six of seven arms") carry X1 `dense_e5`'s "not robust" caveat.
- They omit that two of the six X2 readings (`bm25_unigram`, `bge_m3_dense`) are also not robust to D-004 and also differ as run (⚑).

## Unverifiable
- **Generator runs.** `logs/S8/` holds seven `build_results_s8` runs (00:53–01:29, +02:00). A3/A4 account for five: one at `cd81248`, two at `da654e2`, two at `907990f`. The logs contain only "wrote docs/synthetic-oe/results/S8", so the code state and output of the two extra runs cannot be established.
- **A2's process claims.** "No metrics file has been opened in this session" and "fixed before the generator first ran" are process claims. Only the commit order (A2 committed with the generator, before the first generation) can be checked, and it is consistent.
- **"Fig. 6 shows observed accuracy close to the prediction"** (D-054) is a visual claim. `figures.md` holds the plotted values, and F1 applies to them.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1. Sets resolve, `balanced_texto` gone, zero undecidable | Met | `tests/test_intake_s8.py` passes (31 passed across the three S8 test files) |
| 2. 36 clean dev runs on the two digests, resolving | Met | 36 × `f330ee3`, `code_dirty: false`, `dev`; `check_run_inputs` 280/280 |
| 3a. T1–T11 and Fig. 6 generated, byte-identical, under the prose guard | Met | Regenerated in `bc3cat-s3`: 13/13 identical; prose test passes |
| 3b. n scored / n excluded on every item-level figure | Met | Columns present (A4), 0 throughout |
| 3c. Both intervals and per-concept signs on every contrast | **Not met** | T9's clean readings print the stratified CI only: no concept CI, no per-concept estimates (needed to audit the sign rule; `dense_e5` clean fails on both Holm 0.1854 and 2/4 signs, visible only by recomputation). As-run X1/X2 readings print no estimate or interval at all (F3) |
| 4. X1–X3 read tie-free, as run and clean, with draw noise beside | Met | T10, T9 (as-run readings as labels only; see F3) |
| 5. H4 by the rule, G3 in the design's words, scope, pairs, draw limitation | Met | The rule is applied literally (*partly supported*) and flagged for César. G3's wording is verbatim. Interpretation defects are F1–F4 |
| 6. D-052, D-053 recorded | Met | `DECISIONS.md` lines 1416–1438, both accepted 2026-10-01 |
| 7. Full suite and OEB fixture | Met | 1334 passed, 2 skipped, 1 xfailed (re-run) |

Files: `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\sprints\SPRINT_S8_REPORT.md`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S8\` (`predictions.md`, `additivity.md`, `d004.md`, `draw_noise.md`, `dose_response.md`, `ladder.md`, `s7_reference.md`), `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\src\utils\build_results_s8.py`, `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\DECISIONS.md` (D-054). Two scratch files were copied into `bc3cat-s3`'s `/tmp` (`/tmp/audit_regen.py`, `/tmp/audit_clean.py`, plus `/tmp/audit_s8/`). Nothing tracked was modified; `git status` is clean.
