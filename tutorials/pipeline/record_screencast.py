"""FLOWRA Academy — Playwright screencast recorder.

Records real browser sessions of the FLOWRA UI using the demo tenant
(demo@flowralive.in / demo2026), then hands off the WebM to the FFmpeg
composer which muxes Onyx voiceover + burned Hinglish captions + watermark.

Playbooks are stored in `screencast_playbooks.py` as async functions
`lesson_N(page)`. This keeps the timing of clicks/hovers explicit and
per-lesson tuneable.

Usage:
    python /app/tutorials/pipeline/record_screencast.py 1
"""
import asyncio
import os
import shutil
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
from screencast_playbooks import PLAYBOOKS   # noqa: E402

BASE_URL = os.environ.get(
    "FLOWRA_URL", "https://tally-report-ai.preview.emergentagent.com"
)
DEMO_USER = "demo@flowralive.in"
DEMO_PASS = "demo2026"

WEBM_DIR = Path("/app/tutorials/recordings")
WEBM_DIR.mkdir(parents=True, exist_ok=True)


async def _login_via_localstorage(context) -> None:
    """Bypass reCAPTCHA-protected login form by hitting the API directly
    and injecting the JWT into localStorage. Much more reliable than
    scripted keyboard input in headless."""
    import httpx
    r = httpx.post(f"{BASE_URL}/api/auth/login",
                   json={"username": DEMO_USER, "password": DEMO_PASS},
                   timeout=30)
    r.raise_for_status()
    token = r.json()["data"]["token"]
    await context.add_init_script(
        f"window.localStorage.setItem('flowra_token', '{token}');"
    )


async def record(lesson_n: int) -> Path:
    if lesson_n not in PLAYBOOKS:
        raise SystemExit(f"No playbook for lesson {lesson_n}")
    fn = PLAYBOOKS[lesson_n]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-gpu", "--no-sandbox",
        ])
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(WEBM_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        await _login_via_localstorage(context)
        page = await context.new_page()
        # Warm-up: land on dashboard so localStorage token is loaded
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1500)
        # Run the lesson playbook
        await fn(page)
        await page.close()   # flush video
        await context.close()
        await browser.close()

    # Playwright names the file with a random hash; rename to lesson-NN.webm
    webms = sorted(WEBM_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    if not webms:
        raise SystemExit("No WebM produced — playbook may have crashed silently")
    latest = webms[-1]
    target = WEBM_DIR / f"lesson-{lesson_n:02d}.webm"
    if target.exists():
        target.unlink()
    shutil.move(str(latest), str(target))
    print(f"✓ Recorded {target} ({target.stat().st_size // 1024} KB)")
    return target


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: record_screencast.py <lesson-n | all>")
        sys.exit(1)
    if sys.argv[1] == "all":
        for n in sorted(PLAYBOOKS.keys()):
            asyncio.run(record(n))
    else:
        asyncio.run(record(int(sys.argv[1])))


if __name__ == "__main__":
    main()
