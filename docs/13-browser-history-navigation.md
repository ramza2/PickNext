# 13. Browser History Navigation (NAV-1, NAV-1A)

> **상태:** NAV-1 + NAV-1A 구현 완료 (2026-07-27)  
> **방식:** React Router 전면 전환 없음. `window.history` + `popstate` 기반 소형 Navigation Layer.  
> **근거:** `react-router`는 `package.json`에 있으나 `src`에서 미사용. 기존 `Page` state를 URL과 동기화하는 최소 계층이 적합.

## 1. Route Table (Canonical)

| URL | AppRoute `name` | Auth |
| --- | --- | --- |
| `/` | `home` | Protected |
| `/items` | `items` | Protected |
| `/items/:itemId` | `item-detail` | Protected |
| `/collections` | `collections` | Protected |
| `/collections/:collectionId` | `collections` (+ detail) | Protected |
| `/categories` | `categories` | Protected |
| `/search` | `search` | Protected |
| `/recommend` | `recommend` | Protected |
| `/recommendation-history` | `recommendation-history` | Protected |
| `/recommendation-history/:id` | `recommendation-history-detail` | Protected |
| `/settings` | `settings` | Protected |
| `/login` · `?next=` | `login` | Public |
| `/signup` | `signup` | Public |
| `/find-id` | `find-id` | Public |
| `/password-reset` | `password-reset` | Public |
| `/not-found` · unknown | `not-found` | Public (미인증 시 Login) |

Legacy alias: `/history` → `recommendation-history` (단일 Canonical은 `/recommendation-history`).

## 2. Navigation Layer

```text
frontend/src/navigation/
  routes.ts              AppRoute · parseLocation · buildPath · sanitizeNextPath
  history.ts             PickNextHistoryState · push/replace · initial replaceState
  routeCache.ts          In-memory session cache (logout/401 clear)
  NavigationProvider.tsx navigate · replace · goBack · popstate · scroll
  index.ts               public exports
```

`main.tsx`는 `<NavigationProvider><App /></NavigationProvider>`로 감싼다.  
화면 이동은 `useAppNavigation()`만 사용한다 (Component에서 직접 `pushState` 금지).

## 3. History Metadata

```typescript
interface PickNextHistoryState {
  picknext: true;
  entryId: string;
  navIndex: number;
  routeName: string;
  overlay?: { type: "item-edit"; itemId: string };
}
```

저장하지 않음: Session Token, Password, API Response 전체.

## 3A. Item Edit Overlay (NAV-1A)

- 대상은 `item-detail`의 `항목 수정` 팝업 한 곳만.
- URL은 그대로 `/items/:itemId`를 유지하고, History state의 `overlay`만 push.
- `openOverlay({ type: "item-edit", itemId })`는 동일 URL이어도 별도 Entry를 1회 push.
- `closeOverlay()`는 현재 overlay entry면 `history.back()`으로 닫고, 비정상 상태는 안전하게 local close.
- Modal 표시 기준은 `currentOverlay?.type === "item-edit"` + `route.itemId` 일치.
- 초기 bootstrap(`ensureInitialHistoryMeta`)에서는 overlay를 제거해 새로고침 시 Modal을 자동 복원하지 않음.

## 4. push / replace / no-op

| 상황 | 동작 |
| --- | --- |
| 목록 → 상세, 메뉴 간 이동 | `push` |
| 로그인 성공, 로그아웃, 401, Filter만 변경, 초기 meta, 삭제 후 목록 | `replace` |
| 동일 Canonical URL 재클릭 | no-op (`routesEqual`) |

초기 로드: `pushState` 금지. Metadata만 `replaceState`.

## 5. popstate / goBack

- `popstate`: URL 파싱 후 화면 State만 갱신. 내부에서 `pushState`/`history.back` 재호출 금지.
- `goBack(fallback)`: `navIndex > 0`이면 `history.back()`, 아니면 Fallback Route로 `replace`.
- Fallback 예: Item 상세 → `/items`, History 상세 → `/recommendation-history`, Collection 상세 → `/collections`.

## 6. Auth

- Bootstrap 완료 전 보호 화면 미렌더 (`AuthLoadingSplash`).
- Protected URL + 미인증 → `/login?next=` (same-origin path만 `sanitizeNextPath`).
- 로그인 성공 → `next` 또는 `/` 로 **replace** (Back으로 Login 복귀 금지).
- 로그아웃·401 → Session Cache clear + Login **replace** 1회 (`redirecting401` 가드).
- Open Redirect: `//`, `://`, `javascript:` 등 거부.

## 7. Route Cache / Scroll

- Items·Collections·Search Snapshot, Recommend step/result, `scrollByEntryId`는 **메모리만**.
- Scroll root: `[data-picknext-scroll-root]` (`AppLayout` main).
- 새로고침·Process 종료·로그아웃·401·사용자 변경 시 Cache 무효.

## 8. Nginx / PWA

- Nginx: `try_files $uri $uri/ /index.html;` (`frontend/nginx.conf`).
- PWA: `navigateFallback: '/index.html'`, denylist `/api`·`/health`, `/api` **NetworkOnly**.

## 9. Browser / PWA QA 체크리스트

1. Home → Items → Item 상세 → Back → Items → Back → Home  
2. Items → Detail → Back → Forward → 같은 Detail  
3. Items Filter 유지 후 Detail → Back (Snapshot)  
4. Recommend setup → result → Item → Back → 같은 result  
5. History 목록 → 상세 → Item → Back ×2  
6. Home 최근 선택 → History 상세 → Back → Home  
7. TMDB 검색 → Detail → Back (검색 상태) · 등록 후 등록됨 최신화  
8. 직접 `/items/{id}` · `/recommendation-history/{id}` · 새로고침  
9. 로그아웃 후 Protected URL → Login + next → 로그인 후 복귀  
10. 로그아웃 후 Browser Back → 이전 사용자 데이터 Flash 없음  
11. 설치형 PWA 시스템 Back = Browser Back  
12. 앱 첫 Entry에서 Back → OS 기본 동작 (무한 Home Loop 없음)  
13. Item 상세 → 수정 팝업 → Back/PWA Back → 팝업만 닫힘(상세/URL 유지)  
14. X/취소/Escape/Backdrop 닫기 후 Back 1회 → 상세 이전 화면  
15. Back으로 팝업 닫은 뒤 Forward → 팝업 재오픈 가능(자동 저장/자동 API 호출 없음)

## 10. 비범위 (유지)

React Router 전면 마이그레이션, SSR, Backend/API/DB 변경, Animation Framework, Navigation Analytics.
