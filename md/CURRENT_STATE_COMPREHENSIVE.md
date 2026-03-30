# AI 지방세 지식인 APP - 현재 구현 상태 종합 문서

> **작성일**: 2026.03.30
> **기준**: Codex CLI로 구현된 최종 코드 상태
> **원본 PRD**: `PRD/PRD_step1.md`, `md/CLAUDE_CODE_STEP1_PROMPT.md`, `md/CLAUDE_CODE_STEP1_PROMPT_v2.md`
> **목적**: 원본 PRD 대비 변경된 현재 구현 상태를 정확히 기록하여, 이후 개발/유지보수의 기준 문서로 사용

---

## 1. 프로젝트 개요

"AI 지방세 지식인 APP"은 공무원이 지방세 관련 질문을 입력하면, OLTA(지방세 법령 포털) 크롤링 + LLM 기반으로 근거 있는 답변을 제공하는 웹 애플리케이션이다.

**현재 구현 범위**: PRD Step 1(프론트엔드 + Mock)을 넘어 Step 2~3 범위(백엔드 파이프라인, 크롤링, 검증 엔진)까지 구현되어 있다.

---

## 2. 기술 스택 (실제)

| 구분 | 기술 | 버전 | 비고 |
|------|------|------|------|
| Frontend | React + Vite | React 19, Vite 8 | PRD는 React 18 + Vite 명시 |
| 상태관리 | Zustand | 5.x | |
| 스타일링 | Tailwind CSS | 4.x (Vite 플러그인 방식) | `@tailwindcss/vite` 사용, config 파일 불필요 |
| Markdown 렌더링 | react-markdown + remark-gfm | 10.x / 4.x | |
| Mock Server | MSW (Mock Service Worker) | 2.x | 조건부 활성화 (`VITE_USE_MOCK=true`) |
| Backend | FastAPI + Uvicorn | 0.115 / 0.30 | |
| LLM | OpenAI API | 1.50 | GPT-4o-mini 기본 |
| 크롤러 | Playwright | 1.47 | OLTA 사이트 크롤링 |
| 임베딩/검색 | FAISS + OpenAI embedding | faiss-cpu 1.8 | text-embedding-3-small |
| 테스트 (backend) | pytest + pytest-asyncio | 8.3 / 0.24 | |
| 테스트 (frontend) | **미설치** | - | Vitest, RTL, Playwright 모두 없음 |

---

## 3. 디렉토리 구조 (실제)

