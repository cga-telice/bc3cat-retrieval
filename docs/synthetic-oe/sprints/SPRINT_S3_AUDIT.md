# Sprint S3 — audit (re-audit after the 2026-09-28 FAIL)

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-09-28 · report `eaa184f` · runs `runs/OE/texto` (60), `runs/OE/resumen` (11), `runs/OE/single_texto` (53), `runs/OE/stacked_texto` (53)

## Verified
- **Headline replication figures.** I recomputed every row of `replication.md` from `results_perquery.parquet` with the sidecar `b3cfcad4`, and all match. Examples: `bm25_unigram_params` 0.6394 (run-level 0.6473, n=34,646), `bm25_unigram` 0.0142 and 0.0148 at k1=0.80 (`2a9ffdb`), `dense_es_hiiamsid` 0.0093 / parent 0.5989, `bge_m3_colbert` 0.0437 / 0.9587.
- **Ceiling table.** All ten rows match at both item levels (all queries and scored) and at parent level. This covers `hiiamsid` 1.0000, sparse 0.0501/0.0509/0.8845 and colbert 0.9861/0.9998. Undecidable hits also match: 776/244/676/292/293/65/125/293/104/104. The corpus ceiling is (35,422−484)/35,422 = 0.9863.
- **Sparse diagnosis.** 32,909 misses. 20,717 have the gold at rank 2–100 (median 18) and 12,192 have it past rank 100. Matches.
- **Sweep contrasts.** I ran an independent bootstrap with a different seed. `single_texto`/`bm25_unigram`: Δ +0.0014, CI [−0.0106, +0.0133], p≈0.855, +90/−87. `stacked`/`params`: Δ +0.0049, CI [−0.0069, +0.0166], p≈0.418, +114/−102. Both agree with 0.8507 / 0.4250 within Monte Carlo error.
- **Overlap.** I recomputed `resumen` dev lexical coverage independently: 79.38 % mean, 80.00 % median, n=35,422. Matches.
- **Regeneration.** I ran all three generators into scratch, and all 11 tables came out byte-identical to the committed ones. The tree stayed clean.
- **One sample, one claim.** Within each query set, every run has the same (query key, gold) set, split `dev`, `code_dirty: false`, and scored n: 34,646 / 34,646 / 2,177 / 2,466.
  - There are two digest pairs. `OE_long_norm` vs `OE_long_feats` (and the `short` pair) are the same queries. Stacked `7b0894e6` vs `f34c1798`: I checked all 26 common columns of the two feats parquets and they are identical.
  - No table mixes samples.
- **Design freeze.** `git diff 8353cf7..HEAD` on the design is only the freeze stamp plus amendment rows A1–A11, append-only in every commit.
  - A9 (the operating point kept against the frozen argmax rule for `bm25_unigram`) is declared and dated.
- **Split discipline.** All 177 `runs/OE` runs are `dev`. No test-split run was created during the sprint. The OEB overlap validation reads test-side concepts; this is declared, and no parameter is set from it.
- **Run inputs.** `check_run_inputs.py`: 177 of 177 `runs/OE` resolve, and the five failures are the ones the report names. `run_provenance.md` has 169 rows, 0 dirty.
- **Tests.** `pytest`: 979 passed, 1 xfailed, reproduced.
- **Manifest.** The five delivered digests match `bc3cat-dataset/data/synthetic/handoff_OE/MANIFEST.md`.
- **Carried caveats honoured.** Stacked by-dose uses paired deltas against identity, with concept counts. No interaction claim is drawn from the stacked set. D-004 sensitivity is run per type and per dose. Thin slices carry concept-clustered intervals.
- **Identical embeddings.** The two GTE arms' `embeddings.npy` are byte-identical (A6).

## Findings

