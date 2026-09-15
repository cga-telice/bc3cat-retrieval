# CLAUDE.md

Guidance for Claude Code when working in this repository.

**Branch note.** If you are on `research/synthetic-oe`, read
[`docs/synthetic-oe/CLAUDE.md`](docs/synthetic-oe/CLAUDE.md) and
[`docs/synthetic-oe/STATE.md`](docs/synthetic-oe/STATE.md) **before doing anything else**.
Those two files, plus this one and the active sprint design, are the whole start-of-session
context. Everything else in `docs/` is searched on demand, never read wholesale.

## Project summary

`bc3cat-retrieval` is the **retrieval and evaluation harness** for BC3CAT, a benchmark built
from ADIF's BC3/FIEBDC parametric construction price catalogue. The corpus is produced
upstream by [`bc3cat-dataset`](../bc3cat-dataset); this repo indexes it, runs retrieval
methods against it, and evaluates them.

The task: given a description of a construction work item, retrieve the matching catalogue
item. What makes it hard is that a *concept* (parent) expands into hundreds or thousands of
*leaves* (items) whose descriptions are lexically near-identical and differ only in
parameter values. Retrieval is therefore fine-grained discrimination inside a family of
hard negatives, not topical matching.

## Core concepts and vocabulary

| Term | Meaning |
|---|---|
| **concept / parent** | A BC3 template. Key ends in `$` (e.g. `OEB280$`). |
| **leaf / item** | One resolved parameter assignment of a concept (e.g. `OEB020aaeaa`). |
| **`item_key`** | `parent_key[:-1] + parameter_label_sequence`. |
| **`resumen`** | Short-form description (~14 tokens). Query surface in the original protocol. |
| **`texto`** | Long-form technical description. Retrieval **target** in every protocol. |
| **item-level** | Scoring requires the exact leaf. |
| **parent-level** | Scoring credits any leaf of the correct concept. |
| **parametric collapse** | Near-perfect parent-level accuracy with far lower item-level accuracy. The central phenomenon this repo studies. |

## Dual-target evaluation protocol

Every run is scored **twice**: item-level and parent-level. Reporting one without the other
is meaningless here — the gap between them *is* the finding. Metrics via `ranx` 0.3.7:
Acc@1, Recall@5, Recall@10, MRR, nDCG@10. Significance by paired bootstrap (10,000
resamples) with Holm–Bonferroni and Benjamini–Hochberg correction.

## Repository layout

```
configs/      YAML, one per method variant — the unit of reproducibility
data/         processed corpora and query sets (git-ignored)
index/        built indexes
runs/         retrieval results and metrics — the source of truth for every number
eval/         analysis outputs (bootstrap tests, error analysis)
src/          notebooks + modules: index_builders/, retrievers/, rerankers/, utils/
apis/         service containers (BGE-M3 embedding server)
docs/         per-branch documentation (see "Documentation model")
tests/        harness tests
```

### Pipeline

```
data.ipynb → features.ipynb → index_builder.ipynb → retrieve.ipynb → metrics.ipynb → eval.ipynb
```

with `hybrid.ipynb`, `prf_bm25_orchestrator.ipynb`, `cross_encoder.ipynb`,
`reranker_tiebreak.ipynb` for the fusion/expansion/reranking families, and
`bootstrap_sigtests.ipynb`, `error_analysis.ipynb`, `rank_distribution.ipynb` for analysis.

Index builders follow a fixed contract: `select_field()` chooses the indexed text field,
`build()` constructs the method-specific artefacts.

## Method families

- **Lexical** — BM25 (unigram, unigram+params, unibigram) with `k1`/`b` sweeps; TF-IDF
  (unigram, char n-grams 3–5, phrase detection).
- **Dense** — E5, GTE, BGE-M3 dense, Spanish sentence-transformers.
- **Sparse-neural** — BGE-M3 sparse.
- **Late interaction** — BGE-M3 ColBERT.
- **Hybrid / advanced** — RRF fusion, PRF (RM3, Rocchio), cross-encoder reranking,
  tiebreaking.
- **Structured** — extraction-then-match pipelines (branch `research/structured-retrieval`).

## Environment

```bash
docker-compose up -d            # Jupyter on :8888 (token: j); repo mounted at /work
docker-compose up bge-m3-server # embedding service
```

