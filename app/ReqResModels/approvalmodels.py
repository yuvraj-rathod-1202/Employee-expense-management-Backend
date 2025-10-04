from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from typing import Optional, List, Union
from enum import Enum

class ApprovalSequence(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"

# Request Models
class CreateApproverRequest(BaseModel):
    approver_id: int = Field(..., description="Approver user ID")
    required: bool = Field(default=True, description="Whether this approver is required")
    sequence_order: int = Field(..., description="Order in approval sequence")
    
    @field_validator('approver_id', 'sequence_order', mode='before')
    @classmethod
    def parse_int_fields(cls, v):
        if isinstance(v, str):
            return int(v)
        return v

class CreateApprovalRuleRequest(BaseModel):
    user_id: int = Field(..., description="Employee ID for whom this rule applies")
    description: str = Field(..., min_length=1, max_length=1000, description="Rule description")
    manager_id: Optional[int] = Field(None, description="Override default manager")
    is_manager_approver: bool = Field(default=False, description="Whether manager is an approver")
    approver_sequence: Union[ApprovalSequence, str] = Field(default=ApprovalSequence.SEQUENTIAL, description="Sequential or parallel approval")
    min_approval_percentage: Optional[float] = Field(None, ge=0, le=100, description="Minimum approval percentage required")
    approvers: List[CreateApproverRequest]
    
    @field_validator('user_id', 'manager_id', mode='before')
    @classmethod
    def parse_int_fields(cls, v):
        if v is not None and isinstance(v, str):
            return int(v)
        return v
    
    @field_validator('approver_sequence', mode='before')
    @classmethod
    def parse_approver_sequence(cls, v):
        if isinstance(v, str):
            if v.lower() == "sequential":
                return ApprovalSequence.SEQUENTIAL
            elif v.lower() == "parallel":
                return ApprovalSequence.PARALLEL
        return v

class UpdateApprovalRuleRequest(BaseModel):
    description: Optional[str] = Field(None, min_length=1, max_length=1000)
    manager_id: Optional[int] = Field(None, description="Override default manager")
    approvers: Optional[List[CreateApproverRequest]] = None
    
    

class ApproveExpenseRequest(BaseModel):
    """Request model for approving an expense"""
    approver_id: int = Field(..., description="ID of the approver")
    comments: Optional[str] = Field(None, max_length=500, description="Optional approval comments")
    
    @field_validator('approver_id', mode='before')
    @classmethod
    def parse_approver_id(cls, v):
        if isinstance(v, str):
            return int(v)
        return v

class RejectExpenseRequest(BaseModel):
    """Request model for rejecting an expense"""
    approver_id: int = Field(..., description="ID of the approver")
    comments: str = Field(..., min_length=1, max_length=500, description="Required rejection comments")
    
    @field_validator('approver_id', mode='before')
    @classmethod
    def parse_approver_id(cls, v):
        if isinstance(v, str):
            return int(v)
        return v
    manager_id: Optional[int] = Field(None, gt=0)
    is_manager_approver: Optional[bool] = None
    approver_sequence: Optional[ApprovalSequence] = None
    min_approval_percentage: Optional[float] = Field(None, ge=0, le=100)
    approvers: Optional[List[CreateApproverRequest]] = None

class ApprovalRuleQueryParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")
    user_id: Optional[int] = Field(None, gt=0, description="Filter by user")
    manager_id: Optional[int] = Field(None, gt=0, description="Filter by manager")
    search: Optional[str] = Field(None, max_length=255, description="Search in description")

# Response Models
class ApproverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    approver_id: int
    approver_name: str
    approver_email: str
    required: bool
    sequence_order: int

class ApprovalRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    user_name: str
    user_email: str
    description: str
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    is_manager_approver: bool
    approver_sequence: str
    min_approval_percentage: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    approvers: List[ApproverResponse]

class CreateApprovalRuleResponse(ApprovalRuleResponse):
    pass

class UpdateApprovalRuleResponse(ApprovalRuleResponse):
    pass

class ApprovalRuleDetailResponse(ApprovalRuleResponse):
    pass

class ApprovalRuleListResponse(BaseModel):
    rules: List[ApprovalRuleResponse]
    total: int
    page: int
    limit: int
    total_pages: int

class ApprovalRuleStatsResponse(BaseModel):
    total_rules: int
    rules_by_sequence: dict
    rules_with_manager_approver: int
    average_approvers_per_rule: float

# Error Response Models
class ApprovalRuleErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None

# Expense Approval Models
class ExpenseApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"

class ExpenseApprovalRequest(BaseModel):
    expense_id: int = Field(..., gt=0, description="Expense ID to approve")
    approver_id: int = Field(..., gt=0, description="Approver user ID")
    status: ExpenseApprovalStatus = Field(..., description="Approval status")
    comments: Optional[str] = Field(None, max_length=1000, description="Approval comments")

class ExpenseApprovalResponse(BaseModel):
    id: int
    expense_id: int
    approver_id: int
    approver_name: str
    status: str
    sequence_order: int
    is_manager_approval: bool
    comments: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime

class ExpenseApprovalStatusResponse(BaseModel):
    expense_id: int
    current_status: str
    is_fully_approved: bool
    approval_percentage: float
    required_percentage: float
    next_approver: Optional[str] = None
    pending_approvals: List[ExpenseApprovalResponse]
    completed_approvals: List[ExpenseApprovalResponse]
    manager_approval_required: bool
    manager_approved: bool
    sequential_approval: bool
    can_proceed_to_next_step: bool

class BulkApprovalStatusResponse(BaseModel):
    expenses: List[ExpenseApprovalStatusResponse]
    summary: dict

# Pending Request Models
class PendingExpenseRequest(BaseModel):
    """Expense request pending approval from user's perspective"""
    model_config = ConfigDict(from_attributes=True)
    
    expense_id: int
    amount: float
    currency_code: str
    category: str
    description: Optional[str]
    expense_date: datetime
    submitted_date: datetime
    current_status: str
    approval_percentage: float
    required_percentage: float
    next_approver: Optional[str] = None
    pending_approvals_count: int
    total_approvals_count: int

class PendingReviewRequest(BaseModel):
    """Request pending review from approver's perspective"""
    model_config = ConfigDict(from_attributes=True)
    
    expense_id: int
    submitted_by_id: int
    submitted_by_name: str
    submitted_by_email: str
    amount: float
    currency_code: str
    category: str
    description: Optional[str]
    expense_date: datetime
    submitted_date: datetime
    my_approval_step: int
    is_manager_approval: bool
    can_approve_now: bool  # Based on sequential requirements
    approval_deadline: Optional[datetime] = None

class UserPendingRequestsResponse(BaseModel):
    """Response for user's pending expense requests"""
    pending_requests: List[PendingExpenseRequest]
    total_count: int
    pending_amount: float

class ManagerPendingRequestsResponse(BaseModel):
    """Response for manager/admin's pending reviews"""
    pending_reviews: List[PendingReviewRequest]
    total_count: int
    total_amount: float
    urgent_count: int  # Requests waiting more than X days