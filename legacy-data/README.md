# Legacy source data (Android MovieManager backup)

Place personal backup JSON files here. They are **not** committed to Git.

## Expected files

| File | Used in phase 2 |
| --- | --- |
| `movie.json` | Yes — dry-run analysis input |
| `category.json` | Optional — mapping cross-check |
| `log.json` | No — not migrated |

## Layout

```text
legacy-data/
├─ README.md          # this file (committed)
├─ movie.json         # gitignored
└─ category.json      # gitignored
```

## Dry-run (no DB import)

From the project root (with Compose up):

```bash
docker compose exec backend python -m app.scripts.analyze_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report \
  --category-input /app/legacy-data/category.json \
  --pretty
```

Reports are written to `migration-report/` (also gitignored).
