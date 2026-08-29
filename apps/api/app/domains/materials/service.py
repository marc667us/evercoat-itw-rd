"""The raw material library, its suppliers and its lots.

**Why this module exists.** `/materials` and `/suppliers` have been on the
deployed site since Slice 3's front half, rendering figures baked into
`demo-data.json` by a build script. There was no table, no service and no
route behind either page. Asking this codebase's standing question --
*which production path WRITES it?* -- the answer was "a Python script at
build time", which is a demonstration, not a product.

**Three rules shape everything below.**

*No read-then-write.* Every mutation is a single statement whose guard
lives in its own WHERE clause, with the prior state captured by a CTE in
the same statement. A rule checked in a SELECT and enforced in a later
UPDATE is unknown at write time.

*The service never does the arithmetic.* `CLAUDE.md` rule 2 gives
deterministic scientific calculation to `app.calculations`. This module
loads rows and hands them over; it does not add percentages, average
densities or convert fractions. A `fraction * 100` written here would be
the fourth instance of that defect found in review.

*References are not reads.* `materials.created_by` is a plain
`REFERENCES core.users(id)` because users are not tenant-scoped, and
referential integrity bypasses RLS even under FORCE.

An earlier version of this paragraph claimed "every path that accepts a
user id calls `require_active_member`", which was false:
`set_material_status`, `set_supplier_status` and `link_supplier` all take
an `actor_id` and none of them call it. Not exploitable today -- those
actor ids come from a verified token and are never client-supplied -- but
it is the same comment-asserting-an-unimplemented-rule class this header
warns about, and it would become live the moment a worker or an
admin-on-behalf-of path supplied one. The accurate rule: **every path
that accepts a user id FROM THE REQUEST BODY** -- `create_material`'s and
`create_supplier`'s author, `create_formula`'s owner -- calls it.

**The five statuses, and what each one means to the engine.** A material
is `development` until somebody with `material.approve_lab` promotes it to
`approved`, and `material.approve_production` promotes it further to
`preferred`. `material.restrict` moves it to `restricted` -- which the
formulation engine treats as a HARD submission block that cannot be waived
-- or to `obsolete`, which retires it without deleting a single row of
history.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculations.formulation import fraction_to_percent
from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write
from app.core.file_types import validate_upload
from app.core.malware import MalwareFoundError, MalwareScannerPort
from app.core.object_storage import ObjectStoragePort, new_object_key
from app.core.tenancy import require_active_member

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TRANSITION_PERMISSION",
    "DocumentInput",
    "MaterialDuplicateError",
    "MaterialError",
    "MaterialInput",
    "MaterialInvalidError",
    "MaterialNotFoundError",
    "MaterialPermissionError",
    "MaterialsError",
    "SupplierDuplicateError",
    "SupplierError",
    "SupplierInput",
    "SupplierLinkInput",
    "SupplierNotFoundError",
    "create_material",
    "create_supplier",
    "get_material",
    "link_supplier",
    "list_competitor_documents",
    "list_material_documents",
    "list_materials",
    "list_suppliers",
    "material_usage",
    "set_material_status",
    "set_supplier_status",
    "store_document",
    "update_material",
]

# The statuses that hard-block a formula's submission. Kept here as the
# single Python-side definition and asserted against the database CHECK
# constraint by `tests/db/test_015_materials_formulations.py`, so this
# cannot quietly become a second, disagreeing list -- the recurring root
# cause in this repository.
#
# `obsolete` IS IN THE SET. It was omitted at first, which meant a
# material retired through `material.restrict` could be added as a fresh
# component to a new draft and submitted with no block and no warning --
# retirement that retired nothing. Raised by the Supervisor.
#
# The engine reports both under the code `RESTRICTED_MATERIAL`, because
# what it is being told is "these materials may not be used" and the
# reason is a domain fact rather than an arithmetic one. The message names
# the material, which is what the chemist needs to act.
BLOCKING_STATUSES = frozenset({"restricted", "obsolete"})

# Statuses a material may hold. Ordered as a lifecycle, not alphabetically.
MATERIAL_STATUSES = ("development", "approved", "preferred", "restricted", "obsolete")

SUPPLIER_STATUSES = ("pending", "qualified", "approved", "suspended", "disqualified")

# WHICH STATUS MAY FOLLOW WHICH, AND WHO MAY MAKE EACH MOVE.
#
# 🔴 THE PERMISSION BELONGS TO THE EDGE, NOT TO THE DESTINATION.
#
# The first version of this mapped destination -> permission, and the
# Supervisor found the hole that leaves: `development` is reachable with
# `material.edit`, so a Chemist or a Procurement Specialist could take a
# material QA had just RESTRICTED for a safety finding and move it back to
# `development` -- which also clears `restriction_reason` -- unblocking
# every formula that used it. QA holds `material.restrict` and not
# `material.edit`, so QA could not even undo it. The authority that
# imposes a block is the only authority that may lift it.
#
# It also fixed the other half of the same shape: QA holds BOTH
# `material.restrict` and (since migration 016)
# `material.approve_production`, so a destination-keyed table let QA take a
# brand-new `development` material straight to `preferred`, skipping
# `approved` and the Lead who holds `material.approve_lab`. Raised by
# Codex.
#
# Read each row as "from -> to requires":
TRANSITION_PERMISSION: dict[tuple[str, str], str] = {
    # Promotion is a two-stage ladder, one permission per rung.
    ("development", "approved"): "material.approve_lab",
    ("approved", "preferred"): "material.approve_production",
    # Demotion one rung at a time. Never `preferred` straight to
    # `development`: reversing two decisions in one action hides which of
    # them was actually reversed.
    ("preferred", "approved"): "material.approve_lab",
    ("approved", "development"): "material.edit",
    # Taking a material OUT of circulation is always available, from
    # anywhere -- a safety finding does not wait for a material to be in a
    # convenient state.
    ("development", "restricted"): "material.restrict",
    ("approved", "restricted"): "material.restrict",
    ("preferred", "restricted"): "material.restrict",
    ("development", "obsolete"): "material.restrict",
    ("approved", "obsolete"): "material.restrict",
    ("preferred", "obsolete"): "material.restrict",
    ("restricted", "obsolete"): "material.restrict",
    # Lifting a restriction needs the restricting authority, for the
    # reason above. Bringing a retired material back is an ordinary edit,
    # because `obsolete` records disuse rather than a finding.
    ("restricted", "development"): "material.restrict",
    ("obsolete", "development"): "material.edit",
}

# Derived, never written out a second time: the second list is the one
# that drifts.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    source: frozenset(
        target for (from_status, target) in TRANSITION_PERMISSION if from_status == source
    )
    for source in ("development", "approved", "preferred", "restricted", "obsolete")
}


class MaterialsError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class MaterialError(MaterialsError):
    pass


class MaterialNotFoundError(MaterialError):
    """No such material in this organization.

    Deliberately indistinguishable from "exists in another tenant". The
    difference is itself information about another tenant.
    """


class MaterialDuplicateError(MaterialError):
    """The material code is already used in this organization."""


class MaterialPermissionError(MaterialError):
    """The caller may not make THIS move, though the move itself is legal.

    Distinct from `MaterialInvalidError` so the route can answer 403 rather
    than 422. "You may not do this" and "this cannot be done" are different
    answers and a chemist needs to know which one they got.
    """


class MaterialInvalidError(MaterialError):
    """The resulting row would violate a database invariant.

    Distinct from "not found" so the route answers 422 rather than 404.
    The canonical case is restricting a material without stating why.
    """


class SupplierError(MaterialsError):
    pass


class SupplierNotFoundError(SupplierError):
    pass


class SupplierDuplicateError(SupplierError):
    pass


@dataclass(frozen=True, slots=True)
class MaterialInput:
    """A new material, or the editable half of an existing one.

    Every quantity is `Decimal | None`. `None` means UNKNOWN and is a real,
    common state -- the engine refuses to compute a density it does not
    have rather than assuming one, and that refusal reaches the chemist as
    a named submission block. A default of 1.0 here would turn an unknown
    into a confident wrong answer.
    """

    material_code: str
    name: str
    category: str
    role: str = "other"
    description: str | None = None
    cas_number: str | None = None
    density_g_cm3: Decimal | None = None
    solids_fraction: Decimal | None = None
    voc_fraction: Decimal | None = None
    cost_per_kg: Decimal | None = None
    epoxy_equivalent_weight: Decimal | None = None
    amine_hydrogen_equivalent_weight: Decimal | None = None
    hazard_summary: str | None = None
    requires_sds: bool = True
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentInput:
    """The METADATA a caller supplies about a controlled document.

    🔴 `storage_key`, `byte_size` and `checksum_sha256` ARE NO LONGER HERE, AND
    THAT IS THE POINT OF I41.

    This docstring used to argue: *"Registering 'SDS-2026-014, issued
    2026-03-11, sha256 ...' is a real statement about the material whether or
    not the PDF has been uploaded to this deployment yet."*

    It reads reasonably and it was wrong, because of what the row is USED for.
    `formulations._safety_checks` blocks formula submission on
    `requires_sds AND sds_count = 0` -- it COUNTS ROWS. So the row was not a
    bibliographic note; it was the evidence a hazard document exists, and a
    caller could mint that evidence with `storage_key = 'sds/anything.pdf'`.

    Those three fields now come from `ObjectStoragePort`, which computes them
    while writing the bytes and returns them. A caller cannot supply them, so a
    row cannot claim a file the store does not hold.

    The file content still never touches a database row -- SECURITY.md section
    6 is unchanged. What changed is that the KEY now has to point at something.
    """

    document_type: str
    title: str
    content_type: str | None = None
    issued_on: dt.date | None = None
    expires_on: dt.date | None = None
    supersedes_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SupplierInput:
    supplier_code: str
    name: str
    country: str | None = None
    quality_rating: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class SupplierLinkInput:
    """The commercial facts that belong to the material/supplier PAIR."""

    supplier_id: uuid.UUID
    supplier_part_code: str | None = None
    # TRI-STATE, NOT A BOOLEAN. `None` means "leave it as it is".
    #
    # This endpoint is an upsert -- "add supplier B" and "change supplier
    # B's lead time" are the same intent from the screen's point of view --
    # so with a plain `bool` defaulting to False, a client PATCHing only a
    # lead time on the CURRENT primary supplier silently demoted it and the
    # material ended up with no primary at all. Raised by the Supervisor.
    is_primary: bool | None = None
    lead_time_days: int | None = None
    quoted_price_per_kg: Decimal | None = None
    currency: str | None = None
    qualified_on: dt.date | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


def create_material(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: MaterialInput,
) -> uuid.UUID:
    """Add a material to the library, always as `development`.

    The status is not an argument. A material that could be created
    already `preferred` would let the approval chain be written after the
    fact -- and `material.create` is held by the Chemist, who deliberately
    does NOT hold `material.approve_production`. Accepting a status here
    would hand that permission to everyone who can create a row.
    """
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="author"
    )

    try:
        with guarded_write(session):
            material_id: uuid.UUID = session.execute(
                text(
                    """
                    INSERT INTO materials.materials
                        (organization_id, material_code, name, category, role, status,
                         description, cas_number, density_g_cm3, solids_fraction,
                         voc_fraction, cost_per_kg, epoxy_equivalent_weight,
                         amine_hydrogen_equivalent_weight, hazard_summary,
                         requires_sds, notes, created_by)
                    VALUES
                        (:org, :code, :name, :category, :role, 'development',
                         :description, :cas, :density, :solids,
                         :voc, :cost, :eew,
                         :ahew, :hazard,
                         :requires_sds, :notes, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "code": spec.material_code,
                    "name": spec.name,
                    "category": spec.category,
                    "role": spec.role,
                    "description": spec.description,
                    "cas": spec.cas_number,
                    "density": spec.density_g_cm3,
                    "solids": spec.solids_fraction,
                    "voc": spec.voc_fraction,
                    "cost": spec.cost_per_kg,
                    "eew": spec.epoxy_equivalent_weight,
                    "ahew": spec.amine_hydrogen_equivalent_weight,
                    "hazard": spec.hazard_summary,
                    "requires_sds": spec.requires_sds,
                    "notes": spec.notes,
                    "actor": actor_id,
                },
            ).scalar_one()
    except IntegrityError as exc:
        raise _translate_material_integrity_error(exc, spec.material_code) from exc

    write_audit(
        session,
        AuditEvent(
            action="material.created",
            entity_type="material",
            entity_id=str(material_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "material_code": spec.material_code,
                "name": spec.name,
                "role": spec.role,
                "status": "development",
            },
            reason="material added to the library",
        ),
    )
    return material_id


