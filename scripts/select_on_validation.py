#!/usr/bin/env python3
"""Elige los hiperparametros de BM25 en validacion y mide lo que costo no hacerlo.

El manuscrito reporta la mejor casilla de una rejilla `(k1, b)` evaluada sobre el
mismo conjunto de test del que salen todas las cifras. Es la objecion B3 del
informe, y la respuesta honesta no es reejecutar y callarse: es medir cuanto
optimismo introdujo esa seleccion.

Para eso hacen falta tres numeros por familia, no uno:

  - el que se reporto: el maximo sobre la rejilla en test;
  - el que se deberia haber reportado: el de la configuracion que gana en
    validacion, evaluada en test;
  - la diferencia, que es el sesgo de seleccion.

El conjunto de validacion son 5.000 consultas disjuntas del test (semilla
20260909, de los 30.923 items que nunca se usan como consulta), asi que el test
sigue siendo las mismas 16.590 de siempre y todo lo publicado sigue comparable.

Uso:
    python scripts/select_on_validation.py
    python scripts/select_on_validation.py --criterion MRR --tex paper/tables/validation.tex
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RUNS = Path("runs")
VAL = RUNS / "val"

FAMILIES = {
    "bm25_unigram": "BM25 unigram",
    "bm25_unibigram": "BM25 uni+bigram",
    "bm25_unigram_params": "BM25 + parameter phrases",
}

GRID = re.compile(r"^(?P<family>.+?)__k1-(?P<k1>[\d.]+)__b-(?P<b>[\d.]+)$")


def read(path: Path, criterion: str, target: str = "item") -> float | None:
    if not path.exists():
        return None
    for record in json.loads(path.read_text(encoding="utf-8")):
        if record.get("scope") == "overall" and record.get("target") == target:
            return record.get(criterion)
    return None


def collect(criterion: str) -> dict[str, list[dict]]:
    families: dict[str, list[dict]] = {}
    for run_dir in sorted(VAL.iterdir()) if VAL.exists() else []:
        m = GRID.match(run_dir.name)
        if not m or m["family"] not in FAMILIES:
            continue
        val = read(run_dir / "metrics_dual.json", criterion)
        test = read(RUNS / run_dir.name / "metrics_dual.json", criterion)
        if val is None:
            continue
        families.setdefault(m["family"], []).append({
            "run": run_dir.name,
            "k1": float(m["k1"]),
            "b": float(m["b"]),
            "val": val,
            "test": test,
        })
    return families


def agreement(cells: list[dict]) -> dict | None:
    """Cuanto se parecen las dos particiones: orden y nivel.

    El orden es lo que decide la seleccion; el nivel es lo que impide leer el
    numero de validacion como una estimacion del rendimiento. Son independientes
    y conviene reportar los dos.
    """
    usable = [c for c in cells if c["test"] is not None]
    n = len(usable)
    if n < 3:
        return None
    val = [c["val"] for c in usable]
    test = [c["test"] for c in usable]

    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: -values[i])
        out = [0] * len(values)
        for position, i in enumerate(order):
            out[i] = position
        return out

    rv, rt = ranks(val), ranks(test)
    d2 = sum((a - b) ** 2 for a, b in zip(rv, rt))
    rho = 1 - 6 * d2 / (n * (n * n - 1))
    gaps = [v - t for v, t in zip(val, test)]
    return {
        "spearman": rho,
        "val_minus_test_mean": sum(gaps) / n,
        "val_minus_test_min": min(gaps),
        "val_minus_test_max": max(gaps),
        "validation_easier_everywhere": all(g > 0 for g in gaps),
    }


def render_tex(chosen: list[dict], criterion: str) -> str:
    lines = [
        r"% Generado por scripts/select_on_validation.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        rf"\caption{{Hyperparameter selection for the BM25 families. The grid is scored on"
        rf" a validation set of $5{{,}}000$ queries disjoint from the test set, and the"
        rf" selected configuration is then scored once on the test set. The last column is"
        rf" the optimism that selecting on the test set would have introduced: the"
        rf" difference between the best test cell of the grid and the test score of the"
        rf" cell chosen on validation. Criterion: item-level {criterion}.}}",
        r"\label{tab:validation_selection}",
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r"\textbf{Family} & \textbf{Selected $(k_1, b)$} & \textbf{Validation}"
        r" & \textbf{Test} & \textbf{Best test cell} & \textbf{Optimism (pp)} \\",
        r"\midrule",
    ]
    for c in chosen:
        lines.append(
            f"{c['label']} & $({c['k1']:.2f}, {c['b']:.2f})$ & {c['val']:.4f}"
            f" & {c['test']:.4f} & {c['best_test']:.4f} & {100*c['optimism']:+.2f} " + r"\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--criterion", default="Acc@1",
                        choices=["Acc@1", "Recall@5", "Recall@10", "MRR", "nDCG@10"])
    parser.add_argument("--tex", type=Path)
    parser.add_argument("--out", type=Path, default=Path("eval/validation/selection.json"))
    args = parser.parse_args()

    families = collect(args.criterion)
    if not families:
        print(f"No hay runs de validacion en {VAL}", file=__import__("sys").stderr)
        return 1

    chosen = []
    for family, cells in families.items():
        incomplete = [c["run"] for c in cells if c["test"] is None]
        best_val = max(cells, key=lambda c: c["val"])
        with_test = [c for c in cells if c["test"] is not None]
        best_test = max(with_test, key=lambda c: c["test"]) if with_test else None

        print(f"\n=== {FAMILIES[family]}  ({len(cells)} casillas evaluadas en validacion) ===")
        for c in sorted(cells, key=lambda c: -c["val"]):
            mark = " <- validacion" if c is best_val else ""
            mark += " <- test" if best_test is not None and c is best_test else ""
            test_txt = f"{c['test']:.4f}" if c["test"] is not None else "   --  "
            print(f"  k1={c['k1']:.2f} b={c['b']:.2f}   val={c['val']:.4f}  test={test_txt}{mark}")
        if incomplete:
            print(f"  (sin run de test: {', '.join(incomplete)})")

        agree = agreement(cells)
        if agree:
            print(
                f"  concordancia: spearman={agree['spearman']:.3f}   "
                f"validacion - test: media {100*agree['val_minus_test_mean']:+.2f}pp, "
                f"rango [{100*agree['val_minus_test_min']:+.2f}, {100*agree['val_minus_test_max']:+.2f}], "
                f"validacion mas facil en todas las casillas: "
                f"{'si' if agree['validation_easier_everywhere'] else 'no'}"
            )

        if best_val["test"] is None or best_test is None:
            print("  No se puede medir el optimismo: falta el run de test correspondiente.")
            continue
        optimism = best_test["test"] - best_val["test"]
        chosen.append({
            "family": family, "label": FAMILIES[family], "agreement": agree,
            "k1": best_val["k1"], "b": best_val["b"],
            "val": best_val["val"], "test": best_val["test"],
            "best_test_run": best_test["run"], "best_test": best_test["test"],
            "optimism": optimism,
        })
        print(f"  -> validacion elige ({best_val['k1']:.2f}, {best_val['b']:.2f});"
              f" en test da {best_val['test']:.4f}. La mejor casilla en test es"
              f" ({best_test['k1']:.2f}, {best_test['b']:.2f}) con {best_test['test']:.4f}."
              f" Optimismo: {100*optimism:+.2f} pp.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"criterion": args.criterion, "families": families, "chosen": chosen},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n-> {args.out}")
    if args.tex and chosen:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(render_tex(chosen, args.criterion), encoding="utf-8")
        print(f"-> {args.tex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
