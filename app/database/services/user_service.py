from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_
from datetime import datetime
import bcrypt

from app.database.models.users import User, Company
from app.database.migration import safe_getattr, safe_setattr, has_column
from app.ReqResModels.usermodels import (
    CreateUserRequest,
    UpdateUserRequest,
    ChangePasswordRequest,
    UserQueryParams,
    UserResponse,
    CreateUserResponse,
    UpdateUserResponse,
    UserListResponse,
    UserStatsResponse,
    UserDetailResponse,
    UserCompanyResponse,
    UserManagerResponse
)
from app.logic.exceptions import (
    UserNotFoundError,
    UserAlreadyExistsError,
    CompanyNotFoundError,
    ValidationError,
    DatabaseError
)

class UserService:
    
    @staticmethod
    def create_user(db: Session, request: CreateUserRequest) -> CreateUserResponse:
        """Create a new user"""
        try:
            # Check if user with same email already exists
            existing_user = db.query(User).filter(User.email == request.email).first()
            if existing_user:
                raise UserAlreadyExistsError(f"User with email '{request.email}' already exists")
            
            # Check if company exists
            company = db.query(Company).filter(Company.id == request.company_id).first()
            if not company:
                raise CompanyNotFoundError(f"Company with ID {request.company_id} not found")
            
            # Check if manager exists (if provided)
            if request.manager_id:
                manager = db.query(User).filter(
                    and_(User.id == request.manager_id, User.company_id == request.company_id)
                ).first()
                if not manager:
                    raise ValidationError(f"Manager with ID {request.manager_id} not found in the same company")
            
            # Hash password
            password_hash = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Create new user
            user_data = {
                "company_id": request.company_id,
                "name": request.name,
                "email": request.email,
                "password_hash": password_hash,
                "role": request.role.value,
                "manager_id": request.manager_id,
                "created_at": datetime.utcnow()
            }
            
            db_user = User(**user_data)
            
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
            return UserService._model_to_response(db_user, CreateUserResponse, db)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, (UserAlreadyExistsError, CompanyNotFoundError, ValidationError)):
                raise e
            raise DatabaseError(f"Failed to create user: {str(e)}")
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> UserDetailResponse:
        """Get user by ID with detailed information"""
        user = db.query(User).options(
            joinedload(User.company),
            joinedload(User.manager)
        ).filter(User.id == user_id).first()
        
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")
        
        return UserService._model_to_detailed_response(user, db)
    
    @staticmethod
    def get_users(db: Session, params: UserQueryParams) -> UserListResponse:
        """Get paginated list of users with filters"""
        query = db.query(User).options(joinedload(User.company), joinedload(User.manager))
        
        # Apply filters
        if params.search:
            search_term = f"%{params.search}%"
            query = query.filter(
                or_(
                    User.name.ilike(search_term),
                    User.email.ilike(search_term)
                )
            )
        
        if params.company_id:
            query = query.filter(User.company_id == params.company_id)
        
        if params.role:
            query = query.filter(User.role == params.role.value)
        
        if params.manager_id:
            query = query.filter(User.manager_id == params.manager_id)
        
        # Apply sorting with null check
        if params.sort_by and hasattr(User, params.sort_by):
            order_column = getattr(User, params.sort_by)    
            query = query.order_by(order_column.asc())
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (params.page - 1) * params.limit
        users = query.offset(offset).limit(params.limit).all()
        
        # Calculate total pages
        total_pages = (total + params.limit - 1) // params.limit
        
        user_responses = [UserService._model_to_response(user, UserResponse, db) for user in users]
        
        return UserListResponse(
            users=user_responses,
            total=total,
            page=params.page,
            limit=params.limit,
            total_pages=total_pages
        )
    
    @staticmethod
    def update_user(db: Session, user_id: int, request: UpdateUserRequest) -> UpdateUserResponse:
        """Update user information"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundError(f"User with ID {user_id} not found")
            
            # Check if new email conflicts with existing user
            if request.email and request.email != user.email:
                existing = db.query(User).filter(
                    and_(User.email == request.email, User.id != user_id)
                ).first()
                if existing:
                    raise UserAlreadyExistsError(f"User with email '{request.email}' already exists")
            
            # Check if manager exists in the same company (if provided)
            if request.manager_id:
                manager = db.query(User).filter(
                    and_(User.id == request.manager_id, User.company_id == user.company_id)
                ).first()
                if not manager:
                    raise ValidationError(f"Manager with ID {request.manager_id} not found in the same company")
            
            # Update fields
            update_data = request.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(user, field):
                    if field == 'role' and hasattr(value, 'value'):
                        safe_setattr(user, field, value.value)
                    elif field == 'status' and hasattr(value, 'value'):
                        safe_setattr(user, field, value.value)
                    else:
                        safe_setattr(user, field, value)
            
            # Update timestamp if column exists
            if has_column('users', 'updated_at'):
                safe_setattr(user, 'updated_at', datetime.utcnow())
            
            db.commit()
            db.refresh(user)
            
            return UserService._model_to_response(user, UpdateUserResponse, db)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, (UserNotFoundError, UserAlreadyExistsError, ValidationError)):
                raise e
            raise DatabaseError(f"Failed to update user: {str(e)}")
    
    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        """Delete user (soft delete by changing status)"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundError(f"User with ID {user_id} not found")
            
            # Soft delete by setting status to inactive
            if has_column('users', 'status'):
                safe_setattr(user, 'status', "inactive")
            if has_column('users', 'updated_at'):
                safe_setattr(user, 'updated_at', datetime.utcnow())
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            if isinstance(e, UserNotFoundError):
                raise e
            raise DatabaseError(f"Failed to delete user: {str(e)}")
    
    @staticmethod
    def change_password(db: Session, user_id: int, request: ChangePasswordRequest) -> bool:
        """Change user password"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundError(f"User with ID {user_id} not found")
            
            # Verify current password
            if not bcrypt.checkpw(request.current_password.encode('utf-8'), user.password_hash.encode('utf-8')):
                raise ValidationError("Current password is incorrect")
            
            # Hash new password
            new_password_hash = bcrypt.hashpw(request.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            setattr(user, 'password_hash', new_password_hash)
            setattr(user, 'updated_at', datetime.utcnow())
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise DatabaseError(f"Failed to change password: {str(e)}")
    
    @staticmethod
    def get_users_by_company(db: Session, company_id: int, params: UserQueryParams) -> UserListResponse:
        """Get users filtered by company"""
        # Set company_id in params
        params.company_id = company_id
        return UserService.get_users(db, params)
    
    @staticmethod
    def get_user_stats(db: Session) -> UserStatsResponse:
        """Get user statistics"""
        total_users = db.query(User).count()
        
        # Users by role
        role_stats = db.query(User.role, func.count(User.id)).group_by(User.role).all()
        users_by_role = {role: count for role, count in role_stats}
        
        # Users by company
        company_stats = db.query(Company.name, func.count(User.id)).join(User).group_by(Company.name).all()
        users_by_company = {company: count for company, count in company_stats}
        
        return UserStatsResponse(
            total_users=total_users,
            users_by_role=users_by_role,
            users_by_company=users_by_company
        )
    
    @staticmethod
    def _model_to_response(user: User, response_type, db: Session):
        """Convert SQLAlchemy model to Pydantic response model"""
        
        data = {
            "id": safe_getattr(user, 'id'),
            "company_id": safe_getattr(user, 'company_id'),
            "name": safe_getattr(user, 'name'),
            "email": safe_getattr(user, 'email'),
            "role": safe_getattr(user, 'role'),
            "manager_id": safe_getattr(user, 'manager_id', None),
            "status": safe_getattr(user, 'status', 'active'),
            "created_at": (lambda x: x.isoformat() if x is not None else datetime.utcnow().isoformat())(safe_getattr(user, 'created_at')),
            "updated_at": (lambda x: x.isoformat() if x is not None else None)(safe_getattr(user, 'updated_at')),
            "company_name": safe_getattr(user.company, 'name', None) if hasattr(user, 'company') and user.company else None,
            "manager_name": safe_getattr(user.manager, 'name', None) if hasattr(user, 'manager') and user.manager else None,
        }
        
        return response_type(**data)
    
    @staticmethod
    def _model_to_detailed_response(user: User, db: Session) -> UserDetailResponse:
        """Convert SQLAlchemy model to detailed response model"""

        
        # Prepare company data
        company_data = None
        if hasattr(user, 'company') and user.company:
            company_data = UserCompanyResponse(
                id=getattr(user.company, 'id'),
                name=getattr(user.company, 'name'),
                country=getattr(user.company, 'country'),
                currency_code=getattr(user.company, 'currency_code')
            )
        
        # Prepare manager data
        manager_data = None
        if hasattr(user, 'manager') and user.manager:
            manager_data = UserManagerResponse(
                id=getattr(user.manager, 'id'),
                name=getattr(user.manager, 'name'),
                email=getattr(user.manager, 'email'),
                role=getattr(user.manager, 'role')
            )
        
        # Create base response
        base_data = UserService._model_to_response(user, UserResponse, db)
        
        return UserDetailResponse(
            **base_data.model_dump(),
            company=company_data,
            manager=manager_data,
        )