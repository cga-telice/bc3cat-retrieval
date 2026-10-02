"""S8 — E3 balanced dose design: T1–T11 and Fig. 6 (design `4f62d5a`, A1–A2).

    python src/utils/build_results_s8.py        # in the sprint container, bc3cat-s3

Reads, and never writes, `runs/OE/dose_texto/<arm>` and `runs/OE/isolated_texto/<arm>` (S8's 36 runs), each
arm's `texto` run for the identity side, `single_texto` for T2's reference and `stacked_texto` for T8's. Writes
`docs/synthetic-oe/results/S8/`.

Every effect is within leaf (design): a dev ladder leaf carries its identity result, its five nested rungs and
its nine isolated queries, and every contrast is computed on one leaf before it is averaged. What is new here:
- the **clipped-additive prediction** of a rung, clip(h_id + Σ_{t∈S_k}(h_iso,t − h_id), 0, 1) (design);
- **X1–X3**, 21 registered tests, tie-free (primary), as run and on the D-004 clean subset (A2);
- the **stratified leaf bootstrap** (D-053): leaves resampled within their concept, B draws, beside S2's
  concept-clustered bootstrap, which here rests on four clusters;
- the **per-concept sign rule** (D-053) and the draw-noise check against T3 (design, A2).

Tie-free values are expectations over a uniform break of the rank-1 tie (D-028 note), so every hit is in
[0, 1] and every statistic below is a ratio of sums of per-leaf terms (A2).

The analysis stack is pinned (`analysis_stack.py`): the script refuses to run on another.
"""

from __future__ import annotations

import json
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import sys  # noqa: E402
from itertools import combinations  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils import analysis_stack  # noqa: E402
from utils.build_results_s2 import ALPHA, B, SEED, _rng, bh, boot_p, ci, f4, fci, fd, fp, holm, write  # noqa: E402
from utils.build_results_s4 import AMENDMENT_EXCLUDED as S4_EXCLUDED, CORPUS_JSON, FLOOR, LAYERS, duplicated  # noqa: E402
from utils.build_results_s6 import BASE7, cell  # noqa: E402
from utils.build_results_s7 import (  # noqa: E402
    ARMS, DIR, ORACLE, TWIN, columns, item, leaf_density, meta, paired, parent_of, perquery, run_dir,
    stacked_features, tie_table,
)
from utils.pantry_flags import text_flags  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402
from utils.splits import load_split  # noqa: E402

DATA = REPO / "data" / "processed"
DOSE_JSON = DATA / "OE_dose_texto.json"
ISO_JSON = DATA / "OE_isolated_texto.json"
SINGLE_JSON = DATA / "OE_single_texto.json"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S8"
FIGS = OUT / "figures"
GENERATOR = "src/utils/build_results_s8.py"

DOSE, ISO, IDENT, SINGLE, STACKED = "dose_texto", "isolated_texto", "texto", "single_texto", "stacked_texto"
TYPES = LAYERS["L1"] + LAYERS["L2"] + LAYERS["L3"]
TI = {t: i for i, t in enumerate(TYPES)}
RUNGS = [1, 2, 3, 4, 5]
#: X1 and X2 read the rungs that stack at least two edits (design).
STACK_RUNGS = [k for k in RUNGS if k >= 2]
#: Pairs that never co-occur, by construction (D-009 Delivered, limitation 1).
NOT_IDENTIFIABLE = {frozenset({"reorder", "template_paraphrase"}), frozenset({"unit_conversion", "unit_expansion"})}

#: D-053: a supported reading also needs the predicted sign in at least this many of the dev ladder concepts.
SIGN_MIN = 3
#: Design, thin cells: per-type and per-pair cells under this many leaves carry ‡ and are not read.
THIN_LEAVES = 20
#: Design, risks: an arm with less at-risk mass than this reads X2 *not tested*.
MIN_AT_RISK = 50

VARIANTS = ("tf", "run", "clean")
VARIANT_LABEL = {"tf": "tie-free", "run": "as run", "clean": "tie-free, D-004 clean subset"}

TESTS = [
    # id, hypothesis, statement, kind, predicted sign
    ("X1", "H4 cumulative", "mean over rungs of (h_k − pred_k) < 0, pred = clipped-additive", "x1", -1),
    ("X2", "H4 marginal", "P(iso hit, rung miss) − P(iso miss, rung hit) > 0, over steps at risk", "x2", +1),
    ("X3", "dose-response", "within-leaf slope of item hit on dose < 0", "x3", -1),
]


# --------------------------------------------------------------------------- the ladder, per arm


class Ladder:
    """One arm's dev ladder: per leaf, identity, five rungs and nine isolated hits, both levels, both readings."""

    def __init__(self, short: str, design: dict, parents: dict[str, str]):
        self.short = short
        golds = design["golds"]
        self.golds, self.concept = golds, design["concept"]
        n = len(golds)
        self.h = {}  # (level, variant) -> n × 6 (identity, rungs 1..5)
        self.iso = {}  # (level, variant) -> n × 9
        id_pq = perquery(IDENT, short).set_index("query_item_key")
        t_id = tie_table(run_dir(IDENT, short), set(golds), parents)
        dose_pq = perquery(DOSE, short).set_index("query_item_key")
        iso_pq = perquery(ISO, short).set_index("query_item_key")
        dkeys, ikeys = design["dose_key"], design["iso_key"]
        t_dose = tie_table(run_dir(DOSE, short), set(dkeys.ravel()), parents)
        t_iso = tie_table(run_dir(ISO, short), set(ikeys.ravel()), parents)
        if set(dose_pq.index) != set(dkeys.ravel()) or set(iso_pq.index) != set(ikeys.ravel()):
            raise ValueError(f"{short}: run queries differ from the dev ladder")
        for level in ("item", "parent"):
            for variant, src in (("run", None), ("tf", "tf")):
                h = np.zeros((n, 6))
                if src:
                    h[:, 0] = t_id.loc[golds, f"{level}_tf"].to_numpy(float)
                    for k in RUNGS:
                        h[:, k] = t_dose.loc[dkeys[:, k - 1], f"{level}_tf"].to_numpy(float)
                    iso = np.column_stack([t_iso.loc[ikeys[:, j], f"{level}_tf"].to_numpy(float)
                                           for j in range(len(TYPES))])
                else:
                    h[:, 0] = id_pq.loc[golds, f"{level}_acc1"].to_numpy(float)
                    for k in RUNGS:
                        h[:, k] = dose_pq.loc[dkeys[:, k - 1], f"{level}_acc1"].to_numpy(float)
                    iso = np.column_stack([iso_pq.loc[ikeys[:, j], f"{level}_acc1"].to_numpy(float)
                                           for j in range(len(TYPES))])
                self.h[(level, variant)], self.iso[(level, variant)] = h, iso
        for level in ("item", "parent"):
            self.h[(level, "clean")], self.iso[(level, "clean")] = self.h[(level, "tf")], self.iso[(level, "tf")]
        for level in ("item", "parent"):
            for a, b in ((self.h[(level, "run")], self.h[(level, "tf")]),
                         (self.iso[(level, "run")], self.iso[(level, "tf")])):
                if (((a == 1) & (b == 0)) | ((a == 0) & (b == 1))).any():
                    raise ValueError(f"{short}/{level}: tie-free and as-run disagree on a certainty")

    def hits(self, variant: str, level: str = "item") -> tuple[np.ndarray, np.ndarray]:
        return self.h[(level, variant)], self.iso[(level, variant)]


