"""Shared support for the v2 re-run amendments (D-061; S4 A6, S5 A4, S6 A8, S7 A8, S8 A8, S9 A13, S11 A7).

The 2026-10-16 delivery repaired 163 template paraphrases and shipped v2 of STACKED, SINGLE, dose and isolated:
the same records in the same order, `text` changed on the queries `OE_v2_changes.jsonl` lists. A sprint's
generator takes `--v2` and re-points its query sets to the v2 names, writing under `results/Sx/v2/`; the v1
tables are never overwritten. It also writes a **comparison** table: the same registered statistics on v1 and on
v2 side by side, and v2 − v1 with an interval from **paired draws** — the bootstrap seeds derive from the cell
label, so the same label on the same clusters yields the same multinomial weights for both versions, and the
per-draw difference is a paired bootstrap of the difference. Where the two cluster sets differ the difference is
not paired and is printed without an interval.

`--population stacked_p` (S7 A8) restricts a stacked analysis to STACKED-P (`exclusions.stacked_p`).
"""

from __future__ import annotations

import argparse
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "processed"
CHANGES = DATA / "OE_v2_changes.jsonl"

#: logical query set -> its v2 name
V2 = {"stacked_texto": "stacked_texto_v2", "single_texto": "single_texto_v2",
      "dose_texto": "dose_texto_v2", "isolated_texto": "isolated_texto_v2"}
#: logical query set -> the `set` field of `OE_v2_changes.jsonl`
SET_OF = {"stacked_texto": "stacked", "single_texto": "single", "dose_texto": "dose", "isolated_texto": "isolated"}
POPULATIONS = ("all", "stacked_p")


def parse(argv=None, *, population: bool = False) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", action="store_true", help="read the v2 query sets and write under results/Sx/v2/")
    if population:
        ap.add_argument("--population", choices=POPULATIONS, default="all",
                        help="stacked_p restricts the stacked set to STACKED-P (S7 A8)")
    ns = ap.parse_args(argv)
    if not population:
        ns.population = "all"
    return ns


def mapped(name: str, v2: bool) -> str:
    """The physical query set for a logical one."""
    return V2.get(name, name) if v2 else name


def out_dir(base: Path, v2: bool, population: str = "all") -> Path:
    out = base / "v2" if v2 else base
    return out / "stacked_p" if population == "stacked_p" else out


def generator_label(script: str, v2: bool, population: str = "all") -> str:
    flags = (" --v2" if v2 else "") + (f" --population {population}" if population != "all" else "")
    return script + flags


@lru_cache(maxsize=None)
def changed_keys(logical: str) -> frozenset[str]:
    """The `item_key`s whose text v2 changed, for one logical set."""
    want = SET_OF[logical]
    keys = set()
    for line in CHANGES.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            if c["set"] == want:
                keys.add(c["item_key"])
    return frozenset(keys)


def paired_diff(a: dict, b: dict) -> dict:
    """b − a for two cells holding `est`, `draws` and `concepts`/`n`: paired when the draws align."""
    da, db = np.asarray(a.get("draws", [])), np.asarray(b.get("draws", []))
    out = {"est": float(b["est"] - a["est"]), "c": None, "paired": False}
    if len(da) and len(da) == len(db) and a.get("clusters_key") == b.get("clusters_key"):
        d = db - da
        d = d[np.isfinite(d)]
        if len(d):
            lo, hi = np.percentile(d, [2.5, 97.5])
            out.update(c=(float(lo), float(hi)), paired=True)
    return out


def fsd(x: float) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x:+.4f}"


def fci(c, signed: bool = True) -> str:
    if c is None:
        return "— (not paired)"
    lo, hi = c
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return "—"
    return f"[{lo:+.4f}, {hi:+.4f}]" if signed else f"[{lo:.4f}, {hi:.4f}]"


def moved(r1: str, r2: str) -> str:
    return "no" if r1 == r2 else f"**yes** ({r1} → {r2})"


def intro(sprint: str, ref_label: str, this_label: str, what: str) -> list[str]:
    return [
        f"Reference: **{ref_label}**. This: **{this_label}**. Every statistic below is computed by the same code, "
        "with the same bootstrap labels, on the reference and on this population; the difference this − reference "
        "carries a percentile interval from the paired draws when both rest on the same clusters, and none "
        f"otherwise. {what} The difference is the **sensitivity** of the sprint's readings to the change, not a "
        "registered test: it enters no Holm family and carries no reading (D-061).", "",
    ]
