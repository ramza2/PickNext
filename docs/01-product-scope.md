# 01. Product Scope

## 목적

PickNext는 사용자가 관심 있는 항목을 카테고리별로 기록하고, 조건에 맞는 후보 중 하나를 랜덤으로 추천받아 선택하는 서비스다.

영화에 한정하지 않으며 드라마, 애니메이션, 예능, 만화책, 음식 등 다양한 관심사를 동일한 구조로 관리한다.

## 핵심 사용자 흐름

1. 카테고리를 선택한다.
2. 상태 필터(`PLANNED` / `COMPLETED` / `ALL`)를 선택한다.
3. 랜덤 추천을 실행해 후보를 확인한다. (필요 시 여러 번)
4. `이걸로 선택`으로 최종 결정을 저장한다.
5. 추천 이력에서 항목 상세로 이동해 완료 상태 등을 갱신한다.

## 완료된 범위

- Backend·DB 기반 구성, Alembic Migration, 개발용 Seed
- Health Check API, Docker Compose 개발 환경
- Legacy Import 및 3.5차 데이터 보정 (Item 7,202건)
- Figma Make Frontend 기준선
- TMDB 연동 기획 — [05-tmdb-integration-plan.md](./05-tmdb-integration-plan.md)
- Category·Item 읽기 API 계약 — [07-read-api-contract.md](./07-read-api-contract.md)
- **Category·Item 읽기 API 구현** (`/summary`, `/categories`, `/items`)

## 현재 단계

- 읽기 API 안정화 및 Frontend 읽기 연동 준비

## 후속 범위

- Frontend 읽기 연동 (Mock → API 점진 교체)
- Category·Item·Collection CRUD API
- 랜덤 추천·추천 이력 API
- TMDB Migration·검색·등록
- Export·Import
- 인증
- Traefik / 운영 배포
