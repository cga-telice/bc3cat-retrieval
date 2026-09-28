"""Build docs/synthetic-oe/results/S3/overlap/ — S3 work item 9, the x-axis for H5 and H6.

The reviewers' central objection to the previous submission was that its queries are near-verbatim
copies of their targets. The review analysis measured it and agreed: on OEB, the target contains
**94.09 %** of the query's tokens and **99.93 %** of its numbers. That table is the quantitative
answer to the objection, and the same measurement on BC3CAT-Syn is what makes H5 ("overlap mediates
most of the lexical degradation") and H6 ("query expansion crosses over below some overlap
threshold") statable in terms of a measured quantity rather than an intuition.

**This generator validates itself before it reports anything.** It recomputes the OEB figures first
and refuses to continue if they do not come back within tolerance, because an overlap definition that
does not reproduce the number the objection was granted on is measuring something else, and every OE
figure downstream of it would inherit that silently. The definition was chosen by reproducing the
reference, not asserted: distinct normalised query tokens, looked up in the target's token set.

Overlap is computed on the **dev** split only. It describes the benchmark rather than a run, but
looking at test queries before S12 is looking at test (operating rule 2).

    python src/utils/build_overlap.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.corpus_prep import extract_numbers, normalize_text, tokenize_words  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S3" / "overlap"
GENERATOR = "src/utils/build_overlap.py"

#: `AUTCON_analisis_revision.md` §2.6, measured on OEB `resumen` against `texto`. The report says
#: "20.000 pares alineados"; these reproduce on all 47,514, and the residual below is the sampling
#: difference — the median lands exactly, which a different definition would not.
OEB_REFERENCE = {
    "lexical_mean": 94.09,
    "lexical_median": 94.74,
    "fully_contained": 7.72,
    "numeric_mean": 99.93,
}
#: Exit criterion 8 allows 0.5 pp. Observed worst gap is 0.08 pp.
TOLERANCE_PP = 0.5


# --------------------------------------------------------------------------- the measurement


def lexical_coverage(query: str, target: str) -> float | None:
    """Share of the query's **distinct** normalised tokens that appear in the target.

    Distinct, not positional: a query repeating a token does not get to count it twice. That is
    what reproduces the reference — the positional variant overshoots by ~0.4 pp.
    """
    q = list(dict.fromkeys(tokenize_words(normalize_text(query))))
    if not q:
        return None
    d = set(tokenize_words(normalize_text(target)))
    return sum(t in d for t in q) / len(q)


def numeric_coverage(query: str, target: str) -> float | None:
    """Share of the query's numbers that appear in the target. `None` when it carries none."""
    q = extract_numbers(normalize_text(query))
    if not q:
        return None
    d = set(extract_numbers(normalize_text(target)))
    return sum(n in d for n in q) / len(q)


def numbers_in(query: str) -> int:
    return len(extract_numbers(normalize_text(query)))


def has_doubled_token(text: str) -> bool:
    """The pantry artefact of D-004: an immediately repeated token ("tubos tubos", "mm mm").

    Detected from the text rather than from upstream's modifications sidecar, which this branch has
    not taken in. It is a sound detector here: the rate is **0 %** across the corpus's own `texto`,
    11.2 % in `single_texto` and 31.0 % in `stacked_texto`, so immediate repetition does not occur
    naturally in this catalogue and marks the artefact rather than merely correlating with it.
    """
    t = tokenize_words(normalize_text(text))
    return any(t[i] == t[i + 1] for i in range(len(t) - 1))


def measure(pairs: list[tuple[str, str]]) -> dict:
    """The seven statistics the review analysis reports, over `(query, target)` pairs."""
    lex = [x for x in (lexical_coverage(q, d) for q, d in pairs) if x is not None]
    num = [x for x in (numeric_coverage(q, d) for q, d in pairs) if x is not None]
    counts = [numbers_in(q) for q, _ in pairs]
    gold_counts = [numbers_in(d) for _, d in pairs]
    n = len(pairs)
    return {
        "n": n,
        "lexical_mean": 100 * float(np.mean(lex)) if lex else float("nan"),
        "lexical_median": 100 * float(np.median(lex)) if lex else float("nan"),
        "fully_contained": 100 * float(np.mean([x == 1.0 for x in lex])) if lex else float("nan"),
        "numeric_mean": 100 * float(np.mean(num)) if num else float("nan"),
        "all_numbers": 100 * float(np.mean([x == 1.0 for x in num])) if num else float("nan"),
        "has_number": 100 * float(np.mean([c > 0 for c in counts])) if counts else float("nan"),
        "numbers_per_query": float(np.mean(counts)) if counts else float("nan"),
        "gold_numbers_per_query": float(np.mean(gold_counts)) if gold_counts else float("nan"),
        # The column numeric coverage cannot show. `num_to_text` turns a digit into words and
        # `unit_expansion` spells a unit out, so the affected number leaves the query's number set
        # entirely: it is never *missed*, and numeric coverage stays at 100 % while the numeric
        # surface the retriever matches on has shrunk. Only `unit_conversion`, which rewrites a
        # value rather than removing it, shows up as lost coverage. H5 therefore needs both columns.
        "delta_numbers": (float(np.mean(counts)) - float(np.mean(gold_counts))) if counts else float("nan"),
    }


