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

# ---------------------------------------------------------------------------
# The test client, only when asked for.
# ---------------------------------------------------------------------------
if [ "$WITH_TEST_CLIENT" = "1" ]; then
  echo "creating the direct-grant test client 'evercoat-test' ..."
  # 409 means it already exists, which is success for a bootstrap script.
  api POST "/${KC_REALM}/clients" -d '{
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
  }' -o /dev/null -w 'client: HTTP %{http_code}\n'

  # THE AUDIENCE MAPPER IS NOT OPTIONAL.
  #
  # `app/core/security.py` decodes with `verify_aud: True` against
  # `keycloak_audience` (default `evercoat-api`). A Keycloak access token
  # carries `aud: ["account"]` by DEFAULT -- the API's own client id
  # appears there only if a mapper puts it there. Without the block
  # above, every token would be perfectly valid and rejected, and
  # python-jose reports that as the same flat "invalid token" it reports
  # for a forged signature.
  #
  # The shipped `evercoat-web` client already carries an identical
  # mapper, which is why production sign-in is sound. The test client has
  # to match it, or CI would prove something production does not do.
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

  api POST "/${KC_REALM}/users" -d "{
    \"username\": \"${username}\",
    \"email\": \"${username}@example.test\",
    \"emailVerified\": true,
    \"enabled\": true,
    \"firstName\": \"${username%%.*}\",
    \"lastName\": \"Demo\",
    \"credentials\": [{
      \"type\": \"password\",
      \"value\": \"${KC_USER_PASSWORD}\",
      \"temporary\": false
    }]
  }" -o /dev/null -w "user ${username}: HTTP %{http_code}\n"

  sub="$(api GET "/${KC_REALM}/users?username=${username}&exact=true" \
    | python -c 'import json,sys
try:
    users = json.load(sys.stdin)
    print(users[0]["id"] if users else "")
except Exception:
    print("")')"

  if [ -z "$sub" ]; then
    echo "FAIL: ${username} was not created and has no subject" >&2
    exit 1
  fi

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
  api POST "/${KC_REALM}/users/${sub}/role-mappings/realm" -d "[${role_json}]" -o /dev/null

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
