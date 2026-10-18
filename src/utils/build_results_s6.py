"""S6 — statistical analysis and mediation: T1–T8 and Figs. 1–3 (design frozen at `8abf24f`, A1–A2).

    python src/utils/build_results_s6.py        # in the sprint container, bc3cat-s3

Reads, and never writes, `runs/OE/{texto,single_texto,single_l2_texto}/<arm>` for the fifteen S4 arms.
Writes `docs/synthetic-oe/results/S6/`. The pairing is S4's (treatment effect on the treated, the same
arm's `texto` run on the same gold), imported, not copied; the bootstrap is S2's, seeded by label.

What is new here, and where the design fixes it:
- **Tie-free** readings at item and parent level and for ratios (design, A2 a): each query's rank-1
  tied set is read from its top-100; identity and modified queries are tie-broken independently.
- **Models** M0–M2 per non-floor base arm, as linear mixed models (statsmodels, REML) for the adjusted
  point estimates, and as fixed-effects OLS resampled by concept for every registered interval. The OLS
  is solved by Frisch–Waugh within type, from per-(concept, type) sums, so a bootstrap draw is a
  weighted sum and not a refit.
- **Registered tests** R1–R6 (21), each tie-free (primary), as run, and on the D-004 clean subset.
- The **L2w** population is `single_l2_texto` (D-043), read blind; L2s (S4's) and L2∪ are printed only.
- **A8 (D-061):** `--v2` reads S4 A6's runs on `single_texto_v2` in place of `single_texto` (the same records in
  the same order, `text` repaired on part of the `template_paraphrase` cell) and writes T1–T8 and Figs. 1–3 under
  `results/S6/v2/`, refitting M0–M2 (one BLAS thread, A6) and recomputing the covariates, the D-004 flags and the
  drift flags on the v2 texts. `single_l2_texto` is untouched by the delivery and is read as today. The SINGLE
  modifications sidecar (`OE_single_modifications.jsonl`) stays v1's: its keys are the same records, and the
  repaired strings are L3 template rewrites, which the sidecar returns as undecidable whatever the text. The v1
  results are computed in the same process (same functions, same bootstrap labels, `_PM_CACHE` cleared between
  the two) and `results/S6/v2/comparison.md` sets R1–R6, every fixed effect of M0–M2 and PM on v1 beside v2, with
  v2 − v1 from the paired draws where they align (`utils.v2_variant`). A sensitivity table, not a test. The base
  mode (no flag) regenerates `results/S6/` byte for byte.

The analysis stack is pinned (`analysis_stack.py`, A1): the script refuses to run on another.

    python src/utils/build_results_s6.py --v2   # v2, results/S6/v2/, plus comparison.md
"""

from __future__ import annotations

import json
import os

#: The mixed fits are sensitive to floating-point summation order: the leaf variance component sits near zero,
#: and whether the optimiser converges with it changed with the BLAS thread count (A6). One thread makes every
#: fit deterministic wherever this runs. Set before numpy is imported, because BLAS reads it at load time.
BLAS_THREADS = 1
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_var] = str(BLAS_THREADS)
import subprocess
import sys
import warnings
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils import analysis_stack  # noqa: E402
from utils import v2_variant as v2v  # noqa: E402
from utils.build_overlap import lexical_coverage, numbers_in, numeric_coverage  # noqa: E402
from utils.build_results_s2 import (  # noqa: E402
    ALPHA, B, SEED, _rng, bh, boot_cluster, boot_p, boot_query, ci, f4, fci, fd, fp, holm, write,
)
from utils.build_results_s4 import (  # noqa: E402
    AMENDMENT_EXCLUDED as S4_EXCLUDED, ARMS, CORPUS_JSON, DIR, FEW_CLUSTERS, FLOOR, LAYERS, MARGIN, ORACLE,
    RUNS, SIDECAR, SINGLE_JSON, TWIN, TYPES, _evaluate_prediction, duplicated, meta, perquery,
    reading as s4_reading, require_runs, token_distance,
)
from utils.build_results_s5 import P8_DEV, iter_top100  # noqa: E402
from utils.pantry_flags import load_sidecar, sidecar_doubling, sidecar_topo, text_flags  # noqa: E402
from utils.provenance import sha256_file  # noqa: E402

DATA = REPO / "data" / "processed"
L2_JSON = DATA / "OE_single_l2_texto.json"
SINGLE_SIDECAR = DATA / "OE_single_modifications.jsonl"
L2_SIDECAR = DATA / "OE_single_l2_modifications.jsonl"
RESULTS_S6 = REPO / "docs" / "synthetic-oe" / "results" / "S6"
OUT = RESULTS_S6
FIGS = OUT / "figures"
GENERATOR = "src/utils/build_results_s6.py"

SINGLE, L2W = "single_texto", "single_l2_texto"
L2_TYPES = LAYERS["L2"]
V2_MODE = False


def configure(v2: bool) -> None:
    """A8: point the module at `single_texto_v2` and `results/S6/v2/`, or back at the base mode (identity).

    `SINGLE_JSON` is this module's own global (imported from S4 by value), so it is re-pointed here; S4's stays
    whatever S4's own `configure` set. The SINGLE sidecar is not re-pointed (module docstring).
    """
    global V2_MODE, SINGLE, SINGLE_JSON, OUT, FIGS, GENERATOR
    V2_MODE = v2
    SINGLE = v2v.mapped("single_texto", v2)
    SINGLE_JSON = DATA / f"OE_{SINGLE}.json"
    OUT = v2v.out_dir(RESULTS_S6, v2)
    FIGS = OUT / "figures"
    GENERATOR = v2v.generator_label("src/utils/build_results_s6.py", v2)

#: The seven non-floor base arms the design names (constraint "Arms").
BASE7 = ["bm25_unigram", "bm25_unigram_params", "tfidf_phrases_replace", "bge_m3_colbert", "bge_m3_dense",
         "dense_e5", "dense_es_hiiamsid"]

#: M1's covariates: the three overlap deficits and the no-number indicator, each zero at identity (A2 b).
DEFICITS = ["lex_def", "num_def", "nonum", "dnum_def"]
DEFICIT_LABEL = {
    "lex_def": "1 − lexical coverage",
    "num_def": "1 − numeric coverage",
    "nonum": "no number left (query none, gold some)",
    "dnum_def": "− Δ numbers (gold − query)",
    "d_tok": "d_tok",
}

#: R3's threshold on the proportion mediated ("most"), R5's on the L1 : L3 ratio ("an order of
#: magnitude"), the power and the width that reopens D-043 ruling 3 (design).
PM_NULL = 0.5
RATIO_NULL = 10.0
POWER = 0.8
WIDE_L2 = 0.20
#: The grammar's L2 ceiling: concepts that can carry an L2 rewrite at all (D-043, ruling 3).
CEILING_DEV, CEILING_TEST = 13, 12

#: The P7 query, excluded at item level (S4 A2), as S4 and S5 did.
EXCLUDED = S4_EXCLUDED
NO_P8 = "synonym_label, without P8"
S_SCOPES = TYPES + [NO_P8] + list(LAYERS) + ["all"]
W_SCOPES = L2_TYPES + ["L2w"]
VARIANTS = ("tf", "run", "clean")
VARIANT_LABEL = {"tf": "tie-free", "run": "as run", "clean": "tie-free, clean subset"}


# --------------------------------------------------------------------------- inputs


def parent_of() -> dict[str, str]:
    return {r["item_key"]: r["parent_key"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}


def tie_table(queryset: str, method: str, keep: set[str], parents: dict[str, str]) -> pd.DataFrame:
    """Tie-free item and parent hit of every query in `keep`, from its rank-1 tied set (A2 a)."""
    rows = []
    for r in iter_top100(queryset, method):
        key = str(r["query_item_key"])
        if key not in keep:
            continue
        c = r["candidates"]
        s1 = float(c[0]["score"])
        tied = [str(x["index_item_key"]) for x in c if float(x["score"]) == s1]
        gold, gpar = str(r["gold_item_key"]), str(r["gold_parent_key"])
        rows.append({"key": key,
                     "item_tf": (1.0 / len(tied)) if gold in tied else 0.0,
                     "parent_tf": sum(parents[t] == gpar for t in tied) / len(tied),
                     "truncated": len(tied) == len(c)})
    frame = pd.DataFrame(rows).set_index("key")
    missing = keep - set(frame.index)
    if missing:
        raise KeyError(f"{method}/{queryset}: {len(missing)} keys absent from the top-100 file")
    return frame


def query_features(queryset: str, dev_keys: set[str]) -> pd.DataFrame:
    """Arm-independent per-query covariates and flags, on dev queries only (text is read on dev only).

    The text comes from the query set named, so v1 and v2 can be featurised in one process (A8); the single
    sidecar is the same for both.
    """
    path = L2_JSON if queryset == L2W else DATA / f"OE_{queryset}.json"
    sidecar = load_sidecar(L2_SIDECAR if queryset == L2W else SINGLE_SIDECAR)
    corpus = {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}
    rows = []
    for r in json.loads(path.read_text(encoding="utf-8")):
        key = r["item_key"]
        if key not in dev_keys:
            continue
        q, g = r["text"], corpus[r["gold_item_key"]]
        num_cov = numeric_coverage(q, g)
        nq, ng = numbers_in(q), numbers_in(g)
        flags = text_flags(q, g)
        mods = sidecar[key]
        rows.append({
            "q": key,
            "d_tok": token_distance(q, g),
            "lex_def": 1.0 - lexical_coverage(q, g),
            "num_def": 0.0 if num_cov is None else 1.0 - num_cov,
            "nonum": float(nq == 0 and ng > 0),
            "dnum_def": float(ng - nq),
            "doubled": flags["doubled"],
            "topo": flags["topo"],
            "side_doubled": sidecar_doubling(q, mods),
            "side_topo": sidecar_topo(mods),
            "layer": mods[0]["layer"],
        })
    out = pd.DataFrame(rows).set_index("q")
    out["flagged"] = out["doubled"] | out["topo"]
    return out


def paired(short: str, queryset: str, dup: set[str], parents: dict[str, str], feats: pd.DataFrame) -> pd.DataFrame:
    """One row per dev query of `queryset`: modified and identity, as run and tie-free, both levels."""
    mod = perquery(queryset, DIR[short])
    ident = perquery("texto", DIR[short]).set_index("query_item_key")
    types = mod["modification_types"].map(lambda t: list(t))
    if (types.map(len) != 1).any():
        raise ValueError(f"{short}/{queryset}: a query carries other than one type")
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
        raise KeyError(f"{short}: {len(missing)} golds have no identity result")
    frame["item_id"] = frame["gold"].map(ident["item_acc1"]).astype(float)
    frame["parent_id"] = frame["gold"].map(ident["parent_acc1"]).astype(float)
    t_mod = tie_table(queryset, DIR[short], set(frame["q"]), parents)
    t_id = tie_table("texto", DIR[short], set(frame["gold"]), parents)
    frame["item_mod_tf"] = frame["q"].map(t_mod["item_tf"]).astype(float)
    frame["parent_mod_tf"] = frame["q"].map(t_mod["parent_tf"]).astype(float)
    frame["item_id_tf"] = frame["gold"].map(t_id["item_tf"]).astype(float)
    frame["parent_id_tf"] = frame["gold"].map(t_id["parent_tf"]).astype(float)
    frame["trunc_mod"] = frame["q"].map(t_mod["truncated"]).astype(bool)
    frame["trunc_id"] = frame["gold"].map(t_id["truncated"]).astype(bool)
    # The run's rank 1 lies inside its tied set: a hit as run has a positive tie-free value, and a
    # tie-free certainty (the gold's concept, or the gold, is the whole set) is a hit as run.
    for side in ("mod", "id"):
        for level in ("item", "parent"):
            run, tf = frame[f"{level}_{side}"], frame[f"{level}_{side}_tf"]
            if (((run == 1) & (tf == 0)) | ((run == 0) & (tf == 1))).any():
                raise ValueError(f"{short}/{queryset}/{level}_{side}: tie-free and as-run disagree on a certainty")
    frame["item_scored"] = ~frame["gold"].isin(dup) & ~frame["q"].map(
        lambda k: "item" in EXCLUDED.get(k, {}).get("levels", ()))
    frame["parent_scored"] = ~frame["q"].map(lambda k: "parent" in EXCLUDED.get(k, {}).get("levels", ()))
    frame["queryset"] = queryset
    frame = frame.join(feats, on="q")
    if frame["d_tok"].isna().any():
        raise ValueError(f"{short}/{queryset}: queries without features")
    return frame


def columns(frame: pd.DataFrame, variant: str) -> pd.DataFrame:
    """The frame with its hit columns chosen for a variant: tie-free, as run, or tie-free on the clean subset."""
    f = frame.copy()
    if variant in ("tf", "clean"):
        for side in ("mod", "id"):
            for level in ("item", "parent"):
                f[f"{level}_{side}"] = f[f"{level}_{side}_tf"]
    if variant == "clean":
        f = f[~f["flagged"]]
    return f


def scope(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    if name in ("all", "L2w"):
        return frame
    if name == NO_P8:
        return frame[(frame["type"] == "synonym_label") & ~frame["q"].isin(P8_DEV)]
    if name in LAYERS:
        return frame[frame["type"].isin(LAYERS[name])]
    return frame[frame["type"] == name]


def item(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["item_scored"]]


def parent(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["parent_scored"]]


# --------------------------------------------------------------------------- statistics


def cell(frame: pd.DataFrame, level: str, label: str) -> dict:
    """S4's cell, on whichever hit columns the frame carries (as run or tie-free)."""
    f = item(frame) if level == "item" else parent(frame)
    ident, mod = f[f"{level}_id"].to_numpy(float), f[f"{level}_mod"].to_numpy(float)
    d = mod - ident
    cols = np.column_stack([d, ident * mod, ident])
    q = boot_query(cols, f"s6|{label}|{level}")
    c = boot_cluster(cols, f["concept"].to_numpy(), f"s6|{label}|{level}")
    kept = ident.sum()
    with np.errstate(invalid="ignore", divide="ignore"):
        ret_c = c[:, 1] / c[:, 2]
    ret_c = ret_c[np.isfinite(ret_c)]
    return {
        "n_all": len(frame), "n": len(f), "excluded": len(frame) - len(f), "concepts": int(f["concept"].nunique()),
        "id": float(ident.mean()), "mod": float(mod.mean()), "delta": float(d.mean()),
        "q": ci(q[:, 0]), "c": ci(c[:, 0]), "se_c": float(c[:, 0].std(ddof=1)),
        "retention": float((ident * mod).sum() / kept) if kept else float("nan"),
        "ret_c": ci(ret_c) if len(ret_c) else (float("nan"), float("nan")),
        "down": int(((ident == 1) & (mod == 0)).sum()), "up": int(((ident == 0) & (mod == 1)).sum()),
    }


def mean_draws(f: pd.DataFrame, values: np.ndarray, label: str) -> tuple[float, np.ndarray]:
    return float(values.mean()), boot_cluster(values[:, None], f["concept"].to_numpy(), label)[:, 0]


def loss_share(f: pd.DataFrame, label: str) -> tuple[float, np.ndarray]:
    """Share of item losses whose modified rank 1 is in the wrong concept (A2 a: products of expectations)."""
    ident = f["item_id"].to_numpy(float)
    wrong = ident * (1.0 - f["parent_mod"].to_numpy(float))
    loss = ident * (1.0 - f["item_mod"].to_numpy(float))
    draws = boot_cluster(np.column_stack([wrong, loss]), f["concept"].to_numpy(), label)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = draws[:, 0] / draws[:, 1]
    return (float(wrong.sum() / loss.sum()) if loss.sum() else float("nan")), r


def discrimination(f: pd.DataFrame, label: str) -> tuple[float, np.ndarray]:
    """(D_id − D_mod) − (parent_id − parent_mod), D = Σ item ÷ Σ parent (A2 a)."""
    cols = np.column_stack([f["item_id"], f["parent_id"], f["item_mod"], f["parent_mod"]]).astype(float)

    def stat(m: np.ndarray) -> np.ndarray:
        with np.errstate(invalid="ignore", divide="ignore"):
            return (m[..., 0] / m[..., 1] - m[..., 2] / m[..., 3]) - (m[..., 1] - m[..., 3])

    draws = boot_cluster(cols, f["concept"].to_numpy(), label)
    return float(stat(cols.mean(axis=0))), stat(draws)


def sensitivity_draws(f: pd.DataFrame, label: str) -> tuple[float, np.ndarray, tuple, float]:
    """δ / mean d_tok on one pool: estimate, draws, the δ interval, and mean d_tok."""
    d = (f["item_mod"] - f["item_id"]).to_numpy(float)
    t = f["d_tok"].to_numpy(float)
    draws = boot_cluster(np.column_stack([d, t]), f["concept"].to_numpy(), label)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = draws[:, 0] / draws[:, 1]
    return float(d.mean() / t.mean()), r, ci(draws[:, 0]), float(t.mean())


def cluster_weights(concepts: np.ndarray, label: str) -> tuple[np.ndarray, np.ndarray]:
    """Sorted concept labels and a B × G multinomial weight matrix, as S2's `boot_cluster` draws them."""
    labels = np.unique(concepts)
    g = len(labels)
    return labels, _rng("cluster|" + label).multinomial(g, np.full(g, 1.0 / g), size=B).astype(float)


def ols_within(f: pd.DataFrame, xcols: list[str], label: str) -> dict:
    """δ ~ 0 + type + X by OLS, point and concept-clustered draws, via Frisch–Waugh within type.

    Every quantity the design reads is a function of per-(concept, type) sums, so a bootstrap draw
    re-weights those sums instead of refitting. Returns γ (the covariates' coefficients), the per-type
    means (M0's β), the per-type residual effects (M1's or M2's β), the pool mean δ and PM.
    """
    y = (f["item_mod"] - f["item_id"]).to_numpy(float)
    X = f[xcols].to_numpy(float)
    types = sorted(f["type"].unique())
    labels, W = cluster_weights(f["concept"].to_numpy(), label)
    gi = np.searchsorted(labels, f["concept"].to_numpy())
    ti = np.searchsorted(np.array(types), f["type"].to_numpy())
    G, T, k = len(labels), len(types), X.shape[1]
    n = np.zeros((G, T))
    sy = np.zeros((G, T))
    sx = np.zeros((G, T, k))
    sxx = np.zeros((G, T, k, k))
    sxy = np.zeros((G, T, k))
    np.add.at(n, (gi, ti), 1.0)
    np.add.at(sy, (gi, ti), y)
    np.add.at(sx, (gi, ti), X)
    np.add.at(sxx, (gi, ti), X[:, :, None] * X[:, None, :])
    np.add.at(sxy, (gi, ti), X * y[:, None])

    def solve(w: np.ndarray) -> dict:
        """w: (m, G). Aggregate, demean within type, solve for γ."""
        N = w @ n                                   # (m, T)
        Y = w @ sy
        SX = np.einsum("mg,gtk->mtk", w, sx)
        SXX = np.einsum("mg,gtkl->mtkl", w, sxx)
        SXY = np.einsum("mg,gtk->mtk", w, sxy)
        with np.errstate(invalid="ignore", divide="ignore"):
            inv = np.where(N > 0, 1.0 / N, 0.0)
        Sxx = (SXX - SX[..., :, None] * SX[..., None, :] * inv[..., None, None]).sum(axis=1)
        Sxy = (SXY - SX * (Y * inv)[..., None]).sum(axis=1)
        gamma = np.einsum("mkl,ml->mk", np.linalg.pinv(Sxx), Sxy)
        with np.errstate(invalid="ignore", divide="ignore"):
            beta0 = np.where(N > 0, Y * inv, np.nan)
            beta1 = np.where(N > 0, (Y - np.einsum("mtk,mk->mt", SX, gamma)) * inv, np.nan)
            total = N.sum(axis=1)
            mean_d = Y.sum(axis=1) / total
            explained = np.einsum("mk,mk->m", gamma, SX.sum(axis=1)) / total
            pm = explained / mean_d
        return {"gamma": gamma, "beta0": beta0, "beta1": beta1, "mean_d": mean_d, "pm": pm}

    point = {k_: v[0] for k_, v in solve(np.ones((1, G))).items()}
    draws = solve(W)
    return {"types": types, "xcols": xcols, "n": len(f), "concepts": G, "point": point, "draws": draws,
            # The concepts behind the weights: two fits under the same label with equal keys have paired draws (A8).
            "clusters_key": tuple(labels.tolist())}


def fit_mixed(f: pd.DataFrame, xcols: list[str]) -> dict:
    """M0/M1/M2 as a linear mixed model: concept groups, leaf as a variance component (design, A2 h)."""
    import statsmodels.formula.api as smf

    data = f.assign(delta=(f["item_mod"] - f["item_id"]).astype(float)).reset_index(drop=True)
    rhs = " + ".join(["0 + C(type)", *xcols])
    for with_leaf in (True, False):
        kwargs = {"groups": "concept", "re_formula": "1"}
        if with_leaf:
            kwargs["vc_formula"] = {"leaf": "0 + C(gold)"}
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = smf.mixedlm(f"delta ~ {rhs}", data, **kwargs).fit(reml=True)
        except Exception as err:  # noqa: BLE001 — a failed fit is reported, never dropped (A2 h)
            if with_leaf:
                continue
            return {"ok": False, "why": type(err).__name__, "leaf": False}
        if res.converged or not with_leaf:
            conf = res.conf_int()
            fe = res.fe_params
            names = {c: c.replace("C(type)[", "").replace("]", "") for c in fe.index}
            vc = {"concept": float(res.cov_re.iloc[0, 0]), "residual": float(res.scale)}
            if with_leaf:
                vc["leaf"] = float(res.vcomp[0]) if len(res.vcomp) else float("nan")
            blup = {g: float(v.iloc[0]) for g, v in res.random_effects.items()}
            u = data["concept"].map(blup)
            return {"ok": True, "leaf": with_leaf, "converged": bool(res.converged),
                    "u_by_type": {t: float(u[data["type"] == t].mean()) for t in data["type"].unique()},
                    "fe": {names[c]: float(fe[c]) for c in fe.index},
                    "ci": {names[c]: (float(conf.loc[c, 0]), float(conf.loc[c, 1])) for c in fe.index},
                    "vc": vc, "n": int(res.nobs)}
    return {"ok": False, "why": "no fit", "leaf": False}


def mixed_pm(m0: dict, m1: dict, f: pd.DataFrame) -> float:
    if not (m0.get("ok") and m1.get("ok") and m0.get("converged") and m1.get("converged")):
        return float("nan")
    w = f["type"].value_counts(normalize=True)
    s0 = sum(w[t] * m0["fe"][t] for t in w.index)
    s1 = sum(w[t] * m1["fe"][t] for t in w.index)
    return 1.0 - s1 / s0


def test_p(draws: np.ndarray, null: float = 0.0) -> float:
    d = draws[np.isfinite(draws)]
    return boot_p(d - null) if len(d) else 1.0


def read(r: dict) -> str:
    """S4's rule, against the test's null (0, or the threshold of R3 / R5)."""
    if r.get("forced"):
        return "not supported"
    lo, hi = r["c"]
    null = r.get("null", 0.0)
    good, bad = (lo > null, hi < null) if r["side"] == "positive" else (hi < null, lo > null)
    if good and r["holm"] < ALPHA:
        return "supported"
    if bad and r["holm"] < ALPHA:
        return "contradicted"
    return "not supported"


# --------------------------------------------------------------------------- the registered tests


TESTS = [
    # id, hypothesis, what, kind, arms, blind
    ("R1", "H2 L1 vs L2", "L1 item δ (S4 population) < L2w item δ", "r1", ["bm25_unigram", "bm25_unigram_params"], True),
    ("R2", "H2 L2 concept-level", "share of item losses in the wrong concept: L2w above L1", "r2",
     ["bm25_unigram", "bge_m3_colbert"], True),
    ("R3", "H5 lexical", "proportion mediated by overlap above the threshold", "r3",
     ["bm25_unigram", "bm25_unigram_params"], True),
    ("R4", "H5 lexical vs dense", "PM(`bm25_unigram`) − PM(arm) > 0", "r4", ["bge_m3_colbert", "bge_m3_dense"], True),
    ("R5", "H5 normalised sensitivity", "(δ / d̄_tok) L1 ÷ L3 above the threshold", "r5",
     ["bm25_unigram", "bm25_unigram_params"], False),
    ("R6a", "H1 gap widens", "Δ_mod − Δ_id > 0, all nine types", "r6a",
     ["tfidf_phrases_replace", "bge_m3_dense", "dense_e5", "dense_es_hiiamsid"], False),
    ("R6b", "H1 discrimination", "(D_id − D_mod) − (parent_id − parent_mod) > 0", "r6b", BASE7, False),
]


def unitize(f: pd.DataFrame, unit: str) -> pd.DataFrame:
    """Resample by concept (the reading) or by query (the query-level interval, A4): the query as its own cluster."""
    return f if unit == "concept" else f.assign(concept=f["q"])


def run_test(kind: str, short: str, S: dict, W: dict, variant: str, unit: str = "concept") -> dict:
    s, w = unitize(columns(S[short], variant), unit), unitize(columns(W[short], variant), unit)
    lab = f"s6|{kind}|{short}|{variant}" + ("" if unit == "concept" else "|q")
    if kind == "r1":
        a, da = mean_draws(item(scope(s, "L1")), delta(item(scope(s, "L1"))), lab + "|L1")
        b, db = mean_draws(item(w), delta(item(w)), lab + "|L2w")
        return {"est": a - b, "draws": da - db, "side": "negative",
                "clusters": {"L1": nconc(item(scope(s, "L1"))), "L2w": nconc(item(w))},
                "counts": {"L1": scope(s, "L1"), "L2w": w}}
    if kind == "r2":
        a, da = loss_share(item(w), lab + "|L2w")
        b, db = loss_share(item(scope(s, "L1")), lab + "|L1")
        return {"est": a - b, "draws": da - db, "side": "positive",
                "clusters": {"L2w": nconc(item(w)), "L1": nconc(item(scope(s, "L1")))},
                "counts": {"L2w": w, "L1": scope(s, "L1")}}
    if kind in ("r3", "r4"):
        own = pm_fit(s, short, variant, unit=unit)
        if kind == "r3":
            forced = interval_contains_zero(own["draws"]["mean_d"])
            return {"est": own["point"]["pm"], "draws": own["draws"]["pm"], "side": "positive", "null": PM_NULL,
                    "forced": forced, "clusters": {"all": own["concepts"]}, "counts": {"all": s}}
        ref = pm_fit(unitize(columns(S["bm25_unigram"], variant), unit), "bm25_unigram", variant, unit=unit)
        forced = interval_contains_zero(own["draws"]["mean_d"]) or interval_contains_zero(ref["draws"]["mean_d"])
        return {"est": ref["point"]["pm"] - own["point"]["pm"], "draws": ref["draws"]["pm"] - own["draws"]["pm"],
                "side": "positive", "forced": forced, "clusters": {"all": own["concepts"]}, "counts": {"all": s}}
    if kind == "r5":
        a, da, _, _ = sensitivity_draws(item(scope(s, "L1")), lab + "|L1")
        b, db, l3_ci, _ = sensitivity_draws(item(scope(s, "L3")), lab + "|L3")
        with np.errstate(invalid="ignore", divide="ignore"):
            draws = da / db
        forced = l3_ci[0] <= 0.0 <= l3_ci[1]
        return {"est": a / b, "draws": draws, "side": "positive", "null": RATIO_NULL, "forced": forced,
                "clusters": {"L1": nconc(item(scope(s, "L1"))), "L3": nconc(item(scope(s, "L3")))},
                "counts": {"L1": scope(s, "L1"), "L3": scope(s, "L3")}}
    if kind == "r6a":
        f = item(s)
        v = ((f["parent_mod"] - f["item_mod"]) - (f["parent_id"] - f["item_id"])).to_numpy(float)
        est, draws = mean_draws(f, v, lab)
        return {"est": est, "draws": draws, "side": "positive", "clusters": {"all": nconc(f)}, "counts": {"all": s}}
    if kind == "r6b":
        est, draws = discrimination(item(s), lab)
        return {"est": est, "draws": draws, "side": "positive", "clusters": {"all": nconc(item(s))},
                "counts": {"all": s}}
    raise ValueError(kind)


def delta(f: pd.DataFrame) -> np.ndarray:
    return (f["item_mod"] - f["item_id"]).to_numpy(float)


def nconc(f: pd.DataFrame) -> int:
    return int(f["concept"].nunique())


def nexcl(f: pd.DataFrame) -> int:
    """Queries of a pool not scored at item level: D-033 golds and the P7 query (criterion 3, audit F1)."""
    return int((~f["item_scored"]).sum())


def interval_contains_zero(draws: np.ndarray) -> bool:
    lo, hi = ci(draws[np.isfinite(draws)])
    return lo <= 0.0 <= hi


_PM_CACHE: dict = {}


def pm_fit(frame: pd.DataFrame, short: str, variant: str, tag: str = "all", unit: str = "concept") -> dict:
    """M1 by OLS on the item-scored pool; one label per (variant, tag), so arms share concept weights (A2 e)."""
    key = (short, variant, tag, unit)
    if key not in _PM_CACHE:
        _PM_CACHE[key] = ols_within(item(frame), DEFICITS,
                                    f"s6|pm|{variant}|{tag}" + ("" if unit == "concept" else "|q"))
    return _PM_CACHE[key]


def evaluate(S: dict, W: dict) -> tuple[list[dict], dict]:
    results = []
    for tid, hyp, what, kind, arms, blind in TESTS:
        for short in arms:
            row = {"id": tid, "hyp": hyp, "what": what, "arm": short, "blind": blind}
            for v in VARIANTS:
                r = run_test(kind, short, S, W, v)
                d = r["draws"][np.isfinite(r["draws"])]
                row[v] = {"est": r["est"], "c": ci(d), "side": r["side"], "null": r.get("null", 0.0),
                          "forced": r.get("forced", False), "clusters": r["clusters"], "dropped": len(r["draws"]) - len(d),
                          "counts": {p: (len(item(f)), nexcl(f)) for p, f in r["counts"].items()},
                          "p": 1.0 if r.get("forced") else test_p(r["draws"], r.get("null", 0.0)),
                          # The unfiltered draws and the concepts behind each pool, so that two evaluations under
                          # the same label pair draw by draw (A8, `v2_variant.paired_diff`).
                          "draws": r["draws"],
                          "clusters_key": tuple(tuple(sorted(set(item(f)["concept"]))) for f in r["counts"].values())}
                rq = run_test(kind, short, S, W, v, unit="query")["draws"]
                row[v]["q"] = ci(rq[np.isfinite(rq)])
            results.append(row)
    for v in VARIANTS:
        ps = [r[v]["p"] for r in results]
        for r, h, q in zip(results, holm(ps), bh(ps)):
            r[v].update(holm=h, bh=q)
            r[v]["reading"] = read(r[v])
    reopen = [r for r in results if r["id"] in ("R1", "R2") and r["tf"]["reading"] == "not supported"
              and r["tf"]["c"][1] - r["tf"]["c"][0] > WIDE_L2]
    return results, {"reopen": reopen}


def s4_rereads(S: dict) -> list[dict]:
    """S4's P1–P5 re-read tie-free (D-028 note): reference, not registered, S4's rule and Holm family."""
    from utils.build_results_s4 import PREDICTIONS

    out = []
    for pid, hyp, what, kind, arms in PREDICTIONS:
        for short in arms:
            f = columns(S[short], "tf")
            if kind == "l2_concept":
                a, da = loss_share(item(scope(f, "L2")), f"s6|p5|{short}|L2")
                b, db = loss_share(item(scope(f, "L1")), f"s6|p5|{short}|L1")
                d = (da - db)[np.isfinite(da - db)]
                r = {"est": a - b, "c": ci(d), "p": boot_p(d), "side": "positive"}
            else:
                r = _evaluate_prediction(kind, short, item_view(f))
            out.append({"id": pid, "hyp": hyp, "what": what, "arm": short, **r})
    ps = [r["p"] for r in out]
    for r, h, q in zip(out, holm(ps), bh(ps)):
        r.update(holm=h, bh=q)
        r["reading"] = s4_reading(r)
    return out


def item_view(f: pd.DataFrame) -> pd.DataFrame:
    """S4's prediction code reads `item_scored` / `parent_scored`; the frame already carries both."""
    return f


# --------------------------------------------------------------------------- tables


def name(short: str) -> str:
    return f"`{short}`" + (" **oracle**" if short in ORACLE else "")


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S6 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def ccount(clusters: dict) -> str:
    return " / ".join(f"{p} {n}" + (" ‡" if n < FEW_CLUSTERS else "") for p, n in clusters.items())


def ncount(counts: dict) -> str:
    """Per pool: item-scored queries and those excluded (D-033 golds, the P7 query)."""
    return " / ".join(f"{p} {n:,} ({x:,})" for p, (n, x) in counts.items())


def population_lines(S: dict, W: dict, dup: set[str]) -> list[str]:
    s, w = next(iter(S.values())), next(iter(W.values()))
    return [
        f"**Populations.** `{SINGLE}` (S4's): {len(s):,} dev queries over {nconc(s)} concepts; item level scores "
        f"{int(s['item_scored'].sum()):,} ({int(s['gold'].isin(dup).sum()):,} D-033 golds, "
        f"{sum('item' in e['levels'] for e in EXCLUDED.values())} P7 query excluded). **L2w** = `{L2W}`: "
        f"{len(w):,} dev queries over {nconc(w)} concepts; item level scores {int(w['item_scored'].sum()):,} "
        f"({int(w['gold'].isin(dup).sum()):,} D-033 golds). Layers reach different leaves: every layer contrast is "
        "between-population. L2 breadth under the frozen menus: "
        + " / ".join(f"`{t}` {nconc(scope(w, t))}" for t in L2_TYPES)
        + f" dev concepts, against a grammar ceiling of {CEILING_DEV} dev / {CEILING_TEST} test (D-043).",
        "",
    ]


def write_l2_profile(stats: dict, trunc: dict, S: dict, W: dict, dup: set[str]) -> None:
    lines = header("T1: the L2 profile on `single_l2_texto` (L2w), item and parent level (dev)", [
        "S4's columns, for the fifteen arms. Each query is paired with the same arm's `texto` result on its",
        f"own gold. **L2w** is the registered L2 population (blind). **L2s** is S4's L2 pool on `{SINGLE}`",
        "and **L2∪** the union of both: printed for reference, never read (design).",
    ])
    lines += population_lines(S, W, dup)
    lines += ["Tie-free (A2 a): a query's rank-1 tied set, read from its top-100, broken uniformly; identity and "
              "modified independently. As-run columns are S4's; the tie-free ones are what S6 reads.", ""]
    for level in ("item", "parent"):
        lines += [f"## {level.capitalize()} level", ""]
        for short in stats:
            lines += [f"### {name(short)}", "",
                      "| scope | n | n scored | n excluded | concepts | identity | modified | δ | CI (query) | CI (concept) | "
                      "retention | CI (concept) | lost | gained | identity, tie-free | modified, tie-free | δ, tie-free | "
                      "CI (query), tie-free | CI (concept), tie-free |",
                      "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|---:|---:|---:|---|---|"]
            for sc in W_SCOPES + ["L2s", "L2∪"]:
                c, t = stats[short][(sc, level, "run")], stats[short][(sc, level, "tf")]
                mark = "" if sc in W_SCOPES else " (reference)"
                lines.append(
                    f"| {sc}{mark} | {c['n_all']:,} | {c['n']:,} | {c['excluded']:,} | {c['concepts']}"
                    + (" ‡" if c["concepts"] < FEW_CLUSTERS else "")
                    + f" | {f4(c['id'])} | {f4(c['mod'])} | {fd(c['delta'])} | {fci(c['q'], True)} | "
                    f"{fci(c['c'], True)} | {f4(c['retention'])} | {fci(c['ret_c'])} | {c['down']:,} | {c['up']:,} | "
                    f"{f4(t['id'])} | {f4(t['mod'])} | {fd(t['delta'])} | {fci(t['q'], True)} | {fci(t['c'], True)} |")
            lines.append("")
    lines += ["## Rank-1 tied sets that fill the whole top-100 (A2 a)", "",
              "The tied set is read from the top-100, so a set this large is truncated and its tie-free value is an "
              "upper bound. Counted over every query each arm's S6 readings use.", "",
              f"| arm | `{SINGLE}` modified | L2w modified | identity (golds of both) |", "|---|---:|---:|---:|"]
    for short, (a, b, c) in trunc.items():
        lines.append(f"| {name(short)} | {a:,} | {b:,} | {c:,} |")
    lines += sources_block([SINGLE, L2W, "texto"])
    write(OUT / "l2_profile.md", lines)


def write_adjusted(models: dict, raw: dict, S: dict) -> None:
    lines = header("T2: the adjusted profile, M0 (dev, item level)", [
        "M0: δ ~ 0 + type + (1 | concept) + (1 | leaf ∈ concept), a linear mixed model on the tie-free δ of",
        f"`{SINGLE}`'s item-scored queries, REML. δ is a within-leaf difference, so the leaf's own difficulty",
        "is already differenced out; the random intercepts absorb what concept and leaf share across renderings.",
        "Coefficients are in Acc@1 units, beside the raw mean δ (S4's, as run, and tie-free).",
    ])
    lines += ["**û** is the mean of the fitted concept intercepts over the type's queries. M0's β is the effect at an "
              "*average concept*; raw δ ≈ β + û (plus the leaf part). A large |û| means the concepts that admit the "
              "type differ in difficulty from the average concept, and an additive intercept can only carry that "
              "by moving β: where a type's raw δ is exactly 0 on every query (for instance `reorder` for a "
              "bag-of-words arm) and β is not, the additive concept intercept is what does not hold for that arm.", ""]
    lines += ["The model-based intervals are approximate (a linear probability model on δ ∈ [−1, 1]) and are "
              "printed for description: **no reading rests on them** (design). A fit that fails or does not converge "
              "with the leaf component is refitted without it and marked (A2 h).", ""]
    for short in BASE7:
        for tag in ("all", "no_p8"):
            m = models[short][("M0", tag)]
            title = name(short) + ("" if tag == "all" else ", without the P8 queries (D-044)")
            lines += [f"## {title}", ""]
            if not m.get("ok"):
                lines += [f"Fit failed: {m.get('why')}.", ""]
                continue
            lines += [f"n = {m['n']:,}; leaf component: {'yes' if m['leaf'] else '**no** (refitted without)'}; "
                      f"converged: {'yes' if m['converged'] else '**no**'}. Variance: concept {m['vc']['concept']:.6f}"
                      + (f", leaf {m['vc']['leaf']:.6f}" if 'leaf' in m['vc'] else "")
                      + f", residual {m['vc']['residual']:.6f}.", "",
                      "| type | n scored | n excluded | concepts | raw δ, as run | raw δ, tie-free | CI (query) | "
                      "CI (concept) | M0 β | CI (model) | û | β + û |",
                      "|---|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|"]
            for t in TYPES:
                if t not in m["fe"]:
                    continue
                r = raw[(short, tag, t)]
                u = m["u_by_type"].get(t, float("nan"))
                lines.append(f"| {t} | {r['n']:,} | {r['excluded']:,} | {r['concepts']} | {fd(r['run'])} | {fd(r['tf'])} | "
                             f"{fci(r['q'], True)} | {fci(r['c'], True)} | {fd(m['fe'][t])} | "
                             f"{fci(m['ci'][t], True)} | {fd(u)} | {fd(m['fe'][t] + u)} |")
            lines.append("")
    lines += sources_block([SINGLE, "texto"], only=BASE7)
    write(OUT / "adjusted.md", lines)


def write_mediation(models: dict, pms: dict, S: dict, corr: pd.DataFrame, feats_n: int) -> None:
    lines = header("T3: mediation by overlap, M1 and M2 (dev, item level)", [
        "M1 adds to M0 the overlap deficits, each zero at identity: " + "; ".join(DEFICIT_LABEL[c] for c in DEFICITS)
        + " (A2 b). M2 adds d_tok instead. The **residual** β_t is type t's effect at zero overlap loss.",
        "**PM** = 1 − Σ_t w_t β_t(M1) ÷ Σ_t w_t β_t(M0), w_t the type's share of the item-scored queries.",
    ])
    lines += ["**This is a decomposition, not a causal estimate.** The type fixes the rewrite and the rewrite fixes "
              "the overlap; nothing is randomised between them, so *mediated* means *attenuated by conditioning*, "
              "and sequential ignorability is not claimed (design).", "",
              f"Registered intervals come from the fixed-effects OLS, resampled by concept (B = {B:,}); the mixed "
              "model's PM is its adjusted point estimate, printed beside. PM is printed \"—\" when the pool's mean δ "
              "has a concept-clustered interval containing 0 (A2 d).", "",
              "The mixed PM weights *average-concept* effects (T2's β) by query shares, so it is not on the OLS PM's "
              "scale and is not a check of it; it is printed \"—\" when either fit did not converge. T2's û column "
              "shows how far the two scales are apart, type by type.", ""]
    lines += ["## Covariates", "", f"Correlations over the {feats_n:,} item-scored `{SINGLE}` dev queries "
              "(arm-independent). Deficits are collinear with type by construction (L1 rewrites exactly the numbers): "
              "no claim rests on one deficit's coefficient (design, Risks).", "",
              "| | " + " | ".join(DEFICIT_LABEL[c] for c in corr.columns) + " |", "|---|" + "---:|" * len(corr.columns)]
    for r in corr.index:
        lines.append(f"| {DEFICIT_LABEL[r]} | " + " | ".join(fd(corr.loc[r, c]) for c in corr.columns) + " |")
    lines.append("")
    lines += ["## Proportion mediated", "",
              "| arm | pool | n scored | n excluded | concepts | mean δ, tie-free | CI (query) | CI (concept) | PM (OLS) | "
              "CI (query) | CI (concept) | PM (mixed) | PM (OLS), without P8 | PM (OLS), as run |",
              "|---|---|---:|---:|---:|---:|---|---|---:|---|---|---:|---:|---:|"]
    for short in BASE7:
        p = pms[(short, "tf", "all")]
        und = interval_contains_zero(p["draws"]["mean_d"])
        pm = "—" if und else fd(p["point"]["pm"])
        pmci = "—" if und else fci(ci(p["draws"]["pm"][np.isfinite(p["draws"]["pm"])]), True)
        pq = pms[(short, "tf", "all_q")]
        pmq = "—" if und else fci(ci(pq["draws"]["pm"][np.isfinite(pq["draws"]["pm"])]), True)
        mixed = mixed_pm(models[short][("M0", "all")], models[short][("M1", "all")], item(columns(S[short], "tf")))
        nop8 = pms[(short, "tf", "no_p8")]["point"]["pm"]
        run = pms[(short, "run", "all")]["point"]["pm"]
        lines.append(f"| {name(short)} | all | {p['n']:,} | {nexcl(S[short]):,} | {p['concepts']} | {fd(p['point']['mean_d'])} | "
                     f"{fci(ci(pq['draws']['mean_d']), True)} | {fci(ci(p['draws']['mean_d']), True)} | {pm} | {pmq} | "
                     f"{pmci} | {fd(mixed) if np.isfinite(mixed) else '—'} | "
                     f"{fd(nop8)} | {fd(run)} |")
    lines.append("")
    for short in BASE7:
        p1, p2 = pms[(short, "tf", "all")], pms[(short, "tf", "m2")]
        m1, m2 = models[short][("M1", "all")], models[short][("M2", "all")]
        lines += [f"## {name(short)}", "",
                  "| term | M0 β (OLS) | CI (concept) | M1 β (OLS) | CI (concept) | M1 β (mixed) | CI (model) | "
                  "M2 β (OLS) | CI (concept) | M2 β (mixed) |",
                  "|---|---:|---|---:|---|---:|---|---:|---|---:|"]
        for j, t in enumerate(p1["types"]):
            b0 = p1["draws"]["beta0"][:, j]
            b1 = p1["draws"]["beta1"][:, j]
            b2 = p2["draws"]["beta1"][:, j]
            lines.append(
                f"| {t} | {fd(p1['point']['beta0'][j])} | {fci(ci(b0[np.isfinite(b0)]), True)} | "
                f"{fd(p1['point']['beta1'][j])} | {fci(ci(b1[np.isfinite(b1)]), True)} | "
                f"{mixed_cell(m1, t)} | {mixed_ci(m1, t)} | {fd(p2['point']['beta1'][j])} | "
                f"{fci(ci(b2[np.isfinite(b2)]), True)} | {mixed_cell(m2, t)} |")
        for j, x in enumerate(DEFICITS):
            g = p1["draws"]["gamma"][:, j]
            lines.append(f"| {DEFICIT_LABEL[x]} | | | {fd(p1['point']['gamma'][j])} | {fci(ci(g), True)} | "
                         f"{mixed_cell(m1, x)} | {mixed_ci(m1, x)} | | | |")
        g = p2["draws"]["gamma"][:, 0]
        lines.append(f"| d_tok | | | | | | | {fd(p2['point']['gamma'][0])} | {fci(ci(g), True)} | {mixed_cell(m2, 'd_tok')} |")
        lines.append("")
        for tag, m in (("M1", m1), ("M2", m2)):
            if m.get("ok"):
                lines.append(f"{tag} mixed: n = {m['n']:,}, leaf component {'yes' if m['leaf'] else '**no**'}, "
                             f"converged {'yes' if m['converged'] else '**no**'}.")
            else:
                lines.append(f"{tag} mixed: fit failed ({m.get('why')}).")
        lines.append("")
    lines += ["## `synonym_label` with and without the P8 queries, and the fits without them (D-044, A2 g)", "",
              "Every model is fitted twice, with and without the four case-only `synonym_label` queries. The "
              "`synonym_label` term both ways; every other term moves only through the shared covariate "
              "coefficients.", "",
              "| arm | fit | M0 β (OLS) | M1 β (OLS) | CI (concept) | M1 β (mixed) | M2 β (OLS) | CI (concept) | M2 β (mixed) | PM (OLS) |",
              "|---|---|---:|---:|---|---:|---:|---|---:|---:|"]
    for short in BASE7:
        for tag, k1, k2 in (("all", "all", "m2"), ("no_p8", "no_p8", "m2_no_p8")):
            p1, p2 = pms[(short, "tf", k1)], pms[(short, "tf", k2)]
            j1, j2 = p1["types"].index("synonym_label"), p2["types"].index("synonym_label")
            b1, b2 = p1["draws"]["beta1"][:, j1], p2["draws"]["beta1"][:, j2]
            m1, m2 = models[short][("M1", tag)], models[short][("M2", tag)]
            lines.append(
                f"| {name(short)} | {'with P8' if tag == 'all' else 'without P8'} | {fd(p1['point']['beta0'][j1])} | "
                f"{fd(p1['point']['beta1'][j1])} | {fci(ci(b1[np.isfinite(b1)]), True)} | {mixed_cell(m1, 'synonym_label')} | "
                f"{fd(p2['point']['beta1'][j2])} | {fci(ci(b2[np.isfinite(b2)]), True)} | {mixed_cell(m2, 'synonym_label')} | "
                f"{fd(p1['point']['pm'])} |")
    lines += ["", "Status of every mixed fit without the P8 queries (M0's is also in T2):", ""]
    for short in BASE7:
        parts = []
        for mname in ("M0", "M1", "M2"):
            m = models[short][(mname, "no_p8")]
            parts.append(f"{mname} " + (f"leaf {'yes' if m['leaf'] else '**no**'}, converged "
                                        f"{'yes' if m['converged'] else '**no**'}" if m.get("ok") else f"failed ({m.get('why')})"))
        lines.append(f"- {name(short)}: " + "; ".join(parts) + ".")
    lines.append("")
    lines += ["## `template_paraphrase` inside L3 (descriptive)", "",
              "H2's L3 clause is read per type (S4 finding 4). If `template_paraphrase`'s M1 residual has an interval "
              "containing 0 for a lexical arm, its cost to that arm is overlap, not order (design; descriptive).", "",
              "| arm | M0 β | M1 residual | CI (concept) | interval contains 0 |", "|---|---:|---:|---|---|"]
    for short in ("bm25_unigram", "bm25_unigram_params", "tfidf_phrases_replace"):
        p1 = pms[(short, "tf", "all")]
        j = p1["types"].index("template_paraphrase")
        b1 = p1["draws"]["beta1"][:, j]
        lo, hi = ci(b1[np.isfinite(b1)])
        lines.append(f"| {name(short)} | {fd(p1['point']['beta0'][j])} | {fd(p1['point']['beta1'][j])} | "
                     f"{fci((lo, hi), True)} | {'yes' if lo <= 0 <= hi else 'no'} |")
    lines += sources_block([SINGLE, "texto"], only=BASE7, inputs=(SINGLE_JSON, CORPUS_JSON))
    write(OUT / "mediation.md", lines)


def mixed_cell(m: dict, term: str) -> str:
    return fd(m["fe"][term]) if m.get("ok") and term in m["fe"] else "—"


def mixed_ci(m: dict, term: str) -> str:
    return fci(m["ci"][term], True) if m.get("ok") and term in m["ci"] else "—"


def write_sensitivity(S: dict, W: dict) -> dict:
    lines = header("T4: normalised sensitivity δ / mean d_tok, per layer pool (dev, item level, tie-free)", [
        "δ is the pool's mean tie-free item δ, d_tok S4's (1 − Jaccard of distinct normalised tokens against the",
        "gold `texto`). Each pool is bootstrapped by concept on its own; pools reach different leaves, so the",
        f"L1 : L3 ratio is between-population. R5 reads it against {RATIO_NULL:g} (\"an order of magnitude\").",
    ])
    lines += ["| arm | pool | n scored | n excluded | concepts | mean δ | CI (query) | CI (concept) | mean d_tok | "
              "δ / d_tok | CI (query) | CI (concept) |",
              "|---|---|---:|---:|---:|---:|---|---|---:|---:|---|---|"]
    ratios = {}
    for short in BASE7:
        s, w = columns(S[short], "tf"), columns(W[short], "tf")
        pools = [("L1", scope(s, "L1")), ("L2s", scope(s, "L2")), ("L2w", w), ("L3", scope(s, "L3")), ("all", s)]
        for label, whole in pools:
            f = item(whole)
            est, draws, dci, tbar = sensitivity_draws(f, f"s6|sens|{short}|{label}")
            _, qdraws, qdci, _ = sensitivity_draws(unitize(f, "query"), f"s6|sens|{short}|{label}|q")
            lines.append(f"| {name(short)} | {label} | {len(f):,} | {nexcl(whole):,} | {nconc(f)}"
                         + (" ‡" if nconc(f) < FEW_CLUSTERS else "")
                         + f" | {fd(delta(f).mean())} | {fci(qdci, True)} | {fci(dci, True)} | {f4(tbar)} | {fd(est)} | "
                         f"{fci(ci(qdraws[np.isfinite(qdraws)]), True)} | {fci(ci(draws[np.isfinite(draws)]), True)} |")
    lines += sources_block([SINGLE, L2W, "texto"], only=BASE7, inputs=(SINGLE_JSON, L2_JSON, CORPUS_JSON))
    write(OUT / "sensitivity.md", lines)
    return ratios


def write_d004(feats: dict, results: list[dict]) -> None:
    lines = header("T5: the D-004 sensitivity (dev)", [
        "Flagged = an immediately doubled token, or the *topografía* drift, detected from the text (S3's detector,",
        "primary). The sidecar is the cross-check (`pantry_flags.py`): it decides L1 and L2 rewrites and cannot",
        "decide an L3 template rewrite, which it returns as undecidable, not clean. Every registered test is",
        "recomputed with the flagged queries dropped from both sides of every contrast they enter.",
    ])
    lines += ["## Flags per type", "",
              "| query set | type | n | doubled (detector) | doubled (sidecar) | undecidable (sidecar) | disagree | "
              "topo (detector) | topo (sidecar) | flagged |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for qs, f in feats.items():
        for t in sorted(f["type"].unique(), key=lambda x: (TYPES + L2_TYPES).index(x)):
            s = f[f["type"] == t]
            dec = s[s["side_doubled"].notna()]
            lines.append(
                f"| `{qs}` | {t} | {len(s):,} | {int(s['doubled'].sum())} | {int((s['side_doubled'] == True).sum())} | "  # noqa: E712
                f"{int(s['side_doubled'].isna().sum())} | {int((dec['side_doubled'].astype(bool) != dec['doubled']).sum())} | "
                f"{int(s['topo'].sum())} | {int(s['side_topo'].sum())} | {int(s['flagged'].sum())} |")
    lines += ["", "## Registered tests on the clean subset", "",
              "A reading that changes category between the full population and the clean subset is **not robust**; "
              "the full-population reading stands (D-004 keeps the artefacts in).", "",
              "| test | arm | reading, full | n scored (excluded), clean | estimate, clean | CI (query), clean | "
              "CI (concept), clean | Holm p, clean | reading, clean | robust |",
              "|---|---|---|---|---:|---|---|---:|---|---|"]
    for r in results:
        a, c = r["tf"], r["clean"]
        lines.append(f"| {r['id']} | {name(r['arm'])} | {a['reading']} | {ncount(c['counts'])} | {fd(c['est'])} | "
                     f"{fci(c['q'], True)} | "
                     f"{fci(c['c'], True)} | "
                     f"{fp(c['holm'])} | {c['reading']} | {'yes' if a['reading'] == c['reading'] else '**not robust**'} |")
    lines += sources_block([SINGLE, L2W], only=BASE7, inputs=(SINGLE_JSON, L2_JSON, SINGLE_SIDECAR, L2_SIDECAR))
    write(OUT / "d004.md", lines)


def write_power(S: dict, W: dict) -> None:
    z = NormalDist().inv_cdf(1 - ALPHA / 2) + NormalDist().inv_cdf(POWER)
    lines = header("T6: power note (dev, item level, tie-free)", [
        f"The smallest |δ| detectable at power {POWER:.0%}, two-sided α {ALPHA}, from the concept-clustered",
        f"standard error: MDE = (z(1 − α/2) + z(power)) × SE = {z:.4f} × SE. **No per-type claim is made on a cell",
        "whose MDE exceeds its observed |δ|** (design).",
    ])
    lines += ["| arm | scope | n scored | n excluded | concepts | δ | CI (query) | CI (concept) | SE (concept) | MDE | "
              "claim allowed |",
              "|---|---|---:|---:|---:|---:|---|---|---:|---:|---|"]
    for short in BASE7:
        s, w = columns(S[short], "tf"), columns(W[short], "tf")
        cells = [(sc, scope(s, sc)) for sc in TYPES[:1] + [NO_P8] + TYPES[1:] + list(LAYERS)] + [(f"{t} (L2w)", scope(w, t)) for t in L2_TYPES] \
            + [("L2w", w)]
        for sc, f in cells:
            c = cell(f, "item", f"power|{short}|{sc}")
            mde = z * c["se_c"]
            lines.append(f"| {name(short)} | {sc} | {c['n']:,} | {c['excluded']:,} | {c['concepts']}" + (" ‡" if c["concepts"] < FEW_CLUSTERS else "")
                         + f" | {fd(c['delta'])} | {fci(c['q'], True)} | {fci(c['c'], True)} | {f4(c['se_c'])} | {f4(mde)} | "
                         + ("— (no variance: every draw equal)" if c["se_c"] == 0 else ("yes" if abs(c["delta"]) >= mde else "no"))
                         + " |")
    lines += sources_block([SINGLE, L2W], only=BASE7)
    write(OUT / "power.md", lines)


def write_predictions(results: list[dict], extra: dict, rereads: list[dict], floors: dict) -> None:
    lines = header("T7: the registered predictions R1–R6 (dev)", [
        "Read on the concept-clustered interval (D-030), Holm–Bonferroni across all the tests below, BH beside.",
        "**Supported** when the interval lies on the predicted side of the null and Holm p < α; **contradicted**",
        "in the mirror case; **not supported** otherwise (S4's rule). The null is 0, or the threshold for R3",
        "and R5 (A2 c). Tie-free is primary (D-028 note); as run and the D-004 clean subset each form their",
        "own Holm family and are shown beside.",
    ])
    lines += [f"α = {ALPHA}; R3 threshold {PM_NULL}; R5 threshold {RATIO_NULL:g}. A test is **forced** *not "
              "supported* when its PM is undefined (R3, R4) or R5's L3 denominator has an interval containing 0 "
              "(A2 d). **CI (query)** resamples queries instead of concepts (A4); it is printed, never read. **n scored "
              "(excluded)** is, per pool, the item-scored queries and those left out (D-033 golds, the P7 query). Concepts are "
              "the clusters behind each pool; ‡ marks a pool under "
              f"{FEW_CLUSTERS} concepts, whose percentile interval under-covers.", ""]
    floor_named = [s for s in BASE7 if floors[s] < FLOOR]
    lines += ["**Floor re-check, tie-free, treated leaves** (A2 i): "
              + ", ".join(f"{name(s)} {f4(floors[s])}" for s in BASE7) + ". "
              + ("Below the floor: " + ", ".join(name(s) for s in floor_named) + "; their tests stay registered."
                 if floor_named else "None of the seven named arms is below the floor."), ""]
    lines += ["| test | hypothesis | blind | arm | concepts | n scored (excluded) | estimate | CI (query) | CI (concept) | "
              "p | Holm p | BH p | reading | as run | CI (query), as run | CI (concept), as run | reading, as run | differs |",
              "|---|---|---|---|---|---|---:|---|---|---:|---:|---:|---|---:|---|---|---|---|"]
    for r in results:
        t, a = r["tf"], r["run"]
        lines.append(
            f"| {r['id']} | {r['hyp']}: {r['what']} | {'blind' if r['blind'] else 'confirmatory'} | {name(r['arm'])} | "
            f"{ccount(t['clusters'])} | {ncount(t['counts'])} | {fd(t['est'])} | {fci(t['q'], True)} | {fci(t['c'], True)} | {fp(t['p'])} | "
            f"{fp(t['holm'])} | {fp(t['bh'])} | **{t['reading']}**" + (" (forced)" if t["forced"] else "")
            + f" | {fd(a['est'])} | {fci(a['q'], True)} | {fci(a['c'], True)} | {a['reading']} | {'**yes**' if a['reading'] != t['reading'] else 'no'} |")
    reopen = extra["reopen"]
    lines += ["", f"**D-043 ruling 3.** Reopened if any R1 / R2 test reads *not supported* with a clustered interval "
              f"wider than {WIDE_L2:.2f} (design): "
              + ("**yes** — " + ", ".join(f"{r['id']} {name(r['arm'])}" for r in reopen) if reopen else "**no**") + ".", ""]
    lines += ["## S4's P1–P5 re-read tie-free (reference, not registered)", "",
              "The D-028 note: where a tie-free re-reading changes an S4 category, the S4 reading stands as S4's and "
              "the difference is stated. S4's own rule, margin and Holm family of its tests; P5 with A2 a's loss share.", "",
              "| prediction | hypothesis | test | arm | estimate | CI (concept) | Holm p | reading, tie-free |",
              "|---|---|---|---|---:|---|---:|---|"]
    for r in rereads:
        lines.append(f"| {r['id']} | {r['hyp']} | {r['what']} | {name(r['arm'])} | {fd(r['est'])} | {fci(r['c'], True)} | "
                     f"{fp(r['holm'])} | {r['reading']} |")
    lines += [f"", f"S4 P3 margin ±{MARGIN}."]
    lines += sources_block([SINGLE, L2W, "texto"], only=BASE7)
    write(OUT / "predictions.md", lines)


def write_figures(S: dict, W: dict, stats: dict, models: dict, pms: dict) -> None:
    """Figs. 1–3, and the table of every number they plot."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGS.mkdir(parents=True, exist_ok=True)
    lines = header("Figures 1–3, drafts, and the numbers they plot", [
        "Every plotted value is printed below, computed by the same code as T1–T7. Tie-free throughout; dev.",
    ])
    # Fig. 1 — the collapse, identity → modified, parent against item, all nine single types.
    fig1 = []
    for short in [s for _, s, _, _ in ARMS]:
        f = item(columns(S[short], "tf"))
        fig1.append((short, f["item_id"].mean(), f["parent_id"].mean(), f["item_mod"].mean(), f["parent_mod"].mean()))
    fig, ax = plt.subplots(figsize=(7, 6))
    for short, ii, pi, im, pmv in fig1:
        ax.annotate("", xy=(im, pmv), xytext=(ii, pi), arrowprops={"arrowstyle": "->", "color": "grey", "lw": 0.8})
        ax.plot([ii], [pi], "o", color="black", ms=4)
        ax.plot([im], [pmv], "o", color="tab:red", ms=4)
        ax.text(im, pmv, " " + short, fontsize=6, va="center")
    ax.set_xlabel("item Acc@1 (tie-free)")
    ax.set_ylabel("parent Acc@1 (tie-free)")
    ax.set_title("Fig. 1 — identity (black) → one referent-preserving edit (red)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig1_collapse.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines += ["## Fig. 1 — the collapse (`fig1_collapse.png`)", "",
              f"Item-scored `{SINGLE}` queries, all nine types.", "",
              "| arm | item, identity | parent, identity | item, modified | parent, modified |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {name(s)} | {f4(a)} | {f4(b)} | {f4(c)} | {f4(d)} |" for s, a, b, c, d in fig1]

    # Fig. 2 — retention, arm × type (+ L2w), and M0's adjusted effects for the seven base arms.
    cols = TYPES + ["L2w"]
    arms = [s for _, s, _, _ in ARMS]
    grid = np.array([[stats[s][(c, "item", "tf_ret")] for c in cols] for s in arms])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [3, 2]})
    im = a1.imshow(grid, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    a1.set_xticks(range(len(cols)), cols, rotation=60, ha="right", fontsize=7)
    a1.set_yticks(range(len(arms)), arms, fontsize=7)
    fig.colorbar(im, ax=a1, fraction=0.04, label="retention (tie-free)")
    a1.set_title("Fig. 2a — retention")
    for k, short in enumerate(BASE7):
        m = models[short][("M0", "all")]
        if not m.get("ok"):
            continue
        xs = [m["fe"].get(t, np.nan) for t in TYPES]
        lo = [m["ci"][t][0] if t in m["ci"] else np.nan for t in TYPES]
        hi = [m["ci"][t][1] if t in m["ci"] else np.nan for t in TYPES]
        ys = np.arange(len(TYPES)) + (k - 3) * 0.1
        a2.errorbar(xs, ys, xerr=[np.subtract(xs, lo), np.subtract(hi, xs)], fmt="o", ms=3, lw=0.8, label=short)
    a2.set_yticks(range(len(TYPES)), TYPES, fontsize=7)
    a2.axvline(0, color="grey", lw=0.8)
    a2.set_xlabel("M0 β (Acc@1 units, model CI)")
    a2.set_title("Fig. 2b — adjusted type effects")
    a2.legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(FIGS / "fig2_profile.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines += ["", "## Fig. 2 — the profile (`fig2_profile.png`)", "",
              f"2a: tie-free retention, item level (`{SINGLE}` types; L2w pooled). 2b: M0 β as in T2. The last "
              "column, `synonym_label` without the P8 queries (D-044), is printed and not plotted.", "",
              "| arm | " + " | ".join(cols) + f" | {NO_P8} |", "|---|" + "---:|" * (len(cols) + 1)]
    lines += [f"| {name(s)} | " + " | ".join(f4(v) for v in row) + f" | {f4(stats[s][(NO_P8, 'item', 'tf_ret')])} |"
              for s, row in zip(arms, grid)]

    # Fig. 3 — δ against the lexical deficit, and PM per arm.
    edges = np.quantile(item(columns(S["bm25_unigram"], "tf"))["lex_def"], np.linspace(0, 1, 6))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    fig3 = []
    for short in ("bm25_unigram", "bge_m3_colbert", "bge_m3_dense"):
        f = item(columns(S[short], "tf"))
        idx = np.clip(np.searchsorted(edges, f["lex_def"], side="right") - 1, 0, len(edges) - 2)
        means = [delta(f[idx == b]).mean() if (idx == b).any() else np.nan for b in range(len(edges) - 1)]
        centres = [f["lex_def"][idx == b].mean() if (idx == b).any() else np.nan for b in range(len(edges) - 1)]
        a1.plot(centres, means, "o-", label=short)
        fig3.append((short, centres, means, [int((idx == b).sum()) for b in range(len(edges) - 1)]))
    a1.axhline(0, color="grey", lw=0.8)
    a1.set_xlabel("1 − lexical coverage (quintile bins of `bm25_unigram`'s queries)")
    a1.set_ylabel("mean δ (tie-free)")
    a1.set_title("Fig. 3a — damage against lost overlap")
    a1.legend(fontsize=7)
    pm_rows = []
    for k, short in enumerate(BASE7):
        p = pms[(short, "tf", "all")]
        d = p["draws"]["pm"][np.isfinite(p["draws"]["pm"])]
        lo, hi = ci(d)
        pm_rows.append((short, p["point"]["pm"], lo, hi, interval_contains_zero(p["draws"]["mean_d"])))
        if not pm_rows[-1][4]:
            a2.errorbar([p["point"]["pm"]], [k], xerr=[[p["point"]["pm"] - lo], [hi - p["point"]["pm"]]], fmt="o")
    a2.set_yticks(range(len(BASE7)), BASE7, fontsize=7)
    a2.axvline(PM_NULL, color="grey", lw=0.8, ls="--")
    a2.set_xlabel("proportion mediated by overlap (OLS, concept CI)")
    a2.set_title("Fig. 3b — PM (M1)")
    fig.tight_layout()
    fig.savefig(FIGS / "fig3_mediation.png", dpi=150, metadata={"Software": None})
    plt.close(fig)
    lines += ["", "## Fig. 3 — mediation (`fig3_mediation.png`)", "",
              f"3a: item-scored `{SINGLE}` queries binned by lexical deficit at `bm25_unigram`'s quintiles "
              "(the same queries for every arm).", "",
              "| arm | bin | n | mean deficit | mean δ |", "|---|---:|---:|---:|---:|"]
    for short, centres, means, ns in fig3:
        for b, (cx, m, nb) in enumerate(zip(centres, means, ns), start=1):
            lines.append(f"| {name(short)} | {b} | {nb:,} | {f4(cx)} | {fd(m)} |")
    lines += ["", "3b: PM as in T3 (not plotted when undefined).", "", "| arm | PM | CI (concept) | plotted |", "|---|---:|---|---|"]
    lines += [f"| {name(s)} | {fd(p)} | {fci((lo, hi), True)} | {'no' if und else 'yes'} |" for s, p, lo, hi, und in pm_rows]
    lines += ["", stack_stamp()]
    write(OUT / "figures.md", lines)


# --------------------------------------------------------------------------- provenance


def stack_stamp() -> str:
    return analysis_stack.stamp() + f" BLAS threads: {BLAS_THREADS} (A6)."


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
                f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (SIDECAR, *inputs)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals; p from the concept-clustered "
              "draws (D-030). Split `dev`.", stack_stamp()]
    return lines


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def write_provenance() -> None:
    lines = header("T8: run provenance (dev)", [
        f"Every run the S6 tables read. The `{L2W}` runs are S6's (work item 3); the `texto` and",
        f"`{SINGLE}` runs are S4's and S3's, read, not re-run, so no earlier sprint's run is superseded (D-047).",
    ])
    lines += ["| query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 | derived from |",
              "|---|---|---:|---|---|---|---|---|"]
    for queryset in ("texto", SINGLE, L2W):
        for d, short, _, _ in ARMS:
            m = meta(queryset, d)
            comps = ", ".join(f"`{c['run_id']}` @ `{c['code_commit'][:7]}`" for c in m.get("components", [])) or "—"
            lines.append(f"| `{queryset}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                         f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | "
                         f"`{m['query_set_sha256'][:16]}` | {comps} |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |"
                for p in (SIDECAR, SINGLE_JSON, L2_JSON, CORPUS_JSON, SINGLE_SIDECAR, L2_SIDECAR)),
              "", stack_stamp()]
    write(OUT / "run_provenance.md", lines)


# --------------------------------------------------------------------------- main


def assemble(single: str, dup: set[str], parents: dict[str, str], W: dict) -> dict:
    """Everything T1–T8 read for one single set, beside the L2w frames `W` (unchanged by the delivery).

    The bootstrap labels carry no query-set name, so the v1 and v2 assemblies of the same cell draw the same
    concept weights and their draws pair (A8, `v2_variant.paired_diff`). `_PM_CACHE` is keyed by arm and not by
    query set, so it is cleared here: the two assemblies of a `--v2` run must not share M1 fits.
    """
    _PM_CACHE.clear()
    keys = set(perquery(single, DIR["bm25_unigram"])["query_item_key"].astype(str))
    feats = query_features(single, keys)
    S = {short: paired(short, single, dup, parents, feats) for _, short, _, _ in ARMS}
    first = next(iter(S.values()))
    for short, frame in S.items():
        if list(frame["q"]) != list(first["q"]):
            raise ValueError(f"{short}: query order differs between arms")

    trunc = {short: (int(S[short]["trunc_mod"].sum()), int(W[short]["trunc_mod"].sum()),
                     int(S[short]["trunc_id"].sum() + W[short]["trunc_id"].sum())) for short in S}

    stats: dict = {}
    for short in S:
        stats[short] = {}
        for v in ("run", "tf"):
            s, w = columns(S[short], v), columns(W[short], v)
            union = pd.concat([scope(s, "L2"), w])
            views = {**{sc: scope(w, sc) for sc in W_SCOPES}, "L2s": scope(s, "L2"), "L2∪": union}
            for sc, f in views.items():
                for level in ("item", "parent"):
                    stats[short][(sc, level, v)] = cell(f, level, f"{short}|{sc}|{v}")
        s = columns(S[short], "tf")
        for sc in TYPES:
            stats[short][(sc, "item", "tf_ret")] = cell(scope(s, sc), "item", f"{short}|{sc}|tf")["retention"]
        stats[short][("L2w", "item", "tf_ret")] = stats[short][("L2w", "item", "tf")]["retention"]
        stats[short][(NO_P8, "item", "tf_ret")] = cell(scope(s, NO_P8), "item", f"{short}|{NO_P8}|tf")["retention"]
    floors = {short: float(item(columns(S[short], "tf"))["item_id"].mean()) for short in S}

    models: dict = {}
    pms: dict = {}
    raw: dict = {}
    for short in BASE7:
        models[short] = {}
        tf = item(columns(S[short], "tf"))
        run = item(columns(S[short], "run"))
        for tag, keep in (("all", tf), ("no_p8", tf[~tf["q"].isin(P8_DEV)])):
            for mname, x in (("M0", []), ("M1", DEFICITS), ("M2", ["d_tok"])):
                models[short][(mname, tag)] = fit_mixed(keep, x)
            for t in TYPES:
                sub_tf = keep[keep["type"] == t]
                sub_run = run[run["q"].isin(sub_tf["q"])]
                d_tf = delta(sub_tf)[:, None]
                lab = f"s6|raw|{short}|{tag}|{t}"
                whole = S[short][S[short]["type"] == t]
                if tag == "no_p8":
                    whole = whole[~whole["q"].isin(P8_DEV)]
                raw[(short, tag, t)] = {"n": len(sub_tf), "excluded": nexcl(whole), "tf": float(d_tf.mean()), "run": float(delta(sub_run).mean()),
                                        "concepts": nconc(sub_tf), "q": ci(boot_query(d_tf, lab)[:, 0]),
                                        "c": ci(boot_cluster(d_tf, sub_tf["concept"].to_numpy(), lab)[:, 0])}
        pms[(short, "tf", "all")] = pm_fit(columns(S[short], "tf"), short, "tf")
        pms[(short, "run", "all")] = pm_fit(columns(S[short], "run"), short, "run")
        pms[(short, "tf", "all_q")] = pm_fit(unitize(columns(S[short], "tf"), "query"), short, "tf", unit="query")
        s_tf = columns(S[short], "tf")
        pms[(short, "tf", "no_p8")] = pm_fit(s_tf[~s_tf["q"].isin(P8_DEV)], short, "tf", "no_p8")
        pms[(short, "tf", "m2")] = {**ols_within(item(s_tf), ["d_tok"], "s6|m2|tf")}
        pms[(short, "tf", "m2_no_p8")] = ols_within(item(s_tf[~s_tf["q"].isin(P8_DEV)]), ["d_tok"], "s6|m2|tf|no_p8")

    base = item(columns(S["bm25_unigram"], "tf"))
    corr = base[DEFICITS + ["d_tok"]].corr()

    results, extra = evaluate(S, W)
    rereads = s4_rereads(S)
    return {"single": single, "S": S, "W": W, "trunc": trunc, "stats": stats, "floors": floors, "models": models,
            "pms": pms, "raw": raw, "base": base, "corr": corr, "results": results, "extra": extra, "rereads": rereads}


def ols_diff(a: dict, b: dict, a_draws: np.ndarray, b_draws: np.ndarray, a_est: float, b_est: float) -> dict:
    """b − a of one OLS coefficient from two `ols_within` fits (A8): paired when both rest on the same concepts."""
    return v2v.paired_diff({"est": a_est, "draws": a_draws, "clusters_key": a["clusters_key"]},
                           {"est": b_est, "draws": b_draws, "clusters_key": b["clusters_key"]})


def ols_cells(a: dict, b: dict, coef: str, ia: int, ib: int) -> list[str]:
    """The four comparison columns of one OLS coefficient: v1 with its interval, v2 with its, v2 − v1, paired CI."""
    da, db = a["draws"][coef][:, ia], b["draws"][coef][:, ib]
    d = ols_diff(a, b, da, db, a["point"][coef][ia], b["point"][coef][ib])
    return [f"{fd(a['point'][coef][ia])} {fci(ci(da[np.isfinite(da)]), True)}",
            f"{fd(b['point'][coef][ib])} {fci(ci(db[np.isfinite(db)]), True)}", v2v.fsd(d["est"]), v2v.fci(d["c"])]


def row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def mixed_diff(ma: dict, mb: dict, term: str) -> str:
    """b − a of a mixed-model fixed effect: a point difference, no interval (the fits share no draws)."""
    if ma.get("ok") and mb.get("ok") and term in ma["fe"] and term in mb["fe"]:
        return v2v.fsd(mb["fe"][term] - ma["fe"][term])
    return "—"


def fit_status(m: dict) -> str:
    return (f"leaf {'yes' if m['leaf'] else '**no**'}, converged {'yes' if m['converged'] else '**no**'}"
            if m.get("ok") else f"failed ({m.get('why')})")


def write_comparison(ref: dict, this: dict, dup: set[str]) -> None:
    """A8: R1–R6, every fixed effect of M0–M2, PM and the L1 / L3 pools on v1 beside v2, with the paired-draw
    difference where the draws align, and the stamps of both."""
    S1, S2 = ref["S"], this["S"]
    if list(next(iter(S1.values()))["q"]) != list(next(iter(S2.values()))["q"]):
        raise ValueError(f"{ref['single']} and {this['single']} do not hold the same dev queries in the same order")
    first = next(iter(S2.values()))
    n_changed = int(first["q"].isin(v2v.changed_keys("single_texto")).sum())
    lines = header("Comparison: v2 against v1 (dev, tie-free)", ["Written in the `--v2` mode (A8, D-061)."])
    lines += v2v.intro("S6", f"`{ref['single']}`", f"`{this['single']}`",
                       f"The two single sets hold the same {len(first):,} dev queries in the same order; `text` differs "
                       f"on {n_changed:,}, all in the `template_paraphrase` cell, so L1, L2s and `{L2W}` are the same "
                       "queries on both and a difference there is the H8 batch floor (ColBERT and the arms built on "
                       "it), not the repair. The identity side is the same run on both. The mixed models are refitted "
                       "on each set (one BLAS thread, A6) and their fixed effects differ without an interval.")
    # (A) R1–R6, tie-free
    lines += ["## R1–R6 (tie-free, the registered reading)", "",
              "| test | arm | concepts | n scored (excluded) | estimate, v1 | CI (concept), v1 | Holm p, v1 | "
              "reading, v1 | estimate, v2 | CI (concept), v2 | Holm p, v2 | reading, v2 | v2 − v1 | "
              "CI (paired draws) | reading moved |",
              "|---|---|---|---|---:|---|---:|---|---:|---|---:|---|---:|---|---|"]
    by_key = {(r["id"], r["arm"]): r for r in ref["results"]}
    for r in this["results"]:
        a, b = by_key[(r["id"], r["arm"])]["tf"], r["tf"]
        d = v2v.paired_diff(a, b)
        lines.append(f"| {r['id']} | {name(r['arm'])} | {ccount(b['clusters'])} | {ncount(b['counts'])} | {fd(a['est'])} | "
                     f"{fci(a['c'], True)} | {fp(a['holm'])} | {a['reading']}{' (forced)' if a['forced'] else ''} | "
                     f"{fd(b['est'])} | {fci(b['c'], True)} | {fp(b['holm'])} | **{b['reading']}**"
                     f"{' (forced)' if b['forced'] else ''} | {v2v.fsd(d['est'])} | {v2v.fci(d['c'])} | "
                     f"{v2v.moved(a['reading'], b['reading'])} |")
    for which, src in (("v1", ref), ("v2", this)):
        reopen = src["extra"]["reopen"]
        lines += ["", f"**D-043 ruling 3, {which}:** "
                  + ("**yes** — " + ", ".join(f"{r['id']} {name(r['arm'])}" for r in reopen) if reopen else "**no**") + "."]
    # (B) the fixed effects of M0–M2 per base arm
    lines += ["", "## The fixed effects of M0–M2, per base arm (item level, tie-free)", "",
              "Per type: the raw tie-free δ on both, its per-query paired difference (bootstrapped by concept under its "
              "own label) and the count of queries whose tie-free value moved; then each model's β by OLS with its "
              "concept-clustered interval on both and v2 − v1 from the paired draws, and the mixed model's β on both "
              "with the point difference. The covariate rows follow. A cell is `—` where the term is absent.", ""]
    head = ["term", "n scored", "raw δ, v1", "raw δ, v2", "δ v2 − v1", "CI (concept, paired)", "moved",
            "M0 β (OLS), v1", "M0 β (OLS), v2", "v2 − v1", "CI (paired)",
            "M1 β (OLS), v1", "M1 β (OLS), v2", "v2 − v1", "CI (paired)",
            "M2 β (OLS), v1", "M2 β (OLS), v2", "v2 − v1", "CI (paired)",
            "M0 β (mixed), v1", "v2", "v2 − v1", "M1 β (mixed), v1", "v2", "v2 − v1"]
    blank = [""] * 4
    for short in BASE7:
        pa, pb = ref["pms"][(short, "tf", "all")], this["pms"][(short, "tf", "all")]
        qa, qb = ref["pms"][(short, "tf", "m2")], this["pms"][(short, "tf", "m2")]
        ma1, mb1 = ref["models"][short][("M1", "all")], this["models"][short][("M1", "all")]
        ma0, mb0 = ref["models"][short][("M0", "all")], this["models"][short][("M0", "all")]
        fa, fb = item(columns(S1[short], "tf")).set_index("q"), item(columns(S2[short], "tf")).set_index("q")
        lines += [f"### {name(short)}", "", row(head), "|" + "---|" * len(head)]
        for t in TYPES:
            if t not in pb["types"] or t not in pa["types"]:
                continue
            ja, jb = pa["types"].index(t), pb["types"].index(t)
            ka, kb = qa["types"].index(t), qb["types"].index(t)
            g = fb[fb["type"] == t]
            h = fa.loc[g.index]
            dv = (g["item_mod"] - h["item_mod"]).to_numpy(float)
            dci = ci(boot_cluster(dv[:, None], g["concept"].to_numpy(), f"s6|cmp|{short}|{t}")[:, 0])
            cells = [t, f"{len(g):,}", fd(delta(h).mean()), fd(delta(g).mean()), v2v.fsd(float(dv.mean())), v2v.fci(dci),
                     f"{int((dv != 0).sum()):,}"]
            for fit_a, fit_b, coef, ia, ib in ((pa, pb, "beta0", ja, jb), (pa, pb, "beta1", ja, jb), (qa, qb, "beta1", ka, kb)):
                cells += ols_cells(fit_a, fit_b, coef, ia, ib)
            cells += [mixed_cell(ma0, t), mixed_cell(mb0, t), mixed_diff(ma0, mb0, t),
                      mixed_cell(ma1, t), mixed_cell(mb1, t), mixed_diff(ma1, mb1, t)]
            lines.append(row(cells))
        for j, x in enumerate(DEFICITS):
            lines.append(row([DEFICIT_LABEL[x], "", "", "", "", "", ""] + blank + ols_cells(pa, pb, "gamma", j, j) + blank
                             + ["", "", ""] + [mixed_cell(ma1, x), mixed_cell(mb1, x), mixed_diff(ma1, mb1, x)]))
        lines.append(row(["d_tok", "", "", "", "", "", ""] + blank + blank + ols_cells(qa, qb, "gamma", 0, 0)
                         + ["", "", ""] + ["", "", ""]))
        lines += ["", "Mixed fits: " + "; ".join(
            f"{mname} v1 {fit_status(ref['models'][short][(mname, 'all')])}, v2 {fit_status(this['models'][short][(mname, 'all')])}"
            for mname in ("M0", "M1", "M2")) + ".", ""]
    # (C) PM per arm
    lines += ["## Proportion mediated, per base arm", "",
              "PM (OLS) with its concept-clustered interval on both and v2 − v1 from the paired draws; `—` where the "
              "pool's mean δ has an interval containing 0 (A2 d) on that version. PM (mixed) as in T3.", "",
              "| arm | mean δ, v1 | CI (concept), v1 | mean δ, v2 | CI (concept), v2 | PM (OLS), v1 | CI (concept), v1 | "
              "PM (OLS), v2 | CI (concept), v2 | v2 − v1 | CI (paired) | PM (mixed), v1 | PM (mixed), v2 | v2 − v1 |",
              "|---|---:|---|---:|---|---:|---|---:|---|---:|---|---:|---:|---:|"]
    for short in BASE7:
        pa, pb = ref["pms"][(short, "tf", "all")], this["pms"][(short, "tf", "all")]
        ua, ub = interval_contains_zero(pa["draws"]["mean_d"]), interval_contains_zero(pb["draws"]["mean_d"])
        d = ols_diff(pa, pb, pa["draws"]["pm"], pb["draws"]["pm"], pa["point"]["pm"], pb["point"]["pm"])
        ma = mixed_pm(ref["models"][short][("M0", "all")], ref["models"][short][("M1", "all")], item(columns(S1[short], "tf")))
        mb = mixed_pm(this["models"][short][("M0", "all")], this["models"][short][("M1", "all")], item(columns(S2[short], "tf")))
        cells = [name(short), fd(pa["point"]["mean_d"]), fci(ci(pa["draws"]["mean_d"]), True),
                 fd(pb["point"]["mean_d"]), fci(ci(pb["draws"]["mean_d"]), True)]
        for p, und in ((pa, ua), (pb, ub)):
            finite = p["draws"]["pm"][np.isfinite(p["draws"]["pm"])]
            cells += ["—", "—"] if und else [fd(p["point"]["pm"]), fci(ci(finite), True)]
        cells += ["—", "—"] if ua or ub else [v2v.fsd(d["est"]), v2v.fci(d["c"])]
        cells += [fd(ma) if np.isfinite(ma) else "—", fd(mb) if np.isfinite(mb) else "—",
                  v2v.fsd(mb - ma) if np.isfinite(ma) and np.isfinite(mb) else "—"]
        lines.append(row(cells))
    # (D) the L1 and L3 pools R5 reads: δ, d_tok and δ / d_tok
    lines += ["", "## The L1 and L3 pools (T4): δ, mean d_tok and δ / d_tok", "",
              "R5 reads the L1 : L3 ratio of δ / d̄_tok. L1 holds no repaired query; L3's `template_paraphrase` half "
              "does, and its d_tok is recomputed on the v2 texts.", "",
              "| arm | pool | n scored | mean δ, v1 | mean δ, v2 | δ v2 − v1 | CI (concept, paired) | moved | "
              "mean d_tok, v1 | mean d_tok, v2 | δ / d_tok, v1 | CI (concept), v1 | δ / d_tok, v2 | CI (concept), v2 | "
              "v2 − v1 | CI (paired) |",
              "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|---:|---|---:|---|"]
    for short in BASE7:
        for pool in ("L1", "L3"):
            fa = item(scope(columns(S1[short], "tf"), pool)).set_index("q")
            fb = item(scope(columns(S2[short], "tf"), pool)).set_index("q")
            ea, ra, _, ta = sensitivity_draws(fa, f"s6|sens|{short}|{pool}")
            eb, rb, _, tb = sensitivity_draws(fb, f"s6|sens|{short}|{pool}")
            key_a, key_b = tuple(sorted(set(fa["concept"]))), tuple(sorted(set(fb["concept"])))
            d = v2v.paired_diff({"est": ea, "draws": ra, "clusters_key": key_a},
                                {"est": eb, "draws": rb, "clusters_key": key_b})
            dv = (fb["item_mod"] - fa.loc[fb.index, "item_mod"]).to_numpy(float)
            dci = ci(boot_cluster(dv[:, None], fb["concept"].to_numpy(), f"s6|cmp|{short}|{pool}")[:, 0])
            lines.append(f"| {name(short)} | {pool} | {len(fb):,} | {fd(delta(fa).mean())} | {fd(delta(fb).mean())} | "
                         f"{v2v.fsd(float(dv.mean()))} | {v2v.fci(dci)} | {int((dv != 0).sum()):,} | {f4(ta)} | {f4(tb)} | "
                         f"{fd(ea)} | {fci(ci(ra[np.isfinite(ra)]), True)} | {fd(eb)} | {fci(ci(rb[np.isfinite(rb)]), True)} | "
                         f"{v2v.fsd(d['est'])} | {v2v.fci(d['c'])} |")
    # stamps
    lines += ["", "## Sources", "",
              "| which | query set | run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 |",
              "|---|---|---|---:|---|---|---|---|"]
    for which, queryset in (("v1", ref["single"]), ("v2", this["single"]), ("both", L2W), ("both", "texto")):
        for d, _, _, _ in ARMS:
            m = meta(queryset, d)
            lines.append(f"| {which} | `{queryset}` | `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | "
                         f"`{m['code_commit'][:7]}` | {str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |"
                for p in (SIDECAR, DATA / f"OE_{ref['single']}.json", DATA / f"OE_{this['single']}.json", L2_JSON,
                          CORPUS_JSON, SINGLE_SIDECAR, L2_SIDECAR, v2v.CHANGES)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals. Split `dev`.", stack_stamp()]
    write(OUT / "comparison.md", lines)


def main(argv=None) -> None:
    args = v2v.parse(argv)
    configure(args.v2)
    analysis_stack.require()
    if V2_MODE:
        require_runs(SINGLE, [d for d, _, _, _ in ARMS])
    OUT.mkdir(parents=True, exist_ok=True)
    dup = duplicated()
    parents = parent_of()

    # L2w is untouched by the delivery: featurised and paired once, shared by both assemblies.
    w_keys = set(perquery(L2W, DIR["bm25_unigram"])["query_item_key"].astype(str))
    W = {short: paired(short, L2W, dup, parents, query_features(L2W, w_keys)) for _, short, _, _ in ARMS}
    first = next(iter(W.values()))
    for short, frame in W.items():
        if list(frame["q"]) != list(first["q"]):
            raise ValueError(f"{short}: query order differs between arms")

    this = assemble(SINGLE, dup, parents, W)
    S, stats, models, pms, results = this["S"], this["stats"], this["models"], this["pms"], this["results"]

    write_l2_profile(stats, this["trunc"], S, W, dup)
    write_adjusted(models, this["raw"], S)
    write_mediation(models, pms, S, this["corr"], len(this["base"]))
    write_sensitivity(S, W)
    write_d004({SINGLE: S["bm25_unigram"].drop_duplicates("q"), L2W: W["bm25_unigram"].drop_duplicates("q")}, results)
    write_power(S, W)
    write_predictions(results, this["extra"], this["rereads"], this["floors"])
    write_figures(S, W, stats, models, pms)
    write_provenance()
    if V2_MODE:
        # v1 in the same process: the same functions on the base set, the same L2w frames and identity runs.
        write_comparison(assemble("single_texto", dup, parents, W), this, dup)
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
