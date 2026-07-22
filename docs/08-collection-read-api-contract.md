# 08. Collection 읽기 API 계약

> **상태:** **Backend 구현 완료 · Frontend 목록 연동 완료 · Frontend 상세 연동 대기**  
> **범위:** Collection 목록·상세 읽기 API 요청·응답·정책, Query 권장 구조, 테스트, Backend 구현, Frontend 목록 연동  
> **비범위:** Frontend 상세·Item 연동, Migration, Index 추가, 쓰기 API

검증 일시: 2026-07-22 (개발 PostgreSQL `picknext`, 읽기 전용).  
구현 검증: 2026-07-22 — 자동 테스트 + OpenAPI + Seed Smoke Test 완료.  
Frontend 목록 연동: 2026-07-22 — B-3a (`useCollectionsReadData`, CollectionsPage).

근거: SQLAlchemy Model, Alembic `0001`/`0003`, 실DB `\d`·프로파일·`EXPLAIN ANALYZE`, Frontend `CollectionsPage` JSX/Mock 타입, 기존 Item/Category 읽기 API 패턴.

관련 문서: [02-domain-model](./02-domain-model.md), [03-recommendation-rules](./03-recommendation-rules.md), [06-frontend-integration-plan](./06-frontend-integration-plan.md), [07-read-api-contract](./07-read-api-contract.md).

### Frontend 구현 현황 (B-3a)

| 항목 | 상태 |
| --- | --- |
| Collection 목록 `GET /collections` | **연동 완료** |
| 이름 검색 · Offset 페이지네이션 | **연동 완료** |
| 다중 Category Badge · 진행률 FE 계산 | **연동 완료** |
| `averageRating` | 항상 `null` 표시 (`—`), N+1 호출 없음 |
| Collection 상세 · 소속 Item | **대기 (B-3b)** — 선택 시 목록 메타만 표시, Mock Item 혼합 금지 |
| 구현 파일 | `frontend/src/api/catalog.ts` `getCollections`, `hooks/useCollectionsReadData.ts`, `mappers/collections.ts`, `App.tsx` CollectionsPage |

Backend 최종 계약(본 문서 §5~§12)은 변경하지 않는다.

---

## 0. Backend 구현 요약

### 실제 Endpoint

```http
GET /api/v1/collections
GET /api/v1/collections/{collection_id}
```

소속 Item은 기존 `GET /api/v1/items?collection_id={id}&sort=title&order=asc` 사용.

### 실제 구현 파일

| 역할 | 경로 |
| --- | --- |
| Router | `backend/app/api/v1/collections.py` |
| Router 등록 | `backend/app/api/v1/__init__.py` |
| Service | `backend/app/services/catalog.py` (`list_collections`, `get_collection_detail`, 집계 헬퍼) |
| Schema | `backend/app/schemas/__init__.py` (`CollectionCategoryCount`, `CollectionResponse`, `CollectionListResponse`, `CollectionSort`) |
| 테스트 | `backend/tests/test_collections_read_api.py` |

### 실제 Query 구조

목록 요청당 고정 Query 수 (페이지 Collection 개수와 무관):

1. 필터·정렬·`COUNT` (total)
2. 필터·정렬·`OFFSET/LIMIT` (페이지 Collection 행)
3. 페이지 ID `IN (...)` 상태 집계 (`item_count` / `planned_count` / `completed_count`)
4. 페이지 ID `IN (...)` Category 집계 (`sort_order`, `name` 정렬)

- `category_id` / `status` / 복합 필터: **단일 `EXISTS`** (동일 Item AND)
- `item_count` / `completed_count` 정렬: 활성 Item 집계 subquery `LEFT JOIN` + `COALESCE(..., 0)`
- 상세: 소유권 조회 1회 + 동일 배치 집계 헬퍼 `_collection_dicts` 재사용
- N+1: Relationship lazy load 순회 없음 (테스트 Query ≤ 4)

### 테스트 범위

