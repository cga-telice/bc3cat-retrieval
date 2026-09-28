# STATE — `research/synthetic-oe`

The single living status file for this branch. Always current, under 2 KB. Dated snapshots
belong in `archive/`. Updated at every sprint transition and whenever something blocks.

**Last updated:** 2026-09-28 (S3 work items 1–8 done) · **Updated by:** César

---

## Where we are

**Active sprint: S3** — frozen at `8353cf7`, work items 1–8 done. **S2 is done**
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

- **S3 open, frozen at `8353cf7`** ([design](sprints/SPRINT_S3_DESIGN.md), amendments A1–A9).
  **Work items 1–8 done** 2026-09-28; 9–11 open (overlap tables, generated tables, tests). D-012 closed on the ten-method set.
- **All ten arms are indexed** over the full corpus (D-023), 70,242 docs each, every one
  `code_dirty: false`: `bm25_*` at `6336974`, `bge_m3_colbert` at `31bf1a1`, the other seven at
  `2dd653d`. The four **local dense** arms run on `transformers 4.57.6` / `sentence-transformers
  3.4.1`, not `requirements.txt`'s old pin, which cannot load GTE at all (**D-034**); the BM25 and
  BGE-M3 arms never touch it and keep their S2 stamps. GTE follows the config — `gte-multilingual-base`
  for both arms (**D-035**) — and their `embeddings.npy` are byte-identical, so they differ only at
  query time.
- **Runs in the sprint's own container, `bc3cat-s3`** — main checkout → `/work`, papermill and the
  pinned stack installed by hand, model cache in the bind-mounted `hf-cache/`; `logs/S3/` holds the
  executed notebooks and the build runner. It reports *unhealthy* because the image expects
  JupyterLab and we run `sleep infinity`. **`index/*/meta.json` does not stamp the ML stack**
  (defect H4), so those versions live only in the runner's captured output.
- **Worktree hazard closed** 2026-09-27: `run_context` now refuses a linked worktree, and the two
  containers that mounted one as `/work` are gone or repointed. D-018 amended.
- **Both upstream deliveries taken in** — see [`DELIVERIES.md`](DELIVERIES.md) for what was
  verified. Item-level scoring excludes duplicate-gold queries from work item 3 on (D-033).
- **[`DATASET_DEFECTS.md`](DATASET_DEFECTS.md)** — every corpus defect, classified by who fixes it.

## Incident — 2026-09-14

`data/`, `index/`, `runs/`, `logs/`, `hf-cache/` emptied by an agent session; rebuilt in S1.
[`archive/INCIDENT_2026-09-14.md`](archive/INCIDENT_2026-09-14.md) · D-019, D-020.

## Blocked / waiting

- **Real-query anchor** (200–500 Telice queries) — not requested. Off the path.

## Next action

S3 work item 9 — the overlap tables, and the only one of S3's measurements that is validated before
it is trusted: the implementation must reproduce the review analysis's OEB figures (94.09 % lexical /
99.93 % numeric) *before* being applied to OE. Per query against its gold: mean and median lexical
coverage, full-containment rate, mean numeric coverage, all-numbers-present rate, ≥1-number rate,
numbers per query — for `resumen`, `texto`, `single_texto` per type and `stacked_texto` per
`texto_modification_count`, with the D-004 sensitivity column. Then work items 10–11: the generated
`results/S3/` tables and the remaining regression tests.

## Latest results

**E0 is measured: all ten arms, identity and `resumen`, dev split** — 32 of 32 OE runs resolve
against the tree. Full tables come with work item 10; the two things already settled:

**The identity ceiling is a real instrument.** For a `texto`-only method the corpus permits at most
**0.9863** (292 of 776 duplicate-gold queries correct in expectation, so 484 unavoidable misses of
35,422). Three arms sit exactly on it — `bge_m3_colbert` 0.9861, `bge_m3_dense` 0.9861,
`dense_es_hiiamsid` 0.9864 — and the **only** two that exceed it are the two oracle arms,
`bm25_unigram_params` 0.9994 and `tfidf_unigram_phrases_replace` 0.9970, which can separate
identical `texto` only because they index the record's `parameters` (D-010, confirmed independently).
Below the ceiling and genuinely so: `bm25_unigram` 0.8870, `dense_e5` 0.5073, `dense_gte_instrQ`
0.1083, `dense_gte` 0.0975, **`bge_m3_sparse` 0.0509**.

**The BM25 operating point transfers, and that is a negative result worth having.** 25 points × 2
variants × 3 query sets, 144 runs, 0 failures. In 4 of 6 cells the argmax **is** `k1`=0.60 / `b`=0.35;
in the other two the gain is +0.0014 (p=0.845) and +0.0049 (p=0.417), with near-symmetric flip counts
— those settings reshuffle which queries succeed rather than retrieving better. `b` dominates, more
length normalisation monotonically hurts, and both variants agree. **Both keep 0.60/0.35 into S4**
(D-036, referred to César rather than resolved in passing, because the frozen rule names the argmax and
D-027 was rejected for reinterpreting a rule after results). So a five-fold change in query length does
not move the operating point: the previous study's tuning is not where its headline is weak.

**`bge_m3_sparse` fails in the opposite direction to the one predicted.** D-012 kept it as the most
interesting untested arm, on the expectation that learned sparse expansion might *survive* L1
variation. Its identity ceiling is 0.0509: it cannot retrieve a document from that document's own
text. Diagnosed, not assumed — the gold sits at rank 2–6 with no ties, and the doc vectors are **not
L2-normalised** (norms 0.47–1.09, a 2.3× spread) while scoring is a raw dot product, so a sibling
with a heavier vector out-scores the document against its own. That is BGE-M3's intended lexical
scoring, so it is a method property and a ceiling, not a harness defect — but it leaves the arm no
headroom to lose, and every later figure for it is read against 0.0509 (D-032).

### Earlier, from S2 and its re-score


Two directories, deliberately kept apart. **Every item-level figure is quoted with its scored n**
(D-033 note): the same run has one value on all queries and another on the duplicate-free
population, and both are correct about their own.

- [`results/S2/`](results/S2) — **what S2 reported.** Tuned BM25 falls under L1 (item Acc@1 0.608
  `unit_conversion`, 0.098 `num_to_text`, dev); the rules pipeline overtakes it in no contrast;
  ColBERT holds best under L1 and stacking, its advantage over *tuned* BM25 under
  `unit_conversion` being +0.083 [−0.010, +0.177], the one L1 contrast that does not invert.
- [`results/S3/s2_rescored/`](results/S3/s2_rescored) — **the control S3 inherits**, item-level on
  duplicate-free golds (`build_results_s3.py`, no retrieval, regenerates byte-identically). L1 and
  stacked move in the third decimal and no S2 conclusion turns on it. Identity moves materially and
  only for text-only methods: **`bge_m3_colbert` 0.9861 → 0.9998**, because 484 of its 492 identity
  misses were undecidable from the indexed field. `bm25_unigram_params` is unchanged at 0.9994 with
  **zero** duplicate-gold misses — the oracle signal of D-010, not robustness. Neither is a
  re-reading of G1 (D-032). `stacked_by_dose.md` re-stratifies on the corrected
  `texto_modification_count`: of the 730 dev queries S2 called dose 5, **193** show five
  modifications in the TEXTO, so S2's by-dose strata were misattributed, not merely uncertain. The
  cells' concept counts fall 27 → 17 → 8 → 2 → 1 with dose, which is the dose/family confound E3
  exists to remove — hypothesis H4 is answered in S8, not here.

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
