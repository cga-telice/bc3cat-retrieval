# index_builder/bge_m3_colbert.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import os, json
import numpy as np
import faiss
import requests

# -----------------------
# Remote / Local encoding
# -----------------------
def _encode_colbert_remote(
    texts: List[str],
    api_base: str,
    max_length: int,
    timeout_s: int = 1200,
    batch: int = 128,
) -> List[np.ndarray]:
    url = api_base.rstrip("/") + "/encode_batch"
    out: List[np.ndarray] = []
    for i in range(0, len(texts), batch):
        payload = {
            "texts": texts[i:i+batch],
            "return_colbert_vecs": True,   # explicit — do not rely on "mode"
            "max_length": int(max_length),
        }
        r = requests.post(url, json=payload, timeout=timeout_s)
        r.raise_for_status()
        mats = r.json().get("colbert_vecs", [])
        for M in mats:
            out.append(np.asarray(M, dtype=np.float32))
    return out

def _load_model_local(model_name: str, use_fp16: bool):
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(model_name, use_fp16=use_fp16)

def _encode_colbert_local(model, texts: List[str], max_length: int) -> List[np.ndarray]:
    enc = model.encode(
        texts,
        batch_size=min(64, max(1, len(texts))),
        max_length=int(max_length),
        return_dense=False,
        return_sparse=False,
        return_colbert_vecs=True,
    )
    return [np.asarray(m, dtype=np.float32) for m in enc["colbert_vecs"]]

# === Contract 1: choose the text field (parity with dense builder) ===
def select_field(feats_meta: Optional[Dict]) -> str:
    """
    ColBERT should get raw (normalized) text. Prefer 'text_norm', then 'text'.
    If metadata is missing, fall back conservatively.
    """
    if feats_meta and "text_fields" in feats_meta and isinstance(feats_meta["text_fields"], dict):
        tf = feats_meta["text_fields"]
        # typical raw/normalized keys, if your meta defines them
        for cand in ("text_norm", "text"):
            if cand in tf:
                return tf[cand] if isinstance(tf[cand], str) else cand
    # meta empty or not helpful → default to normalized raw
    return "text_norm"

# Helper: resolve api_base from multiple possible YAML shapes
def _resolve_api_base(cfg: Dict) -> Optional[str]:
    # 1) ENV wins
    env = os.getenv("BGE_M3_API")
    if env:
        return env
    model = cfg.get("model", {}) or {}
    method = cfg.get("method", {}) or {}
    # 2) model.api_base (preferred alongside dense)
    if model.get("api_base"):
        return model["api_base"]
    # 3) method.api_base (sometimes placed here)
    if method.get("api_base"):
        return method["api_base"]
    # 4) method.params.api_base (as in the provided YAML)
    params = method.get("params") or {}
    if isinstance(params, dict) and params.get("api_base"):
        return params["api_base"]
    # 5) top-level api_base (just in case)
    if cfg.get("api_base"):
        return cfg["api_base"]
    return None

# === Contract 2: build (same return & artifacts layout as dense) ===
def build(cfg: Dict, long_df, text_field: str) -> Tuple[Dict, None, None]:
    """
    Artifacts under:
      <paths.index_root>/<method.save_as or method.name>/<io.data_dirname>/
    Files:
      - token_mats.bin  (FP16 concatenation of all doc token vectors)
      - offsets.npy     (int64, length N+1)
      - dim.json        {"d": <int>}
      - faiss.index     (IndexFlatIP over L2-normalized doc centroids)
    """
    method = cfg.get("method", {}) or {}
    paths  = cfg.get("paths", {}) or {}
    io     = cfg.get("io", {}) or {}
    model  = cfg.get("model", {}) or {}

    out_dirname  = method.get("save_as", method.get("name", "bge_m3_colbert"))
    index_root   = paths.get("index_root", "./index")
    data_dirname = io.get("data_dirname", "data")

    model_name     = model.get("name", "BAAI/bge-m3")
    use_fp16       = bool(model.get("use_fp16", True))
    max_len_doc    = int(model.get("max_length_doc", 2048))  # your YAML sets 256; honored here

    api_base = _resolve_api_base(cfg)

    # Helpful warning if someone accidentally nested 'params:' under 'save_as'
    if isinstance(method.get("save_as"), dict):
        raise ValueError(
            "YAML formatting error: 'save_as' should be a string. "
            "If you intended to supply 'params', make sure 'params:' is aligned with 'save_as:' (same indentation level)."
        )

    texts = long_df[text_field].astype(str).tolist()
    n_docs = len(texts)

    if text_field not in long_df.columns:
    # best-effort rescue
        if "text_norm" in long_df.columns:
            text_field = "text_norm"
        elif "text" in long_df.columns:
            text_field = "text"
        else:
            # last resort: keep original (likely 'text_word'), but warn
            print(f"[bge_m3_colbert] WARNING: text_field '{text_field}' not in df; "
                  f"available cols: {list(long_df.columns)[:8]} ...")

    # ---- Encode colbert token-level vectors
    if api_base:
        mats = _encode_colbert_remote(texts, api_base=api_base, max_length=max_len_doc)
    else:
        mdl = _load_model_local(model_name, use_fp16)
        mats = _encode_colbert_local(mdl, texts, max_len_doc)

    # ---- Sanity & shapes
    dims = [m.shape[1] for m in mats if m.size]
    if not dims:
        raise RuntimeError("No token vectors produced by bge-m3 colbert variant.")
    d = int(dims[0])
    if any(dd != d for dd in dims):
        raise ValueError(f"Dimension mismatch across token matrices: {sorted(set(dims))}")

    lengths = np.array([m.shape[0] for m in mats], dtype=np.int64)
    offsets = np.zeros(n_docs + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])
    # total_tokens = int(offsets[-1])  # not used directly, but keeps parity

    # ---- Persist
    data_dir = Path(index_root) / out_dirname / data_dirname
    data_dir.mkdir(parents=True, exist_ok=True)

    # Stream FP16 blocks to file (keeps RAM low)
    with open(data_dir / "token_mats.bin", "wb") as f:
        for m in mats:
            f.write(np.asarray(m, dtype=np.float16).tobytes(order="C"))

    np.save(data_dir / "offsets.npy", offsets)
    with open(data_dir / "dim.json", "w", encoding="utf-8") as f:
        json.dump({"d": d}, f)

    # ---- FAISS preselect (cosine via IP on centroids), parity with dense
    centroids = np.zeros((n_docs, d), dtype=np.float32)
    for i, L in enumerate(lengths):
        if L:
            centroids[i] = mats[i].mean(axis=0)
    faiss.normalize_L2(centroids)
    faiss_index = faiss.IndexFlatIP(d)
    faiss_index.add(centroids)
    faiss.write_index(faiss_index, str(data_dir / "faiss.index"))

    # ---- Artifacts dict (same keys your notebook expects)
    artifacts = {
        "offsets.npy": offsets,
        "dim.json": {"d": d},
        "__num_docs__": int(n_docs),
        "__vocab_size__": 0,
        "faiss_file.json": {"filename": "faiss.index"},
    }
    return artifacts, None, None


