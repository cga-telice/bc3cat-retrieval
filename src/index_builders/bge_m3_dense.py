# src/index_builders/bge_m3_dense.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import os, json, math
import numpy as np
import faiss
import requests

# -----------------------
# Remote / Local encoding
# -----------------------
def _encode_dense_remote(texts: List[str], api_base: str, max_length: int, timeout_s: int = 600) -> np.ndarray:
    """Call the bge-m3 API /encode_batch for dense vectors."""
    url = api_base.rstrip("/") + "/encode_batch"
    # chunk to avoid very large JSON posts
    B = 256
    out = []
    for i in range(0, len(texts), B):
        payload = {"texts": texts[i:i+B], "mode": "dense", "max_length": int(max_length)}
        r = requests.post(url, json=payload, timeout=timeout_s)
        r.raise_for_status()
        vecs = r.json()["vecs"]
        out.extend(vecs)
    X = np.asarray(out, dtype=np.float32)
    return X

def _load_model_local(model_name: str, use_fp16: bool):
    from FlagEmbedding import BGEM3FlagModel
    return BGEM3FlagModel(model_name, use_fp16=use_fp16)

def _encode_dense_local(model, texts: List[str], max_length: int) -> np.ndarray:
    enc = model.encode(
        texts,
        batch_size=64,
        max_length=int(max_length),
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return enc["dense_vecs"].astype(np.float32)  # (N, 1024)

# === Contract 1: choose the text field ===
def select_field(feats_meta: Optional[Dict]) -> str:
    # prefer your normalized word tokens if available; else fall back to "text"
    if feats_meta and "text_fields" in feats_meta:
        for cand in ["text_word", "text_norm", "text"]:
            if cand in feats_meta["text_fields"].values() or cand in feats_meta["text_fields"]:
                return cand
    return "text_word"

# === Contract 2: build ===
def build(cfg: Dict, long_df, text_field: str) -> Tuple[Dict, None, None]:
    """
    Returns (artifacts_dict, transformer_or_None, X_docs_or_None).
    The notebook will write mapping/fields/meta and place artifacts under data/.
    We also persist a FAISS index to data/faiss.index.
    """
    model_cfg = cfg["model"]
    model_name = model_cfg.get("name", "BAAI/bge-m3")
    use_fp16   = bool(model_cfg.get("use_fp16", True))
    max_len    = int(model_cfg.get("max_length_doc", 2048))

    # API base: env var wins; else YAML; else sensible default (compose service name)
    api_base = os.getenv("BGE_M3_API") or model_cfg.get("api_base")
    texts = long_df[text_field].astype(str).tolist()

    if api_base:
        # --- encode via container API ---
        X = _encode_dense_remote(texts, api_base=api_base, max_length=max_len)
    else:
        # --- local fallback (same behavior as before) ---
        model = _load_model_local(model_name, use_fp16)
        X = _encode_dense_local(model, texts, max_len)

    # Build FAISS (cosine via IP with L2-normalized vectors)
    faiss.normalize_L2(X)
    index = faiss.IndexFlatIP(X.shape[1])
    index.add(X)

    # Artifacts auto-written by the notebook (for .npy/.json)
    artifacts = {
        "docvecs.npy": X,
        "__num_docs__": int(len(texts)),
        "__vocab_size__": 0,
        "faiss_file.json": {"filename": "faiss.index"}
    }

    # Persist FAISS index into data/
    out_dirname = cfg["method"].get("save_as", cfg["method"]["name"])
    data_dir = Path(cfg["paths"]["index_root"]) / out_dirname / cfg["io"]["data_dirname"]
    data_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(data_dir / "faiss.index"))

    return artifacts, None, None

