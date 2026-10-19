# Sprint S14 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-10-19 · report `3f08977` (HEAD `662592a`) · design frozen `dd419a1`, A1 `d9c4d62` · runs `runs/OE/bt_texto/` (21), `runs/OE/stacked_texto_v2/`, `runs/OE/texto/`, `runs/OE/texto_u/` · tables `docs/synthetic-oe/results/S14/` (generator `src/utils/build_results_s14.py`, unchanged since `2d0b51a`)

I recomputed every number I checked from `results_top100.jsonl.gz` with my own scripts, using the tie-free scoring (1/|rank-1 tied set| when the gold is in the set) and the D-033 exclusions. All of them reproduce. No comparison mixes samples, and the design has not changed since the freeze (`git diff dd419a1..HEAD -- SPRINT_S14_DESIGN.md` is empty). The findings are about sequencing that was not declared, and about prose that says more than the tables support. F1–F3 should be fixed before `done`.

## Verified
- **Population.** I re-derived the following from the data files. 2,331 dev BT queries on 40 concepts. 2,332 STACKED-P v2 dev leaves, and the only one without a BT query is `OEB160a`. Every BT gold has exactly one query. 55 D-033 golds, which leaves 2,276 item-scored queries on 38 concepts. SHA of the sorted key list is `8d77e31e977b080d`, the same as in A1. On all 2,331 queries the gold in the BT run equals the query file's gold, and the gold of the paired STACKED-P v2 query in the SP run also equals it, for every arm I checked (12).
- **Item Acc@1, tie-free, on the 2,276 queries** (BT / STACKED-P v2 / identity). These match T1 and the report. bm25 0.1641/0.1106/0.9007; ColBERT 0.6785/0.4395/0.9992; bge_m3_dense 0.4534/0.1779; dense_e5 0.3647/0.2008/0.5167; hiiamsid 0.4319/0.1182; K2 0.8983/0.7514/0.8783. Oracles: tfidf_phrases_replace 0.9809/0.1898, oracleparams 0.9666/0.1744, bm25_params 0.6872/0.1840. Parent level: bm25 0.9979→0.4393, ColBERT 1.0000→0.9912.
- **As-run Acc@1 on all 2,331 queries** equals `metrics_dual.json` (overall, item and parent) to 10 decimals for all 12 arms. Example: ColBERT 0.6512226512 / 0.9914199914.
- **B2.** K2 − ColBERT is +0.2197 with concept interval [+0.1511, +0.2594]. I reproduced the interval exactly with the generator's seed scheme. A plain concept bootstrap with an independent seed gives [+0.1525, +0.2603]. Holm p is 0.0046 in a family of 23, so the reading is *supported*. The STACKED-P v2 figure on the same leaves is +0.3118 [+0.1999, +0.3649].
- **Stage P.** I recomputed it from the five `stacked_texto_v2` runs, which were recorded by `results_sha256` before the sprint. All ten estimates, intervals and Holm values match `pairs_stacked_p.json`. P is the same 7 pairs, with the same orientation. With an independent bootstrap seed none of the ten changes category.
- **B1 = P.** The rows in `predictions.md` (lines 13–19) are exactly `P` from `pairs_stacked_p.json`, in the same orientation, with nothing added or dropped. `load_fixed_pairs` re-derives P and asserts it, including the SP results SHA.
- **Holm families.** One per reading, each of 23 tests (|P| 7 + B2 1 + B3 10 + B4 5), as the design specifies. I recomputed the tie-free, as-run and F-BT-1-free readings independently and all 23×3 categories match T8 and T10. That gives 21/23 supported. The three non-robust readings are dense_e5−bm25, dense_e5 W1 and dense_e5 W2. The B1 verdict reads *partly preserved* tie-free and as run, and *preserved* on the F-BT-1-free reading.
- **Oracle arms are in no test.** `evaluate()` builds rows only from `BASE5` plus K2. `ORACLE` contains bm25_params, tfidf_phrases_replace, rrf_params and oracleparams, and none of them is in P, B1–B4 or any Holm family.
- **Runs.** All 21 runs stamp `code_dirty: false`, split `dev`, 2,331 queries and query set `ee8c1d21…`. That equals `sha256(OE_bt_texto_feats.parquet)`. `check_run_inputs.out` reports 578 of 578 runs resolving.
- **Family cache.** The npz SHA is `34a6ed20…` and equals the meta file. The meta's `reference_results_sha256` (`e87c42b0…`) equals the BT ColBERT run's results file. The exact check is 0 mismatched of 194,998. Determinism is 100/100.
- **Generations.** `s14_gen1.sha256` is identical to `s14_gen2.sha256`, and both equal the current files and the committed tree. Nothing has been edited by hand.
- **Identity digests and H5.** The ColBERT and dense identity runs use `75477221` (`OE_long_norm`), which earlier audits (S2, S11) found to be the same IDs. The S11 identity config SHAs (`7f9db9ab`/`b6a5bbd9`/`f0dd7e8b`) are the CRLF encodings of the current LF configs `cf80f290…`. I checked this by re-encoding: it is an H5 phantom.
- **Strata.** The figures the report quotes match the tables: fraction bins, pure BT, coverage B2, OEB, label_added and the F-BT-1 split (BM25 0.0357/0.4113; e5/hiiamsid 0.2864/0.3992).

