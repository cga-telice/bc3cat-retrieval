"""Every figure a typed sprint report states appears in a generated artefact (S91 audit F7).

Sprint reports are the implementer's record and are typed; the tables they cite are generated.
`test_generated_prose.py` keeps typed numbers out of the generators. This test closes the other
side: a figure in the report that no generated table prints is a figure nobody computed. Run on
S91's report as first closed (`8845490`) it flags one, `9,380`, a count T1 never printed.

It traces figures, not claims. The S91 audit's F6 ("resamples without them return a zero delta")
states a result without a number and would pass; that class stays with the auditor.

A *figure* is a decimal (`0.2808`, `85.6 %`) or a thousands-grouped count (`16,980`), sign ignored.
Bare small integers (`6 of 26`, section numbers, amendment IDs) are not checked: they are too
ambiguous to match and too many are labels rather than results. Digests and commits are not
numbers here. A figure passes if it appears anywhere in the report's cited sources.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs" / "synthetic-oe"

#: report → the generated artefacts its figures may come from.
REPORTS = {
    "sprints/SPRINT_S91_REPORT.md": [
        "results/S91/*.md",
        # Cited for S3's coverage figures (finding 7, known-wrong 1, D-037 row).
        "results/S3/overlap/overlap.md",
    ],
    "sprints/SPRINT_S4_REPORT.md": [
        "results/S4/*.md",
        # ColBERT's identity ceiling, cited beside the derived arms' (finding 6).
        "results/S3/e0/ceiling.md",
    ],
    "sprints/SPRINT_S5_REPORT.md": [
        "results/S5/*.md",
    ],
    "sprints/SPRINT_S6_REPORT.md": [
        "results/S6/*.md",
    ],
    "sprints/SPRINT_S7_REPORT.md": [
        "results/S7/*.md",
    ],
    "sprints/SPRINT_S8_REPORT.md": [
        "results/S8/*.md",
    ],
    "sprints/SPRINT_S9_REPORT.md": [
        "results/S9/*.md",
    ],
}

#: Figures in a report: decimals and grouped counts, not inside identifiers, paths or code spans.
FIGURE = re.compile(r"(?<![\w.`$§/@#-])[+\-−]?(\d{1,3}(?:,\d{3})+|\d+\.\d+)(?:\s?%)?(?![\w`])")
#: Figures in a source: anywhere, since a source may print a value inside a run id (`k1-0.60`).
SOURCE = re.compile(r"\d{1,3}(?:,\d{3})+|\d+\.\d+")


def _figures(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for number, line in ((m.group(1), text.count("\n", 0, m.start()) + 1) for m in FIGURE.finditer(text)):
        out.setdefault(number, line)
    return out


@pytest.mark.parametrize("report", sorted(REPORTS))
def test_every_report_figure_is_generated(report):
    path = DOCS / report
    if not path.exists():
        pytest.skip(f"{report} not written")
    known: set[str] = set()
    for pattern in REPORTS[report]:
        files = sorted(DOCS.glob(pattern))
        assert files, f"{report}: source pattern {pattern!r} matches nothing"
        for f in files:
            known |= set(SOURCE.findall(f.read_text(encoding="utf-8")))
    stray = {n: line for n, line in _figures(path.read_text(encoding="utf-8")).items() if n not in known}
    assert not stray, (
        f"{report}: figures no cited source prints — generate them or remove them: "
        + ", ".join(f"{n} (line {line})" for n, line in sorted(stray.items(), key=lambda x: x[1]))
    )


def test_the_check_catches_a_typed_figure(tmp_path):
    """The check is not vacuous: a figure absent from the sources is reported."""
    assert "0.1234" in _figures("the delta is +0.1234 [+0.0100, +0.2000]")
    assert "16,980" in _figures("16,980 of 19,832")
    assert _figures("`k1-0.60`, OEB020$, D-037, S91, `7ee4557f`, 6 of 26") == {}
