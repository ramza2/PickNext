# UI-AUDIT-1 — 더미·Mock·미구현·Figma 불일치 전수 조사

> **작성일:** 2026-07-24  
> **HEAD:** `e991aac` (`feat(data): 로컬 DB 백업·DPL-3 원격 복원 스크립트 추가`)  
> **범위:** Frontend·Backend·저장소 기획 문서 조사 (제품 코드 변경 없음)  
> **운영 DB:** 미조회 · **원격 수정:** 없음 · **런타임 Browser Network:** 미수행 (소스 추적으로 대체)

---

## 1. 목적

DPL-3 배포 및 DATA-1 DB 복원 이후, 사용자에게 보이는 UI 중 **실제 동작 / Mock·더미 / No-op / Figma 불일치**를 근거와 함께 전수 분류하여 후속 개발(TMDB·설정 정리·인증 등) 우선순위를 정한다.

---

## 2. 조사 범위

| 영역 | 조사 |
| --- | --- |
| Frontend Page state (`Page` union) | 전수 |
| Layout·Nav·More Sheet | 전수 |
| Dialog·Modal·Sheet (App.tsx 내) | 전수 |
| Settings 전 항목 | 전수 |
| TMDB 검색·등록 UI | 전수 |
| Home / Items / Collections / Detail | API 연동 여부 |
| Recommend / History / Data / Category 관리 | 전수 |
| Backend FastAPI `/api/v1` | 전수 |
| Frontend `src/api/*` | 전수 |
| Mock (`mocks/data.tsx`) | 전수 |
| Figma·기획 문서 | 저장소 내 자료 |
| 운영 서버·Browser Network | **미수행** |

---

## 3. 조사 기준

상태: `REAL` · `PARTIAL` · `LOCAL_ONLY` · `STATIC` · `MOCK` · `NO_OP` · `BROKEN` · `DEAD_CODE` · `UNKNOWN`  
Figma: `FIGMA_MATCH` · `FIGMA_PARTIAL` · `FIGMA_ONLY` · `IMPLEMENTATION_ONLY` · `FIGMA_MISMATCH` · `FIGMA_UNAVAILABLE`  
우선순위: P0 / P1 / P2 / P3  
처리 제안: `KEEP` · `IMPLEMENT` · `CONNECT` · `REMOVE` · `HIDE_UNTIL_IMPLEMENTED` · `DISABLE_WITH_NOTICE` · `REPLACE_MOCK` · `DEFER` · `NEEDS_DECISION`

---

## 4. Route 인벤토리

**React Router는 패키지에 있으나 미사용.** `useState<Page>` + `AppLayout.onNavigate`로 전환 (`frontend/src/app/pageTypes.ts`, `App.tsx`).

| Route (Page id) | Page Component | 접근 경로 | 주요 기능 | Backend | 상태 |
| --- | --- | --- | --- | --- | --- |
| `home` | `HomePage` | Sidebar / Bottom Nav | 요약·카테고리·최근 항목·빠른 추천 | summary/categories/items **일부** | **PARTIAL** |
| `search` | `SearchPage` | Sidebar / Bottom Nav | TMDB 검색·상세·등록 UI | 없음 | **MOCK** |
| `recommend` | `RecommendPage` | Sidebar / Bottom Nav | 랜덤 추천 setup/result | 없음 (mock ITEMS/HISTORY) | **MOCK** |
| `items` | `ItemsPage` | Sidebar / Bottom Nav | 목록·필터·CRUD 진입 | items/categories | **REAL** (목록·쓰기 연동) |
| `collections` | `CollectionsPage` | Sidebar / More | 목록·상세·쓰기 | collections/items | **REAL** |
| `history` | `HistoryPage` | Sidebar / More | 추천 이력 목록 | 없음 | **MOCK** |
| `history-detail` | `HistoryDetailPage` | History → 상세 | 이력 상세 | 없음 | **MOCK** |
| `data` | `DataPage` | Sidebar / More | Export/Import UI | 없음 | **MOCK** / **NO_OP** |
| `settings` | `SettingsPage` | Sidebar / More | 설정 목록 | 없음 | **STATIC** / **NO_OP** |
| `item-detail` | `ItemDetailPage` | Items/Home 등 | 상세·상태·삭제 | items | **REAL** |
| `category-manage` | `CategoryManagePage` | Settings → | Category CRUD UI | GET만 존재·UI는 mock | **MOCK** / **NO_OP** |

