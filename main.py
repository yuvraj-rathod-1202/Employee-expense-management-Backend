from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.database.databse import Base, engine, test_connection
from app.api import api_router
from app.database.migration import run_migration
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Employee Expense Management API",
    description="A comprehensive API for managing employee expenses and companies",
    version="1.0.0",
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
]

# Allow all origins in production if RENDER environment is detected
if os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT"):
    origins = ["*"]
    logger.info("Production environment detected, allowing all origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Run startup tasks"""
    try:
        logger.info("Starting up Employee Expense Management API...")
        
        # Test database connection
        logger.info("Testing database connection...")
        if test_connection():
            logger.info("Database connection successful!")
            
            # Run database migration
            logger.info("Running database migration...")
            run_migration()
            logger.info("Database migration completed!")
        else:
            logger.error("Database connection failed!")
        
        logger.info("Startup completed!")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Log but don't crash the app

app.include_router(api_router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Employee Expense Management API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
def health_check():
    """Health check endpoint for deployment platforms"""
    try:
        # Test database connection
        db_status = test_connection()
        return {
            "status": "healthy" if db_status else "unhealthy",
            "database": "connected" if db_status else "disconnected",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")