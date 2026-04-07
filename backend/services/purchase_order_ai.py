import os
from dotenv import load_dotenv
import logging
import json
from typing import Dict, Any, List
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
load_dotenv()

class PurchaseOrderAI:
    """
    AI service for generating intelligent purchase orders
    """
    
    def __init__(self):
        self.api_key = os.getenv("EMERGENT_LLM_KEY")
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found")
    
    async def generate_purchase_order(self, inventory_data: List[Dict], sales_data: List[Dict]) -> Dict[str, Any]:
        """
        Generate intelligent purchase order recommendations using AI
        """
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id="purchase_order_generation",
                system_message="""You are an expert inventory manager and procurement specialist.
                
                Analyze inventory levels, sales velocity, and reorder points to generate intelligent purchase orders.
                
                Consider:
                1. Items below reorder level (URGENT priority)
                2. Fast-moving items nearing stock-out (HIGH priority)
                3. Seasonal trends and sales patterns
                4. Optimal order quantities to balance cost and inventory
                5. Lead time considerations
                
                Respond in JSON format:
                {
                    "analysis": "Overall inventory health summary",
                    "urgent_items": [
                        {
                            "item_name": "Product Name",
                            "current_stock": 10,
                            "reorder_level": 50,
                            "recommended_quantity": 100,
                            "priority": "urgent",
                            "reason": "Stock below reorder level, high sales velocity",
                            "estimated_cost": 50000
                        }
                    ],
                    "recommendations": ["Overall procurement strategy", "Cost optimization tips"],
                    "total_estimated_cost": 150000
                }
                
                Be specific with numbers and actionable."""
            ).with_model("openai", "gpt-5.2")
            
            # Calculate sales velocity
            item_sales_velocity = {}
            for sale in sales_data:
                for item in sale.get('items', []):
                    item_name = item.get('item', '')
                    qty = item.get('quantity', 0)
                    item_sales_velocity[item_name] = item_sales_velocity.get(item_name, 0) + qty
            
            # Prepare context
            inventory_analysis = []
            for item in inventory_data:
                item_name = item['item_name']
                sales_velocity = item_sales_velocity.get(item_name, 0)
                inventory_analysis.append({
                    'item_name': item_name,
                    'current_stock': item['quantity'],
                    'reorder_level': item.get('reorder_level', 10),
                    'price': item.get('price', 0),
                    'sales_velocity': sales_velocity,
                    'category': item.get('category', 'General')
                })
            
            context = f"""
            INVENTORY DATA ({len(inventory_analysis)} items):
            {json.dumps(inventory_analysis, indent=2)}
            
            SALES VELOCITY SUMMARY:
            {json.dumps(item_sales_velocity, indent=2)}
            
            Generate purchase order recommendations focusing on items that need immediate attention.
            Prioritize based on stock levels and sales velocity.
            """
            
            user_message = UserMessage(text=context)
            response = await chat.send_message(user_message)
            
            try:
                clean_response = response.strip()
                if clean_response.startswith("```"):
                    clean_response = clean_response.split("\n", 1)[1] if "\n" in clean_response else clean_response[3:]
                    if clean_response.endswith("```"):
                        clean_response = clean_response[:-3].strip()
                po_data = json.loads(clean_response)
            except json.JSONDecodeError:
                po_data = {
                    "analysis": response[:500],
                    "urgent_items": [],
                    "recommendations": [response],
                    "total_estimated_cost": 0
                }
            
            return {
                "success": True,
                "purchase_order": po_data,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"Error generating purchase order: {e}")
            return {
                "success": False,
                "error": str(e)
            }
