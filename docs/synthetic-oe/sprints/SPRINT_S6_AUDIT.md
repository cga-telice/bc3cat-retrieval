# Sprint S6 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-01 · report `450d13d` (HEAD `7875e3f`, tree clean before and after) · runs `runs/OE/single_l2_texto/*` (15 new), `runs/OE/{texto,single_texto}/*` (30 reference), `docs/synthetic-oe/results/S6/`

## Verified
- **The whole of `results/S6/` reproduces.** I regenerated it at HEAD in `bc3cat-s3`, writing to a temp dir; no tracked file was touched. All 9 tables and 3 PNGs are byte-identical to the committed files. Every number traced below therefore reproduces from `runs/`.
- **All 45 run stamps in T8 match the `run_meta.json` files on disk:**
  - Every config SHA-256 was re-hashed from its YAML and matches.
  - All 45 runs are `split: dev` and `code_dirty: false`. The 15 L2w runs are at `a1bbc81`, created 13:54–14:03Z on 09-30, after the freeze (11:29Z). The L2w tests are blind in time.
  - The query-set digests were re-hashed from `data/processed`: `9612ad99` (L2w feats), `e5b79ae4`, `643f1a72`, `75477221`, plus the JSON and sidecar inputs `fff7dd3b`, `b6a43961`, `02a2c270`, `f492d9a0`, `e1e5adbb`, `b3cfcad4`. All match.
- **R3 PM (headline H5 figure)** `bm25_unigram` 0.4410 [0.2300, 0.6316] and oracle 0.5789 [0.4086, 0.7695] — traced to `predictions.md` and `mediation.md` (OLS, run `OE/single_texto/bm25_unigram__k1-0.60__b-0.35__OE` @ `31bf1a1`, `e5b79ae4`). Values match.
- **R4** +0.2560 [+0.1258, +0.4922] and +0.3730: these equal PM(bm25) − PM(arm) = 0.4410 − 0.1850 and 0.4410 − 0.0680 (T3). They match.
- **R1** −0.5013 and −0.5912, **R2** +0.4930 and +0.0195, **R5** 5.6751 [2.8809, 11.6002] and 8.0244, **R6a/R6b** (all 11 values) — match T7.
- **T7 tally** — 16 supported, 5 not supported, 0 contradicted. "Differs" is "no" on all 21 rows.
- **Finding 3** — BM25 L2w parent δ −0.1042 and item δ −0.1081. ColBERT −0.0029 and −0.1485. All tie-free, T1, same 518 queries. They match.
- **Known-wrong #5** — identity 0.7114 against 0.9421 (T1, tie-free) matches.
- **Findings 5 and 7** — −0.6576 → −0.6079, −0.8589 → −0.4071, −0.5237 → −0.1785 [−0.3265, +0.1598], +0.0292 [−0.1172, +0.3056], ColBERT −0.2987 [−0.4256, −0.2032]. All in `mediation.md` (OLS columns). They match.
- **Finding 8** — +0.2015, û −0.2011, compression +0.2125, paraphrase +0.0005 (`adjusted.md`). They match.
- **42 fits, 37 keep the leaf component** — the per-fit status lines in `adjusted.md` and `mediation.md` give the 5 exceptions exactly as the report names them.
- **D-004** — 185 doubled L1 queries, 0 detector/sidecar disagreements, and clean Holm p 0.0756 (R2) and 0.0936 (R6b) all match T5. P8: PM 0.4381 matches. Power: MDE 0.1572 matches.
- **One sample per comparison.** Within-L2w statements use the same 518 queries at both levels. R6a/R6b compute parent and item quantities on the same 2,176 item-scored pool. R1, R2 and R5 are between-population by design, bootstrapped under independent labels, and declared as such.
- **Design freeze** — `git diff 8abf24f..HEAD` on the design changes only the freeze-SHA placeholder (`92df1bb`). A1–A6 are dated in the amendments file. A2 (`d36f78d`, 16:30) predates the generator's first commit (`8c1ce32`, 16:45). The T7 estimate, concept CI, Holm p and reading columns are identical between the first generation (`144f3be`) and the final one, so A3–A6 moved no registered reading.
- **The credited mechanisms actually execute:**
  - The tie-free columns (`columns()`), the clean subset (text detector) and the PM-undefined and R5 forced paths all run.
  - The R4 pairing holds: `pm_fit` uses one bootstrap label per variant for both arms.
  - Holm runs across all 21 tests.
  - The M1 deficits and indicator follow A2(b) and S3's `build_overlap`.
- **Split** — no run has `split: test`. The L2 feature table spans both splits, but only dev keys are paired or read.
- **Suite and inputs.** The suite at HEAD gives 1192 passed, 2 skipped, 1 xfailed; the 2 skips are A1's container-only checks. `check_run_inputs.py` resolves 235 of 241 runs; the 6 failures are all `_archive/S1`, `_archive/S4` or `OEB` dirty-tree stamps.

## Findings

### F1 — major — Exit criterion 3 is reported as met but is not (a repeat of S4 audit F2)
- **What the report says.** Criterion 3 is met, with "n scored / excluded per item cell" and "query-level and clustered interval … on every δ".
- **What the artefacts show:**
  - Only T1 has an `n excluded` column. T2 (`n`), T3 (`n`), T4 and T6 (`n scored`) and T7 (no n at all) print item-level `single_texto` figures without their per-cell exclusions. Those exclusions are non-zero: for example, `synonym_label` has 286 scored of 291 (T2 against T5).
  - T1's tie-free δ columns, which are the ones the report reads, carry only `CI (concept), tie-free`. The query-level CI exists only for the as-run δ.
  - ColBERT's tie-free L2w parent δ −0.0029 (finding 3, known-wrong #4) has no query-level interval in any table.
