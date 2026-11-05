"""A3 manual validation helper for BIO alignment (Sprint LWN-01).

Samples 200 rows stratified across the 13 axes (~15 per axis), reconstructs the
surface text of each tagged span by re-tokenizing text_norm with offset_mapping,
and verifies the reconstructed span equals the canonical value's surface form
(or a surface-override phrase for the TIPO DE TERRENO=Normal case).

Outputs:
  - data/processed/bio_validation_report.md  (human-readable, all 200 rows)
  - data/processed/bio_validation_summary.json  (per-axis correctness)

A row is "fully correct" when EVERY tagged axis span matches the expected
surface form. The protocol's gate is >=95% fully correct out of 200.

Usage:
    python -m src.pipeline.training.validate_bio_alignment
    python -m src.pipeline.training.validate_bio_alignment --n 200 --seed 42
"""

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data" / "processed"
ENCODER_NAME = "intfloat/multilingual-e5-base"
MAX_LEN = 512

# Mirror data_prep_bio.SURFACE_OVERRIDES so we can validate "surface" alignments
SURFACE_OVERRIDES: dict[tuple[str, str], list[str]] = {
    ("TIPO DE TERRENO", "normal"): [
        "cualquier clase de terreno",
        "cualquier tipo de terreno",
    ],
}


