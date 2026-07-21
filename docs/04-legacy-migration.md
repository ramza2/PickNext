# 04. Legacy Migration

기존 Android MovieManager 데이터를 PickNext로 옮기기 위한 정책, Dry-run, Import 도구 안내입니다.

## 이전 대상 / 제외

| 대상 | 처리 |
| --- | --- |
| `legacy-data/movie.json` | Dry-run 분석 + Import 대상 |
| `legacy-data/category.json` | 선택적 매핑 교차 검증 |
| `log.json` | 이전하지 않음 |
| 기존 추천 이력 / Firebase | 이전하지 않음 |

## 원본 JSON 배치

```text
PickNext/
├─ legacy-data/
│  ├─ README.md      # 저장소에 포함
│  ├─ movie.json     # gitignore (개인 데이터)
│  └─ category.json  # gitignore (선택)
└─ migration-report/ # gitignore (분석·Import 결과)
   ├─ ...            # Dry-run (2차)
   └─ import/        # Import (3차)
```

## 카테고리 매핑

| legacy id | Seed 이름 |
| ---: | --- |
| 1 | 애니메이션 |
| 2 | 애니 영화 |
| 3 | 영화 |
| 4 | 한국드라마 |
| 5 | 일본드라마 |
| 6 | 중국드라마 |
| 7 | 미국드라마 |
| 8 | 예능 |
| 9 | 만화책 |
| 10 | 음식 |

운영 DB `items`/`collections`에는 `legacy_id`를 저장하지 않는다.  
Import 감사·롤백용으로 `legacy_import_runs`, `legacy_import_items`, `legacy_import_collections` 테이블을 사용한다.

## 확정 Import 정책 (3차)

Dry-run 결과(7,213건)를 바탕으로 다음 정책을 확정했다.

### 카테고리 누락 6건 → Import 제외

- `미분류` 카테고리를 추가하지 않는다.
- `SKIPPED_MISSING_CATEGORY`로 보고서에 기록한다.

### Ambiguous series → Item은 Import, series 폐기

Dry-run 기준 Ambiguous 12건 중 **11건**이 Import 대상이다. 나머지 1건(`source_id=6243`)은 카테고리 누락과 겹쳐 Import되지 않는다.

```text
collection_id = NULL
progress_note = NULL
memo = NULL
```

- Collection을 생성하지 않는다.
- 원본 `series` 문자열은 신규 DB에 보존하지 않는다.
- `AMBIGUOUS_SERIES_CLEARED` 건수로 보고한다.

### 중복 제목 5건 제외 (5개 그룹)

동일 사용자·동일 Seed 카테고리·동일 제목(앞뒤 공백만 제거)은 그룹당 1건만 Import한다.

선정 우선순위:

1. `COMPLETED` 우선
2. 평점 높은 항목
3. `updated_at` 최신
4. `source_id` 큰 값

선택되지 않은 레코드는 `SKIPPED_DUPLICATE_TITLE`로 제외한다. 값 병합은 하지 않는다.

### series 분류 적용

| Dry-run 분류 | Import 처리 |
| --- | --- |
| `COLLECTION` | Collection 생성·연결 |
| `PROGRESS_NOTE` | `items.progress_note` 저장 |
| `EMPTY` | 모두 NULL |
| `AMBIGUOUS` | EMPTY와 동일 (series 폐기) |

### 예상 건수

```text
7,213 (원본)
-   6 (카테고리 누락)
-   5 (중복 제목)
= 7,202 Item
```

검증식: `7213 = 7202 + 6 + 5`

제목이 DB 컬럼 길이(300자)를 초과하는 항목은 1건 있으며, Import 시 300자로 잘라 저장한다(`title_truncated_count`).

## Dry-run (2차)

DB를 변경하지 않고 분석·분류 보고서만 생성한다.

```bash
docker compose exec backend python -m app.scripts.analyze_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report \
  --pretty
```

## Import (3차)

```bash
# 건수 확인 (DB 변경 없음)
docker compose exec backend python -m app.scripts.import_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/import \
  --dry-run \
  --pretty

# 실제 Import (단일 트랜잭션)
docker compose exec backend python -m app.scripts.import_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/import \
  --apply \
  --pretty
```

대상 사용자: `.env`의 `SEED_USER_EMAIL` (또는 `--user-email`). 사용자가 없으면 Import를 중단한다.

### 재실행 방지

동일 사용자 + 동일 파일 SHA-256으로 성공한 Import가 있으면 `--apply`를 차단한다.

개발환경에서만:

```bash
docker compose exec backend python -m app.scripts.import_legacy_movies \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/import \
  --reset-imported-data \
  --apply \
  --pretty
```

### Import 보고서

```text
migration-report/import/
├─ import-summary.json
├─ imported-items.json
├─ skipped-missing-category.json
├─ skipped-duplicate-titles.json
├─ cleared-ambiguous-series.json
├─ created-collections.json
└─ verification.json
```

## DB 볼륨 주의

Import 후 다음 명령은 **Import 데이터를 삭제**한다.

```bash
docker compose down -v
```

백업·재Import 계획 없이 실행하지 않는다.

## 다음 단계

- Category·Item CRUD API
- 랜덤 추천 및 추천 이력 API
- Frontend
