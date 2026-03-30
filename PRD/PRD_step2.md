# PRD Step 2: 채팅 입력 기반 olta.re.kr 실시간 검색

> **문서 버전**: v1.0  
> **작성일**: 2026.03.28  
> **범위**: FastAPI 백엔드, Playwright 크롤링 엔진, GPKI 실제 인증, LLM 1단계(초안 작성)  
> **선행 조건**: Step 1 완료 (프론트엔드 UI 정상 동작 확인)  
> **산출물**: 프론트엔드 ↔ 백엔드 통합 동작, 실제 olta.re.kr 크롤링 기반 답변 생성

---

## 1. 목표 (Objective)

Step 2의 목표는 **채팅으로 받은 사용자 질문을 바탕으로 olta.re.kr에서 실시간으로 관련 자료를 검색하고, LLM이 1단계 답변 초안을 생성**하는 것이다.

Step 1에서 Mock으로 처리하던 API를 실제 FastAPI 백엔드로 교체하되, **2단계 검증 로직은 Step 3에서 구현**한다. Step 2에서는 1단계 초안을 곧바로 최종 답변으로 반환한다.

추가로, 실제 웹사이트 접근 전에 **가상 데이터를 사용한 통합 테스트**를 먼저 수행하여 파이프라인의 정상 동작을 확인한 후, 실제 olta.re.kr 접근으로 전환한다.

---

## 2. 기술 스택

| 구분 | 기술 | 비고 |
|------|------|------|
| Backend | FastAPI (Python 3.11+) | 비동기 API 서버 |
| 크롤링 | Playwright (Python) | GPKI 인증 + 페이지 크롤링 |
| LLM | OpenAI GPT-4o | 1단계 초안 작성 |
| 임베딩 | OpenAI text-embedding-3-small | 크롤링 결과 벡터화 |
| 벡터 검색 | FAISS (In-Memory) | 유사도 검색 |
| SSE | sse-starlette | FastAPI SSE 스트리밍 |
| 테스트 | pytest + pytest-asyncio | 백엔드 테스트 |

---

## 3. 디렉토리 구조

```
backend/
├── app/
│   ├── main.py                    # FastAPI 엔트리포인트
│   ├── config.py                  # 환경변수 설정
│   ├── routers/
│   │   ├── auth.py                # POST /api/auth/gpki, /logout
│   │   └── chat.py                # POST /api/chat, GET /api/preview
│   ├── services/
│   │   ├── gpki_service.py        # Playwright GPKI 인증 로직
│   │   ├── crawler_service.py     # olta.re.kr 크롤링 엔진
│   │   ├── search_service.py      # 키워드 추출 + 검색 전략
│   │   ├── embedding_service.py   # 벡터화 + 유사도 검색
│   │   └── llm_service.py         # OpenAI GPT 호출 (1단계)
│   ├── models/
│   │   ├── schemas.py             # Pydantic 요청/응답 모델
│   │   └── session.py             # 세션 관리 모델
│   ├── core/
│   │   ├── session_manager.py     # 세션 + Playwright 브라우저 풀 관리
│   │   ├── event_emitter.py       # SSE 이벤트 발행 유틸리티
│   │   └── security.py            # 인증서 비밀번호 암호화/복호화
│   └── prompts/
│       └── stage1_prompt.py       # 1단계 시스템 프롬프트
├── tests/
│   ├── conftest.py                # 공통 fixture
│   ├── mocks/
│   │   ├── mock_crawler.py        # 가상 크롤링 결과 반환
│   │   ├── mock_olta_pages.json   # 가상 olta.re.kr 페이지 데이터
│   │   └── mock_llm.py            # 가상 LLM 응답 반환
│   ├── test_auth.py               # 인증 API 테스트
│   ├── test_crawler.py            # 크롤링 엔진 테스트
│   ├── test_search.py             # 검색 전략 테스트
│   ├── test_chat_pipeline.py      # 전체 파이프라인 통합 테스트
│   └── test_chat_e2e.py           # 실제 olta.re.kr 접근 E2E 테스트
├── .env.example
├── requirements.txt
└── docker-compose.yml             # (선택) 로컬 실행용
```

---

## 4. GPKI 실제 인증 구현

### 4.1 인증 플로우

```
[프론트엔드: POST /api/auth/gpki]
    │
    ▼
[FastAPI: auth.py]
    │
    ├─ 1. Playwright 브라우저 인스턴스 생성
    │     - headless: true (백그라운드 실행)
    │     - CDP 연결로 윈도우 최대화
    │
    ├─ 2. https://www.olta.re.kr 접속
    │
    ├─ 3. "GPKI 인증 로그인" 버튼 클릭
    │
    ├─ 4. "행정전자서명인증서 선택창" iframe 탐색
    │     - "인증서 저장 위치 선택" → "하드디스크이동식" 선택
    │     - "사용할 인증서 선택" → 요청된 cert_id에 해당하는 인증서 선택
    │     - "인증서 비밀번호 입력" → 비밀번호 입력
    │     - "확인" 클릭
    │
    ├─ 5. 로그인 상태 확인
    │     - 왼쪽 상단 "로그아웃" 버튼 존재 확인 (최대 10초 대기)
    │     - 존재하면 로그인 성공
    │     - 미존재 시 3회까지 재시도
    │
    ├─ 6. 성공 시:
    │     - session_id 생성
    │     - Playwright 브라우저 컨텍스트를 session_manager에 저장
    │     - 비밀번호는 메모리에서 즉시 삭제
    │     - { success: true, user_name, session_id } 반환
    │
    └─ 7. 실패 시:
          - { success: false, error: "인증에 실패했습니다" } 반환
```

### 4.2 세션 관리 (session_manager.py)

```python
# 인터페이스
class SessionManager:
    sessions: dict[str, Session]

    async def create_session(cert_id, password) -> Session
    async def get_session(session_id) -> Session | None
    async def destroy_session(session_id) -> None
    async def cleanup_expired() -> None  # 30분 미활동 시 자동 정리

class Session:
    session_id: str
    user_name: str
    browser_context: BrowserContext  # Playwright (로그인 상태 유지)
    created_at: datetime
    last_active: datetime
    crawl_cache: dict[str, CrawlResult]  # 크롤링 결과 캐시
```

### 4.3 보안 규칙

- 비밀번호는 POST 요청 수신 → Playwright 입력 → 즉시 메모리에서 삭제 (변수 덮어쓰기)
- session_id는 UUID4로 생성, 예측 불가능
- 세션 만료: 30분 미활동 시 자동 파기 (브라우저 컨텍스트 포함)
- APP 종료 시 모든 세션 및 브라우저 인스턴스 강제 종료

---

## 5. 크롤링 엔진 구현

### 5.1 olta.re.kr 사이트 구조 분석

크롤링 대상 페이지:

| 페이지 | URL 패턴 | 설명 |
|--------|----------|------|
| 법령 검색 | /law/search?keyword=... | 지방세 관련 법령 조문 검색 |
| 해석례 검색 | /interpret/search?keyword=... | 법제처/행안부 해석례 검색 |
| 판례 검색 | /case/search?keyword=... | 조세심판원/법원 판례 검색 |
| 훈령/예규 검색 | /rule/search?keyword=... | 행정 훈령 및 예규 검색 |

> ⚠️ **주의**: 위 URL 패턴은 추정치이며, 실제 구현 시 olta.re.kr의 실제 URL 구조에 맞게 조정해야 한다.

### 5.2 크롤링 파이프라인

