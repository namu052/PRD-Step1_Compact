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
