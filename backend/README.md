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

테스트: `docker compose exec backend pytest -q`
