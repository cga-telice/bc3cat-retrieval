"""Which queries are scored at item level — D-033 and D-040 in one place (S9 work item 1 (b)).

D-033: a query whose gold `texto` is duplicated by another leaf's has no unique answer; it is excluded at
item level. The groups come from upstream's sidecar, `OE_duplicate_texto_groups.json`.

D-040: a `resumen` query whose text equals another leaf's — under the coded **or** the decoded rendering,
so that both are scored on one population — cannot tell its gold from that leaf either, and is excluded
at item level too. Text is compared with whitespace collapsed, as S91's text ceilings compare it: two
queries identical there are identical to every arm. Groups are formed among the leaves of one split, the
split being scored. No group spans two concepts, so parent level excludes nothing (asserted).

D-040 recorded its counts ad hoc and said the harness implementation regenerates them and replaces them;
`tests/test_exclusions.py` holds the regenerated figures.

A third quantity is **not** an exclusion: a transform that makes two golds' queries identical (S9 design,
Scoring). That is the method's error, so `text_collisions` only counts it, for the report to print.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "processed"
SIDECAR = DATA / "OE_duplicate_texto_groups.json"
RESUMEN_RENDERINGS = (DATA / "OE_resumen.json", DATA / "OE_resumen_decoded.json")

#: Query sets that are renderings of `resumen`, to which D-040 applies. A synthetic set with the same
#: property needs an amendment naming it (D-040, Scope).
RESUMEN_FAMILY = ("resumen", "resumen_decoded", "resumen_u", "resumen_u__canon", "resumen_u__hyde", "resumen_u__rewrite")


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def duplicate_texto() -> frozenset[str]:
    """D-033: every leaf in a duplicate-`texto` group, both splits."""
    groups = json.loads(SIDECAR.read_text(encoding="utf-8"))["groups"]
    return frozenset(str(m) for members in groups.values() for m in members)


def identical_groups(texts: dict[str, str]) -> list[list[str]]:
    """Groups of two or more keys whose collapsed text is the same."""
    by_text: dict[str, list[str]] = defaultdict(list)
    for key, text in texts.items():
        by_text[collapse(text)].append(key)
    return [keys for keys in by_text.values() if len(keys) > 1]


@lru_cache(maxsize=2)
def resumen_identical(split_concepts: frozenset[str]) -> frozenset[str]:
    """D-040: leaves of `split_concepts` sharing their `resumen` text with another such leaf, under the
    coded or the decoded rendering."""
    out: set[str] = set()
    for path in RESUMEN_RENDERINGS:
        records = json.loads(path.read_text(encoding="utf-8"))
        texts = {str(r["item_key"]): r["text"] for r in records if r["parent_key"] in split_concepts}
        parent = {str(r["item_key"]): r["parent_key"] for r in records}
        for group in identical_groups(texts):
            if len({parent[k] for k in group}) != 1:
                raise ValueError(f"{path.name}: a `resumen` group spans concepts {sorted(group)[:4]}…; "
                                 "D-040's parent-level rule no longer holds")
            out.update(group)
    return frozenset(out)


def item_excluded(queryset: str, gold_keys, split_concepts: frozenset[str]) -> frozenset[str]:
    """The gold leaves among `gold_keys` that item-level scoring of `queryset` excludes (D-033, plus
    D-040 for the `resumen` family). Callers drop every query whose gold is in the result and print its n."""
    golds = {str(k) for k in gold_keys}
    excluded = golds & duplicate_texto()
    if queryset in RESUMEN_FAMILY:
        excluded |= golds & resumen_identical(frozenset(split_concepts))
    return frozenset(excluded)


def text_collisions(records) -> int:
    """Queries whose collapsed text equals that of a query with a different gold. Counted, never excluded."""
    golds_by_text: dict[str, set[str]] = defaultdict(set)
    count_by_text: dict[str, int] = defaultdict(int)
    for r in records:
        t = collapse(r["text"])
        golds_by_text[t].add(str(r["gold_item_key"]))
        count_by_text[t] += 1
    return sum(count_by_text[t] for t, golds in golds_by_text.items() if len(golds) > 1)
