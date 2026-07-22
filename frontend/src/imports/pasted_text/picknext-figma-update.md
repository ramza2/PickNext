# PickNext Figma Make 2차 수정 요청

현재 생성된 PickNext React 프로토타입의 디자인 방향과 공통 스타일은 유지해 주세요.

기존 화면을 전면 재생성하거나 다른 디자인 스타일로 교체하지 말고, 아래의 핵심 기능 누락과 잘못 구현된 흐름을 수정해 주세요.

이번 작업은 실제 Backend 연동이 아니라 UI·UX와 Prototype 흐름을 보완하는 작업입니다.

---

## 1. 유지할 기존 디자인

다음 요소는 현재 결과를 유지해 주세요.

* 블루·인디고 중심의 차분한 디자인
* 밝은 배경과 흰색 카드
* Desktop Sidebar
* Mobile Bottom Navigation
* 홈 화면의 통계·빠른 추천·최근 기록 구성
* TMDB 검색 결과 카드 스타일
* 전체 항목 목록 스타일
* Collection 목록과 상세 화면 스타일
* 추천 이력 목록 스타일
* 데이터 관리와 설정 화면
* 포스터가 없는 항목의 문자형 Placeholder
* 기존 Typography, Spacing, Radius, Badge 스타일

기존 디자인 시스템을 확장하는 방식으로 수정합니다.

---

# 가장 중요한 수정 사항

## 2. 랜덤 추천에서 Collection을 실제 추천 후보로 처리

현재 랜덤 추천 화면은 Item만 추천하는 구조로 되어 있습니다.

PickNext의 핵심 규칙은 다음과 같습니다.

> 개별 Item은 각각 하나의 후보입니다.
> Collection은 포함된 Item 수와 관계없이 하나의 후보입니다.

예를 들어 Item 30개가 들어 있는 Collection도 랜덤 추천에서는 후보 1개로 계산됩니다.

### 추천 결과 유형

추천 결과를 두 가지 유형으로 구분해 주세요.

```text
ITEM
COLLECTION
```

### 단일 Item 추천 결과

기존 화면을 유지하며 다음을 표시합니다.

* 포스터 또는 Placeholder
* 제목
* Category
* 상태
* 평점
* 출시·방영일
* Progress Note
* 메모 일부
* TMDB 연결 여부
* `이걸로 선택`
* `다시 추천`
* `상세보기`

### Collection 추천 결과

새로운 결과 화면을 추가해 주세요.

표시 내용:

* Collection명
* Category
* Collection Badge
* 포함 Item 수
* PLANNED 수
* COMPLETED 수
* 진행률
* 내부 Item 목록
* 각 Item 상태
* 각 Item 평점
* Progress Note
* 포스터 Thumbnail 또는 Placeholder

현재 추천 조건에 포함되는 Item은 강조해 주세요.

예:

* PLANNED 추천이라면 PLANNED Item은 선명하게 표시
* COMPLETED Item은 흐리게 표시
* Collection 자체는 추천 후보 1개로 표현

버튼:

1. `이 Collection으로 선택`
2. `다시 추천`
3. `Collection 상세보기`

Mobile에서는 하단 Sticky Action Bar를 사용해 주세요.

### 추천 후보 안내

추천 설정 화면에 다음 안내를 더 명확하게 표현해 주세요.

> Collection에 Item이 여러 개 있어도 랜덤 추천에서는 하나의 후보로 계산됩니다.

간단한 예시 UI도 추가해 주세요.

```text
개별 Item 3개 + Collection 2개
= 총 추천 후보 5개
```

---

## 3. 홈의 빠른 추천 Category 연결

현재 홈 화면의 빠른 추천 버튼이 모두 같은 추천 화면으로 이동합니다.

다음처럼 선택한 Category가 추천 설정에 미리 반영되도록 Prototype을 수정해 주세요.

