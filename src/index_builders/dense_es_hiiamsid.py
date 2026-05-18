# /work/src/index_builders/dense_es_hiiamsid.py
# Create dense Spanish (hiiamsid) builder & retriever files consistent with the project's conventions.

"""
Dense index builder for Spanish (hiiamsid/sentence_similarity_spanish_es).

Contract (matches your other builders):
- expose select_field(feats_meta) -> str
- expose build(cfg, long_df, text_field) -> (artifacts, encoder, E_docs)

Artifacts (to be written by the orchestrator under /index/<save_as>/):
  meta.json
  fields.json
  mapping.jsonl            # [{"doc_id": i, "external_id": "<item_key>"}]
  data/embeddings.npy      # float32 (N, D)

Notes:
- L2-normalize embeddings (cosine == dot).
- No E5 prompt prefixes; raw Spanish text.
"""

from typing import Dict, Any, Tuple, List
import hashlib, time
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
    # canonical external id in this project
    if "item_key" in df.columns:
        return df["item_key"].astype(str).tolist()
    for c in ("id", "external_id"):
        if c in df.columns:
            return df[c].astype(str).tolist()
    return [str(i) for i in range(len(df))]

def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str):
    """
    cfg['method']['params']:
      model_name: "hiiamsid/sentence_similarity_spanish_es"
      batch_size: int
      max_length: int
      normalize:  bool
    """
    params = (cfg.get("method") or {}).get("params") or {}
    model_name = params.get("model_name", "hiiamsid/sentence_similarity_spanish_es")
    batch_size = int(params.get("batch_size", 256))
    max_length = int(params.get("max_length", 256))
    normalize  = bool(params.get("normalize", True))

    try:
        from sentence_transformers import SentenceTransformer
    except Exception as e:
        raise RuntimeError("sentence-transformers is required for dense indexing") from e

    model = SentenceTransformer(model_name)
    model.max_seq_length = max_length

    corpus  = long_df[text_field].fillna("").astype(str).tolist()
    ext_ids = _pick_external_ids(long_df)

    embs_list = []
    t0 = time.time()
    for i in range(0, len(corpus), batch_size):
        batch = corpus[i:i+batch_size]
        E = model.encode(
            batch,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=False,  # we control normalization below
            show_progress_bar=False,
        ).astype("float32")
        embs_list.append(E)
    E_docs = np.vstack(embs_list) if embs_list else model.get_sentence_embedding_dimension()
    if normalize and E_docs.size:
        n = np.linalg.norm(E_docs, axis=1, keepdims=True)
        n[n==0] = 1.0
        E_docs = E_docs / n

    secs = time.time() - t0
    print(f"[dense_es_hiiamsid] docs={E_docs.shape[0]} | dim={E_docs.shape[1] if E_docs.size else 0} | time={secs:.2f}s")

    artifacts: Dict[str, Any] = {
        "embeddings.npy": E_docs,
        "meta.json": {
            "method": "dense",
            "variant": "dense_es_hiiamsid",
            "params": {
                "model_name": model_name,
                "batch_size": batch_size,
                "max_length": max_length,
                "normalize": normalize,
                "add_query_prefix": False
            },
            "dim": int(E_docs.shape[1]) if E_docs.size else 0,
            "__num_docs__": int(E_docs.shape[0]),
            "__corpus_hash__": _sha256_sample(corpus),
        },
        "fields.json": {"text_field": text_field},
        "mapping.jsonl": [
            {"doc_id": int(i), "external_id": ext_ids[i]} for i in range(len(ext_ids))
        ],
    }
    return artifacts, model, E_docs

