"""S7 — E2 stacked headline and stratifications: T1–T9, Figs. 4–5 and the S2 regression (design `5e89809`, A1).

    python src/utils/build_results_s7.py        # in the sprint container, bc3cat-s3

Reads, and never writes, `runs/OE/stacked_texto/<arm>` (S7's eighteen runs), each arm's `texto` run for the
identity side, `single_texto` and `single_l2_texto` for T2's references, and S2's archived stacked runs for the
regression (work item 4). Writes `docs/synthetic-oe/results/S7/`.

The pairing is S4's (treatment effect on the treated: the same arm's `texto` result on the same gold); tie-free
values, cells, discrimination and the clustered bootstrap are S6's, imported, not copied. What is new:
- **W1–W3**, 21 registered tests (design), each tie-free (primary), as run, on the D-004 clean subset, and with
  W3 adjusted (A1 d).
- **W3** is an OLS slope of the item loss on log₂ family size, solved from per-concept sums so that each
  bootstrap draw is a weighted sum (A1 a–c).
- The dose field is `texto_modification_count` (D-025 note); `modification_count` is printed beside it.
- T2–T7 print n excluded, the concept count and the query-level interval beside every item-level δ and slope
  (A5, A6, audit F2); T2's stacked cell shares T1's draws (A6, audit F7).

The analysis stack is pinned (`analysis_stack.py`): the script refuses to run on another.
"""

from __future__ import annotations

import gzip
import json
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import subprocess  # noqa: E402
import sys  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils import analysis_stack  # noqa: E402
from utils.archived_runs import run_dir_as_of  # noqa: E402
from utils.build_results_s2 import ALPHA, B, SEED, bh, boot_cluster, boot_query, ci, f4, fci, fd, fp, holm, write  # noqa: E402
from utils.build_results_s4 import (  # noqa: E402
    AMENDMENT_EXCLUDED as S4_EXCLUDED, ARMS as S4_ARMS, CORPUS_JSON, FEW_CLUSTERS, FLOOR, LAYERS, SIDECAR,
    duplicated,
)
from utils.build_results_s5 import ARMS as S5_ARMS  # noqa: E402
from utils.build_results_s6 import BASE7, cell, cluster_weights, discrimination, mean_draws, test_p  # noqa: E402
from utils.pantry_flags import text_flags  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402

DATA = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
STACKED_JSON = DATA / "OE_stacked_texto.json"
SCHEMA_JSON = DATA / "OE_concept_schema.json"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S7"
FIGS = OUT / "figures"
GENERATOR = "src/utils/build_results_s7.py"

STACKED, SINGLE, L2W, IDENT = "stacked_texto", "single_texto", "single_l2_texto", "texto"

#: (run directory, short name, oracle, kind): the fifteen S4 arms, then the three S5 structured arms.
ARMS = [(d, s, o, "derived" if dv else "base") for d, s, o, dv in S4_ARMS] + [
    (d, s, o, "structured") for d, s, o, st in S5_ARMS if st
]
DIR = {s: d for d, s, _, _ in ARMS}
ORACLE = {s for _, s, o, _ in ARMS if o}
STRUCTURED = [s for _, s, _, k in ARMS if k == "structured"]
TWIN = {"bm25_unigram_params": "bm25_unigram", "tfidf_phrases_replace": "bm25_unigram", "rrf_params": "rrf",
        "oracleparams": "rules_valuenorm"}

L1_TYPES = set(LAYERS["L1"])
#: S2's five stacked runs, archived by work item 2 and re-run here (work item 4).
S2_RERUN = ["bm25_unigram", "bm25_unigram_params", "bge_m3_colbert", "rules_faithful", "rules_valuenorm"]
S2_COMMIT = "31bf1a1"
#: The retrieval path, for work item 4's classes (A1 j).
SHARED_PATH = ["src/retrieve.ipynb", "src/metrics.ipynb", "src/utils/run_context.py", "src/utils/corpus_prep.py",
               "src/utils/feature_prep.py", "src/utils/text_processing.py", "src/utils/evaluation.py"]
ARM_PATH = {
    "bm25_unigram": ["src/retrievers/bm25_unigram.py", "src/index_builders/bm25_unigram.py"],
    "bm25_unigram_params": ["src/retrievers/bm25_unigram_params.py", "src/retrievers/bm25_unigram.py",
                            "src/index_builders/bm25_unigram.py"],
    "bge_m3_colbert": ["src/retrievers/bge_m3_colbert.py", "src/index_builders/bge_m3_colbert.py"],
    "rules_faithful": ["src/retrievers/structured_pipeline.py", "src/index_builders/structured_pipeline_rules.py",
                       "src/utils/structured_stages.py", "src/retrievers/dense_e5.py"],
    "rules_valuenorm": ["src/retrievers/structured_pipeline.py", "src/index_builders/structured_pipeline_rules.py",
                        "src/utils/structured_stages.py", "src/retrievers/dense_e5.py"],
}

VARIANTS = ("tf", "run", "clean", "adj")
VARIANT_LABEL = {"tf": "tie-free", "run": "as run", "clean": "tie-free, D-004 clean subset",
                 "adj": "tie-free, W3 adjusted"}

TESTS = [
    # id, hypothesis, what, kind, confirmatory arms (S2 read their stacked runs)
    ("W1", "H1 gap widens", "Δ_stk − Δ_id > 0, Δ = parent − item", "w1"),
    ("W2", "H1 discrimination", "(D_id − D_stk) − (parent_id − parent_stk) > 0", "w2"),
    ("W3", "E5 sibling density", "slope of the item loss ℓ on log₂ family size > 0", "w3"),
]
CONFIRMATORY = {"bm25_unigram", "bm25_unigram_params", "bge_m3_colbert"}


# --------------------------------------------------------------------------- inputs


def run_dir(queryset: str, short: str) -> Path:
    return RUNS / queryset / DIR[short]


def meta(queryset: str, short: str) -> dict:
    return json.loads((run_dir(queryset, short) / "run_meta.json").read_text(encoding="utf-8"))


def perquery(queryset: str, short: str) -> pd.DataFrame:
    return pd.read_parquet(run_dir(queryset, short) / "results_perquery.parquet")


