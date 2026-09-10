#!/usr/bin/env python3
"""Persiste la fusión óptima del barrido como fichero de resultados del run.

`hybrid.ipynb` guarda dos cosas distintas bajo el mismo directorio: el ranking de
una fusión COMBSUM sin pesos, en `results_top100.jsonl.gz`, y la configuración
ponderada que el barrido eligió, en `fused_best_from_sweep.parquet`. Como todo lo
que consume un run lee el primero —el cross-encoder, el análisis de errores, la
auditoría de muestras— acababan aplicándose a un sistema distinto del que las
tablas reportan. El manuscrito publicado tiene exactamente ese defecto: la fila
«baseline» de la tabla de reranking venía de una fusión y las filas reranqueadas
de otra.

Este script exporta la fusión óptima al formato de resultados, sin repetir la
recuperación, de modo que el run tenga un único ranking y sea el que se reporta.

Uso:
    python scripts/export_best_fusion.py runs/hybrids/*  [--force]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

TOPK = 100
OUT_NAME = f"results_top{TOPK}.jsonl.gz"
BACKUP_NAME = f"results_top{TOPK}__unweighted_combsum.jsonl.gz"


def export(run_dir: Path, force: bool) -> bool:
    parquet = run_dir / "fused_best_from_sweep.parquet"
    sweep = run_dir / "best_from_sweep.json"
    if not parquet.exists() or not sweep.exists():
        print(f"{run_dir.name}: sin barrido persistido", file=sys.stderr)
        return False

    meta_sweep = json.loads(sweep.read_text(encoding="utf-8"))
    destino = run_dir / OUT_NAME
    respaldo = run_dir / BACKUP_NAME

    if respaldo.exists() and not force:
        print(f"{run_dir.name}: ya exportado")
        return True

    # El ranking COMBSUM sin pesos se conserva: es lo que se publicó.
    if destino.exists() and not respaldo.exists():
        destino.rename(respaldo)

    df = pd.read_parquet(parquet, columns=["query_id", "doc_id", "fused_score", "rank"])
    df = df[df["rank"] <= TOPK].sort_values(["query_id", "rank"])

    meta = {
        "fusion": "weighted",
        "weights": meta_sweep["weights"],
        "numeric_bonus": {
            "beta_exact": meta_sweep["beta_exact"],
            "beta_overlap": meta_sweep["beta_overlap"],
        },
        "final_topK": TOPK,
        "source": "fused_best_from_sweep.parquet",
        "note": "configuracion elegida por el barrido; el COMBSUM sin pesos queda en "
        + BACKUP_NAME,
    }

    n = 0
    with gzip.open(destino, "wt", encoding="utf-8") as fh:
        for query_id, grupo in df.groupby("query_id", sort=True):
            registro = {
                "meta": meta,
                "query_id": query_id,
                "query_item_key": query_id,
                "candidates": [
                    {
                        "rank": int(r.rank),
                        "index_item_key": r.doc_id,
                        "score": float(r.fused_score),
                    }
                    for r in grupo.itertuples(index=False)
                ],
            }
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
            n += 1

    print(f"{run_dir.name}: {n:,} consultas -> {destino.name}  (acc@1 declarado {meta_sweep['metrics']['acc@1']:.4f})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    fallos = sum(0 if export(Path(r), args.force) else 1 for r in args.runs)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
