# Frontend (Figma Make 기준선)

PickNext UI 프로토타입입니다. Figma Make에서 생성한 화면·Tailwind·레이아웃을 **디자인 기준선**으로 유지합니다.

임의로 색상·Sidebar·Bottom Nav·카드·Typography를 재설계하지 않습니다.

## 실행

요구: Node.js 20+ (권장 LTS)

```bash
cd frontend
npm install
npm run dev
```

- 개발 서버: http://127.0.0.1:5173
- 프로덕션 빌드: `npm run build` → `dist/`

## 현재 구조

- `src/app/App.tsx` — 전체 화면·Mock 데이터·네비게이션 (단일 파일)
- `src/styles/` — Tailwind 4 + theme CSS 변수
- `src/app/components/ui/` — shadcn/Radix 프리셋 (대부분 미사용)

상세 분석·API 연동 계획: [`docs/06-frontend-integration-plan.md`](../docs/06-frontend-integration-plan.md)

## 원칙

1. 기존 JSX·`className`을 최대한 유지한 채 기능만 연결한다.
2. Mock은 화면 단위로 점진 교체한다 (일괄 삭제 금지).
3. Backend API에 맞춘다는 이유로 화면 구조를 바꾸지 않는다.
