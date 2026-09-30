# Sprint S6 — Statistical analysis and mediation · design

> **Frozen at:** `<commit SHA>` · `<date>`
> This document is read-only from that commit. Changes go in
> [`SPRINT_S6_AMENDMENTS.md`](SPRINT_S6_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S6` · backbone |
| **Status** | planned → active |
| **Serves** | H1 (widening collapse), H2 (layer specificity), H5 (overlap mediation) |
| **Depends on** | S4 (`done`), S5 (`done`); upstream: `OE_single_l2_texto.json` (D-043, landed); SINGLE modifications sidecar (plan §5, **not handed off**, work item 1) |
| **Decisions applied** | D-004, D-010, D-028, D-030, D-032, D-033, D-038, D-043, D-044, D-045, D-047 |
| **Effort** | 2 weeks |
| **Predecessor / successor** | S4, S5 / S7, S9, S10 |

## Goal

At the end of S6 we will know whether H1, H2 and H5 hold on dev once three things S4 could not do are
done: L2 read on 9 / 9 / 8 concepts instead of 5; the type effects estimated net of concept and leaf
difficulty; and the lexical arms' degradation decomposed into the part carried by lost lexical and
numeric overlap and the part that remains. H5 is the new knowledge: whether BM25 fails *because*
the query stops containing the target's words and numbers — in which case S9's query-side
normalisation is the remedy — or whether something survives that overlap does not explain.

## Entry state

Checked in the tree on 2026-09-30, not taken from the registry:

- **S4 `done`**: `SPRINT_S4_AUDIT.md` re-audit **PASS WITH FINDINGS**, all resolved. **S5 `done`**:
  `SPRINT_S5_AUDIT.md` **PASS WITH FINDINGS**, all resolved. HEAD `db3a14c`, tree clean.
- **Runs**: 216 `runs/OE/*/*/run_meta.json`, **0** with `code_dirty: true`. All 15 S4 arms have a
  `texto` and a `single_texto` run; the 10 indexed arms have `index/OE/<arm>`.
- **Digests re-hashed, match `MANIFEST.md`**: `OE_texto.json` `02a2c270`, `OE_single_texto.json`
  `b6a43961`, `OE_duplicate_texto_groups.json` `b3cfcad4`, `OE_single_texto_feats` `e5b79ae4`,
  `OE_long_feats` `643f1a72`, `OE_long_norm` `75477221`, `OE_single_l2_texto.json` `fff7dd3b`,
  `OE_single_l2_modifications.jsonl` `e1e5adbb`.
- **L2 delivery landed, not wired** (D-043 note): 1,092 queries over 400 golds (both splits); 518 dev
  at 179 / 180 / 159 over 9 / 9 / 8 concepts (`DELIVERIES.md`). No query-set name in
  `run_context.py`, no feature tables, no runs. 24 of its golds are also `single_texto` golds.
- **Not landed: the SINGLE modifications sidecar** (`RESEARCH_PLAN.md` §5, "requested S1, consumed
  S6"). It exists upstream, committed at `bc3cat-dataset` `a89eca4`
  (`data/synthetic/processed_OE_ablation_single/BC3CAT_Syn_modifications.jsonl`, SHA-256 `f492d9a0…`,
  4,439 rows whose `item_key`s match all 4,439 `single_texto` queries, keys only checked), and was
  never delivered here: not in `MANIFEST.md` or `DELIVERIES.md`. S3 ran the D-004 sensitivity with a
  text detector instead (D-038 amendment). Taken in by work item 1.
- **Environment, not ready**: `statsmodels` and `matplotlib` are absent from the host interpreter and
  from `requirements.txt`; the Docker engine was not running at open. Work item 2.

## Work

1. **Intake.**
   - Register `single_l2_texto` as a query set in `run_context.py`. Build its norm / feature tables
     with the same `features.ipynb` path as `single_texto`, and record their digests.
   - Take in the SINGLE sidecar as `OE_single_modifications.jsonl` under a `DELIVERIES.md` section:
     upstream commit, digest, key match, and the agreement of S3's text detector with it (below).
   - Refresh `MANIFEST.md` by its generator.
   - Test: every L2 gold resolves; `modification_count` is 1 everywhere; no D-033 gold and no P7 or
     P8 key in dev; each sidecar row names the type its query carries.
2. **Environment.** Add pinned `statsmodels` and `matplotlib` to the sprint container, and stamp
   their versions in every generated table's sources block. No retrieval-path package moves.
3. **Run**, split `dev`, clean tree, sprint container: the 15 S4 arms × `single_l2_texto` = **15 new
   runs** (10 indexed, 2 RRF, 3 CE-blend). The identity side is each arm's existing `texto` run. No
   existing run is re-run, so D-047 does not apply. If one must be re-run, D-047 applies and the
   re-run is recorded.
4. **Analyse** with `src/utils/build_results_s6.py`, under `tests/test_generated_prose.py`, into
   `docs/synthetic-oe/results/S6/`. S4's paired-frame code is imported, not copied.
   - **T1 — L2 profile, item / parent.** S4's T2/T3 columns for the 15 arms on `single_l2_texto`
     (**L2w**). Beside it, S4's L2 pool (**L2s**, 5 concepts) and their union (**L2∪**), for
     reference.
   - **T2 — adjusted profile.** Mixed model M0 (below) per non-floor base arm: the type effects with
     model-based CIs, beside S4's raw δ.
   - **T3 — mediation.** Models M1 and M2 per non-floor base arm: residual type effects, overlap
     coefficients, and the proportion mediated with clustered CIs.
   - **T4 — normalised sensitivity.** δ / mean d_tok per layer pool, with the L1 : L3 ratio and its
     CI.
   - **T5 — D-004 sensitivity.** Every registered reading recomputed without the flagged queries.
     Flag counts per type, from the detector and from the sidecar, with their agreement.
   - **T6 — power.** Per type and per layer pool, for each non-floor base arm: n, concepts, clustered
     SE, and the smallest |δ| detectable at 80 % power, α 0.05, two-sided.
   - **T7 — predictions** R1–R6: estimate, clustered CI, concepts, raw / Holm / BH p, reading,
     tie-free and as run, clean-subset reading.
   - **T8 — provenance**: every run read, stamps, package versions.
5. **Figures 1–3, drafted**, generated by the same script into `results/S6/figures/`:
   - Fig. 1 (H1): parent against item Acc@1, identity → modified, per arm.
   - Fig. 2 (H2): retention, arm × type, with M0's adjusted effects.
   - Fig. 3 (H5): δ against overlap deficit, lexical against dense, with M1's residuals.
   Drafts, not manuscript-final; every plotted number comes from a table.
6. **Report** `SPRINT_S6_REPORT.md` resolving H1, H2 and H5, then `/audit S6` in a fresh session.

## Design constraints

- **Populations.**
  - **S4's for every `single_texto` figure**: item level 2,176 scored of 2,206 (29 D-033 golds, the
    P7 query); parent level all 2,206.
  - **L2w**: the 518 dev `single_l2_texto` queries; item level excludes D-033 golds (expected 0,
    counted).
  - Identity pairs come from each arm's `texto` run on the same golds (treatment effect on the
    treated, S4).
  - Layers reach different leaves, so every layer contrast is **between-population**, bootstrapped
    independently within each pool (S4).
- **L2w is the registered L2 population.** Its queries have never been run, so the L2 tests are
  blind. L2s has been read in S4, and L2∪ mixes seen with unseen, so both are printed and never
  read. L2 breadth is stated in every L2 sentence: **9 / 9 / 8 dev concepts** under the frozen menus,
  against a grammar ceiling of **13 dev / 12 test** (D-043).
- **Tie-free Acc@1 is primary for every registered reading** (D-028, applied to every family as it
  proposes). A third of `bm25_unigram`'s L1 hits are tie-wins (S4 T5), so an as-run δ partly
  measures key order. As-run is printed beside every reading, and any reading that differs between
  the two is flagged in T7. S4's P1–P5 were read as run; where R-tests re-read them, the difference
  is stated, not hidden.
- **Arms.**
  - **Non-floor base arms** (7): `bm25_unigram`, `bm25_unigram_params`†, `tfidf_phrases_replace`†,
    `bge_m3_colbert`, `bge_m3_dense`, `dense_e5`, `dense_es_hiiamsid`.
  - Floor arms (S4's 0.20 rule) and derived arms are profiled in T1 and carry no prediction or model.
  - † Oracle arms travel with their twin `bm25_unigram` (D-010).
- **Models**, fitted per arm at item level on paired δ_q (tie-free) over all nine `single_texto`
  types. δ is a within-leaf difference, so leaf difficulty is already differenced out.
  - **M0**: δ ~ 0 + type + (1 | concept) + (1 | leaf ∈ concept).
  - **M1**: M0 + three **overlap deficits**, each zero at identity:
    - 1 − lexical coverage;
    - 1 − numeric coverage (0 when the query holds no number, with an indicator);
    - − Δ numbers (query − gold).
  - **M2**: M0 + d_tok. It answers H5's "amount or kind" in a single covariate.
  - Definitions are S3's `build_overlap.py` for coverage, D-038 for Δ numbers and S4 for d_tok,
    imported, not re-implemented.
  - Linear mixed models (statsmodels `MixedLM`, REML, leaf as a variance component nested in
    concept). This is a linear probability model on δ ∈ [−1, 1]: its coefficients are Acc@1 units,
    comparable with S4's δ. Its model-based CIs are approximate, printed for description; **no
    reading rests on them**.
  - `modification_count` is 1 throughout `single_texto`, so the plan's count term is not
    identifiable here. It is S7/S8's, and the report says so.
- **Mediation is a decomposition, not a causal estimate.** The type fixes the rewrite, and the
  rewrite fixes the overlap. Nothing is randomised between them, so "mediated" means *attenuated by
  conditioning*. Sequential ignorability is not claimed.
  - **Proportion mediated**: PM = 1 − (Σ_t w_t β_t^{M1}) / (Σ_t w_t β_t^{M0}), where w_t is type t's
    share of item-scored queries. The residual β_t^{M1} is type t's effect at zero overlap loss.
  - PM's registered interval comes from a **concept-clustered bootstrap of the fixed-effects-only
    fits** (OLS, B = 10,000). Refitting the mixed model 10,000 times per arm is not feasible. The
    mixed PM is printed beside it as the adjusted point estimate, and a difference in sign between
    the two is reported.
  - PM is undefined when |Σ w β^{M0}| is within its own CI of 0. It is then printed "—" and read
    *not supported*.
- **Registered predictions**, read on the concept-clustered interval (D-030). Holm–Bonferroni runs
  across all 21 tests, with BH beside. **Supported** when the interval lies on the predicted side
  and Holm p < 0.05; **contradicted** in the mirror case; **not supported** otherwise (S4's rule).
  Blind or confirmatory is stated per test: S4 printed T3's collapse quantities and T4's δ / d_tok
  for every arm.
  - **R1 (H2 L1 vs L2; blind).** L1 item δ (S4 population) < L2w item δ, for `bm25_unigram` and
    `bm25_unigram_params`. 2 tests, between-population.
  - **R2 (H2 L2 concept-level; blind).** Among item losses, the share whose rank-1 lies in the wrong
    concept: L2w above L1, for `bm25_unigram` and `bge_m3_colbert`. 2 tests, between-population.
    This is S4's P5 on 9 concepts instead of 5.
  - **R3 (H5 lexical; blind).** PM > 0.5 for `bm25_unigram` and `bm25_unigram_params` (overlap
    carries most of the degradation). 2 tests.
  - **R4 (H5 lexical vs dense; blind).** PM(`bm25_unigram`) − PM(arm) > 0, for `bge_m3_colbert` and
    `bge_m3_dense` (residual larger for dense encoders). 2 tests, paired by query.
  - **R5 (H5 normalised sensitivity; confirmatory).** (δ / d̄_tok)_{L1} ÷ (δ / d̄_tok)_{L3} > 10,
    for `bm25_unigram` and `bm25_unigram_params` ("an order of magnitude"). p is taken against the
    null ratio 10. If the L3 denominator's interval contains 0, the ratio is undefined and the test
    is read *not supported*. 2 tests, between-population.
  - **R6 (H1; confirmatory).**
    - (a) The gap widens, Δ_mod − Δ_id > 0 over all nine types, for the four non-floor base arms
      S4 did not test: `tfidf_phrases_replace`, `bge_m3_dense`, `dense_e5`, `dense_es_hiiamsid`.
      4 tests.
    - (b) Discrimination falls more than concept identification,
      (D_id − D_mod) − (parent_id − parent_mod) > 0, for all 7 non-floor base arms. 7 tests.
- **H2's L3 clause is read per type** (S4 finding 4). `reorder` keeps S4's P3/P4 readings.
  `template_paraphrase` is read through M1: if its residual for the lexical arms has an interval
  containing 0, its cost is overlap, not order. That is descriptive, and the report says so.
- **How each hypothesis resolves** (the report states one line each, citing T7 rows):
  - **H1** is *supported* if S4's P1 (3 arms) and R6 hold, *contradicted* if any of those tests
    reads contradicted, *partly supported* otherwise, naming the arms.
  - **H2** is resolved per clause: L1 (S4 P2 + R1), L2 (R2), `reorder` (S4 P3/P4) and
    `template_paraphrase` (M1, descriptive).
  - **H5** is resolved per part: mediation (R3, R4) and the normalised sensitivity (R5).
- **D-004 sensitivity is a robustness check on every reading.** Flagged means an immediately
  doubled token, or the *topografía* drift (S3's detector, validated at zero across the corpus). The
  sidecar is the cross-check: a flag it contradicts is listed. Every R-test is recomputed on the
  clean subset. A reading that changes category is reported **not robust**, and the full-population
  reading stands (D-004 keeps the artefacts in).
- **P8** (D-044): every `synonym_label` cell and every model using it is shown with and without the
  four case-only queries.
- **Thin types, power note.** T6 states per type what |δ| the clustered SE can detect. No per-type
  claim is made on a cell whose detectable |δ| exceeds its observed |δ|. D-043 ruling 3 is
  **reopened by the report** if any R1/R2 test is *not supported* with a clustered interval wider
  than 0.20. That is the operational meaning of "uninformative at 9 concepts", fixed now.
- **Cells under 10 concepts carry ‡** (S4 A4). L2w's per-type cells all do (8–9 concepts).
- **Dev only.** No test query is read; L2w test text stays unread. Generated tables type no number
  into their prose. The report is typed and guarded by `tests/test_report_traceability.py`.

## Exit criteria

1. `single_l2_texto` is registered and its feature tables are built. The SINGLE sidecar is taken in
   with a `DELIVERIES.md` section. `MANIFEST.md` is regenerated. Intake tests pass, and so do the full
   suite and the OEB fixture.
2. 15 new runs exist on `single_l2_texto`: `code_dirty: false`, split `dev`, resolving under
   `check_run_inputs.py`. No earlier sprint's `results/` changes on regeneration.
3. `results/S6/` holds T1–T8 and Figs. 1–3, generated by `build_results_s6.py`, byte-identical on
   regeneration and under the prose guard.
   - Every item-level figure carries n scored and n excluded.
   - Every δ and every contrast carries its query-level and clustered CI and its concept count.
   - Every registered reading is shown tie-free and as run.
   - The package versions of the model fits are stamped.
4. M0, M1 and M2 are fitted for all 7 non-floor base arms, and each non-convergence is reported and
   not silently dropped. PM has a clustered CI or an explicit "—".
5. R1–R6 (21 tests) are each read supported, not supported or contradicted, labelled blind or
   confirmatory, with a clean-subset reading beside.
6. The report resolves H1, H2 (per clause) and H5 (per part) under the rules above. It states the L2
   breadth, 9 / 9 / 8 dev concepts against the 13 / 12 ceiling, and says whether D-043 ruling 3
   reopens.

## Out of scope

- **H3 and the structured arms**: closed in S5 (D-046). They are neither modelled nor re-run.
- **Stacked set, dose, the count term**: S7 and S8.
- **Test split**: S12. L2w test queries are registered but never run.
- **Query-side normalisation**, which H5 motivates: S9. S6 measures how much overlap explains; it
  does not repair overlap.
- **A logistic GLMM** (lme4 or Bayesian): the LPM on δ keeps S4's units, and no reading rests on the
  model-based intervals. The GLMM is an alternative S6 declines, not a gap.
- **New menus toward the 13-concept ceiling**: D-043 ruling 3, reopened only under the rule above.

## Risks

| Risk | Handling |
|---|---|
| Overlap deficits are collinear with type (L1 rewrites exactly the numbers) | PM is a decomposition, read on the bootstrap; M1's coefficients are printed with their correlation matrix; no claim rests on one deficit's coefficient |
| MixedLM fails to converge on a sparse leaf variance component | Report it, refit without the leaf component, mark the row; readings do not rest on model CIs |
| "Blind" L2w tests drift after T1 is seen | R1/R2 are frozen here; T1 and T7 are generated in the same run |
| Tie-free primary moves an S4 reading | Both shown; S4's reading stands as S4's, the S6 reading is what H1/H2 resolve on, and the difference is stated |
| Sidecar and detector disagree | Listed in T5; the detector (validated in S3) stays primary, the disagreement is a finding for `DATASET_DEFECTS.md` |
| Power too low for any L2 type claim | T6 states it; L2 is read pooled; D-043 ruling 3's reopening rule |

## Amendments

In [`SPRINT_S6_AMENDMENTS.md`](SPRINT_S6_AMENDMENTS.md), append-only (D-045).
