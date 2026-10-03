"""S9 — Track C, query-side normalisation and rewriting: T1–T10 and Fig. 7 (design `587e466`, A1–A5).

    python src/utils/build_results_s9.py        # in the sprint container, bc3cat-s3

Reads, and never writes, S9's 120 runs — BASE7 × {canon, hyde, rewrite} × five bases, the two IDF-guard
configs on the five untransformed bases, and the LLM-extraction arm on the same five — and their untransformed
references: for `texto_u` / `resumen_u` the arm's `texto` / `resumen` run restricted to U, for the three
synthetic bases the arm's run on that set (A5 b). Writes `docs/synthetic-oe/results/S9/`.

Every effect is paired: transformed − untransformed on the same query, same arm, same scoring population
(design). The overlap axis is S3's lexical coverage of the **untransformed** query against its gold, binned as
A5 (d) fixes. The registered tests are the design's 44 (Y1–Y3, Z1–Z2, G1–G2, E1–E2), read by S4's rule under
A5 (g), tie-free (primary), as run and on the D-004 clean subset.

The analysis stack is pinned (`analysis_stack.py`): the script refuses to run on another.
"""

from __future__ import annotations

import json
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from collections import Counter  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils import analysis_stack, idf_diagnostic  # noqa: E402
from utils.build_overlap import lexical_coverage, numeric_coverage  # noqa: E402
from utils.build_results_s2 import ALPHA, B, SEED, _rng, bh, boot_cluster, boot_query, ci, f4, fci, fd, fp, holm, write  # noqa: E402
from utils.build_results_s4 import AMENDMENT_EXCLUDED as S4_EXCLUDED, CORPUS_JSON, FEW_CLUSTERS, FLOOR, LAYERS  # noqa: E402
from utils.build_results_s6 import BASE7, cluster_weights, test_p  # noqa: E402
from utils.build_results_s7 import tie_table  # noqa: E402
from utils.exclusions import item_excluded, text_collisions  # noqa: E402
from utils.pantry_flags import text_flags  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.run_context import S9_BASES  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
INDEX = REPO / "index" / "OE"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S9"
FIGS = OUT / "figures"
GENERATOR = "src/utils/build_results_s9.py"

ARM_DIR = {
    "bm25_unigram": "bm25_unigram__k1-0.60__b-0.35__OE",
    "bm25_unigram_params": "bm25_unigram_params__k1-0.60__b-0.35__OE",
    "tfidf_phrases_replace": "tfidf_unigram_phrases_replace__OE",
    "bge_m3_colbert": "bge_m3_colbert__OE",
    "bge_m3_dense": "bge_m3_dense__OE",
    "dense_e5": "dense_e5__OE",
    "dense_es_hiiamsid": "dense_es_hiiamsid__OE",
}
#: D-010: they read the query record's `parameters`, which transforms leave as delivered (design).
ORACLE = {"bm25_unigram_params", "tfidf_phrases_replace"}
TESTED = [a for a in BASE7 if a not in ORACLE]
GUARD = {"bm25_unigram": "bm25_unigram__k1-0.60__b-0.35__idfcap-1200__OE",
         "bm25_unigram_params": "bm25_unigram_params__k1-0.60__b-0.35__idfcap-1200__OE"}
LLM_ARM = "structured_pipeline_llm_valuenorm__OE"
RULES_ARM = "structured_pipeline_rules_valuenorm__OE"
ORACLE_BOUND = "structured_pipeline_oracleparams_valuenorm__OE"
#: A7 (post hoc, César): the LLM arm with a tolerant key match; never a test, never pooled with the registered arm.
KEYTOL_ARM = "structured_pipeline_llm_keytol_valuenorm__OE"

TRANSFORMS = ("canon", "hyde", "rewrite")
T_LABEL = {"canon": "C", "hyde": "H", "rewrite": "W"}
NONID = [b for b in S9_BASES if b != "texto_u"]
REF_QS = {"texto_u": "texto", "resumen_u": "resumen"}

#: A5 (d): bins on the untransformed query's lexical coverage, over the non-identity bases.
BINS = [("B1", 0.0, 0.70), ("B2", 0.70, 0.85), ("B3", 0.85, 0.95), ("B4", 0.95, 1.0 + 1e-9)]
#: A5 (g): the non-inferiority margin of Z2 and G2.
MARGIN = -0.01
L1 = set(LAYERS["L1"])
TYPE_LAYER = {t: lay for lay, ts in LAYERS.items() for t in ts}
VARIANTS = ("tf", "run", "clean")
VARIANT_LABEL = {"tf": "tie-free", "run": "as run", "clean": "tie-free, D-004 clean subset"}
NONLATIN = re.compile(r"[　-鿿가-힯Ѐ-ӿ]")


# --------------------------------------------------------------------------- inputs


@lru_cache(maxsize=1)
def corpus() -> tuple[dict[str, str], dict[str, str]]:
    records = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    return {r["item_key"]: r["text"] for r in records}, {r["item_key"]: r["parent_key"] for r in records}


def records(name: str, dev: frozenset[str]) -> list[dict]:
    return [r for r in json.loads((DATA / f"OE_{name}.json").read_text(encoding="utf-8")) if r["parent_key"] in dev]


def query_table(base: str, dev: frozenset[str]) -> pd.DataFrame:
    """One row per dev query of `base`: gold, concept, type, layer, overlap, D-004 flag, scoring masks."""
    gold_text, _ = corpus()
    rows = []
    for r in records(base, dev):
        types = r.get("modification_types") or []
        if isinstance(types, str):
            types = json.loads(types.replace("'", '"'))
        typ = types[0] if len(types) == 1 else ("stacked" if types else base)
        q, g = r["text"], gold_text[r["gold_item_key"]]
        num = numeric_coverage(q, g)
        flags = text_flags(q, g)
        rows.append({"key": r["item_key"], "gold": r["gold_item_key"], "concept": r["parent_key"], "type": typ,
                     "layer": TYPE_LAYER.get(typ, typ), "cov": lexical_coverage(q, g),
                     "numcov": np.nan if num is None else num, "flagged": bool(flags["doubled"] or flags["topo"])})
    frame = pd.DataFrame(rows).set_index("key")
    excluded = item_excluded(base, frame["gold"], dev)
    p7 = {k: set(v["levels"]) for k, v in S4_EXCLUDED.items()}
    frame["item_scored"] = ~frame["gold"].isin(excluded) & ~frame.index.map(lambda k: "item" in p7.get(k, ()))
    frame["parent_scored"] = ~frame.index.map(lambda k: "parent" in p7.get(k, ()))
    frame["base"] = base
    return frame


