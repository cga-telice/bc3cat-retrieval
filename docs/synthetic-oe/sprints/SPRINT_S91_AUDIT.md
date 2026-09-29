# Sprint S91 — audit (re-audit after FAIL)

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-09-29 · report `07dd458` (HEAD, tree clean) · runs `runs/OE/resumen/`, `runs/OE/resumen_stripped/`, `runs/OE/resumen_decoded/`

Every retrieval figure I sampled reproduces from `runs/`. No comparison mixes samples, and the design was not edited after freeze. The sprint still cannot be marked `done`: exit criterion 7 is not met, and two major findings need fixing.

## Verified
- **Stamps.** All 30 `run_meta.json` match the Sources table in `renderings.md`: config SHA, commit, `code_dirty: false`, split `dev`, query-set SHA, 35,422 queries. The 20 new runs are at `cf92bc8`.
- **One sample.** All 30 runs score the identical 35,422 dev query keys (asserted per arm × condition).
  - I rebuilt P myself from `OE_resumen.json`, `OE_resumen_stripped.json` and `OE_duplicate_texto_groups.json`: 27,574 queries over 26 concepts.
  - A suffix regex and the "stripped ≠ coded" test agree on all 70,242 records.
- **All of T2.** Every coded, stripped and decoded Acc@1 at both levels, for all 10 arms, matches on P. So does every Δ and every up/down flip count in all three contrast families. So does the secondary table (n = 34,646 item, 35,422 parent).
- **Headline, finding 3.** `bm25_unigram_params` item 0.5492 → 0.9221, +10,328 / −47. My clustered bootstrap (different seed) gives [+0.2245, +0.4128] against the reported [+0.2255, +0.4140]. `bm25_unigram` item +0.5764 matches.
- **Finding 1 / P2.**
  - `bm25_unigram` parent 0.2808 → 0.7572, +13,136 / −0. My CI is [+0.288, +0.550] against the reported [+0.2920, +0.5504].
  - Params arm +0.3692: my raw p ≈ 0.010. Holm, 4th of 10 × 7 = 0.0700, checked by hand.
  - OEB / rest 0.2170 / 0.9587 match.
- **P1, TF-IDF.** +0.0434, my CI [−0.021, +0.095], p ≈ 0.16, against the reported 0.1700. The Holm arithmetic for the params arm (0.0024 × 2 = 0.0048) checks.
- **Finding 4.** `dense_es_hiiamsid` parent 0.6744 → 0.2881, +724 / −11,377. My CI is [−0.516, −0.105].
- **Finding 5.** ColBERT 0.9918 / 0.0284 coded and 0.9962 / 0.4826 decoded match.
- **Finding 2 ceilings.** I recomputed 0.8342 / 0.0147 / 0.8341 on P and 0.8680 / 0.2158 / 0.8680 on the 34,646 scored queries from the rendering texts; all match.
- **T5, independently recomputed** from `results_top100.jsonl.gz` and `OE_long_feats`: 19,832 parent misses, 18,065 with any code token (91.1 %), 16,980 with a rare one (85.6 %). All match.
- **Regeneration.** I regenerated all five tables into the scratchpad with `OUT` redirected. All five are byte-identical to the committed files.
- **Tests.** The full suite gives **1059 passed, 1 xfailed** (234 s), as the report states.
- **`check_run_inputs.py`.** 197 of 202 resolve. The 5 failures are 4 `_archive/S1` runs and 1 OEB run. All 31 runs under `OE/resumen*` resolve.
- **MANIFEST.** All 7 S91 input and derived-table digests are present.
- **Reuse diff.** From `2e49566`, the changed retrievers are not imported by `bm25_unigram`, `bm25_unigram_params`, `bge_m3_colbert` or `dense_e5`. From `922ae53` only `index_builders/bge_m3_dense` changed; from `a5700a6` only `run_context.py` (the `QUERY_SETS` lines).
- **Mechanisms credited in the report do execute.**
  - `MIN_SHARE` runs through `decode_entry → kept`.
  - `fit()` skips non-dev concepts.
  - `verdict()` requires the interval and Holm p < α, as A2(b) says.
  - `RARE_MAX_DOCS` drives the T5 rare column.
