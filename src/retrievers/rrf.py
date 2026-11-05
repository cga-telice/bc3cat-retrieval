# /src/retrievers/rrf.py
from __future__ import annotations
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import yaml

# ------------------ Minimal RRF engine (self-contained) ------------------

RRF_DEFAULT_K = 60  # constant C in 1/(C + rank)

@dataclass
class BaseComponent:
    name: str
    module: str           # retriever module name under retrievers/, e.g. "bm25_unigram"
    index_dir: str        # path to that component's index dir
    weight: float = 1.0
    k: int = 200          # how many candidates to pull from this component

class RRFEnsembler:
    """
    Fuses multiple child retrievers by Reciprocal Rank Fusion (RRF), aligning
    candidates via *external_id* rather than assuming identical doc-id orders.

    Each child retriever must implement:
      - load(index_dir) -> searcher
      - searcher.search(query_text, k) -> (doc_idx, scores)   # doc_idx w.r.t. that child
      - searcher.search_batch(texts, k) -> (doc_idx_mat, scores_mat)
      - searcher.external_ids: np.ndarray[str] (len N) for that child
    """
    def __init__(self, components: List[Dict[str, Any]], R: int = 60):
        # normalise component cfgs and load children
        self._comps_cfg = [BaseComponent(**c) if not isinstance(c, BaseComponent) else c
                           for c in components]
        self._children = []
        for c in self._comps_cfg:
            mod = import_module(f"retrievers.{c.module}")
            self._children.append(mod.load(Path(c.index_dir)))

        # Choose the first component as the *canonical* doc-id space
        self.base = self._children[0]
        self.external_ids = self.base.external_ids  # canonical external-id array
        # Build inverse map ext_id -> canonical doc_id
        self._inv = {str(e): i for i, e in enumerate(self.external_ids)}

        # Precompute per-component external-id arrays for fast lookup
        self._child_ext = [ch.external_ids for ch in self._children]
        self._R = int(R)

    @staticmethod
    def _rrf_contrib(fetch_k: int, weight: float, R: int) -> np.ndarray:
        # ranks 0..fetch_k-1
        ranks = np.arange(fetch_k, dtype=np.float32)
        return weight * (1.0 / (R + ranks))

    def _map_child_row_to_canonical(self, child_idx_row: np.ndarray, child_ext: np.ndarray) -> np.ndarray:
        """
        Convert a single row of child doc indices -> child external ids -> canonical doc ids.
        """
        ext_row = child_ext[child_idx_row]               # external_ids for that row
        # map each external_id to canonical doc_id (raises if not found)
        try:
            can_row = np.fromiter((self._inv[str(e)] for e in ext_row), count=ext_row.size, dtype=np.int64)
        except KeyError as e:
            raise ValueError(f"External id {e} from a component not present in canonical mapping") from None
        return can_row

    # ---- single-query API (kept efficient) ----
    def search(self, query: str, k: int = 100):
        N = len(self.external_ids)
        fused = np.zeros(N, dtype=np.float32)
        for cfg, child, child_ext in zip(self._comps_cfg, self._children, self._child_ext):
            idx_row, _ = child.search(query, k=cfg.k)           # (fetch_k,)
            if idx_row.size == 0:
                continue
            can_ids = self._map_child_row_to_canonical(idx_row, child_ext)  # (fetch_k,)
            contrib = self._rrf_contrib(idx_row.size, cfg.weight, self._R)  # (fetch_k,)
            fused[can_ids] += contrib

        if k <= 0:
            return np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.float32), {}
        part = np.argpartition(-fused, kth=min(k, fused.size)-1)[:k]
        order = np.argsort(-fused[part])
        top_idx = part[order].astype(np.int64)
        top_scores = fused[top_idx].astype(np.float32)
        return top_idx, top_scores, {}

    # ---- batched API without allocating a huge B×N matrix ----
    def search_batch(self, texts: List[str], k: int = 100):
        B = len(texts)
        k = max(0, int(k))
        top_idx_all = np.empty((B, k), dtype=np.int64) if k > 0 else np.empty((B, 0), dtype=np.int64)
        top_scr_all = np.empty((B, k), dtype=np.float32) if k > 0 else np.empty((B, 0), dtype=np.float32)

        # Run each child once in batch to avoid repeated work
        child_rows = []
        for cfg, child in zip(self._comps_cfg, self._children):
            idx_mat, _ = child.search_batch(texts, k=cfg.k)  # shape (B, fetch_k)
            child_rows.append(idx_mat)

        for i in range(B):
            fused = np.zeros(len(self.external_ids), dtype=np.float32)
            for (cfg, idx_mat, child_ext) in zip(self._comps_cfg, child_rows, self._child_ext):
                row_idx = idx_mat[i]                          # (fetch_k,)
                if row_idx.size == 0:
                    continue
                can_ids = self._map_child_row_to_canonical(row_idx, child_ext)
                contrib = self._rrf_contrib(row_idx.size, cfg.weight, self._R)
                fused[can_ids] += contrib
            if k > 0:
                part = np.argpartition(-fused, kth=min(k, fused.size)-1)[:k]
                order = np.argsort(-fused[part])
                top_idx = part[order].astype(np.int64)
                top_scr = fused[top_idx].astype(np.float32)
                top_idx_all[i] = top_idx
                top_scr_all[i] = top_scr

        return top_idx_all, top_scr_all, {}

# ------------------ YAML-driven retriever wrapper ------------------

def _read_yaml(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _load_components(rrf_cfg: dict):
    comps_cfg = rrf_cfg.get("components", [])
    if not comps_cfg:
        raise ValueError("rrf.components[] is empty")
    # normalise to list[dict] for the ensembler
    out = []
    for c in comps_cfg:
        out.append({
            "name":   c["name"],
            "module": c.get("module", c["name"]),
            "index_dir": str(c["index_dir"]),
            "weight": float(c.get("weight", 1.0)),
            "k":      int(c.get("k", rrf_cfg.get("k_each", 200))),
        })
    return out

class _RRFWrapper:
    """Notebook-compatible searcher: has .external_ids and .search_batch(texts,k)->(top_idx, top_scores)"""
    def __init__(self, ens: RRFEnsembler):
        self._ens = ens
        self.external_ids = ens.external_ids  # shared across components

    def search_batch(self, texts: List[str], k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        top_idx, top_scores, _ = self._ens.search_batch(texts, k=k)
        return top_idx, top_scores

    def search(self, text: str, k: int = 100):
        top_idx, top_scores, _ = self._ens.search(text, k=k)
        return top_idx, top_scores

def load(index_dir: str|Path):
    """
    Entry for retrieve.ipynb dynamic loader.
    Derive METHOD_NAME from index_dir.name and read /work/configs/{METHOD_NAME}.yaml
    """
    index_dir = Path(index_dir)
    method_name = index_dir.name  # e.g., rrf__bm25_char or rrf__bm25_char_e5
    cfg_path = Path("/work/configs") / f"{method_name}.yaml"
    cfg = _read_yaml(cfg_path)
    rrf_cfg = cfg.get("rrf", {}) or {}

    comps = _load_components(rrf_cfg)
    ens = RRFEnsembler(comps, R=int(rrf_cfg.get("rrf_constant", 60)))
    return _RRFWrapper(ens)


