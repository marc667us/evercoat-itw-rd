#!/usr/bin/env python3
"""Report a suite as three numbers, and refuse to call a skip a pass.

🔴 WHY AN EXIT CODE IS NOT AN ANSWER

A pytest run where every test skipped exits 0. So does a run where every
test passed. The two are indistinguishable from the outside, and a suite
that skips itself because its environment was never wired reads in CI as
a green tick over nothing at all.

That is not hypothetical here. `tests/integration/test_auth_end_to_end.py`
skips when no Keycloak is configured -- correct on a laptop, catastrophic
in CI, where the whole point of the job is that Keycloak IS configured.
The same shape has already been shipped in this workspace: a live suite
that reported `passed=0` while nothing had run, and a report of zero that
was indistinguishable from a broken deploy.

So: passed, failed and skipped are three states, reported as three
numbers. `--allow-skips` exists for suites where skipping is legitimate;
without it, a single skip fails the step.

Usage:
    assert-suite-ran.py <junit.xml> [--allow-skips] [--min-passed N]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    allow_skips = "--allow-skips" in argv
    min_passed = 1
    for arg in argv[1:]:
        if arg.startswith("--min-passed"):
            min_passed = int(arg.split("=", 1)[1])

    if not args:
        print(__doc__)
        return 2

    report = Path(args[0])
    if not report.is_file():
        # No report at all is the loudest failure of the three. It means
        # pytest died before collection -- an import error, a missing
        # dependency -- and the step that ran it swallowed the exit code.
        print(
            f"FAIL: {report} does not exist. pytest produced no report, which "
            "means it failed before it could run anything.",
            file=sys.stderr,
        )
        return 1

    root = ET.parse(report).getroot()
    suite = root if root.tag == "testsuite" else root[0]

    total = int(suite.get("tests", "0"))
    failures = int(suite.get("failures", "0"))
    errors = int(suite.get("errors", "0"))
    skipped = int(suite.get("skipped", "0"))
    passed = total - failures - errors - skipped

    print(f"passed={passed} failed={failures + errors} skipped={skipped}")

    ok = True
    if skipped and not allow_skips:
        print(
            f"FAIL: {skipped} test(s) SKIPPED. A skip is not a pass -- the "
            "environment they need was not wired, and nothing they cover was "
            "proven. Pass --allow-skips only where skipping is legitimate.",
            file=sys.stderr,
        )
        ok = False
    if failures or errors:
        print(f"FAIL: {failures + errors} test(s) did not pass.", file=sys.stderr)
        ok = False
    if passed < min_passed:
        print(
            f"FAIL: only {passed} test(s) passed; at least {min_passed} was "
            "expected. An empty suite is not a green one.",
            file=sys.stderr,
        )
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
