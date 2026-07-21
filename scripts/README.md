# Scripts

| Script | Purpose |
| --- | --- |
| `migrate.sh` | Apply Alembic migrations in the backend container |
| `seed.sh` | Apply migrations, then run idempotent seed |

Windows PowerShell 예:

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.services.seed
```
