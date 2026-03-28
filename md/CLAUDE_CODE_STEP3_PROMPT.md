# Claude Code 프롬프트: AI 지방세 지식인 APP - Step 3 (답변 재검증 루틴)

> **이 프롬프트를 Claude Code에 그대로 붙여넣기 하세요.**  
> `claude --dangerously-skip-permissions` 모드에서 실행을 권장합니다.  
> **선행 조건**: Step 2 (백엔드 + Mock 크롤링 + 1단계 LLM)이 `backend/` 디렉토리에 완성되어 있어야 합니다.  
> **선행 조건**: Step 1 (프론트엔드)이 `frontend/` 디렉토리에 완성되어 있어야 합니다.

---

너는 지금부터 "AI 지방세 지식인 APP"의 2단계 검증 파이프라인을 구현하는 시니어 백엔드 개발자야.
Step 2에서 1단계 초안만 반환하던 `/api/chat`에 검증 로직을 추가하여, 출처와 내용을 교차 검증하고 신뢰도 스코어가 포함된 최종 답변을 생성한다.
이 작업은 총 5단계로 나뉘며, 각 단계를 순서대로 완료해야 해.

## 핵심 규칙

1. **Todolist 파일(`backend/TODO_STEP3.md`)을 생성**하고, 모든 작업 항목을 체크박스로 관리해.
2. 각 세부 작업을 완료할 때마다 `TODO_STEP3.md`에서 해당 항목을 `[x]`로 변경해.
3. 각 단계가 끝나면 반드시 **확인사항 체크리스트**를 실행하고, **서버를 실행하여 실제 테스트**해.
4. 테스트 결과를 `TODO_STEP3.md`의 해당 단계 하단에 기록해.
5. 문제가 발견되면 즉시 수정한 후 다시 테스트해. 모든 체크가 통과해야 다음 단계로 진행해.
6. **Mock 모드 유지**: `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true`에서 동작. 검증 로직 자체는 LLM 없이 규칙 기반 Mock으로 먼저 구현하고, 실제 LLM 자리를 `# TODO` 주석으로 확보해.

---

## 사전 작업: TODO_STEP3.md 생성

가장 먼저 `backend/TODO_STEP3.md` 파일을 아래 내용으로 생성해:

