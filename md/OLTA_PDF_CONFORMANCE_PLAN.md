# OLTA 자료수집 PDF 명세 정합성 플랜

## Context

OLTA.pdf 명세서는 자료수집을 4단계로 정의한다:
1. ① 통합검색란에 검색어 입력
2. ② 7개 메인 게시판 탭 진입 (헌법재판소 결정례 ~ 기타)
3. ③ 각 메인 게시판 내 서브 게시판 진입 (합계 0이면 스킵)
4. ④ 서브 게시판 내 개별 자료를 열어 수집

현재 코드의 괴리:
- **③-1 세목별 서브 게시판 미구현**: ②-1~②-6 메인 게시판에서 `doCollection()` 호출 후 세목별 서브 탭(취득, 등면, 주민, 지소, 재산, 자동, 기타) 진입 없이 바로 결과 수집
- **③-1 합계 0 스킵 미구현**: 서브 게시판 합계가 0이면 스킵해야 하는데, 합계 확인 로직 자체가 없음
- **③-2 BBS 인코딩 불안정**: 기타(BBS) 18개 서브 게시판명이 인코딩 깨짐 + 네비게이션 충돌로 3~38번 게시판 전부 실패
- **링크 선택 부정확**: BBS 결과에서 탭/필터 UI 링크를 게시글로 오인

## 수정 대상 파일
- `backend/app/services/crawler_service.py` — 주 수정 대상
- `backend/app/config.py` — 서브 게시판 셀렉터 추가
- `backend/test_bbs_crawl.py` — 테스트 스크립트 보강

---

## Part A: 메인 게시판(②-1~②-6) 세목별 서브 게시판 구현

### A-1. OLTA 서브 게시판 UI 탐색 (동적 디스커버리)

현재 `_collect_collection_cards()`는 `doCollection('{collection_id}')` 호출 후 바로 결과를 수집한다. PDF에 따르면 `doCollection()` 후 세목별 서브 탭이 표시되고, 각 탭 아래에 합계가 있어서 클릭해야 한다.

**구현 방안:**

`_collect_collection_cards()` 내에서 `doCollection()` 호출 직후, 서브 게시판 탭을 동적으로 발견하는 함수를 추가한다.

```python
async def _discover_sub_boards(self, page: Page) -> list[dict]:
    """doCollection() 호출 후 세목별 서브 탭을 발견한다.
    Returns: [{"label": "취득", "count": 15, "element_index": 0}, ...]
    """
```

**디스커버리 전략:**
- OLTA 검색 결과 페이지에서 `doCollection()` 호출 후 나타나는 세목별 탭 UI를 JS evaluate로 탐색
- 탭은 보통 `<a>` 또는 `<li>` 형태이고, 합계는 숫자로 표시됨
- 알려진 세목 라벨: 취득, 등면(등록면허세), 주민, 지소(지방소득세), 재산, 자동(자동차세), 기타
- JS로 페이지 DOM을 탐색하여 세목 라벨과 합계 숫자를 추출

**config.py에 추가할 셀렉터:**
```python
OLTA_SELECTORS["search"]["sub_board"] = {
    "tab_container_selectors": [
        ".tab_area", ".sub_tab", ".category_tab",
        ".search_tab", ".result_tab", "[class*='tab']",
    ],
    "tab_link_selectors": [
        "a[onclick*='doTaxType']",
        "a[onclick*='doSubCollection']",
        "li a", "a",
    ],
    "count_selectors": [
        ".count", ".num", ".total",
        "span", "em",
    ],
    "known_labels": ["취득", "등면", "주민", "지소", "재산", "자동", "기타"],
}
```

> **주의**: 실제 OLTA 페이지의 서브 탭 DOM 구조를 아직 정확히 모른다. 따라서 첫 구현은 **headless=False로 실행하면서 DOM을 덤프**하는 디버그 모드를 포함해야 한다. 탐색 스크립트를 먼저 돌려서 실제 DOM을 확인한 뒤 셀렉터를 확정한다.

### A-2. 서브 게시판 순회 로직

`_collect_collection_cards()`를 수정하여 서브 게시판을 순회한다:

```
현재 흐름:
  doCollection(collection_id) → 결과 수집 → 페이징

수정 후 흐름:
  doCollection(collection_id)
  → _discover_sub_boards() 로 서브 탭 발견
  → 서브 탭이 없으면 (기존처럼) 바로 결과 수집
  → 서브 탭이 있으면:
      for sub_board in sub_boards:
          if sub_board["count"] == 0:
              skip (로그 남김)
          else:
              서브 탭 클릭 (JS 호출 또는 element 클릭)
              결과 수집 + 페이징
              doCollection(collection_id) 재호출로 메인 탭 복귀
```

**수정 위치:** `_collect_collection_cards()` (현재 line ~1076-1122)

**새 함수:**
- `_discover_sub_boards(page) -> list[SubBoard]`
- `_select_sub_board(page, sub_board) -> bool`
- `_collect_sub_board_cards(page, query, collection_id, sub_board, page_limit) -> list[SearchCard]`

### A-3. 합계 0 스킵

`_discover_sub_boards()` 결과의 `count` 필드가 0이면 해당 서브 게시판을 건너뛴다. 로그에 스킵 사유를 기록한다.

---

## Part B: 기타(BBS) 게시판(②-7) 안정화

### B-1. BBS_BOARDS 인코딩 수정

현재 `BBS_BOARDS` (line 19-38)의 한글 문자열이 파일 인코딩 문제로 깨져 있다:
```python
BBS_BOARDS = [
    "吏덉쓽?묐떟",     # 질의응답
    "吏諛⑹꽭?곷떞",   # 지방세상담
    ...
]
```

이를 올바른 UTF-8 한글로 교체:
```python
BBS_BOARDS = [
    "질의응답",
    "지방세상담",
    "추진계획서",
    "실무편람",
    "자유게시판",
    "발표자료",
    "기타자료",
    "이용안내 Q&A",
    "매뉴얼",
    "공지사항",
    "시가표준액 조정기준",
    "참고자료",
    "전국단위사건 알림방",
    "FAQ",
    "시가표준액 부동산시장동향",
    "쟁송사무지원 사례",
    "쟁송사무위크숍 자료",
    "지방자치단체 소통마당",
]
```

마찬가지로 `POPUP_TYPE_MAP`, `COLLECTION_TYPE_MAP` 등의 깨진 한글도 모두 수정.

### B-2. 네비게이션 안정화 강화

현재 `_settle_navigation()` (이전 수정에서 추가)이 `wait_for_load_state("load", timeout=2000)`만 사용한다. 이것만으로는 "같은 URL로의 redirect" 패턴을 해소하지 못한다.

**강화 방안:**
```python
async def _settle_navigation(self, page: Page) -> None:
    """진행 중인 네비게이션이 있으면 안정될 때까지 대기."""
    for state in ("load", "domcontentloaded"):
        try:
            await page.wait_for_load_state(state, timeout=2000)
        except Exception:
            pass
    # 짧은 안정화 대기 — redirect가 시작될 시간을 줌
    await asyncio.sleep(0.3)
```

추가로, `_restore_bbs_page_state()`의 rebuild 단계에서 같은 URL로 goto하는 경우를 감지:
```python
# goto 전에 현재 URL이 이미 목표 URL이면 reload 대신 skip
if page.url == target_url:
    await self._wait_for_bbs_refresh(page)
    if await self._is_bbs_search_page_ready(page):
        return True
```

### B-3. 링크 필터 강화

이전 수정에서 `_is_bbs_article_link()`와 `_has_bbs_identifier()`를 추가했으나, 여전히 통과되는 비게시글 링크:
- `href=javascript:doCollection('ordinance')` — 컬렉션 전환 링크
- `href=javascript:authoritativePopUp(60095968)` — 메인 검색 결과 링크 (BBS가 아님)

**추가 제외 패턴:**
```python
_BBS_LINK_NAV_RE = re.compile(
    r"menuNo=|upperMenuId=|/main\.do|importantList|login|logout|sitemap"
    r"|doCollection\(|doSearchPu\(|doPaging\(",
    re.IGNORECASE,
)
```

`href`뿐 아니라 `onclick`도 제외 패턴 검사:
```python
def _is_bbs_article_link(self, title, href, onclick):
    ...
    # href 또는 onclick에 네비게이션 패턴이 있으면 제외
    if href and self._BBS_LINK_NAV_RE.search(href):
        return False
    if onclick and self._BBS_LINK_NAV_RE.search(onclick):
        return False
    ...
```

### B-4. 서브 게시판 합계 0 스킵 (BBS)

