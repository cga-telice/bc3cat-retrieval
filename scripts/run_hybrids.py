#!/usr/bin/env python3
"""Reejecuta las fusiones híbridas sobre la muestra canónica de consultas.

Los cuatro híbridos publicados evaluaron un conjunto de consultas que sólo
comparte 5.844 de 16.590 con el de BM25, porque `hybrid.ipynb` re-muestreaba con
un criterio distinto al de `retrieve.ipynb`. Además el bonus numérico que el
manuscrito describe como componente de diseño era código muerto.

Corregido lo uno y lo otro, hay que rehacer las cuatro fusiones. Se ejecuta
dentro del contenedor:

    docker exec jupyter-pytorch python /work/scripts/run_hybrids.py
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

WORK = Path("/work")
NOTEBOOK = WORK / "src" / "hybrid.ipynb"
LOGS = WORK / "logs"

SAMPLES = {
    "test": "/work/benchmark/query_samples/OEB_query_sample_test_16590.json",
    "val": "/work/benchmark/query_samples/OEB_query_sample_val_5000.json",
}

# Las cuatro fusiones del manuscrito. Las tres primeras combinan BM25, TF-IDF de
# caracteres y una variante de BGE-M3; la cuarta usa las tres a la vez.
HYBRIDS = {
    "hyb_bm25_uni__bge_colbert__tfidf_char_3_5": [
        "bm25_unigram", "bge_m3_colbert", "tfidf_char_3_5",
    ],
    "hyb_bm25_uni__bge_dense__tfidf_char_3_5": [
        "bm25_unigram", "bge_m3_dense", "tfidf_char_3_5",
    ],
    "hyb_bm25_uni__bge_sparse__tfidf_char_3_5": [
        "bm25_unigram", "bge_m3_sparse", "tfidf_char_3_5",
    ],
    "hyb_bm25_uni__bge_multi__tfidf_char_3_5": [
        "bm25_unigram", "bge_m3_colbert", "bge_m3_dense", "bge_m3_sparse", "tfidf_char_3_5",
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="*", default=None, help="nombres de fusión; vacío = todas")
    parser.add_argument("--split", choices=sorted(SAMPLES), default="test")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not WORK.exists():
        print(
            "Ejecútalo dentro del contenedor:\n"
            "    docker exec jupyter-pytorch python /work/scripts/run_hybrids.py",
            file=sys.stderr,
        )
        return 1

    import os

    import papermill as pm

    # hybrid.ipynb importa los recuperadores por nombre de modulo.
    src = str(WORK / "src")
    existing = os.environ.get("PYTHONPATH", "")
    if src not in existing.split(os.pathsep):
        os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [src, existing]))

    seleccion = args.runs or list(HYBRIDS)
    desconocidos = [r for r in seleccion if r not in HYBRIDS]
    if desconocidos:
        print(f"Fusiones desconocidas: {', '.join(desconocidos)}", file=sys.stderr)
        print(f"Disponibles: {', '.join(HYBRIDS)}", file=sys.stderr)
        return 1

    LOGS.mkdir(parents=True, exist_ok=True)
    failures = 0

    for name in seleccion:
        indexes = HYBRIDS[name]
        print(f"\n=== {name}  [{args.split}] ===")
        print(f"    índices: {', '.join(indexes)}")
        if args.dry_run:
            continue

        started = time.time()
        try:
            pm.execute_notebook(
                input_path=str(NOTEBOOK),
                output_path=str(LOGS / f"hybrid__{name}__{args.split}.ipynb"),
                parameters={
                    "HYBRID_RUN": name,
                    "HYBRID_INDEXES": list(indexes),
                    "QUERY_SAMPLE": SAMPLES[args.split],
                },
                cwd=str(WORK),
            )
        except Exception as exc:
            print(f"[FALLO] {name}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failures += 1
            continue

        print(f"[OK] {name} en {time.time() - started:.0f}s")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
