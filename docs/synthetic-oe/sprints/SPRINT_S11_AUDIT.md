# Sprint S11 — audit of amendments A7–A9 (v2 re-run)

**Verdict:** PASS WITH FINDINGS (1 major, 6 minor)
**Audited:** 2026-10-19 · report `8c8fe18` (section "v2 re-run (A7–A9, 2026-10-18)") · results `docs/synthetic-oe/results/S11/v2/` @ `8c8fe18` (generated at `858d15c`, `src/` clean; the eight `.md` blobs and `figures/fig8_two_stage.png` at `8c8fe18` equal `logs/v2/s11_gen1.sha256` byte for byte; the only working-copy change is the generator-commit line of `run_provenance.md`, the implementer's second generation) · runs `runs/OE/{stacked,single,dose,isolated}_texto_v2/structured_pipeline_{llm_keytol_hard,llm_keytol_hard_colbert,llm_keytol_soft_colbert,rules_canon_soft_colbert,colbert_in_concept}__OE/` (20), references `bge_m3_colbert__OE`, `dense_e5__OE`, `bm25_unigram__k1-0.60__b-0.35__OE`, `structured_pipeline_rules_valuenorm__OE` on the same four sets, archive `runs/_archive/dirty/2026-10-18/`, caches `index/OE/_colbert_family/*_texto_v2.{npz,meta.json}`. Recomputation script (auditor's, read-only): `C:\Users\cesar\AppData\Local\Temp\claude\D--Users-cesar-Dev-Phd-bc3cat-retrieval\f885e42f-130d-4c1d-8931-29cea1cfa390\scratchpad\recompute_s11_v2.py`.

