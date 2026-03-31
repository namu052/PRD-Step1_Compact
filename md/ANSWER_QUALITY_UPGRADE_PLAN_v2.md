# 답변 품질 고도화 구현 계획서 (v2)

## Context

AI 지방세 지식인 APP의 백엔드 답변 파이프라인은 구조적으로 완성되어 있으나, 핵심 품질 메커니즘이 얕다:

| 영역 | 현재 상태 | 문제점 |
|------|----------|--------|
| 검색 키워드 | TAX_TERMS 6개 + TOPIC_TERMS 8개 고정 매칭 | 세목 누락, 복합 질문 처리 불가 |
| 순위화 | 단순 word overlap (embedding 미사용) | 의미적 유사도 없음, 한국어 형태소 미처리 |
| 검증 | 키워드 존재 여부만 체크 | 모순 탐지 1패턴, 신뢰도 3단계 |
| 모델 | 전 단계 gpt-4o-mini | 초안/최종에 약한 모델 사용 |
| 프롬프트 | 인라인 하드코딩, 규칙 부족 | 수정 프롬프트 vague, few-shot 없음 |

이 플랜은 **6개 Phase**로 나누어 점진적으로 답변 품질을 고도화한다. 각 Phase는 독립 배포 가능하며, 기존 Mock 모드 테스트를 깨뜨리지 않는다.

**핵심 원칙**: Config First — 모든 하드코딩 상수를 설정으로 추출한 뒤 코드를 변경한다.

---

## 구현 순서 및 의존 관계

```
Phase 0 (Config 추출) ─┬─> Phase 1 (검색 고도화)     ← 최고 임팩트
                       ├─> Phase 2 (임베딩 순위화)
                       ├─> Phase 3 (검증 강화)
                       │       └─> Phase 4 (생성 품질) ← Phase 3 이후
                       └─> Phase 5 (근거 그룹 개선)    ← Phase 2 이후
```

| Phase | 예상 품질 향상 | 누적 |
|-------|--------------|------|
| 0: Config 추출 | 0% (기반) | 0% |
| 1: 검색 고도화 | 25-35% | 25-35% |
| 2: 임베딩 순위화 | 15-20% | 35-45% |
| 3: 검증 강화 | 15-20% | 45-55% |
| 4: 생성 품질 | 10-15% | 50-60% |
| 5: 근거 그룹 개선 | 5-10% | 55-65% |

---

## Phase 0: Config 추출 (기반 — 동작 변경 없음)

> 모든 하드코딩 상수를 `config.py`로 추출. 기본값은 현재 값과 동일하여 동작 변화 0%.

### 파일: `backend/app/config.py` (Settings 클래스, line 21 이후 추가)

```python
# --- 검색 ---
search_max_keywords: int = 4
search_use_llm_extraction: bool = True

# --- 순위화 ---
ranking_semantic_weight: float = 0.6
ranking_overlap_weight: float = 0.2
ranking_position_weight: float = 0.1
ranking_year_weight: float = 0.1
ranking_diversity_divisor: int = 6
embedding_content_limit: int = 1500

# --- 그룹핑 ---
grouping_similarity_high: float = 0.84
grouping_similarity_medium: float = 0.76
grouping_title_overlap_with_medium: float = 0.35
grouping_title_overlap_standalone: float = 0.55
grouping_content_limit: int = 1200
grouping_review_content_limit: int = 600

# --- 요약 ---
summary_content_limit: int = 900
summary_max_tokens: int = 900
openai_summarization_model: str = "gpt-4o-mini"
max_representative_sources: int = 4

# --- 생성 ---
draft_max_tokens: int = 1800
draft_temperature: float = 0.2
revision_max_tokens: int = 1800
revision_temperature: float = 0.1
final_max_tokens: int = 1800

# --- 검증 페널티 ---
aggregator_penalty_not_found: float = 0.3
aggregator_penalty_mismatch: float = 0.5
aggregator_penalty_expired: float = 0.4
aggregator_penalty_no_citation: float = 0.2
aggregator_slot_contradicted: float = 0.2
aggregator_slot_unused: float = 0.5
aggregator_slot_partial: float = 0.8

# --- 신뢰도 임계값 ---
confidence_very_high: float = 0.85
confidence_high: float = 0.7
confidence_medium: float = 0.4

# --- 검증 루프 ---
stagnation_threshold: float = 0.02
low_confidence_warning: float = 0.5

# --- content_verifier ---
cv_confidence_supported: float = 0.85
cv_confidence_partial: float = 0.5
cv_confidence_unsupported: float = 0.2
```

