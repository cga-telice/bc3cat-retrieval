# Sprint S11 — Track E: two-stage architecture · design

> **Frozen at:** `<commit SHA>` · `<date>`
> This document is read-only from that commit. Changes go in
> [`SPRINT_S11_AMENDMENTS.md`](SPRINT_S11_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- SPRINT_S11_DESIGN.md` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S11` · backbone |
| **Status** | planned → active |
| **Serves** | O4 (method contribution, Track E); D-046's value-reading route; D-056's key-tolerant variant, registered here |
| **Depends on** | S6 (`done`); S9 (`done`): the extractor port, its generation cache, A7's key-tolerant runs, canonicaliser C; local ollama 0.17.7 with `phi4`; BGE-M3 server for ColBERT query encoding |
| **Decisions applied** | D-004, D-008, D-010, D-026, D-028, D-030, D-033, D-040, D-045, D-046, D-047, D-053, D-056 |
| **Effort** | 2 weeks |
| **Predecessor / successor** | S9 / S12 (S10 is blocked on its training set, D-058, and is independent) |

## Goal

Every encoder S4–S8 tested finds the right concept and loses the leaf. At the end of S11 we will know whether
an architecture that takes the concept from a first stage and then **resolves the leaf inside the family**
recovers item-level accuracy under rendering variation, by how much over the best single-stage arm, which part
of the second stage does the work, and at what cost per query. The second stage has three parts:

- read the parameter values from the query;
- match them to the family's leaves, tolerating misreads;
- order what remains with a within-family score.

S9's post-hoc variant (A7) suggests a large effect: on dev `stacked_texto`, item Acc@1 0.6780 against
ColBERT's 0.4128 (`results/S9/extraction.md`, `results/S7/headline.md`). But it was found after the fact, ranks its matches in catalogue order, and has never been
tested on a set it was not developed on. S11 registers it, isolates its parts, and reads it blind where that
is still possible.

## Entry state

Checked in the tree on 2026-10-04, not taken from the registry:

- **S6 `done`** (audit PASS WITH FINDINGS, all resolved) and **S9 `done`** (D-055 amended, D-056 and D-057
  accepted by César on 2026-10-03). HEAD `be33694`, tree clean, branch `research/synthetic-oe`, main checkout.
- **Pipeline code present.** `src/retrievers/structured_pipeline.py`: Stage 1 is `dense_e5`'s top-1 concept,
  Stage 2 is rules, oracle or LLM (`phi4`, `extract` mode, schema axes and values shown in the prompt), Stage 3
  is `CatalogLookup` hard-filtering the family. `_build_ranking` puts matched leaves in **catalogue order**,
  then the rest of the family, then E5 fill. No within-family score exists.
- **Generation cache present** for the five S9 bases (10,575 extractions, `phi4`, 1.03 s per query median,
  `results/S9/cost.md`). A7 read the same cache. The axis-key match is still exact in the code; D-056's label
  stripping is not in the harness.
- **First-stage evidence.** On dev `stacked_texto`, parent Acc@1 is 0.9845 for `dense_e5`, 0.9837 for ColBERT
  and 0.9722 for the pipeline (`results/S7/headline.md`). On the E3 ladder all three keep the concept at rung 5
  (S8, finding 7).
- **E3 dev sets present.** `OE_dose_texto` has 1,640 dev queries and `OE_isolated_texto` 2,952, over the same
  328 leaves in 4 OEB concepts. No LLM has ever been run on them.
- **Canonicaliser C** (`src/query_rewrite/canon.py`) and the ColBERT index (`index/OE/bge_m3_colbert__OE`)
  are present.
- **Not present:** a within-family scorer; soft matching; label stripping; a two-stage config family.

## Work

1. **Harness.**
   (a) **D-056.** Axis labels are stripped and compared in A7's tolerant form (case-folded, accents removed,
   `_` and `-` read as spaces, surrounding spaces trimmed) wherever a response key is matched to a schema axis.
   This is the A7 rule, now registered. A test holds that it reproduces A7's per-base axis counts in
   `results/S9/extraction.md` exactly.
   (b) **Within-family scorer.** Given a concept and a query, score every leaf of the family with ColBERT
   MaxSim. Document vectors come from the existing index; the query is encoded by the BGE-M3 server. The
   scorer must reproduce ColBERT's own scores for the leaves in its stored top-100. The run fails if not.
   (c) **Soft match.** Instead of filtering, Stage 3 scores each leaf by the number of extracted axes it agrees
   with. Abstained axes count for no leaf. Values are compared after `normalize_param_string`, as
   `value_match: normalized` does.
   (d) **Ranking.** The tier order stays (matched, rest of family, fill). Inside each tier, leaves are ordered by
   the within-family score instead of catalogue order. Under soft match the tiers are the agreement counts,
   descending.
