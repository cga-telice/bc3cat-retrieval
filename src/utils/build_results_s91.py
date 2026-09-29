"""Build docs/synthetic-oe/results/S91/ — S91 work item 6.

Three renderings of the catalogue's own `resumen`, paired on the same OE dev leaves against the
same indexes: **coded** (the catalogue's text, `(N/<3/R)`), **stripped** (the suffix removed) and
**decoded** (the codes replaced by their values). Ten arms. The coded runs are S3's E0(b) runs,
reused by digest; the other twenty are S91's.

- `decoder.md` (T1) — the decoder, what it covers on dev and how exactly it decodes.
- `renderings.md` (T2) — per arm and condition, Acc@1 at both levels with ceilings, and the three
  paired contrasts; P1 and P2 read against their registered rules.
- `coverage.md` (T3) — lexical and numeric coverage of each rendering against its gold `texto`.
- `subchapter.md` (T4) — OEB against the rest, descriptive.
- `rare_codes.md` (T5) — the rare-code diagnostic for the lexical arms on the coded rendering.

**Population P** (design): dev leaves whose `resumen` carries a suffix and whose gold `texto` is
unique (D-033). Leaves without a suffix are identical in all three renderings, so their paired delta
is zero by construction; all-query figures are printed as secondary. `resumen`-identical siblings are
**not** excluded — which leaves are identical changes with the rendering — and each condition prints
its own text-only ceiling on P instead.

**Every number in the prose is interpolated** (`tests/test_generated_prose.py`).

    python src/utils/build_results_s91.py
"""

from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_overlap import lexical_coverage, numeric_coverage  # noqa: E402
from utils.build_results_s2 import (  # noqa: E402
    ALPHA,
    B,
    SEED,
    bh,
    boot_cluster,
    boot_p,
    boot_query,
    ci,
    f4,
    fci,
    fd,
    fp,
    holm,
    write,
)
from utils.build_resumen_renderings import AXES, MIN_SHARE, axis_value, split_suffix, tokens  # noqa: E402
from utils.corpus_prep import normalize_param_string, normalize_text, tokenize_words  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.splits import DEFAULT_PATH as SPLITS_FILE, load_split  # noqa: E402

RUNS = REPO / "runs" / "OE"
DATA = REPO / "data" / "processed"
SIDECAR = DATA / "OE_duplicate_texto_groups.json"
DECODER = DATA / "OE_resumen_decoder.json"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S91"
GENERATOR = "src/utils/build_results_s91.py"
LONG_FEATS = DATA / "OE_long_feats.parquet"

#: The ten arms, as S3 ordered them. `True` marks an oracle arm (D-010).
TEN = [
    ("bm25_unigram_params__k1-0.60__b-0.35__OE", "bm25_unigram_params", True),
    ("bm25_unigram__k1-0.60__b-0.35__OE", "bm25_unigram", False),
    ("tfidf_unigram_phrases_replace__OE", "tfidf_phrases_replace", True),
    ("bge_m3_colbert__OE", "bge_m3_colbert", False),
    ("bge_m3_dense__OE", "bge_m3_dense", False),
    ("bge_m3_sparse__OE", "bge_m3_sparse", False),
    ("dense_e5__OE", "dense_e5", False),
    ("dense_es_hiiamsid__OE", "dense_es_hiiamsid", False),
    ("dense_gte__OE", "dense_gte", False),
    ("dense_gte_instrQ__OE", "dense_gte_instrQ", False),
]
ORACLE = {short for _, short, oracle in TEN if oracle}

#: (label, query set, JSON the rendering's text is read from).
CONDITIONS = [
    ("coded", "resumen", "OE_resumen.json"),
    ("stripped", "resumen_stripped", "OE_resumen_stripped.json"),
    ("decoded", "resumen_decoded", "OE_resumen_decoded.json"),
]
#: (label, treatment, reference) — the three paired contrasts the design names.
CONTRASTS = [
    ("stripped − coded", "stripped", "coded"),
    ("decoded − stripped", "decoded", "stripped"),
    ("decoded − coded", "decoded", "coded"),
]
LEVELS = ("item", "parent")

