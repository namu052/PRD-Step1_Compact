# AI 지방세 지식인 APP - Step 1 Todolist (v2: 실제 GPKI 인증서)

## 🔧 1단계: 프로젝트 초기화 + Mock 데이터 + GPKI 플러그인
- [x] Vite + React 프로젝트 구성 확인
- [x] Tailwind CSS 설치 및 설정
- [x] Zustand 설치
- [x] react-markdown + remark-gfm 설치
- [x] MSW(Mock Service Worker) 설치 및 브라우저 설정
- [x] 디렉토리 구조 생성 (components/, stores/, mocks/, hooks/, utils/)
- [x] `vite.config.js`에 `gpkiPlugin()` 구현 (실제 GPKI 인증서 읽기 + 비밀번호 검증)
- [x] `openssl`로 `~/GPKI/Certificate/class2` 인증서 파싱 로직 연결
- [x] `mockChatResponses.json` 생성 (취득세 감면, 재산세 납부 2건)
- [x] `mockSources.json` 생성 (출처 3건)
- [x] `MSW handlers.js` 작성 (POST `/api/chat`, GET `/api/preview/:id`, POST `/api/auth/logout`)
- [x] `MSW browser.js` 설정 + `main.jsx`에서 개발 모드 시 MSW 시작

### ✅ 1단계 확인사항
- [x] `openssl version` 실행 시 버전이 출력되는가?
- [ ] `~/GPKI/Certificate/class2` 폴더에 `*_sig.cer`, `*_sig.key` 파일이 존재하는가?
- [ ] `npm run dev` 실행 시 에러 없이 빈 페이지가 뜨는가?
- [ ] 브라우저 콘솔에 "[MSW] Mocking enabled" 메시지가 표시되는가?
- [ ] 브라우저 콘솔에서 `fetch('/api/auth/certs').then(r=>r.json()).then(console.log)` 실행 시 실제 GPKI 인증서 목록이 반환되는가?
- [ ] 반환된 인증서에 owner(이름), department(부서), validFrom/validTo(유효기간)가 포함되는가?
- [ ] 브라우저 콘솔에서 실제 cert_id와 실제 비밀번호로 GPKI 로그인 요청 시 `{success: true, user_name: "<실제이름>", ...}` 응답이 오는가?
- [ ] 잘못된 비밀번호로 동일 요청 시 `{success: false, error: "비밀번호가 일치하지 않습니다"}` 응답이 오는가?

📋 1단계 테스트 결과: `openssl version`은 성공. 현재 환경에는 `/home/pc/GPKI/Certificate/class2` 경로가 없어 실제 인증서 조회/비밀번호 검증은 미실행.

---

## 🎨 2단계: 레이아웃 + GPKI 로그인 모달
- [x] `AppShell.jsx` 구현 (좌우 50:50 그리드, 하단 `StatusStepper` 영역)
- [x] `TopBar.jsx` 구현 (APP 이름, 사용자명, 로그아웃 버튼)
- [x] `authStore.js` 구현 (`isLoggedIn`, `userName`, `sessionId`, `login`, `logout`, `clearError`)
- [x] `GpkiLoginModal.jsx` 구현 (모달 팝업, 인증서 목록, 비밀번호 입력)
- [x] `CertSelector.jsx` 구현 (인증서 저장 위치 라디오 + 인증서 카드 목록)
- [x] 인증서 카드에 CN, 부서(OU), 유효기간, 시리얼번호 표시
- [x] 로그인 성공 시 모달 닫힘 + TopBar에 사용자명 표시
- [x] 로그인 실패 시 에러 메시지 표시 ("비밀번호가 일치하지 않습니다")
- [x] 모달 외부 클릭 시 닫히지 않도록 처리
- [x] APP 실행 시 자동으로 GPKI 모달 표시
- [x] 로그아웃 시 상태 초기화 + GPKI 모달 재표시

