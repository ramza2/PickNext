# 14. Collection 관리 UX (COL-1)

> **상태:** Cursor 단계 구현 완료 (Browser/PWA 수동 QA · Commit · Push · 운영 배포는 미수행)  
> **범위:** Item ↔ Collection 편입·변경·신규 생성, Collection 상세 기존 Item Bulk 추가  
> **비범위:** 다대다 전환, Drag & Drop, 즐겨찾기, NAV-2, 운영 배포

## 1. 데이터 모델

- `items.collection_id` nullable FK (Item 1 → Collection 최대 1)
- Collection `(user_id, name)` Unique
- 신규 Migration 없음 (Alembic Head `0007_add_auth_tables` 유지)

## 2. API

| 용도 | Endpoint | 비고 |
| --- | --- | --- |
| Collection 검색 | `GET /collections?search=&sort=name&order=asc` | 기존 |
| Item Collection 변경 | `PATCH /items/{id}` `{ "collection_id": uuid\|null }` | 기존 partial PATCH |
| Collection 생성 | `POST /collections` | 기존 |
| 미지정 Item 검색 | `GET /items?has_collection=false&search=&category_id=&status=` | 기존 |
| Bulk 편입 | `POST /collections/{id}/items` `{ "item_ids": [...] }` | **COL-1 신규** |

### Bulk 규칙

- 대상 Collection · 모든 Item은 현재 사용자 소유 (아니면 404, 존재 여부 비노출)
- `collection_id IS NULL`만 신규 편입
- 이미 대상 Collection → idempotent no-op
- 다른 Collection 소속 Item 포함 → **409**, Transaction 전체 롤백
- 응답: `{ "added_count": n }`

## 3. Frontend UX

### Item 상세

- Collection 없음 → 버튼 **Collection에 추가**
- Collection 있음 → 버튼 **Collection 변경**
- 전용 Modal (`CollectionPickerModal`): 검색 List · 선택 · 새 Collection 생성 후 자동 편입 · 제거
- 전체 Item 수정 Modal을 Collection 이동 용도로 열지 않음
- **ITEM-UX-2:** Item 직접 추가·수정·TMDB 일반 등록 Form도 동일 검색형 Picker (`mode="select"`)로 통일. Item 상세는 기존 Immediate PATCH (`mode="immediate"`) 유지.

### Collection 상세

- **기존 항목 추가** → `AddExistingItemsModal`
- 서버 검색 + Category/Status Filter + `has_collection=false`
- 다중 선택 · Pagination 간 선택 유지 · Bulk 1회 호출

## 4. Overlay Navigation (NAV-1A 확장)

```typescript
type AppOverlay =
  | { type: "item-edit"; itemId: string }
  | { type: "item-collection-picker"; itemId: string }
  | { type: "collection-add-existing-items"; collectionId: string };
```

- Browser Back / PWA Back → Modal만 닫힘
- X · 취소 · Escape · Backdrop → `closeOverlay()` 공통
- Overlay State에는 type + id만 저장 (검색·선택·Form은 in-memory)
- Overlay 종료 시 Local Modal State 초기화

## 5. 수동 QA 체크리스트

1. 미지정 Item → Collection에 추가 → 검색 → 추가 → 상세 갱신  
2. Collection A → 변경 → B  
3. 새 Collection 만들기 → 생성 후 추가 (재검색 불필요)  
4. Collection에서 제거 → 미지정  
5. Collection 상세 → 기존 항목 추가 → 다중 선택 → Bulk  
6. Browser/PWA Back으로 Modal만 닫힘 · Forward 재오픈 허용  
7. 검색 Race: 최종 검색어만 표시  