```
[사용자 질문]
    │
    ▼
[search_service.py: 키워드 추출]
    │
    ├─ GPT-4o에게 질문에서 검색 키워드 추출 요청
    │   System: "사용자의 지방세 관련 질문에서 검색에 사용할 핵심 키워드를 추출하라.
    │            법령명, 세목, 핵심 쟁점을 포함하여 1~3개의 검색 쿼리를 JSON으로 반환하라."
    │   예시 출력: { "queries": ["취득세 감면", "지방세특례제한법 36조"] }
    │
    ▼
[crawler_service.py: 실시간 크롤링]
    │
    ├─ 각 쿼리에 대해 병렬 크롤링 실행
    │   1. 법령 검색 페이지에서 키워드 검색
    │   2. 해석례 검색 페이지에서 키워드 검색
    │   3. 판례 검색 페이지에서 키워드 검색
    │
    ├─ 각 검색 결과에서 상위 5건의 상세 페이지 접근
    │   - 조문 전문, 해석례 전문, 판례 요약문 추출
    │   - 출처 URL 기록
    │
    ▼
[embedding_service.py: 벡터화 + 랭킹]
    │
    ├─ 크롤링된 문서를 chunk 단위로 분할 (500자 단위, 100자 중첩)
    ├─ OpenAI Embeddings로 벡터화
    ├─ 사용자 질문도 벡터화
    ├─ FAISS로 코사인 유사도 검색 → 상위 5~10개 chunk 선별
    │
    ▼
[선별된 컨텍스트 + 사용자 질문 → LLM 1단계]
```

### 5.3 크롤링 상세 로직 (crawler_service.py)

```python
# 인터페이스
class CrawlerService:
    async def search(
        session: Session,
        queries: list[str],
        categories: list[str] = ["law", "interpret", "case"]
    ) -> list[CrawlResult]

class CrawlResult:
    id: str                  # 고유 ID
    title: str               # 문서 제목 (예: "지방세법 제17조")
    type: str                # "법령" | "해석례" | "판례" | "훈령"
    content: str             # 전문 텍스트
    preview: str             # 2줄 요약 (첫 100자)
    url: str                 # olta.re.kr 원문 URL
    relevance_score: float   # 유사도 점수
    crawled_at: datetime
```

### 5.4 크롤링 에러 처리

| 상황 | 처리 방법 |
|------|----------|
| 페이지 로딩 실패 | 3회 재시도 (2초 간격), 실패 시 해당 카테고리 스킵 |
| 세션 만료 | 자동 재로그인 시도, 실패 시 에러 반환 |
| 검색 결과 없음 | 빈 결과 반환 + LLM에게 "검색 결과 없음" 컨텍스트 전달 |
| 타임아웃 (10초) | 해당 요청 스킵 + 부분 결과로 진행 |
| 사이트 구조 변경 | CSS Selector를 config.py에 분리, 변경 시 즉시 수정 가능 |

---

## 6. LLM 1단계 파이프라인 구현

### 6.1 프롬프트 설계 (stage1_prompt.py)

```python
STAGE1_SYSTEM_PROMPT = """
너는 한국 지방세 전문 AI 상담원이다.
사용자의 질문에 대해 아래 제공된 [검색 결과]를 근거로 답변을 작성하라.

## 답변 규칙
1. 모든 답변에 근거 법령 조문을 명시할 것 (예: 지방세법 제17조 제1항)
2. 각 주장에 대해 [출처: source_id] 태그를 삽입할 것
3. [검색 결과]에 없는 내용은 절대 답변에 포함하지 말 것
4. 불확실한 내용은 "⚠️ 확인 필요"로 명시할 것
5. 답변은 Markdown 형식으로 작성할 것
6. 표, 목록 등을 활용하여 가독성을 높일 것

## 출처 태그 규칙
- 법령 인용 시: [출처: src_001] 형태로 source_id를 명시
- 하나의 문장에 여러 출처가 있으면 [출처: src_001, src_002] 형태
- 답변 마지막에 "📌 참고 출처" 섹션을 추가하여 전체 출처 목록 나열

## 제공된 검색 결과
{crawl_results}
"""

STAGE1_USER_PROMPT = """
질문: {question}

위 검색 결과를 바탕으로 답변해주세요.
"""
```

### 6.2 LLM 호출 로직 (llm_service.py)

```python
# 인터페이스
class LLMService:
    async def generate_draft(
        question: str,
        crawl_results: list[CrawlResult],
        on_token: Callable[[str], Awaitable[None]]  # SSE 토큰 콜백
    ) -> DraftResponse

class DraftResponse:
    answer: str                      # 전체 답변 텍스트
    cited_sources: list[str]         # 인용된 source_id 목록
    token_usage: dict                # { prompt_tokens, completion_tokens }
```

### 6.3 SSE 스트리밍 통합