### 와이어링 대상 (Phase 0에서 함께 수행)

각 파일의 하드코딩 상수를 `settings.X`로 교체:

| 파일 | 교체 위치 | 상수 |
|------|----------|------|
| `search_service.py` | line 58 | `keywords[:4]` → `[:settings.search_max_keywords]` |
| `embedding_service.py` | line 79 | `limit // 6` → `limit // settings.ranking_diversity_divisor` |
| `evidence_group_service.py` | lines 96-101 | 0.84, 0.76, 0.35, 0.55 → settings |
| `evidence_group_service.py` | line 165, 203 | content[:1200], limit=600 → settings |
| `evidence_summary_service.py` | line 79, 90 | 900 → settings |
| `llm_service.py` | line 62, 113 | max_tokens=1800 → settings |
| `content_verifier.py` | lines 142-161 | 0.85/0.5/0.2 → settings |
| `verification_aggregator.py` | lines 16-24 | 0.3/0.5/0.4/0.2 → settings |
| `verification_aggregator.py` | lines 58-63 | 0.7/0.4 → settings |
| `final_generator.py` | line 44 | max_tokens=1800 → settings |

### 검증
```bash
cd backend && pytest -v    # 모든 테스트 통과 (동작 변화 없음)
cd frontend && npm run build && npm run lint
```

---

## Phase 1: 검색 고도화 (최고 임팩트)

> 검색이 파이프라인 입구. 여기서 놓친 소스는 이후 모든 단계에서 복구 불가.

### 1-1. 신규 파일: `backend/app/prompts/search_extraction_prompt.py`

LLM 기반 키워드 추출 프롬프트 + JSON 스키마:

```python
KEYWORD_EXTRACTION_SYSTEM = """너는 한국 지방세 검색 키워드 추출 전문가이다.
사용자 질문에서 OLTA(지방세 법령정보시스템) 검색에 사용할 키워드를 추출하라.

규칙:
1. 핵심 세목(취득세, 재산세 등)과 쟁점(감면, 환급 등)을 분리 추출
2. 동의어/유사어를 확장 (예: 감면 → 경감, 면제, 비과세)
3. 질문에 언급된 법령 조문이 있으면 포함
4. 최소 3개, 최대 8개 키워드
5. 검색 효율을 위해 2~6글자 키워드 우선"""

KEYWORD_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "keywords": {"type": "array", "items": {"type": "string"}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "legal_refs": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["keywords", "synonyms", "legal_refs"],
    "additionalProperties": False,
}
```

### 1-2. 수정: `backend/app/services/search_service.py`

**`build_search_plan()` (lines 38-63)** — LLM 추출 분기 추가:
```python
if settings.use_mock_llm:
    keywords = self._mock_extract(normalized)
elif settings.search_use_llm_extraction:
    keywords = await self._llm_extract(normalized)
else:
    keywords = self._extract_without_llm(normalized)
```

**새 메서드 `_llm_extract()`** (line 79 근처 삽입):
- `openai_service.create_json(model=settings.openai_verification_model)` 호출 (gpt-4o-mini, 비용 절약)
- keywords + synonyms + legal_refs 합산 후 중복 제거
- `[:settings.search_max_keywords]`로 제한
- 실패 시 `_extract_without_llm()` fallback

**TAX_TERMS / TOPIC_TERMS 확장** (lines 85-86):
```python
TAX_TERMS = ["취득세", "재산세", "등록면허세", "자동차세", "주민세", "지방세",
             "지방소득세", "지방교육세", "지역자원시설세", "레저세", "담배소비세"]
TOPIC_TERMS = ["감면", "환급", "신고", "납부", "비과세", "과세", "판례", "유권해석",
               "추징", "세율", "과세표준", "납세의무", "가산세", "경정청구",
               "유예", "연납", "분할납부", "불복", "심판"]
```