**Page 수:** 11  
**모달/오버레이 (페이지 아님):** `TMDBDetailPanel`, `TMDBRegisterForm`, `ItemFormModal`, `ConfirmModal`, `Toast`, Mobile More Sheet, Collection 생성/수정 모달 등 (`App.tsx`).

---

## 5. Backend API 인벤토리

등록: `backend/app/main.py` → `api_router` prefix `/api/v1`  
마운트: `backend/app/api/v1/__init__.py` — health, summary, categories, collections, items **만**.

| Method | Path | Router | DB 변경 | Frontend 사용 | 상태 |
| --- | --- | --- | --- | --- | --- |
| GET | `/api/v1/health` | health.py | N | (배포/헬스) | REAL |
| GET | `/api/v1/summary` | summary.py | N | Home | REAL |
| GET | `/api/v1/categories` | categories.py | N | Home/Items/ItemForm | REAL |
| POST | `/api/v1/collections` | collections.py | Y | Collections | REAL |
| GET | `/api/v1/collections` | collections.py | N | Collections | REAL |
| GET | `/api/v1/collections/{id}` | collections.py | N | Collection detail | REAL |
| PATCH | `/api/v1/collections/{id}` | collections.py | Y | Collections | REAL |
| DELETE | `/api/v1/collections/{id}` | collections.py | Y | Collections | REAL |
| GET | `/api/v1/items` | items.py | N | Home/Items/Collection | REAL |
| GET | `/api/v1/items/{id}` | items.py | N | Item detail | REAL |
| POST | `/api/v1/items` | items.py | Y | ItemForm | REAL |
| PATCH | `/api/v1/items/{id}` | items.py | Y | ItemForm/Detail | REAL |
| DELETE | `/api/v1/items/{id}` | items.py | Y | Item detail | REAL |

**합계: 13**

### 없는 API (UI에는 존재)

| 영역 | 존재 여부 |
| --- | --- |
| settings | **없음** |
| auth / login / logout / password | **없음** |
| current user profile | **없음** (`deps.get_current_user`는 Seed 이메일로만 해석) |
| TMDB search / detail / from-tmdb | **없음** |
| export / import HTTP | **없음** |
| recommend / history HTTP | **없음** (DB 모델만 존재) |
| category POST/PATCH/DELETE | **없음** (GET만) |

---

## 6. Frontend API 인벤토리

모듈: `frontend/src/api/catalog.ts` (+ `client.ts`, `query.ts`, 메시지 헬퍼).

| 함수 | Backend Path | 사용 Page | Mock Fallback | 비고 |
| --- | --- | --- | --- | --- |
| `getSummary` | GET `/summary` | Home | 없음 | |
| `getCategories` | GET `/categories` | Home/Items/Form | 없음 | |
| `getItems` | GET `/items` | Home/Items/Collection | 없음 | |
| `getItem` | GET `/items/{id}` | Item detail | 없음 | |
| `getCollections` | GET `/collections` | Collections | 없음 | |
| `getCollection` | GET `/collections/{id}` | Collection detail | 없음 | |
| `getAllCollectionsForSelect` | GET `/collections` 반복 | ItemForm | 없음 | |
| `createItem` / `updateItem` / `deleteItem` | POST/PATCH/DELETE items | ItemForm/Detail | 없음 | |
| `createCollection` / `updateCollection` / `deleteCollection` | POST/PATCH/DELETE collections | Collections | 없음 | |

**catalog API 함수 수:** 13  
**정책:** `docs/06` 및 `.cursor/rules/30-frontend-figma.mdc` — API 오류 시 Mock으로 조용히 대체하지 않음 (Home 등은 Error UI).