#: The registered predictions (design, "Design constraints"), read on the concept-clustered
#: interval after Holm across the ten arms.
PREDICTIONS = [
    ("P1", "decoded − coded", "item", ("bm25_unigram_params", "bm25_unigram", "tfidf_phrases_replace")),
    ("P2", "stripped − coded", "parent", ("bm25_unigram", "bm25_unigram_params")),
]

#: The lexical arms the rare-code diagnostic (T5) covers.
LEXICAL = ("bm25_unigram_params", "bm25_unigram", "tfidf_phrases_replace")

#: The previous study's item Acc@1 for tuned BM25 — `docs/reviews/paper_28.tex`, authoritative.
#: Printed beside the decoded figure as reference only (D-039); never differenced.
PREVIOUS = {"bm25_unigram_params": 0.974}

WORDS = {0: "none", 1: "one", 2: "two", 3: "three"}


# --------------------------------------------------------------------------- inputs


def records(name: str) -> dict[str, dict]:
    return {r["item_key"]: r for r in json.loads((DATA / name).read_text(encoding="utf-8"))}


def perquery(queryset: str, method: str) -> pd.DataFrame:
    return pd.read_parquet(RUNS / queryset / method / "results_perquery.parquet")


def meta(queryset: str, method: str) -> dict:
    return json.loads((RUNS / queryset / method / "run_meta.json").read_text(encoding="utf-8"))


def flagged() -> set[str]:
    return {m for g in json.loads(SIDECAR.read_text(encoding="utf-8"))["groups"].values() for m in g}


def english_list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S91 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


#: The run whose per-query table defines the dev population every table reads (`population`).
POPULATION_RUN = ("resumen", TEN[0][0])


def sources(keys: list[tuple[str, str]], note: str = "", inputs: tuple[Path, ...] = ()) -> list[str]:
    """Stamp every run and every file a table reads. A table computed from files alone says so
    rather than printing an empty run table (S91 audit F2)."""
    lines = ["", "## Sources", ""]
    if not keys:
        lines.append("No run is read: this table is computed from the input files below alone.")
    else:
        lines += ["| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
                  "|---|---:|---|---|---|---|"]
    for queryset, method in keys:
        m = meta(queryset, method)
        lines.append(
            f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
            f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
            f"`{m['query_set_sha256'][:16]}` |"
        )
    if note:
        lines += ["", note]
    lines += [
        "",
        "| input | SHA-256 |",
        "|---|---|",
        *(f"| `{path.relative_to(REPO).as_posix() if path == SPLITS_FILE else path.name}` | "
          f"`{sha256_file(path)[:16]}` |" for path in (SIDECAR, DECODER, *inputs)),
        "",
        f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals; p from the concept-clustered "
        "draws (D-030). Split `dev`.",
    ]
    return lines


# --------------------------------------------------------------------------- population


def population(coded: dict[str, dict], dup: set[str]) -> dict:
    """The dev leaves, those with a suffix, and P = suffixed ∩ unique gold `texto`."""
    frame = perquery(*POPULATION_RUN)
    dev = list(frame["query_item_key"])
    suffixed = {k for k in dev if split_suffix(coded[k]["text"]) is not None}
    return {
        "dev": dev,
        "suffixed": suffixed,
        "P": {k for k in suffixed if k not in dup},
        "dup": dup,
        "parent_of": dict(zip(frame["query_item_key"], frame["gold_parent_key"])),
    }


