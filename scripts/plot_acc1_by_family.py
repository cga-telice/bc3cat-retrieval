#!/usr/bin/env python3
"""Dibuja el mejor Acc@1 por familia de método, a nivel de ítem y de padre.

La figura del manuscrito marcaba «n/a» el nivel de padre de las familias híbrida
y de reranking, porque `src/metrics.ipynb` no puede procesar runs sin índice
propio. Justamente esas dos familias son las que combinan señal léxica y neuronal,
así que su brecha ítem/padre es la que dice dónde está la aportación de cada una.

Los valores se leen de `eval/families/acc1_by_family.json`, no de `runs/`: tras
D-019 sólo se han reconstruido algunos runs, y la fusión y el cross-encoder no se
vuelven a ejecutar. El JSON documenta la procedencia de cada cifra.

Uso:  python scripts/plot_acc1_by_family.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

DATA = Path("eval/families/acc1_by_family.json")
OUT = Path("paper/figures/acc1_by_family.pdf")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    familias = json.loads(args.data.read_text(encoding="utf-8"))["families"]
    etiquetas = [f["label"] for f in familias]
    items = [f["item"]["Acc@1"] for f in familias]
    padres = [f["parent"]["Acc@1"] for f in familias]
    for nombre, item, padre in zip(etiquetas, items, padres):
        print(f"  {nombre.replace(chr(10), ' '):34s} item={item:.4f}  padre={padre:.4f}")

    x = range(len(etiquetas))
    ancho = 0.38
    fig, ax = plt.subplots(figsize=(8.4, 3.8))
    b1 = ax.bar([i - ancho / 2 for i in x], items, ancho, label="Item level (exact variant)", color="#31688e")
    b2 = ax.bar([i + ancho / 2 for i in x], padres, ancho, label="Parent level (family)", color="#9ecae1")

    for barras in (b1, b2):
        for b in barras:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.015,
                    f"{b.get_height():.3f}", ha="center", va="bottom", fontsize=7.5)

    ax.set_xticks(list(x))
    ax.set_xticklabels(etiquetas, fontsize=8)
    ax.set_ylabel("Acc@1", fontsize=9)
    ax.set_ylim(0, 1.12)
    ax.spines[["top", "right"]].set_visible(False)
    # La leyenda va por encima del eje, fuera del área de las barras, como en
    # las demás figuras del manuscrito.
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, fontsize=8.5, ncol=2)
    fig.tight_layout()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, bbox_inches="tight")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
