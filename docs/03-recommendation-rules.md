# 03. Recommendation Rules

## 알고리즘

추천 알고리즘은 **단순 랜덤 한 종류**만 사용한다.

구현하지 않는 것:

- 순차 추천 / 혼합 추천
- 가중치·협업 필터링·인기도·평점 가중·AI·TMDB 추천 API
- 추천 방식 선택 UI / `SEQUENCE` / `MIX` / `resolved_mode`

## 입력 조건

1. 카테고리 (현재 로그인 사용자 소유)
2. 상태 필터
   - `PLANNED` → `Item.status = PLANNED`
   - `COMPLETED` → `Item.status = COMPLETED`
   - `ALL` → 상태 조건 없음

## 후보 구성

- 현재 사용자 Item만 사용한다.
- **동일 Collection에 속한 항목은 하나의 추천 후보**로 취급한다.
- Collection에 속하지 않은 항목은 각각 독립 후보다.
- Collection 소속 Item을 개별 후보로 중복 포함하지 않는다.

후보가 구성되면 **매 요청마다 전체 Eligible 후보에서 독립적으로** 하나를 무작위 선택한다.

## 결과 반환

- 단일 Item 후보 → Item 1건
- Collection 후보 → 해당 Collection의 **전체 Item** (혼재 Category·status 가능)
- 후보 0건 → HTTP 200 + 빈 `items` (`eligible_candidate_count: 0`)

## 추천 이력과 후보의 관계

- 추천 이력은 **기록·조회** 용도만 사용한다 (목록·상세·Home 최근 선택·삭제).
- 추천 이력·이전 추천 결과는 **후보 선정에 영향을 주지 않는다**.
- 같은 Item 또는 Collection이 연속으로 추천될 수 있다.
- `이걸로 선택`으로 저장한 뒤에도 해당 후보는 다음 추천에 그대로 포함된다.

Home의 **최근 선택**은 화면 표시 기능이며, 후보 제외와 무관하다.

## 이력 저장 정책

- 랜덤 추천 실행만으로는 `recommendation_history`에 저장하지 않는다.
- 사용자가 **`이걸로 선택`**한 경우에만 Snapshot 이력을 저장한다.
- Snapshot: `title_snapshot`, `status_at_selection`, `sort_order`
- Frontend가 Item 목록을 보내 저장하지 않는다. Backend가 재조회한다.

## 이력 활용

- 이력 `item_id`로 Item 상세 이동
- Item Hard Delete 시 해당 Item을 포함한 History **부모 전체** 삭제
- Item PATCH는 Snapshot을 수정하지 않는다
- Collection 삭제 정책·`collection_id ON DELETE SET NULL`는 기존과 동일

## API (요약)

상세: [12-random-recommendation-history.md](./12-random-recommendation-history.md)

| Method | Path |
| --- | --- |
| `POST` | `/api/v1/recommendations/random` |
| `POST` | `/api/v1/recommendation-history` |
| `GET` | `/api/v1/recommendation-history` |
| `GET` | `/api/v1/recommendation-history/{id}` |
| `DELETE` | `/api/v1/recommendation-history/{id}` |
| `DELETE` | `/api/v1/recommendation-history` |
