#!/usr/bin/env python3
"""Bootstrap pareado sobre Acc@1, con correccion de Holm-Bonferroni.

Sustituye a `src/bootstrap_sigtests.ipynb` para lo que va al manuscrito. El
notebook tenia dos problemas: alineaba los sistemas sobre la **union** de sus
consultas rellenando las ausentes con 0 --lo que deflactaba cada Acc@1 por el
cociente de tamanos y produjo el 0,569 que llego al README-- y su lista de runs
estaba fijada a dos nombres en el codigo.

Aqui la muestra se **interseca** y ademas se exige que sea la canonica, con la
misma comprobacion de huella que usa `scripts/leaderboard.py`: si dos runs no
comparten poblacion no se comparan, en vez de compararse mal.

El test es el estandar de Smucker et al. (2007): se remuestrean con reemplazo
las consultas, no los sistemas, porque lo que se quiere acotar es la varianza
debida a que la muestra de consultas podria haber sido otra.

Uso:
    python scripts/bootstrap_sigtests.py --preset lexical --tex paper/tables/significance.tex
    python scripts/bootstrap_sigtests.py --runs bm25_unigram_params__k1-0.60__b-0.35 bge_m3_colbert
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_dual import load_ranking  # noqa: E402
from sample_utils import fingerprint, load_sample, short  # noqa: E402

RUNS = Path("runs")
CANONICAL_SAMPLE = Path("benchmark/query_samples/OEB_query_sample_test_16590.json")

LABELS = {
    "bm25_unigram_params__k1-0.60__b-0.35": "BM25 + parameter phrases",
    "bm25_unigram__k1-0.80__b-0.35": "BM25 unigram",
    "bm25_unibigram__k1-0.80__b-0.35": "BM25 uni+bigram",
    "tfidf_unigram_phrases_replace": "TF-IDF phrases (replace)",
    "tfidf_unigram_phrases_add": "TF-IDF phrases (add)",
    "tfidf_unigram_nostop": "TF-IDF no stopwords",
    "tfidf_unigram": "TF-IDF unigram",
    "tfidf_char_3_5": "TF-IDF char 3--5",
    "bge_m3_colbert": "BGE-M3 ColBERT",
    "dense_e5": "multilingual-e5-base",
    "structured_pipeline_rules": "Rule-based structured",
}

PRESETS = {
    # Las comparaciones lexicas de la Tabla 5, sobre los runs reales.
    "lexical": [
        "bm25_unigram_params__k1-0.60__b-0.35",
        "bm25_unigram__k1-0.80__b-0.35",
        "bm25_unibigram__k1-0.80__b-0.35",
        "tfidf_unigram_phrases_replace",
        "tfidf_unigram_phrases_add",
        "tfidf_unigram_nostop",
        "tfidf_unigram",
        "tfidf_char_3_5",
    ],
    # Un representante por familia: es la comparacion que sostiene el titular.
    "families": [
        "bm25_unigram_params__k1-0.60__b-0.35",
        "structured_pipeline_rules",
        "bge_m3_colbert",
        "dense_e5",
    ],
}


def hits(run: str) -> dict[str, int] | None:
    """Acierto en rango 1 por consulta, leido del ranking persistido."""
    path = RUNS / run / "results_top100.jsonl.gz"
    if not path.exists():
        return None
    ranking = load_ranking(path)
    return {q: int(bool(docs) and docs[0] == q) for q, docs in ranking.items()}


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n_boot: int, rng):
    """(p bilateral, IC 95 % de la diferencia) con un solo remuestreo.

    El contraste se hace sobre las diferencias **centradas**: bajo H0 la media
    es cero, asi que hay que desplazar la distribucion antes de contar cuantas
    reproducciones igualan o superan la diferencia observada. El intervalo, en
    cambio, se lee sobre las diferencias sin centrar. Son dos lecturas del mismo
    remuestreo y conviene no confundirlas.
    """
    diff = a - b
    observed = diff.mean()
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    p = float((np.abs(means - observed) >= abs(observed)).mean())
    lo, hi = np.percentile(means, [2.5, 97.5])
    return p, (float(lo), float(hi))


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni descendente, con imposicion de monotonia."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        value = min(1.0, (m - rank) * pvalues[i])
        running = max(running, value)
        adjusted[i] = running
    return adjusted


def stars(p: float) -> str:
    if p < 0.001:
        return r"$^{***}$"
    if p < 0.01:
        return r"$^{**}$"
    if p < 0.05:
        return r"$^{*}$"
    return r"\,n.s."


def tex_num(value: int) -> str:
    return f"{value:,}".replace(",", "{,}")


def render_tex(rows: list[dict], n: int, n_boot: int) -> str:
    lines = [
        r"% Generado por scripts/bootstrap_sigtests.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        # Ojo: los separadores de millar van como {,} para que LaTeX no los
        # trate como puntuacion en modo matematico. Se formatean aparte para no
        # tocar las comas del propio texto.
        rf"\caption{{Paired bootstrap on item-level Acc@1 over the ${tex_num(n)}$ queries"
        rf" of the canonical test set, ${tex_num(n_boot)}$ resamples, with $p$-values"
        r" corrected across the whole family of comparisons by the Holm--Bonferroni"
        r" step-down procedure. $\Delta$ is in percentage points.}",
        r"\label{tab:statistical_significance}",
        r"\resizebox{\textwidth}{!}{%",
        r"\begin{tabular}{llccccc}",
        r"\toprule",
        r"\textbf{System A} & \textbf{System B} & \textbf{Acc@1 A} & \textbf{Acc@1 B}"
        r" & \textbf{$\Delta$ (pp)} & \textbf{95\% CI} & \textbf{$p_{\text{Holm}}$} \\",
        r"\midrule",
    ]
    for r in rows:
        p = r["p_holm"]
        ptxt = "$<$0.0001" if p < 1e-4 else f"{p:.4f}"
        lines.append(
            f"{r['a_label']} & {r['b_label']} & {r['acc_a']:.3f} & {r['acc_b']:.3f}"
            f" & {100*(r['acc_a']-r['acc_b']):+.1f}"
            f" & [{100*r['ci_low']:+.1f}, {100*r['ci_high']:+.1f}]"
            f" & {ptxt}{stars(p)} " + r"\\"
        )
    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"}",
        r"\\[2pt]{\footnotesize $^{***}\,p<0.001$; $^{**}\,p<0.01$; $^{*}\,p<0.05$;"
        r" n.s.\ = not significant after correction.}",
        r"\end{table}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="*", default=[])
    parser.add_argument("--preset", choices=sorted(PRESETS))
    parser.add_argument("--n-boot", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--tex", type=Path)
    parser.add_argument("--out", type=Path, default=Path("eval/significance/pairs.json"))
    args = parser.parse_args()

    runs = list(args.runs) + (PRESETS[args.preset] if args.preset else [])
    if len(runs) < 2:
        parser.error("hacen falta al menos dos runs")

    expected = fingerprint(load_sample(CANONICAL_SAMPLE))
    print(f"Muestra canonica: {short(expected)}")

    series, missing = {}, []
    for run in runs:
        h = hits(run)
        if h is None:
            missing.append(run)
            continue
        fp = fingerprint(list(h))
        if fp != expected:
            print(
                f"FALLO: {run} no usa la muestra canonica ({short(fp)}); "
                "no puede entrar en una comparacion pareada.",
                file=sys.stderr,
            )
            return 1
        series[run] = h
    if missing:
        print("Sin results_top100.jsonl.gz: " + ", ".join(missing), file=sys.stderr)
        return 1

    keys = sorted(next(iter(series.values())))
    vectors = {run: np.array([h[k] for k in keys], dtype=np.float64) for run, h in series.items()}
    print(f"{len(keys):,} consultas compartidas, {len(vectors)} sistemas\n")

    rng = np.random.default_rng(args.seed)
    rows = []
    for a, b in combinations(runs, 2):
        va, vb = vectors[a], vectors[b]
        p_raw, ci = paired_bootstrap(va, vb, args.n_boot, rng)
        rows.append({
            "a": a, "b": b,
            "a_label": LABELS.get(a, a.replace("_", r"\_")),
            "b_label": LABELS.get(b, b.replace("_", r"\_")),
            "acc_a": float(va.mean()), "acc_b": float(vb.mean()),
            "ci_low": ci[0], "ci_high": ci[1],
            "p_raw": p_raw,
        })

    for row, p in zip(rows, holm([r["p_raw"] for r in rows])):
        row["p_holm"] = p

    rows.sort(key=lambda r: -abs(r["acc_a"] - r["acc_b"]))
    width = max(len(r["a"]) for r in rows)
    for r in rows:
        print(
            f"{r['a']:{width}}  vs  {r['b']:{width}}  "
            f"{r['acc_a']:.4f} {r['acc_b']:.4f}  d={100*(r['acc_a']-r['acc_b']):+6.1f}pp  "
            f"p_raw={r['p_raw']:.4f}  p_holm={r['p_holm']:.4f}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"n_queries": len(keys), "n_boot": args.n_boot, "seed": args.seed,
                    "pairs": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n-> {args.out}")
    if args.tex:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(render_tex(rows, len(keys), args.n_boot), encoding="utf-8")
        print(f"-> {args.tex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