Notebook paths assume `/work/...`. GPU (NVIDIA) recommended for the neural families.

## Configuration contract

One YAML per method variant. A run is reproducible from `(config, code commit, query-set
digest)` and nothing else:

```yaml
collection: "OE"
method:
  family: "bm25"
  name: "bm25_unigram_params__k1-0.60__b-0.35"
  impl: "bm25_unigram_params"
  params: {analyzer: word, ngram_range: [1, 1], k1: 0.60, b: 0.35}
```

## Branches

| Branch | Purpose |
|---|---|
| `main` | The systematic comparative study (OEB chapter, `resumen→texto`). |
| `research/structured-retrieval` | Three-phase extraction pipeline. Parallel branch. |
| `research/synthetic-oe` | Robustness study on the OE chapter with BC3CAT-Syn queries. Parallel branch. |

Research branches are parallel and long-lived. Do not propose merging one into `main`
without an explicit decision recorded in that branch's `DECISIONS.md`.

## Documentation model

Four classes, distinguished by rate of change. Misclassifying a document is how
documentation stops being useful — a contract that grows into an archive stops being read.

| Class | Changes | The agent… | Budget |
|---|---|---|---|
| **Contract** | almost never | reads in full, always | ≤ 12 KB each |
| **Plan** | at sprint boundaries | reads the active one | ≤ 8 KB |
| **Record** | append-only | *searches*; never reads wholesale | unbounded |
| **Derived** | every run | *regenerates*; never hand-edits | unbounded |

If a document grows past its budget, do not trim it — **split it**, and demote the growing
part to a record.

Per-branch documentation lives in `docs/{branch-name}/`. See `docs/synthetic-oe/`.

## Known defects — do not propagate

- **The results table in `README.md` is wrong.** Its neural rows disagree with
  `docs/reviews/paper_28.tex` in every figure. The manuscript is authoritative:
  E5-large 0.134 item / 0.982 parent; BGE-M3-dense 0.127 / 0.960; BGE-M3-sparse 0.125 /
  0.994; BGE-M3-ColBERT 0.448 / 0.997; GTE-large 0.013 / 0.837; BM25-params 0.974 item.
  Never cite the README table. Fixing it is a tracked task.
- All 76 `configs/*.yaml` hard-code `collection: "OEB"`, and indexes/runs are written to
  flat `index/{method}` / `runs/{method}` paths regardless of collection or query set.
  Branch work that adds a collection must resolve this first.
- The eval, bootstrap and error-analysis notebooks scan a flat `/work/runs`.
- **`tfidf_char_3_5` and `tfidf_unigram_nostop` declare no `retriever` block.** Their
  behaviour therefore comes from a notebook default rather than from the config, which
  contradicts the reproducibility contract above: a run must be reproducible from
  `(config, code commit, query-set digest)` alone. Declare the block explicitly, even when
  it only restates the default.
- **`tfidf_char_3_5` / `tfidf_unigram_nostop` is the visible tip of a wider problem:**
  parsing all 77 configs shows **72 declare no `retriever` block**, not two. See D-016's
  2026-09-15 amendment.
- **`hiiamsid/sentence_similarity_spanish_es` was evaluated and never reported.** It is
  described in the manuscript as one of the seven neural configurations but appears in no
  results table, while `runs/dense_es_hiiamsid/metrics_dual.json` holds item Acc@1 0.0244 /
  parent 0.3952. This is a reporting defect of the previous submission, tracked in
  `docs/reviews/AUTCON_analisis_revision.md` §3.9. Any reuse of that method set must include
  it.

## Working rules

- Numbers come from `runs/`. Reports are generated, not typed. A number without a
  provenance stamp `{run_id, config SHA, code commit, query-set SHA-256}` does not exist.
- Never hand-edit anything under `runs/`, `index/`, or a `results/` directory.
- Prefer adding a config over editing one: configs are the experiment record.
- Data files are git-ignored; their digests are not. Record digests when a dataset lands.

## See also

- [`README.md`](README.md) — public-facing description (mind the defect above).
- [`docs/reviews/`](docs/reviews) — the AiC submission and its review analysis.
- [`docs/synthetic-oe/`](docs/synthetic-oe) — the robustness study.