### F1 — major — The prose guard covers two of the three generators; `build_results_s3.py` still types numbers
- **What the report says.** The header states that no number in the prose of the 11 tables is typed (`tests/test_generated_prose.py`).
- **What the code says.** `GENERATORS` lists only `build_results_e0.py` and `build_overlap.py`.
- **What the guard finds when applied to the third generator.** `build_results_s3.py` types eight literals, lines 261–273 and 588: `492`, `484`, `34,646`, `0.9861`, `0.98`, `21`, `3,471`, `10`. They are emitted into `s2_rescored/identity.md`.
- **Current values.** They are correct today (I recomputed them), but this is the defect class of the previous critical finding.
- **A withdrawn phrase survives.** The same prose still says "A text-only method cannot do this even in principle", which the F6 response says was withdrawn.
- **Must change.** Add the generator to `GENERATORS`, interpolate the eight literals, and drop the phrase.

### F2 — major — The design constraint "every table carries a `ceiling` column and quotes headroom" is not honoured in `replication.md`
- **What the design requires.** D-032 as frozen: every table carries a ceiling column and quotes headroom.
- **What the table has.** `replication.md` has neither column, and no amendment covers this.
- **Why it matters here.** The table reports `bge_m3_sparse` at 0.0205 on `resumen` with no reference to its 0.0501 identity ceiling, and `dense_e5` at 0.0224 against 0.5150. That is exactly the reading D-032 exists to force.
- **Must change.** Add ceiling and headroom (resumen ÷ identity, scored) per arm, or file an amendment.

### F3 — minor — The tie-break mechanism is credited on a path where it does not run
- **What the report says.** Finding 1 and `ceiling.md` attribute the surplus hits of `bge_m3_dense` and `dense_es_hiiamsid` to `np.argpartition`.
- **What the code says.** `bge_m3_dense` ranks with FAISS `self.index.search` (`src/retrievers/bge_m3_dense.py:122`), not argpartition.
- **An unexplained gap.** Both arms show identical-text queries whose gold does not tie rank 1: 19 of 776 for dense (757 level) and 6 for hiiamsid (770). Identical texts are therefore not always encoded to identical scores. The report does not discuss this, and it bears on A7's "memory, not results".
- **Must change.** Restate the mechanism per arm.

### F4 — minor — The ceiling column for the two oracle arms is not the ceiling of their indexed field
- **The requirement.** Exit criterion 5 asks for "the corpus ceiling of the indexed field".
- **What is printed.** `bm25_unigram_params` and `tfidf_phrases_replace` index `texto`+`parameters`, yet the table prints the `texto` ceiling 0.9863.
- **Consequence.** This yields headroom 1.0133 and 1.0108. Their field's ceiling is empirically 1.0 (776/776 resolved).
- The prose explains the >1 values but does not fix the column.

### F5 — minor — "In 4 of 6 cells the argmax is the transferred point" counts an exact tie as a win
- **The tie.** In `bm25_unigram_params`/`texto`, 0.60/0.35 and 0.80/0.35 both score 34,625/34,646.
- **How it was broken.** `max(surface, key=...)` breaks the tie by iteration order (`build_results_e0.py:302`).
- **What it should say.** "3 of 6, plus one exact tie". "Always at k1 = 0.60" is likewise not unique there.
- This does not affect the selection cell (`single_texto`).

### F6 — minor — Report prose inaccurate against the artefacts
- **"Ten arms indexed … clean, at one commit."** Index stamps are at `6336974` (BM25), `31bf1a1` (ColBERT), `2dd653d` (six arms) and `a5700a6` (`bge_m3_dense`). The header's "Indexes at `2dd653d` (seven S3 arms)" is also wrong for `bge_m3_dense`.
- **"The only changes on the retrieval path are `corpus_prep` … and `run_context` … everything else is analysis code."** `git diff 31bf1a1..HEAD -- src/` also changes five retrievers and the `bge_m3_dense` builder. The reuse conclusion still holds: the three reused arms' retrievers are unchanged.
- **"Five new test files."** Eight were added since the freeze.

