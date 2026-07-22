# 10. Item Hard Delete Migration·삭제 정책 영향 분석

**상태:** Migration·삭제 Backend·Frontend·D-8 최종 회귀 완료
**D-2 완료일:** 2026-07-22  
**D-3~D-5 완료일:** 2026-07-22  
**D-6 완료일:** 2026-07-22  
**D-7 완료일:** 2026-07-22  
**D-8 완료일:** 2026-07-22
**작성 기준일:** 2026-07-22  
**연계:** `docs/09-write-api-contract-analysis.md`  
**비범위 (잔여):** Item POST/PATCH, Collection Frontend 생성·수정

---

## 1. 확정된 삭제 정책

| # | 정책 |
|---|------|
| 1 | Item 삭제 = **Hard Delete** (행 실제 삭제) |
| 2 | `items.deleted_at` **즉시 제거** (과도기 없음). Partial Index·Query·문서 Soft Delete 개념 제거 |
| 3 | 복원·보관·활성=`deleted_at IS NULL` 개념 **폐기** |
| 4 | 삭제 Item을 포함한 `recommendation_history` **전체** 삭제 (+ 해당 `recommendation_history_items`) |
| 5 | Collection 직접 DELETE: Item ≥1 → **409**, Item 0 → Hard Delete |
| 6 | 마지막 Item **DELETE** 시 같은 Transaction에서 Collection Hard Delete |
| 7 | PATCH 연결 해제·이동·빈 생성으로 빈 Collection → **유지**. 빈 Collection 직접 DELETE → **허용** |

연결 행만 CASCADE로 지우고 History를 남기는 방식은 **정책 위반**.

---

## 2. 기존 Soft Delete 구조

### 2.1 컬럼

| 항목 | 값 |
|------|-----|
| 생성 | Alembic `0001_initial.py` |
| Model | `Item.deleted_at` (`backend/app/models/__init__.py`) |
| 타입 | `timestamptz`, **NULL 허용**, server default **없음** |
| Constraint | 없음 |
| Trigger / View / Function | **없음** (재검증) |
| 실데이터 | `deleted_at IS NOT NULL` = **0** / 전체 Item 7202 |

### 2.2 Partial Index

```sql
CREATE INDEX ix_items_active ON items (user_id, category_id)
WHERE deleted_at IS NULL;
```

Model `__table_args__`와 `0001_initial`에 정의.  
동일 컬럼의 비부분 Index `ix_items_user_id_category_id`가 **이미 존재** → `deleted_at` 제거 후 `ix_items_active`는 **단순 제거**로 충분. 대체 Index 신설 불필요.

### 2.3 Raw SQL

애플리케이션 Raw SQL에서 `deleted_at` 참조: **없음**. ORM `catalog.py`만 사용.

---

## 3. DB Schema 영향

### 3.1 Migration 후 `items` (목표)

`deleted_at` 컬럼 **없음**. 나머지 컬럼·CHECK·FK 유지.

### 3.2 최종 Index (목표)

| Index | 유지 |
|-------|------|
| `items_pkey` | ✓ |
| `ix_items_user_id` | ✓ |
| `ix_items_category_id` | ✓ |
| `ix_items_collection_id` | ✓ |
| `ix_items_user_id_category_id` | ✓ |
| `ix_items_user_id_status` | ✓ |
| `ix_items_active` | **제거** |

### 3.3 최종 FK (Item 관련, 권장 유지)

| FK | ON DELETE | Migration 변경 |
|----|-----------|----------------|
| `recommendation_history_items.item_id` | **RESTRICT** | **유지** (App이 History 선삭제) |
| `legacy_import_items.item_id` | **CASCADE** | 유지 |
| `recommendation_history_items.recommendation_history_id` | **CASCADE** | 유지 (이미 충족) |
| `items.collection_id` | **RESTRICT** | 유지 |

History→Items CASCADE를 추가로 “강화”할 실익 없음(이미 CASCADE).  
Item→HistoryItems를 CASCADE로 바꾸면 **연결 행만** 삭제되어 정책 불충족 → **하지 않음**.

---

## 4. Index 영향

