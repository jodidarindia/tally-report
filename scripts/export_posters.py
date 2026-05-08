#!/usr/bin/env python3
"""
Export FLOWRA marketing-kit posters and carousel slides as high-res PNGs.

Renders /app/marketing-kit/posters.html in headless Chromium, removes the on-page
preview scaling, and screenshots each .poster element at its native resolution
(1080×1080). Outputs to /app/marketing-kit/exports/{posters,carousels}/ and
zips the lot to /app/marketing-kit/flowra-social-kit.zip.

Run:
    python3 /app/scripts/export_posters.py
"""
from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

KIT_DIR = Path("/app/marketing-kit")
HTML = KIT_DIR / "posters.html"
OUT = KIT_DIR / "exports"
POSTERS_OUT = OUT / "posters"
CAROUSELS_OUT = OUT / "carousels"
ZIP_PATH = KIT_DIR / "flowra-social-kit.zip"

POSTER_TITLES = {
    "p1":  "01-hero-brand-intro",
    "p2":  "02-beat-run-today",
    "p3":  "03-abcd-pareto",
    "p4":  "04-ca-corner-tally-parity",
    "p5":  "05-backups-dpdp",
    "p6":  "06-salesman-dashboard",
    "p7":  "07-dispatch-terminal",
    "p8":  "08-ai-reports-gpt52",
    "p9":  "09-outstanding-crm",
    "p10": "10-security-5min-setup",
    "p11": "11-made-in-india",
    "p12": "12-pricing-roi",
    "p13": "13-testimonial",
    "p14": "14-try-free-cta",
    "p15": "15-whatsapp-direct",
}

# Carousel container id -> (folder name, slide labels in order)
CAROUSELS = {
    "c1": ("c1-5-ways-pays-back", [
        "00-cover", "01-dead-stock", "02-overdues", "03-excel-time",
        "04-ghost-visits", "05-replace-ca-excel", "06-cta",
    ]),
    "c2": ("c2-beat-run-60sec", [
        "00-cover", "01-step-auto-built", "02-step-tap-visited",
        "03-step-day-end-lock", "04-cta",
    ]),
    "c3": ("c3-tally-data-flowra-decisions", [
        "00-cover", "01-problem", "02-solution", "03-result", "04-cta",
    ]),
    "c4": ("c4-abcd-explained", [
        "00-cover", "01-tier-a", "02-tier-b", "03-tier-c", "04-tier-d", "05-auto-abc",
    ]),
}


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


# CSS injected before screenshotting to undo the on-screen 50%-preview scaling
# and lay each poster out at native 1080×1080 with no surrounding chrome.
EXPORT_CSS = """
  body { background: #fff !important; padding: 0 !important; }
  .nav, .kit-title, .kit-sub, .poster-meta, .car-meta { display: none !important; }
  .grid, .car-row { display: block !important; gap: 0 !important; padding: 0 !important; }
  .poster-wrap { padding: 0 !important; background: none !important; border: 0 !important; margin: 0 !important; }
  /* Reset both square and story posters to native size */
  .poster { transform: none !important; margin: 0 !important; }
  .car-slide { width: 1080px !important; height: 1080px !important; flex-shrink: 0 !important;
               border-radius: 0 !important; overflow: hidden !important; margin: 0 !important; }
  .car-slide .inner { transform: none !important; width: 1080px !important; height: 1080px !important; }
"""


def _zip_dir(zip_path: Path, source_root: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(source_root.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(source_root.parent))
        # Bundle docs at the root of the zip too
        for extra in [KIT_DIR / "captions.md", KIT_DIR / "strategy.md"]:
            if extra.exists():
                zf.write(extra, extra.name)


def main() -> None:
    if not HTML.exists():
        raise SystemExit(f"posters.html not found at {HTML}")

    _reset_dir(OUT)
    POSTERS_OUT.mkdir(parents=True, exist_ok=True)
    CAROUSELS_OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1200, "height": 1200},
                                  device_scale_factor=2)
        page = ctx.new_page()
        page.goto(HTML.as_uri(), wait_until="networkidle")
        page.add_style_tag(content=EXPORT_CSS)
        # Wait for web fonts so headlines render correctly
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(400)

        # 1) 15 posters
        for poster_id, slug in POSTER_TITLES.items():
            sel = f"#{poster_id}"
            elem = page.locator(sel).first
            elem.wait_for(state="visible")
            out = POSTERS_OUT / f"{slug}.png"
            elem.screenshot(path=str(out), omit_background=False)
            print(f"  ✓ poster {poster_id:>3} → {out.relative_to(KIT_DIR)}")

        # 2) Carousel slides (each .car-slide > .inner > .poster)
        for car_id, (folder_slug, slide_labels) in CAROUSELS.items():
            car_dir = CAROUSELS_OUT / folder_slug
            car_dir.mkdir(parents=True, exist_ok=True)
            slides = page.locator(f"#{car_id} .car-slide .inner > .poster")
            count = slides.count()
            for i in range(count):
                label = slide_labels[i] if i < len(slide_labels) else f"{i:02d}-slide"
                out = car_dir / f"{label}.png"
                slides.nth(i).screenshot(path=str(out))
                print(f"  ✓ {car_id} slide {i+1}/{count} → {out.relative_to(KIT_DIR)}")

        browser.close()

    # Bundle a single zip the user can download
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    _zip_dir(ZIP_PATH, OUT)

    total = sum(1 for _ in OUT.rglob("*.png"))
    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"\nDone. {total} PNGs exported.")
    print(f"Zip: {ZIP_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