def update_material(
    session: Session,
    *,
    material_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: MaterialInput,
) -> dict[str, Any]:
    """Edit a material's descriptive and property data.

    `material_code` and `status` are NOT editable here. The code is the
    identity every formula component points at through a foreign key, and
    the status is a separate, separately-permissioned decision -- folding
    it into a general edit would let anyone holding `material.edit`
    promote a material to `preferred` without holding
    `material.approve_production`.

    A single statement: the previous state is captured by a CTE in the
    same UPDATE that writes the new one, so the audit record cannot
    describe a row some other transaction has already moved.
    """
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="editor"
    )

    try:
        with guarded_write(session):
            row = (
                session.execute(
                    text(
                        """
                    WITH prev AS (
                        SELECT id, name, category, role, density_g_cm3, cost_per_kg
                        FROM materials.materials
                        WHERE id = :mid AND organization_id = :org
                        FOR UPDATE
                    )
                    UPDATE materials.materials m
                    SET name            = :name,
                        category        = :category,
                        role            = :role,
                        description     = :description,
                        cas_number      = :cas,
                        density_g_cm3   = :density,
                        solids_fraction = :solids,
                        voc_fraction    = :voc,
                        cost_per_kg     = :cost,
                        epoxy_equivalent_weight = :eew,
                        amine_hydrogen_equivalent_weight = :ahew,
                        hazard_summary  = :hazard,
                        requires_sds    = :requires_sds,
                        notes           = :notes,
                        updated_at      = now()
                    FROM prev
                    WHERE m.id = prev.id
                    RETURNING m.id, m.material_code, m.name, m.status,
                              prev.name AS prev_name,
                              prev.role AS prev_role,
                              prev.density_g_cm3 AS prev_density,
                              prev.cost_per_kg AS prev_cost
                    """
                    ),
                    {
                        "mid": material_id,
                        "org": organization_id,
                        "name": spec.name,
                        "category": spec.category,
                        "role": spec.role,
                        "description": spec.description,
                        "cas": spec.cas_number,
                        "density": spec.density_g_cm3,
                        "solids": spec.solids_fraction,
                        "voc": spec.voc_fraction,
                        "cost": spec.cost_per_kg,
                        "eew": spec.epoxy_equivalent_weight,
                        "ahew": spec.amine_hydrogen_equivalent_weight,
                        "hazard": spec.hazard_summary,
                        "requires_sds": spec.requires_sds,
                        "notes": spec.notes,
                    },
                )
                .mappings()
                .one_or_none()
            )
    except IntegrityError as exc:
        raise MaterialInvalidError(str(exc.orig)) from exc

    if row is None:
        raise MaterialNotFoundError("no such material in this organization")

    write_audit(
        session,
        AuditEvent(
            action="material.updated",
            entity_type="material",
            entity_id=str(material_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={
                "name": row["prev_name"],
                "role": row["prev_role"],
                "density_g_cm3": _num(row["prev_density"]),
                "cost_per_kg": _num(row["prev_cost"]),
            },
            new_state={
                "name": spec.name,
                "role": spec.role,
                "density_g_cm3": _num(spec.density_g_cm3),
                "cost_per_kg": _num(spec.cost_per_kg),
            },
            reason="material data edited",
        ),
    )
    # 🔴 NOT `dict(row)`. The RETURNING clause carries `prev_name`, `prev_role`,
    # `prev_density` and `prev_cost` because the audit record needs the state
    # this UPDATE replaced -- captured in the same statement so no other
    # transaction can move the row in between. They are scaffolding for the
    # audit write above, and returning them put four internal fields into the
    # HTTP response, two of them raw `Decimal`s that FastAPI encodes as floats.
    # The caller is told what it changed, not how the change was recorded.
    return {
        "id": row["id"],
        "material_code": row["material_code"],
        "name": row["name"],
        "status": row["status"],
    }


def set_material_status(
    session: Session,
    *,
    material_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    held_permissions: frozenset[str],
    status: str,
    restriction_reason: str | None = None,
    reason: str,
) -> dict[str, Any]:
    """Move a material through its lifecycle.

    The route decides WHICH statuses this caller may set, from the
    permission they hold (`material.approve_lab`, `approve_production`,
    `restrict`). This function enforces what must be true of the ROW
    whoever the caller is -- and those are different questions. Permission
    answers "may this person ever do this"; `ALLOWED_TRANSITIONS` answers
    "may it be done from where the material currently is".

    **The source status is in the UPDATE's own WHERE clause**, not checked
    in a SELECT first. A transition validated against a row that another
    request then moves is a check that was true and is not any more; two
    concurrent promotions would both pass it and the second would silently
    win.

    Restricting a material without stating why is refused here as well as
    by a CHECK constraint. The constraint is the mechanism; this is the
    comprehensible message, because an IntegrityError surfacing as a 500
    tells the chemist whose formula just became unsubmittable nothing at
    all.
    """
    if status not in MATERIAL_STATUSES:
        raise MaterialInvalidError(f"'{status}' is not a material status")
    if status == "restricted" and not restriction_reason:
        raise MaterialInvalidError(
            "restricting a material hard-blocks every formula that uses it, so it must state why"
        )

    # Leaving `restricted` clears the reason: a stale restriction reason on
    # an approved material reads as if the restriction were still in force.
    effective_reason = restriction_reason if status == "restricted" else None

    # Two sets, and the difference between them is the difference between
    # 422 and 403.
    #
    #   legal_sources     statuses from which this move exists at all
    #   permitted_sources those the CALLER holds the edge's permission for
    #
    # Only `permitted_sources` reaches the WHERE clause, so authorization
    # is decided by the same statement that performs the write. A caller
    # who lacks the permission matches no row and changes nothing -- there
    # is no window in which the check has passed and the write has not.
    legal_sources = sorted(source for (source, target) in TRANSITION_PERMISSION if target == status)
    if not legal_sources:
        raise MaterialInvalidError(f"nothing may move to '{status}'")

    permitted_sources = sorted(
        source
        for source in legal_sources
        if TRANSITION_PERMISSION[(source, status)] in held_permissions
    )
    if not permitted_sources:
        raise MaterialPermissionError(
            f"moving a material to '{status}' requires "
            + " or ".join(sorted({TRANSITION_PERMISSION[(src, status)] for src in legal_sources}))
        )

    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, status, material_code
                    FROM materials.materials
                    WHERE id = :mid AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE materials.materials m
                SET status = :status,
                    restriction_reason = :restriction_reason,
                    updated_at = now()
                FROM prev
                WHERE m.id = prev.id
                  AND prev.status = ANY(CAST(:from_statuses AS TEXT[]))
                RETURNING m.id, m.material_code, m.status,
                          prev.status AS previous_status
                """
            ),
            {
                "mid": material_id,
                "org": organization_id,
                "status": status,
                "restriction_reason": effective_reason,
                "from_statuses": permitted_sources,
            },
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        # Two causes, and the caller needs to know which. Look the row up
        # and say so -- within this organization only, so the answer still
        # discloses nothing about any other tenant.
        current = (
            session.execute(
                text(
                    """
                    SELECT status FROM materials.materials
                    WHERE id = :mid AND organization_id = :org
                    """
                ),
                {"mid": material_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise MaterialNotFoundError("no such material in this organization")

        here = current["status"]
        if status not in ALLOWED_TRANSITIONS[here]:
            allowed = sorted(ALLOWED_TRANSITIONS[here])
            raise MaterialInvalidError(
                f"a material that is '{here}' cannot move straight to '{status}'; "
                "from here it may become " + (", ".join(allowed) if allowed else "nothing")
            )
        # The move is legal from where the material actually is, so the
        # only reason the predicate excluded it is the permission on that
        # specific edge.
        raise MaterialPermissionError(
            f"moving a material from '{here}' to '{status}' requires "
            f"{TRANSITION_PERMISSION[(here, status)]}"
        )

    write_audit(
        session,
        AuditEvent(
            action="material.status_changed",
            entity_type="material",
            entity_id=str(material_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": row["previous_status"]},
            new_state={"status": status, "restriction_reason": effective_reason},
            reason=reason,
        ),
    )
    return dict(row)


def list_materials(
    session: Session,
    *,
    organization_id: uuid.UUID,
    status: str | None = None,
    role: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The material library, newest code first within each status.

    RLS already restricts the rows to this organization. The explicit
    `organization_id` predicate is not redundant belt-and-braces: it is
    what makes the query correct when it is called from the Celery worker,
    whose session sets the GUCs from a job payload rather than from a
    request.
    """
    rows = session.execute(
        text(
            """
            SELECT m.id, m.material_code, m.name, m.category, m.role, m.status,
                   m.density_g_cm3, m.solids_fraction, m.voc_fraction,
                   m.cost_per_kg, m.cas_number, m.restriction_reason,
                   m.requires_sds, m.hazard_summary, m.updated_at,
                   (SELECT count(*) FROM materials.material_suppliers ms
                     WHERE ms.material_id = m.id) AS supplier_count
            FROM materials.materials m
            WHERE m.organization_id = :org
              AND (CAST(:status AS TEXT) IS NULL OR m.status = CAST(:status AS TEXT))
              AND (CAST(:role AS TEXT) IS NULL OR m.role = CAST(:role AS TEXT))
              AND (
                    CAST(:search AS TEXT) IS NULL
                    OR m.name ILIKE '%' || CAST(:search AS TEXT) || '%'
                    OR m.material_code ILIKE '%' || CAST(:search AS TEXT) || '%'
                  )
            ORDER BY m.material_code
            LIMIT :limit
            """
        ),
        {
            "org": organization_id,
            "status": status,
            "role": role,
            "search": search,
            "limit": limit,
        },
    ).mappings()
    return [_with_percentages(dict(r)) for r in rows]


def get_material(
    session: Session, *, material_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """One material, with its suppliers attached."""
    row = (
        session.execute(
            text(
                """
                SELECT id, material_code, name, category, role, status,
                       description, cas_number, density_g_cm3, solids_fraction,
                       voc_fraction, cost_per_kg, epoxy_equivalent_weight,
                       amine_hydrogen_equivalent_weight, hazard_summary,
                       requires_sds, restriction_reason, notes,
                       created_at, updated_at
                FROM materials.materials
                WHERE id = :mid AND organization_id = :org
                """
            ),
            {"mid": material_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MaterialNotFoundError("no such material in this organization")

    suppliers = session.execute(
        text(
            """
            SELECT ms.id, ms.supplier_id, s.supplier_code, s.name, s.status,
                   ms.supplier_part_code, ms.is_primary, ms.lead_time_days,
                   ms.quoted_price_per_kg, ms.currency, ms.qualified_on
            FROM materials.material_suppliers ms
            JOIN materials.suppliers s
              ON s.id = ms.supplier_id AND s.organization_id = ms.organization_id
            WHERE ms.material_id = :mid AND ms.organization_id = :org
            ORDER BY ms.is_primary DESC, s.supplier_code
            """
        ),
        {"mid": material_id, "org": organization_id},
    ).mappings()

    # Both halves, and the suppliers too: `quoted_price_per_kg` is a NUMERIC
    # and is in `_QUANTITY_KEYS`, so a nested row goes out as a float unless it
    # is stringified as well.
    result = _with_percentages(dict(row))
    result["suppliers"] = [_stringify_quantities(dict(s)) for s in suppliers]
    return result


def material_usage(
    session: Session, *, material_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Which formula versions use this material, and at what percentage.

    The plan calls this "usage + performance history" and it is the reason
    `formula_components_material_idx` exists. It is also the question that
    has to be answerable BEFORE a material is restricted: restricting one
    silently invalidates every draft that contains it, and an approver who
    cannot see that list is approving blind.

    RLS does the confidentiality work here rather than a WHERE clause --
    a restricted project's formulas are invisible to a non-member, so the
    count a Chemist sees may legitimately be lower than the true one. That
    is the intended behaviour and it is why this returns rows rather than
    only a number: a bare count that RLS had silently reduced would look
    like a fact.
    """
    rows = session.execute(
        text(
            """
            SELECT fc.percentage, fc.role_override,
                   fv.id AS formula_version_id, fv.version_code, fv.status AS version_status,
                   f.id AS formula_id, f.formula_code, f.name AS formula_name,
                   f.project_id
            FROM formulations.formula_components fc
            JOIN formulations.formula_versions fv
              ON fv.id = fc.formula_version_id AND fv.organization_id = fc.organization_id
            JOIN formulations.formulas f
              ON f.id = fv.formula_id AND f.organization_id = fv.organization_id
            WHERE fc.material_id = :mid AND fc.organization_id = :org
            ORDER BY f.formula_code, fv.version_number
            """
        ),
        {"mid": material_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


def create_supplier(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: SupplierInput,
) -> uuid.UUID:
    """Add a supplier, always as `pending`.

    Same reasoning as `create_material`: qualification is a decision with
    its own evidence, not a field on a creation form.
    """
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="author"
    )

    try:
        with guarded_write(session):
            supplier_id: uuid.UUID = session.execute(
                text(
                    """
                    INSERT INTO materials.suppliers
                        (organization_id, supplier_code, name, country, status,
                         quality_rating, contact_name, contact_email, notes, created_by)
                    VALUES
                        (:org, :code, :name, :country, 'pending',
                         :rating, :contact_name, :contact_email, :notes, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "code": spec.supplier_code,
                    "name": spec.name,
                    "country": spec.country,
                    "rating": spec.quality_rating,
                    "contact_name": spec.contact_name,
                    "contact_email": spec.contact_email,
                    "notes": spec.notes,
                    "actor": actor_id,
                },
            ).scalar_one()
    except IntegrityError as exc:
        if "suppliers_org_code_key" in str(exc.orig):
            raise SupplierDuplicateError(
                f"supplier code '{spec.supplier_code}' is already used in this organization"
            ) from exc
        raise SupplierError(str(exc.orig)) from exc

    write_audit(
        session,
        AuditEvent(
            action="supplier.created",
            entity_type="supplier",
            entity_id=str(supplier_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"supplier_code": spec.supplier_code, "name": spec.name},
            reason="supplier added",
        ),
    )
    return supplier_id


def set_supplier_status(
    session: Session,
    *,
    supplier_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    status: str,
    reason: str,
) -> dict[str, Any]:
    """Qualify, approve, suspend or disqualify a supplier."""
    if status not in SUPPLIER_STATUSES:
        raise SupplierError(f"'{status}' is not a supplier status")

    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, status FROM materials.suppliers
                    WHERE id = :sid AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE materials.suppliers s
                SET status = :status, updated_at = now()
                FROM prev
                WHERE s.id = prev.id
                RETURNING s.id, s.supplier_code, s.status, prev.status AS previous_status
                """
            ),
            {"sid": supplier_id, "org": organization_id, "status": status},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise SupplierNotFoundError("no such supplier in this organization")

    write_audit(
        session,
        AuditEvent(
            action="supplier.status_changed",
            entity_type="supplier",
            entity_id=str(supplier_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": row["previous_status"]},
            new_state={"status": status},
            reason=reason,
        ),
    )
    return dict(row)


def list_suppliers(
    session: Session,
    *,
    organization_id: uuid.UUID,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT s.id, s.supplier_code, s.name, s.country, s.status,
                   s.quality_rating, s.contact_name, s.contact_email, s.updated_at,
                   (SELECT count(*) FROM materials.material_suppliers ms
                     WHERE ms.supplier_id = s.id) AS material_count
            FROM materials.suppliers s
            WHERE s.organization_id = :org
              AND (CAST(:status AS TEXT) IS NULL OR s.status = CAST(:status AS TEXT))
            ORDER BY s.supplier_code
            LIMIT :limit
            """
        ),
        {"org": organization_id, "status": status, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def link_supplier(
    session: Session,
    *,
    material_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: SupplierLinkInput,
) -> uuid.UUID:
    """Attach a supplier to a material, or update the pair's terms.

    **Why the primary flag is demoted in the same statement.** At most one
    supplier per material may be primary, enforced by a partial unique
    index. Clearing the others in a separate statement first would leave a
    window in which two rows claim it and the index rejects the insert --
    a correct refusal that reads to the user as "saving failed for no
    reason". So the demotion and the promotion are one statement, and the
    index remains the mechanism rather than the error path.

    `ON CONFLICT` on the pair, because "add supplier B" and "change
    supplier B's lead time" are the same intent from the screen's point of
    view, and a 409 for the second would be an implementation detail
    leaking into the product.
    """
    if spec.quoted_price_per_kg is not None and not spec.currency:
        raise SupplierError("a price with no currency is a number, not a price")

    # Demote first, in the same transaction and before the upsert, so the
    # partial unique index never sees two primaries. Restricted to this
    # material and organization.
    if spec.is_primary is True:
        session.execute(
            text(
                """
                UPDATE materials.material_suppliers
                SET is_primary = FALSE, updated_at = now()
                WHERE organization_id = :org AND material_id = :mid
                  AND is_primary AND supplier_id <> :sid
                """
            ),
            {"org": organization_id, "mid": material_id, "sid": spec.supplier_id},
        )

    try:
        with guarded_write(session):
            link_id: uuid.UUID = session.execute(
                text(
                    """
                    INSERT INTO materials.material_suppliers
                        (organization_id, material_id, supplier_id, supplier_part_code,
                         is_primary, lead_time_days, quoted_price_per_kg, currency,
                         qualified_on, notes)
                    VALUES
                        (:org, :mid, :sid, :part_code,
                         COALESCE(CAST(:is_primary AS BOOLEAN), FALSE),
                         :lead_time, :price, :currency,
                         :qualified_on, :notes)
                    ON CONFLICT (organization_id, material_id, supplier_id) DO UPDATE
                    SET supplier_part_code  = EXCLUDED.supplier_part_code,
                        -- COALESCE, not EXCLUDED: a NULL means the caller
                        -- did not mention the flag, and an upsert must not
                        -- demote the primary supplier as a side effect of
                        -- someone editing a lead time.
                        is_primary          = COALESCE(EXCLUDED.is_primary,
                                                       materials.material_suppliers.is_primary),
                        lead_time_days      = EXCLUDED.lead_time_days,
                        quoted_price_per_kg = EXCLUDED.quoted_price_per_kg,
                        currency            = EXCLUDED.currency,
                        qualified_on        = EXCLUDED.qualified_on,
                        notes               = EXCLUDED.notes,
                        updated_at          = now()
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "mid": material_id,
                    "sid": spec.supplier_id,
                    "part_code": spec.supplier_part_code,
                    "is_primary": spec.is_primary,
                    "lead_time": spec.lead_time_days,
                    "price": spec.quoted_price_per_kg,
                    "currency": spec.currency,
                    "qualified_on": spec.qualified_on,
                    "notes": spec.notes,
                },
            ).scalar_one()
    except IntegrityError as exc:
        detail = str(exc.orig)
        if "material_suppliers_material_fk" in detail:
            raise MaterialNotFoundError("no such material in this organization") from exc
        if "material_suppliers_supplier_fk" in detail:
            raise SupplierNotFoundError("no such supplier in this organization") from exc
        raise SupplierError(detail) from exc

    write_audit(
        session,
        AuditEvent(
            action="material.supplier_linked",
            entity_type="material",
            entity_id=str(material_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"supplier_id": str(spec.supplier_id), "is_primary": spec.is_primary},
            reason="supplier attached to material",
        ),
    )
    return link_id


# ---------------------------------------------------------------------------
# Documents -- TDS / SDS / CoA
# ---------------------------------------------------------------------------


def _permitted_document_types(session: Session) -> set[str]:
    """The document types the DATABASE accepts, read from its own CHECK.

    🔴 READ, NOT REPEATED. `material_documents_document_type_check` is the
    authority; a Python tuple beside it is a second copy that drifts the moment
    a migration widens the constraint -- which 056 did, adding `label`,
    `product_image`, `literature` and `patent`. The copy would have gone on
    refusing all four, and the symptom would have been a schema that permits a
    competitor label and a writer that cannot write one.
    """
    definition = session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'material_documents_document_type_check'"
        )
    ).scalar_one_or_none()
    if not definition:
        # Fail loud rather than silently permitting everything: a missing
        # constraint is a schema problem, not a licence.
        raise MaterialInvalidError(
            "material_documents_document_type_check is missing; the permitted "
            "document types cannot be established"
        )
    return set(re.findall(r"'([a-zA-Z_]+)'::text", definition))


def store_document(
    session: Session,
    *,
    material_id: uuid.UUID | None = None,
    competitor_product_id: uuid.UUID | None = None,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: DocumentInput,
    data: bytes,
    filename: str,
    store: ObjectStoragePort,
    scanner: MalwareScannerPort,
) -> uuid.UUID:
    """Store a controlled document: validate, scan, write bytes, then the row.

    🔴 THIS REPLACES `register_document`, IT DOES NOT SIT BESIDE IT.

    A second entry point would be the I5/I36 shape this codebase has already
    logged twice -- two implementations of one thing, where the older, weaker
    one keeps being reachable. `register_document` accepted a `storage_key` and
    wrote a row; there is no longer any way to do that.

    THE ORDER IS THE CONTROL, and each step is refused rather than repaired:

      1. `validate_upload` -- size, extension, MAGIC BYTES, declared type. The
         extension and the content type are both claims by the uploader.
      2. `scanner.scan`   -- and an UNAVAILABLE scanner raises. It is never
         read as clean; that is the whole design of `MalwareScannerPort`.
      3. `store.put`      -- returns the checksum and size IT observed.
      4. the row          -- `approved`, carrying that evidence plus the
         scanner's name and version.

    Nothing is written to the database before the scan, so a quarantine state
    is not needed for the happy path: a file that fails is simply never stored.
    `quarantined` remains in the schema for the asynchronous pipeline the
    Research Center will need (E10), where ingestion and verdict are separated
    in time.

    ⚠️ THE BYTES ARE HELD IN MEMORY. That is why `MAX_UPLOAD_BYTES` is 25 MB and
    is checked FIRST. A streaming scan-then-store would avoid it, but clamd's
    INSTREAM wants the content and the checksum must describe what was stored,
    so a bounded buffer is the honest trade at this size.
    """
    # 🔴 EXACTLY ONE OWNER, CHECKED BEFORE ANY BYTES ARE STORED.
    #
    # 056 lets a controlled document belong to a material OR to a competitor
    # product, because §14 forbids a second document repository and a
    # competitor's label needs the same checksum, scan verdict, expiry and
    # supersession rules an SDS gets. The database enforces exactly-one-owner;
    # this refuses early so a rejected upload never reaches object storage.
    if (material_id is None) == (competitor_product_id is None):
        raise MaterialInvalidError(
            "a document belongs to exactly one owner: a material or a "
            "competitor product, never both and never neither"
        )

    # 🔴 THE ACCEPTED TYPES ARE READ FROM THE DATABASE'S OWN CHECK.
    #
    # This was a Python tuple repeating what `material_documents_document_type_check`
    # already says. 056 added `label`, `product_image`, `literature` and
    # `patent` to the constraint, and the literal here would have gone on
    # refusing all four -- a schema that permits a competitor label and a
    # writer that cannot write one. Two literals in two files cannot be
    # type-checked into agreement, so there is now one.
    permitted = _permitted_document_types(session)
    if spec.document_type not in permitted:
        raise MaterialInvalidError(
            f"'{spec.document_type}' is not a document type. "
            f"Permitted: {', '.join(sorted(permitted))}"
        )

    # 1. What is it, really?
    # Deliberately NOT wrapped in MaterialInvalidError. That would map to 422
    # through `_invalid`, the same status the route gives a file the SCANNER
    # condemned -- and those are different things a client must be able to tell
    # apart: one means "send a different file", the other means "this file is
    # hostile and the attempt was recorded".
    content_type, display_name = validate_upload(
        data=data, filename=filename, declared_content_type=spec.content_type
    )

    # 2. Is it safe? An unavailable scanner propagates -- see MalwareScannerPort.
    verdict = scanner.scan(data)
    if not verdict.clean:
        # Recorded, then refused. The signature is on the exception so the
        # route can audit WHAT was found rather than only that something was.
        raise MalwareFoundError(verdict.signature or "unknown")

    # 3. Write the bytes, and learn what was actually written.
    key = new_object_key(organization_id, spec.document_type)
    stored = store.put(key, io.BytesIO(data), content_type)

    # 4. Only now does a row exist, and it carries the store's own evidence.
    try:
        with guarded_write(session):
            document_id: uuid.UUID | None = session.execute(
                text(
                    """
                    INSERT INTO materials.material_documents
                        (organization_id, material_id, competitor_product_id,
                         document_type, title, storage_key,
                         content_type, byte_size, checksum_sha256, issued_on, expires_on,
                         supersedes_id, uploaded_by, original_filename,
                         status, scan_status, scanner_name, scanner_version, scanned_at)
                    -- 🔴 STILL AN `INSERT ... SELECT`, AND STILL FOR THE SAME
                    -- REASON. The owner row is read under the caller's RLS, so
                    -- an owner they cannot see yields NO SOURCE ROW and no
                    -- document -- rather than a row referencing something they
                    -- were never allowed to know exists. The UNION covers the
                    -- two owners without weakening that: exactly one branch can
                    -- ever produce a row, because exactly one id is non-null.
                    SELECT CAST(:org AS UUID), m.id, NULL::uuid, :dtype, :title, :key,
                           :content_type, CAST(:size AS BIGINT), :checksum,
                           CAST(:issued AS DATE), CAST(:expires AS DATE),
                           CAST(:supersedes AS UUID), CAST(:actor AS UUID), :original,
                           'approved', 'clean', :scanner, :scanner_version, now()
                    FROM materials.materials m
                    WHERE m.id = :mid AND m.organization_id = :org
                    UNION ALL
                    SELECT CAST(:org AS UUID), NULL::uuid, cp.id, :dtype, :title, :key,
                           :content_type, CAST(:size AS BIGINT), :checksum,
                           CAST(:issued AS DATE), CAST(:expires AS DATE),
                           CAST(:supersedes AS UUID), CAST(:actor AS UUID), :original,
                           'approved', 'clean', :scanner, :scanner_version, now()
                    FROM competitors.products cp
                    WHERE cp.id = :cpid AND cp.organization_id = :org
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "mid": material_id,
                    "cpid": competitor_product_id,
                    "dtype": spec.document_type,
                    "title": spec.title,
                    "key": stored.key,
                    "content_type": content_type,
                    "size": stored.byte_size,
                    "checksum": stored.checksum_sha256,
                    "issued": spec.issued_on,
                    "expires": spec.expires_on,
                    "supersedes": spec.supersedes_id,
                    "actor": actor_id,
                    "original": display_name,
                    "scanner": verdict.scanner,
                    "scanner_version": verdict.version,
                },
            ).scalar_one_or_none()
    except IntegrityError as exc:
        store.delete(stored.key)
        detail = str(exc.orig)
        if "material_documents_storage_key_unique" in detail:
            raise MaterialInvalidError(
                "a document with that storage key is already registered"
            ) from exc
        if "material_documents_supersedes_fk" in detail:
            raise MaterialNotFoundError("the superseded document does not exist here") from exc
        raise MaterialInvalidError(detail) from exc

    if document_id is None:
        # INSERT ... SELECT with no source row: the material is not visible to
        # this caller. The bytes are removed rather than orphaned -- a stored
        # object no row references is invisible to every quota, retention and
        # deletion path in the system (I49).
        store.delete(stored.key)
        raise MaterialNotFoundError(
            "no such material in this organization"
            if material_id is not None
            else "no such competitor product in this organization"
        )

    write_audit(
        session,
        AuditEvent(
            action="material.document_stored",
            entity_type="material",
            entity_id=str(material_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "document_type": spec.document_type,
                "title": spec.title,
                # The evidence, in the audit trail, because "which scanner
                # cleared this SDS" is a question a regulated audit asks.
                "checksum_sha256": stored.checksum_sha256,
                "byte_size": stored.byte_size,
                "scanner": f"{verdict.scanner} {verdict.version}",
            },
            reason="controlled document stored, scanned and approved",
        ),
    )
    return document_id


def list_competitor_documents(
    session: Session, *, competitor_product_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The document register for one competitor product, newest first.

    Beside `list_material_documents` rather than inside it: the two take
    different owners and a single function with two optional arguments would
    have a branch nobody reads. They share the TABLE, which is the thing §14
    cares about; sharing the query would save four lines and cost the caller
    clarity about which owner it is asking for.
    """
    rows = session.execute(
        text(
            """
            SELECT id, document_type, title, storage_key, content_type, byte_size,
                   checksum_sha256, issued_on, expires_on, supersedes_id, created_at
            FROM materials.material_documents
            WHERE competitor_product_id = :cpid AND organization_id = :org
            ORDER BY document_type, issued_on DESC NULLS LAST, created_at DESC
            """
        ),
        {"cpid": competitor_product_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]


def list_material_documents(
    session: Session, *, material_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The document register for one material, newest first.

    `expires_on` comes back so a screen can show an SDS that has lapsed.
    An expired safety data sheet is not the same as a missing one and the
    two must not render alike.
    """
    rows = session.execute(
        text(
            """
            SELECT id, document_type, title, storage_key, content_type, byte_size,
                   checksum_sha256, issued_on, expires_on, supersedes_id, created_at
            FROM materials.material_documents
            WHERE material_id = :mid AND organization_id = :org
            ORDER BY document_type, issued_on DESC NULLS LAST, created_at DESC
            """
        ),
        {"mid": material_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


#: Every stored NUMERIC a material row can carry. They are serialised as
#: STRINGS so the stored scale survives the wire -- see _with_percentages.
#: Add to this list whenever a NUMERIC column joins the row, or it will
#: silently go out as a float.
_QUANTITY_KEYS = (
    "density_g_cm3",
    "solids_fraction",
    "voc_fraction",
    "cost_per_kg",
    "epoxy_equivalent_weight",
    "amine_hydrogen_equivalent_weight",
    "quoted_price_per_kg",
)


def _with_percentages(row: dict[str, Any]) -> dict[str, Any]:
    """Add the percentage forms of the stored fractions.

    🔴 THE CONVERSION IS THE ENGINE'S, NOT THIS MODULE'S AND NOT THE UI'S.

    `solids_fraction` and `voc_fraction` are stored 0-1 because that is
    what the engine consumes. Every screen displays them as percentages,
    and the obvious place to multiply by 100 is the React cell that
    renders them -- which is exactly where Codex already caught it once on
    this project, and where it is genuinely wrong rather than merely
    misplaced, because `0.35 * 100` in JavaScript is 35.000000000000004.

    So the API sends both forms and the browser does no arithmetic at all.
    `fraction_to_percent` is exact under `Decimal` and preserves the scale,
    so a solids fraction recorded to four places renders to four places.

    A missing fraction stays missing. It is NOT rendered as 0% -- an
    unmeasured solids content and a genuinely zero one are different
    facts, and this project has already shipped a defect where a blank
    measurement rendered a green PASS.
    """
    for fraction_key, percent_key in (
        ("solids_fraction", "solids_percent"),
        ("voc_fraction", "voc_percent"),
    ):
        value = row.get(fraction_key)
        row[percent_key] = None if value is None else str(fraction_to_percent(value))

    # 🔴 THE STORED QUANTITIES MUST BE STRINGIFIED TOO, AND THEY WERE NOT.
    #
    # Only the two derived percentages above were. Everything else left
    # this function as a `Decimal`, and FastAPI's jsonable_encoder maps
    # Decimal -> FLOAT. Measured:
    #
    #     jsonable_encoder(Decimal("1.1000"))  ->  1.1   (a float)
    #
    # So a density recorded to four places went out as a JSON number with
    # one, which is precisely the round trip the docstring above says the
    # whole Decimal discipline exists to prevent -- and the web client,
    # which correctly types these as strings, rejected every live row with
    # a parse error.
    #
    # Nothing caught it because the end-to-end test STUBS this response
    # with the shape the client wants. A test that supplies its own
    # contract cannot detect a contract mismatch. Codex found it.
    return _stringify_quantities(row)


def _stringify_quantities(row: dict[str, Any]) -> dict[str, Any]:
    """Every NUMERIC in the row, as a string.

    Split out of :func:`_with_percentages` because a row can need this WITHOUT
    needing the derived percentages: a `material_suppliers` row carries
    `quoted_price_per_kg` and no fractions, and running the percentage half
    over it would attach `solids_percent: null` to a supplier.

    🔴 THE SPLIT IS ALSO THE FIX FOR A SECOND INSTANCE OF THE SAME DEFECT.
    `get_material` -- the detail endpoint the edit form loads from -- built its
    response by hand and called neither helper, so it returned raw `Decimal`s
    and FastAPI encoded them as floats. Every material with a density, cost or
    fraction failed the client's parse, and the scale was lost on the wire
    exactly as `_with_percentages` documents. The list path had been fixed; the
    detail path had never gone through it.
    """
    for quantity_key in _QUANTITY_KEYS:
        if quantity_key in row:
            row[quantity_key] = _num(row[quantity_key])
    return row


def _num(value: Decimal | None) -> str | None:
    """Render a Decimal for the audit payload without going through float.

    `float(Decimal("34.75"))` is exact, `float(Decimal("0.1"))` is not, and
    an audit record is supposed to be the thing you can trust when the
    application disagrees with itself. Strings preserve the stored scale.
    """
    return None if value is None else str(value)


def _translate_material_integrity_error(exc: IntegrityError, code: str) -> MaterialsError:
    """Turn a constraint name into a message the chemist can act on.

    Matching on the CONSTRAINT NAME, not on the message text: PostgreSQL's
    wording varies by version and locale, and a substring match on prose
    is a check that silently stops working after an upgrade.
    """
    detail = str(exc.orig)
    if "materials_org_code_key" in detail:
        return MaterialDuplicateError(
            f"material code '{code}' is already used in this organization"
        )
    if "materials_restriction_has_a_reason" in detail:
        return MaterialInvalidError("a restricted material must state why it is restricted")
    if "materials_role_check" in detail:
        return MaterialInvalidError("that is not a recognised material role")
    if "materials_status_check" in detail:
        return MaterialInvalidError("that is not a recognised material status")
    return MaterialInvalidError(detail)
