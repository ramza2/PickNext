# Frontend (Figma Make 기준선)

PickNext UI 프로토타입입니다. Figma Make에서 생성한 화면·Tailwind·레이아웃을 **디자인 기준선**으로 유지합니다.

임의로 색상·Sidebar·Bottom Nav·카드·Typography를 재설계하지 않습니다.

## 실행

요구: Node.js 20+ (권장 LTS)

Backend가 `http://127.0.0.1:8002`에서 동작 중이어야 합니다 (Docker Compose 권장).

```bash
# 저장소 루트
docker compose up -d

# Frontend
cd frontend
cp .env.example .env   # 선택 — 기본값으로도 동작
npm install
npm run dev
```

| 항목 | 값 |
| --- | --- |
| Frontend Dev | http://127.0.0.1:5173 |
| Backend | http://127.0.0.1:8002 |
| API Base Path | `/api/v1` (`VITE_API_BASE_URL`) |
| Proxy 대상 | `VITE_API_PROXY_TARGET` (기본 `http://127.0.0.1:8002`) |

개발 중 Frontend의 `/api/*` 요청은 Vite Proxy가 Backend로 전달합니다. Path rewrite 없음.

프로덕션 빌드: `npm run build` → `dist/`  
운영에서는 동일 Origin의 `/api/v1`을 기본으로 사용합니다.

## 환경변수 (`.env.example`)

```env
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY_TARGET=http://127.0.0.1:8002
```

Secret·TMDB Token은 Frontend 환경변수에 두지 않습니다.

## 화면별 데이터 출처

| 화면 | 출처 |
| --- | --- |
| Home — Summary / Categories / 최근 등록 | **API** |
| Home — 빠른 추천 / 최근 선택 이력 | Mock |
| Items — Category / 목록 검색·필터·정렬·페이지 | **API** |
| Item Detail | **API** (`GET /items/{id}`) · Poster Placeholder · 수정·삭제·상태 변경 미연동 |
| Collections 목록 | **API** (검색·페이지) |
| Collection 인라인 상세 / 소속 Item | 메타만 표시 · Item 연동 대기 (B-3b) |
| History / Recommend / TMDB / Data / Settings | Mock |

API 오류 시 Mock으로 조용히 Fallback하지 않습니다.

## 현재 구조

```text
src/
├─ api/
├─ types/
├─ mocks/
├─ utils/date.ts
├─ scripts/verify-collections-mapper.mjs
└─ app/
   ├─ App.tsx
   ├─ hooks/useHomeReadData.ts
   ├─ hooks/useItemsReadData.ts
   ├─ hooks/useItemDetail.ts
   ├─ hooks/useCollectionsReadData.ts
   ├─ mappers/home.ts
   ├─ mappers/items.ts
   ├─ mappers/itemDetail.ts
   ├─ mappers/collections.ts
   ├─ presentation/categoryPresentation.ts
   ├─ pageTypes.ts
   └─ layout/AppLayout.tsx
```

다음: Collection 인라인 상세 + 소속 Item 읽기 API 연동 (B-3b).

상세: [`docs/06-frontend-integration-plan.md`](../docs/06-frontend-integration-plan.md)

## 원칙

1. 기존 JSX·`className`을 최대한 유지한 채 기능만 연결한다.
2. Mock은 화면 단위로 점진 교체한다 (일괄 삭제 금지).
3. Backend API에 맞춘다는 이유로 화면 구조를 바꾸지 않는다.
