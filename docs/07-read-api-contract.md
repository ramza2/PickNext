# 07. Category·Item 조회 API 계약 (Phase A-1)

> **상태:** **구현 완료**  
> **범위:** 읽기 API 요청·응답·정책 및 Backend 구현  
> **비범위:** Frontend 연동, TMDB, 쓰기·추천 API, Migration

프로파일링 일시: 2026-07-22 (개발 PostgreSQL, 읽기 전용).  
구현 검증: 자동 테스트 + 실DB 읽기 전용 대조 완료.

---

## 1. 현재 DB 구조 요약

### 1.1 관계

```text
User 1──N Category
User 1──N Collection
User 1──N Item
Category 1──N Item
Collection 1──N Item   (nullable)
```

`Collection`에는 **`category_id`가 없다.**  
Frontend Mock의 `Collection.categoryId`는 DB와 불일치한다. Collection은 `(user_id, name)` unique이며, 하나의 Collection에 여러 Category Item이 섞일 수 있다 (실데이터 18건).

### 1.2 Item 핵심 컬럼

| 컬럼 | 타입 | NULL | 비고 |
| --- | --- | --- | --- |
| id | UUID | NO | PK |
| user_id | UUID | NO | 사용자 범위 |
| category_id | UUID | NO | FK |
| collection_id | UUID | YES | FK |
| title | TEXT | NO | 300자 초과 가능 (최대 321) |
| status | ENUM PLANNED/COMPLETED | NO | |
| rating | NUMERIC(2,1) | **NO** | 0.0~5.0, 0.5 단위 Check |
| progress_note | VARCHAR(200) | YES | |
| memo | TEXT | YES | |
| deleted_at | timestamptz | YES | Soft delete |
| created_at / updated_at | timestamptz | NO | |

### 1.3 Category 컬럼

| 컬럼 | DB 존재 | Frontend Mock |
| --- | --- | --- |
| id (UUID) | ✅ | ❌ 문자열 slug (`movie`) |
| name | ✅ | ✅ |
| category_type | ✅ | ❌ |
| sort_order | ✅ | ❌ (색·아이콘으로 대체) |
| color / icon | ❌ | ✅ Mock only |

**계약에 color/icon을 추가하지 않는다.** Frontend는 이름·`category_type`·로컬 UI 맵으로 표시한다.

### 1.4 인덱스 (items)

- `ix_items_user_id`
- `ix_items_user_id_category_id`
- `ix_items_user_id_status`
- `ix_items_active` (partial: `deleted_at IS NULL`)
- `ix_items_collection_id`
- **title 검색용 인덱스 없음**

### 1.5 TMDB 필드

Migration `0004` 미적용. `poster_path`, `external_*` 등 **컬럼 없음**.  
A-1 응답에 해당 키를 넣지 않는다 (null placeholder 금지). TMDB 도입 시 스키마 확장.

### 1.6 Legacy 내부 메타

`legacy_import_runs`, `legacy_import_items`, `source_id`는 **공개 API에 노출하지 않는다.**

---

## 2. 실데이터 프로파일링 결과

### 2.1 전체 건수

| 대상 | 건수 |
| --- | --- |
| users | 1 (`jchramza@gmail.com`) |
| categories | 10 |
| collections | 249 |
| items (전체·활성) | **7,202** / deleted 0 |
| recommendation_history | 0 |
| legacy_import_runs | 1 |
| legacy_import_items | 7,213 (스킵 포함 매핑) |

### 2.2 Item 상태

| status | 건수 |
| --- | --- |
| PLANNED | **4,708** |
| COMPLETED | **2,494** |
| 기타 / NULL | **0** |

검증식: `4708 + 2494 = 7202`.

### 2.3 Category별 집계

| name | sort | total | PLANNED | COMPLETED | collection 연결 | progress_note |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 애니메이션 | 1 | 563 | 456 | 107 | 67 | 0 |
| 애니 영화 | 2 | 480 | 16 | 464 | 112 | 0 |
| 영화 | 3 | **3662** | 2319 | 1343 | 571 | 0 |
| 한국드라마 | 4 | 1059 | 982 | 77 | 47 | 0 |
| 일본드라마 | 5 | 565 | 476 | 89 | 31 | 0 |
| 중국드라마 | 6 | 96 | 58 | 38 | 7 | 0 |
| 미국드라마 | 7 | 168 | 141 | 27 | 3 | 0 |
| 예능 | 8 | 335 | 3 | 332 | 0 | **294** |
| 만화책 | 9 | 37 | 20 | 17 | 7 | 0 |
| 음식 | 10 | 237 | 237 | 0 | 0 | 0 |
| **합계** | | **7202** | **4708** | **2494** | **845** | **294** |

