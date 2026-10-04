"""S11 — Track E, two-stage architecture: T1–T9 and Fig. 8 (design `931ee0c`, amendments A1–A4).

    python src/utils/build_results_s11.py        # in the sprint container, bc3cat-s3

Reads, and never writes, S11's 35 runs — K0 (A4), K1, K2, R2 and F1 on seven dev bases — and their references,
the earlier sprints' runs on the same queries: `bge_m3_colbert`, `dense_e5`, `bm25_unigram`, `rules_valuenorm`,
S9's registered LLM arm and the oracle arms† (printed, never tested, D-010). For `texto_u` / `resumen_u` a
reference arm's run is its dev `texto` / `resumen` run restricted to U, as in S9. Writes
`docs/synthetic-oe/results/S11/`.

Every contrast is paired: two arms on the same queries and the same scoring population. K0 orders its top tier by
catalogue position, which is not a score, so its tie-free hit treats that tier as one tie set (design;
`utils.s11_stages`); the other S11 arms order by ColBERT score, and exact ties are read from the scores as every
earlier sprint does. The registered tests are the design's eleven (A1–A7), read tie-free (primary), as run and on
the D-004 clean subset; Holm and BH across all eleven per column. A7 is read on the E3 ladder under D-053.

The analysis stack is pinned (`analysis_stack.py`): the script refuses to run on another.
"""

from __future__ import annotations

import hashlib
import json
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import subprocess  # noqa: E402
import sys  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pipeline.catalog_lookup import CatalogLookup  # noqa: E402
from utils import analysis_stack  # noqa: E402
from utils.build_results_s2 import ALPHA, B, SEED, bh, boot_cluster, boot_p, boot_query, ci, f4, fci, fd, fp, holm, write  # noqa: E402
from utils.build_results_s4 import AMENDMENT_EXCLUDED as S4_EXCLUDED, CORPUS_JSON, FEW_CLUSTERS, LAYERS  # noqa: E402
from utils.build_results_s6 import test_p  # noqa: E402
from utils.build_results_s7 import tie_table  # noqa: E402
from utils.build_results_s8 import SIGN_MIN, strat_weights, cluster_leaf_weights  # noqa: E402
from utils.build_results_s9 import query_table as s9_query_table  # noqa: E402
from utils.exclusions import item_excluded  # noqa: E402
from utils.pantry_flags import text_flags  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.s11_stages import decompose, extractor_for, gold_axes_from  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
INDEX = REPO / "index" / "OE"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S11"
FIGS = OUT / "figures"
GENERATOR = "src/utils/build_results_s11.py"
LLM_CACHE = DATA / "llm_cache" / "structured_llm_extract.jsonl"
SCHEMA_JSON = DATA / "OE_concept_schema.json"

#: The S11 arms (design, work item 3; K0 under its S11 name, A4).
S11_ARMS = {
    "K0": "structured_pipeline_llm_keytol_hard__OE",
    "K1": "structured_pipeline_llm_keytol_hard_colbert__OE",
    "K2": "structured_pipeline_llm_keytol_soft_colbert__OE",
    "R2": "structured_pipeline_rules_canon_soft_colbert__OE",
    "F1": "structured_pipeline_colbert_in_concept__OE",
}
#: References, run in earlier sprints. † oracle (D-010): printed, never tested.
REFS = {
    "bge_m3_colbert": "bge_m3_colbert__OE",
    "dense_e5": "dense_e5__OE",
    "bm25_unigram": "bm25_unigram__k1-0.60__b-0.35__OE",
    "rules_valuenorm": "structured_pipeline_rules_valuenorm__OE",
    "llm_exact (S9)": "structured_pipeline_llm_valuenorm__OE",
    "K0 as S9 ran it": "structured_pipeline_llm_keytol_valuenorm__OE",
    "bm25_unigram_params†": "bm25_unigram_params__k1-0.60__b-0.35__OE",
    "tfidf_phrases_replace†": "tfidf_unigram_phrases_replace__OE",
    "oracleparams†": "structured_pipeline_oracleparams_valuenorm__OE",
}
ARM_DIR = {**S11_ARMS, **REFS}
S9_BASES = ("texto_u", "resumen_u", "single_texto", "single_l2_texto", "stacked_texto")
E3_BASES = ("dose_texto", "isolated_texto")
BASES = S9_BASES + E3_BASES
#: A reference run on these U subsets is the arm's dev run on the full set, restricted (S9 A5 b). S11 arms and
#: S9's extractor runs were made on the subsets themselves.
REF_QS = {"texto_u": "texto", "resumen_u": "resumen"}
ON_SUBSET = set(S11_ARMS.values()) | {REFS["llm_exact (S9)"], REFS["K0 as S9 ran it"]}
L1 = set(LAYERS["L1"])
TYPE_LAYER = {t: lay for lay, ts in LAYERS.items() for t in ts}
VARIANTS = ("tf", "run", "clean")
#: A5: the equivalence band, the design's ±0.02.
EQUIV = 0.02
LADDER_RUNG = 5


def run_qs(base: str, method: str) -> str:
    return base if method in ON_SUBSET else REF_QS.get(base, base)


def available(base: str, method: str) -> bool:
    return (RUNS / run_qs(base, method) / method / "results_top100.jsonl.gz").exists()


# --------------------------------------------------------------------------- inputs


