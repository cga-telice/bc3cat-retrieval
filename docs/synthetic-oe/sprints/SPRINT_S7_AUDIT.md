# Sprint S7 — audit of amendments A8–A9 (v2 re-run)

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-19 · report `858d15c` (section "v2 re-run (A8–A9, 2026-10-18)", lines 180–186, all blamed to `858d15c`) · results `docs/synthetic-oe/results/S7/v2/`, `results/S7/v2/stacked_p/`, `results/S7/stacked_p/` @ `858d15c` (87/87 files equal `logs/v2/tables_gen1.sha256` = `tables_gen2.sha256`; `git status` clean under `results/S7/`) · runs `runs/OE/stacked_texto_v2/<18 S7 arms>/`, identity `runs/OE/texto/<arm>/`, archive `runs/_archive/dirty/2026-10-18/`

## Verified
- Provenance of the 18 v2 runs — every `run_meta.json`: `code_dirty: false`, `code_dirty_paths: []`, `split: dev`, `queries: 2521`, `query_set_sha256 = 977d40b9a4ae6bf0…` = SHA-256 of `data/processed/OE_stacked_texto_v2_feats.parquet` on disk (binary, no line-ending exposure); `config_sha256` identical run-for-run to the v1 run's; commits `4f56a39` (`bm25_unigram`, `bm25_unigram_params`, `tfidf_phrases_replace`) and `8d1ffd2` (the other 15). `git diff 4f56a39 8d1ffd2 -- src configs` touches the retrieval path only by the `retriever_provenance` hook in `retrieve.ipynb` and a `provenance()` method in `structured_pipeline.py`; `8d1ffd2` differs from `022ff2a` by `DATASET_DEFECTS.md` and `STATE.md` only, as the report says.
- v1 untouched — `git log --oneline -3 -- results/S7/headline.md` ends at `7313f12`; identity rows of `results/S7/run_provenance.md` and `results/S7/v2/run_provenance.md` are byte-identical; `runs/OE/texto/*` stamps date from 2026-09-17/30 at `31bf1a1`/`26ed9ff` etc.; the v1 stacked runs still carry `f34c17986d09b6cf` at `b314b92`/`d0621a1`.
- A9's two dirty runs — `runs/_archive/dirty/2026-10-18/OE/stacked_texto_v2/{bge_m3_colbert__OE, bge_m3_dense__OE}`: `code_commit 4f56a39`, `code_dirty: true`, dirty paths = the nine/ten generator files A9 names (plus `src/retrieve.ipynb`, `src/retrievers/structured_pipeline.py`, `src/query_rewrite/determinism.py`), saved 20:17:59 / 20:18:49 UTC; `SHA256SUMS` verifies 46/46. `build_results_s7.py` resolves runs as `RUNS/<queryset>/<dir>` only; `run_dir_as_of` (archive reader) is used by `write_regression`, which the `--v2`/`--population` modes skip. No table reads the archive.
- Data — `OE_stacked_texto.json` vs `_v2.json`: same 4,998 `item_key`s in the same order, the only differing field is `text`, on exactly 2,039 records = the `set == "stacked"` keys of `OE_v2_changes.jsonl`; `texto_modification_*` and `modification_count` are v1's. Dev 2,521 queries / 41 concepts; 1,183 changed, 1,338 unchanged; item level 2,466 (55 D-033 golds) / 39 concepts; changed item-scored 1,179, unchanged 1,287. STACKED-P filter: 324 keys, all in the stacked set, 189 dev queries excluded → 2,332 parent / 2,277 item. Digests on disk: `bc1ed968f60933d9` (v2 JSON), `c34a222ae2af05a0` (v1), `981896771092f6a9`, `bbe36522fdccb4fa`, `b3cfcad47c71c5eb` — all as printed in `comparison.md` and as recorded at intake (`DELIVERIES.md`).
- ColBERT headline — traced to `OE/stacked_texto_v2/bge_m3_colbert__OE` @ `8d1ffd2` vs `OE/stacked_texto/bge_m3_colbert__OE` @ `d0621a1`: recomputed from `results_top100.jsonl.gz` as 0.4128 → 0.4280 (n 2,466), identity 0.9993; paired v2 − v1 +0.0152 [+0.0041, +0.0224] (re-implemented concept bootstrap, seed `SeedSequence([20260917, crc32("cluster|s7|cmp|bge_m3_colbert|item")])`, B = 10,000); 261 queries moved, 253 of 1,179 changed, 8 of 1,287 unchanged; unchanged-subset 0.4980 → 0.4971, changed-subset 0.3199 → 0.3525. All match `comparison.md`.
- W1 ColBERT — recomputed +0.5698 [+0.3846, +0.6473] (v1) and +0.5570 [+0.3759, +0.6341] (v2); paired-draw difference −0.0128 [−0.0202, −0.0029]. Matches.
- BM25 — `bm25_unigram__k1-0.60__b-0.35__OE` @ `4f56a39`: item 0.1061 → 0.1078, +0.0016 [+0.0000, +0.0060], 7 moved (all among changed); parent 0.2931 → 0.2955, +0.0024 [−0.0007, +0.0096]; W1 +0.0810 → +0.0818, +0.0008 [−0.0008, +0.0040]. `bm25_unigram_params` 0.1772 → 0.1776 (3 moved), `tfidf_phrases_replace` 0.1889 → 0.1889 (1 moved), `dense_e5` 0.1894 → 0.1918 (32 moved, 0 unchanged), `rrf` changed-subset 0.2099 → 0.2218, `ce_bge_m3_colbert` changed-subset 0.2859 → 0.3120 and all-queries 0.3460 → 0.3569 (+0.0108 [+0.0019, +0.0181]). All match.
- STACKED-P — recomputed on v2 with `OE_stacked_P_exclusion.json`: ColBERT 0.4398 (n 2,277), parent 0.9849 (n 2,332); `bm25_unigram` 0.1106; δ differences against all queries +0.0119 and +0.0090. Matches `v2/stacked_p/comparison.md`. Readings: 21/21 "reading moved: no" in `stacked_p/comparison.md` (v1) and `v2/stacked_p/comparison.md` (v2).
- One sample, one claim — the v1 and v2 frames hold the same 2,521 dev queries in the same order (asserted in `write_comparison` via `same_queries`, and by me); the identity side is the same `texto` run on the same golds; item exclusions are the same 55 golds. Bootstrap labels in `run_test` are `s7|{kind}|{arm}|{variant}` with no query-set name, `cluster_weights`/`boot_cluster` seed from `[SEED, crc32(label)]` over `np.unique(concepts)` sorted, `clusters_key` is the sorted concept tuple, equal on both sides; `paired_diff` subtracts draw-by-draw only when lengths and `clusters_key` agree. My independent re-implementation reproduces every paired interval to four decimals, which is only possible if the draws are paired as claimed. T1's paired cells are per-query differences bootstrapped by concept under `s7|cmp|…` — a genuinely paired bootstrap.
- Recorded before any run — the A8 row was committed in `4f56a39` at 2026-10-18 19:54:58 UTC and is byte-identical at HEAD (the only later change to the file is the A9 row, `e5dd940`). The earliest v2 run (`bm25_unigram`) was saved 19:55:22 UTC with `elapsed_s 5.487`, i.e. started ≈19:55:17 UTC; the first (dirty, archived) ColBERT started ≈19:56:02 UTC. `logs/v2/run_v2_base.sh` (mtime 21:54 +0200) refuses to start on a dirty `src/`/`configs/`.
- Overclaiming, where the tables support the text — "no registered reading moves": 21/21 W readings unchanged; "largest W difference is W1 ColBERT −0.0128 [−0.0202, −0.0029]": true; "lexical arms read v1 and v2 alike": 7 / 3 / 1 tie-free hits moved out of 1,179 changed queries, 0 of 1,287 unchanged, W differences ≤ 0.0058 with intervals touching 0; D-004 item: 632 flagged (620 item-scored) on v2 vs 720 (708) on v1, 21/21 readings robust on both versions; Finding 1 on v2: highest non-floor item Acc@1 0.4280, headroom < 0.5 for every non-floor arm.
- Line endings (check 6) — `OE_stacked_texto_v2.json` has no CR; `OE_stacked_P_exclusion.json` (2,927 CR) and `OE_v2_changes.jsonl` (3,175 CR) are CRLF on disk, git-ignored (`data/`), delivered that way; the digests printed in the tables (`bbe36522…`, `98189677…`) are of those CRLF bytes and equal the intake record, so nothing in this audit is the H5 phantom. LF-normalised they would read `69f2f6faf8cd5b2d` and `be3fe506b10c9612`; a reproducer on an LF system must hash the files as delivered.
- For information, not citable (A9, S1 A2): the archived dirty ColBERT run's tie-free item hit equals the clean re-run's on all 2,466 item-scored queries (0 differ; 0.4280 both).

