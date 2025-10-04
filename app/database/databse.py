from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./test.db"
    logger.warning("No DATABASE_URL found, using SQLite fallback")

# Configure database engine with proper settings for Supabase pooler
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL configuration for Supabase pooler
    engine_kwargs = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,  # Recycle connections every 30 minutes
        "pool_pre_ping": True,  # Validate connections before use
        "echo": False,  # Disable echo in production
        "connect_args": {
            "sslmode": "require",
            "connect_timeout": 10,
            "application_name": "expense_management_api"
        }
    }
    
    try:
        engine = create_engine(DATABASE_URL, **engine_kwargs)
        logger.info("PostgreSQL engine created successfully with Supabase pooler")
    except Exception as e:
        logger.error(f"Failed to create PostgreSQL engine: {e}")
        # Fallback to SQLite for development
        DATABASE_URL = "sqlite:///./test.db"
        engine = create_engine(DATABASE_URL, echo=True)
        logger.info("Falling back to SQLite")
else:
    # SQLite configuration for development
    engine = create_engine(DATABASE_URL, echo=True)
    logger.info("Using SQLite database")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Test database connection
def test_connection():
    """Test database connection on startup"""
    try:
        from sqlalchemy import text
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            connection.commit()
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False