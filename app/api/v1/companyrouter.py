from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session
from typing import Optional

from app.database.databse import SessionLocal
from app.database.services.company_service import CompanyService
from app.ReqResModels.companymodels import (
    CreateCompanyRequest,
    UpdateCompanyRequest,
    CreateCompanyResponse,
    UpdateCompanyResponse,
    CompanyResponse,
    CompanyStatsResponse,
    ErrorResponse,
)
from app.logic.exceptions import (
    CompanyNotFoundError,
    CompanyAlreadyExistsError,
    DatabaseError
)

router = APIRouter(
    prefix="/companies",
    tags=["companies"],
    responses={
        404: {"model": ErrorResponse, "description": "Company not found"},
        400: {"model": ErrorResponse, "description": "Bad request"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/",
    response_model=CreateCompanyResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Create a new company",
    description="Create a new company with the provided information"
)
def create_company(
    request: CreateCompanyRequest,
    db: Session = Depends(get_db)
):
    """Create a new company"""
    try:
        return CompanyService.create_company(db, request)
    except CompanyAlreadyExistsError as e:
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
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get company by ID",
    description="Retrieve a specific company by its ID"
)
def get_company(
    company_id: int,
    db: Session = Depends(get_db)
):
    """Get company by ID"""
    try:
        return CompanyService.get_company_by_id(db, company_id)
    except CompanyNotFoundError as e:
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
    "/{company_id}",
    response_model=UpdateCompanyResponse,
    summary="Update company",
    description="Update company information"
)
def update_company(
    company_id: int,
    request: UpdateCompanyRequest,
    db: Session = Depends(get_db)
):
    """Update company information"""
    try:
        return CompanyService.update_company(db, company_id, request)
    except CompanyNotFoundError as e:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=e.message
        )
    except CompanyAlreadyExistsError as e:
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
    "/{company_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Delete company",
    description="Delete a company (soft delete)"
)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db)
):
    """Delete company (soft delete)"""
    try:
        CompanyService.delete_company(db, company_id)
        return {"message": "Company deleted successfully"}
    except CompanyNotFoundError as e:
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
    response_model=CompanyStatsResponse,
    summary="Get company statistics",
    description="Get overview statistics for all companies"
)
def get_company_stats(
    db: Session = Depends(get_db)
):
    """Get company statistics"""
    try:
        return CompanyService.get_company_stats(db)
    except DatabaseError as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )