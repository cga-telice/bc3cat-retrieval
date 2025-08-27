# /work/src/retrievers/dense_e5.py
"""
Dense retriever (E5/GTE compatible).

Loads:
  index_dir/
    meta.json
    fields.json
    mapping.jsonl
    data/dense_docs.npy

Search returns top-k indices and scores (dot product). If 'normalize'=True in
meta.json, embeddings are L2-normalized and dot product = cosine similarity.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import json
import numpy as np

# Optional: sentence-transformers only needed if you encode queries on-the-fly
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None  # we’ll guard its use

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
    if not (doc_ids.min() == 0 and doc_ids.max() == len(doc_ids) - 1):
        raise ValueError("mapping.jsonl doc_id must be contiguous 0..N-1")
    return doc_ids, ext_ids

def _l2_normalize(mat: np.ndarray, axis: int = 1, eps: float = 1e-8) -> np.ndarray:
    denom = np.linalg.norm(mat, axis=axis, keepdims=True)
    denom = np.maximum(denom, eps)
    return mat / denom

def _argtopk(scores: np.ndarray, k: int) -> np.ndarray:
    k = min(k, scores.shape[-1])
    if k <= 0:
        return np.empty((0,), dtype=np.int64)
    part = np.argpartition(-scores, kth=k-1)[:k]
    order = np.argsort(-scores[part])
    return part[order]

class DenseE5Searcher:
    """
    Cosine similarity search over precomputed dense embeddings.
    Expects the index builder to have written:
      - data/embeddings.npy (float32, shape [N, D], L2-normalized or not)
      - mapping.jsonl       (doc_id -> external_id)
      - meta.json / fields.json (for traceability)
    """
    def __init__(self, index_dir: Path):
        index_dir = Path(index_dir)
        data_dir  = index_dir / "data"

        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")

        # Load document embeddings and ensure float32 + L2-norm
        X = np.load(data_dir / "embeddings.npy").astype(np.float32)
        self.X_docs = _l2_normalize(X, axis=1)

        # Query encoder settings (optional; only used if you want on-the-fly encoding)
        # Prefer pulling model name from meta["params"]["model_name"]
        p = self.meta.get("params", {})
        self.model_name = p.get("model_name", "intfloat/multilingual-e5-base")
        self.add_prefix = bool(p.get("add_query_prefix", True))
        self.device     = p.get("device", None)  # let sentence-transformers auto-pick if None
        self._model = None  # lazy

    # ---------- Optional query encoder (for ad-hoc probes) ----------
    def _ensure_model(self):
        if self._model is None:
            if SentenceTransformer is None:
                raise RuntimeError(
                    "sentence-transformers not available; cannot encode queries on-the-fly.\n"
                    "Either install it or pass precomputed query embeddings to search()."
                )
            self._model = SentenceTransformer(self.model_name, device=self.device)

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        """Encode and L2-normalize queries with E5-style prompt."""
        self._ensure_model()
        if self.add_prefix:
            texts = [f"query: {t}" for t in texts]   # E5 instruction prefix
        Q = self._model.encode(texts, normalize_embeddings=False, convert_to_numpy=True)
        Q = Q.astype(np.float32, copy=False)
        Q = _l2_normalize(Q, axis=1)
        return Q

    # ---------- Search API ----------
    def search(self, query_text: str, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        q = self.encode_queries([query_text])  # (1, D)
        sims = (q @ self.X_docs.T).ravel()     # cosine (dot of L2-normalized)
        top = _argtopk(sims, k)
        return top, sims[top]

    def search_batch(self, queries: List[str], k: int = 100):
        Q = self.encode_queries(queries)       # (B, D)
        sims = Q @ self.X_docs.T               # (B, N)
        B, N = sims.shape
        k = min(k, N)
        idxs = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]
        rows = np.arange(B)[:, None]
        order = np.argsort(-sims[rows, idxs], axis=1)
        top_idx = idxs[rows, order]
        top_sco = sims[rows, top_idx]
        return top_idx, top_sco

# --------- required by your dynamic loader ----------
def load(index_dir: str | Path) -> DenseE5Searcher:
    """
    Factory required by retrieve.ipynb’s dynamic loader.
    Usage:
        from retrievers.dense_e5 import load
        searcher = load('/work/index/dense_e5')
    """
    return DenseE5Searcher(Path(index_dir))

