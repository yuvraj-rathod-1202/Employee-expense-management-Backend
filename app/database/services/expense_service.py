from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal

from app.database.models.expense import Expense, ExpenseReceipt
from app.database.models.users import User
from app.ReqResModels.expensemodels import (
    ExpenseSubmitRequest,
    ExpenseResponse,
    ExpenseDetailResponse,
    ExpenseListResponse,
    ExpenseSubmitResponse,
    ExpenseStatsResponse,
    ExpenseQueryParams,
    ExpenseReceiptResponse
)

class ExpenseService:
    """Service class for handling expense-related operations"""
    
    @staticmethod
    def create_expense(db: Session, request: ExpenseSubmitRequest) -> ExpenseSubmitResponse:
        """Create a new expense"""
        # Verify users exist
        submitted_by_user = db.query(User).filter(User.id == request.submitted_by).first()
        if not submitted_by_user:
            raise ValueError(f"Submitted by user with ID {request.submitted_by} not found")
        
        paid_by_user = db.query(User).filter(User.id == request.paid_by).first()
        if not paid_by_user:
            raise ValueError(f"Paid by user with ID {request.paid_by} not found")
        
        # Create expense
        expense = Expense(
            submitted_by=request.submitted_by,
            paid_by=request.paid_by,
            company_id=request.company_id,
            amount=request.amount,
            currency_code=request.currency_code,
            category=request.category,
            description=request.description,
            remarks=request.remarks,
            expense_date=request.expense_date,
            status="pending",
            created_at=datetime.utcnow()
        )
        
        db.add(expense)
        db.commit()
        db.refresh(expense)
        
        # Create initial receipt
        receipt = ExpenseReceipt(
            expense_id=expense.id,
            status="pending",
            created_at=datetime.utcnow()
        )
        db.add(receipt)
        db.commit()
        
        return ExpenseSubmitResponse(
            id=getattr(expense, 'id', 0),
            message="Expense submitted successfully",
            status="pending",
            created_at=getattr(expense, 'created_at', datetime.utcnow())
        )
    
    @staticmethod
    def get_expense_by_id(db: Session, expense_id: int, include_approvals: bool = False) -> Optional[ExpenseResponse]:
        """Get expense by ID with optional approval details"""
        query = db.query(Expense).options(
            joinedload(Expense.submitted_by_user),
            joinedload(Expense.paid_by_user),
            joinedload(Expense.receipts)
        )
        
        if include_approvals:
            query = query.options(joinedload(Expense.approvals))
        
        expense = query.filter(Expense.id == expense_id).first()
        
        if not expense:
            return None
        
        return ExpenseService._build_expense_response(expense, include_approvals)
    
    @staticmethod
    def get_expenses(db: Session, params: ExpenseQueryParams) -> ExpenseListResponse:
        """Get expenses with filtering and pagination"""
        query = db.query(Expense).options(
            joinedload(Expense.submitted_by_user),
            joinedload(Expense.paid_by_user),
            joinedload(Expense.receipts)
        )
        
        # Apply filters
        if params.submitted_by:
            query = query.filter(Expense.submitted_by == params.submitted_by)
        
        if params.paid_by:
            query = query.filter(Expense.paid_by == params.paid_by)
        
        if params.company_id:
            query = query.filter(Expense.company_id == params.company_id)
        
        if params.status:
            query = query.filter(Expense.status == params.status)
        
        if params.category:
            query = query.filter(Expense.category.ilike(f"%{params.category}%"))
        
        if params.date_from:
            query = query.filter(Expense.expense_date >= params.date_from)
        
        if params.date_to:
            query = query.filter(Expense.expense_date <= params.date_to)
        
        if params.amount_min:
            query = query.filter(Expense.amount >= params.amount_min)
        
        if params.amount_max:
            query = query.filter(Expense.amount <= params.amount_max)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        offset = (params.page - 1) * params.page_size
        expenses = query.offset(offset).limit(params.page_size).all()
        
        # Calculate pagination info
        total_pages = (total_count + params.page_size - 1) // params.page_size
        
        expense_responses = [
            ExpenseService._build_expense_response(expense, False) 
            for expense in expenses
        ]
        
        return ExpenseListResponse(
            expenses=expense_responses,
            total_count=total_count,
            page=params.page,
            page_size=params.page_size,
            total_pages=total_pages
        )
    
    @staticmethod
    def delete_expense(db: Session, expense_id: int) -> bool:
        """Delete an expense"""
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        
        if not expense:
            return False
        
        db.delete(expense)
        db.commit()
        return True
    
    @staticmethod
    def get_expense_stats(db: Session, user_id: Optional[int] = None, company_id: Optional[int] = None) -> ExpenseStatsResponse:
        """Get expense statistics"""
        query = db.query(Expense)
        
        if user_id:
            query = query.filter(or_(Expense.submitted_by == user_id, Expense.paid_by == user_id))
        
        if company_id:
            query = query.filter(Expense.company_id == company_id)
        
        # Count by status
        total_expenses = query.count()
        pending_expenses = query.filter(Expense.status == "pending").count()
        approved_expenses = query.filter(Expense.status == "approved").count()
        rejected_expenses = query.filter(Expense.status == "rejected").count()
        
        # Sum amounts by status
        total_amount = query.with_entities(func.sum(Expense.amount)).scalar() or Decimal('0')
        pending_amount = query.filter(Expense.status == "pending").with_entities(func.sum(Expense.amount)).scalar() or Decimal('0')
        approved_amount = query.filter(Expense.status == "approved").with_entities(func.sum(Expense.amount)).scalar() or Decimal('0')
        
        return ExpenseStatsResponse(
            total_expenses=total_expenses,
            pending_expenses=pending_expenses,
            approved_expenses=approved_expenses,
            rejected_expenses=rejected_expenses,
            total_amount=total_amount,
            pending_amount=pending_amount,
            approved_amount=approved_amount
        )
    
    @staticmethod
    def get_user_expenses(db: Session, user_id: int, params: ExpenseQueryParams) -> ExpenseListResponse:
        """Get expenses for a specific user (submitted by or paid by)"""
        # Modify params to include user filter
        params.submitted_by = user_id
        return ExpenseService.get_expenses(db, params)
    
    @staticmethod
    def _build_expense_response(expense: Expense, include_approvals: bool = False) -> ExpenseResponse:
        """Build expense response from database model"""
        # Get user names
        submitted_by_name = getattr(expense.submitted_by_user, 'name', None) if hasattr(expense, 'submitted_by_user') and expense.submitted_by_user else None
        paid_by_name = getattr(expense.paid_by_user, 'name', None) if hasattr(expense, 'paid_by_user') and expense.paid_by_user else None
        
        # Build receipt responses
        receipts = []
        if hasattr(expense, 'receipts') and expense.receipts:
            receipts = [
                ExpenseReceiptResponse(
                    id=getattr(receipt, 'id', 0),
                    expense_id=getattr(receipt, 'expense_id', 0),
                    status=getattr(receipt, 'status', 'pending'),
                    created_at=getattr(receipt, 'created_at', datetime.utcnow())
                )
                for receipt in expense.receipts
            ]
        
        base_response = ExpenseResponse(
            id=getattr(expense, 'id', 0),
            submitted_by=getattr(expense, 'submitted_by', 0),
            paid_by=getattr(expense, 'paid_by', 0),
            company_id=getattr(expense, 'company_id', 0),
            amount=getattr(expense, 'amount', Decimal('0')),
            currency_code=getattr(expense, 'currency_code', 'INR'),
            category=getattr(expense, 'category', ''),
            description=getattr(expense, 'description', None),
            remarks=getattr(expense, 'remarks', None),
            expense_date=getattr(expense, 'expense_date', date.today()),
            status=getattr(expense, 'status', 'pending'),
            created_at=getattr(expense, 'created_at', datetime.utcnow()),
            updated_at=getattr(expense, 'updated_at', None),
            submitted_by_name=submitted_by_name,
            paid_by_name=paid_by_name,
            receipts=receipts
        )
        
        if include_approvals and hasattr(expense, 'approvals'):
            # This would include approval details if needed
            return ExpenseDetailResponse(**base_response.dict(), approvals=[])
        
        return base_response