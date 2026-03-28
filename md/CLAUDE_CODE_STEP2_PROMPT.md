# Claude Code 프롬프트: AI 지방세 지식인 APP - Step 2 (백엔드 + 크롤링 + LLM)

> **이 프롬프트를 Claude Code에 그대로 붙여넣기 하세요.**  
> `claude --dangerously-skip-permissions` 모드에서 실행을 권장합니다.  
> **선행 조건**: Step 1 (프론트엔드)이 `frontend/` 디렉토리에 완성되어 있어야 합니다.

---

너는 지금부터 "AI 지방세 지식인 APP"의 FastAPI 백엔드를 구현하는 시니어 백엔드 개발자야.
Step 1에서 MSW Mock으로 동작하던 API를 실제 Python 백엔드로 교체한다.
이 작업은 총 5단계로 나뉘며, 각 단계를 순서대로 완료해야 해.

## 핵심 규칙

1. **Todolist 파일(`backend/TODO.md`)을 생성**하고, 모든 작업 항목을 체크박스로 관리해.
2. 각 세부 작업을 완료할 때마다 `TODO.md`에서 해당 항목을 `[x]`로 변경해.
3. 각 단계가 끝나면 반드시 **확인사항 체크리스트**를 실행하고, **서버를 실행하여 실제 테스트**해.
4. 테스트 결과를 `TODO.md`의 해당 단계 하단에 기록해.
5. 문제가 발견되면 즉시 수정한 후 다시 테스트해. 모든 체크가 통과해야 다음 단계로 진행해.
6. **Mock 모드 우선**: 모든 단계는 먼저 `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true`로 검증한 후, 나중에 실제 모드로 전환한다.

---

## 사전 작업: TODO.md 생성

가장 먼저 `backend/TODO.md` 파일을 아래 내용으로 생성해:

```markdown
# AI 지방세 지식인 APP - Step 2 Todolist (Backend)

## 🔧 1단계: FastAPI 프로젝트 초기화 + 환경 설정
- [ ] backend/ 디렉토리 구조 생성
- [ ] requirements.txt 작성 및 의존성 설치
- [ ] Playwright chromium 설치
- [ ] .env.example 및 .env 파일 생성
- [ ] config.py 구현 (환경변수 로드, OLTA Selector 분리, Mock 모드 플래그)
- [ ] main.py 구현 (FastAPI 앱, CORS 설정, 라우터 등록, 시작/종료 이벤트)
- [ ] schemas.py 구현 (Pydantic 모델: AuthRequest, AuthResponse, ChatRequest, SourceResponse 등)
- [ ] event_emitter.py 구현 (SSE 이벤트 포맷팅 유틸리티)
- [ ] 가상 데이터 파일 생성 (tests/mocks/mock_olta_pages.json)

### ✅ 1단계 확인사항
- [ ] `cd backend && uvicorn app.main:app --reload` 실행 시 에러 없이 서버 기동?
- [ ] 브라우저에서 `http://localhost:8000/docs` 접속 시 Swagger UI 표시?
- [ ] `curl http://localhost:8000/health` → `{"status":"ok"}` 응답?

📋 1단계 테스트 결과: (여기에 결과 기록)

---

## 🔐 2단계: 인증 API + 세션 관리 (Mock 모드)
- [ ] session.py 모델 구현 (Session 클래스: session_id, user_name, created_at, last_active, crawl_cache)
- [ ] session_manager.py 구현
  - [ ] create_session(cert_id, password) → Session 생성 + UUID4 session_id
  - [ ] get_session(session_id) → Session 조회 (없으면 None)
  - [ ] destroy_session(session_id) → 세션 삭제
  - [ ] cleanup_expired() → 30분 미활동 세션 자동 정리
- [ ] security.py 구현 (비밀번호 메모리 즉시 삭제 유틸리티)
- [ ] auth.py 라우터 구현
  - [ ] GET /api/auth/certs → Mock 인증서 목록 반환
  - [ ] POST /api/auth/gpki → Mock 모드: password=="test1234"면 성공
  - [ ] POST /api/auth/logout → 세션 파기
- [ ] gpki_service.py 구현 (Mock 모드 분기 포함, 실제 Playwright 로직은 껍데기만)
- [ ] 세션 미들웨어 또는 의존성 주입: /api/chat, /api/preview 요청 시 session_id 검증

### ✅ 2단계 확인사항
- [ ] `curl -X GET http://localhost:8000/api/auth/certs` → 인증서 2건 반환?
- [ ] `curl -X POST http://localhost:8000/api/auth/gpki -H "Content-Type: application/json" -d '{"cert_id":"cert_001","password":"test1234"}'` → `{"success":true, "user_name":"홍길동", ...}` ?
- [ ] 잘못된 비밀번호 → `{"success":false, "error":"..."}` ?
- [ ] 로그인 후 받은 session_id로 → `curl -X POST http://localhost:8000/api/auth/logout -H "Content-Type: application/json" -d '{"session_id":"..."}'` → `{"success":true}` ?
- [ ] 로그아웃 후 해당 session_id로 다른 API 호출 시 401 에러?

