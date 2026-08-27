Reading additional input from stdin...
OpenAI Codex v0.147.0
--------
workdir: C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 01a04544-4983-7962-86da-36265aef4ad8
--------
user
You are reviewing commit 722df3d in the EvercoatITWRD APP repository (working
codex
I’ll inspect commit `722df3d`, its surrounding code, and relevant tests, then report only concrete regressions or risks with file-and-line references.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git status --short; git show --stat --oneline --decorate --no-renames 722df3d; git show --format=fuller --no-ext-diff --no-renames 722df3d' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
codex
The repository command is still running; I’m waiting for the full diff before evaluating behavior.
 succeeded in 1574ms:
722df3d (HEAD -> master) fix: the theme was a half-theme, and the profile was a second copy
 apps/api/app/api/me.py                             |  46 ++-
 apps/api/tests/integration/test_auth_end_to_end.py |   8 +-
 apps/api/tests/test_me_identity_shape.py           | 153 +++++++++
 apps/web/app/account/settings/page.tsx             | 117 +++----
 apps/web/app/admin/permissions/page.tsx            |  10 +-
 apps/web/app/admin/reference-data/page.tsx         |  18 +-
 apps/web/app/admin/roles/page.tsx                  |   4 +-
 apps/web/app/admin/stage-gates/page.tsx            |   9 +-
 apps/web/app/layout.tsx                            |  18 +
 apps/web/app/page.tsx                              |  27 +-
 apps/web/components/nav/user-menu.tsx              |  26 +-
 .../web/components/providers/auth-provider.test.ts |  80 ++++-
 apps/web/components/providers/auth-provider.tsx    |  96 ++++--
 apps/web/components/providers/theme-provider.tsx   |  13 +-
 apps/web/components/ui/entity-header.tsx           |  19 ++
 apps/web/components/ui/radio-cards.tsx             | 133 ++++++++
 apps/web/lib/accessibility-coverage.test.ts        | 127 +++++++
 apps/web/lib/permissions.test.ts                   |   4 +
 apps/web/lib/preferences.ts                        |  19 +-
 apps/web/lib/theme.test.ts                         | 294 +++++++++++++++-
 apps/web/lib/theme.ts                              | 376 ++++++++++++++++++++-
 apps/web/tailwind.config.ts                        | 107 ++++--
 tests/e2e/shell/accessibility.spec.ts              |  30 ++
 tests/e2e/shell/theme.spec.ts                      |  88 +++++
 24 files changed, 1643 insertions(+), 179 deletions(-)
commit 722df3d50bb683208569bd02727d91ce0a44f47b
Author:     Marc <marc667us@yahoo.com>
AuthorDate: Thu Aug 27 15:06:33 2026 -0700
Commit:     Marc <marc667us@yahoo.com>
CommitDate: Thu Aug 27 15:06:33 2026 -0700

    fix: the theme was a half-theme, and the profile was a second copy
    
    Nineteen findings from Codex and the Supervisor on b84a300/ad55d99. None
    were P1; five were found by both. Measuring them found four more.
    
    THE THEME COVERED 12 OF 34 COLOUR TOKENS
    
    `lib/theme.ts` claimed "no component knows a theme exists -- which is also
    why a component cannot opt out of one and quietly stay light" over a file
    that themed `white` and `slate-50…900` and nothing else. That was false for
    129 call sites: every alert ramp, plus `slate-950`, which Tailwind's deep
    merge left at its built-in near-black on a near-black dark page.
    
    Worst was `StatusBadge`: `bg-emerald-50` stayed light while `text-status-pass`
    had just been lightened for a dark surface. 1.65:1 for pass, 2.53 for fail,
    1.61 for conditional. The contrast test could not see it -- it measured status
    colours against `palette.white`, which is not what a badge sits on.
    
      * seven accent ramps themed, derived from the light set by documented
        transforms rather than hand-tinted;
      * `theme.test.ts` now reads the SOURCE for class strings naming both a
        background and a foreground, and measures those pairs on every palette.
        It immediately refused the first dark set at 3.62:1 on the fail badge,
        which is why the dark ramps reach past the product's own steps to each
        hue's 950 and 100;
      * `tailwind.config.ts` IMPORTS the palette. Its comment claimed a drift
        test existed over 60 hand-copied triples; there is now one definition
        and a test that measures the resolved config in both directions.
    
    THE PAGE FLASHED WHITE ON EVERY LOAD
    
    The variables were only ever written by `ThemeProvider`, which is React and
    runs after first paint. A pre-paint script in the document head now applies
    them, built from the same `paletteVariables` the provider uses.
    
    THE PROFILE WAS STORED, WHICH WAS THREE DEFECTS
    
    `signOut` never cleared it, so the previous user's name stayed in the top bar
    of an anonymous application. Switching organization did not change it. And
    its value came from a top-level `display_name` on `/api/me` taken from
    `rows[0]` -- while migration 052 had deliberately moved that attribute onto
    the membership, and the rows are ordered by organization name.
    
    `/api/me` no longer declares tenant attributes on the identity; each
    membership carries its own pair. `activeProfile()` derives the profile from
    the ACTIVE membership, so there is nothing to clear, nothing to refresh, and
    a blank name is an absent name rather than "signed in as ''".
    
    A SETTING WITH NO ENFORCEMENT POINT
    
    `readLanding` had no reader anywhere: the front door redirected to a
    hard-coded /dashboard while Settings said the preference worked. `app/page.tsx`
    now opens on the chosen screen, which is also what sign-in returns to.
    
    AND THE ACCESSIBILITY SWEEP HAD NEVER SEEN TEN PAGES
    
    The Supervisor named /admin/roles and /admin/permissions. Asking which routes
    exist found eight more, some uncovered since the slice that built them.
    `accessibility-coverage.test.ts` derives the list from the filesystem, so
    remembering is no longer the mechanism.
    
    Also: `role="radiogroup"` over plain buttons with no arrow keys, under a
    comment arguing that is exactly what a radiogroup must not be (RadioCards);
    the user menu never moved focus in or back out; and four Administration
    headers reported "0" while the answer was unknown.
    
    apps/api 846 passed / 0 failed / 11 skipped (857 collected).
    apps/web 202 vitest. next build clean; the pre-paint script is in the head.
    
    Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>

diff --git a/apps/api/app/api/me.py b/apps/api/app/api/me.py
index 8209215..ff6a1e7 100644
--- a/apps/api/app/api/me.py
+++ b/apps/api/app/api/me.py
@@ -57,11 +57,28 @@ router = APIRouter()
 
 
 class OrganizationMembership(BaseModel):
-    """One organization this user may act in."""
+    """One organization this user may act in, as that organization knows them."""
 
     organization_id: uuid.UUID
     name: str
     code: str
+    #: The address and name THIS ORGANIZATION holds for the caller (052).
+    #:
+    #: 🔴 052 MOVED THESE ONTO THE MEMBERSHIP AND THIS ROUTE PUT THEM BACK.
+    #:
+    #: ``core.memberships_for_subject`` returns one row per organization and
+    #: each row carries its own ``om.email`` / ``om.display_name`` -- the
+    #: migration's own comment says so, because reading the global identity
+    #: "meant every tenant in the list was described by a single shared
+    #: address". This route then took ``rows[0]`` and reported it as *the*
+    #: identity, and the rows are ordered by organization NAME. So a member of
+    #: two organizations saw the alphabetically-first one's name in the top bar
+    #: no matter which tenant they were working in -- the exact defect 052
+    #: exists to prevent, re-introduced one tier up. Codex found it while
+    #: asking a narrower question: why switching organization does not change
+    #: the displayed profile.
+    email: str
+    display_name: str
     #: Role codes held IN THIS ORGANIZATION. Membership is per-tenant, so
     #: a user can be a chemist in one and a viewer in another. A single
     #: flat role list would be wrong in a way nobody would notice until a
@@ -91,11 +108,23 @@ class OrganizationMembership(BaseModel):
 
 
 class Me(BaseModel):
-    """The caller's identity, and the tenants they may choose from."""
+    """The caller's identity, and the tenants they may choose from.
+
+    🔴 THERE IS NO TOP-LEVEL NAME OR ADDRESS HERE, AND THAT IS THE POINT.
+
+    There used to be, taken from the first row. An identity in this system
+    has exactly one tenant-independent attribute -- ``user_id`` -- because
+    migration 052 is titled *an identity has no tenant attributes* and moved
+    everything else onto the membership. A top-level ``display_name`` is a
+    tenant attribute wearing an identity's clothes: it has to come from
+    somewhere, and "whichever organization sorts first" is not an answer a
+    caller can reason about.
+
+    The browser reads the ACTIVE organization's pair. See
+    ``components/providers/auth-provider.tsx``.
+    """
 
     user_id: uuid.UUID
-    email: str
-    display_name: str
     organizations: list[OrganizationMembership] = Field(default_factory=list)
 
 
@@ -155,16 +184,17 @@ async def read_me(subject: Annotated[str, Depends(get_verified_subject)]) -> Me:
             ),
         )
 
-    first = rows[0]
+    # The id is the one attribute every row agrees on -- it is the identity,
+    # and the function keys on it. Everything else is per-membership.
     return Me(
-        user_id=first["user_id"],
-        email=first["email"],
-        display_name=first["display_name"],
+        user_id=rows[0]["user_id"],
         organizations=[
             OrganizationMembership(
                 organization_id=row["organization_id"],
                 name=row["organization_name"],
                 code=row["organization_code"],
+                email=row["email"],
+                display_name=row["display_name"],
                 roles=sorted(row["roles"]),
                 permissions=sorted(row["permissions"]),
             )
diff --git a/apps/api/tests/integration/test_auth_end_to_end.py b/apps/api/tests/integration/test_auth_end_to_end.py
index 4ba8a81..79291c7 100644
--- a/apps/api/tests/integration/test_auth_end_to_end.py
+++ b/apps/api/tests/integration/test_auth_end_to_end.py
@@ -288,7 +288,6 @@ def test_a_signed_in_user_can_discover_their_organizations() -> None:
     assert response.status_code == 200, response.text
 
     body = response.json()
-    assert body["email"], "a principal with no email is not a usable identity"
     assert body["organizations"], (
         "a valid token resolved to a user with NO organizations. A browser "
         "cannot proceed from here -- it has nothing to put in the header that "
@@ -298,6 +297,13 @@ def test_a_signed_in_user_can_discover_their_organizations() -> None:
     org = body["organizations"][0]
     assert uuid.UUID(org["organization_id"])
     assert org["name"], "an organization with no name cannot be offered in a picker"
+    # 🔴 ON THE MEMBERSHIP, NOT ON THE IDENTITY. This used to read
+    # `body["email"]`, which the route filled from whichever row sorted first
+    # -- so it asserted a name for a tenant it had not chosen. Migration 052
+    # put both attributes on the membership precisely because a user can be
+    # known by different addresses in different organizations.
+    assert org["email"], "a membership with no address is not a usable identity"
+    assert org["display_name"], "a membership with no name renders as a blank top bar"
 
     # 🔴 THE PERMISSIONS ARE PART OF THE CONTRACT NOW (I79), AND THIS IS THE
     # ONLY PLACE THE PYTHON/SQL RESPONSE EDGE IS ASSERTED END TO END.
diff --git a/apps/api/tests/test_me_identity_shape.py b/apps/api/tests/test_me_identity_shape.py
new file mode 100644
index 0000000..66f8570
--- /dev/null
+++ b/apps/api/tests/test_me_identity_shape.py
@@ -0,0 +1,153 @@
+"""🔴 THE ROUTE MUST NOT PUT BACK WHAT MIGRATION 052 TOOK OFF THE IDENTITY.
+
+052 is titled *an identity has no tenant attributes*. It moved ``email`` and
+``display_name`` from ``core.users`` onto ``core.organization_members``, and
+``core.memberships_for_subject`` returns one row per organization so that each
+row can report its own tenant's view of the person. ``test_052`` asserts all of
+that against a real database.
+
+``GET /api/me`` then read ``rows[0]`` and reported that pair as *the* identity
+-- and the function's own ``ORDER BY o.name`` means row zero is whichever
+organization sorts first alphabetically. A member of two organizations working
+in the second one saw the first one's name in the top bar, permanently, and
+switching organization could not change it because there was nothing per
+organization to switch to. Codex found it from the browser end, asking why the
+profile does not follow the organization selector.
+
+The database tier was right and the tier above it flattened the answer. These
+tests hold the ROUTE to what the migration established, without a database:
+what is asserted here is the mapping from rows to response, which is exactly
+where the flattening happened.
+"""
+
+from __future__ import annotations
+
+import uuid
+from contextlib import contextmanager
+from typing import Any
+
+import pytest
+
+from app.api import me as me_module
+from app.api.me import Me, OrganizationMembership, read_me
+
+
+class _Result:
+    def __init__(self, rows: list[dict[str, Any]]) -> None:
+        self._rows = rows
+
+    def mappings(self) -> _Result:
+        return self
+
+    def all(self) -> list[dict[str, Any]]:
+        return self._rows
+
+
+class _Session:
+    def __init__(self, rows: list[dict[str, Any]]) -> None:
+        self._rows = rows
+
+    def execute(self, _statement: Any, _params: Any) -> _Result:
+        return _Result(self._rows)
+
+
+def _rows_for_two_organizations() -> list[dict[str, Any]]:
+    """One person, two organizations, two different names — the only shape that
+    can tell a per-membership implementation from a flattened one."""
+    user_id = uuid.uuid4()
+    return [
+        {
+            "user_id": user_id,
+            # Ordered by organization name, as the function orders them: the
+            # ALPHABETICALLY FIRST row is the one the old code returned.
+            "organization_id": uuid.uuid4(),
+            "organization_name": "Acme Coatings",
+            "organization_code": "ACME",
+            "email": "known.in.acme@acme.example",
+            "display_name": "Known In Acme",
+            "roles": ["product_development_chemist"],
+            "permissions": ["formula.view"],
+        },
+        {
+            "user_id": user_id,
+            "organization_id": uuid.uuid4(),
+            "organization_name": "Zenith Adhesives",
+            "organization_code": "ZEN",
+            "email": "different.address@zenith.example",
+            "display_name": "Different Name Entirely",
+            "roles": ["laboratory_technician"],
+            "permissions": ["test.execute"],
+        },
+    ]
+
+
+@pytest.fixture
+def two_organizations(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
+    rows = _rows_for_two_organizations()
+
+    @contextmanager
+    def _scope() -> Any:
+        yield _Session(rows)
+
+    monkeypatch.setattr(me_module, "auth_session_scope", _scope)
+    return rows
+
+
+def test_the_identity_carries_no_tenant_attributes() -> None:
+    """The shape rule from 052, stated where it was broken.
+
+    Asserted on the MODEL rather than on one response, because the defect was
+    not a wrong value -- every value was real. It was a field existing at a
+    level that cannot answer for it.
+    """
+    fields = set(Me.model_fields)
+
+    tenant_attributes = fields & {"email", "display_name"}
+    assert not tenant_attributes, (
+        f"GET /api/me declares a top-level {sorted(tenant_attributes)}. There is "
+        "no organization at that level to take it from, so it can only be one "
+        "membership's value presented as the identity's -- which is what 052 "
+        "removed from the database and what this route re-created above it."
+    )
+    assert fields == {"user_id", "organizations"}, (
+        f"the identity grew a new tenant-independent attribute: {sorted(fields)}"
+    )
+
+    membership = set(OrganizationMembership.model_fields)
+    assert {"email", "display_name"} <= membership, (
+        "the membership does not carry the attributes, so nothing does and the "
+        f"browser has no name to show. Fields: {sorted(membership)}"
+    )
+
+
+async def test_each_membership_reports_its_own_organizations_view(
+    two_organizations: list[dict[str, Any]],
+) -> None:
+    """🔴 TWO ORGANIZATIONS, TWO NAMES, AND NEITHER MAY BE THE OTHER'S.
+
+    This is the assertion the old shape could not pass. It returned one pair
+    for a caller with two, so the second organization was described by the
+    first one's record.
+    """
+    response = await read_me(subject="a-verified-keycloak-uuid")
+
+    by_code = {org.code: org for org in response.organizations}
+    assert set(by_code) == {"ACME", "ZEN"}
+
+    assert (by_code["ACME"].email, by_code["ACME"].display_name) == (
+        "known.in.acme@acme.example",
+        "Known In Acme",
+    )
+    assert (by_code["ZEN"].email, by_code["ZEN"].display_name) == (
+        "different.address@zenith.example",
+        "Different Name Entirely",
+    ), (
+        "the second organization is describing this person with the first "
+        "organization's record. That is `rows[0]` leaking back: the rows are "
+        "ordered by organization name, so it is always the alphabetically "
+        "first tenant's view that wins."
+    )
+
+    # And the one thing that IS the identity is the same in both.
+    assert response.user_id == two_organizations[0]["user_id"]
+    assert len({org.organization_id for org in response.organizations}) == 2
diff --git a/apps/web/app/account/settings/page.tsx b/apps/web/app/account/settings/page.tsx
index 6f5290d..4714106 100644
--- a/apps/web/app/account/settings/page.tsx
+++ b/apps/web/app/account/settings/page.tsx
@@ -18,13 +18,10 @@
  */
 
 import { EntityHeader } from "@/components/ui/entity-header";
-import { LANDING_SCREENS, usePreferences } from "@/lib/preferences";
+import { RadioCards } from "@/components/ui/radio-cards";
+import { LANDING_SCREENS, usePreferences, type LandingScreen } from "@/lib/preferences";
 import { PALETTES, THEMES, contrast, type ThemeId } from "@/lib/theme";
 
-const TAG =
-  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
-  "tracking-wide text-slate-600";
-
 /**
  * A miniature of what the theme actually paints.
  *
@@ -89,43 +86,24 @@ export default function SettingsPage() {
             traffic-light colours are checked against every theme.
           </p>
 
-          {/* radiogroup, not a list of buttons: these are one choice among
-              five, and arrow-key navigation between them is what a screen
-              reader user expects from a radiogroup and does not get from a row
-              of buttons. */}
-          <div role="radiogroup" aria-labelledby="theme-heading" className="mt-3 grid gap-2">
-            {THEMES.map((option) => {
-              const chosen = option.id === theme;
-              return (
-                <button
-                  key={option.id}
-                  type="button"
-                  role="radio"
-                  aria-checked={chosen}
-                  onClick={() => setTheme(option.id)}
-                  className={[
-                    "flex items-center gap-3 rounded border p-3 text-left",
-                    chosen
-                      ? "border-slate-900 bg-slate-50"
-                      : "border-slate-200 bg-white hover:bg-slate-50",
-                  ].join(" ")}
-                >
-                  <Swatch theme={option.id} />
-                  <span className="min-w-0 flex-1">
-                    <span className="block text-sm font-medium text-slate-900">
-                      {option.label}
-                    </span>
-                    <span className="block text-xs text-slate-600">{option.description}</span>
-                  </span>
-                  {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by
-                      colour or shape alone, and "which one is selected" is
-                      state. `aria-checked` says it assistively; this says it
-                      to everyone else. */}
-                  {chosen && <span className={TAG}>selected</span>}
-                </button>
-              );
-            })}
-          </div>
+          {/* 🔴 `RadioCards` RATHER THAN A ROW OF BUTTONS WITH A ROLE ON IT.
+              This markup used to declare `role="radiogroup"` over five
+              ordinary buttons, under a comment arguing that arrow-key
+              navigation "is what a screen reader user expects from a
+              radiogroup and does not get from a row of buttons" — and it did
+              not implement any. The Supervisor found the gap between the
+              comment and the widget. */}
+          <RadioCards<ThemeId>
+            labelledBy="theme-heading"
+            value={theme}
+            onChange={setTheme}
+            options={THEMES.map((option) => ({
+              id: option.id,
+              label: option.label,
+              description: option.description,
+              preview: <Swatch theme={option.id} />,
+            }))}
+          />
 
           <p className="mt-3 text-xs text-slate-600">
             Measured on the light surface: body text{" "}
@@ -137,41 +115,38 @@ export default function SettingsPage() {
 
         <section aria-labelledby="landing-heading" className="max-w-3xl">
           <h2 id="landing-heading" className="text-sm font-semibold text-slate-900">
-            After signing in, open
+            Where the application opens
           </h2>
+          {/* 🔴 THE HEADING USED TO SAY "AFTER SIGNING IN, OPEN" AND NOTHING
+              IMPLEMENTED IT. `readLanding` had no reader anywhere in the
+              codebase: the front door redirected to a hard-coded `/dashboard`
+              and sign-in returned you to wherever you already were. Both
+              reviewers found it, and it is this project's own rule — a setting
+              with no enforcement point is a defect — arriving from the user's
+              side of the screen.
+
+              It is now the front door's destination, which is also what
+              sign-in returns you to when you have not navigated somewhere
+              else first. The heading says what happens rather than the
+              narrower thing the first version claimed. */}
           <p className="mt-1 text-sm text-slate-600">
             Three screens to choose from. Each one exists — a preference pointing
             at an unbuilt screen would be a setting whose only effect is a 404.
+            Opening a link straight to a record still takes you to that record;
+            this is where you arrive when you have not asked for anywhere in
+            particular.
           </p>
 
-          <div role="radiogroup" aria-labelledby="landing-heading" className="mt-3 grid gap-2">
-            {LANDING_SCREENS.map((screen) => {
-              const chosen = screen.id === landing;
-              return (
-                <button
-                  key={screen.id}
-                  type="button"
-                  role="radio"
-                  aria-checked={chosen}
-                  onClick={() => setLanding(screen.id)}
-                  className={[
-                    "flex items-center gap-3 rounded border p-3 text-left",
-                    chosen
-                      ? "border-slate-900 bg-slate-50"
-                      : "border-slate-200 bg-white hover:bg-slate-50",
-                  ].join(" ")}
-                >
-                  <span className="min-w-0 flex-1">
-                    <span className="block text-sm font-medium text-slate-900">
-                      {screen.label}
-                    </span>
-                    <span className="block text-xs text-slate-600">{screen.description}</span>
-                  </span>
-                  {chosen && <span className={TAG}>selected</span>}
-                </button>
-              );
-            })}
-          </div>
+          <RadioCards<LandingScreen>
+            labelledBy="landing-heading"
+            value={landing}
+            onChange={setLanding}
+            options={LANDING_SCREENS.map((screen) => ({
+              id: screen.id,
+              label: screen.label,
+              description: screen.description,
+            }))}
+          />
         </section>
 
         <section className="max-w-3xl">
diff --git a/apps/web/app/admin/permissions/page.tsx b/apps/web/app/admin/permissions/page.tsx
index d3b796d..81c9e19 100644
--- a/apps/web/app/admin/permissions/page.tsx
+++ b/apps/web/app/admin/permissions/page.tsx
@@ -24,7 +24,7 @@
 import Link from "next/link";
 
 import { ContextSubmenu } from "@/components/ui/context-submenu";
-import { EntityHeader } from "@/components/ui/entity-header";
+import { EntityHeader, headerCount } from "@/components/ui/entity-header";
 import { LiveOnlyPage } from "@/components/ui/data-source-banner";
 import { serverMessage } from "@/lib/api/client";
 import { usePermissionCatalogue } from "@/lib/api/hooks";
@@ -58,7 +58,13 @@ export default function PermissionsPage() {
           { label: "Administration", href: "/admin" },
         ]}
         fields={[
-          { label: "Permissions", value: String(catalogue.length) },
+          {
+            label: "Permissions",
+            value: headerCount(
+              catalogue,
+              mayRead && !isLoading && error === null && unavailable === null,
+            ),
+          },
           { label: "Domains", value: String(byDomain.size) },
         ]}
       />
diff --git a/apps/web/app/admin/reference-data/page.tsx b/apps/web/app/admin/reference-data/page.tsx
index 5c2996a..f0ccbe9 100644
--- a/apps/web/app/admin/reference-data/page.tsx
+++ b/apps/web/app/admin/reference-data/page.tsx
@@ -31,7 +31,7 @@ import Link from "next/link";
 import { useState } from "react";
 
 import { ContextSubmenu } from "@/components/ui/context-submenu";
-import { EntityHeader } from "@/components/ui/entity-header";
+import { EntityHeader, headerCount } from "@/components/ui/entity-header";
 import { LiveOnlyPage } from "@/components/ui/data-source-banner";
 import { serverMessage } from "@/lib/api/client";
 import { useAdminActions, useProductFamilies, useUnits } from "@/lib/api/hooks";
@@ -116,8 +116,20 @@ export default function ReferenceDataPage() {
           { label: "Administration", href: "/admin" },
         ]}
         fields={[
-          { label: "Units", value: String(unitRows.length) },
-          { label: "Product families", value: String(familyRows.length) },
+          {
+            label: "Units",
+            value: headerCount(
+              unitRows,
+              !units.isLoading && units.error === null && units.unavailable === null,
+            ),
+          },
+          {
+            label: "Product families",
+            value: headerCount(
+              familyRows,
+              !families.isLoading && families.error === null && families.unavailable === null,
+            ),
+          },
         ]}
       />
       <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/reference-data" />
diff --git a/apps/web/app/admin/roles/page.tsx b/apps/web/app/admin/roles/page.tsx
index e07850f..6d4de07 100644
--- a/apps/web/app/admin/roles/page.tsx
+++ b/apps/web/app/admin/roles/page.tsx
@@ -27,7 +27,7 @@
 import Link from "next/link";
 
 import { ContextSubmenu } from "@/components/ui/context-submenu";
-import { EntityHeader } from "@/components/ui/entity-header";
+import { EntityHeader, headerCount } from "@/components/ui/entity-header";
 import { LiveOnlyPage } from "@/components/ui/data-source-banner";
 import { serverMessage } from "@/lib/api/client";
 import { useRoles } from "@/lib/api/hooks";
@@ -56,7 +56,7 @@ export default function RolesPage() {
           { label: "Dashboard", href: "/dashboard" },
           { label: "Administration", href: "/admin" },
         ]}
-        fields={[{ label: "Roles", value: String(roles.length) }]}
+        fields={[{ label: "Roles", value: headerCount(roles, mayRead && !isLoading && error === null && unavailable === null) }]}
       />
       <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/roles" />
 
diff --git a/apps/web/app/admin/stage-gates/page.tsx b/apps/web/app/admin/stage-gates/page.tsx
index 1829089..0342a2b 100644
--- a/apps/web/app/admin/stage-gates/page.tsx
+++ b/apps/web/app/admin/stage-gates/page.tsx
@@ -33,7 +33,7 @@ import { useState } from "react";
 
 import { LiveOnlyPage } from "@/components/ui/data-source-banner";
 import { ContextSubmenu } from "@/components/ui/context-submenu";
-import { EntityHeader } from "@/components/ui/entity-header";
+import { EntityHeader, headerCount } from "@/components/ui/entity-header";
 import { serverMessage } from "@/lib/api/client";
 import { useAdminActions, useStageDefinitions } from "@/lib/api/hooks";
 import type { StageDefinition, StageWriteRequest } from "@/lib/api/admin";
@@ -465,7 +465,12 @@ export default function StageGatesPage() {
           { label: "Dashboard", href: "/dashboard" },
           { label: "Administration", href: "/admin" },
         ]}
-        fields={[{ label: "Stages", value: String(stages.length) }]}
+        fields={[
+          {
+            label: "Stages",
+            value: headerCount(stages, !isLoading && error === null && unavailable === null),
+          },
+        ]}
       />
       <ContextSubmenu items={ADMIN_SECTIONS} activeHref="/admin/stage-gates" />
 
diff --git a/apps/web/app/layout.tsx b/apps/web/app/layout.tsx
index c80cc92..032613d 100644
--- a/apps/web/app/layout.tsx
+++ b/apps/web/app/layout.tsx
@@ -20,6 +20,7 @@ import { QueryProvider } from "@/components/providers/query-provider";
 import { AppSidebar } from "@/components/nav/app-sidebar";
 import { TopBar } from "@/components/nav/top-bar";
 import { ALL_NAV_PERMISSIONS } from "@/lib/navigation";
+import { prePaintScript } from "@/lib/theme";
 
 import "./globals.css";
 
