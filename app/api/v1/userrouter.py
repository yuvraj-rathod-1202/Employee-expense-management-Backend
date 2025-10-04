from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from typing import Optional

from app.database.databse import SessionLocal
from app.database.services.user_service import UserService
from app.ReqResModels.usermodels import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    UserQueryParams,
    CreateUserResponse,
    UpdateUserResponse,
    UserResponse,
    UserDetailResponse,
    UserListResponse,
    UserStatsResponse,
    UserManagersListResponse,
    UserErrorResponse,
    UserRole,
)
from app.logic.exceptions import (
    UserNotFoundError,
    UserAlreadyExistsError,
    CompanyNotFoundError,
    ValidationError,
    DatabaseError
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={
        404: {"model": UserErrorResponse, "description": "User not found"},
        400: {"model": UserErrorResponse, "description": "Bad request"},
        500: {"model": UserErrorResponse, "description": "Internal server error"}
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
    response_model=CreateUserResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user with the provided information"
)
def create_user(
    request: CreateUserRequest,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    try:
        return UserService.create_user(db, request)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except CompanyNotFoundError as e:
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

@router.get(
    "/managers",
    response_model=UserManagersListResponse,
    summary="Get all managers",
    description="Retrieve all users who are managers (have manager role or have subordinates)"
)
def get_managers(
    company_id: Optional[int] = Query(None, description="Filter by company ID"),
    db: Session = Depends(get_db)
):
    """Get all managers"""
    try:
        return UserService.get_all_managers(db, company_id)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.get(
    "/stats/overview",
    response_model=UserStatsResponse,
    summary="Get user statistics",
    description="Get overview statistics for all users"
)
def get_user_stats(
    db: Session = Depends(get_db)
):
    """Get user statistics"""
    try:
        return UserService.get_user_stats(db)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get user by ID",
    description="Retrieve a specific user by their ID with detailed information"
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user by ID"""
    try:
        return UserService.get_user_by_id(db, user_id)
    except UserNotFoundError as e:
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
    "/",
    response_model=UserListResponse,
    summary="Get users",
    description="Retrieve a paginated list of users with optional filtering and sorting"
)
def get_users(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    company_id: Optional[int] = Query(None, description="Filter by company"),
    role_filter: Optional[str] = Query(None, alias="role", description="Filter by role"),
    manager_id: Optional[int] = Query(None, description="Filter by manager"),
    sort_by: str = Query("created_at", description="Sort field"),
    db: Session = Depends(get_db)
):
    """Get paginated list of users"""
    try:
        # Convert string role to enum if provided
        role_enum = None
        if role_filter:
            try:
                role_enum = UserRole(role_filter)
            except ValueError:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role value: {role_filter}"
                )
        
        
        params = UserQueryParams(
            page=page,
            limit=limit,
            search=search,
            company_id=company_id,
            role=role_enum,
            manager_id=manager_id,
            sort_by=sort_by,
        )
        return UserService.get_users(db, params)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

@router.put(
    "/{user_id}",
    response_model=UpdateUserResponse,
    summary="Update user",
    description="Update user information"
)
def update_user(
    user_id: int,
    request: UpdateUserRequest,
    db: Session = Depends(get_db)
):
    """Update user information"""
    try:
        return UserService.update_user(db, user_id, request)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
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
    "/{user_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete a user (soft delete)"
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Delete user (soft delete)"""
    try:
        UserService.delete_user(db, user_id)
        return {"message": "User deleted successfully"}
    except UserNotFoundError as e:
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
    "/{user_id}/change-password",
    status_code=http_status.HTTP_200_OK,
    summary="Change user password",
    description="Change user password with current password verification"
)
def change_password(
    user_id: int,
    request: ChangePasswordRequest,
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        UserService.change_password(db, user_id, request)
        return {"message": "Password changed successfully"}
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

@router.get(
    "/company/{company_id}",
    response_model=UserListResponse,
    summary="Get users by company",
    description="Retrieve users filtered by company ID"
)
def get_users_by_company(
    company_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    role_filter: Optional[str] = Query(None, alias="role", description="Filter by role"),
    sort_by: str = Query("created_at", description="Sort field"),
    db: Session = Depends(get_db)
):
    """Get users by company"""
    try:
        # Convert string role to enum if provided
        role_enum = None
        if role_filter:
            try:
                role_enum = UserRole(role_filter)
            except ValueError:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role value: {role_filter}"
                )
                
        
        params = UserQueryParams(
            page=page,
            limit=limit,
            search=search,
            company_id=company_id,
            role=role_enum,
            manager_id=None,
            sort_by=sort_by,
        )
        return UserService.get_users_by_company(db, company_id, params)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )

