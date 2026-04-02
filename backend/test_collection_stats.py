"""
OLTA collection stats test
- Shows per-board / per-sub-board collection progress in real-time
- Prints final summary in board > sub-board hierarchy
"""
import asyncio
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# backend 디렉토리 기준으로 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENAI_API_KEY", "test-not-needed")

from app.models.schemas import BoardCollectionStat

# ── 통계 집계 클래스 ──────────────────────────────────────

class CollectionStatsTracker:
    """게시판 > 서브 게시판 수집 통계를 실시간 추적"""

    def __init__(self):
        # { board_name: { sub_board_name|"__total__": BoardCollectionStat } }
        self.boards: dict[str, dict[str, BoardCollectionStat]] = defaultdict(dict)
        self.event_log: list[tuple[float, BoardCollectionStat]] = []
        self.start_time = time.time()

    async def on_progress(self, stat: BoardCollectionStat):
        """crawler_service의 on_progress 콜백"""
        elapsed = time.time() - self.start_time
        self.event_log.append((elapsed, stat))
        key = stat.sub_board_name or "__total__"
        self.boards[stat.board_name][key] = stat
        self._print_progress(elapsed, stat)

    def _print_progress(self, elapsed: float, stat: BoardCollectionStat):
        """실시간 진행 표시"""
        board = stat.board_name
        sub = stat.sub_board_name or ""
        status_icon = {
            "pending": "⏳",
            "collecting": "🔄",
            "done": "✅",
            "skipped": "⊘ ",
        }.get(stat.status, "?")

        location = f"{board}"
        if sub:
            location += f" > {sub}"

        if stat.status == "collecting":
            print(f"  [{elapsed:6.1f}s] {status_icon} {location} — 수집 중...")
        elif stat.status == "done":
            print(f"  [{elapsed:6.1f}s] {status_icon} {location} — {stat.collected_count}건 수집 완료")
        elif stat.status == "skipped":
            print(f"  [{elapsed:6.1f}s] {status_icon} {location} — 0건 (스킵)")
        else:
            print(f"  [{elapsed:6.1f}s] {status_icon} {location} — {stat.status}")

    def print_summary(self, total_results: int):
        """최종 집계 출력"""
        elapsed = time.time() - self.start_time
        print("\n")
        print("=" * 70)
        print(f"  OLTA 자료 수집 최종 집계  (소요시간: {elapsed:.1f}초)")
        print("=" * 70)

        grand_total = 0
        board_summaries = []

        for board_name in sorted(self.boards.keys()):
            subs = self.boards[board_name]
            board_collected = 0
            sub_details = []

            for sub_key, stat in sorted(subs.items()):
                if sub_key == "__total__":
                    if stat.status == "done":
                        board_collected += stat.collected_count
                    continue
                if stat.status == "done":
                    board_collected += stat.collected_count
                    sub_details.append((sub_key, stat.collected_count, False))
                elif stat.status == "skipped" or stat.skipped:
                    sub_details.append((sub_key, 0, True))

            # __total__만 있고 sub가 없는 경우
            if not sub_details and "__total__" in subs:
                total_stat = subs["__total__"]
                if total_stat.status == "done":
                    board_collected = total_stat.collected_count

            grand_total += board_collected
            board_summaries.append((board_name, board_collected, sub_details))

        print(f"\n  {'게시판':<28} {'수집건수':>8}   세부 내역")
        print("  " + "─" * 66)

        for board_name, board_total, sub_details in board_summaries:
            print(f"  {board_name:<28} {board_total:>6}건", end="")
            if sub_details:
                # 첫 줄에 최대 4개 서브 게시판
                shown = sub_details[:4]
                parts = []
                for name, count, skipped in shown:
                    if skipped:
                        parts.append(f"{name}(스킵)")
                    else:
                        parts.append(f"{name}({count})")
                print(f"   {', '.join(parts)}")

                # 나머지 서브 게시판
                remaining = sub_details[4:]
                while remaining:
                    batch = remaining[:4]
                    remaining = remaining[4:]
                    parts = []
                    for name, count, skipped in batch:
                        if skipped:
                            parts.append(f"{name}(스킵)")
                        else:
                            parts.append(f"{name}({count})")
                    print(f"  {'':28} {'':>8}    {', '.join(parts)}")
            else:
                print("   (서브 게시판 없음)")

        print("  " + "─" * 66)
        print(f"  {'합계':<28} {grand_total:>6}건")
        print(f"  {'CrawlResult 반환 건수':<28} {total_results:>6}건")
        print("=" * 70)

        # 스킵된 게시판 요약
        skipped_list = []
        for board_name, subs in self.boards.items():
            for sub_key, stat in subs.items():
                if stat.status == "skipped" or stat.skipped:
                    loc = board_name
                    if sub_key != "__total__":
                        loc += f" > {sub_key}"
                    skipped_list.append(loc)
        if skipped_list:
            print(f"\n  스킵된 게시판 ({len(skipped_list)}개):")
            for loc in skipped_list:
                print(f"    ⊘  {loc}")
        print()


