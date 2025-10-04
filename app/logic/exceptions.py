from typing import Optional

class BaseCustomError(Exception):
    """Base exception class for custom errors"""
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

class DatabaseError(BaseCustomError):
    """Raised when database operations fail"""
    def __init__(self, message: str):
        super().__init__(message, "DATABASE_ERROR")

class CompanyNotFoundError(BaseCustomError):
    """Raised when a company is not found"""
    def __init__(self, message: str):
        super().__init__(message, "COMPANY_NOT_FOUND")

class CompanyAlreadyExistsError(BaseCustomError):
    """Raised when trying to create a company that already exists"""
    def __init__(self, message: str):
        super().__init__(message, "COMPANY_ALREADY_EXISTS")

class ValidationError(BaseCustomError):
    """Raised when validation fails"""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")

class AuthenticationError(BaseCustomError):
    """Raised when authentication fails"""
    def __init__(self, message: str):
        super().__init__(message, "AUTHENTICATION_ERROR")

class AuthorizationError(BaseCustomError):
    """Raised when authorization fails"""
    def __init__(self, message: str):
        super().__init__(message, "AUTHORIZATION_ERROR")