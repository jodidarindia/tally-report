"""Per-lesson Playwright playbooks. Each is timed to match the ONYX
voiceover of the same lesson so a 50-sec audio pairs with ~50-sec of UI.

Timing anchors (from /app/tutorials/subtitles/lesson-NN.srt):
  Lesson 01: 50 sec total
  Lesson 02: ~40 sec total
"""
import asyncio


async def _pause(page, sec: float) -> None:
    """Slight wobble to feel natural (not robotic)."""
    await page.wait_for_timeout(int(sec * 1000))


async def _smooth_hover(page, selector: str, dwell: float = 0.8) -> None:
    """Move to element with a short pause — makes cursor visible + intentional."""
    try:
        loc = page.locator(selector).first
        if await loc.count() > 0:
            await loc.hover(force=True)
            await _pause(page, dwell)
    except Exception:
        pass


async def lesson_1(page) -> None:
    """FLOWRA kya hai? — 50 sec.
    Story: land on FLOWRA, breeze past company selector, land on
    Dashboard, tour 4 stat cards, hover 4 tabs, glance at What's New."""
    import os
    base = os.environ.get(
        "FLOWRA_URL", "https://tally-report-ai.preview.emergentagent.com"
    ).rstrip("/")

    # (0–5s) Land on Dashboard
    await page.goto(f"{base}/dashboard", wait_until="networkidle", timeout=30000)
    await _pause(page, 2.0)

    # If Select Company modal shows up (demo tenant has 3), click first + Continue
    try:
        cards = page.locator("text=Sharma Lubricants").first
        if await cards.count():
            await cards.click(force=True)
            await _pause(page, 1.2)
            cont = page.get_by_role("button", name="Continue").first
            if await cont.count():
                await cont.click(force=True)
                await _pause(page, 3.0)
    except Exception:
        pass

    # Wait for dashboard-page to render
    try:
        await page.wait_for_selector('[data-testid="dashboard-page"]', timeout=8000)
    except Exception:
        pass
    await _pause(page, 1.5)

    # (8–22s) Slow hover of the top KPI cards
    await _smooth_hover(page, '[data-testid^="stat-"]:nth-of-type(1)', 1.5)
    await _smooth_hover(page, '[data-testid^="stat-"]:nth-of-type(2)', 1.5)
    await _smooth_hover(page, '[data-testid^="stat-"]:nth-of-type(3)', 1.5)
    await _smooth_hover(page, '[data-testid^="stat-"]:nth-of-type(4)', 1.5)

    # (22–38s) Hover 4 tabs
    for tab in ["Sales", "CRM", "Inventory", "Analytics"]:
        try:
            btn = page.get_by_role("button", name=tab).first
            if await btn.count():
                await btn.hover(force=True)
                await _pause(page, 1.5)
        except Exception:
            pass

    # (38–50s) Scroll to What's New panel
    await page.mouse.wheel(0, 500)
    await _pause(page, 4.0)
    await page.mouse.wheel(0, 400)
    await _pause(page, 3.5)


async def lesson_2(page) -> None:
    """Pehli baar login kaise karein — ~40 sec.
    Story: land on FLOWRA home page, hover the top nav, click Login,
    show the login screen briefly, then transition to Dashboard.
    We skip actual form typing because reCAPTCHA blocks headless submits."""
    import os
    base = os.environ.get("FLOWRA_URL", "https://tally-report-ai.preview.emergentagent.com").rstrip("/")

    # (0–8s) Sign out state — clear token, land on landing page
    await page.evaluate("localStorage.removeItem('flowra_token');")
    await page.goto(base, wait_until="networkidle", timeout=30000)
    await _pause(page, 4.0)

    # (8–14s) Slow scroll — show the hero + features
    await page.mouse.wheel(0, 300)
    await _pause(page, 2.5)
    await page.mouse.wheel(0, -300)
    await _pause(page, 1.5)

    # (14–22s) Hover then click the Login button
    try:
        btn = page.get_by_role("button", name="Login").first
        if await btn.count():
            await btn.hover(force=True)
            await _pause(page, 1.5)
            await btn.click(force=True)
            await _pause(page, 3.0)
    except Exception:
        pass

    # (22–30s) Camera lingers on the login screen so viewer sees "email +
    # password + Sign In" without keyboard input
    await _pause(page, 5.5)

    # (30–42s) Simulate successful login by injecting token + navigating.
    # This gives a natural cut to the Dashboard for the viewer.
    import httpx
    r = httpx.post(f"{base}/api/auth/login",
                   json={"username": "demo@flowralive.in", "password": "demo2026"},
                   timeout=15)
    r.raise_for_status()
    token = r.json()["data"]["token"]
    await page.evaluate(f"localStorage.setItem('flowra_token','{token}');")
    await page.goto(f"{base}/dashboard", wait_until="networkidle", timeout=30000)
    # Handle Select Company modal that appears for demo tenant
    try:
        cards = page.locator("text=Sharma Lubricants").first
        if await cards.count():
            await cards.click(force=True)
            await _pause(page, 1.0)
            cont = page.get_by_role("button", name="Continue").first
            if await cont.count():
                await cont.click(force=True)
                await _pause(page, 2.0)
    except Exception:
        pass
    await _pause(page, 4.0)


PLAYBOOKS = {
    1: lesson_1,
    2: lesson_2,
}
