# Sprint S0 — Reproducibility foundation and splits · design

> **Frozen at:** `<commit SHA>` · `<date>`
> This section is read-only from that commit. Changes go in **Amendments** below, dated and
> justified — never as in-place edits. `git log -- <this file>` after the freeze date is an
> audit trail; keep it honest.

| Field | Value |
|---|---|
| **ID / type** | `S0` · backbone |
| **Status** | planned → active |
| **Serves** | all hypotheses (H1–H6), O5 |
| **Depends on** | — (first sprint) |
| **Decisions applied** | D-007, D-008, D-012, D-016, D-017, D-018, D-019, D-020 |
| **Effort** | 0.5 w |
| **Predecessor / successor** | — / S1 |

## Goal

At the end of S0 it is **known which concepts may ever be tuned on and which may not**, and
that claim is reproducible from a committed, seeded artefact rather than from a notebook's
memory. Today the corpus exists but nothing partitions it, the 77 configs cannot name a
collection other than OEB, and one cannot be executed at all. S0 closes the gap between
"the data is here" and "a run is reproducible from `(config, code commit, query-set digest)`
and nothing else". No retrieval result is produced, and none is expected.

## Entry state

Verified on 2026-09-15 in the main checkout, not assumed:

| Condition | How it was checked | Result |
|---|---|---|
| No dependency sprints | `SPRINTS.md` registry: S0 depends on `—` | ok |
| Five OE files present | `ls data/processed/` | ok — 5 present, plus `OE_handoff_README.md` |
| OE digests match intake | SHA-256 recomputed in place, compared with `INTAKE.md §2` | ok — 5/5 (`b6a43961295cc2ca`, `1bde21157ef97421`, `2d3273ddb3e443a1`, `02a2c270d7ffe147`, `0cd380e9e44ad8c5`) |
| OEB working set present | `ls data/processed/OEB_*` | ok — 7 files, restored from `../bc3cat-dataset` |
| Corpus record counts | **not yet verified** — this is work item 1 | pending |
| `runs/`, `index/` | empty after the 2026-09-14 incident (D-019) | expected — S0 produces no runs |

**Carried in from the incident.** `data/` was repopulated by copy, not recovered. The digests
prove the OE files are the intake artefacts; the OEB files carry **no recorded digest
anywhere**, so their provenance is "copied from `../bc3cat-dataset` on 2026-09-15" and
nothing stronger. Work item 1 fixes that for both.

## Work

1. **Manifest.** `docs/synthetic-oe/MANIFEST.md`: full SHA-256 (not prefixes), byte size and
   record count for each of the five OE files **and** the seven OEB files. OE digests are
   cross-checked against `INTAKE.md §2`; a mismatch stops the sprint. Assert the counts
   `INTAKE.md` claims — 70 242 corpus records, 83 concepts, 4 439 single, 4 998 stacked —
   and record what was actually observed, even where it agrees.
2. **Split.** `docs/synthetic-oe/SPLITS.md`: the 83 concepts partitioned dev/test **by
   concept**, stratified by subchapter (OEA–OEG) and by family-size decile, from a named
   seed. Written as an explicit `parent_key` list, not as a rule to be re-executed. Resolves
   **D-007**.
3. **Layout.** Adopt `index/{collection}/{method}` and
   `runs/{collection}/{queryset}/{method}`. Resolves **D-008**.
4. **Config migration — two populations, not one.** Verified by parsing all 77:
   - **62 configs** are JSON-in-`.yaml` with literal absolute paths
     (`/work/data/processed/OEB_short_feats.parquet`). Collection cannot be changed by
     editing one field; their `inputs` must be rewritten to `{data_dir}/{collection}_…`.
   - **15 configs** are YAML with templated inputs; for these `collection:` is sufficient.
   - **72 of 77 declare no `retriever` block** — not two; see the 2026-09-15 amendment
     to D-016.
