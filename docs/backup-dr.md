# Backup & disaster recovery

How to back up Mnemosyne, what is (and isn't) recoverable, and how to restore
after data loss.

## What holds state

| Component | Container | Volume | Criticality |
|---|---|---|---|
| **PostgreSQL** (+ pgvector) | `mnemosyne-postgres` | `postgres_data` | **Critical** — the primary datastore |
| **MinIO** (object storage) | `mnemosyne-minio` | `minio_data` | Low — re-derivable by re-sync |
| **Redis** (arq queue + locks) | `mnemosyne-redis` | `redis_data` | None — ephemeral; jobs re-enqueue |
| **MCP OAuth registrations** | (API) | `mcp_oauth_data` | Low — DCR clients re-register |
| **`TOKEN_ENCRYPTION_KEY`** | — | env / secret | **Critical** — see below |

### What is irreplaceable vs. re-derivable

Back up because it **cannot** be reconstructed from GitHub:
- **GitHub connection credentials** (App private keys, PATs, webhook secrets) —
  stored **encrypted** in Postgres; also needs `TOKEN_ENCRYPTION_KEY` to decrypt.
- **Agent memories** (`agent_memories`) — human/agent-authored.
- **Metrics & readiness time-series** (`repository_metrics_snapshots`,
  `repository_readiness_snapshots`) — accrue one row/repo/day and are **not
  back-fillable**.
- **Audit log**, **API keys** (hashed), **sync-run history**.

Re-derivable from GitHub by a re-sync (so a lossy restore is survivable, just
expensive): repositories, documents, OpenSpec changes, issues, PRs, file trees,
source chunks, embeddings, MinIO raw-payload snapshots.

### `TOKEN_ENCRYPTION_KEY` — back it up separately

Connection credentials are Fernet-encrypted with `TOKEN_ENCRYPTION_KEY`. A
database dump contains only the ciphertext. **Store this key in a secrets manager
independently of the database backups.** Restoring the DB with a different key
leaves credentials undecryptable — you'd reconnect GitHub (a few clicks) but lose
nothing else.

## RPO / RTO targets

- **RPO** (max data loss): a **daily** backup bounds loss to ~24h — acceptable,
  since the only non-re-derivable daily data is the metrics/readiness snapshot
  and any memories written that day. Tighten to hourly if memories are heavily
  used.
- **RTO** (time to restore): minutes — restore a dump, restart the API (it
  migrates on boot), trigger a sync to refresh derived data.

## Backing up

### Recommended: Coolify scheduled backups (Postgres)

Coolify backs up a managed Postgres on a schedule to an S3-compatible target.
On the `cyberdyne` server, open the `mnemosyne-postgres` resource → **Backups** →
add a scheduled backup (daily), destination an S3 bucket, retention ≥ 14 days.
This is the primary, automated mechanism. Verify the first backup lands in S3.

### Manual / verification: the bundled script

`scripts/backup.sh` runs `pg_dump -Fc` against the container and prunes old dumps:

```bash
# on the host running the compose stack (or the Coolify server)
BACKUP_DIR=/var/backups/mnemosyne RETENTION_DAYS=14 scripts/backup.sh
```

Defaults: container `mnemosyne-postgres`, db/user `mnemosyne`, `./backups`,
14-day retention. Override via `PGCONTAINER` / `PGUSER` / `PGDATABASE`. Copy the
resulting `.dump` off-box (the same S3 bucket, or elsewhere) — a backup on the
same host does not survive host loss.

### MinIO (optional)

Snapshots are re-derivable, so backing up MinIO is optional. To keep it, mirror
the bucket to another target:

```bash
mc mirror mnemosyne/mnemosyne-artifacts s3/your-backup-bucket/minio
```

Redis and the OAuth volume need no backup (ephemeral / re-derivable).

## Restoring

### Postgres

```bash
scripts/restore.sh /var/backups/mnemosyne/mnemosyne-mnemosyne-<stamp>.dump
```

It `pg_restore --clean --if-exists` into the DB. Then:

1. Ensure `TOKEN_ENCRYPTION_KEY` matches the value in force when the dump was
   taken (from your secrets manager). If it differs, reconnect GitHub afterward.
2. **Restart the API** — it runs `alembic upgrade head` on boot, bringing an
   older dump's schema to head.
3. Trigger a sync (**Sync now** per org, or wait for the nightly run) to refresh
   re-derivable data (docs/issues/PRs/chunks/embeddings) and the MinIO snapshots.

### Full-stack rebuild (host / region loss)

1. Redeploy the compose stack on a fresh host via Coolify.
2. Set env from your secrets manager — especially `TOKEN_ENCRYPTION_KEY`,
   `DATABASE_URL`, CyberdyneAuth client secrets, `MINIO_*`.
3. Restore the latest Postgres dump (above). The API migrates on boot.
4. Trigger a full sync to rebuild derived data + snapshots.

## Verify restores (do this, don't assume)

A backup you've never restored is a hope, not a plan. Quarterly (or after schema
changes), restore the latest dump into a throwaway Postgres and check row counts:

```bash
docker run -d --name pg-verify -e POSTGRES_PASSWORD=x pgvector/pgvector:pg16
docker exec -i pg-verify createdb -U postgres mnemosyne
docker exec -i pg-verify pg_restore -U postgres -d mnemosyne --no-owner < <dump>
docker exec pg-verify psql -U postgres -d mnemosyne -c \
  "select count(*) from repositories; select count(*) from agent_memories;"
docker rm -f pg-verify
```

## Checklist

- [ ] Coolify scheduled Postgres backup enabled, daily, → S3, retention ≥ 14d
- [ ] `TOKEN_ENCRYPTION_KEY` stored in a secrets manager, separate from DB backups
- [ ] All prod env (DB URL, CyberdyneAuth secrets, MINIO_\*) recorded in the secrets manager
- [ ] Backups copied off the primary host
- [ ] A test-restore performed and row counts sanity-checked
