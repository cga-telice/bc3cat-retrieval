#!/usr/bin/env python3
"""Comprueba que toda cita del manuscrito resuelve contra la bibliografia.

Un `\\cite` sin entrada produce un `[?]` en el PDF y una referencia perdida en la
version publicada. El Revisor 2 ya senalo una cita ausente (Jacques de Sousa),
asi que conviene tener la comprobacion automatizada y no depender de leer el log
de bibtex.

Informa en las dos direcciones:
  - claves citadas que no existen en el .bib  -> rompen el PDF
  - entradas del .bib que nadie cita          -> solo ruido, se ignoran

Uso:  python scripts/check_citations.py [tex] [bib]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CITE = re.compile(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
ENTRY = re.compile(r"^\s*@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)


def main(tex_path: Path, bib_path: Path) -> int:
    if not tex_path.exists():
        print(f"No existe {tex_path}", file=sys.stderr)
        return 1
    if not bib_path.exists():
        print(f"No existe {bib_path}", file=sys.stderr)
        return 1

    tex = tex_path.read_text(encoding="utf-8", errors="replace")
    bib = bib_path.read_text(encoding="utf-8", errors="replace")

    cited: set[str] = set()
    for match in CITE.finditer(tex):
        cited.update(key.strip() for key in match.group(1).split(",") if key.strip())

    defined = {m.group(1) for m in ENTRY.finditer(bib)}

    # BibTeX resuelve las claves sin distinguir mayusculas: `\cite{salton1988term}`
    # encuentra la entrada `@article{salton1988Term`. Compararlas de forma sensible
    # a mayusculas produce falsos positivos y tienta a anadir entradas duplicadas.
    defined_lower = {key.lower() for key in defined}
    missing = sorted(key for key in cited if key.lower() not in defined_lower)
    cited_lower = {key.lower() for key in cited}
    unused = {key for key in defined if key.lower() not in cited_lower}

    duplicates = sorted(
        key for key in defined_lower
        if sum(1 for d in defined if d.lower() == key) > 1
    )

    print(f"claves citadas    : {len(cited)}")
    print(f"entradas en el bib: {len(defined)}  ({len(unused)} sin citar)")
    print(f"claves duplicadas : {len(duplicates)}")
    print(f"sin resolver      : {len(missing)}")

    if duplicates:
        print()
        print("Entradas repetidas (bibtex avisa y usa una de ellas):")
        for key in duplicates:
            print(f"    {key}")

    if missing:
        print()
        print("Estas citas no tienen entrada y saldran como [?] en el PDF:")
        for key in missing:
            print(f"    {key}")
        return 1

    print("\nOK: todas las citas resuelven.")
    return 0


if __name__ == "__main__":
    tex = Path(sys.argv[1] if len(sys.argv) > 1 else "paper/paper_28.tex")
    bib = Path(sys.argv[2] if len(sys.argv) > 2 else "paper/references.bib")
    raise SystemExit(main(tex, bib))
