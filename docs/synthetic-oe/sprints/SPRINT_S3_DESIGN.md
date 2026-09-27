# Sprint S3 — E0 controls, replication and overlap characterisation · design

> **Frozen at:** `8353cf7` · `2026-09-27`
> This section is read-only from that commit. Changes go in **Amendments** below, dated and
> justified — never as in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S3` · backbone |
| **Status** | planned → active |
| **Serves** | H1 (widening collapse), H5 (overlap mediation); closes D-012 |
| **Depends on** | S2 (`done`, audited); upstream delivery 2026-09-27 (`synthetic` @ `f2457fa`); upstream E3 delivery 2026-09-17 (`4d10af2`) |
| **Decisions applied** | D-008 (amended), D-009, D-010, D-012 (**closed here**), D-016, D-023, D-025, D-030, D-031, D-032, D-033 |
| **Effort** | 2 weeks |
| **Predecessor / successor** | S2 → S4 |

## Goal

At the end of S3, four things are known that are not known now.

**Each method's own ceiling** — an identity `texto→texto` figure for ten methods, read
against the corpus ceiling of the field each indexes (D-032). From S4 on, every degradation
is quoted as headroom against that ceiling instead of as distance from 1.0, which is only
meaningful once the ceiling exists and was measured under one code commit.

**What the previous protocol yields here** — `resumen→texto` on OE for the same ten: the
0.974 headline re-measured on a corpus 1.5× the size across seven subchapters instead of one,
including the `hiiamsid` row the previous submission never printed.

**Whether the operating point transfers** — `k1`=0.60 / `b`=0.35 was fitted to OEB `resumen`
queries of ~14 tokens; OE `texto` queries run ~74–78. A full grid on dev says whether one
point serves both lengths, or whether the headline is partly an artefact of the fit.

**The x-axis of everything downstream** — per-query lexical and numeric overlap against the
target, per query set and condition, computed as the review analysis computed OEB's 94.09 % /
99.93 %. That table is on its own the quantitative answer to the reviewers' central
objection, and it is the covariate H5 and H6 are stated in terms of.

S3 also repairs the population S2 scored on, so that every item-level figure this branch
carries rests on queries with exactly one valid answer (D-033).

## Entry state

Verified in the tree on the day of writing, not taken from the registry.

| Requirement | How checked | Result |
|---|---|---|
| Main checkout, correct branch | `git rev-parse --show-toplevel`, `git branch --show-current` | ✓ no worktree in the path |
| S2 `done`, audited in a fresh session | registry log + `SPRINT_S2_AUDIT.md` present | ✓ PASS WITH FINDINGS, all nine resolved |
| Five `OE_*.json` present, digests on record | `ls`, `MANIFEST.md` | ✓ all match `INTAKE.md §2` |
| OE feature tables present | `ls data/processed` | ✓ `OE_{long,short}_{norm,feats}`, `OE_features_meta`, per-query-set feats/norm |
| S2's 15 runs retain their top-100 lists | `ls runs/OE/*/*/` | ✓ `results_top100.jsonl.gz` in all 15 — the re-score needs no retrieval |
| Sidecar `OE_duplicate_texto_groups.json` | `sha256sum` upstream | ✓ `b3cfcad4…`, matches the upstream manifest |
| Corrected stacked file | `sha256sum` upstream; in-tree file re-hashed | ✓ `c34a222a…` upstream, `1bde2115…` in tree |
| Corrected stacked leaves the texts alone | 4,998 records compared field by field | ✓ `text`, `id`, `item_key`, `gold_item_key` identical **row for row**; only `texto_modification_count` / `texto_modification_types` added |
| Disk for six new indexes | `df -h` | ✓ 1.4 TB free (ColBERT's existing index is 16 GB) |
| Model cache | `ls hf-cache/hub` | ⚠ only `BAAI/bge-m3`; E5, GTE and hiiamsid need downloading |

**One finding, recorded rather than rediscovered.** The same upstream handoff carries the
**E3 balanced dose set** — delivered 2026-09-17 at `4d10af2`, with a point-by-point
`E3_DELIVERY_RESPONSE.md` answering `requests/E3_BALANCED_DOSE.md`. Nothing on this branch
recorded it: `STATE.md` still listed it under *Blocked / waiting*, D-009 was still `Proposed`,
no digest was on file. It does not block S3; it blocks S8, which has been waiting ten days
for a file already on disk. S3 takes it in (work item 2). Two caveats, measured, carried
forward to S8: the set covers **7 OEB concepts only**, and those straddle the split —
`OEB020$ 030$ 230$ 290$` dev, `OEB040$ 280$ 300$` test, so 1,640 of its 3,000 queries are
dev-side and the dev dose slope would rest on 4 concepts.

## Work

### Intake

1. **Take the 2026-09-27 delivery, under D-033's rules.** Copy the sidecar
   `OE_duplicate_texto_groups.json`. **Version the current stacked query set before
   replacing it** — `OE_stacked_texto.json` *and its derived* `_feats` / `_norm` parquets —
   because S2's stacked runs are stamped with the feature-table digest `7b0894e6…`, not the
   JSON's; versioning the JSON alone would leave those three runs unresolvable. Then copy the
   corrected `OE_stacked_texto.json` (`c34a222a…`) and re-derive its feature tables at the
   canonical names. Do **not** re-take `OE_texto.json` / `OE_resumen.json` with the flag
   inside: their digests would change although their texts do not, and all 15 S2 runs would
   stop resolving. Regenerate `MANIFEST.md`; record the delivery in `INTAKE.md`.
2. **Take the E3 delivery (D-009).** Copy `OE_dose_texto.json` (`555fab84…`),
   `OE_isolated_texto.json` (`054041ff…`), `OE_leaf_applicability.jsonl` (`eda12d17…`);
   record digests and upstream provenance (`run_id` `e3-20260917T093057Z`, seed 42, generated
   at `e057907`, repackaged at `903d07b8`). Validate that every `gold_item_key` resolves
   against the corpus, that parents agree, that the ladder is nested (600 leaves × 5 rungs,
   600 per count), and that `applicable_types` is present on every record. Record the
   7-concept and split-straddling caveats. Move D-009 to *Delivered* and S8 from `blocked` to
   `planned`. **No dose run happens in S3.**

### Repairing what S2 reported

3. **Duplicate-aware re-score of all 15 S2 runs (D-033).** From the stored top-100 lists; no
   retrieval, and nothing under `runs/` is overwritten. Item-level excludes queries whose
   gold leaf belongs to a `duplicate_texto_group`; parent-level excludes nothing, since no
   group crosses a concept. Every figure states corpus size, scored n and excluded n
   separately. Output to `results/S3/`; `results/S2/` stays as the record of what S2 reported.
4. **Re-stratify the stacked by-dose table on `texto_modification_count`.** S2's table used
   `distinct_modification_count` (D-025); the authoritative field is now the delivered one,
   and the two distributions differ materially — mode 4 vs 5, range 1–6 vs 2–7. Five stacked
   queries carry `texto_modification_count == 1` and are flagged as such.

### E0 — the controls

5. **Mint the six missing OE configs and build their indexes.**
   `tfidf_unigram_phrases_replace__OE`, `dense_gte__OE`, `dense_gte_instrQ__OE`,
   `dense_es_hiiamsid__OE`, `bge_m3_dense__OE`, `bge_m3_sparse__OE`. Each declares
   `collection` **and an explicit `retriever` block**, even where it only restates the
   default (D-016, and the root defect list). Indexes are built over the full 70,242-leaf
   corpus (D-023).
6. **E0(a) identity ceilings.** Ten methods × `texto`, dev split. Four runs already exist
   from S2 and are reused by digest, not re-run: `bm25_unigram_params`, `bm25_unigram`,
   `bge_m3_colbert`, plus the two structured arms, which are reported beside the ten as
   context but are not part of the set S4 inherits.
7. **E0(b) replication.** The same ten methods × `resumen`, dev split. One exists
   (`bm25_unigram_params`).

The ten, closing **D-012**: `bm25_unigram_params`, `bm25_unigram`,
`tfidf_unigram_phrases_replace`, `dense_e5`, `dense_gte`, `dense_gte_instrQ`,
`dense_es_hiiamsid`, `bge_m3_dense`, `bge_m3_sparse`, `bge_m3_colbert`. RRF, PRF and
cross-encoder reranking are **compositions of these runs' top-100 lists** and get their
ceilings in S4, where they are assembled; PRF is additionally already refuted for this domain
by the previous study (RM3 +0.001 n.s., Rocchio −0.012 significant).

8. **The `k1`/`b` re-sweep.** `bm25_unigram` and `bm25_unigram_params`, over
   `k1` ∈ {0.60, 0.80, 1.00, 1.20, 1.40} × `b` ∈ {0.20, 0.35, 0.50, 0.65, 0.80}, on dev
   `texto`, `single_texto` and `stacked_texto`. 150 runs; BM25 costs 92 s at 35,422 queries,
   so the grid is under two hours and ~2 GB.

### Overlap

9. **Overlap characterisation (H5's x-axis).** Per query, against its gold target: mean and
   median lexical coverage (query tokens present literally in the target), full-containment
   rate, mean numeric coverage, all-numbers-present rate, ≥1-number rate, numbers per query
   — the review analysis's definitions exactly. Reported for `resumen`, `texto`,
   `single_texto` per modification type, and `stacked_texto` per `texto_modification_count`.
   **The implementation is validated before use** by reproducing the OEB reference figures
   (94.09 % lexical / 99.93 % numeric) on `OEB_{resumen,texto}.json`.

### Close-out

10. **Generate the results.** `src/utils/build_results_s3.py`, tables under `results/S3/`,
    with `run_provenance.md` carrying `{run_id, config SHA, code commit, query-set SHA-256}`
    for every number.
11. **Tests.** Regression tests for duplicate-exclusion scoring, the overlap metric against
    the OEB reference figures, and resolution of a versioned query set.

## Design constraints

Written now, before any result.

- **Dev only, everywhere.** Every run, every sweep point, every overlap table. This resolves
  an ambiguity in `RESEARCH_PLAN.md §S3`, which says `resumen→texto` runs "over all 70,242
  leaves": the **corpus** is all 70,242 leaves (D-023), the **queries** are dev's 35,422. The
  literal reading would put test queries in a pre-S12 sprint and break operating rule 3
  (one-shot test). The "1.5× scale" claim refers to corpus size — 70,242 against OEB's
  47,514 — and holds under the dev reading.
- **Identity is a ceiling, not a gate (D-032).** Every table carries a `ceiling` column and
  quotes headroom (observed ÷ ceiling). No method is disqualified for missing 1.0; a claim
  that ignores its method's ceiling is. S3 states **no gate**, so no threshold is read — but
  any threshold language that survives review obeys D-030 and is read on the
  concept-clustered interval.
- **Item-level scoring excludes duplicate-gold queries (D-033).** For the scored population
  the `texto`-only corpus ceiling is 1.0, which is the point of the exclusion. Dev item-level
  then rests on 40 of 42 concepts, `OEA050$` and `OEG050$` contributing parent-level figures
  only. Every table prints corpus size, scored n and excluded n.
- **Oracle arms are never quoted alone (D-010).** `bm25_unigram_params` and
  `tfidf_unigram_phrases_replace` consume the parsed `parameters` field, which a real query
  does not carry; the S2 note measured where that signal comes from. They are reported as
  oracle upper bounds, always beside their text-only counterparts.
- **The sweep is tuning, so the selection rule is declared before the grid runs.** The point
  carried into S4, per field variant, is the argmax of **item-level Acc@1 on dev
  `single_texto` pooled over the nine types** — S4's population of interest. The OEB point
  0.60 / 0.35 is always reported beside it, so transferability is a paired contrast with an
  interval rather than a narrative.
- **The replication is a reference, not a paired comparison.** OEB test → OE dev changes the
  chapter, the corpus size, the query set and the split. OE figures are printed beside the
  previous study's with that stated; no delta and no interval is computed between them. What
  may be compared is method against method **within** OE, paired by query.
- **Overlap is descriptive in S3.** The tables are covariates for S6's mediation model, not
  effects. No causal or mediation claim is made here.
- **No cross-type Acc@1 comparison.** Applicability is item-dependent, so a raw comparison
  across modification types confounds the modification with the population admitting it. S3
  reports overlap per type — the population description that makes S4's paired deltas
  readable — and leaves the deltas to S4.
- **Thin slices carry their intervals.** Dev `paraphrase` n=108, `expansion` n=130. Reported
  with intervals or pooled at layer level, never as a bare point estimate.
- **Pantry artefacts get a sensitivity column.** Token doubling and the documented
  "con topo" → "con topografía" drift are traceable per item; the overlap tables report with
  and without them (D-004).
- **Stacked dose means `texto_modification_count`.** The original `modification_count`
  overstates the visible dose and is not used for any stratification.
- **S2's artefacts are immutable.** The re-score writes new generated files; nothing under
  `runs/` is edited, and `results/S2/` is preserved as the record of what S2 reported.

## Exit criteria

1. `MANIFEST.md` regenerated, carrying digests for the sidecar, the corrected stacked file,
   the versioned previous stacked file **and its feature tables**, and the three E3 files —
   each matching the upstream manifest.
2. A test asserts the corrected stacked file's `text`, record order and `gold_item_key` are
   identical row for row to the versioned copy, establishing that S2's stacked Acc@1 stands
   under the new digest rather than assuming it.
3. All 15 S2 runs still resolve against the tree after the intake: config SHA, code commit
   and query-set SHA-256 each found, verified by a script and not by inspection.
4. Ten methods have an identity run and a `resumen` run on dev, every one `code_dirty:
   false` and stamped, all listed in `results/S3/run_provenance.md`.
5. The ceiling table gives, per method, identity Acc@1 at item and parent level with
   query-level and concept-clustered CIs, the corpus ceiling of the indexed field, and
   headroom.
6. The replication table gives OE dev `resumen→texto` for all ten beside the previous
   study's figures, states in writing that the two are reference and not a paired contrast,
   and **contains a `dense_es_hiiamsid` row**.
7. 150 sweep runs exist, and the transferability verdict states, per field variant and query
   set, the argmax point, its Acc@1, and the paired delta against 0.60 / 0.35 with a CI.
8. The overlap implementation reproduces the OEB reference figures within 0.5 pp
   (94.09 % lexical, 99.93 % numeric) **before** being applied to OE.
9. Overlap tables exist for all four query sets, per condition, with all seven statistics.
10. The 15 runs are re-scored duplicate-aware; every item-level figure states corpus size,
    scored n and excluded n; the tables regenerate byte-identically from a clean checkout.
11. The stacked by-dose table is re-stratified on `texto_modification_count`.
12. D-012 recorded closed with the ten-method set; D-009 recorded *Delivered* with its two
    caveats; S8 moved `blocked` → `planned` in the registry with a log line.
13. `tests/` gains the three regression tests of work item 11, and the full suite passes.

## Out of scope

| Not done here | Done in |
|---|---|
| E1 ablation over the nine `single_<type>` conditions | S4 |
| Ceilings for RRF / PRF / cross-encoder | S4, where they are assembled from these runs |
| Structured track beyond S2's two arms | S5 |
| Mediation, mixed-effects models | S6 |
| Stacked headline and stratifications | S7 |
| Any run on the E3 dose or isolated sets | S8 |
| New methods (normalisation, learned representations, two-stage) | S9, S10, S11 |
| Anything touching the test split | S12 |
| Collapsing duplicate-`texto` groups, or dropping both concepts | Kept as an S3 sensitivity **only** if a "every leaf has a unique `texto`" claim is ever needed (D-033); not planned |

## Risks

| Risk | Handling |
|---|---|
| ColBERT `resumen` run is ~3 h and the six index builds are GPU-bound; the sprint overruns on wall-clock | The GPU block runs first and overnight; the sweep (under 2 h, CPU) and the overlap tables (CPU, no index) proceed in parallel and do not wait on it |
| E5, GTE and hiiamsid are not in `hf-cache`; a download fails or the pinned revision has moved | Resolve all three model revisions and warm the cache as the sprint's first action, before any config is minted; a model that cannot be pinned is reported, not silently substituted |
| Re-derived stacked feature tables do not reproduce `text_norm` row for row despite identical texts | Exit criterion 2 tests it. On failure the versioned tables stay authoritative and the corrected file is used only for its two new count fields — which is all S3 needs from it |
| The re-score changes an S2 headline enough to alter the G1 reading | G1 is not re-read; a gate is not re-run after the fact (D-032). Any material change is reported in S3's report as a correction to S2's numbers, with both figures printed |
| `dense_gte_instrQ` shares `impl: dense_gte`; the two configs differ only in query prefix and could collide on one index directory | Checked when the configs are minted: the pair must resolve to distinct `index/OE/` paths or share one index deliberately and say so in both configs |
| 150 sweep runs inflate `runs/` | Measured: ~33 MB per (variant, all three sets) × 50 ≈ 2 GB, against 1.4 TB free |

## Amendments

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
| 2026-09-27 | **A1. The loader carries the visible dose, and carries it conditionally.** `corpus_prep.QUERY_FIELDS` gains `texto_modification_count` / `texto_modification_types`, and `_as_record_from_obj` projects an extra field **only when the source record has it**. Also: `build_manifest.py` widened to cover the OE derived tables and the superseded copies, and `src/utils/check_run_inputs.py` added as the gate for exit criterion 3. | Work item 4 re-stratifies on `texto_modification_count`, and without this the field never reaches the feature tables the metrics layer reads — the corrected file would have been taken in and silently ignored. Conditional because an unconditional projection gives `single_texto` two all-null columns, changing the digest five S2 runs are stamped against (`e5b79ae4…`) for no information. The manifest listed only the deliveries, never the derived tables that `run_meta.json` actually stamps, so exit criterion 1 could not have been met as written. | None. No number moves; this is what makes work item 4 possible at all. Verified: full suite 355 passed, 1 xfailed. |
| 2026-09-27 | **A2. E0(b) runs all ten methods, not nine.** Work item 7 said "One exists (`bm25_unigram_params`)". It does exist — `runs/OE/resumen/bm25_unigram_params__k1-0.60__b-0.35__OE` — but it is an **S1 plumbing run from 2026-09-16, `code_dirty: true`** (`src/index_builders/README.md`, `src/utils/build_results.py`), made at `ddd224be` and never reported as a result. It is archived to `runs/_archive/S1/OE/resumen/` before E0(b) overwrites it, following the precedent S2 set in its own A5. | Operating rule 1: a run from a dirty tree is not reproducible from `(config, code commit, query-set digest)` and cannot be cited. S2 archived S1's other three runs for exactly this reason and never touched this one, because S2 never ran `resumen`. Found by `check_run_inputs.py`, which reported 16 runs where S2's report describes 15. | E0(b)'s run count goes from 19 to 20. No published number changes — the S1 run was never published. |