```
PRD-Step1/
├── AGENTS.md                          # Codex CLI용 프로젝트 가이드라인
├── .gitignore
├── PRD/
│   ├── PRD_step1.md                   # 원본 Step 1 PRD
│   ├── PRD_step2.md                   # Step 2 PRD
│   └── PRD_step3.md                   # Step 3 PRD
├── md/
│   ├── CLAUDE_CODE_STEP1_PROMPT.md    # Claude Code용 프롬프트 v1
│   ├── CLAUDE_CODE_STEP1_PROMPT_v2.md # Claude Code용 프롬프트 v2 (실제 GPKI)
│   ├── CLAUDE_CODE_STEP2_PROMPT.md    # Step 2 프롬프트
│   └── CLAUDE_CODE_STEP3_PROMPT.md    # Step 3 프롬프트
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js                 # gpkiPlugin 포함 (실제 GPKI 인증서 파싱)
│   ├── eslint.config.js
│   ├── TODO.md                        # 작업 진행 기록
│   ├── README.md
│   ├── public/
│   │   ├── favicon.svg
│   │   ├── icons.svg
│   │   └── mockServiceWorker.js       # MSW 서비스워커
│   └── src/
│       ├── main.jsx                   # MSW 조건부 초기화
│       ├── App.jsx                    # OLTA 자동 열기 + bootstrapSession
│       ├── index.css                  # Tailwind v4 import
│       ├── assets/
│       │   ├── hero.png
│       │   ├── react.svg
│       │   └── vite.svg
│       ├── components/
│       │   ├── auth/
│       │   │   ├── GpkiLoginModal.jsx # GPKI 로그인 팝업 (현재 미사용)
│       │   │   └── CertSelector.jsx   # 인증서 선택 UI
│       │   ├── chat/
│       │   │   ├── ChatPanel.jsx      # 채팅 패널 컨테이너
│       │   │   ├── ChatInput.jsx      # 질문 입력창
│       │   │   ├── ChatMessage.jsx    # 개별 메시지
│       │   │   ├── StreamingResponse.jsx  # Markdown 스트리밍 렌더링
│       │   │   └── ConfidenceBadge.jsx    # 답변 신뢰도 배지 (PRD 추가분)
│       │   ├── layout/
│       │   │   ├── AppShell.jsx       # 전체 레이아웃 (좌우 50:50)
│       │   │   ├── TopBar.jsx         # 상단 바
│       │   │   └── StatusStepper.jsx  # 처리 단계 인디케이터 (5단계)
│       │   └── preview/
│       │       ├── PreviewPanel.jsx   # 출처 미리보기 패널
│       │       ├── SourceCard.jsx     # 출처 카드
│       │       └── SourceDetail.jsx   # 출처 상세 보기
│       ├── hooks/
│       │   └── useSSE.js             # SSE 스트리밍 커스텀 훅
│       ├── mocks/
│       │   ├── browser.js            # MSW 브라우저 설정
│       │   ├── handlers.js           # MSW 핸들러 (chat, preview, logout)
│       │   └── data/
│       │       ├── mockChatResponses.json  # Mock 채팅 응답 2건
│       │       └── mockSources.json        # Mock 출처 3건
│       └── stores/
│           ├── authStore.js           # 인증 상태 (자동 부트스트랩 방식)
│           └── chatStore.js           # 채팅 상태
└── backend/
    ├── requirements.txt
    ├── pytest.ini
    ├── .env.example
    ├── app/
    │   ├── main.py                    # FastAPI 앱 진입점
    │   ├── config.py                  # 설정 (pydantic-settings)
    │   ├── core/
    │   │   ├── event_emitter.py       # SSE 이벤트 헬퍼
    │   │   ├── security.py            # 비밀번호 메모리 와이프
    │   │   └── session_manager.py     # 세션 관리 (인메모리)
    │   ├── models/
    │   │   ├── schemas.py             # Pydantic 스키마
    │   │   ├── session.py             # 세션 모델
    │   │   ├── evidence.py            # 근거 슬롯 모델
    │   │   └── verification.py        # 검증 결과 모델
    │   ├── prompts/                   # LLM 프롬프트 템플릿
    │   │   ├── stage1_prompt.py
    │   │   ├── stage2_content_prompt.py
    │   │   ├── stage2_source_prompt.py
    │   │   ├── stage2_final_prompt.py
    │   │   ├── evidence_summary_prompt.py
    │   │   ├── grouped_answer_prompt.py
    │   │   └── grouped_verification_prompt.py
    │   ├── routers/
    │   │   ├── auth.py                # 인증 API (certs, gpki, logout)
    │   │   └── chat.py                # 채팅 API (SSE 스트리밍 + 전체 파이프라인)
    │   └── services/
    │       ├── gpki_service.py        # GPKI Mock 인증 서비스
    │       ├── crawler_service.py     # OLTA Playwright 크롤러
    │       ├── search_service.py      # 검색 계획 수립 (LLM 기반)
    │       ├── embedding_service.py   # FAISS 임베딩 + 순위화
    │       ├── evidence_group_service.py    # 근거 그룹핑
    │       ├── evidence_summary_service.py  # 근거 요약
    │       ├── llm_service.py         # 초안 생성/수정 서비스
    │       ├── openai_service.py      # OpenAI API 래퍼
    │       └── verification/          # 검증 엔진
    │           ├── source_verifier.py
    │           ├── content_verifier.py
    │           ├── grouped_answer_verifier.py
    │           ├── final_generator.py
    │           └── verification_aggregator.py
    └── tests/
        ├── conftest.py
        ├── test_aggregator.py
        ├── test_chat_pipeline.py
        ├── test_content_verifier.py
        ├── test_crawler.py
        └── mocks/
            ├── mock_crawler.py
            ├── mock_drafts.py
            ├── mock_llm.py
            └── mock_olta_pages.json
```

