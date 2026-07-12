#!/usr/bin/env bash
#
# Mnemosyne database backup — pg_dump of the Postgres instance to a timestamped,
# compressed custom-format archive, with retention pruning.
#
# Runs against the containerized Postgres (default container: mnemosyne-postgres).
# The custom format (-Fc) supports selective + parallel restore and is compressed.
#
# Usage:
#   scripts/backup.sh [OUT_DIR]
#
# Env (defaults suit the standard compose deployment):
#   PGCONTAINER   docker container name           (default: mnemosyne-postgres)
#   PGUSER        database user                   (default: mnemosyne)
#   PGDATABASE    database name                   (default: mnemosyne)
#   BACKUP_DIR    output directory                (default: ./backups or $1)
#   RETENTION_DAYS delete dumps older than N days (default: 14)
#
# IMPORTANT: this dump contains GitHub credentials **encrypted with
# TOKEN_ENCRYPTION_KEY**. That key is NOT in the dump — back it up separately and
# securely (a secrets manager). Without it, restored credentials are unusable and
# must be reconnected. See docs/backup-dr.md.
set -euo pipefail

PGCONTAINER="${PGCONTAINER:-mnemosyne-postgres}"
PGUSER="${PGUSER:-mnemosyne}"
PGDATABASE="${PGDATABASE:-mnemosyne}"
BACKUP_DIR="${1:-${BACKUP_DIR:-./backups}}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/mnemosyne-${PGDATABASE}-${stamp}.dump"

echo "→ backing up '$PGDATABASE' from container '$PGCONTAINER' to $out"
if ! docker ps --format '{{.Names}}' | grep -qx "$PGCONTAINER"; then
  echo "error: container '$PGCONTAINER' is not running" >&2
  exit 1
fi

# -Fc custom format, compressed; stream out of the container to the host.
docker exec "$PGCONTAINER" pg_dump -U "$PGUSER" -Fc --no-owner "$PGDATABASE" > "$out"

# Fail loudly on an empty/short dump rather than pruning good backups later.
if [ ! -s "$out" ] || [ "$(wc -c < "$out")" -lt 1024 ]; then
  echo "error: dump is empty or suspiciously small — not pruning" >&2
  rm -f "$out"
  exit 1
fi

size="$(du -h "$out" | cut -f1)"
echo "✓ wrote $out ($size)"

# Retention: prune dumps older than RETENTION_DAYS.
pruned="$(find "$BACKUP_DIR" -name 'mnemosyne-*.dump' -type f -mtime "+${RETENTION_DAYS}" -print -delete | wc -l | tr -d ' ')"
echo "✓ pruned $pruned dump(s) older than ${RETENTION_DAYS}d"
echo "note: back up TOKEN_ENCRYPTION_KEY separately — the dump alone can't decrypt GitHub credentials."
