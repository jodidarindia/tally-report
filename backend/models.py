from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

# Existing models (keeping all previous models)
class TallyConnection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connection_type: str
    host: Optional[str] = None
    port: Optional[int] = 9000
    api_key: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_synced: Optional[datetime] = None

class TallyConnectionCreate(BaseModel):
    connection_type: str
    host: Optional[str] = None
    port: Optional[int] = 9000
    api_key: Optional[str] = None

class InventoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_id: str
    item_name: str
    part_number: Optional[str] = None
    quantity: float
    unit: str
    price: Optional[float] = None
    purchase_price: Optional[float] = None
    standard_price: Optional[float] = None  # Tally STDPRICE — standard sale price master
    standard_price_source: Optional[str] = None  # 'tally_master' | 'unset' | 'unset_cleaned_v982'
    abc_category: Optional[str] = None       # User-assigned A/B/C/D classification (Inventory page)
    category: Optional[str] = None
    stock_group: Optional[str] = None
    reorder_level: Optional[float] = None
    # Stock value fields (for Balance Sheet & P&L)
    opening_quantity: Optional[float] = None
    opening_rate: Optional[float] = None
    opening_value: Optional[float] = None
    closing_value: Optional[float] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SalesVoucher(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    voucher_id: str
    voucher_date: str
    party_name: str
    total_amount: float
    items: Optional[List[Dict[str, Any]]] = []
    reference_number: Optional[str] = None
    salesman: Optional[str] = None
    voucher_type: Optional[str] = None
    ledger_entries: Optional[List[Dict[str, Any]]] = []
    dispatch_through: Optional[str] = None
    destination: Optional[str] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CustomerOutstanding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    outstanding_amount: float
    credit_limit: Optional[float] = None
    overdue_amount: float = 0.0
    last_payment_date: Optional[str] = None
    payment_terms: Optional[str] = None
    aging_30_days: float = 0.0
    aging_60_days: float = 0.0
    aging_90_days: float = 0.0
    aging_90_plus: float = 0.0

class CustomerFollowup(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    followup_date: datetime
    followup_type: str
    status: str
    notes: Optional[str] = None
    next_followup: Optional[datetime] = None
    created_by: Optional[str] = None
    created_by_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CustomerFollowupCreate(BaseModel):
    customer_name: str
    followup_date: str
    followup_type: str
    notes: Optional[str] = None

class CustomerTarget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    target_amount: float
    achieved_amount: float
    period: str
    start_date: str
    end_date: str

class SalesmanPerformance(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    salesman_name: str
    target_amount: float
    achieved_amount: float
    achievement_percentage: float
    total_customers: int
    period: str

class AIQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str
    response: Optional[str] = None
    report_data: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIQueryRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    report_type: Optional[str] = None

class InventoryMovement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_name: str
    opening_stock: float
    purchases: float
    sales: float
    closing_stock: float
    movement_rate: float
    days_to_sell: float

class BelowCostSale(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_name: str
    sale_price: float
    purchase_price: float
    loss_per_unit: float
    quantity_sold: float
    total_loss: float
    voucher_id: str
    sale_date: str

class ExportRequest(BaseModel):
    report_type: str
    format: str
    filters: Optional[Dict[str, Any]] = None

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None

# New Authentication Models
class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_token: str = ""

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: str
    role: str = "employee"

class ResetPasswordRequest(BaseModel):
    username: str
    new_password: str

# New Purchase Order Models
class PurchaseOrderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_name: str = ""
    current_stock: float = 0
    reorder_level: float = 0
    recommended_quantity: float = 0
    priority: str = "medium"
    reason: str = ""
    estimated_cost: float = 0

class PurchaseOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    po_number: str
    items: List[PurchaseOrderItem] = []
    total_items: int = 0
    total_cost: float = 0
    ai_analysis: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "draft"
