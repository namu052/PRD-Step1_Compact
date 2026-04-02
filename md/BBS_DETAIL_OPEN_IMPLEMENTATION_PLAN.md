# BBS 상세 열기 안정화 구현 플랜

## 목표

- OLTA `기타` 18개 게시판에서 검색 결과 목록 추출과 상세 열기를 분리한다.
- 검색 결과별 상세 진입 방식을 `직접 URL`, `popup`, `same-tab`, `modal/iframe`, `실패`로 판정한다.
- shared page를 재사용하면서도, 상세 수집 후 원래 검색 상태로 안정적으로 복귀한다.

## 변경 대상

- `backend/app/config.py`
- `backend/app/services/crawler_service.py`
- `backend/test_bbs_crawl.py`
- `backend/tests/test_bbs_crawler.py`

## 구현 단계

### 1. 결과 카드 구조 확장

- `BBSResultCard`에 아래 필드를 추가한다.
- `target_attr`
- `link_html`
- `data_bbs_id`
- `data_ntt_id`
- `row_html`
- `row_index`

- 새 dataclass `BBSOpenTarget`를 추가한다.
- `mode`
- `detail_url`
- `popup_function`
- `popup_args`
- `canonical_id`
- `requires_click`
- `reason`

### 2. BBS selector 세분화

- `OLTA_SELECTORS["bbs"]`에 아래 키를 추가한다.
- `result_container_selectors`
- `result_title_link_selectors`
- `detail_ready_selectors`
- `modal_selectors`
- `iframe_selectors`

- 클릭/복귀 timeout도 별도 설정으로 분리한다.
- `popup_wait_timeout_ms`
- `same_tab_wait_timeout_ms`
- `detail_ready_timeout_ms`
- `restore_timeout_ms`

### 3. 결과 목록 추출 재작성

- 결과 페이지 전체 anchor를 스캔하지 않는다.
- `result container -> result rows -> row 내부 title link` 순서로 추출한다.
- 각 row에서 `title`, `onclick`, `href`, `target`, `data-*`, `meta`, `preview`, `row_html`, `link_html`를 함께 추출한다.

### 4. 상세 타겟 파서 추가

- `onclick/href/data-*`를 받아 `BBSOpenTarget`을 생성하는 함수를 추가한다.
- 판정 우선순위는 아래와 같다.
- `href` 절대 URL
- `href` 상대 URL
- `onclick` 절대 URL
- `javascript:bbsPopUp(...)`
- `window.open(...)`
- `data_bbs_id + data_ntt_id`
- 클릭만 가능한 경우 `click_only`

### 5. 상세 열기 경로 통합

- direct URL과 click fallback을 별도 경로로 유지하지 않는다.
- 새 함수가 `goto` 또는 `클릭 1회`를 수행한 뒤, 열린 결과가 `popup`, `same-tab`, `modal`, `iframe`, `무반응` 중 무엇인지 판정한다.

### 6. 본문 수집 공통화

- 상세 페이지에 진입한 뒤의 본문/댓글/preview 생성 로직은 하나의 함수로 합친다.
- direct URL이든 click이든 동일한 본문 추출 함수를 사용한다.

### 7. 복귀 로직 강화

- 복귀 순서는 아래와 같다.
- `go_back()`
- 실패 시 `restore_url`로 `goto`
- 실패 시 검색 페이지 재진입 후 `게시판 필터 -> 검색어 재입력 -> page_index 복구`

### 8. 테스트 보강

- 단위 테스트 추가
- `javascript:bbsPopUp(...)` 파싱
- `window.open(...)` 파싱
- `data-bbs-id/data-ntt-id` 기반 URL 조립
- `BBSOpenTarget.mode` 판정
- canonical id 생성

- 라이브 스모크 로그 보강
- 첫 3개 결과의 `title`
- `onclick`
- `href`
- `mode`
- `detail_url`
- `reason`

## 구현 순서

1. dataclass와 config 확장
2. 결과 row 기반 추출 함수 작성
3. JS 호출 파서와 상세 타겟 파서 작성
4. 단일 클릭 기반 상세 열기 함수 작성
5. 본문 수집 공통화
6. 복귀 함수 작성
7. `_search_single_bbs_board()` 연결
8. 테스트 추가 및 검증

## 완료 기준

- 단일 게시판에서 결과 카드별 `open_mode`가 로그에 찍힌다.
- 최소 1건은 실제 본문 수집까지 성공한다.
- 상세 수집 후 같은 shared page로 다음 결과를 계속 처리할 수 있다.
- 18개 게시판 순회 중 한 카드 실패가 다음 카드나 다음 게시판으로 전파되지 않는다.
