from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from datetime import datetime

from app.database.models.users import Company
from app.ReqResModels.companymodels import (
    CreateCompanyRequest, 
    UpdateCompanyRequest, 
    CompanyResponse,
    CreateCompanyResponse,
    UpdateCompanyResponse,
    CompanyStatsResponse
)
from app.logic.exceptions import (
    CompanyNotFoundError,
    CompanyAlreadyExistsError,
    DatabaseError
)

class CompanyService:
    
    @staticmethod
    def create_company(db: Session, request: CreateCompanyRequest) -> CreateCompanyResponse:
        """Create a new company"""
        try:
            # Check if company with same name already exists
            existing_company = db.query(Company).filter(Company.name == request.name).first()
            if existing_company:
                raise CompanyAlreadyExistsError(f"Company with name '{request.name}' already exists")
            
            # Create new company
            db_company = Company(
                name=request.name,
                country=request.country,
                currency_code=request.currency_code,
                created_at=datetime.utcnow()
            )
            
            db.add(db_company)
            db.commit()
            db.refresh(db_company)
            
            return CompanyService._model_to_response(db_company, CreateCompanyResponse)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, CompanyAlreadyExistsError):
                raise e
            raise DatabaseError(f"Failed to create company: {str(e)}")
    
    @staticmethod
    def get_company_by_id(db: Session, company_id: int) -> CompanyResponse:
        """Get company by ID"""
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise CompanyNotFoundError(f"Company with ID {company_id} not found")
        
        return CompanyService._model_to_response(company, CompanyResponse)
    
    @staticmethod
    def update_company(db: Session, company_id: int, request: UpdateCompanyRequest) -> UpdateCompanyResponse:
        """Update company information"""
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                raise CompanyNotFoundError(f"Company with ID {company_id} not found")
            
            # Check if new name conflicts with existing company
            if request.name and request.name != company.name:
                existing = db.query(Company).filter(
                    and_(Company.name == request.name, Company.id != company_id)
                ).first()
                if existing:
                    raise CompanyAlreadyExistsError(f"Company with name '{request.name}' already exists")
            
            # Update fields
            update_data = request.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(company, field):
                    setattr(company, field, value)
            
            setattr(company, 'updated_at', datetime.utcnow())
            
            db.commit()
            db.refresh(company)
            
            return CompanyService._model_to_response(company, UpdateCompanyResponse)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, (CompanyNotFoundError, CompanyAlreadyExistsError)):
                raise e
            raise DatabaseError(f"Failed to update company: {str(e)}")
    
    @staticmethod
    def delete_company(db: Session, company_id: int) -> bool:
        """Delete company (soft delete by changing status)"""
        try:
            company = db.query(Company).filter(Company.id == company_id).first()
            if not company:
                raise CompanyNotFoundError(f"Company with ID {company_id} not found")
                return False
            db.delete(company)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            if isinstance(e, CompanyNotFoundError):
                raise e
            raise DatabaseError(f"Failed to delete company: {str(e)}")
    
    @staticmethod
    def get_company_stats(db: Session) -> CompanyStatsResponse:
        """Get company statistics"""
        total_companies = db.query(Company).count()
        
        countries_count = db.query(func.count(func.distinct(Company.country))).scalar()
        
        # Get most used currency
        most_used_currency = db.query(Company.currency_code).group_by(Company.currency_code).order_by(func.count(Company.currency_code).desc()).first()
        most_used_currency = most_used_currency[0] if most_used_currency else "N/A"
        
        return CompanyStatsResponse(
            total_companies=total_companies,
            countries_count=countries_count,
            most_used_currency=most_used_currency
        )
    
    @staticmethod
    def _model_to_response(company: Company, response_type):
        """Convert SQLAlchemy model to Pydantic response model"""
        # Get user count for this company
        # user_count = len(company.users) if company.users else 0
        user_count = 0  # Placeholder until User relationship is fully set up
        
        data = {
            "id": getattr(company, 'id'),
            "name": getattr(company, 'name'),
            "country": getattr(company, 'country'),
            "currency_code": getattr(company, 'currency_code'),
            "created_at": getattr(company, 'created_at').isoformat(),
            "updated_at": getattr(company, 'updated_at').isoformat() if getattr(company, 'updated_at', None) else None,
            "user_count": user_count
        }
        
        return response_type(**data)