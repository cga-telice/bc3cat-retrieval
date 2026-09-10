#!/usr/bin/env python3
"""BM25 + frases de parametros, pero calculando las frases en vez de leerlas.

`bm25_unigram_params` consulta con el campo `text_word_params`, que anade a la
consulta unos tokens `param_<eje>_<valor>` construidos a partir del campo
`parameters` del registro. Como la consulta y el objetivo son el mismo item, esos
tokens son identicos en los dos lados (47.513 de 47.513) y unicos dentro de la
plantilla (47.513 de 47.513). La consulta llega, por tanto, con la tupla de
parametros ya resuelta contra el esquema, que es justamente lo que el pipeline
estructurado tiene que extraer.

Este script mide la version realizable del mismo sistema: los tokens se calculan
desde el texto de la consulta con el extractor por reglas, sobre la plantilla que
propone la etapa 1 (E5) --- exactamente los componentes que ya usa el pipeline
estructurado--- y se comparan cuatro formulaciones:

    stored     : la tupla leida del registro          (lo publicado)
    computed   : plantilla de E5   + extractor por reglas
    computed_o : plantilla correcta + extractor por reglas
    text_only  : sin tokens de parametros

El script se auto-verifica antes de medir nada: reconstruye los `param_tokens`
almacenados desde `parameters_norm` y falla si no coinciden exactamente.

    docker exec jupyter-pytorch python /work/scripts/probe_computed_params.py
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WORK = Path("/work") if Path("/work").exists() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "src"))
sys.path.insert(0, str(WORK))

DATA = WORK / "data" / "processed"
INDEX = WORK / "index"
RUNS = WORK / "runs"
SAMPLE = WORK / "benchmark" / "query_samples" / "OEB_query_sample_test_16590.json"
SCHEMA = DATA / "OEB_concept_schema.json"

PARENT_LEN = 6
_WORD = re.compile(r"[a-záéíóúüñ0-9]+")


def slug_words(text: str) -> str:
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    return "_".join(_WORD.findall(text.lower()))


def canon_comparators(text: str) -> str:
    text = text.replace("≥", ">=").replace("≤", "<=")
    text = re.sub(r"\s*>=\s*", " ge ", text)
    text = re.sub(r"\s*<=\s*", " le ", text)
    text = re.sub(r"\s*>\s*", " gt ", text)
    text = re.sub(r"\s*<\s*", " lt ", text)
    return text


def token(label: str, value: str) -> str:
    """Mismo token que `build_param_tokens` de src/data.ipynb."""
    return f"param_{slug_words(label) or 'label'}_{slug_words(canon_comparators(value)) or 'value'}"


def selfcheck(short: pd.DataFrame) -> None:
    """Reconstruye los param_tokens almacenados. Sin esto, todo lo demas sobra."""
    bad = 0
    for row in short.itertuples():
        rebuilt = []
        for block in row.parameters_norm.values():
            if block is None:
                continue
            label = block.get("label_norm", "")
            for value in block.get("values", []):
                rebuilt.append(token(label, value.get("value_norm", "")))
        if rebuilt != list(row.param_tokens):
            bad += 1
            if bad <= 3:
                print(f"  DISCREPA {row.item_key}: {rebuilt} != {list(row.param_tokens)}",
                      file=sys.stderr)
    if bad:
        raise SystemExit(f"autocomprobacion fallida en {bad} items: el constructor de tokens no es el mismo")
    print(f"[autocomprobacion] param_tokens reconstruidos en los {len(short):,} items")


def stage1_templates(item_to_parent: dict[str, str]) -> dict[str, str]:
    """Plantilla propuesta por la etapa 1: el padre del top-1 de dense_e5."""
    path = RUNS / "dense_e5" / "results_top100.jsonl.gz"
    out = {}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            top = record["candidates"][0]["index_item_key"]
            out[record["query_item_key"]] = item_to_parent.get(top)
    return out


def evaluate(top_keys: np.ndarray, gold: list[str]) -> dict:
    gold_arr = np.asarray(gold, dtype=object)[:, None]
    hit = top_keys == gold_arr
    parent_top = np.vectorize(lambda k: k[:PARENT_LEN])(top_keys)
    parent_gold = np.asarray([g[:PARENT_LEN] for g in gold], dtype=object)[:, None]

    def block(h):
        rank = np.where(h.any(axis=1), h.argmax(axis=1) + 1, 0)
        rr = np.where((rank > 0) & (rank <= 10), 1.0 / np.maximum(rank, 1), 0.0)
        return {"Acc@1": float(h[:, 0].mean()),
                "Recall@5": float(h[:, :5].any(axis=1).mean()),
                "Recall@10": float(h[:, :10].any(axis=1).mean()),
                "MRR@10": float(rr.mean())}

    return {"item": block(hit), "parent": block(parent_top == parent_gold)}


ROWS = [
    ("text_only", "Query text alone"),
    ("signature", "Parameter tuple alone"),
    ("stored", "Query text + tuple read from the catalog record"),
    ("computed", "Query text + tuple extracted from the query"),
]


def render_tex(summary: dict, extra: dict, n: int) -> str:
    lines = [
        r"% Generado por scripts/probe_computed_params.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{What the parameter tuple contributes, and how it is used. All rows"
        r" share one BM25 index over the catalog text plus the parameter tokens"
        r" ($k_1{=}0.60$, $b{=}0.35$) and differ only in how the query is formed, except"
        r" the last, which uses the same extracted tuple as an exact filter instead of as"
        r" query terms. Canonical test set, $n=" + f"{n:,}".replace(",", "{,}") + r"$.}",
        r"\label{tab:param_tokens}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"\textbf{Query representation} & \textbf{Acc@1} & \textbf{Recall@5}"
        r" & \textbf{MRR@10} & \textbf{Parent Acc@1} \\",
        r"\midrule",
    ]
    for key, label in ROWS:
        m = summary.get(key)
        if not m:
            continue
        lines.append(
            f"{label} & {m['item']['Acc@1']:.3f} & {m['item']['Recall@5']:.3f}"
            f" & {m['item']['MRR@10']:.3f} & {m['parent']['Acc@1']:.3f} " + r"\\"
        )
    if extra:
        lines.append(r"\midrule")
        lines.append(
            r"Same extracted tuple, as an exact filter"
            f" & {extra['Acc@1']:.3f} & {extra['Recall@5']:.3f}"
            f" & {extra['MRR@10']:.3f} & {extra['parent']:.3f} " + r"\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def structured_row() -> dict | None:
    """La fila del pipeline estructurado: misma tupla, usada como filtro."""
    path = RUNS / "structured_pipeline_rules" / "metrics_dual.json"
    if not path.exists():
        return None
    by_target = {r["target"]: r for r in json.loads(path.read_text(encoding="utf-8"))
                 if r.get("scope") == "overall"}
    item = by_target["item"]
    return {"Acc@1": item["Acc@1"], "Recall@5": item["Recall@5"],
            "MRR@10": item["MRR"], "parent": by_target["parent"]["Acc@1"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="bm25_unigram_params__k1-0.60__b-0.35")
    parser.add_argument("--k", type=int, default=100)
    parser.add_argument("--batch", type=int, default=2000)
    parser.add_argument("--save-runs", action="store_true")
    parser.add_argument("--tex", type=Path)
    parser.add_argument("--out", type=Path,
                        default=WORK / "eval" / "param_tokens" / "computed.json")
    args = parser.parse_args()

    short = pd.read_parquet(
        DATA / "OEB_short_norm.parquet",
        columns=["item_key", "parent_key", "text", "text_word", "text_word_params",
                 "param_tokens", "parameters_norm"],
    )
    selfcheck(short)

    long_df = pd.read_parquet(DATA / "OEB_long_norm.parquet", columns=["item_key", "parent_key"])
    item_to_parent = dict(zip(long_df["item_key"], long_df["parent_key"]))

    wanted = set(json.loads(SAMPLE.read_text(encoding="utf-8"))["query_item_keys"])
    short = short[short["item_key"].isin(wanted)].sort_values("item_key").reset_index(drop=True)
    gold = short["item_key"].tolist()
    print(f"{len(gold):,} consultas")

    from src.pipeline.param_extractor_rules import RuleBasedParamExtractor
    extractor = RuleBasedParamExtractor(str(SCHEMA))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    predicted = stage1_templates(item_to_parent)

    def computed_tokens(item_key: str, text: str, parent: str | None) -> list[str]:
        if parent is None or parent not in schema:
            return []
        params = extractor.extract(parent, text)
        return [token(label, value) for label, value in params.items() if value is not None]

    print("[extraer] etapa 2 sobre las consultas...")
    tok_pred, tok_oracle = [], []
    for row in short.itertuples():
        tok_pred.append(computed_tokens(row.item_key, row.text, predicted.get(row.item_key)))
        tok_oracle.append(computed_tokens(row.item_key, row.text, row.parent_key))

    stored = [list(t) for t in short["param_tokens"]]
    exact_pred = sum(1 for a, b in zip(tok_pred, stored) if sorted(a) == sorted(b))
    exact_or = sum(1 for a, b in zip(tok_oracle, stored) if sorted(a) == sorted(b))
    n = len(stored)
    print(f"  tokens calculados identicos a los del registro: "
          f"etapa 1 de E5 {exact_pred}/{n} = {100*exact_pred/n:.2f}%   "
          f"plantilla correcta {exact_or}/{n} = {100*exact_or/n:.2f}%")

    formulations = {
        "stored": list(short["text_word_params"]),
        "computed": [f"{t} {' '.join(k)}".strip() for t, k in zip(short["text_word"], tok_pred)],
        "computed_oracle": [f"{t} {' '.join(k)}".strip() for t, k in zip(short["text_word"], tok_oracle)],
        "text_only": list(short["text_word"]),
        # La tupla sola, sin texto: mide cuanto discrimina la firma por si misma.
        "signature": [" ".join(k) for k in stored],
    }

    from retrievers.bm25_unigram_params import load
    searcher = load(INDEX / args.index)
    ext = np.asarray(searcher.external_ids, dtype=object)

    summary = {"tokens_match_stage1": exact_pred / n, "tokens_match_oracle": exact_or / n}
    for name, texts in formulations.items():
        tops, scores = [], []
        for start in range(0, len(texts), args.batch):
            idx, sc = searcher.search_batch(texts[start:start + args.batch], k=args.k)
            tops.append(idx)
            scores.append(sc)
        top_idx = np.vstack(tops)
        top_sc = np.vstack(scores)
        top_keys = ext[top_idx]
        metrics = evaluate(top_keys, gold)
        summary[name] = metrics
        print(f"  {name:16s} item Acc@1={metrics['item']['Acc@1']:.4f}  "
              f"R@5={metrics['item']['Recall@5']:.4f}  "
              f"MRR@10={metrics['item']['MRR@10']:.4f}  "
              f"parent Acc@1={metrics['parent']['Acc@1']:.4f}")

        if args.save_runs:
            run_dir = RUNS / f"{args.index}__q-{name}"
            run_dir.mkdir(parents=True, exist_ok=True)
            with gzip.open(run_dir / f"results_top{args.k}.jsonl.gz", "wt", encoding="utf-8") as fh:
                for i, key in enumerate(gold):
                    fh.write(json.dumps({
                        "query_id": f"q_{i:06d}", "query_item_key": key, "query_text": texts[i],
                        "candidates": [{"rank": r + 1, "doc_id": int(top_idx[i, r]),
                                        "index_item_key": str(top_keys[i, r]),
                                        "score": float(top_sc[i, r])} for r in range(args.k)],
                        "score_info": {"family": "bm25", "higher_is_better": True},
                        "meta": {"method": "bm25", "variant": f"{args.index}__q-{name}",
                                 "index_path": str(INDEX / args.index),
                                 "query_formulation": name},
                    }, ensure_ascii=False) + "\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"index": args.index, "queries": n, "results": summary},
                                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {args.out}")
    if args.tex:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(render_tex(summary, structured_row(), n), encoding="utf-8")
        print(f"-> {args.tex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
