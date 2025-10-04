from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

# Request Models
class ExpenseSubmitRequest(BaseModel):
    submitted_by: int = Field(..., description="ID of the user submitting the expense")
    paid_by: int = Field(..., description="ID of the user who paid for the expense")
    company_id: int = Field(..., description="ID of the company")
    amount: Decimal = Field(..., gt=0, description="Amount of the expense")
    currency_code: str = Field(default="INR", max_length=10, description="Currency code")
    category: str = Field(..., max_length=100, description="Expense category")
    description: Optional[str] = Field(None, description="Expense description")
    remarks: Optional[str] = Field(None, description="Additional remarks")
    expense_date: date = Field(..., description="Date when the expense occurred")
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        return v
    
    @validator('expense_date')
    def validate_expense_date(cls, v):
        if v > date.today():
            raise ValueError('Expense date cannot be in the future')
        return v

# Response Models
class ExpenseReceiptResponse(BaseModel):
    id: int
    expense_id: int
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ExpenseResponse(BaseModel):
    id: int
    submitted_by: int
    paid_by: int
    company_id: int
    amount: Decimal
    currency_code: str
    category: str
    description: Optional[str]
    remarks: Optional[str]
    expense_date: date
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    # User information
    submitted_by_name: Optional[str] = None
    paid_by_name: Optional[str] = None
    
    # Related data
    receipts: List[ExpenseReceiptResponse] = []
    
    class Config:
        from_attributes = True

class ExpenseDetailResponse(ExpenseResponse):
    """Detailed expense response with approval information"""
    approvals: List["ExpenseApprovalResponse"] = []
    approval_status: Optional["ExpenseApprovalStatusResponse"] = None

class ExpenseListResponse(BaseModel):
    expenses: List[ExpenseResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int

class ExpenseSubmitResponse(BaseModel):
    id: int
    message: str
    status: str
    created_at: datetime

class ExpenseStatsResponse(BaseModel):
    total_expenses: int
    pending_expenses: int
    approved_expenses: int
    rejected_expenses: int
    total_amount: Decimal
    pending_amount: Decimal
    approved_amount: Decimal

class ExpenseQueryParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=10, ge=1, le=100, description="Number of items per page")
    submitted_by: Optional[int] = Field(None, description="Filter by submitter user ID")
    paid_by: Optional[int] = Field(None, description="Filter by payer user ID")
    company_id: Optional[int] = Field(None, description="Filter by company ID")
    status: Optional[str] = Field(None, description="Filter by expense status")
    category: Optional[str] = Field(None, description="Filter by expense category")
    date_from: Optional[date] = Field(None, description="Filter expenses from this date")
    date_to: Optional[date] = Field(None, description="Filter expenses to this date")
    amount_min: Optional[Decimal] = Field(None, ge=0, description="Minimum amount filter")
    amount_max: Optional[Decimal] = Field(None, ge=0, description="Maximum amount filter")

# Error Response
class ExpenseErrorResponse(BaseModel):
    error: str
    detail: str
    expense_id: Optional[int] = None

# Import the approval models to avoid circular imports
from app.ReqResModels.approvalmodels import ExpenseApprovalResponse, ExpenseApprovalStatusResponse

# Update forward references
ExpenseDetailResponse.model_rebuild()