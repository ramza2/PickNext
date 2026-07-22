# 06. Frontend Integration Plan (Figma Make 기준선)

> **상태:** Frontend D-7 삭제 연동 완료 · D-8 회귀·Smoke 검증 완료 · **C-1 Collection POST/PATCH Backend 완료 (2026-07-22)**
> **기준선:** `frontend/` Figma Make 프로토타입 (디자인·DOM·Tailwind 유지)  
> **비범위 (잔여):** Collection·Item Frontend 생성·수정, Item POST/PATCH, History/추천/TMDB, React Router, App.tsx Page 분리

## 1. 실행·빌드 확인 결과

| 항목 | 결과 |
| --- | --- |
| 패키지 매니저 | npm (Node.js LTS) |
| `npm install` | 성공 |
| `npm run build` | **성공** (`vite build`) |
| 산출물 | `frontend/dist/` |
| Dev 서버 | `npm run dev` → `http://127.0.0.1:5173` |
| Vite `/api` Proxy | `VITE_API_PROXY_TARGET` → `http://127.0.0.1:8002` (path rewrite 없음) |

### Phase B-1에서 추가·변경한 파일 (디자인 변경 없음)

| 파일 | 변경 |
| --- | --- |
| `vite.config.ts` | `/api` Proxy 추가 (기존 plugin·alias 유지) |
| `.env.example` | `VITE_API_BASE_URL`, `VITE_API_PROXY_TARGET` |
| `src/vite-env.d.ts` | Vite env 타입 |
| `src/types/api.ts` | Backend 읽기 API DTO (`Api*` prefix) |
| `src/types/mock.ts` | Figma Mock 전용 타입 |
| `src/api/client.ts` | Native fetch + `ApiError` |
| `src/api/query.ts` | Query string 직렬화 (`false`/`0` 유지) |
| `src/api/catalog.ts` | `getSummary`/`getCategories`/`getItems`/`getItem` |
| `src/mocks/data.tsx` | Mock 상수 이동 (값 불변) |
| `src/app/pageTypes.ts` | `Page` union |
| `src/app/layout/AppLayout.tsx` | Sidebar·Top Bar·Mobile Nav·More Sheet |
| `src/app/App.tsx` | Mock/Layout import로 교체, 화면·모달 유지 |

## 2. 현재 코드 구조

```text
frontend/
├─ .env.example
├─ vite.config.ts
└─ src/
   ├─ main.tsx
   ├─ vite-env.d.ts
   ├─ api/
   │  ├─ client.ts
   │  ├─ query.ts
   │  └─ catalog.ts
   ├─ types/
   │  ├─ api.ts
   │  └─ mock.ts
   ├─ mocks/
   │  └─ data.tsx
   ├─ app/
   │  ├─ App.tsx               # 화면·모달 (Home만 읽기 API)
   │  ├─ pageTypes.ts
   │  ├─ hooks/useHomeReadData.ts
   │  ├─ mappers/home.ts
   │  ├─ presentation/categoryPresentation.ts
   │  ├─ layout/AppLayout.tsx
   │  └─ components/
   ├─ utils/date.ts
   └─ styles/
```

라우팅은 **react-router 미사용**. `useState<Page>`로 화면 전환.

디자인 토큰: `src/styles/theme.css` (`--primary: #2563EB`, `--background: #F5F5F3` 등).

**Home·Items 목록·Item Detail·Collection 목록·Collection 상세**는 Backend 읽기 API로 표시한다. **Item·Collection Hard Delete(D-7)** 는 Backend DELETE API와 Confirm Dialog로 연동됐다. 추천·History·TMDB·Item/Collection POST·PATCH는 Mock 또는 대기. API 오류 시 Mock으로 Fallback하지 않는다.

## 3. 화면 목록

| Page id | 화면 | 구현 위치 (App.tsx) | 라우트 후보 |
| --- | --- | --- | --- |
| `home` | 홈 (요약·빠른 추천·최근 항목) | `HomePage` | `/` |
| `search` | TMDB 영화·드라마 검색 | `SearchPage` | `/search` |
| `recommend` | 랜덤 추천 (setup/result/complete) | `RecommendPage` | `/recommend` |
| `items` | 전체 항목 (카드/테이블·필터·페이지) | `ItemsPage` | `/items` |
| `item-detail` | 항목 상세 | `ItemDetailPage` | `/items/:id` |
| `collections` | Collection 목록 + **인라인 상세** | `CollectionsPage` | `/collections`, `/collections/:id` |
| `history` | 추천 이력 목록 | `HistoryPage` | `/history` |
| `history-detail` | 추천 이력 상세 | `HistoryDetailPage` | `/history/:id` |
| `data` | 데이터 내보내기·가져오기 | `DataPage` | `/data` |
| `settings` | 설정 | `SettingsPage` | `/settings` |
| `category-manage` | Category 관리 | `CategoryManagePage` | `/settings/categories` |

