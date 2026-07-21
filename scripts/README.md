# Scripts

| Script | Purpose |
| --- | --- |
| `migrate.sh` | Apply Alembic migrations in the backend container |
| `seed.sh` | Apply migrations, then run idempotent seed |
| `analyze-legacy.sh` | Dry-run analyze `legacy-data/movie.json` → `migration-report/` |
| `import-legacy.sh` | Import `movie.json` (`dry-run` or `apply`) → `migration-report/import/` |

Windows PowerShell 예:

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.services.seed
docker compose exec backend python -m app.scripts.analyze_legacy_movies `
  --input /app/legacy-data/movie.json `
  --report-dir /app/migration-report `
  --pretty
```