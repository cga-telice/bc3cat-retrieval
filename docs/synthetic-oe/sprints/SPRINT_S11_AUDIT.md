# Sprint S11 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-04 · report `bd48082` · runs `runs/OE/{texto_u,resumen_u,single_texto,single_l2_texto,stacked_texto,dose_texto,isolated_texto}/structured_pipeline_{llm_keytol_hard,llm_keytol_hard_colbert,llm_keytol_soft_colbert,rules_canon_soft_colbert,colbert_in_concept}__OE` (35), plus the reference runs named in T9

Every number I sampled reproduces, no comparison mixes samples, and the design has not changed since the freeze. Two exit criteria the report marks "yes" are not met (EC3, EC6). One finding draws a conclusion its own table contradicts (finding 2, which S10 inherits).

## Verified
- **Headline A1, stacked: K2 0.7271 vs ColBERT 0.4128, δ +0.3143.** Recomputed independently from `results_top100.jsonl.gz` of `OE/stacked_texto/structured_pipeline_llm_keytol_soft_colbert__OE` (`7f9db9ab`, `1c9e38d`, `f34c1798`) and `OE/stacked_texto/bge_m3_colbert__OE` (`130f0fc4`, `d0621a1`, `f34c1798`). n = 2,466 after D-033. Tie-free and as-run values (0.7263 / 0.4104) both match.
- **F1 0.4073 and K1 0.7263 on stacked.** Recomputed, they match. A5 δ −0.0055 and A3 δ +0.0008 follow from them.
- **A7 pooled on `dose_texto`: K2 0.7850 vs ColBERT 0.5091.** Recomputed (`ef8c6295`), matches.
- **A6 on `texto_u`: K2 0.8483 vs ColBERT 0.9993.** Recomputed. All 2,636 scored `texto_u` keys are present in the `OE/texto` ColBERT run, so the pairing is a true subset.
- **Stamps.** All 35 run directories exist, with `code_dirty: false` and split `dev`. Every config SHA-256 equals the hash of its YAML. Commits are `4fe109d` (K0) and `1c9e38d` (others), and query-set digests match T9 and the report header.
- **One sample, one claim.** ColBERT's `texto`/`resumen` references read `OE_long_norm`/`OE_short_norm` (`75477221`/`28d09f40`), while the other references read the feats tables. I checked the ID sets: identical (70,242 = 70,242, symmetric difference 0). It is the same sample.
- **Design freeze.** The design's only change since `931ee0c` is the "Frozen at" placeholder, filled in `5e13ff9`. Amendments A1–A6 are dated and justified in `SPRINT_S11_AMENDMENTS.md`.
- **Dead code.** All three options are live on the reported runs:
  - `stage3_match: soft`, `family_order: colbert` and `stage2_canon: true` appear in the configs and in `index/OE/*/meta.json`.
  - They are wired in `structured_pipeline.load`.
  - The retrieve logs print "Stage 3 match: soft" and "canonicaliser C before extraction".
  - K1≠K0 and K2≠K1 on some queries (T1, T3).
- **Byte identity.** `results/S11/*` (10 files) hash to `logs/S11/results_hashes.run3.txt` and `run4.txt`.
- **Split discipline.** I rebuilt the extraction cache keys from the gold concept and `text_norm`:
  - Dev hit rates: 1,636/1,640 `dose`, 2,940/2,952 `isolated`, 2,191/2,206 `single`, 2,451/2,521 `stacked`.
  - Test hits: 0 of 1,360 / 2,448 / 2,233 / 2,477.
  - The family caches are built from dev reference runs.
- **D-004.** T7 recomputes all 11 tests on the clean subset, and all are robust.
- **Tests.** `tests/test_report_traceability.py`, `tests/test_generated_prose.py` and `tests/test_s11_harness.py` pass (30 passed). The tree is clean.

## Findings

### F1 — major — EC3 marked met, but no run carries the model digest or prompt SHA
- **Design EC3 requires:** the runs are "stamped with model digest and prompt SHA".
- **What the run files hold:** no `run_meta.json` has either field (e.g. `runs/OE/stacked_texto/structured_pipeline_llm_keytol_soft_colbert__OE/run_meta.json`). The report's own Debt line admits this.
- **What the report claims instead:** that T9 reads both "from the cache and the determinism log". That holds for the model digest only. `logs/S11/determinism_extract.json` has `"prompt_sha256": null`, and T9 prints no prompt SHA anywhere.
- **What must change:** EC3 reads **not met**, unless a prompt SHA is produced and stamped.

### F2 — major — EC6 marked met, but the report's wording is not scoped as the design requires
- **Design EC6 requires:** wording "scoped to dev, to in-sample rules, and to the extractor's prompt exposure", with cost per query "against `bm25_unigram` and ColBERT".
- **What the report does:**
  - It scopes to dev.
  - It never states that the tolerant-key rule and C's rules are in-sample on dev.
  - It never mentions the `phi4` prompt's exposure on OEB `resumen` (grep for "in-sample", "prompt", "exposure" finds nothing).
  - Finding 9 gives no `bm25_unigram` cost (it is only in T6).
- **What must change:** add the two scope statements and the `bm25_unigram` cost to findings 1 and 9, or mark EC6 not met.

### F3 — major — Finding 2 ("The gain is the order, not the tolerance") is contradicted by the report's own T1
What the numbers say on stacked (T1, tie-free):

