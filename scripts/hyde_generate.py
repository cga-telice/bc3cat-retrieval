#!/usr/bin/env python3
"""Genera el documento hipotetico de HyDE para una submuestra de consultas.

HyDE (Gao et al., 2023) pide al modelo que escriba el documento que responderia
a la consulta y recupera con ese texto en lugar de con la consulta. La prediccion
para este banco de pruebas es que **perjudique**: el objetivo ya contiene el
94,1 % de los tokens de la consulta y el 99,96 % de sus valores numericos, asi
que sustituir la consulta por texto generado solo puede diluir esa coincidencia,
y ademas arriesga alterar los numeros, que es justo lo que distingue una variante
de otra.

Se corre sobre una submuestra estratificada por plantilla, no sobre las 16.590:
a ~4 s por generacion, el conjunto completo serian ~18 h de LLM para medir un
resultado que se ve con 2.000. La submuestra se versiona igual que las demas y
los baselines se recalculan sobre ella, de modo que la comparacion es pareada.

Se ejecuta DENTRO del contenedor, que es quien alcanza a `ollama`:

    docker exec jupyter-pytorch python /work/scripts/hyde_generate.py --n 2000

Es reanudable: cada generacion se escribe segun se produce y una segunda
ejecucion salta las que ya estan.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

WORK = Path("/work") if Path("/work").exists() else Path(__file__).resolve().parents[1]
DATA = WORK / "data" / "processed"
SAMPLES = WORK / "benchmark" / "query_samples"
TEST_SAMPLE = SAMPLES / "OEB_query_sample_test_16590.json"
OUT_DIR = WORK / "runs" / "hyde"

PROMPT = (
    "Eres un tecnico redactor de bases de precios de obra ferroviaria.\n"
    "\n"
    "A partir de la siguiente descripcion resumida de una partida de obra, "
    "redacta el texto descriptivo completo tal y como aparecerian en el pliego: "
    "unidad de obra, materiales, dimensiones y condiciones de ejecucion.\n"
    "\n"
    "Descripcion resumida: \"{query}\"\n"
    "\n"
    "Escribe unicamente el texto descriptivo, sin encabezados ni comentarios.\n"
)


def stratified_sample(keys: list[str], parents: dict[str, str], n: int, seed: int) -> list[str]:
    """Reparte la submuestra entre plantillas en proporcion a su tamano.

    Un muestreo uniforme dedicaria la mitad de las generaciones a las seis
    plantillas de 6.336 variantes y dejaria las pequenas sin representar; uno
    estrictamente proporcional haria lo contrario. Se toma la raiz cuadrada del
    tamano como compromiso, y se garantiza al menos una consulta por plantilla.
    """
    by_parent: dict[str, list[str]] = {}
    for k in keys:
        by_parent.setdefault(parents.get(k, "?"), []).append(k)

    weights = {p: len(v) ** 0.5 for p, v in by_parent.items()}
    total = sum(weights.values())
    rng = random.Random(seed)

    chosen: list[str] = []
    for parent, group in sorted(by_parent.items()):
        take = max(1, round(n * weights[parent] / total))
        take = min(take, len(group))
        chosen.extend(rng.sample(sorted(group), take))

    rng.shuffle(chosen)
    return sorted(chosen[:n])


def generate(url: str, model: str, query: str, num_predict: int, timeout: int) -> str:
    body = json.dumps({
        "model": model,
        "prompt": PROMPT.format(query=query),
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0.0},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{url}/api/generate", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)["response"].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--model", default="phi4:latest")
    parser.add_argument("--url", default="http://ollama:11434")
    parser.add_argument("--num-predict", type=int, default=110)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--out", type=Path, default=OUT_DIR / "hypothetical.jsonl")
    args = parser.parse_args()

    short = pd.read_parquet(DATA / "OEB_short_norm.parquet",
                            columns=["item_key", "parent_key", "text"])
    qtext = dict(zip(short["item_key"], short["text"]))
    parents = dict(zip(short["item_key"], short["parent_key"]))

    payload = json.loads(TEST_SAMPLE.read_text(encoding="utf-8"))
    keys = [k for k in payload["query_item_keys"] if k in qtext]
    sample = stratified_sample(keys, parents, args.n, args.seed)

    sample_file = SAMPLES / f"OEB_query_sample_hyde_{len(sample)}.json"
    if not sample_file.exists():
        import hashlib
        fp = hashlib.sha256("\n".join(sorted(sample)).encode("utf-8")).hexdigest()
        sample_file.write_text(json.dumps({
            "collection": "OEB", "split": "hyde", "n": len(sample), "sha256": fp,
            "seed": args.seed,
            "provenance": "submuestra estratificada por plantilla del split de test de 16.590",
            "query_item_keys": sorted(sample),
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[sample] {sample_file} ({len(sample)} consultas, sha256 {fp[:12]})")
    else:
        print(f"[sample] reutilizando {sample_file}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if args.out.exists():
        with args.out.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    done.add(json.loads(line)["item_key"])
        print(f"[reanudar] ya generadas: {len(done)}")

    pending = [k for k in sample if k not in done]
    print(f"[generar] {len(pending)} con {args.model}, {args.workers} en paralelo")
    if not pending:
        return 0

    started = time.time()
    written = 0
    failures = 0
    with args.out.open("a", encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            def work(key: str):
                try:
                    return key, generate(args.url, args.model, qtext[key],
                                         args.num_predict, args.timeout), None
                except (urllib.error.URLError, TimeoutError, OSError, KeyError) as exc:
                    return key, None, repr(exc)

            for key, text, error in pool.map(work, pending):
                if error is not None:
                    failures += 1
                    print(f"  [fallo] {key}: {error}", file=sys.stderr)
                    continue
                fh.write(json.dumps({"item_key": key, "query": qtext[key],
                                     "hypothetical": text, "model": args.model},
                                    ensure_ascii=False) + "\n")
                fh.flush()
                written += 1
                if written % 50 == 0:
                    rate = written / (time.time() - started)
                    left = (len(pending) - written) / rate if rate else 0
                    print(f"  [{written}/{len(pending)}] {rate:.2f}/s, quedan {left/60:.0f} min")

    print(f"\n{written} generadas, {failures} fallos, {(time.time()-started)/60:.1f} min")
    print(f"-> {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
