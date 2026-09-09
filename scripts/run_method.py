#!/usr/bin/env python3
"""Ejecuta build -> retrieve -> metrics para cualquier metodo, no solo BM25.

El unico runner del proyecto (`notebooks/bm25_orchestrator.ipynb`) cubria las
familias BM25; todo lo demas —densos, BGE-M3, hibridos, PRF— se lanzaba a mano
abriendo notebooks, que es como se colaron tres muestras de consultas distintas
sin que nadie lo notara.

Se ejecuta DENTRO del contenedor, donde las rutas /work/... son validas:

    docker exec jupyter-pytorch python /work/scripts/run_method.py dense_e5

Opciones utiles:
    --split val      usa el conjunto de validacion y escribe en runs/val/
    --build          reconstruye el indice (por defecto se reutiliza)
    --dry-run        muestra lo que haria
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

WORK = Path("/work")
SRC = WORK / "src"
CONFIGS = WORK / "configs"
RUNS = WORK / "runs"
INDEX = WORK / "index"
LOGS = WORK / "logs"

SAMPLES = {
    "test": "/work/benchmark/query_samples/OEB_query_sample_test_16590.json",
    "val": "/work/benchmark/query_samples/OEB_query_sample_val_5000.json",
}


def notebooks() -> dict[str, Path]:
    return {
        "build": SRC / "index_builder.ipynb",
        "retrieve": SRC / "retrieve.ipynb",
        "metrics": SRC / "metrics.ipynb",
    }


def config_for(method: str) -> Path:
    path = CONFIGS / f"{method}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("methods", nargs="+", help="nombres de metodo (= nombre del YAML)")
    parser.add_argument("--split", choices=sorted(SAMPLES), default="test")
    parser.add_argument("--build", action="store_true", help="reconstruye el indice")
    parser.add_argument("--k", type=int, default=100, help="profundidad de recuperacion")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not WORK.exists():
        print(
            "Este script se ejecuta dentro del contenedor:\n"
            "    docker exec jupyter-pytorch python /work/scripts/run_method.py ...",
            file=sys.stderr,
        )
        return 1

    import papermill as pm

    nbs = notebooks()
    missing = [str(p) for p in nbs.values() if not p.exists()]
    if missing:
        print("Faltan notebooks: " + ", ".join(missing), file=sys.stderr)
        return 1

    run_group = "" if args.split == "test" else args.split
    sample = SAMPLES[args.split]
    LOGS.mkdir(parents=True, exist_ok=True)

    failures = 0
    for method in args.methods:
        try:
            cfg = config_for(method)
        except FileNotFoundError as exc:
            print(f"[SKIP] {exc}", file=sys.stderr)
            failures += 1
            continue

        run_dir = (RUNS / run_group / method) if run_group else (RUNS / method)
        tag = f"{method}__{args.split}"
        index_exists = (INDEX / method).exists()

        print(f"\n=== {method}  [{args.split}] ===")
        print(f"    config    {cfg}")
        print(f"    run_dir   {run_dir}")
        print(f"    muestra   {sample}")
        print(f"    indice    {'reconstruir' if args.build else ('reutilizar' if index_exists else 'CONSTRUIR (no existe)')}")

        if args.dry_run:
            continue

        run_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()

        try:
            if args.build or not index_exists:
                print("--> build")
                pm.execute_notebook(
                    input_path=str(nbs["build"]),
                    output_path=str(LOGS / f"build__{tag}.ipynb"),
                    parameters={"CFG_PATH": str(cfg), "RUN_CONTEXT": "run_method"},
                    cwd=str(WORK),
                )

            print("--> retrieve")
            pm.execute_notebook(
                input_path=str(nbs["retrieve"]),
                output_path=str(LOGS / f"retrieve__{tag}.ipynb"),
                parameters={
                    "METHOD_NAME": method,
                    "RUN_GROUP": run_group,
                    "QUERY_SAMPLE": sample,
                    "RANDOM_SAMPLE": None,
                    "K": args.k,
                    "SAVE": True,
                    "RUN_CONTEXT": "run_method",
                },
                cwd=str(WORK),
            )

            print("--> metrics")
            pm.execute_notebook(
                input_path=str(nbs["metrics"]),
                output_path=str(LOGS / f"metrics__{tag}.ipynb"),
                parameters={"RUN_DIR": str(run_dir), "RUN_CONTEXT": "run_method"},
                cwd=str(WORK),
            )
        except Exception as exc:  # papermill envuelve cualquier error de celda
            print(f"[FALLO] {method}: {type(exc).__name__}: {exc}", file=sys.stderr)
            print(f"        log: {LOGS}/*__{tag}.ipynb", file=sys.stderr)
            failures += 1
            continue

        print(f"[OK] {method} en {time.time() - started:.0f}s -> {run_dir}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