5. **Unrunnable and orphan code.** `dense_colbert128.yaml` declares
   `src.index_builders.dense_colbert128` (under a `builder:` key, not `method:`) and
   `src.retrievers.dense_colbert128`; **neither file exists**. Decide D-017 — implement or
   delete — and record it. `src/retrievers/tfidf_unigram_phrases.py` is referenced by zero
   configs: confirm it is reachable some other way, or remove it.
6. **Cross-repo request** for the E3 balanced dose set (S8) issued to `bc3cat-dataset` now,
   because its lead time is external and it blocks S08 only (D-009).

## Design constraints

- **The split partitions concepts, never leaves.** A leaf-level split puts siblings of a test
  item in dev, and every method in this study discriminates between siblings. This is the one
  constraint whose violation invalidates the whole plan rather than one sprint.
- **The split is an artefact, not a procedure.** `SPLITS.md` holds the concept keys
  themselves. A seeded procedure that regenerates them is not equivalent: it makes the split
  a function of a library version.
- **Stratify by subchapter and by family size, because both are extreme.** OEB alone is
  67.6 % of the corpus and OEF is 0.1 %; mean family ≈ 846 leaves. An unstratified draw can
  put a subchapter entirely on one side.
- **No tuning ever touches test** — not hyper-parameters, not model selection, not
  thresholds, not "just to look". The frozen test evaluation runs once, in S12.
- **Config migration must not change any published behaviour.** Rewriting the 62 literal
  paths to templates changes how a path is spelled, never which file is read. Any config
  whose resolved inputs differ after migration is a defect, not a migration.
- **The README results table is never a source.** `docs/reviews/paper_28.tex` is
  authoritative wherever the two disagree.

## Exit criteria

1. `MANIFEST.md` committed; all five OE SHA-256 values match `INTAKE.md §2`, **and** the
   observed record counts equal the claimed ones or the difference is documented.
2. `SPLITS.md` committed, listing every one of the 83 concepts exactly once, each assigned to
   `dev` or `test`; union equals the full concept set and intersection is empty, verified by
   a committed check rather than by eye.
3. All 77 configs resolve to an existing module for every `builder`/`retriever` they declare,
   and each declares its retriever explicitly — restating a default is acceptable, relying on
   one is not (D-016).
4. `dense_colbert128` is either runnable or deleted; D-017 is closed either way.
5. A config parameterised on `collection: "OE"` resolves its inputs to the OE files, proven
   by a dry run that reports the resolved paths — not by inspection of the YAML.
6. The E3 request is recorded in `DECISIONS.md` with the date it was issued.
7. `runs/` is still empty. An S0 that produced a run did something outside its design.

## Stopping criterion — probes only

Not applicable: S0 is backbone.

## Out of scope

- Any retrieval run, index build or metric — S1 adapts the harness, S2 produces the first
  numbers.
- The loader, gold-key and flat-`parameters` fixes that BC3CAT-Syn needs: those are S1.
- Rebuilding the `index/` lost on 2026-09-14. Indexes are derived; they are rebuilt when a
  sprint needs them, deliberately (D-019).
- Reconstructing the previous study's `runs/`. Out of scope for this branch entirely.

## Risks

| Risk | Handling |
|---|---|
| The 62 JSON-style configs are rewritten by hand and drift | Migrate by script, then diff resolved input paths before/after for all 77; the diff must be empty except for the collection segment |
| A stratified split leaves a subchapter with too few concepts to be meaningful | Report per-subchapter dev/test counts in `SPLITS.md`; where a stratum cannot be split sensibly, record the decision rather than silently merging it |
| D-016's error (2 vs 72) suggests the config inventory was sampled, not exhaustive | Re-run the inventory over all 77 by parsing, not grepping |
| OEB files carry no recorded digest, so future corruption would be undetectable | Work item 1 records their digests now; from then on they are checkable |
| The E3 request slips and nobody notices until S7 | Its issue date is an exit criterion, and S8 is already `blocked` in the registry |

## Amendments

| Date | What changed | Why | Effect on claims |
|---|---|---|---|
