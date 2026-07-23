# 09. Collection·Item 쓰기 API 계약 사전 분석

**상태:** Collection·Item 기본 쓰기 Release Candidate **PASS** (RC-1 API·격리 DB · RC-2 브라우저 수동 QA · RC-2-A 결함 조치)
**작성 기준일:** 2026-07-22  
**삭제 정책 갱신:** 2026-07-22 (Item Soft Delete → Hard Delete)  
**D-2 구현:** 2026-07-22 — `0004_remove_item_soft_delete` 적용, Model·Read Query Soft Delete 제거  
**D-3~D-5 구현:** 2026-07-22 — `DELETE /api/v1/items/{item_id}` Hard Delete Transaction  
**D-6 구현:** 2026-07-22 — `DELETE /api/v1/collections/{collection_id}` (Item≥1 → 409)  
**D-7 구현:** 2026-07-22 — Frontend Item·Collection DELETE Dialog·API Client·origin별 복귀  
**C-1 구현:** 2026-07-22 — `POST`/`PATCH /api/v1/collections` (이름 Trim·Unique·no-op)
**C-2 구현:** 2026-07-22 — Frontend Collection 생성·수정 Dialog·API Client·409 Inline
**I-1 구현:** 2026-07-22 — `POST`/`PATCH /api/v1/items` (Validation·Lock·no-op·History Snapshot 불변)
**I-2 구현:** 2026-07-23 — Frontend Item 생성·수정 Dialog·상태 버튼·PATCH Diff·origin 보존
**I-3 구현:** 2026-07-23 — Collection 상세 Item 빠른 연결 해제·상태 변경 · 쓰기 최종 회귀
**RC-1 검증:** 2026-07-23 — API·격리 DB Write Smoke · 자동 회귀 · Seed 비파괴
**RC-2 검증:** 2026-07-23 — 격리 Backend(:8001)·Frontend(:5175) 브라우저 수동 QA · **PASS**
**RC-2-A:** 2026-07-23 — Items checkbox Warning · Item Form Inline Validation · **PASS**
**범위:** Collection·Item 쓰기 Backend·Frontend + Hard Delete 연동
**비범위:** Bulk Delete, Drag & Drop, Category CRUD, RecommendationHistory UI, TMDB, 인증, 자동화 Browser E2E
**연계:** `docs/10-item-hard-delete-migration-analysis.md`

---

## 0. 확정된 삭제·쓰기 정책 (재선택 금지)

| 정책 | 내용 |
|------|------|
| Item 삭제 | **Hard Delete.** DELETE 시 Item 행을 DB에서 실제 삭제 |
| `deleted_at` | **같은 Migration에서 즉시 제거.** 과도기 유지 없음 |
| 활성 Item | **존재하는 Item = 활성 Item.** Soft Delete·복원·보관 개념 없음 |
| 추천 이력 | 삭제 Item을 포함한 `recommendation_history` **전체** 삭제 (연결 행만 삭제 금지) |
| Collection 직접 삭제 | Item **1건 이상 → 409**. Item **0건 → Hard Delete** |
| 마지막 Item DELETE | 같은 Transaction에서 해당 Collection도 Hard Delete |
| 빈 Collection 유지 | PATCH 연결 해제·이동·빈 Collection 생성으로 비면 **유지**. 빈 Collection 직접 DELETE는 **허용** |

### 0.1 폐기된 이전 정책 (참고만)

다음 Soft Delete 정책은 **폐기**되었다. 구현·계약에 사용하지 않는다.

```text
Item Soft Delete / deleted_at 설정
활성 Item = deleted_at IS NULL
삭제 Item 행 유지·복원 API
Hard Delete 금지
recommendation_history_items RESTRICT 때문에 Hard Delete 불가 → Soft Delete로 우회
Soft Delete Item의 Collection FK 유지
Collection 삭제 시 Soft Delete Item unlink 후 삭제 (이전 A안)
```

---

