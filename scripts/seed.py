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

import datetime as _dt
import json
import io
import os
import pathlib
import sys
import tempfile
import uuid

import psycopg

# 🔴 THE SEEDER USES THE REAL OBJECT-STORAGE PORT, NOT A COPY OF IT.
#
# Since I41 (migrations 036/037) a document row must carry a checksum the STORE
# computed, so the seeder has to write real bytes. Reimplementing "hash it and
# write it" here would be a second implementation of the one thing the port
# exists to own -- and the copy would be the one that quietly drifts, in the
# script that decides what the demo database asserts about hazard
# documentation.
#
# The path is resolved from this file's own location rather than from the
# working directory: CI runs `python ../../scripts/seed.py` from apps/api, and
# a developer runs it from wherever they happen to be.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.core.object_storage import (  # noqa: E402  - must follow the path shim
    FilesystemObjectStore,
    new_object_key,
)

# The filesystem adapter, matching the API's default. A seeder writing to a
# different store than the API reads from would produce a database full of
# checksums for files the application cannot fetch -- which is I41 again, one
# level along.
document_store = FilesystemObjectStore(
    os.getenv(
        "OBJECT_STORE_ROOT",
        str(pathlib.Path(tempfile.gettempdir()) / "evercoat-documents"),
    )
)

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


# Slice 3. Every one of these comes out of the SAME `demo-data.json` the
# deployed static site renders, for the reason the header already gives:
# the seeded database and the demonstration must show the same records,
# and a Python copy of the material list would be the second list that
# drifts.
SUPPLIERS = _DEMO["suppliers"]
MATERIALS = _DEMO["materials"]
FORMULAS = _DEMO["formulas"]

# Administration section 3's reference data. These are NOT in the demo
# JSON because nothing on the static site renders them -- they are the
# canonical lists a FORM offers, and the static demonstration has no
# forms. Kept minimal and honest: the units this product's own
# requirements actually use.
UNITS = [
    ("g/cm3", "grams per cubic centimetre", "density", 10),
    ("MPa", "megapascals", "stress", 20),
    ("%", "per cent", "fraction", 30),
    ("min", "minutes", "time", 40),
    ("degC", "degrees Celsius", "temperature", 50),
    ("g/L", "grams per litre", "concentration", 60),
    ("mPa.s", "millipascal-seconds", "viscosity", 70),
]

PRODUCT_FAMILIES = [
    ("POLYESTER_FILLER", "Polyester Fillers", 10),
    ("EPOXY_PUTTY", "Epoxy Putties", 20),
    ("STRUCTURAL_ADHESIVE", "Structural Adhesives", 30),
    ("SEAM_SEALER", "Seam Sealers", 40),
    ("PRIMER", "Primers and Coatings", 50),
]


def _placeholder_sds(material_code: str, name: str) -> bytes:
    """A minimal, VALID PDF that says what it is.

    Valid because `validate_upload` checks magic bytes, and because a
    placeholder that is not really a PDF would make the demo data prove the
    pipeline works when it had actually bypassed it.

    Labelled because a Safety Data Sheet is a regulated document about real
    hazards. Demo data that could be mistaken for one is worse than no demo
    data -- master prompt section 10: no undocumented procedure may be
    represented as an official requirement.
    """
    body = (
        f"SYNTHETIC DEMONSTRATION DATA - NOT A SAFETY DATA SHEET. "
        f"Material {material_code} ({name}). Generated by scripts/seed.py for "
        f"the EvercoatITWRD demo dataset. Contains no hazard information and "
        f"must not be relied upon."
    )
    # A hand-built one-page PDF. No dependency, and it survives a magic-byte
    # check because it genuinely is one.
    content = f"BT /F1 9 Tf 40 750 Td ({body}) Tj ET".encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n"
        f"{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


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

        # --- Administration section 3 -- units and product families -------
        # Config rows, so a deployment adds a product family without a
        # migration. Seeded because a canonical list nobody has populated
        # is a dropdown that renders empty, which reads to a chemist as a
        # broken form rather than as an unconfigured one.
        for code, name, kind, order in UNITS:
            cur.execute(
                """
                INSERT INTO materials.units
                    (organization_id, code, name, quantity_kind, display_order)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, code) DO UPDATE
                SET name = EXCLUDED.name, quantity_kind = EXCLUDED.quantity_kind
                """,
                (org_id, code, name, kind, order),
            )

        for code, name, order in PRODUCT_FAMILIES:
            cur.execute(
                """
                INSERT INTO materials.product_families
                    (organization_id, code, name, display_order)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (organization_id, code) DO UPDATE
                SET name = EXCLUDED.name
                """,
                (org_id, code, name, order),
            )
        print(f"{len(UNITS)} units and {len(PRODUCT_FAMILIES)} product families")

        # --- suppliers ----------------------------------------------------
        supplier_ids: dict[str, uuid.UUID] = {}
        for sup in SUPPLIERS:
            cur.execute(
                """
                INSERT INTO materials.suppliers
                    (organization_id, supplier_code, name, country, status,
                     quality_rating, notes, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, supplier_code) DO UPDATE
                SET name = EXCLUDED.name, status = EXCLUDED.status,
                    quality_rating = EXCLUDED.quality_rating
                RETURNING id
                """,
                (
                    org_id,
                    sup["supplier_code"],
                    sup["name"],
                    sup.get("country"),
                    sup["status"],
                    sup.get("quality_rating"),
                    sup.get("note"),
                    user_ids["procurement_specialist"],
                ),
            )
            supplier_ids[sup["supplier_code"]] = cur.fetchone()[0]

        # --- materials ----------------------------------------------------
        # The numeric columns are passed as STRINGS out of the JSON and
        # cast by PostgreSQL into NUMERIC. Never through `float()`:
        # CLAUDE.md section 5 forbids float for densities and percentages,
        # and a seed that quietly rounded 1.10 to 1.1000000000000001 would
        # make the seeded figures disagree with the baked ones by a margin
        # nobody would think to look for.
        material_ids: dict[str, uuid.UUID] = {}
        for mat in MATERIALS:
            cur.execute(
                """
                INSERT INTO materials.materials
                    (organization_id, material_code, name, category, role, status,
                     density_g_cm3, solids_fraction, voc_fraction, cost_per_kg,
                     notes, requires_sds, restriction_reason, created_by)
                VALUES (%s, %s, %s, %s, %s, %s,
                        CAST(%s AS NUMERIC), CAST(%s AS NUMERIC),
                        CAST(%s AS NUMERIC), CAST(%s AS NUMERIC),
                        %s, TRUE, %s, %s)
                ON CONFLICT (organization_id, material_code) DO UPDATE
                SET name = EXCLUDED.name,
                    category = EXCLUDED.category,
                    role = EXCLUDED.role,
                    status = EXCLUDED.status,
                    density_g_cm3 = EXCLUDED.density_g_cm3,
                    solids_fraction = EXCLUDED.solids_fraction,
                    voc_fraction = EXCLUDED.voc_fraction,
                    cost_per_kg = EXCLUDED.cost_per_kg,
                    restriction_reason = EXCLUDED.restriction_reason
                RETURNING id
                """,
                (
                    org_id,
                    mat["material_code"],
                    mat["name"],
                    mat["category"],
                    mat["role"],
                    mat["status"],
                    mat.get("density_g_cm3"),
                    mat.get("solids_fraction"),
                    mat.get("voc_fraction"),
                    mat.get("cost_per_kg"),
                    mat.get("note"),
                    # A restricted material must state why -- a CHECK
                    # constraint, and the reason the chemist whose formula
                    # it blocks can act on it.
                    mat.get("restriction_reason")
                    or ("recorded in the demonstration dataset"
                        if mat["status"] == "restricted" else None),
                    user_ids["procurement_specialist"],
                ),
            )
            material_ids[mat["material_code"]] = cur.fetchone()[0]

            # The first listed supplier is the primary. At most one may
            # be, enforced by a partial unique index, so the flag is
            # derived from position rather than set twice.
            for position, supplier_code in enumerate(mat.get("suppliers", [])):
                cur.execute(
                    """
                    INSERT INTO materials.material_suppliers
                        (organization_id, material_id, supplier_id, is_primary)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (organization_id, material_id, supplier_id)
                    DO NOTHING
                    """,
                    (org_id, material_ids[mat["material_code"]],
                     supplier_ids[supplier_code], position == 0),
                )

            # WITHOUT THIS, NO FORMULA CAN EVER BE SUBMITTED. `requires_sds`
            # is TRUE on every material above, and the formulation safety
            # check hard-blocks submission for any component with no SDS on
            # file. Seeding the material without its safety data sheet
            # would reproduce, in the demo data, the exact deadlock the
            # Supervisor found in the code.
            #
            # 🔴 AND SINCE I41 (migrations 036/037) THE ROW IS NOT ENOUGH.
            #
            # This block used to insert a row naming `demo/sds/RM-xxx.pdf` and
            # store nothing. That was the defect in miniature: the safety gate
            # counted rows, so the demo data ASSERTED that every material had
            # hazard documentation while no file existed anywhere. The gate now
            # reads `materials.usable_documents`, which requires bytes, a
            # checksum the store computed, and a clean scan.
            #
            # So the seeder writes a real placeholder PDF through the real
            # port. It is a placeholder and it says so IN the document -- demo
            # data must never be mistakable for a genuine Safety Data Sheet,
            # which is a regulated artefact about actual hazards.
            sds_bytes = _placeholder_sds(mat["material_code"], mat["name"])
            stored = document_store.put(
                new_object_key(org_id, "SDS"),
                io.BytesIO(sds_bytes),
                "application/pdf",
            )
            cur.execute(
                """
                INSERT INTO materials.material_documents
                    (organization_id, material_id, document_type, title,
                     storage_key, content_type, uploaded_by, original_filename,
                     byte_size, checksum_sha256,
                     status, scan_status, scanner_name, scanner_version, scanned_at)
                VALUES (%s, %s, 'SDS', %s, %s, 'application/pdf', %s, %s,
                        %s, %s, 'approved', 'clean', 'seed-placeholder', 'n/a', now())
                ON CONFLICT (organization_id, storage_key) DO NOTHING
                """,
                (
                    org_id,
                    material_ids[mat["material_code"]],
                    f"Safety Data Sheet — {mat['name']}",
                    stored.key,
                    user_ids["procurement_specialist"],
                    f"SDS {mat['material_code']}.pdf",
                    stored.byte_size,
                    stored.checksum_sha256,
                ),
            )
        print(f"{len(SUPPLIERS)} suppliers and {len(MATERIALS)} materials, each with an SDS")

        # --- formulas, versions, components -------------------------------
        # The genealogy is seeded in version order, so `parent_version_id`
        # can point at a row that already exists. Every version after the
        # first carries a change_reason and a technical_hypothesis, which
        # the database requires -- section 8's rule that a genealogy must
        # record not only what changed but why.
        #
        # 🔴 EVERY VERSION IS CREATED AS A DRAFT AND MOVED AFTERWARDS.
        #
        # The first version of this seeded each version at its FINAL status
        # and then inserted its components, and CI refused it on the very
        # first run of the new seed gate:
        #
        #   seed failed: the composition of version FRM-014-V001 is frozen
        #   (status superseded); clone it to a new draft version
        #
        # That is migration 015's immutability trigger working exactly as
        # designed -- the composition of anything that has left `draft` is
        # a controlled record, and a seed script is not an exception. It is
        # also the honest order of events: a version really does start as a
        # draft, receive its composition, and only then get submitted,
        # approved and eventually superseded. Seeding it any other way
        # would have required a hole in the rule.
        version_count = 0
        component_count = 0
        for formula in FORMULAS:
            cur.execute(
                """
                INSERT INTO formulations.formulas
                    (organization_id, project_id, formula_code, name,
                     product_family, owner_user_id, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, formula_code) DO UPDATE
                SET name = EXCLUDED.name
                RETURNING id
                """,
                (
                    org_id,
                    project_id,
                    formula["formula_code"],
                    formula["name"],
                    formula.get("product_family"),
                    user_ids["product_development_chemist"],
                    user_ids["product_development_chemist"],
                ),
            )
            formula_id = cur.fetchone()[0]

            previous_version_id = None
            for version in sorted(formula["versions"], key=lambda v: v["version_number"]):
                approved = version["status"] in ("approved", "superseded", "released")
                cur.execute(
                    """
                    INSERT INTO formulations.formula_versions
                        (organization_id, project_id, formula_id, version_number,
                         version_code, parent_version_id, status, change_reason,
                         technical_hypothesis, expected_effect, observed_effect,
                         approved_by, approved_at, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (organization_id, version_code) DO NOTHING
                    RETURNING id
                    """,
                    (
                        org_id,
                        project_id,
                        formula_id,
                        version["version_number"],
                        version["version_code"],
                        previous_version_id,
                        # 'draft' regardless of the target status; moved
                        # below, after the components exist.
                        "draft",
                        version.get("change_reason"),
                        version.get("technical_hypothesis"),
                        version.get("expected_effect"),
                        version.get("observed_effect"),
                        None,
                        None,
                        user_ids["product_development_chemist"],
                    ),
                )
                row = cur.fetchone()
                created = row is not None
                if created:
                    version_id = row[0]
                    version_count += 1
                else:
                    # Already seeded on a previous run. Fetch the id so the
                    # genealogy still links, rather than silently breaking
                    # the chain on the second run of an idempotent script.
                    cur.execute(
                        """
                        SELECT id FROM formulations.formula_versions
                        WHERE organization_id = %s AND version_code = %s
                        """,
                        (org_id, version["version_code"]),
                    )
                    version_id = cur.fetchone()[0]
                    previous_version_id = version_id
                    # 🔴 AND NOTHING ELSE HAPPENS TO IT.
                    #
                    # `ON CONFLICT DO NOTHING` does NOT save the component
                    # inserts below: a BEFORE INSERT trigger fires before
                    # PostgreSQL ever checks the conflict, so re-seeding a
                    # version that has since left `draft` raises "the
                    # composition is frozen" -- on the SECOND run, which is
                    # exactly the run that proves idempotence.
                    #
                    # The rule is not being worked around. An existing
                    # version already has its composition; re-writing it is
                    # precisely what section 8 forbids, and a seed script
                    # is not an exception to that.
                    continue

                for component in version["components"]:
                    cur.execute(
                        """
                        INSERT INTO formulations.formula_components
                            (organization_id, project_id, formula_version_id,
                             material_id, percentage)
                        VALUES (%s, %s, %s, %s, CAST(%s AS NUMERIC))
                        ON CONFLICT (formula_version_id, material_id) DO NOTHING
                        """,
                        (
                            org_id,
                            project_id,
                            version_id,
                            material_ids[component["material_code"]],
                            component["percentage"],
                        ),
                    )
                    component_count += 1

                # NOW move it to its real status. The trigger permits this:
                # a draft is a workspace, so `deny_version_mutation` returns
                # early and the row freezes on the way out rather than on
                # the way in. `approved_by` goes on in the same statement,
                # because `formula_versions_approved_states_have_an_approver`
                # refuses an approved version that names no approver.
                if version["status"] != "draft":
                    cur.execute(
                        """
                        UPDATE formulations.formula_versions
                        SET status = %s, approved_by = %s, approved_at = %s,
                            submitted_by = %s, submitted_at = %s
                        WHERE id = %s AND status = 'draft'
                        """,
                        (
                            version["status"],
                            user_ids["product_development_lead"] if approved else None,
                            # A real datetime, not the string "now()".
                            # psycopg binds parameters as VALUES, and there
                            # is no timestamp literal spelled "now()" --
                            # PostgreSQL accepts 'now'::timestamptz. That
                            # bug would have failed on the first approved
                            # version and nowhere else.
                            _dt.datetime.now(_dt.UTC) if approved else None,
                            user_ids["product_development_chemist"],
                            _dt.datetime.now(_dt.UTC),
                            version_id,
                        ),
                    )

                previous_version_id = version_id

        print(
            f"{len(FORMULAS)} formulas, {version_count} new versions, "
            f"{component_count} component lines"
        )

        conn.commit()

    print("\nseed complete — ALL DATA IS SYNTHETIC AND LABELLED AS DEMO")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"seed failed: {exc}")