### 1-3. 크롤러 콘텐츠 추출 개선: `backend/app/services/crawler_service.py`

**마커 후보 확장** (lines 324-331):
```python
marker_candidates = [
    "질의요지", "회신", "답변요지", "결정요지", "판결요지",
    "관계법령", "주문", "이유", "본문정보",
    "사건번호", "처분내용", "청구취지", "참조조문",
]
```

**콘텐츠 제한** (line 340): `content[:5000]` → `content[:settings.crawler_content_limit]` (config에 `crawler_content_limit: int = 8000` 추가)

**노이즈 제거** (line 339 이후):
```python
noise_patterns = [
    r"Copyright.*$", r"개인정보.*처리방침", r"이용약관",
    r"상단으로\s*이동", r"관련\s*사이트", r"고객센터.*\d{3,4}",
]
for pattern in noise_patterns:
    content = re.sub(pattern, "", content, flags=re.MULTILINE)
```

### 테스트 변경
- `test_search.py`: 확장된 TAX_TERMS/TOPIC_TERMS 커버리지 테스트 추가
- `test_chat_pipeline.py`: 기존 테스트 유지 (mock 모드는 변경 없음)

### 검증
```bash
pytest -v
# 실제 LLM 모드: USE_MOCK_LLM=false 로 "생애최초 주택 취득세 감면 요건" 질문 → 키워드 비교
```

---

## Phase 2: 임베딩 기반 순위화

> 현재 embedding_service는 이름만 embedding이고 실제로는 word overlap.

### 2-1. 수정: `backend/app/services/embedding_service.py`

**`rank_results()` (lines 6-32)** — 실제 임베딩 모드 추가:

```python
async def rank_results(self, question, results, top_k=None, ...):
    settings = get_settings()
    limit = top_k or settings.answer_context_top_k
    if not results:
        return []
    if settings.use_mock_crawler:
        return results[:limit]  # Mock: 기존 동작 유지

    # 실제 임베딩 생성
    doc_texts = [self._build_embedding_text(r) for r in results]
    all_texts = [question] + doc_texts
    embeddings = await openai_service.create_embeddings(
        all_texts, settings.openai_embedding_model
    )
    q_emb = embeddings[0]
    doc_embs = embeddings[1:]

    scored = []
    for i, result in enumerate(results):
        semantic = openai_service.cosine_similarity(q_emb, doc_embs[i])
        overlap = self._term_overlap_score(question, result)
        year_bonus = self._year_bonus(result.document_year, ...)
        combined = (
            semantic * settings.ranking_semantic_weight
            + overlap * settings.ranking_overlap_weight
            + result.relevance_score * settings.ranking_position_weight
            + year_bonus * settings.ranking_year_weight
        )
        scored.append((combined, result))

    scored.sort(key=lambda x: x[0], reverse=True)
    return self._select_diverse_results([r for _, r in scored], limit)
```

**새 헬퍼 메서드**:
- `_build_embedding_text(result)`: `f"{result.title} {result.preview} {result.content[:settings.embedding_content_limit]}"`
- `_term_overlap_score(question, result)`: 기존 로직을 별도 메서드로 분리

**다양성 쿼터** (line 79): `max(1, limit // 6)` → `max(2, limit // settings.ranking_diversity_divisor)`

### 테스트 변경
- `test_search.py`: `test_rank_results_prefers_specific_year` 유지 (mock 모드)
- 새 테스트: `test_rank_results_embedding_mode` (mock_crawler=False, 임베딩 호출 mock)

### 검증
```bash
pytest -v
# 실제 모드: 동일 결과셋에 대해 old vs new 순위 비교
# 임베딩 호출 레이턴시 측정 (48개 결과 < 500ms 목표)
```

---

## Phase 3: 검증 파이프라인 강화

> 검증이 모든 라운드에 영향. 더 많은 패턴 탐지 + 4단계 신뢰도 + 정체 감지.

