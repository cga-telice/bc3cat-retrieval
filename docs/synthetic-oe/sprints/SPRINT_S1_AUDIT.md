# Sprint S1 — audit

**Verdict:** PASS WITH FINDINGS
**Audited:** 2026-09-16 · report blob `f316d9c` (sha256 `f21e2bde…`) at commit `a8e5d21` · runs `D:\Users\cesar\Dev\Phd\bc3cat-retrieval\runs\OE\{texto,resumen,single_texto,stacked_texto}\bm25_unigram_params__k1-0.60__b-0.35__OE` and `…\runs\OEB\resumen\bm25_unigram_params__k1-0.60__b-0.35`

No number in the report is unreproducible, no comparison mixes samples, and the frozen design was not edited outside its Amendments table. Eight findings, two of them major; none invalidates a figure.

## Verified

**Provenance — all five stamps recomputed independently, all match.**

| stamped digest | file | my `sha256sum` |
|---|---|---|
| config `c695c126f20d5a9e…` | `configs/bm25_unigram_params__k1-0.60__b-0.35__OE.yaml` | matches |
| config `34c184257a186497…` | `configs/bm25_unigram_params__k1-0.60__b-0.35.yaml` | matches |
| query-set `643f1a72d5c5df17…` | `data/processed/OE_long_feats.parquet` | matches |
| query-set `f041a8e85d766c55…` | `data/processed/OE_short_feats.parquet` | matches |
| query-set `e5b79ae44fcc544e…` | `data/processed/OE_single_texto_feats.parquet` | matches |
| query-set `7b0894e6bc5c82d3…` | `data/processed/OE_stacked_texto_feats.parquet` | matches |
| query-set `a7fdce118e1adbd6…` | `data/processed/OEB_short_feats.parquet` | matches |
| fixture input `1bdfb1bda4bcc259…` / `58b211e720a09763…` | `OEB_long_feats.parquet` / `OEB_features_meta.json` | matches |

`code_commit beb7b52` is HEAD's real value for the window the runs were created in (`beb7b52` 02:15:36, runs 02:17–02:19, `a8e5d21` 02:22:06 — all 2026-09-16 local).

**Re-derivation from raw `results_top*.jsonl.gz`, outside `metrics.ipynb`** (own scorer over `gold_item_key` / `gold_parent_key`, 10 dp):

| run | item Acc@1 re-derived | `metrics_dual.json` |
|---|---|---|
| `OEB/resumen/…` | 0.9736588306 | 0.9736588306 |
| `OE/texto/…` | 0.9994071481 | 0.9994 (0.9994071481) |
| `OE/resumen/…` | 0.6472531195 | 0.6473 |
| `OE/single_texto/…` | 0.6205802357 | 0.6206 |
| `OE/stacked_texto/…` | 0.1788972630 | 0.1789 |

Recall@5, Recall@10 and MRR also reproduce exactly on all five, item and parent. The single parent-level divergence I saw on OEB (0.9851717902 vs 0.9852320675) is my own artefact: query `q_008141` carries `gold_item_key = "OEB210"` / `gold_parent_key = "OEB210"` (no `$`), which my regex-derived parent key does not match; 1/16,590 = exactly the gap. The run's recorded gold is authoritative and correct. nDCG@10 not re-derived (parent-level IDCG depends on family size); it is the one metric I took on trust.

**The central claim holds and is not vacuous.** `src/utils/compare_metrics.py` reports missing rows unconditionally — `allow_extra_scopes` tolerates *additions only* (`for key in sorted(expected_rows.keys() - actual_rows.keys()): differences.append("missing row: …")` runs before the flag is consulted), and `tests/test_golden_fixture.py::test_the_migration_only_added_slices` asserts `before <= after` plus a closed list of permitted new scope prefixes. All six fixture rows exist in the migrated run and every one of the 36 figures is byte-equal. The two executions are genuinely different: fixture at `a1a2391` (2026-09-15 21:18), migrated run at `beb7b52` (2026-09-16 02:19), with five notebook commits, the resolver and the batching commit in between. Sample identity is anchored, not assumed: the fixture's `inputs.short_feats.sha256` equals the new run's `query_set_sha256`, so `df.sample(16590, random_state=42)` drew the same rows from the same file.

**Batching is on the reported path, not dead code.** `retrievers/bm25_unigram_params.load` returns `bm25_unigram.BM25Searcher`; `retrieve.ipynb` calls `search_batch(texts, k=K)` with no `batch_size` when `BATCH_SIZE is None`, which hits the `_USE_DEFAULT` sentinel and the 2048-row default — not the `batch_size=None` single-block path.

