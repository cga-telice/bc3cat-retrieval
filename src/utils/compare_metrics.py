"""Compare two dual-target metric sets exactly — S1 exit criterion 3.

The migration of S1 changes plumbing, never method, so the metrics it produces must be the
ones it produced before. "Must be" is exact: no tolerance is applied, because a plumbing
change has no reason to move a figure at all, and a tolerance is how a real regression gets
waved through.

Rows are matched on `(target, scope)` — the two keys `metrics.ipynb` writes every row with —
so a row that disappears is reported as missing rather than silently skipped, which is how a
smaller run could otherwise pass as an equal one.
"""

from __future__ import annotations

from typing import Any, Iterable

#: Fields compared on every row. `queries` is in here on purpose: a different sample size is
#: a different experiment even when every score happens to match.
COMPARED = ("queries", "Acc@1", "Recall@5", "Recall@10", "MRR", "nDCG@10")


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("target", "")), str(row.get("scope", ""))


def diff_metrics(
    expected: Iterable[dict], actual: Iterable[dict], *, allow_extra_scopes: bool = False
) -> list[str]:
    """Return one line per difference; an empty list means the two are identical.

    `allow_extra_scopes` tolerates rows the expected set does not have, and nothing else: a
    missing row and a moved figure are still differences. S1 adds slices (per condition, per
    modification type, per count, per subchapter, per family-size tercile) that the fixture
    predates, and those additions must not be read as the migration having changed a number.
    """
    expected_rows = {_key(r): r for r in expected}
    actual_rows = {_key(r): r for r in actual}
    differences: list[str] = []

    for key in sorted(expected_rows.keys() - actual_rows.keys()):
        differences.append(f"missing row: target={key[0]} scope={key[1]}")

    if not allow_extra_scopes:
        for key in sorted(actual_rows.keys() - expected_rows.keys()):
            differences.append(f"unexpected row: target={key[0]} scope={key[1]}")

    for key in sorted(expected_rows.keys() & actual_rows.keys()):
        want, got = expected_rows[key], actual_rows[key]
        for field in COMPARED:
            if want.get(field) != got.get(field):
                differences.append(
                    f"target={key[0]} scope={key[1]} {field}: "
                    f"expected {want.get(field)!r}, got {got.get(field)!r}"
                )

    return differences