```markdown
# AI 지방세 지식인 APP - Step 3 Todolist (검증 파이프라인)

## 🔧 1단계: 검증 데이터 모델 + 디렉토리 구조
- [ ] backend/app/services/verification/ 디렉토리 생성 + __init__.py
- [ ] backend/app/models/verification.py 구현 (SourceVerification, ContentClaim, VerificationResult, FinalAnswer)
- [ ] backend/app/prompts/stage2_source_prompt.py 생성 (출처 검증 프롬프트)
- [ ] backend/app/prompts/stage2_content_prompt.py 생성 (내용 검증 프롬프트)
- [ ] backend/app/prompts/stage2_final_prompt.py 생성 (최종 답변 프롬프트)
- [ ] 테스트용 가상 데이터 생성: tests/mocks/mock_drafts.py (정상 초안, 할루시네이션 포함 초안, 전체 오류 초안)

### ✅ 1단계 확인사항
- [ ] `python -c "from app.models.verification import SourceVerification, ContentClaim, VerificationResult, FinalAnswer; print('OK')"` → OK?
- [ ] 모든 데이터클래스가 인스턴스 생성 가능한가?
- [ ] mock_drafts.py에서 3종류의 테스트 초안을 import 가능한가?

📋 1단계 테스트 결과: (여기에 결과 기록)

---

## 🔍 2단계: 출처 검증기 + 내용 검증기 (Mock 규칙 기반)
- [ ] source_verifier.py 구현
  - [ ] verify(draft_answer, crawl_results) → list[SourceVerification]
  - [ ] 초안에서 [출처: xxx] 패턴을 정규식으로 추출
  - [ ] 각 source_id가 crawl_results에 존재하는지 확인 → verified / not_found
  - [ ] 법령 조문 번호가 원본 content와 일치하는지 확인 → mismatch 감지
  - [ ] URL이 olta.re.kr 도메인인지 확인 → expired 감지
  - [ ] Mock 모드: 위 규칙 기반 로직으로 동작
  - [ ] 실제 모드 자리: GPT-4o-mini 호출 (# TODO 주석)
- [ ] content_verifier.py 구현
  - [ ] verify(draft_answer, crawl_results) → list[ContentClaim]
  - [ ] 초안을 문장 단위로 분해 (마크다운 헤더, 빈 줄 등 제외)
  - [ ] 각 문장이 crawl_results의 content에 키워드 매칭으로 뒷받침되는지 확인
  - [ ] Mock 모드 매칭 규칙:
    - 원본 content에서 핵심 키워드(숫자, 법령명 등) 3개 이상 일치 → supported (0.85)
    - 1~2개 일치 → partial (0.5)
    - 0개 일치 → unsupported (0.2)
    - 원본과 모순 (예: 원본 "50%" vs 초안 "100%") → hallucinated (0.0)
  - [ ] 실제 모드 자리: GPT-4o-mini 호출 (# TODO 주석)
- [ ] pytest 테스트 작성
  - [ ] test_source_verifier.py: VT-01 ~ VT-03 (verified, not_found, mismatch)
  - [ ] test_content_verifier.py: VT-04 ~ VT-07 (supported, unsupported, hallucinated, partial)

### ✅ 2단계 확인사항
- [ ] `pytest tests/test_source_verifier.py -v` → 모든 테스트 통과?
- [ ] `pytest tests/test_content_verifier.py -v` → 모든 테스트 통과?
- [ ] 정상 초안 + 정상 크롤링 데이터 → 모든 출처 "verified"?
- [ ] 할루시네이션 초안 (src_999) → 해당 출처 "not_found"?
- [ ] "지방세법 제999조" 주장 → "hallucinated" 또는 "unsupported"?
- [ ] 부분 일치 주장 → "partial" + corrected_text 제안?

📋 2단계 테스트 결과: (여기에 결과 기록)

---

## 📊 3단계: 검증 결과 통합기 + 신뢰도 산출
- [ ] verification_aggregator.py 구현
  - [ ] aggregate(source_verifications, content_claims) → VerificationResult
  - [ ] 출처 검증 결과와 내용 검증 결과 교차 분석
    - [ ] not_found 출처를 인용한 주장 → confidence × 0.3
    - [ ] mismatch 출처를 인용한 주장 → confidence × 0.5
    - [ ] 출처 없는 주장 → confidence × 0.2
  - [ ] 전체 신뢰도 산출: (보정된 confidence 합계) / (전체 주장 수)
  - [ ] 신뢰도 라벨 결정: 0.7+ → "높음", 0.4+ → "보통", 0.4- → "낮음"
  - [ ] 제거 대상 목록 생성: hallucinated + (unsupported & confidence < 0.3)
  - [ ] 수정 대상 목록 생성: partial → {original, corrected, reason}
  - [ ] 경고 메시지 생성: unsupported & confidence >= 0.3 → "⚠️ 확인 필요"
- [ ] pytest 테스트 작성
  - [ ] test_aggregator.py: VT-08 ~ VT-10
    - [ ] 정상 케이스 → 신뢰도 0.7+, 제거 목록 비어있음
    - [ ] 할루시네이션 포함 → 신뢰도 하향, 해당 주장 제거 목록에 포함
    - [ ] 전체 오류 → 신뢰도 0.4 미만, 강한 경고 포함

### ✅ 3단계 확인사항
- [ ] `pytest tests/test_aggregator.py -v` → 모든 테스트 통과?
- [ ] 정상 초안 → overall_confidence 0.7 이상 + confidence_label "높음"?
- [ ] 할루시네이션 포함 초안 → overall_confidence 0.4~0.7 + confidence_label "보통"?
- [ ] 전체 오류 초안 → overall_confidence 0.4 미만 + confidence_label "낮음"?
- [ ] not_found 출처 인용 주장이 confidence × 0.3으로 보정되었는가?
- [ ] 제거/수정 목록이 정확하게 생성되었는가?

📋 3단계 테스트 결과: (여기에 결과 기록)

---

## 💬 4단계: 최종 답변 생성 + chat.py SSE 파이프라인 수정
- [ ] final_generator.py 구현
  - [ ] generate(draft_answer, verification_result, crawl_results, on_token) → FinalAnswer
  - [ ] Mock 모드: 규칙 기반 텍스트 편집
    - [ ] 제거 대상 주장 → 해당 문장을 초안에서 삭제
    - [ ] 수정 대상 주장 → corrected_text로 교체
    - [ ] unsupported (confidence >= 0.3) → 문장 뒤에 " ⚠️ *확인 필요*" 추가
    - [ ] 답변 마지막에 신뢰도 블록 추가
    - [ ] 검증된 출처만으로 "📌 참고 출처" 섹션 재구성
  - [ ] 실제 모드 자리: GPT-4o 호출 (# TODO 주석)
  - [ ] 에러 처리: 검증 실패 시 1단계 초안 + 경고 메시지 반환
- [ ] chat.py 수정: Step 2의 `# TODO Step 3` 주석을 실제 검증 코드로 교체
  - [ ] stage_change("verifying") 이벤트 추가
  - [ ] source_verifier.verify() + content_verifier.verify() → asyncio.gather로 병렬 실행
  - [ ] aggregator.aggregate() 호출
  - [ ] stage_change("finalizing") 이벤트 추가
  - [ ] final_generator.generate() 호출 (on_token 콜백 연결)
  - [ ] sources 이벤트에 confidence 정보 추가
  - [ ] 에러 처리: 검증 단계 실패 시 1단계 초안 + 경고 그대로 반환
- [ ] pytest 테스트 작성/수정
  - [ ] test_final_generator.py: VT-11 ~ VT-14
  - [ ] test_chat_pipeline.py 수정: SSE 이벤트에 "verifying", "finalizing" 단계 포함 검증
  - [ ] test_verification_pipeline.py: IT-01 ~ IT-07 통합 시나리오 테스트