- **Freeze.** `git diff 09d11f7..HEAD` on the design shows only the freeze-stamp fill-in and the A1–A3 rows.
- **Split.** All 30 runs are `dev`. The decoder is fitted on dev concepts only. No test run exists.

## Findings

### F1 — major — A frozen design constraint was waived outside the Amendments table
- **What the report says.** The F7 disposition reads "every figure in S91's prose is interpolated by the generator" as covering only the generated tables' prose, "as César chose".
- **Where that is recorded.** Only in the report and `STATE.md`. The design's Amendments table has no row for it, although A1 set the precedent that interpretations are recorded there.
- **The report is still typed.** This conflicts with the root rule "Reports are generated, not typed".
- **The mitigating test is weak.** `tests/test_report_traceability.py` checks set membership only: a figure passes if it appears anywhere in `results/S91/*.md`. It skips bare integers ("6 of 26", "3 and 72").
- **What must change.** Add an A4 row recording the waiver, dated and attributed, before `done`.

### F2 — major — Finding 4 claims a parent-level gain its own rule does not support, and calls it a mechanism
- **What the report says.** "The two BM25 arms gain at parent level, by the mechanism of finding 1: … `bm25_unigram_params` +0.3714 [+0.2169, +0.4127]."
- **What the artefacts say.** That contrast has Holm p **0.0896** (`renderings.md`, decoded − coded, parent), so it fails the A2(b) reading. The report omits the p-value.
- **It contradicts the report itself.** Known-wrong 2 says the finding-1 pattern is "an association, not a tested mechanism".
- **This repeats a fixed defect.** It is the same class as the first audit's F3.
- **What must change.** Quote the Holm p, drop "gain" for the params arm, and replace "by the mechanism" with association wording.

### F3 — major — Exit criterion 7 is not met
- `DECISIONS.md` has no commit since the freeze. The D-039 and D-037 amendments exist only as proposals in the report.
- The report marks this "pending" honestly, but the sprint cannot be marked `done` until César rules and the amendments land.

### F4 — minor — Neural-arm results are stated as findings, though the design says "reported, not claimed"
- **The design.** "Neural arms: no directional prediction. Reported, not claimed."
- **What the report does.** Findings 3 ("restores … for every arm except TF-IDF"), 4 ("costs one arm heavily") and 5 ("collapse … is partly the codes", ColBERT only) are headline claims about unregistered arms.
- **"Restores" overstates the small arms.** It covers `dense_gte` 0.0039 → 0.0130 and `dense_gte_instrQ` 0.0018 → 0.0085.
- **What must change.** Label these as exploratory and not registered.

### F5 — minor — "The coded loss is an OEB phenomenon" is a stratum claim T4 declines to make
- **What T4 says.** "No stratum is contrasted with another."
- **What T4 shows.** Outside OEB, `OEC070$` goes 0.3333 → 1.0000 when stripped, and the rest stratum is 0.9587, not 1.0.
- **What must change.** Reword descriptively ("concentrated in four OEB families").

### F6 — minor — Finding 7 says it does not contrast the populations, then contrasts them
- **What the report says.** "Stated side by side, not contrasted", followed by "the decoded all-dev interval excludes it" and "OE stays less verbatim than OEB". The D-037 row says the same.
- **Why that is a contrast across samples.** 94.10 % carries no interval. It is measured on all 47,514 OEB pairs, 22,305 of them on test-side concepts (`results/S3/overlap/overlap.md` l.20).
- **The populations are named, so the mixing is not silent.** But an interval-exclusion statement between different samples is an inferential contrast.
- **What must change.** Keep the wording descriptive, or drop the exclusion statement.

### F7 — minor — The decoder's viability is in-sample
- **What the report says.** "80.9 % exact" and "viable and could be deployed" (finding 6; next sprint inherits).
- **Why it is in-sample.** The 80.9 % is measured on the same dev leaves the table was fitted on.
- **What is left unsaid.** Codes unseen on dev decode to nothing (`render()`), and no held-out coverage is stated. The design allows fitting on dev, but the viability claim needs that qualifier.

