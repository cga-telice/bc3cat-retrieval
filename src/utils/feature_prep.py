"""Feature derivation — the functions that used to live inside `features.ipynb`.

Lifted verbatim (with ast, not retyped) so that the same pipeline can be applied to the
synthetic query sets, which the notebook had no way to reach. `tests/test_feature_prep.py`
pins them to the OEB feature tables they originally produced.

The one addition is `build_features`, which is the notebook's own sequence of calls, in the
notebook's own order, as a function.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

#: The notebook's feature switches, verbatim. They have never been anything but these
#: values; they are kept as a dict so the lifted functions read exactly as they did.
CFG = {
    "use_param_phrases": True,
    "also_keep_raw_text": True,   # only affects *_add (replace ignores this)
    "make_bigrams": True,
    "mark_has_numbers": True,
}

WORD_TOKEN_RE = re.compile(r"[a-záéíóúüñ]+|\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)?", flags=re.UNICODE)


def snake_merge(norm_string: str) -> str:
    toks = WORD_TOKEN_RE.findall(str(norm_string))
    return "_".join(toks)


def make_bigrams(tokens):
    return [(tokens[i], tokens[i+1]) for i in range(len(tokens)-1)] if len(tokens) >= 2 else []


def to_space_joined_bigrams(bigrams):
    return " ".join([f"{a}|{b}" for (a,b) in bigrams])


def _norm_list(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return []
    return list(x) if isinstance(x, (list, tuple)) else [x]


def _as_tokens_str(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return []
    if isinstance(x, (list, tuple, np.ndarray)):
        return [str(t) for t in x]
    return str(x).split()


def _find_phrase_occurrences(tokens, phrase_words):
    occ = []
    L = len(phrase_words)
    if L == 0 or L > len(tokens):
        return occ
    i = 0
    while i <= len(tokens) - L:
        if tokens[i:i+L] == phrase_words:
            occ.append(i)
            i += L  # non-overlap
        else:
            i += 1
    return occ


def inject_phrases_add(tokens, phrases):
    """
    Metadata-aware ADD:
      - Always append every phrase token from metadata (independent of presence in text).
      - Keep original tokens intact.
    """
    tokens = list(tokens)
    merged = ["_".join(p.split("_")) if "_" in p else "_".join(p.split()) for p in phrases]
    # phrases in our pipeline already come snake_cased; the line above is just defensive.
    return tokens + list(merged)


def inject_phrases_replace(tokens, phrases):
    """
    Metadata-aware REPLACE:
      1) Replace any *contiguous* occurrences in the base tokens by the merged token
         (longer phrases first; non-overlapping).
      2) Append ONLY the phrases that did NOT occur in the text (so metadata is still visible).
    """
    tokens = list(tokens)

    # normalize phrases to word lists (split on '_' preferred, fallback on space)
    norm = []
    for p in phrases:
        parts = p.split("_")
        if len(parts) == 1:
            parts = p.split()
        norm.append((p, parts))

    # sort by length desc so longer phrases win overlaps
    norm.sort(key=lambda x: (-len(x[1]), x[0]))

    marks, occupied = [], set()
    found = set()

    for p, words in norm:
        for s in _find_phrase_occurrences(tokens, words):
            idxs = range(s, s+len(words))
            if any(j in occupied for j in idxs):
                continue
            marks.append((s, len(words), p))  # p is already snake_cased
            occupied.update(idxs)
            found.add(p)

    if marks:
        marks.sort(key=lambda t: t[0])
        out, cur = [], 0
        for s, L, merged in marks:
            while cur < s:
                out.append(tokens[cur]); cur += 1
            out.append(merged); cur = s + L
        out.extend(tokens[cur:])
    else:
        out = tokens

    # Append phrases that were NOT found in text
    not_found = [p for p, _ in norm if p not in found]
    return out + not_found


def rebuild_param_phrases(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # param_values_multi_norm is a list of distinct parameter values — keep them separate
    def _norm_list_vals(x):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return []
        if isinstance(x, (list, tuple, np.ndarray)):
            return [str(t).strip() for t in x if str(t).strip()]
        # string fallback: treat it as a single value (upstream ideally keeps lists)
        s = str(x).strip()
        return [s] if s else []

    df["param_phrases"] = df["param_values_multi_norm"].map(
        lambda vals: sorted(
            {snake_merge(v) for v in _norm_list_vals(vals)},
            key=lambda s: (-len(s.split("_")), s)
        )
    )
    return df


def add_optional_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if CFG["make_bigrams"]:
        df["tokens_bigram"] = df["tokens_word"].map(make_bigrams)
        df["text_word_uni_bi"] = df["text_word"] + " " + df["tokens_bigram"].map(to_space_joined_bigrams)
    if CFG["mark_has_numbers"]:
        df["has_numbers"] = df["numbers"].map(lambda xs: len(xs) > 0)
    return df


def _as_list(x):
    if x is None or (isinstance(x, float) and pd.isna(x)): return []
    if isinstance(x, list): return x
    if isinstance(x, tuple): return list(x)
    if isinstance(x, np.ndarray): return x.tolist()
    return [x]


def add_bm25_bigram_tokens(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "tokens_bigram" not in df.columns:
        def _make_bigrams(tokens):
            toks = _as_list(tokens)
            return [(toks[i], toks[i+1]) for i in range(len(toks)-1)] if len(toks) >= 2 else []
        df["tokens_bigram"] = df["tokens_word"].map(_make_bigrams)
    df["tokens_word"]   = df["tokens_word"].map(_as_list)
    df["tokens_bigram"] = df["tokens_bigram"].map(_as_list)
    df["tokens_word_bi"] = df.apply(
        lambda r: _as_list(r["tokens_word"]) + [f"{a}_{b}" for (a, b) in _as_list(r["tokens_bigram"])],
        axis=1
    )
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """The notebook's feature sequence, in its order, over one frame.

    Mirrors lines 280-350 of the original single cell: phrases are rebuilt, the two phrase
    injections are derived from the base tokens, then the optional features and the bigram
    tokens are added.
    """
    feat = rebuild_param_phrases(df)

    base_tokens = feat["text_word"].map(_as_tokens_str)
    feat["text_word_phrases_add"] = [
        " ".join(inject_phrases_add(toks, phrases))
        for toks, phrases in zip(base_tokens, feat["param_phrases"])
    ]
    feat["text_word_phrases_replace"] = [
        " ".join(inject_phrases_replace(toks, phrases))
        for toks, phrases in zip(base_tokens, feat["param_phrases"])
    ]

    feat = add_optional_features(feat)
    feat = add_bm25_bigram_tokens(feat)
    return feat