def joined(method: str, keys: set[str]) -> pd.DataFrame:
    """One row per query in `keys`: each condition's item and parent Acc@1, paired by query key."""
    out = None
    for label, queryset, _ in CONDITIONS:
        f = perquery(queryset, method)[["query_item_key", "gold_parent_key", "item_acc1", "parent_acc1"]]
        f = f.rename(columns={"item_acc1": f"item_{label}", "parent_acc1": f"parent_{label}"})
        if out is None:
            out = f
        else:
            before = len(out)
            out = out.merge(f.drop(columns="gold_parent_key"), on="query_item_key", validate="one_to_one")
            if len(out) != before:
                raise SystemExit(f"{method}: {label} does not hold the same queries as coded")
    out = out[out["query_item_key"].isin(keys)].reset_index(drop=True)
    if len(out) != len(keys):
        raise SystemExit(f"{method}: {len(keys) - len(out)} queries of the population are missing")
    return out


def text_ceiling(texts: dict[str, str], keys: set[str]) -> float:
    """Text-only item ceiling on `keys`: one findable member per group of identical query text.

    Identity is on the raw text with whitespace collapsed: two queries identical there are
    identical to every arm, whatever it tokenises, so this is an upper bound for all of them."""
    norm = [re.sub(r"\s+", " ", texts[k]).strip() for k in keys]
    return len(set(norm)) / len(norm)


# --------------------------------------------------------------------------- T1 — decoder


def decoder_exactness(coded: dict[str, dict], table: dict, dev: set[str]) -> dict:
    """Per axis over dev leaves with a suffix: how the decoded value relates to the leaf's own."""
    per_axis = {axis: collections.Counter() for axis in AXES}
    exact_all = 0
    n = 0
    for record in coded.values():
        if record["parent_key"] not in dev:
            continue
        parts = split_suffix(record["text"])
        if parts is None:
            continue
        n += 1
        exact_here = True
        for position, code in enumerate(parts[2]):
            axis = AXES[position]
            decoded = table["entries"].get(f"{position}|{code}", {}).get("decodes_to", "")
            actual = axis_value(record, axis)
            if actual is None:
                kind = "written for an absent axis" if decoded else "absent axis, nothing written"
            elif not decoded:
                kind = "nothing written"
                exact_here = False
            elif normalize_param_string(decoded) == normalize_param_string(actual):
                kind = "exact"
            elif tokens(decoded) <= tokens(actual):
                kind = "partial (a subset of the value's words)"
                exact_here = False
            else:
                kind = "wrong"
                exact_here = False
            per_axis[axis][kind] += 1
        exact_all += exact_here
    return {"n": n, "per_axis": per_axis, "exact_all": exact_all}


