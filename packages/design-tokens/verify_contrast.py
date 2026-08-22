#!/usr/bin/env python3
"""Verify every colour pair in tokens.css meets its WCAG requirement.

Runs in CI. Fails the build on a regression.

WHY THIS PARSES tokens.css INSTEAD OF LISTING THE COLOURS
---------------------------------------------------------
A verifier holding its own copy of the palette is a second source of truth,
and this repository's single most repeated defect is two literals in two files
disagreeing. Worse, it is a gate that CANNOT FAIL: editing tokens.css would
leave the verifier still checking the old values and still reporting green.
That exact failure has been shipped here three times.

So the pairs are named here, the VALUES are read from tokens.css, and a token
that goes missing is an error rather than a skip.

Thresholds (WCAG 2.2):
  4.5:1  normal text
  3.0:1  large text (>=18.66px bold / >=24px) and non-text UI boundaries
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).parent / "src" / "tokens.css"

# (foreground token, background token, minimum ratio, why)
PAIRS: list[tuple[str, str, float, str]] = [
    # Text on the three surfaces
    ("--color-foreground", "--color-card", 4.5, "body text on a workspace"),
    ("--color-foreground", "--color-background", 4.5, "body text on the canvas"),
    ("--color-muted-foreground", "--color-card", 4.5, "secondary label"),
    ("--color-muted-foreground", "--color-muted", 4.5, "label on a table header"),
    ("--color-primary", "--color-card", 4.5, "primary text"),
    ("--color-accent", "--color-card", 4.5, "link / primary action text"),
    ("--color-on-primary", "--color-primary", 4.5, "text inside a primary button"),
    ("--color-on-accent", "--color-accent", 4.5, "text inside an accent button"),
    ("--color-on-destructive", "--color-destructive", 4.5, "destructive button text"),
    # Disposition badges — each foreground against its OWN surface, which is
    # the check that a foreground verified only against white would miss.
    ("--color-pass-foreground", "--color-pass-surface", 4.5, "PASS badge"),
    ("--color-review-foreground", "--color-review-surface", 4.5, "REVIEW badge"),
    ("--color-fail-foreground", "--color-fail-surface", 4.5, "FAIL badge"),
    ("--color-neutral-foreground", "--color-neutral-surface", 4.5, "neutral badge"),
    # Disposition text used bare on a workspace (a table cell, not a badge)
    ("--color-pass-foreground", "--color-card", 4.5, "PASS text in a cell"),
    ("--color-review-foreground", "--color-card", 4.5, "REVIEW text in a cell"),
    ("--color-fail-foreground", "--color-card", 4.5, "FAIL text in a cell"),
    # MSD provenance — five treatments, all readable
    ("--color-evidence-verified-foreground", "--color-evidence-verified-surface", 4.5, "MSD verified"),
    ("--color-evidence-calculated-foreground", "--color-evidence-calculated-surface", 4.5, "MSD calculated"),
    ("--color-evidence-prediction-foreground", "--color-evidence-prediction-surface", 4.5, "MSD prediction"),
    ("--color-evidence-recommendation-foreground", "--color-evidence-recommendation-surface", 4.5, "MSD recommendation"),
    ("--color-evidence-warning-foreground", "--color-evidence-warning-surface", 4.5, "MSD warning"),
    # Evidence grades, rendered as text on a workspace
    ("--color-grade-a", "--color-card", 4.5, "evidence grade A"),
    ("--color-grade-b", "--color-card", 4.5, "evidence grade B"),
    ("--color-grade-c", "--color-card", 4.5, "evidence grade C"),
    ("--color-grade-d", "--color-card", 4.5, "evidence grade D"),
    ("--color-grade-x", "--color-card", 4.5, "evidence grade X"),
    # Non-text: WCAG 1.4.11. A control the user cannot locate is a control
    # they cannot operate.
    ("--color-border-control", "--color-card", 3.0, "input / checkbox boundary"),
    ("--color-border-control", "--color-background", 3.0, "control boundary on canvas"),
    ("--color-ring", "--color-card", 3.0, "focus ring on a workspace"),
    ("--color-ring", "--color-background", 3.0, "focus ring on the canvas"),
]

# --color-border is deliberately absent above. It is 1.23:1 and is declared
# decorative-only in tokens.css. This assertion is what stops it drifting into
# use as a control boundary: if someone "fixes" the contrast by darkening it,
# the token has silently changed role and that should be a deliberate edit here.
DECORATIVE_ONLY = {"--color-border": 2.0}  # must stay BELOW this


def _linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def load_tokens(path: Path) -> dict[str, str]:
    """Read `--name: #hex;` declarations from the :root block."""
    text = path.read_text(encoding="utf-8")
    # Stop at the first media query so print/reduced-motion overrides (which
    # legitimately set surfaces to `transparent`) are not mistaken for the
    # screen palette.
    head = text.split("@media", 1)[0]
    found = re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;", head)
    return {name: value for name, value in found}


def main() -> int:
    if not TOKENS.exists():
        print(f"FAIL: {TOKENS} not found", file=sys.stderr)
        return 2

    tokens = load_tokens(TOKENS)
    if not tokens:
        print(f"FAIL: no colour tokens parsed from {TOKENS}", file=sys.stderr)
        return 2

    failures: list[str] = []
    checked = 0

    for fg_name, bg_name, minimum, why in PAIRS:
        missing = [n for n in (fg_name, bg_name) if n not in tokens]
        if missing:
            # A renamed or deleted token must FAIL, never silently skip.
            failures.append(f"  MISSING {', '.join(missing)}  ({why})")
            continue
        ratio = contrast(tokens[fg_name], tokens[bg_name])
        checked += 1
        status = "ok  " if ratio >= minimum else "FAIL"
        line = (
            f"  {status} {ratio:5.2f}:1  (needs {minimum})  "
            f"{fg_name} on {bg_name}  - {why}"
        )
        print(line)
        if ratio < minimum:
            failures.append(line)

    print()
    for name, ceiling in DECORATIVE_ONLY.items():
        if name not in tokens:
            failures.append(f"  MISSING {name} (declared decorative-only)")
            continue
        ratio = contrast(tokens[name], tokens["--color-card"])
        checked += 1
        if ratio >= ceiling:
            failures.append(
                f"  FAIL {name} is {ratio:.2f}:1 — it is documented as decorative "
                f"only. If it is now a control boundary, move it into PAIRS "
                f"deliberately instead of raising it here."
            )
        else:
            print(f"  ok   {name} is {ratio:.2f}:1 - decorative only, as declared")

    print()
    if failures:
        print(f"{len(failures)} contrast failure(s) of {checked} checks:\n")
        for f in failures:
            print(f)
        return 1

    print(f"All {checked} contrast checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
