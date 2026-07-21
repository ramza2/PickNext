# 04. Legacy Migration

기존 Android MovieManager 데이터를 PickNext로 옮기기 위한 정책이다.

## 이전 대상

- 이전 대상 파일: 기존 `movie.json`
- `log.json`은 이전하지 않는다.

## 카테고리

- 운영/개발 모두 Seed 카테고리를 사용한다.
- legacy 파일의 카테고리 체계를 그대로 복제하지 않는다.
- 항목은 Seed된 카테고리 중 적절한 곳으로 매핑한다.

## ID / 스키마 정책

- 운영 DB에 `legacy_id` 컬럼을 만들지 않는다.
- 이전은 일회성 스크립트로 수행하며, 변환 결과는 신규 UUID PK를 사용한다.

## series 필드 해석

기존 `series`에는 작품군 이름과 시청 회차 정보가 혼재되어 있다.

이전 시에는 다음을 분리해야 한다.

- 작품군 이름 → `collections.name` 및 `items.collection_id`
- 시청 회차/진행 정보 → `items.progress_note`

단순 문자열 복사는 금지하고, 규칙 기반 파싱/매핑이 필요하다.

## 구현 시점

- 실제 이전 스크립트는 **다음 작업**에서 구현한다.
- 이번 단계에서는 스키마와 정책을 문서화만 한다.
