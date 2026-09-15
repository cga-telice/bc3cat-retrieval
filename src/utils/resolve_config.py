"""Resolve one config's inputs from the config alone — S0 exit criterion 5.

The criterion asks that a config *parameterised on* `collection: "OE"` resolve its inputs
to the OE files, proven by a dry run rather than by reading the YAML. `migrate_configs.py`
cannot prove that: its `--target` flag overrides `collection:` by design, because its job is
to prove the *templates* expand, not that any particular config carries a collection. Audit
finding F1.

This reads one config and nothing else. Whatever `collection:` says is what the paths say.

    python src/utils/resolve_config.py configs/bm25_unigram_params__k1-0.60__b-0.35__OE.yaml

A path marked `not built yet` is not a failure here: the criterion is about resolution, and
the OE feature files are built in S1.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]

# Inside the repo, /work is the repo root (docker-compose mounts it there).
WORK = "/work"


def resolve(cfg: dict) -> dict[str, str]:
    """Resolve every inputs value to a concrete path, using only what the config declares."""
    paths = cfg.get("paths") or {}
    ctx = {
        "data_dir": paths.get("data_dir", ""),
        "index_root": paths.get("index_root", ""),
        "collection": cfg.get("collection", ""),
    }
    return {k: str(v).format(**ctx) for k, v in (cfg.get("inputs") or {}).items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("configs", nargs="+", help="config files to resolve")
    args = ap.parse_args()

    for path in args.configs:
        p = Path(path)
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        collection = cfg.get("collection")
        if not collection:
            raise SystemExit(f"{p.name}: declares no collection")

        print(f"{p.name}")
        print(f"  collection:     {collection!r}  (from the config, nothing overriding it)")
        for key, value in sorted(resolve(cfg).items()):
            on_disk = Path(value.replace(WORK, str(REPO)))
            mark = "exists" if on_disk.exists() else "not built yet"
            print(f"  {key:<16} {value}   [{mark}]")
        print()


if __name__ == "__main__":
    main()