### ✅ 2단계 확인사항
- [ ] APP 실행 시 GPKI 모달이 자동으로 표시되는가?
- [ ] 인증서 목록에 `~/GPKI/Certificate/class2` 폴더의 실제 인증서들이 표시되는가?
- [ ] 인증서 카드에 소유자명(CN 추출), 부서(OU 추출), 유효기간이 표시되는가?
- [ ] 인증서 선택 후 실제 GPKI 비밀번호 입력 + 확인 → 모달 닫힘?
- [ ] 모달 닫힌 후 상단 바에 실제 인증서 소유자 이름이 표시되는가?
- [ ] 잘못된 비밀번호 입력 시 에러 메시지가 모달 내에 빨간색으로 표시되는가?
- [ ] "로그아웃" 클릭 시 GPKI 모달이 다시 뜨는가?
- [ ] 모달 바깥 영역 클릭해도 모달이 닫히지 않는가?

📋 2단계 테스트 결과: UI 로직은 구현됨. 실제 인증서 경로 부재로 수동 로그인 검증은 미실행.

---

## 💬 3단계: 채팅 패널 + SSE 스트리밍
- [x] `chatStore.js` 구현 (`messages`, `currentStage`, `isStreaming`, `selectSource`)
- [x] `ChatPanel.jsx` 구현 (메시지 목록 컨테이너, 스크롤 자동 하단 이동)
- [x] `ChatMessage.jsx` 구현 (user: 오른쪽/파란배경, ai: 왼쪽/흰배경+Markdown, system: 가운데/회색)
- [x] `ChatInput.jsx` 구현 (입력창 + 전송 버튼)
- [x] 로그인 전 비활성화 (placeholder: "GPKI 인증 후 이용 가능합니다")
- [x] 로그인 후 활성화 (placeholder: "지방세 관련 질문을 입력하세요...")
- [x] Enter로 전송, Shift+Enter로 줄바꿈
- [x] 전송 중 입력창 비활성화 + 로딩 표시
- [x] `useSSE.js` 커스텀 훅 구현 (fetch + ReadableStream으로 SSE 파싱)
- [x] `MSW handlers.js`에 Mock SSE 응답 구현 (stage_change → token 스트리밍 → sources → done)
- [x] `StreamingResponse.jsx` 구현 (토큰 단위 실시간 렌더링)
- [x] `StatusStepper.jsx` 구현 (4단계: 웹검색 → 초안작성 → 검증 → 완료)

