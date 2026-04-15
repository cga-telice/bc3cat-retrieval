# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

 **Branch note:** If working on the structured-retrieval branch, read `docs/CLAUDE_STRUCTURED_RETRIEVAL.md` for pipeline-specific context.

## Project Summary

BC3CAT Retrieval is a research benchmark comparing retrieval methods (BM25, TF-IDF, E5, GTE, BGE-M3) on the ADIF Spanish railway construction parametric catalog (~40,000 items, 16,590 queries). Queries are short-format descriptions ("resumen"), documents are long-format technical specifications ("texto"). The primary metric is Acc@1 under a dual-target evaluation (item-level and parent-category level).

## Environment Setup

Docker is the primary development environment:
```bash
docker-compose up -d          # Jupyter (port 8888, token: j) + BGE-M3 API (port 8800)
```

Inside containers, the repo is mounted at `/work`. All config paths use `/work/...`.

Manual setup alternative:
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install pandas pyarrow ranx faiss-cpu scikit-learn tqdm pyyaml matplotlib seaborn
pip install transformers sentence-transformers torch  # for neural methods
```

## Architecture

### Builder/Retriever Contract Pattern

The core design pattern: each retrieval method has a paired **index builder** and **retriever** module with matching filenames.

**Index builders** (`src/index_builders/`) implement:
- `select_field(feats_meta) -> str` — which DataFrame column to index
- `build(cfg, long_df, text_field) -> (artifacts, transformer, X_docs)` — construct index artifacts

**Retrievers** (`src/retrievers/`) implement:
- `load(index_dir) -> Searcher` — factory to load from disk
- `Searcher.search(query, k) -> (top_indices, scores)` — single-query search
- `Searcher.search_batch(queries, k) -> (indices[B,K], scores[B,K])` — batch search

The builder filename **must** match `method.name` in the YAML config (e.g., `bm25_unigram_params.py` ↔ `method.name: bm25_unigram_params`).

### Index Artifact Layout

```
index/<method>/
├── meta.json           # Metadata, parameters, corpus hash
├── fields.json         # Text field used
├── mapping.jsonl       # {doc_id, external_id} per line
└── data/               # Method-specific: .npz (sparse), .npy (dense), .json (vocab)
```

### Configuration System

YAML configs in `configs/` drive all experiments. Key fields:
- `collection`, `paths.data_dir`, `paths.index_root`
- `inputs.short_feats`, `inputs.long_feats` — parquet paths
- `method.family`, `method.name`, `method.impl`, `method.params`
- `model.api_base` — for remote embedding services (BGE-M3)

### Notebook Workflow

Execution order: `data.ipynb` → `index_builder.ipynb` → `retrieve.ipynb` → `eval.ipynb` → `bootstrap_sigtests.ipynb`

Orchestrator notebooks (`bm25_orchestrator.ipynb`, `prf_bm25_orchestrator.ipynb`) automate parameter sweeps.

### BGE-M3 Embedding API

FastAPI service (`apis/bge-m3/serve.py`) serving BAAI/bge-m3 model. Endpoints: `POST /encode`, `POST /encode_batch`. Modes: `"dense"`, `"sparse"`, `"colbert"`. Port 8800 externally, accessed from Jupyter container via `host.docker.internal:8800`.

### Evaluation

Metrics via `ranx` v0.3.7: Acc@1, Recall@5, Recall@10, MRR, nDCG@10. Dual-target: item-level (exact match) and parent-level (hierarchical category match). Core logic in `src/utils/evaluation.py`.

## Key Conventions

- Text processing normalizes Spanish accents and lowercases (`src/utils/text_processing.py`)
- Dense embeddings are always L2-normalized so cosine similarity = dot product
- Lexical retrieval uses sparse matrix multiplication + `np.argpartition` for top-K
- Data format: parquet for features, JSONL for mappings, NPZ for sparse matrices
- All paths in configs assume Docker mount at `/work`
