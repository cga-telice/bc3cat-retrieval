from __future__ import annotations
import os, time
from typing import List, Literal, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

# Lazy import so startup is quick; model loads on first access
from FlagEmbedding import BGEM3FlagModel

APP_NAME = "bge-m3-api"
DEFAULT_MODEL = os.getenv("BGE_MODEL", "BAAI/bge-m3")
USE_FP16 = os.getenv("BGE_USE_FP16", "true").lower() in {"1", "true", "yes", "y"}
MAX_BATCH = int(os.getenv("BGE_MAX_BATCH", "256"))
MAX_TEXT_LEN = int(os.getenv("BGE_MAX_TEXT_LEN", "20000"))  # chars, non-binding safeguard
MAX_LENGTH_QUERY = int(os.getenv("BGE_MAX_LENGTH_QUERY", "256"))
MAX_LENGTH_DOC = int(os.getenv("BGE_MAX_LENGTH_DOC", "2048"))

ENABLE_CORS = os.getenv("BGE_ENABLE_CORS", "false").lower() in {"1","true","yes"}
ALLOWED_ORIGINS = os.getenv("BGE_CORS_ORIGINS", "").split(",") if ENABLE_CORS else []

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
Mode = Literal["dense", "sparse"]  # add "colbert" later

class EncodeRequest(BaseModel):
    text: str = Field(..., description="Single input text")
    mode: Mode = Field("dense", description="dense|sparse")
    max_length: Optional[int] = Field(None, description="Token max_length override")

    @validator("text")
    def _chk_text(cls, v: str):
        if not isinstance(v, str) or not v.strip():
            raise ValueError("text must be a non-empty string")
        if len(v) > MAX_TEXT_LEN:
            raise ValueError(f"text too long (> {MAX_TEXT_LEN} chars)")
        return v

class EncodeBatchRequest(BaseModel):
    texts: List[str] = Field(..., description="Batch of texts")
    mode: Mode = Field("dense", description="dense|sparse")
    max_length: Optional[int] = Field(None, description="Token max_length override (applies to all)")

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
def _encode_dense(model: BGEM3FlagModel, texts: List[str], max_length: int) -> List[List[float]]:
    out = model.encode(
        texts, batch_size=min(len(texts), 64), max_length=max_length,
        return_dense=True, return_sparse=False, return_colbert_vecs=False
    )
    # list[list[float]] for JSON friendliness
    return [vec.tolist() for vec in out["dense_vecs"]]

def _encode_sparse(model: BGEM3FlagModel, texts: List[str], max_length: int) -> List[Dict[str, float]]:
    out = model.encode(
        texts, batch_size=min(len(texts), 64), max_length=max_length,
        return_dense=False, return_sparse=True, return_colbert_vecs=False
    )
    # returns list[dict token_id -> weight] (keys are token ids as strings per FlagEmbedding)
    # We ensure keys are str for JSON
    result = []
    for d in out["lexical_weights"]:
        result.append({str(k): float(v) for k, v in d.items()})
    return result

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
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

@app.post("/encode")
def encode(req: EncodeRequest):
    model = get_model()
    max_len = int(req.max_length or (MAX_LENGTH_QUERY if req.mode == "dense" else MAX_LENGTH_QUERY))
    if req.mode == "dense":
        vec = _encode_dense(model, [req.text], max_len)[0]
        return {"mode": "dense", "vec": vec}
    elif req.mode == "sparse":
        lw = _encode_sparse(model, [req.text], max_len)[0]
        return {"mode": "sparse", "lexical_weights": lw}
    else:
        raise HTTPException(400, "unsupported mode")

@app.post("/encode_batch")
def encode_batch(req: EncodeBatchRequest):
    model = get_model()
    max_len = int(req.max_length or (MAX_LENGTH_DOC if req.mode == "dense" else MAX_LENGTH_QUERY))
    if req.mode == "dense":
        vecs = _encode_dense(model, req.texts, max_len)
        return {"mode": "dense", "vecs": vecs}
    elif req.mode == "sparse":
        lws = _encode_sparse(model, req.texts, max_len)
        return {"mode": "sparse", "lexical_weights": lws}
    else:
        raise HTTPException(400, "unsupported mode")

# ---- Stubs to add later (multi-vector / ColBERT) ----
# from FlagEmbedding you can return_colbert_vecs=True and expose:
# @app.post("/encode_colbert") ...
# and/or a /score endpoint using model.colbert_score for query/doc pairs.

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # no ssl_keyfile, no ssl_certfile
