# scripts/setup_database.py
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.database import engine, Base
from models import database  # Import to register models
from config.logging import setup_logging

def init_db():
    """Initialize database tables"""
    print("Creating database tables...")
    
    # Create all tables defined in models that inherit from Base
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

def drop_db():
    """Drop all database tables"""
    print("Dropping all database tables...")
    
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped successfully.")

def reset_db():
    """Reset database (drop and recreate all tables)"""
    print("Resetting database...")
    drop_db()
    init_db()
    print("Database reset completed.")

if __name__ == "__main__":
    # Setup logging
    setup_logging()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "init":
            init_db()
        elif command == "drop":
            drop_db()
        elif command == "reset":
            reset_db()
        else:
            print("Usage: python setup_database.py [init|drop|reset]")
            print("  init  - Create all tables")
            print("  drop  - Drop all tables")
            print("  reset - Drop and recreate all tables")
    else:
        # Default to init
        init_db()
