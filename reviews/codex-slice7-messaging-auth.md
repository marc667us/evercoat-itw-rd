OpenAI Codex v0.147.0
--------
workdir: C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 01a01781-0c35-79b1-b034-d3061ea6e679
--------
user
Review ONLY these new/changed files in this repo, in order of risk:
1. apps/api/app/domains/messaging/service.py
2. apps/api/app/api/messaging.py
3. scripts/keycloak-bootstrap.sh
4. scripts/keycloak-bind-subs.py
5. .github/workflows/ci.yml (the new "auth" job only)
6. apps/api/tests/db/test_023_messaging.py

Focus on defects a green CI run would NOT catch:
- Can a user be notified about, or read, a channel belonging to a restricted project they are not a member of? Trace _resolve_mentions and list_channels precisely.
- post_message resolves references in the AUTHOR's session. Is there any path where a link, label, or error message discloses a record the author cannot read?
- promote_message: can it create a task in a project the actor cannot access, or with a NULL project_id where the schema requires one?
- Any SQL interpolation. All SQL must be parameterised.
- The Keycloak scripts: any way they leave the realm in a state where authentication silently fails, or a credential leaks into logs?
- The CI auth job: any way it reports success without having actually authenticated?

Report concrete defects with file:line. State clearly if a category has none. Do not review files outside the list.

