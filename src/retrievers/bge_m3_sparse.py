# /src/retrievers/bge_m3_sparse.py
# Retrieval over the BGE-M3 **sparse** index.
# - Loads CSR doc matrix 'sparse_docs.npz' and 'vocab.json' from the built index.
# - At query time, calls the encoder API with {"mode":"sparse"} to obtain lexical weights,
#   builds a sparse query vector aligned to the same vocab, and scores with dot product.
#
# Interface matches your universal retriever contract used by retrieve.ipynb:
#   load(index_dir) -> searcher
#   searcher.search_batch(texts, k) -> (top_idx, top_scores)

from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import os, json, math, requests, numpy as np
from scipy import sparse

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

class BGEM3SparseSearcher:
    def __init__(self, index_dir: Path):
        data_dir = index_dir / "data"
        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")

        # Load doc matrix and vocab
        self.X_docs  = sparse.load_npz(data_dir / "sparse_docs.npz").tocsr().astype(np.float32)
        self.vocab   = _read_json(data_dir / "vocab.json")  # token -> col
        self.inv_vocab = {int(j): t for t, j in self.vocab.items()}  # optional

        # API endpoint
        params = self.meta.get("params", {})
        self.api_url = os.environ.get("BGE_API_URL", params.get("api_url", "http://localhost:8800/encode_batch"))
        self.session = requests.Session()

    @staticmethod
    def _ensure_text(x):
        return x if isinstance(x, str) else ("" if x is None else str(x))

    def _encode_queries_sparse(self, texts: List[str]) -> List[dict]:
        """
        Encode queries into sparse token→weight dicts.
        Splits into batches to avoid 422 errors, and handles both dict and list responses.
        """
        batch_size = int(self.meta.get("params", {}).get("batch_size", 32))
        timeout    = int(self.meta.get("params", {}).get("timeout", 300))
        results = []
    
        for start in range(0, len(texts), batch_size):
            batch = [self._ensure_text(t) for t in texts[start:start+batch_size]]
            payload = {"texts": batch, "mode": "sparse"}
            r = self.session.post(self.api_url, json=payload, timeout=timeout)
            if r.status_code == 422:
                raise RuntimeError(f"Sparse API rejected payload (batch={len(batch)}): {r.text}")
            r.raise_for_status()
            data = r.json()
    
            # --- normalize response ---
            if isinstance(data, dict) and "lexical_weights" in data:
                # server wraps everything in one dict
                lw_list = data["lexical_weights"]
                if isinstance(lw_list, list):
                    for lw in lw_list:
                        results.append({str(k): float(v) for k, v in lw.items()})
                elif isinstance(lw_list, dict):
                    results.append({str(k): float(v) for k, v in lw_list.items()})
            elif isinstance(data, list):
                for item in data:
                    lw = item.get("lexical_weights") if isinstance(item, dict) else item
                    if lw is None:
                        lw = {}
                    results.append({str(k): float(v) for k, v in lw.items()})
            else:
                raise ValueError(f"Unexpected response schema: {type(data)} {data}")
    
        return results

    def _align_query_matrix(self, sparse_dicts: List[dict]) -> sparse.csr_matrix:
        rows_i, cols_j, vals_x = [], [], []
        for i, dct in enumerate(sparse_dicts):
            for tok, w in dct.items():
                j = self.vocab.get(tok)
                if j is None or w == 0.0 or math.isnan(w):
                    continue
                rows_i.append(i)
                cols_j.append(int(j))
                vals_x.append(np.float32(w))
        if not vals_x:
            return sparse.csr_matrix((len(sparse_dicts), len(self.vocab)), dtype=np.float32)
        Q = sparse.csr_matrix((np.array(vals_x, dtype=np.float32),
                               (np.array(rows_i, dtype=np.int32), np.array(cols_j, dtype=np.int32))),
                              shape=(len(sparse_dicts), len(self.vocab)),
                              dtype=np.float32)
        return Q

    def search(self, query_text: str, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        top_idx, top_s = self.search_batch([query_text], k=k)
        return top_idx[0], top_s[0]

    def search_batch(self, queries: List[str], k: int = 100):
        # Encode
        lw_list = self._encode_queries_sparse(queries)
        Q = self._align_query_matrix(lw_list)

        # Score = dot product
        sims = (Q @ self.X_docs.T).toarray()  # (B, N)
        sims = np.nan_to_num(sims, copy=False)
        B, N = sims.shape
        k = min(k, N) if N else 0
        if k == 0:
            return (np.zeros((B,0), dtype=np.int64), np.zeros((B,0), dtype=np.float32))

        part = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]
        row_idx = np.arange(B)[:, None]
        row_vals = sims[row_idx, part]
        sorter = np.argsort(-row_vals, axis=1)
        top_idx = part[row_idx, sorter]
        top_s   = sims[row_idx, top_idx]
        return top_idx, top_s

def load(index_dir: str | Path) -> BGEM3SparseSearcher:
    return BGEM3SparseSearcher(Path(index_dir))