---

## 4. 프론트엔드 상세

### 4.1 전체 레이아웃 (AppShell)

```
┌─────────────────────────────────────────────────────┐
│ [TopBar]  🏛️ AI 지방세 지식인    OLTA 열기 링크     │
├────────────────────────┬────────────────────────────┤
│                        │                            │
│   [ChatPanel]          │   [PreviewPanel]           │
│   좌측 50%             │   우측 50%                 │
│                        │                            │
├────────────────────────┴────────────────────────────┤
│ [StatusStepper] 🔍웹검색 → ✏️초안 → 🔎검증 → 🧩정리 → ✅완료 │
└─────────────────────────────────────────────────────┘
```

- CSS: `grid-cols-2`, 전체 `h-screen flex flex-col`
- TopBar: 앱 이름 + OLTA 링크 (사용자명/로그아웃 버튼 없음)
- StatusStepper: **5단계** (crawling → drafting → verifying → finalizing → done)

### 4.2 인증 플로우 (현재 동작)

```
[APP 실행 (App.jsx)]
    │
    ├── sessionStorage 확인 (OLTA 열기 중복 방지)
    │
    ├── window.open('https://www.olta.re.kr') → OLTA 새 탭에서 열기
    │
    └── bootstrapSession() 자동 호출
        │
        ├── [Mock 모드] POST /api/auth/gpki { cert_id: 'cert_001', password: 'test1234' }
        │   → Vite gpkiPlugin이 실제 GPKI 인증서로 검증
        │
        ├── [실제 백엔드 모드] POST /api/auth/gpki → FastAPI gpki_service
        │
        ├── 성공 → sessionId 저장 → 채팅 활성화
        │
        └── 실패 → loginError 표시 (ChatInput 하단)
```

**주요 변경점**: GPKI 로그인 모달 없이 자동 인증 처리. `GpkiLoginModal.jsx`와 `CertSelector.jsx`는 코드로 존재하지만 `App.jsx`에서 렌더링하지 않음.

### 4.3 채팅 패널

**메시지 유형:**
- `user`: 오른쪽 정렬, 파란색 배경 (`bg-blue-500`), 둥근 모서리
- `ai`: 왼쪽 정렬, 흰색 배경 + 테두리, Markdown 렌더링 + **신뢰도 배지**
- `system`: 가운데 정렬, 회색 이탤릭 (공지/알림용)

**입력창 동작:**
- 세션 초기화 중: "세션 준비 중..." (비활성)
- 스트리밍 중: "답변 생성 중..." (비활성)
- 정상: "지방세 관련 질문을 입력하세요..." (활성)
- Enter로 전송, Shift+Enter로 줄바꿈
- 텍스트에어리어 자동 높이 조절 (최대 120px)

### 4.4 SSE 스트리밍 프로토콜

**이벤트 타입:**

| 이벤트 | 데이터 | 설명 |
|--------|--------|------|
| `stage_change` | `{ stage: "crawling" \| "drafting" \| "verifying" \| "finalizing" \| "done" }` | 처리 단계 변경 |
| `token` | `{ token: "텍스트..." }` | 답변 토큰 스트리밍 |
| `notice` | `{ message: "안내 메시지" }` | 시스템 알림 (처리 과정 안내) |
| `sources` | `{ sources: [...], confidence: { score, label } }` | 출처 + 신뢰도 |
| `done` | `{ stage: "done" }` | 스트리밍 종료 |

