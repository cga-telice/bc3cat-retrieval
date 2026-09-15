"""The dev/test split, read from the contract that declares it (D-007, D-021).

`docs/synthetic-oe/SPLITS.md` says of itself that "the concept lists below are the split
itself, not a recipe for recomputing it". So this parses that file rather than re-running
the generator: re-deriving a split at run time is how a seed change, or a corpus change,
silently moves the boundary between what has been tuned on and what has not.

The split partitions **concepts**, never leaves — siblings share nearly all of a leaf's text,
so a leaf-level split leaks by construction.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

SPLIT_NAMES = ("dev", "test")

#: Where the contract lives, relative to the repository root.
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "docs" / "synthetic-oe" / "SPLITS.md"

#: "## dev — 42 concepts" followed by a fenced block of one concept key per line.
_SECTION = r"^##\s+{name}\b[^\n]*\n+```\n(?P<body>.*?)\n```"


@lru_cache(maxsize=8)
def _read(name: str, path: str) -> frozenset[str]:
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(_SECTION.format(name=re.escape(name)), text, re.MULTILINE | re.DOTALL)
    if not match:
        raise KeyError(f"{path}: no '## {name}' section with a fenced concept list")

    keys = [line.strip() for line in match.group("body").splitlines() if line.strip()]
    stray = [k for k in keys if not k.endswith("$")]
    if stray:
        raise ValueError(f"{path}: '## {name}' holds lines that are not concept keys: {stray[:3]}")
    return frozenset(keys)


def load_split(name: str, *, path: str | Path = DEFAULT_PATH) -> frozenset[str]:
    """The set of concept keys on one side of the split."""
    if name not in SPLIT_NAMES:
        raise ValueError(f"unknown split {name!r}; expected one of {', '.join(SPLIT_NAMES)}")
    return _read(name, str(path))


def split_of_concept(parent_key: str, *, path: str | Path = DEFAULT_PATH) -> str:
    """Which side a concept is on. An unrecognised concept raises rather than defaulting:
    silently putting it in dev would enlarge the set that tuning is allowed to see."""
    for name in SPLIT_NAMES:
        if parent_key in load_split(name, path=path):
            return name
    raise KeyError(f"{parent_key} is in neither split; SPLITS.md covers 83 concepts")


def select_split(frame, name: str, *, parent_column: str = "parent_key", path=DEFAULT_PATH):
    """Filter a query frame to one side of the split, or return it whole for 'all'.

    Every concept present must be in the split: a query whose concept the contract does not
    cover is an error, not a row to drop.
    """
    if name == "all":
        return frame

    concepts = load_split(name, path=path)
    present = set(frame[parent_column].astype(str))
    unknown = sorted(present - load_split("dev", path=path) - load_split("test", path=path))
    if unknown:
        raise KeyError(f"concepts absent from SPLITS.md: {unknown[:5]}")

    return frame[frame[parent_column].astype(str).isin(concepts)]