def iter_top100(path: Path):
    with gzip.open(path / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def parent_of() -> dict[str, str]:
    return {r["item_key"]: r["parent_key"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}


def tie_table(path: Path, keep: set[str], parents: dict[str, str]) -> pd.DataFrame:
    """Tie-free item and parent hit, and the rank-1 tied set, of every query in `keep` (A1 i)."""
    rows = []
    for r in iter_top100(path):
        key = str(r["query_item_key"])
        if key not in keep:
            continue
        c = r["candidates"]
        s1 = float(c[0]["score"])
        tied = [str(x["index_item_key"]) for x in c if float(x["score"]) == s1]
        gold, gpar = str(r["gold_item_key"]), str(r["gold_parent_key"])
        rows.append({"key": key, "item_tf": (1.0 / len(tied)) if gold in tied else 0.0,
                     "parent_tf": sum(parents[t] == gpar for t in tied) / len(tied),
                     "truncated": len(tied) == len(c), "top1": str(c[0]["index_item_key"]),
                     "tied": frozenset(tied)})
    frame = pd.DataFrame(rows).set_index("key")
    missing = keep - set(frame.index)
    if missing:
        raise KeyError(f"{path}: {len(missing)} keys absent from the top-100 file")
    return frame


def leaf_density() -> tuple[dict[str, int], dict[str, int]]:
    """Family size per concept, and per leaf the count of same-concept leaves one label apart (A1 b, g)."""
    schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    by_concept: dict[str, list[str]] = defaultdict(list)
    for r in corpus:
        by_concept[r["parent_key"]].append(r["item_key"])
    size = {c: len(keys) for c, keys in by_concept.items()}
    for c, keys in by_concept.items():
        if schema[c]["num_items"] != len(keys):
            raise ValueError(f"{c}: schema num_items differs from the indexed leaves")
        n_axes = len(schema[c]["axes"])
        if any(len(k) - len(c) + 1 != n_axes for k in keys):
            raise ValueError(f"{c}: a leaf's label sequence is not one character per axis")
    one_apart: dict[str, int] = {}
    for c, keys in by_concept.items():
        stem = len(c) - 1
        labels = [k[stem:] for k in keys]
        n_axes = len(labels[0]) if labels else 0
        masks: dict[tuple[int, str], int] = defaultdict(int)
        for lab in labels:
            for i in range(n_axes):
                masks[(i, lab[:i] + "*" + lab[i + 1:])] += 1
        for k, lab in zip(keys, labels):
            one_apart[k] = sum(masks[(i, lab[:i] + "*" + lab[i + 1:])] - 1 for i in range(n_axes))
    return size, one_apart


def stacked_features(dev_keys: set[str], size: dict[str, int], one_apart: dict[str, int]) -> pd.DataFrame:
    corpus = {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}
    rows = []
    for r in json.loads(STACKED_JSON.read_text(encoding="utf-8")):
        key = r["item_key"]
        if key not in dev_keys:
            continue
        flags = text_flags(r["text"], corpus[r["gold_item_key"]])
        types = list(dict.fromkeys(r["texto_modification_types"]))
        rows.append({"q": key, "dose": int(r["texto_modification_count"]), "dose_field": int(r["modification_count"]),
                     "types": types, "l1": float(bool(L1_TYPES & set(types))),
                     "fam": size[r["parent_key"]], "log2fam": float(np.log2(size[r["parent_key"]])),
                     "one_apart": one_apart[r["gold_item_key"]],
                     "flagged": bool(flags["doubled"] or flags["topo"]),
                     "doubled": bool(flags["doubled"]), "topo": bool(flags["topo"])})
    out = pd.DataFrame(rows).set_index("q")
    if (out["dose"] != out["types"].map(len)).any():
        raise ValueError("texto_modification_count disagrees with its own type list")
    return out


def paired(short: str, queryset: str, dup: set[str], parents: dict[str, str],
           excluded: dict[str, dict] | None = None) -> pd.DataFrame:
    """One row per dev query of `queryset`: modified and identity, as run and tie-free, both levels (S4/S6)."""
    excluded = excluded or {}
    mod = perquery(queryset, short)
    ident = perquery(IDENT, short).set_index("query_item_key")
    frame = pd.DataFrame({
        "q": mod["query_item_key"].astype(str), "gold": mod["gold_item_key"].astype(str),
        "concept": mod["gold_parent_key"].astype(str), "subchapter": mod["subchapter"].astype(str),
        "tercile": mod["family_tercile"].astype(str),
        "item_mod": mod["item_acc1"].astype(float), "parent_mod": mod["parent_acc1"].astype(float),
    })
    missing = set(frame["gold"]) - set(ident.index)
    if missing:
        raise KeyError(f"{short}/{queryset}: {len(missing)} golds have no identity result")
    frame["item_id"] = frame["gold"].map(ident["item_acc1"]).astype(float)
    frame["parent_id"] = frame["gold"].map(ident["parent_acc1"]).astype(float)
    t_mod = tie_table(run_dir(queryset, short), set(frame["q"]), parents)
    t_id = tie_table(run_dir(IDENT, short), set(frame["gold"]), parents)
    for level in ("item", "parent"):
        frame[f"{level}_mod_tf"] = frame["q"].map(t_mod[f"{level}_tf"]).astype(float)
        frame[f"{level}_id_tf"] = frame["gold"].map(t_id[f"{level}_tf"]).astype(float)
    frame["trunc_mod"] = frame["q"].map(t_mod["truncated"]).astype(bool)
    frame["trunc_id"] = frame["gold"].map(t_id["truncated"]).astype(bool)
    for side in ("mod", "id"):
        for level in ("item", "parent"):
            run, tf = frame[f"{level}_{side}"], frame[f"{level}_{side}_tf"]
            if (((run == 1) & (tf == 0)) | ((run == 0) & (tf == 1))).any():
                raise ValueError(f"{short}/{queryset}/{level}_{side}: tie-free and as-run disagree on a certainty")
    frame["item_scored"] = ~frame["gold"].isin(dup) & ~frame["q"].map(
        lambda k: "item" in excluded.get(k, {}).get("levels", ()))
    frame["parent_scored"] = ~frame["q"].map(lambda k: "parent" in excluded.get(k, {}).get("levels", ()))
    return frame


def columns(frame: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Hit columns for a variant: tie-free, as run, tie-free on the clean subset, or tie-free (W3 adjusted)."""
    f = frame.copy()
    if variant != "run":
        for side in ("mod", "id"):
            for level in ("item", "parent"):
                f[f"{level}_{side}"] = f[f"{level}_{side}_tf"]
    if variant == "clean":
        f = f[~f["flagged"]]
    return f


def item(f: pd.DataFrame) -> pd.DataFrame:
    return f[f["item_scored"]]


def parent(f: pd.DataFrame) -> pd.DataFrame:
    return f[f["parent_scored"]]


def scored_cell(frame: pd.DataFrame, level: str, label: str) -> dict | None:
    """S6's cell, or None when the stratum has no query scored at this level."""
    f = item(frame) if level == "item" else parent(frame)
    return cell(frame, level, label) if len(f) else None


def nconc(f: pd.DataFrame) -> int:
    return int(f["concept"].nunique())


def nexcl(f: pd.DataFrame) -> int:
    return int((~f["item_scored"]).sum())


# --------------------------------------------------------------------------- statistics


def ols_draws(f: pd.DataFrame, xcols: list[str], label: str, unit: str = "concept") -> dict:
    """OLS of the item loss on [1, xcols] from per-cluster sums; point estimate and B draws (A1 c)."""
    y = (f["item_id"] - f["item_mod"]).to_numpy(float)
    X = np.column_stack([np.ones(len(f))] + [f[c].to_numpy(float) for c in xcols])
    clusters = f["concept"].to_numpy() if unit == "concept" else f["q"].to_numpy()
    k = X.shape[1]
    frame = pd.DataFrame({"_c": clusters})
    order = frame.groupby("_c", sort=True).indices
    labels = sorted(order)
    xtx = np.stack([X[order[g]].T @ X[order[g]] for g in labels])
    xty = np.stack([X[order[g]].T @ y[order[g]] for g in labels])
    point = np.linalg.lstsq(xtx.sum(0), xty.sum(0), rcond=None)[0]
    got, weights = cluster_weights(clusters, label)
    if list(got) != labels:
        raise ValueError(f"{label}: cluster order differs from the bootstrap's")
    draws = np.full((B, k), np.nan)
    for lo in range(0, B, 1000):
        w = weights[lo:lo + 1000]
        A = np.einsum("bg,gij->bij", w, xtx)
        v = np.einsum("bg,gi->bi", w, xty)
        ok = np.abs(np.linalg.det(A)) > 1e-9
        draws[lo:lo + 1000][ok] = np.linalg.solve(A[ok], v[ok][..., None])[..., 0]
    return {"point": point, "draws": draws, "names": ["intercept", *xcols], "n": len(f),
            "clusters": len(labels)}


def slope_ci(fit: dict) -> tuple[float, float]:
    """Percentile interval of the first regressor's coefficient, over the defined draws."""
    d = fit["draws"][:, 1]
    return ci(d[np.isfinite(d)])


def unitize(f: pd.DataFrame, unit: str) -> pd.DataFrame:
    return f if unit == "concept" else f.assign(concept=f["q"])


def adjusted_x(f: pd.DataFrame) -> pd.DataFrame:
    """A1 d: dose centred on the item-scored mean (L1 present dropped, A2)."""
    centre = item(f)["dose"].mean()
    return f.assign(dose_c=f["dose"] - centre)


#: A2: "L1 present" is 1 for every item-scored dev stacked query, collinear with the intercept, so it is dropped;
#: the adjusted refit carries the dose alone. `write_density` prints the constancy it rests on.
W3_ADJ = ["log2fam", "dose_c"]


def run_test(kind: str, short: str, F: dict, variant: str, unit: str = "concept") -> dict:
    f = unitize(columns(F[short], variant), unit)
    lab = f"s7|{kind}|{short}|{variant}" + ("" if unit == "concept" else "|q")
    g = item(f)
    if kind == "w1":
        v = ((g["parent_mod"] - g["item_mod"]) - (g["parent_id"] - g["item_id"])).to_numpy(float)
        est, draws = mean_draws(g, v, lab)
    elif kind == "w2":
        est, draws = discrimination(g, lab)
    elif kind == "w3":
        x = W3_ADJ if variant == "adj" else ["log2fam"]
        fit = ols_draws(adjusted_x(g) if variant == "adj" else g, x, lab, unit="concept")
        est, draws = float(fit["point"][1]), fit["draws"][:, 1]
    else:
        raise ValueError(kind)
    return {"est": est, "draws": draws, "concepts": nconc(item(columns(F[short], variant))),
            "n": len(g), "excluded": nexcl(f)}


def read(r: dict) -> str:
    lo, hi = r["c"]
    if lo > 0 and r["holm"] < ALPHA:
        return "supported"
    if hi < 0 and r["holm"] < ALPHA:
        return "contradicted"
    return "not supported"


def evaluate(F: dict, floors: dict) -> list[dict]:
    results = []
    for tid, hyp, what, kind in TESTS:
        for short in BASE7:
            row = {"id": tid, "hyp": hyp, "what": what, "arm": short, "blind": short not in CONFIRMATORY,
                   "floor": floors[short] < FLOOR}
            for v in VARIANTS:
                vv = "tf" if (v == "adj" and kind != "w3") else v
                r = run_test(kind, short, F, vv if kind != "w3" else v)
                d = r["draws"][np.isfinite(r["draws"])]
                rq = run_test(kind, short, F, vv if kind != "w3" else v, unit="query")["draws"]
                row[v] = {"est": r["est"], "c": ci(d), "q": ci(rq[np.isfinite(rq)]), "p": test_p(r["draws"]),
                          "concepts": r["concepts"], "n": r["n"], "excluded": r["excluded"],
                          "dropped": len(r["draws"]) - len(d)}
            results.append(row)
    for v in VARIANTS:
        ps = [r[v]["p"] for r in results]
        for r, h, q in zip(results, holm(ps), bh(ps)):
            r[v].update(holm=h, bh=q)
            r[v]["reading"] = "not tested" if r["floor"] else read(r[v])
    for r in results:
        r["robust"] = all(r[v]["reading"] == r["tf"]["reading"] for v in ("clean", "adj"))
    return results


# --------------------------------------------------------------------------- formatting


def name(short: str) -> str:
    return f"`{short}`" + (" **oracle**" if short in ORACLE else "")


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S7 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def conc(n: int) -> str:
    return f"{n}" + (" ‡" if n < FEW_CLUSTERS else "")


def population_lines(F: dict, dup: set[str]) -> list[str]:
    f = next(iter(F.values()))
    return [
        f"**Population.** Dev `{STACKED}`: {len(f):,} queries over {nconc(f)} concepts. Item level scores "
        f"{int(f['item_scored'].sum()):,} ({int(f['gold'].isin(dup).sum()):,} D-033 golds excluded) over "
        f"{nconc(item(f))} concepts; parent level scores all {len(f):,}. Each query is paired with the same arm's "
        f"`{IDENT}` result on its own gold (treatment effect on the treated). ‡ marks fewer than {FEW_CLUSTERS} "
        "concepts behind a cell, whose percentile interval under-covers. δ = stacked − identity.", "",
    ]


def stack_stamp() -> str:
    return analysis_stack.stamp()


def sources_block(querysets: list[str], arms: list[str] | None = None, inputs: tuple[Path, ...] = ()) -> list[str]:
    lines = ["", "## Sources", "", "| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
             "|---|---:|---|---|---|---|"]
    for queryset in querysets:
        for _, short, _, _ in ARMS:
            if arms is not None and short not in arms:
                continue
            if not (run_dir(queryset, short) / "run_meta.json").is_file():
                continue
            m = meta(queryset, short)
            lines.append(f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                         f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
                         f"`{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (SIDECAR, STACKED_JSON, *inputs)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals; readings on the concept-clustered "
              "draws (D-030). Split `dev`.", stack_stamp()]
    return lines


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


# --------------------------------------------------------------------------- tables


def headline_stats(F: dict) -> dict:
    out = {}
    for short, frame in F.items():
        s = {}
        for v in ("run", "tf"):
            f = columns(frame, v)
            for level in ("item", "parent"):
                s[(level, v)] = cell(f, level, f"s7|T1|{short}|{v}")
            g = item(f)
            s[("gap", v)] = (float((g["parent_id"] - g["item_id"]).mean()), float((g["parent_mod"] - g["item_mod"]).mean()))
            s[("D", v)] = (float(g["item_id"].sum() / g["parent_id"].sum()) if g["parent_id"].sum() else float("nan"),
                           float(g["item_mod"].sum() / g["parent_mod"].sum()) if g["parent_mod"].sum() else float("nan"))
            s[("rpwi", v)] = float((g["parent_mod"] - g["item_mod"]).mean())
        out[short] = s
    return out


def write_headline(F: dict, stats: dict, floors: dict, dup: set[str]) -> None:
    lines = header("T1: the stacked headline, item and parent level (dev)", [
        "Eighteen arms on `stacked_texto` (`all_combined`), each paired with its own identity on the same golds.",
        "Tie-free is the reading (D-028 note); as run beside it. The identity column is each arm's ceiling on",
        "these leaves (D-032): **headroom** is stacked ÷ identity; **retention** is P(hit stacked | hit identity).",
    ])
    lines += population_lines(F, dup)
    lines += ["**Δ** = parent − item (the collapse gap); **D** = Σ item ÷ Σ parent (conditional discrimination); "
              "**right parent, wrong item** = mean(parent − item) on the stacked side. All three on the item-scored "
              f"queries. **Floor**: identity item Acc@1 (tie-free, treated leaves) below {FLOOR:.2f} (S4); "
              "floor arms are reported, never read.", ""]
    for level in ("item", "parent"):
        lines += [f"## {level.capitalize()} level", "",
                  "| arm | kind | n scored | n excluded | concepts | identity | stacked | δ | CI (query) | CI (concept) | "
                  "headroom | retention | CI (concept) | identity, as run | stacked, as run | δ, as run | CI (concept), as run |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|---:|---|"]
        for d, short, _, kind in ARMS:
            t, a = stats[short][(level, "tf")], stats[short][(level, "run")]
            head = t["mod"] / t["id"] if t["id"] else float("nan")
            fl = " (floor)" if level == "item" and floors[short] < FLOOR else ""
            lines.append(
                f"| {name(short)}{fl} | {kind} | {t['n']:,} | {t['excluded']:,} | {conc(t['concepts'])} | {f4(t['id'])} | "
                f"{f4(t['mod'])} | {fd(t['delta'])} | {fci(t['q'], True)} | {fci(t['c'], True)} | {f4(head)} | "
                f"{f4(t['retention'])} | {fci(t['ret_c'])} | {f4(a['id'])} | {f4(a['mod'])} | {fd(a['delta'])} | "
                f"{fci(a['c'], True)} |")
        lines.append("")
    lines += ["## Collapse quantities (item-scored queries)", "",
              "| arm | Δ identity | Δ stacked | D identity | D stacked | right parent, wrong item | "
              "Δ stacked, as run | D stacked, as run |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _, short, _, _ in ARMS:
        g, d, r = stats[short][("gap", "tf")], stats[short][("D", "tf")], stats[short][("rpwi", "tf")]
        ga, da = stats[short][("gap", "run")], stats[short][("D", "run")]
        lines.append(f"| {name(short)} | {f4(g[0])} | {f4(g[1])} | {f4(d[0])} | {f4(d[1])} | {f4(r)} | "
                     f"{f4(ga[1])} | {f4(da[1])} |")
    trunc = {s: (int(F[s]["trunc_mod"].sum()), int(F[s]["trunc_id"].sum())) for s in F}
    lines += ["", "## Rank-1 tied sets that fill the whole top-100", "",
              "Such a tied set is truncated, so its tie-free value is an upper bound.", "",
              "| arm | stacked | identity |", "|---|---:|---:|"]
    lines += [f"| {name(s)} | {a:,} | {b:,} |" for s, (a, b) in trunc.items()]
    lines += sources_block([STACKED, IDENT])
    write(OUT / "headline.md", lines)


def write_single_reference(F: dict, S: dict, W: dict, dup: set[str]) -> None:
    lines = header("T2: the single-edit reference (dev, item level, tie-free)", [
        "Each arm's stacked δ beside its pooled `single_texto` δ (S4's population: D-033 golds and the P7 query",
        "excluded at item level) and its L2w δ (`single_l2_texto`, S6's). The three sets reach different leaves:",
        "this is **between-population**, printed and never read as a contrast (design).",
    ])
    lines += ["The stacked cell is T1's: the same bootstrap draws, so the same interval (A6).", "",
              "| arm | stacked n | n excluded | stacked δ | CI (query) | CI (concept) | stacked retention | `single_texto` n | "
              "n excluded | δ | CI (query) | CI (concept) | retention | L2w n | n excluded | δ | CI (query) | CI (concept) | "
              "retention |",
              "|---|---:|---:|---:|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|---|---:|"]
    for _, short, _, _ in ARMS:
        parts = []
        for frame in (F[short], S[short], W.get(short)):
            if frame is None:
                parts.append("— | — | — | — | — | —")
                continue
            qs = frame["queryset"].iloc[0]
            label = f"s7|T1|{short}|tf" if qs == STACKED else f"s7|T2|{short}|{qs}"
            c = cell(columns(frame, "tf"), "item", label)
            parts.append(f"{c['n']:,} | {c['excluded']:,} | {fd(c['delta'])} | {fci(c['q'], True)} | "
                         f"{fci(c['c'], True)} ({conc(c['concepts'])}) | {f4(c['retention'])}")
        lines.append(f"| {name(short)} | " + " | ".join(parts) + " |")
    lines += sources_block([STACKED, SINGLE, L2W, IDENT])
    write(OUT / "single_reference.md", lines)


def strata_table(F: dict, key: str, values: list, title: str, file: str, how: list[str], dup: set[str]) -> None:
    lines = header(title, how)
    lines += population_lines(F, dup)
    for level in ("item", "parent"):
        lines += [f"## {level.capitalize()} level", "",
                  "| arm | stratum | n | n scored | n excluded | concepts | identity | stacked | δ | CI (query) | "
                  "CI (concept) | δ, as run |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|"]
        for _, short, _, _ in ARMS:
            for val in values:
                sub = F[short][F[short][key] == val]
                if sub.empty:
                    continue
                t = scored_cell(columns(sub, "tf"), level, f"s7|{file}|{short}|{val}")
                a = scored_cell(columns(sub, "run"), level, f"s7|{file}|{short}|{val}")
                if t is None:
                    continue
                lines.append(f"| {name(short)} | {val} | {len(sub):,} | {t['n']:,} | {t['excluded']:,} | "
                             f"{conc(t['concepts'])} | {f4(t['id'])} | {f4(t['mod'])} | {fd(t['delta'])} | "
                             f"{fci(t['q'], True)} | {fci(t['c'], True)} | {fd(a['delta'])} |")
        lines.append("")
    lines += sources_block([STACKED, IDENT])
    write(OUT / file, lines)


def write_density(F: dict, results: list[dict], dup: set[str]) -> None:
    lines = header("T4: sibling density (dev, item level, tie-free)", [
        "Family size is the number of indexed leaves in the gold's concept (A1 b). W3 regresses the item **loss**",
        "ℓ = identity − stacked on log₂ family size (A1 a), so a positive slope means larger families lose more.",
        "Its adjusted refit adds the dose (`texto_modification_count`, centred; A1 d). The design's L1-present",
        "indicator is constant on this population and is dropped (A2); its share is printed below.",
    ])
    lines += population_lines(F, dup)
    f0 = item(next(iter(F.values())))
    sizes = f0.groupby("concept")["fam"].first()
    lines += [f"Family sizes behind the item-scored queries: {len(sizes)} concepts, from {int(sizes.min()):,} to "
              f"{int(sizes.max()):,} leaves; correlation of log₂ family size with dose "
              f"{f4(f0[['log2fam', 'dose']].corr().iloc[0, 1])} (query level). L1 present in "
              f"{int(f0['l1'].sum()):,} of {len(f0):,} item-scored queries, so it cannot enter the refit (A2).", ""]
    lines += ["## W3 slopes", "",
              "| arm | n scored | n excluded | concepts | slope, unadjusted | CI (query) | CI (concept) | reading | slope, adjusted | "
              "CI (query) | CI (concept) | dose coef. | reading, adjusted | within OEB slope | n scored | n excluded | "
              "CI (query) | CI (concept) | OEB concepts |",
              "|---|---:|---:|---:|---:|---|---|---|---:|---|---|---:|---|---:|---:|---:|---|---|---:|"]
    for r in [r for r in results if r["id"] == "W3"]:
        short = r["arm"]
        g = item(columns(F[short], "tf"))
        adj = ols_draws(adjusted_x(g), W3_ADJ, f"s7|T4|{short}|adj")
        oeb = g[g["subchapter"] == "OEB"]
        fo = ols_draws(oeb, ["log2fam"], f"s7|T4|{short}|OEB")
        foq = ols_draws(oeb, ["log2fam"], f"s7|T4|{short}|OEB|q", unit="query")
        oeb_all = F[short][F[short]["subchapter"] == "OEB"]
        lines.append(
            f"| {name(short)} | {r['tf']['n']:,} | {r['tf']['excluded']:,} | {conc(r['tf']['concepts'])} | "
            f"{fd(r['tf']['est'])} | "
            f"{fci(r['tf']['q'], True)} | {fci(r['tf']['c'], True)} | "
            f"{r['tf']['reading']} | {fd(r['adj']['est'])} | {fci(r['adj']['q'], True)} | {fci(r['adj']['c'], True)} | "
            f"{fd(adj['point'][2])} | {r['adj']['reading']} | {fd(fo['point'][1])} | {len(oeb):,} | "
            f"{nexcl(oeb_all):,} | {fci(slope_ci(foq), True)} | {fci(slope_ci(fo), True)} | {conc(fo['clusters'])} |")
    lines += ["", "The within-OEB slope is descriptive (design): OEB holds the largest families, so family size and "
              "subchapter are confounded across the full population.", ""]
    lines += ["## Leverage (descriptive, A4)", "",
              "A concept interval can exclude 0 while the reading is *not supported*: the raw two-sided p agrees with "
              "the interval, and Holm's correction across the registered tests is what separates them (T8, A6). The "
              "draws at or below 0 are printed as description, not as the reason. Beside them, the slope outside OEB "
              "(post hoc; read it beside the within-OEB slope above, which the design fixed) and the range of the slope "
              "with one concept left out.", "",
              "| arm | draws ≤ 0 (of B) | largest family in those draws, max | slope outside OEB | n scored | n excluded | "
              "CI (query) | CI (concept) | concepts | leave-one-out min | left out | leave-one-out max | left out |",
              "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---|"]
    for short in BASE7:
        g = item(columns(F[short], "tf"))
        fit = ols_draws(g, ["log2fam"], f"s7|w3|{short}|tf")
        d = fit["draws"][:, 1]
        labels, weights = cluster_weights(g["concept"].to_numpy(), f"s7|w3|{short}|tf")
        fam = np.array([int(g.loc[g["concept"] == c, "fam"].iloc[0]) for c in labels])
        neg = np.where(d <= 0)[0]
        drawn_max = max((int(fam[weights[i] > 0].max()) for i in neg), default=0)
        out = g[g["subchapter"] != "OEB"]
        fo = ols_draws(out, ["log2fam"], f"s7|T4|{short}|notOEB")
        foq = ols_draws(out, ["log2fam"], f"s7|T4|{short}|notOEB|q", unit="query")
        out_all = F[short][F[short]["subchapter"] != "OEB"]
        loo = []
        for c in labels:
            sub_g = g[g["concept"] != c]
            X = np.column_stack([np.ones(len(sub_g)), sub_g["log2fam"].to_numpy(float)])
            y = (sub_g["item_id"] - sub_g["item_mod"]).to_numpy(float)
            loo.append((float(np.linalg.lstsq(X, y, rcond=None)[0][1]), c))
        lo, hi = min(loo), max(loo)
        lines.append(f"| {name(short)} | {len(neg):,} | " + (f"{drawn_max:,}" if len(neg) else "—")
                     + f" | {fd(fo['point'][1])} | {len(out):,} | {nexcl(out_all):,} | {fci(slope_ci(foq), True)} | "
                     f"{fci(slope_ci(fo), True)} | {conc(fo['clusters'])} | {fd(lo[0])} | `{lo[1]}` | {fd(hi[0])} | `{hi[1]}` |")
    sizes_desc = sorted({int(v) for v in sizes}, reverse=True)
    lines += ["", "Family sizes behind the item-scored queries, largest first: "
              + ", ".join(f"{v:,}" for v in sizes_desc) + ".", ""]
    edges = np.unique(np.quantile(f0["one_apart"], np.linspace(0, 1, 5)))
    lines += ["## One-axis siblings of the gold (descriptive, A1 g)", "",
              "Bins at the quartiles of the item-scored queries' one-axis sibling count: "
              + ", ".join(f"{int(e):,}" for e in edges) + ". ℓ slope on log₂(1 + count), concept-clustered.", "",
              "| arm | bin | n scored | n excluded | concepts | mean count | identity | stacked | δ | CI (query) | "
              "CI (concept) |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    slopes = []
    for short in BASE7:
        fa = columns(F[short], "tf")
        g = item(fa).assign(l2h=lambda x: np.log2(1 + x["one_apart"]))
        idx_all = np.clip(np.searchsorted(edges, fa["one_apart"], side="right") - 1, 0, max(len(edges) - 2, 0))
        for b in range(max(len(edges) - 1, 1)):
            sub_all = fa[idx_all == b]
            sub = item(sub_all)
            if sub.empty:
                continue
            c = cell(sub_all, "item", f"s7|T4|{short}|onebin{b + 1}")
            lines.append(f"| {name(short)} | {b + 1} | {len(sub):,} | {c['excluded']:,} | {conc(nconc(sub))} | "
                         f"{f4(sub['one_apart'].mean())} | {f4(sub['item_id'].mean())} | {f4(sub['item_mod'].mean())} | "
                         f"{fd((sub['item_mod'] - sub['item_id']).mean())} | {fci(c['q'], True)} | {fci(c['c'], True)} |")
        fit = ols_draws(g, ["l2h"], f"s7|T4|{short}|h1")
        fitq = ols_draws(g, ["l2h"], f"s7|T4|{short}|h1|q", unit="query")
        slopes.append((short, len(g), nexcl(fa), fit["clusters"], fit["point"][1], slope_ci(fitq), slope_ci(fit)))
    lines += ["", "| arm | n scored | n excluded | concepts | ℓ slope on log₂(1 + one-axis siblings) | CI (query) | "
              "CI (concept) |", "|---|---:|---:|---:|---:|---|---|"]
    lines += [f"| {name(s)} | {n:,} | {x:,} | {conc(k)} | {fd(b)} | {fci(q, True)} | {fci(c, True)} |"
              for s, n, x, k, b, q, c in slopes]
    lines += sources_block([STACKED, IDENT], arms=BASE7, inputs=(SCHEMA_JSON, CORPUS_JSON))
    write(OUT / "density.md", lines)


def write_dose(F: dict, dup: set[str]) -> None:
    lines = header("T5: δ by dose — descriptive, not H4 (dev, tie-free)", [
        "The dose is `texto_modification_count`, the modifications visible in the TEXTO (D-025 note);",
        "`modification_count`, which overstates it, is the second block. Dose varies between concepts, so",
        "each row compares different families: this is the plan's exploratory regression on the stacked set,",
        "printed and never read as H4. **E2 cannot identify interactions** (no `reorder`, `template_paraphrase`",
        "everywhere); H4 is S8's, on the nested ladder (design).",
    ])
    lines += population_lines(F, dup)
    for field, label in (("dose", "`texto_modification_count`"), ("dose_field", "`modification_count`")):
        lines += [f"## By {label}", "",
                  "| arm | dose | n | n scored | n excluded | concepts | identity | stacked | δ | CI (query) | CI (concept) |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
        values = sorted(next(iter(F.values()))[field].unique())
        for _, short, _, _ in ARMS:
            for val in values:
                sub = F[short][F[short][field] == val]
                t = scored_cell(columns(sub, "tf"), "item", f"s7|T5|{field}|{short}|{val}")
                if t is None:
                    continue
                lines.append(f"| {name(short)} | {val} | {len(sub):,} | {t['n']:,} | {t['excluded']:,} | "
                             f"{conc(t['concepts'])} | {f4(t['id'])} | {f4(t['mod'])} | {fd(t['delta'])} | "
                             f"{fci(t['q'], True)} | {fci(t['c'], True)} |")
        lines.append("")
    lines += sources_block([STACKED, IDENT])
    write(OUT / "dose.md", lines)


def write_presence(F: dict, dup: set[str]) -> None:
    lines = header("T6: δ by whether the mix contains a type — descriptive (dev, item level, tie-free)", [
        "Strata overlap (a query carries several types) and each is confounded with the rest of its mix and",
        "with its concepts; no row estimates a type's effect. L1 types and `synonym_label` first (S6 finding 5).",
    ])
    lines += population_lines(F, dup)
    order = LAYERS["L1"] + LAYERS["L2"] + LAYERS["L3"]
    lines += ["| arm | type | n with | n excluded | concepts | δ with | CI (query) | CI (concept) | n without | n excluded | "
              "concepts | δ without | CI (query) | CI (concept) |",
              "|---|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|---|"]
    for _, short, _, _ in ARMS:
        f = columns(F[short], "tf")
        for t in order:
            has = f["types"].map(lambda ts, t=t: t in ts)
            if not has.any():
                continue
            w = scored_cell(f[has], "item", f"s7|T6|{short}|{t}|with")
            o = scored_cell(f[~has], "item", f"s7|T6|{short}|{t}|without")
            if w is None:
                continue
            n_without = int((~has).sum())
            lines.append(f"| {name(short)} | `{t}` | {w['n']:,} | {w['excluded']:,} | {conc(w['concepts'])} | "
                         f"{fd(w['delta'])} | {fci(w['q'], True)} | {fci(w['c'], True)} | "
                         + (f"{o['n']:,} | {o['excluded']:,} | {conc(o['concepts'])} | {fd(o['delta'])} | "
                            f"{fci(o['q'], True)} | {fci(o['c'], True)} |" if o else f"0 | {n_without:,} | 0 | — | — | — |"))
    absent = [t for t in order if not next(iter(F.values()))["types"].map(lambda ts, t=t: t in ts).any()]
    lines += ["", "Types in no dev stacked query: " + (", ".join(f"`{t}`" for t in absent) or "none") + "."]
    lines += sources_block([STACKED, IDENT])
    write(OUT / "presence.md", lines)


def write_d004(F: dict, results: list[dict]) -> None:
    f = next(iter(F.values()))
    lines = header("T7: D-004 sensitivity (dev)", [
        "Flagged: an immediately doubled token, or the *topografía* drift (S3's detector). Every W-reading is",
        "recomputed without the flagged queries; a reading that changes category is **not robust**, and the full",
        "population's reading stands (D-004 keeps the artefacts in).",
    ])
    lines += ["| queries | doubled | topo | flagged | flagged, item-scored | concepts with a flag |", "|---:|---:|---:|---:|---:|---:|",
              f"| {len(f):,} | {int(f['doubled'].sum()):,} | {int(f['topo'].sum()):,} | {int(f['flagged'].sum()):,} | "
              f"{int(item(f)['flagged'].sum()):,} | {int(f[f['flagged']]['concept'].nunique())} |", "",
              "| test | arm | n scored, full | n excluded, full | estimate, full | CI (query) | CI (concept) | reading, full | "
              "estimate, clean | CI (query) | CI (concept) | n scored, clean | n excluded, clean | reading, clean | changes |",
              "|---|---|---:|---:|---:|---|---|---|---:|---|---|---:|---:|---|---|"]
    for r in results:
        t, c = r["tf"], r["clean"]
        lines.append(f"| {r['id']} | {name(r['arm'])} | {t['n']:,} | {t['excluded']:,} | {fd(t['est'])} | "
                     f"{fci(t['q'], True)} | {fci(t['c'], True)} | {t['reading']} | "
                     f"{fd(c['est'])} | {fci(c['q'], True)} | {fci(c['c'], True)} | {c['n']:,} | {c['excluded']:,} | "
                     f"{c['reading']} | "
                     f"{'**yes**' if c['reading'] != t['reading'] else 'no'} |")
    lines += sources_block([STACKED, IDENT], arms=BASE7)
    write(OUT / "d004.md", lines)


def write_predictions(results: list[dict], floors: dict) -> None:
    lines = header("T8: the registered predictions W1–W3 (dev)", [
        f"Read on the concept-clustered interval (D-030), Holm–Bonferroni across the {len(results)} tests, BH beside.",
        "**Supported** when the interval lies above 0 and Holm p < α; **contradicted** in the mirror case;",
        "**not supported** otherwise (S4's rule). Tie-free is primary; as run, the D-004 clean subset and the",
        "W3-adjusted set (dose only, A2) each form their own Holm family (A1 d). A reading whose category differs between",
        "tie-free and clean, or tie-free and adjusted, is **not robust**; the tie-free reading stands.",
    ])
    lines += [f"α = {ALPHA}. W3's estimate is the slope of the item loss on log₂ family size (A1 a). **CI (query)** "
              "resamples queries; it is printed, never read. **Blind**: no earlier sprint printed these arms' stacked "
              "results; **confirmatory**: S2 did.", "",
              "**Floor re-check, tie-free, treated leaves**: " + ", ".join(f"{name(s)} {f4(floors[s])}" for s in BASE7)
              + ". " + ("Below the floor, read *not tested*: " + ", ".join(name(s) for s in BASE7 if floors[s] < FLOOR)
                        if any(floors[s] < FLOOR for s in BASE7) else "None of the seven is below the floor.") + "", "",
              "| test | hypothesis | blind | arm | concepts | n scored (excluded) | estimate | CI (query) | CI (concept) | p | "
              "Holm p | BH p | reading | as run | CI (concept), as run | reading, as run | reading, clean | reading, adjusted | robust |",
              "|---|---|---|---|---:|---|---:|---|---|---:|---:|---:|---|---:|---|---|---|---|---|"]
    for r in results:
        t, a = r["tf"], r["run"]
        lines.append(
            f"| {r['id']} | {r['hyp']}: {r['what']} | {'blind' if r['blind'] else 'confirmatory'} | {name(r['arm'])} | "
            f"{conc(t['concepts'])} | {t['n']:,} ({t['excluded']:,}) | {fd(t['est'])} | {fci(t['q'], True)} | "
            f"{fci(t['c'], True)} | {fp(t['p'])} | {fp(t['holm'])} | {fp(t['bh'])} | **{t['reading']}** | {fd(a['est'])} | "
            f"{fci(a['c'], True)} | {a['reading']} | {r['clean']['reading']} | {r['adj']['reading']} | "
            f"{'yes' if r['robust'] else '**no**'} |")
    lines += sources_block([STACKED, IDENT], arms=BASE7)
    write(OUT / "predictions.md", lines)


def write_regression(parents: dict[str, str]) -> None:
    """Work item 4: rank 1 of each re-run arm against S2's archived run, query by query (A1 j)."""
    lines = header("Work item 4: the five re-run arms against S2's archived stacked runs (dev)", [
        "The texts are unchanged between the two query-set files, so rank 1 should agree except where the code",
        "changed or exact-score ties break differently (A1 j). *Tie*: each run's rank-1 key lies in the other's",
        "rank-1 tied set. Otherwise *code change since S2* when the arm's retrieval path differs between",
        f"`{S2_COMMIT}` and the run's commit, else *unexplained*.",
    ])
    lines += ["| arm | queries | rank 1 agrees | tie | code change since S2 | unexplained | item Acc@1, S2 | item Acc@1, S7 | "
              "retrieval-path files changed |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for short in S2_RERUN:
        old_dir = run_dir_as_of("S2", "OE", STACKED, DIR[short], repo=REPO)
        new_dir = run_dir(STACKED, short)
        new_commit = json.loads((new_dir / "run_meta.json").read_text(encoding="utf-8"))["code_commit"]
        keys = set(pd.read_parquet(new_dir / "results_perquery.parquet")["query_item_key"].astype(str))
        old, new = tie_table(old_dir, keys, parents), tie_table(new_dir, keys, parents)
        if set(old.index) != set(new.index):
            raise ValueError(f"{short}: the archived and new runs cover different queries")
        changed = git("diff", "--name-only", S2_COMMIT, new_commit, "--", *SHARED_PATH, *ARM_PATH[short]).splitlines()
        agree = tie = code = unexplained = 0
        for k in sorted(keys):
            o, n = old.loc[k], new.loc[k]
            if o["top1"] == n["top1"]:
                agree += 1
            elif o["top1"] in n["tied"] and n["top1"] in o["tied"]:
                tie += 1
            elif changed:
                code += 1
            else:
                unexplained += 1
        acc_o = float(pd.read_parquet(old_dir / "results_perquery.parquet")["item_acc1"].mean())
        acc_n = float(pd.read_parquet(new_dir / "results_perquery.parquet")["item_acc1"].mean())
        lines.append(f"| {name(short)} | {len(keys):,} | {agree:,} | {tie:,} | {code:,} | {unexplained:,} | {f4(acc_o)} | "
                     f"{f4(acc_n)} | " + (", ".join(f"`{c}`" for c in changed) or "none") + " |")
    lines += ["", "Item Acc@1 here is as run, on all queries (the runs' own metric), not the item-scored population."]
    lines += ["", "| run | config SHA-256 | code commit | query-set SHA-256 |", "|---|---|---|---|"]
    for short in S2_RERUN:
        for d in (run_dir_as_of("S2", "OE", STACKED, DIR[short], repo=REPO), run_dir(STACKED, short)):
            m = json.loads((d / "run_meta.json").read_text(encoding="utf-8"))
            where = "archive" if "_archive" in d.parts else "live"
            lines.append(f"| `{m['run_id']}` ({where}) | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                         f"`{m['query_set_sha256'][:16]}` |")
    write(OUT / "s2_regression.md", lines)


def write_figures(F: dict, stats: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGS.mkdir(parents=True, exist_ok=True)
    lines = header("Figures 4–5, drafts, and the numbers they plot", [
        "Every plotted value is printed below, computed by the same code as T1–T8. Tie-free; dev.",
    ])
    rows = []
    for _, short, _, _ in ARMS:
        t, p = stats[short][("item", "tf")], stats[short][("parent", "tf")]
        rows.append((short, t["id"], p["id"], t["mod"], p["mod"]))
    fig, ax = plt.subplots(figsize=(7, 6))
    for short, ii, pi, im, pm in rows:
        ax.annotate("", xy=(im, pm), xytext=(ii, pi), arrowprops={"arrowstyle": "->", "color": "grey", "lw": 0.8})
        ax.plot([ii], [pi], "o", color="black", ms=4)
        ax.plot([im], [pm], "o", color="tab:red", ms=4)
        ax.text(im, pm, " " + short, fontsize=6, va="center")
    ax.set_xlabel("item Acc@1 (tie-free)")
    ax.set_ylabel("parent Acc@1 (tie-free)")
    ax.set_title("Fig. 4 — identity (black) → all applicable edits stacked (red)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig4_stacked.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines += ["## Fig. 4 — the stacked collapse (`fig4_stacked.png`)", "",
              "Item level on the item-scored queries, parent level on all.", "",
              "| arm | item, identity | parent, identity | item, stacked | parent, stacked |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {name(s)} | {f4(a)} | {f4(b)} | {f4(c)} | {f4(d)} |" for s, a, b, c, d in rows]

    fig, axes = plt.subplots(2, 4, figsize=(14, 7), sharex=True, sharey=True)
    pts = []
    for ax, short in zip(axes.flat, BASE7):
        g = item(columns(F[short], "tf"))
        per = g.groupby("concept").agg(fam=("fam", "first"), n=("q", "size"),
                                       loss=("item_id", "mean"), mod=("item_mod", "mean"))
        per["loss"] = per["loss"] - per["mod"]
        ax.scatter(np.log2(per["fam"]), per["loss"], s=np.clip(per["n"], 4, 200), alpha=0.6)
        ax.axhline(0, color="grey", lw=0.8)
        ax.set_title(short, fontsize=8)
        pts += [(short, c, int(r["fam"]), int(r["n"]), float(r["loss"])) for c, r in per.iterrows()]
    axes.flat[-1].axis("off")
    for ax in axes[-1]:
        ax.set_xlabel("log₂ family size")
    for ax in axes[:, 0]:
        ax.set_ylabel("item loss ℓ (tie-free)")
    fig.suptitle("Fig. 5 — per-concept loss against family size (marker area ∝ queries)")
    fig.tight_layout()
    fig.savefig(FIGS / "fig5_density.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines += ["", "## Fig. 5 — per-concept loss against family size (`fig5_density.png`)", "",
              "| arm | concept | family size | queries | ℓ |", "|---|---|---:|---:|---:|"]
    lines += [f"| {name(s)} | `{c}` | {fam:,} | {n:,} | {fd(l)} |" for s, c, fam, n, l in pts]
    lines += ["", stack_stamp()]
    write(OUT / "figures.md", lines)


def write_provenance() -> None:
    lines = header("T9: run provenance (dev)", [
        "Every run the S7 tables read. The `stacked_texto` runs are S7's (work item 3); the others are earlier",
        "sprints' runs, read, not re-run. S2's five stacked runs are archived (work item 2, D-047) and read only",
        "by the work-item-4 regression.",
    ])
    lines += ["| query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 | derived from |",
              "|---|---|---:|---|---|---|---|---|"]
    for queryset in (STACKED, IDENT, SINGLE, L2W):
        for _, short, _, _ in ARMS:
            if not (run_dir(queryset, short) / "run_meta.json").is_file():
                continue
            m = meta(queryset, short)
            comps = ", ".join(f"`{c['run_id']}` @ `{c['code_commit'][:7]}`" for c in m.get("components", [])) or "—"
            lines.append(f"| `{queryset}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                         f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
                         f"`{m['query_set_sha256'][:16]}` | {comps} |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (SIDECAR, STACKED_JSON, CORPUS_JSON, SCHEMA_JSON)),
              "", stack_stamp()]
    write(OUT / "run_provenance.md", lines)


# --------------------------------------------------------------------------- main


def main() -> None:
    analysis_stack.require()
    OUT.mkdir(parents=True, exist_ok=True)
    dup = duplicated()
    parents = parent_of()
    size, one_apart = leaf_density()

    keys = set(perquery(STACKED, "bm25_unigram")["query_item_key"].astype(str))
    feats = stacked_features(keys, size, one_apart)
    F = {}
    for _, short, _, _ in ARMS:
        frame = paired(short, STACKED, dup, parents).join(feats, on="q")
        if frame["dose"].isna().any():
            raise ValueError(f"{short}: stacked queries without features")
        F[short] = frame.assign(queryset=STACKED)
    first = next(iter(F.values()))
    for short, frame in F.items():
        if list(frame["q"]) != list(first["q"]):
            raise ValueError(f"{short}: query order differs between arms")
    S = {s: paired(s, SINGLE, dup, parents, S4_EXCLUDED).assign(queryset=SINGLE) for _, s, _, _ in ARMS}
    W = {s: paired(s, L2W, dup, parents).assign(queryset=L2W) for _, s, _, _ in ARMS
         if (run_dir(L2W, s) / "run_meta.json").is_file()}

    floors = {s: float(item(columns(F[s], "tf"))["item_id"].mean()) for s in F}
    stats = headline_stats(F)
    results = evaluate(F, floors)

    write_headline(F, stats, floors, dup)
    write_single_reference(F, S, W, dup)
    strata_table(F, "subchapter", sorted(first["subchapter"].unique()), "T3: by subchapter (dev, tie-free)",
                 "subchapter.md", ["T1's columns per subchapter. Strata of one concept are printed and never read",
                                   "(design); the subchapters differ in family size, dose and type mix."], dup)
    strata_table(F, "tercile", ["small", "medium", "large"], "T4a: by family-size tercile (dev, tie-free)",
                 "tercile.md", ["The harness's terciles (`SPLITS.md` boundaries). Descriptive; W3 in `density.md`",
                                "is the registered sibling-density test."], dup)
    write_density(F, results, dup)
    write_dose(F, dup)
    write_presence(F, dup)
    write_d004(F, results)
    write_predictions(results, floors)
    write_regression(parents)
    write_figures(F, stats)
    write_provenance()
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
