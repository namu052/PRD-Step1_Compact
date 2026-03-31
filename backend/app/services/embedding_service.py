from app.config import get_settings
from app.models.schemas import CrawlResult
from app.services.openai_service import openai_service


class EmbeddingService:
    async def rank_results(
        self,
        question: str,
        results: list[CrawlResult],
        top_k: int | None = None,
        preferred_year: int | None = None,
        prefer_latest: bool = True,
    ) -> list[CrawlResult]:
        settings = get_settings()
        limit = top_k or settings.answer_context_top_k
        if not results:
            return []

        latest_year = max((result.document_year or 0 for result in results), default=0) or None
        try:
            doc_texts = [self._build_embedding_text(result) for result in results]
            embeddings = await openai_service.create_embeddings(
                [question, *doc_texts],
                settings.openai_embedding_model,
            )
            if len(embeddings) != len(results) + 1:
                raise RuntimeError("unexpected embedding length")

            question_embedding = embeddings[0]
            scored = []
            for index, result in enumerate(results):
                semantic = openai_service.cosine_similarity(question_embedding, embeddings[index + 1])
                overlap = self._term_overlap_score(question, result)
                year_bonus = self._year_bonus(
                    result.document_year,
                    preferred_year=preferred_year,
                    latest_year=latest_year,
                    prefer_latest=prefer_latest,
                )
                combined = (
                    semantic * settings.ranking_semantic_weight
                    + overlap * settings.ranking_overlap_weight
                    + result.relevance_score * settings.ranking_position_weight
                    + year_bonus * settings.ranking_year_weight
                )
                scored.append((combined, result))

            scored.sort(key=lambda item: item[0], reverse=True)
            return self._select_diverse_results([result for _, result in scored], limit)
        except Exception:
            question_terms = self._tokenize(question)
            ranked = sorted(
                results,
                key=lambda result: self._score_result(
                    result,
                    question_terms,
                    preferred_year=preferred_year,
                    latest_year=latest_year,
                    prefer_latest=prefer_latest,
                ),
                reverse=True,
            )
            return self._select_diverse_results(ranked, limit)

    def _build_embedding_text(self, result: CrawlResult) -> str:
        settings = get_settings()
        return f"{result.title} {result.preview} {result.content[: settings.embedding_content_limit]}"

    def _score_result(
        self,
        result: CrawlResult,
        question_terms: set[str],
        preferred_year: int | None = None,
        latest_year: int | None = None,
        prefer_latest: bool = True,
    ) -> tuple[float, float, float, float]:
        overlap = self._term_overlap_score(" ".join(question_terms), result)
        year_bonus = self._year_bonus(
            result.document_year,
            preferred_year=preferred_year,
            latest_year=latest_year,
            prefer_latest=prefer_latest,
        )
        return (overlap + result.relevance_score + year_bonus, year_bonus, result.relevance_score, overlap)

    def _tokenize(self, text: str) -> set[str]:
        return {token.strip().lower() for token in text.split() if token.strip()}

    def _term_overlap_score(self, question: str, result: CrawlResult) -> float:
        question_terms = self._tokenize(question)
        haystack = f"{result.title} {result.preview} {result.content[:600]}".lower()
        return float(sum(1 for term in question_terms if term in haystack))

    def _year_bonus(
        self,
        document_year: int | None,
        preferred_year: int | None = None,
        latest_year: int | None = None,
        prefer_latest: bool = True,
    ) -> float:
        if not document_year:
            return 0.0

        if preferred_year is not None:
            distance = abs(document_year - preferred_year)
            return max(0.0, 1.2 - (min(distance, 12) * 0.1))

        if prefer_latest and latest_year:
            distance = max(0, latest_year - document_year)
            return max(0.0, 0.9 - (min(distance, 9) * 0.1))

        return 0.0

    def _select_diverse_results(self, ranked: list[CrawlResult], limit: int) -> list[CrawlResult]:
        if len(ranked) <= limit:
            return ranked

        settings = get_settings()
        per_type_quota = max(2, limit // settings.ranking_diversity_divisor)
        selected: list[CrawlResult] = []
        seen_ids = set()
        type_counts: dict[str, int] = {}

        for result in ranked:
            current_count = type_counts.get(result.type, 0)
            if current_count >= per_type_quota:
                continue
            selected.append(result)
            seen_ids.add(result.id)
            type_counts[result.type] = current_count + 1
            if len(selected) >= limit:
                return selected

        for result in ranked:
            if result.id in seen_ids:
                continue
            selected.append(result)
            if len(selected) >= limit:
                break

        return selected


embedding_service = EmbeddingService()