## Verified
- **Stamps of the 20 runs.** All 20 `run_meta.json`: `code_dirty: false`, `split: dev`, `queries` = 2,521 / 2,206 / 1,640 / 2,952; K0 × 4 at `8d1ffd2`, K1 K2 R2 F1 × 4 at `858d15c`, as the section states. `query_set_sha256` of each run equals the SHA-256 of `data/processed/OE_<set>_v2_feats.parquet` on disk (`977d40b9…`, `03496b0b…`, `ac0cb6a5…`, `35de7967…`); the `.json` digests in T9 (`bc1ed968…`, `b3c58fcb…`, `8becd49a…`, `95c0c2ed…`) also match disk. The 16 reference runs on the v2 sets are clean, dev, at `8d1ffd2` (stacked `bm25_unigram` at `4f56a39`, S7 A9's surviving batch-1 run).
- **`retriever_provenance` (A8).** Every K0/K1/K2 run carries `llm.model_digest ac896e5b…` (equal to both determinism logs), ollama 0.17.7, options `{temperature 0, seed 20260915, num_predict 256, num_ctx 4096}`, `prompt_template_sha256 bdc20c46…` and `prompts_py_sha256 6dcc3f27…`. I recomputed both from the git blobs at `858d15c` and `8d1ffd2`: the file digest is `6dcc3f27…`; the SHA-256 of `build_extraction_prompt`'s source lines (`inspect.getsource` form) is `bdc20c46…`. Every K1/K2/R2/F1 run names its own base's family file and its digest (`stacked 5715b765…`, `single cd65cf0d…`, `dose 84d95ee6…`, `isolated 3a762871…`); each equals the SHA-256 of the `.npz` on disk and the `npz_sha256` in its `meta.json`. K0 carries no family block (it has no ColBERT order) — correct. R2 carries `canon.corpus_sha256 02a2c270…` = `OE_texto.json` on disk.
- **Family caches (A2 check).** The four v2 `meta.json` report `mismatched: 0`, `max_abs_diff: 0.0` (compared 214,496 / 180,553 / 125,582 / 218,044), built at `8d1ffd2` from the v2 `bge_m3_colbert__OE` runs; each `reference_results_sha256` equals the reference run's `results_top100.jsonl.gz` on disk; Stage-1 candidates from the v2 `dense_e5` runs only, as A7 states.
- **Archive (A9).** `runs/_archive/dirty/2026-10-18/` holds the five S11 attempts (`stacked_texto_v2/{llm_keytol_hard_colbert, llm_keytol_soft_colbert}` without `run_meta.json`; `stacked_texto_v2/{rules_canon_soft_colbert, colbert_in_concept}` and `single_texto_v2/llm_keytol_hard_colbert` with `code_dirty: true` over `src/retrievers/structured_pipeline.py` at `8d1ffd2`, created 23:16:43–23:17:56Z) plus S7 A9's two (`bge_m3_colbert`, `bge_m3_dense` on stacked, `4f56a39`, dirty). `sha256sum -c SHA256SUMS`: all 44 files OK. No file under `results/S11/v2/` mentions `_archive`; every run T9 reads is the clean one.
- **Amendments recorded before the runs.** A7 committed at `4f56a39` (2026-10-18 19:54:58Z), A8 at `e5dd940` (20:23:40Z); the caches were built from 22:00:13Z, the first K0 run saved at 23:00:48Z. A9 committed at `858d15c` (23:18:53Z, the fix commit); the clean phase B restarted at 23:19:11Z (`logs/v2/chain_b_s9.out`), first run saved 23:19:45Z. The batch script's guard refuses existing run directories, so the restart could only proceed after the archive move.
- **One sample.** For each of the four bases, v1 and v2 hold the same dev keys in the same order, the same gold and concept per key, and the same item-scored mask (stacked 2,466 scored / 55 excluded D-033 golds; single 2,176 / 30 (29 D-033 golds + S4's P7 query); dose 1,640 / 0; isolated 2,952 / 0). The dev queries whose `text` differs between the two JSONs are exactly `OE_v2_changes.jsonl` ∩ dev: 1,183 / 145 / 337 / 214, the counts the H8 table prints. The paired draws therefore rest on identical cluster sets and identical bootstrap labels (same `evaluate` label, same `SeedSequence([20260917, crc32(label)])`), which is what `v2_variant.paired_diff` requires.
- **Recomputed from `results_top100.jsonl.gz`** (tie-free = 1/|rank-1 tied set| if the gold is in it; K0's tier decoded from its score encoding — matched leaves 1.0, 0.9999, …, rest of family 0.5, 0.4999, … — with an empty matched tier scored as the whole family of Stage 1's concept, 1/`num_items`; the decode reproduces every K0 cell in `profile.md`/`comparison.md` to 4 decimals):
  - A1 stacked: v1 K2 0.7271 − ColBERT 0.4128 = **+0.3143** [+0.2112, +0.3606]; v2 0.7247 − 0.4280 = **+0.2967** [+0.1979, +0.3446]; paired v2 − v1 **−0.0176 [−0.0301, −0.0029]** — exact.
  - T4 `template_paraphrase` (295 scored, 40 concepts): **+0.2403** [+0.1448, +0.3239] → **+0.2219** [+0.1306, +0.3046]; paired **−0.0184 [−0.0306, −0.0049]** — exact.
  - A7 pooled ladder (D-053 stratified-leaf, 328 leaves): +0.2758 [+0.2262, +0.3232] → +0.2666 [+0.2172, +0.3146]; paired −0.0092 [−0.0179, −0.0007] — exact.
  - K2 on the ladder: **0.7850 → 0.7758**, δ −0.0091, concept-clustered CI [−0.0168, −0.0014] — exact (see F5 on which bootstrap this is; the D-053 stratified-leaf paired interval is [−0.0171, −0.0018], same sign).
  - The 337 repaired rung queries: K2 **0.8427 → 0.7982**, K0 **0.7363 → 0.7016** — exact (see F2 for ColBERT).
  - H8 floor: unchanged item-scored queries whose tie-free hit moved — K0 0/0/0/0 and K2 0/0/0/0 on stacked (1,287) / single (2,033) / dose (1,303) / isolated (2,738); R2 8 on stacked, 0 elsewhere; F1 and ColBERT 8 on stacked — exact.
  - Also exact: R2 stacked 0.4779 → 0.4867, +0.0088 [+0.0032, +0.0127]; ColBERT stacked +0.0152 [+0.0040, +0.0223]; K2 stacked −0.0024 [−0.0098, +0.0034]; A1 pooled L1 +0.0445 on both versions (n 1,037); the repaired stacked queries K2 0.6877 → 0.6826, K0 0.6139 → 0.6149, R2 0.3887 → 0.4081.
- **Every figure in the section appears in a generated table** (`comparison.md`, `contrasts.md`, `predictions.md`, `types.md`, `profile.md`, `run_provenance.md`), with the one exception in F2.
- **Resolution rule.** The design (`SPRINT_S11_DESIGN.md` l. 162) reads *established on dev* iff A1 holds on both populations and A7 holds pooled; `resolution()` implements exactly that; on v2 A1 stacked, A1 pooled L1 and A7 pooled are all *supported* under Holm (0.0022, 0.0024, 0.0022), so "established on dev" on both versions and "11 of 11 readings unchanged" are correct.
- **Determinism.** `logs/S11/determinism_extract_v2.json`: 100 of 100 identical, 0 unparsed, 0 truncated; the 100 keys are 25 per set and all are in `OE_v2_changes.jsonl`.
- **Line endings (H5).** The five S11 configs are LF on disk and in every blob (`.gitattributes eol=lf`); content identical between `4fe109d` and `858d15c`. The v1 runs stamped the CRLF digest of each YAML (K0 `51654ff8…`, K1 `d7bbd05f…`, K2 `7f9db9ab…`, R2 `b6a5bbd9…`, F1 `f0dd7e8b…`) and the v2 runs the LF digest (`094557d5…`, `546955de…`, `cf80f290…`, `ad1b9094…`, `8d37d1d4…`); re-encoding the LF file as CRLF reproduces each v1 digest exactly. This is the phantom `DATASET_DEFECTS.md` H5 ("third face") records; "configs unchanged" (A7) holds. `prompts.py` is LF everywhere, so the prompt digests are not affected. The generated tables are LF on disk and equal their committed blobs. Nothing else I found is a line-ending artefact.

## Findings
### F1 — major — "about a seventh of the stacked advantage measured on v1 was the slot defect" does not follow from the figures
The report (Finding 1 restated, and the commit message of `8c8fe18`) says about a seventh of K2 − ColBERT on stacked was the slot defect. The tables and my recomputation give v1 +0.3143, v2 +0.2967, difference −0.0176: 0.0176 / 0.3143 = 0.056, about one eighteenth (5.6 %), not one seventh (14.3 %). No other cell yields a seventh either (T4 `template_paraphrase` 0.0184 / 0.2403 = 7.7 %; A7 pooled 0.0092 / 0.2758 = 3.3 %; on the 1,179 repaired stacked queries (0.3678 − 0.3301) / 0.3678 = 10.3 %). The sentence is bound for the manuscript. It must be restated as "about one part in eighteen (5.6 %, −0.0176 [−0.0301, −0.0029])" or in absolute terms; the commit message cannot be amended but the report and the manuscript can.

### F2 — minor — ColBERT's 0.5091 → 0.5092 is quoted beside the 337 repaired rung queries but is the all-1,640 figure
The report: "on its 337 repaired rung queries 0.8427 → 0.7982 (K0 0.7363 → 0.7016) while ColBERT holds 0.5091 → 0.5092". K2's and K0's figures are the H8 table's 337-query cells; ColBERT's are `comparison.md` T1 on all 1,640 ladder queries (the H8 table has no ColBERT row). On the 337 repaired queries ColBERT reads 0.3700 → 0.3704 (recomputed; in no generated table). The point — ColBERT does not move — holds on both populations, but the sentence presents a figure on a population it was not computed on. Restate ColBERT's figure as "on all 1,640" or drop it.

### F3 — minor — T9 (v2) says the runs' `run_meta.json` carry neither the prompt SHA nor the model digest; the 20 v2 runs do
`run_provenance.md` (v2) prints `prompt_source()`'s fixed sentence: "Recorded here, not in the runs' `run_meta.json`, which carry neither the prompt SHA nor the model digest." The 12 LLM runs it reads on the v2 bases carry both (A8); only the `texto_u`/`resumen_u`/`single_l2_texto` runs do not. The generated table contradicts the report section it supports. Two further loose ends under the same name: T9 labels the whole-file digest `6dcc3f27…` as "(`src/pipeline/prompts.py`, `build_extraction_prompt`)", while the stamps call the function-source digest `bdc20c46…` the "prompt template SHA-256" — two digests under one name; and `determinism_extract_v2.json` has `prompt_sha256: null`. The generator text should distinguish the runs that carry the stamp from those that do not, and print both digests with their meaning (a `src/` change, to land between batches).

### F4 — minor — A9's account of the five archived attempts does not match the archive or the batch log
A9: one run failed at save (`llm_keytol_hard_colbert` on stacked), three saved dirty, "a fourth was killed mid-way", "all five are moved". `logs/v2/chain_s11_s9.out` (l. 189–229) and the archive show two save-time failures (`llm_keytol_hard_colbert` 23:14:33Z and `llm_keytol_soft_colbert` 23:15:12Z on stacked, both with a complete 2,521-line `results_top100.jsonl.gz` and no `run_meta.json`), three dirty saves (rules_canon 23:15:51Z, colbert_in_concept 23:16:47Z on stacked; hard_colbert 23:17:24Z on single), and a sixth attempt (`llm_keytol_soft_colbert` on single, started 23:18:00Z) that was killed and left nothing to archive. Five directories are archived, as A9 says, but they are 2 + 3, not 1 + 3 + 1. The archive directory is also shared with S7 A9's two runs under one `SHA256SUMS`, which A9 does not say. No figure is affected (no archived run is read). A correcting row is due (A9 cannot be edited).

### F5 — minor — the ladder interval the report quotes for K2 (−0.0091 [−0.0168, −0.0014]) is a concept-clustered bootstrap over 4 clusters, which D-053 set aside for the E3 sets
`comparison.md` T1 applies `boot_cluster` by concept on every base, including `dose_texto` and `isolated_texto` whose dev ladder has 4 concepts — the interval D-053 says "cannot support any reading" there. The registered A7 rows use D-053 correctly; the T1 and H8 sections do not. Recomputed with D-053's concept-stratified leaf weights on the same per-query differences, K2's interval is [−0.0171, −0.0018] (K0 [−0.0160, +0.0011]; ColBERT [−0.0059, +0.0062]), so the sentence's sign survives and no reading changes. The comparison generator should print D-053's interval on the E3 bases, or label the 4-cluster one as resting on 4 clusters, as D-053 requires.

### F6 — minor — "K2 giving a little back" on stacked is directional without its interval, and the interval spans zero
"The shrinkage is ColBERT recovering, and K2 giving a little back. On stacked, ColBERT goes 0.4128 → 0.4280 while K2 goes 0.7271 → 0.7247". ColBERT's change carries +0.0152 [+0.0040, +0.0223] in T1; K2's is −0.0024 [−0.0098, +0.0034] and K0's +0.0005 [−0.0095, +0.0075] — neither distinguishable from zero on stacked. On the ladder K2's −0.0091 does exclude zero (both bootstraps), so the "a little worse" reading is supported there and only there. The stacked clause should carry K2's interval and be read as not distinguishable from zero; the shrinkage on stacked is ColBERT's recovery alone, which is what the tables show.

### F7 — minor — the v2 family caches stamp `bge_m3_api: http://host.docker.internal:8800`, not the address A1 records
S11 A1 (2026-10-04) states the server is reached at `http://172.17.0.1:8800` because `host.docker.internal` did not resolve from `bc3cat-s3`, "the address is stamped in each cache's meta.json". `logs/v2/run_v2_s11.sh` exports `host.docker.internal` and the four v2 `meta.json` stamp it; the exact check passed (0 mismatched), so the server answered. The record is inconsistent, not the figures; a row noting the address change is due.

## Unverifiable
- That the 20 runs are "first-time runs": the batch guard refuses an existing directory and the log shows no refusal, but a run directory removed before the restart would leave no trace. Consistent with the archive timeline; not provable from the artefacts.
- That the LLM arms are blind on v2 ("no LLM has seen v2"): the extraction cache is keyed on the prompt text, and the determinism log shows generation on changed queries, but which cache lines were written when is not recorded per line; I did not open the shared cache during a running batch.
- K0's tie-free hits were recomputed by decoding the run's score encoding (matched tier 1.0, 0.9999, …; rest 0.5, 0.4999, …), not by re-running `s11_stages.decompose` (which needs the pipeline modules and the LLM cache). The decode reproduces every K0 cell in `profile.md` and `comparison.md` to 4 decimals; one stacked query has a 100-leaf matched tier truncated at the top-100, which the design's tier could size differently (effect < 1/2,466 on any mean).
- The bootstrap intervals were reproduced with numpy 2.2.2 on the host against the container's 1.26.4; every interval I recomputed with the generator's labels matched to 4 decimals, so the RNG stream is the same, but I did not run the pinned stack.

---

*The record below is the sprint's earlier audit(s), kept as written.*

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