## 1. 실제 DB 구조 (현재 / Migration 전)

근거: SQLAlchemy Model, Alembic `0001`~`0003`, PostgreSQL Schema (2026-07-22 재검증).

### 1.1 Collection

| 컬럼 | 타입 | NULL | Default | 비고 |
|------|------|------|---------|------|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → `users.id` **ON DELETE RESTRICT** |
| `name` | `varchar(200)` | NO | — | 최대 200자 |
| `created_at` | timestamptz | NO | `now()` | |
| `updated_at` | timestamptz | NO | `now()` | ORM `onupdate` |

| 제약·인덱스 | 내용 |
|-------------|------|
| Unique | `uq_collections_user_id_name (user_id, name)` — 대소문자·공백 구분 |
| Soft Delete | **컬럼 없음** (유지) |

Collection을 참조하는 FK:

| 참조 테이블 | 컬럼 | ON DELETE |
|-------------|------|-----------|
| `items` | `collection_id` | **RESTRICT** |
| `recommendation_history` | `collection_id` | **SET NULL** |
| `legacy_import_collections` | `collection_id` | **CASCADE** |

**확정 Collection 삭제 동작 (Migration 후에도 동일 FK):**

- 직접 DELETE: Item이 1건이라도 있으면 App이 **409** (unlink 자동 처리 없음).
- 마지막 Item Hard Delete 시: App이 Collection Hard Delete. History `collection_id`는 **SET NULL**. Legacy collection mapping은 **CASCADE**.

### 1.2 Item (현재 Schema — Soft Delete 잔존)

| 컬럼 | 타입 | NULL | Default | 비고 |
|------|------|------|---------|------|
| `id` | UUID | NO | `gen_random_uuid()` | PK |
| `user_id` | UUID | NO | — | FK → `users` RESTRICT |
| `category_id` | UUID | NO | — | FK → `categories` RESTRICT |
| `collection_id` | UUID | YES | NULL | FK → `collections` RESTRICT |
| `title` | TEXT | NO | — | |
| `status` | item_status | NO | 없음 | PLANNED / COMPLETED |
| `rating` | numeric(2,1) | NO | 없음 | 0~5, 0.5 |
| `progress_note` | varchar(200) | YES | NULL | |
| `memo` | TEXT | YES | NULL | |
| `created_at` / `updated_at` | timestamptz | NO | now() | |
| `deleted_at` | — | — | — | **D-2에서 제거 완료** |

Index (현재):

- `ix_items_user_id`, `ix_items_category_id`, `ix_items_collection_id`
- `ix_items_user_id_category_id`, `ix_items_user_id_status`
- ~~`ix_items_active`~~ — **D-2에서 제거 완료**

### 1.2.1 D-2 구현 결과 (2026-07-22)

- Migration: `backend/alembic/versions/0004_remove_item_soft_delete.py`
- Seed DB Revision: `0004_remove_item_soft_delete`
- Soft Delete 행 0건 → Upgrade 성공, Item 7202 / Collection 249 유지
- Soft Delete 행 존재 시 Upgrade는 RuntimeError로 중단 (가드 DB 검증)
- `catalog.py` Soft Delete 필터·`_active_items_filter` 제거

### 1.2.2 D-3~D-5 구현 결과 (2026-07-22)

- Endpoint: `DELETE /api/v1/items/{item_id}` → **204** (Body 없음)
- Service: `catalog.delete_item` — Item/Collection `FOR UPDATE` → History 부모 일괄 DELETE → Item DELETE → 잔여 EXISTS → 필요 시 Collection DELETE → `commit`
- Legacy Mapping: DB CASCADE (Service 미호출)
- Collection `updated_at` Touch 없음
- 테스트: `tests/test_item_hard_delete_api.py` + FK Schema 검증
- Backend 전체 **112 passed**
- **D-6 완료:** Collection 직접 DELETE + Item≥1 → 409