### F8 — minor — The report header's regeneration account is stale
- **What the header says.** Tables were "generated at `3dc992f`, regenerated for audit F2 … and F4 …; no figure moved".
- **What the history shows.** The tables were also regenerated at `63230f3` (F5, which added the rare column) and `3336131` (F8, which added the ceiling rows). Both added figures.
- **What must change.** Name the last generating commit, `3336131`.

## Unverifiable
- **"A2(b) was committed before any S91 accuracy was read."** Runs completed (2026-09-28 22:27 UTC for the params decoded run) before `50d2c08`. Whether anyone read them cannot be established; carried over from the first audit.
- **The 17 s untracked-file incident.** No artefact records the window. The overlapping run is stamped `code_dirty: false`, and that is all that can be checked.
- **The oracle arms' ceiling of 1.0.** It is asserted by the generator, not computed.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1 renderings + decoder digests in MANIFEST | yes | 7 digests found in `docs/synthetic-oe/MANIFEST.md` |
| 2 renderings test + full suite pass | yes | 1059 passed, 1 xfailed (re-run by me) |
| 3 20 runs clean, dev, resolving; reuse justified | yes | 20 × `cf92bc8`, clean, dev; all resolve; import-path diff checked |
| 4a T1–T5 generated, regenerate identically | yes | byte-identical regeneration |
| 4b every item figure carries n | yes | T2, T4 and the secondary table |
| 4c every accuracy carries its ceiling | yes | T2, secondary and T4 at both levels (parent 1.0) |
| 5 P1/P2 read on clustered CI after Holm | yes | `renderings.md` "The registered predictions"; Holm arithmetic checked |
| 6 decoder viability stated | yes | `decoder.md`, finding 6 (in-sample; F7) |
| 7 D-039 amended; D-037 if needed | no | `DECISIONS.md` untouched since `09d11f7` (F3) |

---

*The first audit of this sprint (FAIL, report `8845490`) follows unchanged.*

# Sprint S91 — audit

**Verdict:** FAIL
**Audited:** 2026-09-29 · report `8845490` · runs `runs/OE/resumen/`, `runs/OE/resumen_stripped/`, `runs/OE/resumen_decoded/`

The retrieval numbers are sound. Every accuracy, delta, flip count and interval I sampled reproduces from `results_perquery.parquet`. The design freeze is clean. The FAIL comes from one thing: a coverage comparison between two different samples, which then feeds a proposed amendment to D-037. That is the defect class the brief makes an automatic FAIL. Fixing it is a rewrite of prose and of the proposed decision text, with no re-run needed.