### F7 — minor — Overclaims in the report's prose
- **H2 row.** "Overlap orders the types as the layer taxonomy predicts (`reorder` 99.65 %, `template_paraphrase` 77.47 %)" cites two L3 types. The taxonomy predicts L3 near-free for bag-of-words, and `template_paraphrase` has the lowest lexical coverage of any single type. The example does not support the claim.
- **Finding 4.** "Doubling concentrates in exactly these types" puts `unit_expansion` at 17.2 %, but `synonym_label` is at 16.2 %.
- **Finding 4's H5 re-specification.** It rests on `unit_conversion`'s 79.14 % / 57.35 %, which are quoted with no interval. The table carries none for numeric coverage.

### F8 — minor — Previous-study parent reference for `bm25_unigram_params` is not attributable
- **What the table cites.** `replication.md` cites 0.985 as its parent Acc@1 from `paper_28.tex`.
- **What the paper contains.** The paper gives BM25 parent-level only as a range, "0.873 to 0.985" (l. 559). The generator treats that same range as "range only" for `bm25_unigram`. The only per-method 0.985 is Recall@10 on numeric queries (l. 640).
- **Must change.** Print "—" with the range note, as for `bm25_unigram`.

### F9 — minor — Undeclared-by-amendment path change
- Exit criterion 4 names `results/S3/run_provenance.md`, but the stamps are in `e0/` and `s2_rescored/`.
- This is declared in the report's prose but not in the Amendments table.

## Unverifiable
- **A7: blocking changes memory, not results.** No pre-blocking runs survive to compare, and F3's non-identical scores for identical texts weaken the claim for `bge_m3_dense`.
- **"12 of 17 runs lost to `DeadKernelError`".** Git-ignored logs only.
- **ML-stack versions of the dense arms (H4).** Not stamped in `index/*/meta.json`.
- **Regeneration "from a clean checkout".** Verified from a clean working tree at HEAD. A fresh clone cannot hold the git-ignored data.
- **OEB validation's 22,305 test-side pairs.** Generator output only, not independently recounted.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1 Manifest digests | yes | Five delivered digests match upstream `handoff_OE/MANIFEST.md`; superseded JSON/norm/feats re-hash to their suffixes |
| 2 Row-for-row identity test | yes | All 26 common columns of `feats__7b0894e6` vs `feats` identical (independent check) |
| 3 S2 runs resolve | yes | `check_run_inputs.py`: 177/177 `runs/OE` |
| 4 Twenty E0 runs, clean, listed | yes | 21 runs recomputed, all `dev`, `code_dirty: false`; listed in `e0/run_provenance.md` (path differs, F9) |
| 5a Item/parent × query/concept CIs | yes | `ceiling.md`, regenerated byte-identically |
| 5b Corpus ceiling of indexed field + headroom | no for 2 of 10 arms | Oracle arms carry the `texto` ceiling (F4) |
| 6 Replication table, statement, hiiamsid row | yes | `replication.md`; all ten rows recomputed |
| 7 150 sweep cells, argmax, paired Δ with CI | yes | 150 runs present; contrasts reproduced; tie in one cell (F5) |
| 8 OEB reference within 0.5 pp | yes | 94.10 / 99.96 %, regenerated |
| 9 Overlap for four sets, seven statistics | yes | `overlap.md`, spot-checked 79.38 % |
| 10 Re-score, n printed, byte-identical | yes | `s2_rescored/` regenerated byte-identically |
| 11 By-dose on `texto_modification_count` | yes | `stacked_by_dose.md`; 730→193 cross-tab present |
| 12 D-012 / D-009 / S8 | yes | `DECISIONS.md` D-012 closed, D-009 Delivered; `SPRINTS.md` log line 78 |
| 13 Regression tests, suite passes | yes | Duplicate-exclusion, overlap-reference and versioned-set tests present; 979 passed, 1 xfailed (re-run) |

