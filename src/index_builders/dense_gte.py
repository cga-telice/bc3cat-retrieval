# /work/src/index_builders/dense_gte.py

"""
Dense index builder for GTE (multilingual) with robust loader:

- Tries SentenceTransformer first.
- If ST cannot load (e.g., needs `trust_remote_code` not supported by ST version),
  falls back to HuggingFace Transformers (AutoTokenizer/AutoModel) with
  mean pooling + L2 normalization.

YAML params (cfg['method']['params']):
  model_name: "Alibaba-NLP/gte-multilingual-base"
  batch_size: 256
  max_length: 512
  normalize: true
  add_doc_prefix: true
  doc_prefix: "passage: "
  add_query_prefix: true            # stored in meta (applied at retrieval time)
  query_prefix: "query: "
  trust_remote_code: true           # consumed by HF fallback; recorded in meta
  device: ""                        # optional torch device, e.g., "cuda"

Artifacts:
  /index/<save_as>/
    meta.json, fields.json, mapping.jsonl, data/dense_docs.npy
"""
from typing import Dict, Any, List, Callable
import time, hashlib, numpy as np, pandas as pd


def _sha256_sample(texts, cap=1000) -> str:
    h = hashlib.sha256()
    n = len(texts)
    if n == 0: return "sha256:0"
    step = max(1, n // min(n, cap))
    for i in range(0, n, step):
        t = texts[i]
        if t is None: t = ""
        h.update(str(t).encode("utf-8"))
    return "sha256:" + h.hexdigest()

def select_field(feats_meta: Dict[str, Any]) -> str:
    return "text"

def _pick_external_ids(df: pd.DataFrame) -> List[str]:
    if "item_key" in df.columns:
        return df["item_key"].astype(str).tolist()
    for c in ("id","external_id"):
        if c in df.columns:
            return df[c].astype(str).tolist()
    return [str(i) for i in range(len(df))]

def _build_encoder(model_name: str, max_length: int, trust_remote: bool, device: str | None = None):
    """Returns (encode_fn, meta_backend)."""
    try:
        from sentence_transformers import SentenceTransformer
        st_model = SentenceTransformer(model_name, device=device if device else None)
        st_model.max_seq_length = max_length
        
        def st_encode(texts: List[str], bs: int = 256) -> np.ndarray:
            E = st_model.encode(
                texts,
                batch_size=bs,                # <- honor batch size
                convert_to_numpy=True,
                normalize_embeddings=False,
                show_progress_bar=False,
            ).astype("float32", copy=False)
            return E
        
        return st_encode, {"backend": "sentence-transformers", "device": str(st_model.device)}
    except Exception as e:
        import torch
        from transformers import AutoTokenizer, AutoModel

        # Choose device explicitly if not provided
        use_device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Use fp16 on GPU for speed & memory (safe for GTE encoders)
        torch_dtype = torch.float16 if use_device.startswith("cuda") else torch.float32
        
        tok = AutoTokenizer.from_pretrained(model_name, trust_remote_code=trust_remote)
        mdl = AutoModel.from_pretrained(model_name, trust_remote_code=trust_remote)
        if device:
            mdl = mdl.to(device)
        mdl.eval()

        @torch.inference_mode()
        def hf_encode(texts: List[str], bs: int = 256) -> np.ndarray:
            outs = []
            for i in range(0, len(texts), bs):
                batch = texts[i:i+bs]
                enc = tok(batch, padding=True, truncation=True, max_length=max_length, return_tensors="pt")
                enc = {k: v.to(use_device, non_blocking=True) for k, v in enc.items()}
                out = mdl(**enc)
                last = out.last_hidden_state
                mask = enc["attention_mask"].unsqueeze(-1)
                mean = (last * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                outs.append(mean.detach().float().cpu().numpy())  # ensure float32 on output
            hidden = mdl.config.hidden_size
            return np.vstack(outs) if outs else np.zeros((0, hidden), dtype="float32")

        return hf_encode, {"backend": "hf-transformers", "device": use_device, "torch_dtype": str(torch_dtype)}

def build(cfg: Dict[str, Any], long_df: pd.DataFrame, text_field: str):
    p = (cfg.get("method") or {}).get("params") or {}
    model_name   = p.get("model_name", "Alibaba-NLP/gte-multilingual-base")
    batch_size   = int(p.get("batch_size", 256))
    max_length   = int(p.get("max_length", 512))
    normalize    = bool(p.get("normalize", True))
    add_doc_pref = bool(p.get("add_doc_prefix", True))
    doc_prefix   = str(p.get("doc_prefix", "passage: "))
    trust_remote = bool(p.get("trust_remote_code", True))
    device       = p.get("device") or None

    encode_fn, backend_meta = _build_encoder(model_name, max_length, trust_remote, device=device)

    corpus = long_df[text_field].fillna("").astype(str).tolist()
    if add_doc_pref and doc_prefix:
        corpus = [f"{doc_prefix}{t}" for t in corpus]
    ext_ids = _pick_external_ids(long_df)

    t0 = time.time()
    embs_list = []
    for i in range(0, len(corpus), batch_size):
        batch = corpus[i:i+batch_size]
        # pass batch_size through so ST/HF can use it internally
        E = encode_fn(batch, bs=batch_size)
        embs_list.append(E)
    E_docs = np.vstack(embs_list) if embs_list else np.zeros((0, 768), dtype="float32")
    if normalize and E_docs.size:
        n = np.linalg.norm(E_docs, axis=1, keepdims=True); n[n==0]=1.0
        E_docs = E_docs / n

    secs = time.time() - t0
    print(
        f"[dense_gte] backend={backend_meta.get('backend')} "
        f"| device={backend_meta.get('device')} "
        f"| bs={batch_size} | docs={E_docs.shape[0]} | dim={E_docs.shape[1] if E_docs.size else 0} "
        f"| time={secs:.2f}s"
    )

    artifacts = {
        "embeddings.npy": E_docs,
        "meta.json": {
            "method": "dense",
            "variant": "dense_gte",
            "params": {
                "model_name": model_name,
                "batch_size": batch_size,
                "max_length": max_length,
                "normalize": normalize,
                "add_doc_prefix": add_doc_pref,
                "doc_prefix": doc_prefix,
                "add_query_prefix": p.get("add_query_prefix", True),
                "query_prefix": p.get("query_prefix", "query: "),
                "trust_remote_code": trust_remote,
                "device": device,
                **backend_meta,
            },
            "dim": int(E_docs.shape[1]) if E_docs.size else 0,
            "__num_docs__": int(E_docs.shape[0]),
            "__corpus_hash__": _sha256_sample(corpus),
        },
        "fields.json": {"text_field": text_field},
        "mapping.jsonl": [
            {"doc_id": int(i), "external_id": ext_ids[i]} for i in range(len(ext_ids))
        ],
    }
    return artifacts, None, E_docs