2. **Generation.** Run `phi4` on the dev E3 sets (4,592 queries, about 1.5 h at S9's rate), with the same
   prompt, cache and options as S9 and nothing changed. A 100-query regeneration check repeats S9's 1c.
3. **Arms.** All share Stage 1 (`dense_e5` top-1 concept), so their parent-level accuracy is identical by
   construction and only the leaf inside the family differs.

   | Arm | Stage 2 | Stage 3 | Order inside tiers | Role |
   |---|---|---|---|---|
   | **K0** `llm_keytol_hard` | `phi4`, tolerant keys | hard filter | catalogue | A7 as registered: reference, seen on dev |
   | **K1** `llm_keytol_hard_colbert` | `phi4`, tolerant keys | hard filter | ColBERT | isolates the order |
   | **K2** `llm_keytol_soft_colbert` | `phi4`, tolerant keys | soft match | ColBERT | **the proposed method** |
   | **R2** `rules_canon_soft_colbert` | C, then rules | soft match | ColBERT | no LLM: the cheap route |
   | **F1** `colbert_in_concept` | none | none | ColBERT | the constraint alone, without reading values |

4. **Run**, split `dev`, clean tree, sprint container. There are seven bases: the five S9 bases over U
   (`texto_u`, `resumen_u`, `single_texto`, `single_l2_texto`, `stacked_texto`) plus `dose_texto` and
   `isolated_texto` (dev).
   - K1, K2, R2 and F1 run on all seven bases: 28 runs.
   - K0 runs on the two E3 bases only: 2 runs. Its five S9 runs are reused by computed diff after the
     harness change in 1a. A diff that is not identical is recorded as an amendment, and K0 is re-run on
     those bases.
   - **30 new runs.** References are the existing runs on the same queries: ColBERT, `dense_e5`,
     `bm25_unigram`, `rules_valuenorm`, and S9's registered LLM arm. Nothing is tuned.
5. **Analyse** with `src/utils/build_results_s11.py` into `results/S11/`, under the prose guard, importing
   S6's tie-free scoring, S2's bootstrap and S8's D-053 sign rule.
   - **T1 — profile.** Per arm × base: item and parent Acc@1 (tie-free, and as run), n scored, n excluded,
     concepts.
   - **T2 — contrasts.** Each registered contrast, paired, with clustered and query-level intervals.
   - **T3 — stage decomposition**, as S5's T4. Columns:
     - Stage-1 concept correct;
     - axes extracted, abstained and misread;
     - gold in tier 1;
     - tier-1 size;
     - gold rank inside its tier.

     This shows whether an arm's errors are in reading, in matching or in ordering.
   - **T4 — by type and layer** on `single_texto`. **T5 — E3 ladder** by rung, under D-053.
   - **T6 — cost**: seconds per query per stage (generation from the cache sidecars, scoring from
     `run_meta.json`), beside `bm25_unigram` and ColBERT.
   - **T7 — D-004.** **T8 — predictions.** **T9 — provenance**, including model digest and prompt SHA.
6. **Figure, drafted:** Fig. 8, item Acc@1 per base for K2, R2, ColBERT and `bm25_unigram`, with intervals.
7. **Report**, then `/audit S11` in a fresh session.

## Design constraints

- **Paired, always.** Every contrast is between two arms on the same queries and the same scoring population.
  Between-base comparisons are labelled between-population. A δ against identity is reported only as S4
  defines it.
- **Same first stage.** All five arms take Stage 1 from `dense_e5`. A gain is therefore attributable to the
  second stage, not to a better concept. Parent level is reported to show it is unchanged, never as a
  finding.
- **What is seen and what is blind.**
  - K0's dev figures on the five S9 bases were seen before this design (S9 A7). Any K0 reading there is
    **not blind** and is labelled so.
  - The design of K1, K2 and R2 was informed by A7's numbers and by S5's tie sets (median 4 leaves).
    Nothing about them has been run.
  - The **E3 ladder** has never been seen by any LLM arm, so it is the blind population for every arm here.
  - All dev figures are **in-sample** with respect to the tolerant-key rule and to C's rules. Their
    held-out reading is S12's.
- **What the second stage may read.** The query text, the concept's schema (axis names and values, which a
  deployed system has) and the indexed corpus. It never reads the query record's `parameters`,
  `modification_types` or gold, the rewrite menus, or the sidecars. The `phi4` prompt was chosen on OEB
  `resumen`, whose concepts sit on both sides of OE's split. That exposure is stated with every figure.
- **Oracle arms are references only.** `bm25_unigram_params`†, `tfidf_phrases_replace`† and S5's
  `oracleparams`† are printed and never tested (D-010).
- **Scoring.** D-033 everywhere; D-040 on `resumen_u`; P7/P8 as in S4. **Tie-free Acc@1 is primary** (D-028
  note). K0's catalogue order is not a score, so its tier 1 is scored as one tie set, as S5's tie-free reading
  does for the structured arms. A reading that differs from the as-run reading is flagged.
- **Inference.** Concept-clustered percentile interval, B = 10,000, seed 20260917 (D-030), with the
  query-level interval beside it. Cells below 10 concepts carry ‡ and are not read. **On the E3 ladder (4
  concepts), readings use D-053**: a concept-stratified leaf bootstrap plus the 3-of-4 sign rule, scoped to
  those concepts.
- **Floor arms** are excluded from tests as in S6.
- **Registered predictions**, item level, tie-free, Holm across all 11, BH beside. Blind unless marked.
  - **A1 (the method beats the best single stage).** K2 − ColBERT > 0 on `stacked_texto`, and on pooled L1 of
    `single_texto`. 2 tests.
  - **A2 (the order matters).** K1 − K0 > 0 on `single_texto` (all types) and on `stacked_texto`. 2 tests.
    K0 is the seen arm, and this contrast is blind because K1 is new.
  - **A3 (tolerance matters under stacking).** K2 − K1 > 0 on `stacked_texto`. More edits mean more misread
    axes, which a hard filter turns into a wrong family slice. 1 test.
  - **A4 (the cheap route).** R2 − `bm25_unigram` > 0 and R2 − `rules_valuenorm` > 0 on pooled L1 of
    `single_texto`. 2 tests.
  - **A5 (the constraint alone does little).** F1 − ColBERT on `stacked_texto`: supported if the clustered
    interval lies within ±0.02. ColBERT's errors are already inside the concept (S7). 1 test.
  - **A6 (verbatim cost).** K2 − ColBERT < 0 on `texto_u`. A two-stage arm cannot be better than a ceiling at
    0.9993, and K0 sits at 0.8380 there, so the price of reading values is stated, not hidden. 1 test.
  - **A7 (the ladder, blind).** K2 − ColBERT > 0 on `dose_texto`, pooled over rungs and at rung 5, under D-053.
    2 tests.
  - **A8 (identity of the parent).** Not a test: every arm's parent Acc@1 equals `dense_e5`'s on every base.
    It is asserted in the generator.
- **How S11 resolves.** The method contribution is **established on dev** if A1 holds on both populations and
  A7 holds pooled. It is **partly established** if A1 holds on one population or A7 fails. It is **not
  established** if A1 is not supported on either. A2, A3 and F1 say which part of the second stage carries
  the effect. A4 says whether it needs an LLM. A6 and T6 give its price.
- **D-004.** Every reading is recomputed without flagged queries in T7. A category change reads *not robust*.
- **Dev only.** Test queries are never generated, extracted or read. Generated tables type no number into their
  prose, and the report is guarded by `tests/test_report_traceability.py`.

## Exit criteria

1. The label-stripping test reproduces A7's axis counts exactly. The within-family scorer reproduces ColBERT's
   stored scores on its top-100 for every query of every base it is used on.
2. The E3 generation has run, and the 100-query regeneration result is recorded (identical, or the rate as an
   amendment).
3. 30 runs exist: `code_dirty: false`, split `dev`, resolving under `check_run_inputs.py`, stamped with model
   digest and prompt SHA. K0's reuse diff is recorded.
4. `results/S11/` holds T1–T9 and Fig. 8, generated, byte-identical on regeneration and under the prose guard.
   Every item-level figure carries n scored, n excluded and concepts. Every contrast carries both intervals.
5. The 11 tests are each read supported, not supported, contradicted or not tested, tie-free and as run, with
   the D-004 reading beside and seen/blind marked.
6. The report states the method contribution by the rule above, with cost per query against `bm25_unigram`
   and ColBERT. Its wording is scoped to dev, to in-sample rules, and to the extractor's prompt exposure.
7. Full suite and the OEB fixture pass.

## Out of scope

- **Test split:** S12, which must register before it opens whether K2 and R2 are admitted.
- **Learned second stages** (a fine-tuned within-family scorer): S10 (D-058). The cross-encoder over siblings is
  not run. The `mmarco-mMiniLMv2` blend lowers ColBERT's stacked item accuracy (S7, `ce_bge_m3_colbert`)
  and is not retrained here.
- **Prompt or model changes**, the classification and two-step prompt modes, and any other extractor model:
  one extractor, unchanged from S9, with only the key match registered.
- **A different first stage.** ColBERT and the oracle TF-IDF also keep the concept (S8). Swapping Stage 1 is a
  later question, not this one.
- Synonym lexicons or anything built from the menus.

## Risks

| Risk | Handling |
|---|---|
| ColBERT within-family scoring is slow on large OEB families | Families are scored once per query from stored vectors; T6 reports it; a cap would be an amendment, not silent |
| BGE-M3 server unreachable from `bc3cat-s3` | Checked before the run; S9's A2 hosts mapping recorded as an amendment if used |
| `phi4` non-determinism on the E3 generation | Regeneration check; the cached file is the artefact |
| The ladder's 4 concepts make A7 a narrow claim | D-053's sign rule; wording scoped to those concepts |
| K0 reuse diff not identical after 1a | Re-run K0 on the five bases, recorded as an amendment |
| The method looks strong only because the A7 rule was fitted on dev | Seen/blind marked per test; S12 is the held-out reading |

## Amendments

In [`SPRINT_S11_AMENDMENTS.md`](SPRINT_S11_AMENDMENTS.md), append-only (D-045).
