#/work/apis/bge_m3/serve.py

from __future__ import annotations
import os, time
from typing import List, Literal, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import torch

# Lazy import so startup is quick; model loads on first access
from FlagEmbedding import BGEM3FlagModel

APP_NAME = "bge-m3-api"
DEFAULT_MODEL = os.getenv("BGE_MODEL", "BAAI/bge-m3")
USE_FP16 = os.getenv("BGE_USE_FP16", "false").lower() in {"1", "true", "yes", "y"}
MAX_BATCH = int(os.getenv("BGE_MAX_BATCH", "256"))
MAX_TEXT_LEN = int(os.getenv("BGE_MAX_TEXT_LEN", "20000"))  # chars, non-binding safeguard
MAX_LENGTH_QUERY = int(os.getenv("BGE_MAX_LENGTH_QUERY", "256"))
MAX_LENGTH_DOC = int(os.getenv("BGE_MAX_LENGTH_DOC", "2048"))

ENABLE_CORS = os.getenv("BGE_ENABLE_CORS", "false").lower() in {"1","true","yes"}
ALLOWED_ORIGINS = os.getenv("BGE_CORS_ORIGINS", "").split(",") if ENABLE_CORS else []

NORMALIZE_DENSE = os.getenv("BGE_NORMALIZE", "true").lower() in {"1","true","yes","y"}
NORMALIZE_COLBERT = os.getenv("BGE_NORMALIZE_COLBERT", "true").lower() in {"1","true","yes","y"}

# -------------------------------------------------------------------
# FastAPI app
# -------------------------------------------------------------------
app = FastAPI(title=APP_NAME)

if ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in ALLOWED_ORIGINS if o],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# -------------------------------------------------------------------
# Model holder (loaded on first request)
# -------------------------------------------------------------------
_model: Optional[BGEM3FlagModel] = None

def get_model() -> BGEM3FlagModel:
    global _model
    if _model is None:
        t0 = time.time()
        _model = BGEM3FlagModel(DEFAULT_MODEL, use_fp16=USE_FP16)
        print(f"[startup] Loaded {DEFAULT_MODEL} (fp16={USE_FP16}) in {time.time()-t0:.2f}s")
    return _model

# -------------------------------------------------------------------
# Schemas
# -------------------------------------------------------------------
Mode = Literal["dense", "sparse", "colbert"]  # request "mode" remains for max_length defaults

class _BaseReq(BaseModel):
    # NEW: output selection flags (all optional; default keeps previous behavior)
    return_dense: Optional[bool] = Field(None, description="If true, include dense vectors")
    return_sparse: Optional[bool] = Field(None, description="If true, include sparse lexical weights")
    return_colbert_vecs: Optional[bool] = Field(None, description="If true, include ColBERT token vectors")
    max_length: Optional[int] = Field(None, description="Token max_length override")

class EncodeRequest(_BaseReq):
    text: str = Field(..., description="Single input text")
    mode: Mode = Field("dense", description="dense|sparse (only affects defaults)")

    @validator("text")
    def _chk_text(cls, v: str):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("text must be a non-empty string")
        if len(v) > MAX_TEXT_LEN:
            raise ValueError(f"text too long (> {MAX_TEXT_LEN} chars)")
        return v

class EncodeBatchRequest(_BaseReq):
    texts: List[str] = Field(..., description="Batch of texts")
    mode: Mode = Field("dense", description="dense|sparse (only affects defaults)")

    @validator("texts")
    def _chk_texts(cls, v: List[str]):
        if not v:
            raise ValueError("texts must be non-empty")
        if len(v) > MAX_BATCH:
            raise ValueError(f"batch too large (>{MAX_BATCH})")
        for t in v:
            if not isinstance(t, str) or not t.strip():
                raise ValueError("each text must be a non-empty string")
            if len(t) > MAX_TEXT_LEN:
                raise ValueError(f"a text is too long (> {MAX_TEXT_LEN} chars)")
        return v

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

# --- update _decide_flags to keep current defaults, adding only a 'colbert' convenience ---
def _decide_flags(req: _BaseReq, mode_hint: Optional[str] = None):
    """
    Backwards-compatible output selection:
    - If no flags are given:
        mode="dense"   → dense (old default)
        mode="sparse"  → sparse (old shortcut)
        mode="colbert" → colbert (new shortcut)
    - Otherwise, honor exactly the flags.
    """
    if req.return_dense is None and req.return_sparse is None and req.return_colbert_vecs is None:
        if mode_hint == "colbert":
            return False, False, True
        if mode_hint == "sparse":
            return False, True, False
        return True, False, False  # dense
    return bool(req.return_dense), bool(req.return_sparse), bool(req.return_colbert_vecs)

