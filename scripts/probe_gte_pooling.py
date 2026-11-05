#!/usr/bin/env python3
"""Mide cuanto del 1,3 % de GTE es el modelo y cuanto la configuracion.

`gte-multilingual-base` exige `trust_remote_code`, que sentence-transformers
2.2.2 no admite. Tanto el constructor de indice como el recuperador caen
entonces a un camino alternativo con AutoModel y *mean pooling*, mientras que el
modelo esta disenado para *CLS pooling*. A eso se suma que se le aplicaron los
prefijos "query: " / "passage: " del estilo E5, que nunca vio en entrenamiento.

El manuscrito atribuye el resultado a la dificultad del dominio (L1109). Antes de
mantener esa lectura hay que separar las dos hipotesis, y la unica forma es
medirlo: se codifica el corpus con las cuatro combinaciones de (pooling, prefijo)
y se compara Acc@1 sobre la misma muestra de consultas.

Se ejecuta dentro del contenedor:
    docker exec jupyter-pytorch python /work/scripts/probe_gte_pooling.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from transformers import AutoModel, AutoTokenizer

MODEL = "Alibaba-NLP/gte-multilingual-base"
SHORT = Path("/work/data/processed/OEB_short_feats.parquet")
LONG = Path("/work/data/processed/OEB_long_feats.parquet")
SAMPLE = Path("/work/benchmark/query_samples/OEB_query_sample_test_16590.json")
OUT = Path("/work/eval/gte_pooling/probe.json")

TEXT_COL = "text_norm"


def l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.clip(n, 1e-12, None)


@torch.inference_mode()
def encode(texts: list[str], tok, mdl, device: str, batch: int, max_len: int):
    """Devuelve (mean_pooled, cls_pooled) de una sola pasada por el modelo."""
    means, clss = [], []
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        enc = tok(chunk, padding=True, truncation=True, max_length=max_len, return_tensors="pt")
        enc = {k: v.to(device) for k, v in enc.items()}
        out = mdl(**enc).last_hidden_state
        mask = enc["attention_mask"].unsqueeze(-1)
        means.append(((out * mask).sum(1) / mask.sum(1).clamp(min=1)).float().cpu().numpy())
        clss.append(out[:, 0].float().cpu().numpy())
        if (i // batch) % 20 == 0:
            print(f"    {i + len(chunk):,}/{len(texts):,}", flush=True)
    return np.vstack(means), np.vstack(clss)


def acc_at_1(Q: np.ndarray, D: np.ndarray, gold_idx: np.ndarray, block: int = 512) -> float:
    """Acc@1 por producto escalar, por bloques para no agotar la memoria."""
    hits = 0
    for i in range(0, len(Q), block):
        scores = Q[i : i + block] @ D.T
        hits += int((scores.argmax(axis=1) == gold_idx[i : i + block]).sum())
    return hits / len(Q)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queries", type=int, default=2000, help="consultas de la muestra")
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--max-length", type=int, default=512)
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={device}  modelo={MODEL}")

    tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
    mdl = AutoModel.from_pretrained(MODEL, trust_remote_code=True).to(device).eval()

    short = pd.read_parquet(SHORT, columns=["item_key", TEXT_COL])
    long = pd.read_parquet(LONG, columns=["item_key", TEXT_COL])

    wanted = set(json.loads(SAMPLE.read_text(encoding="utf-8"))["query_item_keys"])
    q = short[short.item_key.isin(wanted)].sort_values("item_key").reset_index(drop=True)
    q = q.head(args.queries)

    long = long.sort_values("item_key").reset_index(drop=True)
    doc_pos = {k: i for i, k in enumerate(long.item_key)}
    gold = np.array([doc_pos[k] for k in q.item_key], dtype=np.int64)

    print(f"consultas={len(q):,}  documentos={len(long):,}")

    results: dict[str, float] = {}
    for use_prefix in (True, False):
        qp, dp = ("query: ", "passage: ") if use_prefix else ("", "")
        tag = "con prefijos E5" if use_prefix else "sin prefijos"
        print(f"\n=== {tag} ===")

        print("  documentos ...")
        d_mean, d_cls = encode(
            [dp + t for t in long[TEXT_COL].astype(str)], tok, mdl, device, args.batch, args.max_length
        )
        print("  consultas ...")
        q_mean, q_cls = encode(
            [qp + t for t in q[TEXT_COL].astype(str)], tok, mdl, device, args.batch, args.max_length
        )

        for pooling, (Q, D) in {"mean": (q_mean, d_mean), "cls": (q_cls, d_cls)}.items():
            score = acc_at_1(l2(Q), l2(D), gold)
            key = f"{pooling}__{'prefix' if use_prefix else 'noprefix'}"
            results[key] = score
            print(f"  Acc@1  pooling={pooling:4s} {tag:16s} = {score:.4f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"model": MODEL, "n_queries": len(q), "n_docs": len(long), "acc@1": results},
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nResumen (Acc@1 a nivel de item):")
    for key, value in sorted(results.items(), key=lambda kv: -kv[1]):
        print(f"  {key:18s} {value:.4f}")
    published = results.get("mean__prefix")
    best = max(results.values())
    if published is not None:
        print(
            f"\nLa configuracion publicada (mean + prefijos) da {published:.4f}; "
            f"la mejor de las cuatro, {best:.4f}."
        )
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
