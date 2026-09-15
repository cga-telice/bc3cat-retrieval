"""One resolver; notebooks never build a path (D-022).

Given a config and a query set, this returns everything a notebook needs to know about
where things live: the resolved inputs, the index directory, the run directory, the query
table and the retriever module. **No notebook constructs a path after this lands.**

Layout is D-008's, with the fourth query set S1 added:

    index/{collection}/{method}                 — built from the corpus; carries no query set
    runs/{collection}/{queryset}/{method}

Query sets. `texto` is the identity rendering — the leaf's own long description, asked of
the corpus that contains it — and it is the reference every paired delta is measured
against. `resumen` is the replication baseline, the leaf's short summary, which is what the
previous study used as its query. The rest are BC3CAT-Syn renderings.

Paths inside a config are written for the container, where the repo is mounted at /work.
`work_root` rebases that prefix so the same config resolves in a checkout or a tmp dir.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

#: The query sets a run may be asked for. `balanced_texto` arrives only if E3 lands (D-009).
QUERY_SETS = ("texto", "resumen", "single_texto", "stacked_texto", "balanced_texto")

#: The three shapes `inputs` takes across the 77 configs, in the order they are looked for.
#: `feats` is the lexical family (70 configs), `text` the neural one (5), `norm` the hybrid
#: pair (2). Each names its short and long input and the template a synthetic query set
#: takes in that family — BC3CAT-Syn's own `{collection}_{queryset}.json` for the text
#: family, and the tables S1 derives from it for the other two.
_INPUT_SHAPES = (
    ("short_feats", "long_feats", "{collection}_{queryset}_feats.parquet"),
    ("short_text_path", "long_text_path", None),  # template decided by the declared suffix
)

#: Within the text family the declared suffix decides the synthetic template, because the
#: two hybrids read normalised parquets where the neural configs read raw JSON.
_TEXT_TEMPLATES = (
    ("_norm.parquet", "{collection}_{queryset}_norm.parquet"),
    (".json", "{collection}_{queryset}.json"),
)

#: Query sets that are the corpus's own renderings: they read the config's declared inputs
#: rather than a derived table, which is what keeps the OEB fixture reading what it reads
#: today. `texto` is the identity rendering, `resumen` the replication baseline.
_DECLARED_QUERY_SETS = {"resumen": "short", "texto": "long"}

_CONTAINER_ROOT = "/work"

#: Configs spell the retriever `src.retrievers.x`, but what sits on `sys.path` is /work/src,
#: so the importable name is `retrievers.x`. Both spellings are accepted and normalised here,
#: in one place, rather than in each notebook.
_MODULE_PREFIX = "src."


def _rebase(value: str, work_root: Path) -> Path:
    """Rebase a container path onto the root this process can actually see."""
    if value.startswith(_CONTAINER_ROOT):
        return work_root / value[len(_CONTAINER_ROOT) :].lstrip("/\\")
    return Path(value)


@dataclass(frozen=True)
class DataPaths:
    """Where the data phase reads and writes, for one collection."""

    collection: str
    data_dir: Path
    short_json: Path
    long_json: Path
    short_norm: Path
    long_norm: Path
    short_feats: Path
    long_feats: Path
    features_meta: Path
    query_json: dict[str, Path]
    query_norm: dict[str, Path]
    query_feats: dict[str, Path]


def data_paths(
    collection: str,
    *,
    work_root: str | Path = _CONTAINER_ROOT,
    data_dir: str | Path | None = None,
) -> DataPaths:
    """Resolve the data phase's inputs and outputs for `collection`.

    `data.ipynb` runs before any method exists, so it cannot go through a config; this is the
    same service keyed on the collection alone. Synthetic query sets are discovered rather
    than assumed — OEB has none, and asking for them must not invent a path.
    """
    work_root = Path(work_root)
    directory = Path(data_dir) if data_dir else work_root / "data" / "processed"

    short_json = directory / f"{collection}_resumen.json"
    long_json = directory / f"{collection}_texto.json"
    missing = [str(p) for p in (short_json, long_json) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"{collection}: corpus file(s) not found: " + ", ".join(missing))

    synthetic = {}
    for queryset in QUERY_SETS:
        if queryset in _DECLARED_QUERY_SETS:
            continue
        candidate = directory / f"{collection}_{queryset}.json"
        if candidate.exists():
            synthetic[queryset] = candidate

    return DataPaths(
        collection=collection,
        data_dir=directory,
        short_json=short_json,
        long_json=long_json,
        short_norm=directory / f"{collection}_short_norm.parquet",
        long_norm=directory / f"{collection}_long_norm.parquet",
        short_feats=directory / f"{collection}_short_feats.parquet",
        long_feats=directory / f"{collection}_long_feats.parquet",
        features_meta=directory / f"{collection}_features_meta.json",
        query_json=synthetic,
        query_norm={
            queryset: directory / f"{collection}_{queryset}_norm.parquet" for queryset in synthetic
        },
        query_feats={
            queryset: directory / f"{collection}_{queryset}_feats.parquet" for queryset in synthetic
        },
    )


def _input_shape(inputs: dict[str, Path], config_path: Path) -> tuple[str, str, str | None]:
    """Identify which of the three input shapes this config uses."""
    for short_key, long_key, template in _INPUT_SHAPES:
        if short_key in inputs and long_key in inputs:
            return short_key, long_key, template
    raise KeyError(
        f"{config_path.name}: inputs declares no recognised pair; expected "
        + " or ".join(f"{s}/{l}" for s, l, _ in _INPUT_SHAPES)
    )


def _text_template(short_path: Path, config_path: Path) -> str:
    """Pick the synthetic-query template from the suffix the config already uses."""
    name = short_path.name
    for suffix, template in _TEXT_TEMPLATES:
        if name.endswith(suffix):
            return template
    raise KeyError(
        f"{config_path.name}: cannot derive a query-set path from {name!r}; "
        f"known suffixes are {', '.join(s for s, _ in _TEXT_TEMPLATES)}"
    )


@dataclass(frozen=True)
class RunContext:
    """Everything a notebook is allowed to know about where things live."""

    config_path: Path
    collection: str
    method: str
    queryset: str
    data_dir: Path
    index_dir: Path
    run_dir: Path
    corpus_path: Path
    query_path: Path
    inputs: dict[str, Path]
    retriever_module: str
    retriever_entrypoint: str


def load_run_context(
    config_path: str | Path,
    *,
    queryset: str,
    work_root: str | Path = _CONTAINER_ROOT,
    require_inputs: bool = True,
) -> RunContext:
    """Resolve one config for one query set.

    Raises rather than guessing: an unknown query set, a config that declares no collection
    or no retriever module, and — unless `require_inputs=False` — an input file that is not
    on disk are all errors here, where they are cheap, instead of surfacing later as a
    plausible wrong number.
    """
    config_path = Path(config_path)
    work_root = Path(work_root)

    if queryset not in QUERY_SETS:
        raise ValueError(
            f"unknown query set {queryset!r}; expected one of {', '.join(QUERY_SETS)}"
        )

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    collection = cfg.get("collection")
    if not collection:
        raise KeyError(f"{config_path.name}: declares no collection")

    method = (cfg.get("method") or {}).get("save_as")
    if not method:
        raise KeyError(f"{config_path.name}: declares no method.save_as")

    retriever = cfg.get("retriever") or {}
    module = retriever.get("module")
    if not module:
        raise KeyError(
            f"{config_path.name}: declares no retriever.module. The module is read from the "
            "config, never derived from the filename (D-016)."
        )

    paths = cfg.get("paths") or {}
    data_dir = _rebase(paths.get("data_dir", f"{_CONTAINER_ROOT}/data/processed"), work_root)

    fmt = {"data_dir": str(data_dir), "collection": collection, "queryset": queryset}
    inputs = {k: Path(str(v).format(**fmt)) for k, v in (cfg.get("inputs") or {}).items()}

    short_key, long_key, template = _input_shape(inputs, config_path)
    corpus_path = inputs[long_key]

    role = _DECLARED_QUERY_SETS.get(queryset)
    if role:
        query_path = inputs[short_key if role == "short" else long_key]
    else:
        if template is None:
            template = _text_template(inputs[short_key], config_path)
        query_path = data_dir / template.format(collection=collection, queryset=queryset)

    if require_inputs:
        missing = [str(p) for p in (*inputs.values(), query_path) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"{config_path.name} ({queryset}): input(s) not on disk: " + ", ".join(missing)
            )

    return RunContext(
        config_path=config_path,
        collection=collection,
        method=method,
        queryset=queryset,
        data_dir=data_dir,
        index_dir=work_root / "index" / collection / method,
        run_dir=work_root / "runs" / collection / queryset / method,
        corpus_path=corpus_path,
        query_path=query_path,
        inputs=inputs,
        retriever_module=module.removeprefix(_MODULE_PREFIX),
        retriever_entrypoint=retriever.get("entrypoint", "load"),
    )
