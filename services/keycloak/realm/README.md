# The `evercoat` Keycloak realm

> This file exists because **the realm JSON cannot carry comments.**
>
> It used to. `evercoat-realm.json` held three top-level `_comment*` keys,
> and Keycloak's importer refuses any field it does not recognise:
>
> ```
> ERROR: Failed to run import
> ERROR: Unrecognized field "_comment" (class RealmRepresentation),
>        not marked as ignorable (144 known properties)
> ```
>
> The import did not warn and skip — it aborted, and Keycloak then failed
> to start at all. So **that realm had never once been imported**: every
> `docker compose up` since Slice 1 produced either a dead Keycloak or one
> with no `evercoat` realm, and nobody noticed because nothing had ever
> asked it for a token. It was found the first time CI actually ran
> Keycloak, which is the whole argument for running it.
>
> The commentary lives here now, where it costs nothing. A test
> (`apps/api/tests/test_keycloak_realm.py`) asserts the JSON grows no
> unimportable keys again.

## What this realm owns, and what it does not

Keycloak owns **identity only**. It does not own authorization.

The realm roles here are coarse bundles. The application authorizes on
**permissions read from the database** (`CLAUDE.md` §6), so a role is a
label the token carries and a permission is a fact the database states.

Membership is deliberately **not** a token claim. A JWT is a statement
about identity; it is not a current statement about authorization.
Revoking a project membership has to bite immediately, not whenever the
access token happens to expire — so `app/core/security.py` re-reads
membership and permissions per request.

## The roles must match the database exactly

The ten realm roles must equal `core.roles.code` from
`002_seed_roles_permissions.sql`, character for character.

**A mismatch is silent.** Keycloak issues a token naming a role the
database has never heard of, the principal query returns no permissions,
and the user sees an empty application with no error anywhere.
`tests/db/test_002_roles_permissions.py` asserts the two lists agree.

## Tokens

Access tokens are short, because authorization is re-read from the
database on every request anyway. A long-lived token buys nothing here
and widens the window on a stolen one.

Refresh rotation is on with reuse detection, so a replayed refresh token
invalidates the whole chain.

## Users — and how they actually get created

**No users are in this file, on purpose.** Seeding users in a realm
import means the same credentials exist in every environment the file is
imported into, including any that later becomes production.

No default roles are assigned either: a new account should sign in and
see nothing until somebody deliberately grants it membership.

**CORRECTED 2026-08-18.** This note used to say the ten demo users "are
created by `scripts/seed.sh`". They were not. `scripts/seed.py` writes
`core.users` rows in the DATABASE with placeholder subjects
(`keycloak_sub = 'demo-chem.demo'`) and never touches Keycloak — so the
realm had zero users, and a real token's subject (a UUID) matched no row
even if one could have been issued.

Two scripts close that gap, and both must run:

| Script | What it does |
|---|---|
| `scripts/keycloak-bootstrap.sh` | Creates the ten users in Keycloak, assigns realm roles, and writes a `username -> subject` map. `--with-test-client` additionally creates a direct-grant client for tests. |
| `scripts/keycloak-bind-subs.py` | Rebinds `core.users.keycloak_sub` to those real subjects, matched on email. |

Without the second, authentication succeeds and every request is refused
with **403, not 401** — the token is valid and simply matches nobody.
That distinction is the fastest way to tell the two failures apart.

## The audience mapper

`evercoat-web` carries an `oidc-audience-mapper` that adds `evercoat-api`
to the access token's `aud`.

It is **load-bearing**. A Keycloak access token carries `aud: ["account"]`
by default; the API decodes with `verify_aud: True` against
`evercoat-api`. Without the mapper every genuine token is rejected, and
python-jose reports it as the same flat `invalid token` it reports for a
forged signature. Any client that talks to the API needs the same mapper.

## The three clients

These notes lived inside the JSON as `_comment` keys and were part of why
it would not import.

### `evercoat-web` — the browser client

**Public, on purpose.** A browser cannot keep a secret, and shipping one
would only create the illusion of confidentiality. **PKCE S256** is what
actually protects the authorization code.

**Redirect URIs are exact.** A wildcard host here is an open redirect and
an authorization-code interception path. Adding a deployment means adding
its URI explicitly.

It carries the `oidc-audience-mapper` described above. Without it the
token's `aud` omits `evercoat-api` and the API rejects every request as
an invalid audience — a failure that presents as a broken login.

### `evercoat-api` — bearer-only

The API validates tokens and never initiates a login, so it needs no
flows of its own.

**It has no service account.** An API that can mint its own privileged
token has a path around the authorization chain. Background work runs as
the worker client instead.

### `evercoat-worker` — confidential, for Celery

The committed secret is a **placeholder**, replaced at provisioning from
SOPS. It must never be the value in this file.

**The worker holds no realm role.** Background jobs act on records they
are given, not on an identity that can approve anything.
