# Claude Code 프롬프트: AI 지방세 지식인 APP - Step 1 (프론트엔드) v2

> **이 프롬프트를 Claude Code에 그대로 붙여넣기 하세요.**
> `claude --dangerously-skip-permissions` 모드에서 실행을 권장합니다.

---

> **v2 변경사항**: GPKI 인증서를 가상(Mock) 데이터 대신 **실제 인증서**(`~/GPKI/Certificate/class2`)를 사용합니다.
> 인증서 목록 조회와 비밀번호 검증은 Vite 플러그인(`gpkiPlugin`)으로 처리하며, MSW Mock에서 제외합니다.
> 테스트 체크리스트에 **www.olta.re.kr 실제 로그인 테스트**가 포함됩니다.

---

너는 지금부터 "AI 지방세 지식인 APP"의 프론트엔드를 구현하는 시니어 풀스택 개발자야.
이 작업은 총 5단계로 나뉘며, 각 단계를 순서대로 완료해야 해.

## 사전 요구사항

이 Step을 시작하기 전에 아래 조건을 반드시 확인해:

1. **OpenSSL**: 시스템 PATH에 `openssl`이 설치되어 있어야 함. `openssl version`으로 확인.
2. **GPKI 인증서**: `~/GPKI/Certificate/class2` 폴더에 실제 GPKI 인증서 파일(`*_sig.cer`, `*_sig.key`)이 존재해야 함.
3. **Node.js**: v18 이상 설치.

위 조건이 충족되지 않으면 프론트엔드 GPKI 인증이 동작하지 않으니, 먼저 환경을 점검해.

## 핵심 규칙

1. **Todolist 파일(`TODO.md`)을 프로젝트 루트에 생성**하고, 모든 작업 항목을 체크박스로 관리해.
2. 각 세부 작업을 완료할 때마다 `TODO.md`에서 해당 항목을 `[x]`로 변경해.
3. 각 단계가 끝나면 반드시 **확인사항 체크리스트**를 실행하고, **메인 애플리케이션을 실행하여 테스트**해.
4. 테스트 결과를 `TODO.md`의 해당 단계 하단에 기록해.
5. 문제가 발견되면 즉시 수정한 후 다시 테스트해. 모든 체크가 통과해야 다음 단계로 진행해.

---

## 사전 작업: TODO.md 생성

가장 먼저 프로젝트 루트(`frontend/`)에 아래 내용으로 `TODO.md` 파일을 생성해:

```markdown
# AI 지방세 지식인 APP - Step 1 Todolist (v2: 실제 GPKI 인증서)

## 🔧 1단계: 프로젝트 초기화 + Mock 데이터 + GPKI 플러그인
- [ ] Vite + React 18 프로젝트 생성
- [ ] Tailwind CSS 설치 및 설정
- [ ] Zustand 설치
- [ ] react-markdown + remark-gfm 설치
- [ ] MSW(Mock Service Worker) 설치 및 브라우저 설정
- [ ] 디렉토리 구조 생성 (components/, stores/, mocks/, hooks/, utils/)
- [ ] vite.config.js에 gpkiPlugin() 구현 (실제 GPKI 인증서 읽기 + 비밀번호 검증)
- [ ] openssl로 ~/GPKI/Certificate/class2 인증서 파싱 확인
- [ ] mockChatResponses.json 생성 (취득세 감면, 재산세 납부 2건)
- [ ] mockSources.json 생성 (출처 3건)
- [ ] MSW handlers.js 작성 (POST /api/chat, GET /api/preview/:id, POST /api/auth/logout)
- [ ] MSW browser.js 설정 + main.jsx에서 개발 모드 시 MSW 시작

### ✅ 1단계 확인사항
- [ ] `openssl version` 실행 시 버전이 출력되는가?
- [ ] ~/GPKI/Certificate/class2 폴더에 *_sig.cer, *_sig.key 파일이 존재하는가?
- [ ] `npm run dev` 실행 시 에러 없이 빈 페이지가 뜨는가?
- [ ] 브라우저 콘솔에 "[MSW] Mocking enabled" 메시지가 표시되는가?
- [ ] 브라우저 콘솔에서 `fetch('/api/auth/certs').then(r=>r.json()).then(console.log)` 실행 시 실제 GPKI 인증서 목록이 반환되는가?
- [ ] 반환된 인증서에 owner(이름), department(부서), validFrom/validTo(유효기간)가 포함되는가?
- [ ] 브라우저 콘솔에서 실제 cert_id와 실제 비밀번호로 `fetch('/api/auth/gpki', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({cert_id:'<실제ID>', password:'<실제비밀번호>'})}).then(r=>r.json()).then(console.log)` 실행 시 `{success: true, user_name: "<실제이름>", ...}` 응답이 오는가?
- [ ] 잘못된 비밀번호로 동일 요청 시 `{success: false, error: "비밀번호가 일치하지 않습니다"}` 응답이 오는가?

📋 1단계 테스트 결과: (여기에 결과 기록)

---

## 🎨 2단계: 레이아웃 + GPKI 로그인 모달
- [ ] AppShell.jsx 구현 (좌우 50:50 그리드, 하단 StatusStepper 영역)
- [ ] TopBar.jsx 구현 (APP 이름, 사용자명, 로그아웃 버튼)
- [ ] authStore.js 구현 (isLoggedIn, userName, sessionId, login, logout, clearError)
- [ ] GpkiLoginModal.jsx 구현 (모달 팝업, 인증서 목록, 비밀번호 입력)
- [ ] CertSelector.jsx 구현 (인증서 저장 위치 라디오 + 인증서 카드 목록)
- [ ] 인증서 카드에 CN, 부서(OU), 유효기간, 시리얼번호 표시
- [ ] 로그인 성공 시 모달 닫힘 + TopBar에 사용자명 표시
- [ ] 로그인 실패 시 에러 메시지 표시 ("비밀번호가 일치하지 않습니다")
- [ ] 모달 외부 클릭 시 닫히지 않도록 처리
- [ ] APP 실행 시 자동으로 GPKI 모달 표시
- [ ] 로그아웃 시 상태 초기화 + GPKI 모달 재표시

### ✅ 2단계 확인사항
- [ ] APP 실행 시 GPKI 모달이 자동으로 표시되는가?
- [ ] 인증서 목록에 ~/GPKI/Certificate/class2 폴더의 실제 인증서들이 표시되는가?
- [ ] 인증서 카드에 소유자명(CN 추출), 부서(OU 추출), 유효기간이 표시되는가?
- [ ] 인증서 선택 후 실제 GPKI 비밀번호 입력 + 확인 → 모달 닫힘?
- [ ] 모달 닫힌 후 상단 바에 실제 인증서 소유자 이름이 표시되는가?
- [ ] 잘못된 비밀번호 입력 시 에러 메시지가 모달 내에 빨간색으로 표시되는가?
- [ ] "로그아웃" 클릭 시 GPKI 모달이 다시 뜨는가?
- [ ] 모달 바깥 영역 클릭해도 모달이 닫히지 않는가?

📋 2단계 테스트 결과: (여기에 결과 기록)

---

## 💬 3단계: 채팅 패널 + SSE 스트리밍
- [ ] chatStore.js 구현 (messages, currentStage, isStreaming, sendMessage, selectSource)
- [ ] ChatPanel.jsx 구현 (메시지 목록 컨테이너, 스크롤 자동 하단 이동)
- [ ] ChatMessage.jsx 구현 (user: 오른쪽/파란배경, ai: 왼쪽/흰배경+Markdown, system: 가운데/회색)
- [ ] ChatInput.jsx 구현 (입력창 + 전송 버튼)
  - [ ] 로그인 전 비활성화 (placeholder: "GPKI 인증 후 이용 가능합니다")
  - [ ] 로그인 후 활성화 (placeholder: "지방세 관련 질문을 입력하세요...")
  - [ ] Enter로 전송, Shift+Enter로 줄바꿈
  - [ ] 전송 중 입력창 비활성화 + 로딩 표시
- [ ] useSSE.js 커스텀 훅 구현 (fetch + ReadableStream으로 SSE 파싱)
- [ ] MSW handlers.js에 Mock SSE 응답 구현 (stage_change → token 스트리밍 → sources → done)
- [ ] StreamingResponse.jsx 구현 (토큰 단위 실시간 렌더링)
- [ ] StatusStepper.jsx 구현 (4단계: 웹검색 → 초안작성 → 검증 → 완료)
  - [ ] 현재 단계: 파란색 + 펄스 애니메이션
  - [ ] 완료 단계: 초록색 체크
  - [ ] 미도달 단계: 회색 비활성

### ✅ 3단계 확인사항
- [ ] 로그인 전 채팅 입력창에 "GPKI 인증 후 이용 가능합니다"가 표시되고 비활성인가?
- [ ] 로그인 후 "지방세 관련 질문을 입력하세요..."로 변경되고 활성화되는가?
- [ ] "취득세 감면 대상" 입력 후 Enter → 사용자 메시지가 오른쪽 파란 배경으로 표시되는가?
- [ ] StatusStepper가 "웹 검색 중" → "초안 작성 중" → "검증 중" → "답변 완료" 순서로 전환되는가?
- [ ] AI 답변이 글자 단위로 스트리밍되어 실시간 표시되는가?
- [ ] AI 답변에 Markdown (##, **, 표, > 인용) 이 정상 렌더링되는가?
- [ ] 전송 중 입력창이 비활성화되고, 완료 후 다시 활성화되는가?
- [ ] 메시지가 많아지면 자동으로 스크롤이 하단으로 이동하는가?

📋 3단계 테스트 결과: (여기에 결과 기록)

---

## 📄 4단계: 미리보기 패널 + 출처 연동
- [ ] PreviewPanel.jsx 구현 (오른쪽 50% 영역, 상태별 분기 표시)
  - [ ] 채팅 전: 안내 문구 ("질문을 입력하면 관련 법령과 해석례가 여기에 표시됩니다")
  - [ ] 검색 중: 스켈레톤 로딩 UI (회색 펄스 블록 3개)
  - [ ] 결과 있음: SourceCard 목록
  - [ ] 결과 없음: "관련 출처를 찾지 못했습니다"
- [ ] SourceCard.jsx 구현 (제목, 유형 배지, 미리보기 텍스트 2줄)
  - [ ] 유형 배지 색상: 법령(파랑), 해석례(초록), 판례(보라), 훈령(주황)
  - [ ] 클릭 시 chatStore.selectSource(sourceId) 호출
- [ ] SourceDetail.jsx 구현 (전체 내용 표시, 원문 바로가기 링크, 닫기 버튼)
- [ ] 채팅 응답의 sources 이벤트 수신 시 PreviewPanel에 출처 카드 자동 표시
- [ ] 출처 카드 클릭 → SourceDetail 표시 → 닫기 → 카드 목록 복귀

### ✅ 4단계 확인사항
- [ ] 로그인 직후 오른쪽 패널에 "질문을 입력하면..." 안내 문구가 보이는가?
- [ ] 질문 전송 시 오른쪽 패널에 스켈레톤 로딩이 표시되는가?
- [ ] 답변 완료 후 출처 카드가 2개 표시되는가? (취득세 감면 질문 시)
- [ ] 출처 카드에 "법령" 배지가 파란색으로 표시되는가?
- [ ] 출처 카드 클릭 시 상세 내용 (법령 전문)이 표시되는가?
- [ ] "원문 바로가기" 클릭 시 olta.re.kr URL이 새 탭에서 열리는가?
- [ ] 상세에서 "닫기" 클릭 시 카드 목록으로 돌아가는가?
- [ ] "재산세 납부 기한" 질문 시 출처 카드가 1개로 업데이트되는가?

📋 4단계 테스트 결과: (여기에 결과 기록)

---

## 🧪 5단계: 통합 테스트 + 최종 검증
- [ ] 전체 UI 디자인 점검 및 미세 조정
  - [ ] 좌우 패널 높이가 화면에 맞게 꽉 차는가? (h-screen)
  - [ ] 스크롤이 각 패널 내부에서만 동작하는가?
  - [ ] 모바일이 아닌 데스크톱 최소 너비(1024px)에서 레이아웃 깨짐 없는가?
- [ ] 연속 질문 시나리오 테스트
  - [ ] "취득세 감면 대상" → 답변 완료 → "재산세 납부 기한" → 두 대화 모두 유지?
- [ ] 미등록 질문 테스트
  - [ ] "자동차세 환급" (Mock에 없는 질문) → 기본 응답 "해당 질문에 대한 정보를 찾지 못했습니다" 표시?
- [ ] 에러 핸들링 테스트
  - [ ] 네트워크 에러 시 사용자에게 에러 메시지가 표시되는가?
- [ ] beforeunload 이벤트로 탭 닫기 시 로그아웃 호출 확인
- [ ] OLTA 로그인 테스트 (수동)
  - [ ] 브라우저에서 www.olta.re.kr 접속
  - [ ] 실제 GPKI 인증서로 로그인 시도
  - [ ] 정상 접속 및 로그인 완료 확인
- [ ] 빌드 테스트: `npm run build` 에러 없이 완료되는가?

### ✅ 5단계 최종 확인사항 (전체 플로우)
- [ ] APP 실행 → GPKI 모달 표시
- [ ] 실제 인증서 선택 + 실제 비밀번호 입력 → 로그인 성공 → 모달 닫힘
- [ ] 상단 바에 "<실제 소유자명>님" + "로그아웃" 버튼 표시
- [ ] 채팅창 활성화, "지방세 관련 질문을 입력하세요..." placeholder
- [ ] "취득세 감면 대상" 입력 → Enter
- [ ] StatusStepper: 웹 검색 → 초안 작성 → 검증 → 완료 순서 전환
- [ ] AI 답변이 글자 단위로 스트리밍 표시
- [ ] 답변에 Markdown 서식 (제목, 볼드, 표, 인용) 정상 렌더링
- [ ] 오른쪽 패널에 출처 카드 2개 표시
- [ ] 출처 카드 클릭 → 상세 내용 + "원문 바로가기" 링크
- [ ] "재산세 납부 기한" 두 번째 질문 → 이전 대화 유지 + 새 답변 + 출처 업데이트
- [ ] "로그아웃" 클릭 → 대화 초기화 + GPKI 모달 재표시
- [ ] www.olta.re.kr에 실제 GPKI 인증서로 로그인 성공 확인
- [ ] `npm run build` 성공

📋 5단계 테스트 결과: (여기에 결과 기록)
```

