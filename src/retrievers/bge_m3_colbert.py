# /src/retrievers/bge_m3_colbert.py (fast version)
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Optional
import os, json
import numpy as np
import faiss

# Optional GPU path for MaxSim
try:
    import torch
    import torch.nn.functional as F
    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # allow import without requests for local-only mode

"""
Why this version?
- Your previous implementation did exact MaxSim over *preselect=2000* docs/query,
  which is O(B * preselect * Tq * Td * d) and will explode for 16k queries.
- This retriever:
  1) **Caps lengths**: trims query/doc token matrices to {TQ_CAP, TD_CAP}.
  2) **Cuts preselect** aggressively (defaults to 256, overridable from meta.yaml).
  3) **Blocks** docs and computes MaxSim **on GPU** (torch) with einsum.
  4) Falls back to a vectorized NumPy path if torch/GPU is unavailable.

Expected: ~10–100× speedup depending on caps and GPU.
"""

# ----------------------------- knobs -----------------------------------------
REMOTE_MAX_BATCH = int(os.getenv("BGE_REMOTE_MAX_BATCH", "256"))
TQ_CAP = int(os.getenv("COLBERT_TQ_CAP", "256"))       # cap query tokens
TD_CAP = int(os.getenv("COLBERT_TD_CAP", "256"))      # cap doc tokens
DOC_BLOCK = int(os.getenv("COLBERT_DOC_BLOCK", "128")) # docs per GPU block
DTYPE = torch.float16 if _HAS_TORCH and torch.cuda.is_available() else None

# ----------------------------- IO utils --------------------------------------

