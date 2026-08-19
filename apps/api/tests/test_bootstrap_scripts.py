r"""The bootstrap shell scripts must not lie about whether a request worked.

🔴 WHAT THIS CATCHES

Two CI runs of the `auth` job died with a bare `Process completed with
exit code 6` -- curl's "could not resolve host" -- immediately after a
user had been created successfully, and printed nothing else. Reasoning
from the source was wrong twice. `bash -x` on the step gave the answer in
one line:

    + status=204000
    ##[error]Process completed with exit code 6.

Three separate defects sat behind that:

1. `scripts/keycloak-bootstrap.sh` carried a LITERAL `\n` where a line
   continuation (backslash, then a real newline) was intended. Bash
   removes the backslash from an unquoted `\n`, leaving the bare word
   `n`. curl accepts a bare word as a URL, so it was handed TWO: the real
   endpoint, and `n`. It fetched the first (204) and then failed to
   resolve the second -- **exit 6**.

2. `-w '%{http_code}'` prints ONCE PER URL. Two URLs therefore produced
   the single string `204000`, which is not a status at all.

3. `expect_status` matched with `case "$got" in 2*)`, so `204000` would
   have been accepted as success. Only curl's exit code stopped the run.
   Had the stray second URL happened to resolve, a **failed role mapping
   would have passed the gate silently** -- and the failure would have
   surfaced four steps later as `invalid_grant`, reading as a wrong
   password.

`api_status` also had no failure branch of its own, which is why nothing
was printed: called as `status="$(api_status ...)"` under `set -e`, a
non-zero curl aborts the whole script with a number and no message.

These tests need no Keycloak, no database and no network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"
BOOTSTRAP = SCRIPTS / "keycloak-bootstrap.sh"

BASH = shutil.which("bash")

# A backslash-n is legitimate inside a format string (printf '%s\n'), a
# regex, or Python source embedded in the script. There it is always
# flanked by a quote or a format character, never by whitespace on the
# left. It is a defect only when it stands as its own shell WORD, because
# bash then strips the backslash and passes a bare `n` to the command.
#
# 🔴 BOTH REVIEWERS REJECTED THE FIRST VERSION OF THIS PATTERN, AND BOTH
# WERE RIGHT. It was `(?<=\s)\\n(?=\s)` -- whitespace required on BOTH
# sides -- so it missed a stray `\n` at end of line, one against a `;` or
# `)`, and `"…/realm"\n  -d` with no space on the left (which bash joins
# into the single word `…/realmn`). The caller also skipped any line
# containing `printf`, which would have skipped
# `curl ... \n -d "$(printf ...)"` outright. A scanner that does not
# enforce its stated invariant is the same shape as the bug it exists to
# catch.
#
# Only the RIGHT-hand boundary is required now. That is deliberately the
# looser, noisier choice: it would also flag embedded Python such as
# `print(f"\n   x")`, where the `\n` is a real newline inside a string.
# MEASURED: zero such lines exist in scripts/*.sh today (four do exist in
# .github/workflows/*.yml, which this test does not scan). A false
# positive here costs one comment; the false negative cost a CI cycle and
# two wrong diagnoses.
_STRAY_ESCAPE = re.compile(r"\\n(?=\s|[;&|)]|$)")


def _stray_escapes(text: str, label: str = "line") -> list[str]:
    """Every line where a literal backslash-n stands as its own shell word."""
    offenders: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if _STRAY_ESCAPE.search(line):
            offenders.append(f"{label}:{lineno}: {line.strip()}")
    return offenders


def _shell_scripts() -> list[Path]:
    found = sorted(SCRIPTS.glob("*.sh"))
    assert found, f"no shell scripts found under {SCRIPTS}"
    return found


@pytest.mark.parametrize("script", _shell_scripts(), ids=lambda p: p.name)
def test_no_literal_backslash_n_as_a_shell_word(script: Path) -> None:
    r"""A `\n` standing alone is a mangled line continuation, not a newline."""
    offenders = _stray_escapes(script.read_text(encoding="utf-8"), script.name)
    assert not offenders, (
        "a literal backslash-n is standing as its own shell word. Bash strips "
        "the backslash and passes a bare `n` to the command -- curl reads that "
        "as an extra URL and exits 6. Use a real line continuation:\n  " + "\n  ".join(offenders)
    )


@pytest.mark.parametrize(
    ("line", "is_a_defect"),
    [
        # The exact line that cost two CI runs.
        (
            r'  status="$(api_status POST "/${R}/users/${s}/role-mappings/realm" \n    -d "[$j]")"',
            True,
        ),
        # 🔴 The three forms the first version of the pattern MISSED.
        (r'  curl -sS "$url" \n', True),  # end of line
        (r'  curl -sS "$url" \n; echo done', True),  # against a delimiter
        (r'  curl ... \n -d "$(printf \'%s\\n\' "$x")"', True),  # a printf on the same line
        (r'  curl "/${R}/realm"\n    -d "$j"', True),  # no space on the left: joins to `realmn`
        # Legitimate: the \n is followed by a quote or another character,
        # never by whitespace, a delimiter, or end of line.
        (r"note() { printf '  %-52s %s\n' \"$1\" \"$2\"; }", False),
        (r"printf '\n}\n' >> \"$OUT\"", False),
        (r'  echo -e "a\nb"', False),
        (r'  status="$(api_status POST "/${R}/users" -d "[$j]")"', False),
    ],
)
def test_the_scanner_catches_what_it_claims_to(line: str, is_a_defect: bool) -> None:
    """Assert the instrument's reach, not just that it runs."""
    found = bool(_stray_escapes(line))
    assert found is is_a_defect, f"{'missed' if is_a_defect else 'falsely flagged'}: {line!r}"