`test_collections_read_api.py`: 사용자 범위·404/422, 빈 Collection, Soft Delete, 단일·혼재 Category, Status·복합 필터(집계 비축소), 검색 Escape, Validation, 페이지네이션, 전 정렬, ID 보조 정렬, N+1, OpenAPI.

### 검증 결과

| 검증 | 결과 |
| --- | --- |
| `pytest tests/test_collections_read_api.py tests/test_read_api.py` | 통과 |
| `pytest` 전체 | **89 passed** |
| Ruff (구현·테스트 파일) | All checks passed |
| OpenAPI | `/collections`, `/collections/{collection_id}`, Enum params, Schema 노출 |
| Seed Smoke | total=249, 검색·Category(185)·Status(149)·복합(135), `item_count` 정렬(드래곤볼 29), 상세 categories 합=29, page 초과 빈 목록, 스타워즈 필터 후에도 `item_count=9` |

### 계약과 구현 차이

```text
확정 계약과 구현 차이 없음
```

---

## 1. 검증 기준과 근거

| 항목 | 근거 |
| --- | --- |
| DB 구조 | `backend/app/models/__init__.py`, `alembic/versions/0001_initial.py`, 실DB `\d collections` / `\d items` |
| Soft Delete | Item `deleted_at`만 존재. Collection soft delete 컬럼 없음 |
| 실데이터 | Seed `SEED_USER_EMAIL=jchramza@gmail.com` 범위, SELECT만 |
| Frontend | `frontend/src/app/App.tsx` `CollectionsPage`, `types/mock.ts`, `mocks/data.tsx` |
| Backend 패턴 | `services/catalog.py`, `api/v1/items.py`·`categories.py`, `schemas`, `tests/test_read_api.py` |
| 계약 | 사용자 확정안 (본 문서 §5~§12). A/B 재선택 없음 |

문서와 코드가 다르면 **실제 코드·Migration·DB를 우선**한다. 차이는 §16에 기록한다.

---

## 2. 실제 DB 구조

### 2.1 `collections`

| 컬럼 | 타입 | NULL | 비고 |
| --- | --- | --- | --- |
| `id` | UUID | NO | PK, `gen_random_uuid()` |
| `user_id` | UUID | NO | FK → `users.id` **ON DELETE RESTRICT** |
| `name` | VARCHAR(200) | NO | |
| `created_at` | timestamptz | NO | `now()` |
| `updated_at` | timestamptz | NO | `now()`; ORM `onupdate=func.now()` |

**없음:** `category_id`, `deleted_at`, soft delete 관련 컬럼.

**제약·인덱스**

- PK: `collections_pkey`
- Unique: `uq_collections_user_id_name` `(user_id, name)`
- Index: `ix_collections_user_id`

**관계**

- `User` 1:N `Collection`
- `Collection` 1:N `Item` (`items.collection_id` nullable)
- `Collection` 1:N `RecommendationHistory` (`ON DELETE SET NULL`)
- `LegacyImportCollection` → Collection (`ON DELETE CASCADE`)

### 2.2 `items` (Collection 관련)

| 항목 | 실제 |
| --- | --- |
| `collection_id` | UUID NULL, FK → `collections.id` **ON DELETE RESTRICT** |
| Index | `ix_items_collection_id` (non-unique) |
| `deleted_at` | timestamptz NULL — Item soft delete |
| Soft-delete 부분 Unique Index | **없음** |
| Soft-delete 부분 Index | `ix_items_active` `(user_id, category_id) WHERE deleted_at IS NULL` — **non-unique** |
| `title` | TEXT (`0003`에서 VARCHAR(300) → TEXT) |

### 2.3 Collection 삭제 시 Item 처리

- DB: **RESTRICT** — 소속 Item( soft-deleted 포함, FK가 남아 있으면)이 있으면 Collection hard delete 불가.
- Frontend 삭제 다이얼로그 문구(“연결만 해제”)는 **쓰기 정책 희망 문구**이며 현재 FK와 불일치. 읽기 계약 범위 밖 (§17).

### 2.4 Item 수정 시 Collection `updated_at`

