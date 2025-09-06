"""
Database models and operations for meal calories.
"""
import logging
from datetime import datetime
from typing import Optional

from database.connection import get_db_connection
from utils.helpers import get_daily_window_timestamps

logger = logging.getLogger(__name__)


class MealCalorie:
    """Model for meal calorie database operations."""
    
    @staticmethod
    def store(user_id: int, user_name: str, calories: int, meal_analysis: str) -> bool:
        """Store meal calories in the database."""
        try:
            conn = get_db_connection()
            if not conn:
                return False
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO meal_calories (user_id, user_name, calories, meal_analysis)
                    VALUES (%s, %s, %s, %s)
                """, (user_id, user_name, calories, meal_analysis))
            
            conn.commit()
            conn.close()
            logger.info(f"Stored {calories} calories for user {user_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store meal calories: {e}")
            return False

    @staticmethod
    def get_daily_total(user_id: int) -> int:
        """Get total calories for the user within the current 5am-to-5am window."""
        try:
            start_time, _ = get_daily_window_timestamps()
            
            conn = get_db_connection()
            if not conn:
                return 0
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COALESCE(SUM(calories), 0) as total_calories
                    FROM meal_calories
                    WHERE user_id = %s AND created_at >= %s
                """, (user_id, start_time))
                
                result = cur.fetchone()
                total_calories = result[0] if result else 0
            
            conn.close()
            logger.info(f"Retrieved {total_calories} total calories for user {user_id}")
            return total_calories
            
        except Exception as e:
            logger.error(f"Failed to get daily calories: {e}")
            return 0

    @staticmethod
    def reset_daily_total(user_id: int) -> bool:
        """Reset (delete) all meal calories for the user within the current 5am-to-5am window."""
        try:
            start_time, _ = get_daily_window_timestamps()
            
            conn = get_db_connection()
            if not conn:
                return False
            
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM meal_calories
                    WHERE user_id = %s AND created_at >= %s
                """, (user_id, start_time))
                
                deleted_count = cur.rowcount
            
            conn.commit()
            conn.close()
            logger.info(f"Reset {deleted_count} meal entries for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset daily calories: {e}")
            return False