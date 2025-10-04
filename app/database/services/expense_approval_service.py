from typing import List, Optional, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from datetime import datetime

from app.database.models.expense import Expense, ExpenseApproval
from app.database.models.approval import ApprovalRule, ApprovalStep
from app.database.models.users import User
from app.database.migration import safe_getattr, safe_setattr
from app.ReqResModels.approvalmodels import (
    ExpenseApprovalRequest,
    ExpenseApprovalResponse,
    ExpenseApprovalStatusResponse,
    BulkApprovalStatusResponse,
    PendingExpenseRequest,
    PendingReviewRequest,
    UserPendingRequestsResponse,
    ManagerPendingRequestsResponse
)
from app.logic.exceptions import (
    ValidationError,
    DatabaseError
)

class ExpenseNotFoundError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ExpenseApprovalService:
    
    @staticmethod
    def initiate_expense_approval(db: Session, expense_id: int) -> ExpenseApprovalStatusResponse:
        """Initialize approval process for an expense based on approval rules"""
        try:
            # Get expense with user info
            expense = db.query(Expense).options(
                joinedload(Expense.submitted_by_user)
            ).filter(Expense.id == expense_id).first()
            
            if not expense:
                raise ExpenseNotFoundError(f"Expense with ID {expense_id} not found")
            
            # Get approval rule for the user who submitted the expense
            approval_rule = db.query(ApprovalRule).options(
                joinedload(ApprovalRule.steps).joinedload(ApprovalStep.approver),
                joinedload(ApprovalRule.manager)
            ).filter(ApprovalRule.user_id == expense.submitted_by).first()
            
            if not approval_rule:
                # No approval rule - auto approve
                safe_setattr(expense, 'status', "approved")
                db.commit()
                return ExpenseApprovalService._build_approval_status_response(expense, [], approval_rule, db)
            
            # Clear existing approvals for this expense
            db.query(ExpenseApproval).filter(ExpenseApproval.expense_id == expense_id).delete()
            
            approvals_created = []
            
            # Create manager approval if required
            if safe_getattr(approval_rule, 'is_manager_approver', False) and safe_getattr(approval_rule, 'manager_id'):
                manager_approval = ExpenseApproval(
                    expense_id=expense_id,
                    approver_id=safe_getattr(approval_rule, 'manager_id'),
                    sequence_order=0,  # Manager approval comes first
                    is_manager_approval=True,
                    status="pending"
                )
                db.add(manager_approval)
                approvals_created.append(manager_approval)
            
            # Create approvals for each step
            for step in approval_rule.steps:
                step_approval = ExpenseApproval(
                    expense_id=expense_id,
                    approver_id=safe_getattr(step, 'approver_id'),
                    approval_step_id=safe_getattr(step, 'id'),
                    sequence_order=safe_getattr(step, 'sequence_order'),
                    is_manager_approval=False,
                    status="pending"
                )
                db.add(step_approval)
                approvals_created.append(step_approval)
            
            # Update expense status
            safe_setattr(expense, 'status', "in_progress")
            safe_setattr(expense, 'updated_at', datetime.utcnow())
            
            db.commit()
            
            return ExpenseApprovalService._build_approval_status_response(expense, approvals_created, approval_rule, db)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, ExpenseNotFoundError):
                raise e
            raise DatabaseError(f"Failed to initiate expense approval: {str(e)}")
    
    @staticmethod
    def submit_approval(db: Session, request: ExpenseApprovalRequest) -> ExpenseApprovalStatusResponse:
        """Submit an approval for an expense"""
        try:
            # Get the approval record
            approval = db.query(ExpenseApproval).filter(
                and_(
                    ExpenseApproval.expense_id == request.expense_id,
                    ExpenseApproval.approver_id == request.approver_id,
                    ExpenseApproval.status == "pending"
                )
            ).first()
            
            if not approval:
                raise ValidationError(f"No pending approval found for expense {request.expense_id} and approver {request.approver_id}")
            
            # Update approval
            safe_setattr(approval, 'status', request.status.value)
            safe_setattr(approval, 'comments', request.comments)
            safe_setattr(approval, 'approved_at', datetime.utcnow())
            
            db.commit()
            
            # Check overall approval status
            return ExpenseApprovalService.check_expense_approval_status(db, request.expense_id)
            
        except Exception as e:
            db.rollback()
            if isinstance(e, ValidationError):
                raise e
            raise DatabaseError(f"Failed to submit approval: {str(e)}")
    
    @staticmethod
    def check_expense_approval_status(db: Session, expense_id: int) -> ExpenseApprovalStatusResponse:
        """Check the current approval status of an expense"""
        try:
            # Get expense with approvals
            expense = db.query(Expense).options(
                joinedload(Expense.approvals).joinedload(ExpenseApproval.approver),
                joinedload(Expense.submitted_by_user)
            ).filter(Expense.id == expense_id).first()
            
            if not expense:
                raise ExpenseNotFoundError(f"Expense with ID {expense_id} not found")
            
            # Get approval rule
            approval_rule = db.query(ApprovalRule).options(
                joinedload(ApprovalRule.steps)
            ).filter(ApprovalRule.user_id == expense.submitted_by).first()
            
            # If no approval rule, expense should be auto-approved
            if not approval_rule:
                if safe_getattr(expense, 'status') == "pending":
                    safe_setattr(expense, 'status', "approved")
                    db.commit()
                return ExpenseApprovalService._build_approval_status_response(expense, [], None, db)
            
            approvals = expense.approvals
            approved_count = sum(1 for approval in approvals if safe_getattr(approval, 'status') == "approved")
            total_required = sum(1 for approval in approvals if safe_getattr(approval, 'status') in ["pending", "approved"])
            
            approval_percentage = (approved_count / total_required * 100) if total_required > 0 else 0
            
            # Check if manager approval is required and completed
            manager_approved = True
            if safe_getattr(approval_rule, 'is_manager_approver', False):
                manager_approval = next((a for a in approvals if safe_getattr(a, 'is_manager_approval', False)), None)
                manager_approved = bool(manager_approval and safe_getattr(manager_approval, 'status') == "approved")
            
            # Determine if we can proceed and what the next step is
            can_proceed, next_approver = ExpenseApprovalService._check_approval_progression(
                approvals, approval_rule, manager_approved
            )
            
            # Check if fully approved
            is_fully_approved = (
                approval_percentage >= safe_getattr(approval_rule, 'min_approval_percentage', 100) and
                manager_approved and
                ExpenseApprovalService._check_sequential_requirements(approvals, approval_rule)
            )
            
            # Update expense status if needed
            current_status = safe_getattr(expense, 'status')
            if is_fully_approved and current_status != "approved":
                safe_setattr(expense, 'status', "approved")
                safe_setattr(expense, 'updated_at', datetime.utcnow())
                db.commit()
            elif any(safe_getattr(a, 'status') == "rejected" for a in approvals) and current_status != "rejected":
                safe_setattr(expense, 'status', "rejected")
                safe_setattr(expense, 'updated_at', datetime.utcnow())
                db.commit()
            
            return ExpenseApprovalService._build_approval_status_response(expense, approvals, approval_rule, db)
            
        except Exception as e:
            if isinstance(e, ExpenseNotFoundError):
                raise e
            raise DatabaseError(f"Failed to check expense approval status: {str(e)}")
    
    @staticmethod
    def get_bulk_approval_status(db: Session, expense_ids: List[int]) -> BulkApprovalStatusResponse:
        """Get approval status for multiple expenses"""
        try:
            expense_statuses = []
            
            for expense_id in expense_ids:
                try:
                    status = ExpenseApprovalService.check_expense_approval_status(db, expense_id)
                    expense_statuses.append(status)
                except ExpenseNotFoundError:
                    continue
            
            # Generate summary
            summary = {
                "total_expenses": len(expense_statuses),
                "approved": sum(1 for status in expense_statuses if status.is_fully_approved),
                "pending": sum(1 for status in expense_statuses if status.current_status == "in_progress"),
                "rejected": sum(1 for status in expense_statuses if status.current_status == "rejected")
            }
            
            return BulkApprovalStatusResponse(
                expenses=expense_statuses,
                summary=summary
            )
            
        except Exception as e:
            raise DatabaseError(f"Failed to get bulk approval status: {str(e)}")
    
    @staticmethod
    def _check_approval_progression(approvals: List[ExpenseApproval], approval_rule: ApprovalRule, manager_approved: bool) -> tuple[bool, Optional[str]]:
        """Check if approval can proceed to next step and identify next approver"""
        
        # If manager approval required but not completed, that's the blocker
        if safe_getattr(approval_rule, 'is_manager_approver', False) and not manager_approved:
            manager_approval = next((a for a in approvals if safe_getattr(a, 'is_manager_approval', False)), None)
            if manager_approval:
                return False, safe_getattr(manager_approval.approver, 'name', 'Manager')
        
        # For sequential approval
        if safe_getattr(approval_rule, 'approver_sequence', 1) == 1:  # Sequential
            non_manager_approvals = [a for a in approvals if not safe_getattr(a, 'is_manager_approval', False)]
            non_manager_approvals.sort(key=lambda x: safe_getattr(x, 'sequence_order', 0))
            
            for approval in non_manager_approvals:
                if safe_getattr(approval, 'status') == "pending":
                    return True, safe_getattr(approval.approver, 'name', 'Unknown')
                elif safe_getattr(approval, 'status') == "rejected":
                    return False, None
        
        # For parallel approval
        else:  # Parallel
            pending_approvals = [a for a in approvals if safe_getattr(a, 'status') == "pending" and not safe_getattr(a, 'is_manager_approval', False)]
            if pending_approvals:
                return True, f"{len(pending_approvals)} approvers"
        
        return True, None
    
    @staticmethod
    def _check_sequential_requirements(approvals: List[ExpenseApproval], approval_rule: ApprovalRule) -> bool:
        """Check if sequential approval requirements are met"""
        if safe_getattr(approval_rule, 'approver_sequence', 1) == 0:  # Parallel
            return True
        
        # Sequential - check that all required previous steps are approved
        non_manager_approvals = [a for a in approvals if not safe_getattr(a, 'is_manager_approval', False)]
        non_manager_approvals.sort(key=lambda x: safe_getattr(x, 'sequence_order', 0))
        
        for i, approval in enumerate(non_manager_approvals):
            if safe_getattr(approval, 'status') == "rejected":
                return False
            # For sequential, if a required step is pending and there are later approved steps, it's invalid
            if safe_getattr(approval, 'status') == "pending":
                # Check if any later steps are approved (invalid for sequential)
                later_approved = any(
                    safe_getattr(a, 'status') == "approved" for a in non_manager_approvals[i+1:]
                )
                if later_approved:
                    return False
        
        return True
    
    @staticmethod
    def _build_approval_status_response(
        expense: Expense, 
        approvals: List[ExpenseApproval], 
        approval_rule: Optional[ApprovalRule], 
        db: Session
    ) -> ExpenseApprovalStatusResponse:
        """Build the approval status response"""
        
        if not approval_rule:
            expense_id = getattr(expense, 'id', 0)
            current_status = getattr(expense, 'status', 'approved')
            return ExpenseApprovalStatusResponse(
                expense_id=expense_id,
                current_status=current_status,
                is_fully_approved=current_status == "approved",
                approval_percentage=100.0,
                required_percentage=0.0,
                next_approver=None,
                pending_approvals=[],
                completed_approvals=[],
                manager_approval_required=False,
                manager_approved=True,
                sequential_approval=False,
                can_proceed_to_next_step=True
            )
        
        # Convert approvals to response objects
        approval_responses = []
        for approval in approvals:
            approval_responses.append(ExpenseApprovalResponse(
                id=getattr(approval, 'id', 0),
                expense_id=getattr(approval, 'expense_id', 0),
                approver_id=getattr(approval, 'approver_id', 0),
                approver_name=getattr(approval.approver, 'name', 'Unknown') if hasattr(approval, 'approver') and approval.approver else 'Unknown',
                status=getattr(approval, 'status', 'pending'),
                sequence_order=getattr(approval, 'sequence_order', 0),
                is_manager_approval=getattr(approval, 'is_manager_approval', False),
                comments=getattr(approval, 'comments', None),
                approved_at=getattr(approval, 'approved_at', None),
                created_at=getattr(approval, 'created_at', datetime.utcnow())
            ))
        
        # Separate pending and completed approvals
        pending_approvals = [a for a in approval_responses if a.status == "pending"]
        completed_approvals = [a for a in approval_responses if a.status != "pending"]
        
        # Calculate approval percentage
        approved_count = len([a for a in approval_responses if a.status == "approved"])
        total_count = len(approval_responses)
        approval_percentage = (approved_count / total_count * 100) if total_count > 0 else 0
        
        # Check manager approval status
        is_manager_approver = getattr(approval_rule, 'is_manager_approver', False)
        manager_approved = True
        if is_manager_approver:
            manager_approval = next((a for a in approval_responses if a.is_manager_approval), None)
            manager_approved = bool(manager_approval and manager_approval.status == "approved")
        
        # Determine next approver
        can_proceed, next_approver = ExpenseApprovalService._check_approval_progression(
            approvals, approval_rule, manager_approved
        )
        
        # Check if fully approved
        min_percentage = getattr(approval_rule, 'min_approval_percentage', 100)
        is_fully_approved = bool(
            approval_percentage >= min_percentage and
            manager_approved and
            ExpenseApprovalService._check_sequential_requirements(approvals, approval_rule)
        )
        
        expense_id = getattr(expense, 'id', 0)
        current_status = getattr(expense, 'status', 'pending')
        approver_sequence = getattr(approval_rule, 'approver_sequence', 1)
        
        return ExpenseApprovalStatusResponse(
            expense_id=expense_id,
            current_status=current_status,
            is_fully_approved=is_fully_approved,
            approval_percentage=approval_percentage,
            required_percentage=min_percentage,
            next_approver=next_approver,
            pending_approvals=pending_approvals,
            completed_approvals=completed_approvals,
            manager_approval_required=is_manager_approver,
            manager_approved=manager_approved,
            sequential_approval=approver_sequence == 1,
            can_proceed_to_next_step=can_proceed
        )
    
    @staticmethod
    def get_user_pending_requests(db: Session, user_id: int) -> UserPendingRequestsResponse:
        """Get all pending expense requests for a specific user"""
        try:
            # Get all expenses submitted by the user that are still pending approval
            pending_expenses = db.query(Expense).options(
                joinedload(Expense.approvals).joinedload(ExpenseApproval.approver)
            ).filter(
                and_(
                    Expense.submitted_by == user_id,
                    or_(
                        Expense.status == "pending",
                        Expense.status == "in_progress"
                    )
                )
            ).all()
            
            pending_requests = []
            total_amount = 0.0
            
            for expense in pending_expenses:
                # Get approval status for this expense
                expense_id = getattr(expense, 'id', 0)
                approval_status = ExpenseApprovalService.check_expense_approval_status(db, expense_id)
                
                pending_request = PendingExpenseRequest(
                    expense_id=getattr(expense, 'id', 0),
                    amount=float(getattr(expense, 'amount', 0)),
                    currency_code=getattr(expense, 'currency_code', 'INR'),
                    category=getattr(expense, 'category', ''),
                    description=getattr(expense, 'description', None),
                    expense_date=getattr(expense, 'expense_date', datetime.utcnow()),
                    submitted_date=getattr(expense, 'created_at', datetime.utcnow()),
                    current_status=approval_status.current_status,
                    approval_percentage=approval_status.approval_percentage,
                    required_percentage=approval_status.required_percentage,
                    next_approver=approval_status.next_approver,
                    pending_approvals_count=len(approval_status.pending_approvals),
                    total_approvals_count=len(approval_status.pending_approvals) + len(approval_status.completed_approvals)
                )
                
                pending_requests.append(pending_request)
                total_amount += float(getattr(expense, 'amount', 0))
            
            return UserPendingRequestsResponse(
                pending_requests=pending_requests,
                total_count=len(pending_requests),
                pending_amount=total_amount
            )
            
        except Exception as e:
            raise DatabaseError(f"Failed to get user pending requests: {str(e)}")
    
    @staticmethod
    def get_manager_pending_reviews(db: Session, manager_id: int) -> ManagerPendingRequestsResponse:
        """Get all expenses pending review by a specific manager/approver"""
        try:
            # Get all expense approvals where this user is the approver and status is pending
            pending_approvals = db.query(ExpenseApproval).options(
                joinedload(ExpenseApproval.expense).joinedload(Expense.submitted_by_user),
                joinedload(ExpenseApproval.approval_step)
            ).filter(
                and_(
                    ExpenseApproval.approver_id == manager_id,
                    ExpenseApproval.status == "pending"
                )
            ).all()
            
            pending_reviews = []
            total_amount = 0.0
            urgent_count = 0
            
            for approval in pending_approvals:
                expense = approval.expense
                if not expense:
                    continue
                
                submitted_by_user = getattr(expense, 'submitted_by_user', None)
                
                # Check if this approval can be processed now (for sequential approvals)
                expense_id = getattr(expense, 'id', 0)
                approval_status = ExpenseApprovalService.check_expense_approval_status(db, expense_id)
                can_approve_now = approval_status.can_proceed_to_next_step
                
                # Check if urgent (more than 3 days old)
                created_at = getattr(expense, 'created_at', datetime.utcnow())
                days_old = (datetime.utcnow() - created_at).days
                if days_old > 3:
                    urgent_count += 1
                
                pending_review = PendingReviewRequest(
                    expense_id=getattr(expense, 'id', 0),
                    submitted_by_id=getattr(expense, 'submitted_by', 0),
                    submitted_by_name=getattr(submitted_by_user, 'name', 'Unknown') if submitted_by_user else 'Unknown',
                    submitted_by_email=getattr(submitted_by_user, 'email', '') if submitted_by_user else '',
                    amount=float(getattr(expense, 'amount', 0)),
                    currency_code=getattr(expense, 'currency_code', 'INR'),
                    category=getattr(expense, 'category', ''),
                    description=getattr(expense, 'description', None),
                    expense_date=getattr(expense, 'expense_date', datetime.utcnow()),
                    submitted_date=getattr(expense, 'created_at', datetime.utcnow()),
                    my_approval_step=getattr(approval, 'sequence_order', 1),
                    is_manager_approval=getattr(approval, 'is_manager_approval', False),
                    can_approve_now=can_approve_now,
                    approval_deadline=None  # Could be calculated based on business rules
                )
                
                pending_reviews.append(pending_review)
                total_amount += float(getattr(expense, 'amount', 0))
            
            return ManagerPendingRequestsResponse(
                pending_reviews=pending_reviews,
                total_count=len(pending_reviews),
                total_amount=total_amount,
                urgent_count=urgent_count
            )
            
        except Exception as e:
            raise DatabaseError(f"Failed to get manager pending reviews: {str(e)}")
    
    @staticmethod
    def get_admin_pending_reviews(db: Session) -> ManagerPendingRequestsResponse:
        """Get all expenses pending review across the system (admin view)"""
        try:
            # Get all pending expense approvals
            pending_approvals = db.query(ExpenseApproval).options(
                joinedload(ExpenseApproval.expense).joinedload(Expense.submitted_by_user),
                joinedload(ExpenseApproval.approver),
                joinedload(ExpenseApproval.approval_step)
            ).filter(ExpenseApproval.status == "pending").all()
            
            pending_reviews = []
            total_amount = 0.0
            urgent_count = 0
            
            for approval in pending_approvals:
                expense = approval.expense
                if not expense:
                    continue
                
                submitted_by_user = getattr(expense, 'submitted_by_user', None)
                approver = getattr(approval, 'approver', None)
                
                # Check if urgent (more than 3 days old)
                created_at = getattr(expense, 'created_at', datetime.utcnow())
                days_old = (datetime.utcnow() - created_at).days
                if days_old > 3:
                    urgent_count += 1
                
                # Check if this approval can be processed now
                expense_id = getattr(expense, 'id', 0)
                approval_status = ExpenseApprovalService.check_expense_approval_status(db, expense_id)
                can_approve_now = approval_status.can_proceed_to_next_step
                
                pending_review = PendingReviewRequest(
                    expense_id=getattr(expense, 'id', 0),
                    submitted_by_id=getattr(expense, 'submitted_by', 0),
                    submitted_by_name=getattr(submitted_by_user, 'name', 'Unknown') if submitted_by_user else 'Unknown',
                    submitted_by_email=getattr(submitted_by_user, 'email', '') if submitted_by_user else '',
                    amount=float(getattr(expense, 'amount', 0)),
                    currency_code=getattr(expense, 'currency_code', 'INR'),
                    category=getattr(expense, 'category', ''),
                    description=getattr(expense, 'description', None),
                    expense_date=getattr(expense, 'expense_date', datetime.utcnow()),
                    submitted_date=getattr(expense, 'created_at', datetime.utcnow()),
                    my_approval_step=getattr(approval, 'sequence_order', 1),
                    is_manager_approval=getattr(approval, 'is_manager_approval', False),
                    can_approve_now=can_approve_now,
                    approval_deadline=None
                )
                
                pending_reviews.append(pending_review)
                total_amount += float(getattr(expense, 'amount', 0))
            
            return ManagerPendingRequestsResponse(
                pending_reviews=pending_reviews,
                total_count=len(pending_reviews),
                total_amount=total_amount,
                urgent_count=urgent_count
            )
            
        except Exception as e:
            raise DatabaseError(f"Failed to get admin pending reviews: {str(e)}")