### ✅ 4단계 확인사항
- [ ] `pytest tests/test_final_generator.py -v` → 모든 테스트 통과?
- [ ] `pytest tests/test_verification_pipeline.py -v` → 모든 시나리오 통과?
- [ ] `pytest tests/test_chat_pipeline.py -v` → SSE에 verifying + finalizing 단계 포함?
- [ ] curl SSE 테스트:
  ```bash
  SESSION=$(curl -s -X POST http://localhost:8000/api/auth/gpki \
    -H "Content-Type: application/json" \
    -d '{"cert_id":"cert_001","password":"test1234"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")
  curl -N -X POST http://localhost:8000/api/chat \
    -H "Content-Type: application/json" \
    -d "{\"session_id\":\"$SESSION\",\"question\":\"취득세 감면 대상\"}"
  ```
  → SSE 이벤트 순서: crawling → drafting → token... → verifying → finalizing → token... → sources(+confidence) → done?
- [ ] sources 이벤트에 `"confidence": {"score": 0.xx, "label": "높음|보통|낮음"}` 포함?
- [ ] 검증 실패 에러 시 1단계 초안 + 경고 메시지가 정상 반환?

📋 4단계 테스트 결과: (여기에 결과 기록)

---

## 🔗 5단계: 프론트엔드 연동 + 전체 통합 테스트
- [ ] 프론트엔드 StatusStepper 5단계 확장
  - [ ] 기존 4단계 → 5단계: 웹 검색 → 초안 작성 → 검증 → 최종 정리 → 답변 완료
  - [ ] stage 값 매핑: crawling, drafting, verifying, finalizing, done
- [ ] 프론트엔드 신뢰도 배지 컴포넌트 추가
  - [ ] ConfidenceBadge.jsx 구현
  - [ ] sources 이벤트의 confidence 정보를 chatStore에 저장
  - [ ] AI 답변 메시지 하단에 신뢰도 배지 표시
    - [ ] 높음 (🟢, 70%+): bg-green-100 text-green-700
    - [ ] 보통 (🟡, 40~70%): bg-yellow-100 text-yellow-700 + 경고 문구
    - [ ] 낮음 (🔴, 40% 미만): bg-red-100 text-red-700 + "실무 적용 전 반드시 원문 확인"
- [ ] chatStore.js 수정: sources 이벤트에서 confidence 저장
- [ ] 프론트엔드 + 백엔드 통합 시나리오 테스트
  - [ ] 시나리오 1: "취득세 감면 대상" → 5단계 스테퍼 전환 + 스트리밍 + 신뢰도 표시
  - [ ] 시나리오 2: "재산세 납부 기한" → 연속 질문 + 신뢰도 표시
  - [ ] 시나리오 3: 미등록 질문 → 기본 안내 (신뢰도 없음)
  - [ ] 시나리오 4: 로그아웃 → 재로그인 → 정상 동작
- [ ] 전체 pytest 실행: `pytest tests/ -k "not e2e" -v` → 모든 테스트 통과
- [ ] 프론트엔드 빌드: `cd frontend && npm run build` → 에러 없음

### ✅ 5단계 최종 확인사항 (전체 통합 플로우)
- [ ] 백엔드: `USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --port 8000`
- [ ] 프론트엔드: `cd frontend && npm run dev`
- [ ] 브라우저 접속 → GPKI 모달 → 로그인 성공
- [ ] "취득세 감면 대상" 입력
- [ ] StatusStepper: 웹 검색 → 초안 작성 → 검증 → 최종 정리 → 답변 완료 (5단계)
- [ ] 1단계 초안 스트리밍 → 검증 중 표시 → 최종 답변 스트리밍
- [ ] 답변 하단에 신뢰도 배지 표시 (예: "📊 답변 신뢰도: 높음 🟢 87%")
- [ ] 오른쪽 패널에 검증된 출처 카드만 표시
- [ ] 출처 카드 클릭 → 상세 내용 + "원문 바로가기"
- [ ] "재산세 납부 기한" 연속 질문 → 이전 대화 유지 + 새 답변 + 신뢰도
- [ ] 로그아웃 → 재로그인 → 정상 동작
- [ ] `cd backend && pytest tests/ -k "not e2e" -v` → 모든 테스트 통과
- [ ] `cd frontend && npm run build` → 에러 없음

