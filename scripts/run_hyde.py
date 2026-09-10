#!/usr/bin/env python3
"""Recupera con HyDE sobre la submuestra generada por `hyde_generate.py`.

Tres formulaciones de consulta sobre los mismos indices y las mismas consultas:

    query      : la consulta original (baseline, restringido a la submuestra)
    hyde       : solo el documento hipotetico
    query_hyde : la consulta seguida del documento hipotetico

y dos recuperadores que representan las dos familias: `bm25_unigram` (lexico) y
`bge_m3_colbert` (neuronal, el mejor del estudio). Se dejan fuera los indices con
tokens de parametros, porque ahi la pregunta no seria si HyDE ayuda sino si el
documento generado conserva la tupla --- lo que este script mide aparte, con el
extractor por reglas, y es la explicacion del resultado.

El baseline se recalcula sobre la submuestra en vez de citarse del run completo:
2.000 consultas estratificadas no tienen por que dar el mismo Acc@1 que 16.590, y
la comparacion tiene que ser pareada.

    docker exec jupyter-pytorch python /work/scripts/run_hyde.py
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
HYDE = RUNS / "hyde"
SCHEMA = DATA / "OEB_concept_schema.json"

PARENT_LEN = 6

# Mismas funciones que src/data.ipynb. Se auto-verifican contra las columnas ya
# almacenadas antes de aplicarse al texto generado.
THOUSANDS_DOT_RE = re.compile(r"(?<=\d)\.(?=\d{3}\b)")
DECIMAL_COMMA_RE = re.compile(r"(?<=\d),(?=\d)")
PERCENT_RE = re.compile(r"\s*%")
WS_RE = re.compile(r"\s+")
WORD_TOKEN_RE = re.compile(r"[a-záéíóúüñ]+|\d+(?:\.\d+)?(?:x\d+(?:\.\d+)?)?", flags=re.UNICODE)


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    text = text.lower()
    text = THOUSANDS_DOT_RE.sub("", text)
    text = DECIMAL_COMMA_RE.sub(".", text)
    text = PERCENT_RE.sub(" %", text)
    return WS_RE.sub(" ", text).strip()


def text_word(text: str) -> str:
    return " ".join(WORD_TOKEN_RE.findall(normalize_text(text)))


def selfcheck(short: pd.DataFrame) -> None:
    bad_norm = sum(1 for r in short.itertuples() if normalize_text(r.text) != r.text_norm)
    bad_word = sum(1 for r in short.itertuples() if text_word(r.text) != r.text_word)
    if bad_norm or bad_word:
        raise SystemExit(
            f"autocomprobacion fallida: text_norm difiere en {bad_norm}, "
            f"text_word en {bad_word} de {len(short)} items"
        )
    print(f"[autocomprobacion] normalizacion reproducida en los {len(short):,} items")


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


def parameter_survival(rows: list[dict], parents: dict[str, str],
                       gold_params: dict[str, dict]) -> dict:
    """Cuantos parametros del item sobreviven al documento generado.

    Es el mecanismo del resultado: si el documento hipotetico no menciona el
    numero de tubos, ninguna recuperacion posterior puede distinguir la variante.
    Se mide con el mismo extractor por reglas que usa el pipeline estructurado,
    aplicado al texto generado en vez de a la consulta.
    """
    from src.pipeline.param_extractor_rules import RuleBasedParamExtractor
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    extractor = RuleBasedParamExtractor(str(SCHEMA))

    OK, UNRESOLVED, WRONG = 0, 1, 2
    stats = {"query": [0, 0, 0], "hyde": [0, 0, 0]}
    complete = {"query": 0, "hyde": 0}
    n = 0
    for row in rows:
        key = row["item_key"]
        parent = parents.get(key)
        if parent not in schema or key not in gold_params:
            continue
        n += 1
        gold = gold_params[key]
        for source, text in (("query", row["query"]), ("hyde", row["hypothetical"])):
            predicted = extractor.extract(parent, text)
            lowered = {str(k).strip().lower(): v for k, v in predicted.items()}
            ok = 0
            for label, value in gold.items():
                got = lowered.get(label.strip().lower())
                if got is None:
                    stats[source][UNRESOLVED] += 1
                elif str(got).strip().lower() == str(value).strip().lower():
                    stats[source][OK] += 1
                    ok += 1
                else:
                    stats[source][WRONG] += 1
            complete[source] += int(ok == len(gold))

    out = {}
    for source, (ok, unresolved, wrong) in stats.items():
        total = ok + unresolved + wrong
        out[source] = {
            "axes": total,
            "correct": ok / total if total else 0.0,
            "unresolved": unresolved / total if total else 0.0,
            "wrong": wrong / total if total else 0.0,
            "complete_tuple": complete[source] / n if n else 0.0,
        }
    out["queries"] = n
    return out


def idf_mass(rows: list[dict], index_name: str = "bm25_unigram") -> dict:
    """Cuanto peso idf mete el documento generado en la consulta.

    Es la explicacion del resultado de BM25, y no es la que uno esperaria. El
    catalogo entero usa 337 tipos de palabra, todos tecnicos y todos frecuentes.
    La prosa que escribe un LLM esta hecha en su mayor parte de palabras que en
    esta coleccion son **rarisimas** --funcionales como "se", genericas como
    "conexion"-- y a las que BM25 asigna por tanto un idf maximo. El documento
    hipotetico no diluye la consulta: la sepulta bajo terminos que el modelo
    considera muy discriminantes y que no discriminan nada.
    """
    import unicodedata

    index_dir = INDEX / index_name
    vocab = json.loads((index_dir / "data" / "vocab.json").read_text(encoding="utf-8"))
    idf = np.load(index_dir / "data" / "idf.npy")

    def strip_accents(text: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", text)
                       if unicodedata.category(c) != "Mn")

    # El CountVectorizer del indice normaliza acentos; hay que hacer lo mismo
    # para mirar el vocabulario, o no se encuentra ningun termino.
    lookup = {strip_accents(k): v for k, v in vocab.items()}

    def terms(text: str) -> set[str]:
        return {t for t in (strip_accents(w) for w in text_word(text).split())
                if t in lookup}

    q_mass, h_mass, added = [], [], []
    for row in rows:
        tq, th = terms(row["query"]), terms(row["hypothetical"])
        q_mass.append(sum(idf[lookup[t]] for t in tq))
        h_mass.append(sum(idf[lookup[t]] for t in th))
        added.append(len(th - tq))

    return {
        "vocabulary": len(vocab),
        "query_idf_mass": float(np.mean(q_mass)),
        "hyde_idf_mass": float(np.mean(h_mass)),
        "terms_added": float(np.mean(added)),
        "max_idf": float(idf.max()),
    }


def render_tex(summary: dict, survival: dict, n: int) -> str:
    labels = {"query": "Original query", "hyde": "Hypothetical document only",
              "query_hyde": "Query + hypothetical document"}
    retrievers = {"bm25_unigram": "BM25 unigram", "bge_m3_colbert": "BGE-M3 ColBERT"}
    lines = [
        r"% Generado por scripts/run_hyde.py -- no editar a mano.",
        r"\begin{table}[ht]",
        r"\centering",
        r"\caption{HyDE on a stratified subsample of $n=" + f"{n:,}".replace(",", "{,}")
        + r"$ test queries. The hypothetical document is generated by Phi-4 from the"
        r" query alone. Baseline rows are the same retrievers on the same queries, so"
        r" every comparison is paired.}",
        r"\label{tab:hyde}",
        r"\begin{tabular}{llccc}",
        r"\toprule",
        r"\textbf{Retriever} & \textbf{Query representation} & \textbf{Acc@1}"
        r" & \textbf{Recall@10} & \textbf{Parent Acc@1} \\",
        r"\midrule",
    ]
    for ri, (retriever, rlabel) in enumerate(retrievers.items()):
        if ri:
            lines.append(r"\midrule")
        for form, flabel in labels.items():
            m = summary.get(f"{retriever}::{form}")
            if not m:
                continue
            lines.append(
                f"{rlabel if form == 'query' else ''} & {flabel}"
                f" & {m['item']['Acc@1']:.3f} & {m['item']['Recall@10']:.3f}"
                f" & {m['parent']['Acc@1']:.3f} " + r"\\"
            )
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyde", type=Path, default=HYDE / "hypothetical.jsonl")
    parser.add_argument("--retrievers", nargs="*",
                        default=["bm25_unigram", "bge_m3_colbert"])
    parser.add_argument("--k", type=int, default=100)
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--save-runs", action="store_true")
    parser.add_argument("--reuse", action="store_true",
                        help="reutiliza los rankings ya persistidos en vez de recuperar")
    parser.add_argument("--tex", type=Path)
    parser.add_argument("--out", type=Path, default=WORK / "eval" / "hyde" / "results.json")
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.hyde.open(encoding="utf-8") if line.strip()]
    rows.sort(key=lambda r: r["item_key"])
    print(f"{len(rows):,} documentos hipoteticos ({rows[0]['model']})")

    short = pd.read_parquet(
        DATA / "OEB_short_norm.parquet",
        columns=["item_key", "parent_key", "text", "text_norm", "text_word", "parameters_norm"],
    )
    selfcheck(short.head(2000))

    by_key = short.set_index("item_key")
    keys = [r["item_key"] for r in rows if r["item_key"] in by_key.index]
    rows = [r for r in rows if r["item_key"] in by_key.index]
    gold = keys

    parents = dict(zip(short["item_key"], short["parent_key"]))
    gold_params = {}
    for row in short.itertuples():
        params = {}
        for axis_key in ("A", "B", "C", "D", "F"):
            axis = row.parameters_norm[axis_key]
            if axis is not None:
                params[axis["label_norm"]] = axis["values"][0]["value_norm"]
        gold_params[row.item_key] = params

    print("[parametros] cuantos sobreviven al documento generado...")
    survival = parameter_survival(rows, parents, gold_params)
    for source in ("query", "hyde"):
        s = survival[source]
        print(f"  {source:6s} ejes: {100*s['correct']:5.1f}% correcto  "
              f"{100*s['unresolved']:5.1f}% ausente  {100*s['wrong']:5.1f}% erroneo   "
              f"tupla completa: {100*s['complete_tuple']:5.1f}%")

    mass = idf_mass(rows)
    print(f"[idf] vocabulario {mass['vocabulary']} tipos, idf maximo {mass['max_idf']:.2f}. "
          f"Masa idf media: consulta {mass['query_idf_mass']:.1f}, "
          f"hipotetico {mass['hyde_idf_mass']:.1f} "
          f"(+{mass['terms_added']:.1f} terminos nuevos del vocabulario)")

    formulations = {
        "query": [by_key.at[k, "text"] for k in keys],
        "hyde": [r["hypothetical"] for r in rows],
        "query_hyde": [f"{by_key.at[k, 'text']} {r['hypothetical']}"
                       for k, r in zip(keys, rows)],
    }

    summary = {}
    for retriever in args.retrievers:
        meta = json.loads((INDEX / retriever / "meta.json").read_text(encoding="utf-8"))
        field = meta.get("text_field")
        prepare = {"text_word": text_word, "text_norm": normalize_text}.get(field)
        if prepare is None:
            print(f"[SALTO] {retriever}: text_field {field!r} no soportado", file=sys.stderr)
            continue

        from importlib import import_module
        module = import_module(f"retrievers.{retriever}")
        searcher = module.load(INDEX / retriever)
        ext = np.asarray(searcher.external_ids, dtype=object)
        print(f"\n{retriever} (campo {field})")

        for name, raw in formulations.items():
            texts = [prepare(t) for t in raw]
            saved = RUNS / "hyde" / f"{retriever}__{name}" / f"results_top{args.k}.jsonl.gz"
            if args.reuse and saved.exists():
                # Recuperar con ColBERT sobre documentos generados cuesta ~45 min
                # por formulacion; releer el ranking persistido cuesta segundos y
                # da exactamente lo mismo.
                ranking = {}
                with gzip.open(saved, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        record = json.loads(line)
                        ranking[record["query_item_key"]] = [
                            c["index_item_key"] for c in record["candidates"]
                        ]
                top_keys = np.array([ranking[k] for k in gold], dtype=object)
                top_idx = top_sc = None
                print(f"  {name:11s} (reutilizado {saved.name})")
            else:
                tops, scores = [], []
                for start in range(0, len(texts), args.batch):
                    idx, sc = searcher.search_batch(texts[start:start + args.batch], k=args.k)
                    tops.append(idx)
                    scores.append(sc)
                top_idx = np.vstack(tops)
                top_sc = np.vstack(scores)
                top_keys = ext[top_idx]
            metrics = evaluate(top_keys, gold)
            summary[f"{retriever}::{name}"] = metrics
            print(f"  {name:11s} item Acc@1={metrics['item']['Acc@1']:.4f}  "
                  f"R@10={metrics['item']['Recall@10']:.4f}  "
                  f"parent Acc@1={metrics['parent']['Acc@1']:.4f}")

            if args.save_runs and top_idx is not None:
                run_dir = RUNS / "hyde" / f"{retriever}__{name}"
                run_dir.mkdir(parents=True, exist_ok=True)
                with gzip.open(run_dir / f"results_top{args.k}.jsonl.gz", "wt",
                               encoding="utf-8") as fh:
                    for i, key in enumerate(gold):
                        fh.write(json.dumps({
                            "query_id": f"q_{i:06d}", "query_item_key": key,
                            "query_text": texts[i],
                            "candidates": [{"rank": r + 1, "doc_id": int(top_idx[i, r]),
                                            "index_item_key": str(top_keys[i, r]),
                                            "score": float(top_sc[i, r])}
                                           for r in range(args.k)],
                            "score_info": {"family": "mixed", "higher_is_better": True},
                            "meta": {"method": retriever, "variant": f"hyde_{name}",
                                     "index_path": str(INDEX / retriever)},
                        }, ensure_ascii=False) + "\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"queries": len(gold), "survival": survival,
                                    "idf": mass, "results": summary},
                                   indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n-> {args.out}")
    if args.tex:
        args.tex.parent.mkdir(parents=True, exist_ok=True)
        args.tex.write_text(render_tex(summary, survival, len(gold)), encoding="utf-8")
        print(f"-> {args.tex}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
