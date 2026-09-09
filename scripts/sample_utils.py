"""Utilidades compartidas para identificar la muestra de consultas de un run.

El problema que motiva este modulo: el estudio publicado convivio con tres
muestras distintas de 16.590 consultas, presentadas como una sola, porque cada
notebook re-muestreaba en memoria (`.sample(n, random_state=42)`) sobre marcos
de datos con orden y contenido distintos. La huella que se calcula aqui es la
que permite detectarlo y la que impide que vuelva a ocurrir.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

# Claves bajo las que los distintos notebooks guardaron el identificador de
# consulta a lo largo del proyecto.
QUERY_KEY_FIELDS = ("query_item_key", "query_id", "qid")


def query_keys_from_run(path: Path) -> set[str]:
    """Devuelve el conjunto de identificadores de consulta de un fichero de run."""
    keys: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            for field in QUERY_KEY_FIELDS:
                if field in record:
                    keys.add(record[field])
                    break
    return keys


def fingerprint(keys: set[str]) -> str:
    """Huella estable de un conjunto de consultas.

    SHA-256 sobre las claves ordenadas: independiente del orden de lectura y
    comparable entre ejecuciones, maquinas y formatos de fichero.
    """
    joined = "\n".join(sorted(keys))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def short(fp: str) -> str:
    """Prefijo legible de una huella, para tablas e informes."""
    return fp[:12]


def load_sample(path: Path) -> set[str]:
    """Carga un fichero de muestra y verifica su huella declarada."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    keys = set(payload["query_item_keys"])

    declared_n = payload.get("n")
    if declared_n is not None and declared_n != len(keys):
        raise ValueError(
            f"{path}: declara n={declared_n} pero contiene {len(keys)} claves unicas"
        )

    declared_fp = payload.get("sha256")
    if declared_fp is not None:
        actual = fingerprint(keys)
        if actual != declared_fp:
            raise ValueError(
                f"{path}: huella declarada {short(declared_fp)} != real {short(actual)}"
            )

    return keys
