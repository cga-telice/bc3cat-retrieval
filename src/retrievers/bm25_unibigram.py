# /src/retrievers/bm25_unibigram.py
from __future__ import annotations
from pathlib import Path
import json, numpy as np
from typing import List, Tuple
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

def _read_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _load_mapping(mapping_path: Path):
    doc_ids, ext_ids = [], []
    with open(mapping_path, "r", encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            obj = json.loads(ln)
            doc_ids.append(int(obj["doc_id"]))
            ext_ids.append(str(obj["external_id"]))
    doc_ids = np.asarray(doc_ids, dtype=np.int64)
    ext_ids = np.asarray(ext_ids, dtype=object)
    if not (doc_ids.min() == 0 and doc_ids.max() == len(doc_ids)-1):
        raise ValueError("mapping.jsonl doc_id must be contiguous 0..N-1")
    return doc_ids, ext_ids

class BM25UniBigramSearcher:
    """
    Scores = (Q_idf @ X_bm25.T), where X_bm25 holds BM25 doc weights.
    Q_idf is a sparse binary query vector with per-term idf weights.
    API mirrors your TF–IDF retriever: load(index_dir) → search/search_batch(..).
    """
    def __init__(self, index_dir: Path):
        data_dir = index_dir / "data"
        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")

        # Load BM25 artifacts produced by the builder
        self.X_docs  = sparse.load_npz(data_dir / "bm25_docs.npz").tocsr().astype(np.float32)
        self.vocab   = _read_json(data_dir / "vocab.json")
        self.idf     = np.load(data_dir / "idf.npy").astype(np.float32)

        params = self.meta.get("params", {})
        # Query vectorizer with FROZEN vocabulary and same tokenization (1+2-gram)
        self.vec_q = CountVectorizer(
            analyzer=params.get("analyzer", "word"),
            ngram_range=tuple(params.get("ngram_range", [1,2])),
            lowercase=params.get("lowercase", True),
            token_pattern=params.get("token_pattern", r"(?u)\b\w+\b"),
            strip_accents=params.get("strip_accents", "unicode"),
            vocabulary=self.vocab,
            dtype=np.int32
        )

        # sanity
        if self.X_docs.shape[1] != len(self.vocab) or len(self.idf) != len(self.vocab):
            raise ValueError("Dim mismatch: docs vs vocab vs idf")

    @staticmethod
    def _ensure_text(x):
        return x if isinstance(x, str) else ("" if x is None else str(x))

    def _encode_queries_idf(self, texts: List[str]) -> sparse.csr_matrix:
        # binary presence → set values to idf_j
        Qc = self.vec_q.transform([self._ensure_text(t) for t in texts]).tocsr().astype(np.float32)
        if Qc.nnz:
            Qc.data = self.idf[Qc.indices]
        return Qc

    def search(self, query_text: str, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        Q = self._encode_queries_idf([query_text])
        sims = (Q @ self.X_docs.T).toarray().ravel()
        sims = np.nan_to_num(sims, copy=False)
        k = min(k, sims.shape[0])
        if k == 0:
            return np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.float32)
        part = np.argpartition(-sims, kth=k-1)[:k]
        order = np.argsort(-sims[part])
        top_idx = part[order]
        return top_idx, sims[top_idx]

    def search_batch(self, queries: List[str], k: int = 100):
        Q = self._encode_queries_idf(queries)
        sims = (Q @ self.X_docs.T).toarray()
        sims = np.nan_to_num(sims, copy=False)
        B, N = sims.shape
        k = min(k, N)
        part = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]
        row_idx = np.arange(B)[:, None]
        row_vals = sims[row_idx, part]
        sorter = np.argsort(-row_vals, axis=1)
        top_idx = part[row_idx, sorter]
        top_s   = sims[row_idx, top_idx]
        return top_idx, top_s

def load(index_dir: str | Path) -> BM25UniBigramSearcher:
    """
    Entry point required by your universal retrieve runner.
    """
    return BM25UniBigramSearcher(Path(index_dir))