**Split discipline is clean.** Every OE run's gold concepts are a subset of `SPLITS.md` dev: texto/resumen/single 42 concepts, stacked 41, **zero** test concepts in any run, verified over all 45,571 query records. `utils/splits.py` parses `SPLITS.md` rather than recomputing, and raises on an unknown concept. `index/OE/…/meta.json` records `num_docs: 70242` and `mapping.jsonl` has 70,242 lines — D-023 honoured, dev was not made an easier task.

**Counts reconcile.** 35,422 / 35,422 / 2,206 / 2,521 against `SPLITS.md` line 19; single-set per-type counts match `SPLITS.md` lines 50–60 exactly (306/130/315/108/306/291/302/204/244 = 2,206). `dropped: 0` in all five `run_meta.json` (but see F4). `modification_count` slices on stacked sum to 2,521.

**Design freeze is intact.** `git diff 9cd244c..HEAD -- docs/synthetic-oe/sprints/SPRINT_S1_DESIGN.md` is two hunks: the freeze stamp placeholder filled in, and one dated Amendments row. Goal, Entry state, Work, Design constraints, Exit criteria, Out of scope and Risks are untouched.

**Tests.** `python -m pytest -q` → **269 passed in 9.97s**, 0 skipped, 0 failed, as claimed.

**Overclaiming.** `headline_figures.md` is explicitly labelled "These are not results"; the Hypotheses table records H1–H6 as *not addressed*; no per-type point estimate is quoted in the report's prose; the thin-slice, applicability and stacked-set caveats are not invoked because no claim is made that would need them. On its own terms the no-results discipline holds (one shape-level reservation at F7).

## Findings

### F1 — major — the golden fixture is untracked; exit criterion 3's evidence does not exist in the repository
`.gitignore:11` is `*.json`, with no negation for `tests/fixtures/`. `git ls-files tests/fixtures/` returns nothing and `git log -- tests/fixtures/` is empty; commit `b1128f8` ("capture the OEB golden fixture") committed `src/utils/compare_metrics.py` and `tests/test_golden_fixture.py` only. So `tests/fixtures/oeb_bm25_pre_migration/{STAMP.json,metrics_dual.json}` live in the working tree alone.

Consequences. (a) The sprint's single claimed finding rests on an artefact with no version-control history — an auditor cannot establish that today's fixture is the one written at 21:18 on 2026-09-15. (b) `STAMP.json:metrics_sha256 = d82d58d6…` is the digest of `runs/bm25_unigram_params__k1-0.60__b-0.35/metrics_dual.json` (which I confirmed still matches), *not* of the frozen copy; `freeze_fixture.py` copies with `Path.write_text`, which on Windows translated LF→CRLF, so the frozen file digests to `11d8714…` and is anchored by nothing. Content is equal after newline normalisation — I checked — but the integrity chain has a hole at both ends. (c) On a fresh clone the six module-level `load(FIXTURE / …)` calls in `tests/test_golden_fixture.py` raise `FileNotFoundError` and the two criterion tests skip; the "269 tests, 0 skipped" figure is true only of this machine.

Fix: negate the ignore for `tests/fixtures/**` and commit both files; record the frozen copy's own digest in `STAMP.json`; write the copy with `newline="\n"`.

### F2 — major — exit criterion 4 is not met as written, and the re-reading was never amended
Criterion 4 (`SPRINT_S1_DESIGN.md:109`): "No notebook in {data, features, index_builder, retrieve, metrics} contains a literal collection name outside a comment; **grep is the check**." My grep over all code cells finds `COLLECTION  = "OEB"` in the papermill parameters cell of `src/data.ipynb` and `src/features.ipynb` (cell 0 in each). Under the criterion as frozen, criterion 4 fails.

The report declares the substitution (Deviations row 3) and states "Not amended before the fact", and `tests/test_notebooks_are_parameterised.py` enforces the substitute rule over all five notebooks. The design file itself was not edited, so this is not a silent post-freeze rewrite — but it is an exit criterion redefined after the fact and recorded only in the record document, not in the plan's Amendments table where the design's own freeze rule sends it. The re-reading is defensible on the merits; its placement is not.

Fix: add a dated Amendments row to `SPRINT_S1_DESIGN.md` restating criterion 4 as enforced, or mark criterion 4 not met.