def write_decoder(coded: dict[str, dict], table: dict, dev: set[str]) -> None:
    ex = decoder_exactness(coded, table, dev)
    lines = header(
        "T1: the decoder (dev)",
        [
            "The decoder is keyed by *(suffix position, code)* and fitted on dev leaves only "
            "(`build_resumen_renderings.py`). Each code decodes to the words common to every value it "
            "takes on dev, in its most frequent spelling; a value seen on under "
            f"{MIN_SHARE:.0%} of a code's dev occurrences takes no part (amendment A1). It reads neither "
            "the concept nor the gold.",
        ],
    )
    lines += ["| position | axis | code | decodes to | values on dev | axis absent on dev | ignored (A1) |",
              "|---:|---|---|---|---:|---:|---|"]
    for entry in sorted(table["entries"].values(), key=lambda e: (e["position"], e["code"])):
        lines.append(
            f"| {entry['position'] + 1} | {entry['axis']} | `{entry['code']}` | "
            f"{entry['decodes_to'] or '— (nothing)'} | {sum(entry['values_on_dev'].values()):,} | "
            f"{entry['axis_absent_on_dev']:,} | {', '.join(entry['ignored_below_min_share']) or '—'} |"
        )
    kinds = ["exact", "partial (a subset of the value's words)", "nothing written", "wrong",
             "written for an absent axis", "absent axis, nothing written"]
    lines += ["", f"## How exactly it decodes, per axis ({ex['n']:,} dev leaves with a suffix)", "",
              "| axis | " + " | ".join(kinds) + " |", "|---|" + "---:|" * len(kinds)]
    for axis in AXES:
        lines.append(f"| {axis} | " + " | ".join(f"{ex['per_axis'][axis][k]:,}" for k in kinds) + " |")
    partial = sum(ex["per_axis"][a]["partial (a subset of the value's words)"] for a in AXES)
    absent_written = sum(ex["per_axis"][a]["written for an absent axis"] for a in AXES)
    wrong = sum(ex["per_axis"][a]["wrong"] for a in AXES)
    lines += [
        "",
        f"**{ex['exact_all']:,} of {ex['n']:,} leaves decode exactly on every axis they have** "
        f"({ex['exact_all'] / ex['n']:.1%}). The rest are partial, not wrong: {partial:,} axis values "
        "receive a strict subset of their words — the codes that stand for more than one value, above "
        f"all TRABAJO `-` — and {wrong:,} receive words the value does not contain. On {absent_written:,} "
        "occurrences the decoder writes a value for an axis the leaf does not have, because `-` also "
        "marks an absent axis and a decoder that reads only the code cannot tell the two apart. Fixing "
        "that would need the leaf's parameters, which is the oracle information D-010 keeps out of a "
        "deployable query.",
    ]
    write(OUT / "decoder.md", lines + sources([], "", (DATA / CONDITIONS[0][2], SPLITS_FILE)))


# --------------------------------------------------------------------------- T2 — renderings


def arm_stats(frame: pd.DataFrame, short: str) -> dict:
    """Per-condition Acc@1 with both intervals, and the three contrasts, at both levels."""
    clusters = frame["gold_parent_key"].to_numpy()
    out = {"n": len(frame), "concepts": frame["gold_parent_key"].nunique(), "acc": {}, "contrast": {}}
    for level in LEVELS:
        cols = [f"{level}_{label}" for label, _, _ in CONDITIONS]
        values = frame[cols].to_numpy(float)
        q = boot_query(values, f"s91|acc|{short}|{level}")
        c = boot_cluster(values, clusters, f"s91|acc|{short}|{level}")
        for i, (label, _, _) in enumerate(CONDITIONS):
            out["acc"][(level, label)] = {"acc": float(values[:, i].mean()), "q": ci(q[:, i]), "c": ci(c[:, i])}
        for name, a, b in CONTRASTS:
            d = (frame[f"{level}_{a}"] - frame[f"{level}_{b}"]).to_numpy(float)
            dq = boot_query(d[:, None], f"s91|{name}|{short}|{level}")[:, 0]
            dc = boot_cluster(d[:, None], clusters, f"s91|{name}|{short}|{level}")[:, 0]
            out["contrast"][(name, level)] = {
                "delta": float(d.mean()), "q": ci(dq), "c": ci(dc), "p": boot_p(dc),
                "up": int((d > 0).sum()), "down": int((d < 0).sum()),
            }
    return out


def adjust(stats: dict[str, dict]) -> None:
    """Holm and BH across the ten arms, within each (contrast, level) family."""
    for name, _, _ in CONTRASTS:
        for level in LEVELS:
            arms = list(stats)
            p = [stats[s]["contrast"][(name, level)]["p"] for s in arms]
            for s, h, q in zip(arms, holm(p), bh(p)):
                stats[s]["contrast"][(name, level)].update(holm=h, bh=q)


def verdict(cell: dict) -> str:
    lo, hi = cell["c"]
    if lo > 0 and cell["holm"] < ALPHA:
        return "supported"
    if hi < 0 and cell["holm"] < ALPHA:
        return "contradicted"
    return "not supported"


