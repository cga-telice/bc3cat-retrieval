"""No reported number is typed into a generator's prose (S3 audit F1).

The S3 audit found p-values typed into `build_results_e0.py` as string literals that no committed
code produced, beside a table the same script generated with different values. Operating rule 1
says reports are generated from `runs/`, never typed; a literal inside a generator is typing with
extra steps. This test parses each S3 generator and fails on any numeric literal in a string it
could emit, so the only way a number reaches a table is through a computed value.

Exempt: docstrings (never emitted), the cited reference tables (`PREVIOUS`, `OEB_REFERENCE`,
whose provenance is the paper and the review analysis they name), and a short allowlist of
numbers that are definitions rather than results — the 95 % interval level, the 100 % identity
control, a ceiling of 1.0, the top-100 cutoff, a section number and a date. A metric's cutoff
written into its name (`nDCG@10`) is part of the name, not a number.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GENERATORS = [
    "src/utils/build_results_e0.py",
    "src/utils/build_overlap.py",
    "src/utils/build_results_s3.py",
    "src/utils/build_results_s91.py",
    "src/utils/build_results_s4.py",
    "src/utils/build_results_s5.py",
    "src/utils/build_results_s6.py",
]

#: Tables of cited figures whose source is named beside them.
CITED = {"PREVIOUS", "OEB_REFERENCE", "WORDS"}

#: Numbers that are definitions, not results.
ALLOWED = {"1.0", "95 %", "100", "100 %", "20.000", "2.6"}

NUMBER = re.compile(r"(?<![\w.$§/@-])\d+(?:[.,]\d+)*(?:\s?%)?(?![\w-])")


def _docstrings(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _cited(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id in CITED for t in targets):
            ids |= {id(n) for n in ast.walk(node)}
    return ids


def _format_specs(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FormattedValue) and node.format_spec is not None:
            ids |= {id(n) for n in ast.walk(node.format_spec)}
    return ids


def typed_numbers(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree) | _cited(tree) | _format_specs(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            for match in NUMBER.findall(node.value):
                token = match.strip()
                bare = token.rstrip(" %")
                if token in ALLOWED or (bare.isdigit() and int(bare) < 10):
                    continue
                found.append((node.lineno, token))
    return found


@pytest.mark.parametrize("generator", GENERATORS)
def test_no_number_is_typed_into_prose(generator):
    found = typed_numbers(REPO / generator)
    assert not found, (
        f"{generator} types numbers into its output instead of computing them: "
        + ", ".join(f"line {line}: {token!r}" for line, token in found)
    )


def test_the_guard_catches_a_typed_p_value(tmp_path):
    """The exact defect the audit found must fail this test."""
    bad = tmp_path / "bad.py"
    bad.write_text('lines = ["the two exceptions are noise (p = 0.845 and 0.417)"]\n', encoding="utf-8")
    assert [t for _, t in typed_numbers(bad)] == ["0.845", "0.417"]


def test_the_guard_ignores_a_metric_name(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text('lines = ["Acc@1, Recall@k, RR and nDCG@10 are per-query values"]\n', encoding="utf-8")
    assert typed_numbers(ok) == []


def test_the_guard_ignores_computed_values(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text('p = 0.8\nlines = [f"noise (p = {p:.4f})"]\n', encoding="utf-8")
    assert typed_numbers(ok) == []
