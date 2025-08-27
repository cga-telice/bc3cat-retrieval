# /src/index_builders/bm25_unigram_params.py
from typing import Dict, Any
import time, hashlib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

def _sha256_sample(texts, cap=1000) -> str:
    h = hashlib.sha256()
    n = len(texts)
    if n == 0: return "sha256:0"
    step = max(1, n // min(n, cap))
    for i in range(0, n, step):
        h.update(texts[i].encode("utf-8"))
    return "sha256:" + h.hexdigest()

def select_field(feats_meta: Dict[str, Any]) -> str:
    # <-- the only real change: pick your params-only text
    return feats_meta["text_fields"]["word_unigram_params"]

def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str):
    p = cfg["method"]["params"]
    cv = CountVectorizer(
        analyzer=p.get("analyzer", "word"),
        ngram_range=tuple(p.get("ngram_range", [1,1])),
        lowercase=p.get("lowercase", True),
        token_pattern=p.get("token_pattern", r"(?u)\b\w+\b"),
        strip_accents=p.get("strip_accents", "unicode"),
        dtype=np.int32
    )

    corpus = long_df[text_field].fillna("").astype(str).tolist()
    t0 = time.time()
    X_counts = cv.fit_transform(corpus)    # CSR (N x V), int32
    N, V = X_counts.shape

    dl = np.asarray(X_counts.sum(axis=1)).ravel().astype(np.float32)
    avgdl = float(dl.mean()) if N > 0 else 0.0

    df = np.asarray((X_counts > 0).sum(axis=0)).ravel().astype(np.int32)
    idf = np.log((N - df + 0.5) / (df + 0.5) + 1.0).astype(np.float32)

    k1 = float(p.get("k1", 1.2))
    b  = float(p.get("b", 0.75))

    X_counts = X_counts.tocoo()
    tf = X_counts.data.astype(np.float32)
    denom_rows = (k1 * (1.0 - b) + k1 * b * (dl / max(avgdl, 1e-8))).astype(np.float32)
    denom = tf + denom_rows[X_counts.row]
    w = idf[X_counts.col] * (tf * (k1 + 1.0) / np.maximum(denom, 1e-8))
    X_bm25 = sparse.csr_matrix((w, (X_counts.row, X_counts.col)), shape=(N, V), dtype=np.float32)

    secs = time.time() - t0
    print(f"[bm25_unigram_params] docs={N} | vocab={V} | time={secs:.2f}s")

    artifacts = {
        "bm25_docs.npz": X_bm25,
        "vocab.json":     {t:int(j) for t,j in cv.vocabulary_.items()},
        "counts.npz":     X_counts.tocsr().astype(np.int32),
        "df.npy":         df,
        "idf.npy":        idf,
        "dl.npy":         dl.astype(np.float32),
        "__avgdl__":      avgdl,
        "__num_docs__":   int(N),
        "__vocab_size__": int(V),
        "__corpus_hash__": _sha256_sample(corpus),
        "__has_counts__": True
    }
    return artifacts, None, X_bm25
