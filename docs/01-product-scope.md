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
- TMDB 연동 · Item 쓰기 · Collection 쓰기 · Hard Delete
- Session Cookie 인증 (AUTH-1)
- **랜덤 추천·추천 이력 (REC-1)** — [12-random-recommendation-history.md](./12-random-recommendation-history.md)

## 현재 단계

- REC-1 Browser QA · 운영 적용 준비

## 후속 범위

- 브라우저·PWA 백버튼 (NAV-1)
- Category 쓰기 CRUD UI
- Export·Import
- Traefik ACME / 공인 DNS (DPL-4)
