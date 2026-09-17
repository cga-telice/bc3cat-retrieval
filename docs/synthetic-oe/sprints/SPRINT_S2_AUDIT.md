# Sprint S2 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-09-17 · report `7a9bd89` · runs `runs/OE/{texto,single_texto,stacked_texto}/{5 methods}`, `runs/_archive/S1/OE/*/bm25_unigram_params__k1-0.60__b-0.35__OE`

## Verified
- **Tables regenerate exactly.** I re-ran `src/utils/build_results_s2.py` with its output folder pointed at a temp directory. All 7 tables in `docs/synthetic-oe/results/S2/` came out byte-identical. The tree is still clean.
- **Acc@1 recomputed from raw top-100 lists** for all 15 runs. Each matches `results_perquery.parquet` and the report: identity 0.9994 / 0.8870 / 0.9861 / 0.7708 / 0.8014; stacked 0.1789 / 0.1071 / 0.4038 / 0.1142 / 0.1269.
- **L1 deltas, BM25-params** (headline): −0.3824 [−0.4510, −0.3186] and −0.9016 [−0.9333, −0.8667]. Traced to `OE/single_texto` and `OE/texto` `bm25_unigram_params`, config `c695c126`, commit `31bf1a1`, query sets `e5b79ae4` / `643f1a72`. Values match.
- **Structured − BM25, 8 contrasts:** none has a CI entirely above 0, at query or concept level. Deltas −0.373, −0.127, +0.016, +0.003 match `structured_vs_bm25.md`.
- **One sample, one claim:**
  - Within each query set, all 5 runs share identical query ids (the generator checks this).
  - Every run is on the `dev` split, and every gold concept is in the dev list.
  - Test-split concepts in any run: 0.
  - ColBERT's identity queries come from a different table (`OE_long_norm`, `75477221`), but `text_norm` equals `OE_long_feats.text_norm` on all 70,242 rows.
- **Paired L1 deltas:** each is joined on the gold leaf, and 0 queries went unmatched in any of the 10 cells.
- **Structured variants:** they differ on exactly 70 `single_texto` queries, and on 0 of the L1-slice queries.
- **`bm25_unigram` identity misses:** 4,003 misses, of which 3,922 keep the right concept. Of those, 662 have the gold leaf tied with rank 1 on score, and 662 + 3,260 = 3,922. I checked this by score tie, not by comparing token multisets.
- **Failure sample:** misses are 80 and 284; 60/60 sampled ids are misses in the run; co-present flags are 4 thousands-dot and 10 token-doubling.
- **Credited mechanisms actually run:**
  - `stage3_value_match` goes from the config through `structured_pipeline.py:289` into `CatalogLookup`. The effect shows in the data: gold-in-match is 0.9614 (literal) vs 0.9975 (normalised).
  - Stage 3 returns `sorted(results)` (`catalog_lookup.py:119`), so the "lexicographic order" claim holds.
- **Design freeze:** `git diff 1f126f0..HEAD` on the design only fills in the freeze stamp and adds amendments A1–A5, all dated.
- **Run stamps:** all 15 runs are at `31bf1a1` with `code_dirty: false`. `6336974..31bf1a1` changes only `SPRINT_S1_REPORT.md`.
- **S1 archive:** the three `metrics_dual.json` sha256 values match the S1 report's archive note.
- **Tests:** `pytest` gives 334 passed, 1 xfailed, as claimed.
- **No tuning:** k1 = 0.60 and b = 0.35 are unchanged, and no split other than dev appears in any config or run.

## Findings

