from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

class TallyConnection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connection_type: str  # 'rest' or 'xml'
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
    quantity: float
    unit: str
    price: Optional[float] = None
    category: Optional[str] = None
    reorder_level: Optional[float] = None
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
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query_text: str
    response: Optional[str] = None
    report_data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIQueryRequest(BaseModel):
    query: str

class ExportRequest(BaseModel):
    report_type: str  # 'inventory' or 'sales'
    format: str  # 'pdf', 'excel', or 'csv'
    filters: Optional[Dict[str, Any]] = None

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None
