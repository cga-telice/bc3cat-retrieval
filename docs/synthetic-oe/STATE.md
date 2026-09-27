# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under 2 KB. Dated snapshots
belong in `archive/`. Updated at every sprint transition and whenever something blocks.

**Last updated:** 2026-09-27 (S3 opened) · **Updated by:** César

---

## Where we are

**Active sprint: S3** — design frozen at `8353cf7`, 2026-09-27, no work started. **S2 is done**
(2026-09-17). **Gate G1 read: ambiguous** — the L1 branch says proceed, but two gated arms fail
the identity branch under the design as frozen: `bm25_unigram` 0.8870 (clustered [0.7996,
0.9242]) and `bge_m3_colbert` 0.9861 (clustered [0.9463, 1.0000], straddling 0.98). S3 inherits
those ceilings; under D-032 they are read as per-method ceilings, not as a gate.

## Done

Release received and validated (`INTAKE.md`, 2026-09-08); proposal and plan written. Each
sprint below was audited in a fresh session, returned PASS WITH FINDINGS, and had every finding
resolved before it was marked done — see its `SPRINT_XX_AUDIT.md`.

- **S0 2026-09-15** — `data/` repopulated and re-verified, `SPLITS.md` (seed `20260915`), 77
  configs naming collection and retriever, E3 issued.
- **S1 2026-09-16** — five notebooks on one resolver, gold read from the query record, batched
  scoring. The OEB fixture reproduces to ten decimals: the migration moved no number.
- **S2 2026-09-17** — 15 stamped runs, 5 methods × 3 query sets on OE dev. Tuned BM25 falls
  under L1; the rules pipeline overtakes it in none of 8 contrasts; ColBERT inverts in 3 of 4.

## In flight

- **S3 is open and frozen** ([`SPRINT_S3_DESIGN.md`](sprints/SPRINT_S3_DESIGN.md) @ `8353cf7`,
  amendments A1–A2). Eleven work items: the two intakes, the duplicate-aware re-score of S2's 15
  runs, six new OE configs, ten identity ceilings + ten `resumen` replications on dev, the 150-run
  `k1`/`b` grid, the overlap tables. **D-012 closed** on the ten-method set.
  **Work item 1 done** (2026-09-27); 2–11 open.
- **Container:** this branch runs one per sprint — `bc3cat-s1`, `bc3cat-s2`, now **`bc3cat-s3`**
  (image `quay.io/jupyter/pytorch-notebook:cuda12-python-3.11.8`, main checkout → `/work`,
  `HF_HOME=/work/hf-cache`, `--gpus all`, `sleep infinity`; papermill 2.7.0 installed by hand).
  Identical core libraries to `bc3cat-s2` — python 3.11.8, pandas 2.2.2, numpy 1.26.4, pyarrow
  15.0.2, sklearn 1.4.2 — which is why the seven unchanged tables reproduce byte for byte.
  **Do not use the `jupyter-pytorch` container:** it mounts
  `.claude/worktrees/structured-retrieval-type-5aeb7f` as `/work`, not this checkout, with the
  main `data/`, `index/`, `runs/` bound in over it. Running this branch's notebooks there would
  execute another branch's code against this branch's data (D-018).
- **[`DATASET_DEFECTS.md`](DATASET_DEFECTS.md)** — every corpus defect in one place, classified
  by who fixes it. Opened 2026-09-17.
- **Upstream delivery of 2026-09-27 (`synthetic` @ `f2457fa`) — taken in.** Work item 1 closed
  2026-09-27. Sidecar `OE_duplicate_texto_groups.json` `b3cfcad4…` and corrected
  `OE_stacked_texto.json` `c34a222a…` in; the corpus files with the flag inside deliberately
  refused. Stacked derived tables re-derived: norm `81cd501b…` → `4939d99f…`, feats `7b0894e6…` →
  `f34c1798…`, with **all 26 pre-existing columns identical row for row** — so S2's stacked Acc@1
  stands, and the superseded trio survives under digest-stamped names so those runs still resolve.
  The other seven OE derived tables came out **byte-identical**. Digests in
  [`MANIFEST.md`](MANIFEST.md), narrative in [`INTAKE.md §2.1`](INTAKE.md), proof in
  `tests/test_intake_20260927.py` (30 tests) and `src/utils/check_run_inputs.py`.
  Item-level scoring excludes queries whose gold is a duplicate (776/35,422 `texto`, 29/2,206
  `single_texto`, 55/2,521 `stacked_texto`; dev only, test is clean), so every scored query has
  exactly one valid answer — applied from work item 3 on.
