# 파이프라인 고도화: 인터넷검색 우선 + OLTA 검증 아키텍처

## Context

기존 파이프라인은 "OLTA 크롤링 → 초안 → 검증 → 최종답변" 순서로, OLTA가 유일한 정보원이라 크롤링 실패 시 답변 불가.
**인터넷 검색(DuckDuckGo)으로 초안을 먼저 만들고, OLTA로 검증하는 구조**로 변경.
검증 후 미검증 부분은 추가 인터넷 검색 → 재검증을 반복하며, 최종 답변에 검증 이력 요약 포함.

**새 파이프라인 흐름**:
1. 질문 → DuckDuckGo 웹 검색 → 초안 작성
2. 초안 → OLTA 크롤링 → 3병렬 검증 (기존 인프라 재사용)
3. 검증 결과 → gap 분석 → 추가 웹/OLTA 검색 → 재검증 (최대 N회)
4. 최종 답변 = 검증 이력 요약 + 최종 정제 답변

**새 SSE stages**: `searching` → `drafting` → `verifying` → `researching` (반복) → `finalizing` → `done`

---

## Phase 1: 웹 검색 서비스 + Config 추가 ✅

### 1a. Config 확장
**파일**: `backend/app/config.py`

추가된 설정:
```python
web_search_max_results: int = 5
max_research_iterations: int = 2
research_confidence_threshold: float = 0.75
```

### 1b. 웹 검색 서비스 생성
**신규 파일**: `backend/app/services/web_search_service.py`

- DuckDuckGo 검색 사용 (`duckduckgo-search` 패키지, API 키 불필요)
- `AsyncDDGS`로 비동기 검색, `region="kr-ko"` 한국어 우선
- `search(queries, max_results) -> list[WebSearchResult]`
- 에러 시 빈 리스트 반환 + 로깅

### 1c. WebSearchResult + VerificationHistory 모델
**파일**: `backend/app/models/schemas.py`

```python
class WebSearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float = 0.0

class VerificationRound(BaseModel):
    round_number: int
    confidence: float
    gaps_found: list[str] = []
    actions_taken: str = ""

class VerificationHistory(BaseModel):
    rounds: list[VerificationRound] = []
    final_confidence: float = 0.0
    # add_round(), to_summary() 메서드 포함
```

---

## Phase 2: 웹 초안 생성 기능 ✅

### 2a. 웹 초안 프롬프트
**신규 파일**: `backend/app/prompts/web_draft_prompt.py`

- `WEB_DRAFT_SYSTEM_PROMPT`: 웹 검색 결과 기반 지방세 답변 초안 작성 규칙
- `WEB_DRAFT_USER_PROMPT`: 질문 + 웹 검색 결과 전달
- 출처 태그: `[출처: web_001]` 형식 (OLTA 출처와 구분)

### 2b. LLM 서비스에 웹 초안 메서드 추가
**파일**: `backend/app/services/llm_service.py`

- `generate_web_draft(question, web_results, on_token) -> DraftResponse` 추가
- `_format_web_results()`: 웹 결과를 `web_001`, `web_002` 형식으로 포맷
- `_fallback_web_draft()`: LLM 실패 시 웹 결과 나열 형태 fallback

---

## Phase 3: Gap 분석 서비스 ✅

### 3a. Gap 분석 프롬프트
**신규 파일**: `backend/app/prompts/gap_analysis_prompt.py`

- `GAP_ANALYSIS_SYSTEM_PROMPT` + `GAP_ANALYSIS_USER_PROMPT`
- `GAP_ANALYSIS_SCHEMA`: JSON schema (gaps, search_queries, should_continue)

### 3b. Gap 분석 서비스
**신규 파일**: `backend/app/services/gap_analyzer_service.py`

```python
class GapAnalyzerService:
    async def analyze(self, draft_answer, verification_result, history) -> GapAnalysis
```

- LLM 기반 분석으로 미검증 주장 식별 + 추가 검색 키워드 생성
- fallback: unsupported/hallucinated 주장에서 한국어 키워드 추출
- `should_continue`: gap이 있고 검색 키워드가 있을 때만 True

---

## Phase 4: 파이프라인 재구성 (핵심) ✅

### 4a. chat.py 전면 재작성
**파일**: `backend/app/routers/chat.py`

