import re

from app.config import get_settings
from app.models.schemas import CrawlResult
from app.models.verification import ContentClaim
from app.prompts.stage2_content_prompt import CONTENT_VERIFICATION_PROMPT
from app.services.openai_service import openai_service


KEYWORD_PATTERN = re.compile(
    r"(?:제?\d+조|제?\d+항|\d+[억만천백]?원|\d+%|\d+분의\s*\d+|취득세|재산세|감면|경감|면제|부동산|주택|영농조합법인|농업법인|서민주택)"
)

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
        if settings.use_mock_llm:
            return self._mock_verify(draft_answer, crawl_results)

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

    def _mock_verify(
        self, draft_answer: str, crawl_results: list[CrawlResult]
    ) -> list[ContentClaim]:
        crawl_map = {result.id: result for result in crawl_results}
        all_content = " ".join(result.content for result in crawl_results)
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
            relevant_content = " ".join(
                crawl_map[sid].content for sid in claim["cited"] if sid in crawl_map
            ) or all_content

            keywords = KEYWORD_PATTERN.findall(text)
            unique_keywords = list(dict.fromkeys(keywords))
            matched = sum(1 for keyword in unique_keywords if keyword in relevant_content)
            total = len(unique_keywords) if unique_keywords else 1

            contradicted = False
            if ("면제" in text or "100%" in text) and "100분의 50" in relevant_content:
                contradicted = True
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
            elif matched >= 2:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="supported",
                        confidence=0.85,
                        detail=f"핵심 키워드 {matched}/{total}개 일치",
                    )
                )
            elif matched >= 1:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="partial",
                        confidence=0.5,
                        detail=f"핵심 키워드 {matched}/{total}개 부분 일치",
                        corrected_text=f"{text} ⚠️ *일부 내용 확인 필요*",
                    )
                )
            else:
                results.append(
                    ContentClaim(
                        claim_text=text,
                        cited_sources=claim["cited"],
                        verification_status="unsupported",
                        confidence=0.2,
                        detail="크롤링 원본에 근거를 찾을 수 없음",
                    )
                )

        return results


content_verifier = ContentVerifier()
