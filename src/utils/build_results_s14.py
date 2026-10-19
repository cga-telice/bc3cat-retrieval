"""S14 — External rendering: back-translated queries. T1–T11 and Fig. 9 (design frozen 2026-10-19).

Every number the S14 report states is generated here from `runs/`, never typed. The population is the dev side of
`bt_texto` (one back-translated rendering per STACKED-P leaf), paired leaf for leaf with (a) the same arm's
STACKED-P v2 query of the same leaf (`stacked_texto_v2`, the S7 A8 / S11 A7 runs) and (b) the same arm's identity
result on the gold (`texto`; `texto_u` for the S11 arms). Tie-free Acc@1 is the reading (D-028 note), as run
beside it; concept-clustered percentile intervals (D-030), the query-level interval printed and never read; item
level excludes the D-033 golds. The oracle arms (D-010) read `parameters`, which on BT hold the gold's own values
(`DELIVERIES.md`, 2026-10-16): they are printed as upper bounds with that asymmetry stated and enter no test
(César, 2026-10-19).

Two modes:

    python src/utils/build_results_s14.py --fix-pairs   # Stage P, before any BT run is read
    python src/utils/build_results_s14.py               # T1–T11, Fig. 9, the registered readings

**Stage P** (`--fix-pairs`) reads no BT run. On dev STACKED-P v2 restricted to the leaves BT pairs, it computes
the ten contrasts among the five non-oracle base arms, each oriented so that the arm with the higher tie-free item
Acc@1 comes first, with concept-clustered intervals and Holm within the ten; P is the set of contrasts that read
*supported*. It writes `pairs_stacked_p.md` and `pairs_stacked_p.json`; the amendments file lists P from them.
The full run refuses to start without that file and re-derives P, asserting it reproduces.

**Registered tests** (design, Design constraints), one Holm family per reading (tie-free; as run; F-BT-1-free; the
D-004-clean subset when the detector flags any BT query): B1 one contrast per pair in P, Acc(a) − Acc(b) > 0 on
BT, paired on the same item-scored leaves; B2 K2 − ColBERT > 0 on BT; B3 W1 and W2 (S7's H1 statistics) per base
arm with BT as the modification; B4 per base arm, item δ_BT − δ_STACKED-P > 0 per leaf. S4's rule reads each
test; B1's verdict follows the design's rule (preserved / partly preserved / contradicted). Floor arms (identity
item Acc@1 on the BT leaves below `FLOOR`) read *not tested*.

The analysis stack is pinned (`analysis_stack.py`): the script refuses to run on another.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(os.environ.get("BC3CAT_REPO") or Path(__file__).resolve().parents[2])  # the override is for development only
sys.path.insert(0, str(REPO / "src"))

from utils import analysis_stack  # noqa: E402
from utils.build_overlap import lexical_coverage  # noqa: E402
from utils.build_results_s2 import ALPHA, B, SEED, bh, boot_cluster, boot_query, ci, f4, fci, fd, fp, holm, write  # noqa: E402
from utils.build_results_s4 import ARMS as S4_ARMS, CORPUS_JSON, FEW_CLUSTERS, FLOOR, SIDECAR  # noqa: E402
from utils.build_results_s5 import ARMS as S5_ARMS  # noqa: E402
from utils.build_results_s6 import discrimination, test_p  # noqa: E402
from utils.build_results_s7 import parent_of, tie_table  # noqa: E402
from utils.build_results_s9 import BINS as COV_BINS  # noqa: E402
from utils.exclusions import duplicate_texto, stacked_p  # noqa: E402
from utils.pantry_flags import text_flags  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.exclusions import STACKED_P_EXCLUSION  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
RUNS = REPO / "runs" / "OE"
INDEX = REPO / "index" / "OE"
OUT = Path(os.environ.get("BC3CAT_S14_OUT") or REPO / "docs" / "synthetic-oe" / "results" / "S14")  # development override
FIGS = OUT / "figures"
GENERATOR = "src/utils/build_results_s14.py"
LOGS = REPO / "logs" / "S14"

BT, SP, IDENT, IDENT_S11 = "bt_texto", "stacked_texto_v2", "texto", "texto_u"
BT_JSON = DATA / "OE_bt_texto.json"
SP_JSON = DATA / "OE_stacked_texto_v2.json"
MODS_JSONL = DATA / "OE_bt_modifications.jsonl"
BT_FEATS = DATA / "OE_bt_texto_feats.parquet"
FAMILY_META = INDEX / "_colbert_family" / f"{BT}.meta.json"
FAMILY_NPZ = INDEX / "_colbert_family" / f"{BT}.npz"
DET_LOG = LOGS / "determinism_extract.json"
PAIRS_JSON = OUT / "pairs_stacked_p.json"

#: (run directory, short name, oracle, kind): the fifteen S4 arms, the three S5 structured arms, S11's K2, R2, F1.
ARMS = [(d, s, o, "derived" if dv else "base") for d, s, o, dv in S4_ARMS] + [
    (d, s, o, "structured") for d, s, o, st in S5_ARMS if st
] + [
    ("structured_pipeline_llm_keytol_soft_colbert__OE", "K2", False, "s11"),
    ("structured_pipeline_rules_canon_soft_colbert__OE", "R2", False, "s11"),
    ("structured_pipeline_colbert_in_concept__OE", "F1", False, "s11"),
]
DIR = {s: d for d, s, _, _ in ARMS}
KIND = {s: k for _, s, _, k in ARMS}
ORACLE = {s for _, s, o, _ in ARMS if o}
SHORTS = [s for _, s, _, _ in ARMS]
#: The five non-oracle base arms B1, B3 and B4 are registered on.
BASE5 = ("bm25_unigram", "bge_m3_colbert", "bge_m3_dense", "dense_e5", "dense_es_hiiamsid")
#: The ten unordered pairs; Stage P orients each.
PAIRS = [(a, b) for i, a in enumerate(BASE5) for b in BASE5[i + 1:]]
#: Readings: tie-free (the reading), as run, F-BT-1-free, and the D-004 clean subset.
VARIANTS = ("tf", "run", "nobt1", "clean")
VARIANT_LABEL = {"tf": "tie-free", "run": "as run", "nobt1": "F-BT-1-free", "clean": "D-004 clean"}
FRACTION_SPLIT = 0.5
FBT1_QUERY, FBT1_GOLD = "de hormigón", "hormigonada"


def ident_qs(short: str) -> str:
    return IDENT_S11 if KIND[short] == "s11" else IDENT


# --------------------------------------------------------------------------- inputs


def meta(queryset: str, short: str) -> dict:
    return json.loads((RUNS / queryset / DIR[short] / "run_meta.json").read_text(encoding="utf-8"))


def available(queryset: str, short: str) -> bool:
    return (RUNS / queryset / DIR[short] / "run_meta.json").is_file()


_PARENTS: dict = {}


def parents() -> dict[str, str]:
    if not _PARENTS:
        _PARENTS.update(parent_of())
    return _PARENTS


_HITS: dict = {}


def hits(queryset: str, short: str, keys: tuple[str, ...]) -> pd.DataFrame:
    """Tie-free and as-run hits of `keys` in a run, both levels, with the truncation flag (S7 A1 i)."""
    k = (queryset, short, keys)
    if k not in _HITS:
        run = RUNS / queryset / DIR[short]
        tf = tie_table(run, set(keys), parents())
        pq = pd.read_parquet(run / "results_perquery.parquet").set_index("query_item_key")
        missing = set(keys) - set(pq.index)
        if missing:
            raise KeyError(f"{queryset}/{short}: {len(missing)} queries absent from the run: {sorted(missing)[:3]}")
        out = pd.DataFrame({"item_tf": tf.loc[list(keys), "item_tf"].to_numpy(float),
                            "parent_tf": tf.loc[list(keys), "parent_tf"].to_numpy(float),
                            "item_run": pq.loc[list(keys), "item_acc1"].to_numpy(float),
                            "parent_run": pq.loc[list(keys), "parent_acc1"].to_numpy(float),
                            "truncated": tf.loc[list(keys), "truncated"].to_numpy(bool)}, index=list(keys))
        for level in ("item", "parent"):
            a, b = out[f"{level}_run"], out[f"{level}_tf"]
            if (((a == 1) & (b == 0)) | ((a == 0) & (b == 1))).any():
                raise ValueError(f"{queryset}/{short}/{level}: tie-free and as-run disagree on a certainty")
        _HITS[k] = out
    return _HITS[k]


def population(dev: frozenset[str]) -> pd.DataFrame:
    """One row per dev BT query: gold, concept, its STACKED-P v2 query, the strata and flags, the scoring masks."""
    corpus = {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}
    sp_rows = json.loads(SP_JSON.read_text(encoding="utf-8"))
    keep = stacked_p([r["item_key"] for r in sp_rows])
    sp_of: dict[str, str] = {}
    for r, k in zip(sp_rows, keep):
        if k and r["parent_key"] in dev:
            if r["gold_item_key"] in sp_of:
                raise ValueError(f"STACKED-P holds two dev queries of leaf {r['gold_item_key']}")
            sp_of[r["gold_item_key"]] = r["item_key"]
    mods = {}
    for line in MODS_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            m = json.loads(line)
            mods[m["item_key"]] = m["modifications"]
    dup = duplicate_texto()
    rows = []
    for r in json.loads(BT_JSON.read_text(encoding="utf-8")):
        if r["parent_key"] not in dev:
            continue
        gold = r["gold_item_key"]
        if gold not in sp_of:
            raise KeyError(f"{r['item_key']}: its leaf has no STACKED-P v2 dev query")
        types = set(r["modification_types"])
        flags = text_flags(r["text"], corpus[gold])
        rows.append({
            "q": r["item_key"], "gold": gold, "concept": r["parent_key"], "subchapter": gold[:3], "sp": sp_of[gold],
            "fraction": float(r["bt_sentences"]["fraction"]),
            "vbt": "value_back_translation" in types, "gs": "glossary_synonym" in types,
            "label_added": any(m.get("label_added") for m in mods[r["item_key"]]),
            # F-BT-1: the gold's «hormigonada» rendered as «de hormigón» — the query must have lost the token, or a gold
            # that carries both («paramentos de hormigón» beside «canalización hormigonada») is counted twice (audit F6)
            "fbt1": FBT1_QUERY in r["text"] and FBT1_GOLD in corpus[gold] and FBT1_GOLD not in r["text"],
            "flagged": bool(flags["doubled"] or flags["topo"]),
            "cov": lexical_coverage(r["text"], corpus[gold]),
            "item_scored": gold not in dup, "parent_scored": True,
        })
    Q = pd.DataFrame(rows).set_index("q").sort_index()
    Q["fbin"] = np.where(Q["fraction"] < FRACTION_SPLIT, f"< {FRACTION_SPLIT}",
                         np.where(Q["fraction"] > FRACTION_SPLIT, f"> {FRACTION_SPLIT}", f"= {FRACTION_SPLIT}"))
    Q["lists"] = np.select([Q["vbt"] & Q["gs"], Q["vbt"], Q["gs"]], ["value + glossary", "value only", "glossary only"],
                           "pure BT")
    Q["cbin"] = "—"
    for name, lo, hi in COV_BINS:
        Q.loc[(Q["cov"] >= lo) & (Q["cov"] < hi), "cbin"] = name
    return Q


class Frames:
    """The population and, per arm, its hits on BT (unless Stage P), on STACKED-P v2 and on the identity."""

    def __init__(self, dev: frozenset[str], read_bt: bool = True):
        self.Q = population(dev)
        self.read_bt = read_bt
        self.H: dict[str, pd.DataFrame] = {}
        q, sp, gold = tuple(self.Q.index), tuple(self.Q["sp"]), tuple(self.Q["gold"])
        for short in SHORTS:
            h = pd.DataFrame(index=self.Q.index)
            for side, qs, keys in (("sp", SP, sp), ("id", ident_qs(short), gold)) + (((("bt", BT, q),) if read_bt else ())):
                r = hits(qs, short, keys)
                for col in ("item_tf", "parent_tf", "item_run", "parent_run"):
                    h[f"{side}_{col}"] = r[col].to_numpy()
                h[f"{side}_truncated"] = r["truncated"].to_numpy()
            self.H[short] = h

    def frame(self, short: str, variant: str, mod: str | None = None) -> pd.DataFrame:
        """S7's paired frame under a reading: `item_mod`/`parent_mod` are the rendering's hits (`mod` = bt or sp),
        `item_id`/`parent_id` the identity's, plus the other rendering as `item_sp`/`item_bt`; rows per variant."""
        mod = mod or ("bt" if self.read_bt else "sp")
        hit = "run" if variant == "run" else "tf"
        h = self.H[short]
        f = self.Q.copy()
        for level in ("item", "parent"):
            f[f"{level}_mod"] = h[f"{mod}_{level}_{hit}"].to_numpy()
            f[f"{level}_id"] = h[f"id_{level}_{hit}"].to_numpy()
            f[f"{level}_sp"] = h[f"sp_{level}_{hit}"].to_numpy()
            if self.read_bt:
                f[f"{level}_bt"] = h[f"bt_{level}_{hit}"].to_numpy()
        if variant == "nobt1":
            f = f[~f["fbt1"]]
        elif variant == "clean":
            f = f[~f["flagged"]]
        return f


