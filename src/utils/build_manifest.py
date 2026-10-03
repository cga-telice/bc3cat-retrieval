"""Build docs/synthetic-oe/MANIFEST.md — S0 work item 1.

Records, for every data file the branch depends on, a full SHA-256, byte size and
record count, and re-asserts the claims INTAKE.md makes about the corpus and query
sets. Generated, never hand-edited: run it again and it overwrites.

    python src/utils/build_manifest.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "processed"
OUT = REPO / "docs" / "synthetic-oe" / "MANIFEST.md"

OE_CORPUS = ["OE_texto.json", "OE_resumen.json"]
OE_QUERIES = ["OE_single_texto.json", "OE_stacked_texto.json"]
OE_OTHER = ["OE_concept_schema.json", "OE_duplicate_texto_groups.json"]
# D-043: the item keys of the 2 test `single_texto` queries upstream built from a withdrawn rule
# (DATASET_DEFECTS P7). Keys only, no text; applied at item level in S12 and nowhere before.
# D-044: the item keys of the 2 test `single_texto` queries equal to their gold after lower-casing
# (DATASET_DEFECTS P8). Keys only; kept in S12, with every `synonym_label` cell also shown without them.
OE_S12 = ["OE_P7_test_exclusion.json", "OE_P8_test_exclusion.json"]
# D-043 amended: the wider L2 slices, delivered at `bc3cat-dataset` `b0e23f1` (generated at `90a318f`).
# A new query set, registered here and wired in S6.
OE_L2 = ["OE_single_l2_texto.json", "OE_single_l2_modifications.jsonl", "OE_single_l2_provenance.json"]
# S6 work item 1: the SINGLE modifications sidecar (RESEARCH_PLAN §5, D-004), never handed off with the
# release although it is the release's own (`bc3cat-dataset` blob `d5f2f86b` at `8998875`, last changed
# at `a89eca4`). Taken 2026-09-30 from `data/synthetic/processed_OE_ablation_single/`.
OE_SIDECARS = ["OE_single_modifications.jsonl"]
# The E3 balanced dose set (D-009), delivered upstream 2026-09-17 and taken in S3 work item 2.
# Registered, not yet run on: S8 is the sprint that uses them. They are not declared query sets,
# so nothing resolves a run against them yet.
OE_E3 = [
    "OE_dose_texto.json",
    "OE_isolated_texto.json",
    "OE_leaf_applicability.jsonl",
]
# The tables a run is actually stamped against. `run_meta.json` records `query_set_sha256` of
# the *derived* table it read — `OE_stacked_texto_feats.parquet`, not the JSON — so a manifest
# that lists only the deliveries cannot answer "does this run's query set still exist?". They
# were absent here until S3 work item 1; every OE run made before then is stamped against a
# digest this file did not carry.
OE_DERIVED = [
    "OE_long_norm.parquet",
    "OE_short_norm.parquet",
    "OE_long_feats.parquet",
    "OE_short_feats.parquet",
    "OE_features_meta.json",
    "OE_single_texto_norm.parquet",
    "OE_single_texto_feats.parquet",
    "OE_stacked_texto_norm.parquet",
    "OE_stacked_texto_feats.parquet",
    # S6 work item 1, by `build_s6_query_tables.py` along `single_texto`'s path.
    "OE_single_l2_texto_norm.parquet",
    "OE_single_l2_texto_feats.parquet",
    # S8 work item 1 (D-052), by `build_s8_query_tables.py` along the same path.
    "OE_dose_texto_norm.parquet",
    "OE_dose_texto_feats.parquet",
    "OE_isolated_texto_norm.parquet",
    "OE_isolated_texto_feats.parquet",
]
# Superseded by the 2026-09-27 delivery and kept under digest-stamped names, so that S2's three
# stacked runs remain resolvable against the tree (D-033). Not a query set: `run_context` resolves
# query sets by exact canonical name, so these are provenance only and nothing can run on them.
OE_SUPERSEDED = [
    "OE_stacked_texto__1bde2115.json",
    "OE_stacked_texto_norm__81cd501b.parquet",
    "OE_stacked_texto_feats__7b0894e6.parquet",
]
# S91's two renderings of `resumen`, the decoder table they come from
# (`src/utils/build_resumen_renderings.py`) and their derived tables (`build_s91_query_tables.py`). Generated here, not delivered, so no intake digest;
# recorded so the S91 runs, stamped against their derived tables, have a source on record.
OE_S91 = [
    "OE_resumen_decoded.json",
    "OE_resumen_stripped.json",
    "OE_resumen_decoder.json",
    "OE_resumen_decoded_norm.parquet",
    "OE_resumen_decoded_feats.parquet",
    "OE_resumen_stripped_norm.parquet",
    "OE_resumen_stripped_feats.parquet",
]
# S9 work item 1: the two corpus-rendering bases of U (`build_s9_bases.py`) and their tables
# (`build_s9_query_tables.py`, path proven on the stored corpus rows). Generated here, not delivered.
# Work item 2 adds the transformed sets `{base}__{t}`: the query JSON, its provenance sidecar, its two
# tables and, for the LLM transforms, the generation cache. Listed per transform as each is generated.
OE_S9 = [
    "OE_texto_u.json",
    "OE_resumen_u.json",
    "OE_texto_u_norm.parquet",
    "OE_texto_u_feats.parquet",
    "OE_resumen_u_norm.parquet",
    "OE_resumen_u_feats.parquet",
]
S9_BASES = ("texto_u", "resumen_u", "single_texto", "single_l2_texto", "stacked_texto")
S9_GENERATED = ("canon", "hyde", "rewrite")


def _s9_transformed(transform: str) -> list[str]:
    files = []
    for base in S9_BASES:
        stem = f"OE_{base}__{transform}"
        files += [f"{stem}.json", f"{stem}.meta.json", f"{stem}_norm.parquet", f"{stem}_feats.parquet"]
        if transform != "canon":
            files.append(f"llm_cache/{stem}.jsonl")
    return files


OE_S9 += [f for t in S9_GENERATED for f in _s9_transformed(t)]
# Work item 5: the LLM extractor's generations, cached by the structured pipeline while its five runs ran
# (`retrievers.structured_pipeline.LLM_CACHE`), shared by all of them.
OE_S9 += ["llm_cache/structured_llm_extract.jsonl"]
OEB = [
    "OEB_texto.json",
    "OEB_resumen.json",
    "OEB_long_norm.parquet",
    "OEB_short_norm.parquet",
    "OEB_long_feats.parquet",
    "OEB_short_feats.parquet",
    "OEB_features_meta.json",
]

# SHA-256 prefixes recorded at copy time, INTAKE.md §2. A mismatch stops the sprint: these are
# the digests every run's provenance is quoted against.
INTAKE_PREFIXES = {
    "OE_single_texto.json": "b6a43961295cc2ca",
    # Corrected stacked set, taken 2026-09-27 under D-033. The superseded `1bde21157ef97421`
    # lives on below, under its own name.
    "OE_stacked_texto.json": "c34a222ae2af05a0",
    "OE_duplicate_texto_groups.json": "b3cfcad47c71c5eb",
    # E3, from that repository's own handoff manifest, run `e3-20260917T093057Z`.
    "OE_dose_texto.json": "555fab84d134886f",
    "OE_isolated_texto.json": "054041ff05349fae",
    "OE_leaf_applicability.jsonl": "eda12d17c323add4",
    "OE_concept_schema.json": "2d3273ddb3e443a1",
    "OE_texto.json": "02a2c270d7ffe147",
    "OE_resumen.json": "0cd380e9e44ad8c5",
    # D-043, taken 2026-09-29 from `bc3cat-dataset` `data/synthetic/handoff_OE/`.
    "OE_P7_test_exclusion.json": "96fe3854f2b6d935",
    # D-044, taken 2026-09-29 from `bc3cat-dataset` `data/synthetic/handoff_OE/`, committed there at
    # `0923284`. This is the CRLF checkout; the LF blob git stores hashes to `9b007b1c47bf7430`.
    "OE_P8_test_exclusion.json": "6cda7fa05aa6e32f",
    # D-043 amended, from upstream's provenance file and its delivery message.
    "OE_single_l2_texto.json": "fff7dd3be023125b",
    "OE_single_l2_modifications.jsonl": "e1e5adbb8824bd34",
    # S6 work item 1. The CRLF checkout upstream; the LF blob git stores hashes to `e2bcc95f77caa4ca`.
    "OE_single_modifications.jsonl": "f492d9a0b7e133bf",
    # The superseded artefacts are checked against the digest their own filename claims. A copy
    # whose name lies about its contents is worse than no copy, because it would be trusted.
    "OE_stacked_texto__1bde2115.json": "1bde21157ef97421",
    "OE_stacked_texto_norm__81cd501b.parquet": "81cd501b305b17db",
    "OE_stacked_texto_feats__7b0894e6.parquet": "7b0894e6bc5c82d3",
}

# Counts INTAKE.md claims, asserted here against what the files actually hold.
INTAKE_COUNTS = {
    "corpus_records": 70242,
    "concepts": 83,
    "single_queries": 4439,
    "stacked_queries": 4998,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def record_count(path: Path) -> int | str:
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        return pq.ParquetFile(path).metadata.num_rows
    if path.suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, list):
        return len(obj)
    if isinstance(obj, dict):
        # The duplicate sidecar is a wrapper, so len() would report its four header keys and
        # call it four records. Report the grouping it actually carries.
        if "groups" in obj and isinstance(obj["groups"], dict):
            return len(obj["groups"])
        return len(obj)
    return "n/a"


def main() -> None:
    commit = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], text=True
    ).strip()

    rows: list[tuple[str, int, int | str, str, str]] = []
    for name in OE_CORPUS + OE_QUERIES + OE_OTHER + OE_S12 + OE_L2 + OE_SIDECARS + OE_E3 + OE_DERIVED + OE_SUPERSEDED + OE_S91 + OE_S9 + OEB:
        p = DATA / name
        digest = sha256(p)
        expected = INTAKE_PREFIXES.get(name)
        if expected is None:
            check = "— (no digest on record)"
        elif digest.startswith(expected):
            check = f"matches `{expected}`"
        else:
            raise SystemExit(
                f"DIGEST MISMATCH for {name}: INTAKE.md §2 records {expected}, "
                f"file is {digest[:16]}. Sprint stops here."
            )
        rows.append((name, p.stat().st_size, record_count(p), digest, check))

    # --- observed corpus and query facts ---
    texto = json.loads((DATA / "OE_texto.json").read_text(encoding="utf-8"))
    resumen = json.loads((DATA / "OE_resumen.json").read_text(encoding="utf-8"))
    single = json.loads((DATA / "OE_single_texto.json").read_text(encoding="utf-8"))
    stacked = json.loads((DATA / "OE_stacked_texto.json").read_text(encoding="utf-8"))
    schema = json.loads((DATA / "OE_concept_schema.json").read_text(encoding="utf-8"))

    corpus_keys = {r["item_key"] for r in texto}
    parents = {r["parent_key"] for r in texto}
    parent_of = {r["item_key"]: r["parent_key"] for r in texto}
    template_rows = [k for k in corpus_keys if k.endswith("$") or "#" in k]

    def gold_check(qs: list[dict]) -> tuple[int, int, int]:
        missing = sum(1 for q in qs if q["gold_item_key"] not in corpus_keys)
        mismatched = sum(
            1
            for q in qs
            if q["gold_item_key"] in corpus_keys
            and parent_of[q["gold_item_key"]] != q["parent_key"]
        )
        return len({q["gold_item_key"] for q in qs}), missing, mismatched

    s_leaves, s_missing, s_mismatch = gold_check(single)
    k_leaves, k_missing, k_mismatch = gold_check(stacked)

    observed = {
        "corpus_records": len(texto),
        "concepts": len(parents),
        "single_queries": len(single),
        "stacked_queries": len(stacked),
    }

    # --- render ---
    L: list[str] = []
    L.append("# MANIFEST — `research/synthetic-oe`")
    L.append("")
    L.append(
        "Derived. Generated by `src/utils/build_manifest.py`; never hand-edited. "
        "Re-run it to refresh."
    )
    L.append("")
    L.append(f"**Generated:** {date.today().isoformat()} · **Code commit:** `{commit}`")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Files")
    L.append("")
    L.append("| File | Bytes | Records | SHA-256 | vs `INTAKE.md §2` |")
    L.append("|---|---:|---:|---|---|")
    for name, size, n, digest, check in rows:
        L.append(f"| `{name}` | {size:,} | {n:,} | `{digest}` | {check} |")
    L.append("")
    L.append(
        "**The 2026-09-27 delivery (D-033).** `OE_stacked_texto.json` is now the corrected file "
        "`c34a222a…`, which adds `texto_modification_count` / `texto_modification_types` and "
        "changes no text: all 4,998 records agree row for row with the superseded file on "
        "`text`, `id`, `item_key` and `gold_item_key` (`tests/test_intake_20260927.py`). The "
        "three `__`-suffixed rows are that superseded query set, kept under digest-stamped names "
        "so S2's stacked runs — stamped against the *feature table* `7b0894e6…`, not the JSON — "
        "still resolve against the tree. They are not a query set: `run_context` resolves query "
        "sets by exact canonical name, so nothing can be run on them. `OE_texto.json` and "
        "`OE_resumen.json` were deliberately **not** re-taken with `duplicate_texto_group` "
        "inside, because their digests would change although their texts would not, and all 15 "
        "S2 runs would stop resolving; the sidecar carries the same grouping instead."
    )
    L.append("")
    L.append(
        "The seven `OEB_*` files carry no digest anywhere before this manifest: they were "
        "copied from `../bc3cat-dataset/data/processed/` on 2026-09-15 while repopulating "
        "`data/` after the incident (D-019). Their digests are recorded here for the first "
        "time, so they are checkable from now on but not verifiable backwards."
    )
    L.append("")
    L.append("## Claims asserted")
    L.append("")
    L.append("Every count `INTAKE.md` states, re-counted from the files themselves.")
    L.append("")
    L.append("| Claim | `INTAKE.md` | Observed | |")
    L.append("|---|---:|---:|---|")
    for key, claimed in INTAKE_COUNTS.items():
        got = observed[key]
        L.append(
            f"| {key.replace('_', ' ')} | {claimed:,} | {got:,} | "
            f"{'agrees' if got == claimed else '**DIFFERS**'} |"
        )
    L.append("")
    L.append("## Integrity checks")
    L.append("")
    L.append("| Check | Result |")
    L.append("|---|---|")
    L.append(
        f"| `OE_texto.json` and `OE_resumen.json` hold the same leaves, in the same order | "
        f"{'yes' if [r['item_key'] for r in texto] == [r['item_key'] for r in resumen] else '**NO**'} |"
    )
    L.append(
        f"| `item_key` unique across the corpus | "
        f"{'yes' if len(corpus_keys) == len(texto) else '**NO**'} |"
    )
    L.append(
        f"| Template rows (`$` / `#`) present | "
        f"{'**' + str(len(template_rows)) + '**' if template_rows else 'none'} |"
    )
    L.append(f"| Concepts in `OE_concept_schema.json` | {len(schema):,} |")
    L.append(
        f"| Single queries: gold leaves / gold absent from corpus / parent mismatch | "
        f"{s_leaves:,} / {s_missing} / {s_mismatch} |"
    )
    L.append(
        f"| Stacked queries: gold leaves / gold absent from corpus / parent mismatch | "
        f"{k_leaves:,} / {k_missing} / {k_mismatch} |"
    )
    L.append("")

    # --- OEB: reconcile the JSON record count against the parquet row count ---
    import pandas as pd

    oeb = json.loads((DATA / "OEB_texto.json").read_text(encoding="utf-8"))
    oeb_keys = {r["item_key"] for r in oeb}
    oeb_templates = sorted(k for k in oeb_keys if k.endswith("$") or "#" in k)
    norm_keys = set(pd.read_parquet(DATA / "OEB_long_norm.parquet")["item_key"].astype(str))
    only_json = sorted(oeb_keys - norm_keys)
    only_parquet = sorted(norm_keys - oeb_keys)

    L.append("## OEB: JSON against parquet")
    L.append("")
    L.append(
        f"`OEB_texto.json` holds {len(oeb):,} records and the four parquets "
        f"{len(norm_keys):,} rows. The difference is accounted for, not lost: "
        f"{len(only_json)} key(s) present in the JSON and absent from the parquets — "
        f"{', '.join('`' + k + '`' for k in only_json) if only_json else 'none'} — and "
        f"{len(only_parquet)} the other way round. "
        + (
            "Template rows are dropped by normalisation, which is the intended behaviour; "
            f"the OEB corpus still carries {len(oeb_templates)} of them "
            f"({', '.join('`' + k + '`' for k in oeb_templates)}), whereas the OE corpus "
            "carries none."
            if oeb_templates
            else ""
        )
    )
    L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    try:
        print(f"written: {OUT.relative_to(REPO)}")
    except ValueError:  # OUT redirected out of the tree, e.g. a dry run
        print(f"written: {OUT}")
    for key, claimed in INTAKE_COUNTS.items():
        print(f"  {key}: claimed {claimed}, observed {observed[key]}")
    print(f"  single gold missing/mismatch: {s_missing}/{s_mismatch}")
    print(f"  stacked gold missing/mismatch: {k_missing}/{k_mismatch}")
    print(f"  template rows: {len(template_rows)}")


if __name__ == "__main__":
    main()
