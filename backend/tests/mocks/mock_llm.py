from app.prompts.stage1_prompt import NO_RESULTS_ANSWER


class MockLLM:
    def extract_keywords(self, question: str) -> list[str]:
        if "취득세" in question:
            return ["취득세 감면"]
        if "재산세" in question:
            return ["재산세 납부"]
        return [question]

    def generate_draft(self, question: str, crawl_results) -> str:
        if not crawl_results:
            return NO_RESULTS_ANSWER

        lines = [f"## {question}에 대한 답변", ""]
        for result in crawl_results:
            lines.append(f"- {result.title}")
        return "\n".join(lines)


mock_llm = MockLLM()