### 2.4 NULL·빈 문자열

| 필드 | NULL | 빈 문자열 | 비어 있지 않음 |
| --- | ---: | ---: | ---: |
| collection_id | 6357 | — | 845 |
| progress_note | 6908 | **0** | 294 |
| memo | **7202** | 0 | 0 |
| created_at / updated_at | 0 | — | 7202 |
| deleted_at | 7202 (활성) | — | 0 |

빈 `progress_note`/`memo`는 현재 없음. API는 빈 문자열을 받으면 **null로 정규화**하는 방향을 쓰기 API에서 채택 예정. 조회는 DB 값을 그대로 반환.

### 2.5 Collection

- Collection 249개, **Item 없는 Collection 0**
- 동일 사용자 중복 이름 0
- **Category 혼재 Collection 18개** (예: 강철의 연금술사 3개 Category)
- → Collection 상세/목록 API에서 “대표 Category”를 단정하면 안 됨

### 2.6 제목·검색

- 최장 제목: **321자** (source_id 2209 픽사단편, 복구 완료)
- 동일 user+category 중복 제목: **0**
- 공백·대소문자만 다른 제목 그룹: **0**
- 한글 포함 7068 / 영문 611 / 숫자 1524 / 특수문자 1899

### 2.7 평점

| 값 | 건수 |
| --- | ---: |
| 0.0 | **6870** |
| 0.5~5.0 (0.5 단위) | 332 |
| half-step 위반 | 0 |
| 범위 위반 | 0 |

- 컬럼: `NUMERIC(2,1)` **NOT NULL**
- Legacy Import는 미입력 시 `0.0` 저장
- **0.0 = 미평가 관례**로 취급하되, 진짜 0점과 구분 불가 → 향후 `rating` nullable 검토 (A-1에서는 스키마 변경 없음)

### 2.8 데이터 특이사항 (계약·구현 시 주의)

1. Collection ≠ 단일 Category  
2. `rating=0.0` 대다수 (표시는 “평가 없음”)  
3. memo 전무, progress_note는 예능 중심  
4. Soft delete 미사용 (전부 `deleted_at IS NULL`)  
5. Category UUID는 Seed마다 달라질 수 있음 → Frontend는 **런타임 API id**만 사용  
6. 추천 이력 테이블은 비어 있음 (홈 “최근 선택”은 A-1에서 빈 배열 허용)

---

## 3. Frontend 화면별 데이터 요구사항

### 3.1 홈

| UI | Backend 필드/API | 비고 |
| --- | --- | --- |
| 전체/예정/완료 수 | Summary 또는 Category counts 합 | Mock 배열 합산 금지 |
| Collection 수 | Summary `collection_count` | |
| 최근 등록 | `GET /items?sort=created_at&order=desc&page_size=5` | |
| 최근 선택 | History API (후속) | A-1은 미구현 → 빈 목록 |
| 빠른 추천 | Category UUID 목록 | 이름→UUID 해석은 Frontend 설정 |

### 3.2 전체 항목 목록

| Mock 필드 | DB/계약 | A-1 |
| --- | --- | --- |
| id | items.id | ✅ |
| title | title | ✅ |
| category | nested `{id,name}` | ✅ |
| collection | nested 또는 null | ✅ |
| status | status | ✅ |
| rating | rating | ✅ (0.0=미평가 표시는 FE) |
| progress_note | progress_note | ✅ |
| poster_path | 없음 | ❌ 생략 |
| external_source | 없음 | ❌ 생략 |
| updated_at | updated_at | ✅ |
| registeredAt | created_at | ✅ `created_at` |

필터 UI: category, status, title search, sort(`updatedAt`/`title`/`rating`), page_size 25.

### 3.3 Item 상세

목록 필드 + `memo`, `created_at`.  
TMDB/overview/releaseDate는 DB 없음 → 생략.  
Legacy source_id 비공개.

### 3.4 Category 필터

| 필요 | DB | 결정 |
| --- | --- | --- |
| id | UUID | ✅ |
| name | name | ✅ |
| sort_order | sort_order | ✅ |
| category_type | category_type | ✅ (선택 노출) |
| item/planned/completed counts | 집계 | ✅ **항상 포함** (`include_counts` 파라미터 없음) |
| color/icon | 없음 | **계약 추가 안 함** |

---

## 4. 확정 API 목록

| Method | Path | 역할 |
| --- | --- | --- |
| `GET` | `/api/v1/summary` | 홈용 전체 집계 |
| `GET` | `/api/v1/categories` | Category 목록 + 집계 (항상) |
| `GET` | `/api/v1/items` | Item 목록 (필터·정렬·페이지) |
| `GET` | `/api/v1/items/{item_id}` | Item 상세 |

### Summary 분리 — **확정 (안 B)**

| 안 | 내용 | 결정 |
| --- | --- | --- |
| A | Category에만 집계 | 기각 |
| **B** | `GET /categories` + `GET /summary` | **채택** |

Category 응답은 항상 `{ "categories": [ ... ] }` 래퍼를 사용한다.  
집계 필드는 항상 반환한다 (`item_count`, `planned_count`, `completed_count`).

`GET /summary`는 Category 반복 없이 다음만 반환한다.

```json
{
  "item_count": 7202,
  "planned_count": 4708,
  "completed_count": 2494,
  "collection_count": 249,
  "category_count": 10
}
```

최근 등록은 Summary에 넣지 **않는다** → `GET /items` 재사용.

---

## 5. Query Parameter

### 5.1 `GET /categories`

Query Parameter 없음. 집계는 항상 포함.

정렬: `sort_order ASC`, `name ASC`.

### 5.2 `GET /items`

| Param | 타입 | 기본 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| `page` | int ≥ 1 | 1 | | Offset 페이지 |
| `page_size` | int 1~100 | 25 | | |
| `search` | string | — | | 제목만, trim 후 빈 값 무시 |
| `category_id` | UUID | — | | 이름 조회 금지 |
| `status` | `PLANNED` \| `COMPLETED` | — | | |
| `collection_id` | UUID | — | | |
| `has_collection` | bool | — | | true=연결됨, false=미연결 |
| `sort` | enum | `updated_at` | | 아래 |
| `order` | `asc` \| `desc` | `desc` | | `title` 기본은 구현 시 `asc` 권장 가능하나 **명시 order 우선** |

**A-1에서 제외 (후속):**  
`has_progress_note`, `rating_min/max`, `created_from/to`, `updated_from/to` — 홈·목록 UI에 당장 없고, 구현 복잡도만 증가.

#### 잘못된 값

| 상황 | HTTP |
| --- | --- |
| UUID 형식 오류 | **422** (FastAPI validation) |
| `page` < 1, `page_size` 범위 밖, 잘못된 sort/status | **422** |
| 존재하지 않는 `category_id` / `collection_id` | **200 + 빈 목록** (목록 API) |
| `search` 공백만 | 필터 미적용 (전체) |
| `search` 최소 글자 | **강제 안 함** (1글자 허용, 7k 규모에서 충분) |

#### 정렬 (`sort`)

| sort | 보조 정렬 |
| --- | --- |
| `updated_at` | `id` 동일 direction |
| `created_at` | `id` |
| `title` | `id` |
| `rating` | `id` |
| `status` | `id` |

예: `sort=updated_at&order=desc` → `ORDER BY updated_at DESC, id DESC`.

### 5.3 Soft delete

기본: `deleted_at IS NULL`만.  
삭제 포함 조회 파라미터는 A-1에 두지 않음.

---

## 6. 검색 정책

**선택안 1 확정: `title`만 ILIKE 검색.**

근거:

- 목록 UI가 제목 검색만 사용
- memo 전무, progress_note 294건·예능 중심
- Collection name 조인 검색은 인덱스·복잡도 증가
- 7,202건 `ILIKE '%…%'` EXPLAIN ~4ms (현재 충분)

구현 규칙:

