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
