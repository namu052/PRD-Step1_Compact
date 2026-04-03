import asyncio
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
from fastapi.responses import StreamingResponse

from app.core.event_emitter import sse_event
from app.core.session_manager import session_manager
from app.models.schemas import (
    BoardCollectionStat,
    ChatRequest,
    CollectionProgress,
    CrawlResult,
    SourceDetail,
)
from app.services.crawler_service import crawler_service
from app.services.embedding_service import embedding_service
from app.services.evidence_group_service import evidence_group_service
from app.services.evidence_summary_service import evidence_summary_service
from app.services.llm_service import llm_service
from app.services.search_service import search_service

router = APIRouter(prefix="/api", tags=["chat"])


async def require_session(session_id: str):
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="유효한 세션이 필요합니다")
    return session


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
        # ──────────────────────────────────────────────
        # Stage 1: 자료 수집
        # ──────────────────────────────────────────────
        yield sse_event("stage_change", {"stage": "searching"})
        search_plan = await search_service.build_search_plan(payload.question)
        yield stage_notice(search_plan.to_notice())

        crawl_progress_stats: list[BoardCollectionStat] = []
        olta_event_queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_crawl_progress(stat: BoardCollectionStat) -> None:
            crawl_progress_stats.append(stat)
            await olta_event_queue.put(sse_event("crawl_progress", stat.model_dump()))

        try:
            olta_logged_in = await crawler_service.check_olta_login()
        except Exception:
            olta_logged_in = False

        if olta_logged_in:
            yield stage_notice("OLTA 로그인 확인 완료 - 기타(BBS) 게시판 포함 전체 수집합니다.")
        else:
            yield sse_event("olta_login_required", {
                "message": "OLTA 미로그인 상태입니다. 기타(BBS) 게시판 수집이 제한됩니다. OLTA 로그인 후 더 정확한 답변을 받을 수 있습니다.",
            })
            yield stage_notice("OLTA 미로그인 - 기존 법령/판례 자료만 수집합니다.")

        crawl_results = await _search_with_optional_progress(
            session,
            search_plan.keywords,
            search_plan.categories,
            on_progress=on_crawl_progress,
        )
        while not olta_event_queue.empty():
            yield await olta_event_queue.get()

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
            f"자료 수집 완료: {len(crawl_results)}건 수집, "
            f"{len(ranked_results)}건 우선 검토, 근거 묶음 {len(evidence_slots)}개 정리."
        )

        evidence_slot_results: list[CrawlResult] = [slot.to_crawl_result() for slot in evidence_slots]
        session.crawl_cache = {
            result.id: result for result in [*ranked_results, *evidence_slot_results]
        }

        # ──────────────────────────────────────────────
        # Stage 2: 최종 답변 생성
        # ──────────────────────────────────────────────
        yield sse_event("stage_change", {"stage": "answering"})

        try:
            draft = await llm_service.generate_draft(
                question=payload.question,
                crawl_results=ranked_results,
                evidence_slots=evidence_slots,
            )

            # 답변 스트리밍
            for index in range(0, len(draft.answer), 5):
                yield sse_event("token", {"token": draft.answer[index : index + 5]})

            yield stage_notice(
                f"답변 생성 완료: {len(ranked_results)}건의 자료를 기반으로 답변을 작성했습니다."
            )

        except Exception:
            logger.warning("답변 생성 실패, fallback 반환", exc_info=True)
            fallback_warning = "답변 생성에 실패했습니다. 다시 시도해 주세요."
            for index in range(0, len(fallback_warning), 5):
                yield sse_event("token", {"token": fallback_warning[index : index + 5]})
            draft = None

        # ──────────────────────────────────────────────
        # 출처 카드 전송
        # ──────────────────────────────────────────────
        sources = dedupe_source_cards(
            [r.to_source_card() for r in evidence_slot_results]
            + [
                r.to_source_card()
                for r in ranked_results
                if not draft or not draft.cited_sources or r.id in draft.cited_sources
            ]
        )

        crawl_summary = _build_crawl_summary(crawl_progress_stats)
        yield sse_event("crawl_summary", crawl_summary)
        crawl_summary_notice = _build_crawl_summary_notice(crawl_summary)
        if crawl_summary_notice:
            yield stage_notice(crawl_summary_notice)

        yield sse_event("sources", {"sources": sources, "confidence": None})
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
