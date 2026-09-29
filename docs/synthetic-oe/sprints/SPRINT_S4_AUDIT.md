# Sprint S4 — audit

**Verdict:** FAIL
**Audited:** 2026-09-29 · report `b748138` (`docs/synthetic-oe/sprints/SPRINT_S4_REPORT.md`) · design frozen at `dd407c6` · runs `runs/OE/texto/<arm>`, `runs/OE/single_texto/<arm>`, `runs/_archive/S4/OE/single_texto/dense_gte_instrQ__OE`

The FAIL rests on one defect: a generated table mixes samples (F1). The fix is narrow. Every headline figure I recomputed from the raw runs reproduces exactly. The design is clean and the derived arms execute as specified.

## Verified
- **Headline retentions (Finding 1).** Recomputed from `results_perquery.parquet` (single_texto) paired with the texto identity runs on the gold, excluding D-033 golds and the P7 query (n=2,176, 42/40 concepts). All match to 4 dp:
  - `bm25_unigram` 0.5391
  - `bm25_unigram_params` 0.6226
  - `bge_m3_colbert` 0.7791
  - `bge_m3_dense` 0.6341
  - `dense_es_hiiamsid` 0.5928
  - `rrf` 0.7876
  - `ce_bge_m3_colbert` 0.6700
- **Parent level (Finding 1).** `bm25_unigram` 0.9991 → 0.8001 and ColBERT 1.0000 → 0.9995 (n=2,206). Both match.
- **Collapse quantities (Finding 2).** Gap change +0.2050 / +0.2546 / +0.2201. D 0.9986 → 0.7784 (ColBERT) and 0.8951 → 0.6115 (`bm25_unigram`). Oracle right-parent/wrong-item 0.0028 → 0.2574. All recomputed; all match. The P1 rows of T6 agree.
- **Finding 3.** `bm25_unigram` L1/L2/L3 retention 0.3036 / 0.7832 / 0.6989. `num_to_text` 0.1178 / 0.0958 (oracle) / 0.7700 (ColBERT). All recomputed; all match.
- **Findings 4–5.** `reorder` δ is 0.0000 (both BM25 arms), −0.1333 (ColBERT), −0.3400 (`bge_m3_dense`) and −0.1100 (hiiamsid). `template_paraphrase` retention 0.3864 / 0.2823. ColBERT L2 item δ −0.1434 with L2 parent 1.0000. All recomputed; all match.
- **Finding 7 ties.** L1 tied 483, gold in tie 268, gold wins 92 (0.3433), uniform 0.3005. `synonym_label` tie share 0.8182. Recomputed from `results_top100.jsonl.gz`; matches.
- **Finding 8 floors.** 0.0625 / 0.0951 / 0.1062 recomputed; GTE parent 0.9665 matches.
- **T1 ceilings.** `rrf` 0.9547 and `ce_bge_m3_colbert` 0.9457 are on the same scored population (34,646) as S3's ColBERT 0.9998 (`results/S3/e0/ceiling.md`).
- **Input digests re-hashed.** `OE_single_texto_feats` `e5b79ae4`, `OE_long_feats` `643f1a72`, `OE_long_norm` `75477221`, duplicate-groups sidecar `b3cfcad4`. All match the stamps.
- **Byte-identical regeneration.** `build_results_s4.py` regenerated into the scratchpad (`OUT` redirected); all 7 tables are byte-identical to the committed ones. The tree stayed clean.
- **RRF executes as designed.** An independent RRF (k=60, top-100, absent contributes 0) reproduces rank 1 on 2,206/2,206 `single_texto` queries.
- **CE blend is wired as designed.** min–max per query, λ=0.6, depth 100, fp32 and a pinned revision are in `rerank_ce.py`, the config and `run_meta.json`. The ML stack is stamped.
- **Work item 4 count.** Exactly one dev query equals another dev leaf's `texto` (`OEC140baa_syn_74d5dd2c9da3` → `OEC140aba`), and no two queries are identical. Reproduced.
- **Reuse diffs (T7).** Verified with `git diff <commit>..36bed7a`: no retriever, builder, `retrieve.ipynb` or config change on any reused run's path. The `corpus_prep`/`run_context` changes are a field-carrying guard and a worktree guard.
- **Archived run (A2b).** `code_dirty: true`, dirty path `src/utils/build_results_s4.py`. The re-run is clean at `36bed7a`.
- **Design freeze.** `git diff dd407c6..HEAD` on the design touches only the freeze line and adds amendments A1–A3.
- **Tests.** `test_report_traceability.py`, `test_derived_runs.py` and `test_generated_prose.py` pass (32 tests). `build_results_s4.py` is under the prose guard.

