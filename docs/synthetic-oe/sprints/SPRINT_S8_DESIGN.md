# Sprint S8 — E3 balanced dose design · design

> **Frozen at:** `<commit SHA>` · `<date>`
> This document is read-only from that commit. Changes go in
> [`SPRINT_S8_AMENDMENTS.md`](SPRINT_S8_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S8` · backbone |
| **Status** | planned → active |
| **Serves** | H4 (super-additivity); gate G3 re-read as identifiability |
| **Depends on** | S7 (`done`); upstream: E3 delivery `OE_dose_texto.json` `555fab84…`, `OE_isolated_texto.json` `054041ff…`, `OE_leaf_applicability.jsonl` `eda12d17…` (D-009 Delivered, taken in by S3 work item 2) |
| **Decisions applied** | D-004, D-008, D-009, D-010, D-028, D-030, D-032, D-033, D-045, D-046, D-047, D-048, D-052, D-053 (both accepted at opening, César, 2026-10-01) |
| **Effort** | 1.5 weeks |
| **Predecessor / successor** | S7 / S12 |

## Goal

At the end of S8 we will know whether stacked modifications hurt **more than the sum of their isolated
effects** (H4) when the comparison is made **within the same leaf**: each of 328 dev leaves carries a nested
ladder of one to five modifications and, separately, each of the nine types alone. S7 could not ask this,
because on the stacked set dose varies between concepts and within-leaf additivity reached 26 queries. We
will also know the within-leaf dose-response with family held fixed by construction, which is what S7's
dose gradient could not separate from family. The claim's reach is fixed now: four OEB canalization
concepts, all of them large families.

## Entry state

Checked in the tree on 2026-10-01, not taken from the registry:

- **S7 `done`**: `SPRINT_S7_AUDIT.md` **PASS WITH FINDINGS**, all seven resolved; D-050 and the D-051
  amendment accepted. HEAD `f19a2fe`, tree clean, branch `research/synthetic-oe`, main checkout.
- **E3 files in place, re-hashed**: `OE_dose_texto.json` `555fab84…` (3,000), `OE_isolated_texto.json`
  `054041ff…` (5,400), `OE_leaf_applicability.jsonl` `eda12d17…` (1,500); all three match `MANIFEST.md`.
  `tests/test_intake_e3.py` re-run: 23 passed.
- **Dev population, counted**: dose 1,640 queries, isolated 2,952, both over the **same 328 leaves** in
  4 concepts — `OEB020$` 61 leaves, `OEB030$` 87, `OEB230$` 93, `OEB290$` 87. Family sizes 4,608 /
  6,336 / 6,336 / 6,336: every ladder concept is a large family with the same five axes. 328 queries per
  rung; each leaf has nine isolated queries, one per type.
- **The ladder is nested in text as well as in labels**: the tokens rung *k*−1 inserts against identity
  survive into rung *k* at a mean rate 0.9927 (1,158 of 1,295 steps keep all of them; the rest are later
  edits writing over earlier spans, e.g. `template_paraphrase`).
- **The isolated set is a different draw.** For the same leaf and type, the rung-1 query equals the
  isolated query in **89 of 328** cases; the other 239 use a different rewrite from the same type's menu
  (`unit_conversion` 15 of 18 equal, `synonym_label` 4 of 38). "The sum of the isolated effects" is
  therefore a sum over the same leaves and types, **not over the same edits**. Constrained below.
- **Type balance on dev**: at rung 1 each type 31–48 leaves except `unit_conversion` 18; `reorder` and
  `template_paraphrase` enter at rung 5 for only 10 and 9 leaves. `reorder` × `template_paraphrase` and
  `unit_conversion` × `unit_expansion` never co-occur (pinned by the intake tests).
- **Undecidable and excluded queries**: no dose or isolated query equals any corpus `texto`, also after
  lower-casing; no query text is shared between golds; no ladder leaf is in a D-033 duplicate group; P7 and
  P8 are single-set keys and do not apply. No E3 modifications sidecar was delivered (request §6 asked
  for one); D-004 flags come from `utils/pantry_flags.py`, as in S7.
- **Not wired**: `run_context.QUERY_SETS` reserves `balanced_texto` only; no feature tables exist for
  either set; no run reads them.
- **Identity runs**: all 15 S4 arms and the three S5 structured arms have a `texto` run on dev; 0 runs
  with `code_dirty: true`.

## Work

1. **Wire the two sets (D-052).** Register `dose_texto` and `isolated_texto` in `run_context.QUERY_SETS`
   and retire `balanced_texto`. Build their feature and norm tables with the S1 loader; the projection
   keeps `gold_item_key`, `parent_key`, `modification_types`, `modification_count`, `applicable_types`.
   Tests: every dev gold resolves, row counts 1,640 / 2,952, nesting holds per leaf, a test-side query
   is never loaded by a dev run, and the undecidable count above is asserted (zero; any nonzero stops the
   sprint for an amendment).
2. **Run**, split `dev`, clean tree, sprint container, both sets: the **15 S4 arms** (10 indexed, 2 RRF,
   3 CE-blend; components first) and the **3 S5 structured arms** = **36 runs**, every parameter as
   frozen in S4/S5. Nothing is tuned. The identity side is each arm's existing `texto` run, not re-made.
3. **Analyse** with `src/utils/build_results_s8.py` into `docs/synthetic-oe/results/S8/`, under
   `tests/test_generated_prose.py`. S6's tie-free scoring and S7's bootstrap code are imported, not
   copied.
   - **T1 — ladder.** Per arm: item and parent Acc@1 at identity and rungs 1–5 on the 328 leaves
     (tie-free and as run), retention, δ per rung, Δ = parent − item.
   - **T2 — isolated.** Per arm × type: δ_iso against identity on the same 328 leaves; S4's pooled
     `single_texto` δ for the type printed beside, between-population, never read as a contrast.
   - **T3 — realisation check.** Per arm × type, on rung-1 queries: agreement of rung-1 and isolated hit,
     split by text-equal (89) and text-different (239). This measures how much of X1 can be draw noise.
   - **T4 — additivity, cumulative (X1).** Observed against clipped-additive prediction per rung and
     pooled over rungs 2–5; the two discordant cells counted.
   - **T5 — marginal cost (X2).** At-risk steps, the two discordant cells, per rung and per added type.
   - **T6 — dose-response (X3).** Within-leaf slope of item hit on dose 0–5, per arm; quadratic term
     beside it, descriptive.
   - **T7 — pairwise, descriptive.** For each of the 34 identifiable type pairs, the X2 excess at the
     step that completes the pair, with n. The two non-identifiable pairs are printed as such.
   - **T8 — S7 reference.** S7's stacked δ by `texto_modification_count` beside the ladder's δ by rung,
     between-population, descriptive.
   - **T9 — D-004 sensitivity.** Every X-reading without flagged queries (leaf dropped from a contrast if
     any query it uses is flagged).
   - **T10 — predictions** X1–X3. **T11 — provenance.**
4. **Figure, drafted**, into `results/S8/figures/`: Fig. 6, per arm, observed and clipped-additive item
   Acc@1 against dose, with the identity point.
5. **Report** `SPRINT_S8_REPORT.md`, then `/audit S8` in a fresh session.

## Design constraints

- **Population.** Dev ladder leaves only: 328 leaves, 4 concepts, 1,640 dose and 2,952 isolated queries
  plus the 328 identity results. Test-side ladder queries (3 concepts, 272 leaves) are never read; they are
  S12's. No item-level exclusion applies (entry state); n excluded is printed anyway, as 0.
- **Within leaf, always.** Every effect is a contrast on the same leaf: rung against identity, rung
  against the previous rung, rung against the isolated queries of its own types. No δ in a test reads a
  leaf against another leaf.
- **The additive reference is the E3 isolated set on the same leaves**, not S4's single-type effects. The
  plan's wording ("S4's isolated effects") predates the delivery; S4's figures are a different population
  and appear in T2 only, never in a contrast. Recorded in `RESEARCH_PLAN.md` with this design.
- **H4 on a bounded scale.** Item hit is 0/1, so the literal sum can fall below −1 and cannot be exceeded
  by any observation. The registered reference is the **clipped-additive prediction**, per leaf and rung:
  pred = clip(hit_id + Σ_{t∈S_k} (hit_iso,t − hit_id), 0, 1). For a leaf hit at identity this is 1 when
  every component survives alone and 0 when any fails alone; it is the sum of isolated effects with the
  bound applied and nothing else. The unclipped sum is printed in T4, never read.
- **Isolated and ladder edits are different draws** (entry state). X1 and X2 compare edit types, not
  identical edits. T3 is printed beside every X-reading; the report states draw noise as a limitation
  and does not attribute an X-excess to interaction unless it exceeds T3's text-different disagreement
  rate for that arm.
- **Two interactions are not identifiable**: `reorder` × `template_paraphrase`, `unit_conversion` ×
  `unit_expansion`. No claim, pooled or pairwise, names them; T7 marks them.
- **Thin cells.** `unit_conversion` 18 leaves at rung 1; `reorder` and `template_paraphrase` enter rung 5
  for 10 and 9 leaves. Per-type and per-pair figures carry n, cells under 20 leaves carry ‡, and none is
  read.
- **Inference (D-053).** Four clusters cannot carry D-030's reading. The interval read is the
  **leaf bootstrap stratified by concept**, B = 10,000; the concept-clustered interval is printed beside
  every reading and labelled as resting on 4 clusters. A reading is *supported* only if, in addition, the
  point estimate has the predicted sign in at least 3 of the 4 concepts (per-concept estimates in T10).
  The claim is therefore scoped to these leaves and concepts; no generalisation across concepts is
  claimed, and S12's 3 test concepts are the replication.
- **Tie-free Acc@1 is primary** (D-028 note), as run beside it; a reading that differs between the two is
  flagged.
- **Floor arms**: identity item Acc@1 on the 328 leaves below 0.20, recomputed here. Reported, excluded
  from every reading, read *not tested* and stated.
- **Oracle arms travel with their twins** (D-010). Dose and isolated `parameters` carry rewritten
  values, so the oracle arms read rewritten parameters, as on stacked.
- **Structured arms are profiled, not tested** (D-046); T1–T2 only.
- **No mixed model** (D-048). X3's slope is the mean of per-leaf OLS slopes, which is the leaf
  fixed-effects estimate on a balanced ladder.
- **Registered predictions**, 21 tests, Holm across all 21, BH beside. Supported / contradicted / not
  supported by S4's rule under D-053. Arms: S6's seven non-floor base arms — `bm25_unigram`,
  `bm25_unigram_params`†, `tfidf_phrases_replace`†, `bge_m3_colbert`, `bge_m3_dense`, `dense_e5`,
  `dense_es_hiiamsid` — minus floor arms. All **blind**: no arm has been run on either set.
  - **X1 (H4, cumulative).** Mean over leaves and rungs 2–5 of (hit_k − pred_k) < 0: the stack fails more
    often than its clipped-additive prediction. 7 tests.
  - **X2 (H4, marginal).** Over steps *k* = 2–5 where rung *k*−1 is a hit, with *t* the type added at
    *k*: P(hit_iso,t = 1, hit_k = 0) − P(hit_iso,t = 0, hit_k = 1) > 0 — an edit breaks the leaf in
    company more often than it breaks it alone. 7 tests. Conditioning on survival selects robust leaves,
    which works against X2; this is stated, not corrected.
  - **X3 (dose-response).** Within-leaf slope of item hit on dose 0–5 < 0. 7 tests. It establishes that
    the ladder has a dose effect at all; it does not bear on additivity.
- **How H4 resolves.** *Supported* on these leaves if X1 and X2 are supported for every tested arm;
  *contradicted* if X1 reads contradicted (sub-additive) for any arm; *partly supported* otherwise,
  naming arms. Every H4 sentence names the 4 concepts and the draw-noise limitation.
- **How G3 is read.** H4 is identifiable within leaf for 34 of 36 type pairs on 328 dev leaves; across
  concepts it is not (4 clusters). The report states G3 in those words, so the gate is answered by the
  design rather than by the result.
- **D-004.** Every X-reading recomputed in T9; a category change is *not robust*, and the
  full-population reading stands.
- **Dev only.** Generated tables type no number into their prose; the report is guarded by
  `tests/test_report_traceability.py`.

## Exit criteria

1. `dose_texto` and `isolated_texto` resolve through `run_context`; `balanced_texto` is gone; work item
   1's tests pass, including the zero-undecidable assertion.
2. 36 runs exist on the two sets: `code_dirty: false`, split `dev`, resolving under
   `check_run_inputs.py`, each stamped against its set's feature-table digest.
3. `results/S8/` holds T1–T11 and Fig. 6, generated by `build_results_s8.py`, byte-identical on
   regeneration and under the prose guard. Every item-level figure carries n scored and n excluded;
   every contrast its stratified-leaf and concept-clustered intervals and its per-concept signs.
4. X1–X3 (21 tests) are each read supported, not supported, contradicted or not tested, tie-free and as
   run, with the D-004 reading and T3's draw-noise rate beside.
5. The report resolves H4 under the rule above, reads G3 in the words above, and states the 4-concept
   scope, the two non-identifiable pairs and the different-draw limitation.
6. D-052 and D-053 stand as recorded in `DECISIONS.md`; any change to either is an amendment here.
7. Full suite and the OEB fixture pass.

## Out of scope

- **The sibling-density law**: every ladder concept is a large family; S8 cannot vary it. S12 re-reads W3.
- **Test-side ladder** (`OEB040$ 280$ 300$`): S12.
- **Interactions involving the two never-co-occurring pairs**, and any per-pair claim (T7 descriptive).
- **H1, H3, H5 on the ladder**: printed in T1, not re-tested.
- **Re-tuning**, new methods, the mixed model (D-048 debt).

## Risks

| Risk | Handling |
|---|---|
| Draw noise between isolated and ladder edits swamps any interaction | T3 measures it per arm; no excess below it is read as interaction |
| BM25-like arms fail early on the ladder, leaving few at-risk steps for X2 | n at risk printed per arm; an arm with fewer than 50 at-risk steps reads X2 *not tested* |
| Floor effects make X1 sub-additive by construction for arms that fail at rung 1 | Clipped prediction is 0 there, so those leaves can only contribute sub-additively; the share of such leaves is printed, and the report says contradicted X1 may reflect it |
| Four clusters | D-053; per-concept signs; scope stated in every H4 sentence |
| BGE-M3 server unreachable from `bc3cat-s3` (STATE, 2026-10-01) | Check `host.docker.internal` before the run; S7's `/etc/hosts` mapping recorded as an amendment if used again |
| CE-blend runtime on 4,592 queries × 3 | `_ce_cache`; budgeted within the sprint |

## Amendments

In [`SPRINT_S8_AMENDMENTS.md`](SPRINT_S8_AMENDMENTS.md), append-only (D-045).
