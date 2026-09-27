# /src/retrievers/tfidf_unigram.py
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
from typing import List, Tuple, Dict, Any
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

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

#: Query rows scored per block (S3). Mirrors retrievers.dense_e5: the score block is B x N, and
#: the 35,422 OE dev identity queries in one block are ~9.3 GiB in float32.
DEFAULT_BATCH_SIZE = 2048
_USE_DEFAULT = object()


class TfidfSearcher:
    """
    Exact cosine search: sims = (q_vec @ X_docs.T)
    NOTE: This retriever is method-agnostic for TF–IDF; the difference between
    'tfidf_unigram' and 'tfidf_unigram_phrases' lives in WHICH TEXT FIELD you use
    for queries, chosen upstream based on features_meta (same as index build):contentReference[oaicite:4]{index=4}.
    """
    def __init__(self, index_dir: Path):
        data_dir = index_dir / "data"
        # standard files from the builder output:contentReference[oaicite:5]{index=5}
        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")
        self.X_docs  = sparse.load_npz(data_dir / "tfidf_docs.npz").tocsr()
        vocab        = _read_json(data_dir / "vocab.json")
        idf          = np.load(data_dir / "idf.npy").astype(np.float32)
        params = self.meta.get("params", {})

        # rebuild a query vectorizer with fixed vocab + same IDF
        self.vec_q = TfidfVectorizer(
            analyzer=params.get("analyzer", "word"),
            ngram_range=tuple(params.get("ngram_range", [1,1])),
            lowercase=params.get("lowercase", True),
            token_pattern=params.get("token_pattern", r"(?u)\b\w+\b"),
            strip_accents=params.get("strip_accents", "unicode"),
            vocabulary=vocab
        )
        self.vec_q.fit(["dummy"])
        self.vec_q._tfidf.idf_ = idf

        if self.X_docs.shape[1] != len(vocab) or len(idf) != len(vocab):
            raise ValueError("Dim mismatch: docs vs vocab vs idf")

    @staticmethod
    def _ensure_text(x):
        return x if isinstance(x, str) else ("" if x is None else str(x))

    def encode(self, texts: List[str]) -> sparse.csr_matrix:
        texts = [self._ensure_text(t) for t in texts]
        return self.vec_q.transform(texts)  # L2 normed by sklearn

    def search(self, query_text: str, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        q = self.encode([query_text])            # 1 x |V|
        sims = (q @ self.X_docs.T).toarray().ravel()
        sims = np.nan_to_num(sims, copy=False)   # guard
        k = min(k, sims.shape[0])
        if k == 0:
            return np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.float32)
        part = np.argpartition(-sims, kth=k-1)[:k]
        order = np.argsort(-sims[part])
        top_idx = part[order]
        return top_idx, sims[top_idx]

    def search_batch(self, queries: List[str], k: int = 100, batch_size=_USE_DEFAULT):
        """Score `queries` in blocks of `batch_size` rows (S3); `None` means one block.

        A query's scores depend on no other query, so blocking changes memory, not results —
        see tests/test_retriever_batching.py. Added in S3 work item 6, after all ten runs of
        this arm at 35,422 dev queries died with DeadKernelError: the unblocked path builds a
        B x N dense score matrix, 9.3 GiB in float32 against ~20 GiB of container RAM. S1 had
        blocked bm25_unigram, dense_e5 and bge_m3_colbert — the three methods S2 needed — and
        this arm was simply never run at that scale before (defect H6).
        """
        if batch_size is _USE_DEFAULT:
            batch_size = DEFAULT_BATCH_SIZE
        if batch_size is not None and batch_size < 1:
            raise ValueError(f"batch_size must be a positive integer or None, got {batch_size!r}")
        queries = list(queries)
        if batch_size is None or batch_size >= len(queries):
            return self._search_block(queries, k)
        blocks = [
            self._search_block(queries[s : s + batch_size], k)
            for s in range(0, len(queries), batch_size)
        ]
        return (
            np.concatenate([i for i, _ in blocks], axis=0),
            np.concatenate([sc for _, sc in blocks], axis=0),
        )

    def _search_block(self, queries: List[str], k: int = 100):
        Q = self.encode(queries)                 # B x |V|
        sims = (Q @ self.X_docs.T).toarray()     # B x N
        sims = np.nan_to_num(sims, copy=False)
        B, N = sims.shape
        k = min(k, N)
        part = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]     # B x k (unsorted per row)
        row_idx = np.arange(B)[:, None]
        row_vals = sims[row_idx, part]
        sorter = np.argsort(-row_vals, axis=1)
        top_idx = part[row_idx, sorter]                           # B x k (sorted)
        top_s   = sims[row_idx, top_idx]
        return top_idx, top_s

def load(index_dir: str | Path) -> TfidfSearcher:
    return TfidfSearcher(Path(index_dir))