### 3-1. content_verifier.py — KEYWORD_PATTERN 확장

**현재** (lines 10-12): 11개 키워드
**변경**:
```python
KEYWORD_PATTERN = re.compile(
    r"(?:"
    r"제?\d+조(?:의\d+)?(?:\s*제?\d+항)?(?:\s*제?\d+호)?"
    r"|\d+[억만천백]?원"
    r"|\d+(?:\.\d+)?%"
    r"|\d+분의\s*\d+"
    r"|취득세|재산세|등록면허세|자동차세|주민세|지방세"
    r"|지방소득세|지방교육세|지역자원시설세"
    r"|감면|경감|면제|비과세|추징|환급|가산세"
    r"|부동산|주택|토지|건축물"
    r"|납기|신고기한|납부기한|과세표준|세율|세액"
    r")"
)
```

### 3-2. content_verifier.py — 모순 탐지 확장

**현재** (lines 126-130): 1개 패턴만
**변경**: CONTRADICTION_PAIRS 리스트 추가:
```python
CONTRADICTION_PAIRS = [
    ("면제", "100분의 50"),
    ("면제", "경감"),
    ("비과세", "감면"),
    ("100%", "100분의 50"),
    ("전액", "일부"),
    ("의무", "임의"),
    ("필수", "선택"),
]
```

모순 탐지 로직 (lines 125-131 교체):
```python
contradicted = False
for term_a, term_b in CONTRADICTION_PAIRS:
    if term_a in text and term_b in relevant_content and term_b not in text:
        contradicted = True
        break
    if term_b in text and term_a in relevant_content and term_a not in text:
        contradicted = True
        break
# 조문 번호 불일치
article_numbers = re.findall(r"제(\d+)조", text)
if article_numbers and not any(f"제{num}조" in relevant_content for num in article_numbers):
    contradicted = True
```

### 3-3. content_verifier.py — 신뢰도 세분화

**lines 142-161**: 3+키워드 매칭 분기 추가:
```python
if contradicted:
    status, confidence = "hallucinated", 0.0
elif matched >= 3:
    status, confidence = "supported", 0.90
elif matched >= 2:
    status, confidence = "supported", settings.cv_confidence_supported  # 0.85
elif matched >= 1:
    status, confidence = "partial", settings.cv_confidence_partial      # 0.5
else:
    status, confidence = "unsupported", settings.cv_confidence_unsupported  # 0.2
```

### 3-4. source_verifier.py — content-level 매칭

**lines 109-124 이후** — 인용 수치 검증 메서드 추가:
```python
def _verify_cited_content(self, source_id, cited_lines, source):
    """인용 문장의 금액/비율/분수가 원본에 실제 존재하는지 확인"""
    source_content = source.content.lower()
    for line in cited_lines:
        amounts = re.findall(r"(\d+[억만천백]?원)", line)
        percentages = re.findall(r"(\d+(?:\.\d+)?%)", line)
        fractions = re.findall(r"(\d+분의\s*\d+)", line)
        for v in amounts + percentages:
            if v not in source_content:
                return "mismatch"
        for frac in fractions:
            if re.sub(r"\s+", "", frac) not in re.sub(r"\s+", "", source_content):
                return "mismatch"
    return "verified"
```

### 3-5. verification_aggregator.py — 4단계 신뢰도 + 가중 평균

**신뢰도 라벨** (lines 58-63):
```python
if overall_confidence >= settings.confidence_very_high:   # 0.85
    label = "매우 높음"
elif overall_confidence >= settings.confidence_high:       # 0.7
    label = "높음"
elif overall_confidence >= settings.confidence_medium:     # 0.4
    label = "보통"
else:
    label = "낮음"
```

**가중 평균** (line 57):
```python
def _claim_weight(claim):
    weight = 1.0
    if re.search(r"제\d+조", claim.claim_text):
        weight += 0.3   # 조문 인용 → 더 중요
    if re.search(r"\d+[억만천백]?원|\d+%|\d+분의\s*\d+", claim.claim_text):
        weight += 0.2   # 수치 포함 → 더 중요
    return weight
```

