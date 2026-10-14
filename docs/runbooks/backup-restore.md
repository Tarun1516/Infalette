# Backup & Disaster Recovery Runbook

**Applies to:** Neon Postgres 18.6 (primary) / RDS Postgres (fallback for
self-hosted environments) + ElastiCache Redis + S3 media (`infalette-*`).

## 1. What is backed up

| Service | Mechanism | Retention / Window | Where configured |
|---|---|---|---|
| Postgres (Neon, primary) | Branch snapshots + transaction log (PITR up to 7 days on paid plans) | 7 days prod / configurable per branch | Neon console / API / `neonctl` |
| Postgres (RDS, fallback) | Automated snapshot + transaction log (PITR) | 7 days prod / 1 day non-prod, window `03:00-04:00 UTC` | `terraform/modules/rds` `backup_retention_period`, `copy_tags_to_snapshot`, `deletion_protection` + `final_snapshot_identifier` in prod |
| Redis (ElastiCache) | Daily snapshot | 7 days prod / 1 day non-prod, window `02:00-03:00 UTC` | `terraform/modules/elasticache` |
| S3 media | Versioning + lifecycle | Non-current versions expire 30d, incomplete multipart 7d, `tmp/` 1d | `terraform/modules/s3` + bucket versioning |

Cross-region replication is **not** enabled by default — enable `replication_configuration` on the S3 module before pilot if RPO < 24h is required.

## 1a. Neon-specific operations

Neon's "branching" primitive is the recommended backup/restore mechanism for
production. A branch is a copy-on-write clone that can be promoted to the
primary branch in seconds, so a restore is effectively a swap of `DATABASE_URL_DIRECT`
in the application config.

### Restore via branch (fast path, recommended)

```bash
# 1. Create a branch from a past point in time (UTC, ISO-8601)
RESTORE_TIME="2026-08-26T04:15:00Z"
neonctl branches create \
  --project-id "$NEON_PROJECT_ID" \
  --name "restore-$(date -u +%Y%m%d%H%M)" \
  --parent main \
  --restore-timestamp "$RESTORE_TIME"

# 2. Get the new branch's direct connection string from `neonctl connection-string`
neonctl connection-string "$NEON_PROJECT_ID" --branch-name "restore-..."

# 3. Validate: apply migrations if needed, then point the app at the new branch
#    (DATABASE_URL_DIRECT for migrations, DATABASE_URL_POOLED for runtime)

# 4. After validation, optionally delete the old branch
neonctl branches delete "$NEON_PROJECT_ID" --branch-name main
```

### Point-in-time recovery (PITR)

```bash
# Neon automatically retains a configurable history window per project.
# The `neonctl branches create --restore-timestamp` command above creates
# a branch that reflects the database at the given instant.
```

### Verifying a Neon backup

```bash
# List all branches and their creation times
neonctl branches list --project-id "$NEON_PROJECT_ID" \
  --output json | jq '.[] | {name, created_at, primary}'

# Confirm the primary branch is on the expected Postgres version
neonctl branches get main --project-id "$NEON_PROJECT_ID" \
  --output json | jq '{name, primary, current_state, created_at}'
```

## 2. Verifying backups exist

```bash
# RDS — list automated snapshots (prod)
aws rds describe-db-snapshots --db-instance-identifier infalette-prod --snapshot-type automated | jq '.DBSnapshots | length'

# Most recent snapshot age
aws rds describe-db-snapshots --db-instance-identifier infalette-prod \
  --query 'reverse(sort_by(DBSnapshots, &SnapshotCreateTime))[0].{id:DBSnapshotIdentifier,created:SnapshotCreateTime,status:Status}' --output table

# ElastiCache
aws elasticache describe-snapshots --cache-cluster-id infalette-prod | jq .

# S3 — list versions (proves versioning is live)
aws s3api list-object-versions --bucket infalette-media-prod --max-items 5
```