## Findings

### F1 — critical — T4 mixes samples, and the report quotes the contaminated figure
- **What the report says.** Finding 4 opens "every figure below is on that population" (2,176 at item level), then quotes `template_paraphrase` d_tok 0.3206 against 0.0053 for `reorder`.
- **What the table does.** In `results/S4/token_distance.md`, every item-level δ/d_tok cell divides an item δ taken over the item-scored queries by a mean d_tok taken over all 2,206 queries.
- **Why it matters.** The 2,206 include the P7 query, which the report itself excludes as not referent-preserving; it carries a sibling's whole `texto`. On the item-scored population, `reorder` d_tok is **0.0023**, not 0.0053 (`template_paraphrase` 0.3221; all 0.0933). The item-level `reorder` δ/d_tok ratios are therefore off by a factor of about 2.3. S6 inherits T4 for H5.
- **What must change.**
  - Compute d_tok per level on that level's population and regenerate T4.
  - Re-quote Finding 4 on the item-scored population (the contrast survives: 0.3221 vs 0.0023).

### F2 — major — Exit criterion 4 is reported "yes" but is not met
- **What the requirement is.** Design (Population, T2 spec), amendment A2 ("Its n excluded is printed beside every figure") and EC4 ("Every item-level figure carries n scored and n excluded") all require per-cell exclusion counts.
- **What the tables do.** T2 prints a single `n` per cell and no excluded column. The 29 + 1 exclusions appear once, in the header. T1 prints "item, all" and "n scored" but no n excluded.
- **What must change.** Add the column, or mark EC4 not met.

### F3 — major — L2 conclusions rest on 5 concepts, and the report never says so
- **What the tables show.** In T2/T3, `paraphrase`, `compression`, `expansion` and the L2 pool each cover **5 concepts**.
- **What rests on them.** P2 (×4) and P5 are read "supported" on a concept-clustered percentile bootstrap, with one side of the contrast built on 5 clusters; percentile intervals under-cover at that cluster count. On the same slice, the report states:
  - "L2 attacks the concept only for BM25"
  - "L2 hurts the encoders at item level only"
  - and lists "L2 affects concept-level more than item-level" under "What is now known to be wrong".
- **The report's own records know this.** `RESEARCH_PLAN.md` §5 records "reach 5 dev concepts".
- **What must change.**
  - Print the concept count in every L2 sentence.
  - Label the P2/P5 readings as resting on 5 clusters.
  - Move known-wrong #2 out of "known to be wrong" and restate it as a dev observation on 5 concepts pending the 9/9/8 build.

### F4 — minor — "bm25_unigram is the only family that loses the concept materially" (Finding 1)
T3 shows three other arms losing the concept:
- `rrf`: −0.0843 [−0.1029, −0.0405]
- `ce_bm25_unigram`: −0.0861
- the oracle twin: −0.1201

All contain BM25; say "BM25 and the arms built on it". Finding 5's "item level only" also holds only for ColBERT. At L2 parent level, `bge_m3_dense` is 0.9963, hiiamsid 0.9945 and `ce_bge_m3_colbert` 0.9706.

### F5 — minor — Finding 6 makes an arm-vs-arm directional claim that the design excludes
"Fusion and reranking lower the identity ceiling" has no paired test, and the design states "No arm-vs-arm contrast is claimed". Restate it as side-by-side reference.

### F6 — minor — Finding 7 asserts a null without an interval
- "The sort neither hands BM25 its hits nor takes them away" rests on 92 of 268 wins against 80.5 expected, with no interval or test given.
- "Those hits are draws" overgeneralises: 92 of about 276 L1 hits are tie-wins.

### F7 — minor — The decimal-artefact caveat is counted under a different definition, unreconciled
- **Design:** 9 `unit_conversion` + 4 `unit_expansion` (DATASET_DEFECTS H1).
- **T4:** 5 `unit_conversion` + 0 `unit_expansion`, because it counts only decimals absent from the gold.
- **Report:** never mentions the artefact.

Reconcile the two counts and state which set a miss is attributed to.

### F8 — minor — Four "treated" queries are untreated for any case-folding arm
`OED010bkabc_syn_85a4f552cd1b`, `OED030babca_syn_609ea3a72274`, `OED050bcbdc_syn_c59e212d9862` and `OED080bhbda_syn_7575e67f784b` (all `synonym_label`) differ from their gold `texto` only in letter case ("Semi-Rocoso" vs "semi-rocoso"). After normalisation they equal the identity query, so their δ is 0 by construction. Work item 4's scope did not cover this, but it bears on the treatment-on-the-treated reading. Record it (candidate P-class defect) and report the effect on `synonym_label`.

### F9 — minor — "L3 as a layer refuted" rests on an unregistered, post-hoc observation
The hypotheses table flags it as "not a registered test", but "refuted" is movement language. Use "not supported descriptively; S6 to test".

## Unverifiable
- **CE blend scores.** Not recomputed; that needs the cross-encoder. Only the wiring and parameters were checked.
- **Bootstrap p-values and Holm/BH.** Confirmed only through byte-identical regeneration with the committed seed, not by an independent implementation.
- **"No S4 figure had been read" before A2/A3.** A process claim; no artefact can show it.
- **Upstream claims.** P7's two test-split cases, the 9/9/8 L2 reach and the CE "~37 min" cost are not in `runs/`.
- **Finding 7's mechanism** ("because the rewritten token is out of vocabulary"). Plausible, but not tested in any table.
- **Full test suite and the OEB fixture (EC1).** I ran only the three S4-relevant test files. `check_run_inputs.py` (EC3) was not re-run.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1 Derived modules, configs, tests; suite green; components named | yes | `36bed7a`; `test_derived_runs.py` passes; naming by method per A1(b). The full suite was not re-run by the auditor. |
| 2 Work item 4 count recorded; amendment before reading | yes | Count of 1 reproduced; A2 in the design. Its timing cannot be verified. |
| 3 17 new runs clean, dev, resolving; CE ML stack; reuse diffs | yes | `run_meta.json`: `36bed7a`, `code_dirty: false`, split dev. `ml_stack` present. Reuse diffs verified by git. |
| 4 T1–T7 generated, byte-identical, guarded; n scored + n excluded per figure; CIs; identity baseline | **no** | Regeneration is byte-identical and the guard passes. No per-cell n excluded (F2). T4 mixes populations (F1). |
| 5 15 arms × 9 types × 2 levels + 3 pools, no empty cell | yes | 15 sections × 13 scopes in each of T2/T3; 0 empty cells. |
| 6 P1–P5 each read | yes | T6: 15 readings (14 supported, 1 not supported). See F3 on P2/P5 robustness. |
| 7 `WIDER_THIN_SLICES.md` committed; RESEARCH_PLAN §5 | yes | `docs/synthetic-oe/requests/WIDER_THIN_SLICES.md`; `RESEARCH_PLAN.md` line 372. |
| 8 H1/H2 movement lines stating S6 resolves | yes | Report hypotheses table. |
