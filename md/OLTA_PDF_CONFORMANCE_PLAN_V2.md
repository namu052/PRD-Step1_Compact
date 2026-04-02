# OLTA 자료수집 PDF 명세 정합성 플랜 V2

> **V1 대비 변경사항**
> - 앱 실행 → OLTA 로그인 확인 → 자료수집 시작까지의 기존 흐름은 **수정 대상에서 제외** (현행 유지)
> - **자료수집 진행 현황 실시간 표시** 기능 추가 (Part D)
> - **최종 답변 시 게시판/서브 게시판별 수집 집계** 기능 추가 (Part E)

---

## 수정 불가 영역 (현행 유지)

아래 흐름은 현재 정상 동작하며, 본 플랜에서 **절대 수정하지 않는다**:

1. 앱 실행 (`uvicorn app.main:app`)
2. 프론트엔드에서 질문 입력 → `/api/chat` 호출
3. `chat.py`의 `olta_branch()`에서 `crawler_service.check_olta_login()` 호출
4. 로그인 상태에 따라 OLTA 로그인 확인/미로그인 안내 SSE 이벤트 발행
5. `crawler_service.search()` 호출로 자료수집 **시작**

이 구간의 코드(`chat.py:119~142`, `crawler_service.check_olta_login()`)는 변경하지 않는다.

---

## Context

OLTA.pdf 명세서는 자료수집을 4단계로 정의한다:
1. ① 통합검색란에 검색어 입력
2. ② 7개 메인 게시판 탭 진입 (헌법재판소 결정례 ~ 기타)
3. ③ 각 메인 게시판 내 서브 게시판 진입 (합계 0이면 스킵)
4. ④ 서브 게시판 내 개별 자료를 열어 수집

현재 코드의 괴리:
- **③-1 세목별 서브 게시판 미구현**: ②-1~②-6 메인 게시판에서 `doCollection()` 호출 후 세목별 서브 탭 진입 없이 바로 결과 수집
- **③-1 합계 0 스킵 미구현**: 서브 게시판 합계가 0이면 스킵해야 하는데, 합계 확인 로직 자체가 없음
- **③-2 BBS 인코딩 불안정**: 기타(BBS) 18개 서브 게시판명이 인코딩 깨짐 + 네비게이션 충돌로 실패
- **링크 선택 부정확**: BBS 결과에서 탭/필터 UI 링크를 게시글로 오인
- **수집 진행 현황 미표시**: 어느 게시판에서 몇 건이 수집되고 있는지 사용자에게 알려주지 않음

## 수정 대상 파일
- `backend/app/services/crawler_service.py` — 주 수정 대상 (수집 로직 + 통계 추적)
- `backend/app/config.py` — 서브 게시판 셀렉터 추가
- `backend/app/routers/chat.py` — SSE 수집 통계 이벤트 발행 (자료수집 시작 이후 구간만)
- `backend/app/models/schemas.py` — 수집 통계 모델 추가
- `frontend/src/hooks/useSSE.js` — 수집 통계 SSE 이벤트 수신
- `frontend/src/stores/chatStore.js` — 수집 통계 상태 관리
- `frontend/src/components/chat/` — 수집 진행 현황 UI 컴포넌트
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
              ★ 수집 통계 업데이트 (Part D 연동)
              doCollection(collection_id) 재호출로 메인 탭 복귀
```

**수정 위치:** `_collect_collection_cards()` (현재 line ~1164-1191)

**새 함수:**
- `_discover_sub_boards(page) -> list[SubBoard]`
- `_select_sub_board(page, sub_board) -> bool`
- `_collect_sub_board_cards(page, query, collection_id, sub_board, page_limit) -> list[SearchCard]`

### A-3. 합계 0 스킵

`_discover_sub_boards()` 결과의 `count` 필드가 0이면 해당 서브 게시판을 건너뛴다. 로그에 스킵 사유를 기록한다.

---

## Part B: 기타(BBS) 게시판(②-7) 안정화

### B-1. BBS_BOARDS 인코딩 수정

현재 `BBS_BOARDS`는 이미 UTF-8로 교정되어 있으나, `POPUP_TYPE_MAP`, `COLLECTION_TYPE_MAP` 등에 인코딩 깨짐이 남아있으면 함께 수정한다.

### B-2. 네비게이션 안정화 강화

현재 `_settle_navigation()`이 `wait_for_load_state("load", timeout=2000)`만 사용한다. 이것만으로는 "같은 URL로의 redirect" 패턴을 해소하지 못한다.

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

## Part D: 자료수집 진행 현황 실시간 표시 (신규)

사용자가 자료수집 진행 상태를 게시판/서브 게시판 단위로 실시간 확인할 수 있도록 한다.

### D-1. 수집 통계 데이터 모델

**`backend/app/models/schemas.py`에 추가:**

```python
from pydantic import BaseModel

