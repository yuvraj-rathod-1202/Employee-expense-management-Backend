from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List
from enum import Enum

class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

# Request Models
class CreateCompanyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Company name")
    country: str = Field(..., min_length=2, max_length=100, description="Country name")
    currency_code: str = Field(default="INR", min_length=3, max_length=3, description="Currency code (ISO 4217)")
    
class UpdateCompanyRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    country: Optional[str] = Field(None, min_length=2, max_length=100)
    currency_code: Optional[str] = Field(None, min_length=3, max_length=3)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[CompanyStatus] = None

class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    country: str
    currency_code: str
    created_at: str
    updated_at: Optional[str] = None
    user_count: Optional[int] = 0
    
class CreateCompanyResponse(CompanyResponse):
    pass

class UpdateCompanyResponse(CompanyResponse):
    pass

class CompanyListResponse(BaseModel):
    companies: List[CompanyResponse]
    total: int
    page: int
    limit: int
    total_pages: int

class CompanyStatsResponse(BaseModel):
    total_companies: int
    countries_count: int
    most_used_currency: str

# Error Response Models
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None
    