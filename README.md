# PickNext

카테고리별로 관심 항목(영화, 드라마, 애니메이션, 예능, 만화책, 음식 등)을 기록하고 랜덤 추천받는 반응형 웹/PWA 서비스입니다.

기존 Android MovieManager와는 별개의 신규 프로젝트이며, 이번 저장소 범위는 **Backend·DB 기반 구성**까지입니다.

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
│  │  ├─ services/
│  │  └─ main.py
│  ├─ alembic/
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/          # placeholder only
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

Backend: http://localhost:8000  
Health: http://localhost:8000/api/v1/health  
OpenAPI: http://localhost:8000/docs

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

- Monorepo 골격 (frontend는 README placeholder)
- SQLAlchemy 도메인 모델 (users, categories, collections, items, recommendation_history*)
- Alembic 초기 migration
- 개발용 Seed (멱등)
- Health Check API (`GET /api/v1/health`)
- Docker Compose (`backend`, `postgres`)
- pytest 기반 검증

## 이번 범위에서 제외

- React Frontend / PWA
- 인증·로그인
- Category/Item CRUD API
- 랜덤 추천·선택·이력 API
- `movie.json` Import
- TMDB / 이미지 / Traefik / 서버 배포

## 다음 개발 단계

1. Category·Item CRUD API
2. 랜덤 추천 및 `이걸로 선택` 이력 API
3. `movie.json` legacy import
4. React + TypeScript + Vite Frontend
5. Traefik 및 운영 배포 설정

설계 문서는 `docs/`를 참고하세요.