- `pattern = '%' + escape_like(trim(search)) + '%'`
- Escape: `\`, `%`, `_`
- PostgreSQL `ILIKE` (한글 문제없음)
- Full Text Search는 후속

---

## 7. 페이지네이션

**Offset 기반** (Frontend 페이지 번호 UI와 일치).

```json
{
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 7202,
  "total_pages": 289,
  "has_next": true,
  "has_previous": false
}
```

경계:

| 조건 | 동작 |
| --- | --- |
| page > total_pages (total>0) | `items=[]`, 동일 meta, has_next=false |
| total=0 | total_pages=0, items=[] |
| page_size 최대 100 | 초과 시 422 |

`total_pages = ceil(total / page_size)` (total=0이면 0).

---

## 8. 응답 Schema

### 8.1 Category

```json
{
  "id": "1565eb72-c351-4daf-b5dc-ef22515cbbbd",
  "name": "영화",
  "category_type": "MEDIA",
  "sort_order": 3,
  "item_count": 3662,
  "planned_count": 2319,
  "completed_count": 1343
}
```

`rating`은 JSON number. **`0.0`은 Legacy 미평가 관례**이며 API는 null을 반환하지 않는다.  
진짜 0점과의 구분은 후속 nullable Migration에서 검토한다.

중첩 `category` / `collection`은 Frontend 매핑 단순화용이다.  
N+1 방지는 응답 형태가 아니라 **`joinedload(Item.category)`, `joinedload(Item.collection)`** (또는 동등 JOIN)으로 해결한다.

`include_counts=false` 옵션은 **제공하지 않는다**.

식별자는 항상 UUID. 이름은 표시값.

### 8.2 Summary

위 §4 JSON.

### 8.3 Item 목록 요소

```json
{
  "id": "uuid",
  "title": "작품명",
  "status": "PLANNED",
  "rating": 0.0,
  "progress_note": null,
  "category": {
    "id": "uuid",
    "name": "영화"
  },
  "collection": {
    "id": "uuid",
    "name": "007 시리즈"
  },
  "created_at": "2026-07-21T00:00:00+00:00",
  "updated_at": "2026-07-21T00:00:00+00:00"
}
```

- `collection` 없으면 `null`
- Category/Collection은 **중첩 객체** (평면 `category_id`+`category_name`보다 N+1 방지·FE 매핑 단순)
- rating은 number(JSON). `0.0` 의미는 문서상 미평가 관례
- TMDB 필드 없음

### 8.4 Item 상세

목록 필드 + `memo`:

```json
{
  "id": "uuid",
  "title": "작품명",
  "status": "PLANNED",
  "rating": 0.0,
  "progress_note": null,
  "memo": null,
  "category": { "id": "uuid", "name": "영화" },
  "collection": null,
  "created_at": "...",
  "updated_at": "..."
}
```

### 8.5 오류 응답

FastAPI 기본 validation (`detail` 배열/문자열)을 유지.

| 코드 | 상황 |
| --- | --- |
| 422 | Query/path validation |
| 404 | Item 없음 **또는** 다른 사용자 Item (존재 여부 비노출) |
| 503 | DB 장애 (health와 동일 계열, 조회 실패 시) |

**403을 쓰지 않음** — 인증 전 단계에서 타 사용자 Item은 404로 통일해 정보 누출 방지.

---

## 9. 사용자 범위 정책

현재 인증 없음. A-1:

```text
get_current_user_id() 의존성
→ settings.seed_user_email 로 User 조회
→ 없으면 500 (설정 오류)
→ 모든 조회에 user_id = 해당 User.id 강제
```

| 상황 | 정책 |
| --- | --- |
| Seed 이메일 사용자 없음 | 500 + 명확한 메시지 |
| 사용자 2명 이상 | Seed 이메일 사용자만 (타 사용자 데이터 미노출) |
| 향후 JWT/세션 | Dependency만 교체, 경로·스키마 유지 |

Frontend는 Category/Item id로만 필터한다.  
빠른 추천 preset은 **이름 배열 → 로드된 categories에서 UUID resolve** (저장·API 파라미터에는 UUID만).

```ts
// Frontend 설정 예 (관계 키 아님)
const QUICK_RECOMMENDATION_PRESETS = {
  movie: ["영화"],
  drama: ["한국드라마", "일본드라마", "미국드라마", "중국드라마"],
  // ...
};
// API 호출 시: category_id=<uuid>
```

---

## 10. 성능 검증 계획

실측 (ANALYZE, 개발 DB, 2026-07-22):

| Query | Execution Time |
| --- | --- |
| 첫 페이지 updated_at DESC LIMIT 25 | ~2.3 ms |
| 마지막 페이지 OFFSET 7175 | ~4.5 ms |
| Category=영화 필터 | ~3.1 ms |
| status=PLANNED | ~1.9 ms |
| title ILIKE '%007%' | ~4.4 ms |
| Category별 COUNT | ~3.6 ms |

**A-1에서 Index Migration 불필요.**  
후속 후보 (문서만):

- `(user_id, updated_at DESC, id DESC)` — 기본 목록 정렬 최적화
- `title` gin_trgm — 검색량 증가 시

구현 후 동일 EXPLAIN를 CI/매뉴얼 체크로 재실행.

---

## 11. 테스트 계획 (구현 단계)

### Category

- Seed 사용자 Category 10개, `sort_order` 순
- 집계값 §2.3 표와 일치 (항상 포함)
- 다른 user Category 제외
- Item 0건 Category도 목록에 포함 (counts=0)

### Item 목록

- 기본 page=1, page_size=25, total=7202
- page_size=100 / 경계 422
- 마지막 페이지·빈 페이지
- search 한글·특수문자·`%` escape
- category_id / status / collection_id / has_collection
- 복합 필터
- 모든 sort/order + 안정 순서
- 존재하지 않는 UUID → 빈 목록
- 잘못된 UUID → 422
- soft-deleted 제외 (fixture로 1건 삭제 후)

### Item 상세

- 정상 + collection null/non-null
- 제목 321자 Item
- memo/progress_note null
- 없는 UUID / 타 사용자 → 404

### Summary

- item/planned/completed/collection/category counts = 실측값

### 회귀 상수

```text
Item total = 7202
PLANNED = 4708
COMPLETED = 2494
Category total = 10
Collection total = 249  (보정 후; Import 직후 244에서 증가)
```

---

## 12. OpenAPI 예시 (초안)

```yaml
openapi: 3.1.0
info:
  title: PickNext Read API (Phase A-1)
  version: 0.1.0
