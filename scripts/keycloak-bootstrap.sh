#!/usr/bin/env bash
# Bring a running Keycloak to the state the application actually needs.
#
# WHY THIS SCRIPT EXISTS
# ----------------------
# `services/keycloak/realm/evercoat-realm.json` defines three clients and
# ten realm roles -- and ZERO users. A realm with no users has no sign-in
# path, which is the same defect this project has now caught five times
# under a different name: "which production path WRITES this?". Importing
# that realm gives you an identity provider nobody can authenticate
# against.
#
# It also explains why authentication has never once been exercised. The
# API verifies tokens properly (JWKS, issuer, audience, expiry -- all
# four), and it has never had a real token to verify, because no Keycloak
# has ever run anywhere: not on Render, not in CI, not on the dev host.
#
# WHAT IT DOES NOT DO
# -------------------
# It does not add a password-grant client or test users to the production
# realm file. A direct-access-grant client exists so tests can obtain a
# token without driving a browser; putting it in the shipped realm would
# mean every deployment carried a password-grant path forever because CI
# once needed one. It is created HERE, at bootstrap time, and only
# when --with-test-client is passed.
#
# Usage:
#   scripts/keycloak-bootstrap.sh [--with-test-client]
#
# Environment:
#   KC_URL            base URL          (default http://localhost:8080)
#   KC_ADMIN          admin username    (default admin)
#   KC_ADMIN_PASSWORD admin password    (required)
#   KC_REALM          realm             (default evercoat)
#   KC_USER_PASSWORD  password set on every created user (required)
#   KC_SUBS_OUT       where to write the username -> sub map
#                     (default ./keycloak-subs.json)

set -euo pipefail

KC_URL="${KC_URL:-http://localhost:8080}"
KC_ADMIN="${KC_ADMIN:-admin}"
KC_REALM="${KC_REALM:-evercoat}"
KC_SUBS_OUT="${KC_SUBS_OUT:-./keycloak-subs.json}"
WITH_TEST_CLIENT=0
[ "${1:-}" = "--with-test-client" ] && WITH_TEST_CLIENT=1

: "${KC_ADMIN_PASSWORD:?KC_ADMIN_PASSWORD is required}"
: "${KC_USER_PASSWORD:?KC_USER_PASSWORD is required}"

# The ten users the seeder writes into core.users, as
# `username:realm_role`. They match `scripts/seed.py` exactly -- one user
# per role, so every permission path has a holder.
USERS=(
  "chem.demo:product_development_chemist"
  "eng.demo:product_development_engineer"
  "lead.demo:product_development_lead"
  "dir.demo:product_development_director"
  "qa.demo:qa_compliance_officer"
  "tech.demo:laboratory_technician"
  "proc.demo:procurement_specialist"
  "prod.demo:production_engineer"
  "exec.demo:executive_viewer"
  "admin.demo:administrator"
)

# ---------------------------------------------------------------------------
# Wait for Keycloak. Not a fixed sleep: Keycloak's startup varies from a
# few seconds to a minute, and a sleep long enough to be safe is a minute
# wasted on every run while STILL not being proof.
# ---------------------------------------------------------------------------
echo "waiting for Keycloak at ${KC_URL} ..."
deadline=$(( SECONDS + 180 ))
until code="$(curl -s -o /dev/null -w '%{http_code}' "${KC_URL}/realms/master" 2>/dev/null)" \
      && [ "$code" = "200" ]; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "FAIL: Keycloak did not answer within 180s (last status: ${code:-none})" >&2
    exit 1
  fi
  sleep 3
done
echo "Keycloak is up."

# ---------------------------------------------------------------------------
# Admin token. `|| tok=""` rather than a bare assignment: a failing curl
# inside $( ) aborts the whole script under `set -e`, which reports as a
# silent exit with no message at all.
# ---------------------------------------------------------------------------
admin_token() {
  local body=""
  body="$(curl -s -X POST \
    "${KC_URL}/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=${KC_ADMIN}" \
    -d "password=${KC_ADMIN_PASSWORD}" \
    -d "grant_type=password")" || body=""
  printf '%s' "$body" | python -c \
    'import json,sys; d=json.load(sys.stdin); print(d.get("access_token",""))' 2>/dev/null || true
}

