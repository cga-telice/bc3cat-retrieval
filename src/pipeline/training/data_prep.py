"""
Training data generation for the multi-head E5 classifier.

Reads OEB_long_norm.parquet + OEB_concept_schema.json and produces:
  - data/processed/classifier_training_data.parquet
  - data/processed/classifier_label_encoders.json

We train on LONG text (documento/texto) so that evaluation queries
(short text / resumen) are a fully held-out cross-distribution test.
This avoids data leakage and tests genuine generalization.

Usage:
    python src/pipeline/training/data_prep.py [--data-dir DATA_DIR]
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


def load_inputs(data_dir: Path):
    long_df = pd.read_parquet(data_dir / "OEB_long_norm.parquet")
    with open(data_dir / "OEB_concept_schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    return long_df, schema


def filter_leaf_items(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["parent_key"].str.endswith("$")].copy()


def extract_labels(row) -> dict:
    """Extract {axis_label: value} from the parameters column."""
    params = row["parameters"]
    if not isinstance(params, dict):
        return {}
    labels = {}
    for axis_key, axis_info in params.items():
        if axis_info is None:
            continue
        label = axis_info["label"].strip()
        values = axis_info["values"]
        if values is not None and len(values) > 0:
            labels[label] = values[0]["value"].strip()
    return labels


def build_label_encoders(schema: dict) -> dict:
    """Build {parent_key: {axis_label: {value: index}}} mapping.
    Index 0 is always the null class."""
    encoders = {}
    for parent_key, info in schema.items():
        encoders[parent_key] = {}
        for axis_label, axis_values in info["axes"].items():
            mapping = {"null": 0}
            for i, val in enumerate(sorted(axis_values), start=1):
                mapping[val] = i
            encoders[parent_key][axis_label] = mapping
    return encoders


def split_data(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """80/10/10 split stratified by parent_key.

    Concept groups with fewer than 5 items are placed entirely in
    the train split (too few for stratified splitting).
    """
    group_counts = df["parent_key"].value_counts()
    small_groups = group_counts[group_counts < 5].index
    small_mask = df["parent_key"].isin(small_groups)

    df["split"] = "train"

    # Split only groups large enough for stratification
    big_df = df[~small_mask]
    train_idx, rest_idx = train_test_split(
        big_df.index, test_size=0.2, random_state=seed, stratify=big_df["parent_key"]
    )
    rest_sub = big_df.loc[rest_idx]
    val_idx, test_idx = train_test_split(
        rest_sub.index, test_size=0.5, random_state=seed, stratify=rest_sub["parent_key"]
    )
    df.loc[val_idx, "split"] = "val"
    df.loc[test_idx, "split"] = "test"

    if len(small_groups) > 0:
        print(f"  Note: {len(small_groups)} small groups placed entirely in train: "
              f"{list(small_groups)}")
    return df


def verify(df: pd.DataFrame, encoders: dict, schema: dict, raw_df: pd.DataFrame):
    """Print verification summary."""
    print("=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    # Row counts
    print(f"\nTotal rows: {len(df)}")
    print(f"Split distribution:")
    for split, count in df["split"].value_counts().items():
        print(f"  {split}: {count} ({100*count/len(df):.1f}%)")

    # Concept groups per split
    print(f"\nConcept groups per split:")
    for split in ["train", "val", "test"]:
        n = df[df["split"] == split]["parent_key"].nunique()
        print(f"  {split}: {n} groups")

    # Label encoder stats
    total_heads = sum(len(axes) for axes in encoders.values())
    total_classes = sum(
        len(vals) for axes in encoders.values() for vals in axes.values()
    )
    print(f"\nLabel encoders: {total_heads} heads, {total_classes} total classes (incl. null)")

    # Check all schema values present in train
    train_df = df[df["split"] == "train"]
    missing_values = []
    for pk, axes in encoders.items():
        pk_rows = train_df[train_df["parent_key"] == pk]
        for axis_label, val_map in axes.items():
            train_values = set()
            for _, row in pk_rows.iterrows():
                labels = json.loads(row["labels"])
                if axis_label in labels:
                    train_values.add(labels[axis_label])
            schema_values = set(v for v in val_map.keys() if v != "null")
            missing = schema_values - train_values
            if missing:
                missing_values.append((pk, axis_label, missing))
    if missing_values:
        print(f"\nWARNING: {len(missing_values)} (group, axis) pairs with values missing from train:")
        for pk, axis, vals in missing_values[:5]:
            print(f"  {pk}/{axis}: missing {vals}")
    else:
        print("\nAll axis values present in train split.")

    # Spot-check 3 rows
    print("\nSpot-check (3 rows):")
    sample = df.sample(3, random_state=42)
    for _, row in sample.iterrows():
        labels = json.loads(row["labels"])
        raw_row = raw_df[raw_df["item_key"] == row["item_key"]].iloc[0]
        raw_labels = extract_labels(raw_row)
        match = labels == raw_labels
        print(f"  {row['item_key']} ({row['parent_key']}): {'PASS' if match else 'FAIL'}")
        if not match:
            print(f"    expected: {raw_labels}")
            print(f"    got:      {labels}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Generate classifier training data")
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/processed"),
        help="Path to processed data directory"
    )
    args = parser.parse_args()

    data_dir = args.data_dir

    print("Loading inputs...")
    raw_df, schema = load_inputs(data_dir)
    print(f"  Long parquet: {len(raw_df)} rows")
    print(f"  Schema: {len(schema)} concept groups")

    print("Filtering to leaf items...")
    df = filter_leaf_items(raw_df)
    print(f"  {len(df)} leaf items (excluded {len(raw_df) - len(df)} non-leaf)")

    print("Extracting labels...")
    df["labels"] = df.apply(extract_labels, axis=1).apply(json.dumps, ensure_ascii=False)

    print("Building label encoders...")
    encoders = build_label_encoders(schema)

    print("Splitting data (80/10/10)...")
    df = split_data(df)

    # Select output columns
    out_df = df[["query_text", "item_key", "parent_key", "labels", "split"]].copy() \
        if "query_text" in df.columns else \
        df.rename(columns={"text_norm": "query_text"})[
            ["query_text", "item_key", "parent_key", "labels", "split"]
        ]

    print("Saving outputs...")
    out_path = data_dir / "classifier_training_data.parquet"
    out_df.to_parquet(out_path, index=False)
    print(f"  {out_path}")

    enc_path = data_dir / "classifier_label_encoders.json"
    with open(enc_path, "w", encoding="utf-8") as f:
        json.dump(encoders, f, ensure_ascii=False, indent=2)
    print(f"  {enc_path}")

    verify(out_df, encoders, schema, raw_df)


if __name__ == "__main__":
    main()