def test_api_status_keeps_curls_error_message() -> None:
    r"""🔴 `curl -s` silences the ERROR TEXT, not just the progress meter.

    The Supervisor caught this and Codex did not. `api_status` captured
    curl's stderr into a file and printed it -- while calling `curl -s`,
    which suppresses the very message being captured. The diagnostic this
    whole change exists to produce would have read `curl said: ` with
    nothing after it, on the exact incident it was written for. `-S`
    restores the message. Measured directly:

        curl -s  ... http://nonexistent.invalid 2>e  ->  e is EMPTY
        curl -sS ... http://nonexistent.invalid 2>e  ->  e is
                     "curl: (6) Could not resolve host: nonexistent.invalid"

    The stub-curl test above cannot catch this, because a shell function
    standing in for curl writes to stderr whatever the flags say.
    """
    body = _extract_function("api_status", BOOTSTRAP.read_text(encoding="utf-8"))
    assert "curl -sS " in body, (
        "api_status must call `curl -sS`. With plain `-s` the captured stderr "
        "is empty and the FAIL diagnostic says nothing:\n" + body
    )


def test_the_curl_error_file_is_not_a_predictable_shared_path() -> None:
    """A fixed name in /tmp is another user's symlink and another run's file."""
    source = BOOTSTRAP.read_text(encoding="utf-8")
    # Comments are excluded on purpose: the script's own commentary names
    # the old path to explain why it went.
    code_lines = [line for line in source.splitlines() if not line.lstrip().startswith("#")]
    # S108 is suppressed below: this names the bad path in order to FORBID
    # it, and is the one place the literal must appear.
    offenders = [line.strip() for line in code_lines if "/tmp/kc-curl-err" in line]  # noqa: S108
    assert not offenders, (
        "the literal /tmp/kc-curl-err is back in executable code. Any local "
        "user can pre-create that path as a symlink, and two concurrent runs "
        "would share it:\n  " + "\n  ".join(offenders)
    )
    assert "mktemp" in source, "the curl error file should come from mktemp"
    assert "CURL_ERR" in source, "the curl error file should be held in CURL_ERR"
    assert "trap " in source, "the temporary file needs a trap so it is removed on exit"


