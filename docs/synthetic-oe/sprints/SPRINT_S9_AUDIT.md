# Sprint S9 — audit of amendments A13–A14 (v2 re-run)

**Verdict:** PASS WITH FINDINGS (0 major, 5 minor)
**Audited:** 2026-10-19 · report `65b7fd5` (section "v2 re-run (A13–A14, 2026-10-18)", written at `fc59fd4`) · results `docs/synthetic-oe/results/S9/v2/` @ `65b7fd5` (the eleven `.md`, `figures/fig7_crossover.png` and `overlap_per_query.parquet` on disk equal `logs/v2/s9_gen2.sha256` and the committed blobs byte for byte; generated at `fc59fd4`, `src/` clean, per `run_provenance.md` l. 250) · runs `runs/OE/stacked_texto_v2__{canon,hyde,rewrite}/{7 arms}` (21), `runs/OE/stacked_texto_v2/{bm25_unigram, bm25_unigram_params}__…__idfcap-1200__OE` (2), `runs/OE/stacked_texto_v2/structured_pipeline_llm_{valuenorm,keytol_valuenorm}__OE` (2); references `runs/OE/stacked_texto_v2/{7 arms, structured_pipeline_rules_valuenorm}__OE` (S7 A8/A9); v1 `runs/OE/stacked_texto{,__canon,__hyde,__rewrite}/` · caches `data/processed/llm_cache/OE_stacked_texto_v2__{hyde,rewrite}.jsonl` (+ `OE_stacked_texto_v2__hyde.before_seed.jsonl`) · logs `logs/v2/chain_b_s9.out`, `chain_s9.out`, `gen_s9_v2.sh`, `run_v2_s9.sh`, `s9_gen{1,2}.sha256`, `logs/S9/determinism_{hyde,rewrite}_v2.json`. Recomputation scripts (auditor's, read-only): `C:\Users\cesar\AppData\Local\Temp\claude\D--Users-cesar-Dev-Phd-bc3cat-retrieval\f885e42f-130d-4c1d-8931-29cea1cfa390\scratchpad\recompute_s9_v2.py` (hits, bins, cells, slopes), `check_a.py`, `check_a2.py` (caches, change list, determinism keys, sidecars), `stamps.py` (run stamps).

## Verified
- **Stamps of the 25 runs.** All 25 `run_meta.json`: `code_commit 9036805`, `code_dirty: false`, `code_dirty_paths: []`, `split: dev`, `queries 2,521` (before/after split 2,521, dropped 0), `K 100`. `query_set_sha256` equals the SHA-256 of the file each run names on disk: `stacked_texto_v2__canon_feats.parquet` `b275ea66…`, `__hyde` `2f5f7579…`, `__rewrite` `2e039685…`, `stacked_texto_v2_feats.parquet` `977d40b9…`. `config_sha256` of every run equals the SHA-256 of its `configs/*.yaml` on disk (all eleven LF; the CRLF re-encoding matches no stamp, so no H5 phantom on this amendment); each v2 run stamps the same config digest as its v1 counterpart. `created_utc` 2026-10-19 01:57:15Z (`canon/bm25_unigram`) to 03:00:28Z (`llm_keytol_valuenorm`), consistent with `chain_s9.out`'s start times run by run; the batch guard refuses an existing run directory and the log shows no refusal. The eight references on `stacked_texto_v2` are clean, dev, at `8d1ffd2` (ColBERT, `bge_m3_dense`, `dense_e5`, `dense_es_hiiamsid`, `rules_valuenorm`) and `4f56a39` (`bm25_unigram`, `bm25_unigram_params`, `tfidf_phrases_replace`), created 2026-10-18 19:55:22Z–20:54:57Z (see F3).
- **Amendments before the runs.** A13 committed at `4f56a39` (2026-10-18 19:54:58Z); the first S7 A8 reference run on `stacked_texto_v2` saved 19:55:22Z, the first A13 run 01:57:15Z. A14 committed at `8c8fe18` (23:42:58Z), before every A13 run but after the seeded generation restarted (see F2). `9036805` (00:03:33Z) precedes the batch (01:57:05Z); the generation ran at `858d15c` (23:42:10Z, `dirty=0`), which the canon sidecar stamps (`code_commit 858d15c`).
- **v1 untouched.** The 32 v1 run directories under `runs/OE/stacked_texto{,__canon,__hyde,__rewrite}/` have no file newer than 2026-10-03 10:58:41Z (created 2026-10-01 to 10-03, commits `b314b92`, `d0621a1`, `7174392`, `d24e7c7`, `58e950f`, `d2db530`). No commit has touched `docs/synthetic-oe/results/S9/*.md` since `84a5029` (2026-10-03); the ten v1 tables on disk are CRLF (autocrlf checkout, `fig7_crossover.png` identical) and equal their `HEAD` blobs once CR is stripped — a line-ending phantom (H5), not a change. `git status` is clean under `docs/`, `src/`, `data/`, `logs/`.
- **Same queries, legitimate pairing.** `OE_stacked_texto.json` and `OE_stacked_texto_v2.json`: 4,998 records, same `item_key` order, every non-`text` field equal; `text` differs on exactly the 2,039 keys `OE_v2_changes.jsonl` lists for `stacked` (v1 text = `old`, v2 text = `new`, all 2,039). Dev (42 concepts, `SPLITS.md`): 2,521 queries, 1,183 changed, 1,338 unchanged; D-033 excludes 55 golds → **2,466 scored**, same mask, gold and concept on both versions (41 concepts). The generator's bootstrap labels carry no query-set name (`s9|T2|{arm}|{t}|{bin}|item`, `s9|Y2|{arm}|{t}|tf|item`, `s9|cmp|{arm}|{t}`; `boot_cluster` seeds `SeedSequence([20260917, crc32("cluster|"+label)])` and groups by sorted concept), and `paired_diff` pairs only when `clusters_key` (sorted concept set) and draw length agree. Recomputed: the pooled non-identity bins hold the same concept sets on v1 and v2 (B1 38, B2 37, B3 39, B4 39 concepts), so every paired interval in T2 and in the registered table rests on identical cluster sets. Coverage is computed on the untransformed text, so 530 dev stacked queries change coverage; 53 scored stacked queries leave B1 and none enter it.
- **Recomputed from `results_top100.jsonl.gz`** (tie-free, 1/|rank-1 tied set| when the gold is in it; concept draws by the generator's labels; numpy 2.2.2 on the host), every figure below exact to the table's 4 decimals:
  - T1 of the comparison, all 21 rows: `bm25_unigram` C **+0.0055 → +0.0057**, +0.0002 [+0.0000, +0.0007], 1 query moved, 0 unchanged-text; H **−0.0309 → −0.0321**, −0.0012 [−0.0044, +0.0004], 20 / 0; W −0.0012 → −0.0019, −0.0007 [−0.0044, +0.0010], 11 / 0. ColBERT C +0.0066 → +0.0070, +0.0004 [−0.0019, +0.0028], 72 / 0; H **−0.2102 → −0.2130**, −0.0029 [−0.0094, +0.0050], **395 moved, 8 unchanged-text** (all 8 on the untransformed side, S7 A8's two ColBERT runs); W **−0.0039 → −0.0089**, −0.0050 [−0.0204, +0.0102], **386 / 15** (8 untransformed side, 7 transformed side). `dense_es_hiiamsid` C +0.0024 [+0.0000, +0.0064]; W 104 moved; lexical maximum 31 (`bm25_unigram_params` H). ColBERT untransformed item Acc@1 on stacked 0.4128 → 0.4280 (profile T1) — exact.
  - Bins (scored, pooled over `resumen_u`, `single_texto`, `single_l2_texto`, stacked): **B1 1,746 → 1,693, B2 2,491 → 2,538, B3 1,040 → 1,046, B4 1,816 → 1,816** — exact (all 1,798 → 1,745 / 2,893 → 2,940 / 1,393 → 1,399 / 1,852).
  - Y2 `bm25_unigram` H: **−0.0226 [−0.0479, −0.0101] → −0.0247 [−0.0528, −0.0109]**, paired **−0.0021 [−0.0059, −0.0004]** — exact; and the other nine Y2 cells, the ten Y1 cells (all +0.0000 differences) — exact.
  - Y3, all ten fits: slopes, concept intervals, c* and the paired slope difference — exact, e.g. `bm25_unigram` H −0.4073 → −0.4088, c* 0.6207 → 0.6217; ColBERT W −0.2685 → −0.2527 (+0.0158 [−0.0199, +0.0539]), c* 0.6691 → 0.6551; `dense_es_hiiamsid` W −0.5686 → −0.5889 (−0.0203 [−0.0496, +0.0055]), c* 0.6964 → 0.7050; `bm25_unigram` W positive on both versions, no crossing in range: **9 of 10 in range on both**.
  - T2, all 84 cells: estimates, intervals and paired differences — exact (see F4 for which exclude 0).
- **Every figure the section quotes is in a generated table and quoted correctly**: the registered rows and c* values (`comparison.md`), the four T2 cells it names (`comparison.md` T2), the below-c* cells with their v1 counterparts (`crossover.md` A11 section, v2 and v1: `bge_m3_dense` H −0.0145 [−0.0395, −0.0040] vs v1 −0.0107 [−0.0372, +0.0024]; `dense_es_hiiamsid` W +0.0238 [−0.0091, +0.0552], query-level [+0.0108, +0.0374], +0.0000 [−0.0217, +0.0186] without the stacked base; ColBERT H 2 scored, ‡), the stacked T1 rows (`profile.md` l. 66–68: ColBERT W −0.0089 [−0.0301, +0.0070], fallbacks 0 / 2), T6 (`extraction.md`: 0.2157 → 0.2145, 0.6780 → 0.6764, lost axes 3,864 → 3,870, 31.4 % both — quoted, not recomputed), and the determinism figures in T2's and T1's headers. "44 of 44 unchanged": the registered table has 44 rows, all `reading moved: no`; `predictions.md` v1 and v2 differ only in Y2's n column (1,798 → 1,745); the only registered paired interval excluding 0 is Y2 `bm25_unigram` H. Y1, Z1, Z2, G1, G2, E1, E2: +0.0000 [+0.0000, +0.0000]. Finding 1's "no bin shows a gain" (tested arms under H), finding 2's "every B1 interval contains 0" (W) and known-wrong 1 hold on the v2 tables.
- **Generation caches (A14).** `OE_stacked_texto_v2__{hyde,rewrite}.jsonl` hold 3,704 lines each = S9's 2,521 + 1,183 (`gen_s9_v2.sh`: hyde 2,622 lines before the restart, rewrite 2,521; 3,704 after). Parsed, the first 2,521 lines of each equal S9's `OE_stacked_texto__{t}.jsonl` records, same order and same `cache_key`/`response`; the remaining 1,183 carry distinct `query_key`s that are exactly the changed dev queries, and none of their `cache_key`s is in S9's file. `before_seed.jsonl`: 266 lines, 165 with a key S9 holds (all 165 responses identical to S9's lines; not kept) and 101 for changed queries, which are lines 2,522–2,622 of the seeded hyde cache in order — as A14 says. Consequence checked on the query sets: for the 1,338 unchanged dev queries the transformed `text` is identical on v1 and v2 for C, H and W (1,338 of 1,338 each); for the 1,183 changed ones it differs on C and H for all and on W for 1,132 (51 rewrites coincide). Sidecars: same model digest `7cdf5a0187d5…`, ollama 0.17.7, options, prompt SHA (`ed5de490…` H, `6811f1a9…` W); rewrite fallbacks 2 on both versions, the same keys (`OEC050aa_syn_4811a1ed3f6b`, `OEC050ab_syn_b042df723dc0`); truncated 2 / 2. One line-ending note: the seeded part of each v2 cache was written CRLF (2,622 hyde, 2,521 rewrite lines) and the lines generated afterwards LF, so the seeded lines are S9's bytes plus a CR; `json.loads` tolerates it and the content is identical.
- **Determinism (A13).** `logs/S9/determinism_hyde_v2.json`: 97 of 100 identical, 0 unparsed, 0 truncated; `rewrite_v2`: 100 of 100. The 100 keys per transform are distinct, all in the changed dev set, seed 20261002, model/options/prompt as above; the three hyde mismatches are listed with both texts (no mojibake in the logs, caches or query sets; the non-ASCII is UTF-8 throughout).
- **The two generations' hashes.** `s9_gen1.sha256` (03:27Z, before `fc59fd4`) and `s9_gen2.sha256` (03:39Z, at it) list the same 13 files; 12 digests are equal and only `run_provenance.md` differs (`ec5763db…` → `ff683729…`). Disk and `65b7fd5` equal gen2.
- **Extraction cache.** `chain_s9.out`: `structured_llm_extract.jsonl` 16,853 lines before the registered extractor arm, 16,853 after it and after the key-tolerant arm (A7's no-growth check passed).

## Findings
### F1 — minor — the registered-tests table prints one n and concept count, the v2 side's, although Y2's population differs between versions
`comparison.md` "The registered tests" has single `n scored` and `concepts` columns, filled from the v2 cell (`y['n']`, `y['concepts']`). For the ten Y2 rows that is 1,693 / 38, while the v1 cell rests on 1,746 scored queries (same 38 concepts); the other 34 rows are the same population on both sides. A13 promises "n, concepts and stamps for both". T2 does print both n. What must change: the generator prints n (and concepts) for v1 and v2, or labels the column as v2's.

### F2 — minor — A14 was committed 49 s after the seeded generation it describes restarted
`chain_s9.out`: the restart from the seeded caches began 2026-10-18 23:42:09Z (`gen_s9_v2.sh` at `858d15c`, hyde cache 2,622 lines before); `before_seed.jsonl` was written 23:41:47Z; A14 was committed at `8c8fe18`, 23:42:58Z. Every A13 run came later (first 01:57:15Z), so A13's "recorded before any v2 run" holds for the runs; the amendment that governs the generation was recorded after the generation restarted. No figure is affected (the seeded lines are S9's, verified above). What must change: a dated row noting the order (seeding 23:41Z, restart 23:42:09Z, A14 committed 23:42:58Z), so the record does not read as if A14 preceded the procedure it records.

### F3 — minor — "`bm25_unigram` at `4f56a39`, S7 A9" names one of three reference runs at that commit
The section: "the untransformed reference runs are S7 A8's (`8d1ffd2`; `bm25_unigram` at `4f56a39`, S7 A9)". The stamps on `stacked_texto_v2`: `bm25_unigram`, `bm25_unigram_params` and `tfidf_unigram_phrases_replace` at `4f56a39` (S7 A9: "the three runs before them … are clean at `4f56a39` and stay"); ColBERT, `bge_m3_dense`, `dense_e5`, `dense_es_hiiamsid` and `rules_valuenorm` at `8d1ffd2`. `comparison.md` Sources and `run_provenance.md` print this correctly. What must change: the sentence names the three lexical arms at `4f56a39`.

### F4 — minor — the list of T2 cells whose v2 − v1 interval excludes 0 is incomplete
The section: "The T2 cells whose v2 − v1 interval excludes 0 are a few thousandths: `bm25_unigram_params` H in B2 …, `dense_e5` W in B2 …, `dense_es_hiiamsid` W in B2 … and ColBERT C in B1". At the table's own precision `bm25_unigram_params` C B1 also excludes 0 (+0.0002 [+0.0001, +0.0004]), and at full precision so do `bm25_unigram` C B1 (+0.000107 [+0.000035, +0.000205], printed [+0.0000, +0.0002]) and `bm25_unigram_params` C B2 (−0.000085 [−0.000213, −0.000007], printed [−0.0002, −0.0000]); the Y2 `bm25_unigram` H cell is the fifth and is named elsewhere in the section. The omitted three are ten-thousandths and change no reading; the sentence's "a few thousandths" is right for the ones it names. What must change: the enumeration either lists the eight cells (or the four of order 10⁻³ and says the rest are ≤ 2 × 10⁻⁴), or stops claiming to be the list.

### F5 — minor — the extractor arm's lines for the changed stacked queries were generated in S11 A7's batch, not this one
`logs/v2/run_v2_s9.sh` (header): "`structured_pipeline_llm_valuenorm__OE` on `stacked_texto_v2` (the extraction cache grows by the changed queries)". `chain_s9.out`: 16,853 lines before and after that run — nothing was generated, because S11 A7's K0 run on `stacked_texto_v2` (23:00:48Z, same `structured_llm_extract.jsonl`, same prompt) had already written them. The report section and `extraction.md` are correct as written (they quote S11's determinism log); only the script's comment and, by omission, the provenance of T6's v2 generations are off. What must change: a line in the section or T9 saying the extractor's changed-query generations were produced by S11 A7's batch and read here from the shared cache.

## Unverifiable
- That gen1 and gen2 "differ only in T10's generator line": gen1's `run_provenance.md` (`ec5763db…`) is not stored (it was overwritten and never committed; `fc59fd4` has no `results/S9/v2/`), so only the hash listing (12 of 13 equal) can be checked, not the content of the one difference.
- That the 25 runs are first-time runs beyond what the artefacts show: the guard refuses an existing directory and `chain_s9.out` has no refusal, `chain_b_s9.out` ends during the first hyde generation before any run; a directory removed between the two chains would leave no trace.
- T6's v2 figures (0.2145, 0.6764, 3,870 axes) were checked against `extraction.md` and not recomputed: the tiers need the pipeline modules and the extraction cache.
- The bootstrap draws were reproduced with numpy 2.2.2 on the host against the container's 1.26.4; every interval recomputed with the generator's labels matched to 4 decimals (and the paired ones to 6), so the RNG stream is the same, but the pinned stack was not run.
- The regeneration check's "100 seeded changed queries per transform" — the seed 20261002 and the 100 keys are logged; I did not re-draw the sample from the generator's code.

---

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