```python
# chat.py 라우터
@router.post("/api/chat")
async def chat(request: ChatRequest):
    session = session_manager.get_session(request.session_id)

    async def event_generator():
        # 1. 크롤링 단계
        yield sse_event("stage_change", {"stage": "crawling"})
        queries = await search_service.extract_keywords(request.question)
        results = await crawler_service.search(session, queries)

        # 2. 초안 작성 단계
        yield sse_event("stage_change", {"stage": "drafting"})
        async def on_token(token):
            yield sse_event("token", {"content": token})
        draft = await llm_service.generate_draft(
            request.question, results, on_token
        )

        # 3. 출처 전달
        sources = [r.to_source_card() for r in results if r.id in draft.cited_sources]
        yield sse_event("sources", {"sources": sources})

        # 4. 완료 (Step 2에서는 검증 단계 스킵)
        yield sse_event("stage_change", {"stage": "done"})

    return EventSourceResponse(event_generator())
```

---

## 7. 가상 데이터 기반 통합 테스트

### 7.1 테스트 전략

Step 2의 핵심 원칙: **실제 olta.re.kr 접근 전에, 가상 데이터로 전체 파이프라인을 먼저 검증한다.**

```
[테스트 레벨 1] 가상 데이터 단위 테스트
    - mock_crawler.py로 크롤링 결과를 고정 반환
    - mock_llm.py로 LLM 응답을 고정 반환
    - 파이프라인 로직만 검증

[테스트 레벨 2] 가상 데이터 통합 테스트
    - 프론트엔드 → FastAPI → Mock 크롤러 → Mock LLM → SSE 응답
    - 전체 흐름이 정상 동작하는지 검증

[테스트 레벨 3] 실제 olta.re.kr E2E 테스트
    - 가상 데이터 테스트 통과 후에만 실행
    - 실제 GPKI 인증 + 실제 크롤링 + 실제 LLM 호출
    - 수동 트리거 (CI에서 자동 실행하지 않음)
```

### 7.2 가상 크롤링 데이터 (mock_olta_pages.json)

```json
{
  "law_search": {
    "취득세 감면": [
      {
        "id": "mock_law_001",
        "title": "지방세특례제한법 제36조(서민주택 등에 대한 감면)",
        "type": "법령",
        "content": "제36조(서민주택 등에 대한 감면) ① 「주택법」 제2조제1호에 따른 주택으로서 대통령령으로 정하는 주택(이하 이 조에서 \"서민주택\"이라 한다)을 취득하는 경우에는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다. ② 제1항에서 \"대통령령으로 정하는 주택\"이란 취득 당시의 가액이 1억원 이하인 주택을 말한다.",
        "url": "https://www.olta.re.kr/law/detail?lawId=36"
      },
      {
        "id": "mock_law_002",
        "title": "지방세특례제한법 제11조(농업법인에 대한 감면)",
        "type": "법령",
        "content": "제11조(농업법인에 대한 감면) ① 「농어업경영체 육성 및 지원에 관한 법률」 제16조에 따른 영농조합법인이 그 법인의 사업에 직접 사용하기 위하여 취득하는 부동산에 대해서는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다.",
        "url": "https://www.olta.re.kr/law/detail?lawId=11"
      }
    ],
    "재산세 납부": [
      {
        "id": "mock_law_003",
        "title": "지방세법 제115조(납기)",
        "type": "법령",
        "content": "제115조(납기) ① 재산세의 납기는 다음 각 호와 같다. 1. 토지: 매년 9월 16일부터 9월 30일까지 2. 건축물: 매년 7월 16일부터 7월 31일까지 3. 주택: 산출세액의 2분의 1은 매년 7월 16일부터 7월 31일까지, 나머지 2분의 1은 9월 16일부터 9월 30일까지.",
        "url": "https://www.olta.re.kr/law/detail?lawId=115"
      }
    ]
  },
  "interpret_search": {
    "취득세 감면": [
      {
        "id": "mock_interp_001",
        "title": "해석례 2024-0312 (서민주택 감면 적용 범위)",
        "type": "해석례",
        "content": "질의: 취득가액 1억원 이하 주택의 감면 적용 시 부속토지도 포함되는지 여부. 회신: 지방세특례제한법 제36조에 따른 서민주택 감면은 주택과 그 부속토지를 포함하여 적용하는 것이 타당함.",
        "url": "https://www.olta.re.kr/interpret/detail?id=2024-0312"
      }
    ]
  }
}
```

