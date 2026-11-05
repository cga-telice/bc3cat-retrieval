#!/usr/bin/env python3
"""Cuantos items son indistinguibles para cada indice lexico, y que techo impone.

Despues de normalizar, todo el catalogo cabe en unos pocos cientos de tipos de
palabra. Con 47.513 items construidos a partir de ese vocabulario, hay parejas
--y tercetos-- cuyo vector BM25 es exactamente el mismo: para ese indice no son
dos documentos distintos, son el mismo documento dos veces.

Eso es un techo, no una tendencia. Si el objetivo de una consulta comparte vector
con otros m-1 documentos, el mejor Acc@1 alcanzable para esa consulta es 1/m,
porque el desempate es arbitrario. El techo de un indice es la media de 1/m sobre
la muestra.

Uso:  python scripts/probe_vector_collisions.py
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index"
RUNS = ROOT / "runs"
SAMPLE = ROOT / "benchmark" / "query_samples" / "OEB_query_sample_test_16590.json"

DEFAULT = [
    "bm25_unigram",
    "bm25_unigram_params__k1-0.60__b-0.35",
    "bm25_unibigram__k1-0.80__b-0.35",
]


def measured_acc1(index_name: str) -> float | None:
    """Acc@1 del run correspondiente, para contrastar con el techo."""
    path = RUNS / index_name / "metrics_dual.json"
    if not path.exists():
        return None
    for record in json.loads(path.read_text(encoding="utf-8")):
        if record.get("scope") == "overall" and record.get("target") == "item":
            return record["Acc@1"]
    return None


def collisions(index_name: str, sample: list[str]) -> dict:
    index_dir = INDEX / index_name
    matrix = sparse.load_npz(index_dir / "data" / "bm25_docs.npz").tocsr()
    external = [json.loads(line)["external_id"]
                for line in (index_dir / "mapping.jsonl").open(encoding="utf-8")]

    # La firma es (columnas, pesos redondeados): dos filas con la misma firma son
    # el mismo punto del espacio, no dos puntos proximos.
    groups: dict[tuple, list[int]] = collections.defaultdict(list)
    for row in range(matrix.shape[0]):
        start, end = matrix.indptr[row], matrix.indptr[row + 1]
        key = (matrix.indices[start:end].tobytes(),
               np.round(matrix.data[start:end], 6).tobytes())
        groups[key].append(row)

    size = {external[row]: len(rows) for rows in groups.values() for row in rows}
    sizes = [size.get(key, 1) for key in sample]
    duplicated = [g for g in groups.values() if len(g) > 1]

    return {
        "vocabulary": int(matrix.shape[1]),
        "documents": int(matrix.shape[0]),
        "duplicate_groups": len(duplicated),
        "duplicate_documents": sum(len(g) for g in duplicated),
        "affected_queries": sum(1 for s in sizes if s > 1),
        "affected_share": sum(1 for s in sizes if s > 1) / len(sizes),
        "acc1_ceiling": sum(1.0 / s for s in sizes) / len(sizes),
        "acc1_measured": measured_acc1(index_name),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("indexes", nargs="*", default=DEFAULT)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "eval" / "collisions" / "collisions.json")
    args = parser.parse_args()

    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))["query_item_keys"]
    print(f"{len(sample):,} consultas de la muestra canonica\n")

    out = {}
    for name in args.indexes:
        stats = collisions(name, sample)
        out[name] = stats
        measured = stats["acc1_measured"]
        gap = (f"  medido {measured:.4f} ({100*(stats['acc1_ceiling']-measured):+.1f} pp del techo)"
               if measured is not None else "")
        print(
            f"{name:44s} vocab={stats['vocabulary']:5d}  "
            f"grupos={stats['duplicate_groups']:5d}  docs={stats['duplicate_documents']:5d}  "
            f"consultas afectadas={100*stats['affected_share']:5.2f}%  "
            f"techo={stats['acc1_ceiling']:.4f}{gap}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"queries": len(sample), "indexes": out},
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
