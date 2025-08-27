# /src/retrievers/tfidf_unigram_phrases.py
# Identical TF–IDF mechanics; kept as a separate module for clarity/symmetry with build side.
# The difference between unigram vs unigram+phrases is WHICH query field you pass in (picked upstream
# from features_meta, mirroring the builder's select_field()):contentReference[oaicite:6]{index=6}.

from __future__ import annotations
from pathlib import Path
import json
import numpy as np
from typing import List, Tuple
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

def _read_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

class TfidfPhrasesSearcher:
    def __init__(self, index_dir: Path):
        index_dir = Path(index_dir)
        self.X_docs = sparse.load_npz(index_dir / "data" / "tfidf_docs.npz").tocsr()
        self.vocab  = _read_json(index_dir / "data" / "vocab.json")
        self.idf    = np.load(index_dir / "data" / "idf.npy").astype(np.float32)
        self.fields = _read_json(index_dir / "fields.json") if (index_dir / "fields.json").exists() else {}
        # safety checks
        assert self.X_docs.shape[1] == len(self.vocab), "vocab size mismatch"
        assert self.idf.shape[0] == len(self.vocab), "idf size mismatch"

    def _encode_one(self, text: str) -> sparse.csr_matrix:
        # Simple TF–IDF encoding using stored vocab+idf (unigram)
        # build bow
        counts = {}
        for tok in text.split():
            col = self.vocab.get(tok)
            if col is not None:
                counts[col] = counts.get(col, 0) + 1.0
        if not counts:
            return sparse.csr_matrix((1, len(self.vocab)), dtype=np.float32)
        cols = np.fromiter(counts.keys(), dtype=np.int32)
        vals = np.fromiter(counts.values(), dtype=np.float32)
        # tf * idf
        vals = vals * self.idf[cols]
        # l2 normalize
        norm = np.linalg.norm(vals)
        if norm > 0:
            vals = vals / norm
        indptr = np.array([0, len(cols)], dtype=np.int32)
        return sparse.csr_matrix((vals, cols, indptr), shape=(1, len(self.vocab)), dtype=np.float32)

    def encode(self, texts: List[str]) -> sparse.csr_matrix:
        rows = [self._encode_one(t or "") for t in texts]
        return sparse.vstack(rows).tocsr()

    def search(self, query: str, k: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        Q = self.encode([query])
        sims = (Q @ self.X_docs.T).toarray()[0]
        sims = np.nan_to_num(sims, copy=False)
        k = min(k, sims.shape[0])
        part = np.argpartition(-sims, kth=k-1)[:k]
        order = part[np.argsort(-sims[part])]
        return order, sims[order]

    def search_batch(self, queries: List[str], k: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        Q = self.encode(queries)
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

def load(index_dir: str | Path) -> TfidfPhrasesSearcher:
    return TfidfPhrasesSearcher(Path(index_dir))
