# PickNext

카테고리별로 관심 항목(영화, 드라마, 애니메이션, 예능, 만화책, 음식 등)을 기록하고 랜덤 추천받는 반응형 웹/PWA 서비스입니다.

기존 Android MovieManager와는 별개의 신규 프로젝트입니다.  
현재 저장소 범위는 **Backend·DB 기반 구성**과 **legacy `movie.json` Dry-run 분석 도구**까지입니다.

## 기술 스택

- Python 3.12
- FastAPI
- PostgreSQL 16
- SQLAlchemy 2.x
- Alembic
- Pydantic 2
- pytest
- Docker Compose

패키지 관리는 `backend/pyproject.toml` 하나로 통일합니다. Frontend(React + TypeScript + Vite)와 Traefik은 이후 단계에서 추가합니다.

## 디렉터리 구조

```text
PickNext/
├─ backend/
│  ├─ app/
│  │  ├─ api/v1/
│  │  ├─ core/
│  │  ├─ db/
│  │  ├─ models/
│  │  ├─ schemas/
│  │  ├─ scripts/       # dry-run CLI 등
│  │  ├─ services/
│  │  │  └─ legacy/     # movie.json 분석·분류
│  │  └─ main.py
│  ├─ alembic/
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/          # Figma 기준선 + 구조 준비 완료, 읽기 API 연동 전
├─ legacy-data/       # 개인 JSON (*.json은 gitignore)
├─ migration-report/  # Dry-run 결과 (gitignore)
├─ scripts/
├─ infra/
├─ docs/
├─ compose.yaml
├─ .env.example
└─ README.md
```

## 빠른 시작

```bash
cp .env.example .env
# 필요 시 .env의 비밀번호·SECRET_KEY를 변경

docker compose up --build
```

Backend: http://localhost:${BACKEND_PORT:-8000}  
Health: http://localhost:${BACKEND_PORT:-8000}/api/v1/health  
OpenAPI: http://localhost:${BACKEND_PORT:-8000}/docs

로컬에 PostgreSQL 등이 이미 `5432`/`8000`을 사용 중이면 `.env`의 `POSTGRES_PUBLISH_PORT`, `BACKEND_PORT`를 빈 포트로 변경하세요.

종료:

```bash
docker compose down
```

볼륨까지 삭제하려면:

```bash
docker compose down -v
```

## Alembic Migration

빈 DB에 스키마를 적용합니다.

```bash
docker compose exec backend alembic upgrade head
```

또는:

```bash
bash scripts/migrate.sh
```

현재 revision: `0001_initial`

## Seed

개발용 사용자 1명과 기본 카테고리 10개를 멱등하게 생성합니다.

```bash
docker compose exec backend python -m app.services.seed
```

또는:

```bash
bash scripts/seed.sh
```

Seed 사용자 기본값(`.env`로 변경 가능):

| 변수 | 기본값 |
| --- | --- |
| `SEED_USER_EMAIL` | `dev@picknext.local` |
| `SEED_USER_DISPLAY_NAME` | `Dev User` |
| `SEED_USER_PASSWORD` | `dev-password-change-me` |

같은 명령을 여러 번 실행해도 카테고리는 중복 생성되지 않습니다.

## Legacy Dry-run (movie.json 분석)

실제 DB Import는 **수행하지 않습니다.** `movie.json`을 읽어 변환 가능 여부와 `series` 분류 보고서만 생성합니다.

1. `legacy-data/movie.json` 배치 (`legacy-data/*.json`은 gitignore)
2. Compose 기동 후:

```bash
docker compose exec backend python -m app.scripts.analyze_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report \
  --category-input /app/legacy-data/category.json \
  --pretty
```

결과는 `migration-report/`에 저장됩니다 (`summary.json`, 분류 CSV, `normalized-preview.json` 등).  
상세 정책·분류 기준은 [`docs/04-legacy-migration.md`](docs/04-legacy-migration.md)를 참고하세요.

## Legacy Import (movie.json → PostgreSQL)

Dry-run 검토 후 확정된 정책으로 실제 Import합니다.

**확정 정책 요약**

| 항목 | 처리 |
| --- | --- |
| 카테고리 누락 6건 | Import 제외 (`SKIPPED_MISSING_CATEGORY`) |
| 중복 제목 5건 | 그룹당 1건만 Import (`SKIPPED_DUPLICATE_TITLE`) |
| Ambiguous 12건 | Item은 Import, series는 폐기 (Collection/Progress NULL) — Import 대상은 **11건** (1건은 카테고리 누락과 겹침) |
| 예상 최종 Item | **7,202건** (`7213 - 6 - 5`) |

중복 선정 우선순위: `COMPLETED` → 높은 평점 → 최신 `updated_at` → 큰 `source_id`

1. Migration 적용 (`0002_legacy_import` 포함)
2. Seed 사용자·카테고리 존재 확인
3. Dry-run으로 건수 확인:

```bash
docker compose exec backend python -m app.scripts.import_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/import \
  --dry-run \
  --pretty
```

4. 실제 Import:

```bash
docker compose exec backend python -m app.scripts.import_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/import \
  --apply \
  --pretty
```