모달/오버레이 (페이지 아님):

- `TMDBDetailPanel` — 검색 상세 미리보기
- `TMDBRegisterForm` — 등록 확인 Form
- `ItemFormModal` — 직접 추가·수정
- `ConfirmModal` — 완료/되돌리기/삭제 확인
- `Toast` — 하단 토스트
- Mobile More Sheet — 하단 네비 「더보기」

레이아웃 (`AppLayout`):

- Desktop Sidebar (`lg:`)
- Top Bar
- Mobile Bottom Navigation + More Sheet

## 4. Component 목록 (App.tsx 내부)

### 공통 Atom

| Component | 역할 |
| --- | --- |
| `StarRating` | 읽기 전용 별점 (정수 별 UI) |
| `StarPicker` | 편집용 별점 (**현재 1점 단위**, 0.5 미지원) |
| `StatusBadge` | PLANNED/COMPLETED |
| `CategoryBadge` | Category 색상 뱃지 |
| `Poster` | 이미지 또는 이니셜 Placeholder |
| `ProgressBar` | Collection 진행률 |
| `Toast` | 성공 메시지 |

### 화면·모달

위 화면 표 + `TMDBDetailPanel`, `TMDBRegisterForm`, `ItemFormModal`, `ConfirmModal`

### shadcn `components/ui/*`

설치된 프리셋 다수. **현재 App.tsx UI는 대부분 raw Tailwind button/div**이며 shadcn Button 등은 거의 사용하지 않음. 유지하되 디자인 교체용으로 쓰지 않는다.

## 5. Mock 데이터

| 상수 | 위치 | 규모 | 용도 |
| --- | --- | --- | --- |
| `CATEGORIES` | `src/mocks/data.tsx` | 10개 | Seed Category와 이름 일치, id는 `movie`/`kdrama` 등 문자열 |
| `ITEMS` | 〃 | 40건 | 목록·추천·상세·홈 요약 |
| `COLLECTIONS` | 〃 | 8개 | Collection 목록·추천 후보 |
| `HISTORY` | 〃 | 5건 | 추천 이력 |
| `TMDB_RESULTS` | 〃 | 8건 | 검색 Mock (Unsplash 포스터 URL) |
| `MOCK_FILE` | 〃 | 1건 | Export/Import UI 데모 (items: 7202) |

홈 통계는 `CATEGORIES.reduce(...total)` 등 **Mock 배열 집계**를 사용한다. 실제 Backend 집계와 교체는 Phase B-2.

## 6. 동작 / 미동작·허수 버튼

### 동작하는 Mock UX

- Sidebar / Mobile Nav / More Sheet 화면 전환
- 홈 → 추천·검색·항목 추가·최근 목록 이동
- TMDB 검색 필터·상세·등록 Form (로컬 state + toast)
- 랜덤 추천 pool 구성·뽑기·선택 확인·complete (로컬)
- 항목 목록 필터·페이지·상세 이동
- Collection 목록 → 상세 인라인, 삭제 toast
- 이력 목록 → 상세, 삭제 toast
- Import 마법사 단계 UI (파일 실체 없음)
- Item/Category Form 저장 toast (DB 반영 없음)

### 미동작·부분 동작 (클릭해도 실질 효과 없음 또는 toast만)

| 위치 | 요소 | 상태 |
| --- | --- | --- |
| Top Bar | 검색 아이콘 | onClick 없음 |
| Recommend complete | 「완료 처리」「상세보기」 | onClick 없음 |
| Collection 상세 | Shuffle·Edit | onClick 없음 |
| Collection 상세 | 「TMDB 검색 후 추가」「직접 추가」 | onClick 없음 |
| Collection 항목 행 | 「완료」「제거」 | onClick 없음 |
| Collection 목록 | 「추가」 | onClick 없음 |
| Items 카드/테이블 | MoreVertical 메뉴 | 메뉴 미구현 |
| Data | 「데이터 내보내기」 | 다운로드 없음 |
| Data | 파일 선택 | 실파일 없이 Mock 플래그 |
| Settings | 대부분 행 | 화면/저장 없음 (Category 관리만 이동) |
| Settings / More | 로그아웃 | 동작 없음 |
| Category 관리 | GripVertical 드래그 | 시각만 |
| Category 저장/삭제 | toast만, 배열 미갱신 | |
| TMDB 등록·Item 저장 | toast만, ITEMS 미갱신 | |
| Recommend 「이걸로 선택」 | HISTORY 배열 미갱신 | |

