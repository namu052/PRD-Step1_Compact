# PRD Step 1: 프론트엔드 UI + GPKI 로그인

> **문서 버전**: v1.0  
> **작성일**: 2026.03.28  
> **범위**: React 프론트엔드 전체 구현, GPKI 인증 플로우, 가상 데이터 기반 E2E 검증  
> **선행 조건**: 없음 (독립 실행 가능)  
> **산출물**: 로컬에서 실행 가능한 프론트엔드 APP + Mock Backend

---

## 1. 목표 (Objective)

Step 1의 목표는 **"AI 지방세 지식인 APP"의 전체 프론트엔드를 완성하고, 가상(Mock) 데이터로 모든 화면과 인터랙션이 정상 동작함을 검증**하는 것이다.

실제 LLM 호출이나 웹 크롤링 없이도, 사용자가 APP을 실행하고 GPKI 로그인 → 채팅 입력 → 답변 표시 → 출처 미리보기까지의 전체 흐름을 체험할 수 있어야 한다.

---

## 2. 기술 스택

| 구분 | 기술 | 비고 |
|------|------|------|
| Frontend | React 18 + Vite | SPA 구조 |
| 상태관리 | Zustand | 경량 상태관리 |
| 스타일링 | Tailwind CSS | 유틸리티 기반 |
| Markdown 렌더링 | react-markdown + remark-gfm | 답변 표시용 |
| Mock Server | MSW (Mock Service Worker) | 가상 API 응답 |
| 테스트 | Vitest + React Testing Library | 단위/통합 테스트 |
| E2E 테스트 | Playwright | 전체 플로우 검증 |

---