- **E3 balanced dose set — arrived 2026-09-17, recorded 2026-09-27, not yet taken in.** S3 work
  item 2 copies and registers `OE_dose_texto.json` (`555fab84…`), `OE_isolated_texto.json`
  (`054041ff…`) and `OE_leaf_applicability.jsonl` (`eda12d17…`), and runs nothing with them.


## Incident — 2026-09-14

`data/`, `index/`, `runs/`, `logs/`, `hf-cache/` emptied by an agent session; rebuilt in S1.
[`archive/INCIDENT_2026-09-14.md`](archive/INCIDENT_2026-09-14.md) · D-019, D-020.

## Blocked / waiting

- ~~**E3 balanced dose set**~~ — **it arrived.** Delivered upstream 2026-09-17 (`4d10af2`) and
  unrecorded here for ten days; found by re-hashing the handoff while verifying S3's entry state.
  3,000 dose queries (600 leaves × 5 rungs, nested, 600 per count), 5,400 isolated effects,
  per-leaf applicability, plus an upstream response answering the request point by point. Two
  caveats for S8: **7 OEB concepts only**, straddling the split (4 dev, 3 test), so a dev dose
  slope rests on 4 concepts. S8 goes `blocked` → `planned` when S3's work item 2 lands; gate G3
  no longer has an absence to rule on. See the D-009 note of 2026-09-27.
- **Real-query anchor** (200–500 Telice queries) — not requested. Off the path.

## Next action

S3 work item 2 — the E3 intake: copy and register the three dose files, validate the ladder,
record the 7-concept and split-straddling caveats, move D-009 to *Delivered* and S8 to `planned`.
Then work item 3, the duplicate-aware re-score of S2's 15 runs from their stored top-100 lists —
the control S3 inherits — and work item 4, re-stratifying the stacked by-dose table on
`texto_modification_count`, now that the field reaches the feature tables. Before the GPU block:
resolve and warm the E5, GTE and hiiamsid model revisions, since `hf-cache/hub` holds only
`BAAI/bge-m3`. ColBERT is the L1 reference (D-029, amended); the identity ceilings above stand.

## Latest results

[`results/S2/`](results/S2) — the first reportable numbers, generated by
`src/utils/build_results_s2.py`. Tuned BM25 falls under L1 (item Acc@1 0.608 `unit_conversion`,
0.098 `num_to_text`, dev); the rules structured pipeline does not overtake it in any contrast;
ColBERT holds best under L1 and stacking, though its advantage over *tuned* BM25 under
`unit_conversion` is +0.083 [−0.010, +0.177] — the one L1 contrast that does not invert. Stamps
in `run_provenance.md`.

## Open decisions

See `DECISIONS.md` (`Open`). **D-012 (method scope on OE) is closed** — 2026-09-27, ten arms,
full `k1`/`b` re-sweep; it gated S3 and no longer does. Closed in S1:
**D-016**, **D-022**. Recorded in S1: **D-023** (index over the full corpus), **D-024**
(`OEB#`), **D-025** (the stacked dose is one lower than `modification_count` says — it reaches
H4), and an amendment to **D-008** adding `texto` as the fourth query set. Recorded in S2: **D-026** (structured
pipeline ported by file checkout, not merged), **D-030** (a threshold on an Acc@1 is read
against the concept-clustered interval). Rejected in S2: **D-027** (re-defining G1's stop rule
after the result). Still Proposed, amended: **D-028** (tie-free reading for every family),
**D-029** (ColBERT as the L1 reference for S3).