| 질문 | 답 |
|------|-----|
| `ix_items_active` 단순 제거 가능한가? | **예** |
| 일반 Index와 중복인가? | `ix_items_user_id_category_id`와 컬럼 동일(부분 조건만 다름) |
| 대체 Index 필요? | **아니오** |
| Read EXPLAIN 영향? | Soft Delete 0건이라 제거 전후 유사 cost. 기능 회귀 없음 |

---

## 5. RecommendationHistory 삭제 영향

### 5.1 Schema 요약

**`recommendation_history`:** id, user_id, category_id, status_filter, collection_id(NULL, SET NULL on Collection delete), selected_at.

**`recommendation_history_items`:** recommendation_history_id, item_id, title_snapshot, status_at_selection, sort_order. Unique `(history_id, item_id)`.

### 5.2 삭제 범위

한 Item이 여러 History에 포함될 수 있다 (`ix_recommendation_history_items_item_id`).

```text
Item A ∈ R1, R2, R3
→ R1·R2·R3 전체 DELETE
→ 각 History의 모든 history_items DELETE (CASCADE)
→ Item B·C 본체는 유지 (R1에 함께 있어도)
→ Item A DELETE
```

Seed: History 0건 → 현재 데이터 손실 없음. 구현 후 동작은 테스트로 고정.

### 5.3 권장 삭제 순서 (DB 제약 우선)

```text
1. Item 소유권 조회 + original_collection_id 보관
2. SELECT DISTINCT recommendation_history_id
     FROM recommendation_history_items WHERE item_id = :id
3. DELETE recommendation_history WHERE id IN (...)
     → history_items ON DELETE CASCADE
4. DELETE items WHERE id = :id
     → legacy_import_items ON DELETE CASCADE
5. original_collection_id IS NOT NULL 이면
     EXISTS(SELECT 1 FROM items WHERE collection_id = :cid)
6. 없으면 DELETE collections WHERE id = :cid AND user_id = :uid
7. COMMIT
```

ORM으로 History를 `db.delete(history)` 하면 `cascade="all, delete-orphan"`도 동작하나, **ID 집합 조회 후 부모 DELETE**가 명확하고 RESTRICT와 충돌하지 않는다.

### 5.4 FK Migration

| 옵션 | 평가 |
|------|------|
| RESTRICT 유지 + App 선삭제 History | **권장** — 정책(History 전체 삭제)과 일치 |
| History→Items CASCADE 추가 | 이미 있음 — no-op |
| Item→history_items CASCADE | 연결만 삭제 → **정책 위반, 금지** |

---

## 6. Legacy Import 영향

| 항목 | 분석 |
|------|------|
| Mapping 자동 처리 | `legacy_import_items.item_id ON DELETE CASCADE` → Item 삭제 시 mapping 행 삭제. 선삭제 불필요 |
| `item_id` NULL | Schema상 NULL 가능(스킵 disposition). CASCADE는 item_id가 있는 행에만 해당 |
| Import Run 통계 | `imported_item_count` 등은 **과거 스냅샷**. Item Hard Delete 후 자동 감소하지 않음 |
| 재Import | SUCCESS `(user_id, source_sha256)` Unique로 동일 파일 재Import 차단. 정책 미정의 시 **잔여 위험** |
| Hard Delete 후 멱등성 | 삭제된 Item이 원본 JSON에 있으면 재Import 정책이 별도 필요 |
| Collection 자동 삭제 | `legacy_import_collections` **CASCADE**로 mapping 삭제 |

원본 `legacy-data` 수정 금지. 재Import 정책은 잔여 위험으로 기록.

---

## 7. Read API 영향

### 7.1 파일·함수별