paths:
  /api/v1/summary:
    get:
      summary: Home aggregate counts
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SummaryResponse"
  /api/v1/categories:
    get:
      summary: List categories with item counts
      responses:
        "200":
          content:
            application/json:
              schema:
                type: object
                required: [categories]
                properties:
                  categories:
                    type: array
                    items: { $ref: "#/components/schemas/CategoryResponse" }
  /api/v1/items:
    get:
      parameters:
        - { name: page, in: query, schema: { type: integer, minimum: 1, default: 1 } }
        - { name: page_size, in: query, schema: { type: integer, minimum: 1, maximum: 100, default: 25 } }
        - { name: search, in: query, schema: { type: string } }
        - { name: category_id, in: query, schema: { type: string, format: uuid } }
        - { name: status, in: query, schema: { type: string, enum: [PLANNED, COMPLETED] } }
        - { name: collection_id, in: query, schema: { type: string, format: uuid } }
        - { name: has_collection, in: query, schema: { type: boolean } }
        - { name: sort, in: query, schema: { type: string, enum: [updated_at, created_at, title, rating, status], default: updated_at } }
        - { name: order, in: query, schema: { type: string, enum: [asc, desc], default: desc } }
      responses:
        "200":
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ItemListResponse" }
  /api/v1/items/{item_id}:
    get:
      parameters:
        - { name: item_id, in: path, required: true, schema: { type: string, format: uuid } }
      responses:
        "200":
          content:
            application/json:
              schema: { $ref: "#/components/schemas/ItemDetailResponse" }
        "404":
          description: Not found