def ladder_design(dev: frozenset[str]) -> dict:
    """The dev ladder's structure, read from the two JSON files: arms read it, never re-derive it."""
    corpus = {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}
    dose = [r for r in json.loads(DOSE_JSON.read_text(encoding="utf-8")) if r["parent_key"] in dev]
    iso = [r for r in json.loads(ISO_JSON.read_text(encoding="utf-8")) if r["parent_key"] in dev]
    golds = sorted({r["gold_item_key"] for r in dose})
    pos = {g: i for i, g in enumerate(golds)}
    n = len(golds)
    concept = np.empty(n, dtype=object)
    dose_key = np.empty((n, len(RUNGS)), dtype=object)
    iso_key = np.empty((n, len(TYPES)), dtype=object)
    member = np.zeros((n, 6, len(TYPES)), dtype=bool)  # rung 0 holds no type
    added = np.full((n, 6), -1)
    rung_flag = np.zeros((n, 6), dtype=bool)
    iso_flag = np.zeros((n, len(TYPES)), dtype=bool)
    rung_text = np.empty((n, len(RUNGS)), dtype=object)
    iso_text = np.empty((n, len(TYPES)), dtype=object)
    for r in dose:
        i, k = pos[r["gold_item_key"]], int(r["modification_count"])
        concept[i] = r["parent_key"]
        dose_key[i, k - 1] = r["item_key"]
        rung_text[i, k - 1] = r["text"]
        for t in r["modification_types"]:
            member[i, k, TI[t]] = True
        f = text_flags(r["text"], corpus[r["gold_item_key"]])
        rung_flag[i, k] = bool(f["doubled"] or f["topo"])
    for r in iso:
        i, j = pos[r["gold_item_key"]], TI[r["modification_types"][0]]
        iso_key[i, j] = r["item_key"]
        iso_text[i, j] = r["text"]
        f = text_flags(r["text"], corpus[r["gold_item_key"]])
        iso_flag[i, j] = bool(f["doubled"] or f["topo"])
    if any(v is None for v in dose_key.ravel()) or any(v is None for v in iso_key.ravel()):
        raise ValueError("a dev ladder leaf lacks a rung or an isolated type")
    for k in RUNGS:
        diff = member[:, k] & ~member[:, k - 1]
        if (diff.sum(1) != 1).any() or (member[:, k - 1] & ~member[:, k]).any():
            raise ValueError(f"rung {k} is not rung {k - 1} plus one type")
        added[:, k] = diff.argmax(1)
    same_draw = np.array([rung_text[i, 0] == iso_text[i, added[i, 1]] for i in range(n)])
    return {"golds": golds, "concept": concept, "dose_key": dose_key, "iso_key": iso_key, "member": member,
            "added": added, "rung_flag": rung_flag, "iso_flag": iso_flag, "same_draw": same_draw,
            "n_dose": len(dose), "n_iso": len(iso)}


# --------------------------------------------------------------------------- per-leaf terms


def predicted(h: np.ndarray, iso: np.ndarray, member: np.ndarray, k: int, clip: bool = True) -> np.ndarray:
    """The additive prediction of rung k per leaf: h_id + Σ_{t∈S_k} (h_iso,t − h_id), clipped to [0, 1]."""
    s = h[:, 0] + ((iso - h[:, [0]]) * member[:, k]).sum(1)
    return np.clip(s, 0.0, 1.0) if clip else s


