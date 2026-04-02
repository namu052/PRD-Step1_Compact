import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Awaitable, Callable

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.core.event_emitter import sse_event
from app.core.session_manager import session_manager
from app.models.evidence import EvidenceSlot
from app.models.schemas import (
    BoardCollectionStat,
    ChatRequest,
    CollectionProgress,
    CrawlResult,
    SourceDetail,
    VerificationHistory,
)
from app.services.crawler_service import crawler_service
from app.services.embedding_service import embedding_service
from app.services.evidence_group_service import evidence_group_service
from app.services.evidence_summary_service import evidence_summary_service
from app.services.gap_analyzer_service import gap_analyzer_service
from app.services.verification.content_verifier import content_verifier
from app.services.verification.final_generator import final_generator
from app.services.verification.grouped_answer_verifier import grouped_answer_verifier
from app.services.verification.source_verifier import source_verifier
from app.services.verification.verification_aggregator import verification_aggregator
from app.services.llm_service import DraftResponse, llm_service
from app.services.search_service import SearchPlan, search_service
from app.services.web_search_service import web_search_service

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


def stage_notice(message: str) -> str:
    return sse_event("notice", {"message": message})


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


def _build_collection_progress(stats: list[BoardCollectionStat]) -> CollectionProgress:
    board_map: dict[str, BoardCollectionStat] = {}

    for stat in stats:
        key = f"{stat.board_name}::{stat.sub_board_name or ''}"
        board_map[key] = stat

    boards = list(board_map.values())
    collecting_entries = [board for board in boards if board.status == "collecting"]

    return CollectionProgress(
        total_collected=sum(board.collected_count for board in boards if board.status == "done"),
        boards=boards,
        current_board=collecting_entries[-1].board_name if collecting_entries else None,
        current_sub_board=collecting_entries[-1].sub_board_name if collecting_entries else None,
    )


def _build_crawl_summary(stats: list[BoardCollectionStat]) -> dict:
    progress = _build_collection_progress(stats)
    board_map: dict[str, dict] = {}

    for stat in progress.boards:
        board = board_map.setdefault(
            stat.board_name,
            {
                "board_name": stat.board_name,
                "total_collected": 0,
                "sub_boards": [],
            },
        )

        if stat.status == "done":
            board["total_collected"] += stat.collected_count

        if stat.sub_board_name:
            board["sub_boards"].append(
                {
                    "name": stat.sub_board_name,
                    "collected_count": stat.collected_count,
                    "skipped": stat.skipped,
                    "status": stat.status,
                }
            )

    boards = list(board_map.values())
    return {
        "grand_total": sum(board["total_collected"] for board in boards),
        "boards": boards,
    }


def _build_crawl_summary_notice(crawl_summary: dict) -> str | None:
    board_parts = [
        f"{board['board_name']}({board['total_collected']}건)"
        for board in crawl_summary.get("boards", [])
        if board.get("total_collected", 0) > 0
    ]
    if not board_parts:
        return None
    return f"게시판별: {', '.join(board_parts)}"


def _build_crawl_summary_notice(crawl_summary: dict) -> str | None:
    board_parts = [
        f"{board['board_name']}({board['total_collected']})"
        for board in crawl_summary.get("boards", [])
        if board.get("total_collected", 0) > 0
    ]
    if not board_parts:
        return None
    return f"Board totals: {', '.join(board_parts)}"


async def _search_with_optional_progress(session, queries, categories, on_progress=None):
    if on_progress is None:
        return await crawler_service.search(session, queries, categories)

    try:
        return await crawler_service.search(
            session,
            queries,
            categories,
            on_progress=on_progress,
        )
    except TypeError as exc:
        if "on_progress" not in str(exc):
            raise
        return await crawler_service.search(session, queries, categories)


