import os
from dotenv import load_dotenv
import logging
import json
from typing import Dict, Any, List
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

load_dotenv()

class AIReportService:
    """
    Service for AI-powered report generation using OpenAI GPT-5.2
    """
    
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY")
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment")
    
    async def generate_report(self, query: str, inventory_data: List[Dict], sales_data: List[Dict]) -> Dict[str, Any]:
        """
        Generate AI-powered report based on natural language query.
        
        Args:
            query: Natural language query from user
            inventory_data: List of inventory items
            sales_data: List of sales vouchers
            
        Returns:
            Dictionary containing report insights and analysis
        """
        try:
            # Create chat instance
            chat = LlmChat(
                api_key=self.api_key,
                session_id="report_builder_session",
                system_message="""You are an expert financial analyst and report builder. 
                Your task is to analyze inventory and sales data from Tally and provide clear, actionable insights.
                Always structure your response as JSON with the following format:
                {
                    "summary": "Brief overview of findings",
                    "key_insights": ["insight 1", "insight 2", ...],
                    "metrics": {"metric_name": value, ...},
                    "recommendations": ["recommendation 1", "recommendation 2", ...]
                }
                Be concise, data-driven, and business-focused."""
            ).with_model("openai", "gpt-5.2")
            
            # Prepare context with data
            context = f"""
            USER QUERY: {query}
            
            INVENTORY DATA ({len(inventory_data)} items):
            {json.dumps(inventory_data[:20], indent=2)}
            
            SALES DATA ({len(sales_data)} transactions):
            {json.dumps(sales_data[:20], indent=2)}
            
            Analyze the data and respond to the user's query with actionable insights.
            """
            
            user_message = UserMessage(text=context)
            response = await chat.send_message(user_message)
            
            # Parse response
            try:
                report_data = json.loads(response)
            except json.JSONDecodeError:
                # If response is not JSON, structure it
                report_data = {
                    "summary": response[:500],
                    "key_insights": [response],
                    "metrics": {},
                    "recommendations": []
                }
            
            return {
                "success": True,
                "query": query,
                "report": report_data,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error generating AI report: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