@lru_cache(maxsize=None)
def _perquery(qs: str, method: str) -> pd.DataFrame:
    return pd.read_parquet(RUNS / qs / method / "results_perquery.parquet").set_index("query_item_key")


@lru_cache(maxsize=None)
def run_meta(qs: str, method: str) -> dict:
    return json.loads((RUNS / qs / method / "run_meta.json").read_text(encoding="utf-8"))


_HITS: dict = {}


def hits(qs: str, method: str, keys: tuple[str, ...]) -> pd.DataFrame:
    """Tie-free and as-run hits of `keys` in one run, both levels (A5 a)."""
    k = (qs, method, keys)
    if k not in _HITS:
        _, parents = corpus()
        tf = tie_table(RUNS / qs / method, set(keys), parents)
        pq = _perquery(qs, method)
        missing = set(keys) - set(pq.index)
        if missing:
            raise KeyError(f"{qs}/{method}: queries absent from the run: {sorted(missing)[:3]}")
        out = pd.DataFrame({"item_tf": tf.loc[list(keys), "item_tf"].to_numpy(float),
                            "parent_tf": tf.loc[list(keys), "parent_tf"].to_numpy(float),
                            "item_run": pq.loc[list(keys), "item_acc1"].to_numpy(float),
                            "parent_run": pq.loc[list(keys), "parent_acc1"].to_numpy(float)}, index=list(keys))
        for level in ("item", "parent"):
            a, b = out[f"{level}_run"], out[f"{level}_tf"]
            if (((a == 1) & (b == 0)) | ((a == 0) & (b == 1))).any():
                raise ValueError(f"{qs}/{method}/{level}: tie-free and as-run disagree on a certainty")
        _HITS[k] = out
    return _HITS[k]


def pair(Q: pd.DataFrame, mod: tuple[str, str], ref: tuple[str, str]) -> pd.DataFrame:
    """`Q` joined to the transformed (`mod`) and untransformed (`ref`) hits of its queries."""
    keys = tuple(Q.index)
    m, r = hits(*mod, keys), hits(*ref, keys)
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


def delta_cell(frame: pd.DataFrame, level: str, label: str) -> dict:
    """Mean paired δ on the level's scored queries, with concept and query intervals."""
    f = scored(frame, level)
    n_all = len(frame)
    if len(f) == 0:
        return {"n_all": n_all, "n": 0, "excluded": n_all, "concepts": 0, "est": float("nan"), "ref": float("nan"),
                "mod": float("nan"), "c": (float("nan"),) * 2, "q": (float("nan"),) * 2, "draws": np.array([])}
    ref, mod = f[f"ref_{level}"].to_numpy(float), f[f"mod_{level}"].to_numpy(float)
    d = mod - ref
    c = boot_cluster(d[:, None], f["concept"].to_numpy(), f"s9|{label}|{level}")[:, 0]
    q = boot_query(d[:, None], f"s9|{label}|{level}")[:, 0]
    return {"n_all": n_all, "n": len(f), "excluded": n_all - len(f), "concepts": int(f["concept"].nunique()),
            "est": float(d.mean()), "ref": float(ref.mean()), "mod": float(mod.mean()), "c": ci(c), "q": ci(q),
            "draws": c}


def _sums(x: np.ndarray, y: np.ndarray, groups: np.ndarray, labels: np.ndarray) -> np.ndarray:
    gi = np.searchsorted(labels, groups)
    s = np.zeros((len(labels), 5))
    np.add.at(s, gi, np.column_stack([np.ones_like(x), x, y, x * x, x * y]))
    return s


