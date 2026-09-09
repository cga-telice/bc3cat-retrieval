#!/usr/bin/env python3
"""Audita que todos los runs evaluen exactamente la misma muestra de consultas.

Es la comprobacion que habria detectado el defecto principal del estudio
publicado: los `results_top100.jsonl.gz` de BM25, de los densos y de los
hibridos contienen tres conjuntos distintos de 16.590 consultas, con solapes
del 47 % y del 35 %, mientras el manuscrito afirma que todos comparten el mismo
conjunto de test.

Uso:
    python scripts/check_sample_consistency.py                 # audita runs/
    python scripts/check_sample_consistency.py --expect FILE   # exige una muestra
    python scripts/check_sample_consistency.py --refresh       # ignora la cache

Devuelve codigo de salida 1 si hay mas de una muestra, o si alguna no coincide
con la esperada.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_utils import fingerprint, load_sample, query_keys_from_run, short  # noqa: E402

CACHE_PATH = Path(".cache/sample_fingerprints.json")
RESULT_GLOBS = ("**/results_top100.jsonl.gz", "**/results_top*_ce_*.jsonl.gz")


def load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def stat_key(path: Path) -> str:
    """Identidad del contenido a efectos de cache: tamano y fecha."""
    st = path.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def collect(runs_dir: Path, refresh: bool) -> dict[str, dict]:
    cache = {} if refresh else load_cache()
    results: dict[str, dict] = {}

    paths = sorted({p for pattern in RESULT_GLOBS for p in runs_dir.glob(pattern)})
    if not paths:
        print(f"No se encontro ningun fichero de resultados bajo {runs_dir}", file=sys.stderr)
        return results

    for i, path in enumerate(paths, start=1):
        rel = path.relative_to(runs_dir).as_posix()
        key = stat_key(path)
        cached = cache.get(rel)

        if cached and cached.get("stat") == key:
            results[rel] = cached
            continue

        print(f"  [{i:3d}/{len(paths)}] leyendo {rel}", file=sys.stderr)
        try:
            keys = query_keys_from_run(path)
        except (OSError, EOFError, json.JSONDecodeError) as exc:
            results[rel] = {"stat": key, "error": f"{type(exc).__name__}: {exc}"}
            continue

        results[rel] = {"stat": key, "n": len(keys), "sha256": fingerprint(keys)}

    cache.update(results)
    save_cache(cache)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    parser.add_argument(
        "--expect",
        type=Path,
        help="fichero de muestra canonica; exige que todos los runs coincidan",
    )
    parser.add_argument("--refresh", action="store_true", help="recalcula, ignora la cache")
    args = parser.parse_args()

    results = collect(args.runs_dir, args.refresh)
    if not results:
        return 1

    groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    errors: list[str] = []
    for rel, info in sorted(results.items()):
        if "error" in info:
            errors.append(f"{rel}: {info['error']}")
            continue
        groups[(info["sha256"], info["n"])].append(rel)

    print()
    print(f"{len(results) - len(errors)} runs analizados, {len(groups)} muestras distintas")
    print()

    expected_fp = None
    if args.expect:
        expected_fp = fingerprint(load_sample(args.expect))
        print(f"Muestra canonica ({args.expect}): {short(expected_fp)}")
        print()

    for (fp, n), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        mark = ""
        if expected_fp is not None:
            mark = "  <- canonica" if fp == expected_fp else "  <- NO COINCIDE"
        print(f"muestra {short(fp)}  n={n:,}  {len(members)} runs{mark}")
        for rel in members[:6]:
            print(f"    {rel}")
        if len(members) > 6:
            print(f"    ... y {len(members) - 6} mas")
        print()

    if errors:
        print("Ficheros ilegibles:")
        for e in errors:
            print(f"    {e}")
        print()

    if expected_fp is not None:
        deviating = [m for (fp, _), ms in groups.items() if fp != expected_fp for m in ms]
        if deviating:
            print(f"FALLO: {len(deviating)} runs no usan la muestra canonica.")
            return 1
        print("OK: todos los runs usan la muestra canonica.")
        return 0

    if len(groups) > 1:
        print(f"FALLO: conviven {len(groups)} muestras distintas.")
        return 1

    print("OK: todos los runs comparten la misma muestra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