**주의사항:**
- `token` 이벤트의 필드명은 `token` (PRD의 `content`가 아님)
- `error` 이벤트 핸들러 없음 (네트워크 에러는 catch에서 일괄 처리)
- `finalizing` 단계 진입 시 AI 메시지 내용이 초기화됨 (최종 답변으로 교체)

### 4.5 미리보기 패널

**상태별 표시:**
- 채팅 전: "질문을 입력하면 관련 법령과 해석례가 여기에 표시됩니다"
- 스트리밍 중 + 출처 없음: 스켈레톤 로딩 (3개 블록)
- 출처 있음: SourceCard 목록
- 결과 없음: "관련 출처를 찾지 못했습니다"

**SourceCard 유형 배지 색상:**
- 법령: 파랑 (`bg-blue-100 text-blue-700`)
- 해석례: 초록 (`bg-green-100 text-green-700`)
- 판례: 보라 (`bg-purple-100 text-purple-700`)
- 훈령: 주황 (`bg-orange-100 text-orange-700`)
- 처리 요약: 앰버 (`bg-amber-100 text-amber-700`) — 백엔드 추가
- 근거 묶음: 틸 (`bg-teal-100 text-teal-700`) — 백엔드 추가

**SourceDetail:**
- "← 목록으로" 뒤로가기 버튼
- 제목 + 전체 내용 (pre-wrap)
- "원문 바로가기" 버튼 → 새 탭에서 URL 열기
- `/api/preview/:sourceId?session_id=xxx`로 상세 데이터 별도 로드

### 4.6 ConfidenceBadge (PRD에 없는 추가 기능)

AI 답변 하단에 신뢰도 배지를 표시:
- 높음 (🟢): 녹색 배경
- 보통 (🟡): 노란색 배경 + "일부 내용은 원문 확인 권장"
- 낮음 (🔴): 빨간색 배경 + "실무 적용 전 반드시 원문 확인"

---

## 5. 상태 관리 설계 (실제)

### 5.1 authStore (Zustand)

```javascript
{
  // State
  isLoggedIn: true,          // 항상 true (모달 비활성화)
  userName: '홍길동',         // 기본값 하드코딩
  sessionId: null,            // bootstrapSession 성공 시 설정
  isInitializing: false,      // 세션 초기화 중 여부
  loginError: null,           // 에러 메시지

  // Actions
  bootstrapSession() → Promise<void>  // 자동 로그인 (cert_001, test1234)
  logout() → Promise<void>            // POST /api/auth/logout + 상태 리셋
}
```

**PRD 대비 변경:**
- `isLoggingIn` → `isInitializing`
- `login(certPath, password)` → `bootstrapSession()` (자동)
- `clearError()` → login 시 자동 초기화
- `isLoggedIn`이 항상 `true`이므로 GpkiLoginModal 표시 조건이 작동하지 않음

### 5.2 chatStore (Zustand)

```javascript
{
  // State
  messages: [],               // { id, role, content, timestamp, confidence?, sources? }
  currentStage: null,         // 'crawling'|'drafting'|'verifying'|'finalizing'|'done'|null
  isStreaming: false,
  activeMessageId: null,      // 현재 스트리밍 중인 AI 메시지 ID
  selectedSourceId: null,     // 미리보기 패널에서 선택된 출처
  currentSources: [],         // 현재 출처 목록
  currentConfidence: null,    // 현재 신뢰도 정보
  hasAskedQuestion: false,    // 질문 1회 이상 여부

  // Actions
  beginStream(question) → messageId  // 스트리밍 시작 (user+ai 메시지 추가)
  appendToken(messageId, token)      // 토큰 추가
  addSystemMessage(content)          // 시스템 메시지 추가
  setStage(stage)                    // 단계 변경 (finalizing 시 content 초기화)
  setSources({ sources, confidence }) // 출처 + 신뢰도 설정
  finishStream()                     // 스트리밍 완료
  failStream(messageId, errorMsg)    // 스트리밍 실패 처리
  selectSource(sourceId)             // 출처 선택/해제
  clearChat()                        // 전체 초기화
}
```

