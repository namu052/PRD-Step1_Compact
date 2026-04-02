"""OLTA 로그인 상태에서 18개 BBS 게시판 개별 수집 검증"""
import asyncio
import sys
import time
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

sys.stdout.reconfigure(encoding="utf-8")

import httpx

BASE = "http://127.0.0.1:8001"


async def main():
    print("=" * 70)
    print("OLTA BBS 18개 게시판 개별 수집 라이브 검증")
    print("=" * 70)

    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        # 1. OLTA 로그인 상태 확인
        resp = await client.get("/api/auth/olta-status")
        status = resp.json()
        print(f"\n[1] OLTA 로그인: {status['logged_in']}")
        if not status["logged_in"]:
            print("  ERROR: OLTA에 로그인되어 있지 않습니다!")
            return

        # 2. 세션 확보
        resp = await client.post(
            "/api/auth/gpki",
            json={"cert_id": "cert_001", "password": "test1234"},
        )
        auth = resp.json()
        print(f"[2] 세션 확보: {auth['user_name']} (session={auth['session_id'][:8]}...)")
        session_id = auth["session_id"]

    # 3. 채팅 요청 (SSE 스트리밍) - BBS 포함 전체 파이프라인
    print(f"\n[3] 파이프라인 실행 (BBS 포함)")
    query = "취득세 감면 요건"
    print(f"  검색어: {query}")

    stages = []
    notices = []
    tokens = []
    sources = []
    errors = []

    start = time.time()

    async with httpx.AsyncClient(base_url=BASE, timeout=300) as client:
        async with client.stream(
            "POST",
            "/api/chat",
            json={"session_id": session_id, "question": query},
        ) as resp:
            if resp.status_code != 200:
                print(f"  ERROR: HTTP {resp.status_code}")
                return

            import json
            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    raw_event, buffer = buffer.split("\n\n", 1)
                    event_type = ""
                    event_data = ""
                    for line in raw_event.strip().split("\n"):
                        if line.startswith("event: "):
                            event_type = line[7:]
                        elif line.startswith("data: "):
                            event_data = line[6:]

                    if not event_type or not event_data:
                        continue
                    try:
                        data = json.loads(event_data)
                    except json.JSONDecodeError:
                        continue

                    elapsed = round(time.time() - start, 1)

                    if event_type == "stage_change":
                        stage = data.get("stage", "")
                        stages.append(stage)
                        print(f"  [{elapsed:>6.1f}s] STAGE: {stage}")

                    elif event_type == "token":
                        tokens.append(data.get("token", ""))

                    elif event_type == "notice":
                        msg = data.get("message", "")
                        notices.append(msg)
                        print(f"  [{elapsed:>6.1f}s] NOTICE: {msg}")

                    elif event_type == "sources":
                        sources = data.get("sources", [])

                    elif event_type == "error":
                        errors.append(data.get("message", ""))
                        print(f"  [{elapsed:>6.1f}s] ERROR: {data.get('message')}")

    total = round(time.time() - start, 1)

    # ── 결과 분석 ──
    print(f"\n{'=' * 70}")
    print("검증 결과")
    print(f"{'=' * 70}")

    print(f"\n[시간] 총 {total}초")
    print(f"[단계] {' → '.join(stages)}")
    print(f"[알림] {len(notices)}건")
    for n in notices:
        print(f"  - {n}")

    # 출처 분석 - BBS 게시판별 태깅 확인
    print(f"\n[출처 분석] 전체 {len(sources)}건")

    type_counts = {}
    bbs_sources = []
    non_bbs_sources = []
    for s in sources:
        stype = s.get("type", "")
        type_counts[stype] = type_counts.get(stype, 0) + 1
        if stype.startswith("기타"):
            bbs_sources.append(s)
        else:
            non_bbs_sources.append(s)

    print(f"\n  유형별 출처:")
    for stype, count in sorted(type_counts.items()):
        print(f"    {stype}: {count}건")

    # 핵심 검증 1: BBS 게시판별 태깅 확인
    print(f"\n{'─' * 50}")
    print(f"[검증 1] 게시판별 태깅 (기타/게시판명)")
    print(f"{'─' * 50}")
    if bbs_sources:
        bbs_boards_found = set()
        for s in bbs_sources:
            board = s.get("type", "").replace("기타/", "")
            bbs_boards_found.add(board)
            print(f"  [{s['type']}] {s.get('title', '')[:60]}")
        print(f"\n  발견된 BBS 게시판: {len(bbs_boards_found)}개")
        for b in sorted(bbs_boards_found):
            print(f"    - {b}")
        has_slash = any("/" in s.get("type", "") for s in bbs_sources)
        print(f"\n  게시판별 태깅 여부: {'✅ 정상 (기타/게시판명 형식)' if has_slash else '❌ 실패 (기타 단일 태그)'}")
    else:
        print(f"  BBS 출처 없음 (검색어에 해당하는 BBS 자료가 없을 수 있음)")

    # 핵심 검증 2: 상세 페이지에서 수집된 내용 확인
    print(f"\n{'─' * 50}")
    print(f"[검증 2] 상세 페이지 수집 확인")
    print(f"{'─' * 50}")

    # preview API로 상세 내용/댓글 확인
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        bbs_detail_checked = 0
        bbs_with_comments = 0
        for s in bbs_sources[:5]:
            source_id = s.get("id", "")
            resp = await client.get(
                "/api/preview",
                params={"session_id": session_id, "source_id": source_id},
            )
            if resp.status_code == 200:
                detail = resp.json()
                content_len = len(detail.get("content", ""))
                comments = detail.get("comments", "")
                has_comments = bool(comments and len(comments) > 5)
                bbs_detail_checked += 1
                if has_comments:
                    bbs_with_comments += 1

                print(f"\n  [{s['type']}] {s.get('title', '')[:50]}")
                print(f"    내용 길이: {content_len}자")
                print(f"    댓글: {'있음' if has_comments else '없음'}")
                if has_comments:
                    print(f"    댓글 미리보기: {comments[:120]}...")
            else:
                print(f"  [{s['type']}] {source_id} - 상세 조회 실패 ({resp.status_code})")

        # 비BBS 출처도 댓글 확인
        for s in non_bbs_sources[:2]:
            source_id = s.get("id", "")
            resp = await client.get(
                "/api/preview",
                params={"session_id": session_id, "source_id": source_id},
            )
            if resp.status_code == 200:
                detail = resp.json()
                print(f"\n  (비교) [{s['type']}] {s.get('title', '')[:50]}")
                print(f"    내용 길이: {len(detail.get('content', ''))}자")
                print(f"    댓글: {'있음' if detail.get('comments') else '없음'}")

    # 핵심 검증 3: 댓글 수집 여부
    print(f"\n{'─' * 50}")
    print(f"[검증 3] BBS 댓글 수집")
    print(f"{'─' * 50}")
    print(f"  확인한 BBS 상세: {bbs_detail_checked}건")
    print(f"  댓글 있는 BBS: {bbs_with_comments}건")
    if bbs_detail_checked > 0:
        print(f"  댓글 수집률: {bbs_with_comments}/{bbs_detail_checked}")
    else:
        print(f"  (BBS 상세 자료 없음)")

    # 답변 요약
    answer = "".join(tokens)
    print(f"\n{'─' * 50}")
    print(f"[답변 요약]")
    print(f"{'─' * 50}")
    print(f"  길이: {len(answer)}자")
    print(f"  미리보기: {answer[:300]}...")

    if errors:
        print(f"\n[오류] {errors}")

    # 최종 판정
    print(f"\n{'=' * 70}")
    print("최종 검증 결과")
    print(f"{'=' * 70}")
    print(f"  1. 게시판별 태깅: {'✅' if any('/' in s.get('type','') for s in bbs_sources) else '⚠️ BBS 결과 없음 또는 미태깅'}")
    print(f"  2. BBS 수집 건수: {len(bbs_sources)}건")
    print(f"  3. 댓글 수집: {bbs_with_comments}건")
    print(f"  4. 전체 출처: {len(sources)}건")
    print(f"  5. 소요 시간: {total}초")


if __name__ == "__main__":
    asyncio.run(main())
