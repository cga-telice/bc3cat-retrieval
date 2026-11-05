# src/retrievers/bge_m3_dense.py
from __future__ import annotations
from pathlib import Path
import os, json
import numpy as np
import faiss
import requests

# Use server-side limit or override from env
REMOTE_MAX_BATCH = int(os.getenv("BGE_REMOTE_MAX_BATCH", "256"))

def _encode_dense_remote(texts, api_base: str, max_length: int, timeout_s: int = 600) -> np.ndarray:
    """
    Call /encode_batch in chunks to respect FastAPI's MAX_BATCH.
    Also filters out empty strings to avoid 422.
    """
    url = api_base.rstrip("/") + "/encode_batch"
    out = []
    # pre-filter empty/blank strings (server would 422 on invalid items)
    norm_texts = [t if isinstance(t, str) else str(t) for t in texts]
    norm_texts = [t for t in norm_texts if t.strip()]

    B = max(1, REMOTE_MAX_BATCH)
    for i in range(0, len(norm_texts), B):
        payload = {"texts": norm_texts[i:i+B], "mode": "dense", "max_length": int(max_length)}
        r = requests.post(url, json=payload, timeout=timeout_s)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            # If server still 422s (e.g., too big), fall back to half batch size and retry
            if r.status_code == 422 and B > 1:
                half = max(1, B // 2)
                # recursively process the same window with a smaller batch
                sub = []
                for j in range(i, min(i+B, len(norm_texts)), half):
                    sub_payload = {"texts": norm_texts[j:j+half], "mode": "dense", "max_length": int(max_length)}
                    r2 = requests.post(url, json=sub_payload, timeout=timeout_s)
                    r2.raise_for_status()
                    sub.extend(r2.json()["vecs"])
                out.extend(sub)
                continue
            raise
        out.extend(r.json()["vecs"])

    X = np.asarray(out, dtype=np.float32)
    faiss.normalize_L2(X)
    return X

class _Searcher:
    def __init__(self, index_dir: Path, model_name: str, use_fp16: bool, max_length_query: int, api_base: str | None):
        self.dir = Path(index_dir)
        meta = json.loads((self.dir / "meta.json").read_text(encoding="utf-8"))
        # external ids
        exts = []
        with open(self.dir / "mapping.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                exts.append(rec["external_id"])
        self.external_ids = np.asarray(exts, dtype=object)
        # faiss
        data_dir = self.dir / "data"
        self.index = faiss.read_index(str(data_dir / "faiss.index"))
        # encoding path
        self.api_base = api_base
        self._max_length_query = int(max_length_query)
        if not self.api_base:
            # local fallback only if truly needed
            from FlagEmbedding import BGEM3FlagModel
            self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        else:
            self.model = None

    def _encode(self, texts):
        if self.api_base:
            return _encode_dense_remote(texts, self.api_base, self._max_length_query)
        # local
        out = self.model.encode(
            texts, batch_size=64, max_length=self._max_length_query,
            return_dense=True, return_sparse=False, return_colbert_vecs=False
        )
        Q = out["dense_vecs"].astype(np.float32)
        faiss.normalize_L2(Q)
        return Q

    def search_batch(self, texts, k=10):
        Q = self._encode(texts)
        D, I = self.index.search(Q, int(k))
        return I, D

def load(index_dir: str):
    # read YAML-like params from meta.json for consistency
    meta = json.loads((Path(index_dir) / "meta.json").read_text(encoding="utf-8"))
    model_cfg = meta.get("params", {}) or {}
    model_name = meta.get("software", {}).get("model_name") or "BAAI/bge-m3"
    use_fp16   = bool(model_cfg.get("use_fp16", True))
    max_q      = int(model_cfg.get("max_length_query", 256))

    # Prefer ENV for the API base; fall back to what was used at build time (if recorded)
    api_base = os.getenv("BGE_M3_API") or model_cfg.get("api_base") or None
    return _Searcher(Path(index_dir), model_name, use_fp16, max_q, api_base)

