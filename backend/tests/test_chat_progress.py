from app.models.schemas import BoardCollectionStat
from app.routers.chat import _build_collection_progress, _build_crawl_summary


def test_build_collection_progress_uses_latest_board_state():
    stats = [
        BoardCollectionStat(board_name="법원 판례", sub_board_name="취득", status="collecting"),
        BoardCollectionStat(
            board_name="법원 판례",
            sub_board_name="취득",
            collected_count=5,
            status="done",
        ),
        BoardCollectionStat(board_name="기타", sub_board_name="FAQ", status="collecting"),
    ]

    progress = _build_collection_progress(stats)

    assert progress.total_collected == 5
    assert len(progress.boards) == 2
    assert progress.current_board == "기타"
    assert progress.current_sub_board == "FAQ"


def test_build_crawl_summary_groups_main_and_sub_boards():
    stats = [
        BoardCollectionStat(
            board_name="법원 판례",
            sub_board_name="취득",
            collected_count=5,
            status="done",
        ),
        BoardCollectionStat(
            board_name="법원 판례",
            sub_board_name="재산",
            skipped=True,
            status="skipped",
        ),
        BoardCollectionStat(
            board_name="기타",
            sub_board_name="FAQ",
            collected_count=3,
            status="done",
        ),
    ]

    summary = _build_crawl_summary(stats)

    assert summary["grand_total"] == 8
    assert len(summary["boards"]) == 2

    case_board = next(board for board in summary["boards"] if board["board_name"] == "법원 판례")
    assert case_board["total_collected"] == 5
    assert case_board["sub_boards"] == [
        {"name": "취득", "collected_count": 5, "skipped": False, "status": "done"},
        {"name": "재산", "collected_count": 0, "skipped": True, "status": "skipped"},
    ]
