import asyncio
import difflib
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Awaitable, Callable

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.core.event_emitter import sse_event
from app.core.session_manager import session_manager
from app.models.evidence import EvidenceSlot
from app.models.schemas import ChatRequest, CrawlResult, SourceDetail
from app.services.crawler_service import crawler_service
from app.services.embedding_service import embedding_service
from app.services.evidence_group_service import evidence_group_service
from app.services.evidence_summary_service import evidence_summary_service
from app.services.verification.content_verifier import content_verifier
from app.services.verification.final_generator import final_generator
from app.services.verification.grouped_answer_verifier import grouped_answer_verifier
from app.services.verification.source_verifier import source_verifier
from app.services.verification.verification_aggregator import verification_aggregator
from app.services.llm_service import llm_service
from app.services.search_service import SearchPlan, search_service

router = APIRouter(prefix="/api", tags=["chat"])


async def require_session(session_id: str):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="유효한 세션이 필요합니다")
    return session


async def verify_answer(answer: str, ranked_results, evidence_slots: list[EvidenceSlot]):
    source_verifications, content_claims, slot_verifications = await asyncio.gather(
        source_verifier.verify(answer, ranked_results),
        content_verifier.verify(answer, ranked_results),
        grouped_answer_verifier.verify(answer, evidence_slots),
    )
    return verification_aggregator.aggregate(
        source_verifications,
        content_claims,
        slot_verifications,
    )


async def noop_notice(_: str) -> None:
    return None


def _build_revision_diff_notice(before: str, after: str, label: str) -> list[str]:
    before_lines = [line.strip() for line in before.splitlines() if line.strip()]
    after_lines = [line.strip() for line in after.splitlines() if line.strip()]
    diff_lines = list(difflib.ndiff(before_lines, after_lines))
    changes = []
    for line in diff_lines:
        if line.startswith("- "):
            changes.append(f"{label} 삭제: {line[2:][:140]}")
        elif line.startswith("+ "):
            changes.append(f"{label} 추가: {line[2:][:140]}")
        if len(changes) >= 6:
            break
    return changes


def _verification_metrics_notice(verification_result) -> str:
    return (
        "검증 세부 지표: "
        f"주장 {round(verification_result.claim_confidence * 100, 1)}%, "
        f"출처 {round(verification_result.source_confidence * 100, 1)}%, "
        f"근거묶음 {round(verification_result.slot_confidence * 100, 1)}%, "
        f"직접출처커버리지 {round(verification_result.citation_coverage * 100, 1)}%, "
        f"검증출처연결 {round(verification_result.verified_citation_ratio * 100, 1)}%"
    )


def _verification_issue_notice(verification_result) -> str | None:
    if verification_result.critical_issues:
        return f"주요 검증 이슈: {', '.join(verification_result.critical_issues[:3])}"
    if verification_result.warnings:
        cleaned = [warning.replace('⚠️ ', '') for warning in verification_result.warnings[:3]]
        return f"주요 경고: {', '.join(cleaned)}"
    return None


async def run_verification_cycle(
    question: str,
    ranked_results,
    evidence_slots: list[EvidenceSlot],
    draft,
    on_notice: Callable[[str], Awaitable[None]] = noop_notice,
):
    settings = get_settings()
    max_rounds = max(1, settings.max_verification_rounds)
    target_confidence = settings.verification_target_confidence

    current_draft = draft
    verification_result = None
    rounds_run = 0
    prev_confidence = 0.0

    for round_index in range(max_rounds):
        rounds_run = round_index + 1
        verification_result = await verify_answer(
            current_draft.answer,
            ranked_results,
            evidence_slots,
        )
        await on_notice(
            (
                f"검증 {round_index + 1}차: 현재 신뢰도 "
                f"{round(verification_result.overall_confidence * 100, 1)}% "
                f"({verification_result.confidence_label})입니다."
            )
        )
        await on_notice(_verification_metrics_notice(verification_result))
        issue_notice = _verification_issue_notice(verification_result)
        if issue_notice:
            await on_notice(issue_notice)

        if verification_result.overall_confidence >= target_confidence:
            await on_notice("검증 목표에 도달하여 초안 수정을 종료합니다.")
            break
        if round_index > 0:
            improvement = verification_result.overall_confidence - prev_confidence
            if improvement < settings.stagnation_threshold:
                await on_notice(
                    "검증 신뢰도 개선 폭이 작아 추가 초안 수정을 중단합니다."
                )
                break
        prev_confidence = verification_result.overall_confidence

        if round_index == max_rounds - 1:
            await on_notice("최대 검증 라운드에 도달하여 초안 수정을 종료합니다.")
            break

        await on_notice(f"검증 {round_index + 1}차 결과를 반영해 초안을 다시 수정합니다.")
        previous_answer = current_draft.answer
        current_draft = await llm_service.revise_draft(
            question=question,
            draft_answer=current_draft.answer,
            verification_result=verification_result,
            crawl_results=ranked_results,
            evidence_slots=evidence_slots,
        )
        for notice in _build_revision_diff_notice(previous_answer, current_draft.answer, "초안"):
            await on_notice(notice)
        await on_notice(f"검증 {round_index + 1}차 수정이 완료되었습니다.")

    return current_draft, verification_result, rounds_run


