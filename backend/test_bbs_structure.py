"""BBS 코드 구조 검증 (OLTA 로그인 불필요)"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.services.crawler_service import BBS_BOARDS, POPUP_TYPE_MAP, crawler_service
from app.config import get_settings

print("=== BBS 코드 구조 검증 ===\n")

print(f"[1] BBS_BOARDS: {len(BBS_BOARDS)}개")
for i, b in enumerate(BBS_BOARDS, 1):
    print(f"  {i:2d}. {b}")

print(f"\n[2] POPUP_TYPE_MAP['bbsPopUp'] = '{POPUP_TYPE_MAP['bbsPopUp']}'")

print(f"\n[3] 메서드 존재 확인")
print(f"  _search_all_bbs_boards: {hasattr(crawler_service, '_search_all_bbs_boards')}")
print(f"  _search_single_bbs_board: {hasattr(crawler_service, '_search_single_bbs_board')}")

s = get_settings()
print(f"\n[4] BBS 관련 설정")
print(f"  olta_bbs_max_pages_per_board: {s.olta_bbs_max_pages_per_board}")
print(f"  olta_bbs_concurrency: {s.olta_bbs_concurrency}")

print(f"\n[5] 타입 라벨 형식 예시")
for b in BBS_BOARDS[:5]:
    print(f"  기타/{b}")

print(f"\n코드 구조 검증 완료!")
