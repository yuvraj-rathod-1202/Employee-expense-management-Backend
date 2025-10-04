from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, Text, Date, Boolean, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.databse import Base
from datetime import datetime

class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    submitted_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paid_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency_code = Column(String(10), nullable=False, default="INR")
    category = Column(String(100), nullable=False)
    description = Column(Text)
    remarks = Column(Text, default=None)
    expense_date = Column(Date, nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected, in_progress
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    submitted_by_user = relationship("User", foreign_keys=[submitted_by])
    paid_by_user = relationship("User", foreign_keys=[paid_by])
    receipts = relationship("ExpenseReceipt", back_populates="expense", cascade="all, delete-orphan")
    approvals = relationship("ExpenseApproval", back_populates="expense", cascade="all, delete-orphan")
    
class ExpenseReceipt(Base):
    __tablename__ = "expense_receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    expense = relationship("Expense", back_populates="receipts")

class ExpenseApproval(Base):
    __tablename__ = "expense_approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_step_id = Column(Integer, ForeignKey("approval_steps.id"), nullable=True)  # Reference to approval step
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected
    sequence_order = Column(Integer, nullable=False, default=1)
    is_manager_approval = Column(Boolean, default=False)
    comments = Column(Text, nullable=True)
    approved_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    
    expense = relationship("Expense", back_populates="approvals")
    approver = relationship("User")
    approval_step = relationship("ApprovalStep")