### F1 — major — The G1 identity reading departs from the frozen rule; exit criterion 6 is not a single outcome
- **Report:** "G1 reading: proceed, subject to the ruling on `bm25_unigram` identity". It argues the design "names 'BM25' without saying which arm".
- **Design as frozen:** the D-010 constraint says `bm25_unigram` "is the deployable arm G1 is also read on". The stop branch applies "if BM25 or ColBERT identity is below 0.98". `bm25_unigram` scores 0.8870, CI [0.8837, 0.8903], entirely below 0.98.
- So the frozen text points to *stop*, or at least *ambiguous on that arm*, for that arm. It does not point to *proceed*.
- D-027 proposes a new stop rule after the result was seen ("stops only when the same code path reads another method at ≥ 0.98"). It is disclosed, so this is not an undeclared change. But it is a post-hoc redefinition of a gate, and it is not in `DECISIONS.md` (STATE.md confirms this).
- **Must change:** record G1 as *ambiguous* on the `bm25_unigram` arm now, under the frozen rule. Do not adopt D-027's rule without a dated design amendment and César's ruling.

### F2 — major — A CI straddles the identity threshold and the report does not say so
- The design requires: "If a CI straddles a threshold, the memo says so and G1 is recorded as ambiguous on that arm".
- ColBERT's identity concept-clustered CI is [0.9463, 1.0000] (`identity.md`), which straddles 0.98. The report quotes only the query-level CI [0.9849, 0.9873] and says ColBERT "clear[s] it".
- **Must change:** disclose the straddle, and either record ColBERT as ambiguous or add a dated amendment stating which CI governs thresholds.

### F3 — major — The "ColBERT inverts" claim has no support; recomputed, one of its four contrasts includes 0
- **Report:** "Open questions" calls ColBERT vs BM25 "the contrast that did invert", and D-029 names ColBERT as the L1 reference for S3. Gate G1 does say no CI was computed.
- **What I found:** I recomputed paired bootstraps from the per-query files (read-only, 10,000 resamples):

| Contrast (ColBERT −) | Slice | Δ | Query-level CI | Concept-clustered CI |
|---|---|---:|---|---|
| `bm25_unigram_params` | `unit_conversion` | +0.083 | [−0.010, +0.177] | [−0.150, +0.333] |
| `bm25_unigram` | `unit_conversion` | +0.328 | [+0.235, +0.422] | — |
| `bm25_unigram_params` | `num_to_text` | +0.667 | [+0.606, +0.727] | — |
| `bm25_unigram` | `num_to_text` | +0.654 | [+0.594, +0.711] | — |

- The first contrast, against tuned BM25 on `unit_conversion`, is not an inversion under either CI.
- **Must change:**
  - Drop "did invert" as a general statement.
  - Add the ColBERT − BM25 contrasts to the generator.
  - Base D-029 only on the contrasts whose CIs exclude 0.

### F4 — minor — Finding 4 does not say which structured variant it describes
- **Report:** "Gold is in the match on 94.1 % / 99.4 %". Those are the `structured_rules` values; `structured_valuenorm` gives 98.5 % / 100 %.
- A1 says "the memo must say which one any structured claim rests on."
- **Must change:** name the variant, or give both.

### F5 — minor — Clustered CIs that include 0 are not mentioned
- **Report:** "BM25 also loses the concept under `unit_conversion` (parent 0.8725 params, 0.8137 unigram)" is given with no interval. Its clustered CIs are [−0.2959, +0.0000] and [−0.4457, +0.0000].
- The Finding 2 table gives `structured rules` −0.314 [−0.402, −0.226] with only the query-level CI. Its clustered CI is [−0.7217, +0.0800].
- With 13 concepts per slice, the design names the clustered bootstrap as the sensitivity check.
- **Must change:** print the clustered CI wherever it changes the reading.

### F6 — minor — The tie-break criticism is applied to the structured pipeline only
- D-028 and "known wrong" #2 blame structured Acc@1 on key ordering. BM25 and ColBERT also rank-1 ties, broken by candidate order:
  - `bm25_unigram` identity: 518 correct answers sit on a rank-1 score tie, and 662 misses are gold-tied.
  - Stacked `bm25_unigram_params`: 222 of 451 correct answers are tied.
