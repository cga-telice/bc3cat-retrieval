# Sprint S91 — Coded vs decoded `resumen` · report

| Field | Value |
|---|---|
| **Design** | [`SPRINT_S91_DESIGN.md`](SPRINT_S91_DESIGN.md) · frozen at `09d11f7` · amendments A1–A3 |
| **Closed** | 2026-09-29, inside the 3-day time-box. `done` withheld until `/audit S91` in a fresh session |
| **Code commit** | All 20 new runs at `cf92bc8`, clean. Reused coded runs: `2e49566` (4), `922ae53` (5), `a5700a6` (1), as S3 stamped them. Tables generated at `3dc992f` |
| **Query-set digests** | coded `resumen` `f041a8e8` (`bge_m3_colbert`/`bge_m3_dense`: `28d09f40`) · `resumen_stripped` `c136a743` · `resumen_decoded` `7d9679fd`. Sources: `OE_resumen_stripped.json` `4703d33f`, `OE_resumen_decoded.json` `ca7fc230`, decoder `7ee4557f` (`MANIFEST.md`) |
| **Runs** | `runs/OE/{resumen,resumen_stripped,resumen_decoded}/`, ten arms each · split `dev` · `check_run_inputs.py`: 197 of 202 resolve; the 5 that do not are S3's declared five |
| **Results** | [`results/S91/`](../results/S91) — 5 tables from `src/utils/build_results_s91.py`, regenerating byte-identically, under `tests/test_generated_prose.py` |

## What ran

Every stamp `{run_id, config SHA, code commit, query-set SHA-256}` is printed in the Sources
section of [`renderings.md`](../results/S91/renderings.md) (30 rows); none is repeated here.

| Block | What | Where |
|---|---|---|
| Renderings | Decoder fitted on dev by *(position, code)*, shared-words rule, A1 floor; two renderings of all 70,242 records | `build_resumen_renderings.py`, [`decoder.md`](../results/S91/decoder.md) |
| Tables | `_norm`/`_feats` of both renderings, along the coded `resumen`'s own path, proven by re-deriving the coded tables exactly first (A2a) | `build_s91_query_tables.py` |
| Runs | 10 arms × `resumen_stripped`, `resumen_decoded` = 20 runs, BM25 at 0.60/0.35 (D-036), existing indexes | `logs/S91/run_s91.sh` (git-ignored) |
| Coded | S3's ten E0(b) runs, reused by digest | retrieval-path diff in `renderings.md` Sources |
| Analysis | T1 decoder, T2 renderings and contrasts, T3 coverage, T4 subchapter, T5 rare codes | [`results/S91/`](../results/S91) |

**Reuse was verified, not assumed.** For each coded run, `git diff <run commit> HEAD` over its
retriever and what it imports, `retrieve.ipynb`, `metrics.ipynb`, `run_context`, `provenance`,
`corpus_prep` and `splits` shows one change: the `QUERY_SETS` entries registering the two
renderings, which cannot alter how `resumen` resolves.

**Pairing across table types.** `bge_m3_colbert` and `bge_m3_dense` read `OE_short_norm` for
coded `resumen` and a `_feats` table for each rendering, as every non-declared query set resolves.
`tests/test_resumen_renderings.py` proves a `_norm` table is its `_feats` table minus columns.

**An incident with no effect.** `build_results_s91.py` sat untracked in `src/utils/` for 17 s while
runs were in flight, and runs stamp `code_dirty` from `git status -- src configs`. The one run that
overlapped the window, `resumen_stripped/bge_m3_sparse__OE`, was stamped after the file was moved:
`code_dirty: false`. Nothing under `src/` or `configs/` was touched again until the batch ended.

## Findings

All figures are on **P**, the 27,574 dev queries whose `resumen` carries a suffix and whose gold
`texto` is unique (26 concepts), unless stated otherwise ([`renderings.md`](../results/S91/renderings.md)).

