"""Make every config declare its retriever explicitly — S0 work item 4, D-016.

Today the retriever is not in the config at all. `retrieve.ipynb` derives it from the
config's *filename* and an alias table written into the notebook:

    base = METHOD_NAME.split("__", 1)[0]          # METHOD_NAME is the config's stem
    alias = {"tfidf_unigram_nostop": "tfidf_unigram",
             "tfidf_char_3_5":       "tfidf_unigram",
             "dense_gte_instrQ":     "dense_gte"}
    import_module(f"retrievers.{alias.get(base, base)}")

So a run is reproducible from (config, code commit) only because the filename happens to
survive, and `method.impl` — which looks like it selects the implementation — does not.
This writes the resolved module into each config, restating the default rather than
changing it, which is what D-016 asks for.

It does not make the config authoritative: the notebook still reads the filename. Wiring
the harness to the declared block is S1.

    python src/utils/declare_retrievers.py          # check
    python src/utils/declare_retrievers.py --apply
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from importlib import import_module
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = sorted(glob.glob(str(REPO / "configs" / "*.yaml")))
RETRIEVERS = REPO / "src" / "retrievers"
sys.path.insert(0, str(REPO / "src"))

# Copied verbatim from dynamic_load_retriever() in src/retrieve.ipynb.
ALIAS = {
    "tfidf_unigram_nostop": "tfidf_unigram",
    "tfidf_char_3_5": "tfidf_unigram",
    "dense_gte_instrQ": "dense_gte",
}


def resolved_module(config_path: Path) -> str:
    base = config_path.stem.split("__", 1)[0]
    return ALIAS.get(base, base)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    added, present, missing = [], [], []

    for path in CONFIGS:
        p = Path(path)
        module = resolved_module(p)
        if not (RETRIEVERS / f"{module}.py").exists():
            missing.append((p.name, module))
            continue
        # Import it exactly as the notebook does, rather than grepping for `def load`:
        # the phrase variants are shims that re-export it with `from .tfidf_unigram import *`.
        try:
            mod = import_module(f"retrievers.{module}")
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            missing.append((p.name, f"{module} ({type(exc).__name__}: {exc})"))
            continue
        if not hasattr(mod, "load"):
            missing.append((p.name, f"{module} (no load())"))
            continue

        original = p.read_text(encoding="utf-8")
        cfg = yaml.safe_load(original)
        if "retriever" in cfg:
            present.append((p.name, (cfg["retriever"] or {}).get("module")))
            continue

        block = {"module": f"src.retrievers.{module}", "entrypoint": "load"}
        if original.lstrip().startswith("{"):
            new_cfg = dict(cfg)
            new_cfg["retriever"] = block
            text = json.dumps(new_cfg, indent=2, ensure_ascii=False) + "\n"
        else:
            text = original.rstrip("\n") + (
                "\n\nretriever:\n"
                f"  module: {block['module']}\n"
                f"  entrypoint: {block['entrypoint']}\n"
            )

        # The only permitted difference is the new key.
        check = yaml.safe_load(text)
        if {k: v for k, v in check.items() if k != "retriever"} != cfg:
            raise SystemExit(f"{p.name}: rewrite changed something other than `retriever`")
        if check["retriever"] != block:
            raise SystemExit(f"{p.name}: retriever block did not round-trip")

        added.append((p.name, block["module"]))
        if args.apply:
            p.write_text(text, encoding="utf-8", newline="\n")

    print(f"configs:                  {len(CONFIGS)}")
    print(f"  already declared:       {len(present)}")
    print(f"  declaration added:      {len(added)}")
    print(f"  unresolvable:           {len(missing)}")
    for name, mod in missing:
        print(f"    ! {name} -> retrievers.{mod}")
    print()
    by_module: dict[str, int] = {}
    for _, mod in added:
        by_module[mod] = by_module.get(mod, 0) + 1
    for mod, n in sorted(by_module.items()):
        print(f"  {n:>3}  {mod}")
    if missing:
        raise SystemExit("some configs resolve to a module that does not exist")
    if not args.apply:
        print("\n(check only — nothing written; re-run with --apply)")


if __name__ == "__main__":
    main()
