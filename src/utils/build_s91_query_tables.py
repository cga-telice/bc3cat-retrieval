"""Derive the `_norm` and `_feats` tables of S91's two `resumen` renderings — S91 work item 3.

`data.ipynb` and `features.ipynb` with `SAVE=True` rewrite **every** table of the collection,
including `OE_short_norm.parquet` and `OE_short_feats.parquet`, whose digests stamp the coded
`resumen` runs this probe pairs against. So this script derives only the two new sets, and leaves
every existing table untouched.

It runs them through the path the coded `resumen` took in `data.ipynb` — the corpus's short path,
`add_processed_columns` then `add_param_token_columns`, then `build_features` — not the synthetic
path, because the renderings are the corpus's own `resumen` with only the suffix changed, and the
pairing requires that nothing but the text differs. The synthetic path would give the same
`param_tokens` for these nested parameters anyway (axis labels are consulted only for flat dicts).

**It proves the path first.** Before writing anything it re-derives the coded `resumen` from
`OE_resumen.json` with the same function and requires the result to equal the existing
`OE_short_norm` / `OE_short_feats` content, column for column and row for row. If that fails, the
path is not the one the coded runs were made on, and nothing is written.

    python src/utils/build_s91_query_tables.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.corpus_prep import (  # noqa: E402
    QUERY_FIELDS,
    add_param_token_columns,
    add_processed_columns,
    assert_gold_present,
    clean_df,
    load_records,
)
from utils.feature_prep import build_features  # noqa: E402
from utils.run_context import data_paths  # noqa: E402

RENDERINGS = ("resumen_decoded", "resumen_stripped")


def derive(path: Path, corpus_keys: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(norm, feats) for one `resumen` rendering, along the corpus's short path."""
    frame = clean_df(load_records(path, extra_fields=QUERY_FIELDS))
    assert_gold_present(frame, corpus_keys)
    norm = add_param_token_columns(add_processed_columns(frame, "text"))
    return norm, build_features(norm)


def same_content(derived: pd.DataFrame, stored: pd.DataFrame, name: str) -> None:
    """Fail unless `derived` holds exactly `stored`'s columns and values, in its row order."""
    missing = [c for c in stored.columns if c not in derived.columns]
    if missing:
        raise SystemExit(f"{name}: re-derived table lacks {missing}; the path is not the coded one")
    # Compared after a parquet round trip, because that is what the stored table went through:
    # parquet keeps a nested dict as a struct, so an axis a record lacks (7,212 OE records have a
    # null one) comes back as a key holding None. In memory the key is absent. Comparing without
    # the round trip reports that serialisation as a difference in 10.27 % of rows.
    buffer = io.BytesIO()
    derived[list(stored.columns)].to_parquet(buffer, index=False)
    buffer.seek(0)
    left = pd.read_parquet(buffer).reset_index(drop=True)
    right = stored.reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(left, right, check_dtype=False)
    except AssertionError as err:
        raise SystemExit(f"{name}: re-derived coded `resumen` differs from the stored table:\n{err}")


def main() -> None:
    paths = data_paths("OE", work_root=REPO)
    missing = [q for q in RENDERINGS if q not in paths.query_json]
    if missing:
        raise SystemExit(f"not found: {missing}. Run build_resumen_renderings.py first.")

    long_keys = set(clean_df(load_records(paths.long_json))["item_key"].astype(str))

    coded_norm, coded_feats = derive(paths.short_json, long_keys)
    same_content(coded_norm, pd.read_parquet(paths.short_norm), "OE_short_norm")
    same_content(coded_feats, pd.read_parquet(paths.short_feats), "OE_short_feats")
    print("path proven: the coded `resumen` re-derives to OE_short_norm and OE_short_feats exactly")

    for queryset in RENDERINGS:
        norm, feats = derive(paths.query_json[queryset], long_keys)
        norm.to_parquet(paths.query_norm[queryset], index=False)
        feats.to_parquet(paths.query_feats[queryset], index=False)
        for out in (paths.query_norm[queryset], paths.query_feats[queryset]):
            print(f"written: {out.relative_to(REPO)} ({len(norm):,} rows)")


if __name__ == "__main__":
    main()