## 3. 디렉토리 구조

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.jsx          # 전체 레이아웃 (좌우 50:50 분할)
│   │   │   ├── TopBar.jsx            # 상단 바 (로그인 상태, 로그아웃)
│   │   │   └── StatusStepper.jsx     # 처리 단계 인디케이터
│   │   ├── auth/
│   │   │   ├── GpkiLoginModal.jsx    # GPKI 로그인 팝업
│   │   │   └── CertSelector.jsx      # 인증서 선택 UI
│   │   ├── chat/
│   │   │   ├── ChatPanel.jsx         # 왼쪽 채팅 패널 컨테이너
│   │   │   ├── ChatInput.jsx         # 질문 입력창
│   │   │   ├── ChatMessage.jsx       # 개별 메시지 (사용자/AI)
│   │   │   └── StreamingResponse.jsx # SSE 스트리밍 답변 표시
│   │   └── preview/
│   │       ├── PreviewPanel.jsx      # 오른쪽 미리보기 패널 컨테이너
│   │       ├── SourceCard.jsx        # 출처 카드 (클릭 가능)
│   │       └── SourceDetail.jsx      # 출처 상세 미리보기
│   ├── stores/
│   │   ├── authStore.js              # 인증 상태 관리
│   │   └── chatStore.js              # 채팅 상태 관리
│   ├── mocks/
│   │   ├── handlers.js               # MSW 핸들러 (Mock API)
│   │   ├── browser.js                # MSW 브라우저 설정
│   │   ├── data/
│   │   │   ├── mockCerts.json        # 가상 GPKI 인증서 목록
│   │   │   ├── mockChatResponses.json # 가상 채팅 응답 (2단계 포함)
│   │   │   └── mockSources.json      # 가상 출처 데이터
│   │   └── server.js                 # MSW Node 설정 (테스트용)
│   ├── hooks/
│   │   ├── useSSE.js                 # SSE 스트리밍 커스텀 훅
│   │   └── useAuth.js                # 인증 관련 커스텀 훅
│   ├── utils/
│   │   └── api.js                    # API 호출 유틸리티
│   ├── App.jsx
│   └── main.jsx
├── e2e/
│   ├── gpki-login.spec.js            # GPKI 로그인 E2E 테스트
│   ├── chat-flow.spec.js             # 채팅 플로우 E2E 테스트
│   └── preview-panel.spec.js         # 미리보기 패널 E2E 테스트
├── package.json
├── vite.config.js
├── tailwind.config.js
└── playwright.config.js
```

---

## 4. 화면 설계 상세

### 4.1 전체 레이아웃 (AppShell)

```
┌─────────────────────────────────────────────────────┐
│ [TopBar]  AI 지방세 지식인    홍길동님  [로그아웃]     │
├────────────────────────┬────────────────────────────┤
│                        │                            │
│   [ChatPanel]          │   [PreviewPanel]           │
│                        │                            │
│   사용자: 취득세 감면   │   📄 출처 1               │
│   대상은?              │   지방세법 제17조           │
│                        │   ─────────────────────    │
│   🤖 AI:              │   취득세의 과세표준은...    │
│   지방세법 제17조에     │                            │
│   따르면...            │   📄 출처 2               │
│                        │   지방세법 시행령 제35조    │
│   [상태: ✅ 완료]       │   ─────────────────────    │
│                        │   시행령에서 정하는...      │
│ ┌────────────────────┐ │                            │
│ │ 질문을 입력하세요... │ │   🔗 원문 바로가기        │
│ └────────────────────┘ │                            │
├────────────────────────┴────────────────────────────┤
│ [StatusStepper] ① 웹 검색 → ② 초안 작성 → ③ 검증 → ④ 완료 │
└─────────────────────────────────────────────────────┘
```

**레이아웃 규칙:**
- 전체 화면을 좌우 50:50으로 분할 (CSS `grid-cols-2` 또는 `flex basis-1/2`)
- 최소 너비 1024px, 반응형은 Phase 2에서 고려
- 하단 StatusStepper는 전체 너비를 사용

### 4.2 GPKI 로그인 모달 (GpkiLoginModal)

```
┌─────────────────────────────────────┐
│         행정전자서명 인증 로그인        │
│                                     │
│  인증서 저장 위치 선택:              │
│  ┌─────────────────────────────┐    │
│  │ ○ 하드디스크이동식            │    │
│  │ ○ 보안토큰                   │    │
│  └─────────────────────────────┘    │
│                                     │
│  사용할 인증서 선택:                 │
│  ┌─────────────────────────────┐    │
│  │ 📋 홍길동 (OO시 세무과)      │    │
│  │    유효기간: 2026.01~2027.01 │    │
│  │ 📋 김영희 (OO시 재무과)      │    │
│  │    유효기간: 2025.06~2026.06 │    │
│  └─────────────────────────────┘    │
│                                     │
│  인증서 비밀번호:                    │
│  ┌─────────────────────────────┐    │
│  │ ••••••••                    │    │
│  └─────────────────────────────┘    │
│                                     │
│       [ 취소 ]    [ 확인 ]           │
└─────────────────────────────────────┘
```

**동작 규칙:**
- APP 최초 실행 시 자동으로 모달이 표시됨
- 모달 외부 클릭으로 닫히지 않음 (필수 인증)
- '하드디스크이동식' 기본 선택 상태
- 인증서 목록은 Mock 데이터에서 로드
- 비밀번호 입력 후 '확인' 클릭 시 POST /api/auth/gpki 호출
- 인증 성공: 모달 닫힘 → 채팅창 활성화
- 인증 실패: 모달 내 에러 메시지 표시 ("비밀번호가 일치하지 않습니다")

### 4.3 채팅 패널 (ChatPanel)

**메시지 유형:**
- `user`: 사용자 질문 (오른쪽 정렬, 파란색 배경)
- `ai`: AI 답변 (왼쪽 정렬, 흰색 배경, Markdown 렌더링)
- `system`: 상태 메시지 ("웹에서 관련 자료를 검색하고 있습니다...")

**SSE 스트리밍 동작:**
- POST /api/chat 호출 시 SSE(Server-Sent Events) 연결
- 이벤트 타입별 처리:
  - `stage_change`: StatusStepper 업데이트 (예: "crawling" → "drafting" → "verifying" → "done")
  - `token`: 답변 텍스트 토큰 단위 스트리밍 표시
  - `sources`: 출처 목록 수신 → PreviewPanel에 표시
  - `error`: 에러 메시지 표시

**입력창 동작:**
- 로그인 전: 비활성화 (placeholder: "GPKI 인증 후 이용 가능합니다")
- 로그인 후: 활성화 (placeholder: "지방세 관련 질문을 입력하세요...")
- Enter 키 또는 전송 버튼으로 전송
- Shift+Enter로 줄바꿈
- 전송 중에는 입력창 비활성화 + 로딩 표시

### 4.4 미리보기 패널 (PreviewPanel)

**출처 카드 (SourceCard):**
- 제목 (예: "지방세법 제17조")
- 유형 배지 (법령 | 해석례 | 판례 | 훈령)
- 미리보기 텍스트 (2줄 요약)
- 클릭 시 SourceDetail 표시

**출처 상세 (SourceDetail):**
- 전체 텍스트 내용 표시
- "원문 바로가기" 버튼 → olta.re.kr 해당 페이지 새 탭으로 열기
- 닫기 버튼 → 카드 목록으로 복귀

**상태별 표시:**
- 채팅 전: "질문을 입력하면 관련 법령과 해석례가 여기에 표시됩니다" 안내 문구
- 검색 중: 스켈레톤 로딩 UI
- 결과 있음: 출처 카드 목록 표시
- 결과 없음: "관련 출처를 찾지 못했습니다" 안내 문구

### 4.5 상태 스테퍼 (StatusStepper)

4단계 진행 표시:

| 단계 | 라벨 | stage 값 | 아이콘 |
|------|------|----------|--------|
| 1 | 웹 검색 중 | crawling | 🔍 |
| 2 | 초안 작성 중 | drafting | ✏️ |
| 3 | 검증 중 | verifying | 🔎 |
| 4 | 답변 완료 | done | ✅ |

- 현재 단계: 파란색 강조 + 펄스 애니메이션
- 완료 단계: 초록색 체크 표시
- 미도달 단계: 회색 비활성

---

## 5. 상태 관리 설계

### 5.1 authStore (Zustand)

```javascript
{
  // State
  isLoggedIn: false,
  userName: null,
  sessionId: null,
  isLoggingIn: false,
  loginError: null,

  // Actions
  login(certPath, password) → Promise<void>   // POST /api/auth/gpki
  logout() → void                              // 상태 초기화
  clearError() → void
}
```

### 5.2 chatStore (Zustand)

```javascript
{
  // State
  messages: [],           // { id, role, content, timestamp, sources? }
  currentStage: null,     // 'crawling' | 'drafting' | 'verifying' | 'done' | null
  isStreaming: false,
  selectedSourceId: null, // 미리보기 패널에서 선택된 출처

  // Actions
  sendMessage(question) → void       // SSE 연결 + 스트리밍 처리
  selectSource(sourceId) → void      // 미리보기 패널 출처 선택
  clearChat() → void                 // 대화 초기화
}
```

---

## 6. Mock API 설계

### 6.1 Mock 데이터

#### mockCerts.json
```json
[
  {
    "id": "cert_001",
    "owner": "홍길동",
    "department": "OO시 세무과",
    "validFrom": "2026-01-15",
    "validTo": "2027-01-15",
    "serial": "GP2026-001234"
  },
  {
    "id": "cert_002",
    "owner": "김영희",
    "department": "OO시 재무과",
    "validFrom": "2025-06-01",
    "validTo": "2026-06-01",
    "serial": "GP2025-005678"
  }
]
```

#### mockChatResponses.json
```json
{
  "취득세 감면 대상": {
    "stages": [
      { "stage": "crawling", "delay": 1500 },
      { "stage": "drafting", "delay": 2000 },
      { "stage": "verifying", "delay": 1500 },
      { "stage": "done", "delay": 0 }
    ],
    "answer": "## 취득세 감면 대상\n\n**지방세특례제한법 제36조**에 따르면, 다음에 해당하는 경우 취득세를 감면받을 수 있습니다.\n\n### 1. 서민주택 취득세 감면\n- 취득가액 **1억원 이하**의 주택을 취득하는 경우\n- 감면율: 취득세의 **50% 경감**\n\n### 2. 농업법인 감면\n- 영농조합법인 또는 농업회사법인이 농업에 직접 사용하기 위하여 취득하는 부동산\n- 근거: 지방세특례제한법 제11조\n\n> ⚠️ **확인 필요**: 감면 적용 시 추징 요건(5년 내 매각 등)을 반드시 확인하시기 바랍니다.\n\n---\n📌 **출처**: 지방세특례제한법 제36조, 제11조",
    "sources": [
      {
        "id": "src_001",
        "title": "지방세특례제한법 제36조",
        "type": "법령",
        "preview": "서민주택에 대한 감면 규정으로, 취득가액 1억원 이하 주택에 대해...",
        "content": "제36조(서민주택 등에 대한 감면) ① 「주택법」 제2조제1호에 따른 주택으로서 대통령령으로 정하는 주택(이하 이 조에서 \"서민주택\"이라 한다)을 취득하는 경우에는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다.",
        "url": "https://www.olta.re.kr/law/detail?lawId=36"
      },
      {
        "id": "src_002",
        "title": "지방세특례제한법 제11조",
        "type": "법령",
        "preview": "농업법인이 농업에 직접 사용하기 위하여 취득하는 부동산에 대해...",
        "content": "제11조(농업법인에 대한 감면) ① 「농어업경영체 육성 및 지원에 관한 법률」 제16조에 따른 영농조합법인이 그 법인의 사업에 직접 사용하기 위하여 취득하는 부동산에 대해서는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다.",
        "url": "https://www.olta.re.kr/law/detail?lawId=11"
      }
    ]
  },
  "재산세 납부 기한": {
    "stages": [
      { "stage": "crawling", "delay": 1000 },
      { "stage": "drafting", "delay": 1500 },
      { "stage": "verifying", "delay": 1000 },
      { "stage": "done", "delay": 0 }
    ],
    "answer": "## 재산세 납부 기한\n\n**지방세법 제115조**에 따른 재산세 납부 기한은 다음과 같습니다.\n\n| 과세 대상 | 납부 기한 |\n|-----------|----------|\n| 주택 (1기분) | 매년 **7월 16일 ~ 7월 31일** |\n| 주택 (2기분) | 매년 **9월 16일 ~ 9월 30일** |\n| 건축물 | 매년 **7월 16일 ~ 7월 31일** |\n| 토지 | 매년 **9월 16일 ~ 9월 30일** |\n\n> 주택분 재산세의 세액이 **20만원 이하**인 경우 7월에 전액 부과합니다.\n\n---\n📌 **출처**: 지방세법 제115조",
    "sources": [
      {
        "id": "src_003",
        "title": "지방세법 제115조",
        "type": "법령",
        "preview": "재산세의 납기에 관한 규정으로, 주택·건축물·토지에 대한 납부 기한을...",
        "content": "제115조(납기) ① 재산세의 납기는 다음 각 호와 같다. 1. 제111조제1항제1호에 따른 토지: 매년 9월 16일부터 9월 30일까지 2. 제111조제1항제2호에 따른 건축물: 매년 7월 16일부터 7월 31일까지",
        "url": "https://www.olta.re.kr/law/detail?lawId=115"
      }
    ]
  }
}
```

### 6.2 MSW 핸들러 설계

```
POST /api/auth/gpki
  Request:  { cert_id: string, password: string }
  Response: { success: true, user_name: "홍길동", session_id: "sess_xxx" }
  실패 시:  { success: false, error: "비밀번호가 일치하지 않습니다" }
  Mock 규칙: password === "test1234" 이면 성공, 그 외 실패

