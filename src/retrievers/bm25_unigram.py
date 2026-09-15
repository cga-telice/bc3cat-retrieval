# /src/retrievers/bm25_unigram.py
from __future__ import annotations
from pathlib import Path
import json, numpy as np
from typing import List, Tuple
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

#: Rows of the dense score block held in memory at once. 2048 x 70,242 float32 is about
#: 575 MB, which fits everywhere this runs; the whole OE query set at once would not.
DEFAULT_BATCH_SIZE = 2048

#: Distinguishes "caller said nothing" from "caller asked for one block" (batch_size=None).
_USE_DEFAULT = object()


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

class BM25Searcher:
    """
    Scores = (Q_idf @ X_bm25.T), where X_bm25 holds BM25 doc weights.
    Q_idf is a sparse row with idf_j for terms present in the query.
    """
    def __init__(self, index_dir: Path):
        data_dir = index_dir / "data"
        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")
        self.default_batch_size = DEFAULT_BATCH_SIZE

        self.X_docs  = sparse.load_npz(data_dir / "bm25_docs.npz").tocsr().astype(np.float32)
        self.vocab   = _read_json(data_dir / "vocab.json")
        self.idf     = np.load(data_dir / "idf.npy").astype(np.float32)

        # Build a query vectorizer with frozen vocab (binary counts)
        params = self.meta.get("params", {})
        self.vec_q = CountVectorizer(
            analyzer=params.get("analyzer", "word"),
            ngram_range=tuple(params.get("ngram_range", [1,1])),
            lowercase=params.get("lowercase", True),
            token_pattern=params.get("token_pattern", r"(?u)\b\w+\b"),
            strip_accents=params.get("strip_accents", "unicode"),
            vocabulary=self.vocab,
            dtype=np.int32
        )

        if self.X_docs.shape[1] != len(self.vocab) or len(self.idf) != len(self.vocab):
            raise ValueError("Dim mismatch: docs vs vocab vs idf")

    @staticmethod
    def _ensure_text(x):
        return x if isinstance(x, str) else ("" if x is None else str(x))

    def _encode_queries_idf(self, texts: List[str]) -> sparse.csr_matrix:
        # binary term presence → multiply by idf per column
        Qc = self.vec_q.transform([self._ensure_text(t) for t in texts]).tocsr().astype(np.float32)
        # set values to idf (presence → idf; 0 stays 0)
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

    def _search_block(self, queries: List[str], k: int):
        """Score one block of queries against every document, densely."""
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

    def search_batch(self, queries: List[str], k: int = 100, batch_size=_USE_DEFAULT):
        """Score `queries` in blocks, returning the same (indices, scores) as one block would.

        The dense score block is len(queries) x num_docs, so scoring the whole query set at
        once costs ~9 GB on OEB and ~20 GB on OE, and dies. A query's scores depend on no
        other query, so blocking is an arithmetic no-op — see tests/test_bm25_batching.py.

        `batch_size=None` restores the single-block behaviour; it is what the equality tests
        compare against, not something a run should use.
        """
        if batch_size is _USE_DEFAULT:
            batch_size = self.default_batch_size
        if batch_size is not None and batch_size < 1:
            raise ValueError(f"batch_size must be a positive integer or None, got {batch_size!r}")

        n_queries = len(queries)
        if n_queries == 0:
            return (
                np.empty((0, 0), dtype=np.int64),
                np.empty((0, 0), dtype=np.float32),
            )

        if batch_size is None or batch_size >= n_queries:
            return self._search_block(list(queries), k)

        blocks = [
            self._search_block(list(queries[start : start + batch_size]), k)
            for start in range(0, n_queries, batch_size)
        ]
        return (
            np.concatenate([idx for idx, _ in blocks], axis=0),
            np.concatenate([scores for _, scores in blocks], axis=0),
        )

def load(index_dir: str | Path) -> BM25Searcher:
    return BM25Searcher(Path(index_dir))
