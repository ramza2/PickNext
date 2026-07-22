# 06. Frontend Integration Plan (Figma Make 기준선)

> **상태:** 1단계 완료 — 실행·빌드 확인, 구조 분석, 연동 계획  
> **기준선:** `frontend/` Figma Make 프로토타입 (디자인·DOM·Tailwind 유지)  
> **비범위 (이번 단계):** API 전면 연동, App.tsx 전면 리팩터링, UI 재설계

## 1. 실행·빌드 확인 결과

| 항목 | 결과 |
| --- | --- |
| 패키지 매니저 | npm (Node.js LTS 24.18.0) |
| `npm install` | 성공 (288 packages) |
| `npm run build` | **성공** (`vite build`, ~3.7s) |
| 산출물 | `frontend/dist/` |
| Dev 서버 | `npm run dev` → `http://127.0.0.1:5173` |

### 1단계에서 수정한 파일 (디자인 변경 없음)

| 파일 | 변경 |
| --- | --- |
| `package.json` | `react`/`react-dom`을 peer → **dependencies**로 이동, TypeScript·types 추가 |
| `pnpm-workspace.yaml` | Linux-only `supportedArchitectures` 제거 (Windows 설치 가능) |
| `tsconfig.json` | **신규** — Vite + React JSX 경로 alias |
| `README.md` | placeholder → 실행 방법·구조 안내 |

## 2. 현재 코드 구조

```text
frontend/
├─ src/
│  ├─ main.tsx                 # createRoot → App
│  ├─ app/
│  │  ├─ App.tsx               # ★ 단일 파일 (~2,446줄): 화면·Mock·상태 전부
│  │  └─ components/
│  │     ├─ figma/ImageWithFallback.tsx
│  │     └─ ui/*               # shadcn/Radix 프리셋 (App.tsx에서 거의 미사용)
│  ├─ styles/                  # Tailwind 4 + theme CSS 변수
│  └─ imports/pasted_text/     # 디자인 스펙 메모
├─ vite.config.ts
└─ package.json
```

라우팅은 **react-router 미사용**. `useState<Page>`로 화면 전환.

디자인 토큰: `src/styles/theme.css` (`--primary: #2563EB`, `--background: #F5F5F3` 등).

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

레이아웃 (App 루트):

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

| 상수 | 규모 | 용도 |
| --- | --- | --- |
| `CATEGORIES` | 10개 | Seed Category와 이름 일치, id는 `movie`/`kdrama` 등 문자열 |
| `ITEMS` | 40건 | 목록·추천·상세·홈 요약 |
| `COLLECTIONS` | 8개 | Collection 목록·추천 후보 |
| `HISTORY` | 5건 | 추천 이력 |
| `TMDB_RESULTS` | 8건 | 검색 Mock (Unsplash 포스터 URL) |
| `MOCK_FILE` | 1건 | Export/Import UI 데모 (items: 7202) |

홈 통계는 `CATEGORIES.reduce(...total)` 등 **Mock 배열 집계**를 사용한다. 실제 Backend 집계와 교체 필요.

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
| 미평가 vs 0점 | `!rating` → 평가 없음 (0도 동일 취급) | `rating: null` vs `0.0` 구분 |
| 이력 Snapshot | Mock title 문자열 | Backend history + snapshot |
| 통계 Backend 집계 | Mock 합산 | stats API |
| Legacy 7202건, poster NULL | Mock 40건, Placeholder는 Poster 컴포넌트 있음 | 목록 API + Placeholder 유지 |
| Category UUID | Mock string id | Seed Category UUID 매핑 |
| react-router 미사용 | state 전환 | 점진적 Route 도입 |

## 8. Backend API 연동 단계 계획

디자인을 바꾸지 않고 **Mock → API를 화면 단위로** 교체한다.

### Phase A — 기반 (디자인 무변경)

1. Vite proxy: `/api` → Backend (`localhost:8002` 등)
2. `src/api/client.ts`, `src/types/` (Backend DTO)
3. Mock을 `src/mocks/`로 **이동만** (App에서 import) — 동작 동일
4. `AppLayout` 추출 (Sidebar/Top/Bottom JSX·className 그대로)

### Phase B — 읽기 전용 연동

5. Categories + Items 목록/상세 (Home·Items·ItemDetail Mock 교체)
6. Collections 목록/상세
7. History 목록/상세
8. 홈 통계를 Backend 집계로 교체

*선행:* Backend CRUD·집계 API 구현 (아직 없음 → Backend 작업과 병행)

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

### 권장 Backend 선행 순서

1. Category·Item·Collection CRUD  
2. Recommendation + History  
3. TMDB Migration·프록시·from-tmdb (`docs/05-tmdb-integration-plan.md`)  
4. Stats / Export

## 9. 위험 요소

| 위험 | 설명 | 완화 |
| --- | --- | --- |
| App.tsx 단일 거대 파일 | 2,400+줄, 분리 시 디자인 회귀 | 화면 단위 복사 분리, 시각 비교 |
| Backend API 미구현 | Frontend만 연동 불가 | Phase B 전 Backend CRUD 우선 |
| Category id 불일치 | Mock `movie` vs UUID | 이름 매핑 또는 Seed 고정 UUID |
| react는 peer였음 | 설치 누락 가능 | dependencies로 수정 완료 |
| shadcn vs raw Tailwind | 혼용 시 스타일 불일치 | App 기존 className 유지, shadcn 강제 적용 금지 |
| StarPicker 0.5 | 기획과 불일치 | 최소 UI 보정, 색·크기 유지 |
| TMDB 포스터 Unsplash | 실제 poster_path와 다름 | Backend image base URL 조합 |
| `frontend/PickNext.zip` | 미추적 zip | gitignore 권장, 커밋 금지 |
| npm audit high | vite 관련 가능 | 디자인 단계에서는 강제 upgrade 보류 |
| Docker Desktop 미기동 | Backend 연동 테스트 시 필요 | compose up 후 proxy |

## 10. 다음 작업 순서 (중단 후 재개 시)

1. Docker Compose로 Backend Health 확인  
2. Backend Category/Item 읽기 API (최소)  
3. Frontend Phase A (proxy + mocks 분리 + AppLayout)  
4. Home/Items를 읽기 API에 연결 (UI 동일)  
5. 시각 회귀 확인 후 커밋

**금지 유지:** 새 React 프로젝트, App 전면 재작성, Tailwind/색상 체계 교체, Mock 일괄 삭제.