def item(f: pd.DataFrame) -> pd.DataFrame:
    return f[f["item_scored"]]


def nconc(f: pd.DataFrame) -> int:
    return int(f["concept"].nunique())


# --------------------------------------------------------------------------- statistics


_CELLS: dict = {}


def cell(frame: pd.DataFrame, level: str, label: str, mod: str = "mod") -> dict:
    """S6's cell: mean δ = rendering − identity on the level's scored queries, with both intervals and retention."""
    f = item(frame) if level == "item" else frame[frame["parent_scored"]]
    ident, m = f[f"{level}_id"].to_numpy(float), f[f"{level}_{mod}"].to_numpy(float)
    key = (label, level, mod, tuple(f.index))
    if key in _CELLS:
        return _CELLS[key]
    d = m - ident
    cols = np.column_stack([d, ident * m, ident])
    q = boot_query(cols, f"s14|{label}|{level}")
    c = boot_cluster(cols, f["concept"].to_numpy(), f"s14|{label}|{level}")
    kept = ident.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        ret_c = c[:, 1] / c[:, 2]
    ret_c = ret_c[np.isfinite(ret_c)]
    out = {"n_all": len(frame), "n": len(f), "excluded": len(frame) - len(f), "concepts": nconc(f),
           "id": float(ident.mean()), "mod": float(m.mean()), "delta": float(d.mean()),
           "q": ci(q[:, 0]), "c": ci(c[:, 0]), "draws": c[:, 0],
           "retention": float((ident * m).sum() / kept) if kept else float("nan"),
           "ret_c": ci(ret_c) if len(ret_c) else (float("nan"), float("nan")),
           "down": int(((ident == 1) & (m == 0)).sum()), "up": int(((ident == 0) & (m == 1)).sum())}
    _CELLS[key] = out
    return out