---

## 6. API 인터페이스 (실제)

### 6.1 인증 API

```
GET /api/auth/certs
  Response: [{ id, owner, cn, department, validFrom, validTo, serial }]
  구현: [Mock] Vite gpkiPlugin (openssl로 실제 인증서 파싱)
       [실제] FastAPI gpki_service (Mock 데이터 2건)

POST /api/auth/gpki
  Request:  { cert_id: string, password: string }
  Response: { success: true, user_name, session_id, cert_cn? }
  실패:     { success: false, error: "비밀번호가 일치하지 않습니다" }
  구현: [Mock] Vite gpkiPlugin (openssl pkcs8으로 실제 검증)
       [실제] FastAPI gpki_service (password === "test1234" 체크)

POST /api/auth/logout
  Request:  { session_id: string }
  Response: { success: true }
```

### 6.2 채팅 API

```
POST /api/chat
  Request:  { session_id: string, question: string }
  Response: SSE Stream
    - event: stage_change    data: { stage: "crawling" }
    - event: notice          data: { message: "검색 계획 안내..." }
    - event: stage_change    data: { stage: "drafting" }
    - event: token           data: { token: "답변텍스트..." }
    - event: notice          data: { message: "초안 완료 안내" }
    - event: stage_change    data: { stage: "verifying" }
    - event: notice          data: { message: "검증 결과 안내" }
    - event: stage_change    data: { stage: "finalizing" }
    - event: token           data: { token: "최종답변..." }
    - event: sources         data: { sources: [...], confidence: { score, label } }
    - event: stage_change    data: { stage: "done" }

GET /api/preview/:sourceId?session_id=xxx
  Response: { id, title, type, content, url, crawled_at? }
  404:      { error: "출처를 찾을 수 없습니다" }
```

### 6.3 Mock 모드 vs 실제 모드

| 모드 | 활성화 조건 | 인증 처리 | 채팅 처리 | 출처 조회 |
|------|------------|----------|----------|----------|
| Mock (MSW + Vite Plugin) | `VITE_USE_MOCK=true` | Vite 미들웨어 (실제 GPKI 인증서) | MSW (mockChatResponses.json) | MSW (mockSources.json) |
| 실제 (FastAPI) | `VITE_USE_MOCK` 미설정 | FastAPI → gpki_service | FastAPI → 크롤링+LLM 파이프라인 | FastAPI → 세션 crawl_cache |

프론트엔드의 Vite 프록시: `/api` → `http://127.0.0.1:8000` (Mock 모드가 아닐 때)

---

## 7. 백엔드 파이프라인 (실제)

```
[질문 입력]
    │
    ▼
[Stage 1: crawling]
    ├── search_service: 질문 분석 → 키워드 추출 + 검색 계획 수립 (LLM)
    ├── crawler_service: OLTA 크롤링 (Playwright)
    ├── embedding_service: FAISS 임베딩 → 관련도 순위화
    ├── evidence_group_service: 근거 그룹핑 (LLM)
    └── evidence_summary_service: 근거 요약 (LLM)
    │
    ▼
[Stage 2: drafting]
    └── llm_service.generate_draft: 근거 기반 초안 생성 (토큰 스트리밍)
    │
    ▼
[Stage 3: verifying] (최대 N회 루프)
    ├── source_verifier: 출처 정확성 검증
    ├── content_verifier: 내용 정합성 검증
    ├── grouped_answer_verifier: 근거 묶음 기반 검증
    ├── verification_aggregator: 검증 결과 통합 → 신뢰도 산출
    └── (신뢰도 < 목표) → llm_service.revise_draft → 재검증
    │
    ▼
[Stage 4: finalizing] (최대 N회 루프)
    ├── final_generator: 최종 답변 정리
    ├── 재검증 → 신뢰도 재산출
    └── verified_sources 구성
    │
    ▼
[Stage 5: done]
    └── sources + confidence 전송
```