`VITE_*`는 `VITE_API_BASE_URL` / proxy만. **`VITE_TMDB_*` 없음.**

---

## 7. 화면별 구현 상태

| ID | Route | 화면·영역 | 기능·표시 | Figma | 데이터 출처 | API | 저장 | 상태 | 우선순위 | 근거 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| U01 | home | 요약·카테고리·최근 등록 | 실데이터 | FIGMA_PARTIAL | Backend | Y | DB | PARTIAL | P2 | Home API + `HISTORY` mock 병행 `App.tsx` ~1999–2014 |
| U02 | home | 최근 선택 이력 | Mock 5건 | FIGMA_PARTIAL | `HISTORY` | N | — | MOCK | P1 | `mocks/data.tsx:77-83` |
| U03 | home | 인사말 | `박민준님` | FIGMA_MISMATCH* | 하드코딩 | N | — | MOCK | P1 | `App.tsx:1877` |
| U04 | search | 검색 결과 | 고정 8건 필터 | FIGMA_PARTIAL | `TMDB_RESULTS` | N | memory | MOCK | P1 | `App.tsx:2070-2088`, `mocks/data.tsx:85-156` |
| U05 | search | 등록됨 / 등록 | `alreadyAdded` | FIGMA_PARTIAL | mock flag | N | Set state | MOCK | P1 | `alreadyAdded` + `addedIds` |
| U06 | search | TMDB 등록 저장 | Toast + Set만 | FIGMA_PARTIAL | — | N | memory | NO_OP | P1 | `handleRegister`, `TMDBRegisterForm` |
| U07 | recommend | 전체 플로우 | Mock 후보 | FIGMA_PARTIAL | ITEMS/COLLECTIONS/HISTORY | N | memory | MOCK | P1 | `RecommendPage` + mocks |
| U08 | items | 목록·필터·페이지 | 실데이터 | FIGMA_MATCH | Backend | Y | DB | REAL | — | hooks + catalog |
| U09 | item-detail | 상세·상태·삭제 | 실데이터 | FIGMA_MATCH | Backend | Y | DB | REAL | — | |
| U10 | collections | 목록·상세·CRUD | 실데이터 | FIGMA_MATCH | Backend | Y | DB | REAL | — | |
| U11 | history | 목록 | Mock | FIGMA_PARTIAL | `HISTORY` | N | — | MOCK | P1 | |
| U12 | history-detail | 상세 | Mock | FIGMA_PARTIAL | HISTORY/ITEMS | N | — | MOCK | P1 | |
| U13 | data | Export/Import | Mock 파일·단계 | FIGMA_PARTIAL | `MOCK_FILE` | N | — | MOCK/NO_OP | P1 | `DataPage` ~3969+ |
| U14 | settings | 전 행 (Category·로그아웃 제외) | 고정 값 | FIGMA_PARTIAL | 하드코딩 | N | 없음 | STATIC/NO_OP | P1 | `SettingsPage` 4159–4227 |
| U15 | settings | Category 관리 링크 | 페이지 이동만 | FIGMA_PARTIAL | — | — | — | REAL(내비) | — | `setPage("category-manage")` |
| U16 | category-manage | 목록·추가·수정·삭제 | Mock+Toast | FIGMA_PARTIAL | `CATEGORIES` | N | 없음 | MOCK/NO_OP | P1 | `CategoryManagePage` 1678–1814; 저장=Toast만 |
| U17 | layout | Sidebar 사용자 | 박민준 / minjun@… | FIGMA_MISMATCH* | 하드코딩 | N | — | MOCK | P1 | `AppLayout.tsx:76-77` |
| U18 | layout | 로그아웃 (More/Settings) | 버튼만 | FIGMA_PARTIAL | — | N | — | NO_OP | P1 | onClick 없음 |
| U19 | — | PWA Update Prompt | 실 SW | — | vite-plugin-pwa | — | — | REAL | — | `PwaUpdatePrompt.tsx` |

