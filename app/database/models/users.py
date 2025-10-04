from sqlalchemy import Column, Integer, String, ForeignKey, Text, TIMESTAMP
from sqlalchemy.orm import relationship
from app.database.databse import Base
from datetime import datetime

class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    country = Column(String(255), nullable=False)
    currency_code = Column(String(10), nullable=False, default="INR")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=True)
    
    users = relationship("User", back_populates="company", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="employee")
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, nullable=True)
    # approval_rule_id = Column(Integer, ForeignKey("approval_rules.id"), nullable=True)
    
    manager = relationship("User", remote_side=[id])
    # expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    # approval_rule = relationship("ApprovalRule", back_populates="user", uselist=False")
    company = relationship("Company", back_populates="users")
    
