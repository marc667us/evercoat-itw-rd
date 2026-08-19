# ▶ RESUME HERE — EvercoatITWRD APP

**Session closed 2026-08-18 (part 4). Read this file, then `TODO.md`.**

Repository: **https://github.com/marc667us/evercoat-itw-rd** (PUBLIC),
branch `master`. Tip **`4287feb`**, working tree **clean**, **pushed**
(`HEAD == origin/master`, verified).

Session transcript archived at
`../session-logs/session_2026-08-18_pt4_messaging_keycloak.jsonl`.

---

## 🔴 FIRST THING TO DO NEXT SESSION

**Read the `bash -x` trace in the Auth job. It was enabled for exactly this.**

```bash
gh run list --limit 3
gh api repos/marc667us/evercoat-itw-rd/actions/jobs/<job_id>/logs > auth.log
grep -n "looking up chem.demo" -B 40 auth.log
```

### Where CI actually stands (measured on run `32205073660`, commit `a51f89b`)

| Job | Result |
|---|---|
| API — lint, type, test | ✅ **success** |
| Web — lint, type, test | ✅ success |
| E2E — browser shell, axe-core | ✅ success |
| Security scan | ✅ success |
| **Auth — real Keycloak** | ❌ **failure** |

**Four of five are green.** Auth is the only one left, and it has moved a
long way: Keycloak now starts, **imports the shipped realm** (which it
could never do before), creates the test client `HTTP 201` and the first
user `HTTP 201`.

### The one open defect

Immediately after `user chem.demo: HTTP 201`, the step dies with a bare
`Process completed with exit code 6` — curl's *"could not resolve host"* —
**for the same host that had just answered two requests successfully**,
and **without the script's own failure branch printing anything**.

`api_body()` was added specifically to name the failing request, URL and
curl error. It did not fire. **So the abort is not where the
instrumentation assumed it was, and reasoning from the source has now
been wrong twice.** Do not guess a third time — `bash -x` is enabled on
that step; read the trace.

Two candidate causes worth holding, neither confirmed:
- something in the `users?username=...&exact=true` command substitution
  at `scripts/keycloak-bootstrap.sh:293`;
- an environment/DNS effect between the container and the runner that
  only bites on the third request.

Note the admin-token expiry fix is already in (Keycloak's master token
lives ~60 s, and ten users at several requests each runs past it) — that
was a real latent bug but is **not** this failure, since this dies on the
first user.

## ✅ LIVE, AND VERIFIED PUBLIC THIS SESSION

# https://itwevercoatrd.aiappinvent.com
# https://itwevercoat.aiappinvent.com

Both certificated (expire **2026-11-16**). Render static site, free.

**The operator reported the app unreachable from a second computer, a
phone, and a client in another state. It was measured from outside this
machine's browser cache and it is genuinely up:**

| Check | Result |
|---|---|
| DNS via Cloudflare **and** Google public resolvers | ✅ both hosts → `evercoat-itw-rd-web.onrender.com` → `216.24.57.7 / .15` |
| TLS, both hosts × both edge IPs, SNI set | ✅ valid, 89 days left |
| `http://` → `https://` | ✅ 200 |
| Root, iPhone UA, cache-bypass headers | ✅ 200, `<title>EvercoatITWRD APP</title>` |
| `/dashboard` `/projects` `/formulations` | ✅ 200 / 200 / 200 |
| All 9 JS+CSS assets | ✅ **0 broken of 9** |
| `www.` variant | ❌ 000 — no `www` record exists |
| IPv6 (AAAA) | none — *including on Render's own hostname*, so this is Render's design, not a misconfiguration |

**Then this host lost its uplink entirely**, which is a live candidate
explanation for the operator's report: an intermittent router/ISP outage
takes every device on that LAN off the app at once while a device holding
a cached page still shows it.

**Unresolved for the next session:** the client in another state. That
cannot be this router. Two things to establish before touching code —
(1) exactly which URL they were sent (the `www.` form fails), and (2)
whether it fails for them *now*, since the domain genuinely did not
resolve earlier on 08-18 and a device that tried then cached the
NXDOMAIN for ~1 hour. **Do not "fix" the deployment before proving it is
broken for them** — every server-side check above passed.

---

## What `93bdb57` and `86fd34b` delivered

### Messaging — the schema finally has a writer

`app/domains/messaging/service.py` + `app/api/messaging.py`, **6 routes**
(103 total). Channels, technical threads per record, messages,
`#CODE` reference resolution, `@mention` resolution, notifications,
and promotion.

- **Links resolve at WRITE time**, into `messaging.message_links`. A
  message must say what it said when it was written, not re-render after
  a record is renamed.
- **`promote_message` is the only path from chat to a controlled record**
  (§7). It requires `project.edit` and produces a **task**, not a
  conclusion — somebody still has to do the work and sign for it.
- **No `message.*` permissions were invented.** There are none in the
  catalogue and inventing them would repeat the defect this project has
  caught six times: a permission nobody holds, gating a feature nobody
  can then use. Messaging is governed by RLS and project membership.

### 🔴 Authentication has now run for the first time — and the realm was broken

The API has verified tokens correctly since Slice 1 and **had never once
verified a real one**, because no Keycloak had ever run anywhere. Running
it in CI immediately found four things, each of which presents to an
operator as an unexplained "sign-in is broken":

1. **The shipped realm could not be imported — since Slice 1.** It
   carried **seven** `_comment` keys (three top-level, **four nested
   inside clients**). Keycloak's importer *aborts* on an unrecognised
   field — it does not warn and skip — and then fails to start. So every
   `docker compose up` since Slice 1 produced a dead Keycloak or one with
   no `evercoat` realm. Nobody noticed because nothing had ever asked it
   for a token.