# --- normalize utilities (kept small & optional via envs) ---
def _l2norm_rows_np(mat):
    # mat: list[list[float]] or np.ndarray
    import numpy as _np
    A = _np.asarray(mat, dtype=_np.float32)
    n = _np.linalg.norm(A, axis=-1, keepdims=True) + 1e-12
    return (A / n).astype(_np.float32)

def _norm_colbert_blocks(blocks):
    # blocks: list[np.ndarray (T_i, d)] | list[list[list[float]]]
    return [ _l2norm_rows_np(b).tolist() for b in blocks ]

# --- pass a larger, controlled batch size to the underlying model (uses your MAX_BATCH) ---
def _encode_any(model: BGEM3FlagModel, texts: List[str], max_length: int,
                want_dense: bool, want_sparse: bool, want_colbert: bool) -> Dict[str, Any]:
    out = model.encode(
        texts,
        batch_size=min(len(texts), MAX_BATCH),   # was hard-coded 64; now honors BGE_MAX_BATCH
        max_length=int(max_length),
        return_dense=want_dense,
        return_sparse=want_sparse,
        return_colbert_vecs=want_colbert,
    )
    resp: Dict[str, Any] = {}
    if want_dense:
        vecs = out.get("dense_vecs", [])
        # optional server-side L2 normalization for cosine/IP parity
        if NORMALIZE_DENSE and len(vecs):
            vecs = _l2norm_rows_np(vecs).tolist()
        resp["vecs"] = [v if isinstance(v, list) else v.tolist() for v in vecs]

    if want_sparse:
        lw_all = []
        for d in out.get("lexical_weights", []):
            lw_all.append({str(k): float(v) for k, v in d.items()})
        resp["lexical_weights"] = lw_all

    if want_colbert:
        cvs = out.get("colbert_vecs", [])
        # optional per-token L2 norm for ColBERT MaxSim
        if NORMALIZE_COLBERT and len(cvs):
            cvs = _norm_colbert_blocks(cvs)
        else:
            cvs = [m.tolist() if hasattr(m, "tolist") else m for m in cvs]
        resp["colbert_vecs"] = cvs
    return resp

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
# --- tiny warmup endpoint to trigger model load & compile kernels ---
@app.post("/warmup")
def warmup():
    m = get_model()
    _ = _encode_any(m, ["hola"], MAX_LENGTH_QUERY, True, False, False)
    return {"ok": True}

@app.get("/health")
def health():
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        dev = torch.cuda.get_device_name(0) if cuda_ok else "cpu"
    except Exception:
        cuda_ok = False
        dev = "cpu"
    return {"ok": True, "device": dev, "cuda": cuda_ok, "model": DEFAULT_MODEL}

@app.get("/info")
def info():
    return {
        "model": DEFAULT_MODEL,
        "fp16": USE_FP16,
        "max_batch": MAX_BATCH,
        "max_text_len": MAX_TEXT_LEN,
        "defaults": {
            "max_length_query": MAX_LENGTH_QUERY,
            "max_length_doc": MAX_LENGTH_DOC,
        }
    }

# --- in /encode & /encode_batch, pass the mode to _decide_flags and keep other logic as-is ---
@app.post("/encode")
def encode(req: EncodeRequest):
    model = get_model()
    want_dense, want_sparse, want_colbert = _decide_flags(req, req.mode)
    max_len = int(req.max_length or (MAX_LENGTH_DOC if want_colbert else MAX_LENGTH_QUERY))
    resp = _encode_any(model, [req.text], max_len, want_dense, want_sparse, want_colbert)
    resp["mode"] = "dense" if want_dense and not (want_sparse or want_colbert) else "mixed"
    if "vecs" in resp and len(resp["vecs"]) == 1:
        resp["vec"] = resp["vecs"][0]; del resp["vecs"]
    if "lexical_weights" in resp and len(resp["lexical_weights"]) == 1:
        resp["lexical_weights"] = resp["lexical_weights"][0]
    if "colbert_vecs" in resp and len(resp["colbert_vecs"]) == 1:
        resp["colbert_vecs"] = resp["colbert_vecs"][0]
    return resp

@app.post("/encode_batch")
def encode_batch(req: EncodeBatchRequest):
    model = get_model()
    want_dense, want_sparse, want_colbert = _decide_flags(req, req.mode)
    # keep your heuristic; prefer long limit for colbert/doc
    max_len = int(req.max_length or (MAX_LENGTH_DOC if want_colbert else MAX_LENGTH_DOC if req.mode=="dense" else MAX_LENGTH_QUERY))
    resp = _encode_any(model, req.texts, max_len, want_dense, want_sparse, want_colbert)
    resp["mode"] = "dense" if want_dense and not (want_sparse or want_colbert) else "mixed"
    return resp

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

