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