`completed_at`·TMDB 컬럼: **없음**. TMDB 계획 Migration 번호는 `docs/10`에서 조정.

### 1.2.3 D-6 구현 결과 (2026-07-22)

- Endpoint: `DELETE /api/v1/collections/{collection_id}` → **204** (Body 없음)
- Service: `catalog.delete_collection` — Collection `FOR UPDATE` → Item `EXISTS` → Item 있으면 **409** → 빈 Collection `DELETE` → `commit`
- RecommendationHistory: DB `ON DELETE SET NULL` (History 부모·Items 유지)
- Legacy Mapping: DB CASCADE (Service 미호출)
- IntegrityError(FK RESTRICT 등) → rollback 후 **409** `Collection contains items`
- Collection `updated_at` Touch 없음 (409 포함)
- 테스트: `tests/test_collection_delete_api.py`
- Backend 전체 **128 passed** (D-6 검증 2026-07-22)
- **잔여:** Item POST/PATCH Frontend

### 1.2.6 I-1 Item POST/PATCH 구현 결과 (2026-07-22)

- Endpoint: `POST /api/v1/items` → **201** `ItemDetailResponse` / `PATCH /api/v1/items/{item_id}` → **200** `ItemDetailResponse`
- Schema: `ItemCreate` · `ItemUpdate` (`model_fields_set`로 생략·명시 null 구분)
- Service: `catalog.create_item` · `catalog.update_item`
  - POST: Category 소유권 → Collection `FOR UPDATE`(연결 시) → INSERT → `joinedload` 응답
  - PATCH: Item `FOR UPDATE` → 필드별 검증·정규화 → Collection Lock(이동·해제 시 UUID 정렬) → no-op 시 UPDATE 생략·`updated_at` 불변
- Validation: `title` Trim·빈값 422·길이 상한 없음·중복 허용 / `rating` 0~5·0.5·Decimal / `progress_note` 200자 / `memo` Trim·빈→null
- PATCH `{}` 또는 Body 없음 → **422** / `collection_id`·`progress_note`·`memo` 명시 null 허용 / `title`·`category_id`·`status`·`rating` 명시 null → **422**
- Collection: 연결·이동·해제 시 빈 Collection **유지** (PATCH에서 자동 삭제 없음) · `updated_at` **Touch 없음**
- RecommendationHistory: PATCH가 Snapshot·History **수정 안 함** (DELETE에서만 History 전체 삭제)
- Legacy: POST 신규 Item Mapping 없음 · Legacy Item PATCH 시 Mapping·Import Run 유지
- IntegrityError(알려진 FK) → **409** `Related resource changed`
- 테스트: `tests/test_item_write_api.py` (36) · DELETE·Collection 회귀 포함
- 격리 DB Smoke: `picknext_item_write_smoke` **16/16**
- Backend 전체 **195 passed** (I-1 시점) · I-3 최종 **196 passed**
- **I-3에서 Collection 상세 「제거」 Frontend 연동 완료**

### 1.2.7 I-2 Item 생성·수정 Frontend 구현 결과 (2026-07-23)

- API: `createItem` / `updateItem` · `ItemCreatePayload` / `ItemUpdatePayload`
- UI: `ItemFormModal` (create/edit), Category·Collection Options 전체 로드, Rating 0.5 Select
- PATCH Diff: 변경 필드만 전송 · `collection_id`/`progress_note`/`memo` 명시 null · 변경 없음 시 요청 생략
- 생성 Context: home / items / collections(locked Collection)
- 생성 후 Item 상세 진입 · 수정 후 상세 유지 · origin·Snapshot 보존
- 상태 빠른 변경: Item 상세 기존 버튼 → `updateItem({ status })`
- Collection 상세 「제거」: I-3에서 연동
- 검증: `verify-item-write-api.mjs` · `verify-item-write-flow.mjs` · tsc · build

### 1.2.8 I-3 Collection 상세 빠른 작업 · 최종 회귀 (2026-07-23)

