# /src/index_builders/bge_m3_sparse.py
# Build a **sparse** SPLADE-style index using BGE-M3 served by your FastAPI (`serve.py`).
# It mirrors your universal builder contract used by index_build.ipynb:
#   - select_field(feats_meta) -> str
#   - build(cfg, long_df, text_field) -> (artifacts_dict, transformer_or_None, X_docs)
#
# Artifacts written under /index/<method>/data/:
#   - sparse_docs.npz : CSR (N_docs x |V|) float32 weights returned by the encoder
#   - vocab.json      : {token: col}
#   - df.npy          : int32 doc frequency (docs with token > 0)
#   - cf.npy          : float64 collection frequency (sum of weights across docs)
#   - __num_docs__, __vocab_size__, __corpus_hash__
#
# Notes:
# - Tokens come from the encoder outputs (string tokens). We build a global vocab.
# - We **do not** compute BM25 idf; weights are model-provided. Retrieval is a dot product.
# - The encoder endpoint is assumed at ENV BGE_API_URL (default: http://localhost:8000/encode_batch)
#   with JSON body: {"texts":[...], "mode":"sparse"}
#   and returns: [{"lexical_weights": {"token": weight, ...}}, ...]
#
# Dependencies: requests, numpy, scipy

from __future__ import annotations
from typing import Dict, Any, Tuple, List
import os, time, hashlib, math, json, requests
import numpy as np
import pandas as pd
from scipy import sparse

def _sha256_sample(texts, cap=1000) -> str:
    h = hashlib.sha256()
    n = len(texts)
    if n == 0:
        return "sha256:0"
    step = max(1, n // min(n, cap))
    for i in range(0, n, step):
        t = "" if texts[i] is None else str(texts[i])
        h.update(t.encode("utf-8"))
    return "sha256:" + h.hexdigest()

def select_field(feats_meta: Dict[str, Any]) -> str:
    # Match the word-unigram field that all other builders use【34†source】.
    tf = feats_meta.get("text_fields") or {}
    return tf.get("word_unigram") or tf.get("char_ngram") or "text_word"

def _chunks(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def _to_token_weight_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict) and all(isinstance(v,(int,float)) for v in obj.values()):
        return {str(k): float(v) for k,v in obj.items()}
    return {}

def _extract_items(payload):
    """
    Given the top-level JSON, yield per-text sparse objects to pass to _to_token_weight_dict.
    """
    if isinstance(payload, list):
        for it in payload:
            yield it
        return
    if isinstance(payload, dict):
        # special case: FastAPI returns {"lexical_weights": [ {...}, {...} ]}
        if "lexical_weights" in payload and isinstance(payload["lexical_weights"], list):
            for lw in payload["lexical_weights"]:
                yield lw
            return
        for key in ("results", "data", "items", "embeddings", "vectors"):
            if key in payload and isinstance(payload[key], list):
                for it in payload[key]:
                    yield it
                return
        yield payload
        return
    return

def _encode_sparse(texts: List[str], url: str, batch_size: int = 128, timeout: int = 300):
    """
    Yields per-text dict[str->float] lexical weights by calling the FastAPI service.
    Robust to different response schemas.
    """
    sess = requests.Session()
    for batch in _chunks(texts, batch_size):
        payload = {"texts": batch, "mode": "sparse"}
        r = sess.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        items = list(_extract_items(data))
        if len(items) != len(batch):
            # Some servers return a single merged item; still try to parse it.
            if len(items) == 1:
                yield _to_token_weight_dict(items[0])
                # fill the rest with empty dicts so shapes align
                for _ in range(len(batch) - 1):
                    yield {}
                continue
            # If lengths differ strangely, fail loudly with a hint.
            raise ValueError(f"Sparse API returned {len(items)} items for batch size {len(batch)}.")
        for item in items:
            yield _to_token_weight_dict(item)


def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str) -> Tuple[Dict[str, Any], Any, Any]:
    """
    Encodes all long documents into sparse lexical-weight vectors via the BGE-M3 API (sparse mode).
    Builds a consistent vocab and a CSR matrix.
    """
    p = cfg.get("method", {}).get("params", {}) or {}
    api_url = os.environ.get("BGE_API_URL", p.get("api_url", "http://host.docker.internal:8800/encode_batch"))
    batch_size = int(p.get("batch_size", 64))
    timeout = int(p.get("timeout", 300))

    corpus = long_df[text_field].fillna("").astype(str).tolist()
    N = len(corpus)
    t0 = time.time()

    # Pass 1: build vocab and collect COO triplets
    vocab: Dict[str, int] = {}
    rows_i: List[int] = []
    cols_j: List[int] = []
    vals_x: List[float] = []

    df_counts: Dict[int, int] = {}   # per-col doc frequency (count of docs where token appears)
    cf_sums: Dict[int, float] = {}   # per-col collection frequency (sum of weights)

    for i, lw in enumerate(_encode_sparse(corpus, api_url, batch_size=batch_size, timeout=timeout)):
        # Map tokens to columns
        for tok, w in lw.items():
            if not tok:
                continue
            j = vocab.get(tok)
            if j is None:
                j = len(vocab)
                vocab[tok] = j
            if w == 0.0 or math.isnan(w):
                continue
            rows_i.append(i)
            cols_j.append(j)
            vals_x.append(np.float32(w))
        if (i+1) % 1000 == 0:
            pass  # keep output quiet; the orchestrator prints its own logs

    # Build CSR
    if len(vals_x) == 0:
        X = sparse.csr_matrix((N, 0), dtype=np.float32)
    else:
        X = sparse.csr_matrix((np.array(vals_x, dtype=np.float32),
                               (np.array(rows_i, dtype=np.int32), np.array(cols_j, dtype=np.int32))),
                              shape=(N, len(vocab)), dtype=np.float32)

    # Compute df/cf from X (presence & sums)
    if X.shape[1] > 0:
        X_bin = X.sign()
        df = np.asarray(X_bin.sum(axis=0)).ravel().astype(np.int32)
        cf = np.asarray(X.sum(axis=0)).ravel().astype(np.float64)
    else:
        df = np.zeros((0,), dtype=np.int32)
        cf = np.zeros((0,), dtype=np.float64)

    secs = time.time() - t0
    print(f"[bge_m3_sparse] docs={N} | vocab={X.shape[1]} | nnz={X.nnz} | time={secs:.2f}s")

    artifacts = {
        "sparse_docs.npz": X,
        "vocab.json":      {t: int(j) for t, j in vocab.items()},
        "df.npy":          df,
        "cf.npy":          cf,
        "__num_docs__":    int(N),
        "__vocab_size__":  int(X.shape[1]),
        "__corpus_hash__": _sha256_sample(corpus),
        "__has_counts__":  True
    }
    # No transformer object is needed for retrieval (queries are encoded via API)
    return artifacts, None, X