\*표시 이름은 Seed/`users`와 불일치 → 사용자 오인.

---

## 8. Mock·더미 목록

| ID | 값·데이터 | 선언 위치 | 사용 화면 | 실제처럼 보임 | 제거·교체 시점 | 비고 |
| --- | --- | --- | --- | --- | --- | --- |
| M01 | `minjun@example.com` | `AppLayout.tsx:77`, `SettingsPage`, `MOCK_FILE.user` | Layout·Settings·Data | 예 | AUTH-1 / SET-CLEAN-1 | DB는 `jchramza@gmail.com` |
| M02 | `박민준` | `AppLayout.tsx:76`, Settings, Home 인사 | Layout·Settings·Home | 예 | AUTH-1 / SET-CLEAN-1 | DB display_name과 불일치 |
| M03 | `TMDB 연동 상태: 연동됨` | `SettingsPage` value 하드코딩 | Settings | 예 | TMDB-1 + SET-CLEAN-1 | Backend TMDB Client 없음 |
| M04 | `TMDB_RESULTS` 8건 (서울의 봄 등) | `mocks/data.tsx:85-156` | Search | 예 | TMDB-2 | Unsplash 포스터 URL |
| M05 | `alreadyAdded` 플래그 | 동상 | Search 등록됨 | 예 | TMDB-2 | DB 7,202건과 무관 |
| M06 | `App Version 1.0.0` | Settings, footer, MOCK_FILE | Settings·Data | 예 | APP-CONFIG-1 | package.json=`0.0.1` |
| M07 | `Schema Version v2.1` | Settings, Data, MOCK_FILE | Settings·Data | 예 | EXPORT-1 | Alembic=`0004_…`와 무관 |
| M08 | `성인 콘텐츠 제외: 켜짐` | Settings 하드코딩 | Settings | 예 | SET-CLEAN-1 / NEEDS_DECISION | 저장·검색 미적용 |
| M09 | `CATEGORIES` mock 10 | `mocks/data.tsx:10-21` | Category관리·Recommend·Data | 예 | Category API 후 | Seed 실데이터와 별개 |
| M10 | `ITEMS` 40건 | `mocks/data.tsx:23-64` | Recommend·HistoryDetail | 예 | Recommend API | |
| M11 | `COLLECTIONS` 8건 | `mocks/data.tsx:66-75` | Recommend·TMDB 등록폼 | 예 | 실 Collections API로 교체 | |
| M12 | `HISTORY` 5건 | `mocks/data.tsx:77-83` | Home·History·Recommend | 예 | History API | DB history=0 |
| M13 | `MOCK_FILE` | `mocks/data.tsx:158` | Data | 예 | EXPORT-1 | |

---

## 9. 미구현·No-op 목록

| ID | 화면 | 항목 | Handler | Backend API | 현재 동작 | 의존 단계 | 권고 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N01 | Settings | 일반·화면·외부·데이터·계정 대부분 Row | 없음 (button만) | 없음 | 클릭해도 변경 없음 | APP-CONFIG-1 / AUTH-1 / TMDB-1 | HIDE_UNTIL_IMPLEMENTED 또는 DISABLE_WITH_NOTICE |
| N02 | Settings | 로그아웃 | 없음 | 없음 | 무반응 | AUTH-1 | HIDE_UNTIL_IMPLEMENTED |
| N03 | More Sheet | 로그아웃 | 없음 | 없음 | 무반응 | AUTH-1 | 동일 |
| N04 | Settings | 비밀번호 변경 | 없음 | 없음 | 무반응 | AUTH-1 | 동일 |
| N05 | Settings | 데이터 내보내기·가져오기 Row | 없음 | 없음 | 무반응 (Data 페이지는 별도 nav) | EXPORT-1 | CONNECT to `data` or HIDE |
| N06 | Category 관리 | 저장 | Toast만 | Category write 없음 | “저장되었습니다” 가짜 성공 | Category CRUD | REPLACE_MOCK / DISABLE |
| N07 | Category 관리 | 삭제 확인 | Toast만 | 없음 | 가짜 삭제 | Category CRUD | 동일 |
| N08 | Category 관리 | 드래그 순서 | grab 커서만 | 없음 | 미구현 | — | DISABLE |
| N09 | Search | 등록 | Set+Toast | from-tmdb 없음 | DB 미반영 | TMDB-1/2 | REPLACE_MOCK |
| N10 | Data | Export/Import 단계 | UI 상태만 | 없음 | 가짜 완료 | EXPORT-1 | HIDE or REPLACE |
| N11 | Recommend | 추천 확정 | mock HISTORY 취급 | history API 없음 | DB 미반영 | Recommend API | REPLACE_MOCK |

