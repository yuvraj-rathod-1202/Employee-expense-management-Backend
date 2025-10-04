from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from typing import Optional

from app.database.databse import SessionLocal
from app.database.services.approval_service import ApprovalRuleService, ApprovalRuleNotFoundError
from app.ReqResModels.approvalmodels import (
    CreateApprovalRuleRequest,
    UpdateApprovalRuleRequest,
    ApprovalRuleQueryParams,
    CreateApprovalRuleResponse,
    UpdateApprovalRuleResponse,
    ApprovalRuleResponse,
    ApprovalRuleDetailResponse,
    ApprovalRuleListResponse,
    ApprovalRuleStatsResponse,
    ApprovalRuleErrorResponse
)
from app.logic.exceptions import (
    UserNotFoundError,
    ValidationError,
    DatabaseError
)

router = APIRouter(
    prefix="/approval-rules",
    tags=["approval-rules"],
    responses={
        404: {"model": ApprovalRuleErrorResponse, "description": "Approval rule not found"},
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
    "/",
    response_model=CreateApprovalRuleResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Create a new approval rule",
    description="Create a new approval rule for a user with specified approvers and settings"
)
def create_approval_rule(
    request: CreateApprovalRuleRequest,
    db: Session = Depends(get_db)
):
    """Create a new approval rule"""
    try:
        return ApprovalRuleService.create_approval_rule(db, request)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"User not found: {e.message}"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e.message}"
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e.message}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create approval rule: {str(e)}"
        )

@router.get(
    "/user/{user_id}",
    response_model=ApprovalRuleDetailResponse,
    summary="Get approval rule by user ID",
    description="Retrieve the approval rule for a specific user"
)
def get_approval_rule_by_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get approval rule for a user"""
    try:
        return ApprovalRuleService.get_approval_rule_by_user_id(db, user_id)
    except ApprovalRuleNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.get(
    "/stats/overview",
    response_model=ApprovalRuleStatsResponse,
    summary="Get approval rule statistics",
    description="Get overview statistics for all approval rules"
)
def get_approval_rule_stats(
    db: Session = Depends(get_db)
):
    """Get approval rule statistics"""
    try:
        return ApprovalRuleService.get_approval_rule_stats(db)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.get(
    "/",
    response_model=ApprovalRuleListResponse,
    summary="Get approval rules",
    description="Retrieve a paginated list of approval rules with optional filtering"
)
def get_approval_rules(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    manager_id: Optional[int] = Query(None, description="Filter by manager ID"),
    search: Optional[str] = Query(None, description="Search in description"),
    db: Session = Depends(get_db)
):
    """Get paginated list of approval rules"""
    try:
        params = ApprovalRuleQueryParams(
            page=page,
            limit=limit,
            user_id=user_id,
            manager_id=manager_id,
            search=search
        )
        return ApprovalRuleService.get_approval_rules(db, params)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.get(
    "/{rule_id}",
    response_model=ApprovalRuleDetailResponse,
    summary="Get approval rule by ID",
    description="Retrieve a specific approval rule by its ID"
)
def get_approval_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """Get approval rule by ID"""
    try:
        return ApprovalRuleService.get_approval_rule_by_id(db, rule_id)
    except ApprovalRuleNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.put(
    "/{rule_id}",
    response_model=UpdateApprovalRuleResponse,
    summary="Update approval rule",
    description="Update an existing approval rule"
)
def update_approval_rule(
    rule_id: int,
    request: UpdateApprovalRuleRequest,
    db: Session = Depends(get_db)
):
    """Update an approval rule"""
    try:
        return ApprovalRuleService.update_approval_rule(db, rule_id, request)
    except ApprovalRuleNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.delete(
    "/{rule_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Delete approval rule",
    description="Delete an approval rule"
)
def delete_approval_rule(
    rule_id: int,
    db: Session = Depends(get_db)
):
    """Delete an approval rule"""
    try:
        ApprovalRuleService.delete_approval_rule(db, rule_id)
        return {"message": "Approval rule deleted successfully"}
    except ApprovalRuleNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )