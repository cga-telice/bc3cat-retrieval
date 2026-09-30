"""Derive the `_norm` and `_feats` tables of `single_l2_texto` — S6 work item 1.

`data.ipynb` and `features.ipynb` with `SAVE=True` rewrite **every** table of the collection,
including `OE_single_texto_norm.parquet` / `OE_single_texto_feats.parquet`, whose digests stamp every
S4 and S5 run on `single_texto`. So this script derives only the new set, and leaves every existing
table untouched (as `build_s91_query_tables.py` did for S91).

It runs the set through the path `single_texto` took in `data.ipynb` — the synthetic path:
`add_processed_columns`, then the flat `parameters` re-normalised with the corpus's axis labels, then
`add_param_token_columns`, then `build_features`. The L2 build shares SINGLE's schema field for field
(`DELIVERIES.md`), so it is the same kind of query and must take the same path.

**It proves the path first.** Before writing anything it re-derives `single_texto` from
`OE_single_texto.json` with the same functions and requires the result to equal the stored
`OE_single_texto_norm` / `OE_single_texto_feats`, column for column and row for row. If that fails,
the path is not the one the S4 runs were made on, and nothing is written.

    python src/utils/build_s6_query_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_s91_query_tables import same_content  # noqa: E402
from utils.corpus_prep import (  # noqa: E402
    QUERY_FIELDS,
    add_param_token_columns,
    add_processed_columns,
    assert_gold_present,
    axis_labels_from_corpus,
    clean_df,
    load_records,
    normalize_parameters_field,
)
from utils.feature_prep import build_features  # noqa: E402
from utils.run_context import data_paths  # noqa: E402

REFERENCE = "single_texto"
NEW = "single_l2_texto"


def derive(path: Path, corpus_keys: set[str], axis_labels: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(norm, feats) for one synthetic query set, along `data.ipynb`'s `prepare_query_set`."""
    frame = clean_df(load_records(path, extra_fields=QUERY_FIELDS))
    assert_gold_present(frame, corpus_keys)
    frame = add_processed_columns(frame, "text")
    normalised = [
        normalize_parameters_field(par, axis_labels.get(str(parent), {}))
        for par, parent in zip(frame["parameters"], frame["parent_key"])
    ]
    frame["parameters_norm"] = [n for n, _ in normalised]
    frame["param_values_multi_norm"] = [m for _, m in normalised]
    norm = add_param_token_columns(frame)
    return norm, build_features(norm)


def main() -> None:
    paths = data_paths("OE", work_root=REPO)
    if NEW not in paths.query_json:
        raise SystemExit(f"not found: data/processed/OE_{NEW}.json")

    long_proc = add_param_token_columns(add_processed_columns(clean_df(load_records(paths.long_json)), "text"))
    corpus_keys = set(long_proc["item_key"].astype(str))
    axis_labels = axis_labels_from_corpus(long_proc)

    ref_norm, ref_feats = derive(paths.query_json[REFERENCE], corpus_keys, axis_labels)
    same_content(ref_norm, pd.read_parquet(paths.query_norm[REFERENCE]), f"OE_{REFERENCE}_norm")
    same_content(ref_feats, pd.read_parquet(paths.query_feats[REFERENCE]), f"OE_{REFERENCE}_feats")
    print(f"path proven: `{REFERENCE}` re-derives to its stored norm and feats tables exactly")

    norm, feats = derive(paths.query_json[NEW], corpus_keys, axis_labels)
    for out in (paths.query_norm[NEW], paths.query_feats[NEW]):
        if out.exists():
            raise SystemExit(f"{out.relative_to(REPO)} exists; refusing to overwrite a table runs may stamp")
    norm.to_parquet(paths.query_norm[NEW], index=False)
    feats.to_parquet(paths.query_feats[NEW], index=False)
    for out in (paths.query_norm[NEW], paths.query_feats[NEW]):
        print(f"written: {out.relative_to(REPO)} ({len(norm):,} rows)")


if __name__ == "__main__":
    main()