📋 2단계 테스트 결과: (여기에 결과 기록)

---

## 🔍 3단계: 크롤링 엔진 + 키워드 추출 (Mock 모드)
- [ ] mock_crawler.py 구현 (mock_olta_pages.json 기반 가상 크롤링 결과 반환)
- [ ] mock_llm.py 구현 (가상 키워드 추출 및 답변 생성)
- [ ] CrawlResult 데이터 클래스 정의 (id, title, type, content, preview, url, relevance_score, crawled_at)
- [ ] search_service.py 구현
  - [ ] extract_keywords(question) → Mock: 키워드 추출 규칙 기반 매칭
  - [ ] 실제 모드 자리: GPT-4o 호출로 키워드 추출 (주석으로 TODO 표시)
- [ ] crawler_service.py 구현
  - [ ] search(session, queries, categories) → Mock: mock_olta_pages.json에서 매칭
  - [ ] 실제 모드 자리: Playwright 크롤링 (주석으로 TODO 표시)
  - [ ] 에러 처리: 타임아웃, 결과 없음, 페이지 로딩 실패
- [ ] embedding_service.py 구현
  - [ ] embed_documents(documents) → Mock: 임의 벡터 생성
  - [ ] search_similar(query_vector, doc_vectors, top_k) → Mock: 입력 순서대로 반환
  - [ ] 실제 모드 자리: OpenAI Embeddings + FAISS (주석으로 TODO 표시)
- [ ] pytest 테스트 작성
  - [ ] test_search.py: 키워드 추출 테스트 (MT-01)
  - [ ] test_crawler.py: Mock 크롤링 결과 반환 테스트 (MT-02)

### ✅ 3단계 확인사항
- [ ] `USE_MOCK_CRAWLER=true pytest tests/test_search.py -v` → 키워드 추출 테스트 통과?
- [ ] `USE_MOCK_CRAWLER=true pytest tests/test_crawler.py -v` → Mock 크롤링 테스트 통과?
- [ ] Mock 크롤러에 "취득세 감면" 쿼리 → mock_law_001, mock_law_002, mock_interp_001 3건 반환?
- [ ] Mock 크롤러에 "재산세 납부" 쿼리 → mock_law_003 1건 반환?
- [ ] 존재하지 않는 키워드 → 빈 리스트 반환?

📋 3단계 테스트 결과: (여기에 결과 기록)

---

## 💬 4단계: LLM 파이프라인 + SSE 채팅 API (Mock 모드)
- [ ] stage1_prompt.py 구현 (1단계 시스템 프롬프트 + 사용자 프롬프트 템플릿)
- [ ] llm_service.py 구현
  - [ ] generate_draft(question, crawl_results, on_token) → DraftResponse
  - [ ] Mock 모드: 미리 정의된 답변을 토큰 단위로 스트리밍 (30ms 간격)
  - [ ] 실제 모드 자리: OpenAI ChatCompletion stream=True (주석으로 TODO 표시)
  - [ ] DraftResponse: answer(전체텍스트), cited_sources(인용 source_id 목록), token_usage
- [ ] chat.py 라우터 구현
  - [ ] POST /api/chat → SSE EventSourceResponse
    - [ ] session_id 검증 → 401 에러 처리
    - [ ] stage_change("crawling") 이벤트 발행
    - [ ] search_service.extract_keywords() 호출
    - [ ] crawler_service.search() 호출
    - [ ] stage_change("drafting") 이벤트 발행
    - [ ] llm_service.generate_draft() 호출 (on_token 콜백으로 token 이벤트 발행)
    - [ ] sources 이벤트 발행 (인용된 출처만 필터링)
    - [ ] stage_change("done") 이벤트 발행
    - [ ] # TODO Step 3: 여기에 검증 단계 추가 예정 (주석으로 명시)
  - [ ] GET /api/preview/{source_id} → 세션의 crawl_cache에서 조회하여 반환
- [ ] pytest 테스트 작성
  - [ ] test_chat_pipeline.py: 전체 파이프라인 통합 테스트 (MT-04, MT-05)
  - [ ] SSE 이벤트 순서 검증: stage_change(crawling) → stage_change(drafting) → token... → sources → stage_change(done)
  - [ ] 세션 없는 요청 → 401 에러 테스트 (MT-09)
  - [ ] 검색 결과 없는 질문 → 기본 안내 메시지 테스트 (MT-07)

### ✅ 4단계 확인사항
- [ ] `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/test_chat_pipeline.py -v` → 모든 테스트 통과?
- [ ] curl로 SSE 스트리밍 테스트:
  ```bash
  # 먼저 로그인하여 session_id 획득
  SESSION=$(curl -s -X POST http://localhost:8000/api/auth/gpki \
    -H "Content-Type: application/json" \
    -d '{"cert_id":"cert_001","password":"test1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

  # SSE 스트리밍 테스트
  curl -N -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d "{\"session_id\":\"$SESSION\",\"question\":\"취득세 감면 대상\"}"
  ```
  → `event: stage_change` + `event: token` + `event: sources` + `event: stage_change(done)` 순서로 출력?
