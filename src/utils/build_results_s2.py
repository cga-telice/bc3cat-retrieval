"""Generate the S2 statistics tables — never hand-edited.

Reads the 15 S2 runs under `runs/OE/{texto,single_texto,stacked_texto}/`, the stage
decomposition under `logs/S2/stages/` (derived by `src/utils/structured_stages.py`) and the
classified failure sample `docs/synthetic-oe/sprints/SPRINT_S2_FAILURES.csv`, and writes
markdown tables to `docs/synthetic-oe/results/S2/`.

    python src/utils/build_results_s2.py

Tables only. No gate reading, no thresholds, no interpretation: those belong to the sprint
report, which quotes these files.

Statistics, as fixed by the S2 design ("Design constraints"):

- Every bootstrap draws 10,000 resamples. The query-level bootstrap resamples queries with
  replacement; the concept-clustered bootstrap resamples `gold_parent_key` clusters with
  replacement and recomputes each statistic as a ratio of summed counts. Intervals are
  percentile 95 %.
- Resampling is done exactly, not approximately, through multinomial counts over the
  distinct row patterns (query level) or over clusters (clustered): drawing n indices with
  replacement and counting how often each distinct row appears has precisely that
  multinomial law, so the result is the ordinary bootstrap at a fraction of the memory.
- Seeds are derived per table cell from `SEED` and a CRC-32 of the cell's label, so a cell's
  interval does not depend on the order in which the cells are computed.
- Two-sided bootstrap p-values for paired deltas, `(1 + #{d* on the far side of 0}) /
  (B + 1)` doubled and capped at 1, are adjusted by Holm–Bonferroni and Benjamini–Hochberg
  within each table's family of contrasts.
"""

from __future__ import annotations

import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from utils.provenance import sha256_file  # noqa: E402

RUNS = REPO / "runs" / "OE"
STAGES = REPO / "logs" / "S2" / "stages"
FAILURES = REPO / "docs" / "synthetic-oe" / "sprints" / "SPRINT_S2_FAILURES.csv"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S2"
GENERATOR = "src/utils/build_results_s2.py"

SEED = 20260917
B = 10_000
ALPHA = 0.05

QUERYSETS = ("texto", "single_texto", "stacked_texto")
METHODS = (
    "bm25_unigram_params__k1-0.60__b-0.35__OE",
    "bm25_unigram__k1-0.60__b-0.35__OE",
    "bge_m3_colbert__OE",
    "structured_pipeline_rules__OE",
    "structured_pipeline_rules_valuenorm__OE",
)
SHORT = {
    "bm25_unigram_params__k1-0.60__b-0.35__OE": "bm25_unigram_params",
    "bm25_unigram__k1-0.60__b-0.35__OE": "bm25_unigram",
    "bge_m3_colbert__OE": "bge_m3_colbert",
    "structured_pipeline_rules__OE": "structured_rules",
    "structured_pipeline_rules_valuenorm__OE": "structured_valuenorm",
}
STRUCTURED = ("structured_pipeline_rules__OE", "structured_pipeline_rules_valuenorm__OE")
L1_CONDITIONS = ("single_unit_conversion", "single_num_to_text")
CONTRASTS = (  # (treatment, reference)
    ("structured_pipeline_rules__OE", "bm25_unigram_params__k1-0.60__b-0.35__OE"),
    ("structured_pipeline_rules__OE", "bm25_unigram__k1-0.60__b-0.35__OE"),
    ("structured_pipeline_rules_valuenorm__OE", "bm25_unigram_params__k1-0.60__b-0.35__OE"),
    ("structured_pipeline_rules_valuenorm__OE", "bm25_unigram__k1-0.60__b-0.35__OE"),
)
COLBERT_CONTRASTS = (  # F3 of the S2 audit: the inversion claim needs its own intervals
    ("bge_m3_colbert__OE", "bm25_unigram_params__k1-0.60__b-0.35__OE"),
    ("bge_m3_colbert__OE", "bm25_unigram__k1-0.60__b-0.35__OE"),
)
#: The corpus the identity queries are read back from, for the miss anatomy table.
CORPUS = REPO / "data" / "processed" / "OE_long_feats.parquet"
#: Methods whose rank-1 ties are read from the run's own scores. The structured arms encode
#: their tie order in the score itself (tier 1 descends by 1e-4), so their ties come from the
#: stage decomposition's `stage3_matched` instead.
SCORE_TIE_METHODS = (
    "bm25_unigram_params__k1-0.60__b-0.35__OE",
    "bm25_unigram__k1-0.60__b-0.35__OE",
    "bge_m3_colbert__OE",
)
METRIC_COLS = ["item_acc1", "parent_acc1"]


# --------------------------------------------------------------------------- loading


def load_runs() -> dict[tuple[str, str], dict]:
    """The 15 S2 runs, keyed (queryset, method). Fails loud on a missing run or stamp."""
    runs = {}
    for queryset in QUERYSETS:
        for method in METHODS:
            run_dir = RUNS / queryset / method
            meta_path = run_dir / "run_meta.json"
            if not meta_path.is_file():
                raise SystemExit(f"missing run: {run_dir}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for field in ("run_id", "config_sha256", "code_commit", "query_set_sha256"):
                if not meta.get(field):
                    raise SystemExit(f"{meta_path}: stamp field {field!r} missing or empty")
            meta["_perquery"] = pd.read_parquet(run_dir / "results_perquery.parquet")
            meta["_metrics"] = json.loads((run_dir / "metrics_dual.json").read_text(encoding="utf-8"))
            if not meta["_perquery"]["query_item_key"].is_unique:
                raise SystemExit(f"{run_dir}: duplicate query_item_key in results_perquery")
            runs[(queryset, method)] = meta
    # Cross-method pairing needs identical query ids within a query set.
    for queryset in QUERYSETS:
        ref = set(runs[(queryset, METHODS[0])]["_perquery"]["query_item_key"])
        for method in METHODS[1:]:
            if set(runs[(queryset, method)]["_perquery"]["query_item_key"]) != ref:
                raise SystemExit(f"{queryset}: query ids differ between {METHODS[0]} and {method}")
    return runs


def metrics_dual_overall(meta: dict, target: str) -> float:
    for row in meta["_metrics"]:
        if row["target"] == target and row["scope"] == "overall":
            return row["Acc@1"]
    return float("nan")


# --------------------------------------------------------------------------- bootstrap


def _rng(label: str) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([SEED, zlib.crc32(label.encode("utf-8"))]))


