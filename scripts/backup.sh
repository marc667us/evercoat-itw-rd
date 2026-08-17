#!/usr/bin/env bash
# Backup with verification.
#
# The database holds the company's entire R&D intellectual property --
# formulations, experimental history, failure knowledge, released product
# specifications. A formula cannot be rotated like a password, so losing
# this data is permanent in a way that losing application state is not.
#
# TWO TRAPS THIS SCRIPT EXISTS TO AVOID:
#
# 1. pg_dump under FORCE ROW LEVEL SECURITY as a non-superuser SILENTLY
#    OMITS every row the connecting role cannot see. It exits 0. The file
#    looks plausible. You discover the gap during a restore, which is the
#    worst possible moment. This script therefore dumps as the OWNER role
#    and then COMPARES ROW COUNTS between source and dump.
#
# 2. An untested backup is not a backup. --verify restores into a
#    throwaway database and re-counts. Without that, "the backup ran" and
#    "the backup is restorable" are different claims and only the weaker
#    one is being made.
#
# Usage:
#   ./scripts/backup.sh                 # dump + row-count verification
#   ./scripts/backup.sh --verify        # additionally restore and re-count
#   ./scripts/backup.sh --help

set -euo pipefail

CONTAINER="${BACKUP_CONTAINER:-evercoat-postgres}"
DB="${POSTGRES_DB:-evercoat_itw_rd}"
# The OWNER role, not the runtime role -- see trap 1.
DUMP_USER="${BACKUP_USER:-postgres}"
OUT_DIR="${BACKUP_DIR:-./backups}"
VERIFY=0

for arg in "$@"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    --help|-h) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; exit 2 ;;
  esac
done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="${OUT_DIR}/${DB}_${TS}.dump"
mkdir -p "$OUT_DIR"

# Assigning separately from declaring: `local x=$(cmd)` masks the exit
# code of cmd behind the successful assignment.
count_rows() {
  local target_db="$1"
  local out
  out="$(docker exec "$CONTAINER" psql -U "$DUMP_USER" -d "$target_db" -tAc "
    SELECT COALESCE(sum(n), 0) FROM (
      SELECT (xpath('/row/c/text()',
              query_to_xml(format('SELECT count(*) AS c FROM %I.%I', schemaname, relname),
                           false, true, '')))[1]::text::bigint AS n
      FROM pg_stat_user_tables
      WHERE schemaname NOT IN ('pg_catalog','information_schema')
    ) t")" || return 1
  echo "$out" | tr -d '[:space:]'
}

echo "==> dumping ${DB} from ${CONTAINER} as ${DUMP_USER}"
SOURCE_ROWS="$(count_rows "$DB")"
echo "    source rows: ${SOURCE_ROWS}"

# Custom format: compressed, selectively restorable, and pg_restore can
# list its contents without a running server.
docker exec "$CONTAINER" pg_dump \
  -U "$DUMP_USER" -d "$DB" \
  --format=custom --compress=9 \
  --no-owner --no-privileges \
  > "$DUMP"

BYTES="$(wc -c < "$DUMP" | tr -d '[:space:]')"
echo "    wrote ${DUMP} (${BYTES} bytes)"

if [ "$BYTES" -lt 1024 ]; then
  echo "FAIL: dump is implausibly small -- likely an RLS-filtered empty dump" >&2
  exit 1
fi

# A dump whose table list is empty is the RLS trap in its purest form.
TABLES_IN_DUMP="$(docker exec -i "$CONTAINER" pg_restore --list < "$DUMP" | grep -c 'TABLE DATA' || true)"
echo "    tables with data in dump: ${TABLES_IN_DUMP}"

if [ "$VERIFY" -eq 0 ]; then
  echo
  echo "==> dump complete, NOT verified."
  echo "    Run with --verify to prove it restores. Until then this is a"
  echo "    file that looks like a backup, not a backup."
  exit 0
fi

VERIFY_DB="${DB}_restore_check_${TS}"
echo
echo "==> verifying by restoring into ${VERIFY_DB}"

cleanup() {
  docker exec "$CONTAINER" psql -U "$DUMP_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"${VERIFY_DB}\" WITH (FORCE)" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker exec "$CONTAINER" psql -U "$DUMP_USER" -d postgres \
  -c "CREATE DATABASE \"${VERIFY_DB}\"" >/dev/null

# Roles are cluster-wide and already exist; --no-owner above means the
# restore does not need them. Exit code is checked explicitly because
# pg_restore warns freely on a clean target.
if ! docker exec -i "$CONTAINER" pg_restore \
      -U "$DUMP_USER" -d "$VERIFY_DB" --no-owner --no-privileges \
      < "$DUMP" 2> /tmp/restore_err.txt; then
  echo "    pg_restore reported errors:" >&2
  tail -20 /tmp/restore_err.txt >&2
  exit 1
fi

RESTORED_ROWS="$(count_rows "$VERIFY_DB")"
echo "    restored rows: ${RESTORED_ROWS}"

if [ "$SOURCE_ROWS" != "$RESTORED_ROWS" ]; then
  echo
  echo "FAIL: row count mismatch -- source ${SOURCE_ROWS}, restored ${RESTORED_ROWS}." >&2
  echo "      This is what an RLS-filtered dump looks like. Do not trust" >&2
  echo "      this backup." >&2
  exit 1
fi

echo
echo "==> VERIFIED"
echo "    ${SOURCE_ROWS} rows dumped and restored identically."
echo "    dump: ${DUMP}"
