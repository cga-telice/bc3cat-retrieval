#!/usr/bin/env python3
"""Aplica las correcciones de codigo de la revision AUTCON a los notebooks.

Los notebooks son JSON con el codigo troceado en listas de lineas, asi que
editarlos a mano es propenso a romper el fichero. Este script los carga como
JSON, sustituye bloques de lineas exactos y los vuelve a escribir, de forma
idempotente y verificable.

Cada parche lleva el identificador del registro de correcciones
(docs/reviews/CORRECTIONS_LOG.md) para que el cambio quede trazado.

Uso:
    python scripts/apply_code_corrections.py --check    # solo informa
    python scripts/apply_code_corrections.py            # aplica
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Patch:
    ident: str
    notebook: str
    rationale: str
    old: list[str]
    new: list[str]
    applied_marker: str = field(default="")
    # Algunos defectos estan copiados en varias celdas del mismo notebook y hay
    # que corregirlos en todas.
    all_occurrences: bool = field(default=False)

    def __post_init__(self) -> None:
        # Una linea del bloque nuevo que no exista en el viejo sirve para
        # detectar que el parche ya esta aplicado.
        if not self.applied_marker:
            novel = [ln for ln in self.new if ln not in self.old]
            self.applied_marker = novel[0] if novel else self.new[0]


CANONICAL_SAMPLE_PATH = "/work/benchmark/query_samples/OEB_query_sample_test_16590.json"

PATCHES: list[Patch] = [
    Patch(
        ident="C1-param",
        notebook="src/retrieve.ipynb",
        rationale=(
            "Expone la muestra de consultas como parametro de papermill, para poder "
            "lanzar el mismo notebook sobre test o sobre validacion sin editarlo."
        ),
        old=[
            "RANDOM_SAMPLE = 16590   \n",
        ],
        new=[
            "# Fichero versionado con los identificadores de consulta. Sustituye al\n",
            "# muestreo en memoria; RANDOM_SAMPLE solo actua si este queda vacio.\n",
            f'QUERY_SAMPLE  = "{CANONICAL_SAMPLE_PATH}"\n',
            "RANDOM_SAMPLE = 16590   \n",
        ],
    ),
    Patch(
        ident="C5-rungroup-param",
        notebook="src/retrieve.ipynb",
        rationale=(
            "Permite escribir los runs de seleccion de hiperparametros en un "
            "directorio aparte, para que no sobrescriban los que luego se reportan."
        ),
        old=[
            'METHOD_NAME   = "bge_m3_colbert"\n',
        ],
        new=[
            'METHOD_NAME   = "bge_m3_colbert"\n',
            "# Subdirectorio bajo runs/. Vacio para el test que se reporta; \"val\" para\n",
            "# los barridos de seleccion, que no deben mezclarse con aquel.\n",
            'RUN_GROUP     = ""\n',
        ],
    ),
    Patch(
        ident="C5-rungroup-dir",
        notebook="src/retrieve.ipynb",
        rationale=(
            "El estudio publicado selecciono (k1,b), pesos de fusion y beta sobre el "
            "mismo conjunto que despues reporta. Separar los directorios es el primer "
            "paso para que la seleccion se haga en validacion."
        ),
        old=[
            'RUN_DIR      = Path(f"/work/runs/{METHOD_NAME}")\n',
        ],
        new=[
            'RUN_DIR      = Path(f"/work/runs/{RUN_GROUP}/{METHOD_NAME}" if RUN_GROUP else f"/work/runs/{METHOD_NAME}")\n',
        ],
    ),
    Patch(
        ident="C1-load",
        notebook="src/retrieve.ipynb",
        rationale=(
            "`.sample(n, random_state=42)` es posicional: con el mismo seed pero "
            "distinto orden de filas produce subconjuntos distintos. Como cada YAML "
            "declara un fichero de queries diferente (short_feats.parquet, "
            "resumen.json, short_norm.parquet), el estudio publicado acabo "
            "conviviendo con tres muestras presentadas como una sola."
        ),
        old=[
            "# 1) Optional: take a random subset (also shuffles it)\n",
            "if RANDOM_SAMPLE is not None:\n",
            "    queries_df = queries_df.sample(n=int(RANDOM_SAMPLE), random_state=42).copy()\n",
            "# 2) Else: just shuffle order (no change to membership)\n",
            "elif SHUFFLE:\n",
            "    queries_df = queries_df.sample(frac=1.0, random_state=42).copy()\n",
        ],
        new=[
            "# 1) Muestra fija, cargada de un fichero versionado y verificada por huella.\n",
            "if QUERY_SAMPLE:\n",
            "    import hashlib as _hashlib, json as _json\n",
            "    _payload = _json.loads(Path(QUERY_SAMPLE).read_text(encoding='utf-8'))\n",
            "    _wanted = set(_payload['query_item_keys'])\n",
            "    _fp = _hashlib.sha256('\\n'.join(sorted(_wanted)).encode('utf-8')).hexdigest()\n",
            "    if _payload.get('sha256') and _fp != _payload['sha256']:\n",
            "        raise ValueError(f\"{QUERY_SAMPLE}: huella {_fp[:12]} != declarada {_payload['sha256'][:12]}\")\n",
            "    queries_df = queries_df[queries_df['item_key'].astype(str).isin(_wanted)].copy()\n",
            "    if len(queries_df) != len(_wanted):\n",
            "        raise ValueError(f\"El fichero de queries aporta {len(queries_df)} de las {len(_wanted)} consultas de la muestra\")\n",
            "    queries_df = queries_df.sort_values('item_key').reset_index(drop=True)\n",
            "    print(f\"[SAMPLE] {len(queries_df):,} consultas de {QUERY_SAMPLE} (sha256 {_fp[:12]})\")\n",
            "# 2) Legado: muestreo aleatorio en memoria. No usar para resultados publicables.\n",
            "elif RANDOM_SAMPLE is not None:\n",
            "    queries_df = queries_df.sample(n=int(RANDOM_SAMPLE), random_state=42).copy()\n",
            "elif SHUFFLE:\n",
            "    queries_df = queries_df.sample(frac=1.0, random_state=42).copy()\n",
        ],
    ),
    Patch(
        ident="C6-hybdir",
        notebook="src/error_analysis.ipynb",
        rationale=(
            "Las fusiones se escriben en runs/hybrids/<nombre>, pero el analisis las "
            "buscaba en runs/<nombre>, donde habia quedado una copia obsoleta de la "
            "ejecucion publicada. Habria analizado los resultados antiguos creyendo que "
            "eran los nuevos."
        ),
        old=[
            "    run_dir = RUNS_DIR / m\n",
        ],
        new=[
            "    # Las fusiones viven bajo runs/hybrids/; el resto, directamente en runs/.\n",
            "    run_dir = RUNS_DIR / m\n",
            '    if not run_dir.exists() and (RUNS_DIR / "hybrids" / m).exists():\n',
            '        run_dir = RUNS_DIR / "hybrids" / m\n',
        ],
    ),
    Patch(
        ident="C6-errors",
        notebook="src/error_analysis.ipynb",
        rationale=(
            "El analisis de errores intersectaba en silencio las consultas de los tres "
            "metodos y acababa trabajando sobre 5.844 de 16.590 sin que nada lo "
            "advirtiera. El manuscrito nunca lo menciona y sus captions declaran "
            "n=16.590. Con la muestra unificada la interseccion debe ser la identidad; "
            "si no lo es, es un error de datos y hay que detenerse."
        ),
        old=[
            "common_q = sorted(common_q)\n",
            'print(f"Common queries across methods: {len(common_q)}")\n',
        ],
        new=[
            "common_q = sorted(common_q)\n",
            "_universo = set().union(*[set(df['query_item_key']) for df in method_runs.values()])\n",
            "if len(common_q) != len(_universo):\n",
            "    raise ValueError(\n",
            '        f"Los metodos analizados no comparten muestra: {len(common_q):,} consultas "\n',
            '        f"comunes frente a {len(_universo):,} en la union. El analisis de errores "\n',
            '        f"sobre una interseccion parcial no es comparable con las metricas."\n',
            "    )\n",
            'print(f"Queries analysed: {len(common_q):,} (identical across all methods)")\n',
        ],
    ),
    Patch(
        ident="C6",
        notebook="src/bootstrap_sigtests.ipynb",
        all_occurrences=True,
        rationale=(
            "Alinear los runs sobre la UNION de consultas rellenando con 0 las que un "
            "run no evaluo cuenta esas ausencias como fallos. Con muestras distintas "
            "eso deflacta cada Acc@1 por el cociente de denominadores: bm25_unigram "
            "aparece como 0,569 en eval/bootstrap_global (union de 25.321 consultas) "
            "en lugar de 0,869. Esas cifras deflactadas llegaron al README publicado."
        ),
        old=[
            "all_queries = sorted(set().union(*[s.index for s in runs.values()]))\n",
            "X = pd.DataFrame({m: s.reindex(all_queries).fillna(0).astype(int) for m, s in runs.items()})\n",
        ],
        new=[
            "# Interseccion, no union: comparar sistemas exige que hayan visto las mismas\n",
            "# consultas. Si no coinciden es un error de datos, no algo que rellenar.\n",
            "_indices = [set(s.index) for s in runs.values()]\n",
            "all_queries = sorted(set.intersection(*_indices)) if _indices else []\n",
            "_union = set().union(*_indices) if _indices else set()\n",
            "if len(all_queries) != len(_union):\n",
            "    raise ValueError(\n",
            '        f"Los runs comparados no evaluan la misma muestra: {len(all_queries):,} "\n',
            '        f"consultas comunes frente a {len(_union):,} en la union. "\n',
            '        f"Reejecutalos sobre la muestra canonica antes de comparar."\n',
            "    )\n",
            "X = pd.DataFrame({m: s.reindex(all_queries).astype(int) for m, s in runs.items()})\n",
        ],
    ),
    Patch(
        ident="C9-hybrid-params",
        notebook="src/hybrid.ipynb",
        rationale=(
            "El notebook tenia el nombre del run y la lista de indices fijados en el "
            "codigo, asi que cada una de las cuatro fusiones exigia editarlo a mano. "
            "Leerlos de globals() permite lanzarlas con papermill sin tocar el fichero."
        ),
        old=[
            '    "run_name": "hyb_bm25_uni__bge_multi__tfidf_char_3_5",\n',
        ],
        new=[
            '    "run_name": globals().get("HYBRID_RUN", "hyb_bm25_uni__bge_multi__tfidf_char_3_5"),\n',
            '    "query_sample": globals().get("QUERY_SAMPLE", "/work/benchmark/query_samples/OEB_query_sample_test_16590.json"),\n',
        ],
    ),
    Patch(
        ident="C9-hybrid-indexes",
        notebook="src/hybrid.ipynb",
        rationale="Ver C9-hybrid-params: la lista de indices tambien estaba fijada.",
        old=[
            '    "indexes": ["bm25_unigram", "bge_m3_colbert", "bge_m3_dense", "bge_m3_sparse", "tfidf_char_3_5"],  # ← add more names here\n',
        ],
        new=[
            '    "indexes": globals().get("HYBRID_INDEXES", ["bm25_unigram", "bge_m3_colbert", "bge_m3_dense", "bge_m3_sparse", "tfidf_char_3_5"]),\n',
        ],
    ),
    Patch(
        ident="C1-hybrid",
        notebook="src/hybrid.ipynb",
        rationale=(
            "hybrid.ipynb muestreaba con `sample_aligned(..., seed=1337)` sobre las "
            "claves ordenadas, mientras retrieve.ipynb usaba `.sample(n, "
            "random_state=42)` posicional. Dos criterios distintos sobre marcos "
            "distintos: de ahi que los hibridos evaluaran un conjunto de consultas "
            "que solo comparte 5.844 de 16.590 con el de BM25."
        ),
        old=[
            "log(f\"[SAMPLE] Sampling {CONFIG['sample_size']:,} aligned pairs (seed={CONFIG['seed']}) …\")\n",
            'short_s, long_s = sample_aligned(short_df, long_df, CONFIG["sample_size"], CONFIG["seed"])\n',
            'log(f"[SAMPLE] Done. Sample size = {len(short_s):,}")\n',
        ],
        new=[
            "# La muestra se carga del fichero versionado, no se re-muestrea aqui.\n",
            "import hashlib as _hashlib, json as _json\n",
            '_QUERY_SAMPLE = CONFIG.get("query_sample") or "/work/benchmark/query_samples/OEB_query_sample_test_16590.json"\n',
            '_payload = _json.loads(Path(_QUERY_SAMPLE).read_text(encoding="utf-8"))\n',
            '_wanted = set(_payload["query_item_keys"])\n',
            "_fp = _hashlib.sha256('\\n'.join(sorted(_wanted)).encode('utf-8')).hexdigest()\n",
            'if _payload.get("sha256") and _fp != _payload["sha256"]:\n',
            "    raise ValueError(f\"{_QUERY_SAMPLE}: huella {_fp[:12]} != declarada {_payload['sha256'][:12]}\")\n",
            'short_s = short_df[short_df.item_key.isin(_wanted)].copy().sort_values("item_key").reset_index(drop=True)\n',
            'long_s  = long_df[long_df.item_key.isin(_wanted)].copy().sort_values("item_key").reset_index(drop=True)\n',
            "if len(short_s) != len(_wanted) or len(long_s) != len(_wanted):\n",
            '    raise ValueError(f"la muestra pide {len(_wanted)} consultas y hay {len(short_s)} cortas / {len(long_s)} largas")\n',
            'log(f"[SAMPLE] {len(short_s):,} consultas de {_QUERY_SAMPLE} (sha256 {_fp[:12]})")\n',
        ],
    ),
    Patch(
        ident="C3b",
        notebook="src/hybrid.ipynb",
        rationale=(
            "El bonus numerico comparaba la consulta solo contra los documentos "
            "muestreados. El 65,2 % de los distractores candidatos queda fuera de la "
            "muestra, asi que el bonus se habria concedido preferentemente al "
            "documento gold: fuga de informacion del conjunto de test."
        ),
        old=[
            "numbers_long  = dict(zip(long_s.item_key,  long_s.numbers))\n",
        ],
        new=[
            "# El bonus numerico se compara contra el corpus completo (47.513 documentos),\n",
            "# no contra los 16.590 muestreados: restringirlo a la muestra concederia el\n",
            "# bonus preferentemente al documento gold y filtraria informacion del test.\n",
            "numbers_long  = dict(zip(long_df.item_key, long_df.numbers))\n",
        ],
    ),
    Patch(
        ident="C3a",
        notebook="src/hybrid.ipynb",
        rationale=(
            "La columna `numbers` se materializa como numpy.ndarray al releerse de "
            "Parquet, no como list. `isinstance(v, list)` era siempre False, de modo "
            "que _nums devolvia [] siempre y numeric_exact / numeric_overlap eran "
            "identicamente cero en los nueve runs hibridos publicados."
        ),
        old=[
            "def _nums(v): \n",
            "    return [float(x) for x in v] if isinstance(v, list) else []\n",
        ],
        new=[
            "def _nums(v):\n",
            "    # Acepta list, tuple y numpy.ndarray. Comprobar `isinstance(v, list)`\n",
            "    # dejaba el bonus numerico permanentemente a cero (ver CORRECTIONS_LOG C3a).\n",
            "    if v is None or isinstance(v, (str, bytes)):\n",
            "        return []\n",
            "    try:\n",
            "        return [float(x) for x in v]\n",
            "    except TypeError:\n",
            "        return []\n",
        ],
    ),
    Patch(
        ident="C4",
        notebook="src/hybrid.ipynb",
        rationale=(
            "beta_exact = 0.0 y 0.05 nunca se probaron pese a que el manuscrito los "
            "declara. Con el bonus ya operativo (C3) la rejilla debe cubrir el rango "
            "anunciado e incluir el 0, que es la condicion de control."
        ),
        old=[
            "    beta_exact_grid = (0.10, 0.15)\n",
            "    beta_overlap_grid = (0.00, 0.05)\n",
        ],
        new=[
            "    beta_exact_grid = (0.00, 0.05, 0.10, 0.15)\n",
            "    beta_overlap_grid = (0.00, 0.05)\n",
        ],
    ),
]


def encode_block(lines: list[str], indent: str) -> str:
    """Codifica lineas de codigo como aparecen en el JSON de un notebook.

    Se opera sobre el texto crudo, y no sobre el JSON deserializado, porque un
    round-trip con json.dumps reformatea el fichero entero y sepulta el cambio
    real bajo un diff de miles de lineas.
    """
    return (",\n" + indent).join(json.dumps(ln, ensure_ascii=False) for ln in lines)


def apply_patch(text: str, patch: Patch, indent: str = " " * 4) -> tuple[str, str]:
    """Devuelve (texto, 'aplicado' | 'ya-aplicado' | 'no-encontrado')."""
    old_block = encode_block(patch.old, indent)
    new_block = encode_block(patch.new, indent)
    marker = json.dumps(patch.applied_marker, ensure_ascii=False)

    # El marcador se comprueba ANTES que el bloque viejo: cuando `new` conserva
    # alguna linea de `old` —por ejemplo al insertar un parametro encima de otro
    # que se mantiene—, el bloque viejo sigue presente tras aplicar el parche y
    # buscarlo primero lo aplicaria una y otra vez.
    if marker in text:
        return text, "ya-aplicado"

    if old_block in text:
        count = text.count(old_block)
        if count > 1 and not patch.all_occurrences:
            return text, "ambiguo"
        sufijo = f" ({count} veces)" if count > 1 else ""
        return text.replace(old_block, new_block), "aplicado" + sufijo

    return text, "no-encontrado"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="informa sin escribir")
    parser.add_argument("--only", help="aplica solo el parche con este identificador")
    args = parser.parse_args()

    selected = [p for p in PATCHES if not args.only or p.ident == args.only]
    if not selected:
        print(f"Ningun parche con identificador {args.only!r}", file=sys.stderr)
        return 1

    by_notebook: dict[str, list[Patch]] = {}
    for patch in selected:
        by_notebook.setdefault(patch.notebook, []).append(patch)

    failures = 0
    for nb_path_str, patches in by_notebook.items():
        nb_path = Path(nb_path_str)
        if not nb_path.exists():
            print(f"{nb_path}: NO EXISTE", file=sys.stderr)
            failures += 1
            continue

        original = nb_path.read_text(encoding="utf-8")
        text = original

        print(f"{nb_path}")
        for patch in patches:
            text, status = apply_patch(text, patch)
            print(f"  {patch.ident:5s} {status}")
            if status in ("no-encontrado", "ambiguo"):
                failures += 1

        if text == original:
            continue

        # El resultado debe seguir siendo un notebook valido.
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"  el parcheo rompio el JSON: {exc}", file=sys.stderr)
            failures += 1
            continue

        if args.check:
            print("  (--check: no se ha escrito)")
        else:
            nb_path.write_text(text, encoding="utf-8", newline="")
            print(f"  escrito {nb_path}")

    if failures:
        print(f"\n{failures} parches no encontrados: revisa si el codigo cambio.", file=sys.stderr)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