## Findings
### F1 — major — The report's stamp sentence names the wrong commits for four of the 18 runs, including the headline arm
What the report says: "at `022ff2a` (ColBERT) and `8d1ffd2` (the rest; `8d1ffd2` adds documentation only to `022ff2a`)". What the artefacts say: `runs/OE/stacked_texto_v2/bge_m3_colbert__OE/run_meta.json` is stamped `8d1ffd2`, and `bm25_unigram`, `bm25_unigram_params` and `tfidf_phrases_replace` are stamped `4f56a39` — exactly as `results/S7/v2/run_provenance.md`, `comparison.md` ("Sources") and the A9 row ("the three runs before them … are clean at `4f56a39` and stay") print. No run is stamped `022ff2a`. Why they differ: typed prose, not generated; the clause about `022ff2a` vs `8d1ffd2` is true but attached to the wrong run. What must change: a dated correction row (A10) restating the commits as `4f56a39` (3) and `8d1ffd2` (15), and the report sentence replaced by a pointer to T9 (rule 1: numbers and stamps come from `runs/`, never typed). No figure is affected.

### F2 — minor — "every other W difference is smaller than a hundredth" is contradicted by W2 ColBERT
What the report says: after W1 ColBERT (−0.0128), "every other W difference is smaller than a hundredth and most intervals contain 0". What the tables say: W2 `bge_m3_colbert` v2 − v1 = −0.0119 [−0.0195, −0.0022] (`comparison.md`, W1–W3); two of 21 intervals exclude 0 strictly (W1 and W2 ColBERT), six more sit on +0.0000. Why they differ: the sentence was written from W1 alone. What must change: "both ColBERT differences are near a hundredth (W1 −0.0128, W2 −0.0119); every other W difference is below 0.006".

### F3 — minor — The STACKED-P sentence labels a δ difference as an Acc@1 difference, and "321 drift queries" is not the filter
What the report says: "ColBERT at 0.4398 and `bm25_unigram` at 0.1106 on v2 (differences against all queries +0.0119 and +0.0090, not paired …)"; "The 321 drift queries do not carry the headline." What the artefacts say: +0.0119 and +0.0090 are the "δ this − ref" column of `v2/stacked_p/comparison.md` (stacked − identity, both sides re-measured on the filtered population). The Acc@1 differences are +0.0118 (ColBERT, coincidentally equal because its identity is ≈1) and **+0.0028** for `bm25_unigram` (0.1106 − 0.1078). The filter holds 324 keys (189 dev queries excluded); `exclusions.py` says 321 carry a drift rewrite, 2 duplicate a delivered query, 1 is degenerate. Why they differ: a column read as the neighbouring one; a sub-count used as the population. What must change: state the δ differences as δ differences, or quote the Acc@1 differences (+0.0118, +0.0028); say "the 324 excluded queries (189 in dev)".

### F4 — minor — RRF is said to "move with" ColBERT on the strength of subset point values whose only interval contains 0
What the report says: "The RRF and CE arms built on it move with it on the repaired queries (`rrf` 0.2099 → 0.2218, `ce_bge_m3_colbert` 0.2859 → 0.3120)", and "`bm25_unigram` goes 0.1061 → 0.1078 (+0.0016, 7 hits)". What the tables say: the subset figures come from the H8-floor table, which carries no interval; the paired all-queries difference for `rrf` is +0.0051 [−0.0002, +0.0099] (contains 0), for `ce_bge_m3_colbert` +0.0108 [+0.0019, +0.0181]. "7 hits" is 7 queries whose tie-free hit moved (net ≈ +4 hit-equivalents), not 7 hits gained. Why they differ: directional prose on a quantity the amendment itself says "carries an interval and no reading". What must change: give the paired intervals beside the two arms, and drop "move with it" for `rrf` or mark its interval as containing 0; "7 queries moved".

