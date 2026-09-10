#!/usr/bin/env python3
"""Dibuja el mejor Acc@1 por familia de método, a nivel de ítem y de padre.

La figura del manuscrito marcaba «n/a» el nivel de padre de las familias híbrida
y de reranking, porque `src/metrics.ipynb` no puede procesar runs sin índice
propio. Justamente esas dos familias son las que combinan señal léxica y neuronal,
así que su brecha ítem/padre es la que dice dónde está la aportación de cada una.

Uso:  python scripts/plot_acc1_by_family.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_dual import load_ranking, metrics  # noqa: E402

RUNS = Path("runs")
OUT = Path("paper/figures/acc1_by_family.pdf")

# (familia, mejor configuración de esa familia, cómo leerla)
FAMILIAS = [
    ("Lexical\n(BM25 + params)", RUNS / "bm25_unigram_params__k1-0.60__b-0.35" / "metrics_dual.json", "dual"),
    ("PRF\n(RM3)", RUNS / "prf_rm3__bm25_unigram_params__k1-0.60__b-0.35__M5__N20__beta0_7" / "metrics_dual_parent.json", "parent"),
    ("Structured\n(rules)", RUNS / "structured_pipeline_rules" / "metrics_dual.json", "dual"),
    ("Hybrid\n(3-way)", RUNS / "hybrids" / "hyb_bm25_uni__bge_colbert__tfidf_char_3_5" / "metrics_dual_parent.json", "parent"),
    ("Reranking\n(BM25 + blend)", RUNS / "bm25_unigram" / "results_top50_ce_blend.jsonl.gz", "ranking"),
    ("Neural\n(BGE-M3 ColBERT)", RUNS / "bge_m3_colbert" / "metrics_dual.json", "dual"),
]


def leer(path: Path, tipo: str) -> tuple[float, float] | None:
    if not path.exists():
        return None
    if tipo == "dual":
        d = {
            r["target"]: r
            for r in json.loads(path.read_text(encoding="utf-8"))
            if r.get("scope") == "overall"
        }
        return d["item"]["Acc@1"], d["parent"]["Acc@1"]
    if tipo == "parent":
        d = json.loads(path.read_text(encoding="utf-8"))
        return d["item"]["Acc@1"], d["parent"]["Acc@1"]
    if tipo == "ranking":
        ranking = load_ranking(path)
        return metrics(ranking, "item")["Acc@1"], metrics(ranking, "parent")["Acc@1"]
    raise ValueError(tipo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    etiquetas, items, padres = [], [], []
    for nombre, path, tipo in FAMILIAS:
        valores = leer(path, tipo)
        if valores is None:
            print(f"sin artefacto: {path}", file=sys.stderr)
            continue
        etiquetas.append(nombre)
        items.append(valores[0])
        padres.append(valores[1])
        print(f"  {nombre.replace(chr(10), ' '):34s} item={valores[0]:.4f}  padre={valores[1]:.4f}")

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
    ax.legend(loc="lower left", frameon=False, fontsize=8.5, ncol=2)
    fig.tight_layout()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, bbox_inches="tight")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
