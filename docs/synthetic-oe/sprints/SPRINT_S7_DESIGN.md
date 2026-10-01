# Sprint S7 — E2 stacked headline and stratifications · design

> **Frozen at:** `5e89809` · `2026-10-01`
> This document is read-only from that commit. Changes go in
> [`SPRINT_S7_AMENDMENTS.md`](SPRINT_S7_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S7` · backbone |
| **Status** | planned → active |
| **Serves** | H1 (widening collapse) in the realistic regime; the sibling-density law (proposal E5). H4 only descriptively — see Design constraints |
| **Depends on** | S6 (`done`); upstream: corrected stacked set `c34a222a…` (D-033 intake, landed 2026-09-27) |
| **Decisions applied** | D-004, D-010, D-025, D-028, D-030, D-032, D-033, D-045, D-046, D-047, D-048 |
| **Effort** | 1 week |
| **Predecessor / successor** | S6 / S8 |

## Goal

At the end of S7 we will know the realistic-regime number: how much item-level accuracy each Track A
and Track B arm keeps when every applicable modification is stacked on a query, against its own
identity on the same leaves, and whether parent level holds while it falls (H1 on `all_combined`).
We will also know whether that loss **scales with sibling density** — whether a gold in a larger family
loses more — which is the proposal's E5 prediction and has never been tested. S2 read stacked for five
arms on a dose field later found to be wrong; S7 reads all eighteen, tie-free, on the corrected field.

## Entry state

Checked in the tree on 2026-10-01, not taken from the registry:

- **S6 `done`**: `SPRINT_S6_AUDIT.md` **PASS WITH FINDINGS**, all six resolved (report §Audit
  response). HEAD `9fceb67`, tree clean, branch `research/synthetic-oe`, main checkout.
- **Corrected stacked set in place.** `OE_stacked_texto.json` re-hashed: `c34a222a…`, matches
  `MANIFEST.md`; carries `texto_modification_count` / `texto_modification_types`. The superseded
  `__1bde2115` JSON and its `__81cd501b` / `__7b0894e6` tables are present under versioned names.
  Current tables: `OE_stacked_texto_feats.parquet` `f34c1798…`, `_norm` `4939d99f…` (derived; no
  upstream digest, as `MANIFEST.md` records).
- **Dev stacked population, counted**: 2,521 queries, 2,521 distinct golds, 41 concepts. Distinct
  TEXTO dose (`texto_modification_count`) 2–6: 593 / 546 / 936 / 370 / 76 queries over 29 / 18 / 8 /
  2 / 1 concepts. `reorder` in 0 records; `template_paraphrase` in all 2,521. Subchapters: OEB 1,794
  queries (13 concepts), OED 475 (9), OEC 114 (5), OEA 97 (9), OEG 35 (3), OEE 3 (1), OEF 3 (1).
  Family-size terciles (SPLITS boundaries 72 / 432): 2,321 queries sit in large families.
- **Existing stacked runs are S2's**, all stamped against the superseded table `7b0894e6…`: the two
  BM25 operating-point arms (plus S3's 50-cell sweep, which S7 does not touch), `bge_m3_colbert`,
  `structured_pipeline_rules`, `structured_pipeline_rules_valuenorm`. The other 13 arms have no
  stacked run. All 15 S4 arms and the three S5 structured arms have a `texto` run.
- **Runs**: 231 `runs/OE/*/*/run_meta.json`, **0** with `code_dirty: true`. All ten indexed arms
  and the three structured arms have `index/OE/<arm>`.
- **Within-leaf additivity is not available on stacked**: of the 2,521 dev stacked queries, 26 have
  every one of their TEXTO types also present as a `single_texto` query on the same gold; 1,529 have
  none. This fixes H4's role below.

## Work

1. **Intake check, no new data.**
   - Assert the corrected and superseded stacked files agree on `parameters` as well as on `text`,
     `id`, `item_key`, `gold_item_key` (the 2026-09-27 test checked the latter four only). The oracle
     arms read `parameters`; a difference stops the sprint for an amendment.
   - **Undecidable-query check** (S4 work item 4, D-040's scope clause): count dev stacked queries
     whose text equals another dev leaf's `texto` or another dev stacked query's text. Any → stop and
     amend, naming the set; none → record the zero.
   - Count D-033 golds in dev stacked (expected 55) and P7 / P8 keys (expected 0: both are `single`).
2. **Archive** S2's five stacked runs to `runs/_archive/S2/OE/stacked_texto/` with `SHA256SUMS`, and
   route their readers through `utils/archived_runs.py` (D-047). `results/S2/` and
   `results/S3/s2_rescored/` must regenerate byte-identically afterwards.
3. **Run**, split `dev`, clean tree, sprint container, on `stacked_texto` (`f34c1798…`): the **15 S4
   arms** (10 indexed, 2 RRF, 3 CE-blend; components first) and the **3 S5 structured arms**
   (`rules`, `rules_valuenorm`, `oracleparams_valuenorm`) = **18 runs**, every parameter as frozen in
   S4/S5. Nothing is tuned.
4. **Regression against S2.** For the five re-run arms, compare per-query rank-1 with the archived run
   on the 2,521 queries. Texts are unchanged, so the text-only arms must agree except on exact-score
   ties; every disagreement is classified (tie / code change since S2 / unexplained). An unexplained
   one stops the sprint for an amendment.
5. **Analyse** with `src/utils/build_results_s7.py` into `docs/synthetic-oe/results/S7/`, under
   `tests/test_generated_prose.py`. S4's paired frames and S6's tie-free and clustered-bootstrap code
   are imported, not copied.
   - **T1 — headline.** 18 arms: identity and stacked item Acc@1 (tie-free and as run, n scored /
     excluded, ceiling per D-032), parent Acc@1, δ, retention, Δ = parent − item, D = P(item | parent),
     right-parent / wrong-item rate. Query-level and clustered CI, concept count.
   - **T2 — single-edit reference.** Each arm's stacked δ beside its pooled `single_texto` δ (S4) and
     L2w δ (S6 T1). Between-population: printed, never read as a contrast.
   - **T3 — subchapter.** T1's item and parent columns per subchapter.
   - **T4 — sibling density.** Per family-size tercile; the W3 slopes (below), unadjusted and adjusted;
     and a leaf-level density, the gold's count of same-concept siblings differing on exactly one
     axis (from `OE_concept_schema.json`), as a descriptive covariate.
   - **T5 — dose, descriptive.** δ by `texto_modification_count`, with `modification_count` beside it
     (D-025), and the concepts in each cell.
   - **T6 — type presence, descriptive.** δ split by whether the mix contains each type (L1 types and
     `synonym_label` first; S6 finding 5). Strata overlap and are confounded; no effect is claimed.
   - **T7 — D-004 sensitivity.** Every W-reading on the clean subset (S3's detector).
   - **T8 — predictions** W1–W3. **T9 — provenance.**
6. **Figures, drafted**, by the same script into `results/S7/figures/`: Fig. 4, parent against item,
   identity → stacked, per arm; Fig. 5, per-concept δ against log₂ family size per non-floor base arm.
7. **Report** `SPRINT_S7_REPORT.md`, then `/audit S7` in a fresh session.

## Design constraints

- **Population.** Dev stacked, 2,521 queries over 41 concepts. Item level excludes D-033 golds and any
  query found by work item 1, with n excluded beside every figure; parent level excludes nothing.
  Test stacked queries are never read.
- **Paired against identity on the same leaves** (treatment effect on the treated, S4): the identity
  side of every δ is the arm's `texto` run restricted to the 2,521 stacked golds, never its all-dev
  identity figure.
- **Retention, not δ, sets arms side by side** (S4): δ is bounded by each arm's identity on the
  treated leaves.
- **Floor arms**: identity item Acc@1 on the treated leaves below 0.20 (S4's rule, recomputed on these
  leaves). Reported in every table, excluded from every reading; parent level always reported.
- **Oracle arms travel with their twins** (D-010): `bm25_unigram_params` and `tfidf_phrases_replace`
  with `bm25_unigram`, the oracle RRF with the deployable one, `oracleparams_valuenorm` with
  `rules_valuenorm`. On stacked the oracle reads a `parameters` dict whose values are rewritten.
- **Structured arms are profiled, not tested.** H3 is closed (D-046); they appear in T1–T7 only.
- **Tie-free Acc@1 is primary for every reading** (D-028 note), as run beside it; a reading that differs
  between the two is flagged in T8.
- **The dose field is `texto_modification_count`** (D-004/D-025 note: the original field overstates the
  visible dose). Every dose figure names its field.
- **The stacked set is not a balanced crossing** (D-002, D-009): no `reorder`, `template_paraphrase`
  everywhere. T5 and T6 are descriptive, and the report states in its own words that E2 **cannot
  identify interactions** — so that no interaction claim can enter the manuscript from S7.
- **H4 is not tested in S7.** Dose varies between concepts (29 concepts at dose 2, one at 6), so a
  stacked dose slope is a concept contrast; and within-leaf additivity is reachable for 26 queries.
  S8's nested ladder answers H4 within leaf. S7's T5 is the exploratory regression the plan's fallback
  describes, printed and never read as H4.
- **No mixed model** (D-048). Inference is the paired, concept-clustered bootstrap, B = 10,000.
- **Registered predictions**, 21 tests, read on the concept-clustered interval (D-030), Holm across all
  21, BH beside. Supported / contradicted / not supported by S4's rule. Arms: S6's seven non-floor base
  arms — `bm25_unigram`, `bm25_unigram_params`†, `tfidf_phrases_replace`†, `bge_m3_colbert`,
  `bge_m3_dense`, `dense_e5`, `dense_es_hiiamsid` — minus any that fall under the floor on these
  leaves, which is then read *not tested* and stated.
  - **W1 (H1, gap widens).** Δ_stk − Δ_id > 0. 7 tests. Confirmatory for `bm25_unigram`,
    `bm25_unigram_params`, `bge_m3_colbert` (S2 printed their stacked levels); blind for the other four.
  - **W2 (H1, discrimination falls more than concept identification).**
    (D_id − D_stk) − (parent_id − parent_stk) > 0. 7 tests, labelled as W1.
  - **W3 (E5, sibling density).** Slope of the paired item δ_q (tie-free) on log₂ family size > 0:
    larger families lose more. Linear probability model at query level, interval by concept-clustered
    bootstrap (41 clusters), p against slope 0. 7 tests. Confirmatory for the three S2 arms (their S2 runs carry
    family-tercile slices), blind for the other four.
    - **Robustness, fixed now**: refitted with mean-centred `texto_modification_count` and an
      L1-present indicator as covariates. A reading that changes category under adjustment is reported
      **not robust**; the unadjusted reading stands as registered.
    - Family size is confounded with subchapter (OEB holds the three 6,336-leaf families). A within-OEB
      slope (13 concepts) is printed, descriptive.
- **How H1 resolves here.** On stacked, H1 is *supported* if W1 and W2 hold for every tested arm,
  *contradicted* if any reads contradicted, *partly supported* otherwise, naming arms. S6's resolution
  on single edits stands as S6's; the report states whether stacking agrees with it.
- **D-004.** Every W-reading recomputed without flagged queries; a category change is *not robust*, and
  the full-population reading stands (D-004 keeps the artefacts in).
- **Cells under 10 concepts carry ‡** (S4 A4); OEE and OEF (3 queries, 1 concept each) are printed,
  never read.
- **Dev only.** Generated tables type no number into their prose; the report is guarded by
  `tests/test_report_traceability.py`.

## Exit criteria

1. Work item 1's three checks are recorded with their counts, and any stop has its amendment.
2. S2's five stacked runs are archived with checksums; `results/S2/` and `results/S3/s2_rescored/`
   regenerate byte-identically after the move.
3. 18 runs exist on `stacked_texto` at `f34c1798…`: `code_dirty: false`, split `dev`, resolving under
   `check_run_inputs.py`. The work-item-4 regression lists every rank-1 disagreement with its class and
   no unexplained one.
4. `results/S7/` holds T1–T9 and Figs. 4–5, generated by `build_results_s7.py`, byte-identical on
   regeneration and under the prose guard. Every item-level figure carries n scored and n excluded;
   every δ and contrast its query-level and clustered CI and concept count; every reading tie-free and
   as run.
5. W1–W3 (21 tests) are each read supported, not supported, contradicted or not tested, labelled blind
   or confirmatory, with the clean-subset and (W3) adjusted readings beside.
6. The report states the headline, resolves H1 on stacked under the rule above, states the sibling-
   density verdict, and carries the not-a-crossing and no-H4 statements verbatim in substance.
7. Full suite and the OEB fixture pass.

## Out of scope

- **H4** and any interaction claim: S8, on the nested ladder (D-009).
- **H3**: closed (D-046). **H5** on stacked: S6 measured it on single edits; not repeated.
- **Re-tuning**: the S3 sweep's stacked cells stay as S3's record and are not re-run.
- **Test split**: S12.
- **A type × concept mixed model** (D-048 debt): not needed for any W-test.

## Risks

| Risk | Handling |
|---|---|
| Corrected file differs in `parameters` from the superseded one | Work item 1 checks before any run; a difference is an amendment |
| Re-runs disagree with S2 beyond ties | Work item 4 classifies each; unexplained stops the sprint |
| Family size collinear with subchapter and dose | Adjusted refit and within-OEB slope, both fixed now; the unadjusted slope is what is registered |
| 41 clusters dominated by three OEB families | Stated; the per-concept Fig. 5 shows the leverage; no reading rests on the query-level interval |
| An arm falls under the floor on stacked golds | Read *not tested*, stated; Holm still runs over 21 |
| CE-blend runtime on 2,521 queries × 3 | `_ce_cache` exists; budgeted within the week |
| Stacked dose read as H4 | T5 descriptive, H4 sentence required in the report; the auditor checks it |

## Amendments

In [`SPRINT_S7_AMENDMENTS.md`](SPRINT_S7_AMENDMENTS.md), append-only (D-045).
