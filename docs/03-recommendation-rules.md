# 03. Recommendation Rules

## 알고리즘

추천 알고리즘은 **단순 랜덤 한 종류**만 사용한다. 가중치, 협업 필터링, 인기도 기반 로직은 초기 범위에 포함하지 않는다.

## 입력 조건

사용자는 다음을 선택한다.

1. 카테고리
2. 상태 필터
   - `PLANNED`
   - `COMPLETED`
   - `ALL`

## 후보 구성

- DB에 **존재하는 Item 전체**를 후보에 포함한다. Soft Delete / `deleted_at` 조건은 없다.
- **동일 컬렉션에 속한 항목은 하나의 추천 후보로 취급**한다.
- 컬렉션에 속하지 않은 항목은 각각 독립 후보다.

## 결과 반환

- 단일 항목 후보가 선택되면 해당 항목 1개를 반환한다.
- **시리즈(컬렉션)가 선택되면 해당 시리즈의 전체 항목을 결과로 반환**한다.

## 이력 저장 정책

- 랜덤 추천 실행만으로는 `recommendation_history`에 저장하지 않는다.
- 사용자가 **`이걸로 선택`**한 경우에만 이력을 저장한다.
- 이력에는 선택 시점의 `title_snapshot`과 `status_at_selection`을 함께 남긴다.

## 이력 활용

- 추천 이력에서 각 항목의 `item_id`로 상세 화면에 이동할 수 있어야 한다.
- 상세 화면에서 완료 상태(`PLANNED` ↔ `COMPLETED`)를 수정할 수 있어야 한다.
- Item Hard Delete(`DELETE /api/v1/items/{id}`, D-3~D-5 구현) 시 해당 Item을 포함한 `recommendation_history` **전체**와 연결 행·Snapshot을 함께 삭제한다.
- Item PATCH(`PATCH /api/v1/items/{id}`, I-1 구현) 및 Item Frontend 수정(I-2)은 `title_snapshot`·`status_at_selection` 등 추천 이력 Snapshot을 **수정하지 않는다**. Snapshot 갱신·History 삭제는 Item DELETE에서만 수행한다.
- 같은 History에 있던 다른 Item **본체**는 유지한다.
- 연결 행만 지우고 부모 History를 남기지 않는다.

> 참고: 실제 추천/선택 API는 이후 작업에서 구현한다. Item 삭제 Transaction은 구현됨.
