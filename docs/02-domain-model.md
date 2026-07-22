# 02. Domain Model

모든 주요 PK는 UUID다. 인증은 아직 없지만 다중 사용자를 고려해 주요 테이블은 `user_id`를 가진다.

## 테이블

### users

| 컬럼 | 설명 |
| --- | --- |
| id | UUID PK |
| email | 고유 |
| display_name | 표시 이름 |
| password_hash | 향후 인증용 |
| is_active | 활성 여부 |
| created_at / updated_at | 감사 시각 |

### categories

| 컬럼 | 설명 |
| --- | --- |
| id | UUID PK |
| user_id | 소유 사용자 |
| name | 카테고리 이름 |
| category_type | `MEDIA` / `BOOK` / `FOOD` / `GENERAL` |
| sort_order | 정렬 순서 |
| created_at / updated_at | 감사 시각 |

제약: `(user_id, name)` unique

### collections

동일 시리즈·작품군을 묶는다. 예: 터미네이터, 인디아나 존스, 선검기협전

제약: `(user_id, name)` unique

### items

| 컬럼 | 설명 |
| --- | --- |
| category_id | 소속 카테고리 |
| collection_id | 시리즈 연결 (nullable) |
| title | 제목 |
| status | `PLANNED` / `COMPLETED` |
| rating | 0.0~5.0, 0.5 단위 |
| progress_note | 회차·시즌·권수 등 |
| memo | 감상평·일반 메모 |
| deleted_at | 소프트 삭제 |

#### TMDB 연동 확장 (구현 전, Migration `0004` 예정)

Legacy Import 7,202건 및 직접 입력 Item은 외부 연동 정보 없이 `NULL`을 유지한다. 자동 TMDB 매칭은 하지 않는다.

| 컬럼 | 설명 |
| --- | --- |
| external_source | `TMDB` 또는 NULL |
| external_id | TMDB ID |
| external_media_type | `MOVIE` / `TV` / NULL |
| poster_path | TMDB `poster_path` (상대 경로) |
| overview | 줄거리 |
| release_date | 개봉일 또는 첫 방영일 |
| original_title | 원제 |
| external_rating | TMDB 평점 (`items.rating`과 별도, 선택) |

중복 정책: 활성 Item에 대해 `(user_id, external_source, external_media_type, external_id)` unique (부분 인덱스).

상세: [05-tmdb-integration-plan.md](./05-tmdb-integration-plan.md)

### recommendation_history

사용자가 `이걸로 선택`한 결과만 저장한다.

- `status_filter`: `PLANNED` / `COMPLETED` / `ALL`
- 단일 항목 선택 시 `collection_id`는 NULL

### recommendation_history_items

선택 결과에 포함된 실제 항목 목록.

- `item_id`: 현재 상세 화면 이동용
- `title_snapshot`: 추천 당시 제목 보존
- `status_at_selection`: 선택 시점 상태
- `sort_order`: 결과 내 순서

## 관계

- User 1:N Category / Collection / Item / RecommendationHistory
- Category 1:N Item
- Collection 1:N Item
- RecommendationHistory 1:N RecommendationHistoryItem
- Item 1:N RecommendationHistoryItem

## 삭제 정책

- Category / Collection에 연결된 Item이 있으면 연쇄 삭제하지 않는다. (`ON DELETE RESTRICT`)
- RecommendationHistory 삭제가 Item을 삭제하지 않는다.
- RecommendationHistoryItem → Item은 `RESTRICT`
- RecommendationHistoryItem → RecommendationHistory는 `CASCADE`
- Item은 `deleted_at` 기반 소프트 삭제를 기본으로 한다.
