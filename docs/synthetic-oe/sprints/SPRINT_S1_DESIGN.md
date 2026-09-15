# Sprint S1 — Harness adaptation to BC3CAT-Syn/OE · design

> **Frozen at:** `9cd244c` · `2026-09-15`
> This section is read-only from that commit. Changes go in **Amendments** below, dated and
> justified — never as in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S1` · backbone |
| **Status** | planned → active |
| **Serves** | all hypotheses — nothing downstream can run until this closes |
| **Depends on** | S0 (`done`, audited) |
| **Decisions applied** | D-007/D-021, D-008, D-016, D-022; raises D-023, D-024 |
| **Effort** | 2 weeks |
| **Predecessor / successor** | S0 → S2 |

## Goal

At the end of S1 it is known that the harness reads what its config says it reads, scores
against the gold the query declares rather than against its own key, and produces the same
OEB numbers after the change as before it. Today none of those three is known: the
collection is a literal in five notebooks, gold is inferred from `query_item_key`, and there
is no baseline to compare against. S1 converts "the config resolves to OE" (S0 exit 5, and
its caveat) into "OE runs end to end, and the plumbing that made it run did not move a
number". The sprint is plumbing and produces **no reportable result**.

## Entry state

Verified in the working tree on 2026-09-15, not taken from the registry.

| Requirement | How checked | Result |
|---|---|---|
| S0 `done` and audited | `SPRINTS.md` log; `SPRINT_S0_AUDIT.md` present | PASS WITH FINDINGS, six resolved |
| Five OE files present | `ls data/processed/OE_*.json` | 5/5 |
| OEB inputs present for the fixture | `ls data/processed/OEB_*` | 7 files, digests in `MANIFEST.md` |
| Split committed before any run | `SPLITS.md`, seed `20260915` | 42/41 concepts |
| Configs name collection and retriever | 77 YAML, one on `collection: "OE"` | present |
| `runs/`, `index/` empty | `find` | 0 files each — no baseline exists (D-022) |
| Main checkout, correct branch | `git rev-parse --show-toplevel`, `git branch --show-current` | pass, no worktree |

Two entry facts shape the work. `tests/` holds **no tracked file** (only two orphan `.pyc`),
so S1 also establishes the test harness it is asked to write tests in. And `data.ipynb` —
which owns `normalize_parameters_field` / `build_param_tokens` and the only `COLLECTION`
knob upstream of features — is not in D-022's three-notebook scope, although nothing on OE
can be built without it. S1 therefore migrates **five** notebooks, not three.

## Work

1. **`src/utils/run_context.py` + tests, no notebook touched** (D-022). Given a config path
   it returns the resolved data paths, `index/{collection}/{method}`,
   `runs/{collection}/{queryset}/{method}`, the query set, and the retriever module read
   from `retriever.module`. Missing key, missing file and unknown query set all raise.
2. **Test harness.** `pytest` under a tracked `tests/`, with the resolver, the parameter
   adapter and the fail-loud path as its first suites.
3. **Golden fixture, captured before anything moves.** On the current code, run
   `bm25_unigram_params__k1-0.60__b-0.35` on OEB `resumen→texto` end to end and freeze the
   run as the pre-migration reference, stamped with the `MANIFEST.md` digests of its inputs.
4. **`data.ipynb`** — parameter adapter accepting both the nested corpus shape and the flat
   query shape, axis labels rebuilt from `OE_concept_schema.json`; loader keyed on
   `(collection, queryset)`; projection preserves `gold_item_key`, `parent_key`,
   `modification_types`, `modification_count`. Produces `OE_short_norm`, `OE_long_norm` and
   one normalised query table per query set.
5. **`features.ipynb`** on OE → `OE_short_feats`, `OE_long_feats`, `OE_features_meta`.
6. **`index_builder.ipynb`** → one BM25 index at `index/OE/{method}`, built over the full
   70,242-leaf corpus.
7. **`retrieve.ipynb`** — run records carry `gold_item_key` and `gold_parent_key` taken from
   the query record; a query whose gold key is absent from the corpus raises; the in-notebook
   alias table is deleted and the module comes from the resolver (closes D-016).
8. **`metrics.ipynb`** — gold read from the run record, never from `query_item_key`; slices
   per condition, per modification type, per `modification_count`, per subchapter, per
   family-size tercile (**not** decile — S0 finding 4), plus the existing `has_numbers`.
9. **Migration verification.** Re-run item 3 after items 4–8 and require the metrics to be
   identical. Static path equality under `collection: "OEB"` is checked for all 77 configs,
   as in the S0 migrations.
10. **Answer the inherited open question**: whether the OEB corpus keeps its `OEB#` template
    row (47,513 parquet rows vs 47,514 JSON records). Recorded as D-024 either way.
11. **End-to-end OE run** of the same BM25 config on the four query sets, dev split only.

## Design constraints

- **The index is built over the full corpus; the split selects queries only.** Restricting
  the index to dev concepts would make dev an easier task than test and silently inflate
  every number this project reports. Not written anywhere before now — raised as **D-023**.
- **The identity rendering is `texto→texto`, not `resumen`.** D-008's queryset table lists
  three values and calls `resumen` "the identity rendering"; the proposal and S4's paired
  delta both use the leaf's unmodified `texto`. `texto` is added as a fourth queryset value
  and the parenthetical corrected — `resumen` is the *replication baseline*. Amendment to
  D-008, made before any run so that no path has to be renamed later.
- **S1 tunes nothing.** The operating point is the manuscript's OEB one (k1 0.60 / b 0.35),
  used as given. The re-sweep at OE query length is S3, and D-012 gates it.
- **S1 numbers are evidence of plumbing, not findings.** No S1 number is quoted as a result,
  and no OEB number is compared with an OE number in this sprint: different corpora,
  different query length, nothing controlled.
- **Fail loud, and prove it.** Queries dropped for any reason must be zero, asserted inside
  the run rather than inspected afterwards. The regression test asserts the raise.
- **The fixture proves preservation for OEB only.** It shows the migration did not move the
  numbers on the corpus it was captured from. It says nothing about whether OE is correct;
  that is what S2's identity control is for.
- **Dev split only.** S1 touches no test query. Full-corpus runs begin in S3.

## Exit criteria

1. `run_context.py` committed with tests passing; `pytest` runs from a tracked `tests/`.
2. All 77 configs resolve byte-identically before and after the migration under
   `collection: "OEB"`; 0 defects.
3. The golden fixture re-run after migration reproduces the pre-migration
   `metrics_dual.json` exactly — same item and parent figures, same query count.
4. No notebook in `{data, features, index_builder, retrieve, metrics}` contains a literal
   collection name outside a comment; grep is the check.
5. `retrieve.ipynb` raises on a query whose gold key is absent from the corpus, demonstrated
   by a test, and reports 0 dropped queries on all four OE runs.
6. The BM25 config completes on OE for `texto`, `resumen`, `single_texto`, `stacked_texto`
   (dev split), writing to `runs/OE/{queryset}/{method}`, each with its four-part stamp.
7. `metrics.ipynb` emits dual-target metrics plus every slice named in work item 8, on all
   four runs, with slice counts that reconcile against `SPLITS.md`.
8. D-016 closed; D-022 executed; D-023 and D-024 recorded.

## Out of scope

- `cross_encoder`, `hybrid`, `prf_bm25_orchestrator`, `reranker_tiebreak` — migrated when
  S4 needs them, against a resolver that has by then survived real use (D-022 scope).
- Any method beyond one BM25 config; the canonical set is D-012, gated at S3.
- Any tuning, any test-split query, any neural model download (S4 pays that cost).
- Deleting `src/utils/config.py` — a separate step once nothing imports it (D-022 follow-on).

## Risks

| Risk | Handling |
|---|---|
| S1 overruns and blocks everything behind it (the plan's own warning) | Work items 1–3 are the gate: if the fixture cannot be captured in the first three days, fall back to D-022's static path equality and record the downgrade as an amendment rather than extending the sprint |
| The fixture is irreproducible even before migration (non-determinism in the index build) | Then the harness was never reproducible; that is a finding, reported as such, and exit 3 is replaced by an explicit statement of what is not verifiable |
| Scope creep from five notebooks to seven | The four out-of-scope notebooks are named above; touching one requires an amendment |
| Flat/nested adapter mis-parses silently instead of raising | Unrecognised shapes are rejected; round-trip tests on both shapes with known expected `param_tokens` |
| The `OEB#` template row makes the fixture irreproducible from `data.ipynb` | Work item 10 answers it first; the fixture is captured from the parquets as they stand, digested |

## Amendments

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