def write_renderings(stats: dict[str, dict], ceilings: dict[str, float], pop: dict,
                     secondary: dict[str, dict], reference: dict) -> None:
    n_p = len(pop["P"])
    lines = header(
        "T2: coded, stripped and decoded `resumen`, per arm (dev)",
        [
            f"Population **P**: the {n_p:,} dev queries whose `resumen` carries a suffix and whose gold "
            f"`texto` is unique (D-033), out of {len(pop['dev']):,} dev queries, {len(pop['suffixed']):,} of "
            "them with a suffix. Every contrast is paired by query, on the same index and arm. Arms are "
            "printed side by side as reference; no arm-vs-arm contrast is claimed.",
        ],
    )
    lines += [
        "`ceiling` is the text-only item ceiling of each rendering on P: one findable member per group "
        "of identical query text (D-032). It moves with the condition, in one direction only: the decoded "
        "text is a function of the coded text, so decoding can merge groups but never split them, and "
        "stripping merges every group whose members differ only in the suffix. An oracle arm's query carries the gold's parameter "
        "tokens (D-010), which separate every sibling, so its ceiling is 1.0 in every condition.",
        "",
        "## Acc@1 per condition",
        "",
        "| method | | level | coded | CI (concept) | stripped | CI (concept) | decoded | CI (concept) | n | concepts |",
        "|---|---|---|---:|---|---:|---|---:|---|---:|---:|",
    ]
    for _, short, oracle in TEN:
        s = stats[short]
        for level in LEVELS:
            cells = " | ".join(
                f"{f4(s['acc'][(level, label)]['acc'])} | {fci(s['acc'][(level, label)]['c'])}"
                for label, _, _ in CONDITIONS
            )
            lines.append(f"| `{short}` | {'**oracle**' if oracle else ''} | {level} | {cells} | "
                         f"{s['n']:,} | {s['concepts']} |")
    lines += ["", "| ceiling on P (text-only arms) | " + " | ".join(
        f"{label} {f4(ceilings[label])}" for label, _, _ in CONDITIONS) + " |", "|---|---|"]

    for name, _, _ in CONTRASTS:
        lines += ["", f"## {name}", "",
                  "| method | | level | Δ | CI (query) | CI (concept) | p | p Holm | p BH | queries up / down |",
                  "|---|---|---|---:|---|---|---:|---:|---:|---|"]
        for _, short, oracle in TEN:
            for level in LEVELS:
                c = stats[short]["contrast"][(name, level)]
                lines.append(
                    f"| `{short}` | {'**oracle**' if oracle else ''} | {level} | {fd(c['delta'])} | "
                    f"{fci(c['q'], signed=True)} | {fci(c['c'], signed=True)} | {fp(c['p'])} | "
                    f"{fp(c['holm'])} | {fp(c['bh'])} | +{c['up']:,} / −{c['down']:,} |"
                )

    lines += ["", "## The registered predictions", "",
              "Read on the concept-clustered interval, after Holm across the ten arms (design, D-030): "
              "**supported** when the interval excludes 0 on the predicted side, **contradicted** when it "
              "excludes 0 on the other, **not supported** otherwise.", "",
              "| prediction | contrast | level | method | Δ | CI (concept) | p Holm | reading |",
              "|---|---|---|---|---:|---|---:|---|"]
    for pid, name, level, arms in PREDICTIONS:
        for short in arms:
            c = stats[short]["contrast"][(name, level)]
            lines.append(f"| {pid} | {name} | {level} | `{short}` | {fd(c['delta'])} | "
                         f"{fci(c['c'], signed=True)} | {fp(c['holm'])} | **{verdict(c)}** |")

    lines += ["", "## Secondary: every scored dev query", "",
              "Item level on all dev queries with a unique gold `texto` (D-033), parent level on all dev "
              "queries. Leaves without a suffix contribute zero to every delta, so these dilute the P "
              "figures above rather than add to them.", "",
              "| method | level | n | coded | stripped | decoded |", "|---|---|---:|---:|---:|---:|"]
    for _, short, _ in TEN:
        for level in LEVELS:
            s = secondary[short][level]
            lines.append(f"| `{short}` | {level} | {s['n']:,} | " + " | ".join(
                f4(s[label]) for label, _, _ in CONDITIONS) + " |")

    ref = reference["bm25_unigram_params"]
    lines += [
        "",
        "## Reference, not a contrast (D-039)",
        "",
        f"On every scored dev query, decoded `bm25_unigram_params` reaches **{f4(ref['decoded'])}** "
        f"(n = {ref['n']:,} scored), beside the previous study's {PREVIOUS['bm25_unigram_params']} on OEB "
        "test. Decoding reproduces the *kind* of edit the previous study made, not its text, and the two "
        "still differ in chapter, corpus size and split. No delta is computed.",
    ]
    keys = [(queryset, method) for method, _, _ in TEN for _, queryset, _ in CONDITIONS]
    note = (
        "**Reuse of the coded runs.** The ten `resumen` runs are S3's E0(b) runs. For each, "
        "`git diff <run commit> HEAD` over its retriever and what it imports, `retrieve.ipynb`, "
        "`metrics.ipynb`, `run_context`, `provenance`, `corpus_prep` and `splits` shows one change: the "
        "`QUERY_SETS` entries that register the two renderings, which cannot alter how `resumen` resolves. "
        "`bge_m3_colbert` and `bge_m3_dense` read `OE_short_norm` for coded `resumen` and a `_feats` table "
        "for each rendering; `tests/test_resumen_renderings.py` proves a `_norm` table is its `_feats` "
        "table minus columns."
    )
    write(OUT / "renderings.md", lines + sources(keys, note, tuple(DATA / name for _, _, name in CONDITIONS)))