@router.post("/chat")
async def chat(payload: ChatRequest):
    session = await require_session(payload.session_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        settings = get_settings()
        yield_queue: list[str] = []

        async def emit_notice(message: str) -> None:
            yield_queue.append(stage_notice(message))

        history = VerificationHistory()

        # ──────────────────────────────────────────────
        # Stage 1: 웹 검색+초안 과 OLTA 파이프라인 병렬 실행
        # ──────────────────────────────────────────────
        yield sse_event("stage_change", {"stage": "searching"})
        search_plan = await search_service.build_search_plan(payload.question)
        yield stage_notice(search_plan.to_notice())

        # --- OLTA 브랜치 (백그라운드) ---
        olta_result_holder: dict = {}
        olta_notices: list[str] = []
        crawl_progress_stats: list[BoardCollectionStat] = []
        olta_event_queue: asyncio.Queue[str] = asyncio.Queue()

        async def queue_olta_event(event: str) -> None:
            await olta_event_queue.put(event)

        async def on_crawl_progress(stat: BoardCollectionStat) -> None:
            crawl_progress_stats.append(stat)
            await queue_olta_event(sse_event("crawl_progress", stat.model_dump()))

        async def olta_branch():
            try:
                olta_logged_in = await crawler_service.check_olta_login()
            except Exception:
                olta_logged_in = False
            olta_result_holder["logged_in"] = olta_logged_in

            if olta_logged_in:
                olta_notices.append(stage_notice("OLTA 로그인 확인 완료 - 기타(BBS) 게시판 포함 전체 수집합니다."))
            else:
                olta_notices.append(sse_event("olta_login_required", {
                    "message": "OLTA 미로그인 상태입니다. 기타(BBS) 게시판 수집이 제한됩니다. OLTA 로그인 후 더 정확한 답변을 받을 수 있습니다.",
                }))
                olta_notices.append(stage_notice("OLTA 미로그인 - 기존 법령/판례 자료만 수집합니다."))

            crawl_results = await _search_with_optional_progress(
                session,
                search_plan.keywords,
                search_plan.categories,
                on_progress=on_crawl_progress,
            )
            ranked_results = await embedding_service.rank_results(
                payload.question,
                crawl_results,
                preferred_year=search_plan.detected_year,
                prefer_latest=search_plan.prefer_latest,
            )

            evidence_groups = await evidence_group_service.group(payload.question, ranked_results)
            slots = await evidence_summary_service.summarize(
                payload.question,
                evidence_groups,
                ranked_results,
            )

            olta_notices.append(stage_notice(
                f"OLTA 자료 수집 완료: {len(crawl_results)}건 수집, "
                f"{len(ranked_results)}건 우선 검토, 근거 묶음 {len(slots)}개 정리."
            ))

            olta_result_holder["ranked_results"] = ranked_results
            olta_result_holder["evidence_slots"] = slots

        olta_task = asyncio.create_task(olta_branch())

        # --- 웹 브랜치 (스트리밍) ---
        web_results = await web_search_service.search(
            search_plan.keywords or [payload.question],
        )
        yield stage_notice(
            f"웹 검색 완료: {len(web_results)}건의 관련 자료를 찾았습니다."
        )

        yield sse_event("stage_change", {"stage": "drafting"})
        draft_queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_draft_token(chunk: str) -> None:
            await draft_queue.put(sse_event("token", {"token": chunk}))

        draft_task = asyncio.create_task(
            llm_service.generate_web_draft(
                payload.question,
                web_results,
                on_token=on_draft_token,
            )
        )

        while True:
            while not olta_event_queue.empty():
                yield await olta_event_queue.get()
            if draft_task.done() and draft_queue.empty():
                break
            try:
                yield await asyncio.wait_for(draft_queue.get(), timeout=0.1)
            except TimeoutError:
                continue

        draft = await draft_task
        yield stage_notice("초안 작성 완료: 웹 검색 결과를 기반으로 1차 답변 초안을 만들었습니다.")

        # --- OLTA 브랜치 완료 대기 ---
        while not olta_task.done() or not olta_event_queue.empty():
            while not olta_event_queue.empty():
                yield await olta_event_queue.get()
            if not olta_task.done():
                await asyncio.sleep(0.1)
        await olta_task
        for notice in olta_notices:
            yield notice

        ranked_results = olta_result_holder.get("ranked_results", [])
        evidence_slots = olta_result_holder.get("evidence_slots", [])

        # ──────────────────────────────────────────────
        # Stage 2: OLTA 검증
        # ──────────────────────────────────────────────
        final_answer = None
        verification_result = None
        all_olta_results: list[CrawlResult] = list(ranked_results)
        evidence_slot_results: list[CrawlResult] = [slot.to_crawl_result() for slot in evidence_slots]
        process_summaries: list[CrawlResult] = []

        try:
            yield sse_event("stage_change", {"stage": "verifying"})

            session.crawl_cache = {
                result.id: result for result in [*ranked_results, *evidence_slot_results]
            }

            # 1차 검증
            verification_result = await verify_answer(
                draft.answer, ranked_results, evidence_slots,
            )
            history.add_round(
                confidence=verification_result.overall_confidence,
                gaps=verification_result.critical_issues,
                actions="OLTA 자료 기반 1차 검증",
            )
            await emit_notice(
                f"1차 검증 완료: 신뢰도 {round(verification_result.overall_confidence * 100, 1)}% "
                f"({verification_result.confidence_label})"
            )
            await emit_notice(_verification_metrics_notice(verification_result))
            issue_notice = _verification_issue_notice(verification_result)
            if issue_notice:
                await emit_notice(issue_notice)
            while yield_queue:
                yield yield_queue.pop(0)

            # ──────────────────────────────────────────────
            # Stage 3: 반복 연구 (researching → verifying)
            # ──────────────────────────────────────────────
            for iteration in range(settings.max_research_iterations):
                if verification_result.overall_confidence >= settings.research_confidence_threshold:
                    yield stage_notice("검증 신뢰도가 목표치에 도달하여 추가 조사를 건너뜁니다.")
                    break

                yield sse_event("stage_change", {"stage": "researching"})
                gap_analysis = await gap_analyzer_service.analyze(
                    draft.answer, verification_result, history,
                )
                if not gap_analysis.should_continue or not gap_analysis.search_queries:
                    yield stage_notice("추가 조사가 필요하지 않다고 판단하여 조사를 종료합니다.")
                    break

                yield stage_notice(
                    f"추가 조사 {iteration + 1}차: 미비점 {len(gap_analysis.gaps)}건 발견, "
                    f"'{', '.join(gap_analysis.search_queries[:2])}' 키워드로 추가 검색합니다."
                )

                # 추가 웹 검색 + OLTA 검색 (병렬)
                extra_web, extra_olta_raw = await asyncio.gather(
                    web_search_service.search(gap_analysis.search_queries),
                    crawler_service.search(
                        session, gap_analysis.search_queries, search_plan.categories,
                    ),
                )
                extra_olta = await embedding_service.rank_results(
                    payload.question, extra_olta_raw,
                    preferred_year=search_plan.detected_year,
                    prefer_latest=search_plan.prefer_latest,
                )

                # 새 OLTA 결과 병합
                existing_ids = {r.id for r in all_olta_results}
                for r in extra_olta:
                    if r.id not in existing_ids:
                        all_olta_results.append(r)
                        existing_ids.add(r.id)

                # 근거 묶음 재생성
                evidence_groups = await evidence_group_service.group(
                    payload.question, all_olta_results,
                )
                evidence_slots = await evidence_summary_service.summarize(
                    payload.question, evidence_groups, all_olta_results,
                )
                evidence_slot_results = [slot.to_crawl_result() for slot in evidence_slots]
                session.crawl_cache.update(
                    {r.id: r for r in [*extra_olta, *evidence_slot_results]}
                )

                yield stage_notice(
                    f"추가 자료 수집 완료: 웹 {len(extra_web)}건, OLTA {len(extra_olta)}건 추가."
                )

                # 초안 보완
                yield sse_event("stage_change", {"stage": "verifying"})
                draft = await llm_service.revise_draft(
                    question=payload.question,
                    draft_answer=draft.answer,
                    verification_result=verification_result,
                    crawl_results=all_olta_results,
                    evidence_slots=evidence_slots,
                )

                # 재검증
                verification_result = await verify_answer(
                    draft.answer, all_olta_results, evidence_slots,
                )
                history.add_round(
                    confidence=verification_result.overall_confidence,
                    gaps=[g for g in gap_analysis.gaps[:3]],
                    actions=f"추가 조사 {iteration + 1}차 (웹 {len(extra_web)}건 + OLTA {len(extra_olta)}건)",
                )
                await emit_notice(
                    f"재검증 완료: 신뢰도 {round(verification_result.overall_confidence * 100, 1)}% "
                    f"({verification_result.confidence_label})"
                )
                await emit_notice(_verification_metrics_notice(verification_result))
                issue_notice = _verification_issue_notice(verification_result)
                if issue_notice:
                    await emit_notice(issue_notice)
                while yield_queue:
                    yield yield_queue.pop(0)

            # ──────────────────────────────────────────────
            # Stage 4: 최종 답변 (검증 이력 포함)
            # ──────────────────────────────────────────────
            yield sse_event("stage_change", {"stage": "finalizing"})

            final_answer = await final_generator.generate(
                draft.answer,
                verification_result,
                evidence_slots,
                all_olta_results,
                verification_history=history,
            )
            final_answer.confidence_score = round(
                verification_result.overall_confidence * 100, 1
            )
            final_answer.confidence_label = verification_result.confidence_label
            final_answer.warnings = verification_result.warnings
            final_answer.verified_sources = final_generator.build_verified_source_cards(
                verification_result, evidence_slots, all_olta_results,
            )

            # 최종 답변 스트리밍
            final_queue: asyncio.Queue[str] = asyncio.Queue()

            async def on_final_token(chunk: str) -> None:
                await final_queue.put(sse_event("token", {"token": chunk}))

            for index in range(0, len(final_answer.answer), 5):
                await on_final_token(final_answer.answer[index : index + 5])
            while not final_queue.empty():
                yield await final_queue.get()

            yield stage_notice(
                f"최종 답변 정리 완료: 신뢰도 "
                f"{round(final_answer.confidence_score, 1)}%, "
                f"검증 {len(history.rounds)}회 수행."
            )

            process_summaries = _build_process_summaries(
                payload.question, search_plan, all_olta_results,
                verification_result, history, web_results,
            )
            session.crawl_cache.update({r.id: r for r in process_summaries})

        except Exception:
            logger.warning("검증/최종화 파이프라인 실패, 초안 반환", exc_info=True)
            fallback_warning = "검증 단계에 실패하여 웹 검색 기반 초안을 그대로 반환합니다."
            yield sse_event("stage_change", {"stage": "finalizing"})
            for index in range(0, len(fallback_warning), 5):
                yield sse_event("token", {"token": fallback_warning[index : index + 5]})
            final_answer = None

        # ──────────────────────────────────────────────
        # 출처 카드 + 신뢰도 전송
        # ──────────────────────────────────────────────
        if final_answer:
            sources = dedupe_source_cards(
                [r.to_source_card() for r in process_summaries]
                + [r.to_source_card() for r in evidence_slot_results]
                + final_answer.verified_sources
            )
            confidence = {
                "score": round(final_answer.confidence_score / 100, 2),
                "label": final_answer.confidence_label,
            } if final_answer.verified_sources else None
        else:
            sources = dedupe_source_cards(
                [r.to_source_card() for r in process_summaries]
                + [r.to_source_card() for r in evidence_slot_results]
                + [
                    r.to_source_card()
                    for r in all_olta_results
                    if not draft.cited_sources or r.id in draft.cited_sources
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

        crawl_summary = _build_crawl_summary(crawl_progress_stats)
        yield sse_event("crawl_summary", crawl_summary)
        crawl_summary_notice = _build_crawl_summary_notice(crawl_summary)
        if crawl_summary_notice:
            yield stage_notice(crawl_summary_notice)

        yield sse_event("sources", {"sources": sources, "confidence": confidence})
        yield sse_event("stage_change", {"stage": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


def _build_process_summaries(
    question: str,
    search_plan: SearchPlan,
    ranked_results,
    verification_result,
    history: VerificationHistory,
    web_results,
):
    settings = get_settings()
    searched_titles = [result.title for result in ranked_results[:5]]
    search_summary = CrawlResult(
        id="process_search_summary",
        title="질문 분석 및 검색 요약",
        type="처리 요약",
        preview=(
            f"{search_plan.question_type} 질문으로 판단했고 "
            f"웹 검색 {len(web_results)}건 + OLTA {len(ranked_results)}건을 수집했습니다."
        ),
        content="\n".join([
            f"질문: {question}",
            f"질문 유형: {search_plan.question_type}",
            f"추출 키워드: {', '.join(search_plan.keywords) if search_plan.keywords else question}",
            f"웹 검색 결과: {len(web_results)}건",
            f"OLTA 수집 결과: {len(ranked_results)}건",
            "상위 근거 문서:",
            *[f"- {title}" for title in searched_titles],
        ]),
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
        title="검증 이력 요약",
        type="처리 요약",
        preview=f"검증 {len(history.rounds)}회 수행, {confidence_line}",
        content="\n".join([
            "파이프라인 흐름:",
            "1. 웹 검색으로 초안 작성",
            "2. OLTA 자료 수집 및 1차 검증",
            "3. gap 분석 기반 추가 조사 및 재검증",
            "4. 최종 답변 생성 (검증 이력 포함)",
            "",
            "검증 이력:",
            history.to_summary(),
            "",
            confidence_line,
            (
                f"세부 지표: 주장 {round(verification_result.claim_confidence * 100, 1)}%, "
                f"출처 {round(verification_result.source_confidence * 100, 1)}%, "
                f"근거묶음 {round(verification_result.slot_confidence * 100, 1)}%"
                if verification_result
                else "세부 지표: 계산 불가"
            ),
        ]),
        url="",
        relevance_score=0.99,
        crawled_at=datetime.now(),
    )
    return [search_summary, verification_summary]


@router.get("/preview/{source_id}", response_model=SourceDetail)
async def preview(source_id: str, session_id: str):
    session = await require_session(session_id)
    source = session.crawl_cache.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="출처를 찾을 수 없습니다")
    return SourceDetail(**source.to_source_detail())