### 3-6. grouped_answer_verifier.py — 검증 개선

**lines 63-75**: 키워드 12개 제한 → 30개로 확장, ratio 기반 판정:
```python
all_text = f"{slot.title} {slot.summary} {slot.conclusion} " + \
           " ".join(slot.key_points) + " ".join(slot.exceptions)
terms = {t for t in re.split(r"[\s,/()-]+", all_text) if len(t) >= 2}
terms = list(terms)[:30]

overlap = sum(1 for t in terms if t.lower() in answer_text)
ratio = overlap / len(terms) if terms else 0

if ratio >= 0.3:
    status, confidence = "supported", 0.85
elif ratio >= 0.15:
    status, confidence = "partial", 0.55
else:
    status, confidence = "unused", 0.2
```

### 3-7. chat.py — 정체 감지

**`run_verification_cycle()` (lines 48-79)** 수정:
```python
prev_confidence = 0.0
for round_index in range(max_rounds):
    verification_result = await verify_answer(...)

    if verification_result.overall_confidence >= settings.verification_target_confidence:
        break

    # 정체 감지: 개선 < threshold면 조기 종료
    if round_index > 0:
        improvement = verification_result.overall_confidence - prev_confidence
        if improvement < settings.stagnation_threshold:
            break
    prev_confidence = verification_result.overall_confidence

    if round_index == max_rounds - 1:
        break
    current_draft = await llm_service.revise_draft(...)
```

**`run_finalization_cycle()` (lines 82-132)** 에도 동일 패턴 적용.

### 3-8. 프론트엔드: ConfidenceBadge.jsx — 4단계 대응

```javascript
const BADGE_STYLES = {
  '매우 높음': 'bg-emerald-100 text-emerald-700',
  높음: 'bg-green-100 text-green-700',
  보통: 'bg-yellow-100 text-yellow-700',
  낮음: 'bg-red-100 text-red-700',
}
const BADGE_ICONS = {
  '매우 높음': '🟢',
  높음: '🔵',
  보통: '🟡',
  낮음: '🔴',
}
// hint: '높음' → '주요 내용은 근거 확인 완료', '매우 높음' → null
```

### 테스트 변경
- `test_aggregator.py`: `"높음"` → `in ("높음", "매우 높음")`, 4단계 테스트 추가
- `test_content_verifier.py`: 모순 패턴별 테스트 추가
- `test_chat_pipeline.py`: confidence 라벨 4단계 대응

### 검증
```bash
pytest -v
cd frontend && npm run build && npm run lint
```

---

## Phase 4: 생성 품질 개선

> 모델 업그레이드 + 프롬프트 분리/강화. Phase 3(4단계 신뢰도) 이후 실행.

### 4-1. 모델 기본값 변경: `config.py`

```python
openai_model: str = "gpt-4o"              # was gpt-4o-mini (초안 생성)
openai_verification_model: str = "gpt-4o-mini"  # 유지 (비용 절약)
openai_final_model: str = "gpt-4o"        # was gpt-4o-mini (최종 답변)
```

비용 민감 환경은 `.env`에서 `OPENAI_MODEL=gpt-4o-mini`로 오버라이드 가능.

### 4-2. 신규 파일: `backend/app/prompts/revision_prompt.py`

`llm_service.py` lines 81-93의 인라인 프롬프트를 분리:

```python
REVISION_SYSTEM_PROMPT = """너는 한국 지방세 전문 AI 상담원이다.
검증 피드백을 반영해 답변 초안을 수정하라.

규칙:
1. unsupported, hallucinated 주장은 삭제 또는 수정
2. partial 주장은 더 보수적으로 수정
3. 근거 묶음 구조(결론, 적용범위, 예외, 충돌) 유지
4. 미활용 근거 묶음이 있으면 반영 여부 판단
5. 제공된 자료에 없는 사실 추가 금지
6. 각 사실 문장에 [출처: source_id] 태그 유지
7. 법령 조문은 조·항·호 단위까지 원문 근거 있는 경우만 명시
8. 금액/비율/기한은 원문 확인값만 사용
9. Markdown 형식 유지
10. '📌 참고 출처' 섹션 유지
11. 지적된 부분만 교체, 구조 최대 유지
12. 삭제된 자리에 빈 줄 남기지 말고 자연스럽게 이어 붙이기"""
```