@@ -73,6 +74,23 @@ export default function RootLayout({
 
   return (
     <html lang="en">
+      <head>
+        {/* 🔴 BEFORE THE FIRST PAINT, NOT AFTER HYDRATION.
+ 
+            The themed variables were only ever set by `ThemeProvider`, which is
+            React and therefore runs after the document has already been
+            painted. A reader who had chosen dark got a full white page and then
+            their theme — on a static export served from a CDN, that flash is
+            the whole first impression, and it lands hardest on the people who
+            chose dark because a bright screen bothers them. Both reviewers
+            found it.
+
+            `dangerouslySetInnerHTML` because there is no other way to inline a
+            script in the document head from a server component. The content is
+            generated from this application's own constants — no request, no
+            user input, nothing interpolated from outside the build. */}
+        <script dangerouslySetInnerHTML={{ __html: prePaintScript() }} />
+      </head>
       <body className="bg-slate-50 text-slate-900 antialiased">
         {/* TanStack Query, for the whole tree. It wraps the shell rather
             than each page so that a query started on one screen is still
diff --git a/apps/web/app/page.tsx b/apps/web/app/page.tsx
index 63fe027..934a11d 100644
--- a/apps/web/app/page.tsx
+++ b/apps/web/app/page.tsx
@@ -1,7 +1,7 @@
 "use client";
 
 /**
- * Front door. Sends the visitor to the dashboard.
+ * Front door. Sends the visitor to the screen they chose to open on.
  *
  * WHY THIS IS A CLIENT REDIRECT AND NOT `redirect("/dashboard")`.
  *
@@ -35,13 +35,26 @@ import Link from "next/link";
 import { useRouter } from "next/navigation";
 import { useEffect } from "react";
 
+import { DEFAULT_LANDING, readLanding } from "@/lib/preferences";
+
 export default function Home() {
   const router = useRouter();
 
   useEffect(() => {
+    // 🔴 THE CHOSEN SCREEN, NOT A CONSTANT. Settings offers three destinations
+    // under "After signing in, open"; this used to be a hard `/dashboard`, so
+    // the preference had no reader anywhere in the application and the screen
+    // asserted a behaviour nothing implemented. Both reviewers found it — and
+    // it is the project's own rule about a setting with no enforcement point,
+    // reached from the other side.
+    //
+    // Read here rather than in a provider because this is the front door: it
+    // is where "where does the application open" is actually decided, and it
+    // works signed in or out.
+    //
     // `replace`, not `push` — the front door should not become a back-button
     // trap that bounces the visitor straight back out to it.
-    router.replace("/dashboard");
+    router.replace(readLanding());
   }, [router]);
 
   return (
@@ -55,10 +68,16 @@ export default function Home() {
           a screen-reader user landing here got an unlabelled page.
           The layout already supplies the <main> landmark. */}
       <h1 className="text-sm font-medium text-slate-600">
-        Redirecting to the dashboard…
+        Opening the application…
       </h1>
+      {/* ⚠️ THE DEFAULT, NOT THE PREFERENCE, AND DELIBERATELY SO. This link is
+          the whole page for a visitor with JavaScript disabled or still
+          loading. The preference lives in `localStorage`, which is only
+          readable by script, so a link that claimed to honour it would be a
+          link that could not — and rendering it from the preference after
+          hydration would change the destination under a reader mid-click. */}
       <Link
-        href="/dashboard"
+        href={DEFAULT_LANDING}
         className="mt-2 inline-block text-sm font-medium text-slate-900 underline"
       >
         Continue to the dashboard
diff --git a/apps/web/components/nav/user-menu.tsx b/apps/web/components/nav/user-menu.tsx
index 02d0b45..44dbe32 100644
--- a/apps/web/components/nav/user-menu.tsx
+++ b/apps/web/components/nav/user-menu.tsx
@@ -27,7 +27,7 @@ import { useAuth } from "@/components/providers/auth-provider";
 /** The three things a person can do about their own account. */
 const ITEMS = [
   { href: "/account/profile", label: "Profile", hint: "Who you are here, and what you may do" },
-  { href: "/account/settings", label: "Settings", hint: "Theme, and where you land after signing in" },
+  { href: "/account/settings", label: "Settings", hint: "Theme, and where the application opens" },
   { href: "/account/security", label: "Security", hint: "Your session, password and sign-out" },
 ] as const;
 
@@ -35,6 +35,8 @@ export function UserMenu() {
   const { profile } = useAuth();
   const [open, setOpen] = useState(false);
   const container = useRef<HTMLDivElement>(null);
+  const trigger = useRef<HTMLButtonElement>(null);
+  const firstItem = useRef<HTMLAnchorElement>(null);
 
   // 🔴 CLOSES ON OUTSIDE CLICK **AND** ON ESCAPE. A menu that only closes by
   // clicking its own trigger is a keyboard trap: tab into it, and the only way
@@ -48,7 +50,14 @@ export function UserMenu() {
       }
     };
     const onKey = (event: KeyboardEvent) => {
-      if (event.key === "Escape") setOpen(false);
+      if (event.key !== "Escape") return;
+      setOpen(false);
+      // 🔴 AND FOCUS GOES BACK TO THE TRIGGER. Escape used to close the menu
+      // and leave focus on an element that had just been removed from the
+      // document, which browsers resolve by sending it to `<body>` — so a
+      // keyboard user was returned to the top of the page and had to tab all
+      // the way back to where they were. Codex found it.
+      trigger.current?.focus();
     };
 
     document.addEventListener("mousedown", onPointer);
@@ -59,6 +68,15 @@ export function UserMenu() {
     };
   }, [open]);
 
+  // 🔴 OPENING A MENU MOVES FOCUS INTO IT. Without this the menu appeared and
+  // focus stayed on the trigger, so a screen reader announced a menu the user
+  // then had to hunt for, and the next Tab left it entirely. This is the other
+  // half of the Escape behaviour above: focus enters on open and returns on
+  // close, which is what `aria-haspopup="menu"` promises.
+  useEffect(() => {
+    if (open) firstItem.current?.focus();
+  }, [open]);
+
   if (profile === null) {
     return null;
   }
@@ -66,6 +84,7 @@ export function UserMenu() {
   return (
     <div ref={container} className="relative">
       <button
+        ref={trigger}
         type="button"
         aria-expanded={open}
         aria-haspopup="menu"
@@ -103,9 +122,10 @@ export function UserMenu() {
             <p className="truncate text-xs text-slate-600">{profile.email}</p>
           </div>
 
-          {ITEMS.map((item) => (
+          {ITEMS.map((item, index) => (
             <Link
               key={item.href}
+              ref={index === 0 ? firstItem : undefined}
               href={item.href}
               role="menuitem"
               onClick={() => setOpen(false)}
diff --git a/apps/web/components/providers/auth-provider.test.ts b/apps/web/components/providers/auth-provider.test.ts
index 1569485..1a4de20 100644
--- a/apps/web/components/providers/auth-provider.test.ts
+++ b/apps/web/components/providers/auth-provider.test.ts
@@ -21,12 +21,16 @@
 
 import { describe, expect, it } from "vitest";
 
-import { chooseOrganization, type OrganizationChoice } from "./auth-provider";
+import type { SessionState } from "@/lib/api/session";
+
+import { activeProfile, chooseOrganization, type OrganizationChoice } from "./auth-provider";
 
 const ACME: OrganizationChoice = {
   organizationId: "11111111-1111-1111-1111-111111111111",
   name: "Acme Coatings",
   code: "ACME",
+  email: "kwame.chemist@acme.example",
+  displayName: "Kwame Chemist",
   roles: ["product_development_chemist"],
   // I79: per-tenant, like the roles beside them.
   permissions: ["project.view", "formula.submit"],
@@ -36,6 +40,8 @@ const BOREAL: OrganizationChoice = {
   organizationId: "22222222-2222-2222-2222-222222222222",
   name: "Boreal Adhesives",
   code: "BOR",
+  email: "esi.lead@boreal.example",
+  displayName: "Esi Lead",
   roles: ["product_development_lead"],
   permissions: ["project.view", "formula.approve_lab"],
 };
@@ -71,3 +77,75 @@ describe("chooseOrganization", () => {
     expect(() => chooseOrganization([], undefined)).toThrow(/no organizations/);
   });
 });
+
+/**
+ * 🔴 THE PROFILE WAS STORED, AND STORING IT WAS THE DEFECT.
+ *
+ * Three findings, one cause. `signOut` cleared the session and the
+ * organizations and never cleared the profile, so the previous user's name
+ * stayed in the top bar of an anonymous application — both reviewers found
+ * that one, and on a shared bench machine it is somebody else's name over your
+ * work. Switching organization left it unchanged. And its value came from a
+ * top-level `display_name` that `/api/me` filled from whichever tenant sorted
+ * first, though migration 052 had deliberately moved that attribute onto the
+ * membership.
+ *
+ * Derived from the active membership, none of the three is reachable: there is
+ * no second copy to clear, none to refresh, and none to take from the wrong
+ * row. These tests assert the properties, not the implementation.
+ */
+describe("activeProfile", () => {
+  const authenticated = (organizationId: string): SessionState => ({
+    status: "authenticated",
+    credentials: {
+      token: "not-a-real-token",
+      organizationId,
+      userId: "44444444-4444-4444-4444-444444444444",
+    },
+  });
+
+  it("🔴 an anonymous session has no name, whatever is still in memory", () => {
+    // The finding, exactly. The organizations list survives a failed refresh
+    // in one path on purpose ("your session is intact -- retry in a moment"),
+    // so "the list is empty" was never a safe proxy for "signed out".
+    const profile = activeProfile(
+      { status: "anonymous", reason: "you have signed out" },
+      [ACME, BOREAL],
+    );
+    expect(profile).toBeNull();
+  });
+
+  it("🔴 follows the ACTIVE organization, not the first one", () => {
+    expect(activeProfile(authenticated(ACME.organizationId), [ACME, BOREAL])?.displayName).toBe(
+      "Kwame Chemist",
+    );
+    expect(activeProfile(authenticated(BOREAL.organizationId), [ACME, BOREAL])?.displayName).toBe(
+      "Esi Lead",
+    );
+  });
+
+  it("carries the user id from the session, which is the one global attribute", () => {
+    expect(activeProfile(authenticated(ACME.organizationId), [ACME, BOREAL])?.userId).toBe(
+      "44444444-4444-4444-4444-444444444444",
+    );
+  });
+
+  it("🔴 a blank name is an absent name, not an empty top bar entry", () => {
+    // The previous check was `!== undefined`, which `""` satisfies — so an API
+    // returning a blank produced "signed in as ''", which reads as a rendering
+    // fault rather than a missing field. The comment claimed this case was
+    // excluded; Codex measured that it was not.
+    const nameless: OrganizationChoice = { ...ACME, displayName: "  " };
+    expect(activeProfile(authenticated(ACME.organizationId), [nameless])).toBeNull();
+
+    const addressless: OrganizationChoice = { ...ACME, email: "" };
+    expect(activeProfile(authenticated(ACME.organizationId), [addressless])).toBeNull();
+  });
+
+  it("has no name for an organization it holds no membership for", () => {
+    // Reachable: a membership revoked between the token being issued and the
+    // list being refreshed. Showing the old name would be asserting a
+    // membership the server has already withdrawn.
+    expect(activeProfile(authenticated("99999999-9999-9999-9999-999999999999"), [ACME])).toBeNull();
+  });
+});
diff --git a/apps/web/components/providers/auth-provider.tsx b/apps/web/components/providers/auth-provider.tsx
index bc25485..0ec4d40 100644
--- a/apps/web/components/providers/auth-provider.tsx
+++ b/apps/web/components/providers/auth-provider.tsx
@@ -57,18 +57,27 @@ import { safeReturnTo, saveFlow } from "@/lib/auth/flow-state";
 import { authorizationUrl, createChallenge, refreshTokens } from "@/lib/auth/pkce";
 
 /**
- * Who the signed-in person is, as `/api/me` reports them.
+ * Who the signed-in person is, in the organization they are currently working in.
  *
- * 🔴 THE API HAS ALWAYS SENT THIS AND THE PROVIDER THREW IT AWAY.
- * `GET /api/me` returns `user_id`, `email` and `display_name` at the top level
- * beside `organizations`, and the parse below read only `organizations`. So the
- * application knew the caller's name on every load and had nowhere to put it —
- * which is why the top bar showed a grey circle with a dash in it.
+ * 🔴 DERIVED FROM THE ACTIVE MEMBERSHIP. NOT STORED, AND THAT IS THE FIX.
+ *
+ * It used to be its own `useState`, set from a top-level `display_name` on
+ * `/api/me`, and it went wrong in three directions at once. `signOut` cleared
+ * the session and the organizations and never cleared this, so the previous
+ * user's name stayed in the top bar of an anonymous application — on a shared
+ * bench machine, somebody else's name over your work. Switching organization
+ * did not change it. And the value itself was whichever tenant sorted first
+ * alphabetically, because migration 052 put the name on the MEMBERSHIP and the
+ * route flattened the rows back to one.
+ *
+ * All three were the same defect: a per-tenant fact kept as though it were a
+ * global one, in a second place, needing a second thing to remember to clear
+ * it. Derived from the active membership there is nothing to clear, nothing to
+ * refresh, and no second copy — the anonymous state has no active membership,
+ * so it has no name. Both reviewers found the first of the three; Codex found
+ * the second.
  *
  * ⚠️ THIS IS THE ORGANIZATION'S VIEW OF THE PERSON, not a global identity.
- * Migration 052 moved `email` and `display_name` onto the membership (I106);
- * `/api/me` resolves them through the same path, so what arrives here is the
- * name THIS tenant knows them by.
  */
 export interface UserProfile {
   readonly userId: string;
@@ -95,6 +104,9 @@ export interface OrganizationChoice {
   readonly organizationId: string;
   readonly name: string;
   readonly code: string;
+  /** What THIS organization calls the caller (052). Per-tenant, like the roles. */
+  readonly email: string;
+  readonly displayName: string;
   readonly roles: readonly string[];
   /**
    * Permission codes held in THIS organization (I79).
@@ -170,10 +182,45 @@ export function chooseOrganization(
   return first;
 }
 
+/**
+ * The caller as the organization they are working in knows them.
+ *
+ * 🔴 A BLANK NAME IS AN ABSENT NAME. The previous version required all three
+ * fields to be `!== undefined`, which an empty string satisfies — so an API
+ * returning `""` produced "signed in as ''" in the top bar, under a comment
+ * claiming that exact case was excluded. Codex found the gap between the
+ * comment and the check. Nothing here trims a name into existence: if either
+ * attribute is blank there is no profile, and `UserMenu` renders nothing rather
+ * than an initialled circle with no initials.
+ *
+ * Exported and pure so the rule can be tested without a network call or a
+ * React tree — the same reason `chooseOrganization` is.
+ */
+export function activeProfile(
+  session: SessionState,
+  organizations: readonly OrganizationChoice[],
+): UserProfile | null {
+  // Anonymous has no active membership, so it has no name. That is the whole
+  // of the "signOut must clear the profile" fix: there is no profile to clear.
+  if (session.status !== "authenticated") return null;
+
+  const active = organizations.find(
+    (org) => org.organizationId === session.credentials.organizationId,
+  );
+  if (active === undefined) return null;
+
+  if (active.displayName.trim() === "" || active.email.trim() === "") return null;
+
+  return {
+    userId: session.credentials.userId,
+    email: active.email,
+    displayName: active.displayName,
+  };
+}
+
 export function AuthProvider({ children }: { children: React.ReactNode }) {
   const session = useSession();
   const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
-  const [profile, setProfile] = useState<UserProfile | null>(null);
   const tokens = useRef<LiveTokens | null>(null);
   const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
   // 🔴 clearTimeout CANNOT STOP A REFRESH THAT IS ALREADY IN FLIGHT.
@@ -251,12 +298,12 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
 
     const body = (await response.json()) as {
       user_id?: string;
-      email?: string;
-      display_name?: string;
       organizations?: {
         organization_id: string;
         name: string;
         code: string;
+        email?: string;
+        display_name?: string;
         roles?: string[];
         permissions?: string[];
       }[];
@@ -266,6 +313,11 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
       organizationId: org.organization_id,
       name: org.name,
       code: org.code,
+      // 🔴 THE MEMBERSHIP'S OWN PAIR (052). An API too old to send them yields
+      // an empty string, which `useProfile` reads as "no name" rather than
+      // rendering "signed in as ''" — see the profile derivation below.
+      email: org.email ?? "",
+      displayName: org.display_name ?? "",
       roles: org.roles ?? [],
       // `?? []` and not `?? ALL_NAV_PERMISSIONS`: an API too old to send
       // permissions must yield a shell that shows LESS, never one that shows
@@ -274,21 +326,6 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
       permissions: org.permissions ?? [],
     }));
 
-    // 🔴 ONLY WHEN ALL THREE ARE PRESENT. A half-populated profile would put an
-    // empty string where a name goes, and "signed in as ''" is worse than no
-    // name at all — it looks like a rendering bug rather than an absent field.
-    setProfile(
-      body.user_id !== undefined &&
-        body.email !== undefined &&
-        body.display_name !== undefined
-        ? {
-            userId: body.user_id,
-            email: body.email,
-            displayName: body.display_name,
-          }
-        : null,
-    );
-
     const first = choices[0];
     if (first === undefined) {
       // Absence must never present as success. An empty list would render
@@ -556,6 +593,11 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
     [organizations],
   );
 
+  const profile = useMemo(
+    () => activeProfile(session, organizations),
+    [session, organizations],
+  );
+
   const value = useMemo<AuthContextValue>(
     () => ({
       session,
diff --git a/apps/web/components/providers/theme-provider.tsx b/apps/web/components/providers/theme-provider.tsx
index 00bcb8a..cfd41e3 100644
--- a/apps/web/components/providers/theme-provider.tsx
+++ b/apps/web/components/providers/theme-provider.tsx
@@ -24,17 +24,18 @@
 import { useEffect } from "react";
 
 import { readTheme } from "@/lib/preferences";
-import { CSS_VARIABLES, STATUS_VARIABLES, resolvePalette, type ThemeId } from "@/lib/theme";
+import { paletteVariables, resolvePalette, type ThemeId } from "@/lib/theme";
 
 function apply(theme: ThemeId, prefersDark: boolean): void {
   const palette = resolvePalette(theme, prefersDark);
   const root = document.documentElement;
 
-  for (const [key, variable] of Object.entries(CSS_VARIABLES)) {
-    root.style.setProperty(variable, palette[key as keyof typeof CSS_VARIABLES]);
-  }
-  for (const [key, variable] of Object.entries(STATUS_VARIABLES)) {
-    root.style.setProperty(variable, palette.status[key as keyof typeof STATUS_VARIABLES]);
+  // 🔴 THE SAME LIST THE PRE-PAINT SCRIPT USES. `paletteVariables` is the one
+  // producer; this provider and `app/layout.tsx` are its two consumers. When
+  // they each owned a loop, adding a variable to one meant the page changed
+  // colour the moment React arrived — the flash this pair exists to prevent.
+  for (const [variable, value] of Object.entries(paletteVariables(palette))) {
+    root.style.setProperty(variable, value);
   }
 
   // Which theme is active, for anything that needs to branch on it — and for a
diff --git a/apps/web/components/ui/entity-header.tsx b/apps/web/components/ui/entity-header.tsx
index 4ddecc8..81f6d20 100644
--- a/apps/web/components/ui/entity-header.tsx
+++ b/apps/web/components/ui/entity-header.tsx
@@ -22,6 +22,25 @@
 import Link from "next/link";
 import type { ReactNode } from "react";
 
+/**
+ * A count for a header field, or an em dash while it is not yet known.
+ *
+ * 🔴 "0" IS AN ANSWER AND AN EMPTY LIST BEFORE THE RESPONSE ARRIVES IS NOT.
+ *
+ * Every Administration header rendered `String(rows.length)` over a list that
+ * starts empty, so each one reported **0 roles**, **0 permissions**, **0
+ * stages** for the whole of the first request — and reported exactly the same
+ * thing when the caller lacked the permission to read it, and again when the
+ * request failed. A reader cannot tell "there are none" from "nobody has said
+ * yet", and this application has already shipped the same shape once, where an
+ * empty requirement set rendered ALL REQUIREMENTS PASSED. Codex found it.
+ *
+ * Absence must never present as an answer.
+ */
+export function headerCount(rows: { readonly length: number }, known: boolean): string {
+  return known ? String(rows.length) : "—";
+}
+
 export interface Crumb {
   label: string;
   href: string;
diff --git a/apps/web/components/ui/radio-cards.tsx b/apps/web/components/ui/radio-cards.tsx
new file mode 100644
index 0000000..ce7dc5f
--- /dev/null
+++ b/apps/web/components/ui/radio-cards.tsx
@@ -0,0 +1,133 @@
+"use client";
+
+/**
+ * A radiogroup of cards — one choice among a handful, each with a description.
+ *
+ * 🔴 IT EXISTS BECAUSE `role="radiogroup"` IS A PROMISE ABOUT THE KEYBOARD.
+ *
+ * The settings screen declared two of them over rows of ordinary buttons, with
+ * a comment saying arrow-key navigation "is what a screen reader user expects
+ * from a radiogroup and does not get from a row of buttons" — and then did not
+ * implement it. So the role announced a widget whose keyboard behaviour was
+ * absent: every option was a separate tab stop, arrow keys did nothing, and a
+ * screen reader told the user to press arrows that had no effect. The
+ * Supervisor found it. That is worse than the plain buttons the comment was
+ * arguing against, because the plain buttons at least behave the way they are
+ * announced.
+ *
+ * ⚠️ SELECTION FOLLOWS FOCUS, which is the WAI-ARIA radiogroup pattern and not
+ * an oversight. Arrowing to an option chooses it. That is right here for the
+ * same reason the screen has no Save button: both choices apply immediately and
+ * are reversible in one keystroke, so there is nothing to confirm.
+ *
+ * 🔴 ROVING TABINDEX, so the group is ONE tab stop rather than five. Five
+ * separate stops in the middle of a settings page is exactly the keyboard
+ * treacle §11 exists to prevent, and it is what the previous buttons did.
+ */
+
+import { useRef } from "react";
+
+export interface RadioCardOption<T extends string> {
+  readonly id: T;
+  readonly label: string;
+  /** One line a person can choose by, not a restatement of the label. */
+  readonly description: string;
+  /** Optional visual, e.g. a palette swatch. Decorative; never the only cue. */
+  readonly preview?: React.ReactNode;
+}
+
+const TAG =
+  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
+  "tracking-wide text-slate-600";
+
+export function RadioCards<T extends string>({
+  labelledBy,
+  options,
+  value,
+  onChange,
+}: {
+  readonly labelledBy: string;
+  readonly options: readonly RadioCardOption<T>[];
+  readonly value: T;
+  readonly onChange: (next: T) => void;
+}) {
+  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
+
+  const move = (from: number, delta: number) => {
+    // Wrapping, because a radiogroup is a ring: arrowing past the end of five
+    // options and stopping dead reads as a broken control rather than a
+    // boundary.
+    const next = (from + delta + options.length) % options.length;
+    const option = options[next];
+    if (option === undefined) return;
+    onChange(option.id);
+    buttons.current[next]?.focus();
+  };
+
+  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
+    switch (event.key) {
+      case "ArrowDown":
+      case "ArrowRight":
+        event.preventDefault();
+        move(index, 1);
+        break;
+      case "ArrowUp":
+      case "ArrowLeft":
+        event.preventDefault();
+        move(index, -1);
+        break;
+      case "Home":
+        event.preventDefault();
+        move(index, -index);
+        break;
+      case "End":
+        event.preventDefault();
+        move(index, options.length - 1 - index);
+        break;
+      default:
+        break;
+    }
+  };
+
+  return (
+    <div role="radiogroup" aria-labelledby={labelledBy} className="mt-3 grid gap-2">
+      {options.map((option, index) => {
+        const chosen = option.id === value;
+        return (
+          <button
+            key={option.id}
+            ref={(element) => {
+              buttons.current[index] = element;
+            }}
+            type="button"
+            role="radio"
+            aria-checked={chosen}
+            // 🔴 THE GROUP IS ONE TAB STOP. Only the selected option is
+            // reachable by Tab; the arrows move within. A group where every
+            // option is tabbable is the thing this component replaced.
+            tabIndex={chosen ? 0 : -1}
+            onClick={() => onChange(option.id)}
+            onKeyDown={(event) => onKeyDown(event, index)}
+            className={[
+              "flex items-center gap-3 rounded border p-3 text-left",
+              chosen
+                ? "border-slate-900 bg-slate-50"
+                : "border-slate-200 bg-white hover:bg-slate-50",
+            ].join(" ")}
+          >
+            {option.preview}
+            <span className="min-w-0 flex-1">
+              <span className="block text-sm font-medium text-slate-900">{option.label}</span>
+              <span className="block text-xs text-slate-600">{option.description}</span>
+            </span>
+            {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by colour
+                or shape alone, and "which one is selected" is state.
+                `aria-checked` says it assistively; this says it to everyone
+                else. */}
+            {chosen && <span className={TAG}>selected</span>}
+          </button>
+        );
+      })}
+    </div>
+  );
+}
diff --git a/apps/web/lib/accessibility-coverage.test.ts b/apps/web/lib/accessibility-coverage.test.ts
new file mode 100644
index 0000000..cb89edf
--- /dev/null
+++ b/apps/web/lib/accessibility-coverage.test.ts
@@ -0,0 +1,127 @@
+/**
+ * 🔴 A PAGE ABSENT FROM THE ACCESSIBILITY SWEEP IS A PAGE NOBODY CHECKED.
+ *
+ * `tests/e2e/shell/accessibility.spec.ts` runs axe-core against WCAG 2.1 AA on
+ * a hand-maintained list of paths. §11 requires accessibility of the product,
+ * not of a list — and the list grows only when somebody remembers to add to it.
+ *
+ * The Supervisor found `/admin/roles` and `/admin/permissions` missing, shipped
+ * in the same commit as the sweep entries beside them. Asking the wider
+ * question — which routes exist, and which are in the list — found **eight
+ * more**: `/analytics`, `/knowledge`, `/reports` and all five workspace routes,
+ * some uncovered since the slice that built them. The list has always looked
+ * complete, because a list that grows by memory looks exactly like a list that
+ * is finished.
+ *
+ * So the list is derived from the filesystem and compared. This is the same
+ * shape as `sections.catalogue.test.ts` reading the seed SQL and
+ * `decisions.test.ts` reading `Field(pattern=…)`: the test reads the OTHER
+ * tier rather than a copy of it. A hand-written list checked against a
+ * hand-written list proves only that somebody typed twice.
+ *
+ * ⚠️ EXEMPTIONS ARE NAMED HERE, WITH A REASON, and there are two. An exemption
+ * that is merely a filter would let the next reader delete a page from the
+ * sweep by adding a pattern.
+ */
+import { readFileSync, readdirSync } from "node:fs";
+import { join } from "node:path";
+
+import { describe, expect, it } from "vitest";
+
+const APP = join(__dirname, "..", "app");
+const SPEC = join(__dirname, "..", "..", "..", "tests", "e2e", "shell", "accessibility.spec.ts");
+
+/**
+ * Routes the sweep does not cover, and why.
+ *
+ * Not "pages that are awkward to test" — pages that axe-core running against
+ * the application shell cannot meaningfully assert.
+ */
+const EXEMPT = new Map<string, string>([
+  [
+    "/",
+    "the front door redirects on mount, so by the time axe could run the " +
+      "browser is on the landing screen — which IS swept. Its no-JavaScript " +
+      "content is one heading and one link.",
+  ],
+  [
+    "/auth/callback",
+    "reached only with a live authorization code from Keycloak. Opened " +
+      "directly it renders its own refusal, and the sweep drives no OIDC flow.",
+  ],
+]);
+
+/** Every route with a `page.tsx`, as the router will serve it. */
+function routes(directory: string, prefix = ""): string[] {
+  const found: string[] = [];
+  for (const entry of readdirSync(directory, { withFileTypes: true })) {
+    if (entry.isDirectory()) {
+      found.push(...routes(join(directory, entry.name), `${prefix}/${entry.name}`));
+    } else if (entry.name === "page.tsx") {
+      found.push(prefix === "" ? "/" : prefix);
+    }
+  }
+  return found;
+}
+
+/** The paths the sweep actually visits. */
+function swept(): string[] {
+  const spec = readFileSync(SPEC, "utf8");
+  return [...spec.matchAll(/path:\s*"([^"]+)"/g)].map((match) => match[1] as string);
+}
+
+describe("the accessibility sweep covers the application", () => {
+  it("reads a real spec with a real list", () => {
+    // 🔴 THE GUARD ON THE GUARD. If the spec is renamed or the shape of its
+    // list changes, `swept()` returns nothing and every assertion below passes
+    // vacuously — a check that walks through its own gap.
+    expect(swept().length).toBeGreaterThan(20);
+    expect(routes(APP).length).toBeGreaterThan(20);
+  });
+
+  it("🔴 every route is either swept or exempt with a stated reason", () => {
+    const paths = swept();
+
+    const uncovered = routes(APP).filter((route) => {
+      if (EXEMPT.has(route)) return false;
+      // A dynamic segment is covered by any concrete path under the same
+      // prefix — the sweep visits `/projects/RDP-2026-014` for
+      // `/projects/[code]`, which is the only way to visit it at all.
+      const dynamic = route.indexOf("/[");
+      if (dynamic !== -1) {
+        const parent = route.slice(0, dynamic);
+        return !paths.some((path) => path.startsWith(`${parent}/`) && path !== parent);
+      }
+      return !paths.includes(route);
+    });
+
+    expect(
+      uncovered.sort(),
+      "these routes render in a browser and no accessibility check has ever " +
+        "run against them. Add them to tests/e2e/shell/accessibility.spec.ts, " +
+        "or exempt them in EXEMPT above with the reason",
+    ).toEqual([]);
+  });
+
+  it("sweeps nothing that does not exist", () => {
+    // The other direction. A path left behind by a deleted or renamed route
+    // makes the sweep visit a 404, which axe-core reports as clean — coverage
+    // that measures a Next.js error page.
+    const existing = routes(APP);
+    const stale = swept().filter((path) => {
+      if (existing.includes(path)) return false;
+      // Concrete instances of a dynamic route: `/projects/RDP-2026-014`.
+      const parent = path.slice(0, path.lastIndexOf("/"));
+      return !existing.some((route) => route.startsWith(`${parent}/[`));
+    });
+
+    expect(stale, "the sweep visits paths that no longer have a page").toEqual([]);
+  });
+
+  it("every exemption names a route that exists", () => {
+    // An exemption for a deleted route is a hole nobody can see: it silences
+    // nothing today and silences whatever takes that path tomorrow.
+    const existing = new Set(routes(APP));
+    expect([...EXEMPT.keys()].filter((route) => !existing.has(route))).toEqual([]);
+  });
+});
diff --git a/apps/web/lib/permissions.test.ts b/apps/web/lib/permissions.test.ts
index 35de0d6..19e7eef 100644
--- a/apps/web/lib/permissions.test.ts
+++ b/apps/web/lib/permissions.test.ts
@@ -59,6 +59,8 @@ const TECHNICIAN: OrganizationChoice = {
   organizationId: ACME_ID,
   name: "Acme Coatings",
   code: "ACME",
+  email: "tech@acme.example",
+  displayName: "Ama Technician",
   roles: ["laboratory_technician"],
   // The real figure, measured against the seeded realm on 2026-08-25:
   // tech.demo holds 11 permissions and lead.demo holds 38.
@@ -147,6 +149,8 @@ describe("effectiveNavPermissions", () => {
       organizationId: OTHER_ID,
       name: "Boreal Adhesives",
       code: "BOR",
+      email: "esi.lead@boreal.example",
+      displayName: "Esi Lead",
       roles: ["product_development_lead"],
       permissions: ["product.release"],
     };
diff --git a/apps/web/lib/preferences.ts b/apps/web/lib/preferences.ts
index e24dae4..ea4e257 100644
--- a/apps/web/lib/preferences.ts
+++ b/apps/web/lib/preferences.ts
@@ -1,7 +1,7 @@
 "use client";
 
 /**
- * What this person prefers — theme, and where they land after signing in.
+ * What this person prefers — theme, and where the application opens.
  *
  * 🔴 STORED IN THE BROWSER, AND THAT IS A DECISION RATHER THAN A SHORTCUT.
  *
@@ -24,16 +24,27 @@
 
 import { useCallback, useEffect, useState } from "react";
 
-import { DEFAULT_THEME, isThemeId, type ThemeId } from "./theme";
+import { DEFAULT_THEME, THEME_STORAGE_KEY, isThemeId, type ThemeId } from "./theme";
 
-const THEME_KEY = "evercoat.theme";
+// 🔴 IMPORTED, NOT REPEATED. The pre-paint script in `app/layout.tsx` reads the
+// same key before this module exists, and two spellings of a storage key cannot
+// be type-checked into agreement — the reader would simply find nothing and
+// paint the default, forever, with every test green.
+const THEME_KEY = THEME_STORAGE_KEY;
 const LANDING_KEY = "evercoat.landing";
 
 /**
- * Where a person lands after signing in.
+ * Where the application opens.
  *
  * Three, and each is a real destination that exists today — a preference
  * pointing at an unbuilt screen would be a setting whose only effect is a 404.
+ *
+ * 🔴 ITS READER IS `app/page.tsx`, AND FOR A WHILE IT HAD NONE. The front door
+ * redirected to a hard-coded `/dashboard`, so this value was written by the
+ * settings screen, validated on the way back out, and consulted by nothing.
+ * Both reviewers found it. Because `/` resolves here before anybody presses
+ * Sign in, it is also what sign-in returns you to — `signIn()` remembers where
+ * you were, and where you were is this.
  */
 export const LANDING_SCREENS = [
   {
diff --git a/apps/web/lib/theme.test.ts b/apps/web/lib/theme.test.ts
index 88f1d01..2b26a4d 100644
--- a/apps/web/lib/theme.test.ts
+++ b/apps/web/lib/theme.test.ts
@@ -19,16 +19,27 @@
  * only for decoration and for disabled controls, which WCAG 1.4.3 exempts and
  * which this codebase deliberately does not rely on to convey state.
  */
+import { readFileSync, readdirSync } from "node:fs";
+import { join } from "node:path";
+
 import { describe, expect, it } from "vitest";
 
+import tailwindConfig from "../tailwind.config";
 import {
+  ACCENT_NAMES,
+  ACCENT_STEPS,
   CSS_VARIABLES,
   PALETTES,
   STATUS_VARIABLES,
   THEMES,
+  THEME_STORAGE_KEY,
+  accentVariable,
   contrast,
   luminance,
+  paletteVariables,
+  prePaintScript,
   resolvePalette,
+  type Palette,
 } from "./theme";
 
 /** The steps this application actually uses for TEXT, with their usage counts. */
@@ -145,6 +156,7 @@ describe("theme palettes", () => {
         palette.slate700,
         palette.slate800,
         palette.slate900,
+        palette.slate950,
       ].map(luminance);
 
       const descending = steps.every((value, i) => i === 0 || value <= (steps[i - 1] ?? 1));
@@ -167,7 +179,7 @@ describe("theme palettes", () => {
     // would simply never be applied, and the step would silently keep the
     // previous theme's value.
     const keys = Object.keys(PALETTES.light)
-      .filter((key) => key !== "status")
+      .filter((key) => key !== "status" && key !== "accents")
       .sort();
     expect(Object.keys(CSS_VARIABLES).sort()).toEqual(keys);
     expect(Object.keys(STATUS_VARIABLES).sort()).toEqual(
@@ -175,3 +187,283 @@ describe("theme palettes", () => {
     );
   });
 });
+
+/* -------------------------------------------------------------------------- */
+/* The pairs that actually appear together                                     */
+/* -------------------------------------------------------------------------- */
+
+/**
+ * 🔴 THE CONTRAST TEST ABOVE MEASURED THE WRONG THING, AND SHIPPED A 1.65:1
+ * BADGE.
+ *
+ * It checks every status colour against `palette.white` — the page. A
+ * `StatusBadge` does not sit on the page: it sits on `bg-emerald-50`, and while
+ * the status colours moved with the theme the accent ramps did not, so on dark
+ * the pass badge was lightened text on a ground that had stayed light. Measured
+ * afterwards: **1.65:1**. Codex found it.
+ *
+ * So this reads the SOURCE and measures what the source pairs. A class string
+ * naming both a background and a foreground is an element whose two colours
+ * will be seen together; there is no judgement here about which pairs matter,
+ * which is the point — a hand-written list of pairs is the hand-copied list
+ * this project has already been caught by twice.
+ */
+
+/** Every `.tsx` under the given root. */
+function sources(root: string, found: string[] = []): string[] {
+  for (const entry of readdirSync(root, { withFileTypes: true })) {
+    const path = join(root, entry.name);
+    if (entry.isDirectory()) sources(path, found);
+    else if (entry.name.endsWith(".tsx")) found.push(path);
+  }
+  return found;
+}
+
+/** The palette value a Tailwind colour utility resolves to, or null if it is not a colour. */
+function resolve(token: string, palette: Palette): string | null {
+  const status = /^(?:bg|text|border)-status-(pass|fail|conditional|invalid|neutral)$/.exec(token);
+  if (status !== null) return palette.status[status[1] as keyof typeof palette.status];
+
+  if (/^(?:bg|text|border)-white$/.test(token)) return palette.white;
+
+  const slate = /^(?:bg|text|border)-slate-(50|100|200|300|400|500|600|700|800|900|950)$/.exec(
+    token,
+  );
+  if (slate !== null) return palette[`slate${slate[1] as string}` as keyof Palette] as string;
+
+  const accent = new RegExp(
+    "^(?:bg|text|border)-(" + ACCENT_NAMES.join("|") + ")-(" + ACCENT_STEPS.join("|") + ")$",
+  ).exec(token);
+  if (accent !== null) {
+    return palette.accents[accent[1] as (typeof ACCENT_NAMES)[number]][
+      accent[2] as (typeof ACCENT_STEPS)[number]
+    ];
+  }
+
+  return null;
+}
+
+interface Pairing {
+  readonly file: string;
+  readonly background: string;
+  readonly foreground: string;
+}
+
+/** Class strings in the source that name a background AND a foreground. */
+function pairings(): Pairing[] {
+  const found: Pairing[] = [];
+  const roots = [join(__dirname, "..", "app"), join(__dirname, "..", "components")];
+
+  for (const root of roots) {
+    for (const file of sources(root)) {
+      const text = readFileSync(file, "utf8");
+      // Runs of class names between quotes. Deliberately crude: a run that
+      // happens to contain a background and a foreground is exactly the thing
+      // being looked for, and a false positive costs one measurement.
+      for (const literal of text.match(/"[^"\n]{0,400}"/g) ?? []) {
+        const tokens = literal.slice(1, -1).split(/\s+/);
+        const background = tokens.find((token) => token.startsWith("bg-"));
+        if (background === undefined) continue;
+        for (const token of tokens) {
+          if (!token.startsWith("text-") && !token.startsWith("border-")) continue;
+          found.push({ file: file.replace(/\\/g, "/"), background, foreground: token });
+        }
+      }
+    }
+  }
+  return found;
+}
+
+describe("the colours that appear together", () => {
+  it("finds real pairings to measure", () => {
+    // 🔴 A SCANNER THAT FINDS NOTHING PASSES EVERYTHING. This is the guard that
+    // stops the test below from going green because a regex stopped matching.
+    const measurable = pairings().filter(
+      (pair) =>
+        resolve(pair.background, PALETTES.light) !== null &&
+        resolve(pair.foreground, PALETTES.light) !== null,
+    );
+    expect(measurable.length).toBeGreaterThan(40);
+  });
+
+  it("🔴 text stays readable on the ground it is actually painted on, in every theme", () => {
+    const failures: string[] = [];
+
+    for (const [name, palette] of Object.entries(PALETTES)) {
+      for (const pair of pairings()) {
+        if (!pair.foreground.startsWith("text-")) continue;
+        const background = resolve(pair.background, palette);
+        const foreground = resolve(pair.foreground, palette);
+        if (background === null || foreground === null) continue;
+
+        const ratio = contrast(foreground, background);
+        if (ratio < 4.5) {
+          failures.push(
+            `${name}: ${pair.foreground} on ${pair.background} = ${ratio.toFixed(2)}:1`,
+          );
+        }
+      }
+    }
+
+    expect([...new Set(failures)].sort()).toEqual([]);
+  });
+
+  it("🔴 no theme makes a border LESS visible than the shipped default does", () => {
+    // 🔴 THE ABSOLUTE THRESHOLD WAS THE WRONG MEASUREMENT, AND IT FAILED THE
+    // SHIPPED DESIGN.
+    //
+    // Written as "every border clears 1.35:1" this refused the LIGHT theme:
+    // `border-slate-200` on `bg-white` is 1.23:1, and that is Tailwind's own
+    // pairing, used across the entire product, accepted long before themes
+    // existed. A guard that refuses the accepted default is not finding a
+    // defect; it is a second opinion about a decision already made.
+    //
+    // What a THEME can be held to is that it does not make things worse. So
+    // each pair is measured against the same pair on light, which is the
+    // property this change could actually break.
+    const failures: string[] = [];
+
+    for (const [name, palette] of Object.entries(PALETTES)) {
+      if (name === "light") continue;
+      for (const pair of pairings()) {
+        if (!pair.foreground.startsWith("border-")) continue;
+        const background = resolve(pair.background, palette);
+        const foreground = resolve(pair.foreground, palette);
+        if (background === null || foreground === null) continue;
+
+        const reference = contrast(
+          resolve(pair.foreground, PALETTES.light) as string,
+          resolve(pair.background, PALETTES.light) as string,
+        );
+        // An edge the default deliberately does not draw -- `border-slate-900`
+        // on `bg-slate-900`, the primary button -- has nothing to preserve.
+        if (reference < 1.05) continue;
+
+        // Capped at WCAG 1.4.11's non-text threshold: once a border clears
+        // 3:1 it is visible, and holding a 17:1 pairing to 14.5:1 is arithmetic
+        // rather than legibility. Below 3:1 -- which is where every alert box
+        // border in this product sits -- the theme must not erode it.
+        const required = Math.min(reference * 0.85, 3);
+        const ratio = contrast(foreground, background);
+        if (ratio < required) {
+          failures.push(
+            `${name}: ${pair.foreground} on ${pair.background} = ${ratio.toFixed(2)}:1 ` +
+              `against ${reference.toFixed(2)}:1 on light`,
+          );
+        }
+      }
+    }
+
+    expect([...new Set(failures)].sort()).toEqual([]);
+  });
+});
+
+/* -------------------------------------------------------------------------- */
+/* One producer                                                                */
+/* -------------------------------------------------------------------------- */
+
+describe("tailwind resolves through the palette and nothing else", () => {
+  /** Every `rgb(var(--x, R G B) / <alpha-value>)` in the built config. */
+  function configTokens(): Map<string, string> {
+    const found = new Map<string, string>();
+    const walk = (value: unknown): void => {
+      if (typeof value === "string") {
+        const match = /^rgb\(var\((--[a-z0-9-]+),\s*([0-9 ]+)\)\s*\/\s*<alpha-value>\)$/.exec(value);
+        if (match !== null) found.set(match[1] as string, (match[2] as string).trim());
+        return;
+      }
+      if (value !== null && typeof value === "object") {
+        Object.values(value as Record<string, unknown>).forEach(walk);
+      }
+    };
+    walk(tailwindConfig.theme?.extend?.colors);
+    return found;
+  }
+
+  it("🔴 every themed colour in the config falls back to the LIGHT palette", () => {
+    // `tailwind.config.ts` used to CLAIM this test existed while it did not,
+    // over 60 hand-copied triples. The config now imports the palette, so there
+    // is nothing to drift — and this measures the RESOLVED config rather than
+    // trusting that, so re-hardcoding a value is caught rather than assumed
+    // impossible.
+    const light = paletteVariables(PALETTES.light);
+    const drifted: string[] = [];
+
+    for (const [variable, fallback] of configTokens()) {
+      if (light[variable] !== fallback) {
+        drifted.push(`${variable}: config ${fallback} vs palette ${light[variable] ?? "absent"}`);
+      }
+    }
+
+    expect(drifted).toEqual([]);
+  });
+
+  it("🔴 every variable a theme sets is reachable from a Tailwind class", () => {
+    // The other direction, and the one that caught `slate-950`: a variable the
+    // provider writes that no utility reads is a colour that never moves — and
+    // Tailwind DEEP-MERGES a partial scale, so the missing step silently keeps
+    // its built-in literal instead of failing.
+    const inConfig = new Set(configTokens().keys());
+    const missing = Object.keys(paletteVariables(PALETTES.light)).filter(
+      (variable) => !inConfig.has(variable),
+    );
+
+    expect(missing).toEqual([]);
+  });
+
+  it("names a CSS variable for every accent step", () => {
+    const variables = paletteVariables(PALETTES.light);
+    for (const name of ACCENT_NAMES) {
+      for (const step of ACCENT_STEPS) {
+        expect(variables[accentVariable(name, step)]).toBe(PALETTES.light.accents[name][step]);
+      }
+    }
+  });
+
+  it("🔴 no themed palette leaves an accent ramp at Tailwind's own values", () => {
+    // The half-theme, stated as an assertion.
+    for (const [name, palette] of Object.entries(PALETTES)) {
+      if (name === "light") continue;
+      const unchanged = ACCENT_NAMES.filter((hue) =>
+        ACCENT_STEPS.every(
+          (step) => palette.accents[hue][step] === PALETTES.light.accents[hue][step],
+        ),
+      );
+      expect(unchanged, `${name} left these ramps at the light values`).toEqual([]);
+    }
+  });
+});
+
+describe("the pre-paint script", () => {
+  const script = prePaintScript();
+
+  it("reads the same storage key the application writes", () => {
+    expect(script).toContain(JSON.stringify(THEME_STORAGE_KEY));
+  });
+
+  it("🔴 carries every variable the React provider sets", () => {
+    // A property in one and not the other is a colour that changes at
+    // hydration — the same flash, arriving later and harder to see.
+    for (const variable of Object.keys(paletteVariables(PALETTES.dark))) {
+      expect(script).toContain(variable);
+    }
+  });
+
+  it("carries all four palettes, and the dark one is really dark", () => {
+    const payload = /var P=(\{.*?\}),K=/.exec(script);
+    expect(payload).not.toBeNull();
+    const palettes = JSON.parse((payload as RegExpExecArray)[1] as string) as Record<
+      string,
+      Record<string, string>
+    >;
+    expect(Object.keys(palettes).sort()).toEqual(["contrast", "dark", "light", "paper"]);
+    expect(palettes["dark"]?.[CSS_VARIABLES.white]).toBe(PALETTES.dark.white);
+  });
+
+  it("is one self-contained expression that cannot throw out of the document", () => {
+    // It runs before anything else exists. `localStorage` throws outright in
+    // some private windows, and an exception here would be an unstyled page.
+    expect(script.startsWith("(function(){try{")).toBe(true);
+    expect(script.endsWith("}catch(e){}})();")).toBe(true);
+  });
+});
diff --git a/apps/web/lib/theme.ts b/apps/web/lib/theme.ts
index 1f81cd0..f68ae91 100644
--- a/apps/web/lib/theme.ts
+++ b/apps/web/lib/theme.ts
@@ -3,20 +3,37 @@
  *
  * 🔴 WHY THIS WORKS WITHOUT TOUCHING A SINGLE COMPONENT.
  *
- * Measured across `app/` and `components/`, this application draws from a very
- * small palette: `white` and `slate-50…900` as background, text and border,
- * plus the four traffic-light tokens. `text-slate-600` alone appears 247 times.
+ * Measured across `app/` and `components/`, this application draws from a small
+ * palette: `white` and `slate-50…950` as background, text and border, the four
+ * traffic-light tokens, and seven accent ramps used for notices and alert boxes.
+ * `text-slate-600` alone appears 247 times.
  *
- * So the themes redefine THE SCALE rather than the call sites. `tailwind.config`
- * resolves each slate step to a CSS custom property, a theme sets those
- * properties on `<html>`, and every existing `bg-white` / `text-slate-600` /
- * `border-slate-200` follows. No component knows a theme exists — which is also
- * why a component cannot opt out of one and quietly stay light.
+ * So the themes redefine THE SCALES rather than the call sites. `tailwind.config`
+ * resolves each step to a CSS custom property, a theme sets those properties on
+ * `<html>`, and every existing `bg-white` / `text-slate-600` / `bg-red-50`
+ * follows. No component knows a theme exists.
+ *
+ * 🔴 AND THE FIRST VERSION OF THAT SENTENCE WAS FALSE FOR 129 CALL SITES.
+ *
+ * It said "no component knows a theme exists — which is also why a component
+ * cannot opt out of one and quietly stay light", over a file that themed only
+ * `white` and `slate-50…900`. Everything else stayed literal: every
+ * `bg-red-50` alert box, every `border-amber-300`, `slate-950`, and — worst —
+ * `StatusBadge`, whose `bg-emerald-50` ground stayed light while its
+ * `text-status-pass` had just been LIGHTENED for a dark surface. Measured on
+ * the badge's own ground rather than on the page: **1.65:1 for pass, 2.53:1 for
+ * fail, 1.61:1 for conditional.** The contrast test did not see it because it
+ * measured status colours against `palette.white`, which is not what a badge
+ * sits on. Both reviewers found it independently.
+ *
+ * A partial theme is a theme with a lie in its header. Every ramp the product
+ * actually paints with is now themed, and `theme.test.ts` measures the PAIRS
+ * that appear together in the source rather than text-on-surface alone.
  *
  * ⚠️ THIS IS NOT `packages/design-tokens`, AND MUST NOT BE MISTAKEN FOR IT.
  * Extension slice E5 builds a real token layer — primitive → semantic →
  * component, exported to a Tailwind preset, with Storybook and per-story
- * axe-core. This is the interim: one ramp, remapped. When E5 lands, these
+ * axe-core. This is the interim: the ramps, remapped. When E5 lands, these
  * palettes become token sets and this file goes away.
  *
  * 🔴 THE STATUS COLOURS NEEDED A SECOND SET, AND THE TEST IS WHAT FOUND OUT.
@@ -86,9 +103,218 @@ const STATUS_ON_DARK: StatusColours = {
   neutral: "161 161 170",
 };
 
-/** The slate ramp plus the surface, as `R G B` triples for `rgb()`. */
+/* -------------------------------------------------------------------------- */
+/* The accent ramps                                                            */
+/* -------------------------------------------------------------------------- */
+
+/**
+ * The seven hues this product paints with beyond slate, measured from source.
+ *
+ * Not "the ones Tailwind ships" — the ones actually used. `red` and `amber`
+ * carry alerts and warnings, `emerald` carries the pass badge, and `purple`,
+ * `sky`, `rose` and `orange` distinguish record kinds in the knowledge and MSD
+ * surfaces. A hue nothing uses would be a variable set on every page load for
+ * nothing.
+ */
+export const ACCENT_NAMES = ["red", "amber", "emerald", "purple", "sky", "rose", "orange"] as const;
+export type AccentName = (typeof ACCENT_NAMES)[number];
+
+/**
+ * The steps used, in lightness order.
+ *
+ * 🔴 THESE ARE THE STEPS THE SOURCE NAMES, NOT A TIDY SUBSET. `border-amber-400`
+ * appears once and `text-red-800` twice; dropping either would mean two call
+ * sites silently keeping Tailwind's literal value while the rest of their own
+ * ramp moved — which is the half-theme this whole change exists to end.
+ */
+export const ACCENT_STEPS = ["50", "200", "300", "400", "700", "800", "900"] as const;
+export type AccentStep = (typeof ACCENT_STEPS)[number];
+
+export type Accent = Readonly<Record<AccentStep, string>>;
+export type Accents = Readonly<Record<AccentName, Accent>>;
+
+/** Tailwind's own values for every step this product uses. The default must not move. */
+const ACCENTS_ON_LIGHT: Accents = {
+  red: {
+    "50": "254 242 242",
+    "200": "254 202 202",
+    "300": "252 165 165",
+    "400": "248 113 113",
+    "700": "185 28 28",
+    "800": "153 27 27",
+    "900": "127 29 29",
+  },
+  amber: {
+    "50": "255 251 235",
+    "200": "253 230 138",
+    "300": "252 211 77",
+    "400": "251 191 36",
+    "700": "180 83 9",
+    "800": "146 64 14",
+    "900": "120 53 15",
+  },
+  emerald: {
+    "50": "236 253 245",
+    "200": "167 243 208",
+    "300": "110 231 183",
+    "400": "52 211 153",
+    "700": "4 120 87",
+    "800": "6 95 70",
+    "900": "6 78 59",
+  },
+  purple: {
+    "50": "250 245 255",
+    "200": "233 213 255",
+    "300": "216 180 254",
+    "400": "192 132 252",
+    "700": "126 34 206",
+    "800": "107 33 168",
+    "900": "88 28 135",
+  },
+  sky: {
+    "50": "240 249 255",
+    "200": "186 230 253",
+    "300": "125 211 252",
+    "400": "56 189 248",
+    "700": "3 105 161",
+    "800": "7 89 133",
+    "900": "12 74 110",
+  },
+  rose: {
+    "50": "255 241 242",
+    "200": "254 205 211",
+    "300": "253 164 175",
+    "400": "251 113 133",
+    "700": "190 18 60",
+    "800": "159 18 57",
+    "900": "136 19 55",
+  },
+  orange: {
+    "50": "255 247 237",
+    "200": "254 215 170",
+    "300": "253 186 116",
+    "400": "251 146 60",
+    "700": "194 65 12",
+    "800": "154 52 18",
+    "900": "124 45 18",
+  },
+};
+
+/**
+ * The two steps beyond the ones the product names, per hue.
+ *
+ * 🔴 THE REVERSAL NEEDED MORE ROOM THAN THE PRODUCT'S OWN STEPS GAVE IT, AND
+ * THE PAIRING TEST IS WHAT SAID SO.
+ *
+ * Reversing `50…900` onto itself put the dark alert ground at the hue's `900`,
+ * and `text-status-fail` on that ground measured **3.62:1** — below AA, on the
+ * fail badge, which is the single element in this product that most has to be
+ * read correctly. That is the same defect Codex found one layer down, caught
+ * this time by measurement rather than by a reviewer.
+ *
+ * `950` is dark enough to hold light text and `100` is light enough to be it,
+ * and both are values Tailwind already ships for that hue — so the dark theme
+ * still invents no colour.
+ */
+const ACCENT_ENDS: Readonly<Record<AccentName, { readonly "100": string; readonly "950": string }>> =
+  {
+    red: { "100": "254 226 226", "950": "69 10 10" },
+    amber: { "100": "254 243 199", "950": "69 26 3" },
+    emerald: { "100": "209 250 229", "950": "2 44 34" },
+    purple: { "100": "243 232 255", "950": "59 7 100" },
+    sky: { "100": "224 242 254", "950": "8 47 73" },
+    rose: { "100": "255 228 230", "950": "76 5 25" },
+    orange: { "100": "255 237 213", "950": "67 20 7" },
+  };
+
+/**
+ * The dark accent set: each ramp REVERSED within its own hue.
+ *
+ * 🔴 A REVERSAL RATHER THAN A RE-TINT, FOR THE SAME REASON THE SLATE RAMP IS
+ * REVERSED. `bg-red-50` is the ground an alert sits on and `text-red-900` is
+ * its text; on a dark surface the ground has to become the dark end and the
+ * text the light end, or the box stays a white rectangle on a dark page. Every
+ * pairing in the source is (light step, dark step) of one hue, so swapping the
+ * ends keeps every pair readable while moving the box onto the page.
+ *
+ * `400` is the axis of the reversal and stays where it is.
+ */
+function reversed(name: AccentName): Accent {
+  const accent = ACCENTS_ON_LIGHT[name];
+  const ends = ACCENT_ENDS[name];
+  return {
+    "50": ends["950"],
+    "200": accent["900"],
+    "300": accent["800"],
+    "400": accent["400"],
+    "700": accent["300"],
+    "800": accent["200"],
+    "900": ends["100"],
+  };
+}
+
+/** Mix two `R G B` triples in sRGB space. `t = 0` is `a`, `t = 1` is `b`. */
+function mix(a: string, b: string, t: number): string {
+  const left = a.split(/\s+/).map(Number);
+  const right = b.split(/\s+/).map(Number);
+  return [0, 1, 2]
+    .map((i) => Math.round((left[i] ?? 0) * (1 - t) + (right[i] ?? 0) * t))
+    .join(" ");
+}
+
+const BLACK = "0 0 0";
+
+/**
+ * High contrast: the grounds stay pale, the text and borders go much darker.
+ *
+ * The hue is kept because it is doing work — a red notice and an amber one are
+ * different kinds of message, and this theme exists for low vision, not for
+ * monochrome. What changes is separation.
+ */
+function hardened(name: AccentName): Accent {
+  const accent = ACCENTS_ON_LIGHT[name];
+  return {
+    "50": accent["50"],
+    "200": mix(accent["200"], BLACK, 0.3),
+    "300": mix(accent["300"], BLACK, 0.4),
+    "400": mix(accent["400"], BLACK, 0.45),
+    "700": mix(accent["700"], BLACK, 0.35),
+    "800": mix(accent["800"], BLACK, 0.4),
+    "900": mix(accent["900"], BLACK, 0.45),
+  };
+}
+
+const PAPER_SURFACE = "250 246 238";
+
+/**
+ * Paper: the grounds warmed toward the page, the text left alone.
+ *
+ * A `bg-red-50` box on a warm page is the one thing that gives this theme away
+ * if it is not adjusted — a cool white-pink rectangle on cream reads as a
+ * rendering fault. The ink steps are already dark enough on a light ground and
+ * moving them would cost contrast for nothing.
+ */
+function warmed(name: AccentName): Accent {
+  const accent = ACCENTS_ON_LIGHT[name];
+  return {
+    "50": mix(accent["50"], PAPER_SURFACE, 0.55),
+    "200": mix(accent["200"], PAPER_SURFACE, 0.3),
+    "300": mix(accent["300"], PAPER_SURFACE, 0.2),
+    "400": accent["400"],
+    "700": accent["700"],
+    "800": accent["800"],
+    "900": accent["900"],
+  };
+}
+
+function mapAccents(transform: (name: AccentName) => Accent): Accents {
+  return Object.fromEntries(ACCENT_NAMES.map((name) => [name, transform(name)])) as Accents;
+}
+
+/** The slate ramp, the surface and the accents, as `R G B` triples for `rgb()`. */
 export interface Palette {
   readonly status: StatusColours;
+  readonly accents: Accents;
   readonly white: string;
   readonly slate50: string;
   readonly slate100: string;
@@ -100,6 +326,15 @@ export interface Palette {
   readonly slate700: string;
   readonly slate800: string;
   readonly slate900: string;
+  /**
+   * ⚠️ `slate-950` IS ONE CALL SITE AND IT WAS MISSED BY THE FIRST VERSION.
+   *
+   * `components/msd/msd-panel.tsx` uses it, and a deep merge of Tailwind's own
+   * slate scale kept `#020617` there while every other step became a variable —
+   * so on the dark theme that one element stayed near-black on a near-black
+   * page. The Supervisor found it. One call site is still a call site.
+   */
+  readonly slate950: string;
 }
 
 export interface Theme {
@@ -119,10 +354,11 @@ export type ThemeId = "system" | "light" | "dark" | "contrast" | "paper";
 /**
  * The default. Identical to Tailwind's own slate, so an application with no
  * stored preference looks exactly as it did before themes existed — and
- * `theme.test.ts` asserts `globals.css`'s `:root` block still matches it.
+ * `theme.test.ts` asserts `tailwind.config.ts`'s fallbacks still match it.
  */
 const LIGHT: Palette = {
   status: STATUS_ON_LIGHT,
+  accents: ACCENTS_ON_LIGHT,
   white: "255 255 255",
   slate50: "248 250 252",
   slate100: "241 245 249",
@@ -134,6 +370,7 @@ const LIGHT: Palette = {
   slate700: "51 65 85",
   slate800: "30 41 59",
   slate900: "15 23 42",
+  slate950: "2 6 23",
 };
 
 /**
@@ -147,6 +384,7 @@ const LIGHT: Palette = {
  */
 const DARK: Palette = {
   status: STATUS_ON_DARK,
+  accents: mapAccents(reversed),
   white: "15 23 42",
   slate50: "30 41 59",
   slate100: "38 50 68",
@@ -158,6 +396,9 @@ const DARK: Palette = {
   slate700: "226 232 240",
   slate800: "241 245 249",
   slate900: "248 250 252",
+  // Past the end of the reversed ramp, and therefore lighter than `slate900`.
+  // Anything else breaks the monotonicity the whole hierarchy is built on.
+  slate950: "255 255 255",
 };
 
 /**
@@ -170,6 +411,7 @@ const DARK: Palette = {
  */
 const CONTRAST: Palette = {
   status: STATUS_ON_LIGHT,
+  accents: mapAccents(hardened),
   white: "255 255 255",
   slate50: "242 242 242",
   slate100: "212 212 212",
@@ -181,6 +423,7 @@ const CONTRAST: Palette = {
   slate700: "17 17 17",
   slate800: "10 10 10",
   slate900: "0 0 0",
+  slate950: "0 0 0",
 };
 
 /**
@@ -192,7 +435,8 @@ const CONTRAST: Palette = {
  */
 const PAPER: Palette = {
   status: STATUS_ON_LIGHT,
-  white: "250 246 238",
+  accents: mapAccents(warmed),
+  white: PAPER_SURFACE,
   slate50: "243 237 225",
   slate100: "235 227 212",
   slate200: "221 211 192",
@@ -203,6 +447,7 @@ const PAPER: Palette = {
   slate700: "58 50 40",
   slate800: "40 34 27",
   slate900: "28 24 18",
+  slate950: "18 15 10",
 };
 
 /**
@@ -264,7 +509,7 @@ export function isThemeId(value: string): value is ThemeId {
  * `system` is not a palette. It resolves against `prefers-color-scheme` at the
  * moment it is asked, which is why this takes the answer rather than reading
  * `matchMedia` itself — the same function then works in a test, on the server,
- * and inside the pre-paint script that has no React.
+ * and inside the pre-paint script in `app/layout.tsx`, which has no React.
  */
 export function resolvePalette(theme: ThemeId, prefersDark: boolean): Palette {
   if (theme === "system") {
@@ -273,8 +518,10 @@ export function resolvePalette(theme: ThemeId, prefersDark: boolean): Palette {
   return PALETTES[theme];
 }
 
-/** The CSS custom-property name for each palette entry. */
-export const CSS_VARIABLES: Readonly<Record<Exclude<keyof Palette, "status">, string>> = {
+/** The CSS custom-property name for each slate/surface entry. */
+export const CSS_VARIABLES: Readonly<
+  Record<Exclude<keyof Palette, "status" | "accents">, string>
+> = {
   white: "--surface",
   slate50: "--slate-50",
   slate100: "--slate-100",
@@ -286,6 +533,7 @@ export const CSS_VARIABLES: Readonly<Record<Exclude<keyof Palette, "status">, st
   slate700: "--slate-700",
   slate800: "--slate-800",
   slate900: "--slate-900",
+  slate950: "--slate-950",
 };
 
 /** The CSS custom-property name for each status colour. */
@@ -297,6 +545,104 @@ export const STATUS_VARIABLES: Readonly<Record<keyof StatusColours, string>> = {
   neutral: "--status-neutral",
 };
 
+/**
+ * The CSS custom-property name for one accent step.
+ *
+ * A function rather than a table because the names are mechanical — 49 hand
+ * written entries would be 49 chances to write `--rose-300` beside `rose.200`,
+ * and nothing would notice until a border went the wrong colour on one theme.
+ */
+export function accentVariable(name: AccentName, step: AccentStep): string {
+  return `--${name}-${step}`;
+}
+
+/**
+ * Every custom property a theme sets, as `name → value`.
+ *
+ * 🔴 ONE PRODUCER, TWO CONSUMERS. The React provider applies this after
+ * hydration and the pre-paint script in `app/layout.tsx` applies it before
+ * first paint. They must set exactly the same properties or the page changes
+ * colour when React arrives — so they call this, and neither owns a list.
+ */
+export function paletteVariables(palette: Palette): Record<string, string> {
+  const variables: Record<string, string> = {};
+
+  for (const [key, variable] of Object.entries(CSS_VARIABLES)) {
+    variables[variable] = palette[key as keyof typeof CSS_VARIABLES];
+  }
+  for (const [key, variable] of Object.entries(STATUS_VARIABLES)) {
+    variables[variable] = palette.status[key as keyof StatusColours];
+  }
+  for (const name of ACCENT_NAMES) {
+    for (const step of ACCENT_STEPS) {
+      variables[accentVariable(name, step)] = palette.accents[name][step];
+    }
+  }
+
+  return variables;
+}
+
+/* -------------------------------------------------------------------------- */
+/* Before first paint                                                          */
+/* -------------------------------------------------------------------------- */
+
+/**
+ * Where the chosen theme is kept.
+ *
+ * 🔴 IN THIS FILE RATHER THAN IN `lib/preferences.ts`, WHICH READS IT.
+ * `preferences.ts` is a `"use client"` module, and the pre-paint script is
+ * built by the SERVER component `app/layout.tsx`. A server component importing
+ * a constant across a client boundary is a build-time reference rather than a
+ * string, so the key would have had to be written out a second time — and a
+ * pre-paint script reading `"evercoat.theme"` while the application wrote
+ * `"evercoat.themes"` would flash the default forever and pass every test.
+ */
+export const THEME_STORAGE_KEY = "evercoat.theme";
+
+/**
+ * The script that themes the page BEFORE the browser paints it.
+ *
+ * 🔴 WITHOUT THIS, EVERY LOAD FLASHES WHITE. Both reviewers found it. The
+ * fallbacks in `tailwind.config` are the LIGHT palette by design — they have to
+ * be, or a page with no JavaScript would render colourless — so a reader who
+ * has chosen dark got a full white page, then their theme when React hydrated.
+ * On a static export served from a CDN that gap is the whole first impression,
+ * and it is worst on the theme chosen by people most sensitive to a bright
+ * screen.
+ *
+ * ⚠️ IT IS BUILT FROM `paletteVariables`, NOT FROM A SECOND LIST. The provider
+ * and this script must set exactly the same properties; if they diverge the
+ * page changes colour at hydration, which is the same flash in a subtler form.
+ *
+ * ⚠️ AND IT SWALLOWS EVERYTHING. This runs before the application exists, with
+ * `localStorage` unavailable in a locked-down profile and throwing outright in
+ * some private windows. A theme that cannot be read is not an error worth
+ * having; it is the default. Nothing here may be allowed to stop the page.
+ */
+export function prePaintScript(): string {
+  const palettes = Object.fromEntries(
+    Object.entries(PALETTES).map(([id, palette]) => [id, paletteVariables(palette)]),
+  );
+
+  return (
+    `(function(){try{` +
+    `var P=${JSON.stringify(palettes)},K=${JSON.stringify(THEME_STORAGE_KEY)},t=null;` +
+    `try{t=window.localStorage.getItem(K)}catch(e){}` +
+    // An unknown id -- a theme a previous version of this application offered
+    // -- resolves to the default rather than to nothing.
+    `if(t!=="light"&&t!=="dark"&&t!=="contrast"&&t!=="paper")t="system";` +
+    `var d=window.matchMedia("(prefers-color-scheme: dark)").matches;` +
+    `var p=P[t==="system"?(d?"dark":"light"):t],r=document.documentElement;` +
+    `for(var k in p)r.style.setProperty(k,p[k]);` +
+    `r.dataset.theme=t;` +
+    // `color-scheme` too, or the scrollbar and the overscroll band stay light
+    // on a dark page -- and on this product the scrollbar sits beside a data
+    // grid on most screens.
+    `r.style.colorScheme=(t==="dark"||(t==="system"&&d))?"dark":"light";` +
+    `}catch(e){}})();`
+  );
+}
+
 /* -------------------------------------------------------------------------- */
 /* Contrast                                                                    */
 /* -------------------------------------------------------------------------- */
diff --git a/apps/web/tailwind.config.ts b/apps/web/tailwind.config.ts
index bde1281..d69a642 100644
--- a/apps/web/tailwind.config.ts
+++ b/apps/web/tailwind.config.ts
@@ -1,21 +1,32 @@
 import type { Config } from "tailwindcss";
 
+import {
+  ACCENT_NAMES,
+  ACCENT_STEPS,
+  CSS_VARIABLES,
+  PALETTES,
+  STATUS_VARIABLES,
+  accentVariable,
+} from "./lib/theme";
+
 /**
  * 🔴 THE PALETTE RESOLVES THROUGH CSS VARIABLES, WHICH IS WHAT MAKES THEMES
  * POSSIBLE WITHOUT EDITING 900 CALL SITES.
  *
- * Measured across `app/` and `components/`: this application draws almost
- * entirely from `white` and `slate-50…900` — `text-slate-600` alone appears 247
- * times, `text-slate-900` 166, `bg-white` 67. Every one of those resolves here,
- * so redefining the variables on `<html>` re-themes the whole product and no
- * component knows a theme exists.
+ * Measured across `app/` and `components/`: this application draws from
+ * `white`, `slate-50…950`, the four traffic-light tokens, and seven accent
+ * ramps — `text-slate-600` alone appears 247 times, `text-slate-900` 166,
+ * `bg-white` 67, and the accents another 129 between them. Every one of those
+ * resolves here, so redefining the variables on `<html>` re-themes the whole
+ * product and no component knows a theme exists.
  *
  * ⚠️ EVERY VARIABLE CARRIES ITS LIGHT VALUE AS A FALLBACK, and that is not
- * belt-and-braces. This is a STATIC EXPORT: the HTML is served before any script
- * runs, so between first paint and hydration there are no custom properties set
- * at all. Without the fallback every colour would resolve to nothing and the
- * first frame would be unreadable — text with no colour on a background with
- * none. The fallbacks ARE the light theme, which is also the default.
+ * belt-and-braces. This is a STATIC EXPORT: the HTML is served before any
+ * script runs. A pre-paint script in `app/layout.tsx` now sets the properties
+ * before first paint, but it is a script — with JavaScript disabled, or if it
+ * throws, there would be no custom properties at all and every colour would
+ * resolve to nothing. The fallbacks ARE the light theme, which is also the
+ * default.
  *
  * 🔴 `white` IS REDEFINED AND THAT IS DELIBERATE. `bg-white` is the card
  * surface and `text-white` is the primary button's label; on a dark theme both
@@ -24,31 +35,69 @@ import type { Config } from "tailwindcss";
  * white — a variable called `--white` holding `15 23 42` is the kind of name
  * that survives into a bug report.
  *
- * `theme.test.ts` asserts the fallbacks below match the LIGHT palette in
- * `lib/theme.ts`, so the two cannot drift.
+ * 🔴 THE FALLBACKS ARE IMPORTED, NOT COPIED, AND THAT IS THE POINT.
+ *
+ * The first version wrote every triple out by hand under a comment claiming
+ * *"`theme.test.ts` asserts the fallbacks below match the LIGHT palette"* — a
+ * drift guard that did not exist. The Supervisor found it. Two literals in two
+ * files cannot be type-checked into agreement, and a test that compares them is
+ * strictly worse than not having two: this file now reads `PALETTES.light`, so
+ * there is one definition and nothing to drift. `theme.test.ts` still measures
+ * the resolved config, so a future hand-written value is caught rather than
+ * assumed impossible.
  */
-const surface = "rgb(var(--surface, 255 255 255) / <alpha-value>)";
+const L = PALETTES.light;
+
+/** `rgb(var(--x, <light value>) / <alpha-value>)`, the one shape used below. */
+function token(variable: string, fallback: string): string {
+  return `rgb(var(${variable}, ${fallback}) / <alpha-value>)`;
+}
 
 const slate = {
-  50: "rgb(var(--slate-50, 248 250 252) / <alpha-value>)",
-  100: "rgb(var(--slate-100, 241 245 249) / <alpha-value>)",
-  200: "rgb(var(--slate-200, 226 232 240) / <alpha-value>)",
-  300: "rgb(var(--slate-300, 203 213 225) / <alpha-value>)",
-  400: "rgb(var(--slate-400, 148 163 184) / <alpha-value>)",
-  500: "rgb(var(--slate-500, 100 116 139) / <alpha-value>)",
-  600: "rgb(var(--slate-600, 71 85 105) / <alpha-value>)",
-  700: "rgb(var(--slate-700, 51 65 85) / <alpha-value>)",
-  800: "rgb(var(--slate-800, 30 41 59) / <alpha-value>)",
-  900: "rgb(var(--slate-900, 15 23 42) / <alpha-value>)",
+  50: token(CSS_VARIABLES.slate50, L.slate50),
+  100: token(CSS_VARIABLES.slate100, L.slate100),
+  200: token(CSS_VARIABLES.slate200, L.slate200),
+  300: token(CSS_VARIABLES.slate300, L.slate300),
+  400: token(CSS_VARIABLES.slate400, L.slate400),
+  500: token(CSS_VARIABLES.slate500, L.slate500),
+  600: token(CSS_VARIABLES.slate600, L.slate600),
+  700: token(CSS_VARIABLES.slate700, L.slate700),
+  800: token(CSS_VARIABLES.slate800, L.slate800),
+  900: token(CSS_VARIABLES.slate900, L.slate900),
+  // 🔴 950 IS HERE BECAUSE IT WAS MISSING AND ONE CALL SITE STAYED LITERAL.
+  // Tailwind DEEP-MERGES a partial colour scale, so listing 50…900 left
+  // `slate-950` resolving to its built-in `#020617` — near-black text on a
+  // near-black page under the dark theme, in `components/msd/msd-panel.tsx`.
+  // An incomplete scale does not fail; it silently keeps the original. The
+  // Supervisor found it, and `theme.test.ts` now asserts the other direction:
+  // every variable a theme sets must be reachable from some utility.
+  950: token(CSS_VARIABLES.slate950, L.slate950),
 };
 
+/**
+ * The accent ramps, generated from the same list the palettes are built from.
+ *
+ * Written by hand this is 49 entries, each a chance to pair `--rose-300` with
+ * `rose.200` — and nothing would notice until one border went the wrong colour
+ * on one theme.
+ */
+const accents = Object.fromEntries(
+  ACCENT_NAMES.map((name) => [
+    name,
+    Object.fromEntries(
+      ACCENT_STEPS.map((step) => [step, token(accentVariable(name, step), L.accents[name][step])]),
+    ),
+  ]),
+);
+
 export default {
   content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
   theme: {
     extend: {
       colors: {
-        white: surface,
+        white: token(CSS_VARIABLES.white, L.white),
         slate,
+        ...accents,
         // Traffic-light tokens. Named by MEANING, not by colour, so a
         // component cannot render "green" for a result that is only
         // technically passing but not yet approved (CLAUDE.md §10).
@@ -69,11 +118,11 @@ export default {
         // likely to be used late in the day. The dark set keeps the same hues
         // with lightness raised; the fallbacks here are the validated light set.
         status: {
-          pass: "rgb(var(--status-pass, 21 128 61) / <alpha-value>)",
-          fail: "rgb(var(--status-fail, 185 28 28) / <alpha-value>)",
-          conditional: "rgb(var(--status-conditional, 161 98 7) / <alpha-value>)",
-          invalid: "rgb(var(--status-invalid, 185 28 28) / <alpha-value>)",
-          neutral: "rgb(var(--status-neutral, 82 81 78) / <alpha-value>)",
+          pass: token(STATUS_VARIABLES.pass, L.status.pass),
+          fail: token(STATUS_VARIABLES.fail, L.status.fail),
+          conditional: token(STATUS_VARIABLES.conditional, L.status.conditional),
+          invalid: token(STATUS_VARIABLES.invalid, L.status.invalid),
+          neutral: token(STATUS_VARIABLES.neutral, L.status.neutral),
         },
       },
     },
diff --git a/tests/e2e/shell/accessibility.spec.ts b/tests/e2e/shell/accessibility.spec.ts
index c4c7da9..006030e 100644
--- a/tests/e2e/shell/accessibility.spec.ts
+++ b/tests/e2e/shell/accessibility.spec.ts
@@ -66,6 +66,36 @@ const PAGES = [
   // Administration's new sections.
   { name: "stage gates", path: "/admin/stage-gates" },
   { name: "reference data", path: "/admin/reference-data" },
+  // 🔴 THESE TWO WERE SHIPPED IN THE SAME COMMIT AND LEFT OUT OF THIS LIST.
+  // The Supervisor found it. They are the densest pages in Administration —
+  // `/admin/permissions` renders every permission code in the product as a
+  // `<code>` chip, and a chip is exactly the small, low-contrast element this
+  // sweep exists to catch. A page absent from the list is a page nobody
+  // checked, and the list looked complete because it had just grown.
+  { name: "roles", path: "/admin/roles" },
+  { name: "permissions", path: "/admin/permissions" },
+  // 🔴 AND MEASURING THE WHOLE ROUTE LIST FOUND EIGHT MORE.
+  //
+  // The Supervisor named the two above. Asking the wider question — which
+  // routes exist and which appear here — found that this list had never
+  // covered `/analytics`, `/knowledge`, `/reports`, or any of the five
+  // workspace routes, some of them since the slice that built them. The list
+  // has always LOOKED complete because it grows whenever somebody remembers.
+  //
+  // `lib/accessibility-coverage.test.ts` now derives the route list from the
+  // filesystem and fails when one is absent, so remembering is no longer the
+  // mechanism.
+  { name: "analytics", path: "/analytics" },
+  { name: "knowledge", path: "/knowledge" },
+  { name: "reports", path: "/reports" },
+  // The workspace routes, with no record named. That is a REAL state — it is
+  // what a bookmarked link without its query string renders — and it is the
+  // one most likely to be an unlabelled empty page.
+  { name: "failure investigation", path: "/failures/investigation" },
+  { name: "formula workspace", path: "/formulations/formula" },
+  { name: "batch workspace", path: "/laboratory/batch" },
+  { name: "project workspace", path: "/projects/workspace" },
+  { name: "test workspace", path: "/testing/test" },
 ];
 
 for (const target of PAGES) {
diff --git a/tests/e2e/shell/theme.spec.ts b/tests/e2e/shell/theme.spec.ts
index 2c533b3..7df1c7c 100644
--- a/tests/e2e/shell/theme.spec.ts
+++ b/tests/e2e/shell/theme.spec.ts
@@ -100,3 +100,91 @@ test.describe("themes", () => {
     expect(result.body).toBe("rgb(248, 250, 252)");
   });
 });
+
+test.describe("before the first paint", () => {
+  /**
+   * 🔴 THE THEME WAS APPLIED BY REACT, SO EVERY LOAD FLASHED WHITE.
+   *
+   * `ThemeProvider` runs in an effect — after hydration, and therefore after
+   * the browser has already painted a document whose only colours are the
+   * light fallbacks in `tailwind.config`. A reader who had chosen dark got a
+   * full white page and then their theme. Both reviewers found it, and every
+   * test above passed over it, because all of them read the computed style
+   * once the application is running.
+   *
+   * This asserts the state of the document BEFORE any React has executed.
+   */
+  test("the palette is set before React runs, not after", async ({ page }) => {
+    await page.goto("/dashboard/");
+    await page.evaluate(() => window.localStorage.setItem("evercoat.theme", "dark"));
+
+    // Stop the page as early as a browser will let us: `domcontentloaded`
+    // fires once the head scripts have run and before the React bundle has
+    // hydrated. If the dark palette is only applied by the provider, the
+    // variable is empty at this moment.
+    await page.goto("/dashboard/", { waitUntil: "domcontentloaded" });
+
+    const surface = await page.evaluate(() =>
+      getComputedStyle(document.documentElement).getPropertyValue("--surface").trim(),
+    );
+
+    expect(
+      surface,
+      "the dark surface was not set at DOMContentLoaded, so the first frame " +
+        "is painted with the light fallbacks and the page flashes white",
+    ).toBe("15 23 42");
+  });
+
+  test("an unreadable preference still paints, rather than leaving no colours", async ({
+    page,
+  }) => {
+    // The pre-paint script runs before anything else exists and swallows
+    // everything on purpose. A stored value from a version of this application
+    // that offered a theme no longer in the list must resolve to the default,
+    // not to an unstyled document.
+    await page.goto("/dashboard/");
+    await page.evaluate(() => window.localStorage.setItem("evercoat.theme", "midnight-1998"));
+    await page.reload({ waitUntil: "load" });
+
+    const surface = await page.evaluate(() =>
+      getComputedStyle(document.documentElement).getPropertyValue("--surface").trim(),
+    );
+    expect(surface).toBe("255 255 255");
+  });
+});
+
+test.describe("where the application opens", () => {
+  /**
+   * 🔴 THE PREFERENCE HAD NO READER, AND THE SCREEN SAID IT WORKED.
+   *
+   * `readLanding()` was written by Settings, validated on the way back out,
+   * and consulted by nothing: `app/page.tsx` redirected to a hard-coded
+   * `/dashboard`. Both reviewers found it — it is this project's own rule
+   * about a setting with no enforcement point, arriving from the user's side
+   * of the screen.
+   */
+  test("the front door opens on the chosen screen", async ({ page }) => {
+    await page.goto("/dashboard/");
+    await page.evaluate(() => window.localStorage.setItem("evercoat.landing", "/testing"));
+
+    await page.goto("/");
+    await expect(page).toHaveURL(/\/testing\/?$/, { timeout: 15_000 });
+  });
+
+  test("and on the dashboard when nothing has been chosen", async ({ page }) => {
+    // The default must be unchanged for anybody who never opens Settings.
+    await page.goto("/");
+    await expect(page).toHaveURL(/\/dashboard\/?$/, { timeout: 15_000 });
+  });
+
+  test("a stored screen that no longer exists falls back rather than 404s", async ({ page }) => {
+    await page.goto("/dashboard/");
+    await page.evaluate(() => window.localStorage.setItem("evercoat.landing", "/formulations"));
+    // `/formulations` is a real page but NOT one of the three offered, so it is
+    // not a valid stored value — `isLandingScreen` refuses it and the default
+    // applies. A preference read that accepted any path would be an open
+    // redirect with a friendly name.
+    await page.goto("/");
+    await expect(page).toHaveURL(/\/dashboard\/?$/, { timeout: 15_000 });
+  });
+});

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show 722df3d:apps/web/components/providers/auth-provider.tsx; git show 722df3d:apps/web/app/page.tsx; git show 722df3d:apps/web/app/layout.tsx; git show 722df3d:apps/web/components/ui/radio-cards.tsx; git show 722df3d:apps/web/lib/preferences.ts; git show 722df3d:apps/web/components/providers/theme-provider.tsx' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 1155ms:
/**
 * The sign-in flow, wired to the session the rest of the app already reads.
 *
 * `lib/api/session.ts` was written before there was an implementation and
 * predicted this exactly: *"When Keycloak is deployed, `readSession` gains
 * an OIDC implementation and nothing else in the application changes — the
 * hooks, the client and the pages are already written against this
 * interface."* This is that implementation. No hook, no page and no
 * request changes.
 *
 * 🔴 THE TOKEN LIVES IN MEMORY, AND A RELOAD SIGNS YOU OUT.
 *
 * That is a decision, not an omission. `session.ts` recorded the rule
 * first: an access token in browser storage is readable by any script on
 * the origin, so one XSS becomes a stolen session that outlives the page.
 *
 * The cost is real and is stated plainly: after a reload the user is
 * ANONYMOUS and must press Sign in. Nothing happens automatically. What
 * makes that acceptable rather than merely tolerable is that the redirect
 * usually returns without a password prompt, because Keycloak's own SSO
 * cookie is still valid — so it costs a round trip, not a login.
 *
 * (An earlier version of this paragraph described that as "silent" and as
 * "a flicker, not a login form". Codex pointed out that no code performed
 * any silent check — the `prompt=none` path was never wired up — so the
 * comment promised behaviour the file did not have. Corrected rather than
 * implemented, because the silent path is deliberately declined below.)
 *
 * 🔴 WHY THERE IS NO HIDDEN-IFRAME SILENT RENEW.
 *
 * The classic answer is a `prompt=none` request in a hidden iframe. It is
 * deliberately not used: it depends on the realm's cookie being sent in a
 * third-party context, which Safari's ITP blocks outright and Chrome is
 * removing. A mechanism that works in development and silently stops
 * working for some users in production is worse than one that visibly
 * asks — this codebase has already been caught by config that "read
 * correct while the mechanism was INERT". `signIn()` is a full redirect,
 * and it is honest.
 *
 * See ADR-025.
 */

"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { API_BASE_URL } from "@/lib/api/config";
import { readSession, setSession, useSession, type SessionState } from "@/lib/api/session";
import {
  AUTH_UNCONFIGURED_REASON,
  CALLBACK_PATH,
  KEYCLOAK_CLIENT_ID,
  endpoints,
  isAuthConfigured,
} from "@/lib/auth/config";
import { safeReturnTo, saveFlow } from "@/lib/auth/flow-state";
import { authorizationUrl, createChallenge, refreshTokens } from "@/lib/auth/pkce";

/**
 * Who the signed-in person is, in the organization they are currently working in.
 *
 * 🔴 DERIVED FROM THE ACTIVE MEMBERSHIP. NOT STORED, AND THAT IS THE FIX.
 *
 * It used to be its own `useState`, set from a top-level `display_name` on
 * `/api/me`, and it went wrong in three directions at once. `signOut` cleared
 * the session and the organizations and never cleared this, so the previous
 * user's name stayed in the top bar of an anonymous application — on a shared
 * bench machine, somebody else's name over your work. Switching organization
 * did not change it. And the value itself was whichever tenant sorted first
 * alphabetically, because migration 052 put the name on the MEMBERSHIP and the
 * route flattened the rows back to one.
 *
 * All three were the same defect: a per-tenant fact kept as though it were a
 * global one, in a second place, needing a second thing to remember to clear
 * it. Derived from the active membership there is nothing to clear, nothing to
 * refresh, and no second copy — the anonymous state has no active membership,
 * so it has no name. Both reviewers found the first of the three; Codex found
 * the second.
 *
 * ⚠️ THIS IS THE ORGANIZATION'S VIEW OF THE PERSON, not a global identity.
 */
export interface UserProfile {
  readonly userId: string;
  readonly email: string;
  readonly displayName: string;
}

export interface AuthContextValue {
  readonly session: SessionState;
  /** The signed-in person, or null when there is no session. */
  readonly profile: UserProfile | null;
  /** True when this build has an identity provider to talk to. */
  readonly configured: boolean;
  /** Begin sign-in. A full-page redirect; this function does not return. */
  readonly signIn: () => Promise<void>;
  /** Discard the session locally and end it at the provider. */
  readonly signOut: () => void;
  /** The active organization, and the ability to change it. */
  readonly organizations: readonly OrganizationChoice[];
  readonly selectOrganization: (organizationId: string) => void;
}

export interface OrganizationChoice {
  readonly organizationId: string;
  readonly name: string;
  readonly code: string;
  /** What THIS organization calls the caller (052). Per-tenant, like the roles. */
  readonly email: string;
  readonly displayName: string;
  readonly roles: readonly string[];
  /**
   * Permission codes held in THIS organization (I79).
   *
   * 🔴 PERMISSIONS, NOT ROLES, AND THEY ARE PER-TENANT LIKE THE ROLES ARE.
   * §6 authorizes on permissions and never on role names; before migration
   * 045 `/api/me` returned only roles, so the shell could either show every
   * control or re-derive the mapping in TypeScript. It showed every control.
   *
   * Empty is a legitimate value and must not be confused with "unknown":
   * a member holding no roles yet has no permissions, and the sidebar
   * should say so rather than showing the whole module map. `undefined`
   * organizations -- no session at all -- is the different case, handled
   * where the sidebar chooses its fallback.
   */
  readonly permissions: readonly string[];
}

/** The ordinary signed-out state of a build that CAN sign in. */
export const NOT_SIGNED_IN = "you are not signed in";

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * The full redirect URI, built from the browser's own origin.
 *
 * A static export cannot know its deployed origin at build time, so it is
 * read at run time — and it MUST match a `redirectUris` entry in the
 * realm exactly, or Keycloak refuses with `invalid_redirect_uri` before
 * issuing anything. Building it in one place is deliberate: two spellings
 * of a redirect URI cannot be type-checked into agreement, which is the
 * defect shape this project keeps hitting.
 */
export function redirectUri(): string {
  return `${window.location.origin}${CALLBACK_PATH}`;
}

/** In-memory refresh material. Never written to storage — see the header. */
interface LiveTokens {
  readonly accessToken: string;
  readonly refreshToken: string | null;
  readonly expiresAt: number;
}

/**
 * Which organization stays active across a token refresh.
 *
 * 🔴 A REFRESH MUST NOT SILENTLY MOVE THE USER TO ANOTHER TENANT.
 *
 * `establish()` runs on sign-in AND on every refresh. The first version
 * always took `choices[0]`, so a chemist working in their second
 * organization was silently switched back to the first roughly once per
 * token lifetime — and every write after that went to the WRONG TENANT,
 * with the correct name shown only in a corner nobody was watching. In an
 * application whose records are controlled and audited, that is a
 * data-integrity defect, not a UI annoyance. Codex found it.
 *
 * Falling back to the first when the preferred one is gone is deliberate:
 * that means the membership was revoked, and staying on it is not an
 * option. Extracted and exported so the rule is testable on its own
 * rather than reachable only through a network call.
 */
export function chooseOrganization(
  choices: readonly OrganizationChoice[],
  preferred: string | undefined,
): OrganizationChoice {
  const kept = choices.find((org) => org.organizationId === preferred);
  if (kept !== undefined) return kept;
  const first = choices[0];
  if (first === undefined) {
    throw new Error("chooseOrganization called with no organizations");
  }
  return first;
}

/**
 * The caller as the organization they are working in knows them.
 *
 * 🔴 A BLANK NAME IS AN ABSENT NAME. The previous version required all three
 * fields to be `!== undefined`, which an empty string satisfies — so an API
 * returning `""` produced "signed in as ''" in the top bar, under a comment
 * claiming that exact case was excluded. Codex found the gap between the
 * comment and the check. Nothing here trims a name into existence: if either
 * attribute is blank there is no profile, and `UserMenu` renders nothing rather
 * than an initialled circle with no initials.
 *
 * Exported and pure so the rule can be tested without a network call or a
 * React tree — the same reason `chooseOrganization` is.
 */
export function activeProfile(
  session: SessionState,
  organizations: readonly OrganizationChoice[],
): UserProfile | null {
  // Anonymous has no active membership, so it has no name. That is the whole
  // of the "signOut must clear the profile" fix: there is no profile to clear.
  if (session.status !== "authenticated") return null;

  const active = organizations.find(
    (org) => org.organizationId === session.credentials.organizationId,
  );
  if (active === undefined) return null;

  if (active.displayName.trim() === "" || active.email.trim() === "") return null;

  return {
    userId: session.credentials.userId,
    email: active.email,
    displayName: active.displayName,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
  const tokens = useRef<LiveTokens | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 🔴 clearTimeout CANNOT STOP A REFRESH THAT IS ALREADY IN FLIGHT.
  //
  // The cleanup clears the pending timer, but if the callback has already
  // fired it is sitting in `await refreshTokens(...)`, and when that
  // resolves it sets state and schedules the NEXT timer -- after unmount.
  // The result is a React warning, a token refreshed for a tree nobody is
  // rendering, and a timer that outlives the provider. Codex found it.
  const mounted = useRef(true);

  /**
   * Ask the API who we are, and which tenants we may act in.
   *
   * 🔴 THIS CALL IS WHAT MAKES SIGNING IN USEFUL. Every other route
   * requires `X-Organization-Id`, and until `GET /api/me` existed nothing
   * told the browser what to put in it — a valid token bought 400s and
   * nothing else. It is therefore NOT optional and NOT best-effort: if it
   * fails there is no usable session, and saying so is better than an
   * application that renders empty.
   */
  /**
   * @returns true when a usable session was established.
   *
   * 🔴 IT USED TO RETURN void AND "SUCCEED" ON EVERY FAILURE.
   *
   * A 401, 404 or 500 from `/api/me` set an anonymous session and then
   * resolved normally, so the caller went on to schedule another refresh.
   * A deprovisioned user was therefore left holding live tokens that the
   * application kept refreshing indefinitely, while the UI insisted there
   * was no session. Codex found it. The caller now stops, and drops the
   * tokens.
   */
  const establish = useCallback(async (accessToken: string): Promise<boolean> => {
    if (API_BASE_URL === null) {
      setSession({
        status: "anonymous",
        reason:
          "signed in, but this build was compiled without an API address, so " +
          "there is nothing to sign in to",
      });
      return false;
    }

    const response = await fetch(`${API_BASE_URL}/api/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    if (response.status === 404) {
      // The single most useful diagnostic in the whole auth path: the
      // token is genuine and its subject matches no user. Historically
      // this exact state was produced by seed.py writing
      // `keycloak_sub = 'demo-chem.demo'` while a real token carries a
      // UUID. Naming it saves the next reader a day.
      setSession({
        status: "anonymous",
        reason:
          "you signed in successfully, but this application has no account for " +
          "you yet — your identity is valid and your access is not provisioned",
        failed: true,
      });
      return false;
    }

    if (!response.ok) {
      setSession({
        status: "anonymous",
        reason: `the API refused to identify you (HTTP ${response.status})`,
        // A request WAS made and it failed. Not an absence -- see the
        // `failed` field on SessionState.
        failed: true,
      });
      return false;
    }

    const body = (await response.json()) as {
      user_id?: string;
      organizations?: {
        organization_id: string;
        name: string;
        code: string;
        email?: string;
        display_name?: string;
        roles?: string[];
        permissions?: string[];
      }[];
    };

    const choices: OrganizationChoice[] = (body.organizations ?? []).map((org) => ({
      organizationId: org.organization_id,
      name: org.name,
      code: org.code,
      // 🔴 THE MEMBERSHIP'S OWN PAIR (052). An API too old to send them yields
      // an empty string, which `useProfile` reads as "no name" rather than
      // rendering "signed in as ''" — see the profile derivation below.
      email: org.email ?? "",
      displayName: org.display_name ?? "",
      roles: org.roles ?? [],
      // `?? []` and not `?? ALL_NAV_PERMISSIONS`: an API too old to send
      // permissions must yield a shell that shows LESS, never one that shows
      // everything. Failing open on an authorization-shaped field is how a
      // cosmetic filter turns into a claim the server never made.
      permissions: org.permissions ?? [],
    }));

    const first = choices[0];
    if (first === undefined) {
      // Absence must never present as success. An empty list would render
      // as a working sign-in into an application with nothing in it.
      setSession({
        status: "anonymous",
        reason: "you are signed in but belong to no organization, so there is nothing to show",
        failed: true,
      });
      return false;
    }

    // 🔴 A TOKEN REFRESH MUST NOT SILENTLY MOVE THE USER TO ANOTHER TENANT.
    //
    // This function runs on sign-in AND on every refresh. The first
    // version always selected `choices[0]`, so a chemist working in their
    // second organization was silently switched back to the first roughly
    // once every token lifetime -- and every write after that point went
    // to the wrong tenant, with the UI showing the wrong name in a corner
    // nobody was looking at. Codex found it.
    //
    // The active organization is therefore CARRIED unless it has gone
    // away, in which case falling back to the first is correct: the
    // membership was revoked and staying on it is not an option.
    const currently = readSession();
    const chosen = chooseOrganization(
      choices,
      currently.status === "authenticated" ? currently.credentials.organizationId : undefined,
    );

    const userId = typeof body.user_id === "string" ? body.user_id : "";
    if (userId === "") {
      // A principal with no id cannot scope a cache entry, and a cache
      // entry that cannot be scoped is one that can be served to the
      // wrong person. Refuse rather than fall back to a shared key.
      setSession({
        status: "anonymous",
        reason: "the API did not identify who you are",
        failed: true,
      });
      return false;
    }

    setOrganizations(choices);
    setSession({
      status: "authenticated",
      credentials: {
        token: accessToken,
        organizationId: chosen.organizationId,
        userId,
      },
    });
    return true;
  }, []);

  /** Keep the access token fresh while the tab is open. */
  const scheduleRefresh = useCallback(
    (live: LiveTokens) => {
      if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
      if (live.refreshToken === null) return;

      // 30 seconds of margin. Refreshing exactly at expiry races the
      // clock against network latency and loses often enough to matter,
      // and the failure looks like a random 401 rather than a timing bug.
      const delay = Math.max(5_000, live.expiresAt - Date.now() - 30_000);
      refreshTimer.current = setTimeout(() => {
        void (async () => {
          try {
            const next = await refreshTokens({
              tokenEndpoint: endpoints().token,
              clientId: KEYCLOAK_CLIENT_ID,
              refreshToken: live.refreshToken as string,
            });
            if (!mounted.current) return;
            tokens.current = next;
            // 🔴 SEPARATED FROM THE REFRESH FAILURE ON PURPOSE.
            //
            // `establish()` reaches the API, and a thrown fetch -- API
            // host down, DNS, a refused CORS preflight -- used to
            // propagate into the catch below and report "your session
            // expired", nulling a refresh token that was perfectly
            // valid. The user was signed out and told the wrong reason.
            // The Supervisor found it.
            let usable = false;
            try {
              usable = await establish(next.accessToken);
            } catch {
              if (!mounted.current) return;
              setSession({
                status: "anonymous",
                reason:
                  "you are signed in, but the application cannot be reached right " +
                  "now. Your session is intact -- retry in a moment.",
                failed: true,
              });
              // Tokens are KEPT and the timer is rescheduled: the
              // credential is fine, the network is not.
              scheduleRefresh(next);
              return;
            }
            if (!mounted.current) return;
            if (!usable) {
              // The token still refreshes, but it buys nothing: the API
              // will not identify this subject. Holding and re-refreshing
              // a credential for a session that does not exist is the
              // defect Codex named. Stop, and drop it.
              tokens.current = null;
              return;
            }
            scheduleRefresh(next);
          } catch {
            // The refresh token has expired or been revoked. Signing the
            // user out is the honest outcome; retrying would produce a
            // session that appears live and 401s on every request.
            if (!mounted.current) return;
            tokens.current = null;
            setSession({
              status: "anonymous",
              reason: "your session expired, please sign in again",
            });
          }
        })();
      }, delay);
    },
    [establish],
  );

  /**
   * Adopt tokens produced by the callback page.
   *
   * Exposed on `window` rather than through context because the callback
   * is a separate route that mounts its own tree, and threading a
   * provider through a page whose only job is to hand over a token would
   * be more machinery than the handover is worth.
   */
  useEffect(() => {
    const adopt = async (live: LiveTokens) => {
      tokens.current = live;
      const usable = await establish(live.accessToken);
      if (!usable) {
        tokens.current = null;
        return;
      }
      scheduleRefresh(live);
    };
    mounted.current = true;
    (window as unknown as Record<string, unknown>).__evercoatAdoptTokens = adopt;
    return () => {
      mounted.current = false;
      if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
      delete (window as unknown as Record<string, unknown>).__evercoatAdoptTokens;
    };
  }, [establish, scheduleRefresh]);

  /** Tell the reader why there is no sign-in, rather than showing a dead button.
   *
   * 🔴 IT MUST NOT CLOBBER A SESSION SOMEBODY ELSE ALREADY SET.
   *
   * The first version set the anonymous reason unconditionally on mount,
   * and broke five end-to-end tests: the suite establishes a session
   * through the compiled-out test seam, and this effect then overwrote
   * it. `readSession()` rather than the `session` prop, so the check sees
   * the store's current value and not a render-time snapshot.
   */
  useEffect(() => {
    if (readSession().status === "authenticated") return;
    // 🔴 THE DEFAULT REASON LIED IN A CONFIGURED BUILD.
    //
    // `session.ts` seeds the store with NO_IDENTITY_PROVIDER ("no
    // identity provider is deployed for this environment"), and this
    // effect only overwrote it when the build was UNconfigured. So a
    // build that HAD a Keycloak showed that sentence beside a working
    // Sign in button, telling the reader the deployment has no identity
    // provider while they look at the control that uses it. The
    // Supervisor found it. Both branches are now stated.
    setSession({
      status: "anonymous",
      reason: isAuthConfigured ? NOT_SIGNED_IN : AUTH_UNCONFIGURED_REASON,
    });
  }, []);

  const signIn = useCallback(async () => {
    if (!isAuthConfigured) return;
    const challenge = await createChallenge();
    const returnTo = safeReturnTo(
      window.location.pathname + window.location.search,
      window.location.origin,
    );

    // 🔴 DO NOT REDIRECT IF THE FLOW COULD NOT BE STORED.
    //
    // Without the verifier the callback cannot complete, so redirecting
    // would send the user to Keycloak, have them authenticate for real,
    // and then fail with "no sign-in was in progress" — every time, with
    // no way forward. Storage is genuinely unavailable in Safari private
    // mode and under some enterprise policies. Codex found it.
    if (!saveFlow(challenge, returnTo)) {
      setSession({
        status: "anonymous",
        reason:
          "this browser is blocking session storage, which sign-in needs to " +
          "complete securely. Try a normal window, or allow storage for this site.",
      });
      return;
    }

    window.location.assign(
      authorizationUrl({
        authorizeEndpoint: endpoints().authorize,
        clientId: KEYCLOAK_CLIENT_ID,
        redirectUri: redirectUri(),
        challenge,
      }),
    );
  }, []);

  const signOut = useCallback(() => {
    // Local state first. If the redirect below fails for any reason, the
    // browser must not be left holding a live token while believing it
    // has signed out.
    if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
    tokens.current = null;
    setOrganizations([]);
    setSession({ status: "anonymous", reason: "you have signed out" });

    // 🔴 GATED ON CONFIGURATION ONLY.
    //
    // It used to also require `refreshToken !== null` -- a condition with
    // nothing to do with logging out, since the request below sends only
    // `client_id` and `post_logout_redirect_uri`. If Keycloak's response
    // had omitted a refresh token, Sign out cleared local state and left
    // the realm's SSO cookie alive, so the next Sign in silently returned
    // the previous user. On the shared machine the comment below names,
    // that is the wrong person. The Supervisor found it.
    if (!isAuthConfigured) return;
    // Ends the session at Keycloak too. Without this the SSO cookie
    // survives and the next "Sign in" silently returns the same user —
    // which on a shared machine is the wrong person.
    const params = new URLSearchParams({
      client_id: KEYCLOAK_CLIENT_ID,
      post_logout_redirect_uri: window.location.origin,
    });
    window.location.assign(`${endpoints().endSession}?${params.toString()}`);
  }, []);

  const selectOrganization = useCallback(
    (organizationId: string) => {
      const token = tokens.current?.accessToken;
      if (token === undefined) return;
      // Only an organization the API itself listed. A tenant id typed in
      // from anywhere else would be refused server-side anyway, but
      // offering it at all would imply it was a choice.
      if (!organizations.some((org) => org.organizationId === organizationId)) return;
      // Read the store, not the render-time `session` prop: this callback
      // is memoised on `organizations` and would otherwise close over a
      // stale session.
      const active = readSession();
      const userId = active.status === "authenticated" ? active.credentials.userId : "";
      if (userId === "") return;
      setSession({
        status: "authenticated",
        credentials: { token, organizationId, userId },
      });
    },
    [organizations],
  );

  const profile = useMemo(
    () => activeProfile(session, organizations),
    [session, organizations],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      configured: isAuthConfigured,
      signIn,
      signOut,
      profile,
      organizations,
      selectOrganization,
    }),
    [session, signIn, signOut, profile, organizations, selectOrganization],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    // A hook that silently returned a signed-out value outside its
    // provider would make a missing <AuthProvider> look like a user who
    // had not signed in — indistinguishable, and wrong.
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return context;
}
"use client";

/**
 * Front door. Sends the visitor to the screen they chose to open on.
 *
 * WHY THIS IS A CLIENT REDIRECT AND NOT `redirect("/dashboard")`.
 *
 * This page used to be a server component calling `redirect()`. That works
 * under `output: "standalone"`, where a Node server is there to answer 307.
 * It does NOT survive `output: "export"`: there is no server, so Next has
 * nothing to emit for this route and writes an error document —
 * `out/index.html` came out as `<html id="__next_error__">` while
 * `next build` exited 0 and printed `✓ Exporting (2/2)`. The front door
 * was an error page with every gate green.
 *
 * The obvious repair — a Render redirect rule for `/` — does not work
 * either. Render's rule engine is documented as: "Render does not apply
 * redirect or rewrite rules to a path if a resource exists at that path."
 * `out/index.html` exists, so the rule would never fire. Deleting the file
 * after the build would work and is exactly the kind of second mechanism
 * that later disagrees with the first.
 *
 * So the redirect is expressed once, here, in a form that holds in BOTH
 * build modes: a real page that navigates on mount. The cost is one frame
 * of "Redirecting…" on the server build, which previously got a 307. That
 * is the deliberate trade — one mechanism that cannot drift, over two that
 * can.
 *
 * The visible link is not decoration: it is the whole page for a visitor
 * with JavaScript disabled or still loading, who would otherwise sit on a
 * blank screen with no way forward.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DEFAULT_LANDING, readLanding } from "@/lib/preferences";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // 🔴 THE CHOSEN SCREEN, NOT A CONSTANT. Settings offers three destinations
    // under "After signing in, open"; this used to be a hard `/dashboard`, so
    // the preference had no reader anywhere in the application and the screen
    // asserted a behaviour nothing implemented. Both reviewers found it — and
    // it is the project's own rule about a setting with no enforcement point,
    // reached from the other side.
    //
    // Read here rather than in a provider because this is the front door: it
    // is where "where does the application open" is actually decided, and it
    // works signed in or out.
    //
    // `replace`, not `push` — the front door should not become a back-button
    // trap that bounces the visitor straight back out to it.
    router.replace(readLanding());
  }, [router]);

  return (
    <div className="p-6">
      {/* A real <h1>, not an aria-live paragraph.
          The first version used aria-live="polite" on text that is present
          at first render and never changes. A live region announces
          CHANGES to its contents, so static text inside one is never
          announced — the accessibility benefit claimed in the comment did
          not exist. Every other route has a heading; this one had none, so
          a screen-reader user landing here got an unlabelled page.
          The layout already supplies the <main> landmark. */}
      <h1 className="text-sm font-medium text-slate-600">
        Opening the application…
      </h1>
      {/* ⚠️ THE DEFAULT, NOT THE PREFERENCE, AND DELIBERATELY SO. This link is
          the whole page for a visitor with JavaScript disabled or still
          loading. The preference lives in `localStorage`, which is only
          readable by script, so a link that claimed to honour it would be a
          link that could not — and rendering it from the preference after
          hydration would change the destination under a reader mid-click. */}
      <Link
        href={DEFAULT_LANDING}
        className="mt-2 inline-block text-sm font-medium text-slate-900 underline"
      >
        Continue to the dashboard
      </Link>
    </div>
  );
}
/**
 * Root layout — the persistent application shell.
 *
 * Structure is fixed by the Navigation narrative §1: a global top bar
 * across the width, a persistent left sidebar, and the active workspace.
 * The user must never lose access to the principal modules while working
 * inside a project or technical record.
 *
 * The contextual top submenu is NOT here — it belongs to whichever entity
 * is open (project, formula, batch, test, failure, pilot, product), so it
 * is rendered by that entity's own layout. Putting it here would force
 * every route to know about every other route's submenu.
 */

import type { Metadata } from "next";

import { AuthProvider } from "@/components/providers/auth-provider";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { AppSidebar } from "@/components/nav/app-sidebar";
import { TopBar } from "@/components/nav/top-bar";
import { ALL_NAV_PERMISSIONS } from "@/lib/navigation";
import { prePaintScript } from "@/lib/theme";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "EvercoatITWRD APP",
    template: "%s · EvercoatITWRD APP",
  },
  description:
    "Integrated R&D, Smart Formulation, Laboratory Testing, Product Modeling " +
    "and Product Development Intelligence Platform",
  // Proprietary formulation data. Never indexable, even if a deployment
  // is accidentally exposed.
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // THE DEMONSTRATION PRINCIPAL.
  //
  // Slice 1 passed an EMPTY set, deliberately, so that a shell showing
  // everything could not be mistaken for a working RBAC filter. That was
  // right while nothing was built — and wrong the moment Slice 2 shipped
  // pages: with no permissions, `visibleNavigation` filtered Projects,
  // Innovation and R&D Pipeline out of the sidebar entirely, so the pages
  // existed and were unreachable. Found by looking at the rendered page,
  // not by any test.
  //
  // This is a PRESENTATION set and nothing more. CLAUDE.md §6 and
  // SECURITY.md §3 both state that frontend permission checks are
  // cosmetic and every route is re-authorized server-side; handing the
  // sidebar the full set grants no access to anything. Destinations that
  // are not built yet still render inert via `isAvailable`, so the module
  // map is honest about what exists.
  //
  // When Keycloak is wired in, this becomes the verified principal's own
  // permissions and the RBAC filter is exercised for real.
  const permissions = ALL_NAV_PERMISSIONS;

  // 🔴 THE BADGE COUNT MOVED OUT OF THIS FILE.
  //
  // It used to be computed here, in a SERVER component, from the bundled
  // demonstration fixture. That was right while My Work was a
  // demonstration screen. Now that My Work issues a real request, a
  // build-time constant beside a live list would mean a signed-in chemist
  // with four real tasks saw whatever number the fixture contained.
  //
  // `AppSidebar` reads the count from the same hook, query key and cache
  // entry the page reads, so the two cannot drift.

  return (
    <html lang="en">
      <head>
        {/* 🔴 BEFORE THE FIRST PAINT, NOT AFTER HYDRATION.
 
            The themed variables were only ever set by `ThemeProvider`, which is
            React and therefore runs after the document has already been
            painted. A reader who had chosen dark got a full white page and then
            their theme — on a static export served from a CDN, that flash is
            the whole first impression, and it lands hardest on the people who
            chose dark because a bright screen bothers them. Both reviewers
            found it.

            `dangerouslySetInnerHTML` because there is no other way to inline a
            script in the document head from a server component. The content is
            generated from this application's own constants — no request, no
            user input, nothing interpolated from outside the build. */}
        <script dangerouslySetInnerHTML={{ __html: prePaintScript() }} />
      </head>
      <body className="bg-slate-50 text-slate-900 antialiased">
        {/* TanStack Query, for the whole tree. It wraps the shell rather
            than each page so that a query started on one screen is still
            cached when the reader navigates back to it — and so that a
            page added later is wired by existing, not by remembering. */}
        {/* AuthProvider outside QueryProvider: a query fired before
            the session is known would run anonymously and cache the
            refusal. */}
        {/* 🔴 OUTSIDE EVERYTHING, INCLUDING THE AUTH PROVIDER. The theme is a
            property of the BROWSER, not of the session: a signed-out reader
            looking at the sign-in screen has already chosen dark, and a theme
            that only applied once somebody was authenticated would flash white
            at exactly the moment they are least expecting it. */}
        <ThemeProvider>
        <AuthProvider>
        <QueryProvider>
        <div className="flex h-screen overflow-hidden">
          <AppSidebar permissions={permissions} />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            {/* min-w-0 above and here is what lets wide technical tables
                scroll inside the workspace instead of pushing the page
                into a horizontal scroll.

                tabIndex={0} because this element SCROLLS. axe-core reports
                `scrollable-region-focusable` (serious) for a scroll
                container a keyboard cannot reach, and it surfaced the first
                time a page shipped with no focusable content of its own —
                /suppliers is entirely static cards, so there was nothing to
                tab to and the region below the fold was unreachable.

                Fixed here rather than by adding a link to that one page: the
                next static page would have reintroduced it. A scroll
                container needs keyboard access as a property of scrolling,
                not as a side effect of what happens to be inside it. */}
            <main tabIndex={0} className="min-w-0 flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
        </QueryProvider>
        </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
"use client";

/**
 * A radiogroup of cards — one choice among a handful, each with a description.
 *
 * 🔴 IT EXISTS BECAUSE `role="radiogroup"` IS A PROMISE ABOUT THE KEYBOARD.
 *
 * The settings screen declared two of them over rows of ordinary buttons, with
 * a comment saying arrow-key navigation "is what a screen reader user expects
 * from a radiogroup and does not get from a row of buttons" — and then did not
 * implement it. So the role announced a widget whose keyboard behaviour was
 * absent: every option was a separate tab stop, arrow keys did nothing, and a
 * screen reader told the user to press arrows that had no effect. The
 * Supervisor found it. That is worse than the plain buttons the comment was
 * arguing against, because the plain buttons at least behave the way they are
 * announced.
 *
 * ⚠️ SELECTION FOLLOWS FOCUS, which is the WAI-ARIA radiogroup pattern and not
 * an oversight. Arrowing to an option chooses it. That is right here for the
 * same reason the screen has no Save button: both choices apply immediately and
 * are reversible in one keystroke, so there is nothing to confirm.
 *
 * 🔴 ROVING TABINDEX, so the group is ONE tab stop rather than five. Five
 * separate stops in the middle of a settings page is exactly the keyboard
 * treacle §11 exists to prevent, and it is what the previous buttons did.
 */

import { useRef } from "react";

export interface RadioCardOption<T extends string> {
  readonly id: T;
  readonly label: string;
  /** One line a person can choose by, not a restatement of the label. */
  readonly description: string;
  /** Optional visual, e.g. a palette swatch. Decorative; never the only cue. */
  readonly preview?: React.ReactNode;
}

const TAG =
  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
  "tracking-wide text-slate-600";

export function RadioCards<T extends string>({
  labelledBy,
  options,
  value,
  onChange,
}: {
  readonly labelledBy: string;
  readonly options: readonly RadioCardOption<T>[];
  readonly value: T;
  readonly onChange: (next: T) => void;
}) {
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (from: number, delta: number) => {
    // Wrapping, because a radiogroup is a ring: arrowing past the end of five
    // options and stopping dead reads as a broken control rather than a
    // boundary.
    const next = (from + delta + options.length) % options.length;
    const option = options[next];
    if (option === undefined) return;
    onChange(option.id);
    buttons.current[next]?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        event.preventDefault();
        move(index, 1);
        break;
      case "ArrowUp":
      case "ArrowLeft":
        event.preventDefault();
        move(index, -1);
        break;
      case "Home":
        event.preventDefault();
        move(index, -index);
        break;
      case "End":
        event.preventDefault();
        move(index, options.length - 1 - index);
        break;
      default:
        break;
    }
  };

  return (
    <div role="radiogroup" aria-labelledby={labelledBy} className="mt-3 grid gap-2">
      {options.map((option, index) => {
        const chosen = option.id === value;
        return (
          <button
            key={option.id}
            ref={(element) => {
              buttons.current[index] = element;
            }}
            type="button"
            role="radio"
            aria-checked={chosen}
            // 🔴 THE GROUP IS ONE TAB STOP. Only the selected option is
            // reachable by Tab; the arrows move within. A group where every
            // option is tabbable is the thing this component replaced.
            tabIndex={chosen ? 0 : -1}
            onClick={() => onChange(option.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={[
              "flex items-center gap-3 rounded border p-3 text-left",
              chosen
                ? "border-slate-900 bg-slate-50"
                : "border-slate-200 bg-white hover:bg-slate-50",
            ].join(" ")}
          >
            {option.preview}
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-slate-900">{option.label}</span>
              <span className="block text-xs text-slate-600">{option.description}</span>
            </span>
            {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by colour
                or shape alone, and "which one is selected" is state.
                `aria-checked` says it assistively; this says it to everyone
                else. */}
            {chosen && <span className={TAG}>selected</span>}
          </button>
        );
      })}
    </div>
  );
}
"use client";

/**
 * What this person prefers — theme, and where the application opens.
 *
 * 🔴 STORED IN THE BROWSER, AND THAT IS A DECISION RATHER THAN A SHORTCUT.
 *
 * There is no user-preference endpoint, and inventing one would mean a
 * migration, a table, a route and a permission for something that is not a
 * technical record. §1 is explicit that PostgreSQL owns *verified technical
 * facts*; a colour scheme is not one, and putting it in the same database as
 * formula compositions would be the beginning of treating it like one.
 *
 * ⚠️ SO IT DOES NOT FOLLOW THE PERSON BETWEEN MACHINES, and the settings screen
 * says so. That is the honest trade, not an omission — the alternative is a
 * server round trip on every page load to decide a colour.
 *
 * 🔴 AND `localStorage` IS SAFE FOR THIS AND WOULD NOT BE FOR A TOKEN.
 * `lib/api/session.ts` records the rule: an access token in `localStorage` is
 * readable by any script on the origin, so one XSS becomes a stolen session
 * that outlives the page. A theme is not a credential. The distinction is the
 * whole reason this file may use storage and that one may not.
 */

import { useCallback, useEffect, useState } from "react";

import { DEFAULT_THEME, THEME_STORAGE_KEY, isThemeId, type ThemeId } from "./theme";

// 🔴 IMPORTED, NOT REPEATED. The pre-paint script in `app/layout.tsx` reads the
// same key before this module exists, and two spellings of a storage key cannot
// be type-checked into agreement — the reader would simply find nothing and
// paint the default, forever, with every test green.
const THEME_KEY = THEME_STORAGE_KEY;
const LANDING_KEY = "evercoat.landing";

/**
 * Where the application opens.
 *
 * Three, and each is a real destination that exists today — a preference
 * pointing at an unbuilt screen would be a setting whose only effect is a 404.
 *
 * 🔴 ITS READER IS `app/page.tsx`, AND FOR A WHILE IT HAD NONE. The front door
 * redirected to a hard-coded `/dashboard`, so this value was written by the
 * settings screen, validated on the way back out, and consulted by nothing.
 * Both reviewers found it. Because `/` resolves here before anybody presses
 * Sign in, it is also what sign-in returns you to — `signIn()` remembers where
 * you were, and where you were is this.
 */
export const LANDING_SCREENS = [
  {
    id: "/dashboard",
    label: "Dashboard",
    description: "The overview for your role — what is moving and what is waiting.",
  },
  {
    id: "/my-work",
    label: "My Work",
    description: "Only what is assigned to you or your role, and nothing else.",
  },
  {
    id: "/testing",
    label: "Testing queue",
    description: "Straight to the test queue, for a day spent on the bench.",
  },
] as const;

export type LandingScreen = (typeof LANDING_SCREENS)[number]["id"];

export const DEFAULT_LANDING: LandingScreen = "/dashboard";

export function isLandingScreen(value: string): value is LandingScreen {
  return LANDING_SCREENS.some((screen) => screen.id === value);
}

/**
 * Read a stored preference, defensively.
 *
 * 🔴 EVERY BRANCH HERE IS A REAL STATE. `localStorage` throws outright in a
 * private window with site data blocked, is absent during the server render of
 * a static export, and returns whatever a previous version of this application
 * wrote — including a theme id that no longer exists. A preference that cannot
 * be read is not an error worth surfacing; it is the default.
 */
function read<T extends string>(key: string, valid: (value: string) => value is T, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }
  try {
    const stored = window.localStorage.getItem(key);
    return stored !== null && valid(stored) ? stored : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // A preference that cannot be saved still applies for this session. Failing
    // the change because it could not be remembered would be worse than
    // forgetting it.
  }
}

export function readTheme(): ThemeId {
  return read(THEME_KEY, isThemeId, DEFAULT_THEME);
}

export function readLanding(): LandingScreen {
  return read(LANDING_KEY, isLandingScreen, DEFAULT_LANDING);
}

/**
 * The stored preferences, and the ability to change them.
 *
 * ⚠️ IT STARTS AT THE DEFAULT AND CORRECTS ON MOUNT, deliberately. A static
 * export renders on the server where there is no `localStorage`, so reading it
 * during render would make the server and client markup disagree — React's
 * hydration mismatch, which in this application would show as the settings page
 * flickering to a different answer than the one painted.
 */
export function usePreferences(): {
  readonly theme: ThemeId;
  readonly landing: LandingScreen;
  readonly setTheme: (theme: ThemeId) => void;
  readonly setLanding: (landing: LandingScreen) => void;
} {
  const [theme, setThemeState] = useState<ThemeId>(DEFAULT_THEME);
  const [landing, setLandingState] = useState<LandingScreen>(DEFAULT_LANDING);

  useEffect(() => {
    setThemeState(readTheme());
    setLandingState(readLanding());
  }, []);

  const setTheme = useCallback((next: ThemeId) => {
    setThemeState(next);
    write(THEME_KEY, next);
    // 🔴 TELL THE PROVIDER, RATHER THAN LETTING IT POLL. `storage` fires only in
    // OTHER tabs, never the one that wrote — so a same-tab change would repaint
    // nothing without this. Found the way everybody finds it.
    window.dispatchEvent(new CustomEvent("evercoat:theme", { detail: next }));
  }, []);

  const setLanding = useCallback((next: LandingScreen) => {
    setLandingState(next);
    write(LANDING_KEY, next);
  }, []);

  return { theme, landing, setTheme, setLanding };
}
"use client";

/**
 * Applies the chosen palette to `<html>`.
 *
 * 🔴 IT WRITES CSS VARIABLES RATHER THAN SWAPPING A STYLESHEET, so there is
 * exactly one definition of every palette — `lib/theme.ts` — and no second copy
 * in CSS to drift from it. `tailwind.config` resolves `bg-white`,
 * `text-slate-600` and the rest through those variables, so setting them
 * re-themes every screen at once.
 *
 * ⚠️ IT ALSO SETS `color-scheme`. Without it the browser goes on painting form
 * controls, scrollbars and the space beyond the page in light colours, so a
 * dark theme arrives with white scrollbars and a white overscroll band. That is
 * not cosmetic on a screen this dense — the scrollbar is beside a data grid on
 * most pages.
 *
 * 🔴 `system` KEEPS LISTENING. It is the only option that is not a palette but
 * a rule, and a rule that stopped applying the moment it was chosen would be a
 * setting that lies: choose "match my system", turn the machine dark at dusk,
 * and nothing happens. The media-query listener is what makes the label true.
 */

import { useEffect } from "react";

import { readTheme } from "@/lib/preferences";
import { paletteVariables, resolvePalette, type ThemeId } from "@/lib/theme";

function apply(theme: ThemeId, prefersDark: boolean): void {
  const palette = resolvePalette(theme, prefersDark);
  const root = document.documentElement;

  // 🔴 THE SAME LIST THE PRE-PAINT SCRIPT USES. `paletteVariables` is the one
  // producer; this provider and `app/layout.tsx` are its two consumers. When
  // they each owned a loop, adding a variable to one meant the page changed
  // colour the moment React arrived — the flash this pair exists to prevent.
  for (const [variable, value] of Object.entries(paletteVariables(palette))) {
    root.style.setProperty(variable, value);
  }

  // Which theme is active, for anything that needs to branch on it — and for a
  // person inspecting the page to see what they are looking at.
  root.dataset["theme"] = theme;
  root.style.colorScheme = (theme === "system" && prefersDark) || theme === "dark" ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    let current = readTheme();

    const repaint = () => apply(current, media.matches);
    repaint();

    // Same tab: the settings screen dispatches this, because `storage` fires
    // only in OTHER tabs and never in the one that wrote.
    const onChosen = (event: Event) => {
      const detail = (event as CustomEvent<ThemeId>).detail;
      current = detail;
      repaint();
    };
    // Other tabs: keep two windows of the same application in agreement.
    const onStorage = () => {
      current = readTheme();
      repaint();
    };

    window.addEventListener("evercoat:theme", onChosen);
    window.addEventListener("storage", onStorage);
    media.addEventListener("change", repaint);

    return () => {
      window.removeEventListener("evercoat:theme", onChosen);
      window.removeEventListener("storage", onStorage);
      media.removeEventListener("change", repaint);
    };
  }, []);

  return <>{children}</>;
}

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show 722df3d:apps/web/app/page.tsx; git diff 722df3d''^ 722df3d -- apps/web/components/nav/user-menu.tsx apps/web/components/providers/auth-provider.tsx apps/web/app/account/settings/page.tsx; rg -n "interface.*Me|display_name|organizations" apps/web apps/api -g "*.ts" -g "*.tsx" -g "*.py" | Select-Object -First 200' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
2026-08-27T22:09:20.274706Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 2.9 seconds
Total output lines: 670
Output:
"use client";

/**
 * Front door. Sends the visitor to the screen they chose to open on.
 *
 * WHY THIS IS A CLIENT REDIRECT AND NOT `redirect("/dashboard")`.
 *
 * This page used to be a server component calling `redirect()`. That works
 * under `output: "standalone"`, where a Node server is there to answer 307.
 * It does NOT survive `output: "export"`: there is no server, so Next has
 * nothing to emit for this route and writes an error document —
 * `out/index.html` came out as `<html id="__next_error__">` while
 * `next build` exited 0 and printed `✓ Exporting (2/2)`. The front door
 * was an error page with every gate green.
 *
 * The obvious repair — a Render redirect rule for `/` — does not work
 * either. Render's rule engine is documented as: "Render does not apply
 * redirect or rewrite rules to a path if a resource exists at that path."
 * `out/index.html` exists, so the rule would never fire. Deleting the file
 * after the build would work and is exactly the kind of second mechanism
 * that later disagrees with the first.
 *
 * So the redirect is expressed once, here, in a form that holds in BOTH
 * build modes: a real page that navigates on mount. The cost is one frame
 * of "Redirecting…" on the server build, which previously got a 307. That
 * is the deliberate trade — one mechanism that cannot drift, over two that
 * can.
 *
 * The visible link is not decoration: it is the whole page for a visitor
 * with JavaScript disabled or still loading, who would otherwise sit on a
 * blank screen with no way forward.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DEFAULT_LANDING, readLanding } from "@/lib/preferences";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // 🔴 THE CHOSEN SCREEN, NOT A CONSTANT. Settings offers three destinations
    // under "After signing in, open"; this used to be a hard `/dashboard`, so
    // the preference had no reader anywhere in the application and the screen
    // asserted a behaviour nothing implemented. Both reviewers found it — and
    // it is the project's own rule about a setting with no enforcement point,
    // reached from the other side.
    //
    // Read here rather than in a provider because this is the front door: it
    // is where "where does the application open" is actually decided, and it
    // works signed in or out.
    //
    // `replace`, not `push` — the front door should not become a back-button
    // trap that bounces the visitor straight back out to it.
    router.replace(readLanding());
  }, [router]);

  return (
    <div className="p-6">
      {/* A real <h1>, not an aria-live paragraph.
          The first version used aria-live="polite" on text that is present
          at first render and never changes. A live region announces
          CHANGES to its contents, so static text inside one is never
          announced — the accessibility benefit claimed in the comment did
          not exist. Every other route has a heading; this one had none, so
          a screen-reader user landing here got an unlabelled page.
          The layout already supplies the <main> landmark. */}
      <h1 className="text-sm font-medium text-slate-600">
        Opening the application…
      </h1>
      {/* ⚠️ THE DEFAULT, NOT THE PREFERENCE, AND DELIBERATELY SO. This link is
          the whole page for a visitor with JavaScript disabled or still
          loading. The preference lives in `localStorage`, which is only
          readable by script, so a link that claimed to honour it would be a
          link that could not — and rendering it from the preference after
          hydration would change the destination under a reader mid-click. */}
      <Link
        href={DEFAULT_LANDING}
        className="mt-2 inline-block text-sm font-medium text-slate-900 underline"
      >
        Continue to the dashboard
      </Link>
    </div>
  );
}
diff --git a/apps/web/app/account/settings/page.tsx b/apps/web/app/account/settings/page.tsx
index 6f5290d..4714106 100644
--- a/apps/web/app/account/settings/page.tsx
+++ b/apps/web/app/account/settings/page.tsx
@@ -18,13 +18,10 @@
  */
 
 import { EntityHeader } from "@/components/ui/entity-header";
-import { LANDING_SCREENS, usePreferences } from "@/lib/preferences";
+import { RadioCards } from "@/components/ui/radio-cards";
+import { LANDING_SCREENS, usePreferences, type LandingScreen } from "@/lib/preferences";
 import { PALETTES, THEMES, contrast, type ThemeId } from "@/lib/theme";
 
-const TAG =
-  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
-  "tracking-wide text-slate-600";
-
 /**
  * A miniature of what the theme actually paints.
  *
@@ -89,43 +86,24 @@ export default function SettingsPage() {
             traffic-light colours are checked against every theme.
           </p>
 
-          {/* radiogroup, not a list of buttons: these are one choice among
-              five, and arrow-key navigation between them is what a screen
-              reader user expects from a radiogroup and does not get from a row
-              of buttons. */}
-          <div role="radiogroup" aria-labelledby="theme-heading" className="mt-3 grid gap-2">
-            {THEMES.map((option) => {
-              const chosen = option.id === theme;
-              return (
-                <button
-                  key={option.id}
-                  type="button"
-                  role="radio"
-                  aria-checked={chosen}
-                  onClick={() => setTheme(option.id)}
-                  className={[
-                    "flex items-center gap-3 rounded border p-3 text-left",
-                    chosen
-                      ? "border-slate-900 bg-slate-50"
-                      : "border-slate-200 bg-white hover:bg-slate-50",
-                  ].join(" ")}
-                >
-                  <Swatch theme={option.id} />
-                  <span className="min-w-0 flex-1">
-                    <span className="block text-sm font-medium text-slate-900">
-                      {option.label}
-                    </span>
-                    <span className="block text-xs text-slate-600">{option.description}</span>
-                  </span>
-                  {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by
-                      colour or shape alone, and "which one is selected" is
-                      state. `aria-checked` says it assistively; this says it
-                      to everyone else. */}
-                  {chosen && <span className={TAG}>selected</span>}
-                </button>
-              );
-            })}
-          </div>
+          {/* 🔴 `RadioCards` RATHER THAN A ROW OF BUTTONS WITH A ROLE ON IT.
+              This markup used to declare `role="radiogroup"` over five
+              ordinary buttons, under a comment arguing that arrow-key
+              navigation "is what a screen reader user expects from a
+              radiogroup and does not get from a row of buttons" — and it did
+              not implement any. The Supervisor found the gap between the
+              comment and the widget. */}
+          <RadioCards<ThemeId>
+            labelledBy="theme-heading"
+            value={theme}
+            onChange={setTheme}
+            options={THEMES.map((option) => ({
+              id: option.id,
+              label: option.label,
+              description: option.description,
+              preview: <Swatch theme={option.id} />,
+            }))}
+          />
 
           <p className="mt-3 text-xs text-slate-600">
             Measured on the light surface: body text{" "}
@@ -137,41 +115,38 @@ export default function SettingsPage() {
 
         <section aria-labelledby="landing-heading" className="max-w-3xl">
           <h2 id="landing-heading" className="text-sm font-semibold text-slate-900">
-            After signing in, open
+            Where the application opens
           </h2>
+          {/* 🔴 THE HEADING USED TO SAY "AFTER SIGNING IN, OPEN" AND NOTHING
+              IMPLEMENTED IT. `readLanding` had no reader anywhere in the
+              codebase: the front door redirected to a hard-coded `/dashboard`
+              and sign-in returned you to wherever you already were. Both
+              reviewers found it, and it is this project's own rule — a setting
+              with no enforcement point is a defect — arriving from the user's
+              side of the screen.
+
+              It is now the front door's destination, which is also what
+              sign-in returns you to when you have not navigated somewhere
+              else first. The heading says what happens rather than the
+              narrower thing the first version claimed. */}
           <p className="mt-1 text-sm text-slate-600">
             Three screens to choose from. Each one exists — a preference pointing
             at an unbuilt screen would be a setting whose only effect is a 404.
+            Opening a link straight to a record still takes you to that record;
+            this is where you arrive when you have not asked for anywhere in
+            particular.
           </p>
 
-          <div role="radiogroup" aria-labelledby="landing-heading" className="mt-3 grid gap-2">
-            {LANDING_SCREENS.map((screen) => {
-              const chosen = screen.id === landing;
-              return (
-                <button
-                  key={screen.id}
-                  type="button"
-                  role="radio"
-                  aria-checked={chosen}
-                  onClick={() => setLanding(screen.id)}
-                  className={[
-                    "flex items-center gap-3 rounded border p-3 text-left",
-                    chosen
-                      ? "border-slate-900 bg-slate-50"
-                      : "border-slate-200 bg-white hover:bg-slate-50",
-                  ].join(" ")}
-                >
-                  <span className="min-w-0 flex-1">
-                    <span className="block text-sm font-medium text-slate-900">
-                      {screen.label}
-                    </span>
-                    <span className="block text-xs text-slate-600">{screen.description}</span>
-                  </span>
-                  {chosen && <span className={TAG}>selected</span>}
-                </button>
-              );
-            })}
-          </div>
+          <RadioCards<LandingScreen>
+            labelledBy="landing-heading"
+            value={landing}
+            onChange={setLanding}
+            options={LANDING_SCREENS.map((screen) => ({
+              id: screen.id,
+              label: screen.label,
+              description: screen.description,
+            }))}
+          />
         </section>
 
         <section className="max-w-3xl">
diff --git a/apps/web/components/nav/user-menu.tsx b/apps/web/components/nav/user-menu.tsx
index 02d0b45..44dbe32 100644
--- a/apps/web/components/nav/user-menu.tsx
+++ b/apps/web/components/nav/user-menu.tsx
@@ -27,7 +27,7 @@ import { useAuth } from "@/components/providers/auth-provider";
 /** The three things a person can do about their own account. */
 const ITEMS = [
   { href: "/account/profile", label: "Profile", hint: "Who you are here, and what you may do" },
-  { href: "/account/settings", label: "Settings", hint: "Theme, and where you land after signing in" },
+  { href: "/account/settings", label: "Settings", hint: "Theme, and where the application opens" },
   { href: "/account/security", label: "Security", hint: "Your session, password and sign-out" },
 ] as const;
 
@@ -35,6 +35,8 @@ export function UserMenu() {
   const { profile } = useAuth();
   const [open, setOpen] = useState(false);
   const container = useRef<HTMLDivElement>(null);
+  const trigger = useRef<HTMLButtonElement>(null);
+  const firstItem = useRef<HTMLAnchorElement>(null);
 
   // 🔴 CLOSES ON OUTSIDE CLICK **AND** ON ESCAPE. A menu that only closes by
   // clicking its own trigger is a keyboard trap: tab into it, and the only way
@@ -48,7 +50,14 @@ export function UserMenu() {
       }
     };
     const onKey = (event: KeyboardEvent) => {
-      if (event.key === "Escape") setOpen(false);
+      if (event.key !== "Escape") return;
+      setOpen(false);
+      // 🔴 AND FOCUS GOES BACK TO THE TRIGGER. Escape used to close the menu
+      // and leave focus on an element that had just been removed from the
+      // document, which browsers resolve by sending it to `<body>` — so a
+      // keyboard user was returned to the top of the page and had to tab all
+      // the way back to where they were. Codex found it.
+      trigger.current?.focus();
     };
 
     document.addEventListener("mousedown", onPointer);
@@ -59,6 +68,15 @@ export function UserMenu() {
     };
   }, [open]);
 
+  // 🔴 OPENING A MENU MOVES FOCUS INTO IT. Without this the menu appeared and
+  // focus stayed on the trigger, so a screen reader announced a menu the user
+  // then had to hunt for, and the next Tab left it entirely. This is the other
+  // half of the Escape behaviour above: focus enters on open and returns on
+  // close, which is what `aria-haspopup="menu"` promises.
+  useEffect(() => {
+    if (open) firstItem.current?.focus();
+  }, [open]);
+
   if (profile === null) {
     return null;
   }
@@ -66,6 +84,7 @@ export function UserMenu() {
   return (
     <div ref={container} className="relative">
       <button
+        ref={trigger}
         type="button"
         aria-expanded={open}
         aria-haspopup="menu"
@@ -103,9 +122,10 @@ export function UserMenu() {
             <p className="truncate text-xs text-slate-600">{profile.email}</p>
           </div>
 
-          {ITEMS.map((item) => (
+          {ITEMS.map((item, index) => (
             <Link
               key={item.href}
+              ref={index === 0 ? firstItem : undefined}
               href={item.href}
               role="menuitem"
               onClick={() => setOpen(false)}
diff --git a/apps/web/components/providers/auth-provider.tsx b/apps/web/components/providers/auth-provider.tsx
index bc25485..0ec4d40 100644
--- a/apps/web/components/providers/auth-provider.tsx
+++ b/apps/web/components/providers/auth-provider.tsx
@@ -57,18 +57,27 @@ import { safeReturnTo, saveFlow } from "@/lib/auth/flow-state";
 import { authorizationUrl, createChallenge, refreshTokens } from "@/lib/auth/pkce";
 
 /**
- * Who the signed-in person is, as `/api/me` reports them.
+ * Who the signed-in person is, in the organization they are currently working in.
  *
- * 🔴 THE API HAS ALWAYS SENT THIS AND THE PROVIDER THREW IT AWAY.
- * `GET /api/me` returns `user_id`, `email` and `display_name` at the top level
- * beside `organizations`, and the parse below read only `organizations`. So the
- * application knew the caller's name on every load and had nowhere to put it —
- * which is why the top bar showed a grey circle with a dash in it.
+ * 🔴 DERIVED FROM THE ACTIVE MEMBERSHIP. NOT STORED, AND THAT IS THE FIX.
+ *
+ * It used to be its own `useState`, set from a top-level `display_name` on
+ * `/api/me`, and it went wrong in three directions at once. `signOut` cleared
+ * the session and the organizations and never cleared this, so the previous
+ * user's name stayed in the top bar of an anonymous application — on a shared
+ * bench machine, somebody else's name over your work. Switching organization
+ * did not change it. And the value itself was whichever tenant sorted first
+ * alphabetically, because migration 052 put the name on the MEMBERSHIP and the
+ * route flattened the rows back to one.
+ *
+ * All three were the same defect: a per-tenant fact kept as though it were a
+ * global one, in a second place, needing a second thing to remember to clear
+ * it. Derived from the active membership there is nothing to clear, nothing to
+ * refresh, and no second copy — the anonymous state has no active membership,
+ * so it has no name. Both reviewers found the first of the three; Codex found
+ * the second.
  *
  * ⚠️ THIS IS THE ORGANIZATION'S VIEW OF THE PERSON, not a global identity.
- * Migration 052 moved `email` and `display_name` onto the membership (I106);
- * `/api/me` resolves them through the same path, so what arrives here is the
- * name THIS tenant knows them by.
  */
 export interface UserProfile {
   readonly userId: string;
@@ -95,6 +104,9 @@ export interface OrganizationChoice {
   readonly organizationId: string;
   readonly name: string;
   readonly code: string;
+  /** What THIS organization calls the caller (052). Per-tenant, like the roles. */
+  readonly email: string;
+  readonly displayName: string;
   readonly roles: readonly string[];
   /**
    * Permission codes held in THIS organization (I79).
@@ -170,10 +182,45 @@ export function chooseOrganization(
   return first;
 }
 
+/**
+ * The caller as the organization they are working in knows them.
+ *
+ * 🔴 A BLANK NAME IS AN ABSENT NAME. The previous version required all three
+ * fields to be `!== undefined`, which an empty string satisfies — so an API
+ * returning `""` produced "signed in as ''" in the top bar, under a comment
+ * claiming that exact case was excluded. Codex found the gap between the
+ * comment and the check. Nothing here trims a name into existence: if either
+ * attribute is blank there is no profile, and `UserMenu` renders nothing rather
+ * than an initialled circle with no initials.
+ *
+ * Exported and pure so the rule can be tested without a network call or a
+ * React tree — the same reason `chooseOrganization` is.
+ */
+export function activeProfile(
+  session: SessionState,
+  organizations: readonly OrganizationChoice[],
+): UserProfile | null {
+  // Anonymous has no active membership, so it has no name. That is the whole
+  // of the "signOut must clear the profile" fix: there is no profile to clear.
+  if (session.status !== "authenticated") return null;
+
+  const active = organizations.find(
+    (org) => org.organizationId === session.credentials.organizationId,
+  );
+  if (active === undefined) return null;
+
+  if (active.displayName.trim() === "" || active.email.trim() === "") return null;
+
+  return {
+    userId: session.credentials.userId,
+    email: active.email,
+    displayName: active.displayName,
+  };
+}
+
 export function AuthProvider({ children }: { children: React.ReactNode }) {
   const session = useSession();
   const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
-  const [profile, setProfile] = useState<UserProfile | null>(null);
   const tokens = useRef<LiveTokens | null>(null);
   const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
   // 🔴 clearTimeout CANNOT STOP A REFRESH THAT IS ALREADY IN FLIGHT.
@@ -251,12 +298,12 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
 
     const body = (await response.json()) as {
       user_id?: string;
-      email?: string;
-      display_name?: string;
       organizations?: {
         organization_id: string;
         name: string;
         code: string;
+        email?: string;
+        display_name?: string;
         roles?: string[];
         permissions?: string[];
       }[];
@@ -266,6 +313,11 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
       organizationId: org.organization_id,
       name: org.name,
       code: org.code,
+      // 🔴 THE MEMBERSHIP'S OWN PAIR (052). An API too old to send them yields
+      // an empty string, which `useProfile` reads as "no name" rather than
+      // rendering "signed in as ''" — see the profile derivation below.
+      email: org.email ?? "",
+      displayName: org.display_name ?? "",
       roles: org.roles ?? [],
       // `?? []` and not `?? ALL_NAV_PERMISSIONS`: an API …1317 tokens truncated…tes.py:155:        owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org_id})
apps/api\tests\auth\test_admin_member_routes.py:180:        "display_name": "Newly Invited",
apps/api\tests\auth\test_admin_member_routes.py:203:    assert got["display_name"] == body["display_name"]
apps/api\tests\auth\test_admin_member_routes.py:211:            SELECT organization_id, email::text, display_name
apps/api\tests\auth\test_admin_member_routes.py:218:    assert (stored.email, stored.display_name) == (body["email"], body["display_name"])
apps/api\tests\auth\conftest.py:154:        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\conftest.py:159:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\conftest.py:167:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:233:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\conftest.py:241:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:251:        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\conftest.py:256:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\conftest.py:264:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:319:    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": org_id})
apps/api\tests\auth\conftest.py:320:    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": foreign_org_id})
apps/api\tests\auth\conftest.py:353:        text("INSERT INTO core.organizations (code, name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\conftest.py:359:            "INSERT INTO core.users (keycloak_sub, email, display_name) "
apps/api\tests\auth\conftest.py:368:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:426:        ("DELETE FROM core.organizations WHERE id=:o", {"o": org_id}),
apps/web\components\providers\auth-provider.tsx:64: * It used to be its own `useState`, set from a top-level `display_name` on
apps/web\components\providers\auth-provider.tsx:66: * the session and the organizations and never cleared this, so the previous
apps/web\components\providers\auth-provider.tsx:99:  readonly organizations: readonly OrganizationChoice[];
apps/web\components\providers\auth-provider.tsx:122:   * organizations -- no session at all -- is the different case, handled
apps/web\components\providers\auth-provider.tsx:180:    throw new Error("chooseOrganization called with no organizations");
apps/web\components\providers\auth-provider.tsx:201:  organizations: readonly OrganizationChoice[],
apps/web\components\providers\auth-provider.tsx:207:  const active = organizations.find(
apps/web\components\providers\auth-provider.tsx:223:  const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
apps/web\components\providers\auth-provider.tsx:301:      organizations?: {
apps/web\components\providers\auth-provider.tsx:306:        display_name?: string;
apps/web\components\providers\auth-provider.tsx:312:    const choices: OrganizationChoice[] = (body.organizations ?? []).map((org) => ({
apps/web\components\providers\auth-provider.tsx:320:      displayName: org.display_name ?? "",
apps/web\components\providers\auth-provider.tsx:581:      if (!organizations.some((org) => org.organizationId === organizationId)) return;
apps/web\components\providers\auth-provider.tsx:583:      // is memoised on `organizations` and would otherwise close over a
apps/web\components\providers\auth-provider.tsx:593:    [organizations],
apps/web\components\providers\auth-provider.tsx:597:    () => activeProfile(session, organizations),
apps/web\components\providers\auth-provider.tsx:598:    [session, organizations],
apps/web\components\providers\auth-provider.tsx:608:      organizations,
apps/web\components\providers\auth-provider.tsx:611:    [session, signIn, signOut, profile, organizations, selectOrganization],
apps/web\components\providers\auth-provider.test.ts:77:    expect(() => chooseOrganization([], undefined)).toThrow(/no organizations/);
apps/web\components\providers\auth-provider.test.ts:85: * organizations and never cleared the profile, so the previous user's name
apps/web\components\providers\auth-provider.test.ts:89: * top-level `display_name` that `/api/me` filled from whichever tenant sorted
apps/web\components\providers\auth-provider.test.ts:108:    // The finding, exactly. The organizations list survives a failed refresh
apps/web\components\nav\user-menu.tsx:7: * `GET /api/me` returns `display_name` and `email` beside `organizations`, and
apps/web\components\nav\user-menu.tsx:8: * the auth provider parsed only the organizations — so the top bar showed a
apps/web\components\nav\top-bar.tsx:11: * to several organizations, and switching must NAVIGATE rather than
apps/web\components\nav\top-bar.tsx:85:            always returned `display_name`; the auth provider parsed only the
apps/web\components\nav\top-bar.tsx:86:            organizations and threw it away, which is why this spot held a grey
apps/web\components\nav\app-sidebar.tsx:70:  const { organizations } = useAuth();
apps/web\components\nav\app-sidebar.tsx:73:    organizations,
apps/web\components\nav\account-menu.tsx:12: * It offers ONLY organizations the API itself returned. A free-text
apps/web\components\nav\account-menu.tsx:22:  const { session, configured, signIn, signOut, organizations, selectOrganization } = useAuth();
apps/web\components\nav\account-menu.tsx:72:        {organizations.map((org) => (
apps/api\app\domains\tasks\service.py:636:                   u.display_name AS assignee,
apps/api\tests\test_upload_pipeline_units.py:199:def test_a_traversal_filename_cannot_survive_as_a_display_name() -> None:
apps/api\tests\test_upload_pipeline_units.py:211:def test_a_nameless_file_still_gets_a_display_name() -> None:
apps/api\tests\test_msd_conductor.py:67:            display_name="Caller",
apps/api\tests\test_me_identity_shape.py:4:``display_name`` from ``core.users`` onto ``core.organization_members``, and
apps/api\tests\test_me_identity_shape.py:11:organization sorts first alphabetically. A member of two organizations working
apps/api\tests\test_me_identity_shape.py:54:def _rows_for_two_organizations() -> list[dict[str, Any]]:
apps/api\tests\test_me_identity_shape.py:55:    """One person, two organizations, two different names — the only shape that
apps/api\tests\test_me_identity_shape.py:67:            "display_name": "Known In Acme",
apps/api\tests\test_me_identity_shape.py:77:            "display_name": "Different Name Entirely",
apps/api\tests\test_me_identity_shape.py:85:def two_organizations(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
apps/api\tests\test_me_identity_shape.py:86:    rows = _rows_for_two_organizations()
apps/api\tests\test_me_identity_shape.py:105:    tenant_attributes = fields & {"email", "display_name"}
apps/api\tests\test_me_identity_shape.py:112:    assert fields == {"user_id", "organizations"}, (
apps/api\tests\test_me_identity_shape.py:117:    assert {"email", "display_name"} <= membership, (
apps/api\tests\test_me_identity_shape.py:123:async def test_each_membership_reports_its_own_organizations_view(
apps/api\tests\test_me_identity_shape.py:124:    two_organizations: list[dict[str, Any]],
apps/api\tests\test_me_identity_shape.py:134:    by_code = {org.code: org for org in response.organizations}
apps/api\tests\test_me_identity_shape.py:137:    assert (by_code["ACME"].email, by_code["ACME"].display_name) == (
apps/api\tests\test_me_identity_shape.py:141:    assert (by_code["ZEN"].email, by_code["ZEN"].display_name) == (
apps/api\tests\test_me_identity_shape.py:152:    assert response.user_id == two_organizations[0]["user_id"]
apps/api\tests\test_me_identity_shape.py:153:    assert len({org.organization_id for org in response.organizations}) == 2
apps/api\tests\test_conductor_boundary.py:85:            display_name="Caller",
apps/api\tests\test_conductor_boundary.py:1153:        display_name="d",
apps/api\tests\test_conductor_boundary.py:1472:            display_name="Caller",
apps/api\app\core\tenancy.py:4:belongs to organizations through `core.organization_members`, and may
apps/api\app\core\security.py:85:    display_name: str
apps/api\app\core\security.py:200:    SELECT user_id, email, display_name, organization_id, roles, permissions
apps/api\app\core\security.py:341:        display_name=row["display_name"],
apps/api\app\core\file_types.py:120:    """Return `(canonical_content_type, safe_display_name)` or raise.
apps/api\app\core\db.py:224:    organizations the caller's own subject may act in. Both take the subject
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:25:`core.users.email` and `core.users.display_name` stop being readable by the
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:141:    display_name    TEXT,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:153:           u.display_name,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:170:    GROUP BY u.id, u.email, u.display_name, om.organization_id
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:179:    display_name      TEXT,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:193:           u.display_name,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:205:    JOIN core.organizations o
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:214:    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:280:        "        (organization_id, user_id, email, display_name)\n"
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:281:        "    VALUES (v_org, v_user, p_email::public.citext, p_display_name)",
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:287:    # The first version asked whether `"email, display_name"` still appeared
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:300:        "(organization_id, user_id, email, display_name)" in restored
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:356:            "GRANT SELECT (email, display_name) ON core.users"
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:360:    op.execute(text("GRANT UPDATE (email, display_name) ON core.users TO evercoat_app"))
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:365:        text("ALTER TABLE core.organization_members DROP COLUMN email, DROP COLUMN display_name")
apps/api\migrations_alembic\versions\2026_08_26_0050-i1000_bind_proves_the_caller_administers.py:67:                p_subject TEXT, p_email TEXT, p_display_name TEXT
apps/api\migrations_alembic\versions\2026_08_26_0050-i1000_bind_proves_the_caller_administers.py:85:                    INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\migrations_alembic\versions\2026_08_26_0050-i1000_bind_proves_the_caller_administers.py:86:                    VALUES (p_subject, p_email::public.citext, p_display_name)
apps/api\migrations_alembic\versions\2026_08_25_0047-f2000_an_authentication_identifier_is_not_readable.py:11:before acting: `display_name` has eleven readers, `email` has two production
apps/api\migrations_alembic\versions\2026_08_25_0047-f2000_an_authentication_identifier_is_not_readable.py:62:            "REVOKE SELECT (id, email, display_name, status, created_at, updated_at)"
apps/api\migrations_alembic\versions\2026_08_25_0047-f2000_an_authentication_identifier_is_not_readable.py:66:    op.execute(text("REVOKE UPDATE (email, display_name) ON core.users FROM evercoat_app"))
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:9:`GET /api/me` returned `organizations[].roles` and no permissions, so
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:68:                display_name      TEXT,
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:81:                       u.display_name,
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:91:                JOIN core.organizations o
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:98:                GROUP BY u.id, u.email, u.display_name, om.organization_id,
apps/api\migrations_alembic\versions\2026_08_23_0044-e8000_user_directory_is_not_global.py:15:UPDATE SET display_name` was run as `evercoat_app` under organization A's GUC
apps/api\migrations_alembic\versions\2026_08_22_0032-d5000_the_database_fails_closed.py:13:organizations, 137 projects**. The entire database, every tenant. The only
apps/api\migrations_alembic\versions\2026_08_22_0032-d5000_the_database_fails_closed.py:23:what tells a signed-in browser which organizations exist for it. Forcing RLS
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:8:`FOR org IN SELECT id FROM core.organizations LOOP`. There is no trigger and
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:18:AFTER INSERT trigger on `core.organizations`, and a backfill for the
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:19:organizations 020 left behind. The migration verifies its own backfill and
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:57:    op.execute("DROP TRIGGER IF EXISTS organizations_get_approval_templates ON core.organizations")
apps/api\app\domains\projects\members.py:241:                   u.display_name, u.email::text AS email,
apps/api\app\domains\projects\members.py:260:                u.display_name
apps/api\app\domains\projects\dashboard.py:55:                   lead.display_name     AS lead_name,
apps/api\app\domains\projects\dashboard.py:56:                   director.display_name AS director_name,
apps/api\app\domains\projects\dashboard.py:64:            -- Names come from the MEMBERSHIP (052): `core.users.display_name`
apps/api\app\domains\projects\dashboard.py:173:                   t.required_action, u.display_name AS assignee
apps/api\app\domains\projects\dashboard.py:250:            SELECT t.transitioned_at AS at, t.reason, u.display_name AS actor,
apps/api\app\domains\pipeline\service.py:344:                   u.display_name AS actor,
apps/api\app\domains\opportunities\service.py:554:                   u.display_name AS created_by_name,
apps/api\app\domains\opportunities\service.py:594:            SELECT o.*, u.display_name AS created_by_name,
apps/api\app\domains\opportunities\service.py:595:                   d.display_name AS decided_by_name,
apps/api\tests\db\test_slice2_tasks.py:39:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_tasks.py:48:                INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_tasks.py:61:                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
apps/api\tests\db\test_slice2_tasks.py:391:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\app\api\me.py:70:    #: each row carries its own ``om.email`` / ``om.display_name`` -- the
apps/api\app\api\me.py:75:    #: two organizations saw the alphabetically-first one's name in the top bar
apps/api\app\api\me.py:81:    display_name: str
apps/api\app\api\me.py:118:    everything else onto the membership. A top-level ``display_name`` is a
apps/api\app\api\me.py:128:    organizations: list[OrganizationMembership] = Field(default_factory=list)
apps/api\app\api\me.py:133:# definition of "which organizations may this subject act in" and no
apps/api\app\api\me.py:191:        organizations=[
apps/api\app\api\me.py:197:                display_name=row["display_name"],
apps/api\tests\integration\test_auth_end_to_end.py:276:def test_a_signed_in_user_can_discover_their_organizations() -> None:
apps/api\tests\integration\test_auth_end_to_end.py:291:    assert body["organizations"], (
apps/api\tests\integration\test_auth_end_to_end.py:292:        "a valid token resolved to a user with NO organizations. A browser "
apps/api\tests\integration\test_auth_end_to_end.py:297:    org = body["organizations"][0]
apps/api\tests\integration\test_auth_end_to_end.py:304:    # known by different addresses in different organizations.
apps/api\tests\integration\test_auth_end_to_end.py:306:    assert org["display_name"], "a membership with no name renders as a blank top bar"
apps/api\tests\integration\test_auth_end_to_end.py:353:    organization_id = me.json()["organizations"][0]["organization_id"]
apps/api\tests\db\test_slice2_stage_gates.py:40:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_stage_gates.py:233:def test_reorder_cannot_reach_another_organizations_stages(owner_session, gate_world):
apps/api\tests\db\test_slice2_stage_gates.py:241:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_review_fixes.py:52:    """Two organizations, each with one active member, plus a project."""
apps/api\tests\db\test_slice2_review_fixes.py:58:            text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_review_fixes.py:64:                INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_review_fixes.py:77:                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
apps/api\tests\db\test_slice2_review_fixes.py:276:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_review_fixes.py:285:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\tests\db\test_slice2_review_fixes.py:330:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_review_fixes.py:339:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\tests\db\test_slice2_opportunities.py:39:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_opportunities.py:46:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_opportunities.py:55:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\app\api\admin.py:53:    display_name: str
apps/api\app\api\admin.py:67:    display_name: str = Field(min_length=1, max_length=200)
apps/api\app\api\admin.py:173:                   om.display_name, om.status,

 exited 1 in 2926ms:
"use client";

/**
 * Front door. Sends the visitor to the screen they chose to open on.
 *
 * WHY THIS IS A CLIENT REDIRECT AND NOT `redirect("/dashboard")`.
 *
 * This page used to be a server component calling `redirect()`. That works
 * under `output: "standalone"`, where a Node server is there to answer 307.
 * It does NOT survive `output: "export"`: there is no server, so Next has
 * nothing to emit for this route and writes an error document —
 * `out/index.html` came out as `<html id="__next_error__">` while
 * `next build` exited 0 and printed `✓ Exporting (2/2)`. The front door
 * was an error page with every gate green.
 *
 * The obvious repair — a Render redirect rule for `/` — does not work
 * either. Render's rule engine is documented as: "Render does not apply
 * redirect or rewrite rules to a path if a resource exists at that path."
 * `out/index.html` exists, so the rule would never fire. Deleting the file
 * after the build would work and is exactly the kind of second mechanism
 * that later disagrees with the first.
 *
 * So the redirect is expressed once, here, in a form that holds in BOTH
 * build modes: a real page that navigates on mount. The cost is one frame
 * of "Redirecting…" on the server build, which previously got a 307. That
 * is the deliberate trade — one mechanism that cannot drift, over two that
 * can.
 *
 * The visible link is not decoration: it is the whole page for a visitor
 * with JavaScript disabled or still loading, who would otherwise sit on a
 * blank screen with no way forward.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { DEFAULT_LANDING, readLanding } from "@/lib/preferences";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // 🔴 THE CHOSEN SCREEN, NOT A CONSTANT. Settings offers three destinations
    // under "After signing in, open"; this used to be a hard `/dashboard`, so
    // the preference had no reader anywhere in the application and the screen
    // asserted a behaviour nothing implemented. Both reviewers found it — and
    // it is the project's own rule about a setting with no enforcement point,
    // reached from the other side.
    //
    // Read here rather than in a provider because this is the front door: it
    // is where "where does the application open" is actually decided, and it
    // works signed in or out.
    //
    // `replace`, not `push` — the front door should not become a back-button
    // trap that bounces the visitor straight back out to it.
    router.replace(readLanding());
  }, [router]);

  return (
    <div className="p-6">
      {/* A real <h1>, not an aria-live paragraph.
          The first version used aria-live="polite" on text that is present
          at first render and never changes. A live region announces
          CHANGES to its contents, so static text inside one is never
          announced — the accessibility benefit claimed in the comment did
          not exist. Every other route has a heading; this one had none, so
          a screen-reader user landing here got an unlabelled page.
          The layout already supplies the <main> landmark. */}
      <h1 className="text-sm font-medium text-slate-600">
        Opening the application…
      </h1>
      {/* ⚠️ THE DEFAULT, NOT THE PREFERENCE, AND DELIBERATELY SO. This link is
          the whole page for a visitor with JavaScript disabled or still
          loading. The preference lives in `localStorage`, which is only
          readable by script, so a link that claimed to honour it would be a
          link that could not — and rendering it from the preference after
          hydration would change the destination under a reader mid-click. */}
      <Link
        href={DEFAULT_LANDING}
        className="mt-2 inline-block text-sm font-medium text-slate-900 underline"
      >
        Continue to the dashboard
      </Link>
    </div>
  );
}
diff --git a/apps/web/app/account/settings/page.tsx b/apps/web/app/account/settings/page.tsx
index 6f5290d..4714106 100644
--- a/apps/web/app/account/settings/page.tsx
+++ b/apps/web/app/account/settings/page.tsx
@@ -18,13 +18,10 @@
  */
 
 import { EntityHeader } from "@/components/ui/entity-header";
-import { LANDING_SCREENS, usePreferences } from "@/lib/preferences";
+import { RadioCards } from "@/components/ui/radio-cards";
+import { LANDING_SCREENS, usePreferences, type LandingScreen } from "@/lib/preferences";
 import { PALETTES, THEMES, contrast, type ThemeId } from "@/lib/theme";
 
-const TAG =
-  "rounded border border-slate-300 px-1.5 py-0.5 text-[10px] font-medium uppercase " +
-  "tracking-wide text-slate-600";
-
 /**
  * A miniature of what the theme actually paints.
  *
@@ -89,43 +86,24 @@ export default function SettingsPage() {
             traffic-light colours are checked against every theme.
           </p>
 
-          {/* radiogroup, not a list of buttons: these are one choice among
-              five, and arrow-key navigation between them is what a screen
-              reader user expects from a radiogroup and does not get from a row
-              of buttons. */}
-          <div role="radiogroup" aria-labelledby="theme-heading" className="mt-3 grid gap-2">
-            {THEMES.map((option) => {
-              const chosen = option.id === theme;
-              return (
-                <button
-                  key={option.id}
-                  type="button"
-                  role="radio"
-                  aria-checked={chosen}
-                  onClick={() => setTheme(option.id)}
-                  className={[
-                    "flex items-center gap-3 rounded border p-3 text-left",
-                    chosen
-                      ? "border-slate-900 bg-slate-50"
-                      : "border-slate-200 bg-white hover:bg-slate-50",
-                  ].join(" ")}
-                >
-                  <Swatch theme={option.id} />
-                  <span className="min-w-0 flex-1">
-                    <span className="block text-sm font-medium text-slate-900">
-                      {option.label}
-                    </span>
-                    <span className="block text-xs text-slate-600">{option.description}</span>
-                  </span>
-                  {/* 🔴 A WORD, NOT A TICK ALONE. §11 forbids state carried by
-                      colour or shape alone, and "which one is selected" is
-                      state. `aria-checked` says it assistively; this says it
-                      to everyone else. */}
-                  {chosen && <span className={TAG}>selected</span>}
-                </button>
-              );
-            })}
-          </div>
+          {/* 🔴 `RadioCards` RATHER THAN A ROW OF BUTTONS WITH A ROLE ON IT.
+              This markup used to declare `role="radiogroup"` over five
+              ordinary buttons, under a comment arguing that arrow-key
+              navigation "is what a screen reader user expects from a
+              radiogroup and does not get from a row of buttons" — and it did
+              not implement any. The Supervisor found the gap between the
+              comment and the widget. */}
+          <RadioCards<ThemeId>
+            labelledBy="theme-heading"
+            value={theme}
+            onChange={setTheme}
+            options={THEMES.map((option) => ({
+              id: option.id,
+              label: option.label,
+              description: option.description,
+              preview: <Swatch theme={option.id} />,
+            }))}
+          />
 
           <p className="mt-3 text-xs text-slate-600">
             Measured on the light surface: body text{" "}
@@ -137,41 +115,38 @@ export default function SettingsPage() {
 
         <section aria-labelledby="landing-heading" className="max-w-3xl">
           <h2 id="landing-heading" className="text-sm font-semibold text-slate-900">
-            After signing in, open
+            Where the application opens
           </h2>
+          {/* 🔴 THE HEADING USED TO SAY "AFTER SIGNING IN, OPEN" AND NOTHING
+              IMPLEMENTED IT. `readLanding` had no reader anywhere in the
+              codebase: the front door redirected to a hard-coded `/dashboard`
+              and sign-in returned you to wherever you already were. Both
+              reviewers found it, and it is this project's own rule — a setting
+              with no enforcement point is a defect — arriving from the user's
+              side of the screen.
+
+              It is now the front door's destination, which is also what
+              sign-in returns you to when you have not navigated somewhere
+              else first. The heading says what happens rather than the
+              narrower thing the first version claimed. */}
           <p className="mt-1 text-sm text-slate-600">
             Three screens to choose from. Each one exists — a preference pointing
             at an unbuilt screen would be a setting whose only effect is a 404.
+            Opening a link straight to a record still takes you to that record;
+            this is where you arrive when you have not asked for anywhere in
+            particular.
           </p>
 
-          <div role="radiogroup" aria-labelledby="landing-heading" className="mt-3 grid gap-2">
-            {LANDING_SCREENS.map((screen) => {
-              const chosen = screen.id === landing;
-              return (
-                <button
-                  key={screen.id}
-                  type="button"
-                  role="radio"
-                  aria-checked={chosen}
-                  onClick={() => setLanding(screen.id)}
-                  className={[
-                    "flex items-center gap-3 rounded border p-3 text-left",
-                    chosen
-                      ? "border-slate-900 bg-slate-50"
-                      : "border-slate-200 bg-white hover:bg-slate-50",
-                  ].join(" ")}
-                >
-                  <span className="min-w-0 flex-1">
-                    <span className="block text-sm font-medium text-slate-900">
-                      {screen.label}
-                    </span>
-                    <span className="block text-xs text-slate-600">{screen.description}</span>
-                  </span>
-                  {chosen && <span className={TAG}>selected</span>}
-                </button>
-              );
-            })}
-          </div>
+          <RadioCards<LandingScreen>
+            labelledBy="landing-heading"
+            value={landing}
+            onChange={setLanding}
+            options={LANDING_SCREENS.map((screen) => ({
+              id: screen.id,
+              label: screen.label,
+              description: screen.description,
+            }))}
+          />
         </section>
 
         <section className="max-w-3xl">
diff --git a/apps/web/components/nav/user-menu.tsx b/apps/web/components/nav/user-menu.tsx
index 02d0b45..44dbe32 100644
--- a/apps/web/components/nav/user-menu.tsx
+++ b/apps/web/components/nav/user-menu.tsx
@@ -27,7 +27,7 @@ import { useAuth } from "@/components/providers/auth-provider";
 /** The three things a person can do about their own account. */
 const ITEMS = [
   { href: "/account/profile", label: "Profile", hint: "Who you are here, and what you may do" },
-  { href: "/account/settings", label: "Settings", hint: "Theme, and where you land after signing in" },
+  { href: "/account/settings", label: "Settings", hint: "Theme, and where the application opens" },
   { href: "/account/security", label: "Security", hint: "Your session, password and sign-out" },
 ] as const;
 
@@ -35,6 +35,8 @@ export function UserMenu() {
   const { profile } = useAuth();
   const [open, setOpen] = useState(false);
   const container = useRef<HTMLDivElement>(null);
+  const trigger = useRef<HTMLButtonElement>(null);
+  const firstItem = useRef<HTMLAnchorElement>(null);
 
   // 🔴 CLOSES ON OUTSIDE CLICK **AND** ON ESCAPE. A menu that only closes by
   // clicking its own trigger is a keyboard trap: tab into it, and the only way
@@ -48,7 +50,14 @@ export function UserMenu() {
       }
     };
     const onKey = (event: KeyboardEvent) => {
-      if (event.key === "Escape") setOpen(false);
+      if (event.key !== "Escape") return;
+      setOpen(false);
+      // 🔴 AND FOCUS GOES BACK TO THE TRIGGER. Escape used to close the menu
+      // and leave focus on an element that had just been removed from the
+      // document, which browsers resolve by sending it to `<body>` — so a
+      // keyboard user was returned to the top of the page and had to tab all
+      // the way back to where they were. Codex found it.
+      trigger.current?.focus();
     };
 
     document.addEventListener("mousedown", onPointer);
@@ -59,6 +68,15 @@ export function UserMenu() {
     };
   }, [open]);
 
+  // 🔴 OPENING A MENU MOVES FOCUS INTO IT. Without this the menu appeared and
+  // focus stayed on the trigger, so a screen reader announced a menu the user
+  // then had to hunt for, and the next Tab left it entirely. This is the other
+  // half of the Escape behaviour above: focus enters on open and returns on
+  // close, which is what `aria-haspopup="menu"` promises.
+  useEffect(() => {
+    if (open) firstItem.current?.focus();
+  }, [open]);
+
   if (profile === null) {
     return null;
   }
@@ -66,6 +84,7 @@ export function UserMenu() {
   return (
     <div ref={container} className="relative">
       <button
+        ref={trigger}
         type="button"
         aria-expanded={open}
         aria-haspopup="menu"
@@ -103,9 +122,10 @@ export function UserMenu() {
             <p className="truncate text-xs text-slate-600">{profile.email}</p>
           </div>
 
-          {ITEMS.map((item) => (
+          {ITEMS.map((item, index) => (
             <Link
               key={item.href}
+              ref={index === 0 ? firstItem : undefined}
               href={item.href}
               role="menuitem"
               onClick={() => setOpen(false)}
diff --git a/apps/web/components/providers/auth-provider.tsx b/apps/web/components/providers/auth-provider.tsx
index bc25485..0ec4d40 100644
--- a/apps/web/components/providers/auth-provider.tsx
+++ b/apps/web/components/providers/auth-provider.tsx
@@ -57,18 +57,27 @@ import { safeReturnTo, saveFlow } from "@/lib/auth/flow-state";
 import { authorizationUrl, createChallenge, refreshTokens } from "@/lib/auth/pkce";
 
 /**
- * Who the signed-in person is, as `/api/me` reports them.
+ * Who the signed-in person is, in the organization they are currently working in.
  *
- * 🔴 THE API HAS ALWAYS SENT THIS AND THE PROVIDER THREW IT AWAY.
- * `GET /api/me` returns `user_id`, `email` and `display_name` at the top level
- * beside `organizations`, and the parse below read only `organizations`. So the
- * application knew the caller's name on every load and had nowhere to put it —
- * which is why the top bar showed a grey circle with a dash in it.
+ * 🔴 DERIVED FROM THE ACTIVE MEMBERSHIP. NOT STORED, AND THAT IS THE FIX.
+ *
+ * It used to be its own `useState`, set from a top-level `display_name` on
+ * `/api/me`, and it went wrong in three directions at once. `signOut` cleared
+ * the session and the organizations and never cleared this, so the previous
+ * user's name stayed in the top bar of an anonymous application — on a shared
+ * bench machine, somebody else's name over your work. Switching organization
+ * did not change it. And the value itself was whichever tenant sorted first
+ * alphabetically, because migration 052 put the name on the MEMBERSHIP and the
+ * route flattened the rows back to one.
+ *
+ * All three were the same defect: a per-tenant fact kept as though it were a
+ * global one, in a second place, needing a second thing to remember to clear
+ * it. Derived from the active membership there is nothing to clear, nothing to
+ * refresh, and no second copy — the anonymous state has no active membership,
+ * so it has no name. Both reviewers found the first of the three; Codex found
+ * the second.
  *
  * ⚠️ THIS IS THE ORGANIZATION'S VIEW OF THE PERSON, not a global identity.
- * Migration 052 moved `email` and `display_name` onto the membership (I106);
- * `/api/me` resolves them through the same path, so what arrives here is the
- * name THIS tenant knows them by.
  */
 export interface UserProfile {
   readonly userId: string;
@@ -95,6 +104,9 @@ export interface OrganizationChoice {
   readonly organizationId: string;
   readonly name: string;
   readonly code: string;
+  /** What THIS organization calls the caller (052). Per-tenant, like the roles. */
+  readonly email: string;
+  readonly displayName: string;
   readonly roles: readonly string[];
   /**
    * Permission codes held in THIS organization (I79).
@@ -170,10 +182,45 @@ export function chooseOrganization(
   return first;
 }
 
+/**
+ * The caller as the organization they are working in knows them.
+ *
+ * 🔴 A BLANK NAME IS AN ABSENT NAME. The previous version required all three
+ * fields to be `!== undefined`, which an empty string satisfies — so an API
+ * returning `""` produced "signed in as ''" in the top bar, under a comment
+ * claiming that exact case was excluded. Codex found the gap between the
+ * comment and the check. Nothing here trims a name into existence: if either
+ * attribute is blank there is no profile, and `UserMenu` renders nothing rather
+ * than an initialled circle with no initials.
+ *
+ * Exported and pure so the rule can be tested without a network call or a
+ * React tree — the same reason `chooseOrganization` is.
+ */
+export function activeProfile(
+  session: SessionState,
+  organizations: readonly OrganizationChoice[],
+): UserProfile | null {
+  // Anonymous has no active membership, so it has no name. That is the whole
+  // of the "signOut must clear the profile" fix: there is no profile to clear.
+  if (session.status !== "authenticated") return null;
+
+  const active = organizations.find(
+    (org) => org.organizationId === session.credentials.organizationId,
+  );
+  if (active === undefined) return null;
+
+  if (active.displayName.trim() === "" || active.email.trim() === "") return null;
+
+  return {
+    userId: session.credentials.userId,
+    email: active.email,
+    displayName: active.displayName,
+  };
+}
+
 export function AuthProvider({ children }: { children: React.ReactNode }) {
   const session = useSession();
   const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
-  const [profile, setProfile] = useState<UserProfile | null>(null);
   const tokens = useRef<LiveTokens | null>(null);
   const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
   // 🔴 clearTimeout CANNOT STOP A REFRESH THAT IS ALREADY IN FLIGHT.
@@ -251,12 +298,12 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
 
     const body = (await response.json()) as {
       user_id?: string;
-      email?: string;
-      display_name?: string;
       organizations?: {
         organization_id: string;
         name: string;
         code: string;
+        email?: string;
+        display_name?: string;
         roles?: string[];
         permissions?: string[];
       }[];
@@ -266,6 +313,11 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
       organizationId: org.organization_id,
       name: org.name,
       code: org.code,
+      // 🔴 THE MEMBERSHIP'S OWN PAIR (052). An API too old to send them yields
+      // an empty string, which `useProfile` reads as "no name" rather than
+      // rendering "signed in as ''" — see the profile derivation below.
+      email: org.email ?? "",
+      displayName: org.display_name ?? "",
       roles: org.roles ?? [],
       // `?? []` and not `?? ALL_NAV_PERMISSIONS`: an API too old to send
       // permissions must yield a shell that shows LESS, never one that shows
@@ -274,21 +326,6 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
       permissions: org.permissions ?? [],
     }));
 
-    // 🔴 ONLY WHEN ALL THREE ARE PRESENT. A half-populated profile would put an
-    // empty string where a name goes, and "signed in as ''" is worse than no
-    // name at all — it looks like a rendering bug rather than an absent field.
-    setProfile(
-      body.user_id !== undefined &&
-        body.email !== undefined &&
-        body.display_name !== undefined
-        ? {
-            userId: body.user_id,
-            email: body.email,
-            displayName: body.display_name,
-          }
-        : null,
-    );
-
     const first = choices[0];
     if (first === undefined) {
       // Absence must never present as success. An empty list would render
@@ -556,6 +593,11 @@ export function AuthProvider({ children }: { children: React.ReactNode }) {
     [organizations],
   );
 
+  const profile = useMemo(
+    () => activeProfile(session, organizations),
+    [session, organizations],
+  );
+
   const value = useMemo<AuthContextValue>(
     () => ({
       session,
apps/web\lib\permissions.ts:58: * @param organizations every tenant `/api/me` offered, each with its own
apps/web\lib\permissions.ts:65:  organizations: readonly OrganizationChoice[],
apps/web\lib\permissions.ts:78:  const active = organizations.find(
apps/web\lib\permissions.ts:136:  const { organizations } = useAuth();
apps/web\lib\permissions.ts:137:  return effectiveNavPermissions(session, organizations, ALL_NAV_PERMISSIONS);
apps/web\lib\permissions.test.ts:136:    // The fifth state Codex named: authenticated while `organizations` is
apps/web\app\admin\members.tsx:116:        <span className="text-sm font-medium text-slate-900">{member.display_name}</span>
apps/web\app\admin\members.tsx:535:                  display_name: displayName.trim(),
apps/web\lib\demo\dataset.ts:55:  readonly display_name: string;
apps/web\lib\demo\dataset.ts:97:export interface DemoMember {
apps/web\lib\demo\dataset.ts:215:  return USERS.find((u) => u.username === username)?.display_name ?? username;
apps/web\app\account\profile\page.tsx:9: * `display_name` and `email` are the ORGANIZATION's view of the person
apps/web\app\account\profile\page.tsx:35:  const { profile, organizations, session } = useAuth();
apps/web\app\account\profile\page.tsx:39:      ? organizations.find(
apps/web\app\account\profile\page.tsx:119:              {organizations.length > 1 && (
apps/web\app\account\profile\page.tsx:121:                  You belong to {organizations.length} organizations. Switch with
apps/web\lib\api\projects.ts:108:  // moved a tenant's `display_name` and `email` onto the membership and revoked
apps/web\lib\api\projects.ts:112:  display_name: z.string(),
apps/web\lib\api\hooks.ts:400: * `demo-data.json` carries organizations, users, stages, opportunities,
apps/web\lib\api\client.ts:158:    // to several organizations, so the active one is a request that the
apps/web\lib\api\admin.ts:46:  display_name: z.string(),
apps/web\lib\api\admin.ts:107:export interface MemberInviteRequest {
apps/web\lib\api\admin.ts:110:  readonly display_name: string;
apps/web\app\projects\workspace\page.tsx:1226:      <span className="font-medium text-slate-900">{member.display_name}</span>
apps/web\app\projects\workspace\page.tsx:1244:            aria-label={`Reason for removing ${member.display_name}`}
apps/api\tests\auth\test_export_and_classification_routes.py:137:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\test_export_and_classification_routes.py:145:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\tests\auth\test_document_upload_routes.py:336:        text("INSERT INTO core.organizations (code,name) VALUES (:c,'Other') RETURNING id"),
apps/api\tests\auth\test_document_upload_routes.py:341:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\test_document_upload_routes.py:374:            text("DELETE FROM core.organizations WHERE id = :o"), {"o": other_org}
apps/api\tests\auth\test_dashboard_routes.py:66:        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\test_dashboard_routes.py:71:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\test_dashboard_routes.py:79:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\test_dashboard_routes.py:127:    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": org_id})
apps/api\tests\auth\test_admin_member_routes.py:69:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\auth\test_admin_member_routes.py:76:                "INSERT INTO core.users (keycloak_sub, email, display_name)"
apps/api\tests\auth\test_admin_member_routes.py:84:                " (organization_id, user_id, email, display_name)"
apps/api\tests\auth\test_admin_member_routes.py:155:        owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org_id})
apps/api\tests\auth\test_admin_member_routes.py:180:        "display_name": "Newly Invited",
apps/api\tests\auth\test_admin_member_routes.py:203:    assert got["display_name"] == body["display_name"]
apps/api\tests\auth\test_admin_member_routes.py:211:            SELECT organization_id, email::text, display_name
apps/api\tests\auth\test_admin_member_routes.py:218:    assert (stored.email, stored.display_name) == (body["email"], body["display_name"])
apps/api\tests\auth\conftest.py:154:        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\conftest.py:159:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\conftest.py:167:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:233:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\conftest.py:241:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:251:        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\conftest.py:256:            "INSERT INTO core.users (keycloak_sub,email,display_name) "
apps/api\tests\auth\conftest.py:264:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:319:    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": org_id})
apps/api\tests\auth\conftest.py:320:    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": foreign_org_id})
apps/api\tests\auth\conftest.py:353:        text("INSERT INTO core.organizations (code, name) VALUES (:c,:n) RETURNING id"),
apps/api\tests\auth\conftest.py:359:            "INSERT INTO core.users (keycloak_sub, email, display_name) "
apps/api\tests\auth\conftest.py:368:            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
apps/api\tests\auth\conftest.py:426:        ("DELETE FROM core.organizations WHERE id=:o", {"o": org_id}),
apps/web\components\providers\auth-provider.tsx:64: * It used to be its own `useState`, set from a top-level `display_name` on
apps/web\components\providers\auth-provider.tsx:66: * the session and the organizations and never cleared this, so the previous
apps/web\components\providers\auth-provider.tsx:99:  readonly organizations: readonly OrganizationChoice[];
apps/web\components\providers\auth-provider.tsx:122:   * organizations -- no session at all -- is the different case, handled
apps/web\components\providers\auth-provider.tsx:180:    throw new Error("chooseOrganization called with no organizations");
apps/web\components\providers\auth-provider.tsx:201:  organizations: readonly OrganizationChoice[],
apps/web\components\providers\auth-provider.tsx:207:  const active = organizations.find(
apps/web\components\providers\auth-provider.tsx:223:  const [organizations, setOrganizations] = useState<readonly OrganizationChoice[]>([]);
apps/web\components\providers\auth-provider.tsx:301:      organizations?: {
apps/web\components\providers\auth-provider.tsx:306:        display_name?: string;
apps/web\components\providers\auth-provider.tsx:312:    const choices: OrganizationChoice[] = (body.organizations ?? []).map((org) => ({
apps/web\components\providers\auth-provider.tsx:320:      displayName: org.display_name ?? "",
apps/web\components\providers\auth-provider.tsx:581:      if (!organizations.some((org) => org.organizationId === organizationId)) return;
apps/web\components\providers\auth-provider.tsx:583:      // is memoised on `organizations` and would otherwise close over a
apps/web\components\providers\auth-provider.tsx:593:    [organizations],
apps/web\components\providers\auth-provider.tsx:597:    () => activeProfile(session, organizations),
apps/web\components\providers\auth-provider.tsx:598:    [session, organizations],
apps/web\components\providers\auth-provider.tsx:608:      organizations,
apps/web\components\providers\auth-provider.tsx:611:    [session, signIn, signOut, profile, organizations, selectOrganization],
apps/web\components\providers\auth-provider.test.ts:77:    expect(() => chooseOrganization([], undefined)).toThrow(/no organizations/);
apps/web\components\providers\auth-provider.test.ts:85: * organizations and never cleared the profile, so the previous user's name
apps/web\components\providers\auth-provider.test.ts:89: * top-level `display_name` that `/api/me` filled from whichever tenant sorted
apps/web\components\providers\auth-provider.test.ts:108:    // The finding, exactly. The organizations list survives a failed refresh
apps/web\components\nav\user-menu.tsx:7: * `GET /api/me` returns `display_name` and `email` beside `organizations`, and
apps/web\components\nav\user-menu.tsx:8: * the auth provider parsed only the organizations — so the top bar showed a
apps/web\components\nav\top-bar.tsx:11: * to several organizations, and switching must NAVIGATE rather than
apps/web\components\nav\top-bar.tsx:85:            always returned `display_name`; the auth provider parsed only the
apps/web\components\nav\top-bar.tsx:86:            organizations and threw it away, which is why this spot held a grey
apps/web\components\nav\app-sidebar.tsx:70:  const { organizations } = useAuth();
apps/web\components\nav\app-sidebar.tsx:73:    organizations,
apps/web\components\nav\account-menu.tsx:12: * It offers ONLY organizations the API itself returned. A free-text
apps/web\components\nav\account-menu.tsx:22:  const { session, configured, signIn, signOut, organizations, selectOrganization } = useAuth();
apps/web\components\nav\account-menu.tsx:72:        {organizations.map((org) => (
apps/api\app\domains\tasks\service.py:636:                   u.display_name AS assignee,
apps/api\tests\test_upload_pipeline_units.py:199:def test_a_traversal_filename_cannot_survive_as_a_display_name() -> None:
apps/api\tests\test_upload_pipeline_units.py:211:def test_a_nameless_file_still_gets_a_display_name() -> None:
apps/api\tests\test_msd_conductor.py:67:            display_name="Caller",
apps/api\tests\test_me_identity_shape.py:4:``display_name`` from ``core.users`` onto ``core.organization_members``, and
apps/api\tests\test_me_identity_shape.py:11:organization sorts first alphabetically. A member of two organizations working
apps/api\tests\test_me_identity_shape.py:54:def _rows_for_two_organizations() -> list[dict[str, Any]]:
apps/api\tests\test_me_identity_shape.py:55:    """One person, two organizations, two different names — the only shape that
apps/api\tests\test_me_identity_shape.py:67:            "display_name": "Known In Acme",
apps/api\tests\test_me_identity_shape.py:77:            "display_name": "Different Name Entirely",
apps/api\tests\test_me_identity_shape.py:85:def two_organizations(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
apps/api\tests\test_me_identity_shape.py:86:    rows = _rows_for_two_organizations()
apps/api\tests\test_me_identity_shape.py:105:    tenant_attributes = fields & {"email", "display_name"}
apps/api\tests\test_me_identity_shape.py:112:    assert fields == {"user_id", "organizations"}, (
apps/api\tests\test_me_identity_shape.py:117:    assert {"email", "display_name"} <= membership, (
apps/api\tests\test_me_identity_shape.py:123:async def test_each_membership_reports_its_own_organizations_view(
apps/api\tests\test_me_identity_shape.py:124:    two_organizations: list[dict[str, Any]],
apps/api\tests\test_me_identity_shape.py:134:    by_code = {org.code: org for org in response.organizations}
apps/api\tests\test_me_identity_shape.py:137:    assert (by_code["ACME"].email, by_code["ACME"].display_name) == (
apps/api\tests\test_me_identity_shape.py:141:    assert (by_code["ZEN"].email, by_code["ZEN"].display_name) == (
apps/api\tests\test_me_identity_shape.py:152:    assert response.user_id == two_organizations[0]["user_id"]
apps/api\tests\test_me_identity_shape.py:153:    assert len({org.organization_id for org in response.organizations}) == 2
apps/api\tests\test_conductor_boundary.py:85:            display_name="Caller",
apps/api\tests\test_conductor_boundary.py:1153:        display_name="d",
apps/api\tests\test_conductor_boundary.py:1472:            display_name="Caller",
apps/api\app\core\tenancy.py:4:belongs to organizations through `core.organization_members`, and may
apps/api\app\core\security.py:85:    display_name: str
apps/api\app\core\security.py:200:    SELECT user_id, email, display_name, organization_id, roles, permissions
apps/api\app\core\security.py:341:        display_name=row["display_name"],
apps/api\app\core\file_types.py:120:    """Return `(canonical_content_type, safe_display_name)` or raise.
apps/api\app\core\db.py:224:    organizations the caller's own subject may act in. Both take the subject
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:25:`core.users.email` and `core.users.display_name` stop being readable by the
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:141:    display_name    TEXT,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:153:           u.display_name,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:170:    GROUP BY u.id, u.email, u.display_name, om.organization_id
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:179:    display_name      TEXT,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:193:           u.display_name,
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:205:    JOIN core.organizations o
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:214:    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:280:        "        (organization_id, user_id, email, display_name)\n"
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:281:        "    VALUES (v_org, v_user, p_email::public.citext, p_display_name)",
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:287:    # The first version asked whether `"email, display_name"` still appeared
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:300:        "(organization_id, user_id, email, display_name)" in restored
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:356:            "GRANT SELECT (email, display_name) ON core.users"
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:360:    op.execute(text("GRANT UPDATE (email, display_name) ON core.users TO evercoat_app"))
apps/api\migrations_alembic\versions\2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py:365:        text("ALTER TABLE core.organization_members DROP COLUMN email, DROP COLUMN display_name")
apps/api\migrations_alembic\versions\2026_08_26_0050-i1000_bind_proves_the_caller_administers.py:67:                p_subject TEXT, p_email TEXT, p_display_name TEXT
apps/api\migrations_alembic\versions\2026_08_26_0050-i1000_bind_proves_the_caller_administers.py:85:                    INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\migrations_alembic\versions\2026_08_26_0050-i1000_bind_proves_the_caller_administers.py:86:                    VALUES (p_subject, p_email::public.citext, p_display_name)
apps/api\migrations_alembic\versions\2026_08_25_0047-f2000_an_authentication_identifier_is_not_readable.py:11:before acting: `display_name` has eleven readers, `email` has two production
apps/api\migrations_alembic\versions\2026_08_25_0047-f2000_an_authentication_identifier_is_not_readable.py:62:            "REVOKE SELECT (id, email, display_name, status, created_at, updated_at)"
apps/api\migrations_alembic\versions\2026_08_25_0047-f2000_an_authentication_identifier_is_not_readable.py:66:    op.execute(text("REVOKE UPDATE (email, display_name) ON core.users FROM evercoat_app"))
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:9:`GET /api/me` returned `organizations[].roles` and no permissions, so
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:68:                display_name      TEXT,
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:81:                       u.display_name,
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:91:                JOIN core.organizations o
apps/api\migrations_alembic\versions\2026_08_25_0045-e9000_membership_carries_permissions.py:98:                GROUP BY u.id, u.email, u.display_name, om.organization_id,
apps/api\migrations_alembic\versions\2026_08_23_0044-e8000_user_directory_is_not_global.py:15:UPDATE SET display_name` was run as `evercoat_app` under organization A's GUC
apps/api\migrations_alembic\versions\2026_08_22_0032-d5000_the_database_fails_closed.py:13:organizations, 137 projects**. The entire database, every tenant. The only
apps/api\migrations_alembic\versions\2026_08_22_0032-d5000_the_database_fails_closed.py:23:what tells a signed-in browser which organizations exist for it. Forcing RLS
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:8:`FOR org IN SELECT id FROM core.organizations LOOP`. There is no trigger and
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:18:AFTER INSERT trigger on `core.organizations`, and a backfill for the
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:19:organizations 020 left behind. The migration verifies its own backfill and
apps/api\migrations_alembic\versions\2026_08_21_0030-d3000_every_organization_gets_the_approval_engine.py:57:    op.execute("DROP TRIGGER IF EXISTS organizations_get_approval_templates ON core.organizations")
apps/api\app\domains\projects\members.py:241:                   u.display_name, u.email::text AS email,
apps/api\app\domains\projects\members.py:260:                u.display_name
apps/api\app\domains\projects\dashboard.py:55:                   lead.display_name     AS lead_name,
apps/api\app\domains\projects\dashboard.py:56:                   director.display_name AS director_name,
apps/api\app\domains\projects\dashboard.py:64:            -- Names come from the MEMBERSHIP (052): `core.users.display_name`
apps/api\app\domains\projects\dashboard.py:173:                   t.required_action, u.display_name AS assignee
apps/api\app\domains\projects\dashboard.py:250:            SELECT t.transitioned_at AS at, t.reason, u.display_name AS actor,
apps/api\app\domains\pipeline\service.py:344:                   u.display_name AS actor,
apps/api\app\domains\opportunities\service.py:554:                   u.display_name AS created_by_name,
apps/api\app\domains\opportunities\service.py:594:            SELECT o.*, u.display_name AS created_by_name,
apps/api\app\domains\opportunities\service.py:595:                   d.display_name AS decided_by_name,
apps/api\tests\db\test_slice2_tasks.py:39:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_tasks.py:48:                INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_tasks.py:61:                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
apps/api\tests\db\test_slice2_tasks.py:391:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\app\api\me.py:70:    #: each row carries its own ``om.email`` / ``om.display_name`` -- the
apps/api\app\api\me.py:75:    #: two organizations saw the alphabetically-first one's name in the top bar
apps/api\app\api\me.py:81:    display_name: str
apps/api\app\api\me.py:118:    everything else onto the membership. A top-level ``display_name`` is a
apps/api\app\api\me.py:128:    organizations: list[OrganizationMembership] = Field(default_factory=list)
apps/api\app\api\me.py:133:# definition of "which organizations may this subject act in" and no
apps/api\app\api\me.py:191:        organizations=[
apps/api\app\api\me.py:197:                display_name=row["display_name"],
apps/api\tests\integration\test_auth_end_to_end.py:276:def test_a_signed_in_user_can_discover_their_organizations() -> None:
apps/api\tests\integration\test_auth_end_to_end.py:291:    assert body["organizations"], (
apps/api\tests\integration\test_auth_end_to_end.py:292:        "a valid token resolved to a user with NO organizations. A browser "
apps/api\tests\integration\test_auth_end_to_end.py:297:    org = body["organizations"][0]
apps/api\tests\integration\test_auth_end_to_end.py:304:    # known by different addresses in different organizations.
apps/api\tests\integration\test_auth_end_to_end.py:306:    assert org["display_name"], "a membership with no name renders as a blank top bar"
apps/api\tests\integration\test_auth_end_to_end.py:353:    organization_id = me.json()["organizations"][0]["organization_id"]
apps/api\tests\db\test_slice2_stage_gates.py:40:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_stage_gates.py:233:def test_reorder_cannot_reach_another_organizations_stages(owner_session, gate_world):
apps/api\tests\db\test_slice2_stage_gates.py:241:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_review_fixes.py:52:    """Two organizations, each with one active member, plus a project."""
apps/api\tests\db\test_slice2_review_fixes.py:58:            text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_review_fixes.py:64:                INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_review_fixes.py:77:                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
apps/api\tests\db\test_slice2_review_fixes.py:276:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_review_fixes.py:285:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\tests\db\test_slice2_review_fixes.py:330:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_review_fixes.py:339:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\tests\db\test_slice2_opportunities.py:39:        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
apps/api\tests\db\test_slice2_opportunities.py:46:            INSERT INTO core.users (keycloak_sub, email, display_name)
apps/api\tests\db\test_slice2_opportunities.py:55:            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
apps/api\app\api\admin.py:53:    display_name: str
apps/api\app\api\admin.py:67:    display_name: str = Field(min_length=1, max_length=200)
apps/api\app\api\admin.py:173:                   om.display_name, om.status,

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content apps/api/migrations_alembic/versions/2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py | Select-Object -Skip 120 -First 110; Get-Content apps/web/components/providers/auth-provider.tsx | Select-Object -Skip 540 -First 85; Get-Content apps/web/components/nav/user-menu.tsx | Select-Object -First 180' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 1723ms:
         WHERE mine.user_id = NEW.id
           AND mine.status = 'active'
           AND mine.organization_id = core.current_org_id()
           AND u.email = NEW.email
    ) THEN
        RAISE EXCEPTION
            'address already belongs to an active member of this organization'
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'users_address_stays_unique_in_organization';
    END IF;

    RETURN NEW;
END $fn$;
"""

_RESTORE_PRINCIPAL = """
CREATE OR REPLACE FUNCTION core.principal_for_subject(p_sub TEXT, p_org UUID)
RETURNS TABLE (
    user_id         UUID,
    email           TEXT,
    display_name    TEXT,
    organization_id UUID,
    roles           TEXT[],
    permissions     TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    SELECT u.id,
           u.email::TEXT,
           u.display_name,
           om.organization_id,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
      AND om.organization_id = p_org
    GROUP BY u.id, u.email, u.display_name, om.organization_id
$$;
"""

_RESTORE_MEMBERSHIPS = """
CREATE OR REPLACE FUNCTION core.memberships_for_subject(p_sub TEXT)
RETURNS TABLE (
    user_id           UUID,
    email             TEXT,
    display_name      TEXT,
    organization_id   UUID,
    organization_name TEXT,
    organization_code TEXT,
    roles             TEXT[],
    permissions       TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    SELECT u.id,
           u.email::TEXT,
           u.display_name,
           om.organization_id,
           o.name,
           o.code,
           COALESCE(array_agg(DISTINCT r.code ORDER BY r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code ORDER BY p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    JOIN core.organizations o
      ON o.id = om.organization_id
     AND o.status = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
    ORDER BY o.name
$$;
"""


def downgrade() -> None:
    bind = op.get_bind()

    # ðŸ”´ REFUSE RATHER THAN INSTALL A GUARD THE DATA ALREADY VIOLATES.
    #
    # 052 stops policing `core.users.email`, so two members of ONE
    # organization may since have acquired the same GLOBAL address while
    # holding different membership addresses. Restoring 046's triggers over
    # that data leaves a rule that is false the moment anyone touches those
    # rows â€” a guard installed against a population that violates it.
    # Same shape as 046's own downgrade, which refuses rather than deleting.
      }),
    );
  }, []);

  const signOut = useCallback(() => {
    // Local state first. If the redirect below fails for any reason, the
    // browser must not be left holding a live token while believing it
    // has signed out.
    if (refreshTimer.current !== null) clearTimeout(refreshTimer.current);
    tokens.current = null;
    setOrganizations([]);
    setSession({ status: "anonymous", reason: "you have signed out" });

    // ðŸ”´ GATED ON CONFIGURATION ONLY.
    //
    // It used to also require `refreshToken !== null` -- a condition with
    // nothing to do with logging out, since the request below sends only
    // `client_id` and `post_logout_redirect_uri`. If Keycloak's response
    // had omitted a refresh token, Sign out cleared local state and left
    // the realm's SSO cookie alive, so the next Sign in silently returned
    // the previous user. On the shared machine the comment below names,
    // that is the wrong person. The Supervisor found it.
    if (!isAuthConfigured) return;
    // Ends the session at Keycloak too. Without this the SSO cookie
    // survives and the next "Sign in" silently returns the same user â€”
    // which on a shared machine is the wrong person.
    const params = new URLSearchParams({
      client_id: KEYCLOAK_CLIENT_ID,
      post_logout_redirect_uri: window.location.origin,
    });
    window.location.assign(`${endpoints().endSession}?${params.toString()}`);
  }, []);

  const selectOrganization = useCallback(
    (organizationId: string) => {
      const token = tokens.current?.accessToken;
      if (token === undefined) return;
      // Only an organization the API itself listed. A tenant id typed in
      // from anywhere else would be refused server-side anyway, but
      // offering it at all would imply it was a choice.
      if (!organizations.some((org) => org.organizationId === organizationId)) return;
      // Read the store, not the render-time `session` prop: this callback
      // is memoised on `organizations` and would otherwise close over a
      // stale session.
      const active = readSession();
      const userId = active.status === "authenticated" ? active.credentials.userId : "";
      if (userId === "") return;
      setSession({
        status: "authenticated",
        credentials: { token, organizationId, userId },
      });
    },
    [organizations],
  );

  const profile = useMemo(
    () => activeProfile(session, organizations),
    [session, organizations],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      configured: isAuthConfigured,
      signIn,
      signOut,
      profile,
      organizations,
      selectOrganization,
    }),
    [session, signIn, signOut, profile, organizations, selectOrganization],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    // A hook that silently returned a signed-out value outside its
    // provider would make a missing <AuthProvider> look like a user who
    // had not signed in â€” indistinguishable, and wrong.
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return context;
"use client";

/**
 * The signed-in person's name, and what they can do about themselves.
 *
 * ðŸ”´ THE APPLICATION HAS ALWAYS KNOWN THIS NAME AND HAD NOWHERE TO PUT IT.
 * `GET /api/me` returns `display_name` and `email` beside `organizations`, and
 * the auth provider parsed only the organizations â€” so the top bar showed a
 * grey circle containing a dash while the browser held "Esi Lead" in memory.
 *
 * Navigation narrative Â§2 puts the user profile at the end of the global bar:
 * *Organization Selector | Global Search | Quick Create | MSD | Notifications |
 * Help | User Profile*. This sits between Alerts and Help, which is where the
 * person asking for it wanted it and is a difference of one position from Â§2.
 *
 * âš ï¸ SIGNED OUT, IT OFFERS NOTHING AND SAYS NOTHING. `AccountMenu` at the other
 * end of the bar already owns "you are not signed in" and the Sign in control;
 * a second, quieter version of that message here would be two components
 * disagreeing about how to say the same thing.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/providers/auth-provider";

/** The three things a person can do about their own account. */
const ITEMS = [
  { href: "/account/profile", label: "Profile", hint: "Who you are here, and what you may do" },
  { href: "/account/settings", label: "Settings", hint: "Theme, and where the application opens" },
  { href: "/account/security", label: "Security", hint: "Your session, password and sign-out" },
] as const;

export function UserMenu() {
  const { profile } = useAuth();
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstItem = useRef<HTMLAnchorElement>(null);

  // ðŸ”´ CLOSES ON OUTSIDE CLICK **AND** ON ESCAPE. A menu that only closes by
  // clicking its own trigger is a keyboard trap: tab into it, and the only way
  // out is the mouse. Escape is the expected key and costs one listener.
  useEffect(() => {
    if (!open) return;

    const onPointer = (event: MouseEvent) => {
      if (container.current !== null && !container.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      // ðŸ”´ AND FOCUS GOES BACK TO THE TRIGGER. Escape used to close the menu
      // and leave focus on an element that had just been removed from the
      // document, which browsers resolve by sending it to `<body>` â€” so a
      // keyboard user was returned to the top of the page and had to tab all
      // the way back to where they were. Codex found it.
      trigger.current?.focus();
    };

    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // ðŸ”´ OPENING A MENU MOVES FOCUS INTO IT. Without this the menu appeared and
  // focus stayed on the trigger, so a screen reader announced a menu the user
  // then had to hunt for, and the next Tab left it entirely. This is the other
  // half of the Escape behaviour above: focus enters on open and returns on
  // close, which is what `aria-haspopup="menu"` promises.
  useEffect(() => {
    if (open) firstItem.current?.focus();
  }, [open]);

  if (profile === null) {
    return null;
  }

  return (
    <div ref={container} className="relative">
      <button
        ref={trigger}
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((was) => !was)}
        className="flex items-center gap-2 rounded px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-slate-900"
      >
        <span
          aria-hidden
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-200 text-[10px] font-semibold text-slate-700"
        >
          {/* Initials, and only as decoration â€” the name itself is beside it,
              so this never has to be the thing a reader relies on. */}
          {profile.displayName
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part.charAt(0).toUpperCase())
            .join("")}
        </span>
        <span className="max-w-[10rem] truncate">{profile.displayName}</span>
        <span aria-hidden className="text-[10px] text-slate-500">
          {open ? "â–²" : "â–¼"}
        </span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Your account"
          className="absolute right-0 z-50 mt-1 w-72 rounded border border-slate-200 bg-white p-1 shadow-lg"
        >
          <div className="border-b border-slate-200 px-3 py-2">
            <p className="truncate text-sm font-medium text-slate-900">{profile.displayName}</p>
            {/* The address this ORGANIZATION knows them by. Migration 052 moved
                it onto the membership, so it is not a global identity. */}
            <p className="truncate text-xs text-slate-600">{profile.email}</p>
          </div>

          {ITEMS.map((item, index) => (
            <Link
              key={item.href}
              ref={index === 0 ? firstItem : undefined}
              href={item.href}
              role="menuitem"
              onClick={() => setOpen(false)}
              className="block rounded px-3 py-2 hover:bg-slate-50"
            >
              <span className="block text-sm font-medium text-slate-900">{item.label}</span>
              {/* A line of what it does, not a restatement of the label. Three
                  bare words in a menu make a reader open all three to find out
                  which one they wanted. */}
              <span className="block text-xs text-slate-600">{item.hint}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "CREATE OR REPLACE FUNCTION core.(principal|memberships)|SELECT u.id|om.email|GROUP BY" apps/api/migrations_alembic/versions/2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 574ms:
137:CREATE OR REPLACE FUNCTION core.principal_for_subject(p_sub TEXT, p_org UUID)
151:    SELECT u.id,
170:    GROUP BY u.id, u.email, u.display_name, om.organization_id
175:CREATE OR REPLACE FUNCTION core.memberships_for_subject(p_sub TEXT)
191:    SELECT u.id,
214:    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
239:                 GROUP BY 1, 2

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'Get-Content apps/api/migrations_alembic/versions/2026_08_26_0052-k1000_identity_has_no_tenant_attributes.py | Select-Object -First 125' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 523ms:
"""an identity has no tenant attributes; a membership does

Revision ID: k1000
Revises: j1000
Created: 2026-08-26

Closes I106 â€” the channel 051 named in its own header and left open â€” and
I108, found while measuring it.

ðŸ”´ THE MEMBERSHIP COLUMNS ARE NOT THE CLOSURE. The revoke is.

I106 is a rolled-back bind reading a foreign identity's stored email and
display name through the membership it just created. The obvious fix is
tenant-scoped attributes on `core.organization_members`, and this migration
adds them â€” but measuring the defect turned up I108: `evercoat_app` holds
table-level INSERT on that table, `org_member_isolation` constrains only
`organization_id`, and `user_id` is a plain FK to a global table. So an
ORDINARY member â€” no `admin.users`, no EXECUTE on the bind, no
`keycloak_sub` â€” can manufacture a membership naming any identity in the
system, read it, and roll back. Measured.

That reframes it. The defect is not "the bind leaks"; it is **a membership
row turns a global identity into a readable one**, and the bind is one of
two ways to make one. What actually closes both is that
`core.users.email` and `core.users.display_name` stop being readable by the
runtime roles at all. The membership columns are what keeps the application
working once they are gone.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "k1000"
down_revision: str | None = "j1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("052_an_identity_has_no_tenant_attributes.sql")


# ---------------------------------------------------------------------------
# The downgrade
# ---------------------------------------------------------------------------
# `j1000` describes a schema in which I106 and I108 were both open, so this
# reopens them. A downgrade that quietly kept the fix would make that
# description false â€” the same argument 049, 050 and 051 each make.

_RESTORE_DUPLICATE_GUARD = """
CREATE OR REPLACE FUNCTION core.deny_duplicate_address_in_organization()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
AS $fn$
DECLARE
    v_email public.citext;
BEGIN
    SELECT u.email INTO v_email
      FROM core.users u
     WHERE u.id = NEW.user_id;

    IF v_email IS NULL THEN
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtext(NEW.organization_id::TEXT),
        hashtext(v_email::TEXT)
    );

    IF EXISTS (
        SELECT 1
          FROM core.organization_members om
          JOIN core.users u ON u.id = om.user_id
         WHERE om.organization_id = NEW.organization_id
           AND om.id <> NEW.id
           AND om.status = 'active'
           AND u.email = v_email
    ) THEN
        RAISE EXCEPTION
            'address already belongs to an active member of this organization'
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'organization_members_one_address_per_organization';
    END IF;

    RETURN NEW;
END $fn$;
"""

_RESTORE_RENAME_GUARD = """
CREATE OR REPLACE FUNCTION core.deny_address_collision_on_rename()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
AS $fn$
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtext(COALESCE(core.current_org_id()::TEXT, '<none>')),
        hashtext(NEW.email::TEXT)
    );

    IF core.current_org_id() IS NULL THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM core.organization_members mine
          JOIN core.organization_members other
            ON other.organization_id = mine.organization_id
           AND other.user_id <> NEW.id
           AND other.status = 'active'
          JOIN core.users u ON u.id = other.user_id
         WHERE mine.user_id = NEW.id
           AND mine.status = 'active'
           AND mine.organization_id = core.current_org_id()
           AND u.email = NEW.email
    ) THEN

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "memberships_for_subject|principal_for_subject|om.email|om.display_name" apps/api/migrations/052_an_identity_has_no_tenant_attributes.sql; Get-Content apps/api/migrations/052_an_identity_has_no_tenant_attributes.sql | Select-Object -Skip 80 -First 160' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 806ms:
86:-- accepted. `core.memberships_for_subject(TEXT)` and
87:-- `core.principal_for_subject(TEXT, UUID)` are SECURITY DEFINER, take a
95:--     core.memberships_for_subject(<B's sub>) : org='...B'  code='...'
320:CREATE OR REPLACE FUNCTION core.principal_for_subject(p_sub TEXT, p_org UUID)
334:    -- 🔴 `om.email`, NOT `u.email` (052). This function is scoped to ONE
339:           om.email::TEXT,
340:           om.display_name,
357:    GROUP BY u.id, om.email, om.display_name, om.organization_id
360:ALTER FUNCTION core.principal_for_subject(TEXT, UUID) OWNER TO evercoat_owner;
361:GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO evercoat_app;
363:COMMENT ON FUNCTION core.principal_for_subject(TEXT, UUID) IS
371:CREATE OR REPLACE FUNCTION core.memberships_for_subject(p_sub TEXT)
387:    -- 🔴 `om.email` / `om.display_name` (052). This function returns ONE
392:           om.email::TEXT,
393:           om.display_name,
421:    GROUP BY u.id, om.email, om.display_name, om.organization_id, o.name, o.code
425:ALTER FUNCTION core.memberships_for_subject(TEXT) OWNER TO evercoat_owner;
426:REVOKE ALL ON FUNCTION core.memberships_for_subject(TEXT) FROM PUBLIC;
427:GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_app;
429:COMMENT ON FUNCTION core.memberships_for_subject(TEXT) IS
-- ---------------------------------------------------------------------
-- ðŸ”´ WHAT THIS DOES *NOT* CLOSE, MEASURED AND FILED AS I109
-- ---------------------------------------------------------------------
--
-- Raised by Codex reviewing this migration, and measured before it was
-- accepted. `core.memberships_for_subject(TEXT)` and
-- `core.principal_for_subject(TEXT, UUID)` are SECURITY DEFINER, take a
-- subject as an ARGUMENT, and are granted EXECUTE to `evercoat_app`.
-- Neither can bind that argument to its caller, because both exist to
-- answer BEFORE a session has an organization -- there is nothing yet to
-- compare against. As an ordinary member of organization A, holding
-- nothing:
--
--     direct read of B's memberships          : 0 rows
--     core.memberships_for_subject(<B's sub>) : org='...B'  code='...'
--                                               email='secret.person@competitor.example'
--                                               name='Confidential B Person'
--
-- âš ï¸ AND IT DISCLOSES MORE THAN THE ADDRESS: the NAME and CODE of every
-- organization that subject belongs to, which is a larger fact than the
-- email this migration is about.
--
-- **This migration did not introduce it** -- those functions date from
-- 024, 033 and 045, and before today they read `core.users` directly. But
-- the claim above must not be read as wider than it is: the revoke closes
-- the TABLE, not every path to the value. The bound is 047's: no runtime
-- role can read `keycloak_sub`, so an `evercoat_app` session cannot
-- enumerate subjects from the database and must already know an opaque
-- Keycloak uuid. **A bound is not a closure.** The fix is a separate
-- database role holding EXECUTE on those two functions and used only by
-- the authentication path -- a change to `app/core/db.py` with its own
-- measurement. Filed as I109, and
-- `test_the_sign_in_definers_still_answer_for_any_subject` pins it OPEN so
-- it cannot be quietly forgotten.
--
-- âš ï¸ WHY THE COLUMNS ARE NOT DROPPED. `keycloak_sub` was revoked rather
-- than dropped by 047 for the same reason: the sign-in definers need the
-- mirror, and an identity with no membership anywhere still has to have
-- come from somewhere. Dropping them would also make the bind unable to
-- record what it was given when it creates a NEW identity, which is the
-- only honest source for a first membership's attributes.
--
-- ---------------------------------------------------------------------
-- 046's TWO TRIGGER GUARDS ARE REPLACED BY A REAL UNIQUE INDEX
-- ---------------------------------------------------------------------
--
-- 046 could not use an index. The rule is "one active member per address
-- per organization", the address lived on the GLOBAL `core.users`, and no
-- index spans two tables -- so it was a pair of trigger functions holding
-- `pg_advisory_xact_lock` to stop two concurrent writers forking the
-- invariant, plus a second trigger on `core.users` because the address
-- could be changed in place without any membership row moving.
--
-- With the address ON the membership row, `(organization_id, email) WHERE
-- status = 'active'` is a single partial unique index. It covers INSERT,
-- UPDATE of the address, and a reactivation, in one mechanism, with no
-- advisory lock and no window in which two writers both pass.
--
-- ðŸ”´ AND IT IS NOT I83's ORACLE COMING BACK. That is the question this
-- change has to answer, because 046 exists precisely because a unique
-- index is enforced OUTSIDE row-level security. The difference is the
-- KEY: `users_email_key` was `(email)` platform-wide, so its refusal
-- answered "does this address exist ANYWHERE". This key leads with
-- `organization_id`, so a refusal can only ever concern a row in the
-- organization the writer named -- and after this migration the only
-- writer is the definer, which takes the organization from
-- `core.current_org_id()` after proving the caller administers it. Every
-- refusal therefore describes a member `list_members` already shows that
-- caller. That is exactly 046's own stated criterion for where a
-- uniqueness rule may be enforced.
--
-- âš ï¸ The index is NAMED `organization_members_one_address_per_organization`,
-- the same name 046's trigger used, because `app/api/admin.py` classifies
-- the 409 by constraint name and a rename would silently turn that into
-- "the membership could not be created" (500). Verified below.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The membership carries the organization's own view of the person.
-- ---------------------------------------------------------------------
ALTER TABLE core.organization_members
    ADD COLUMN email        public.citext,
    ADD COLUMN display_name TEXT;

-- Backfill from the global row, which is what every existing membership
-- was displaying anyway. Measured before writing this: 153 memberships,
-- 0 with a NULL email or display name, so NOT NULL below cannot fail on
-- the live population -- and if it ever does, it fails loudly rather than
-- leaving a nullable column nobody notices.
UPDATE core.organization_members om
   SET email        = u.email,
       display_name = u.display_name
  FROM core.users u
 WHERE u.id = om.user_id;

ALTER TABLE core.organization_members
    ALTER COLUMN email        SET NOT NULL,
    ALTER COLUMN display_name SET NOT NULL;

COMMENT ON COLUMN core.organization_members.email IS
    'The address THIS organization knows this member by, submitted by the '
    'administrator who bound them (migration 052, I106). Deliberately not '
    'read from core.users: for an identity that already existed in another '
    'tenant that row holds the OTHER tenant''s address, and a rolled-back '
    'bind made it readable for free.';

COMMENT ON COLUMN core.organization_members.display_name IS
    'The name THIS organization knows this member by (migration 052, I106). '
    'See core.organization_members.email.';

-- ---------------------------------------------------------------------
-- 2. One active member per address per organization -- as an INDEX now.
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS organization_members_one_address_per_organization
    ON core.organization_members;
DROP TRIGGER IF EXISTS users_address_stays_unique_in_organization
    ON core.users;
DROP FUNCTION IF EXISTS core.deny_duplicate_address_in_organization();
DROP FUNCTION IF EXISTS core.deny_address_collision_on_rename();

CREATE UNIQUE INDEX organization_members_one_address_per_organization
    ON core.organization_members (organization_id, email)
    WHERE status = 'active';

COMMENT ON INDEX core.organization_members_one_address_per_organization IS
    'One ACTIVE member per address, per organization (I83, restated by '
    'migration 052). Replaces the two trigger functions 046 needed while '
    'the address lived on the global core.users table. Leading with '
    'organization_id is what keeps it from being users_email_key again: a '
    'refusal can only describe a member of the organization the writer '
    'named, which list_members already shows them.';

-- ---------------------------------------------------------------------
-- 3. The bind records what it was GIVEN, on the membership.
-- ---------------------------------------------------------------------
DROP FUNCTION IF EXISTS core.bind_subject_to_organization(TEXT, TEXT, TEXT);

CREATE FUNCTION core.bind_subject_to_organization(
    p_subject      TEXT,
    p_email        TEXT,
    p_display_name TEXT
)
    -- Still only `member_id`, for 051's reason: any value that repeats
    -- across two rolled-back attempts answers "does this subject already
    -- exist somewhere on this platform".
    RETURNS TABLE (member_id UUID)
    LANGUAGE plpgsql
    VOLATILE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $fn$
DECLARE
    v_org     UUID := core.current_org_id();
    v_actor   UUID := core.current_user_id();
    v_perms   TEXT[];
    v_user    UUID;
    v_member  UUID;
BEGIN

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "Content-Security-Policy|script-src|nonce|unsafe-inline" . -g "!*node_modules*" -g "!*out*"; git diff 722df3d''^ 722df3d -- apps/web/lib/theme.ts | Select-String -Pattern '"'"'^'"\\+export const|"'^'"\\+  (white|slate|status|accents)|"'^'"\\+function|"'^'"\\+export function'" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 4304ms:
.\apps\web\lib\auth\pkce.ts:46:  // 🔴 THERE IS DELIBERATELY NO `nonce`.
.\apps\web\lib\auth\pkce.ts:50:  // id_token. A nonce binds an ID TOKEN to a request; with no ID token it
.\apps\web\lib\auth\pkce.ts:56:  // If an ID token is ever consumed here, reinstate the nonce AND
.\apps\web\lib\auth\pkce.test.ts:129:  it("does NOT send a nonce", () => {
.\apps\web\lib\auth\pkce.test.ts:130:    // 🔴 One was sent and never verified. A nonce binds an ID TOKEN to a
.\apps\web\lib\auth\pkce.test.ts:135:    expect(url().searchParams.get("nonce")).toBeNull();
.\apps\api\app\main.py:82:    by requesting ``/whatever/<nonce>`` -- growing API and Prometheus
.\apps\web\package-lock.json:6140:    "node_modules/get-nonce": {
.\apps\web\package-lock.json:6142:      "resolved": "https://registry.npmjs.org/get-nonce/-/get-nonce-1.0.1.tgz",
.\apps\web\package-lock.json:8233:        "get-nonce": "^1.0.0",
.\apps\api\tests\test_metrics_label_cardinality.py:17:    requesting `/whatever/<nonce>`, growing the API process and the
.\apps\api\tests\test_metrics_label_cardinality.py:69:    nonces = [uuid.uuid4().hex for _ in range(20)]
.\apps\api\tests\test_metrics_label_cardinality.py:72:    for nonce in nonces:
.\apps\api\tests\test_metrics_label_cardinality.py:73:        response = client.get(f"/no-such-route/{nonce}")
.\apps\api\tests\test_metrics_label_cardinality.py:75:            f"/no-such-route/{nonce} was routed to something; pick a path that 404s"
.\apps\api\tests\test_metrics_label_cardinality.py:80:    leaked = {label for label in after if any(nonce in label for nonce in nonces)}
.\apps\api\tests\test_metrics_label_cardinality.py:93:    # asserting only "no nonce leaked" would also pass if the middleware
.\apps\api\tests\test_conductor_boundary.py:1183:    """The nonce is consumed, so it cannot be captured and reused.
.\apps\api\app\agents\principal.py:135:# A nonce that is CONSUMED on use closes 1, 2 and 4: each mint is unique and
.\CHANGELOG.md:201:| `dataclasses.replace(real, permissions=forged)` — replayed the guard out of a legitimate principal | **closed** — the guard is a nonce, minted per construction and consumed on use |
.\RESUME_HERE.md:385:code**; three are closed (exact type check; the guard is a nonce consumed on
.\reviews\codex-api-security-2026-08-20.md:4018:SECURITY.md-143-- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy without `unsafe-inline` scripts.
.\reviews\codex-api-security-2026-08-20.md:5942:The middleware reads `request.scope["route"]` before `call_next()` performs routing. Consequently, it normally falls back to `request.url.path`. An unauthenticated attacker can request arbitrary unique paths such as `/random/<nonce>`, creating a new Prometheus time series for every value.
.\reviews\codex-api-security-2026-08-20.md:6037:The middleware reads `request.scope["route"]` before `call_next()` performs routing. Consequently, it normally falls back to `request.url.path`. An unauthenticated attacker can request arbitrary unique paths such as `/random/<nonce>`, creating a new Prometheus time series for every value.
.\SECURITY.md:234:- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy without `unsafe-inline` scripts.
.\SECURITY.md:287:| **A2** | 🔴 High | **Unbounded Prometheus label cardinality, anonymously reachable.** The access-log middleware read `request.scope["route"]` *before* `call_next`, and Starlette's router is what writes that key — so the `request.url.path` fallback fired on **every** request. `/api/projects/<uuid>` minted one time series per project, and an anonymous caller could mint unlimited series with `/whatever/<nonce>`. The line's own comment claimed it did the opposite. | `_metric_label()`, called after `call_next`; unrouted requests collapse into `<unmatched>`. Three tests, verified to fail against the prior mechanism. |

+export const ACCENT_NAMES = ["red", "amber", "emerald", "purple", "sky", "rose", "orange"] as const;
+export const ACCENT_STEPS = ["50", "200", "300", "400", "700", "800", "900"] as const;
+function reversed(name: AccentName): Accent {
+function mix(a: string, b: string, t: number): string {
+function hardened(name: AccentName): Accent {
+function warmed(name: AccentName): Accent {
+function mapAccents(transform: (name: AccentName) => Accent): Accents {
+  accents: ACCENTS_ON_LIGHT,
+  slate950: "2 6 23",
+  accents: mapAccents(reversed),
+  slate950: "255 255 255",
+  accents: mapAccents(hardened),
+  slate950: "0 0 0",
+  accents: mapAccents(warmed),
+  white: PAPER_SURFACE,
+  slate950: "18 15 10",
+export const CSS_VARIABLES: Readonly<
+  slate950: "--slate-950",
+export function accentVariable(name: AccentName, step: AccentStep): string {
+export function paletteVariables(palette: Palette): Record<string, string> {
+export const THEME_STORAGE_KEY = "evercoat.theme";
+export function prePaintScript(): string {



2026-08-27T22:10:03.566935Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=1; Get-Content apps/web/app/layout.tsx | ForEach-Object { if($i -ge 55 -and $i -le 100){"$i`t$_"}; $i++ }; $i=1; Get-Content SECURITY.md | ForEach-Object { if($i -ge 225 -and $i -le 240){"$i`t$_"}; $i++ }; rg -n "securityHeaders|headers|Content-Security" render.yaml apps/web next.config.* Dockerfile* .github -g "*"'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=1; Get-Content apps/web/app/layout.tsx | ForEach-Object { if($i -ge 55 -and $i -le 100){"$i`t$_"}; $i++ }; $i=1; Get-Content SECURITY.md | ForEach-Object { if($i -ge 225 -and $i -le 240){"$i`t$_"}; $i++ }; rg -n "securityHeaders|headers|Content-Security" render.yaml apps/web next.config.* Dockerfile* .github -g "*"' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command '$i=1; Get-Content apps/web/app/layout.tsx | ForEach-Object { if($i -ge 55 -and $i -le 100){"$i`t$_"}; $i++ }; $i=1; Get-Content SECURITY.md | ForEach-Object { if($i -ge 225 -and $i -le 240){"$i`t$_"}; $i++ }; rg -n "securityHeaders|headers|Content-Security" render.yaml apps/web next.config.* Dockerfile* .github -g "*"'` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'rg -n "dangerouslySetInnerHTML|prePaintScript" apps/web/app/layout.tsx; rg -n "Content-Security-Policy without|unsafe-inline" SECURITY.md; rg -n "Content-Security-Policy|script-src" render.yaml apps/web .github' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
2026-08-27T22:10:09.472808Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.9 seconds
Output:
23:import { prePaintScript } from "@/lib/theme";
88:            `dangerouslySetInnerHTML` because there is no other way to inline a
92:        <script dangerouslySetInnerHTML={{ __html: prePaintScript() }} />
234:- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy without `unsafe-inline` scripts.

 exited 1 in 895ms:
23:import { prePaintScript } from "@/lib/theme";
88:            `dangerouslySetInnerHTML` because there is no other way to inline a
92:        <script dangerouslySetInnerHTML={{ __html: prePaintScript() }} />
234:- HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a Content-Security-Policy without `unsafe-inline` scripts.

codex
Found one issue:

- [P2] The pre-paint theme script conflicts with the required CSP — [layout.tsx:92](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/layout.tsx:92)

  `SECURITY.md` requires a Content Security Policy without `unsafe-inline` scripts, but this commit injects an unnonced inline script. Under that production policy, the browser blocks it, so the dark-theme first-paint fix does not work. The script needs an allowed external source or a nonce/hash integrated with the deployed CSP.
tokens used
52,661
Found one issue:

- [P2] The pre-paint theme script conflicts with the required CSP — [layout.tsx:92](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/layout.tsx:92)

  `SECURITY.md` requires a Content Security Policy without `unsafe-inline` scripts, but this commit injects an unnonced inline script. Under that production policy, the browser blocks it, so the dark-theme first-paint fix does not work. The script needs an allowed external source or a nonce/hash integrated with the deployed CSP.
