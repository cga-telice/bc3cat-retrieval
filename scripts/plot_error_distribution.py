#!/usr/bin/env python3
"""Dibuja la distribución de tipos de error desde el CSV del análisis.

La figura del manuscrito venía de una ejecución en la que el híbrido aparecía con
el 100 % de sus fallos en «Other», un artefacto de que su texto de consulta no se
resolvía. Regenerarla desde el CSV garantiza que figura y tabla digan lo mismo.

Uso:  python scripts/plot_error_distribution.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

CSV = Path("eval/error_analysis/error_distribution.csv")
OUT = Path("paper/figures/error_distribution.pdf")

ETIQUETAS = {
    "bm25_unigram": "BM25\nunigram",
    "bge_m3_colbert": "BGE-M3\nColBERT",
    "hyb_bm25_uni__bge_colbert__tfidf_char_3_5": "Hybrid\n(3-way)",
}
ORDEN_TIPOS = ["Numeric Mismatch", "Lexical Confusion", "Other"]
COLORES = {"Numeric Mismatch": "#31688e", "Lexical Confusion": "#35b779", "Other": "#bdbdbd"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    pivot = (
        df.pivot(index="method", columns="error_type", values="percent")
        .reindex(columns=ORDEN_TIPOS)
        .fillna(0.0)
    )
    pivot = pivot.reindex([m for m in ETIQUETAS if m in pivot.index])

    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    abajo = pd.Series(0.0, index=pivot.index)
    for tipo in ORDEN_TIPOS:
        valores = pivot[tipo]
        ax.barh(
            range(len(pivot)), valores, left=abajo, height=0.55,
            color=COLORES[tipo], label=tipo, edgecolor="white", linewidth=0.6,
        )
        # Sólo se etiqueta el segmento dominante: los otros dos no caben.
        for i, (v, b) in enumerate(zip(valores, abajo)):
            if v >= 8:
                ax.text(b + v / 2, i, f"{v:.1f}%", ha="center", va="center",
                        color="white", fontsize=9, fontweight="bold")
        abajo = abajo + valores

    ax.set_yticks(range(len(pivot)))
    ax.set_yticklabels([ETIQUETAS[m] for m in pivot.index], fontsize=9)
    ax.set_xlabel("Share of that method's failed queries (%)", fontsize=9)
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3,
        frameon=False, fontsize=9,
    )
    fig.tight_layout()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, bbox_inches="tight")
    print(f"-> {args.out}")
    for m in pivot.index:
        fila = "  ".join(f"{t}={pivot.loc[m, t]:.2f}%" for t in ORDEN_TIPOS)
        print(f"   {m[:44]:46s} {fila}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
