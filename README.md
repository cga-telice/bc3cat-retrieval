# BC3CAT Retrieval: A Benchmark for Retrieval on Parametric Construction Catalogs

DOI: 10.5281/zenodo.20277824

This repository contains the retrieval pipeline for creating a evaluation benchmark from ADIF's parametric construction price catalog. The methods are part of the research presented in:

> **A Systematic Comparative Study of Retrieval Methods for Parametric Construction Catalogs: From Lexical to Neural Approaches**  
> González-Alvarez, C., Fernández-Robles, L., Alegre, E., & Castejón-Limas, M.  
> *Automation in Construction* (under review)

## Overview

This repository contains the implementation and evaluation framework for construction catalog matching, where:

- **Queries**: Short-format descriptions (*resumen*) — condensed summaries of construction work items
- **Documents**: Long-format descriptions (*texto*) — detailed technical specifications

The study evaluates retrieval methods on the ADIF Spanish railway construction catalog (~40,000 items, 16,590 queries), using a dual-target evaluation protocol that assesses both item-level and parent-category accuracy.

### Key Findings

- **Best Method**: BM25 with tuned parameters (k1=0.60, b=0.35) achieves **97.4% Item Acc@1** and **98.5% Parent Acc@1**
- Lexical methods with parameter values in queries outperform neural embeddings at fine-grained item retrieval
- Dense neural embeddings show improved consistency at the broader parent-category level
- Well-tuned BM25 provides a robust, interpretable baseline for construction catalog matching

## Repository Structure

```
bc3cat-retrieval/
├── configs/           # YAML configuration files for all method variants
├── data/              # Processed datasets (parquet/json) and HuggingFace cache
├── index/             # Built indexes for all retrieval methods
├── runs/              # Evaluation results (metrics, rankings, logs)
├── eval/              # Analysis outputs (bootstrap tests, error analysis)
├── src/               # Python implementation
│   ├── index_builders/   # Index construction modules
│   ├── retrievers/       # Retrieval implementations
│   ├── rerankers/        # Reranking modules
│   └── utils/            # Shared utilities
├── notebooks/         # Analysis and orchestration notebooks
├── apis/              # API services (e.g., BGE-M3 server)
└── logs/              # Execution logs
```

## Methods Implemented

### Lexical Methods
- **BM25** (unigram, unigram+params, unibigram) with parameter sweeps (k1, b)
- **TF-IDF** variants (unigram, char n-grams 3-5, phrase detection)

### Neural Methods
- **Dense Embeddings**: E5, GTE, BGE-M3, Spanish sentence-transformers
- **Sparse Embeddings**: BGE-M3 sparse
- **Late Interaction**: BGE-M3 ColBERT

### Hybrid & Advanced
- **RRF Fusion**: Combining lexical and neural rankings
- **PRF** (Pseudo-Relevance Feedback): RM3 and Rocchio query expansion
- **Reranking**: Cross-encoder and tiebreaking strategies

## Quick Start

### Prerequisites

- Docker with NVIDIA GPU support (recommended)
- Or: Python 3.11+ with dependencies

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/cga-telice/bc3cat-dataset.git
cd bc3cat-dataset

# Start Jupyter environment
docker-compose up -d

# Access Jupyter at http://localhost:8888 (token: j)
```

### Manual Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run notebooks in order
cd src
jupyter notebook
```

### Additional Dependencies

For full functionality, you may need:

```bash
pip install pandas pyarrow ranx faiss-cpu scikit-learn tqdm pyyaml matplotlib seaborn
```

For neural methods:
```bash
pip install transformers sentence-transformers torch
```

## Usage

### 1. Data Preparation

The dataset should be placed in `data/` with the following structure:
- `OEB_short_feats.parquet`: Short feature representations
- `OEB_long_feats.parquet`: Long feature representations  
- `OEB_features_meta.json`: Feature metadata

### 2. Building Indexes

Use the index builder notebooks in `src/`:

```python
# In src/index_builder.ipynb
# Load config and build index for a specific method
config = load_config("configs/bm25_unigram_params__k1-0.60__b-0.35.yaml")
# Build and save index artifacts
```

Each index builder module follows a standard contract:
- `select_field()`: Determines which text field to index
- `build()`: Constructs method-specific artifacts (matrices, vocabularies, etc.)

### 3. Running Retrieval

Use the retrieval notebooks in `src/`:

```python
# In src/retrieve.ipynb
# Load index and run retrieval on query set
results = retrieve(config, queries, top_k=100)
```

### 4. Evaluation

Evaluate results using the evaluation notebook:

```python
# In src/eval.ipynb
# Compute metrics for both item and parent targets
metrics = evaluate(results, qrels, targets=['item', 'parent'])
```

Metrics computed via [ranx](https://github.com/AmenRa/ranx) v0.3.7:
- **Acc@1** (Accuracy at rank 1)
- **Recall@5, Recall@10**
- **MRR** (Mean Reciprocal Rank)
- **nDCG@10**

### 5. Parameter Sweeps

Configuration files in `configs/` support systematic parameter exploration:

```yaml
method:
  family: bm25
  name: bm25_unigram_params__k1-0.60__b-0.35
  params:
    k1: 0.60
    b: 0.35
```

## Evaluation Protocol

The evaluation uses a **dual-target** approach:
1. **Item-level**: Exact match to the specific catalog item
2. **Parent-level**: Match to the parent category (allowing siblings as correct)

This reflects the hierarchical structure of parametric construction catalogs where items share parent categories through parameterized attributes.

### Statistical Testing

Bootstrap significance tests (10,000 iterations) with Holm-Bonferroni and Benjamini-Hochberg corrections are provided in `eval/bootstrap_*/`.

## Results Summary

| Method | Item Acc@1 | Parent Acc@1 | MRR |
|--------|------------|--------------|-----|
| BM25 (k1=0.60, b=0.35) | **0.974** | **0.985** | 0.979 |
| BM25 (default) | 0.569 | 0.612 | 0.584 |
| TF-IDF unigram | 0.411 | 0.468 | 0.432 |
| BGE-M3 ColBERT | 0.294 | 0.412 | 0.341 |
| Dense E5 | 0.088 | 0.324 | 0.142 |

*Full results available in `runs/` and `eval/` directories.*

## Configuration

All experiments are controlled via YAML configuration files:

```yaml
collection: "OEB"
paths:
  data_dir: "/work/data/processed"
  index_root: "/work/index"
inputs:
  short_feats: "/work/data/processed/OEB_short_feats.parquet"
  long_feats: "/work/data/processed/OEB_long_feats.parquet"
method:
  family: "bm25"
  name: "bm25_unigram_params__k1-0.60__b-0.35"
  impl: "bm25_unigram_params"
  params:
    analyzer: "word"
    ngram_range: [1, 1]
    k1: 0.60
    b: 0.35
```

## Docker Support

For BGE-M3 embedding server:

```bash
docker-compose up bge-m3-server
```

## Citation

If you use this code or dataset, please cite:

```bibtex
@article{gonzalez2025systematic,
  title={A Systematic Comparative Study of Retrieval Methods for Parametric Construction Catalogs: From Lexical to Neural Approaches},
  author={González-Alvarez, Cesáreo and Fernández-Robles, Laura and Alegre, Enrique and Castejón-Limas, Manuel},
  journal={Automation in Construction},
  year={2025},
  note={Under review}
}
```

## License

This repository uses dual licensing:

### Code (MIT License)

The source code (notebooks, scripts, utilities) is licensed under the MIT License:
```
MIT License

Copyright (c) 2025 Cesáreo González-Alvarez, Laura Fernández-Robles, 
Enrique Alegre, Manuel Castejón-Limas, Universidad de León

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Dataset (CC-BY 4.0)

The processed dataset files are licensed under [Creative Commons Attribution 4.0 International (CC-BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

You are free to:
- **Share** — copy and redistribute the material in any medium or format
- **Adapt** — remix, transform, and build upon the material for any purpose, including commercial

Under the following terms:
- **Attribution** — You must give appropriate credit, provide a link to the license, and indicate if changes were made. Please cite our paper (see Citation section above).

The source data is derived from ADIF's publicly available price catalog (Base de Precios ADIF). Our processed dataset and annotations are original contributions licensed under CC-BY 4.0.

### Third-Party Models

This repository uses pre-trained models with their own licenses:
- **E5/GTE**: MIT License
- **BGE-M3**: MIT License
- **Sentence-Transformers**: Apache 2.0

Please refer to the respective model repositories for full license terms.

## Acknowledgments

This work was conducted at the Group for Vision and Intelligent Systems (GVIS), I4 Institute, Universidad de León, Spain.

The authors gratefully acknowledge **Telice S.A.** for providing resources and data access that made this research possible, and **ADIF** for making their price catalog (Base de Precios ADIF) publicly available.

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

### AI Disclosure

The authors used generative AI tools to assist with code development, data analysis, and manuscript preparation. All AI-assisted outputs were reviewed and verified by the authors, who take full responsibility for the content of this work.

## Contact

Cesáreo González-Alvarez  
Universidad de León  
Email: cgonza06@estudiantes.unileon.es