def _read_json(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_mapping(mapping_path: Path):
    doc_ids, ext_ids = [], []
    with open(mapping_path, "r", encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            obj = json.loads(ln)
            doc_ids.append(int(obj["doc_id"]))
            ext_ids.append(str(obj["external_id"]))
    doc_ids = np.asarray(doc_ids, dtype=np.int64)
    ext_ids = np.asarray(ext_ids, dtype=object)
    if len(doc_ids) == 0:
        raise ValueError("Empty mapping.jsonl")
    if not (doc_ids.min() == 0 and doc_ids.max() == len(doc_ids) - 1):
        raise ValueError("mapping.jsonl doc_id must be contiguous 0..N-1")
    return doc_ids, ext_ids

# ------------------------ Remote / Local encoding ----------------------------

def _encode_colbert_remote(texts: List[str], api_base: str, max_length: int, timeout_s: int = 600) -> List[np.ndarray]:
    if requests is None:
        raise RuntimeError("requests is required for remote encoding but is not installed")
    url = api_base.rstrip("/") + "/encode_batch"
    out: List[np.ndarray] = []
    norm_texts = [t if isinstance(t, str) else str(t) for t in texts]
    norm_texts = [t for t in norm_texts if t.strip()]

    B = max(1, REMOTE_MAX_BATCH)
    for i in range(0, len(norm_texts), B):
        payload = {
            "texts": norm_texts[i:i+B],
            "return_colbert_vecs": True,
            "return_dense": False,
            "return_sparse": False,
            "max_length": int(max_length),
        }
        r = requests.post(url, json=payload, timeout=timeout_s)
        r.raise_for_status()
        mats = r.json().get("colbert_vecs", [])
        out.extend([np.asarray(m, dtype=np.float32) for m in mats])
    return out


def _load_model_local(model_name: str, use_fp16: bool):
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(model_name, use_fp16=use_fp16)


def _encode_colbert_local(model, texts: List[str], max_length: int) -> List[np.ndarray]:
    enc = model.encode(
        texts,
        batch_size=min(len(texts), 64),
        max_length=int(max_length),
        return_dense=False,
        return_sparse=False,
        return_colbert_vecs=True,
    )
    mats = enc.get("colbert_vecs", [])
    return [np.asarray(m, dtype=np.float32) for m in mats]

# ------------------------- packing helpers -----------------------------------

def _cap_tokens(M: np.ndarray, tcap: int) -> np.ndarray:
    if M.shape[0] <= tcap:
        return M
    return M[:tcap]


def _stack_docs(doc_mats: List[np.ndarray], td_cap: int) -> Tuple[np.ndarray, np.ndarray]:
    """Pad/truncate a list of (Td_i, d) to (B, Td_cap, d) and return lengths."""
    if not doc_mats:
        return np.zeros((0, td_cap, 0), dtype=np.float32), np.zeros((0,), dtype=np.int32)
    d = doc_mats[0].shape[1]
    B = len(doc_mats)
    out = np.zeros((B, td_cap, d), dtype=np.float32)
    lens = np.zeros((B,), dtype=np.int32)
    for i, M in enumerate(doc_mats):
        L = min(M.shape[0], td_cap)
        if L > 0:
            out[i, :L] = M[:L]
        lens[i] = L
    return out, lens

# ------------------------------- Searcher ------------------------------------

class ColBERTSearcher:
    def __init__(self, index_dir: Path, model_name: str, use_fp16: bool, max_length_query: int, api_base: Optional[str], preselect: int, already_norm: bool = True):
        self.dir = Path(index_dir)
        self.api_base = api_base
        self._max_length_query = int(max_length_query)
        self._preselect = int(preselect)
        self._already_norm = already_norm  # true if encoder outputs L2-normalized tokens

        # ---- mapping / external ids
        self.doc_ids, self.external_ids = _load_mapping(self.dir / "mapping.jsonl")

        # ---- data files
        data_dir = self.dir / "data"
        self.offsets = np.load(data_dir / "offsets.npy").astype(np.int64)
        with open(data_dir / "dim.json", "r", encoding="utf-8") as f:
            self.d = int(json.load(f)["d"])
        total_tokens = int(self.offsets[-1])
        # memory-map fp16 blob; we will slice and cast on demand
        self._mm = np.memmap(data_dir / "token_mats.bin", dtype=np.float16, mode="r", shape=(total_tokens * self.d,))
        # FAISS preselection on centroids
        self.faiss = faiss.read_index(str(data_dir / "faiss.index"))

        # local model only if no API base (rare for you)
        if not self.api_base:
            from FlagEmbedding import BGEM3FlagModel
            self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
        else:
            self.model = None

        # safety: extremely large preselect will be slow
        if self._preselect > 512:
            print(f"[bge_m3_colbert] WARNING: preselect={self._preselect} is large; consider 128–512 for speed.")

    # -------- encoding & slicing --------
    def _encode_queries(self, texts: List[str]) -> List[np.ndarray]:
        if self.api_base:
            mats = _encode_colbert_remote(texts, self.api_base, self._max_length_query)
        else:
            mats = _encode_colbert_local(self.model, texts, self._max_length_query)
        return [ _cap_tokens(M, TQ_CAP) for M in mats ]

    def _doc_tokens(self, i: int) -> np.ndarray:
        a = int(self.offsets[i]); b = int(self.offsets[i+1])
        if b <= a:
            return np.empty((0, self.d), dtype=np.float32)
        flat = self._mm[a*self.d : b*self.d]
        M = np.asarray(flat, dtype=np.float16).reshape(-1, self.d)
        return _cap_tokens(M.astype(np.float32, copy=False), TD_CAP)

    # -------- GPU MaxSim for one query over a block of docs --------
    def _maxsim_gpu_one(self, Q: np.ndarray, doc_ids: np.ndarray) -> np.ndarray:
        assert _HAS_TORCH and torch.cuda.is_available()
        Qt = torch.from_numpy(Q)
        if DTYPE is not None:
            Qt = Qt.to(device="cuda", dtype=DTYPE)
        else:
            Qt = Qt.to(device="cuda")
        if not self._already_norm:
            Qt = F.normalize(Qt, p=2, dim=-1)

        scores_all = []
        for s in range(0, len(doc_ids), DOC_BLOCK):
            block_ids = doc_ids[s:s+DOC_BLOCK]
            docs = [self._doc_tokens(int(idx)) for idx in block_ids]
            Dnp, lens = _stack_docs(docs, TD_CAP)   # (B, Ld, d)
            Dt = torch.from_numpy(Dnp)
            if DTYPE is not None:
                Dt = Dt.to(device="cuda", dtype=DTYPE)
            else:
                Dt = Dt.to(device="cuda")
            if not self._already_norm:
                Dt = F.normalize(Dt, p=2, dim=-1)
            # einsum: (q,d) x (b,l,d) -> (b,q,l)
            S = torch.einsum("qd,bld->bql", Qt, Dt)
            s_block = S.amax(dim=2).sum(dim=1).float().detach().cpu().numpy()
            scores_all.append(s_block)
            del Dt, S
        return np.concatenate(scores_all, axis=0) if scores_all else np.zeros((0,), dtype=np.float32)

    # -------- CPU vectorized MaxSim (fallback) --------
    def _maxsim_cpu_one(self, Q: np.ndarray, doc_ids: np.ndarray) -> np.ndarray:
        scores = np.empty((len(doc_ids),), dtype=np.float32)
        for j, idx in enumerate(doc_ids):
            D = self._doc_tokens(int(idx))
            if D.size == 0 or Q.size == 0:
                scores[j] = 0.0
                continue
            # (Tq, Td)
            sims = Q @ D.T
            scores[j] = sims.max(axis=1).sum(dtype=np.float32)
        return scores

    # -------- public API --------
    def search(self, query_text: str, k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        top_idx, top_sc = self.search_batch([query_text], k)
        return top_idx[0], top_sc[0]

    def search_batch(self, texts: List[str], k: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        B = len(texts)
        N = len(self.doc_ids)
        k_eff = min(max(int(k), 1), N)
        pre = max(1, min(self._preselect, N))

        # 1) encode queries
        Qmats = self._encode_queries(texts)

        # 2) FAISS preselect via centroids
        Qc = np.zeros((B, self.d), dtype=np.float32)
        for i, M in enumerate(Qmats):
            if M.size:
                Qc[i] = M.mean(axis=0)
        faiss.normalize_L2(Qc)
        _, Cands = self.faiss.search(Qc, pre)  # (B, pre)

        # 3) exact MaxSim on candidate sets
        top_idx = np.zeros((B, k_eff), dtype=np.int64)
        top_sc  = np.zeros((B, k_eff), dtype=np.float32)
        use_gpu = _HAS_TORCH and torch.cuda.is_available()
        for i in range(B):
            qi = Qmats[i]
            cand = Cands[i]
            if use_gpu:
                scores = self._maxsim_gpu_one(qi, cand)
            else:
                scores = self._maxsim_cpu_one(qi, cand)
            kk = min(k_eff, len(scores))
            part = np.argpartition(-scores, kth=kk-1)[:kk]
            order = np.argsort(-scores[part])
            sel = part[order]
            top_idx[i, :kk] = cand[sel]
            top_sc[i,  :kk] = scores[sel]
        return top_idx, top_sc

# ------------------------------- Factory -------------------------------------

def load(index_dir: str | Path):
    """Factory mirroring dense/tfidf/BM25 retrievers.
    Reads meta.json, honors ENV BGE_M3_API if present.
    """
    index_dir = Path(index_dir)
    meta = _read_json(index_dir / "meta.json")

    model_name = meta.get("software", {}).get("model_name") or "BAAI/bge-m3"
    params = meta.get("params", {}) or {}
    use_fp16 = bool(params.get("use_fp16", True))
    max_q    = int(params.get("max_length_query", 256))

    # Preselection: prefer retrieval.preselect, else params.preselect, else 256
    preselect = int((meta.get("retrieval", {}) or {}).get("preselect", params.get("preselect", 256)))

    # Query to server if available; otherwise local model
    api_base = os.getenv("BGE_M3_API") or params.get("api_base") or None

    # If your server already returns L2-normalized token vectors (your tests showed True),
    # we can skip re-normalization for a small speed gain.
    already_norm = bool(params.get("normalized_tokens", True))

    return ColBERTSearcher(index_dir, model_name, use_fp16, max_q, api_base, preselect, already_norm)