- **What must change.** Add the columns, or record an amendment and mark criterion 3 not met.

### F2 — major — "The encoders'" generalises R4 beyond the two arms it tested
- **What the report says.** Finding 4 says overlap "explains more of BM25's damage than of the encoders'". D-049's manuscript wording says "than of the dense encoders'".
- **What the artefacts show.** R4 tested only `bge_m3_colbert` and `bge_m3_dense`. In T3, `dense_e5`'s OLS PM is +0.4944, above `bm25_unigram`'s +0.4410; `dense_es_hiiamsid` is +0.3210.
- **What must change.** Restrict the claim, and the accepted D-049 wording, to ColBERT and BGE-M3-dense. The alternative is to state that `dense_e5` points the other way (its interval is wide, [−0.0435, +0.8507]).

### F3 — minor — "What is now known to be wrong" includes claims that are unresolved, not wrong
- **What the report says.** Item 2 lists "overlap mediates most" and item 3 the order-of-magnitude ratio, under "known to be wrong".
- **What the artefacts show:**
  - Both R3 intervals contain 0.5, and the oracle's point estimate (0.5789) is above it.
  - The R5 interval [2.88, 11.60] contains 10, yet item 3 says the interval "reaches only 11.6002", which reads as if it falls short of 10.
  - The Hypotheses table is correct ("not refuted either"); this section contradicts it.
- **What must change.** Reword items 2 and 3 as "not established".

### F4 — minor — Power caveat narrowed to "per-type"; the pooled BM25 L2w cell also fails it
- **What the report says.** "No L2w per-type claim is made for BM25."
- **What the artefacts show:**
  - T6 marks the pooled L2w row "claim allowed: no" as well: MDE 0.1572 against |δ| 0.1081 for `bm25_unigram`, and 0.0524 against 0.0502 for the oracle.
  - BM25's tie-free L2w item δ has concept CI [−0.2167, +0.0000].
  - Finding 3 and known-wrong #5 ("L2s and L2w δ are not interchangeable") nonetheless read that pooled cell.
- **What must change.** State that the pooled cell is below its MDE wherever it is read.

### F5 — minor — "It replicated, blind, on 9" is stated without its qualifiers
- **What the report says.** Known-wrong #5 and finding 3's heading ("BM25 loses the concept") are unqualified.
- **What the artefacts show.** The BM25 half of the replication (R2) has Holm p 0.0480 and is not robust to D-004 (clean 0.0756). The report says this only in finding 9.
- **What must change.** Carry the qualifier where the claim is made.

### F6 — minor — The row count for A6's thread effect disagrees
- **What the report says.** Known-wrong #7 and the Deviations table say 33 rows moved.
- **What the amendment says.** A6 says "37 of 993 rows moved".
- **What must change.** Reconcile the two, or state which comparison each figure counts.

## Unverifiable
- **"Byte-identical across two generations" as the implementer ran it.** I verified one independent regeneration instead, which matched.
- **Exit criterion 2's "earlier generators regenerate with identical content".** The S3–S5 generators were not re-run here. Their `results/` are unchanged in git since the freeze.
- **The OEB fixture.** It is not isolated; it passes only inside the whole suite.
- **A1's container checks and the `pip freeze` digest** (`logs/`, git-ignored).
- **That A2 was written before any figure was computed.** Commit order supports it; uncommitted work cannot be ruled out.
- **The six-hour concurrent-generation episode and its discarded output.**

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1 Intake, sidecar, MANIFEST, tests | yes | `run_context` registered. `DELIVERIES.md:26` and `MANIFEST.md:24` record `f492d9a0`. Suite passes at HEAD (1192 passed, 2 skipped, 1 xfailed). OEB fixture not isolated |
| 2 15 runs clean, dev, resolving; earlier results unchanged | yes | 15 × `a1bbc81`, `dirty: false`, dev, 518 queries each. `check_run_inputs` 235/241, none of the 6 failures is S6's. No `results/S3–S5` diff since `8abf24f` |
| 3 T1–T8, figures, byte-identical, n scored/excluded, both CIs, tie-free/as-run, stack stamped | **no** | Byte-identical, guarded, tie-free/as-run and stack stamp are met. Per-cell n excluded is missing in T2–T7, and tie-free δ lacks a query-level CI (F1) |
| 4 M0–M2 × 7 arms, non-convergence reported, PM CI or "—" | yes | 42 fits with status printed. `dense_es_hiiamsid` M1 non-converged and marked, its mixed PM "—". OLS PM has a clustered CI for all 7 arms |
| 5 21 tests read, blind/confirmatory, clean subset beside | yes | T7 has 21 rows with blind labels. T5 gives the clean reading for every test |
| 6 H1, H2 per clause, H5 per part; L2 breadth; D-043 ruling 3 | yes | Hypotheses table follows the design's rules. 9/8/9 against 13/12 is stated. Ruling 3 is not reopened (widest not-supported R1/R2 interval is 0.055) |

Paths: `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\sprints\SPRINT_S6_REPORT.md`, `...\sprints\SPRINT_S6_AMENDMENTS.md`, `...\results\S6\` (`predictions.md`, `mediation.md`, `l2_profile.md`, `power.md`, `d004.md`, `adjusted.md`, `sensitivity.md`, `run_provenance.md`), `...\DECISIONS.md` (D-049), `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\src\utils\build_results_s6.py`.
