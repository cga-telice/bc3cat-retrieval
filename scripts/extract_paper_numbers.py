#!/usr/bin/env python3
"""Extrae todas las cifras numericas de paper_28.tex junto con su contexto.

Produce un inventario exhaustivo y auditable de cada numero publicado, para
poder contrastar una a una las cifras del manuscrito revisado contra las del
enviado a Automation in Construction (AUTCON-D-26-03592).

Se distinguen dos contextos:
  - tabular : filas dentro de un entorno tabular, atribuidas a su label
  - prosa   : cifras en el cuerpo del texto, con la linea completa

Las tres ultimas columnas del CSV se rellenan a mano durante la revision:
fuente_verificada (el artefacto de runs/ o eval/ del que sale la cifra),
valor_correcto y estado.

Uso:  python scripts/extract_paper_numbers.py [tex] [csv]
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

BS = "\\"

# Una cifra publicable: entero con separadores de millar opcionales, decimal
# opcional y signo de porcentaje opcional.
NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(%)?"
)

LABEL = re.compile(re.escape(BS) + r"label\{([^}]*)\}")
CAPTION = re.compile(re.escape(BS) + r"caption\{(.*)")
FLOAT_ENV = re.compile(re.escape(BS) + r"(begin|end)\{(table|figure)\*?\}")

# Lineas que contienen numeros que no son resultados: geometria, versiones de
# paquete, referencias cruzadas. Se excluyen solo fuera de tablas.
NOISE_HINTS = (
    "includegraphics", "resizebox", "setlength", "vspace", "hspace",
    "documentclass", "usepackage", "linewidth", "textwidth",
    "affiliation", "postcode", "ead{", "cortext", "bibliography",
)


def strip_math(s: str) -> str:
    """Normaliza la notacion LaTeX que envuelve a las cifras."""
    s = s.replace("{,}", ",").replace("{.}", ".")
    s = s.replace(BS + ",", "")
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    for cmd in ("textbf", "emph", "textit", "texttt", "mathbf"):
        s = s.replace(BS + cmd, "")
    s = s.replace(BS + "%", "%")
    s = s.replace("{", "").replace("}", "")
    return s


def main(tex_path: Path, out_path: Path) -> int:
    if not tex_path.exists():
        print(f"No existe {tex_path}", file=sys.stderr)
        return 1

    lines = tex_path.read_text(encoding="utf-8").splitlines()

    in_tabular = False
    in_body = False
    current_label = ""
    rows: list[dict[str, str]] = []

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()

        # El preambulo solo contiene numeros de version y opciones de clase.
        if not in_body:
            if line.startswith(BS + "begin{document}"):
                in_body = True
            continue

        # Comentarios LaTeX: no llegan al PDF.
        if line.startswith("%"):
            continue

        if m := LABEL.search(line):
            current_label = m.group(1)

        if BS + "begin{tabular}" in line:
            in_tabular = True
            continue
        if BS + "end{tabular}" in line:
            in_tabular = False
            continue
        if m := FLOAT_ENV.match(line):
            if m.group(1) == "end":
                current_label = ""
            continue

        if not in_tabular and any(h in line for h in NOISE_HINTS):
            continue

        clean = strip_math(line)
        found = [(m.group(1), bool(m.group(2))) for m in NUMBER.finditer(clean)]
        if not found:
            continue

        # En una fila de tabla, la primera celda identifica la fila.
        row_label = ""
        if in_tabular:
            cells = [c.strip() for c in clean.split("&")]
            row_label = cells[0][:80]

        for value, is_pct in found:
            rows.append(
                {
                    "linea": str(lineno),
                    "contexto": "tabular" if in_tabular else "prosa",
                    "tabla_label": current_label if in_tabular else "",
                    "fila": row_label,
                    "valor": value + ("%" if is_pct else ""),
                    "texto": clean[:200],
                    "fuente_verificada": "",
                    "valor_correcto": "",
                    "estado": "",
                }
            )

    if not rows:
        print("No se extrajo ninguna cifra: revisa el patron.", file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    tabular = sum(1 for r in rows if r["contexto"] == "tabular")
    print(f"{len(rows)} cifras extraidas de {tex_path} -> {out_path}")
    print(f"  {tabular} en tablas, {len(rows) - tabular} en prosa")
    return 0


if __name__ == "__main__":
    tex = Path(sys.argv[1] if len(sys.argv) > 1 else "paper/paper_28.tex")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/reviews/baseline_published_numbers.csv")
    raise SystemExit(main(tex, out))
