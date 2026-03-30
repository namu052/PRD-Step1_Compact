# AI 지방세 지식인 APP - 수정/추가 작업 계획서

> **작성일**: 2026.03.30
> **기준 문서**: `md/CURRENT_STATE_COMPREHENSIVE.md`
> **용도**: 이 문서를 Claude Code 또는 Codex CLI에 전달하여 수정 작업을 수행
> **원칙**: 기존 동작을 깨뜨리지 않으면서 점진적으로 개선. 각 항목은 독립적으로 적용 가능.

---

## 작업 우선순위

| 등급 | 의미 |
|------|------|
| 🔴 필수 | 버그 또는 플랫폼 호환 문제. 반드시 수정 |
| 🟡 권장 | 누락된 핵심 기능 복원. 사용자 경험에 직접 영향 |
| 🟢 선택 | 코드 품질 개선 또는 부가 기능. 여유 있을 때 적용 |

---

## 🔴 A. 버그/이슈 수정 (필수)

### A1. `authStore.js` — `isLoggedIn` 항상 `true` 문제

**현재 문제**
- `frontend/src/stores/authStore.js:4` → 초기값 `isLoggedIn: true`
- `logout()` 에서도 `isLoggedIn: true`로 리셋
- 로그아웃해도 "로그인 상태"로 남음. GpkiLoginModal 조건 분기가 동작 불가

**수정 방법**
```javascript
// 초기 상태
isLoggedIn: false,
userName: null,

// bootstrapSession 성공 시
set({
  isLoggedIn: true,
  userName: data.user_name,
  sessionId: data.session_id,
  // ...
})

// logout 시
set({
  isLoggedIn: false,
  userName: null,
  sessionId: null,
  loginError: null,
  isInitializing: false,
})
```

**영향 범위**: authStore.js, 의존하는 컴포넌트(ChatInput, App.jsx)의 동작 확인 필요

---

### A2. `vite.config.js` — Windows `/dev/null` 호환 문제

**현재 문제**
- `frontend/vite.config.js:136` → openssl 출력을 `/dev/null`로 보냄
- Windows에서는 `/dev/null`이 존재하지 않아 에러 발생 가능

**수정 방법**
```javascript
// vite.config.js 상단 또는 verifyPrivateKey 함수 내
const NULL_DEVICE = process.platform === 'win32' ? 'NUL' : '/dev/null'

// 기존
'-out', '/dev/null',

// 변경
'-out', NULL_DEVICE,
```

**영향 범위**: vite.config.js의 verifyPrivateKey 함수만 해당

---

### A3. `vite.config.js` — GPKI 인증서 폴더 미존재 시 처리

**현재 문제**
- `collectCertificates()` 에서 폴더 미존재 시 `throw new Error` → 500 에러
- `bootstrapSession()` 실패 → `loginError` 표시되지만 사용자가 복구할 방법 없음

**수정 방법**
```javascript
function collectCertificates() {
  if (!fs.existsSync(GPKI_CERT_PATH)) {
    // throw 대신 빈 배열 반환
    console.warn(`[gpkiPlugin] 인증서 폴더가 존재하지 않습니다: ${GPKI_CERT_PATH}`)
    return []
  }
  // ... 기존 로직
}
```

**영향 범위**: vite.config.js의 collectCertificates, `/api/auth/certs` 엔드포인트

---

### A4. `chatStore.js` — `setStage('finalizing')` 시 content 초기화 UX

**현재 문제**
- `frontend/src/stores/chatStore.js:70-74`
- `finalizing` 진입 시 AI 메시지의 `content`를 빈 문자열로 덮어씀
- 사용자가 보던 초안 답변이 갑자기 사라짐

**수정 방법**
```javascript
setStage: (stage) =>
  set((state) => {
    if (stage === 'finalizing' && state.activeMessageId) {
      // 기존 AI 메시지 content를 지우는 대신 시스템 메시지 추가
      return {
        currentStage: stage,
        messages: [
          ...state.messages,
          {
            id: `msg_${Date.now()}_system_finalizing`,
            role: 'system',
            content: '최종 답변을 정리하고 있습니다...',
            timestamp: new Date().toISOString(),
          },
        ],
      }
    }
    return { currentStage: stage }
  }),
```