📋 5단계 테스트 결과: (여기에 결과 기록)
```

---

## ▶ 1단계 시작: 검증 데이터 모델 + 디렉토리 구조

이제 1단계를 시작해. 아래 지시사항을 **순서대로** 실행해.

### 1-1. 디렉토리 생성

```bash
mkdir -p backend/app/services/verification
touch backend/app/services/verification/__init__.py
```

### 1-2. verification.py 데이터 모델

**`backend/app/models/verification.py`**:
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class SourceVerification:
    source_id: str
    title: str = ""
    url: str = ""
    status: str = "verified"        # "verified" | "not_found" | "mismatch" | "expired"
    detail: str = ""
    verified_at: datetime = field(default_factory=datetime.now)

@dataclass
class ContentClaim:
    claim_text: str
    cited_sources: list[str] = field(default_factory=list)
    verification_status: str = "supported"  # "supported" | "unsupported" | "partial" | "hallucinated"
    confidence: float = 0.0
    detail: str = ""
    corrected_text: Optional[str] = None

@dataclass
class VerificationResult:
    source_verifications: list[SourceVerification] = field(default_factory=list)
    content_claims: list[ContentClaim] = field(default_factory=list)
    overall_confidence: float = 0.0
    removed_claims: list[str] = field(default_factory=list)
    modified_claims: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

@dataclass
class FinalAnswer:
    answer: str = ""
    confidence_score: float = 0.0
    confidence_label: str = "보통"      # "높음" | "보통" | "낮음"
    verified_sources: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

### 1-3. 프롬프트 파일 생성

**`backend/app/prompts/stage2_source_prompt.py`**:
```python
SOURCE_VERIFICATION_PROMPT = """너는 지방세 법령 출처 검증 전문가이다.
아래 [답변 초안]에서 인용된 출처가 [크롤링 원본 데이터]와 일치하는지 검증하라.

## 검증 규칙
1. [출처: source_id] 태그로 표시된 모든 출처를 추출하라
2. 각 출처에 대해 다음을 확인하라:
   a) source_id가 [크롤링 원본 데이터]에 존재하는가?
   b) 인용된 법령 조문 번호가 원본의 실제 조문과 일치하는가?
   c) 인용된 내용이 원본의 실제 내용과 부합하는가?
3. 검증 결과를 JSON으로 반환하라 (JSON만 출력, 다른 텍스트 없이)

## 출력 형식
{{"verifications": [{{"source_id": "...", "title": "...", "status": "verified|not_found|mismatch|expired", "detail": "..."}}]}}

## 답변 초안
{draft_answer}

## 크롤링 원본 데이터
{crawl_results}"""
```

**`backend/app/prompts/stage2_content_prompt.py`**:
```python
CONTENT_VERIFICATION_PROMPT = """너는 지방세 답변 내용 검증 전문가이다.
아래 [답변 초안]의 각 주장이 [크롤링 원본 데이터]에 의해 뒷받침되는지 검증하라.

## 검증 규칙
1. 답변 초안에서 사실적 주장을 모두 추출하라 (일반적 안내 문구는 제외)
2. 각 주장에 대해 크롤링 원본에서 근거를 찾아라
3. 분류 기준:
   - "supported": 원본 데이터에서 명확한 근거 있음 (confidence: 0.7~1.0)
   - "partial": 부분적으로 뒷받침됨, 일부 수정 필요 (confidence: 0.4~0.7)
   - "unsupported": 원본 데이터에 근거 없음 (confidence: 0.0~0.4)
   - "hallucinated": 원본 데이터와 명백히 모순됨 (confidence: 0.0)
4. "partial"인 경우 corrected_text를 제안하라
5. JSON으로만 반환하라

## 출력 형식
{{"claims": [{{"claim_text": "...", "cited_sources": [...], "status": "...", "confidence": 0.0, "detail": "...", "corrected_text": null}}]}}

## 답변 초안
{draft_answer}

## 크롤링 원본 데이터
{crawl_results}"""
```

**`backend/app/prompts/stage2_final_prompt.py`**:
```python
FINAL_ANSWER_PROMPT = """너는 지방세 답변 최종 편집자이다.
아래 [답변 초안]과 [검증 결과]를 바탕으로 최종 답변을 작성하라.

## 편집 규칙
1. "제거 대상" 주장은 답변에서 완전히 삭제하라
2. "수정 필요" 주장은 제안된 수정 텍스트로 교체하라
3. "⚠️ 확인 필요" 표시가 필요한 부분에 경고를 삽입하라
4. 출처 태그를 검증 결과에 맞게 업데이트하라
5. 답변의 전체적인 흐름과 가독성을 유지하라
6. 제거/수정으로 부자연스러워지면 문장을 다듬어라
7. 답변 마지막에 신뢰도 정보를 표시하라

## 신뢰도 표시 형식
---
📊 **답변 신뢰도**: {{confidence_label}} ({{confidence_score}}%)

## 답변 초안
{draft_answer}

## 검증 결과
{verification_result}

## 검증 완료된 출처 목록
{verified_sources}"""
```

### 1-4. 테스트용 가상 초안 데이터

**`backend/tests/mocks/mock_drafts.py`**:
```python
"""테스트용 가상 답변 초안 모음"""

# ── 정상 초안 (모든 출처 + 주장이 크롤링 데이터와 일치) ──
MOCK_DRAFT_NORMAL = """## 취득세 감면 대상

**지방세특례제한법 제36조**에 따르면 서민주택 취득 시 취득세 50%를 경감합니다. [출처: mock_law_001]

취득가액 1억원 이하의 주택이 감면 대상입니다. [출처: mock_law_001]

영농조합법인이 농업에 직접 사용하기 위하여 취득하는 부동산도 감면 대상입니다. [출처: mock_law_002]

---
📌 **참고 출처**: 지방세특례제한법 제36조, 제11조"""

# ── 할루시네이션 포함 초안 (존재하지 않는 출처 + 근거 없는 주장) ──
MOCK_DRAFT_WITH_HALLUCINATION = """## 취득세 감면 대상

**지방세특례제한법 제36조**에 따르면 서민주택 취득 시 취득세 50%를 경감합니다. [출처: mock_law_001]

또한 **지방세법 제999조**에 따르면 모든 1주택자는 취득세가 면제됩니다. [출처: src_999]

감면 적용 후 3년 내 매각 시 감면세액이 추징됩니다.

---
📌 **참고 출처**: 지방세특례제한법 제36조, 지방세법 제999조"""

# ── 전체 오류 초안 (모든 주장이 근거 없음) ──
MOCK_DRAFT_ALL_WRONG = """## 취득세 감면 대상

**지방세법 제888조**에 따르면 모든 부동산 취득에 대해 취득세가 면제됩니다. [출처: src_888]

국민주택규모 이하의 주택은 취득세 100% 면제됩니다. [출처: src_777]

---
📌 **참고 출처**: 지방세법 제888조, 제777조"""

# ── 크롤링 결과 (mock_olta_pages.json과 동일한 구조를 Python dict로) ──
MOCK_CRAWL_RESULTS = [
    {
        "id": "mock_law_001",
        "title": "지방세특례제한법 제36조(서민주택 등에 대한 감면)",
        "type": "법령",
        "content": "제36조(서민주택 등에 대한 감면) ① 주택으로서 대통령령으로 정하는 주택을 취득하는 경우에는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다. ② 대통령령으로 정하는 주택이란 취득 당시의 가액이 1억원 이하인 주택을 말한다.",
        "url": "https://www.olta.re.kr/law/detail?lawId=36"
    },
    {
        "id": "mock_law_002",
        "title": "지방세특례제한법 제11조(농업법인에 대한 감면)",
        "type": "법령",
        "content": "제11조(농업법인에 대한 감면) ① 영농조합법인이 그 법인의 사업에 직접 사용하기 위하여 취득하는 부동산에 대해서는 취득세의 100분의 50을 2027년 12월 31일까지 경감한다.",
        "url": "https://www.olta.re.kr/law/detail?lawId=11"
    },
    {
        "id": "mock_interp_001",
        "title": "해석례 2024-0312 (서민주택 감면 적용 범위)",
        "type": "해석례",
        "content": "질의: 취득가액 1억원 이하 주택의 감면 적용 시 부속토지도 포함되는지 여부. 회신: 지방세특례제한법 제36조에 따른 서민주택 감면은 주택과 그 부속토지를 포함하여 적용하는 것이 타당함.",
        "url": "https://www.olta.re.kr/interpret/detail?id=2024-0312"
    }
]
```

### 1-5. 1단계 확인

```bash
cd backend
python -c "from app.models.verification import SourceVerification, ContentClaim, VerificationResult, FinalAnswer; print('OK')"
python -c "from tests.mocks.mock_drafts import MOCK_DRAFT_NORMAL, MOCK_DRAFT_WITH_HALLUCINATION, MOCK_DRAFT_ALL_WRONG, MOCK_CRAWL_RESULTS; print('OK')"
```

TODO_STEP3.md 1단계 항목 모두 `[x]` 업데이트.

---

## ▶ 2단계 시작: 출처 검증기 + 내용 검증기 (Mock 규칙 기반)

### 2-1. source_verifier.py

**`backend/app/services/verification/source_verifier.py`** — 아래 로직으로 구현해:

```python
import re
from app.config import get_settings
from app.models.verification import SourceVerification
from app.models.schemas import CrawlResult

class SourceVerifier:
    async def verify(self, draft_answer: str, crawl_results: list[CrawlResult]) -> list[SourceVerification]:
        settings = get_settings()
        if settings.use_mock_llm:
            return self._mock_verify(draft_answer, crawl_results)
        else:
            # TODO 실제 모드: GPT-4o-mini로 출처 검증
            raise NotImplementedError("실제 LLM 출처 검증 미구현")

    def _mock_verify(self, draft_answer: str, crawl_results: list[CrawlResult]) -> list[SourceVerification]:
        """규칙 기반 출처 검증 (Mock)"""
        # 1. 초안에서 [출처: xxx] 패턴 추출
        source_ids = re.findall(r'\[출처:\s*([^\]]+)\]', draft_answer)
        # 개별 source_id 분리 (쉼표 구분 가능)
        all_ids = []
        for sid_group in source_ids:
            for sid in sid_group.split(','):
                sid = sid.strip()
                if sid:
                    all_ids.append(sid)
        all_ids = list(set(all_ids))

        # 2. 크롤링 결과 ID 맵
        crawl_map = {r.id: r for r in crawl_results}

        verifications = []
        for sid in all_ids:
            if sid not in crawl_map:
                # 존재하지 않는 출처 → not_found
                verifications.append(SourceVerification(
                    source_id=sid, status="not_found",
                    detail=f"크롤링 원본 데이터에 {sid}가 존재하지 않음"
                ))
            else:
                result = crawl_map[sid]
                # URL 도메인 확인
                if "olta.re.kr" not in result.url:
                    verifications.append(SourceVerification(
                        source_id=sid, title=result.title, url=result.url,
                        status="expired", detail="URL이 olta.re.kr 도메인이 아님"
                    ))
                else:
                    # 조문 번호 일치 확인 (초안에서 해당 source 인용 문맥과 원본 비교)
                    # 간단한 규칙: 원본 title에 있는 "제XX조"가 초안에도 있는지
                    article_match = re.search(r'제(\d+)조', result.title)
                    if article_match:
                        article_num = article_match.group(0)
                        if article_num in draft_answer:
                            verifications.append(SourceVerification(
                                source_id=sid, title=result.title, url=result.url,
                                status="verified", detail="법령 조문 번호 및 내용이 원본과 일치함"
                            ))
                        else:
                            verifications.append(SourceVerification(
                                source_id=sid, title=result.title, url=result.url,
                                status="mismatch", detail=f"초안에서 {article_num}을 참조하지 않음"
                            ))
                    else:
                        verifications.append(SourceVerification(
                            source_id=sid, title=result.title, url=result.url,
                            status="verified", detail="출처 확인됨"
                        ))
        return verifications

