# PickNext backend package

## API (v1, 구현 완료)

| Method | Path | 비고 |
|--------|------|------|
| GET | `/api/v1/summary` | 홈 집계 |
| GET | `/api/v1/categories` | Category 목록 |
| GET | `/api/v1/items` | Item 목록 |
| GET | `/api/v1/items/{item_id}` | Item 상세 |
| POST | `/api/v1/items` | 생성 (I-1) |
| PATCH | `/api/v1/items/{item_id}` | 수정 (I-1) |
| DELETE | `/api/v1/items/{item_id}` | Hard Delete |
| GET | `/api/v1/collections` | Collection 목록 |
| GET | `/api/v1/collections/{collection_id}` | Collection 상세 |
| POST | `/api/v1/collections` | 생성 (C-1) |
| PATCH | `/api/v1/collections/{collection_id}` | 이름 수정 (C-1) |
| DELETE | `/api/v1/collections/{collection_id}` | 빈 Collection만 204 |
| POST | `/api/v1/recommendations/random` | 랜덤 추천 (저장 없음, REC-1) |
| GET | `/api/v1/recommendation-history` | 이력 목록 |
| GET | `/api/v1/recommendation-history/{id}` | 이력 상세 |
| POST | `/api/v1/recommendation-history` | 이걸로 선택 |
| DELETE | `/api/v1/recommendation-history/{id}` | 개별 삭제 204 |
| DELETE | `/api/v1/recommendation-history` | 전체 삭제 |

테스트: 격리 DB 권장 — `POSTGRES_DB=picknext_rec1_test docker compose exec -e POSTGRES_DB=picknext_rec1_test backend pytest -q`
