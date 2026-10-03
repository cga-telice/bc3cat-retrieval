# Sprint S9 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-03 · report `a2a72a1` · runs `runs/OE/{texto_u,resumen_u,single_texto,single_l2_texto,stacked_texto}__{canon,hyde,rewrite}/*` (105), `runs/OE/*/bm25_unigram{,_params}__k1-0.60__b-0.35__idfcap-1200__OE` (10), `runs/OE/*/structured_pipeline_llm_valuenorm__OE` (5), `runs/OE/*/structured_pipeline_llm_keytol_valuenorm__OE` (5); references `runs/OE/{texto,resumen,single_texto,single_l2_texto,stacked_texto}/*`

No number failed to reproduce, no comparison mixes samples, and the design did not change after the freeze. The findings below are about how intervals are reported, overclaiming, and exit-criterion clauses that the report marks met but that are not.

## Verified
- **Design freeze holds.** `git diff 587e466..HEAD -- SPRINT_S9_DESIGN.md` shows only the placeholder fill at `7649994` (the freeze SHA and the file name). The amendments file is append-only: every post-freeze commit to it removes 0 lines, except that same placeholder at `7649994`.
- **Regeneration is byte-identical.** I re-ran `build_results_s9.py` at HEAD in `bc3cat-s3` with its output sent to `/tmp`. All 9 analysis tables and `fig7_crossover.png` hash the same as the committed files. `run_provenance.md` differs only in its "Generator commit" line (`a2a72a1` vs `86b995c`).
- **Runs are clean.** There are 125 S9 runs (105 + 10 + 5 + 5). All have `code_dirty: false`, split `dev` and `dropped: 0`. `check_run_inputs.py --collection OE` reports 405 of 405 resolving.
- **Inputs match their stamps.** The config SHA-256 of `structured_pipeline_llm{,_keytol}_valuenorm__OE`, `bm25_unigram…idfcap-1200__OE`, `bge_m3_colbert__OE` and `bm25_unigram…__OE` match T10. The data digests `OE_texto_u` `703940b6`, `OE_resumen_u` `000021c5`, `OE_single_texto` `b6a43961`, `OE_single_texto_feats` `e5b79ae4`, `OE_resumen_u__hyde` `eae8e281`, and the extractor cache `9760108b` all match.
- **Sampled figures, recomputed independently from `results_perquery.parquet` and `results_top100.jsonl.gz`:**
  - Headline Y2, `bm25_unigram` H, B1, tie-free: −0.0226 on n 1,746. Matches.
  - Y2, ColBERT H, B1: −0.1634. Matches.
  - Y1, `bm25_unigram` W, B4: +0.1135 on n 1,816. Matches.
  - T1 `texto_u` H, as run: BM25 −0.3042 on n 2,636; `dense_es_hiiamsid` −0.8714. Match.
  - BM25 W on `single_texto`, as run: +0.0896. Matches.
  - G1, as run: +0.0654 at parent level on n 2,691. G2, as run: +0.0951. Stacked parent with the cap: +0.2150. Identity with the cap, tie-free: 0.8934 → 0.9082. All match.
  - Z1 BM25, as run: +0.2594 on n 1,037. Z2: +0.0000. Match.
  - E1 and E2, as run: +0.0241 and +0.0058. Key-tolerant variant on L1, tie-free: 0.7830. Match.
- **The IDF cap actually executes.** `idf.npy` in the capped index has max 4.0692, and 468 of 682 terms sit at the cap. The uncapped index has max 9.907. The cap feeds both the document weights and the query side through `idf.npy`.
- **The A7 tolerant key match executes.** The keytol index `meta.json` has `llm_key_match: tolerant`, and `LLMParamExtractor._lookup` branches on it.
- **The canonicaliser reads only query text and `OE_texto.json`.** Neither `canon.py` nor `apply_canon.py` reads parameters, modification types, gold or concept.
- **Split discipline holds.** All 15 derived sets contain dev concepts only (0 test-concept records). Runs report `queries_before_split == queries_after_split`.
- **T7 counts add up.** Rewrite fallbacks total 7 and HyDE non-Latin outputs total 13, 11 of them on `resumen_u`. Determinism logs: HyDE 98/100, rewrite 99/100, extractor 100/100.
- **No ⚑ anywhere in T9.** No tie-free reading differs from its as-run reading.
- **D-004 robustness is reported correctly.** Z1 ColBERT reads "not robust" in T8, and the report says so.
- **Tests pass.** Full suite: 1718 passed, 2 skipped, 1 xfailed. OEB golden fixture: 11 passed. `test_report_traceability`, `test_canon` and `test_intake_s9`: 86 passed.