def mean_test(values: np.ndarray, f: pd.DataFrame, label: str) -> dict:
    """A registered mean > 0: estimate, concept draws, query draws, p, n, concepts."""
    c = boot_cluster(values[:, None], f["concept"].to_numpy(), f"s14|{label}")[:, 0]
    q = boot_query(values[:, None], f"s14|{label}")[:, 0]
    c = c[np.isfinite(c)]
    return {"est": float(values.mean()), "c": ci(c), "q": ci(q[np.isfinite(q)]), "p": test_p(c), "n": len(f),
            "concepts": nconc(f), "draws": c, "clusters_key": tuple(sorted(f["concept"].unique()))}


def contrast(F: Frames, a: str, b: str, variant: str, rendering: str, label: str) -> dict:
    """Acc(a) − Acc(b) on one rendering, paired per item-scored query (design, B1): per query, hit_a − hit_b."""
    fa, fb = item(F.frame(a, variant, rendering)), item(F.frame(b, variant, rendering))
    if not fa.index.equals(fb.index):
        raise ValueError(f"{a} and {b} are not scored on the same queries")
    d = (fa["item_mod"] - fb["item_mod"]).to_numpy(float)
    out = mean_test(d, fa, f"{label}|{a}|{b}|{variant}")
    out.update(acc_a=float(fa["item_mod"].mean()), acc_b=float(fb["item_mod"].mean()),
               excluded=len(F.frame(a, variant, rendering)) - len(fa))
    return out


def read(r: dict) -> str:
    """S4's rule."""
    lo, hi = r["c"]
    if lo > 0 and r["holm"] < ALPHA:
        return "supported"
    if hi < 0 and r["holm"] < ALPHA:
        return "contradicted"
    return "not supported"


# --------------------------------------------------------------------------- Stage P


def stage_p(F: Frames) -> dict:
    """The ten oriented contrasts on dev STACKED-P v2, restricted to the BT-paired leaves; P = the supported ones."""
    out = {}
    for variant in ("tf", "run"):
        rows = []
        for a, b in PAIRS:
            r = contrast(F, a, b, variant, "sp", "P")
            if r["acc_a"] < r["acc_b"]:
                a, b = b, a
                r = contrast(F, a, b, variant, "sp", "P")
            rows.append({"a": a, "b": b, **r})
        for r, h, q in zip(rows, holm([r["p"] for r in rows]), bh([r["p"] for r in rows])):
            r.update(holm=h, bh=q)
            r["reading"] = read(r)
        out[variant] = rows
    return out


def pairs_digest(F: Frames) -> tuple[int, str]:
    keys = sorted(item(F.Q).index)
    return len(keys), hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()


def write_pairs(F: Frames, P: dict) -> None:
    n, digest = pairs_digest(F)
    tf = P["tf"]
    in_p = [r for r in tf if r["reading"] == "supported"]
    lines = header("Stage P: the pairwise ordering on STACKED-P v2, fixed before any BT run is read", [
        "The ten contrasts among the five non-oracle base arms on dev `stacked_texto_v2` restricted to STACKED-P and to",
        "the leaves `bt_texto` pairs, item level, tie-free (the reading) and as run beside; each oriented so that the",
        "arm with the higher tie-free item Acc@1 comes first; Acc(a) − Acc(b) paired per query, concept-clustered",
        "intervals, Holm within the ten. **P** is the set of contrasts reading *supported* (interval above 0, Holm",
        "p < α) on the tie-free reading. No BT run is read in this stage; B1 tests exactly these contrasts on BT.",
    ])
    lines += [f"Population: {n:,} item-scored queries of the {len(F.Q):,} dev BT-paired leaves over {nconc(item(F.Q))} "
              f"concepts (SHA-256 of the sorted key list `{digest[:16]}`). α = {ALPHA}. Fixed on {today()}.", "",
              f"**P = {len(in_p)} of {len(tf)} contrasts:** " + (", ".join(f"`{r['a']}` − `{r['b']}`" for r in in_p) or "none"),
              "", "| contrast (a − b) | n scored | concepts | Acc(a) | Acc(b) | Acc(a) − Acc(b) | CI (query) | CI (concept) | p | "
              "Holm p | BH p | reading | in P | as run: Acc(a) − Acc(b) | CI (concept), as run | reading, as run |",
              "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---|---|---:|---|---|"]
    run_by = {(r["a"], r["b"]): r for r in P["run"]} | {(r["b"], r["a"]): r for r in P["run"]}
    for r in tf:
        a = run_by[(r["a"], r["b"])]
        flip = -1.0 if (a["a"], a["b"]) != (r["a"], r["b"]) else 1.0
        lines.append(f"| `{r['a']}` − `{r['b']}` | {r['n']:,} | {conc(r['concepts'])} | {f4(r['acc_a'])} | {f4(r['acc_b'])} | "
                     f"{fd(r['est'])} | {fci(r['q'], True)} | {fci(r['c'], True)} | {fp(r['p'])} | {fp(r['holm'])} | "
                     f"{fp(r['bh'])} | **{r['reading']}** | {'yes' if r['reading'] == 'supported' else 'no'} | "
                     f"{fd(flip * a['est'])} | {fci(tuple(sorted((flip * a['c'][0], flip * a['c'][1]))), True)} | "
                     f"{a['reading']}{' (orientation reversed)' if flip < 0 else ''} |")
    lines += sources_block([SP], arms=list(BASE5))
    write(OUT / "pairs_stacked_p.md", lines)
    payload = {"fixed_on": today(), "generator_commit": git_head(), "n_scored": n, "keys_sha256": digest,
               "runs": {s: {"run_id": meta(SP, s)["run_id"], "code_commit": meta(SP, s)["code_commit"],
                            "results_sha256": sha256_file(RUNS / SP / DIR[s] / "results_top100.jsonl.gz")} for s in BASE5},
               "pairs": [{"a": r["a"], "b": r["b"], "est": r["est"], "c": list(r["c"]), "p": r["p"], "holm": r["holm"],
                          "reading": r["reading"]} for r in tf],
               "P": [[r["a"], r["b"]] for r in in_p]}
    PAIRS_JSON.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def load_fixed_pairs(F: Frames) -> dict:
    """The P of the Stage-P file, re-derived and asserted to reproduce before any BT figure is read."""
    if not PAIRS_JSON.is_file():
        raise SystemExit("Stage P has not been fixed: run `--fix-pairs` before the full generation")
    fixed = json.loads(PAIRS_JSON.read_text(encoding="utf-8"))
    now = stage_p(F)["tf"]
    for want, got in zip(fixed["pairs"], now):
        if (want["a"], want["b"]) != (got["a"], got["b"]) or abs(want["est"] - got["est"]) > 1e-12 or want["reading"] != got["reading"]:
            raise ValueError(f"Stage P does not reproduce for {want['a']} − {want['b']}: the fixed file is stale")
    for s in BASE5:
        if fixed["runs"][s]["results_sha256"] != sha256_file(RUNS / SP / DIR[s] / "results_top100.jsonl.gz"):
            raise ValueError(f"{s}: the STACKED-P v2 run differs from the one P was fixed on")
    return fixed


