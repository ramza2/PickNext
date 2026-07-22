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

## 현재 구조

```text
src/
├─ api/           # fetch client + catalog 읽기 함수 (화면 미연결)
├─ types/         # Api* DTO / Mock 전용 타입
├─ mocks/         # Figma Mock 데이터 (화면 기준)
└─ app/
   ├─ App.tsx     # 화면·상태·모달 (Mock 기반)
   ├─ pageTypes.ts
   └─ layout/AppLayout.tsx
```

**화면은 아직 Mock 데이터로 동작합니다.** `src/api/catalog.ts`는 준비만 되어 있으며, 다음 Phase(B-2)에서 읽기 API에 점진 연결합니다.

상세: [`docs/06-frontend-integration-plan.md`](../docs/06-frontend-integration-plan.md)

## 원칙

1. 기존 JSX·`className`을 최대한 유지한 채 기능만 연결한다.
2. Mock은 화면 단위로 점진 교체한다 (일괄 삭제 금지).
3. Backend API에 맞춘다는 이유로 화면 구조를 바꾸지 않는다.
