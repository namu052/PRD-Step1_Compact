import re

from app.config import get_settings
from app.models.schemas import CrawlResult
from app.models.verification import SourceVerification
from app.prompts.stage2_source_prompt import SOURCE_VERIFICATION_PROMPT
from app.services.openai_service import openai_service


SOURCE_VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "verifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["verified", "not_found", "mismatch", "expired"],
                    },
                    "detail": {"type": "string"},
                },
                "required": ["source_id", "title", "url", "status", "detail"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verifications"],
    "additionalProperties": False,
}


class SourceVerifier:
    async def verify(
        self, draft_answer: str, crawl_results: list[CrawlResult]
    ) -> list[SourceVerification]:
        settings = get_settings()
        if settings.use_mock_llm:
            return self._mock_verify(draft_answer, crawl_results)

        payload, _ = await openai_service.create_json(
            model=settings.openai_verification_model,
            system_prompt="너는 지방세 법령 출처 검증 전문가이다. 반드시 JSON schema만 출력하라.",
            user_prompt=SOURCE_VERIFICATION_PROMPT.format(
                draft_answer=draft_answer,
                crawl_results=openai_service.format_crawl_results(crawl_results),
            ),
            schema_name="source_verifications",
            schema=SOURCE_VERIFICATION_SCHEMA,
            temperature=0.0,
            max_tokens=1600,
        )
        return [
            SourceVerification(
                source_id=item["source_id"],
                title=item.get("title", ""),
                url=item.get("url", ""),
                status=item.get("status", "verified"),
                detail=item.get("detail", ""),
            )
            for item in payload.get("verifications", [])
        ]

    def _mock_verify(
        self, draft_answer: str, crawl_results: list[CrawlResult]
    ) -> list[SourceVerification]:
        source_ids = re.findall(r"\[출처:\s*([^\]]+)\]", draft_answer)
        all_ids = []
        for sid_group in source_ids:
            for sid in sid_group.split(","):
                sid = sid.strip()
                if sid and sid not in all_ids:
                    all_ids.append(sid)

        crawl_map = {result.id: result for result in crawl_results}
        verifications = []

        for sid in all_ids:
            if sid not in crawl_map:
                verifications.append(
                    SourceVerification(
                        source_id=sid,
                        status="not_found",
                        detail=f"크롤링 원본 데이터에 {sid}가 존재하지 않음",
                    )
                )
                continue

            result = crawl_map[sid]
            if "olta.re.kr" not in result.url:
                verifications.append(
                    SourceVerification(
                        source_id=sid,
                        title=result.title,
                        url=result.url,
                        status="expired",
                        detail="URL이 olta.re.kr 도메인이 아님",
                    )
                )
                continue

            cited_lines = [
                line for line in draft_answer.splitlines() if f"[출처: {sid}]" in line or f"[출처:{sid}]" in line
            ]
            expected_article = re.search(r"제(\d+)조", result.title)
            cited_articles = []
            for line in cited_lines:
                cited_articles.extend(re.findall(r"제(\d+)조", line))

            if expected_article and cited_articles and expected_article.group(1) not in cited_articles:
                verifications.append(
                    SourceVerification(
                        source_id=sid,
                        title=result.title,
                        url=result.url,
                        status="mismatch",
                        detail=f"초안의 조문 번호가 원본 {expected_article.group(0)}와 일치하지 않음",
                    )
                )
                continue

            verifications.append(
                SourceVerification(
                    source_id=sid,
                    title=result.title,
                    url=result.url,
                    status="verified",
                    detail="출처 확인됨",
                )
            )

        return verifications


source_verifier = SourceVerifier()