components:
  schemas:
    SummaryResponse:
      type: object
      required: [item_count, planned_count, completed_count, collection_count, category_count]
      properties:
        item_count: { type: integer }
        planned_count: { type: integer }
        completed_count: { type: integer }
        collection_count: { type: integer }
        category_count: { type: integer }
    CategoryResponse:
      type: object
      required: [id, name, category_type, sort_order]
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
        category_type: { type: string, enum: [MEDIA, BOOK, FOOD, GENERAL] }
        sort_order: { type: integer }
        item_count: { type: integer }
        planned_count: { type: integer }
        completed_count: { type: integer }
    CategoryRef:
      type: object
      required: [id, name]
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
    CollectionRef:
      type: object
      required: [id, name]
      properties:
        id: { type: string, format: uuid }
        name: { type: string }
    ItemListItem:
      type: object
      required: [id, title, status, rating, category, created_at, updated_at]
      properties:
        id: { type: string, format: uuid }
        title: { type: string }
        status: { type: string, enum: [PLANNED, COMPLETED] }
        rating: { type: number }
        progress_note: { type: string, nullable: true }
        category: { $ref: "#/components/schemas/CategoryRef" }
        collection: { allOf: [{ $ref: "#/components/schemas/CollectionRef" }], nullable: true }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }
    ItemListResponse:
      type: object
      required: [items, page, page_size, total, total_pages, has_next, has_previous]
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/ItemListItem" }
        page: { type: integer }
        page_size: { type: integer }
        total: { type: integer }
        total_pages: { type: integer }
        has_next: { type: boolean }
        has_previous: { type: boolean }
    ItemDetailResponse:
      allOf:
        - $ref: "#/components/schemas/ItemListItem"
        - type: object
          properties:
            memo: { type: string, nullable: true }
```

---

## 13. 추후 확장 항목

- TMDB 필드 (Migration 0004 이후)
- Collection 목록·상세 읽기 API → **구현 완료** ([08-collection-read-api-contract](./08-collection-read-api-contract.md))
- History 읽기 API (홈 최근 선택)
- rating nullable / 미평가 구분
- title trigram Index
- Cursor pagination
- 다중 사용자 인증
- `has_progress_note`, 날짜·평점 범위 필터

---

## 14. 확정·잔여 확인 항목

| 항목 | 상태 | 비고 |
| --- | --- | --- |
| Category 응답 래퍼 `{ "categories": [] }` | **확정** | 구현됨 |
| Category counts 항상 반환 | **확정** | `include_counts` 없음 |
| Summary 분리 | **확정** | 구현됨 |
| rating 0.0 미평가 관례 | **확정 (현재)** | nullable은 후속 |
| Seed 사용자 = Import 사용자 | 운영 전 재확인 | `.env` `SEED_USER_EMAIL` |

---

## 15. 구현 전 승인 체크리스트 (구현 반영)

| 항목 | 결정 내용 | 근거 | Frontend 영향 | Backend 영향 | 향후 변경 가능성 |
| --- | --- | --- | --- | --- | --- |
| Summary API 분리 | **분리 (`GET /summary`)** | 홈 카드·Collection 수 | 홈 2~3 호출 | 집계 쿼리 1개 | 낮음 |
| Category counts | **항상 포함** | 10개·성능 충분 | slug→UUID 교체 | LEFT JOIN 집계 | 낮음 |
| Category 래퍼 | `{ categories: [] }` | 확장성 | `payload.categories` | Schema | 낮음 |
| Item 목록 구조 | 페이지 래퍼 + 중첩 category/collection | FE 매핑 | Mock→nested | joinedload | 낮음 |
| Item 상세 구조 | 목록 + memo | 상세 UI | overview 등 Mock 제거 대비 | 동일 조회 | TMDB 시 확장 |
| 검색 대상 | **title만** | UI·데이터 분포 | 동작 동일 | ILIKE + escape | FTS 가능 |
| 페이지네이션 | Offset, page_size≤100 | FE 페이지 UI | total 사용 | COUNT+LIMIT | Cursor 후속 |
| 정렬 | updated_at/created_at/title/rating/status + id | 안정성 | sort 키 이름 맞춤 | ORDER BY | 낮음 |
| 사용자 범위 | Seed 이메일 DI | 인증 전 | 체감 없음 | `get_current_user` | 인증 시 교체 |
| rating 0.0 | 미평가 관례, NOT NULL 유지 | Legacy 6870건 | 0 표시=평가없음 | 스키마 유지 | nullable 검토 |
| TMDB 필드 | **A-1 미포함** | 컬럼 없음 | Placeholder 유지 | 스키마 단순 | 0004 후 |
| color/icon | API 미제공 | DB 없음 | 로컬 맵 | 없음 | 낮음 |
| N+1 | joinedload | 목록 성능 | 없음 | catalog.list_items | 낮음 |

---

## 16. 관련 문서

- [02-domain-model.md](./02-domain-model.md)
- [05-tmdb-integration-plan.md](./05-tmdb-integration-plan.md)
- [06-frontend-integration-plan.md](./06-frontend-integration-plan.md)
