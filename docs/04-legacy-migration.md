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

제목 길이 관련 이력:

* **3차 최초 Import** 당시 `items.title`이 `VARCHAR(300)`이라 300자를 초과한 제목 1건은 절단되어 저장됐다 (`title_truncated_count`).
* **3.5차 보정**에서 Migration `0003`으로 `items.title`을 `TEXT`로 확장하고, source_id 2209 원본 제목 **321자**로 복구했다.
* **현재** 신규 Import·분석 로직은 제목을 임의로 절단하지 않는다.

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

Import·보정 후 다음 명령은 **데이터를 삭제**한다.

```bash
docker compose down -v
```

백업·재Import 계획 없이 실행하지 않는다.

## Import 데이터 보정 (3.5차)

Import 전체를 재실행하지 않고 기존 7,202개 Item과 성공 Import Run을 유지한 채 다음만 보정한다.

### 왜 재Import가 아닌가

* 기존 UUID·Import Run·매핑을 보존해야 한다.
* 전체 삭제·재생성은 데이터 손실 위험이 크다.
* 보정 범위가 명확히 제한되어 있다.

### DB 변경

Migration `0003_legacy_data_repairs`: `items.title`을 `TEXT`로 확장한다.

신규 Import·분석 로직에서 제목 300자 자동 절단을 하지 않는다.

### 필수 보정

| 대상 | 보정 |
| --- | --- |
| source_id 2209 | `movie.json` 원본 `name` 전체로 제목 복구 |
| progress_note `007 시리즈` | Collection `007 시리즈` 연결, progress_note NULL |
| progress_note `47미터` | Collection `47미터` 연결, progress_note NULL |
| progress_note `28일 후` | Collection `28일 후` 연결, progress_note NULL |
| progress_note `007 북경특급` | Collection `007 북경특급` 연결, progress_note NULL |
| progress_note `99.9~형사 전문 변호사~` | Collection `99.9~형사 전문 변호사~` 연결, progress_note NULL |

정확히 일치하는 `progress_note`만 자동 보정한다.

### 추가 후보 (자동 반영 안 함)

예능이 아니고 `progress_note`가 반복되거나 `"시리즈"`를 포함하는 값은 `additional-collection-candidates.csv`에만 기록한다.

### 보정 CLI

```bash
docker compose exec backend alembic upgrade head

docker compose exec backend python -m app.scripts.repair_legacy_import_data \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/repair \
  --dry-run \
  --pretty

docker compose exec backend python -m app.scripts.repair_legacy_import_data \
  --input /app/legacy-data/movie.json \
  --report-dir /app/migration-report/repair \
  --apply \
  --pretty
```

* `--dry-run` / `--apply` 중 하나 필수
* 단일 트랜잭션, 오류 시 Rollback
* 재실행 멱등 (`already_repaired` 기록)
* Item 7,202건·상태별 건수·Category별 건수 불변

### 보정 보고서

각 실행마다 타임스탬프 디렉터리에 보고서가 저장되어 이전 실행 결과가 덮어써지지 않는다.

```text
migration-report/repair/runs/
└─ {YYYYMMDDTHHMMSSffffff}-{dry-run|apply}/
   ├─ repair-summary.json
   ├─ title-repair.json
   ├─ collection-repairs.json
   ├─ additional-collection-candidates.csv
   └─ repair-verification.json
```

`repair-summary.json`의 `report_run_dir`에 실제 저장 경로가 기록된다.

## 다음 단계

- Category·Item CRUD API
- 랜덤 추천 및 추천 이력 API
- Frontend