async def run_finalization_cycle(
    question: str,
    draft,
    verification_result,
    ranked_results,
    evidence_slots: list[EvidenceSlot],
    on_notice: Callable[[str], Awaitable[None]] = noop_notice,
):
    settings = get_settings()
    max_rounds = max(1, settings.max_verification_rounds)
    target_confidence = settings.verification_target_confidence
    current_draft = draft
    current_verification = verification_result
    final_answer = None
    rounds_run = 0
    prev_confidence = current_verification.overall_confidence if current_verification else 0.0

    for round_index in range(max_rounds):
        rounds_run = round_index + 1
        final_answer = await final_generator.generate(
            current_draft.answer,
            current_verification,
            evidence_slots,
            ranked_results,
        )
        current_verification = await verify_answer(
            final_answer.answer,
            ranked_results,
            evidence_slots,
        )
        await on_notice(
            (
                f"최종 정리 {round_index + 1}차: 현재 신뢰도 "
                f"{round(current_verification.overall_confidence * 100, 1)}% "
                f"({current_verification.confidence_label})입니다."
            )
        )
        await on_notice(_verification_metrics_notice(current_verification))
        issue_notice = _verification_issue_notice(current_verification)
        if issue_notice:
            await on_notice(issue_notice)
        final_answer.confidence_score = round(current_verification.overall_confidence * 100, 1)
        final_answer.confidence_label = current_verification.confidence_label
        final_answer.warnings = current_verification.warnings
        final_answer.verified_sources = final_generator.build_verified_source_cards(
            current_verification,
            evidence_slots,
            ranked_results,
        )

        if current_verification.overall_confidence >= target_confidence:
            await on_notice("최종 답변 신뢰도가 목표치에 도달했습니다.")
            break
        if round_index > 0:
            improvement = current_verification.overall_confidence - prev_confidence
            if improvement < settings.stagnation_threshold:
                await on_notice("최종 정리 단계의 개선 폭이 작아 반복 정리를 종료합니다.")
                break
        prev_confidence = current_verification.overall_confidence
        if round_index == max_rounds - 1:
            await on_notice("최대 최종 정리 라운드에 도달했습니다.")
            break

        await on_notice(f"최종 정리 {round_index + 1}차 결과를 반영해 답변을 다시 다듬습니다.")
        previous_answer = final_answer.answer
        current_draft = await llm_service.revise_draft(
            question=question,
            draft_answer=final_answer.answer,
            verification_result=current_verification,
            crawl_results=ranked_results,
            evidence_slots=evidence_slots,
        )
        for notice in _build_revision_diff_notice(previous_answer, current_draft.answer, "최종안"):
            await on_notice(notice)
        await on_notice(f"최종 정리 {round_index + 1}차 수정이 완료되었습니다.")

    return final_answer, current_verification, rounds_run


