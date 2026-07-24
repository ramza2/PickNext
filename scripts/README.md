# Scripts

| Script | Purpose |
| --- | --- |
| `migrate.sh` | Apply Alembic migrations in the backend container |
| `seed.sh` | Apply migrations, then run idempotent seed |
| `analyze-legacy.sh` | Dry-run analyze `legacy-data/movie.json` → `migration-report/` |
| `import-legacy.sh` | Import `movie.json` (`dry-run` or `apply`) → `migration-report/import/` |
| `repair-legacy.sh` | Repair import data (`dry-run` or `apply`) → `migration-report/repair/` |
| `export-local-db.ps1` | Local custom-format `pg_dump` + manifest + SHA-256 (read-only) |
| `dpl3-remote-db-restore.sh` | Restore dump into fixed project `picknext-dpl3` only |
| `dpl3-remote-deploy.sh` | DPL-3 remote deploy (postgres → migrate → seed → up) |
| `dpl3-remote-inspect.sh` | DPL-3 remote inspect helpers |

Windows PowerShell 예:

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.services.seed
docker compose exec backend python -m app.scripts.analyze_legacy_movies `
  --input /app/legacy-data/movie.json `
  --report-dir /app/migration-report `
  --pretty
```