## Findings

### F1 — major — P was fixed after the freeze and after 18 BT runs existed, which the frozen design forbids; the report says "no deviation"
The frozen Entry state says "P … is computed and listed, before the freeze". Work item 4 says "`--fix-pairs`, run before any BT run exists or is read".

The artefacts give this timeline:
- freeze `dd419a1` at 07:13:15Z;
- BT base batch 07:14:44–07:40:56Z (`run_s14_base.out`), 18 runs, each followed by `metrics.ipynb`;
- `logs/S14/metrics__bt_texto__*.ipynb` contain rendered Acc@1 tables;
- generator `2d0b51a` at 07:42:19Z;
- `pairs_stacked_p.*` written at 07:43Z;
- A1 at 07:44:46Z.

A1 and the report ("Deviations … None in substance; the design allows the runs to be made first") present this as compliant. The design allows the runs before the freeze, but it also requires P before the freeze.

In substance P is safe. It is a deterministic function of SP runs that predate the sprint, and it is robust to the bootstrap seed (see Verified). The deviation still has to be declared. Required: an A2 amendment recording the actual order, the "Deviations" section corrected, and EC4 marked as below.

### F2 — major — "every pair with a wider margin on BT" is false for 2 of the 6 pairs
The claim appears in report lines 36–37, 94 and 106–107. T2 (`contrasts.md` lines 17 and 19) shows ColBERT − bge_m3_dense going from +0.2616 on STACKED-P to +0.2251 on BT, and ColBERT − hiiamsid from +0.3214 to +0.2466. Both margins are narrower on BT. Only the three pairs against BM25 and ColBERT − e5 widen. Required: correct all three places.

### F3 — major — the losses are attributed to the F-BT-1 token, but that token cannot be separated from four concepts
Report lines 37, 44–45, 70–71, 94 and 102–104 say "carried by the F-BT-1 queries", "the damage is F-BT-1's" and "one systematic token substitution … is enough".

- **The token and the concepts coincide.** F-BT-1 covers every dev query of OEB020, OEB030, OEB230, OEB290 (and OEB130). Those concepts have 0 non-F-BT-1 queries.
- **The same leaves fail without the token.** On those leaves STACKED-P v2, which is a different rendering, gives BM25 item 0.0159 (BT 0.0357) and BM25 parent 0.0781 (BT 0.2250), against 0.2930 and 0.6735 on the other leaves. The leaves fail under both renderings, so the token is not shown to be the cause.
- **"Holds without the F-BT-1 queries" is too strong.** The report says this of dense_e5 − hiiamsid at +0.0206 [−0.1122, +0.1273]. That is a positive point estimate on a 33-concept population, not "holds".

The report's own known-wrong #4 concedes the confounding, which contradicts these sentences. Required: describe the subset as concept-confounded, and drop the causal wording and "holds".

### F4 — minor — directional claims without interval support
- **K2 and its identity.** "K2's own accuracy is higher on BT than on its identity" and known-wrong #3 rest on δ_BT +0.0200 [−0.0506, +0.0610]. The 0.5-bin gain (+0.0619, concept CI [+0.0000, +0.1061]) and the OEB gain (+0.0545, [−0.0076, +0.0957]) are quoted without their intervals.
- **STACKED-P ordering.** "bge_m3_dense > dense_es_hiiamsid" on STACKED-P (line 38) is not supported (Holm 0.1308).
- **The B1 rule is misquoted.** The parenthetical at line 44 quotes the rule for *preserved* as the reason for *partly preserved*.

### F5 — minor — the S11 arms' identity is `texto_u`; the frozen design says `texto`, and there is no amendment
The frozen design gives the identity as "each arm's own `texto` run" and never mentions `texto_u`. `runs/OE/texto/` holds no K2/R2/F1 run, and the generator uses `IDENT_S11 = "texto_u"`. Report line 132 says "as the design states". No registered test is affected: B2 uses no identity, and B3/B4 cover only the five base arms. The K2 δ and the T1 rows for K2/R2/F1 do depend on it, and so does the H5 config-digest phantom on those identity runs, which S14 does not state. Required: an amendment and a header note.