```text
영화 추천
→ 랜덤 추천 설정
→ Category: 영화 선택 상태

드라마 추천
→ 랜덤 추천 설정
→ 한국·일본·미국·중국드라마 선택 상태

애니 추천
→ 랜덤 추천 설정
→ 애니메이션·애니 영화 선택 상태

예능 추천
→ 랜덤 추천 설정
→ Category: 예능 선택 상태

음식 추천
→ 랜덤 추천 설정
→ Category: 음식 선택 상태
```

사용자는 추천 설정 화면에서 선택된 Category를 다시 변경할 수 있습니다.

---

# TMDB 검색·등록 흐름

## 4. TMDB 검색 결과에서 바로 등록하지 않도록 수정

현재 TMDB 검색 결과에서 `등록` 버튼을 누르면 바로 등록 완료로 처리됩니다.

다음 흐름으로 변경해 주세요.

```text
검색 결과
→ 상세 미리보기
→ 앞으로 볼 항목으로 등록
→ PickNext 등록 확인 화면
→ Category·Collection 확인
→ 최종 저장
```

TMDB 검색 결과는 사용자가 확인하기 전에는 자동 저장하지 않습니다.

---

## 5. TMDB 콘텐츠 상세 미리보기 보완

검색 결과의 `상세보기`를 누르면 Desktop에서는 우측 Drawer 또는 Modal, Mobile에서는 전체 화면으로 표시해 주세요.

표시 내용:

* 큰 포스터
* 한국어 제목
* 원제
* Movie 또는 TV Badge
* 개봉일 또는 첫 방영일
* 제작 국가
* 장르
* TMDB 평점
* 줄거리
* 주요 출연진 일부
* 영화면 러닝타임
* TV면 시즌 수
* TMDB 출처 표시

버튼:

* `앞으로 볼 항목으로 등록`
* `닫기`

---

## 6. TMDB 등록 확인 화면 추가

TMDB 콘텐츠를 PickNext에 저장하기 전에 반드시 등록 Form을 표시해 주세요.

자동 입력 정보:

* 제목
* 원제
* 포스터
* 출시·방영일
* 줄거리
* TMDB ID
* Movie 또는 TV
* 상태: PLANNED

사용자 확인·수정 항목:

* 제목
* Category
* Collection
* Progress Note
* 메모
* 포스터 사용 여부

### Category 추천 UI

TMDB 정보를 기반으로 추천 Category를 보여 주되 자동 확정하지 않습니다.

예:

```text
추천 Category
한국드라마

TMDB의 제작 국가와 콘텐츠 유형을 기준으로 추천했습니다.
저장 전 Category를 확인해 주세요.
```

추천이 불확실한 경우:

```text
Category를 선택해 주세요.
```

Category 선택은 필수입니다.

### Collection 입력

다음 기능을 제공합니다.

* 기존 Collection 검색
* 기존 Collection 선택
* 새 Collection 생성
* Collection 미지정

버튼:

* `앞으로 볼 항목으로 등록`
* `취소`

Mobile에서는 하단 Sticky Button을 사용해 주세요.

---

## 7. TMDB 중복 등록 상태

이미 PickNext에 등록된 TMDB 콘텐츠는 검색 결과에 다음 정보를 표시해 주세요.

* `이미 등록됨` Badge
* 현재 상태: PLANNED 또는 COMPLETED
* 등록된 Category
* `기존 항목 보기` 버튼

기본 등록 버튼은 비활성화합니다.

제목만 같은 직접 등록 Item은 TMDB 중복으로 처리하지 않습니다.

---

# Item 관리 화면

## 8. 직접 Item 등록 화면 추가

홈의 `항목 추가`, 전체 항목의 `신규 항목 추가` 버튼과 연결되는 직접 등록 화면을 추가해 주세요.

Desktop:

* 우측 Drawer 또는 Modal

Mobile:

* 전체 화면 Form

입력 항목:

* 제목: 필수
* Category: 필수
* 상태: PLANNED / COMPLETED
* 평점: 선택
* Collection: 선택
* Progress Note: 선택
* 메모: 선택
* 출시·방영일: 선택
* 포스터 URL 또는 이미지: 향후 확장 표시

