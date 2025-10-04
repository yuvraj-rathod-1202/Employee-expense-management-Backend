from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.database.databse import SessionLocal
from app.database.services.expense_approval_service import ExpenseApprovalService
from app.ReqResModels.approvalmodels import (
    ExpenseApprovalStatusResponse,
    ApprovalRuleErrorResponse,
    UserPendingRequestsResponse,
    ManagerPendingRequestsResponse
)
from app.logic.exceptions import (
    ValidationError,
)

router = APIRouter(
    prefix="/expense-approval",
    tags=["expense-approval"],
    responses={
        404: {"model": ApprovalRuleErrorResponse, "description": "Expense or approval rule not found"},
        400: {"model": ApprovalRuleErrorResponse, "description": "Bad request"},
        500: {"model": ApprovalRuleErrorResponse, "description": "Internal server error"}
    }
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/initiate/{expense_id}",
    response_model=ExpenseApprovalStatusResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Initiate expense approval process",
    description="Start the approval process for an expense based on the user's approval rules"
)
def initiate_expense_approval(
    expense_id: int,
    db: Session = Depends(get_db)
):
    """Initiate the approval process for an expense"""
    try:
        return ExpenseApprovalService.initiate_expense_approval(db, expense_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Expense not found or approval rule missing: {str(e)}"
        )

@router.get(
    "/status/{expense_id}",
    response_model=ExpenseApprovalStatusResponse,
    summary="Check expense approval status",
    description="Check the current approval status of an expense including progress and next steps"
)
def check_expense_approval_status(
    expense_id: int,
    db: Session = Depends(get_db)
):
    """Check the approval status of an expense"""
    try:
        return ExpenseApprovalService.check_expense_approval_status(db, expense_id)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Expense not found: {str(e)}"
        )

@router.get(
    "/history/{expense_id}",
    response_model=ExpenseApprovalStatusResponse,
    summary="Get expense approval history",
    description="Get the complete approval history for an expense"
)
def get_expense_approval_history(
    expense_id: int,
    db: Session = Depends(get_db)
):
    """Get the approval history for an expense"""
    try:
        return ExpenseApprovalService.check_expense_approval_status(db, expense_id)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Expense not found: {str(e)}"
        )

@router.get(
    "/pending/user/{user_id}",
    response_model=UserPendingRequestsResponse,
    summary="Get user's pending expense requests",
    description="Get all expenses submitted by a user that are still pending approval"
)
def get_user_pending_requests(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get all pending expense requests for a specific user"""
    try:
        return ExpenseApprovalService.get_user_pending_requests(db, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user pending requests: {str(e)}"
        )

@router.get(
    "/pending/manager/{manager_id}",
    response_model=ManagerPendingRequestsResponse,
    summary="Get manager's pending reviews",
    description="Get all expenses pending review by a specific manager/approver"
)
def get_manager_pending_reviews(
    manager_id: int,
    db: Session = Depends(get_db)
):
    """Get all expenses pending review by a specific manager"""
    try:
        return ExpenseApprovalService.get_manager_pending_reviews(db, manager_id)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving manager pending reviews: {str(e)}"
        )

@router.get(
    "/pending/admin",
    response_model=ManagerPendingRequestsResponse,
    summary="Get all pending reviews (admin view)",
    description="Get all expenses pending review across the system (admin view)"
)
def get_admin_pending_reviews(
    db: Session = Depends(get_db)
):
    """Get all expenses pending review across the system (admin view)"""
    try:
        return ExpenseApprovalService.get_admin_pending_reviews(db)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving admin pending reviews: {str(e)}"
        )