| 파일 | 함수·위치 | 현재 deleted_at 의존 | 변경 | 테스트 |
|------|-----------|----------------------|------|--------|
| `services/catalog.py` | `get_summary` | `deleted_at.is_(None)` | 제거 | summary 건수 |
| 同上 | `list_categories_with_counts` | 同上 | 제거 | category counts |
| 同上 | `_active_items_filter` | user_id + deleted_at | **헬퍼 제거** 또는 user_id만 | items list |
| 同上 | `_apply_item_filters` | 헬퍼 경유 | user_id만 | |
| 同上 | `get_item_detail` | deleted_at 필터 404 | 존재 여부만 404 | detail |
| 同上 | `_collection_item_exists_clause` | deleted_at | 제거 | collection filters |
| 同上 | `_collection_status_agg_subquery` | deleted_at | 제거 | counts/sort |
| 同上 | `_status_counts_by_collection` | deleted_at | 제거 | |
| 同上 | `_category_counts_by_collection` | deleted_at | 제거 | |
| `models/__init__.py` | `Item.deleted_at`, `ix_items_active` | 정의 | **제거** | model tests |
| `alembic/0001` | 역사적 정의 | — | 신규 revision으로 drop | migration tests |
| Pydantic schemas | — | **없음** | 변경 없음 | — |
| API routers | — | Service 경유 | 직접 변경 최소 | OpenAPI |

### 7.2 새 Item 정의

```text
존재하는 Item = 활성 Item
삭제된 Item = DB에 없음 → 404
```

`Item.deleted_at.is_(None)` 전부 제거.

### 7.3 Collection 집계

집계·EXISTS에서 Soft Delete 조건 제거.  
의미: **DB에 있는 Item 전체 집계** (현재 Soft Delete 0건이라 **수치 변화 없음**).

### 7.4 Item 상세 404

Soft Delete 필터 404 → 일반 미존재 404로 단순화.

---

## 8. Collection 집계 영향

현재 Soft Delete 0 → Migration 직후 집계 동일.  
이후 Hard Delete는 행 제거이므로 집계·EXISTS가 자연 반영. 마지막 Item DELETE면 Collection도 목록에서 소멸.

---

## 9. Frontend 영향

| 검색어 | 결과 |
|--------|------|
| `deleted_at` / soft delete | **없음** (앱 코드) |
| 복원 / 휴지통 | 백업 **Import RESTORE** UI만 (Item Soft Delete와 무관) |
| DTO `Item` | `deleted_at` 필드 **없음** |

### 9.1 Item 삭제 UX (연동 시)

```text
이 항목을 삭제합니다.
삭제된 항목은 복구할 수 없습니다.
이 항목이 Collection의 마지막 항목이면 Collection도 함께 삭제됩니다.
```

추천 이력 안내(선택):

```text
이 항목이 포함된 추천 이력도 함께 삭제됩니다.
```

API는 단순 204 유지 가능. 삭제된 이력 수 body는 잔여 결정.

### 9.2 Collection 직접 삭제 UX

- `item_count > 0`: 버튼 비활성 **또는** 클릭 후 409 Toast. **Backend 409 필수.**
- `item_count == 0`: 확인 후 DELETE.

---

## 10. Item 삭제 Transaction

§5.3 순서. `get_db`는 commit하지 않으므로 Service에서 **명시 commit**. 실패 시 rollback.  
부분 성공 금지.

---

## 11. 마지막 Item의 Collection 자동 삭제

### 11.1 잔여 판정

```sql
SELECT EXISTS (
  SELECT 1 FROM items WHERE collection_id = :cid
);
```

COUNT(*)보다 EXISTS가 적합. Index: `ix_items_collection_id`.

### 11.2 자동 삭제 시 부수 효과

| 대상 | 동작 |
|------|------|
| `recommendation_history.collection_id` | **SET NULL** |
| `legacy_import_collections` | **CASCADE** |
| Collection 상세 화면 | 404 → 목록 복귀 |
| 목록 Pagination | 재조회·마지막 페이지 보정 (FE) |

### 11.3 자동 삭제하지 않는 경우

- `collection_id` PATCH null
- Collection A→B 이동으로 A 비움
- 빈 Collection 생성

---

## 12. Collection 직접 삭제 409 정책

```http
DELETE /api/v1/collections/{collection_id}
```

| 조건 | 응답 |
|------|------|
| 소유·Item 0 | 204 |
| 소유·Item ≥1 | 409 |
| 없음·타 사용자 | 404 |
| UUID 오류 | 422 |

Transaction: Collection 행 `SELECT FOR UPDATE`(권장 후보) → EXISTS(items) → DELETE 또는 409.  
동시 Item INSERT 시 RESTRICT 실패 → IntegrityError → **409**.

---

## 13. 동시성·Lock

