# -*- coding: utf-8 -*-
"""Seed synthetic demo data.

**Everything created here is SYNTHETIC and labelled as such.** The
organization is named "(Demo)", users are `@example.test`, and the
project reuses the worked example from the source documents (RDP-2026-014
Premium Lightweight Putty). No real Evercoat data is present, and no
undocumented ITW procedure is represented as an official requirement —
the master prompt §10 forbids that explicitly.

Two things this seeder deliberately does NOT do:

* **It does not invent test results.** Synthetic data cannot validate
  scientific correctness, and a database pre-populated with plausible
  adhesion figures makes the calculation engine look verified when it is
  not. Formulas, batches and tests arrive in Slices 3–5 with real
  calculation behind them.

* **It does not create Keycloak users.** Keycloak owns identity; this
  writes `core.users` rows with the `keycloak_sub` values the realm will
  later carry. Seeding credentials in two places is how they drift.

Idempotent: re-running updates rather than duplicating.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid

import psycopg

# ---------------------------------------------------------------------
# ONE SOURCE FOR THE DEMO RECORDS.
#
# The users and pipeline stages below used to be Python literals in this
# file, while apps/web carried its own TypeScript copy for the static
# demonstration build. Two lists, in two languages, that had to agree and
# that nothing could check against each other -- the exact defect this
# repository keeps rediscovering.
#
# Both now read this file. It lives under apps/web because TypeScript can
# only import JSON from inside its own project root, and Python can read
# any path; putting it there costs this script one relative path and buys
# the guarantee that the seeded database and the deployed demonstration
# show the same records.
# ---------------------------------------------------------------------
DEMO_DATA_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "apps"
    / "web"
    / "lib"
    / "demo"
    / "demo-data.json"
)

try:
    _DEMO = json.loads(DEMO_DATA_PATH.read_text(encoding="utf-8"))
except FileNotFoundError:  # pragma: no cover - operator-facing failure
    sys.exit(
        f"demo dataset not found at {DEMO_DATA_PATH}. It is shared with the web "
        "application; do not re-create it here as a Python literal."
    )

DSN = os.getenv(
    "SEED_DATABASE_URL",
    "postgresql://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd",
)

ORG_CODE = "EVERCOAT-DEMO"

# One user per seeded role, so every permission path has a holder. The
# operator's own most-repeated lesson: a role nobody holds is a role with
# no production write path.
USERS = [
    (u["username"], u["display_name"], u["role"]) for u in _DEMO["users"]
]

# The MVP pipeline: 8 stages. The full build expands to 18 — which is an
# INSERT, because stages are configuration rows rather than a code enum.
STAGES = [
    (
        st["stage_code"],
        st["name"],
        st["sequence"],
        st["entry_criteria"],
        st["required_deliverables"],
        st["responsible_role"],
        st["requires_approval"],
        st["approval_role"],
    )
    for st in sorted(_DEMO["stages"], key=lambda x: x["sequence"])
]



def main() -> None:
    with psycopg.connect(DSN, autocommit=False) as conn, conn.cursor() as cur:
        # --- organization -------------------------------------------------
        cur.execute(
            """
            INSERT INTO core.organizations (code, name)
            VALUES (%s, 'ITW Evercoat (Demo)')
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (ORG_CODE,),
        )
        org_id = cur.fetchone()[0]
        print(f"organization: {org_id}")

        # --- users and memberships ---------------------------------------
        user_ids: dict[str, uuid.UUID] = {}
        for username, display, role_code in USERS:
            cur.execute(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (keycloak_sub) DO UPDATE
                    SET display_name = EXCLUDED.display_name
                RETURNING id
                """,
                (f"demo-{username}", f"{username}@example.test", display),
            )
            uid = cur.fetchone()[0]
            user_ids[role_code] = uid

            cur.execute(
                """
                INSERT INTO core.organization_members (organization_id, user_id)
                VALUES (%s, %s)
                ON CONFLICT (organization_id, user_id) DO NOTHING
                RETURNING id
                """,
                (org_id, uid),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "SELECT id FROM core.organization_members "
                    "WHERE organization_id = %s AND user_id = %s",
                    (org_id, uid),
                )
                row = cur.fetchone()
            member_id = row[0]

            cur.execute(
                """
                INSERT INTO core.member_roles (member_id, role_id)
                SELECT %s, id FROM core.roles WHERE code = %s
                ON CONFLICT DO NOTHING
                """,
                (member_id, role_code),
            )
        print(f"users + memberships: {len(USERS)}")

        # --- pipeline stage definitions ----------------------------------
        for code, name, seq, entry, deliverable, role, needs_approval, approver in STAGES:
            cur.execute(
                """
                INSERT INTO workflow.stage_definitions
                    (organization_id, stage_code, name, sequence, entry_criteria,
                     required_deliverables, responsible_role, requires_approval, approval_role)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, stage_code) DO UPDATE
                    SET name = EXCLUDED.name,
                        sequence = EXCLUDED.sequence,
                        entry_criteria = EXCLUDED.entry_criteria,
                        required_deliverables = EXCLUDED.required_deliverables,
                        responsible_role = EXCLUDED.responsible_role,
                        requires_approval = EXCLUDED.requires_approval,
                        approval_role = EXCLUDED.approval_role
                """,
                (org_id, code, name, seq, entry, deliverable, role, needs_approval, approver),
            )
        print(f"pipeline stages: {len(STAGES)}")

        # --- one demo project, from the source's worked example -----------
        cur.execute(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, product_family, status,
                 confidentiality, current_stage, description, technical_objective,
                 priority, lead_user_id, director_user_id)
            VALUES (%s, 'RDP-2026-014', 'Premium Lightweight Automotive Putty',
                    'Polyester Fillers', 'active', 'normal', 'REQUIREMENTS',
                    'DEMO DATA — synthetic project from the source worked example.',
                    'Lower density than benchmark with sanding time below target.',
                    'high', %s, %s)
            ON CONFLICT (organization_id, project_code) DO UPDATE
                SET name = EXCLUDED.name
            RETURNING id
            """,
            (org_id, user_ids["product_development_lead"],
             user_ids["product_development_director"]),
        )
        project_id = cur.fetchone()[0]

        for role_code, project_role in [
            ("product_development_lead", "lead"),
            ("product_development_chemist", "chemist"),
            ("product_development_engineer", "engineer"),
            ("laboratory_technician", "technician"),
        ]:
            cur.execute(
                """
                INSERT INTO projects.project_members
                    (organization_id, project_id, user_id, project_role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (project_id, user_id) DO NOTHING
                """,
                (org_id, project_id, user_ids[role_code], project_role),
            )

        # --- requirements, from the source's own example table ------------
        # Real numbers from the source documents, not invented ones.
        requirements = [
            ("REQ-DEN-001", "Density", 1.25, 1.20, 1.30, "g/cm3", "major"),
            ("REQ-WRK-001", "Working time", 5.0, 4.0, 6.0, "minutes", "major"),
            ("REQ-ADH-001", "Adhesion", 7.0, 6.0, None, "MPa", "critical"),
            ("REQ-SND-001", "Sanding time", 18.0, None, 22.0, "minutes", "major"),
        ]
        for code, name, target, minimum, maximum, unit, crit in requirements:
            # +5% of the acceptance limit, per the plan's seeded default.
            warn = round(minimum * 1.05, 6) if minimum is not None else None
            cur.execute(
                """
                INSERT INTO projects.requirements
                    (organization_id, project_id, requirement_code, category, name,
                     target_value, minimum_value, maximum_value, canonical_unit,
                     warning_threshold, criticality, verification_method, status, created_by)
                VALUES (%s, %s, %s, 'technical', %s, %s, %s, %s, %s, %s, %s,
                        'test', 'approved', %s)
                ON CONFLICT (project_id, requirement_code, revision) DO NOTHING
                """,
                (org_id, project_id, code, name, target, minimum, maximum, unit,
                 warn, crit, user_ids["product_development_lead"]),
            )
        print(f"project RDP-2026-014 with {len(requirements)} requirements")

        conn.commit()

    print("\nseed complete — ALL DATA IS SYNTHETIC AND LABELLED AS DEMO")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"seed failed: {exc}")