2. **The realm has zero users.** A realm with no users has no sign-in
   path — the same shape as the five-roles-with-no-write-path finding.
3. **`seed.py` writes `keycloak_sub = 'demo-chem.demo'`** while a real
   token carries a UUID. A perfectly valid token then resolves to no
   principal: the API answers **403, not 401**. That distinction is the
   single most useful diagnostic in the whole auth path.
4. **A Keycloak access token's `aud` is `["account"]`** unless a mapper
   adds `evercoat-api`. `evercoat-web` *does* carry that mapper — so
   production sign-in is sound — but any client that talks to the API
   needs it, or every genuine token is rejected with the same flat
   "invalid token" a forged one gets.

Now in place:

| File | Role |
|---|---|
| `scripts/keycloak-bootstrap.sh` | Creates the ten users + role mappings. `--with-test-client` adds a direct-grant client **that is deliberately NOT in the shipped realm**. |
| `scripts/keycloak-bind-subs.py` | Rebinds `core.users.keycloak_sub` to real subjects, matched on email. One transaction — all ten or none. |
| `apps/api/tests/integration/test_auth_end_to_end.py` | 6 tests against a real token: valid, absent, forged, no org header, foreign org, and permissions read from the DB rather than the token. |
| `.github/workflows/ci.yml` job **`auth`** | Runs Keycloak 26 with the shipped realm. **Costs nothing, needs no deploy.** |
| `apps/api/tests/test_keycloak_realm.py` | 14 tests, no DB, no Keycloak. Recursive check for unimportable keys **at any depth** — it is what found the four nested ones. |
| `scripts/assert-suite-ran.py` | passed / failed / **skipped** as three numbers. A fully skipped pytest run exits 0 and would read as proof. |
| `services/keycloak/realm/README.md` | Where the realm's commentary lives now, since the JSON cannot carry it. |

### What `93bdb57` fixes (the three failed jobs on `86fd34b`)

- **API** — `projects.projects` has **no `project_type` and no
  `created_by`**, and `workflow.tasks` has **no `created_by`**.
  `promote_message` would have failed at runtime. Schema read, not
  assumed.
- **Auth** — the realm import failure above.
- **Security** — Semgrep `use-defused-xml-parse` on the new script.
  Switched to `defusedxml` rather than carrying an exception for
  "trusted" input.

### Codex findings — all four real, all fixed

- `POST /users` answers **409** and curl exits **0**, so a rerun left the
  old account untouched (possibly disabled, possibly a different
  password) while still writing a valid-looking subject map. Now:
  create, then **unconditionally** enable + reset password + clear the
  brute-force lockout, for new and existing users alike.
- An existing `evercoat-test` client was accepted without checking it was
  enabled, had direct grants, or carried the mapper. Re-asserted on 409.
- Added `api_status` / `expect_status`; **every** call now checks its
  HTTP status. A failed role mapping used to pass silently.
- `keycloak-bind-subs.py` committed as it went, leaving the DB
  half-rebound on failure. Now atomic.

### A leak I found in my own code

`_resolve_mentions` first reused `list_channels`' predicate — which
evaluates in the **author's** session. The author can always see the
channel they just posted in, so **a restricted project's channel read as
reachable for everyone**, and the mention notification would have named
that project to somebody with no access to it. The channel's RLS protects
the *messages* and cannot stop a notification row addressed to an
outsider. Recipient access is now evaluated explicitly against
confidentiality + membership, and
`tests/db/test_023_messaging.py` asserts it in both directions.

---

## Where the build actually stands

| | |
|---|---|
| Migrations | **23** (023 = `deny_mutation` names its own table) |
| API routes | **103** |
| Python test functions | **307** |
| Playwright spec files | 4 |
| CI jobs | 5 — api, web, e2e, security, **auth** |
| Slices 1–3 | shipped **and deployed** |
| Slices 4–7 | **backend built, not deployed, no UI** |

### 🔴 The honest MVP position

**By backend hours the MVP is far along. By "a user can drive the golden
scenario in a browser" it is near zero, and that is the acceptance gate.**

- **11 of the 12 web screens still render `demo-data.json`.** Only the
  API-wiring seam is real (`tests/e2e/shell/api-wiring.spec.ts`).
- **There is no sign-in flow.** `next-auth` is installed and imported by
  nothing.
- **The golden E2E does not exist.** It is MVP-1's acceptance gate
  (`IMPLEMENTATION_PLAN.md` §Golden scenario).
- **No dashboards.** Four role dashboards with drill-down are Slice 7.
- **No MSD orchestration.** `app/agents/graphs/` does not exist; Ollama
  is not installed. The retrieval half and its boundary test *are* built
  and are provable without a model.

---

## Constraints that must not be forgotten

- 🔴 **NEVER propose spending.** The API + Keycloak deploy is blocked on
  Render's free web-service quota. That is the operator's decision, not
  the build's. The CI `auth` job exists precisely so the work is not
  blocked on it.
- 🔴 **Do not touch any `aw-*` container.** Operator's words: *"if i find
  the autoworkshop in issues you will be responsible for breaking it."*
  This project's DB is `evercoat-postgres` on port **55432**.
- 🔴 **`RENDER_API_KEY` is still unrotated** since it was pasted into
  chat on 2026-08-17. Dashboard-only; operator action.
- ⚠️ **`autoworkshop-postgres` is FREE tier and EXPIRES 2026-09-01.**
- ⚠️ **Docker on this host is wedged** — engine 500s, container won't
  kill, port 55432 accepts then never answers. The operator declined
  restarting Docker Desktop (it would restart the `aw-*` stack).
  **CI is the verification path.** For fast local skips point
  `TEST_DB_PORT` at a dead port — psycopg's default connect timeout is
  infinite, so `pytest` otherwise hangs forever.
