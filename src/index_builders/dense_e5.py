# /work/src/index_builders/dense_e5.py
"""
Dense index builder (multilingual/Spanish) — E5/GTE compatible.

API mirrors other index builders in this repo:
  - select_field(feats_meta) -> str
  - build(cfg: Dict[str,Any], long_df: pd.DataFrame, text_field: str) -> (artifacts: Dict[str,Any], encoder, E_docs)

Artifacts follow the existing layout:
  /index/<method>/
    meta.json
    fields.json
    mapping.jsonl            # one JSON per line: {"doc_id": int, "external_id": str}
    data/
      embeddings.npy         # (N, D) float32
      # (optional) doc_norms.npy if not using pre-normalized embeddings

Notes
-----
- We L2-normalize embeddings by default to enable cosine = dot product.
- For ~40k docs, a single (N,D) matrix product for search is fine; FAISS is optional.
"""

from typing import Dict, Any, Tuple, List
import time, hashlib
import numpy as np
import pandas as pd

def _sha256_sample(texts, cap=1000) -> str:
    h = hashlib.sha256()
    n = len(texts)
    if n == 0:
        return "sha256:0"
    step = max(1, n // min(n, cap))
    for i in range(0, n, step):
        t = texts[i]
        if t is None:
            t = ""
        h.update(str(t).encode("utf-8"))
    return "sha256:" + h.hexdigest()

def select_field(feats_meta: Dict[str, Any]) -> str:
    return "text"

def _pick_external_ids(df: pd.DataFrame) -> List[str]:
    # Canonical external id in this project is item_key (per data prep notes).
    if "item_key" in df.columns:
        return df["item_key"].astype(str).tolist()
    # Fallbacks
    for c in ("id", "external_id"):
        if c in df.columns:
            return df[c].astype(str).tolist()
    # Last resort: numeric row ids
    return [str(i) for i in range(len(df))]

def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str):
    """
    Encode long-format docs with a SentenceTransformer-compatible model.
    cfg['method']['params'] should include:
      model_name: str  (e.g., 'intfloat/multilingual-e5-base')
      batch_size: int
      max_length: int
      normalize: bool  (L2 normalize embeddings for cosine/dot)
    """
    params = (cfg.get("method") or {}).get("params") or {}
    model_name = params.get("model_name", "intfloat/multilingual-e5-base")
    batch_size = int(params.get("batch_size", 256))
    max_length = int(params.get("max_length", 256))
    normalize  = bool(params.get("normalize", True))
    add_doc_pref = bool(params.get("add_doc_prefix", True))
    doc_prefix   = str(params.get("doc_prefix", "passage: "))

    # Lazy import so indexing environments without these deps can still import the module.
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise RuntimeError("sentence-transformers is required for dense indexing") from e

    model = SentenceTransformer(model_name)
    model.max_seq_length = max_length

    corpus = long_df[text_field].fillna("").astype(str).tolist()
    ext_ids = _pick_external_ids(long_df)

    t0 = time.time()
    embs_list = []
    for i in range(0, len(corpus), batch_size):
        batch = corpus[i:i+batch_size]
        E = model.encode(
            batch,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,  # we'll normalize ourselves if requested
            show_progress_bar=False,
        )
        embs_list.append(E.astype("float32"))
    E_docs = np.vstack(embs_list).astype("float32")
    if normalize and E_docs.size:
        # L2-normalize rows
        n = np.linalg.norm(E_docs, axis=1, keepdims=True)
        n[n==0] = 1.0
        E_docs = E_docs / n

    secs = time.time() - t0
    print(f"[dense_e5] docs={E_docs.shape[0]} | dim={E_docs.shape[1] if E_docs.size else 0} | time={secs:.2f}s")

    # Prepare artifacts
    artifacts: Dict[str, Any] = {
        # data/
        "embeddings.npy": E_docs,
        # root files
        "meta.json": {
            "method": "dense_e5",
            "model_name": model_name,
            "dim": int(E_docs.shape[1]) if E_docs.size else 0,
            "normalize": normalize,
            "__corpus_hash__": _sha256_sample(corpus),
            "__num_docs__": int(E_docs.shape[0]),
        },
        "fields.json": {"text_field": text_field},
        # mapping.jsonl lines are provided so the orchestrator can write the jsonl
        "mapping.jsonl": [
            {"doc_id": int(i), "external_id": ext_ids[i]}
            for i in range(len(ext_ids))
        ],
    }

    return artifacts, model, E_docs