# ── 메인 테스트 ──────────────────────────────────────────

async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "장애인 감면"
    print(f"\n{'=' * 70}")
    print(f"  OLTA 자료수집 통계 테스트")
    print(f"  검색어: \"{query}\"")
    print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 70}\n")

    # headless=False로 설정하여 브라우저 볼 수 있도록
    os.environ["PLAYWRIGHT_HEADLESS"] = "false"

    from app.config import get_settings
    settings = get_settings()
    # headless=False 강제
    settings.playwright_headless = False

    from app.services.crawler_service import CrawlerService
    crawler = CrawlerService()
    tracker = CollectionStatsTracker()

    try:
        # 1. 브라우저 시작 + OLTA 페이지 열기
        print("  [단계 1] 브라우저 시작 중...")
        await crawler.ensure_browser()
        print("  [단계 1] 브라우저 시작 완료\n")

        # 2. OLTA 로그인 확인
        print("  [단계 2] OLTA 로그인 상태 확인 중...")
        logged_in = await crawler.check_olta_login()

        if not logged_in:
            print("  [단계 2] OLTA 미로그인 상태입니다.")
            print("           Playwright 브라우저 창에서 OLTA에 로그인해주세요.")
            print("           3분 대기 -> 10초간격 6회 확인 -> 반복 (최대 5사이클)")
            await crawler.bring_browser_to_front()

            # 3분 대기 → 10초마다 6회 확인 → 반복
            max_cycles = 5
            for cycle in range(1, max_cycles + 1):
                # 3분 대기 (로그인 확인 안 함)
                print(f"           [사이클 {cycle}/{max_cycles}] 3분 대기 시작...")
                await asyncio.sleep(180)
                print(f"           [사이클 {cycle}/{max_cycles}] 대기 완료, 로그인 확인 시작")

                # 10초 간격으로 6회 확인
                for check in range(1, 7):
                    try:
                        logged_in = await crawler.check_olta_login()
                    except Exception:
                        logged_in = False
                    if logged_in:
                        break
                    print(f"           ... 확인 {check}/6 - 미로그인 (10초 후 재확인)")
                    if check < 6:
                        await asyncio.sleep(10)

                if logged_in:
                    break
                print(f"           [사이클 {cycle}/{max_cycles}] 로그인 안됨, 다음 사이클로...")

            if logged_in:
                print("  [단계 2] [OK] OLTA 로그인 확인 완료!\n")
            else:
                print("  [단계 2] [!!] 로그인되지 않았습니다. BBS 수집이 제한됩니다.\n")
        else:
            print("  [단계 2] [OK] OLTA 로그인 확인 완료!\n")

        # 3. 자료수집 시작 — 진행 현황 실시간 표시
        print("  [단계 3] 자료수집 시작")
        print("  " + "-" * 50)

        # DummySession 생성
        class DummySession:
            id = "test-session"

        results = await crawler.search(
            DummySession(),
            [query],
            categories=None,
            on_progress=tracker.on_progress,
        )
        print("  " + "-" * 50)

        # 4. 최종 집계 출력
        tracker.print_summary(total_results=len(results))

        # 5. 결과 샘플 출력
        if results:
            print(f"  수집 결과 샘플 (상위 10건):")
            print(f"  {'#':>3}  {'유형':<20} {'제목':<40} {'연도':>4}")
            print("  " + "-" * 70)
            for i, r in enumerate(results[:10], 1):
                title = r.title[:38] if len(r.title) > 38 else r.title
                year = str(r.document_year) if r.document_year else "-"
                print(f"  {i:>3}  {r.type:<20} {title:<40} {year:>4}")
            if len(results) > 10:
                print(f"  ... 외 {len(results) - 10}건")
            print()

    except KeyboardInterrupt:
        print("\n\n  [!!] 사용자에 의해 중단됨")
        tracker.print_summary(total_results=0)
    except Exception as e:
        print(f"\n  [ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        tracker.print_summary(total_results=0)
    finally:
        print("  브라우저 종료 중...")
        await crawler.close_browser()
        print("  완료.")


if __name__ == "__main__":
    asyncio.run(main())