TOKEN="$(admin_token)"
if [ -z "$TOKEN" ]; then
  echo "FAIL: could not obtain an admin token -- check KC_ADMIN_PASSWORD" >&2
  exit 1
fi

api() {
  local method="$1" path="$2"
  shift 2
  curl -s -X "$method" "${KC_URL}/admin/realms${path}" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" "$@"
}

# 🔴 CURL EXITS 0 ON AN HTTP 409, AND ON A 500.
#
# The first version of this script ignored the status entirely, so a
# failed role mapping, a rejected client, and a user that already existed
# with a DIFFERENT password all looked identical to success -- and the
# script went on to write a subject map binding accounts nobody could
# authenticate as. Codex caught it. A bootstrap that reports success
# while leaving the realm unusable is worse than one that fails, because
# the next thing to break is authentication, three steps away.
api_status() {
  local method="$1" path="$2"
  shift 2
  curl -s -o /dev/null -w '%{http_code}' -X "$method" "${KC_URL}/admin/realms${path}"     -H "Authorization: Bearer ${TOKEN}"     -H "Content-Type: application/json" "$@"
}

# Fails loudly unless the status is 2xx or one the caller tolerates.
expect_status() {
  local got="$1" what="$2"
  shift 2
  case "$got" in 2*) return 0 ;; esac
  for ok in "$@"; do
    [ "$got" = "$ok" ] && return 0
  done
  echo "FAIL: ${what} returned HTTP ${got}" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# The test client, only when asked for.
# ---------------------------------------------------------------------------
if [ "$WITH_TEST_CLIENT" = "1" ]; then
  echo "creating the direct-grant test client 'evercoat-test' ..."

  # 🔴 THE AUDIENCE MAPPER IS NOT OPTIONAL.
  #
  # `app/core/security.py` decodes with `verify_aud: True` against
  # `keycloak_audience` (default `evercoat-api`). A Keycloak access token
  # carries `aud: ["account"]` by DEFAULT -- the API's own client id
  # appears there only if a mapper puts it there. Without it every token
  # is perfectly valid and rejected, and python-jose reports that as the
  # same flat "invalid token" it reports for a forged signature.
  #
  # The shipped `evercoat-web` client already carries an identical
  # mapper, which is why production sign-in is sound. The test client has
  # to match it, or CI would prove something production does not do.
  client_status="$(api_status POST "/${KC_REALM}/clients" -d '{
    "clientId": "evercoat-test",
    "name": "CI and local testing only -- direct access grants",
    "enabled": true,
    "publicClient": true,
    "standardFlowEnabled": false,
    "directAccessGrantsEnabled": true,
    "serviceAccountsEnabled": false,
    "protocol": "openid-connect",
    "fullScopeAllowed": true,
    "attributes": {"post.logout.redirect.uris": "+"},
    "protocolMappers": [{
      "name": "evercoat-api-audience",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-audience-mapper",
      "config": {
        "included.client.audience": "evercoat-api",
        "access.token.claim": "true",
        "id.token.claim": "false"
      }
    }]
  }')"
  expect_status "$client_status" "creating the evercoat-test client" 409
  echo "client evercoat-test: HTTP ${client_status}"

  # A 409 means one already exists -- and says NOTHING about whether it is
  # enabled, has direct grants, or carries the mapper. An existing client
  # in the wrong shape issues tokens the API rejects, so the settings are
  # re-asserted rather than assumed.
  if [ "$client_status" = "409" ]; then
    cid="$(api GET "/${KC_REALM}/clients?clientId=evercoat-test" | python -c 'import json,sys
try:
    cs = json.load(sys.stdin)
    print(cs[0]["id"] if cs else "")
except Exception:
    print("")')"
    if [ -z "$cid" ]; then
      echo "FAIL: evercoat-test answered 409 but cannot be found" >&2
      exit 1
    fi

    status="$(api_status PUT "/${KC_REALM}/clients/${cid}" -d '{
      "clientId": "evercoat-test",
      "enabled": true,
      "publicClient": true,
      "standardFlowEnabled": false,
      "directAccessGrantsEnabled": true,
      "fullScopeAllowed": true
    }')"
    expect_status "$status" "repairing the evercoat-test client"

    # The mapper, re-created when missing. 409 here means it is already
    # present, which is the outcome either way.
    api_status POST "/${KC_REALM}/clients/${cid}/protocol-mappers/models" -d '{
      "name": "evercoat-api-audience",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-audience-mapper",
      "config": {
        "included.client.audience": "evercoat-api",
        "access.token.claim": "true",
        "id.token.claim": "false"
      }
    }' >/dev/null || true
  fi
