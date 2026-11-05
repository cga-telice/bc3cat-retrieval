#!/usr/bin/env python3
"""Mide la etapa 2 del pipeline estructurado por separado del resto.

El Acc@1 del pipeline confunde tres cosas: identificar la plantilla (etapa 1),
extraer los valores (etapa 2) y resolver la busqueda exacta (etapa 3). Sin
separarlas no se puede explicar por que el clasificador afinado se queda en
0,209 cuando su propio registro de entrenamiento declara 0,996 de acierto por
consulta.

La explicacion esta en `src/pipeline/training/data_prep.py`: ambos modelos
supervisados se entrenan sobre el texto LARGO del item y se evaluan sobre el
texto CORTO que hace de consulta. Su validacion mide la distribucion de
entrenamiento; el pipeline mide la otra. Este script cuantifica esa caida.

Se compara contra los parametros verdaderos del item consultado, que es la
unica referencia legitima: el gold de la etapa 2 no es una anotacion aparte,
es la tupla que genero el item.

Uso:  python scripts/probe_stage2_extractors.py --n 500
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "processed"
SCHEMA = DATA / "OEB_concept_schema.json"
SAMPLE = ROOT / "benchmark" / "query_samples" / "OEB_query_sample_test_16590.json"
OUT = ROOT / "eval" / "structured" / "stage2_extraction.json"

AXIS_KEYS = ("A", "B", "C", "D", "F")

RUNS_FOR_TIERS = [
    "structured_pipeline_rules",
    "structured_pipeline_phi4_classify",
    "structured_pipeline",
    "structured_pipeline_classifier",
    "structured_pipeline_bio_tagger",
]


def gold_params(long_df: pd.DataFrame) -> dict[str, tuple[str, dict[str, str]]]:
    """{item_key: (parent_key, {label_norm: value_norm})}, tal como los indexa
    `CatalogLookup`: si un eje se predice distinto de esto, la busqueda falla."""
    gold = {}
    for row in long_df.itertuples():
        params = {}
        for axis_key in AXIS_KEYS:
            axis = row.parameters_norm[axis_key]
            if axis is not None:
                params[axis["label_norm"]] = axis["values"][0]["value_norm"]
        gold[row.item_key] = (row.parent_key, params)
    return gold


def compare(pred: dict, gold: dict[str, str]) -> tuple[int, int, int]:
    """(aciertos, abstenciones, errores) sobre los ejes del item.

    La comparacion es en minusculas porque `CatalogLookup` normaliza asi antes
    de filtrar. Un eje sin resolver no es un acierto, pero tampoco cuesta lo
    mismo: deja el eje libre y el item correcto sigue en el conjunto devuelto.
    """
    lowered = {str(k).strip().lower(): v for k, v in pred.items()}
    ok = abstain = wrong = 0
    for label, gv in gold.items():
        pv = lowered.get(label.strip().lower())
        if pv is None:
            abstain += 1
        elif str(pv).strip().lower() == str(gv).strip().lower():
            ok += 1
        else:
            wrong += 1
    return ok, abstain, wrong


def tier_profile(run: str) -> dict | None:
    """Tamano del conjunto que devuelve la etapa 3, leido del run persistido.

    El pipeline puntua con 1.0 los items que casan con la tupla extraida y con
    0.5 el resto de la plantilla, asi que el corte en 0,9 recupera exactamente
    el conjunto de la busqueda exacta. Su tamano es lo que decide si un fallo de
    la etapa 2 es recuperable: un conjunto de un solo item que no es el correcto
    no lo arregla ninguna profundidad de ranking.
    """
    import gzip

    path = ROOT / "runs" / run / "results_top100.jsonl.gz"
    if not path.exists():
        return None
    sizes, hit, n = [], 0, 0
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            n += 1
            tier1 = [c for c in d["candidates"] if c["score"] > 0.9]
            sizes.append(len(tier1))
            hit += any(c["index_item_key"] == d["query_item_key"] for c in tier1)
    return {
        "queries": n,
        "mean_size": sum(sizes) / n,
        "singleton_share": sum(1 for s in sizes if s == 1) / n,
        "gold_in_set": hit / n,
    }


TEX_LABELS = {
    "rules": ("Rule-based", "structured_pipeline_rules"),
    "classifier": ("Fine-tuned classifier", "structured_pipeline_classifier"),
    "bio_tagger": ("Fine-tuned BIO tagger", "structured_pipeline_bio_tagger"),
}


def render_tex(summary: dict, tiers: dict, n: int) -> str:
    """Une lo que hace la etapa 2 con lo que eso le cuesta al pipeline."""
    lines = [
        r"% Generado por scripts/probe_stage2_extractors.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        rf"\caption{{What stage 2 gets right, and what it costs. Axis-level figures are"
        rf" measured on {n} queries of the canonical test set against the parameter tuple"
        r" that generated the target item; the candidate set is measured on all"
        r" $16{,}590$ queries of the corresponding run. An unresolved axis acts as a"
        r" wildcard and keeps the target in the set; a wrong value removes it.}",
        r"\label{tab:stage2}",
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r" & \multicolumn{3}{c}{\textbf{Axes}} & \multicolumn{2}{c}{\textbf{Candidate set}} \\",
        r"\cmidrule(lr){2-4}\cmidrule(lr){5-6}",
        r"\textbf{Stage 2} & \textbf{Correct} & \textbf{Unresolved} & \textbf{Wrong}"
        r" & \textbf{Mean size} & \textbf{Contains target} \\",
        r"\midrule",
    ]
    for key, (label, run) in TEX_LABELS.items():
        s = summary.get(key)
        if s is None:
            continue
        t = tiers.get(run, {})
        size = f"{t['mean_size']:.2f}" if t else "---"
        hit = f"{100*t['gold_in_set']:.1f}\\%" if t else "---"
        lines.append(
            f"{label} & {100*s['axis_correct']:.1f}\\% & {100*s['axis_abstained']:.1f}\\%"
            f" & {100*s['axis_wrong']:.1f}\\% & {size} & {hit} " + r"\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def build_extractors(which: list[str], device: str):
    made = {}
    if "rules" in which:
        from src.pipeline.param_extractor_rules import RuleBasedParamExtractor
        made["rules"] = RuleBasedParamExtractor(str(SCHEMA))
    if "classifier" in which:
        from src.pipeline.param_extractor_classifier import ClassifierParamExtractor
        made["classifier"] = ClassifierParamExtractor(
            str(ROOT / "models" / "e5_classifier"), device=device
        )
    if "bio_tagger" in which:
        from src.pipeline.param_extractor_bio import BIOParamExtractor
        made["bio_tagger"] = BIOParamExtractor(
            str(ROOT / "models" / "e5_bio_tagger"), schema_path=str(SCHEMA), device=device
        )
    return made


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--device", default="cpu")
    parser.add_argument(
        "--extractors", nargs="*", default=["rules", "classifier", "bio_tagger"]
    )
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--tex", type=Path, help="tabla LaTeX de la etapa 2")
    args = parser.parse_args()

    long_df = pd.read_parquet(DATA / "OEB_long_norm.parquet")
    short_df = pd.read_parquet(DATA / "OEB_short_norm.parquet")
    text_field = "text_norm" if "text_norm" in short_df.columns else short_df.columns[1]
    qtext = dict(zip(short_df["item_key"], short_df[text_field]))
    gold = gold_params(long_df)

    keys = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if isinstance(keys, dict):
        keys = keys.get("keys") or keys.get("query_item_keys")
    keys = [k for k in keys if k in gold and k in qtext]
    random.Random(args.seed).shuffle(keys)
    sample = keys[: args.n]

    extractors = build_extractors(args.extractors, args.device)

    summary = {}
    for name, extractor in extractors.items():
        ok = abstain = wrong = axes = complete = 0
        for k in sample:
            parent, g = gold[k]
            pred = extractor.extract(parent, qtext[k])
            a, b, c = compare(pred, g)
            ok += a
            abstain += b
            wrong += c
            axes += len(g)
            complete += int(a == len(g))
        summary[name] = {
            "queries": len(sample),
            "axes": axes,
            "axis_correct": ok / axes,
            "axis_abstained": abstain / axes,
            "axis_wrong": wrong / axes,
            "query_complete": complete / len(sample),
        }
        s = summary[name]
        print(
            f"{name:12s} ejes: {100*s['axis_correct']:5.1f}% correcto  "
            f"{100*s['axis_abstained']:5.1f}% sin resolver  {100*s['axis_wrong']:5.1f}% erroneo   "
            f"tupla completa: {100*s['query_complete']:5.1f}%"
        )

    print()
    tiers = {}
    for run in RUNS_FOR_TIERS:
        prof = tier_profile(run)
        if prof is None:
            print(f"sin run: {run}", file=sys.stderr)
            continue
        tiers[run] = prof
        print(
            f"{run:38s} conjunto medio {prof['mean_size']:6.2f}  "
            f"un solo item en {100*prof['singleton_share']:5.1f}%  "
            f"contiene el correcto {100*prof['gold_in_set']:5.2f}%"
        )

    if args.tex:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(render_tex(summary, tiers, len(sample)), encoding="utf-8")
        print(f"-> {args.tex}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {"seed": args.seed, "n": len(sample), "results": summary, "tiers": tiers},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
