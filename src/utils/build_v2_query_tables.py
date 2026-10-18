"""Derive the `_norm` / `_feats` tables of the 2026-10-16 delivery: the four v2 sets and `bt_texto`.

The v2 sets (`stacked_texto_v2`, `single_texto_v2`, `dose_texto_v2`, `isolated_texto_v2`) are the v1
sets with 163 broken template paraphrases repaired upstream: same records in the same order, only
`text` changed on the queries `OE_v2_changes.jsonl` lists (`DELIVERIES.md`, 2026-10-16). `bt_texto` is
the back-translated rendering of the gold `texto` of 4,670 STACKED-P leaves. Each takes the path its
v1 (or, for BT, STACKED) took through `data.ipynb` — `build_s6_query_tables.derive`, with the E3
projection for dose / isolated (`build_s8_query_tables.E3_FIELDS`) and `condition` / `source_item_key`
added for BT, so the pairing to STACKED-P needs no second file.

**The path is proven on every v1 set first**, not only on `single_texto`: each v1 set is re-derived and
must equal its stored tables exactly, or nothing is written. That is what lets
`tests/test_intake_20261016.py` require a v2 table to equal the v1 table on every unchanged row. No
existing table is overwritten.

    python src/utils/build_v2_query_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_s6_query_tables import derive  # noqa: E402
from utils.build_s8_query_tables import E3_FIELDS  # noqa: E402
from utils.build_s91_query_tables import same_content  # noqa: E402
from utils.corpus_prep import (  # noqa: E402
    QUERY_FIELDS,
    add_param_token_columns,
    add_processed_columns,
    axis_labels_from_corpus,
    clean_df,
    load_records,
)
from utils.run_context import BT_QUERY_SETS, V2_QUERY_SETS, data_paths  # noqa: E402

BT_FIELDS = QUERY_FIELDS + ("condition", "source_item_key")

#: new set -> (reference set whose path it takes, projection)
PATHS: dict[str, tuple[str, tuple[str, ...]]] = {
    "stacked_texto_v2": ("stacked_texto", QUERY_FIELDS),
    "single_texto_v2": ("single_texto", QUERY_FIELDS),
    "dose_texto_v2": ("dose_texto", E3_FIELDS),
    "isolated_texto_v2": ("isolated_texto", E3_FIELDS),
    "bt_texto": ("stacked_texto", BT_FIELDS),
}
assert set(PATHS) == set(V2_QUERY_SETS) | set(BT_QUERY_SETS)


def main() -> None:
    paths = data_paths("OE", work_root=REPO)
    for name in PATHS:
        if name not in paths.query_json:
            raise SystemExit(f"not found: data/processed/OE_{name}.json")
        for out in (paths.query_norm[name], paths.query_feats[name]):
            if out.exists():
                raise SystemExit(f"{out.relative_to(REPO)} exists; refusing to overwrite a table runs may stamp")

    long_proc = add_param_token_columns(add_processed_columns(clean_df(load_records(paths.long_json)), "text"))
    corpus_keys = set(long_proc["item_key"].astype(str))
    axis_labels = axis_labels_from_corpus(long_proc)

    for reference in sorted({ref for ref, _ in PATHS.values()}):
        fields = E3_FIELDS if reference in ("dose_texto", "isolated_texto") else QUERY_FIELDS
        ref_norm, ref_feats = derive(paths.query_json[reference], corpus_keys, axis_labels, extra_fields=fields)
        same_content(ref_norm, pd.read_parquet(paths.query_norm[reference]), f"OE_{reference}_norm")
        same_content(ref_feats, pd.read_parquet(paths.query_feats[reference]), f"OE_{reference}_feats")
        print(f"path proven: `{reference}` re-derives to its stored norm and feats tables exactly")

    for name, (_reference, fields) in PATHS.items():
        norm, feats = derive(paths.query_json[name], corpus_keys, axis_labels, extra_fields=fields)
        norm.to_parquet(paths.query_norm[name], index=False)
        feats.to_parquet(paths.query_feats[name], index=False)
        for out in (paths.query_norm[name], paths.query_feats[name]):
            print(f"written: {out.relative_to(REPO)} ({len(norm):,} rows)")


if __name__ == "__main__":
    main()
