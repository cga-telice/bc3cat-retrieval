# Sprint S6 — Statistical analysis and mediation · report

| Field | Value |
|---|---|
| **Design** | [`SPRINT_S6_DESIGN.md`](SPRINT_S6_DESIGN.md) · frozen at `8abf24f` · amendments A1–A7 in [`SPRINT_S6_AMENDMENTS.md`](SPRINT_S6_AMENDMENTS.md) |
| **Closed** | 2026-09-30 (report written). Audit 2026-10-01 **PASS WITH FINDINGS** ([`SPRINT_S6_AUDIT.md`](SPRINT_S6_AUDIT.md)); all six resolved. See [Audit response](#audit-response) |
| **Code commit** | 15 new runs at `a1bbc81`, all `code_dirty: false`. 30 reference runs read, not re-run (S3/S4 commits, T8). Generator `src/utils/build_results_s6.py`; tables generated at `c2ecdde` (A7; `041c3e5` before the audit), in `bc3cat-s3`, one BLAS thread |
| **Query-set digests** | `single_l2_texto` `9612ad99` (feats; JSON `fff7dd3b`) · `single_texto` `e5b79ae4` · `texto` `643f1a72` (ColBERT and `bge_m3_dense` `texto` read `OE_long_norm` `75477221`) |
| **Runs** | `runs/OE/single_l2_texto/<arm>` (new, 15) · `runs/OE/{texto,single_texto}/<arm>` (S4's) · split `dev` |
| **Results** | [`results/S6/`](../results/S6): T1–T8, `figures.md` and Figs. 1–3, generated, byte-identical across two generations, under the prose guard |

## What ran

Every stamp `{run_id, config SHA-256, code commit, query-set SHA-256}` is in
[`run_provenance.md`](../results/S6/run_provenance.md) (T8); none is repeated here.

| Block | What | Where |
|---|---|---|
| Intake | `single_l2_texto` registered; its tables derived on `single_texto`'s path, proven by re-deriving `single_texto` exactly. SINGLE modifications sidecar taken in (release blob, never handed off) | `66fc8b0`, [`DELIVERIES.md`](../DELIVERIES.md) |
| Environment | Analysis stack pinned in code; nothing installed (A1) | `c6003d3` |
| Runs | 15 S4 arms × `single_l2_texto` | `a1bbc81`, T8 |
| Analysis | T1 L2 profile · T2 M0 · T3 M1/M2 and PM · T4 δ / d_tok · T5 D-004 · T6 power · T7 R1–R6 · T8 provenance · Figs. 1–3 | [`results/S6/`](../results/S6) |

**Populations.** `single_texto` (S4's): 2,206 dev queries over 42 concepts, item level 2,176 scored over 40.
**L2w** = `single_l2_texto`: 518 dev queries, 518 scored, over 9 concepts (per type 9 / 8 / 9 in T1; the grammar
ceiling is 13 dev / 12 test, D-043). Layers reach different leaves: every layer contrast is **between-population**.
**Tie-free Acc@1 is the reading** (D-028 note); as run is printed beside every test and **no reading differs** (T7).

## Findings

**1. H1 holds for every non-floor base arm (T7).** The parent − item gap widens under one edit for the four arms
S4 did not test (R6a, 4 of 4 supported: `tfidf_phrases_replace` +0.3638, `bge_m3_dense` +0.3460, `dense_e5`
+0.0915, `dense_es_hiiamsid` +0.3950). Conditional discrimination falls more than concept identification in all
seven (R6b, 7 of 7): from +0.0887 [+0.0501, +0.1324] for `bm25_unigram` to +0.3875 for `dense_es_hiiamsid`.
S4's P1 re-read tie-free is supported for its three arms (T7, reference).

**2. L1 is where lexical arms break, confirmed on unseen L2 queries (R1, blind).** Pooled L1 item δ minus L2w item
δ: −0.5013 [−0.6824, −0.2205] for `bm25_unigram`, −0.5912 [−0.7318, −0.3457] for its oracle twin. Both supported.
L2w rests on 9 concepts (‡).

**3. Under L2, BM25 loses the concept and ColBERT does not (R2, blind; BM25's reading not robust to D-004, and its
pooled L2w δ below its MDE).** Among item losses, the share landing in the wrong concept is higher on L2w than on
L1 by +0.4930 [+0.3175, +0.6728] for `bm25_unigram` (supported, Holm p 0.0480; not supported on the D-004 clean
subset, Holm p 0.0756, T5) and +0.0195 [+0.0000, +0.0552] for ColBERT (not supported). On L2w, BM25's parent δ is
−0.1042 against an item δ of −0.1081; ColBERT's parent δ is −0.0029 against an item δ of −0.1485 (T1). These
T1 figures are descriptive: BM25's pooled L2w item δ is below its MDE (0.1081 against 0.1572, T6), with a concept
interval of [−0.2167, +0.0000]. For ColBERT, L2 costs the leaf, not the concept.

**4. Lost overlap explains more of BM25's damage than of BGE-M3's, but is not shown to explain most of it (R3,
R4, blind).** PM, the share of the pooled δ attenuated by the four overlap terms (T3; a decomposition, not a
causal estimate): `bm25_unigram` 0.4410 [0.2300, 0.6316], `bm25_unigram_params` 0.5789 [0.4086, 0.7695]. Neither
interval clears 0.5: R3 not supported for both. Against `bm25_unigram`, PM is lower for ColBERT by +0.2560
[+0.1258, +0.4922] and for `bge_m3_dense` by +0.3730 [+0.2070, +0.5097]: R4 supported for both. R4 tested those two
arms only, and across the seven arms PM does not split lexical from dense (T3, descriptive): `dense_e5` is
+0.4944 [−0.0435, +0.8507], above `bm25_unigram`, `dense_es_hiiamsid` +0.3210, and the lexical
`tfidf_phrases_replace` oracle +0.2171 (audit F2, D-049 amendment).

**5. What overlap does not see: which token was lost.** Under M1, `bm25_unigram`'s `synonym_label` effect barely
moves (−0.6576 → −0.6079), while `num_to_text` halves (−0.8589 → −0.4071) and `template_paraphrase`'s residual
interval reaches 0 (−0.5237 → −0.1785 [−0.3265, +0.1598]) (T3). A synonym swap changes one token, so
coverage hardly falls, yet that token is the one that tells siblings apart. Coverage counts how much surface
changed; the damage follows which surface changed.

**6. L1 is not shown an order of magnitude worse per unit of surface change (R5, confirmatory).** L1 : L3 ratio
of δ / d_tok: 5.6751 [2.8809, 11.6002] for `bm25_unigram`, 8.0244 [4.2929, 15.8136] for its twin; both contain 10.

**7. `template_paraphrase` inside L3: an overlap cost for BM25, not for ColBERT (T3, descriptive).** Its M1
residual contains 0 for both BM25 arms (`bm25_unigram_params` +0.0292 [−0.1172, +0.3056]) and stays below 0 for
ColBERT (−0.2987 [−0.4256, −0.2032]): for bag-of-words it costs what it removes; for ColBERT, more.

**8. The mixed model's additive concept intercept does not hold for bag-of-words (T2).** For `bm25_unigram`,
`reorder` δ is exactly 0 on every one of its queries, yet M0 puts its average-concept effect at +0.2015; the
concepts admitting `reorder` sit at û −0.2011. The same arithmetic moves `compression` to +0.2125 and
`paraphrase` to +0.0005. The proposal's model assumes a concept's difficulty is shared across types; for a
bag-of-words arm it is not. No reading rests on the mixed model (design), and T2 prints û so its β are not
read as type effects (A3). The mixed PM is on a different scale and is not a check of the OLS PM (T3).
The fits are also fragile. The leaf variance component is estimated near zero, and whether the optimiser
converges with it changed with the BLAS thread count; the generator now pins one thread (A6). Of 42 fits, 37
keep the leaf component; `bge_m3_colbert`'s M0 and both its M1 fits drop it, and `dense_es_hiiamsid`'s two M1
fits converge with neither (T2, T3).

**9. Carried caveats, counted.**
- **D-004 (T5).** 185 L1/L2 queries carry a doubled token, and detector and sidecar agree on every decidable
  one; L3 rewrites are templates the sidecar cannot decide. Two readings are **not robust** to dropping the
  flagged queries: R2 for `bm25_unigram` (Holm p 0.0756 clean) and R6b for `bm25_unigram` (0.0936 clean). Both
  intervals still exclude 0. The full-population readings stand (D-004).
- **P8 (D-044).** Without the four case-only queries, PM moves from 0.4410 to 0.4381 for `bm25_unigram` (T3);
  the `synonym_label` term of M0–M2 and every no-P8 fit's status are printed both ways (T2, T3, A5).
- **Power (T6).** For `bm25_unigram` on pooled L2w the MDE is 0.1572 against an observed |δ| of 0.1081, and for
  its oracle twin 0.0524 against 0.0502: no L2w item-level claim, per type **or pooled**, is made for either BM25
  arm. Where finding 3 and known-wrong 5 cite those cells, they cite them descriptively (audit F4).
- **D-043 ruling 3 is not reopened** (T7): no R1 / R2 test is not supported with a wide interval.

## Hypotheses

| Hypothesis | Movement | Evidence |
|---|---|---|
| **H1** (widening collapse) | **supported** on dev, all seven non-floor base arms | S4 P1 (3 arms) and its tie-free re-read; R6a 4 / 4, R6b 7 / 7. R6b for `bm25_unigram` not robust to D-004 (interval still above 0) |
| **H2**, L1 clause | **supported** | S4 P2; R1 2 / 2, blind, on 9 L2 concepts |
| **H2**, L2 clause ("concept-level more than item-level") | **supported for BM25; not supported for ColBERT** | R2: BM25 supported (not robust to D-004); ColBERT not supported, and descriptively the reverse holds: it keeps the concept while losing the leaf (finding 3) |
| **H2**, L3 clause | **supported for `reorder`; `template_paraphrase` is an overlap cost for bag-of-words** (descriptive) | S4 P3/P4 and their tie-free re-read; finding 7 |
| **H5**, mediation | **comparative clause supported for BM25 against BGE-M3 (ColBERT, dense); "most" not supported** | R4 2 / 2, the only two arms tested; `dense_e5` descriptively above BM25 (finding 4); R3 0 / 2 (PM intervals contain 0.5) |
| **H5**, normalised sensitivity | **not supported** (interval contains 10; not refuted either) | R5 0 / 2 |
| H3, H4, H6 | **not addressed** | S5 closed H3; H4 is S8's; H6 S9's |

## What is now known to be wrong

Items 2 and 3 are registered claims S6 could not establish, listed here because the manuscript must stop making
them; neither is refuted (audit F3; the Hypotheses table reads them the same way).

1. **"A random intercept for concept separates a modification's effect from the family's difficulty"**
   (`RESEARCH_PROPOSAL.md` §6). For bag-of-words arms the concept effect is not shared across types: M0 gives
   `reorder` +0.2015 where every query's δ is 0 (finding 8). An adjusted type effect needs a type-by-concept
   structure, or it must be read as an average-concept quantity, which is not what the proposal meant.
2. **"Overlap mediates most of the lexical degradation"** (H5). *Not established, not shown wrong.* PM 0.4410
   for `bm25_unigram` and 0.5789 for its oracle twin, both intervals containing 0.5 and the twin's point above
   it. What is known is narrower: token coverage measures the amount of change, and the type it explains least,
   `synonym_label`, changes one token (finding 5).
3. **"L1 damage per unit of change is an order of magnitude higher than L3's"** (H5). *Not established, not
   shown wrong.* The points are 5.6751 and 8.0244, and both intervals contain 10 ([2.8809, 11.6002] and
   [4.2929, 15.8136]). The registered claim cannot be read on these data.
4. **"L2 affects concept-level more than item-level"** as a family-free statement (H2). It holds for BM25; for
   ColBERT the test is not supported and the reverse is observed: it keeps the concept on L2w (parent δ −0.0029).
5. **"The L2 result rests on 5 concepts and may not replicate."** It replicated, blind, on 9, with two
   qualifiers: BM25's concept-level half (R2) is not robust to D-004 (Holm p 0.0480 full, 0.0756 clean, T5), and
   BM25's pooled L2w item δ is below its MDE (T6). What did not carry over is the identity level:
   `bm25_unigram` retrieves the L2w golds from their own `texto` at 0.7114 tie-free against 0.9421 on S4's L2
   leaves (T1). The new concepts are harder for BM25 before any edit, so L2s and L2w δ are not interchangeable;
   that is read from the identity levels, not from the under-powered L2w δ.
6. **"Key order drives BM25's readings"** (the worry behind D-028's tie-free reading). No registered reading
   changes between tie-free and as run (T7), and no S4 category changes when re-read tie-free.
7. **"A mixed model on this data gives one answer."** At the leaf-variance boundary its convergence depends on
   floating-point summation order: 33 of the 702 table rows present in both committed generations moved between
   the first (`144f3be`, 32 threads) and the final one (`450d13d`, one thread), and convergence flipped both ways
   (finding 8, A6). Any mixed-model figure here is reproducible only with its thread pin.
8. **"The release shipped every sidecar the plan lists."** The SINGLE modifications sidecar existed upstream
   since the release and was never handed off; S3's text detector stood in for it. It agrees with that detector
   wherever it can decide.

## Exit criteria

| # | Met | Evidence |
|---|---|---|
| 1 | yes | `66fc8b0`: query set registered, tables derived on a proven path, sidecar in `DELIVERIES.md`, `MANIFEST.md` regenerated; intake tests pass; suite 1158 passed, 1 xfailed (at `66fc8b0`) |
| 2 | yes | 15 runs `code_dirty: false`, dev, `a1bbc81`; `check_run_inputs.py` resolves 235 of 241 runs, the 6 others the same dirty-tree stamps as before; earlier generators regenerate with identical content (11 S3/S4 files differ in CRLF only on the host, H5) |
| 3 | yes, after A4–A7 | T1–T8 and Figs. 1–3 byte-identical across two generations, under the prose guard; tie-free and as run on every registered reading; stack stamped. **First reported "yes" without two parts (audit F1):** n excluded was printed in T1 only, and T1's tie-free δ carried the clustered interval only. A7 adds n excluded to T2–T7 and the query-level interval to T1's tie-free δ (ColBERT's L2w parent δ −0.0029: [−0.0077, +0.0000] query, [−0.0087, +0.0000] concept) |
| 4 | yes | M0–M2 fitted for 7 arms, with and without P8 (42 fits, every status printed, A5): 37 with the leaf component; 5 refitted without it, of which `dense_es_hiiamsid`'s two M1 fits do not converge and are marked, its mixed PM "—". PM has a clustered interval for every arm |
| 5 | yes | T7: 21 tests, 16 supported, 5 not supported, 0 contradicted; blind / confirmatory labelled; clean-subset reading beside (T5) |
| 6 | yes | Hypotheses table; L2 breadth and ceiling stated; D-043 ruling 3 not reopened |

## Deviations from design

| Amendment | Deviation | Why |
|---|---|---|
| A1 | Work item 2: nothing installed; the stack pinned in code; container checks run by direct call | The packages were already in `bc3cat-s3`; it has no `pytest` |
| A2 | Tie-free at parent level and for ratios, the no-number indicator, p against a non-zero null, "PM undefined", paired R4 weights, clean subset, P8 in the models, MixedLM fallback, floor re-check — fixed **before** any S6 figure | The design defined tie-free at item level only and left the rest open |
| A3 | T2 gains û and β + û; T3 marks a non-converged mixed PM; T6 marks zero-variance cells | The first generation printed an M0 β that contradicts its raw δ, and a non-converged PM, unexplained |
| A4 | Query-level intervals beside every clustered one | Exit criterion 3, checked before writing this report |
| A5 | The `synonym_label` term and every fit without the P8 queries printed; P8 rows in T6 and `figures.md` | D-044 and A2 (g) required them; found checking this report against the tables |
| A6 | BLAS pinned to one thread; the mixed-model cells of the first generation superseded | Changing the thread count moved mixed-model output, and nothing else. Two counts, of two comparisons: A6's "37 of 993" is the uncommitted 8-thread A4/A5 generation against `144f3be` (not recoverable from git); "33 of 702" is `144f3be` against the committed final `450d13d`, over the rows both contain, all 33 in ColBERT's mixed cells (audit F6) |
| A7 | n excluded in T2–T7; T1's tie-free δ gains its query-level interval | Audit F1. Columns only: all 723 earlier table rows unchanged against `450d13d`, no reading moved |

Not an amendment: two generations ran concurrently for about six hours on 2026-09-30 after a stop left one
process alive; their output was discarded and regenerated. Docker Desktop was repaired on 2026-09-30 by renaming a stale socket directory (`STATE.md`).

## What the next sprint inherits

- **S7** — the stacked set with the tie-free reading; T1's L2w and `single_texto` frames as the single-edit
  reference. Finding 5 (which token, not how many) is a covariate question S7's stratifications can ask.
- **S8** — the count term M0 could not carry (`modification_count` is 1 throughout `single_texto`).
- **S9** — H5's residual: normalising surfaces will recover what overlap explains (PM 0.4410 for BM25), not the
  discriminating token of a `synonym_label` rewrite. S9's value-reading step is where that is tested.
- **S10** — ColBERT loses the leaf, not the concept, under L2 (finding 3), and its `template_paraphrase` cost
  survives the overlap terms (finding 7): the target is within-concept ordering.
- **Debt.** A mixed model with a type-by-concept term, if any later sprint wants adjusted type effects. Fig. 1
  labels overlap at the top right (draft). `index/*/meta.json` still omits the ML stack (H4).

## Decisions raised

| ID | Status | What |
|---|---|---|
| D-048 | **Accepted** (César, 2026-10-01) | M0's additive concept intercept is recorded as not holding for bag-of-words; the proposal's §6 "separating the modification's effect from the family's difficulty" is withdrawn for the random-intercept model, and adjusted type effects, if needed, require a type × concept term (finding 8) |
| D-049 | **Accepted** (César, 2026-10-01); **amended** after audit F2 | H5 is restated for the manuscript on what S6 measured: overlap explains more of BM25's damage than of BGE-M3's, ColBERT and dense (R4; first worded "the lexical arms' … the encoders'", which R4 did not test); it is not shown to explain most of it (R3), and the L1 : L3 ratio is not shown to reach 10 (R5) |
| D-028 | note | Tie-free changed no S6 reading and no S4 category (T7) |

## Audit response

`/audit S6` ran in a fresh session on 2026-10-01 and returned **PASS WITH FINDINGS**
([`SPRINT_S6_AUDIT.md`](SPRINT_S6_AUDIT.md), verbatim). It regenerated `results/S6/` byte-identically, re-hashed
all 45 run stamps and every input, and traced every quoted figure. It raised 2 major and 4 minor findings. No run
was re-made. One change is to the tables (columns only, A7); the rest are to prose and to D-049.

| Finding | Resolution |
|---|---|
| F1 — criterion 3 reported met without n excluded in T2–T7 and without a query-level CI on the tie-free δ (a repeat of S4 audit F2) | **Fixed** by A7 (`c2ecdde`). T2, T3, T4 and T6 print n excluded; T5 and T7 print n scored (excluded) per pool; T1's tie-free δ carries both intervals. All 723 earlier table rows are unchanged against `450d13d`. Criterion 3 now reads "yes, after A4–A7" and says it was first reported without them |
| F2 — "the encoders'" generalises R4 beyond ColBERT and `bge_m3_dense` | **Fixed.** Finding 4 and the H5 row name the two arms tested and give the seven-arm PM beside them, with `dense_e5` above BM25. D-049 is amended in `DECISIONS.md` (César, 2026-10-01): the manuscript clause reads "than of BGE-M3's (ColBERT and dense)" |
| F3 — known-wrong 2 and 3 are unresolved, not wrong | **Fixed.** Both read "not established, not shown wrong", with both intervals; the section says why they are listed |
| F4 — power caveat narrowed to per-type; the pooled BM25 L2w cell also fails its MDE | **Fixed.** The caveat covers pooled cells and the oracle twin; finding 3 and known-wrong 5 say their L2w δ is descriptive and below its MDE |
| F5 — "replicated, blind, on 9" without its qualifiers | **Fixed.** Finding 3's heading and known-wrong 5 carry the D-004 non-robustness of BM25's R2 (Holm p 0.0480 full, 0.0756 clean) and the MDE caveat |
| F6 — 33 against 37 rows | **Reconciled.** Both are right, and they count different comparisons. The 37 of 993 in A6 compared the uncommitted 8-thread A4/A5 generation with `144f3be`, and git cannot recover it. The 33 of 702 compares `144f3be` with the committed final `450d13d`, over the rows both contain; all 33 are ColBERT's mixed cells. Known-wrong 7 and the Deviations row say which is which |

The auditor's unverifiable items stand as it listed them. After A7, `results/S6/` was generated twice at `c2ecdde`
and is byte-identical across the two.
