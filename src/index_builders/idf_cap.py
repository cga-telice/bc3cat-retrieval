"""The IDF guard — S9 work item 3, shared by the two BM25 builders.

A config may set `method.params.idf_cap_df: c`. The builder then caps every term's IDF at the IDF a term
in `c` documents would have, with the builder's own formula, on this corpus:

    cap = log((N - c + 0.5) / (c + 0.5) + 1)

The capped IDF is what both the document weights and the saved `idf.npy` use, so the retriever, which
reads `idf.npy` for the query side, needs no change and the cap applies to both factors of the score.
Without the parameter the IDF is returned untouched, so every existing index rebuilds byte-identically.

S9 fixes c = 1,200: S91's rare cut (`results/S91/rare_codes.md`), itself read on dev `resumen`, so the
guard's dev reading is in-sample (S9 design, work item 3).
"""

from __future__ import annotations

from typing import Any

import numpy as np


def cap_value(n_docs: int, cap_df: int) -> float:
    return float(np.log((n_docs - cap_df + 0.5) / (cap_df + 0.5) + 1.0))


def apply_idf_cap(idf: np.ndarray, n_docs: int, params: dict[str, Any]) -> tuple[np.ndarray, float | None]:
    """(idf, cap). `cap` is None when the config sets no `idf_cap_df`."""
    cap_df = params.get("idf_cap_df")
    if cap_df is None:
        return idf, None
    if not (isinstance(cap_df, int) and 0 < cap_df < n_docs):
        raise ValueError(f"idf_cap_df must be an integer in (0, {n_docs}), got {cap_df!r}")
    cap = cap_value(n_docs, cap_df)
    return np.minimum(idf, np.float32(cap)).astype(idf.dtype), cap