class BoardCollectionStat(BaseModel):
    """개별 게시판/서브 게시판의 수집 통계"""
    board_name: str           # 메인 게시판명 (예: "법원 판례", "기타")
    sub_board_name: str | None = None  # 서브 게시판명 (예: "취득", "질의응답")
    collected_count: int = 0  # 수집된 자료 수
    skipped: bool = False     # 합계 0으로 스킵되었는지
    status: str = "pending"   # pending | collecting | done | skipped

class CollectionProgress(BaseModel):
    """전체 수집 진행 현황"""
    total_collected: int = 0
    boards: list[BoardCollectionStat] = []
    current_board: str | None = None       # 현재 수집 중인 메인 게시판
    current_sub_board: str | None = None   # 현재 수집 중인 서브 게시판
```

### D-2. crawler_service 내부 통계 추적

`crawler_service.py`의 `search()` 메서드에 **콜백 기반 진행 보고** 메커니즘을 추가한다.

```python
from typing import Callable, Awaitable

# 진행 보고 콜백 타입
ProgressCallback = Callable[[BoardCollectionStat], Awaitable[None]] | None

class OltaCrawlerService:
    async def search(
        self,
        session,
        queries: list[str],
        categories: list[str] | None = None,
        on_progress: ProgressCallback = None,  # ★ 신규 파라미터
    ) -> list[CrawlResult]:
        ...
```

**수집 지점마다 콜백 호출:**

```python
# _collect_collection_cards() 내부 — 메인 게시판 수집 시작
if on_progress:
    await on_progress(BoardCollectionStat(
        board_name=POPUP_TYPE_MAP.get(collection_id, collection_id),
        status="collecting",
    ))

# 서브 게시판 수집 시작 시
if on_progress:
    await on_progress(BoardCollectionStat(
        board_name=board_name,
        sub_board_name=sub_board["label"],
        status="collecting",
    ))

# 서브 게시판 수집 완료 시
if on_progress:
    await on_progress(BoardCollectionStat(
        board_name=board_name,
        sub_board_name=sub_board["label"],
        collected_count=len(cards),
        status="done",
    ))

# 합계 0 스킵 시
if on_progress:
    await on_progress(BoardCollectionStat(
        board_name=board_name,
        sub_board_name=sub_board["label"],
        skipped=True,
        status="skipped",
    ))
```

**BBS 게시판도 동일하게 적용:**
```python
# _search_single_bbs_board() 내부
if on_progress:
    await on_progress(BoardCollectionStat(
        board_name="기타",
        sub_board_name=board.label,  # "질의응답", "지방세상담" 등
        collected_count=len(board_results),
        status="done",
    ))
```

### D-3. SSE 이벤트로 진행 현황 전달

**`chat.py`의 `olta_branch()` 내부에서 콜백을 정의하여 SSE 이벤트를 발행한다.**

> 주의: `olta_branch()`는 `asyncio.create_task()`로 백그라운드 실행되므로, SSE 이벤트를 직접 yield할 수 없다. 기존 `olta_notices` 리스트와 같은 패턴으로 큐에 적재한다.

```python
# chat.py — olta_branch() 내부
crawl_progress_events: list[str] = []

async def on_crawl_progress(stat: BoardCollectionStat):
    """크롤러가 게시판/서브 게시판 수집 상태를 보고할 때 호출됨"""
    crawl_progress_events.append(
        sse_event("crawl_progress", stat.model_dump())
    )

