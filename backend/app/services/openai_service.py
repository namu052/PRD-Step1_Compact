import json
import math
from typing import Awaitable, Callable, Optional

from openai import AsyncOpenAI

from app.config import get_settings
from app.models.evidence import EvidenceSlot
from app.models.schemas import CrawlResult


class OpenAIService:
    def __init__(self) -> None:
        self._client = None
        self._api_key = None

    def _get_client(self) -> AsyncOpenAI:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when USE_MOCK_LLM=false")

        if self._client is None or self._api_key != settings.openai_api_key:
            self._api_key = settings.openai_api_key
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

        return self._client

    async def create_text(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1600,
        on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> tuple[str, dict]:
        client = self._get_client()

        if on_token:
            stream = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            chunks = []
            async for event in stream:
                delta = event.choices[0].delta.content or ""
                if not delta:
                    continue
                chunks.append(delta)
                await on_token(delta)
            return "".join(chunks).strip(), {}

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        usage = response.usage.model_dump() if response.usage else {}
        return content.strip(), usage

    async def create_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        schema: dict,
        temperature: float = 0.0,
        max_tokens: int = 1600,
    ) -> tuple[dict, dict]:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        usage = response.usage.model_dump() if response.usage else {}
        return json.loads(content), usage

    async def create_embeddings(self, texts: list[str], model: str) -> list[list[float]]:
        if not texts:
            return []

        client = self._get_client()
        vectors = []
        batch_size = 32
        for index in range(0, len(texts), batch_size):
            batch = texts[index : index + batch_size]
            response = await client.embeddings.create(
                model=model,
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend([item.embedding for item in ordered])
        return vectors

    def format_crawl_results(self, crawl_results: list[CrawlResult], content_limit: int = 1400) -> str:
        blocks = []
        for result in crawl_results:
            blocks.append(
                "\n".join(
                    [
                        f"- source_id: {result.id}",
                        f"  title: {result.title}",
                        f"  type: {result.type}",
                        f"  url: {result.url}",
                        f"  preview: {result.preview}",
                        f"  content: {result.content[:content_limit]}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    def format_evidence_slots(self, evidence_slots: list[EvidenceSlot]) -> str:
        blocks = []
        for slot in evidence_slots:
            rep_sources = ", ".join(slot.representative_source_ids)
            rep_links = ", ".join(slot.representative_links)
            key_points = " | ".join(slot.key_points)
            exceptions = " | ".join(slot.exceptions)
            conflicts = " | ".join(slot.conflicts)
            fact_distinctions = " | ".join(slot.fact_distinctions)
            practice_notes = " | ".join(slot.practice_notes)
            source_types = " | ".join(slot.source_type_summary)
            blocks.append(
                "\n".join(
                    [
                        f"- slot_id: {slot.slot_id}",
                        f"  title: {slot.title}",
                        f"  issue: {slot.issue}",
                        f"  conclusion: {slot.conclusion}",
                        f"  applicability: {slot.applicability}",
                        f"  exceptions: {exceptions}",
                        f"  conflicts: {conflicts}",
                        f"  fact_distinctions: {fact_distinctions}",
                        f"  practice_notes: {practice_notes}",
                        f"  summary: {slot.summary}",
                        f"  key_points: {key_points}",
                        f"  source_type_summary: {source_types}",
                        f"  representative_source_ids: {rep_sources}",
                        f"  representative_links: {rep_links}",
                    ]
                )
            )
        return "\n\n".join(blocks)

    def cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=False))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)


openai_service = OpenAIService()
