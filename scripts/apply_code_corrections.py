#!/usr/bin/env python3
"""Aplica las correcciones de codigo de la revision AUTCON a los notebooks.

Los notebooks son JSON con el codigo troceado en listas de lineas, asi que
editarlos a mano es propenso a romper el fichero. Este script los carga como
JSON, sustituye bloques de lineas exactos y los vuelve a escribir, de forma
idempotente y verificable.

Cada parche lleva el identificador del registro de correcciones
(docs/reviews/CORRECTIONS_LOG.md) para que el cambio quede trazado.

Uso:
    python scripts/apply_code_corrections.py --check    # solo informa
    python scripts/apply_code_corrections.py            # aplica
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Patch:
    ident: str
    notebook: str
    rationale: str
    old: list[str]
    new: list[str]
    applied_marker: str = field(default="")

    def __post_init__(self) -> None:
        # Una linea del bloque nuevo que no exista en el viejo sirve para
        # detectar que el parche ya esta aplicado.
        if not self.applied_marker:
            novel = [ln for ln in self.new if ln not in self.old]
            self.applied_marker = novel[0] if novel else self.new[0]


PATCHES: list[Patch] = [
    Patch(
        ident="C3b",
        notebook="src/hybrid.ipynb",
        rationale=(
            "El bonus numerico comparaba la consulta solo contra los documentos "
            "muestreados. El 65,2 % de los distractores candidatos queda fuera de la "
            "muestra, asi que el bonus se habria concedido preferentemente al "
            "documento gold: fuga de informacion del conjunto de test."
        ),
        old=[
            "numbers_long  = dict(zip(long_s.item_key,  long_s.numbers))\n",
        ],
        new=[
            "# El bonus numerico se compara contra el corpus completo (47.513 documentos),\n",
            "# no contra los 16.590 muestreados: restringirlo a la muestra concederia el\n",
            "# bonus preferentemente al documento gold y filtraria informacion del test.\n",
            "numbers_long  = dict(zip(long_df.item_key, long_df.numbers))\n",
        ],
    ),
    Patch(
        ident="C3a",
        notebook="src/hybrid.ipynb",
        rationale=(
            "La columna `numbers` se materializa como numpy.ndarray al releerse de "
            "Parquet, no como list. `isinstance(v, list)` era siempre False, de modo "
            "que _nums devolvia [] siempre y numeric_exact / numeric_overlap eran "
            "identicamente cero en los nueve runs hibridos publicados."
        ),
        old=[
            "def _nums(v): \n",
            "    return [float(x) for x in v] if isinstance(v, list) else []\n",
        ],
        new=[
            "def _nums(v):\n",
            "    # Acepta list, tuple y numpy.ndarray. Comprobar `isinstance(v, list)`\n",
            "    # dejaba el bonus numerico permanentemente a cero (ver CORRECTIONS_LOG C3a).\n",
            "    if v is None or isinstance(v, (str, bytes)):\n",
            "        return []\n",
            "    try:\n",
            "        return [float(x) for x in v]\n",
            "    except TypeError:\n",
            "        return []\n",
        ],
    ),
    Patch(
        ident="C4",
        notebook="src/hybrid.ipynb",
        rationale=(
            "beta_exact = 0.0 y 0.05 nunca se probaron pese a que el manuscrito los "
            "declara. Con el bonus ya operativo (C3) la rejilla debe cubrir el rango "
            "anunciado e incluir el 0, que es la condicion de control."
        ),
        old=[
            "    beta_exact_grid = (0.10, 0.15)\n",
            "    beta_overlap_grid = (0.00, 0.05)\n",
        ],
        new=[
            "    beta_exact_grid = (0.00, 0.05, 0.10, 0.15)\n",
            "    beta_overlap_grid = (0.00, 0.05)\n",
        ],
    ),
]


def encode_block(lines: list[str], indent: str) -> str:
    """Codifica lineas de codigo como aparecen en el JSON de un notebook.

    Se opera sobre el texto crudo, y no sobre el JSON deserializado, porque un
    round-trip con json.dumps reformatea el fichero entero y sepulta el cambio
    real bajo un diff de miles de lineas.
    """
    return (",\n" + indent).join(json.dumps(ln, ensure_ascii=False) for ln in lines)


def apply_patch(text: str, patch: Patch, indent: str = " " * 4) -> tuple[str, str]:
    """Devuelve (texto, 'aplicado' | 'ya-aplicado' | 'no-encontrado')."""
    old_block = encode_block(patch.old, indent)
    new_block = encode_block(patch.new, indent)

    if old_block in text:
        if text.count(old_block) > 1:
            return text, "ambiguo"
        return text.replace(old_block, new_block), "aplicado"

    if json.dumps(patch.applied_marker, ensure_ascii=False) in text:
        return text, "ya-aplicado"

    return text, "no-encontrado"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="informa sin escribir")
    parser.add_argument("--only", help="aplica solo el parche con este identificador")
    args = parser.parse_args()

    selected = [p for p in PATCHES if not args.only or p.ident == args.only]
    if not selected:
        print(f"Ningun parche con identificador {args.only!r}", file=sys.stderr)
        return 1

    by_notebook: dict[str, list[Patch]] = {}
    for patch in selected:
        by_notebook.setdefault(patch.notebook, []).append(patch)

    failures = 0
    for nb_path_str, patches in by_notebook.items():
        nb_path = Path(nb_path_str)
        if not nb_path.exists():
            print(f"{nb_path}: NO EXISTE", file=sys.stderr)
            failures += 1
            continue

        original = nb_path.read_text(encoding="utf-8")
        text = original

        print(f"{nb_path}")
        for patch in patches:
            text, status = apply_patch(text, patch)
            print(f"  {patch.ident:5s} {status}")
            if status in ("no-encontrado", "ambiguo"):
                failures += 1

        if text == original:
            continue

        # El resultado debe seguir siendo un notebook valido.
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"  el parcheo rompio el JSON: {exc}", file=sys.stderr)
            failures += 1
            continue

        if args.check:
            print("  (--check: no se ha escrito)")
        else:
            nb_path.write_text(text, encoding="utf-8", newline="")
            print(f"  escrito {nb_path}")

    if failures:
        print(f"\n{failures} parches no encontrados: revisa si el codigo cambio.", file=sys.stderr)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