- On the L1 slices the effect is small. Replacing tie order with a random tie-break moves Acc@1 by at most 0.018 (for example 0.1111 → 0.0932).
- **Must change:** apply the D-028 idea (report tie-free accuracy, or break ties at random) to every family, not only structured.

### F7 — minor — Provenance statements in the report do not match the artefacts
- **Header:** "all 15 runs and all 7 OE indexes, `code_dirty: false`" at `31bf1a1`.
  - Only 6 index directories exist, and "Inherits" lists 6.
  - 5 of the 6 index stamps show `6336974`; only ColBERT shows `31bf1a1`.
- **A5** says "All five S2 BM25 indexes"; there are two.
- **ColBERT index stamp** records query set `643f1a72` (feats), while its config and runs read `OE_long_norm` (`75477221`).
- None of this changes a number: the code differs only in docs, and the text is identical. But a sprint whose rule is provenance should not carry wrong stamp statements.

### F8 — minor — Some numbers appear only in prose, with no generator
- "662 rank a sibling with an identical token multiset" and "3,260 of the rest": no script or table produces these. I checked them indirectly (F-free, see Verified).
- "one miss was re-scored by hand": no record of it.
- CLAUDE.md: "Reports are generated, not typed."
- **Must change:** add the miss breakdown to `identity.md`.

### F9 — minor — The pantry-artefact caveat is recorded but not carried
- 10 of 30 sampled `num_to_text` misses have D-004 token doubling. They are classified "genuine" on a hand-written note ("on a non-discriminating token").
- D-004 requires a sensitivity analysis excluding affected items "before any per-type claim". Yet the H3 row reads "Supported" on the `num_to_text` Δ −0.90 without that caveat next to it. The exclusion analysis is deferred to S6 in the design, but the report must still say the claim is conditional on it.

## Unverifiable
- **Failure classification (60/60 genuine rendering effects):** these are hand judgments, and I did not re-classify rows.
- **The previous study's "0.903 structured figure" and its "1,080 OEB leaves" with the comma defect:** no S2 artefact holds them. In `paper_28.tex`, 0.903 appears only as fusion figures (an Acc@1 and an MRR@10).
- **A1's "fix chosen before any structured run exists":** the amendment commit (01:21 +0200) is earlier than the kept structured runs (07:56 +0200), but git cannot show whether earlier, overwritten structured runs existed.
- **A4's "blocked retrieval equals one-block retrieval":** relies on the tests passing. I did not re-run the unblocked path.
- **ColBERT index build start at `6336974`:** only the finish stamp is on disk.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1. 15 runs (A1), one clean commit | Yes | 15 `run_meta.json`, all `31bf1a1`, `code_dirty: false` |
| 2. Identity Acc@1 + CI, generated | Yes | `identity.md`, regenerated identical |
| 3. Paired L1 deltas + CI per method | Yes | `l1_deltas.md`, 0 unmatched |
| 4. Structured − BM25 paired deltas, both variants | Yes | `structured_vs_bm25.md`, 8 contrasts |
| 5. Stage table and 60-miss classification | Yes | `structured_stages.md` (100 % of queries reproduce the run's rank 1); `SPRINT_S2_FAILURES.csv`, 60 rows, cross-checked against the run |
| 6. G1 read as one of proceed / reframe / stop / ambiguous | No | Reading is "proceed, subject to ruling", which contradicts the frozen stop branch for `bm25_unigram` (F1) and skips the ColBERT clustered-CI straddle (F2) |
| 7. `pytest` green incl. ported-extractor test (A2) | Yes | Re-run: 334 passed, 1 xfailed; `test_extractor_on_20_dev_texto_leaves_abstains_but_never_misreads` present |

Files referenced:
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\sprints\SPRINT_S2_REPORT.md`
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\sprints\SPRINT_S2_DESIGN.md`
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S2\identity.md`
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S2\l1_deltas.md`
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\src\utils\build_results_s2.py`
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\src\pipeline\catalog_lookup.py`
- `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\index\OE\*\meta.json`
