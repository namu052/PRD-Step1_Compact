# BBS 18개 게시판 수집 복구 및 고도화 플랜

## 1. 목표

현재 OLTA `기타` 카테고리의 18개 게시판 자료가 안정적으로 수집되지 않는 문제를 해결한다.

이번 작업의 목표는 아래 3가지다.

1. 로그인 상태에서 18개 게시판을 실제로 순회하고 자료를 수집할 수 있게 만든다.
2. 일반 검색 경로와 BBS 게시판 수집 경로를 분리해 유지보수성을 높인다.
3. 실패 시 게시판 단위로 원인을 바로 식별할 수 있도록 관측성과 디버그 수단을 보강한다.

## 2. 현재 문제 가설

### 2.1 일반 검색 selector 재사용 문제
- 일반 검색 결과 selector를 BBS 검색 결과에도 그대로 사용하고 있을 가능성이 높다.
- 이 경우 BBS 검색 결과 DOM과 맞지 않아 링크를 찾지 못하고 `0건`으로 종료될 수 있다.

### 2.2 게시판 필터 방식 문제
- 게시판 필터가 현재 하드코딩된 게시판명 문자열에 의존한다.
- 실제 OLTA가 `label`이 아니라 `value` 또는 내부 코드를 기대하면 18개 게시판 전부 필터 적용에 실패할 수 있다.

### 2.3 상세 진입 방식 문제
- 상세 자료 진입이 팝업, same-tab, iframe/modal 중 어느 형태인지 일반 검색 경로와 다를 수 있다.
- 지금처럼 클릭 중심으로 처리하면 DOM 상태 변화에 취약하다.

### 2.4 인증 컨텍스트 문제
- 로그인 상태는 전역 shared browser/context에만 걸려 있고 세션 단위 ownership이 불명확하다.
- 게시판 병렬 순회 중 로그인 상태 확인, 탭 상태, 페이지 이동이 충돌할 수 있다.

### 2.5 관측성 부족
- 현재는 "0건"과 "필터 실패", "링크 추출 실패", "상세 수집 실패"가 명확히 분리되지 않는다.
- 그래서 코드 수정 전에 어디가 깨졌는지 바로 판단하기 어렵다.

## 3. 설계 원칙

### 3.1 BBS 경로는 일반 검색 경로와 분리
- selector, 페이지 이동, 링크 파싱, 상세 수집을 일반 검색 로직과 공유하지 않는다.

### 3.2 DOM discovery 우선
- 게시판명 하드코딩보다, 실제 BBS 페이지 DOM에서 게시판 목록과 식별자를 읽는 방식을 우선한다.

### 3.3 직접 URL 이동 우선
- 가능하면 `onclick`이나 `href`에서 상세 URL을 추출해 직접 이동한다.
- 직접 URL을 만들 수 없을 때만 클릭과 팝업 처리에 의존한다.

### 3.4 실패를 분해해서 기록
- 게시판별로 `discovered`, `filter_applied`, `links_found`, `details_succeeded`, `failure_reason`을 남긴다.

### 3.5 단계별 안정화
- 단일 게시판 단일 질의부터 복구하고, 그 다음 18개 전체 순회, 마지막으로 병렬화 순으로 확장한다.

## 4. 구현 범위

### 4.1 설정 계층
- BBS 전용 selector/config 블록 추가
- 디버그 플래그 및 dump 위치 추가
- 게시판 discovery 모드와 fallback registry 모드 지원

### 4.2 크롤러 구조 개편
- BBS 전용 helper 메서드 추가
- 게시판 discovery, 필터 적용, 링크 추출, 상세 수집, 정규화 분리
- 게시판별 상태 집계 로직 추가

### 4.3 테스트 보강
- BBS result link parsing helper 테스트
- BBS board discovery parsing helper 테스트
- canonical id / dedupe key 테스트

### 4.4 수동 검증 도구
- 기존 `test_bbs_crawl.py`를 기준선 도구로 유지
- 단일 게시판 smoke 모드와 전체 18개 게시판 모드로 나눠 점검

## 5. 단계별 실행 플랜

### Phase 0. 기준선 수집

목표: 현재 실패 지점을 `필터`, `결과 링크`, `상세 수집` 중 어디인지 분해한다.

작업:
- 단일 게시판 1개, 질의 1개 기준 로그를 확보한다.
- 필터 적용 전후 결과 수를 기록한다.
- 현재 페이지 URL, 결과 링크 수, 첫 번째 링크의 `onclick`/`href` 샘플을 기록한다.
- 상세 진입이 팝업인지 same-tab인지 확인한다.

완료 기준:
- "왜 0건인지"를 코드 추정이 아니라 실제 상태값으로 설명할 수 있다.

### Phase 1. DOM 계약 수집

목표: BBS 페이지의 실제 구조를 코드가 의존할 수 있는 형태로 정리한다.

작업:
- 게시판 목록 DOM에서 `label`, `value`, `selected state`를 수집한다.
- 결과 row selector와 result link selector를 확정한다.
- 페이지네이션 방식이 `doPaging()`인지 DOM click인지 확인한다.
- 상세 페이지의 본문 영역 후보 selector를 정리한다.

