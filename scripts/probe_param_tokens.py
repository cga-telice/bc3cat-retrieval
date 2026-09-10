#!/usr/bin/env python3
"""Separa lo que aporta el texto de lo que aporta la firma de parametros.

`bm25_unigram_params` indexa el campo `text_word_params`, que `src/data.ipynb`
construye asi:

    df["text_word_params"] = df["text_word"] + " " + " ".join(df["param_tokens"])
    df["param_tokens"]     = df["parameters_norm"].map(build_param_tokens)

Los `param_tokens` no salen del texto: salen del campo `parameters` del registro
del catalogo. Y como la consulta y el objetivo son el mismo item (el `resumen` y
el `texto` de la misma partida), la consulta llega con la **misma firma** que su
objetivo: identica en los 47.513 pares, y unica dentro de su plantilla en los
47.513 casos.

Esto no es una variante de tokenizacion, es meter la tupla de parametros
verdadera dentro de la consulta. Este script mide cuanto de la cifra publicada
depende de eso, comparando tres formulaciones de consulta sobre el mismo indice:

    published : text_word + firma   (lo que se publico)
    text_only : text_word           (lo que tendria una consulta real)
    signature : firma               (solo la clave, sin texto)

Se ejecuta DENTRO del contenedor:

    docker exec jupyter-pytorch python /work/scripts/probe_param_tokens.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path("/work") if Path("/work").exists() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "src"))

DATA = WORK / "data" / "processed"
INDEX = WORK / "index"
RUNS = WORK / "runs"
SAMPLE = WORK / "benchmark" / "query_samples" / "OEB_query_sample_test_16590.json"

PARENT_LEN = 6

FORMULATIONS = {
    "published": lambda row: row["text_word_params"],
    "text_only": lambda row: row["text_word"],
    "signature": lambda row: " ".join(row["param_tokens"]),
}


def evaluate(top_keys: np.ndarray, gold: list[str]) -> dict[str, float]:
    """Acc@1, Recall@5/@10 y MRR@10 a nivel de item y de padre."""
    gold_arr = np.asarray(gold, dtype=object)[:, None]
    hit = top_keys == gold_arr

    parent_top = np.vectorize(lambda k: k[:PARENT_LEN])(top_keys)
    parent_gold = np.asarray([g[:PARENT_LEN] for g in gold], dtype=object)[:, None]
    hit_parent = parent_top == parent_gold

    def block(h):
        rank = np.where(h.any(axis=1), h.argmax(axis=1) + 1, 0)
        rr = np.where((rank > 0) & (rank <= 10), 1.0 / np.maximum(rank, 1), 0.0)
        return {
            "Acc@1": float(h[:, 0].mean()),
            "Recall@5": float(h[:, :5].any(axis=1).mean()),
            "Recall@10": float(h[:, :10].any(axis=1).mean()),
            "MRR@10": float(rr.mean()),
        }

    return {"item": block(hit), "parent": block(hit_parent)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="bm25_unigram_params__k1-0.60__b-0.35")
    parser.add_argument("--k", type=int, default=100)
    parser.add_argument("--batch", type=int, default=2000)
    parser.add_argument("--save-runs", action="store_true",
                        help="persiste cada formulacion como un run comparable")
    parser.add_argument("--out", type=Path,
                        default=WORK / "eval" / "param_tokens" / "formulations.json")
    args = parser.parse_args()

    from retrievers.bm25_unigram_params import load  # noqa: E402

    short = pd.read_parquet(
        DATA / "OEB_short_norm.parquet",
        columns=["item_key", "text_word", "text_word_params", "param_tokens"],
    )
    wanted = set(json.loads(SAMPLE.read_text(encoding="utf-8"))["query_item_keys"])
    short = short[short["item_key"].isin(wanted)].sort_values("item_key").reset_index(drop=True)
    if len(short) != len(wanted):
        print(f"La muestra aporta {len(short)} de {len(wanted)} consultas", file=sys.stderr)
        return 1
    gold = short["item_key"].tolist()
    print(f"{len(gold):,} consultas, indice {args.index}")

    searcher = load(INDEX / args.index)
    ext = np.asarray(searcher.external_ids, dtype=object)

    summary = {}
    for name, build in FORMULATIONS.items():
        texts = [build(row) for _, row in short.iterrows()]
        empty = sum(1 for t in texts if not str(t).strip())
        tops, scores = [], []
        for start in range(0, len(texts), args.batch):
            idx, sc = searcher.search_batch(texts[start:start + args.batch], k=args.k)
            tops.append(idx)
            scores.append(sc)
            print(f"  {name}: {min(start + args.batch, len(texts)):,}/{len(texts):,}", end="\r")
        top_idx = np.vstack(tops)
        top_sc = np.vstack(scores)
        top_keys = ext[top_idx]

        metrics = evaluate(top_keys, gold)
        summary[name] = {"empty_queries": empty, **metrics}
        print(
            f"  {name:10s} item Acc@1={metrics['item']['Acc@1']:.4f} "
            f"R@5={metrics['item']['Recall@5']:.4f}  "
            f"parent Acc@1={metrics['parent']['Acc@1']:.4f}"
            + (f"   ({empty} consultas vacias)" if empty else "")
        )

        if args.save_runs:
            run_dir = RUNS / f"{args.index}__q-{name}"
            run_dir.mkdir(parents=True, exist_ok=True)
            path = run_dir / f"results_top{args.k}.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                for i, key in enumerate(gold):
                    fh.write(json.dumps({
                        "query_id": f"q_{i:06d}",
                        "query_item_key": key,
                        "query_text": texts[i],
                        "candidates": [
                            {"rank": r + 1, "doc_id": int(top_idx[i, r]),
                             "index_item_key": str(top_keys[i, r]),
                             "score": float(top_sc[i, r])}
                            for r in range(args.k)
                        ],
                        "score_info": {"family": "bm25", "higher_is_better": True},
                        "meta": {"method": "bm25", "variant": f"{args.index}__q-{name}",
                                 "index_path": str(INDEX / args.index),
                                 "query_formulation": name},
                    }, ensure_ascii=False) + "\n")
            print(f"    -> {path}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"index": args.index, "queries": len(gold),
                                    "formulations": summary}, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
