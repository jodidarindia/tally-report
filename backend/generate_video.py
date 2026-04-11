import sys
import os
sys.path.insert(0, os.path.abspath(''))
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration

prompt = """A sleek, modern business analytics dashboard showing real-time data visualizations. 
The camera slowly pans across a dark-themed dashboard with glowing blue charts, inventory graphs, 
sales trends lines, and customer data cards. Numbers animate smoothly. 
Professional SaaS software interface for Indian SME businesses. 
Clean typography, data tables with sorting, pie charts, bar graphs.
The text "FLOWRA" appears prominently. Tagline: Organize. Automate. Accelerate.
Corporate professional atmosphere with subtle animations."""

video_gen = OpenAIVideoGeneration(api_key=os.environ['EMERGENT_LLM_KEY'])
print("Starting video generation with Sora 2...")
video_bytes = video_gen.text_to_video(
    prompt=prompt,
    model="sora-2",
    size="1280x720",
    duration=8,
    max_wait_time=600
)

if video_bytes:
    output_path = '/app/frontend/public/flowra-demo.mp4'
    video_gen.save_video(video_bytes, output_path)
    print(f"Video saved to: {output_path}")
else:
    print("Video generation failed")
