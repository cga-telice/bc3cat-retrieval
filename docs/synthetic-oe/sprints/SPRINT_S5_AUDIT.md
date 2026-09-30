# Sprint S5 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-09-30 · report `8105135` (`docs/synthetic-oe/sprints/SPRINT_S5_REPORT.md`, HEAD `a9a97ab`) · design frozen at `432b39e` · runs `runs/OE/{texto,single_texto}/structured_pipeline_{rules,rules_valuenorm,oracleparams_valuenorm}__OE`, the reference arms `runs/OE/{texto,single_texto}/{bm25_unigram,bm25_unigram_params}__k1-0.60__b-0.35__OE` and `bge_m3_colbert__OE`, `runs/_archive/S2`

## Verified
- **Regeneration.** I ran `build_results_s5.main()` with `OUT` pointed at a scratch directory. All 7 tables (T1–T7) came out byte-identical to `docs/synthetic-oe/results/S5/`.
- **Headline.** Q1 pooled L1, `rules_valuenorm` − `bm25_unigram` = −0.0525 [−0.1338, −0.0105], 39 concepts, Holm p 0.0144, contradicted. Traced to `OE/single_texto/structured_pipeline_rules_valuenorm__OE` (config `e9e2acdc`, `26ed9ff`, query set `e5b79ae4`) × `OE/single_texto/bm25_unigram__k1-0.60__b-0.35__OE` (`ec943fef`, `31bf1a1`, `e5b79ae4`). T6 matches.
- **Every other T6 row quoted in the report matches:** −0.1589, −0.0177, −0.0393, −0.1201, +0.0166, and the DiDs +0.0656 / +0.0817 / +0.0903 with their intervals and Holm p. The tally of 2 supported, 4 not supported and 3 contradicted is correct.
- **T5 values quoted in prose match:**
  - ColBERT −0.5528 [−0.6008, −0.4721]
  - oracle L2 +0.2592 and L3 +0.3403
  - L1 identity Δ −0.1181 [−0.2349, +0.0966]
  - vs `bm25_unigram_params`: −0.1512 [−0.2829, −0.0639] and DiD +0.0975 [−0.1327, +0.2360]
  - as run −0.0183 [−0.0935, +0.0285]
  - P8 −0.0291 → −0.0295
- **T1 and T4 values match:**
  - T1: 0.8136 as run, 0.7532 tie-free, 0.7085 unique gold; the oracle's figures are 0.9975.
  - T4: 0.0039 and 0.0513; median 4, IQR [3, 8]; 11 on `num_to_text`; decimal artefact 9 / 5.
- **T2 values match:** 0.2988, 0.1614, `reorder` +0.0000, oracle L2 +0.0000 and L3 −0.0118.
- **Provenance.**
  - All 6 structured `run_meta.json` show `26ed9ff`, `code_dirty: false`, `split: dev`. They were created at 00:31–00:34 UTC, after that commit.
  - The re-hashed config SHA-256s (a3b08f47, e9e2acdc, b6e3031c, ec943fef, c695c126, 130f0fc4) and data digests (643f1a72, e5b79ae4, 75477221, b3cfcad4) all match T7.
- **One sample.**
  - `contrast()` raises if the two arms score different queries. Every T5/T6 cell uses dev `single_texto` `e5b79ae4` for the modified side and dev `texto` for the identity side.
  - n scored + n excluded adds up: L1 1,037+17, L2 544+0, L3 595+13, 2,176+30 in total.
  - ColBERT's identity side reads `OE_long_norm` `75477221`. The report discloses this, and the S4 audit already accepted it.
- **Mechanism executes.**
  - The config sets `stage2_method: oracle_params`. `load()` routes it to `OracleParamsExtractor`, and `retrieve.ipynb` calls `bind_queries` (lines 169–173).
  - `search_batch` refuses unbound or misaligned texts.
  - `oracle: false` in the config is the unported oracle-parent flag, not a contradiction.
  - The generator re-derives Stages 1–3 and raises if its tie set does not reproduce each run's rank 1. It passed on all queries.
- **Design freeze.** `git diff 432b39e..HEAD` on the design shows only the freeze-stamp placeholder being filled (`ddfac3e`, 22 s after the freeze). That is the precedent the S3 audit accepted. The design body is unchanged. Changes live in `SPRINT_S5_AMENDMENTS.md` (A1, A2).
- **S2 archive.** `sha256sum -c runs/_archive/S2/SHA256SUMS`: 40 of 40 OK. The file's own digest `f5705d08` matches T7.
- **`check_run_inputs.py --collection OE`:** 216 of 216 resolve.
- **Tests at HEAD.** The full suite gives 1141 passed, 1 xfailed; the report's 1135 was at `26ed9ff`, and tests were added since. `test_report_traceability.py` passes.
- **Split.** Every run is dev. Nothing is tuned or thresholded; the generator only indexes dev keys.

