# 05. TMDB Integration Plan

> **상태:** TMDB-1 Backend 기반 + **TMDB-2 Frontend 실검색·상세·`POST /items/from-tmdb` 등록** 완료.  
> **범위:** TMDB 기반 영화·TV 검색·상세 및 Item 등록  
> **비범위 (잔여):** Legacy 7,202건 자동 매칭·Backfill, Trailer/Watch Provider, 추천 History 연동

## 0. TMDB-1 / TMDB-2 범위 구분

| 단계 | 포함 | 제외 |
| --- | --- | --- |
| **TMDB-1 (완료)** | Settings·Secret 안전 처리, Async TMDB Client, Status/Search/Details API, 응답 정규화, Image URL, Item 외부 식별 컬럼·Partial Unique Index, Migration `0005`, Mock 테스트 | Frontend 검색 UI 연결, Item 등록 API (당시), Legacy Backfill |
| **TMDB-2 (완료)** | Frontend 검색·상세·등록 UI, `POST /items/from-tmdb`, 서버 TMDB Detail 재조회, 중복 409(`TMDB_ITEM_ALREADY_EXISTS`) | Legacy 자동 매칭 |

### 구현 API

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/api/v1/tmdb/status` | 설정·연결 상태 (`AVAILABLE` / `NOT_CONFIGURED` / `UNAVAILABLE`), Secret 미노출 |
| `GET` | `/api/v1/tmdb/search` | `query`, `media_type=all\|movie\|tv`, `page` — movie/tv만, person 제외 |
| `GET` | `/api/v1/tmdb/details/{media_type}/{tmdb_id}` | movie\|tv 상세 + credits·external_ids |
| `POST` | `/api/v1/items/from-tmdb` | TMDB Detail 재조회 후 Item 생성 (201) / 중복 409 |

### 인증·정책 (확정)

| 항목 | 정책 |
| --- | --- |
| 인증 우선순위 | `TMDB_API_READ_ACCESS_TOKEN` (Bearer) → 없으면 `TMDB_API_KEY` (`api_key` query). 동시 전송 금지 |
| `include_adult` | Backend 고정 `true`. 환경변수·Frontend Override 없음 |
| 언어 | `TMDB_LANGUAGE` (기본 `ko-KR`). Frontend Query로 변경 불가 |
| 지역 | `TMDB_REGION` (기본 `KR`). 공식 Endpoint가 지원할 때만 전달 (예: `/search/movie`) |
| 등록 여부 | `(user_id, external_source=tmdb, external_media_type, external_id)`만. 제목 Fuzzy 금지 |

### Item 외부 식별 (TMDB-1 Migration `0005_add_item_external_identity`)

| 필드 | 타입 | 비고 |
| --- | --- | --- |
| `external_source` | `VARCHAR(32)` NULL | 예: `"tmdb"` |
| `external_id` | `VARCHAR(64)` NULL | TMDB ID 문자열 |
| `external_media_type` | `VARCHAR(16)` NULL | `"movie"` \| `"tv"` |
| `original_title` | `TEXT` NULL | |
| `original_language` | `VARCHAR(16)` NULL | |
| `poster_path` / `backdrop_path` | `VARCHAR(500)` NULL | 상대 경로 |
| `external_metadata_updated_at` | timestamptz NULL | |

- Check: 세 식별 필드 모두 NULL 또는 모두 NOT NULL  
- Unique: `uq_items_user_external_identity` on `(user_id, external_source, external_media_type, external_id)` WHERE `external_id IS NOT NULL`  
- 일반 `POST/PATCH /items`는 외부 식별 필드를 받지 않음 (`extra=forbid`). 값은 TMDB-2 등록 API가 설정  
- Legacy 7,202건은 NULL 유지. Backfill·자동 매칭 없음. **실데이터 DB에는 TMDB-1에서 Migration을 적용하지 않음** (파일·격리 DB 검증만)

## 1. 기능 목적

사용자가 TMDB에서 영화(Movie) 또는 TV·드라마를 검색하고 상세정보를 확인한 뒤, 원하는 콘텐츠를 PickNext의 `PLANNED` Item으로 등록한다.

```text
영화·드라마 검색
→ 검색 결과 확인
→ 상세 미리보기
→ 앞으로 볼 항목으로 등록
→ Category 및 Collection 확인
→ 저장
```

TMDB 검색 결과는 **자동 저장하지 않는다.** 사용자가 내용을 확인하고 등록을 확정해야 한다.

검색이 실패해도 기존 PickNext 기능(목록·추천·직접 등록)은 정상 동작해야 한다.

## 2. 현재 코드·DB 영향 범위 분석

### 2.1 변경 없음 (보존)

| 영역 | 현재 상태 | TMDB 도입 시 |
| --- | --- | --- |
| Legacy Import 7,202건 | `external_*` 필드 없음 | 자동 TMDB 매칭 **하지 않음**, NULL 유지 |
| Legacy Import·보정 CLI | `import_legacy_movies`, `repair_legacy_import_data` | 변경 없음 |
| 추천 규칙 | 카테고리·상태·Collection 기반 랜덤 | TMDB 등록 Item도 동일 `items` 행이므로 규칙 동일 적용 |
| `recommendation_history` | 선택 시 snapshot 저장 | TMDB Item도 `item_id`로 연결 가능 |
| Category Seed | 10개 고정 (`seed.py`) | TMDB는 기존 Category 중에서 사용자가 선택 |
| Health API | `/api/v1/health` | TMDB 장애와 무관하게 DB 연결만 검사 |

### 2.2 확장 대상

| 영역 | 파일·위치 | 영향 |
| --- | --- | --- |
| `items` 테이블 | `backend/app/models/__init__.py`, Alembic | 외부 메타데이터 컬럼 추가 (Migration `0005` 후보) |
| Pydantic Schema | `backend/app/schemas/__init__.py` | `ItemCreate`, TMDB 전용 요청·응답 모델 추가 |
| Settings | `backend/app/core/config.py`, `.env.example` | `TMDB_*` 환경변수 추가 |
| API Router | `backend/app/api/v1/` | `external/tmdb/*`, `items/from-tmdb` 신규 |
| 서비스 계층 | `backend/app/services/` | `tmdb/` 클라이언트·변환·Category 추천·중복 검사 |
| 도메인 문서 | `docs/02-domain-model.md` | `items` 확장 필드 반영 |
| Export·Import | 미구현 | 향후 스키마에 외부 필드 포함 필요 |

### 2.3 설계 시 주의 사항 (현재 모델과의 차이)

1. **`rating` NOT NULL**  
   현재 `items.rating`은 `0.0~5.0` 필수(`Numeric(2,1)`, CheckConstraint). 기획상 TMDB 등록 시 "평점 미입력"이므로 구현 단계에서 다음 중 하나를 선택한다.
   - **권장:** `rating = 0.0`을 "미평가" 관례로 사용하고 UI에서 0.0을 미입력으로 표시
   - **대안:** Migration으로 `rating` nullable 허용 (Legacy 7,202건은 기존 값 유지)

2. **`title_snapshot` VARCHAR(300)**  
   `recommendation_history_items.title_snapshot`은 300자 제한. `items.title`은 TEXT로 확장됨(`0003`). TMDB 장제목이 snapshot에 잘릴 수 있으므로, 추천 이력 snapshot도 TEXT 확장을 후속 검토한다.

3. **제목 기반 중복과 TMDB 중복 분리**  
   Legacy Import는 `(user_id, title)` 중복 스킵 정책이 있었으나, TMDB는 `(user_id, external_source, external_media_type, external_id)`로만 중복 판정한다. 제목이 같아도 TMDB ID가 다르면 별도 Item.

4. **소프트 삭제와 중복**  
   중복 unique 인덱스는 `external_id IS NOT NULL`인 Item에 적용한다 (Hard Delete 전제; Soft Delete/`deleted_at` 조건 없음). 동일 TMDB ID 재등록은 409.

## 3. 검색 범위

### 3.1 TMDB API (향후)

| 항목 | 값 |
| --- | --- |
| 검색 엔드포인트 | `GET /search/multi` |
| 허용 `media_type` | `movie`, `tv` only (`person` 제외) |
| 언어 | `ko-KR` (`language=ko-KR`) |
| 성인 콘텐츠 | 포함 (`include_adult=true` 고정). 사용자 설정·Frontend Override 없음 |
| 실패 시 | 직접 Item 등록 UI 제공 |

### 3.2 아키텍처

```text
React Frontend
    ↓  (PickNext API만 호출)
PickNext Backend
    ↓  (TMDB_API_TOKEN 사용)
TMDB API
```

Frontend는 TMDB API Key·Token을 **절대** 보유하지 않는다.

## 4. 화면 흐름 (Frontend 계획)

```text
[검색 화면]
  검색어 입력 → 결과 목록 (movie/tv만)
  각 행: 포스터(또는 Placeholder) / 제목 / 유형 / 개봉·방영일 / already_registered 뱃지

[상세 미리보기]
  TMDB 상세 조회 → 제목·원제·줄거리·포스터·장르·국가·TMDB 평점
  already_registered 시: 현재 status, 기존 Item 상세 링크

[등록 확인]
  자동 채움: title, original_title, overview, poster_path, release_date, external_*
  사용자 확인: category_id, collection_id, progress_note, memo, 포스터 사용 여부
  Category 추천값 표시 (변경 가능, 불확실 시 미선택)

[저장]
  POST /api/v1/items/from-tmdb → PLANNED Item 생성
```

포스터 없는 Legacy Item과 TMDB Item이 같은 목록에서 자연스럽게 보이도록 **Placeholder UI**가 필요하다.

## 5. 데이터 모델 확장 계획

### 5.1 `items` 신규 컬럼

| 컬럼 | 타입 (안) | NULL | 설명 |
| --- | --- | --- | --- |
| `external_source` | `external_source` ENUM 또는 `VARCHAR` | YES | `TMDB` 또는 NULL (Legacy·직접 입력) |
| `external_id` | `INTEGER` | YES | TMDB ID (`movie.id` / `tv.id`) |
| `external_media_type` | `external_media_type` ENUM | YES | `MOVIE`, `TV`, NULL |
| `poster_path` | `VARCHAR(500)` | YES | TMDB `poster_path` (상대 경로만 저장) |
| `overview` | `TEXT` | YES | 줄거리 |
| `release_date` | `DATE` | YES | 개봉일 또는 첫 방영일 (`release_date` / `first_air_date`) |
| `original_title` | `TEXT` | YES | 원제 (`original_title` / `original_name`) |
| `external_rating` | `NUMERIC(3,1)` | YES | TMDB vote_average (선택, `items.rating`과 분리) |

### 5.2 ENUM 정의 (안)

```text
external_source: TMDB
external_media_type: MOVIE, TV
```

DB enum 이름 예: `external_source`, `external_media_type`.

### 5.3 Legacy·직접 입력 Item 기본값

```text
external_source = NULL
external_id = NULL
external_media_type = NULL
poster_path = NULL
overview = NULL
release_date = NULL
original_title = NULL
external_rating = NULL
```

기존 7,202건은 Migration 후에도 위 값이 유지된다. **자동 TMDB 매칭 없음.**

### 5.4 중복 등록 정책

동일 사용자가 같은 TMDB 콘텐츠를 중복 등록하지 않도록 다음 조합으로 판정한다.

```text
(user_id, external_source, external_media_type, external_id)
```

- **부분 Unique Index**:  
  `WHERE external_id IS NOT NULL`
- 검색·상세 응답에 `already_registered`, `existing_item_id`, `existing_item_status` 포함
- 제목만 같은 Legacy Item과는 **자동 중복 처리하지 않음**
- 중복 등록 API 요청 시 `409 Conflict` 반환
- Item Hard Delete 후 동일 TMDB ID 재등록은 **새 행으로 허용** (행이 없으므로 Unique 충돌 없음)

### 5.5 등록 기본값

| 필드 | TMDB 등록 시 |
| --- | --- |
| `status` | `PLANNED` |
| `rating` | `0.0` (미평가 관례, UI에서 미입력 표시) |
| `external_source` | `TMDB` |
| `external_id` | TMDB ID |
| `external_media_type` | `MOVIE` 또는 `TV` |

자동 입력 후보: 한국어 제목, 원제, 포스터 경로, 줄거리, 개봉·방영일, TMDB ID, 유형, (선택) TMDB 평점 → `external_rating`

사용자 확인 항목: 제목, Category, Collection, Progress Note, 메모, 포스터 사용 여부

**PickNext 사용자 평점(`rating`)과 TMDB 평점(`external_rating`)은 분리한다.**

## 6. Category 처리

TMDB Movie·TV 유형을 PickNext Category에 1:1로 매핑하지 않는다.

| TMDB 유형 | PickNext Category 후보 |
| --- | --- |
| Movie | 영화, 애니 영화 |
| TV | 한국드라마, 일본드라마, 미국드라마, 중국드라마, 애니메이션, 예능 |

### 6.1 추천 규칙 (휴리스틱, 구현 시 서비스로 분리)

| 조건 | 추천 Category |
| --- | --- |
| `media_type=movie` + 애니메이션 장르 | 애니 영화 |
| `media_type=movie` (기본) | 영화 |
| `media_type=tv` + `origin_country`에 `KR` | 한국드라마 |
| `media_type=tv` + `JP` + 애니메이션 장르 | 애니메이션 |
| `media_type=tv` + `JP` | 일본드라마 |
| `media_type=tv` + `US` | 미국드라마 |
| `media_type=tv` + `CN` / `TW` / `HK` | 중국드라마 |
| `media_type=tv` + Reality/토크 장르 | 예능 |
| 불확실 | `suggested_category_id = null` → 사용자 필수 선택 |

저장 전 사용자가 Category를 반드시 확인·변경한다. API는 `category_id`를 요청 본문에서 받는다.

## 7. 포스터 처리

- 초기: 이미지 파일을 PickNext 서버에 저장하지 않고 `poster_path`만 DB에 보관
- 표시: Backend 설정으로 `TMDB_IMAGE_BASE_URL` (예: `https://image.tmdb.org/t/p/w500`) 제공, Frontend가 조합
- `use_poster=false` 요청 시 `poster_path`를 NULL로 저장 가능 (구현 시 옵션 필드)
- 포스터 없음: Placeholder UI

## 8. API Key 보안

### 8.1 환경변수

| 변수 | 설명 |
| --- | --- |
| `TMDB_API_READ_ACCESS_TOKEN` | 1순위 인증 (Bearer). SecretStr |
| `TMDB_API_KEY` | 2순위 인증 (`api_key` query). Token과 동시 미사용 |
| `TMDB_LANGUAGE` | 기본 `ko-KR` |
| `TMDB_REGION` | 기본 `KR` (지원 Endpoint만) |
| `TMDB_API_BASE_URL` | 기본 `https://api.themoviedb.org/3` |
| `TMDB_REQUEST_TIMEOUT_SECONDS` | 기본 `10` |
| `TMDB_CONFIGURATION_TTL_SECONDS` | Configuration 캐시 (기본 86400) |
| `TMDB_STATUS_TTL_SECONDS` | Status 캐시 (기본 60) |
| `TMDB_POSTER_SIZE` / `TMDB_BACKDROP_SIZE` / `TMDB_PROFILE_SIZE` | 기본 `w500` / `w780` / `w185` |

`include_adult`는 코드 상수로 `true` 고정. 환경변수로 두지 않는다.

토큰·키가 모두 없으면: `/tmdb/status`는 HTTP 200 + `NOT_CONFIGURED`, 검색·상세는 `503` / `TMDB_NOT_CONFIGURED`. Health·Items·Collections는 정상.
### 8.2 오류 처리

- TMDB 타임아웃·5xx: 사용자에게 일반 메시지 ("검색 서비스를 일시적으로 사용할 수 없습니다")
- TMDB 원문 오류·스택을 Frontend에 노출하지 않음
- 검색 화면에 재시도 버튼

## 9. 향후 Backend API 계획

모든 경로는 `API_V1_PREFIX` (`/api/v1`) 하위. 인증 도입 전까지는 Seed 사용자 또는 향후 세션 사용자 기준 `user_id` 스코프.

### 9.1 TMDB 프록시 (읽기 전용) — TMDB-1 구현

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/tmdb/status` | 연결 상태 |
| `GET` | `/tmdb/search` | `query`, `media_type=all\|movie\|tv`, `page` |
| `GET` | `/tmdb/details/{media_type}/{tmdb_id}` | movie\|tv 상세 |

검색·상세 응답은 PickNext DTO이며 `registered` / `registered_item_id`를 포함한다. Image URL은 `/configuration` 기반(캐시)으로 Backend가 조합한다.

### 9.2 등록 — TMDB-2 (완료)

| Method | Path | 설명 |
| --- | --- | --- |
| `POST` | `/items/from-tmdb` | 서버가 TMDB Detail을 재조회한 뒤 Item 생성. 클라이언트 `external_*` 위조 무시 (`extra=forbid`) |

**요청 (`ItemFromTmdbCreate`):** `media_type`, `tmdb_id`, `category_id` 필수. 선택: `title`(override), `collection_id`, `status`, `rating`, `progress_note`, `memo`.

**정책:**
- 제목: Form override 가능. 미전달 시 TMDB `ko-KR` title/name
- 저장 필드: `external_source=tmdb`, `external_id`, `external_media_type`, `original_*`, `poster_path`, `backdrop_path`, `external_metadata_updated_at` (overview/release_date DB 컬럼 없음)
- 중복: `409` + `detail: { code: "TMDB_ITEM_ALREADY_EXISTS", existing_item_id }` (pre-check + Unique race)
- 신규 Migration 없음 (`0005` 사용)

### 9.3 응답 모델 (안)

**검색 결과 항목 (`TmdbSearchResultItem`):**

```json
{
  "external_id": 157336,
  "media_type": "movie",
  "title": "인터스텔라",
  "original_title": "Interstellar",
  "overview": "...",
  "poster_path": "/abc.jpg",
  "release_date": "2014-11-06",
  "origin_countries": ["US"],
  "genres": ["SF", "드라마"],
  "external_rating": 8.4,
  "already_registered": false,
  "existing_item_id": null,
  "existing_item_status": null
}
```

**상세 (`TmdbDetailResponse`):** 위 필드 + `runtime` / `number_of_seasons` 등 UI에 필요한 최소 필드.

**등록 요청 (`ItemFromTmdbCreate`):**

```json
{
  "media_type": "movie",
  "external_id": 157336,
  "category_id": "uuid",
  "title": "인터스텔라",
  "collection_id": null,
  "progress_note": null,
  "memo": null,
  "use_poster": true
}
```

서버는 요청의 `external_id`로 TMDB 상세를 재조회하거나, 클라이언트가 보낸 스냅샷과 교차 검증한다(구현 시 **서버 재조회 권장**).

### 9.4 HTTP 상태 코드 (안)

| 코드 | 상황 |
| --- | --- |
| `200` | 검색·상세 성공 |
| `201` | Item 등록 성공 |
| `409` | 동일 TMDB 콘텐츠 이미 등록됨 |
| `422` | Category 미선택 등 검증 실패 |
| `502` / `503` | TMDB 장애·타임아웃 |
| `404` | TMDB ID 없음 |

## 10. Alembic Migration (`0005_add_item_external_identity`)

> Revises: `0004_remove_item_soft_delete`  
> **실데이터(로컬 7202 / DPL-3)에는 TMDB-1에서 적용하지 않음.** 격리 DB에서 upgrade·downgrade·재upgrade 검증.

구현:

```text
- nullable columns: external_source, external_id, external_media_type,
  original_title, original_language, poster_path, backdrop_path,
  external_metadata_updated_at
- CHECK ck_items_external_identity_all_or_none
- UNIQUE INDEX uq_items_user_external_identity
  ON (user_id, external_source, external_media_type, external_id)
  WHERE external_id IS NOT NULL
```

문자열 식별자·소문자 `tmdb` / `movie` / `tv`를 사용한다 (초기 ENUM 초안은 폐기).

Hard Delete 전제라 Soft Delete partial 조건은 사용하지 않는다.


## 11. Export·Import 영향

향후 사용자 데이터 Export JSON/CSV에 다음 필드를 포함한다.

```text
external_source
external_id
external_media_type
poster_path
overview
release_date
original_title
external_rating  (도입 시)
```

복원 시 TMDB API 재호출 없이 Export 데이터만으로 Item 복원 가능해야 한다. 포스터 **파일**은 Export에 포함하지 않고 `poster_path`만 저장한다.

Legacy Import 경로와 TMDB 등록 경로는 별도이며, Import 포맷 변경은 하지 않는다.

## 12. 출처 표시

TMDB 데이터·이미지를 사용하는 화면 Footer 등에 다음 문구 표시 가능하도록 설계한다.

```text
This product uses the TMDB API but is not endorsed or certified by TMDB.
```

## 13. 구현 순서 (권장)

| 단계 | 작업 | 산출물 |
| --- | --- | --- |
| 1 | Migration `0005` + SQLAlchemy 모델·Enum + Pydantic 스키마 | DB·모델 |
| 2 | `Settings` TMDB 환경변수, `.env.example` | 설정 |
| 3 | `app/services/tmdb/client.py` — HTTP 클라이언트, 타임아웃, 오류 래핑 | 서비스 |
| 4 | `app/services/tmdb/mapper.py` — TMDB → PickNext DTO 변환 | 서비스 |
| 5 | `app/services/tmdb/category_suggest.py` — Category 휴리스틱 | 서비스 |
| 6 | `GET /external/tmdb/search`, `movie/{id}`, `tv/{id}` | API |
| 7 | 중복 검사 + `POST /items/from-tmdb` | API |
| 8 | 단위·통합 테스트 (TMDB mock) | 테스트 |
| 9 | Frontend 검색·상세·등록 UI | UI |
| 10 | Export·Import 필드 확장 | 후속 |

**선행 조건:** Item CRUD API 기반이 있으면 등록·중복 UX 연결이 수월하나, `from-tmdb` 단독 엔드포인트로도 시작 가능.

## 14. 테스트 계획 (구현 단계)

### 14.1 Migration·모델

- 신규 컬럼 nullable, Legacy 행 NULL 유지
- partial unique index: 동일 TMDB ID 중복 INSERT 차단
- `external_source=TMDB` 시 필수 필드 검증
- downgrade 안전

### 14.2 TMDB 클라이언트 (mock)

- `/search/multi` 응답에서 `movie`/`tv`만 반환, `person` 제외
- `language=ko-KR`, `include_adult=true` 파라미터 고정 전달 (모든 search/movie·search/tv·search/multi)
- 타임아웃 시 구조화된 예외
- 5xx 응답 시 사용자 안전 메시지

### 14.3 검색·상세 API

- PickNext DTO 변환 필드 누락 없음
- 이미 등록된 `external_id`에 `already_registered=true`
- TMDB 토큰 미설정 시 기존 Health·다른 API 무영향

### 14.4 등록 API

- `PLANNED` 생성, `rating=0.0`
- Category 사용자 지정 필수
- 중복 등록 `409`
- 제목만 같은 Legacy Item과 별도 등록 허용
- `use_poster=false` 시 `poster_path` NULL

### 14.5 회귀

- Legacy 7,202건 수·상태·Category 분포 불변
- 추천 후보 쿼리(존재 Item 전체)에 TMDB Item 포함 정상
- Import·보정 CLI 무변경

## 15. TMDB-2 이후 잔여

- Legacy 데이터 TMDB 자동 매칭·Backfill
- 기존 7,202 Item 수정
- 검색·상세 결과 Cache / Redis
- Trailer·Watch Provider·추천 History
- 실데이터 DB에 대한 등록 Live Smoke (테스트는 MockTransport·격리 Fixture만)

## 16. 관련 문서

- [01-product-scope.md](./01-product-scope.md) — 서비스 범위
- [02-domain-model.md](./02-domain-model.md) — 도메인 모델 (확장 예정 필드)
- [04-legacy-migration.md](./04-legacy-migration.md) — Legacy Import·보정 (변경 없음)
