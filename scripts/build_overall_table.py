#!/usr/bin/env python3
"""Construye la tabla resumen del estudio desde los artefactos de cada sistema.

Es la tabla que más manos había tocado y la que más contradicciones acumulaba:
etiquetaba la fila de 0,799 como «5-way fusion + Blend» mientras la tabla de
reranking la atribuía al híbrido de tres vías, y llamaba «default» a unos
hiperparámetros que eran el óptimo de un barrido.

Los sistemas se leen de tres formatos distintos según cómo se produjeran:
`metrics_dual.json` para los runs con índice propio, `metrics_dual_parent.json`
para las fusiones, y `metrics_ce_*_k*.json` para los reranqueados.

Uso:  python scripts/build_overall_table.py --out paper/tables/overall.tex
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RUNS = Path("runs")
HYB = RUNS / "hybrids"

# (etiqueta, ruta del run, tipo de fuente, clave opcional)
SISTEMAS = [
    ("BM25 + parameter phrases ($k_1{=}0.60$, $b{=}0.35$)", RUNS / "bm25_unigram_params__k1-0.60__b-0.35", "dual", None),
    ("RM3 over BM25 + parameter phrases ($M{=}5$, $N{=}20$, $\\lambda{=}0.7$)", RUNS / "prf_rm3__bm25_unigram_params__k1-0.60__b-0.35__M5__N20__beta0_7", "parent", None),
    ("Rocchio over BM25 + parameter phrases ($M{=}10$, $N{=}20$, $\\beta{=}0.7$)", RUNS / "prf_rocchio__bm25_unigram_params__k1-0.60__b-0.35__M10__N20__beta0_7", "parent", None),
    ("Hybrid: BM25 + ColBERT + TF-IDF char", HYB / "hyb_bm25_uni__bge_colbert__tfidf_char_3_5", "parent", None),
    ("Hybrid: BM25 + BGE-dense + TF-IDF char", HYB / "hyb_bm25_uni__bge_dense__tfidf_char_3_5", "parent", None),
    ("Hybrid: BM25 + BGE-sparse + TF-IDF char", HYB / "hyb_bm25_uni__bge_sparse__tfidf_char_3_5", "parent", None),
    ("BM25 unigram ($k_1{=}0.80$, $b{=}0.35$)", RUNS / "bm25_unigram__k1-0.80__b-0.35", "dual", None),
    ("Rule-based structured pipeline", RUNS / "structured_pipeline_rules", "dual", None),
    ("Hybrid (3-way) + cross-encoder blend, $K'{=}100$", HYB / "hyb_bm25_uni__bge_colbert__tfidf_char_3_5", "ce", "blend_k100"),
    ("BM25 unigram + cross-encoder blend, $K'{=}50$", RUNS / "bm25_unigram", "ce", "blend_k50"),
    ("TF-IDF + parameter phrases", RUNS / "tfidf_unigram_phrases_replace", "dual", None),
    ("Five-way fusion (BM25 + 3$\\times$BGE-M3 + TF-IDF)", HYB / "hyb_bm25_uni__bge_multi__tfidf_char_3_5", "parent", None),
    ("BGE-M3 ColBERT (best neural)", RUNS / "bge_m3_colbert", "dual", None),
]


def leer(run_dir: Path, tipo: str, clave: str | None) -> dict[str, float] | None:
    if tipo == "dual":
        path = run_dir / "metrics_dual.json"
        if not path.exists():
            return None
        for r in json.loads(path.read_text(encoding="utf-8")):
            if r.get("scope") == "overall" and r.get("target") == "item":
                return {"acc@1": r["Acc@1"], "mrr": r["MRR"]}
        return None

    if tipo == "parent":
        path = run_dir / "metrics_dual_parent.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))["item"]
        return {"acc@1": d["Acc@1"], "mrr": d["MRR@10"]}

    if tipo == "ce":
        estrategia, k = clave.split("_k")
        path = run_dir / f"metrics_ce_{estrategia}_k{k}.json"
        if not path.exists():
            return None
        d = json.loads(path.read_text(encoding="utf-8"))
        return {"acc@1": d["acc@1"], "mrr": d["mrr@10"]}

    raise ValueError(tipo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    filas, faltan = [], []
    for etiqueta, run_dir, tipo, clave in SISTEMAS:
        m = leer(run_dir, tipo, clave)
        if m is None:
            faltan.append(f"{etiqueta} ({run_dir})")
            continue
        filas.append((etiqueta, m))

    filas.sort(key=lambda f: -f[1]["acc@1"])
    mostradas = filas[: args.top]
    resto = filas[args.top :]

    lines = [
        r"% Generado por scripts/build_overall_table.py -- no editar a mano.",
        r"\begin{table}[htbp]",
        r"\centering",
        # Ojo: sólo el primer fragmento es f-string, así que las llaves de los
        # siguientes son literales y no hay que duplicarlas.
        rf"\caption{{Top {args.top} configurations by item-level Acc@1 on the canonical test"
        r" set ($n=16{,}590$). Every row is measured on the same queries. MRR is given for"
        r" reference.}",
        r"\label{tab:overall_performance}",
        r"\begin{tabular}{lcc}",
        r"\toprule",
        r"\textbf{Configuration} & \textbf{Acc@1} & \textbf{MRR} \\",
        r"\midrule",
    ]
    for etiqueta, m in mostradas:
        lines.append(f"{etiqueta} & {m['acc@1']:.3f} & {m['mrr']:.3f} " + r"\\")

    if resto:
        lines.append(r"\midrule")
        lines.append(r"\multicolumn{3}{l}{\textit{For reference:}} \\")
        for etiqueta, m in resto:
            lines.append(f"{etiqueta} & {m['acc@1']:.3f} & {m['mrr']:.3f} " + r"\\")

    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]

    for etiqueta, m in filas:
        print(f"  {m['acc@1']:.4f}  {m['mrr']:.4f}  {etiqueta[:62]}")
    if faltan:
        print("\nSin artefacto:")
        for f in faltan:
            print(f"    {f}")

    tex = "\n".join(lines) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(tex, encoding="utf-8")
        print(f"\n-> {args.out}")
    return 1 if faltan else 0


if __name__ == "__main__":
    raise SystemExit(main())
