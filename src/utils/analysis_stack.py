"""The analysis stack S6's models and figures run on, pinned and checked (S6 work item 2).

S6 fits mixed models (`statsmodels`) and draws figures (`matplotlib`). Neither sits on the retrieval
path, and neither was pinned anywhere: `requirements.txt` still carries the pre-D-034 stack, and
`index/*/meta.json` stamps no ML stack at all (defect H4). So the versions are pinned **here**, in the
code the generator imports. `require()` refuses to run on anything else, and `stamp()` is the line every
generated S6 table prints in its sources block, so a table cannot silently come from another fit.

The pins are the versions already present in the sprint container `bc3cat-s3`
(`quay.io/jupyter/pytorch-notebook:cuda12-python-3.11.8`), checked on 2026-09-30. Nothing was installed
or upgraded to get them, so no retrieval-path package moved.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

#: Package → exact version. The model and figure packages, and the numeric stack their results depend on.
PINNED = {
    "statsmodels": "0.14.1",
    "patsy": "0.5.6",
    "scipy": "1.13.0",
    "numpy": "1.26.4",
    "pandas": "2.2.2",
    "matplotlib": "3.8.4",
}


def installed() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in PINNED:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = None
    return out


def require() -> None:
    """Fail loud unless every pinned package is installed at its pinned version."""
    have = installed()
    wrong = {n: (have[n], want) for n, want in PINNED.items() if have[n] != want}
    if wrong:
        detail = ", ".join(f"{n} {got or 'absent'} (pinned {want})" for n, (got, want) in wrong.items())
        raise SystemExit(
            f"analysis stack mismatch: {detail}. Run in the sprint container bc3cat-s3 "
            "(src/utils/analysis_stack.py)."
        )


def stamp() -> str:
    """One line for a generated table's sources block."""
    return "Analysis stack: " + ", ".join(f"`{n}` {v}" for n, v in PINNED.items()) + "."
