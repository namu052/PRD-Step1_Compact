GAP_ANALYSIS_SYSTEM_PROMPT = """너는 지방세 답변 검증 전문가이다.
아래 제공된 [답변 초안]과 [검증 결과]를 분석하여 아직 검증되지 않았거나 미비한 부분을 식별하고,
추가 검색이 필요한 키워드를 생성하라."""

GAP_ANALYSIS_USER_PROMPT = """## 답변 초안
{draft_answer}

## 검증 결과
- 전체 신뢰도: {overall_confidence}
- 주장 신뢰도: {claim_confidence}
- 출처 신뢰도: {source_confidence}
- 치명 이슈: {critical_issues}
- 제거 필요 주장: {removed_claims}
- 수정 필요 주장: {modified_claims}
- 경고: {warnings}

## 검증 이력
{verification_history}

위 정보를 바탕으로:
1. 아직 검증되지 않은 주장이나 미비한 부분을 식별하라
2. 추가 검색에 사용할 구체적인 키워드를 생성하라
3. 추가 검증이 필요한지 판단하라

반드시 JSON 형식으로 응답하라."""

GAP_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "검증되지 않은 주장이나 미비한 부분 목록",
        },
        "search_queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "추가 검색 키워드 목록",
        },
        "should_continue": {
            "type": "boolean",
            "description": "추가 검증이 필요한지 여부",
        },
    },
    "required": ["gaps", "search_queries", "should_continue"],
    "additionalProperties": False,
}