## Verified
- Stamps: all 30 `run_meta.json` match the Sources table in `renderings.md` (config SHA, commit, `code_dirty: false`, split `dev`, query-set SHA). The 20 new runs are at `cf92bc8`.
- P = 27,574 queries over 26 concepts (28,150 carry a suffix, minus the 776 texto-duplicate leaves). Recomputed independently from `OE_resumen.json`, `OE_resumen_stripped.json` and `OE_duplicate_texto_groups.json`.
- **Headline (finding 3):** `bm25_unigram_params` item on P, coded → decoded, 0.5492 → 0.9221 (+10,328 / −47). Traced to `OE/resumen{,_decoded}/bm25_unigram_params__k1-0.60__b-0.35__OE`; matches. My own clustered bootstrap (different seed) gives [+0.229, +0.415], against the reported [+0.2255, +0.4140].
- **Finding 1:** `bm25_unigram` parent 0.2808 → 0.7572, +13,136 / −0; my clustered CI [+0.285, +0.549] against the reported [+0.2920, +0.5504]. OEB 0.2170 / rest 0.9587 also match.
- **Finding 4:** `dense_es_hiiamsid` parent 0.6744 → 0.2881, +724 / −11,377; my CI [−0.520, −0.102] against the reported [−0.5151, −0.1029].
- **Finding 5:** ColBERT 0.9918 / 0.0284 coded and 0.9962 / 0.4826 decoded; match.
- **P2, params arm:** stripped − coded parent +0.3692. 0.5 % of my clustered draws are ≤ 0, which is consistent with the reported raw p 0.0100. Holm across the parent family gives 4th rank × 7 = 0.0700; consistent.
- **Reference:** decoded params item on all scored dev = 0.9361, n = 34,646; matches.
- **T5:** 18,065 of 19,832 (91.1 %) reproduced.
- **Regeneration:** all five tables regenerated into the scratchpad with `OUT` redirected. Content is identical to the committed files; the only difference is CRLF from running on the Windows host. No tracked file was touched.
- **Tests:** `tests/test_resumen_renderings.py` and `tests/test_generated_prose.py` give 37 passed.
- **Freeze:** `git diff 09d11f7..HEAD` on the design shows only the freeze stamp and the A1–A3 rows. No in-place edit.
- **Scope:** since the freeze, the only changes under `src/` are new generators, `build_manifest.py` and `run_context.py`. No retriever, builder or index changed.
- **Reuse diff:** since `2e49566` the diff touches the tfidf, sparse, dense, hiiamsid and gte retrievers and `index_builders/bge_m3_dense`. None of those is imported by the four arms reused from that commit: `bm25_unigram`, `bm25_unigram_params` (which imports only `bm25_unigram`), `bge_m3_colbert` and `dense_e5`. Since `922ae53`, only `index_builders/bge_m3_dense` changed, and no retriever imports `index_builders`. Since `a5700a6`, only `run_context`. The claim holds.
- **Table pairing:** `_norm` equals `_feats` on every shared column, for both coded and decoded.
- **Digests:** all seven input digests are present in `MANIFEST.md`.
- **Split:** the decoder is fitted on dev concepts only (`build_resumen_renderings.fit`). Every run has `queries_after_split` 35,422 on dev. A1's `MIN_SHARE` runs on the reported path: `decoder.md` lists the dropped values.
- **`check_run_inputs.py`:** 197 of 202 resolve. The 5 that fail are four `_archive/S1` runs and one OEB run; none is from S91.

## Findings

### F1 — critical — The coverage comparison mixes samples, and a D-037 amendment is built on it
- **What the report says.** Finding 7 says the two figures are "stated side by side, not contrasted". But known-wrong #1 and the proposed D-037 amendment do contrast them: "decoded OE reaches OEB's coverage", "the gap S3 measured is substantially the rendering".
- **The two samples differ.** 94.41 % is measured on P (27,574 OE dev leaves that carry a suffix). 94.10 % is measured on all 47,514 OEB pairs, including test-side concepts (`results/S3/overlap/overlap.md`). S3's gap was 79.38 % against 94.10 %, on all 35,422 dev queries.
- **On S3's own population the claim does not hold.** Decoded all-dev coverage is **89.83 % [83.43, 92.99]** (`coverage.md`), and that interval excludes 94.10 %.
- **What must change:**
  - Restate the comparison on all dev: decoding closes about 10.5 of 14.7 pp.
  - Or withdraw "reaches".
  - Rewrite the D-037 proposal to match.

### F2 — major — The T4 accuracies carry no provenance stamps
- **What the tables show.** The Sources tables in `subchapter.md`, `coverage.md` and `decoder.md` are empty. T4 is computed from 30 runs, and the report quotes it (finding 1: 0.2170 / 0.9587; P2: 85.9 %). The values reproduce, but under operating rule 1 they are unstamped.
- **What must change.** Have `write_subchapter` pass its run keys to `sources()`. Have T3 print the query-set digests of the three renderings.

### F3 — major — Finding 1's heading contradicts the registered readings
- **What the report says.** "The codes actively mislead the lexical arms" (plural).
- **What the artefacts say.** P2 is supported only for `bm25_unigram`. It is not supported for `bm25_unigram_params` (Holm p 0.0700). TF-IDF parent stripped − coded has Holm p 0.1824, and T5 shows TF-IDF at 1.2 %.
- **What must change.** Name `bm25_unigram` in the heading. Known-wrong #2's causal "because rare code tokens pull it" should also be worded as association (see F5).