def terms(kind: str, L: Ladder, D: dict, variant: str, rungs: list[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Per-leaf numerator and denominator of a statistic; the statistic is Σ num ÷ Σ den (A2)."""
    h, iso = L.hits(variant)
    member, added = D["member"], D["added"]
    clean = variant == "clean"
    rungs = rungs or STACK_RUNGS
    n = len(h)
    num, den = np.zeros(n), np.zeros(n)
    if kind == "x1":
        for k in rungs:
            m = np.ones(n)
            if clean:
                m = (~D["rung_flag"][:, k] & ~(D["iso_flag"] & member[:, k]).any(1)).astype(float)
            num += (h[:, k] - predicted(h, iso, member, k)) * m
            den += m
    elif kind == "x2":
        for k in rungs:
            t = added[:, k]
            hi = iso[np.arange(n), t]
            m = np.ones(n)
            if clean:
                m = (~D["rung_flag"][:, k - 1] & ~D["rung_flag"][:, k] & ~D["iso_flag"][np.arange(n), t]).astype(float)
            at_risk = h[:, k - 1] * m
            num += at_risk * (hi * (1 - h[:, k]) - (1 - hi) * h[:, k])
            den += at_risk
    elif kind in ("x3", "x3q"):
        x = np.arange(6) - np.arange(6).mean()
        basis = x if kind == "x3" else x ** 2 - (x ** 2).mean()
        coef = (h * basis).sum(1) / (basis ** 2).sum()
        m = np.ones(n) if not clean else (~D["rung_flag"].any(1)).astype(float)
        num, den = coef * m, m
    else:
        raise ValueError(kind)
    return num, den


# --------------------------------------------------------------------------- bootstrap (D-053)


def strat_weights(concepts: np.ndarray, label: str) -> np.ndarray:
    """B × n leaf weights: within each concept, its leaves resampled with replacement (D-053)."""
    rng = _rng("strat|" + label)
    w = np.zeros((B, len(concepts)))
    for c in sorted(set(concepts)):
        idx = np.flatnonzero(concepts == c)
        w[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1.0 / len(idx)), size=B)
    return w


def cluster_leaf_weights(concepts: np.ndarray, label: str) -> np.ndarray:
    """B × n leaf weights from S2's concept-clustered bootstrap: each leaf carries its concept's multiplicity."""
    labels = np.unique(concepts)
    g = _rng("cluster|" + label).multinomial(len(labels), np.full(len(labels), 1.0 / len(labels)), size=B)
    return g[:, np.searchsorted(labels, concepts)].astype(float)


def ratio_draws(num: np.ndarray, den: np.ndarray, w: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return (w @ num) / (w @ den)


def stat(num: np.ndarray, den: np.ndarray) -> float:
    return float(num.sum() / den.sum()) if den.sum() else float("nan")


def summarise(num: np.ndarray, den: np.ndarray, concepts: np.ndarray, label: str) -> dict:
    s = ratio_draws(num, den, strat_weights(concepts, label))
    c = ratio_draws(num, den, cluster_leaf_weights(concepts, label))
    s, c = s[np.isfinite(s)], c[np.isfinite(c)]
    per = {k: stat(num[concepts == k], den[concepts == k]) for k in sorted(set(concepts))}
    return {"est": stat(num, den), "s": ci(s), "c": ci(c), "p": boot_p(s) if len(s) else 1.0,
            "draws": s, "per": per, "den": float(den.sum()), "leaves": int((den > 0).sum())}


# --------------------------------------------------------------------------- tests


def read(r: dict, side: int) -> str:
    lo, hi = r["s"]
    signs = sum(1 for v in r["per"].values() if np.isfinite(v) and v * side > 0)
    good = (lo > 0) if side > 0 else (hi < 0)
    bad = (hi < 0) if side > 0 else (lo > 0)
    if good and r["holm"] < ALPHA and signs >= SIGN_MIN:
        return "supported"
    if bad and r["holm"] < ALPHA:
        return "contradicted"
    return "not supported"


def evaluate(LL: dict, D: dict, floors: dict) -> list[dict]:
    results = []
    for tid, hyp, what, kind, side in TESTS:
        for short in BASE7:
            row = {"id": tid, "hyp": hyp, "what": what, "arm": short, "side": side, "floor": floors[short] < FLOOR}
            for v in VARIANTS:
                num, den = terms(kind, LL[short], D, v)
                row[v] = summarise(num, den, D["concept"], f"s8|{tid}|{short}|{v}")
            row["thin"] = kind == "x2" and row["tf"]["den"] < MIN_AT_RISK
            results.append(row)
    for v in VARIANTS:
        ps = [r[v]["p"] for r in results]
        for r, h, q in zip(results, holm(ps), bh(ps)):
            r[v].update(holm=h, bh=q)
            r[v]["reading"] = "not tested" if (r["floor"] or r["thin"]) else read(r[v], r["side"])
    for r in results:
        r["robust"] = r["clean"]["reading"] == r["tf"]["reading"]
        r["differs_run"] = r["run"]["reading"] != r["tf"]["reading"]
    return results


def h4_resolution(results: list[dict]) -> tuple[str, list[str], list[str]]:
    """The design's rule: supported if X1 and X2 hold for every tested arm; contradicted if any X1 is."""
    tested = [r for r in results if r["id"] in ("X1", "X2") and r["tf"]["reading"] != "not tested"]
    arms = sorted({r["arm"] for r in tested})
    held = [a for a in arms if all(r["tf"]["reading"] == "supported" for r in tested if r["arm"] == a)
            and {r["id"] for r in tested if r["arm"] == a} == {"X1", "X2"}]
    contra = [r["arm"] for r in tested if r["id"] == "X1" and r["tf"]["reading"] == "contradicted"]
    if contra:
        return "contradicted", held, contra
    if arms and held == arms:
        return "supported", held, contra
    return "partly supported", held, contra


# --------------------------------------------------------------------------- formatting


def name(short: str) -> str:
    return f"`{short}`" + (" **oracle**" if short in ORACLE else "")


def thin(n: int) -> str:
    return f"{n}" + (" ‡" if n < THIN_LEAVES else "")


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S8 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def population_lines(D: dict) -> list[str]:
    n, conc = len(D["golds"]), sorted(set(D["concept"]))
    return [
        f"**Population.** Dev E3 ladder: {n:,} leaves over {len(conc)} concepts ("
        + ", ".join(f"`{c}` {int((D['concept'] == c).sum()):,}" for c in conc)
        + f"); {D['n_dose']:,} `{DOSE}` and {D['n_iso']:,} `{ISO}` queries, each leaf paired with its own `{IDENT}` "
        "result. No query is excluded at either level (n excluded 0 everywhere; work item 1). Intervals: "
        "**stratified** = leaves resampled within concept (D-053, the one read); **concept** = whole concepts "
        f"resampled, resting on {len(conc)} clusters, printed and not read. B = {B:,}, seed {SEED}.", "",
    ]


def sources_block(querysets: list[str], arms: list[str] | None = None, inputs: tuple[Path, ...] = ()) -> list[str]:
    lines = ["", "## Sources", "", "| query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
             "|---|---|---:|---|---|---|---|"]
    for queryset in querysets:
        for _, short, _, _ in ARMS:
            if arms is not None and short not in arms:
                continue
            if not (run_dir(queryset, short) / "run_meta.json").is_file():
                continue
            m = meta(queryset, short)
            lines.append(f"| `{queryset}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                         f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
                         f"`{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (DOSE_JSON, ISO_JSON, CORPUS_JSON, *inputs)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals; readings on the stratified leaf "
              "draws (D-053). Split `dev`.", analysis_stack.stamp()]
    return lines


def step_terms(L: Ladder, D: dict, select) -> tuple[np.ndarray, np.ndarray]:
    """Per-leaf X2 numerator and at-risk mass over the steps `select(k)` marks (A4: T5 by type, T7)."""
    h, iso = L.hits("tf")
    n = len(h)
    num, den = np.zeros(n), np.zeros(n)
    for k in STACK_RUNGS:
        sel = select(k).astype(float)
        hi = iso[np.arange(n), D["added"][:, k]]
        num += sel * h[:, k - 1] * (hi * (1 - h[:, k]) - (1 - hi) * h[:, k])
        den += sel * h[:, k - 1]
    return num, den


def concept_cells(per: dict) -> str:
    return " · ".join(f"{fd(v)}" if np.isfinite(v) else "—" for v in per.values())


# --------------------------------------------------------------------------- T1 ladder


def write_ladder(LL: dict, D: dict, floors: dict) -> None:
    lines = header("T1: the dose ladder, item and parent level (dev)", [
        "Eighteen arms on the dev ladder. Each rung is paired with the arm's identity on the same leaf;",
        "δ_k = rung k − identity. Tie-free is the reading (D-028 note); as run beside it. **Retention** is",
        "P(hit at rung k | hit at identity). **Δ** = parent − item at that rung.",
    ])
    lines += population_lines(D)
    lines += [f"**Floor**: identity item Acc@1 (tie-free, ladder leaves) below {FLOOR:.2f} (S4); floor arms are "
              "printed, never read. Structured arms are profiled, not tested (D-046).", ""]
    for level in ("item", "parent"):
        lines += [f"## {level.capitalize()} level", "",
                  "| arm | kind | rung | n | n excluded | Acc@1 | δ | CI (stratified) | CI (concept) | retention | Δ | "
                  "Acc@1, as run | δ, as run | per concept (A4) |", "|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|"]
        for _, short, _, kind in ARMS:
            h, _ = LL[short].hits("tf", level)
            hr, _ = LL[short].hits("run", level)
            hp, _ = LL[short].hits("tf", "parent")
            hi, _ = LL[short].hits("tf", "item")
            fl = " (floor)" if floors[short] < FLOOR else ""
            lines.append(f"| {name(short)}{fl} | {kind} | identity | {len(h):,} | 0 | {f4(h[:, 0].mean())} | — | — | — | — | "
                         f"{f4((hp[:, 0] - hi[:, 0]).mean())} | {f4(hr[:, 0].mean())} | — | — |")
            for k in RUNGS:
                d = h[:, k] - h[:, 0]
                r = summarise(d, np.ones(len(d)), D["concept"], f"s8|T1|{short}|{level}|{k}")
                kept = h[:, 0].sum()
                ret = float((h[:, 0] * h[:, k]).sum() / kept) if kept else float("nan")
                lines.append(f"| {name(short)}{fl} | {kind} | {k} | {len(h):,} | 0 | {f4(h[:, k].mean())} | {fd(r['est'])} | "
                             f"{fci(r['s'], True)} | {fci(r['c'], True)} | {f4(ret)} | "
                             f"{f4((hp[:, k] - hi[:, k]).mean())} | {f4(hr[:, k].mean())} | "
                             f"{fd((hr[:, k] - hr[:, 0]).mean())} | {concept_cells(r['per'])} |")
        lines.append("")
    lines += sources_block([DOSE, IDENT])
    write(OUT / "ladder.md", lines)


# --------------------------------------------------------------------------- T2 isolated


def single_reference(dup: set[str], parents: dict[str, str]) -> dict:
    """S4's pooled `single_texto` δ per arm and type (S4's population), for printing beside T2."""
    types = {r["item_key"]: r["modification_types"][0] for r in json.loads(SINGLE_JSON.read_text(encoding="utf-8"))}
    out = {}
    for _, short, _, _ in ARMS:
        frame = columns(paired(short, SINGLE, dup, parents, S4_EXCLUDED), "tf")
        frame = frame.assign(type=frame["q"].map(types))
        for t in TYPES:
            sub = frame[frame["type"] == t]
            if len(item(sub)):
                out[(short, t)] = cell(sub, "item", f"s8|T2|S4|{short}|{t}")
    return out


def write_isolated(LL: dict, D: dict, ref: dict) -> None:
    lines = header("T2: each type alone, on the ladder's own leaves (dev, item level, tie-free)", [
        "δ_iso = isolated − identity, per arm and type, on the same leaves. These are the components of the",
        "clipped-additive prediction. S4's pooled `single_texto` δ for the type is printed beside it: a",
        "**different population** (other leaves and concepts), never read as a contrast (design).",
    ])
    lines += population_lines(D)
    lines += ["| arm | type | leaves | n excluded | identity | isolated | δ_iso | CI (stratified) | CI (concept) | "
              "S4 `single_texto` n | S4 δ | S4 CI (concept) | per concept (A4) |",
              "|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---|---|"]
    for _, short, _, _ in ARMS:
        h, iso = LL[short].hits("tf")
        for t in TYPES:
            d = iso[:, TI[t]] - h[:, 0]
            r = summarise(d, np.ones(len(d)), D["concept"], f"s8|T2|{short}|{t}")
            s4 = ref.get((short, t))
            lines.append(f"| {name(short)} | `{t}` | {len(d):,} | 0 | {f4(h[:, 0].mean())} | {f4(iso[:, TI[t]].mean())} | "
                         f"{fd(r['est'])} | {fci(r['s'], True)} | {fci(r['c'], True)} | "
                         + (f"{s4['n']:,} | {fd(s4['delta'])} | {fci(s4['c'], True)} |" if s4 else "— | — | — |")
                         + f" {concept_cells(r['per'])} |")
    lines += sources_block([ISO, IDENT, SINGLE], inputs=(SINGLE_JSON,))
    write(OUT / "isolated.md", lines)


# --------------------------------------------------------------------------- T3 draw noise


def draw_noise(LL: dict, D: dict) -> dict:
    """Per arm: expected disagreement of rung-1 and isolated hit for the same leaf and type, by draw (A2)."""
    out = {}
    idx = np.arange(len(D["golds"]))
    for _, short, _, _ in ARMS:
        h, iso = LL[short].hits("tf")
        a, b = h[:, 1], iso[idx, D["added"][:, 1]]
        dis = a * (1 - b) + b * (1 - a)
        same = D["same_draw"]
        out[short] = {"same": (int(same.sum()), float(dis[same].mean()) if same.any() else float("nan")),
                      "diff": (int((~same).sum()), float(dis[~same].mean()) if (~same).any() else float("nan")),
                      "by_type": {t: (int(((D["added"][:, 1] == TI[t]) & ~same).sum()),
                                      float(dis[(D["added"][:, 1] == TI[t]) & ~same].mean())
                                      if ((D["added"][:, 1] == TI[t]) & ~same).any() else float("nan"))
                                  for t in TYPES}}
    return out


def write_noise(noise: dict, D: dict) -> None:
    lines = header("T3: realisation check — rung 1 against the isolated query of the same leaf and type (dev, tie-free)", [
        "The isolated set and the ladder are different rewrite draws (design, entry state). On rung 1 the two",
        "carry the same single type on the same leaf, so their disagreement measures draw noise alone.",
        "Disagreement = P(one hits, the other misses), the expectation under independent tie-breaks. The",
        "text-different rate is the bar an X-excess must clear before it is read as interaction (design, A2).",
    ])
    lines += population_lines(D)
    lines += ["| arm | text-equal leaves | disagreement | text-different leaves | disagreement | n excluded (A4) |",
              "|---|---:|---:|---:|---:|---:|"]
    for _, short, _, _ in ARMS:
        s, d = noise[short]["same"], noise[short]["diff"]
        lines.append(f"| {name(short)} | {s[0]:,} | {f4(s[1])} | {d[0]:,} | {f4(d[1])} | 0 |")
    lines += ["", "## Text-different rung-1 leaves, by type", "",
              "| arm | " + " | ".join(f"`{t}`" for t in TYPES) + " |", "|---|" + "---:|" * len(TYPES)]
    for short in BASE7:
        bt = noise[short]["by_type"]
        lines.append(f"| {name(short)} | " + " | ".join(
            (f"{f4(bt[t][1])} ({thin(bt[t][0])})" if bt[t][0] else "—") for t in TYPES) + " |")
    lines += ["", f"Leaves behind each cell in brackets; ‡ marks fewer than {THIN_LEAVES}."]
    lines += sources_block([DOSE, ISO])
    write(OUT / "draw_noise.md", lines)


# --------------------------------------------------------------------------- T4 X1 by rung


def write_additivity(LL: dict, D: dict, results: list[dict]) -> None:
    lines = header("T4: cumulative additivity, X1 (dev, item level, tie-free)", [
        "Per rung: the observed Acc@1, the clipped-additive prediction clip(h_id + Σ_{t∈S_k}(h_iso,t − h_id), 0, 1),",
        "and their difference; the unclipped sum is printed and never read (design). **Super** counts leaves",
        "predicted to survive that fail (as run); **sub** leaves predicted to fail that survive. **Floor-bound**",
        "is the share of leaves whose prediction is 0: they can only contribute sub-additively (design, risks).",
    ])
    lines += population_lines(D)
    lines += ["| arm | rung | leaves | observed | predicted | unclipped | observed − predicted | CI (stratified) | "
              "CI (concept) | per concept | super | sub | floor-bound | n excluded (A4) |",
              "|---|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|---:|---:|"]
    for short in BASE7:
        h, iso = LL[short].hits("tf")
        hr, isor = LL[short].hits("run")
        for k in RUNGS:
            pred = predicted(h, iso, D["member"], k)
            num, den = terms("x1", LL[short], D, "tf", rungs=[k])
            r = summarise(num, den, D["concept"], f"s8|T4|{short}|{k}")
            pr = predicted(hr, isor, D["member"], k)
            sup = int(((pr == 1) & (hr[:, k] == 0)).sum())
            sub = int(((pr == 0) & (hr[:, k] == 1)).sum())
            lines.append(f"| {name(short)} | {k} | {len(h):,} | {f4(h[:, k].mean())} | {f4(pred.mean())} | "
                         f"{fd(predicted(h, iso, D['member'], k, clip=False).mean())} | {fd(r['est'])} | "
                         f"{fci(r['s'], True)} | {fci(r['c'], True)} | {concept_cells(r['per'])} | {sup:,} | {sub:,} | "
                         f"{f4((pred == 0).mean())} | 0 |")
        x = next(r for r in results if r["id"] == "X1" and r["arm"] == short)["tf"]
        lines.append(f"| {name(short)} | pooled | {x['leaves']:,} | — | — | — | {fd(x['est'])} | {fci(x['s'], True)} | "
                     f"{fci(x['c'], True)} | {concept_cells(x['per'])} | — | — | — | 0 |")
    lines += ["", "Per-concept estimates in the order " + ", ".join(f"`{c}`" for c in sorted(set(D["concept"]))) + "."]
    lines += sources_block([DOSE, ISO, IDENT], arms=BASE7)
    write(OUT / "additivity.md", lines)


# --------------------------------------------------------------------------- T12 X1 decomposition (A6, post hoc)


def x1_split_terms(L: Ladder, D: dict, variant: str, weight: np.ndarray, open_only: bool) -> tuple[np.ndarray, np.ndarray]:
    """X1's per-leaf terms weighted by `weight`; with `open_only`, a leaf-rung counts only if its prediction is above 0."""
    h, iso = L.hits(variant)
    n = len(h)
    num, den = np.zeros(n), np.zeros(n)
    for k in STACK_RUNGS:
        pred = predicted(h, iso, D["member"], k)
        m = weight * ((pred > 0) if open_only else np.ones(n))
        num += (h[:, k] - pred) * m
        den += m
    return num, den


def write_x1_split(LL: dict, D: dict) -> None:
    lines = header("T12: X1 decomposed, post hoc and descriptive (dev, item level) — A6", [
        "Added after the audit (F1, F2); **not a registered test**: no Holm, no reading, never cited as evidence",
        "for or against H4. X1 (A2) split by the leaf's identity outcome, each leaf weighted by its expected",
        "identity hit (tie-free) or its hit as run, so a tie at identity splits its leaf between the rows. **Open**",
        "keeps only the leaf-rungs whose clipped-additive prediction is above 0, where X1 can move in either",
        "direction (T4, floor-bound); its leaf-rungs column is the mass X1 had left to test.",
    ])
    lines += population_lines(D)
    lines += ["| arm | scoring | subset | weight (leaves) | leaf-rungs | X1 | CI (stratified) | CI (concept) | per concept |",
              "|---|---|---|---:|---:|---:|---|---|---|"]
    for short in BASE7:
        for v in ("tf", "run"):
            h, _ = LL[short].hits(v)
            for label, w, open_only in (("all", np.ones(len(h)), False), ("hit at identity", h[:, 0], False),
                                        ("missed at identity", 1 - h[:, 0], False), ("all, open", np.ones(len(h)), True)):
                num, den = x1_split_terms(LL[short], D, v, w, open_only)
                r = summarise(num, den, D["concept"], f"s8|T12|{short}|{v}|{label}")
                lines.append(f"| {name(short)} | {VARIANT_LABEL[v]} | {label} | {w.sum():,.1f} | {den.sum():,.1f} | "
                             f"{fd(r['est'])} | {fci(r['s'], True)} | {fci(r['c'], True)} | {concept_cells(r['per'])} |")
    lines += ["", "Per-concept estimates in the order " + ", ".join(f"`{c}`" for c in sorted(set(D["concept"]))) + ".",
              "*All* reproduces T10's X1 for its scoring; the hit and missed rows sum to it, weighted by their leaf-rungs."]
    lines += sources_block([DOSE, ISO, IDENT], arms=BASE7)
    write(OUT / "x1_split.md", lines)


# --------------------------------------------------------------------------- T5 X2 marginal


def write_marginal(LL: dict, D: dict) -> None:
    lines = header("T5: marginal cost of the added edit, X2 (dev, item level, tie-free)", [
        "Over steps k − 1 → k where rung k − 1 is a hit (at-risk mass Σ h_{k−1}), with t the type added at k:",
        "**in company** = P(iso_t hits, rung k misses), **alone** = P(iso_t misses, rung k hits); X2 = in company",
        "− alone, per unit of at-risk mass. Conditioning on survival selects robust leaves, which works against",
        "X2 (design). Per added type the cells are descriptive; ‡ marks fewer than",
        f"{THIN_LEAVES} leaves.",
    ])
    lines += population_lines(D)
    lines += ["## By rung", "", "| arm | step | at risk | in company | alone | X2 | CI (stratified) | CI (concept) | "
              "per concept (A4) | n excluded (A4) |", "|---|---|---:|---:|---:|---:|---|---|---|---:|"]
    n = len(D["golds"])
    for short in BASE7:
        h, iso = LL[short].hits("tf")
        for k in STACK_RUNGS:
            num, den = terms("x2", LL[short], D, "tf", rungs=[k])
            r = summarise(num, den, D["concept"], f"s8|T5|{short}|{k}")
            hi = iso[np.arange(n), D["added"][:, k]]
            comp = float((h[:, k - 1] * hi * (1 - h[:, k])).sum())
            alone = float((h[:, k - 1] * (1 - hi) * h[:, k]).sum())
            lines.append(f"| {name(short)} | {k - 1}→{k} | {f4(den.sum())} | {f4(comp)} | {f4(alone)} | {fd(r['est'])} | "
                         f"{fci(r['s'], True)} | {fci(r['c'], True)} | {concept_cells(r['per'])} | 0 |")
    lines += ["", "## By added type (steps pooled)", "",
              "| arm | type | steps | leaves | at risk | X2 | CI (stratified, A4) | CI (concept, A4) | per concept (A4) | "
              "n excluded (A4) |", "|---|---|---:|---:|---:|---:|---|---|---|---:|"]
    for short in BASE7:
        h, iso = LL[short].hits("tf")
        for t in TYPES:
            num = den = 0.0
            steps, leaves = 0, set()
            for k in STACK_RUNGS:
                sel = D["added"][:, k] == TI[t]
                hi = iso[sel, TI[t]]
                num += float((h[sel, k - 1] * (hi * (1 - h[sel, k]) - (1 - hi) * h[sel, k])).sum())
                den += float(h[sel, k - 1].sum())
                steps += int(sel.sum())
                leaves |= set(np.flatnonzero(sel))
            tn, td = step_terms(LL[short], D, lambda k, t=t: D["added"][:, k] == TI[t])
            r = summarise(tn, td, D["concept"], f"s8|T5|{short}|type|{t}")
            lines.append(f"| {name(short)} | `{t}` | {steps:,} | {thin(len(leaves))} | {f4(den)} | "
                         + (f"{fd(num / den)} |" if den else "— |")
                         + f" {fci(r['s'], True)} | {fci(r['c'], True)} | {concept_cells(r['per'])} | 0 |")
    lines += sources_block([DOSE, ISO], arms=BASE7)
    write(OUT / "marginal.md", lines)


# --------------------------------------------------------------------------- T6 X3 dose-response


def write_dose_response(LL: dict, D: dict, results: list[dict]) -> None:
    lines = header("T6: within-leaf dose-response, X3 (dev, item level)", [
        "Per leaf, the OLS slope of item hit on dose 0–5 (identity = 0) and the coefficient of the centred",
        "quadratic, averaged over leaves: the leaf fixed-effects estimate on a balanced ladder (design). The",
        "slope establishes a dose effect; it does not bear on additivity. The quadratic is descriptive: a floor",
        "bends the curve upward, so a negative quadratic is against the floor, not because of it.",
    ])
    lines += population_lines(D)
    lines += ["| arm | slope | CI (stratified) | CI (concept) | per concept | slope, as run | quadratic | CI (stratified) | "
              "quadratic CI (concept, A4) | quadratic per concept (A4) | n excluded (A4) |",
              "|---|---:|---|---|---|---:|---:|---|---|---|---:|"]
    for short in BASE7:
        x = next(r for r in results if r["id"] == "X3" and r["arm"] == short)
        num, den = terms("x3q", LL[short], D, "tf")
        q = summarise(num, den, D["concept"], f"s8|T6|{short}|quad")
        lines.append(f"| {name(short)} | {fd(x['tf']['est'])} | {fci(x['tf']['s'], True)} | {fci(x['tf']['c'], True)} | "
                     f"{concept_cells(x['tf']['per'])} | {fd(x['run']['est'])} | {fd(q['est'])} | {fci(q['s'], True)} | "
                     f"{fci(q['c'], True)} | {concept_cells(q['per'])} | 0 |")
    lines += sources_block([DOSE, IDENT], arms=BASE7)
    write(OUT / "dose_response.md", lines)


# --------------------------------------------------------------------------- T7 pairs


def write_pairs(LL: dict, D: dict) -> None:
    lines = header("T7: pairwise, descriptive (dev, item level, tie-free)", [
        "For each pair of types, the steps that complete it: the type added at k is one of the pair and the",
        "other is already present at k − 1. X2's excess on those steps, per unit of at-risk mass. Pairs that",
        "never co-occur are not identifiable (D-009) and are marked; no cell is read (design).",
    ])
    lines += population_lines(D)
    lines += ["| pair | " + " | ".join(name(s) for s in BASE7) + " | leaves |", "|---|" + "---:|" * (len(BASE7) + 1)]
    n = len(D["golds"])
    for a, b in combinations(TYPES, 2):
        if frozenset({a, b}) in NOT_IDENTIFIABLE:
            lines.append(f"| `{a}` × `{b}` | " + " | ".join("not identifiable" for _ in BASE7) + " | 0 |")
            continue
        cells, leaves = [], set()
        for short in BASE7:
            h, iso = LL[short].hits("tf")
            num = den = 0.0
            for k in STACK_RUNGS:
                t = D["added"][:, k]
                prev = D["member"][:, k - 1]
                sel = ((t == TI[a]) & prev[:, TI[b]]) | ((t == TI[b]) & prev[:, TI[a]])
                hi = iso[np.arange(n), t][sel]
                num += float((h[sel, k - 1] * (hi * (1 - h[sel, k]) - (1 - hi) * h[sel, k])).sum())
                den += float(h[sel, k - 1].sum())
                leaves |= set(np.flatnonzero(sel))
            cells.append(fd(num / den) if den else "—")
        lines.append(f"| `{a}` × `{b}` | " + " | ".join(cells) + f" | {thin(len(leaves))} |")
    lines += ["", "## With intervals (A4)", "",
              "The cells above, each with its stratified and concept intervals and per-concept estimates. Descriptive.", "",
              "| pair | arm | leaves | n excluded | X2 excess | CI (stratified) | CI (concept) | per concept |",
              "|---|---|---:|---:|---:|---|---|---|"]
    for a, b in combinations(TYPES, 2):
        if frozenset({a, b}) in NOT_IDENTIFIABLE:
            continue

        def completes(k, a=a, b=b):
            t, prev = D["added"][:, k], D["member"][:, k - 1]
            return ((t == TI[a]) & prev[:, TI[b]]) | ((t == TI[b]) & prev[:, TI[a]])

        leaves = int(np.any([completes(k) for k in STACK_RUNGS], axis=0).sum())
        for short in BASE7:
            pn, pd_ = step_terms(LL[short], D, completes)
            if not pd_.sum():
                continue
            r = summarise(pn, pd_, D["concept"], f"s8|T7|{short}|{a}|{b}")
            lines.append(f"| `{a}` × `{b}` | {name(short)} | {thin(leaves)} | 0 | {fd(r['est'])} | {fci(r['s'], True)} | "
                         f"{fci(r['c'], True)} | {concept_cells(r['per'])} |")
    lines += sources_block([DOSE, ISO], arms=BASE7)
    write(OUT / "pairs.md", lines)


# --------------------------------------------------------------------------- T8 S7 reference


def write_s7_reference(LL: dict, D: dict, dup: set[str], parents: dict[str, str]) -> None:
    lines = header("T8: S7's stacked dose gradient beside the ladder's (dev, item level, tie-free)", [
        "S7's δ by `texto_modification_count` compares different concepts at each dose; the ladder's δ by rung",
        "compares the same leaves. **Between-population**, descriptive: printed so the two gradients can be seen",
        "side by side, never read as a contrast (design).",
    ])
    size, one_apart = leaf_density()
    keys = set(perquery(STACKED, "bm25_unigram")["query_item_key"].astype(str))
    feats = stacked_features(keys, size, one_apart)
    lines += ["| arm | dose | S7 n scored | S7 n excluded | S7 concepts | S7 δ | S7 CI (concept) | ladder leaves | "
              "ladder δ | ladder CI (stratified) | ladder CI (concept, A4) | ladder per concept (A4) | S7 CI (query, A4) | ladder n excluded (A4) |",
              "|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|---|---:|"]
    for short in BASE7:
        frame = columns(paired(short, STACKED, dup, parents).join(feats, on="q"), "tf")
        h, _ = LL[short].hits("tf")
        for k in sorted(set(feats["dose"]) | set(RUNGS)):
            sub = frame[frame["dose"] == k]
            s7 = cell(sub, "item", f"s8|T8|{short}|{k}") if len(item(sub)) else None
            # A5: T1's label, so the ladder side reuses T1's draws and prints T1's intervals (audit F9)
            lad = summarise(h[:, k] - h[:, 0], np.ones(len(h)), D["concept"], f"s8|T1|{short}|item|{k}") \
                if k in RUNGS else None
            lines.append(f"| {name(short)} | {k} | "
                         + (f"{s7['n']:,} | {s7['excluded']:,} | {s7['concepts']} | {fd(s7['delta'])} | {fci(s7['c'], True)} | "
                            if s7 else "— | — | — | — | — | ")
                         + (f"{len(h):,} | {fd(lad['est'])} | {fci(lad['s'], True)} |" if lad else "— | — | — |")
                         + (f" {fci(lad['c'], True)} | {concept_cells(lad['per'])} |" if lad else " — | — |")
                         + (f" {fci(s7['q'], True)} |" if s7 else " — |") + (" 0 |" if lad else " — |"))
    lines += sources_block([STACKED, DOSE, IDENT], arms=BASE7)
    write(OUT / "s7_reference.md", lines)


# --------------------------------------------------------------------------- T9 D-004, T10 predictions


def write_d004(D: dict, results: list[dict]) -> None:
    lines = header("T9: D-004 sensitivity (dev, tie-free)", [
        "Every X-reading recomputed without pantry-flagged queries (S3's detector, `pantry_flags.text_flags`):",
        "a leaf-rung drops from X1 if its rung or any isolated query it uses is flagged, a step from X2 if",
        "either rung or the added isolated query is, a leaf from X3 if any rung is (design, A2). A reading",
        "that changes category is *not robust*; the full-population reading stands (D-004).",
    ])
    lines += population_lines(D)
    lines += [f"Flagged: {int(D['rung_flag'].sum()):,} of {D['rung_flag'][:, 1:].size:,} dev rung queries, "
              f"{int(D['iso_flag'].sum()):,} of {D['iso_flag'].size:,} dev isolated queries.", "",
              "| test | arm | estimate | CI (stratified) | reading | clean estimate | clean CI (stratified) | clean leaves | "
              "clean reading | robust | clean CI (concept, A5) | clean per concept (A5) | clean Holm p (A5) |",
              "|---|---|---:|---|---|---:|---|---:|---|---|---|---|---:|"]
    for r in results:
        t, c = r["tf"], r["clean"]
        lines.append(f"| {r['id']} | {name(r['arm'])} | {fd(t['est'])} | {fci(t['s'], True)} | {t['reading']} | "
                     f"{fd(c['est'])} | {fci(c['s'], True)} | {c['leaves']:,} | {c['reading']} | "
                     f"{'yes' if r['robust'] else '**no**'} | {fci(c['c'], True)} | {concept_cells(c['per'])} | "
                     f"{fp(c['holm'])} |")
    lines += sources_block([DOSE, ISO, IDENT], arms=BASE7)
    write(OUT / "d004.md", lines)


def write_predictions(results: list[dict], floors: dict, noise: dict, D: dict) -> None:
    lines = header("T10: the registered predictions X1–X3 (dev)", [
        "Each test read tie-free (primary), as run and on the D-004 clean subset, under S4's rule as D-053",
        "amends it: **supported** needs the stratified interval to exclude 0 in the predicted direction, Holm",
        f"p < {ALPHA}, and the predicted sign in at least {SIGN_MIN} of the {len(set(D['concept']))} concepts;",
        f"**contradicted** needs the interval to exclude 0 the other way and Holm p < {ALPHA}. Holm and BH run",
        f"across all {len(results)} tests, per reading. All tests are **blind** (no arm had run on either set).",
        f"*Not tested*: a floor arm, or X2 with at-risk mass below {MIN_AT_RISK}.",
    ])
    lines += population_lines(D)
    lines += ["| test | arm | statement | estimate | CI (stratified) | CI (concept) | per concept | p | Holm p | BH q | "
              "reading | as run | clean | text-different draw noise | exceeds noise | as-run estimate (A5) | "
              "as-run CI (stratified, A5) | as-run CI (concept, A5) | as-run per concept (A5) | as-run Holm p (A5) | "
              "as run exceeds noise (A5) |",
              "|---|---|---|---:|---|---|---|---:|---:|---:|---|---|---|---:|---|---:|---|---|---|---:|---|"]
    for r in results:
        t, a = r["tf"], r["run"]
        nz = noise[r["arm"]]["diff"][1]
        x3 = r["id"] == "X3"
        exceeds = "—" if x3 else ("yes" if abs(t["est"]) > nz else "no")
        # A5: the same T3 bar (tie-free, A2 d) against the as-run estimate; ⚐ when the two disagree (audit F3)
        run_exceeds = "—" if x3 else ("yes" if abs(a["est"]) > nz else "no") + (" ⚐" if (abs(a["est"]) > nz) != (abs(t["est"]) > nz) else "")
        flag = " ⚑" if r["differs_run"] else ""
        lines.append(f"| {r['id']} | {name(r['arm'])} | {r['what']} | {fd(t['est'])} | {fci(t['s'], True)} | "
                     f"{fci(t['c'], True)} | {concept_cells(t['per'])} | {fp(t['p'])} | {fp(t['holm'])} | {fp(t['bh'])} | "
                     f"**{t['reading']}**{flag} | {a['reading']} | {r['clean']['reading']} | {f4(nz)} | {exceeds} | "
                     f"{fd(a['est'])} | {fci(a['s'], True)} | {fci(a['c'], True)} | {concept_cells(a['per'])} | "
                     f"{fp(a['holm'])} | {run_exceeds} |")
    verdict, held, contra = h4_resolution(results)
    lines += ["", "⚑ the as-run reading differs from the tie-free one. ⚐ (A5) the as-run estimate and the tie-free "
              "one fall on different sides of the draw-noise bar.", "",
              "## H4 under the design's rule", "",
              f"**{verdict}** on these leaves (tie-free), by the design's three-way rule: supported if X1 and X2 "
              "hold for every tested arm, contradicted if X1 reads contradicted for any, partly supported otherwise. "
              "X1 and X2 both supported for: " + (", ".join(name(a) for a in held) or "no arm") + ". "
              + " ".join(f"{tid} supported for: " + (", ".join(name(r['arm']) for r in results
                         if r["id"] == tid and r["tf"]["reading"] == "supported") or "no arm") + "."
                         for tid in ("X1", "X2"))
              + " X1 contradicted for: " + (", ".join(name(a) for a in contra) or "no arm") + ". Scope: the "
              f"{len(set(D['concept']))} dev ladder concepts ("
              + ", ".join(f"`{c}`" for c in sorted(set(D["concept"])))
              + "), all large families; isolated and ladder edits are different draws (T3).", "",
              "## Floors", "", "| arm | identity item Acc@1 on the ladder leaves (tie-free) | floor |", "|---|---:|---|"]
    lines += [f"| {name(s)} | {f4(floors[s])} | {'yes' if floors[s] < FLOOR else 'no'} |" for s in BASE7]
    lines += sources_block([DOSE, ISO, IDENT], arms=BASE7)
    write(OUT / "predictions.md", lines)


# --------------------------------------------------------------------------- Fig. 6, T11


def write_figure(LL: dict, D: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGS.mkdir(parents=True, exist_ok=True)
    lines = header("Fig. 6, draft, and the numbers it plots", [
        "Per arm, observed item Acc@1 (tie-free) against dose on the dev ladder, with the clipped-additive",
        "prediction from the isolated set at each rung. Every plotted value is printed below.",
    ])
    fig, axes = plt.subplots(2, 4, figsize=(14, 7), sharex=True, sharey=True)
    rows = []
    for ax, short in zip(axes.flat, BASE7):
        h, iso = LL[short].hits("tf")
        obs = [float(h[:, k].mean()) for k in range(6)]
        pred = [float(h[:, 0].mean())] + [float(predicted(h, iso, D["member"], k).mean()) for k in RUNGS]
        ax.plot(range(6), obs, "o-", color="black", ms=4, label="observed")
        ax.plot(range(6), pred, "s--", color="tab:blue", ms=4, label="clipped-additive")
        ax.set_title(short, fontsize=8)
        ax.grid(alpha=0.3)
        rows += [(short, k, obs[k], pred[k]) for k in range(6)]
    axes.flat[-1].axis("off")
    axes.flat[0].legend(fontsize=7)
    for ax in axes[-1]:
        ax.set_xlabel("dose (identity = 0)")
    for ax in axes[:, 0]:
        ax.set_ylabel("item Acc@1 (tie-free)")
    fig.suptitle("Fig. 6 — the dose ladder against its clipped-additive prediction")
    fig.tight_layout()
    fig.savefig(FIGS / "fig6_ladder.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines += ["| arm | dose | observed | clipped-additive |", "|---|---:|---:|---:|"]
    lines += [f"| {name(s)} | {k} | {f4(o)} | {f4(p)} |" for s, k, o, p in rows]
    lines += ["", analysis_stack.stamp()]
    write(OUT / "figures.md", lines)


def write_provenance() -> None:
    lines = header("T11: run provenance (dev)", [
        f"Every run the S8 tables read. The `{DOSE}` and `{ISO}` runs are S8's (work item 2); the others are",
        "earlier sprints' runs, read, not re-run.",
    ])
    lines += ["| query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 | derived from |",
              "|---|---|---:|---|---|---|---|---|"]
    for queryset in (DOSE, ISO, IDENT, SINGLE, STACKED):
        for _, short, _, _ in ARMS:
            if not (run_dir(queryset, short) / "run_meta.json").is_file():
                continue
            m = meta(queryset, short)
            comps = ", ".join(f"`{c['run_id']}` @ `{c['code_commit'][:7]}`" for c in m.get("components", [])) or "—"
            lines.append(f"| `{queryset}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                         f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
                         f"`{m['query_set_sha256'][:16]}` | {comps} |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (DOSE_JSON, ISO_JSON, CORPUS_JSON, SINGLE_JSON)),
              "", analysis_stack.stamp()]
    write(OUT / "run_provenance.md", lines)


# --------------------------------------------------------------------------- main


def main() -> None:
    analysis_stack.require()
    OUT.mkdir(parents=True, exist_ok=True)
    dup = duplicated()
    parents = parent_of()
    D = ladder_design(load_split("dev"))
    if set(D["golds"]) & dup:
        raise ValueError("a dev ladder gold is a duplicate-texto leaf; the design assumed none")
    LL = {short: Ladder(short, D, parents) for _, short, _, _ in ARMS}
    floors = {s: float(LL[s].hits("tf")[0][:, 0].mean()) for s in LL}
    results = evaluate(LL, D, floors)
    noise = draw_noise(LL, D)

    write_ladder(LL, D, floors)
    write_isolated(LL, D, single_reference(dup, parents))
    write_noise(noise, D)
    write_additivity(LL, D, results)
    write_x1_split(LL, D)
    write_marginal(LL, D)
    write_dose_response(LL, D, results)
    write_pairs(LL, D)
    write_s7_reference(LL, D, dup, parents)
    write_d004(D, results)
    write_predictions(results, floors, noise, D)
    write_figure(LL, D)
    write_provenance()
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
