"""Build docs/synthetic-oe/results/S5/ — S5 work item 5 (design frozen at `432b39e`, + A1).

E1 ablation, Track B: the published rules pipeline (valuenorm; the faithful port for comparability)
and the oracle-extraction bound, × nine single modification types on OE dev, each query paired with
the same arm's identity result on its own gold leaf, and set against three reference arms of S4
(`bm25_unigram`, its oracle twin `bm25_unigram_params`, `bge_m3_colbert`) on the same queries.

- `ceilings.md` (T1) — the three structured arms' identity ceilings.
- `profile_item.md` (T2) — arm × type, item level, as run **and** tie-free.
- `profile_parent.md` (T3) — the same at parent level, plus the collapse quantities of H1.
- `stages.md` (T4) — Stage 1 / 2 / 3 per arm and type, re-derived from each run; match size; the
  decimal artefact counts.
- `contrasts.md` (T5) — each structured arm against each reference arm: paired difference at
  identity, under modification, and the difference-in-differences; tie-free and as run.
- `predictions.md` (T6) — Q1–Q3 read under the frozen rule, and G2 read from Q1.
- `run_provenance.md` (T7) — every run read.

**Tie-free Acc@1** (design, D-028). The expectation of a uniform tie-break over the query's rank-1
tied set: 1/|set| when the gold is in it, else 0. For a structured arm the set is Stage 3's match;
when Stage 3 matches nothing, rank 1 is the Stage-1 family's first key in schema order, and the set
is the family. For a score-based arm it is the candidates whose score equals rank 1's; a tie filling
all of the top-100 has an unknown size and is counted (`truncated`), its size taken as the 100 seen.

**Population.** S4's: item level scores dev `single_texto` minus D-033 golds and the P7 query;
parent level scores every query. **Every number in the prose is interpolated**
(`tests/test_generated_prose.py`).

    python src/utils/build_results_s5.py
"""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from pipeline.catalog_lookup import CatalogLookup  # noqa: E402
from pipeline.param_extractor_oracle import OracleParamsExtractor  # noqa: E402
from pipeline.param_extractor_rules import RuleBasedParamExtractor  # noqa: E402
from utils.build_results_s2 import (  # noqa: E402
    ALPHA, B, SEED, bh, boot_cluster, boot_p, boot_query, ci, f4, fci, fd, fp, holm, write,
)
from utils.build_results_s4 import (  # noqa: E402
    _DECIMAL, AMENDMENT_EXCLUDED as S4_EXCLUDED, FEW_CLUSTERS, LAYERS, TYPES, cell, collapse, reading,
)
from utils.provenance import sha256_file  # noqa: E402

RUNS = REPO / "runs" / "OE"
DATA = REPO / "data" / "processed"
SIDECAR = DATA / "OE_duplicate_texto_groups.json"
SCHEMA = DATA / "OE_concept_schema.json"
LONG_NORM = DATA / "OE_long_norm.parquet"
QUERY_TABLES = {"texto": DATA / "OE_long_feats.parquet", "single_texto": DATA / "OE_single_texto_feats.parquet"}
SINGLE_JSON = DATA / "OE_single_texto.json"
CORPUS_JSON = DATA / "OE_texto.json"
OUT = REPO / "docs" / "synthetic-oe" / "results" / "S5"
GENERATOR = "src/utils/build_results_s5.py"

#: (run directory, short name, oracle, structured)
ARMS = [
    ("structured_pipeline_rules_valuenorm__OE", "rules_valuenorm", False, True),
    ("structured_pipeline_rules__OE", "rules_faithful", False, True),
    ("structured_pipeline_oracleparams_valuenorm__OE", "oracleparams", True, True),
    ("bm25_unigram__k1-0.60__b-0.35__OE", "bm25_unigram", False, False),
    ("bm25_unigram_params__k1-0.60__b-0.35__OE", "bm25_unigram_params", True, False),
    ("bge_m3_colbert__OE", "bge_m3_colbert", False, False),
]
DIR = {short: d for d, short, _, _ in ARMS}
ORACLE = {short for _, short, o, _ in ARMS if o}
STRUCTURED = [short for _, short, _, s in ARMS if s]
REFERENCE = [short for _, short, _, s in ARMS if not s]
TWIN = {"oracleparams": "rules_valuenorm", "bm25_unigram_params": "bm25_unigram"}

