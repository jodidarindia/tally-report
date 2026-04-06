import os
from dotenv import load_dotenv
import logging
import json
from typing import Dict, Any, List
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
load_dotenv()

class EnhancedAIReportService:
    """
    Enhanced AI service with comprehensive report building capabilities
    """
    
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY")
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found")
    
    async def generate_advanced_report(self, query: str, report_type: str, filters: Dict, 
                                      inventory_data: List[Dict], sales_data: List[Dict],
                                      customer_data: List[Dict] = None) -> Dict[str, Any]:
        """
        Generate comprehensive AI-powered reports with filters
        """
        try:
            system_prompts = {
                'inventory': self._get_inventory_analyst_prompt(),
                'sales': self._get_sales_analyst_prompt(),
                'customer': self._get_customer_analyst_prompt(),
                'profit': self._get_profit_analyst_prompt(),
                'movement': self._get_movement_analyst_prompt(),
                'general': self._get_general_analyst_prompt()
            }
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"report_{report_type}",
                system_message=system_prompts.get(report_type, system_prompts['general'])
            ).with_model("openai", "gpt-5.2")
            
            # Apply filters to data
            filtered_inventory = self._apply_filters(inventory_data, filters)
            filtered_sales = self._apply_filters(sales_data, filters)
            filtered_customers = self._apply_filters(customer_data or [], filters)
            
            context = self._build_context(
                query, report_type, filters,
                filtered_inventory, filtered_sales, filtered_customers
            )
            
            user_message = UserMessage(text=context)
            response = await chat.send_message(user_message)
            
            try:
                report_data = json.loads(response)
            except json.JSONDecodeError:
                report_data = {
                    "summary": response[:500],
                    "key_insights": [response],
                    "metrics": {},
                    "recommendations": [],
                    "detailed_analysis": response
                }
            
            return {
                "success": True,
                "query": query,
                "report_type": report_type,
                "filters_applied": filters,
                "report": report_data,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error generating AI report: {e}")
            return {"success": False, "error": str(e), "query": query}
    
    def _get_inventory_analyst_prompt(self) -> str:
        return """You are an expert inventory analyst for businesses using TallyPrime.
        
        Analyze inventory data and provide insights on:
        - Stock levels and turnover rates
        - Slow-moving and fast-moving items
        - Reorder recommendations
        - Category-wise performance
        - Dead stock identification
        - Inventory value optimization
        
        Always respond in JSON format:
        {
            "summary": "Brief executive summary",
            "key_insights": ["insight 1", "insight 2", ...],
            "metrics": {"metric_name": value, ...},
            "recommendations": ["action 1", "action 2", ...],
            "detailed_analysis": "In-depth analysis with specific numbers"
        }
        
        Be specific, data-driven, and actionable."""
    
    def _get_sales_analyst_prompt(self) -> str:
        return """You are an expert sales analyst specializing in retail and distribution.
        
        Analyze sales data focusing on:
        - Revenue trends and patterns
        - Top-performing customers
        - Seasonal variations
        - Sales by product category
        - Average transaction value
        - Sales growth rates
        - Conversion opportunities
        
        Respond in JSON format with summary, key_insights, metrics, recommendations, and detailed_analysis.
        Highlight both opportunities and concerns."""
    
    def _get_customer_analyst_prompt(self) -> str:
        return """You are a CRM and customer relationship expert.
        
        Analyze customer data including:
        - Payment behavior patterns
        - Outstanding amounts and aging
        - Customer lifetime value
        - Risk assessment (high-risk customers)
        - Loyalty indicators
        - Follow-up priorities
        - Target achievement analysis
        
        Provide actionable CRM insights in JSON format.
        Identify customers needing immediate attention."""
    
    def _get_profit_analyst_prompt(self) -> str:
        return """You are a profitability and margin analyst.
        
        Analyze profit margins focusing on:
        - Items sold below cost (critical issue)
        - Margin analysis by product
        - Pricing optimization opportunities
        - Cost-benefit analysis
        - Profit leakage identification
        - High-margin vs low-margin products
        
        Provide profit improvement recommendations in JSON format.
        Flag any losses or below-cost sales immediately."""
    
    def _get_movement_analyst_prompt(self) -> str:
        return """You are an inventory movement and logistics analyst.
        
        Analyze inventory movement patterns:
        - Fast-moving vs slow-moving items
        - Stock turnover ratios
        - Days to sell calculation
        - Movement efficiency
        - Seasonal movement patterns
        - Overstocking and understocking issues
        
        Provide movement optimization insights in JSON format."""
    
    def _get_general_analyst_prompt(self) -> str:
        return """You are a comprehensive business analyst with expertise in inventory, sales, and finance.
        
        Analyze all available data to provide holistic business insights.
        Connect dots between inventory, sales, and customer behavior.
        Identify opportunities and risks across all areas.
        
        Respond in JSON with summary, key_insights, metrics, recommendations, and detailed_analysis."""
    
    def _apply_filters(self, data: List[Dict], filters: Dict) -> List[Dict]:
        """Apply filters to data"""
        if not filters or not data:
            return data
        
        filtered = data
        
        # Date range filter
        if 'start_date' in filters and 'end_date' in filters:
            filtered = [
                item for item in filtered
                if filters['start_date'] <= item.get('voucher_date', item.get('date', '9999-99-99')) <= filters['end_date']
            ]
        
        # Category filter
        if 'category' in filters:
            filtered = [item for item in filtered if item.get('category') == filters['category']]
        
        # Customer filter
        if 'customer' in filters:
            filtered = [item for item in filtered if filters['customer'].lower() in item.get('party_name', '').lower()]
        
        # Amount range filter
        if 'min_amount' in filters:
            filtered = [item for item in filtered if item.get('total_amount', item.get('price', 0)) >= filters['min_amount']]
        
        if 'max_amount' in filters:
            filtered = [item for item in filtered if item.get('total_amount', item.get('price', 0)) <= filters['max_amount']]
        
        return filtered
    
    def _build_context(self, query: str, report_type: str, filters: Dict,
                      inventory: List[Dict], sales: List[Dict], customers: List[Dict]) -> str:
        """Build comprehensive context for AI"""
        context = f"""USER QUERY: {query}
        
REPORT TYPE: {report_type}
        
FILTERS APPLIED: {json.dumps(filters, indent=2)}
        
INVENTORY DATA ({len(inventory)} items):
{json.dumps(inventory[:50], indent=2)}
        
SALES DATA ({len(sales)} transactions):
{json.dumps(sales[:50], indent=2)}
        
CUSTOMER DATA ({len(customers)} records):
{json.dumps(customers[:30], indent=2)}
        
Analyze this data comprehensively and provide actionable insights.
        """
        return context
