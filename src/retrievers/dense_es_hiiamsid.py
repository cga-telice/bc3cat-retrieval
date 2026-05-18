# /work/src/retrievers/dense_es_hiiamsid.py

"""
Dense retriever for Spanish model 'hiiamsid/sentence_similarity_spanish_es'.

Contract for your dynamic loader:
- expose load(index_dir) -> DenseESSearcher
- class DenseESSearcher must have search(text, k) and search_batch(texts, k)

Reads standard artifacts:
  index_dir/meta.json
  index_dir/fields.json
  index_dir/mapping.jsonl
  index_dir/data/embeddings.npy
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import json, numpy as np

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

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
    if len(doc_ids) and not (doc_ids.min() == 0 and doc_ids.max() == len(doc_ids)-1):
        raise ValueError("mapping.jsonl doc_id must be contiguous 0..N-1")
    return doc_ids, ext_ids

def _l2norm(X: np.ndarray, axis=1, eps: float = 1e-8) -> np.ndarray:
    n = np.linalg.norm(X, axis=axis, keepdims=True)
    n = np.maximum(n, eps)
    return X / n

class DenseESSearcher:
    def __init__(self, index_dir: Path):
        index_dir = Path(index_dir)
        data_dir  = index_dir / "data"
        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")
        self.X_docs = np.load(data_dir / "embeddings.npy").astype(np.float32, copy=False)
        # Ensure docs are normalized (builder already did; this is a safeguard)
        self.X_docs = _l2norm(self.X_docs, axis=1) if self.X_docs.size else self.X_docs

        params = self.meta.get("params", {})
        self.model_name = params.get("model_name", "hiiamsid/sentence_similarity_spanish_es")
        self.add_query_prefix = bool(params.get("add_query_prefix", False))  # should be False for this model
        self.max_length = int(params.get("max_length", 512))

        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers required to encode queries")
        self.model = SentenceTransformer(self.model_name)
        self.model.max_seq_length = self.max_length

    @staticmethod
    def _ensure_text(x):
        return x if isinstance(x, str) else ("" if x is None else str(x))

    def encode(self, texts: List[str]) -> np.ndarray:
        texts = [self._ensure_text(t) for t in texts]
        if self.add_query_prefix:
            # kept for parity with E5 family; not used for hiiamsid
            texts = [f"query: {t}" for t in texts]
        Q = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=False, show_progress_bar=False)
        Q = Q.astype(np.float32, copy=False)
        Q = _l2norm(Q, axis=1)
        return Q

    def search(self, query_text: str, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        Q = self.encode([query_text])  # (1, D)
        sims = (Q @ self.X_docs.T).ravel()
        sims = np.nan_to_num(sims, copy=False)
        k = min(k, sims.shape[0])
        if k == 0:
            return np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.float32)
        part = np.argpartition(-sims, kth=k-1)[:k]
        order = np.argsort(-sims[part])
        top_idx = part[order]
        return top_idx, sims[top_idx]

    def search_batch(self, queries: List[str], k: int = 100):
        Q = self.encode(queries)                 # (B, D)
        sims = (Q @ self.X_docs.T)               # (B, N)
        sims = np.nan_to_num(sims, copy=False)
        B, N = sims.shape
        k = min(k, N)
        part = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]
        rows = np.arange(B)[:, None]
        order = np.argsort(-sims[rows, part], axis=1)
        top_idx = part[rows, order]
        top_sco = sims[rows, top_idx]
        return top_idx, top_sco

def load(index_dir: str | Path) -> DenseESSearcher:
    return DenseESSearcher(Path(index_dir))
