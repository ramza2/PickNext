# PickNext 반응형 웹·PWA UI/UX 디자인

## 1. 서비스 개요

**PickNext**는 사용자가 영화, 드라마, 애니메이션, 예능, 만화책, 음식 등의 선택 후보를 관리하고, 무엇을 볼지 또는 무엇을 선택할지 랜덤으로 추천받는 개인용 웹·PWA 애플리케이션입니다.

기존 Android 앱에서 이전한 데이터가 있습니다.

* 전체 Item: 약 7,202건
* PLANNED: 약 4,708건
* COMPLETED: 약 2,494건
* Collection: 약 250개
* Category: 10개

주요 사용 목적:

* 앞으로 볼 콘텐츠 등록
* 기존 항목 검색·수정·완료 처리
* 영화·드라마 외부 검색
* 시리즈·Collection 관리
* 조건별 랜덤 추천
* 추천 결과 재추첨
* 최종 선택 확정
* 추천 이력 확인
* 데이터 내보내기·복원

서비스명:

> PickNext

슬로건:

> 고민하지 말고, 다음 선택은 PickNext

---

## 2. 핵심 UX 원칙

다음 원칙을 기준으로 디자인해 주세요.

* 개인용 콘텐츠 관리 앱과 생산성 앱의 중간 성격
* OTT처럼 포스터만 크게 보여주는 구조보다 검색과 데이터 관리에 집중
* 많은 항목을 빠르게 검색하고 관리할 수 있는 정보 밀도
* 랜덤 추천 기능은 가장 쉽게 접근 가능해야 함
* 긴 콘텐츠 제목을 충분히 표시할 수 있어야 함
* Desktop과 Mobile 모두 사용하기 쉬워야 함
* Mobile에서는 설치형 PWA처럼 자연스럽게 보여야 함
* 주요 기능은 2~3단계 이내로 접근 가능해야 함
* 한국어 UI를 기본으로 사용
* 과도한 그라데이션, 그림자, 장식은 피함
* 접근성 있는 명도 대비와 충분한 터치 영역 사용
* 실제 React 기반 서비스로 구현하기 쉬운 구조로 제작

---

## 3. 디자인 스타일

### 기본 분위기

* 차분하고 현대적인 개인용 앱
* 정돈된 카드·리스트 기반 UI
* 정보가 많아도 답답하지 않은 여백
* 포스터가 없는 기존 데이터도 자연스럽게 표현 가능
* 포스터가 있는 TMDB 데이터와 텍스트 전용 기존 데이터를 동일한 UI 안에서 함께 표시

### 색상

* 기본 배경: 밝은 회색 또는 따뜻한 미색
* 카드 배경: 흰색
* 기본 텍스트: 차콜 또는 짙은 네이비
* Primary: 블루 또는 인디고
* Accent: 민트 또는 라임
* PLANNED: 블루 또는 오렌지
* COMPLETED: 그린
* 위험 작업: 레드

### 형태

* Border Radius: 10~14px
* 얇고 명확한 Border
* 최소한의 Shadow
* 한글 가독성이 좋은 산세리프 폰트
* Desktop 최대 콘텐츠 폭: 약 1,400px

Light Mode를 우선 제작하되 추후 Dark Mode 적용이 가능하도록 Color Variable을 분리해 주세요.

---

## 4. 반응형 기준

### Desktop

* 기준 너비: 1440px
* 좌측 Sidebar
* 메인 콘텐츠 중앙 정렬
* 목록은 Table 또는 고밀도 List 사용

### Tablet

* 기준 너비: 768px
* Sidebar 축소 또는 Drawer 전환
* 일부 Table을 Card List로 전환

### Mobile

* 기준 너비: 390px
* 상단 App Bar
* 하단 Bottom Navigation
* Form은 단일 열
* 주요 Action은 하단 Sticky 영역 사용
* 카드형 목록 사용
* PWA 설치형 앱처럼 구성

---

## 5. 공통 내비게이션

### Desktop Sidebar

메뉴:

1. 홈
2. 콘텐츠 검색
3. 랜덤 추천
4. 전체 항목
5. Collection
6. 추천 이력
7. 데이터 관리
8. 설정

Sidebar 하단:

* 사용자 표시 이름
* 사용자 이메일
* 계정 메뉴
* 로그아웃

### Mobile Bottom Navigation

5개 메뉴:

1. 홈
2. 검색
3. 추천
4. 항목
5. 더보기

`더보기` 내부:

* Collection
* 추천 이력
* 데이터 관리
* 설정

### 공통 Top Bar

* 페이지 제목
* 검색
* 항목 추가
* 사용자 프로필

알림 기능은 제외합니다.

---

## 6. 데이터 구조

### Category

사용자가 직접 관리하는 분류입니다.

기본 Category 예시:

* 영화
* 한국드라마
* 일본드라마
* 미국드라마
* 중국드라마
* 애니메이션
* 애니 영화
* 예능
* 만화책
* 음식

표시 정보:

* 이름
* 색상
* 아이콘
* 전체 Item 수
* PLANNED 수
* COMPLETED 수

### Item

개별 선택 후보입니다.

필드:

* 제목
* Category
* Collection
* 상태
* 평점
* Progress Note
* 메모
* 포스터
* 외부 데이터 출처
* 출시·방영일
* 등록일
* 수정일

상태:

* PLANNED: 앞으로 볼 항목
* COMPLETED: 완료한 항목

### Collection

같은 작품군이나 시리즈를 묶는 단위입니다.

예시:

* 007 시리즈
* 건담
* 강철의 연금술사
* 47미터
* 28일 후
* 99.9~형사 전문 변호사~

중요 규칙:

> Collection은 여러 Item을 포함하지만 랜덤 추천에서는 하나의 후보로 취급합니다.

### Progress Note

Collection이 아닌 회차·권수·시청 진행정보입니다.

예시:

* 1~82, 84, 87~89
* 15권까지 읽음
* 2007년 10~12월
* 44~45, 57~58, 70

Collection과 Progress Note를 화면에서 명확히 구분해 주세요.

---

# 핵심 화면

## 7. 홈 화면

### Hero 영역

* 사용자 인사
* 문구: `오늘은 무엇을 선택할까요?`
* Primary 버튼: `랜덤 추천 시작`
* Secondary 버튼: `콘텐츠 검색`
* Text 버튼: `직접 항목 추가`

### 요약 통계

다음 수치를 카드로 표시:

* 전체 항목: 7,202
* 앞으로 볼 항목: 4,708
* 완료 항목: 2,494
* Collection: 약 250
* 최근 선택 횟수

### 빠른 추천

Category별 빠른 추천:

* 영화 추천
* 드라마 추천
* 애니 추천
* 예능 추천
* 음식 추천

### 최근 등록한 콘텐츠

TMDB 검색 또는 직접 등록으로 최근 추가한 PLANNED Item을 보여 주세요.

### 최근 선택 이력

최근 확정한 추천 결과 5개:

* 제목 또는 Collection명
* Category
* 선택 일시
* 현재 상태
* 상세보기

---

## 8. 외부 콘텐츠 검색 화면

TMDB를 이용해 영화와 드라마를 검색하고 PLANNED Item으로 등록하는 핵심 화면입니다.

화면 제목:

> 영화·드라마 검색

### 검색 영역

* 검색창
* Placeholder: `영화 또는 드라마 제목을 검색하세요`
* 검색 버튼
* 최근 검색어
* 검색어 초기화

### 콘텐츠 유형 필터

Segmented Control 또는 Filter Chip:

* 전체
* 영화
* TV·드라마

기본값은 `전체`입니다.

### 검색 결과 카드

각 결과에 다음 정보를 표시:

* 포스터
* 한국어 제목
* 원제
* 영화 또는 TV Badge
* 개봉일 또는 첫 방영일
* 제작 국가
* TMDB 평점
* 장르
* 줄거리 2~3줄
* `상세보기`
* `앞으로 볼 항목으로 등록`

포스터가 없는 경우 기본 Placeholder를 사용합니다.

