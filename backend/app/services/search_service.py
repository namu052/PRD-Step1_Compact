import re
from dataclasses import dataclass, field

from app.config import get_settings


@dataclass
class SearchPlan:
    question_type: str
    categories: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    detected_year: int | None = None
    prefer_latest: bool = True
    analysis_focus: list[str] = field(default_factory=list)
    collection_focus: list[str] = field(default_factory=list)

    @property
    def weighting_label(self) -> str:
        if self.detected_year:
            return f"{self.detected_year}년과 가까운 자료를 우선 검토"
        return "최신 자료를 우선 검토"

    def to_notice(self) -> str:
        focus_text = ", ".join(self.analysis_focus) if self.analysis_focus else "관련 법령과 해석 흐름 종합"
        collections = ", ".join(self.collection_focus) if self.collection_focus else "전체 컬렉션"
        keywords = ", ".join(self.keywords[:3]) if self.keywords else "질문 원문"
        return (
            f"질문 분석 완료: {self.question_type}. "
            f"수집 계획은 {collections}에서 '{keywords}' 중심으로 자료를 모으고, "
            f"{self.weighting_label} 기준으로 정렬한 뒤 {focus_text} 순서로 답변을 구성합니다."
        )


class SearchService:
    async def extract_keywords(self, question: str) -> list[str]:
        return (await self.build_search_plan(question)).keywords

    async def build_search_plan(self, question: str) -> SearchPlan:
        settings = get_settings()
        normalized = re.sub(r"\s+", " ", question).strip()
        if not normalized:
            return SearchPlan(question_type="일반 질의", keywords=[], categories=[])

        detected_year = self._extract_year(normalized)
        keywords = (
            self._mock_extract(normalized)
            if settings.use_mock_llm
            else self._extract_without_llm(normalized)
        )
        question_type = self._classify_question_type(normalized)
        categories = self._select_categories(question_type, normalized)
        analysis_focus = self._build_analysis_focus(question_type, normalized)
        collection_focus = [self._category_label(category) for category in categories]

        return SearchPlan(
            question_type=question_type,
            categories=categories,
            keywords=keywords[:4],
            detected_year=detected_year,
            prefer_latest=detected_year is None,
            analysis_focus=analysis_focus,
            collection_focus=collection_focus,
        )

    def _mock_extract(self, question: str) -> list[str]:
        keywords = []
        keyword_map = {
            "취득세": "취득세 감면",
            "재산세": "재산세 납부",
            "등록면허세": "등록면허세",
            "자동차세": "자동차세",
            "주민세": "주민세",
        }
        for trigger, keyword in keyword_map.items():
            if trigger in question:
                keywords.append(keyword)
        return keywords if keywords else [question]

    def _extract_without_llm(self, question: str) -> list[str]:
        normalized = re.sub(r"\s+", " ", question).strip()
        if not normalized:
            return []

        keywords = []
        tax_terms = ["취득세", "재산세", "등록면허세", "자동차세", "주민세", "지방세"]
        topic_terms = ["감면", "환급", "신고", "납부", "비과세", "과세", "판례", "유권해석"]

        for tax in tax_terms:
            if tax in normalized:
                for topic in topic_terms:
                    if topic in normalized:
                        keywords.append(f"{tax} {topic}")
                keywords.append(tax)

        compact = re.sub(r"[?.,()]", " ", normalized)
        compact = re.sub(r"\s+", " ", compact).strip()
        if compact and compact not in keywords:
            keywords.append(compact)

        deduped = []
        seen = set()
        for keyword in keywords:
            value = keyword.strip()
            if value and value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped[:3]

    def _extract_year(self, text: str) -> int | None:
        match = re.search(r"(?<!\d)((?:19|20)\d{2})(?:년)?(?!\d)", text)
        return int(match.group(1)) if match else None

    def _classify_question_type(self, question: str) -> str:
        if any(token in question for token in ["판례", "판결", "심판", "결정례"]):
            return "판례·결정례 비교형"
        if any(token in question for token in ["유권해석", "법제처", "행안부", "해석"]):
            return "유권해석 중심형"
        if any(token in question for token in ["감면", "비과세", "면제", "대상", "요건"]):
            return "감면·적용요건형"
        if any(token in question for token in ["신고", "납부", "기한", "절차", "제출"]):
            return "절차·기한형"
        if any(token in question for token in ["환급", "경정청구", "불복", "구제"]):
            return "환급·구제형"
        return "일반 종합형"

    def _select_categories(self, question_type: str, question: str) -> list[str]:
        if question_type == "판례·결정례 비교형":
            return ["case_search", "interpret_search"]
        if question_type == "유권해석 중심형":
            return ["law_search", "interpret_search"]
        if question_type == "절차·기한형":
            return ["law_search", "interpret_search"]
        if question_type == "환급·구제형":
            return ["case_search", "interpret_search", "law_search"]
        if question_type == "감면·적용요건형":
            return ["law_search", "interpret_search", "case_search"]
        if "판례" in question or "해석" in question:
            return ["case_search", "interpret_search", "law_search"]
        return ["law_search", "interpret_search", "case_search"]

    def _build_analysis_focus(self, question_type: str, question: str) -> list[str]:
        focus = []
        if question_type in {"감면·적용요건형", "일반 종합형"}:
            focus.extend(["적용 요건", "예외·제한", "실무상 주의사항"])
        if question_type in {"판례·결정례 비교형", "환급·구제형"}:
            focus.extend(["사실관계 차이", "판단 충돌 여부", "구제 가능성"])
        if question_type in {"유권해석 중심형", "절차·기한형"}:
            focus.extend(["법령 문언", "행정해석 흐름", "실무 절차"])
        if self._extract_year(question):
            focus.append("특정 연도와 가까운 자료 비교")
        elif "최신" in question or "최근" in question:
            focus.append("최신 해석 우선 검토")
        return list(dict.fromkeys(focus))

    def _category_label(self, category: str) -> str:
        labels = {
            "law_search": "법령·유권해석",
            "interpret_search": "해석·심판",
            "case_search": "판례·결정례",
        }
        return labels.get(category, category)


search_service = SearchService()