### F3 — minor — a slice reports more queries than the run has
`docs/synthetic-oe/results/S1/slices.md` and `runs/OE/stacked_texto/…/metrics_dual.json` carry `modification_type:template_paraphrase` with `queries = 5,042` on a 2,521-query run. Cause: `OE_stacked_texto.json` lists `template_paraphrase` **twice** in `modification_types` for all 4,998 records (I counted: occurrences 9,996, distinct 4,998), and the slice explodes the list without de-duplicating. The doubling is uniform, so the metric values are unaffected (they equal the overall row exactly, as expected when the type covers 100 % of the set), but the published population is wrong by 2×, and a non-uniform duplicate in a future corpus would silently re-weight a slice mean. No other type is affected (all eight others: occurrences = distinct).

Fix: de-duplicate `modification_types` when building the slice, and add an upstream note — this is a BC3CAT-Syn packaging artefact not listed among the branch's "pantry artefacts".

### F4 — minor — `dropped: 0` is a literal, and the test that checks it asserts against a constant
`src/retrieve.ipynb` writes `"dropped": 0` as a hard-coded value in `run_meta`; nothing computes it. `tests/test_provenance.py::test_every_run_records_what_it_dropped` then asserts `meta["dropped"] == 0` — asserting against data the harness generated unconditionally. It cannot fail. The substantive guarantee is real and elsewhere: `assert_gold_present` raises before scoring, and the `len(top_idx) != len(qkeys)` check raises after. The report cites the weak evidence (`dropped: 0` in five files) for exit criterion 5 rather than the strong evidence.

Fix: compute `dropped` as `n_after_filters - len(qkeys)` (necessarily 0 given the raise) so the stamp records a measurement, and have the test compare `queries` against the query table's post-split row count.

### F5 — minor — two numbers in the report's prose have no run and no stamp
Report line 96: "Re-running it gives item Acc@1 0.9737 … the full 47,513 give **0.9735**." The 0.9735 figure exists in no run directory — `runs/` holds five stamped runs plus the pre-migration flat one (16,590 queries), none of them the full 47,513-query execution. The figure appears only in prose and in commit message `a3c4ce0`. By the branch's own operating rule 1, it does not exist. The same applies to "the full OEB set now runs in 48 s" (report line 92).

Fix: either drop the two figures or keep the run and cite it.

### F6 — minor — the report's own provenance table omits the sampling parameter it criticises the manuscript for omitting
`results/S1/run_provenance.md` has columns for K and batch but none for `random_sample`/`random_state`, so the OEB row reads as 16,590 queries at split "all" with nothing to say it is a 35 % deterministic sample of 47,513. `run_meta.json` records `random_sample: 16590, random_state: 42` correctly. Given finding 8 is precisely "the sampling … is nowhere stated", the generated table should surface it.

### F7 — minor — `headline_figures.md` puts two collections and five query sets in one table
The design constraint at `SPRINT_S1_DESIGN.md:93` reads "no OEB number is compared with an OE number in this sprint: different corpora, different query length, nothing controlled." The table stacks `OEB/resumen` 0.9737 beneath `OE/stacked_texto` 0.1789 in the same column. Every row is stamped with its own `run_id` and query count and the header disclaims results, so this is not the defect that sank the previous submission — but it is the shape of it, and it invites the comparison the design forbids. Splitting OEB into its own table would cost nothing.

### F8 — minor — index artefacts are outside the four-part stamp, and the S1 evidence for exit criterion 2 is now vacuous
(a) `index/OE/…/meta.json` records `created_utc 2026-09-15T20:18:39Z`, i.e. the index was built from working-tree `index_builder.ipynb` some three hours before that notebook was committed at `09d18a0`. The run stamp names `code_commit beb7b52` with only `src/index_builders/README.md` dirty, which is true of the retrieval step but says nothing about the code that produced the index the run read. `meta.json` carries `corpus_hash` and params but no code commit. Reproducibility from `(config, code commit, query-set digest)` is therefore established for retrieval and metrics, not for indexing.
(b) Exit criterion 2 is evidenced by quoting `migrate_configs.py`'s "Resolved inputs are byte-identical before and after for all 77 configs". That script is S0 work item 4 and its "before/after" is the literal→template textual rewrite; `grep -l "/work/data/processed/OEB_" configs/*.yaml` now returns zero files, so every config falls into "already templated", `migrated == original`, and the comparison is `resolve(cfg) == resolve(cfg)`. Re-running it today proves nothing about the S1 notebook migration. Note also that the script prints that sentence unconditionally, before the `SystemExit` on failures. The criterion's substance is nonetheless covered by `tests/test_configs_resolve.py` (154 parametrised tests over 77 configs, all passing), which is the evidence that should be cited.

## Unverifiable

- **"No number changed" across the late stamp addition** (Deviations row 4). The first five runs carried `run_id` and config path only and were overwritten by the re-runs; their artefacts are gone. That the OEB re-run reproduces the fixture is verified, but the claim that the four *OE* runs' figures are unchanged from the unstamped first pass has no surviving artefact. Stated as fact in the report; it should be stated as an inference.
- **`nDCG@10`** on any run. I re-derived Acc@1, Recall@5, Recall@10 and MRR independently; nDCG's parent-level IDCG depends on the family-size map, which I did not rebuild.
- **Report finding 9's ranx claim.** "`ranx` is not among them, though the root contract specifies ranx 0.3.7 … Both were installed by hand to run this sprint." `grep -rn "ranx" src/ tests/` returns nothing, and `git show a1a2391:src/metrics.ipynb` contains no `ranx` either — the metrics are hand-rolled in-notebook both before and after the migration. So ranx cannot have been needed to run S1. The `papermill` half of the claim is sound (all five notebooks carry a tagged `parameters` cell). Separately, this means the root contract's "Metrics via `ranx` 0.3.7" has not described the harness for some time — a pre-existing divergence S1 neither caused nor recorded.
- **Elapsed times and the CRLF explanation** for `src/index_builders/README.md`. The host tree is clean (`git status --porcelain -- src configs` is empty), which is consistent with the report's account, but the container-side state cannot be inspected from here.

## Exit criteria

| Criterion | Met | Evidence |
|---|---|---|
| 1 · `run_context.py` committed with tests; `pytest` from a tracked `tests/` | **yes** | `python -m pytest -q` → 269 passed, 0 skipped; `pytest.ini` tracked; 11 test modules tracked under `tests/` |
| 2 · 77 configs resolve byte-identically before and after under `OEB`; 0 defects | **yes, on weaker evidence than cited** | 77 configs, all resolve, 0 defects via `tests/test_configs_resolve.py` (154 tests). The cited `migrate_configs.py` output is an S0 result and is vacuous if re-run today — F8(b) |
| 3 · Fixture re-run reproduces `metrics_dual.json` exactly | **yes** | All 36 figures equal; `diff_metrics` reports missing rows independently of `allow_extra_scopes`; fixture and run are different commits (`a1a2391` vs `beb7b52`) over the same input digest `a7fdce11…`. Caveat: the fixture is untracked — F1 |
| 4 · No collection literal in the five notebooks | **no, as written; yes as re-read** | `COLLECTION = "OEB"` in the parameters cell of `src/data.ipynb` and `src/features.ipynb`. Substitute rule enforced by three tests but never amended into the design — F2 |
| 5 · `retrieve.ipynb` raises on absent gold; 0 dropped on all four OE runs | **yes** | `utils/corpus_prep.assert_gold_present` called before scoring on the full query table, with its own tests; row-count raise after scoring; 45,571 gold keys all present. The `dropped: 0` stamp itself is a literal — F4 |
| 6 · Config completes on OE for all four query sets (dev), each with its four-part stamp | **yes** | Four `run_meta.json` with all four fields non-empty; every digest recomputed and matching. Stamp added late; the claim that the pre-stamp runs gave the same figures is unverifiable |
| 7 · Dual-target metrics plus every named slice, reconciling with `SPLITS.md` | **yes, with one wrong count** | condition, modification_type, modification_count, subchapter, family_tercile and has_numbers all present on all four runs; single-set per-type counts match `SPLITS.md` exactly; `modification_type:template_paraphrase` on stacked reports 5,042 of 2,521 — F3 |
| 8 · D-016 closed; D-022 executed; D-023 and D-024 recorded | **yes** | `docs/synthetic-oe/DECISIONS.md` lines 175 (D-016 Closed), 316 (D-022 Accepted, executed), 350 (D-023), 365 (D-024), 378 (D-008 amendment), plus dated closing notes |

No tracked file was modified during this audit; `git status --porcelain` shows only the pre-existing `MethodsX_BC3CAT.docx` change. One verification step was blocked by the permission system: re-running `python src/utils/migrate_configs.py --target OEB` (read-only, `--apply` omitted) was denied, so F8(b) is established by reading the script and confirming that no config still contains the literal spellings it rewrites.
