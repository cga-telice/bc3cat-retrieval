"""Write `OE_texto_u.json` and `OE_resumen_u.json`, S9's two corpus-rendering bases — S9 work item 1.

S9 measures H6 on one leaf population, U: every dev leaf that is the gold of a `single_texto`,
`single_l2_texto` or `stacked_texto` query (2,691 leaves in the design's entry state). Two of its five
bases are renderings the corpus already holds for those leaves — the identity `texto` and the coded
`resumen` — so they are written here as subsets of `OE_texto.json` / `OE_resumen.json`, record for
record, with `gold_item_key` added (equal to `item_key`), as S91's renderings carry it. Nothing else in
a record changes, and the records keep the corpus's order.

Test-split leaves are never written: U is built from dev golds only, and the script asserts it.

    python src/utils/build_s9_bases.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
SYNTHETIC = ("OE_single_texto.json", "OE_single_l2_texto.json", "OE_stacked_texto.json")
BASES = {"texto_u": "OE_texto.json", "resumen_u": "OE_resumen.json"}


def read(name: str) -> list[dict]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def u_leaves(dev: frozenset[str]) -> set[str]:
    """Dev golds of the three synthetic query sets."""
    leaves: set[str] = set()
    for name in SYNTHETIC:
        leaves |= {str(r["gold_item_key"]) for r in read(name) if r["parent_key"] in dev}
    return leaves


def subset(records: list[dict], leaves: set[str]) -> list[dict]:
    out = []
    for r in records:
        if str(r["item_key"]) in leaves:
            out.append({**r, "gold_item_key": r["item_key"]})
    return out


def main() -> None:
    dev = load_split("dev")
    leaves = u_leaves(dev)
    print(f"U: {len(leaves):,} dev leaves")
    for queryset, source in BASES.items():
        records = subset(read(source), leaves)
        if {str(r["gold_item_key"]) for r in records} != leaves:
            raise SystemExit(f"{source}: does not hold every leaf of U")
        if any(r["parent_key"] not in dev for r in records):
            raise SystemExit(f"{queryset}: a test-split record would be written")
        out = DATA / f"OE_{queryset}.json"
        payload = json.dumps(records, ensure_ascii=False, indent=2)
        if out.exists():
            if out.read_text(encoding="utf-8") == payload:
                print(f"unchanged: {out.relative_to(REPO)}")
                continue
            raise SystemExit(f"{out.relative_to(REPO)} exists with other content; refusing to overwrite")
        out.write_text(payload, encoding="utf-8")
        print(f"written: {out.relative_to(REPO)} ({len(records):,} records)")


if __name__ == "__main__":
    main()
