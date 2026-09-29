"""Build docs/synthetic-oe/results/S4/ — S4 work item 6 (design frozen at `dd407c6`).

The E1 robustness profile, Track A: fifteen arms × nine single modification types on OE dev, each
query paired with the **same arm's identity result on its own gold leaf** (treatment effect on the
treated). Ten arms are the indexed ones S3 measured; five are derived from their top-100 lists
(two RRF fusions, three cross-encoder blends).

- `ceilings.md` (T1) — the five derived arms' identity ceilings; the ten indexed ones are S3's.
- `profile_item.md` (T2) — arm × type, item level: identity on the treated leaves, modified, δ,
  retention, flips.
- `profile_parent.md` (T3) — the same at parent level, plus the collapse quantities of H1.
- `token_distance.md` (T4) — d_tok and δ / d_tok per cell; the D-038 number count. Descriptive.
- `ties.md` (T5) — rank-1 score ties per cell (D-028).
- `predictions.md` (T6) — P1–P5 read under the frozen rule.
- `run_provenance.md` (T7) — every run read, and the retrieval-path diff behind each reuse.

**Population.** Item level: dev `single_texto` queries whose gold is not in a
`duplicate_texto_group` (D-033), minus any query excluded by a design amendment
(`AMENDMENT_EXCLUDED`). Parent level: every dev query, minus amendment exclusions that apply to it.

**Every number in the prose is interpolated** (`tests/test_generated_prose.py`).

    python src/utils/build_results_s4.py
"""

from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.build_results_s2 import (  # noqa: E402
    ALPHA, B, SEED, bh, boot_cluster, boot_p, boot_query, ci, f4, fci, fd, fp, holm, write,
)
from utils.corpus_prep import extract_numbers, normalize_text, tokenize_words  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402

RUNS = REPO / "runs" / "OE"
DATA = REPO / "data" / "processed"
SIDECAR = DATA / "OE_duplicate_texto_groups.json"
SINGLE_JSON = DATA / "OE_single_texto.json"
CORPUS_JSON = DATA / "OE_texto.json"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S4"
GENERATOR = "src/utils/build_results_s4.py"

#: (run directory, short name, oracle, derived)
ARMS = [
    ("bm25_unigram_params__k1-0.60__b-0.35__OE", "bm25_unigram_params", True, False),
    ("bm25_unigram__k1-0.60__b-0.35__OE", "bm25_unigram", False, False),
    ("tfidf_unigram_phrases_replace__OE", "tfidf_phrases_replace", True, False),
    ("bge_m3_colbert__OE", "bge_m3_colbert", False, False),
    ("bge_m3_dense__OE", "bge_m3_dense", False, False),
    ("bge_m3_sparse__OE", "bge_m3_sparse", False, False),
    ("dense_e5__OE", "dense_e5", False, False),
    ("dense_es_hiiamsid__OE", "dense_es_hiiamsid", False, False),
    ("dense_gte__OE", "dense_gte", False, False),
    ("dense_gte_instrQ__OE", "dense_gte_instrQ", False, False),
    ("rrf__bm25_unigram+bge_m3_colbert__OE", "rrf", False, True),
    ("rrf__bm25_unigram_params+bge_m3_colbert__OE", "rrf_params", True, True),
    ("ce_blend__bm25_unigram__OE", "ce_bm25_unigram", False, True),
    ("ce_blend__bge_m3_colbert__OE", "ce_bge_m3_colbert", False, True),
    ("ce_blend__rrf__bm25_unigram+bge_m3_colbert__OE", "ce_rrf", False, True),
]
DIR = {short: d for d, short, _, _ in ARMS}
ORACLE = {short for _, short, o, _ in ARMS if o}
DERIVED = [short for _, short, _, dv in ARMS if dv]
TWIN = {"bm25_unigram_params": "bm25_unigram", "rrf_params": "rrf", "tfidf_phrases_replace": "bm25_unigram"}

LAYERS = {
    "L1": ["synonym_label", "num_to_text", "unit_expansion", "unit_conversion"],
    "L2": ["paraphrase", "compression", "expansion"],
    "L3": ["reorder", "template_paraphrase"],
}
TYPES = [t for layer in LAYERS.values() for t in layer]
SCOPES = TYPES + list(LAYERS) + ["all"]
LEVELS = ("item", "parent")