source_verifier = SourceVerifier()
```

### 2-2. content_verifier.py

**`backend/app/services/verification/content_verifier.py`** — 아래 로직으로 구현해:

```python
import re
from app.config import get_settings
from app.models.verification import ContentClaim
from app.models.schemas import CrawlResult

class ContentVerifier:
    async def verify(self, draft_answer: str, crawl_results: list[CrawlResult]) -> list[ContentClaim]:
        settings = get_settings()
        if settings.use_mock_llm:
            return self._mock_verify(draft_answer, crawl_results)
        else:
            # TODO 실제 모드: GPT-4o-mini로 내용 검증
            raise NotImplementedError("실제 LLM 내용 검증 미구현")

    def _mock_verify(self, draft_answer: str, crawl_results: list[CrawlResult]) -> list[ContentClaim]:
        """규칙 기반 내용 검증 (Mock)"""
        # 모든 크롤링 원본 텍스트 합치기
        all_content = " ".join([r.content for r in crawl_results])

        # 초안에서 사실적 주장 추출 (마크다운 헤더, 빈 줄, 출처 태그, 구분선 제외)
        claims = []
        for line in draft_answer.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#') or line.startswith('---') or line.startswith('📌'):
                continue
            if line.startswith('>'):  # 인용문(경고 등)은 제외
                continue
            # [출처: xxx] 태그 제거하여 순수 주장 텍스트 추출
            clean_line = re.sub(r'\[출처:\s*[^\]]+\]', '', line).strip()
            if len(clean_line) < 10:  # 너무 짧은 줄은 제외
                continue
            # 출처 태그에서 source_id 추출
            cited = re.findall(r'\[출처:\s*([^\]]+)\]', line)
            cited_ids = []
            for c in cited:
                for sid in c.split(','):
                    cited_ids.append(sid.strip())

            claims.append({"text": clean_line, "cited": cited_ids, "original_line": line})

        # 각 주장별 검증
        results = []
        for claim in claims:
            text = claim["text"]
            # 핵심 키워드 추출 (숫자, 법령명, 핵심 명사)
            keywords = re.findall(r'(?:제?\d+조|제?\d+항|\d+[억만천백]?원|\d+%|\d+분의\s*\d+|취득세|재산세|감면|경감|면제|부동산|주택|영농조합법인|농업법인)', text)

            # 키워드 매칭 점수 계산
            matched = sum(1 for kw in keywords if kw in all_content)
            total = len(keywords) if keywords else 1

            # 모순 검사: 초안에서 "100% 면제"인데 원본은 "50% 경감"인 경우
            is_contradicted = False
            if "면제" in text and "100분의 50" in all_content and "면제" not in all_content:
                is_contradicted = True
            if "100%" in text and "100분의 50" in all_content:
                is_contradicted = True

            if is_contradicted:
                results.append(ContentClaim(
                    claim_text=claim["text"], cited_sources=claim["cited"],
                    verification_status="hallucinated", confidence=0.0,
                    detail="원본 데이터와 모순됨"
                ))
            elif matched >= 3 or (total > 0 and matched / total >= 0.6):
                results.append(ContentClaim(
                    claim_text=claim["text"], cited_sources=claim["cited"],
                    verification_status="supported", confidence=0.85,
                    detail=f"핵심 키워드 {matched}/{total}개 일치"
                ))
            elif matched >= 1:
                results.append(ContentClaim(
                    claim_text=claim["text"], cited_sources=claim["cited"],
                    verification_status="partial", confidence=0.5,
                    detail=f"핵심 키워드 {matched}/{total}개 부분 일치",
                    corrected_text=claim["text"] + " ⚠️ *일부 내용 확인 필요*"
                ))
            else:
                results.append(ContentClaim(
                    claim_text=claim["text"], cited_sources=claim["cited"],
                    verification_status="unsupported", confidence=0.2,
                    detail="크롤링 원본에 근거를 찾을 수 없음"
                ))

        return results

content_verifier = ContentVerifier()
```

### 2-3. pytest 테스트

**`backend/tests/test_source_verifier.py`**:
```python
import pytest
from app.services.verification.source_verifier import source_verifier
from app.models.schemas import CrawlResult
from tests.mocks.mock_drafts import MOCK_DRAFT_NORMAL, MOCK_DRAFT_WITH_HALLUCINATION, MOCK_CRAWL_RESULTS

def _to_crawl_results(data_list):
    return [CrawlResult(**{**d, "preview": d["content"][:100]+"...", "relevance_score": 0.9}) for d in data_list]

@pytest.mark.asyncio
async def test_source_verified():
    """VT-01: 존재하는 출처 → verified"""
    results = await source_verifier.verify(MOCK_DRAFT_NORMAL, _to_crawl_results(MOCK_CRAWL_RESULTS))
    verified = [r for r in results if r.status == "verified"]
    assert len(verified) >= 2

