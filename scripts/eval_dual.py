#!/usr/bin/env python3
"""Evalúa un run a nivel de ítem y de padre directamente desde sus resultados.

`src/metrics.ipynb` exige que el run declare un `index_path` en su metadatos, algo
que las fusiones no tienen porque no proceden de un índice único. Por eso el
manuscrito reporta «n/a» en el nivel de padre para las familias híbrida y de
reranking (Fig. acc1_by_family), y por eso la disociación ítem/padre —que es su
hallazgo central— no podía comprobarse justo en los sistemas que combinan ambos
mundos.

Este evaluador sólo necesita el fichero de resultados: el padre es el prefijo de
seis caracteres del identificador, la misma regla que usa el resto del estudio.

Uso:
    python scripts/eval_dual.py runs/hybrids/hyb_bm25_uni__bge_colbert__tfidf_char_3_5
    python scripts/eval_dual.py runs/hybrids/* --write
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

PARENT_LEN = 6
KS = (1, 5, 10)


def parent_of(item_key: str) -> str:
    return item_key[:PARENT_LEN]


def load_ranking(path: Path) -> dict[str, list[str]]:
    """query_item_key -> lista de doc_item_key en orden de ranking."""
    ranking: dict[str, list[str]] = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            q = rec.get("query_item_key") or rec.get("query_id")
            docs = rec.get("candidates") or rec.get("docs") or rec.get("results")
            if docs is None:
                continue
            keys = []
            for d in docs:
                if isinstance(d, dict):
                    # Los distintos runners nombran esta clave de forma distinta.
                    keys.append(
                        d.get("index_item_key")
                        or d.get("doc_item_key")
                        or d.get("doc_id")
                        or d.get("id")
                    )
                else:
                    keys.append(d)
            ranking[q] = [k for k in keys if k is not None]
    return ranking


def metrics(ranking: dict[str, list[str]], target: str) -> dict[str, float]:
    n = len(ranking)
    if n == 0:
        return {}
    acc1 = rec5 = rec10 = rr = 0.0
    for q, docs in ranking.items():
        gold = q if target == "item" else parent_of(q)
        pos = None
        for i, d in enumerate(docs[: max(KS)], start=1):
            if (d if target == "item" else parent_of(d)) == gold:
                pos = i
                break
        if pos is None:
            continue
        if pos == 1:
            acc1 += 1
        if pos <= 5:
            rec5 += 1
        if pos <= 10:
            rec10 += 1
        rr += 1.0 / pos
    return {
        "queries": n,
        "Acc@1": acc1 / n,
        "Recall@5": rec5 / n,
        "Recall@10": rec10 / n,
        "MRR@10": rr / n,
    }


def results_file(run_dir: Path) -> Path | None:
    for name in ("results_top100.jsonl.gz", "results_top50.jsonl.gz"):
        if (run_dir / name).exists():
            return run_dir / name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--write", action="store_true", help="escribe metrics_dual_parent.json")
    args = parser.parse_args()

    fallos = 0
    for run_dir in args.runs:
        path = results_file(run_dir)
        if path is None:
            print(f"{run_dir}: sin fichero de resultados", file=sys.stderr)
            fallos += 1
            continue

        ranking = load_ranking(path)
        if not ranking:
            print(f"{run_dir}: no se pudo interpretar {path.name}", file=sys.stderr)
            fallos += 1
            continue

        salida = {t: metrics(ranking, t) for t in ("item", "parent")}
        item, parent = salida["item"], salida["parent"]
        gap = 100 * (parent["Acc@1"] - item["Acc@1"])
        print(
            f"{run_dir.name[:46]:48s} n={item['queries']:,}  "
            f"item={item['Acc@1']:.4f}  padre={parent['Acc@1']:.4f}  brecha={gap:5.1f}p"
        )

        if args.write:
            (run_dir / "metrics_dual_parent.json").write_text(
                json.dumps(salida, indent=2), encoding="utf-8"
            )

    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
