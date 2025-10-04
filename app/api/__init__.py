from fastapi import APIRouter
from app.api.v1 import companyrouter, userrouter

api_router = APIRouter()

api_router.include_router(companyrouter.router, prefix="/api/v1")
api_router.include_router(userrouter.router, prefix="/api/v1")