## Findings

### F1 — major — The same statistic has different intervals in different tables, and the report mixes them
- **Report:** findings 1 and 2 give `bm25_unigram` H B1 as −0.0226 [−0.0487, −0.0105], ColBERT H B1 as −0.1634 [−0.2132, −0.1347], and BM25 W B4 as +0.1135 [+0.0429, +0.1474] "(Holm 0.3172)". These are T2's intervals placed next to T9's Holm p.
- **Artefacts:** T9 (`predictions.md`) gives the same three estimates as [−0.0479, −0.0101], [−0.2109, −0.1335] and [+0.0413, +0.1480].
  - E1 and E2 in the report ([−0.0881, +0.2507], [−0.0688, +0.1812]) are T9's. T6 prints [−0.0864, +0.2570] and [−0.0682, +0.1879].
  - G1 in T9 is [+0.0225, +0.1299]; in T5 it is [+0.0228, +0.1334].
  - BM25 `texto_u` H is [−0.4080, −0.2274] in T1 and [−0.4096, −0.2274] in T2's B5.
- **Cause:** `delta_cell` draws under the label `s9|{table}|…`, so every table resamples on its own. A6 fixed this for T3 only. This is the same defect as S7 F7, S8 F9 and S9 A6.
- **Required:** one bootstrap draw per statistic across T1, T2, T5, T6 and T9, regenerated. The report must quote one interval per statistic, from the table it cites.

### F2 — major — The report claims HyDE harms everywhere, and "refutes" the gain clause, beyond what the intervals show
- **Report:**
  - Finding 1's heading: "HyDE hurts every tested arm at every overlap".
  - Known-wrong 1: "HyDE is harmful at every overlap".
  - Hypotheses table: the gain clause is "**refuted** … for H and W".
- **Artefacts:**
  - T2 concept intervals include 0 for `bge_m3_dense` H B1 (−0.0069 [−0.0319, +0.0064]) and B2 (−0.0044 [−0.0377, +0.0125]), and for `dense_e5` H B1 [−0.0342, +0.0069] and B2 [−0.0300, +0.0073].
  - Under W, Y2 is "not supported" for 5 of 5 arms and "contradicted" for none. `dense_es_hiiamsid` W B1 is +0.0189 with a query-level interval of [+0.0063, +0.0321].
  - Under H, Y2 is contradicted for only 2 of 5 arms.
- **Required:**
  - Restate H as "harm, or no detectable effect, in every bin".
  - The gain clause is contradicted for H on BM25 and ColBERT only. It is not supported for the other H arms and for all W arms. It is not "refuted".

### F3 — major — "No crossover exists" overrides the registered decision rule's output without an amendment
- **Report:** the Hypotheses table says "no crossover exists". Finding 1 says c* "is not a threshold". Known-wrong 1 says c* "must not be reported as a threshold".
- **Artefacts:** under the design's rule (A5 e), T3 reads "c* in range: yes" for 9 of the 10 H and W fits.
- **The argument rests on B1.** B1 spans [0, 0.70) and contains c* for four of the five H arms, so it is not the region below c*.
- **My own check (point estimates only, no interval):** below c*, the observed tie-free H δ is negative for every arm:

  | arm | δ below c* | n | of which stacked |
  |---|---:|---:|---:|
  | BM25 | −0.0240 | 748 | 678 |
  | `bge_m3_dense` | −0.0107 | 1,405 | 1,147 |
  | `dense_e5` | −0.0179 | 894 | 802 |
  | `dense_es_hiiamsid` | −0.0317 | 1,137 | 970 |

  The substance is therefore plausible, but it is confounded with `stacked_texto`. ColBERT's c* of 0.3436 has a single query below it (observed range starts at 0.3415).
- **Required:**
  - Record the reinterpretation as an amendment, or at minimum under "Deviations from design".
  - Back it with a generated statistic: δ below c* per arm, with both intervals and the base mix.
  - Until then, the report should not contradict T3's own "in range: yes".

### F4 — major — Exit criterion 3 says T10 carries model digest and prompt SHA per LLM run; the extractor runs have neither
- **Report:** exit criterion 3 "yes".
- **Artefacts:**
  - T10's LLM table lists only the 10 H and W sets.
  - The 5 registered extractor runs and the 5 keytol runs have no model digest or prompt SHA in T10, and their `run_meta.json` has neither.
  - T7 prints the tag `phi4:latest` and "source `extract`".
  - `logs/S9/determinism_extract.json` has `prompt_sha256: null`.