### F4 — minor — The rule printed in T2 is not the rule the code applies
- **What the table says.** `renderings.md` §"The registered predictions" defines **supported** as "interval excludes 0", yet labels P2 for the params arm, whose interval is [+0.2177, +0.4091], **not supported**.
- **What the code does.** `build_results_s91.py:334` also requires `holm < ALPHA`, as A2(b) says.
- **What must change.** Fix the generated sentence.

### F5 — minor — T5 counts common code tokens, but the prose credits rare ones
- **What the report says.** The 91.1 % is attributed to "near-absent" tokens, and it cites `nni` and `ne`.
- **What the code does.** `write_rare_codes` counts any code token, including `5` and `3` (each in about 53 % of documents) and `de` (in every document). `nni` and `ne` occur in 0 documents, so they can never be in a rank-1 document.
- **The mechanism still holds.** Restricting the count to tokens in fewer than 1,200 documents gives 16,980 of 19,832 = **85.6 %**.
- **What must change.** Generate the rare-only share, or reword.

### F6 — minor — The P2 row makes a claim that no artefact contains
- **What the report says.** "Resamples without them return a zero delta."
- **What the artefacts say.** No artefact contains this. The per-concept table leaves OEB100 (+0.25), OEB160 (+0.33) and OEB200 (−0.03) nonzero, so the claim is not literally true.
- **What must change.** Remove it, or generate it.

### F7 — minor — The report is hand-typed prose
- **What the rule says.** The design says "Every figure in S91's prose is interpolated by the generator". The root contract says "Reports are generated, not typed".
- **What the report is.** `SPRINT_S91_REPORT.md` is typed by hand. Every number I sampled matches a generated table; F6 is what typed prose lets through.

### F8 — minor — Exit criterion 4's ceiling clause is not met for two tables
- **What the table shows.** T4 (`subchapter.md`) and the "Secondary: every scored dev query" table print accuracies with no per-condition ceiling.
- **Why A2(c) does not cover this.** A2(c) relaxes how often T2 prints the ceiling. It does not cover T4 or the secondary table.

## Unverifiable
- **A2(b) "committed … before any S91 accuracy was read".** The `metrics_dual.json` files for all 20 runs were written by 2026-09-29 04:43. `50d2c08` is 08:19. Accuracies therefore existed before the rule was committed; whether they were read cannot be established. Clustered Holm p-values did not exist before the generator, and the rule is the more conservative reading, so the effect on claims is nil.
- **"Full suite 1057 passed, 1 xfailed at `58a2c6c`".** I did not re-run the full suite; I ran only the two S91 test files.
- **The 17 s untracked-file incident.** No artefact records the window. The overlapping run is stamped `code_dirty: false`, which is all that can be checked.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1 renderings + decoder digests in MANIFEST | yes | `sha256sum` of all 3 inputs and 4 tables found in `MANIFEST.md` |
| 2a `test_resumen_renderings.py` passes | yes | 37 passed, together with the prose guard |
| 2b full suite passes | unverifiable | not re-run |
| 3 20 runs clean, dev, resolving; reuse justified | yes | 20 × `cf92bc8`, `code_dirty: false`; 197/202 with no S91 run failing; import-path diff verified |
| 4a T1–T5 generated, regenerate identically | yes | regenerated content identical (only CRLF differs, from the host) |
| 4b every item figure carries n | yes | T2, T4 and secondary tables carry n |
| 4c every accuracy carries its per-condition ceiling | no | T4 and the secondary table have none (F8) |
| 5 P1/P2 read per rule | yes | `renderings.md`, per A2(b) as coded; printed rule wrong (F4) |
| 6 decoder viability stated | yes | `decoder.md`: 22,774 / 28,150 exact; 59 absent-axis writes |
| 7 D-039 answered by amendment; D-037 if needed | no | `DECISIONS.md` unchanged since freeze; the D-037 proposal rests on F1 |