완료 기준:
- 게시판 레지스트리 초안과 selector 초안이 나온다.

### Phase 2. 설정 계층 분리

목표: 일반 검색 selector와 BBS selector를 완전히 분리한다.

작업:
- `olta_bbs_enabled`
- `olta_bbs_debug`
- `olta_bbs_dump_dir`
- `olta_bbs_mode`
- `olta_bbs_concurrency`
- `olta_bbs_max_pages_per_board`
- `OLTA_SELECTORS["bbs"]` 블록 추가

완료 기준:
- BBS 구조 변경 시 crawler 로직이 아니라 config 중심으로 대응 가능해진다.

### Phase 3. 게시판 레지스트리화

목표: 문자열 목록 대신 구조화된 게시판 정의를 사용한다.

작업:
- `BoardDefinition` 도입
- `label`, `value`, `normalized_key`, `type_label`, `enabled` 구조 사용
- DOM discovery 실패 시 fallback registry 사용

완료 기준:
- 18개 게시판을 "발견됨/설정됨/비활성" 상태로 구분할 수 있다.

### Phase 4. BBS 전용 수집 파이프라인 분리

목표: 일반 검색과 독립적인 BBS 수집 흐름을 만든다.

작업:
- `_open_bbs_search_page()`
- `_discover_bbs_boards()`
- `_apply_bbs_board_filter()`
- `_extract_bbs_result_cards()`
- `_resolve_bbs_detail_target()`
- `_fetch_bbs_detail()`
- `_normalize_bbs_result()`

완료 기준:
- 단일 게시판 수집 로직이 별도 helper 체인으로 읽히고 디버깅 가능해진다.

### Phase 5. 필터 전략 고도화

목표: 게시판 필터 적용 성공률을 높인다.

우선순위:
1. value/code 기반 필터
2. DOM click 기반 필터
3. 기존 JavaScript 함수 호출 기반 필터

완료 기준:
- 최소 1개 게시판에서 필터 적용 후 결과 수 변화가 확인된다.

### Phase 6. 상세 진입 안정화

목표: 게시판 상세 자료 진입 실패율을 낮춘다.

우선순위:
1. 직접 detail URL 생성 후 `goto`
2. 팝업 처리
3. same-tab 처리

완료 기준:
- 결과 row에서 1건 이상 상세 본문을 안정적으로 읽어온다.

### Phase 7. 병렬화 재도입

목표: 성공 경로가 안정화된 뒤 성능을 회복한다.

작업:
- 초기 안정화는 concurrency 1
- 전체 18개 순회가 안정되면 concurrency 2~3
- 실패율과 수집량을 비교하며 조정

완료 기준:
- 병렬화 적용 전보다 수집량이 유지되고 실패율이 증가하지 않는다.

## 6. 코드 변경 예정 파일

### 문서/검증
- `md/BBS_COLLECTION_RECOVERY_PLAN.md`
- `backend/test_bbs_crawl.py`

### 백엔드 설정
- `backend/app/config.py`

### 백엔드 크롤러
- `backend/app/services/crawler_service.py`

### 테스트
- `backend/tests/test_bbs_crawler.py` 신규 추가 가능

## 7. 로그/관측성 설계

게시판별로 아래 필드를 기록한다.

- `run_id`
- `query`
- `board_label`
- `board_value`
- `filter_method`
- `links_found`
- `details_succeeded`
- `details_failed`
- `failure_reason`

디버그 모드에서는 아래 산출물을 남긴다.

- BBS 페이지 HTML dump
- 게시판 필터 후 HTML dump
- 첫 결과 row의 onclick/href 샘플
- 필요 시 screenshot

## 8. 테스트 계획

### 자동 테스트
- 게시판 discovery 파서 테스트
- result link 파서 테스트
- canonical id 생성 테스트
- dedupe 테스트

### 수동 테스트
1. 로그인 상태 확인
2. 단일 게시판 단일 질의 테스트
3. 단일 게시판 다중 질의 테스트
4. 전체 18개 게시판 순회 테스트
5. `/api/chat`에서 `sources`에 `기타/게시판명` 항목 포함 여부 확인

## 9. 완료 기준

아래를 만족하면 복구 완료로 본다.

1. 로그인 상태에서 18개 게시판이 실제로 발견되거나 fallback registry로 매핑된다.
2. 모든 게시판에 대해 검색 시도 여부가 로그에 남는다.
3. 대표 질의 세트 중 최소 일부에서 BBS 결과가 실제 수집된다.
4. `type`이 `기타/게시판명` 형태로 유지된다.
5. BBS 실패 시에도 일반 검색 경로는 정상 동작한다.
6. `/api/chat`의 `sources`에 BBS 자료가 반영된다.

## 10. 구현 우선순위

1. 기준선 진단 및 DOM 계약 수집
2. BBS selector/config 분리
3. 게시판 discovery 및 registry 도입
4. 상세 진입 전략 안정화
5. 18개 게시판 전체 순회 안정화
6. 테스트/로그 정비
7. 세션 ownership 개선