또는 더 간단하게: content를 초기화하지 않고 새 AI 메시지를 추가하여 최종 답변을 별도로 스트리밍

**영향 범위**: chatStore.js의 setStage, chat.py의 finalizing 토큰 스트리밍 흐름

---

## 🟡 B. 누락 기능 복원 (권장)

### B1. TopBar에 사용자명 + 로그아웃 버튼 복원

**현재 상태**
- `frontend/src/components/layout/TopBar.jsx` → OLTA 링크만 표시
- 사용자 이름, 로그아웃 버튼 없음

**수정 방법**
```jsx
import { useAuthStore } from '../../stores/authStore'

export default function TopBar() {
  const userName = useAuthStore((state) => state.userName)
  const sessionId = useAuthStore((state) => state.sessionId)
  const logout = useAuthStore((state) => state.logout)

  return (
    <header className="bg-slate-800 text-white px-6 py-3 flex items-center justify-between shrink-0">
      <h1 className="text-lg font-semibold tracking-tight">
        🏛️ AI 지방세 지식인
      </h1>
      <div className="flex items-center gap-4">
        <a
          href="https://www.olta.re.kr"
          target="_blank"
          rel="noreferrer"
          className="text-sm px-3 py-1 rounded bg-slate-700 hover:bg-slate-600 transition"
        >
          OLTA 열기
        </a>
        {sessionId && (
          <>
            <span className="text-sm text-slate-300">{userName}님</span>
            <button
              type="button"
              onClick={() => void logout()}
              className="text-sm px-3 py-1 rounded bg-red-600 hover:bg-red-700 transition"
            >
              로그아웃
            </button>
          </>
        )}
      </div>
    </header>
  )
}
```

**영향 범위**: TopBar.jsx. A1(authStore 수정) 적용 후 logout 동작이 정상화되어야 의미 있음

---

### B2. GpkiLoginModal 렌더링 연결

**현재 상태**
- `GpkiLoginModal.jsx`, `CertSelector.jsx` 존재하지만 `App.jsx`에서 렌더링하지 않음
- 자동 부트스트랩만 동작

**수정 방법**: 자동 부트스트랩 실패 시 모달로 fallback
```jsx
// App.jsx
import GpkiLoginModal from './components/auth/GpkiLoginModal'
import { useAuthStore } from './stores/authStore'

function App() {
  const sessionId = useAuthStore((state) => state.sessionId)
  const isInitializing = useAuthStore((state) => state.isInitializing)
  const bootstrapSession = useAuthStore((state) => state.bootstrapSession)
  const logout = useAuthStore((state) => state.logout)

  useEffect(() => {
    // OLTA 열기 로직 (기존 유지)
    // ...
    void bootstrapSession()
  }, [bootstrapSession])

  useEffect(() => {
    const handleBeforeUnload = () => void logout()
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [logout])

  return (
    <>
      <AppShell />
      {/* 세션 없고 초기화 중도 아닐 때 모달 표시 */}
      {!sessionId && !isInitializing && <GpkiLoginModal />}
    </>
  )
}
```

**전제 조건**: A1(authStore `isLoggedIn` 수정) 먼저 적용 필요
**영향 범위**: App.jsx, authStore.js, GpkiLoginModal.jsx

---

### B3. ChatInput placeholder — GPKI 인증 전 상태 메시지

**현재 상태**
- 세션 없을 때: "세션 준비 중..."
- PRD 명세: "GPKI 인증 후 이용 가능합니다"

**수정 방법**
```javascript
// frontend/src/components/chat/ChatInput.jsx
const placeholder = isInitializing
  ? '세션 준비 중...'
  : !sessionId
    ? 'GPKI 인증 후 이용 가능합니다'
    : isStreaming
      ? '답변 생성 중...'
      : '지방세 관련 질문을 입력하세요...'
```

**영향 범위**: ChatInput.jsx만 해당

---

## 🟢 C. 코드 품질 개선 (선택)

### C1. `useSSE.js` — `error` 이벤트 핸들러 추가

**현재 상태**
- 백엔드가 `error` 이벤트를 보낼 수 있으나 프론트에서 무시됨
- 네트워크 에러만 catch에서 처리