- 「제거」= `updateItem({ collection_id: null })` — Item 유지 · 빈 Collection 유지 · DELETE 미호출
- Confirm Dialog 문구: 영구 삭제와 구분 · 마지막 Item 시 빈 Collection 유지 안내
- 기존 행 상태 버튼: `updateItem({ status })` PLANNED↔COMPLETED
- 비낙관적 Reload · 페이지 보정 · 404/409/422/5xx Toast
- 검증: `verify-collection-item-quick-actions.mjs` · Backend **196 passed** · 격리 DB Smoke **33/33**
- Seed 비파괴 확인
- **잔여:** Bulk Delete, Drag & Drop, Category CRUD, History UI, TMDB, 인증, 자동화 Browser E2E

### 1.2.9 RC-1 API·격리 DB Release Candidate 검증 (2026-07-23)

```text
API·격리 DB Release Candidate 검증: 통과
당시 브라우저 수동 QA: 대기 → RC-2에서 완료
당시 판정: PASS WITH NOTES
```

- 격리 DB: `picknext_write_rc` · Fixture(영화/드라마/도서 · RC Empty/Single/Multi/Rename · Standalone · History · Legacy · 타 사용자)
- API Smoke: `backend/scripts/rc1_write_rc_smoke.py` **40/40**
  - Collection POST/409/PATCH/DELETE(빈·비어있지 않음)
  - Item POST/PATCH Diff·연결·이동·Form unlink
  - 빠른 unlink · **마지막 Item unlink → Collection 유지**
  - 빠른 status · **마지막 Item DELETE → Collection 404** · 204 body 길이 0
  - History Snapshot 불변 · Legacy Mapping 유지 · 타 사용자 404
- 자동 회귀: Backend **196 passed** · Frontend verify · tsc · build
- Seed: 7202 / 249 / 10 / 4708 / 2494 / linked 845 전후 동일

### 1.2.10 RC-2 브라우저 수동 QA · Release Candidate PASS (2026-07-23)

```text
브라우저 수동 QA: 완료
최종 판정: PASS
```

- 환경: `picknext_write_rc` · RC Backend `:8001` · Frontend `:5175` · Seed Backend `:8002` 분리
- Fixture bootstrap: `backend/scripts/rc2_bootstrap_fixtures.py`
- Desktop 1440×900 · Mobile 390×844 · Console · Network 확인
- Collection·Item 기본 쓰기·빠른 작업·마지막 unlink/DELETE 정책 구분 브라우저 검증
- **RC-2-A PASS:** Items `checked`/`onChange` Warning 제거 · Item Form 필드별 Inline Validation · Focus/Scroll · Write 0회
- **잔여(별도):** Bulk Delete, Drag & Drop, Category CRUD, History UI, TMDB, 인증, 자동화 Browser E2E

### 1.2.4 D-7 Frontend 구현 결과 (2026-07-22)

- API: `frontend/src/api/catalog.ts` — `deleteItem`, `deleteCollection` (204 → `undefined`)
- 오류 문구: `frontend/src/api/deleteMessages.ts`
- UI: `App.tsx` — `ConfirmModal`(pending), ItemDetailPage·CollectionDetailInline 삭제 Dialog
- Item origin(home/items/collections) 복귀, Collection GET 404 시 「항목과 빈 컬렉션」 Toast
- Collection `item_count > 0` → DELETE 미호출 + Toast
- Item 행 「제거」: I-3에서 연결 해제 (`collection_id: null`) 연동 — Hard Delete 미연결
- 검증: `npm run build`, `npx tsc --noEmit`, `node scripts/verify-delete-api.mjs`
- **잔여 (당시):** POST·PATCH, Bulk 삭제, Vitest/RTL — I-2/I-3에서 POST·PATCH·빠른 제거 완료

### 1.2.5 D-8 안정화 결과 (2026-07-22)