**1. The codes actively mislead the lexical arms, at concept level.** Removing the suffix lifts
`bm25_unigram` from 0.2808 to 0.7572 at parent level. The clustered interval of that difference is
[+0.2920, +0.5504]; 13,136 queries go up and none go down. [`rare_codes.md`](../results/S91/rare_codes.md)
shows the pattern: in 91.1 % of its coded parent misses (18,065 of 19,832), the rank-1 document
holds a suffix code token that the gold lacks. Such tokens are near-absent from the corpus: `e` is
in 72 of 70,242 documents, `nni` and `ne` in none. `tfidf_phrases_replace` shows it in 1.2 % of its
parent misses. The coded loss is an OEB phenomenon: `bm25_unigram` parent is 0.2170 on OEB and
0.9587 on the rest ([`subchapter.md`](../results/S91/subchapter.md), descriptive).

**2. The suffix carries nearly everything that tells a leaf from its siblings.** On P the
text-only ceiling is **0.8342** coded, **0.0147** stripped and **0.8341** decoded. Most P leaves
differ from their siblings only in the three work-regime axes. Stripping removes the misleading
tokens and the information together, so it is a diagnostic, not a remedy.

**3. Decoding restores item-level accuracy for every arm except TF-IDF, whose change is not
detected.** Decoded − coded at item level, clustered intervals, Holm p ≤ 0.0048 each:

| arm | coded | decoded | Δ | CI (concept) |
|---|---:|---:|---:|---|
| `bm25_unigram_params` (oracle) | 0.5492 | 0.9221 | +0.3729 | [+0.2255, +0.4140] |
| `bm25_unigram` | 0.0051 | 0.5815 | +0.5764 | [+0.4787, +0.6752] |
| `bge_m3_colbert` | 0.0284 | 0.4826 | +0.4542 | [+0.4242, +0.5573] |
| `dense_e5` | 0.0122 | 0.1722 | +0.1600 | [+0.1449, +0.2112] |
| `bge_m3_sparse` | 0.0157 | 0.1470 | +0.1314 | [+0.0972, +0.2313] |
| `bge_m3_dense` | 0.0170 | 0.1312 | +0.1141 | [+0.0854, +0.2173] |

`tfidf_phrases_replace` moves +0.0434 [−0.0231, +0.0964]. The GTE arms and `dense_es_hiiamsid`
gain less than +0.04, with intervals that exclude 0.

**4. Decoding costs one arm heavily at concept level.** `dense_es_hiiamsid` parent falls from
0.6744 to 0.2881 (Δ −0.3863 [−0.5151, −0.1029], Holm p 0.0180; 11,377 queries down, 724 up).
The two BM25 arms gain at parent level, by the mechanism of finding 1: `bm25_unigram` +0.4717
[+0.2746, +0.5476], `bm25_unigram_params` +0.3714 [+0.2169, +0.4127]. For TF-IDF and the other
neural arms the decoded − coded parent interval includes 0, except `bge_m3_sparse` (−0.0011, upper
bound −0.0000). Why a short-text sentence model is pulled off the concept by a longer suffix was not
tested.

**5. Parametric collapse on coded `resumen` is partly the codes.** ColBERT reads 0.9918 parent
and 0.0284 item coded, against 0.9962 and 0.4826 decoded. Collapse is still present decoded,
but the item level moves by an order of magnitude. S3's coded figures described the catalogue's
own query surface correctly; they did not describe how far the parameters themselves, rather than
their codes, are what the arms fail on.

**6. The decoder is catalogue-only and 80.9 % exact.** On the 28,150 dev leaves with a suffix,
22,774 decode exactly on every axis they have ([`decoder.md`](../results/S91/decoder.md)).
5,419 axis values get a strict subset of their words (above all TRABAJO `-`), 2 get foreign
words, and on 59 occurrences a value is written for an axis the leaf lacks. It reads neither
the concept nor the gold.

**7. Coverage, descriptively.** Lexical coverage on P is 80.92 % coded, 90.78 % stripped and
94.41 % decoded ([`coverage.md`](../results/S91/coverage.md)). P is not the population S3
measured OE on: S3's 79.38 % is every dev query (n = 35,422), and on that population decoding
moves coverage from 79.38 % to 89.83 % [83.43, 92.99]. S3's OEB reference, 94.10 %, is measured
on all 47,514 OEB pairs, test-side concepts included
([`results/S3/overlap/overlap.md`](../results/S3/overlap/overlap.md)). The decoded all-dev
interval excludes it. The two populations still differ (OE dev against all of OEB), so the
figures are stated side by side, not contrasted; the P figure is not set against OEB's at all.