---

*The first audit of this sprint (FAIL, report `4a3f9ef`) follows unchanged.*

# Sprint S3 — audit

**Verdict:** FAIL
**Audited:** 2026-09-28 · report `4a3f9ef` (`docs/synthetic-oe/sprints/SPRINT_S3_REPORT.md`) · runs `runs/OE/{texto,resumen,single_texto,stacked_texto}` (177 run dirs)

The main reason for FAIL is F1. Two p-values the report emphasises cannot be reproduced by any committed code, and the committed generator prints different values in the same results directory. The substance of the sprint holds up well. The headline numbers trace, the tables regenerate byte-for-byte, no run touched test, and the design was not edited after freeze. What fails is the provenance rule plus the overclaiming in F2–F3.

## Verified
- Design freeze: `git diff 8353cf7..HEAD -- SPRINT_S3_DESIGN.md` shows only the freeze stamp and amendment rows A1–A10, each dated. A9 (keeping 0.60/0.35 rather than the literal argmax) is a declared amendment, not a silent change.
- `bm25_unigram_params` identity 0.9994 scored, 776 of 776 undecidable resolved. Traced to `OE/texto/bm25_unigram_params__k1-0.60__b-0.35__OE`; matches.
- `dense_es_hiiamsid` identity 1.0000 on n=34,646, 293/776 (`OE/texto/dense_es_hiiamsid__OE`); `resumen` 0.0093 scored (`OE/resumen/dense_es_hiiamsid__OE`). Both match.
- `bge_m3_sparse` 0.0501 scored / 0.0509 all; ColBERT 0.9998 scored, 292/776; `bge_m3_dense` 293/776. All match.
- Replication 0.6394 / 0.0142 / 0.0148 (k1=0.80), all n=34,646. Match the `OE/resumen/*` runs.
- Transferability deltas +0.0014 [−0.0106, +0.0133] (+90/−87) and +0.0049 [−0.0065, +0.0166] (+114/−102). These match. The p-values do not (F1).
- Finding 5 (730 → 193; concepts 27→17→8→2→1) matches `s2_rescored/stacked_by_dose.md`.
- Overlap 79.38 % / 94.10 % / 99.96 % and the finding 4 figures match `overlap/overlap.md`.
- All three result directories (`e0`, `s2_rescored`, `overlap`) regenerate byte-identically. I ran the generators with `OUT` redirected to the scratchpad and diffed; the tree stayed clean.
- All 177 `runs/OE` runs are `split: dev` and `code_dirty: false`. `check_run_inputs.py` resolves all 177.
- One sample per comparison: query keys are identical across the digests mixed inside tables (texto `643f1a72` vs `75477221`; resumen `f041a8e8` vs `28d09f40`; stacked `7b0894e6` vs `f34c1798`, 2,521 = 2,521).
- Previous-study figures 0.974 / 0.869 / 0.708 match `docs/reviews/paper_28.tex`.
- `MANIFEST.md` carries all six digests. In-tree hashes match `b3cfcad4`, `c34a222a`, `555fab84`.
- Test suite: 972 passed, 1 xfailed. The S3 test files alone: 144 passed.

## Findings

### F1 — critical — the reported p-values cannot be reproduced; the generator hard-codes prose numbers that contradict its own tables
- **Report says:** p=0.845 and p=0.417 (report line 57). The same values appear in D-036, A9, and the prose of `results/S3/e0/replication.md`.
- **Artefacts say:** `transferability.md`, generated by the same script, prints **0.8507** and **0.4250**. I recomputed both from `results_perquery.parquet` with the committed helpers and got 0.8507 / 0.4250.
- **Why they differ:** I only reproduced 0.8449 / 0.4168 by seeding the bootstrap with the label `"{variant}|{queryset}"`. No committed code uses that label; the generator uses `"sweep|{variant}|{queryset}"`. So the reported values come from an uncommitted computation. They were then typed into `build_results_e0.py` as literal strings (line 303).
- **Same pattern elsewhere in the generator:**
  - "0.0096 on `resumen`" (line 227, and STATE.md) is hiiamsid's all-queries figure, not the scored 0.0093 that D-033 requires.
  - "292, 293, 293", "776 of 776", "79.38 %" and "94.09 %" are also literals, not interpolated.
