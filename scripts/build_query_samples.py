#!/usr/bin/env python3
"""Fija y versiona las muestras de consultas del benchmark.

Genera dos ficheros bajo benchmark/query_samples/:

  OEB_query_sample_test_16590.json
      Las 16.590 consultas de test. NO se re-muestrean: se extraen del run de
      referencia para que las cifras nuevas sigan siendo comparables con las
      publicadas. Es la "muestra A" del analisis de revision, la que usan BM25,
      TF-IDF, PRF, BGE-M3 y los pipelines estructurados.

  OEB_query_sample_val_5000.json
      5.000 consultas de validacion, muestreadas de los items del catalogo que
      NO se usan como consulta en el test. Al ser disjuntas, la seleccion de
      hiperparametros deja de hacerse sobre el conjunto que luego se reporta,
      sin necesidad de encoger el test.

Uso:  python scripts/build_query_samples.py [--force]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_utils import fingerprint, query_keys_from_run, short  # noqa: E402

# Run de referencia del que se extrae la muestra de test. Cualquier run de la
# muestra A serviria; se elige BM25-unigram por ser el baseline del paper.
REFERENCE_RUN = Path("runs/bm25_unigram__k1-0.80__b-0.35/results_top100.jsonl.gz")

CATALOG = Path("data/processed/OEB_resumen.json")
OUT_DIR = Path("benchmark/query_samples")

# Registro raiz del catalogo: es el titulo del capitulo, no un item recuperable.
ROOT_KEY = "OEB#"

VAL_SIZE = 5_000
VAL_SEED = 20260909


def catalog_item_keys(path: Path) -> list[str]:
    """item_keys del catalogo, en orden de fichero y sin el registro raiz."""
    records = json.loads(path.read_text(encoding="utf-8"))
    return [r["item_key"] for r in records if r["item_key"] != ROOT_KEY]


def write_sample(
    path: Path, keys: set[str], *, split: str, provenance: str, seed: int | None
) -> str:
    ordered = sorted(keys)
    fp = fingerprint(keys)
    payload = {
        "collection": "OEB",
        "split": split,
        "n": len(ordered),
        "sha256": fp,
        "seed": seed,
        "provenance": provenance,
        "query_item_keys": ordered,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return fp


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="sobrescribe ficheros existentes")
    args = parser.parse_args()

    test_path = OUT_DIR / "OEB_query_sample_test_16590.json"
    val_path = OUT_DIR / "OEB_query_sample_val_5000.json"

    existing = [p for p in (test_path, val_path) if p.exists()]
    if existing and not args.force:
        print("Ya existen; usa --force para regenerar:", file=sys.stderr)
        for p in existing:
            print(f"    {p}", file=sys.stderr)
        return 1

    if not REFERENCE_RUN.exists():
        print(f"No existe el run de referencia {REFERENCE_RUN}", file=sys.stderr)
        return 1

    print(f"Extrayendo la muestra de test de {REFERENCE_RUN} ...")
    test_keys = query_keys_from_run(REFERENCE_RUN)
    test_fp = write_sample(
        test_path,
        test_keys,
        split="test",
        provenance=f"extraida de {REFERENCE_RUN.as_posix()} (muestra A del estudio publicado)",
        seed=None,
    )
    print(f"  test : n={len(test_keys):,}  sha256={short(test_fp)}  -> {test_path}")

    all_keys = catalog_item_keys(CATALOG)
    unknown = test_keys - set(all_keys)
    if unknown:
        print(
            f"AVISO: {len(unknown)} claves del run no estan en {CATALOG}", file=sys.stderr
        )

    pool = sorted(set(all_keys) - test_keys)
    print(f"Reserva para validacion: {len(pool):,} items no usados como consulta en test")
    if len(pool) < VAL_SIZE:
        print(f"Insuficiente para {VAL_SIZE} consultas de validacion", file=sys.stderr)
        return 1

    val_keys = set(random.Random(VAL_SEED).sample(pool, VAL_SIZE))
    val_fp = write_sample(
        val_path,
        val_keys,
        split="val",
        provenance=(
            f"muestreadas de los {len(pool)} items de {CATALOG.as_posix()} "
            "que no aparecen en el split de test"
        ),
        seed=VAL_SEED,
    )
    print(f"  val  : n={len(val_keys):,}  sha256={short(val_fp)}  -> {val_path}")

    overlap = test_keys & val_keys
    assert not overlap, f"test y val comparten {len(overlap)} consultas"
    print()
    print(f"OK: los splits son disjuntos ({len(test_keys):,} test / {len(val_keys):,} val)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