crawl_results = await crawler_service.search(
    session,
    search_plan.keywords,
    search_plan.categories,
    on_progress=on_crawl_progress,  # ★ 콜백 전달
)
```

**SSE 이벤트 형식:**
```json
event: crawl_progress
data: {
    "board_name": "법원 판례",
    "sub_board_name": "취득",
    "collected_count": 5,
    "skipped": false,
    "status": "done"
}
```

**기존 olta_notices와 함께 flush:**
```python
# olta_task 완료 후 flush 구간 (chat.py)
for ev in crawl_progress_events:
    yield ev
for ev in olta_notices:
    yield ev
```

### D-4. 프론트엔드 — 실시간 수집 현황 수신 및 표시

**`frontend/src/hooks/useSSE.js` — 새 이벤트 타입 처리:**

```javascript
// useSSE.js — onmessage 핸들러 내부
case 'crawl_progress':
  useChatStore.getState().updateCrawlProgress(parsed.data)
  break
```

**`frontend/src/stores/chatStore.js` — 수집 통계 상태 추가:**

```javascript
// chatStore.js — state에 추가
crawlProgress: {
  totalCollected: 0,
  boards: [],           // [{ boardName, subBoardName, collectedCount, skipped, status }]
  currentBoard: null,
  currentSubBoard: null,
},

// actions
updateCrawlProgress: (stat) => set((state) => {
  const progress = { ...state.crawlProgress }
  const key = `${stat.board_name}::${stat.sub_board_name || ''}`

  // 기존 항목 업데이트 또는 새 항목 추가
  const idx = progress.boards.findIndex(
    (b) => `${b.boardName}::${b.subBoardName || ''}` === key
  )
  const entry = {
    boardName: stat.board_name,
    subBoardName: stat.sub_board_name,
    collectedCount: stat.collected_count,
    skipped: stat.skipped,
    status: stat.status,
  }
  if (idx >= 0) {
    progress.boards[idx] = entry
  } else {
    progress.boards.push(entry)
  }

  // 현재 진행 중인 게시판 업데이트
  if (stat.status === 'collecting') {
    progress.currentBoard = stat.board_name
    progress.currentSubBoard = stat.sub_board_name
  }

  // 전체 수집 건수 재계산
  progress.totalCollected = progress.boards.reduce(
    (sum, b) => sum + (b.collectedCount || 0), 0
  )

  return { crawlProgress: progress }
}),

resetCrawlProgress: () => set({ crawlProgress: { totalCollected: 0, boards: [], currentBoard: null, currentSubBoard: null } }),
```

**수집 진행 UI 컴포넌트 (`frontend/src/components/chat/CrawlProgressBar.jsx`):**

```
┌─────────────────────────────────────────────────┐
│  📊 OLTA 자료 수집 중...  (총 23건)              │
│                                                   │
│  ✅ 법원 판례          12건                       │
│    ├ 취득  5건  ├ 재산  4건  ├ 기타  3건          │
│  🔄 행안부 유권해석     수집 중...                 │
│    ├ 취득  3건  ├ 등면  수집 중...                 │
│  ⏳ 기타(BBS)           대기 중                    │
│  ⊘  헌법재판소 결정례   0건 (스킵)                 │
└─────────────────────────────────────────────────┘
```

**표시 규칙:**
- `status: "collecting"` → 🔄 수집 중 애니메이션
- `status: "done"` → ✅ 완료 + 수집 건수
- `status: "skipped"` → ⊘ 0건 (스킵)
- `status: "pending"` → ⏳ 대기 중

**표시 위치:** 기존 `stage_change: "searching"` 단계의 ChatPanel 내부, 시스템 메시지 영역 아래에 표시. 수집 완료 후(`stage_change: "drafting"`) 자동으로 접힘(collapse) 처리.

---

## Part E: 최종 답변 시 수집 집계 요약 (신규)

최종 답변(`stage_change: "done"`) 직전에 전체 수집 통계를 집계하여 전달한다.

### E-1. 백엔드 — 수집 집계 SSE 이벤트

**`chat.py`의 sources 이벤트 발행 직전에 집계 이벤트를 발행한다:**

```python
# chat.py — sources 이벤트 발행 직전
crawl_summary = _build_crawl_summary(crawl_progress_events)
yield sse_event("crawl_summary", crawl_summary)
```

**집계 함수:**

```python
def _build_crawl_summary(progress_events: list[BoardCollectionStat]) -> dict:
    """수집 통계를 게시판 > 서브 게시판 계층으로 집계한다."""
    board_map: dict[str, dict] = {}

    for stat in progress_events:
        if stat.board_name not in board_map:
            board_map[stat.board_name] = {
                "board_name": stat.board_name,
                "total_collected": 0,
                "sub_boards": [],
            }
        board = board_map[stat.board_name]

        if stat.sub_board_name:
            board["sub_boards"].append({
                "name": stat.sub_board_name,
                "collected_count": stat.collected_count,
                "skipped": stat.skipped,
            })

        if stat.status == "done":
            board["total_collected"] += stat.collected_count

    # 전체 합계
    grand_total = sum(b["total_collected"] for b in board_map.values())

    return {
        "grand_total": grand_total,
        "boards": list(board_map.values()),
    }
