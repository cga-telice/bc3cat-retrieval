# Sprint S9 — Track C: query-side normalisation and rewriting · design

> **Frozen at:** `<commit SHA>` · `<date>`
> This document is read-only from that commit. Changes go in
> [`SPRINT_S9_AMENDMENTS.md`](SPRINT_S9_AMENDMENTS.md) (D-045), dated and justified — never as
> in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S9` · backbone |
| **Status** | planned → active |
| **Serves** | H6 (crossover); the practical decision rule; D-046's value-reading step; D-041's two redirected questions |
| **Depends on** | S6 (`done`); S91's decoder and renderings (`OE_resumen_decoded.json` `ca7fc230…`, `OE_resumen_decoder.json` `7ee4557f…`); local ollama 0.17.7 with `qwen2.5:14b` `7cdf5a0187d5` and `phi4` `ac896e5b8b34`; extractor at `research/structured-retrieval@85c3359` |
| **Decisions applied** | D-004, D-008, D-010, D-026, D-028, D-030, D-033, D-039 (2nd amendment), D-040, D-041, D-045, D-046, D-047, D-049 |
| **Effort** | 3 weeks (plan: 2; the LLM arms add generation time and their own stamping) |
| **Predecessor / successor** | S8 / S10, S11 (D-046: two-stage builds on S9's value reading), S12 |

## Goal

At the end of S9 we will know whether rewriting a query before matching helps or hurts as a function of how
much of it its target already contains (H6), and where the sign changes, measured on the same leaves across
renderings that span S3's overlap range: identity `texto` (1.00), `single_texto` (0.94), coded `resumen`
(0.79) and `stacked_texto` (0.68). We will also know whether a deterministic, catalogue-only canonicaliser of
numbers and units recovers the L1 damage S4 measured, which is the value-reading step D-046 says any structured
or two-stage route needs. Whether an IDF guard removes S91's rare-code hijacking without cost elsewhere, and
whether an LLM extractor reads values the rules pipeline cannot, are answered beside these.

## Entry state

Checked in the tree on 2026-10-02, not taken from the registry:

- **S6 `done`**: `SPRINT_S6_AUDIT.md` **PASS WITH FINDINGS**, all six resolved; D-048, D-049 accepted. S7, S8,
  S91 also `done`. HEAD `2ab4636`, tree clean, branch `research/synthetic-oe`, main checkout.
- **Query sets re-hashed against `MANIFEST.md`**, all matching: `OE_texto` `02a2c270`, `OE_resumen` `0cd380e9`,
  `OE_resumen_decoded` `ca7fc230`, `OE_resumen_stripped` `4703d33f`, `OE_resumen_decoder` `7ee4557f`,
  `OE_single_texto` `b6a43961`, `OE_single_l2_texto` `fff7dd3b`, `OE_stacked_texto` `c34a222a`.
- **Dev population, counted**: `single_texto` 2,206 queries over 1,460 leaves, 42 concepts; `single_l2_texto` 518
  over 188 leaves, 9 concepts; `stacked_texto` 2,521 over 2,521 leaves, 41 concepts. Their union **U** is **2,691
  dev leaves** (1,458 in both single and stacked). Mean query length 78–81 words.
- **Existing runs to pair against**: every BASE7 arm has dev runs on `texto`, `resumen`, `resumen_decoded`,
  `single_texto`, `single_l2_texto`, `stacked_texto` (S3, S91, S4, S6, S7).
- **LLM service**: container `ollama` (0.17.7, RTX 4090 24 GB), reachable from `bc3cat-s3` at
  `host.docker.internal:11434`; models `qwen2.5:14b`, `phi4`, `llama3.1:8b` present. No generative model has been
  run on this branch, and no LLM client code exists on it.
- **Not present**: no query-transform hook in `retrieve.ipynb` (lexical normalisation is baked into the feature
  tables); no unit, number-word or conversion normaliser anywhere in `src/`; no IDF cap in any builder; D-040's
  exclusion not in the harness (its recorded debt); per-query overlap is not persisted (S6 recomputes it).

## Work

1. **Infrastructure.**
   (a) **Derived query sets.** A query set `{base}__{transform}` resolves in `run_context` from a generated JSON plus
   its `_norm`/`_feats` tables, built by `build_s9_query_tables.py` on the S91 path (re-derive the base first and
   require equality). Bases: `texto_u` and `resumen_u` (identity and coded `resumen` of U, as subsets of the existing
   sets), `single_texto`, `single_l2_texto`, `stacked_texto`. Every derived file goes into `build_manifest.py`.
   (b) **D-040 in the harness**, with its excluded n, regenerating D-040's counts. Transforms never change the
   excluded population: it is fixed on the base set's text.
   (c) **LLM client** `src/query_rewrite/llm.py`: ollama HTTP, model by digest, `temperature 0`, `seed 20260915`,
   `num_predict 256`, `num_ctx 4096`. Every generation is cached; the JSON sidecar records model digest, ollama
   version, prompt SHA-256, options and seconds per query. Runs stamp the generated query file, so the generation is
   inside the provenance chain. A 100-query regeneration must be byte-identical; if not, the rate is recorded as an
   amendment and the cached file is the artefact.
   (d) **Prompts** in `src/query_rewrite/prompts.py`, zero-shot, in Spanish, naming the domain and nothing from any
   leaf. Developed on at most 20 dev queries for format only; no retrieval is run before they are committed. Their
   SHA-256 is recorded before the first scored run.
2. **Transforms**, each producing a derived set for all five bases:
   - **C — canonicalise** (`src/query_rewrite/canon.py`, deterministic): Spanish number words → digits (cardinals,
     decimals "coma", "medio"); unit names → abbreviations; a quantity converted to another unit only when the
     result equals a value surface present in the corpus `texto` inventory for that dimension, else left alone.
     Knowledge: generic Spanish rules and the indexed corpus only (constraints below). Unit tests from hand-written
     cases.
   - **H — HyDE expansion** (`qwen2.5:14b`): the model writes a catalogue-style technical description for the query;
     the query becomes original ⊕ generated, for every arm.
   - **W — LLM rewrite** (`qwen2.5:14b`): the model rewrites the query in canonical catalogue style (digits,
     abbreviated units, catalogue wording); the rewrite replaces the query.
   - **D — the S91 decoder**: `resumen_u` only; reuses S91's decoded runs, no new run.
3. **IDF guard.** First the D-041 diagnostic: why TF-IDF, same tokenizer, barely shows the rare-code pattern —
   decompose rank-1 score shares of rare tokens for `tfidf_phrases_replace` and `bm25_unigram` on coded `resumen`
   misses (descriptive). Then a builder parameter `idf_cap`, set now to the BM25 IDF at df = 1,200 (S91's rare cut,
   itself read on dev `resumen`: in-sample, stated), two new configs `bm25_unigram__…__idfcap__OE`,
   `bm25_unigram_params__…__idfcap__OE`, indexes rebuilt, run on the five untransformed bases.
4. **Slot filling.** Port `param_extractor.py` and `prompts.py` from `research/structured-retrieval@85c3359` by file
   checkout (D-026), `extract` mode, `phi4` as there. New arm `structured_pipeline_llm_valuenorm__OE` = S5's
   `rules_valuenorm` with Stage 2 replaced by the LLM extractor; Stages 1 and 3 untouched. Run on the five
   untransformed bases. The prompts were chosen on OEB `resumen`, whose concepts sit on both sides of OE's split:
   that exposure is stated with every figure.
5. **Run**, split `dev`, clean tree, sprint container: BASE7 × C, H, W × five bases = **105 runs**; IDF guard **10**;
   slot filling **5**. **120 runs.** Untransformed references are the existing runs restricted to the same queries,
   not re-made. Nothing is tuned.
6. **Analyse** with `src/utils/build_results_s9.py` into `results/S9/`, under the prose guard, importing S6's
   tie-free scoring and S2's bootstrap. Per-query overlap is computed with `build_overlap`'s functions on the
   **untransformed** query and persisted as `results/S9/overlap_per_query.parquet` (derived).
   - **T1 — profile.** Per arm × base × transform: item and parent Acc@1 (tie-free, as run), n scored, n excluded,
     δ against untransformed.
   - **T2 — by overlap bin.** Per arm × transform: δ in bins B1 < 0.70, B2 0.70–0.85, B3 0.85–0.95, B4 0.95–1.00
     (non-identity), B5 identity; n, concepts, clustered CI.
   - **T3 — crossover.** Per arm × H/W: linear fit of per-query δ on coverage over non-identity queries; slope, c* =
     coverage where the fit crosses 0, both with clustered intervals; c* outside the observed range reads "no
     crossing in range". Per-base fits beside, descriptive.
   - **T4 — canonicaliser by type.** δ_C per single type and layer, with S4's identity-paired δ beside; what C
     changed (queries touched, tokens rewritten, conversions snapped / declined).
   - **T5 — IDF guard** and the TF-IDF decomposition. **T6 — slot filling** against `rules_valuenorm`, `bm25_unigram`
     and S5's oracle bound. **T7 — cost**: seconds per query, generated tokens, per transform.
   - **T8 — D-004.** **T9 — predictions.** **T10 — provenance**, including model digests and prompt SHAs.
7. **Figure, drafted**: Fig. 7, δ against coverage per arm, H and W, bins with intervals, fitted line and c*.
8. **Report**, then `/audit S9` in a fresh session.

## Design constraints

- **Paired, always.** Every δ is transformed − untransformed on the same query, same arm, same scoring
  population. No transform is compared with another on a different population; between-base comparisons are
  labelled between-population.
- **The overlap axis is the untransformed query's lexical coverage of its gold** (S3's definition, unchanged).
  The bins are fixed above. The crossover is observational: coverage co-varies with base and type, so c* is a
  property of these renderings, not a causal threshold, and per-base fits are printed beside it.
- **No leakage into the canonicaliser.** It never reads upstream's rewrite menus, the modifications sidecars,
  a query's `parameters`, its `modification_types`, its gold, or the concept. Its knowledge is generic Spanish and
  the indexed corpus, which a deployed system has. Rules are developed on dev, so its dev figures are in-sample,
  as the S91 decoder's are; its held-out reading is S12's. `synonym_label` has no generic inverse and is not
  targeted; per S6's inheritance, C is expected to recover what overlap explains and not that token.
- **LLM arms are deployable but not reproducible by construction.** Determinism is asserted (work item 1c), not
  assumed; the cached generation is the artefact and is stamped. No prompt sees a leaf's text or parameters.
- **Oracle arms travel with their twins** (D-010). Transforms rewrite `text` only; `parameters` stays as delivered,
  so `bm25_unigram_params`† and `tfidf_phrases_replace`† are run and profiled and **never tested**.
- **Scoring.** D-033 everywhere; D-040 on `resumen_u` (and on any base found with text-identical golds); P7/P8 as in
  S4. A transform that makes two golds' queries identical is **not** excluded — it is the method's error — and the
  count is printed.
- **Tie-free Acc@1 is primary** (D-028 note), as run beside; a reading that differs is flagged.
- **Inference.** Concept-clustered percentile interval, B = 10,000, seed 20260917 (D-030); bins below 10 concepts
  carry ‡ and are not read; query-level CI printed beside. The same leaf appears under several bases, which the
  concept clusters absorb.
- **Floor arms** excluded as in S6 (identity item Acc@1 < 0.20 on the base population, recomputed).
- **Registered predictions**, Holm across all, BH beside, all **blind** (no transform has been run). Tested arms:
  the five deployable BASE7 arms — `bm25_unigram`, `bge_m3_colbert`, `bge_m3_dense`, `dense_e5`,
  `dense_es_hiiamsid` — minus floor arms. Item level.
  - **Y1 (H6, harm near-verbatim).** δ < 0 in B4 for H and for W. 10 tests.
  - **Y2 (H6, gain at low overlap).** δ > 0 in B1 for H and for W. 10 tests.
  - **Y3 (H6, crossover).** Slope of δ on coverage < 0 for H and for W. 10 tests.
  - **Z1 (C recovers L1).** δ_C > 0 on pooled L1 of `single_texto`. 5 tests.
  - **Z2 (C is harmless verbatim).** δ_C on `texto_u`: supported if the clustered interval's lower bound
    is > −0.01. 5 tests.
  - **G1 (guard).** `bm25_unigram` + `idf_cap` − `bm25_unigram` on coded `resumen_u`, parent level, > 0. 1 test.
  - **G2 (guard costs nothing).** Same contrast on `single_texto`, item level, lower bound > −0.01. 1 test.
  - **E1 (value reading).** LLM extractor − `rules_valuenorm` on pooled L1 `single_texto` > 0. 1 test.
  - **E2 (G2 revisited).** LLM extractor − `bm25_unigram`, same population, > 0. 1 test.
  **44 tests.**
- **How H6 resolves.** *Supported* for a transform if Y1, Y2 and Y3 hold for a majority of tested arms;
  *contradicted* if Y1 reads contradicted (expansion helps near-verbatim) for a majority; *partly supported*
  otherwise, naming arms and transforms. The decision rule is stated as c* per arm and transform, with its
  interval, or as "no crossing in range".
- **D-004.** Every reading recomputed without flagged queries in T8; a category change is *not robust*.
- **Dev only.** Test queries are never generated, transformed or read. Generated tables type no number into
  their prose; the report is guarded by `tests/test_report_traceability.py`.

## Exit criteria

1. Every derived set resolves through `run_context`, each base re-derives exactly, every derived file is in
   the manifest; D-040's exclusion is in the harness with tests, and its counts are regenerated.
2. The 100-query regeneration test has run for H, W and the extractor; result recorded (identical, or the
   rate as an amendment).
3. 120 runs exist: `code_dirty: false`, split `dev`, resolving under `check_run_inputs.py`, stamped against their
   derived set's digest; T10 carries model digest and prompt SHA per LLM run.
4. `results/S9/` holds T1–T10 and Fig. 7, generated, byte-identical on regeneration and under the prose
   guard. Every item-level figure carries n scored and n excluded; every contrast its clustered and query-level
   intervals and concept count.
5. The 44 tests are each read supported, not supported, contradicted or not tested, tie-free and as run, with
   the D-004 reading beside.
6. The report resolves H6 by the rule above, states c* per arm and transform, and answers D-041's two
   questions and D-046's value-reading question in words scoped to dev and in-sample where that applies.
7. Full suite and the OEB fixture pass.

## Out of scope

- **Test split**, and the canonicaliser's and decoder's held-out coverage: S12.
- **Learned representations** and any training: S10. **Two-stage designs**: S11, on top of what E1 shows.
- **Synonym lexicons** or any resource built from the menus; **few-shot prompts**; prompt or model selection by
  accuracy (one model per role, fixed here).
- **`dose_texto` / `isolated_texto`** (S8's population), the cross-encoder and RRF arms, `resumen_stripped`.
- **Whether real queries carry codes**: S90, if the anchor arrives.

## Risks

| Risk | Handling |
|---|---|
| Generation time: ≈ 10,600 queries × 2 transforms + extraction | Cached, resumable; estimated ≈ 16–20 h on the 4090; T7 reports it |
| ollama non-determinism (batching, GPU kernels) | Work item 1c test; cached file is the artefact; rate recorded |
| B1 or B4 thin or concentrated in few concepts | n and concepts printed; ‡ below 10 concepts, not read |
| Canonicaliser rules fitted to dev by inspection | In-sample stated; leakage rule above; S12 reads it held out |
| Extractor exposure to OEB `resumen` | Stated with every E-figure |
| BGE-M3 server unreachable from `bc3cat-s3` | Checked before the run; S7's mapping recorded as an amendment if used |
| H on lexical arms is dominated by generated length | Generated length printed in T7; not corrected, stated |

## Amendments

In [`SPRINT_S9_AMENDMENTS.md`](SPRINT_S9_AMENDMENTS.md), append-only (D-045).
