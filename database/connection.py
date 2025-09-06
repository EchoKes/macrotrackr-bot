"""
Database connection and initialization utilities.
"""
import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError as e:
    logger.error(f"PostgreSQL dependencies not available: {e}")
    POSTGRES_AVAILABLE = False


def get_db_connection():
    """Get a connection to the PostgreSQL database."""
    if not POSTGRES_AVAILABLE:
        logger.error("PostgreSQL not available")
        return None
    try:
        return psycopg2.connect(config.DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def init_database() -> bool:
    """Initialize the database table for meal calories."""
    try:
        if not POSTGRES_AVAILABLE:
            logger.error("PostgreSQL not available - cannot initialize database")
            return False
            
        conn = get_db_connection()
        if not conn:
            logger.error("No database connection - cannot initialize database")
            return False
        
        with conn.cursor() as cur:
            # Create table if it doesn't exist
            logger.info("Creating meal_calories table...")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS meal_calories (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    user_name VARCHAR(255),
                    calories INTEGER NOT NULL,
                    meal_analysis TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Create index on user_id and created_at for faster queries
            logger.info("Creating database index...")
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_meal_calories_user_date 
                ON meal_calories(user_id, created_at);
            """)
            
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if 'conn' in locals() and conn:
            try:
                conn.close()
            except:
                pass
        return False


def check_db_connection() -> str:
    """Check database connection status."""
    conn = get_db_connection()
    if conn:
        conn.close()
        return 'connected'
    else:
        return 'disconnected'