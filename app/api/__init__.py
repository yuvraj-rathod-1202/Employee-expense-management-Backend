from fastapi import APIRouter
from app.api.v1 import companyrouter, userrouter, approvalroute, expense_route, expense_approval_route

api_router = APIRouter()

api_router.include_router(companyrouter.router, prefix="/api/v1")
api_router.include_router(userrouter.router, prefix="/api/v1")
api_router.include_router(approvalroute.router, prefix="/api/v1")
api_router.include_router(expense_route.router, prefix="/api/v1")
api_router.include_router(expense_approval_route.router, prefix="/api/v1")