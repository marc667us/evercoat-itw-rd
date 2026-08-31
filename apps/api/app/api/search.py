"""Global search, over HTTP — spec §29.

🔴 THIS ROUTE IS GATED ON AUTHENTICATION, NOT ON ONE PERMISSION, AND THAT IS
THE WHOLE DESIGN.

Every other read route in this API names the permission it needs. This one
cannot: a search box in the top bar is reachable by all ten roles, and gating
it on any single permission would either lock a role out of search entirely or
hand every role a permission it should not have. The authorization lives one
level down, per record type, in `SEARCHABLE` — a caller without
`material.view` runs no material branch at all.

So the rule this project applies to every route — *which production path
enforces this permission?* — is answered here by
`test_search_filters_by_permission_in_both_directions`, which asserts the same
query returns a material for a caller holding `material.view` and returns
nothing for one who does not. A gate asserted in only one direction is not a
gate, and this repository has counted six of those.

⚠️ THERE IS NO WRITE ROUTE IN THIS FILE, AND THERE SHOULD NEVER BE ONE.
Search reads. A "save this search" feature would be a new table with its own
writer and its own control, not an eighth verb bolted onto the search box.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_db, get_principal
from app.domains.search.service import (
    ABSENT,
    MAX_SEARCH_RESULTS,
    MIN_QUERY_LENGTH,
    SearchError,
    global_search,
    searchable_types,
)

router = APIRouter()


@router.get("", summary="Search every record type this caller may reach")
def get_search(
    q: str = Query(min_length=MIN_QUERY_LENGTH, max_length=200),
    limit: int = Query(default=MAX_SEARCH_RESULTS, ge=1, le=MAX_SEARCH_RESULTS),
    types: list[str] | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ranked record hits, plus what was and was not searched.

    The response carries `searched` and `absent` alongside the results because
    "no results" and "not searched" are different answers and a screen that
    conflates them tells the user something false. A chemist who cannot see
    failures should be told failures were not searched, not that there are
    none.
    """
    selected = tuple(types) if types else None
    try:
        outcome = global_search(
            session,
            organization_id=principal.organization_id,
            permissions=principal.permissions,
            question=q,
            limit=limit,
            types=selected,
        )
    except SearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    results = outcome["results"]
    return {
        "query": q,
        "results": results,
        "result_count": len(results),
        # 🔴 REPORTED, NOT INFERRED FROM THE RESULTS. A type with zero hits and
        # a type the caller may not search look identical in `results`.
        #
        # ✅ `selected` IS PASSED IN NOW. Codex P2: this called
        # `searchable_types(principal.permissions)` and labelled the answer
        # `searched`, so `?types=material` reported fourteen types as searched
        # when their branches had not run. Each row now carries `permitted`
        # (may this caller search it) and `searched` (did this request), which
        # differ exactly when a type filter was supplied.
        "searched": searchable_types(principal.permissions, selected),
        "absent": [{"record_type": k, "reason": v} for k, v in sorted(ABSENT.items())],
        # ✅ MEASURED, NOT INFERRED. Codex P2: `len(results) == limit` is also
        # true for an exactly-complete answer, so the screen said "the list is
        # capped" about a whole one. The service fetches one row more than
        # asked for and reports whether it got it.
        "truncated": outcome["truncated"],
    }