## 7. 실제 기획과의 Gap

| 기획 | Figma Mock 현황 | 연동 시 조치 |
| --- | --- | --- |
| Collection = 추천 후보 1개, 소속 Item 개별 제외 | RecommendPage `buildPool`에 **이미 반영** | Backend API와 동일 규칙 유지 |
| 최근 선택 제외 (Item+Collection) | Item만 `HISTORY.slice(0,3)` 체크, Collection 제외 미흡 | API `exclude_recent`에 맡김 |
| TMDB 등록 Form + Category 확인 | UI 존재, 저장은 toast | `POST /items/from-tmdb` |
| 새 Collection 생성 | 등록 Form에 기존 Collection 선택만 | Form에 「새 Collection」 옵션 추가 (UI 확장 최소) |
| 평점 0.5 단위 | StarPicker **정수만** | 0.5 UI로 보정 (시각 동일 계열) |
| 미평가 표시 | Mock은 `!rating`으로 평가 없음 | **현재 API는 `rating=0.0`을 숫자로 반환** → FE가 `0.0`을 「평가 없음」으로 표시. `null` 미사용. 진짜 0점과의 구분은 **후속**에서 `rating` nullable Migration을 별도 검토 |
| 이력 Snapshot | Mock title 문자열 | Backend history + snapshot |
| 통계 Backend 집계 | **Home: API Summary/Categories 연동 완료** | Items 등 나머지 화면은 후속 |
| Legacy 7202건, poster NULL | Home 최근 등록은 API + Placeholder | 목록 API + Placeholder 유지 |
| Category UUID | Mock string id | API UUID 그대로 사용 (이름 slug 금지) |
| react-router 미사용 | state 전환 | 점진적 Route 도입 |

## 8. Backend API 연동 단계 계획

디자인을 바꾸지 않고 **Mock → API를 화면 단위로** 교체한다.

### Phase B-1 — 구조 준비 ✅ 완료

1. Vite proxy: `/api` → Backend (`127.0.0.1:8002`)
2. `src/api/client.ts`, `src/types/api.ts` (Backend DTO)
3. Mock을 `src/mocks/`로 **이동만** (App에서 import) — 동작 동일
4. `AppLayout` 추출 (Sidebar/Top/Bottom JSX·className 그대로)
5. Catalog 읽기 함수 준비 (화면 미호출)

### Phase B-2a — 홈 읽기 API ✅ 완료

- Summary / Categories / 최근 등록(`items?page=1&page_size=5&sort=created_at&order=desc`)
- Category Presentation Map (이름 → 아이콘·색상)
- 섹션별 Loading·Error·Empty, 부분 실패, Abort
- 빠른 추천·History·기타 화면은 Mock 유지
- 최근 등록 카드는 **클릭 없음**(원본과 동일). 상세 API 미연결

### Phase B-2b — 전체 항목 목록 ✅ 완료

- `GET /items` 서버 측 검색·필터·정렬·페이지네이션
- Category UUID 필터 (`GET /categories`)
- 카드·테이블 동일 API 데이터, View 전환 시 재호출 없음
- Loading·Error·Empty, Abort·Race 방지
- 클릭 시 상세 API 미연결 (Toast 안내)
- Mock 제목 매칭 없음

### Phase B-2c — Item 상세 ✅ 완료

- Items 카드·테이블 / Home 최근 등록 → UUID로 Detail 이동
- `GET /items/{item_id}` + Loading·404·Error·재시도·Abort
- Origin 기반 뒤로가기 (Items ↔ Home)
- Items 검색·필터·정렬·페이지·View Snapshot 보존
- 수정·상태 버튼은 안내 Toast (POST·PATCH 미연동)
- **삭제(D-7):** `DELETE /items/{id}` Confirm Dialog + origin별 복귀·재조회
- Mock 제목 매칭 없음

### Phase D-7 — Item·Collection 삭제 ✅ 완료 (2026-07-22)