- [ ] 존재하지 않는 session_id로 /api/chat 호출 → 401 에러?
- [ ] /api/preview/{source_id} → 올바른 출처 내용 반환?
- [ ] 매칭 안 되는 질문 → "관련 자료를 찾지 못했습니다" 메시지 포함 답변?

📋 4단계 테스트 결과: (여기에 결과 기록)

---

## 🔗 5단계: 프론트엔드 연동 + 통합 테스트
- [ ] Step 1 프론트엔드에서 MSW 비활성화 (또는 환경변수로 분기)
  - [ ] main.jsx에서 MSW 시작 코드를 `VITE_USE_MOCK !== 'true'`일 때 스킵하도록 수정
  - [ ] vite.config.js에 proxy 설정: `/api` → `http://localhost:8000`
- [ ] 프론트엔드 + 백엔드 동시 실행 테스트
- [ ] 시나리오 1: GPKI 로그인 → 채팅 활성화
- [ ] 시나리오 2: "취득세 감면 대상" 질문 → SSE 스트리밍 답변 + 출처 카드 표시
- [ ] 시나리오 3: "재산세 납부 기한" 연속 질문 → 이전 대화 유지 + 새 답변
- [ ] 시나리오 4: 미등록 질문 "자동차세 환급" → 기본 안내 메시지
- [ ] 시나리오 5: 출처 카드 클릭 → 상세 미리보기 정상 표시
- [ ] 시나리오 6: 로그아웃 → 재로그인 → 정상 동작
- [ ] 에러 처리: 백엔드 중단 시 프론트엔드에 에러 메시지 표시
- [ ] `npm run build` (프론트엔드 빌드) 에러 없는지 확인

### ✅ 5단계 최종 확인사항 (전체 통합 플로우)
- [ ] 백엔드: `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --port 8000` 실행
- [ ] 프론트엔드: `cd frontend && npm run dev` 실행
- [ ] 브라우저 http://localhost:5173 접속 → GPKI 모달 표시
- [ ] 인증서 선택 + "test1234" → 로그인 성공 → 채팅 활성화
- [ ] "취득세 감면 대상" 입력 → 스테퍼 전환 + 스트리밍 답변 + 출처 2건
- [ ] 출처 카드 클릭 → 상세 내용 + "원문 바로가기"
- [ ] "재산세 납부 기한" 입력 → 연속 대화 + 출처 1건
- [ ] "자동차세 환급" → 기본 안내 메시지
- [ ] 로그아웃 → GPKI 모달 재표시 → 재로그인 성공
- [ ] 모든 pytest 테스트 통과: `cd backend && USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v`

📋 5단계 테스트 결과: (여기에 결과 기록)
```

---

## ▶ 1단계 시작: FastAPI 프로젝트 초기화 + 환경 설정

이제 1단계를 시작해. 아래 지시사항을 **순서대로** 실행해.

### 1-1. 디렉토리 구조 생성

```bash
mkdir -p backend/app/{routers,services,models,core,prompts}
mkdir -p backend/tests/mocks
```

### 1-2. requirements.txt

```
backend/requirements.txt
```

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sse-starlette==2.1.0
pydantic==2.9.0
pydantic-settings==2.5.0
python-dotenv==1.0.1
openai==1.50.0
playwright==1.47.0
faiss-cpu==1.8.0
numpy==1.26.4
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
```

### 1-3. .env.example 및 .env

**`backend/.env.example`**:
```bash
# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Playwright
PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_TIMEOUT=10000

# GPKI
GPKI_CERT_BASE_PATH=C:/Users/username/AppData/LocalLow/GPKI

# Server
HOST=127.0.0.1
PORT=8000
SESSION_TIMEOUT_MINUTES=30

# Mode (true = 가상 데이터 사용, false = 실제 연동)
USE_MOCK_CRAWLER=true
USE_MOCK_LLM=true
```

**`backend/.env`**: `.env.example`을 복사하여 생성. `USE_MOCK_CRAWLER=true`, `USE_MOCK_LLM=true`로 설정.

### 1-4. config.py

**`backend/app/config.py`** — 아래 내용으로 구현해:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # Playwright
    playwright_headless: bool = True
    playwright_timeout: int = 10000

    # GPKI
    gpki_cert_base_path: str = ""

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    session_timeout_minutes: int = 30

    # Mode flags
    use_mock_crawler: bool = True
    use_mock_llm: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings():
    return Settings()

# olta.re.kr CSS Selector 설정 (사이트 구조 변경 시 여기만 수정)
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

### 1-5. schemas.py