**Reference, not a contrast (D-039).** Decoded `bm25_unigram_params` reaches 0.9361 on every
scored dev query (n = 34,646), beside the previous study's 0.974 on OEB test. Chapter, corpus size
and split still differ, and the decoded text reproduces the kind of edit, not its text.

## Hypotheses

| Hypothesis | Movement | Evidence |
|---|---|---|
| **P1** decoded > coded, item, lexical arms | **supported** for `bm25_unigram_params` and `bm25_unigram`; **not supported** for `tfidf_phrases_replace` | Finding 3; interval [−0.0231, +0.0964], Holm p 0.1700 |
| **P2** stripped > coded, parent, BM25 arms | **supported** for `bm25_unigram`; **not supported** for `bm25_unigram_params` under the A2(b) rule | Finding 1. For the params arm, Δ +0.3692 [+0.2177, +0.4091] but Holm p 0.0700: 6 of 26 concepts gain, holding 85.9 % of P, and the four large OEB families (`OEB020/030/230/290`) carry it; resamples without them return a zero delta ([`subchapter.md`](../results/S91/subchapter.md)) |
| D-039's rare-code observation | **supported** for `bm25_unigram` | P2 and T5; not withdrawn |
| **H5** (overlap mediation) | **not addressed** | The renderings are an intervention on overlap (finding 7); mediation remains S6's |
| H1–H4, H6 | **not addressed** | Out of the probe's scope |

## What is now known to be wrong

1. **"The gap between OE and OEB coverage is the chapter"** (D-037, as amended), in so far as
   D-037 reads the gap as a property of OE. On S3's own OE population (all dev), decoding
   alone moves coverage from 79.38 % to 89.83 % [83.43, 92.99]. Much of the gap moves with the
   rendering. It does not close: the interval excludes OEB's 94.10 %, so decoded OE remains less
   verbatim than OEB on these figures. The populations still differ (OE dev, all OEB pairs),
   and this is a description, not a mediation claim.
2. **"Lexical arms fail on OE `resumen` because they cannot tell siblings apart."** At concept level,
   `bm25_unigram` fails because rare code tokens pull it to other concepts: 0.2808 coded against
   0.7572 stripped. That is a different failure from parametric collapse.
3. **"S3's replication headroom reads each arm against its ceiling."** It reads `resumen` against the
   `texto` identity ceiling. `resumen` has its own text-only ceiling, 0.8342 on P coded, because
   siblings share their summary text. S3 did not measure it.
4. **"Decoding splits groups of identical text"** — the frozen design's own sentence (A3). The decoded
   text is a function of the coded text, so it can only merge them.
5. **"More of the discriminating information in the query cannot hurt."** It cost `dense_es_hiiamsid`
   0.3863 at parent level.
6. **"`data.ipynb` can register a new query set."** Run with `SAVE=True` it rewrites every table of the
   collection, and it fails on a set without `modification_count`. The stamped tables survive only
   because A2(a) routed around it.

## Exit criteria

| # | Met | Evidence |
|---|---|---|
| 1 | yes | Both renderings, the decoder and the four derived tables are in `MANIFEST.md`; `test_each_s91_input_matches_its_manifest_digest` |
| 2 | yes | `tests/test_resumen_renderings.py` 30 passed; full suite **1057 passed, 1 xfailed** at `58a2c6c` |
| 3 | yes | 20 runs, all `cf92bc8`, `code_dirty: false`, `dev`, 35,422 queries; 197/202 resolve; reuse diff recorded in `renderings.md` |
| 4 | yes | T1–T5 regenerate byte-identically at `3dc992f`; every Acc@1 row carries n; each condition's ceiling printed (A2c) |
| 5 | yes | P1 and P2 each read, per arm, in `renderings.md` §"The registered predictions" |
| 6 | yes | Finding 6; `decoder.md` |
| 7 | **pending** | D-039 and D-037 amendments proposed below, for César |