## 3. Restore procedure — Postgres

### 3.1 Point-in-time recovery (PITR) to new instance

```bash
RESTORE_TIME="2026-08-26T04:15:00Z"    # UTC, within retention window
NEW_ID="infalette-prod-restore-$(date +%Y%m%d%H%M)"

aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier infalette-prod \
  --target-db-instance-identifier "$NEW_ID" \
  --restore-time "$RESTORE_TIME" \
  --use-latest-restorable-time # omit --restore-time to use latest

# Wait until available ( ~10 min for t3.micro)
aws rds wait db-instance-available --db-instance-identifier "$NEW_ID"

# Point the app at the restored DB (SSM/Secrets Manager)
aws secretsmanager put-secret-value \
  --secret-id infalette/prod/DATABASE_URL \
  --secret-string "postgresql+asyncpg://infalette:<pw>@${NEW_ID}.<region>.rds.amazonaws.com:5432/infalette"

# Restart API/workers (ECS services notice Secrets Manager rotation, or force deploy)
aws ecs update-service --cluster infalette-prod --service api --force-new-deployment
```

### 3.2 Snapshot restore (full)

```bash
SNAP="rds:infalette-prod-2026-08-26-03-00"  # from §2
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier infalette-prod-restored \
  --db-snapshot-identifier "$SNAP"
```

### 3.3 Local / staging restore from `pg_dump`

```bash
pg_dump -Fc -h prod-host -U infalette infalette > infalette-$(date +%F).dump
pg_restore --clean --if-exists -h staging-host -U infalette -d infalette infalette-*.dump
# then
alembic -c packages/database/alembic.ini upgrade head
```

## 4. Restore procedure — Redis

ElastiCache restores by **creating a new replication group from snapshot**:

```bash
SNAP="infalette-prod-0001-001"   # from describe-snapshots
aws elasticache create-replication-group \
  --replication-group-id infalette-prod-restore \
  --snapshot-name "$SNAP"

# Update REDIS_URL secret and restart workers
aws secretsmanager put-secret-value --secret-id infalette/prod/REDIS_URL \
  --secret-string "redis://infalette-prod-restore.<region>.cache.amazonaws.com:6379/0"
aws ecs update-service --cluster infalette-prod --service workers --force-new-deployment
```

For non-prod, `FLUSHALL` + re-seed with `scripts/demo_seed.py` is acceptable.

## 5. Restore procedure — S3 media

*Versioning* means deletes are soft — restore a deleted key by deleting its delete-marker:

```bash
# Find delete markers
aws s3api list-object-versions --bucket infalette-media-prod --prefix media/<tenant>/ | jq '.DeleteMarkers[] | {Key,VersionId,IsLatest}'

# Remove the marker (undeletes)
aws s3api delete-object --bucket infalette-media-prod --key media/<tenant>/photo.jpg --version-id <delete-marker-id>
```

Bulk region-copy (if replication was enabled pre-incident) is via `aws s3 sync s3://infalette-media-prod s3://infalette-media-dr --delete`.

## 6. Quarterly drill checklist (30 min, non-prod)

1. `terraform apply` a throwaway `infalette-drill` env from same modules.
2. Restore the **oldest** retained snapshot (§3.2) to that env; run `alembic upgrade head` + `pytest tests/integration -q --tb=short`.
3. Restore one media key via delete-marker (§5) and verify `GET /media/{key}` signed URL.
4. Record pass/fail + wall time in `docs/runbooks/backup-restore.md` revision history below.

## 7. Escalation

* On-call: `#incidents` Slack + PagerDuty `infalette-prod`.
* If automated snapshots are missing (`describe-db-snapshots` returns 0), escalate to AWS Support **immediately** — retention misconfiguration is P1.

## Revision history

| Date | Drill result | Notes |
|---|---|---|
| 2026-08-26 | Template created | Awaiting first quarterly drill post-pilot |
