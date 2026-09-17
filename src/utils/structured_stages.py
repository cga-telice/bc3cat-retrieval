"""Stage decomposition of a structured_pipeline run (S2 work item 5).

For every query of a finished run, re-derive what each stage did, from the run's own ranking
and deterministic code only — no E5 call:

- Stage 1 parent: the parent of the rank-1 candidate. Tier 1 and tier 2 are drawn from the
  Stage-1 family, and the E5 fallback fires only for a parent absent from the schema (never on
  OE), so rank 1 always belongs to the Stage-1 family. Checked, not assumed: see `consistent`.
- Stage 2: the rules extractor on the query text the run used, for that parent.
- Stage 3: the catalogue lookup on that extraction, with the run's own `stage3_value_match`.

`consistent` asserts the re-derivation reproduces the run: when Stage 3 matched anything, the
run's rank 1 is the first matched key; when it matched nothing, rank 1 is the family's first
item. A run where this fails is reported, not summarised.

Recovery is scored against the gold *leaf's* corpus parameters (stripped), on queries whose
Stage-1 parent is correct — elsewhere the extractor is reading another concept's axes.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pipeline.catalog_lookup import CatalogLookup  # noqa: E402
from pipeline.param_extractor_rules import RuleBasedParamExtractor  # noqa: E402

PROCESSED = REPO / "data" / "processed"
SCHEMA = PROCESSED / "OE_concept_schema.json"
LONG_NORM = PROCESSED / "OE_long_norm.parquet"


def gold_params(parameters) -> dict[str, str]:
    return {a["label"].strip(): a["values"][0]["value"].strip()
            for a in parameters.values() if a is not None}


def decompose(run_dir: Path, corpus: pd.DataFrame, schema: dict, extractor, catalogs) -> pd.DataFrame:
    meta = json.loads((REPO / "index" / "OE" / run_dir.name / "meta.json").read_text(encoding="utf-8"))
    value_match = meta["params"].get("stage3_value_match", "literal")
    catalog = catalogs[value_match]
    parent_of = dict(zip(corpus["item_key"], corpus["parent_key"]))
    params_of = dict(zip(corpus["item_key"], corpus["parameters"]))

    rows = []
    with gzip.open(run_dir / "results_top100.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            top = r["candidates"][0]["index_item_key"]
            s1 = parent_of[top]
            gold_parent, gold_item = r["gold_parent_key"], r["gold_item_key"]
            got = extractor.extract(s1, r["query_text"])
            matched = catalog.lookup(s1, got)
            expected_top = matched[0] if matched else next(
                (k for k in schema[s1]["item_keys"] if k in parent_of), None)
            row = {
                "query_item_key": r["query_item_key"],
                "stage1_correct": s1 == gold_parent,
                "stage3_matched": len(matched),
                "stage3_gold_in_match": gold_item in matched,
                "stage3_unique_gold": matched == [gold_item],
                "consistent": top == expected_top,
            }
            if s1 == gold_parent:
                gold = gold_params(params_of[gold_item])
                ext = {a.strip(): (v.strip() if v is not None else None) for a, v in got.items()}
                row.update(
                    axes=len(gold),
                    recovered=sum(ext.get(a) == v for a, v in gold.items()),
                    abstained=sum(ext.get(a) is None for a in gold),
                    misread=sum(ext.get(a) not in (None, v) for a, v in gold.items()),
                )
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    corpus = pd.read_parquet(LONG_NORM, columns=["item_key", "parent_key", "parameters"])
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    extractor = RuleBasedParamExtractor(SCHEMA)
    catalogs = {m: CatalogLookup(SCHEMA, LONG_NORM, value_match=m) for m in ("literal", "normalized")}
    out = REPO / "logs" / "S2" / "stages"  # derived, git-ignored; summarised into results/S2
    out.mkdir(parents=True, exist_ok=True)
    for run_dir in sorted((REPO / "runs" / "OE").glob("*/structured_pipeline_rules*__OE")):
        df = decompose(run_dir, corpus, schema, extractor, catalogs)
        name = f"{run_dir.parent.name}__{run_dir.name}"
        df.to_parquet(out / f"{name}.parquet")
        print(f"{name}: n={len(df)} consistent={df['consistent'].mean():.4f}")


if __name__ == "__main__":
    main()