def _fit(S: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n, sx, sy, sxx, sxy = (S[..., i] for i in range(5))
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        icept = (sy - slope * sx) / n
    return icept, slope


def _query_draws(x: np.ndarray, y: np.ndarray, label: str, chunk: int = 1_000) -> tuple[np.ndarray, np.ndarray]:
    """Query-level bootstrap of the OLS fit, drawn in chunks so the weight matrix stays small."""
    rng = _rng("query|" + label)
    n = len(x)
    cols = np.column_stack([np.ones_like(x), x, y, x * x, x * y])
    out_a, out_b = [], []
    for start in range(0, B, chunk):
        W = rng.multinomial(n, np.full(n, 1.0 / n), size=min(chunk, B - start)).astype(float)
        a, b = _fit(W @ cols)
        out_a.append(a)
        out_b.append(b)
    return np.concatenate(out_a), np.concatenate(out_b)


def crossover(f: pd.DataFrame, label: str) -> dict:
    """OLS of per-query item δ on coverage (A5 e): slope, c* and their draws, concept- and query-level."""
    g = scored(f, "item")
    x, y = g["cov"].to_numpy(float), (g["mod_item"] - g["ref_item"]).to_numpy(float)
    labels, W = cluster_weights(g["concept"].to_numpy(), f"s9|{label}")
    S = _sums(x, y, g["concept"].to_numpy(), labels)
    a, b = _fit(S.sum(axis=0))
    da, db = _fit(W @ S)
    qa, qb = _query_draws(x, y, f"s9|{label}")
    with np.errstate(invalid="ignore", divide="ignore"):
        cstar = -da / db
    neg = db < 0
    cpoint = -a / b if b != 0 else float("nan")
    lo, hi = float(x.min()), float(x.max())
    return {"n": len(g), "concepts": int(g["concept"].nunique()), "slope": float(b), "icept": float(a),
            "slope_c": ci(db[np.isfinite(db)]), "slope_q": ci(qb[np.isfinite(qb)]), "draws": db,
            "cstar": float(cpoint), "in_range": bool(b < 0 and lo <= cpoint <= hi),
            "cstar_c": ci(cstar[neg & np.isfinite(cstar)]) if neg.sum() > 1 else (float("nan"),) * 2,
            "neg_share": float(neg.mean()), "range": (lo, hi)}


def read(est_c: tuple[float, float], holm_p: float, side: int, null: float) -> str:
    """S4's rule (A5 g): side +1 predicts above the null, −1 below."""
    lo, hi = est_c
    good, bad = (lo > null, hi < null) if side > 0 else (hi < null, lo > null)
    if good and holm_p < ALPHA:
        return "supported"
    if bad and holm_p < ALPHA:
        return "contradicted"
    return "not supported"


# --------------------------------------------------------------------------- building the frames


class Frames:
    """Every paired frame the tables read, built once."""

    def __init__(self, dev: frozenset[str]):
        self.dev = dev
        self.Q = {b: query_table(b, dev) for b in S9_BASES}
        self.T: dict = {}      # (arm, base, transform) -> frame
        self.G: dict = {}      # (arm, base) -> guard frame
        for arm in BASE7:
            d = ARM_DIR[arm]
            for base in S9_BASES:
                ref = (REF_QS.get(base, base), d)
                for t in TRANSFORMS:
                    self.T[(arm, base, t)] = pair(self.Q[base], (f"{base}__{t}", d), ref)
                if arm in GUARD:
                    self.G[(arm, base)] = pair(self.Q[base], (base, GUARD[arm]), ref)

    def pooled(self, arm: str, t: str, bases=NONID) -> pd.DataFrame:
        return pd.concat([self.T[(arm, b, t)] for b in bases])


def floors(F: Frames) -> dict[str, float]:
    """A5 (h): tie-free identity item Acc@1 on `texto_u`, per arm."""
    return {arm: float(scored(variant(F.T[(arm, "texto_u", "canon")], "tf"), "item")["ref_item"].mean())
            for arm in BASE7}


# --------------------------------------------------------------------------- the registered tests


def _bin(f: pd.DataFrame, name: str) -> pd.DataFrame:
    _, lo, hi = next(b for b in BINS if b[0] == name)
    return f[(f["cov"] >= lo) & (f["cov"] < hi)]


def registered(F: Frames) -> list[dict]:
    """The 44 tests: id, arm, transform, what, side, null, and a function from variant to (frame or fit)."""
    tests = []
    for t in ("hyde", "rewrite"):
        for arm in TESTED:
            tests.append({"id": "Y1", "arm": arm, "t": t, "what": "item δ in B4 < 0 (harm near-verbatim)",
                          "side": -1, "null": 0.0, "kind": "mean", "level": "item",
                          "frame": lambda v, a=arm, t=t: _bin(variant(F.pooled(a, t), v), "B4")})
            tests.append({"id": "Y2", "arm": arm, "t": t, "what": "item δ in B1 > 0 (gain at low overlap)",
                          "side": +1, "null": 0.0, "kind": "mean", "level": "item",
                          "frame": lambda v, a=arm, t=t: _bin(variant(F.pooled(a, t), v), "B1")})
            tests.append({"id": "Y3", "arm": arm, "t": t, "what": "slope of item δ on coverage < 0 (crossover)",
                          "side": -1, "null": 0.0, "kind": "slope", "level": "item",
                          "frame": lambda v, a=arm, t=t: variant(F.pooled(a, t), v)})
    for arm in TESTED:
        tests.append({"id": "Z1", "arm": arm, "t": "canon", "what": "item δ_C on pooled L1 of single_texto > 0",
                      "side": +1, "null": 0.0, "kind": "mean", "level": "item",
                      "frame": lambda v, a=arm: (lambda g: g[g["type"].isin(L1)])(
                          variant(F.T[(a, "single_texto", "canon")], v))})
    for arm in TESTED:
        tests.append({"id": "Z2", "arm": arm, "t": "canon", "what": "item δ_C on texto_u above the margin",
                      "side": +1, "null": MARGIN, "kind": "mean", "level": "item",
                      "frame": lambda v, a=arm: variant(F.T[(a, "texto_u", "canon")], v)})
    tests.append({"id": "G1", "arm": "bm25_unigram", "t": "idf_cap", "what": "parent δ on coded resumen_u > 0",
                  "side": +1, "null": 0.0, "kind": "mean", "level": "parent",
                  "frame": lambda v: variant(F.G[("bm25_unigram", "resumen_u")], v)})
    tests.append({"id": "G2", "arm": "bm25_unigram", "t": "idf_cap", "what": "item δ on single_texto above the margin",
                  "side": +1, "null": MARGIN, "kind": "mean", "level": "item",
                  "frame": lambda v: variant(F.G[("bm25_unigram", "single_texto")], v)})
    E = extraction_frames(F)
    tests.append({"id": "E1", "arm": "llm extractor", "t": "extract", "what": "item, LLM − rules_valuenorm, pooled L1 > 0",
                  "side": +1, "null": 0.0, "kind": "mean", "level": "item",
                  "frame": lambda v: (lambda g: g[g["type"].isin(L1)])(variant(E["vs_rules"], v))})
    tests.append({"id": "E2", "arm": "llm extractor", "t": "extract", "what": "item, LLM − bm25_unigram, pooled L1 > 0",
                  "side": +1, "null": 0.0, "kind": "mean", "level": "item",
                  "frame": lambda v: (lambda g: g[g["type"].isin(L1)])(variant(E["vs_bm25"], v))})
    return tests


def extraction_frames(F: Frames) -> dict[str, pd.DataFrame]:
    Q = F.Q["single_texto"]
    mod = ("single_texto", LLM_ARM)
    return {"vs_rules": pair(Q, mod, ("single_texto", RULES_ARM)),
            "vs_bm25": pair(Q, mod, ("single_texto", ARM_DIR["bm25_unigram"]))}


def evaluate(F: Frames, fl: dict[str, float]) -> list[dict]:
    results = []
    for spec in registered(F):
        row = {k: spec[k] for k in ("id", "arm", "t", "what", "side", "null", "level")}
        row["floor"] = spec["arm"] in fl and fl[spec["arm"]] < FLOOR
        for v in VARIANTS:
            frame = spec["frame"](v)
            label = f"{spec['id']}|{spec['arm']}|{spec['t']}|{v}"
            if spec["kind"] == "slope":
                fit = crossover(frame, label)
                cell = {"est": fit["slope"], "c": fit["slope_c"], "q": fit["slope_q"], "draws": fit["draws"],
                        "n": fit["n"], "concepts": fit["concepts"], "excluded": len(frame) - fit["n"]}
            else:
                cell = delta_cell(frame, spec["level"], label)
            cell["p"] = test_p(cell["draws"], spec["null"]) if len(cell["draws"]) else 1.0
            cell["tested"] = not row["floor"] and cell["concepts"] >= FEW_CLUSTERS
            row[v] = cell
        results.append(row)
    for v in VARIANTS:
        live = [r for r in results if r[v]["tested"]]
        for r, h, b in zip(live, holm([r[v]["p"] for r in live]), bh([r[v]["p"] for r in live])):
            r[v]["holm"], r[v]["bh"] = h, b
        for r in results:
            c = r[v]
            c["reading"] = read(c["c"], c["holm"], r["side"], r["null"]) if c["tested"] else "not tested"
    return results


# --------------------------------------------------------------------------- tables


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S9 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def footer() -> list[str]:
    return ["", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile intervals at level {1 - ALPHA:.0%}; concept-clustered "
            "(D-030) unless marked query-level. Split `dev`.", "", analysis_stack.stamp()]


def ncell(c: dict) -> str:
    return f"{c['n_all']:,} | {c['n']:,} | {c['excluded']:,} | {c['concepts']}"


def write_profile(F: Frames, fl: dict[str, float]) -> None:
    lines = header("T1: profile — every arm, base and transform against its untransformed reference", [
        "Paired on the same queries (A5 b). Tie-free primary; as-run δ beside. Item level excludes D-033 golds, "
        "D-040 on the `resumen` family and S4's P7 query; n excluded per row. † oracle arm (D-010): profiled, "
        "never tested. Collisions: queries whose transformed text equals another gold's (counted, not excluded)."])
    floor_line = ", ".join(f"`{a}` {f4(fl[a])}" for a in BASE7)
    lines += [f"Identity item Acc@1 on `texto_u`, tie-free, per arm (floor below {FLOOR}): {floor_line}.", ""]
    lines += ["| arm | base | transform | n | n scored | n excluded | concepts | item ref | item mod | item δ "
              "| CI (concept) | CI (query) | item δ as run | parent ref | parent mod | parent δ | CI (concept) | collisions "
              "| parent CI (query) |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|---:|---|"]
    for arm in BASE7:
        mark = "†" if arm in ORACLE else ""
        for base in S9_BASES:
            for t in TRANSFORMS:
                f = F.T[(arm, base, t)]
                ci_ = delta_cell(variant(f, "tf"), "item", f"T1|{arm}|{base}|{t}")
                cr = delta_cell(variant(f, "run"), "item", f"T1r|{arm}|{base}|{t}")
                cp = delta_cell(variant(f, "tf"), "parent", f"T1p|{arm}|{base}|{t}")
                coll = text_collisions(json.loads((DATA / f"OE_{base}__{t}.json").read_text(encoding="utf-8")))
                lines.append(f"| `{arm}`{mark} | `{base}` | {T_LABEL[t]} | {ncell(ci_)} | {f4(ci_['ref'])} | "
                             f"{f4(ci_['mod'])} | {fd(ci_['est'])} | {fci(ci_['c'], True)} | {fci(ci_['q'], True)} | "
                             f"{fd(cr['est'])} | {f4(cp['ref'])} | {f4(cp['mod'])} | {fd(cp['est'])} | "
                             f"{fci(cp['c'], True)} | {coll:,} | {fci(cp['q'], True)} |")
    write(OUT / "profile.md", lines + footer())


def write_bins(F: Frames) -> None:
    edges = "; ".join(f"{name} [{lo:.2f}, {min(hi, 1.0):.2f}{']' if hi > 1 else ')'}" for name, lo, hi in BINS)
    lines = header("T2: item δ by overlap bin", [
        f"Bins on the untransformed query's lexical coverage of its gold (S3's definition), over the non-identity "
        f"bases pooled: {edges}. B5 is `texto_u`, the identity rendering. Tie-free. ‡ fewer than "
        f"{FEW_CLUSTERS} concepts: printed, not read. † oracle arm."])
    lines += ["| arm | transform | bin | n | n scored | n excluded | concepts | item δ | CI (concept) | CI (query) | |",
              "|---|---|---|---:|---:|---:|---:|---:|---|---|---|"]
    for arm in BASE7:
        mark = "†" if arm in ORACLE else ""
        for t in TRANSFORMS:
            pooled = variant(F.pooled(arm, t), "tf")
            cells = [(name, _bin(pooled, name)) for name, _, _ in BINS]
            cells.append(("B5", variant(F.T[(arm, "texto_u", t)], "tf")))
            for name, f in cells:
                c = delta_cell(f, "item", f"T2|{arm}|{t}|{name}")
                thin = "‡" if c["concepts"] < FEW_CLUSTERS else ""
                lines.append(f"| `{arm}`{mark} | {T_LABEL[t]} | {name} | {ncell(c)} | {fd(c['est'])} | "
                             f"{fci(c['c'], True)} | {fci(c['q'], True)} | {thin} |")
    write(OUT / "bins.md", lines + footer())


def write_crossover(F: Frames) -> list[dict]:
    lines = header("T3: the crossover — item δ against coverage", [
        "OLS of per-query item δ on the untransformed query's lexical coverage over the non-identity bases pooled "
        "(A5 e), tie-free. c* is the coverage where the fitted δ is zero; its interval is over the draws whose "
        "slope is negative. c* outside the observed coverage range reads *no crossing in range*. The crossover is "
        "observational: coverage co-varies with base and type (design). Per-base slopes below are descriptive."])
    lines += ["| arm | transform | n scored | concepts | slope | CI (concept) | CI (query) | intercept | c* "
              "| c* CI (concept) | draws with slope < 0 | coverage range | c* in range |",
              "|---|---|---:|---:|---:|---|---|---:|---:|---|---:|---|---|"]
    fits = []
    for arm in TESTED:
        for t in ("hyde", "rewrite", "canon"):
            # Y3's own draws for H and W (A6), so that T3, T9 and Fig. 7 quote one interval per statistic.
            label = f"Y3|{arm}|{t}|tf" if t != "canon" else f"T3|{arm}|{t}"
            fit = crossover(variant(F.pooled(arm, t), "tf"), label)
            fits.append({"arm": arm, "t": t, **fit})
            lo, hi = fit["range"]
            lines.append(f"| `{arm}` | {T_LABEL[t]} | {fit['n']:,} | {fit['concepts']} | {fd(fit['slope'])} | "
                         f"{fci(fit['slope_c'], True)} | {fci(fit['slope_q'], True)} | {fd(fit['icept'])} | "
                         f"{f4(fit['cstar'])} | {fci(fit['cstar_c'])} | {fit['neg_share']:.1%} | "
                         f"[{f4(lo)}, {f4(hi)}] | {'yes' if fit['in_range'] else 'no crossing in range'} |")
    lines += ["", "## Per base, descriptive", "", "| arm | transform | base | n scored | concepts | slope | CI (concept) | CI (query) |",
              "|---|---|---|---:|---:|---:|---|---|"]
    for arm in TESTED:
        for t in ("hyde", "rewrite"):
            for base in NONID:
                fit = crossover(variant(F.T[(arm, base, t)], "tf"), f"T3b|{arm}|{t}|{base}")
                lines.append(f"| `{arm}` | {T_LABEL[t]} | `{base}` | {fit['n']:,} | {fit['concepts']} | "
                             f"{fd(fit['slope'])} | {fci(fit['slope_c'], True)} | {fci(fit['slope_q'], True)} |")
    write(OUT / "crossover.md", lines + footer())
    return fits


def canon_actions(dev: frozenset[str]) -> dict[str, pd.DataFrame]:
    """Per query of each synthetic base, what C did, re-derived and checked against the stored canon set."""
    from query_rewrite.canon import from_corpus
    c = from_corpus()
    out = {}
    for base in ("single_texto", "single_l2_texto", "stacked_texto"):
        stored = {r["item_key"]: r["text"] for r in records(f"{base}__canon", dev)}
        rows = []
        for r in records(base, dev):
            text, rep = c.apply(r["text"])
            if text != stored[r["item_key"]]:
                raise ValueError(f"{base}: the canonicaliser no longer reproduces the stored text of {r['item_key']}")
            rows.append({"key": r["item_key"], "changed": text != r["text"], "numbers": rep.numbers,
                         "units": rep.units, "converted": rep.converted, "declined": rep.declined})
        out[base] = pd.DataFrame(rows).set_index("key")
    return out


def write_canon(F: Frames, actions: dict[str, pd.DataFrame]) -> None:
    lines = header("T4: the canonicaliser by type", [
        "Item δ_C (C − untransformed) per single type, tie-free. Beside it, the damage C works against: the "
        "untransformed query's δ against the identity rendering of its gold (S4's pairing, recomputed here on the "
        "same queries). What C did per type is re-derived with the committed canonicaliser and checked equal to "
        "the stored set. Types are read for analysis only; C never sees them."])
    lines += ["| arm | base | type | n | n scored | concepts | changed by C (of n) | conversions | declined | item δ_C "
              "| CI (concept) | identity-paired δ | CI (concept) | δ_C CI (query) | identity-paired CI (query) |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|"]
    for arm in TESTED:
        for base in ("single_texto", "single_l2_texto"):
            f = variant(F.T[(arm, base, "canon")], "tf")
            ident = F.T[(arm, "texto_u", "canon")]
            ref_of_gold = variant(ident, "tf").set_index("gold")["ref_item"]
            act = actions[base]
            for typ in sorted(f["type"].unique()):
                g = f[f["type"] == typ]
                c = delta_cell(g, "item", f"T4|{arm}|{base}|{typ}")
                s = scored(g, "item")
                h = s.copy()
                h["mod_item"] = s["ref_item"]
                h["ref_item"] = s["gold"].map(ref_of_gold).astype(float)
                ip = delta_cell(h, "item", f"T4i|{arm}|{base}|{typ}")
                a = act.loc[g.index]
                lines.append(f"| `{arm}` | `{base}` | `{typ}` | {c['n_all']:,} | {c['n']:,} | {c['concepts']} | {int(a['changed'].sum()):,} | "
                             f"{int(a['converted'].sum()):,} | {int(a['declined'].sum()):,} | {fd(c['est'])} | "
                             f"{fci(c['c'], True)} | {fd(ip['est'])} | {fci(ip['c'], True)} | {fci(c['q'], True)} | "
                             f"{fci(ip['q'], True)} |")
    write(OUT / "canon_types.md", lines + footer())


def write_guard(F: Frames, diag: list) -> None:
    lines = header("T5: the IDF guard, and why TF-IDF escapes the rare-code pattern (D-041)", [
        "First the diagnostic (`utils.idf_diagnostic`, descriptive): on dev coded `resumen`, each arm's "
        "parent misses, the share of the rank-1 score carried by rare query tokens (S91's rule: in fewer than "
        f"{idf_diagnostic.RARE_MAX_DOCS:,} corpus documents), and the median IDF the arm gives rare and other "
        "query tokens. Then the guard: `idf_cap_df` at that cut, against the uncapped arm, paired."])
    lines += ["| arm | parent misses | share: lower quartile | median | upper quartile | misses with share above half "
              "| median IDF, rare tokens | median IDF, other tokens | ratio |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for a in diag:
        q = np.percentile(a.rare_share, [25, 50, 75])
        lines.append(f"| `{a.arm}` | {a.misses:,} | {f4(q[0])} | {f4(q[1])} | {f4(q[2])} | "
                     f"{np.mean(a.rare_share > 0.5):.1%} | {f4(a.rare_idf)} | {f4(a.other_idf)} | "
                     f"{a.rare_idf / a.other_idf:.2f} |")
    lines += ["", "## Vocabulary the cap reaches", "", "| config | vocabulary | terms capped | cap |", "|---|---:|---:|---:|"]
    for arm, d in GUARD.items():
        plain = np.load(INDEX / ARM_DIR[arm] / "data" / "idf.npy")
        capped = np.load(INDEX / d / "data" / "idf.npy")
        lines.append(f"| `{d}` | {len(plain):,} | {int((plain > capped).sum()):,} | {f4(float(capped.max()))} |")
    lines += ["", "## The guard against the uncapped arm, every base", "",
              "| arm | base | level | n | n scored | n excluded | concepts | uncapped | capped | δ | CI (concept) | CI (query) |",
              "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for arm in GUARD:
        for base in S9_BASES:
            for level in ("item", "parent"):
                c = delta_cell(variant(F.G[(arm, base)], "tf"), level, f"T5|{arm}|{base}|{level}")
                lines.append(f"| `{arm}` | `{base}` | {level} | {ncell(c)} | {f4(c['ref'])} | {f4(c['mod'])} | "
                             f"{fd(c['est'])} | {fci(c['c'], True)} | {fci(c['q'], True)} |")
    write(OUT / "idf_guard.md", lines + footer())


def write_extraction(F: Frames) -> None:
    lines = header("T6: slot filling — the LLM extractor as Stage 2 of `rules_valuenorm`", [
        "`structured_pipeline_llm_valuenorm__OE` (phi4, `extract`, ported from `research/structured-retrieval@85c3359`; "
        "its prompts were chosen on OEB `resumen`, whose concepts sit on both sides of OE's split) against "
        "`rules_valuenorm` (same pipeline, rules Stage 2), `bm25_unigram`, and S5's oracle-extraction bound, "
        "paired on the same queries, tie-free. A reference without a run on a base is left blank."])
    E = extraction_frames(F)
    lines += ["| comparison | scope | n | n scored | n excluded | concepts | reference | LLM arm | δ | CI (concept) | CI (query) |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    Q = F.Q["single_texto"]
    refs = [("vs rules_valuenorm", E["vs_rules"]), ("vs bm25_unigram", E["vs_bm25"]),
            ("vs oracle bound", pair(Q, ("single_texto", LLM_ARM), ("single_texto", ORACLE_BOUND)))]
    for name, frame in refs:
        for scope_name, sel in (("L1", L1), ("all single types", None)):
            f = variant(frame, "tf")
            f = f[f["type"].isin(sel)] if sel else f
            c = delta_cell(f, "item", f"T6|{name}|{scope_name}")
            lines.append(f"| {name} | {scope_name} | {ncell(c)} | {f4(c['ref'])} | {f4(c['mod'])} | {fd(c['est'])} | "
                         f"{fci(c['c'], True)} | {fci(c['q'], True)} |")
    lines += ["", "## Profile on every base", "", "| base | LLM arm item | LLM arm parent | rules_valuenorm item | n scored |",
              "|---|---:|---:|---:|---:|"]
    for base in S9_BASES:
        Qb = F.Q[base]
        own = variant(pair(Qb, (base, LLM_ARM), (base, LLM_ARM)), "tf")
        rq = REF_QS.get(base, base)
        rules = ""
        if (RUNS / rq / RULES_ARM / "results_perquery.parquet").exists():
            rules = f4(scored(variant(pair(Qb, (base, LLM_ARM), (rq, RULES_ARM)), "tf"), "item")["ref_item"].mean())
        lines.append(f"| `{base}` | {f4(scored(own, 'item')['mod_item'].mean())} | "
                     f"{f4(scored(own, 'parent')['mod_parent'].mean())} | {rules} | {int(own['item_scored'].sum()):,} |")
    lines += keytol_section(F)
    write(OUT / "extraction.md", lines + footer())


#: `phi4:latest`'s full digest, the one every extractor run used (A4's log, the runs' client); its prefix is
#: the design's (`query_rewrite.llm.MODELS`), asserted. The cache key needs the full digest.
PHI4_DIGEST = "ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba"


def axis_outcomes(F: Frames) -> pd.DataFrame:
    """Per query and schema axis of its Stage-1 concept, how the cached response names the axis (A7).

    The Stage-1 concept is the registered run's rank-1 concept (S2's consistency, `structured_stages`); the
    prompt is rebuilt as the pipeline built it, and its response is read from the cache. A prompt absent from
    the cache stops the generator: the runs read every one."""
    from pipeline.param_extractor import LLMParamExtractor
    from pipeline.prompts import build_extraction_prompt
    from query_rewrite import llm as L
    if not PHI4_DIGEST.startswith(L.MODELS["phi4:latest"]):
        raise ValueError("PHI4_DIGEST does not carry the design's prefix")
    schema = json.loads((DATA / "OE_concept_schema.json").read_text(encoding="utf-8"))
    cache = {}
    for line in (DATA / "llm_cache" / "structured_llm_extract.jsonl").read_text(encoding="utf-8").splitlines():
        if line:
            r = json.loads(line)
            cache[r["cache_key"]] = r["response"]
    _, parents = corpus()
    rows = []
    for base in S9_BASES:
        feats = pd.read_parquet(DATA / f"OE_{base}_feats.parquet", columns=["item_key", "text_norm"]).set_index("item_key")
        keys = set(F.Q[base].index)
        from utils.build_results_s7 import iter_top100
        for r in iter_top100(RUNS / base / LLM_ARM):
            k = str(r["query_item_key"])
            if k not in keys:
                continue
            concept = parents[str(r["candidates"][0]["index_item_key"])]
            g = schema[concept]
            prompt = build_extraction_prompt(g["concept"], g["axes"], feats.loc[k, "text_norm"])
            ck = L.sha256_text(json.dumps([PHI4_DIGEST, L.OPTIONS, None, prompt], ensure_ascii=False, sort_keys=True))
            if ck not in cache:
                raise KeyError(f"{base}/{k}: its extraction prompt is not in the cache")
            parsed = LLMParamExtractor._parse_json_response(cache[ck]) or {}
            for axis in g["axes"]:
                if axis in parsed:
                    kind = "exact"
                elif any(key.strip() == axis.strip() for key in parsed):
                    kind = "trimmed"
                elif any(LLMParamExtractor._key(key) == LLMParamExtractor._key(axis) for key in parsed):
                    kind = "renamed"
                else:
                    kind = "absent"
                rows.append({"base": base, "key": k, "axis_padded": axis != axis.strip(), "kind": kind})
    return pd.DataFrame(rows)


def keytol_section(F: Frames) -> list[str]:
    """A7: why the registered extractor drops axes, and the key-tolerant variant. Post hoc, descriptive."""
    out = axis_outcomes(F)
    lines = ["", "## Post hoc (A7): why the extractor drops axes, and a key-tolerant variant", "",
             "Added after this table was first read, at César's decision; descriptive: no test, no Holm, no reading, "
             "no bearing on E1, E2 or H6. The registered arm reads each axis from the response under its schema name "
             "exactly, as the source does. For every query, each axis of its Stage-1 concept, by how the cached "
             "response names it: *exact*; *trimmed*, equal only once surrounding spaces are removed (the schema "
             "carries axis names with stray spaces, and the model writes them without); *renamed*, equal only under "
             "A7's tolerant form (case-folded, accents stripped, `_` and `-` as spaces); *absent*. The registered "
             "arm reads only *exact*; the variant reads all but *absent*.", "",
             "| base | axes | exact | trimmed | renamed | absent | lost by the registered arm | of them, on a padded schema name |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for base in list(S9_BASES) + ["all"]:
        f = out if base == "all" else out[out["base"] == base]
        k = f["kind"].value_counts()
        lost = f[f["kind"].isin(["trimmed", "renamed"])]
        label = "all bases" if base == "all" else f"`{base}`"
        lines.append(f"| {label} | {len(f):,} | {k.get('exact', 0):,} | {k.get('trimmed', 0):,} | {k.get('renamed', 0):,} | "
                     f"{k.get('absent', 0):,} | {len(lost):,} ({len(lost) / len(f):.1%}) | {int(lost['axis_padded'].sum()):,} |")
    lines += ["", "The variant reads the same cached responses (no new generation; the run script checked that the cache "
              "did not grow) and differs from the registered arm only in that match. Paired, tie-free, on "
              "`single_texto`:", "",
              "| comparison | scope | n | n scored | n excluded | concepts | reference | variant | δ | CI (concept) | CI (query) |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    Q = F.Q["single_texto"]
    mod = ("single_texto", KEYTOL_ARM)
    for name, ref in (("vs the registered LLM arm", LLM_ARM), ("vs rules_valuenorm", RULES_ARM),
                      ("vs bm25_unigram", ARM_DIR["bm25_unigram"]), ("vs oracle bound", ORACLE_BOUND)):
        frame = pair(Q, mod, ("single_texto", ref))
        for scope_name, sel in (("L1", L1), ("all single types", None)):
            f = variant(frame, "tf")
            f = f[f["type"].isin(sel)] if sel else f
            c = delta_cell(f, "item", f"T6k|{name}|{scope_name}")
            lines.append(f"| {name} | {scope_name} | {ncell(c)} | {f4(c['ref'])} | {f4(c['mod'])} | {fd(c['est'])} | "
                         f"{fci(c['c'], True)} | {fci(c['q'], True)} |")
    lines += ["", "Every base, item and parent Acc@1, tie-free, beside the registered arm:", "",
              "| base | variant item | variant parent | registered item | n scored |", "|---|---:|---:|---:|---:|"]
    for base in S9_BASES:
        f = variant(pair(F.Q[base], (base, KEYTOL_ARM), (base, LLM_ARM)), "tf")
        lines.append(f"| `{base}` | {f4(scored(f, 'item')['mod_item'].mean())} | {f4(scored(f, 'parent')['mod_parent'].mean())} | "
                     f"{f4(scored(f, 'item')['ref_item'].mean())} | {int(f['item_scored'].sum()):,} |")
    return lines


def write_cost() -> None:
    lines = header("T7: cost, and what the generation did", [
        "Per LLM set, from its provenance sidecar and generation cache: queries, fallbacks (a response that did "
        "not parse; the query keeps its text, A3), outputs cut by `num_predict`, outputs with non-Latin script "
        "(CJK or Cyrillic; kept, not repaired), and generation time. Then retrieval wall-clock from each run's "
        "`run_meta.json`. Nothing here is excluded from any test."])
    lines += ["| set | model | prompt | n | fallback | truncated | non-Latin | seconds, total | seconds per query, median "
              "| generated tokens |", "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for t in ("hyde", "rewrite"):
        for base in S9_BASES:
            m = json.loads((DATA / f"OE_{base}__{t}.meta.json").read_text(encoding="utf-8"))
            gen = json.loads((DATA / f"OE_{base}__{t}.json").read_text(encoding="utf-8"))
            nonlatin = sum(bool(NONLATIN.search(r["text"])) for r in gen)
            lines.append(f"| `{base}__{t}` | `{m['model']}` `{m['model_digest'][:12]}` | `{m['prompt_sha256'][:8]}` | "
                         f"{m['n']:,} | {m['fallback']} | {m['truncated']} | {nonlatin} | {m['seconds_total']:,.0f} | "
                         f"{m['seconds_median']:.2f} | {m['eval_tokens_total']:,} |")
    cache = [json.loads(l) for l in (DATA / "llm_cache" / "structured_llm_extract.jsonl").read_text(encoding="utf-8").splitlines() if l]
    secs = [r["seconds"] for r in cache]
    lines.append(f"| extractor (all bases) | `phi4:latest` | source `extract` | {len(cache):,} | — | "
                 f"{sum(r['done_reason'] == 'length' for r in cache)} | — | {sum(secs):,.0f} | {np.median(secs):.2f} | "
                 f"{sum(r.get('eval_count') or 0 for r in cache):,} |")
    lines += ["", "## Retrieval wall-clock, seconds per query", "", "| arm | untransformed | C | H | W |", "|---|---:|---:|---:|---:|"]
    for arm in BASE7:
        cells = []
        for t in (None,) + TRANSFORMS:
            tot = q = 0
            for base in S9_BASES:
                qs = REF_QS.get(base, base) if t is None else f"{base}__{t}"
                m = run_meta(qs, ARM_DIR[arm])
                tot += m["elapsed_s"]
                q += m["queries"]
            cells.append(f"{tot / q:.4f}")
        lines.append(f"| `{arm}` | " + " | ".join(cells) + " |")
    write(OUT / "cost.md", lines + footer())


def write_d004(F: Frames, results: list[dict]) -> None:
    lines = header("T8: D-004 sensitivity", [
        "Every registered test recomputed without the queries whose untransformed text carries a pantry artefact "
        "(S3's detector: token doubling, the topo drift). A reading that changes category is *not robust*; the "
        "full-population reading stands."])
    lines += ["| base | queries | flagged |", "|---|---:|---:|"]
    for base in S9_BASES:
        q = F.Q[base]
        lines.append(f"| `{base}` | {len(q):,} | {int(q['flagged'].sum()):,} |")
    lines += ["", "| test | arm | transform | tie-free | reading | clean | CI (concept) | reading | robust |",
              "|---|---|---|---:|---|---:|---|---|---|"]
    for r in results:
        a, c = r["tf"], r["clean"]
        lines.append(f"| {r['id']} | `{r['arm']}` | {r['t']} | {fd(a['est'])} | {a['reading']} | {fd(c['est'])} | "
                     f"{fci(c['c'], True)} | {c['reading']} | {'yes' if a['reading'] == c['reading'] else 'not robust'} |")
    write(OUT / "d004.md", lines + footer())


def write_predictions(results: list[dict], fits: list[dict]) -> None:
    lines = header("T9: the registered predictions", [
        f"The design's {len(results)} tests, all blind. S4's rule (A5 g): Holm and BH across the tests read in "
        "each column; a floor arm, or a cell with fewer than "
        f"{FEW_CLUSTERS} concepts, reads *not tested* and takes no part. Z2 and G2 are non-inferiority tests "
        f"against a margin of {MARGIN:+.2f}. ⚑ the tie-free and as-run readings differ."])
    lines += ["| test | arm | transform | prediction | n | n scored | n excluded | concepts | estimate | CI (concept) "
              "| CI (query) | p | Holm | BH | reading | as run | as-run reading | |",
              "|---|---|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---|---:|---|---|"]
    for r in results:
        a, b = r["tf"], r["run"]
        n_all = a["n"] + a["excluded"]
        holm_s = fp(a["holm"]) if a["tested"] else "—"
        bh_s = fp(a["bh"]) if a["tested"] else "—"
        flag = "⚑" if a["reading"] != b["reading"] else ""
        lines.append(f"| {r['id']} | `{r['arm']}` | {r['t']} | {r['what']} | {n_all:,} | {a['n']:,} | {a['excluded']:,} | "
                     f"{a['concepts']} | {fd(a['est'])} | {fci(a['c'], True)} | {fci(a['q'], True)} | {fp(a['p'])} | "
                     f"{holm_s} | {bh_s} | {a['reading']} | {fd(b['est'])} | {b['reading']} | {flag} |")
    lines += ["", "## H6, by the design's rule", ""]
    for t in ("hyde", "rewrite"):
        rows = [r for r in results if r["t"] == t and r["id"] in ("Y1", "Y2", "Y3")]
        arms = sorted({r["arm"] for r in rows if r["tf"]["tested"]})
        def held(tid: str) -> set[str]:
            return {r["arm"] for r in rows if r["id"] == tid and r["tf"]["reading"] == "supported"}
        all3 = held("Y1") & held("Y2") & held("Y3")
        y1_contra = {r["arm"] for r in rows if r["id"] == "Y1" and r["tf"]["reading"] == "contradicted"}
        half = len(arms) / 2
        if arms and len(all3) > half:
            label = "supported"
        elif arms and len(y1_contra) > half:
            label = "contradicted"
        else:
            label = "partly supported"
        names = lambda s: ", ".join(f"`{a}`" for a in sorted(s)) or "none"
        lines.append(f"- **{T_LABEL[t]} ({t})**: {label}. Tested arms: {names(arms)}. Y1 supported for {names(held('Y1'))}; "
                     f"Y2 for {names(held('Y2'))}; Y3 for {names(held('Y3'))}; all three for {names(all3)}; "
                     f"Y1 contradicted for {names(y1_contra)}.")
    lines += ["", "## The decision rule: c* per arm and transform (from T3)", ""]
    for fit in fits:
        if fit["t"] == "canon":
            continue
        where = (f"c* = {f4(fit['cstar'])} {fci(fit['cstar_c'])}" if fit["in_range"] else "no crossing in range")
        lines.append(f"- `{fit['arm']}`, {T_LABEL[fit['t']]}: slope {fd(fit['slope'])} {fci(fit['slope_c'], True)}; {where}.")
    write(OUT / "predictions.md", lines + footer())


def write_provenance(F: Frames) -> None:
    lines = header("T10: provenance", [
        "Every run these tables read, with its stamp, then the data files, model digests and prompt hashes. "
        "References (`texto`, `resumen`, the synthetic bases) are the earlier sprints' runs, unchanged."])
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
    inputs = [CORPUS_JSON, DATA / "OE_resumen_decoded.json", DATA / "OE_duplicate_texto_groups.json",
              REPO / "docs" / "synthetic-oe" / "SPLITS.md", DATA / "llm_cache" / "structured_llm_extract.jsonl"]
    inputs += [DATA / f"OE_{b}.json" for b in S9_BASES]
    inputs += [DATA / f"OE_{b}__{t}.json" for b in S9_BASES for t in TRANSFORMS]
    for p in inputs:
        lines.append(f"| `{p.relative_to(REPO).as_posix()}` | `{sha256_file(p)[:16]}` |")
    lines += ["", "| LLM set | model digest | ollama | prompt SHA-256 | options |", "|---|---|---|---|---|"]
    for t in ("hyde", "rewrite"):
        for base in S9_BASES:
            m = json.loads((DATA / f"OE_{base}__{t}.meta.json").read_text(encoding="utf-8"))
            lines.append(f"| `{base}__{t}` | `{m['model_digest'][:16]}` | {m['ollama_version']} | `{m['prompt_sha256'][:16]}` | "
                         f"`{json.dumps(m['options'], sort_keys=True)}` |")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "src"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    lines += ["", f"Generator commit `{commit}`, `src/` {'dirty' if dirty else 'clean'}."]
    write(OUT / "run_provenance.md", lines + footer())


def write_overlap(F: Frames) -> None:
    frame = pd.concat([F.Q[b][["base", "gold", "concept", "type", "cov", "numcov", "flagged"]] for b in S9_BASES])
    frame.reset_index().to_parquet(OUT / "overlap_per_query.parquet", index=False)


def write_figure(F: Frames, fits: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGS.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(TESTED), figsize=(3.2 * len(TESTED), 3.2), sharey=True)
    mids = [(lo + min(hi, 1.0)) / 2 for _, lo, hi in BINS]
    for ax, arm in zip(axes, TESTED):
        for t, colour in (("hyde", "#3b6ea8"), ("rewrite", "#c2622d")):
            pooled = variant(F.pooled(arm, t), "tf")
            est, lo, hi = [], [], []
            for name, _, _ in BINS:
                c = delta_cell(_bin(pooled, name), "item", f"T2|{arm}|{t}|{name}")
                est.append(c["est"]); lo.append(c["c"][0]); hi.append(c["c"][1])
            est, lo, hi = map(np.array, (est, lo, hi))
            ax.errorbar(mids, est, yerr=[est - lo, hi - est], fmt="o", color=colour, label=T_LABEL[t], capsize=2)
            fit = next(f for f in fits if f["arm"] == arm and f["t"] == t)
            xs = np.linspace(*fit["range"], 50)
            ax.plot(xs, fit["icept"] + fit["slope"] * xs, color=colour, lw=1)
            if fit["in_range"]:
                ax.axvline(fit["cstar"], color=colour, ls=":", lw=1)
            b5 = delta_cell(variant(F.T[(arm, "texto_u", t)], "tf"), "item", f"T2|{arm}|{t}|B5")
            ax.plot([1.0], [b5["est"]], marker="s", color=colour, mfc="none")
        ax.axhline(0, color="grey", lw=0.5)
        ax.set_title(arm, fontsize=9)
        ax.set_xlabel("lexical coverage (untransformed)")
    axes[0].set_ylabel("item δ (tie-free)")
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGS / "fig7_crossover.png", dpi=150, metadata={"Software": None})
    plt.close(fig)


def main() -> None:
    analysis_stack.require()
    OUT.mkdir(parents=True, exist_ok=True)
    dev = load_split("dev")
    F = Frames(dev)
    fl = floors(F)
    results = evaluate(F, fl)
    write_profile(F, fl)
    write_bins(F)
    fits = write_crossover(F)
    write_canon(F, canon_actions(dev))
    write_guard(F, idf_diagnostic.run())
    write_extraction(F)
    write_cost()
    write_d004(F, results)
    write_predictions(results, fits)
    write_overlap(F)
    write_figure(F, fits)
    write_provenance(F)
    print(f"written: {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