@lru_cache(maxsize=1)
def corpus_parents() -> dict[str, str]:
    return {r["item_key"]: r["parent_key"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}


@lru_cache(maxsize=1)
def corpus_text() -> dict[str, str]:
    return {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}


def e3_table(base: str, dev: frozenset[str]) -> pd.DataFrame:
    """One row per dev query of an E3 set: gold, concept, rung, type, D-004 flag, scoring masks."""
    gold_text = corpus_text()
    rows = []
    for r in json.loads((DATA / f"OE_{base}.json").read_text(encoding="utf-8")):
        if r["parent_key"] not in dev:
            continue
        types = r["modification_types"]
        f = text_flags(r["text"], gold_text[r["gold_item_key"]])
        rows.append({"key": r["item_key"], "gold": r["gold_item_key"], "concept": r["parent_key"],
                     "rung": int(r["modification_count"]), "type": types[0] if len(types) == 1 else "stacked",
                     "layer": TYPE_LAYER.get(types[0], "stacked") if len(types) == 1 else "stacked",
                     "flagged": bool(f["doubled"] or f["topo"])})
    frame = pd.DataFrame(rows).set_index("key")
    excluded = item_excluded(base, frame["gold"], dev)
    frame["item_scored"] = ~frame["gold"].isin(excluded)
    frame["parent_scored"] = True
    frame["base"] = base
    return frame


def query_table(base: str, dev: frozenset[str]) -> pd.DataFrame:
    if base in E3_BASES:
        return e3_table(base, dev)
    q = s9_query_table(base, dev)
    q["rung"] = 0
    return q


@lru_cache(maxsize=None)
def run_meta(qs: str, method: str) -> dict:
    return json.loads((RUNS / qs / method / "run_meta.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _perquery(qs: str, method: str) -> pd.DataFrame:
    return pd.read_parquet(RUNS / qs / method / "results_perquery.parquet").set_index("query_item_key")


class Stages:
    """`s11_stages.decompose` per (arm, base), built once; the catalogue and extractors are shared."""

    def __init__(self):
        self.schema = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
        ln = pd.read_parquet(DATA / "OE_long_norm.parquet", columns=["item_key", "parent_key", "parameters_norm"])
        self.gold_axes = gold_axes_from(ln[ln["parent_key"].str.endswith("$")])
        self._cat: dict = {}
        self._ex: dict = {}
        self._d: dict = {}

    def get(self, short: str, base: str) -> pd.DataFrame:
        k = (short, base)
        if k not in self._d:
            method = S11_ARMS[short]
            params = json.loads((INDEX / method / "meta.json").read_text(encoding="utf-8"))["params"]
            vm = params.get("stage3_value_match", "literal")
            if vm not in self._cat:
                self._cat[vm] = CatalogLookup(SCHEMA_JSON, DATA / "OE_long_norm.parquet", value_match=vm)
            if short not in self._ex:
                self._ex[short] = extractor_for(params, SCHEMA_JSON, LLM_CACHE)
            d = decompose(RUNS / base / method, params, self.schema, corpus_parents(), self.gold_axes,
                          self._ex[short], self._cat[vm])
            if not d["consistent"].all():
                raise ValueError(f"{short}/{base}: re-derived top tier misses the run's rank 1 for "
                                 f"{int((~d['consistent']).sum())} queries")
            self._d[k] = d
        return self._d[k]


STAGES: Stages | None = None
_HITS: dict = {}


def hits(base: str, method: str, keys: tuple[str, ...]) -> pd.DataFrame:
    """Tie-free and as-run hits of `keys`, both levels. K0's tie-free hit reads its top tier as one tie set."""
    qs = run_qs(base, method)
    k = (qs, method, keys)
    if k not in _HITS:
        tf = tie_table(RUNS / qs / method, set(keys), corpus_parents())
        pq = _perquery(qs, method)
        missing = set(keys) - set(pq.index)
        if missing:
            raise KeyError(f"{qs}/{method}: queries absent from the run: {sorted(missing)[:3]}")
        out = pd.DataFrame({"item_tf": tf.loc[list(keys), "item_tf"].to_numpy(float),
                            "parent_tf": tf.loc[list(keys), "parent_tf"].to_numpy(float),
                            "item_run": pq.loc[list(keys), "item_acc1"].to_numpy(float),
                            "parent_run": pq.loc[list(keys), "parent_acc1"].to_numpy(float)}, index=list(keys))
        if method == S11_ARMS["K0"]:
            st = STAGES.get("K0", base).loc[list(keys)]
            out["item_tf"] = st["item_tie_tier"].to_numpy(float)
            out["parent_tf"] = st["s1_correct"].to_numpy(float)
        for level in ("item", "parent"):
            a, b = out[f"{level}_run"], out[f"{level}_tf"]
            if (((a == 1) & (b == 0)) | ((a == 0) & (b == 1))).any():
                raise ValueError(f"{qs}/{method}/{level}: tie-free and as-run disagree on a certainty")
        _HITS[k] = out
    return _HITS[k]


def pair(Q: pd.DataFrame, base: str, mod: str, ref: str) -> pd.DataFrame:
    keys = tuple(Q.index)
    m, r = hits(base, ARM_DIR[mod], keys), hits(base, ARM_DIR[ref], keys)
    f = Q.copy()
    for col in ("item_tf", "parent_tf", "item_run", "parent_run"):
        f[f"mod_{col}"] = m[col].to_numpy()
        f[f"ref_{col}"] = r[col].to_numpy()
    return f


def variant(f: pd.DataFrame, v: str) -> pd.DataFrame:
    src = "run" if v == "run" else "tf"
    g = f.copy()
    for side in ("mod", "ref"):
        for level in ("item", "parent"):
            g[f"{side}_{level}"] = g[f"{side}_{level}_{src}"]
    return g[~g["flagged"]] if v == "clean" else g


def scored(f: pd.DataFrame, level: str) -> pd.DataFrame:
    return f[f[f"{level}_scored"]]


# --------------------------------------------------------------------------- statistics

_CELLS: dict = {}


def delta_cell(frame: pd.DataFrame, level: str, label: str) -> dict:
    """Mean paired δ (mod − ref) on the level's scored queries, concept- and query-level intervals.
    One bootstrap draw per statistic: a later table printing the same statistic reuses it (S9 audit F1)."""
    f = scored(frame, level)
    n_all = len(frame)
    if len(f) == 0:
        nan2 = (float("nan"),) * 2
        return {"n_all": n_all, "n": 0, "excluded": n_all, "concepts": 0, "est": float("nan"), "ref": float("nan"),
                "mod": float("nan"), "c": nan2, "q": nan2, "draws": np.array([])}
    ref, mod = f[f"ref_{level}"].to_numpy(float), f[f"mod_{level}"].to_numpy(float)
    key = (level, tuple(f.index), tuple(f["concept"]), ref.tobytes(), mod.tobytes())
    if key not in _CELLS:
        d = mod - ref
        c = boot_cluster(d[:, None], f["concept"].to_numpy(), f"s11|{label}|{level}")[:, 0]
        q = boot_query(d[:, None], f"s11|{label}|{level}")[:, 0]
        _CELLS[key] = {"n": len(f), "concepts": int(f["concept"].nunique()), "est": float(d.mean()),
                       "ref": float(ref.mean()), "mod": float(mod.mean()), "c": ci(c), "q": ci(q), "draws": c}
    return {"n_all": n_all, "excluded": n_all - len(f), **_CELLS[key]}


def acc_cell(Q: pd.DataFrame, base: str, arm: str, level: str, v: str) -> dict:
    """An arm's Acc@1 on the level's scored queries of `Q`, with n."""
    h = hits(base, ARM_DIR[arm], tuple(Q.index))
    f = Q.copy()
    f["hit"] = h[f"{level}_{'run' if v == 'run' else 'tf'}"].to_numpy()
    if v == "clean":
        f = f[~f["flagged"]]
    s = scored(f, level)
    return {"n_all": len(f), "n": len(s), "excluded": len(f) - len(s), "concepts": int(s["concept"].nunique()),
            "acc": float(s["hit"].mean()) if len(s) else float("nan")}


_LADDERS: dict = {}


def ladder_cell(frame: pd.DataFrame, label: str) -> dict:
    """D-053 on the E3 ladder: per leaf, Σ δ over its scored queries and their count; concept-stratified leaf
    bootstrap (the reading) and concept-clustered (beside); per-concept estimates for the sign rule.
    One bootstrap draw per statistic, as in `delta_cell`: T5 reuses T2's draws for A7's rung (S11 audit F5)."""
    f = scored(frame, "item")
    d = (f["mod_item"] - f["ref_item"]).to_numpy(float)
    key = (tuple(f.index), tuple(f["gold"]), tuple(f["concept"]), d.tobytes())
    if key not in _LADDERS:
        _LADDERS[key] = _ladder_draws(f, d, label)
    return {"n_all": len(frame), "excluded": len(frame) - len(f), **_LADDERS[key]}


def _ladder_draws(f: pd.DataFrame, d: np.ndarray, label: str) -> dict:
    g = pd.DataFrame({"gold": f["gold"].to_numpy(), "concept": f["concept"].to_numpy(), "d": d})
    leaf = g.groupby("gold", sort=True).agg(num=("d", "sum"), den=("d", "size"), concept=("concept", "first"))
    num, den, conc = leaf["num"].to_numpy(float), leaf["den"].to_numpy(float), leaf["concept"].to_numpy()
    with np.errstate(invalid="ignore", divide="ignore"):
        s = (strat_weights(conc, label) @ num) / (strat_weights(conc, label) @ den)
        c = (cluster_leaf_weights(conc, label) @ num) / (cluster_leaf_weights(conc, label) @ den)
    s, c = s[np.isfinite(s)], c[np.isfinite(c)]
    per = {k: float(num[conc == k].sum() / den[conc == k].sum()) for k in sorted(set(conc))}
    return {"n": len(f), "concepts": len(per), "leaves": len(leaf), "est": float(num.sum() / den.sum()), "ref": float(f["ref_item"].mean()),
            "mod": float(f["mod_item"].mean()), "c": ci(s), "q": ci(c), "draws": s, "per": per}


def read_mean(c: dict, holm_p: float, side: int) -> str:
    lo, hi = c["c"]
    good, bad = (lo > 0, hi < 0) if side > 0 else (hi < 0, lo > 0)
    if good and holm_p < ALPHA:
        return "supported"
    if bad and holm_p < ALPHA:
        return "contradicted"
    return "not supported"


def read_equiv(c: dict, holm_p: float) -> str:
    lo, hi = c["c"]
    if -EQUIV < lo and hi < EQUIV and holm_p < ALPHA:
        return "supported"
    if (lo > EQUIV or hi < -EQUIV) and holm_p < ALPHA:
        return "contradicted"
    return "not supported"


def read_ladder(c: dict, holm_p: float, side: int) -> str:
    lo, hi = c["c"]
    signs = sum(1 for v in c["per"].values() if np.isfinite(v) and v * side > 0)
    good, bad = (lo > 0, hi < 0) if side > 0 else (hi < 0, lo > 0)
    if good and holm_p < ALPHA and signs >= SIGN_MIN:
        return "supported"
    if bad and holm_p < ALPHA:
        return "contradicted"
    return "not supported"


# --------------------------------------------------------------------------- frames and tests


class Frames:
    def __init__(self, dev: frozenset[str]):
        self.dev = dev
        self.Q = {b: query_table(b, dev) for b in BASES}

    def pair(self, base: str, mod: str, ref: str, sel=None) -> pd.DataFrame:
        Q = self.Q[base] if sel is None else sel(self.Q[base])
        return pair(Q, base, mod, ref)


def l1(Q: pd.DataFrame) -> pd.DataFrame:
    return Q[Q["type"].isin(L1)]


def rung(k: int):
    return lambda Q: Q[Q["rung"] == k]


def registered(F: Frames) -> list[dict]:
    """The design's eleven: id, contrast, population, prediction, kind, side, and whether K0 (seen) is a side."""
    T = []
    def add(tid, mod, ref, base, sel, pop, what, kind, side):
        T.append({"id": tid, "mod": mod, "ref": ref, "base": base, "pop": pop, "what": what, "kind": kind,
                  "side": side, "seen_side": "K0" in (mod, ref),
                  "frame": lambda v, b=base, m=mod, r=ref, s=sel: variant(F.pair(b, m, r, s), v)})
    add("A1", "K2", "bge_m3_colbert", "stacked_texto", None, "stacked_texto", "K2 − ColBERT > 0", "mean", +1)
    add("A1", "K2", "bge_m3_colbert", "single_texto", l1, "single_texto, pooled L1", "K2 − ColBERT > 0", "mean", +1)
    add("A2", "K1", "K0", "single_texto", None, "single_texto, all types", "K1 − K0 > 0", "mean", +1)
    add("A2", "K1", "K0", "stacked_texto", None, "stacked_texto", "K1 − K0 > 0", "mean", +1)
    add("A3", "K2", "K1", "stacked_texto", None, "stacked_texto", "K2 − K1 > 0", "mean", +1)
    add("A4", "R2", "bm25_unigram", "single_texto", l1, "single_texto, pooled L1", "R2 − bm25_unigram > 0", "mean", +1)
    add("A4", "R2", "rules_valuenorm", "single_texto", l1, "single_texto, pooled L1", "R2 − rules_valuenorm > 0",
        "mean", +1)
    add("A5", "F1", "bge_m3_colbert", "stacked_texto", None, "stacked_texto", "F1 − ColBERT within the band",
        "equiv", 0)
    add("A6", "K2", "bge_m3_colbert", "texto_u", None, "texto_u", "K2 − ColBERT < 0", "mean", -1)
    add("A7", "K2", "bge_m3_colbert", "dose_texto", None, "dose_texto, pooled over rungs", "K2 − ColBERT > 0",
        "ladder", +1)
    add("A7", "K2", "bge_m3_colbert", "dose_texto", rung(LADDER_RUNG), "dose_texto, top rung", "K2 − ColBERT > 0",
        "ladder", +1)
    return T


def evaluate(F: Frames) -> list[dict]:
    results = []
    for spec in registered(F):
        row = {k: spec[k] for k in ("id", "mod", "ref", "base", "pop", "what", "kind", "side", "seen_side")}
        for v in VARIANTS:
            frame = spec["frame"](v)
            label = f"{spec['id']}|{spec['mod']}|{spec['ref']}|{spec['pop']}|{v}"
            if spec["kind"] == "ladder":
                cell = ladder_cell(frame, label)
                cell["p"] = boot_p(cell["draws"]) if len(cell["draws"]) else 1.0
                cell["tested"] = True
            else:
                cell = delta_cell(frame, "item", label)
                if spec["kind"] == "equiv":
                    cell["p"] = max(test_p(cell["draws"], -EQUIV), test_p(cell["draws"], EQUIV))
                else:
                    cell["p"] = test_p(cell["draws"], 0.0) if len(cell["draws"]) else 1.0
                cell["tested"] = cell["concepts"] >= FEW_CLUSTERS
            row[v] = cell
        results.append(row)
    for v in VARIANTS:
        live = [r for r in results if r[v]["tested"]]
        for r, h, q in zip(live, holm([r[v]["p"] for r in live]), bh([r[v]["p"] for r in live])):
            r[v]["holm"], r[v]["bh"] = h, q
        for r in results:
            c = r[v]
            if not c["tested"]:
                c["reading"] = "not tested"
            elif r["kind"] == "ladder":
                c["reading"] = read_ladder(c, c["holm"], r["side"])
            elif r["kind"] == "equiv":
                c["reading"] = read_equiv(c, c["holm"])
            else:
                c["reading"] = read_mean(c, c["holm"], r["side"])
    return results


def resolution(results: list[dict]) -> str:
    """The design's rule for the method contribution, on the tie-free readings."""
    a1 = [r["tf"]["reading"] == "supported" for r in results if r["id"] == "A1"]
    a7_pooled = next(r for r in results if r["id"] == "A7" and r["pop"].endswith("pooled over rungs"))
    a7 = a7_pooled["tf"]["reading"] == "supported"
    if all(a1) and a7:
        return "established on dev"
    if any(a1):
        return "partly established"
    return "not established"


# --------------------------------------------------------------------------- tables


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S11 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def footer() -> list[str]:
    return ["", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile intervals at level {1 - ALPHA:.0%}; concept-clustered "
            "(D-030) unless marked otherwise; on the E3 ladder, concept-stratified leaf bootstrap (D-053). Split `dev`.",
            "", analysis_stack.stamp()]


def name(arm: str) -> str:
    if arm in S11_ARMS:
        return f"**{arm}** `{S11_ARMS[arm].replace('structured_pipeline_', '').replace('__OE', '')}`"
    return f"`{arm}`"


def thin(c: dict) -> str:
    return "‡" if c["concepts"] < FEW_CLUSTERS else ""


def write_profile(F: Frames) -> None:
    lines = header("T1: profile — every arm on every base", [
        "Item and parent Acc@1, tie-free (primary) and as run. Item level excludes D-033 golds, D-040 on `resumen_u` "
        "and S4's P7 query; n scored and n excluded per row. K0's tie-free reading scores its catalogue-ordered top "
        "tier as one tie set (design). A blank row: that reference was never run on the base. † oracle (D-010), never "
        f"tested. ‡ fewer than {FEW_CLUSTERS} concepts."])
    lines += ["| base | arm | n | n scored | n excluded | concepts | item | item, as run | item, D-004 clean | parent | "
              "parent, as run | |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for base in BASES:
        for arm in list(S11_ARMS) + list(REFS):
            if not available(base, ARM_DIR[arm]):
                continue
            Q = F.Q[base]
            it, ir, ic = (acc_cell(Q, base, arm, "item", v) for v in VARIANTS)
            pt, pr = (acc_cell(Q, base, arm, "parent", v) for v in ("tf", "run"))
            lines.append(f"| `{base}` | {name(arm)} | {it['n_all']:,} | {it['n']:,} | {it['excluded']:,} | {it['concepts']} | "
                         f"{f4(it['acc'])} | {f4(ir['acc'])} | {f4(ic['acc'])} | {f4(pt['acc'])} | {f4(pr['acc'])} | "
                         f"{thin(it)} |")
    write(OUT / "profile.md", lines + footer())


def check_parent_identity(F: Frames) -> list[str]:
    """A8 as restated by A3: the S11 arms' parent level, as run, equals K0's on every query of every base."""
    lines = []
    for base in BASES:
        keys = tuple(F.Q[base].index)
        ref = hits(base, S11_ARMS["K0"], keys)["parent_run"].to_numpy()
        for arm in ("K1", "K2", "R2", "F1"):
            other = hits(base, S11_ARMS[arm], keys)["parent_run"].to_numpy()
            if not np.array_equal(ref, other):
                raise ValueError(f"A8 (A3): {arm}'s parent level differs from K0's on {base}")
        lines.append(f"`{base}` {len(keys):,}")
    return lines


def write_contrasts(results: list[dict]) -> None:
    lines = header("T2: the registered contrasts", [
        "Each of the design's eleven contrasts, paired on the same queries, item level. Tie-free (primary), as run and "
        "on the D-004 clean subset. On the E3 ladder (A7) the reading interval is D-053's concept-stratified leaf "
        "bootstrap and the concept-clustered interval is printed beside it as *CI (other)*; elsewhere *CI (other)* is "
        "the query-level interval. Readings are in T8."])
    lines += ["| test | contrast | population | n | n scored | n excluded | concepts | ref | mod | δ | CI (reading) | "
              "CI (other) | δ as run | CI as run | δ clean | CI clean |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|---:|---|"]
    for r in results:
        a, b, c = r["tf"], r["run"], r["clean"]
        lines.append(f"| {r['id']} | {r['what']} | {r['pop']} | {a['n_all']:,} | {a['n']:,} | {a['excluded']:,} | "
                     f"{a['concepts']} | {f4(a['ref'])} | {f4(a['mod'])} | {fd(a['est'])} | {fci(a['c'], True)} | "
                     f"{fci(a['q'], True)} | {fd(b['est'])} | {fci(b['c'], True)} | {fd(c['est'])} | {fci(c['c'], True)} |")
    write(OUT / "contrasts.md", lines + footer())


def write_stages(F: Frames) -> None:
    lines = header("T3: stage decomposition", [
        "Re-derived from each run's own ranking (`utils.s11_stages`): Stage 1 is the rank-1 leaf's concept; Stage 2 the "
        "arm's extractor on the run's query text (the LLM extractor from the cache only); Stage 3 the tiers. Every "
        "re-derivation reproduces its run's rank 1 (checked). Axis counts are usable extractions (schema axis and "
        "value); *correct* and *misread* are against the gold leaf, on queries whose Stage 1 is right. *Gold rank in "
        "tier* is its position within its own tier, when the gold is in the run's top 100. Item-scored queries."])
    lines += ["| base | arm | n scored | Stage 1 | axes / query | extracted / query | correct / query | misread / query | "
              "gold in top tier | top-tier size, median | IQR | gold rank in tier, median | gold in top 100 |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for base in BASES:
        Q = F.Q[base]
        keys = Q.index[Q["item_scored"]]
        for arm in S11_ARMS:
            d = STAGES.get(arm, base).loc[keys]
            ok = d[d["s1_correct"]]
            q1, q3 = np.percentile(d["top_tier_size"], [25, 75])
            rk = d["gold_rank_in_tier"].dropna()
            lines.append(f"| `{base}` | {name(arm)} | {len(d):,} | {f4(d['s1_correct'].mean())} | "
                         f"{ok['axes'].mean():.2f} | {ok['extracted'].mean():.2f} | {ok['correct'].mean():.2f} | "
                         f"{ok['misread'].mean():.2f} | {f4(d['gold_in_top'].mean())} | {d['top_tier_size'].median():.0f} | "
                         f"[{q1:.0f}, {q3:.0f}] | {(rk.median() if len(rk) else float('nan')):.0f} | "
                         f"{f4(len(rk) / len(d))} |")
    write(OUT / "stages.md", lines + footer())


def write_types(F: Frames) -> None:
    lines = header("T4: by type and layer, `single_texto`", [
        "Item Acc@1 tie-free per arm and single type, and each S11 arm − ColBERT, paired. Types and layers differ in "
        "which leaves admit them, so rows are between-population and never compared with one another (design). "
        f"‡ fewer than {FEW_CLUSTERS} concepts: not read."])
    Q = F.Q["single_texto"]
    groups = [(t, Q[Q["type"] == t]) for t in sorted(Q["type"].unique())]
    groups += [(lay, Q[Q["layer"] == lay]) for lay in LAYERS]
    arms = list(S11_ARMS) + ["bge_m3_colbert", "bm25_unigram", "rules_valuenorm"]
    lines += ["| scope | n | n scored | concepts | " + " | ".join(name(a) for a in arms) + " | K2 − ColBERT | CI | "
              "R2 − ColBERT | CI | |", "|---|---:|---:|---:|" + "---:|" * len(arms) + "---:|---|---:|---|---|"]
    for scope, sub in groups:
        accs = [acc_cell(sub, "single_texto", a, "item", "tf") for a in arms]
        k2 = delta_cell(variant(pair(sub, "single_texto", "K2", "bge_m3_colbert"), "tf"), "item", f"T4|K2|{scope}")
        r2 = delta_cell(variant(pair(sub, "single_texto", "R2", "bge_m3_colbert"), "tf"), "item", f"T4|R2|{scope}")
        lines.append(f"| {scope} | {accs[0]['n_all']:,} | {accs[0]['n']:,} | {accs[0]['concepts']} | "
                     + " | ".join(f4(c["acc"]) for c in accs)
                     + f" | {fd(k2['est'])} | {fci(k2['c'], True)} | {fd(r2['est'])} | {fci(r2['c'], True)} | {thin(accs[0])} |")
    write(OUT / "types.md", lines + footer())


def write_ladder(F: Frames) -> None:
    concepts = sorted(F.Q["dose_texto"]["concept"].unique())
    iso_rung = int(F.Q["isolated_texto"]["rung"].max())
    lines = header(f"T5: the E3 ladder, by rung (`dose_texto`, and `isolated_texto` as rung {iso_rung})", [
        f"Item Acc@1 tie-free per arm and rung on the dev ladder ({len(concepts)} concepts: "
        + ", ".join(f"`{c}`" for c in concepts) + "), and K2 − ColBERT paired per rung under "
        "D-053: concept-stratified leaf interval, and the number of concepts whose estimate has the predicted sign "
        f"(a supported reading needs {SIGN_MIN}). No LLM arm had seen these queries (design). Rows are scoped to "
        "these concepts."])
    arms = list(S11_ARMS) + ["bge_m3_colbert", "dense_e5", "bm25_unigram", "rules_valuenorm"]
    lines += ["| set | rung | n scored | n excluded | concepts | leaves | " + " | ".join(name(a) for a in arms)
              + " | K2 − ColBERT | CI (D-053) | concepts with δ > 0 |",
              "|---|---:|---:|---:|---:|---:|" + "---:|" * len(arms) + "---:|---|---:|"]
    for base in E3_BASES:
        Q = F.Q[base]
        for k in sorted(Q["rung"].unique()):
            sub = Q[Q["rung"] == k]
            accs = [acc_cell(sub, base, a, "item", "tf") for a in arms]
            c = ladder_cell(variant(pair(sub, base, "K2", "bge_m3_colbert"), "tf"), f"T5|{base}|{k}")
            pos = sum(1 for v in c["per"].values() if v > 0)
            lines.append(f"| `{base}` | {k} | {c['n']:,} | {c['excluded']:,} | {c['concepts']} | {c['leaves']} | " + " | ".join(f4(a["acc"]) for a in accs)
                         + f" | {fd(c['est'])} | {fci(c['c'], True)} | {pos} of {len(c['per'])} |")
    write(OUT / "ladder.md", lines + footer())


def extraction_seconds(base: str) -> list[float]:
    """Generation seconds of K0's extraction for every query of `base`. The extractor caches every prompt under the
    query key `"extract"`, so a query's line is found by its cache key: the prompt is rebuilt from K0's Stage-1
    concept and the run's query text, keyed as `OllamaClient.key` keys it. A prompt absent from the cache stops
    the generator: every K0 run read one."""
    import gzip
    from pipeline.prompts import build_extraction_prompt
    from utils.s11_stages import OfflineClient
    by_key = {}
    for line in LLM_CACHE.read_text(encoding="utf-8").splitlines():
        if line:
            r = json.loads(line)
            by_key[r["cache_key"]] = float(r.get("seconds", float("nan")))
    client, schema, parents = OfflineClient(), STAGES.schema, corpus_parents()
    out = []
    with gzip.open(RUNS / base / S11_ARMS["K0"] / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for r in map(json.loads, fh):
            g = schema[parents[r["candidates"][0]["index_item_key"]]]
            k = client.key(build_extraction_prompt(g["concept"], g["axes"], r["query_text"]))
            if k not in by_key:
                raise KeyError(f"{base}/{r['query_item_key']}: its extraction prompt is not in the cache")
            out.append(by_key[k])
    return out


def write_cost(F: Frames) -> None:
    lines = header("T6: cost", [
        "Seconds per query. *Retrieval* is each run's wall clock over its queries (`run_meta.json`); the LLM arms read "
        "a warm cache there, so their extraction time is given apart, from the cache's per-generation timing. The "
        "within-family ColBERT scores are built once per base (`index/OE/_colbert_family/`, A2); their build time "
        "includes encoding the reference run's full query list, so it is an upper bound per query of the base."])
    lines += ["| base | arm | queries | retrieval s / query |", "|---|---|---:|---:|"]
    for base in BASES:
        for arm in list(S11_ARMS) + ["bge_m3_colbert", "dense_e5", "bm25_unigram", "rules_valuenorm"]:
            m = ARM_DIR[arm]
            if not available(base, m):
                continue
            meta = run_meta(run_qs(base, m), m)
            lines.append(f"| `{base}` | {name(arm)} | {meta['queries']:,} | {meta['elapsed_s'] / meta['queries']:.4f} |")
    lines += ["", "| base | extractions found | phi4 seconds / query, median | ColBERT family build s | queries scored | "
              "s / query |", "|---|---:|---:|---:|---:|---:|"]
    for base in BASES:
        secs = extraction_seconds(base)
        cm = json.loads((INDEX / "_colbert_family" / f"{base}.meta.json").read_text(encoding="utf-8"))
        lines.append(f"| `{base}` | {len(secs):,} | {np.median(secs):.2f} | "
                     f"{cm['seconds']:,.0f} | {cm['queries']:,} | {cm['seconds'] / cm['queries']:.3f} |")
    write(OUT / "cost.md", lines + footer())


def write_d004(F: Frames, results: list[dict]) -> None:
    lines = header("T7: D-004 sensitivity", [
        "Every registered test recomputed without queries whose text carries a pantry artefact (S3's detector). A "
        "reading that changes category is *not robust*; the full-population reading stands."])
    lines += ["| base | queries | flagged |", "|---|---:|---:|"]
    for base in BASES:
        lines.append(f"| `{base}` | {len(F.Q[base]):,} | {int(F.Q[base]['flagged'].sum()):,} |")
    lines += ["", "| test | population | tie-free | reading | clean | CI | reading | robust |",
              "|---|---|---:|---|---:|---|---|---|"]
    for r in results:
        a, c = r["tf"], r["clean"]
        lines.append(f"| {r['id']} {r['what']} | {r['pop']} | {fd(a['est'])} | {a['reading']} | {fd(c['est'])} | "
                     f"{fci(c['c'], True)} | {c['reading']} | {'yes' if a['reading'] == c['reading'] else 'not robust'} |")
    write(OUT / "d004.md", lines + footer())


def write_predictions(results: list[dict], parent_lines: list[str]) -> None:
    lines = header("T8: the registered predictions", [
        f"The design's {len(results)} tests, blind: no S11 arm but K0 had been run, and A2's contrasts are blind "
        "because K1 is new (K0, the seen side, is marked). Holm and BH across every test read in a column; a cell with "
        f"fewer than {FEW_CLUSTERS} concepts reads *not tested*, except on the E3 ladder, read under D-053 (needs "
        f"{SIGN_MIN} concepts with the predicted sign). A5 is an equivalence test against a band of "
        f"±{EQUIV:.2f}: its p is the larger of the two one-sided ones. ⚑ the tie-free and as-run readings differ."])
    lines += ["| test | contrast | population | K0 side | n scored | concepts | estimate | CI (reading) | p | Holm | BH | "
              "reading | as run | as-run reading | clean reading | |",
              "|---|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---:|---|---|---|"]
    for r in results:
        a, b, c = r["tf"], r["run"], r["clean"]
        live = a["tested"]
        lines.append(f"| {r['id']} | {r['what']} | {r['pop']} | {'seen' if r['seen_side'] else ''} | {a['n']:,} | "
                     f"{a['concepts']} | {fd(a['est'])} | {fci(a['c'], True)} | {fp(a['p'])} | "
                     f"{fp(a['holm']) if live else '—'} | {fp(a['bh']) if live else '—'} | {a['reading']} | {fd(b['est'])} | "
                     f"{b['reading']} | {c['reading']} | {'⚑' if a['reading'] != b['reading'] else ''} |")
    lines += ["", "## The method contribution, by the design's rule", "",
              f"**{resolution(results)}.** The rule: established if A1 holds on both populations and A7 holds pooled; "
              "partly established if A1 holds on one population, or A7 fails; not established if A1 holds on neither.",
              "", "## A8, as restated by A3", "",
              "Every S11 arm's parent level, as run, equals K0's query by query on every base (asserted): "
              + "; ".join(parent_lines) + "."]
    write(OUT / "predictions.md", lines + footer())


def k0_comparison() -> list[str]:
    """A4: K0 re-run under its S11 name against S9's run, top 100 keys and scores, query by query."""
    out = ["", "## A4: K0 against S9's key-tolerant runs", "", "| base | queries | identical top 100 |", "|---|---:|---:|"]
    import gzip
    for base in S9_BASES:
        def load(m):
            with gzip.open(RUNS / base / m / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
                return [(r["query_item_key"], [(c["index_item_key"], c["score"]) for c in r["candidates"]])
                        for r in map(json.loads, fh)]
        a, b = load(S11_ARMS["K0"]), load(REFS["K0 as S9 ran it"])
        same = sum(x == y for x, y in zip(a, b)) if len(a) == len(b) else 0
        out.append(f"| `{base}` | {len(a):,} | {same:,} |")
    return out


def prompt_source() -> list[str]:
    """The extraction prompt has no template file: `build_extraction_prompt` in `src/pipeline/prompts.py` is the
    prompt. Its SHA-256 at each run commit stands in for the prompt SHA that no `run_meta.json` carries (S11 audit F1)."""
    path = "src/pipeline/prompts.py"
    commits = sorted({run_meta(qs, m)["code_commit"] for qs, m, _ in _HITS if m in S11_ARMS.values()})
    shas = {}
    for c in commits:
        blob = subprocess.run(["git", "show", f"{c}:{path}"], cwd=REPO, capture_output=True, check=True).stdout
        shas[c[:7]] = hashlib.sha256(blob).hexdigest()
    if len(set(shas.values())) != 1:
        raise ValueError(f"{path} differs across the S11 run commits: {shas}")
    return ["", f"Extraction prompt (`{path}`, `build_extraction_prompt`): SHA-256 `{next(iter(shas.values()))[:16]}` "
            f"at every S11 run commit ({', '.join(f'`{c}`' for c in shas)}). Recorded here, not in the runs' "
            "`run_meta.json`, which carry neither the prompt SHA nor the model digest."]


def write_provenance() -> None:
    lines = header("T9: provenance", [
        "Every run these tables read, with its stamp; then the data files, the ColBERT family caches and their "
        "reproduction check (A2), the extractor's regeneration check, and A4's comparison."])
    lines += ["| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |", "|---|---:|---|---|---|---|"]
    seen = set()
    for qs, method, _ in sorted(_HITS):
        if (qs, method) in seen:
            continue
        seen.add((qs, method))
        m = run_meta(qs, method)
        lines.append(f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                     f"{str(m['code_dirty']).lower()} | `{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|"]
    inputs = [CORPUS_JSON, SCHEMA_JSON, DATA / "OE_duplicate_texto_groups.json", REPO / "docs" / "synthetic-oe" / "SPLITS.md",
              LLM_CACHE] + [DATA / f"OE_{b}.json" for b in BASES]
    for p in inputs:
        lines.append(f"| `{p.relative_to(REPO).as_posix()}` | `{sha256_file(p)[:16]}` |")
    lines += ["", "| ColBERT family cache | file SHA-256 | reference run | queries | pairs | compared | mismatched | "
              "built at |", "|---|---|---|---:|---:|---:|---:|---|"]
    for base in BASES:
        cm = json.loads((INDEX / "_colbert_family" / f"{base}.meta.json").read_text(encoding="utf-8"))
        if sha256_file(INDEX / "_colbert_family" / f"{base}.npz") != cm["npz_sha256"]:
            raise ValueError(f"{base}: the family cache differs from the one its meta.json records")
        ch = cm["check"]
        lines.append(f"| `{base}` | `{cm['npz_sha256'][:16]}` | `{cm['reference_run']}` | {cm['queries']:,} | "
                     f"{cm['query_concept_pairs']:,} | {ch['compared']:,} | {ch['mismatched']} | `{cm['code_commit'][:7]}` |")
    det = json.loads((REPO / "logs" / "S11" / "determinism_extract.json").read_text(encoding="utf-8"))
    lines += ["", f"Extractor regeneration (work item 2): {det['identical']} of {det['n']} identical, "
              f"{len(det['unparsed'])} unparsed, {det['truncated']} truncated; model `{det['model_digest'][:16]}`, ollama "
              f"{det['ollama_version']}, options `{json.dumps(det['options'], sort_keys=True)}`."]
    lines += prompt_source()
    lines += k0_comparison()
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "src"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    lines += ["", f"Generator commit `{commit}`, `src/` {'dirty' if dirty else 'clean'}."]
    write(OUT / "run_provenance.md", lines + footer())


def write_figure(F: Frames) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGS.mkdir(parents=True, exist_ok=True)
    arms = [("K2", "#3b6ea8"), ("R2", "#5a9e4b"), ("bge_m3_colbert", "#c2622d"), ("bm25_unigram", "#7a7a7a")]
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    width = 0.8 / len(arms)
    for j, (arm, colour) in enumerate(arms):
        xs, est, lo, hi = [], [], [], []
        for i, base in enumerate(BASES):
            if not available(base, ARM_DIR[arm]):
                continue
            Q = F.Q[base]
            f = variant(pair(Q, base, arm, arm), "tf")
            s = scored(f, "item")
            d = s["mod_item"].to_numpy(float)
            draws = boot_cluster(d[:, None], s["concept"].to_numpy(), f"fig8|{arm}|{base}")[:, 0]
            m, (a, b) = float(d.mean()), ci(draws)
            xs.append(i + (j - (len(arms) - 1) / 2) * width); est.append(m); lo.append(m - a); hi.append(b - m)
        ax.bar(xs, est, width=width, color=colour, label=arm, yerr=[lo, hi], capsize=2)
    ax.set_xticks(range(len(BASES)))
    ax.set_xticklabels(BASES, rotation=20, fontsize=8)
    ax.set_ylabel("item Acc@1 (tie-free)")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8, ncol=len(arms))
    fig.tight_layout()
    fig.savefig(FIGS / "fig8_two_stage.png", dpi=150, metadata={"Software": None})
    plt.close(fig)


def main() -> None:
    global STAGES
    analysis_stack.require()
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES = Stages()
    F = Frames(load_split("dev"))
    results = evaluate(F)
    parent_lines = check_parent_identity(F)
    write_profile(F)
    write_contrasts(results)
    write_stages(F)
    write_types(F)
    write_ladder(F)
    write_cost(F)
    write_d004(F, results)
    write_predictions(results, parent_lines)
    write_figure(F)
    write_provenance()
    print(f"written: {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