- Backend pytest **128 passed**, 삭제 관련 **66 passed**
- 격리 DB `picknext_d8_smoke` HTTP DELETE Smoke **28/28**
- Seed 비파괴: `/summary`·DB 조회로 7202 / 249 / 10 / linked 845 전후 동일 (실DELETE 없음)
- 보조 PowerShell JSON 파싱 명령은 셸 작성 문제로 exit 1 — API·Seed 데이터 이상 없음
- 판정: **PASS WITH NOTES** (Desktop/Mobile 수동 시각 검증 권장)

### 1.3 Item 연관 테이블

| 참조 테이블 | FK | NULL | ON DELETE | Hard Delete 영향 | 선행 처리 |
|-------------|-----|-----:|-----------|------------------|-----------|
| `recommendation_history_items` | `item_id` | NO | **RESTRICT** | Item 직접 DELETE 차단 | 포함 History **전체** 선삭제 |
| `legacy_import_items` | `item_id` | YES | **CASCADE** | Mapping 행 자동 삭제 | 선삭제 불필요 |
| (간접) `recommendation_history` | — | — | 자식→부모 CASCADE | History 삭제 시 Items CASCADE | App이 History ID 단위 삭제 |

ORM:

- `RecommendationHistory.items`: `cascade="all, delete-orphan"`
- `RecommendationHistoryItem.item`: DB RESTRICT
- `LegacyImportItem.item`: DB CASCADE

**Item FK에 CASCADE를 걸어 연결 행만 지우는 방식은 정책 불충족.** History 전체 삭제가 필수.

---

## 2. 실데이터 프로파일 (요약, SELECT only)

사용자: `jchramza@gmail.com`

| 지표 | 값 |
|------|-----|
| Collection | 249 (빈 Collection 0, 이름 Unique OK) |
| Item | 7202 |
| `deleted_at IS NOT NULL` | **0** (재검증 완료) |
| 추천 이력 | 0 |
| Legacy item mapping | 7202 / collection mapping 244 |
| rating=0 (미평가) | 6870 |
| Collection 연결 Item | 845 |

Migration 전제: Soft Delete 행 0건. 행이 발견되면 **자동 Hard Delete하지 않고 Migration 실패** 권장 (`docs/10`).

---

## 3. Frontend 쓰기 UI (요약)

**D-7 완료 (2026-07-22):** Item·Collection Hard Delete — Confirm Dialog + `deleteItem`/`deleteCollection` API Client. origin별 복귀·재조회, Collection `item_count > 0` 사전 Toast, Backend 409 재조회. Collection 상세 Item 「제거」는 연결 해제 미구현 Toast 유지.

**미연동:** Collection 상세 Item 「제거」, Bulk 삭제, History/추천 UI.

Frontend DTO에 `deleted_at` **없음**. “복원” 문구는 **백업 Import RESTORE**용이며 Item Soft Delete 복원과 무관.

---

## 4. Backend 쓰기 패턴 (현재)

**구현됨**

- `DELETE /api/v1/items/{item_id}` — `catalog.delete_item`
- `DELETE /api/v1/collections/{collection_id}` — `catalog.delete_collection`
- `POST /api/v1/collections` — `catalog.create_collection` (C-1)
- `PATCH /api/v1/collections/{collection_id}` — `catalog.update_collection` (C-1)
- Router는 Service에 Transaction 위임. `get_db` auto-commit **없음** (Service가 명시적 commit/rollback).

**미구현**

- Item POST/PATCH
- 읽기 Service `catalog.py`는 Soft Delete 필터 없이 `Item.user_id` 범위만 사용 (D-2 완료).

---

## 5. Collection 생성 (구현 완료 — C-1)

`POST /api/v1/collections` — `{ "name" }`

| 항목 | 구현 |
|------|------|
| Trim / 빈 이름 | 서버 Trim, 빈값 422 |
| 최대 길이 | 200 |
| Unique | 같은 사용자 409; 타 사용자 동일 이름 허용 |
| 대소문자 | DB case-sensitive 유지 |
| 응답 | 201 + `CollectionResponse` |
| 빈 Collection 생성 | 허용 |
| Race | `uq_collections_user_id_name` → rollback + 409 |