POST /api/auth/logout
  Response: { success: true }

POST /api/chat
  Request:  { session_id: string, question: string }
  Response: SSE Stream
    - event: stage_change, data: { stage: "crawling" }
    - event: stage_change, data: { stage: "drafting" }
    - event: token, data: { content: "지방세법..." }  (글자 단위 스트리밍)
    - event: stage_change, data: { stage: "verifying" }
    - event: token, data: { content: "...(검증 완료)..." }
    - event: sources, data: { sources: [...] }
    - event: stage_change, data: { stage: "done" }
  Mock 규칙: question에 키워드 매칭하여 mockChatResponses에서 선택
             매칭 없으면 기본 응답("해당 질문에 대한 정보를 찾지 못했습니다")

GET /api/preview/:sourceId
  Response: { title, content, url, type }
  Mock 규칙: mockSources에서 sourceId로 조회
```

---

## 7. GPKI 로그인 구현 상세

### 7.1 프론트엔드 로그인 플로우

```
[APP 실행]
    │
    ▼
[GpkiLoginModal 표시]
    │
    ├─ GET /api/auth/certs → 인증서 목록 로드
    │
    ▼
[사용자: 인증서 선택 + 비밀번호 입력 + 확인 클릭]
    │
    ├─ POST /api/auth/gpki { cert_id, password }
    │
    ├─ 성공 → authStore.login() → 모달 닫기 → 채팅 활성화
    │
    └─ 실패 → 에러 메시지 표시 → 재입력 유도
