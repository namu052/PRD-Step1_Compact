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

    def print_summary(self, total_results: int, results: list = None):
        """최종 집계 출력 — 서브게시판별 제목 리스트 포함"""
        elapsed = time.time() - self.start_time

        print("\n")
        print("=" * 80)
        print(f"  OLTA 자료 수집 최종 집계  (소요시간: {elapsed:.1f}초)")
        print("=" * 80)

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
                    sub_details.append((sub_key, stat.collected_count, False, stat.titles))
                elif stat.status == "skipped" or stat.skipped:
                    sub_details.append((sub_key, 0, True, []))

            # __total__만 있고 sub가 없는 경우
            if not sub_details and "__total__" in subs:
                total_stat = subs["__total__"]
                if total_stat.status == "done":
                    board_collected = total_stat.collected_count
                    sub_details.append(("(전체)", total_stat.collected_count, False, total_stat.titles))

            grand_total += board_collected
            board_summaries.append((board_name, board_collected, sub_details))

        # ── 게시판별 상세 (집계 + 제목 리스트) ──
        skipped_count = 0
        board_num = 0
        for board_name, board_total, sub_details in board_summaries:
            board_num += 1
            print(f"\n  {'━' * 76}")
            print(f"  [{board_num}] {board_name}  (소계: {board_total}건)")
            print(f"  {'━' * 76}")

            if sub_details:
                for name, count, skipped, titles in sub_details:
                    if skipped:
                        skipped_count += 1
                        print(f"    ⊘ {name} — 스킵 (0건)")
                        continue

                    print(f"    ✅ {name} — {count}건 수집")

                    if titles:
                        print(f"    {'─' * 72}")
                        print(f"    {'#':>4}  제목")
                        print(f"    {'─' * 72}")
                        for i, title in enumerate(titles, 1):
                            t = title[:68] if len(title) > 68 else title
                            print(f"    {i:>4}  {t}")
                        print()

        # ── 총 합계 ──
        print(f"\n  {'=' * 76}")
        print(f"  총 수집 건수:         {grand_total:>6}건")
        print(f"  CrawlResult 반환:     {total_results:>6}건  (중복 제거 후)")
        if skipped_count:
            print(f"  스킵된 서브게시판:     {skipped_count:>6}개")
        print(f"  {'=' * 76}")
        print()

    def save_full_results(self, results: list, query: str, output_path: str):
        """CrawlResult 전체 내용을 파일로 저장"""
        elapsed = time.time() - self.start_time

        # type별로 그룹핑
        by_type: dict[str, list] = defaultdict(list)
        for r in results:
            by_type[r.type].append(r)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("=" * 90 + "\n")
            f.write(f"  OLTA 자료 수집 전체 결과\n")
            f.write(f"  검색어: \"{query}\"\n")
            f.write(f"  수집일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"  소요시간: {elapsed:.1f}초\n")
            f.write(f"  CrawlResult 총 건수: {len(results)}건\n")
            f.write("=" * 90 + "\n\n")

            global_idx = 0
            for type_key in sorted(by_type.keys()):
                items = by_type[type_key]
                f.write("━" * 90 + "\n")
                f.write(f"  [{type_key}]  —  {len(items)}건\n")
                f.write("━" * 90 + "\n\n")

                for i, r in enumerate(items, 1):
                    global_idx += 1
                    year = str(r.document_year) if r.document_year else "-"
                    f.write(f"  ── [{global_idx}] ──────────────────────────────────────\n")
                    f.write(f"  제목: {r.title}\n")
                    f.write(f"  유형: {r.type}\n")
                    f.write(f"  연도: {year}\n")
                    f.write(f"  ID:   {r.id}\n")
                    f.write(f"  URL:  {r.url}\n")
                    f.write(f"  관련도: {r.relevance_score:.2f}\n")
                    if r.comments:
                        f.write(f"  댓글: {r.comments}\n")
                    f.write(f"\n  [미리보기]\n")
                    f.write(f"  {r.preview}\n")
                    f.write(f"\n  [본문]\n")
                    # 본문을 줄단위로 들여쓰기
                    for line in r.content.split("\n"):
                        f.write(f"  {line}\n")
                    f.write("\n\n")

            f.write("=" * 90 + "\n")
            f.write(f"  총 {global_idx}건 출력 완료\n")
            f.write("=" * 90 + "\n")

        print(f"  >>> 전체 결과 저장: {output_path}")
        print(f"      ({global_idx}건, {os.path.getsize(output_path):,} bytes)")


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

        # 4. 최종 집계 + 제목 리스트 출력
        tracker.print_summary(total_results=len(results), results=results)

        # 5. 전체 결과를 파일로 저장
        if results:
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "collection_result.txt",
            )
            tracker.save_full_results(results, query, output_path)

    except KeyboardInterrupt:
        print("\n\n  [!!] 사용자에 의해 중단됨")
        tracker.print_summary(total_results=0, results=[])
    except Exception as e:
        print(f"\n  [ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        tracker.print_summary(total_results=0, results=[])
    finally:
        print("  브라우저 종료 중...")
        await crawler.close_browser()
        print("  완료.")


if __name__ == "__main__":
    asyncio.run(main())