def build_process_summary_results(
    question: str,
    search_plan: SearchPlan,
    ranked_results,
    verification_result,
    rounds_run: int,
):
    settings = get_settings()
    searched_titles = [result.title for result in ranked_results[:5]]
    search_summary = CrawlResult(
        id="process_search_summary",
        title="질문 분석 및 검색 요약",
        type="처리 요약",
        preview=(
            f"{search_plan.question_type} 질문으로 판단했고 "
            f"'{', '.join(search_plan.keywords[:3]) or question}' 기준으로 {len(ranked_results)}건을 추렸습니다."
        ),
        content="\n".join(
            [
                f"질문: {question}",
                f"질문 유형: {search_plan.question_type}",
                f"추출 키워드: {', '.join(search_plan.keywords) if search_plan.keywords else question}",
                f"우선 가중치: {search_plan.weighting_label}",
                (
                    f"분석 초점: {', '.join(search_plan.analysis_focus)}"
                    if search_plan.analysis_focus
                    else "분석 초점: 관련 법령과 해석 흐름 종합"
                ),
                f"후보 문서 수: {len(ranked_results)}건",
                "상위 근거 문서:",
                *[f"- {title}" for title in searched_titles],
            ]
        ),
        url="",
        relevance_score=1.0,
        crawled_at=datetime.now(),
    )

    confidence_line = (
        f"최종 신뢰도: {verification_result.confidence_label} ({round(verification_result.overall_confidence * 100, 1)}%)"
        if verification_result
        else "최종 신뢰도: 계산 불가"
    )
    verification_summary = CrawlResult(
        id="process_verification_summary",
        title="답변 작성 및 검증 요약",
        type="처리 요약",
        preview=(
            f"초안 작성 후 최대 {round(settings.verification_target_confidence * 100)}% 신뢰도를 목표로 "
            f"검증을 {rounds_run}회 수행했습니다."
        ),
        content="\n".join(
            [
                "처리 흐름:",
                f"- {search_plan.weighting_label} 기준으로 수집 결과를 재정렬",
                "- OLTA 검색 결과를 기반으로 근거 묶음을 생성",
                "- 묶음 기반 초안을 생성하고 개별 문서/근거 묶음을 함께 검증",
                (
                    f"- 신뢰도가 {round(settings.verification_target_confidence * 100)}% 미만이면 "
                    "검증 피드백을 반영해 답변을 재작성"
                ),
                f"- 실제 수행 라운드 수: {rounds_run}회",
                confidence_line,
                (
                    f"세부 지표: 주장 {round(verification_result.claim_confidence * 100, 1)}%, "
                    f"출처 {round(verification_result.source_confidence * 100, 1)}%, "
                    f"근거묶음 {round(verification_result.slot_confidence * 100, 1)}%"
                    if verification_result
                    else "세부 지표: 계산 불가"
                ),
                (
                    f"인용 커버리지: 직접 출처 {round(verification_result.citation_coverage * 100, 1)}%, "
                    f"검증된 출처 연결 {round(verification_result.verified_citation_ratio * 100, 1)}%, "
                    f"supported 주장 {round(verification_result.supported_claim_ratio * 100, 1)}%"
                    if verification_result
                    else "인용 커버리지: 계산 불가"
                ),
                f"경고 수: {len(verification_result.warnings) if verification_result else 0}",
                (
                    f"치명 이슈: {', '.join(verification_result.critical_issues[:5])}"
                    if verification_result and verification_result.critical_issues
                    else "치명 이슈: 없음"
                ),
            ]
        ),
        url="",
        relevance_score=0.99,
        crawled_at=datetime.now(),
    )
    return [search_summary, verification_summary]


def dedupe_source_cards(cards: list[dict]) -> list[dict]:
    deduped = []
    seen_ids = set()
    for card in cards:
        card_id = card.get("id")
        if card_id in seen_ids:
            continue
        deduped.append(card)
        seen_ids.add(card_id)
    return deduped


def stage_notice(message: str) -> str:
    return sse_event("notice", {"message": message})