- **Fix:**
  - Interpolate every number in generator prose from the computed values.
  - Correct the report, D-036 and A9 to 0.8507 / 0.4250, or commit the code that produced 0.845 / 0.417.
  - Regenerate.
- The conclusion (noise) does not change. The provenance rule is still broken.

### F2 — major — mechanism and mediation claims that the frozen design rules out
- **Report says:** "the mechanism is measured", "two findings settle why", H5 "partially supported… already explains the baseline difference between chapters", D-037 "the mechanism of the replication gap".
- **Design says:** "Overlap is descriptive in S3… No causal or mediation claim is made here." It also says the replication is a reference, with no delta computed against OEB.
- **What the evidence is:** "15 points" is a delta between OE dev across all 7 subchapters and the full OEB reference. That is two data points, with chapter confounded — which the report concedes in the next paragraph.
- **Fix:**
  - Restate finding 3 and D-037 as descriptive.
  - Move H5 back to "not addressed".
  - If a mechanism is wanted, compare within OE (OEB-subchapter dev leaves against the rest) and do it in S6.

### F3 — major — "tuning is not where the difference lives" rests on a sweep that never ran on `resumen`
- **Report says:** the replication gap is not tuning, and "The previous study's operating point may not transfer" is listed as *false*.
- **Artefacts say:**
  - The replication gap is on `resumen→texto`. The sweep covers `texto`, `single_texto` and `stacked_texto` only.
  - On `resumen` there are two points: 0.60/0.35 and 0.80/0.35.
  - The two non-significant contrasts have CIs about ±1.2 pp wide. Failing to reject a difference does not show equivalence.
- **Fix:** restrict the claim to "no detectable gain on the three swept sets" and drop "false".

### F4 — major — exit criterion 5 is reported met but is not
`ceiling.md` gives a concept-clustered CI for item level only. The parent column has a query-level CI and no clustered CI. This matters where parent is below 1: sparse 0.8845, GTE 0.9787 and 0.9671.

### F5 — major — the pantry-artefact sensitivity (D-004) is not honoured for the per-type claims
- **Report says:** per-type L1 claims (finding 4, D-038).
- **Artefacts say:**
  - `overlap.md` runs the sensitivity only at the `all` level. The generator's own text says D-004 requires it "before any per-type claim".
  - The "con topo" → "con topografía" drift, which the design names, is not handled at all.
  - The doubled-token subset differs where the claim lives: Δ numbers −0.67 against −0.18 for the rest of `single_texto`. So the doubling likely concentrates in the number-removing types.
- **Fix:** per-type sensitivity rows, plus the topo exclusion.

### F6 — minor — the "categorical" ceiling claim is contradicted by the report's own numbers
- `bge_m3_dense` and `hiiamsid` resolve 293 of 776 undecidable queries, above the 292 "no text-only arm beats".
- `hiiamsid` all-queries is 0.9864, above "the corpus permits at most 0.9863". Its headroom is therefore above 1.0, against "only the two oracle arms".
- The report does not explain this; tie-breaking or floating-point nondeterminism in the embeddings is the likely cause.
- The oracle result (776 vs about 292) stands. Explain the extra query or soften "categorically" and "even in principle".

### F7 — minor — thin slices are printed as bare point estimates
In `overlap.md`, `paraphrase` (n=108) and `expansion` (n=130) have no intervals and are not pooled. The design constraint "Thin slices carry their intervals" requires one or the other.