```

**SSE 이벤트 형식 — `crawl_summary`:**
```json
event: crawl_summary
data: {
    "grand_total": 47,
    "boards": [
        {
            "board_name": "법원 판례",
            "total_collected": 12,
            "sub_boards": [
                { "name": "취득", "collected_count": 5, "skipped": false },
                { "name": "재산", "collected_count": 4, "skipped": false },
                { "name": "등면", "collected_count": 0, "skipped": true },
                { "name": "기타", "collected_count": 3, "skipped": false }
            ]
        },
        {
            "board_name": "행안부 유권해석",
            "total_collected": 8,
            "sub_boards": [
                { "name": "취득", "collected_count": 5, "skipped": false },
                { "name": "등면", "collected_count": 3, "skipped": false }
            ]
        },
        {
            "board_name": "기타",
            "total_collected": 27,
            "sub_boards": [
                { "name": "질의응답", "collected_count": 10, "skipped": false },
                { "name": "지방세상담", "collected_count": 8, "skipped": false },
                { "name": "FAQ", "collected_count": 9, "skipped": false },
                { "name": "자유게시판", "collected_count": 0, "skipped": true }
            ]
        }
    ]
}
```

### E-2. 프론트엔드 — 집계 표시

**`useSSE.js` — 집계 이벤트 처리:**

```javascript
case 'crawl_summary':
  useChatStore.getState().setCrawlSummary(parsed.data)
  break
```

**`chatStore.js` — 집계 상태:**

```javascript
crawlSummary: null,  // { grand_total, boards: [...] }

setCrawlSummary: (summary) => set({ crawlSummary: summary }),
```

**최종 답변 영역에 집계 카드 표시 (`CrawlSummaryCard.jsx`):**

```
┌─────────────────────────────────────────────────────┐
│  📋 OLTA 자료 수집 결과 — 총 47건                    │
│                                                       │
│  게시판                수집  세부 내역                 │
│  ─────────────────────────────────────────────────── │
│  법원 판례             12건  취득(5) 재산(4) 기타(3)  │
│                              등면(0·스킵)             │
│  행안부 유권해석        8건  취득(5) 등면(3)          │
│  조세심판원 결정례      0건  전체 스킵                 │
│  기타(BBS)             27건  질의응답(10) 지방세상담(8)│
│                              FAQ(9) 자유게시판(0·스킵)│
│                              … 외 14개 게시판          │
│                                                       │
│  ▸ 세부 펼치기                                        │
└─────────────────────────────────────────────────────┘
```

**표시 규칙:**
- 기본: 메인 게시판별 합계 + 상위 3개 서브 게시판만 표시
- "세부 펼치기" 클릭 시 전체 서브 게시판 목록 표시
- 스킵된 게시판은 회색 + "(스킵)" 라벨
- 수집 0건인 메인 게시판도 표시하여 전체 게시판 수집 여부 투명하게 공개
- PreviewPanel(우측) 하단에 고정 배치, sources 카드 위에 위치

### E-3. 기존 수집 완료 notice 보강

현재 `chat.py:157~159`의 수집 완료 notice:
```python
f"OLTA 자료 수집 완료: {len(crawl_results)}건 수집, "
f"{len(ranked_results)}건 우선 검토, 근거 묶음 {len(slots)}개 정리."
```

이것을 게시판별 요약을 포함하도록 보강:
```python
# 기존 notice 직후에 추가
board_summary_parts = []
for board in crawl_summary["boards"]:
    if board["total_collected"] > 0:
        board_summary_parts.append(f"{board['board_name']}({board['total_collected']}건)")
