from app.services.crawler_service import (
    BBS_BOARDS,
    BBSBoardDefinition,
    BBSResultCard,
    crawler_service,
)


def test_resolve_bbs_detail_url_from_onclick_absolute_url():
    onclick = "javascript:bbsPopUp('https://www.olta.re.kr/board/view.do?bbsId=B001&nttId=12345')"

    detail_url = crawler_service._resolve_bbs_detail_url(
        onclick=onclick,
        href="",
        current_url="https://www.olta.re.kr/search/PU_0003_search.jsp",
    )

    assert detail_url == "https://www.olta.re.kr/board/view.do?bbsId=B001&nttId=12345"


def test_resolve_bbs_detail_url_from_relative_href():
    detail_url = crawler_service._resolve_bbs_detail_url(
        onclick="",
        href="/board/view.do?bbsId=B009&nttId=77",
        current_url="https://www.olta.re.kr/search/PU_0003_search.jsp",
    )

    assert detail_url == "https://www.olta.re.kr/board/view.do?bbsId=B009&nttId=77"


def test_build_bbs_canonical_id_uses_bbs_and_ntt_id():
    board = BBSBoardDefinition(
        label="sample",
        value="sample",
        normalized_key="sample",
        type_label="기타/sample",
    )

    canonical_id = crawler_service._build_bbs_canonical_id(
        detail_url="https://www.olta.re.kr/board/view.do?bbsId=B777&nttId=9001",
        board=board,
        index=0,
    )

    assert canonical_id == "olta_bbs_B777_9001"


def test_parse_js_call_extracts_bbs_popup_function_and_args():
    parsed = crawler_service._parse_js_call(
        "javascript:bbsPopUp('https://www.olta.re.kr/board/view.do?bbsId=B001&nttId=12345')"
    )

    assert parsed is not None
    assert parsed["function_name"] == "bbsPopUp"
    assert parsed["args"][0] == "https://www.olta.re.kr/board/view.do?bbsId=B001&nttId=12345"


def test_build_bbs_detail_url_from_identifiers():
    detail_url = crawler_service._build_bbs_detail_url_from_identifiers(
        bbs_id="B123",
        ntt_id="4567",
        current_url="https://www.olta.re.kr/search/PU_0003_search.jsp",
    )

    assert detail_url == "https://www.olta.re.kr/board/view.do?bbsId=B123&nttId=4567"


def test_build_bbs_open_target_prefers_direct_url():
    board = BBSBoardDefinition(
        label="sample",
        value="sample",
        normalized_key="sample",
        type_label="etc/sample",
    )
    card = BBSResultCard(
        title="sample title",
        meta="",
        preview="",
        onclick="javascript:bbsPopUp('https://www.olta.re.kr/board/view.do?bbsId=B009&nttId=77')",
        href="",
        detail_url=None,
        canonical_id=None,
        row_index=0,
    )

    target = crawler_service._build_bbs_open_target(
        result_card=card,
        current_url="https://www.olta.re.kr/search/PU_0003_search.jsp",
        board=board,
    )

    assert target.mode == "direct_url"
    assert target.detail_url == "https://www.olta.re.kr/board/view.do?bbsId=B009&nttId=77"
    assert target.requires_click is False


def test_build_bbs_open_target_marks_popup_click_when_only_target_blank_exists():
    board = BBSBoardDefinition(
        label="sample",
        value="sample",
        normalized_key="sample",
        type_label="etc/sample",
    )
    card = BBSResultCard(
        title="popup only",
        meta="",
        preview="",
        onclick="javascript:bbsPopUp('')",
        href="#",
        detail_url=None,
        canonical_id=None,
        target_attr="_blank",
        row_index=0,
    )

    target = crawler_service._build_bbs_open_target(
        result_card=card,
        current_url="https://www.olta.re.kr/search/PU_0003_search.jsp",
        board=board,
    )

    assert target.mode == "popup_click"
    assert target.requires_click is True


def test_merge_bbs_board_records_prefers_discovered_value_for_known_board():
    known_board = BBS_BOARDS[0]

    merged = crawler_service._merge_bbs_board_records(
        [
            {
                "label": known_board,
                "value": "BOARD_001",
                "source": "option",
            }
        ]
    )

    matching = next(
        board for board in merged
        if board.normalized_key == crawler_service._normalize_bbs_label(known_board)
    )

    assert matching.label == known_board
    assert matching.value == "BOARD_001"


def test_merge_bbs_board_records_skips_placeholder_entries():
    merged = crawler_service._merge_bbs_board_records(
        [
            {"label": "전체", "value": "", "source": "option"},
            {"label": "선택", "value": "", "source": "option"},
        ]
    )

    normalized_keys = {board.normalized_key for board in merged}

    assert crawler_service._normalize_bbs_label("전체") not in normalized_keys
    assert crawler_service._normalize_bbs_label("선택") not in normalized_keys
