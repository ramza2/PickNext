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

## 이번 단계 범위

- Backend·DB 기반 구성
- 도메인 모델과 Migration
- 개발용 Seed
- Health Check API
- Docker Compose 개발 환경

## 비범위 (이번 단계)

- Frontend / PWA
- 인증
- CRUD·추천 API
- Legacy import 실행
- Traefik / 운영 배포