#: Four `synonym_label` dev queries differ from their gold only in letter case (DATASET_DEFECTS P8,
#: D-044). Every `synonym_label` cell is shown with and without them.
P8_DEV = {"OED010bkabc_syn_85a4f552cd1b", "OED030babca_syn_609ea3a72274",
          "OED050bcbdc_syn_c59e212d9862", "OED080bhbda_syn_7575e67f784b"}
NO_P8 = "synonym_label, without P8"
SCOPES = TYPES + [NO_P8] + list(LAYERS) + ["all"]
LEVELS = ("item", "parent")

#: The P7 query, excluded at item level by S4 design A2 (D-043); S5 inherits S4's population.
EXCLUDED = {k: {**v, "amendment": "S4 design A2, D-043"} for k, v in S4_EXCLUDED.items()}

#: The registered predictions (design, "Design constraints"). kind: mod | did.
PREDICTIONS = [
    ("Q1", "H3 inversion, published method (confirmatory)", "mod", "rules_valuenorm", "bm25_unigram",
     ["L1", "unit_conversion", "num_to_text"]),
    ("Q2", "H3 bound (blind)", "mod", "oracleparams", "bm25_unigram", ["L1", "unit_conversion", "num_to_text"]),
    ("Q3", "H3 gap closes (confirmatory)", "did", "rules_valuenorm", "bm25_unigram", ["L1", "L2", "L3"]),
]


# --------------------------------------------------------------------------- inputs


def meta(queryset: str, method: str) -> dict:
    return json.loads((RUNS / queryset / method / "run_meta.json").read_text(encoding="utf-8"))


def perquery(queryset: str, method: str) -> pd.DataFrame:
    return pd.read_parquet(RUNS / queryset / method / "results_perquery.parquet")


def duplicated() -> set[str]:
    return {m for g in json.loads(SIDECAR.read_text(encoding="utf-8"))["groups"].values() for m in g}


