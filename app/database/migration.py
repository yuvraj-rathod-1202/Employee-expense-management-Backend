from sqlalchemy import text, inspect, MetaData
from app.database.databse import engine, Base
from app.database.models.users import User, Company
import logging

# Global cache for column existence checks
_column_cache = {}

def has_column(table_name: str, column_name: str) -> bool:
    """Check if a table has a specific column (with caching)"""
    cache_key = f"{table_name}.{column_name}"
    
    if cache_key not in _column_cache:
        try:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            _column_cache[cache_key] = column_name in columns
        except Exception:
            _column_cache[cache_key] = False
    
    return _column_cache[cache_key]

def add_column_if_not_exists(table_name: str, column_name: str, column_type: str):
    """Add a column to a table if it doesn't exist"""
    if not has_column(table_name, column_name):
        try:
            with engine.connect() as conn:
                sql = text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                conn.execute(sql)
                conn.commit()
                print(f"Added column {column_name} to {table_name} table")
                # Update cache
                _column_cache[f"{table_name}.{column_name}"] = True
        except Exception as e:
            print(f"Failed to add column {column_name} to {table_name}: {e}")

def check_and_add_missing_columns():
    """Check for missing columns and add them if necessary"""
    
    print("Checking for missing database columns...")
    
    try:
        # Check and add missing columns for users table
        expected_user_columns = {
            'updated_at': 'TIMESTAMP',
        }
        
        for col_name, col_type in expected_user_columns.items():
            add_column_if_not_exists('users', col_name, col_type)
        
        # Check and add missing columns for companies table  
        expected_company_columns = {
            'updated_at': 'TIMESTAMP',
            'description': 'TEXT',
        }
        
        for col_name, col_type in expected_company_columns.items():
            add_column_if_not_exists('companies', col_name, col_type)
            
        print("Column verification completed")
            
    except Exception as e:
        print(f"Error checking database schema: {e}")

def create_tables_if_not_exist():
    """Create tables if they don't exist"""
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created/verified")
    except Exception as e:
        print(f"Error creating tables: {e}")

def run_migration():
    """Run complete database migration"""
    print("Starting database migration...")
    
    # Create tables first
    create_tables_if_not_exist()
    
    # Then add missing columns
    check_and_add_missing_columns()
    
    print("Database migration completed!")

def safe_setattr(obj, attr, value, default=None):
    """Safely set an attribute, handling missing columns"""
    try:
        setattr(obj, attr, value)
    except Exception:
        if default is not None:
            setattr(obj, attr, default)

def safe_getattr(obj, attr, default=None):
    """Safely get an attribute, handling missing columns"""
    try:
        return getattr(obj, attr, default)
    except Exception:
        return default