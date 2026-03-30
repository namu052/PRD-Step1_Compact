# AI 지방세 지식인 APP - Step 2 Todolist (Backend)

## 🔧 1단계: FastAPI 프로젝트 초기화 + 환경 설정
- [x] backend/ 디렉토리 구조 생성
- [x] requirements.txt 작성 및 의존성 설치
- [x] Playwright chromium 설치
- [x] .env.example 및 .env 파일 생성
- [x] config.py 구현 (환경변수 로드, OLTA Selector 분리, Mock 모드 플래그)
- [x] main.py 구현 (FastAPI 앱, CORS 설정, 라우터 등록, 시작/종료 이벤트)
- [x] schemas.py 구현 (Pydantic 모델: AuthRequest, AuthResponse, ChatRequest, SourceResponse 등)
- [x] event_emitter.py 구현 (SSE 이벤트 포맷팅 유틸리티)
- [x] 가상 데이터 파일 생성 (tests/mocks/mock_olta_pages.json)

### ✅ 1단계 확인사항
- [x] `cd backend && uvicorn app.main:app --reload` 실행 시 에러 없이 서버 기동?
- [x] 브라우저에서 `http://localhost:8000/docs` 접속 시 Swagger UI 표시?
- [x] `curl http://localhost:8000/health` → `{"status":"ok"}` 응답?

📋 1단계 테스트 결과: `uv run uvicorn app.main:app --port 8000` 기동 성공. `/docs` HTML 확인, `/health` 응답 `{"status":"ok"}` 확인.

---

## 🔐 2단계: 인증 API + 세션 관리 (Mock 모드)
- [x] session.py 모델 구현 (Session 클래스: session_id, user_name, created_at, last_active, crawl_cache)
- [x] session_manager.py 구현
- [x] security.py 구현 (비밀번호 메모리 즉시 삭제 유틸리티)
- [x] auth.py 라우터 구현
- [x] gpki_service.py 구현 (Mock 모드 분기 포함, 실제 Playwright 로직은 껍데기만)
- [x] 세션 미들웨어 또는 의존성 주입: /api/chat, /api/preview 요청 시 session_id 검증

### ✅ 2단계 확인사항
- [x] `curl -X GET http://localhost:8000/api/auth/certs` → 인증서 2건 반환?
- [x] `curl -X POST http://localhost:8000/api/auth/gpki -H "Content-Type: application/json" -d '{"cert_id":"cert_001","password":"test1234"}'` → 성공 응답?
- [x] 잘못된 비밀번호 → 실패 응답?
- [x] 로그인 후 받은 session_id로 로그아웃 → `{"success":true}` ?
- [x] 로그아웃 후 해당 session_id로 다른 API 호출 시 401 에러?

📋 2단계 테스트 결과: 인증서 2건 반환 확인. 정상 로그인 시 `session_id` 발급, 잘못된 비밀번호 시 `"비밀번호가 일치하지 않습니다"` 반환, 로그아웃 후 `/api/chat` 401 확인.

---

## 🔍 3단계: 크롤링 엔진 + 키워드 추출 (Mock 모드)
- [x] mock_crawler.py 구현 (mock_olta_pages.json 기반 가상 크롤링 결과 반환)
- [x] mock_llm.py 구현 (가상 키워드 추출 및 답변 생성)
- [x] CrawlResult 데이터 클래스 정의 (id, title, type, content, preview, url, relevance_score, crawled_at)
- [x] search_service.py 구현
- [x] crawler_service.py 구현
- [x] embedding_service.py 구현
- [x] pytest 테스트 작성

### ✅ 3단계 확인사항
- [x] `USE_MOCK_CRAWLER=true pytest tests/test_search.py -v` → 키워드 추출 테스트 통과?
- [x] `USE_MOCK_CRAWLER=true pytest tests/test_crawler.py -v` → Mock 크롤링 테스트 통과?
- [x] Mock 크롤러에 "취득세 감면" 쿼리 → mock_law_001, mock_law_002, mock_interp_001 3건 반환?
- [x] Mock 크롤러에 "재산세 납부" 쿼리 → mock_law_003 1건 반환?
- [x] 존재하지 않는 키워드 → 빈 리스트 반환?

📋 3단계 테스트 결과: `uv run pytest tests/test_search.py tests/test_crawler.py -v` 통과. 키워드 추출과 Mock 크롤링 결과가 기대값과 일치.

---

## 💬 4단계: LLM 파이프라인 + SSE 채팅 API (Mock 모드)
- [x] stage1_prompt.py 구현 (1단계 시스템 프롬프트 + 사용자 프롬프트 템플릿)
- [x] llm_service.py 구현
- [x] chat.py 라우터 구현
- [x] pytest 테스트 작성

### ✅ 4단계 확인사항
- [x] `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/test_chat_pipeline.py -v` → 모든 테스트 통과?
- [x] curl로 SSE 스트리밍 테스트 순서 확인?
- [x] 존재하지 않는 session_id로 /api/chat 호출 → 401 에러?
- [x] /api/preview/{source_id} → 올바른 출처 내용 반환?
- [x] 매칭 안 되는 질문 → "관련 자료를 찾지 못했습니다" 메시지 포함 답변?

📋 4단계 테스트 결과: `uv run pytest tests/test_chat_pipeline.py -v` 포함 전체 10개 테스트 통과. curl SSE에서 `stage_change(crawling) → stage_change(drafting) → token → sources → stage_change(done)` 순서 확인. `/api/preview/mock_law_003` 정상 반환 확인.

---

## 🔗 5단계: 프론트엔드 연동 + 통합 테스트
- [x] Step 1 프론트엔드에서 MSW 비활성화 (또는 환경변수로 분기)
- [x] vite.config.js에 proxy 설정: `/api` → `http://localhost:8000`
- [x] 프론트엔드 + 백엔드 동시 실행 테스트
- [ ] 시나리오 테스트 및 에러 처리 점검
- [x] `npm run build` (프론트엔드 빌드) 에러 없는지 확인

### ✅ 5단계 최종 확인사항 (전체 통합 플로우)
- [x] 백엔드 실행
- [x] 프론트엔드 실행
- [ ] 브라우저 통합 플로우 확인
- [x] 모든 pytest 테스트 통과

📋 5단계 테스트 결과: 프론트 dev server `http://127.0.0.1:5173`와 백엔드 `http://127.0.0.1:8000` 동시 실행 확인. 프론트 proxy 경유 `/api/auth/certs`, `/api/auth/gpki`, `/api/chat`, `/api/preview` 응답 확인. 현재 프론트는 사용자 요청으로 GPKI 로그인 UI를 제거하고 내부 세션 bootstrap 방식으로 연동되어 있어, 브라우저 수동 플로우 체크는 별도 미실행.
