"""S2 work item 6: a seeded sample of bm25_unigram_params item-level misses per L1 condition.

Writes, per miss, what a reader needs to classify it as *genuine rendering effect*, *harness or
feature artefact*, or *pantry artefact (D-004)*: the query text as the run saw it, the gold and
rank-1 leaves' normalised text, the tokens each side has that the other lacks, the gold's rank,
and two mechanical flags — the thousands-dot artefact recorded under D-010, and token doubling
(D-004). Classification itself is not automated: the classified sample is the record
`docs/synthetic-oe/sprints/SPRINT_S2_FAILURES.csv`.
"""

from __future__ import annotations

import gzip
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
METHOD = "bm25_unigram_params__k1-0.60__b-0.35__OE"
RUN = REPO / "runs" / "OE" / "single_texto" / METHOD
CONDITIONS = ("single_unit_conversion", "single_num_to_text")
N, SEED = 30, 20260917
THOUSANDS = re.compile(r"(?<=\d)\.(?=\d{3}\b)")
DOUBLED = re.compile(r"\b(\w+) \1\b")

perq = pd.read_parquet(RUN / "results_perquery.parquet")
corpus = pd.read_parquet(REPO / "data" / "processed" / "OE_long_norm.parquet",
                         columns=["item_key", "text_norm"]).set_index("item_key")["text_norm"]
raw = {r["item_key"]: r["text"] for r in json.load(open(
    REPO / "data" / "processed" / "OE_single_texto.json", encoding="utf-8"))}
runs = {}
with gzip.open(RUN / "results_top100.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        runs[r["query_item_key"]] = r

rows = []
for cond in CONDITIONS:
    misses = perq[(perq["condition"] == cond) & (perq["item_acc1"] == 0)]["query_item_key"].tolist()
    sample = sorted(random.Random(SEED).sample(misses, min(N, len(misses)))) if misses else []
    for qk in sample:
        r = runs[qk]
        top = r["candidates"][0]["index_item_key"]
        rank = next((c["rank"] for c in r["candidates"] if c["index_item_key"] == r["gold_item_key"]), None)
        q = set(r["query_text"].split())
        g = set(corpus[r["gold_item_key"]].split())
        t = set(corpus[top].split())
        rows.append({
            "condition": cond, "query_item_key": qk, "n_misses_in_condition": len(misses),
            "gold": r["gold_item_key"], "top1": top, "gold_rank": rank,
            "top1_same_parent": top[:6] == r["gold_item_key"][:6],
            "query_raw": raw[qk], "query_text": r["query_text"],
            "gold_text": corpus[r["gold_item_key"]], "top1_text": corpus[top],
            "gold_minus_query": " ".join(sorted(g - q)), "query_minus_gold": " ".join(sorted(q - g)),
            "top1_minus_gold": " ".join(sorted(t - g)), "gold_minus_top1": " ".join(sorted(g - t)),
            "thousands_dot_artefact": bool(THOUSANDS.search(raw[qk])),
            "token_doubling": bool(DOUBLED.search(r["query_text"])),
            "classification": "", "note": "",
        })

out = REPO / "logs" / "S2" / "failure_sample_bm25_params.csv"  # classified copy: sprints/SPRINT_S2_FAILURES.csv
pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8")
print(out, len(rows))