**설정 (config.py):**
- `openai_model`: gpt-4o-mini (초안)
- `openai_verification_model`: gpt-4o-mini (검증)
- `openai_final_model`: gpt-4o-mini (최종)
- `verification_target_confidence`: 0.8 (80%)
- `max_verification_rounds`: 5
- `answer_context_top_k`: 48
- `olta_max_results_per_query`: 8
- `olta_max_detail_fetch`: 96

---

## 8. Mock 데이터 (실제)

### mockChatResponses.json
- `"취득세 감면"` 키워드 매칭 → 취득세 감면 답변 + 출처 2건
- `"재산세 납부"` 키워드 매칭 → 재산세 납부 기한 답변 + 출처 1건
- 매칭 없음 → "해당 질문에 대한 정보를 찾지 못했습니다" 기본 응답

### mockSources.json
- `src_001`: 지방세특례제한법 제36조 (법령)
- `src_002`: 지방세특례제한법 제11조 (법령)
- `src_003`: 지방세법 제115조 (법령)

### backend gpki_service.py (Mock 인증서)
- `cert_001`: 홍길동 / OO시 세무과
- `cert_002`: 김영희 / OO시 재무과
- 비밀번호: `test1234`

---

## 9. 원본 PRD 대비 주요 변경 요약

### 9.1 설계 변경

| 항목 | PRD 원본 | 현재 구현 | 변경 사유 |
|------|---------|----------|----------|
| GPKI 인증 | Mock 데이터 (mockCerts.json) | Vite 플러그인으로 실제 GPKI 인증서 파싱 (openssl) | v2 프롬프트에서 실제 인증서 사용으로 변경 |
| 로그인 UI | GpkiLoginModal 수동 조작 | bootstrapSession 자동 인증 | 개발 편의 + OLTA 연동 |
| TopBar | 사용자명 + 로그아웃 버튼 | OLTA 링크만 표시 | 자동 인증 방식에 맞춤 |
| StatusStepper | 4단계 (crawling→drafting→verifying→done) | 5단계 (+finalizing) | 백엔드 최종 정리 단계 반영 |
| SSE token 필드 | `{ content: "..." }` | `{ token: "..." }` | 백엔드 구현에 맞춤 |
| 세션 전달 | X-Session-Id 헤더 | 쿼리 파라미터 (`?session_id=xxx`) | 구현 편의 |
| MSW 활성화 | 개발 모드 자동 | `VITE_USE_MOCK=true` 환경변수 필요 | 실제 백엔드 모드와 분리 |
| React 버전 | 18 | 19 | Vite 8과 호환 |

### 9.2 PRD에 없는 추가 구현

| 항목 | 설명 |
|------|------|
| ConfidenceBadge | AI 답변 신뢰도 배지 (높음/보통/낮음) |
| notice 이벤트 | SSE 처리 과정 안내 메시지 |
| OLTA 자동 열기 | APP 최초 로드 시 OLTA 사이트 자동 오픈 |
| 전체 백엔드 | FastAPI + 크롤링 + LLM + 검증 파이프라인 |
| 처리 요약 출처 카드 | 검색 요약, 검증 요약 출처 카드 |
| 근거 묶음 출처 카드 | evidence_group 기반 묶음 카드 |

### 9.3 PRD 대비 누락/미구현