---

## ▶ 1단계 시작: 프로젝트 초기화 + Mock 데이터 + GPKI 플러그인

이제 1단계를 시작해. 아래 지시사항을 **순서대로** 실행해.

### 1-1. 프로젝트 생성

```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install zustand react-markdown remark-gfm
npm install -D tailwindcss @tailwindcss/vite msw
npx msw init public --save
```

### 1-2. Tailwind CSS 설정 + GPKI 플러그인

`vite.config.js`에 Tailwind 플러그인과 **gpkiPlugin()** 을 함께 추가해.

> ⚠️ **핵심**: GPKI 인증서 목록 조회(`GET /api/auth/certs`)와 비밀번호 검증(`POST /api/auth/gpki`)은 이 Vite 플러그인이 처리한다. MSW에 등록하지 마.

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'
import { execSync } from 'child_process'

// GPKI 인증서 폴더 경로 (하드디스크: ~/GPKI/Certificate/class2)
const GPKI_CERT_PATH = path.join(
  process.env.HOME || process.env.USERPROFILE,
  'GPKI/Certificate/class2'
)

function gpkiPlugin() {
  return {
    name: 'gpki-cert-api',
    configureServer(server) {
      // GET /api/auth/certs — 실제 GPKI 인증서 목록 반환
      server.middlewares.use('/api/auth/certs', (req, res, next) => {
        if (req.method !== 'GET') return next()

        try {
          const files = fs.readdirSync(GPKI_CERT_PATH)
          const sigCerts = files.filter(f => f.endsWith('_sig.cer'))

          const certs = sigCerts.map(sigFile => {
            const baseName = sigFile.replace('_sig.cer', '')
            const cerPath = path.join(GPKI_CERT_PATH, sigFile)

            // openssl로 인증서 정보 파싱
            let subject = '', serial = '', notBefore = '', notAfter = ''
            try {
              const out = execSync(
                `openssl x509 -in "${cerPath}" -inform DER -subject -serial -dates -noout`,
                { encoding: 'utf8' }
              )
              const lines = out.trim().split('\n')
              for (const line of lines) {
                if (line.startsWith('subject=')) subject = line.slice(8)
                if (line.startsWith('serial=')) serial = line.slice(7)
                if (line.startsWith('notBefore=')) notBefore = line.slice(10)
                if (line.startsWith('notAfter=')) notAfter = line.slice(9)
              }
            } catch (e) {
              console.error('인증서 파싱 실패:', sigFile, e.message)
            }

            // CN에서 이름 추출 (예: "062김현수027" → "김현수")
            const cnMatch = subject.match(/CN=(\S+)/)
            const cn = cnMatch ? cnMatch[1] : baseName
            const nameMatch = cn.match(/\d*([가-힣]+)\d*/)
            const ownerName = nameMatch ? nameMatch[1] : cn

            // OU에서 부서 추출
            const ouParts = subject.match(/OU=([^,]+)/g) || []
            const department = ouParts
              .map(p => p.replace('OU=', '').trim())
              .filter(p => p !== 'GPKI' && p !== 'people')
              .join(' ') || '미상'

            return {
              id: baseName,
              owner: ownerName,
              cn: cn,
              department: department,
              validFrom: notBefore.trim(),
              validTo: notAfter.trim(),
              serial: serial.substring(0, 16) + '...',
            }
          })

          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(certs))
        } catch (err) {
          res.statusCode = 500
          res.end(JSON.stringify({ error: '인증서 폴더를 읽을 수 없습니다: ' + err.message }))
        }
      })

      // POST /api/auth/gpki — 실제 GPKI 인증서 비밀번호 검증 (openssl pkcs8)
      server.middlewares.use('/api/auth/gpki', (req, res, next) => {
        if (req.method !== 'POST') return next()

        let body = ''
        req.on('data', chunk => { body += chunk })
        req.on('end', () => {
          try {
            const { cert_id, password } = JSON.parse(body)
            const keyPath = path.join(GPKI_CERT_PATH, cert_id + '_sig.key')

            if (!fs.existsSync(keyPath)) {
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({ success: false, error: '인증서 키 파일을 찾을 수 없습니다' }))
              return
            }

            // openssl로 개인키 복호화 시도 → 비밀번호 검증
            try {
              execSync(
                `openssl pkcs8 -in "${keyPath}" -inform DER -passin pass:${password} -noout 2>&1`,
                { encoding: 'utf8', timeout: 5000 }
              )

              // 비밀번호 검증 성공 → 인증서에서 이름 추출
              const cerPath = path.join(GPKI_CERT_PATH, cert_id + '_sig.cer')
              const out = execSync(
                `openssl x509 -in "${cerPath}" -inform DER -subject -noout`,
                { encoding: 'utf8' }
              )
              const cnMatch = out.match(/CN=(\S+)/)
              const cn = cnMatch ? cnMatch[1] : cert_id
              const nameMatch = cn.match(/\d*([가-힣]+)\d*/)
              const ownerName = nameMatch ? nameMatch[1] : cn

              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({
                success: true,
                user_name: ownerName,
                session_id: `session_${Date.now()}`,
                cert_cn: cn
              }))
            } catch (e) {
              res.setHeader('Content-Type', 'application/json')
              res.end(JSON.stringify({
                success: false,
                error: '비밀번호가 일치하지 않습니다'
              }))
            }
          } catch (e) {
            res.statusCode = 400
            res.end(JSON.stringify({ error: '잘못된 요청입니다' }))
          }
        })
      })
    }
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), gpkiPlugin()],
})
```

`src/index.css` 최상단에 추가:
```css
@import "tailwindcss";
```

### 1-3. 디렉토리 구조 생성

```
src/
├── components/
│   ├── layout/
│   ├── auth/
│   ├── chat/
│   └── preview/
├── stores/
├── mocks/
│   └── data/
├── hooks/
└── utils/
```

### 1-4. Mock 데이터 파일 생성

> ⚠️ **참고**: GPKI 인증서 Mock 데이터(mockCerts.json)는 **생성하지 않는다**. 인증서 데이터는 Vite 플러그인이 실제 파일에서 읽어온다.

**`src/mocks/data/mockChatResponses.json`**:
```json
{
  "취득세 감면": {
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
  "재산세 납부": {
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

### 1-5. MSW 핸들러 구현

**`src/mocks/handlers.js`** — 아래 API를 Mock으로 구현해:

> ⚠️ **주의**: `GET /api/auth/certs`와 `POST /api/auth/gpki`는 Vite 플러그인(gpkiPlugin)이 처리하므로, MSW 핸들러에 등록하지 마. MSW에서 이들을 등록하면 Vite 미들웨어보다 먼저 가로채서 실제 인증서가 사용되지 않게 된다.

1. **`POST /api/auth/logout`**: `{ success: true }` 반환
2. **`POST /api/chat`**: question에서 키워드("취득세", "재산세") 매칭 → SSE 형식 응답 반환
   - SSE는 MSW에서 직접 지원하지 않으므로 **`new Response(new ReadableStream(...))`** 패턴을 사용
   - `Content-Type: text/event-stream` 헤더 설정
   - stages 배열의 delay에 따라 stage_change 이벤트 전송
   - answer를 5글자 단위 chunk로 분할하여 token 이벤트 전송 (30ms 간격)
   - sources 이벤트 전송
   - 매칭 안 되면 기본 응답: "해당 질문에 대한 정보를 찾지 못했습니다"
3. **`GET /api/preview/:sourceId`**: mockChatResponses의 sources에서 id 매칭하여 반환

**`src/mocks/browser.js`**:
```javascript
import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'
export const worker = setupWorker(...handlers)
```

**`src/main.jsx`** 수정: 개발 모드에서 MSW 시작 후 React 렌더링:
```javascript
async function enableMocking() {
  if (import.meta.env.DEV) {
    const { worker } = await import('./mocks/browser')
    return worker.start({ onUnhandledRequest: 'bypass' })
  }
}
enableMocking().then(() => {
  // ReactDOM.createRoot(...).render(...)
})
```

> `onUnhandledRequest: 'bypass'`로 설정해야 MSW에 등록되지 않은 `/api/auth/certs`, `/api/auth/gpki` 요청이 Vite 미들웨어(gpkiPlugin)로 정상 전달된다.

### 1-6. 1단계 확인

모든 파일 생성 후:
1. `openssl version` 실행 → 버전 출력 확인
2. `ls ~/GPKI/Certificate/class2/` 실행 → `*_sig.cer`, `*_sig.key` 파일 존재 확인
3. `npm run dev` 실행
4. 브라우저에서 http://localhost:5173 접속
5. 콘솔에 `[MSW] Mocking enabled` 확인
6. 콘솔에서 인증서 목록 테스트:
```javascript
fetch('/api/auth/certs').then(r=>r.json()).then(console.log)
// → 실제 GPKI 인증서 목록 (owner, cn, department, validFrom, validTo) 반환 확인
```
7. 콘솔에서 로그인 테스트 (반환된 인증서의 id와 실제 비밀번호 사용):
```javascript
fetch('/api/auth/gpki', {
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body: JSON.stringify({cert_id:'<위에서 반환된 실제 id>', password:'<실제 비밀번호>'})
}).then(r=>r.json()).then(console.log)
// → {success: true, user_name: "<실제이름>", session_id: "session_...", cert_cn: "..."} 확인
```
8. 잘못된 비밀번호로 동일 요청 → `{success: false, error: "비밀번호가 일치하지 않습니다"}` 확인

**TODO.md의 1단계 항목들을 모두 `[x]`로 업데이트하고, 테스트 결과를 기록해.**

---

## ▶ 2단계 시작: 레이아웃 + GPKI 로그인 모달

1단계 확인이 모두 통과하면 2단계를 시작해.

### 2-1. authStore.js

```javascript
// src/stores/authStore.js
import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  isLoggedIn: false,
  userName: null,
  sessionId: null,
  isLoggingIn: false,
  loginError: null,

  login: async (certId, password) => {
    set({ isLoggingIn: true, loginError: null })
    try {
      const res = await fetch('/api/auth/gpki', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cert_id: certId, password })
      })
      const data = await res.json()
      if (data.success) {
        set({ isLoggedIn: true, userName: data.user_name, sessionId: data.session_id, isLoggingIn: false })
      } else {
        set({ loginError: data.error, isLoggingIn: false })
      }
    } catch (err) {
      set({ loginError: '로그인 중 오류가 발생했습니다.', isLoggingIn: false })
    }
  },

  logout: async () => {
    try { await fetch('/api/auth/logout', { method: 'POST' }) } catch {}
    set({ isLoggedIn: false, userName: null, sessionId: null, loginError: null })
  },

  clearError: () => set({ loginError: null })
}))
```

### 2-2. 컴포넌트 구현 지시

아래 화면 설계에 맞게 각 컴포넌트를 구현해. **Tailwind CSS만 사용**하고, 외부 UI 라이브러리는 사용하지 마.

**AppShell.jsx**:
- 최상위 컨테이너: `h-screen flex flex-col`
- TopBar (상단)
- 본문: `flex-1 grid grid-cols-2` (왼쪽 ChatPanel, 오른쪽 PreviewPanel)
- StatusStepper (하단)
- isLoggedIn이 false면 GpkiLoginModal을 오버레이로 표시

**TopBar.jsx**:
- 왼쪽: "🏛️ AI 지방세 지식인" 앱 이름
- 오른쪽: 로그인 상태면 "OOO님" + "로그아웃" 버튼
- 배경: 진한 남색(`bg-slate-800 text-white`)

**GpkiLoginModal.jsx**:
- 화면 중앙 모달 (backdrop: `bg-black/50`, 모달: `bg-white rounded-xl shadow-2xl`)
- 모달 외부 클릭으로 닫히지 않음
- 상단: "🔐 행정전자서명 인증 로그인" 제목
- 인증서 저장 위치: 라디오 버튼 ("하드디스크" 기본 선택, "보안토큰")
- 인증서 목록: GET /api/auth/certs로 로드 (Vite 플러그인이 실제 인증서 반환)
  - 소유자명 (CN에서 추출한 한국어 이름)
  - 부서명 (OU에서 추출)
  - CN 원본 표시
  - 유효기간 (notBefore ~ notAfter)
  - 시리얼번호
  - 선택된 인증서는 파란 테두리 하이라이트
- 비밀번호 입력: `type="password"`
- 에러 메시지: 빨간 텍스트
- 하단: "취소"(회색) + "확인"(파란색) 버튼
- "확인" 클릭 → authStore.login(certId, password) 호출
- 로딩 중 버튼에 스피너 표시

### 2-3. 2단계 확인

구현 후:
1. `npm run dev`로 실행
2. 브라우저에서 전체 플로우 테스트:
   - 모달 표시 → 실제 인증서 목록 확인 → 인증서 선택 → 실제 비밀번호 입력 → 로그인 성공
   - 잘못된 비밀번호 → 에러 메시지 → 올바른 비밀번호로 재시도 → 성공
   - 로그아웃 → 모달 재표시
3. TODO.md 2단계 확인사항을 모두 체크하고 결과 기록

---

## ▶ 3단계 시작: 채팅 패널 + SSE 스트리밍

2단계 확인이 모두 통과하면 3단계를 시작해.

### 3-1. chatStore.js

```javascript
// src/stores/chatStore.js — 아래 인터페이스로 구현해
{
  messages: [],           // { id: string, role: 'user'|'ai'|'system', content: string, timestamp: Date, sources?: [] }
  currentStage: null,     // 'crawling' | 'drafting' | 'verifying' | 'done' | null
  isStreaming: false,
  selectedSourceId: null,
  currentSources: [],     // 현재 답변의 출처 목록

  sendMessage: async (question, sessionId) => {
    // 1. 사용자 메시지 추가
    // 2. isStreaming = true
    // 3. fetch POST /api/chat (SSE)
    // 4. ReadableStream으로 SSE 파싱
    //    - stage_change → currentStage 업데이트
    //    - token → AI 메시지의 content에 토큰 추가 (실시간)
    //    - sources → currentSources 업데이트
    //    - done → isStreaming = false
  },
  selectSource: (sourceId) => set({ selectedSourceId: sourceId }),
  clearChat: () => set({ messages: [], currentStage: null, currentSources: [], selectedSourceId: null })
}
```

### 3-2. SSE 파싱 로직

**useSSE.js**는 만들지 않아도 돼. chatStore 안에서 직접 처리해.

SSE 파싱 핵심 로직:
```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id: sessionId, question })
})

const reader = response.body.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })

  // SSE 파싱: "event: xxx\ndata: {...}\n\n" 패턴 분리
  const events = buffer.split('\n\n')
  buffer = events.pop() // 마지막 미완성 이벤트는 buffer에 유지

  for (const eventStr of events) {
    const lines = eventStr.split('\n')
    let eventType = '', eventData = ''
    for (const line of lines) {
      if (line.startsWith('event: ')) eventType = line.slice(7)
      if (line.startsWith('data: ')) eventData = line.slice(6)
    }
    if (!eventType || !eventData) continue
    const data = JSON.parse(eventData)
    // eventType에 따라 처리...
  }
}
```

### 3-3. 컴포넌트 구현 지시

**ChatPanel.jsx**:
- 메시지 목록 영역: `flex-1 overflow-y-auto` (내부 스크롤)
- 메시지 추가 시 자동 하단 스크롤 (`useRef` + `scrollIntoView`)
- 하단에 ChatInput 고정

**ChatMessage.jsx**:
- role === 'user': 오른쪽 정렬, `bg-blue-500 text-white` 말풍선
- role === 'ai': 왼쪽 정렬, `bg-white border` 말풍선, `react-markdown`으로 렌더링
- role === 'system': 가운데 정렬, `text-gray-500 text-sm italic`

**ChatInput.jsx**:
- `textarea`로 구현 (Shift+Enter 줄바꿈 지원)
- 높이 자동 조절 (최소 1줄, 최대 5줄)
- 오른쪽에 전송 버튼 (파란 화살표 아이콘 또는 "전송" 텍스트)
- isStreaming 중이면 비활성화 + "답변 생성 중..." placeholder

**StatusStepper.jsx**:
- 가로 배치 4단계: 🔍 웹 검색 → ✏️ 초안 작성 → 🔎 검증 → ✅ 완료
- 각 단계 사이에 진행 바(─────)
- currentStage에 따라:
  - 해당 단계: `text-blue-600 font-bold` + `animate-pulse`
  - 이전 단계: `text-green-600` + ✓ 체크 아이콘
  - 이후 단계: `text-gray-300`
- currentStage가 null이면 모든 단계 회색 비활성

### 3-4. 3단계 확인

구현 후:
1. `npm run dev`로 실행
2. 실제 GPKI 인증서로 로그인 → "취득세 감면 대상" 입력 → 전체 스트리밍 플로우 확인
3. TODO.md 3단계 확인사항을 모두 체크하고 결과 기록

---

## ▶ 4단계 시작: 미리보기 패널 + 출처 연동

3단계 확인이 모두 통과하면 4단계를 시작해.

### 4-1. 컴포넌트 구현 지시

**PreviewPanel.jsx**:
- 전체 높이를 채우는 컨테이너 (`h-full overflow-y-auto bg-gray-50`)
- 상단 헤더: "📋 출처 및 관련 문서" 제목
- 상태별 렌더링:
  - `currentSources.length === 0 && !isStreaming`: 안내 문구
  - `isStreaming && currentStage === 'crawling'`: 스켈레톤 로딩 (3개의 회색 펄스 블록)
  - `currentSources.length > 0`: SourceCard 목록
- selectedSourceId가 있으면 SourceDetail 표시 (카드 목록 대신)

**SourceCard.jsx**:
- 카드 디자인: `bg-white rounded-lg shadow-sm border p-4 cursor-pointer hover:shadow-md transition`
- 상단: 유형 배지 (법령/해석례/판례/훈령, 각각 다른 색상)
  - 법령: `bg-blue-100 text-blue-700`
  - 해석례: `bg-green-100 text-green-700`
  - 판례: `bg-purple-100 text-purple-700`
  - 훈령: `bg-orange-100 text-orange-700`
- 제목: `font-semibold text-lg`
- 미리보기 텍스트: `text-gray-600 text-sm line-clamp-2`
- 클릭 → `chatStore.selectSource(source.id)`

**SourceDetail.jsx**:
- 상단: "← 목록으로" 뒤로가기 버튼 + 제목
- 본문: 전체 content 텍스트 (프리포맷 또는 줄바꿈 유지)
- 하단: "🔗 원문 바로가기" 버튼 → `window.open(url, '_blank')`
- 닫기: `chatStore.selectSource(null)` 호출

### 4-2. 4단계 확인

구현 후:
1. `npm run dev`로 실행
2. 실제 GPKI 인증서로 로그인 → 질문 → 출처 표시 → 카드 클릭 → 상세 → 바로가기 → 닫기 전체 플로우 확인
3. TODO.md 4단계 확인사항을 모두 체크하고 결과 기록

---

## ▶ 5단계 시작: 통합 테스트 + 최종 검증

4단계 확인이 모두 통과하면 5단계를 시작해.

### 5-1. UI 미세 조정

- 각 패널이 `h-full`로 화면 높이를 꽉 채우는지 확인
- 긴 답변 시 채팅 패널 내부 스크롤이 정상인지 확인
- StatusStepper가 하단에 고정되어 내용이 잘리지 않는지 확인
- 색상, 간격, 폰트 크기 등 전체적으로 깔끔한지 점검

### 5-2. 시나리오 테스트

아래 시나리오를 **순서대로** 직접 브라우저에서 수행하고 결과를 TODO.md에 기록해:

1. **정상 로그인 → 첫 질문**: 실제 GPKI 인증서 + 실제 비밀번호로 로그인 → "취득세 감면 대상" 입력 → 스트리밍 + 출처 2건
2. **연속 질문**: "재산세 납부 기한" 입력 → 이전 대화 유지 + 새 답변 + 출처 1건으로 업데이트
3. **미등록 질문**: "자동차세 환급" 입력 → 기본 안내 메시지 표시
4. **로그아웃 → 재로그인**: 로그아웃 → 대화 초기화 확인 → 재로그인 가능 확인
5. **로그인 실패**: 잘못된 비밀번호 입력 → "비밀번호가 일치하지 않습니다" 에러 → 올바른 실제 비밀번호 재입력 → 성공
6. **OLTA 로그인 테스트** (수동, APP 외부):
   - 브라우저에서 **www.olta.re.kr** 접속
   - 실제 GPKI 인증서를 사용하여 로그인 시도
   - 정상 접속 및 로그인 완료 여부 확인
   - 이 테스트는 APP의 GPKI 인증서가 실제 유효한 인증서인지 검증하기 위한 것

### 5-3. 빌드 테스트

```bash
npm run build
```

에러 없이 완료되는지 확인.

### 5-4. 최종 확인

TODO.md의 5단계 최종 확인사항을 **모두** 체크해. 하나라도 실패하면 수정 후 재테스트.

모든 항목이 `[x]`가 되면 **최종 TODO.md 내용을 출력**해.

---

## ⚠️ 중요 제약사항

1. **한국어 UI**: 모든 텍스트는 한국어로 작성. 영어 UI 텍스트 사용 금지.
2. **GPKI는 실제 인증서, 나머지는 Mock**: GPKI 인증(인증서 목록 조회, 비밀번호 검증)은 Vite 플러그인(`gpkiPlugin`)을 통해 `~/GPKI/Certificate/class2`의 실제 인증서를 사용. 채팅 SSE, 미리보기 등 나머지 API는 MSW Mock으로 동작. 실제 API 서버(FastAPI)는 없음.
3. **localStorage 금지**: 모든 상태는 Zustand 메모리 전용. localStorage, sessionStorage, cookie 사용 금지.
4. **외부 UI 라이브러리 금지**: Tailwind CSS만 사용. MUI, Ant Design 등 사용 금지.
5. **TODO.md 필수 업데이트**: 모든 작업 완료/실패를 TODO.md에 기록.
6. **단계 건너뛰기 금지**: 이전 단계의 모든 확인사항이 통과해야 다음 단계 진행.
7. **Step 2 호환성**: API 엔드포인트와 요청/응답 포맷은 변경하지 마. Step 2에서 MSW만 제거하고 실제 FastAPI로 교체할 수 있어야 해.
8. **OpenSSL 필수**: 시스템에 `openssl`이 PATH에 설치되어 있어야 함. `openssl version`으로 확인.
9. **GPKI 인증서 경로**: `~/GPKI/Certificate/class2`에 실제 GPKI 인증서 파일(`*_sig.cer`, `*_sig.key`)이 존재해야 함.