**`backend/app/models/schemas.py`**:
```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ── Auth ──
class AuthRequest(BaseModel):
    cert_id: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    user_name: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

class LogoutRequest(BaseModel):
    session_id: str

class CertInfo(BaseModel):
    id: str
    owner: str
    department: str
    validFrom: str
    validTo: str
    serial: str

# ── Chat ──
class ChatRequest(BaseModel):
    session_id: str
    question: str

class SourceCard(BaseModel):
    id: str
    title: str
    type: str  # "법령" | "해석례" | "판례" | "훈령"
    preview: str

class SourceDetail(BaseModel):
    id: str
    title: str
    type: str
    content: str
    url: str
    crawled_at: Optional[datetime] = None

# ── Crawl ──
class CrawlResult(BaseModel):
    id: str
    title: str
    type: str
    content: str
    preview: str
    url: str
    relevance_score: float = 0.0
    crawled_at: datetime = datetime.now()

    def to_source_card(self) -> dict:
        return {"id": self.id, "title": self.title, "type": self.type, "preview": self.preview}

    def to_source_detail(self) -> dict:
        return {"id": self.id, "title": self.title, "type": self.type, "content": self.content, "url": self.url, "crawled_at": self.crawled_at.isoformat()}
```

### 1-6. event_emitter.py

**`backend/app/core/event_emitter.py`**:
```python
import json

def sse_event(event_type: str, data: dict) -> str:
    """SSE 포맷의 이벤트 문자열 생성"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 1-7. main.py

**`backend/app/main.py`**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, chat

app = FastAPI(title="AI 지방세 지식인 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

아직 auth.py와 chat.py가 없으면 빈 라우터 파일을 만들어:

**`backend/app/routers/auth.py`**:
```python
from fastapi import APIRouter
router = APIRouter()
```

**`backend/app/routers/chat.py`**:
```python
from fastapi import APIRouter
router = APIRouter()
```

### 1-8. 가상 데이터 파일 생성

**`backend/tests/mocks/mock_olta_pages.json`**: PRD에 명시된 가상 크롤링 데이터를 그대로 사용해.

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

### 1-9. conftest.py

**`backend/tests/conftest.py`**:
```python
import os
import pytest

# 테스트 시 항상 Mock 모드
os.environ["USE_MOCK_CRAWLER"] = "true"
os.environ["USE_MOCK_LLM"] = "true"

@pytest.fixture
def mock_session_id():
    """테스트용 세션 생성 후 session_id 반환"""
    from app.core.session_manager import session_manager
    import asyncio
    session = asyncio.get_event_loop().run_until_complete(
        session_manager.create_session("cert_001", "test1234")
    )
    return session.session_id
```

### 1-10. 1단계 확인

모든 파일 생성 후:
1. `cd backend && uvicorn app.main:app --reload --port 8000`
2. 브라우저에서 `http://localhost:8000/docs` 접속 → Swagger UI 확인
3. `curl http://localhost:8000/health` → `{"status":"ok"}`

**TODO.md 1단계 항목들을 모두 `[x]`로 업데이트하고, 테스트 결과를 기록해.**

---

## ▶ 2단계 시작: 인증 API + 세션 관리 (Mock 모드)

1단계 확인이 모두 통과하면 2단계를 시작해.

### 2-1. session.py

**`backend/app/models/session.py`**:
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

@dataclass
class Session:
    session_id: str
    user_name: str
    cert_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    browser_context: Optional[Any] = None  # Playwright BrowserContext (실제 모드)
    crawl_cache: dict = field(default_factory=dict)  # source_id → CrawlResult

    def touch(self):
        """마지막 활동 시간 갱신"""
        self.last_active = datetime.now()

    def is_expired(self, timeout_minutes: int) -> bool:
        elapsed = (datetime.now() - self.last_active).total_seconds() / 60
        return elapsed > timeout_minutes
```

### 2-2. session_manager.py

**`backend/app/core/session_manager.py`** — 아래 인터페이스로 구현해:

```python
import uuid
from datetime import datetime
from app.models.session import Session
from app.config import get_settings

class SessionManager:
    def __init__(self):
        self.sessions: dict[str, Session] = {}

    async def create_session(self, cert_id: str, password: str) -> Session:
        """새 세션 생성 + Mock 모드에서는 인증서 ID로 사용자명 결정"""
        settings = get_settings()
        session_id = str(uuid.uuid4())

        # Mock 모드: 인증서 ID → 사용자명 매핑
        mock_users = {"cert_001": "홍길동", "cert_002": "김영희"}
        user_name = mock_users.get(cert_id, "사용자")

        session = Session(
            session_id=session_id,
            user_name=user_name,
            cert_id=cert_id
        )
        self.sessions[session_id] = session
        return session

    async def get_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if session and not session.is_expired(get_settings().session_timeout_minutes):
            session.touch()
            return session
        elif session:
            await self.destroy_session(session_id)
        return None

    async def destroy_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session and session.browser_context:
            try:
                await session.browser_context.close()
            except:
                pass

    async def cleanup_expired(self):
        timeout = get_settings().session_timeout_minutes
        expired = [sid for sid, s in self.sessions.items() if s.is_expired(timeout)]
        for sid in expired:
            await self.destroy_session(sid)