# --------------------------------------------------------------------------- the registered tests


def evaluate(F: Frames, fixed: dict, floors: dict[str, float]) -> list[dict]:
    """B1–B4 under every reading; one Holm family per reading; S4's rule; B1's verdict."""
    rows: list[dict] = []
    for a, b in fixed["P"]:
        rows.append({"id": "B1", "hyp": "ordering preserved", "what": f"Acc(`{a}`) − Acc(`{b}`) > 0 on BT", "arm": f"{a} − {b}",
                     "kind": "pair", "a": a, "b": b, "floor": floors[a] < FLOOR or floors[b] < FLOOR})
    rows.append({"id": "B2", "hyp": "method contribution", "what": "K2 − ColBERT > 0 on BT (S11 A1)", "arm": "K2 − bge_m3_colbert",
                 "kind": "pair", "a": "K2", "b": "bge_m3_colbert", "floor": floors["bge_m3_colbert"] < FLOOR})
    for short in BASE5:
        rows.append({"id": "B3", "hyp": "H1 gap widens", "what": "Δ_BT − Δ_id > 0, Δ = parent − item (W1)", "arm": short,
                     "kind": "w1", "floor": floors[short] < FLOOR})
        rows.append({"id": "B3", "hyp": "H1 discrimination", "what": "(D_id − D_BT) − (parent_id − parent_BT) > 0 (W2)", "arm": short,
                     "kind": "w2", "floor": floors[short] < FLOOR})
    for short in BASE5:
        rows.append({"id": "B4", "hyp": "BT gentler", "what": "item δ_BT − δ_STACKED-P > 0 per leaf", "arm": short,
                     "kind": "b4", "floor": floors[short] < FLOOR})
    for v in VARIANTS:
        for r in rows:
            if r["kind"] == "pair":
                res = contrast(F, r["a"], r["b"], v, "bt", r["id"])
            else:
                f = item(F.frame(r["arm"], v))
                lab = f"{r['id']}|{r['kind']}|{r['arm']}|{v}"
                if r["kind"] == "w1":
                    vals = ((f["parent_mod"] - f["item_mod"]) - (f["parent_id"] - f["item_id"])).to_numpy(float)
                    res = mean_test(vals, f, lab)
                elif r["kind"] == "w2":
                    est, draws = discrimination(f, f"s14|{lab}")
                    _, dq = discrimination(f.assign(concept=f.index), f"s14|{lab}|q")
                    d = draws[np.isfinite(draws)]
                    res = {"est": est, "c": ci(d), "q": ci(dq[np.isfinite(dq)]), "p": test_p(draws), "n": len(f),
                           "concepts": nconc(f), "draws": d, "clusters_key": tuple(sorted(f["concept"].unique()))}
                else:
                    vals = (f["item_mod"] - f["item_sp"]).to_numpy(float)
                    res = mean_test(vals, f, lab)
                res["excluded"] = len(F.frame(r["arm"], v)) - len(f)
            r[v] = res
        ps = [r[v]["p"] for r in rows]
        for r, h, q in zip(rows, holm(ps), bh(ps)):
            r[v].update(holm=h, bh=q)
            r[v]["reading"] = "not tested" if r["floor"] else read(r[v])
    for r in rows:
        r["robust"] = all(r[v]["reading"] == r["tf"]["reading"] for v in ("run", "nobt1", "clean"))
    return rows


def b1_verdict(rows: list[dict], variant: str, n_pairs: int) -> str:
    """The design's rule: preserved if every pair in P has a positive estimate and at least half are supported;
    contradicted if any pair is contradicted; partly preserved otherwise; undefined when P is empty."""
    b1 = [r[variant] for r in rows if r["id"] == "B1"]
    if not b1:
        return "undefined (P is empty)"
    if any(r["reading"] == "contradicted" for r in b1):
        return "contradicted"
    supported = sum(r["reading"] == "supported" for r in b1)
    if all(r["est"] > 0 for r in b1) and 2 * supported >= n_pairs:
        return "preserved"
    return "partly preserved"


# --------------------------------------------------------------------------- formatting


def name(short: str) -> str:
    return f"`{short}`" + (" †" if short in ORACLE else "")


def conc(n: int) -> str:
    return f"{n}" + (" ‡" if n < FEW_CLUSTERS else "")


def today() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()


def git_head() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S14 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), "",
            "† oracle arm (D-010): it reads `parameters`, which on BT hold the **gold's own values**, not the variants the "
            "text carries, so on BT it is a stronger oracle than on STACKED-P; printed as an upper bound, in no test "
            "(César, 2026-10-19). ‡ fewer than "
            f"{FEW_CLUSTERS} concepts behind a cell. **H8**: BT and STACKED-P are separate ColBERT encodings, so every "
            "comparison across the two runs of `bge_m3_colbert`, and of the arms ordered by it (K2, R2, F1, the RRF and CE "
            "blends), carries ColBERT's batch dependence (D-060); S11 A11 measured it at a few tie-free hits per thousand "
            "unchanged queries, below any effect read here.", ""]


def population_lines(F: Frames) -> list[str]:
    Q = F.Q
    return [f"**Population.** Dev `{BT}`: {len(Q):,} queries over {nconc(Q)} concepts, one per STACKED-P v2 dev leaf "
            f"(the one STACKED-P dev leaf without a BT query is not read). Item level scores {int(Q['item_scored'].sum()):,} "
            f"({int((~Q['item_scored']).sum()):,} D-033 golds excluded) over {nconc(item(Q))} concepts; parent level scores "
            f"all {len(Q):,}. Each query is paired with the same arm's `{SP}` query of the same leaf (STACKED-P) and with "
            f"its `{IDENT}` result on the gold (`{IDENT_S11}` for the S11 arms): treatment effect on the treated. "
            f"δ_BT = BT − identity, δ_SP = STACKED-P − identity. F-BT-1: {int(Q['fbt1'].sum()):,} queries say «{FBT1_QUERY}» "
            f"where the gold says «{FBT1_GOLD}». D-004 detector: {int(Q['flagged'].sum()):,} BT queries flagged.", ""]


def stack_stamp() -> str:
    return analysis_stack.stamp()


def sources_block(querysets: list[str], arms: list[str] | None = None, inputs: tuple[Path, ...] = ()) -> list[str]:
    lines = ["", "## Sources", "", "| query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
             "|---|---|---:|---|---|---|---|"]
    for qs in querysets:
        for short in SHORTS:
            if arms is not None and short not in arms:
                continue
            q = ident_qs(short) if qs == IDENT else qs
            if not available(q, short):
                continue
            m = meta(q, short)
            lines.append(f"| `{q}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                         f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (BT_JSON, SP_JSON, STACKED_P_EXCLUSION, SIDECAR, CORPUS_JSON, *inputs)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile intervals at level {1 - ALPHA:.0%}; readings on the "
              "concept-clustered draws (D-030). Split `dev`.", stack_stamp()]
    return lines


# --------------------------------------------------------------------------- tables


def floors_of(F: Frames) -> dict[str, float]:
    """Identity item Acc@1, tie-free, on the item-scored BT leaves (S4's floor)."""
    return {s: float(item(F.frame(s, "tf"))["item_id"].mean()) for s in SHORTS}