| 시나리오 | 위험 | 최소 대응 |
|----------|------|-----------|
| 마지막 Item 삭제 vs 같은 Collection에 INSERT | Collection 삭제 후 INSERT FK 실패 | Collection `FOR UPDATE` |
| 마지막 Item 삭제 vs 다른 Item 이동-in | 유사 | 同上 |
| 마지막 두 Item 동시 DELETE | 양쪽 Collection DELETE | 한쪽 성공, 한쪽 404 — 허용 |
| 개인용 초기 | 낮은 동시성 | Version 컬럼 **불필요** |

Isolation: 기본 READ COMMITTED + 행 Lock으로 충분.

---

## 14. Alembic Upgrade 설계

**현재 Head:** `0003_legacy_data_repairs`  
**후보 Revision:** `0004_remove_item_soft_delete`  
**충돌:** `docs/05` TMDB 계획 `0004` → 문서상 TMDB를 **`0005_add_tmdb_external_columns`** 등으로 재번호.

### Upgrade 순서

```text
1. Soft Delete 행 사전 검증
   SELECT COUNT(*) FROM items WHERE deleted_at IS NOT NULL
   → 0이 아니면 raise (데이터 자동 Hard Delete 금지)
2. DROP INDEX ix_items_active
3. (대체 Index 생성 — 없음)
4. ALTER TABLE items DROP COLUMN deleted_at
5. RecommendationHistory FK 변경 — 없음(유지)
6. 검증: 컬럼·ix_items_active 부재 확인
```

사전 검증 실패 시: Migration **중단**. 운영자가 Soft Delete 행을 수동 검토한 뒤에만 재시도.

---

## 15. Alembic Downgrade 설계

```text
1. ADD COLUMN deleted_at timestamptz NULL
2. CREATE INDEX ix_items_active ... WHERE deleted_at IS NULL
3. FK 원복 — 변경 없었으면 no-op
```

```text
Schema Downgrade는 가능할 수 있으나
Hard Delete된 Item·RecommendationHistory·Legacy mapping은 복원 불가능
```

---

## 16. Model·Schema 영향

### SQLAlchemy

- `Item.deleted_at` 제거
- `ix_items_active` Index 정의 제거
- Relationship cascade **필수 변경 없음** (App 삭제 순서에 의존)

### Pydantic

- `deleted_at` 필드 **현재 없음**
- Soft Delete/복원 Schema **없음**
- DELETE 응답: 204 또는 확장 body (잔여 결정)

### Helper

- `_active_items_filter`: **제거**하고 `Item.user_id == user.id`만 사용. 빈 헬퍼 잔존 금지.

---

## 17. 테스트 영향

프레임워크: pytest + TestClient. Soft Delete fixture: `test_read_api.py`, `test_collections_read_api.py`, `test_models.py`.

### 제거·변경

| 기존 | 조치 |
|------|------|
| Soft Delete 목록 제외 | Hard Delete 후 부재로 재작성 |
| Soft Delete 상세 404 | 미존재 404로 통합 |
| Soft Delete Collection 집계 제외 | 제거 |
| `assert item.deleted_at is None` | 삭제 |
| `test_soft_delete_excluded` | 제거·대체 |

### 신규 필요

- Item Hard Delete 후 DB 행 없음 / GET·PATCH 404
- 관련 추천 이력 전체 삭제, 형제 Item 본체 유지
- Legacy mapping 삭제
- 마지막 Collection Item 삭제 → Collection 삭제
- 비마지막 Item 삭제 → Collection 유지
- Collection 없는 Item 삭제
- Item 있는 Collection DELETE → 409
- 빈 Collection DELETE → 204
- PATCH null / 이동으로 빈 Collection → Collection 유지
- (선택) Collection FOR UPDATE / 동시성 smoke

### Migration 테스트

Upgrade 성공, `deleted_at`/`ix_items_active` 없음, FK 유지, Soft Delete 행 있으면 upgrade fail, Downgrade Schema만 복원.

**후보 파일:** `test_item_hard_delete_api.py`, `test_collection_delete_api.py`.

---

## 18. 문서 영향

이번 단계: **`docs/09` 수정 + 본 문서(`docs/10`) 작성만**.