Request Schema: `CollectionCreate` (`name` 필수, 공통 `_normalize_collection_name`).

---

## 6. Collection 이름 수정 (구현 완료 — C-1)

`PATCH /api/v1/collections/{collection_id}` — `{ "name" }`

| 항목 | 구현 |
|------|------|
| 소유권 | 현재 사용자만; 미존재·타 사용자 404 |
| Trim / 빈 이름 | POST와 동일 Validator |
| Unique 충돌 | 409, 대상 Collection·Item 유지 |
| no-op | Trim 후 현재 이름과 동일 → 200, DB UPDATE 없음, `updated_at` 불변 |
| 실제 변경 | `updated_at` 갱신 (Model `onupdate`) |
| Lock | `SELECT FOR UPDATE` |
| 응답 | 200 + `CollectionResponse` (기존 Item 집계 유지) |

Request Schema: `CollectionUpdate`. 테스트: `tests/test_collection_write_api.py` (31건). Backend 전체 **159 passed**.

### 6.1 C-2 Frontend 연동 (2026-07-22)

| 항목 | 구현 |
|------|------|
| API Client | `createCollection`, `updateCollection` (`catalog.ts`) |
| Dialog | `CollectionFormModal` — 생성·수정 공용, Trim·1~200자, `{length}/200` |
| 생성 UX | 목록 「추가」→ POST 201 → 상세 진입, 목록 Reload, Toast |
| 수정 UX | 상세 연필 → PATCH 200 → 상세 유지, Header·목록 Reload |
| no-op | 동일 이름 저장 Disabled, PATCH 미호출 |
| 409 | Inline Error (Toast 중복 없음) |
| 404 PATCH | Toast + 목록 복귀 |
| 5xx/Network | Toast, Dialog·입력 유지 |
| 검증 | `verify-collection-write-api.mjs`, `verify-delete-api.mjs`, tsc, build |

---

## 7. Collection 직접 삭제 (구현 완료 — D-6)

`DELETE /api/v1/collections/{collection_id}`

| 조건 | 응답 |
|------|------|
| 현재 사용자·Item 0건 | **204** Hard Delete |
| Item 1건 이상 | **409 Conflict** |
| 타 사용자·미존재 | **404** |
| UUID 형식 오류 | **422** |
| 동시 Item 연결 FK 충돌 | **409** (rollback) |

- Item을 **자동 연결 해제하지 않음**.
- RecommendationHistory **전체 삭제하지 않음** (`collection_id` SET NULL).
- Soft Delete 조건 없음.
- 검사와 DELETE는 **한 Transaction** (`Collection FOR UPDATE` → `EXISTS` → DELETE).

**폐기:** 이전 분석의 Collection 삭제 A안(unlink 후 삭제)·C안(Collection Soft Delete)·D안(Item Cascade).

---

## 8. Item 생성 (I-1 구현 완료)

`POST /api/v1/items` → **201** `ItemDetailResponse`

| 필드 | 구현 |
|------|------|
| title | 필수·앞뒤 Trim·빈값 422·TEXT·중복 허용 |
| category_id | 필수·현재 사용자 소유·404 |
| collection_id | 선택·NULL·소유 Collection만 |
| status | 기본 PLANNED |
| rating | 기본 0.0·0.5 단위·Decimal |
| progress_note / memo | Trim·빈→null·progress_note 최대 200자 |

삭제 후 동일 제목 재등록 = **새 행 INSERT** (복원·행 재사용 없음).

---

## 9. Item 수정 (I-1 구현 완료)

`PATCH /api/v1/items/{item_id}` → **200** `ItemDetailResponse`