### 중복 등록 표시

이미 PickNext에 등록된 콘텐츠는 다음처럼 표현해 주세요.

* `이미 등록됨` Badge
* 현재 상태 표시
* 기존 항목 보기 버튼
* 중복 등록 버튼은 기본 비활성

---

## 9. TMDB 콘텐츠 상세 미리보기

검색 결과를 선택했을 때 Drawer, Modal 또는 Mobile Full Screen으로 표시합니다.

표시 정보:

* 큰 포스터
* 제목
* 원제
* 영화·TV 유형
* 개봉일 또는 첫 방영일
* 제작 국가
* 장르
* TMDB 평점
* 줄거리
* 주요 출연진 일부
* 시즌 수 또는 러닝타임
* 데이터 출처: TMDB

버튼:

* `앞으로 볼 항목으로 등록`
* `닫기`

외부 서비스 페이지로 이동하는 링크는 선택적으로 배치합니다.

---

## 10. TMDB 콘텐츠 등록 화면

TMDB 콘텐츠를 선택하면 PickNext 등록 Form으로 이동합니다.

자동 입력:

* 제목
* 포스터
* 출시일 또는 첫 방영일
* 줄거리
* TMDB ID
* 외부 유형: MOVIE 또는 TV
* 외부 출처: TMDB
* 상태: PLANNED

사용자가 확인·수정할 항목:

* Category
* Collection
* Progress Note
* 메모
* 제목 수정
* 포스터 사용 여부

### Category 추천

TMDB 정보를 바탕으로 Category를 추천하되 반드시 사용자가 확인하게 해 주세요.

예:

* KR TV → 한국드라마 추천
* JP TV → 일본드라마 또는 애니메이션 추천
* US TV → 미국드라마 추천
* CN TV → 중국드라마 추천
* 영화 → 영화 또는 애니 영화 추천

UI 예시:

> 추천 Category: 한국드라마
> TMDB 정보를 기준으로 추천했습니다. 저장 전 확인해 주세요.

### 등록 버튼

* `앞으로 볼 항목으로 등록`
* `취소`

모바일에서는 하단 Sticky Button을 사용합니다.

---

## 11. 직접 항목 등록·수정 화면

TMDB를 사용하지 않고 직접 Item을 등록하거나 수정하는 화면입니다.

Desktop:

* Modal 또는 우측 Drawer

Mobile:

* 전체 화면 Form

입력 필드:

* 제목: 필수
* Category: 필수
* 상태: PLANNED / COMPLETED
* 평점: 선택
* Collection: 선택
* Progress Note: 선택
* 메모: 선택
* 포스터 URL 또는 이미지: 추후 확장 가능

### Collection 입력

* 기존 Collection 검색
* 기존 Collection 선택
* 새 Collection 생성
* 선택 해제

Collection과 Progress Note는 함께 사용할 수 있습니다.

### 평점

* 0~5점
* 0.5점 단위
* 평가하지 않음 상태 지원
* 0점과 미입력 상태를 구분

버튼:

* 저장
* 취소

---

## 12. 랜덤 추천 설정 화면

### Category 선택

* 전체 Category
* 하나 또는 여러 Category
* Category Card 또는 Chip 사용

### 상태 필터

Segmented Control:

* 앞으로 볼 항목
* 완료 항목
* 전체

기본값:

> 앞으로 볼 항목

### 추천 단위 안내

다음 내용을 안내합니다.

> 개별 Item은 각각 하나의 후보입니다.
> Collection은 포함된 Item 수와 관계없이 하나의 후보입니다.

### 추가 옵션

* 최근 선택 제외
* 특정 Collection 제외
* 최소 평점
* 포스터가 있는 항목만 보기 옵션은 제공하지 않음

### 실행 버튼

> 추천 결과 보기

모바일은 하단 Sticky Button으로 구성합니다.

---

## 13. 랜덤 추천 결과 화면

PickNext의 가장 중요한 화면입니다.

### 공통 표시

