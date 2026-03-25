"""Deterministic catalog lookup (Stage 3).

Maps (parent_key, extracted_params) → matching item_key(s).

Usage::

    cl = CatalogLookup()
    result = cl.lookup("OEB010$", {"TERRENO": "blando", "PAVIMENTO": None, ...})
"""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
DEFAULT_SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"
DEFAULT_PARQUET_PATH = DATA_DIR / "OEB_long_norm.parquet"


class CatalogLookup:
    """Deterministic lookup from (parent_key, extracted_params) to item_key(s)."""

    def __init__(self, schema_path=None, parquet_path=None):
        """Load the concept schema and build the lookup structures."""
        schema_path = Path(schema_path or DEFAULT_SCHEMA_PATH)
        parquet_path = Path(parquet_path or DEFAULT_PARQUET_PATH)

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


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.WARNING)

    cl = CatalogLookup()
    print(f"Loaded {len(cl.get_all_parent_keys())} concept groups")
    passed = 0
    total = 7

    # Test 1: Full match (all axes specified) -- exactly 1 item
    r = cl.lookup("OEB010$", {
        "TERRENO": "blando",
        "PAVIMENTO": "sin reposición",
        "CONDICIONES DE EJECUCIÓN": "Volumen relevante",
    })
    assert r == ["OEB010aaa"], f"T1 FAIL: {r}"
    passed += 1
    print("T1 PASS: full match -> 1 item")

    # Test 2: Partial match (only TERRENO set) -- 6 items (2 pav x 3 cond)
    r = cl.lookup("OEB010$", {
        "TERRENO": "blando",
        "PAVIMENTO": None,
        "CONDICIONES DE EJECUCIÓN": None,
    })
    assert len(r) == 6, f"T2 FAIL: got {len(r)}"
    passed += 1
    print("T2 PASS: partial match -> 6 items")

    # Test 3: All null on small group -- all items
    r = cl.lookup("OEB160$", {"CONDICIONES DE EJECUCIÓN": None})
    assert len(r) == 3, f"T3 FAIL: got {len(r)}"
    passed += 1
    print("T3 PASS: all null -> 3 items")

    # Test 4: Unknown parent_key -- empty list
    r = cl.lookup("NONEXISTENT$", {"X": "y"})
    assert r == [], f"T4 FAIL: {r}"
    passed += 1
    print("T4 PASS: unknown parent -> []")

    # Test 5: Unknown value -- warning + treated as wildcard
    r = cl.lookup("OEB160$", {"CONDICIONES DE EJECUCIÓN": "valor inventado"})
    assert len(r) == 3, f"T5 FAIL: got {len(r)}"
    passed += 1
    print("T5 PASS: unknown value -> 3 items (wildcard)")

    # Test 6: Large group (6336 items), all null -- all items
    r = cl.lookup("OEB030$", {})
    assert len(r) == 6336, f"T6 FAIL: got {len(r)}"
    passed += 1
    print("T6 PASS: large all-null -> 6336 items")

    # Test 6b: Large group, one axis specified -- correct sub-group
    r = cl.lookup("OEB030$", {"Nº TUBOS": "1"})
    assert len(r) == 576, f"T6b FAIL: got {len(r)}"
    passed += 1
    print("T6b PASS: large 1-axis -> 576 items")

    print(f"\n{passed}/{total} tests passed")
    sys.exit(0 if passed == total else 1)
