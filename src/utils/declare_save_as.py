"""Declare `method.save_as` in the configs that only imply it — S1, D-008.

D-008 fixes the run layout as `runs/{collection}/{queryset}/{method}`, where `{method}` is
the config's `method.save_as`. Nine of the 77 configs never declared it: they worked only
because the harness took the method name from the config's *filename*, which is the same
coupling S0 recorded as finding 1.

In all 68 configs that do declare it, `save_as == method.name == filename stem`, without a
single mismatch. This copies `method.name` into `save_as` for the nine, and refuses to write
unless that identity holds for the config in hand — so the value is never invented.

    python src/utils/declare_save_as.py --check     # report, write nothing
    python src/utils/declare_save_as.py --write

The edit is textual, not a re-serialisation: all nine of these are hand-written YAML with
comments, and dumping them back through a parser would rewrite them as JSON and drop every
comment. One line is inserted after `method.name`, at its indentation, and nothing else in
the file is touched.

Verification mirrors S0's migrations: every config is parsed before and after, and nothing
but the one intended key may differ.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"


def needs_save_as(cfg: dict) -> bool:
    return not (cfg.get("method") or {}).get("save_as")


def planned_value(path: Path, cfg: dict) -> str:
    """The value to declare, or an explanation of why it cannot be declared safely."""
    method = cfg.get("method") or {}
    name = method.get("name")
    if not name:
        raise SystemExit(f"{path.name}: declares neither method.save_as nor method.name")
    if name != path.stem:
        raise SystemExit(
            f"{path.name}: method.name {name!r} differs from the filename stem "
            f"{path.stem!r}; the two are identical in every config that declares save_as, "
            "so this one is not safe to migrate automatically"
        )
    return name


def insert_save_as(text: str, value: str, path: Path) -> str:
    """Insert `save_as` right after `method.name`, keeping the file's own formatting.

    JSON-style configs (63 of the 77) are re-serialised safely, because they carry no
    comments; the YAML ones are edited as text so that theirs survive.
    """
    if text.lstrip().startswith("{"):
        cfg = json.loads(text)
        cfg["method"]["save_as"] = value
        return json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"

    lines = text.splitlines(keepends=True)
    in_method = False
    for i, line in enumerate(lines):
        if line.startswith("method:"):
            in_method = True
            continue
        if in_method:
            stripped = line.lstrip()
            if line.strip() and not line[0].isspace():
                break  # left the method block without finding name
            if stripped.startswith("name:"):
                indent = line[: len(line) - len(stripped)]
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                lines.insert(i + 1, f'{indent}save_as: "{value}"{newline}')
                return "".join(lines)
    raise SystemExit(f"{path.name}: no `name:` line inside the method block to anchor on")


def only_save_as_changed(before: dict, after: dict) -> bool:
    """True when `after` is `before` plus method.save_as and nothing else."""
    stripped = copy.deepcopy(after)
    stripped["method"].pop("save_as", None)
    return stripped == before


def main() -> None:
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report and write nothing")
    mode.add_argument("--write", action="store_true")
    args = ap.parse_args()

    paths = sorted(CONFIGS.glob("*.yaml"))
    if not paths:
        raise SystemExit(f"no configs under {CONFIGS}")

    pending, defects = [], 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        before = yaml.safe_load(text)
        if not needs_save_as(before):
            continue

        value = planned_value(path, before)
        new_text = insert_save_as(text, value, path)
        after = yaml.safe_load(new_text)

        if after["method"].get("save_as") != value:
            print(f"  DEFECT {path.name}: the edit did not take")
            defects += 1
            continue
        if not only_save_as_changed(before, after):
            print(f"  DEFECT {path.name}: more than method.save_as would change")
            defects += 1
            continue

        pending.append((path, new_text, value))
        print(f"  {path.name:40} method.save_as <- {value!r}")

    print(f"\n{len(paths)} configs, {len(pending)} to migrate, {defects} defects")
    if defects:
        raise SystemExit("refusing to write while defects stand")

    if args.check or not pending:
        return

    for path, new_text, _ in pending:
        path.write_text(new_text, encoding="utf-8", newline="")
    print(f"written: {len(pending)}")


if __name__ == "__main__":
    main()