* 추천 결과 Label
* Category Badge
* Item 또는 Collection Badge
* 제목
* 상태
* 평점
* 메타 정보
* 포스터가 있으면 표시
* 포스터가 없으면 텍스트 중심 카드

### 단일 Item 결과

* 제목
* Category
* 상태
* 평점
* 출시일
* Progress Note
* 메모 일부
* 외부 출처
* 포스터

### Collection 결과

* Collection명
* 포함 Item 수
* 완료 수
* 미완료 수
* 진행률
* 내부 Item 목록

현재 추천 조건에 해당하는 Item은 강조하고, 조건에 해당하지 않는 Item은 흐리게 표현합니다.

### 주요 버튼

우선순위:

1. `이걸로 선택`
2. `다시 추천`
3. `상세보기`

모바일은 Sticky Action Bar 사용.

---

## 14. 선택 확인 Modal 또는 Bottom Sheet

표시 정보:

* 선택한 Item 또는 Collection
* Category
* 현재 상태
* 추천 이력에 저장된다는 안내

버튼:

* `선택 확정`
* `취소`

---

## 15. 추천 완료 화면

문구:

> 오늘의 선택이 정해졌습니다.

표시:

* 선택 완료 아이콘
* 포스터 또는 Placeholder
* Item 또는 Collection명
* Category
* 상태

버튼:

* 상세보기
* 완료 처리
* 다시 추천
* 홈으로

Collection인 경우 내부 Item 목록도 표시합니다.

---

## 16. 전체 항목 목록

7,202건의 대량 데이터를 탐색하기 쉬워야 합니다.

### 상단 기능

* 검색창
* 필터
* 정렬
* 표시 방식 전환
* 신규 항목 추가
* TMDB에서 검색
* 결과 건수

### 필터

* Category
* 상태
* Collection 포함 여부
* 외부 출처
* 영화·TV 구분
* 평점
* 출시일
* 등록일
* 수정일

### 정렬

* 제목순
* 최근 등록순
* 최근 수정순
* 평점 높은 순
* 출시일순

### Desktop

Table 또는 고밀도 List:

* 포스터 Thumbnail
* 제목
* Category
* Collection
* 상태
* 평점
* 진행 정보
* 외부 출처
* 수정일
* More Menu

### Mobile

Card List:

* 포스터 Thumbnail
* 제목
* Category Badge
* 상태 Badge
* Collection
* 평점
* Progress Note
* More Menu

포스터가 없는 기존 Item도 동일한 Card 크기를 유지할 수 있도록 Placeholder를 사용합니다.

---

## 17. 항목 상세 화면

표시:

* 포스터
* 제목
* Category
* Collection
* 상태
* 평점
* 출시·방영일
* Progress Note
* 메모
* 줄거리
* 외부 데이터 출처
* 등록일
* 수정일

주요 작업:

* 수정
* 완료 처리
* PLANNED로 되돌리기
* Collection 이동
* 삭제

TMDB 연결 Item의 경우:

* TMDB 정보 다시 보기
* 외부 정보 갱신
* TMDB 연결 해제

외부 정보 갱신은 추후 기능으로 표시해도 됩니다.

---

## 18. Category 관리

각 Category 카드:

* 아이콘
* 색상
* 이름
* 전체 Item
* PLANNED
* COMPLETED

기능:

* 추가
* 수정
* 순서 변경
* 아이콘 변경
* 색상 변경
* 삭제

Item이 있는 Category는 바로 삭제하지 못하도록 경고 Modal을 표시합니다.

---

## 19. Collection 목록

상단:

* 검색
* Category 필터
* 상태 필터
* 정렬
* Collection 추가

Collection 카드:

* Collection명
* Category
* Item 수
* PLANNED 수
* COMPLETED 수
* 평균 평점
* 진행률
* 최근 수정일

---

## 20. Collection 상세

상단:

* Collection명
* Category
* Item 수
* 진행률
* 수정
* 삭제
* 이 Collection에서 추천

내부 Item 목록:

* 포스터
* 제목
* 상태
* 평점
* Progress Note
* 수정일
* 완료 처리
* Collection에서 제거