---

## 10. Figma 불일치

### 조사한 자료

| 자료 | 경로 | 비고 |
| --- | --- | --- |
| Figma Make pasted design spec | `frontend/src/imports/pasted_text/picknext-design-spec.md` | 설정·성인 콘텐츠 포함 (§24) |
| Figma update notes | `frontend/src/imports/pasted_text/picknext-figma-update.md` | App/Schema Version, 성인 콘텐츠 언급 |
| Frontend Figma 규칙 | `.cursor/rules/30-frontend-figma.mdc` | Make 결과를 UI 기준선으로 유지 |
| Frontend 연동 계획 | `docs/06-frontend-integration-plan.md` | Mock 잔여 명시 |
| TMDB 계획 | `docs/05-tmdb-integration-plan.md` | `include_adult=false`는 **Backend 기본값** |
| 제품 범위 | `docs/01-product-scope.md` 등 | |
| 외부 Figma URL / 파일 | **저장소에 없음** | 라이브 Figma 직접 대조 **불가** |

### Figma 비교 가능 여부

**부분 가능** — 저장소 pasted_text·docs 기준. 외부 “승인된 Figma”와 사용자 진술이 다를 수 있음 → 해당 항목은 `NEEDS_DECISION`.

### Figma에는 있으나 미구현/부분 (FIGMA_ONLY / FIGMA_PARTIAL)

| 항목 | 분류 | 근거 |
| --- | --- | --- |
| TMDB 실검색·등록 | FIGMA_PARTIAL | UI만, API 없음 |
| 랜덤 추천·History DB 연동 | FIGMA_PARTIAL | Mock |
| 설정 값 저장·적용 | FIGMA_PARTIAL | UI만 |
| Export/Import | FIGMA_PARTIAL | Mock |
| 인증·비밀번호·로그아웃 | FIGMA_PARTIAL | UI만 |
| Category CRUD | FIGMA_PARTIAL | UI Mock+Toast (사용자 관찰과 달리 **미구현**) |
| Dark/시스템 테마 | FIGMA_ONLY | Settings에 “라이트” 고정 |
| 포스터 표시 여부 설정 | FIGMA_ONLY | design-spec §24, UI 행 없음 |

### 구현에는 있으나 기획 근거 충돌 (IMPLEMENTATION_ONLY / NEEDS_DECISION)

| 항목 | 분류 | 근거 |
| --- | --- | --- |
| **성인 콘텐츠 제외** 설정 Row | **NEEDS_DECISION** | pasted design-spec §24·figma-update에 **존재**. 사용자: “승인 Figma에 없었다”. `docs/05`는 UI가 아니라 `include_adult=false` Backend 기본. Git: `322a91f`(Figma Make baseline)에서 FE에 최초 등장 |
| Mock 계정 `박민준` / `minjun@example.com` | IMPLEMENTATION_ONLY (프로토타입 잔존) | Seed 사용자와 불일치 |

---

## 11. 사용자 오인 위험