# 싱글톤 인스턴스
session_manager = SessionManager()
```

### 2-3. auth.py 라우터

**`backend/app/routers/auth.py`** — 아래 3개 엔드포인트를 구현해:

1. **`GET /api/auth/certs`**: Mock 인증서 목록 반환 (Step 1의 mockCerts.json과 동일한 데이터)
2. **`POST /api/auth/gpki`**: `AuthRequest` 수신 → password가 "test1234"이면 성공, 아니면 실패. 성공 시 `session_manager.create_session()` 호출하여 session_id 반환.
3. **`POST /api/auth/logout`**: `LogoutRequest` 수신 → `session_manager.destroy_session()` 호출

**보안 규칙**: password 변수는 사용 후 즉시 `password = "0" * len(password)` + `del password`로 덮어쓰기.

### 2-4. 2단계 확인

구현 후 서버 재시작하고:
1. curl로 인증서 목록, 로그인 성공/실패, 로그아웃 테스트
2. TODO.md 2단계 확인사항을 모두 체크하고 결과 기록

---

## ▶ 3단계 시작: 크롤링 엔진 + 키워드 추출 (Mock 모드)

2단계 확인이 모두 통과하면 3단계를 시작해.

### 3-1. mock_crawler.py

**`backend/tests/mocks/mock_crawler.py`**:
- `mock_olta_pages.json`을 로드
- `search(queries, categories)` 메서드: 각 query에 대해 law_search, interpret_search에서 키워드 부분 매칭
- 매칭된 결과를 `CrawlResult` 객체 리스트로 반환
- preview는 content의 첫 100자

### 3-2. mock_llm.py

**`backend/tests/mocks/mock_llm.py`**:
- `extract_keywords(question)` 메서드: 간단한 키워드 매칭 규칙
  - "취득세" 포함 → ["취득세 감면"]
  - "재산세" 포함 → ["재산세 납부"]
  - 기타 → [question 그대로]
- `generate_draft(question, crawl_results)` 메서드: CrawlResult를 기반으로 미리 정의된 Markdown 답변 생성

### 3-3. search_service.py

**`backend/app/services/search_service.py`**:
```python
from app.config import get_settings

class SearchService:
    async def extract_keywords(self, question: str) -> list[str]:
        settings = get_settings()
        if settings.use_mock_llm:
            return self._mock_extract(question)
        else:
            # TODO Step 2 실제 모드: OpenAI GPT-4o로 키워드 추출
            # response = await openai_client.chat.completions.create(...)
            # return parsed_keywords
            raise NotImplementedError("실제 LLM 키워드 추출 미구현")

    def _mock_extract(self, question: str) -> list[str]:
        """규칙 기반 키워드 추출 (Mock)"""
        keywords = []
        keyword_map = {
            "취득세": "취득세 감면",
            "재산세": "재산세 납부",
            "등록면허세": "등록면허세",
            "자동차세": "자동차세",
            "주민세": "주민세",
        }
        for trigger, keyword in keyword_map.items():
            if trigger in question:
                keywords.append(keyword)
        return keywords if keywords else [question]

search_service = SearchService()
```

### 3-4. crawler_service.py

**`backend/app/services/crawler_service.py`**:
```python
import json
from pathlib import Path
from datetime import datetime
from app.config import get_settings
from app.models.schemas import CrawlResult

class CrawlerService:
    def __init__(self):
        self._mock_data = None

    def _load_mock_data(self):
        if self._mock_data is None:
            mock_path = Path(__file__).parent.parent.parent / "tests" / "mocks" / "mock_olta_pages.json"
            with open(mock_path, "r", encoding="utf-8") as f:
                self._mock_data = json.load(f)
        return self._mock_data

    async def search(self, session, queries: list[str], categories: list[str] = None) -> list[CrawlResult]:
        settings = get_settings()
        if settings.use_mock_crawler:
            return self._mock_search(queries)
        else:
            # TODO Step 2 실제 모드: Playwright로 olta.re.kr 크롤링
            # return await self._real_search(session, queries, categories)
            raise NotImplementedError("실제 크롤링 미구현")

    def _mock_search(self, queries: list[str]) -> list[CrawlResult]:
        data = self._load_mock_data()
        results = []
        seen_ids = set()

        for query in queries:
            for category in ["law_search", "interpret_search"]:
                category_data = data.get(category, {})
                for keyword, items in category_data.items():
                    # 부분 매칭: 쿼리가 키워드에 포함되거나 키워드가 쿼리에 포함
                    if query in keyword or keyword in query:
                        for item in items:
                            if item["id"] not in seen_ids:
                                seen_ids.add(item["id"])
                                results.append(CrawlResult(
                                    id=item["id"],
                                    title=item["title"],
                                    type=item["type"],
                                    content=item["content"],
                                    preview=item["content"][:100] + "...",
                                    url=item["url"],
                                    relevance_score=0.9,
                                    crawled_at=datetime.now()
                                ))
        return results

crawler_service = CrawlerService()
```

### 3-5. embedding_service.py

**`backend/app/services/embedding_service.py`**:
```python
from app.config import get_settings
from app.models.schemas import CrawlResult

class EmbeddingService:
    async def rank_results(self, question: str, results: list[CrawlResult], top_k: int = 5) -> list[CrawlResult]:
        settings = get_settings()
        if settings.use_mock_crawler:
            # Mock: 입력 순서 그대로 반환 (최대 top_k개)
            return results[:top_k]
        else:
            # TODO Step 2 실제 모드: OpenAI Embeddings + FAISS 유사도 검색
            # 1. question 벡터화
            # 2. 각 result.content 벡터화
            # 3. FAISS 인덱스 생성 → 유사도 검색 → top_k 반환
            raise NotImplementedError("실제 임베딩 검색 미구현")