def stratified_sample(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """Sample ~n rows stratified across axes — one row may contribute to multiple
    axes, so we deduplicate by item_key after collecting per-axis subsamples.

    Strategy: for each of the 13 axes, take ceil(n/13) rows that have a
    non-empty span for that axis. Concatenate, dedupe, trim to n if needed.
    """
    per_axis = max(1, (n + 12) // 13)  # ~15 per axis for n=200
    axis_set: set[str] = set()
    for blob in df["bio_labels"]:
        for lbl in blob:
            if lbl != "O":
                axis_set.add(lbl[2:])  # strip B-/I- prefix

    parts = []
    rng = pd.Series(range(len(df))).sample(frac=1.0, random_state=seed).tolist()
    df_shuffled = df.iloc[rng].reset_index(drop=True)

    for axis in sorted(axis_set):
        b_label = f"B-{axis}"
        mask = df_shuffled["bio_labels"].apply(lambda labs: b_label in labs)
        sub = df_shuffled[mask]
        parts.append(sub.head(per_axis))

    sampled = pd.concat(parts, ignore_index=True).drop_duplicates("item_key")
    # Top up with random rows if dedup left us short
    if len(sampled) < n:
        remaining = df_shuffled[~df_shuffled["item_key"].isin(sampled["item_key"])]
        topup = remaining.head(n - len(sampled))
        sampled = pd.concat([sampled, topup], ignore_index=True)
    if len(sampled) > n:
        sampled = sampled.head(n)
    return sampled.reset_index(drop=True)


def reconstruct_span_text(text_norm: str, token_idxs: list[int], offsets):
    """Reconstruct the surface text of a token span using char offsets.

    Returns the substring of text_norm covering offsets[token_idxs[0]].start
    through offsets[token_idxs[-1]].end. Handles non-contiguous tokens by
    spanning the full range (rare).
    """
    if not token_idxs:
        return ""
    starts = [offsets[i][0] for i in token_idxs]
    ends = [offsets[i][1] for i in token_idxs]
    return text_norm[min(starts):max(ends)]


def expected_surface(axis: str, value_norm: str, text_lower: str) -> str | None:
    """Return the surface phrase that should be tagged for (axis, value_norm).

    Tries direct match first; falls back to surface overrides.
    """
    value_lower = value_norm.lower()
    if value_lower in text_lower:
        return value_lower
    value_collapsed = re.sub(r"\s+", " ", value_lower).strip()
    if value_collapsed != value_lower and value_collapsed in text_lower:
        return value_collapsed
    for override in SURFACE_OVERRIDES.get((axis, value_lower), []):
        if override.lower() in text_lower:
            return override.lower()
    return None


def extract_canonical_labels(row) -> dict[str, str]:
    """Mirror of data_prep_bio.extract_canonical_labels — kept local to avoid
    cross-module coupling at validation time."""
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
        v = (values[0].get("value_norm") or "").strip()
        if v:
            out[label] = v
    return out


def axis_spans_from_bio(bio_labels: list[str]) -> dict[str, list[list[int]]]:
    """Group consecutive token indices by axis: {axis: [[i0, i1, ...], ...]}.

    A new span starts on B-{axis}; subsequent I-{axis} extend it; anything else
    closes the span.
    """
    spans: dict[str, list[list[int]]] = defaultdict(list)
    cur_axis: str | None = None
    cur_idxs: list[int] = []
    for i, lab in enumerate(bio_labels):
        if lab == "O":
            if cur_axis is not None:
                spans[cur_axis].append(cur_idxs)
                cur_axis, cur_idxs = None, []
            continue
        prefix, axis = lab[0], lab[2:]
        if prefix == "B":
            if cur_axis is not None:
                spans[cur_axis].append(cur_idxs)
            cur_axis = axis
            cur_idxs = [i]
        elif prefix == "I":
            if cur_axis == axis:
                cur_idxs.append(i)
            else:
                # Stray I-X — treat as B-X start for robustness
                if cur_axis is not None:
                    spans[cur_axis].append(cur_idxs)
                cur_axis = axis
                cur_idxs = [i]
    if cur_axis is not None:
        spans[cur_axis].append(cur_idxs)
    return spans


def validate_row(row, long_row, tokenizer):
    """Verify each tagged span equals the canonical (or surface-override) value.

    Returns (per_axis_results, row_correct) where:
      per_axis_results: list of (axis, status, expected, actual)
        status in {"ok", "mismatch", "missing_span", "expected_no_span"}
      row_correct: True iff every axis has status "ok"
    """
    text = long_row["text_norm"]
    text_lower = text.lower()
    canonical = extract_canonical_labels(long_row)

    encoding = tokenizer(
        text, return_offsets_mapping=True, truncation=True,
        max_length=MAX_LEN, add_special_tokens=True,
    )
    offsets = encoding["offset_mapping"]

    # Defensive check: tokens in BIO row must match a fresh re-tokenization.
    # If they don't, the parquet was made with a different tokenizer/version.
    if len(row["bio_labels"]) != len(encoding["input_ids"]):
        return [("__tokenization__", "mismatch", "len_match", "len_diff")], False

    spans = axis_spans_from_bio(list(row["bio_labels"]))

    results = []
    for axis, value_norm in canonical.items():
        expected = expected_surface(axis, value_norm, text_lower)
        actual_spans = spans.get(axis, [])
        if expected is None:
            # No surface form for this canonical value -> we expect no span
            if actual_spans:
                actual_text = reconstruct_span_text(text, actual_spans[0], offsets).lower()
                results.append((axis, "expected_no_span", None, actual_text))
            else:
                results.append((axis, "ok", None, None))
            continue

        if not actual_spans:
            results.append((axis, "missing_span", expected, None))
            continue

        # Reconstruct span text and compare (case-insensitive, whitespace-normalized)
        actual_text = reconstruct_span_text(text, actual_spans[0], offsets).lower()
        actual_norm = re.sub(r"\s+", " ", actual_text).strip()
        expected_norm = re.sub(r"\s+", " ", expected).strip()
        if actual_norm == expected_norm:
            results.append((axis, "ok", expected, actual_text))
        else:
            results.append((axis, "mismatch", expected, actual_text))

    row_correct = all(s[1] == "ok" for s in results)
    return results, row_correct


def main():
    parser = argparse.ArgumentParser(description="Validate BIO alignments")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()

    print("Loading data...")
    bio_df = pd.read_parquet(args.data_dir / "bio_training_data.parquet")
    long_df = pd.read_parquet(args.data_dir / "OEB_long_norm.parquet")
    long_idx = {r["item_key"]: r for _, r in long_df.iterrows()}

    print(f"Sampling {args.n} rows stratified across axes (seed={args.seed})...")
    sampled = stratified_sample(bio_df, n=args.n, seed=args.seed)
    print(f"  Sampled {len(sampled)} unique rows")

    print(f"Loading tokenizer: {ENCODER_NAME}...")
    tokenizer = AutoTokenizer.from_pretrained(ENCODER_NAME)

    print("Validating...")
    per_axis_status: dict[str, Counter] = defaultdict(Counter)
    n_correct = 0
    detailed = []
    for i, (_, row) in enumerate(sampled.iterrows()):
        long_row = long_idx.get(row["item_key"])
        if long_row is None:
            continue
        results, ok = validate_row(row, long_row, tokenizer)
        for axis, status, expected, actual in results:
            per_axis_status[axis][status] += 1
        if ok:
            n_correct += 1
        detailed.append((row["item_key"], row["parent_key"], results, ok))

    rate = n_correct / len(sampled) if len(sampled) else 0.0
    print(f"\nFully correct rows: {n_correct}/{len(sampled)} ({rate:.1%})")

    print("\nPer-axis status counts:")
    for axis in sorted(per_axis_status):
        cnts = per_axis_status[axis]
        total = sum(cnts.values())
        ok_n = cnts["ok"]
        print(f"  {axis:<28} ok={ok_n}/{total} ({ok_n/total:.1%})  other={dict({k:v for k,v in cnts.items() if k != 'ok'})}")

    # Markdown report
    report_path = args.data_dir / "bio_validation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# BIO Alignment Validation Report (Sprint LWN-01, A3)\n\n")
        f.write(f"**Sample size:** {len(sampled)} rows, stratified across 13 axes (seed={args.seed})\n")
        f.write(f"**Fully correct rows:** {n_correct}/{len(sampled)} ({rate:.1%})\n")
        f.write(f"**Gate:** >=95% (protocol §10 risk register)\n\n")
        f.write(f"## Per-axis status\n\n")
        f.write(f"| axis | ok | other |\n|---|---|---|\n")
        for axis in sorted(per_axis_status):
            cnts = per_axis_status[axis]
            total = sum(cnts.values())
            ok_n = cnts["ok"]
            other = {k: v for k, v in cnts.items() if k != "ok"}
            f.write(f"| {axis} | {ok_n}/{total} ({ok_n/total:.1%}) | {other or ''} |\n")
        f.write(f"\n## Per-row details\n\n")
        for item_key, parent_key, results, ok in detailed:
            mark = "OK" if ok else "FAIL"
            f.write(f"### {item_key} ({parent_key}) — {mark}\n\n")
            for axis, status, expected, actual in results:
                if status == "ok":
                    f.write(f"- `{axis}` — ok (`{expected}`)\n")
                else:
                    f.write(f"- `{axis}` — **{status}** (expected: `{expected}`, actual: `{actual}`)\n")
            f.write("\n")
    print(f"  Markdown report: {report_path}")

    # JSON summary for downstream tooling
    summary = {
        "n_sampled": len(sampled),
        "n_correct": n_correct,
        "correctness_rate": rate,
        "per_axis": {a: dict(c) for a, c in per_axis_status.items()},
        "gate_passed": rate >= 0.95,
    }
    summary_path = args.data_dir / "bio_validation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  JSON summary:    {summary_path}")

    if not summary["gate_passed"]:
        print(f"\n!! Gate NOT passed (need >=95%, got {rate:.1%}). Iterate on data_prep_bio.py.")
    else:
        print(f"\nGate passed. >= 95% rows fully correct.")


if __name__ == "__main__":
    main()