- DB trigger: **없음**
- ORM: Collection 행을 갱신할 때만 `updated_at` 변경
- Item INSERT/UPDATE/ soft delete만으로는 Collection `updated_at`이 **자동 갱신되지 않음**
- 읽기 정렬·필드는 확정 계약대로 **Collection 자체 `updated_at`만** 사용한다. `MAX(items.updated_at)`은 사용하지 않는다.

---

## 3. 실데이터 프로파일 (Seed 사용자)

활성 Item: `Item.deleted_at IS NULL`. 현재 soft-deleted Item **0건**.

### 3.1 Collection 전체

| 지표 | 값 |
| --- | ---: |
| 전체 Collection | **249** |
| Item 없는 Collection | **0** |
| 활성 Item 있는 Collection | **249** |
| 중복 이름 그룹 | **0** (`uq`와 일치) |
| 이름 길이 min / max / avg | **1 / 15 / 5.04** (`char_length`) |
| 활성 Item 중 Collection 연결 | **845 / 7202** |

### 3.2 Collection별 활성 Item 규모

| 지표 | 값 |
| --- | ---: |
| min | 2 |
| max | **29** (드래곤볼) |
| avg | 3.39 |
| median | 2 |
| p90 | 6 |
| p95 | 7 |
| > 25 | **2** (드래곤볼 29, 건담 27) |
| > 50 | 0 |
| > 100 | 0 |

**Item 수 상위 20**

| name | count |
| --- | ---: |
| 드래곤볼 | 29 |
| 건담 | 27 |
| 기묘한 이야기 | 22 |
| 007 시리즈 | 15 |
| 스타워즈 | 9 |
| 스파이더맨 | 9 |
| 엑스맨 | 9 |
| 패트레이버 | 9 |
| 사탄의 인형 | 8 |
| 사형참극 | 8 |
| 토미에 | 8 |
| 강철의 연금술사 | 7 |
| 고질라 | 7 |
| 기니어 피그 | 7 |
| 레지던트 이블 | 7 |
| 록키 | 7 |
| 분노의 질주 | 7 |
| 슈퍼맨 | 7 |
| 학교 | 7 |
| 겟타로보 | 6 |

### 3.3 상태 분포 (Collection 분류)

| 분류 | 건수 |
| --- | ---: |
| 활성 Item 없음 | 0 |
| 전부 PLANNED | 100 |
| 전부 COMPLETED | 87 |
| 상태 혼합 | 62 |
| **합계** | **249** |

### 3.4 Category 분포

| 지표 | 값 |
| --- | ---: |
| 단일 Category Collection | **231** |
| Category 혼재 | **18** |
| Category 0 (빈 Collection) | 0 |
| 최대 고유 Category 수 | **3** |

**혼재 예시 10**

| name | categories | items |
| --- | ---: | ---: |
| 드래곤볼 | 3 | 29 |
| 강철의 연금술사 | 3 | 7 |
| 레지던트 이블 | 3 | 7 |
| 건담 | 2 | 27 |
| 스타워즈 | 2 | 9 |
| 스파이더맨 | 2 | 9 |
| 패트레이버 | 2 | 9 |
| 고질라 | 2 | 7 |
| 오오쿠 | 2 | 6 |
| 교향시편 에우레카 7 | 2 | 4 |

**최대 혼재 상세 (드래곤볼):** 애니메이션 13 + 애니 영화 9 + 만화책 7 = 29.

대표 Category는 저장·추론하지 않는다. 계약의 `categories[]`가 이 분포와 맞다.

### 3.5 날짜

| 지표 | 값 |
| --- | --- |
| `created_at` 범위 | 2026-07-21 06:53:28Z ~ 07:52:53Z |
| `updated_at` 범위 | 동일 |
| Item `updated_at` > Collection `updated_at` | **현재 0건** |

현재 seed는 import 직후라 stale 사례가 없으나, trigger/자동 갱신 부재로 **쓰기 API 도입 후 stale은 정상적으로 발생 가능**. 계약은 이를 허용하고 Collection `updated_at`만 사용한다.

---

## 4. Frontend 화면 요구 (현황 vs 계약)