현재는 모든 18개 BBS 게시판에 무조건 진입한다. 검색 결과 페이지에서 게시판 필터 후 결과 0건이면 바로 skip하도록 개선:

`_search_single_bbs_board()` 내 결과 카드 추출 직후:
```python
result_cards = await self._extract_bbs_result_cards(search_page, board)
if not result_cards:
    # 합계 0: 바로 다음 게시판으로
    logger.info("BBS board empty: %s (query=%s), skipping", board.label, query)
    break
```

이 부분은 현재도 비슷하게 동작하지만, fallback 필터 재적용 로직이 불필요한 시간을 소모한다. 합계가 실제로 0인 경우를 더 빨리 감지하도록 개선.

---

## Part C: DOM 탐색 스크립트 (A-1의 전제조건)

Part A를 구현하려면 먼저 OLTA 검색 결과 페이지에서 `doCollection()` 호출 후 실제 DOM 구조를 확인해야 한다.

**`backend/explore_olta_sub_boards.py` 스크립트 작성:**
1. OLTA 로그인 대기
2. 통합검색에서 "장애인 감면" 검색
3. 각 collection_id별로 `doCollection()` 호출
4. DOM을 덤프 — 특히:
   - 탭/서브 탭 영역의 HTML
   - 클릭 가능한 요소들의 onclick 속성
   - 합계 숫자가 포함된 요소
5. 결과를 `debug/sub_boards/` 디렉토리에 저장

이 스크립트의 결과로:
- 서브 탭의 실제 CSS 셀렉터 확정
- 서브 탭 전환 JS 함수명 확정 (예: `doTaxTypeCollection()` 또는 다른 이름)
- 합계 값 추출 방법 확정

---

## 구현 순서

| 순서 | 작업 | 의존성 | 예상 범위 |
|------|------|--------|-----------|
| **1** | Part C: DOM 탐색 스크립트 | 없음 | 신규 파일 1개 |
| **2** | Part C 실행 → 실제 DOM 확인 | Step 1 | 수동 실행 |
| **3** | Part B-1: BBS_BOARDS 인코딩 수정 | 없음 | crawler_service.py 상수 교체 |
| **4** | Part B-2: 네비게이션 안정화 강화 | 없음 | crawler_service.py 2개 함수 수정 |
| **5** | Part B-3: 링크 필터 강화 | 없음 | crawler_service.py 1개 함수 수정 |
| **6** | Part B-4: BBS 합계 0 스킵 | 없음 | crawler_service.py 1개 함수 수정 |
| **7** | Part A-1: 서브 게시판 디스커버리 | Step 2 결과 | config.py + crawler_service.py 신규 함수 |
| **8** | Part A-2: 서브 게시판 순회 | Step 7 | crawler_service.py `_collect_collection_cards` 리팩터 |
| **9** | Part A-3: 합계 0 스킵 | Step 7 | Step 8에 포함 |
| **10** | 통합 테스트 | 전체 | test_bbs_crawl.py 실행 |

**핵심 포인트: Step 1~2 (DOM 탐색)가 Part A의 전제조건이다.** 실제 OLTA 페이지의 서브 탭 DOM 구조를 확인하지 않고는 정확한 셀렉터와 JS 함수명을 알 수 없다. 따라서:
- Part B (BBS 안정화)는 DOM 탐색 없이 바로 진행 가능
- Part A (세목별 서브 게시판)는 DOM 탐색 결과에 따라 구체화

---

## 검증 방법

### 단계별 검증
1. `pytest tests/test_bbs_crawler.py -v` — 기존 유닛 테스트 통과
2. `python explore_olta_sub_boards.py` — DOM 구조 확인 (수동)
3. `python test_bbs_crawl.py "장애인감면"` — BBS 안정화 후:
   - 38개 게시판 전체 순회 완료 확인
   - 비게시글 링크(doCollection, 탭 링크) 수집 안 됨 확인
   - 합계 0인 게시판 스킵 로그 확인

### 최종 통합 검증
- 전체 파이프라인 테스트: `uvicorn app.main:app --reload` + 프론트엔드에서 질문 입력
- OLTA 로그인 상태에서 검색 → ②-1~②-7 전체 수집 확인
- 세목별 서브 게시판 진입 로그 확인
- 수집된 CrawlResult의 type 필드가 올바른 게시판/세목 조합인지 확인