재실행은 동일 파일 SHA-256 기준으로 차단됩니다. 개발환경에서만 `--reset-imported-data --apply`로 이전 Import 데이터를 삭제한 뒤 재실행할 수 있습니다.

> **주의:** Import 후 `docker compose down -v`를 실행하면 PostgreSQL 볼륨이 삭제되어 Import 데이터가 함께 사라집니다.

## Legacy Import 데이터 보정 (3.5차)

Import를 **재실행하지 않고** 기존 7,202개 Item을 유지한 채 제한적으로 보정합니다.

| 보정 항목 | 내용 |
| --- | --- |
| `items.title` | `VARCHAR(300)` → `TEXT` (Migration `0003_legacy_data_repairs`) |
| source_id 2209 | 잘린 제목을 `movie.json` 원본 전체 제목으로 복구 |
| Collection 전환 | `007 시리즈`, `47미터`, `28일 후`, `007 북경특급`, `99.9~형사 전문 변호사~` — `progress_note` → Collection 연결 |

추가 후보(`additional-collection-candidates.csv`)는 보고서만 생성하며 자동 변경하지 않습니다. 보고서는 `migration-report/repair/runs/{timestamp}-{dry-run|apply}/`에 실행별로 보존됩니다.

```bash
# Migration 적용 후 Dry-run
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.repair_legacy_import_data \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/repair \
  --dry-run \
  --pretty

# 실제 보정
docker compose exec backend python -m app.scripts.repair_legacy_import_data \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/repair \
  --apply \
  --pretty
```

보정 CLI는 멱등합니다. 재실행 시 이미 보정된 항목은 `already_repaired`로 기록됩니다.

> **금지:** `docker compose down -v`, `--reset-imported-data`, Import 전체 재실행

## 테스트

PostgreSQL이 기동되어 있고 Migration이 적용된 상태에서 실행합니다.

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend pytest -q
```

로컬에서 직접 실행하려면 `backend`에서 의존성을 설치한 뒤 `.env`의 DB 접속 정보를 맞춥니다.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## 환경변수

| 변수 | 설명 |
| --- | --- |
| `APP_NAME` | 앱 이름 |
| `APP_ENV` | 환경 (`development` 등) |
| `DEBUG` | FastAPI debug |
| `LOG_LEVEL` | 애플리케이션 로그 레벨 |
| `SQL_ECHO` | SQLAlchemy SQL 로그 |
| `API_V1_PREFIX` | API prefix (기본 `/api/v1`) |
| `CORS_ORIGINS` | 쉼표 구분 CORS origin |
| `SECRET_KEY` | 비밀키 (커밋 금지, 운영에서 교체) |
| `POSTGRES_HOST` | DB 호스트 |
| `POSTGRES_PORT` | DB 포트 |
| `POSTGRES_DB` | DB 이름 |
| `POSTGRES_USER` | DB 사용자 |
| `POSTGRES_PASSWORD` | DB 비밀번호 |
| `DATABASE_URL` | 선택. 설정 시 개별 `POSTGRES_*`보다 우선 |
| `BACKEND_PORT` | Backend 노출 포트 |
| `POSTGRES_PUBLISH_PORT` | PostgreSQL 노출 포트 |
| `SEED_USER_*` | Seed 사용자 정보 |

`.env`는 커밋하지 않습니다. `.env.example`만 저장소에 포함합니다.

## 현재 구현 범위

- Monorepo 골격 + Figma Make Frontend 기준선
- SQLAlchemy 도메인 모델, Alembic Migration (`0001`~`0003`)
- 개발용 Seed (멱등), Health Check API
- Docker Compose (`backend`, `postgres`)
- Legacy Dry-run / Import / 보정 CLI
- **Category·Item 읽기 API** (`GET /summary`, `/categories`, `/items`, `/items/{id}`)
- Frontend Phase B-1 구조 준비 (Proxy·API Client·Mock/Layout 분리, 화면은 아직 Mock)

## 이번 범위에서 제외

- Frontend 읽기 API 화면 연동 (Phase B-2)
- 인증·로그인
- Category/Item/Collection 쓰기 API
- 랜덤 추천·선택·이력 API
- TMDB API 실제 연동 (기획 문서만 반영)
- Traefik / 서버 배포

## 다음 개발 단계

1. Frontend Phase B-2 읽기 API 점진 연결 (`docs/06-frontend-integration-plan.md`)
2. Category·Item·Collection CRUD API
3. 랜덤 추천 및 `이걸로 선택` 이력 API
4. TMDB Migration·검색·등록 Backend
5. Traefik 및 운영 배포 설정

설계 문서는 `docs/`를 참고하세요.

| 문서 | 내용 |
| --- | --- |
| `docs/01-product-scope.md` | 서비스 범위 |
| `docs/02-domain-model.md` | 도메인 모델 |
| `docs/03-recommendation-rules.md` | 추천 규칙 |
| `docs/04-legacy-migration.md` | Legacy Import·보정 |
| `docs/05-tmdb-integration-plan.md` | TMDB 검색·등록 기획 |
| `docs/06-frontend-integration-plan.md` | Figma Frontend 분석·API 연동 계획 |
| `docs/07-read-api-contract.md` | Category·Item 조회 API 계약·구현 (Phase A-1) |
