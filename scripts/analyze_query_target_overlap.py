#!/usr/bin/env python3
"""Cuantifica cuanta informacion comparten la consulta y su documento objetivo.

El Revisor 2 (comentario 2.3) pide medir el solape entre el campo `resumen`,
que se usa como consulta, y el campo `texto`, que es el documento a recuperar.
Es la objecion central del rechazo: si el objetivo contiene casi literalmente la
consulta, la tarea no evalua busqueda por parte de un profesional sino
contencion lexica, y el 97,4 % de BM25 deja de ser sorprendente.

Se mide sobre los 47.513 pares alineados del catalogo, no sobre una muestra.

Salidas (eval/overlap/):
    overlap_summary.json      metricas agregadas
    overlap_per_query.parquet cobertura por consulta, para las figuras
    overlap_by_parent.csv     desglose por plantilla parametrica
    overlap_summary.tex       tabla lista para el manuscrito

Uso:  python scripts/analyze_query_target_overlap.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SHORT = Path("data/processed/OEB_short_feats.parquet")
LONG = Path("data/processed/OEB_long_feats.parquet")
OUT_DIR = Path("eval/overlap")
# Las tablas que el manuscrito incluye con \input viven dentro de paper/, para
# que el proyecto LaTeX sea autocontenido: TeX no lee rutas con ".." bajo la
# configuracion por defecto, y Overleaf tampoco puede salir del proyecto.
TABLES_DIR = Path("paper/tables")

COLUMNS = ["item_key", "parent_key", "tokens_word", "numbers"]


def as_set(value) -> set:
    """Normaliza list / numpy.ndarray / None a un conjunto."""
    if value is None:
        return set()
    return set(value.tolist() if isinstance(value, np.ndarray) else value)


def main() -> int:
    short = pd.read_parquet(SHORT, columns=COLUMNS)
    long = pd.read_parquet(LONG, columns=COLUMNS)

    pairs = short.merge(long, on="item_key", suffixes=("_q", "_d"))
    if len(pairs) != len(short):
        print(f"AVISO: {len(short)} consultas pero {len(pairs)} pares alineados")

    rows = []
    for r in pairs.itertuples(index=False):
        q_tok, d_tok = as_set(r.tokens_word_q), as_set(r.tokens_word_d)
        q_num, d_num = as_set(r.numbers_q), as_set(r.numbers_d)

        rows.append(
            {
                "item_key": r.item_key,
                "parent_key": r.parent_key_q,
                "n_query_tokens": len(q_tok),
                "n_query_numbers": len(q_num),
                # Fraccion de tokens de la consulta que aparecen literalmente
                # en el documento objetivo.
                "lexical_coverage": len(q_tok & d_tok) / len(q_tok) if q_tok else np.nan,
                "lexical_contained": bool(q_tok and q_tok <= d_tok),
                "numeric_coverage": len(q_num & d_num) / len(q_num) if q_num else np.nan,
                "numeric_contained": bool(q_num and q_num <= d_num),
                "has_numbers": bool(q_num),
            }
        )

    per_query = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_query.to_parquet(OUT_DIR / "overlap_per_query.parquet", index=False)

    n = len(per_query)
    with_numbers = per_query[per_query.has_numbers]

    summary = {
        "n_pairs": n,
        "lexical_coverage_mean": float(per_query.lexical_coverage.mean()),
        "lexical_coverage_median": float(per_query.lexical_coverage.median()),
        "lexical_fully_contained_pct": float(100 * per_query.lexical_contained.mean()),
        "queries_with_numbers_pct": float(100 * per_query.has_numbers.mean()),
        "numbers_per_query_mean": float(with_numbers.n_query_numbers.mean()),
        "numeric_coverage_mean": float(with_numbers.numeric_coverage.mean()),
        "numeric_fully_contained_pct": float(100 * with_numbers.numeric_contained.mean()),
        "query_tokens_mean": float(per_query.n_query_tokens.mean()),
    }

    (OUT_DIR / "overlap_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    by_parent = (
        per_query.groupby("parent_key")
        .agg(
            n_variants=("item_key", "size"),
            lexical_coverage=("lexical_coverage", "mean"),
            numeric_coverage=("numeric_coverage", "mean"),
        )
        .sort_values("n_variants", ascending=False)
    )
    by_parent.to_csv(OUT_DIR / "overlap_by_parent.csv")

    tex = [
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"\textbf{Query--target overlap} & \textbf{Value} \\",
        r"\midrule",
        rf"Mean lexical coverage & {summary['lexical_coverage_mean'] * 100:.2f}\% \\",
        rf"Median lexical coverage & {summary['lexical_coverage_median'] * 100:.2f}\% \\",
        rf"Queries fully contained in target (tokens) & {summary['lexical_fully_contained_pct']:.2f}\% \\",
        r"\midrule",
        rf"Queries containing at least one number & {summary['queries_with_numbers_pct']:.2f}\% \\",
        rf"Numbers per query (mean) & {summary['numbers_per_query_mean']:.2f} \\",
        rf"Mean numeric coverage & {summary['numeric_coverage_mean'] * 100:.2f}\% \\",
        rf"Queries whose numbers all appear in target & {summary['numeric_fully_contained_pct']:.2f}\% \\",
        r"\bottomrule",
        r"\end{tabular}",
    ]
    table = "% Generado por scripts/analyze_query_target_overlap.py -- no editar a mano.\n"
    table += "\n".join(tex) + "\n"
    (OUT_DIR / "overlap_summary.tex").write_text(table, encoding="utf-8")
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (TABLES_DIR / "overlap_summary.tex").write_text(table, encoding="utf-8")

    print(f"Pares analizados: {n:,}   plantillas: {len(by_parent):,}")
    print()
    for key, value in summary.items():
        print(f"  {key:34s} {value:10.4f}")
    print()
    print(f"Salidas en {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
