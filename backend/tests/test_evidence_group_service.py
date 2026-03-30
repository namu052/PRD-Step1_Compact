import pytest

from app.models.schemas import CrawlResult
from app.services.evidence_group_service import evidence_group_service


def _to_crawl_results(data_list):
    return [
        CrawlResult(**{**item, "preview": f"{item['content'][:100]}...", "relevance_score": 0.9})
        for item in data_list
    ]


@pytest.mark.asyncio
async def test_groups_related_tax_issue_documents_together():
    results = _to_crawl_results(
        [
            {
                "id": "doc_1",
                "title": "지방세특례제한법 제36조(서민주택 등에 대한 감면)",
                "type": "법령",
                "content": "취득세 감면, 1억원 이하 주택, 서민주택 감면 규정",
                "url": "https://www.olta.re.kr/a",
            },
            {
                "id": "doc_2",
                "title": "해석례 2024-0312 (서민주택 감면 적용 범위)",
                "type": "해석례",
                "content": "취득세 감면과 부속토지 범위를 설명하는 해석례",
                "url": "https://www.olta.re.kr/b",
            },
            {
                "id": "doc_3",
                "title": "지방세법 제115조(재산세 납기)",
                "type": "법령",
                "content": "재산세 납부 기한을 정하는 규정",
                "url": "https://www.olta.re.kr/c",
            },
        ]
    )

    groups = await evidence_group_service.group("취득세 감면 대상이 무엇인지 알려줘", results)
    grouped_sets = [set(group.source_ids) for group in groups]

    assert any({"doc_1", "doc_2"}.issubset(grouped) for grouped in grouped_sets)
    assert any({"doc_3"} == grouped for grouped in grouped_sets)


@pytest.mark.asyncio
async def test_representative_sources_are_limited():
    results = _to_crawl_results(
        [
            {
                "id": f"doc_{index}",
                "title": f"취득세 감면 관련 문서 {index}",
                "type": "판례" if index % 2 else "해석례",
                "content": "취득세 감면 생애최초 주택 관련 내용",
                "url": f"https://www.olta.re.kr/{index}",
            }
            for index in range(1, 6)
        ]
    )

    groups = await evidence_group_service.group("취득세 감면 대상이 무엇인지 알려줘", results)
    assert groups
    assert all(len(group.representative_source_ids) <= 3 for group in groups)