# --------------------------------------------------------------------------- T3 — coverage


def write_coverage(texts: dict[str, dict[str, str]], gold: dict[str, str], pop: dict) -> None:
    lines = header(
        "T3: how much of each rendering its gold `texto` contains (dev)",
        [
            "The S3 overlap statistics (`build_overlap.py`): lexical coverage is the share of the query's "
            "distinct normalised tokens found in its gold `texto`; numeric coverage the share of its "
            "numbers. Concept-clustered intervals.",
        ],
    )
    lines += ["| population | condition | n | lexical mean | CI (concept) | numeric mean | numbers per query |",
              "|---|---|---:|---:|---|---:|---:|"]
    for pop_label, keys in (("P", sorted(pop["P"])), ("all dev", pop["dev"])):
        clusters = np.array([pop["parent_of"][k] for k in keys])
        for label, _, _ in CONDITIONS:
            lex = np.array([lexical_coverage(texts[label][k], gold[k]) or 0.0 for k in keys], dtype=float)
            num = [numeric_coverage(texts[label][k], gold[k]) for k in keys]
            num = [x for x in num if x is not None]
            count = np.mean([len(re.findall(r"\d+(?:[.,]\d+)?", normalize_text(texts[label][k]))) for k in keys])
            lo, hi = ci(boot_cluster(lex[:, None], clusters, f"s91|cov|{pop_label}|{label}")[:, 0])
            lines.append(
                f"| {pop_label} | {label} | {len(keys):,} | {lex.mean():.2%} | [{lo:.2%}, {hi:.2%}] | "
                f"{(np.mean(num) if num else float('nan')):.2%} | {count:.2f} |"
            )
    lines += ["", "Coverage describes the queries, not any method's accuracy. It is the covariate the "
              "renderings move; whether it mediates the accuracy change is S6's question, not this probe's."]
    note = ("The population (dev leaves, P) is read from the run above; the queries' text from the "
            "three rendering files and the gold `texto` from the corpus table below. No accuracy is read.")
    write(OUT / "coverage.md", lines + sources(
        [POPULATION_RUN], note, (*(DATA / name for _, _, name in CONDITIONS), LONG_FEATS)))


