"""Training data generation for the shared BIO tagger (Sprint LWN-01, Phase A).

Reads OEB_long_norm.parquet + OEB_concept_schema.json and produces:
  - data/processed/bio_training_data.parquet
  - data/processed/bio_label_inventory.json

We train on LONG text (text_norm) so that evaluation queries (short text)
remain a fully held-out cross-distribution test (matches LW-06 methodology).
This is intentional: cross-distribution generalization is the property
under test in this branch (see protocol Section 1).

Source columns used from OEB_long_norm.parquet:
  - text_norm: long-form normalized text to be tagged
  - parameters_norm: dict {axis_key: {label, label_norm, values: [{value, value_norm, ...}]}}
  - item_key, parent_key

Usage:
    python -m src.pipeline.training.data_prep_bio
    python -m src.pipeline.training.data_prep_bio --max-rows 200       # sanity run
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data" / "processed"
LONG_PARQUET = DATA_DIR / "OEB_long_norm.parquet"
SCHEMA_PATH = DATA_DIR / "OEB_concept_schema.json"
ENCODER_NAME = "intfloat/multilingual-e5-base"
MAX_LEN = 512

# Surface-form overrides: when the canonical value has no literal surface form
# in the long text, map it to one of these phrases. Tried in order. Both ends
# of the catalog phrasing for "Normal" terrain are covered here.
SURFACE_OVERRIDES: dict[tuple[str, str], list[str]] = {
    ("TIPO DE TERRENO", "normal"): [
        "cualquier clase de terreno",
        "cualquier tipo de terreno",
    ],
}


# ── Loading ─────────────────────────────────────────────────────────────────

def load_inputs(data_dir: Path):
    long_df = pd.read_parquet(data_dir / "OEB_long_norm.parquet")
    with open(data_dir / "OEB_concept_schema.json", encoding="utf-8") as f:
        schema = json.load(f)
    return long_df, schema


def filter_leaf_items(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["parent_key"].str.endswith("$")].copy()


def collect_axis_labels(schema: dict) -> list[str]:
    """Sorted list of unique axis labels across all concept groups."""
    axes = set()
    for group in schema.values():
        for axis in group["axes"]:
            axes.add(axis.strip())
    return sorted(axes)


def build_bio_label_inventory(axis_labels: list[str]) -> dict[str, int]:
    """Build {label: integer index} for the BIO inventory.

    Layout: O (0), then B-{axis} for each axis sorted, then I-{axis} for each.
    For 13 axes -> 27 labels.
    """
    labels = ["O"]
    labels.extend(f"B-{axis}" for axis in axis_labels)
    labels.extend(f"I-{axis}" for axis in axis_labels)
    return {label: i for i, label in enumerate(labels)}


def extract_canonical_labels(row) -> dict[str, str]:
    """{axis_label_stripped: value_norm} for the row.

    Uses parameters_norm (richer than parameters; has value_norm pre-computed).
    Skips axes with None / empty values.
    """
    params = row["parameters_norm"]
    if not isinstance(params, dict):
        return {}
    out = {}
    for axis_info in params.values():
        if axis_info is None:
            continue
        label = axis_info["label"].strip()
        values = axis_info.get("values")
        if values is None or len(values) == 0:
            continue
        value_norm = (values[0].get("value_norm") or "").strip()
        if value_norm:
            out[label] = value_norm
    return out


# ── Span alignment ──────────────────────────────────────────────────────────

def _find_anchored_unoccupied(
    text_lower: str,
    needle: str,
    occupied: list[tuple[int, int]],
) -> tuple[int, int] | None:
    """Leftmost (start, end) of `needle` in `text_lower` such that:
       - chars at start-1 and end are non-alphanumeric (or at text boundary), so
         the needle is a delimited unit (handles `1''` and digit anchoring), AND
       - (start, end) does not overlap any range in `occupied`.
    Returns None if no valid match exists.
    """
    if not needle:
        return None
    n = len(needle)
    pos = 0
    L = len(text_lower)
    while pos <= L - n:
        idx = text_lower.find(needle, pos)
        if idx < 0:
            return None
        end = idx + n
        left_ok = idx == 0 or not text_lower[idx - 1].isalnum()
        right_ok = end == L or not text_lower[end].isalnum()
        overlaps = any(s < end and e > idx for s, e in occupied)
        if left_ok and right_ok and not overlaps:
            return idx, end
        pos = idx + 1
    return None


def find_span(
    text_norm: str,
    value_norm: str,
    axis_label: str,
    occupied: list[tuple[int, int]],
):
    """Locate a (start_char, end_char) span for value_norm in text_norm.

    Strategies, tried in order:
      1. Direct anchored search for value_norm.
      2. Whitespace-collapsed value (handles inconsistent spacing).
      3. Surface-form overrides (e.g. TIPO DE TERRENO=Normal -> "cualquier
         clase de terreno") — used when the canonical value has no literal
         form in the long text.

    All searches require non-alphanumeric boundaries on both sides and skip
    positions already covered by `occupied` to avoid same-surface collisions
    like TRABAJO=BANDA="no aplica".

    Returns (start, end, confidence) where confidence in {"high","medium",
    "surface"}, or (None, None, status) where status in
    {"failed","empty","failed_no_surface_form"}.
    """
    if not value_norm:
        return None, None, "empty"

    text_lower = text_norm.lower()
    value_lower = value_norm.lower()

    span = _find_anchored_unoccupied(text_lower, value_lower, occupied)
    if span is not None:
        return span[0], span[1], "high"

    value_collapsed = re.sub(r"\s+", " ", value_lower).strip()
    if value_collapsed and value_collapsed != value_lower:
        span = _find_anchored_unoccupied(text_lower, value_collapsed, occupied)
        if span is not None:
            return span[0], span[1], "medium"

    overrides = SURFACE_OVERRIDES.get((axis_label, value_lower), [])
    for surface in overrides:
        span = _find_anchored_unoccupied(text_lower, surface.lower(), occupied)
        if span is not None:
            return span[0], span[1], "surface"

    return None, None, "failed"


def char_span_to_token_indices(c_start: int, c_end: int, offsets):
    """Map (c_start, c_end) to a list of overlapping token indices.

    Special tokens (CLS, SEP, PAD) have offset (0, 0) and are skipped.
    Returns [] if no overlap.
    """
    matched = []
    for i, (s, e) in enumerate(offsets):
        if s == 0 and e == 0:
            continue
        if s < c_end and e > c_start:
            matched.append(i)
    return matched


def make_bio_labels(row, tokenizer, axis_inventory_set):
    """Tokenize text_norm and produce BIO label sequence aligned to value spans.

    Returns (tokens, bio_labels, alignment_confidence_list).
    """
    text = row["text_norm"]
    canonical = extract_canonical_labels(row)

    encoding = tokenizer(
        text,
        return_offsets_mapping=True,
        truncation=True,
        max_length=MAX_LEN,
        add_special_tokens=True,
    )
    token_ids = encoding["input_ids"]
    offsets = encoding["offset_mapping"]
    tokens = tokenizer.convert_ids_to_tokens(token_ids)

    bio = ["O"] * len(tokens)
    confidence: list[tuple[str, str]] = []
    occupied: list[tuple[int, int]] = []  # char ranges already labeled

    for axis_label, value_norm in canonical.items():
        if axis_label not in axis_inventory_set:
            confidence.append((axis_label, "unknown_axis"))
            continue

        c_start, c_end, status = find_span(text, value_norm, axis_label, occupied)
        if c_start is None:
            confidence.append((axis_label, status))
            continue

        token_idxs = char_span_to_token_indices(c_start, c_end, offsets)
        if not token_idxs:
            # Span lies past truncation boundary
            confidence.append((axis_label, "failed_truncated"))
            continue

        b_idx = token_idxs[0]
        i_idxs = token_idxs[1:]
        bio[b_idx] = f"B-{axis_label}"
        for j in i_idxs:
            bio[j] = f"I-{axis_label}"
        occupied.append((c_start, c_end))
        confidence.append((axis_label, status))

    return tokens, bio, confidence


# ── Split (mirrors data_prep.py:65-92) ──────────────────────────────────────

def split_data(df: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """80/10/10 split stratified by parent_key.

    Concept groups with fewer than 5 items go entirely to train. Mirrors
    src/pipeline/training/data_prep.py exactly so that the same item_key gets
    the same split assignment as the CLS classifier training data.
    """
    from sklearn.model_selection import train_test_split

    group_counts = df["parent_key"].value_counts()
    small_groups = group_counts[group_counts < 5].index
    small_mask = df["parent_key"].isin(small_groups)

    df["split"] = "train"

    big_df = df[~small_mask]
    train_idx, rest_idx = train_test_split(
        big_df.index, test_size=0.2, random_state=seed,
        stratify=big_df["parent_key"]
    )
    rest_sub = big_df.loc[rest_idx]
    val_idx, test_idx = train_test_split(
        rest_sub.index, test_size=0.5, random_state=seed,
        stratify=rest_sub["parent_key"]
    )
    df.loc[val_idx, "split"] = "val"
    df.loc[test_idx, "split"] = "test"

    if len(small_groups) > 0:
        print(
            f"  Note: {len(small_groups)} small groups placed entirely in train: "
            f"{list(small_groups)}"
        )
    return df


# ── Reporting ───────────────────────────────────────────────────────────────

def report(df: pd.DataFrame, axis_labels: list[str], label_inventory: dict, n_samples: int = 5):
    """Print sanity report after BIO generation."""
    print("=" * 72)
    print("BIO TRAINING DATA SANITY REPORT")
    print("=" * 72)

    print(f"\nTotal rows: {len(df)}")
    print(f"Label inventory: {len(label_inventory)} labels (expected {1 + 2 * len(axis_labels)})")

    # Aggregate alignment confidence across rows
    by_axis: dict[str, Counter] = {}
    overall = Counter()
    for blob in df["alignment_confidence"]:
        for axis, status in json.loads(blob):
            by_axis.setdefault(axis, Counter())[status] += 1
            overall[status] += 1

    print(f"\nOverall alignment status histogram:")
    for s, n in overall.most_common():
        print(f"  {s:<22} {n}")
    n_total_axes = sum(overall.values())
    n_aligned = overall.get("high", 0) + overall.get("medium", 0) + overall.get("surface", 0)
    print(f"  ---")
    print(f"  total axis occurrences: {n_total_axes}")
    print(f"  aligned (high+medium):  {n_aligned} ({100*n_aligned/max(n_total_axes,1):.1f}%)")

    print(f"\nPer-axis alignment success:")
    print(f"  {'axis':<28} {'total':>6} {'high':>6} {'medium':>7} {'surface':>8} {'failed':>7} {'success_rate':>13}")
    for axis in axis_labels:
        c = by_axis.get(axis, Counter())
        total = sum(c.values())
        high = c.get("high", 0)
        med = c.get("medium", 0)
        surf = c.get("surface", 0)
        aligned = high + med + surf
        failed = total - aligned
        rate = aligned / total if total else 0.0
        print(f"  {axis:<28} {total:>6} {high:>6} {med:>7} {surf:>8} {failed:>7} {rate:>12.1%}")

    # Per-split row counts
    if "split" in df.columns:
        print(f"\nSplit distribution:")
        for sp, n in df["split"].value_counts().items():
            print(f"  {sp:<6} {n} ({100*n/len(df):.1f}%)")

    # Coverage in train: every B-{axis} appears at least once
    if "split" in df.columns:
        train_df = df[df["split"] == "train"]
        seen = set()
        for blob in train_df["bio_labels"]:
            seen.update(blob)
        missing_b = [f"B-{a}" for a in axis_labels if f"B-{a}" not in seen]
        if missing_b:
            print(f"\nWARNING: BIO labels missing from train split: {missing_b}")
        else:
            print(f"\nAll B-{{axis}} labels present in train split.")

    # Render sample rows (only marked tokens) — written to a debug file because
    # SentencePiece tokens contain U+2581 which Windows cp1252 console can't print.
    sample_path = DATA_DIR / "bio_training_data_samples.txt"
    n = min(n_samples, len(df))
    with open(sample_path, "w", encoding="utf-8") as f:
        f.write(f"Sample row renderings ({n} rows)\n")
        f.write("=" * 72 + "\n")
        for i in range(n):
            row = df.iloc[i]
            tokens = row["tokens"]
            bio = row["bio_labels"]
            marked = [(t, b) for t, b in zip(tokens, bio) if b != "O"]
            text_preview = row["text_norm"][:200].replace("\n", " ")
            f.write(f"\n--- {row['item_key']} ({row['parent_key']}) ---\n")
            f.write(f"text_norm[:200]: {text_preview}\n")
            f.write(f"alignment_confidence: {row['alignment_confidence']}\n")
            f.write(f"marked tokens ({len(marked)}):\n")
            for t, b in marked:
                f.write(f"  {b:<28} {t}\n")
    print(f"\nSample row renderings written to {sample_path}")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate BIO training data")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--encoder", default=ENCODER_NAME)
    parser.add_argument(
        "--max-rows", type=int, default=None,
        help="Optional cap on rows (for sanity testing; default: all)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for the train/val/test split (must match data_prep.py)",
    )
    args = parser.parse_args()

    print("Loading inputs...")
    long_df, schema = load_inputs(args.data_dir)
    print(f"  Long parquet: {len(long_df)} rows")
    print(f"  Schema: {len(schema)} concept groups")

    print("Filtering to leaf items...")
    df = filter_leaf_items(long_df)
    print(f"  {len(df)} leaf items (excluded {len(long_df) - len(df)} non-leaf)")

    if args.max_rows:
        df = df.head(args.max_rows).copy()
        print(f"  Capped to {len(df)} rows for testing")

    print("Building BIO label inventory...")
    axis_labels = collect_axis_labels(schema)
    label_inventory = build_bio_label_inventory(axis_labels)
    print(f"  {len(axis_labels)} unique axes -> {len(label_inventory)} BIO labels")
    print(f"  axes: {axis_labels}")

    inv_path = args.data_dir / "bio_label_inventory.json"
    with open(inv_path, "w", encoding="utf-8") as f:
        json.dump(label_inventory, f, ensure_ascii=False, indent=2)
    print(f"  saved: {inv_path}")

    print(f"Loading tokenizer: {args.encoder}...")
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.encoder)

    print(f"Generating BIO labels for {len(df)} rows...")
    axis_inventory_set = set(axis_labels)
    tokens_col, bio_col, conf_col = [], [], []
    for i, (_, row) in enumerate(df.iterrows()):
        tokens, bio, conf = make_bio_labels(row, tokenizer, axis_inventory_set)
        tokens_col.append(tokens)
        bio_col.append(bio)
        conf_col.append(json.dumps(conf, ensure_ascii=False))
        if (i + 1) % 5000 == 0:
            print(f"  [{i+1}/{len(df)}]")

    df["tokens"] = tokens_col
    df["bio_labels"] = bio_col
    df["alignment_confidence"] = conf_col

    out_df = df[
        ["item_key", "parent_key", "text_norm",
         "tokens", "bio_labels", "alignment_confidence"]
    ].copy()

    print("Splitting data (80/10/10)...")
    out_df = split_data(out_df, seed=args.seed)

    print("Saving BIO training data...")
    out_path = args.data_dir / "bio_training_data.parquet"
    out_df.to_parquet(out_path, index=False)
    print(f"  saved: {out_path}")

    report(out_df, axis_labels, label_inventory)


if __name__ == "__main__":
    main()