평점:

* 0~5
* 0.5 단위
* `평가하지 않음` 상태 지원
* 0점과 미평가 상태를 시각적으로 구분

버튼:

* 저장
* 취소

---

## 9. Item 상세 화면 추가

전체 항목 목록, 추천 결과, 추천 이력에서 Item을 클릭하면 상세 화면으로 이동하게 해 주세요.

표시 정보:

* 포스터 또는 Placeholder
* 제목
* Category
* Collection
* 상태
* 사용자 평점
* 출시·방영일
* Progress Note
* 메모
* 줄거리
* 외부 데이터 출처
* 등록일
* 수정일

TMDB 연결 Item은 다음도 표시합니다.

* `TMDB 연결됨` Badge
* 원제
* TMDB 정보 보기
* 외부 정보 갱신: 추후 제공 표시

주요 버튼:

* 수정
* 완료 처리
* PLANNED로 되돌리기
* Collection 이동
* 삭제

삭제는 Danger Button과 Confirm Modal을 사용합니다.

---

## 10. Item 수정 화면 추가

Item 상세의 `수정` 버튼과 연결되는 Form을 추가해 주세요.

직접 등록 Form과 같은 Component를 재사용합니다.

수정 가능 항목:

* 제목
* Category
* 상태
* 평점
* Collection
* Progress Note
* 메모

TMDB ID와 외부 출처는 일반 수정 Form에서 변경하지 않도록 합니다.

---

## 11. 완료 상태 변경 확인

PLANNED Item을 COMPLETED로 변경할 때 간단한 Confirm Modal 또는 Bottom Sheet를 사용해 주세요.

내용:

```text
이 항목을 완료 처리할까요?
완료 날짜는 현재 시각으로 기록됩니다.
```

버튼:

* 완료 처리
* 취소

COMPLETED에서 PLANNED로 되돌리는 흐름도 제공합니다.

---

# Category 관리

## 12. Category 관리 화면 추가

현재 별도 Category 관리 화면이 없으므로 설정 또는 더보기 메뉴에서 접근 가능한 화면을 추가해 주세요.

화면 제목:

> Category 관리

각 Category 카드 또는 행에 다음을 표시합니다.

* 아이콘
* 색상
* 이름
* 전체 Item 수
* PLANNED 수
* COMPLETED 수
* 순서 이동 Handle
* More Menu

기능:

* Category 추가
* 이름 수정
* 아이콘 변경
* 색상 변경
* 순서 변경
* 삭제

Item이 포함된 Category 삭제 시 다음 안내를 보여 주세요.

```text
이 Category에는 등록된 항목이 있습니다.
항목이 있는 Category는 삭제할 수 없습니다.
```

버튼:

* 항목 보기
* 확인

Category 추가·수정은 Modal 또는 Drawer로 구성해 주세요.

---

# Collection 관리 보완

## 13. Collection 상세 기능 보완

현재 Collection 상세 화면을 유지하면서 다음 기능을 추가해 주세요.

* Collection 이름 수정
* Category 수정
* 기존 Item 추가
* 새 Item 직접 등록
* TMDB 검색 후 추가
* Item을 Collection에서 제거
* 개별 Item 완료 처리
* Collection 삭제

Collection 삭제 시 포함된 Item은 삭제하지 않고 Collection 연결만 해제된다는 안내를 표시합니다.

```text
Collection을 삭제해도 내부 Item은 삭제되지 않습니다.
Item의 Collection 연결만 해제됩니다.
```

---

# 추천 이력

## 14. 추천 이력 상세 화면 추가

추천 이력 목록의 `상세보기`와 연결되는 화면을 추가해 주세요.

표시 정보:

* 선택 일시
* Item 또는 Collection
* Category
* 선택 유형
* 선택 당시 상태
* 현재 상태
* 선택 당시 Snapshot
* 현재 데이터와 달라진 항목

단일 Item 이력:

* 선택 당시 제목
* Category
* 상태
* 평점
* Progress Note
* 현재 상태와 차이

