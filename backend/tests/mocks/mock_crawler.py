import json
from datetime import datetime
from pathlib import Path

from app.models.schemas import CrawlResult


class MockCrawler:
    def __init__(self) -> None:
        mock_path = Path(__file__).resolve().parent / "mock_olta_pages.json"
        with mock_path.open("r", encoding="utf-8") as file:
            self.data = json.load(file)

    def search(self, queries: list[str], categories: list[str] | None = None) -> list[CrawlResult]:
        results = []
        seen_ids = set()
        target_categories = categories or ["law_search", "interpret_search"]

        for query in queries:
            for category in target_categories:
                for keyword, items in self.data.get(category, {}).items():
                    if query in keyword or keyword in query:
                        for item in items:
                            if item["id"] in seen_ids:
                                continue
                            seen_ids.add(item["id"])
                            results.append(
                                CrawlResult(
                                    id=item["id"],
                                    title=item["title"],
                                    type=item["type"],
                                    content=item["content"],
                                    preview=f"{item['content'][:100]}...",
                                    url=item["url"],
                                    relevance_score=0.9,
                                    crawled_at=datetime.now(),
                                )
                            )
        return results


mock_crawler = MockCrawler()