### 4-3. llm_service.py 수정

- **import 추가**: `from app.prompts.revision_prompt import REVISION_SYSTEM_PROMPT, REVISION_USER_PROMPT`
- **lines 81-93**: 인라인 프롬프트 → `REVISION_SYSTEM_PROMPT` 상수로 교체
- **line 62**: `max_tokens=1800` → `settings.draft_max_tokens`
- **line 59**: `temperature=0.2` → `settings.draft_temperature`
- **line 113**: `max_tokens=1800` → `settings.revision_max_tokens`
- **lines 172-177**: 인용 추출 regex 강화: `\[출처:\s*{re.escape(result.id)}\s*\]` + 콤마 분리 케이스

### 4-4. 초안 프롬프트 강화: `grouped_answer_prompt.py`

기존 규칙 10개 이후 추가:
```
11. 결론에서 확정적 표현이 불가능하면 조건부 결론과 분기 구조 명시
12. 법령 조문은 조·항·호 단위까지 명시 (예: 지방세특례제한법 제36조 제1항 제1호)
13. 금액, 비율, 기한 등 수치는 근거 묶음 원문 확인값만 사용
14. 동일 쟁점에 서로 다른 해석이 있으면 각각의 근거와 한계를 병렬 제시
```

### 4-5. 최종 답변 프롬프트 강화: `stage2_final_prompt.py`

기존 규칙 8개 이후 추가:
```
9. 신뢰도 0.5 미만이면 답변 상단에 경고 표시
10. "⚠️ 확인 필요" 마커 3개 이상이면 전체 불확실성 안내 추가
11. unused 근거 묶음이 있으면 "추가 참고" 섹션에 결론 요약
12. 빈 섹션 제거
13. 같은 출처 3회 이상 반복 인용 시 대표 1회로 통합
14. 불확실성 섹션은 반드시 유지하고 warnings 반영
```

### 4-6. final_generator.py — 낮은 신뢰도 경고

**line 46 이후**:
```python
if verification_result.overall_confidence < settings.low_confidence_warning:
    warning = "\n\n---\n⚠️ **주의**: 이 답변의 신뢰도가 낮습니다. 실무 적용 전 반드시 원문 확인 바랍니다.\n"
    if verification_result.warnings:
        warning += "주요 확인 사항:\n"
        for w in verification_result.warnings[:5]:
            warning += f"- {w}\n"
    answer = answer + warning
```

**lines 48-50**: `except Exception` → 구체적 예외 캐치 + `logger.exception()` 추가.

### 4-7. 근거 요약 프롬프트 강화: `evidence_summary_prompt.py`

규칙 추가:
```
14. summary는 원문에서 직접 인용 가능한 법령 조문이나 해석 요지를 포함할 것
15. conclusion에서 확정이 불가능하면 조건부 결론과 이유를 적을 것
```

Few-shot 예시 1개 추가 (규칙 이후, `[질문]` 이전).

### 4-8. evidence_summary_service.py 파라미터 확대

- line 79: `content_limit=900` → `settings.summary_content_limit`
- line 81: `model=settings.openai_model` → `settings.openai_summarization_model`
- line 90: `max_tokens=900` → `settings.summary_max_tokens`
- line 150, 162: `4` → `settings.max_representative_sources`

### 검증
```bash
pytest -v
cd frontend && npm run build
# 실제 모드: "취득세 감면 대상" 질문으로 답변 품질 before/after 비교
```

---

## Phase 5: 근거 그룹 개선

> Phase 2(임베딩) 이후 실행. 클러스터링 품질 향상.

### 5-1. evidence_group_service.py 수정

**TAX_TERMS / TOPIC_TERMS** (lines 10-25): `settings.search_tax_terms` / `settings.search_topic_terms` 사용 (Phase 1에서 확장된 리스트)

