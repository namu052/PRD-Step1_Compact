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
        try:
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
        except Exception:
            return self._fallback_verify(draft_answer, crawl_results)

    def _fallback_verify(
        self, draft_answer: str, crawl_results: list[CrawlResult]
    ) -> list[SourceVerification]:
        cited_lines_by_source = self._collect_cited_lines_by_source(draft_answer)
        all_ids = list(cited_lines_by_source)

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

            cited_lines = cited_lines_by_source.get(sid, [])
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

            content_status = self._verify_cited_content(sid, cited_lines, result)
            if content_status != "verified":
                verifications.append(
                    SourceVerification(
                        source_id=sid,
                        title=result.title,
                        url=result.url,
                        status=content_status,
                        detail="인용한 수치 또는 비율이 원문과 일치하지 않음",
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

    def _collect_cited_lines_by_source(self, draft_answer: str) -> dict[str, list[str]]:
        lines_by_source: dict[str, list[str]] = {}
        for line in draft_answer.splitlines():
            cited_groups = re.findall(r"\[출처:\s*([^\]]+)\]", line)
            for group in cited_groups:
                for sid in group.split(","):
                    sid = sid.strip()
                    if not sid:
                        continue
                    lines_by_source.setdefault(sid, []).append(line)
        return lines_by_source

    def _verify_cited_content(
        self,
        source_id: str,
        cited_lines: list[str],
        source: CrawlResult,
    ) -> str:
        del source_id
        source_content = source.content.lower()
        normalized_source = re.sub(r"\s+", "", source_content)
        for line in cited_lines:
            amounts = re.findall(r"(\d+[억만천백]?원)", line)
            percentages = re.findall(r"(\d+(?:\.\d+)?%)", line)
            fractions = re.findall(r"(\d+분의\s*\d+)", line)
            for value in amounts + percentages:
                if not self._contains_numeric_value(value, source_content, normalized_source):
                    return "mismatch"
            for fraction in fractions:
                if not self._contains_numeric_value(fraction, source_content, normalized_source):
                    return "mismatch"
        return "verified"

    def _contains_numeric_value(self, value: str, source_content: str, normalized_source: str) -> bool:
        normalized_value = re.sub(r"\s+", "", value.lower())
        if normalized_value in normalized_source or value.lower() in source_content:
            return True

        percentage_match = re.fullmatch(r"(\d+(?:\.\d+)?)%", normalized_value)
        if percentage_match:
            number = percentage_match.group(1)
            equivalent_fraction = f"100분의{number}"
            return equivalent_fraction in normalized_source

        fraction_match = re.fullmatch(r"(\d+)분의(\d+)", normalized_value)
        if fraction_match and fraction_match.group(1) == "100":
            equivalent_percentage = f"{fraction_match.group(2)}%"
            return equivalent_percentage in normalized_source

        return False


source_verifier = SourceVerifier()
