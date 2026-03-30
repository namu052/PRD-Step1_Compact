# AI 지방세 지식인 APP - Step 3 Todolist (검증 파이프라인)

## 🔧 1단계: 검증 데이터 모델 + 디렉토리 구조
- [x] backend/app/services/verification/ 디렉토리 생성 + __init__.py
- [x] backend/app/models/verification.py 구현
- [x] backend/app/prompts/stage2_source_prompt.py 생성
- [x] backend/app/prompts/stage2_content_prompt.py 생성
- [x] backend/app/prompts/stage2_final_prompt.py 생성
- [x] 테스트용 가상 데이터 생성: tests/mocks/mock_drafts.py

### ✅ 1단계 확인사항
- [x] `python -c "from app.models.verification import SourceVerification, ContentClaim, VerificationResult, FinalAnswer; print('OK')"` → OK?
- [x] 모든 데이터클래스가 인스턴스 생성 가능한가?
- [x] mock_drafts.py에서 3종류의 테스트 초안을 import 가능한가?

📋 1단계 테스트 결과: `uv run python -c ...` 2회 실행으로 verification 모델 import 및 `mock_drafts.py` import 모두 `OK` 확인.

---

## 🔍 2단계: 출처 검증기 + 내용 검증기 (Mock 규칙 기반)
- [x] source_verifier.py 구현
- [x] content_verifier.py 구현
- [x] pytest 테스트 작성

### ✅ 2단계 확인사항
- [x] `pytest tests/test_source_verifier.py -v` → 모든 테스트 통과?
- [x] `pytest tests/test_content_verifier.py -v` → 모든 테스트 통과?
- [x] 정상 초안 + 정상 크롤링 데이터 → 모든 출처 "verified"?
- [x] 할루시네이션 초안 (src_999) → 해당 출처 "not_found"?
- [x] "지방세법 제999조" 주장 → "hallucinated" 또는 "unsupported"?
- [x] 부분 일치 주장 → "partial" + corrected_text 제안?

📋 2단계 테스트 결과: `uv run pytest tests/test_source_verifier.py tests/test_content_verifier.py -v` 통과. `src_999`는 `not_found`, 허위 조문 주장은 `hallucinated`, 약한 문장은 `partial`로 분류됨.

---

## 📊 3단계: 검증 결과 통합기 + 신뢰도 산출
- [x] verification_aggregator.py 구현
- [x] pytest 테스트 작성

### ✅ 3단계 확인사항
- [x] `pytest tests/test_aggregator.py -v` → 모든 테스트 통과?
- [x] 정상 초안 → overall_confidence 0.7 이상 + confidence_label "높음"?
- [x] 할루시네이션 포함 초안 → overall_confidence 0.4~0.7 + confidence_label "보통"?
- [x] 전체 오류 초안 → overall_confidence 0.4 미만 + confidence_label "낮음"?
- [x] not_found 출처 인용 주장이 confidence × 0.3으로 보정되었는가?
- [x] 제거/수정 목록이 정확하게 생성되었는가?

📋 3단계 테스트 결과: `uv run pytest tests/test_aggregator.py -v` 통과. 보정 계수 적용, 제거 목록/수정 목록 생성, confidence label 분기 확인.

---

## 💬 4단계: 최종 답변 생성 + chat.py SSE 파이프라인 수정
- [x] final_generator.py 구현
- [x] chat.py 수정
- [x] pytest 테스트 작성/수정

### ✅ 4단계 확인사항
- [x] `pytest tests/test_final_generator.py -v` → 모든 테스트 통과?
- [x] `pytest tests/test_verification_pipeline.py -v` → 모든 시나리오 통과?
- [x] `pytest tests/test_chat_pipeline.py -v` → SSE에 verifying + finalizing 단계 포함?
- [x] curl SSE 테스트 → verifying + finalizing + confidence 포함?
- [x] sources 이벤트에 confidence 포함?
- [x] 검증 실패 에러 시 1단계 초안 + 경고 메시지가 정상 반환?

📋 4단계 테스트 결과: `uv run pytest tests/test_final_generator.py tests/test_verification_pipeline.py tests/test_chat_pipeline.py -v` 통과. curl SSE에서 `crawling → drafting → token → verifying → finalizing → token → sources(confidence 포함) → done` 확인.

---

## 🔗 5단계: 프론트엔드 연동 + 전체 통합 테스트
- [x] StatusStepper 5단계 확장
- [x] ConfidenceBadge 추가
- [x] chatStore 수정
- [x] 프론트엔드 + 백엔드 통합 시나리오 테스트
- [x] 전체 pytest 실행
- [x] 프론트엔드 빌드

### ✅ 5단계 최종 확인사항 (전체 통합 플로우)
- [x] 백엔드 실행
- [x] 프론트엔드 실행
- [ ] 브라우저 접속 후 5단계 스테퍼/신뢰도 확인
- [x] `pytest tests/ -k "not e2e" -v` 통과
- [x] `cd frontend && npm run build` 통과

📋 5단계 테스트 결과: 백엔드 `http://127.0.0.1:8000`, 프론트 `http://127.0.0.1:5173` 동시 실행 확인. 프론트 proxy 경유 `/api/chat`에서 5단계 SSE와 `confidence` 포함 응답 확인. 브라우저 수동 확인만 미실행.
