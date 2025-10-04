from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database.databse import SessionLocal
from app.database.services.expense_service import ExpenseService
from app.ReqResModels.expensemodels import (
    ExpenseSubmitRequest,
    ExpenseResponse,
    ExpenseListResponse,
    ExpenseSubmitResponse,
    ExpenseStatsResponse,
    ExpenseQueryParams,
    ExpenseErrorResponse
)

router = APIRouter(
    prefix="/expenses",
    tags=["expenses"],
    responses={
        404: {"model": ExpenseErrorResponse, "description": "Expense not found"},
        400: {"model": ExpenseErrorResponse, "description": "Bad request"},
        500: {"model": ExpenseErrorResponse, "description": "Internal server error"}
    }
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/submit",
    response_model=ExpenseSubmitResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Submit a new expense",
    description="Submit a new expense for approval"
)
def submit_expense(
    request: ExpenseSubmitRequest,
    db: Session = Depends(get_db)
):
    """Submit a new expense"""
    try:
        return ExpenseService.create_expense(db, request)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit expense: {str(e)}"
        )

@router.get(
    "/{expense_id}",
    response_model=ExpenseResponse,
    summary="Get expense by ID",
    description="Retrieve a specific expense by its ID"
)
def get_expense(
    expense_id: int,
    include_approvals: bool = Query(False, description="Include approval details"),
    db: Session = Depends(get_db)
):
    """Get expense by ID"""
    try:
        expense = ExpenseService.get_expense_by_id(db, expense_id, include_approvals)
        if not expense:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Expense with ID {expense_id} not found"
            )
        return expense
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving expense: {str(e)}"
        )

@router.get(
    "/",
    response_model=ExpenseListResponse,
    summary="Get expenses with filtering",
    description="Get a list of expenses with optional filtering and pagination"
)
def get_expenses(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    submitted_by: Optional[int] = Query(None, description="Filter by submitter user ID"),
    paid_by: Optional[int] = Query(None, description="Filter by payer user ID"),
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    status: Optional[str] = Query(None, description="Filter by expense status"),
    category: Optional[str] = Query(None, description="Filter by expense category"),
    date_from: Optional[str] = Query(None, description="Filter expenses from this date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter expenses to this date (YYYY-MM-DD)"),
    amount_min: Optional[float] = Query(None, ge=0, description="Minimum amount filter"),
    amount_max: Optional[float] = Query(None, ge=0, description="Maximum amount filter"),
    db: Session = Depends(get_db)
):
    """Get expenses with filtering and pagination"""
    try:
        # Convert string dates to date objects if provided
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
        
        if date_to:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
        
        from decimal import Decimal
        
        amount_min_decimal = Decimal(str(amount_min)) if amount_min is not None else None
        amount_max_decimal = Decimal(str(amount_max)) if amount_max is not None else None
        
        params = ExpenseQueryParams(
            page=page,
            page_size=page_size,
            submitted_by=submitted_by,
            paid_by=paid_by,
            company_id=company_id,
            status=status,
            category=category,
            date_from=date_from_obj,
            date_to=date_to_obj,
            amount_min=amount_min_decimal,
            amount_max=amount_max_decimal
        )
        
        return ExpenseService.get_expenses(db, params)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving expenses: {str(e)}"
        )

@router.get(
    "/stats/summary",
    response_model=ExpenseStatsResponse,
    summary="Get expense statistics",
    description="Get statistical summary of expenses"
)
def get_expense_stats(
    user_id: Optional[int] = Query(None, description="Filter stats by user ID"),
    company_id: Optional[int] = Query(None, description="Filter stats by company ID"),
    db: Session = Depends(get_db)
):
    """Get expense statistics"""
    try:
        return ExpenseService.get_expense_stats(db, user_id, company_id)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving expense statistics: {str(e)}"
        )

@router.get(
    "/user/{user_id}",
    response_model=ExpenseListResponse,
    summary="Get user expenses",
    description="Get all expenses for a specific user (submitted by or paid by)"
)
def get_user_expenses(
    user_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    status: Optional[str] = Query(None, description="Filter by expense status"),
    category: Optional[str] = Query(None, description="Filter by expense category"),
    db: Session = Depends(get_db)
):
    """Get expenses for a specific user"""
    try:
        params = ExpenseQueryParams(
            page=page,
            page_size=page_size,
            submitted_by=user_id,
            paid_by=None,
            company_id=None,
            status=status,
            category=category,
            date_from=None,
            date_to=None,
            amount_min=None,
            amount_max=None
        )
        
        return ExpenseService.get_user_expenses(db, user_id, params)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user expenses: {str(e)}"
        )