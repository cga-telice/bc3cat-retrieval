# Sprint S5 — E1 ablation, Track B (structured) · design

> **Frozen at:** `432b39e` · `2026-09-30`
> This document is read-only from that commit. Changes go in
> [`SPRINT_S5_AMENDMENTS.md`](SPRINT_S5_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S5` · backbone |
| **Status** | planned → active |
| **Serves** | H3 (rank inversion); gate G2 |
| **Depends on** | S4 (`done`); S2's structured port and runs (D-026); no upstream delivery |
| **Decisions applied** | D-004, D-010, D-026, D-028, D-029, D-030, D-032, D-033, D-043 (P7), D-044 (P8), D-045 |
| **Effort** | 1 week |
| **Predecessor / successor** | S4 / S6 |

## Goal

At the end of S5 we will know whether the structured method the previous study **published** — the
three-stage rules pipeline — overtakes tuned BM25 once the query is rewritten, over all nine
modification types rather than S2's two, with the ordering advantage its Stage 3 gets from sorted
keys removed. We will also know how far the approach could go at best: an oracle-extraction bound
that hands Stage 3 the query's own parameters. That bound separates "the extractor is weak" from
"reading schema literals cannot work under L1", which is the question G2 needs answered.

## Entry state

Checked in the tree on 2026-09-30, not taken from the registry:

- **S4 `done`**: registry row and log; `SPRINT_S4_AUDIT.md` re-audit verdict PASS WITH FINDINGS,
  all six resolved. HEAD `7cd2c64`, tree clean.
- **S4's reference runs**: 130 run directories under `runs/OE/{texto,single_texto}/`, all
  `split: dev`, all `code_dirty: false` (checked over every `run_meta.json`).
- **S2's structured runs**: `structured_pipeline_rules__OE` and `…_rules_valuenorm__OE` on `texto`
  and `single_texto`, clean at `31bf1a1`; their stage table is `results/S2/structured_stages.md`.
- **Stage-1 index** `index/OE/dense_e5__OE` present.
- **Digests re-hashed, match `MANIFEST.md`**: `OE_long_feats` `643f1a72`, `OE_single_texto_feats`
  `e5b79ae4`, `OE_texto.json` `02a2c270`, `OE_concept_schema.json` `2d3273dd`, sidecar
  `OE_duplicate_texto_groups.json` `b3cfcad4`. `OE_long_norm` `75477221` matches the S4 stamps.
- **Not ready**, and therefore work: the oracle mode is not ported — `structured_pipeline.load`
  raises `NotImplementedError` on `oracle`.
- **Recorded at the freeze**: D-028 and D-029 existed only in the S2 report; both are appended to
  `DECISIONS.md` in the freeze commit, unchanged in substance.

## Work

1. **Arm set** (César, 2026-09-30). Stage 1 = item-level `dense_e5__OE`, top-1 parent, throughout.
   - **`structured_pipeline_rules_valuenorm__OE`** — reused (S2). The published method with the
     Stage-3 decimal-comma defect fixed (S2 A1). **Deployable. The arm every claim rests on.**
   - **`structured_pipeline_rules__OE`** — reused (S2). The faithful port, printed for comparability
     with the previous study's 0.903; no claim rests on it.
   - **`structured_pipeline_oracleparams_valuenorm__OE`** — new. **Oracle bound** (D-010). Stage 2 is
     replaced by the query record's own flat `parameters`, mapped to the concept's schema values by
     the same case-insensitive, valuenorm'd comparison Stage 3 uses; a value not in the axis's
     schema list is an abstention on that axis. On `texto` and L2/L3 it is the gold's full
     fingerprint; on L1 exactly the rewritten axis abstains. It is the best any extractor that
     reads schema literals could do.
2. **Port the oracle-params mode** into `structured_pipeline.load` with its config, declaring
   `collection` and an explicit `retriever` block. No new extractor code is ported (see Out of scope).
3. **Test before any run**: on 20 `texto` dev leaves the oracle mode returns every gold axis and the
   gold as the unique match; on 20 L1 queries it abstains on exactly one axis. Full suite and the
   OEB fixture pass.
4. **Run**, split `dev`, clean tree, sprint container: `oracleparams` × {`texto`, `single_texto`} =
   **2 new runs**. The four S2 rules runs are reused, justified by a recorded retrieval-path diff
   (S4's procedure); a changed path means re-running that arm, recorded. S4's 15 arms are read, not
   re-run.
5. **Analyse** with `src/utils/build_results_s5.py`, under `tests/test_generated_prose.py`, into
   `docs/synthetic-oe/results/S5/`:
   - **T1 — ceilings.** `oracleparams` identity item and parent Acc@1, field ceiling, headroom
     (D-032); the rules arms' ceilings from their S2 runs, recomputed on S4's population.
   - **T2 / T3 — profile, item / parent.** The three structured arms × nine types, layer pools, all;
     S4's columns exactly (n, n scored, n excluded, concepts, identity on the treated leaves,
     modified, δ with query-level and clustered CI, retention, flips; parent adds the collapse
     quantities). Item Acc@1 twice: **as run** and **tie-free** (below).
   - **T4 — stages.** S2's `structured_stages.md` columns for the three arms on S4's population,
     plus Stage-3 match size (median, IQR), per type.
   - **T5 — H3 contrasts.** Each structured arm against `bm25_unigram`, `bm25_unigram_params` and
     `bge_m3_colbert`: paired Acc@1 difference at identity (treated leaves), under modification, and
     the difference-in-differences, per type, per layer pool, and all.
   - **T6 — predictions** Q1–Q3 with estimate, clustered CI, concepts, raw / Holm / BH p, reading.
   - **T7 — provenance**: every run read, stamps, reuse diffs.
6. **Report** `SPRINT_S5_REPORT.md` with the H3 and G2 readings, then `/audit S5` in a fresh session.

## Design constraints

- **Populations are S4's.** Item level: dev `single_texto` minus the 29 D-033 golds and the one P7
  query, **2,176 scored of 2,206**; parent level all 2,206. The identity side of every pair is read
  from the arm's own `texto` run restricted to the same golds. Ceilings (T1) on the 35,422 identity
  queries, 776 D-033 excluded at item level.
- **Contrasts are paired by query.** Both arms of a T5 contrast answered the same query; the
  difference is taken per query and bootstrapped by concept. The DiD per query is
  (s_q − b_q) − (s_id(g) − b_id(g)) = δ_s − δ_b. Arms are compared on **Acc@1**, because H3 is a
  claim about the ranking of methods; retention is printed beside and is what any sentence about
  robustness (as opposed to ranking) quotes.
- **Tie-free reading is primary for every H3 contrast** (D-028). Stage 3 returns a matched
  sub-family in `item_key` order, which S2 measured as worth about +0.05 to the structured arms at
  identity by ordering alone. A query's tie-free Acc@1 is the expectation under a uniform tie-break
  over its rank-1 tied set: 1/|set| if the gold is in it, else 0. For structured arms the set is the
  tier-1 match; for score-based arms the rank-1 score tie, as in S4 T5. Exact, no seed. As-run Acc@1
  is printed beside, never read alone.
- **What is not blind, and is said so.** The rules arms' as-run Acc@1 per type is already printed in
  `results/S2/structured_stages.md`, and S2 read `unit_conversion` and `num_to_text` against BM25.
  Q1 and Q3 are therefore **confirmatory re-readings**, not blind predictions: their tie-free values,
  the pooled L1 cell and S4's population have not been computed. The report labels them so. Q2 is
  blind: `oracleparams` has never run.
- **Oracle arms travel with twins** (D-010). `oracleparams` is quoted beside `rules_valuenorm`;
  `bm25_unigram_params` beside `bm25_unigram`. No sentence quotes an oracle figure alone. The
  **deployable** contrast of H3 is `rules_valuenorm` vs `bm25_unigram`. The previous study's
  contrast (0.903 vs 0.974) is structured vs `bm25_unigram_params`, deployable vs oracle on
  synthetic queries (D-010 note); printed and labelled as such.
- **ColBERT is printed, not predicted.** It is the L1 reference (D-029); H3 names lexical methods.
  Its contrasts are in T5 with their CIs; no reading is taken on them.
- **Registered predictions**, clustered interval, Holm–Bonferroni across the 9 tests, BH beside.
  **Supported** when the interval lies above 0 and Holm p < 0.05; **contradicted** in the mirror
  case; **not supported** otherwise (S4's rule). Tie-free Acc@1 throughout.
  - **Q1 (H3, inversion, published method).** Under modification, `rules_valuenorm` −
    `bm25_unigram` > 0 on pooled L1, on `unit_conversion` and on `num_to_text` (the two types H3
    names). 3 tests. Confirmatory.
  - **Q2 (H3, bound).** `oracleparams` − `bm25_unigram` > 0 on the same three cells. 3 tests. Blind.
  - **Q3 (H3, gap closes).** DiD `rules_valuenorm` vs `bm25_unigram` > 0 on pooled L1, L2 and L3
    separately. H3 predicts closing on L1 only; closing on L2/L3 too would mean the pipeline is
    simply less sensitive to rewriting, not better at parameters. 3 tests, between-population
    across layers. Confirmatory.
  - The same contrasts against `bm25_unigram_params` are printed in T5, not tested.
- **G2 is read here, once, on dev.** **Yes** (the structured/lexical ranking inverts) if Q1's
  pooled-L1 test is supported; **no** if contradicted, or not supported with a point estimate ≤ 0;
  **ambiguous** otherwise, recorded as such and not rounded (D-030). Q2 is printed beside the G2
  reading as its interpretation: if even the oracle bound does not overtake BM25 under L1, reading
  schema literals is the limit, and any structured route (S11) needs a value-reading step (S9)
  first. The plan's consequence (G2 "no" moves priority from S11 to S10) is César's to confirm in the
  report; S5 reorders no sprint itself.
- **Mechanism is read from T4, descriptively.** For each L1 type: share of queries (Stage 1 correct)
  recovering every gold axis, abstentions, misreads, match size. Under the oracle, L1 match size is
  the rewritten axis's value count, which is what the tie-free reading divides by.
- **Layers are different leaves.** Any layer contrast is between-population. L2 reaches **5 of 42**
  dev concepts on this set; every L2 figure says so; any cell or pool under 10 concepts carries ‡
  (S4 A4). The wider L2 set is S6's (D-043).
- **Carried caveats.** P8: `synonym_label` cells shown with and without the four case-only queries
  (D-044). D-004 pantry artefacts stay in; their sensitivity is S6's. The decimal artefact reaches
  the rules extractor through normalised text: counted per cell as in S4 T4.
- **Dev only.** No test query is read. No typed numbers in the generated tables' prose; the report
  is typed and guarded by `tests/test_report_traceability.py`.

## Exit criteria

1. The oracle-params mode, its config and its tests are committed; the full suite and the OEB
   fixture pass.
2. 2 new runs exist, `code_dirty: false`, split `dev`, resolving under `check_run_inputs.py`. The
   reuse of the four S2 runs is justified by a recorded retrieval-path diff.
3. `results/S5/` holds T1–T7, generated by `build_results_s5.py`, byte-identical on regeneration,
   under the prose guard. Every item-level figure carries n scored and n excluded; every δ and every
   contrast its query-level and clustered CI and its concept count; every H3 contrast its tie-free
   and as-run values.
4. The profile covers 3 structured arms × 9 types at both levels plus three layer pools, no empty
   cell unexplained; T5 covers each structured arm against the three reference arms.
5. Q1–Q3 are each read supported, not supported or contradicted under the rule above, and Q1/Q3 are
   labelled confirmatory.
6. The report reads G2 as yes / no / ambiguous citing the T6 row it rests on, with Q2 beside it, and
   has an H3 movement line stating what S6 still owes it.

## Out of scope

- **LLM extraction** (the structured branch's `param_extractor.py`, Phi-4 / Llama prompts). It was
  explored there on ≤ 50 queries and never published; the published method is rules. As a way of
  reading free-text parameters it belongs to **S9** (slot-filling), where it is compared with
  normalisation and rewriting; `RESEARCH_PLAN.md` S9 records it in the freeze commit.
- **Stacked set**: S7, which re-runs every arm on the corrected stacked file (`c34a222a`); S2's
  stacked runs read the superseded `7b0894e6` table.
- **Oracle-parent variants**: Stage 1 is ≥ 0.97 on every single type in S2, and T4 conditions
  Stages 2–3 on Stage 1 being correct, which answers the same question without a run.
- **New extractor rules, value normalisation in Stage 2**: tuning on dev, or S9's query-side
  normalisation.
- **A stable tie-break in Stage 3**: measured by the tie-free reading; fixing it is S11 territory.
- **Mixed model, mediation, D-004 sensitivity, the wider L2 set**: S6. **Test split**: S12.

## Risks

| Risk | Handling |
|---|---|
| Stage-3 ordering flatters the structured arms | Tie-free reading primary for every contrast (D-028) |
| Rules results already seen bias the reading | Q1/Q3 labelled confirmatory; Q2, the only blind test, is on an unrun arm |
| Reused S2 runs no longer match the code path | Recorded retrieval-path diff; re-run on any change |
| Oracle mapping of a rewritten value succeeds by accident (e.g. a label that equals another value) | T4 counts misreads under the oracle per type; a non-zero count is reported and explained |
| G2 read on a thin L1 cell | Pooled L1 carries G2; `num_to_text` rests on 9 concepts, and any cell under 10 carries ‡ |

## Amendments

In [`SPRINT_S5_AMENDMENTS.md`](SPRINT_S5_AMENDMENTS.md), append-only (D-045).
