#!/usr/bin/env python3
"""Dibuja las dos figuras de rendimiento léxico (padre e ítem) desde eval/lexical/.

Las figuras del manuscrito llegaron de Overleaf sin script que las generase. Sus
datos son los de `eval/lexical/lb_{parent,item}.tex`, los leaderboards que
escribió `notebooks/eval_all_runs.ipynb`, y como `runs/` ya no existe (D-019) son
la única fuente que queda. Se dibujan las ocho configuraciones léxicas de la
tabla, sin la fusión RRF, ordenadas por Acc@1 en cada nivel.

Uso:  python scripts/plot_lexical_performance.py
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402

EVAL = Path("eval/lexical")
FIGURES = Path("paper/figures")
METRICS = ["Acc@1", "Recall@5", "Recall@10", "MRR", "nDCG@10"]

# Nombre en la leyenda, color, estilo de línea y marcador. Colores de la paleta de
# Okabe e Ito, que se distinguen también con daltonismo; cada serie lleva además
# su propio marcador, así que no dependen sólo del color.
SERIES = {
    "bm25_unigram_params__k1-0.60__b-0.35": ("BM25 with parameter tokens", "#0b4f9c", "-", "s"),
    "bm25_unigram__k1-0.80__b-0.35": ("BM25-unigram", "#56b4e9", "-", "o"),
    "bm25_unibigram__k1-0.80__b-0.35": ("BM25-unibigram", "#009e73", "-", "P"),
    "tfidf_unigram_phrases_replace": ("TF-IDF phrases replace", "#d55e00", "--", "o"),
    "tfidf_unigram_phrases_add": ("TF-IDF phrases add", "#cc79a7", "--", "D"),
    "tfidf_unigram_nostop": ("TF-IDF nostop", "#6a3d9a", "--", "^"),
    "tfidf_unigram": ("TF-IDF-unigram", "#e69f00", ":", "v"),
    "tfidf_char_3_5": ("TF-IDF-char 3-5", "#7f7f7f", ":", "X"),
}

# Los mismos límites del eje Y que las figuras publicadas.
YLIM = {"item": (0.50, 1.045), "parent": (0.72, 1.045)}


def read_leaderboard(path: Path) -> list[tuple[str, dict[str, float]]]:
    """Filas de un leaderboard de eval_all_runs, en el orden de la tabla."""
    header, rows = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if "&" not in line:
            continue
        cells = [c.strip() for c in re.sub(r"\\\\\s*$", "", line).split("&")]
        if cells[0] == "method":
            header = cells
            continue
        rows.append((cells[0], {h: float(v) for h, v in zip(header[1:], cells[1:])}))
    return rows


def plot(level: str, out: Path) -> None:
    rows = [(run, m) for run, m in read_leaderboard(EVAL / f"lb_{level}.tex") if run in SERIES]
    rows.sort(key=lambda r: -r[1]["Acc@1"])

    # 1568 x 1017 px a 200 ppp, como las figuras publicadas.
    fig, ax = plt.subplots(figsize=(7.84, 5.085), dpi=200)
    x = range(len(METRICS))
    for run, m in rows:
        label, color, style, marker = SERIES[run]
        ax.plot(x, [m[k] for k in METRICS], linestyle=style, marker=marker, color=color,
                linewidth=2.2 if style == "-" else 1.8, markersize=6,
                markeredgecolor="white", markeredgewidth=0.6, label=label)

    ax.set_xticks(list(x), METRICS)
    ax.set_ylim(*YLIM[level])
    ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%.2f"))
    ax.set_ylabel("Score")
    ax.grid(True, color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    # Leyenda debajo del eje, fuera del área de datos. matplotlib la rellena por
    # columnas; se reordena para que se lea por filas en el orden de Acc@1.
    ncol = 4
    handles, labels = ax.get_legend_handles_labels()
    nrow = -(-len(handles) // ncol)
    order = [r * ncol + c for c in range(ncol) for r in range(nrow) if r * ncol + c < len(handles)]
    ax.legend([handles[i] for i in order], [labels[i] for i in order],
              loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=ncol, frameon=False,
              fontsize=8, handlelength=2.6, columnspacing=1.4)
    fig.text(0.09, 0.02, "n = 16,590 test queries  ·  ordered by Acc@1",
             fontsize=8.5, color="#666666")
    fig.subplots_adjust(left=0.09, right=0.98, top=0.98, bottom=0.22)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"-> {out}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=FIGURES)
    args = parser.parse_args()
    for level in ("parent", "item"):
        plot(level, args.outdir / f"lexical_performance_{level}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
