from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, Text, Date
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
    converted_amount = Column(Numeric(12, 2), nullable=True)
    category = Column(String(100), nullable=False)
    description = Column(Text)
    remarks = Column(Text)
    expense_date = Column(Date, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(Date, default=datetime.utcnow)
    
    employee = relationship("User", back_populates="expenses")
    receipts = relationship("ExpenseReceipt", back_populates="expense", cascade="all, delete-orphan")
    approvals = relationship("ExpenseApproval", back_populates="expense", cascade="all, delete-orphan")
    paid_by_user = relationship("User", foreign_keys=[paid_by])
    submitted_by_user = relationship("User", foreign_keys=[submitted_by])
    
class ExpenseReceipt(Base):
    __tablename__ = "expense_receipts"
    
    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    file_url = Column(String(255), nullable=False)
    ocr_data = Column(Text, nullable=True)
    created_at = Column(Date, default=datetime.utcnow)
    
    expenses = relationship("Expense", back_populates="receipts")