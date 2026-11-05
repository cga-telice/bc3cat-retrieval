# BC3CAT Retrieval: A Benchmark for Retrieval on Parametric Construction Catalogs

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20277823.svg)](https://doi.org/10.5281/zenodo.20277823)

Code, configurations and evaluation artefacts of the study:

> **A Systematic Comparative Study of Retrieval Methods for Parametric Construction Catalogs: From Lexical to Neural Approaches**
> González-Alvarez, C., Fernández-Robles, L., Alegre, E., & Castejón-Limas, M.
> Manuscript under review.

The DOI above is the concept DOI and resolves to the latest release; each release
has its own version DOI on Zenodo. The catalog itself, with its parsed parameters
and the BC3/FIEBDC conversion tools, is the
[BC3CAT dataset](https://github.com/cga-telice/bc3cat-dataset)
([10.5281/zenodo.20277800](https://doi.org/10.5281/zenodo.20277800)).

## Overview

The benchmark is built from the 47,513 items of subcategory OEB of ADIF's railway
price catalog; 47,508 of them are variants generated from 25 parametric templates.

- **Queries**: the catalog's short-format descriptions (*resumen*)
- **Documents**: the long-format descriptions (*texto*)
- **Query sets**: 16,590 test and 5,000 validation queries, disjoint, fixed and
  identified by SHA-256 (`benchmark/query_samples/`)

Every system is scored twice: at **item level** (the exact parametric variant) and
at **parent level** (its template family).

### Key findings

- **The item/parent dissociation**: every zero-shot multilingual dense retriever
  identifies the correct parametric family almost perfectly (96.0-99.8% Acc@1)
  and the correct variant almost never (7.0-13.6%). The gap reaches 92.9 points.
- **Best method**: BM25 with parameter tokens (k1=0.60, b=0.35) reaches 97.4%
  item-level Acc@1 and shows almost no gap (98.5% at parent level).
- **Evidence beats filtering**: given the same extracted parameter tuple, using it
  as query terms reaches 97.4% and using it as an exact filter reaches 90.3%.
- **The collapse is not only neural.** TF-IDF with parameter phrases gives up 28.1
  points between the two levels, BM25-unigram 10.4. For 6.94% of queries,
  BM25-unigram assigns the target and a sibling variant identical vectors.
- **By design**, queries are the catalog's own short descriptions, so the target
  contains 94.1% of the query's tokens and 99.96% of its numeric values verbatim.
  Removing the vocabulary gap is what isolates the parametric one.

## Results summary

| Method | Item Acc@1 | Parent Acc@1 | Gap (pp) |
|--------|------------|--------------|----------|
| BM25 + parameter tokens (k1=0.60, b=0.35) | **0.974** | 0.985 | 1.2 |
| Rule-based structured pipeline | 0.903 | 0.985 | 8.1 |
| Hybrid: BM25 + ColBERT + TF-IDF char | 0.893 | 0.974 | 8.1 |
| BM25 unigram (k1=0.80, b=0.35) | 0.869 | 0.973 | 10.4 |
| TF-IDF + parameter phrases | 0.708 | 0.990 | 28.1 |
| BGE-M3 ColBERT | 0.448 | 0.997 | 54.9 |
| multilingual-e5-base | 0.136 | 0.982 | 84.5 |
| BGE-M3 sparse | 0.125 | 0.994 | 87.0 |
| GTE-multilingual-base | 0.070 | **0.998** | **92.9** |

All figures are Acc@1 over the same 16,590 test queries
(`benchmark/query_samples/OEB_query_sample_test_16590.json`).

### What the top row actually is

`bm25_unigram_params` does not index plain text. It indexes `text_word_params`: the
normalized text plus one token per parameter axis (`param_terreno_blando`,
`param_no_tubos_6`, ...), built from the `parameters` field that the BC3 format
declares for every catalog item. The same representation is used on both sides,
because in a catalog-to-catalog match both sides are catalog records.

So the top row is not "BM25 beats neural retrieval". It is a term-weighting model
that has been given the catalog's parametric structure, against sentence encoders
that were given only prose. Measured on the same index, varying only the query
(`scripts/probe_param_tokens.py`, `scripts/probe_computed_params.py`):

| Query | Item Acc@1 |
|---|---|
| Text only | 0.871 |
| Parameter tuple only | 0.219 |
| Text + tuple from the catalog record | 0.974 |
| Text + tuple **extracted from the query text** | 0.974 |

The last row is the control: where the tuple comes from does not matter, so the
figure is not an artifact of reading it rather than deriving it. If you reuse this
benchmark, the choice to make explicitly is whether your queries are catalog records
(and therefore carry the tuple) or free text (and therefore do not).

## Methods implemented

- **Lexical**: BM25 (unigram, unigram + parameter tokens, unibigram) with
  (k1, b) sweeps; TF-IDF (unigram, character 3-5-grams, parameter phrases)
- **Pseudo-relevance feedback**: RM3 and Rocchio over two BM25 bases
- **Neural, zero-shot**: E5, GTE, a Spanish sentence-similarity model, and BGE-M3
  in its dense, sparse and late-interaction (ColBERT) forms
- **Hybrid**: weighted fusion of min-max normalized scores over a weight sweep
- **Reranking**: a multilingual cross-encoder, replacing or blended with the
  first-stage score
- **Query expansion**: HyDE
- **Structured attribute matching**: parameter extraction from the query, then
  exact filtering against the template schema

142 configurations in total; Table 3 of the manuscript lists them per family.

## Repository structure

```
bc3cat-retrieval/
├── benchmark/query_samples/  # versioned test, validation and HyDE query sets
├── configs/                  # one YAML per run
├── src/                      # implementation
│   ├── index_builders/       #   index construction per method
│   ├── retrievers/           #   retrieval per method
│   ├── rerankers/            #   cross-encoder reranking
│   ├── pipeline/             #   structured attribute extraction and matching
│   ├── utils/                #   shared utilities
│   └── *.ipynb               #   data preparation, indexing, retrieval, metrics
├── scripts/                  # command-line runners, evaluation and paper builders
├── eval/                     # aggregate analysis outputs used by the paper
├── notebooks/                # orchestration and exploratory notebooks
├── paper/                    # manuscript source, tables and figures
├── apis/bge-m3/              # BGE-M3 embedding server
├── Dockerfile.bge-m3
└── docker-compose.yml
```

`data/`, `index/` and `runs/` are created locally and are not versioned. The
per-query outputs and the aggregate metrics of every run are released with the
BC3CAT data deposit.

## Quick start

### Environment

```bash
git clone https://github.com/cga-telice/bc3cat-retrieval.git
cd bc3cat-retrieval
docker-compose up -d        # Jupyter (container jupyter-pytorch) and the BGE-M3 server
```

Jupyter is then at http://localhost:8888 (token set by `JUPYTER_TOKEN` in
`docker-compose.yml`). Without Docker: Python 3.11 and `pip install -r requirements.txt`.

### Data

Download the BC3CAT dataset and place its processed files in `data/processed/`.
The code reads `OEB_short_feats.parquet`, `OEB_long_feats.parquet`,
`OEB_features_meta.json`, `OEB_texto.json`, `OEB_resumen.json` and
`OEB_concept_schema.json`.

### Running a method

Every run is defined by its YAML in `configs/`. Inside the container:

```bash
docker exec jupyter-pytorch python /work/scripts/run_method.py bm25_unigram_params__k1-0.60__b-0.35
docker exec jupyter-pytorch python /work/scripts/run_method.py dense_e5 --split val
```

`run_method.py` builds the index (or reuses it), retrieves the top 100 candidates
for each query and writes `runs/<run>/`. Fusion, reranking and HyDE have their own
runners (`run_hybrids.py`, `run_cross_encoder.py`, `run_hyde.py`).

### Evaluation

```bash
python scripts/eval_dual.py runs/<run>          # item- and parent-level metrics
python scripts/leaderboard.py --runs bm25_unigram_params__k1-0.60__b-0.35 bge_m3_colbert
python scripts/bootstrap_sigtests.py --preset lexical
```

Metrics are Acc@1, Recall@5, Recall@10, MRR and nDCG@10, computed by a
purpose-written evaluator: the parent-level criterion needs a non-standard ideal
ranking, so no general-purpose IR library is used. Significance is a paired
bootstrap on Acc@1 with Holm-Bonferroni correction.

### Rebuilding the paper

The manuscript's tables and figures are generated from the run artifacts by the
`scripts/build_*_table.py` and `scripts/plot_*.py` scripts. The manuscript is
compiled in a TeX Live container and the journal submission package is assembled
from it:

```bash
python scripts/build_paper.py          # paper/paper_rev_AEI.pdf
python scripts/build_submission.py     # submission/aei/
```

## Provenance

Some code comments describe defects found and corrected while revising an earlier
version of the manuscript. On 2026-09-14 the local `runs/` directory was
lost; the eleven systems whose per-query outputs are released were re-run on
2026-10-12, and the manuscript reports those re-runs.

## Citation

Please cite the article and the software release you used. GitHub's
"Cite this repository" button reads `CITATION.cff`:

```bibtex
@misc{bc3cat_software,
  author       = {Gonz{\'a}lez-Alvarez, Ces{\'a}reo and Fern{\'a}ndez-Robles, Laura
                  and Alegre, Enrique and Castej{\'o}n-Limas, Manuel},
  title        = {{BC3CAT-RETRIEVAL}: retrieval and evaluation code for the
                  {BC3CAT} parametric construction catalog benchmark},
  howpublished = {Zenodo},
  year         = {2026},
  doi          = {10.5281/zenodo.20277823},
}
```

## License

- **Code** (source, notebooks, scripts): MIT, see `LICENSE`.
- **Data and evaluation artifacts** (`benchmark/`, `eval/`): CC-BY 4.0, see
  `LICENSE-DATA`. They derive from ADIF's publicly available price catalog
  (*Base de Precios ADIF*, https://bpa.adif.es).
- **Third-party models** keep their own licenses: E5 and GTE (MIT), BGE-M3 (MIT),
  Sentence-Transformers (Apache 2.0).

## Acknowledgments

This work was conducted at the Group for Vision and Intelligent Systems (GVIS),
I4 Institute, Universidad de León, Spain. The authors gratefully acknowledge
**Telice S.A.** for providing time, computing resources, data access and software
licenses, and **ADIF** for making its price catalog publicly available. This
research did not receive any specific grant from funding agencies in the public,
commercial, or not-for-profit sectors.

### AI disclosure

The authors used generative AI tools to assist with code development, data
analysis, and manuscript preparation. All AI-assisted outputs were reviewed and
verified by the authors, who take full responsibility for the content of this work.

## Contact

Cesáreo González-Alvarez, Universidad de León — cgonza06@estudiantes.unileon.es