```

### 7.2 세션 관리

- 로그인 성공 시 session_id를 authStore에 저장
- 모든 API 요청에 session_id를 헤더(X-Session-Id)로 포함
- 로그아웃 시: authStore 초기화 + chatStore 초기화 + GpkiLoginModal 재표시
- 탭 닫기(beforeunload) 시: POST /api/auth/logout 호출

### 7.3 보안 규칙

- 비밀번호는 입력 후 API 전송 즉시 프론트엔드 메모리에서 삭제
- session_id는 localStorage/cookie에 저장하지 않음 (Zustand 메모리 전용)
- 브라우저 새로고침 시 세션 만료 → 재로그인 필요

---

## 8. SSE 스트리밍 구현 상세

### 8.1 useSSE 커스텀 훅

```javascript
// 인터페이스
useSSE({
  url: '/api/chat',
  body: { session_id, question },
  onStageChange: (stage) => void,
  onToken: (token) => void,
  onSources: (sources) => void,
  onError: (error) => void,
  onDone: () => void
})
```

### 8.2 SSE 이벤트 포맷

```
event: stage_change
data: {"stage":"crawling"}

event: token
data: {"content":"지"}

event: token
data: {"content":"방"}

event: sources
data: {"sources":[{"id":"src_001","title":"지방세법 제17조",...}]}