| 등급 | 항목 | 설명 |
| --- | --- | --- |
| **P0** | (현재 코드 기준) Secret Frontend 노출 | **미검출** — TMDB Key/Token은 FE Bundle에 없음 |
| **P0** | Category/TMDB 등록 Toast 가짜 성공 | Category 저장·삭제·TMDB 등록이 Toast만 → **데이터 변경된 것처럼 오인** (보안 Secret은 아니나 **데이터 신뢰 P0에 준하는 위험**) → 본 문서에서는 **P1**로 두고 “가짜 성공”으로 강조 |
| **P1** | TMDB `연동됨` | 미연동인데 연동됨 |
| **P1** | Mock 검색 결과 | 실검색처럼 보임 |
| **P1** | Mock 계정 정보 | 실 Seed 사용자와 다름 |
| **P1** | 등록됨 뱃지 | DB와 무관한 mock flag |
| **P1** | Settings 활성 Row | 전부 미동작인데 조작 가능처럼 보임 |
| **P1** | Category 관리 가짜 CRUD | “구현됨”으로 오인하기 쉬움 |
| **P2** | Home 이력 Mock vs 실 summary | 혼재 |
| **P2** | Recommend/History 미연동 | 핵심 흐름 미완 |
| **P3** | App/Schema Version 표기 | `0.0.1` / Alembic 0004와 불일치 |

---

## 12. TMDB 현황

### 검색 데이터 실제 출처

```text
SearchPage
→ TMDB_RESULTS (frontend/src/mocks/data.tsx)
→ 로컬 title/type 필터만
→ Network 요청 없음
→ Backend TMDB Client 없음
→ 실제 TMDB API 호출 없음
```

표시 작품(서울의 봄, 콘크리트 유토피아, 오펜하이머, 패스트 라이브즈, 이니셰린의 밴시, 오징어 게임 시즌 2, 탑건, 파친코) = **Frontend Mock**.

### 연동 상태 표시

| 기대 “실제 연동됨” | 현재 |
| --- | --- |
| Backend Client + env + Health + FE 조회 | **하드코딩 `"연동됨"`** (`SettingsPage`) |
| `.env`에 TMDB_* 존재 | Config/`config.py` **미사용** (문서·example만) |

→ 분류: **하드코딩**

### 등록됨 판정

| 항목 | 결과 |
| --- | --- |
| DB 7,202 Item 비교 | **안 함** |
| `tmdb_id` / `external_id` | Item 모델에 **필드 없음** |
| 방식 | Mock `alreadyAdded: boolean` + 로컬 `addedIds` Set |
| Schema 변경 후보 | `docs/05`의 `external_*`, `poster_path` 등 (이번 Audit에서 Migration 안 함) |

### Secret 노출

| 점검 | 결과 |
| --- | --- |
| Frontend Bundle에 TMDB Token | **없음** |
| `VITE_TMDB_*` | **없음** |
| API 응답에 Token | **없음** |
| Backend Settings TMDB 필드 | **없음** (env 예시만) |

---

## 13. 설정 화면 현황