embedding_service = EmbeddingService()
```

### 3-6. pytest 테스트 작성

**`backend/tests/test_search.py`**:
```python
import pytest
from app.services.search_service import search_service

@pytest.mark.asyncio
async def test_extract_keywords_취득세():
    keywords = await search_service.extract_keywords("취득세 감면 대상이 어떻게 되나요?")
    assert "취득세 감면" in keywords

@pytest.mark.asyncio
async def test_extract_keywords_재산세():
    keywords = await search_service.extract_keywords("재산세 납부 기한은 언제인가요?")
    assert "재산세 납부" in keywords

@pytest.mark.asyncio
async def test_extract_keywords_unknown():
    keywords = await search_service.extract_keywords("잘 모르겠는 질문입니다")
    assert len(keywords) >= 1
```

**`backend/tests/test_crawler.py`**:
```python
import pytest
from app.services.crawler_service import crawler_service

@pytest.mark.asyncio
async def test_mock_crawl_취득세():
    results = await crawler_service.search(None, ["취득세 감면"])
    assert len(results) >= 2  # mock_law_001, mock_law_002, mock_interp_001
    ids = [r.id for r in results]
    assert "mock_law_001" in ids
    assert "mock_law_002" in ids

@pytest.mark.asyncio
async def test_mock_crawl_재산세():
    results = await crawler_service.search(None, ["재산세 납부"])
    assert len(results) >= 1
    assert results[0].id == "mock_law_003"

@pytest.mark.asyncio
async def test_mock_crawl_no_results():
    results = await crawler_service.search(None, ["존재하지않는세목"])
    assert len(results) == 0
```

### 3-7. 3단계 확인

```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/test_search.py tests/test_crawler.py -v
```

모든 테스트 통과 확인 후 TODO.md 업데이트.

---

## ▶ 4단계 시작: LLM 파이프라인 + SSE 채팅 API (Mock 모드)

3단계 확인이 모두 통과하면 4단계를 시작해.

### 4-1. stage1_prompt.py

**`backend/app/prompts/stage1_prompt.py`**:
```python
STAGE1_SYSTEM_PROMPT = """너는 한국 지방세 전문 AI 상담원이다.
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
- 답변 마지막에 "📌 참고 출처" 섹션을 추가하여 전체 출처 목록 나열

## 제공된 검색 결과
{crawl_results}
"""

STAGE1_USER_PROMPT = """질문: {question}

위 검색 결과를 바탕으로 답변해주세요."""

NO_RESULTS_ANSWER = """관련 자료를 찾지 못했습니다.

질문을 더 구체적으로 입력하시거나, 다른 키워드로 다시 질문해 주세요.

> 예시: "취득세 감면 대상", "재산세 납부 기한", "등록면허세 세율" 등"""
```

### 4-2. llm_service.py

**`backend/app/services/llm_service.py`** — 아래 구조로 구현해:

```python
import asyncio
from dataclasses import dataclass
from typing import Callable, Awaitable, Optional
from app.config import get_settings
from app.models.schemas import CrawlResult
from app.prompts.stage1_prompt import STAGE1_SYSTEM_PROMPT, STAGE1_USER_PROMPT, NO_RESULTS_ANSWER

@dataclass
class DraftResponse:
    answer: str
    cited_sources: list[str]
    token_usage: dict