허용: title, category_id, collection_id, status, rating, progress_note, memo  
`collection_id: null` = 연결 해제 → **빈 Collection 유지**  
Collection A→B 이동으로 A가 비어도 **A 유지**  
빈 Body `{}` → **422** · no-op 시 UPDATE 생략·`updated_at` 불변  
미존재 Item → 404

---

## 10. Item Hard Delete 계약 (확정)

후보: `DELETE /api/v1/items/{item_id}`

```text
1. 소유권 확인, collection_id 보관
2. 해당 Item을 참조하는 recommendation_history ID 집합 조회
3. 해당 History 전체 DELETE → history_items CASCADE
4. Item DELETE → legacy_import_items CASCADE
5. 원래 collection_id가 있으면 잔여 Item EXISTS 확인
6. 0건이면 Collection Hard Delete
7. Commit
```

| 항목 | 확정·권장 |
|------|-----------|
| 성공 | **204** (이력 건수 body는 잔여 결정) |
| 미존재·타 사용자 | **404** |
| 재 DELETE | **404** |
| 복원 | **없음** |
| History | **포함 History 전체** 삭제. 다른 Item 본체는 유지 |

`recommendation_history_items.item_id ON DELETE CASCADE`만으로 연결 행만 지우는 것은 **정책 위반**.

---

## 11. Status·Rating

PATCH로 PLANNED↔COMPLETED. 완료 시 Rating 필수 아님. `rating=0` = 미평가. `completed_at` 추가 안 함.

---

## 12. Category·Collection 연결

소유권 검증, 타 사용자 404. Collection–Item Category 불일치 **허용**.  
연결 해제·이동으로 빈 Collection → **유지**.

---

## 13. PATCH·Validation

생략=유지, `null`=클리어(`collection_id`/`memo`/`progress_note`). `rating: null`은 잔여 결정(0 정규화 vs 422). Trim, UUID 422/404.

---

## 14. HTTP Status·오류

| 상황 | Status |
|------|--------|
| 생성 성공 | 201 |
| PATCH 성공 | 200 |
| Item/빈 Collection DELETE 성공 | 204 (권장) |
| Validation / UUID | 422 |
| 미존재·타 사용자 | 404 |
| Collection 이름 Unique | 409 |
| Item 있는 Collection 직접 DELETE | **409** |
| IntegrityError Unique/FK | 409 (메시지 비노출) |

---

## 15. Transaction·동시성

### Item DELETE (확정 순서)

History 선삭제 → Item 삭제 → (필요 시) Collection 삭제 → Commit. 부분 성공 금지.

### Collection 직접 DELETE

`EXISTS(items)` 검사와 DELETE를 한 Transaction. 동시 Item 연결 시 RESTRICT/재검사로 409.

### 동시성 (개인용 최소)

- 마지막 두 Item 동시 삭제: 둘 다 Collection 삭제 시도 가능 → 한쪽 성공, 한쪽 no-op/404.
- 마지막 Item 삭제 vs 새 Item INSERT: Collection 삭제와 INSERT 경쟁 → FK 실패 가능. 최소 `SELECT … FOR UPDATE` on Collection 권장 후보 (`docs/10`).
- Version 컬럼·Event 시스템: **초기 불필요**.

---

## 16. Collection `updated_at`

| 안 | 내용 | 상태 |
|----|------|------|
| A | Collection 행 직접 변경만 | 읽기 계약과 일치 — **후보** |
| B | 구성 변경(연결·이동·해제) 시 touch | UX — **후보** |
| C | Item 내용까지 touch | 비권장 |

Item Hard Delete로 Collection이 같이 삭제되면 `updated_at` 무의미. **미확정(잔여).**

---

## 17. Frontend 저장 UX

성공 후 재조회. Optimistic 비권장.  
삭제 Dialog: 복구 불가·(해당 시) Collection 동반 삭제·(선택) 추천 이력 삭제 안내 (`docs/10`).  
Item 있는 Collection 삭제: FE 사전 차단 가능하나 **Backend 409 필수**.

