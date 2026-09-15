"""Migrate configs off hard-coded collection paths — S0 work item 4.

62 of the 76 configs carry their input paths written out literally
(`/work/data/processed/OEB_short_feats.parquet`), so the collection cannot be changed by
setting `collection:`. The other 14 already use `{data_dir}/{collection}_…`; this rewrites
the 62 to match them.

The migration changes how a path is *spelled*, never which file is read. That is checked,
not assumed: every config's inputs are resolved before and after, and any config whose
resolved paths differ is a defect — the script refuses to write.

    python src/utils/migrate_configs.py --check     # resolve and report, write nothing
    python src/utils/migrate_configs.py --apply     # rewrite the 62
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = sorted(glob.glob(str(REPO / "configs" / "*.yaml")))

# The literal spellings to migrate, and the template each becomes. The templates are not
# invented here: they are exactly what the 14 already-parameterised configs use.
REWRITES = {
    "/work/data/processed/OEB_short_feats.parquet": "{data_dir}/{collection}_short_feats.parquet",
    "/work/data/processed/OEB_long_feats.parquet": "{data_dir}/{collection}_long_feats.parquet",
    "/work/data/processed/OEB_features_meta.json": "{data_dir}/{collection}_features_meta.json",
}

# Inside the repo, /work is the repo root (docker-compose mounts it there).
WORK = "/work"


def resolve(cfg: dict, collection: str | None = None) -> dict[str, str]:
    """Resolve every inputs value to a concrete path, as the harness would."""
    paths = cfg.get("paths") or {}
    ctx = {
        "data_dir": paths.get("data_dir", ""),
        "index_root": paths.get("index_root", ""),
        "collection": collection or cfg.get("collection", ""),
    }
    out = {}
    for key, value in (cfg.get("inputs") or {}).items():
        out[key] = str(value).format(**ctx)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the rewritten configs")
    ap.add_argument("--target", default="OE", help="collection to prove parameterisation on")
    args = ap.parse_args()

    changed: list[str] = []
    unchanged: list[str] = []
    failures: list[str] = []
    target_paths: dict[str, str] = {}

    for path in CONFIGS:
        p = Path(path)
        original = p.read_text(encoding="utf-8")
        before = resolve(yaml.safe_load(original))

        migrated = original
        for literal, template in REWRITES.items():
            migrated = migrated.replace(literal, template)

        cfg_after = yaml.safe_load(migrated)
        after = resolve(cfg_after)

        if before != after:
            failures.append(
                f"{p.name}: resolved inputs changed\n  before: {before}\n  after:  {after}"
            )
            continue

        (changed if migrated != original else unchanged).append(p.name)
        for key, value in resolve(cfg_after, collection=args.target).items():
            target_paths.setdefault(value, key)

        if args.apply and migrated != original:
            p.write_text(migrated, encoding="utf-8", newline="\n")

    print(f"configs:            {len(CONFIGS)}")
    print(f"  rewritten:        {len(changed)}")
    print(f"  already templated:{len(unchanged)}")
    print(f"  defects:          {len(failures)}")
    for f in failures:
        print("  ! " + f)
    print()
    print(f"Resolved inputs are byte-identical before and after for all "
          f"{len(changed) + len(unchanged)} configs.")
    print()
    print(f"With collection={args.target!r}, every config resolves to:")
    for value, key in sorted(target_paths.items()):
        on_disk = Path(value.replace(WORK, str(REPO)))
        mark = "exists" if on_disk.exists() else "not built yet"
        print(f"  {key:<16} {value}   [{mark}]")

    if failures:
        raise SystemExit("migration refused: resolved paths changed")
    if not args.apply:
        print("\n(check only — nothing written; re-run with --apply)")


if __name__ == "__main__":
    main()
