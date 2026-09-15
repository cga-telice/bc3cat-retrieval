"""Build docs/synthetic-oe/SPLITS.md — S0 work item 2, resolving D-007.

Partitions the 83 OE concepts into dev and test. By concept, never by leaf: siblings of a
test leaf share nearly all of its text, so a leaf-level split leaks into any tuning.

Stratified by (subchapter, family-size tercile). The frozen design said *decile*; with 83
concepts that yields 30 non-empty cells of which 10 hold a single concept, and a singleton
cell cannot be split — it lands wholly on one side, so a tenth of the corpus would be
assigned arbitrarily and the stratification would be decorative. Terciles give 17 cells
with 3 singletons. See the amendment on the S0 design.

Deterministic: same seed, same split. Run it again and it overwrites.

    python src/utils/build_splits.py [--dev-fraction 0.5] [--seed 20260915]
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import subprocess
from datetime import date
from pathlib import Path
from random import Random

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "processed"
OUT = REPO / "docs" / "synthetic-oe" / "SPLITS.md"

CORPUS = "OE_texto.json"
QUERY_SETS = {"single": "OE_single_texto.json", "stacked": "OE_stacked_texto.json"}


def subchapter(parent_key: str) -> str:
    return parent_key[:3]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-fraction", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--balance", choices=("concepts", "both"), default="both")
    ap.add_argument("--dry-run", action="store_true", help="print the balance, write nothing")
    args = ap.parse_args()

    commit = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True
    ).strip()

    corpus = json.loads((DATA / CORPUS).read_text(encoding="utf-8"))
    family = collections.Counter(r["parent_key"] for r in corpus)

    # Tercile boundaries from the observed family-size distribution, recorded in the output
    # so the strata are reconstructible without re-running anything.
    sizes = sorted(family.values())
    lo = statistics.quantiles(sizes, n=3)[0]
    hi = statistics.quantiles(sizes, n=3)[1]

    def tercile(n: int) -> int:
        return 0 if n <= lo else (1 if n <= hi else 2)

    strata: dict[tuple[str, int], list[str]] = collections.defaultdict(list)
    for key, n in family.items():
        strata[(subchapter(key), tercile(n))].append(key)

    # Assign within each stratum. Rounding debt carries across strata in a fixed order, so
    # singleton cells alternate sides instead of all landing on the same one.
    rng = Random(args.seed)
    dev: list[str] = []
    test: list[str] = []
    if args.balance == "concepts":
        debt = 0.0
        for cell in sorted(strata):
            members = sorted(strata[cell])
            rng.shuffle(members)
            target = len(members) * args.dev_fraction + debt
            n_dev = int(round(target))
            n_dev = max(0, min(len(members), n_dev))
            debt = target - n_dev
            dev.extend(members[:n_dev])
            test.extend(members[n_dev:])
    else:
        # Both at once. Each stratum contributes its concepts to the two sides in the
        # proportion asked for — that is what keeps a small subchapter represented on both
        # sides — but *which* concepts go where is chosen to even out leaves, because family
        # sizes span 3 to 6,336 and an even split of concepts is a lopsided split of the
        # corpus. Balancing only concepts gives a 62/38 leaf split; balancing only leaves
        # empties the small subchapters out of test.
        dev_leaves = test_leaves = 0
        quota = args.dev_fraction
        debt = 0.0
        for cell in sorted(strata):
            members = sorted(strata[cell])
            rng.shuffle(members)
            target = len(members) * quota + debt
            n_dev = max(0, min(len(members), int(round(target))))
            debt = target - n_dev
            n_test = len(members) - n_dev
            for key in sorted(members, key=lambda k: (-family[k], k)):
                total = dev_leaves + test_leaves + family[key]
                dev_gap = quota * total - dev_leaves
                test_gap = (1 - quota) * total - test_leaves
                to_dev = dev_gap >= test_gap
                if n_dev == 0:
                    to_dev = False
                elif n_test == 0:
                    to_dev = True
                if to_dev:
                    dev.append(key)
                    dev_leaves += family[key]
                    n_dev -= 1
                else:
                    test.append(key)
                    test_leaves += family[key]
                    n_test -= 1

    dev, test = sorted(dev), sorted(test)
    assert not set(dev) & set(test), "dev and test overlap"
    assert set(dev) | set(test) == set(family), "split does not cover every concept"

    side = {k: "dev" for k in dev} | {k: "test" for k in test}

    def leaves(keys: list[str]) -> int:
        return sum(family[k] for k in keys)

    # --- query balance, including the thin modification types ---
    qstats: dict[str, dict[str, collections.Counter]] = {}
    for label, fname in QUERY_SETS.items():
        qs = json.loads((DATA / fname).read_text(encoding="utf-8"))
        per_side = collections.Counter(side[q["parent_key"]] for q in qs)
        per_type: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for q in qs:
            for t in q["modification_types"]:
                per_type[t][side[q["parent_key"]]] += 1
        qstats[label] = {"side": per_side, "type": per_type}

    # --- render ---
    L: list[str] = []
    L.append("# SPLITS — `research/synthetic-oe`")
    L.append("")
    L.append(
        "Contract. The dev/test partition of the OE concepts, fixed before any run "
        "(D-007). Generated by `src/utils/build_splits.py`; the concept lists below are the "
        "split itself, not a recipe for recomputing it."
    )
    L.append("")
    L.append(
        f"**Generated:** {date.today().isoformat()} · **Code commit:** `{commit}` · "
        f"**Seed:** `{args.seed}` · **Dev fraction:** {args.dev_fraction:g} (balanced on {args.balance})"
    )
    L.append("")
    L.append("---")
    L.append("")
    L.append("## The rule")
    L.append("")
    L.append(
        "- **By concept, never by leaf.** Siblings of a test leaf share nearly all of its "
        "text; a leaf-level split leaks into any tuning or fine-tuning by construction."
    )
    L.append(
        "- **No tuning ever touches test** — not hyper-parameters, not model selection, not "
        "thresholds. The frozen test evaluation runs once, in S12."
    )
    L.append(
        f"- **Strata:** (subchapter, family-size tercile), with tercile boundaries at "
        f"{lo:.0f} and {hi:.0f} leaves, taken from the observed distribution."
    )
    L.append("")
    L.append("## Balance")
    L.append("")
    L.append("| | Concepts | Leaves | Single queries | Stacked queries |")
    L.append("|---|---:|---:|---:|---:|")
    for name, keys in (("dev", dev), ("test", test)):
        L.append(
            f"| {name} | {len(keys)} | {leaves(keys):,} | "
            f"{qstats['single']['side'][name]:,} | {qstats['stacked']['side'][name]:,} |"
        )
    L.append(
        f"| **total** | **{len(family)}** | **{leaves(dev + test):,}** | "
        f"**{sum(qstats['single']['side'].values()):,}** | "
        f"**{sum(qstats['stacked']['side'].values()):,}** |"
    )
    L.append("")
    L.append("### By subchapter")
    L.append("")
    L.append("| Subchapter | Concepts dev | Concepts test | Leaves dev | Leaves test |")
    L.append("|---|---:|---:|---:|---:|")
    for s in sorted({subchapter(k) for k in family}):
        d = [k for k in dev if subchapter(k) == s]
        t = [k for k in test if subchapter(k) == s]
        L.append(f"| {s} | {len(d)} | {len(t)} | {leaves(d):,} | {leaves(t):,} |")
    L.append("")
    L.append("### Verification")
    L.append("")
    L.append(
        "Asserted by the generator, which fails rather than writing a broken split "
        "(exit criterion 2):"
    )
    L.append("")
    L.append("| Check | Result |")
    L.append("|---|---|")
    L.append(f"| Every concept assigned exactly once | {len(dev) + len(test)} of {len(family)} |")
    L.append(f"| dev ∩ test | empty ({len(set(dev) & set(test))}) |")
    L.append(f"| dev ∪ test = full concept set | {set(dev) | set(test) == set(family)} |")
    L.append(
        f"| Leaf balance | {leaves(dev):,} / {leaves(test):,} "
        f"({100 * leaves(dev) / leaves(dev + test):.1f} % dev) |"
    )
    L.append("")
    L.append("### Single queries by modification type")
    L.append("")
    L.append(
        "The thin types are the binding constraint on what the test split can support. "
        "Where a type is thin, report it with its interval or pool at layer level; do not "
        "over-read a per-type point estimate."
    )
    L.append("")
    L.append("| Type | dev | test |")
    L.append("|---|---:|---:|")
    for t, c in sorted(qstats["single"]["type"].items(), key=lambda kv: -sum(kv[1].values())):
        L.append(f"| `{t}` | {c['dev']:,} | {c['test']:,} |")
    L.append("")
    for name, keys in (("dev", dev), ("test", test)):
        L.append(f"## {name} — {len(keys)} concepts")
        L.append("")
        L.append("```")
        L.extend(keys)
        L.append("```")
        L.append("")

    text = "\n".join(L) + "\n"
    if args.dry_run:
        print(text[: text.index("## dev —")])
    else:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        print(f"written: {OUT.relative_to(REPO)}")
    print(f"dev {len(dev)} concepts / {leaves(dev):,} leaves · "
          f"test {len(test)} concepts / {leaves(test):,} leaves")


if __name__ == "__main__":
    main()
