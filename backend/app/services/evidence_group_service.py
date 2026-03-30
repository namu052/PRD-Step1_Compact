import re
from collections import Counter

from app.config import get_settings
from app.models.evidence import EvidenceGroup
from app.models.schemas import CrawlResult
from app.services.openai_service import openai_service


TAX_TERMS = ["취득세", "재산세", "등록면허세", "자동차세", "주민세", "지방세"]
TOPIC_TERMS = [
    "감면",
    "면제",
    "추징",
    "환급",
    "생애최초",
    "농업법인",
    "영농조합법인",
    "학교법인",
    "프로젝트금융투자회사",
    "직장어린이집",
    "임대주택",
    "전세사기",
    "창업",
]

GROUP_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {"type": "string"},
        "rationale": {"type": "string"},
        "primary_tax": {"type": "string"},
        "primary_topic": {"type": "string"},
        "review_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "representative_source_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "theme",
        "rationale",
        "primary_tax",
        "primary_topic",
        "review_notes",
        "representative_source_ids",
    ],
    "additionalProperties": False,
}


class EvidenceGroupService:
    async def group(self, question: str, crawl_results: list[CrawlResult]) -> list[EvidenceGroup]:
        settings = get_settings()
        if not crawl_results:
            return []
        if settings.use_mock_llm:
            return self._group_by_heuristics(question, crawl_results)
        return await self._group_with_embeddings(question, crawl_results)

    async def _group_with_embeddings(
        self,
        question: str,
        crawl_results: list[CrawlResult],
    ) -> list[EvidenceGroup]:
        settings = get_settings()
        texts = [self._build_document_text(question, result) for result in crawl_results]
        embeddings = await openai_service.create_embeddings(texts, settings.openai_embedding_model)

        parents = list(range(len(crawl_results)))

        def find(index: int) -> int:
            while parents[index] != index:
                parents[index] = parents[parents[index]]
                index = parents[index]
            return index

        def union(left: int, right: int) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                parents[right_root] = left_root

        for left in range(len(crawl_results)):
            for right in range(left + 1, len(crawl_results)):
                score = openai_service.cosine_similarity(embeddings[left], embeddings[right])
                same_tax = self._extract_tax(crawl_results[left]) == self._extract_tax(crawl_results[right])
                shared_topics = bool(
                    set(self._extract_topics(crawl_results[left])) & set(self._extract_topics(crawl_results[right]))
                )
                title_overlap = self._title_overlap(crawl_results[left].title, crawl_results[right].title)

                if score >= 0.84:
                    union(left, right)
                elif score >= 0.76 and same_tax and (shared_topics or title_overlap >= 0.35):
                    union(left, right)
                elif same_tax and title_overlap >= 0.55:
                    union(left, right)

        clusters: dict[int, list[CrawlResult]] = {}
        for index, result in enumerate(crawl_results):
            clusters.setdefault(find(index), []).append(result)

        groups = []
        for group_index, items in enumerate(clusters.values(), start=1):
            items = sorted(items, key=lambda item: item.relevance_score, reverse=True)
            cluster_review = await self._review_cluster(question, items)
            groups.append(
                EvidenceGroup(
                    group_id=f"group_{group_index:03d}",
                    theme=cluster_review["theme"],
                    rationale=cluster_review["rationale"],
                    source_ids=[item.id for item in items],
                    representative_source_ids=self._select_representatives(
                        items,
                        cluster_review["representative_source_ids"],
                    ),
                    primary_tax=cluster_review["primary_tax"],
                    primary_topic=cluster_review["primary_topic"],
                    source_types=sorted({item.type for item in items}),
                    review_notes=cluster_review["review_notes"][:4],
                )
            )
        return groups

    def _group_by_heuristics(
        self,
        question: str,
        crawl_results: list[CrawlResult],
    ) -> list[EvidenceGroup]:
        groups: dict[str, EvidenceGroup] = {}
        for result in crawl_results:
            theme = self._build_theme(question, result)
            key = self._build_group_key(theme, result)
            group = groups.get(key)
            if not group:
                group = EvidenceGroup(
                    group_id=f"group_{len(groups) + 1:03d}",
                    theme=theme,
                    rationale=f"{result.type} 문서 중 동일 쟁점으로 분류된 근거 묶음",
                    primary_tax=self._extract_tax(result),
                    primary_topic=self._extract_topics(result)[0],
                    source_types=[result.type],
                )
                groups[key] = group

            group.source_ids.append(result.id)
            if result.id not in group.representative_source_ids and len(group.representative_source_ids) < 3:
                group.representative_source_ids.append(result.id)
            if result.type not in group.source_types:
                group.source_types.append(result.type)
        return list(groups.values())

    def _build_document_text(self, question: str, result: CrawlResult) -> str:
        return "\n".join(
            [
                f"question: {question}",
                f"type: {result.type}",
                f"title: {result.title}",
                f"preview: {result.preview}",
                f"content: {result.content[:1200]}",
            ]
        )

    def _build_cluster_theme(self, question: str, items: list[CrawlResult]) -> str:
        taxes = [self._extract_tax(item) for item in items]
        topics = [topic for item in items for topic in self._extract_topics(item)]
        tax = self._most_common_nonempty(taxes) or self._first_match(question, TAX_TERMS) or items[0].type
        topic = self._most_common_nonempty(topics) or self._first_match(question, TOPIC_TERMS) or self._fallback_topic(items[0].title)
        return f"{tax} {topic}".strip()

    def _build_cluster_rationale(self, items: list[CrawlResult]) -> str:
        types = ", ".join(sorted({item.type for item in items}))
        return f"{types} 문서를 유사 쟁점으로 군집화한 근거 묶음"

    async def _review_cluster(self, question: str, items: list[CrawlResult]) -> dict:
        settings = get_settings()
        theme = self._build_cluster_theme(question, items)
        rationale = self._build_cluster_rationale(items)
        primary_tax = self._most_common_nonempty([self._extract_tax(item) for item in items]) or ""
        primary_topic = self._most_common_nonempty(
            [topic for item in items for topic in self._extract_topics(item)]
        ) or ""
        representative_ids = self._select_representatives(items)
        default_payload = {
            "theme": theme,
            "rationale": rationale,
            "primary_tax": primary_tax,
            "primary_topic": primary_topic,
            "review_notes": [
                f"{len(items)}건 문서가 유사 쟁점으로 묶였습니다.",
                f"문서 유형: {', '.join(sorted({item.type for item in items}))}",
            ],
            "representative_source_ids": representative_ids,
        }

        if settings.use_mock_llm or len(items) <= 1:
            return default_payload

        cluster_documents = openai_service.format_crawl_results(items[:8], content_limit=600)
        try:
            payload, _ = await openai_service.create_json(
                model=settings.openai_verification_model,
                system_prompt="너는 지방세 근거 문서 군집 검토자이다. 같은 쟁점으로 묶인 문서의 대표 주제와 주의점을 JSON으로 정리하라.",
                user_prompt=(
                    f"질문: {question}\n\n"
                    f"가설 주제: {theme}\n"
                    f"가설 근거: {rationale}\n\n"
                    f"[후보 문서]\n{cluster_documents}\n\n"
                    "문서들이 같은 쟁점으로 묶여도 되는지 검토하고, 대표 주제와 주의점을 정리하라."
                ),
                schema_name="evidence_group_review",
                schema=GROUP_REVIEW_SCHEMA,
                temperature=0.0,
                max_tokens=700,
            )
        except Exception:
            return default_payload

        payload["representative_source_ids"] = self._select_representatives(
            items,
            payload.get("representative_source_ids", []),
        )
        if not payload.get("theme"):
            payload["theme"] = theme
        if not payload.get("rationale"):
            payload["rationale"] = rationale
        if not payload.get("primary_tax"):
            payload["primary_tax"] = primary_tax
        if not payload.get("primary_topic"):
            payload["primary_topic"] = primary_topic
        return payload

    def _extract_tax(self, result: CrawlResult) -> str:
        haystack = f"{result.title} {result.preview} {result.content[:500]}"
        return self._first_match(haystack, TAX_TERMS) or result.type

    def _extract_topics(self, result: CrawlResult) -> list[str]:
        haystack = f"{result.title} {result.preview} {result.content[:600]}"
        topics = [term for term in TOPIC_TERMS if term in haystack]
        return topics or [self._fallback_topic(result.title)]

    def _title_overlap(self, left: str, right: str) -> float:
        left_tokens = {token for token in re.split(r"[\s/(),\-]+", left) if len(token) >= 2}
        right_tokens = {token for token in re.split(r"[\s/(),\-]+", right) if len(token) >= 2}
        if not left_tokens or not right_tokens:
            return 0.0
        intersection = len(left_tokens & right_tokens)
        union = len(left_tokens | right_tokens)
        return intersection / union if union else 0.0

    def _build_theme(self, question: str, result: CrawlResult) -> str:
        haystack = f"{question} {result.title} {result.preview} {result.content[:500]}"
        tax = self._first_match(haystack, TAX_TERMS) or result.type
        topic = self._first_match(haystack, TOPIC_TERMS) or self._fallback_topic(result.title)
        return f"{tax} {topic}".strip()

    def _build_group_key(self, theme: str, result: CrawlResult) -> str:
        tax = self._extract_tax(result)
        topic = self._extract_topics(result)[0]
        return f"{tax}|{topic}"

    def _first_match(self, text: str, candidates: list[str]) -> str | None:
        for candidate in candidates:
            if candidate in text:
                return candidate
        return None

    def _fallback_topic(self, title: str) -> str:
        compact = re.sub(r"\s+", " ", title).strip()
        return compact[:20] if compact else "쟁점"

    def _most_common_nonempty(self, values: list[str]) -> str | None:
        filtered = [value for value in values if value]
        if not filtered:
            return None
        return Counter(filtered).most_common(1)[0][0]

    def _select_representatives(
        self,
        items: list[CrawlResult],
        preferred_ids: list[str] | None = None,
    ) -> list[str]:
        preferred_ids = preferred_ids or []
        chosen: list[CrawlResult] = []
        seen_ids = set()
        seen_types = set()

        for preferred_id in preferred_ids:
            matched = next((item for item in items if item.id == preferred_id), None)
            if matched and matched.id not in seen_ids:
                chosen.append(matched)
                seen_ids.add(matched.id)
                seen_types.add(matched.type)

        for item in items:
            if len(chosen) >= 4:
                break
            if item.id in seen_ids:
                continue
            if item.type not in seen_types:
                chosen.append(item)
                seen_ids.add(item.id)
                seen_types.add(item.type)

        for item in items:
            if len(chosen) >= 4:
                break
            if item.id not in seen_ids:
                chosen.append(item)
                seen_ids.add(item.id)

        return [item.id for item in chosen[:4]]


evidence_group_service = EvidenceGroupService()
