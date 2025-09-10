"""
Telegram service for bot interactions.
"""
import requests
import base64
import logging
from typing import Optional

from config import config

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for interacting with Telegram Bot API."""
    
    @staticmethod
    def send_message(chat_id: str, text: str, photo_file_id: Optional[str] = None) -> bool:
        """
        Send a message or photo with caption to a Telegram chat.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text or photo caption
            photo_file_id: Optional Telegram file ID for photo
        
        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            if photo_file_id:
                # Send photo with caption
                url = f"{config.telegram_api_url}/sendPhoto"
                data = {
                    'chat_id': chat_id,
                    'photo': photo_file_id,
                    'caption': text,
                    'parse_mode': 'Markdown'
                }
            else:
                # Send text message
                url = f"{config.telegram_api_url}/sendMessage"
                data = {
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': 'Markdown'
                }
            
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Message sent successfully to chat {chat_id}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    @staticmethod
    def get_photo_from_telegram(file_id: str) -> Optional[str]:
        """
        Download photo from Telegram and return as base64 string.
        
        Args:
            file_id: Telegram file ID
        
        Returns:
            Base64 encoded image string or None if failed
        """
        try:
            # Get file info
            file_info_url = f"{config.telegram_api_url}/getFile"
            response = requests.get(file_info_url, params={'file_id': file_id}, timeout=10)
            response.raise_for_status()
            
            file_path = response.json()['result']['file_path']
            
            # Download file
            file_url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}"
            file_response = requests.get(file_url, timeout=30)
            file_response.raise_for_status()
            
            # Convert to base64
            return base64.b64encode(file_response.content).decode('utf-8')
            
        except requests.RequestException as e:
            logger.error(f"Failed to download photo from Telegram: {e}")
            return None

    @staticmethod
    def get_help_text() -> str:
        """Get the help text for the bot."""
        return (
            "🍽️ *Macro Tracker Bot*\n\n"
            "Send me a photo of your meal with a brief description as the caption, "
            "and I'll analyze the calories and macros for you!\n\n"
            "Commands:\n"
            "• /progress - View your daily calorie progress\n"
            "• /resetprogress - Reset your daily calorie progress\n"
            "• /deletelast - Delete your most recent meal submission\n\n"
            "Example: Send a photo with caption 'Grilled chicken breast with rice and vegetables'"
        )