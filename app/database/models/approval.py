from sqlalchemy import Column, Integer, Numeric, String, ForeignKey, Text, Date, Boolean, Float
from sqlalchemy.orm import relationship
from app.database.databse import Base
from datetime import datetime

class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    description = Column(Text)
    is_manager_approver = Column(Boolean, default=False)
    approver_sequence = Column(Integer, nullable=False)
    min_approval_percentage = Column(Float, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # user is to whom this rule belongs
    user = relationship("User", back_populates="approval_rule")
    
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True) # manager who approves if is_manager_approver is True
    manager = relationship("User", foreign_keys=[manager_id])

    steps = relationship("ApprovalStep", back_populates="approval_rule", cascade="all, delete-orphan")
    

class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    id = Column(Integer, primary_key=True, index=True)
    sequence_order = Column(Integer, nullable=False) # 1, 2, 3 if sequenctial
    
    rule_id = Column(Integer, ForeignKey("approval_rules.id", ondelete="CASCADE"), nullable=False)
    
    approver_id =  Column(Integer, ForeignKey("users.id"), nullable=False) # user who approves in this step
    approver = relationship("User")
    
    required = Column(Boolean, default=False) # if False, this step is optional