새 파이프라인 흐름:
```
1. searching  → DuckDuckGo 웹 검색 + 키워드 추출
2. drafting   → 웹 검색 결과 기반 초안 (generate_web_draft)
3. verifying  → OLTA 크롤링 + 임베딩 + 근거묶음 + 3병렬 검증
4. researching → gap 분석 → 추가 웹/OLTA 검색 → 초안 보완 → 재검증 (최대 N회 반복)
5. finalizing → 검증 이력 포함 최종 답변 생성
6. done       → 출처 카드 + 신뢰도 전송
```

기존 코드 재사용:
- `verify_answer()` (3병렬 검증기 + aggregator) 그대로 유지
- `embedding_service`, `evidence_group_service`, `evidence_summary_service` 그대로 유지

### 4b. Source Verifier 수정
**파일**: `backend/app/services/verification/source_verifier.py`

- `web_` 접두사 출처는 자동 `verified` 처리 (OLTA 매칭 대상에서 제외)

### 4c. Final Generator 수정
**파일**: `backend/app/services/verification/final_generator.py`

- `generate()` 메서드에 `verification_history: VerificationHistory | None` 파라미터 추가
- 검증 이력이 있으면 프롬프트에 이력 요약 섹션 추가 → 답변 서두에 포함 지시

---

## Phase 5: 프론트엔드 업데이트 ✅

### 5a. StatusStepper
**파일**: `frontend/src/components/layout/StatusStepper.jsx`

```javascript
const STAGES = [
  { key: 'searching', label: '웹 검색', icon: '🔍' },
  { key: 'drafting', label: '초안 작성', icon: '✏️' },
  { key: 'verifying', label: 'OLTA 검증', icon: '🔎' },
  { key: 'researching', label: '추가 조사', icon: '📚' },
  { key: 'finalizing', label: '최종 정리', icon: '🧩' },
  { key: 'done', label: '완료', icon: '✅' },
]
```

### 5b. 기타
- `chatStore.js`: 초기 stage `'crawling'` → `'searching'` 변경
- `handlers.js`, `mockChatResponses.json`: mock 데이터 stage명 동기화

---

## Phase 6: 테스트 업데이트 ✅

### conftest.py 수정
- `WebSearchService.search`에 `fake_web_search` monkeypatch 추가
- 취득세/감면/서민주택 키워드에 대해 테스트용 WebSearchResult 반환

### test_chat_pipeline.py 수정
- `"searching"`, `"verifying"`, `"finalizing"` 등 새 stage 순서 검증
- `"웹 검색 완료"`, `"초안 작성 완료"` notice 메시지 검증
- `"검증 세부 지표"` 포함 확인

### 테스트 결과
- **40개 테스트 전체 통과** (3.62초)

---

## 수정 대상 파일 요약

| 파일 | 작업 | Phase |
|------|------|-------|
| `backend/app/config.py` | 웹검색/연구 설정 추가 | 1 |
| `backend/app/models/schemas.py` | WebSearchResult, VerificationHistory 추가 | 1 |
| `backend/app/services/web_search_service.py` | **신규** — DuckDuckGo 웹 검색 | 1 |
| `backend/app/prompts/web_draft_prompt.py` | **신규** — 웹 초안 프롬프트 | 2 |
| `backend/app/services/llm_service.py` | `generate_web_draft()` 추가 | 2 |
| `backend/app/prompts/gap_analysis_prompt.py` | **신규** — gap 분석 프롬프트 | 3 |
| `backend/app/services/gap_analyzer_service.py` | **신규** — gap 분석 서비스 | 3 |
| `backend/app/routers/chat.py` | 파이프라인 전면 재구성 | 4 |
| `backend/app/services/verification/source_verifier.py` | web_ 출처 스킵 | 4 |
| `backend/app/services/verification/final_generator.py` | 검증 이력 파라미터 + 프롬프트 | 4 |
| `frontend/src/components/layout/StatusStepper.jsx` | 새 stages | 5 |
| `frontend/src/stores/chatStore.js` | 초기 stage 변경 | 5 |
| `backend/requirements.txt` | `duckduckgo-search` 추가 | 1 |
| `tests/conftest.py` | web_search mock 추가 | 6 |
| `tests/test_chat_pipeline.py` | 새 stage 순서 테스트 | 6 |

## 의존 패키지
- `duckduckgo-search` — DuckDuckGo 비동기 웹 검색 (API 키 불필요)