class LLMService:
    async def generate_draft(
        self,
        question: str,
        crawl_results: list[CrawlResult],
        on_token: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> DraftResponse:
        settings = get_settings()

        # 검색 결과가 없으면 기본 안내 메시지
        if not crawl_results:
            if on_token:
                for chunk in [NO_RESULTS_ANSWER[i:i+5] for i in range(0, len(NO_RESULTS_ANSWER), 5)]:
                    await on_token(chunk)
                    await asyncio.sleep(0.03)
            return DraftResponse(answer=NO_RESULTS_ANSWER, cited_sources=[], token_usage={})

        if settings.use_mock_llm:
            return await self._mock_generate(question, crawl_results, on_token)
        else:
            # TODO Step 2 실제 모드: OpenAI ChatCompletion stream=True
            raise NotImplementedError("실제 LLM 호출 미구현")

    async def _mock_generate(self, question, crawl_results, on_token):
        """Mock 모드: 크롤링 결과를 기반으로 Markdown 답변 생성"""
        # 크롤링 결과를 조합하여 답변 구성
        lines = [f"## {question}에 대한 답변\n"]
        cited = []
        for i, result in enumerate(crawl_results):
            lines.append(f"### {i+1}. {result.title}\n")
            lines.append(f"{result.content[:200]}\n")
            lines.append(f"[출처: {result.id}]\n")
            cited.append(result.id)
        lines.append(f"\n---\n📌 **참고 출처**:")
        for result in crawl_results:
            lines.append(f"\n- {result.title} ({result.type})")

        answer = "\n".join(lines)

        # 토큰 단위 스트리밍 (5글자 단위)
        if on_token:
            for i in range(0, len(answer), 5):
                chunk = answer[i:i+5]
                await on_token(chunk)
                await asyncio.sleep(0.03)

        return DraftResponse(answer=answer, cited_sources=cited, token_usage={"prompt_tokens": 0, "completion_tokens": 0})

llm_service = LLMService()
```

### 4-3. chat.py 라우터

**`backend/app/routers/chat.py`** — 핵심 라우터 구현:

```python
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.core.session_manager import session_manager
from app.core.event_emitter import sse_event
from app.services.search_service import search_service
from app.services.crawler_service import crawler_service
from app.services.embedding_service import embedding_service
from app.services.llm_service import llm_service

router = APIRouter()

@router.post("/api/chat")
async def chat(request: ChatRequest):
    # 세션 검증
    session = await session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다. 다시 로그인해 주세요.")

    async def event_generator():
        # ── 1. 크롤링 단계 ──
        yield sse_event("stage_change", {"stage": "crawling", "message": "olta.re.kr에서 관련 자료를 검색하고 있습니다..."})
        await asyncio.sleep(0.5)  # UI 전환 여유

        queries = await search_service.extract_keywords(request.question)
        crawl_results = await crawler_service.search(session, queries)

        # 벡터 유사도 랭킹
        ranked_results = await embedding_service.rank_results(request.question, crawl_results)

        # 크롤링 결과를 세션 캐시에 저장 (미리보기용)
        for result in ranked_results:
            session.crawl_cache[result.id] = result

        # ── 2. 초안 작성 단계 ──
        yield sse_event("stage_change", {"stage": "drafting", "message": "검색된 자료를 바탕으로 답변을 작성하고 있습니다..."})

        collected_tokens = []
        async def on_token(token):
            collected_tokens.append(token)

        draft = await llm_service.generate_draft(request.question, ranked_results, on_token)

        # 토큰 스트리밍 (SSE는 제너레이터에서만 yield 가능하므로 수집 후 재전송)
        for token in collected_tokens:
            yield sse_event("token", {"content": token})

        # ── 3. 출처 전달 ──
        source_cards = [r.to_source_card() for r in ranked_results if r.id in draft.cited_sources]
        if source_cards:
            yield sse_event("sources", {"sources": source_cards})

        # ── TODO Step 3: 여기에 2단계 검증 로직 추가 예정 ──
        # yield sse_event("stage_change", {"stage": "verifying", ...})
        # verification = await verification_service.verify(draft, crawl_results)
        # final = await final_generator.generate(draft, verification)

        # ── 4. 완료 ──
        yield sse_event("stage_change", {"stage": "done", "message": "답변이 완료되었습니다."})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@router.get("/api/preview/{source_id}")
async def preview_source(source_id: str):
    # 모든 세션의 캐시에서 검색 (간소화)
    for session in session_manager.sessions.values():
        if source_id in session.crawl_cache:
            result = session.crawl_cache[source_id]
            return result.to_source_detail()
    raise HTTPException(status_code=404, detail="출처를 찾을 수 없습니다.")
```

### 4-4. pytest 통합 테스트

**`backend/tests/test_chat_pipeline.py`**:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_chat_pipeline_full():
    """전체 파이프라인: 로그인 → 채팅 → SSE 응답"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 로그인
        login_res = await client.post("/api/auth/gpki", json={"cert_id": "cert_001", "password": "test1234"})
        assert login_res.status_code == 200
        session_id = login_res.json()["session_id"]

        # 채팅 (SSE)
        chat_res = await client.post("/api/chat", json={"session_id": session_id, "question": "취득세 감면 대상"})
        assert chat_res.status_code == 200
        body = chat_res.text

        # SSE 이벤트 파싱 검증
        assert "event: stage_change" in body
        assert '"stage": "crawling"' in body or '"stage":"crawling"' in body
        assert "event: token" in body
        assert "event: sources" in body
        assert '"stage": "done"' in body or '"stage":"done"' in body

@pytest.mark.asyncio
async def test_chat_invalid_session():
    """유효하지 않은 세션 → 401"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/chat", json={"session_id": "fake-session", "question": "테스트"})
        assert res.status_code == 401

@pytest.mark.asyncio
async def test_chat_no_results():
    """매칭 안 되는 질문 → 기본 안내 메시지"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post("/api/auth/gpki", json={"cert_id": "cert_001", "password": "test1234"})
        session_id = login_res.json()["session_id"]

        chat_res = await client.post("/api/chat", json={"session_id": session_id, "question": "존재하지않는세목"})
        assert chat_res.status_code == 200
        assert "관련 자료를 찾지 못했습니다" in chat_res.text

@pytest.mark.asyncio
async def test_preview_source():
    """출처 미리보기"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 로그인 + 채팅 (캐시 생성)
        login_res = await client.post("/api/auth/gpki", json={"cert_id": "cert_001", "password": "test1234"})
        session_id = login_res.json()["session_id"]
        await client.post("/api/chat", json={"session_id": session_id, "question": "취득세 감면"})

        # 미리보기
        preview_res = await client.get("/api/preview/mock_law_001")
        assert preview_res.status_code == 200
        data = preview_res.json()
        assert data["title"] == "지방세특례제한법 제36조(서민주택 등에 대한 감면)"

@pytest.mark.asyncio
async def test_preview_not_found():
    """존재하지 않는 출처 → 404"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/preview/nonexistent_id")
        assert res.status_code == 404
```

### 4-5. 4단계 확인

```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v
```

전체 테스트 통과 확인.

그리고 서버를 실행하여 curl로 SSE 스트리밍 수동 테스트:
```bash
# 터미널 1: 서버 실행
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --port 8000

# 터미널 2: curl 테스트
SESSION=$(curl -s -X POST http://localhost:8000/api/auth/gpki \
  -H "Content-Type: application/json" \
  -d '{"cert_id":"cert_001","password":"test1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION\",\"question\":\"취득세 감면 대상\"}"
```

TODO.md 4단계 확인사항 모두 체크 후 결과 기록.

---

## ▶ 5단계 시작: 프론트엔드 연동 + 통합 테스트

4단계 확인이 모두 통과하면 5단계를 시작해.

### 5-1. 프론트엔드 MSW 비활성화 + Proxy 설정

**`frontend/src/main.jsx`** 수정:
```javascript
async function enableMocking() {
  // 환경변수 VITE_USE_MOCK가 'true'일 때만 MSW 활성화
  if (import.meta.env.DEV && import.meta.env.VITE_USE_MOCK === 'true') {
    const { worker } = await import('./mocks/browser')
    return worker.start({ onUnhandledRequest: 'bypass' })
  }
}
enableMocking().then(() => {
  // ReactDOM.createRoot(...).render(...)
})
```

**`frontend/vite.config.js`** 수정 — API 프록시 추가:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

이렇게 하면:
- `VITE_USE_MOCK=true npm run dev` → MSW Mock 모드 (Step 1 단독 테스트용)
- `npm run dev` (기본) → 백엔드 프록시 모드 (Step 2 연동)

### 5-2. 통합 실행

**터미널 1 (백엔드)**:
```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --port 8000 --reload
```

**터미널 2 (프론트엔드)**:
```bash
cd frontend
npm run dev
```

### 5-3. 시나리오 테스트

브라우저에서 http://localhost:5173 에 접속하여 아래 시나리오를 **순서대로** 수동 실행해:

1. **GPKI 로그인**: 인증서 선택 + "test1234" → 로그인 성공 → 채팅 활성화
2. **첫 질문**: "취득세 감면 대상" → 스테퍼 전환 + 스트리밍 답변 + 출처 카드
3. **출처 클릭**: 출처 카드 클릭 → 상세 내용 → "원문 바로가기"
4. **연속 질문**: "재산세 납부 기한" → 이전 대화 유지 + 새 답변 + 출처 1건
5. **미등록 질문**: "자동차세 환급" → "관련 자료를 찾지 못했습니다"
6. **로그아웃 + 재로그인**: 로그아웃 → 모달 → 재로그인 → 정상 동작

### 5-4. 프론트엔드 빌드 테스트

```bash
cd frontend && npm run build
```

에러 없이 완료 확인.

### 5-5. 전체 pytest 실행

```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v
```

모든 테스트 통과 확인.

### 5-6. 최종 확인

TODO.md 5단계 최종 확인사항을 **모두** 체크해. 하나라도 실패하면 수정 후 재테스트.
모든 항목이 `[x]`가 되면 **최종 TODO.md 내용을 출력**해.

---

## ⚠️ 중요 제약사항

1. **Mock 모드 우선**: 모든 구현은 `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true`에서 먼저 동작해야 함. 실제 OpenAI API나 olta.re.kr 접근은 이 Step에서 하지 않음.
2. **실제 모드 자리 확보**: 각 서비스에 `if settings.use_mock_*:` 분기와 함께, 실제 모드 코드 자리를 `# TODO` 주석으로 명확히 남겨둘 것.
3. **Step 3 확장 포인트**: chat.py의 SSE 파이프라인에 `# TODO Step 3: 여기에 2단계 검증 로직 추가 예정` 주석을 반드시 포함할 것.
4. **API 포맷 불변**: Step 1 프론트엔드와 동일한 API 엔드포인트, 요청/응답 포맷을 유지할 것. 포맷 변경 시 프론트엔드도 함께 수정해야 하므로 변경 금지.
5. **SSE 포맷 준수**: 모든 SSE 이벤트는 `event: {type}\ndata: {json}\n\n` 포맷을 정확히 따를 것.
6. **TODO.md 필수 업데이트**: 모든 작업 완료/실패를 TODO.md에 기록.
7. **단계 건너뛰기 금지**: 이전 단계의 모든 확인사항이 통과해야 다음 단계 진행.
8. **Python 비동기**: 모든 서비스 메서드는 `async def`로 작성. FastAPI의 비동기 패턴을 따를 것.
9. **보안**: 비밀번호는 사용 후 즉시 메모리에서 삭제. session_id는 UUID4. `.env` 파일은 `.gitignore`에 추가.