---

## 18. 구현 단계

쓰기·삭제 Migration은 `docs/10`의 **D-1~D-8**을 따른다. 이전 Soft Delete 중심 W-3/W-4 A안은 **폐기**.

| 단계 | 내용 |
|------|------|
| D-1 | 계약·문서 (`09`/`10` 및 후속 문서 반영) |
| D-2 | `deleted_at` 제거 Migration + Model·Read Query |
| D-3~D-6 | Item Hard Delete / History / 마지막 Collection / Collection 409 |
| D-7 | FE 삭제 UI |
| D-8 | 회귀·Smoke |

생성·PATCH는 Migration(D-2) 이후 또는 병행 가능. **삭제 API는 D-2 이후.**

---

## 19. 성능·Index

- `ix_items_active` 제거 후 기존 Index로 충분. **대체 Index 신설 불필요.**
- History ID 조회: `ix_recommendation_history_items_item_id`
- Collection 잔여: `ix_items_collection_id` + EXISTS
- 상세는 `docs/10` §16

---

## 20. 사용자 결정 필요 항목 (잔여만)

1. RecommendationHistory 부모→자식 FK 추가 변경 필요성 (이미 CASCADE)
2. Item DELETE 응답: 순수 204 vs 삭제된 이력 수 포함 200
3. Migration 시 Soft Delete 행 발견 → **실패(권장)** 확정 문구
4. 마지막 Item 삭제 시 FE/API 안내 수준
5. Collection 자동 삭제 시 최소 Lock (`FOR UPDATE` 여부) — **Item POST/PATCH·DELETE 구현 완료**
6. Collection `updated_at` touch — **Item 쓰기에서 Touch 안 함 (확정·구현)**
7. title API 상한 — **임의 상한 없음 (Legacy 321자 유지, 확정·구현)**
8. `rating: null` 의미 — **POST/PATCH에서 null 거부, 0.0=미평가 (확정·구현)**

### 더 이상 질문이 아닌 확정 항목

```text
Item Hard Delete
deleted_at 즉시 제거
복원 없음
추천 이력 전체 삭제
Collection 직접 삭제 = Item 있으면 409
마지막 Item DELETE 시 Collection 자동 삭제
연결 해제·이동으로 빈 Collection 유지
Item POST/PATCH Backend (I-1)
rating null 거부·0.0=미평가
Collection Lock·PATCH null 의미
```

---

## 21. 구현 전 충돌 사항

| 충돌 | 내용 |
|------|------|
| `recommendation_history_items` RESTRICT | Hard Delete 전 History 전체 선삭제 **필수** |
| 읽기 API `deleted_at` 필터 | Migration과 동시 제거 필요 |
| `docs/05` TMDB partial Unique `deleted_at IS NULL` | TMDB Migration에서 조건 재설계 필요 |
| Collection 삭제 이전 A안(unlink) | **폐기** — 409 정책과 반대 |
| Soft Delete 테스트 Fixture | Hard Delete·집계 테스트로 교체 |
| Alembic Head `0003` vs TMDB 계획 `0004` | Soft Delete 제거를 `0004`로 쓰면 TMDB는 `0005`로 문서 조정 |

Model·FK와 확정 Hard Delete 정책은 **Application 선삭제로 정합 가능**. Schema만으로 History 전체 삭제를 CASCADE 한 방에 보장할 수 없음.

---

## 22. 미확정 항목

- DELETE 응답 body 여부
- Lock 수준
- `updated_at` touch
- title 길이·rating null
- Soft Delete 잔존 행 Migration 실패 메시지/운영 절차
- Legacy 재Import와 Hard Delete 멱등성 (`docs/10` 잔여 위험)

---

## 23. 참고

- `docs/10-item-hard-delete-migration-analysis.md`
- `docs/02`, `03`, `07`, `08`, `05` — Soft Delete 문구는 구현 단계에서 일괄 수정
