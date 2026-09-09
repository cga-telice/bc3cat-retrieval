#!/usr/bin/env python3
"""Comprueba que todo fichero de consultas cubre la muestra canonica.

Cada YAML de metodo declara su propia fuente de consultas: unos apuntan a
`OEB_short_feats.parquet`, otros a `OEB_resumen.json` y los BGE-M3 a
`OEB_short_norm.parquet`. Esa divergencia, combinada con un muestreo posicional,
es lo que produjo tres muestras distintas en el estudio publicado.

Ahora que la muestra se carga de un fichero fijo, hay que verificar antes de
reejecutar nada que las tres fuentes contienen las mismas 16.590 consultas. Si
alguna no las tuviera, el notebook fallaria a mitad de un run largo.

Uso:  python scripts/check_query_sources.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_utils import load_sample  # noqa: E402

CONFIGS = Path("configs")
DATA_DIR = Path("data/processed")
SAMPLES = [
    Path("benchmark/query_samples/OEB_query_sample_test_16590.json"),
    Path("benchmark/query_samples/OEB_query_sample_val_5000.json"),
]

QUERY_FIELDS = ("short_text_path", "short_feats", "short_path")


def declared_sources() -> dict[str, list[str]]:
    """Fuentes de consultas declaradas en los YAML, agrupadas por fichero."""
    import yaml

    sources: dict[str, list[str]] = {}
    for cfg_path in sorted(CONFIGS.glob("*.yaml")):
        try:
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(cfg, dict):
            continue
        inputs = cfg.get("inputs") or {}
        template = next((inputs[f] for f in QUERY_FIELDS if inputs.get(f)), None)
        if not template:
            continue
        resolved = template.format(
            data_dir=str(DATA_DIR), collection=cfg.get("collection", "OEB")
        )
        # Los YAML usan rutas de contenedor; aqui se leen desde el host.
        resolved = resolved.replace("/work/data/processed", str(DATA_DIR))
        sources.setdefault(resolved, []).append(cfg_path.stem)
    return sources


def item_keys(path: Path) -> set[str]:
    if path.suffix == ".parquet":
        return set(pd.read_parquet(path, columns=["item_key"]).item_key.astype(str))
    records = json.loads(path.read_text(encoding="utf-8"))
    return {str(r["item_key"]) for r in records}


def main() -> int:
    sources = declared_sources()
    if not sources:
        print("Ningun YAML declara fuente de consultas", file=sys.stderr)
        return 1

    samples = {p.name: load_sample(p) for p in SAMPLES if p.exists()}
    if not samples:
        print("No hay ficheros de muestra; ejecuta build_query_samples.py", file=sys.stderr)
        return 1

    failures = 0
    for source, methods in sorted(sources.items()):
        path = Path(source)
        print(f"{path}  ({len(methods)} configs: {', '.join(methods[:3])}"
              f"{', ...' if len(methods) > 3 else ''})")
        if not path.exists():
            print("    NO EXISTE")
            failures += 1
            continue

        keys = item_keys(path)
        print(f"    {len(keys):,} item_keys")
        for name, sample in samples.items():
            missing = sample - keys
            status = "OK" if not missing else f"FALTAN {len(missing):,}"
            print(f"    {name}: {status}")
            if missing:
                failures += 1
        print()

    if failures:
        print(f"FALLO: {failures} comprobaciones no pasan.")
        return 1
    print("OK: todas las fuentes cubren todas las muestras.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
