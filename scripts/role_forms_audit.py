"""For every role, does it have a control for every WRITE permission it holds?

The inverse of the defect this project keeps finding. "A permission with no
enforcement point" is a gate nobody passes; this is the other side -- a
permission a person HOLDS with nothing in the product to press. Both leave a
capability the catalogue claims and the running application lacks.

Nothing here is hand-kept. Roles and grants come from the database, gates from
the API source, controls from the web source. A list of "known gaps" in a file
would be wrong within a week and would go on passing.

WHAT A "CONTROL" MEANS HERE, AND WHAT THIS CANNOT SEE
----------------------------------------------------
A permission counts as having a control when its code appears anywhere in the
web application's own `.tsx`. That is deliberately crude, and it is crude in
the safe direction: it under-reports gaps rather than inventing them. It cannot
tell a gated button from a permission named in a comment, and it cannot tell a
control a person can actually reach from one rendered on a page nothing links
to. Treat a clean run as "nothing obviously missing", never as "every role can
do everything it holds" -- for that, press the thing.

It also says nothing about READ permissions: a role holding `material.view`
needs a page, not a form, and `READ_ONLY` below filters those out.

USAGE
-----
    python scripts/role_forms_audit.py

The database is reached through `docker exec`, because the schema this reads --
`core.roles`, `core.role_permissions`, `core.permissions` -- is seeded into the
development container. Override the container and database with
`EVERCOAT_PG_CONTAINER` and `POSTGRES_DB` if yours are named differently.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

# The repository root, derived -- `scripts/` is one level down. A literal path
# here would make the tool run on exactly one machine, which is most of the
# reason the last version of it was never committed.
ROOT = pathlib.Path(__file__).resolve().parent.parent
API = ROOT / "apps" / "api" / "app" / "api"
WEB = ROOT / "apps" / "web"

CONTAINER = os.environ.get("EVERCOAT_PG_CONTAINER", "evercoat-postgres")
DATABASE = os.environ.get("POSTGRES_DB", "evercoat_itw_rd")
DB_USER = os.environ.get("EVERCOAT_PG_USER", "postgres")

# Permissions that gate a READ. A role holding one needs a page, not a form.
READ_ONLY = re.compile(r"\.(view|view_cost|portfolio)$|^analytics\.|^report\.")


def psql(sql: str) -> list[str]:
    out = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-U",
            DB_USER,
            "-d",
            DATABASE,
            "-t",
            "-A",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def write_gates() -> dict[str, set[str]]:
    """``{permission: {route label, ...}}`` for every WRITE route in the API."""
    gates: dict[str, set[str]] = {}
    for path in sorted(API.glob("*.py")):
        src = path.read_text(encoding="utf-8")
        for block in re.split(r"\n@router\.", src)[1:]:
            verb = block.split("(", 1)[0].strip().lower()
            if verb not in {"post", "put", "patch", "delete"}:
                continue
            # Only the signature, not the body: a permission named in a
            # docstring is a mention, not a gate.
            body = block[: block.find('"""')] if '"""' in block else block
            perms = re.search(r"require_permission\(([^)]*)\)", body, re.DOTALL)
            if not perms:
                continue
            route = re.match(r'\s*"([^"]*)"', block)
            label = f"{path.stem}{route.group(1) if route else ''}"
            for code in re.findall(r'"([a-z_]+\.[a-z_]+)"', perms.group(1)):
                gates.setdefault(code, set()).add(label)
    return gates


def controls() -> str:
    """Every `.tsx` under `app/` and `components/` -- where a control lives."""
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for directory in ("app", "components")
        for p in (WEB / directory).rglob("*.tsx")
        if ".test." not in p.name
    )


def main() -> int:
    ui = controls()
    gates = write_gates()

    # The guard on the guard. Both regexes parse source that is free to be
    # restructured, and a run that found nothing would print a table of zeroes
    # and read exactly like a clean bill of health.
    if not gates:
        print(
            "ERROR: no permission-gated write routes found -- has the API "
            "route or dependency style changed?",
            file=sys.stderr,
        )
        return 2
    if len(ui) < 10_000:
        print(
            f"ERROR: only {len(ui)} characters of web source found -- is the "
            "path right?",
            file=sys.stderr,
        )
        return 2

    rows = psql(
        "SELECT r.code, p.code FROM core.roles r "
        "JOIN core.role_permissions rp ON rp.role_id = r.id "
        "JOIN core.permissions p ON p.id = rp.permission_id ORDER BY 1, 2"
    )
    if not rows:
        print("ERROR: no role grants found -- is the database seeded?", file=sys.stderr)
        return 2

    held: dict[str, list[str]] = {}
    for line in rows:
        role, perm = line.split("|")
        held.setdefault(role, []).append(perm)

    print(f"{'role':<32}{'writes':>7}{'with control':>14}{'WITHOUT':>9}")
    print("-" * 78)
    missing: dict[str, set[str]] = {}
    for role, perms in sorted(held.items()):
        writes = [p for p in perms if not READ_ONLY.search(p) and p in gates]
        have, lack = [], []
        for perm in writes:
            (have if f'"{perm}"' in ui else lack).append(perm)
        print(f"{role:<32}{len(writes):>7}{len(have):>14}{len(lack):>9}")
        for perm in lack:
            missing.setdefault(perm, set()).add(role)

    print("\nWRITE PERMISSIONS SOMEBODY HOLDS WITH NO CONTROL IN THE PRODUCT")
    print("-" * 78)
    if not missing:
        print("  (none)")
    for perm, roles in sorted(missing.items()):
        print(f"  {perm}")
        print(f"      routes : {', '.join(sorted(gates.get(perm, {'?'})))}")
        print(f"      held by: {', '.join(sorted(roles))}")

    # Not a non-zero exit on findings: this is a report, and the gaps it finds
    # are usually a slice of work rather than a broken build.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