fi

# ---------------------------------------------------------------------------
# Users. Each is created, given a NON-temporary password (a temporary one
# forces a password-update flow that a direct grant cannot complete, and
# the failure reads as "invalid_grant" -- an unhelpful lie), and assigned
# its realm role.
# ---------------------------------------------------------------------------
echo "{" > "$KC_SUBS_OUT"
first=1

for entry in "${USERS[@]}"; do
  username="${entry%%:*}"
  role="${entry##*:}"

  # CREATE, then REPAIR. `POST /users` answers 409 when the user already
  # exists, and curl exits 0 on a 409 -- so a rerun used to leave the old
  # account untouched: possibly disabled, possibly with a different
  # password, and the script would still write a valid-looking subject
  # map. Everything downstream then fails at `invalid_grant`, four steps
  # away from the cause.
  status="$(api_status POST "/${KC_REALM}/users" -d "{
    \"username\": \"${username}\",
    \"email\": \"${username}@example.test\",
    \"emailVerified\": true,
    \"enabled\": true,
    \"firstName\": \"${username%%.*}\",
    \"lastName\": \"Demo\"
  }")"
  expect_status "$status" "creating ${username}" 409
  echo "user ${username}: HTTP ${status}"

  sub="$(api GET "/${KC_REALM}/users?username=${username}&exact=true"     | python -c 'import json,sys
try:
    users = json.load(sys.stdin)
    print(users[0]["id"] if users else "")
except Exception:
    print("")')"

  if [ -z "$sub" ]; then
    echo "FAIL: ${username} was not created and has no subject" >&2
    exit 1
  fi

  # Applied UNCONDITIONALLY, to a new user and an existing one alike.
  # This is the step that makes a rerun mean something: whatever state the
  # account was in, it is now enabled, verified, and holds the password
  # this run generated.
  status="$(api_status PUT "/${KC_REALM}/users/${sub}" -d "{
    \"enabled\": true,
    \"emailVerified\": true,
    \"email\": \"${username}@example.test\"
  }")"
  expect_status "$status" "enabling ${username}"

  # A NON-temporary password. A temporary one forces an update-password
  # action that a direct grant cannot complete, and Keycloak reports the
  # refusal as "invalid_grant" -- which reads as a wrong password.
  status="$(api_status PUT "/${KC_REALM}/users/${sub}/reset-password" -d "{
    \"type\": \"password\",
    \"value\": \"${KC_USER_PASSWORD}\",
    \"temporary\": false
  }")"
  expect_status "$status" "setting the password for ${username}"

  # Brute-force protection is on in this realm (failureFactor 5). A rerun
  # after failed attempts would otherwise find the account locked out and
  # report a wrong password.
  api_status PUT "/${KC_REALM}/attack-detection/brute-force/users/${sub}" >/dev/null || true

  role_json="$(api GET "/${KC_REALM}/roles/${role}")"
  role_ok="$(printf '%s' "$role_json" | python -c 'import json,sys
try:
    r = json.load(sys.stdin)
    print("1" if r.get("id") else "")
except Exception:
    print("")')"
  if [ -z "$role_ok" ]; then
    echo "FAIL: realm role '${role}' does not exist -- the realm import did not apply" >&2
    exit 1
  fi
  status="$(api_status POST "/${KC_REALM}/users/${sub}/role-mappings/realm" \n    -d "[${role_json}]")"
  expect_status "$status" "granting ${role} to ${username}" 409

  [ "$first" = "1" ] || echo "," >> "$KC_SUBS_OUT"
  first=0
  printf '  "%s": "%s"' "$username" "$sub" >> "$KC_SUBS_OUT"
done

printf '\n}\n' >> "$KC_SUBS_OUT"

echo
echo "wrote ${#USERS[@]} subjects to ${KC_SUBS_OUT}"
echo "NEXT: scripts/keycloak-bind-subs.py -- core.users.keycloak_sub still"
echo "holds the seeder's placeholders ('demo-<username>'), and until it is"
echo "rebound every valid token resolves to no principal at all."
