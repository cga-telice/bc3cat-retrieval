#!/usr/bin/env python3
"""Construye tablas de resultados directamente desde los artefactos de runs/.

Toda cifra del manuscrito revisado debe entrar por `\\input{}` desde una tabla
generada aqui, y no teclearse a mano. Es lo que impide que reaparezcan cifras
huerfanas como el 24.711/15.136 arrastrado de una version anterior del estudio,
o que dos tablas atribuyan el mismo numero a sistemas distintos.

Cada tabla verifica ademas que todos sus runs comparten la muestra canonica de
consultas: una tabla que mezcla poblaciones no se genera, falla.

Uso:
    python scripts/leaderboard.py --runs bm25_unigram structured_pipeline_rules
    python scripts/leaderboard.py --preset structured --out eval/structured/lb_item.tex
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_utils import fingerprint, load_sample, query_keys_from_run, short  # noqa: E402

RUNS_DIR = Path("runs")
CANONICAL_SAMPLE = Path("benchmark/query_samples/OEB_query_sample_test_16590.json")

METRICS = ["Acc@1", "Recall@5", "Recall@10", "MRR", "nDCG@10"]

# Etiquetas para el manuscrito. Sin entrada aqui se usa el nombre del run.
LABELS = {
    "structured_pipeline_rules": "Rule-based extraction + structured lookup",
    "structured_pipeline_oracle_rules": r"\quad with oracle extraction",
    "structured_pipeline_phi4_classify": "LLM classification + structured lookup",
    "structured_pipeline_oracle_phi4_classify": r"\quad with oracle extraction",
    "structured_pipeline": "Schema extraction + structured lookup",
    "structured_pipeline_oracle": r"\quad with oracle extraction",
    "structured_pipeline_classifier": "Trained classifier + structured lookup",
    "structured_pipeline_bio_tagger": "BIO tagger + structured lookup",
    "bm25_unigram_params__k1-0.60__b-0.35": "BM25 with parameter phrases (best lexical)",
    "bm25_unigram__k1-0.80__b-0.35": "BM25 unigram",
    "bge_m3_colbert": "BGE-M3 ColBERT (best neural)",
}

PRESETS = {
    # Baselines estructurados: la respuesta a la ultima pregunta del Revisor 2,
    # que pregunta si un filtrado por reglas sobre los atributos no seria un
    # baseline mas fuerte que la recuperacion textual.
    # Cada pipeline va seguido de su variante con extraccion perfecta, que es
    # su cota superior: separa el error de extraccion del error de busqueda.
    "structured": [
        "bm25_unigram_params__k1-0.60__b-0.35",
        "bge_m3_colbert",
        "structured_pipeline_rules",
        "structured_pipeline_oracle_rules",
        "structured_pipeline_phi4_classify",
        "structured_pipeline_oracle_phi4_classify",
        "structured_pipeline",
        "structured_pipeline_oracle",
        "structured_pipeline_classifier",
        "structured_pipeline_bio_tagger",
    ],
}


def read_metrics(run: str, target: str, scope: str = "overall") -> dict | None:
    path = RUNS_DIR / run / "metrics_dual.json"
    if not path.exists():
        return None
    for record in json.loads(path.read_text(encoding="utf-8")):
        if record.get("target") == target and record.get("scope") == scope:
            return record
    return None


def check_sample(runs: list[str], expected: str) -> list[str]:
    """Devuelve los runs cuya muestra de consultas no es la canonica."""
    deviating = []
    for run in runs:
        path = RUNS_DIR / run / "results_top100.jsonl.gz"
        if not path.exists():
            continue
        if fingerprint(query_keys_from_run(path)) != expected:
            deviating.append(run)
    return deviating


def render(rows: list[tuple[str, dict]], target: str, caption: str, label: str) -> str:
    header = " & ".join(rf"\textbf{{{m}}}" for m in METRICS)
    best = max((r[1]["Acc@1"] for r in rows), default=0.0)

    lines = [
        r"% Generado por scripts/leaderboard.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        rf"\caption{{{caption}}}",
        rf"\label{{{label}}}",
        r"\begin{tabular}{l" + "c" * len(METRICS) + "}",
        r"\toprule",
        rf"\textbf{{System}} & {header} \\",
        r"\midrule",
    ]
    for name, m in rows:
        cells = []
        for metric in METRICS:
            value = f"{m[metric]:.3f}"
            if metric == "Acc@1" and abs(m[metric] - best) < 1e-9:
                value = rf"\textbf{{{value}}}"
            cells.append(value)
        lines.append(f"{LABELS.get(name, name)} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="*", help="nombres de run bajo runs/")
    parser.add_argument("--preset", choices=sorted(PRESETS), help="conjunto predefinido")
    parser.add_argument("--target", default="item", choices=["item", "parent"])
    parser.add_argument("--out", type=Path, help="fichero .tex de salida")
    parser.add_argument("--caption", default="")
    parser.add_argument("--label", default="tab:generated")
    parser.add_argument(
        "--skip-sample-check",
        action="store_true",
        help="no verificar que los runs comparten la muestra canonica",
    )
    args = parser.parse_args()

    runs = list(args.runs or []) + (PRESETS[args.preset] if args.preset else [])
    if not runs:
        parser.error("indica --runs o --preset")

    rows, missing = [], []
    for run in runs:
        m = read_metrics(run, args.target)
        if m is None:
            missing.append(run)
            continue
        rows.append((run, m))

    if missing:
        print("Sin metrics_dual.json:", ", ".join(missing), file=sys.stderr)
        return 1

    if not args.skip_sample_check:
        expected = fingerprint(load_sample(CANONICAL_SAMPLE))
        print(f"Muestra canonica: {short(expected)}")
        deviating = check_sample([r for r, _ in rows], expected)
        if deviating:
            print(
                "FALLO: estos runs no usan la muestra canonica y no pueden compartir "
                "tabla:\n    " + "\n    ".join(deviating),
                file=sys.stderr,
            )
            return 1
        print("Todos los runs comparten la muestra canonica.")

    print()
    width = max(len(LABELS.get(r, r)) for r, _ in rows)
    print(f"{'':{width}}  " + "  ".join(f"{m:>9}" for m in METRICS))
    for name, m in rows:
        values = "  ".join(f"{m[metric]:9.4f}" for metric in METRICS)
        print(f"{LABELS.get(name, name):{width}}  {values}   (n={int(m['queries']):,})")

    tex = render(rows, args.target, args.caption or "Generated leaderboard", args.label)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(tex, encoding="utf-8")
        print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