#: Design constraint "Floor arms": below this identity item Acc@1 on the treated leaves an arm
#: has no item-level headroom to lose, and is excluded from every prediction reading.
FLOOR = 0.20
#: P3's equivalence margin on `reorder` item δ.
MARGIN = 0.02

#: Queries excluded by a design amendment, with the amendment and the levels it applies to.
AMENDMENT_EXCLUDED: dict[str, dict] = {
    "OEC140baa_syn_74d5dd2c9da3": {
        "amendment": "design A2",
        "levels": ("item",),
        "why": "its text is another leaf's `texto` verbatim (`OEC140aba`), rendered by a `reorder` that "
               "permuted a lookup's arguments upstream (`DATASET_DEFECTS.md` P7); its concept is right.",
    },
}

#: The registered predictions (design, "Design constraints"). kind: paired | between | tost.
PREDICTIONS = [
    ("P1", "H1", "gap widens, all nine types: (parent − item)_mod − (parent − item)_id > 0",
     "gap", ["bm25_unigram", "bm25_unigram_params", "bge_m3_colbert"]),
    ("P2", "H2 L1", "pooled L1 item δ below pooled L2 δ", "l1_vs_l2", ["bm25_unigram", "bm25_unigram_params"]),
    ("P2", "H2 L1", "pooled L1 item δ below pooled L3 δ", "l1_vs_l3", ["bm25_unigram", "bm25_unigram_params"]),
    ("P3", "H2 L3", "`reorder` item δ within the margin", "reorder_equiv",
     ["bm25_unigram", "bm25_unigram_params", "tfidf_phrases_replace"]),
    ("P4", "H2 L3", "`reorder` item δ < 0", "reorder_neg", ["bge_m3_colbert", "bge_m3_dense", "dense_es_hiiamsid"]),
    ("P5", "H2 L2", "share of item losses in the wrong concept: pooled L2 above pooled L1", "l2_concept",
     ["bm25_unigram", "bge_m3_colbert"]),
]

_DECIMAL = re.compile(r"\d\.\d{3}\b")


# --------------------------------------------------------------------------- inputs


def meta(queryset: str, method: str) -> dict:
    return json.loads((RUNS / queryset / method / "run_meta.json").read_text(encoding="utf-8"))


def perquery(queryset: str, method: str) -> pd.DataFrame:
    return pd.read_parquet(RUNS / queryset / method / "results_perquery.parquet")


def duplicated() -> set[str]:
    return {m for g in json.loads(SIDECAR.read_text(encoding="utf-8"))["groups"].values() for m in g}