| Section | 항목 | 표시값 출처 | Handler | 저장 | 적용 | Backend | Figma(pasted) | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 일반 | 앱 표시 이름 | `"박민준"` | 없음 | 없음 | 없음 | 없음 | 있음 | STATIC/NO_OP |
| 일반 | 기본 추천 상태 | `"앞으로 볼 항목"` | 없음 | 없음 | 없음 | 없음 | 있음 | STATIC/NO_OP |
| 일반 | 기본 카테고리 | `"전체"` | 없음 | 없음 | 없음 | 없음 | 있음 | STATIC/NO_OP |
| 일반 | 목록 기본 정렬 | `"최근 수정순"` | 없음 | 없음 | Items API와 무관 | 없음 | 있음 | STATIC/NO_OP |
| 일반 | 페이지당 표시 개수 | `"25개"` | 없음 | 없음 | page_size 미연동 | 없음 | 있음 | STATIC/NO_OP |
| 화면 | 테마 | `"라이트"` | 없음 | 없음 | CSS 미연동 | 없음 | Light/Dark/System | STATIC/NO_OP |
| 화면 | 목록 밀도 | `"보통"` | 없음 | 없음 | 없음 | 없음 | 있음 | STATIC/NO_OP |
| 외부 | TMDB 연동 상태 | `"연동됨"` | 없음 | 없음 | 검사 없음 | 없음 | 있음 | MOCK/STATIC |
| 외부 | 기본 검색 언어 | `"한국어"` | 없음 | 없음 | 검색 미반영 | 없음 | 있음 | STATIC/NO_OP |
| 외부 | 성인 콘텐츠 제외 | `"켜짐"` | 없음 | 없음 | 검색 미반영 | 없음 | pasted 있음 / 사용자 부정 | STATIC + NEEDS_DECISION |
| 데이터 | 내보내기·가져오기 | 빈값 | 없음 | — | — | 없음 | 있음 | NO_OP (Data 페이지는 별도) |
| 데이터 | App Version | `"1.0.0"` | 없음 | — | — | — | 있음 | STATIC |
| 데이터 | Schema Version | `"v2.1"` | 없음 | — | — | — | 있음 | STATIC |
| 계정 | 이메일 | `minjun@example.com` | 없음 | — | — | 없음 | 있음 | MOCK |
| 계정 | 표시 이름 | `박민준` | 없음 | — | — | 없음 | 있음 | MOCK |
| 계정 | 비밀번호 변경 | 빈값 | 없음 | — | — | 없음 | 있음 | NO_OP |
| — | Category 관리 | — | `setPage` | — | Mock 화면 | GET만 | 있음 | NAV=REAL / 화면=MOCK |
| — | 로그아웃 | — | 없음 | — | — | 없음 | 있음 | NO_OP |

**localStorage / sessionStorage / IndexedDB:** Frontend `src`에서 **설정 저장 용도 사용 없음**.

---

## 14. 보안 확인

| 항목 | 결과 |
| --- | --- |
| TMDB Secret Frontend 노출 | **없음** (P0 미해당) |
| 로그/응답 Token | 코드상 해당 경로 없음 |
| 가짜 성공으로 DB 변경 유도 | Category·TMDB 등록 Toast — **오인 위험 높음** (실제 DB 쓰기는 안 함) |
| 잘못된 계정 표시 | **있음** (P1) — 소유권 혼동 가능 |

---

## 15. 후속 단계 제안

권장 순서 (구현은 본 Audit 범위 밖):

1. **SET-CLEAN-1** — Settings·Layout·Category관리의 더미·No-op·가짜 Toast를 숨김/비활성/실데이터 교체. 가짜 “연동됨”·계정 정보 즉시 제거 권장.  
2. **TMDB-1** — Backend Config·Client·Search/Detail/from-tmdb API (`docs/05`).  
3. **TMDB-2** — Frontend `TMDB_RESULTS` 제거, 실검색·등록됨(external_id)·등록 연결.  
4. **Recommend/History API** — Mock `HISTORY`/`ITEMS` 추천 경로 교체.  
5. **AUTH-1** — 로그인·세션·비밀번호·로그아웃 (계정 UI는 그전까지 숨김).  
6. **EXPORT-1** — Export/Import 실구현 또는 UI 숨김.  
7. **APP-CONFIG-1** — 일반·화면 설정의 저장·적용 (필요 시).  
8. **성인 콘텐츠** — `NEEDS_DECISION`: UI 제거 vs Backend `include_adult=false`만 유지.

---

## 16. 최종 결론

- **실연동(REAL) 핵심:** Items·Item Detail·Collections·(Home 일부)·Item/Collection 쓰기·PWA 업데이트.  
- **대량 Mock/No-op:** Search(TMDB)·Recommend·History·Data·Settings 거의 전부·**Category 관리**(사용자 추정과 달리 미구현)·계정·버전·TMDB 연동 표시.  
- **P0 Secret 노출: 없음.**  
- **P1 사용자 오인: 다수** (연동됨, Mock 검색, 가짜 계정, 가짜 Category/TMDB 성공).  
- Figma: 저장소 Make 명세와 대조 가능. 외부 승인본은 검증 불가. `성인 콘텐츠 제외`는 **명세 충돌 → 결정 필요**.