## Findings

### F1 — major — "Known to be wrong" items 1–2 overstate Q2
- **Report:** item 1 says the oracle bound "cannot beat BM25 on pooled L1". Item 2 lists "Perfect extraction would win" as known to be wrong.
- **T6:** Q2 pooled L1 is **not supported**, −0.0393 [−0.1523, +0.0278]. The upper bound admits a win of about +0.03, so "cannot" is not shown. Q2 `num_to_text` is **supported**, +0.0166 [+0.0045, +0.0437] on 9 concepts (‡). So on one of the two types H3 names, the bound does win.
- **Fix:** item 1 becomes "did not detectably beat BM25 on pooled L1 (interval includes 0)". Item 2 is scoped to pooled L1 and `unit_conversion` and states the `num_to_text` exception with its ‡.

### F2 — minor — Oracle figures quoted without their twin and without intervals
Design, "Oracle arms travel with twins": "No sentence quotes an oracle figure alone."
- Finding 2 gives the oracle's +0.2592 (L2, 5 concepts) and +0.3403 (L3) as "wins widely" with no interval, no ‡ on L2, and no `rules_valuenorm` figure beside them.
- Finding 7 gives the oracle's L2 δ +0.0000 and L3 δ −0.0118 without `rules_valuenorm`'s −0.1673 / −0.1899 from T2.
- Finding 2 also contrasts L1 with L2/L3 without the "between-population" label that finding 4 carries.
- **Fix:** add the twins, the clustered CIs ([+0.2094, +0.2918] and [+0.2707, +0.3794]), ‡ on L2, and the between-population label.

### F3 — minor — Directional word on an interval that spans 0
- Finding 4 says "At identity on the L1 golds, the pipeline already trails by −0.1181 [−0.2349, +0.0966]". The concept-clustered interval includes 0; only the query-level one excludes it.
- **Fix:** drop "trails", or name the query-level interval as the basis and state that the clustered one includes 0.

### F4 — minor — A2's timing claim cannot be checked
- The A2 row says its rule was "written when the generator was, before any T5 or T6 figure was read". The rule is in the generator docstring at `93e5a41`, but that commit also contains T5 and T6. The row itself was only added in `8105135`, after the tables.
- No claim is affected: A2 reaches only `rules_faithful`. T4 shows "no match" = 0.0000 for `rules_valuenorm` and `oracleparams`, and 0.0427 overall for `rules_faithful`.
- **Fix:** amend the row so it says the rule and the tables landed in the same commit.

## Unverifiable
- **"No result had been computed when this was decided" (A1).** A1 is committed in `26ed9ff`, before the runs' timestamps, so this is consistent, but a decision's timing cannot be proven from the artefacts.
- **"On 20 texto / 20 L1 queries… over all 2,206 dev queries only P8's four are exceptions" (report's Check row).** The tests pass. I did not independently confirm that the all-2,206 check is one of the tests that ran, rather than a one-off.
- **"OEB fixture included" in the suite.** Not isolated. The suite passes as a whole.

## Exit criteria
| Criterion | Met | Evidence |
|---|---|---|
| 1. Oracle mode, config and tests committed; suite and OEB fixture pass | yes | `26ed9ff` adds `param_extractor_oracle.py`, config and tests. Suite at HEAD: 1141 passed, 1 xfailed |
| 2. New runs clean, dev, resolving; reuse justified (as amended by A1: re-run and archive) | yes | 6 runs at `26ed9ff`, `code_dirty: false`, dev; 216/216 resolve; archive 40/40 checksums OK |
| 3. T1–T7 generated, byte-identical, guarded; n scored/excluded, CIs, concepts, tie-free and as run | yes | Regenerated byte-identical; prose tests pass; T4–T6 carry the n excluded column; T5 has both readings |
| 4. 3 arms × 9 types × 2 levels plus pools; T5 against the 3 references | yes | `profile_item.md` / `profile_parent.md`; 9 contrast blocks in `contrasts.md` |
| 5. Q1–Q3 read under the rule; Q1/Q3 labelled confirmatory | yes | `predictions.md` labels match the rule for all 9 rows |
| 6. G2 read citing its T6 row, Q2 beside it, H3 movement line with what S6 owes | yes | G2 reads "no" from the Q1 L1 row; Q2 is printed beside it; H3 row says "S6 does not revisit it" |

---
Side effect of this audit: my first regeneration attempt, run with a mis-translated path, created the untracked directory `D:\c\Users\cesar\AppData\Local\Temp\claude\...\scratchpad\s5regen\` outside the repo. It holds only regenerated copies of the S5 tables and can be deleted. No tracked file was modified (`git status` is clean).