if board_summary_parts:
    olta_notices.append(stage_notice(
        f"게시판별: {', '.join(board_summary_parts)}"
    ))
```

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
| **7** | Part D-1: 수집 통계 데이터 모델 | 없음 | schemas.py 추가 |
| **8** | Part D-2: crawler_service 콜백 | Step 7 | crawler_service.py search() 시그니처 변경 + 콜백 호출 삽입 |
| **9** | Part D-3: SSE 이벤트 발행 | Step 8 | chat.py olta_branch() 수정 |
| **10** | Part D-4: 프론트엔드 수신 + UI | Step 9 | useSSE.js, chatStore.js, CrawlProgressBar.jsx |
| **11** | Part A-1: 서브 게시판 디스커버리 | Step 2 결과 | config.py + crawler_service.py 신규 함수 |
| **12** | Part A-2: 서브 게시판 순회 | Step 11 | crawler_service.py `_collect_collection_cards` 리팩터 |
| **13** | Part A-3: 합계 0 스킵 | Step 11 | Step 12에 포함 |
| **14** | Part E-1: 집계 SSE 이벤트 | Step 8 | chat.py 집계 함수 + 이벤트 |
| **15** | Part E-2: 프론트엔드 집계 카드 | Step 14 | CrawlSummaryCard.jsx, chatStore.js |
| **16** | Part E-3: 수집 완료 notice 보강 | Step 14 | chat.py notice 수정 |
| **17** | 통합 테스트 | 전체 | test_bbs_crawl.py 실행 |

**핵심 포인트:**
- Step 1~2 (DOM 탐색)가 Part A의 전제조건
- Part B (BBS 안정화)와 Part D (통계 모델/콜백)는 DOM 탐색 없이 병렬 진행 가능
- Part D, E는 Part A/B와 독립적으로 먼저 골격을 구현하고, Part A/B 완료 후 실제 데이터로 연동 검증

---

## 검증 방법

### 단계별 검증
1. `pytest tests/test_bbs_crawler.py -v` — 기존 유닛 테스트 통과
2. `python explore_olta_sub_boards.py` — DOM 구조 확인 (수동)
3. `python test_bbs_crawl.py "장애인감면"` — BBS 안정화 후:
   - 18개 게시판 전체 순회 완료 확인
   - 비게시글 링크(doCollection, 탭 링크) 수집 안 됨 확인
   - 합계 0인 게시판 스킵 로그 확인

### 수집 통계 검증 (Part D/E)
4. 브라우저 DevTools의 EventSource 탭에서 `crawl_progress` 이벤트 수신 확인
5. 수집 진행 중 UI에 게시판별 실시간 카운트 업데이트 확인
6. 수집 완료 후 `crawl_summary` 이벤트의 `grand_total`이 실제 `crawl_results` 길이와 일치 확인
7. CrawlSummaryCard에서 모든 메인 게시판이 표시되고, 스킵된 게시판도 표시 확인

### 최종 통합 검증
- 전체 파이프라인 테스트: `uvicorn app.main:app --reload` + 프론트엔드에서 질문 입력
- OLTA 로그인 상태에서 검색 → ②-1~②-7 전체 수집 확인
- 세목별 서브 게시판 진입 로그 확인
- 수집된 CrawlResult의 type 필드가 올바른 게시판/세목 조합인지 확인
- **수집 진행 현황 UI가 실시간으로 업데이트되는지 확인**
- **최종 답변에 수집 집계 카드가 정확한 수치로 표시되는지 확인**
