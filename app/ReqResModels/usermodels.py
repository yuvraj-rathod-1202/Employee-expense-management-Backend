from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    HR = "hr"

# Request Models
class CreateUserRequest(BaseModel):
    company_id: int = Field(..., gt=0, description="Company ID")
    name: str = Field(..., min_length=1, max_length=255, description="User full name")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=5, max_length=100, description="User password")
    role: UserRole = Field(default=UserRole.EMPLOYEE, description="User role")
    manager_id: Optional[int] = Field(None, gt=0, description="Manager ID (optional)")
    
class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    manager_id: Optional[int] = Field(None, gt=0)
    
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=5, max_length=100, description="New password")
    
class UserQueryParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")
    search: Optional[str] = Field(None, max_length=255, description="Search term")
    company_id: Optional[int] = Field(None, gt=0, description="Filter by company")
    role: Optional[UserRole] = Field(None, description="Filter by role")
    manager_id: Optional[int] = Field(None, gt=0, description="Filter by manager")
    sort_by: Optional[str] = Field(default="created_at", description="Sort field")

# Response Models
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    company_id: int
    name: str
    email: str
    role: str
    manager_id: Optional[int] = None
    status: str = "active"
    created_at: str
    updated_at: Optional[str] = None
    
class CreateUserResponse(UserResponse):
    pass

class UpdateUserResponse(UserResponse):
    pass

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    limit: int
    total_pages: int

class UserStatsResponse(BaseModel):
    total_users: int
    users_by_role: dict
    users_by_company: dict

# Specific response models
class UserCompanyResponse(BaseModel):
    id: int
    name: str
    country: str
    currency_code: str
    
class UserManagerResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    company_id: int
    company_name: Optional[str] = None
    subordinates_count: int = 0

class UserManagersListResponse(BaseModel):
    managers: List[UserManagerResponse]
    total: int

class UserDetailResponse(UserResponse):
    company: Optional[UserCompanyResponse] = None
    manager: Optional[UserManagerResponse] = None

# Error Response Models
class UserErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None