| 문서 | 구현 단계 수정 대상 |
|------|---------------------|
| `docs/02-domain-model.md` | Soft Delete → Hard Delete |
| `docs/03-recommendation-rules.md` | `deleted_at IS NULL` 제거; Snapshot 문구 재작성 |
| `docs/04-legacy-migration.md` | Hard Delete 후 mapping/재Import 주의 |
| `docs/05-tmdb-integration-plan.md` | partial Unique에서 `deleted_at` 제거; Migration 번호 0005 |
| `docs/06-frontend-integration-plan.md` | 삭제 UX·단계 |
| `docs/07-read-api-contract.md` | deleted_at·ix_items_active·soft delete 절 |
| `docs/08-collection-read-api-contract.md` | Soft Delete 정책·집계·EXISTS |
| `docs/09` | **본 단계에서 반영 완료** |
| `frontend/README.md` / `backend/README.md` | Soft Delete 언급 시 갱신 |

---

## 19. 구현 단계 권장 순서

| 단계 | 범위 | 비범위 |
|------|------|--------|
| **D-1** | 계약·문서 (`09`/`10`, 후속 문서 Soft Delete 문구) | 코드·Migration |
| **D-2** | Alembic `0004_remove_item_soft_delete` + Model + Read Query 전환 + 읽기 테스트 | 쓰기 DELETE API |
| **D-3** | Item Hard Delete API | Collection 자동 삭제 |
| **D-4** | RecommendationHistory 동반 전체 삭제 | — |
| **D-5** | 마지막 Item → Collection 자동 삭제 | — |
| **D-6** | Collection 직접 DELETE + 409 | unlink 로직 |
| **D-7** | FE Item·Collection 삭제 Dialog·연동 | TMDB |
| **D-8** | 전체 회귀·실DB Smoke | 원본 Legacy 수정 |

**D-2를 삭제 API보다 선행.** 한 번에 전부 구현하지 않는다.

---

## 20. 위험과 Rollback 전략

| 위험 | 완화 |
|------|------|
| Soft Delete 잔존 행 있는 DB에 Migration | 사전 COUNT 실패 |
| History 선삭제 누락 | RESTRICT가 Item DELETE 차단 + 테스트 |
| Collection 자동 삭제와 동시 INSERT | FOR UPDATE / 409 |
| Legacy 재Import 불일치 | 잔여 정책 |
| Downgrade 착각 | Schema만 복원, 데이터 불가 명시 |
| TMDB Migration 번호 충돌 | 0004=Soft Delete 제거, TMDB=0005 |

Rollback: Alembic downgrade는 Schema용. 실데이터 Hard Delete는 **백업 복원만** 가능.

---

## 21. 구현 전 충돌 사항

1. `recommendation_history_items` **RESTRICT** ↔ Hard Delete → App History 전체 선삭제 필수  
2. 전 Read Path의 `deleted_at` ↔ 컬럼 드롭 → **D-2 동시 전환**  
3. `docs/05` Unique `WHERE deleted_at IS NULL` ↔ 컬럼 제거  
4. 이전 `docs/09` Collection 삭제 A안(unlink) ↔ 확정 409 — **폐기 완료**  
5. Soft Delete 테스트 ↔ 컬럼 제거  
6. Alembic `0004` 번호 ↔ TMDB 계획  

---

## 22. 잔여 결정 사항

구현 세부만 (정책 재질문 금지):

1. Item DELETE: **204** vs 삭제 History 수 포함 **200**  
2. Migration Soft Delete 행 발견 시 실패 메시지·운영 런북  
3. Collection `SELECT FOR UPDATE` 채택 여부  
4. FE Dialog에 추천 이력 삭제 문구 포함 여부  
5. 마지막 Item → Collection 삭제 사실을 API 응답에 넣을지  
6. Legacy Hard Delete 후 재Import 정책  
7. Collection `updated_at` touch (A/B)  
8. TMDB Migration을 0005로 문서 확정하는 시점  

**재질문 금지:** Item Hard Delete, `deleted_at` 제거, 복원, 추천 이력 전체 삭제, Collection 409, 마지막 Item 시 Collection 자동 삭제, 연결 해제·이동 시 빈 Collection 유지.

---

## 23. 성능·Index (EXPLAIN 요약)