| Step | Arms | Item Acc@1 | Change |
|---|---|---|---|
| A1 total gain | ColBERT → K2 | 0.4128 → 0.7271 | +0.314 |
| Order (A2, registered) | K0 → K1 | 0.6571 → 0.7263 | +0.069 |
| Reading values plus the filter (descriptive, not registered) | F1 → K1 | 0.4073 → 0.7263 | +0.319 |

- Tolerance (A3) adds +0.0008.
- So most of the A1 gain comes from reading values and filtering, not from the order.
- "Not the tolerance" is supported. "The gain is the order" is not.
- The same claim is repeated in "What is now known to be wrong" #5 and in the S10 inheritance ("the within-family order is what carries the gain").

**What must change:** restate it as "the order adds +0.069 beyond K0; the tolerance adds nothing detectable". Mark any statement about the reading's share as descriptive (K1 − F1 is not a registered contrast), and correct the S10 line.

### F4 — minor — The test tally under EC5 is wrong
- **Report:** "8 supported, 3 not supported, 0 contradicted".
- **T8:** 9 supported (A1×2, A2×2, A4×2, A6, A7×2) and 2 not supported (A3, A5).

### F5 — minor — Two different intervals for the same registered statistic
- **The statistic:** the A7 rung-5 contrast.
- **The two intervals:**
  - T2/T8 (the reading interval): [+0.3941, +0.5202].
  - T5: [+0.3965, +0.5186].
- **Which one the report quotes:** T5's, in finding 1.
- **Cause:** `ladder_cell` in `src/utils/build_results_s11.py` has no draw cache, so T5 (label `T5|dose_texto|5`) and T2 (label `A7|…`) bootstrap the same statistic separately. `delta_cell` caches its draws for exactly this reason (its comment cites S9 audit F1). The fix was not carried to the ladder.
- **What must change:** quote the T8 interval, and reuse the draws across tables.

### F6 — minor — Per-type claims (finding 6) lack intervals and rank types against each other
- **What the report does:**
  - It quotes `template_paraphrase` +0.2403, `unit_conversion` +0.1214 and `unit_expansion` +0.0791 without intervals.
  - `unit_conversion` is [+0.0051, +0.2855] on 12 concepts.
  - The heading says the gain "is in" those types. That is a cross-row reading which T4 itself forbids, and the applicability confound applies to it.
- **What must change:** print each interval and drop the ranking.

### F7 — minor — Two readings use wording stronger than the design's reading categories
- **Finding 3:** the heading "does not change it" asserts a null that A5 did not establish. The query-level interval [−0.0105, −0.0007] excludes 0.
- **Hypotheses table:** A3 is read as "Refuted on dev". That is not a design category (supported / not supported / contradicted). The interval [+0.0000, +0.0036] does bound the effect, so say that instead.

### F8 — minor — The retrieval cost range in finding 9 is selective
- **Report:** "0.0059–0.0093 s per query".
- **T6:** that range covers only `texto_u`, `single_texto` and `stacked_texto`.
  - The arms reach 0.0324 s on `single_l2_texto`.
  - K0 on the E3 bases is 1.10–1.30 s (live generation).
- **What must change:** qualify the range, or give the full one.

### F9 — minor — T5 rows lack the n-excluded and concepts columns that EC4 requires on every item-level figure
- T5 rows carry n scored and leaves.
- The concept count appears only in the header.
- All exclusions there are 0, so nothing is hidden, but the format rule is unmet.

### F10 — minor — The report header omits two reference digests
- **Missing:** the `texto`/`resumen` ColBERT references' query-set digests, `75477221` and `28d09f40`.
- **Where they appear:** in T9 only.
- **Precedent:** S7 audit, same disclosure.

## Unverifiable
- **A2's batch-dependence measurement.** The claim: 20 queries, 535 of 1,710 MaxSim scores moving, up to 0.13 per component and up to 0.3125 in score. No log or artefact in `logs/S11/` holds it. It underpins "What is now known to be wrong" #1 and the proposed D-060.
- **A5's figures.** "Each of the seven bases selects exactly its own file; about 4 s and 1 GB" has no artefact.
- **EC7's full-suite result (1816 passed, 2 skipped, 1 xfailed).** I did not run the full suite. I ran only the three S11-relevant test files.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1a. Label stripping reproduces A7's counts | yes | `tests/test_s11_harness.py` passes |
| 1b. Scorer reproduces ColBERT's stored scores | yes | T9: 0 mismatched on all 7 caches |
| 2. E3 generation and 100-query regeneration | yes | `determinism_extract.json`: 100/100 identical |
| 3a. Runs clean, dev, resolving, stamped (config, commit, query set) | yes | 35 `run_meta.json` checked |
| 3b. Runs stamped with model digest and prompt SHA | no | F1 |
| 3c. K0 reuse diff recorded | yes | T9 A4: 5/5 identical |
| 4a. Tables generated, byte-identical, prose guard, both intervals | yes | hashes match run3/run4; tests pass |
| 4b. Every item-level figure has n scored, n excluded, concepts | no | F9 (T5) |
| 5. 11 tests read tie-free, as run, D-004, seen/blind | yes | T8, T7. The report's tally is wrong (F4) |
| 6a. Method contribution stated by the rule | yes | T8: established on dev |
| 6b. Cost against ColBERT | yes | finding 9 |
| 6c. Cost against `bm25_unigram` | no | F2 |
| 6d. Scoped to dev | yes | findings 1 and 9 |
| 6e. Scoped to in-sample rules and prompt exposure | no | F2 |
| 7. Full suite and OEB fixture | unverifiable | full suite not re-run; the 3 S11 test files pass |
