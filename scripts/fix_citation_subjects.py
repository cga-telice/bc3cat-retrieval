#!/usr/bin/env python3
"""Antepone el nombre de los autores a las citas usadas como sujeto gramatical.

El Revisor 2 (comentario 8.3) senala que el manuscrito escribe
"~\\cite{clave} developed ..." usando la referencia como sujeto. Es incorrecto
en cualquier estilo y, con `elsarticle-num`, produce frases que empiezan por un
numero entre corchetes.

Detecta las citas que abren oracion y van seguidas de un verbo, busca el apellido
del primer autor en el .bib y reescribe a "Apellido et al.~\\cite{clave} developed".

Uso:
    python scripts/fix_citation_subjects.py            # muestra los cambios
    python scripts/fix_citation_subjects.py --apply    # los escribe
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Cita que abre oracion (inicio de linea o tras punto) seguida de un verbo en
# minuscula: el patron que delata el uso como sujeto.
SUBJECT_CITE = re.compile(
    r"(?P<pre>(?:^|(?<=\. )|(?<=\.\s)))~?\\cite[a-z]*\{(?P<key>[^},]+)\}\s+(?P<verb>[a-z]\w+)"
)

AUTHOR_FIELD = re.compile(r"author\s*=\s*\{(.+?)\}\s*,\s*\n", re.S)


def bib_authors(bib_text: str) -> dict[str, str]:
    """Apellido del primer autor por clave de entrada."""
    authors: dict[str, str] = {}
    for chunk in re.split(r"\n@", bib_text):
        m_key = re.match(r"\w+\s*\{\s*([^,\s]+)\s*,", chunk)
        if not m_key:
            m_key = re.match(r"@?\w+\s*\{\s*([^,\s]+)\s*,", chunk)
        if not m_key:
            continue
        key = m_key.group(1)
        m_auth = AUTHOR_FIELD.search(chunk)
        if not m_auth:
            continue
        first = m_auth.group(1).split(" and ")[0].strip()
        # "Apellido, Nombre" o "Nombre Apellido"; las llaves protegen apellidos
        # compuestos como {de Sousa}.
        if "," in first:
            surname = first.split(",")[0]
        else:
            surname = first.split()[-1] if first.split() else first
        surname = surname.replace("{", "").replace("}", "").strip()
        if surname:
            authors[key.lower()] = surname
    return authors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tex", type=Path, default=Path("paper/paper_28.tex"))
    parser.add_argument("--bib", type=Path, default=Path("paper/references.bib"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    tex = args.tex.read_text(encoding="utf-8")
    authors = bib_authors(args.bib.read_text(encoding="utf-8", errors="replace"))
    print(f"{len(authors)} entradas con autor en {args.bib}")

    cambios: list[tuple[str, str]] = []

    def sustituir(m: re.Match) -> str:
        key = m.group("key").strip()
        surname = authors.get(key.lower())
        if not surname:
            return m.group(0)
        original = m.group(0)
        nuevo = f"{m.group('pre')}{surname} et al.~\\cite{{{key}}} {m.group('verb')}"
        cambios.append((original.strip(), nuevo.strip()))
        return nuevo

    nuevo_tex = SUBJECT_CITE.sub(sustituir, tex)

    if not cambios:
        print("No hay citas usadas como sujeto.")
        return 0

    print(f"\n{len(cambios)} citas usadas como sujeto:\n")
    for antes, despues in cambios:
        print(f"  - {antes[:88]}")
        print(f"  + {despues[:88]}\n")

    if args.apply:
        args.tex.write_text(nuevo_tex, encoding="utf-8")
        print(f"Escrito {args.tex}")
    else:
        print("(sin --apply no se ha escrito nada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
