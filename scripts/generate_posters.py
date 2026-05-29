"""iter-111 helper — generate 2 FLOWRA social-media posters with Nano Banana.

Saves PNGs to /app/frontend/public/posters/ so they're downloadable at:
  <REACT_APP_BACKEND_URL>/posters/<filename>.png
"""
import asyncio
import base64
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env so EMERGENT_LLM_KEY is in os.environ.
load_dotenv("/app/backend/.env")

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

OUT_DIR = Path("/app/frontend/public/posters")
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("EMERGENT_LLM_KEY")
if not API_KEY:
    sys.exit("EMERGENT_LLM_KEY missing")

# Brand palette: FLOWRA blue #2563EB, deep navy #0F1B4C, amber accent #f59e0b.
# Both posters are 1080x1080 (Instagram / LinkedIn / WhatsApp square).
PROMPTS = {
    "flowra-salesman-poster.png": (
        "Design a modern 1080x1080 square SOCIAL-MEDIA POSTER for an Indian B2B "
        "SaaS product called FLOWRA INSIGHTS, targeting field sales teams.\n\n"
        "VISUAL STYLE:\n"
        "- Bold, confident, modern fintech / SaaS aesthetic — NOT cartoonish, NOT clip-art.\n"
        "- Background: deep navy gradient (#0F1B4C base, brighter towards top-right corner).\n"
        "- Accent color: vivid blue #2563EB on highlights, amber #f59e0b on the call-to-action.\n"
        "- Subtle abstract geometric pattern in the background (dotted grid + diagonal lines).\n"
        "- A photorealistic Indian male sales executive (smart casual shirt, around 30 years old) "
        "  on the LEFT THIRD of the poster, smiling confidently, holding a smartphone showing a "
        "  beat-route map. He is shot at 3/4 angle, professional lighting.\n"
        "- On the RIGHT TWO-THIRDS: a clean stack of UI cards / floating mockups showing a beat "
        "  plan list with green check-marks ('Visited'), a small revenue chart trending UP, and "
        "  a pill labelled '85% Coverage'. The mockups have crisp drop-shadows and a slight tilt.\n\n"
        "TYPOGRAPHY (must be sharp, readable, no spelling errors):\n"
        "- TOP-RIGHT corner small wordmark: 'FLOWRA INSIGHTS' in white, semi-bold, letter-spacing 0.1em.\n"
        "- BIG HEADLINE (top-centre, bold white sans-serif, 88pt):\n"
        "    'YOUR FIELD FORCE.\n"
        "     ALWAYS ON TARGET.'\n"
        "- SUBHEAD (under the headline, light grey, 32pt):\n"
        "    'Beat plans · Daily check-ins · Order capture · Payment tracking — built for India.'\n"
        "- BOTTOM-CENTRE pill button (amber #f59e0b, dark navy text, 36pt):\n"
        "    'Start free at flowralive.in'\n"
        "- BOTTOM-LEFT small caption: 'Powered by Tally & Busy integration.'\n\n"
        "CRITICAL: NO misspellings. NO Lorem ipsum. NO faces other than the one salesman. Composition "
        "must feel premium — like Stripe / Razorpay / Slack marketing material."
    ),
    "flowra-dispatch-poster.png": (
        "Design a modern 1080x1080 square SOCIAL-MEDIA POSTER for an Indian B2B SaaS product called "
        "FLOWRA INSIGHTS, targeting warehouse / dispatch operations.\n\n"
        "VISUAL STYLE:\n"
        "- Bold modern logistics aesthetic — feels like a premium fintech, NOT a stock-photo collage.\n"
        "- Background: clean off-white #F8FAFC at the top, transitioning to deep navy #0F1B4C at the "
        "  bottom (diagonal gradient).\n"
        "- Accent color: vivid blue #2563EB on UI elements, amber #f59e0b on a single CTA pill.\n"
        "- LEFT HALF: a sharp, photorealistic warehouse / dispatch counter scene — neat stacks of "
        "  cardboard cartons labelled 'INV', a wall-mounted tablet showing a kanban board, a dispatch "
        "  employee (Indian, navy-blue uniform, 30s) scanning a parcel with a barcode scanner. Soft "
        "  warehouse lighting, slightly desaturated for a clean editorial feel.\n"
        "- RIGHT HALF: a stack of crisp UI mockup cards floating above the scene — a 4-column KANBAN "
        "  board (columns: NEW / QUEUED / PACKED / DISPATCHED) with sample invoice cards in each column. "
        "  One card highlighted in amber says 'INV-1234 · Krishna Sales · Bilty uploaded ✓'. The cards "
        "  have a subtle drop-shadow and tilt.\n\n"
        "TYPOGRAPHY (sharp, readable, no spelling errors):\n"
        "- TOP-LEFT small wordmark: 'FLOWRA INSIGHTS' in deep navy, semi-bold, letter-spacing 0.1em.\n"
        "- BIG HEADLINE (centre-top, bold deep-navy sans-serif, 88pt):\n"
        "    'FROM INVOICE\n"
        "     TO DOORSTEP.'\n"
        "- Below headline, smaller (52pt, blue #2563EB):\n"
        "    'ZERO PAPER. ZERO MISS.'\n"
        "- SUBHEAD (light grey, 30pt):\n"
        "    'Kanban dispatch board · LR/Bilty uploads · Tally + Busy auto-sync · Built for India.'\n"
        "- BOTTOM-CENTRE pill button (amber #f59e0b, dark navy text, 36pt):\n"
        "    'See it live at flowralive.in'\n"
        "- BOTTOM-RIGHT tiny caption (white): 'Trusted by Indian SMEs.'\n\n"
        "CRITICAL: NO misspellings. NO Lorem ipsum. The single dispatch employee should be the only "
        "person on the poster. Premium feel — like a Shopify / Razorpay launch poster."
    ),
}


async def generate_one(filename: str, prompt: str) -> None:
    out_path = OUT_DIR / filename
    print(f"\n→ {filename}")
    print(f"  out: {out_path}")
    # Always create a fresh LlmChat per session — per playbook.
    chat = LlmChat(
        api_key=API_KEY,
        session_id=f"poster-{filename}",
        system_message="You are a top-tier brand designer producing print-ready social media posters."
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

    msg = UserMessage(text=prompt)
    text, images = await chat.send_message_multimodal_response(msg)
    if text:
        # Only show first 80 chars of any text response — never the full base64 of images.
        print(f"  text (truncated): {text[:80]!r}")
    if not images:
        print("  ✗ no image returned — provider may have refused. Skipping.")
        return
    img = images[0]
    print(f"  mime: {img.get('mime_type')}")
    image_bytes = base64.b64decode(img["data"])
    out_path.write_bytes(image_bytes)
    print(f"  ✓ wrote {len(image_bytes):,} bytes")


async def main():
    for fname, prompt in PROMPTS.items():
        try:
            await generate_one(fname, prompt)
        except Exception as e:
            print(f"  ✗ failed {fname}: {e!r}")


if __name__ == "__main__":
    asyncio.run(main())