### 7.3 가상 데이터 테스트 케이스

| ID | 테스트 시나리오 | 검증 내용 |
|----|---------------|----------|
| MT-01 | 키워드 추출 | "취득세 감면 대상이 어떻게 되나요?" → ["취득세 감면"] 추출 확인 |
| MT-02 | Mock 크롤링 | 키워드 "취득세 감면" → mock_law_001, mock_law_002, mock_interp_001 반환 확인 |
| MT-03 | 벡터화+검색 | 크롤링 결과 벡터화 → 질문과 유사도 top-3 선별 확인 |
| MT-04 | LLM 초안 생성 | 컨텍스트 + 질문 → 답변에 [출처: mock_law_001] 태그 포함 확인 |
| MT-05 | SSE 스트리밍 | POST /api/chat → SSE 이벤트 순서: stage_change(crawling) → stage_change(drafting) → token... → sources → stage_change(done) |
| MT-06 | 출처 미리보기 | GET /api/preview/mock_law_001 → 정확한 title, content, url 반환 확인 |
| MT-07 | 검색 결과 없음 | 키워드 "존재하지않는세목" → 빈 결과 → "관련 자료를 찾지 못했습니다" 응답 확인 |
| MT-08 | 크롤링 타임아웃 | Mock 크롤러에서 10초 지연 → 타임아웃 처리 → 부분 결과로 답변 생성 확인 |
| MT-09 | 세션 유효성 | 만료된 session_id → 401 에러 반환 확인 |
| MT-10 | 프론트-백 통합 | React 프론트엔드에서 질문 입력 → FastAPI(Mock 크롤러) → SSE 스트리밍 → 답변 + 출처 표시 |

### 7.4 실제 olta.re.kr E2E 테스트

> ⚠️ 가상 데이터 테스트(MT-01~MT-10)가 모두 통과한 후에만 실행한다.

| ID | 테스트 시나리오 | 검증 내용 |
|----|---------------|----------|
| E2E-S2-01 | GPKI 실제 로그인 | 실제 인증서 + 비밀번호 → olta.re.kr 로그인 성공 → "로그아웃" 버튼 확인 |
| E2E-S2-02 | 실제 법령 검색 | "취득세 과세표준" 검색 → 법령 조문 1건 이상 크롤링 확인 |
| E2E-S2-03 | 실제 해석례 검색 | "재산세 과세기준일" 검색 → 해석례 1건 이상 크롤링 확인 |
| E2E-S2-04 | 전체 파이프라인 | 프론트엔드 질문 입력 → 실제 크롤링 → LLM 답변 생성 → 출처 표시 |
| E2E-S2-05 | 세션 재사용 | 연속 2개 질문 → 두 번째 질문에서 GPKI 재인증 없이 크롤링 성공 |

---

## 8. API 상세 설계

### 8.1 POST /api/auth/gpki

```
Request:
{
    "cert_id": "cert_001",      // 인증서 식별자
    "password": "비밀번호"       // 인증서 비밀번호
}

Response (성공):
{
    "success": true,
    "user_name": "홍길동",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}

Response (실패):
{
    "success": false,
    "error": "인증에 실패했습니다. 비밀번호를 확인해 주세요."
}
```

### 8.2 POST /api/chat (SSE)

```
Request:
{
    "session_id": "550e8400-...",
    "question": "취득세 감면 대상이 어떻게 되나요?"
}

Response (SSE Stream):

event: stage_change
data: {"stage": "crawling", "message": "olta.re.kr에서 관련 자료를 검색하고 있습니다..."}

event: stage_change
data: {"stage": "drafting", "message": "검색된 자료를 바탕으로 답변을 작성하고 있습니다..."}

event: token
data: {"content": "##"}

event: token
data: {"content": " 취득세"}

event: token
data: {"content": " 감면"}

... (토큰 단위 스트리밍)

event: sources
data: {"sources": [
    {"id": "src_001", "title": "지방세특례제한법 제36조", "type": "법령", "preview": "서민주택에 대한..."},
    {"id": "src_002", "title": "해석례 2024-0312", "type": "해석례", "preview": "취득가액 1억원 이하..."}
]}

event: stage_change
data: {"stage": "done", "message": "답변이 완료되었습니다."}
```

