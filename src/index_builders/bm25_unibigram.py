# /src/index_builders/bm25_unibigram.py
from __future__ import annotations
from typing import Dict, Any, Tuple
import time, hashlib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer

def _sha256_sample(texts, cap=1000) -> str:
    h = hashlib.sha256()
    n = len(texts)
    if n == 0:
        return "sha256:0"
    step = max(1, n // min(n, cap))
    for i in range(0, n, step):
        h.update(texts[i].encode("utf-8"))
    return "sha256:" + h.hexdigest()

def select_field(feats_meta: Dict[str, Any]) -> str:
    """
    Choose the feature column to index; follow the same rule as TF–IDF:
    features_meta['text_fields']['word_unigram'] (usually 'text_word').
    Keeps the retriever/runner consistent with the rest of the pipeline.
    """
    return feats_meta["text_fields"]["word_unigram"]

def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str):
    """
    Fit BM25 (1+2-gram) on long documents and return artifacts for persistence.
    Return:
      artifacts: { filename -> npz/npy/json/sparse } matching your universal schema
      transformer: None (BM25 doesn't need a sklearn transformer downstream)
      X_docs: CSR matrix of BM25-weighted document vectors (N x V, float32)
    """
    p = cfg.get("method", {}).get("params", {})
    analyzer     = p.get("analyzer", "word")
    ngram_range  = tuple(p.get("ngram_range", [1, 2]))  # default to 1+2-gram
    lowercase    = p.get("lowercase", True)
    token_pattern= p.get("token_pattern", r"(?u)\b\w+\b")
    strip_accents= p.get("strip_accents", "unicode")

    # BM25 knobs
    k1 = float(p.get("k1", 1.2))
    b  = float(p.get("b", 0.75))

    corpus = long_df[text_field].fillna("").astype(str).tolist()
    t0 = time.time()

    # 1) Vocabulary + raw counts (int32)
    cv = CountVectorizer(
        analyzer=analyzer,
        ngram_range=ngram_range,
        lowercase=lowercase,
        token_pattern=token_pattern,
        strip_accents=strip_accents,
        dtype=np.int32,
    )
    X_counts = cv.fit_transform(corpus)  # CSR [N x V], int32
    N, V = X_counts.shape

    # 2) Document lengths and average length
    dl = np.asarray(X_counts.sum(axis=1)).ravel().astype(np.float32)
    avgdl = float(dl.mean()) if N > 0 else 0.0

    # 3) Document frequency per term
    df = np.asarray((X_counts > 0).sum(axis=0)).ravel().astype(np.int32)

    # 4) Robertson–Sparck Jones IDF (with +1 to keep positive)
    #    idf_j = log( (N - df_j + 0.5) / (df_j + 0.5) + 1 )
    idf = np.log((N - df + 0.5) / (df + 0.5) + 1.0).astype(np.float32)

    # 5) Build BM25-weighted doc matrix
    Xc = X_counts.tocoo()
    tf = Xc.data.astype(np.float32)

    # denominator per row i: k1 * (1 - b + b * dl_i / avgdl)
    denom_rows = (k1 * (1.0 - b) + k1 * b * (dl / max(avgdl, 1e-8))).astype(np.float32)
    denom = tf + denom_rows[Xc.row]

    w = idf[Xc.col] * (tf * (k1 + 1.0) / np.maximum(denom, 1e-8))
    X_bm25 = sparse.csr_matrix((w, (Xc.row, Xc.col)), shape=(N, V), dtype=np.float32)

    secs = time.time() - t0
    print(f"[bm25_unibigram] docs={N} | vocab={V} | time={secs:.2f}s | k1={k1} b={b} | avgdl={avgdl:.2f}")

    # 6) Artifacts for your universal index schema
    artifacts = {
        "bm25_docs.npz": X_bm25,                                   # doc-term BM25 weights
        "vocab.json":     {t:int(j) for t,j in cv.vocabulary_.items()},
        "counts.npz":     X_counts.tocsr().astype(np.int32),       # raw counts (diagnostics/PRF)
        "df.npy":         df,                                      # document frequency
        "idf.npy":        idf,                                     # BM25 idf
        "dl.npy":         dl.astype(np.float32),                   # doc lengths
        "__avgdl__":      avgdl,
        "__num_docs__":   int(N),
        "__vocab_size__": int(V),
        "__corpus_hash__": _sha256_sample(corpus),
        "__has_counts__": True
    }
    return artifacts, None, X_bm25