**이번 단계 판정:** Audit 목적상 **PASS** (전수 분류·문서화 완료). 제품 완성도와 무관.

---

## 부록 A. 카운트 요약

| 분류 | 대략 수 (화면·기능 단위) |
| --- | ---: |
| REAL | ~8 (Items/Collections/Detail/쓰기/PWA/내비 일부) |
| PARTIAL | ~2 (Home 혼재 등) |
| LOCAL_ONLY | 0 (설정 저장소 없음; 검색 addedIds는 memory) |
| STATIC | Settings 버전·다수 표시값 |
| MOCK | Search/Recommend/History/Data/Category목록/계정/TMDB결과 |
| NO_OP | Settings rows, logout, password, Category 저장/삭제 Toast |
| BROKEN | 0 (의도적 Mock; Category 수정 input 비활성에 가까움) |
| DEAD_CODE | react-router 의존성 미사용 수준 (별도 dead page 라우트 없음) |
| Backend API | 13 |
| Frontend catalog API | 13 |
| Page ids | 11 |

## 부록 B. App / Schema Version

| 소스 | 값 |
| --- | --- |
| UI Settings / footer | `1.0.0` / `v2.1` |
| `frontend/package.json` | `0.0.1` |
| PWA manifest | version 필드 없음 |
| Alembic head | `0004_remove_item_soft_delete` |
| `MOCK_FILE.schemaVersion` | `v2.1` (Export 포맷 문서화와 공식 연결 근거 없음) |

## 부록 C. 제품 코드 변경

본 Audit는 `docs/audits/UI-AUDIT-1.md`만 추가한다. 애플리케이션·테스트 코드는 변경하지 않는다.

---

## Post-Audit Decision (SET-CLEAN-1, 2026-07-24)

조사 시점의 사실 기록은 위 본문을 유지한다. 이후 제품된 정책:

- 설정 화면의 “성인 콘텐츠 제외” Row는 **제거**한다.
- 향후 TMDB Backend 검색은 `include_adult=true`로 **고정**한다.
- 사용자 설정 UI나 Frontend Override는 **제공하지 않는다**.
- 운영 UI에서 Mock 검색·가짜 계정·가짜 성공 Toast·미구현 Settings·Recommend/History/Data Nav를 제거·차단한다 (SET-CLEAN-1).
- Category는 `GET /api/v1/categories` 기반 **읽기 전용**으로 전환한다.

## Post-Audit Progress (TMDB-1, 2026-07-24)

- Backend TMDB Client·Status·Search·Details API 및 Item 외부 식별 Migration(`0005`) 작업 진행·완료.
- Frontend 실검색 연결·`from-tmdb` 등록은 **TMDB-2** 범위로 유지.

## Post-Audit Progress (TMDB-2, 2026-07-24)

- `POST /api/v1/items/from-tmdb` + 서버 Detail 재조회 + 409 `TMDB_ITEM_ALREADY_EXISTS` 구현.
- Frontend `SearchPage` 실검색·Detail Panel·Register Form·등록됨 UX·search snapshot/`origin:"search"` 복귀.
- Collection「TMDB 검색 후 추가」가짜 Toast 제거 → Search 이동.
- 런타임 `TMDB_RESULTS` Mock 미사용 유지.

## Post-Audit Progress (TMDB-3, 2026-07-24)

- `items.release_year` + `items.synopsis` + Migration `0006_add_item_year_synopsis` + Check `ck_items_release_year_range`.
- Item API `release_year`·`synopsis`·`poster_url`·`backdrop_url` (TMDB path 기반 순수 URL, Configuration 호출 없음).
- TMDB `overview` → Item `synopsis` (trim, 빈값 NULL). `memo`/`progress_note`와 분리. 기존 Item Backfill 없음.
- 수동 Item Form 출시년도·줄거리 · UI Poster/연도 (목록·상세·Collection·Home) · Item 상세 줄거리 실데이터 연결 (고정 Placeholder 제거).
- Legacy NULL·Placeholder 유지. 실데이터 `0006` 적용은 별도 Backup·승인 후.