현재 Collection은 **Mock 전용**. API 연동은 본 단계 비범위.

### 4.1 목록 (`CollectionsPage`, `sel === null`)

| 표시/UI | Mock 소스 | 확정 API |
| --- | --- | --- |
| 이름 | `name` | `name` |
| Category 뱃지 | **단일** `categoryId` slug | **`categories[]`** (혼재 가능) |
| Item 수·예정·완료 | `itemCount`/`plannedCount`/`completedCount` | 동일 의미 필드 |
| 진행률 | FE 계산 `completed/itemCount` | FE 계산 (API에 `completion_rate` 없음) |
| 평균 평점 | `avgRating` optional | **API 미포함** |
| 최근 수정일 | Mock `updatedAt` 있으나 **목록 UI 미표시** | 응답에 `updated_at` (정렬용) |
| Poster Preview | **없음** | **없음** |
| 검색 | 이름 `includes` | `search` (이름 ILIKE) |
| Category/Status 필터 UI | **없음** | API는 `category_id`/`status` 지원 (FE는 후속) |
| 정렬 UI | **없음** | API 기본 `updated_at desc` |
| 페이지네이션 | 전체 그리드 (8 Mock) | Offset (`page`/`page_size`) |

### 4.2 인라인 상세 (`sel` 설정 시 동일 컴포넌트)

| 표시/UI | 현황 | 확정 연동 |
| --- | --- | --- |
| 전환 | `useState<Collection\|null>` 인라인 | 동일 UX 유지 가능 |
| 이름·카운트·진행률 | Mock Collection | `GET /collections/{id}` |
| Category | 단일 뱃지 | `categories[]` 표시로 확장 필요 (연동 시) |
| avgRating | 표시 | API 미제공 → 연동 시 제거 또는 후속 |
| Item 목록 | `ITEMS.filter(collectionId)` **전체 스크롤**, pagination 없음 | `GET /items?collection_id=&sort=title&order=asc` **기본 page_size** |
| Item 필드 | title, status, progressNote, rating, Poster | Item List API 필드 |
| 버튼 | Shuffle/Edit/삭제, TMDB추가/직접추가, 완료/제거 | 읽기 연동 범위 밖 (Toast/미연결 유지 가능) |

### 4.3 Mock 구조

```ts
interface Collection {
  id: string;
  name: string;
  categoryId: string;      // DB에 없음
  itemCount: number;       // Mock에 저장
  plannedCount: number;
  completedCount: number;
  avgRating?: number;      // API 없음
  updatedAt: string;
}
```

- `itemIds` 배열 **없음** — Item은 `collectionId`로 역참조
- Count는 Mock에 **저장** (DB 집계와 다를 수 있음)
- 상세는 목록에서 선택한 Mock 객체를 그대로 사용 (별도 fetch 없음)

**Frontend ≠ 계약인 점:** 단일 `categoryId`, `avgRating`, 상세 Item 일괄 로드, 목록 필터/정렬/페이지 UI 부재.  
→ **계약을 바꾸지 않는다.** 연동 단계에서 ViewModel 매핑으로 흡수한다.

---

## 5. 확정 Endpoint

```http
GET /api/v1/collections
GET /api/v1/collections/{collection_id}
```

- 목록·상세 모두 동일 `CollectionResponse` (Item 배열 **미포함**).
- 소속 Item:

```http
GET /api/v1/items?collection_id={collection_id}&sort=title&order=asc
```

- 상세 화면 Item 목록은 Item API **기존 기본 `page_size`(25)** 사용. `page_size=100` 강제 금지.
- 기존 `GET /items?collection_id=`는 이미 구현되어 있으며 본 계약과 호환된다.

---

## 6. Query Parameter 계약 (`GET /collections`)

| Param | 타입 | 기본 | 설명 |
| --- | --- | --- | --- |
| `page` | int ≥ 1 | 1 | Offset |
| `page_size` | int 1~100 | 25 | max 100 |
| `search` | string | — | Collection **이름만** |
| `category_id` | UUID | — | 활성 Item 중 해당 Category ≥1 |
| `status` | `PLANNED` \| `COMPLETED` | — | 활성 Item 중 해당 status ≥1 |
| `sort` | enum | `updated_at` | 아래 |
| `order` | `asc` \| `desc` | `desc` | |