event: stage_change
data: {"stage":"done"}
```

### 8.3 Mock SSE 구현

MSW에서 직접 SSE를 지원하지 않으므로, Mock 모드에서는 다음과 같이 처리한다:
- POST /api/chat 호출 시 ReadableStream을 반환
- mockChatResponses의 stages 배열에 정의된 delay에 따라 이벤트 순차 전송
- answer 텍스트를 글자 단위로 분할하여 token 이벤트로 전송 (30ms 간격)

---

## 9. 검증 체크리스트

### 9.1 단위 테스트 (Vitest)

| ID | 테스트 대상 | 검증 내용 |
|----|------------|----------|
| UT-01 | GpkiLoginModal | 모달이 초기 실행 시 자동 표시되는가 |
| UT-02 | GpkiLoginModal | 인증서 목록이 정상 로드되는가 |
| UT-03 | GpkiLoginModal | 올바른 비밀번호 입력 시 로그인 성공하는가 |
| UT-04 | GpkiLoginModal | 잘못된 비밀번호 입력 시 에러 메시지가 표시되는가 |
| UT-05 | GpkiLoginModal | 모달 외부 클릭 시 닫히지 않는가 |
| UT-06 | ChatInput | 로그인 전 입력창이 비활성화되는가 |
| UT-07 | ChatInput | 로그인 후 입력창이 활성화되는가 |
| UT-08 | ChatInput | Enter 키로 메시지 전송되는가 |
| UT-09 | ChatInput | Shift+Enter로 줄바꿈되는가 |
| UT-10 | ChatInput | 전송 중 입력창이 비활성화되는가 |
| UT-11 | ChatMessage | 사용자 메시지가 오른쪽 정렬로 표시되는가 |
| UT-12 | ChatMessage | AI 메시지가 Markdown으로 렌더링되는가 |
| UT-13 | StatusStepper | 각 단계별 상태 전환이 정상 표시되는가 |
| UT-14 | SourceCard | 출처 카드 클릭 시 상세 내용이 표시되는가 |
| UT-15 | SourceDetail | "원문 바로가기" 클릭 시 새 탭으로 URL이 열리는가 |
| UT-16 | authStore | login 성공 시 isLoggedIn=true, userName 설정되는가 |
| UT-17 | authStore | logout 시 모든 상태가 초기화되는가 |
| UT-18 | chatStore | sendMessage 시 messages에 사용자 메시지가 추가되는가 |

### 9.2 E2E 테스트 (Playwright)

| ID | 시나리오 | 검증 내용 |
|----|---------|----------|
| E2E-01 | GPKI 정상 로그인 | APP 실행 → 인증서 선택 → 비밀번호 입력 → 확인 → 채팅창 활성화 |
| E2E-02 | GPKI 로그인 실패 | 잘못된 비밀번호 → 에러 메시지 → 재입력 가능 |
| E2E-03 | 채팅 전체 플로우 | 질문 입력 → 스테퍼 단계별 전환 → 답변 스트리밍 표시 → 출처 카드 표시 |
| E2E-04 | 출처 미리보기 | 출처 카드 클릭 → 상세 내용 표시 → 원문 바로가기 링크 확인 |
| E2E-05 | 로그아웃 | 로그아웃 클릭 → 채팅 초기화 → GPKI 모달 재표시 |
| E2E-06 | 연속 질문 | 첫 질문 완료 → 두 번째 질문 → 이전 대화 유지 + 새 답변 표시 |
| E2E-07 | 미등록 질문 | 매칭되지 않는 질문 → 기본 안내 메시지 표시 |

### 9.3 수동 검증 체크리스트

- [ ] APP 실행 시 GPKI 모달이 자동으로 뜨는가?
- [ ] 인증서 목록이 2개 이상 표시되는가?
- [ ] 비밀번호 "test1234" 입력 시 로그인 성공하는가?
- [ ] 로그인 후 상단 바에 사용자 이름이 표시되는가?
- [ ] "취득세 감면 대상"을 입력하면 Mock 답변이 스트리밍으로 표시되는가?
- [ ] 스테퍼가 웹 검색 → 초안 작성 → 검증 → 완료 순서로 전환되는가?
- [ ] 오른쪽 패널에 출처 카드가 표시되는가?
- [ ] 출처 카드 클릭 시 상세 내용이 표시되는가?
- [ ] 로그아웃 버튼 클릭 시 모달이 다시 뜨는가?

---

## 10. Step 2 연결 포인트

Step 1 완료 시, Step 2로의 전환을 위해 다음 인터페이스가 확정되어야 한다:

| 항목 | Step 1 (Mock) | Step 2 (실제) |
|------|--------------|--------------|
| POST /api/auth/gpki | MSW Mock 응답 | FastAPI → Playwright GPKI 실제 인증 |
| POST /api/chat | MSW Mock SSE | FastAPI → Playwright 크롤링 → GPT-4o 호출 |
| GET /api/preview/:id | MSW Mock 데이터 | FastAPI → 크롤링 결과 캐시에서 조회 |

**핵심 원칙**: Step 1의 프론트엔드 코드는 Step 2에서 **수정 없이** 그대로 사용된다. API 엔드포인트와 요청/응답 포맷이 동일하므로, MSW를 제거하고 실제 FastAPI 서버로 연결만 변경하면 된다.

---

## 11. 실행 방법

```bash
# 의존성 설치
cd frontend && npm install

# 개발 서버 실행 (Mock 모드)
npm run dev

# 단위 테스트
npm run test

# E2E 테스트
npm run test:e2e

# 빌드
npm run build
```

---

> **다음 단계**: Step 1 완료 후, PRD_step2.md에 따라 FastAPI 백엔드 + Playwright 크롤링 엔진을 구현한다.
