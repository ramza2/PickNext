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

## 운영 Docker 이미지 (DPL-1)

Multi-stage Build: Node에서 `npm ci` + `npm run build` → Nginx가 `dist` 정적 파일만 제공합니다.

```bash
# 저장소 루트
docker build \
  --build-arg VITE_API_BASE_URL=/api/v1 \
  -t picknext-frontend:dpl1 \
  ./frontend
```

| 항목 | 값 |
| --- | --- |
| Build ARG / ENV | `VITE_API_BASE_URL` (기본 `/api/v1`) |
| Runtime | `nginx:1.28-alpine`, Port **80** |
| Health | `GET /health` → `200` `text/plain` `ok` |
| SPA | `try_files` → 없는 경로도 `index.html` |
| Asset Cache | `/assets/*` 장기 Cache · `index.html` No-cache |
| API Proxy | **없음** (Traefik이 `/`·`/api` 분기는 DPL-2·DPL-3) |

Vite 변수는 **Build-time**에 Bundle에 삽입됩니다. Browser에 공개되는 값만 넣고, Secret·TMDB Token은 넣지 않습니다.

단독 Container Smoke (Traefik·Compose Frontend 서비스 없이):

```bash
docker rm -f picknext-frontend-dpl1 2>/dev/null || true
docker run --rm -d \
  --name picknext-frontend-dpl1 \
  -p 127.0.0.1:5180:80 \
  picknext-frontend:dpl1

curl -i http://127.0.0.1:5180/
curl -i http://127.0.0.1:5180/health
curl -i http://127.0.0.1:5180/items   # SPA fallback → index.html
docker exec picknext-frontend-dpl1 nginx -t
docker rm -f picknext-frontend-dpl1
```

이 단독 실행에서는 Backend 라우팅이 없어 API 요청은 실패할 수 있습니다. 정적 HTML·JS·CSS 로딩만 확인합니다.

관련 파일: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`

## PWA (PWA-1)

설치 가능한 Web App Manifest + Service Worker(App Shell Precache) + 업데이트 안내 UX.

| 정책 | 내용 |
| --- | --- |
| Manifest | `name`/`short_name` PickNext · `display: standalone` · `start_url`/`scope` `/` |
| Theme | `theme_color` `#2563EB` · `background_color` `#F5F5F3` (앱 primary / background) |
| SW | `vite-plugin-pwa` `generateSW` · `registerType: prompt` |
| Precache | HTML·JS·CSS·아이콘 등 정적 Asset |
| API | Cache 금지 · `/api`·`/health` Navigation Fallback 제외 · NetworkOnly |
| Offline CRUD | **미지원** (오프라인 조회·쓰기·Background Sync·Push 없음) |
| Dev | `npm run dev`에서 Service Worker **비활성** |
| 운영 예정 | `https://picknext.ramza.duckdns.org/` |
| Nginx Header | **DPL-1A** — Manifest MIME·SW/아이콘 Cache 정책 적용 |

아이콘 원본: `public/pwa-source.svg` (AppLayout Target 마크 + primary `#2563EB`)

```bash
cd frontend
npm run generate-pwa-assets   # minimal-2023 → public/*.png · favicon.ico
npm run build
node scripts/verify-pwa-build.mjs
node scripts/verify-pwa-nginx.mjs
npm run preview -- --host 127.0.0.1 --port 4173
```

업데이트 UX: 새 SW 대기 시 「새 버전이 있습니다」 → **업데이트**(`updateServiceWorker(true)`) / **나중에**(Prompt만 닫기). 강제 Reload·autoUpdate 없음.

커스텀 설치 버튼(`beforeinstallprompt`)은 이번 범위가 아닙니다. Browser 기본 설치 UI를 사용합니다.

## PWA Nginx Header (DPL-1A)

운영 예정 주소: `https://picknext.ramza.duckdns.org/`

| 경로 | MIME / Cache |
| --- | --- |
| `/manifest.webmanifest` | `application/manifest+json` · `no-cache, must-revalidate` |
| `/sw.js` | JS · `no-store, no-cache, must-revalidate, max-age=0` |
| `/registerSW.js` | 현재 Build에 없음 → Location 미추가 (생성 시 `no-cache` 권장) |
| `/workbox-<hash>.js` | JS · `public, max-age=31536000, immutable` |
| 고정 PWA 아이콘·favicon | image · `public, max-age=86400, must-revalidate` |
| `/assets/<hash>.*` | `public, max-age=31536000, immutable` |
| `/index.html` | `no-store, no-cache, must-revalidate` |
| `/health` | `text/plain` · Cache 없음 |

Docker Header Smoke:

```bash
# 저장소 루트
docker build --build-arg VITE_API_BASE_URL=/api/v1 -t picknext-frontend:dpl1a ./frontend
docker rm -f picknext-frontend-dpl1a 2>/dev/null || true
docker run --rm -d --name picknext-frontend-dpl1a -p 127.0.0.1:5182:80 picknext-frontend:dpl1a

curl -I http://127.0.0.1:5182/manifest.webmanifest
curl -I http://127.0.0.1:5182/sw.js
curl -I http://127.0.0.1:5182/workbox-98f7a950.js   # 실제 hash로 교체
curl -I http://127.0.0.1:5182/pwa-192x192.png
docker exec picknext-frontend-dpl1a nginx -t
docker rm -f picknext-frontend-dpl1a
```

정적 설정 검사: `node scripts/verify-pwa-nginx.mjs` (HTTP Header의 최종 근거는 Docker curl).

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
| Item Detail | **API** (`GET /items/{id}`) · **생성·수정(I-2)** · **삭제(D-7)** · 상태 버튼 PATCH · Poster Placeholder |
| Collections 목록 | **API** (검색·페이지) · **생성(C-2)** |
| Collection 인라인 상세 / 소속 Item | **API** · **이름 수정(C-2)** · **삭제(D-7)** · Item 추가(I-2) · Item 행 「제거」= 연결 해제(I-3) · 빠른 상태(I-3) |
| History / Recommend / TMDB / Data / Settings | Mock |

API 오류 시 Mock으로 조용히 Fallback하지 않습니다.

## 현재 구조

```text
src/
├─ api/
│  ├─ client.ts
│  ├─ query.ts
│  ├─ catalog.ts
│  ├─ deleteMessages.ts
│  ├─ collectionWriteMessages.ts
│  └─ itemWriteMessages.ts
├─ types/
├─ mocks/
├─ utils/date.ts
├─ scripts/verify-collections-mapper.mjs
├─ scripts/verify-collection-detail-mapper.mjs
├─ scripts/verify-delete-api.mjs
├─ scripts/verify-collection-write-api.mjs
├─ scripts/verify-item-write-api.mjs
├─ scripts/verify-item-write-flow.mjs
├─ scripts/verify-collection-item-quick-actions.mjs
└─ app/
   ├─ App.tsx
   ├─ hooks/useHomeReadData.ts
   ├─ hooks/useItemsReadData.ts
   ├─ hooks/useItemDetail.ts
   ├─ hooks/useCollectionsReadData.ts
   ├─ hooks/useCollectionDetail.ts
   ├─ hooks/useCollectionItemsReadData.ts
   ├─ mappers/home.ts
   ├─ mappers/items.ts
   ├─ mappers/itemDetail.ts
   ├─ mappers/collections.ts
   ├─ presentation/categoryPresentation.ts
   ├─ pageTypes.ts
   └─ layout/AppLayout.tsx
```

다음: Bulk Delete / Drag & Drop / Category CRUD / History UI / TMDB / 인증 (별도). 자동화 Browser E2E는 선택.

현재 쓰기 상태:

```text
Collection CRUD 완료
Item CRUD 완료
Item 상태 변경 완료
Item Form Collection 연결·이동·해제 완료
Collection 상세 빠른 Item 연결 해제 완료
Collection 상세 빠른 상태 변경 완료
```

RC 검증 상태 (2026-07-23):

```text
RC-1 API·격리 DB 기본 쓰기 Release Candidate 검증: 완료(통과)
RC-2 브라우저 수동 QA: 완료(통과)
RC-2-A Items Warning·Form Inline Validation: 조치 완료 / PASS
실브라우저 Desktop 1440×900: 통과
실브라우저 Mobile 390×844: 통과
Browser Console / Network: 통과
최종 판정: PASS
```

지원 Viewport(디자인 기준선): Desktop 1440×900 · Mobile 390×844 (Bottom Nav).

상세: [`docs/06-frontend-integration-plan.md`](../docs/06-frontend-integration-plan.md)

## 검증

```bash
node scripts/verify-collection-item-quick-actions.mjs
node scripts/verify-item-write-api.mjs
node scripts/verify-item-write-flow.mjs
node scripts/verify-collection-write-api.mjs
node scripts/verify-delete-api.mjs
node scripts/verify-pwa-build.mjs
node scripts/verify-pwa-nginx.mjs
npx tsc --noEmit
npm run build
```

## 원칙

1. 기존 JSX·`className`을 최대한 유지한 채 기능만 연결한다.
2. Mock은 화면 단위로 점진 교체한다 (일괄 삭제 금지).
3. Backend API에 맞춘다는 이유로 화면 구조를 바꾸지 않는다.