**초기 미제공:** `has_multiple_categories`, `completion_state`, `has_items`.

### 검증

| 상황 | HTTP |
| --- | --- |
| `page` < 1 | 422 |
| `page_size` < 1 또는 > 100 | 422 |
| 잘못된 UUID (`category_id`, path id) | 422 |
| 지원하지 않는 `status` / `sort` / `order` | 422 (Enum/Literal) |
| 마지막 페이지 초과 `page` | **200**, `collections=[]`, `total`/`total_pages` 유지 |

---

## 7. Response Schema

### 7.1 `CollectionResponse` (목록 요소 = 상세)

```json
{
  "id": "collection-uuid",
  "name": "007 시리즈",
  "item_count": 7,
  "planned_count": 2,
  "completed_count": 5,
  "categories": [
    {
      "id": "category-uuid",
      "name": "영화",
      "item_count": 7
    }
  ],
  "created_at": "2026-07-01T00:00:00+00:00",
  "updated_at": "2026-07-20T00:00:00+00:00"
}
```

**미포함:** Item Preview/배열, 대표 Category, `completion_rate`, `last_item_updated_at`, `activity_updated_at`, `avg_rating`.

완료율 (Frontend):

```text
item_count > 0 ? completed_count / item_count : 0
```

### 7.2 목록 Wrapper

```json
{
  "collections": [],
  "page": 1,
  "page_size": 25,
  "total": 0,
  "total_pages": 0,
  "has_next": false,
  "has_previous": false
}
```

Item 목록 Wrapper와 동일 패턴 (`collections` 키만 다름).

### 7.3 `categories[]`

- 활성 Item만
- 혼재 전부 반환, 대표 선택 없음
- `sum(categories[].item_count) == item_count`
- 정렬: `Category.sort_order ASC`, `Category.name ASC`

### 7.4 빈 Collection

```json
{
  "item_count": 0,
  "planned_count": 0,
  "completed_count": 0,
  "categories": []
}
```

기본 목록·상세에 **포함**. `category_id` 또는 `status` 필터 적용 시 조건 불충족으로 **제외**.

---

## 8. 필터 의미

### `search`