| Query | Index |
|-------|--------|
| Soft Delete 필터 count (현재) | `ix_items_active` Index Only |
| 필터 제거 count | `ix_items_user_id_status` 등 — 유사 cost |
| Collection EXISTS | `ix_items_collection_id` |
| History ID by item | `ix_recommendation_history_items_item_id` |

쓰기 전 **추가 Index Migration 불필요** (`deleted_at`/`ix_items_active` 제거만).

---

## 24. 참고

- 재검증: PostgreSQL Schema, Alembic head `0003_legacy_data_repairs`
- Soft Delete 행: 0
- 코드 검색: `catalog.py`, tests, `docs/02`~`09`, `docs/05`


---

## 25. D-2 구현 결과 (2026-07-22)

### Migration

- 파일: `backend/alembic/versions/0004_remove_item_soft_delete.py`
- Head: `0003_legacy_data_repairs` → `0004_remove_item_soft_delete`
- Upgrade: Soft Delete COUNT 가드 → drop `ix_items_active` → drop `deleted_at`
- Downgrade: Schema만 복원 (데이터 Hard Delete 복원 불가 주석)
- Seed Upgrade: soft_deleted=0, items=7202 유지
- Clean Install (`picknext_d2_clean`): base→head 성공, 최종 `deleted_at` 없음
- 보호 로직 (`picknext_d2_guard`): soft-deleted 1건 시 Upgrade RuntimeError, revision 0003 유지, 행 보존
- Downgrade→Upgrade 재검증: Schema·건수 정상

### Model·Service

- `Item.deleted_at` / `ix_items_active` 제거
- `catalog.py`: `_active_items_filter` 제거, 모든 `deleted_at.is_(None)` 제거
- Summary / Categories / Items / Collections 집계·필터 = 존재 Item 전체

### 테스트

- Soft Delete fixture 제거, 빈 Collection·사용자 범위 테스트로 교체
- `tests/test_item_hard_delete_schema.py` 추가
- Backend 전체 pytest **93 passed**
- D-2 변경 파일 Ruff 통과 (legacy 기존 F401은 미수정)

### Smoke (Seed)

- summary item_count=7202, categories sum=7202, collections total=249
- 드래곤볼 item_count=29, categories=3, cat sum=29
- 스타워즈 item_count=9
- EXPLAIN: user count → `ix_items_user_id_status`; category → `ix_items_user_id_category_id`

### 계약과 구현 차이

- Collection 직접 DELETE / Item≥1 → 409: **구현 완료 (D-6)**
- FK ON DELETE 정책: Migration에서 변경 없음 (RESTRICT 유지)
- Frontend Collection·Item 삭제 UI: **D-7 연동 완료**

### D-3~D-5 (완료 — §26)

---

## 26. D-3~D-5 구현 결과 (2026-07-22)

### 파일

- `backend/app/api/v1/items.py` — `DELETE /items/{item_id}`
- `backend/app/services/catalog.py` — `delete_item`
- `backend/tests/test_item_hard_delete_api.py`
- `backend/tests/test_item_hard_delete_schema.py` (RESTRICT/CASCADE FK)

### Lock·Query

1. Item `SELECT … FOR UPDATE`
2. Collection `SELECT … FOR UPDATE` (`collection_id` 있을 때)
3. `DISTINCT recommendation_history_id` (`ix_recommendation_history_items_item_id`)
4. History 부모 일괄 `DELETE` → items CASCADE
5. Item `DELETE` → legacy_import_items CASCADE
6. 잔여 Item `EXISTS`
7. 비어 있으면 Collection `DELETE`
8. `commit`

### 응답

- 성공 204 No Content (이력 수·Collection 자동 삭제 여부 Body 없음)
- 404 Item not found / 422 UUID / 409 IntegrityError 충돌

### 테스트·회귀

- Hard Delete·History·Legacy·Collection 자동 삭제·OpenAPI·IntegrityError→409
- 중간 실패 Monkeypatch 롤백 테스트는 테스트 nested transaction과 충돌하여 **IntegrityError→409**로 대체 (운영은 단일 Transaction + rollback)
- Backend 전체 **112 passed**
- Seed 읽기 Smoke: 7202 / 249 / 10 유지 (Seed Item 실제 삭제 없음)

---

## 27. D-6 구현 결과 (2026-07-22)

### 파일

