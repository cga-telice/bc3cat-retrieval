"""No notebook builds a path, and no notebook names a collection in its body (D-022).

S1 exit criterion 4 as written says "no literal collection name outside a comment". Read
literally that would forbid the papermill parameters cell, which is exactly where a literal
belongs: it is the notebook's input, the thing papermill overrides, not a path built behind
the caller's back. So the rule enforced here is: **outside the parameters cell and comments,
a collection is never named and a data path is never constructed.**
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The five notebooks S1 migrates. The other four move when S4 needs them (D-022 scope).
MIGRATED = ("data", "features", "index_builder", "retrieve", "metrics")

#: A bare collection name used as a value, e.g. "OEB" or 'OE'.
COLLECTION_LITERAL = re.compile(r"""['"]OEB?['"]|_OEB?_|\bOEB_\w+|\bOE_\w+""")

#: Hand-built data paths: the two directories a notebook must never assemble itself.
BUILT_PATH = re.compile(r"""['"]/work/(data|index|runs)/""")


def body_lines(notebook: str):
    """Every executable line outside the parameters cell, with its cell index."""
    nb = json.loads((REPO / "src" / f"{notebook}.ipynb").read_text(encoding="utf-8"))
    in_docstring = False
    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code" or "parameters" in cell["metadata"].get("tags", []):
            continue
        for line in "".join(cell["source"]).split("\n"):
            stripped = line.strip()
            if stripped.count('"""') == 1:
                in_docstring = not in_docstring
                continue
            if in_docstring or stripped.startswith("#") or not stripped:
                continue
            yield index, stripped


@pytest.mark.parametrize("notebook", MIGRATED)
def test_the_body_never_names_a_collection(notebook):
    offenders = [line for _, line in body_lines(notebook) if COLLECTION_LITERAL.search(line)]

    assert offenders == [], f"{notebook}.ipynb names a collection outside its parameters cell"


@pytest.mark.parametrize("notebook", MIGRATED)
def test_the_body_never_builds_a_data_path(notebook):
    offenders = [line for _, line in body_lines(notebook) if BUILT_PATH.search(line)]

    assert offenders == [], f"{notebook}.ipynb builds a path instead of asking the resolver"


@pytest.mark.parametrize("notebook", MIGRATED)
def test_every_migrated_notebook_has_a_parameters_cell(notebook):
    nb = json.loads((REPO / "src" / f"{notebook}.ipynb").read_text(encoding="utf-8"))

    tagged = [c for c in nb["cells"] if "parameters" in c["metadata"].get("tags", [])]

    assert len(tagged) == 1, f"{notebook}.ipynb needs exactly one papermill parameters cell"


def test_retrieve_no_longer_carries_an_alias_table():
    """The alias table derived the retriever from the config's *filename*, so renaming a
    config silently changed which code ran (S0 finding 1, D-016). Checked against the code
    cells only: the markdown cell says the table is gone, and that mention is the point."""
    nb = json.loads((REPO / "src" / "retrieve.ipynb").read_text(encoding="utf-8"))
    code = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")

    assert "alias" not in code.lower()
    assert 'split("__", 1)' not in code
    assert "ctx.retriever_module" in code