- Collection 이름만; 소속 Item 제목 검색 금지
- trim 후 공백만이거나 미입력 → 필터 미적용
- Escape된 `ILIKE`: `\`, `%`, `_`를 와일드카드로 직접 해석하지 않음
- 구현: 기존 `catalog.escape_like_pattern` + `escape="\\"` 재사용

### `category_id`

- 포함 조건: 활성 Item 중 `category_id` 일치 ≥ 1 (`EXISTS`)
- **응답 집계는 Collection 전체 활성 Item** (필터에 매칭된 Item만으로 축소 금지)
- 유효 UUID지만 Category 없음 / 매칭 Collection 없음 → **200 + 빈 목록**

### `status`

- 파라미터명 Item API와 동일 `status`
- 포함 조건: 활성 Item 중 해당 status ≥ 1
- 응답 집계는 전체 활성 Item 기준

### `category_id` + `status`

- **동일 활성 Item**이 두 조건을 모두 만족해야 포함 (`EXISTS ... AND category_id AND status`)
- 서로 다른 Item이 조건을 나눠 만족하는 Collection은 **제외**
- 예: 영화/COMPLETED + 애니영화/PLANNED만 있으면 `category_id=영화&status=PLANNED`에 **미포함**
- 포함돼도 응답 집계는 전체 활성 Item

**축소 금지 예시 (실데이터):** `스타워즈` — 전체 9, 영화만 6. `category_id=영화`로 포함되더라도 `item_count`는 **9**여야 한다.

---

## 9. 정렬과 페이지네이션

### 정렬

| sort | 의미 |
| --- | --- |
| `updated_at` | Collection.`updated_at` |
| `created_at` | Collection.`created_at` |
| `name` | Collection.`name` |
| `item_count` | 활성 Item 수 |
| `completed_count` | 활성 COMPLETED 수 |

기본: `sort=updated_at&order=desc`.  
보조 정렬: 동일 direction의 Collection `id`  
예: `ORDER BY updated_at DESC, id DESC`.

`item_count` / `completed_count` 정렬 시에도 집계는 활성 Item만, 빈 Collection은 0으로 참여.

### 페이지네이션

Offset. `total_pages = ceil(total / page_size)` (total=0 → 0).  
`has_next` / `has_previous`는 Item API와 동일 규칙.

---

## 10. Soft Delete 정책

```text
활성 Item = Item.deleted_at IS NULL
```

다음에만 활성 Item 사용:

- `item_count`, `planned_count`, `completed_count`
- `categories[].item_count`
- `category_id` / `status` / 복합 필터
- Collection 상세의 Item 목록 (`GET /items`)

모든 활성 Item이 없어져도 Collection 행은 유지 → 빈 Collection으로 목록·상세 노출.  
초기 버전 Item 복원 API 없음. Collection 자체 soft delete 없음.

---

## 11. 오류와 사용자 접근 정책

### 상세 `GET /collections/{collection_id}`

| 상황 | HTTP |
| --- | --- |
| 현재 사용자 Collection | 200 |
| 존재하지 않음 | 404 |
| 다른 사용자 Collection | **404** (존재 여부 비노출) |
| UUID 형식 오류 | 422 |

조회 조건: `Collection.id = :id AND Collection.user_id = current_user.id` (없으면 404). Item 상세와 동일 패턴.

### Enum

지원하지 않는 `status` / `sort` / `order` → 422.

---

## 12. Frontend 상세 연동 규칙 (문서만, 코드 미수정)

상세 화면은 두 API를 **독립 호출**:

```http
GET /api/v1/collections/{collection_id}
GET /api/v1/items?collection_id={collection_id}&sort=title&order=asc
```

| 결과 | UI |
| --- | --- |
| Collection 성공 + Items 실패 | 메타데이터 표시, Item 영역만 오류·재시도 |
| Collection 실패 (네트워크/5xx) | 상세 전체 오류 |
| Collection 404 | Item 목록 결과 **표시하지 않음** |

목록 → 상세 복귀 시 목록 쿼리 상태 보존은 Items 상세와 같은 패턴을 권장하나, 구현은 연동 단계에서 결정.

---

## 13. 성능 분석 결과

환경: PostgreSQL 16, seed 249 collections / 845 linked items / 7202 items.  
측정: 읽기 전용 `EXPLAIN (ANALYZE, BUFFERS)`.

| 후보 Query | Execution Time |
| --- | ---: |
| 기본 목록 + 상태 집계 (`updated_at`, page 25) | **1.13 ms** |
| 페이지 Collection Category 집계 (2nd query) | **1.42 ms** |
| 이름 검색 ILIKE | **0.37 ms** |
| `category_id` EXISTS + 전체 집계 | **8.48 ms** |
| `status` EXISTS | **2.07 ms** |
| `category_id`+`status` EXISTS | **1.82 ms** |
| `item_count` 정렬 | **1.04 ms** |
| `completed_count` 정렬 | **0.91 ms** |
| `updated_at` 정렬만 | **0.27 ms** |
| 상세 상태 집계 (최대 Collection) | **0.15 ms** |
| 상세 Category 집계 | **0.28 ms** |
| 최대 Collection Item 목록 25 | **0.14 ms** |

### 관찰

- 현재 규모에서 **추가 Index 필수 아님**. Seq scan on 249 collections는 허용 범위.
- `ix_items_collection_id`가 Collection 소속 Item·EXISTS·상세에 사용됨.
- N+1 위험: Collection마다 Category/Item을 개별 조회하면 발생. **페이지 ID 집합에 대한 일괄 집계**로 방지.
- 필터용 JOIN을 집계 JOIN에 섞으면 `item_count`가 축소됨 (BAD pattern 실측). **EXISTS(필터) ⊕ 별도 전체 집계** 필수.
- 이름 검색용 인덱스 불필요 (249행).
- `item_count`/`completed_count` 정렬은 전 Collection 집계 후 sort — 현재 1ms대.

---

## 14. 구현 시 Query 권장 구조

기존 `catalog.py` 패턴을 따른다: Service 함수 + Pydantic 응답, `get_current_user`, soft delete는 `_active_items_filter`와 동일하게 `deleted_at IS NULL`.

### 14.1 목록 (권장: 2~3 쿼리, N+1 금지)

1. **필터된 Collection ID + total + 페이지 슬라이스**  
   - `search` → `name ILIKE`  
   - `category_id` / `status` → `EXISTS (SELECT 1 FROM items WHERE collection_id = collections.id AND deleted_at IS NULL AND …)`  
   - 복합 필터는 **하나의 EXISTS** 안에 AND  
   - `ORDER BY` + `LIMIT/OFFSET`  
   - `item_count`/`completed_count` 정렬 시 LEFT JOIN 집계 subquery (필터 EXISTS와 분리)

2. **페이지 ID에 대한 상태 집계** (전체 활성 Item)

```sql
SELECT collection_id,
       COUNT(*) AS item_count,
       COUNT(*) FILTER (WHERE status = 'PLANNED') AS planned_count,
       COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed_count
