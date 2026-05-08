"""Re-generate the FLOWRA demo video using Sora 2 (May 2026 features).

Output: /app/frontend/public/flowra-demo.mp4
Used by: QuestionnaireForm.js Thank-You page (post-lead-enquiry).
"""
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(''))
load_dotenv('/app/backend/.env')

from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

PROMPT = """Modern Indian SME business analytics SaaS dashboard, FLOWRA branding.
4-second cinematic close-up: dark navy dashboard with electric blue (#0052FF) accents.
Camera pans across animated KPI cards showing INR amounts and "FY 2026-27" pill.
A/B/C/D inventory category pills snap into a grid in the foreground.
"Tally + Busy synced" status badge glows briefly.
Final beat: FLOWRA wordmark crisp on deep navy with tagline "From Tally and Busy. To Action."
Style: cinematic, smooth easing, crisp Cabinet Grotesk typography, no people, premium B2B feel."""


def main():
    print("Initialising Sora 2 client...")
    video_gen = OpenAIVideoGeneration(api_key=os.environ['EMERGENT_LLM_KEY'])

    print("Generating 4-second 1280x720 video (this can take 2-5 minutes)...")
    video_bytes = video_gen.text_to_video(
        prompt=PROMPT,
        model="sora-2",
        size="1280x720",
        duration=4,
        max_wait_time=600,
    )

    if not video_bytes:
        print("ERROR: Video generation returned empty bytes")
        sys.exit(1)

    out = '/app/frontend/public/flowra-demo.mp4'
    video_gen.save_video(video_bytes, out)
    print(f"OK Saved -> {out}")
    print(f"   Size: {os.path.getsize(out)/1024:.1f} KB")


if __name__ == "__main__":
    main()