기능:

* 기존 Item 추가
* 새 Item 등록
* TMDB 검색 후 Collection에 추가

---

## 21. 추천 이력 목록

추천 이력은 사용자가 `이걸로 선택`을 눌러 확정한 결과만 저장합니다.

필터:

* 기간
* Category
* Item / Collection
* 검색
* 정렬

이력 카드:

* 선택 일시
* 포스터
* Item 또는 Collection명
* Category
* 선택 당시 상태
* 현재 상태
* Item / Collection Badge
* 상세보기
* 이력 삭제

---

## 22. 추천 이력 상세

표시:

* 선택 일시
* Category
* 선택 유형
* 선택한 Item 또는 Collection
* 선택 당시 Snapshot
* 현재 상태
* 현재 데이터와 달라진 부분
* Collection이면 당시 포함 Item 목록

안내:

> 추천 이력을 삭제해도 실제 Item과 Collection은 삭제되지 않습니다.

---

## 23. 데이터 관리

### 사용자 데이터 Export

표시:

* 전체 데이터 건수
* 마지막 Export 일시
* 파일 형식
* Schema Version

버튼:

> 데이터 내보내기

### 데이터 Import

* 백업 파일 선택
* 파일 정보
* Schema Version
* 포함 데이터 건수
* 검증 결과
* 전체 복원 RESTORE

초기 UI에서는 MERGE를 지원하지 않습니다.

복원 전 경고 Modal을 제공합니다.

### 서버 이전 안내

다음 내용을 표시합니다.

> 애플리케이션 Export는 사용자 데이터 백업용입니다.
> 서버 전체 이전은 PostgreSQL 백업과 복원을 사용해야 합니다.

---

## 24. 설정 화면

### 일반

* 앱 표시 이름
* 기본 추천 상태
* 기본 Category
* 목록 기본 정렬
* 페이지당 표시 개수

### 화면

* Light
* Dark
* 시스템 설정
* 목록 밀도

### 외부 콘텐츠

* TMDB 연동 상태
* TMDB 출처 안내
* 기본 검색 언어: 한국어
* 성인 콘텐츠 제외
* 포스터 표시 여부

API Key 값 자체는 화면에 직접 노출하지 않습니다.

### 데이터

* Export·Import 이동
* 전체 데이터 통계
* App Version
* Schema Version

### 계정

* 사용자 이메일
* 표시 이름
* 비밀번호 변경
* 로그아웃

인증은 화면 구조만 제공합니다.

---

# 공통 상태

## 25. Empty State

다음 상태를 디자인해 주세요.

* 검색 결과 없음
* 등록된 Item 없음
* Collection 없음
* 추천 이력 없음
* 추천 후보 없음
* TMDB 결과 없음

추천 후보 없음 문구:

> 선택한 조건에 맞는 항목이 없습니다.

버튼:

* 필터 변경
* 항목 추가
* 콘텐츠 검색

---

## 26. Loading State

* 목록 Skeleton
* 카드 Skeleton
* TMDB 검색 Skeleton
* 콘텐츠 상세 Skeleton
* 추천 실행 중 Shuffle Animation

과도한 룰렛 Animation은 사용하지 않습니다.

---

## 27. Error State

* 서버 연결 실패
* TMDB 검색 실패
* Item 저장 실패
* 추천 실패
* Import 검증 실패
* 네트워크 오류

재시도 버튼을 제공합니다.

---

## 28. Success Toast

예시:

* 항목이 저장되었습니다.
* 앞으로 볼 항목으로 등록되었습니다.
* 완료 처리되었습니다.
* 추천 이력에 저장되었습니다.
* 데이터가 내보내졌습니다.
* 복원이 완료되었습니다.

---

# Component

## 29. 재사용 Component

다음 요소를 Component와 Variant로 제작해 주세요.

