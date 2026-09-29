# Sprint S4 — E1 ablation, Track A · design

> **Frozen at:** `dd407c6` · `2026-09-29`
> This section is read-only from that commit. Changes go in **Amendments** below, dated and
> justified — never as in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S4` · backbone |
| **Status** | planned → active |
| **Serves** | H1 (widening collapse), H2 (layer specificity); the x-axis inputs of H5 |
| **Depends on** | S3 (`done`); S91 (`done`, not a dependency: `texto` renderings carry no codes) |
| **Decisions applied** | D-004, D-007, D-010, D-012, D-018, D-023, D-028, D-030, D-032, D-033, D-036, D-038 |
| **Effort** | 2 weeks |
| **Predecessor / successor** | S3 / S5, S6 |

## Goal

At the end of S4 we will know, for each Track A arm and each of the nine modification types, how
much item-level and parent-level accuracy a single referent-preserving modification costs
**on the leaves that received it**, measured against the same arm's identity rendering of those
leaves. We will know whether the cost concentrates in L1 for the lexical arms, whether `reorder`
is free for bag-of-words and costly for order-sensitive encoders, and whether the item/parent
gap widens under modification: the first reading of H1 and H2 on OE. Today S2 has four cells for
five arms, and S3 has identity ceilings but no profile.

## Entry state

Checked in the tree on 2026-09-29, not taken from the registry:

- **S3 `done`**: registry row and log; third audit PASS WITH FINDINGS, all resolved. **S91 `done`**
  likewise; nothing in S4 reads its outputs.
- **Ten indexes** under `index/OE/` at the stamps S3 lists: the two BM25 arms at `k1`=0.60/`b`=0.35
  (D-036), `tfidf_unigram_phrases_replace`, `dense_e5`, `dense_gte`, `dense_gte_instrQ`,
  `dense_es_hiiamsid`, `bge_m3_dense`, `bge_m3_sparse`, `bge_m3_colbert`.
- **Identity runs, ten of ten**, `runs/OE/texto/<arm>`: split `dev`, 35,422 queries, all
  `code_dirty: false`, at `31bf1a1` / `2e49566` / `922ae53` / `a5700a6`. Query-set digests
  `643f1a72` (`OE_long_feats`) or `75477221` (`OE_long_norm`, ColBERT and `bge_m3_dense`); both
  re-hashed and match `MANIFEST.md`.
- **`single_texto` runs, three of ten**: `bm25_unigram`, `bm25_unigram_params`, `bge_m3_colbert` at
  `31bf1a1`, `code_dirty: false`, 2,206 dev queries, digest `e5b79ae4` — re-hashed, matches.
- **Sidecar** `OE_duplicate_texto_groups.json` `b3cfcad4`, matches (D-033).
- **Not ready**, and therefore work: `hybrid.ipynb` and `cross_encoder.ipynb` do not use
  `run_context` and read flat OEB paths; the only fusion config (`rrf__bm25_char_e5.yaml`) is
  `collection: OEB` with flat index paths. `cross_encoder.ipynb`'s blend mixes raw score scales
  (`λ·ce + (1−λ)·fused`, no normalisation) and defaults to depth 50.

## Work

1. **Arm set, fixed here** (César, 2026-09-29, under D-012). Fifteen arms:
   - the **ten indexed arms**, as in S3;
   - **`rrf__bm25_unigram+bge_m3_colbert`** (deployable) and **`rrf__bm25_unigram_params+bge_m3_colbert`**
     (its oracle twin, D-010): reciprocal-rank fusion of the two components' top-100,
     `score = Σ 1/(60 + rank)`, equal weights, a document absent from a list contributes 0;
   - **`ce_blend__<base>`** for base ∈ {`bm25_unigram`, `bge_m3_colbert`,
     `rrf__bm25_unigram+bge_m3_colbert`}: cross-encoder
     `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (the model the code names; D-035's precedent),
     pinned by Hub revision, `max_length` 320, over the base's **top-100**. Blend
     `λ·ĉ + (1−λ)·ŝ`, λ = 0.6, where ĉ and ŝ are the CE and base scores **min–max normalised per
     query** over the 100 candidates. Ties broken by base rank.
   - **PRF is excluded** (RM3 +0.001 n.s., Rocchio −0.012 on OEB; D-012). No fusion or rerank
     parameter is tuned on OE; every value above is fixed now.
2. **Port the two derived families** into committed modules driven by `run_context`
   (`src/utils/fuse_rrf.py`, `src/utils/rerank_ce.py` or equivalent), with one config per derived
   arm declaring `collection`, an explicit `retriever` block, and its component **run IDs**. A
   derived run reads its components' `results_top100.jsonl.gz` and **fails loud** if they differ
   in split, query-set digest, or query order. Its `run_meta.json` carries the components' stamps;
   a CE run also records its ML stack (`torch`, `transformers`, `sentence-transformers`, model
   revision), since `index/*/meta.json` does not (H4). The dirty-tree refusal moves into
   `src/utils/provenance.py` (S3 debt, audit F11), since these are new runners.
3. **Test before any run**: RRF on a hand-computed fixture; the blend on a fixture including a
   constant-score query (min–max on zero range → 0); fail-loud on mismatched components;
   `check_run_inputs.py` resolves a derived run through its components. Full suite and the OEB
   fixture pass.
4. **Undecidable-query check on `single_texto`** (D-040's scope clause). Count dev queries whose
   text equals another dev leaf's `texto` or another dev query's text. If any, stop and raise an
   amendment naming the set before any figure is read; if none, record the zero.
5. **Run**, all split `dev`, clean tree, in the sprint container:
   - 7 base arms × `single_texto` (the three S2 runs are reused);
   - 5 derived arms × {`texto`, `single_texto`} = 10.
   **17 new runs.** Reuse of the 13 existing runs is justified by a recorded `git diff` of each
   arm's retriever and builder between its commit and S4's, as S3 did; a changed path means
   re-running that arm, recorded.
6. **Analyse** with `src/utils/build_results_s4.py`, added to `tests/test_generated_prose.py`,
   into `docs/synthetic-oe/results/S4/`:
   - **T1 — ceilings.** The five derived arms' identity ceilings, item and parent, with the ten from
     S3 cited by path, field ceiling and headroom (D-032).
   - **T2 — the profile, item level.** Arm × type, plus layer pools and all-single: n, n scored,
     n excluded, concepts; identity Acc@1 **on the treated leaves**; modified Acc@1; δ with
     query-level and concept-clustered CI; retention; flips both ways.
   - **T3 — the profile, parent level**, the same columns, plus the collapse quantities of H1:
     right-parent/wrong-item rate, D = P(item | parent), and gap Δ = parent − item, each at
     identity and under modification, with the paired change.
   - **T4 — token distance.** Per cell, mean d_tok and δ / mean d_tok; the D-038 query-vs-gold
     number count beside it. Descriptive.
   - **T5 — ties** (D-028): share of queries whose rank-1 score is tied, per cell, for every arm.
   - **T6 — predictions**: each of P1–P5 with its estimate, clustered CI, raw and Holm p, reading.
   - **T7 — run provenance**, all 30 runs, stamps and reuse diffs.
7. **Issue the thin-slice request** upstream: `requests/WIDER_THIN_SLICES.md` asking for wider
   `paraphrase` and `expansion` slices (dev n = 108 / 130), for S6. Update `RESEARCH_PLAN.md` §5
   with the issue date. S4 does not wait for it.
8. **Report** `SPRINT_S4_REPORT.md`, then `/audit S4` in a fresh session.

## Design constraints

- **Treatment effect on the treated, paired by leaf.** For query *q* with gold leaf *g*,
  δ_q = hit(*q*) − hit(identity query of *g*), same arm, same index. A cell's δ is the mean over its
  queries. A leaf in several types pairs with the same identity result in each. Raw Acc@1 across
  types is **not reported as a comparison**: T2 prints it only beside its own identity baseline.
- **Population.** Item level: dev `single_texto` queries whose gold is not in a
  `duplicate_texto_group` (D-033): 2,177 of 2,206, the 29 excluded printed per cell. Parent
  level: all 2,206. The identity side of every pair is read from the S3 run restricted to the
  same golds, never from its whole-population figure.
- **Retention before δ when reading across arms.** δ is bounded below by the arm's identity
  accuracy on the treated leaves, so δ is not comparable between arms with different ceilings.
  Retention, P(hit under modification | hit at identity), is the headroom-normalised quantity
  (D-032) and is what any sentence setting two arms side by side quotes.
- **Floor arms.** An arm whose identity item Acc@1 on the treated leaves is below 0.20 has no
  item-level headroom to lose. On S3's figures that is `bge_m3_sparse` (0.0501), `dense_gte`
  (0.0967) and `dense_gte_instrQ` (0.1077), subject to the treated-leaf figure. They are
  reported in every table and **excluded from every prediction reading**. Their parent level is
  reported without exception, and GTE's is the arm H1 names as a counterexample (D-012).
- **Oracle arms travel with their twins** (D-010): `bm25_unigram_params` with `bm25_unigram`,
  `tfidf_phrases_replace` marked oracle, the oracle RRF with the deployable RRF. On L2/L3 the
  oracle query carries the gold's full parameter fingerprint; on L1 exactly one token is out of
  vocabulary (D-010, second note). No sentence quotes an oracle figure alone.
- **No arm-vs-arm contrast is claimed.** Arms are printed side by side as reference. Whether
  fusion or reranking beats a base arm is not an S4 claim; rank inversion is S5's, inference S6's.
- **Layers are compared across different leaves.** L1, L2, L3 pools cover different populations
  (applicability is item-dependent), so a layer contrast is a difference of two treated-effects,
  bootstrapped by resampling concepts **independently within each pool**. It is labelled
  between-population wherever it appears. S6's mixed model is where concept difficulty is
  separated from layer.
- **Token distance** d_tok = 1 − Jaccard of the distinct tokens of query and gold `texto`, using
  the S3 overlap's own `normalize_text` / `tokenize_words`. Fixed now; S6 inherits it. It is
  descriptive in S4: no mediation claim (H5 is S6's, over two covariates, D-038).
- **Statistics.** Paired bootstrap, B = 10,000, seeded, percentile 95 %; query-level and
  concept-clustered intervals throughout. A reading uses the **clustered** interval (D-030). Dev
  is 71 % OEB by leaf; per-type concept counts (5 to 42) are printed with every interval.
- **Registered predictions**, read on the clustered interval; Holm–Bonferroni across the 15
  tests below, Benjamini–Hochberg printed beside. **Supported** when the interval lies on the
  predicted side of 0 (or inside the margin, for P3) **and** Holm p < 0.05; **contradicted** in the
  mirror case; **not supported** otherwise (S91 A2's rule).
  - **P1 (H1).** Under modification the gap widens: pooled over all nine types, Δ_mod − Δ_id > 0,
    for `bm25_unigram`, `bm25_unigram_params`, `bge_m3_colbert` (3 tests).
  - **P2 (H2, L1).** For both BM25 arms, pooled L1 item δ is below pooled L2 **and** below pooled
    L3 (4 tests, between-population).
  - **P3 (H2, L3 bag-of-words).** `reorder` item δ lies within ±0.02 for `bm25_unigram`,
    `bm25_unigram_params`, `tfidf_phrases_replace` (3 tests, two one-sided).
  - **P4 (H2, L3 order-sensitive).** `reorder` item δ < 0 for `bge_m3_colbert`, `bge_m3_dense`,
    `dense_es_hiiamsid` (3 tests).
  - **P5 (H2, L2).** Among item-level losses (identity hit → modified miss), the share whose rank-1
    lies in the wrong concept is larger under pooled L2 than pooled L1, for `bm25_unigram` and
    `bge_m3_colbert` (2 tests, between-population).
  - Derived arms and floor arms: no prediction. Reported, not claimed.
- **Thin types.** `paraphrase` (108 dev) and `expansion` (130) are printed with their intervals
  and pooled into L2; no per-type claim rests on them.
- **Carried caveats, printed where they bite.** The decimal-mangling artefact (D-010 adjacent: 9
  `unit_conversion`, 4 `unit_expansion` dev queries) is counted per cell; a miss there is a feature
  artefact. Pantry artefacts (D-004) stay in; their sensitivity analysis is S6's. Exact-score
  ties are broken by FAISS or `np.argpartition`, not stably (S3 debt), which T5 quantifies.
- **Dev only.** No test query is read, no S12 artefact touched. **No typed numbers** in the
  generated tables' prose (S91 A4 applies: the report is typed and guarded by
  `tests/test_report_traceability.py`).

## Exit criteria

1. The two derived modules, five configs and their tests are committed; the full suite and the OEB
   fixture pass. Every derived config names its components by run ID.
2. Work item 4's count is recorded in the report; if non-zero, an amendment precedes any reading.
3. 17 new runs exist, all `code_dirty: false`, split `dev`, resolving under `check_run_inputs.py`;
   CE runs stamp their ML stack. The reuse of 13 runs is justified by a recorded retrieval-path diff.
4. `results/S4/` holds T1–T7, generated by `build_results_s4.py`, regenerating byte-identically,
   under the prose guard. Every item-level figure carries n scored and n excluded; every δ its
   query-level and clustered CI and its concept count; every accuracy its identity baseline on the
   same leaves.
5. The profile covers 15 arms × 9 types at both levels, plus the three layer pools, with no empty
   cell unexplained.
6. P1–P5 are each read supported, not supported or contradicted under the rule above.
7. `requests/WIDER_THIN_SLICES.md` is committed and `RESEARCH_PLAN.md` §5 records its issue.
8. H1 and H2 each have a movement line in the report, stating that S6 resolves them.

## Out of scope

- **Structured pipelines and H3**: S5. **Mixed-effects model, mediation, power notes, D-004
  sensitivity**: S6. **Stacked set**: S7. **Dose and isolated sets**: S8 (D-009).
- **PRF** (César, 2026-09-29). **Tuning** RRF's constant, weights, CE depth or λ: any change is an
  amendment and invalidates the affected cells.
- **Replace-mode CE reranking**: the previous study found it worse than blend on every base; not
  run. **`resumen`** in any rendering: nothing here reports it, so D-039/D-040 do not bind.
- **Fixing H4 in `index/*/meta.json`** (before S12) and a **stable tie-break** (S3 debt): measured
  in T5, not fixed.
- **Test split, S12.**

## Risks

| Risk | Handling |
|---|---|
| Blend departs from the previous study's (raw scales, depth 50 by default) | Normalised blend fixed here; the previous study's CE rows are not a reference for these, stated in T1 |
| The manuscript names `ms-marco-MiniLM-L-6-v2` (English), the code `mmarco-mMiniLMv2-L12` | Follow the code, as D-035 did for GTE; raise a decision at the port recording the manuscript defect |
| CE cost: ~3.5 M (query, doc) pairs per base on `texto` | Cache scores by (query key, doc key, model revision, `max_length`); shared across the three bases |
| Derived runs stamp components from different commits | Components named by run ID; their stamps copied into the derived run; fail-loud on mismatch |
| Floor arms make δ look like robustness | Retention, the 0.20 floor rule, excluded from predictions |
| One chapter drives pooled figures (OEB 71 % of dev) | Clustered intervals; concept counts in every cell |
| Layer contrasts confound layer with the leaves that admit it | Labelled between-population; S6 separates them |
| Identity ties resolve differently across runs for dense arms | T5 per cell; D-033 already removes the undecidable ones |

## Amendments

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
| 2026-09-29 | **A1. How work item 2's pairing check and configs were implemented, and four choices the design left open.** (a) Components are checked for the same split, the same query set and the same ordered `(query key, gold key)` sequence as the derived run's own query table, **not** for an equal query-set digest; every component's digest is copied into the derived run instead. (b) A derived config names its components by **method**; the run ID follows as `OE/{queryset}/{method}`, since each derived arm runs on two query sets. (c) RRF ties are broken by the better rank in the first component, then the second, then item key. (d) The cross-encoder runs in fp32, batch 128. It reads the raw `text` column of the query and corpus feature tables. Its scores are cached under `index/OE/_ce_cache/`, keyed by (sha1 of the query text, document key) for one (model, revision, `max_length`). A derived run's `doc_id` is the corpus row. | (a) Work item 2 as written would refuse every `texto` fusion: ColBERT reads `OE_long_norm` (`75477221`) and BM25 `OE_long_feats` (`643f1a72`), different files holding the same queries in the same order. What pairing needs is row identity, which the key check tests directly. (b) A run ID names one query set, and a config serves two. (c) RRF produces exact ties by construction, for example rank 1 in one list against rank 1 in the other, and the design fixed no order. (d) fp32 avoids half-precision variation across batch compositions. The cache is sound because a score depends only on its key. | None on any figure: made before any S4 run, in `src/utils/derived_runs.py`, `fuse_rrf.py`, `rerank_ce.py` and `tests/test_derived_runs.py`. (a) is stricter than a digest check for what it tests. `check_run_inputs.py` now also fails a derived run whose component has been re-run since. |
| 2026-09-29 | **A2. Work item 4 found one query; it is excluded at item level. Two run-bookkeeping events.** (a) One dev `single_texto` query's text equals another dev leaf's `texto`: `OEC140baa_syn_74d5dd2c9da3`, labelled `reorder`, carries `OEC140aba`'s TEXTO verbatim. It is excluded from item-level scoring and kept at parent level. Its n excluded is printed beside every figure. No query equals another query's text. (b) `dense_gte_instrQ` × `single_texto` was stamped `code_dirty: true`, because an uncommitted generator sat in `src/` when it started. It is archived to `runs/_archive/S4/`, not deleted (D-019, S3 A2's precedent), and re-run. The derived runners' new refusal stopped the two RRF runs that would have been dirty too. (c) The resume script re-ran all seven base arms, not only the archived one, so the six clean base runs were overwritten by runs of the same configs at the same clean commit `36bed7a`. | (a) The design's own rule (work item 4): stop and amend before any figure is read. An upstream investigation found a generation error, not an undecidable query (`DATASET_DEFECTS.md` P7). The rewrite permuted the arguments of a table lookup, so the query describes a sibling while claiming the gold. It is not referent-preserving, and its only valid item answer is not its gold. Its concept is right. Ruled by César, 2026-09-29. (b) Operating rule 1. (c) A script error, found in the runner's log. | (a) Item-level n drops by one (2,177 → 2,176), all in `reorder`; parent level is unchanged. The file is not re-taken, so no run is invalidated. Upstream is told in `requests/REORDER_LOOKUP_ARGUMENTS.md`. (b), (c) None. No S4 figure had been read, and every reported run is clean at one commit per family. |