**수정 방법**
```javascript
// frontend/src/hooks/useSSE.js — handleEvent 함수 내 추가
if (eventType === 'error') {
  const errorMsg = data.message || data.error || '서버 오류가 발생했습니다.'
  failStream(aiMessageId, errorMsg)
  sawTerminalStage = true
  return
}
```

**영향 범위**: useSSE.js만 해당

---

### C2. `GpkiLoginModal.jsx` — 취소 버튼 추가

**현재 상태**
- PRD: [취소] + [확인] 두 버튼
- 현재: [확인] 버튼만 존재

**수정 방법**
```jsx
// GpkiLoginModal.jsx — form 내 버튼 영역
<div className="flex gap-3 pt-2">
  <button
    type="button"
    onClick={() => {
      setSelectedCertId(null)
      setPassword('')
      clearError()
    }}
    className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-50"
  >
    취소
  </button>
  <button
    type="submit"
    className="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm text-white transition hover:bg-blue-700 disabled:opacity-50"
    disabled={!selectedCertId || !password || isLoggingIn}
  >
    {isLoggingIn ? '인증 중...' : '확인'}
  </button>
</div>
```

**영향 범위**: GpkiLoginModal.jsx만 해당. B2(모달 렌더링 연결) 적용 시에만 의미 있음

---

### C3. `beforeunload` 로그아웃 — `sendBeacon` 방식으로 변경

**현재 문제**
- `fetch`로 로그아웃 호출 → 탭 닫기 시 요청이 완료되지 않을 가능성 높음

**수정 방법**
```javascript
// App.jsx — handleBeforeUnload
const handleBeforeUnload = () => {
  const { sessionId } = useAuthStore.getState()
  if (sessionId) {
    navigator.sendBeacon(
      '/api/auth/logout',
      new Blob(
        [JSON.stringify({ session_id: sessionId })],
        { type: 'application/json' }
      )
    )
  }
}
```

**영향 범위**: App.jsx만 해당. 백엔드 `/api/auth/logout` 엔드포인트는 변경 불필요

---

### C4. 세션 만료 시 재인증 유도

**현재 문제**
- 백엔드 세션 만료(30분) → 401 반환
- 프론트에서 401을 감지하여 재로그인 유도하는 로직 없음

**수정 방법**
```javascript
// frontend/src/hooks/useSSE.js — streamChat 내
const response = await fetch('/api/chat', { ... })

if (response.status === 401) {
  // 세션 만료 처리
  useAuthStore.getState().logout()
  failStream(aiMessageId, '세션이 만료되었습니다. 다시 로그인해 주세요.')
  return
}
```

**영향 범위**: useSSE.js, PreviewPanel.jsx (preview API도 동일 처리 권장)

---

## 작업 적용 순서 (권장)

의존 관계를 고려한 순서:

```
1단계 (기반 수정)
  A1. authStore isLoggedIn 수정
  A2. vite.config.js Windows 호환
  A3. vite.config.js 인증서 폴더 미존재 처리

2단계 (UI 복원 — A1 완료 후)
  B1. TopBar 사용자명 + 로그아웃 버튼
  B2. GpkiLoginModal 렌더링 연결
  B3. ChatInput placeholder 변경

3단계 (UX 개선)
  A4. finalizing content 초기화 개선

4단계 (품질 개선 — 독립 적용 가능)
  C1. error 이벤트 핸들러
  C2. 취소 버튼 (B2 적용 시)
  C3. sendBeacon 로그아웃
  C4. 세션 만료 재인증
```

---

## 적용 후 검증 체크리스트

- [ ] `npm run build` 성공
- [ ] `npm run lint` 에러 없음
- [ ] GPKI 인증서 폴더 없는 환경에서 `VITE_USE_MOCK=true npm run dev` 에러 없이 실행
- [ ] 로그인 모달이 표시되고 인증서 선택 + 비밀번호 입력으로 로그인 가능
- [ ] 로그인 후 TopBar에 사용자명 표시
- [ ] 로그아웃 버튼 클릭 시 모달 재표시
- [ ] "취득세 감면" 질문 → 스테퍼 5단계 전환 → 답변 스트리밍 → 출처 카드 표시
- [ ] finalizing 단계에서 이전 초안이 갑자기 사라지지 않음
- [ ] 출처 카드 클릭 → 상세 → 원문 바로가기 → 목록 복귀
- [ ] 탭 닫기 시 콘솔 에러 없음