### 8.3 GET /api/preview/{source_id}

```
Response:
{
    "id": "src_001",
    "title": "지방세특례제한법 제36조(서민주택 등에 대한 감면)",
    "type": "법령",
    "content": "제36조(서민주택 등에 대한 감면) ① 「주택법」 제2조제1호에...",
    "url": "https://www.olta.re.kr/law/detail?lawId=36",
    "crawled_at": "2026-03-28T14:30:00"
}
```

---

## 9. CSS Selector 설정 분리

olta.re.kr의 페이지 구조 변경에 대응하기 위해, 모든 CSS Selector를 설정 파일로 분리한다.

```python
# config.py (또는 selectors.yaml)
OLTA_SELECTORS = {
    "login": {
        "gpki_button": "button:has-text('GPKI 인증 로그인')",
        "cert_iframe": "iframe#certFrame",
        "storage_radio_hdd": "input[value='hdd']",
        "cert_list": ".cert-list .cert-item",
        "password_input": "input[type='password']#certPwd",
        "confirm_button": "button#confirmBtn",
        "logout_button": "a:has-text('로그아웃')"
    },
    "search": {
        "search_input": "input#searchKeyword",
        "search_button": "button#searchBtn",
        "result_list": ".search-result-list .result-item",
        "result_title": ".result-item .title a",
        "result_content": ".result-item .content"
    },
    "detail": {
        "law_content": ".law-content-area",
        "interpret_content": ".interpret-content-area",
        "case_content": ".case-content-area"
    }
}
```

> ⚠️ 위 Selector 값은 추정치이다. 실제 구현 시 olta.re.kr의 실제 DOM 구조를 분석하여 정확한 Selector로 교체해야 한다.

---

## 10. 환경 설정

### .env.example

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Playwright
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_TIMEOUT=10000

# GPKI
GPKI_CERT_BASE_PATH=C:/Users/{username}/AppData/LocalLow/GPKI

# Server
HOST=127.0.0.1
PORT=8000
SESSION_TIMEOUT_MINUTES=30

# Mode
USE_MOCK_CRAWLER=false     # true: 가상 데이터 사용, false: 실제 크롤링
USE_MOCK_LLM=false         # true: 가상 LLM 응답, false: 실제 GPT 호출
```

---

## 11. Step 3 연결 포인트

Step 2 완료 시, Step 3으로의 전환을 위해 다음 인터페이스가 확정된다:

| 항목 | Step 2 (1단계만) | Step 3 (2단계 추가) |
|------|-----------------|-------------------|
| POST /api/chat SSE | stage: crawling → drafting → done | stage: crawling → drafting → **verifying** → done |
| LLM 호출 횟수 | 1회 (초안만) | 2회 (초안 + 검증) |
| 답변 품질 | 출처 태그 포함하나 미검증 | 출처 검증 완료 + 할루시네이션 필터링 |

**핵심 원칙**: Step 2의 chat.py 라우터에 2단계 검증 호출 자리를 주석으로 미리 남겨둔다. Step 3에서는 해당 주석을 실제 코드로 교체하면 된다.

---

## 12. 실행 방법

```bash
# 의존성 설치
cd backend && pip install -r requirements.txt
playwright install chromium

# 가상 데이터 모드로 실행 (개발 초기)
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --reload

# 실제 모드로 실행
uvicorn app.main:app --reload

# 가상 데이터 테스트
pytest tests/ -k "not e2e" -v

# 실제 E2E 테스트 (가상 테스트 통과 후)
pytest tests/test_chat_e2e.py -v

# 프론트엔드 연동 (Step 1 프론트엔드)
cd ../frontend && VITE_API_URL=http://localhost:8000 npm run dev
```

---

> **다음 단계**: Step 2 완료 후, PRD_step3.md에 따라 2단계 검증 로직을 구현한다.