**content 윈도우 확대**:
- `_build_document_text()` line 165: → `settings.grouping_content_limit`
- `_review_cluster()` line 203: → `settings.grouping_review_content_limit`

**TOPIC_TERMS 확장** (lines 11-25): `"과세표준", "세율", "납세의무자", "가산세", "경정청구", "불복", "심판", "판결"` 추가

### 5-2. evidence_summary_service.py — 신뢰도 계산 개선

**lines 109-113**:
```python
base_conf = sum(item.relevance_score for item in rep_sources) / max(len(rep_sources), 1)
type_bonus = min(0.1, len(set(item.type for item in rep_sources)) * 0.03)
confidence = round(min(1.0, base_conf + type_bonus), 2)
```

### 테스트 변경
- `test_evidence_group_service.py`: 다양한 문서 수/타입 조합 테스트 추가

### 검증
```bash
pytest -v
# "취득세와 재산세 감면 차이" 복합 질문으로 그룹핑 결과 비교
```

---

## 수정 파일 전체 목록

| Phase | 파일 | 변경 유형 |
|-------|------|----------|
| 0 | `backend/app/config.py` | 설정 필드 대량 추가 |
| 0 | 8개 서비스 파일 | 하드코딩 → settings 참조 |
| 1 | `backend/app/prompts/search_extraction_prompt.py` | **신규** |
| 1 | `backend/app/services/search_service.py` | LLM 추출 + 용어 확장 |
| 1 | `backend/app/services/crawler_service.py` | 마커 확장 + 노이즈 제거 |
| 2 | `backend/app/services/embedding_service.py` | 실제 임베딩 순위화 |
| 3 | `backend/app/services/verification/content_verifier.py` | 패턴 + 모순 + 신뢰도 |
| 3 | `backend/app/services/verification/source_verifier.py` | content-level 매칭 |
| 3 | `backend/app/services/verification/grouped_answer_verifier.py` | ratio 기반 검증 |
| 3 | `backend/app/services/verification/verification_aggregator.py` | 4단계 + 가중 평균 |
| 3 | `backend/app/routers/chat.py` | 정체 감지 |
| 3 | `frontend/src/components/chat/ConfidenceBadge.jsx` | 4단계 UI |
| 4 | `backend/app/prompts/revision_prompt.py` | **신규** |
| 4 | `backend/app/services/llm_service.py` | 프롬프트 분리 + config |
| 4 | `backend/app/prompts/grouped_answer_prompt.py` | 규칙 추가 |
| 4 | `backend/app/prompts/stage2_final_prompt.py` | 규칙 추가 |
| 4 | `backend/app/prompts/evidence_summary_prompt.py` | 규칙 + few-shot |
| 4 | `backend/app/services/evidence_summary_service.py` | 파라미터 + 모델 |
| 4 | `backend/app/services/verification/final_generator.py` | 경고 + 로깅 |
| 5 | `backend/app/services/evidence_group_service.py` | 용어 + content 확대 |

## 테스트 수정 목록

| 파일 | 변경 |
|------|------|
| `test_aggregator.py` | 4단계 신뢰도 라벨 대응 |
| `test_content_verifier.py` | 모순 패턴 테스트 추가 |
| `test_chat_pipeline.py` | confidence 라벨 4단계 대응 |
| `test_search.py` | 확장 용어 + LLM 추출 테스트 |
| `test_evidence_group_service.py` | 다양 조합 테스트 |

## 최종 E2E 검증

```bash
# 1. Mock 모드 전체 테스트
cd backend && pytest -v

# 2. 프론트엔드 빌드
cd frontend && npm run build && npm run lint

# 3. Mock E2E
USE_MOCK_CRAWLER=true USE_MOCK_LLM=true uvicorn app.main:app --port 8000
# → "취득세 감면 대상" 질문 → 5단계 스테퍼 → 답변 → 신뢰도 배지 4단계 확인

# 4. 실제 LLM E2E (API 키 필요)
USE_MOCK_CRAWLER=true USE_MOCK_LLM=false uvicorn app.main:app --port 8000
# → 답변 품질 비교, notice로 검증 라운드 추적, 낮은 신뢰도 경고 확인
```
