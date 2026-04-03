import asyncio
import logging
import os
import sys
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

os.environ["PLAYWRIGHT_HEADLESS"] = "False"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


async def main():
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()

    from app.services.crawler_service import crawler_service

    await crawler_service.ensure_browser()
    page = await crawler_service.ensure_shared_page()
    url = await crawler_service.open_olta_for_login()

    print("=" * 60)
    print("Shared OLTA page is ready")
    print(f"  profile dir : {settings.olta_shared_user_data_dir}")
    print(f"  page url    : {url}")
    print("  action      : complete OLTA login on the opened browser page")
    print("  popup       : browser launched with popup blocking disabled")
    print("  stop        : Ctrl+C")
    print("=" * 60)

    was_logged_in = False
    while True:
        logged_in = await crawler_service.check_olta_login(navigate=False)
        if logged_in and not was_logged_in:
            print("[OK] login confirmed on shared profile")
            was_logged_in = True
        elif not logged_in and was_logged_in:
            print("[WARN] login no longer detected")
            was_logged_in = False

        await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            from app.services.crawler_service import crawler_service

            asyncio.run(crawler_service.close_browser())
        except Exception:
            pass