def write_profile(F: Frames, floors: dict[str, float]) -> None:
    lines = header("T1: profile on BT, item and parent level (dev)", [
        f"Every arm on `{BT}`, paired with its identity on the same golds and with its STACKED-P v2 query of the same leaf.",
        "Tie-free is the reading (D-028 note); as run beside it. **Retention** is P(hit BT | hit identity).",
    ]) + population_lines(F)
    lines += [f"**Floor**: identity item Acc@1 (tie-free, these leaves) below {FLOOR:.2f} (S4); floor arms are reported, "
              "never read.", ""]
    for level in ("item", "parent"):
        lines += [f"## {level.capitalize()} level", "",
                  "| arm | kind | n scored | n excluded | concepts | identity | BT | δ_BT | CI (query) | CI (concept) | retention | "
                  "CI (concept) | STACKED-P v2 | δ_SP | CI (concept) | identity, as run | BT, as run | δ_BT, as run | "
                  "CI (concept), as run |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|---|---:|---:|---:|---|"]
        for short in SHORTS:
            t = cell(F.frame(short, "tf"), level, f"T1|{short}|tf")
            s = cell(F.frame(short, "tf"), level, f"T1|{short}|tf", mod="sp")
            a = cell(F.frame(short, "run"), level, f"T1|{short}|run")
            fl = " (floor)" if level == "item" and floors[short] < FLOOR else ""
            lines.append(f"| {name(short)}{fl} | {KIND[short]} | {t['n']:,} | {t['excluded']:,} | {conc(t['concepts'])} | "
                         f"{f4(t['id'])} | {f4(t['mod'])} | {fd(t['delta'])} | {fci(t['q'], True)} | {fci(t['c'], True)} | "
                         f"{f4(t['retention'])} | {fci(t['ret_c'])} | {f4(s['mod'])} | {fd(s['delta'])} | {fci(s['c'], True)} | "
                         f"{f4(a['id'])} | {f4(a['mod'])} | {fd(a['delta'])} | {fci(a['c'], True)} |")
        lines.append("")
    trunc = {s: (int(F.H[s]["bt_truncated"].sum()), int(F.H[s]["sp_truncated"].sum()), int(F.H[s]["id_truncated"].sum()))
             for s in SHORTS}
    lines += ["## Rank-1 tied sets that fill the whole top-100", "",
              "Such a tied set is truncated, so its tie-free value is an upper bound.", "",
              "| arm | BT | STACKED-P v2 | identity |", "|---|---:|---:|---:|"]
    lines += [f"| {name(s)} | {a:,} | {b:,} | {c:,} |" for s, (a, b, c) in trunc.items()]
    lines += sources_block([BT, SP, IDENT])
    write(OUT / "profile.md", lines)


def write_contrasts(F: Frames, fixed: dict, rows: list[dict]) -> None:
    in_p = {(a, b) for a, b in fixed["P"]}
    lines = header("T2: the pairwise contrasts on both renderings (B1)", [
        "The ten contrasts among the five non-oracle base arms, item level, tie-free, as Stage P oriented them on",
        "STACKED-P v2 (`pairs_stacked_p.md`), and the same contrast on BT, paired per query on the same item-scored",
        "leaves. Every contrast is printed on both renderings, descriptively; **only the pairs in P are tests (B1)**, and",
        "their BT reading is in `predictions.md`'s Holm family. The oracle arms enter no pair.",
    ]) + population_lines(F)
    lines += [f"**P** (fixed {fixed['fixed_on']}, generator `{fixed['generator_commit']}`): "
              + (", ".join(f"`{a}` − `{b}`" for a, b in fixed["P"]) or "empty") + ".", "",
              "| contrast (a − b) | in P | n scored | n excluded | concepts | STACKED-P v2: Acc(a) | Acc(b) | a − b | CI (query) | "
              "CI (concept) | reading (Stage P) | BT: Acc(a) | Acc(b) | a − b | CI (query) | CI (concept) | sign kept |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---|---|---|"]
    for pr in fixed["pairs"]:
        a, b = pr["a"], pr["b"]
        r = contrast(F, a, b, "tf", "bt", "B1")  # the registered label: one statistic, one interval (S9 audit F1)
        sp = contrast(F, a, b, "tf", "sp", "P")  # Stage P's own draws
        lines.append(f"| `{a}` − `{b}` | {'**yes**' if (a, b) in in_p else 'no'} | {r['n']:,} | {r['excluded']:,} | {conc(r['concepts'])} | "
                     f"{f4(sp['acc_a'])} | {f4(sp['acc_b'])} | {fd(pr['est'])} | {fci(sp['q'], True)} | {fci(tuple(pr['c']), True)} | "
                     f"{pr['reading']} | {f4(r['acc_a'])} | {f4(r['acc_b'])} | {fd(r['est'])} | {fci(r['q'], True)} | "
                     f"{fci(r['c'], True)} | {'yes' if r['est'] > 0 else '**no**'} |")
    lines += ["", "## The oracle arms beside (printed, never in a pair)", "",
              "| arm | STACKED-P v2 item Acc@1 | BT item Acc@1 | identity |", "|---|---:|---:|---:|"]
    for short in SHORTS:
        if short in ORACLE:
            t = cell(F.frame(short, "tf"), "item", f"T1|{short}|tf")
            s = cell(F.frame(short, "tf"), "item", f"T1|{short}|tf", mod="sp")
            lines.append(f"| {name(short)} | {f4(s['mod'])} | {f4(t['mod'])} | {f4(t['id'])} |")
    lines += sources_block([BT, SP], arms=list(BASE5) + sorted(ORACLE))
    write(OUT / "contrasts.md", lines)


def write_method(F: Frames) -> None:
    lines = header("T3: the method contribution on BT (B2) and the S11 arms beside", [
        "K2 − ColBERT on BT, item level, paired per query (the S11 A1 contrast; B2). Descriptive beside it, not tested:",
        "R2 − `bm25_unigram`, F1 − ColBERT, K2 − `rules_valuenorm`, and K2 − ColBERT per translated-fraction bin. The",
        "S11 arms' identity is their `texto_u` run (S11); ColBERT's and BM25's their `texto` run, on the same golds.",
    ]) + population_lines(F)
    lines += ["| contrast | rendering | n scored | n excluded | concepts | Acc(a) | Acc(b) | a − b | CI (query) | CI (concept) | a − b, as run |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|"]
    for a, b in (("K2", "bge_m3_colbert"), ("R2", "bm25_unigram"), ("F1", "bge_m3_colbert"), ("K2", "rules_valuenorm"),
                 ("K2", "R2"), ("R2", "bge_m3_colbert")):
        for rendering, shown in (("bt", "BT"), ("sp", "STACKED-P v2")):
            seed = "B2" if (a, b, rendering) == ("K2", "bge_m3_colbert", "bt") else "T3"  # B2's own draws for the registered cell
            r = contrast(F, a, b, "tf", rendering, seed)
            rr = contrast(F, a, b, "run", rendering, seed)
            lines.append(f"| `{a}` − `{b}` | {shown} | {r['n']:,} | {r['excluded']:,} | {conc(r['concepts'])} | {f4(r['acc_a'])} | "
                         f"{f4(r['acc_b'])} | {fd(r['est'])} | {fci(r['q'], True)} | {fci(r['c'], True)} | {fd(rr['est'])} |")
    lines += ["", "## K2 − ColBERT by translated-sentence fraction (BT, descriptive)", "",
              "| fraction bin | n scored | concepts | K2 | ColBERT | K2 − ColBERT | CI (query) | CI (concept) |",
              "|---|---:|---:|---:|---:|---:|---|---|"]
    fk, fc = item(F.frame("K2", "tf")), item(F.frame("bge_m3_colbert", "tf"))
    for fbin in sorted(F.Q["fbin"].unique()):
        g, h = fk[fk["fbin"] == fbin], fc[fc["fbin"] == fbin]
        d = (g["item_mod"] - h["item_mod"]).to_numpy(float)
        r = mean_test(d, g, f"T3|fbin|{fbin}")
        lines.append(f"| {fbin} | {r['n']:,} | {conc(r['concepts'])} | {f4(g['item_mod'].mean())} | {f4(h['item_mod'].mean())} | "
                     f"{fd(r['est'])} | {fci(r['q'], True)} | {fci(r['c'], True)} |")
    lines += sources_block([BT, SP, IDENT], arms=["K2", "R2", "F1", "bge_m3_colbert", "bm25_unigram", "rules_valuenorm"])
    write(OUT / "method.md", lines)


