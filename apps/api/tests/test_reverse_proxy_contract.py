"""The proxy and the API must agree about the `/api` prefix.

🔴 WHAT THIS CATCHES

`infrastructure/compose/Caddyfile` carried `uri strip_prefix /api` inside
its `handle /api/*` block, while `app/main.py` mounts every router UNDER
`/api` and `apps/web/lib/api/client.test.ts` asserts the client asks for
`/api/materials` unstripped.

So the proxy rewrote `/api/projects` to `/projects`, which the API does
not serve. **Every API route would have 404'd through the reverse proxy.**

Nothing caught it, and nothing could have:

  * CI talks to uvicorn directly, never through Caddy;
  * the full compose stack has never been up at once (`CLAUDE.md` §15);
  * `tsc`, `ruff` and `mypy` cannot see across a Caddyfile.

This is the platform's recurring shape — *two literals in two files
cannot be type-checked into agreement* — applied to the one hop where a
mismatch takes the entire API offline. The rule was copied from the
`/auth` block, where stripping IS correct because Keycloak serves
`/realms/...` at its root.

It needs no database, no network and no running proxy.
"""

from __future__ import annotations

import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
CADDYFILE = REPO_ROOT / "infrastructure" / "compose" / "Caddyfile"
# 🔴 THE FILE THAT ACTUALLY FRONTS THE DEPLOYED DEMONSTRATION. I110 was
# invisible for as long as it was because every assertion in this file
# read the OTHER one.
TUNNEL_CADDYFILE = REPO_ROOT / "infrastructure" / "compose" / "Caddyfile.tunnel"
MAIN_PY = API_ROOT / "app" / "main.py"


def _caddyfile() -> str:
    assert CADDYFILE.exists(), f"the reverse-proxy config is missing: {CADDYFILE}"
    return CADDYFILE.read_text(encoding="utf-8")


def _block(source: str, opener: str) -> str:
    """The body of one `handle ... {` block, by brace matching."""
    start = source.index(opener)
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"unterminated block starting at {opener!r}")


def test_the_api_still_mounts_under_the_api_prefix() -> None:
    """The premise of every assertion below.

    If the API is ever re-mounted at the root, this test fails FIRST and
    says so, rather than the proxy assertions silently becoming wrong in
    the other direction.
    """
    source = MAIN_PY.read_text(encoding="utf-8")
    mounts = re.findall(r'include_router\([^)]*prefix="(/[^"]*)"', source, re.S)
    api_mounts = [prefix for prefix in mounts if prefix.startswith("/api")]

    assert api_mounts, (
        "no router is mounted under /api any more. If that is deliberate, "
        "the Caddyfile's /api handling must change with it -- and this test "
        "is the reminder that the two files have to move together."
    )


def test_the_proxy_does_not_strip_the_prefix_the_api_expects() -> None:
    block = _block(_caddyfile(), "handle /api/*")

    assert "strip_prefix /api" not in block, (
        "the reverse proxy strips /api while the API mounts its routers "
        "UNDER /api, so every route 404s through the proxy. This is the "
        "defect the file's own comment now documents; do not reinstate it."
    )
    assert "reverse_proxy api:8000" in block, (
        "the /api block no longer forwards to the API service at all"
    )


def test_the_auth_block_still_strips_because_keycloak_serves_at_its_root() -> None:
    """The positive case, so the rule is understood rather than obeyed.

    A blanket "never strip_prefix" would break identity: Keycloak serves
    `/realms/...` at its root, so `/auth/realms/x` MUST become
    `/realms/x`. The difference between the two blocks is the point.
    """
    block = _block(_caddyfile(), "handle /auth/*")

    assert "strip_prefix /auth" in block, (
        "the /auth block stopped stripping its prefix; Keycloak serves "
        "/realms/... at its root, so /auth/realms/x would 404"
    )


def test_metrics_are_refused_at_the_edge() -> None:
    """`/metrics` is unauthenticated in the API and must not be public.

    It enumerates every route template and its traffic — free
    reconnaissance. The Caddyfile previously CLAIMED metrics were kept off
    the internet while providing no `/metrics` handler at all, and the
    `/api/*` strip_prefix meant `/api/metrics` reached it regardless.
    """
    source = _caddyfile()
    assert "handle /metrics" in source, (
        "there is no /metrics handler, so the request falls through to the "
        "catch-all. Refuse it explicitly: a route that is private by "
        "accident is not private."
    )

    block = _block(source, "handle /metrics")
    assert "respond 404" in block, f"the /metrics block does not refuse the request: {block!r}"
    assert "reverse_proxy" not in block, (
        "the /metrics block forwards to a backend; the API's Prometheus "
        "endpoint has no authentication of its own"
    )


# ---------------------------------------------------------------------------
# I110 — the five headers SECURITY.md claims, in the file that actually serves
# ---------------------------------------------------------------------------


