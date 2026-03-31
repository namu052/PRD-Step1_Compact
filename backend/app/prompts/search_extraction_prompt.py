KEYWORD_EXTRACTION_SYSTEM = """너는 한국 지방세 검색 키워드 추출 전문가이다.
사용자 질문에서 OLTA(지방세 법령정보시스템) 검색에 사용할 키워드를 추출하라.

규칙:
1. 핵심 세목(취득세, 재산세 등)과 쟁점(감면, 환급 등)을 분리 추출
2. 동의어/유사어를 확장 (예: 감면 -> 경감, 면제, 비과세)
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