- **Mitigation:** the digest is enforced at runtime (`llm.py` pins `ac896e5b8b34`, and the cache key includes it), and the cache file's digest is in T10.
- **Required:** add the extractor's model digest and prompt-template SHA to T10, or downgrade the criterion.

### F5 — minor — Thin cells are read without ‡, and T4 lacks content the design asks for
- **Thin cells:**
  - Finding 3 reads BM25 `num_to_text` +0.7475 [+0.6654, +0.8148] on **9 concepts**. T4 marks no cell ‡: `compression`, `expansion` and `paraphrase` are at 5 concepts. S5 flagged the same `num_to_text` cell ‡.
  - Finding 4 includes `single_l2_texto` (9 concepts) in "lowers no base … raises most". T5 has no ‡ either.
- **Missing from T4:** the design's per-layer δ_C rows and the "tokens rewritten" column.
- **Required:** ‡ in T4 and T5, and per-layer rows in T4. The `num_to_text` sentence must carry its concept count.

### F6 — minor — Caveats that amendments and the design promised are not carried
- **A1's rate:** A1 commits that "the report states [the 1–2 % regeneration rate] with every H and W figure". The report never does.
- **A3/A5(l) fallbacks:** they put the fallback n "beside each W figure" in T1 and T7. Only T7 has it, and `profile.md` has 0 occurrences.
- **OEB exposure:** the design's risk row requires the extractor's OEB exposure "with every E-figure". Finding 5 omits it (only T6's header states it).
- **Effect:** numerically negligible, but each of these was promised.

### F7 — minor — Wording and comparisons that need tightening
- **"Oracle bound":** "+0.5439 over the oracle bound" (finding 5). S5's bound reads schema literals and leaves the rewritten axis blank, so it is not an upper bound on a value-reading extractor. Call it the "literal-oracle bound".
- **"Rewriting costs less than HyDE"** (finding 2) has no paired W − H contrast or interval behind it.
- **T6 profile tables:** both the registered arm's and the variant's print n scored without n or n excluded. This is an exit criterion 4 clause.

## Unverifiable
- **A5's statement that no S9 metrics or per-query files were opened before the specification (`90c5ed2`).** This is a session claim; the runs already existed on disk.
- **The "byte-identical twice" claims for runs 1–14.** The logs record only the commit and "written", not output hashes. My own regeneration at HEAD does match the committed tables (see Verified).

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1. Sets resolve, bases re-derive, manifest, D-040 in harness with tests | yes | `test_intake_s9` passes; MANIFEST lists 71 derived/cache entries; 405/405 resolve |
| 2. Regeneration test for H, W, extractor, recorded | yes | `logs/S9/determinism_*.json`: 98, 99, 100 of 100; A1, A4 |
| 3a. 120 runs clean, dev, resolving, stamped | yes | 125 runs `code_dirty: false`, split dev; `check_run_inputs` 405/405 |
| 3b. T10 model digest + prompt SHA per LLM run | no | Extractor and keytol runs absent from T10's LLM table (F4) |
| 4a. T1–T10, Fig. 7 generated, byte-identical, prose guard | yes | Auditor regeneration identical; `test_report_traceability` passes |
| 4b. n, n scored, n excluded on every item-level figure | no | T6 base profiles print n scored only (F7) |
| 4c. Concept and query-level intervals and concepts per contrast | yes | Both intervals present in T1–T6, T9; but see F1 on their inconsistency |
| 5. 44 tests read tie-free, as run, D-004 beside | yes | T9 (44 rows, no ⚑), T8 |
| 6a. H6 resolved by the rule | yes | T9: "partly supported" for H and W |
| 6b. c* per arm and transform stated | no in the report / yes in T9 | Report gives 3 of 10 (H only, no intervals); T9 lists all 10 with intervals; F3 |
| 6c. D-041 and D-046 answered, scoped to dev / in-sample | yes | Findings 4 and 5, Hypotheses table |
| 7. Full suite and OEB fixture | yes | 1718 passed, 2 skipped, 1 xfailed; `test_golden_fixture` 11 passed (auditor run) |

Paths: report `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\sprints\SPRINT_S9_REPORT.md`; tables `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\docs\synthetic-oe\results\S9\`; generator `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\src\utils\build_results_s9.py` (`delta_cell` labels, the cause of F1); runs `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\runs\OE\`.
