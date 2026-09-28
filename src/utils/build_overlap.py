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

The OE figures are computed on the **dev** split only. They describe the benchmark rather than a
run, but looking at test queries before S12 is looking at test (operating rule 2). **The OEB
validation is the exception, and it is declared rather than hidden:** it reads every OEB
`resumen`/`texto` pair, because that is the population the reference was measured on, and roughly
half of those pairs belong to concepts that are on OE's *test* side (the table prints how many).
No retrieval parameter is set from it; it fixes only which overlap definition is used (S3 audit F10).

Every number in the prose is interpolated from a computed value (S3 audit F1), and every slice
carries a concept-clustered interval, because the thin ones cannot be read without one (F7).

    python src/utils/build_overlap.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_results_s2 import B, SEED, boot_cluster, ci  # noqa: E402
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




def has_topo_drift(query: str, target: str) -> bool:
    """The one documented semantic drift of D-004: "con topo" rewritten as "con topografía".

    The corpus never says "topografía" (asserted in `tests/test_overlap.py`), so a query that does,
    against a target that does not, carries the drift.
    """
    return "topograf" in query.lower() and "topograf" not in target.lower()


def per_pair(pairs: list[tuple[str, str]]) -> dict[str, np.ndarray]:
    """Per-pair values behind the two columns that carry an interval; NaN where undefined."""
    lex = [lexical_coverage(q, d) for q, d in pairs]
    return {
        "lexical": np.array([np.nan if x is None else x for x in lex], dtype=float),
        "delta": np.array([numbers_in(q) - numbers_in(d) for q, d in pairs], dtype=float),
    }


def intervals(pairs: list[tuple[str, str]], clusters: list[str], label: str) -> dict[str, tuple[float, float]]:
    """Concept-clustered 95 % intervals for lexical mean (in %) and Δ numbers."""
    values = per_pair(pairs)
    clusters = np.asarray(clusters)
    out: dict = {"concepts": len(set(clusters.tolist()))}
    if out["concepts"] < 2:
        # Resampling one concept returns that concept every time: an interval of width zero that
        # would read as certainty. Print no interval instead, and say why.
        return out
    for key, scale in (("lexical", 100.0), ("delta", 1.0)):
        v = values[key]
        keep = ~np.isnan(v)
        draws = boot_cluster(v[keep][:, None], clusters[keep], f"overlap|{key}|{label}")
        lo, hi = ci(draws[:, 0])
        out[key] = (scale * lo, scale * hi)
    return out


# --------------------------------------------------------------------------- the gate


def oeb_pairs() -> list[tuple[dict, tuple[str, str]]]:
    resumen = json.loads((DATA / "OEB_resumen.json").read_text(encoding="utf-8"))
    texto = {r["item_key"]: r["text"] for r in json.loads((DATA / "OEB_texto.json").read_text(encoding="utf-8"))}
    return [(r, (r["text"], texto[r["item_key"]])) for r in resumen if r["item_key"] in texto]


def validate_against_oeb() -> tuple[dict, list[str]]:
    observed = measure([p for _, p in oeb_pairs()])
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


def oeb_pairs_in_test() -> int:
    """How many validation pairs belong to concepts on OE's test side (S3 audit F10)."""
    test = load_split("test")
    return sum(r.get("parent_key") in test for r, _ in oeb_pairs())


# --------------------------------------------------------------------------- OE slices


def load(name: str) -> list[dict]:
    return json.loads((DATA / f"OE_{name}.json").read_text(encoding="utf-8"))


Slice = tuple[str, str, list[tuple[str, str]], list[str]]


def oe_slices() -> list[Slice]:
    """(query set, slice label, pairs, concept of each pair) on the dev split only."""
    dev = load_split("dev")
    corpus = load("texto")
    target_of = {r["item_key"]: r["text"] for r in corpus}

    def mk(query_set: str, label: str, rows: list[dict], gold: str) -> Slice:
        return (query_set, label, [(r["text"], target_of[r[gold]]) for r in rows],
                [r["parent_key"] for r in rows])

    out: list[Slice] = []

    # The replication regime: the leaf's own summary asked of its own long description.
    out.append(mk("`resumen`", "all", [r for r in load("resumen") if r["parent_key"] in dev], "item_key"))

    # The identity rendering. Coverage is 1.0 by construction; it is here as a control on the
    # measurement, not as a finding.
    out.append(mk("`texto` (identity)", "all", [r for r in corpus if r["parent_key"] in dev], "item_key"))

    single = [r for r in load("single_texto") if r["parent_key"] in dev]
    out.append(mk("`single_texto`", "all", single, "gold_item_key"))
    for mod_type in sorted({r["modification_types"][0] for r in single}):
        out.append(mk("`single_texto`", f"`{mod_type}`",
                      [r for r in single if r["modification_types"][0] == mod_type], "gold_item_key"))

    stacked = [r for r in load("stacked_texto") if r["parent_key"] in dev]
    out.append(mk("`stacked_texto`", "all", stacked, "gold_item_key"))
    for dose in sorted({r["texto_modification_count"] for r in stacked}):
        out.append(mk("`stacked_texto`", f"dose {dose}",
                      [r for r in stacked if r["texto_modification_count"] == dose], "gold_item_key"))

    return out


def replication_coverage() -> tuple[dict, dict, int]:
    """(OEB observed, OE dev `resumen`, OEB pairs on OE's test side) — for E0(b)'s prose."""
    observed, _ = validate_against_oeb()
    _, _, pairs, _ = oe_slices()[0]
    return observed, measure(pairs), oeb_pairs_in_test()


#: D-004's two pantry artefacts, each a predicate over (record, target text).
ARTEFACTS = {
    "doubled": lambda r, target: has_doubled_token(r["text"]),
    "topo": lambda r, target: has_topo_drift(r["text"], target),
}

Item = tuple[tuple[str, str], str]


def sensitivity_rows() -> list[tuple[str, str, dict[str, list[Item]]]]:
    """(query set, slice, partition) — the D-004 check at every level a claim is made.

    Partitioned by the predicates on each record, not by differencing pair lists: two queries can
    carry the same text against the same target, and a set difference would then drop or
    double-count them. Every query is either clean or flagged, and that is asserted.
    """
    dev = load_split("dev")
    target_of = {r["item_key"]: r["text"] for r in load("texto")}
    out = []
    for name, key in (("single_texto", lambda r: f"`{r['modification_types'][0]}`"),
                      ("stacked_texto", lambda r: f"dose {r['texto_modification_count']}")):
        rows = [r for r in load(name) if r["parent_key"] in dev]
        slices = [("all", rows)] + [(k, [r for r in rows if key(r) == k]) for k in sorted({key(r) for r in rows})]
        for label, members in slices:
            part: dict[str, list[Item]] = {"all": [], "doubled": [], "topo": [], "clean": []}
            flagged = 0
            for r in members:
                target = target_of[r["gold_item_key"]]
                item = ((r["text"], target), r["parent_key"])
                part["all"].append(item)
                flags = {k: f(r, target) for k, f in ARTEFACTS.items()}
                for k, hit in flags.items():
                    if hit:
                        part[k].append(item)
                if any(flags.values()):
                    flagged += 1
                else:
                    part["clean"].append(item)
            assert len(part["clean"]) + flagged == len(part["all"]), f"{name}/{label}: partition does not add up"
            out.append((f"`{name}`", label, part))
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


WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four"}


def fci_pc(iv: dict | None) -> str:
    if not iv or "lexical" not in iv:
        return "— (one concept)" if iv else "—"
    return f"[{iv['lexical'][0]:.2f}, {iv['lexical'][1]:.2f}]"


def fci_d(iv: dict | None) -> str:
    if not iv or "delta" not in iv:
        return "— (one concept)" if iv else "—"
    return f"[{iv['delta'][0]:+.2f}, {iv['delta'][1]:+.2f}]"


def row(label_a: str, label_b: str, stats: dict, iv: dict) -> str:
    cells = [fmt.format(stats[key]) for key, _, fmt in COLUMNS]
    cells.insert(1, f"{iv['concepts']:,}")
    cells.insert(3, fci_pc(iv))
    cells.append(fci_d(iv))
    return f"| {label_a} | {label_b} | " + " | ".join(cells) + " |"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    observed, validation_rows = validate_against_oeb()
    in_test = oeb_pairs_in_test()
    dev = load_split("dev")

    names = [name for _, name, _ in COLUMNS]
    head = "| query set | slice | " + " | ".join(
        names[:1] + ["concepts"] + names[1:2] + ["CI (concept)"] + names[2:] + ["CI (concept)"]) + " |"
    rule = "|---|---|" + "---:|" * 3 + "---|" + "---:|" * (len(COLUMNS) - 2) + "---|"

    ref = OEB_REFERENCE
    exact = abs(observed["lexical_median"] - ref["lexical_median"]) < 0.005
    lines = [
        "# S3 — lexical and numeric overlap with the target",
        "",
        f"Generated by `{GENERATOR}`. **OE figures: dev split only** — overlap describes the benchmark "
        "rather than a run, but reading test queries before S12 is reading test (operating rule 2). "
        "**The OEB validation below is the declared exception** (see there).",
        "",
        "Lexical coverage is the share of the query's **distinct** normalised tokens that appear in "
        "the target; numeric coverage the share of its numbers. Both use this repo's own "
        "`normalize_text` / `tokenize_words` / `extract_numbers`, so what is measured is what the "
        "lexical retrievers actually see.",
        "",
        "## The definition is validated before it is used",
        "",
        f"The reviewers' objection was granted on the strength of one measurement: on OEB, the target "
        f"holds {ref['lexical_mean']:.2f} % of the query's tokens and {ref['numeric_mean']:.2f} % of its "
        "numbers (`docs/reviews/AUTCON_analisis_revision.md` §2.6). This generator recomputes those "
        "figures first and **refuses to report anything if they do not come back**, because a definition "
        "that cannot reproduce them is measuring something else and every OE figure would inherit that "
        "silently.",
        "",
        "| statistic | reference | recomputed | gap | |",
        "|---|---:|---:|---:|---|",
        *validation_rows,
        "",
        f"Tolerance {TOLERANCE_PP:.1f} pp. The reference was measured on \"20.000 pares alineados\"; "
        f"these reproduce on all {observed['n']:,}, and the median lands "
        + ("**exactly** — which a different tokenisation would not" if exact else "within tolerance")
        + ". The residual on *fully contained* is the sampling difference, not a definitional one.",
        "",
        f"**This check reads test-split concepts.** It uses every OEB pair, because that is the population "
        f"the reference was measured on, and {in_test:,} of the {observed['n']:,} belong to concepts on OE's "
        "test side. The overlap definition was chosen by matching them. Nothing else was: no retrieval "
        "parameter, threshold or model choice is set from this table, and every OE figure below is dev.",
        "",
        "## OE, by query set and slice",
        "",
        "Intervals are concept-clustered percentile 95 % intervals — a slice's concepts are resampled "
        "whole, since siblings are not independent draws. They are what makes the thin slices readable.",
        "",
        head,
        rule,
    ]
    by_slice = {}
    for query_set, label, pairs, clusters in oe_slices():
        stats = measure(pairs)
        by_slice[(query_set, label)] = stats
        lines.append(row(query_set, label, stats, intervals(pairs, clusters, f"{query_set}|{label}")))

    sens = sensitivity_rows()
    clean = {(qs, label): measure([p for p, _ in part["clean"]]) for qs, label, part in sens}

    def s(t: str) -> dict:
        return by_slice[("`single_texto`", f"`{t}`")]

    def c(t: str) -> dict:
        return clean[("`single_texto`", f"`{t}`")]

    def blind(stats: dict) -> bool:
        return stats["numeric_mean"] == 100 and stats["delta_numbers"] < 0

    removing = [t for t in ("num_to_text", "unit_expansion") if blind(s(t)) and blind(c(t))]
    nt, ue, uc = s("num_to_text"), s("unit_expansion"), s("unit_conversion")
    lines += [
        "",
        "`texto` is the identity rendering, where the query **is** the target: 100 % on every "
        "coverage column is the control that the measurement is wired correctly, not a result.",
        "",
        f"**Numeric coverage cannot see {WORDS[len(removing)]} of the four L1 types, and the last columns are "
        f"why.** `num_to_text` changes numbers / query by {nt['delta_numbers']:+.2f} against the same gold "
        f"({nt['gold_numbers_per_query']:.2f} → {nt['numbers_per_query']:.2f}) by spelling a number out, and "
        f"`unit_expansion` by {ue['delta_numbers']:+.2f}. The affected number is not *missed* by the target, "
        f"it is no longer in the query to miss, so numeric coverage stays at {nt['numeric_mean']:.2f} % and "
        f"{ue['numeric_mean']:.2f} % while the numeric surface the retriever matches on has shrunk. "
        f"`unit_conversion`, which rewrites a value rather than removing it, appears as lost coverage: "
        f"{uc['numeric_mean']:.2f} %, with {uc['all_numbers']:.2f} % of its queries retaining all their "
        "numbers. **H5 must therefore be stated over both columns.**",
        "",
        "**The pattern survives removing both pantry artefacts** (next section): on the clean subset "
        + ", ".join(f"`{t}` is at {c(t)['numeric_mean']:.2f} % numeric coverage with Δ {c(t)['delta_numbers']:+.2f}"
                    for t in ("num_to_text", "unit_expansion", "unit_conversion"))
        + "."
        if len(removing) == 2 else
        "**The pattern does not fully survive removing the pantry artefacts** — read the next section "
        "before any per-type figure.",
        "",
        "## D-004 sensitivity: excluding the pantry artefacts, at every level a claim is made",
        "",
        "Upstream kept two artefacts as documented stress, and D-004 requires a sensitivity analysis "
        "excluding them **before any per-type claim**:",
        "",
        "- **token doubling** (\"tubos tubos\", \"mm mm\"), detected from the text as an immediately "
        "repeated token rather than from upstream's modifications sidecar, which this branch has not "
        "taken in. The detector is sound here because immediate repetition never occurs in the corpus's "
        "own `texto` (asserted over every document by `tests/test_overlap.py`);",
        "- **the \"con topo\" → \"con topografía\" drift**, detected as a query saying *topografía* "
        "against a target that does not. The corpus never does (asserted by the same file).",
        "",
        "*Clean* excludes a query carrying either. The interval is on the clean subset.",
        "",
        "| query set | slice | n | doubled | topo drift | n clean | lexical mean | clean | CI (concept) | "
        "numeric mean | clean | Δ numbers | clean | CI (concept) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]
    for qs, label, part in sens:
        a = measure([p for p, _ in part["all"]])
        k = clean[(qs, label)]
        cp = [p for p, _ in part["clean"]]
        iv = intervals(cp, [g for _, g in part["clean"]], f"clean|{qs}|{label}") if len(cp) > 1 else None
        lines.append(
            f"| {qs} | {label} | {a['n']:,} | {len(part['doubled']):,} | {len(part['topo']):,} | {k['n']:,} | "
            f"{a['lexical_mean']:.2f} % | {k['lexical_mean']:.2f} % | {fci_pc(iv)} | "
            f"{a['numeric_mean']:.2f} % | {k['numeric_mean']:.2f} % | "
            f"{a['delta_numbers']:+.2f} | {k['delta_numbers']:+.2f} | {fci_d(iv)} |"
        )

    single = {label: part for qs, label, part in sens if qs == "`single_texto`"}
    share = {label: len(p["doubled"]) / len(p["all"]) for label, p in single.items() if label != "all" and p["all"]}
    top = sorted(share, key=share.get, reverse=True)[:3]
    lines += [
        "",
        f"Doubling is not spread evenly: {len(single['all']['doubled']):,} of {len(single['all']['all']):,} "
        "`single_texto` queries carry it, concentrated in "
        + ", ".join(f"{t} ({100 * share[t]:.1f} %)" for t in top)
        + ". That is why the check has to be per type and not only on `all`.",
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
    lines.append(f"Split: `dev`, from `SPLITS.md` ({len(dev)} concepts). Bootstrap: B = {B:,}, seed = {SEED}.")

    (OUT / "overlap.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written: {(OUT / 'overlap.md').relative_to(REPO)}")


if __name__ == "__main__":
    main()
