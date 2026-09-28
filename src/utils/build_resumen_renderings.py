"""Build the two S91 renderings of the OE `resumen` — S91 work item 1.

The catalogue's `resumen` ends in a three-code suffix naming the work-regime axes, in the order
TRABAJO / BANDA DE MANTENIMIENTO / CONDICIONES DE EJECUCIÓN, e.g. `(N/<3/R)`. The previous study
expanded those codes into their values before querying (D-039). This writes, beside
`OE_resumen.json`:

- `OE_resumen_decoded.json` — the suffix replaced by the decoded values, `(v1/v2/v3)`;
- `OE_resumen_stripped.json` — the suffix removed;
- `OE_resumen_decoder.json` — the decoder table and the counts it was fitted on.

Every other field is copied unchanged, and each record gains `gold_item_key = item_key`.

**The decoder** (S91 design, work item 1). It is keyed by *(suffix position, code)* and fitted on
**dev leaves only**; test is transformed with it and never read to fit it. Each entry decodes to
the words common to every value the code takes on dev, written in that code's most frequent
catalogue spelling. So TRABAJO `-`, which stands for *Cualquier franja horaria* and for its
*excepcional* variant, decodes to *Cualquier franja horaria*. A code with no common words decodes
to nothing. The table uses neither the concept nor the gold, so it is a component a deployed
system could have.

**A missing axis is not a value.** `-` also marks an axis the leaf does not have: `OEA180a` is
`(D/-/-)` with only a TRABAJO axis. Such an occurrence contributes no value to the intersection,
since counting it as an empty value would empty every `-` entry. The count of such occurrences is
kept in the table.

A suffix is the final parenthesised group with exactly three `/`-separated codes. A record without
one is identical in all three renderings.

    python src/utils/build_resumen_renderings.py
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.corpus_prep import WORD_TOKEN_RE, normalize_param_string  # noqa: E402

DATA = REPO / "data" / "processed"
SOURCE = DATA / "OE_resumen.json"
SPLITS = REPO / "docs" / "synthetic-oe" / "SPLITS.md"
DECODED = DATA / "OE_resumen_decoded.json"
STRIPPED = DATA / "OE_resumen_stripped.json"
TABLE = DATA / "OE_resumen_decoder.json"

#: The axis each suffix position names, as the catalogue labels it.
AXES = ("TRABAJO", "BANDA DE MANTENIMIENTO", "CONDICIONES DE EJECUCIÓN")

#: Amendment A1 (2026-09-28). A value seen on under 1 % of a code's dev occurrences takes no part
#: in the intersection. Without it, `OEB160a/b` — which put their CONDICIONES code in position 1,
#: `(R/-/-)` — make CONDICIONES `-` take three values and decode to nothing on 9,380 dev leaves.
#: The smallest genuine variant, *diurno con/sin corte de tensión* under `D`, is at 2.9 %.
MIN_SHARE = 0.01

SUFFIX_RE = re.compile(r"(\s*)\(([^()]*)\)\s*$")


def dev_concepts() -> set[str]:
    text = SPLITS.read_text(encoding="utf-8")
    block = text.split("## dev")[1].split("## test")[0]
    concepts = set(re.findall(r"^(OE[A-G]\d{3}\$)$", block, flags=re.M))
    if not concepts:
        raise SystemExit(f"no dev concepts parsed from {SPLITS}")
    return concepts


def split_suffix(text: str) -> tuple[str, str, list[str]] | None:
    """(text before the suffix, the whitespace before it, its codes), or None."""
    m = SUFFIX_RE.search(text)
    if not m:
        return None
    codes = [c.strip() for c in m.group(2).split("/")]
    if len(codes) != len(AXES):
        return None
    return text[: m.start()], m.group(1), codes


def axis_value(record: dict, axis: str) -> str | None:
    """The leaf's raw value on `axis`, or None when it has no such axis."""
    want = normalize_param_string(axis)
    for block in record["parameters"].values():
        if isinstance(block, dict) and normalize_param_string(block.get("label", "")) == want:
            values = block.get("values") or []
            return values[0]["value"].strip() if values else None
    return None


