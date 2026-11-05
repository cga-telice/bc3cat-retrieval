"""Extract concept schema from OEB_long_norm.parquet.

Produces data/processed/OEB_concept_schema.json with the structure:
{
  "OEB030$": {
    "concept": "CANALIZACIÓN CON TUBOS DE POLIETILENO...",
    "axes": {
      "TRABAJO": ["Diurno", "Nocturno"],
      "Nº TUBOS": ["1", "2", "3", "4"],
      ...
    },
    "item_keys": ["OEB030aaa", "OEB030aab", ...],
    "num_items": 24
  },
  ...
}
"""

import json
from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
INPUT_PATH = DATA_DIR / "OEB_long_norm.parquet"
OUTPUT_PATH = DATA_DIR / "OEB_concept_schema.json"


def extract_schema(input_path: Path = INPUT_PATH) -> dict:
    df = pd.read_parquet(input_path)

    # Keep only leaf items (parent_key ends with $)
    leaf_df = df[df["parent_key"].str.endswith("$")]

    schema = {}
    for parent_key, grp in leaf_df.groupby("parent_key"):
        concept = grp.iloc[0]["concept"]

        # Collect axes: skip axis entries that are None
        axes = {}
        for _, row in grp.iterrows():
            params = row["parameters"]
            for axis_key in sorted(params.keys()):
                axis = params[axis_key]
                if axis is None:
                    continue
                label = axis["label"].strip()
                value = axis["values"][0]["value"].strip()
                if label not in axes:
                    axes[label] = set()
                axes[label].add(value)

        # Sort values within each axis
        axes = {label: sorted(values) for label, values in axes.items()}

        item_keys = sorted(grp["item_key"].tolist())

        schema[parent_key] = {
            "concept": concept,
            "axes": axes,
            "item_keys": item_keys,
            "num_items": len(item_keys),
        }

    return schema


def main():
    schema = extract_schema()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(schema)} concept groups to {OUTPUT_PATH}")

    # Summary table
    print(f"\n{'Group':<12} {'#Axes':>6} {'#Items':>7}")
    print("-" * 27)
    for pk in sorted(schema):
        entry = schema[pk]
        print(f"{pk:<12} {len(entry['axes']):>6} {entry['num_items']:>7}")


if __name__ == "__main__":
    main()