Collection 이력:

* 선택 당시 Collection명
* 당시 포함 Item 목록
* 각 Item의 당시 상태
* 현재 Item 상태
* 삭제되거나 변경된 Item 표시

안내:

> 추천 이력을 삭제해도 실제 Item과 Collection은 삭제되지 않습니다.

버튼:

* 현재 Item 상세보기
* 현재 Collection 상세보기
* 이력 삭제

---

# 대량 데이터 목록

## 15. 전체 항목 화면 폭 확대

Desktop 전체 항목 목록은 현재보다 넓게 사용해 주세요.

* 최대 콘텐츠 폭: 약 1,280~1,400px
* Sidebar를 제외한 가용 공간을 충분히 활용
* 긴 제목 컬럼을 넓게 배치

권장 컬럼:

* 선택 Checkbox
* 포스터
* 제목
* Category
* Collection
* 상태
* 평점
* Progress Note
* 수정일
* More Menu

---

## 16. 페이지네이션 추가

전체 7,202건을 고려해 페이지네이션 UI를 추가해 주세요.

표시:

* 전체 결과 수
* 현재 페이지
* 페이지당 항목 수
* 이전·다음
* 처음·마지막
* 페이지 번호

페이지당 항목 수:

* 25
* 50
* 100

Mobile에서는 단순화된 이전·다음 버튼과 현재 페이지를 사용합니다.

---

## 17. 다중 선택 UI

향후 일괄 상태 변경과 삭제를 고려한 다중 선택 UI를 추가해 주세요.

항목을 선택하면 상단에 Bulk Action Bar를 표시합니다.

예:

```text
3개 항목 선택됨

[완료 처리] [Category 이동] [Collection 지정] [삭제]
```

현재는 UI Prototype만 제공해 주세요.

---

# 데이터 관리

## 18. Import 흐름 보완

현재 단순 파일 선택 영역을 다음 단계형 화면으로 수정해 주세요.

```text
1. 백업 파일 선택
2. 파일 검증
3. 포함 데이터 확인
4. 복원 경고
5. 최종 확인
6. 복원 결과
```

### 파일 검증 화면

표시:

* 파일명
* 파일 크기
* Export 일시
* App Version
* Schema Version
* 사용자
* Category 수
* Collection 수
* Item 수
* 추천 이력 수
* 검증 상태

검증 결과:

* 정상
* 지원하지 않는 버전
* 파일 손상
* 필수 데이터 누락

### Restore 경고

```text
전체 복원은 현재 데이터를 백업 파일의 상태로 교체합니다.
이 작업은 되돌릴 수 없습니다.
```

사용자가 확인 문구를 입력하게 해 주세요.

예:

```text
복원을 진행하려면 RESTORE를 입력하세요.
```

버튼:

* 전체 복원
* 취소

MERGE는 다음처럼 비활성 상태로 표시합니다.

```text
MERGE
추후 제공 예정
```

---

# 포스터 UI 검증

## 19. 실제 포스터 비율 Mock 추가

TMDB 검색 화면과 상세 화면에서 실제 이미지와 유사한 세로형 포스터 Mock을 일부 사용해 주세요.

* 비율: 약 2:3
* 영화·TV 결과 중 2~4개는 이미지형 Mock
* 일부 결과는 포스터 없음 Placeholder
* 기존 Legacy Item은 대부분 Placeholder 사용

포스터 유무에 따라 카드 크기나 텍스트 정렬이 흔들리지 않아야 합니다.

저작권이 있는 실제 영화 포스터 대신 추상적이고 저작권 문제가 없는 Mock Artwork를 사용해 주세요.

---

# Prototype 연결

## 20. 추가·수정할 Prototype 흐름

### Collection 추천

```text
홈
→ 랜덤 추천 설정
→ Collection 추천 결과
→ 내부 Item 확인
→ 이 Collection으로 선택
→ 선택 확인
→ 추천 완료
```

### TMDB 등록