### F5 — minor — The A8 row says the paired draws rest on "the same 41 dev concepts"; the W tests pair on 39
What the amendment says: "the same bootstrap labels give the same multinomial cluster weights on the same 41 dev concepts". What the tables say: W1–W3 and the item-level T1 cells are clustered on the 39 concepts that have item-scored queries (`comparison.md`: "concepts 39"); 41 holds only for the parent-level T1 cells. Why they differ: the item exclusion removes two concepts entirely (D-033; both fully duplicated). What must change: a correction row: "39 concepts at item level, 41 at parent level". The pairing itself is correct (clusters_key equal on both sides).

### F6 — minor — The archive A9 describes as holding "the two runs" holds seven run directories at HEAD
What the amendment says: the two dirty A8 runs "were moved … to `runs/_archive/dirty/2026-10-18/OE/stacked_texto_v2/` with a `SHA256SUMS`". What the artefacts say: the directory also holds `stacked_texto_v2/{structured_pipeline_colbert_in_concept, …_llm_keytol_hard_colbert, …_llm_keytol_soft_colbert, …_rules_canon_soft_colbert}` and `single_texto_v2/structured_pipeline_llm_keytol_hard_colbert` — S11 arms stamped dirty at `8d1ffd2` over `src/retrievers/structured_pipeline.py`, saved 23:16–23:17 UTC — and the `SHA256SUMS` (46 lines, all verify) covers them. The archived `bge_m3_dense` holds only `run_meta.json` and `results_top100.jsonl.gz` (batch stopped before metrics). Why they differ: a later archiving (S11's) reused the dated directory and regenerated the checksum file. What must change for S7: nothing in the tables; the record should say the directory is shared and name, in S11's amendments, the five runs and why `structured_pipeline.py` was dirty at `8d1ffd2` while a batch ran — which is the exact event A9's new rule forbids.

## Unverifiable
- "Every parameter as frozen in S4/S5" — the config digests equal v1's run-for-run, but `run_meta.json` stamps no digest of the index under `index_dir`; that the indexes read in October are the builds S4/S5 read cannot be shown from the artefacts. The H8-floor zeros (0 of 1,287 unchanged queries moved for every non-ColBERT arm) corroborate, but do not prove, an unchanged retrieval path.
- The 19-second margin between the A8 commit (host git committer date, 19:54:58 UTC) and the first run's start (container `pd.Timestamp.utcnow()` minus `elapsed_s`) rests on the two clocks agreeing; nothing on disk records either clock against the other.
- What the uncommitted edits contained when the two dirty runs were saved — the stamps list the paths (which include `src/retrieve.ipynb` and `src/retrievers/structured_pipeline.py`, retrieval-path files, besides the generators A9 names), not the diffs; A9's "edits were to analysis generators, not to the retrieval path" cannot be checked, and A9 rightly does not rely on it.
- D-061 is still **Proposed** (owner César); the section's "the manuscript quotes v2" acts on a decision whose acceptance is not recorded in `DECISIONS.md`.
- The dirty-run incident's batch log (which arm was running when which file was edited) — `logs/v2/` holds `.start__*` markers and the script, not a transcript; the sequence in A9 is consistent with the stamps' timestamps but is not independently recorded.
- Outside S7's scope but visible in the checkout: `docs/synthetic-oe/results/S11/v2/run_provenance.md` is modified and uncommitted, and `paper/`, `submission/` are untracked.

---

*The record below is the sprint's earlier audit(s), kept as written.*

# Sprint S7 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-01 · report `d5d743e` (written `7313f12`) · results `docs/synthetic-oe/results/S7/` @ `cab15b4` · runs `runs/OE/stacked_texto/` (18), `runs/OE/texto/` (18 identity), `runs/_archive/S2/`

Every number I sampled reproduces from the runs, and no comparison mixes samples. The design changed after the freeze only to fill in its freeze-SHA placeholder. Two major findings: the sibling-density verdict (D-051) relies on a post-hoc outside-OEB slope while leaving out the within-OEB slope that the design fixed in advance and that points the other way; and exit criterion 4 is marked met when it is not.

## Verified
- Headline (T1, tie-free, 2,466 item-scored / 55 excluded / 39 concepts): ColBERT 0.9993 → 0.4128, δ −0.5865, retention 0.4130. I recomputed it from the `bge_m3_colbert__OE` stacked and texto runs (`130f0fc4`, `d0621a1`/`31bf1a1`, `f34c1798`/`75477221`). Matches.
- `bm25_unigram` 0.9069 → 0.1061, δ −0.8008, retention 0.1113; parent 0.9980 → 0.2931. As-run 0.9063 / 0.1083. Recomputed from `bm25_unigram__k1-0.60__b-0.35__OE` (`ec943fef`, `b314b92`, `f34c1798`). Matches.
- `bm25_unigram_params` 0.9992 → 0.1772, parent 0.3967; `dense_es_hiiamsid` 1.0000 → 0.1135; `dense_e5` 0.5081 → 0.1894, retention 0.3456; `rules_valuenorm` 0.1298; `rrf` tie-free 0.3317 / as run 0.2397, parent 0.7075 / 0.4260. All recomputed and all match.
- W1 point estimates: `bm25_unigram` +0.0810, `bge_m3_colbert` +0.5698. W3 slopes: `bm25_unigram` +0.0990, `bm25_unigram_params` +0.0865, `bge_m3_colbert` +0.0801, `dense_es_hiiamsid` +0.0360, `dense_e5` +0.0342. Outside-OEB slopes: +0.0393 / −0.0597 / −0.0292 / +0.0475. log₂ family size vs dose correlation 0.5984. OEB holds 1,794 queries. I recomputed all of these independently (OLS on the item loss, tie-free). All match T8/T4.
- `results/S7/` (14 files) matches `logs/S7/s7_hashes_run5.txt`, and runs 4 and 5 are hash-identical.
- All 18 stacked runs are `split: dev`, `code_dirty: false`, query set `f34c1798`, 2,521 queries, 0 dropped. Each has the same config SHA as its texto twin, so nothing was retuned. Each derived run's components are S7 stacked runs.
- `check_run_inputs.py --collection OE`: 244 of 244 resolve. `runs/_archive/S2/SHA256SUMS`: 90 of 90 verify.
- `s2_regression.md`: 2,521 of 2,521 rank-1 agreements for all five arms, 0 unexplained.
- T7: 720 flagged in 25 concepts. T5: BM25 δ −0.5606 at dose 2 and −1.0000 at dose 6, over 27/17/8/2/1 concepts. T6: `synonym_label` 2,411 with / 55 without, BM25 δ +0.0000. All match the report.
- Tests at HEAD: S7, traceability, prose and archive tests 44 passed. Full suite 1247 passed, 2 skipped, 1 xfailed (the report's 1246 was at `cab15b4`; one test was added in `d5d743e`).
- Design freeze: `git diff 5e89809..HEAD -- SPRINT_S7_DESIGN.md` changes only the `Frozen at:` placeholder. The amendments file changes only by A1–A4 rows and its own placeholder.
- Paired-delta requirement: met. Every δ uses the arm's own texto result on the same gold (`paired()`), and the identity side is restricted to the stacked golds.
- Carried caveats: the not-a-crossing and no-H4 statements are in finding 7. The pantry sensitivity is computed for all 21 tests.

## Findings

### F1 — major — The density verdict uses the post-hoc outside-OEB slope and leaves out the pre-registered within-OEB slope, which contradicts it
**What the report says.** Finding 5: "outside OEB the slope vanishes… The association is between OEB's large families and the rest… Family size is not separated from subchapter on this set." "What is now known to be wrong" #2 says the law "cannot be separated from OEB". D-051 rests on this.

**What the artefacts say.** The design fixed the within-OEB slope as the subchapter-confound check. T4 (`density.md`) prints it:

| arm | within-OEB slope | CI (concept) |
|---|---:|---|
| `bm25_unigram` | +0.1179 | [+0.0401, +0.1752] |
| `bm25_unigram_params` | +0.0704 | [+0.0192, +0.1143] |
| `bge_m3_colbert` | +0.0496 | [+0.0280, +0.0700] |
| `bge_m3_dense` | +0.0566 | [+0.0368, +0.0863] |
| `dense_es_hiiamsid` | +0.0273 | [+0.0030, +0.0539] |

Inside a single subchapter, larger families lose more for 5 of 7 arms, with intervals that exclude 0. The report never cites these slopes.

The outside-OEB slope comes from A4, which is post hoc. Its intervals are wide, for example [−0.0459, +0.0771] for BM25, and that set has no family above 2,160 leaves. Those intervals show absence of evidence, not a slope that "vanishes".

For the one supported arm, `dense_es_hiiamsid`, the outside-OEB point estimate (+0.0475) is *larger* than the full-population slope (+0.0360).

**What must change.**
- Report the within-OEB slopes next to the outside-OEB ones.
- Drop "vanishes" and drop "the association is between OEB's large families and the rest".
- Restate D-051's rationale. "Not established" still follows from Holm alone, but "not separated from subchapter" is contradicted by the design's own check.

### F2 — major — Exit criterion 4 is marked "yes" but is not met
The criterion says: "Every item-level figure carries n scored and n excluded; every δ … its query-level and clustered CI." The tables do not do this:
- T3 (`tercile.md`, `subchapter.md`) and T5 (`dose.md`) print only `CI (concept)`, with no query-level CI.
- T6 (`presence.md`) has no n excluded and no query-level CI.
- T4's one-axis-sibling bins (`density.md` l.43) print δ with no interval at all and no n excluded.

This is the same defect as S6 audit F1, which was resolved for S6 only. Either regenerate with the missing columns, or mark the criterion not met.

### F3 — minor — The report explains the interval/p disagreement wrongly
The report says: "The interval and p disagree because p counts the draws at or below 0." A4's rationale says the same thing.

The raw p-values of all six non-supported W3 tests (0.0064, 0.0298, 0.0482, 0.0210, 0.0146, 0.0294) are below 0.05. That agrees with their intervals excluding 0 (`boot_p` is two-sided). The only thing separating the interval from the reading is Holm correction across 21 tests: for example 0.0064 → 0.0512. The leverage block is fine as description, but it is not the reason. Correct the sentence.

### F4 — minor — Counts in the prose do not match the tables
- Finding 5 says "intervals containing 0 for four of the remaining five". In T4 all five remaining outside-OEB intervals contain 0.
- "What is now known to be wrong" #2 says "no positive slope for six of seven arms". The outside-OEB point estimates are positive for 2 of 7 (`bm25_unigram`, `dense_es_hiiamsid`), and no interval lies above 0 for any of the 7. Neither reading gives six.
- D-051 says the draws at or below 0 "omit OEB's largest families". T4 shows the 6,336-leaf family inside those draws for `tfidf_phrases_replace` and `dense_e5`. The claim holds only for `bm25_unigram`, which is the only arm the report itself names.

### F5 — minor — A1 and A3 do not match the run stamps
- **A3 commit split.** A3 says the runs are at `b314b92` (8) and `d0621a1` (10). `run_meta.json` shows 7 and 11.
- **A3 re-made count.** A3 says "seven runs were re-made". What happened is 4 re-made (2 RRF, 2 CE), 1 retried (`ce_blend__bm25_unigram`) and 3 first-time BGE-M3 runs.
- **A1 timing.** A1 says it was fixed "before any S7 figure is computed". The seven `b314b92` stacked runs, including `metrics_dual.json` for both BM25 arms, were written 07:34–07:36 UTC. A1 was committed at 07:37:14 UTC.

A1's choices (W3 sign, Holm families, and the others) are not plausibly steered by aggregate Acc@1. The claim is still inaccurate as written. Correct it with a new amendment row.

### F6 — minor — Overclaiming in headline wording
- **"Lexical family".** "What is now known to be wrong" #1: "The lexical family does not show parametric collapse on stacked." `tfidf_phrases_replace` (lexical, oracle) keeps parent level at 0.9638. The claim holds for BM25, which is what D-050 says. Narrow the wording to BM25.
- **No paired comparison between arms.** Finding 1's "best deployable arm" and "level with the oracle RRF" (0.4128 vs 0.4108) are between-arm comparisons with no paired interval. Either soften the wording or add the paired test.

### F7 — minor — The same δ is printed with two different intervals, and the header omits a digest disclosure
- **Two intervals for one δ.** `bm25_unigram`'s stacked δ −0.8008 has concept CI [−0.8685, −0.6311] in T1 and [−0.8695, −0.6276] in T2. ColBERT: [−0.6566, −0.4145] vs [−0.6570, −0.4175]. These are separate bootstrap streams for one quantity. Use one set of draws.
- **Missing disclosure.** The report header lists no texto digest. Unlike S4–S6, it does not disclose that the ColBERT and `bge_m3_dense` identity sides read `OE_long_norm` `75477221` (row-equivalent per the S2 audit), while their stacked side reads the feats table. T9 does show this.

## Unverifiable
- That no stacked figure was *read* before A1 and A2. The timestamps show figures existed on disk (F5). Whether anyone read them cannot be established from artefacts.
- That `results/S2/` and `results/S3/s2_rescored/` were *regenerated* byte-identically after the archive. The files are unchanged in git since the freeze, but there is no regeneration log for them under `logs/S7/`.
- That `/etc/hosts` was restored after the second pass (A3). This is environment state, not recorded in any artefact.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1. Intake checks recorded | yes | `tests/test_intake_s7.py` passes; T1 population shows 55 D-033 golds |
| 2. Archive with checksums; S2/S3 byte-identical | yes (regeneration itself unverifiable) | 90/90 `SHA256SUMS` OK; `results/S2`, `results/S3` unchanged since `5e89809` |
| 3. 18 clean dev runs at `f34c1798`, resolving; regression with no unexplained disagreement | yes | `run_meta.json` ×18; `check_run_inputs.py --collection OE` 244/244; `s2_regression.md` 0 unexplained |
| 4. T1–T9, Figs. 4–5, byte-identical, prose guard, n excluded and query+concept CI on every figure | no | hashes run4 = run5 = tree, prose test passes; but T3–T6 lack the query-level CI, and T4 bins and T6 lack n excluded (F2) |
| 5. 21 tests read, blind/confirmatory, clean and adjusted beside | yes | `predictions.md` |
| 6. Headline, H1 resolution, density verdict, not-a-crossing and no-H4 statements | yes (density verdict's rationale defective, F1) | Report findings 1, 3–5, 7; H1 "partly supported" follows the rule (W2 not supported for both BM25 arms, none contradicted) |
| 7. Full suite and OEB fixture | yes | 1247 passed, 2 skipped, 1 xfailed at `d5d743e` |
