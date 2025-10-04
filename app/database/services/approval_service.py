from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_
from datetime import datetime

from app.database.models.approval import ApprovalRule, ApprovalStep
from app.database.models.users import User
from app.database.migration import safe_getattr, safe_setattr, has_column
from app.ReqResModels.approvalmodels import (
    CreateApprovalRuleRequest,
    UpdateApprovalRuleRequest,
    ApprovalRuleQueryParams,
    ApprovalRuleResponse,
    CreateApprovalRuleResponse,
    UpdateApprovalRuleResponse,
    ApprovalRuleDetailResponse,
    ApprovalRuleListResponse,
    ApprovalRuleStatsResponse,
    ApproverResponse
)
from app.logic.exceptions import (
    UserNotFoundError,
    ValidationError,
    DatabaseError
)

class ApprovalRuleNotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ApprovalRuleService:
    
    @staticmethod
    def create_approval_rule(db: Session, request: CreateApprovalRuleRequest) -> CreateApprovalRuleResponse:
        """Create a new approval rule"""
        try:
            # Check if user exists
            user = db.query(User).filter(User.id == request.user_id).first()
            if not user:
                raise UserNotFoundError(f"User with ID {request.user_id} not found")
            
            # Check if user already has an approval rule
            existing_rule = db.query(ApprovalRule).filter(ApprovalRule.user_id == request.user_id).first()
            if existing_rule:
                raise ValidationError(f"User with ID {request.user_id} already has an approval rule")
            
            # Check if manager exists (if provided)
            if request.manager_id:
                manager = db.query(User).filter(User.id == request.manager_id).first()
                if not manager:
                    raise UserNotFoundError(f"Manager with ID {request.manager_id} not found")
            
            # Validate approvers exist
            approver_ids = [approver.approver_id for approver in request.approvers]
            existing_approvers = db.query(User).filter(User.id.in_(approver_ids)).all()
            if len(existing_approvers) != len(approver_ids):
                missing_ids = set(approver_ids) - {u.id for u in existing_approvers} # type: ignore
                raise UserNotFoundError(f"Approvers with IDs {list(missing_ids)} not found")
            
            # Validate sequence orders are unique and start from 1
            sequence_orders = [approver.sequence_order for approver in request.approvers]
            if len(set(sequence_orders)) != len(sequence_orders):
                raise ValidationError("Duplicate sequence orders not allowed")
            if min(sequence_orders) != 1 or max(sequence_orders) != len(sequence_orders):
                raise ValidationError("Sequence orders must start from 1 and be consecutive")
            
            # Create approval rule
            rule_data = {
                "user_id": request.user_id,
                "description": request.description,
                "manager_id": request.manager_id,
                "is_manager_approver": request.is_manager_approver,
                "approver_sequence": 1 if request.approver_sequence == "sequential" else 0,
                "min_approval_percentage": request.min_approval_percentage or 100.0,
                "created_at": datetime.utcnow()
            }
            
            # Add updated_at if column exists
            if has_column('approval_rules', 'updated_at'):
                rule_data["updated_at"] = datetime.utcnow()
            
            db_rule = ApprovalRule(**rule_data)
            db.add(db_rule)
            db.flush()  # Get the ID
            
            # Create approval steps
            for approver_req in request.approvers:
                step = ApprovalStep(
                    rule_id=db_rule.id,
                    approver_id=approver_req.approver_id,
                    sequence_order=approver_req.sequence_order,
                    required=approver_req.required
                )
                db.add(step)
            
            db.commit()
            db.refresh(db_rule)
            
            return ApprovalRuleService._model_to_response(db_rule, CreateApprovalRuleResponse, db)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, (UserNotFoundError, ValidationError)):
                raise e
            raise DatabaseError(f"Failed to create approval rule: {str(e)}")
    
    @staticmethod
    def get_approval_rule_by_user_id(db: Session, user_id: int) -> ApprovalRuleDetailResponse:
        """Get approval rule for a specific user"""
        rule = db.query(ApprovalRule).options(
            joinedload(ApprovalRule.user),
            joinedload(ApprovalRule.manager),
            joinedload(ApprovalRule.steps).joinedload(ApprovalStep.approver)
        ).filter(ApprovalRule.user_id == user_id).first()
        
        if not rule:
            raise ApprovalRuleNotFoundError(f"No approval rule found for user ID {user_id}")
        
        return ApprovalRuleService._model_to_detailed_response(rule, db)
    
    @staticmethod
    def get_approval_rule_by_id(db: Session, rule_id: int) -> ApprovalRuleDetailResponse:
        """Get approval rule by ID"""
        rule = db.query(ApprovalRule).options(
            joinedload(ApprovalRule.user),
            joinedload(ApprovalRule.manager),
            joinedload(ApprovalRule.steps).joinedload(ApprovalStep.approver)
        ).filter(ApprovalRule.id == rule_id).first()
        
        if not rule:
            raise ApprovalRuleNotFoundError(f"Approval rule with ID {rule_id} not found")
        
        return ApprovalRuleService._model_to_detailed_response(rule, db)
    
    @staticmethod
    def get_approval_rules(db: Session, params: ApprovalRuleQueryParams) -> ApprovalRuleListResponse:
        """Get paginated list of approval rules with filters"""
        query = db.query(ApprovalRule).options(
            joinedload(ApprovalRule.user),
            joinedload(ApprovalRule.manager),
            joinedload(ApprovalRule.steps).joinedload(ApprovalStep.approver)
        )
        
        # Apply filters
        if params.user_id:
            query = query.filter(ApprovalRule.user_id == params.user_id)
        
        if params.manager_id:
            query = query.filter(ApprovalRule.manager_id == params.manager_id)
        
        if params.search:
            query = query.filter(ApprovalRule.description.ilike(f"%{params.search}%"))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        rules = query.offset((params.page - 1) * params.limit).limit(params.limit).all()
        
        # Convert to response format
        rule_responses = [ApprovalRuleService._model_to_response(rule, ApprovalRuleResponse, db) for rule in rules]
        
        return ApprovalRuleListResponse(
            rules=rule_responses,
            total=total,
            page=params.page,
            limit=params.limit,
            total_pages=(total + params.limit - 1) // params.limit
        )
    
    @staticmethod
    def update_approval_rule(db: Session, rule_id: int, request: UpdateApprovalRuleRequest) -> UpdateApprovalRuleResponse:
        """Update an existing approval rule"""
        try:
            rule = db.query(ApprovalRule).filter(ApprovalRule.id == rule_id).first()
            if not rule:
                raise ApprovalRuleNotFoundError(f"Approval rule with ID {rule_id} not found")
            
            # Check if manager exists (if provided)
            if request.manager_id:
                manager = db.query(User).filter(User.id == request.manager_id).first()
                if not manager:
                    raise UserNotFoundError(f"Manager with ID {request.manager_id} not found")
            
            # Update basic fields
            update_data = request.model_dump(exclude_unset=True, exclude={'approvers'})
            for field, value in update_data.items():
                if field == 'approver_sequence' and value is not None:
                    safe_setattr(rule, field, 1 if value.value == "sequential" else 0)
                elif hasattr(rule, field) and value is not None:
                    safe_setattr(rule, field, value)
            
            # Update timestamp if column exists
            if has_column('approval_rules', 'updated_at'):
                safe_setattr(rule, 'updated_at', datetime.utcnow())
            
            # Update approvers if provided
            if request.approvers is not None:
                # Validate approvers exist
                approver_ids = [approver.approver_id for approver in request.approvers]
                existing_approvers = db.query(User).filter(User.id.in_(approver_ids)).all()
                if len(existing_approvers) != len(approver_ids):
                    missing_ids = set(approver_ids) - {u.id for u in existing_approvers} # type: ignore
                    raise UserNotFoundError(f"Approvers with IDs {list(missing_ids)} not found")
                
                # Validate sequence orders
                sequence_orders = [approver.sequence_order for approver in request.approvers]
                if len(set(sequence_orders)) != len(sequence_orders):
                    raise ValidationError("Duplicate sequence orders not allowed")
                if min(sequence_orders) != 1 or max(sequence_orders) != len(sequence_orders):
                    raise ValidationError("Sequence orders must start from 1 and be consecutive")
                
                # Delete existing steps
                db.query(ApprovalStep).filter(ApprovalStep.rule_id == rule_id).delete()
                
                # Create new steps
                for approver_req in request.approvers:
                    step = ApprovalStep(
                        rule_id=rule_id,
                        approver_id=approver_req.approver_id,
                        sequence_order=approver_req.sequence_order,
                        required=approver_req.required
                    )
                    db.add(step)
            
            db.commit()
            db.refresh(rule)
            
            return ApprovalRuleService._model_to_response(rule, UpdateApprovalRuleResponse, db)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, (ApprovalRuleNotFoundError, UserNotFoundError, ValidationError)):
                raise e
            raise DatabaseError(f"Failed to update approval rule: {str(e)}")
    
    @staticmethod
    def delete_approval_rule(db: Session, rule_id: int) -> bool:
        """Delete an approval rule"""
        try:
            rule = db.query(ApprovalRule).filter(ApprovalRule.id == rule_id).first()
            if not rule:
                raise ApprovalRuleNotFoundError(f"Approval rule with ID {rule_id} not found")
            
            db.delete(rule)
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            if isinstance(e, ApprovalRuleNotFoundError):
                raise e
            raise DatabaseError(f"Failed to delete approval rule: {str(e)}")
    
    @staticmethod
    def get_approval_rule_stats(db: Session) -> ApprovalRuleStatsResponse:
        """Get approval rule statistics"""
        try:
            total_rules = db.query(ApprovalRule).count()
            
            # Rules by sequence type
            sequential_rules = db.query(ApprovalRule).filter(ApprovalRule.approver_sequence == 1).count()
            parallel_rules = db.query(ApprovalRule).filter(ApprovalRule.approver_sequence == 0).count()
            
            rules_by_sequence = {
                "sequential": sequential_rules,
                "parallel": parallel_rules
            }
            
            # Rules with manager approver
            rules_with_manager_approver = db.query(ApprovalRule).filter(ApprovalRule.is_manager_approver == True).count()
            
            # Average approvers per rule
            total_steps = db.query(ApprovalStep).count()
            average_approvers_per_rule = total_steps / total_rules if total_rules > 0 else 0
            
            return ApprovalRuleStatsResponse(
                total_rules=total_rules,
                rules_by_sequence=rules_by_sequence,
                rules_with_manager_approver=rules_with_manager_approver,
                average_approvers_per_rule=round(average_approvers_per_rule, 2)
            )
            
        except Exception as e:
            raise DatabaseError(f"Failed to get approval rule stats: {str(e)}")
    
    @staticmethod
    def _model_to_response(rule: ApprovalRule, response_type, db: Session):
        """Convert SQLAlchemy model to Pydantic response model"""
        # Get approvers
        approvers = []
        if hasattr(rule, 'steps') and rule.steps:
            for step in sorted(rule.steps, key=lambda x: x.sequence_order):
                approver_data = {
                    "id": safe_getattr(step, 'id'),
                    "approver_id": safe_getattr(step, 'approver_id'),
                    "approver_name": safe_getattr(step.approver, 'name', '') if hasattr(step, 'approver') and step.approver else '',
                    "approver_email": safe_getattr(step.approver, 'email', '') if hasattr(step, 'approver') and step.approver else '',
                    "required": safe_getattr(step, 'required', True),
                    "sequence_order": safe_getattr(step, 'sequence_order', 0)
                }
                approvers.append(ApproverResponse(**approver_data))
        
        data = {
            "id": safe_getattr(rule, 'id'),
            "user_id": safe_getattr(rule, 'user_id'),
            "user_name": safe_getattr(rule.user, 'name', '') if hasattr(rule, 'user') and rule.user else '',
            "user_email": safe_getattr(rule.user, 'email', '') if hasattr(rule, 'user') and rule.user else '',
            "description": safe_getattr(rule, 'description', ''),
            "manager_id": safe_getattr(rule, 'manager_id'),
            "manager_name": safe_getattr(rule.manager, 'name', None) if hasattr(rule, 'manager') and rule.manager else None,
            "is_manager_approver": safe_getattr(rule, 'is_manager_approver', False),
            "approver_sequence": "sequential" if safe_getattr(rule, 'approver_sequence', 1) == 1 else "parallel",
            "min_approval_percentage": safe_getattr(rule, 'min_approval_percentage', 100.0),
            "created_at": (lambda x: x.isoformat() if x is not None else datetime.utcnow().isoformat())(safe_getattr(rule, 'created_at')),
            "updated_at": (lambda x: x.isoformat() if x is not None else None)(safe_getattr(rule, 'updated_at')),
            "approvers": approvers
        }
        
        return response_type(**data)
    
    @staticmethod
    def _model_to_detailed_response(rule: ApprovalRule, db: Session) -> ApprovalRuleDetailResponse:
        """Convert SQLAlchemy model to detailed response model"""
        return ApprovalRuleService._model_to_response(rule, ApprovalRuleDetailResponse, db)