"""Build docs/synthetic-oe/results/S3/e0/ — S3 work item 10.

Three tables and their stamps: the per-method identity **ceiling** (E0a), the `resumen`
**replication** (E0b), and the `k1`/`b` **transferability** verdict (the sweep).

Item-level figures are computed on the duplicate-free population (D-033) and every one is printed
with its scored n, because after the re-score each item-level Acc@1 has two values and quoting one
without its n is how the README's table went wrong. Helpers — bootstrap, clustering, formatting,
provenance — are imported from `build_results_s2`, so no table in this sprint can drift from
another in its definitions.

**Every number in the prose is interpolated from a computed value.** The S3 audit (F1) found p-values
typed into this file that no committed code produced, beside a table that printed different ones.
`tests/test_generated_prose.py` now fails on a numeric literal in any string this file emits.

    python src/utils/build_results_e0.py
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_overlap import replication_coverage  # noqa: E402
from utils.build_results_s2 import (  # noqa: E402
    B,
    SEED,
    boot_cluster,
    boot_p,
    boot_query,
    ci,
    f4,
    fci,
    fd,
    fp,
    write,
)
from utils.corpus_prep import normalize_text, tokenize_words  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.splits import load_split  # noqa: E402

RUNS = REPO / "runs" / "OE"
INDEX = REPO / "index" / "OE"
DATA = REPO / "data" / "processed"
SIDECAR = DATA / "OE_duplicate_texto_groups.json"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S3" / "e0"
GENERATOR = "src/utils/build_results_e0.py"

#: D-012's ten arms, in the order the tables read best: lexical first, then neural.
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
#: True where the arm consumes the record's parsed `parameters`, which a real query does not carry
#: (D-010). Such an arm is an upper bound, never quoted alone.
ORACLE = {short for _, short, oracle in TEN if oracle}
METHOD_OF = {short: method for method, short, _ in TEN}

#: The previous study's figures, from `docs/reviews/paper_28.tex` — the authoritative source; the
#: README's table disagrees with it and must never be cited. `(item, parent, note)`.
PREVIOUS = {
    "bm25_unigram_params": (0.974, 0.985, "its own tuned point, `k1`=0.60/`b`=0.35"),
    "bm25_unigram": (0.869, None, "reported at `k1`=0.80/`b`=0.35; parent given only as a 0.873–0.985 range"),
    "tfidf_phrases_replace": (0.708, 0.990, "the previous study's best TF-IDF, and its best parent-level arm"),
    "bge_m3_colbert": (0.448, 0.997, "its best neural arm"),
    "bge_m3_dense": (0.127, 0.960, ""),
    "bge_m3_sparse": (0.125, 0.994, ""),
    "dense_e5": (0.134, 0.982, "reported as \"E5-large\"; the config says `multilingual-e5-base`"),
    "dense_es_hiiamsid": (0.0244, 0.3952, "**never published** — from `runs/`, the reporting defect the root `CLAUDE.md` tracks"),
    "dense_gte": (0.013, 0.837, "table labels it `GTE-large-en-v1.5`, the config says `gte-multilingual-base` (D-035)"),
    "dense_gte_instrQ": (0.014, 0.697, "table labels it `GTE-Qwen2-instruct` (D-035)"),
}

#: The sweep, per D-036.
K1_VALUES = (0.60, 0.80, 1.00, 1.20, 1.40)
B_VALUES = (0.20, 0.35, 0.50, 0.65, 0.80)
SWEEP_VARIANTS = ("bm25_unigram", "bm25_unigram_params")
SWEEP_SETS = ("texto", "single_texto", "stacked_texto")
TRANSFERRED = (0.60, 0.35)
#: The previous study's own operating point for `bm25_unigram`, run on `resumen` for a like-for-like row.
PREVIOUS_BM25_POINT = (0.80, 0.35)

WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

#: A text-only arm "sits at its corpus ceiling" when its scored identity Acc@1 reaches this.
AT_CEILING = 0.999


def point(variant: str, k1: float, b: float) -> str:
    return f"{variant}__k1-{k1:.2f}__b-{b:.2f}__OE"


def pt(k1_b: tuple[float, float]) -> str:
    return f"{k1_b[0]:.2f}/{k1_b[1]:.2f}"


def fpc(x: float) -> str:
    return f"{x:.2f} %"


def sidecar() -> dict:
    return json.loads(SIDECAR.read_text(encoding="utf-8"))


def flagged() -> set[str]:
    return {m for g in sidecar()["groups"].values() for m in g}


def perquery(queryset: str, method: str) -> pd.DataFrame:
    return pd.read_parquet(RUNS / queryset / method / "results_perquery.parquet")


def meta(queryset: str, method: str) -> dict:
    return json.loads((RUNS / queryset / method / "run_meta.json").read_text(encoding="utf-8"))


def scored(frame: pd.DataFrame, dup: set[str], target: str) -> pd.DataFrame:
    return frame if target == "parent" else frame[~frame["gold_item_key"].isin(dup)]


def stats(frame: pd.DataFrame, target: str, label: str) -> dict:
    col = f"{target}_acc1"
    values = frame[[col]].to_numpy()
    q = boot_query(values, label)
    c = boot_cluster(values, frame["gold_parent_key"].to_numpy(), label)
    return {
        "n": len(frame),
        "acc": float(frame[col].mean()),
        "q": ci(q[:, 0]),
        "c": ci(c[:, 0]),
    }


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S3 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def sources(keys: list[tuple[str, str]], note: str = "") -> list[str]:
    lines = ["", "## Sources", "", "| run_id | queries | config SHA-256 | code commit | query-set SHA-256 |", "|---|---:|---|---|---|"]
    for queryset, method in keys:
        m = meta(queryset, method)
        lines.append(
            f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
            f"`{m['code_commit'][:7]}` | `{m['query_set_sha256'][:16]}` |"
        )
    if note:
        lines += ["", note]
    lines += [
        "",
        "| exclusion input | SHA-256 |",
        "|---|---|",
        f"| `OE_duplicate_texto_groups.json` | `{sha256_file(SIDECAR)[:16]}` |",
        "",
        f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals. Split `dev`.",
    ]
    return lines


def english_list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# --------------------------------------------------------------------------- ranked lists

_QKEY = re.compile(r'"query_item_key":\s*"([^"]+)"')


def top_lists(queryset: str, method: str, keys: set[str]) -> dict[str, dict]:
    """The ranked candidates of the queries in `keys`, streamed from the run's own top-100 file."""
    out = {}
    with gzip.open(RUNS / queryset / method / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            hit = _QKEY.search(line)
            if hit and hit.group(1) in keys:
                rec = json.loads(line)
                out[rec["query_item_key"]] = rec
    return out


def gold_position(rec: dict) -> tuple[int | None, float | None, float]:
    """(gold's rank or None past 100, gold's score, the rank-1 score)."""
    cands = rec["candidates"]
    top = cands[0]["score"]
    for c in cands:
        if c["index_item_key"] == rec["gold_item_key"]:
            return c["rank"], c["score"], top
    return None, None, top


# --------------------------------------------------------------------------- measurements


def ceiling_rows(dup: set[str]) -> dict[str, dict]:
    """Everything the ceiling table and its prose print, per arm, computed once."""
    groups = list(sidecar()["groups"].values())
    group_of = {m: set(g) for g in groups for m in g}
    rows = {}
    for method, short, oracle in TEN:
        frame = perquery("texto", method)
        kept = scored(frame, dup, "item")
        dups = frame[frame["gold_item_key"].isin(dup)]
        ranked = top_lists("texto", method, set(dups["gold_item_key"]))
        tied = outside = 0
        for rec in ranked.values():
            _, gold_score, top = gold_position(rec)
            tied += gold_score is not None and gold_score == top
            outside += rec["candidates"][0]["index_item_key"] not in group_of[rec["gold_item_key"]]
        hit = dict(zip(dups["gold_item_key"], dups["item_acc1"]))
        per_group = [sum(hit[m] for m in g) for g in groups]
        rows[short] = {
            "oracle": oracle,
            "n_all": len(frame),
            "all": float(frame["item_acc1"].mean()),
            "item": stats(kept, "item", f"ceil|{short}"),
            "parent": stats(frame, "parent", f"ceilp|{short}"),
            "undecidable": len(dups),
            "resolved": int(dups["item_acc1"].sum()),
            "tied_at_top": tied,
            "rank1_outside": outside,
            "groups_multi": sum(h > 1 for h in per_group),
            "groups_zero": sum(h == 0 for h in per_group),
        }
    return rows


def sparse_diagnosis(dup: set[str]) -> dict:
    """Why `bge_m3_sparse` misses its own document: gold ranks, ties, and the vector norms."""
    method = METHOD_OF["bge_m3_sparse"]
    frame = scored(perquery("texto", method), dup, "item")
    misses = set(frame.loc[frame["item_acc1"] == 0, "gold_item_key"])
    ranks, ties, beyond = [], 0, 0
    for rec in top_lists("texto", method, misses).values():
        rank, gold_score, top = gold_position(rec)
        if rank is None:
            beyond += 1
            continue
        ranks.append(rank)
        ties += gold_score == top
    docs = sp.load_npz(INDEX / method / "data" / "sparse_docs.npz")
    norms = np.sqrt(np.asarray(docs.multiply(docs).sum(axis=1)).ravel())
    return {
        "misses": len(misses),
        "rank_lo": min(ranks),
        "rank_hi": max(ranks),
        "rank_median": float(np.median(ranks)),
        "ties": ties,
        "beyond": beyond,
        "norm_lo": float(norms.min()),
        "norm_hi": float(norms.max()),
    }


def mean_tokens(texts: list[str]) -> float:
    return float(np.mean([len(tokenize_words(normalize_text(t))) for t in texts]))


def query_lengths() -> dict[str, float]:
    """Mean normalised query length: OEB `resumen` (where 0.60/0.35 was fitted) against the OE sets."""
    dev = load_split("dev")
    out = {"OEB resumen": mean_tokens([r["text"] for r in json.loads((DATA / "OEB_resumen.json").read_text(encoding="utf-8"))])}
    for name in SWEEP_SETS:
        rows = json.loads((DATA / f"OE_{name}.json").read_text(encoding="utf-8"))
        out[name] = mean_tokens([r["text"] for r in rows if r["parent_key"] in dev])
    return out


def sweep_acc(variant: str, k1: float, b: float, queryset: str, dup: set[str]) -> float | None:
    path = RUNS / queryset / point(variant, k1, b)
    if not (path / "results_perquery.parquet").is_file():
        return None
    frame = pd.read_parquet(path / "results_perquery.parquet")
    return float(frame[~frame["gold_item_key"].isin(dup)]["item_acc1"].mean())


def sweep(dup: set[str]) -> list[dict]:
    """One record per (variant, query set): the surface, its argmax, and the paired contrast."""
    cells = []
    for variant in SWEEP_VARIANTS:
        for queryset in SWEEP_SETS:
            surface = {(k1, b): sweep_acc(variant, k1, b, queryset, dup) for k1 in K1_VALUES for b in B_VALUES}
            surface = {k: v for k, v in surface.items() if v is not None}
            best = max(surface, key=surface.get)
            cell = {"variant": variant, "queryset": queryset, "surface": surface, "best": best,
                    "ref": surface[TRANSFERRED], "delta": surface[best] - surface[TRANSFERRED]}
            if best != TRANSFERRED:
                a = perquery(queryset, point(variant, *best))
                r = perquery(queryset, point(variant, *TRANSFERRED))
                m = a[["query_item_key", "gold_item_key", "gold_parent_key", "item_acc1"]].merge(
                    r[["query_item_key", "item_acc1"]], on="query_item_key",
                    suffixes=("_a", "_r"), validate="one_to_one")
                m = m[~m["gold_item_key"].isin(dup)]
                d = (m["item_acc1_a"] - m["item_acc1_r"]).to_numpy(float)
                draws = boot_query(np.column_stack([d]), f"sweep|{variant}|{queryset}")
                cell.update(ci=ci(draws[:, 0]), p=boot_p(draws[:, 0]),
                            up=int((d > 0).sum()), down=int((d < 0).sum()),
                            digests=(meta(queryset, point(variant, *best))["query_set_sha256"],
                                     meta(queryset, point(variant, *TRANSFERRED))["query_set_sha256"]))
            cells.append(cell)
    return cells


def shape_in_b(cells: list[dict]) -> tuple[int, int, list[tuple[float, int]], int]:
    """Over (variant, set, k1) rows: how many fall at every step up in `b`, how many are
    single-peaked, where the peaks sit, and how many rows there are."""
    mono = peaked = total = 0
    peaks: dict[float, int] = {}
    for cell in cells:
        for k1 in K1_VALUES:
            row = [cell["surface"].get((k1, b)) for b in B_VALUES]
            if None in row:
                continue
            total += 1
            mono += all(x >= y for x, y in zip(row, row[1:]))
            top = int(np.argmax(row))
            peaks[B_VALUES[top]] = peaks.get(B_VALUES[top], 0) + 1
            rising = all(x <= y for x, y in zip(row[:top], row[1:top + 1]))
            falling = all(x >= y for x, y in zip(row[top:], row[top + 1:]))
            peaked += rising and falling
    return mono, peaked, sorted(peaks.items()), total


# --------------------------------------------------------------------------- E0(a) ceilings


def write_ceiling(dup: set[str], rows: dict[str, dict], sparse: dict, resumen_hiiamsid: dict) -> None:
    lines = header(
        "E0(a): the identity ceiling, per method (`texto`, dev)",
        [
            "Each arm asked to retrieve a document when handed that document's own text. Under",
            "D-032 this is **the arm's own ceiling**, not a gate: no method is disqualified for",
            "failing to reach 1.0, but a claim that ignores its method's ceiling is.",
        ],
    )
    side = sidecar()
    n_groups, n_leaves = side["n_groups"], side["n_leaves"]
    unavoidable = n_leaves - n_groups
    n_all = rows[TEN[0][1]]["n_all"]
    n_scored = n_all - n_leaves
    corpus_ceiling = 1 - unavoidable / n_all
    lines += [
        f"**The corpus permits at most {corpus_ceiling:.4f} for a `texto`-only method.** {n_leaves:,} leaves in "
        f"{n_groups:,} groups share a `texto` with a sibling, so one member of each group can be found and the "
        f"rest cannot: {unavoidable:,} unavoidable misses out of {n_all:,}. Item-level scoring excludes "
        "those queries (D-033), which is why the scored column below has a ceiling of exactly **1.0** "
        "and headroom is the observed value itself.",
        "",
        "Both levels carry a query-level and a concept-clustered interval. The parent level is scored on "
        "every query: a duplicate's gold concept is decidable even where its leaf is not.",
        "",
        "| method | | item, all queries | corpus ceiling | headroom | item, scored | n scored | CI (query) | CI (concept) | parent | CI (query) | CI (concept) |",
        "|---|---|---:|---:|---:|---:|---:|---|---|---:|---|---|",
    ]
    for _, short, oracle in TEN:
        r = rows[short]
        s, p = r["item"], r["parent"]
        lines.append(
            f"| `{short}` | {'**oracle**' if oracle else ''} | {f4(r['all'])} | {corpus_ceiling:.4f} | "
            f"{r['all'] / corpus_ceiling:.4f} | **{f4(s['acc'])}** | "
            f"{s['n']:,} | {fci(s['q'])} | {fci(s['c'])} | {f4(p['acc'])} | {fci(p['q'])} | {fci(p['c'])} |"
        )

    text_only = [short for _, short, oracle in TEN if not oracle]
    oracles = [short for _, short, oracle in TEN if oracle]
    at_ceiling = [s for s in text_only if rows[s]["item"]["acc"] >= AT_CEILING]
    above = [s for s in text_only if rows[s]["resolved"] > n_groups]
    below = sorted((s for s in text_only if rows[s]["resolved"] < n_groups), key=lambda s: -rows[s]["resolved"])
    over_text = [s for s in text_only if rows[s]["all"] > corpus_ceiling]
    best_oracle = max(oracles, key=lambda s: rows[s]["resolved"])
    other_oracle = [s for s in oracles if s != best_oracle]

    lines += [
        "",
        f"## The oracle arms' advantage is the {n_leaves:,} undecidable queries",
        "",
        "Splitting each arm's identity performance at the duplicate groups makes the structure plain. "
        "Within a group every member has the same text, so a `texto`-only arm scores them **identically** "
        "and which member it ranks first is decided by how its sort breaks an exact tie. With one hit per "
        f"group in expectation, the chance baseline is **{n_groups:,}** hits. An arm that also indexes the "
        "record's parsed `parameters` is not bound by that, because the parameters differ even where the "
        "`texto` does not.",
        "",
        f"| method | | on the {n_scored:,} decidable | on the {n_leaves:,} undecidable | vs chance ({n_groups:,}) | gold scores level with rank 1 | rank 1 outside the group | groups hit twice | groups missed |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, short, oracle in TEN:
        r = rows[short]
        lines.append(
            f"| `{short}` | {'**oracle**' if oracle else ''} | {f4(r['item']['acc'])} | "
            f"{r['resolved']:,} of {r['undecidable']:,} | {r['resolved'] - n_groups:+,d} | {r['tied_at_top']:,} | "
            f"{r['rank1_outside']:,} | {r['groups_multi']:,} | {r['groups_zero']:,} |"
        )

    lines += [
        "",
        f"**`{best_oracle}` resolves {rows[best_oracle]['resolved']:,} of {n_leaves:,}.** "
        + "".join(f"`{s}` resolves {rows[s]['resolved']:,}. " for s in other_oracle)
        + f"The text-only arms that sit at their corpus ceiling ({english_list([f'`{s}`' for s in at_ceiling])}) "
        f"land on {english_list([str(rows[s]['resolved']) for s in at_ceiling])} against an expectation of "
        f"{n_groups:,}.",
    ]
    if above:
        lines += [
            "",
            english_list([f"`{s}` exceeds {n_groups:,} by {rows[s]['resolved'] - n_groups:,}" for s in above])
            + ", and that is not resolution. "
            + english_list([f"`{s}` hits {rows[s]['groups_multi']:,} groups twice and misses "
                            f"{rows[s]['groups_zero']:,} entirely" for s in above])
            + ", with the gold's score **exactly** equal to rank 1's on "
            + english_list([f"{rows[s]['tied_at_top']:,}" for s in above])
            + " of the undecidable queries respectively, so which member wins is the tie-break. The "
            "retrievers take the top k with `np.argpartition`, which does not break ties stably, so queries "
            "with the same text can resolve the same tie differently, and the surplus is a coin that "
            "happened to land favourably. No text-only arm resolves the undecidable queries: the oracle "
            "arms are not *better* at identity, they are answering a different question, one in which the "
            "answer is determined.",
        ]
    lines += [
        "",
        "The arms *below* chance are below it for a different reason, and the column should not be "
        "read as tie-breaking skill: "
        + english_list([f"`{s}` at {rows[s]['resolved']:,} ({rows[s]['rank1_outside']:,} ranking a "
                        "non-member first)" for s in below])
        + " often put a document outside the group at rank 1, so they lose these queries the way they "
        "lose their others rather than by picking the wrong sibling.",
        "",
        "**Headroom** is observed ÷ corpus ceiling, as D-032 requires. It exceeds 1.0 by a margin for the "
        "oracle arms — "
        + english_list([f"`{s}` {rows[s]['all'] / corpus_ceiling:.4f}" for s in oracles])
        + " — because the ceiling binds a `texto`-only method and does not bind an arm that also indexes "
        "the record's `parameters`."
        + (
            " A text-only arm can exceed it only by a tie-breaking surplus, and one does: "
            + english_list([f"`{s}` at {rows[s]['all'] / corpus_ceiling:.5f}, "
                            f"{round((rows[s]['all'] - corpus_ceiling) * n_all):,} query's worth" for s in over_text])
            + "."
            if over_text else ""
        )
        + " On the scored column the ceiling is exactly 1.0, so there headroom is the observed value itself.",
        "",
        f"D-010 was argued from the code in S2 and measured on query sets. This is a third confirmation: "
        f"**{rows[best_oracle]['resolved']:,} of {n_leaves:,} against a chance baseline of {n_groups:,}.** "
        "Neither oracle arm may be quoted without its text-only counterpart.",
    ]

    best_scored = max(rows, key=lambda s: rows[s]["item"]["acc"])
    if best_scored not in ORACLE:
        lines += [
            "",
            f"And on the decidable population the ranking is not what the full-population column suggests: "
            f"`{best_scored}` reads its own target back at **{f4(rows[best_scored]['item']['acc'])}**, above "
            f"both oracle arms."
            + (
                f" A Spanish sentence-similarity model that the previous submission never reported has the "
                f"cleanest identity behaviour in the set — which says nothing yet about retrieval under "
                f"variation, where it falls to {f4(resumen_hiiamsid['acc'])} on `resumen` "
                f"(n = {resumen_hiiamsid['n']:,} scored)"
                if best_scored == "dense_es_hiiamsid" else ""
            )
            + ", and everything about why a ceiling must be measured per method before any degradation "
            "is read against it (D-032).",
        ]

    sp_all = rows["bge_m3_sparse"]["all"]
    sp_scored = rows["bge_m3_sparse"]["item"]["acc"]
    bm = rows["bm25_unigram"]
    lines += [
        "",
        "## Two arms are far below their corpus ceiling, and for different reasons",
        "",
        f"`bge_m3_sparse` at {f4(sp_scored)} scored (n = {n_scored:,}; {f4(sp_all)} over all {n_all:,}) cannot "
        "retrieve a document from that document's own text. Of its "
        f"{sparse['misses']:,} misses on the decidable population, the gold sits at rank "
        f"{sparse['rank_lo']}–{sparse['rank_hi']} (median {sparse['rank_median']:.0f}), "
        f"{sparse['beyond']:,} fall past rank 100, and {sparse['ties']:,} are exact ties with rank 1. The "
        f"indexed vectors are **not** L2-normalised — norms {sparse['norm_lo']:.2f}–{sparse['norm_hi']:.2f}, a "
        f"{sparse['norm_hi'] / sparse['norm_lo']:.1f}× spread — and scored by a raw dot product, so a sibling "
        "with a heavier vector out-scores the document against its own. That is BGE-M3's intended lexical "
        "scoring, so it is a ceiling rather than a defect, but it leaves the arm no headroom to lose and "
        f"every later figure for it is read against {f4(sp_scored)}.",
        "",
        f"`bm25_unigram` at {f4(bm['item']['acc'])} scored ({f4(bm['all'])} over all) is below for a different "
        "reason, diagnosed in S2's `identity_misses.md`: token subsumption between maintenance bands, not "
        "duplication. The two GTE arms and `dense_e5` are below too. The likely reading — near-identical "
        "sibling texts embedding to near-identical vectors, the parametric collapse at the encoder — is "
        "not tested here.",
    ]
    write(OUT / "ceiling.md", lines + sources([("texto", m) for m, _, _ in TEN]))


# --------------------------------------------------------------------------- E0(b) replication


def write_replication(dup: set[str], cells: list[dict], coverage: tuple[dict, dict, int]) -> dict:
    oe_texto = json.loads((DATA / "OE_texto.json").read_text(encoding="utf-8"))
    oeb_texto = json.loads((DATA / "OEB_texto.json").read_text(encoding="utf-8"))
    n_sub = len({r["parent_key"][:3] for r in oe_texto})
    lines = header(
        "E0(b): the previous protocol re-run on OE (`resumen→texto`, dev)",
        [
            "The previous study's protocol — the leaf's own summary asked of the corpus — on a",
            f"corpus {len(oe_texto) / len(oeb_texto):.2f}× the size ({len(oe_texto):,} leaves against",
            f"{len(oeb_texto):,}) across {n_sub} subchapters instead of one.",
        ],
    )
    lines += [
        "> **The two columns are reference, not a paired contrast.** OEB test → OE dev changes the "
        "chapter, the corpus size, the query set and the split, so no delta between them is computed "
        "and none should be inferred. What may be compared is arm against arm *within* OE, paired by "
        "query. The previous figures are quoted from `docs/reviews/paper_28.tex`, which is "
        "authoritative; the README's results table disagrees with it and must never be cited.",
        "",
        "| method | | OE item | n scored | CI (query) | CI (concept) | OE parent | CI (query) | CI (concept) | previous item | previous parent | note |",
        "|---|---|---:|---:|---|---|---:|---|---|---:|---:|---|",
    ]
    item = {}
    for method, short, oracle in TEN:
        frame = perquery("resumen", method)
        s = stats(scored(frame, dup, "item"), "item", f"rep|{short}")
        p = stats(frame, "parent", f"repp|{short}")
        item[short] = s
        prev_i, prev_p, note = PREVIOUS[short]
        lines.append(
            f"| `{short}` | {'**oracle**' if oracle else ''} | **{f4(s['acc'])}** | {s['n']:,} | {fci(s['q'])} | "
            f"{fci(s['c'])} | {f4(p['acc'])} | {fci(p['q'])} | {fci(p['c'])} | {prev_i:.3f} | "
            f"{f'{prev_p:.3f}' if prev_p is not None else '—'} | {note} |"
        )

    # like-for-like row for the one arm the previous study tuned elsewhere
    alt = point("bm25_unigram", *PREVIOUS_BM25_POINT)
    if (RUNS / "resumen" / alt).is_dir():
        s = stats(scored(perquery("resumen", alt), dup, "item"), "item", "rep|bm25_unigram_080")
        item["bm25_unigram@previous"] = s
        lines += [
            "",
            f"`bm25_unigram` is the one arm the previous study reported at a different operating point "
            f"(`k1`/`b` = {pt(PREVIOUS_BM25_POINT)}). Run at **that** point on OE it reaches **{f4(s['acc'])}** "
            f"{fci(s['q'])} (n = {s['n']:,} scored) against {f4(item['bm25_unigram']['acc'])} at "
            f"{pt(TRANSFERRED)} — so the row is not an artefact of the point we carry.",
        ]

    oeb, oe_resumen, oeb_in_test = coverage
    moved = [c for c in cells if c["best"] != TRANSFERRED]
    lines += [
        "",
        "## What this says, and what it does not",
        "",
        "**It does not say the previous number was wrong.** It says the protocol yields a different "
        "result on this chapter. S3 made two measurements that bear on why, and **neither is a causal "
        "account**: the design keeps overlap descriptive in this sprint and fixes the replication as a "
        "reference, not a contrast.",
        "",
        f"1. **Tuning was not tested on `resumen`.** The sweep ran on {english_list([f'`{q}`' for q in SWEEP_SETS])}. "
        f"There, {pt(TRANSFERRED)} is the argmax in {len(cells) - len(moved)} of {len(cells)} cells and the "
        "other cells gain nothing detectable ("
        + "; ".join(f"{fd(c['delta'])}, p = {fp(c['p'])}" for c in moved)
        + "). On `resumen` itself there are two points, "
        + (f"{f4(item['bm25_unigram']['acc'])} and {f4(item['bm25_unigram@previous']['acc'])} for "
           f"`bm25_unigram` at {pt(TRANSFERRED)} and {pt(PREVIOUS_BM25_POINT)}" if "bm25_unigram@previous" in item else "")
        + ". Failing to detect a gain is not showing there is none, and the swept sets are not the "
        "regime of the gap, so whether tuning explains part of it is **open**.",
        f"2. **OE's summaries are less verbatim copies of their targets than OEB's.** `resumen→texto` "
        f"lexical coverage is **{fpc(oe_resumen['lexical_mean'])}** on OE dev (n = {oe_resumen['n']:,}) "
        f"against **{fpc(oeb['lexical_mean'])}** on OEB (n = {oeb['n']:,}, the population the review "
        f"analysis measured, {oeb_in_test:,} of whose pairs belong to OE test concepts), with the "
        "definition that reproduces the review analysis's own figures. That is a difference between two "
        "populations that also differ in chapter, corpus and split — a description, consistent with the "
        "gap, and not a measurement of what caused it. A within-OE comparison belongs to S6.",
        "",
        "**Carry the confound.** Chapter and regime are not separable here: OEB is the largest chapter "
        "of the corpus and the only one the previous study used. The honest claim is *\"does not "
        "replicate on OE\"*.",
        "",
        "**And the table now has a `dense_es_hiiamsid` row**, which the previous submission never "
        "printed although it described the model as one of its seven neural configurations.",
    ]
    keys = [("resumen", m) for m, _, _ in TEN]
    if (RUNS / "resumen" / alt).is_dir():
        keys.append(("resumen", alt))
    write(OUT / "replication.md", lines + sources(keys))
    return item


# --------------------------------------------------------------------------- the sweep


def write_transferability(cells: list[dict], lengths: dict[str, float]) -> None:
    n_cells = len(K1_VALUES) * len(B_VALUES) * len(SWEEP_VARIANTS) * len(SWEEP_SETS)
    lines = header(
        "the `k1`/`b` transferability verdict (dev)",
        [
            f"`k1`/`b` = {pt(TRANSFERRED)} was fitted to OEB `resumen` queries of {lengths['OEB resumen']:.1f}",
            "normalised tokens on average; the OE dev sets swept here run "
            + english_list([f"`{q}` {lengths[q]:.1f}" for q in SWEEP_SETS]) + ".",
            f"{len(K1_VALUES) * len(B_VALUES)} points × {len(SWEEP_VARIANTS)} field variants × "
            f"{len(SWEEP_SETS)} query sets, {n_cells} runs, each point",
            "with its own index because BM25 bakes both parameters into the document weights.",
            "**This is tuning, so it touches dev only.** `resumen` was not swept.",
        ],
    )
    moved = [c for c in cells if c["best"] != TRANSFERRED]
    lines += ["## Verdict: no detectable gain over the transferred point, on the three swept sets (D-036)", ""]
    rows = []
    for c in cells:
        if c["best"] != TRANSFERRED:
            extra = (fci(c["ci"], signed=True), fp(c["p"]), f"+{c['up']} / −{c['down']}")
        else:
            extra = ("—", "—", "—")
        rows.append(
            f"| `{c['variant']}` | `{c['queryset']}` | {pt(c['best'])} | {f4(c['surface'][c['best']])} | "
            f"{f4(c['ref'])} | {fd(c['delta'])} | {extra[0]} | {extra[1]} | {extra[2]} |"
        )
    lines += [
        f"| variant | query set | argmax | its Acc@1 | {pt(TRANSFERRED)} | Δ | CI (paired) | p | queries up / down |",
        "|---|---|---|---:|---:|---:|---|---:|---|",
        *rows,
        "",
        f"**In {len(cells) - len(moved)} of {len(cells)} cells the argmax *is* the transferred point.** In the "
        f"{WORDS[len(moved)]} where it is not, the paired contrast straddles 0 and the flip counts are near-symmetric: "
        "those settings reshuffle which queries succeed rather than retrieving better. Both variants "
        f"therefore keep **{pt(TRANSFERRED)}** into S4 (D-036, referred to César because the frozen rule "
        "names the argmax and S2 rejected D-027 for reinterpreting a rule after seeing results).",
        "",
        "**What this does and does not show.** Not detecting a gain is not showing equivalence: the "
        f"intervals above admit a gain of up to {fd(max(c['ci'][1] for c in moved)) if moved else '—'}. "
        "And the sweep covers the identity and synthetic sets, not `resumen`, so it says nothing about "
        "how much of the replication gap tuning could close — that stays open.",
        "",
        "## The surfaces",
        "",
    ]
    mono, peaked, peak_b, total = shape_in_b(cells)
    corners = sorted({pt(c["best"]) for c in cells})
    k1_best = sorted({f"{c['best'][0]:.2f}" for c in cells})
    lines += [
        f"Item Acc@1 on the duplicate-free population. Every argmax sits at {english_list(corners)}, so "
        f"always at `k1` = {english_list(k1_best)}, the lowest value swept. In `b` the surface is "
        f"single-peaked in {peaked} of {total} (variant, set, `k1`) rows, the peak is at `b` = "
        + english_list([f"{b:.2f} in {n}" for b, n in peak_b])
        + f", and accuracy falls at every step up in `b` in only {mono}: it rises to a peak at low `b` "
        "and declines past it, rather than falling with `b` throughout.",
        "",
    ]
    for c in cells:
        lines += [f"**`{c['variant']}` / `{c['queryset']}`**", "",
                  "| | " + " | ".join(f"b={b:.2f}" for b in B_VALUES) + " |",
                  "|---|" + "---:|" * len(B_VALUES)]
        for k1 in K1_VALUES:
            cells_ = [f4(c["surface"][(k1, b)]) if (k1, b) in c["surface"] else "—" for b in B_VALUES]
            lines.append(f"| **k1={k1:.2f}** | " + " | ".join(cells_) + " |")
        lines.append("")
    keys = [(c["queryset"], point(c["variant"], *TRANSFERRED)) for c in cells]
    keys += [(c["queryset"], point(c["variant"], *c["best"])) for c in moved]
    pairs = [c for c in moved if c["digests"][0] != c["digests"][1]]
    note = ""
    if pairs:
        note = (
            "**Query-set digest pairs.** "
            + " ".join(
                f"`{c['variant']}` / `{c['queryset']}`: the argmax run is on `{c['digests'][0][:8]}` and the "
                f"{pt(TRANSFERRED)} reference on `{c['digests'][1][:8]}`."
                for c in pairs
            )
            + " The reference runs predate the 2026-09-27 corrected delivery. The paired contrast joins on "
            "query key, and the two files carry the same keys and the same query texts "
            "(`tests/test_intake_20260927.py`), so both sides score the same sample."
        )
    write(OUT / "transferability.md", lines + sources(keys, note))


def write_provenance() -> None:
    """Every S3 run in one table, so a reader can check a stamp without opening `runs/`."""
    lines = [
        "# S3 — provenance of every run behind `results/S3/e0/`",
        "",
        f"Generated by `{GENERATOR}`. Operating rule 1: a number without "
        "`{run_id, config SHA, code commit, query-set SHA-256}` does not exist. "
        "`src/utils/check_run_inputs.py` verifies that each of these still resolves against the tree.",
        "",
        "| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
        "|---|---:|---|---|---|---|",
    ]
    seen = set()
    groups = [("texto", [m for m, _, _ in TEN]),
              ("resumen", [m for m, _, _ in TEN] + [point("bm25_unigram", *PREVIOUS_BM25_POINT)])]
    for variant in SWEEP_VARIANTS:
        for queryset in SWEEP_SETS:
            groups.append((queryset, [point(variant, k1, b) for k1 in K1_VALUES for b in B_VALUES]))
    n = dirty = 0
    for queryset, methods in groups:
        for method in methods:
            key = (queryset, method)
            if key in seen or not (RUNS / queryset / method / "run_meta.json").is_file():
                continue
            seen.add(key)
            m = meta(queryset, method)
            n += 1
            dirty += bool(m.get("code_dirty"))
            lines.append(
                f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
                f"`{m['query_set_sha256'][:16]}` |"
            )
    lines += [
        "",
        f"{n} runs, {dirty} stamped `code_dirty: true`. The S3 runner scripts (the git-ignored "
        "`logs/S3/*.sh`) checked the tree before starting, after S3 found that a host/container "
        "line-ending disagreement had stamped a clean tree dirty (defect H5). **That check is not in "
        "committed code** — `src/utils/provenance.py` records dirtiness and does not refuse — so the "
        "guarantee is this column, not the runner.",
        "",
        "**What these stamps do not carry**, for the four local dense arms: the `torch`, "
        "`transformers` and `sentence-transformers` versions that produced the embeddings. "
        "`index/*/meta.json` records only `{python, sklearn}` (defect H4), so for a neural arm the "
        "provenance set is incomplete and the versions live in `logs/S3/build_indexes.sh`'s captured "
        "output — a log, not a stamp. To be fixed before S12, the one run that cannot be repeated.",
    ]
    write(OUT / "run_provenance.md", lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dup = flagged()
    rows = ceiling_rows(dup)
    cells = sweep(dup)
    hiiamsid = stats(scored(perquery("resumen", METHOD_OF["dense_es_hiiamsid"]), dup, "item"), "item",
                     "rep|dense_es_hiiamsid")
    write_ceiling(dup, rows, sparse_diagnosis(dup), hiiamsid)
    write_replication(dup, cells, replication_coverage())
    write_transferability(cells, query_lengths())
    write_provenance()
    print(f"written: {OUT.relative_to(REPO)}")
    for path in sorted(OUT.glob("*.md")):
        print(f"  {path.name}")


if __name__ == "__main__":
    main()