### F8 — minor — the stacked transferability row pairs two query-set digests without saying so
The 0.60/0.35 reference is on `7b0894e6` and the 0.60/0.50 argmax is on `f34c1798`. It is the same sample in substance: keys are identical and the texts are tested identical. But `transferability.md`'s Sources lists only the reference runs, never the argmax runs. List both and note the digest pair.

### F9 — minor — the report's provenance header and evidence are inaccurate
- The code-commit span omits `789a6d7` (all 144 sweep runs) and `2a9ffdb` (the k1=0.80 `resumen` run).
- The digest list omits `28d09f40` (ColBERT and dense on `resumen`).
- The k1=0.80 `resumen` run is missing from `e0/run_provenance.md` (168 rows). It is stamped only in `replication.md`.
- Test suite: 972 passed, not 971.
- `check_run_inputs.py` reports 5 failures, not "the one": four archived S1 runs plus `OEB/resumen/…`.
- D-037 quotes 0.6473, the all-queries figure, where the report uses 0.6394.

### F10 — minor — the overlap validation reads test-split concepts
`validate_against_oeb()` uses all 47,514 OEB pairs, including OE test concepts such as `OEB040$` and `OEB280$`. That contradicts the generator's "Dev split only" header, and the definition was chosen by matching against these pairs. The design mandates the check and no retrieval parameter was set from it, but it should be declared.

### F11 — minor — the dirty-tree refusal is not in committed code
`run_provenance.md` says "the runners refuse to start from a dirty tree". That refusal lives only in the git-ignored `logs/S3/*.sh`; `src/utils/provenance.py` records dirtiness but does not refuse. The stamps themselves are verified clean.

## Unverifiable
- `bge_m3_sparse` vector norms 0.47–1.09 and the "gold at rank 2–6, no ties" explanation — would need the index loaded.
- A7's claim that "blocking changes memory, not results" for the five newly blocked arms — there are no pre-blocking completed runs to compare against.
- A6's claim that the GTE pair's `embeddings.npy` are byte-identical — not checked.
- The ML-stack versions behind the dense arms — recorded only in a git-ignored log (defect H4).
- "Regenerate byte-identically from a *clean checkout*" — verified from the current clean main checkout, not a fresh clone.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1 Manifest | yes | All six digests in `MANIFEST.md`; in-tree hashes match |
| 2 Row-for-row identity test | yes | `tests/test_intake_20260927.py` passes |
| 3 S2's 15 runs resolve | yes | `check_run_inputs.py` resolves 177/177 `runs/OE` (evidence text misstated, F9) |
| 4 Ten × identity + `resumen`, clean, listed | yes | 20 runs, dev, `code_dirty: false`, in `e0/run_provenance.md` (path deviation declared) |
| 5 Ceiling table incl. clustered CIs at both levels | no | Parent-level concept-clustered CI absent (F4) |
| 6 Replication table + disclaimer + hiiamsid row | yes | `e0/replication.md` |
| 7 150 sweep runs, argmax, Acc@1, paired Δ with CI | yes | `e0/transferability.md`; p-values in prose do not reproduce (F1) |
| 8 OEB reference within 0.5 pp before use | yes | 94.10 / 99.96 %; `validate_against_oeb()` runs first |
| 9 Overlap, four sets, per condition, seven statistics | yes | `overlap/overlap.md` (+2 columns, A10) |
| 10 Re-score with corpus / scored / excluded n; byte-identical regeneration | yes | `s2_rescored/exclusion.md` gives all three per query set; regeneration diff empty |
| 11 By-dose on `texto_modification_count` | yes | `s2_rescored/stacked_by_dose.md` |
| 12 D-012 closed, D-009 Delivered, S8 → planned with log line | yes | `SPRINTS.md` log rows dated 2026-09-27 |
| 13 Regression tests + suite passes | yes | 972 passed, 1 xfailed |
