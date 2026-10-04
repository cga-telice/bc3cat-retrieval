"""Build the within-family ColBERT scores the S11 two-stage arms order by — S11 work item 1b.

For one base: take its reference ColBERT run (the run of the same query set; for `texto_u` / `resumen_u`, the dev
`texto` / `resumen` run they are subsets of), encode that run's full query list in its own order and blocks, and
score every query of the base against every leaf of each candidate concept. The candidates are the concepts a
two-stage arm's Stage 1 can pick: the `dense_e5` run's three highest-ranked distinct concepts, plus the Stage-1
concept of S9's key-tolerant pipeline run where one exists (it differs from `dense_e5`'s rank 1 on a few queries).

Every score of every scored family leaf that is in the reference run's top 100 must equal the run's stored score
exactly; otherwise nothing is written. Output, under `index/OE/_colbert_family/`:
`{base}.npz` (`rerankers.colbert_family.FamilyScoreStore`) and `{base}.meta.json` (provenance and the check).

    BGE_M3_API=http://172.17.0.1:8800 python src/utils/build_colbert_family_cache.py --base stacked_texto
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from rerankers.colbert_family import (  # noqa: E402
    families_from_mapping, score_in_run_blocks, verify_against_run, write_store)
from utils.provenance import sha256_file  # noqa: E402

DATA = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
INDEX = REPO / "index" / "OE" / "bge_m3_colbert__OE"
OUT = REPO / "index" / "OE" / "_colbert_family"
COLBERT = "bge_m3_colbert__OE"
E5 = "dense_e5__OE"
K0 = "structured_pipeline_llm_keytol_valuenorm__OE"
BASES = ("texto_u", "resumen_u", "single_texto", "single_l2_texto", "stacked_texto", "dose_texto", "isolated_texto")
REFERENCE = {"texto_u": "texto", "resumen_u": "resumen"}
TOP_CONCEPTS = 3


def rows(path: Path) -> list[dict]:
    with gzip.open(path / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, choices=BASES)
    base = ap.parse_args().base
    ref = REFERENCE.get(base, base)
    if git("status", "--porcelain", "src"):
        raise SystemExit("src/ has uncommitted changes; commit first")
    if not os.getenv("BGE_M3_API"):
        raise SystemExit("set BGE_M3_API to the server the ColBERT runs used")

    i2p = {r["item_key"]: r["parent_key"] for r in json.loads((DATA / "OE_texto.json").read_text(encoding="utf-8"))}
    cb_rows = rows(RUNS / ref / COLBERT)
    e5_rows = rows(RUNS / ref / E5)
    if [r["query_item_key"] for r in cb_rows] != [r["query_item_key"] for r in e5_rows]:
        raise SystemExit(f"{ref}: the ColBERT and dense_e5 runs do not list the same queries in the same order")
    if base in REFERENCE:
        keys = {r["item_key"] for r in json.loads((DATA / f"OE_{base}.json").read_text(encoding="utf-8"))}
    else:
        keys = {r["query_item_key"] for r in cb_rows}
    by_key = {r["query_item_key"]: r for r in cb_rows}
    if not keys <= set(by_key):
        raise SystemExit(f"{base}: {len(keys - set(by_key))} queries are not in the {ref} ColBERT run")

    k0 = {}
    if (RUNS / base / K0).exists():
        for r in rows(RUNS / base / K0):
            if r["query_text"] != by_key[r["query_item_key"]]["query_text"]:
                raise SystemExit(f"{base}: K0 and the reference run encode different text for {r['query_item_key']}")
            k0[r["query_item_key"]] = i2p[r["candidates"][0]["index_item_key"]]
    concepts, outside = [], 0
    for r in e5_rows:
        k = r["query_item_key"]
        if k not in keys:
            concepts.append(())
            continue
        top = []
        for c in r["candidates"]:
            p = i2p[c["index_item_key"]]
            if p not in top:
                top.append(p)
            if len(top) == TOP_CONCEPTS:
                break
        outside += int(k in k0 and k0[k] not in top)
        concepts.append(tuple(sorted(set(top) | ({k0[k]} if k in k0 else set()))))

    from retrievers import bge_m3_colbert as cb
    t0 = time.time()
    searcher = cb.load(INDEX)
    fams = families_from_mapping(searcher.external_ids, i2p)
    texts = [r["query_text"] for r in cb_rows]
    scored = score_in_run_blocks(searcher, fams, texts, concepts, log=lambda m: print(f"[{base}] {m}", flush=True))
    check = verify_against_run(scored, cb_rows)
    print(f"[{base}] check {check}", flush=True)
    if check["mismatched"] or check["queries"] != len(keys):
        raise SystemExit(f"{base}: family scores do not reproduce the {ref} ColBERT run; nothing written")

    out = OUT / f"{base}.npz"
    n = write_store(out, texts, scored)
    meta = {
        "base": base, "reference_run": f"runs/OE/{ref}/{COLBERT}",
        "reference_results_sha256": sha256_file(RUNS / ref / COLBERT / "results_top100.jsonl.gz"),
        "stage1_sources": [f"runs/OE/{ref}/{E5} (top {TOP_CONCEPTS} distinct concepts)"]
                          + ([f"runs/OE/{base}/{K0} (rank-1 concept)"] if k0 else []),
        "queries": len(keys), "query_concept_pairs": n,
        "k0_concept_outside_e5_top": outside,
        "check": check, "bge_m3_api": os.getenv("BGE_M3_API"),
        "code_commit": git("rev-parse", "HEAD"), "seconds": round(time.time() - t0, 1),
        "npz_sha256": sha256_file(out),
    }
    (OUT / f"{base}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"[{base}] wrote {n} query-concept pairs in {meta['seconds']} s", flush=True)


if __name__ == "__main__":
    main()
