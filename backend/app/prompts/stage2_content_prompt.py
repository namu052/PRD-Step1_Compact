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
