# /src/rerankers/bm25_tiebreak.py
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Dict, Any

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)

def rerank_with_metadata(
    candidates: List[Dict[str, Any]],
    query_meta: Dict[str, Any],
    doc_meta: pd.DataFrame,
    w_num: float = 1.0,
    w_param: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Re-rank BM25 candidates by tie-breaking with numeric + parameter features.

    Args:
      candidates: list of dicts {rank, index_item_key, score, ...} from BM25
      query_meta: dict with query 'numbers' (list[float]) and
                  'param_values_multi_norm' (list[str])
      doc_meta:   dataframe indexed by item_key with cols ['numbers','param_values_multi_norm']
      w_num:      weight for numeric Jaccard
      w_param:    weight for param Jaccard
    Returns:
      reordered list of candidate dicts (sorted in place by adjusted_score)
    """
    q_nums   = set(str(x) for x in query_meta.get("numbers", []) if x is not None)
    q_params = set(query_meta.get("param_values_multi_norm", []))

    rescored = []
    for c in candidates:
        doc_id = c["index_item_key"]
        base   = float(c["score"])
        extra  = 0.0
        if doc_id in doc_meta.index:
            drow = doc_meta.loc[doc_id]
            d_nums   = set(str(x) for x in drow.get("numbers", []) if x is not None)
            d_params = set(drow.get("param_values_multi_norm", []))
            extra += w_num   * jaccard(q_nums, d_nums)
            extra += w_param * jaccard(q_params, d_params)
        c2 = dict(c)
        c2["adjusted_score"] = base + extra
        rescored.append(c2)

    return sorted(rescored, key=lambda r: r["adjusted_score"], reverse=True)