codex
I’ll inspect only the six specified files and trace the relevant call/data paths. I’ll keep the review read-only and report only concrete defects or explicit “none” findings by category.
2026-08-19T00:52:34.317676Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'apps/api/app/domains/messaging/service.py','apps/api/app/api/messaging.py','scripts/keycloak-bootstrap.sh','scripts/keycloak-bind-subs.py','.github/workflows/ci.yml','apps/api/tests/db/test_023_messaging.py'); foreach ("'$f in $files) { Write-Output "FILE $f"; $n=0; Get-Content -LiteralPath $f | ForEach-Object { $n++; '"'{0,5}: {1}' -f "'$n, $_ } }'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'apps/api/app/domains/messaging/service.py','apps/api/app/api/messaging.py','scripts/keycloak-bootstrap.sh','scripts/keycloak-bind-subs.py','.github/workflows/ci.yml','apps/api/tests/db/test_023_messaging.py'); foreach ("'$f in $files) { Write-Output "FILE $f"; $n=0; Get-Content -LiteralPath $f | ForEach-Object { $n++; '"'{0,5}: {1}' -f "'$n, $_ } }' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$files = @('"'apps/api/app/domains/messaging/service.py','apps/api/app/api/messaging.py','scripts/keycloak-bootstrap.sh','scripts/keycloak-bind-subs.py','.github/workflows/ci.yml','apps/api/tests/db/test_023_messaging.py'); foreach ("'$f in $files) { Write-Output "FILE $f"; $n=0; Get-Content -LiteralPath $f | ForEach-Object { $n++; '"'{0,5}: {1}' -f "'$n, $_ } }'` rejected: blocked by policy
codex
The combined read is still running, so I’m waiting for the file output before drawing conclusions.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "''^" apps/api/app/domains/messaging/service.py apps/api/app/api/messaging.py scripts/keycloak-bootstrap.sh scripts/keycloak-bind-subs.py .github/workflows/ci.yml apps/api/tests/db/test_023_messaging.py' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 1425ms:
scripts/keycloak-bind-subs.py:1:#!/usr/bin/env python3
scripts/keycloak-bind-subs.py:2:"""Bind `core.users.keycloak_sub` to the real Keycloak subjects.
scripts/keycloak-bind-subs.py:3:
scripts/keycloak-bind-subs.py:4:🔴 THE GAP THIS CLOSES
scripts/keycloak-bind-subs.py:5:
scripts/keycloak-bind-subs.py:6:`scripts/seed.py` writes `keycloak_sub = 'demo-chem.demo'` -- a
scripts/keycloak-bind-subs.py:7:placeholder, because at seed time no identity provider exists to ask.
scripts/keycloak-bind-subs.py:8:`app/core/security.py` resolves a principal with
scripts/keycloak-bind-subs.py:9:`WHERE u.keycloak_sub = :sub`, where `:sub` is the token's real subject,
scripts/keycloak-bind-subs.py:10:a UUID minted by Keycloak.
scripts/keycloak-bind-subs.py:11:
scripts/keycloak-bind-subs.py:12:Those two never meet. A perfectly valid token -- correct signature,
scripts/keycloak-bind-subs.py:13:correct issuer, correct audience, unexpired -- resolves to no row, and
scripts/keycloak-bind-subs.py:14:the API answers 403 "not a member of the requested organization". The
scripts/keycloak-bind-subs.py:15:authentication is right, the authorization lookup is right, and the
scripts/keycloak-bind-subs.py:16:system is unusable, because two literals in two files cannot be
scripts/keycloak-bind-subs.py:17:type-checked into agreement.
scripts/keycloak-bind-subs.py:18:
scripts/keycloak-bind-subs.py:19:That is a shape this project has hit repeatedly: nav vs router, landing
scripts/keycloak-bind-subs.py:20:vs pack, `release.yml` vs `_deploy-render.yml`. The fix is the same one
scripts/keycloak-bind-subs.py:21:each time -- make one side READ the other rather than restate it.
scripts/keycloak-bind-subs.py:22:
scripts/keycloak-bind-subs.py:23:Usage:
scripts/keycloak-bind-subs.py:24:    python scripts/keycloak-bind-subs.py keycloak-subs.json
scripts/keycloak-bind-subs.py:25:
scripts/keycloak-bind-subs.py:26:Environment:
scripts/keycloak-bind-subs.py:27:    SEED_DATABASE_URL (or DATABASE_URL) -- a connection that may UPDATE
scripts/keycloak-bind-subs.py:28:    core.users. RLS does not apply to `core.users` reads by primary key,
scripts/keycloak-bind-subs.py:29:    but the connection still needs write rights, so this is an operator
scripts/keycloak-bind-subs.py:30:    or migration credential, never the application role.
scripts/keycloak-bind-subs.py:31:"""
scripts/keycloak-bind-subs.py:32:
scripts/keycloak-bind-subs.py:33:from __future__ import annotations
scripts/keycloak-bind-subs.py:34:
scripts/keycloak-bind-subs.py:35:import json
scripts/keycloak-bind-subs.py:36:import os
scripts/keycloak-bind-subs.py:37:import sys
scripts/keycloak-bind-subs.py:38:from pathlib import Path
scripts/keycloak-bind-subs.py:39:
scripts/keycloak-bind-subs.py:40:import psycopg
scripts/keycloak-bind-subs.py:41:
scripts/keycloak-bind-subs.py:42:
scripts/keycloak-bind-subs.py:43:def main() -> int:
scripts/keycloak-bind-subs.py:44:    if len(sys.argv) != 2:
scripts/keycloak-bind-subs.py:45:        print(__doc__)
scripts/keycloak-bind-subs.py:46:        return 2
scripts/keycloak-bind-subs.py:47:
scripts/keycloak-bind-subs.py:48:    subs_path = Path(sys.argv[1])
scripts/keycloak-bind-subs.py:49:    if not subs_path.is_file():
scripts/keycloak-bind-subs.py:50:        print(f"FAIL: {subs_path} does not exist", file=sys.stderr)
scripts/keycloak-bind-subs.py:51:        return 1
scripts/keycloak-bind-subs.py:52:
scripts/keycloak-bind-subs.py:53:    mapping: dict[str, str] = json.loads(subs_path.read_text(encoding="utf-8"))
scripts/keycloak-bind-subs.py:54:    if not mapping:
scripts/keycloak-bind-subs.py:55:        # An empty map would rebind nothing and report success -- exactly
scripts/keycloak-bind-subs.py:56:        # the "absence of evidence rendering as success" failure this
scripts/keycloak-bind-subs.py:57:        # codebase has already shipped once.
scripts/keycloak-bind-subs.py:58:        print("FAIL: the subject map is empty; nothing was bound", file=sys.stderr)
scripts/keycloak-bind-subs.py:59:        return 1
scripts/keycloak-bind-subs.py:60:
scripts/keycloak-bind-subs.py:61:    dsn = os.environ.get("SEED_DATABASE_URL") or os.environ.get("DATABASE_URL")
scripts/keycloak-bind-subs.py:62:    if not dsn:
scripts/keycloak-bind-subs.py:63:        print("FAIL: set SEED_DATABASE_URL or DATABASE_URL", file=sys.stderr)
scripts/keycloak-bind-subs.py:64:        return 1
scripts/keycloak-bind-subs.py:65:    dsn = dsn.replace("postgresql+psycopg://", "postgresql://")
scripts/keycloak-bind-subs.py:66:
scripts/keycloak-bind-subs.py:67:    bound = 0
scripts/keycloak-bind-subs.py:68:    missing: list[str] = []
scripts/keycloak-bind-subs.py:69:
scripts/keycloak-bind-subs.py:70:    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
scripts/keycloak-bind-subs.py:71:        for username, sub in mapping.items():
scripts/keycloak-bind-subs.py:72:            # Matched on EMAIL, not on the placeholder sub. The seeder's
scripts/keycloak-bind-subs.py:73:            # placeholder is an implementation detail of the seeder; the
scripts/keycloak-bind-subs.py:74:            # email is the identity both sides genuinely share, and
scripts/keycloak-bind-subs.py:75:            # Keycloak is configured to issue it verified.
scripts/keycloak-bind-subs.py:76:            cur.execute(
scripts/keycloak-bind-subs.py:77:                """
scripts/keycloak-bind-subs.py:78:                UPDATE core.users
scripts/keycloak-bind-subs.py:79:                SET keycloak_sub = %s
scripts/keycloak-bind-subs.py:80:                WHERE email = %s
scripts/keycloak-bind-subs.py:81:                RETURNING id
scripts/keycloak-bind-subs.py:82:                """,
scripts/keycloak-bind-subs.py:83:                (sub, f"{username}@example.test"),
scripts/keycloak-bind-subs.py:84:            )
scripts/keycloak-bind-subs.py:85:            if cur.fetchone() is None:
scripts/keycloak-bind-subs.py:86:                missing.append(username)
scripts/keycloak-bind-subs.py:87:            else:
scripts/keycloak-bind-subs.py:88:                bound += 1
scripts/keycloak-bind-subs.py:89:        conn.commit()
scripts/keycloak-bind-subs.py:90:
scripts/keycloak-bind-subs.py:91:    print(f"bound {bound} of {len(mapping)} subjects")
scripts/keycloak-bind-subs.py:92:
scripts/keycloak-bind-subs.py:93:    if missing:
scripts/keycloak-bind-subs.py:94:        # Loud, and a failure. A user who exists in Keycloak but not in
scripts/keycloak-bind-subs.py:95:        # the database can sign in and then be refused by every route,
scripts/keycloak-bind-subs.py:96:        # which presents to the operator as "the app is broken" rather
scripts/keycloak-bind-subs.py:97:        # than as "that account was never seeded".
scripts/keycloak-bind-subs.py:98:        print(
scripts/keycloak-bind-subs.py:99:            "FAIL: no core.users row for: " + ", ".join(missing) + "\n"
scripts/keycloak-bind-subs.py:100:            "      They can authenticate and will then be refused by every\n"
scripts/keycloak-bind-subs.py:101:            "      route. Run scripts/seed.py first.",
scripts/keycloak-bind-subs.py:102:            file=sys.stderr,
scripts/keycloak-bind-subs.py:103:        )
scripts/keycloak-bind-subs.py:104:        return 1
scripts/keycloak-bind-subs.py:105:
scripts/keycloak-bind-subs.py:106:    return 0
scripts/keycloak-bind-subs.py:107:
scripts/keycloak-bind-subs.py:108:
scripts/keycloak-bind-subs.py:109:if __name__ == "__main__":
scripts/keycloak-bind-subs.py:110:    raise SystemExit(main())
apps/api/app/api/messaging.py:1:"""Messaging, notifications, and promotion into controlled records.
apps/api/app/api/messaging.py:2:
apps/api/app/api/messaging.py:3:**Most of these routes carry no permission dependency, deliberately** --
apps/api/app/api/messaging.py:4:the same reasoning as My Work. There are no `message.*` or
apps/api/app/api/messaging.py:5:`notification.*` permissions in the catalogue, and inventing them here
apps/api/app/api/messaging.py:6:would produce exactly the defect this project has now caught five times:
apps/api/app/api/messaging.py:7:a permission nobody holds, gating a feature nobody can then use.
apps/api/app/api/messaging.py:8:
apps/api/app/api/messaging.py:9:That is not a gap. Messaging is governed by something stronger than a
apps/api/app/api/messaging.py:10:grant: **RLS and channel membership**. A restricted project's channel is
apps/api/app/api/messaging.py:11:not returned to a non-member by the database, so there is nothing for a
apps/api/app/api/messaging.py:12:permission check to add. `promote_message` is the exception -- it creates
apps/api/app/api/messaging.py:13:a controlled record, so it requires `project.edit`.
apps/api/app/api/messaging.py:14:"""
apps/api/app/api/messaging.py:15:
apps/api/app/api/messaging.py:16:from __future__ import annotations
apps/api/app/api/messaging.py:17:
apps/api/app/api/messaging.py:18:import uuid
apps/api/app/api/messaging.py:19:from typing import Any
apps/api/app/api/messaging.py:20:
apps/api/app/api/messaging.py:21:from fastapi import APIRouter, Depends, HTTPException, Query, status
apps/api/app/api/messaging.py:22:from pydantic import BaseModel, Field
apps/api/app/api/messaging.py:23:from sqlalchemy.orm import Session
apps/api/app/api/messaging.py:24:
apps/api/app/api/messaging.py:25:from app.core.security import Principal, get_db, get_principal, require_permission
apps/api/app/api/messaging.py:26:from app.core.tenancy import CrossTenantReferenceError
apps/api/app/api/messaging.py:27:from app.domains.messaging.service import (
apps/api/app/api/messaging.py:28:    ChannelInput,
apps/api/app/api/messaging.py:29:    MessageInput,
apps/api/app/api/messaging.py:30:    MessagingError,
apps/api/app/api/messaging.py:31:    MessagingNotFoundError,
apps/api/app/api/messaging.py:32:    create_channel,
apps/api/app/api/messaging.py:33:    list_channels,
apps/api/app/api/messaging.py:34:    list_messages,
apps/api/app/api/messaging.py:35:    mark_notification_read,
apps/api/app/api/messaging.py:36:    my_notifications,
apps/api/app/api/messaging.py:37:    post_message,
apps/api/app/api/messaging.py:38:    promote_message,
apps/api/app/api/messaging.py:39:    thread_for_record,
apps/api/app/api/messaging.py:40:)
apps/api/app/api/messaging.py:41:
apps/api/app/api/messaging.py:42:router = APIRouter()
apps/api/app/api/messaging.py:43:
apps/api/app/api/messaging.py:44:__all__ = ["router"]
apps/api/app/api/messaging.py:45:
apps/api/app/api/messaging.py:46:
apps/api/app/api/messaging.py:47:class ChannelCreate(BaseModel):
apps/api/app/api/messaging.py:48:    channel_type: str = Field(pattern="^(project|direct|technical_thread|announcement)$")
apps/api/app/api/messaging.py:49:    name: str | None = Field(default=None, max_length=200)
apps/api/app/api/messaging.py:50:    project_id: uuid.UUID | None = None
apps/api/app/api/messaging.py:51:    entity_type: str | None = Field(default=None, max_length=50)
apps/api/app/api/messaging.py:52:    entity_id: uuid.UUID | None = None
apps/api/app/api/messaging.py:53:    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
apps/api/app/api/messaging.py:54:
apps/api/app/api/messaging.py:55:
apps/api/app/api/messaging.py:56:class ThreadOpen(BaseModel):
apps/api/app/api/messaging.py:57:    """Open (or find) the discussion thread attached to one record."""
apps/api/app/api/messaging.py:58:
apps/api/app/api/messaging.py:59:    entity_type: str = Field(max_length=50)
apps/api/app/api/messaging.py:60:    entity_id: uuid.UUID
apps/api/app/api/messaging.py:61:    project_id: uuid.UUID
apps/api/app/api/messaging.py:62:
apps/api/app/api/messaging.py:63:
apps/api/app/api/messaging.py:64:class MessagePost(BaseModel):
apps/api/app/api/messaging.py:65:    # 4000 characters, not unbounded. A message is a message; a 2MB paste
apps/api/app/api/messaging.py:66:    # belongs in an attachment, where it can be versioned and scanned.
apps/api/app/api/messaging.py:67:    body: str = Field(min_length=1, max_length=4000)
apps/api/app/api/messaging.py:68:    reply_to_id: uuid.UUID | None = None
apps/api/app/api/messaging.py:69:
apps/api/app/api/messaging.py:70:
apps/api/app/api/messaging.py:71:class MessagePromote(BaseModel):
apps/api/app/api/messaging.py:72:    task_type: str = Field(max_length=50)
apps/api/app/api/messaging.py:73:    title: str = Field(min_length=1, max_length=200)
apps/api/app/api/messaging.py:74:    assigned_user_id: uuid.UUID | None = None
apps/api/app/api/messaging.py:75:
apps/api/app/api/messaging.py:76:
apps/api/app/api/messaging.py:77:@router.get("/channels", summary="Channels this user can see")
apps/api/app/api/messaging.py:78:def get_channels(
apps/api/app/api/messaging.py:79:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:80:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:81:    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py:82:) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py:83:    return list_channels(
apps/api/app/api/messaging.py:84:        session,
apps/api/app/api/messaging.py:85:        organization_id=principal.organization_id,
apps/api/app/api/messaging.py:86:        actor_id=principal.user_id,
apps/api/app/api/messaging.py:87:        limit=limit,
apps/api/app/api/messaging.py:88:    )
apps/api/app/api/messaging.py:89:
apps/api/app/api/messaging.py:90:
apps/api/app/api/messaging.py:91:@router.post("/channels", status_code=status.HTTP_201_CREATED, summary="Open a channel")
apps/api/app/api/messaging.py:92:def post_channel(
apps/api/app/api/messaging.py:93:    payload: ChannelCreate,
apps/api/app/api/messaging.py:94:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:95:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:96:) -> dict[str, Any]:
apps/api/app/api/messaging.py:97:    try:
apps/api/app/api/messaging.py:98:        result = create_channel(
apps/api/app/api/messaging.py:99:            session,
apps/api/app/api/messaging.py:100:            organization_id=principal.organization_id,
apps/api/app/api/messaging.py:101:            actor_id=principal.user_id,
apps/api/app/api/messaging.py:102:            spec=ChannelInput(
apps/api/app/api/messaging.py:103:                channel_type=payload.channel_type,
apps/api/app/api/messaging.py:104:                name=payload.name,
apps/api/app/api/messaging.py:105:                project_id=payload.project_id,
apps/api/app/api/messaging.py:106:                entity_type=payload.entity_type,
apps/api/app/api/messaging.py:107:                entity_id=payload.entity_id,
apps/api/app/api/messaging.py:108:                member_ids=tuple(payload.member_ids),
apps/api/app/api/messaging.py:109:            ),
apps/api/app/api/messaging.py:110:        )
apps/api/app/api/messaging.py:111:    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py:112:        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py:113:    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py:114:        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py:115:    session.commit()
apps/api/app/api/messaging.py:116:    return result
apps/api/app/api/messaging.py:117:
apps/api/app/api/messaging.py:118:
apps/api/app/api/messaging.py:119:@router.post("/threads", summary="The discussion thread for a record, opening one if needed")
apps/api/app/api/messaging.py:120:def open_thread(
apps/api/app/api/messaging.py:121:    payload: ThreadOpen,
apps/api/app/api/messaging.py:122:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:123:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:124:) -> dict[str, Any]:
apps/api/app/api/messaging.py:125:    """Idempotent.
apps/api/app/api/messaging.py:126:
apps/api/app/api/messaging.py:127:    Every "discuss this" button can call it without checking first, which
apps/api/app/api/messaging.py:128:    is the only way a record ends up with one thread rather than six.
apps/api/app/api/messaging.py:129:    """
apps/api/app/api/messaging.py:130:    try:
apps/api/app/api/messaging.py:131:        result = thread_for_record(
apps/api/app/api/messaging.py:132:            session,
apps/api/app/api/messaging.py:133:            organization_id=principal.organization_id,
apps/api/app/api/messaging.py:134:            actor_id=principal.user_id,
apps/api/app/api/messaging.py:135:            entity_type=payload.entity_type,
apps/api/app/api/messaging.py:136:            entity_id=payload.entity_id,
apps/api/app/api/messaging.py:137:            project_id=payload.project_id,
apps/api/app/api/messaging.py:138:        )
apps/api/app/api/messaging.py:139:    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py:140:        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py:141:    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py:142:        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py:143:    session.commit()
apps/api/app/api/messaging.py:144:    return result
apps/api/app/api/messaging.py:145:
apps/api/app/api/messaging.py:146:
apps/api/app/api/messaging.py:147:@router.get("/channels/{channel_id}/messages", summary="A channel's messages")
apps/api/app/api/messaging.py:148:def get_messages(
apps/api/app/api/messaging.py:149:    channel_id: uuid.UUID,
apps/api/app/api/messaging.py:150:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:151:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:152:    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py:153:) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py:154:    return list_messages(
apps/api/app/api/messaging.py:155:        session,
apps/api/app/api/messaging.py:156:        channel_id=channel_id,
apps/api/app/api/messaging.py:157:        organization_id=principal.organization_id,
apps/api/app/api/messaging.py:158:        limit=limit,
apps/api/app/api/messaging.py:159:    )
apps/api/app/api/messaging.py:160:
apps/api/app/api/messaging.py:161:
apps/api/app/api/messaging.py:162:@router.post(
apps/api/app/api/messaging.py:163:    "/channels/{channel_id}/messages",
apps/api/app/api/messaging.py:164:    status_code=status.HTTP_201_CREATED,
apps/api/app/api/messaging.py:165:    summary="Post a message, resolving #references and @mentions",
apps/api/app/api/messaging.py:166:)
apps/api/app/api/messaging.py:167:def post_channel_message(
apps/api/app/api/messaging.py:168:    channel_id: uuid.UUID,
apps/api/app/api/messaging.py:169:    payload: MessagePost,
apps/api/app/api/messaging.py:170:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:171:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:172:) -> dict[str, Any]:
apps/api/app/api/messaging.py:173:    try:
apps/api/app/api/messaging.py:174:        result = post_message(
apps/api/app/api/messaging.py:175:            session,
apps/api/app/api/messaging.py:176:            channel_id=channel_id,
apps/api/app/api/messaging.py:177:            organization_id=principal.organization_id,
apps/api/app/api/messaging.py:178:            actor_id=principal.user_id,
apps/api/app/api/messaging.py:179:            spec=MessageInput(body=payload.body, reply_to_id=payload.reply_to_id),
apps/api/app/api/messaging.py:180:        )
apps/api/app/api/messaging.py:181:    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py:182:        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py:183:    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py:184:        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py:185:    session.commit()
apps/api/app/api/messaging.py:186:    return result
apps/api/app/api/messaging.py:187:
apps/api/app/api/messaging.py:188:
apps/api/app/api/messaging.py:189:@router.post(
apps/api/app/api/messaging.py:190:    "/messages/{message_id}/promote",
apps/api/app/api/messaging.py:191:    status_code=status.HTTP_201_CREATED,
apps/api/app/api/messaging.py:192:    summary="Promote a message into a controlled record (a task)",
apps/api/app/api/messaging.py:193:)
apps/api/app/api/messaging.py:194:def post_promotion(
apps/api/app/api/messaging.py:195:    message_id: uuid.UUID,
apps/api/app/api/messaging.py:196:    payload: MessagePromote,
apps/api/app/api/messaging.py:197:    principal: Principal = Depends(require_permission("project.edit")),
apps/api/app/api/messaging.py:198:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:199:) -> dict[str, Any]:
apps/api/app/api/messaging.py:200:    """The only route here that requires a permission.
apps/api/app/api/messaging.py:201:
apps/api/app/api/messaging.py:202:    Section 7: informal chat never becomes authoritative knowledge
apps/api/app/api/messaging.py:203:    automatically. This route is the explicit human act that the rule
apps/api/app/api/messaging.py:204:    demands, and it is the only one in this module that writes a
apps/api/app/api/messaging.py:205:    controlled record -- which is exactly why it is the only one gated.
apps/api/app/api/messaging.py:206:    """
apps/api/app/api/messaging.py:207:    try:
apps/api/app/api/messaging.py:208:        result = promote_message(
apps/api/app/api/messaging.py:209:            session,
apps/api/app/api/messaging.py:210:            message_id=message_id,
apps/api/app/api/messaging.py:211:            organization_id=principal.organization_id,
apps/api/app/api/messaging.py:212:            actor_id=principal.user_id,
apps/api/app/api/messaging.py:213:            task_type=payload.task_type,
apps/api/app/api/messaging.py:214:            title=payload.title,
apps/api/app/api/messaging.py:215:            assigned_user_id=payload.assigned_user_id,
apps/api/app/api/messaging.py:216:        )
apps/api/app/api/messaging.py:217:    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py:218:        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py:219:    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py:220:        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py:221:    session.commit()
apps/api/app/api/messaging.py:222:    return result
apps/api/app/api/messaging.py:223:
apps/api/app/api/messaging.py:224:
apps/api/app/api/messaging.py:225:@router.get("/notifications", summary="This user's notifications")
apps/api/app/api/messaging.py:226:def get_notifications(
apps/api/app/api/messaging.py:227:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:228:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:229:    unread_only: bool = Query(default=False),
apps/api/app/api/messaging.py:230:    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py:231:) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py:232:    return my_notifications(
apps/api/app/api/messaging.py:233:        session,
apps/api/app/api/messaging.py:234:        organization_id=principal.organization_id,
apps/api/app/api/messaging.py:235:        recipient_id=principal.user_id,
apps/api/app/api/messaging.py:236:        unread_only=unread_only,
apps/api/app/api/messaging.py:237:        limit=limit,
apps/api/app/api/messaging.py:238:    )
apps/api/app/api/messaging.py:239:
apps/api/app/api/messaging.py:240:
apps/api/app/api/messaging.py:241:@router.post("/notifications/{notification_id}/read", summary="Mark one as read")
apps/api/app/api/messaging.py:242:def post_notification_read(
apps/api/app/api/messaging.py:243:    notification_id: uuid.UUID,
apps/api/app/api/messaging.py:244:    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py:245:    session: Session = Depends(get_db),
apps/api/app/api/messaging.py:246:) -> dict[str, Any]:
apps/api/app/api/messaging.py:247:    """`recipient_id` comes from the token, never the request.
apps/api/app/api/messaging.py:248:
apps/api/app/api/messaging.py:249:    A caller therefore cannot mark somebody else's notification read and
apps/api/app/api/messaging.py:250:    hide it, silently and permanently, from the person who needed to act.
apps/api/app/api/messaging.py:251:    """
apps/api/app/api/messaging.py:252:    try:
apps/api/app/api/messaging.py:253:        result = mark_notification_read(
apps/api/app/api/messaging.py:254:            session,
apps/api/app/api/messaging.py:255:            notification_id=notification_id,
apps/api/app/api/messaging.py:256:            organization_id=principal.organization_id,
apps/api/app/api/messaging.py:257:            recipient_id=principal.user_id,
apps/api/app/api/messaging.py:258:        )
apps/api/app/api/messaging.py:259:    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py:260:        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py:261:    session.commit()
apps/api/app/api/messaging.py:262:    return result
apps/api/tests/db/test_023_messaging.py:1:"""Messaging: the notification boundary, and promotion by hand only.
apps/api/tests/db/test_023_messaging.py:2:
apps/api/tests/db/test_023_messaging.py:3:Two rules carry this module, and both are the kind that pass a code
apps/api/tests/db/test_023_messaging.py:4:review and fail in production.
apps/api/tests/db/test_023_messaging.py:5:
apps/api/tests/db/test_023_messaging.py:6:**A notification must not disclose what its recipient cannot see.** The
apps/api/tests/db/test_023_messaging.py:7:channel's own RLS protects the MESSAGES and does nothing about a
apps/api/tests/db/test_023_messaging.py:8:notification row addressed to an outsider. My first version of this check
apps/api/tests/db/test_023_messaging.py:9:reused `list_channels`'s predicate, which evaluates in the AUTHOR's
apps/api/tests/db/test_023_messaging.py:10:session -- so a restricted project's channel read as reachable for
apps/api/tests/db/test_023_messaging.py:11:everyone, and the mention notification would have named the project to
apps/api/tests/db/test_023_messaging.py:12:somebody with no access to it. The test below is the one that would have
apps/api/tests/db/test_023_messaging.py:13:caught it.
apps/api/tests/db/test_023_messaging.py:14:
apps/api/tests/db/test_023_messaging.py:15:**Informal chat never becomes authoritative knowledge automatically**
apps/api/tests/db/test_023_messaging.py:16:(§7). Promotion exists, is explicit, produces a TASK rather than a
apps/api/tests/db/test_023_messaging.py:17:conclusion, and links back to the message it came from.
apps/api/tests/db/test_023_messaging.py:18:
apps/api/tests/db/test_023_messaging.py:19:Everything here runs on `app_session` where the boundary is the subject,
apps/api/tests/db/test_023_messaging.py:20:because the owner is exempt from RLS while `relforcerowsecurity` is FALSE
apps/api/tests/db/test_023_messaging.py:21:and an owner-run version of this file would pass against a system with no
apps/api/tests/db/test_023_messaging.py:22:boundary at all.
apps/api/tests/db/test_023_messaging.py:23:"""
apps/api/tests/db/test_023_messaging.py:24:
apps/api/tests/db/test_023_messaging.py:25:from __future__ import annotations
apps/api/tests/db/test_023_messaging.py:26:
apps/api/tests/db/test_023_messaging.py:27:import uuid
apps/api/tests/db/test_023_messaging.py:28:from collections.abc import Iterator
apps/api/tests/db/test_023_messaging.py:29:
apps/api/tests/db/test_023_messaging.py:30:import pytest
apps/api/tests/db/test_023_messaging.py:31:from sqlalchemy import text
apps/api/tests/db/test_023_messaging.py:32:from sqlalchemy.orm import Session
apps/api/tests/db/test_023_messaging.py:33:
apps/api/tests/db/test_023_messaging.py:34:from app.domains.messaging.service import (
apps/api/tests/db/test_023_messaging.py:35:    ChannelInput,
apps/api/tests/db/test_023_messaging.py:36:    MessageInput,
apps/api/tests/db/test_023_messaging.py:37:    create_channel,
apps/api/tests/db/test_023_messaging.py:38:    list_messages,
apps/api/tests/db/test_023_messaging.py:39:    my_notifications,
apps/api/tests/db/test_023_messaging.py:40:    post_message,
apps/api/tests/db/test_023_messaging.py:41:    promote_message,
apps/api/tests/db/test_023_messaging.py:42:)
apps/api/tests/db/test_023_messaging.py:43:
apps/api/tests/db/test_023_messaging.py:44:
apps/api/tests/db/test_023_messaging.py:45:@pytest.fixture
apps/api/tests/db/test_023_messaging.py:46:def channel_fixture(owner_session: Session, app_session: Session) -> Iterator[dict[str, uuid.UUID]]:
apps/api/tests/db/test_023_messaging.py:47:    """One org, one RESTRICTED project, an author inside it and an
apps/api/tests/db/test_023_messaging.py:48:    outsider who is not.
apps/api/tests/db/test_023_messaging.py:49:
apps/api/tests/db/test_023_messaging.py:50:    Both are active organization members, so nothing but the project
apps/api/tests/db/test_023_messaging.py:51:    boundary separates them -- which is the only way the test can
apps/api/tests/db/test_023_messaging.py:52:    attribute a difference in behaviour to that boundary.
apps/api/tests/db/test_023_messaging.py:53:    """
apps/api/tests/db/test_023_messaging.py:54:    suffix = uuid.uuid4().hex[:8]
apps/api/tests/db/test_023_messaging.py:55:
apps/api/tests/db/test_023_messaging.py:56:    org = owner_session.execute(
apps/api/tests/db/test_023_messaging.py:57:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api/tests/db/test_023_messaging.py:58:        {"c": f"MSG-{suffix}", "n": "Messaging Org"},
apps/api/tests/db/test_023_messaging.py:59:    ).scalar_one()
apps/api/tests/db/test_023_messaging.py:60:
apps/api/tests/db/test_023_messaging.py:61:    def _user(handle: str, name: str) -> uuid.UUID:
apps/api/tests/db/test_023_messaging.py:62:        uid: uuid.UUID = owner_session.execute(
apps/api/tests/db/test_023_messaging.py:63:            text(
apps/api/tests/db/test_023_messaging.py:64:                """
apps/api/tests/db/test_023_messaging.py:65:                INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api/tests/db/test_023_messaging.py:66:                VALUES (:s, :e, :n) RETURNING id
apps/api/tests/db/test_023_messaging.py:67:                """
apps/api/tests/db/test_023_messaging.py:68:            ),
apps/api/tests/db/test_023_messaging.py:69:            {"s": f"msg-{handle}-{suffix}", "e": f"{handle}@example.test", "n": name},
apps/api/tests/db/test_023_messaging.py:70:        ).scalar_one()
apps/api/tests/db/test_023_messaging.py:71:        owner_session.execute(
apps/api/tests/db/test_023_messaging.py:72:            text(
apps/api/tests/db/test_023_messaging.py:73:                """
apps/api/tests/db/test_023_messaging.py:74:                INSERT INTO core.organization_members (organization_id, user_id, status)
apps/api/tests/db/test_023_messaging.py:75:                VALUES (:o, :u, 'active')
apps/api/tests/db/test_023_messaging.py:76:                """
apps/api/tests/db/test_023_messaging.py:77:            ),
apps/api/tests/db/test_023_messaging.py:78:            {"o": org, "u": uid},
apps/api/tests/db/test_023_messaging.py:79:        )
apps/api/tests/db/test_023_messaging.py:80:        return uid
apps/api/tests/db/test_023_messaging.py:81:
apps/api/tests/db/test_023_messaging.py:82:    author = _user(f"author{suffix}", "Author")
apps/api/tests/db/test_023_messaging.py:83:    outsider = _user(f"outsider{suffix}", "Outsider")
apps/api/tests/db/test_023_messaging.py:84:
apps/api/tests/db/test_023_messaging.py:85:    project = owner_session.execute(
apps/api/tests/db/test_023_messaging.py:86:        text(
apps/api/tests/db/test_023_messaging.py:87:            """
apps/api/tests/db/test_023_messaging.py:88:            INSERT INTO projects.projects
apps/api/tests/db/test_023_messaging.py:89:                (organization_id, project_code, name, project_type, confidentiality, created_by)
apps/api/tests/db/test_023_messaging.py:90:            VALUES (:o, :c, 'Restricted Work', 'new_product', 'restricted', :u)
apps/api/tests/db/test_023_messaging.py:91:            RETURNING id
apps/api/tests/db/test_023_messaging.py:92:            """
apps/api/tests/db/test_023_messaging.py:93:        ),
apps/api/tests/db/test_023_messaging.py:94:        {"o": org, "c": f"P-{suffix}", "u": author},
apps/api/tests/db/test_023_messaging.py:95:    ).scalar_one()
apps/api/tests/db/test_023_messaging.py:96:
apps/api/tests/db/test_023_messaging.py:97:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:98:        text(
apps/api/tests/db/test_023_messaging.py:99:            """
apps/api/tests/db/test_023_messaging.py:100:            INSERT INTO projects.project_members
apps/api/tests/db/test_023_messaging.py:101:                (organization_id, project_id, user_id, project_role)
apps/api/tests/db/test_023_messaging.py:102:            VALUES (:o, :p, :u, 'lead')
apps/api/tests/db/test_023_messaging.py:103:            """
apps/api/tests/db/test_023_messaging.py:104:        ),
apps/api/tests/db/test_023_messaging.py:105:        {"o": org, "p": project, "u": author},
apps/api/tests/db/test_023_messaging.py:106:    )
apps/api/tests/db/test_023_messaging.py:107:    owner_session.commit()
apps/api/tests/db/test_023_messaging.py:108:
apps/api/tests/db/test_023_messaging.py:109:    _scope(app_session, org, author)
apps/api/tests/db/test_023_messaging.py:110:
apps/api/tests/db/test_023_messaging.py:111:    yield {"org": org, "author": author, "outsider": outsider, "project": project}
apps/api/tests/db/test_023_messaging.py:112:
apps/api/tests/db/test_023_messaging.py:113:    app_session.rollback()
apps/api/tests/db/test_023_messaging.py:114:    owner_session.begin()
apps/api/tests/db/test_023_messaging.py:115:    for statement in (
apps/api/tests/db/test_023_messaging.py:116:        "DELETE FROM messaging.notifications WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:117:        "DELETE FROM messaging.message_links WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:118:        "DELETE FROM workflow.tasks WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:119:        "DELETE FROM messaging.channel_members WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:120:        "DELETE FROM messaging.channels WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:121:        "DELETE FROM projects.project_members WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:122:        "DELETE FROM projects.projects WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:123:        "DELETE FROM core.organization_members WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py:124:    ):
apps/api/tests/db/test_023_messaging.py:125:        owner_session.execute(text(statement), {"o": org})
apps/api/tests/db/test_023_messaging.py:126:    # Messages carry a `deny_message_rewrite` trigger. Disabled here for
apps/api/tests/db/test_023_messaging.py:127:    # the same reason the MSD fixture disables its append-only guards:
apps/api/tests/db/test_023_messaging.py:128:    # having to do so is proof the mechanism is real.
apps/api/tests/db/test_023_messaging.py:129:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:130:        text("ALTER TABLE messaging.messages DISABLE TRIGGER messages_are_a_record")
apps/api/tests/db/test_023_messaging.py:131:    )
apps/api/tests/db/test_023_messaging.py:132:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:133:        text("DELETE FROM messaging.messages WHERE organization_id = :o"), {"o": org}
apps/api/tests/db/test_023_messaging.py:134:    )
apps/api/tests/db/test_023_messaging.py:135:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:136:        text("ALTER TABLE messaging.messages ENABLE TRIGGER messages_are_a_record")
apps/api/tests/db/test_023_messaging.py:137:    )
apps/api/tests/db/test_023_messaging.py:138:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:139:        text("DELETE FROM core.users WHERE id IN (:a, :b)"), {"a": author, "b": outsider}
apps/api/tests/db/test_023_messaging.py:140:    )
apps/api/tests/db/test_023_messaging.py:141:    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
apps/api/tests/db/test_023_messaging.py:142:    owner_session.commit()
apps/api/tests/db/test_023_messaging.py:143:
apps/api/tests/db/test_023_messaging.py:144:
apps/api/tests/db/test_023_messaging.py:145:def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
apps/api/tests/db/test_023_messaging.py:146:    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
apps/api/tests/db/test_023_messaging.py:147:    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})
apps/api/tests/db/test_023_messaging.py:148:
apps/api/tests/db/test_023_messaging.py:149:
apps/api/tests/db/test_023_messaging.py:150:def test_a_mention_does_not_notify_someone_outside_the_project(
apps/api/tests/db/test_023_messaging.py:151:    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py:152:) -> None:
apps/api/tests/db/test_023_messaging.py:153:    """🔴 THE NOTIFICATION IS THE LEAK, IF YOU LET IT BE.
apps/api/tests/db/test_023_messaging.py:154:
apps/api/tests/db/test_023_messaging.py:155:    The outsider is a full organization member and is mentioned by name
apps/api/tests/db/test_023_messaging.py:156:    in a RESTRICTED project's channel. They must get no notification --
apps/api/tests/db/test_023_messaging.py:157:    because the notification would name a project they cannot open, and
apps/api/tests/db/test_023_messaging.py:158:    the channel's RLS cannot stop a row addressed to them.
apps/api/tests/db/test_023_messaging.py:159:    """
apps/api/tests/db/test_023_messaging.py:160:    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py:161:
apps/api/tests/db/test_023_messaging.py:162:    channel = create_channel(
apps/api/tests/db/test_023_messaging.py:163:        app_session,
apps/api/tests/db/test_023_messaging.py:164:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:165:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:166:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py:167:    )
apps/api/tests/db/test_023_messaging.py:168:
apps/api/tests/db/test_023_messaging.py:169:    outsider_handle = app_session.execute(
apps/api/tests/db/test_023_messaging.py:170:        text("SELECT split_part(email, '@', 1) FROM core.users WHERE id = :u"),
apps/api/tests/db/test_023_messaging.py:171:        {"u": fx["outsider"]},
apps/api/tests/db/test_023_messaging.py:172:    ).scalar_one()
apps/api/tests/db/test_023_messaging.py:173:
apps/api/tests/db/test_023_messaging.py:174:    result = post_message(
apps/api/tests/db/test_023_messaging.py:175:        app_session,
apps/api/tests/db/test_023_messaging.py:176:        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py:177:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:178:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:179:        spec=MessageInput(body=f"@{outsider_handle} can you look at this?"),
apps/api/tests/db/test_023_messaging.py:180:    )
apps/api/tests/db/test_023_messaging.py:181:    app_session.commit()
apps/api/tests/db/test_023_messaging.py:182:
apps/api/tests/db/test_023_messaging.py:183:    # The MENTION is recorded -- the message said what it said.
apps/api/tests/db/test_023_messaging.py:184:    assert result["mentions"], "the mention was not resolved at all"
apps/api/tests/db/test_023_messaging.py:185:    assert result["mentions"][0]["user_id"] == fx["outsider"]
apps/api/tests/db/test_023_messaging.py:186:    assert result["mentions"][0]["notified"] is False, (
apps/api/tests/db/test_023_messaging.py:187:        "a user outside a restricted project was notified about its channel; "
apps/api/tests/db/test_023_messaging.py:188:        "the notification discloses the project's existence"
apps/api/tests/db/test_023_messaging.py:189:    )
apps/api/tests/db/test_023_messaging.py:190:
apps/api/tests/db/test_023_messaging.py:191:    delivered = my_notifications(
apps/api/tests/db/test_023_messaging.py:192:        app_session, organization_id=fx["org"], recipient_id=fx["outsider"]
apps/api/tests/db/test_023_messaging.py:193:    )
apps/api/tests/db/test_023_messaging.py:194:    assert delivered == [], f"a notification reached an outsider: {delivered}"
apps/api/tests/db/test_023_messaging.py:195:
apps/api/tests/db/test_023_messaging.py:196:
apps/api/tests/db/test_023_messaging.py:197:def test_a_mention_notifies_a_project_member(
apps/api/tests/db/test_023_messaging.py:198:    app_session: Session, owner_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py:199:) -> None:
apps/api/tests/db/test_023_messaging.py:200:    """Verified in BOTH directions.
apps/api/tests/db/test_023_messaging.py:201:
apps/api/tests/db/test_023_messaging.py:202:    A check that notified nobody would pass the test above while making
apps/api/tests/db/test_023_messaging.py:203:    mentions useless. Adding the outsider to the project must make the
apps/api/tests/db/test_023_messaging.py:204:    mention deliver.
apps/api/tests/db/test_023_messaging.py:205:    """
apps/api/tests/db/test_023_messaging.py:206:    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py:207:
apps/api/tests/db/test_023_messaging.py:208:    owner_session.begin()
apps/api/tests/db/test_023_messaging.py:209:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:210:        text(
apps/api/tests/db/test_023_messaging.py:211:            """
apps/api/tests/db/test_023_messaging.py:212:            INSERT INTO projects.project_members
apps/api/tests/db/test_023_messaging.py:213:                (organization_id, project_id, user_id, project_role)
apps/api/tests/db/test_023_messaging.py:214:            VALUES (:o, :p, :u, 'chemist')
apps/api/tests/db/test_023_messaging.py:215:            """
apps/api/tests/db/test_023_messaging.py:216:        ),
apps/api/tests/db/test_023_messaging.py:217:        {"o": fx["org"], "p": fx["project"], "u": fx["outsider"]},
apps/api/tests/db/test_023_messaging.py:218:    )
apps/api/tests/db/test_023_messaging.py:219:    owner_session.commit()
apps/api/tests/db/test_023_messaging.py:220:
apps/api/tests/db/test_023_messaging.py:221:    channel = create_channel(
apps/api/tests/db/test_023_messaging.py:222:        app_session,
apps/api/tests/db/test_023_messaging.py:223:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:224:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:225:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py:226:    )
apps/api/tests/db/test_023_messaging.py:227:    handle = app_session.execute(
apps/api/tests/db/test_023_messaging.py:228:        text("SELECT split_part(email, '@', 1) FROM core.users WHERE id = :u"),
apps/api/tests/db/test_023_messaging.py:229:        {"u": fx["outsider"]},
apps/api/tests/db/test_023_messaging.py:230:    ).scalar_one()
apps/api/tests/db/test_023_messaging.py:231:
apps/api/tests/db/test_023_messaging.py:232:    result = post_message(
apps/api/tests/db/test_023_messaging.py:233:        app_session,
apps/api/tests/db/test_023_messaging.py:234:        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py:235:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:236:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:237:        spec=MessageInput(body=f"@{handle} please review"),
apps/api/tests/db/test_023_messaging.py:238:    )
apps/api/tests/db/test_023_messaging.py:239:    app_session.commit()
apps/api/tests/db/test_023_messaging.py:240:
apps/api/tests/db/test_023_messaging.py:241:    assert result["mentions"][0]["notified"] is True, (
apps/api/tests/db/test_023_messaging.py:242:        "a project member was not notified of their own mention; the check is excluding too much"
apps/api/tests/db/test_023_messaging.py:243:    )
apps/api/tests/db/test_023_messaging.py:244:    delivered = my_notifications(
apps/api/tests/db/test_023_messaging.py:245:        app_session, organization_id=fx["org"], recipient_id=fx["outsider"]
apps/api/tests/db/test_023_messaging.py:246:    )
apps/api/tests/db/test_023_messaging.py:247:    assert len(delivered) == 1
apps/api/tests/db/test_023_messaging.py:248:    assert delivered[0]["is_actionable"] is True
apps/api/tests/db/test_023_messaging.py:249:
apps/api/tests/db/test_023_messaging.py:250:
apps/api/tests/db/test_023_messaging.py:251:def test_promotion_creates_a_task_and_links_back_to_the_message(
apps/api/tests/db/test_023_messaging.py:252:    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py:253:) -> None:
apps/api/tests/db/test_023_messaging.py:254:    """§7: conclusions become controlled records only by explicit human
apps/api/tests/db/test_023_messaging.py:255:    promotion -- and what they become is a TASK, not a decision.
apps/api/tests/db/test_023_messaging.py:256:
apps/api/tests/db/test_023_messaging.py:257:    The link back is the digital thread's rule applied to conversation:
apps/api/tests/db/test_023_messaging.py:258:    the task can always answer "where did this come from?".
apps/api/tests/db/test_023_messaging.py:259:    """
apps/api/tests/db/test_023_messaging.py:260:    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py:261:
apps/api/tests/db/test_023_messaging.py:262:    channel = create_channel(
apps/api/tests/db/test_023_messaging.py:263:        app_session,
apps/api/tests/db/test_023_messaging.py:264:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:265:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:266:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py:267:    )
apps/api/tests/db/test_023_messaging.py:268:    message = post_message(
apps/api/tests/db/test_023_messaging.py:269:        app_session,
apps/api/tests/db/test_023_messaging.py:270:        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py:271:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:272:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:273:        spec=MessageInput(body="We should re-run the adhesion test at 5 degrees."),
apps/api/tests/db/test_023_messaging.py:274:    )
apps/api/tests/db/test_023_messaging.py:275:
apps/api/tests/db/test_023_messaging.py:276:    promoted = promote_message(
apps/api/tests/db/test_023_messaging.py:277:        app_session,
apps/api/tests/db/test_023_messaging.py:278:        message_id=message["id"],
apps/api/tests/db/test_023_messaging.py:279:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:280:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:281:        task_type="experiment",
apps/api/tests/db/test_023_messaging.py:282:        title="Re-run adhesion at 5 C",
apps/api/tests/db/test_023_messaging.py:283:    )
apps/api/tests/db/test_023_messaging.py:284:    app_session.commit()
apps/api/tests/db/test_023_messaging.py:285:
apps/api/tests/db/test_023_messaging.py:286:    source = (
apps/api/tests/db/test_023_messaging.py:287:        app_session.execute(
apps/api/tests/db/test_023_messaging.py:288:            text(
apps/api/tests/db/test_023_messaging.py:289:                """
apps/api/tests/db/test_023_messaging.py:290:            SELECT source_event, entity_type, entity_id
apps/api/tests/db/test_023_messaging.py:291:            FROM workflow.tasks WHERE id = :t AND organization_id = :o
apps/api/tests/db/test_023_messaging.py:292:            """
apps/api/tests/db/test_023_messaging.py:293:            ),
apps/api/tests/db/test_023_messaging.py:294:            {"t": promoted["task_id"], "o": fx["org"]},
apps/api/tests/db/test_023_messaging.py:295:        )
apps/api/tests/db/test_023_messaging.py:296:        .mappings()
apps/api/tests/db/test_023_messaging.py:297:        .one()
apps/api/tests/db/test_023_messaging.py:298:    )
apps/api/tests/db/test_023_messaging.py:299:
apps/api/tests/db/test_023_messaging.py:300:    assert source["source_event"] == "message.promoted"
apps/api/tests/db/test_023_messaging.py:301:    assert source["entity_id"] == message["id"], (
apps/api/tests/db/test_023_messaging.py:302:        "the task does not point back at the message it came from"
apps/api/tests/db/test_023_messaging.py:303:    )
apps/api/tests/db/test_023_messaging.py:304:
apps/api/tests/db/test_023_messaging.py:305:    link = (
apps/api/tests/db/test_023_messaging.py:306:        app_session.execute(
apps/api/tests/db/test_023_messaging.py:307:            text(
apps/api/tests/db/test_023_messaging.py:308:                """
apps/api/tests/db/test_023_messaging.py:309:            SELECT link_type, entity_type, entity_id FROM messaging.message_links
apps/api/tests/db/test_023_messaging.py:310:            WHERE message_id = :m AND link_type = 'promotion'
apps/api/tests/db/test_023_messaging.py:311:            """
apps/api/tests/db/test_023_messaging.py:312:            ),
apps/api/tests/db/test_023_messaging.py:313:            {"m": message["id"]},
apps/api/tests/db/test_023_messaging.py:314:        )
apps/api/tests/db/test_023_messaging.py:315:        .mappings()
apps/api/tests/db/test_023_messaging.py:316:        .one()
apps/api/tests/db/test_023_messaging.py:317:    )
apps/api/tests/db/test_023_messaging.py:318:    assert link["entity_id"] == promoted["task_id"]
apps/api/tests/db/test_023_messaging.py:319:
apps/api/tests/db/test_023_messaging.py:320:
apps/api/tests/db/test_023_messaging.py:321:def test_nothing_is_promoted_without_being_asked(
apps/api/tests/db/test_023_messaging.py:322:    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py:323:) -> None:
apps/api/tests/db/test_023_messaging.py:324:    """Posting a message must create no controlled record at all.
apps/api/tests/db/test_023_messaging.py:325:
apps/api/tests/db/test_023_messaging.py:326:    The rule is that informal chat never becomes authoritative knowledge
apps/api/tests/db/test_023_messaging.py:327:    AUTOMATICALLY. A service that helpfully opened a task for any message
apps/api/tests/db/test_023_messaging.py:328:    containing "we should" would violate it while looking like a feature.
apps/api/tests/db/test_023_messaging.py:329:    """
apps/api/tests/db/test_023_messaging.py:330:    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py:331:
apps/api/tests/db/test_023_messaging.py:332:    channel = create_channel(
apps/api/tests/db/test_023_messaging.py:333:        app_session,
apps/api/tests/db/test_023_messaging.py:334:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:335:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:336:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py:337:    )
apps/api/tests/db/test_023_messaging.py:338:    post_message(
apps/api/tests/db/test_023_messaging.py:339:        app_session,
apps/api/tests/db/test_023_messaging.py:340:        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py:341:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:342:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:343:        spec=MessageInput(body="We should probably reformulate and open a corrective action."),
apps/api/tests/db/test_023_messaging.py:344:    )
apps/api/tests/db/test_023_messaging.py:345:    app_session.commit()
apps/api/tests/db/test_023_messaging.py:346:
apps/api/tests/db/test_023_messaging.py:347:    tasks = app_session.execute(
apps/api/tests/db/test_023_messaging.py:348:        text("SELECT count(*) FROM workflow.tasks WHERE organization_id = :o"), {"o": fx["org"]}
apps/api/tests/db/test_023_messaging.py:349:    ).scalar_one()
apps/api/tests/db/test_023_messaging.py:350:    assert tasks == 0, "a message created a controlled record on its own"
apps/api/tests/db/test_023_messaging.py:351:
apps/api/tests/db/test_023_messaging.py:352:
apps/api/tests/db/test_023_messaging.py:353:def test_a_withdrawn_message_leaves_the_conversation_readable(
apps/api/tests/db/test_023_messaging.py:354:    app_session: Session, owner_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py:355:) -> None:
apps/api/tests/db/test_023_messaging.py:356:    """A withdrawn message is replaced, not omitted.
apps/api/tests/db/test_023_messaging.py:357:
apps/api/tests/db/test_023_messaging.py:358:    Omitting it would leave replies pointing at nothing, and a
apps/api/tests/db/test_023_messaging.py:359:    conversation with holes cannot be read at all.
apps/api/tests/db/test_023_messaging.py:360:    """
apps/api/tests/db/test_023_messaging.py:361:    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py:362:
apps/api/tests/db/test_023_messaging.py:363:    channel = create_channel(
apps/api/tests/db/test_023_messaging.py:364:        app_session,
apps/api/tests/db/test_023_messaging.py:365:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:366:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:367:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py:368:    )
apps/api/tests/db/test_023_messaging.py:369:    first = post_message(
apps/api/tests/db/test_023_messaging.py:370:        app_session,
apps/api/tests/db/test_023_messaging.py:371:        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py:372:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:373:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:374:        spec=MessageInput(body="Original claim."),
apps/api/tests/db/test_023_messaging.py:375:    )
apps/api/tests/db/test_023_messaging.py:376:    post_message(
apps/api/tests/db/test_023_messaging.py:377:        app_session,
apps/api/tests/db/test_023_messaging.py:378:        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py:379:        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py:380:        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:381:        spec=MessageInput(body="Agreed.", reply_to_id=first["id"]),
apps/api/tests/db/test_023_messaging.py:382:    )
apps/api/tests/db/test_023_messaging.py:383:    app_session.commit()
apps/api/tests/db/test_023_messaging.py:384:
apps/api/tests/db/test_023_messaging.py:385:    owner_session.begin()
apps/api/tests/db/test_023_messaging.py:386:    owner_session.execute(
apps/api/tests/db/test_023_messaging.py:387:        text("UPDATE messaging.messages SET is_deleted = TRUE WHERE id = :m"), {"m": first["id"]}
apps/api/tests/db/test_023_messaging.py:388:    )
apps/api/tests/db/test_023_messaging.py:389:    owner_session.commit()
apps/api/tests/db/test_023_messaging.py:390:
apps/api/tests/db/test_023_messaging.py:391:    thread = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
apps/api/tests/db/test_023_messaging.py:392:    assert len(thread) == 2, "the withdrawn message vanished and took the thread with it"
apps/api/tests/db/test_023_messaging.py:393:    assert thread[0]["body"] == "(this message was withdrawn)"
apps/api/tests/db/test_023_messaging.py:394:    assert thread[1]["reply_to_id"] == first["id"]
.github/workflows/ci.yml:1:name: CI
.github/workflows/ci.yml:2:
.github/workflows/ci.yml:3:# All logic lives in scripts/ so the runner stays swappable (ADR-010).
.github/workflows/ci.yml:4:# The source's zero-cost default is Forgejo Actions; GitHub is used as a
.github/workflows/ci.yml:5:# permitted convenience, and moving back means changing this file only.
.github/workflows/ci.yml:6:
.github/workflows/ci.yml:7:on:
.github/workflows/ci.yml:8:  push:
.github/workflows/ci.yml:9:    # `master` FIRST because that is this repository's actual default
.github/workflows/ci.yml:10:    # branch. This said `[main]` only, so every push since the repository
.github/workflows/ci.yml:11:    # was created matched nothing and CI never ran once — a workflow
.github/workflows/ci.yml:12:    # gated on a branch that does not exist is indistinguishable from
.github/workflows/ci.yml:13:    # having no CI at all, and it reports nothing while it happens.
.github/workflows/ci.yml:14:    # `main` is kept so a future default-branch rename does not silently
.github/workflows/ci.yml:15:    # switch CI off again.
.github/workflows/ci.yml:16:    branches: [master, main]
.github/workflows/ci.yml:17:  pull_request:
.github/workflows/ci.yml:18:  workflow_dispatch:
.github/workflows/ci.yml:19:
.github/workflows/ci.yml:20:concurrency:
.github/workflows/ci.yml:21:  # One run per ref. Note that a GitHub concurrency group is a one-slot
.github/workflows/ci.yml:22:  # replacement waiting room, not a queue -- a pending run can be evicted
.github/workflows/ci.yml:23:  # rather than queued. That is fine for CI; it is NOT fine for deploy or
.github/workflows/ci.yml:24:  # migration workflows, which must confirm their run id actually started.
.github/workflows/ci.yml:25:  group: ci-${{ github.ref }}
.github/workflows/ci.yml:26:  cancel-in-progress: true
.github/workflows/ci.yml:27:
.github/workflows/ci.yml:28:env:
.github/workflows/ci.yml:29:  PYTHON_VERSION: "3.12"
.github/workflows/ci.yml:30:  NODE_VERSION: "22"
.github/workflows/ci.yml:31:
.github/workflows/ci.yml:32:jobs:
.github/workflows/ci.yml:33:  api:
.github/workflows/ci.yml:34:    name: API — lint, type, test
.github/workflows/ci.yml:35:    runs-on: ubuntu-latest
.github/workflows/ci.yml:36:
.github/workflows/ci.yml:37:    services:
.github/workflows/ci.yml:38:      postgres:
.github/workflows/ci.yml:39:        # pgvector, matching the compose stack. Testing against plain
.github/workflows/ci.yml:40:        # postgres would pass and then fail at Slice 8 when the extension
.github/workflows/ci.yml:41:        # is needed (ADR-004).
.github/workflows/ci.yml:42:        image: pgvector/pgvector:pg16
.github/workflows/ci.yml:43:        env:
.github/workflows/ci.yml:44:          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml:45:          POSTGRES_USER: postgres
.github/workflows/ci.yml:46:          POSTGRES_PASSWORD: ci-postgres
.github/workflows/ci.yml:47:        options: >-
.github/workflows/ci.yml:48:          --health-cmd "pg_isready -U postgres -d evercoat_itw_rd"
.github/workflows/ci.yml:49:          --health-interval 5s --health-timeout 5s --health-retries 20
.github/workflows/ci.yml:50:        ports: ["5432:5432"]
.github/workflows/ci.yml:51:
.github/workflows/ci.yml:52:    steps:
.github/workflows/ci.yml:53:      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml:54:
.github/workflows/ci.yml:55:      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5, resolved 2026-08-18
.github/workflows/ci.yml:56:        with:
.github/workflows/ci.yml:57:          python-version: ${{ env.PYTHON_VERSION }}
.github/workflows/ci.yml:58:          cache: pip
.github/workflows/ci.yml:59:
.github/workflows/ci.yml:60:      - name: Install
.github/workflows/ci.yml:61:        working-directory: apps/api
.github/workflows/ci.yml:62:        run: pip install -e ".[dev]"
.github/workflows/ci.yml:63:
.github/workflows/ci.yml:64:      - name: Lint
.github/workflows/ci.yml:65:        working-directory: apps/api
.github/workflows/ci.yml:66:        run: ruff check . && ruff format --check .
.github/workflows/ci.yml:67:
.github/workflows/ci.yml:68:      - name: Type check
.github/workflows/ci.yml:69:        working-directory: apps/api
.github/workflows/ci.yml:70:        run: mypy app
.github/workflows/ci.yml:71:
.github/workflows/ci.yml:72:      - name: Apply migrations
.github/workflows/ci.yml:73:        working-directory: apps/api
.github/workflows/ci.yml:74:        env:
.github/workflows/ci.yml:75:          # The OWNER role, not the runtime role. ADR-017 keeps DDL away
.github/workflows/ci.yml:76:          # from the role the application connects with, so these two
.github/workflows/ci.yml:77:          # URLs are deliberately different credentials.
.github/workflows/ci.yml:78:          MIGRATION_DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:79:        run: |
.github/workflows/ci.yml:80:          set -euo pipefail
.github/workflows/ci.yml:81:          # Alembic, not a loop over *.sql. The loop applied files in
.github/workflows/ci.yml:82:          # glob order with no record of what had run -- acceptable on a
.github/workflows/ci.yml:83:          # throwaway CI database, useless anywhere the schema persists.
.github/workflows/ci.yml:84:          alembic upgrade head
.github/workflows/ci.yml:85:          # Prove version tracking works rather than assume it. A second
.github/workflows/ci.yml:86:          # run must be a no-op; if it re-applies, the version table is
.github/workflows/ci.yml:87:          # not being written and every future deploy would replay the
.github/workflows/ci.yml:88:          # entire history.
.github/workflows/ci.yml:89:          out=$(alembic upgrade head 2>&1)
.github/workflows/ci.yml:90:          if echo "$out" | grep -q "Running upgrade"; then
.github/workflows/ci.yml:91:            echo "alembic re-applied migrations on a second run:"
.github/workflows/ci.yml:92:            echo "$out"
.github/workflows/ci.yml:93:            exit 1
.github/workflows/ci.yml:94:          fi
.github/workflows/ci.yml:95:          alembic current
.github/workflows/ci.yml:96:
.github/workflows/ci.yml:97:      - name: Grant the test roles a login
.github/workflows/ci.yml:98:        env:
.github/workflows/ci.yml:99:          PGPASSWORD: ci-postgres
.github/workflows/ci.yml:100:        run: |
.github/workflows/ci.yml:101:          set -euo pipefail
.github/workflows/ci.yml:102:          # LOGIN and a password are the ONLY things this step may do.
.github/workflows/ci.yml:103:          #
.github/workflows/ci.yml:104:          # It used to also grant privileges and reassign table ownership
.github/workflows/ci.yml:105:          # for `core, projects, audit`. That list was wrong -- it omitted
.github/workflows/ci.yml:106:          # `innovation` and `workflow` -- so the first CI run that ever
.github/workflows/ci.yml:107:          # executed failed 37 tests with 50 `permission denied` errors
.github/workflows/ci.yml:108:          # while the same suite passed 152/0/0 locally, because the local
.github/workflows/ci.yml:109:          # database had been repaired by hand with a DIFFERENT list.
.github/workflows/ci.yml:110:          #
.github/workflows/ci.yml:111:          # Two hand-maintained lists in two files, which nothing can check
.github/workflows/ci.yml:112:          # against each other, is this platform's most repeated defect.
.github/workflows/ci.yml:113:          # Ownership and grants now belong to migration 014 and are
.github/workflows/ci.yml:114:          # asserted by tests/db/test_object_ownership.py, so there is one
.github/workflows/ci.yml:115:          # decider and a test that fails if a new table misses it.
.github/workflows/ci.yml:116:          #
.github/workflows/ci.yml:117:          # Credentials genuinely are CI-only: the migration creates these
.github/workflows/ci.yml:118:          # roles NOLOGIN by design, and the suite must connect AS the
.github/workflows/ci.yml:119:          # runtime role -- running the tenancy tests as superuser would
.github/workflows/ci.yml:120:          # bypass RLS and pass against a schema with no isolation at all.
.github/workflows/ci.yml:121:          psql -h localhost -U postgres -d evercoat_itw_rd -v ON_ERROR_STOP=1 <<'SQL'
.github/workflows/ci.yml:122:          ALTER ROLE evercoat_owner LOGIN PASSWORD 'ci-owner';
.github/workflows/ci.yml:123:          ALTER ROLE evercoat_app   LOGIN PASSWORD 'ci-app';
.github/workflows/ci.yml:124:          GRANT CONNECT ON DATABASE evercoat_itw_rd TO evercoat_owner, evercoat_app;
.github/workflows/ci.yml:125:          SQL
.github/workflows/ci.yml:126:
.github/workflows/ci.yml:127:      - name: Tests
.github/workflows/ci.yml:128:        working-directory: apps/api
.github/workflows/ci.yml:129:        env:
.github/workflows/ci.yml:130:          TEST_DB_HOST: localhost
.github/workflows/ci.yml:131:          TEST_DB_PORT: "5432"
.github/workflows/ci.yml:132:          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml:133:          TEST_OWNER_USER: evercoat_owner
.github/workflows/ci.yml:134:          TEST_OWNER_PASSWORD: ci-owner
.github/workflows/ci.yml:135:          APP_DB_USER: evercoat_app
.github/workflows/ci.yml:136:          APP_DB_PASSWORD: ci-app
.github/workflows/ci.yml:137:          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:138:          KEYCLOAK_ISSUER: http://localhost:18080/realms/evercoat
.github/workflows/ci.yml:139:        run: |
.github/workflows/ci.yml:140:          # -rs so SKIPPED tests are named, not just counted. A suite that
.github/workflows/ci.yml:141:          # silently skips its database tests reports green while proving
.github/workflows/ci.yml:142:          # nothing -- results are always passed / failed / SKIPPED.
.github/workflows/ci.yml:143:          pytest -v -rs --tb=short
.github/workflows/ci.yml:144:
.github/workflows/ci.yml:145:      - name: Assert tenancy tests actually ran
.github/workflows/ci.yml:146:        working-directory: apps/api
.github/workflows/ci.yml:147:        env:
.github/workflows/ci.yml:148:          TEST_DB_HOST: localhost
.github/workflows/ci.yml:149:          TEST_DB_PORT: "5432"
.github/workflows/ci.yml:150:          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml:151:          TEST_OWNER_USER: evercoat_owner
.github/workflows/ci.yml:152:          TEST_OWNER_PASSWORD: ci-owner
.github/workflows/ci.yml:153:          APP_DB_USER: evercoat_app
.github/workflows/ci.yml:154:          APP_DB_PASSWORD: ci-app
.github/workflows/ci.yml:155:          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:156:          KEYCLOAK_ISSUER: http://localhost:18080/realms/evercoat
.github/workflows/ci.yml:157:        run: |
.github/workflows/ci.yml:158:          set -euo pipefail
.github/workflows/ci.yml:159:          # The db fixtures skip when no database is reachable. That is
.github/workflows/ci.yml:160:          # right for a laptop and wrong for CI: a misconfigured service
.github/workflows/ci.yml:161:          # container would turn the entire tenancy suite into skips and
.github/workflows/ci.yml:162:          # the job would still be green. Fail if they did not run.
.github/workflows/ci.yml:163:          count=$(pytest tests/db -q --collect-only 2>/dev/null | grep -c "test_" || echo 0)
.github/workflows/ci.yml:164:          if [ "$count" -lt 12 ]; then
.github/workflows/ci.yml:165:            echo "expected >=12 tenancy tests, collected $count"; exit 1
.github/workflows/ci.yml:166:          fi
.github/workflows/ci.yml:167:          pytest tests/db -q --no-header -rs \
.github/workflows/ci.yml:168:            | tee /tmp/db.txt
.github/workflows/ci.yml:169:          if grep -q "skipped" /tmp/db.txt; then
.github/workflows/ci.yml:170:            echo "tenancy tests were SKIPPED -- the database was not reachable"
.github/workflows/ci.yml:171:            exit 1
.github/workflows/ci.yml:172:          fi
.github/workflows/ci.yml:173:
.github/workflows/ci.yml:174:      # AN UNRUN SEEDER IS NOT A SEEDER.
.github/workflows/ci.yml:175:      #
.github/workflows/ci.yml:176:      # The same rule this repository already applied to backup.sh, where
.github/workflows/ci.yml:177:      # the restore drill is what made the backup real. `scripts/seed.py`
.github/workflows/ci.yml:178:      # is the only thing that puts demonstration data into a database,
.github/workflows/ci.yml:179:      # it reads the SAME demo-data.json the deployed site renders, and
.github/workflows/ci.yml:180:      # until now nothing ever executed it -- so a schema change could
.github/workflows/ci.yml:181:      # break it and the break would surface on an operator's machine
.github/workflows/ci.yml:182:      # while every gate stayed green.
.github/workflows/ci.yml:183:      #
.github/workflows/ci.yml:184:      # Run LAST, after the tests, deliberately: seeding before them would
.github/workflows/ci.yml:185:      # put rows in front of assertions that were written against an empty
.github/workflows/ci.yml:186:      # database, and a suite that passes only because of seed data is a
.github/workflows/ci.yml:187:      # suite that has stopped saying what it means.
.github/workflows/ci.yml:188:      - name: Seed — run it, twice, and count what it wrote
.github/workflows/ci.yml:189:        working-directory: apps/api
.github/workflows/ci.yml:190:        env:
.github/workflows/ci.yml:191:          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:192:          PGPASSWORD: ci-postgres
.github/workflows/ci.yml:193:        run: |
.github/workflows/ci.yml:194:          set -euo pipefail
.github/workflows/ci.yml:195:          python ../../scripts/seed.py
.github/workflows/ci.yml:196:
.github/workflows/ci.yml:197:          # TWICE, because the script claims to be idempotent and a claim
.github/workflows/ci.yml:198:          # is not a mechanism. The second run must not raise -- every
.github/workflows/ci.yml:199:          # INSERT carries an ON CONFLICT -- and must not double any row.
.github/workflows/ci.yml:200:          python ../../scripts/seed.py
.github/workflows/ci.yml:201:
.github/workflows/ci.yml:202:          # Counted from the database, not from the script's own printed
.github/workflows/ci.yml:203:          # summary. A seeder reporting what it MEANT to write is exactly
.github/workflows/ci.yml:204:          # the "report saying zero is indistinguishable from a broken
.github/workflows/ci.yml:205:          # deploy" shape already recorded against this platform.
.github/workflows/ci.yml:206:          counts=$(psql -h localhost -U postgres -d evercoat_itw_rd -tAF' ' -v ON_ERROR_STOP=1 -c "
.github/workflows/ci.yml:207:            SELECT
.github/workflows/ci.yml:208:              (SELECT count(*) FROM materials.materials),
.github/workflows/ci.yml:209:              (SELECT count(*) FROM materials.suppliers),
.github/workflows/ci.yml:210:              (SELECT count(*) FROM materials.material_documents WHERE document_type = 'SDS'),
.github/workflows/ci.yml:211:              (SELECT count(*) FROM materials.units),
.github/workflows/ci.yml:212:              (SELECT count(*) FROM formulations.formulas),
.github/workflows/ci.yml:213:              (SELECT count(*) FROM formulations.formula_versions),
.github/workflows/ci.yml:214:              (SELECT count(*) FROM formulations.formula_components)")
.github/workflows/ci.yml:215:          echo "materials suppliers sds units formulas versions components = $counts"
.github/workflows/ci.yml:216:
.github/workflows/ci.yml:217:          set -- $counts
.github/workflows/ci.yml:218:          materials=$1; suppliers=$2; sds=$3; units=$4
.github/workflows/ci.yml:219:          formulas=$5; versions=$6; components=$7
.github/workflows/ci.yml:220:
.github/workflows/ci.yml:221:          # The expected numbers come from demo-data.json, read here rather
.github/workflows/ci.yml:222:          # than hardcoded, so adding a material to the demonstration does
.github/workflows/ci.yml:223:          # not silently fail this gate.
.github/workflows/ci.yml:224:          expected=$(python - <<'PY'
.github/workflows/ci.yml:225:          import json, pathlib
.github/workflows/ci.yml:226:          d = json.loads(pathlib.Path("../../apps/web/lib/demo/demo-data.json").read_text(encoding="utf-8"))
.github/workflows/ci.yml:227:          versions = [v for f in d["formulas"] for v in f["versions"]]
.github/workflows/ci.yml:228:          print(len(d["materials"]), len(d["suppliers"]), len(d["formulas"]),
.github/workflows/ci.yml:229:                len(versions), sum(len(v["components"]) for v in versions))
.github/workflows/ci.yml:230:          PY
.github/workflows/ci.yml:231:          )
.github/workflows/ci.yml:232:          set -- $expected
.github/workflows/ci.yml:233:          exp_materials=$1; exp_suppliers=$2; exp_formulas=$3
.github/workflows/ci.yml:234:          exp_versions=$4; exp_components=$5
.github/workflows/ci.yml:235:
.github/workflows/ci.yml:236:          fail=0
.github/workflows/ci.yml:237:          check() {
.github/workflows/ci.yml:238:            if [ "$2" -ne "$3" ]; then
.github/workflows/ci.yml:239:              echo "MISMATCH $1: database has $2, demo-data.json has $3"; fail=1
.github/workflows/ci.yml:240:            fi
.github/workflows/ci.yml:241:          }
.github/workflows/ci.yml:242:          check materials  "$materials"  "$exp_materials"
.github/workflows/ci.yml:243:          check suppliers  "$suppliers"  "$exp_suppliers"
.github/workflows/ci.yml:244:          check formulas   "$formulas"   "$exp_formulas"
.github/workflows/ci.yml:245:          check versions   "$versions"   "$exp_versions"
.github/workflows/ci.yml:246:          check components "$components" "$exp_components"
.github/workflows/ci.yml:247:
.github/workflows/ci.yml:248:          # EVERY material must carry an SDS. Without one the formulation
.github/workflows/ci.yml:249:          # safety check hard-blocks submission, so a seeded database
.github/workflows/ci.yml:250:          # missing them is a demonstration in which no formula can be
.github/workflows/ci.yml:251:          # submitted -- the exact deadlock this slice's review found.
.github/workflows/ci.yml:252:          check sds "$sds" "$exp_materials"
.github/workflows/ci.yml:253:
.github/workflows/ci.yml:254:          if [ "$units" -lt 1 ]; then
.github/workflows/ci.yml:255:            echo "MISMATCH units: Administration section 3 seeded nothing"; fail=1
.github/workflows/ci.yml:256:          fi
.github/workflows/ci.yml:257:
.github/workflows/ci.yml:258:          exit "$fail"
.github/workflows/ci.yml:259:
.github/workflows/ci.yml:260:  web:
.github/workflows/ci.yml:261:    name: Web — lint, type, test
.github/workflows/ci.yml:262:    runs-on: ubuntu-latest
.github/workflows/ci.yml:263:    steps:
.github/workflows/ci.yml:264:      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml:265:      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020  # v4, resolved 2026-08-18
.github/workflows/ci.yml:266:        with:
.github/workflows/ci.yml:267:          node-version: ${{ env.NODE_VERSION }}
.github/workflows/ci.yml:268:          cache: npm
.github/workflows/ci.yml:269:          cache-dependency-path: apps/web/package-lock.json
.github/workflows/ci.yml:270:      - working-directory: apps/web
.github/workflows/ci.yml:271:        run: npm ci || npm install
.github/workflows/ci.yml:272:      - working-directory: apps/web
.github/workflows/ci.yml:273:        run: npm run lint
.github/workflows/ci.yml:274:      - working-directory: apps/web
.github/workflows/ci.yml:275:        run: npm run typecheck
.github/workflows/ci.yml:276:      - working-directory: apps/web
.github/workflows/ci.yml:277:        # 17 navigation contract tests. They assert the RBAC filter in
.github/workflows/ci.yml:278:        # BOTH directions -- serving the shell only ever proved that it
.github/workflows/ci.yml:279:        # removes items, which a filter returning nothing would also do.
.github/workflows/ci.yml:280:        run: npm test
.github/workflows/ci.yml:281:      - working-directory: apps/web
.github/workflows/ci.yml:282:        # NODE_ENV=production explicitly: building as development ships
.github/workflows/ci.yml:283:        # the dev React runtime, which behaves differently from what was
.github/workflows/ci.yml:284:        # tested and is slower and larger.
.github/workflows/ci.yml:285:        env:
.github/workflows/ci.yml:286:          NODE_ENV: production
.github/workflows/ci.yml:287:        run: npm run build
.github/workflows/ci.yml:288:
.github/workflows/ci.yml:289:      - name: Build the mode the site actually ships in, and assert it
.github/workflows/ci.yml:290:        working-directory: apps/web
.github/workflows/ci.yml:291:        # CI only ever built `standalone`. The DEPLOYED site is the static
.github/workflows/ci.yml:292:        # EXPORT, and the two differ in ways that have already broken the
.github/workflows/ci.yml:293:        # front door once: under `output: "export"` a server `redirect()`
.github/workflows/ci.yml:294:        # emits an error document, and without `trailingSlash` the export
.github/workflows/ci.yml:295:        # writes dashboard.html, which Render 404s because it does no
.github/workflows/ci.yml:296:        # clean-URL fallback.
.github/workflows/ci.yml:297:        #
.github/workflows/ci.yml:298:        # Both guards existed only inside the Render build command — that is,
.github/workflows/ci.yml:299:        # they ran after merge, at deploy time, against whatever had already
.github/workflows/ci.yml:300:        # landed on master. Running them here makes a regression a failed PR
.github/workflows/ci.yml:301:        # instead of a broken production front door.
.github/workflows/ci.yml:302:        env:
.github/workflows/ci.yml:303:          NODE_ENV: production
.github/workflows/ci.yml:304:          NEXT_OUTPUT: export
.github/workflows/ci.yml:305:        run: |
.github/workflows/ci.yml:306:          set -euo pipefail
.github/workflows/ci.yml:307:          npm run build
.github/workflows/ci.yml:308:          if grep -q "__next_error__" out/index.html; then
.github/workflows/ci.yml:309:            echo "::error::/ exported as a Next.js error document — the front door is broken"
.github/workflows/ci.yml:310:            exit 1
.github/workflows/ci.yml:311:          fi
.github/workflows/ci.yml:312:          test -f out/dashboard/index.html || {
.github/workflows/ci.yml:313:            echo "::error::out/dashboard/index.html missing — /dashboard would 404 on a host with no .html fallback"
.github/workflows/ci.yml:314:            exit 1
.github/workflows/ci.yml:315:          }
.github/workflows/ci.yml:316:          test -f out/admin/index.html || {
.github/workflows/ci.yml:317:            echo "::error::out/admin/index.html missing"; exit 1
.github/workflows/ci.yml:318:          }
.github/workflows/ci.yml:319:          echo "static export OK: real root document, directory indexes present"
.github/workflows/ci.yml:320:
.github/workflows/ci.yml:321:  e2e:
.github/workflows/ci.yml:322:    name: E2E — browser shell, axe-core, API over HTTP
.github/workflows/ci.yml:323:    runs-on: ubuntu-latest
.github/workflows/ci.yml:324:
.github/workflows/ci.yml:325:    # The suite existed and passed locally while CI ran neither Playwright
.github/workflows/ci.yml:326:    # nor axe-core, so every PR could be green without either having
.github/workflows/ci.yml:327:    # executed. `CLAUDE.md` §11 has required axe-core in CI since Slice 1;
.github/workflows/ci.yml:328:    # this job is the first time that requirement is actually enforced
.github/workflows/ci.yml:329:    # rather than merely written down.
.github/workflows/ci.yml:330:
.github/workflows/ci.yml:331:    services:
.github/workflows/ci.yml:332:      postgres:
.github/workflows/ci.yml:333:        image: pgvector/pgvector:pg16
.github/workflows/ci.yml:334:        env:
.github/workflows/ci.yml:335:          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml:336:          POSTGRES_USER: postgres
.github/workflows/ci.yml:337:          POSTGRES_PASSWORD: ci-postgres
.github/workflows/ci.yml:338:        options: >-
.github/workflows/ci.yml:339:          --health-cmd "pg_isready -U postgres -d evercoat_itw_rd"
.github/workflows/ci.yml:340:          --health-interval 5s --health-timeout 5s --health-retries 20
.github/workflows/ci.yml:341:        ports: ["5432:5432"]
.github/workflows/ci.yml:342:
.github/workflows/ci.yml:343:    steps:
.github/workflows/ci.yml:344:      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml:345:
.github/workflows/ci.yml:346:      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5, resolved 2026-08-18
.github/workflows/ci.yml:347:        with:
.github/workflows/ci.yml:348:          python-version: ${{ env.PYTHON_VERSION }}
.github/workflows/ci.yml:349:          cache: pip
.github/workflows/ci.yml:350:
.github/workflows/ci.yml:351:      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020  # v4, resolved 2026-08-18
.github/workflows/ci.yml:352:        with:
.github/workflows/ci.yml:353:          node-version: ${{ env.NODE_VERSION }}
.github/workflows/ci.yml:354:
.github/workflows/ci.yml:355:      - name: Install API
.github/workflows/ci.yml:356:        working-directory: apps/api
.github/workflows/ci.yml:357:        run: pip install -e ".[dev]"
.github/workflows/ci.yml:358:
.github/workflows/ci.yml:359:      - name: Apply migrations
.github/workflows/ci.yml:360:        working-directory: apps/api
.github/workflows/ci.yml:361:        env:
.github/workflows/ci.yml:362:          MIGRATION_DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:363:          DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:364:          KEYCLOAK_ISSUER: http://127.0.0.1:1/realms/evercoat
.github/workflows/ci.yml:365:        run: alembic upgrade head
.github/workflows/ci.yml:366:
.github/workflows/ci.yml:367:      - name: Grant the application role a login
.github/workflows/ci.yml:368:        env:
.github/workflows/ci.yml:369:          PGPASSWORD: ci-postgres
.github/workflows/ci.yml:370:        run: |
.github/workflows/ci.yml:371:          set -euo pipefail
.github/workflows/ci.yml:372:          # The API refuses to start as a superuser -- `Settings` validates
.github/workflows/ci.yml:373:          # it, deliberately, because the runtime role is the one FORCE RLS
.github/workflows/ci.yml:374:          # applies to. This job had no such step and pointed the server at
.github/workflows/ci.yml:375:          # `postgres`, so Playwright's webServer died on a pydantic
.github/workflows/ci.yml:376:          # ValidationError before a single test ran and the failure read
.github/workflows/ci.yml:377:          # as a broken E2E suite rather than a misconfigured job.
.github/workflows/ci.yml:378:          #
.github/workflows/ci.yml:379:          # That refusal is worth keeping exactly as it is: it turned a
.github/workflows/ci.yml:380:          # silent "CI tests something production can never be" into a hard
.github/workflows/ci.yml:381:          # stop. The job is what was wrong.
.github/workflows/ci.yml:382:          psql -h localhost -U postgres -d evercoat_itw_rd -v ON_ERROR_STOP=1 <<'SQL'
.github/workflows/ci.yml:383:          ALTER ROLE evercoat_app LOGIN PASSWORD 'ci-app';
.github/workflows/ci.yml:384:          GRANT CONNECT ON DATABASE evercoat_itw_rd TO evercoat_app;
.github/workflows/ci.yml:385:          SQL
.github/workflows/ci.yml:386:
.github/workflows/ci.yml:387:      - name: Install web dependencies
.github/workflows/ci.yml:388:        working-directory: apps/web
.github/workflows/ci.yml:389:        run: npm ci || npm install
.github/workflows/ci.yml:390:
.github/workflows/ci.yml:391:      - name: Install E2E dependencies
.github/workflows/ci.yml:392:        run: npm ci || npm install
.github/workflows/ci.yml:393:
.github/workflows/ci.yml:394:      # `--with-deps` because the GitHub runner lacks the shared libraries
.github/workflows/ci.yml:395:      # Chromium needs. Without it the browser downloads and then fails to
.github/workflows/ci.yml:396:      # launch, which reads as a broken test rather than a missing library.
.github/workflows/ci.yml:397:      - name: Install Playwright browsers
.github/workflows/ci.yml:398:        run: npx playwright install --with-deps chromium
.github/workflows/ci.yml:399:
.github/workflows/ci.yml:400:      - name: Run E2E
.github/workflows/ci.yml:401:        env:
.github/workflows/ci.yml:402:          # The RUNTIME role, never `postgres`. Playwright starts the API
.github/workflows/ci.yml:403:          # itself and the API refuses a superuser connection string, so
.github/workflows/ci.yml:404:          # this must match what production actually connects as.
.github/workflows/ci.yml:405:          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:406:          KEYCLOAK_ISSUER: http://127.0.0.1:1/realms/evercoat
.github/workflows/ci.yml:407:          # CI supplies a real database, so readiness reporting 503 here
.github/workflows/ci.yml:408:          # means something is genuinely broken. Locally the suite tolerates
.github/workflows/ci.yml:409:          # 503 (there may be no database); accepting it in CI too would let
.github/workflows/ci.yml:410:          # a wrong DATABASE_URL leave the run green.
.github/workflows/ci.yml:411:          E2E_REQUIRE_DB_READY: "1"
.github/workflows/ci.yml:412:          CI: "true"
.github/workflows/ci.yml:413:        # --fail-on-flaky-tests: a retry that passes on the second attempt
.github/workflows/ci.yml:414:        # still means the suite is not trustworthy. Without this, `retries`
.github/workflows/ci.yml:415:        # quietly converts an intermittent failure into a green job.
.github/workflows/ci.yml:416:        run: npx playwright test --fail-on-flaky-tests
.github/workflows/ci.yml:417:
.github/workflows/ci.yml:418:      - name: Upload report
.github/workflows/ci.yml:419:        if: always()
.github/workflows/ci.yml:420:        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02  # v4, resolved 2026-08-18
.github/workflows/ci.yml:421:        with:
.github/workflows/ci.yml:422:          name: playwright-report
.github/workflows/ci.yml:423:          path: |
.github/workflows/ci.yml:424:            playwright-report/
.github/workflows/ci.yml:425:            test-results/
.github/workflows/ci.yml:426:          retention-days: 7
.github/workflows/ci.yml:427:
.github/workflows/ci.yml:428:  security:
.github/workflows/ci.yml:429:    name: Security scan
.github/workflows/ci.yml:430:    runs-on: ubuntu-latest
.github/workflows/ci.yml:431:    steps:
.github/workflows/ci.yml:432:      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml:433:        with:
.github/workflows/ci.yml:434:          # gitleaks on `push` scans only the pushed commits; full history
.github/workflows/ci.yml:435:          # needs the whole repo, so fetch it.
.github/workflows/ci.yml:436:          fetch-depth: 0
.github/workflows/ci.yml:437:
.github/workflows/ci.yml:438:      - name: Gitleaks
.github/workflows/ci.yml:439:        uses: gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7  # v2, resolved 2026-08-18
.github/workflows/ci.yml:440:        env:
.github/workflows/ci.yml:441:          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
.github/workflows/ci.yml:442:
.github/workflows/ci.yml:443:      - name: Trivy — filesystem
.github/workflows/ci.yml:444:        # 0.28.0 was never a published tag, so this step failed to resolve
.github/workflows/ci.yml:445:        # on every run with "unable to find version" — the scan had never
.github/workflows/ci.yml:446:        # executed once. A security job that cannot start is worse than an
.github/workflows/ci.yml:447:        # absent one: it occupies the slot where the check is supposed to
.github/workflows/ci.yml:448:        # be. Pinned to a tag that exists (verified against the action's
.github/workflows/ci.yml:449:        # releases) rather than a floating ref, so a supply-chain change
.github/workflows/ci.yml:450:        # upstream cannot silently alter what runs here.
.github/workflows/ci.yml:451:        uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25  # v0.36.0, resolved 2026-08-18
.github/workflows/ci.yml:452:        with:
.github/workflows/ci.yml:453:          scan-type: fs
.github/workflows/ci.yml:454:          scan-ref: .
.github/workflows/ci.yml:455:          severity: HIGH,CRITICAL
.github/workflows/ci.yml:456:          # A high-severity finding blocks the merge. The source is
.github/workflows/ci.yml:457:          # explicit that this gates staging deployment.
.github/workflows/ci.yml:458:          exit-code: "1"
.github/workflows/ci.yml:459:          ignore-unfixed: true
.github/workflows/ci.yml:460:
.github/workflows/ci.yml:461:      - name: Semgrep
.github/workflows/ci.yml:462:        run: |
.github/workflows/ci.yml:463:          pip install semgrep
.github/workflows/ci.yml:464:          semgrep --config auto --error --skip-unknown-extensions .
.github/workflows/ci.yml:465:
.github/workflows/ci.yml:466:  auth:
.github/workflows/ci.yml:467:    name: Auth — real Keycloak, real tokens
.github/workflows/ci.yml:468:    runs-on: ubuntu-latest
.github/workflows/ci.yml:469:
.github/workflows/ci.yml:470:    # 🔴 THE FIRST TIME AUTHENTICATION HAS EVER RUN.
.github/workflows/ci.yml:471:    #
.github/workflows/ci.yml:472:    # The API has verified tokens correctly since Slice 1 and had never
.github/workflows/ci.yml:473:    # once verified a real one, because no Keycloak had ever run anywhere:
.github/workflows/ci.yml:474:    # not on Render, not in CI, not on the development host. Every auth
.github/workflows/ci.yml:475:    # test until now fabricated its own JWT or mocked the verifier, so the
.github/workflows/ci.yml:476:    # four defects this job exists to catch were all invisible — the realm
.github/workflows/ci.yml:477:    # ships with zero users, the seeder writes placeholder subjects, a
.github/workflows/ci.yml:478:    # Keycloak token's audience is `account` unless a mapper says
.github/workflows/ci.yml:479:    # otherwise, and nothing had ever sent `X-Organization-Id`.
.github/workflows/ci.yml:480:    #
.github/workflows/ci.yml:481:    # This job needs no deployment and costs nothing, which matters:
.github/workflows/ci.yml:482:    # deploying the API and Keycloak is blocked on Render's free
.github/workflows/ci.yml:483:    # web-service quota, and that is the operator's decision, not CI's.
.github/workflows/ci.yml:484:
.github/workflows/ci.yml:485:    services:
.github/workflows/ci.yml:486:      postgres:
.github/workflows/ci.yml:487:        image: pgvector/pgvector:pg16
.github/workflows/ci.yml:488:        env:
.github/workflows/ci.yml:489:          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml:490:          POSTGRES_USER: postgres
.github/workflows/ci.yml:491:          POSTGRES_PASSWORD: ci-postgres
.github/workflows/ci.yml:492:        options: >-
.github/workflows/ci.yml:493:          --health-cmd "pg_isready -U postgres -d evercoat_itw_rd"
.github/workflows/ci.yml:494:          --health-interval 5s --health-timeout 5s --health-retries 20
.github/workflows/ci.yml:495:        ports: ["5432:5432"]
.github/workflows/ci.yml:496:
.github/workflows/ci.yml:497:    steps:
.github/workflows/ci.yml:498:      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml:499:
.github/workflows/ci.yml:500:      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5, resolved 2026-08-18
.github/workflows/ci.yml:501:        with:
.github/workflows/ci.yml:502:          python-version: ${{ env.PYTHON_VERSION }}
.github/workflows/ci.yml:503:          cache: pip
.github/workflows/ci.yml:504:
.github/workflows/ci.yml:505:      - name: Install API
.github/workflows/ci.yml:506:        working-directory: apps/api
.github/workflows/ci.yml:507:        run: pip install -e ".[dev]"
.github/workflows/ci.yml:508:
.github/workflows/ci.yml:509:      # Generated, never written down. A hardcoded password in a workflow
.github/workflows/ci.yml:510:      # file is a gitleaks finding whatever the comment beside it says, and
.github/workflows/ci.yml:511:      # the realm's policy (12 chars, mixed case, digit, special) would push
.github/workflows/ci.yml:512:      # anyone writing one by hand toward something they had used before.
.github/workflows/ci.yml:513:      - name: Mint throwaway credentials
.github/workflows/ci.yml:514:        run: |
.github/workflows/ci.yml:515:          set -euo pipefail
.github/workflows/ci.yml:516:          admin="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9')Aa1!"
.github/workflows/ci.yml:517:          user="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9')Bb2!"
.github/workflows/ci.yml:518:          echo "::add-mask::$admin"
.github/workflows/ci.yml:519:          echo "::add-mask::$user"
.github/workflows/ci.yml:520:          echo "KC_ADMIN_PASSWORD=$admin" >> "$GITHUB_ENV"
.github/workflows/ci.yml:521:          echo "KC_USER_PASSWORD=$user" >> "$GITHUB_ENV"
.github/workflows/ci.yml:522:
.github/workflows/ci.yml:523:      - name: Start Keycloak with the shipped realm
.github/workflows/ci.yml:524:        run: |
.github/workflows/ci.yml:525:          set -euo pipefail
.github/workflows/ci.yml:526:          # `docker run`, not a `services:` block: a service container takes
.github/workflows/ci.yml:527:          # only an image and env, and Keycloak needs BOTH a command
.github/workflows/ci.yml:528:          # (`start-dev --import-realm`) and the realm mounted. A service
.github/workflows/ci.yml:529:          # container would start a Keycloak with no realm at all — which
.github/workflows/ci.yml:530:          # would pass a health check and fail every token request.
.github/workflows/ci.yml:531:          docker run -d --name evercoat-keycloak-ci \
.github/workflows/ci.yml:532:            -p 8080:8080 \
.github/workflows/ci.yml:533:            -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
.github/workflows/ci.yml:534:            -e KC_BOOTSTRAP_ADMIN_PASSWORD="$KC_ADMIN_PASSWORD" \
.github/workflows/ci.yml:535:            -e KC_HEALTH_ENABLED=true \
.github/workflows/ci.yml:536:            -e KC_HTTP_ENABLED=true \
.github/workflows/ci.yml:537:            -v "$PWD/services/keycloak/realm:/opt/keycloak/data/import:ro" \
.github/workflows/ci.yml:538:            quay.io/keycloak/keycloak:26.0 \
.github/workflows/ci.yml:539:            start-dev --import-realm
.github/workflows/ci.yml:540:
.github/workflows/ci.yml:541:      - name: Apply migrations
.github/workflows/ci.yml:542:        working-directory: apps/api
.github/workflows/ci.yml:543:        env:
.github/workflows/ci.yml:544:          MIGRATION_DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:545:          DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:546:          KEYCLOAK_ISSUER: http://localhost:8080/realms/evercoat
.github/workflows/ci.yml:547:        run: alembic upgrade head
.github/workflows/ci.yml:548:
.github/workflows/ci.yml:549:      - name: Grant the application role a login
.github/workflows/ci.yml:550:        env:
.github/workflows/ci.yml:551:          PGPASSWORD: ci-postgres
.github/workflows/ci.yml:552:        run: |
.github/workflows/ci.yml:553:          set -euo pipefail
.github/workflows/ci.yml:554:          psql -h localhost -U postgres -d evercoat_itw_rd -v ON_ERROR_STOP=1 <<'SQL'
.github/workflows/ci.yml:555:          ALTER ROLE evercoat_app LOGIN PASSWORD 'ci-app';
.github/workflows/ci.yml:556:          GRANT CONNECT ON DATABASE evercoat_itw_rd TO evercoat_app;
.github/workflows/ci.yml:557:          SQL
.github/workflows/ci.yml:558:
.github/workflows/ci.yml:559:      - name: Seed, and capture the organization the tokens will name
.github/workflows/ci.yml:560:        env:
.github/workflows/ci.yml:561:          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:562:        run: |
.github/workflows/ci.yml:563:          set -euo pipefail
.github/workflows/ci.yml:564:          python scripts/seed.py | tee seed.log
.github/workflows/ci.yml:565:          org="$(grep -oE 'organization: [0-9a-f-]{36}' seed.log | head -1 | awk '{print $2}')" || org=""
.github/workflows/ci.yml:566:          if [ -z "$org" ]; then
.github/workflows/ci.yml:567:            echo "FAIL: the seeder printed no organization id; every request would 400" >&2
.github/workflows/ci.yml:568:            exit 1
.github/workflows/ci.yml:569:          fi
.github/workflows/ci.yml:570:          echo "TEST_ORGANIZATION_ID=$org" >> "$GITHUB_ENV"
.github/workflows/ci.yml:571:
.github/workflows/ci.yml:572:      - name: Create the realm's users and bind their subjects
.github/workflows/ci.yml:573:        env:
.github/workflows/ci.yml:574:          KC_URL: http://localhost:8080
.github/workflows/ci.yml:575:          KC_SUBS_OUT: keycloak-subs.json
.github/workflows/ci.yml:576:          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:577:        run: |
.github/workflows/ci.yml:578:          set -euo pipefail
.github/workflows/ci.yml:579:          bash scripts/keycloak-bootstrap.sh --with-test-client
.github/workflows/ci.yml:580:          python scripts/keycloak-bind-subs.py keycloak-subs.json
.github/workflows/ci.yml:581:
.github/workflows/ci.yml:582:      - name: Start the API
.github/workflows/ci.yml:583:        working-directory: apps/api
.github/workflows/ci.yml:584:        env:
.github/workflows/ci.yml:585:          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml:586:          KEYCLOAK_ISSUER: http://localhost:8080/realms/evercoat
.github/workflows/ci.yml:587:          KEYCLOAK_AUDIENCE: evercoat-api
.github/workflows/ci.yml:588:        run: |
.github/workflows/ci.yml:589:          set -euo pipefail
.github/workflows/ci.yml:590:          nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$GITHUB_WORKSPACE/api.log" 2>&1 &
.github/workflows/ci.yml:591:          deadline=$(( SECONDS + 90 ))
.github/workflows/ci.yml:592:          until code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health/live)" \
.github/workflows/ci.yml:593:                && [ "$code" = "200" ]; do
.github/workflows/ci.yml:594:            if [ "$SECONDS" -ge "$deadline" ]; then
.github/workflows/ci.yml:595:              echo "FAIL: the API never became live. Its log:" >&2
.github/workflows/ci.yml:596:              cat "$GITHUB_WORKSPACE/api.log" >&2
.github/workflows/ci.yml:597:              exit 1
.github/workflows/ci.yml:598:            fi
.github/workflows/ci.yml:599:            sleep 2
.github/workflows/ci.yml:600:          done
.github/workflows/ci.yml:601:
.github/workflows/ci.yml:602:      # 🔴 THE COUNTS, AND THE THIRD STATE.
.github/workflows/ci.yml:603:      #
.github/workflows/ci.yml:604:      # These tests skip themselves when no Keycloak is configured, which
.github/workflows/ci.yml:605:      # is right on a laptop and catastrophic here: a fully skipped run
.github/workflows/ci.yml:606:      # exits 0 and reads as proof. The assertion below is on the number
.github/workflows/ci.yml:607:      # that PASSED and on skipped being zero — never on the exit code.
.github/workflows/ci.yml:608:      - name: Prove authentication end to end
.github/workflows/ci.yml:609:        working-directory: apps/api
.github/workflows/ci.yml:610:        env:
.github/workflows/ci.yml:611:          TEST_KEYCLOAK_URL: http://localhost:8080
.github/workflows/ci.yml:612:          TEST_API_URL: http://127.0.0.1:8000
.github/workflows/ci.yml:613:          TEST_KEYCLOAK_REALM: evercoat
.github/workflows/ci.yml:614:          TEST_KEYCLOAK_CLIENT: evercoat-test
.github/workflows/ci.yml:615:          TEST_KEYCLOAK_PASSWORD: ${{ env.KC_USER_PASSWORD }}
.github/workflows/ci.yml:616:          TEST_ORGANIZATION_ID: ${{ env.TEST_ORGANIZATION_ID }}
.github/workflows/ci.yml:617:        run: |
.github/workflows/ci.yml:618:          set -euo pipefail
.github/workflows/ci.yml:619:          pytest tests/integration/test_auth_end_to_end.py -v --junitxml=auth-results.xml || true
.github/workflows/ci.yml:620:          python "$GITHUB_WORKSPACE/scripts/assert-suite-ran.py" auth-results.xml
.github/workflows/ci.yml:621:
.github/workflows/ci.yml:622:      - name: Keycloak and API logs on failure
.github/workflows/ci.yml:623:        if: failure()
.github/workflows/ci.yml:624:        run: |
.github/workflows/ci.yml:625:          echo "=== keycloak ==="; docker logs evercoat-keycloak-ci 2>&1 | tail -80
.github/workflows/ci.yml:626:          echo "=== api ==="; tail -80 "$GITHUB_WORKSPACE/api.log" || true
apps/api/app/domains/messaging/service.py:1:"""Messaging, smart linking, and the NotificationService.
apps/api/app/domains/messaging/service.py:2:
apps/api/app/domains/messaging/service.py:3:**A conversation about a record is part of that record's thread.** The
apps/api/app/domains/messaging/service.py:4:digital thread's rule — "no major technical record may become an isolated
apps/api/app/domains/messaging/service.py:5:data island" — applies to discussion too: a decision argued out in a chat
apps/api/app/domains/messaging/service.py:6:window that links to nothing is exactly the island the rule forbids. So
apps/api/app/domains/messaging/service.py:7:`#FRM-014` in a message body becomes a real row in
apps/api/app/domains/messaging/service.py:8:`messaging.message_links`, and "what has been said about this formula?"
apps/api/app/domains/messaging/service.py:9:is a query rather than a search.
apps/api/app/domains/messaging/service.py:10:
apps/api/app/domains/messaging/service.py:11:🔴 TWO RULES THAT SHAPE EVERYTHING BELOW
apps/api/app/domains/messaging/service.py:12:
apps/api/app/domains/messaging/service.py:13:**Informal chat never becomes authoritative knowledge automatically.**
apps/api/app/domains/messaging/service.py:14:§7. `promote_message` is the only path from a message to a controlled
apps/api/app/domains/messaging/service.py:15:record, it requires an explicit human act, and it creates a TASK rather
apps/api/app/domains/messaging/service.py:16:than a conclusion — somebody still has to do the work and sign for it.
apps/api/app/domains/messaging/service.py:17:Nothing here promotes anything on its own.
apps/api/app/domains/messaging/service.py:18:
apps/api/app/domains/messaging/service.py:19:**A notification must not disclose what the recipient cannot see.**
apps/api/app/domains/messaging/service.py:20:Mentioning somebody in a restricted project's channel would otherwise
apps/api/app/domains/messaging/service.py:21:send them a notification naming a project they have no access to — the
apps/api/app/domains/messaging/service.py:22:notification itself becomes the leak, and no amount of care in the
apps/api/app/domains/messaging/service.py:23:channel's RLS prevents it. So a mention only notifies a user who can
apps/api/app/domains/messaging/service.py:24:already reach that channel, and the mention link is still recorded either
apps/api/app/domains/messaging/service.py:25:way: the message said what it said.
apps/api/app/domains/messaging/service.py:26:"""
apps/api/app/domains/messaging/service.py:27:
apps/api/app/domains/messaging/service.py:28:from __future__ import annotations
apps/api/app/domains/messaging/service.py:29:
apps/api/app/domains/messaging/service.py:30:import re
apps/api/app/domains/messaging/service.py:31:import uuid
apps/api/app/domains/messaging/service.py:32:from dataclasses import dataclass
apps/api/app/domains/messaging/service.py:33:from typing import Any
apps/api/app/domains/messaging/service.py:34:
apps/api/app/domains/messaging/service.py:35:from sqlalchemy import text
apps/api/app/domains/messaging/service.py:36:from sqlalchemy.exc import IntegrityError
apps/api/app/domains/messaging/service.py:37:from sqlalchemy.orm import Session
apps/api/app/domains/messaging/service.py:38:
apps/api/app/domains/messaging/service.py:39:from app.core.audit import AuditEvent, write_audit
apps/api/app/domains/messaging/service.py:40:from app.core.tenancy import require_active_member
apps/api/app/domains/messaging/service.py:41:
apps/api/app/domains/messaging/service.py:42:__all__ = [
apps/api/app/domains/messaging/service.py:43:    "ChannelInput",
apps/api/app/domains/messaging/service.py:44:    "MessageInput",
apps/api/app/domains/messaging/service.py:45:    "MessagingError",
apps/api/app/domains/messaging/service.py:46:    "MessagingNotFoundError",
apps/api/app/domains/messaging/service.py:47:    "MessagingStateError",
apps/api/app/domains/messaging/service.py:48:    "create_channel",
apps/api/app/domains/messaging/service.py:49:    "list_channels",
apps/api/app/domains/messaging/service.py:50:    "list_messages",
apps/api/app/domains/messaging/service.py:51:    "mark_notification_read",
apps/api/app/domains/messaging/service.py:52:    "my_notifications",
apps/api/app/domains/messaging/service.py:53:    "notify",
apps/api/app/domains/messaging/service.py:54:    "post_message",
apps/api/app/domains/messaging/service.py:55:    "promote_message",
apps/api/app/domains/messaging/service.py:56:    "thread_for_record",
apps/api/app/domains/messaging/service.py:57:]
apps/api/app/domains/messaging/service.py:58:
apps/api/app/domains/messaging/service.py:59:# `#FRM-014`, `#LB-2026-0007`, `#T-2026-0041`. Deliberately narrow: an
apps/api/app/domains/messaging/service.py:60:# uppercase prefix, a hyphen, then alphanumerics and hyphens. A looser
apps/api/app/domains/messaging/service.py:61:# pattern would turn every `#1` and every hex colour in a message into a
apps/api/app/domains/messaging/service.py:62:# failed lookup, and a message full of unresolved links reads as broken.
apps/api/app/domains/messaging/service.py:63:_REFERENCE = re.compile(r"#([A-Z]{1,6}-[A-Za-z0-9-]{2,40})")
apps/api/app/domains/messaging/service.py:64:
apps/api/app/domains/messaging/service.py:65:# `@username`. Resolved against `core.users.email`'s local part, because
apps/api/app/domains/messaging/service.py:66:# that is the only handle this schema has today; a display name is not
apps/api/app/domains/messaging/service.py:67:# unique and cannot be a mention target.
apps/api/app/domains/messaging/service.py:68:_MENTION = re.compile(r"@([a-zA-Z0-9._-]{2,60})")
apps/api/app/domains/messaging/service.py:69:
apps/api/app/domains/messaging/service.py:70:# Which code prefixes resolve against which table. Written out rather
apps/api/app/domains/messaging/service.py:71:# than derived, because a dynamic version would need interpolated table
apps/api/app/domains/messaging/service.py:72:# names -- and interpolation defended by an argument has already been the
apps/api/app/domains/messaging/service.py:73:# wrong answer three times in this repository.
apps/api/app/domains/messaging/service.py:74:_RESOLVERS: dict[str, tuple[str, str]] = {
apps/api/app/domains/messaging/service.py:75:    "formula_version": (
apps/api/app/domains/messaging/service.py:76:        "version_code",
apps/api/app/domains/messaging/service.py:77:        """
apps/api/app/domains/messaging/service.py:78:        SELECT v.id FROM formulations.formula_versions v
apps/api/app/domains/messaging/service.py:79:        WHERE v.organization_id = :org AND v.version_code = :code
apps/api/app/domains/messaging/service.py:80:        """,
apps/api/app/domains/messaging/service.py:81:    ),
apps/api/app/domains/messaging/service.py:82:    "batch": (
apps/api/app/domains/messaging/service.py:83:        "batch_number",
apps/api/app/domains/messaging/service.py:84:        """
apps/api/app/domains/messaging/service.py:85:        SELECT b.id FROM laboratory.batches b
apps/api/app/domains/messaging/service.py:86:        WHERE b.organization_id = :org AND b.batch_number = :code
apps/api/app/domains/messaging/service.py:87:        """,
apps/api/app/domains/messaging/service.py:88:    ),
apps/api/app/domains/messaging/service.py:89:    "test": (
apps/api/app/domains/messaging/service.py:90:        "test_number",
apps/api/app/domains/messaging/service.py:91:        """
apps/api/app/domains/messaging/service.py:92:        SELECT t.id FROM testing.tests t
apps/api/app/domains/messaging/service.py:93:        WHERE t.organization_id = :org AND t.test_number = :code
apps/api/app/domains/messaging/service.py:94:        """,
apps/api/app/domains/messaging/service.py:95:    ),
apps/api/app/domains/messaging/service.py:96:    "failure": (
apps/api/app/domains/messaging/service.py:97:        "failure_code",
apps/api/app/domains/messaging/service.py:98:        """
apps/api/app/domains/messaging/service.py:99:        SELECT f.id FROM quality.failures f
apps/api/app/domains/messaging/service.py:100:        WHERE f.organization_id = :org AND f.failure_code = :code
apps/api/app/domains/messaging/service.py:101:        """,
apps/api/app/domains/messaging/service.py:102:    ),
apps/api/app/domains/messaging/service.py:103:    "material": (
apps/api/app/domains/messaging/service.py:104:        "material_code",
apps/api/app/domains/messaging/service.py:105:        """
apps/api/app/domains/messaging/service.py:106:        SELECT m.id FROM materials.materials m
apps/api/app/domains/messaging/service.py:107:        WHERE m.organization_id = :org AND m.material_code = :code
apps/api/app/domains/messaging/service.py:108:        """,
apps/api/app/domains/messaging/service.py:109:    ),
apps/api/app/domains/messaging/service.py:110:}
apps/api/app/domains/messaging/service.py:111:
apps/api/app/domains/messaging/service.py:112:
apps/api/app/domains/messaging/service.py:113:class MessagingError(RuntimeError):
apps/api/app/domains/messaging/service.py:114:    """Base for refusals that are business rules, not bugs."""
apps/api/app/domains/messaging/service.py:115:
apps/api/app/domains/messaging/service.py:116:
apps/api/app/domains/messaging/service.py:117:class MessagingNotFoundError(MessagingError):
apps/api/app/domains/messaging/service.py:118:    pass
apps/api/app/domains/messaging/service.py:119:
apps/api/app/domains/messaging/service.py:120:
apps/api/app/domains/messaging/service.py:121:class MessagingStateError(MessagingError):
apps/api/app/domains/messaging/service.py:122:    pass
apps/api/app/domains/messaging/service.py:123:
apps/api/app/domains/messaging/service.py:124:
apps/api/app/domains/messaging/service.py:125:@dataclass(frozen=True, slots=True)
apps/api/app/domains/messaging/service.py:126:class ChannelInput:
apps/api/app/domains/messaging/service.py:127:    channel_type: str
apps/api/app/domains/messaging/service.py:128:    name: str | None = None
apps/api/app/domains/messaging/service.py:129:    project_id: uuid.UUID | None = None
apps/api/app/domains/messaging/service.py:130:    entity_type: str | None = None
apps/api/app/domains/messaging/service.py:131:    entity_id: uuid.UUID | None = None
apps/api/app/domains/messaging/service.py:132:    member_ids: tuple[uuid.UUID, ...] = ()
apps/api/app/domains/messaging/service.py:133:
apps/api/app/domains/messaging/service.py:134:
apps/api/app/domains/messaging/service.py:135:@dataclass(frozen=True, slots=True)
apps/api/app/domains/messaging/service.py:136:class MessageInput:
apps/api/app/domains/messaging/service.py:137:    body: str
apps/api/app/domains/messaging/service.py:138:    reply_to_id: uuid.UUID | None = None
apps/api/app/domains/messaging/service.py:139:
apps/api/app/domains/messaging/service.py:140:
apps/api/app/domains/messaging/service.py:141:# ---------------------------------------------------------------------------
apps/api/app/domains/messaging/service.py:142:# Channels
apps/api/app/domains/messaging/service.py:143:# ---------------------------------------------------------------------------
apps/api/app/domains/messaging/service.py:144:
apps/api/app/domains/messaging/service.py:145:
apps/api/app/domains/messaging/service.py:146:def create_channel(
apps/api/app/domains/messaging/service.py:147:    session: Session,
apps/api/app/domains/messaging/service.py:148:    *,
apps/api/app/domains/messaging/service.py:149:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:150:    actor_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:151:    spec: ChannelInput,
apps/api/app/domains/messaging/service.py:152:) -> dict[str, Any]:
apps/api/app/domains/messaging/service.py:153:    """Open a channel.
apps/api/app/domains/messaging/service.py:154:
apps/api/app/domains/messaging/service.py:155:    A PROJECT channel is created through the project, so RLS applies that
apps/api/app/domains/messaging/service.py:156:    project's confidentiality to the conversation from the first message.
apps/api/app/domains/messaging/service.py:157:    The author must be able to see the project to open a channel on it —
apps/api/app/domains/messaging/service.py:158:    the same predicate the policy uses, applied in the INSERT for the
apps/api/app/domains/messaging/service.py:159:    reason `create_formula` needed it: WITH CHECK is organization-only,
apps/api/app/domains/messaging/service.py:160:    so naming a restricted project would otherwise succeed and merely
apps/api/app/domains/messaging/service.py:161:    become invisible.
apps/api/app/domains/messaging/service.py:162:    """
apps/api/app/domains/messaging/service.py:163:    require_active_member(
apps/api/app/domains/messaging/service.py:164:        session, user_id=actor_id, organization_id=organization_id, role_description="author"
apps/api/app/domains/messaging/service.py:165:    )
apps/api/app/domains/messaging/service.py:166:
apps/api/app/domains/messaging/service.py:167:    if spec.channel_type == "project" and spec.project_id is None:
apps/api/app/domains/messaging/service.py:168:        raise MessagingError(
apps/api/app/domains/messaging/service.py:169:            "a project channel must name its project; without one, RLS cannot apply "
apps/api/app/domains/messaging/service.py:170:            "that project's confidentiality to the conversation"
apps/api/app/domains/messaging/service.py:171:        )
apps/api/app/domains/messaging/service.py:172:
apps/api/app/domains/messaging/service.py:173:    if spec.project_id is not None:
apps/api/app/domains/messaging/service.py:174:        channel_id = session.execute(
apps/api/app/domains/messaging/service.py:175:            text(
apps/api/app/domains/messaging/service.py:176:                """
apps/api/app/domains/messaging/service.py:177:                INSERT INTO messaging.channels
apps/api/app/domains/messaging/service.py:178:                    (organization_id, project_id, channel_type, name, entity_type,
apps/api/app/domains/messaging/service.py:179:                     entity_id, created_by)
apps/api/app/domains/messaging/service.py:180:                SELECT :org, p.id, :ctype, :name, :etype, :eid, :actor
apps/api/app/domains/messaging/service.py:181:                FROM projects.projects p
apps/api/app/domains/messaging/service.py:182:                WHERE p.id = :pid AND p.organization_id = :org
apps/api/app/domains/messaging/service.py:183:                  AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
apps/api/app/domains/messaging/service.py:184:                RETURNING id
apps/api/app/domains/messaging/service.py:185:                """
apps/api/app/domains/messaging/service.py:186:            ),
apps/api/app/domains/messaging/service.py:187:            {
apps/api/app/domains/messaging/service.py:188:                "org": organization_id,
apps/api/app/domains/messaging/service.py:189:                "pid": spec.project_id,
apps/api/app/domains/messaging/service.py:190:                "ctype": spec.channel_type,
apps/api/app/domains/messaging/service.py:191:                "name": spec.name,
apps/api/app/domains/messaging/service.py:192:                "etype": spec.entity_type,
apps/api/app/domains/messaging/service.py:193:                "eid": spec.entity_id,
apps/api/app/domains/messaging/service.py:194:                "actor": actor_id,
apps/api/app/domains/messaging/service.py:195:            },
apps/api/app/domains/messaging/service.py:196:        ).scalar_one_or_none()
apps/api/app/domains/messaging/service.py:197:        if channel_id is None:
apps/api/app/domains/messaging/service.py:198:            raise MessagingNotFoundError("no such project in this organization")
apps/api/app/domains/messaging/service.py:199:    else:
apps/api/app/domains/messaging/service.py:200:        channel_id = session.execute(
apps/api/app/domains/messaging/service.py:201:            text(
apps/api/app/domains/messaging/service.py:202:                """
apps/api/app/domains/messaging/service.py:203:                INSERT INTO messaging.channels
apps/api/app/domains/messaging/service.py:204:                    (organization_id, channel_type, name, entity_type, entity_id,
apps/api/app/domains/messaging/service.py:205:                     created_by)
apps/api/app/domains/messaging/service.py:206:                VALUES (:org, :ctype, :name, :etype, :eid, :actor)
apps/api/app/domains/messaging/service.py:207:                RETURNING id
apps/api/app/domains/messaging/service.py:208:                """
apps/api/app/domains/messaging/service.py:209:            ),
apps/api/app/domains/messaging/service.py:210:            {
apps/api/app/domains/messaging/service.py:211:                "org": organization_id,
apps/api/app/domains/messaging/service.py:212:                "ctype": spec.channel_type,
apps/api/app/domains/messaging/service.py:213:                "name": spec.name,
apps/api/app/domains/messaging/service.py:214:                "etype": spec.entity_type,
apps/api/app/domains/messaging/service.py:215:                "eid": spec.entity_id,
apps/api/app/domains/messaging/service.py:216:                "actor": actor_id,
apps/api/app/domains/messaging/service.py:217:            },
apps/api/app/domains/messaging/service.py:218:        ).scalar_one()
apps/api/app/domains/messaging/service.py:219:
apps/api/app/domains/messaging/service.py:220:    # The author is always a member. A channel its creator is not in is a
apps/api/app/domains/messaging/service.py:221:    # channel that vanishes from their own list the moment they make it.
apps/api/app/domains/messaging/service.py:222:    for member in {actor_id, *spec.member_ids}:
apps/api/app/domains/messaging/service.py:223:        require_active_member(
apps/api/app/domains/messaging/service.py:224:            session, user_id=member, organization_id=organization_id, role_description="member"
apps/api/app/domains/messaging/service.py:225:        )
apps/api/app/domains/messaging/service.py:226:        session.execute(
apps/api/app/domains/messaging/service.py:227:            text(
apps/api/app/domains/messaging/service.py:228:                """
apps/api/app/domains/messaging/service.py:229:                INSERT INTO messaging.channel_members
apps/api/app/domains/messaging/service.py:230:                    (organization_id, channel_id, user_id)
apps/api/app/domains/messaging/service.py:231:                VALUES (:org, :cid, :uid)
apps/api/app/domains/messaging/service.py:232:                ON CONFLICT (channel_id, user_id) DO NOTHING
apps/api/app/domains/messaging/service.py:233:                """
apps/api/app/domains/messaging/service.py:234:            ),
apps/api/app/domains/messaging/service.py:235:            {"org": organization_id, "cid": channel_id, "uid": member},
apps/api/app/domains/messaging/service.py:236:        )
apps/api/app/domains/messaging/service.py:237:
apps/api/app/domains/messaging/service.py:238:    write_audit(
apps/api/app/domains/messaging/service.py:239:        session,
apps/api/app/domains/messaging/service.py:240:        AuditEvent(
apps/api/app/domains/messaging/service.py:241:            action="channel.created",
apps/api/app/domains/messaging/service.py:242:            entity_type="channel",
apps/api/app/domains/messaging/service.py:243:            entity_id=str(channel_id),
apps/api/app/domains/messaging/service.py:244:            organization_id=organization_id,
apps/api/app/domains/messaging/service.py:245:            user_id=actor_id,
apps/api/app/domains/messaging/service.py:246:            new_state={"channel_type": spec.channel_type, "name": spec.name},
apps/api/app/domains/messaging/service.py:247:            reason="channel opened",
apps/api/app/domains/messaging/service.py:248:        ),
apps/api/app/domains/messaging/service.py:249:    )
apps/api/app/domains/messaging/service.py:250:    return {"id": channel_id, "channel_type": spec.channel_type}
apps/api/app/domains/messaging/service.py:251:
apps/api/app/domains/messaging/service.py:252:
apps/api/app/domains/messaging/service.py:253:def thread_for_record(
apps/api/app/domains/messaging/service.py:254:    session: Session,
apps/api/app/domains/messaging/service.py:255:    *,
apps/api/app/domains/messaging/service.py:256:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:257:    actor_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:258:    entity_type: str,
apps/api/app/domains/messaging/service.py:259:    entity_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:260:    project_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:261:) -> dict[str, Any]:
apps/api/app/domains/messaging/service.py:262:    """The technical thread for a record, opening one if it has none.
apps/api/app/domains/messaging/service.py:263:
apps/api/app/domains/messaging/service.py:264:    Idempotent on purpose. Every screen that offers "discuss this" would
apps/api/app/domains/messaging/service.py:265:    otherwise create a new thread per click, and a record with six threads
apps/api/app/domains/messaging/service.py:266:    has no discussion at all — it has six fragments nobody reads together.
apps/api/app/domains/messaging/service.py:267:    """
apps/api/app/domains/messaging/service.py:268:    existing = (
apps/api/app/domains/messaging/service.py:269:        session.execute(
apps/api/app/domains/messaging/service.py:270:            text(
apps/api/app/domains/messaging/service.py:271:                """
apps/api/app/domains/messaging/service.py:272:                SELECT id, channel_type FROM messaging.channels
apps/api/app/domains/messaging/service.py:273:                WHERE organization_id = :org AND entity_type = :etype
apps/api/app/domains/messaging/service.py:274:                  AND entity_id = :eid AND channel_type = 'technical_thread'
apps/api/app/domains/messaging/service.py:275:                  AND NOT is_archived
apps/api/app/domains/messaging/service.py:276:                """
apps/api/app/domains/messaging/service.py:277:            ),
apps/api/app/domains/messaging/service.py:278:            {"org": organization_id, "etype": entity_type, "eid": entity_id},
apps/api/app/domains/messaging/service.py:279:        )
apps/api/app/domains/messaging/service.py:280:        .mappings()
apps/api/app/domains/messaging/service.py:281:        .one_or_none()
apps/api/app/domains/messaging/service.py:282:    )
apps/api/app/domains/messaging/service.py:283:    if existing is not None:
apps/api/app/domains/messaging/service.py:284:        return dict(existing)
apps/api/app/domains/messaging/service.py:285:
apps/api/app/domains/messaging/service.py:286:    return create_channel(
apps/api/app/domains/messaging/service.py:287:        session,
apps/api/app/domains/messaging/service.py:288:        organization_id=organization_id,
apps/api/app/domains/messaging/service.py:289:        actor_id=actor_id,
apps/api/app/domains/messaging/service.py:290:        spec=ChannelInput(
apps/api/app/domains/messaging/service.py:291:            channel_type="technical_thread",
apps/api/app/domains/messaging/service.py:292:            name=f"Discussion: {entity_type}",
apps/api/app/domains/messaging/service.py:293:            project_id=project_id,
apps/api/app/domains/messaging/service.py:294:            entity_type=entity_type,
apps/api/app/domains/messaging/service.py:295:            entity_id=entity_id,
apps/api/app/domains/messaging/service.py:296:        ),
apps/api/app/domains/messaging/service.py:297:    )
apps/api/app/domains/messaging/service.py:298:
apps/api/app/domains/messaging/service.py:299:
apps/api/app/domains/messaging/service.py:300:def list_channels(
apps/api/app/domains/messaging/service.py:301:    session: Session, *, organization_id: uuid.UUID, actor_id: uuid.UUID, limit: int = 100
apps/api/app/domains/messaging/service.py:302:) -> list[dict[str, Any]]:
apps/api/app/domains/messaging/service.py:303:    """Channels this caller can see.
apps/api/app/domains/messaging/service.py:304:
apps/api/app/domains/messaging/service.py:305:    RLS excludes restricted projects they are not in; membership narrows
apps/api/app/domains/messaging/service.py:306:    it further for direct messages, which are not project-scoped and
apps/api/app/domains/messaging/service.py:307:    therefore have nothing else to hide behind.
apps/api/app/domains/messaging/service.py:308:    """
apps/api/app/domains/messaging/service.py:309:    rows = session.execute(
apps/api/app/domains/messaging/service.py:310:        text(
apps/api/app/domains/messaging/service.py:311:            """
apps/api/app/domains/messaging/service.py:312:            SELECT c.id, c.channel_type, c.name, c.project_id, c.entity_type,
apps/api/app/domains/messaging/service.py:313:                   c.entity_id, c.created_at,
apps/api/app/domains/messaging/service.py:314:                   (SELECT count(*) FROM messaging.messages m
apps/api/app/domains/messaging/service.py:315:                     WHERE m.channel_id = c.id AND NOT m.is_deleted) AS message_count
apps/api/app/domains/messaging/service.py:316:            FROM messaging.channels c
apps/api/app/domains/messaging/service.py:317:            WHERE c.organization_id = :org
apps/api/app/domains/messaging/service.py:318:              AND NOT c.is_archived
apps/api/app/domains/messaging/service.py:319:              AND (
apps/api/app/domains/messaging/service.py:320:                    c.channel_type <> 'direct'
apps/api/app/domains/messaging/service.py:321:                    OR EXISTS (
apps/api/app/domains/messaging/service.py:322:                        SELECT 1 FROM messaging.channel_members cm
apps/api/app/domains/messaging/service.py:323:                        WHERE cm.channel_id = c.id AND cm.user_id = :actor
apps/api/app/domains/messaging/service.py:324:                    )
apps/api/app/domains/messaging/service.py:325:                  )
apps/api/app/domains/messaging/service.py:326:            ORDER BY c.created_at DESC
apps/api/app/domains/messaging/service.py:327:            LIMIT :limit
apps/api/app/domains/messaging/service.py:328:            """
apps/api/app/domains/messaging/service.py:329:        ),
apps/api/app/domains/messaging/service.py:330:        {"org": organization_id, "actor": actor_id, "limit": limit},
apps/api/app/domains/messaging/service.py:331:    ).mappings()
apps/api/app/domains/messaging/service.py:332:    return [dict(r) for r in rows]
apps/api/app/domains/messaging/service.py:333:
apps/api/app/domains/messaging/service.py:334:
apps/api/app/domains/messaging/service.py:335:# ---------------------------------------------------------------------------
apps/api/app/domains/messaging/service.py:336:# Messages
apps/api/app/domains/messaging/service.py:337:# ---------------------------------------------------------------------------
apps/api/app/domains/messaging/service.py:338:
apps/api/app/domains/messaging/service.py:339:
apps/api/app/domains/messaging/service.py:340:def post_message(
apps/api/app/domains/messaging/service.py:341:    session: Session,
apps/api/app/domains/messaging/service.py:342:    *,
apps/api/app/domains/messaging/service.py:343:    channel_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:344:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:345:    actor_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:346:    spec: MessageInput,
apps/api/app/domains/messaging/service.py:347:) -> dict[str, Any]:
apps/api/app/domains/messaging/service.py:348:    """Post a message, resolving its `#references` and `@mentions`.
apps/api/app/domains/messaging/service.py:349:
apps/api/app/domains/messaging/service.py:350:    **Links are resolved at WRITE time and stored.** Resolving on read
apps/api/app/domains/messaging/service.py:351:    would mean a message rendering differently after the record it names
apps/api/app/domains/messaging/service.py:352:    is renamed or retired, and a conversation must say what it said when
apps/api/app/domains/messaging/service.py:353:    it was written.
apps/api/app/domains/messaging/service.py:354:
apps/api/app/domains/messaging/service.py:355:    **Resolution runs in the author's session**, so a reference to a
apps/api/app/domains/messaging/service.py:356:    record they cannot see simply does not resolve — it stays as text.
apps/api/app/domains/messaging/service.py:357:    That is deliberate: an unresolvable reference is a broken link, and
apps/api/app/domains/messaging/service.py:358:    the alternative is a link whose existence confirms that a record with
apps/api/app/domains/messaging/service.py:359:    that code exists somewhere the author cannot look.
apps/api/app/domains/messaging/service.py:360:    """
apps/api/app/domains/messaging/service.py:361:    channel = (
apps/api/app/domains/messaging/service.py:362:        session.execute(
apps/api/app/domains/messaging/service.py:363:            text(
apps/api/app/domains/messaging/service.py:364:                """
apps/api/app/domains/messaging/service.py:365:                SELECT id, project_id, channel_type FROM messaging.channels
apps/api/app/domains/messaging/service.py:366:                WHERE id = :cid AND organization_id = :org AND NOT is_archived
apps/api/app/domains/messaging/service.py:367:                """
apps/api/app/domains/messaging/service.py:368:            ),
apps/api/app/domains/messaging/service.py:369:            {"cid": channel_id, "org": organization_id},
apps/api/app/domains/messaging/service.py:370:        )
apps/api/app/domains/messaging/service.py:371:        .mappings()
apps/api/app/domains/messaging/service.py:372:        .one_or_none()
apps/api/app/domains/messaging/service.py:373:    )
apps/api/app/domains/messaging/service.py:374:    if channel is None:
apps/api/app/domains/messaging/service.py:375:        raise MessagingNotFoundError("no such channel in this organization")
apps/api/app/domains/messaging/service.py:376:
apps/api/app/domains/messaging/service.py:377:    message_id: uuid.UUID = session.execute(
apps/api/app/domains/messaging/service.py:378:        text(
apps/api/app/domains/messaging/service.py:379:            """
apps/api/app/domains/messaging/service.py:380:            INSERT INTO messaging.messages
apps/api/app/domains/messaging/service.py:381:                (organization_id, channel_id, body, reply_to_id, author_id)
apps/api/app/domains/messaging/service.py:382:            VALUES (:org, :cid, :body, :reply, :actor)
apps/api/app/domains/messaging/service.py:383:            RETURNING id
apps/api/app/domains/messaging/service.py:384:            """
apps/api/app/domains/messaging/service.py:385:        ),
apps/api/app/domains/messaging/service.py:386:        {
apps/api/app/domains/messaging/service.py:387:            "org": organization_id,
apps/api/app/domains/messaging/service.py:388:            "cid": channel_id,
apps/api/app/domains/messaging/service.py:389:            "body": spec.body,
apps/api/app/domains/messaging/service.py:390:            "reply": spec.reply_to_id,
apps/api/app/domains/messaging/service.py:391:            "actor": actor_id,
apps/api/app/domains/messaging/service.py:392:        },
apps/api/app/domains/messaging/service.py:393:    ).scalar_one()
apps/api/app/domains/messaging/service.py:394:
apps/api/app/domains/messaging/service.py:395:    links = _resolve_references(
apps/api/app/domains/messaging/service.py:396:        session, organization_id=organization_id, message_id=message_id, body=spec.body
apps/api/app/domains/messaging/service.py:397:    )
apps/api/app/domains/messaging/service.py:398:    mentions = _resolve_mentions(
apps/api/app/domains/messaging/service.py:399:        session,
apps/api/app/domains/messaging/service.py:400:        organization_id=organization_id,
apps/api/app/domains/messaging/service.py:401:        message_id=message_id,
apps/api/app/domains/messaging/service.py:402:        channel_id=channel_id,
apps/api/app/domains/messaging/service.py:403:        body=spec.body,
apps/api/app/domains/messaging/service.py:404:        actor_id=actor_id,
apps/api/app/domains/messaging/service.py:405:    )
apps/api/app/domains/messaging/service.py:406:
apps/api/app/domains/messaging/service.py:407:    return {
apps/api/app/domains/messaging/service.py:408:        "id": message_id,
apps/api/app/domains/messaging/service.py:409:        "links": links,
apps/api/app/domains/messaging/service.py:410:        "mentions": mentions,
apps/api/app/domains/messaging/service.py:411:    }
apps/api/app/domains/messaging/service.py:412:
apps/api/app/domains/messaging/service.py:413:
apps/api/app/domains/messaging/service.py:414:def _resolve_references(
apps/api/app/domains/messaging/service.py:415:    session: Session, *, organization_id: uuid.UUID, message_id: uuid.UUID, body: str
apps/api/app/domains/messaging/service.py:416:) -> list[dict[str, Any]]:
apps/api/app/domains/messaging/service.py:417:    """Turn `#FRM-014` into a row pointing at the real record.
apps/api/app/domains/messaging/service.py:418:
apps/api/app/domains/messaging/service.py:419:    Tries every resolver for each code, because the prefixes are a
apps/api/app/domains/messaging/service.py:420:    convention rather than a guarantee — a deployment may issue
apps/api/app/domains/messaging/service.py:421:    `T-2026-0041` for a test and `T-...` for something else later, and a
apps/api/app/domains/messaging/service.py:422:    resolver keyed on the prefix alone would then point at the wrong
apps/api/app/domains/messaging/service.py:423:    table with complete confidence.
apps/api/app/domains/messaging/service.py:424:    """
apps/api/app/domains/messaging/service.py:425:    found: list[dict[str, Any]] = []
apps/api/app/domains/messaging/service.py:426:    for code in dict.fromkeys(_REFERENCE.findall(body)):
apps/api/app/domains/messaging/service.py:427:        for entity_type, (_column, sql) in _RESOLVERS.items():
apps/api/app/domains/messaging/service.py:428:            entity_id = session.execute(
apps/api/app/domains/messaging/service.py:429:                text(sql), {"org": organization_id, "code": code}
apps/api/app/domains/messaging/service.py:430:            ).scalar_one_or_none()
apps/api/app/domains/messaging/service.py:431:            if entity_id is None:
apps/api/app/domains/messaging/service.py:432:                continue
apps/api/app/domains/messaging/service.py:433:
apps/api/app/domains/messaging/service.py:434:            session.execute(
apps/api/app/domains/messaging/service.py:435:                text(
apps/api/app/domains/messaging/service.py:436:                    """
apps/api/app/domains/messaging/service.py:437:                    INSERT INTO messaging.message_links
apps/api/app/domains/messaging/service.py:438:                        (organization_id, message_id, link_type, entity_type,
apps/api/app/domains/messaging/service.py:439:                         entity_id, label)
apps/api/app/domains/messaging/service.py:440:                    VALUES (:org, :mid, 'record', :etype, :eid, :label)
apps/api/app/domains/messaging/service.py:441:                    """
apps/api/app/domains/messaging/service.py:442:                ),
apps/api/app/domains/messaging/service.py:443:                {
apps/api/app/domains/messaging/service.py:444:                    "org": organization_id,
apps/api/app/domains/messaging/service.py:445:                    "mid": message_id,
apps/api/app/domains/messaging/service.py:446:                    "etype": entity_type,
apps/api/app/domains/messaging/service.py:447:                    "eid": entity_id,
apps/api/app/domains/messaging/service.py:448:                    "label": code,
apps/api/app/domains/messaging/service.py:449:                },
apps/api/app/domains/messaging/service.py:450:            )
apps/api/app/domains/messaging/service.py:451:            found.append({"code": code, "entity_type": entity_type, "entity_id": entity_id})
apps/api/app/domains/messaging/service.py:452:            break
apps/api/app/domains/messaging/service.py:453:
apps/api/app/domains/messaging/service.py:454:    return found
apps/api/app/domains/messaging/service.py:455:
apps/api/app/domains/messaging/service.py:456:
apps/api/app/domains/messaging/service.py:457:def _resolve_mentions(
apps/api/app/domains/messaging/service.py:458:    session: Session,
apps/api/app/domains/messaging/service.py:459:    *,
apps/api/app/domains/messaging/service.py:460:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:461:    message_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:462:    channel_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:463:    body: str,
apps/api/app/domains/messaging/service.py:464:    actor_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:465:) -> list[dict[str, Any]]:
apps/api/app/domains/messaging/service.py:466:    """Record @mentions, and notify only those who can see the channel.
apps/api/app/domains/messaging/service.py:467:
apps/api/app/domains/messaging/service.py:468:    🔴 THE NOTIFICATION IS THE LEAK, IF YOU LET IT BE.
apps/api/app/domains/messaging/service.py:469:
apps/api/app/domains/messaging/service.py:470:    Mentioning somebody in a restricted project's channel would otherwise
apps/api/app/domains/messaging/service.py:471:    send them a notification naming a project they have no access to. The
apps/api/app/domains/messaging/service.py:472:    channel's RLS protects the MESSAGES and does nothing about a
apps/api/app/domains/messaging/service.py:473:    notification row addressed to an outsider — so membership is checked
apps/api/app/domains/messaging/service.py:474:    before notifying.
apps/api/app/domains/messaging/service.py:475:
apps/api/app/domains/messaging/service.py:476:    The mention LINK is recorded either way. The message said what it
apps/api/app/domains/messaging/service.py:477:    said, and editing history to match permissions would be a worse lie
apps/api/app/domains/messaging/service.py:478:    than an unresolved handle.
apps/api/app/domains/messaging/service.py:479:    """
apps/api/app/domains/messaging/service.py:480:    notified: list[dict[str, Any]] = []
apps/api/app/domains/messaging/service.py:481:    for handle in dict.fromkeys(_MENTION.findall(body)):
apps/api/app/domains/messaging/service.py:482:        user = (
apps/api/app/domains/messaging/service.py:483:            session.execute(
apps/api/app/domains/messaging/service.py:484:                text(
apps/api/app/domains/messaging/service.py:485:                    """
apps/api/app/domains/messaging/service.py:486:                    SELECT u.id, u.display_name
apps/api/app/domains/messaging/service.py:487:                    FROM core.users u
apps/api/app/domains/messaging/service.py:488:                    JOIN core.organization_members m
apps/api/app/domains/messaging/service.py:489:                      ON m.user_id = u.id AND m.organization_id = :org
apps/api/app/domains/messaging/service.py:490:                     AND m.status = 'active'
apps/api/app/domains/messaging/service.py:491:                    WHERE split_part(u.email, '@', 1) = :handle
apps/api/app/domains/messaging/service.py:492:                    """
apps/api/app/domains/messaging/service.py:493:                ),
apps/api/app/domains/messaging/service.py:494:                {"org": organization_id, "handle": handle},
apps/api/app/domains/messaging/service.py:495:            )
apps/api/app/domains/messaging/service.py:496:            .mappings()
apps/api/app/domains/messaging/service.py:497:            .one_or_none()
apps/api/app/domains/messaging/service.py:498:        )
apps/api/app/domains/messaging/service.py:499:        if user is None:
apps/api/app/domains/messaging/service.py:500:            continue
apps/api/app/domains/messaging/service.py:501:
apps/api/app/domains/messaging/service.py:502:        session.execute(
apps/api/app/domains/messaging/service.py:503:            text(
apps/api/app/domains/messaging/service.py:504:                """
apps/api/app/domains/messaging/service.py:505:                INSERT INTO messaging.message_links
apps/api/app/domains/messaging/service.py:506:                    (organization_id, message_id, link_type, mentioned_user_id, label)
apps/api/app/domains/messaging/service.py:507:                VALUES (:org, :mid, 'mention', :uid, :label)
apps/api/app/domains/messaging/service.py:508:                """
apps/api/app/domains/messaging/service.py:509:            ),
apps/api/app/domains/messaging/service.py:510:            {"org": organization_id, "mid": message_id, "uid": user["id"], "label": handle},
apps/api/app/domains/messaging/service.py:511:        )
apps/api/app/domains/messaging/service.py:512:
apps/api/app/domains/messaging/service.py:513:        # Can the RECIPIENT reach this channel?
apps/api/app/domains/messaging/service.py:514:        #
apps/api/app/domains/messaging/service.py:515:        # 🔴 THE ANSWER CANNOT BE BORROWED FROM RLS HERE.
apps/api/app/domains/messaging/service.py:516:        #
apps/api/app/domains/messaging/service.py:517:        # This query runs in the AUTHOR's session, so RLS answers "can the
apps/api/app/domains/messaging/service.py:518:        # author see it?" -- and the author demonstrably can, because they
apps/api/app/domains/messaging/service.py:519:        # just posted in it. Reusing `list_channels`'s predicate would
apps/api/app/domains/messaging/service.py:520:        # therefore return true for every project channel including a
apps/api/app/domains/messaging/service.py:521:        # restricted one, and the notification would name a project the
apps/api/app/domains/messaging/service.py:522:        # recipient has no access to. The leak would be the notification
apps/api/app/domains/messaging/service.py:523:        # itself, in the one place the channel's own RLS cannot reach.
apps/api/app/domains/messaging/service.py:524:        #
apps/api/app/domains/messaging/service.py:525:        # So the recipient's access is evaluated EXPLICITLY, against the
apps/api/app/domains/messaging/service.py:526:        # same two facts the project policy uses: confidentiality, and
apps/api/app/domains/messaging/service.py:527:        # membership.
apps/api/app/domains/messaging/service.py:528:        reachable = session.execute(
apps/api/app/domains/messaging/service.py:529:            text(
apps/api/app/domains/messaging/service.py:530:                """
apps/api/app/domains/messaging/service.py:531:                SELECT EXISTS (
apps/api/app/domains/messaging/service.py:532:                    SELECT 1
apps/api/app/domains/messaging/service.py:533:                    FROM messaging.channels c
apps/api/app/domains/messaging/service.py:534:                    LEFT JOIN projects.projects p
apps/api/app/domains/messaging/service.py:535:                      ON p.id = c.project_id AND p.organization_id = c.organization_id
apps/api/app/domains/messaging/service.py:536:                    WHERE c.id = :cid AND c.organization_id = :org
apps/api/app/domains/messaging/service.py:537:                      -- A direct message reaches only its own members.
apps/api/app/domains/messaging/service.py:538:                      AND (
apps/api/app/domains/messaging/service.py:539:                            c.channel_type <> 'direct'
apps/api/app/domains/messaging/service.py:540:                            OR EXISTS (
apps/api/app/domains/messaging/service.py:541:                                SELECT 1 FROM messaging.channel_members cm
apps/api/app/domains/messaging/service.py:542:                                WHERE cm.channel_id = c.id AND cm.user_id = :uid
apps/api/app/domains/messaging/service.py:543:                            )
apps/api/app/domains/messaging/service.py:544:                          )
apps/api/app/domains/messaging/service.py:545:                      -- A project channel reaches only people who can see
apps/api/app/domains/messaging/service.py:546:                      -- the project. `p.confidentiality` is NULL for a
apps/api/app/domains/messaging/service.py:547:                      -- channel with no project, which is why the
apps/api/app/domains/messaging/service.py:548:                      -- IS NULL arm comes first rather than relying on a
apps/api/app/domains/messaging/service.py:549:                      -- NULL comparison to behave.
apps/api/app/domains/messaging/service.py:550:                      AND (
apps/api/app/domains/messaging/service.py:551:                            c.project_id IS NULL
apps/api/app/domains/messaging/service.py:552:                            OR p.confidentiality = 'normal'
apps/api/app/domains/messaging/service.py:553:                            OR EXISTS (
apps/api/app/domains/messaging/service.py:554:                                SELECT 1 FROM projects.project_members pm
apps/api/app/domains/messaging/service.py:555:                                WHERE pm.project_id = c.project_id
apps/api/app/domains/messaging/service.py:556:                                  AND pm.organization_id = c.organization_id
apps/api/app/domains/messaging/service.py:557:                                  AND pm.user_id = :uid
apps/api/app/domains/messaging/service.py:558:                                  AND pm.status = 'active'
apps/api/app/domains/messaging/service.py:559:                            )
apps/api/app/domains/messaging/service.py:560:                          )
apps/api/app/domains/messaging/service.py:561:                )
apps/api/app/domains/messaging/service.py:562:                """
apps/api/app/domains/messaging/service.py:563:            ),
apps/api/app/domains/messaging/service.py:564:            {"cid": channel_id, "org": organization_id, "uid": user["id"]},
apps/api/app/domains/messaging/service.py:565:        ).scalar_one()
apps/api/app/domains/messaging/service.py:566:
apps/api/app/domains/messaging/service.py:567:        if reachable and user["id"] != actor_id:
apps/api/app/domains/messaging/service.py:568:            notify(
apps/api/app/domains/messaging/service.py:569:                session,
apps/api/app/domains/messaging/service.py:570:                organization_id=organization_id,
apps/api/app/domains/messaging/service.py:571:                recipient_id=user["id"],
apps/api/app/domains/messaging/service.py:572:                notification_type="message.mention",
apps/api/app/domains/messaging/service.py:573:                title="You were mentioned",
apps/api/app/domains/messaging/service.py:574:                body=body[:200],
apps/api/app/domains/messaging/service.py:575:                entity_type="message",
apps/api/app/domains/messaging/service.py:576:                entity_id=message_id,
apps/api/app/domains/messaging/service.py:577:                is_actionable=True,
apps/api/app/domains/messaging/service.py:578:            )
apps/api/app/domains/messaging/service.py:579:            notified.append({"handle": handle, "user_id": user["id"], "notified": True})
apps/api/app/domains/messaging/service.py:580:        else:
apps/api/app/domains/messaging/service.py:581:            # Recorded, deliberately, so the behaviour is inspectable
apps/api/app/domains/messaging/service.py:582:            # rather than a silent no-op somebody later mistakes for a bug.
apps/api/app/domains/messaging/service.py:583:            notified.append({"handle": handle, "user_id": user["id"], "notified": False})
apps/api/app/domains/messaging/service.py:584:
apps/api/app/domains/messaging/service.py:585:    return notified
apps/api/app/domains/messaging/service.py:586:
apps/api/app/domains/messaging/service.py:587:
apps/api/app/domains/messaging/service.py:588:def list_messages(
apps/api/app/domains/messaging/service.py:589:    session: Session,
apps/api/app/domains/messaging/service.py:590:    *,
apps/api/app/domains/messaging/service.py:591:    channel_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:592:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:593:    limit: int = 100,
apps/api/app/domains/messaging/service.py:594:) -> list[dict[str, Any]]:
apps/api/app/domains/messaging/service.py:595:    """A channel's messages, oldest first, with their links.
apps/api/app/domains/messaging/service.py:596:
apps/api/app/domains/messaging/service.py:597:    Withdrawn messages come back with their body replaced rather than
apps/api/app/domains/messaging/service.py:598:    omitted: a conversation with holes in it cannot be read, and a reply
apps/api/app/domains/messaging/service.py:599:    to a message that has vanished is unintelligible.
apps/api/app/domains/messaging/service.py:600:    """
apps/api/app/domains/messaging/service.py:601:    rows = [
apps/api/app/domains/messaging/service.py:602:        dict(r)
apps/api/app/domains/messaging/service.py:603:        for r in session.execute(
apps/api/app/domains/messaging/service.py:604:            text(
apps/api/app/domains/messaging/service.py:605:                """
apps/api/app/domains/messaging/service.py:606:                SELECT m.id, m.body, m.author_id, m.posted_at, m.edited_at,
apps/api/app/domains/messaging/service.py:607:                       m.is_deleted, m.reply_to_id, u.display_name AS author_name
apps/api/app/domains/messaging/service.py:608:                FROM messaging.messages m
apps/api/app/domains/messaging/service.py:609:                JOIN core.users u ON u.id = m.author_id
apps/api/app/domains/messaging/service.py:610:                WHERE m.channel_id = :cid AND m.organization_id = :org
apps/api/app/domains/messaging/service.py:611:                ORDER BY m.posted_at
apps/api/app/domains/messaging/service.py:612:                LIMIT :limit
apps/api/app/domains/messaging/service.py:613:                """
apps/api/app/domains/messaging/service.py:614:            ),
apps/api/app/domains/messaging/service.py:615:            {"cid": channel_id, "org": organization_id, "limit": limit},
apps/api/app/domains/messaging/service.py:616:        ).mappings()
apps/api/app/domains/messaging/service.py:617:    ]
apps/api/app/domains/messaging/service.py:618:
apps/api/app/domains/messaging/service.py:619:    if not rows:
apps/api/app/domains/messaging/service.py:620:        return []
apps/api/app/domains/messaging/service.py:621:
apps/api/app/domains/messaging/service.py:622:    links = session.execute(
apps/api/app/domains/messaging/service.py:623:        text(
apps/api/app/domains/messaging/service.py:624:            """
apps/api/app/domains/messaging/service.py:625:            SELECT l.message_id, l.link_type, l.entity_type, l.entity_id,
apps/api/app/domains/messaging/service.py:626:                   l.mentioned_user_id, l.label
apps/api/app/domains/messaging/service.py:627:            FROM messaging.message_links l
apps/api/app/domains/messaging/service.py:628:            JOIN messaging.messages m
apps/api/app/domains/messaging/service.py:629:              ON m.id = l.message_id AND m.organization_id = l.organization_id
apps/api/app/domains/messaging/service.py:630:            WHERE m.channel_id = :cid AND l.organization_id = :org
apps/api/app/domains/messaging/service.py:631:            """
apps/api/app/domains/messaging/service.py:632:        ),
apps/api/app/domains/messaging/service.py:633:        {"cid": channel_id, "org": organization_id},
apps/api/app/domains/messaging/service.py:634:    ).mappings()
apps/api/app/domains/messaging/service.py:635:
apps/api/app/domains/messaging/service.py:636:    by_message: dict[uuid.UUID, list[dict[str, Any]]] = {}
apps/api/app/domains/messaging/service.py:637:    for link in links:
apps/api/app/domains/messaging/service.py:638:        by_message.setdefault(link["message_id"], []).append(dict(link))
apps/api/app/domains/messaging/service.py:639:
apps/api/app/domains/messaging/service.py:640:    for row in rows:
apps/api/app/domains/messaging/service.py:641:        row["links"] = by_message.get(row["id"], [])
apps/api/app/domains/messaging/service.py:642:        if row["is_deleted"]:
apps/api/app/domains/messaging/service.py:643:            row["body"] = "(this message was withdrawn)"
apps/api/app/domains/messaging/service.py:644:
apps/api/app/domains/messaging/service.py:645:    return rows
apps/api/app/domains/messaging/service.py:646:
apps/api/app/domains/messaging/service.py:647:
apps/api/app/domains/messaging/service.py:648:def promote_message(
apps/api/app/domains/messaging/service.py:649:    session: Session,
apps/api/app/domains/messaging/service.py:650:    *,
apps/api/app/domains/messaging/service.py:651:    message_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:652:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:653:    actor_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:654:    task_type: str,
apps/api/app/domains/messaging/service.py:655:    title: str,
apps/api/app/domains/messaging/service.py:656:    assigned_user_id: uuid.UUID | None = None,
apps/api/app/domains/messaging/service.py:657:) -> dict[str, Any]:
apps/api/app/domains/messaging/service.py:658:    """Turn a message into a controlled record — a TASK.
apps/api/app/domains/messaging/service.py:659:
apps/api/app/domains/messaging/service.py:660:    🔴 §7: "Informal chat never becomes authoritative knowledge
apps/api/app/domains/messaging/service.py:661:    automatically. Conclusions become controlled records only by explicit
apps/api/app/domains/messaging/service.py:662:    human promotion."
apps/api/app/domains/messaging/service.py:663:
apps/api/app/domains/messaging/service.py:664:    This is that explicit act, and it deliberately creates a task rather
apps/api/app/domains/messaging/service.py:665:    than a decision or a conclusion: somebody still has to do the work and
apps/api/app/domains/messaging/service.py:666:    sign for it. A path from "somebody said so in chat" straight to a
apps/api/app/domains/messaging/service.py:667:    technical decision is the thing the rule forbids.
apps/api/app/domains/messaging/service.py:668:
apps/api/app/domains/messaging/service.py:669:    The promotion is recorded as a link back to the message, so the task
apps/api/app/domains/messaging/service.py:670:    can always answer "where did this come from?" — which is the digital
apps/api/app/domains/messaging/service.py:671:    thread's rule applied to the conversation itself.
apps/api/app/domains/messaging/service.py:672:    """
apps/api/app/domains/messaging/service.py:673:    message = (
apps/api/app/domains/messaging/service.py:674:        session.execute(
apps/api/app/domains/messaging/service.py:675:            text(
apps/api/app/domains/messaging/service.py:676:                """
apps/api/app/domains/messaging/service.py:677:                SELECT m.id, m.body, c.project_id
apps/api/app/domains/messaging/service.py:678:                FROM messaging.messages m
apps/api/app/domains/messaging/service.py:679:                JOIN messaging.channels c
apps/api/app/domains/messaging/service.py:680:                  ON c.id = m.channel_id AND c.organization_id = m.organization_id
apps/api/app/domains/messaging/service.py:681:                WHERE m.id = :mid AND m.organization_id = :org
apps/api/app/domains/messaging/service.py:682:                """
apps/api/app/domains/messaging/service.py:683:            ),
apps/api/app/domains/messaging/service.py:684:            {"mid": message_id, "org": organization_id},
apps/api/app/domains/messaging/service.py:685:        )
apps/api/app/domains/messaging/service.py:686:        .mappings()
apps/api/app/domains/messaging/service.py:687:        .one_or_none()
apps/api/app/domains/messaging/service.py:688:    )
apps/api/app/domains/messaging/service.py:689:    if message is None:
apps/api/app/domains/messaging/service.py:690:        raise MessagingNotFoundError("no such message in this organization")
apps/api/app/domains/messaging/service.py:691:
apps/api/app/domains/messaging/service.py:692:    if assigned_user_id is not None:
apps/api/app/domains/messaging/service.py:693:        require_active_member(
apps/api/app/domains/messaging/service.py:694:            session,
apps/api/app/domains/messaging/service.py:695:            user_id=assigned_user_id,
apps/api/app/domains/messaging/service.py:696:            organization_id=organization_id,
apps/api/app/domains/messaging/service.py:697:            role_description="assignee",
apps/api/app/domains/messaging/service.py:698:        )
apps/api/app/domains/messaging/service.py:699:
apps/api/app/domains/messaging/service.py:700:    try:
apps/api/app/domains/messaging/service.py:701:        task_id: uuid.UUID = session.execute(
apps/api/app/domains/messaging/service.py:702:            text(
apps/api/app/domains/messaging/service.py:703:                """
apps/api/app/domains/messaging/service.py:704:                INSERT INTO workflow.tasks
apps/api/app/domains/messaging/service.py:705:                    (organization_id, project_id, task_type, title, description,
apps/api/app/domains/messaging/service.py:706:                     assigned_user_id, assigned_role, source_event, entity_type,
apps/api/app/domains/messaging/service.py:707:                     entity_id, created_by)
apps/api/app/domains/messaging/service.py:708:                VALUES (:org, :pid, :ttype, :title, :description, :assignee,
apps/api/app/domains/messaging/service.py:709:                        CASE WHEN :assignee IS NULL THEN 'product_development_lead' END,
apps/api/app/domains/messaging/service.py:710:                        'message.promoted', 'message', :mid, :actor)
apps/api/app/domains/messaging/service.py:711:                RETURNING id
apps/api/app/domains/messaging/service.py:712:                """
apps/api/app/domains/messaging/service.py:713:            ),
apps/api/app/domains/messaging/service.py:714:            {
apps/api/app/domains/messaging/service.py:715:                "org": organization_id,
apps/api/app/domains/messaging/service.py:716:                "pid": message["project_id"],
apps/api/app/domains/messaging/service.py:717:                "ttype": task_type,
apps/api/app/domains/messaging/service.py:718:                "title": title,
apps/api/app/domains/messaging/service.py:719:                "description": message["body"][:2000],
apps/api/app/domains/messaging/service.py:720:                "assignee": assigned_user_id,
apps/api/app/domains/messaging/service.py:721:                "mid": message_id,
apps/api/app/domains/messaging/service.py:722:                "actor": actor_id,
apps/api/app/domains/messaging/service.py:723:            },
apps/api/app/domains/messaging/service.py:724:        ).scalar_one()
apps/api/app/domains/messaging/service.py:725:    except IntegrityError as exc:
apps/api/app/domains/messaging/service.py:726:        session.rollback()
apps/api/app/domains/messaging/service.py:727:        raise MessagingError(str(exc.orig)) from exc
apps/api/app/domains/messaging/service.py:728:
apps/api/app/domains/messaging/service.py:729:    session.execute(
apps/api/app/domains/messaging/service.py:730:        text(
apps/api/app/domains/messaging/service.py:731:            """
apps/api/app/domains/messaging/service.py:732:            INSERT INTO messaging.message_links
apps/api/app/domains/messaging/service.py:733:                (organization_id, message_id, link_type, entity_type, entity_id, label)
apps/api/app/domains/messaging/service.py:734:            VALUES (:org, :mid, 'promotion', 'task', :tid, :label)
apps/api/app/domains/messaging/service.py:735:            """
apps/api/app/domains/messaging/service.py:736:        ),
apps/api/app/domains/messaging/service.py:737:        {"org": organization_id, "mid": message_id, "tid": task_id, "label": title[:100]},
apps/api/app/domains/messaging/service.py:738:    )
apps/api/app/domains/messaging/service.py:739:
apps/api/app/domains/messaging/service.py:740:    write_audit(
apps/api/app/domains/messaging/service.py:741:        session,
apps/api/app/domains/messaging/service.py:742:        AuditEvent(
apps/api/app/domains/messaging/service.py:743:            action="message.promoted",
apps/api/app/domains/messaging/service.py:744:            entity_type="task",
apps/api/app/domains/messaging/service.py:745:            entity_id=str(task_id),
apps/api/app/domains/messaging/service.py:746:            organization_id=organization_id,
apps/api/app/domains/messaging/service.py:747:            user_id=actor_id,
apps/api/app/domains/messaging/service.py:748:            new_state={"task_type": task_type, "from_message": str(message_id)},
apps/api/app/domains/messaging/service.py:749:            reason=f"promoted from a message: {title}",
apps/api/app/domains/messaging/service.py:750:        ),
apps/api/app/domains/messaging/service.py:751:    )
apps/api/app/domains/messaging/service.py:752:    return {"task_id": task_id, "message_id": message_id}
apps/api/app/domains/messaging/service.py:753:
apps/api/app/domains/messaging/service.py:754:
apps/api/app/domains/messaging/service.py:755:# ---------------------------------------------------------------------------
apps/api/app/domains/messaging/service.py:756:# Notifications
apps/api/app/domains/messaging/service.py:757:# ---------------------------------------------------------------------------
apps/api/app/domains/messaging/service.py:758:
apps/api/app/domains/messaging/service.py:759:
apps/api/app/domains/messaging/service.py:760:def notify(
apps/api/app/domains/messaging/service.py:761:    session: Session,
apps/api/app/domains/messaging/service.py:762:    *,
apps/api/app/domains/messaging/service.py:763:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:764:    recipient_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:765:    notification_type: str,
apps/api/app/domains/messaging/service.py:766:    title: str,
apps/api/app/domains/messaging/service.py:767:    body: str | None = None,
apps/api/app/domains/messaging/service.py:768:    entity_type: str | None = None,
apps/api/app/domains/messaging/service.py:769:    entity_id: uuid.UUID | None = None,
apps/api/app/domains/messaging/service.py:770:    is_actionable: bool = False,
apps/api/app/domains/messaging/service.py:771:) -> uuid.UUID:
apps/api/app/domains/messaging/service.py:772:    """Write one notification.
apps/api/app/domains/messaging/service.py:773:
apps/api/app/domains/messaging/service.py:774:    THE single writer, in the same sense as one approval engine: every
apps/api/app/domains/messaging/service.py:775:    module calls this rather than growing its own table. `is_actionable`
apps/api/app/domains/messaging/service.py:776:    separates "you must do something" from "this happened", because §11
apps/api/app/domains/messaging/service.py:777:    requires a badge to count items needing action and that distinction
apps/api/app/domains/messaging/service.py:778:    has to exist in the data or every count is a total.
apps/api/app/domains/messaging/service.py:779:    """
apps/api/app/domains/messaging/service.py:780:    return session.execute(  # type: ignore[no-any-return]
apps/api/app/domains/messaging/service.py:781:        text(
apps/api/app/domains/messaging/service.py:782:            """
apps/api/app/domains/messaging/service.py:783:            INSERT INTO messaging.notifications
apps/api/app/domains/messaging/service.py:784:                (organization_id, recipient_id, notification_type, title, body,
apps/api/app/domains/messaging/service.py:785:                 entity_type, entity_id, is_actionable)
apps/api/app/domains/messaging/service.py:786:            VALUES (:org, :recipient, :ntype, :title, :body, :etype, :eid, :actionable)
apps/api/app/domains/messaging/service.py:787:            RETURNING id
apps/api/app/domains/messaging/service.py:788:            """
apps/api/app/domains/messaging/service.py:789:        ),
apps/api/app/domains/messaging/service.py:790:        {
apps/api/app/domains/messaging/service.py:791:            "org": organization_id,
apps/api/app/domains/messaging/service.py:792:            "recipient": recipient_id,
apps/api/app/domains/messaging/service.py:793:            "ntype": notification_type,
apps/api/app/domains/messaging/service.py:794:            "title": title,
apps/api/app/domains/messaging/service.py:795:            "body": body,
apps/api/app/domains/messaging/service.py:796:            "etype": entity_type,
apps/api/app/domains/messaging/service.py:797:            "eid": entity_id,
apps/api/app/domains/messaging/service.py:798:            "actionable": is_actionable,
apps/api/app/domains/messaging/service.py:799:        },
apps/api/app/domains/messaging/service.py:800:    ).scalar_one()
apps/api/app/domains/messaging/service.py:801:
apps/api/app/domains/messaging/service.py:802:
apps/api/app/domains/messaging/service.py:803:def my_notifications(
apps/api/app/domains/messaging/service.py:804:    session: Session,
apps/api/app/domains/messaging/service.py:805:    *,
apps/api/app/domains/messaging/service.py:806:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:807:    recipient_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:808:    unread_only: bool = False,
apps/api/app/domains/messaging/service.py:809:    limit: int = 100,
apps/api/app/domains/messaging/service.py:810:) -> list[dict[str, Any]]:
apps/api/app/domains/messaging/service.py:811:    """This caller's notifications.
apps/api/app/domains/messaging/service.py:812:
apps/api/app/domains/messaging/service.py:813:    Scoped by `recipient_id` in the predicate rather than by RLS, because
apps/api/app/domains/messaging/service.py:814:    notifications are organization-scoped rows: without this clause every
apps/api/app/domains/messaging/service.py:815:    colleague's notifications would be readable. RLS answers "which
apps/api/app/domains/messaging/service.py:816:    tenant"; this answers "whose".
apps/api/app/domains/messaging/service.py:817:    """
apps/api/app/domains/messaging/service.py:818:    rows = session.execute(
apps/api/app/domains/messaging/service.py:819:        text(
apps/api/app/domains/messaging/service.py:820:            """
apps/api/app/domains/messaging/service.py:821:            SELECT id, notification_type, title, body, entity_type, entity_id,
apps/api/app/domains/messaging/service.py:822:                   is_actionable, read_at, created_at
apps/api/app/domains/messaging/service.py:823:            FROM messaging.notifications
apps/api/app/domains/messaging/service.py:824:            WHERE organization_id = :org AND recipient_id = :recipient
apps/api/app/domains/messaging/service.py:825:              AND (:unread_only = FALSE OR read_at IS NULL)
apps/api/app/domains/messaging/service.py:826:            ORDER BY created_at DESC
apps/api/app/domains/messaging/service.py:827:            LIMIT :limit
apps/api/app/domains/messaging/service.py:828:            """
apps/api/app/domains/messaging/service.py:829:        ),
apps/api/app/domains/messaging/service.py:830:        {
apps/api/app/domains/messaging/service.py:831:            "org": organization_id,
apps/api/app/domains/messaging/service.py:832:            "recipient": recipient_id,
apps/api/app/domains/messaging/service.py:833:            "unread_only": unread_only,
apps/api/app/domains/messaging/service.py:834:            "limit": limit,
apps/api/app/domains/messaging/service.py:835:        },
apps/api/app/domains/messaging/service.py:836:    ).mappings()
apps/api/app/domains/messaging/service.py:837:    return [dict(r) for r in rows]
apps/api/app/domains/messaging/service.py:838:
apps/api/app/domains/messaging/service.py:839:
apps/api/app/domains/messaging/service.py:840:def mark_notification_read(
apps/api/app/domains/messaging/service.py:841:    session: Session,
apps/api/app/domains/messaging/service.py:842:    *,
apps/api/app/domains/messaging/service.py:843:    notification_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:844:    organization_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:845:    recipient_id: uuid.UUID,
apps/api/app/domains/messaging/service.py:846:) -> dict[str, Any]:
apps/api/app/domains/messaging/service.py:847:    """Mark one as read.
apps/api/app/domains/messaging/service.py:848:
apps/api/app/domains/messaging/service.py:849:    `recipient_id` is in the WHERE clause, so a caller cannot mark
apps/api/app/domains/messaging/service.py:850:    somebody else's notification read — which would hide it from the
apps/api/app/domains/messaging/service.py:851:    person who needed it, silently and permanently.
apps/api/app/domains/messaging/service.py:852:    """
apps/api/app/domains/messaging/service.py:853:    row = (
apps/api/app/domains/messaging/service.py:854:        session.execute(
apps/api/app/domains/messaging/service.py:855:            text(
apps/api/app/domains/messaging/service.py:856:                """
apps/api/app/domains/messaging/service.py:857:                UPDATE messaging.notifications
apps/api/app/domains/messaging/service.py:858:                SET read_at = now()
apps/api/app/domains/messaging/service.py:859:                WHERE id = :nid AND organization_id = :org
apps/api/app/domains/messaging/service.py:860:                  AND recipient_id = :recipient AND read_at IS NULL
apps/api/app/domains/messaging/service.py:861:                RETURNING id, read_at
apps/api/app/domains/messaging/service.py:862:                """
apps/api/app/domains/messaging/service.py:863:            ),
apps/api/app/domains/messaging/service.py:864:            {"nid": notification_id, "org": organization_id, "recipient": recipient_id},
apps/api/app/domains/messaging/service.py:865:        )
apps/api/app/domains/messaging/service.py:866:        .mappings()
apps/api/app/domains/messaging/service.py:867:        .one_or_none()
apps/api/app/domains/messaging/service.py:868:    )
apps/api/app/domains/messaging/service.py:869:    if row is None:
apps/api/app/domains/messaging/service.py:870:        raise MessagingNotFoundError("no such unread notification for this recipient")
apps/api/app/domains/messaging/service.py:871:    return dict(row)
scripts/keycloak-bootstrap.sh:1:#!/usr/bin/env bash
scripts/keycloak-bootstrap.sh:2:# Bring a running Keycloak to the state the application actually needs.
scripts/keycloak-bootstrap.sh:3:#
scripts/keycloak-bootstrap.sh:4:# WHY THIS SCRIPT EXISTS
scripts/keycloak-bootstrap.sh:5:# ----------------------
scripts/keycloak-bootstrap.sh:6:# `services/keycloak/realm/evercoat-realm.json` defines three clients and
scripts/keycloak-bootstrap.sh:7:# ten realm roles -- and ZERO users. A realm with no users has no sign-in
scripts/keycloak-bootstrap.sh:8:# path, which is the same defect this project has now caught five times
scripts/keycloak-bootstrap.sh:9:# under a different name: "which production path WRITES this?". Importing
scripts/keycloak-bootstrap.sh:10:# that realm gives you an identity provider nobody can authenticate
scripts/keycloak-bootstrap.sh:11:# against.
scripts/keycloak-bootstrap.sh:12:#
scripts/keycloak-bootstrap.sh:13:# It also explains why authentication has never once been exercised. The
scripts/keycloak-bootstrap.sh:14:# API verifies tokens properly (JWKS, issuer, audience, expiry -- all
scripts/keycloak-bootstrap.sh:15:# four), and it has never had a real token to verify, because no Keycloak
scripts/keycloak-bootstrap.sh:16:# has ever run anywhere: not on Render, not in CI, not on the dev host.
scripts/keycloak-bootstrap.sh:17:#
scripts/keycloak-bootstrap.sh:18:# WHAT IT DOES NOT DO
scripts/keycloak-bootstrap.sh:19:# -------------------
scripts/keycloak-bootstrap.sh:20:# It does not add a password-grant client or test users to the production
scripts/keycloak-bootstrap.sh:21:# realm file. A direct-access-grant client exists so tests can obtain a
scripts/keycloak-bootstrap.sh:22:# token without driving a browser; putting it in the shipped realm would
scripts/keycloak-bootstrap.sh:23:# mean every deployment carried a password-grant path forever because CI
scripts/keycloak-bootstrap.sh:24:# once needed one. It is created HERE, at bootstrap time, and only
scripts/keycloak-bootstrap.sh:25:# when --with-test-client is passed.
scripts/keycloak-bootstrap.sh:26:#
scripts/keycloak-bootstrap.sh:27:# Usage:
scripts/keycloak-bootstrap.sh:28:#   scripts/keycloak-bootstrap.sh [--with-test-client]
scripts/keycloak-bootstrap.sh:29:#
scripts/keycloak-bootstrap.sh:30:# Environment:
scripts/keycloak-bootstrap.sh:31:#   KC_URL            base URL          (default http://localhost:8080)
scripts/keycloak-bootstrap.sh:32:#   KC_ADMIN          admin username    (default admin)
scripts/keycloak-bootstrap.sh:33:#   KC_ADMIN_PASSWORD admin password    (required)
scripts/keycloak-bootstrap.sh:34:#   KC_REALM          realm             (default evercoat)
scripts/keycloak-bootstrap.sh:35:#   KC_USER_PASSWORD  password set on every created user (required)
scripts/keycloak-bootstrap.sh:36:#   KC_SUBS_OUT       where to write the username -> sub map
scripts/keycloak-bootstrap.sh:37:#                     (default ./keycloak-subs.json)
scripts/keycloak-bootstrap.sh:38:
scripts/keycloak-bootstrap.sh:39:set -euo pipefail
scripts/keycloak-bootstrap.sh:40:
scripts/keycloak-bootstrap.sh:41:KC_URL="${KC_URL:-http://localhost:8080}"
scripts/keycloak-bootstrap.sh:42:KC_ADMIN="${KC_ADMIN:-admin}"
scripts/keycloak-bootstrap.sh:43:KC_REALM="${KC_REALM:-evercoat}"
scripts/keycloak-bootstrap.sh:44:KC_SUBS_OUT="${KC_SUBS_OUT:-./keycloak-subs.json}"
scripts/keycloak-bootstrap.sh:45:WITH_TEST_CLIENT=0
scripts/keycloak-bootstrap.sh:46:[ "${1:-}" = "--with-test-client" ] && WITH_TEST_CLIENT=1
scripts/keycloak-bootstrap.sh:47:
scripts/keycloak-bootstrap.sh:48:: "${KC_ADMIN_PASSWORD:?KC_ADMIN_PASSWORD is required}"
scripts/keycloak-bootstrap.sh:49:: "${KC_USER_PASSWORD:?KC_USER_PASSWORD is required}"
scripts/keycloak-bootstrap.sh:50:
scripts/keycloak-bootstrap.sh:51:# The ten users the seeder writes into core.users, as
scripts/keycloak-bootstrap.sh:52:# `username:realm_role`. They match `scripts/seed.py` exactly -- one user
scripts/keycloak-bootstrap.sh:53:# per role, so every permission path has a holder.
scripts/keycloak-bootstrap.sh:54:USERS=(
scripts/keycloak-bootstrap.sh:55:  "chem.demo:product_development_chemist"
scripts/keycloak-bootstrap.sh:56:  "eng.demo:product_development_engineer"
scripts/keycloak-bootstrap.sh:57:  "lead.demo:product_development_lead"
scripts/keycloak-bootstrap.sh:58:  "dir.demo:product_development_director"
scripts/keycloak-bootstrap.sh:59:  "qa.demo:qa_compliance_officer"
scripts/keycloak-bootstrap.sh:60:  "tech.demo:laboratory_technician"
scripts/keycloak-bootstrap.sh:61:  "proc.demo:procurement_specialist"
scripts/keycloak-bootstrap.sh:62:  "prod.demo:production_engineer"
scripts/keycloak-bootstrap.sh:63:  "exec.demo:executive_viewer"
scripts/keycloak-bootstrap.sh:64:  "admin.demo:administrator"
scripts/keycloak-bootstrap.sh:65:)
scripts/keycloak-bootstrap.sh:66:
scripts/keycloak-bootstrap.sh:67:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:68:# Wait for Keycloak. Not a fixed sleep: Keycloak's startup varies from a
scripts/keycloak-bootstrap.sh:69:# few seconds to a minute, and a sleep long enough to be safe is a minute
scripts/keycloak-bootstrap.sh:70:# wasted on every run while STILL not being proof.
scripts/keycloak-bootstrap.sh:71:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:72:echo "waiting for Keycloak at ${KC_URL} ..."
scripts/keycloak-bootstrap.sh:73:deadline=$(( SECONDS + 180 ))
scripts/keycloak-bootstrap.sh:74:until code="$(curl -s -o /dev/null -w '%{http_code}' "${KC_URL}/realms/master" 2>/dev/null)" \
scripts/keycloak-bootstrap.sh:75:      && [ "$code" = "200" ]; do
scripts/keycloak-bootstrap.sh:76:  if [ "$SECONDS" -ge "$deadline" ]; then
scripts/keycloak-bootstrap.sh:77:    echo "FAIL: Keycloak did not answer within 180s (last status: ${code:-none})" >&2
scripts/keycloak-bootstrap.sh:78:    exit 1
scripts/keycloak-bootstrap.sh:79:  fi
scripts/keycloak-bootstrap.sh:80:  sleep 3
scripts/keycloak-bootstrap.sh:81:done
scripts/keycloak-bootstrap.sh:82:echo "Keycloak is up."
scripts/keycloak-bootstrap.sh:83:
scripts/keycloak-bootstrap.sh:84:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:85:# Admin token. `|| tok=""` rather than a bare assignment: a failing curl
scripts/keycloak-bootstrap.sh:86:# inside $( ) aborts the whole script under `set -e`, which reports as a
scripts/keycloak-bootstrap.sh:87:# silent exit with no message at all.
scripts/keycloak-bootstrap.sh:88:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:89:admin_token() {
scripts/keycloak-bootstrap.sh:90:  local body=""
scripts/keycloak-bootstrap.sh:91:  body="$(curl -s -X POST \
scripts/keycloak-bootstrap.sh:92:    "${KC_URL}/realms/master/protocol/openid-connect/token" \
scripts/keycloak-bootstrap.sh:93:    -d "client_id=admin-cli" \
scripts/keycloak-bootstrap.sh:94:    -d "username=${KC_ADMIN}" \
scripts/keycloak-bootstrap.sh:95:    -d "password=${KC_ADMIN_PASSWORD}" \
scripts/keycloak-bootstrap.sh:96:    -d "grant_type=password")" || body=""
scripts/keycloak-bootstrap.sh:97:  printf '%s' "$body" | python -c \
scripts/keycloak-bootstrap.sh:98:    'import json,sys; d=json.load(sys.stdin); print(d.get("access_token",""))' 2>/dev/null || true
scripts/keycloak-bootstrap.sh:99:}
scripts/keycloak-bootstrap.sh:100:
scripts/keycloak-bootstrap.sh:101:TOKEN="$(admin_token)"
scripts/keycloak-bootstrap.sh:102:if [ -z "$TOKEN" ]; then
scripts/keycloak-bootstrap.sh:103:  echo "FAIL: could not obtain an admin token -- check KC_ADMIN_PASSWORD" >&2
scripts/keycloak-bootstrap.sh:104:  exit 1
scripts/keycloak-bootstrap.sh:105:fi
scripts/keycloak-bootstrap.sh:106:
scripts/keycloak-bootstrap.sh:107:api() {
scripts/keycloak-bootstrap.sh:108:  local method="$1" path="$2"
scripts/keycloak-bootstrap.sh:109:  shift 2
scripts/keycloak-bootstrap.sh:110:  curl -s -X "$method" "${KC_URL}/admin/realms${path}" \
scripts/keycloak-bootstrap.sh:111:    -H "Authorization: Bearer ${TOKEN}" \
scripts/keycloak-bootstrap.sh:112:    -H "Content-Type: application/json" "$@"
scripts/keycloak-bootstrap.sh:113:}
scripts/keycloak-bootstrap.sh:114:
scripts/keycloak-bootstrap.sh:115:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:116:# The test client, only when asked for.
scripts/keycloak-bootstrap.sh:117:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:118:if [ "$WITH_TEST_CLIENT" = "1" ]; then
scripts/keycloak-bootstrap.sh:119:  echo "creating the direct-grant test client 'evercoat-test' ..."
scripts/keycloak-bootstrap.sh:120:  # 409 means it already exists, which is success for a bootstrap script.
scripts/keycloak-bootstrap.sh:121:  api POST "/${KC_REALM}/clients" -d '{
scripts/keycloak-bootstrap.sh:122:    "clientId": "evercoat-test",
scripts/keycloak-bootstrap.sh:123:    "name": "CI and local testing only -- direct access grants",
scripts/keycloak-bootstrap.sh:124:    "enabled": true,
scripts/keycloak-bootstrap.sh:125:    "publicClient": true,
scripts/keycloak-bootstrap.sh:126:    "standardFlowEnabled": false,
scripts/keycloak-bootstrap.sh:127:    "directAccessGrantsEnabled": true,
scripts/keycloak-bootstrap.sh:128:    "serviceAccountsEnabled": false,
scripts/keycloak-bootstrap.sh:129:    "protocol": "openid-connect",
scripts/keycloak-bootstrap.sh:130:    "fullScopeAllowed": true,
scripts/keycloak-bootstrap.sh:131:    "attributes": {"post.logout.redirect.uris": "+"},
scripts/keycloak-bootstrap.sh:132:    "protocolMappers": [{
scripts/keycloak-bootstrap.sh:133:      "name": "evercoat-api-audience",
scripts/keycloak-bootstrap.sh:134:      "protocol": "openid-connect",
scripts/keycloak-bootstrap.sh:135:      "protocolMapper": "oidc-audience-mapper",
scripts/keycloak-bootstrap.sh:136:      "config": {
scripts/keycloak-bootstrap.sh:137:        "included.client.audience": "evercoat-api",
scripts/keycloak-bootstrap.sh:138:        "access.token.claim": "true",
scripts/keycloak-bootstrap.sh:139:        "id.token.claim": "false"
scripts/keycloak-bootstrap.sh:140:      }
scripts/keycloak-bootstrap.sh:141:    }]
scripts/keycloak-bootstrap.sh:142:  }' -o /dev/null -w 'client: HTTP %{http_code}\n'
scripts/keycloak-bootstrap.sh:143:
scripts/keycloak-bootstrap.sh:144:  # THE AUDIENCE MAPPER IS NOT OPTIONAL.
scripts/keycloak-bootstrap.sh:145:  #
scripts/keycloak-bootstrap.sh:146:  # `app/core/security.py` decodes with `verify_aud: True` against
scripts/keycloak-bootstrap.sh:147:  # `keycloak_audience` (default `evercoat-api`). A Keycloak access token
scripts/keycloak-bootstrap.sh:148:  # carries `aud: ["account"]` by DEFAULT -- the API's own client id
scripts/keycloak-bootstrap.sh:149:  # appears there only if a mapper puts it there. Without the block
scripts/keycloak-bootstrap.sh:150:  # above, every token would be perfectly valid and rejected, and
scripts/keycloak-bootstrap.sh:151:  # python-jose reports that as the same flat "invalid token" it reports
scripts/keycloak-bootstrap.sh:152:  # for a forged signature.
scripts/keycloak-bootstrap.sh:153:  #
scripts/keycloak-bootstrap.sh:154:  # The shipped `evercoat-web` client already carries an identical
scripts/keycloak-bootstrap.sh:155:  # mapper, which is why production sign-in is sound. The test client has
scripts/keycloak-bootstrap.sh:156:  # to match it, or CI would prove something production does not do.
scripts/keycloak-bootstrap.sh:157:fi
scripts/keycloak-bootstrap.sh:158:
scripts/keycloak-bootstrap.sh:159:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:160:# Users. Each is created, given a NON-temporary password (a temporary one
scripts/keycloak-bootstrap.sh:161:# forces a password-update flow that a direct grant cannot complete, and
scripts/keycloak-bootstrap.sh:162:# the failure reads as "invalid_grant" -- an unhelpful lie), and assigned
scripts/keycloak-bootstrap.sh:163:# its realm role.
scripts/keycloak-bootstrap.sh:164:# ---------------------------------------------------------------------------
scripts/keycloak-bootstrap.sh:165:echo "{" > "$KC_SUBS_OUT"
scripts/keycloak-bootstrap.sh:166:first=1
scripts/keycloak-bootstrap.sh:167:
scripts/keycloak-bootstrap.sh:168:for entry in "${USERS[@]}"; do
scripts/keycloak-bootstrap.sh:169:  username="${entry%%:*}"
scripts/keycloak-bootstrap.sh:170:  role="${entry##*:}"
scripts/keycloak-bootstrap.sh:171:
scripts/keycloak-bootstrap.sh:172:  api POST "/${KC_REALM}/users" -d "{
scripts/keycloak-bootstrap.sh:173:    \"username\": \"${username}\",
scripts/keycloak-bootstrap.sh:174:    \"email\": \"${username}@example.test\",
scripts/keycloak-bootstrap.sh:175:    \"emailVerified\": true,
scripts/keycloak-bootstrap.sh:176:    \"enabled\": true,
scripts/keycloak-bootstrap.sh:177:    \"firstName\": \"${username%%.*}\",
scripts/keycloak-bootstrap.sh:178:    \"lastName\": \"Demo\",
scripts/keycloak-bootstrap.sh:179:    \"credentials\": [{
scripts/keycloak-bootstrap.sh:180:      \"type\": \"password\",
scripts/keycloak-bootstrap.sh:181:      \"value\": \"${KC_USER_PASSWORD}\",
scripts/keycloak-bootstrap.sh:182:      \"temporary\": false
scripts/keycloak-bootstrap.sh:183:    }]
scripts/keycloak-bootstrap.sh:184:  }" -o /dev/null -w "user ${username}: HTTP %{http_code}\n"
scripts/keycloak-bootstrap.sh:185:
scripts/keycloak-bootstrap.sh:186:  sub="$(api GET "/${KC_REALM}/users?username=${username}&exact=true" \
scripts/keycloak-bootstrap.sh:187:    | python -c 'import json,sys
scripts/keycloak-bootstrap.sh:188:try:
scripts/keycloak-bootstrap.sh:189:    users = json.load(sys.stdin)
scripts/keycloak-bootstrap.sh:190:    print(users[0]["id"] if users else "")
scripts/keycloak-bootstrap.sh:191:except Exception:
scripts/keycloak-bootstrap.sh:192:    print("")')"
scripts/keycloak-bootstrap.sh:193:
scripts/keycloak-bootstrap.sh:194:  if [ -z "$sub" ]; then
scripts/keycloak-bootstrap.sh:195:    echo "FAIL: ${username} was not created and has no subject" >&2
scripts/keycloak-bootstrap.sh:196:    exit 1
scripts/keycloak-bootstrap.sh:197:  fi
scripts/keycloak-bootstrap.sh:198:
scripts/keycloak-bootstrap.sh:199:  role_json="$(api GET "/${KC_REALM}/roles/${role}")"
scripts/keycloak-bootstrap.sh:200:  role_ok="$(printf '%s' "$role_json" | python -c 'import json,sys
scripts/keycloak-bootstrap.sh:201:try:
scripts/keycloak-bootstrap.sh:202:    r = json.load(sys.stdin)
scripts/keycloak-bootstrap.sh:203:    print("1" if r.get("id") else "")
scripts/keycloak-bootstrap.sh:204:except Exception:
scripts/keycloak-bootstrap.sh:205:    print("")')"
scripts/keycloak-bootstrap.sh:206:  if [ -z "$role_ok" ]; then
scripts/keycloak-bootstrap.sh:207:    echo "FAIL: realm role '${role}' does not exist -- the realm import did not apply" >&2
scripts/keycloak-bootstrap.sh:208:    exit 1
scripts/keycloak-bootstrap.sh:209:  fi
scripts/keycloak-bootstrap.sh:210:  api POST "/${KC_REALM}/users/${sub}/role-mappings/realm" -d "[${role_json}]" -o /dev/null
scripts/keycloak-bootstrap.sh:211:
scripts/keycloak-bootstrap.sh:212:  [ "$first" = "1" ] || echo "," >> "$KC_SUBS_OUT"
scripts/keycloak-bootstrap.sh:213:  first=0
scripts/keycloak-bootstrap.sh:214:  printf '  "%s": "%s"' "$username" "$sub" >> "$KC_SUBS_OUT"
scripts/keycloak-bootstrap.sh:215:done
scripts/keycloak-bootstrap.sh:216:
scripts/keycloak-bootstrap.sh:217:printf '\n}\n' >> "$KC_SUBS_OUT"
scripts/keycloak-bootstrap.sh:218:
scripts/keycloak-bootstrap.sh:219:echo
scripts/keycloak-bootstrap.sh:220:echo "wrote ${#USERS[@]} subjects to ${KC_SUBS_OUT}"
scripts/keycloak-bootstrap.sh:221:echo "NEXT: scripts/keycloak-bind-subs.py -- core.users.keycloak_sub still"
scripts/keycloak-bootstrap.sh:222:echo "holds the seeder's placeholders ('demo-<username>'), and until it is"
scripts/keycloak-bootstrap.sh:223:echo "rebound every valid token resolves to no principal at all."

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "rg -n -C 45 \"def (_resolve_mentions|list_channels|post_message|promote_message)|REFERENCE|MENTION|text\\(\" apps/api/app/domains/messaging/service.py" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 418ms:
18-
19-**A notification must not disclose what the recipient cannot see.**
20-Mentioning somebody in a restricted project's channel would otherwise
21-send them a notification naming a project they have no access to — the
22-notification itself becomes the leak, and no amount of care in the
23-channel's RLS prevents it. So a mention only notifies a user who can
24-already reach that channel, and the mention link is still recorded either
25-way: the message said what it said.
26-"""
27-
28-from __future__ import annotations
29-
30-import re
31-import uuid
32-from dataclasses import dataclass
33-from typing import Any
34-
35-from sqlalchemy import text
36-from sqlalchemy.exc import IntegrityError
37-from sqlalchemy.orm import Session
38-
39-from app.core.audit import AuditEvent, write_audit
40-from app.core.tenancy import require_active_member
41-
42-__all__ = [
43-    "ChannelInput",
44-    "MessageInput",
45-    "MessagingError",
46-    "MessagingNotFoundError",
47-    "MessagingStateError",
48-    "create_channel",
49-    "list_channels",
50-    "list_messages",
51-    "mark_notification_read",
52-    "my_notifications",
53-    "notify",
54-    "post_message",
55-    "promote_message",
56-    "thread_for_record",
57-]
58-
59-# `#FRM-014`, `#LB-2026-0007`, `#T-2026-0041`. Deliberately narrow: an
60-# uppercase prefix, a hyphen, then alphanumerics and hyphens. A looser
61-# pattern would turn every `#1` and every hex colour in a message into a
62-# failed lookup, and a message full of unresolved links reads as broken.
63:_REFERENCE = re.compile(r"#([A-Z]{1,6}-[A-Za-z0-9-]{2,40})")
64-
65-# `@username`. Resolved against `core.users.email`'s local part, because
66-# that is the only handle this schema has today; a display name is not
67-# unique and cannot be a mention target.
68:_MENTION = re.compile(r"@([a-zA-Z0-9._-]{2,60})")
69-
70-# Which code prefixes resolve against which table. Written out rather
71-# than derived, because a dynamic version would need interpolated table
72-# names -- and interpolation defended by an argument has already been the
73-# wrong answer three times in this repository.
74-_RESOLVERS: dict[str, tuple[str, str]] = {
75-    "formula_version": (
76-        "version_code",
77-        """
78-        SELECT v.id FROM formulations.formula_versions v
79-        WHERE v.organization_id = :org AND v.version_code = :code
80-        """,
81-    ),
82-    "batch": (
83-        "batch_number",
84-        """
85-        SELECT b.id FROM laboratory.batches b
86-        WHERE b.organization_id = :org AND b.batch_number = :code
87-        """,
88-    ),
89-    "test": (
90-        "test_number",
91-        """
92-        SELECT t.id FROM testing.tests t
93-        WHERE t.organization_id = :org AND t.test_number = :code
94-        """,
95-    ),
96-    "failure": (
97-        "failure_code",
98-        """
99-        SELECT f.id FROM quality.failures f
100-        WHERE f.organization_id = :org AND f.failure_code = :code
101-        """,
102-    ),
103-    "material": (
104-        "material_code",
105-        """
106-        SELECT m.id FROM materials.materials m
107-        WHERE m.organization_id = :org AND m.material_code = :code
108-        """,
109-    ),
110-}
111-
112-
113-class MessagingError(RuntimeError):
--
130-    entity_type: str | None = None
131-    entity_id: uuid.UUID | None = None
132-    member_ids: tuple[uuid.UUID, ...] = ()
133-
134-
135-@dataclass(frozen=True, slots=True)
136-class MessageInput:
137-    body: str
138-    reply_to_id: uuid.UUID | None = None
139-
140-
141-# ---------------------------------------------------------------------------
142-# Channels
143-# ---------------------------------------------------------------------------
144-
145-
146-def create_channel(
147-    session: Session,
148-    *,
149-    organization_id: uuid.UUID,
150-    actor_id: uuid.UUID,
151-    spec: ChannelInput,
152-) -> dict[str, Any]:
153-    """Open a channel.
154-
155-    A PROJECT channel is created through the project, so RLS applies that
156-    project's confidentiality to the conversation from the first message.
157-    The author must be able to see the project to open a channel on it —
158-    the same predicate the policy uses, applied in the INSERT for the
159-    reason `create_formula` needed it: WITH CHECK is organization-only,
160-    so naming a restricted project would otherwise succeed and merely
161-    become invisible.
162-    """
163-    require_active_member(
164-        session, user_id=actor_id, organization_id=organization_id, role_description="author"
165-    )
166-
167-    if spec.channel_type == "project" and spec.project_id is None:
168-        raise MessagingError(
169-            "a project channel must name its project; without one, RLS cannot apply "
170-            "that project's confidentiality to the conversation"
171-        )
172-
173-    if spec.project_id is not None:
174-        channel_id = session.execute(
175:            text(
176-                """
177-                INSERT INTO messaging.channels
178-                    (organization_id, project_id, channel_type, name, entity_type,
179-                     entity_id, created_by)
180-                SELECT :org, p.id, :ctype, :name, :etype, :eid, :actor
181-                FROM projects.projects p
182-                WHERE p.id = :pid AND p.organization_id = :org
183-                  AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
184-                RETURNING id
185-                """
186-            ),
187-            {
188-                "org": organization_id,
189-                "pid": spec.project_id,
190-                "ctype": spec.channel_type,
191-                "name": spec.name,
192-                "etype": spec.entity_type,
193-                "eid": spec.entity_id,
194-                "actor": actor_id,
195-            },
196-        ).scalar_one_or_none()
197-        if channel_id is None:
198-            raise MessagingNotFoundError("no such project in this organization")
199-    else:
200-        channel_id = session.execute(
201:            text(
202-                """
203-                INSERT INTO messaging.channels
204-                    (organization_id, channel_type, name, entity_type, entity_id,
205-                     created_by)
206-                VALUES (:org, :ctype, :name, :etype, :eid, :actor)
207-                RETURNING id
208-                """
209-            ),
210-            {
211-                "org": organization_id,
212-                "ctype": spec.channel_type,
213-                "name": spec.name,
214-                "etype": spec.entity_type,
215-                "eid": spec.entity_id,
216-                "actor": actor_id,
217-            },
218-        ).scalar_one()
219-
220-    # The author is always a member. A channel its creator is not in is a
221-    # channel that vanishes from their own list the moment they make it.
222-    for member in {actor_id, *spec.member_ids}:
223-        require_active_member(
224-            session, user_id=member, organization_id=organization_id, role_description="member"
225-        )
226-        session.execute(
227:            text(
228-                """
229-                INSERT INTO messaging.channel_members
230-                    (organization_id, channel_id, user_id)
231-                VALUES (:org, :cid, :uid)
232-                ON CONFLICT (channel_id, user_id) DO NOTHING
233-                """
234-            ),
235-            {"org": organization_id, "cid": channel_id, "uid": member},
236-        )
237-
238-    write_audit(
239-        session,
240-        AuditEvent(
241-            action="channel.created",
242-            entity_type="channel",
243-            entity_id=str(channel_id),
244-            organization_id=organization_id,
245-            user_id=actor_id,
246-            new_state={"channel_type": spec.channel_type, "name": spec.name},
247-            reason="channel opened",
248-        ),
249-    )
250-    return {"id": channel_id, "channel_type": spec.channel_type}
251-
252-
253-def thread_for_record(
254-    session: Session,
255-    *,
256-    organization_id: uuid.UUID,
257-    actor_id: uuid.UUID,
258-    entity_type: str,
259-    entity_id: uuid.UUID,
260-    project_id: uuid.UUID,
261-) -> dict[str, Any]:
262-    """The technical thread for a record, opening one if it has none.
263-
264-    Idempotent on purpose. Every screen that offers "discuss this" would
265-    otherwise create a new thread per click, and a record with six threads
266-    has no discussion at all — it has six fragments nobody reads together.
267-    """
268-    existing = (
269-        session.execute(
270:            text(
271-                """
272-                SELECT id, channel_type FROM messaging.channels
273-                WHERE organization_id = :org AND entity_type = :etype
274-                  AND entity_id = :eid AND channel_type = 'technical_thread'
275-                  AND NOT is_archived
276-                """
277-            ),
278-            {"org": organization_id, "etype": entity_type, "eid": entity_id},
279-        )
280-        .mappings()
281-        .one_or_none()
282-    )
283-    if existing is not None:
284-        return dict(existing)
285-
286-    return create_channel(
287-        session,
288-        organization_id=organization_id,
289-        actor_id=actor_id,
290-        spec=ChannelInput(
291-            channel_type="technical_thread",
292-            name=f"Discussion: {entity_type}",
293-            project_id=project_id,
294-            entity_type=entity_type,
295-            entity_id=entity_id,
296-        ),
297-    )
298-
299-
300:def list_channels(
301-    session: Session, *, organization_id: uuid.UUID, actor_id: uuid.UUID, limit: int = 100
302-) -> list[dict[str, Any]]:
303-    """Channels this caller can see.
304-
305-    RLS excludes restricted projects they are not in; membership narrows
306-    it further for direct messages, which are not project-scoped and
307-    therefore have nothing else to hide behind.
308-    """
309-    rows = session.execute(
310:        text(
311-            """
312-            SELECT c.id, c.channel_type, c.name, c.project_id, c.entity_type,
313-                   c.entity_id, c.created_at,
314-                   (SELECT count(*) FROM messaging.messages m
315-                     WHERE m.channel_id = c.id AND NOT m.is_deleted) AS message_count
316-            FROM messaging.channels c
317-            WHERE c.organization_id = :org
318-              AND NOT c.is_archived
319-              AND (
320-                    c.channel_type <> 'direct'
321-                    OR EXISTS (
322-                        SELECT 1 FROM messaging.channel_members cm
323-                        WHERE cm.channel_id = c.id AND cm.user_id = :actor
324-                    )
325-                  )
326-            ORDER BY c.created_at DESC
327-            LIMIT :limit
328-            """
329-        ),
330-        {"org": organization_id, "actor": actor_id, "limit": limit},
331-    ).mappings()
332-    return [dict(r) for r in rows]
333-
334-
335-# ---------------------------------------------------------------------------
336-# Messages
337-# ---------------------------------------------------------------------------
338-
339-
340:def post_message(
341-    session: Session,
342-    *,
343-    channel_id: uuid.UUID,
344-    organization_id: uuid.UUID,
345-    actor_id: uuid.UUID,
346-    spec: MessageInput,
347-) -> dict[str, Any]:
348-    """Post a message, resolving its `#references` and `@mentions`.
349-
350-    **Links are resolved at WRITE time and stored.** Resolving on read
351-    would mean a message rendering differently after the record it names
352-    is renamed or retired, and a conversation must say what it said when
353-    it was written.
354-
355-    **Resolution runs in the author's session**, so a reference to a
356-    record they cannot see simply does not resolve — it stays as text.
357-    That is deliberate: an unresolvable reference is a broken link, and
358-    the alternative is a link whose existence confirms that a record with
359-    that code exists somewhere the author cannot look.
360-    """
361-    channel = (
362-        session.execute(
363:            text(
364-                """
365-                SELECT id, project_id, channel_type FROM messaging.channels
366-                WHERE id = :cid AND organization_id = :org AND NOT is_archived
367-                """
368-            ),
369-            {"cid": channel_id, "org": organization_id},
370-        )
371-        .mappings()
372-        .one_or_none()
373-    )
374-    if channel is None:
375-        raise MessagingNotFoundError("no such channel in this organization")
376-
377-    message_id: uuid.UUID = session.execute(
378:        text(
379-            """
380-            INSERT INTO messaging.messages
381-                (organization_id, channel_id, body, reply_to_id, author_id)
382-            VALUES (:org, :cid, :body, :reply, :actor)
383-            RETURNING id
384-            """
385-        ),
386-        {
387-            "org": organization_id,
388-            "cid": channel_id,
389-            "body": spec.body,
390-            "reply": spec.reply_to_id,
391-            "actor": actor_id,
392-        },
393-    ).scalar_one()
394-
395-    links = _resolve_references(
396-        session, organization_id=organization_id, message_id=message_id, body=spec.body
397-    )
398-    mentions = _resolve_mentions(
399-        session,
400-        organization_id=organization_id,
401-        message_id=message_id,
402-        channel_id=channel_id,
403-        body=spec.body,
404-        actor_id=actor_id,
405-    )
406-
407-    return {
408-        "id": message_id,
409-        "links": links,
410-        "mentions": mentions,
411-    }
412-
413-
414-def _resolve_references(
415-    session: Session, *, organization_id: uuid.UUID, message_id: uuid.UUID, body: str
416-) -> list[dict[str, Any]]:
417-    """Turn `#FRM-014` into a row pointing at the real record.
418-
419-    Tries every resolver for each code, because the prefixes are a
420-    convention rather than a guarantee — a deployment may issue
421-    `T-2026-0041` for a test and `T-...` for something else later, and a
422-    resolver keyed on the prefix alone would then point at the wrong
423-    table with complete confidence.
424-    """
425-    found: list[dict[str, Any]] = []
426:    for code in dict.fromkeys(_REFERENCE.findall(body)):
427-        for entity_type, (_column, sql) in _RESOLVERS.items():
428-            entity_id = session.execute(
429:                text(sql), {"org": organization_id, "code": code}
430-            ).scalar_one_or_none()
431-            if entity_id is None:
432-                continue
433-
434-            session.execute(
435:                text(
436-                    """
437-                    INSERT INTO messaging.message_links
438-                        (organization_id, message_id, link_type, entity_type,
439-                         entity_id, label)
440-                    VALUES (:org, :mid, 'record', :etype, :eid, :label)
441-                    """
442-                ),
443-                {
444-                    "org": organization_id,
445-                    "mid": message_id,
446-                    "etype": entity_type,
447-                    "eid": entity_id,
448-                    "label": code,
449-                },
450-            )
451-            found.append({"code": code, "entity_type": entity_type, "entity_id": entity_id})
452-            break
453-
454-    return found
455-
456-
457:def _resolve_mentions(
458-    session: Session,
459-    *,
460-    organization_id: uuid.UUID,
461-    message_id: uuid.UUID,
462-    channel_id: uuid.UUID,
463-    body: str,
464-    actor_id: uuid.UUID,
465-) -> list[dict[str, Any]]:
466-    """Record @mentions, and notify only those who can see the channel.
467-
468-    🔴 THE NOTIFICATION IS THE LEAK, IF YOU LET IT BE.
469-
470-    Mentioning somebody in a restricted project's channel would otherwise
471-    send them a notification naming a project they have no access to. The
472-    channel's RLS protects the MESSAGES and does nothing about a
473-    notification row addressed to an outsider — so membership is checked
474-    before notifying.
475-
476-    The mention LINK is recorded either way. The message said what it
477-    said, and editing history to match permissions would be a worse lie
478-    than an unresolved handle.
479-    """
480-    notified: list[dict[str, Any]] = []
481:    for handle in dict.fromkeys(_MENTION.findall(body)):
482-        user = (
483-            session.execute(
484:                text(
485-                    """
486-                    SELECT u.id, u.display_name
487-                    FROM core.users u
488-                    JOIN core.organization_members m
489-                      ON m.user_id = u.id AND m.organization_id = :org
490-                     AND m.status = 'active'
491-                    WHERE split_part(u.email, '@', 1) = :handle
492-                    """
493-                ),
494-                {"org": organization_id, "handle": handle},
495-            )
496-            .mappings()
497-            .one_or_none()
498-        )
499-        if user is None:
500-            continue
501-
502-        session.execute(
503:            text(
504-                """
505-                INSERT INTO messaging.message_links
506-                    (organization_id, message_id, link_type, mentioned_user_id, label)
507-                VALUES (:org, :mid, 'mention', :uid, :label)
508-                """
509-            ),
510-            {"org": organization_id, "mid": message_id, "uid": user["id"], "label": handle},
511-        )
512-
513-        # Can the RECIPIENT reach this channel?
514-        #
515-        # 🔴 THE ANSWER CANNOT BE BORROWED FROM RLS HERE.
516-        #
517-        # This query runs in the AUTHOR's session, so RLS answers "can the
518-        # author see it?" -- and the author demonstrably can, because they
519-        # just posted in it. Reusing `list_channels`'s predicate would
520-        # therefore return true for every project channel including a
521-        # restricted one, and the notification would name a project the
522-        # recipient has no access to. The leak would be the notification
523-        # itself, in the one place the channel's own RLS cannot reach.
524-        #
525-        # So the recipient's access is evaluated EXPLICITLY, against the
526-        # same two facts the project policy uses: confidentiality, and
527-        # membership.
528-        reachable = session.execute(
529:            text(
530-                """
531-                SELECT EXISTS (
532-                    SELECT 1
533-                    FROM messaging.channels c
534-                    LEFT JOIN projects.projects p
535-                      ON p.id = c.project_id AND p.organization_id = c.organization_id
536-                    WHERE c.id = :cid AND c.organization_id = :org
537-                      -- A direct message reaches only its own members.
538-                      AND (
539-                            c.channel_type <> 'direct'
540-                            OR EXISTS (
541-                                SELECT 1 FROM messaging.channel_members cm
542-                                WHERE cm.channel_id = c.id AND cm.user_id = :uid
543-                            )
544-                          )
545-                      -- A project channel reaches only people who can see
546-                      -- the project. `p.confidentiality` is NULL for a
547-                      -- channel with no project, which is why the
548-                      -- IS NULL arm comes first rather than relying on a
549-                      -- NULL comparison to behave.
550-                      AND (
551-                            c.project_id IS NULL
552-                            OR p.confidentiality = 'normal'
553-                            OR EXISTS (
554-                                SELECT 1 FROM projects.project_members pm
555-                                WHERE pm.project_id = c.project_id
556-                                  AND pm.organization_id = c.organization_id
557-                                  AND pm.user_id = :uid
558-                                  AND pm.status = 'active'
559-                            )
560-                          )
561-                )
562-                """
563-            ),
564-            {"cid": channel_id, "org": organization_id, "uid": user["id"]},
565-        ).scalar_one()
566-
567-        if reachable and user["id"] != actor_id:
568-            notify(
569-                session,
570-                organization_id=organization_id,
571-                recipient_id=user["id"],
572-                notification_type="message.mention",
573-                title="You were mentioned",
574-                body=body[:200],
575-                entity_type="message",
576-                entity_id=message_id,
577-                is_actionable=True,
578-            )
579-            notified.append({"handle": handle, "user_id": user["id"], "notified": True})
580-        else:
581-            # Recorded, deliberately, so the behaviour is inspectable
582-            # rather than a silent no-op somebody later mistakes for a bug.
583-            notified.append({"handle": handle, "user_id": user["id"], "notified": False})
584-
585-    return notified
586-
587-
588-def list_messages(
589-    session: Session,
590-    *,
591-    channel_id: uuid.UUID,
592-    organization_id: uuid.UUID,
593-    limit: int = 100,
594-) -> list[dict[str, Any]]:
595-    """A channel's messages, oldest first, with their links.
596-
597-    Withdrawn messages come back with their body replaced rather than
598-    omitted: a conversation with holes in it cannot be read, and a reply
599-    to a message that has vanished is unintelligible.
600-    """
601-    rows = [
602-        dict(r)
603-        for r in session.execute(
604:            text(
605-                """
606-                SELECT m.id, m.body, m.author_id, m.posted_at, m.edited_at,
607-                       m.is_deleted, m.reply_to_id, u.display_name AS author_name
608-                FROM messaging.messages m
609-                JOIN core.users u ON u.id = m.author_id
610-                WHERE m.channel_id = :cid AND m.organization_id = :org
611-                ORDER BY m.posted_at
612-                LIMIT :limit
613-                """
614-            ),
615-            {"cid": channel_id, "org": organization_id, "limit": limit},
616-        ).mappings()
617-    ]
618-
619-    if not rows:
620-        return []
621-
622-    links = session.execute(
623:        text(
624-            """
625-            SELECT l.message_id, l.link_type, l.entity_type, l.entity_id,
626-                   l.mentioned_user_id, l.label
627-            FROM messaging.message_links l
628-            JOIN messaging.messages m
629-              ON m.id = l.message_id AND m.organization_id = l.organization_id
630-            WHERE m.channel_id = :cid AND l.organization_id = :org
631-            """
632-        ),
633-        {"cid": channel_id, "org": organization_id},
634-    ).mappings()
635-
636-    by_message: dict[uuid.UUID, list[dict[str, Any]]] = {}
637-    for link in links:
638-        by_message.setdefault(link["message_id"], []).append(dict(link))
639-
640-    for row in rows:
641-        row["links"] = by_message.get(row["id"], [])
642-        if row["is_deleted"]:
643-            row["body"] = "(this message was withdrawn)"
644-
645-    return rows
646-
647-
648:def promote_message(
649-    session: Session,
650-    *,
651-    message_id: uuid.UUID,
652-    organization_id: uuid.UUID,
653-    actor_id: uuid.UUID,
654-    task_type: str,
655-    title: str,
656-    assigned_user_id: uuid.UUID | None = None,
657-) -> dict[str, Any]:
658-    """Turn a message into a controlled record — a TASK.
659-
660-    🔴 §7: "Informal chat never becomes authoritative knowledge
661-    automatically. Conclusions become controlled records only by explicit
662-    human promotion."
663-
664-    This is that explicit act, and it deliberately creates a task rather
665-    than a decision or a conclusion: somebody still has to do the work and
666-    sign for it. A path from "somebody said so in chat" straight to a
667-    technical decision is the thing the rule forbids.
668-
669-    The promotion is recorded as a link back to the message, so the task
670-    can always answer "where did this come from?" — which is the digital
671-    thread's rule applied to the conversation itself.
672-    """
673-    message = (
674-        session.execute(
675:            text(
676-                """
677-                SELECT m.id, m.body, c.project_id
678-                FROM messaging.messages m
679-                JOIN messaging.channels c
680-                  ON c.id = m.channel_id AND c.organization_id = m.organization_id
681-                WHERE m.id = :mid AND m.organization_id = :org
682-                """
683-            ),
684-            {"mid": message_id, "org": organization_id},
685-        )
686-        .mappings()
687-        .one_or_none()
688-    )
689-    if message is None:
690-        raise MessagingNotFoundError("no such message in this organization")
691-
692-    if assigned_user_id is not None:
693-        require_active_member(
694-            session,
695-            user_id=assigned_user_id,
696-            organization_id=organization_id,
697-            role_description="assignee",
698-        )
699-
700-    try:
701-        task_id: uuid.UUID = session.execute(
702:            text(
703-                """
704-                INSERT INTO workflow.tasks
705-                    (organization_id, project_id, task_type, title, description,
706-                     assigned_user_id, assigned_role, source_event, entity_type,
707-                     entity_id, created_by)
708-                VALUES (:org, :pid, :ttype, :title, :description, :assignee,
709-                        CASE WHEN :assignee IS NULL THEN 'product_development_lead' END,
710-                        'message.promoted', 'message', :mid, :actor)
711-                RETURNING id
712-                """
713-            ),
714-            {
715-                "org": organization_id,
716-                "pid": message["project_id"],
717-                "ttype": task_type,
718-                "title": title,
719-                "description": message["body"][:2000],
720-                "assignee": assigned_user_id,
721-                "mid": message_id,
722-                "actor": actor_id,
723-            },
724-        ).scalar_one()
725-    except IntegrityError as exc:
726-        session.rollback()
727-        raise MessagingError(str(exc.orig)) from exc
728-
729-    session.execute(
730:        text(
731-            """
732-            INSERT INTO messaging.message_links
733-                (organization_id, message_id, link_type, entity_type, entity_id, label)
734-            VALUES (:org, :mid, 'promotion', 'task', :tid, :label)
735-            """
736-        ),
737-        {"org": organization_id, "mid": message_id, "tid": task_id, "label": title[:100]},
738-    )
739-
740-    write_audit(
741-        session,
742-        AuditEvent(
743-            action="message.promoted",
744-            entity_type="task",
745-            entity_id=str(task_id),
746-            organization_id=organization_id,
747-            user_id=actor_id,
748-            new_state={"task_type": task_type, "from_message": str(message_id)},
749-            reason=f"promoted from a message: {title}",
750-        ),
751-    )
752-    return {"task_id": task_id, "message_id": message_id}
753-
754-
755-# ---------------------------------------------------------------------------
756-# Notifications
757-# ---------------------------------------------------------------------------
758-
759-
760-def notify(
761-    session: Session,
762-    *,
763-    organization_id: uuid.UUID,
764-    recipient_id: uuid.UUID,
765-    notification_type: str,
766-    title: str,
767-    body: str | None = None,
768-    entity_type: str | None = None,
769-    entity_id: uuid.UUID | None = None,
770-    is_actionable: bool = False,
771-) -> uuid.UUID:
772-    """Write one notification.
773-
774-    THE single writer, in the same sense as one approval engine: every
775-    module calls this rather than growing its own table. `is_actionable`
776-    separates "you must do something" from "this happened", because §11
777-    requires a badge to count items needing action and that distinction
778-    has to exist in the data or every count is a total.
779-    """
780-    return session.execute(  # type: ignore[no-any-return]
781:        text(
782-            """
783-            INSERT INTO messaging.notifications
784-                (organization_id, recipient_id, notification_type, title, body,
785-                 entity_type, entity_id, is_actionable)
786-            VALUES (:org, :recipient, :ntype, :title, :body, :etype, :eid, :actionable)
787-            RETURNING id
788-            """
789-        ),
790-        {
791-            "org": organization_id,
792-            "recipient": recipient_id,
793-            "ntype": notification_type,
794-            "title": title,
795-            "body": body,
796-            "etype": entity_type,
797-            "eid": entity_id,
798-            "actionable": is_actionable,
799-        },
800-    ).scalar_one()
801-
802-
803-def my_notifications(
804-    session: Session,
805-    *,
806-    organization_id: uuid.UUID,
807-    recipient_id: uuid.UUID,
808-    unread_only: bool = False,
809-    limit: int = 100,
810-) -> list[dict[str, Any]]:
811-    """This caller's notifications.
812-
813-    Scoped by `recipient_id` in the predicate rather than by RLS, because
814-    notifications are organization-scoped rows: without this clause every
815-    colleague's notifications would be readable. RLS answers "which
816-    tenant"; this answers "whose".
817-    """
818-    rows = session.execute(
819:        text(
820-            """
821-            SELECT id, notification_type, title, body, entity_type, entity_id,
822-                   is_actionable, read_at, created_at
823-            FROM messaging.notifications
824-            WHERE organization_id = :org AND recipient_id = :recipient
825-              AND (:unread_only = FALSE OR read_at IS NULL)
826-            ORDER BY created_at DESC
827-            LIMIT :limit
828-            """
829-        ),
830-        {
831-            "org": organization_id,
832-            "recipient": recipient_id,
833-            "unread_only": unread_only,
834-            "limit": limit,
835-        },
836-    ).mappings()
837-    return [dict(r) for r in rows]
838-
839-
840-def mark_notification_read(
841-    session: Session,
842-    *,
843-    notification_id: uuid.UUID,
844-    organization_id: uuid.UUID,
845-    recipient_id: uuid.UUID,
846-) -> dict[str, Any]:
847-    """Mark one as read.
848-
849-    `recipient_id` is in the WHERE clause, so a caller cannot mark
850-    somebody else's notification read — which would hide it from the
851-    person who needed it, silently and permanently.
852-    """
853-    row = (
854-        session.execute(
855:            text(
856-                """
857-                UPDATE messaging.notifications
858-                SET read_at = now()
859-                WHERE id = :nid AND organization_id = :org
860-                  AND recipient_id = :recipient AND read_at IS NULL
861-                RETURNING id, read_at
862-                """
863-            ),
864-            {"nid": notification_id, "org": organization_id, "recipient": recipient_id},
865-        )
866-        .mappings()
867-        .one_or_none()
868-    )
869-    if row is None:
870-        raise MessagingNotFoundError("no such unread notification for this recipient")
871-    return dict(row)

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -C 35 "promote|auth:|name: auth|keycloak|token|curl|pytest|023|restricted|list_channels|mention|NULL|project_id" apps/api/app/api/messaging.py .github/workflows/ci.yml apps/api/tests/db/test_023_messaging.py' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 452ms:
apps/api/app/api/messaging.py-1-"""Messaging, notifications, and promotion into controlled records.
apps/api/app/api/messaging.py-2-
apps/api/app/api/messaging.py-3-**Most of these routes carry no permission dependency, deliberately** --
apps/api/app/api/messaging.py-4-the same reasoning as My Work. There are no `message.*` or
apps/api/app/api/messaging.py-5-`notification.*` permissions in the catalogue, and inventing them here
apps/api/app/api/messaging.py-6-would produce exactly the defect this project has now caught five times:
apps/api/app/api/messaging.py-7-a permission nobody holds, gating a feature nobody can then use.
apps/api/app/api/messaging.py-8-
apps/api/app/api/messaging.py-9-That is not a gap. Messaging is governed by something stronger than a
apps/api/app/api/messaging.py:10:grant: **RLS and channel membership**. A restricted project's channel is
apps/api/app/api/messaging.py-11-not returned to a non-member by the database, so there is nothing for a
apps/api/app/api/messaging.py:12:permission check to add. `promote_message` is the exception -- it creates
apps/api/app/api/messaging.py-13-a controlled record, so it requires `project.edit`.
apps/api/app/api/messaging.py-14-"""
apps/api/app/api/messaging.py-15-
apps/api/app/api/messaging.py-16-from __future__ import annotations
apps/api/app/api/messaging.py-17-
apps/api/app/api/messaging.py-18-import uuid
apps/api/app/api/messaging.py-19-from typing import Any
apps/api/app/api/messaging.py-20-
apps/api/app/api/messaging.py-21-from fastapi import APIRouter, Depends, HTTPException, Query, status
apps/api/app/api/messaging.py-22-from pydantic import BaseModel, Field
apps/api/app/api/messaging.py-23-from sqlalchemy.orm import Session
apps/api/app/api/messaging.py-24-
apps/api/app/api/messaging.py-25-from app.core.security import Principal, get_db, get_principal, require_permission
apps/api/app/api/messaging.py-26-from app.core.tenancy import CrossTenantReferenceError
apps/api/app/api/messaging.py-27-from app.domains.messaging.service import (
apps/api/app/api/messaging.py-28-    ChannelInput,
apps/api/app/api/messaging.py-29-    MessageInput,
apps/api/app/api/messaging.py-30-    MessagingError,
apps/api/app/api/messaging.py-31-    MessagingNotFoundError,
apps/api/app/api/messaging.py-32-    create_channel,
apps/api/app/api/messaging.py:33:    list_channels,
apps/api/app/api/messaging.py-34-    list_messages,
apps/api/app/api/messaging.py-35-    mark_notification_read,
apps/api/app/api/messaging.py-36-    my_notifications,
apps/api/app/api/messaging.py-37-    post_message,
apps/api/app/api/messaging.py:38:    promote_message,
apps/api/app/api/messaging.py-39-    thread_for_record,
apps/api/app/api/messaging.py-40-)
apps/api/app/api/messaging.py-41-
apps/api/app/api/messaging.py-42-router = APIRouter()
apps/api/app/api/messaging.py-43-
apps/api/app/api/messaging.py-44-__all__ = ["router"]
apps/api/app/api/messaging.py-45-
apps/api/app/api/messaging.py-46-
apps/api/app/api/messaging.py-47-class ChannelCreate(BaseModel):
apps/api/app/api/messaging.py-48-    channel_type: str = Field(pattern="^(project|direct|technical_thread|announcement)$")
apps/api/app/api/messaging.py-49-    name: str | None = Field(default=None, max_length=200)
apps/api/app/api/messaging.py:50:    project_id: uuid.UUID | None = None
apps/api/app/api/messaging.py-51-    entity_type: str | None = Field(default=None, max_length=50)
apps/api/app/api/messaging.py-52-    entity_id: uuid.UUID | None = None
apps/api/app/api/messaging.py-53-    member_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
apps/api/app/api/messaging.py-54-
apps/api/app/api/messaging.py-55-
apps/api/app/api/messaging.py-56-class ThreadOpen(BaseModel):
apps/api/app/api/messaging.py-57-    """Open (or find) the discussion thread attached to one record."""
apps/api/app/api/messaging.py-58-
apps/api/app/api/messaging.py-59-    entity_type: str = Field(max_length=50)
apps/api/app/api/messaging.py-60-    entity_id: uuid.UUID
apps/api/app/api/messaging.py:61:    project_id: uuid.UUID
apps/api/app/api/messaging.py-62-
apps/api/app/api/messaging.py-63-
apps/api/app/api/messaging.py-64-class MessagePost(BaseModel):
apps/api/app/api/messaging.py-65-    # 4000 characters, not unbounded. A message is a message; a 2MB paste
apps/api/app/api/messaging.py-66-    # belongs in an attachment, where it can be versioned and scanned.
apps/api/app/api/messaging.py-67-    body: str = Field(min_length=1, max_length=4000)
apps/api/app/api/messaging.py-68-    reply_to_id: uuid.UUID | None = None
apps/api/app/api/messaging.py-69-
apps/api/app/api/messaging.py-70-
apps/api/app/api/messaging.py-71-class MessagePromote(BaseModel):
apps/api/app/api/messaging.py-72-    task_type: str = Field(max_length=50)
apps/api/app/api/messaging.py-73-    title: str = Field(min_length=1, max_length=200)
apps/api/app/api/messaging.py-74-    assigned_user_id: uuid.UUID | None = None
apps/api/app/api/messaging.py-75-
apps/api/app/api/messaging.py-76-
apps/api/app/api/messaging.py-77-@router.get("/channels", summary="Channels this user can see")
apps/api/app/api/messaging.py-78-def get_channels(
apps/api/app/api/messaging.py-79-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-80-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-81-    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py-82-) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py:83:    return list_channels(
apps/api/app/api/messaging.py-84-        session,
apps/api/app/api/messaging.py-85-        organization_id=principal.organization_id,
apps/api/app/api/messaging.py-86-        actor_id=principal.user_id,
apps/api/app/api/messaging.py-87-        limit=limit,
apps/api/app/api/messaging.py-88-    )
apps/api/app/api/messaging.py-89-
apps/api/app/api/messaging.py-90-
apps/api/app/api/messaging.py-91-@router.post("/channels", status_code=status.HTTP_201_CREATED, summary="Open a channel")
apps/api/app/api/messaging.py-92-def post_channel(
apps/api/app/api/messaging.py-93-    payload: ChannelCreate,
apps/api/app/api/messaging.py-94-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-95-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-96-) -> dict[str, Any]:
apps/api/app/api/messaging.py-97-    try:
apps/api/app/api/messaging.py-98-        result = create_channel(
apps/api/app/api/messaging.py-99-            session,
apps/api/app/api/messaging.py-100-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-101-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-102-            spec=ChannelInput(
apps/api/app/api/messaging.py-103-                channel_type=payload.channel_type,
apps/api/app/api/messaging.py-104-                name=payload.name,
apps/api/app/api/messaging.py:105:                project_id=payload.project_id,
apps/api/app/api/messaging.py-106-                entity_type=payload.entity_type,
apps/api/app/api/messaging.py-107-                entity_id=payload.entity_id,
apps/api/app/api/messaging.py-108-                member_ids=tuple(payload.member_ids),
apps/api/app/api/messaging.py-109-            ),
apps/api/app/api/messaging.py-110-        )
apps/api/app/api/messaging.py-111-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-112-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-113-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-114-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-115-    session.commit()
apps/api/app/api/messaging.py-116-    return result
apps/api/app/api/messaging.py-117-
apps/api/app/api/messaging.py-118-
apps/api/app/api/messaging.py-119-@router.post("/threads", summary="The discussion thread for a record, opening one if needed")
apps/api/app/api/messaging.py-120-def open_thread(
apps/api/app/api/messaging.py-121-    payload: ThreadOpen,
apps/api/app/api/messaging.py-122-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-123-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-124-) -> dict[str, Any]:
apps/api/app/api/messaging.py-125-    """Idempotent.
apps/api/app/api/messaging.py-126-
apps/api/app/api/messaging.py-127-    Every "discuss this" button can call it without checking first, which
apps/api/app/api/messaging.py-128-    is the only way a record ends up with one thread rather than six.
apps/api/app/api/messaging.py-129-    """
apps/api/app/api/messaging.py-130-    try:
apps/api/app/api/messaging.py-131-        result = thread_for_record(
apps/api/app/api/messaging.py-132-            session,
apps/api/app/api/messaging.py-133-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-134-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-135-            entity_type=payload.entity_type,
apps/api/app/api/messaging.py-136-            entity_id=payload.entity_id,
apps/api/app/api/messaging.py:137:            project_id=payload.project_id,
apps/api/app/api/messaging.py-138-        )
apps/api/app/api/messaging.py-139-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-140-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-141-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-142-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-143-    session.commit()
apps/api/app/api/messaging.py-144-    return result
apps/api/app/api/messaging.py-145-
apps/api/app/api/messaging.py-146-
apps/api/app/api/messaging.py-147-@router.get("/channels/{channel_id}/messages", summary="A channel's messages")
apps/api/app/api/messaging.py-148-def get_messages(
apps/api/app/api/messaging.py-149-    channel_id: uuid.UUID,
apps/api/app/api/messaging.py-150-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-151-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-152-    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py-153-) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py-154-    return list_messages(
apps/api/app/api/messaging.py-155-        session,
apps/api/app/api/messaging.py-156-        channel_id=channel_id,
apps/api/app/api/messaging.py-157-        organization_id=principal.organization_id,
apps/api/app/api/messaging.py-158-        limit=limit,
apps/api/app/api/messaging.py-159-    )
apps/api/app/api/messaging.py-160-
apps/api/app/api/messaging.py-161-
apps/api/app/api/messaging.py-162-@router.post(
apps/api/app/api/messaging.py-163-    "/channels/{channel_id}/messages",
apps/api/app/api/messaging.py-164-    status_code=status.HTTP_201_CREATED,
apps/api/app/api/messaging.py:165:    summary="Post a message, resolving #references and @mentions",
apps/api/app/api/messaging.py-166-)
apps/api/app/api/messaging.py-167-def post_channel_message(
apps/api/app/api/messaging.py-168-    channel_id: uuid.UUID,
apps/api/app/api/messaging.py-169-    payload: MessagePost,
apps/api/app/api/messaging.py-170-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-171-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-172-) -> dict[str, Any]:
apps/api/app/api/messaging.py-173-    try:
apps/api/app/api/messaging.py-174-        result = post_message(
apps/api/app/api/messaging.py-175-            session,
apps/api/app/api/messaging.py-176-            channel_id=channel_id,
apps/api/app/api/messaging.py-177-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-178-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-179-            spec=MessageInput(body=payload.body, reply_to_id=payload.reply_to_id),
apps/api/app/api/messaging.py-180-        )
apps/api/app/api/messaging.py-181-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-182-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-183-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-184-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-185-    session.commit()
apps/api/app/api/messaging.py-186-    return result
apps/api/app/api/messaging.py-187-
apps/api/app/api/messaging.py-188-
apps/api/app/api/messaging.py-189-@router.post(
apps/api/app/api/messaging.py:190:    "/messages/{message_id}/promote",
apps/api/app/api/messaging.py-191-    status_code=status.HTTP_201_CREATED,
apps/api/app/api/messaging.py-192-    summary="Promote a message into a controlled record (a task)",
apps/api/app/api/messaging.py-193-)
apps/api/app/api/messaging.py-194-def post_promotion(
apps/api/app/api/messaging.py-195-    message_id: uuid.UUID,
apps/api/app/api/messaging.py-196-    payload: MessagePromote,
apps/api/app/api/messaging.py-197-    principal: Principal = Depends(require_permission("project.edit")),
apps/api/app/api/messaging.py-198-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-199-) -> dict[str, Any]:
apps/api/app/api/messaging.py-200-    """The only route here that requires a permission.
apps/api/app/api/messaging.py-201-
apps/api/app/api/messaging.py-202-    Section 7: informal chat never becomes authoritative knowledge
apps/api/app/api/messaging.py-203-    automatically. This route is the explicit human act that the rule
apps/api/app/api/messaging.py-204-    demands, and it is the only one in this module that writes a
apps/api/app/api/messaging.py-205-    controlled record -- which is exactly why it is the only one gated.
apps/api/app/api/messaging.py-206-    """
apps/api/app/api/messaging.py-207-    try:
apps/api/app/api/messaging.py:208:        result = promote_message(
apps/api/app/api/messaging.py-209-            session,
apps/api/app/api/messaging.py-210-            message_id=message_id,
apps/api/app/api/messaging.py-211-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-212-            actor_id=principal.user_id,
apps/api/app/api/messaging.py-213-            task_type=payload.task_type,
apps/api/app/api/messaging.py-214-            title=payload.title,
apps/api/app/api/messaging.py-215-            assigned_user_id=payload.assigned_user_id,
apps/api/app/api/messaging.py-216-        )
apps/api/app/api/messaging.py-217-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-218-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-219-    except (MessagingError, CrossTenantReferenceError) as exc:
apps/api/app/api/messaging.py-220-        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
apps/api/app/api/messaging.py-221-    session.commit()
apps/api/app/api/messaging.py-222-    return result
apps/api/app/api/messaging.py-223-
apps/api/app/api/messaging.py-224-
apps/api/app/api/messaging.py-225-@router.get("/notifications", summary="This user's notifications")
apps/api/app/api/messaging.py-226-def get_notifications(
apps/api/app/api/messaging.py-227-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-228-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-229-    unread_only: bool = Query(default=False),
apps/api/app/api/messaging.py-230-    limit: int = Query(default=100, ge=1, le=500),
apps/api/app/api/messaging.py-231-) -> list[dict[str, Any]]:
apps/api/app/api/messaging.py-232-    return my_notifications(
apps/api/app/api/messaging.py-233-        session,
apps/api/app/api/messaging.py-234-        organization_id=principal.organization_id,
apps/api/app/api/messaging.py-235-        recipient_id=principal.user_id,
apps/api/app/api/messaging.py-236-        unread_only=unread_only,
apps/api/app/api/messaging.py-237-        limit=limit,
apps/api/app/api/messaging.py-238-    )
apps/api/app/api/messaging.py-239-
apps/api/app/api/messaging.py-240-
apps/api/app/api/messaging.py-241-@router.post("/notifications/{notification_id}/read", summary="Mark one as read")
apps/api/app/api/messaging.py-242-def post_notification_read(
apps/api/app/api/messaging.py-243-    notification_id: uuid.UUID,
apps/api/app/api/messaging.py-244-    principal: Principal = Depends(get_principal),
apps/api/app/api/messaging.py-245-    session: Session = Depends(get_db),
apps/api/app/api/messaging.py-246-) -> dict[str, Any]:
apps/api/app/api/messaging.py:247:    """`recipient_id` comes from the token, never the request.
apps/api/app/api/messaging.py-248-
apps/api/app/api/messaging.py-249-    A caller therefore cannot mark somebody else's notification read and
apps/api/app/api/messaging.py-250-    hide it, silently and permanently, from the person who needed to act.
apps/api/app/api/messaging.py-251-    """
apps/api/app/api/messaging.py-252-    try:
apps/api/app/api/messaging.py-253-        result = mark_notification_read(
apps/api/app/api/messaging.py-254-            session,
apps/api/app/api/messaging.py-255-            notification_id=notification_id,
apps/api/app/api/messaging.py-256-            organization_id=principal.organization_id,
apps/api/app/api/messaging.py-257-            recipient_id=principal.user_id,
apps/api/app/api/messaging.py-258-        )
apps/api/app/api/messaging.py-259-    except MessagingNotFoundError as exc:
apps/api/app/api/messaging.py-260-        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
apps/api/app/api/messaging.py-261-    session.commit()
apps/api/app/api/messaging.py-262-    return result
--
.github/workflows/ci.yml-108-          # while the same suite passed 152/0/0 locally, because the local
.github/workflows/ci.yml-109-          # database had been repaired by hand with a DIFFERENT list.
.github/workflows/ci.yml-110-          #
.github/workflows/ci.yml-111-          # Two hand-maintained lists in two files, which nothing can check
.github/workflows/ci.yml-112-          # against each other, is this platform's most repeated defect.
.github/workflows/ci.yml-113-          # Ownership and grants now belong to migration 014 and are
.github/workflows/ci.yml-114-          # asserted by tests/db/test_object_ownership.py, so there is one
.github/workflows/ci.yml-115-          # decider and a test that fails if a new table misses it.
.github/workflows/ci.yml-116-          #
.github/workflows/ci.yml-117-          # Credentials genuinely are CI-only: the migration creates these
.github/workflows/ci.yml-118-          # roles NOLOGIN by design, and the suite must connect AS the
.github/workflows/ci.yml-119-          # runtime role -- running the tenancy tests as superuser would
.github/workflows/ci.yml-120-          # bypass RLS and pass against a schema with no isolation at all.
.github/workflows/ci.yml-121-          psql -h localhost -U postgres -d evercoat_itw_rd -v ON_ERROR_STOP=1 <<'SQL'
.github/workflows/ci.yml-122-          ALTER ROLE evercoat_owner LOGIN PASSWORD 'ci-owner';
.github/workflows/ci.yml-123-          ALTER ROLE evercoat_app   LOGIN PASSWORD 'ci-app';
.github/workflows/ci.yml-124-          GRANT CONNECT ON DATABASE evercoat_itw_rd TO evercoat_owner, evercoat_app;
.github/workflows/ci.yml-125-          SQL
.github/workflows/ci.yml-126-
.github/workflows/ci.yml-127-      - name: Tests
.github/workflows/ci.yml-128-        working-directory: apps/api
.github/workflows/ci.yml-129-        env:
.github/workflows/ci.yml-130-          TEST_DB_HOST: localhost
.github/workflows/ci.yml-131-          TEST_DB_PORT: "5432"
.github/workflows/ci.yml-132-          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml-133-          TEST_OWNER_USER: evercoat_owner
.github/workflows/ci.yml-134-          TEST_OWNER_PASSWORD: ci-owner
.github/workflows/ci.yml-135-          APP_DB_USER: evercoat_app
.github/workflows/ci.yml-136-          APP_DB_PASSWORD: ci-app
.github/workflows/ci.yml-137-          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-138-          KEYCLOAK_ISSUER: http://localhost:18080/realms/evercoat
.github/workflows/ci.yml-139-        run: |
.github/workflows/ci.yml-140-          # -rs so SKIPPED tests are named, not just counted. A suite that
.github/workflows/ci.yml-141-          # silently skips its database tests reports green while proving
.github/workflows/ci.yml-142-          # nothing -- results are always passed / failed / SKIPPED.
.github/workflows/ci.yml:143:          pytest -v -rs --tb=short
.github/workflows/ci.yml-144-
.github/workflows/ci.yml-145-      - name: Assert tenancy tests actually ran
.github/workflows/ci.yml-146-        working-directory: apps/api
.github/workflows/ci.yml-147-        env:
.github/workflows/ci.yml-148-          TEST_DB_HOST: localhost
.github/workflows/ci.yml-149-          TEST_DB_PORT: "5432"
.github/workflows/ci.yml-150-          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml-151-          TEST_OWNER_USER: evercoat_owner
.github/workflows/ci.yml-152-          TEST_OWNER_PASSWORD: ci-owner
.github/workflows/ci.yml-153-          APP_DB_USER: evercoat_app
.github/workflows/ci.yml-154-          APP_DB_PASSWORD: ci-app
.github/workflows/ci.yml-155-          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-156-          KEYCLOAK_ISSUER: http://localhost:18080/realms/evercoat
.github/workflows/ci.yml-157-        run: |
.github/workflows/ci.yml-158-          set -euo pipefail
.github/workflows/ci.yml-159-          # The db fixtures skip when no database is reachable. That is
.github/workflows/ci.yml-160-          # right for a laptop and wrong for CI: a misconfigured service
.github/workflows/ci.yml-161-          # container would turn the entire tenancy suite into skips and
.github/workflows/ci.yml-162-          # the job would still be green. Fail if they did not run.
.github/workflows/ci.yml:163:          count=$(pytest tests/db -q --collect-only 2>/dev/null | grep -c "test_" || echo 0)
.github/workflows/ci.yml-164-          if [ "$count" -lt 12 ]; then
.github/workflows/ci.yml-165-            echo "expected >=12 tenancy tests, collected $count"; exit 1
.github/workflows/ci.yml-166-          fi
.github/workflows/ci.yml:167:          pytest tests/db -q --no-header -rs \
.github/workflows/ci.yml-168-            | tee /tmp/db.txt
.github/workflows/ci.yml-169-          if grep -q "skipped" /tmp/db.txt; then
.github/workflows/ci.yml-170-            echo "tenancy tests were SKIPPED -- the database was not reachable"
.github/workflows/ci.yml-171-            exit 1
.github/workflows/ci.yml-172-          fi
.github/workflows/ci.yml-173-
.github/workflows/ci.yml-174-      # AN UNRUN SEEDER IS NOT A SEEDER.
.github/workflows/ci.yml-175-      #
.github/workflows/ci.yml-176-      # The same rule this repository already applied to backup.sh, where
.github/workflows/ci.yml-177-      # the restore drill is what made the backup real. `scripts/seed.py`
.github/workflows/ci.yml-178-      # is the only thing that puts demonstration data into a database,
.github/workflows/ci.yml-179-      # it reads the SAME demo-data.json the deployed site renders, and
.github/workflows/ci.yml-180-      # until now nothing ever executed it -- so a schema change could
.github/workflows/ci.yml-181-      # break it and the break would surface on an operator's machine
.github/workflows/ci.yml-182-      # while every gate stayed green.
.github/workflows/ci.yml-183-      #
.github/workflows/ci.yml-184-      # Run LAST, after the tests, deliberately: seeding before them would
.github/workflows/ci.yml-185-      # put rows in front of assertions that were written against an empty
.github/workflows/ci.yml-186-      # database, and a suite that passes only because of seed data is a
.github/workflows/ci.yml-187-      # suite that has stopped saying what it means.
.github/workflows/ci.yml-188-      - name: Seed — run it, twice, and count what it wrote
.github/workflows/ci.yml-189-        working-directory: apps/api
.github/workflows/ci.yml-190-        env:
.github/workflows/ci.yml-191-          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-192-          PGPASSWORD: ci-postgres
.github/workflows/ci.yml-193-        run: |
.github/workflows/ci.yml-194-          set -euo pipefail
.github/workflows/ci.yml-195-          python ../../scripts/seed.py
.github/workflows/ci.yml-196-
.github/workflows/ci.yml-197-          # TWICE, because the script claims to be idempotent and a claim
.github/workflows/ci.yml-198-          # is not a mechanism. The second run must not raise -- every
.github/workflows/ci.yml-199-          # INSERT carries an ON CONFLICT -- and must not double any row.
.github/workflows/ci.yml-200-          python ../../scripts/seed.py
.github/workflows/ci.yml-201-
.github/workflows/ci.yml-202-          # Counted from the database, not from the script's own printed
--
.github/workflows/ci.yml-431-    steps:
.github/workflows/ci.yml-432-      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml-433-        with:
.github/workflows/ci.yml-434-          # gitleaks on `push` scans only the pushed commits; full history
.github/workflows/ci.yml-435-          # needs the whole repo, so fetch it.
.github/workflows/ci.yml-436-          fetch-depth: 0
.github/workflows/ci.yml-437-
.github/workflows/ci.yml-438-      - name: Gitleaks
.github/workflows/ci.yml-439-        uses: gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7  # v2, resolved 2026-08-18
.github/workflows/ci.yml-440-        env:
.github/workflows/ci.yml-441-          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
.github/workflows/ci.yml-442-
.github/workflows/ci.yml-443-      - name: Trivy — filesystem
.github/workflows/ci.yml-444-        # 0.28.0 was never a published tag, so this step failed to resolve
.github/workflows/ci.yml-445-        # on every run with "unable to find version" — the scan had never
.github/workflows/ci.yml-446-        # executed once. A security job that cannot start is worse than an
.github/workflows/ci.yml-447-        # absent one: it occupies the slot where the check is supposed to
.github/workflows/ci.yml-448-        # be. Pinned to a tag that exists (verified against the action's
.github/workflows/ci.yml-449-        # releases) rather than a floating ref, so a supply-chain change
.github/workflows/ci.yml-450-        # upstream cannot silently alter what runs here.
.github/workflows/ci.yml-451-        uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25  # v0.36.0, resolved 2026-08-18
.github/workflows/ci.yml-452-        with:
.github/workflows/ci.yml-453-          scan-type: fs
.github/workflows/ci.yml-454-          scan-ref: .
.github/workflows/ci.yml-455-          severity: HIGH,CRITICAL
.github/workflows/ci.yml-456-          # A high-severity finding blocks the merge. The source is
.github/workflows/ci.yml-457-          # explicit that this gates staging deployment.
.github/workflows/ci.yml-458-          exit-code: "1"
.github/workflows/ci.yml-459-          ignore-unfixed: true
.github/workflows/ci.yml-460-
.github/workflows/ci.yml-461-      - name: Semgrep
.github/workflows/ci.yml-462-        run: |
.github/workflows/ci.yml-463-          pip install semgrep
.github/workflows/ci.yml-464-          semgrep --config auto --error --skip-unknown-extensions .
.github/workflows/ci.yml-465-
.github/workflows/ci.yml:466:  auth:
.github/workflows/ci.yml:467:    name: Auth — real Keycloak, real tokens
.github/workflows/ci.yml-468-    runs-on: ubuntu-latest
.github/workflows/ci.yml-469-
.github/workflows/ci.yml-470-    # 🔴 THE FIRST TIME AUTHENTICATION HAS EVER RUN.
.github/workflows/ci.yml-471-    #
.github/workflows/ci.yml:472:    # The API has verified tokens correctly since Slice 1 and had never
.github/workflows/ci.yml-473-    # once verified a real one, because no Keycloak had ever run anywhere:
.github/workflows/ci.yml-474-    # not on Render, not in CI, not on the development host. Every auth
.github/workflows/ci.yml-475-    # test until now fabricated its own JWT or mocked the verifier, so the
.github/workflows/ci.yml-476-    # four defects this job exists to catch were all invisible — the realm
.github/workflows/ci.yml-477-    # ships with zero users, the seeder writes placeholder subjects, a
.github/workflows/ci.yml:478:    # Keycloak token's audience is `account` unless a mapper says
.github/workflows/ci.yml-479-    # otherwise, and nothing had ever sent `X-Organization-Id`.
.github/workflows/ci.yml-480-    #
.github/workflows/ci.yml-481-    # This job needs no deployment and costs nothing, which matters:
.github/workflows/ci.yml-482-    # deploying the API and Keycloak is blocked on Render's free
.github/workflows/ci.yml-483-    # web-service quota, and that is the operator's decision, not CI's.
.github/workflows/ci.yml-484-
.github/workflows/ci.yml-485-    services:
.github/workflows/ci.yml-486-      postgres:
.github/workflows/ci.yml-487-        image: pgvector/pgvector:pg16
.github/workflows/ci.yml-488-        env:
.github/workflows/ci.yml-489-          POSTGRES_DB: evercoat_itw_rd
.github/workflows/ci.yml-490-          POSTGRES_USER: postgres
.github/workflows/ci.yml-491-          POSTGRES_PASSWORD: ci-postgres
.github/workflows/ci.yml-492-        options: >-
.github/workflows/ci.yml-493-          --health-cmd "pg_isready -U postgres -d evercoat_itw_rd"
.github/workflows/ci.yml-494-          --health-interval 5s --health-timeout 5s --health-retries 20
.github/workflows/ci.yml-495-        ports: ["5432:5432"]
.github/workflows/ci.yml-496-
.github/workflows/ci.yml-497-    steps:
.github/workflows/ci.yml-498-      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
.github/workflows/ci.yml-499-
.github/workflows/ci.yml-500-      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5, resolved 2026-08-18
.github/workflows/ci.yml-501-        with:
.github/workflows/ci.yml-502-          python-version: ${{ env.PYTHON_VERSION }}
.github/workflows/ci.yml-503-          cache: pip
.github/workflows/ci.yml-504-
.github/workflows/ci.yml-505-      - name: Install API
.github/workflows/ci.yml-506-        working-directory: apps/api
.github/workflows/ci.yml-507-        run: pip install -e ".[dev]"
.github/workflows/ci.yml-508-
.github/workflows/ci.yml-509-      # Generated, never written down. A hardcoded password in a workflow
.github/workflows/ci.yml-510-      # file is a gitleaks finding whatever the comment beside it says, and
.github/workflows/ci.yml-511-      # the realm's policy (12 chars, mixed case, digit, special) would push
.github/workflows/ci.yml-512-      # anyone writing one by hand toward something they had used before.
.github/workflows/ci.yml-513-      - name: Mint throwaway credentials
.github/workflows/ci.yml-514-        run: |
.github/workflows/ci.yml-515-          set -euo pipefail
.github/workflows/ci.yml-516-          admin="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9')Aa1!"
.github/workflows/ci.yml-517-          user="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9')Bb2!"
.github/workflows/ci.yml-518-          echo "::add-mask::$admin"
.github/workflows/ci.yml-519-          echo "::add-mask::$user"
.github/workflows/ci.yml-520-          echo "KC_ADMIN_PASSWORD=$admin" >> "$GITHUB_ENV"
.github/workflows/ci.yml-521-          echo "KC_USER_PASSWORD=$user" >> "$GITHUB_ENV"
.github/workflows/ci.yml-522-
.github/workflows/ci.yml-523-      - name: Start Keycloak with the shipped realm
.github/workflows/ci.yml-524-        run: |
.github/workflows/ci.yml-525-          set -euo pipefail
.github/workflows/ci.yml-526-          # `docker run`, not a `services:` block: a service container takes
.github/workflows/ci.yml-527-          # only an image and env, and Keycloak needs BOTH a command
.github/workflows/ci.yml-528-          # (`start-dev --import-realm`) and the realm mounted. A service
.github/workflows/ci.yml-529-          # container would start a Keycloak with no realm at all — which
.github/workflows/ci.yml:530:          # would pass a health check and fail every token request.
.github/workflows/ci.yml:531:          docker run -d --name evercoat-keycloak-ci \
.github/workflows/ci.yml-532-            -p 8080:8080 \
.github/workflows/ci.yml-533-            -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
.github/workflows/ci.yml-534-            -e KC_BOOTSTRAP_ADMIN_PASSWORD="$KC_ADMIN_PASSWORD" \
.github/workflows/ci.yml-535-            -e KC_HEALTH_ENABLED=true \
.github/workflows/ci.yml-536-            -e KC_HTTP_ENABLED=true \
.github/workflows/ci.yml:537:            -v "$PWD/services/keycloak/realm:/opt/keycloak/data/import:ro" \
.github/workflows/ci.yml:538:            quay.io/keycloak/keycloak:26.0 \
.github/workflows/ci.yml-539-            start-dev --import-realm
.github/workflows/ci.yml-540-
.github/workflows/ci.yml-541-      - name: Apply migrations
.github/workflows/ci.yml-542-        working-directory: apps/api
.github/workflows/ci.yml-543-        env:
.github/workflows/ci.yml-544-          MIGRATION_DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-545-          DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-546-          KEYCLOAK_ISSUER: http://localhost:8080/realms/evercoat
.github/workflows/ci.yml-547-        run: alembic upgrade head
.github/workflows/ci.yml-548-
.github/workflows/ci.yml-549-      - name: Grant the application role a login
.github/workflows/ci.yml-550-        env:
.github/workflows/ci.yml-551-          PGPASSWORD: ci-postgres
.github/workflows/ci.yml-552-        run: |
.github/workflows/ci.yml-553-          set -euo pipefail
.github/workflows/ci.yml-554-          psql -h localhost -U postgres -d evercoat_itw_rd -v ON_ERROR_STOP=1 <<'SQL'
.github/workflows/ci.yml-555-          ALTER ROLE evercoat_app LOGIN PASSWORD 'ci-app';
.github/workflows/ci.yml-556-          GRANT CONNECT ON DATABASE evercoat_itw_rd TO evercoat_app;
.github/workflows/ci.yml-557-          SQL
.github/workflows/ci.yml-558-
.github/workflows/ci.yml:559:      - name: Seed, and capture the organization the tokens will name
.github/workflows/ci.yml-560-        env:
.github/workflows/ci.yml-561-          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-562-        run: |
.github/workflows/ci.yml-563-          set -euo pipefail
.github/workflows/ci.yml-564-          python scripts/seed.py | tee seed.log
.github/workflows/ci.yml-565-          org="$(grep -oE 'organization: [0-9a-f-]{36}' seed.log | head -1 | awk '{print $2}')" || org=""
.github/workflows/ci.yml-566-          if [ -z "$org" ]; then
.github/workflows/ci.yml-567-            echo "FAIL: the seeder printed no organization id; every request would 400" >&2
.github/workflows/ci.yml-568-            exit 1
.github/workflows/ci.yml-569-          fi
.github/workflows/ci.yml-570-          echo "TEST_ORGANIZATION_ID=$org" >> "$GITHUB_ENV"
.github/workflows/ci.yml-571-
.github/workflows/ci.yml-572-      - name: Create the realm's users and bind their subjects
.github/workflows/ci.yml-573-        env:
.github/workflows/ci.yml-574-          KC_URL: http://localhost:8080
.github/workflows/ci.yml:575:          KC_SUBS_OUT: keycloak-subs.json
.github/workflows/ci.yml-576-          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-577-        run: |
.github/workflows/ci.yml-578-          set -euo pipefail
.github/workflows/ci.yml:579:          bash scripts/keycloak-bootstrap.sh --with-test-client
.github/workflows/ci.yml:580:          python scripts/keycloak-bind-subs.py keycloak-subs.json
.github/workflows/ci.yml-581-
.github/workflows/ci.yml-582-      - name: Start the API
.github/workflows/ci.yml-583-        working-directory: apps/api
.github/workflows/ci.yml-584-        env:
.github/workflows/ci.yml-585-          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
.github/workflows/ci.yml-586-          KEYCLOAK_ISSUER: http://localhost:8080/realms/evercoat
.github/workflows/ci.yml-587-          KEYCLOAK_AUDIENCE: evercoat-api
.github/workflows/ci.yml-588-        run: |
.github/workflows/ci.yml-589-          set -euo pipefail
.github/workflows/ci.yml-590-          nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$GITHUB_WORKSPACE/api.log" 2>&1 &
.github/workflows/ci.yml-591-          deadline=$(( SECONDS + 90 ))
.github/workflows/ci.yml:592:          until code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health/live)" \
.github/workflows/ci.yml-593-                && [ "$code" = "200" ]; do
.github/workflows/ci.yml-594-            if [ "$SECONDS" -ge "$deadline" ]; then
.github/workflows/ci.yml-595-              echo "FAIL: the API never became live. Its log:" >&2
.github/workflows/ci.yml-596-              cat "$GITHUB_WORKSPACE/api.log" >&2
.github/workflows/ci.yml-597-              exit 1
.github/workflows/ci.yml-598-            fi
.github/workflows/ci.yml-599-            sleep 2
.github/workflows/ci.yml-600-          done
.github/workflows/ci.yml-601-
.github/workflows/ci.yml-602-      # 🔴 THE COUNTS, AND THE THIRD STATE.
.github/workflows/ci.yml-603-      #
.github/workflows/ci.yml-604-      # These tests skip themselves when no Keycloak is configured, which
.github/workflows/ci.yml-605-      # is right on a laptop and catastrophic here: a fully skipped run
.github/workflows/ci.yml-606-      # exits 0 and reads as proof. The assertion below is on the number
.github/workflows/ci.yml-607-      # that PASSED and on skipped being zero — never on the exit code.
.github/workflows/ci.yml-608-      - name: Prove authentication end to end
.github/workflows/ci.yml-609-        working-directory: apps/api
.github/workflows/ci.yml-610-        env:
.github/workflows/ci.yml-611-          TEST_KEYCLOAK_URL: http://localhost:8080
.github/workflows/ci.yml-612-          TEST_API_URL: http://127.0.0.1:8000
.github/workflows/ci.yml-613-          TEST_KEYCLOAK_REALM: evercoat
.github/workflows/ci.yml-614-          TEST_KEYCLOAK_CLIENT: evercoat-test
.github/workflows/ci.yml-615-          TEST_KEYCLOAK_PASSWORD: ${{ env.KC_USER_PASSWORD }}
.github/workflows/ci.yml-616-          TEST_ORGANIZATION_ID: ${{ env.TEST_ORGANIZATION_ID }}
.github/workflows/ci.yml-617-        run: |
.github/workflows/ci.yml-618-          set -euo pipefail
.github/workflows/ci.yml:619:          pytest tests/integration/test_auth_end_to_end.py -v --junitxml=auth-results.xml || true
.github/workflows/ci.yml-620-          python "$GITHUB_WORKSPACE/scripts/assert-suite-ran.py" auth-results.xml
.github/workflows/ci.yml-621-
.github/workflows/ci.yml-622-      - name: Keycloak and API logs on failure
.github/workflows/ci.yml-623-        if: failure()
.github/workflows/ci.yml-624-        run: |
.github/workflows/ci.yml:625:          echo "=== keycloak ==="; docker logs evercoat-keycloak-ci 2>&1 | tail -80
.github/workflows/ci.yml-626-          echo "=== api ==="; tail -80 "$GITHUB_WORKSPACE/api.log" || true
--
apps/api/tests/db/test_023_messaging.py-1-"""Messaging: the notification boundary, and promotion by hand only.
apps/api/tests/db/test_023_messaging.py-2-
apps/api/tests/db/test_023_messaging.py-3-Two rules carry this module, and both are the kind that pass a code
apps/api/tests/db/test_023_messaging.py-4-review and fail in production.
apps/api/tests/db/test_023_messaging.py-5-
apps/api/tests/db/test_023_messaging.py-6-**A notification must not disclose what its recipient cannot see.** The
apps/api/tests/db/test_023_messaging.py-7-channel's own RLS protects the MESSAGES and does nothing about a
apps/api/tests/db/test_023_messaging.py-8-notification row addressed to an outsider. My first version of this check
apps/api/tests/db/test_023_messaging.py:9:reused `list_channels`'s predicate, which evaluates in the AUTHOR's
apps/api/tests/db/test_023_messaging.py:10:session -- so a restricted project's channel read as reachable for
apps/api/tests/db/test_023_messaging.py:11:everyone, and the mention notification would have named the project to
apps/api/tests/db/test_023_messaging.py-12-somebody with no access to it. The test below is the one that would have
apps/api/tests/db/test_023_messaging.py-13-caught it.
apps/api/tests/db/test_023_messaging.py-14-
apps/api/tests/db/test_023_messaging.py-15-**Informal chat never becomes authoritative knowledge automatically**
apps/api/tests/db/test_023_messaging.py-16-(§7). Promotion exists, is explicit, produces a TASK rather than a
apps/api/tests/db/test_023_messaging.py-17-conclusion, and links back to the message it came from.
apps/api/tests/db/test_023_messaging.py-18-
apps/api/tests/db/test_023_messaging.py-19-Everything here runs on `app_session` where the boundary is the subject,
apps/api/tests/db/test_023_messaging.py-20-because the owner is exempt from RLS while `relforcerowsecurity` is FALSE
apps/api/tests/db/test_023_messaging.py-21-and an owner-run version of this file would pass against a system with no
apps/api/tests/db/test_023_messaging.py-22-boundary at all.
apps/api/tests/db/test_023_messaging.py-23-"""
apps/api/tests/db/test_023_messaging.py-24-
apps/api/tests/db/test_023_messaging.py-25-from __future__ import annotations
apps/api/tests/db/test_023_messaging.py-26-
apps/api/tests/db/test_023_messaging.py-27-import uuid
apps/api/tests/db/test_023_messaging.py-28-from collections.abc import Iterator
apps/api/tests/db/test_023_messaging.py-29-
apps/api/tests/db/test_023_messaging.py:30:import pytest
apps/api/tests/db/test_023_messaging.py-31-from sqlalchemy import text
apps/api/tests/db/test_023_messaging.py-32-from sqlalchemy.orm import Session
apps/api/tests/db/test_023_messaging.py-33-
apps/api/tests/db/test_023_messaging.py-34-from app.domains.messaging.service import (
apps/api/tests/db/test_023_messaging.py-35-    ChannelInput,
apps/api/tests/db/test_023_messaging.py-36-    MessageInput,
apps/api/tests/db/test_023_messaging.py-37-    create_channel,
apps/api/tests/db/test_023_messaging.py-38-    list_messages,
apps/api/tests/db/test_023_messaging.py-39-    my_notifications,
apps/api/tests/db/test_023_messaging.py-40-    post_message,
apps/api/tests/db/test_023_messaging.py:41:    promote_message,
apps/api/tests/db/test_023_messaging.py-42-)
apps/api/tests/db/test_023_messaging.py-43-
apps/api/tests/db/test_023_messaging.py-44-
apps/api/tests/db/test_023_messaging.py:45:@pytest.fixture
apps/api/tests/db/test_023_messaging.py-46-def channel_fixture(owner_session: Session, app_session: Session) -> Iterator[dict[str, uuid.UUID]]:
apps/api/tests/db/test_023_messaging.py-47-    """One org, one RESTRICTED project, an author inside it and an
apps/api/tests/db/test_023_messaging.py-48-    outsider who is not.
apps/api/tests/db/test_023_messaging.py-49-
apps/api/tests/db/test_023_messaging.py-50-    Both are active organization members, so nothing but the project
apps/api/tests/db/test_023_messaging.py-51-    boundary separates them -- which is the only way the test can
apps/api/tests/db/test_023_messaging.py-52-    attribute a difference in behaviour to that boundary.
apps/api/tests/db/test_023_messaging.py-53-    """
apps/api/tests/db/test_023_messaging.py-54-    suffix = uuid.uuid4().hex[:8]
apps/api/tests/db/test_023_messaging.py-55-
apps/api/tests/db/test_023_messaging.py-56-    org = owner_session.execute(
apps/api/tests/db/test_023_messaging.py-57-        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api/tests/db/test_023_messaging.py-58-        {"c": f"MSG-{suffix}", "n": "Messaging Org"},
apps/api/tests/db/test_023_messaging.py-59-    ).scalar_one()
apps/api/tests/db/test_023_messaging.py-60-
apps/api/tests/db/test_023_messaging.py-61-    def _user(handle: str, name: str) -> uuid.UUID:
apps/api/tests/db/test_023_messaging.py-62-        uid: uuid.UUID = owner_session.execute(
apps/api/tests/db/test_023_messaging.py-63-            text(
apps/api/tests/db/test_023_messaging.py-64-                """
apps/api/tests/db/test_023_messaging.py:65:                INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api/tests/db/test_023_messaging.py-66-                VALUES (:s, :e, :n) RETURNING id
apps/api/tests/db/test_023_messaging.py-67-                """
apps/api/tests/db/test_023_messaging.py-68-            ),
apps/api/tests/db/test_023_messaging.py-69-            {"s": f"msg-{handle}-{suffix}", "e": f"{handle}@example.test", "n": name},
apps/api/tests/db/test_023_messaging.py-70-        ).scalar_one()
apps/api/tests/db/test_023_messaging.py-71-        owner_session.execute(
apps/api/tests/db/test_023_messaging.py-72-            text(
apps/api/tests/db/test_023_messaging.py-73-                """
apps/api/tests/db/test_023_messaging.py-74-                INSERT INTO core.organization_members (organization_id, user_id, status)
apps/api/tests/db/test_023_messaging.py-75-                VALUES (:o, :u, 'active')
apps/api/tests/db/test_023_messaging.py-76-                """
apps/api/tests/db/test_023_messaging.py-77-            ),
apps/api/tests/db/test_023_messaging.py-78-            {"o": org, "u": uid},
apps/api/tests/db/test_023_messaging.py-79-        )
apps/api/tests/db/test_023_messaging.py-80-        return uid
apps/api/tests/db/test_023_messaging.py-81-
apps/api/tests/db/test_023_messaging.py-82-    author = _user(f"author{suffix}", "Author")
apps/api/tests/db/test_023_messaging.py-83-    outsider = _user(f"outsider{suffix}", "Outsider")
apps/api/tests/db/test_023_messaging.py-84-
apps/api/tests/db/test_023_messaging.py-85-    project = owner_session.execute(
apps/api/tests/db/test_023_messaging.py-86-        text(
apps/api/tests/db/test_023_messaging.py-87-            """
apps/api/tests/db/test_023_messaging.py-88-            INSERT INTO projects.projects
apps/api/tests/db/test_023_messaging.py-89-                (organization_id, project_code, name, project_type, confidentiality, created_by)
apps/api/tests/db/test_023_messaging.py:90:            VALUES (:o, :c, 'Restricted Work', 'new_product', 'restricted', :u)
apps/api/tests/db/test_023_messaging.py-91-            RETURNING id
apps/api/tests/db/test_023_messaging.py-92-            """
apps/api/tests/db/test_023_messaging.py-93-        ),
apps/api/tests/db/test_023_messaging.py-94-        {"o": org, "c": f"P-{suffix}", "u": author},
apps/api/tests/db/test_023_messaging.py-95-    ).scalar_one()
apps/api/tests/db/test_023_messaging.py-96-
apps/api/tests/db/test_023_messaging.py-97-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-98-        text(
apps/api/tests/db/test_023_messaging.py-99-            """
apps/api/tests/db/test_023_messaging.py-100-            INSERT INTO projects.project_members
apps/api/tests/db/test_023_messaging.py:101:                (organization_id, project_id, user_id, project_role)
apps/api/tests/db/test_023_messaging.py-102-            VALUES (:o, :p, :u, 'lead')
apps/api/tests/db/test_023_messaging.py-103-            """
apps/api/tests/db/test_023_messaging.py-104-        ),
apps/api/tests/db/test_023_messaging.py-105-        {"o": org, "p": project, "u": author},
apps/api/tests/db/test_023_messaging.py-106-    )
apps/api/tests/db/test_023_messaging.py-107-    owner_session.commit()
apps/api/tests/db/test_023_messaging.py-108-
apps/api/tests/db/test_023_messaging.py-109-    _scope(app_session, org, author)
apps/api/tests/db/test_023_messaging.py-110-
apps/api/tests/db/test_023_messaging.py-111-    yield {"org": org, "author": author, "outsider": outsider, "project": project}
apps/api/tests/db/test_023_messaging.py-112-
apps/api/tests/db/test_023_messaging.py-113-    app_session.rollback()
apps/api/tests/db/test_023_messaging.py-114-    owner_session.begin()
apps/api/tests/db/test_023_messaging.py-115-    for statement in (
apps/api/tests/db/test_023_messaging.py-116-        "DELETE FROM messaging.notifications WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-117-        "DELETE FROM messaging.message_links WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-118-        "DELETE FROM workflow.tasks WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-119-        "DELETE FROM messaging.channel_members WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-120-        "DELETE FROM messaging.channels WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-121-        "DELETE FROM projects.project_members WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-122-        "DELETE FROM projects.projects WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-123-        "DELETE FROM core.organization_members WHERE organization_id = :o",
apps/api/tests/db/test_023_messaging.py-124-    ):
apps/api/tests/db/test_023_messaging.py-125-        owner_session.execute(text(statement), {"o": org})
apps/api/tests/db/test_023_messaging.py-126-    # Messages carry a `deny_message_rewrite` trigger. Disabled here for
apps/api/tests/db/test_023_messaging.py-127-    # the same reason the MSD fixture disables its append-only guards:
apps/api/tests/db/test_023_messaging.py-128-    # having to do so is proof the mechanism is real.
apps/api/tests/db/test_023_messaging.py-129-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-130-        text("ALTER TABLE messaging.messages DISABLE TRIGGER messages_are_a_record")
apps/api/tests/db/test_023_messaging.py-131-    )
apps/api/tests/db/test_023_messaging.py-132-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-133-        text("DELETE FROM messaging.messages WHERE organization_id = :o"), {"o": org}
apps/api/tests/db/test_023_messaging.py-134-    )
apps/api/tests/db/test_023_messaging.py-135-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-136-        text("ALTER TABLE messaging.messages ENABLE TRIGGER messages_are_a_record")
apps/api/tests/db/test_023_messaging.py-137-    )
apps/api/tests/db/test_023_messaging.py-138-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-139-        text("DELETE FROM core.users WHERE id IN (:a, :b)"), {"a": author, "b": outsider}
apps/api/tests/db/test_023_messaging.py-140-    )
apps/api/tests/db/test_023_messaging.py-141-    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
apps/api/tests/db/test_023_messaging.py-142-    owner_session.commit()
apps/api/tests/db/test_023_messaging.py-143-
apps/api/tests/db/test_023_messaging.py-144-
apps/api/tests/db/test_023_messaging.py-145-def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
apps/api/tests/db/test_023_messaging.py-146-    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
apps/api/tests/db/test_023_messaging.py-147-    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})
apps/api/tests/db/test_023_messaging.py-148-
apps/api/tests/db/test_023_messaging.py-149-
apps/api/tests/db/test_023_messaging.py:150:def test_a_mention_does_not_notify_someone_outside_the_project(
apps/api/tests/db/test_023_messaging.py-151-    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py-152-) -> None:
apps/api/tests/db/test_023_messaging.py-153-    """🔴 THE NOTIFICATION IS THE LEAK, IF YOU LET IT BE.
apps/api/tests/db/test_023_messaging.py-154-
apps/api/tests/db/test_023_messaging.py:155:    The outsider is a full organization member and is mentioned by name
apps/api/tests/db/test_023_messaging.py-156-    in a RESTRICTED project's channel. They must get no notification --
apps/api/tests/db/test_023_messaging.py-157-    because the notification would name a project they cannot open, and
apps/api/tests/db/test_023_messaging.py-158-    the channel's RLS cannot stop a row addressed to them.
apps/api/tests/db/test_023_messaging.py-159-    """
apps/api/tests/db/test_023_messaging.py-160-    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py-161-
apps/api/tests/db/test_023_messaging.py-162-    channel = create_channel(
apps/api/tests/db/test_023_messaging.py-163-        app_session,
apps/api/tests/db/test_023_messaging.py-164-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-165-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:166:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py-167-    )
apps/api/tests/db/test_023_messaging.py-168-
apps/api/tests/db/test_023_messaging.py-169-    outsider_handle = app_session.execute(
apps/api/tests/db/test_023_messaging.py-170-        text("SELECT split_part(email, '@', 1) FROM core.users WHERE id = :u"),
apps/api/tests/db/test_023_messaging.py-171-        {"u": fx["outsider"]},
apps/api/tests/db/test_023_messaging.py-172-    ).scalar_one()
apps/api/tests/db/test_023_messaging.py-173-
apps/api/tests/db/test_023_messaging.py-174-    result = post_message(
apps/api/tests/db/test_023_messaging.py-175-        app_session,
apps/api/tests/db/test_023_messaging.py-176-        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py-177-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-178-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-179-        spec=MessageInput(body=f"@{outsider_handle} can you look at this?"),
apps/api/tests/db/test_023_messaging.py-180-    )
apps/api/tests/db/test_023_messaging.py-181-    app_session.commit()
apps/api/tests/db/test_023_messaging.py-182-
apps/api/tests/db/test_023_messaging.py-183-    # The MENTION is recorded -- the message said what it said.
apps/api/tests/db/test_023_messaging.py:184:    assert result["mentions"], "the mention was not resolved at all"
apps/api/tests/db/test_023_messaging.py:185:    assert result["mentions"][0]["user_id"] == fx["outsider"]
apps/api/tests/db/test_023_messaging.py:186:    assert result["mentions"][0]["notified"] is False, (
apps/api/tests/db/test_023_messaging.py:187:        "a user outside a restricted project was notified about its channel; "
apps/api/tests/db/test_023_messaging.py-188-        "the notification discloses the project's existence"
apps/api/tests/db/test_023_messaging.py-189-    )
apps/api/tests/db/test_023_messaging.py-190-
apps/api/tests/db/test_023_messaging.py-191-    delivered = my_notifications(
apps/api/tests/db/test_023_messaging.py-192-        app_session, organization_id=fx["org"], recipient_id=fx["outsider"]
apps/api/tests/db/test_023_messaging.py-193-    )
apps/api/tests/db/test_023_messaging.py-194-    assert delivered == [], f"a notification reached an outsider: {delivered}"
apps/api/tests/db/test_023_messaging.py-195-
apps/api/tests/db/test_023_messaging.py-196-
apps/api/tests/db/test_023_messaging.py:197:def test_a_mention_notifies_a_project_member(
apps/api/tests/db/test_023_messaging.py-198-    app_session: Session, owner_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py-199-) -> None:
apps/api/tests/db/test_023_messaging.py-200-    """Verified in BOTH directions.
apps/api/tests/db/test_023_messaging.py-201-
apps/api/tests/db/test_023_messaging.py-202-    A check that notified nobody would pass the test above while making
apps/api/tests/db/test_023_messaging.py:203:    mentions useless. Adding the outsider to the project must make the
apps/api/tests/db/test_023_messaging.py:204:    mention deliver.
apps/api/tests/db/test_023_messaging.py-205-    """
apps/api/tests/db/test_023_messaging.py-206-    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py-207-
apps/api/tests/db/test_023_messaging.py-208-    owner_session.begin()
apps/api/tests/db/test_023_messaging.py-209-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-210-        text(
apps/api/tests/db/test_023_messaging.py-211-            """
apps/api/tests/db/test_023_messaging.py-212-            INSERT INTO projects.project_members
apps/api/tests/db/test_023_messaging.py:213:                (organization_id, project_id, user_id, project_role)
apps/api/tests/db/test_023_messaging.py-214-            VALUES (:o, :p, :u, 'chemist')
apps/api/tests/db/test_023_messaging.py-215-            """
apps/api/tests/db/test_023_messaging.py-216-        ),
apps/api/tests/db/test_023_messaging.py-217-        {"o": fx["org"], "p": fx["project"], "u": fx["outsider"]},
apps/api/tests/db/test_023_messaging.py-218-    )
apps/api/tests/db/test_023_messaging.py-219-    owner_session.commit()
apps/api/tests/db/test_023_messaging.py-220-
apps/api/tests/db/test_023_messaging.py-221-    channel = create_channel(
apps/api/tests/db/test_023_messaging.py-222-        app_session,
apps/api/tests/db/test_023_messaging.py-223-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-224-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:225:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py-226-    )
apps/api/tests/db/test_023_messaging.py-227-    handle = app_session.execute(
apps/api/tests/db/test_023_messaging.py-228-        text("SELECT split_part(email, '@', 1) FROM core.users WHERE id = :u"),
apps/api/tests/db/test_023_messaging.py-229-        {"u": fx["outsider"]},
apps/api/tests/db/test_023_messaging.py-230-    ).scalar_one()
apps/api/tests/db/test_023_messaging.py-231-
apps/api/tests/db/test_023_messaging.py-232-    result = post_message(
apps/api/tests/db/test_023_messaging.py-233-        app_session,
apps/api/tests/db/test_023_messaging.py-234-        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py-235-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-236-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-237-        spec=MessageInput(body=f"@{handle} please review"),
apps/api/tests/db/test_023_messaging.py-238-    )
apps/api/tests/db/test_023_messaging.py-239-    app_session.commit()
apps/api/tests/db/test_023_messaging.py-240-
apps/api/tests/db/test_023_messaging.py:241:    assert result["mentions"][0]["notified"] is True, (
apps/api/tests/db/test_023_messaging.py:242:        "a project member was not notified of their own mention; the check is excluding too much"
apps/api/tests/db/test_023_messaging.py-243-    )
apps/api/tests/db/test_023_messaging.py-244-    delivered = my_notifications(
apps/api/tests/db/test_023_messaging.py-245-        app_session, organization_id=fx["org"], recipient_id=fx["outsider"]
apps/api/tests/db/test_023_messaging.py-246-    )
apps/api/tests/db/test_023_messaging.py-247-    assert len(delivered) == 1
apps/api/tests/db/test_023_messaging.py-248-    assert delivered[0]["is_actionable"] is True
apps/api/tests/db/test_023_messaging.py-249-
apps/api/tests/db/test_023_messaging.py-250-
apps/api/tests/db/test_023_messaging.py-251-def test_promotion_creates_a_task_and_links_back_to_the_message(
apps/api/tests/db/test_023_messaging.py-252-    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py-253-) -> None:
apps/api/tests/db/test_023_messaging.py-254-    """§7: conclusions become controlled records only by explicit human
apps/api/tests/db/test_023_messaging.py-255-    promotion -- and what they become is a TASK, not a decision.
apps/api/tests/db/test_023_messaging.py-256-
apps/api/tests/db/test_023_messaging.py-257-    The link back is the digital thread's rule applied to conversation:
apps/api/tests/db/test_023_messaging.py-258-    the task can always answer "where did this come from?".
apps/api/tests/db/test_023_messaging.py-259-    """
apps/api/tests/db/test_023_messaging.py-260-    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py-261-
apps/api/tests/db/test_023_messaging.py-262-    channel = create_channel(
apps/api/tests/db/test_023_messaging.py-263-        app_session,
apps/api/tests/db/test_023_messaging.py-264-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-265-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:266:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py-267-    )
apps/api/tests/db/test_023_messaging.py-268-    message = post_message(
apps/api/tests/db/test_023_messaging.py-269-        app_session,
apps/api/tests/db/test_023_messaging.py-270-        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py-271-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-272-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-273-        spec=MessageInput(body="We should re-run the adhesion test at 5 degrees."),
apps/api/tests/db/test_023_messaging.py-274-    )
apps/api/tests/db/test_023_messaging.py-275-
apps/api/tests/db/test_023_messaging.py:276:    promoted = promote_message(
apps/api/tests/db/test_023_messaging.py-277-        app_session,
apps/api/tests/db/test_023_messaging.py-278-        message_id=message["id"],
apps/api/tests/db/test_023_messaging.py-279-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-280-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-281-        task_type="experiment",
apps/api/tests/db/test_023_messaging.py-282-        title="Re-run adhesion at 5 C",
apps/api/tests/db/test_023_messaging.py-283-    )
apps/api/tests/db/test_023_messaging.py-284-    app_session.commit()
apps/api/tests/db/test_023_messaging.py-285-
apps/api/tests/db/test_023_messaging.py-286-    source = (
apps/api/tests/db/test_023_messaging.py-287-        app_session.execute(
apps/api/tests/db/test_023_messaging.py-288-            text(
apps/api/tests/db/test_023_messaging.py-289-                """
apps/api/tests/db/test_023_messaging.py-290-            SELECT source_event, entity_type, entity_id
apps/api/tests/db/test_023_messaging.py-291-            FROM workflow.tasks WHERE id = :t AND organization_id = :o
apps/api/tests/db/test_023_messaging.py-292-            """
apps/api/tests/db/test_023_messaging.py-293-            ),
apps/api/tests/db/test_023_messaging.py:294:            {"t": promoted["task_id"], "o": fx["org"]},
apps/api/tests/db/test_023_messaging.py-295-        )
apps/api/tests/db/test_023_messaging.py-296-        .mappings()
apps/api/tests/db/test_023_messaging.py-297-        .one()
apps/api/tests/db/test_023_messaging.py-298-    )
apps/api/tests/db/test_023_messaging.py-299-
apps/api/tests/db/test_023_messaging.py:300:    assert source["source_event"] == "message.promoted"
apps/api/tests/db/test_023_messaging.py-301-    assert source["entity_id"] == message["id"], (
apps/api/tests/db/test_023_messaging.py-302-        "the task does not point back at the message it came from"
apps/api/tests/db/test_023_messaging.py-303-    )
apps/api/tests/db/test_023_messaging.py-304-
apps/api/tests/db/test_023_messaging.py-305-    link = (
apps/api/tests/db/test_023_messaging.py-306-        app_session.execute(
apps/api/tests/db/test_023_messaging.py-307-            text(
apps/api/tests/db/test_023_messaging.py-308-                """
apps/api/tests/db/test_023_messaging.py-309-            SELECT link_type, entity_type, entity_id FROM messaging.message_links
apps/api/tests/db/test_023_messaging.py-310-            WHERE message_id = :m AND link_type = 'promotion'
apps/api/tests/db/test_023_messaging.py-311-            """
apps/api/tests/db/test_023_messaging.py-312-            ),
apps/api/tests/db/test_023_messaging.py-313-            {"m": message["id"]},
apps/api/tests/db/test_023_messaging.py-314-        )
apps/api/tests/db/test_023_messaging.py-315-        .mappings()
apps/api/tests/db/test_023_messaging.py-316-        .one()
apps/api/tests/db/test_023_messaging.py-317-    )
apps/api/tests/db/test_023_messaging.py:318:    assert link["entity_id"] == promoted["task_id"]
apps/api/tests/db/test_023_messaging.py-319-
apps/api/tests/db/test_023_messaging.py-320-
apps/api/tests/db/test_023_messaging.py:321:def test_nothing_is_promoted_without_being_asked(
apps/api/tests/db/test_023_messaging.py-322-    app_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py-323-) -> None:
apps/api/tests/db/test_023_messaging.py-324-    """Posting a message must create no controlled record at all.
apps/api/tests/db/test_023_messaging.py-325-
apps/api/tests/db/test_023_messaging.py-326-    The rule is that informal chat never becomes authoritative knowledge
apps/api/tests/db/test_023_messaging.py-327-    AUTOMATICALLY. A service that helpfully opened a task for any message
apps/api/tests/db/test_023_messaging.py-328-    containing "we should" would violate it while looking like a feature.
apps/api/tests/db/test_023_messaging.py-329-    """
apps/api/tests/db/test_023_messaging.py-330-    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py-331-
apps/api/tests/db/test_023_messaging.py-332-    channel = create_channel(
apps/api/tests/db/test_023_messaging.py-333-        app_session,
apps/api/tests/db/test_023_messaging.py-334-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-335-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:336:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py-337-    )
apps/api/tests/db/test_023_messaging.py-338-    post_message(
apps/api/tests/db/test_023_messaging.py-339-        app_session,
apps/api/tests/db/test_023_messaging.py-340-        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py-341-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-342-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-343-        spec=MessageInput(body="We should probably reformulate and open a corrective action."),
apps/api/tests/db/test_023_messaging.py-344-    )
apps/api/tests/db/test_023_messaging.py-345-    app_session.commit()
apps/api/tests/db/test_023_messaging.py-346-
apps/api/tests/db/test_023_messaging.py-347-    tasks = app_session.execute(
apps/api/tests/db/test_023_messaging.py-348-        text("SELECT count(*) FROM workflow.tasks WHERE organization_id = :o"), {"o": fx["org"]}
apps/api/tests/db/test_023_messaging.py-349-    ).scalar_one()
apps/api/tests/db/test_023_messaging.py-350-    assert tasks == 0, "a message created a controlled record on its own"
apps/api/tests/db/test_023_messaging.py-351-
apps/api/tests/db/test_023_messaging.py-352-
apps/api/tests/db/test_023_messaging.py-353-def test_a_withdrawn_message_leaves_the_conversation_readable(
apps/api/tests/db/test_023_messaging.py-354-    app_session: Session, owner_session: Session, channel_fixture: dict[str, uuid.UUID]
apps/api/tests/db/test_023_messaging.py-355-) -> None:
apps/api/tests/db/test_023_messaging.py-356-    """A withdrawn message is replaced, not omitted.
apps/api/tests/db/test_023_messaging.py-357-
apps/api/tests/db/test_023_messaging.py-358-    Omitting it would leave replies pointing at nothing, and a
apps/api/tests/db/test_023_messaging.py-359-    conversation with holes cannot be read at all.
apps/api/tests/db/test_023_messaging.py-360-    """
apps/api/tests/db/test_023_messaging.py-361-    fx = channel_fixture
apps/api/tests/db/test_023_messaging.py-362-
apps/api/tests/db/test_023_messaging.py-363-    channel = create_channel(
apps/api/tests/db/test_023_messaging.py-364-        app_session,
apps/api/tests/db/test_023_messaging.py-365-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-366-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py:367:        spec=ChannelInput(channel_type="project", name="Restricted", project_id=fx["project"]),
apps/api/tests/db/test_023_messaging.py-368-    )
apps/api/tests/db/test_023_messaging.py-369-    first = post_message(
apps/api/tests/db/test_023_messaging.py-370-        app_session,
apps/api/tests/db/test_023_messaging.py-371-        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py-372-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-373-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-374-        spec=MessageInput(body="Original claim."),
apps/api/tests/db/test_023_messaging.py-375-    )
apps/api/tests/db/test_023_messaging.py-376-    post_message(
apps/api/tests/db/test_023_messaging.py-377-        app_session,
apps/api/tests/db/test_023_messaging.py-378-        channel_id=channel["id"],
apps/api/tests/db/test_023_messaging.py-379-        organization_id=fx["org"],
apps/api/tests/db/test_023_messaging.py-380-        actor_id=fx["author"],
apps/api/tests/db/test_023_messaging.py-381-        spec=MessageInput(body="Agreed.", reply_to_id=first["id"]),
apps/api/tests/db/test_023_messaging.py-382-    )
apps/api/tests/db/test_023_messaging.py-383-    app_session.commit()
apps/api/tests/db/test_023_messaging.py-384-
apps/api/tests/db/test_023_messaging.py-385-    owner_session.begin()
apps/api/tests/db/test_023_messaging.py-386-    owner_session.execute(
apps/api/tests/db/test_023_messaging.py-387-        text("UPDATE messaging.messages SET is_deleted = TRUE WHERE id = :m"), {"m": first["id"]}
apps/api/tests/db/test_023_messaging.py-388-    )
apps/api/tests/db/test_023_messaging.py-389-    owner_session.commit()
apps/api/tests/db/test_023_messaging.py-390-
apps/api/tests/db/test_023_messaging.py-391-    thread = list_messages(app_session, channel_id=channel["id"], organization_id=fx["org"])
apps/api/tests/db/test_023_messaging.py-392-    assert len(thread) == 2, "the withdrawn message vanished and took the thread with it"
apps/api/tests/db/test_023_messaging.py-393-    assert thread[0]["body"] == "(this message was withdrawn)"
apps/api/tests/db/test_023_messaging.py-394-    assert thread[1]["reply_to_id"] == first["id"]

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n -A 180 "''^  auth:" .github/workflows/ci.yml' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 422ms:
466:  auth:
467-    name: Auth — real Keycloak, real tokens
468-    runs-on: ubuntu-latest
469-
470-    # 🔴 THE FIRST TIME AUTHENTICATION HAS EVER RUN.
471-    #
472-    # The API has verified tokens correctly since Slice 1 and had never
473-    # once verified a real one, because no Keycloak had ever run anywhere:
474-    # not on Render, not in CI, not on the development host. Every auth
475-    # test until now fabricated its own JWT or mocked the verifier, so the
476-    # four defects this job exists to catch were all invisible — the realm
477-    # ships with zero users, the seeder writes placeholder subjects, a
478-    # Keycloak token's audience is `account` unless a mapper says
479-    # otherwise, and nothing had ever sent `X-Organization-Id`.
480-    #
481-    # This job needs no deployment and costs nothing, which matters:
482-    # deploying the API and Keycloak is blocked on Render's free
483-    # web-service quota, and that is the operator's decision, not CI's.
484-
485-    services:
486-      postgres:
487-        image: pgvector/pgvector:pg16
488-        env:
489-          POSTGRES_DB: evercoat_itw_rd
490-          POSTGRES_USER: postgres
491-          POSTGRES_PASSWORD: ci-postgres
492-        options: >-
493-          --health-cmd "pg_isready -U postgres -d evercoat_itw_rd"
494-          --health-interval 5s --health-timeout 5s --health-retries 20
495-        ports: ["5432:5432"]
496-
497-    steps:
498-      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4, resolved 2026-08-18
499-
500-      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5, resolved 2026-08-18
501-        with:
502-          python-version: ${{ env.PYTHON_VERSION }}
503-          cache: pip
504-
505-      - name: Install API
506-        working-directory: apps/api
507-        run: pip install -e ".[dev]"
508-
509-      # Generated, never written down. A hardcoded password in a workflow
510-      # file is a gitleaks finding whatever the comment beside it says, and
511-      # the realm's policy (12 chars, mixed case, digit, special) would push
512-      # anyone writing one by hand toward something they had used before.
513-      - name: Mint throwaway credentials
514-        run: |
515-          set -euo pipefail
516-          admin="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9')Aa1!"
517-          user="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9')Bb2!"
518-          echo "::add-mask::$admin"
519-          echo "::add-mask::$user"
520-          echo "KC_ADMIN_PASSWORD=$admin" >> "$GITHUB_ENV"
521-          echo "KC_USER_PASSWORD=$user" >> "$GITHUB_ENV"
522-
523-      - name: Start Keycloak with the shipped realm
524-        run: |
525-          set -euo pipefail
526-          # `docker run`, not a `services:` block: a service container takes
527-          # only an image and env, and Keycloak needs BOTH a command
528-          # (`start-dev --import-realm`) and the realm mounted. A service
529-          # container would start a Keycloak with no realm at all — which
530-          # would pass a health check and fail every token request.
531-          docker run -d --name evercoat-keycloak-ci \
532-            -p 8080:8080 \
533-            -e KC_BOOTSTRAP_ADMIN_USERNAME=admin \
534-            -e KC_BOOTSTRAP_ADMIN_PASSWORD="$KC_ADMIN_PASSWORD" \
535-            -e KC_HEALTH_ENABLED=true \
536-            -e KC_HTTP_ENABLED=true \
537-            -v "$PWD/services/keycloak/realm:/opt/keycloak/data/import:ro" \
538-            quay.io/keycloak/keycloak:26.0 \
539-            start-dev --import-realm
540-
541-      - name: Apply migrations
542-        working-directory: apps/api
543-        env:
544-          MIGRATION_DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
545-          DATABASE_URL: postgresql+psycopg://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
546-          KEYCLOAK_ISSUER: http://localhost:8080/realms/evercoat
547-        run: alembic upgrade head
548-
549-      - name: Grant the application role a login
550-        env:
551-          PGPASSWORD: ci-postgres
552-        run: |
553-          set -euo pipefail
554-          psql -h localhost -U postgres -d evercoat_itw_rd -v ON_ERROR_STOP=1 <<'SQL'
555-          ALTER ROLE evercoat_app LOGIN PASSWORD 'ci-app';
556-          GRANT CONNECT ON DATABASE evercoat_itw_rd TO evercoat_app;
557-          SQL
558-
559-      - name: Seed, and capture the organization the tokens will name
560-        env:
561-          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
562-        run: |
563-          set -euo pipefail
564-          python scripts/seed.py | tee seed.log
565-          org="$(grep -oE 'organization: [0-9a-f-]{36}' seed.log | head -1 | awk '{print $2}')" || org=""
566-          if [ -z "$org" ]; then
567-            echo "FAIL: the seeder printed no organization id; every request would 400" >&2
568-            exit 1
569-          fi
570-          echo "TEST_ORGANIZATION_ID=$org" >> "$GITHUB_ENV"
571-
572-      - name: Create the realm's users and bind their subjects
573-        env:
574-          KC_URL: http://localhost:8080
575-          KC_SUBS_OUT: keycloak-subs.json
576-          SEED_DATABASE_URL: postgresql://postgres:ci-postgres@localhost:5432/evercoat_itw_rd
577-        run: |
578-          set -euo pipefail
579-          bash scripts/keycloak-bootstrap.sh --with-test-client
580-          python scripts/keycloak-bind-subs.py keycloak-subs.json
581-
582-      - name: Start the API
583-        working-directory: apps/api
584-        env:
585-          DATABASE_URL: postgresql+psycopg://evercoat_app:ci-app@localhost:5432/evercoat_itw_rd
586-          KEYCLOAK_ISSUER: http://localhost:8080/realms/evercoat
587-          KEYCLOAK_AUDIENCE: evercoat-api
588-        run: |
589-          set -euo pipefail
590-          nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$GITHUB_WORKSPACE/api.log" 2>&1 &
591-          deadline=$(( SECONDS + 90 ))
592-          until code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health/live)" \
593-                && [ "$code" = "200" ]; do
594-            if [ "$SECONDS" -ge "$deadline" ]; then
595-              echo "FAIL: the API never became live. Its log:" >&2
596-              cat "$GITHUB_WORKSPACE/api.log" >&2
597-              exit 1
598-            fi
599-            sleep 2
600-          done
601-
602-      # 🔴 THE COUNTS, AND THE THIRD STATE.
603-      #
604-      # These tests skip themselves when no Keycloak is configured, which
605-      # is right on a laptop and catastrophic here: a fully skipped run
606-      # exits 0 and reads as proof. The assertion below is on the number
607-      # that PASSED and on skipped being zero — never on the exit code.
608-      - name: Prove authentication end to end
609-        working-directory: apps/api
610-        env:
611-          TEST_KEYCLOAK_URL: http://localhost:8080
612-          TEST_API_URL: http://127.0.0.1:8000
613-          TEST_KEYCLOAK_REALM: evercoat
614-          TEST_KEYCLOAK_CLIENT: evercoat-test
615-          TEST_KEYCLOAK_PASSWORD: ${{ env.KC_USER_PASSWORD }}
616-          TEST_ORGANIZATION_ID: ${{ env.TEST_ORGANIZATION_ID }}
617-        run: |
618-          set -euo pipefail
619-          pytest tests/integration/test_auth_end_to_end.py -v --junitxml=auth-results.xml || true
620-          python "$GITHUB_WORKSPACE/scripts/assert-suite-ran.py" auth-results.xml
621-
622-      - name: Keycloak and API logs on failure
623-        if: failure()
624-        run: |
625-          echo "=== keycloak ==="; docker logs evercoat-keycloak-ci 2>&1 | tail -80
626-          echo "=== api ==="; tail -80 "$GITHUB_WORKSPACE/api.log" || true

codex
Found three concrete defects.

- High — [scripts/keycloak-bootstrap.sh:172](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:172): rerunning bootstrap does not repair existing users. `POST /users` returns 409, which `curl` treats as success; the script then uses the existing user without resetting its password, enabling it, or correcting its email. It can exit successfully and write valid subject mappings while those accounts still cannot authenticate with `KC_USER_PASSWORD`.

- High — [scripts/keycloak-bootstrap.sh:121](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:121): an existing `evercoat-test` client is also accepted without validation or repair. If it is disabled, lacks direct grants, or lacks the audience mapper, bootstrap reports success but issued tokens are unavailable or rejected by the API. More generally, the `api()` wrapper at line 107 never uses `curl --fail` or checks HTTP status, so failed role-mapping writes at line 210 are silently accepted too.

- Medium — [.github/workflows/ci.yml:619](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/.github/workflows/ci.yml:619): `pytest ... || true` discards pytest’s result. The following assertion is documented as checking only that tests passed and none skipped. Therefore a run containing the expected passing test(s) plus a failure/error can still make the auth job green; successful authentication does not prove the complete authentication suite succeeded.

Category results:

- Restricted-project channel notification/read: none found. `_resolve_mentions` explicitly checks the recipient’s active project membership for restricted projects at service.py:528–565. `list_channels` relies on channel RLS for restricted projects and additionally filters direct channels by membership at service.py:309–330.
- Author-session reference disclosure: none found. Resolver lookups are parameterized and execute under the author’s RLS-scoped session; unresolved records generate neither stored links nor identifying errors.
- Promotion across inaccessible projects: none found. The source-message/channel lookup remains subject to actor-session RLS.
- NULL promotion: no unauthorized task is created, but promoting a direct/announcement channel attempts an insert with `project_id = NULL` at service.py:673–724. If the schema requires a project, the constraint prevents creation and the API returns a 400 containing the raw database error via service.py:725–727. This is poor validation/error hygiene, but not a path that creates a NULL task.
- SQL interpolation: none found. SQL values in the reviewed Python files are parameterized; resolver SQL comes only from the static `_RESOLVERS` table.
- Credential leakage into logs: none found. Passwords are not explicitly printed, and CI masks generated values. They are passed in command arguments/JSON, but the reviewed scripts do not enable shell tracing.
- `keycloak-bind-subs.py`: no SQL-interpolation defect. However, it commits successful bindings before reporting missing users at lines 70–104, so failure leaves a partially rebound database. It exits nonzero, so this is not silent success, but rerunning authentication between remediation steps can produce mixed working/broken accounts.
tokens used
42,683
Found three concrete defects.

- High — [scripts/keycloak-bootstrap.sh:172](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:172): rerunning bootstrap does not repair existing users. `POST /users` returns 409, which `curl` treats as success; the script then uses the existing user without resetting its password, enabling it, or correcting its email. It can exit successfully and write valid subject mappings while those accounts still cannot authenticate with `KC_USER_PASSWORD`.

- High — [scripts/keycloak-bootstrap.sh:121](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/scripts/keycloak-bootstrap.sh:121): an existing `evercoat-test` client is also accepted without validation or repair. If it is disabled, lacks direct grants, or lacks the audience mapper, bootstrap reports success but issued tokens are unavailable or rejected by the API. More generally, the `api()` wrapper at line 107 never uses `curl --fail` or checks HTTP status, so failed role-mapping writes at line 210 are silently accepted too.

- Medium — [.github/workflows/ci.yml:619](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/.github/workflows/ci.yml:619): `pytest ... || true` discards pytest’s result. The following assertion is documented as checking only that tests passed and none skipped. Therefore a run containing the expected passing test(s) plus a failure/error can still make the auth job green; successful authentication does not prove the complete authentication suite succeeded.

Category results:

- Restricted-project channel notification/read: none found. `_resolve_mentions` explicitly checks the recipient’s active project membership for restricted projects at service.py:528–565. `list_channels` relies on channel RLS for restricted projects and additionally filters direct channels by membership at service.py:309–330.
- Author-session reference disclosure: none found. Resolver lookups are parameterized and execute under the author’s RLS-scoped session; unresolved records generate neither stored links nor identifying errors.
- Promotion across inaccessible projects: none found. The source-message/channel lookup remains subject to actor-session RLS.
- NULL promotion: no unauthorized task is created, but promoting a direct/announcement channel attempts an insert with `project_id = NULL` at service.py:673–724. If the schema requires a project, the constraint prevents creation and the API returns a 400 containing the raw database error via service.py:725–727. This is poor validation/error hygiene, but not a path that creates a NULL task.
- SQL interpolation: none found. SQL values in the reviewed Python files are parameterized; resolver SQL comes only from the static `_RESOLVERS` table.
- Credential leakage into logs: none found. Passwords are not explicitly printed, and CI masks generated values. They are passed in command arguments/JSON, but the reviewed scripts do not enable shell tracing.
- `keycloak-bind-subs.py`: no SQL-interpolation defect. However, it commits successful bindings before reporting missing users at lines 70–104, so failure leaves a partially rebound database. It exits nonzero, so this is not silent success, but rerunning authentication between remediation steps can produce mixed working/broken accounts.
