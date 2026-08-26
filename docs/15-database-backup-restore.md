# OPS-1 Database Backup & Restore

## Purpose

PickNext OPS-1 provides **full PostgreSQL database** backup download and safe restore
from Settings → 데이터 관리. This is not a per-user export.

Use cases:

- Server / Docker host migration
- Disaster recovery
- Revert after bad data changes
- Dev ↔ ops environment transfer (same schema major)

Safety is prioritized over convenience.

## Admin gate (no Migration)

OPS-1 does **not** add `users.is_admin`, roles, or RBAC tables.

Gate (both required):

```text
OPS_DATABASE_MAINTENANCE_ENABLED=true
current user.login_id == OPS_MAINTENANCE_ADMIN_LOGIN_ID
```

Backend enforces the gate on every maintenance endpoint (403 if denied).
Hiding UI alone is not security.

Do not put real admin login IDs in the repository. Configure them only in local/ops env files.

## APIs

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/api/v1/settings/database-maintenance` | Status; non-admin gets limited fields |
| POST | `/api/v1/settings/database-backup` | ZIP download (`FileResponse`) |
| POST | `/api/v1/settings/database-restore/inspect` | Multipart upload → validation DB + one-time token |
| POST | `/api/v1/settings/database-restore/execute` | Token + confirmation `"복원"` + password |

Non-admin / disabled → **403 Forbidden**.

## Backup package format

Download name:

```text
picknext-backup-YYYYMMDD-HHMMSS.zip
```

ZIP entries (only):

```text
manifest.json
database.dump
```

- `database.dump`: `pg_dump --format=custom`
- Manifest includes format version, PostgreSQL major, Alembic revision, dump SHA-256, core table counts
- Manifest never includes secrets (`POSTGRES_PASSWORD`, `SECRET_KEY`, SMTP/TMDB tokens, cookies, etc.)

### Excluded table **data** (schema still dumped)

```text
user_sessions
auth_verification_codes
```

After restore these tables are empty → all sessions/codes invalidated; users must log in again.

### Sensitive content that **is** included

User emails, login IDs, password hashes, and all content data are included (required for account migration). Store ZIP files securely.

## Restore pipeline

1. **Inspect**: ZIP security checks → SHA-256 → `pg_restore --list` → temporary validation DB restore → counts/Alembic check → drop validation DB → issue one-time restore token (TTL default 15 minutes, file-backed under temp `picknext-restore/`)
2. **Execute**: re-check token/TTL/SHA/admin/password/`복원` → staging DB restore → **safety backup** to `/app/backups/pre-restore-*.zip` → maintenance mode → dispose pool → rename swap → post-validation → drop old DB → clear token → maintenance off
3. On post-validation failure: automatic rename rollback to previous DB when possible
4. On rollback failure: keep maintenance **on**, CRITICAL log with safety backup path only (no secrets)

Compatibility (v1, strict):

- Backup format version `1`
- Same PostgreSQL major (16)
- Same Alembic revision (no auto `alembic upgrade` during restore)

## Safety backups

- Host mount: `./backups` → `/app/backups`
- Retention: `OPS_BACKUP_RETENTION` (default 5) applies only to `pre-restore-*.zip` created by OPS-1
- Existing manual backups in that directory are never deleted by OPS-1

## Maintenance mode

Process-local lock + maintenance flag (assumes **single Uvicorn worker**; default Compose command has no `--workers`).

During cutover, general `/api/v1/*` returns **503**, except:

- `/api/v1/health` (must stay 200 so Docker does not restart)
- `/api/v1/settings/database-restore/execute`

## Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `OPS_DATABASE_MAINTENANCE_ENABLED` | `false` | Master switch |
| `OPS_MAINTENANCE_ADMIN_LOGIN_ID` | empty | Operator `login_id` |
| `OPS_BACKUP_DIR` | `/app/backups` | Persistent safety backups |
| `OPS_BACKUP_RETENTION` | `5` | Keep N OPS-1 pre-restore ZIPs |
| `OPS_BACKUP_MAX_UPLOAD_BYTES` | `1073741824` | Upload cap (~1 GiB) |
| `OPS_RESTORE_TOKEN_TTL_SECONDS` | `900` | Inspect token TTL |

## PostgreSQL client

Backend image installs **PostgreSQL 16** client (`postgresql-client-16` via PGDG).  
`pg_dump` / `pg_restore` must match server major 16.

Password is passed only via child-process `PGPASSWORD` (`shell=False`).

## Ops migration notes

Restore does **not** move `.env` / `.env.dpl3` secrets. Configure secrets separately on the new host.

If restored users’ `login_id` values no longer match `OPS_MAINTENANCE_ADMIN_LOGIN_ID`, update that env key after restore (operator action).

Production compose pattern (operator-run only):

```bash
docker compose --env-file .env.dpl3 -p picknext-dpl3 -f compose.yaml -f compose.traefik.yaml up -d --build backend
```

Do not mix `compose.local.yaml` into production.

## Testing constraints

- Do not run destructive restore QA against shared DB `picknext`
- Integration swap tests require `OPS1_INTEGRATION=1` and `POSTGRES_DB` prefixed `picknext_ops1_test_`
- Never `docker compose down -v` for OPS-1 tests
