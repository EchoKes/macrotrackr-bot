"""
Progress service for calorie tracking and visualization.
"""
import logging
from typing import Dict

from config import config
from database.models import MealCalorie

logger = logging.getLogger(__name__)


class ProgressService:
    """Service for calculating and formatting progress information."""
    
    @staticmethod
    def calculate_daily_progress(user_id: int) -> Dict[str, int]:
        """
        Calculate current daily calorie progress from database.
        Returns dict with progress information.
        """
        total_calories = MealCalorie.get_daily_total(user_id)
        
        percentage = min(100, round((total_calories / config.DAILY_CALORIE_TARGET) * 100)) if config.DAILY_CALORIE_TARGET > 0 else 0
        remaining_calories = max(0, config.DAILY_CALORIE_TARGET - total_calories)
        
        return {
            'total_calories': total_calories,
            'target_calories': config.DAILY_CALORIE_TARGET,
            'percentage': percentage,
            'remaining_calories': remaining_calories
        }

    @staticmethod
    def create_progress_bar(percentage: int, length: int = None) -> str:
        """
        Create a visual progress bar.
        
        Args:
            percentage: Progress percentage (0-100)
            length: Length of progress bar (defaults to config value)
        
        Returns:
            Progress bar string
        """
        if length is None:
            length = config.PROGRESS_BAR_LENGTH
            
        filled_length = round(length * percentage / 100)
        bar = '█' * filled_length + '░' * (length - filled_length)
        return f"[{bar}]"

    @staticmethod
    def format_progress_message(progress: Dict[str, int]) -> str:
        """
        Format the progress information into a message focused on remaining calories.
        
        Args:
            progress: Progress dictionary from calculate_daily_progress
        
        Returns:
            Formatted progress message
        """
        progress_bar = ProgressService.create_progress_bar(progress['percentage'])
        
        message = f"""📊 *Daily Calorie Progress*
{progress_bar} {progress['total_calories']} / {progress['target_calories']} kcal ({progress['percentage']}%)

🎯 Remaining: {progress['remaining_calories']} kcal"""
        
        return message

    @staticmethod
    def reset_progress(user_id: int) -> bool:
        """
        Reset daily progress for a user.
        
        Args:
            user_id: User ID to reset progress for
        
        Returns:
            True if reset successful, False otherwise
        """
        return MealCalorie.reset_daily_total(user_id)