@router.post("/chat")
async def chat(payload: ChatRequest):
    session = await require_session(payload.session_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        async def emit_notice(message: str) -> None:
            yield_queue.append(stage_notice(message))

        yield_queue: list[str] = []

        yield sse_event("stage_change", {"stage": "crawling"})
        search_plan = await search_service.build_search_plan(payload.question)
        yield stage_notice(search_plan.to_notice())

        crawl_results = await crawler_service.search(
            session,
            search_plan.keywords,
            search_plan.categories,
        )
        ranked_results = await embedding_service.rank_results(
            payload.question,
            crawl_results,
            preferred_year=search_plan.detected_year,
            prefer_latest=search_plan.prefer_latest,
        )
        evidence_groups = await evidence_group_service.group(payload.question, ranked_results)
        evidence_slots = await evidence_summary_service.summarize(
            payload.question,
            evidence_groups,
            ranked_results,
        )
        yield stage_notice(
            (
                f"자료 수집 및 분석 완료: OLTA 자료 {len(crawl_results)}건을 모아 "
                f"{len(ranked_results)}건을 우선 검토하고, 근거 묶음 {len(evidence_slots)}개로 정리했습니다."
            )
        )
        evidence_slot_results = [slot.to_crawl_result() for slot in evidence_slots]
        session.crawl_cache = {
            result.id: result for result in [*ranked_results, *evidence_slot_results]
        }

        yield sse_event("stage_change", {"stage": "drafting"})
        draft_queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_draft_token(chunk: str) -> None:
            await draft_queue.put(sse_event("token", {"token": chunk}))

        draft_task = asyncio.create_task(
            llm_service.generate_draft(
                payload.question,
                ranked_results,
                evidence_slots=evidence_slots,
                on_token=on_draft_token,
            )
        )

        while True:
            if draft_task.done() and draft_queue.empty():
                break
            try:
                yield await asyncio.wait_for(draft_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

        draft = await draft_task
        yield stage_notice("초안 작성 완료: 근거 묶음을 기준으로 1차 답변 초안을 만들었습니다.")

        final_answer = None
        verification_result = None
        process_summaries = []

        try:
            yield sse_event("stage_change", {"stage": "verifying"})
            draft, verification_result, rounds_run = await run_verification_cycle(
                payload.question,
                ranked_results,
                evidence_slots,
                draft,
                on_notice=emit_notice,
            )
            while yield_queue:
                yield yield_queue.pop(0)
            yield stage_notice(
                (
                    f"검증 완료: 문서 근거와 근거 묶음을 함께 점검했고 "
                    f"{rounds_run}회 검증·수정 루프를 수행했습니다."
                )
            )
            process_summaries = build_process_summary_results(
                payload.question,
                search_plan,
                ranked_results,
                verification_result,
                rounds_run,
            )
            session.crawl_cache.update({result.id: result for result in process_summaries})

            yield sse_event("stage_change", {"stage": "finalizing"})
            final_queue: asyncio.Queue[str] = asyncio.Queue()

            async def on_final_token(chunk: str) -> None:
                await final_queue.put(sse_event("token", {"token": chunk}))

            final_task = asyncio.create_task(run_finalization_cycle(
                payload.question,
                draft,
                verification_result,
                ranked_results,
                evidence_slots,
                emit_notice,
            ))

            final_answer, verification_result, final_rounds_run = await final_task
            while yield_queue:
                yield yield_queue.pop(0)
            rounds_run += max(final_rounds_run - 1, 0)
            for index in range(0, len(final_answer.answer), 5):
                await on_final_token(final_answer.answer[index : index + 5])

            while not final_queue.empty():
                yield await final_queue.get()

            yield stage_notice(
                (
                    f"최종 답변 정리 완료: 현재 신뢰도는 "
                    f"{round(final_answer.confidence_score, 1)}%이며 출처 카드와 함께 답변을 마무리했습니다."
                )
            )

            process_summaries = build_process_summary_results(
                payload.question,
                search_plan,
                ranked_results,
                verification_result,
                rounds_run,
            )
            session.crawl_cache.update({result.id: result for result in process_summaries})
        except Exception:
            fallback_warning = "⚠️ 검증 단계에 실패하여 1단계 초안을 그대로 반환합니다."
            yield sse_event("stage_change", {"stage": "finalizing"})
            for index in range(0, len(fallback_warning), 5):
                yield sse_event("token", {"token": fallback_warning[index : index + 5]})
            final_answer = None

        if final_answer:
            sources = dedupe_source_cards(
                [result.to_source_card() for result in process_summaries]
                + [slot_result.to_source_card() for slot_result in evidence_slot_results]
                + final_answer.verified_sources
            )
            confidence = {
                "score": round(final_answer.confidence_score / 100, 2),
                "label": final_answer.confidence_label,
            } if final_answer.verified_sources else None
        else:
            sources = dedupe_source_cards(
                [result.to_source_card() for result in process_summaries] + [
                    slot_result.to_source_card() for slot_result in evidence_slot_results
                ] + [
                    result.to_source_card()
                    for result in ranked_results
                    if not draft.cited_sources or result.id in draft.cited_sources
                ]
            )
            confidence = (
                {
                    "score": verification_result.overall_confidence,
                    "label": verification_result.confidence_label,
                }
                if verification_result and sources
                else None
            )

        yield sse_event("sources", {"sources": sources, "confidence": confidence})
        yield sse_event("stage_change", {"stage": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/preview/{source_id}", response_model=SourceDetail)
async def preview(source_id: str, session_id: str):
    session = await require_session(session_id)
    source = session.crawl_cache.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="출처를 찾을 수 없습니다")
    return SourceDetail(**source.to_source_detail())
