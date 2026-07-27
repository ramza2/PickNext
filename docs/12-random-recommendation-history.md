# 12. Random Recommendation & History (REC-1)

> **상태:** 구현 완료 (Cursor 단계 — 격리 pytest·Frontend build 통과, Browser QA 대기)  
> **알고리즘:** 랜덤 **한 종류만** (순차·혼합·가중치·AI 없음)

## 개요

사용자는 Category와 상태 필터를 고른 뒤 랜덤 추천을 실행하고, 결과가 마음에 들면 **이걸로 선택**으로만 추천 이력을 남긴다.

```text
카테고리 선택
→ 상태 필터 (PLANNED / COMPLETED / ALL)
→ 랜덤 추천 실행  (이력 저장 안 함)
→ 다시 추천 (동일 조건 재실행)
→ 이걸로 선택     (Snapshot 이력 저장)
→ 추천 이력 목록·상세·삭제
```

## 후보 단위

| 조건 | 후보 |
| --- | --- |
| `collection_id IS NULL` | Item 1건 = 후보 1개 |
| `collection_id IS NOT NULL` | 동일 Collection = 후보 1개 |

Collection에 속한 Item을 개별 후보로 중복 포함하지 않는다.

후보가 구성되면 **매 요청마다 전체 Eligible 후보에서 독립적으로** 하나를 무작위 선택한다.
같은 Item·Collection이 연속으로 나올 수 있다.

## Collection 결과

Collection 후보가 선택되면 **현재 사용자의 해당 Collection 소속 Item 전체**를 반환한다.

- 선택 당시 Category·상태 필터와 다른 Item이 포함될 수 있다 (혼재 Category·status 허용).
- 각 Item의 실제 Category·status를 표시한다.
- 정렬: `Category.sort_order ASC` → `Item.created_at ASC` → `Item.id ASC`

## 추천 이력의 역할

추천 이력은 **기록·조회**만 한다.

- `이걸로 선택` Snapshot 저장
- 목록·상세·개별/전체 삭제
- Home **최근 선택** 표시 (`page_size=5`)

추천 이력은 다음 용도로 쓰지 않는다.

- 후보 제외 / 확률 조정 / 중복 회피 / 순서·Seed 결정

`이걸로 선택` 후에도 해당 Item·Collection은 다음 추천 후보에 그대로 포함된다.

Home의 **최근 선택 표시**와 예전의 **최근 선택 후보 제외**는 다른 개념이다. 후자는 제거됐다.

## API

| Method | Path | 설명 |
| --- | --- | --- |
| `POST` | `/api/v1/recommendations/random` | 랜덤 추천 (저장 없음) |
| `POST` | `/api/v1/recommendation-history` | 이걸로 선택 |
| `GET` | `/api/v1/recommendation-history` | 목록 (`page`, `page_size`) |
| `GET` | `/api/v1/recommendation-history/{id}` | 상세 |
| `DELETE` | `/api/v1/recommendation-history/{id}` | 개별 삭제 (204) |
| `DELETE` | `/api/v1/recommendation-history` | 전체 삭제 (`deleted_count`) |

모든 Endpoint는 인증 필수. 다른 사용자 리소스는 **404**.

## 스키마·Migration

기존 테이블을 그대로 사용한다. **신규 Migration 없음** (Alembic Head `0007_add_auth_tables`).

- `recommendation_history`: user, category, status_filter, collection_id, selected_at
- `recommendation_history_items`: item_id, title_snapshot, status_at_selection, sort_order

`recommendation_type` / SEQUENCE / MIX 컬럼은 추가하지 않는다.

## Item Hard Delete 연계

Item 삭제 시 해당 Item이 포함된 `RecommendationHistory` **부모 전체**를 삭제한다 (기존 D-3~D-5 정책 유지).  
`recommendation_history_items.item_id` FK는 **RESTRICT** 유지 (CASCADE로 바꾸지 않음).

## Frontend

- Recommend / History 메뉴 복원 (Desktop Sidebar · Mobile · More)
- Home: 빠른 추천 · 최근 선택 (History API `page_size=5`)
- Mock `HISTORY` / Frontend `Math.random` 미사용
- 로그아웃·401 시 추천·이력 State 초기화
- PWA: `/api/` NetworkOnly (AUTH-1 유지)

## 비범위

- 순차·혼합 추천, 추천 방식 UI
- React Router (NAV-1)
- 실DB Migration·운영 배포 (사용자 Browser QA 후)