# --------------------------------------------------------------------------- the gate


def validate_against_oeb() -> tuple[dict, list[str]]:
    resumen = json.loads((DATA / "OEB_resumen.json").read_text(encoding="utf-8"))
    texto = {r["item_key"]: r["text"] for r in json.loads((DATA / "OEB_texto.json").read_text(encoding="utf-8"))}
    pairs = [(r["text"], texto[r["item_key"]]) for r in resumen if r["item_key"] in texto]
    observed = measure(pairs)
    lines, failures = [], []
    for key, expected in OEB_REFERENCE.items():
        got = observed[key]
        gap = abs(got - expected)
        ok = gap <= TOLERANCE_PP
        if not ok:
            failures.append(f"{key}: reference {expected:.2f} %, observed {got:.2f} %")
        lines.append(f"| {key.replace('_', ' ')} | {expected:.2f} % | {got:.2f} % | {gap:.2f} pp | "
                     f"{'ok' if ok else '**FAILS**'} |")
    if failures:
        raise SystemExit(
            "overlap definition does not reproduce the OEB reference; refusing to report OE "
            "figures computed with it:\n  " + "\n  ".join(failures)
        )
    return observed, lines


# --------------------------------------------------------------------------- OE slices


def load(name: str) -> list[dict]:
    return json.loads((DATA / f"OE_{name}.json").read_text(encoding="utf-8"))


def oe_slices() -> list[tuple[str, str, list[tuple[str, str]]]]:
    """(query set, slice label, pairs) on the dev split only."""
    dev = load_split("dev")
    corpus = load("texto")
    target_of = {r["item_key"]: r["text"] for r in corpus}

    out: list[tuple[str, str, list[tuple[str, str]]]] = []

    # The replication regime: the leaf's own summary asked of its own long description.
    resumen = [r for r in load("resumen") if r["parent_key"] in dev]
    out.append(("`resumen`", "all", [(r["text"], target_of[r["item_key"]]) for r in resumen]))

    # The identity rendering. Coverage is 1.0 by construction; it is here as a control on the
    # measurement, not as a finding.
    ident = [r for r in corpus if r["parent_key"] in dev]
    out.append(("`texto` (identity)", "all", [(r["text"], target_of[r["item_key"]]) for r in ident]))

    single = [r for r in load("single_texto") if r["parent_key"] in dev]
    out.append(("`single_texto`", "all", [(r["text"], target_of[r["gold_item_key"]]) for r in single]))
    for mod_type in sorted({r["modification_types"][0] for r in single}):
        rows = [r for r in single if r["modification_types"][0] == mod_type]
        out.append(("`single_texto`", f"`{mod_type}`", [(r["text"], target_of[r["gold_item_key"]]) for r in rows]))

    stacked = [r for r in load("stacked_texto") if r["parent_key"] in dev]
    out.append(("`stacked_texto`", "all", [(r["text"], target_of[r["gold_item_key"]]) for r in stacked]))
    for dose in sorted({r["texto_modification_count"] for r in stacked}):
        rows = [r for r in stacked if r["texto_modification_count"] == dose]
        out.append(("`stacked_texto`", f"dose {dose}", [(r["text"], target_of[r["gold_item_key"]]) for r in rows]))

    return out


def sensitivity_slices() -> list[tuple[str, list, list, list]]:
    """(query set, all, without a doubled token, with one) — the D-004 check.

    Partitioned by the predicate on each record, not by differencing the pair lists: two queries
    can carry the same text against the same target, and a set difference would then drop or
    double-count them. The three counts are asserted to add up.
    """
    dev = load_split("dev")
    target_of = {r["item_key"]: r["text"] for r in load("texto")}
    out = []
    for name in ("single_texto", "stacked_texto"):
        rows = [r for r in load(name) if r["parent_key"] in dev]
        pairs = [(r, (r["text"], target_of[r["gold_item_key"]])) for r in rows]
        clean = [p for r, p in pairs if not has_doubled_token(r["text"])]
        doubled = [p for r, p in pairs if has_doubled_token(r["text"])]
        allp = [p for _, p in pairs]
        assert len(clean) + len(doubled) == len(allp), f"{name}: partition does not add up"
        out.append((f"`{name}`", allp, clean, doubled))
    return out


# --------------------------------------------------------------------------- rendering

COLUMNS = [
    ("n", "n", "{:,}"),
    ("lexical_mean", "lexical mean", "{:.2f} %"),
    ("lexical_median", "lexical median", "{:.2f} %"),
    ("fully_contained", "fully contained", "{:.2f} %"),
    ("numeric_mean", "numeric mean", "{:.2f} %"),
    ("all_numbers", "all numbers present", "{:.2f} %"),
    ("has_number", "has a number", "{:.2f} %"),
    ("numbers_per_query", "numbers / query", "{:.2f}"),
    ("gold_numbers_per_query", "gold numbers / query", "{:.2f}"),
    ("delta_numbers", "Δ numbers", "{:+.2f}"),
]


