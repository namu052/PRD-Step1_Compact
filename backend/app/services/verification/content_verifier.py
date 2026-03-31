import re

from app.config import get_settings
from app.models.schemas import CrawlResult
from app.models.verification import ContentClaim
from app.prompts.stage2_content_prompt import CONTENT_VERIFICATION_PROMPT
from app.services.openai_service import openai_service


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
ASSERTIVE_CLAIM_PATTERN = re.compile(
    r"(?:"
    r"제?\d+조"
    r"|\d+[억만천백]?원"
    r"|\d+(?:\.\d+)?%"
    r"|\d+분의\s*\d+"
    r"|적용(?:됩니다|된다|됨)"
    r"|경감(?:됩니다|된다|됨)"
    r"|면제(?:됩니다|된다|됨)"
    r"|비과세(?:입니다|된다|됨)"
    r"|추징(?:됩니다|된다|됨)"
    r"|납부(?:합니다|한다|됨)"
    r"|해당(?:합니다|한다|됨)"
    r")"
)

CONTRADICTION_PAIRS = [
    ("면제", "100분의 50"),
    ("면제", "경감"),
    ("비과세", "감면"),
    ("100%", "100분의 50"),
    ("전액", "일부"),
    ("의무", "임의"),
    ("필수", "선택"),
]

CONTENT_VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "cited_sources": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "status": {
                        "type": "string",
                        "enum": ["supported", "partial", "unsupported", "hallucinated"],
                    },
                    "confidence": {"type": "number"},
                    "detail": {"type": "string"},
                    "corrected_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                    },
                },
                "required": [
                    "claim_text",
                    "cited_sources",
                    "status",
                    "confidence",
                    "detail",
                    "corrected_text",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["claims"],
    "additionalProperties": False,
}


class ContentVerifier:
    async def verify(
        self, draft_answer: str, crawl_results: list[CrawlResult]
    ) -> list[ContentClaim]:
        settings = get_settings()
        try:
            payload, _ = await openai_service.create_json(
                model=settings.openai_verification_model,
                system_prompt="너는 지방세 답변 내용 검증 전문가이다. 반드시 JSON schema만 출력하라.",
                user_prompt=CONTENT_VERIFICATION_PROMPT.format(
                    draft_answer=draft_answer,
                    crawl_results=openai_service.format_crawl_results(crawl_results),
                ),
                schema_name="content_verifications",
                schema=CONTENT_VERIFICATION_SCHEMA,
                temperature=0.0,
                max_tokens=2200,
            )
            return [
                ContentClaim(
                    claim_text=item["claim_text"],
                    cited_sources=item.get("cited_sources", []),
                    verification_status=item.get("status", "unsupported"),
                    confidence=float(item.get("confidence", 0.0)),
                    detail=item.get("detail", ""),
                    corrected_text=item.get("corrected_text"),
                )
                for item in payload.get("claims", [])
            ]
        except Exception:
            return self._fallback_verify(draft_answer, crawl_results)

    def _fallback_verify(
        self, draft_answer: str, crawl_results: list[CrawlResult]
    ) -> list[ContentClaim]:
        crawl_map = {result.id: result for result in crawl_results}
        all_content = " ".join(result.content for result in crawl_results)
        settings = get_settings()
        claims = []

        for line in draft_answer.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("---") or line.startswith("📌") or line.startswith(">"):
                continue

            clean_line = re.sub(r"\[출처:\s*[^\]]+\]", "", line).strip()
            clean_line = re.sub(r"\*+", "", clean_line).strip()
            if len(clean_line) < 10:
                continue

            cited_groups = re.findall(r"\[출처:\s*([^\]]+)\]", line)
            cited_ids = []
            for group in cited_groups:
                for sid in group.split(","):
                    sid = sid.strip()
                    if sid:
                        cited_ids.append(sid)

            claims.append({"text": clean_line, "cited": cited_ids})

        results = []
        for claim in claims:
            text = claim["text"]
            cited_content = " ".join(
                crawl_map[sid].content for sid in claim["cited"] if sid in crawl_map
            )
            relevant_content = cited_content or all_content

            keywords = KEYWORD_PATTERN.findall(text)
            unique_keywords = list(dict.fromkeys(keywords))
            matched = sum(1 for keyword in unique_keywords if keyword in relevant_content)
            total = len(unique_keywords) if unique_keywords else 1
            has_assertive_pattern = bool(ASSERTIVE_CLAIM_PATTERN.search(text))
            cited_source_count = len([sid for sid in claim["cited"] if sid in crawl_map])

            contradicted = False
            for term_a, term_b in CONTRADICTION_PAIRS:
                if term_a in text and term_b in relevant_content and term_b not in text:
                    contradicted = True
                    break
                if term_b in text and term_a in relevant_content and term_a not in text:
                    contradicted = True
                    break
            article_numbers = re.findall(r"제(\d+)조", text)
            if article_numbers and not any(f"제{number}조" in relevant_content for number in article_numbers):
                contradicted = True

            if contradicted:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="hallucinated",
                        confidence=0.0,
                        detail="원본 데이터와 모순됨",
                    )
                )
            elif has_assertive_pattern and cited_source_count == 0:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="unsupported",
                        confidence=0.05,
                        detail="단정적 주장이나 수치가 있으나 연결된 출처가 없음",
                        corrected_text=f"{text} ⚠️ *직접 근거 출처를 다시 지정해야 함*",
                    )
                )
            elif matched >= 3:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="supported",
                        confidence=0.9,
                        detail=f"핵심 키워드 {matched}/{total}개 강하게 일치",
                    )
                )
            elif matched >= 2:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="supported",
                        confidence=settings.cv_confidence_supported,
                        detail=f"핵심 키워드 {matched}/{total}개 일치",
                    )
                )
            elif matched >= 1:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="partial",
                        confidence=settings.cv_confidence_partial if cited_source_count > 0 else 0.3,
                        detail=(
                            f"핵심 키워드 {matched}/{total}개 부분 일치"
                            if cited_source_count > 0
                            else f"핵심 키워드 {matched}/{total}개만 일치하고 직접 출처 연결이 약함"
                        ),
                        corrected_text=f"{text} ⚠️ *일부 내용 확인 필요*",
                    )
                )
            else:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="unsupported",
                        confidence=settings.cv_confidence_unsupported,
                        detail="크롤링 원본에 근거를 찾을 수 없음",
                    )
                )

        return results


content_verifier = ContentVerifier()