# --------------------------------------------------------------------------- T4 — subchapter


def write_subchapter(frames: dict[str, pd.DataFrame]) -> None:
    lines = header(
        "T4: OEB against the rest of OE, on P (dev)",
        [
            "Descriptive. OEB is most of dev, so pooled figures lean on it; this splits them. No stratum "
            "is contrasted with another: they differ in concepts, families and parameters.",
        ],
    )
    lines += ["| method | stratum | n | concepts | level | coded | stripped | decoded |",
              "|---|---|---:|---:|---|---:|---:|---:|"]
    for _, short, _ in TEN:
        f = frames[short]
        for stratum, mask in (("OEB", f["gold_parent_key"].str.startswith("OEB")),
                              ("rest", ~f["gold_parent_key"].str.startswith("OEB"))):
            g = f[mask]
            for level in LEVELS:
                lines.append(f"| `{short}` | {stratum} | {len(g):,} | {g['gold_parent_key'].nunique()} | {level} | "
                             + " | ".join(f4(g[f'{level}_{label}'].mean()) for label, _, _ in CONDITIONS) + " |")

    # Per concept, for the BM25 arms: where a pooled contrast actually lives. A concept-clustered
    # interval is only as wide as the concepts that move, and this shows which ones do.
    n_p = len(frames[TEN[0][1]])
    lines += ["", "## Per concept, parent level, the two BM25 arms", "",
              "| method | concept | n | share of P | coded | stripped | decoded | stripped − coded | decoded − coded |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for short in ("bm25_unigram_params", "bm25_unigram"):
        f = frames[short]
        g = f.groupby("gold_parent_key").agg(
            n=("query_item_key", "size"),
            **{label: (f"parent_{label}", "mean") for label, _, _ in CONDITIONS},
        )
        g["sc"] = g["stripped"] - g["coded"]
        g = g.sort_values(["sc", "n"], ascending=[False, False])
        for concept, r in g.iterrows():
            lines.append(f"| `{short}` | `{concept}` | {int(r['n']):,} | {r['n'] / n_p:.1%} | {f4(r['coded'])} | "
                         f"{f4(r['stripped'])} | {f4(r['decoded'])} | {fd(r['sc'])} | {fd(r['decoded'] - r['coded'])} |")
        moved = g[g["sc"] > 0]
        lines += ["", f"`{short}`: {len(moved)} of {len(g)} concepts gain from stripping, holding "
                  f"{int(moved['n'].sum()):,} of {n_p:,} queries ({moved['n'].sum() / n_p:.1%}) of P.", ""]
    keys = [(queryset, method) for method, _, _ in TEN for _, queryset, _ in CONDITIONS]
    write(OUT / "subchapter.md", lines + sources(keys, "", (DATA / CONDITIONS[0][2],)))


# --------------------------------------------------------------------------- T5 — rare codes


_QKEY = re.compile(r'"query_item_key":\s*"([^"]+)"')


def rank1(queryset: str, method: str, keys: set[str]) -> dict[str, str]:
    out = {}
    with gzip.open(RUNS / queryset / method / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            hit = _QKEY.search(line)
            if hit and hit.group(1) in keys:
                rec = json.loads(line)
                out[rec["query_item_key"]] = rec["candidates"][0]["index_item_key"]
    return out


def write_rare_codes(coded: dict[str, dict], corpus_tokens: dict[str, set[str]], df: collections.Counter,
                     n_docs: int, frames: dict[str, pd.DataFrame]) -> None:
    lines = header(
        "T5: the rare-code diagnostic (coded `resumen`, lexical arms, P)",
        [
            "Descriptive, and the mechanism D-039 recorded as untested. A suffix code is a query token; "
            "several are near-absent from the corpus, so IDF weights them heavily. For each miss, does the "
            "rank-1 document contain a code token of the query that the gold does not? P2 is the test; "
            "this only shows how often the pattern is there to be tested.",
        ],
    )
    code_tokens = collections.Counter()
    for k in frames[LEXICAL[0]]["query_item_key"]:
        for code in split_suffix(coded[k]["text"])[2]:
            code_tokens.update(set(tokenize_words(normalize_text(code))))
    lines += ["| code token | queries on P carrying it | corpus documents containing it |", "|---|---:|---:|"]
    for tok, n in code_tokens.most_common():
        lines.append(f"| `{tok}` | {n:,} | {df.get(tok, 0):,} of {n_docs:,} |")
    lines += ["", "| method | level | misses | rank-1 holds a query code token the gold lacks | share |",
              "|---|---|---:|---:|---:|"]
    for short in LEXICAL:
        f = frames[short]
        method = next(m for m, s, _ in TEN if s == short)
        for level in LEVELS:
            misses = set(f.loc[f[f"{level}_coded"] == 0, "query_item_key"])
            top = rank1("resumen", method, misses)
            hit = 0
            for k in misses:
                codes = set().union(*(set(tokenize_words(normalize_text(c))) for c in split_suffix(coded[k]["text"])[2]))
                gold_t = corpus_tokens[coded[k]["item_key"]]
                hit += bool((codes - gold_t) & corpus_tokens.get(top.get(k, ""), set()))
            lines.append(f"| `{short}` | {level} | {len(misses):,} | {hit:,} | "
                         f"{(hit / len(misses) if misses else float('nan')):.1%} |")
    keys = [("resumen", next(m for m, s, _ in TEN if s == short)) for short in LEXICAL]
    write(OUT / "rare_codes.md", lines + sources(keys, "", (DATA / CONDITIONS[0][2], LONG_FEATS)))


# --------------------------------------------------------------------------- main


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    coded = records("OE_resumen.json")
    texts = {label: {k: r["text"] for k, r in records(name).items()} for label, _, name in CONDITIONS}
    table = json.loads(DECODER.read_text(encoding="utf-8"))
    dev = set(load_split("dev"))
    dup = flagged()
    pop = population(coded, dup)

    long = pd.read_parquet(LONG_FEATS, columns=["item_key", "text", "text_word"])
    gold = dict(zip(long["item_key"], long["text"]))
    corpus_tokens = {k: set(t.split()) for k, t in zip(long["item_key"], long["text_word"])}
    df = collections.Counter()
    for toks in corpus_tokens.values():
        df.update(toks)

    ceilings = {label: text_ceiling(texts[label], pop["P"]) for label, _, _ in CONDITIONS}

    frames, stats, secondary = {}, {}, {}
    scored_all = {k for k in pop["dev"] if k not in dup}
    for method, short, _ in TEN:
        frames[short] = joined(method, pop["P"])
        stats[short] = arm_stats(frames[short], short)
        every = joined(method, set(pop["dev"]))
        secondary[short] = {
            "item": {"n": len(scored_all), **{label: float(every.loc[every["query_item_key"].isin(scored_all),
                                                                     f"item_{label}"].mean())
                                              for label, _, _ in CONDITIONS}},
            "parent": {"n": len(every), **{label: float(every[f"parent_{label}"].mean())
                                           for label, _, _ in CONDITIONS}},
        }
    adjust(stats)
    reference = {"bm25_unigram_params": {"decoded": secondary["bm25_unigram_params"]["item"]["decoded"],
                                         "n": secondary["bm25_unigram_params"]["item"]["n"]}}

    write_decoder(coded, table, dev)
    write_renderings(stats, ceilings, pop, secondary, reference)
    write_coverage(texts, gold, pop)
    write_subchapter(frames)
    write_rare_codes(coded, corpus_tokens, df, len(corpus_tokens), frames)
    print(f"written: {OUT.relative_to(REPO)}")
    for path in sorted(OUT.glob("*.md")):
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
