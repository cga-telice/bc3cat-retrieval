"""Deterministic catalog lookup (Stage 3).

Maps (parent_key, extracted_params) → matching item_key(s).

Usage::

    cl = CatalogLookup(schema_path, long_norm_path)
    result = cl.lookup("OEA010$", {"DIMENSIONES": "30x15 mm", "TRABAJO": None, ...})

Ported from `research/structured-retrieval@85c3359` (D-026). Changes against the source:
the default `OEB_*` paths are gone — both paths are required, and the caller gets them from
the resolver (D-022); the `__main__` self-test, which asserted OEB counts, is replaced by
`tests/test_structured_pipeline.py`. Matching logic is unchanged.
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class CatalogLookup:
    """Deterministic lookup from (parent_key, extracted_params) to item_key(s)."""

    def __init__(self, schema_path, parquet_path):
        """Load the concept schema and build the lookup structures."""
        schema_path = Path(schema_path)
        parquet_path = Path(parquet_path)

        with open(schema_path, encoding="utf-8") as f:
            self._schema = json.load(f)

        # Build valid-values sets from schema (lowercased for comparison)
        self._valid_values = {}
        for pk, entry in self._schema.items():
            self._valid_values[pk] = {}
            for label, values in entry["axes"].items():
                self._valid_values[pk][label.strip().lower()] = {
                    v.strip().lower() for v in values
                }

        # Build item index from parquet
        df = pd.read_parquet(parquet_path)
        leaf_df = df[df["parent_key"].str.endswith("$")]

        self._index = {}
        for pk in self._schema:
            grp = leaf_df[leaf_df["parent_key"] == pk]
            items = []
            for _, row in grp.iterrows():
                pn = row["parameters_norm"]
                params = {}
                for axis_key in ("A", "B", "C", "D", "F"):
                    axis = pn[axis_key]
                    if axis is not None:
                        params[axis["label_norm"]] = axis["values"][0]["value_norm"]
                items.append({"item_key": row["item_key"], "params": params})
            self._index[pk] = items

    def lookup(self, parent_key: str, extracted_params: dict) -> list[str]:
        """Return matching item_key(s) for a concept group and extracted params.

        - All axes resolved → single item_key (list of 1)
        - Some axes None → sub-group of matching items
        - All axes None → all items in the concept group
        - Unknown parent_key → empty list
        - Unknown value for an axis → treat as None for that axis
        """
        if parent_key not in self._index:
            return []

        filters = {}
        valid = self._valid_values.get(parent_key, {})
        for label, value in extracted_params.items():
            if value is None:
                continue
            nl = label.strip().lower()
            nv = value.strip().lower()
            if nl not in valid:
                logger.warning(
                    "Unknown axis %r for %s, treating as None", label, parent_key
                )
                continue
            if nv not in valid[nl]:
                logger.warning(
                    "Unknown value %r for axis %r in %s, treating as None",
                    value, label, parent_key,
                )
                continue
            filters[nl] = nv

        results = []
        for item in self._index[parent_key]:
            if all(item["params"].get(l) == v for l, v in filters.items()):
                results.append(item["item_key"])
        return sorted(results)

    def get_schema(self, parent_key: str) -> dict | None:
        """Return the schema for a concept group (axes, values), or None."""
        return self._schema.get(parent_key)

    def get_all_parent_keys(self) -> list[str]:
        """Return all known parent_keys."""
        return sorted(self._schema.keys())