def _header_block(text: str) -> str:
    """The contents of the top-level `header { ... }` directive."""
    start = text.index("\theader {")
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError("unterminated header block")


REQUIRED_HEADERS = (
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "X-Frame-Options",
    "Referrer-Policy",
    "Content-Security-Policy",
)


def test_both_proxies_send_the_headers_security_md_claims() -> None:
    """🔴 I110: THE DEPLOYED SITE SENT NONE OF THE FIVE.

    `SECURITY.md:234` claimed HSTS, nosniff, X-Frame-Options, Referrer-Policy
    and a CSP. The repository's own `Caddyfile` carried three; the file in
    front of the demonstration tunnel — `Caddyfile.tunnel` — had no `header`
    block at all, and that is the one serving traffic. `curl -D -` against the
    deployed site returned none of the five, twice, a day apart.

    ⚠️ THE POINT IS *BOTH* FILES. Asserting only `Caddyfile` is what let this
    survive: every existing test in this module reads that file, and the
    deployment reads the other one. A header present in the config nobody runs
    is not a header.
    """
    for label, path in (("Caddyfile", CADDYFILE), ("Caddyfile.tunnel", TUNNEL_CADDYFILE)):
        block = _header_block(path.read_text(encoding="utf-8"))
        for header in REQUIRED_HEADERS:
            assert header in block, (
                f"{label} does not send {header}. SECURITY.md §13 claims it, and "
                "a claim the proxy does not implement is the "
                "comment-asserts-a-rule-that-does-not-exist defect."
            )


def test_the_two_proxies_send_the_same_headers() -> None:
    """Two literals in two files cannot be type-checked into agreement.

    `Caddyfile.tunnel` cannot `import` the shared block: it is mounted
    standalone into its container and an import would need the imported file
    mounted beside it. So the duplication is deliberate, and this is what stops
    it drifting — which is exactly how one of them ended up with no headers at
    all.
    """
    compose = _header_block(CADDYFILE.read_text(encoding="utf-8"))
    tunnel = _header_block(TUNNEL_CADDYFILE.read_text(encoding="utf-8"))

    def directives(block: str) -> list[str]:
        out = []
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line in ("header {", "}"):
                continue
            out.append(line)
        return sorted(out)

    assert directives(compose) == directives(tunnel), (
        "the two proxies send different headers. They front the same "
        "application and a browser cannot tell which one answered it."
    )


def test_the_csp_does_not_pretend_to_control_scripts() -> None:
    """🔴 A PERMISSIVE POLICY WOULD MAKE THE DOCUMENT TRUE AND THE CONTROL WORTHLESS.

    Measured on this build: 13 inline `<script>` blocks, and 13 of 13 routes
    PRERENDERED (`○ Static` / `● SSG`, zero `ƒ Dynamic`). A nonce is
    per-request and prerendered HTML is written at build time, so it cannot
    carry one. That leaves `'unsafe-inline'` — which enforces nothing about
    scripts while letting SECURITY.md claim a CSP — or a nonce, which blocks
    every inline script on every page and blanks the app.

    Neither ships. The CSP carries only directives that are genuinely enforced
    and unrelated to inline scripts. This test fails if somebody later adds
    `'unsafe-inline'` to buy the appearance of a script policy.

    ⚠️ It also fails if somebody adds a real `script-src` WITHOUT doing the
    dynamic-rendering work (I116) — which is the point: that change has to be
    made deliberately, with the rendering change, not slipped into a config.
    """
    for label, path in (("Caddyfile", CADDYFILE), ("Caddyfile.tunnel", TUNNEL_CADDYFILE)):
        block = _header_block(path.read_text(encoding="utf-8"))
        # ⚠️ SKIP COMMENTS. The block explains at length why there is no
        # script-src, and those lines contain the words -- a naive scan reads
        # the explanation instead of the directive, which is its own small
        # version of measuring the wrong thing.
        csp = next(
            line
            for line in block.splitlines()
            if "Content-Security-Policy" in line and not line.strip().startswith("#")
        )
        assert "unsafe-inline" not in csp, (
            f"{label}'s CSP contains 'unsafe-inline'. That makes SECURITY.md's "
            "claim technically true and the control worthless — the exact trade "
            "I110 was raised to refuse."
        )
        assert "unsafe-eval" not in csp, f"{label}'s CSP contains 'unsafe-eval'"
        assert "script-src" not in csp, (
            f"{label}'s CSP declares script-src. Every route is prerendered, so "
            "a nonce cannot be stamped and this would block every inline script "
            "on every page. Doing it properly is I116 — the dynamic-rendering "
            "change — not a config edit."
        )
        # And the four that ARE enforced must still be there.
        for directive in ("frame-ancestors", "base-uri", "form-action", "object-src"):
            assert directive in csp, f"{label}'s CSP lost {directive}"
