#!/usr/bin/env python3
"""Contrasta las tablas de PRF del manuscrito contra los artefactos de runs/.

El manuscrito reporta seis configuraciones de RM3 y seis de Rocchio con cuatro
decimales. Verificarlas a mano es tedioso y propenso a error, que es justamente
como se colaron cifras de una version anterior del estudio en otras tablas.

Uso:  python scripts/verify_prf_tables.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEX = Path("paper/paper_28.tex")
RUNS = Path("runs")

# Filas de las tablas: "M & N & lambda & MRR & nDCG@10 & Acc@1 \\"
ROW = re.compile(
    r"^(\d+)\s*&\s*(\d+)\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*&\s*([\d.]+)\s*\\\\"
)


def run_name(family: str, m: str, n: str, beta: str) -> str:
    return f"prf_{family}__bm25_unigram__M{m}__N{n}__beta{beta.replace('.', '_')}"


def artefact(name: str) -> dict | None:
    path = RUNS / name / "metrics_dual.json"
    if not path.exists():
        return None
    for r in json.loads(path.read_text(encoding="utf-8")):
        if r.get("scope") == "overall" and r.get("target") == "item":
            return r
    return None


def table_rows(tex: str, label: str) -> list[re.Match]:
    # Hay que buscar la DEFINICION de la etiqueta, no la etiqueta suelta: el
    # texto la referencia con \ref{} antes de definirla, y arrancar ahi lleva a
    # leer las filas de la tabla anterior. Confundir asi las tablas de RM3 y
    # Rocchio es exactamente el tipo de error que este script debe detectar.
    marker = "\\label{" + label + "}"
    start = tex.find(marker)
    if start < 0:
        return []
    end = tex.find(r"\end{tabular}", start)
    if end < 0:
        return []
    return [m for line in tex[start:end].splitlines() if (m := ROW.match(line.strip()))]


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    problemas = 0

    for label, family in (("tab:rm3_configurations", "rm3"), ("tab:rocchio_configurations", "rocchio")):
        filas = table_rows(tex, label)
        print(f"\n{label}: {len(filas)} filas")
        if not filas:
            print("  no se pudo leer la tabla")
            problemas += 1
            continue

        for m in filas:
            M, N, beta, mrr, ndcg, acc = m.groups()
            name = run_name(family, M, N, beta)
            got = artefact(name)
            if got is None:
                print(f"  M={M} N={N} b={beta}: SIN RUN ({name})")
                problemas += 1
                continue

            esperado = {"MRR": float(mrr), "nDCG@10": float(ndcg), "Acc@1": float(acc)}
            diffs = {
                k: (v, got[k]) for k, v in esperado.items() if abs(v - got[k]) > 5e-5
            }
            if diffs:
                detalle = "  ".join(
                    f"{k}: paper {a:.4f} vs run {b:.4f}" for k, (a, b) in diffs.items()
                )
                print(f"  M={M} N={N} b={beta}: DISCREPA  {detalle}")
                problemas += 1
            else:
                print(f"  M={M} N={N} b={beta}: ok")

    print()
    if problemas:
        print(f"{problemas} discrepancias.")
        return 1
    print("Todas las filas coinciden con los artefactos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
