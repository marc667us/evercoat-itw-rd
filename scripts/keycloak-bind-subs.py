#!/usr/bin/env python3
"""Bind `core.users.keycloak_sub` to the real Keycloak subjects.

🔴 THE GAP THIS CLOSES

`scripts/seed.py` writes `keycloak_sub = 'demo-chem.demo'` -- a
placeholder, because at seed time no identity provider exists to ask.
`app/core/security.py` resolves a principal with
`WHERE u.keycloak_sub = :sub`, where `:sub` is the token's real subject,
a UUID minted by Keycloak.

Those two never meet. A perfectly valid token -- correct signature,
correct issuer, correct audience, unexpired -- resolves to no row, and
the API answers 403 "not a member of the requested organization". The
authentication is right, the authorization lookup is right, and the
system is unusable, because two literals in two files cannot be
type-checked into agreement.

That is a shape this project has hit repeatedly: nav vs router, landing
vs pack, `release.yml` vs `_deploy-render.yml`. The fix is the same one
each time -- make one side READ the other rather than restate it.

Usage:
    python scripts/keycloak-bind-subs.py keycloak-subs.json

Environment:
    SEED_DATABASE_URL (or DATABASE_URL) -- a connection that may UPDATE
    core.users. RLS does not apply to `core.users` reads by primary key,
    but the connection still needs write rights, so this is an operator
    or migration credential, never the application role.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psycopg


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    subs_path = Path(sys.argv[1])
    if not subs_path.is_file():
        print(f"FAIL: {subs_path} does not exist", file=sys.stderr)
        return 1

    mapping: dict[str, str] = json.loads(subs_path.read_text(encoding="utf-8"))
    if not mapping:
        # An empty map would rebind nothing and report success -- exactly
        # the "absence of evidence rendering as success" failure this
        # codebase has already shipped once.
        print("FAIL: the subject map is empty; nothing was bound", file=sys.stderr)
        return 1

    dsn = os.environ.get("SEED_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("FAIL: set SEED_DATABASE_URL or DATABASE_URL", file=sys.stderr)
        return 1
    dsn = dsn.replace("postgresql+psycopg://", "postgresql://")

    bound = 0
    missing: list[str] = []

    # 🔴 ONE TRANSACTION, COMMITTED ONLY IF EVERY USER BINDS.
    #
    # The first version committed each UPDATE as it went and reported the
    # missing users afterwards, so a partial failure left the database
    # half-rebound: some accounts working, some not, and a rerun of the
    # auth suite in between producing a mixed result nobody could read.
    # Codex caught it. Either all ten identities line up or none of them
    # move.
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        for username, sub in mapping.items():
            # Matched on EMAIL, not on the placeholder sub. The seeder's
            # placeholder is an implementation detail of the seeder; the
            # email is the identity both sides genuinely share, and
            # Keycloak is configured to issue it verified.
            cur.execute(
                """
                UPDATE core.users
                SET keycloak_sub = %s
                WHERE email = %s
                RETURNING id
                """,
                (sub, f"{username}@example.test"),
            )
            if cur.fetchone() is None:
                missing.append(username)
            else:
                bound += 1

        if missing:
            conn.rollback()
        else:
            conn.commit()

    print(f"bound {bound} of {len(mapping)} subjects")

    if missing:
        # Loud, and a failure. A user who exists in Keycloak but not in
        # the database can sign in and then be refused by every route,
        # which presents to the operator as "the app is broken" rather
        # than as "that account was never seeded".
        print(
            "FAIL: no core.users row for: " + ", ".join(missing) + "\n"
            "      They can authenticate and will then be refused by every\n"
            "      route. Run scripts/seed.py first.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