def write_h1(F: Frames, rows: list[dict]) -> None:
    lines = header("T4: H1 on BT (B3) — the collapse quantities", [
        "For each base arm, W1 (the parent − item gap widens under BT) and W2 (discrimination falls more than concept",
        "identification), as S7 defines them, with BT as the modification; the same quantities on STACKED-P v2 beside.",
        "Readings are in `predictions.md`. Item-scored queries; Δ = parent − item; D = Σ item ÷ Σ parent.",
    ]) + population_lines(F)
    lines += ["| arm | n scored | concepts | Δ identity | Δ BT | Δ STACKED-P v2 | D identity | D BT | D STACKED-P v2 | "
              "W1 on BT | CI (concept) | W2 on BT | CI (concept) | W1 on STACKED-P v2 | W2 on STACKED-P v2 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|"]
    by = {(r["arm"], r["kind"]): r["tf"] for r in rows if r["id"] == "B3"}
    for short in SHORTS:
        f = item(F.frame(short, "tf"))
        gap = lambda side: float((f[f"parent_{side}"] - f[f"item_{side}"]).mean())  # noqa: E731
        dis = lambda side: float(f[f"item_{side}"].sum() / f[f"parent_{side}"].sum()) if f[f"parent_{side}"].sum() else float("nan")  # noqa: E731
        w1_sp = float(((f["parent_sp"] - f["item_sp"]) - (f["parent_id"] - f["item_id"])).mean())
        w2_sp = (dis("id") - dis("sp")) - (float(f["parent_id"].mean()) - float(f["parent_sp"].mean()))
        if short in BASE5:
            w1, w2 = by[(short, "w1")], by[(short, "w2")]
            w1s, w2s = f"{fd(w1['est'])} | {fci(w1['c'], True)}", f"{fd(w2['est'])} | {fci(w2['c'], True)}"
        else:
            w1_bt = float(((f["parent_mod"] - f["item_mod"]) - (f["parent_id"] - f["item_id"])).mean())
            w2_bt = (dis("id") - dis("mod")) - (float(f["parent_id"].mean()) - float(f["parent_mod"].mean()))
            w1s, w2s = f"{fd(w1_bt)} | — (not registered)", f"{fd(w2_bt)} | — (not registered)"
        lines.append(f"| {name(short)} | {len(f):,} | {conc(nconc(f))} | {f4(gap('id'))} | {f4(gap('mod'))} | {f4(gap('sp'))} | "
                     f"{f4(dis('id'))} | {f4(dis('mod'))} | {f4(dis('sp'))} | {w1s} | {w2s} | {fd(w1_sp)} | {fd(w2_sp)} |")
    lines += sources_block([BT, SP, IDENT])
    write(OUT / "h1.md", lines)


def write_calibration(F: Frames, rows: list[dict]) -> None:
    lines = header("T5: BT against STACKED-P v2 per leaf (B4, calibration)", [
        "For each arm, item δ_BT − δ_STACKED-P per leaf (δ = rendering − identity, so the difference is BT − STACKED-P on",
        "the same leaf), concept-clustered. Registered for the five base arms (B4); descriptive for the rest. A *not",
        "supported* B4 does not touch B1–B3: it says the two renderings are of similar strength.",
    ]) + population_lines(F)
    lines += ["| arm | n scored | concepts | δ_BT | δ_SP | δ_BT − δ_SP | CI (query) | CI (concept) | leaves BT hits, STACKED-P misses | "
              "the reverse | registered |", "|---|---:|---:|---:|---:|---:|---|---|---:|---:|---|"]
    by = {r["arm"]: r["tf"] for r in rows if r["id"] == "B4"}
    for short in SHORTS:
        f = item(F.frame(short, "tf"))
        d = (f["item_mod"] - f["item_sp"]).to_numpy(float)
        r = by[short] if short in by else mean_test(d, f, f"T5|{short}|tf")
        lines.append(f"| {name(short)} | {r['n']:,} | {conc(r['concepts'])} | {fd(float((f['item_mod'] - f['item_id']).mean()))} | "
                     f"{fd(float((f['item_sp'] - f['item_id']).mean()))} | {fd(r['est'])} | {fci(r['q'], True)} | {fci(r['c'], True)} | "
                     f"{int(((f['item_mod'] == 1) & (f['item_sp'] == 0)).sum()):,} | {int(((f['item_mod'] == 0) & (f['item_sp'] == 1)).sum()):,} | "
                     f"{'B4' if short in by else 'no'} |")
    lines += sources_block([BT, SP, IDENT])
    write(OUT / "calibration.md", lines)


def strata_table(F: Frames, key: str, values: list, title: str, how: list[str], file: str, display: dict | None = None) -> None:
    lines = header(title, how + ["Descriptive: no Holm, no reading. Item level, tie-free; δ_BT = BT − identity on the",
                                 "stratum's item-scored queries, δ_SP the same leaves' STACKED-P v2 δ; retention P(hit BT | hit identity)."])
    lines += population_lines(F)
    lines += ["| arm | stratum | n | n scored | n excluded | concepts | identity | BT | δ_BT | CI (query) | CI (concept) | retention | "
              "STACKED-P v2 | δ_SP | CI (concept) |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---|"]
    for short in SHORTS:
        f = F.frame(short, "tf")
        for value in values:
            g = f[f[key] == value]
            if not len(item(g)):
                continue
            t = cell(g, "item", f"{file}|{short}|{value}")
            s = cell(g, "item", f"{file}|{short}|{value}", mod="sp")
            shown = (display or {}).get(value, value)
            lines.append(f"| {name(short)} | {shown} | {len(g):,} | {t['n']:,} | {t['excluded']:,} | {conc(t['concepts'])} | {f4(t['id'])} | "
                         f"{f4(t['mod'])} | {fd(t['delta'])} | {fci(t['q'], True)} | {fci(t['c'], True)} | {f4(t['retention'])} | "
                         f"{f4(s['mod'])} | {fd(s['delta'])} | {fci(s['c'], True)} |")
    lines += sources_block([BT, SP, IDENT])
    write(OUT / f"{file}.md", lines)