* App Sidebar
* Mobile Bottom Navigation
* Top App Bar
* Primary Button
* Secondary Button
* Danger Button
* Text Button
* Status Badge
* Category Badge
* Collection Badge
* Media Type Badge
* External Source Badge
* Rating
* Poster
* Poster Placeholder
* Item Card
* Item List Row
* TMDB Search Result Card
* TMDB Detail Preview
* Collection Card
* Recommendation Result Card
* History Card
* Summary Stat Card
* Search Input
* Filter Chip
* Segmented Control
* Empty State
* Confirm Modal
* Bottom Sheet
* Toast
* Skeleton
* Form Field
* Dropdown
* Date Range Picker
* More Menu

Auto Layout과 Variant를 적극 활용해 주세요.

---

# Prototype

## 30. 핵심 Prototype 흐름

### TMDB 검색·등록

```text
홈
→ 콘텐츠 검색
→ 검색 결과
→ 콘텐츠 상세 미리보기
→ 앞으로 볼 항목으로 등록
→ Category 확인
→ 저장
→ 항목 상세
```

### 추천

```text
홈
→ 랜덤 추천 설정
→ 추천 결과
→ 다시 추천
→ 이걸로 선택
→ 선택 확인
→ 추천 완료
```

### 직접 등록

```text
전체 항목
→ 직접 항목 추가
→ 저장
→ 항목 상세
```

### Collection

```text
Collection 목록
→ Collection 상세
→ TMDB에서 Item 추가
→ 저장
```

### 추천 이력

```text
추천 이력
→ 이력 상세
→ 현재 Item 상세
```

### 데이터 복원

```text
데이터 관리
→ 파일 선택
→ 검증
→ 복원 확인
→ 완료 또는 오류
```

---

# Figma 파일 구조

## 31. Page 구성

```text
00. Cover
01. Foundations
02. Components
03. Desktop
04. Tablet
05. Mobile
06. Prototype
07. Empty-Loading-Error
```

### Foundations

* Color Variables
* Typography
* Spacing
* Radius
* Shadow
* Grid
* Breakpoints
* Icon Size

### 제작 기준

* Auto Layout 사용
* Component와 Variant 사용
* Variable 사용
* 의미 있는 Layer 이름
* 반복 요소는 Instance 사용
* Desktop·Mobile 공통 Component 구조
* React Component로 옮기기 쉬운 구조
* 포스터 유무에 따라 레이아웃이 흔들리지 않도록 설계

---

# 우선 제작 화면

## 32. 높은 완성도로 제작할 화면

1. Desktop 홈
2. Mobile 홈
3. Desktop 콘텐츠 검색
4. Mobile 콘텐츠 검색
5. TMDB 검색 결과
6. TMDB 콘텐츠 상세 미리보기
7. TMDB 콘텐츠 등록
8. Desktop 랜덤 추천 설정
9. Mobile 랜덤 추천 설정
10. 단일 Item 추천 결과
11. Collection 추천 결과
12. Desktop 전체 항목 목록
13. Mobile 전체 항목 목록
14. 항목 등록·수정
15. 항목 상세
16. Collection 목록
17. Collection 상세
18. 추천 이력 목록
19. 추천 이력 상세
20. 데이터 관리

---

# 제한사항

## 33. 제외 범위

* 댓글
* 팔로우
* 소셜 공유
* 사용자 간 추천
* 실시간 알림
* 스트리밍 재생
* 결제
* 구독
* AI 개인화 추천
* 관리자용 복잡한 운영 Dashboard
* TMDB 인물 검색
* 성인 콘텐츠 검색
* 데이터 Import MERGE
* 외부 콘텐츠 자동 등록

랜덤 추천은 AI가 아니라 단순 랜덤 선택 기능으로 표현합니다.

TMDB 검색 결과는 사용자가 반드시 확인한 후 등록하게 해 주세요.

TMDB 포스터와 메타데이터를 사용하는 화면에는 적절한 위치에 다음 출처 안내가 들어갈 수 있도록 설계해 주세요.

> This product uses the TMDB API but is not endorsed or certified by TMDB.

최종 결과는 PickNext를 실제 React 기반 반응형 웹·PWA로 구현할 수 있을 정도로 일관된 디자인 시스템과 구체적인 화면 구조로 제작해 주세요.