def top2(queryset: str, method: str, keep: set[str] | None = None) -> dict[str, tuple[float, float | None, frozenset]]:
    """query key -> (rank-1 score, rank-2 score, the keys tied with rank 1), for the tie table."""
    out = {}
    with gzip.open(RUNS / queryset / method / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            key = str(r["query_item_key"])
            if keep is not None and key not in keep:
                continue
            c = r["candidates"]
            s1 = float(c[0]["score"])
            tied = frozenset(str(x["index_item_key"]) for x in c if float(x["score"]) == s1)
            out[key] = (s1, float(c[1]["score"]) if len(c) > 1 else None, tied)
    return out


def texts() -> tuple[dict[str, str], dict[str, str]]:
    queries = {r["item_key"]: r["text"] for r in json.loads(SINGLE_JSON.read_text(encoding="utf-8"))}
    corpus = {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}
    return queries, corpus


# --------------------------------------------------------------------------- pairing


def paired(short: str, dup: set[str]) -> pd.DataFrame:
    """One row per dev single query: modified and identity hits at both levels, and its type."""
    mod = perquery("single_texto", DIR[short])
    ident = perquery("texto", DIR[short]).set_index("query_item_key")
    types = mod["modification_types"].map(lambda t: list(t))
    if (types.map(len) != 1).any():
        raise ValueError(f"{short}: a single_texto query carries other than one type")
    frame = pd.DataFrame({
        "q": mod["query_item_key"].astype(str),
        "gold": mod["gold_item_key"].astype(str),
        "concept": mod["gold_parent_key"].astype(str),
        "type": types.map(lambda t: t[0]),
        "item_mod": mod["item_acc1"].astype(float),
        "parent_mod": mod["parent_acc1"].astype(float),
    })
    missing = set(frame["gold"]) - set(ident.index)
    if missing:
        raise KeyError(f"{short}: {len(missing)} golds have no identity result, e.g. {sorted(missing)[:3]}")
    frame["item_id"] = frame["gold"].map(ident["item_acc1"]).astype(float)
    frame["parent_id"] = frame["gold"].map(ident["parent_acc1"]).astype(float)
    frame["item_scored"] = ~frame["gold"].isin(dup) & ~frame["q"].map(lambda k: "item" in AMENDMENT_EXCLUDED.get(k, {}).get("levels", ()))
    frame["parent_scored"] = ~frame["q"].map(lambda k: "parent" in AMENDMENT_EXCLUDED.get(k, {}).get("levels", ()))
    return frame


def scope(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "all":
        return frame
    if name in LAYERS:
        return frame[frame["type"].isin(LAYERS[name])]
    return frame[frame["type"] == name]


def level_frame(frame: pd.DataFrame, level: str) -> pd.DataFrame:
    return frame[frame[f"{level}_scored"]]


# --------------------------------------------------------------------------- statistics


def cell(frame: pd.DataFrame, level: str, label: str) -> dict:
    """Identity, modified, δ, retention and flips for one (arm, scope, level)."""
    f = level_frame(frame, level)
    ident, mod = f[f"{level}_id"].to_numpy(), f[f"{level}_mod"].to_numpy()
    clusters = f["concept"].to_numpy()
    d = mod - ident
    cols = np.column_stack([d, ident * mod, ident])
    q = boot_query(cols, f"s4|{label}|{level}")
    c = boot_cluster(cols, clusters, f"s4|{label}|{level}")
    kept = ident.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        ret_c = c[:, 1] / c[:, 2]
    ret_c = ret_c[np.isfinite(ret_c)]
    return {
        "n": len(f), "concepts": int(f["concept"].nunique()),
        "id": float(ident.mean()), "mod": float(mod.mean()),
        "delta": float(d.mean()), "q": ci(q[:, 0]), "c": ci(c[:, 0]), "p": boot_p(c[:, 0]),
        "retention": float((ident * mod).sum() / kept) if kept else float("nan"),
        "ret_c": ci(ret_c) if len(ret_c) else (float("nan"), float("nan")),
        "id_hits": int(kept), "down": int(((ident == 1) & (mod == 0)).sum()),
        "up": int(((ident == 0) & (mod == 1)).sum()),
    }


def collapse(frame: pd.DataFrame, label: str) -> dict:
    """H1's quantities on the item-scored queries: RP/WI rate, D, the gap, and their changes."""
    f = level_frame(frame, "item")
    clusters = f["concept"].to_numpy()
    out = {"n": len(f)}
    for side in ("id", "mod"):
        item, parent = f[f"item_{side}"].to_numpy(), f[f"parent_{side}"].to_numpy()
        out[f"rpwi_{side}"] = float(((parent == 1) & (item == 0)).mean())
        out[f"D_{side}"] = float(item[parent == 1].mean()) if (parent == 1).any() else float("nan")
        out[f"gap_{side}"] = float((parent - item).mean())
    for name, values in (
        ("rpwi", ((f["parent_mod"] == 1) & (f["item_mod"] == 0)).astype(float)
                 - ((f["parent_id"] == 1) & (f["item_id"] == 0)).astype(float)),
        ("gap", (f["parent_mod"] - f["item_mod"]) - (f["parent_id"] - f["item_id"])),
    ):
        v = values.to_numpy(float)[:, None]
        cq = boot_query(v, f"s4|{label}|{name}")[:, 0]
        cc = boot_cluster(v, clusters, f"s4|{label}|{name}")[:, 0]
        out[f"d_{name}"] = float(v.mean())
        out[f"d_{name}_q"], out[f"d_{name}_c"], out[f"d_{name}_p"] = ci(cq), ci(cc), boot_p(cc)
    return out


def pool_draws(frame: pd.DataFrame, level: str, value, label: str) -> tuple[float, np.ndarray]:
    """Point estimate and concept-clustered draws of mean(value) on one pool."""
    f = level_frame(frame, level)
    v = value(f)
    return float(v.mean()), boot_cluster(v[:, None], f["concept"].to_numpy(), label)[:, 0]


def ratio_draws(frame: pd.DataFrame, num, den, label: str) -> tuple[float, np.ndarray]:
    f = level_frame(frame, "item")
    n, d = num(f), den(f)
    draws = boot_cluster(np.column_stack([n, d]), f["concept"].to_numpy(), label)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = draws[:, 0] / draws[:, 1]
    return float(n.sum() / d.sum()) if d.sum() else float("nan"), r


# --------------------------------------------------------------------------- predictions


def delta_item(f: pd.DataFrame) -> np.ndarray:
    return (f["item_mod"] - f["item_id"]).to_numpy(float)


def evaluate_prediction(kind: str, short: str, frame: pd.DataFrame) -> dict:
    label = f"s4|pred|{kind}|{short}"
    if kind == "gap":
        est, draws = pool_draws(frame, "item",
                                lambda f: ((f["parent_mod"] - f["item_mod"]) - (f["parent_id"] - f["item_id"])).to_numpy(float),
                                label)
        return {"est": est, "c": ci(draws), "p": boot_p(draws), "side": "positive"}
    if kind in ("l1_vs_l2", "l1_vs_l3"):
        other = "L2" if kind == "l1_vs_l2" else "L3"
        a, da = pool_draws(scope(frame, "L1"), "item", delta_item, label + "|L1")
        b, db = pool_draws(scope(frame, other), "item", delta_item, label + "|" + other)
        draws = da - db
        return {"est": a - b, "c": ci(draws), "p": boot_p(draws), "side": "negative"}
    if kind == "reorder_equiv":
        est, draws = pool_draws(scope(frame, "reorder"), "item", delta_item, label)
        p = max((1 + int((draws <= -MARGIN).sum())) / (B + 1), (1 + int((draws >= MARGIN).sum())) / (B + 1))
        return {"est": est, "c": ci(draws), "p": min(1.0, p), "side": "equivalent"}
    if kind == "reorder_neg":
        est, draws = pool_draws(scope(frame, "reorder"), "item", delta_item, label)
        return {"est": est, "c": ci(draws), "p": boot_p(draws), "side": "negative"}
    if kind == "l2_concept":
        loss = lambda f: ((f["item_id"] == 1) & (f["item_mod"] == 0)).to_numpy(float)  # noqa: E731
        wrong = lambda f: (((f["item_id"] == 1) & (f["item_mod"] == 0)) & (f["parent_mod"] == 0)).to_numpy(float)  # noqa: E731
        a, da = ratio_draws(scope(frame, "L2"), wrong, loss, label + "|L2")
        b, db = ratio_draws(scope(frame, "L1"), wrong, loss, label + "|L1")
        draws = da - db
        draws = draws[np.isfinite(draws)]
        return {"est": a - b, "c": ci(draws), "p": boot_p(draws), "side": "positive"}
    raise ValueError(kind)


def reading(r: dict) -> str:
    lo, hi = r["c"]
    if r["side"] == "equivalent":
        if -MARGIN < lo and hi < MARGIN and r["holm"] < ALPHA:
            return "supported"
        if lo >= MARGIN or hi <= -MARGIN:
            return "contradicted"
        return "not supported"
    good, bad = (lo > 0, hi < 0) if r["side"] == "positive" else (hi < 0, lo > 0)
    if good and r["holm"] < ALPHA:
        return "supported"
    if bad and r["holm"] < ALPHA:
        return "contradicted"
    return "not supported"


# --------------------------------------------------------------------------- tables


def name(short: str) -> str:
    return f"`{short}`" + (" **oracle**" if short in ORACLE else "")


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S4 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def population_note(pops: dict) -> list[str]:
    lines = [
        f"**Population.** {pops['n']:,} dev `single_texto` queries over {pops['concepts']} concepts. "
        f"Item level scores {pops['item']:,}: {pops['dup']:,} excluded because the gold shares its "
        f"`texto` (D-033)" + (f" and {pops['amend_item']:,} by design amendment" if pops['amend_item'] else "")
        + f". Parent level scores {pops['parent']:,}"
        + (f" ({pops['amend_parent']:,} excluded by design amendment)." if pops['amend_parent'] else "."),
        "",
    ]
    for key, entry in sorted(AMENDMENT_EXCLUDED.items()):
        lines.append(f"- `{key}` excluded at {', '.join(entry['levels'])} level ({entry['amendment']}): {entry['why']}")
    if AMENDMENT_EXCLUDED:
        lines.append("")
    return lines


def write_profile(level: str, stats: dict, floors: dict, pops: dict) -> None:
    title = "T2: the E1 profile, item level (dev)" if level == "item" else "T3: the E1 profile, parent level (dev)"
    lines = header(title, [
        "Each query is paired with the same arm's identity result on its own gold leaf; δ is the mean of",
        "modified − identity over the cell's queries, so every row is a treatment effect on the treated.",
        "Raw modified Acc@1 is printed only beside its own identity baseline and is not compared across types,",
        "whose populations differ.",
    ])
    lines += population_note(pops)
    lines += [
        "**Retention** is P(hit under modification | hit at identity). δ is bounded below by the identity",
        "baseline, so where arms are set side by side it is retention that is quoted (D-032).",
        "",
    ]
    if level == "item":
        floor_arms = [s for s, v in floors.items() if v < FLOOR]
        lines += [
            f"**Floor arms**, identity item Acc@1 below {f4(FLOOR)} on the treated leaves: "
            + (", ".join(f"{name(s)} ({f4(floors[s])})" for s in floor_arms) if floor_arms else "none")
            + ". They are reported and excluded from every prediction reading.",
            "",
        ]
    lines += ["Oracle arms read the query's own parsed `parameters` (D-010) and are quoted only with their "
              "text-only twin: " + ", ".join(f"{name(o)} with `{t}`" for o, t in TWIN.items()) + ".", ""]
    for short in stats:
        lines += [f"## {name(short)}", "",
                  "| scope | n | concepts | identity | modified | δ | CI (query) | CI (concept) | retention | CI (concept) | lost | gained |",
                  "|---|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|"]
        for sc in SCOPES:
            c = stats[short][(sc, level)]
            lines.append(
                f"| {sc} | {c['n']:,} | {c['concepts']} | {f4(c['id'])} | {f4(c['mod'])} | {fd(c['delta'])} | "
                f"{fci(c['q'], True)} | {fci(c['c'], True)} | {f4(c['retention'])} | {fci(c['ret_c'])} | "
                f"{c['down']:,} | {c['up']:,} |"
            )
        lines.append("")
    if level == "parent":
        lines += ["## The collapse quantities of H1 (item-scored queries)", "",
                  "RP/WI is the share of queries whose rank 1 is in the right concept and is the wrong leaf; "
                  "D = P(item correct | parent correct); the gap is parent − item Acc@1. Changes are paired, "
                  "modified − identity.", ""]
        for short in stats:
            lines += [f"### {name(short)}", "",
                      "| scope | n | RP/WI id | RP/WI mod | Δ RP/WI | CI (concept) | D id | D mod | gap id | gap mod | Δ gap | CI (concept) |",
                      "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|"]
            for sc in SCOPES:
                k = stats[short][(sc, "collapse")]
                lines.append(
                    f"| {sc} | {k['n']:,} | {f4(k['rpwi_id'])} | {f4(k['rpwi_mod'])} | {fd(k['d_rpwi'])} | "
                    f"{fci(k['d_rpwi_c'], True)} | {f4(k['D_id'])} | {f4(k['D_mod'])} | {f4(k['gap_id'])} | "
                    f"{f4(k['gap_mod'])} | {fd(k['d_gap'])} | {fci(k['d_gap_c'], True)} |"
                )
            lines.append("")
    lines += sources_block(["texto", "single_texto"])
    write(OUT / ("profile_item.md" if level == "item" else "profile_parent.md"), lines)


def token_distance(q: str, g: str) -> float:
    a = set(tokenize_words(normalize_text(q)))
    b = set(tokenize_words(normalize_text(g)))
    union = a | b
    return 1.0 - len(a & b) / len(union) if union else 0.0


def write_token_distance(stats: dict, frame0: pd.DataFrame, qtext: dict, ctext: dict) -> None:
    f = frame0.copy()
    f["d_tok"] = [token_distance(qtext[k], ctext[g]) for k, g in zip(f["q"], f["gold"])]
    f["d_num"] = [len(extract_numbers(normalize_text(qtext[k]))) - len(extract_numbers(normalize_text(ctext[g])))
                  for k, g in zip(f["q"], f["gold"])]
    f["decimal"] = [bool(set(_DECIMAL.findall(qtext[k])) - set(_DECIMAL.findall(ctext[g])))
                    for k, g in zip(f["q"], f["gold"])]
    lines = header("T4: token distance to the gold `texto`, per cell (dev)", [
        "d_tok = 1 − Jaccard of the distinct tokens of the query and its gold `texto`, with the S3 overlap's",
        "`normalize_text` / `tokenize_words`; 0 for the identity rendering. δ / d_tok divides the cell's mean δ",
        "by its mean d_tok. Δ numbers is the query's number count minus the gold's (D-038). Descriptive: no",
        "mediation is claimed here (H5 is S6's).",
    ])
    lines += [f"`decimal artefact` counts queries carrying a `d.ddd` decimal their gold lacks, which `normalize_text` "
              "reads as a thousands group (D-010, adjacent note): a miss there is a feature artefact.", ""]
    lines += ["| scope | n | mean d_tok | Δ numbers | decimal artefact |", "|---|---:|---:|---:|---:|"]
    for sc in SCOPES:
        s = scope(f, sc)
        lines.append(f"| {sc} | {len(s):,} | {f4(s['d_tok'].mean())} | {fd(s['d_num'].mean())} | {int(s['decimal'].sum())} |")
    lines += ["", "## δ / d_tok per arm, item and parent level", "",
              "| arm | " + " | ".join(SCOPES) + " |", "|---|" + "---:|" * len(SCOPES)]
    means = {sc: scope(f, sc)["d_tok"].mean() for sc in SCOPES}
    for short in stats:
        for level in LEVELS:
            lines.append(f"| {name(short)} {level} | " + " | ".join(
                fd(stats[short][(sc, level)]["delta"] / means[sc]) if means[sc] else "—" for sc in SCOPES) + " |")
    lines += sources_block(["single_texto"], inputs=(SINGLE_JSON, CORPUS_JSON))
    write(OUT / "token_distance.md", lines)


def write_ties(frames: dict, dup: set[str]) -> None:
    lines = header("T5: rank-1 score ties, per cell (dev)", [
        "Share of queries whose rank-1 and rank-2 scores are exactly equal, under modification and at identity",
        "on the same golds (D-028). A tie is broken by the retriever's sort, not by anything the query controls;",
        "the derived arms break theirs by a fixed rule (design A1).",
    ])
    lines += ["Item-scored queries only: a gold that shares its `texto` with a sibling (D-033) ties with it "
              "by construction, whatever the query, and is excluded here as it is from item-level scoring.", ""]
    lines += ["| arm | " + " | ".join(SCOPES) + " |", "|---|" + "---|" * len(SCOPES)]
    decisive = []
    for short, frame in frames.items():
        frame = level_frame(frame, "item")
        mod = top2("single_texto", DIR[short], keep=set(frame["q"]))
        ident = top2("texto", DIR[short], keep=set(frame["gold"]))
        is_tie = lambda v: v[1] is not None and v[0] == v[1]  # noqa: E731
        cells = []
        for sc in SCOPES:
            s = scope(frame, sc)
            tm = np.mean([is_tie(mod[k]) for k in s["q"]])
            ti = np.mean([is_tie(ident[g]) for g in s["gold"]])
            cells.append(f"{f4(tm)} / {f4(ti)}")
        lines.append(f"| {name(short)} | " + " | ".join(cells) + " |")
        for sc in ("L1", "all"):
            s = scope(frame, sc)
            tied = [(mod[k][2], g, h) for k, g, h in zip(s["q"], s["gold"], s["item_mod"]) if is_tie(mod[k])]
            with_gold = [(t, h) for t, g, h in tied if g in t]
            decisive.append((short, sc, len(s), len(tied), len(with_gold),
                             sum(h for _, h in with_gold),
                             float(np.mean([1 / len(t) for t, _ in with_gold])) if with_gold else float("nan")))
    lines += ["", "Each cell: modified / identity.", "",
              "## Where a modified query's rank 1 is tied, did the gold win the tie?", "",
              "Among tied modified queries: how many have the gold inside the tied group (top-100 only), how many "
              "of those the gold wins, and the share a uniform draw from the tied group would win. A gold that wins "
              "above that share wins by the retriever's sort order, not by anything in the query.", "",
              "| arm | scope | n | tied | gold in tie | gold wins | wins, share | uniform draw |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for short, sc, n, t, wg, won, chance in decisive:
        lines.append(f"| {name(short)} | {sc} | {n:,} | {t:,} | {wg:,} | {int(won):,} | "
                     f"{f4(won / wg) if wg else '—'} | {f4(chance) if wg else '—'} |")
    lines += sources_block(["texto", "single_texto"])
    write(OUT / "ties.md", lines)


def write_ceilings(dup: set[str]) -> None:
    lines = header("T1: identity ceilings of the derived arms (`texto`, dev)", [
        "Each derived arm asked to retrieve a document from that document's own text, as S3 did for the ten",
        "indexed arms (their table: `results/S3/e0/ceiling.md`, not recomputed here). Item level on the",
        "duplicate-free golds (D-033), whose ceiling is 1.0, so headroom is the scored value itself (D-032).",
        "The cross-encoder blend is not comparable with the previous study's reranking rows (design A1, D-042).",
    ])
    lines += ["| arm | item, all | item, scored | n scored | CI (query) | CI (concept) | parent | CI (query) | CI (concept) |",
              "|---|---:|---:|---:|---|---|---:|---|---|"]
    for short in DERIVED:
        f = perquery("texto", DIR[short])
        scored = f[~f["gold_item_key"].isin(dup)]
        cl_s, cl = scored["gold_parent_key"].to_numpy(), f["gold_parent_key"].to_numpy()
        iv = scored[["item_acc1"]].to_numpy(float)
        pv = f[["parent_acc1"]].to_numpy(float)
        lines.append(
            f"| {name(short)} | {f4(f['item_acc1'].mean())} | **{f4(iv.mean())}** | {len(scored):,} | "
            f"{fci(ci(boot_query(iv, 's4|ceil|' + short)[:, 0]))} | {fci(ci(boot_cluster(iv, cl_s, 's4|ceil|' + short)[:, 0]))} | "
            f"{f4(pv.mean())} | {fci(ci(boot_query(pv, 's4|ceilp|' + short)[:, 0]))} | "
            f"{fci(ci(boot_cluster(pv, cl, 's4|ceilp|' + short)[:, 0]))} |"
        )
    lines += sources_block(["texto"], only=DERIVED)
    write(OUT / "ceilings.md", lines)


def write_predictions(results: list[dict], excluded: list[str]) -> None:
    lines = header("T6: the registered predictions (dev)", [
        "Read on the concept-clustered interval, Holm–Bonferroni across the tests below, Benjamini–Hochberg",
        "beside it. **Supported** when the interval lies on the predicted side of 0 (inside the margin for P3)",
        "and the Holm p is below α; **contradicted** in the mirror case (for P3, an interval wholly outside",
        "the margin); **not supported** otherwise. Layer contrasts (P2, P5) compare different leaves and are",
        "bootstrapped independently within each pool: they are between-population.",
    ])
    lines += [f"α = {ALPHA}; P3 margin ±{MARGIN}.", ""]
    if excluded:
        lines += ["Tests dropped because the arm is a floor arm: " + ", ".join(excluded) + ".", ""]
    lines += ["| prediction | hypothesis | test | arm | estimate | CI (concept) | p | Holm p | BH p | reading |",
              "|---|---|---|---|---:|---|---:|---:|---:|---|"]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['hyp']} | {r['what']} | {name(r['arm'])} | {fd(r['est'])} | {fci(r['c'], True)} | "
            f"{fp(r['p'])} | {fp(r['holm'])} | {fp(r['bh'])} | **{r['reading']}** |"
        )
    lines += sources_block(["texto", "single_texto"], only=sorted({r["arm"] for r in results}))
    write(OUT / "predictions.md", lines)


# --------------------------------------------------------------------------- provenance


def sources_block(querysets: list[str], only: list[str] | None = None, inputs: tuple[Path, ...] = ()) -> list[str]:
    lines = ["", "## Sources", "", "| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
             "|---|---:|---|---|---|---|"]
    for queryset in querysets:
        for d, short, _, _ in ARMS:
            if only is not None and short not in only:
                continue
            m = meta(queryset, d)
            lines.append(
                f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` |"
            )
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (SIDECAR, *inputs)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals; p from the concept-clustered "
              "draws (D-030). Split `dev`."]
    return lines


RETRIEVAL_PATH = ["src/retrieve.ipynb", "src/utils/run_context.py", "src/utils/splits.py",
                  "src/utils/corpus_prep.py", "src/utils/provenance.py"]
MODULE_FILES = {"bm25_unigram_params": ["bm25_unigram"], "tfidf_unigram_phrases_replace": ["tfidf_unigram"]}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def write_provenance() -> None:
    new_commits = {meta("single_texto", d)["code_commit"] for d, s, _, dv in ARMS if dv}
    lines = header("T7: run provenance and reuse (dev)", [
        "Every run the S4 tables read. A run made before S4 is reused only if nothing on its retrieval path",
        "changed between its commit and S4's: its retriever module (and what it imports), `retrieve.ipynb`,",
        "`run_context`, `splits`, `corpus_prep`, `provenance`, and its config. The diff is computed here, not typed.",
    ])
    lines += ["| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 | derived from | S4 |",
              "|---|---:|---|---|---|---|---|---|"]
    reused = []
    for queryset in ("texto", "single_texto"):
        for d, short, _, dv in ARMS:
            m = meta(queryset, d)
            comps = ", ".join(f"`{c['run_id']}` @ `{c['code_commit'][:7]}`" for c in m.get("components", [])) or "—"
            is_new = m["code_commit"] in new_commits
            lines.append(
                f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` | {comps} | "
                f"{'new' if is_new else 'reused'} |"
            )
            if not is_new:
                reused.append(m)
    head = sorted(new_commits)[0] if len(new_commits) == 1 else None
    lines += ["", "## Retrieval-path diff of each reused run against S4's commit", ""]
    if head is None:
        lines.append(f"S4's runs span {len(new_commits)} commits; each reuse is diffed against every one.")
    for m in reused:
        module = m["retriever_module"].split(".")[-1]
        files = [f"src/retrievers/{x}.py" for x in [module, *MODULE_FILES.get(module, [])]]
        files += RETRIEVAL_PATH + ["configs/" + Path(m["config"]).name]
        for target in sorted(new_commits):
            stat = git("diff", "--stat", f"{m['code_commit']}..{target}", "--", *files)
            changed = [line.split("|")[0].strip() for line in stat.splitlines()[:-1]]
            touches_retriever = [c for c in changed if c.startswith("src/retrievers/") or c.endswith(".ipynb") or c.startswith("configs/")]
            lines.append(
                f"- `{m['run_id']}` `{m['code_commit'][:7]}..{target[:7]}`: "
                + (", ".join(f"`{c}`" for c in changed) if changed else "no change")
                + (" — **retriever, notebook or config changed**" if touches_retriever else "")
            )
    lines += ["", "No reused run's retriever, `retrieve.ipynb` or config may appear above; the remaining files "
              "are precondition checks and query-set registration, and the query tables the runs read carry the "
              "digests printed in the table."]
    write(OUT / "run_provenance.md", lines)


# --------------------------------------------------------------------------- main


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dup = duplicated()
    frames = {short: paired(short, dup) for _, short, _, _ in ARMS}

    first = next(iter(frames.values()))
    for short, frame in frames.items():
        if list(frame["q"]) != list(first["q"]):
            raise ValueError(f"{short}: single_texto queries differ from {ARMS[0][1]}'s")
    pops = {
        "n": len(first), "concepts": int(first["concept"].nunique()),
        "item": int(first["item_scored"].sum()), "parent": int(first["parent_scored"].sum()),
        "dup": int(first["gold"].isin(dup).sum()),
        "amend_item": sum("item" in e["levels"] for e in AMENDMENT_EXCLUDED.values()),
        "amend_parent": sum("parent" in e["levels"] for e in AMENDMENT_EXCLUDED.values()),
    }

    stats = {}
    for short, frame in frames.items():
        stats[short] = {}
        for sc in SCOPES:
            s = scope(frame, sc)
            for level in LEVELS:
                stats[short][(sc, level)] = cell(s, level, f"{short}|{sc}")
            stats[short][(sc, "collapse")] = collapse(s, f"{short}|{sc}")
    floors = {short: stats[short][("all", "item")]["id"] for short in stats}

    write_ceilings(dup)
    write_profile("item", stats, floors, pops)
    write_profile("parent", stats, floors, pops)
    qtext, ctext = texts()
    write_token_distance(stats, first, qtext, ctext)
    write_ties(frames, dup)

    results, excluded = [], []
    for pid, hyp, what, kind, arms in PREDICTIONS:
        for short in arms:
            if floors[short] < FLOOR:
                excluded.append(f"{pid} `{short}`")
                continue
            results.append({"id": pid, "hyp": hyp, "what": what, "arm": short,
                            **evaluate_prediction(kind, short, frames[short])})
    p = [r["p"] for r in results]
    for r, h, q in zip(results, holm(p), bh(p)):
        r.update(holm=h, bh=q)
        r["reading"] = reading(r)
    write_predictions(results, excluded)
    write_provenance()
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
