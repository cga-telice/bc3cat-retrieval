#!/usr/bin/env python3
"""Construye la tabla de reranking con cross-encoder desde los artefactos.

La tabla publicada mezclaba sistemas: la fila «baseline» del híbrido traía las
cifras de la fusión de cinco vías mientras las filas reranqueadas venían de la de
tres, y el MRR@10 del baseline de BM25 figuraba como 1,000, imposible con un
Acc@1 de 0,869. Generarla evita que eso se repita.

Uso:  python scripts/build_reranking_table.py --out paper/tables/reranking.tex
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RUNS = Path("runs")

SYSTEMS = [
    ("BM25 (unigram)", RUNS / "bm25_unigram"),
    ("BGE-M3 ColBERT", RUNS / "bge_m3_colbert"),
    (
        "Hybrid (BM25 + BGE-ColBERT + TF-IDF char)",
        RUNS / "hybrids" / "hyb_bm25_uni__bge_colbert__tfidf_char_3_5",
    ),
]
DEPTHS = [20, 50, 100]
METRICS = ["acc@1", "recall@5", "recall@10", "mrr@10"]


def baseline(run_dir: Path) -> tuple[dict[str, float], bool] | None:
    """Métricas del sistema de primera etapa, antes de reranquear.

    Devuelve también si su MRR está truncado en el rango 10. El de
    `metrics_dual.json` (src/metrics.ipynb) recorre los 100 candidatos; el del
    barrido de fusión (`best_from_sweep.json`, src/hybrid.ipynb) corta en 10.
    """
    dual = run_dir / "metrics_dual.json"
    if dual.exists():
        for r in json.loads(dual.read_text(encoding="utf-8")):
            if r.get("scope") == "overall" and r.get("target") == "item":
                return {
                    "acc@1": r["Acc@1"],
                    "recall@5": r["Recall@5"],
                    "recall@10": r["Recall@10"],
                    "mrr@10": r["MRR"],
                }, False
    sweep = run_dir / "best_from_sweep.json"
    if sweep.exists():
        return json.loads(sweep.read_text(encoding="utf-8"))["metrics"], True
    return None


def reranked(run_dir: Path, strategy: str, depth: int) -> dict[str, float] | None:
    path = run_dir / f"metrics_ce_{strategy}_k{depth}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def row(label: str, m: dict[str, float], bold: bool = False, truncated: bool = False) -> str:
    """Sólo se resalta Acc@1: es el criterio por el que se elige la mejor fila.

    Poner en negrita las cuatro métricas de esa fila sugeriría que también son las
    mejores de su columna, que no tiene por qué ser cierto: para BM25, el mejor
    Recall@5 lo da una configuración reranqueada, no el baseline.
    """
    cells = []
    for k in METRICS:
        v = f"{m[k]:.3f}"
        if bold and k == "acc@1":
            v = rf"\textbf{{{v}}}"
        if truncated and k == "mrr@10":
            v += r"$^{\dagger}$"
        cells.append(v)
    return f"{label} & " + " & ".join(cells) + r" \\"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    lines = [
        r"% Generado por scripts/build_reranking_table.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{Cross-encoder reranking at three depths, item level ($n=16{,}590$)."
        r" \textit{Replace} ranks by cross-encoder score alone; \textit{blend} interpolates"
        r" it with the first-stage score ($\lambda=0.6$). The baseline row is the"
        r" first-stage system itself. No configuration improves on its own baseline in"
        r" Acc@1 except BGE-M3 ColBERT.}",
        r"\label{tab:reranking_results}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"\textbf{System / strategy} & \textbf{Acc@1} & \textbf{Recall@5} & "
        r"\textbf{Recall@10} & \textbf{MRR} \\",
    ]

    faltan = []
    for label, run_dir in SYSTEMS:
        found = baseline(run_dir)
        if found is None:
            faltan.append(str(run_dir))
            continue
        base, base_truncated = found

        lines.append(r"\midrule")
        lines.append(rf"\multicolumn{{5}}{{l}}{{\textit{{{label}}}}} \\")

        # El mejor Acc@1 de la familia se marca en negrita, baseline incluido.
        candidatos = [base["acc@1"]]
        for depth in DEPTHS:
            for strategy in ("replace", "blend"):
                m = reranked(run_dir, strategy, depth)
                if m:
                    candidatos.append(m["acc@1"])
        mejor = max(candidatos)

        lines.append(row(r"\quad Baseline (no reranking)", base, base["acc@1"] == mejor,
                         base_truncated))
        for depth in DEPTHS:
            for strategy in ("replace", "blend"):
                m = reranked(run_dir, strategy, depth)
                if m is None:
                    faltan.append(f"{run_dir} {strategy} k={depth}")
                    continue
                nombre = rf"\quad {strategy.capitalize()}, $K'={depth}$"
                # El cross-encoder (src/cross_encoder.ipynb) da MRR@10.
                lines.append(row(nombre, m, m["acc@1"] == mejor, truncated=True))

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"}",
        r"\\[2pt]{\footnotesize $^{\dagger}$\,MRR@10 (reciprocal rank truncated at rank 10).}",
        r"\end{table}",
    ]

    if faltan:
        print("Faltan artefactos:")
        for f in faltan:
            print(f"    {f}")

    tex = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(tex, encoding="utf-8")
        print(f"-> {args.out}")
    else:
        print(tex)
    return 1 if faltan else 0


if __name__ == "__main__":
    raise SystemExit(main())