def iter_top100(queryset: str, method: str):
    with gzip.open(RUNS / queryset / method / "results_top100.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


class Stages:
    """Re-derives Stage 1–3 of a structured run from its own rank 1 and deterministic code."""

    def __init__(self):
        corpus = pd.read_parquet(LONG_NORM, columns=["item_key", "parent_key", "parameters"])
        self.parent_of = dict(zip(corpus["item_key"], corpus["parent_key"]))
        self.params_of = dict(zip(corpus["item_key"], corpus["parameters"]))
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.rules = RuleBasedParamExtractor(SCHEMA)
        self.oracle = OracleParamsExtractor(SCHEMA)
        self.catalogs = {m: CatalogLookup(SCHEMA, LONG_NORM, value_match=m) for m in ("literal", "normalized")}
        self.records = {qs: None for qs in QUERY_TABLES}

    def _records(self, queryset: str) -> dict:
        if self.records[queryset] is None:
            t = pd.read_parquet(QUERY_TABLES[queryset], columns=["item_key", "parameters_norm"])
            self.records[queryset] = dict(zip(t["item_key"].astype(str), t["parameters_norm"]))
        return self.records[queryset]

    def family(self, parent: str) -> list[str]:
        return [k for k in self.schema[parent]["item_keys"] if k in self.parent_of]

    def run(self, queryset: str, method: str) -> pd.DataFrame:
        imeta = json.loads((REPO / "index" / "OE" / method / "meta.json").read_text(encoding="utf-8"))
        params = imeta["params"]
        catalog = self.catalogs[params.get("stage3_value_match", "literal")]
        oracle = params["stage2_method"] == "oracle_params"
        records = self._records(queryset) if oracle else None
        rows = []
        for r in iter_top100(queryset, method):
            top = r["candidates"][0]["index_item_key"]
            s1 = self.parent_of[top]
            gold_item = r["gold_item_key"]
            got = (self.oracle.extract(s1, records[r["query_item_key"]]) if oracle
                   else self.rules.extract(s1, r["query_text"]))
            matched = catalog.lookup(s1, got)
            tie_set = matched if matched else self.family(s1)
            row = {
                "q": str(r["query_item_key"]),
                "stage1_correct": s1 == r["gold_parent_key"],
                "matched": len(matched),
                "gold_in_match": gold_item in matched,
                "unique_gold": matched == [gold_item],
                "tie_size": len(tie_set),
                "tie_free": (1.0 / len(tie_set)) if gold_item in tie_set else 0.0,
                "consistent": top == tie_set[0],
            }
            if s1 == r["gold_parent_key"]:
                gold = {a["label"].strip(): a["values"][0]["value"].strip()
                        for a in self.params_of[gold_item].values() if a is not None}
                ext = {a.strip(): (v.strip() if v is not None else None) for a, v in got.items()}
                row.update(axes=len(gold), recovered=sum(ext.get(a) == v for a, v in gold.items()),
                           abstained=sum(ext.get(a) is None for a in gold),
                           misread=sum(ext.get(a) not in (None, v) for a, v in gold.items()))
            rows.append(row)
        return pd.DataFrame(rows).set_index("q")


def score_ties(queryset: str, method: str) -> pd.DataFrame:
    """Tie-free item hit of a score-based run: the rank-1 score tie seen in the top-100."""
    rows = []
    for r in iter_top100(queryset, method):
        c = r["candidates"]
        s1 = float(c[0]["score"])
        tied = [x["index_item_key"] for x in c if float(x["score"]) == s1]
        gold = r["gold_item_key"]
        rows.append({"q": str(r["query_item_key"]), "tie_size": len(tied),
                     "tie_free": (1.0 / len(tied)) if gold in tied else 0.0,
                     "truncated": len(tied) == len(c)})
    return pd.DataFrame(rows).set_index("q")


# --------------------------------------------------------------------------- pairing


def paired(short: str, dup: set[str], stages: Stages) -> tuple[pd.DataFrame, dict]:
    """One row per dev single query: modified and identity hits, as run and tie-free, and its type."""
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
    frame["item_scored"] = ~frame["gold"].isin(dup) & ~frame["q"].map(
        lambda k: "item" in EXCLUDED.get(k, {}).get("levels", ()))
    frame["parent_scored"] = ~frame["q"].map(lambda k: "parent" in EXCLUDED.get(k, {}).get("levels", ()))

    if short in STRUCTURED:
        mod_s, id_s = stages.run("single_texto", DIR[short]), stages.run("texto", DIR[short])
        for side, s in (("mod", mod_s), ("id", id_s)):
            if not s["consistent"].all():
                raise ValueError(f"{short}/{side}: re-derivation does not reproduce rank 1 on "
                                 f"{int((~s['consistent']).sum())} queries")
        extra = {"stages_mod": mod_s, "stages_id": id_s, "truncated": 0}
    else:
        mod_s, id_s = score_ties("single_texto", DIR[short]), score_ties("texto", DIR[short])
        extra = {"truncated": int(mod_s.loc[frame["q"], "truncated"].sum())
                 + int(id_s.loc[frame["gold"], "truncated"].sum())}
    frame["item_mod_tf"] = frame["q"].map(mod_s["tie_free"]).astype(float)
    frame["item_id_tf"] = frame["gold"].map(id_s["tie_free"]).astype(float)
    if short in STRUCTURED:
        # Stage 3's tie set lies inside the Stage-1 family, so the gold can be in it only when Stage 1
        # found the gold's concept.
        for side, s, keys in (("mod", mod_s, frame["q"]), ("id", id_s, frame["gold"])):
            s = s.loc[keys]
            if ((s["tie_free"] > 0) & ~s["stage1_correct"]).any():
                raise ValueError(f"{short}/{side}: gold in a tie set outside its concept")
    return frame, extra


def scope(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "all":
        return frame
    if name == NO_P8:
        return frame[(frame["type"] == "synonym_label") & ~frame["q"].isin(P8_DEV)]
    if name in LAYERS:
        return frame[frame["type"].isin(LAYERS[name])]
    return frame[frame["type"] == name]


def item(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["item_scored"]]


# --------------------------------------------------------------------------- statistics


def tie_free_cell(frame: pd.DataFrame, label: str) -> dict:
    f = item(frame)
    ident, mod = f["item_id_tf"].to_numpy(float), f["item_mod_tf"].to_numpy(float)
    d = (mod - ident)[:, None]
    return {"id": float(ident.mean()), "mod": float(mod.mean()), "delta": float(d.mean()),
            "q": ci(boot_query(d, f"s5|tf|{label}")[:, 0]),
            "c": ci(boot_cluster(d, f["concept"].to_numpy(), f"s5|tf|{label}")[:, 0])}


def contrast(a: pd.DataFrame, b: pd.DataFrame, label: str) -> dict:
    """Arm a − arm b on the same item-scored queries: at identity, modified, and the DiD."""
    fa, fb = item(a).set_index("q"), item(b).set_index("q")
    if list(fa.index) != list(fb.index):
        raise ValueError(f"{label}: the two arms scored different queries")
    clusters = fa["concept"].to_numpy()
    out = {"n": len(fa), "excluded": len(a) - len(fa), "concepts": int(fa["concept"].nunique())}
    for tag, sfx in (("tf", "_tf"), ("run", "")):
        d_id = (fa[f"item_id{sfx}"] - fb[f"item_id{sfx}"]).to_numpy(float)
        d_mod = (fa[f"item_mod{sfx}"] - fb[f"item_mod{sfx}"]).to_numpy(float)
        cols = np.column_stack([d_id, d_mod, d_mod - d_id])
        q = boot_query(cols, f"s5|con|{tag}|{label}")
        c = boot_cluster(cols, clusters, f"s5|con|{tag}|{label}")
        for j, name in enumerate(("id", "mod", "did")):
            out[f"{tag}_{name}"] = float(cols[:, j].mean())
            out[f"{tag}_{name}_q"] = ci(q[:, j])
            out[f"{tag}_{name}_c"] = ci(c[:, j])
            out[f"{tag}_{name}_p"] = boot_p(c[:, j])
    return out


# --------------------------------------------------------------------------- tables


def name(short: str) -> str:
    return f"`{short}`" + (" **oracle**" if short in ORACLE else "")


def header(title: str, how: list[str]) -> list[str]:
    return [f"# S5 — {title}", "", f"Generated by `{GENERATOR}`. " + " ".join(how), ""]


def population_note(pops: dict) -> list[str]:
    lines = [
        f"**Population.** {pops['n']:,} dev `single_texto` queries over {pops['concepts']} concepts. "
        f"Item level scores {pops['item']:,}: {pops['dup']:,} excluded because the gold shares its `texto` "
        f"(D-033) and {pops['amend_item']:,} by amendment. Parent level scores {pops['parent']:,}. "
        f"`{NO_P8}` drops the {len(P8_DEV)} case-only queries of P8 (D-044). Layers and types reach different "
        "leaves, so any comparison across them is **between-population**.",
        "",
    ]
    for key, entry in sorted(EXCLUDED.items()):
        lines.append(f"- `{key}` excluded at {', '.join(entry['levels'])} level ({entry['amendment']}): {entry['why']}")
    return lines + [""]


def oracle_note() -> list[str]:
    return ["Oracle arms read the query's own parsed parameters (D-010) and are quoted only beside their "
            "deployable twin: " + ", ".join(f"{name(o)} with `{t}`" for o, t in TWIN.items()) + ".", ""]


def write_ceilings(dup: set[str], extras: dict) -> None:
    lines = header("T1: identity ceilings of the structured arms (`texto`, dev)", [
        "Each arm asked to retrieve a leaf from that leaf's own `texto`. Item level on the duplicate-free golds",
        "(D-033), whose field ceiling is 1.0, so headroom is 1.0 minus the scored value (D-032). The two rules",
        "arms are S5's re-runs (A1); S2's runs of them are archived and remain S2's figures.",
    ])
    lines += ["\"item, all\" is every dev `texto` query, printed for reference only. **Tie-free** is the expected "
              "Acc@1 under a uniform tie-break over Stage 3's match (module docstring).", "",
              "| arm | item, all | item, scored | n scored | n excluded | CI (query) | CI (concept) | headroom | tie-free, scored | unique gold | parent | n | CI (concept) |",
              "|---|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|"]
    for short in STRUCTURED:
        f = perquery("texto", DIR[short])
        st = extras[short]["stages_id"]
        scored = f[~f["gold_item_key"].isin(dup)]
        iv = scored[["item_acc1"]].to_numpy(float)
        pv = f[["parent_acc1"]].to_numpy(float)
        keys = scored["query_item_key"].astype(str)
        lines.append(
            f"| {name(short)} | {f4(f['item_acc1'].mean())} | **{f4(iv.mean())}** | {len(scored):,} | "
            f"{len(f) - len(scored):,} | {fci(ci(boot_query(iv, 's5|ceil|' + short)[:, 0]))} | "
            f"{fci(ci(boot_cluster(iv, scored['gold_parent_key'].to_numpy(), 's5|ceil|' + short)[:, 0]))} | "
            f"{f4(1.0 - iv.mean())} | {f4(st.loc[keys, 'tie_free'].mean())} | {f4(st.loc[keys, 'unique_gold'].mean())} | "
            f"{f4(pv.mean())} | {len(f):,} | "
            f"{fci(ci(boot_cluster(pv, f['gold_parent_key'].to_numpy(), 's5|ceilp|' + short)[:, 0]))} |"
        )
    lines += sources_block(["texto"], only=STRUCTURED)
    write(OUT / "ceilings.md", lines)


def write_profile(level: str, stats: dict, pops: dict) -> None:
    title = "T2: the profile, item level (dev)" if level == "item" else "T3: the profile, parent level (dev)"
    lines = header(title, [
        "Each query is paired with the same arm's identity result on its own gold leaf; δ is the mean of",
        "modified − identity over the cell's queries, a treatment effect on the treated. Raw modified Acc@1 is",
        "printed only beside its own identity baseline. S4's columns; the reference arms' own profiles are S4's",
        "(`results/S4/`), not repeated here.",
    ])
    lines += population_note(pops) + oracle_note()
    lines += ["**Retention** is P(hit under modification | hit at identity), quoted when arms are set side by "
              "side (D-032).", ""]
    for short in STRUCTURED:
        lines += [f"## {name(short)}", ""]
        if level == "item":
            lines += ["| scope | n | n scored | n excluded | concepts | identity | modified | δ | CI (query) | CI (concept) | retention | CI (concept) | lost | gained | tie-free id | tie-free mod | tie-free δ | CI (query) | CI (concept) |",
                      "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|---:|---:|---:|---|---|"]
        else:
            lines += ["| scope | n | n scored | n excluded | concepts | identity | modified | δ | CI (query) | CI (concept) | retention | CI (concept) | lost | gained |",
                      "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|---:|---:|"]
        for sc in SCOPES:
            c = stats[short][(sc, level)]
            row = (f"| {sc} | {c['n_all']:,} | {c['n']:,} | {c['excluded']:,} | {c['concepts']} | {f4(c['id'])} | "
                   f"{f4(c['mod'])} | {fd(c['delta'])} | {fci(c['q'], True)} | {fci(c['c'], True)} | "
                   f"{f4(c['retention'])} | {fci(c['ret_c'])} | {c['down']:,} | {c['up']:,} |")
            if level == "item":
                t = stats[short][(sc, "tf")]
                row += f" {f4(t['id'])} | {f4(t['mod'])} | {fd(t['delta'])} | {fci(t['q'], True)} | {fci(t['c'], True)} |"
            lines.append(row)
        lines.append("")
    if level == "parent":
        lines += ["## The collapse quantities of H1 (item-scored queries)", "",
                  "RP/WI: rank 1 in the right concept and the wrong leaf. D = P(item | parent). Gap = parent − item. "
                  "Changes are paired, modified − identity.", ""]
        for short in STRUCTURED:
            lines += [f"### {name(short)}", "",
                      "| scope | n scored | n excluded | concepts | RP/WI id | RP/WI mod | Δ RP/WI | CI (query) | CI (concept) | D id | D mod | gap id | gap mod | Δ gap | CI (query) | CI (concept) |",
                      "|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|"]
            for sc in SCOPES:
                k = stats[short][(sc, "collapse")]
                lines.append(
                    f"| {sc} | {k['n']:,} | {k['excluded']:,} | {k['concepts']} | {f4(k['rpwi_id'])} | {f4(k['rpwi_mod'])} | "
                    f"{fd(k['d_rpwi'])} | {fci(k['d_rpwi_q'], True)} | {fci(k['d_rpwi_c'], True)} | {f4(k['D_id'])} | "
                    f"{f4(k['D_mod'])} | {f4(k['gap_id'])} | {f4(k['gap_mod'])} | {fd(k['d_gap'])} | "
                    f"{fci(k['d_gap_q'], True)} | {fci(k['d_gap_c'], True)} |")
            lines.append("")
    lines += sources_block(["texto", "single_texto"], only=STRUCTURED)
    write(OUT / ("profile_item.md" if level == "item" else "profile_parent.md"), lines)


def write_stages(frames: dict, extras: dict, qtext: dict, ctext: dict) -> None:
    lines = header("T4: stage decomposition (dev `single_texto`)", [
        "Re-derived from each run's own rank 1 and deterministic code, as S2's `structured_stages.md`: Stage 1 is",
        "the rank-1 leaf's concept; Stage 2 the arm's extractor on that concept (the oracle reads the query",
        "record); Stage 3 the catalogue lookup. Re-derivation reproduces every run's rank 1 (checked on load).",
        "Axis columns are over queries whose Stage 1 is correct, scored against the gold leaf's parameters.",
    ])
    lines += ["**Match size** is the tie set's size (Stage 3's match, or the family when nothing matched): the "
              "number of leaves the arm cannot order. Item-scored queries.", "",
              "| arm | scope | n scored | n excluded | concepts | Stage 1 | all axes | axis recovery | abstained axes (q) | misread axes (q) | gold in match | unique gold | no match | match size median | IQR |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---|"]
    for short in STRUCTURED:
        st = extras[short]["stages_mod"]
        for sc in SCOPES:
            whole = scope(frames[short], sc)
            f = item(whole)
            s = st.loc[f["q"]]
            ok = s[s["stage1_correct"]]
            axes = ok["axes"].sum()
            q25, q50, q75 = np.percentile(s["tie_size"], [25, 50, 75])
            lines.append(
                f"| {name(short)} | {sc} | {len(s):,} | {len(whole) - len(s):,} | {f['concept'].nunique()} | {f4(s['stage1_correct'].mean())} | "
                f"{f4((ok['recovered'] == ok['axes']).mean()) if len(ok) else '—'} | "
                f"{f4(ok['recovered'].sum() / axes) if axes else '—'} | "
                f"{int(ok['abstained'].sum()):,} ({int((ok['abstained'] > 0).sum()):,}) | "
                f"{int(ok['misread'].sum()):,} ({int((ok['misread'] > 0).sum()):,}) | "
                f"{f4(s['gold_in_match'].mean())} | {f4(s['unique_gold'].mean())} | {f4((s['matched'] == 0).mean())} | "
                f"{q50:,.0f} | [{q25:,.0f}, {q75:,.0f}] |")
    lines += ["", "## The decimal artefact (DATASET_DEFECTS H1), per type", "",
              "`in query`: item-scored queries whose text carries a `d.ddd` decimal, which `normalize_text` mangles "
              "(the rules extractor reads normalised text). `absent from gold`: of those, the ones whose decimal "
              "the gold `texto` lacks, the only ones where a miss is attributable to the artefact (S4 A4).", "",
              "| type | n scored | n excluded | in query | absent from gold |", "|---|---:|---:|---:|---:|"]
    all0 = frames[STRUCTURED[0]]
    f0 = item(all0)
    for t in TYPES:
        f = f0[f0["type"] == t]
        n_excl = int((all0["type"] == t).sum()) - len(f)
        inq = [k for k in f["q"] if _DECIMAL.search(qtext[k])]
        absent = [k for k, g in zip(f["q"], f["gold"])
                  if _DECIMAL.search(qtext[k]) and not set(_DECIMAL.findall(qtext[k])) <= set(_DECIMAL.findall(ctext[g]))]
        lines.append(f"| {t} | {len(f):,} | {n_excl:,} | {len(inq):,} | {len(absent):,} |")
    lines += sources_block(["single_texto"], only=STRUCTURED, inputs=(SCHEMA, LONG_NORM, QUERY_TABLES["single_texto"]))
    write(OUT / "stages.md", lines)


def write_contrasts(cons: dict, extras: dict) -> None:
    lines = header("T5: H3 contrasts, structured against reference arms (dev, item level)", [
        "Both arms answered the same queries; differences are per query, bootstrapped by concept. Δ id is the",
        "difference on the queries' gold leaves at identity, Δ mod under modification, and DiD = Δ mod − Δ id",
        "per query (= δ of the structured arm − δ of the reference arm).",
    ])
    lines += ["**Tie-free is the reading** for every contrast (design, D-028); as-run values are printed beside "
              "and are not read alone. A positive Δ mod means the structured arm ranks above the reference arm "
              "under modification. `bm25_unigram_params` is an **oracle** (D-010): its contrasts are the previous "
              "study's comparison (structured against BM25 with parameters), deployable against oracle, labelled "
              "so. `bge_m3_colbert` is printed and predicted nowhere (D-029).", "",
              "Score ties filling the whole top-100, whose size is therefore unknown and taken as the 100 seen: "
              + ", ".join(f"`{s}` {extras[s]['truncated']:,}" for s in REFERENCE) + ".", ""]
    for short in STRUCTURED:
        for ref in REFERENCE:
            lines += [f"## {name(short)} − {name(ref)}", "",
                      "| scope | n scored | n excluded | concepts | Δ id | CI (query) | CI (concept) | Δ mod | CI (query) | CI (concept) | DiD | CI (query) | CI (concept) | Δ mod, as run | CI (query) | CI (concept) | DiD, as run | CI (query) | CI (concept) |",
                      "|---|---:|---:|---:|---:|---|---|---:|---|---|---:|---|---|---:|---|---|---:|---|---|"]
            for sc in SCOPES:
                k = cons[(short, ref, sc)]
                lines.append(
                    f"| {sc} | {k['n']:,} | {k['excluded']:,} | {k['concepts']} | "
                    + " | ".join(
                        (f"**{fd(k[key])}**" if key == "tf_mod" else fd(k[key]))
                        + f" | {fci(k[key + '_q'], True)} | {fci(k[key + '_c'], True)}"
                        for key in ("tf_id", "tf_mod", "tf_did", "run_mod", "run_did"))
                    + " |")
            lines.append("")
    lines += sources_block(["texto", "single_texto"])
    write(OUT / "contrasts.md", lines)


def write_predictions(results: list[dict], g2: dict) -> None:
    lines = header("T6: the registered predictions and G2 (dev)", [
        "Tie-free Acc@1 throughout. Read on the concept-clustered interval, Holm–Bonferroni across the tests",
        "below, Benjamini–Hochberg beside. **Supported** when the interval lies above 0 and the Holm p is below",
        "α; **contradicted** in the mirror case; **not supported** otherwise (S4's rule).",
    ])
    lines += [f"α = {ALPHA}. Q1 and Q3 are **confirmatory**: the rules arms' per-type results were visible in S2 "
              "before this design. Q2 is **blind**: the oracle bound had never run. Q3's L2 and L3 cells compare "
              "different leaves from L1: between-population. A pool on fewer than "
              f"{FEW_CLUSTERS} concepts is marked ‡.", "",
              "| prediction | hypothesis | test | cell | n scored | n excluded | concepts | estimate | CI (concept) | p | Holm p | BH p | reading |",
              "|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|"]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['hyp']} | {r['what']} | {r['cell']} | {r['n']:,} | {r['excluded']:,} | "
            f"{r['concepts']}{' ‡' if r['concepts'] < FEW_CLUSTERS else ''} | {fd(r['est'])} | {fci(r['c'], True)} | "
            f"{fp(r['p'])} | {fp(r['holm'])} | {fp(r['bh'])} | **{r['reading']}** |")
    lines += ["", "## G2, read under the frozen rule", "",
              f"G2 asks whether the structured/lexical ranking inverts. Rule (design): **yes** if Q1's pooled-L1 test "
              f"is supported; **no** if it is contradicted, or not supported with a point estimate at or below 0; "
              f"**ambiguous** otherwise. Q1 pooled L1: {g2['reading']}, estimate {fd(g2['est'])} "
              f"{fci(g2['c'], True)}. **G2 reads: {g2['g2']}.** Q2's pooled L1 (the bound) is printed beside it: "
              f"{g2['q2_reading']}, estimate {fd(g2['q2_est'])} {fci(g2['q2_c'], True)}. The plan's consequence is "
              "César's to confirm in the report."]
    lines += sources_block(["texto", "single_texto"], only=["rules_valuenorm", "oracleparams", "bm25_unigram"])
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
                f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` |")
    lines += ["", "| input | SHA-256 |", "|---|---|",
              *(f"| `{p.name}` | `{sha256_file(p)[:16]}` |" for p in (SIDECAR, *inputs)),
              "", f"Bootstrap: B = {B:,}, seed = {SEED}, percentile 95 % intervals; p from the concept-clustered "
              "draws (D-030). Split `dev`."]
    return lines


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def write_provenance() -> None:
    s5 = meta("single_texto", DIR["oracleparams"])["code_commit"]
    lines = header("T7: run provenance (dev)", [
        "Every run the S5 tables read. The structured runs are S5's own, at one commit (A1: the rules arms",
        "re-run; S2's copies archived under `runs/_archive/S2`). The reference runs are S4's and S3's, read",
        "and not re-run (design work item 4).",
    ])
    lines += ["| run_id | queries | config SHA-256 | code commit | dirty | query-set SHA-256 | split | S5 |",
              "|---|---:|---|---|---|---|---|---|"]
    for queryset in ("texto", "single_texto"):
        for d, short, _, _ in ARMS:
            m = meta(queryset, d)
            lines.append(
                f"| `{m['run_id']}` | {m['queries']:,} | `{m['config_sha256'][:16]}` | `{m['code_commit'][:7]}` | "
                f"{str(bool(m.get('code_dirty'))).lower()} | `{m['query_set_sha256'][:16]}` | {m.get('split')} | "
                f"{'new' if m['code_commit'] == s5 else 'read'} |")
    archive = REPO / "runs" / "_archive" / "S2" / "SHA256SUMS"
    lines += ["", f"S5 commit: `{s5[:7]}` (`{git('log', '-1', '--format=%s', s5)}`).",
              f"S2 archive checksum list: `{archive.relative_to(REPO).as_posix()}`, SHA-256 `{sha256_file(archive)[:16]}`."]
    write(OUT / "run_provenance.md", lines)


# --------------------------------------------------------------------------- main


def texts() -> tuple[dict[str, str], dict[str, str]]:
    queries = {r["item_key"]: r["text"] for r in json.loads(SINGLE_JSON.read_text(encoding="utf-8"))}
    corpus = {r["item_key"]: r["text"] for r in json.loads(CORPUS_JSON.read_text(encoding="utf-8"))}
    return queries, corpus


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    dup = duplicated()
    stages = Stages()
    frames, extras = {}, {}
    for _, short, _, _ in ARMS:
        frames[short], extras[short] = paired(short, dup, stages)
        print(f"paired {short}")

    first = frames[ARMS[0][1]]
    for short, frame in frames.items():
        if list(frame["q"]) != list(first["q"]):
            raise ValueError(f"{short}: single_texto queries differ from {ARMS[0][1]}'s")
    pops = {
        "n": len(first), "concepts": int(first["concept"].nunique()),
        "item": int(first["item_scored"].sum()), "parent": int(first["parent_scored"].sum()),
        "dup": int(first["gold"].isin(dup).sum()),
        "amend_item": sum("item" in e["levels"] for e in EXCLUDED.values()),
    }

    stats = {}
    for short in STRUCTURED:
        stats[short] = {}
        for sc in SCOPES:
            s = scope(frames[short], sc)
            for level in LEVELS:
                stats[short][(sc, level)] = cell(s, level, f"s5|{short}|{sc}")
            stats[short][(sc, "collapse")] = collapse(s, f"s5|{short}|{sc}")
            stats[short][(sc, "tf")] = tie_free_cell(s, f"{short}|{sc}")
    cons = {(s, r, sc): contrast(scope(frames[s], sc), scope(frames[r], sc), f"{s}|{r}|{sc}")
            for s in STRUCTURED for r in REFERENCE for sc in SCOPES}

    write_ceilings(dup, extras)
    write_profile("item", stats, pops)
    write_profile("parent", stats, pops)
    qtext, ctext = texts()
    write_stages(frames, extras, qtext, ctext)
    write_contrasts(cons, extras)

    results = []
    for pid, hyp, kind, arm, ref, cells in PREDICTIONS:
        for sc in cells:
            k = cons[(arm, ref, sc)]
            key = "tf_mod" if kind == "mod" else "tf_did"
            what = (f"{name(arm)} − `{ref}` > 0 under modification" if kind == "mod"
                    else f"DiD {name(arm)} vs `{ref}` > 0")
            results.append({"id": pid, "hyp": hyp, "what": what, "cell": sc, "concepts": k["concepts"],
                            "n": k["n"], "excluded": k["excluded"],
                            "est": k[key], "c": k[f"{key}_c"], "p": k[f"{key}_p"], "side": "positive"})
    p = [r["p"] for r in results]
    for r, h, q in zip(results, holm(p), bh(p)):
        r.update(holm=h, bh=q)
        r["reading"] = reading(r)
    q1 = next(r for r in results if r["id"] == "Q1" and r["cell"] == "L1")
    q2 = next(r for r in results if r["id"] == "Q2" and r["cell"] == "L1")
    g2 = ("yes" if q1["reading"] == "supported" else
          "no" if q1["reading"] == "contradicted" or q1["est"] <= 0 else "ambiguous")
    write_predictions(results, {"reading": q1["reading"], "est": q1["est"], "c": q1["c"], "g2": g2,
                                "q2_reading": q2["reading"], "q2_est": q2["est"], "q2_c": q2["c"]})
    write_provenance()
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
