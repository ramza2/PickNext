# 11. Authentication Plan (AUTH-1)

> **상태:** AUTH-1 구현 완료 (코드·격리 테스트) · **실DB/운영 Migration·실제 SMTP·Credential CLI 실행은 미적용**  
> **방식:** DB Opaque Session Token + HttpOnly Cookie (`picknext_session`) · JWT/OAuth/Firebase 없음  
> **비밀번호:** Argon2id (`argon2-cffi`) · 인증번호: HMAC-SHA256(`AUTH_CODE_PEPPER`)

## 1. 개요

PickNext는 자체 계정으로 로그인한다. Runtime API의 현재 사용자는 더 이상 `SEED_USER_EMAIL`이 아니라 Session Cookie로 결정된다.

| 기능 | 상태 |
| --- | --- |
| 회원가입 (이메일 인증번호) | 구현 |
| 로그인 / 자동 로그인 / 로그아웃 | 구현 |
| `GET /auth/me` | 구현 |
| 아이디 찾기 | 구현 |
| 비밀번호 재설정 (전 Session revoke) | 구현 |
| 사용자별 API 격리 | 구현 (기존 `user_id` 스코프 + Cookie DI) |
| SMTP (Naver SSL 465) | 구현 · 테스트는 FakeEmailSender |
| 기존 사용자 Credential CLI | 구현 · 승인 후 수동 실행 |

## 2. Cookie·Session

```text
Cookie: picknext_session
HttpOnly / SameSite=Lax / Path=/ / Domain 미지정
Secure: AUTH_COOKIE_SECURE (로컬 false · 운영 true)

일반 로그인: Session Cookie (Max-Age 없음) · 서버 TTL 12h
자동 로그인: Persistent Cookie · Max-Age 30d · 서버 TTL 30d

DB: user_sessions.token_hash = SHA-256(raw token)
원문 Token은 DB에 저장하지 않음
만료는 절대시간 · 요청마다 TTL 연장하지 않음
last_seen_at: 10분 throttle
```

## 3. API

공개:

- `GET /api/v1/health`
- `POST /api/v1/auth/signup/request-code|complete`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/find-id/request-code|verify`
- `POST /api/v1/auth/password-reset/request-code|confirm`

인증 필요:

- `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`
- Summary / Categories / Collections / Items
- TMDB status·search·details·from-tmdb

에러 `detail`: `{"code":"AUTH_*","message":"..."}`

## 4. Migration

- Revision: `0007_add_auth_tables` (← `0006_add_item_year_synopsis`)
- `users`: `login_id`(NULL 가능)·`email_verified_at`·`last_login_at`
- `user_sessions`, `auth_verification_codes`
- **비밀번호·login_id backfill 없음** (기존 운영 사용자 보존)

## 5. 설정

`.env.example` 참고:

- `AUTH_*` — cookie/TTL/code/`AUTH_CODE_PEPPER`(필수)
- `SMTP_*` — Naver SSL 465 (`SMTP_USE_SSL=true`, `SMTP_USE_TLS=false`)
- `CORS_ORIGINS` — 명시 목록 + `allow_credentials` · `*` 금지
- `SEED_*` — Seed CLI/bootstrap 전용 (Runtime current user 아님)

Frontend에 SMTP·AUTH Secret을 넣지 않는다.

## 6. CLI (수동)

```bash
python -m app.cli.set_user_credentials --email <existing-email>
python -m app.cli.test_smtp --to <address>
```

비밀번호 인수로 전달 금지. AUTH-1 자동 단계에서는 실행하지 않음.

## 7. Frontend

- `credentials: "include"`
- Bootstrap `GET /auth/me` → Loading / AuthGate / App
- 로그인·회원가입·아이디찾기·비밀번호찾기 화면
- 401 전역 처리 (공개 auth 경로 제외) · 로그아웃 시 보호 State 클리어
- PWA: `/api/*` NetworkOnly 유지 · auth JSON precache 금지

## 8. 로컬 적용 체크리스트 (별도 승인)

1. Custom Dump Backup
2. `.env`에 `AUTH_CODE_PEPPER`·SMTP·`AUTH_COOKIE_SECURE` 설정
3. Backend 중지 → `alembic upgrade head` (실DB)
4. 건수 검증 (users/categories/collections/items)
5. `set_user_credentials`로 기존 사용자 자격정보 설정
6. Backend·Frontend 재기동
7. SMTP Test 1회 (승인 후)
8. Browser QA

## 9. 운영 배포 체크리스트 (별도 승인)

1. Commit·Push 확인
2. 서버 `.env.dpl3` AUTH·SMTP
3. DB Backup → Backend 중지 → `0006`→`0007`
4. 건수 검증 → Credential CLI → Build·재기동
5. SMTP·API Smoke·Browser/PWA QA
