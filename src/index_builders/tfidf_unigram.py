# /src/index_builders/tfidf_unigram.py
from typing import Tuple, Dict, Any
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
    Choose the feature column for TF–IDF (unigrams) (plain).
    In features_meta this is 'text_fields.word_unigram' (usually 'text_word').
    """
    return feats_meta["text_fields"]["word_unigram"]

def build(cfg: Dict[str, Any], long_df, text_field: str):
    """
    Fit TF–IDF (unigrams) on long documents.
    Returns:
      artifacts: dict with files to persist (npz/json/npy) + meta counters
      transformer: fitted TfidfVectorizer (for quick probe)
      X_docs: CSR matrix of document vectors
    """
    p = cfg["method"]["params"]
    stop_words = p.get("stop_words", None)
    
    vec = TfidfVectorizer(
        analyzer=p.get("analyzer", "word"),
        ngram_range=tuple(p.get("ngram_range", [1,1])),
        lowercase=p.get("lowercase", True),
        token_pattern=p.get("token_pattern", r"(?u)\b\w+\b"),
        strip_accents=p.get("strip_accents", 'unicode'),
        norm=p.get("norm", "l2"),
        use_idf=p.get("use_idf", True),
        smooth_idf=p.get("smooth_idf", True),
        sublinear_tf=p.get("sublinear_tf", False),
        dtype=np.float32 if p.get("dtype","float32")=="float32" else np.float64,
    )
    corpus = long_df[text_field].fillna("").astype(str).tolist()
    t0 = time.time()
    X = vec.fit_transform(corpus)  # CSR (N_docs x |V|)

   # Use the same vocabulary and tokenization params to get raw counts
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
    X_counts = cv.transform(corpus)  # corpus = list/series of long texts you indexed
    
    # Document frequency (docs that contain the term at least once)
    df = (X_counts > 0).sum(axis=0).A1.astype(np.int32)
    
    # Collection frequency (total term occurrences across the whole corpus)
    cf = X_counts.sum(axis=0).A1.astype(np.int64) 
    
    secs = time.time() - t0
    print(f"[tfidf_unigram] docs={X.shape[0]} | vocab={X.shape[1]} | time={secs:.2f}s")

    artifacts = {
        "tfidf_docs.npz": X,
        "vocab.json":     {term:int(col) for term, col in vec.vocabulary_.items()},
        "idf.npy":        vec.idf_.astype(np.float32),
        "__num_docs__":   int(X.shape[0]),
        "__vocab_size__": int(X.shape[1]),
        "__corpus_hash__": _sha256_sample(corpus),
        "counts.npz" : X_counts,        # raw term counts, CSR int32
        "df.npy"     : df,              # per-term doc frequency
        "cf.npy"     : cf,              # per-term collection frequency
        "__has_counts__": True
    }
    return artifacts, vec, X
