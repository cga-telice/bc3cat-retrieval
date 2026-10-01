"""Derive the `_norm` and `_feats` tables of `dose_texto` and `isolated_texto` — S8 work item 1.

The E3 delivery (D-009, registered under D-052) shares SINGLE's schema field for field, plus
`applicable_types` / `available_types` (`requests/E3_BALANCED_DOSE.md` §4-§5). It takes the path
`single_texto` took, through `build_s6_query_tables.derive`, and the projection also keeps
`applicable_types`, which S8's design asks for. That extra field is passed for these two sets only:
`QUERY_FIELDS` is unchanged, so no existing table would derive differently.

As in S6, the path is proven first: `single_texto` is re-derived and must equal its stored tables
exactly, or nothing is written. No existing table is overwritten.

    python src/utils/build_s8_query_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_s6_query_tables import REFERENCE, derive  # noqa: E402
from utils.build_s91_query_tables import same_content  # noqa: E402
from utils.corpus_prep import (  # noqa: E402
    QUERY_FIELDS,
    add_param_token_columns,
    add_processed_columns,
    axis_labels_from_corpus,
    clean_df,
    load_records,
)
from utils.run_context import data_paths  # noqa: E402

NEW = ("dose_texto", "isolated_texto")
E3_FIELDS = QUERY_FIELDS + ("applicable_types",)


def main() -> None:
    paths = data_paths("OE", work_root=REPO)
    for name in NEW:
        if name not in paths.query_json:
            raise SystemExit(f"not found: data/processed/OE_{name}.json")
        for out in (paths.query_norm[name], paths.query_feats[name]):
            if out.exists():
                raise SystemExit(f"{out.relative_to(REPO)} exists; refusing to overwrite a table runs may stamp")

    long_proc = add_param_token_columns(add_processed_columns(clean_df(load_records(paths.long_json)), "text"))
    corpus_keys = set(long_proc["item_key"].astype(str))
    axis_labels = axis_labels_from_corpus(long_proc)

    ref_norm, ref_feats = derive(paths.query_json[REFERENCE], corpus_keys, axis_labels)
    same_content(ref_norm, pd.read_parquet(paths.query_norm[REFERENCE]), f"OE_{REFERENCE}_norm")
    same_content(ref_feats, pd.read_parquet(paths.query_feats[REFERENCE]), f"OE_{REFERENCE}_feats")
    print(f"path proven: `{REFERENCE}` re-derives to its stored norm and feats tables exactly")

    for name in NEW:
        norm, feats = derive(paths.query_json[name], corpus_keys, axis_labels, extra_fields=E3_FIELDS)
        norm.to_parquet(paths.query_norm[name], index=False)
        feats.to_parquet(paths.query_feats[name], index=False)
        for out in (paths.query_norm[name], paths.query_feats[name]):
            print(f"written: {out.relative_to(REPO)} ({len(norm):,} rows)")


if __name__ == "__main__":
    main()
