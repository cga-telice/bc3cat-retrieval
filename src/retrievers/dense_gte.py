# /work/src/retrievers/dense_gte.py

"""
Dense retriever for GTE (multilingual) with robust loader (ST -> HF fallback).
Reads: meta.json / fields.json / mapping.jsonl / data/dense_docs.npy
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple
import json, numpy as np

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
    if len(doc_ids) and not (doc_ids.min() == 0 and doc_ids.max() == len(doc_ids)-1):
        raise ValueError("mapping.jsonl doc_id must be contiguous 0..N-1")
    return doc_ids, ext_ids

def _l2norm(X: np.ndarray, axis=1, eps: float = 1e-8) -> np.ndarray:
    n = np.linalg.norm(X, axis=axis, keepdims=True)
    n = np.maximum(n, eps)
    return X / n

#: Query rows scored per block (S3). Mirrors retrievers.dense_e5: the score block is B x N, and
#: the 35,422 OE dev identity queries in one block are ~9.3 GiB in float32.
DEFAULT_BATCH_SIZE = 2048
_USE_DEFAULT = object()


class DenseGTESearcher:
    def __init__(self, index_dir: Path):
        index_dir = Path(index_dir)
        data_dir  = index_dir / "data"
        self.meta    = _read_json(index_dir / "meta.json")
        self.fields  = _read_json(index_dir / "fields.json")
        self.doc_ids, self.external_ids = _load_mapping(index_dir / "mapping.jsonl")
        self.X_docs = np.load(data_dir / "embeddings.npy").astype(np.float32, copy=False)
        self.X_docs = _l2norm(self.X_docs, axis=1) if self.X_docs.size else self.X_docs

        p = self.meta.get("params", {})
        self.model_name      = p.get("model_name", "Alibaba-NLP/gte-multilingual-base")
        self.add_query_pref  = bool(p.get("add_query_prefix", True))
        self.query_prefix    = str(p.get("query_prefix", "query: "))
        self.max_length      = int(p.get("max_length", 256))
        self.trust_remote    = bool(p.get("trust_remote_code", True))
        self.device          = p.get("device") or None
        self.batch_size      = int(p.get("batch_size", 256))
        self.encode_fn = self._make_encoder()

    def _make_encoder(self):
        # Try ST first
        try:
            from sentence_transformers import SentenceTransformer
            # Be explicit about device if provided
            st_model = SentenceTransformer(self.model_name, device=self.device if self.device else None)
            st_model.max_seq_length = self.max_length
    
            def st_encode(texts: List[str], bs: int | None = None) -> np.ndarray:
                E = st_model.encode(
                    texts,
                    batch_size=bs or self.batch_size,     # honor batch size
                    convert_to_numpy=True,
                    normalize_embeddings=False,
                    show_progress_bar=False,
                )
                return E.astype("float32", copy=False)
    
            # quick log for sanity
            print(f"[dense_gte:retriever] backend=sentence-transformers | device={st_model.device} | bs={self.batch_size}")
            return st_encode
    
        except Exception:
            import torch
            from transformers import AutoTokenizer, AutoModel
    
            # Choose a device if not provided
            use_device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            # Use fp16 on GPU
            torch_dtype = torch.float16 if str(use_device).startswith("cuda") else torch.float32
    
            tok = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=self.trust_remote)
            mdl = AutoModel.from_pretrained(self.model_name, trust_remote_code=self.trust_remote, torch_dtype=torch_dtype)
            mdl = mdl.to(use_device)
            mdl.eval()
    
            # (Optional) enable TF32 for Ampere+ for extra speed
            if str(use_device).startswith("cuda"):
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
    
            @torch.inference_mode()
            def hf_encode(texts: List[str], bs: int | None = None) -> np.ndarray:
                bs = bs or self.batch_size
                outs = []
                for i in range(0, len(texts), bs):
                    batch = texts[i:i+bs]
                    enc = tok(batch, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
                    enc = {k: v.to(use_device, non_blocking=True) for k, v in enc.items()}
                    out = mdl(**enc)
                    last = out.last_hidden_state
                    mask = enc["attention_mask"].unsqueeze(-1)
                    mean = (last * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                    outs.append(mean.detach().float().cpu().numpy())   # float32 output
                hidden = mdl.config.hidden_size
                return np.vstack(outs) if outs else np.zeros((0, hidden), dtype="float32")
    
            print(f"[dense_gte:retriever] backend=hf-transformers | device={use_device} | dtype={torch_dtype} | bs={self.batch_size}")
            return hf_encode

    @staticmethod
    def _ensure_text(x):
        return x if isinstance(x, str) else ("" if x is None else str(x))

    def encode(self, texts: List[str]) -> np.ndarray:
        texts = [self._ensure_text(t) for t in texts]
        if self.add_query_pref and self.query_prefix:
            texts = [f"{self.query_prefix}{t}" for t in texts]
        Q = self.encode_fn(texts, bs=self.batch_size)
        Q = _l2norm(Q, axis=1)
        return Q

    def search(self, query_text: str, k: int = 100):
        Q = self.encode([query_text])
        sims = (Q @ self.X_docs.T).ravel()
        sims = np.nan_to_num(sims, copy=False)
        k = min(k, sims.shape[0])
        if k == 0:
            return np.empty((0,), dtype=np.int64), np.empty((0,), dtype=np.float32)
        part = np.argpartition(-sims, kth=k-1)[:k]
        order = np.argsort(-sims[part])
        top_idx = part[order]
        return top_idx, sims[top_idx]

    def search_batch(self, queries: List[str], k: int = 100, batch_size=_USE_DEFAULT):
        """Score `queries` in blocks of `batch_size` rows (S3); `None` means one block.

        A query's scores depend on no other query, so blocking changes memory, not results —
        see tests/test_retriever_batching.py. Added in S3 work item 6, after all ten runs of
        this arm at 35,422 dev queries died with DeadKernelError: the unblocked path builds a
        B x N dense score matrix, 9.3 GiB in float32 against ~20 GiB of container RAM. S1 had
        blocked bm25_unigram, dense_e5 and bge_m3_colbert — the three methods S2 needed — and
        this arm was simply never run at that scale before (defect H6).
        """
        if batch_size is _USE_DEFAULT:
            batch_size = DEFAULT_BATCH_SIZE
        if batch_size is not None and batch_size < 1:
            raise ValueError(f"batch_size must be a positive integer or None, got {batch_size!r}")
        queries = list(queries)
        if batch_size is None or batch_size >= len(queries):
            return self._search_block(queries, k)
        blocks = [
            self._search_block(queries[s : s + batch_size], k)
            for s in range(0, len(queries), batch_size)
        ]
        return (
            np.concatenate([i for i, _ in blocks], axis=0),
            np.concatenate([sc for _, sc in blocks], axis=0),
        )

    def _search_block(self, queries: List[str], k: int = 100):
        Q = self.encode(queries)
        sims = (Q @ self.X_docs.T)
        sims = np.nan_to_num(sims, copy=False)
        B, N = sims.shape
        k = min(k, N)
        part = np.argpartition(-sims, kth=k-1, axis=1)[:, :k]
        rows = np.arange(B)[:, None]
        order = np.argsort(-sims[rows, part], axis=1)
        top_idx = part[rows, order]
        top_sco = sims[rows, top_idx]
        return top_idx, top_sco

def load(index_dir: str | Path) -> DenseGTESearcher:
    return DenseGTESearcher(Path(index_dir))