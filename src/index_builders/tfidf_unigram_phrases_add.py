# -*- coding: utf-8 -*-
# Selects the *_phrases_add field and builds TF–IDF (unigram) index.
from typing import Dict, Any, Tuple
import time, hashlib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

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
    Choose phrase-augmented column for the ADD policy.
    Required in features_meta.text_fields:
      - word_unigram_phrases_add  (preferred)
      - fallback: word_unigram_phrases
    """
    tf = feats_meta["text_fields"]
    return (
        tf.get("word_unigram_phrases_add")
        or tf.get("word_unigram_phrases")
        or (_raise := (_ for _ in ()).throw(KeyError(
            "features_meta.text_fields must have 'word_unigram_phrases_add' "
            "or 'word_unigram_phrases' for the ADD variant"
        )))
    )

def build(cfg: Dict[str, Any], long_df, text_field: str) -> Tuple[Dict[str, Any], Any, Any]:
    """
    Fit TF–IDF (unigrams) over the selected phrase+unigram text_field.
    Returns artifacts dict with keys (no 'data/' prefix), a fitted vectorizer, and X_docs CSR.
    """
    p = cfg["method"]["params"]
    vec = TfidfVectorizer(
        analyzer=p.get("analyzer", "word"),
        ngram_range=tuple(p.get("ngram_range", [1, 1])),
        lowercase=p.get("lowercase", True),
        token_pattern=p.get("token_pattern", r"(?u)\b\w+\b"),
        strip_accents=p.get("strip_accents", "unicode"),
        norm=p.get("norm", "l2"),
        use_idf=p.get("use_idf", True),
        smooth_idf=p.get("smooth_idf", True),
        sublinear_tf=p.get("sublinear_tf", False),
        dtype=np.float32 if p.get("dtype", "float32") == "float32" else np.float64,
    )

    corpus = long_df[text_field].fillna("").astype(str).tolist()
    t0 = time.time()
    X = vec.fit_transform(corpus)   # CSR (N x |V|)
    secs = time.time() - t0
    print(f"[tfidf_unigram_phrases_add] docs={X.shape[0]} | vocab={X.shape[1]} | time={secs:.2f}s")

    # raw counts for df/cf, using exact same tokenizer/vocab as TF–IDF
    cv = CountVectorizer(
        vocabulary=vec.vocabulary_,
        analyzer=vec.analyzer,
        ngram_range=vec.ngram_range,
        lowercase=vec.lowercase,
        token_pattern=getattr(vec, "token_pattern", None),
        strip_accents=vec.strip_accents,
        stop_words=vec.stop_words,
        dtype=np.int32,
    )
    X_counts = cv.transform(corpus)
    df = (X_counts > 0).sum(axis=0).A1.astype(np.int32)   # doc frequency
    cf = X_counts.sum(axis=0).A1.astype(np.int64)         # collection frequency

    artifacts = {
        # writer will place these under <index_dir>/data/...
        "tfidf_docs.npz": X,
        "vocab.json":     {t: int(c) for t, c in vec.vocabulary_.items()},
        "idf.npy":        vec.idf_.astype(np.float32),
        "counts.npz":     X_counts,
        "df.npy":         df,
        "cf.npy":         cf,
        "__num_docs__":   int(X.shape[0]),
        "__vocab_size__": int(X.shape[1]),
        "__corpus_hash__": _sha256_sample(corpus),
        "__has_counts__": True,
        # top-level files written by writer at <index_dir>/
        "fields.json":    {"text_field": text_field},
        "meta.json": {
            "method": "tfidf",
            "variant": "tfidf_unigram_phrases_add",
            "text_field": text_field,
            "num_docs": int(X.shape[0]),
            "vocab_size": int(X.shape[1]),
            "params": p,
        },
    }
    return artifacts, vec, X
