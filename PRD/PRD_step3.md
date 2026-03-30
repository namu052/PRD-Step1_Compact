# PRD Step 3: 출력된 답변의 재검증 루틴

> **문서 버전**: v1.0  
> **작성일**: 2026.03.28  
> **범위**: LLM 2단계 검증 파이프라인, 할루시네이션 필터링, 출처 교차 검증, 신뢰도 스코어링  
> **선행 조건**: Step 2 완료 (1단계 초안 생성 + 실제 크롤링 정상 동작)  
> **산출물**: 2단계 검증이 포함된 완전한 답변 파이프라인

---

## 1. 목표 (Objective)

Step 3의 목표는 **1단계에서 생성된 답변 초안을 체계적으로 재검증하여, 출처가 불분명하거나 잘못된 내용을 필터링하고 신뢰도 높은 최종 답변을 생성**하는 것이다.

지방세 실무에서 부정확한 답변은 잘못된 과세 처분이나 민원 대응 오류로 이어질 수 있으므로, 이 검증 단계는 APP의 핵심 가치이다.

---

## 2. 검증 아키텍처 개요

```
[1단계 초안]
    │
    ▼
┌──────────────────────────────────────┐
│          2단계 검증 파이프라인          │
│                                      │
│  ┌────────────┐   ┌───────────────┐  │
│  │ 출처 검증기 │   │ 내용 검증기    │  │
│  │ (Source     │   │ (Content      │  │
│  │  Verifier)  │   │  Verifier)    │  │
│  └──────┬─────┘   └──────┬────────┘  │
│         │                │           │
│         ▼                ▼           │
│  ┌──────────────────────────────┐    │
│  │      검증 결과 통합기          │    │
│  │   (Verification Aggregator)  │    │
│  └──────────────┬───────────────┘    │
│                 │                    │
│                 ▼                    │
│  ┌──────────────────────────────┐    │
│  │      최종 답변 생성기          │    │
│  │   (Final Answer Generator)   │    │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
    │
    ▼
[최종 답변 + 신뢰도 스코어]
```

---

## 3. 디렉토리 구조 (Step 2에 추가)

```
backend/app/
├── services/
│   ├── ... (기존 Step 2 서비스)
│   └── verification/
│       ├── __init__.py
│       ├── source_verifier.py       # 출처 검증기
│       ├── content_verifier.py      # 내용 검증기
│       ├── verification_aggregator.py # 검증 결과 통합
│       └── final_generator.py       # 최종 답변 생성
├── prompts/
│   ├── stage1_prompt.py             # (기존)
│   ├── stage2_source_prompt.py      # 출처 검증 프롬프트
│   ├── stage2_content_prompt.py     # 내용 검증 프롬프트
│   └── stage2_final_prompt.py       # 최종 답변 생성 프롬프트
├── models/
│   ├── schemas.py                   # (기존)
│   └── verification.py              # 검증 결과 데이터 모델
└── tests/
    ├── ... (기존 테스트)
    ├── test_source_verifier.py
    ├── test_content_verifier.py
    ├── test_verification_pipeline.py
    └── test_verification_e2e.py
```

---

## 4. 검증 데이터 모델

### 4.1 verification.py

```python
class SourceVerification:
    source_id: str
    title: str
    url: str
    status: str          # "verified" | "not_found" | "mismatch" | "expired"
    detail: str          # 상세 검증 결과 설명
    verified_at: datetime

class ContentClaim:
    claim_text: str      # 초안에서 추출한 개별 주장
    cited_sources: list[str]          # 인용된 source_id 목록
    verification_status: str          # "supported" | "unsupported" | "partial" | "hallucinated"
    confidence: float                 # 0.0 ~ 1.0
    detail: str                       # 검증 상세 설명
    corrected_text: str | None        # 수정이 필요한 경우 수정 텍스트

class VerificationResult:
    source_verifications: list[SourceVerification]
    content_claims: list[ContentClaim]
    overall_confidence: float         # 전체 신뢰도 (0.0 ~ 1.0)
    removed_claims: list[str]         # 제거된 주장 목록
    modified_claims: list[dict]       # 수정된 주장 목록 { original, corrected, reason }
    warnings: list[str]               # 경고 메시지 목록

class FinalAnswer:
    answer: str                       # 최종 답변 (Markdown)
    confidence_score: float           # 전체 신뢰도
    confidence_label: str             # "높음" | "보통" | "낮음"
    verified_sources: list[dict]      # 검증된 출처 목록
    warnings: list[str]               # 사용자에게 표시할 경고
```