### F6 — minor — the F-BT-1 definition includes 5 false positives
The definition (`build_results_s14.py:188`, `tests/test_intake_s14.py:156`) is: the substring «de hormigón» is in the query and «hormigonada» is in the gold. It catches all 5 OEB130$ dev queries. Those queries keep «canalización hormigonada», and their «de hormigón» is the gold's own «paramentos de hormigón». The genuine count is 1,493 on 4 concepts, not 1,498 on 5. The intake test asserts 1,498 using the same definition, so it is circular. The F-BT-1-free reading drops OEB130$ for no reason.

### F7 — minor — T3 mislabels which rendering each row is
`build_results_s14.py:597–598` overwrites `lab` before printing it, so the "rendering" column of `method.md` (lines 11–22) prints "B2"/"T3" instead of "BT"/"STACKED-P v2". Row pairs can only be told apart by their accuracy values. Fix the generator and regenerate.

### F8 — minor — stamps record HEAD when a run ends, not when it starts
- **K2.** The run started at `d9c4d62` (07:53:16Z, `run_s14_s11.out`) but stamps `6a0effb`, which was committed at 08:01:31Z during the 2,512 s run.
- **Family cache.** It was started at `2d0b51a` and its meta stamps `d9c4d62`.

There is no effect: `git diff --stat d9c4d62..6a0effb -- src configs` is empty, and A1 touched only docs. Even so, the stamp misattributes the code. The report says "two commits moved HEAD"; there were four (`2d0b51a`, `d9c4d62`, `fd475c6`, `6a0effb`).

### F9 — minor — the H8 caveat is not stated anywhere in S14
Design caveat (v) and the Risks row ("comparisons across runs state it") require it. `grep H8` over `results/S14/*.md` and the report returns 0 hits. It applies to B4 and T1's δ_SP for ColBERT and the arms built on it (BT and SP are separate encodings). The size measured in S11 A11 (8 tie-free hits on 1,287 queries) is negligible next to effects of 0.2 or more, but the design requires it to be stated in the table headers.

### F10 — minor — EC3's "n excluded … both intervals on every contrast" is not met in two tables
`contrasts.md` has no n-excluded column, and its STACKED-P side prints only the concept interval. `method.md` has no n-excluded column either. In both, the count appears only in the population header.

## Unverifiable
- **Whether a BT result was read before P was fixed.** BT Acc@1 tables existed on disk in `logs/S14/metrics__bt_texto__*.ipynb` from 07:14Z, before P was written at 07:43Z. Mitigation: P reproduces exactly from the pre-sprint runs.
- **Whether T1–T11 were written without sight of BT figures.** The generator `2d0b51a` was committed 80 s after the base batch finished.
- **Which 2 tests were skipped in `pytest_close.out`.** The log is in quiet mode, so I cannot confirm that the OEB fixture (`tests/test_golden_fixture.py`) or `test_intake_s14.py` were among the passed tests. The totals are 2,150 passed, 2 skipped, 1 xfailed.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1a. Intake tests committed | yes | `tests/test_intake_s14.py`, 8 tests, `23a162f` |
| 1b. Intake tests passing | unverifiable | Suite: 2,150 passed, 2 skipped. The quiet log does not name the skipped tests. |
| 1c. Entry-state counts re-derived | yes | I re-derived 2,331/40, 2,332, `OEB160a`, 55/2,276 and 1,498. The 1,498 is only correct under the substring definition (F6). |
| 2. 21 clean dev runs stamped `ee8c1d21…`; cache 0 mismatched; regeneration logged; inputs resolve | yes | `run_meta.json` ×21; cache meta and SHAs; `determinism_extract.json` 100/100; `check_run_inputs.out` 578/578 (stamp timing: F8) |
| 3a. T1–T11 and Fig. 9 byte-identical across two generations; prose guard | yes | gen1 = gen2 = tree; `test_generated_prose.py` covers `build_results_s14.py` |
| 3b. n scored, n excluded, concepts and both intervals on every contrast | no | F10 (`contrasts.md`, `method.md`) |
| 4a. P computed from the S7 A8 runs on the paired leaves and listed with date and run IDs | yes | A1; I recomputed P |
| 4b. P fixed before the first BT run was read | unverifiable | F1. The design's stricter "before the freeze" and "before any BT run exists" are **not met**. |
| 4c. B1–B4 tie-free, as run and F-BT-1-free, one Holm family of 23 per reading | yes | I recomputed it (Verified) |
| 5. The report states the B1–B4 verdicts, the strata and what BT reproduces | yes | Overclaims in F2–F4 |
| 6a. Full suite passes | yes | `pytest_close.out` |
| 6b. OEB fixture passes | unverifiable | Quiet log |
| 6c. Audit in a fresh session passes | yes, with findings | This audit; F1–F3 to be resolved before `done` |
