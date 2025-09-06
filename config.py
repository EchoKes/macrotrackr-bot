"""
Configuration settings for MacroTrackr Bot.
"""
import os
from typing import Optional

class Config:
    """Configuration class for environment variables and constants."""
    
    # Environment variables
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    CHANNEL_ID: Optional[str] = os.getenv('CHANNEL_ID')
    DATABASE_URL: Optional[str] = os.getenv('DATABASE_URL')
    PORT: int = int(os.getenv('PORT', 5000))
    
    # Application constants
    DAILY_CALORIE_TARGET: int = 1350
    PROGRESS_BAR_LENGTH: int = 20
    MAX_CALORIE_VALUE: int = 3000
    MIN_CALORIE_VALUE: int = 0
    
    # Telegram API configuration
    @property
    def telegram_api_url(self) -> str:
        """Get the Telegram API base URL."""
        if not self.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        return f"https://api.telegram.org/bot{self.TELEGRAM_BOT_TOKEN}"
    
    @classmethod
    def validate_required_env_vars(cls) -> None:
        """Validate that all required environment variables are set."""
        required_vars = ['TELEGRAM_BOT_TOKEN', 'OPENAI_API_KEY', 'CHANNEL_ID', 'DATABASE_URL']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Global config instance
config = Config()