---

## 5. 출처 검증기 (Source Verifier)

### 5.1 검증 로직

출처 검증기는 1단계 초안에서 인용된 모든 출처에 대해 다음을 확인한다:

```
[1단계 초안에서 출처 추출]
    │
    ├─ [출처: src_001] → "지방세특례제한법 제36조"
    ├─ [출처: src_002] → "해석례 2024-0312"
    │
    ▼
[각 출처에 대해 검증]
    │
    ├─ 검증 1: 해당 source_id가 크롤링 결과에 실제 존재하는가?
    │   - 존재 → 다음 검증으로
    │   - 미존재 → status: "not_found" (할루시네이션)
    │
    ├─ 검증 2: 출처의 법령 조문 번호가 실제 크롤링 내용과 일치하는가?
    │   - "제36조"로 인용했는데 크롤링 내용에 제36조가 있는가?
    │   - 일치 → 다음 검증으로
    │   - 불일치 → status: "mismatch"
    │
    └─ 검증 3: 출처 URL이 유효한가?
        - olta.re.kr 도메인인가?
        - 유효 → status: "verified"
        - 무효 → status: "expired"
```

### 5.2 프롬프트 (stage2_source_prompt.py)

```python
SOURCE_VERIFICATION_PROMPT = """
너는 지방세 법령 출처 검증 전문가이다.
아래 [답변 초안]에서 인용된 출처가 [크롤링 원본 데이터]와 일치하는지 검증하라.

## 검증 규칙
1. [출처: source_id] 태그로 표시된 모든 출처를 추출하라
2. 각 출처에 대해 다음을 확인하라:
   a) source_id가 [크롤링 원본 데이터]에 존재하는가?
   b) 인용된 법령 조문 번호(예: 제36조)가 원본의 실제 조문과 일치하는가?
   c) 인용된 내용이 원본의 실제 내용과 부합하는가?
3. 검증 결과를 JSON으로 반환하라

## 출력 형식 (JSON만 출력, 다른 텍스트 없이)
{
    "verifications": [
        {
            "source_id": "src_001",
            "title": "지방세특례제한법 제36조",
            "status": "verified",
            "detail": "법령 조문 번호 및 내용이 원본과 일치함"
        },
        {
            "source_id": "src_003",
            "status": "not_found",
            "detail": "크롤링 원본 데이터에 해당 source_id가 존재하지 않음"
        }
    ]
}

## 답변 초안
{draft_answer}

## 크롤링 원본 데이터
{crawl_results}
"""
```

---

## 6. 내용 검증기 (Content Verifier)

### 6.1 검증 로직

내용 검증기는 초안의 각 주장(claim)이 크롤링 원본 데이터에 의해 뒷받침되는지 확인한다:

```
[1단계 초안을 문장 단위로 분해]
    │
    ├─ "취득가액 1억원 이하의 주택을 취득하는 경우 취득세 50% 경감"
    ├─ "영농조합법인이 농업에 직접 사용하기 위하여 취득하는 부동산"
    ├─ "감면 적용 시 5년 내 매각 시 추징"
    │
    ▼
[각 주장에 대해 검증]
    │
    ├─ 주장 1: 크롤링 원본에서 "1억원 이하" + "50% 경감" 확인
    │   → status: "supported", confidence: 0.95
    │
    ├─ 주장 2: 크롤링 원본에서 "영농조합법인" + "직접 사용" 확인
    │   → status: "supported", confidence: 0.90
    │
    └─ 주장 3: 크롤링 원본에서 "5년 내 매각 추징" 확인 불가
        → status: "unsupported", confidence: 0.20
        → corrected_text: null (제거 대상)
```

### 6.2 프롬프트 (stage2_content_prompt.py)

```python
CONTENT_VERIFICATION_PROMPT = """
너는 지방세 답변 내용 검증 전문가이다.
아래 [답변 초안]의 각 주장이 [크롤링 원본 데이터]에 의해 뒷받침되는지 검증하라.

## 검증 규칙
1. 답변 초안에서 사실적 주장을 모두 추출하라 (일반적 안내 문구는 제외)
2. 각 주장에 대해 크롤링 원본에서 근거를 찾아라
3. 다음 기준으로 분류하라:
   - "supported": 원본 데이터에서 명확한 근거를 찾을 수 있음 (confidence: 0.7~1.0)
   - "partial": 부분적으로 뒷받침됨. 일부 수정 필요 (confidence: 0.4~0.7)
   - "unsupported": 원본 데이터에 근거가 없음 (confidence: 0.0~0.4)
   - "hallucinated": 원본 데이터와 명백히 모순됨 (confidence: 0.0)
4. "partial"인 경우 수정 텍스트를 제안하라
5. "unsupported"와 "hallucinated"는 최종 답변에서 제거 대상으로 표시하라

## 출력 형식 (JSON만 출력)
{
    "claims": [
        {
            "claim_text": "취득가액 1억원 이하의 주택에 대해 취득세 50%를 경감",
            "cited_sources": ["src_001"],
            "status": "supported",
            "confidence": 0.95,
            "detail": "지방세특례제한법 제36조 제1항, 제2항에서 확인됨"
        },
        {
            "claim_text": "감면 적용 후 5년 내 매각 시 추징됨",
            "cited_sources": [],
            "status": "unsupported",
            "confidence": 0.15,
            "detail": "크롤링 원본에 해당 추징 조항에 대한 내용이 없음"
        }
    ]
}

## 답변 초안
{draft_answer}

## 크롤링 원본 데이터
{crawl_results}
"""
```

---

## 7. 검증 결과 통합기 (Verification Aggregator)

### 7.1 통합 로직

```python
class VerificationAggregator:
    def aggregate(
        source_verifications: list[SourceVerification],
        content_claims: list[ContentClaim]
    ) -> VerificationResult:
        """
        1. 출처 검증 결과와 내용 검증 결과를 교차 분석
        2. 미검증 출처를 인용한 주장은 자동으로 confidence 하향
        3. 전체 신뢰도 점수 산출
        4. 제거/수정 대상 목록 생성
        """
```

### 7.2 신뢰도 산출 규칙

```
전체 신뢰도 = (검증된 주장의 confidence 합계) / (전체 주장 수)

주장별 confidence 보정:
- 출처가 "verified"인 주장: confidence 유지
- 출처가 "not_found"인 주장: confidence × 0.3 (대폭 하향)
- 출처가 "mismatch"인 주장: confidence × 0.5 (하향)
- 출처가 없는 주장: confidence × 0.2 (대폭 하향)

최종 신뢰도 라벨:
- 0.7 이상: "높음" (🟢)
- 0.4 이상: "보통" (🟡) + 경고 메시지
- 0.4 미만: "낮음" (🔴) + 강한 경고 메시지
```

### 7.3 제거/수정 규칙

| 조건 | 처리 |
|------|------|
| status: "hallucinated" | 최종 답변에서 완전 제거 |
| status: "unsupported" & confidence < 0.3 | 최종 답변에서 완전 제거 |
| status: "unsupported" & confidence >= 0.3 | "⚠️ 확인 필요" 표시 후 유지 |
| status: "partial" | corrected_text로 교체 |
| status: "supported" | 그대로 유지 |
| 출처 "not_found" | 해당 출처 태그 제거 + 주장에 "⚠️ 출처 확인 필요" 추가 |
| 출처 "mismatch" | 정확한 조문 번호로 교체 |

---

## 8. 최종 답변 생성기 (Final Answer Generator)

### 8.1 프롬프트 (stage2_final_prompt.py)

```python
FINAL_ANSWER_PROMPT = """
너는 지방세 답변 최종 편집자이다.
아래 [답변 초안]과 [검증 결과]를 바탕으로 최종 답변을 작성하라.

## 편집 규칙
1. [검증 결과]에서 "제거 대상"으로 표시된 주장은 답변에서 완전히 삭제하라
2. [검증 결과]에서 "수정 필요"로 표시된 주장은 제안된 수정 텍스트로 교체하라
3. "⚠️ 확인 필요" 표시가 필요한 부분에 경고를 삽입하라
4. 출처 태그를 검증 결과에 맞게 업데이트하라
5. 답변의 전체적인 흐름과 가독성을 유지하라
6. 제거/수정으로 인해 답변이 부자연스러워지면 문장을 자연스럽게 다듬어라
7. 답변 마지막에 신뢰도 정보를 표시하라

## 신뢰도 표시 형식
---
📊 **답변 신뢰도**: {confidence_label} ({confidence_score}%)
{warnings가 있으면}
⚠️ **주의사항**: {warning_message}

## 답변 초안
{draft_answer}

## 검증 결과
{verification_result}

## 검증 완료된 출처 목록
{verified_sources}
"""
```

### 8.2 최종 답변 포맷

```markdown
## 취득세 감면 대상

**지방세특례제한법 제36조**에 따르면, 다음에 해당하는 경우 취득세를 감면받을 수 있습니다.

### 1. 서민주택 취득세 감면
- 취득가액 **1억원 이하**의 주택을 취득하는 경우
- 감면율: 취득세의 **50% 경감**
- [출처: 지방세특례제한법 제36조 제1항, 제2항]

### 2. 농업법인 감면
- 영농조합법인이 농업에 직접 사용하기 위하여 취득하는 부동산
- 근거: 지방세특례제한법 제11조
- [출처: 지방세특례제한법 제11조 제1항]

---
📊 **답변 신뢰도**: 높음 🟢 (87%)
📌 **참고 출처**:
1. 지방세특례제한법 제36조 (서민주택 등에 대한 감면)
2. 지방세특례제한법 제11조 (농업법인에 대한 감면)
3. 해석례 2024-0312 (서민주택 감면 적용 범위)
```

---

## 9. SSE 스트리밍 통합 (chat.py 수정)

### 9.1 전체 파이프라인 (Step 3 완성본)

```python
@router.post("/api/chat")
async def chat(request: ChatRequest):
    session = session_manager.get_session(request.session_id)

    async def event_generator():
        # ── 크롤링 단계 ──
        yield sse_event("stage_change", {
            "stage": "crawling",
            "message": "olta.re.kr에서 관련 자료를 검색하고 있습니다..."
        })
        queries = await search_service.extract_keywords(request.question)
        crawl_results = await crawler_service.search(session, queries)

        # ── 1단계: 초안 작성 ──
        yield sse_event("stage_change", {
            "stage": "drafting",
            "message": "검색된 자료를 바탕으로 답변을 작성하고 있습니다..."
        })
        draft_tokens = []
        async def on_draft_token(token):
            draft_tokens.append(token)
            yield sse_event("token", {"content": token, "stage": "draft"})
        draft = await llm_service.generate_draft(
            request.question, crawl_results, on_draft_token
        )

        # ── 2단계: 검증 ──
        yield sse_event("stage_change", {
            "stage": "verifying",
            "message": "답변의 출처와 내용을 검증하고 있습니다..."
        })

        # 2-a. 출처 검증
        source_verifications = await source_verifier.verify(
            draft.answer, crawl_results
        )

        # 2-b. 내용 검증
        content_claims = await content_verifier.verify(
            draft.answer, crawl_results
        )

        # 2-c. 검증 결과 통합
        verification = aggregator.aggregate(
            source_verifications, content_claims
        )

        # 2-d. 최종 답변 생성
        yield sse_event("stage_change", {
            "stage": "finalizing",
            "message": "최종 답변을 정리하고 있습니다..."
        })
        final_tokens = []
        async def on_final_token(token):
            final_tokens.append(token)
            yield sse_event("token", {"content": token, "stage": "final"})
        final = await final_generator.generate(
            draft.answer, verification, crawl_results, on_final_token
        )

        # ── 출처 + 신뢰도 전달 ──
        yield sse_event("sources", {
            "sources": final.verified_sources,
            "confidence": {
                "score": final.confidence_score,
                "label": final.confidence_label
            }
        })

        # ── 완료 ──
        yield sse_event("stage_change", {
            "stage": "done",
            "message": "답변이 완료되었습니다."
        })

    return EventSourceResponse(event_generator())
```

### 9.2 프론트엔드 StatusStepper 업데이트

Step 3에서 스테퍼를 5단계로 확장한다:

| 단계 | 라벨 | stage 값 | 아이콘 |
|------|------|----------|--------|
| 1 | 웹 검색 중 | crawling | 🔍 |
| 2 | 초안 작성 중 | drafting | ✏️ |
| 3 | 검증 중 | verifying | 🔎 |
| 4 | 최종 정리 중 | finalizing | 📝 |
| 5 | 답변 완료 | done | ✅ |

### 9.3 프론트엔드 신뢰도 표시

답변 하단에 신뢰도 배지를 표시한다:

```
┌─────────────────────────────────────┐
│  📊 답변 신뢰도: 높음 🟢 87%       │
│                                     │
│  ⚠️ 일부 내용은 추가 확인이         │
│     필요할 수 있습니다.              │
└─────────────────────────────────────┘
```

- 높음 (🟢, 70%+): 녹색 배지
- 보통 (🟡, 40~70%): 노란색 배지 + 경고 문구
- 낮음 (🔴, 40% 미만): 빨간색 배지 + 강한 경고 문구 + "실무 적용 전 반드시 원문을 확인하세요"

---

## 10. 검증 체크리스트

### 10.1 단위 테스트

| ID | 테스트 대상 | 검증 내용 |
|----|------------|----------|
| VT-01 | source_verifier | 존재하는 출처 → status: "verified" 반환 |
| VT-02 | source_verifier | 존재하지 않는 출처 → status: "not_found" 반환 |
| VT-03 | source_verifier | 조문 번호 불일치 → status: "mismatch" 반환 |
| VT-04 | content_verifier | 원본에 근거 있는 주장 → status: "supported" |
| VT-05 | content_verifier | 원본에 근거 없는 주장 → status: "unsupported" |
| VT-06 | content_verifier | 원본과 모순되는 주장 → status: "hallucinated" |
| VT-07 | content_verifier | 부분적으로 맞는 주장 → status: "partial" + corrected_text |
| VT-08 | aggregator | 전체 신뢰도 점수 산출 정확성 |
| VT-09 | aggregator | 미검증 출처 인용 주장의 confidence 하향 반영 |
| VT-10 | aggregator | 제거/수정 대상 목록 정확성 |
| VT-11 | final_generator | hallucinated 주장이 최종 답변에서 제거되었는가 |
| VT-12 | final_generator | partial 주장이 corrected_text로 교체되었는가 |
| VT-13 | final_generator | 신뢰도 표시가 포맷에 맞게 포함되었는가 |
| VT-14 | final_generator | 제거 후 답변의 문장 흐름이 자연스러운가 |

### 10.2 시나리오별 통합 테스트

| ID | 시나리오 | 입력 | 기대 결과 |
|----|---------|------|----------|
| IT-01 | 모든 출처 검증 성공 | 정확한 초안 + 일치하는 크롤링 데이터 | 신뢰도 높음 (85%+), 수정 없음 |
| IT-02 | 할루시네이션 포함 | 존재하지 않는 "지방세법 제999조" 인용 | 해당 주장 제거, 신뢰도 하향 |
| IT-03 | 조문 번호 오류 | "제36조"를 "제37조"로 잘못 인용 | mismatch 감지, 올바른 조문으로 교체 |
| IT-04 | 출처 없는 주장 | [출처] 태그 없이 사실 주장 | unsupported 분류, "확인 필요" 표시 |
| IT-05 | 전체 검증 실패 | 모든 주장이 근거 없음 | 신뢰도 낮음, 강한 경고 + "원문 확인" 안내 |
| IT-06 | 부분 검증 성공 | 3개 주장 중 2개 검증, 1개 미검증 | 미검증 주장에 "확인 필요" 표시 |
| IT-07 | 검색 결과 없음 처리 | 크롤링 결과가 빈 경우 | "관련 자료를 찾지 못했습니다" + 신뢰도 없음 |

### 10.3 가상 데이터 기반 검증 테스트

```python
# test_verification_pipeline.py

# 테스트용 가상 초안 (할루시네이션 포함)
MOCK_DRAFT_WITH_HALLUCINATION = """
## 취득세 감면 대상

**지방세특례제한법 제36조**에 따르면 서민주택 취득 시 취득세 50%를 경감합니다. [출처: src_001]

또한 **지방세법 제999조**에 따르면 모든 1주택자는 취득세가 면제됩니다. [출처: src_999]

감면 적용 후 3년 내 매각 시 감면세액이 추징됩니다.
"""

# 기대 결과:
# - src_001: verified
# - src_999: not_found (할루시네이션)
# - "지방세법 제999조" 관련 주장: hallucinated → 제거
# - "3년 내 매각 추징" 주장: unsupported → 제거 또는 "확인 필요" 표시
# - 신뢰도: 약 0.4~0.5 (보통)
```

### 10.4 E2E 테스트