def boot_query(values: np.ndarray, label: str) -> np.ndarray:
    """B × k matrix of resampled column means. `values` is n × k."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    patterns, counts = np.unique(values, axis=0, return_counts=True)
    weights = _rng("query|" + label).multinomial(n, counts / n, size=B)
    return weights @ patterns / n


def boot_cluster(values: np.ndarray, clusters: np.ndarray, label: str) -> np.ndarray:
    """B × k matrix of resampled column means, resampling whole clusters."""
    frame = pd.DataFrame(np.asarray(values, dtype=float))
    frame["_c"] = clusters
    grouped = frame.groupby("_c", sort=True)
    sums = grouped.sum().to_numpy()
    sizes = grouped.size().to_numpy().astype(float)
    g = len(sizes)
    weights = _rng("cluster|" + label).multinomial(g, np.full(g, 1.0 / g), size=B)
    return (weights @ sums) / (weights @ sizes)[:, None]


def ci(draws: np.ndarray) -> tuple[float, float]:
    lo, hi = np.percentile(draws, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return float(lo), float(hi)


def boot_p(draws: np.ndarray) -> float:
    below = int((draws <= 0).sum())
    above = int((draws >= 0).sum())
    return min(1.0, 2 * (1 + min(below, above)) / (B + 1))


def holm(p: list[float]) -> list[float]:
    m = len(p)
    order = np.argsort(p, kind="stable")
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[idx]))
        adj[idx] = running
    return adj.tolist()


def bh(p: list[float]) -> list[float]:
    m = len(p)
    order = np.argsort(p, kind="stable")
    adj = np.empty(m)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        idx = order[rank]
        running = min(running, p[idx] * m / (rank + 1))
        adj[idx] = running
    return adj.tolist()


# --------------------------------------------------------------------------- formatting


def f4(x: float) -> str:
    return f"{x:.4f}"


def fd(x: float) -> str:
    return f"{x:+.4f}"


def fci(lo_hi: tuple[float, float], signed: bool = False) -> str:
    fmt = fd if signed else f4
    return f"[{fmt(lo_hi[0])}, {fmt(lo_hi[1])}]"


def fp(p: float) -> str:
    return "< 0.0001" if p < 1e-4 else f"{p:.4f}"


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S2 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def sources(runs: dict, keys: list[tuple[str, str]], extra: list[tuple[str, Path]] = ()) -> list[str]:
    lines = [
        "",
        "## Sources",
        "",
        "| run_id | config SHA-256 | code commit | query-set SHA-256 |",
        "|---|---|---|---|",
    ]
    for key in keys:
        m = runs[key]
        lines.append(
            f"| `{m['run_id']}` | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
            f"`{m['query_set_sha256'][:16]}` |"
        )
    if extra:
        lines += ["", "| derived input | SHA-256 |", "|---|---|"]
        for name, path in extra:
            lines.append(f"| `{name}` | `{sha256_file(path)[:16]}` |")
    lines += ["", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals."]
    return lines


def write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- pairing


def paired_with_identity(runs: dict, queryset: str, method: str, condition: str | None) -> tuple[pd.DataFrame, int]:
    """Condition rows joined to the identity (`texto`) rows of the same gold leaves."""
    cond = runs[(queryset, method)]["_perquery"]
    if condition is not None:
        cond = cond[cond["condition"] == condition]
    ident = runs[("texto", method)]["_perquery"][["query_item_key", *METRIC_COLS]].rename(
        columns={"query_item_key": "gold_item_key", "item_acc1": "id_item_acc1", "parent_acc1": "id_parent_acc1"}
    )
    joined = cond.merge(ident, on="gold_item_key", how="left", validate="many_to_one")
    unmatched = int(joined["id_item_acc1"].isna().sum())
    return joined.dropna(subset=["id_item_acc1"]), unmatched


# --------------------------------------------------------------------------- tables


def write_identity(runs: dict) -> None:
    lines = header(
        "identity (`texto`, dev)",
        [
            "Acc@1 per method on the identity rendering, with query-level and concept-clustered",
            "bootstrap 95 % CIs. Δ = parent − item Acc@1; D = P(item correct | parent correct).",
            "`metrics_dual` is the run's own overall Acc@1, printed as a cross-check.",
        ],
    )
    lines += [
        "| method | n queries | n concepts | item Acc@1 | item CI (query) | item CI (concept) | "
        "parent Acc@1 | parent CI (query) | parent CI (concept) | Δ | Δ CI (query) | D | D CI (query) | "
        "metrics_dual item / parent |",
        "|---|---:|---:|---:|---|---|---:|---|---|---:|---|---:|---|---|",
    ]
    for method in METHODS:
        meta = runs[("texto", method)]
        df = meta["_perquery"]
        vals = df[METRIC_COLS].to_numpy()
        label = f"identity|{method}"
        q = boot_query(vals, label)
        c = boot_cluster(vals, df["gold_parent_key"].to_numpy(), label)
        item, parent = vals.mean(axis=0)
        gap = parent - item
        d = df.loc[df["parent_acc1"] == 1, "item_acc1"].mean()
        d_draws = q[:, 0] / q[:, 1]  # item ⊆ parent: P(item|parent) = acc_item / acc_parent
        joint_ok = bool(((df["item_acc1"] == 1) <= (df["parent_acc1"] == 1)).all())
        lines.append(
            f"| {SHORT[method]} | {len(df):,} | {df['gold_parent_key'].nunique()} | {f4(item)} | "
            f"{fci(ci(q[:, 0]))} | {fci(ci(c[:, 0]))} | {f4(parent)} | {fci(ci(q[:, 1]))} | "
            f"{fci(ci(c[:, 1]))} | {fd(gap)} | {fci(ci(q[:, 1] - q[:, 0]), True)} | {f4(d)} | "
            + (fci(ci(d_draws)) if joint_ok else "n/a (item hit without parent hit)")
            + f" | {f4(metrics_dual_overall(meta, 'item'))} / {f4(metrics_dual_overall(meta, 'parent'))} |"
        )
    write(OUT / "identity.md", lines + sources(runs, [("texto", m) for m in METHODS]))


def write_l1_deltas(runs: dict) -> None:
    rows = []
    for method in METHODS:
        for condition in L1_CONDITIONS:
            joined, unmatched = paired_with_identity(runs, "single_texto", method, condition)
            vals = joined[["item_acc1", "parent_acc1", "id_item_acc1", "id_parent_acc1"]].to_numpy()
            label = f"l1|{method}|{condition}"
            q = boot_query(vals, label)
            c = boot_cluster(vals, joined["gold_parent_key"].to_numpy(), label)
            mean = vals.mean(axis=0)
            row = dict(method=method, condition=condition, n=len(joined), unmatched=unmatched,
                       concepts=joined["gold_parent_key"].nunique(), leaves=joined["gold_item_key"].nunique())
            for level, a, b in (("item", 0, 2), ("parent", 1, 3)):
                dq, dc = q[:, a] - q[:, b], c[:, a] - c[:, b]
                row[level] = dict(
                    cond=mean[a], cond_ci=ci(q[:, a]), ident=mean[b], ident_ci=ci(q[:, b]),
                    delta=mean[a] - mean[b], dq=ci(dq), dc=ci(dc), p=boot_p(dq),
                )
            rows.append(row)

    family = [(i, lvl) for i in range(len(rows)) for lvl in ("item", "parent")]
    ps = [rows[i][lvl]["p"] for i, lvl in family]
    for (i, lvl), ph, pb in zip(family, holm(ps), bh(ps)):
        rows[i][lvl]["holm"], rows[i][lvl]["bh"] = ph, pb

    lines = header(
        "L1 conditions, paired against identity (dev)",
        [
            "Each `single_texto` query of the condition is joined to the `texto` run's row whose",
            "`query_item_key` equals its `gold_item_key` (same method, same gold leaf); delta =",
            "condition − identity, per query. CIs: paired query-level bootstrap and",
            "concept-clustered bootstrap (resampling `gold_parent_key`). p-values are two-sided",
            f"query-level bootstrap p; Holm and BH adjust over the {len(ps)} deltas in this file",
            "(5 methods × 2 conditions × 2 levels). `unmatched` counts queries whose gold leaf had",
            "no identity row; they are excluded from every column.",
        ],
    )
    for level in ("item", "parent"):
        lines += [
            f"## {level}-level Acc@1",
            "",
            "| method | condition | n queries | n concepts | n leaves | unmatched | condition Acc@1 | "
            "CI | identity Acc@1 (same leaves) | CI | delta | CI (paired, query) | CI (clustered, concept) | "
            "p | p Holm | p BH |",
            "|---|---|---:|---:|---:|---:|---:|---|---:|---|---:|---|---|---:|---:|---:|",
        ]
        for r in rows:
            s = r[level]
            lines.append(
                f"| {SHORT[r['method']]} | `{r['condition']}` | {r['n']} | {r['concepts']} | {r['leaves']} | "
                f"{r['unmatched']} | {f4(s['cond'])} | {fci(s['cond_ci'])} | {f4(s['ident'])} | "
                f"{fci(s['ident_ci'])} | {fd(s['delta'])} | {fci(s['dq'], True)} | {fci(s['dc'], True)} | "
                f"{fp(s['p'])} | {fp(s['holm'])} | {fp(s['bh'])} |"
            )
        lines.append("")

    lines += [
        "## Collapse gap and conditional discrimination on the condition",
        "",
        "Δ = parent − item Acc@1; D = P(item correct | parent correct); both on the condition",
        "queries, with the identity values of the same leaves beside them. Point estimates.",
        "",
        "| method | condition | Δ condition | Δ identity | D condition | D identity |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        joined, _ = paired_with_identity(runs, "single_texto", r["method"], r["condition"])
        d_c = joined.loc[joined["parent_acc1"] == 1, "item_acc1"].mean()
        d_i = joined.loc[joined["id_parent_acc1"] == 1, "id_item_acc1"].mean()
        lines.append(
            f"| {SHORT[r['method']]} | `{r['condition']}` | {fd(r['parent']['cond'] - r['item']['cond'])} | "
            f"{fd(r['parent']['ident'] - r['item']['ident'])} | {f4(d_c)} | {f4(d_i)} |"
        )
    keys = [(qs, m) for m in METHODS for qs in ("texto", "single_texto")]
    write(OUT / "l1_deltas.md", lines + sources(runs, keys))


def write_structured_vs_bm25(runs: dict) -> None:
    write_contrasts(
        runs,
        CONTRASTS,
        "structured_vs_bm25.md",
        "structured − BM25 on the L1 conditions (dev)",
        [("single_texto", m) for m in METHODS if m != "bge_m3_colbert__OE"],
    )


def write_colbert_vs_bm25(runs: dict) -> None:
    write_contrasts(
        runs,
        COLBERT_CONTRASTS,
        "colbert_vs_bm25.md",
        "ColBERT − BM25 on the L1 conditions (dev)",
        [("single_texto", m) for m in ("bge_m3_colbert__OE", *SCORE_TIE_METHODS[:2])],
        extra_how=[
            "S2 read ColBERT's L1 advantage from point estimates alone; these are its intervals.",
        ],
    )


def write_contrasts(runs: dict, contrasts: tuple, filename: str, title: str,
                    source_keys: list, extra_how: list[str] = ()) -> None:
    rows = []
    for condition in L1_CONDITIONS:
        for treat, ref in contrasts:
            a = runs[("single_texto", treat)]["_perquery"]
            b = runs[("single_texto", ref)]["_perquery"]
            a = a[a["condition"] == condition]
            joined = a[["query_item_key", "gold_parent_key", *METRIC_COLS]].merge(
                b[["query_item_key", *METRIC_COLS]], on="query_item_key", suffixes=("_t", "_r"),
                how="inner", validate="one_to_one",
            )
            if len(joined) != len(a):
                raise SystemExit(f"{condition}: {treat} vs {ref} pairs {len(joined)} of {len(a)} queries")
            vals = joined[["item_acc1_t", "parent_acc1_t", "item_acc1_r", "parent_acc1_r"]].to_numpy()
            label = f"xmethod|{condition}|{treat}|{ref}"
            q = boot_query(vals, label)
            c = boot_cluster(vals, joined["gold_parent_key"].to_numpy(), label)
            mean = vals.mean(axis=0)
            row = dict(condition=condition, treat=treat, ref=ref, n=len(joined),
                       concepts=joined["gold_parent_key"].nunique())
            for level, i, j in (("item", 0, 2), ("parent", 1, 3)):
                dq, dc = q[:, i] - q[:, j], c[:, i] - c[:, j]
                row[level] = dict(t=mean[i], r=mean[j], delta=mean[i] - mean[j], dq=ci(dq), dc=ci(dc),
                                  p=boot_p(dq))
            rows.append(row)

    for level in ("item", "parent"):
        ps = [r[level]["p"] for r in rows]
        for r, ph, pb in zip(rows, holm(ps), bh(ps)):
            r[level]["holm"], r[level]["bh"] = ph, pb

    lines = header(
        title,
        [
            "Paired on identical `query_item_key` within `single_texto`; delta = treatment −",
            "reference, per query. CIs: paired query-level bootstrap and concept-clustered bootstrap.",
            "`CI entirely above 0` is `true` when the lower bound of the respective CI is > 0.",
            f"Holm and BH adjust over the {len(rows)} contrasts of each level separately.",
            *extra_how,
        ],
    )
    for level in ("item", "parent"):
        lines += [
            f"## {level}-level Acc@1",
            "",
            "| condition | treatment | reference | n queries | n concepts | treatment Acc@1 | reference Acc@1 | "
            "delta | CI (paired, query) | CI entirely above 0 (query) | CI (clustered, concept) | "
            "CI entirely above 0 (clustered) | p | p Holm | p BH |",
            "|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|---:|---:|---:|",
        ]
        for r in rows:
            s = r[level]
            lines.append(
                f"| `{r['condition']}` | {SHORT[r['treat']]} | {SHORT[r['ref']]} | {r['n']} | {r['concepts']} | "
                f"{f4(s['t'])} | {f4(s['r'])} | {fd(s['delta'])} | {fci(s['dq'], True)} | "
                f"{str(s['dq'][0] > 0).lower()} | {fci(s['dc'], True)} | {str(s['dc'][0] > 0).lower()} | "
                f"{fp(s['p'])} | {fp(s['holm'])} | {fp(s['bh'])} |"
            )
        lines.append("")
    write(OUT / filename, lines + sources(runs, source_keys))


def write_stacked(runs: dict) -> None:
    lines = header(
        "stacked (`all_combined`, dev)",
        [
            "Acc@1 per method with query-level and concept-clustered bootstrap 95 % CIs, and the",
            "paired delta against the `texto` identity rows of the same gold leaves (joined on",
            "`gold_item_key`). Dose is `distinct_modification_count` (D-025).",
        ],
    )
    lines += [
        "## Overall",
        "",
        "| method | n queries | n concepts | unmatched | item Acc@1 | CI (query) | CI (concept) | identity item | "
        "item delta | CI (paired, query) | CI (clustered) | parent Acc@1 | CI (query) | CI (concept) | "
        "identity parent | parent delta | CI (paired, query) | CI (clustered) | metrics_dual item / parent |",
        "|---|---:|---:|---:|---:|---|---|---:|---:|---|---|---:|---|---|---:|---:|---|---|---|",
    ]
    dose_rows = []
    for method in METHODS:
        joined, unmatched = paired_with_identity(runs, "stacked_texto", method, None)
        cols = ["item_acc1", "parent_acc1", "id_item_acc1", "id_parent_acc1"]
        vals = joined[cols].to_numpy()
        label = f"stacked|{method}"
        q = boot_query(vals, label)
        c = boot_cluster(vals, joined["gold_parent_key"].to_numpy(), label)
        mean = vals.mean(axis=0)
        meta = runs[("stacked_texto", method)]
        lines.append(
            f"| {SHORT[method]} | {len(joined):,} | {joined['gold_parent_key'].nunique()} | {unmatched} | "
            f"{f4(mean[0])} | {fci(ci(q[:, 0]))} | {fci(ci(c[:, 0]))} | {f4(mean[2])} | {fd(mean[0] - mean[2])} | "
            f"{fci(ci(q[:, 0] - q[:, 2]), True)} | {fci(ci(c[:, 0] - c[:, 2]), True)} | "
            f"{f4(mean[1])} | {fci(ci(q[:, 1]))} | {fci(ci(c[:, 1]))} | {f4(mean[3])} | {fd(mean[1] - mean[3])} | "
            f"{fci(ci(q[:, 1] - q[:, 3]), True)} | {fci(ci(c[:, 1] - c[:, 3]), True)} | "
            f"{f4(metrics_dual_overall(meta, 'item'))} / {f4(metrics_dual_overall(meta, 'parent'))} |"
        )
        for dose, grp in joined.groupby("distinct_modification_count", sort=True):
            gv = grp[cols].to_numpy()
            gq = boot_query(gv, f"{label}|dose={dose}")
            gm = gv.mean(axis=0)
            dose_rows.append(
                f"| {SHORT[method]} | {dose} | {len(grp):,} | {grp['gold_parent_key'].nunique()} | "
                f"{f4(gm[0])} | {fci(ci(gq[:, 0]))} | {f4(gm[2])} | {fd(gm[0] - gm[2])} | "
                f"{fci(ci(gq[:, 0] - gq[:, 2]), True)} | {f4(gm[1])} | {fd(gm[1] - gm[3])} | "
                f"{fci(ci(gq[:, 1] - gq[:, 3]), True)} |"
            )
    lines += [
        "",
        "## By dose (`distinct_modification_count`)",
        "",
        "Query-level paired bootstrap only. Strata are not a balanced crossing of modification types.",
        "",
        "| method | dose | n queries | n concepts | item Acc@1 | CI | identity item | item delta | CI (paired) | "
        "parent Acc@1 | parent delta | CI (paired) |",
        "|---|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---|",
        *dose_rows,
    ]
    keys = [(qs, m) for m in METHODS for qs in ("texto", "stacked_texto")]
    write(OUT / "stacked.md", lines + sources(runs, keys))


def _stage_summary(st: pd.DataFrame) -> dict:
    s1 = st[st["stage1_correct"]]
    axes = s1["axes"].astype(float)
    rec = s1["recovered"].astype(float)
    return {
        "n": len(st),
        "s1_acc": st["stage1_correct"].mean(),
        "n_s1": len(s1),
        "all_axes": (rec == axes).mean() if len(s1) else float("nan"),
        "axis_rec_micro": rec.sum() / axes.sum() if axes.sum() else float("nan"),
        "axis_rec_macro": (rec / axes.where(axes > 0)).mean() if len(s1) else float("nan"),
        "abstained": int(s1["abstained"].sum()),
        "q_abstained": int((s1["abstained"] > 0).sum()),
        "misread": int(s1["misread"].sum()),
        "q_misread": int((s1["misread"] > 0).sum()),
        "gold_in": st["stage3_gold_in_match"].mean(),
        "gold_in_s1": s1["stage3_gold_in_match"].mean() if len(s1) else float("nan"),
        "unique": st["stage3_unique_gold"].mean(),
        "no_match": (st["stage3_matched"] == 0).mean(),
        "consistent": st["consistent"].mean(),
        "n_inconsistent": int((~st["consistent"]).sum()),
        "item_acc1": st["item_acc1"].mean(),
        "parent_acc1": st["parent_acc1"].mean(),
    }


def write_structured_stages(runs: dict) -> None:
    lines = header(
        "structured pipeline stage decomposition (dev)",
        [
            "Summarises `logs/S2/stages/{queryset}__{method}.parquet` (derived by",
            "`src/utils/structured_stages.py`), joined on `query_item_key` to the run's own",
            "per-query Acc@1. Stage-2 columns are computed over queries whose Stage-1 parent is",
            "correct: `all axes` = share recovering every gold axis; axis recovery micro = Σ",
            "recovered / Σ axes, macro = mean per-query recovered / axes; abstained / misread are",
            "axis counts, with the number of queries having ≥ 1 in parentheses. Stage-3 rates are",
            "over all queries unless marked `| S1 ok`. `consistent` = the re-derivation reproduces",
            "the run's rank 1.",
        ],
    )
    lines += [
        "| queryset | method | condition | n | run item Acc@1 | run parent Acc@1 | Stage-1 parent Acc@1 | "
        "n S1 ok | all axes recovered | axis recovery micro | macro | abstained axes (q) | "
        "misread axes (q) | Stage-3 gold in match | gold in match \\| S1 ok | unique gold | no match | "
        "consistent | n inconsistent |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    extra = []
    for queryset in QUERYSETS:
        for method in STRUCTURED:
            path = STAGES / f"{queryset}__{method}.parquet"
            if not path.is_file():
                raise SystemExit(f"missing stage decomposition: {path}")
            extra.append((str(path.relative_to(REPO)).replace("\\", "/"), path))
            stages = pd.read_parquet(path)
            run = runs[(queryset, method)]["_perquery"]
            st = stages.merge(run[["query_item_key", "condition", *METRIC_COLS]], on="query_item_key",
                              how="inner", validate="one_to_one")
            if len(st) != len(run) or len(st) != len(stages):
                raise SystemExit(f"{path.name}: {len(stages)} stage rows, {len(run)} run rows, {len(st)} joined")
            groups = [("all", st)]
            if queryset == "single_texto":
                groups += sorted(st.groupby("condition"), key=lambda kv: kv[0])
            for condition, grp in groups:
                s = _stage_summary(grp)
                lines.append(
                    f"| {queryset} | {SHORT[method]} | `{condition}` | {s['n']:,} | {f4(s['item_acc1'])} | "
                    f"{f4(s['parent_acc1'])} | {f4(s['s1_acc'])} | {s['n_s1']:,} | {f4(s['all_axes'])} | "
                    f"{f4(s['axis_rec_micro'])} | {f4(s['axis_rec_macro'])} | {s['abstained']:,} ({s['q_abstained']:,}) | "
                    f"{s['misread']:,} ({s['q_misread']:,}) | {f4(s['gold_in'])} | {f4(s['gold_in_s1'])} | "
                    f"{f4(s['unique'])} | {f4(s['no_match'])} | {f4(s['consistent'])} | {s['n_inconsistent']} |"
                )
    keys = [(qs, m) for qs in QUERYSETS for m in STRUCTURED]
    write(OUT / "structured_stages.md", lines + sources(runs, keys, extra))


def write_failures(runs: dict) -> None:
    fail = pd.read_csv(FAILURES)
    lines = header(
        "classified BM25-params misses (work item 6)",
        [
            "Counts from `docs/synthetic-oe/sprints/SPRINT_S2_FAILURES.csv` (the seeded 30-per-condition",
            "sample of `bm25_unigram_params` misses on `single_texto`). `n misses in condition` is the",
            "population the sample was drawn from, as recorded in the CSV.",
        ],
    )
    lines += [
        "## Condition × classification",
        "",
        "| condition | n misses in condition | classification | n sampled |",
        "|---|---:|---|---:|",
    ]
    for (condition, cls), grp in fail.groupby(["condition", "classification"], sort=True):
        pop = ", ".join(str(v) for v in sorted(grp["n_misses_in_condition"].unique()))
        lines.append(f"| `{condition}` | {pop} | {cls} | {len(grp)} |")

    flags = ["thousands_dot_artefact", "token_doubling", "top1_same_parent"]
    fail = fail.assign(gold_out_of_top100=fail["gold_rank"].isna())
    flags.append("gold_out_of_top100")
    lines += [
        "",
        "## Co-present flags",
        "",
        "Rows flagged `True` per condition × classification. `gold_out_of_top100` = empty `gold_rank`.",
        "",
        "| condition | classification | n | " + " | ".join(f"`{f}`" for f in flags) + " |",
        "|---|---|---:|" + "---:|" * len(flags),
    ]
    for (condition, cls), grp in fail.groupby(["condition", "classification"], sort=True):
        counts = " | ".join(str(int(grp[f].astype(str).str.lower().eq("true").sum())) for f in flags)
        lines.append(f"| `{condition}` | {cls} | {len(grp)} | {counts} |")

    # Cross-check: every sampled query is a miss in the stamped bm25_unigram_params run.
    run = runs[("single_texto", METHODS[0])]["_perquery"].set_index("query_item_key")
    present = fail["query_item_key"].isin(run.index)
    misses = run.loc[fail.loc[present, "query_item_key"], "item_acc1"].eq(0)
    pop = run[run["item_acc1"] == 0].groupby("condition").size()
    lines += [
        "",
        "## Cross-check against the run",
        "",
        f"Sampled query ids found in `{runs[('single_texto', METHODS[0])]['run_id']}`: "
        f"{int(present.sum())} of {len(fail)}; of those, item-level misses in the run: {int(misses.sum())}.",
        "",
        "| condition | misses in run | n misses in condition (CSV) |",
        "|---|---:|---:|",
    ]
    for condition in L1_CONDITIONS:
        csv_pop = ", ".join(str(v) for v in sorted(fail.loc[fail["condition"] == condition, "n_misses_in_condition"].unique()))
        lines.append(f"| `{condition}` | {int(pop.get(condition, 0))} | {csv_pop or '—'} |")
    write(OUT / "failures.md", lines + sources(runs, [("single_texto", METHODS[0])],
                                              [("docs/synthetic-oe/sprints/SPRINT_S2_FAILURES.csv", FAILURES)]))


def _iter_top100(run_dir: Path):
    """Stream a run's ranked candidate lists, as the run wrote them."""
    import gzip

    with gzip.open(run_dir / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


#: Why an identity query failed, in the order the classifier tries them. The token comparison
#: is over the analysed multiset of the indexed field, so it is the view BM25 itself has.
MISS_CLASSES = (
    ("other_concept", "rank 1 is outside the gold's concept"),
    ("duplicate_texto", "gold and rank 1 have byte-identical `texto`"),
    ("identical_tokens", "same token multiset: the scores tie and the order decides"),
    ("rank1_superset", "rank 1 has every token of the gold and more"),
    ("gold_superset", "the gold has every token of rank 1 and more"),
    ("both_differ", "each has tokens the other lacks"),
)


def write_identity_misses(runs: dict) -> None:
    """Anatomy of the identity misses of the two BM25 arms (S2 audit, F8).

    The S2 report stated the 662 / 3,260 split in prose. This derives the whole breakdown,
    because the reading of gate G1 rests on it: ties are only part of the story.
    """
    import collections
    import re

    from sklearn.feature_extraction.text import CountVectorizer

    corpus = pd.read_parquet(CORPUS, columns=["item_key", "parent_key", "text", "text_word"])
    analyse = CountVectorizer(
        lowercase=True, token_pattern=r"(?u)\b\w+\b", strip_accents="unicode"
    ).build_analyzer()
    tokens = {k: collections.Counter(analyse(t)) for k, t in zip(corpus.item_key, corpus.text_word)}
    parent = dict(zip(corpus.item_key, corpus.parent_key))
    texto = dict(zip(corpus.item_key, corpus.text))
    methods = ("bm25_unigram__k1-0.60__b-0.35__OE", "bm25_unigram_params__k1-0.60__b-0.35__OE")

    lines = header(
        "identity misses of the BM25 arms (`texto`, dev)",
        [
            "Every identity miss classified by comparing the gold's analysed token multiset with",
            "rank 1's, on the indexed field, using the index's own token pattern `(?u)\\b\\w+\\b`",
            "with accents stripped. Classes are exclusive and tried in table order.",
            "`differing parameter` counts the `texto` lines present in the gold and absent from",
            "rank 1, by the label before the colon.",
        ],
    )
    lines += [
        "| class | what it means |",
        "|---|---|",
        *[f"| `{name}` | {what} |" for name, what in MISS_CLASSES],
        "",
        "## Misses by class",
        "",
        "| method | n queries | n misses | "
        + " | ".join(f"`{name}`" for name, _ in MISS_CLASSES)
        + " | gold at rank 2 | gold outside top 100 |",
        "|---|---:|---:|" + "---:|" * (len(MISS_CLASSES) + 2),
    ]
    labels: dict[str, collections.Counter] = {}
    for method in methods:
        counts = collections.Counter()
        label_counts = collections.Counter()
        n = rank2 = outside = 0
        for record in _iter_top100(RUNS / "texto" / method):
            n += 1
            gold, top = record["gold_item_key"], record["candidates"][0]["index_item_key"]
            if gold == top:
                continue
            position = next((c["rank"] for c in record["candidates"] if c["index_item_key"] == gold), None)
            rank2 += position == 2
            outside += position is None
            gold_tokens, top_tokens = tokens[gold], tokens[top]
            only_gold, only_top = gold_tokens - top_tokens, top_tokens - gold_tokens
            if parent[top] != parent[gold]:
                cls = "other_concept"
            elif texto[gold] == texto[top]:
                cls = "duplicate_texto"
            elif not only_gold and not only_top:
                cls = "identical_tokens"
            elif not only_gold:
                cls = "rank1_superset"
            elif not only_top:
                cls = "gold_superset"
            else:
                cls = "both_differ"
            counts[cls] += 1
            gold_lines = [l.strip().rstrip(".") for l in texto[gold].split("\n")]
            top_lines = [l.strip().rstrip(".") for l in texto[top].split("\n")]
            for line in gold_lines:
                if line not in top_lines:
                    label_counts[line.split(":")[0] if ":" in line else "(description)"] += 1
        labels[method] = label_counts
        lines.append(
            f"| {SHORT[method]} | {n:,} | {sum(counts.values()):,} | "
            + " | ".join(f"{counts[name]:,}" for name, _ in MISS_CLASSES)
            + f" | {rank2:,} | {outside:,} |"
        )

    lines += [
        "",
        "## Which `texto` line separates the gold from rank 1",
        "",
        "One row per parameter label; a miss with two differing lines counts in both.",
        "",
        "| method | differing line | n misses |",
        "|---|---|---:|",
    ]
    for method in methods:
        for label, count in labels[method].most_common(8):
            lines.append(f"| {SHORT[method]} | {label} | {count:,} |")

    duplicates = collections.Counter(texto.values())
    repeated = sum(c for c in duplicates.values() if c > 1)
    group_size = {k: duplicates[t] for k, t in texto.items()}
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for key, text in texto.items():
        if duplicates[text] > 1:
            groups[text].append(key)
    spread = collections.Counter(
        (
            "several concepts" if len({parent[k] for k in members}) > 1 else parent[members[0]],
            len(members),
        )
        for members in groups.values()
    )
    dev = list(runs[("texto", methods[0])]["_perquery"]["query_item_key"])
    ceiling = sum(1.0 / group_size[k] for k in dev) / len(dev)
    lines += [
        "",
        "## The ceiling a `texto`-only method can reach",
        "",
        f"Leaves whose `texto` is not unique: {repeated:,} of {len(texto):,} "
        f"({repeated / len(texto):.4f}), in {sum(1 for c in duplicates.values() if c > 1):,} groups; "
        f"{sum(1 for k in dev if group_size[k] > 1):,} of them are dev identity queries. Nothing that "
        "reads only `texto` can separate a group, so its expected identity Acc@1 under a uniform "
        f"draw inside each group is **{ceiling:.4f}**, not 1.0. The column below counts how many of "
        "each method's identity misses are leaves in such a group.",
        "",
        "| method | identity misses | of them, duplicate-`texto` leaves | other misses |",
        "|---|---:|---:|---:|",
    ]
    concept_rows = [
        f"| `{concept}` | {size} | {count:,} | {count * size:,} |"
        for (concept, size), count in sorted(spread.items())
    ]
    for method in METHODS:
        missed = [
            r["gold_item_key"]
            for r in _iter_top100(RUNS / "texto" / method)
            if r["candidates"][0]["index_item_key"] != r["gold_item_key"]
        ]
        duplicated = sum(1 for k in missed if group_size[k] > 1)
        lines.append(
            f"| {SHORT[method]} | {len(missed):,} | {duplicated:,} | {len(missed) - duplicated:,} |"
        )

    lines += [
        "",
        "Where those groups sit. A group spanning two concepts would cap parent-level Acc@1 as",
        "well; one inside a single concept caps only the item level.",
        "",
        "| concept | group size | n groups | n leaves |",
        "|---|---:|---:|---:|",
        *concept_rows,
    ]
    write(OUT / "identity_misses.md", lines + sources(runs, [("texto", m) for m in methods],
                                                     [("data/processed/OE_long_feats.parquet", CORPUS)]))


def write_tiebreak(runs: dict) -> None:
    """Rank-1 ties in every family, not only the structured one (S2 audit, F6).

    `Acc@1 (random tie-break)` is the expectation over a uniform draw inside the rank-1 tie:
    a query contributes 1/|tie| when the gold is in the tie set and 0 otherwise. It is exact,
    so it needs no seed. The gap to the run's own Acc@1 is what candidate order is worth.
    """
    lines = header(
        "rank-1 ties and what order is worth (dev)",
        [
            "For the lexical and late-interaction arms a tie is an exact equality of the run's",
            "own scores at rank 1. The structured arms encode their order in the score (tier 1",
            "descends by 1e-4), so their tie set is Stage 3's matched-key set, read from",
            "`logs/S2/stages/`. Point estimates; `Acc@1 (random tie-break)` is an expectation,",
            "not a simulation.",
        ],
    )
    lines += [
        "| queryset | method | n queries | queries tied at rank 1 | share tied | mean tie size | "
        "gold in the tie set | run Acc@1 | Acc@1 (random tie-break) | difference |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for queryset in QUERYSETS:
        for method in METHODS:
            run = runs[(queryset, method)]["_perquery"]
            observed = float(run["item_acc1"].mean())
            if method in SCORE_TIE_METHODS:
                tied = tie_sizes = gold_in = 0
                expected = 0.0
                n = 0
                for record in _iter_top100(RUNS / queryset / method):
                    n += 1
                    best = record["candidates"][0]["score"]
                    tie = [c for c in record["candidates"] if c["score"] == best]
                    in_tie = any(c["index_item_key"] == record["gold_item_key"] for c in tie)
                    if len(tie) > 1:
                        tied += 1
                        tie_sizes += len(tie)
                    gold_in += in_tie
                    expected += (1.0 / len(tie)) if in_tie else 0.0
                expected /= n
                mean_tie = tie_sizes / tied if tied else float("nan")
            else:
                stages = pd.read_parquet(STAGES / f"{queryset}__{method}.parquet")
                matched = stages["stage3_matched"].to_numpy(dtype=float)
                gold_in_match = stages["stage3_gold_in_match"].to_numpy(dtype=bool)
                # A query with no Stage-3 match never reaches a tier-1 tie; it is counted as
                # untied here and contributes its run outcome, not an expectation.
                has_tier1 = matched > 0
                n = len(stages)
                tied = int((matched > 1).sum())
                tie_sizes = float(matched[matched > 1].sum())
                gold_in = int(gold_in_match.sum())
                mean_tie = tie_sizes / tied if tied else float("nan")
                contrib = np.where(has_tier1 & gold_in_match, 1.0 / np.where(matched > 0, matched, 1), 0.0)
                fallback = run.set_index("query_item_key").loc[stages["query_item_key"], "item_acc1"].to_numpy()
                expected = float(np.where(has_tier1, contrib, fallback).mean())
            lines.append(
                f"| {queryset} | {SHORT[method]} | {n:,} | {tied:,} | {tied / n:.4f} | "
                + (f"{mean_tie:.2f}" if tied else "—")
                + f" | {gold_in / n:.4f} | {f4(observed)} | {f4(expected)} | {fd(expected - observed)} |"
            )
    extra = [
        (f"logs/S2/stages/{qs}__{m}.parquet", STAGES / f"{qs}__{m}.parquet")
        for qs in QUERYSETS
        for m in STRUCTURED
    ]
    write(OUT / "tiebreak.md", lines + sources(runs, [(qs, m) for qs in QUERYSETS for m in METHODS], extra))


def write_provenance(runs: dict) -> None:
    lines = header(
        "run provenance",
        [
            "Every S2 run's four-part stamp, as the run recorded it at execution time. Digests are",
            "truncated; full values are in each run's `run_meta.json`.",
        ],
    )
    lines += [
        "| run_id | queries | split | config SHA-256 | code commit | code dirty | query-set SHA-256 | "
        "query table | gold column | K | created (UTC) |",
        "|---|---:|---|---|---|---|---|---|---|---:|---|",
    ]
    for queryset in QUERYSETS:
        for method in METHODS:
            m = runs[(queryset, method)]
            lines.append(
                f"| `{m['run_id']}` | {m['queries']:,} | {m['split']} | `{m['config_sha256'][:16]}` | "
                f"`{m['code_commit'][:7]}` | {str(m.get('code_dirty')).lower()} | `{m['query_set_sha256'][:16]}` | "
                f"`{Path(m['query_path']).name}` | `{m['gold_column']}` | {m['K']} | {m.get('created_utc', '')} |"
            )
    commits = sorted({m["code_commit"] for m in runs.values()})
    dirty = sorted(m["run_id"] for m in runs.values() if m.get("code_dirty"))
    lines += [
        "",
        f"Distinct code commits: {', '.join(f'`{c[:7]}`' for c in commits)}. "
        f"Runs stamped dirty: {', '.join(f'`{d}`' for d in dirty) or 'none'}.",
    ]
    write(OUT / "run_provenance.md", lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    write_provenance(runs)
    write_identity(runs)
    write_identity_misses(runs)
    write_l1_deltas(runs)
    write_structured_vs_bm25(runs)
    write_colbert_vs_bm25(runs)
    write_tiebreak(runs)
    write_stacked(runs)
    write_structured_stages(runs)
    write_failures(runs)
    print(f"{len(runs)} runs -> {OUT.relative_to(REPO)}")
    for path in sorted(OUT.glob("*.md")):
        print(f"  {path.name} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