```text
콘텐츠 검색
→ 검색 결과
→ 상세 미리보기
→ 앞으로 볼 항목으로 등록
→ Category·Collection 확인
→ 저장
→ Item 상세
```

### 직접 Item 등록

```text
전체 항목
→ 신규 항목 추가
→ 입력
→ 저장
→ Item 상세
```

### Item 수정

```text
Item 상세
→ 수정
→ 저장
→ 상세 복귀
```

### 상태 변경

```text
Item 상세
→ 완료 처리
→ 확인
→ 완료 상태 반영
```

### Category 관리

```text
설정 또는 더보기
→ Category 관리
→ 추가 또는 수정
→ 저장
```

### 추천 이력 상세

```text
추천 이력 목록
→ 이력 상세
→ 현재 Item 또는 Collection 상세
```

### 데이터 복원

```text
데이터 관리
→ 파일 선택
→ 검증 결과
→ 복원 경고
→ 최종 확인
→ 완료 또는 오류
```

---

# 공통 UI 보완

## 21. Modal·Drawer·Bottom Sheet 상태

다음 상태를 Component Variant로 만들어 주세요.

* Default
* Loading
* Success
* Error
* Disabled

Modal과 Bottom Sheet에는 다음 요소가 시각적으로 표현되도록 합니다.

* 닫기 버튼
* 제목
* 설명
* Primary Action
* Secondary Action
* 위험 작업 경고

---

## 22. 접근성 고려

UI Prototype에서 다음을 고려해 주세요.

* Icon-only Button에는 Tooltip 또는 접근 가능한 Label
* 모든 입력 필드에 Label
* 충분한 색상 대비
* 키보드 Focus 상태
* Error Message와 입력 필드 연결
* 버튼 터치 영역 최소 44px
* 색상만으로 상태를 구분하지 않음
* Modal의 첫 번째 Focus 위치를 시각적으로 표현

실제 Focus Trap이나 키보드 코드를 완전히 구현할 필요는 없지만, 구현 가능한 UI 구조로 설계해 주세요.

---

# 수정 후 우선 확인 화면

## 23. 높은 완성도로 보완할 화면

다음 화면을 우선적으로 완성해 주세요.

1. Desktop Collection 추천 결과
2. Mobile Collection 추천 결과
3. TMDB 콘텐츠 상세 미리보기
4. TMDB 등록 확인 Form
5. Desktop Item 상세
6. Mobile Item 상세
7. Item 직접 등록·수정
8. Category 관리
9. 추천 이력 상세
10. Desktop 전체 항목 페이지네이션
11. 데이터 Import 검증·Restore 흐름

---

# 제한사항

## 24. 이번 수정에서 제외

다음 기능은 추가하지 않습니다.

* 실제 Backend API 연동
* 실제 TMDB API 호출
* 실제 데이터 저장
* 인증 구현
* AI 추천
* 사용자 간 공유
* 댓글
* 팔로우
* 알림
* 결제
* 구독
* 스트리밍 재생
* 관리자 Dashboard
* TMDB 인물 검색
* 성인 콘텐츠
* Import MERGE
* 기존 Legacy Item 자동 TMDB 매칭

Mock 데이터와 UI 상태만으로 Prototype을 구성해 주세요.

---

# 최종 요청

현재 PickNext의 전체 디자인 스타일과 공통 Component를 유지하면서 위 기능을 기존 프로젝트에 추가·수정해 주세요.

새 프로젝트를 만들거나 기존 화면을 전면 교체하지 마세요.

특히 다음 세 가지는 반드시 실제 화면과 Prototype 흐름에 반영해 주세요.

1. Collection은 Item 수와 관계없이 랜덤 추천 후보 하나로 처리
2. TMDB 검색 결과는 Category 확인 Form을 거친 후 등록
3. Item 상세·등록·수정과 추천 이력 상세 화면 제공

최종 결과는 실제 React 기반 PickNext Frontend를 구현할 때 화면과 Component 구조를 그대로 참고할 수 있는 수준으로 정리해 주세요.