- `backend/app/api/v1/collections.py` — `DELETE /collections/{collection_id}`
- `backend/app/services/catalog.py` — `delete_collection`
- `backend/tests/test_collection_delete_api.py`

### Lock·Query

1. Collection `SELECT … FOR UPDATE`
2. Item `EXISTS` (`collection_id` 기준; 다른 `user_id` 참조 시 500)
3. Item 있으면 **409** (DELETE·Commit 없음)
4. 빈 Collection `DELETE` → `legacy_import_collections` CASCADE / `recommendation_history.collection_id` SET NULL
5. `commit`

### 응답

- 성공 **204** No Content
- **404** Collection not found / **422** UUID / **409** Item 존재 또는 IntegrityError

### Item DELETE와 구분

| 경로 | Item 있을 때 | Item 0건 |
|------|-------------|----------|
| Item DELETE (마지막) | Item 삭제 후 Collection 자동 삭제 | — |
| Collection 직접 DELETE | **409** (Item·Collection 유지) | **204** |

### 테스트·회귀

- 빈 Collection 204·Item 409·unlink 금지·History SET NULL·Legacy CASCADE·IntegrityError→409·Item DELETE 회귀·OpenAPI
- Backend 전체 **128 passed**
- Seed 읽기 Smoke: 7202 / 249 / 10 유지 (Seed Collection 실제 삭제 없음)

### 잔여

- Collection POST/PATCH, Item POST/PATCH

---

## 28. D-7 Frontend 구현 결과 (2026-07-22)

### 파일

- `frontend/src/api/catalog.ts` — `deleteItem`, `deleteCollection`
- `frontend/src/api/deleteMessages.ts`
- `frontend/scripts/verify-delete-api.mjs`
- `frontend/src/app/App.tsx` — Dialog·origin 복귀·409 처리
- Hook 페이지 보정: `useItemsReadData`, `useCollectionsReadData`, `useCollectionItemsReadData`

### UX

- 비낙관적 삭제: 204 확인 후 복귀·재조회
- Item Dialog: 복구 불가·추천 이력·마지막 Collection 안내
- Collection: 빈 Collection만 Dialog, Item≥1 Toast 선차단
- 마지막 Item DELETE → Collection 404 → 목록 복귀

### 검증

- `npm run build` / `tsc --noEmit` / verify-delete-api script
- Seed DB 실제 DELETE 없음 (Mock·격리 script)
- Backend OpenAPI·128 passed 유지 (Backend 미변경)

---

## 29. D-8 최종 회귀·Smoke (2026-07-22)

### 검증

| 영역 | 결과 |
|------|------|
| Backend pytest | 128 passed |
| 삭제 관련 pytest | 66 passed |
| Ruff (삭제 변경 파일) | All checks passed |
| Ruff (전체) | 기존 11건 (D-8 무관, 미수정) |
| OpenAPI DELETE | 204/404/409/422, Body 없음 |
| Frontend verify/tsc/build | 통과 |
| 격리 DB HTTP Smoke | 28/28 (`scripts/d8_delete_smoke.py`) |
| Migration roundtrip (smoke DB) | 0004→0003→0004, `deleted_at` 없음 |
| Seed DB | 전후 수치 동일 (실DELETE 없음) |

### Seed DB 비파괴 (상세)

- 핵심 집계는 `GET /api/v1/summary` 및 DB 조회로 D-8 전후 동일함을 확인했다 (Items 7202, Collections 249, Categories 10, PLANNED 4708, COMPLETED 2494, linked 845).
- 보조 PowerShell `curl | python -c json.load` 명령은 셸 파이프·인코딩 문제로 exit 1이었으나, 제품 API·Seed 데이터 이상은 확인되지 않았다.

### 배포 판정

**PASS WITH NOTES** — 기능·계약·격리 Smoke 통과. Desktop/Mobile 브라우저 시각 검증은 수동 확인 권장.

### 잔여

- Item POST/PATCH, Collection Frontend 생성·수정, Bulk Delete, Vitest/RTL E2E

### C-1 (2026-07-22)

- `POST`/`PATCH /api/v1/collections` Backend 구현 완료
- 삭제 Transaction·FK·D-6 DELETE 계약 **변화 없음** (회귀 테스트 통과)
