# /src/index_builders/tfidf_char_3_5.py
# Build TF–IDF index with character n-grams (3–5), using sklearn.
# Mirrors the structure used by other TF–IDF builders in this project.
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
        # Type guard (just in case) and stable encoding
        t = texts[i]
        if t is None:
            t = ""
        h.update(str(t).encode("utf-8"))
    return "sha256:" + h.hexdigest()

def select_field(feats_meta: Dict[str, Any]) -> str:
    """
    Choose the feature column to index.
    Prefer a dedicated char-ngram text field if present; otherwise fall back to the
    standard word_unigram field (the analyzer='char_wb' will still work on raw text).
    """
    tf = feats_meta.get("text_fields", {})
    return tf.get("char_ngram") or tf.get("word_unigram") or "text_word"

def build(cfg: Dict[str, Any], long_df, text_field: str):
    """
    Fit Character TF–IDF (3–5) on long documents.

    Returns:
      artifacts: dict with files to persist (npz/json/npy) + meta counters
      transformer: fitted TfidfVectorizer (for quick probe)
      X_docs: CSR matrix of document vectors
    """
    p = cfg["method"].get("params", {})

    # Defaults for char 3–5 (wb = within word boundaries to avoid cross-word noise)
    analyzer     = p.get("analyzer", "char_wb")
    ngram_range  = tuple(p.get("ngram_range", [3, 5]))
    lowercase    = p.get("lowercase", True)
    strip_acc    = p.get("strip_accents", "unicode")
    norm         = p.get("norm", "l2")
    use_idf      = p.get("use_idf", True)
    smooth_idf   = p.get("smooth_idf", True)
    sublinear_tf = p.get("sublinear_tf", False)
    min_df       = p.get("min_df", 2)
    dtype_opt    = np.float32 if p.get("dtype", "float32") == "float32" else np.float64

    vec = TfidfVectorizer(
        analyzer=analyzer,
        ngram_range=ngram_range,
        lowercase=lowercase,
        strip_accents=strip_acc,
        norm=norm,
        use_idf=use_idf,
        smooth_idf=smooth_idf,
        sublinear_tf=sublinear_tf,
        min_df=min_df,
        dtype=dtype_opt,
    )

    corpus = long_df[text_field].fillna("").astype(str).tolist()

    t0 = time.time()
    X = vec.fit_transform(corpus)  # CSR (N_docs x |V|)
    secs = time.time() - t0
    print(f"[tfidf_char_3_5] docs={X.shape[0]} | vocab={X.shape[1]} | time={secs:.2f}s")

    # Build raw counts with the exact same analyzer/vocab (needed for df/cf artifacts)
    cv = CountVectorizer(
        vocabulary=vec.vocabulary_,
        analyzer=vec.analyzer,
        ngram_range=vec.ngram_range,
        lowercase=vec.lowercase,
        strip_accents=vec.strip_accents,
        min_df=min_df,
        dtype=np.int32,
    )
    X_counts = cv.transform(corpus)

    # Document frequency (docs that contain the term at least once)
    df = (X_counts > 0).sum(axis=0).A1.astype(np.int32)

    # Collection frequency (total term occurrences across the whole corpus)
    cf = X_counts.sum(axis=0).A1.astype(np.int64)

    artifacts = {
        "tfidf_docs.npz": X,
        "vocab.json":     {term:int(col) for term, col in vec.vocabulary_.items()},
        "idf.npy":        vec.idf_.astype(np.float32),
        "__num_docs__":   int(X.shape[0]),
        "__vocab_size__": int(X.shape[1]),
        "__corpus_hash__": _sha256_sample(corpus),
        "counts.npz" : X_counts,   # raw term counts, CSR int32
        "df.npy"     : df,         # per-term doc frequency
        "cf.npy"     : cf,         # per-term collection frequency
        "__has_counts__": True
    }
    return artifacts, vec, X