| ID | 시나리오 | 검증 내용 |
|----|---------|----------|
| E2E-S3-01 | 전체 파이프라인 | 질문 → 크롤링 → 1단계 초안 → 2단계 검증 → 최종 답변 + 신뢰도 |
| E2E-S3-02 | 스테퍼 전환 | SSE 이벤트로 5단계 스테퍼가 순차적으로 전환되는가 |
| E2E-S3-03 | 신뢰도 표시 | 프론트엔드에서 신뢰도 배지가 올바른 색상과 수치로 표시되는가 |
| E2E-S3-04 | 할루시네이션 필터링 | 의도적으로 애매한 질문 → 검증 후 할루시네이션 제거 확인 |
| E2E-S3-05 | 출처 패널 연동 | 검증된 출처만 오른쪽 패널에 표시되는가 |
| E2E-S3-06 | 응답 시간 | 전체 파이프라인 완료까지 30초 이내인가 |

---

## 11. 성능 최적화

### 11.1 병렬 처리

```
[1단계 초안 완료 후]
    │
    ├─ 출처 검증 ──┐
    │              ├─ 동시 실행 (asyncio.gather)
    ├─ 내용 검증 ──┘
    │
    ▼
[검증 결과 통합]
    │
    ▼
[최종 답변 생성]
```

- 출처 검증과 내용 검증을 `asyncio.gather`로 병렬 실행
- 예상 시간 절감: 순차 15초 → 병렬 8~10초

### 11.2 토큰 절약

- 2단계 검증에는 GPT-4o-mini 사용 (비용 절감)
- 최종 답변 생성에만 GPT-4o 사용 (품질 유지)
- 크롤링 결과 중 유사도 상위 5건만 LLM에 전달 (컨텍스트 축소)

### 11.3 목표 성능

| 단계 | 목표 시간 | 비고 |
|------|----------|------|
| 크롤링 | 5초 이내 | 3개 카테고리 병렬 |
| 1단계 초안 | 8초 이내 | GPT-4o 스트리밍 |
| 2단계 검증 | 5초 이내 | 출처+내용 병렬, GPT-4o-mini |
| 최종 답변 | 5초 이내 | GPT-4o 스트리밍 |
| **전체** | **25초 이내** | SSE로 체감 속도 향상 |

---

## 12. 에러 처리

| 상황 | 처리 방법 |
|------|----------|
| 2단계 검증 실패 (LLM 에러) | 1단계 초안을 경고 메시지와 함께 그대로 반환 ("⚠️ 검증을 완료하지 못했습니다. 원문을 직접 확인해 주세요.") |
| 검증 결과 JSON 파싱 실패 | 1회 재시도 후 실패 시 1단계 초안 + 경고 반환 |
| 전체 주장이 제거됨 | "제공된 자료만으로는 정확한 답변이 어렵습니다. 아래 출처를 직접 확인해 주세요." + 출처 목록만 표시 |
| 신뢰도 산출 불가 | 신뢰도 표시 없이 답변 + "검증 정보를 산출하지 못했습니다" 표시 |

---

## 13. 향후 개선 사항

### Phase 2 검증 고도화
- 크롤링 결과의 최신성 확인 (법령 개정일 체크)
- 사용자 피드백 기반 검증 품질 개선 (👍/👎 버튼)
- 검증 결과 캐싱 (동일 출처 반복 검증 방지)

### Phase 3 검증 확장
- 법령 조문 간 상충 여부 자동 감지
- 판례와 해석례 간 불일치 경고
- 사용자 질문 의도와 답변의 부합도 평가

---

## 14. 실행 방법

```bash
# Step 2 환경에서 추가 의존성 설치
pip install -r requirements.txt  # faiss-cpu 등 추가 패키지 포함

# 가상 데이터로 검증 파이프라인 테스트
USE_MOCK_CRAWLER=true USE_MOCK_LLM=false pytest tests/test_verification_pipeline.py -v

# 전체 가상 데이터 테스트
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true pytest tests/ -k "not e2e" -v

# 실제 E2E 테스트
pytest tests/test_verification_e2e.py -v

# 전체 서비스 실행
uvicorn app.main:app --reload

# 프론트엔드 연동
cd ../frontend && VITE_API_URL=http://localhost:8000 npm run dev
```

---

> **프로젝트 완료**: Step 1 (프론트엔드) + Step 2 (크롤링+초안) + Step 3 (검증) 통합 시, "AI 지방세 지식인 APP"의 전체 기능이 완성된다.