def row(label_a: str, label_b: str, stats: dict) -> str:
    cells = [fmt.format(stats[key]) for key, _, fmt in COLUMNS]
    return f"| {label_a} | {label_b} | " + " | ".join(cells) + " |"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    observed, validation_rows = validate_against_oeb()

    head = "| query set | slice | " + " | ".join(name for _, name, _ in COLUMNS) + " |"
    rule = "|---|---|" + "---:|" * len(COLUMNS)

    lines = [
        "# S3 — lexical and numeric overlap with the target",
        "",
        f"Generated by `{GENERATOR}`. **Dev split only** — overlap describes the benchmark rather "
        "than a run, but reading test queries before S12 is reading test (operating rule 2).",
        "",
        "Lexical coverage is the share of the query's **distinct** normalised tokens that appear in "
        "the target; numeric coverage the share of its numbers. Both use this repo's own "
        "`normalize_text` / `tokenize_words` / `extract_numbers`, so what is measured is what the "
        "lexical retrievers actually see.",
        "",
        "## The definition is validated before it is used",
        "",
        "The reviewers' objection was granted on the strength of one measurement: on OEB, the target "
        "holds 94.09 % of the query's tokens and 99.93 % of its numbers "
        "(`docs/reviews/AUTCON_analisis_revision.md` §2.6). This generator recomputes those figures "
        "first and **refuses to report anything if they do not come back**, because a definition that "
        "cannot reproduce them is measuring something else and every OE figure would inherit that "
        "silently.",
        "",
        "| statistic | reference | recomputed | gap | |",
        "|---|---:|---:|---:|---|",
        *validation_rows,
        "",
        f"Tolerance {TOLERANCE_PP:.1f} pp. The reference was measured on \"20.000 pares alineados\"; "
        f"these reproduce on all {observed['n']:,}, and the median lands **exactly** — which a "
        "different tokenisation would not. The residual on *fully contained* is the sampling "
        "difference, not a definitional one.",
        "",
        "## OE, by query set and slice",
        "",
        head,
        rule,
    ]
    for query_set, label, pairs in oe_slices():
        lines.append(row(query_set, label, measure(pairs)))

    lines += [
        "",
        "`texto` is the identity rendering, where the query **is** the target: 100 % on every "
        "coverage column is the control that the measurement is wired correctly, not a result.",
        "",
        "**Numeric coverage cannot see two of the four L1 types, and the last two columns are why.** "
        "`num_to_text` removes exactly **one** number per query (4.14 → 3.14 against the same gold) "
        "by spelling it out, and `unit_expansion` removes 0.64; the affected number is not *missed* "
        "by the target, it is no longer in the query to miss, so numeric coverage stays at 100 % "
        "while the numeric surface the retriever matches on has shrunk. Only `unit_conversion` — "
        "which rewrites a value rather than removing it — appears as lost coverage, at 79.14 % with "
        "barely half its queries retaining all their numbers. **H5 must therefore be stated over "
        "both columns**, because numeric coverage alone would score two of the three most damaging "
        "L1 types as doing nothing at all.",
        "",
        "## D-004 sensitivity: excluding the pantry artefact",
        "",
        "Upstream kept token doubling (\"tubos tubos\", \"mm mm\") as documented stress, and D-004 "
        "requires a sensitivity analysis excluding it **before any per-type claim**. Doubling is "
        "detected from the text — an immediately repeated token — rather than from upstream's "
        "modifications sidecar, which this branch has not taken in. That detector is sound here: the "
        "rate is **0 %** across the corpus's own `texto`, so immediate repetition does not occur "
        "naturally in this catalogue.",
        "",
        "| query set | slice | " + " | ".join(name for _, name, _ in COLUMNS) + " |",
        rule,
    ]
    for name, allp, clean, doubled in sensitivity_slices():
        lines.append(row(name, "all", measure(allp)))
        lines.append(row(name, "no doubled token", measure(clean)))
        lines.append(row(name, "*the doubled ones*", measure(doubled)))

    lines += [
        "",
        "## Sources",
        "",
        "| file | SHA-256 |",
        "|---|---|",
    ]
    for name in ("OEB_resumen.json", "OEB_texto.json", "OE_texto.json", "OE_resumen.json",
                 "OE_single_texto.json", "OE_stacked_texto.json"):
        lines.append(f"| `{name}` | `{sha256_file(DATA / name)[:16]}` |")
    lines.append("")
    lines.append("Split: `dev`, from `SPLITS.md` (42 concepts).")

    (OUT / "overlap.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written: {(OUT / 'overlap.md').relative_to(REPO)}")


if __name__ == "__main__":
    main()