def write_strata(F: Frames) -> None:
    Q = F.Q
    strata_table(F, "fbin", sorted(Q["fbin"].unique()), "T6: δ_BT by translated-sentence fraction",
                 ["Bins on `bt_sentences.fraction`, the share of the query's sentences that went through the pivot chain.",
                  f"Mean fraction on dev {Q['fraction'].mean():.2f}; label sentences return identical."], "fraction")
    strata_table(F, "lists", ["pure BT", "value only", "glossary only", "value + glossary"], "T7: δ_BT by list-driven variation",
                 ["Whether the query carries a `value_back_translation` (audited value variants) and / or a `glossary_synonym`",
                  "(trade-term list); *pure BT* carries neither. Half of BT's variation is list-driven, so independence from a",
                  "menu is partial; the pure-BT stratum is the thin one."], "lists")
    Q2 = Q.assign(label=np.where(Q["label_added"], "axis label precedes the variant", "no label added"))
    F.Q = Q2
    strata_table(F, "label", ["axis label precedes the variant", "no label added"], "T7b: δ_BT by `label_added`",
                 ["Whether an axis label was written before a value variant (`OE_bt_modifications.jsonl`)."], "label_added")
    F.Q = Q
    strata_table(F, "subchapter", sorted(Q["subchapter"].unique()), "T8: δ_BT by subchapter",
                 ["Subchapter of the gold leaf; concepts and subchapter are confounded across the population."], "subchapter")
    strata_table(F, "cbin", [b for b, _, _ in COV_BINS], "T9: δ_BT by S9's lexical-coverage bin",
                 ["S3's lexical coverage of the BT query against its gold, binned as S9 binned the untransformed query: "
                  + "; ".join(f"{b} [{lo:.2f}, {hi:.2f})" for b, lo, hi in COV_BINS) + ". This places BT on the overlap axis.",
                  f"Dev median coverage of BT {Q['cov'].median():.4f}. The bins are S9's, named `coverage B1`–`B4` here so that "
                  "they are not read as this sprint's hypotheses B1–B4."], "coverage",
                 display={b: f"coverage {b} [{lo:.2f}, {hi:.2f})" for b, lo, hi in COV_BINS})


def write_sensitivity(F: Frames, rows: list[dict], fixed: dict) -> None:
    lines = header("T10: sensitivity — F-BT-1 and the D-004 flags", [
        "Every registered reading under the four readings: tie-free (the one read), as run, without the F-BT-1 queries",
        "(«de hormigón» for the gold's «hormigonada», closed upstream) and on the D-004-clean subset. A reading whose",
        "category changes is **not robust**; the tie-free reading on the full population stands. Then the F-BT-1 subset",
        "and its complement per base arm.",
    ]) + population_lines(F)
    lines += ["| test | arm | " + " | ".join(f"{VARIANT_LABEL[v]}: estimate | CI (concept) | reading" for v in VARIANTS) + " | robust |",
              "|---|---|" + "---:|---|---|" * len(VARIANTS) + "---|"]
    for r in rows:
        cells = " | ".join(f"{fd(r[v]['est'])} | {fci(r[v]['c'], True)} | {r[v]['reading']}" for v in VARIANTS)
        lines.append(f"| {r['id']} | {r['arm']} | {cells} | {'yes' if r['robust'] else '**no**'} |")
    lines += ["", "**B1 verdict by reading:** " + "; ".join(f"{VARIANT_LABEL[v]} **{b1_verdict(rows, v, len(fixed['P']))}**" for v in VARIANTS) + ".", "",
              "## The F-BT-1 queries and the rest, per arm (item, tie-free)", "",
              "| arm | subset | n scored | concepts | identity | BT | δ_BT | CI (concept) | STACKED-P v2 | δ_SP |",
              "|---|---|---:|---:|---:|---:|---:|---|---:|---:|"]
    for short in SHORTS:
        f = F.frame(short, "tf")
        for label, mask in (("F-BT-1", f["fbt1"]), ("not F-BT-1", ~f["fbt1"])):
            g = f[mask]
            if not len(item(g)):
                continue
            t = cell(g, "item", f"T10|{short}|{label}")
            s = cell(g, "item", f"T10|{short}|{label}", mod="sp")
            lines.append(f"| {name(short)} | {label} | {t['n']:,} | {conc(t['concepts'])} | {f4(t['id'])} | {f4(t['mod'])} | "
                         f"{fd(t['delta'])} | {fci(t['c'], True)} | {f4(s['mod'])} | {fd(s['delta'])} |")
    n_flag = int(F.Q["flagged"].sum())
    lines += ["", f"D-004: the detector flags {n_flag:,} BT queries" + ("; the clean reading above drops them." if n_flag else
              "; the clean reading equals the tie-free one by construction and is printed for the record.")]
    lines += sources_block([BT, SP, IDENT])
    write(OUT / "sensitivity.md", lines)


def write_predictions(rows: list[dict], fixed: dict, floors: dict[str, float]) -> None:
    lines = header("T8: the registered predictions B1–B4 (dev)", [
        f"Read on the concept-clustered interval (D-030), Holm–Bonferroni across the {len(rows)} tests of one reading, BH",
        "beside. **Supported** when the interval lies above 0 and Holm p < α; **contradicted** in the mirror case;",
        "**not supported** otherwise (S4's rule). Tie-free is the reading; as run, F-BT-1-free and D-004-clean each form",
        "their own Holm family. A reading whose category differs under another reading is **not robust**; the tie-free",
        "reading stands. Floor arms read *not tested*.",
    ])
    lines += [f"α = {ALPHA}. **CI (query)** resamples queries; it is printed, never read. **P** = "
              + (", ".join(f"`{a}` − `{b}`" for a, b in fixed["P"]) or "empty")
              + f" ({len(fixed['P'])} of {len(fixed['pairs'])} contrasts, fixed {fixed['fixed_on']}; `pairs_stacked_p.md`).", "",
              "**Floor re-check, tie-free, identity on the BT leaves**: " + ", ".join(f"{name(s)} {f4(floors[s])}" for s in BASE5)
              + ". " + ("Below the floor, read *not tested*: " + ", ".join(name(s) for s in BASE5 if floors[s] < FLOOR)
                        if any(floors[s] < FLOOR for s in BASE5) else "None of the five is below the floor."), "",
              "| test | hypothesis | arm | concepts | n scored (excluded) | estimate | CI (query) | CI (concept) | p | Holm p | BH p | "
              "reading | as run | CI (concept), as run | reading, as run | reading, F-BT-1-free | reading, clean | robust |",
              "|---|---|---|---:|---|---:|---|---|---:|---:|---:|---|---:|---|---|---|---|---|"]
    for r in rows:
        t, a = r["tf"], r["run"]
        lines.append(f"| {r['id']} | {r['hyp']}: {r['what']} | {r['arm']} | {conc(t['concepts'])} | {t['n']:,} ({t['excluded']:,}) | "
                     f"{fd(t['est'])} | {fci(t['q'], True)} | {fci(t['c'], True)} | {fp(t['p'])} | {fp(t['holm'])} | {fp(t['bh'])} | "
                     f"**{t['reading']}** | {fd(a['est'])} | {fci(a['c'], True)} | {a['reading']} | {r['nobt1']['reading']} | "
                     f"{r['clean']['reading']} | {'yes' if r['robust'] else '**no**'} |")
    tally = {k: sum(r["tf"]["reading"] == k for r in rows) for k in ("supported", "not supported", "contradicted", "not tested")}
    lines += ["", "**Tally, tie-free:** " + ", ".join(f"{v} {k}" for k, v in tally.items()) + ".",
              f"**B1 verdict (tie-free):** **{b1_verdict(rows, 'tf', len(fixed['P']))}** — the design's rule: preserved if every pair "
              "in P has a positive point estimate on BT and at least half are supported; contradicted if any is contradicted; "
              "partly preserved otherwise.",
              "**B2 (tie-free):** " + ", ".join(f"**{r['tf']['reading']}**" for r in rows if r["id"] == "B2") + ".",
              "**B3 (tie-free):** " + ", ".join(f"{r['arm']} {r['kind'].upper()} {r['tf']['reading']}" for r in rows if r["id"] == "B3") + ".",
              "**B4 (tie-free):** " + ", ".join(f"{r['arm']} {r['tf']['reading']}" for r in rows if r["id"] == "B4") + "."]
    lines += sources_block([BT, SP, IDENT], arms=list(BASE5) + ["K2"])
    write(OUT / "predictions.md", lines)


