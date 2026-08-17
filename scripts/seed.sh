#!/usr/bin/env bash
# Seed synthetic demo data. Wrapper around seed.py -- see that file for
# what it deliberately does not create.
set -euo pipefail
export SEED_DATABASE_URL="${SEED_DATABASE_URL:-postgresql://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd}"
echo "seeding ${SEED_DATABASE_URL%%:*}://…/$(echo "$SEED_DATABASE_URL" | sed 's|.*/||')"
python "$(dirname "$0")/seed.py"
