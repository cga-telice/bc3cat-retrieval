"""Derive the `_norm` and `_feats` tables of S9's query sets — S9 work item 1 (a).

Two kinds of set (`run_context.S9_QUERY_SETS`):

- **`texto_u`, `resumen_u`** — subsets of the corpus's own records (`build_s9_bases.py`). They take the
  corpus's path, as S91's renderings did (`build_s91_query_tables.derive`). **The path is proven on the
  subset itself:** the derived rows must equal the stored `OE_long_*` / `OE_short_*` rows of the same
  leaves, column for column, so that a `texto_u` run reads exactly what the existing `texto` run read for
  those queries, and the existing run can serve as its untransformed reference.
- **`{base}__{t}`** — a base with its `text` rewritten by transform `t`. The JSON must equal its base's
  record for record in every field but `text`, in the same order; that is checked before anything is
  derived. It then takes its base's path: the corpus path for `texto_u` / `resumen_u`, the synthetic path
  (`build_s6_query_tables.derive`) for the three synthetic bases, whose own stored tables are re-derived
  first, as S6 and S8 did.

A transformed set whose JSON is not on disk yet is skipped and listed; the transforms are written by work
item 2. No existing table is overwritten: if a table exists, it is re-derived and must match.

    python src/utils/build_s9_query_tables.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_s6_query_tables import derive as derive_synthetic  # noqa: E402
from utils.build_s91_query_tables import derive as derive_corpus  # noqa: E402
from utils.build_s91_query_tables import same_content  # noqa: E402
from utils.corpus_prep import (  # noqa: E402
    add_param_token_columns,
    add_processed_columns,
    axis_labels_from_corpus,
    clean_df,
    load_records,
)
from utils.run_context import S9_BASES, S9_TRANSFORMS, data_paths  # noqa: E402

CORPUS_BASES = {"texto_u": "long", "resumen_u": "short"}


def same_but_text(base: Path, transformed: Path) -> None:
    """Fail unless `transformed` is `base` with only `text` changed."""
    left = json.loads(base.read_text(encoding="utf-8"))
    right = json.loads(transformed.read_text(encoding="utf-8"))
    if len(left) != len(right):
        raise SystemExit(f"{transformed.name}: {len(right)} records, base has {len(left)}")
    for i, (a, b) in enumerate(zip(left, right)):
        if set(a) != set(b):
            raise SystemExit(f"{transformed.name}[{i}]: fields differ from the base: {set(a) ^ set(b)}")
        moved = [k for k in a if k != "text" and a[k] != b[k]]
        if moved:
            raise SystemExit(f"{transformed.name}[{i}] ({a.get('item_key')}): {moved} changed; only `text` may")


def write_or_match(norm: pd.DataFrame, feats: pd.DataFrame, norm_out: Path, feats_out: Path) -> None:
    for frame, out in ((norm, norm_out), (feats, feats_out)):
        if out.exists():
            same_content(frame, pd.read_parquet(out), out.name)
            print(f"unchanged: {out.relative_to(REPO)}")
        else:
            frame.to_parquet(out, index=False)
            print(f"written: {out.relative_to(REPO)} ({len(frame):,} rows)")


def main() -> None:
    paths = data_paths("OE", work_root=REPO)
    long_proc = add_param_token_columns(add_processed_columns(clean_df(load_records(paths.long_json)), "text"))
    corpus_keys = set(long_proc["item_key"].astype(str))
    axis_labels = axis_labels_from_corpus(long_proc)

    def derive(base: str, path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
        if base in CORPUS_BASES:
            return derive_corpus(path, corpus_keys)
        return derive_synthetic(path, corpus_keys, axis_labels)

    for base in S9_BASES:
        if base not in paths.query_json:
            raise SystemExit(f"not found: data/processed/OE_{base}.json. Run build_s9_bases.py first.")
        norm, feats = derive(base, paths.query_json[base])
        if base in CORPUS_BASES:
            side = CORPUS_BASES[base]
            for frame, stored_path in ((norm, getattr(paths, f"{side}_norm")), (feats, getattr(paths, f"{side}_feats"))):
                stored = pd.read_parquet(stored_path)
                rows = stored[stored["item_key"].astype(str).isin(set(frame["item_key"].astype(str)))]
                same_content(frame, rows, f"{stored_path.name} restricted to {base}")
            print(f"path proven: `{base}` derives to the stored {side} rows of its {len(norm):,} leaves exactly")
            write_or_match(norm, feats, paths.query_norm[base], paths.query_feats[base])
        else:
            same_content(norm, pd.read_parquet(paths.query_norm[base]), f"OE_{base}_norm")
            same_content(feats, pd.read_parquet(paths.query_feats[base]), f"OE_{base}_feats")
            print(f"path proven: `{base}` re-derives to its stored norm and feats tables exactly")

    pending = []
    for base in S9_BASES:
        for transform in S9_TRANSFORMS:
            name = f"{base}__{transform}"
            if name not in paths.query_json:
                pending.append(name)
                continue
            same_but_text(paths.query_json[base], paths.query_json[name])
            norm, feats = derive(base, paths.query_json[name])
            write_or_match(norm, feats, paths.query_norm[name], paths.query_feats[name])
    if pending:
        print(f"not yet generated ({len(pending)}): {', '.join(pending)}")


if __name__ == "__main__":
    main()
