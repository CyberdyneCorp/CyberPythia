#!/usr/bin/env bash
#
# Mnemosyne database restore — restore a pg_dump custom-format archive into the
# Postgres instance. DESTRUCTIVE: drops and recreates the objects it restores.
#
# Usage:
#   scripts/restore.sh <DUMP_FILE>
#
# Env (defaults suit the standard compose deployment):
#   PGCONTAINER   docker container name  (default: mnemosyne-postgres)
#   PGUSER        database user          (default: mnemosyne)
#   PGDATABASE    database name          (default: mnemosyne)
#
# After a restore, the API applies migrations on boot (run_migrations_on_boot);
# if you restored an older dump, the next API start brings the schema to head.
# Ensure TOKEN_ENCRYPTION_KEY matches the one in force when the dump was taken,
# or stored GitHub credentials will not decrypt (reconnect them). See
# docs/backup-dr.md.
set -euo pipefail

PGCONTAINER="${PGCONTAINER:-mnemosyne-postgres}"
PGUSER="${PGUSER:-mnemosyne}"
PGDATABASE="${PGDATABASE:-mnemosyne}"
DUMP="${1:-}"

if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "usage: scripts/restore.sh <DUMP_FILE>" >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$PGCONTAINER"; then
  echo "error: container '$PGCONTAINER' is not running" >&2
  exit 1
fi

echo "!! about to restore '$DUMP' into '$PGDATABASE' on '$PGCONTAINER'"
echo "!! this DROPS and recreates the restored objects. Ctrl-C within 5s to abort."
sleep 5

# --clean --if-exists drops existing objects first; --no-owner avoids role
# mismatches. Errors are surfaced but do not abort mid-stream (--exit-on-error
# omitted intentionally so a benign extension/owner notice doesn't halt a restore).
docker exec -i "$PGCONTAINER" pg_restore -U "$PGUSER" -d "$PGDATABASE" \
  --clean --if-exists --no-owner < "$DUMP"

echo "✓ restore complete. Restart the API so it applies migrations to head."