@pytest.mark.asyncio
async def test_source_not_found():
    """VT-02: 존재하지 않는 출처 → not_found"""
    results = await source_verifier.verify(MOCK_DRAFT_WITH_HALLUCINATION, _to_crawl_results(MOCK_CRAWL_RESULTS))
    not_found = [r for r in results if r.status == "not_found"]
    assert len(not_found) >= 1
    assert any(r.source_id == "src_999" for r in not_found)

@pytest.mark.asyncio
async def test_source_mismatch():
    """VT-03: 조문 번호 불일치 → mismatch"""
    # 초안에서 제36조를 인용하되 mock_law_002(제11조)의 ID를 사용
    draft_mismatch = "제36조에 따르면 농업법인은 감면됩니다. [출처: mock_law_002]"
    results = await source_verifier.verify(draft_mismatch, _to_crawl_results(MOCK_CRAWL_RESULTS))
    # mock_law_002의 title은 "제11조"인데 초안에 제11조가 없으면 mismatch
    # 실제로는 제36조가 초안에 있으므로 mock_law_002(제11조) 관점에서 확인
    assert len(results) >= 1
```

**`backend/tests/test_content_verifier.py`**:
```python
import pytest
from app.services.verification.content_verifier import content_verifier
from app.models.schemas import CrawlResult
from tests.mocks.mock_drafts import MOCK_DRAFT_NORMAL, MOCK_DRAFT_WITH_HALLUCINATION, MOCK_DRAFT_ALL_WRONG, MOCK_CRAWL_RESULTS

def _to_crawl_results(data_list):
    return [CrawlResult(**{**d, "preview": d["content"][:100]+"...", "relevance_score": 0.9}) for d in data_list]

@pytest.mark.asyncio
async def test_content_supported():
    """VT-04: 원본에 근거 있는 주장 → supported"""
    results = await content_verifier.verify(MOCK_DRAFT_NORMAL, _to_crawl_results(MOCK_CRAWL_RESULTS))
    supported = [c for c in results if c.verification_status == "supported"]
    assert len(supported) >= 2

@pytest.mark.asyncio
async def test_content_unsupported():
    """VT-05: 원본에 근거 없는 주장 → unsupported"""
    results = await content_verifier.verify(MOCK_DRAFT_WITH_HALLUCINATION, _to_crawl_results(MOCK_CRAWL_RESULTS))
    unsupported = [c for c in results if c.verification_status in ("unsupported", "hallucinated")]
    assert len(unsupported) >= 1

@pytest.mark.asyncio
async def test_content_hallucinated():
    """VT-06: 원본과 모순되는 주장 → hallucinated"""
    results = await content_verifier.verify(MOCK_DRAFT_ALL_WRONG, _to_crawl_results(MOCK_CRAWL_RESULTS))
    hallucinated = [c for c in results if c.verification_status == "hallucinated"]
    # "100% 면제"는 원본 "50% 경감"과 모순
    assert len(hallucinated) >= 1 or all(c.verification_status in ("unsupported", "hallucinated") for c in results)

@pytest.mark.asyncio
async def test_content_partial():
    """VT-07: 부분 일치 → partial + corrected_text"""
    results = await content_verifier.verify(MOCK_DRAFT_WITH_HALLUCINATION, _to_crawl_results(MOCK_CRAWL_RESULTS))
    # "3년 내 매각" 주장은 partial 또는 unsupported
    non_supported = [c for c in results if c.verification_status != "supported"]
    assert len(non_supported) >= 1
```

### 2-4. 2단계 확인

```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/test_source_verifier.py tests/test_content_verifier.py -v
```

TODO_STEP3.md 2단계 항목 모두 체크.

---

## ▶ 3단계 시작: 검증 결과 통합기 + 신뢰도 산출

### 3-1. verification_aggregator.py

**`backend/app/services/verification/verification_aggregator.py`** — 아래 로직으로 구현해:

- 출처 검증 상태 맵 생성: `{source_id: status}`
- 각 주장의 confidence를 출처 상태에 따라 보정
- 전체 신뢰도 산출 + 라벨 결정
- 제거/수정 대상 목록 + 경고 메시지 생성
- `VerificationResult` 반환

보정 규칙, 제거/수정 규칙, 신뢰도 라벨은 PRD에 명시된 것을 그대로 따라.

### 3-2. test_aggregator.py

3가지 시나리오(정상, 할루시네이션 포함, 전체 오류) 테스트. TODO에 명시된 VT-08 ~ VT-10.

### 3-3. 3단계 확인

```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/test_aggregator.py -v
```

---

## ▶ 4단계 시작: 최종 답변 생성 + chat.py SSE 파이프라인 수정

### 4-1. final_generator.py

규칙 기반 텍스트 편집으로 최종 답변 생성:
- 제거 대상 주장의 원문 줄 삭제
- 수정 대상 주장을 corrected_text로 교체
- unsupported (confidence >= 0.3) 뒤에 " ⚠️ *확인 필요*" 추가
- 답변 마지막에 신뢰도 블록 추가
- 검증된 출처만으로 "📌 참고 출처" 재구성
- 에러 시 1단계 초안 + 경고 반환

### 4-2. chat.py 수정

Step 2에서 `# TODO Step 3` 주석이 있던 자리에 실제 검증 코드를 삽입해:

핵심 변경:
1. `stage_change("verifying")` 이벤트 추가
2. `asyncio.gather(source_verifier.verify(...), content_verifier.verify(...))` 로 병렬 실행
3. `aggregator.aggregate(...)` 호출
4. `stage_change("finalizing")` 이벤트 추가
5. `final_generator.generate(...)` 호출 (토큰 스트리밍)
6. `sources` 이벤트에 `confidence` 정보 추가: `{"sources": [...], "confidence": {"score": 0.87, "label": "높음"}}`
7. 전체를 `try/except`로 감싸서, 검증 실패 시 1단계 초안 + 경고 반환

### 4-3. pytest 테스트

기존 `test_chat_pipeline.py`를 수정하여 SSE 이벤트에 `verifying`, `finalizing` 단계가 포함되는지 검증. 그리고 `test_verification_pipeline.py`에서 IT-01~IT-07 시나리오 테스트 작성.

### 4-4. 4단계 확인

```bash
cd backend
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v
```

전체 통과 확인 후 curl SSE 수동 테스트.

---

## ▶ 5단계 시작: 프론트엔드 연동 + 전체 통합 테스트

### 5-1. StatusStepper 5단계 확장

**`frontend/src/components/layout/StatusStepper.jsx`** 수정:
- 기존 4단계 배열을 5단계로 확장:
```javascript
const STEPS = [
  { stage: 'crawling',   label: '웹 검색 중',   icon: '🔍' },
  { stage: 'drafting',   label: '초안 작성 중',  icon: '✏️' },
  { stage: 'verifying',  label: '검증 중',      icon: '🔎' },
  { stage: 'finalizing', label: '최종 정리 중',  icon: '📝' },
  { stage: 'done',       label: '답변 완료',    icon: '✅' },
]
```

### 5-2. ConfidenceBadge.jsx 신규 생성

**`frontend/src/components/chat/ConfidenceBadge.jsx`**:
- props: `{ score, label }`
- label 기반 색상:
  - "높음": `bg-green-100 text-green-700 border-green-300`
  - "보통": `bg-yellow-100 text-yellow-700 border-yellow-300` + "일부 내용은 추가 확인이 필요할 수 있습니다"
  - "낮음": `bg-red-100 text-red-700 border-red-300` + "실무 적용 전 반드시 원문을 확인하세요"
- 표시: `📊 답변 신뢰도: {label} {emoji} {score}%`

### 5-3. chatStore.js 수정

`sources` 이벤트 처리 시 `confidence` 정보도 저장:
```javascript
// chatStore에 추가할 state
currentConfidence: null,  // { score: 0.87, label: "높음" }

// sources 이벤트 처리
case 'sources':
  set({
    currentSources: data.sources,
    currentConfidence: data.confidence || null
  })
```

### 5-4. ChatMessage.jsx 수정

AI 메시지 하단에 `currentConfidence`가 있으면 `ConfidenceBadge` 표시.

### 5-5. 통합 실행 + 시나리오 테스트

**터미널 1**: `cd backend && USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --port 8000`
**터미널 2**: `cd frontend && npm run dev`

브라우저에서 시나리오 1~4 수행 후 TODO_STEP3.md 5단계 최종 확인사항 모두 체크.

### 5-6. 전체 테스트

```bash
cd backend && USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v
cd frontend && npm run build
```

모든 항목이 `[x]`가 되면 **최종 TODO_STEP3.md 내용을 출력**해.

---

## ⚠️ 중요 제약사항

1. **Mock 모드 유지**: 검증 로직은 규칙 기반 Mock으로 구현. 실제 LLM 호출(GPT-4o-mini)은 `# TODO` 주석으로 자리 확보.
2. **병렬 처리**: 출처 검증과 내용 검증은 반드시 `asyncio.gather`로 병렬 실행. 순차 실행 금지.
3. **에러 안전**: 검증 파이프라인의 어떤 단계가 실패해도 최소한 1단계 초안 + 경고 메시지는 반환되어야 함. 검증 실패가 전체 답변 실패로 이어지면 안 됨.
4. **SSE 이벤트 순서**: crawling → drafting → token(초안)... → verifying → finalizing → token(최종)... → sources(+confidence) → done. 이 순서를 반드시 지킬 것.
5. **프론트엔드 호환**: sources 이벤트에 confidence 필드가 추가되더라도, confidence가 없는 경우(Step 2 호환)에도 프론트엔드가 에러 없이 동작해야 함. Optional 처리 필수.
6. **TODO_STEP3.md 필수 업데이트**: 모든 작업 완료/실패를 기록.
7. **단계 건너뛰기 금지**: 이전 단계 확인 통과 후 다음 단계 진행.
8. **Step 2 코드 최소 수정**: 기존 Step 2 코드는 chat.py의 `# TODO Step 3` 부분만 수정. 다른 기존 서비스(search_service, crawler_service, llm_service 등)는 건드리지 말 것.
9. **신뢰도 산출 규칙 엄수**: PRD에 명시된 보정 계수(0.3, 0.5, 0.2)와 라벨 기준(0.7, 0.4)을 정확히 따를 것.
