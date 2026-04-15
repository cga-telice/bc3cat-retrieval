# /src/retrievers/bm25_unigram_params.py
from pathlib import Path
from .bm25_unigram import BM25Searcher as _BM25Searcher

def load(index_dir: str | Path):
    return _BM25Searcher(Path(index_dir))