### ✅ 3단계 확인사항
- [ ] 로그인 전 채팅 입력창에 "GPKI 인증 후 이용 가능합니다"가 표시되고 비활성인가?
- [ ] 로그인 후 "지방세 관련 질문을 입력하세요..."로 변경되고 활성화되는가?
- [ ] "취득세 감면 대상" 입력 후 Enter → 사용자 메시지가 오른쪽 파란 배경으로 표시되는가?
- [ ] `StatusStepper`가 "웹 검색 중" → "초안 작성 중" → "검증 중" → "답변 완료" 순서로 전환되는가?
- [ ] AI 답변이 글자 단위로 스트리밍되어 실시간 표시되는가?
- [ ] AI 답변에 Markdown (##, **, 표, > 인용) 이 정상 렌더링되는가?
- [ ] 전송 중 입력창이 비활성화되고, 완료 후 다시 활성화되는가?
- [ ] 메시지가 많아지면 자동으로 스크롤이 하단으로 이동하는가?

📋 3단계 테스트 결과: 코드 구현 완료. 브라우저 수동 테스트는 미실행.

---

## 📄 4단계: 미리보기 패널 + 출처 연동
- [x] `PreviewPanel.jsx` 구현 (오른쪽 50% 영역, 상태별 분기 표시)
- [x] 채팅 전 안내 문구 표시
- [x] 검색 중 스켈레톤 로딩 UI 표시
- [x] 결과 있음 시 `SourceCard` 목록 표시
- [x] 결과 없음 시 "관련 출처를 찾지 못했습니다" 표시
- [x] `SourceCard.jsx` 구현 (제목, 유형 배지, 미리보기 텍스트 2줄)
- [x] 유형 배지 색상 적용: 법령(파랑), 해석례(초록), 판례(보라), 훈령(주황)
- [x] 클릭 시 `chatStore.selectSource(sourceId)` 호출
- [x] `SourceDetail.jsx` 구현 (전체 내용 표시, 원문 바로가기 링크, 닫기 버튼)
- [x] 채팅 응답의 `sources` 이벤트 수신 시 `PreviewPanel`에 출처 카드 자동 표시
- [x] 출처 카드 클릭 → `SourceDetail` 표시 → 닫기 → 카드 목록 복귀

### ✅ 4단계 확인사항
- [ ] 로그인 직후 오른쪽 패널에 "질문을 입력하면..." 안내 문구가 보이는가?
- [ ] 질문 전송 시 오른쪽 패널에 스켈레톤 로딩이 표시되는가?
- [ ] 답변 완료 후 출처 카드가 2개 표시되는가? (취득세 감면 질문 시)
- [ ] 출처 카드에 "법령" 배지가 파란색으로 표시되는가?
- [ ] 출처 카드 클릭 시 상세 내용 (법령 전문)이 표시되는가?
- [ ] "원문 바로가기" 클릭 시 `olta.re.kr` URL이 새 탭에서 열리는가?
- [ ] 상세에서 "닫기" 클릭 시 카드 목록으로 돌아가는가?
- [ ] "재산세 납부 기한" 질문 시 출처 카드가 1개로 업데이트되는가?

📋 4단계 테스트 결과: 코드 구현 완료. 브라우저 수동 테스트는 미실행.

---

## 🧪 5단계: 통합 테스트 + 최종 검증
- [x] 전체 UI 디자인 점검 및 미세 조정
- [x] 좌우 패널 높이가 화면에 맞게 꽉 차도록 유지 (`h-screen`)
- [x] 스크롤이 각 패널 내부에서만 동작하도록 유지
- [x] 데스크톱 최소 너비(1024px) 기준 레이아웃 유지
- [x] 연속 질문 시나리오 지원
- [x] 미등록 질문 기본 응답 처리
- [x] 네트워크 에러 메시지 처리
- [x] `beforeunload` 이벤트로 탭 닫기 시 로그아웃 호출 연결
- [x] 빌드 테스트 준비
- [ ] OLTA 로그인 테스트 (수동)

### ✅ 5단계 최종 확인사항 (전체 플로우)
- [ ] APP 실행 → GPKI 모달 표시
- [ ] 실제 인증서 선택 + 실제 비밀번호 입력 → 로그인 성공 → 모달 닫힘
- [ ] 상단 바에 "<실제 소유자명>님" + "로그아웃" 버튼 표시
- [ ] 채팅창 활성화, "지방세 관련 질문을 입력하세요..." placeholder
- [ ] "취득세 감면 대상" 입력 → Enter
- [ ] `StatusStepper`: 웹 검색 → 초안 작성 → 검증 → 완료 순서 전환
- [ ] AI 답변이 글자 단위로 스트리밍 표시
- [ ] 답변에 Markdown 서식 (제목, 볼드, 표, 인용) 정상 렌더링
- [ ] 오른쪽 패널에 출처 카드 2개 표시
- [ ] 출처 카드 클릭 → 상세 내용 + "원문 바로가기" 링크
- [ ] "재산세 납부 기한" 두 번째 질문 → 이전 대화 유지 + 새 답변 + 출처 업데이트
- [ ] "로그아웃" 클릭 → 대화 초기화 + GPKI 모달 재표시
- [ ] `www.olta.re.kr`에 실제 GPKI 인증서로 로그인 성공 확인
- [ ] `npm run build` 성공

📋 5단계 테스트 결과: 코드 수정 완료. 실제 인증서/브라우저 수동 테스트 및 OLTA 로그인 테스트는 환경 제약으로 미실행.