- `deleteItem` / `deleteCollection` API Client (204 No Content)
- Item 상세·Collection 상세 기존 삭제 버튼 → Confirm Dialog
- Item: 추천 이력·마지막 Collection 자동 삭제 안내
- Collection: `item_count > 0` 사전 Toast 차단, Backend 409 후 재조회
- Collection 상세 Item 행 「제거」: 연결 해제 미구현 Toast 유지 (Hard Delete 미연결)
- origin(home/items/collections)별 복귀, Snapshot·페이지 보존, 마지막 페이지 보정
- `scripts/verify-delete-api.mjs` (Fetch Mock)
- D-8: Backend 격리 DB Smoke 28/28, Seed 비파괴, build/tsc 통과

### 다음 권장

```text
Collection Frontend 생성·수정 Dialog 연동
Item POST/PATCH (생성·수정·상태·연결 해제)
```

### Phase C-1 — Collection POST/PATCH Backend ✅ 완료 (2026-07-22)

- `POST /api/v1/collections` — 201 + `CollectionResponse`, Trim·200자·동일 사용자 409
- `PATCH /api/v1/collections/{collection_id}` — 200 + `CollectionResponse`, FOR UPDATE·no-op·409
- Frontend 생성·수정 UI는 **미연동** (후속)
- D-6 DELETE 계약 회귀 유지 (pytest 159 passed)

### Phase C — 쓰기·추천·TMDB

9. Item 생성/수정/삭제, 상태 전환
10. 랜덤 추천 API + 「이걸로 선택」이력
11. TMDB search/detail/from-tmdb (등록 Form 유지)
12. Collection CRUD, Category 관리

### Phase D — 데이터·설정·마무리

13. Export/Import 실파일
14. Settings 영속화
15. Route 도입, 큰 화면 파일 분리 (JSX/className 보존)
16. Form 검증·API 오류 toast/배너
17. Mock 잔여 제거 (단계적)

### 현재 Backend 구현 완료 API

```text
GET /api/v1/summary
GET /api/v1/categories
GET /api/v1/items
GET /api/v1/items/{item_id}
GET /api/v1/collections
GET /api/v1/collections/{collection_id}
POST /api/v1/collections
PATCH /api/v1/collections/{collection_id}
DELETE /api/v1/items/{item_id}
DELETE /api/v1/collections/{collection_id}
```

### Frontend 연동 현황

| 영역 | 상태 |
| --- | --- |
| Home Summary / Categories / 최근 등록 | ✅ API |
| Home 빠른 추천 / 최근 선택 | Mock |
| Items 목록 | ✅ API |
| Item 상세 | ✅ API · **삭제(D-7)** |
| Collections 목록 | ✅ API (B-3a) |
| Collections 인라인 상세 · 소속 Item | ✅ API (B-3b) · **Collection 삭제(D-7)** |
| Item·Collection DELETE UI | ✅ D-7 · D-8 Smoke 검증 |
| Collection POST/PATCH Backend | ✅ C-1 (Frontend 연동 대기) |
| History / TMDB / Recommend | Mock |
| React Router / Page 분리 | 미완료 |
| Item POST/PATCH·Frontend Collection 생성·수정 | 미완료 |

## 9. 위험 요소

| 위험 | 설명 | 완화 |
| --- | --- | --- |
| App.tsx 단일 거대 파일 | 2,000+줄, 분리 시 디자인 회귀 | 화면 단위 복사 분리, 시각 비교 |
| Category id 불일치 | Mock slug(`movie`)와 API UUID 구조가 다름 | API에서 로드한 Category의 UUID를 사용하고, 빠른 추천 Preset만 Category 이름으로 런타임 Resolve. DB 관계·API 파라미터에는 항상 UUID를 쓰고, 이름은 Preset→UUID 변환에만 사용. Seed 고정 UUID는 사용하지 않음 |
| react는 peer였음 | 설치 누락 가능 | dependencies로 수정 완료 |
| shadcn vs raw Tailwind | 혼용 시 스타일 불일치 | App 기존 className 유지, shadcn 강제 적용 금지 |
| StarPicker 0.5 | 기획과 불일치 | 최소 UI 보정, 색·크기 유지 |
| TMDB 포스터 Unsplash | 실제 poster_path와 다름 | Backend image base URL 조합 |
| `frontend/PickNext.zip` | 미추적 zip | gitignore 권장, 커밋 금지 |
| npm audit high | vite 관련 가능 | 디자인 단계에서는 강제 upgrade 보류 |
| Docker Desktop 미기동 | Backend 연동 테스트 시 필요 | compose up 후 proxy |

## 10. 다음 작업 순서

```text
Collection Frontend 생성·수정 연동 — Item POST/PATCH Backend
```

**금지 유지:** 새 React 프로젝트, App 전면 재작성, Tailwind/색상 체계 교체, Mock 일괄 삭제.