| 항목 | PRD 요구 | 현재 상태 |
|------|---------|----------|
| 단위 테스트 (Vitest + RTL) | 18개 테스트 케이스 명세 | 미설치, 미구현 |
| E2E 테스트 (Playwright) | 7개 시나리오 명세 | 미설치, 미구현 |
| useAuth.js 훅 | 인증 관련 커스텀 훅 | 미구현 (authStore 직접 사용) |
| utils/api.js | API 호출 유틸리티 | 미구현 (fetch 직접 사용) |
| mocks/server.js | MSW Node 설정 | 미구현 |
| 로그아웃 UI 버튼 | TopBar에 로그아웃 버튼 | 없음 |
| 사용자명 TopBar 표시 | "{이름}님" 표시 | 없음 |
| GpkiLoginModal 실사용 | 모달을 통한 수동 인증 | 컴포넌트 존재하나 미렌더링 |
| 취소 버튼 | 로그인 모달 취소 버튼 | GpkiLoginModal에 취소 버튼 없음 |
| mockCerts.json | Mock 인증서 데이터 파일 | 파일 없음 (Vite 플러그인 대체) |

---

## 10. 실행 방법

### 프론트엔드 (Mock 모드)
```bash
cd frontend
npm install

# Mock 모드 (MSW 사용, 백엔드 불필요)
VITE_USE_MOCK=true npm run dev

# 실제 백엔드 연동 모드
npm run dev
# → /api 요청이 http://127.0.0.1:8000으로 프록시됨
```

### 백엔드
```bash
cd backend
pip install -r requirements.txt

# .env 설정 필요
cp .env.example .env
# OPENAI_API_KEY, USE_MOCK_CRAWLER, USE_MOCK_LLM 등 설정

# 서버 실행
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 빌드
```bash
cd frontend
npm run build   # → dist/ 생성
npm run lint    # ESLint 검사
```

### 백엔드 테스트
```bash
cd backend
pytest
```

---

## 11. 알려진 이슈 및 주의사항

1. **authStore 초기값**: `isLoggedIn: true` 하드코딩으로 GPKI 모달이 동작하지 않음. 수동 인증 플로우를 복원하려면 `isLoggedIn: false`로 변경하고 App.jsx에서 GpkiLoginModal 렌더링 필요.

2. **GPKI 인증서 경로**: Vite gpkiPlugin은 `~/GPKI/Certificate/class2` 경로를 하드코딩. 해당 경로에 인증서가 없으면 Mock 모드에서도 `/api/auth/certs` 500 에러 발생.

3. **Windows 호환**: vite.config.js의 `verifyPrivateKey`에서 `/dev/null` 사용 → Windows에서는 `NUL`로 변경 필요할 수 있음.

4. **프론트엔드 테스트 부재**: Vitest, RTL, Playwright 모두 미설치. 자동화된 테스트가 없음.

5. **SourceDetail의 to_source_detail**: 백엔드 스키마(`SourceDetail`)에는 `crawled_at`이 Optional이나 `document_year` 필드를 반환하는데, 프론트엔드 SourceDetail 스키마에 `document_year`가 없음.

6. **session_manager 패스워드 전달**: `create_session(cert_id, password)`에서 password를 받지만 사용하지 않음 (Mock에서는 user_name만 cert_id로 조회).

---

## 12. Step 2 연결 포인트

Step 1 프론트엔드는 API 인터페이스가 동일하므로, **MSW를 비활성화하고 실제 FastAPI 서버로 연결만 변경**하면 된다.

현재 이미 FastAPI 백엔드가 구현되어 있으므로:
1. `VITE_USE_MOCK` 환경변수를 제거하거나 `false`로 설정
2. FastAPI 서버 실행 (`uvicorn app.main:app`)
3. `.env`에 `OPENAI_API_KEY` 설정
4. OLTA 크롤링을 위한 Playwright 브라우저 설치 (`playwright install chromium`)

실질적으로 Step 2~3의 백엔드 코드가 이미 존재하므로, 환경 설정만 완료하면 전체 파이프라인이 동작한다.