## Deviations from design

| # | Deviation | Why |
|---|---|---|
| A1 | 1 % floor in the shared-words rule; an absent axis contributes no value | `OEB160a/b` mis-order their suffix and would empty CONDICIONES `-` for 9,380 dev leaves (`OE_resumen_decoder.json`, `7ee4557f`); ruled by César before any run |
| A2 | Tables derived by a new generator; verdict rule made explicit; T5 at both levels | The notebooks would rewrite the tables that stamp the coded runs; the rule was committed before results |
| A3 | A false design sentence corrected | Decoding cannot split identical-text groups |

## What the next sprint inherits

- **A decoder that is viable and could be deployed**, and two query sets that stay in the tree
  (`resumen_decoded`, `resumen_stripped`).
- **The rare-code failure** of the BM25 arms on the catalogue's own summaries, measured.
- **Evidence that document-side expansion is worth a probe.** The design deferred it "only if the
  rendering matters"; it matters (finding 3). Indexing each leaf's codes would remove the query-side
  step. Not scheduled: César's call.
- **Debt:**
  - `data.ipynb`/`features.ipynb` cannot register a query set safely (known wrong 6).
  - The `resumen` ceiling is not in S3's replication table (known wrong 3).
  - The TF-IDF tokenizer hypothesis (it drops single-letter tokens) is untested.
  - `STATE.md` states a 2 KB budget and stands at 9 KB.
- **S4 is unaffected**: its query sets carry no codes.

## Decisions raised

| ID | Proposed | What |
|---|---|---|
| D-039 | amendment | The open question answered: a catalogue-only decoder is viable (80.9 % exact) and changes item-level accuracy by up to +0.5764. Whether any future `resumen` result is reported coded, decoded or both is César's ruling |
| D-037 | amendment | Part of the coverage gap S3 measured is rendering: on all dev, decoding moves OE coverage from 79.38 % to 89.83 % [83.43, 92.99], still short of OEB's 94.10 % (interval excludes it; populations differ). OE stays less verbatim than OEB, by less than S3's coded figure implies (finding 7) |
| D-040 | new, for César | Whether `resumen`-identical siblings get a scoring rule like D-033's, or remain a printed ceiling |
| D-041 | new, for César | Whether to open a document-side expansion probe |

## Audit response

`/audit S91` ran in a fresh session on 2026-09-29 and returned **FAIL**
([`SPRINT_S91_AUDIT.md`](SPRINT_S91_AUDIT.md), verbatim). It confirmed that every retrieval figure,
interval and flip count it sampled reproduces from `runs/`, that the five tables regenerate
identically, and that the design was not edited after freeze. The sprint was reopened. Disposition
of the eight findings:

| Finding | Disposition |
|---|---|
| F1 — coverage compared across different samples; D-037 proposal built on it | **Fixed.** "Decoded OE reaches OEB's coverage" is withdrawn. Finding 7, known-wrong 1 and the D-037 row now read the all-dev population S3 measured OE on: 79.38 % coded → 89.83 % decoded [83.43, 92.99], whose interval excludes OEB's 94.10 %. The P figure is no longer set against OEB's. Part of the gap moves with the rendering; OE stays less verbatim than OEB. The remaining population difference (OE dev, all OEB pairs) is stated |
| F2 — T4, T3, T1 sources unstamped | **Fixed.** `sources()` now stamps every file a table reads as well as every run, and a table that reads no run says so instead of printing an empty run table. T4 lists its thirty runs. T3 lists the run its dev population comes from and the digests of the three rendering files and of the gold `texto` table. T1 lists `OE_resumen.json` and `SPLITS.md`. T2 and T5 also gained the files they read. The population's run is now one named constant rather than an index into the arm list. Regenerated: only the Sources sections changed; no figure moved. Every data digest matches `MANIFEST.md` |
| F3 — finding 1's heading overgeneralises | open |
| F4 — T2's printed rule differs from the code's | open |
| F5 — T5 counts common code tokens | open |
| F6 — ungenerated P2 claim | open |
| F7 — report typed by hand | open |
| F8 — T4 and secondary table without ceilings | open |