def write_figure(F: Frames) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGS.mkdir(parents=True, exist_ok=True)
    rows = []
    for short in SHORTS:
        t = cell(F.frame(short, "tf"), "item", f"T1|{short}|tf")
        s = cell(F.frame(short, "tf"), "item", f"T1|{short}|tf", mod="sp")
        rows.append((short, s["mod"], t["mod"], t["id"]))
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.plot([0, 1], [0, 1], color="grey", lw=0.8, ls="--")
    for short, x, y, _ in rows:
        ax.plot([x], [y], "o", color="tab:orange" if short in ORACLE else "tab:blue", ms=5)
        ax.text(x, y, " " + short, fontsize=6, va="center")
    ax.set_xlabel("item Acc@1 on STACKED-P v2 (tie-free)")
    ax.set_ylabel("item Acc@1 on BT (tie-free)")
    ax.set_title("Fig. 9 — the same leaves under two renderings (orange: oracle arms)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig9_bt_vs_stacked_p.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines = header("Fig. 9 and the numbers it plots", ["Item level on the item-scored queries, tie-free; one point per arm."])
    lines += ["## Fig. 9 — item Acc@1 on BT against STACKED-P v2 (`fig9_bt_vs_stacked_p.png`)", "",
              "| arm | STACKED-P v2 | BT | identity |", "|---|---:|---:|---:|"]
    lines += [f"| {name(s)} | {f4(x)} | {f4(y)} | {f4(i)} |" for s, x, y, i in rows]
    lines += ["", stack_stamp()]
    write(OUT / "figures.md", lines)


def write_provenance(F: Frames) -> None:
    lines = header("T11: run provenance (dev)", [
        f"Every run the S14 tables read: the `{BT}` runs are S14's (work item 3); the `{SP}` runs are S7 A8's and S11 A7's;",
        f"the `{IDENT}` / `{IDENT_S11}` runs are earlier sprints' identity runs, read, not re-run. Then the inputs, the BT",
        "ColBERT family cache and its exact check, the extractor's regeneration check and the LLM stamps of the K2 run.",
    ])
    lines += ["| query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 | derived from |",
              "|---|---|---:|---|---|---|---|---|"]
    for qs in (BT, SP, IDENT, IDENT_S11):
        for short in SHORTS:
            q = ident_qs(short) if qs in (IDENT, IDENT_S11) else qs
            if q != qs or not available(q, short):
                continue
            m = meta(q, short)
            comps = ", ".join(f"`{c['run_id']}` @ `{c['code_commit'][:7]}`" for c in m.get("components", [])) or "—"
            lines.append(f"| `{q}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                         f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` | {comps} |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.relative_to(REPO).as_posix()}` | `{sha256_file(p)[:16]}` |"
                for p in (BT_JSON, BT_FEATS, MODS_JSONL, SP_JSON, STACKED_P_EXCLUSION, SIDECAR, CORPUS_JSON, REPO / "docs" / "synthetic-oe" / "SPLITS.md"))]
    if FAMILY_META.is_file():
        cm = json.loads(FAMILY_META.read_text(encoding="utf-8"))
        if sha256_file(FAMILY_NPZ) != cm["npz_sha256"]:
            raise ValueError("the BT family cache differs from the one its meta.json records")
        ch = cm["check"]
        lines += ["", "| ColBERT family cache | file SHA-256 | reference run | queries | pairs | compared | mismatched | built at |",
                  "|---|---|---|---:|---:|---:|---:|---|",
                  f"| `{BT}` | `{cm['npz_sha256'][:16]}` | `{cm['reference_run']}` | {cm['queries']:,} | {cm['query_concept_pairs']:,} | "
                  f"{ch['compared']:,} | {ch['mismatched']} | `{cm['code_commit'][:7]}` |"]
    else:
        lines += ["", f"No ColBERT family cache for `{BT}` at generation."]
    if DET_LOG.is_file():
        det = json.loads(DET_LOG.read_text(encoding="utf-8"))
        lines += ["", f"Extractor regeneration on `{BT}` (work item 2): {det['identical']} of {det['n']} identical, "
                  f"{len(det['unparsed'])} unparsed, {det['truncated']} truncated; model `{det['model_digest'][:16]}`, ollama "
                  f"{det['ollama_version']}, options `{json.dumps(det['options'], sort_keys=True)}`."]
    else:
        lines += ["", f"Extractor regeneration log `{DET_LOG.relative_to(REPO).as_posix()}` absent at generation."]
    for short in ("K2", "R2", "F1"):
        if available(BT, short):
            prov = meta(BT, short).get("retriever_provenance", {})
            llm, fam = prov.get("llm"), prov.get("colbert_family")
            parts = []
            if llm:
                parts.append(f"model `{llm['model']}` digest `{llm['model_digest'][:16]}`, ollama {llm['ollama_version']}, prompt "
                             f"`{llm['prompt_template']}` SHA-256 `{llm['prompt_template_sha256'][:16]}` (file `{llm['prompts_py_sha256'][:16]}`), "
                             f"key match {llm['key_match']}")
            if fam:
                parts.append(f"family file `{fam['file']}` `{fam['sha256'][:16]}`")
            lines += ["", f"`{short}` on `{BT}` stamps: " + ("; ".join(parts) if parts else "no `retriever_provenance`") + "."]
    commit = git_head()
    dirty = subprocess.run(["git", "status", "--porcelain", "src"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    lines += ["", f"Generator commit `{commit}`, `src/` {'dirty' if dirty else 'clean'}.", "",
              f"Bootstrap: B = {B:,}, seed = {SEED}, percentile intervals at level {1 - ALPHA:.0%}; concept-clustered "
              "(D-030) unless marked query-level. Split `dev`.", stack_stamp()]
    write(OUT / "run_provenance.md", lines)


# --------------------------------------------------------------------------- main


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix-pairs", action="store_true", help="Stage P only: no BT run is read")
    args = ap.parse_args(argv)
    analysis_stack.require()
    OUT.mkdir(parents=True, exist_ok=True)
    dev = load_split("dev")
    if args.fix_pairs:
        F = Frames(dev, read_bt=False)
        write_pairs(F, stage_p(F))
        print(f"written: {OUT}/pairs_stacked_p.{{md,json}}")
        return
    F = Frames(dev, read_bt=True)
    fixed = load_fixed_pairs(F)
    floors = floors_of(F)
    rows = evaluate(F, fixed, floors)
    write_profile(F, floors)
    write_contrasts(F, fixed, rows)
    write_method(F)
    write_h1(F, rows)
    write_calibration(F, rows)
    write_strata(F)
    write_sensitivity(F, rows, fixed)
    write_predictions(rows, fixed, floors)
    write_figure(F)
    write_provenance(F)
    print(f"written: {OUT}")


if __name__ == "__main__":
    main()