@pytest.mark.parametrize("script", _shell_scripts(), ids=lambda p: p.name)
def test_scripts_parse(script: Path) -> None:
    """`bash -n` every script. A syntax error must not wait for CI to run it."""
    if BASH is None:
        pytest.skip("bash is not available on this host")
    result = subprocess.run(  # noqa: S603 -- BASH is from shutil.which; the argument is a repo path
        [BASH, "-n", str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, f"{script.name} does not parse:\n{result.stderr}"


def _extract_function(name: str, source: str) -> str:
    """Lift one function out of the script so it can be exercised alone.

    The script cannot be sourced: it runs `set -euo pipefail`, demands two
    passwords, and calls a live Keycloak at import time.
    """
    match = re.search(rf"^{name}\(\) \{{$.*?^\}}$", source, re.M | re.S)
    assert match, f"{name} not found in {BOOTSTRAP.name} -- was it renamed?"
    return match.group(0)


@pytest.mark.parametrize(
    ("status", "should_pass"),
    [
        ("204", True),
        ("201", True),
        ("409", False),  # rejected here; tolerated only where a caller says so
        ("500", False),
        ("204000", False),  # 🔴 the concatenation this whole file exists for
        ("000", False),
        ("", False),
        ("20", False),
    ],
)
def test_expect_status_accepts_only_a_three_digit_status(status: str, should_pass: bool) -> None:
    """`204000` must be refused. `case "$got" in 2*)` used to accept it."""
    if BASH is None:
        pytest.skip("bash is not available on this host")
    body = _extract_function("expect_status", BOOTSTRAP.read_text(encoding="utf-8"))
    program = f'{body}\nexpect_status "$1" "a test call"\necho ACCEPTED\n'
    result = subprocess.run(  # noqa: S603 -- BASH is from shutil.which; the program is built above
        [BASH, "-c", program, "bash", status],
        capture_output=True,
        text=True,
        timeout=30,
    )
    accepted = result.returncode == 0 and "ACCEPTED" in result.stdout
    assert accepted is should_pass, (
        f"expect_status({status!r}) "
        f"{'was rejected' if should_pass else 'was ACCEPTED'} "
        f"-- rc={result.returncode} stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )


def test_api_status_reports_a_curl_failure_by_name() -> None:
    """A failing curl must name the request, not abort on a bare number."""
    if BASH is None:
        pytest.skip("bash is not available on this host")
    body = _extract_function("api_status", BOOTSTRAP.read_text(encoding="utf-8"))
    # A stand-in curl that fails the way the real one did: exit 6, and a
    # -w that has already emitted a code for the URL it did reach.
    program = (
        'curl() { printf "204000"; echo "curl: (6) Could not resolve host: n" >&2; '
        "return 6; }\n"
        # CURL_ERR is set at the top of the real script; the harness has to
        # supply it too, because api_status redirects stderr into it.
        'KC_URL="http://localhost:8080"\nTOKEN="x"\nCURL_ERR="$(mktemp)"\n'
        f"{body}\n"
        'set +e\ncode="$(api_status POST /evercoat/users)"\nrc=$?\nset -e\n'
        'echo "rc=${rc} code=${code}"\n'
    )
    result = subprocess.run(  # noqa: S603 -- BASH is from shutil.which; the program is built above
        [BASH, "-c", program], capture_output=True, text=True, timeout=30
    )
    assert "rc=6" in result.stdout, (
        "api_status must propagate curl's exit code to its caller, so `set -e` "
        f"still aborts the run. Got: {result.stdout!r}"
    )
    assert "FAIL:" in result.stderr, (
        "a curl failure inside api_status must announce itself. Two CI runs "
        "printed nothing at all. Got stderr: " + repr(result.stderr)
    )
    assert "/evercoat/users" in result.stderr, (
        "the diagnosis must name the URL that failed, or it does not save the "
        "next reader a guess. Got stderr: " + repr(result.stderr)
    )
