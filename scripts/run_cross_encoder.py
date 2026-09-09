#!/usr/bin/env python3
"""Aplica el cross-encoder a varios sistemas y profundidades de reranking.

El manuscrito declara haber evaluado profundidades de 20, 50 y 100 candidatos
(§3.2.4) y, en otro punto, que el reranking se aplicó «a los 100 mejores»
(§4.5). Sólo existe K' = 50. Corregir esa afirmación exige o rebajarla o
ejecutar las otras dos: esto último, además, permite responder si la
profundidad importa.

El notebook cachea las puntuaciones en `ce_cache/`, así que ejecutar primero
K'=100 hace que 50 y 20 salgan casi gratis: son subconjuntos de los mismos
pares.

Se ejecuta dentro del contenedor:
    docker exec jupyter-pytorch python /work/scripts/run_cross_encoder.py
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

WORK = Path("/work")
NOTEBOOK = WORK / "src" / "cross_encoder.ipynb"
LOGS = WORK / "logs"

# Los tres sistemas de primera etapa que el manuscrito reranquea.
SYSTEMS = {
    "bm25_unigram": "/work/runs/bm25_unigram",
    "bge_m3_colbert": "/work/runs/bge_m3_colbert",
    "hybrid_3way": "/work/runs/hybrids/hyb_bm25_uni__bge_colbert__tfidf_char_3_5",
}

# De mayor a menor: la caché de la primera pasada sirve a las siguientes.
DEPTHS = [100, 50, 20]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("systems", nargs="*", help="claves de sistema; vacío = todos")
    parser.add_argument("--depths", type=int, nargs="*", default=DEPTHS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not WORK.exists():
        print("Ejecútalo dentro del contenedor.", file=sys.stderr)
        return 1

    import os

    import papermill as pm

    src = str(WORK / "src")
    existing = os.environ.get("PYTHONPATH", "")
    if src not in existing.split(os.pathsep):
        os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [src, existing]))

    seleccion = args.systems or list(SYSTEMS)
    desconocidos = [s for s in seleccion if s not in SYSTEMS]
    if desconocidos:
        print(f"Sistemas desconocidos: {', '.join(desconocidos)}", file=sys.stderr)
        print(f"Disponibles: {', '.join(SYSTEMS)}", file=sys.stderr)
        return 1

    LOGS.mkdir(parents=True, exist_ok=True)
    failures = 0

    for system in seleccion:
        run_dir = Path(SYSTEMS[system])
        if not (run_dir / "results_top100.jsonl.gz").exists():
            print(f"[SKIP] {system}: no hay results_top100 en {run_dir}", file=sys.stderr)
            failures += 1
            continue

        for depth in args.depths:
            print(f"\n=== {system}  K'={depth} ===")
            print(f"    run: {run_dir}")
            if args.dry_run:
                continue

            started = time.time()
            try:
                pm.execute_notebook(
                    input_path=str(NOTEBOOK),
                    output_path=str(LOGS / f"ce__{system}__k{depth}.ipynb"),
                    parameters={
                        "INPUT_RUN_DIR": str(run_dir),
                        "K_PRIME": depth,
                    },
                    cwd=str(WORK),
                )
            except Exception as exc:
                print(f"[FALLO] {system} K'={depth}: {type(exc).__name__}: {exc}", file=sys.stderr)
                failures += 1
                continue

            print(f"[OK] {system} K'={depth} en {time.time() - started:.0f}s")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
