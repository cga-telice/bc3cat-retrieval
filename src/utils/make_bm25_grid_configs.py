"""Generate the OE BM25 `k1`/`b` grid configs — S3 work item 8 (D-012).

The previous study fitted `k1`=0.60 / `b`=0.35 to OEB `resumen` queries of ~14 tokens. OE `texto`
queries run ~74–78. Whether that operating point transfers is one of the four things S3 exists to
answer, and answering it needs the grid as configs, because a config is the unit of reproducibility
here: a run must be recoverable from `(config, code commit, query-set digest)` alone.

`k1` and `b` are baked into the document weights at index time — `bm25_unigram.py` precomputes
`w_ij = idf_j * tf_ij * (k1+1) / (tf_ij + k1*(1-b+b*dl_i/avgdl))` — so every grid point needs its own
index, not just its own scoring call. 50 points, 2 of which already exist from S2.

Written as JSON because that is what `configs/bm25_*__OE.yaml` already are (JSON is a subset of YAML,
and S0's migration produced them that way); matching it keeps the grid diff-comparable with the point
S2 ran, which is the one the whole sweep is measured against.

    python src/utils/make_bm25_grid_configs.py          # writes only what is missing
    python src/utils/make_bm25_grid_configs.py --check   # verifies, writes nothing
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"

#: The grid the design froze. Same geometry as the OEB sweep of the previous study, so the two are
#: comparable point for point.
K1_VALUES = (0.60, 0.80, 1.00, 1.20, 1.40)
B_VALUES = (0.20, 0.35, 0.50, 0.65, 0.80)

#: The two field variants: text only (deployable) and text + parameter tokens (oracle bound, D-010).
VARIANTS = ("bm25_unigram", "bm25_unigram_params")

COLLECTION = "OE"


def config_name(variant: str, k1: float, b: float) -> str:
    return f"{variant}__k1-{k1:.2f}__b-{b:.2f}__{COLLECTION}"


def build(variant: str, k1: float, b: float) -> dict:
    name = config_name(variant, k1, b)
    return {
        "collection": COLLECTION,
        "paths": {"data_dir": "/work/data/processed", "index_root": "/work/index"},
        "inputs": {
            "short_feats": "{data_dir}/{collection}_short_feats.parquet",
            "long_feats": "{data_dir}/{collection}_long_feats.parquet",
            "features_meta": "{data_dir}/{collection}_features_meta.json",
        },
        "method": {
            "family": "bm25",
            "name": name,
            "impl": variant,
            "save_as": name,
            "params": {
                "analyzer": "word",
                "ngram_range": [1, 1],
                "lowercase": True,
                "token_pattern": "(?u)\\b\\w+\\b",
                "strip_accents": "unicode",
                "k1": k1,
                "b": b,
            },
        },
        "io": {
            "data_dirname": "data",
            "mapping_file": "mapping.jsonl",
            "fields_file": "fields.json",
            "meta_file": "meta.json",
        },
        "retriever": {"module": f"src.retrievers.{variant}", "entrypoint": "load"},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="verify without writing")
    args = ap.parse_args()

    written, existing, mismatched = [], [], []
    for variant in VARIANTS:
        for k1 in K1_VALUES:
            for b in B_VALUES:
                name = config_name(variant, k1, b)
                path = CONFIGS / f"{name}.yaml"
                want = build(variant, k1, b)
                if path.exists():
                    have = json.loads(path.read_text(encoding="utf-8"))
                    # The two S2 points are the reference the sweep is read against: if a generated
                    # config disagreed with the one S2 actually ran, the sweep would be comparing
                    # the grid against a point that never existed.
                    if have != want:
                        mismatched.append(name)
                    else:
                        existing.append(name)
                    continue
                if not args.check:
                    path.write_text(json.dumps(want, indent=2) + "\n", encoding="utf-8")
                written.append(name)

    print(f"grid: {len(VARIANTS)} variants x {len(K1_VALUES)} k1 x {len(B_VALUES)} b = "
          f"{len(VARIANTS) * len(K1_VALUES) * len(B_VALUES)} points")
    print(f"  already present and identical : {len(existing)}")
    print(f"  {'missing' if args.check else 'written'} : {len(written)}")
    if mismatched:
        print(f"  DISAGREE with what is on disk: {len(mismatched)}")
        for name in mismatched:
            print(f"    {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
