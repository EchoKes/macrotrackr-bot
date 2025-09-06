"""
Helper utilities for date/time operations and text processing.
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Tuple

from config import config

logger = logging.getLogger(__name__)


def get_daily_window_timestamps() -> Tuple[datetime, datetime]:
    """
    Get start and end timestamps for the current 24-hour cycle (5am to 5am).
    Returns tuple of (start_timestamp, end_timestamp).
    """
    now = datetime.now()
    
    # Get today's 5am
    today_5am = now.replace(hour=5, minute=0, second=0, microsecond=0)
    
    # If current time is before 5am, use yesterday's 5am as start
    if now.hour < 5:
        start_time = today_5am - timedelta(days=1)
        end_time = today_5am
    else:
        # If current time is after 5am, use today's 5am as start
        start_time = today_5am
        end_time = today_5am + timedelta(days=1)
    
    return start_time, end_time


def extract_total_calories(analysis_text: str) -> int:
    """
    Extract total calories from meal analysis text.
    Tries multiple patterns to handle different formats.
    Returns 0 if no calories found.
    """
    # Multiple patterns to handle different possible formats
    patterns = [
        r'\*Total\*:?\s*(\d+)\s*kcal',  # *Total:* 450 kcal
        r'Total:?\s*(\d+)\s*kcal',      # Total: 450 kcal
        r'Total.*?(\d+)\s*kcal',        # Total anything 450 kcal
        r'(\d+)\s*kcal.*?total',        # 450 kcal ... total (case insensitive)
        r'total.*?(\d+)\s*kcal',        # total ... 450 kcal (case insensitive)
        r'(\d+)\s*kcal.*?P\s*\d+g.*?C\s*\d+g.*?F\s*\d+g',  # Pattern with macros
    ]
    
    for pattern in patterns:
        match = re.search(pattern, analysis_text, re.IGNORECASE)
        if match:
            try:
                calories = int(match.group(1))
                # Sanity check: calories should be reasonable
                if config.MIN_CALORIE_VALUE <= calories <= config.MAX_CALORIE_VALUE:
                    logger.info(f"Extracted {calories} calories using pattern: {pattern}")
                    return calories
            except (ValueError, IndexError):
                continue
    
    logger.warning(f"Could not extract calories from text: {analysis_text[:200]}...")
    return 0