FROM items
WHERE user_id = :uid AND deleted_at IS NULL
  AND collection_id IN (:page_ids)
GROUP BY collection_id
```

3. **페이지 ID에 대한 Category 집계**

```sql
SELECT i.collection_id, c.id, c.name, COUNT(*) AS item_count
FROM items i
JOIN categories c ON c.id = i.category_id
WHERE i.user_id = :uid AND i.deleted_at IS NULL
  AND i.collection_id IN (:page_ids)
GROUP BY i.collection_id, c.id, c.name, c.sort_order
ORDER BY c.sort_order, c.name
```

빈 Collection은 집계 row가 없어도 `item_count=0`, `categories=[]`로 조립.

### 14.2 상세

- `SELECT collection WHERE id AND user_id` → 없으면 404  
- 동일 집계 쿼리 (단건 `collection_id`)  
- Item 배열은 Service에서 만들지 않음

### 14.3 금지

- 필터 조건이 걸린 `JOIN items`로 `COUNT`하여 응답 집계에 사용
- Collection loop 내 per-row query
- `MAX(items.updated_at)`를 정렬·필드로 사용

---

## 15. 테스트 필수 항목

구현 전 수립한 테스트 항목이다. Backend 구현 시 `test_collections_read_api.py`에 반영했으며, Fixture/Factory 패턴은 `test_read_api.py`와 동일하다.

| # | 항목 |
| --- | --- |
| 1 | 현재 사용자 Collection만 목록에 포함 |
| 2 | 다른 사용자 Collection 상세 → 404 |
| 3 | 존재하지 않는 id → 404 |
| 4 | 빈 Collection 목록·상세 포함 (`counts=0`, `categories=[]`) |
| 5 | 활성 Item만 집계 |
| 6 | `deleted_at` 설정된 Item 제외 |
| 7 | 단일 Category `categories` 길이 1 |
| 8 | 혼재 Category 전부 반환, 합계 = `item_count` |
| 9 | `categories` 정렬 `sort_order`, `name` |
| 10 | 상태 혼합 시 planned/completed 합 = item_count |
| 11 | `category_id` 단독 필터 |
| 12 | `status` 단독 필터 |
| 13 | 동일 Item 복합 필터 포함 |
| 14 | 서로 다른 Item이 조건 분담 → 복합 필터 제외 |
| 15 | 검색 Escape (`%`, `_`, `\`) |
| 16 | 공백 검색 → 필터 미적용 |
| 17 | 잘못된 UUID → 422 |
| 18 | 존재하지 않는 Category → 200 빈 목록 |
| 19 | 잘못된 Enum sort/status/order → 422 |
| 20 | 지원 정렬 전 항목 + `id` 보조 정렬 안정성 |
| 21 | 빈 결과 total=0 |
| 22 | 마지막 페이지 초과 → 200 + 빈 배열 + total 유지 |
| 23 | N+1 방지 (쿼리 수 upper bound / 페이지 크기와 무관한 고정 쿼리 수) |
| 24 | 목록 요소와 상세의 동일 `CollectionResponse` 필드 |
| 25 | `page`/`page_size` 경계 422 |
| 26 | 필터 적용 시에도 응답 집계가 전체 활성 Item 기준 (스타워즈형 fixture) |

---

## 16. 실제 코드와 계약의 충돌 사항

**읽기 API 구현을 막는 스키마/데이터 충돌: 없음.**

기록용 차이 (계약 유지, 연동·쓰기 단계에서 처리):

| 구분 | 내용 |
| --- | --- |
| Frontend Mock | 단일 `categoryId`, `avgRating`, Item 일괄 로드 — 계약과 다름. 계약 변경 없음 |
| Frontend 삭제 문구 | “연결 해제” vs DB `ON DELETE RESTRICT` — **쓰기** 이슈 |
| Collection `updated_at` | Item 변경 시 미갱신 — 계약이 Collection 컬럼만 쓰도록 이미 확정 |
| Soft-delete Unique Index | 현재 없음 (TMDB용 부분 unique는 `0004` 예정·미적용). 읽기 계약 의존 없음 |
| Collection soft delete | 컬럼 없음 — 계약도 Collection soft delete 요구 안 함 |
| 빈 Collection | 실데이터 0건이나 스키마·LEFT JOIN으로 구현 가능 |
| `docs/02` | Collection 컬럼 표가 간략함 — 실제는 §2가 우선 |

---

## 17. 구현 전 잔여 위험

1. **쓰기 도입 후 “최근 수정” UX:** Item만 바꾸면 Collection 목록 정렬이 안 움직일 수 있음. 읽기 계약은 유지; 필요 시 쓰기에서 Collection touch 또는 별도 정책을 후속으로 논한다 (이번 A/B 재오픈 없음).
2. **Collection hard delete:** RESTRICT + soft-deleted Item FK 잔존 시 삭제 실패. 쓰기 API 설계 시 SET NULL/unlink 절차 필요.
3. **Frontend 연동:** `categories[]` 다중 표시, `avgRating` 제거, Item 페이지네이션 UI 추가가 필요할 수 있음.
4. **대량 성장 시:** collections ≫ 수천, linked items ≫ 수만이면 `(user_id, updated_at)` 또는 `(collection_id) WHERE deleted_at IS NULL` 인덱스 재검토. **현재는 추가 불필요.**
5. ~~Router/Service 미구현~~ → **Backend 구현 완료** (Frontend 연동은 후속).

---

## 부록 A. Backend 구현 패턴 정렬 (참고)

| 패턴 | 기존 | Collection에 적용 |
| --- | --- | --- |
| Router 등록 | `api/v1/__init__.py` include | `collections` router **등록됨** |
| User | `Depends(get_current_user)` | 동일 |
| Service | `catalog.py` | `list_collections` / `get_collection_detail` **구현됨** |
| Schema | `*ListResponse` wrapper | `CollectionListResponse` **구현됨** |
| page 계산 | `math.ceil` | 동일 |
| Escape | `escape_like_pattern` | 이름 검색 재사용 |
| 타 사용자 | 404 | 동일 |
| N+1 | `joinedload` / subquery 집계 | 페이지 일괄 집계 |
| Soft delete | service where 절 | Item 집계·필터에만 |

---

## 부록 B. 문서 상태 변경 이력

| 일시 | 내용 |
| --- | --- |
| 2026-07-22 | 구현 전 검증 완료, 최종 계약 문서 최초 작성 |
| 2026-07-22 | Backend 구현·테스트·Smoke 완료, 상태 → **Backend 구현 완료** |
| 2026-07-22 | Frontend B-3a 목록 연동 완료 · 상세 연동 대기 |