def tokens(value: str) -> set[str]:
    return set(WORD_TOKEN_RE.findall(normalize_param_string(value)))


def kept(spellings: collections.Counter) -> collections.Counter:
    """The values that take part in the intersection: those at or above `MIN_SHARE` (amendment A1)."""
    total = sum(spellings.values())
    return collections.Counter({v: n for v, n in spellings.items() if n >= MIN_SHARE * total})


def decode_entry(spellings: collections.Counter) -> str:
    """The words common to every kept value, in the most frequent spelling's order and case."""
    spellings = kept(spellings)
    if not spellings:
        return ""
    common = set.intersection(*(tokens(v) for v in spellings))
    top = max(spellings, key=lambda v: (spellings[v], v))
    return " ".join(w for w in top.split() if tokens(w) <= common and (tokens(w) or common)).strip()


def fit(records: list[dict], dev: set[str]) -> dict:
    spellings: dict[tuple[int, str], collections.Counter] = collections.defaultdict(collections.Counter)
    absent: collections.Counter = collections.Counter()
    for record in records:
        if record["parent_key"] not in dev:
            continue
        parts = split_suffix(record["text"])
        if parts is None:
            continue
        for position, code in enumerate(parts[2]):
            value = axis_value(record, AXES[position])
            if value is None:
                absent[(position, code)] += 1
            else:
                spellings[(position, code)][value] += 1
    keys = sorted(set(spellings) | set(absent))
    return {
        f"{position}|{code}": {
            "position": position,
            "axis": AXES[position],
            "code": code,
            "decodes_to": decode_entry(spellings[(position, code)]),
            "values_on_dev": dict(spellings[(position, code)].most_common()),
            "ignored_below_min_share": sorted(set(spellings[(position, code)])
                                              - set(kept(spellings[(position, code)]))),
            "axis_absent_on_dev": absent[(position, code)],
        }
        for position, code in keys
    }


def render(record: dict, table: dict) -> tuple[str, str]:
    """(decoded text, stripped text). An unseen code decodes to nothing."""
    parts = split_suffix(record["text"])
    if parts is None:
        return record["text"], record["text"]
    head, space, codes = parts
    decoded = [table.get(f"{p}|{c}", {}).get("decodes_to", "") for p, c in enumerate(codes)]
    decoded = [d for d in decoded if d]
    stripped = head.rstrip()
    return (f"{head}{space}({'/'.join(decoded)})" if decoded else stripped), stripped


def dump(path: Path, records: list[dict]) -> None:
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    records = json.loads(SOURCE.read_text(encoding="utf-8"))
    dev = dev_concepts()
    table = fit(records, dev)

    decoded, stripped = [], []
    counts = collections.Counter()
    for record in records:
        text_d, text_s = render(record, table)
        has_suffix = split_suffix(record["text"]) is not None
        counts["suffix"] += has_suffix
        counts["dev"] += record["parent_key"] in dev
        counts["dev_suffix"] += has_suffix and record["parent_key"] in dev
        decoded.append({**record, "text": text_d, "gold_item_key": record["item_key"]})
        stripped.append({**record, "text": text_s, "gold_item_key": record["item_key"]})

    dump(DECODED, decoded)
    dump(STRIPPED, stripped)
    TABLE.write_text(
        json.dumps({"fitted_on": "dev", "dev_concepts": len(dev), "axes": AXES, "min_share": MIN_SHARE,
                    "entries": table},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"records {len(records):,} · with a suffix {counts['suffix']:,} · "
          f"dev {counts['dev']:,}, of which with a suffix {counts['dev_suffix']:,}")
    for key, entry in table.items():
        print(f"  {entry['axis'][:12]:12s} {entry['code']!r:8s} -> {entry['decodes_to']!r:28s} "
              f"values {sum(entry['values_on_dev'].values()):>6,} · axis absent {entry['axis_absent_on_dev']:>4,}")
    for path in (DECODED, STRIPPED, TABLE):
        print(f"written: {path.relative_to(REPO)}")


if __name__ == "__main__":
    main()
